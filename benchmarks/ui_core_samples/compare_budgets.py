"""Compare a frozen baseline with its unchanged-code control, not a candidate."""
import hashlib
import json
from pathlib import Path
import sys

root = Path(sys.argv[1])
budgets = json.loads((root / "budgets.json").read_text())
loaded = {}
def read(name):
    if name not in loaded:
        path = root / name
        if path.suffix == ".jsonl":
            rows = [json.loads(line) for line in path.read_text().splitlines()]
            loaded[name] = (rows[0], rows[1:])
        else:
            loaded[name] = (json.loads(path.read_text()), None)
    return loaded[name]

environment_checks = []
for name, expected in budgets["baseline_sha256"].items():
    assert hashlib.sha256((root / name).read_bytes()).hexdigest() == expected, name
    baseline, _ = read(name)
    control, _ = read(name.replace("-baseline", "-control"))
    keys = ("python","implementation","platform","machine","processor","pointer_bits",
            "gc_enabled","head","head_tree","source_sha256")
    assert all(baseline["environment"][key] == control["environment"][key] for key in keys), name
    assert baseline["conditions"] == control["conditions"], name
    environment_checks.append(name)

comparisons = []
for entry in budgets["entries"]:
    control, imports = read(entry["file"].replace("-baseline", "-control"))
    section = entry["section"]
    identity = entry["identity"]
    if imports is not None:
        row = next(row for row in imports if row["case"] == identity["case"])
        stats = row[section]
    elif "/" in section:
        collection, statistic = section.split("/")
        row = next(row for row in control[collection] if all(row[k] == v for k,v in identity.items()))
        stats = row[statistic][entry["metric"]]
    else:
        stats = control[section][entry["metric"]]
    comparisons.append({"file":entry["file"],"identity":identity,"section":section,
                        "metric":entry["metric"],"scope":entry["scope"],
                        "limit":entry["investigation_limit"],"control":stats,
                        "baseline":entry["baseline"],
                        "exceeded":stats["p95"] > entry["investigation_limit"]})
hard = {}
for suffix in ("baseline","control"):
    renderer, _ = read("rendering-" + suffix + ".json")
    hard[suffix + "_unchanged_zero"] = all(
        all(sample["utf8_bytes"] == sample["writes"] == sample["flushes"] == 0 for sample in row["raw"])
        for row in renderer["results"] if row["workload"] == "unchanged")
    _, imports = read("imports-" + suffix + ".jsonl")
    hard[suffix + "_imports_quiet_without_threads"] = all(
        not sample["stdout"] and not sample["stderr"] and not sample["threads_started"]
        and sample["cereja_modules"] == row["cereja_modules"] for row in imports for sample in row["raw"])
    for transport in ("scheduling","native-input"):
        scheduler, _ = read(transport + "-" + suffix + ".json")
        hard[suffix + "_" + transport + "_idle_and_fairness"] = all(
            sample["idle"]["blocking_waits"] == 1
            and sample["idle"]["renders"] == sample["idle"]["writes"] == sample["idle"]["flushes"] == 0
            and sample["key_inspection_turn"] <= sample["key_injection_turn"] + 1
            and sample["workload"] == 10000 for sample in scheduler["samples"])
baseline, old_imports = read("imports-baseline.jsonl")
control, new_imports = read("imports-control.jsonl")
old_root = next(row for row in old_imports if row["case"] == "root")
new_root = next(row for row in new_imports if row["case"] == "root")
hard["root_import_module_set_unchanged"] = old_root["cereja_modules"] == new_root["cereja_modules"]
hard["root_import_median_guard"] = new_root["summary_ns"]["median"] <= budgets["root_import_median_limit_ns"]
assert all(hard.values()), hard
report = {"environment_and_condition_checks":environment_checks, "hard_checks":hard,
          "candidate":"None; unchanged-code control only", "comparisons":comparisons,
          "breaches":[row for row in comparisons if row["exceeded"]]}
(root / "budget-control.json").write_text(json.dumps(report, indent=2)+"\n", encoding="utf-8")
counts = {}
for row in report["breaches"]:
    counts[row["scope"]] = counts.get(row["scope"],0) + 1
print("Compared",len(comparisons),"thresholds; breaches",counts,"hard gates passed",len(hard))
