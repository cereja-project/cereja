"""Measure imports in fresh processes; optionally inventory the public surface.

Run from a source checkout: python benchmarks/imports.py --samples 7
Use --inventory to deliberately resolve and capture the complete public API.
No timing threshold is imposed: compare equivalent interpreter/OS environments.
"""

import argparse
import json
import os
from pathlib import Path
import platform
import statistics
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]
CASES = {
    "root": "import cereja",
    "path": "from cereja.system import Path",
    "file": "from cereja.file import FileIO",
    "concurrently": "from cereja.concurrently import TaskList",
    "timer": "from cereja.utils import Timer",
}
PROBE = r'''
import contextlib
import io
import sys
import threading
import time
out, err = io.StringIO(), io.StringIO()
before_modules = set(sys.modules)
before_threads = {id(t) for t in threading.enumerate()}
with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
    start = time.perf_counter_ns()
    exec(sys.argv[1], {})
    elapsed = time.perf_counter_ns() - start
added = sorted(set(sys.modules) - before_modules)
report = {
    "elapsed_ns": elapsed,
    "modules_added": len(added),
    "cereja_modules": sorted(n for n in sys.modules if n == "cereja" or n.startswith("cereja.")),
    "stdout": out.getvalue(),
    "stderr": err.getvalue(),
    "threads_started": [t.name for t in threading.enumerate() if id(t) not in before_threads],
}
import json
print(json.dumps(report, sort_keys=True))
'''
INVENTORY = r'''
import ast
import contextlib
import io
import json
from pathlib import Path
import sys
import types
reports = []
with contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(io.StringIO()):
    import cereja
    # Inventory intentionally resolves the API in a separate process.
    for name in dir(cereja):
        if not name.startswith("_"):
            getattr(cereja, name)
    packages = sorted(
        (name, module) for name, module in tuple(sys.modules.items())
        if (name == "cereja" or name.startswith("cereja."))
        and isinstance(module, types.ModuleType) and hasattr(module, "__path__")
    )
    for name, module in packages:
        names = sorted(n for n in dir(module) if not n.startswith("_"))
        exports = {}
        for key in names:
            value = getattr(module, key)
            if isinstance(value, types.ModuleType):
                target = [value.__name__, None]
            else:
                owner = getattr(value, "__module__", None)
                attr = getattr(value, "__name__", None)
                origin = sys.modules.get(owner)
                target = [owner, attr] if origin is not None and attr and getattr(origin, attr, None) is value else None
            exports[key] = {"target": target, "type": type(value).__module__ + "." + type(value).__qualname__}
        filename = getattr(module, "__file__", None)
        initializer = None
        if filename and filename.endswith(".py"):
            tree = ast.parse(Path(filename).read_text(encoding="utf-8"))
            tree.body = [node for node in tree.body if not (
                isinstance(node, ast.Expr) and isinstance(node.value, ast.Constant)
                and isinstance(node.value.value, str)
            )]
            initializer = ast.unparse(tree)
        reports.append({"package": name, "exports": exports,
                        "star_exports": list(getattr(module, "__all__", names)),
                        "initializer": initializer})
for report in reports:
    print(json.dumps(report, sort_keys=True))
'''


def positive_samples(value):
    number = int(value)
    if not 1 <= number <= 100:
        raise argparse.ArgumentTypeError("samples must be between 1 and 100")
    return number


def execute(code, *args):
    result = subprocess.run(
        [sys.executable, "-c", code, *args], cwd=ROOT,
        env=dict(os.environ, PYTHONPATH=str(ROOT), PYTHONIOENCODING="utf-8"),
        capture_output=True, text=True, encoding="utf-8", timeout=60,
    )
    if result.returncode:
        raise RuntimeError(result.stdout + result.stderr)
    return result.stdout


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--samples", type=positive_samples, default=7)
    parser.add_argument("--case", choices=CASES, action="append", dest="cases")
    parser.add_argument("--inventory", action="store_true")
    args = parser.parse_args(argv)
    print(json.dumps({"python": platform.python_version(), "platform": sys.platform}))
    for case in args.cases or CASES:
        probes = [json.loads(execute(PROBE, CASES[case])) for _ in range(args.samples)]
        report = dict(probes[-1], case=case)
        report.pop("elapsed_ns")
        report["median_ms"] = statistics.median(p["elapsed_ns"] for p in probes) / 1_000_000
        report["samples_ms"] = [p["elapsed_ns"] / 1_000_000 for p in probes]
        print(json.dumps(report, sort_keys=True))
    if args.inventory:
        print(execute(INVENTORY), end="")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
