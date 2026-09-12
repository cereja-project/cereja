import unittest

from cereja.http import Headers, Request, Response, Timeout, URL
from cereja.http._core.framing import response_framing
from cereja.http._core.prepare import prepare_request
from cereja.http.errors import HTTPStatusError, ProtocolError


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

    def test_headers_reject_non_token_names_and_unsafe_values(self):
        for name in ("Bad Name", "Bad\tName", "Bäd", "Bad:Name", ""):
            with self.subTest(name=name), self.assertRaises(ValueError):
                Headers([(name, "ok")])
        for value in ("bad\x00value", "bad\x7fvalue", "bad\u0100value"):
            with self.subTest(value=value), self.assertRaises(ValueError):
                Headers([("X-Test", value)])
        headers = Headers([("X-Test", "value\twith-tab")])
        self.assertEqual(headers["x-test"], "value\twith-tab")

    def test_response_framing_rejects_ambiguous_or_unsupported_encodings(self):
        with self.assertRaises(ProtocolError):
            response_framing(
                "GET", 200,
                Headers([("Transfer-Encoding", "chunked"), ("Content-Length", "5")]),
                "HTTP/1.1",
            )
        for transfer in ("gzip", "gzip, chunked", "chunked, gzip", "chunked, chunked"):
            with self.subTest(transfer=transfer), self.assertRaises(ProtocolError):
                response_framing(
                    "GET", 200, Headers([("Transfer-Encoding", transfer)]), "HTTP/1.1"
                )
        with self.assertRaises(ProtocolError):
            response_framing(
                "GET", 200,
                Headers([("Content-Length", "5"), ("Content-Length", "5")]),
                "HTTP/1.1",
            )

        self.assertEqual(
            response_framing("GET", 200, Headers([("Transfer-Encoding", "chunked")]), "HTTP/1.1"),
            ("chunked", None, True),
        )
        self.assertEqual(
            response_framing("HEAD", 200, Headers([("Content-Length", "5")]), "HTTP/1.1"),
            ("none", 0, True),
        )


if __name__ == "__main__":
    unittest.main()
