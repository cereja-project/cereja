import unittest

from cereja.http import Headers, Request, Response, Timeout, URL
from cereja.http._core.prepare import prepare_request
from cereja.http.errors import HTTPStatusError


class CoreContractsTest(unittest.TestCase):
    def test_url_headers_body_and_response_contracts(self):
        url = URL.parse("https://[::1]:8443/a%20b?x=1")
        self.assertEqual((url.host, url.port, url.target), ("::1", 8443, "/a%20b?x=1"))
        with self.assertRaises(ValueError):
            Headers({"X-Test": "ok\r\nInjected: yes"})
        request = prepare_request("POST", "https://example.com", content=b"\x00\xff")
        self.assertEqual(request.content, b"\x00\xff")
        for value, expected in ((None, b"null"), (False, b"false"), (0, b"0"), ({}, b"{}")):
            self.assertEqual(prepare_request("POST", "https://example.com", json=value).content, expected)
        response = Response.from_parts(
            request=Request("GET", URL.parse("https://example.com"), Headers(), None),
            status_code=404, reason="Not Found",
            headers=Headers({"Content-Type": "application/json; charset=utf-8"}),
            content=b'{"ok": false}', http_version="HTTP/1.1",
        )
        self.assertEqual(response.json(), {"ok": False})
        with self.assertRaises(HTTPStatusError):
            response.raise_for_status()
        self.assertEqual(Timeout.from_value(2.5).read, 2.5)


if __name__ == "__main__":
    unittest.main()
