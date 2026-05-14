import unittest
from unittest.mock import patch, MagicMock
from cereja._requests._http import _Http, HttpRequest


class HttpParseUrlTest(unittest.TestCase):
    """Tests for _Http.parse_url static method."""

    def test_parse_full_url(self):
        protocol, port, domains, endpoint = _Http.parse_url("https://example.com/api/v1")
        self.assertEqual(protocol, "https")
        self.assertEqual(domains, "example.com")
        self.assertEqual(endpoint, "api/v1")
        self.assertEqual(port, "")

    def test_parse_url_with_port(self):
        protocol, port, domains, endpoint = _Http.parse_url("http://localhost:8080/path")
        self.assertEqual(protocol, "http")
        self.assertEqual(port, "8080")
        self.assertEqual(domains, "localhost")
        self.assertEqual(endpoint, "path")

    def test_parse_url_no_endpoint(self):
        protocol, port, domains, endpoint = _Http.parse_url("https://example.com")
        self.assertEqual(protocol, "https")
        self.assertEqual(domains, "example.com")
        self.assertEqual(endpoint, "")

    def test_parse_url_with_subdomain(self):
        protocol, port, domains, endpoint = _Http.parse_url("https://api.example.com/v2/users")
        self.assertEqual(protocol, "https")
        self.assertEqual(domains, "api.example.com")
        self.assertEqual(endpoint, "v2/users")

    def test_parse_url_no_protocol_defaults_https(self):
        protocol, port, domains, endpoint = _Http.parse_url("example.com/path")
        self.assertEqual(protocol, "https")
        self.assertEqual(domains, "example.com")

    def test_parse_url_with_external_port(self):
        protocol, port, domains, endpoint = _Http.parse_url("https://example.com/path", port=443)
        self.assertEqual(port, 443)


class HttpIsUrlTest(unittest.TestCase):
    """Tests for _Http.is_url static method."""

    def test_valid_https(self):
        self.assertTrue(_Http.is_url("https://example.com"))

    def test_valid_http(self):
        self.assertTrue(_Http.is_url("http://example.com"))

    def test_invalid_no_scheme(self):
        self.assertFalse(_Http.is_url("example.com"))

    def test_invalid_empty(self):
        self.assertFalse(_Http.is_url(""))

    def test_invalid_none(self):
        self.assertFalse(_Http.is_url(None))

    def test_invalid_number(self):
        self.assertFalse(_Http.is_url(123))


class HttpRequestTest(unittest.TestCase):
    """Tests for HttpRequest class."""

    def test_constructor(self):
        req = HttpRequest(method="GET", url="https://example.com/api")
        self.assertEqual(req.protocol, "https")
        self.assertEqual(req.domains, "example.com")
        self.assertEqual(req.endpoint, "api")
        self.assertEqual(req.url, "https://example.com/api")

    def test_constructor_with_data(self):
        req = HttpRequest(method="POST", url="https://example.com/api", data={"key": "value"})
        self.assertEqual(req.data, {"key": "value"})
        self.assertEqual(req.headers.get("Content-type"), "application/json")

    def test_repr(self):
        req = HttpRequest(method="GET", url="https://example.com/api")
        self.assertIn("example.com", repr(req))
        self.assertIn("GET", repr(req))

    def test_parser_dict(self):
        result = HttpRequest.parser({"key": "value"})
        self.assertIsInstance(result, bytes)
        self.assertIn(b"key", result)

    def test_parser_string(self):
        result = HttpRequest.parser("hello")
        self.assertEqual(result, b"hello")

    def test_parser_none(self):
        result = HttpRequest.parser(None)
        self.assertEqual(result, b"")

    def test_total_request_starts_at_zero(self):
        req = HttpRequest(method="GET", url="https://example.com")
        self.assertEqual(req.total_request, 0)

    def test_urllib_req_property(self):
        req = HttpRequest(method="POST", url="https://example.com/api", data={"a": 1})
        urllib_request = req.urllib_req
        self.assertEqual(urllib_request.get_method(), "POST")
        self.assertEqual(urllib_request.full_url, "https://example.com/api")


class HttpObjectTest(unittest.TestCase):
    """Tests for _Http object properties."""

    def test_url_reconstruction(self):
        http = _Http(url="https://api.example.com:8443/v1/users")
        self.assertEqual(http.url, "https://api.example.com:8443/v1/users")

    def test_content_type_header(self):
        http = _Http(url="https://example.com", headers={"Content-type": "text/html"})
        self.assertEqual(http.content_type, "text/html")

    def test_content_length_header(self):
        http = _Http(url="https://example.com", headers={"Content-length": "42"})
        self.assertEqual(http.content_length, "42")

    def test_default_headers_empty(self):
        http = _Http(url="https://example.com")
        self.assertEqual(http.headers, {})

    def test_default_data_none(self):
        http = _Http(url="https://example.com")
        self.assertIsNone(http.data)


if __name__ == "__main__":
    unittest.main()
