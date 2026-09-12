import unittest

from cereja.http import Headers, Request, URL
from cereja.http._core.policies import RetryPolicy, build_redirect_request
from cereja.http.errors import ConnectError


class PolicyTest(unittest.TestCase):
    def test_redirect_and_retry_policies(self):
        request = Request("POST", URL.parse("https://a.example/start"), Headers({
            "Host": "a.example", "Authorization": "secret", "Content-Type": "text/plain", "Content-Length": "1"
        }), b"x")
        redirected = build_redirect_request(request, 303, "/next")
        self.assertEqual(redirected.method, "GET")
        self.assertIsNone(redirected.content)
        cross = build_redirect_request(Request("GET", request.url, request.headers, None), 307, "https://b.example/next")
        self.assertNotIn("authorization", cross.headers)
        policy = RetryPolicy(max_retries=2)
        get = Request("GET", URL.parse("https://example.com"), Headers(), None)
        post = Request("POST", get.url, Headers(), None)
        self.assertTrue(policy.should_retry(get, error=ConnectError("x"), attempt=0))
        self.assertFalse(policy.should_retry(post, error=ConnectError("x"), attempt=0))


if __name__ == "__main__":
    unittest.main()
