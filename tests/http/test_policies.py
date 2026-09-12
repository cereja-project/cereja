import unittest

from cereja.http import Headers, Request, URL
from cereja.http._core.policies import RetryPolicy, build_redirect_request
from cereja.http.errors import ConnectError


class RedirectPolicyTest(unittest.TestCase):
    def request(self, method="POST"):
        return Request(
            method,
            URL.parse("https://a.example/start"),
            Headers({"Host": "a.example", "Authorization": "secret", "Content-Type": "text/plain", "Content-Length": "1"}),
            b"x",
        )

    def test_303_converts_to_get_and_drops_body(self):
        redirected = build_redirect_request(self.request(), 303, "/next")
        self.assertEqual(redirected.method, "GET")
        self.assertIsNone(redirected.content)
        self.assertNotIn("content-length", redirected.headers)
        self.assertNotIn("content-type", redirected.headers)

    def test_cross_origin_strips_authorization(self):
        redirected = build_redirect_request(self.request("GET"), 307, "https://b.example/next")
        self.assertNotIn("authorization", redirected.headers)
        self.assertEqual(redirected.headers["host"], "b.example")

    def test_307_preserves_method_and_body(self):
        redirected = build_redirect_request(self.request(), 307, "/next")
        self.assertEqual(redirected.method, "POST")
        self.assertEqual(redirected.content, b"x")


class RetryPolicyTest(unittest.TestCase):
    def test_disabled_by_default(self):
        policy = RetryPolicy()
        request = self._request("GET")
        self.assertFalse(policy.should_retry(request, error=ConnectError("x"), attempt=0))

    def test_idempotent_transport_failure_can_retry(self):
        policy = RetryPolicy(max_retries=2)
        self.assertTrue(policy.should_retry(self._request("GET"), error=ConnectError("x"), attempt=0))
        self.assertFalse(policy.should_retry(self._request("POST"), error=ConnectError("x"), attempt=0))
        self.assertFalse(policy.should_retry(self._request("GET"), error=ConnectError("x"), attempt=2))

    @staticmethod
    def _request(method):
        return Request(method, URL.parse("https://example.com"), Headers(), None)


if __name__ == "__main__":
    unittest.main()
