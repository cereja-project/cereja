import unittest

from cereja.system._context.models import ContextResult, ContextSnippet, SkippedFile
from cereja.system._context.query import build_search_result, finalize_response


class ContextQueryTest(unittest.TestCase):
    def test_build_search_result_preserves_and_semantics_and_score(self):
        result, snippets_truncated = build_search_result(
            path="C:/repo/a-auth.md",
            root="C:/repo",
            relative_path="a-auth.md",
            size_bytes=27,
            text="Auth cache\nCACHE auth again\n",
            terms=("auth", "cache"),
            max_snippets=1,
            max_snippet_chars=40,
        )
        self.assertIsNotNone(result)
        self.assertEqual(result.score, 1004)
        self.assertEqual(result.match_count, 4)
        self.assertEqual(result.snippets, (ContextSnippet(1, "Auth cache"),))
        self.assertTrue(snippets_truncated)

    def test_build_search_result_rejects_missing_and_term(self):
        result, truncated = build_search_result(
            path="C:/repo/auth.md",
            root="C:/repo",
            relative_path="auth.md",
            size_bytes=4,
            text="auth",
            terms=("auth", "cache"),
            max_snippets=2,
            max_snippet_chars=40,
        )
        self.assertIsNone(result)
        self.assertFalse(truncated)

    def test_finalize_response_sorts_and_bounds_results_and_skipped(self):
        results = [
            ContextResult("C:/z", "C:/", "z", 1, 2, 2, ()),
            ContextResult("C:/a", "C:/", "a", 1, 2, 2, ()),
        ]
        response = finalize_response(
            mode="search",
            query="x",
            roots=("C:/",),
            results=results,
            skipped=[SkippedFile("C:/z.bin", "binary_file"),
                     SkippedFile("C:/a.bin", "binary_file")],
            max_results=1,
            snippets_truncated=False,
        )
        self.assertEqual(response.results[0].relative_path, "a")
        self.assertEqual(response.skipped[0].path, "C:/a.bin")
        self.assertTrue(response.truncated)
