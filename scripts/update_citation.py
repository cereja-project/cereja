import argparse
import re
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
INIT_FILE = PROJECT_ROOT / "cereja" / "__init__.py"
CFF_FILE = PROJECT_ROOT / "CITATION.cff"
BIB_FILE = PROJECT_ROOT / "CITATION.bib"


def _read_text(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def _write_text(path: Path, content: str) -> None:
    path.write_text(content, encoding="utf-8", newline="\n")


def _extract_version_raw(init_text: str) -> str:
    match = re.search(r"^VERSION\s*=\s*\"([^\"]+)\"\s*$", init_text, re.MULTILINE)
    if not match:
        raise ValueError("VERSION not found in cereja/__init__.py")
    return match.group(1)


def _pep440_from_raw(raw_version: str) -> str:
    parts = raw_version.split(".")
    if len(parts) != 5:
        raise ValueError("VERSION must have 5 parts: major.minor.patch.stage.serial")

    major, minor, patch, stage, serial = parts
    try:
        major_i = int(major)
        minor_i = int(minor)
        patch_i = int(patch)
        serial_i = int(serial)
    except ValueError as exc:
        raise ValueError("VERSION numeric parts must be integers") from exc

    if stage not in {"alpha", "beta", "rc", "final"}:
        raise ValueError("VERSION stage must be one of: alpha, beta, rc, final")

    base = f"{major_i}.{minor_i}.{patch_i}"
    if stage == "final" and serial_i == 0:
        return base

    stage_map = {"alpha": "a", "beta": "b", "rc": "rc"}
    if stage in stage_map:
        return f"{base}{stage_map[stage]}{serial_i}"

    return f"{base}-{serial_i}"


def _update_cff(content: str, version: str) -> str:
    if re.search(r"^version:\s*\"?[^\n\"]+\"?\s*$", content, re.MULTILINE):
        return re.sub(
            r"^version:\s*\"?[^\n\"]+\"?\s*$",
            f"version: \"{version}\"",
            content,
            flags=re.MULTILINE,
        )

    return content.rstrip() + f"\nversion: \"{version}\"\n"


def _update_bib(content: str, version: str) -> str:
    if re.search(r"^\s*version\s*=\s*\{[^\}]+\}\s*,?\s*$", content, re.MULTILINE):
        return re.sub(
            r"^\s*version\s*=\s*\{[^\}]+\}\s*,?\s*$",
            f"  version = {{{version}}},",
            content,
            flags=re.MULTILINE,
        )

    insert_at = content.rfind("}")
    if insert_at == -1:
        raise ValueError("Invalid BibTeX content: missing closing brace")

    before = content[:insert_at].rstrip()
    after = content[insert_at:]
    return f"{before}\n  version = {{{version}}},\n{after}"


def _sync_citations(check_only: bool) -> bool:
    init_text = _read_text(INIT_FILE)
    raw_version = _extract_version_raw(init_text)
    pep440 = _pep440_from_raw(raw_version)

    cff_text = _read_text(CFF_FILE)
    bib_text = _read_text(BIB_FILE)

    cff_updated = _update_cff(cff_text, pep440)
    bib_updated = _update_bib(bib_text, pep440)

    if check_only:
        return cff_updated == cff_text and bib_updated == bib_text

    if cff_updated != cff_text:
        _write_text(CFF_FILE, cff_updated)
    if bib_updated != bib_text:
        _write_text(BIB_FILE, bib_updated)

    return True


def main() -> int:
    parser = argparse.ArgumentParser(description="Sync citation versions from cereja.__version__.")
    parser.add_argument("--check", action="store_true", help="Exit non-zero if files need updates.")
    args = parser.parse_args()

    ok = _sync_citations(check_only=args.check)
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())

