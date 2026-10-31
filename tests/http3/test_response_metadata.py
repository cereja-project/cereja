"""Header-only metadata is consistent across all response views."""

import unittest

from cereja.http import DecodeError, Headers, Request, Response, ResponseInfo, URL
from cereja.http.async_.stream import AsyncStreamResponse
from cereja.http.sync.stream import StreamResponse


class ResponseMetadataTests(unittest.TestCase):
    def responses(self, values, content=b'payload', method='GET'):
        url = URL.parse('https://example.com/file.json')
        request = Request(method, url, Headers(), None)
        info = ResponseInfo(200, 'OK', Headers(values), url, 'HTTP/1.1')
        # Stream sentinels fail if metadata access tries to consume the body.
        return (
            info,
            Response(request, info, content),
            StreamResponse(request, info, object()),
            AsyncStreamResponse(request, info, object()),
        )

    def test_media_type_and_charset_are_normalized(self):
        cases = (
            ('Application/JSON; charset=UTF-8', 'application/json', 'utf-8'),
            (' Text/Plain ; CHARSET = "ISO-8859-1" ', 'text/plain', 'iso-8859-1'),
            ('application/problem+json', 'application/problem+json', None),
            ('multipart/form-data; boundary="a;b"; charset="UTF-8"', 'multipart/form-data', 'utf-8'),
            ('text/plain; note="a\\\";b"; charset=UTF-8', 'text/plain', 'utf-8'),
            ('text/plain; charset="UTF\\-8"', 'text/plain', 'utf-8'),
            ('text/plain;', 'text/plain', None),
            ('text/plain;;charset=utf-8;', 'text/plain', 'utf-8'),
            ('text/plain; charset=x-unknown-encoding', 'text/plain', 'x-unknown-encoding'),
            ('text/plain; charset=""', 'text/plain', None),
            ('text/plain; charset="bad name"', 'text/plain', None),
            ('text/plain; charset=utf-8; CHARSET=latin-1', 'text/plain', None),
            ('text/plain; charset=utf-8; charset=utf-8', 'text/plain', None),
        )
        for value, media_type, charset in cases:
            for response in self.responses([('Content-Type', value)]):
                with self.subTest(value=value, response=type(response).__name__):
                    self.assertEqual(response.content_type, media_type)
                    self.assertEqual(response.charset, charset)

    def test_missing_malformed_and_repeated_content_type_returns_none(self):
        cases = [[], [('Content-Type', 'text/plain'), ('Content-Type', 'text/plain')]]
        for value in ('', 'plain', 'text/', '/plain', 'text/plain/extra', 'text /plain',
                      'text/plain, application/json', 'text/plain; charset="unterminated',
                      'text/plain; charset=utf-8 garbage', 'text/plain; flag',
                      'text/plain; charset='):
            cases.append([('Content-Type', value)])
        for values in cases:
            for response in self.responses(values):
                with self.subTest(values=values, response=type(response).__name__):
                    self.assertIsNone(response.content_type)
                    self.assertIsNone(response.charset)

    def test_content_length_is_declared_length_not_body_size(self):
        for value, expected in (('0', 0), ('123', 123), ('0007', 7), (' \t42\t ', 42),
                                ('18446744073709551616', 18446744073709551616)):
            for response in self.responses([('Content-Length', value)], content=b'', method='HEAD'):
                with self.subTest(value=value, response=type(response).__name__):
                    self.assertEqual(response.content_length, expected)
                    self.assertIs(type(response.content_length), int)
        for response in self.responses([('Transfer-Encoding', 'chunked')], content=b'payload'):
            self.assertIsNone(response.content_length)

    def test_missing_invalid_or_repeated_lengths_return_none(self):
        cases = [[], [('Content-Length', '7'), ('Content-Length', '7')],
                 [('Content-Length', '7'), ('Content-Length', '8')]]
        for value in ('', '-1', '+1', '1.5', '1e3', '7, 7', '1_000', '\u00b2', '1 2'):
            cases.append([('Content-Length', value)])
        for values in cases:
            for response in self.responses(values):
                with self.subTest(values=values, response=type(response).__name__):
                    self.assertIsNone(response.content_length)

    def test_properties_do_not_mutate_headers_and_follow_header_changes(self):
        for response in self.responses([('Content-Type', 'text/plain; charset=UTF-8'),
                                        ('Content-Length', '100')]):
            before = response.headers.items()
            self.assertEqual(response.content_type, 'text/plain')
            self.assertEqual(response.charset, 'utf-8')
            self.assertEqual(response.content_length, 100)
            self.assertEqual(response.headers.items(), before)
        for index in range(4):
            response = self.responses([])[index]
            self.assertIsNone(response.content_type)
            response.headers.set('Content-Type', 'application/json; charset=ASCII')
            response.headers.set('Content-Length', '0')
            self.assertEqual(response.content_type, 'application/json')
            self.assertEqual(response.charset, 'ascii')
            self.assertEqual(response.content_length, 0)
            if isinstance(response, Response):
                self.assertEqual(response.content, b'payload')

    def test_text_decoding_retains_existing_behavior(self):
        response = self.responses([], content='\u20ac'.encode('utf-8'))[1]
        self.assertEqual(response.text, '\u20ac')
        self.assertIsNone(response.charset)
        response = self.responses([('Content-Type', 'text/plain; charset="latin-1"')], content=b'\xa3')[1]
        self.assertEqual(response.text, '\u00a3')
        self.assertEqual(response.charset, 'latin-1')
        response = self.responses([('Content-Type', 'text/plain; charset=x-unknown-encoding')])[1]
        self.assertEqual(response.charset, 'x-unknown-encoding')
        with self.assertRaises(DecodeError):
            _ = response.text


if __name__ == '__main__':
    unittest.main()
