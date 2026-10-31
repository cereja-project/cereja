import unittest

from cereja.http import Headers, Request, Response, ResponseInfo, URL
from cereja.http.async_.stream import AsyncStreamResponse
from cereja.http.sync.stream import StreamResponse


class ResponseFilenameTest(unittest.TestCase):
    def responses(self, values):
        url = URL.parse("https://example.com/fallback.zip")
        request = Request("GET", url, Headers(), None)
        info = ResponseInfo(200, "OK", Headers(values), url, "HTTP/1.1")
        # Metadata access must not touch the stream or consume body bytes.
        return (
            info,
            Response(request, info, b"payload"),
            StreamResponse(request, info, object()),
            AsyncStreamResponse(request, info, object()),
        )

    def test_filename_is_shared_by_all_response_types(self):
        cases = (
            ('attachment; filename="report.zip"', "report.zip"),
            ('inline; FILENAME = "quarter; report.txt"', "quarter; report.txt"),
            ('attachment; filename=report.zip', "report.zip"),
            ("attachment; filename*=UTF-8''%E2%82%AC%20rates.csv", "\u20ac rates.csv"),
            ("attachment; filename*=ISO-8859-1'en'%A3rates.csv", "\u00a3rates.csv"),
            ('attachment; filename="fallback.csv"; filename*=UTF-8\'\'preferred.csv',
             "preferred.csv"),
            ('attachment; filename*=UTF-8\'\'preferred.csv; filename="fallback.csv"',
             "preferred.csv"),
            ('attachment; filename="100%20complete.txt"', "100%20complete.txt"),
            ('attachment; filename="../../report.zip"', "report.zip"),
            ('attachment; filename="C:\\\\downloads\\\\report.zip"', "report.zip"),
            ("attachment; filename*=UTF-8''..%2F..%2Freport.zip", "report.zip"),
            ('attachment; filename="report.zip"; size=123', "report.zip"),
            ('attachment; filename="  report.zip  "', "report.zip"),
        )
        for header, expected in cases:
            for response in self.responses([("Content-Disposition", header)]):
                with self.subTest(header=header, response=type(response).__name__):
                    self.assertEqual(response.filename, expected)

    def test_missing_invalid_or_unsafe_names_return_none(self):
        cases = (
            [],
            [("Content-Disposition", "attachment")],
            [("Content-Disposition", 'attachment; filename=""')],
            [("Content-Disposition", 'attachment; filename="unterminated')],
            [("Content-Disposition", 'attachment; filename="report.zip"garbage')],
            [("Content-Disposition", 'attachment; filename=report name.zip')],
            [("Content-Disposition", 'attachment; filename="report.zip";')],
            [("Content-Disposition", 'attachment; filename*0="report"; filename*1=".zip"')],
            [("Content-Disposition", 'attachment, inline; filename="report.zip"')],
            [("Content-Disposition", 'attachment; filename="a.zip"; FILENAME="b.zip"')],
            [("Content-Disposition", 'attachment; filename="a.zip"'),
             ("Content-Disposition", 'attachment; filename="b.zip"')],
        )
        for value in (".", "..", "~", "CON", "nul.txt", "COM1.zip", "LPT9", "name:stream",
                      "file?.zip", "file|name", "trailing.", "a\tb.zip", "../", "CONIN$",
                      "COM\u00b9.txt", "\\\\server\\\\NUL.txt"):
            cases += ([("Content-Disposition", f'attachment; filename="{value}"')],)
        for headers in cases:
            for response in self.responses(headers):
                with self.subTest(headers=headers, response=type(response).__name__):
                    self.assertIsNone(response.filename)

    def test_invalid_extended_value_uses_plain_fallback(self):
        for extended in ("UTF-8''bad%ZZ", "UTF-8''bad%FF", "UTF-8''bad%",
                         "unknown''report.zip", "missing-encoding", "UTF-8''%00bad.zip"):
            header = f'attachment; filename="fallback.zip"; filename*={extended}'
            with self.subTest(extended=extended):
                self.assertEqual(self.responses([("Content-Disposition", header)])[0].filename,
                                 "fallback.zip")
                header = f"attachment; filename*={extended}"
                self.assertIsNone(self.responses([("Content-Disposition", header)])[0].filename)

    def test_metadata_does_not_mutate_headers_or_body(self):
        headers = [("Content-Disposition", 'attachment; filename="report.zip"')]
        for response in self.responses(headers):
            before = response.headers.items()
            self.assertEqual(response.filename, "report.zip")
            self.assertEqual(response.headers.items(), before)
            response.headers.set("Content-Disposition", 'inline; filename="updated.zip"')
            self.assertEqual(response.filename, "updated.zip")
            if isinstance(response, Response):
                self.assertEqual(response.content, b"payload")
            response.headers.set("Content-Disposition", 'attachment; filename="report.zip"')


if __name__ == "__main__":
    unittest.main()
