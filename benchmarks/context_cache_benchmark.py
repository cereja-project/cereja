"""Reproducible API and CLI benchmarks for the text-context cache."""

import argparse
import json
import math
import os
import statistics
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path
from tempfile import TemporaryDirectory
from time import perf_counter_ns
from unittest.mock import patch

from cereja.system import search_text_context


QUERY = "needle"
MUTATIONS = ("unchanged", "create", "modify", "rename", "remove")


@dataclass(frozen=True, slots=True)
class BenchmarkCase:
    """One reproducible corpus size and filesystem-mutation scenario."""

    files: int
    mutation: str


def _build_corpus(root: Path, files: int) -> None:
    for index in range(files):
        (root / f"file_{index:05d}.py").write_text(
            "# deterministic context benchmark\n"
            f"VALUE_{index:05d} = 'needle {index:05d}'\n",
            encoding="utf-8",
        )


def _apply_mutation(root: Path, mutation: str) -> None:
    if mutation == "unchanged":
        return
    if mutation == "create":
        (root / "created.py").write_text(
            "# deterministic context benchmark\n"
            "CREATED = 'needle created'\n",
            encoding="utf-8",
        )
        return
    if mutation == "modify":
        (root / "file_00000.py").write_text(
            "# deterministic context benchmark modified\n"
            "VALUE_00000 = 'needle modified'\n",
            encoding="utf-8",
        )
        return
    if mutation == "rename":
        (root / "file_00000.py").rename(root / "renamed_00000.py")
        return
    if mutation == "remove":
        sorted(root.glob("file_*.py"))[-1].unlink()
        return
    raise ValueError(f"unsupported mutation: {mutation}")


def _time_call(operation) -> int:
    started = perf_counter_ns()
    operation()
    return perf_counter_ns() - started


def _nearest_rank_p95(samples: list[int]) -> int:
    ordered = sorted(samples)
    return ordered[math.ceil(len(ordered) * 0.95) - 1]


def _milliseconds(samples: list[int]) -> tuple[float, float]:
    return (
        statistics.median(samples) / 1_000_000,
        _nearest_rank_p95(samples) / 1_000_000,
    )


def _api_search(root: Path, cache: bool) -> None:
    search_text_context(
        [root], QUERY, extensions=[".py"], max_results=10, cache=cache
    )


def _cli_search(root: Path, cache: bool, environment: dict[str, str]) -> None:
    command = [
        sys.executable,
        "-m",
        "cereja",
        "context",
        "search",
        "--root",
        str(root),
        "--query",
        QUERY,
        "--extension",
        ".py",
        "--format",
        "json",
    ]
    if cache:
        command.append("--cache")
    subprocess.run(
        command,
        check=True,
        capture_output=True,
        text=True,
        cwd=Path(__file__).resolve().parents[1],
        env=environment,
    )


def _result_prefix(name: str, direct: list[int], cached: list[int]) -> dict[str, float]:
    direct_median, direct_p95 = _milliseconds(direct)
    cached_median, cached_p95 = _milliseconds(cached)
    return {
        f"{name}_direct_median_ms": direct_median,
        f"{name}_direct_p95_ms": direct_p95,
        f"{name}_cached_median_ms": cached_median,
        f"{name}_cached_p95_ms": cached_p95,
        f"{name}_cached_direct_ratio": cached_median / direct_median,
    }


def run_case(case: BenchmarkCase, iterations: int = 15) -> dict:
    """Run one cache benchmark case in isolated API and CLI environments."""
    if case.files < 1:
        raise ValueError("files must be at least one")
    if case.mutation not in MUTATIONS:
        raise ValueError(f"unsupported mutation: {case.mutation}")
    if iterations < 1:
        raise ValueError("iterations must be at least one")

    with TemporaryDirectory() as temporary_directory:
        temporary_root = Path(temporary_directory)
        corpus_root = temporary_root / "corpus"
        corpus_root.mkdir()
        _build_corpus(corpus_root, case.files)
        api_cache_path = temporary_root / "api-cache" / "context.sqlite3"
        local_app_data = temporary_root / "cli-local-app-data"
        local_app_data.mkdir()
        cli_environment = os.environ.copy()
        cli_environment["LOCALAPPDATA"] = str(local_app_data)

        with patch(
                "cereja.system._context.cache.default_cache_path",
                return_value=api_cache_path,
        ):
            _api_search(corpus_root, cache=True)
            _cli_search(corpus_root, cache=True, environment=cli_environment)
            _apply_mutation(corpus_root, case.mutation)

            api_direct = [
                _time_call(lambda: _api_search(corpus_root, cache=False))
                for _ in range(iterations)
            ]
            api_cached = [
                _time_call(lambda: _api_search(corpus_root, cache=True))
                for _ in range(iterations)
            ]
            cli_direct = [
                _time_call(
                    lambda: _cli_search(
                        corpus_root, cache=False, environment=cli_environment
                    )
                )
                for _ in range(iterations)
            ]
            cli_cached = [
                _time_call(
                    lambda: _cli_search(
                        corpus_root, cache=True, environment=cli_environment
                    )
                )
                for _ in range(iterations)
            ]

    result = {"files": case.files, "mutation": case.mutation}
    result.update(_result_prefix("api", api_direct, api_cached))
    result.update(_result_prefix("cli", cli_direct, cli_cached))
    return result


def _parse_arguments() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--files", type=int, action="append", required=True)
    parser.add_argument("--mutation", choices=MUTATIONS, default="unchanged")
    parser.add_argument("--iterations", type=int, default=15)
    return parser.parse_args()


def main() -> int:
    arguments = _parse_arguments()
    results = [
        run_case(BenchmarkCase(files, arguments.mutation), arguments.iterations)
        for files in arguments.files
    ]
    print(json.dumps(results, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
