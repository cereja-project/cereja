import io
import json
import unittest
from contextlib import redirect_stderr, redirect_stdout

from cereja.entrypoint import main
from http3._server import running_server


class HttpCliTest(unittest.TestCase):
    def run_cli(self, *args):
        stdout = io.StringIO()
        stderr = io.StringIO()
        with redirect_stdout(stdout), redirect_stderr(stderr):
            code = main(["http", *args])
        return code, stdout.getvalue(), stderr.getvalue()

    def test_get_prints_body_only_by_default(self):
        with running_server() as (base, _):
            code, stdout, stderr = self.run_cli(base + "/fixed")
        self.assertEqual(code, 0)
        self.assertEqual(stdout, "hello")
        self.assertEqual(stderr, "")

    def test_json_body_is_translated_to_http_client(self):
        with running_server() as (base, _):
            code, stdout, stderr = self.run_cli(
                "POST", base + "/fixed",
                "--json", '{"name":"Joab","active":true}',
            )
        self.assertEqual(code, 0)
        payload = json.loads(stdout)
        self.assertEqual(payload["body"], '{"name":"Joab","active":true}')
        self.assertEqual(payload["content_type"], "application/json")
        self.assertEqual(stderr, "")

    def test_method_data_and_query_flags_reach_http_client(self):
        with running_server() as (base, _):
            code, stdout, stderr = self.run_cli(
                "-X", "POST", base + "/fixed",
                "-d", "hello-cli",
            )
            self.assertEqual(code, 0)
            self.assertEqual(json.loads(stdout)["body"], "hello-cli")

            code, stdout, stderr = self.run_cli(
                "-v", base + "/fixed", "-q", "page=1", "-q", "name=Joab",
            )
        self.assertEqual(code, 0)
        self.assertEqual(stdout, "hello")
        self.assertIn("/fixed?page=1&name=Joab", stderr)

    def test_follow_and_pretty_flags(self):
        with running_server() as (base, _):
            code, stdout, stderr = self.run_cli("-L", base + "/redirect")
            self.assertEqual((code, stdout, stderr), (0, "hello", ""))

            code, stdout, stderr = self.run_cli("--pretty", base + "/json")
        self.assertEqual(code, 0)
        self.assertEqual(json.loads(stdout), {"ok": True})
        self.assertIn('\n  "ok": true\n', stdout)
        self.assertEqual(stderr, "")

    def test_include_prints_response_head_before_body(self):
        with running_server() as (base, _):
            code, stdout, _ = self.run_cli("-i", base + "/fixed")
        self.assertEqual(code, 0)
        self.assertIn("HTTP/1.1 200", stdout)
        self.assertIn("Content-Length: 5", stdout)
        self.assertTrue(stdout.endswith("\n\nhello"))

    def test_head_prints_headers_without_body(self):
        with running_server() as (base, _):
            code, stdout, _ = self.run_cli("-I", base + "/fixed")
        self.assertEqual(code, 0)
        self.assertIn("HTTP/1.1 200", stdout)
        self.assertNotIn("hello", stdout)

    def test_output_writes_body_to_file_without_printing_it(self):
        import tempfile
        from pathlib import Path

        with tempfile.TemporaryDirectory() as directory, running_server() as (base, _):
            target = Path(directory) / "body.bin"
            code, stdout, stderr = self.run_cli(base + "/fixed", "-o", str(target))
            self.assertEqual(target.read_bytes(), b"hello")
        self.assertEqual(code, 0)
        self.assertEqual(stdout, "")
        self.assertEqual(stderr, "")

    def test_verbose_redacts_sensitive_request_headers(self):
        with running_server() as (base, _):
            code, stdout, stderr = self.run_cli(
                "-v", base + "/fixed",
                "-H", "Authorization: Bearer super-secret",
            )
        self.assertEqual(code, 0)
        self.assertEqual(stdout, "hello")
        self.assertIn("Authorization: <redacted>", stderr)
        self.assertNotIn("super-secret", stderr)

    def test_invalid_header_is_a_usage_error(self):
        code, _, stderr = self.run_cli("https://example.com", "-H", "invalid")
        self.assertEqual(code, 1)
        self.assertIn("Header must use 'Name: value'", stderr)


if __name__ == "__main__":
    unittest.main()
