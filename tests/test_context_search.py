import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from cereja.system import (
    context_response_to_dict,
    list_text_context,
    search_text_context,
)


class ContextSearchTest(unittest.TestCase):
    def test_requires_all_terms_and_limits_snippets(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            (root / "auth-guide.md").write_text(
                "Auth cache\nother\nCACHE auth again\n", encoding="utf-8"
            )
            (root / "auth-only.md").write_text(
                "auth without second term", encoding="utf-8"
            )

            response = search_text_context(
                [root],
                "AUTH cache",
                max_results=10,
                max_snippets=1,
                max_snippet_chars=40,
            )

            self.assertEqual(
                [item.relative_path for item in response.results],
                ["auth-guide.md"],
            )
            self.assertEqual(response.results[0].match_count, 4)
            self.assertEqual(len(response.results[0].snippets), 1)
            self.assertEqual(response.results[0].snippets[0].line, 1)
            self.assertTrue(response.truncated)

    def test_scores_filename_hits_then_occurrences_and_path(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            (root / "z-auth.md").write_text("auth cache", encoding="utf-8")
            (root / "a-auth.md").write_text("auth cache", encoding="utf-8")
            (root / "many.md").write_text("auth auth cache cache cache", encoding="utf-8")

            response = search_text_context([root], "auth cache")

            self.assertEqual(
                [item.relative_path for item in response.results],
                ["a-auth.md", "z-auth.md", "many.md"],
            )
            self.assertEqual([item.score for item in response.results], [1002, 1002, 5])

    def test_limits_results_and_snippet_characters(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            for name in ("a.txt", "b.txt"):
                (root / name).write_text("needle " + "x" * 80, encoding="utf-8")

            response = search_text_context(
                [root], "needle", max_results=1, max_snippet_chars=12
            )

            self.assertEqual(len(response.results), 1)
            self.assertLessEqual(len(response.results[0].snippets[0].text), 12)
            self.assertTrue(response.truncated)

    def test_reports_large_binary_and_invalid_utf8_files(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            (root / "large.txt").write_bytes(b"needle-too-large")
            (root / "binary.txt").write_bytes(b"needle\x00binary")
            (root / "invalid.txt").write_bytes(b"needle\xff")

            response = search_text_context([root], "needle", max_file_bytes=13)

            reasons = {Path(item.path).name: item.reason for item in response.skipped}
            self.assertEqual(
                reasons,
                {
                    "binary.txt": "binary_file",
                    "invalid.txt": "invalid_utf8",
                    "large.txt": "file_too_large",
                },
            )

    def test_list_returns_only_text_metadata_and_serializes_schema_v1(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            (root / "guide.md").write_text("guide", encoding="utf-8-sig")
            (root / "data.bin").write_bytes(b"binary\x00data")

            response = list_text_context([root], extensions=["md"])
            payload = context_response_to_dict(response)

            self.assertIsNone(response.query)
            self.assertEqual(response.results[0].score, 0)
            self.assertEqual(response.results[0].match_count, 0)
            self.assertEqual(response.results[0].snippets, ())
            self.assertEqual(list(payload), [
                "schema_version", "mode", "query", "roots", "results", "skipped", "truncated"
            ])
            self.assertEqual(payload["schema_version"], 1)
            self.assertEqual(payload["mode"], "list")
            self.assertEqual(payload["results"][0]["relative_path"], "guide.md")

    def test_rejects_empty_query_and_non_positive_limits(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            for query in ("", "   "):
                with self.assertRaises(ValueError):
                    search_text_context([root], query)
            for keyword in (
                "max_results", "max_snippets", "max_snippet_chars", "max_file_bytes"
            ):
                with self.subTest(keyword=keyword):
                    with self.assertRaises(ValueError):
                        search_text_context([root], "query", **{keyword: 0})

    def test_reports_file_that_disappears_during_read(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            path = root / "vanished.txt"
            path.write_text("needle", encoding="utf-8")

            with patch("cereja.system._context_search.open", side_effect=FileNotFoundError):
                response = search_text_context([root], "needle")

            self.assertEqual(response.results, ())
            self.assertEqual(response.skipped[0].reason, "disappeared")

    def test_reports_file_permission_denied_during_read(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            path = root / "private.txt"
            path.write_text("needle", encoding="utf-8")

            with patch("cereja.system._context_search.open", side_effect=PermissionError):
                response = search_text_context([root], "needle")

            self.assertEqual(response.results, ())
            self.assertEqual(response.skipped[0].reason, "permission_denied")


if __name__ == "__main__":
    unittest.main()
