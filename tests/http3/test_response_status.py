import unittest

from cereja.http import Headers, HTTPStatusError, Request, Response, ResponseInfo, URL
from cereja.http.async_.stream import AsyncStreamResponse
from cereja.http.sync.stream import StreamResponse


class ResponseStatusTest(unittest.TestCase):
    def test_materialized_subclass_reason_is_preserved(self):
        class CustomResponse(Response):
            @property
            def reason(self):
                if self.status_code < 400:
                    raise AssertionError("reason accessed for a successful response")
                return "Custom reason"

        response = self.responses(404)[0]
        custom = CustomResponse(response.request, response.info, response.content)
        with self.assertRaisesRegex(HTTPStatusError, "HTTP 404 Custom reason"):
            custom.raise_for_status()
        successful = self.responses(200)[0]
        custom = CustomResponse(successful.request, successful.info, successful.content)
        self.assertIsNone(custom.raise_for_status())

    def responses(self, status):
        url = URL.parse("https://example.com/file")
        request = Request("GET", url, Headers(), None)
        info = ResponseInfo(status, "Example status", Headers(), url, "HTTP/1.1")
        return (
            Response(request, info, b"payload"),
            StreamResponse(request, info, object()),
            AsyncStreamResponse(request, info, object()),
        )

    def test_status_below_400_returns_none_without_consuming_body(self):
        for status in (200, 204, 301, 399):
            for response in self.responses(status):
                with self.subTest(status=status, response=type(response).__name__):
                    self.assertIsNone(response.raise_for_status())

    def test_error_preserves_request_and_response_without_consuming_body(self):
        for status in (400, 401, 404, 429, 500, 503):
            for response in self.responses(status):
                with self.subTest(status=status, response=type(response).__name__):
                    with self.assertRaises(HTTPStatusError) as caught:
                        response.raise_for_status()
                    error = caught.exception
                    self.assertIs(error.request, response.request)
                    self.assertIs(error.response, response)
                    self.assertNotIsInstance(error, RuntimeError)
                    self.assertEqual(
                        str(error),
                        f"HTTP {status} Example status for GET https://example.com/file",
                    )


if __name__ == "__main__":
    unittest.main()
