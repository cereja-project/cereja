"""Benchmark direct, cold, warm, and refreshed context searches."""

import argparse
import json
import sys
import tempfile
import time
from pathlib import Path
from unittest.mock import patch


REPOSITORY_ROOT = Path(__file__).resolve().parents[1]
if str(REPOSITORY_ROOT) not in sys.path:
    sys.path.insert(0, str(REPOSITORY_ROOT))

from cereja.system import search_text_context  # noqa: E402


def build_fixture(root, *, files=2_000, lines=200):
    """Create a repeatable collection of UTF-8 text files."""
    for index in range(files):
        text = "\n".join(
            f"line {line} auth cache payload {index}" if line % 50 == 0
            else f"line {line} payload {index}"
            for line in range(lines)
        )
        (root / f"file-{index:05}.txt").write_text(text, encoding="utf-8")


def _positive_int(value):
    parsed = int(value)
    if parsed <= 0:
        raise argparse.ArgumentTypeError("must be greater than zero")
    return parsed


def _timed_search(root, *, files, cache, refresh_cache=False):
    started = time.perf_counter()
    response = search_text_context(
        [root],
        "auth cache",
        max_results=files,
        cache=cache,
        refresh_cache=refresh_cache,
    )
    return response, time.perf_counter() - started


def run_benchmark(*, files, lines):
    """Run the benchmark in isolated fixture and cache directories."""
    with tempfile.TemporaryDirectory(prefix="cereja-context-benchmark-") as temp:
        temp_root = Path(temp)
        fixture_root = temp_root / "fixture"
        fixture_root.mkdir()
        build_fixture(fixture_root, files=files, lines=lines)
        cache_path = temp_root / "cache" / "context.sqlite3"

        with patch(
            "cereja.system._context.cache.default_cache_path",
            return_value=cache_path,
        ):
            direct, direct_seconds = _timed_search(
                fixture_root, files=files, cache=False
            )
            cold, cold_seconds = _timed_search(
                fixture_root, files=files, cache=True
            )
            warm, warm_seconds = _timed_search(
                fixture_root, files=files, cache=True
            )
            refreshed, refresh_seconds = _timed_search(
                fixture_root, files=files, cache=True, refresh_cache=True
            )

        responses = {
            "direct": direct,
            "cold_cache": cold,
            "warm_cache": warm,
            "refresh_cache": refreshed,
        }
        equalities = {
            "cold_equals_direct": cold == direct,
            "warm_equals_direct": warm == direct,
            "refresh_equals_direct": refreshed == direct,
        }
        equalities["all_equal"] = all(equalities.values())
        return {
            "fixture": {
                "files": files,
                "lines_per_file": lines,
                "bytes": sum(path.stat().st_size for path in fixture_root.iterdir()),
            },
            "durations_seconds": {
                "direct": direct_seconds,
                "cold_cache": cold_seconds,
                "warm_cache": warm_seconds,
                "refresh_cache": refresh_seconds,
            },
            "result_counts": {
                name: len(response.results) for name, response in responses.items()
            },
            "equalities": equalities,
        }


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--files", type=_positive_int, default=2_000)
    parser.add_argument("--lines", type=_positive_int, default=200)
    args = parser.parse_args(argv)
    payload = run_benchmark(files=args.files, lines=args.lines)
    print(json.dumps(payload, indent=2, sort_keys=True))
    return 0 if payload["equalities"]["all_equal"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
