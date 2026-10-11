import hashlib, json, sys
from pathlib import Path
root = Path(sys.argv[1])
entries = []
sources = {}
def add(file, identity, section, values):
    for metric, stats in values.items():
        if metric.endswith("_ns"):
            limit = max(1.25*stats["p95"], stats["p95"]+3*stats["mad"], 50000)
            scope = "core-compute-or-memory-sink"
        elif metric in ("retained_bytes", "peak_bytes", "live_traced_blocks"):
            floor = 16 if metric == "live_traced_blocks" else 4096
            limit = max(1.10*stats["p95"], stats["p95"]+3*stats["mad"], floor)
            scope = "tracked-memory"
        elif metric.endswith("_seconds"):
            limit = max(1.25*stats["p95"], stats["p95"]+3*stats["mad"], .00005)
            scope = "native-observation"
        else:
            continue
        if metric.startswith("instrumented") or metric == "transaction_instrumented_ns":
            scope = "instrumentation-observation"
        if file.startswith("native-output"):
            scope = "native-observation"
        entries.append(dict(file=file, identity=identity, section=section, metric=metric,
                            baseline=stats, investigation_limit=limit, scope=scope))
for file in sorted(root.glob("*-baseline.json")):
    report = json.loads(file.read_text())
    sources[file.name] = hashlib.sha256(file.read_bytes()).hexdigest()
    for section in ("results", "text_results", "timer_results"):
        for row in report.get(section, []):
            identity = {k:row[k] for k in ("width","height","profile","workload","cache","timers") if k in row}
            add(file.name, identity, section + "/summary", row["summary"])
            if "memory_summary" in row:
                add(file.name, identity, section + "/memory_summary", row["memory_summary"])
    if "summary" in report:
        add(file.name, {}, "summary", report["summary"])
file = root / "imports-baseline.jsonl"
sources[file.name] = hashlib.sha256(file.read_bytes()).hexdigest()
imports = [json.loads(line) for line in file.read_text().splitlines()][1:]
for row in imports:
    for section in ("summary_ns", "warm_summary_ns"):
        add(file.name, {"case":row["case"]}, section, {"elapsed_ns":row[section]})
root_import = next(row for row in imports if row["case"] == "root")
m = root_import["summary_ns"]["median"]
report = {"status":"Frozen before unchanged-code control", "baseline_sha256":sources,
          "time_formula":"max(1.25*p95, p95+3*MAD, 50us)",
          "memory_formula":"max(1.10*p95, p95+3*MAD, 4096 bytes or 16 live blocks)",
          "root_import_median_limit_ns":m + max(2000000,.20*m),
          "root_import_modules":root_import["cereja_modules"],
          "limits":"Local regression investigation thresholds, never application latency or RSS guarantees.",
          "entries":entries}
(root / "budgets.json").write_text(json.dumps(report, indent=2)+"\n", encoding="utf-8")
print("Frozen",len(entries),"metric thresholds from",len(sources),"baseline files")
