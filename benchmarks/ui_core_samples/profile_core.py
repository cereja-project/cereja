"""Bounded diagnostic profiles; profiler times are never benchmark samples."""
import argparse
import cProfile
import io
import json
from pathlib import Path
import pstats
import sys

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "benchmarks"))
import ui_rendering as bench
from _ui_bench import environment

parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument("--long-input", action="store_true")
parser.add_argument("--output", required=True)
args = parser.parse_args()
bench.LONG_INPUT = args.long_input
base = bench.CellBuffer(240,80)
bench.fill(base,"unicode_styles")
sink = bench.MemorySink(size=base.size, options=bench.CapabilityOptions(color=24))
sink.reset_counters()
with bench.TerminalSession(sink) as session:
    operations = {
        "paint_full":lambda: bench.draw_workload(base,"all_drawable_cells","unicode_styles"),
        "prepare_unchanged":lambda: bench.rendering._prepare_frame(base,session.capabilities),
    }
    profiles = {}
    for name, operation in operations.items():
        operation()
        profiler = cProfile.Profile()
        for _ in range(3):
            profiler.runcall(operation)
        output = io.StringIO()
        pstats.Stats(profiler,stream=output).strip_dirs().sort_stats("cumulative").print_stats(20)
        profiles[name] = output.getvalue()
report = {"environment":environment(),
          "conditions":{"dimensions":[240,80],"profile":"unicode_styles","long_input":args.long_input,
                        "warmup":1,"profiled_calls":3,
                        "limits":"Diagnostic cumulative call attribution; cProfile overhead included, "
                                 "not latency/throughput samples or a candidate comparison."},
          "profiles":profiles}
Path(args.output).write_text(json.dumps(report,indent=2)+"\n",encoding="utf-8")
