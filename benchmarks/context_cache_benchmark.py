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
        (root / "file_00000.py").rename(root / "changed_00000.py")
        return
    if mutation == "remove":
        (root / "file_00000.py").unlink()
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


def _api_search(root: Path, cache: bool):
    return search_text_context(
        [root], QUERY, extensions=[".py"], max_results=10, cache=cache
    )


def _cli_search(root: Path, cache: bool, environment: dict[str, str]) -> dict:
    cli_entrypoint = (
        "import contextlib, io\n"
        "with contextlib.redirect_stdout(io.StringIO()):\n"
        "    from cereja.cli import main\n"
        "raise SystemExit(main())\n"
    )
    command = [
        sys.executable,
        "-c",
        cli_entrypoint,
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
    result = subprocess.run(
        command,
        check=True,
        capture_output=True,
        text=True,
        cwd=Path(__file__).resolve().parents[1],
        env=environment,
    )
    return json.loads(result.stdout)


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


def _sample_corpus(root: Path, name: str, files: int) -> Path:
    corpus_root = root / name
    corpus_root.mkdir()
    _build_corpus(corpus_root, files)
    return corpus_root


def _cli_environment(root: Path, name: str) -> dict[str, str]:
    local_app_data = root / name
    local_app_data.mkdir()
    environment = os.environ.copy()
    environment["LOCALAPPDATA"] = str(local_app_data)
    return environment


def _response_entries(response) -> dict[str, tuple[str, ...]]:
    if isinstance(response, dict):
        return {
            result["relative_path"]: tuple(
                snippet["text"] for snippet in result["snippets"]
            )
            for result in response["results"]
        }
    return {
        result.relative_path: tuple(snippet.text for snippet in result.snippets)
        for result in response.results
    }


def _validate_cached_mutation(response, mutation: str) -> None:
    entries = _response_entries(response)
    if mutation == "unchanged" and "file_00000.py" in entries:
        return
    if mutation == "create" and "created.py" in entries:
        return
    if mutation == "modify" and any(
            "needle modified" in text for text in entries.get("file_00000.py", ())
    ):
        return
    if mutation == "rename" and (
            "changed_00000.py" in entries and "file_00000.py" not in entries
    ):
        return
    if mutation == "remove" and "file_00000.py" not in entries:
        return
    raise AssertionError(f"cached response did not reflect {mutation} mutation")


def _api_direct_sample(root: Path, case: BenchmarkCase, index: int) -> int:
    corpus_root = _sample_corpus(root, f"api-direct-{index}", case.files)
    _apply_mutation(corpus_root, case.mutation)
    return _time_call(lambda: _api_search(corpus_root, cache=False))


def _api_cached_sample(root: Path, case: BenchmarkCase, index: int) -> int:
    corpus_root = _sample_corpus(root, f"api-cached-{index}", case.files)
    cache_path = root / f"api-cache-{index}.sqlite3"
    with patch(
            "cereja.system._context.cache.default_cache_path",
            return_value=cache_path,
    ):
        _api_search(corpus_root, cache=True)
        _apply_mutation(corpus_root, case.mutation)
        response = None

        def search():
            nonlocal response
            response = _api_search(corpus_root, cache=True)

        elapsed = _time_call(search)
    _validate_cached_mutation(response, case.mutation)
    return elapsed


def _cli_direct_sample(root: Path, case: BenchmarkCase, index: int) -> int:
    corpus_root = _sample_corpus(root, f"cli-direct-{index}", case.files)
    environment = _cli_environment(root, f"cli-direct-cache-{index}")
    _apply_mutation(corpus_root, case.mutation)
    return _time_call(
        lambda: _cli_search(corpus_root, cache=False, environment=environment)
    )


def _cli_cached_sample(root: Path, case: BenchmarkCase, index: int) -> int:
    corpus_root = _sample_corpus(root, f"cli-cached-{index}", case.files)
    environment = _cli_environment(root, f"cli-cached-cache-{index}")
    _cli_search(corpus_root, cache=True, environment=environment)
    _apply_mutation(corpus_root, case.mutation)
    response = None

    def search():
        nonlocal response
        response = _cli_search(corpus_root, cache=True, environment=environment)

    elapsed = _time_call(search)
    _validate_cached_mutation(response, case.mutation)
    return elapsed


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
        api_direct = [
            _api_direct_sample(temporary_root, case, index)
            for index in range(iterations)
        ]
        api_cached = [
            _api_cached_sample(temporary_root, case, index)
            for index in range(iterations)
        ]
        cli_direct = [
            _cli_direct_sample(temporary_root, case, index)
            for index in range(iterations)
        ]
        cli_cached = [
            _cli_cached_sample(temporary_root, case, index)
            for index in range(iterations)
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
