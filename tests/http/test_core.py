import unittest

from cereja.http import Headers, Request, Response, Timeout, URL
from cereja.http._core.prepare import prepare_request
from cereja.http.errors import HTTPStatusError


class URLTest(unittest.TestCase):
    def test_absolute_url_with_ipv6_port_and_query(self):
        url = URL.parse("https://[::1]:8443/a%20b?x=1")
        self.assertEqual(url.scheme, "https")
        self.assertEqual(url.host, "::1")
        self.assertEqual(url.port, 8443)
        self.assertEqual(url.target, "/a%20b?x=1")

    def test_relative_url_requires_base(self):
        with self.assertRaises(ValueError):
            URL.parse("/users")
        url = URL.parse("/users", base_url="https://example.com/api/")
        self.assertEqual(str(url), "https://example.com/users")

    def test_query_params_preserve_existing_query(self):
        url = URL.parse("https://example.com/path?a=1").with_params({"b": [2, 3]})
        self.assertIn("a=1", url.query)
        self.assertIn("b=2", url.query)
        self.assertIn("b=3", url.query)


class HeadersTest(unittest.TestCase):
    def test_case_insensitive_and_repeated(self):
        headers = Headers([("Set-Cookie", "a=1"), ("set-cookie", "b=2")])
        self.assertEqual(headers.get_list("SET-cookie"), ["a=1", "b=2"])
        self.assertEqual(headers["set-cookie"], "a=1, b=2")

    def test_rejects_crlf(self):
        with self.assertRaises(ValueError):
            Headers({"X-Test": "ok\r\nInjected: yes"})


class PrepareRequestTest(unittest.TestCase):
    def test_raw_bytes_are_not_reencoded(self):
        request = prepare_request("POST", "https://example.com", content=b"\x00\xff")
        self.assertEqual(request.content, b"\x00\xff")

    def test_falsy_json_values_are_preserved(self):
        for value, expected in ((None, b"null"), (False, b"false"), (0, b"0"), ({}, b"{}")):
            with self.subTest(value=value):
                request = prepare_request("POST", "https://example.com", json=value)
                self.assertEqual(request.content, expected)
                self.assertEqual(request.headers["content-type"], "application/json")

    def test_body_forms_are_mutually_exclusive(self):
        with self.assertRaises(ValueError):
            prepare_request("POST", "https://example.com", json={}, content=b"x")


class ResponseTest(unittest.TestCase):
    def test_response_decoding_and_status_error(self):
        request = Request("GET", URL.parse("https://example.com"), Headers(), None)
        response = Response.from_parts(
            request=request,
            status_code=404,
            reason="Not Found",
            headers=Headers({"Content-Type": "application/json; charset=utf-8"}),
            content=b'{"ok": false}',
            http_version="HTTP/1.1",
        )
        self.assertEqual(response.json(), {"ok": False})
        self.assertIn('"ok": false', response.text)
        with self.assertRaises(HTTPStatusError):
            response.raise_for_status()

    def test_timeout_scalar_expands(self):
        timeout = Timeout.from_value(2.5)
        self.assertEqual((timeout.connect, timeout.read, timeout.write, timeout.pool), (2.5, 2.5, 2.5, 2.5))


if __name__ == "__main__":
    unittest.main()
