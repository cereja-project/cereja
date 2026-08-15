"""Tests for the reproducible context-cache benchmark."""

from pathlib import Path
from tempfile import TemporaryDirectory
from unittest import TestCase
from unittest.mock import patch

from benchmarks.context_cache_benchmark import (
    BenchmarkCase,
    _apply_mutation,
    _build_corpus,
    run_case,
)


class ContextCacheBenchmarkTests(TestCase):
    def test_build_corpus_uses_deterministic_utf8_python_files(self):
        """Changing the corpus layout would make benchmark runs incomparable."""
        with TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)

            _build_corpus(root, 3)

            self.assertEqual(
                [path.name for path in sorted(root.glob("*.py"))],
                ["file_00000.py", "file_00001.py", "file_00002.py"],
            )
            self.assertEqual(
                (root / "file_00000.py").read_text(encoding="utf-8"),
                "# deterministic context benchmark\n"
                "VALUE_00000 = 'needle 00000'\n",
            )

    def test_run_case_returns_stable_schema_for_each_mutation(self):
        """Removing a timing result must fail rather than silently changing JSON."""
        expected_keys = {
            "files",
            "mutation",
            "api_direct_median_ms",
            "api_direct_p95_ms",
            "api_cached_median_ms",
            "api_cached_p95_ms",
            "api_cached_direct_ratio",
            "cli_direct_median_ms",
            "cli_direct_p95_ms",
            "cli_cached_median_ms",
            "cli_cached_p95_ms",
            "cli_cached_direct_ratio",
        }

        for mutation in ("unchanged", "create", "modify", "rename", "remove"):
            with self.subTest(mutation=mutation), patch(
                    "benchmarks.context_cache_benchmark._time_call",
                    side_effect=lambda operation: (operation(), 1_000_000)[1],
            ):
                result = run_case(BenchmarkCase(files=3, mutation=mutation), iterations=1)

            self.assertEqual(set(result), expected_keys)
            self.assertEqual(result["files"], 3)
            self.assertEqual(result["mutation"], mutation)

    def test_apply_mutation_changes_the_expected_corpus_entry(self):
        """Wrong mutation behavior would hide cache invalidation regressions."""
        expectations = {
            "unchanged": (3, True, True),
            "create": (4, True, True),
            "modify": (3, True, True),
            "rename": (3, False, True),
            "remove": (2, True, False),
        }
        for mutation, (count, first_exists, last_exists) in expectations.items():
            with self.subTest(mutation=mutation), TemporaryDirectory() as temp_dir:
                root = Path(temp_dir)
                _build_corpus(root, 3)

                _apply_mutation(root, mutation)

                self.assertEqual(len(list(root.glob("*.py"))), count)
                self.assertEqual((root / "file_00000.py").exists(), first_exists)
                self.assertEqual((root / "file_00002.py").exists(), last_exists)
