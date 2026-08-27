"""IOC extraction and explainable defensive heuristics."""
import re
from pathlib import PurePath

from ._models import Finding

URL_RE = re.compile(r"https?://[^\s'\"<>]+", re.I)
IP_RE = re.compile(r"(?<!\d)(?:\d{1,3}\.){3}\d{1,3}(?!\d)")
DOMAIN_RE = re.compile(r"(?<![@\w])(?:[a-z0-9-]+\.)+(?:com|net|org|io|dev|ru|cn|xyz|top|site|online)(?!\w)", re.I)

RULES = (
    ("command.execution", "execution", "high", 0.85, ("powershell", "cmd.exe", "subprocess", "os.system", "wscript", "cscript")),
    ("persistence.windows", "persistence", "high", 0.85, ("currentversion\\run", "schtasks", "startup\\", "reg add")),
    ("credential.access", "credential_access", "critical", 0.9, ("login data", "local state", "cookies", "wallet", "discord\\local storage")),
    ("network.download", "network", "high", 0.8, ("downloadstring", "invoke-webrequest", "urlretrieve", "curl ", "wget ")),
)


def extract_iocs(strings):
    text = "\n".join(strings)
    urls = sorted(set(URL_RE.findall(text)))[:200]
    ips = []
    for value in IP_RE.findall(text):
        if all(0 <= int(part) <= 255 for part in value.split(".")):
            ips.append(value)
    domains = sorted(set(DOMAIN_RE.findall(text)))[:200]
    return {"urls": urls, "ips": sorted(set(ips))[:200], "domains": domains}


def inspect_indicators(name: str, data: bytes, strings):
    text = "\n".join(strings).lower()
    findings = []
    for rule_id, category, severity, confidence, needles in RULES:
        hits = sorted({needle for needle in needles if needle in text})
        if hits:
            findings.append(Finding(rule_id, category, severity, confidence,
                "Suspicious static indicator(s) found.", ", ".join(hits), name))

    suffix = PurePath(name).suffix.lower()
    if data.startswith(b"MZ") and suffix not in (".exe", ".dll", ".sys", ".scr", ".cpl"):
        findings.append(Finding("file.extension_mismatch", "evasion", "medium", 0.9,
            "Windows PE content does not match the filename extension.", suffix or "no extension", name))

    if data.startswith(b"MZ") and b"luajit" in data[:4 * 1024 * 1024].lower():
        findings.append(Finding("runtime.luajit", "runtime", "info", 0.95,
            "Windows executable contains LuaJIT runtime identifiers.", "LuaJIT/luajit.exe", name))

    if suffix in (".lua", ".txt") and len(data) >= 4096:
        escaped = len(re.findall(rb"\\\d{2,3}", data))
        density = escaped / max(1, len(data))
        if escaped >= 50 or density > 0.01:
            findings.append(Finding("script.obfuscation.numeric_escapes", "obfuscation", "high", 0.9,
                "Script contains a high volume of numeric escape sequences.", f"numeric_escapes={escaped}", name))

        lines = data.count(b"\n") + 1
        lowered_data = data.lower()
        flattened = len(data) >= 32768 and lines <= 2 and b"return(function" in lowered_data[:4096]
        if flattened:
            findings.append(Finding("script.obfuscation.flattened", "obfuscation", "high", 0.85,
                "Large script is flattened into a single line with nested function wrappers.",
                f"bytes={len(data)}, lines={lines}", name))

        prometheus_tokens = (
            b"getfenv", b"_env", b"unpack", b"newproxy", b"setmetatable",
            b"getmetatable", b"select",
        )
        environment_signature = all(token in lowered_data for token in prometheus_tokens)
        dispatcher_count = len(re.findall(rb"if\s+[A-Za-z_]\w*\s*<", data))
        if flattened and environment_signature and dispatcher_count >= 32:
            findings.append(Finding(
                "obfuscator.prometheus_vm", "obfuscation", "info", 0.98,
                "Script structure matches the custom VM wrapper emitted by Prometheus Vmify.",
                f"environment_signature=true, dispatcher_comparisons={dispatcher_count}", name))
    return findings
