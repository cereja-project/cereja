"""Owned-fixture traversal calibration; no checkout or private inventory."""
import json
from pathlib import Path
import statistics
import tempfile
import time
import tracemalloc

from cereja.system.repository import RepositoryTree


def measure(samples=11):
    with tempfile.TemporaryDirectory() as directory:
        root = Path(directory)
        for index in range(300):
            (root / ('file-' + str(index))).touch()
        rows = []
        for _ in range(samples):
            tracemalloc.start()
            start = time.perf_counter_ns()
            with RepositoryTree(root, max_directory_entries=128) as tree:
                page = tree.children(page_size=32)
                while page.next_offset is not None:
                    page = tree.children(offset=page.next_offset, page_size=32)
                elapsed = (time.perf_counter_ns() - start) / 1e6
                _, peak = tracemalloc.get_traced_memory()
                rows.append(dict(milliseconds=elapsed, traced_peak_bytes=peak,
                                 examined=tree.examined, complete=page.complete))
            tracemalloc.stop()
        ordered = sorted(row['milliseconds'] for row in rows)
        return dict(scenario='300 empty files; 128-entry cap; 32-node pages',
                    samples=rows, median_ms=statistics.median(ordered),
                    p95_ms=ordered[int(.95 * (len(ordered) - 1))],
                    limitations='OS cache/load uncontrolled; traced allocation is not RSS; no terminal timing')


if __name__ == '__main__':
    print(json.dumps(measure(), indent=2))
