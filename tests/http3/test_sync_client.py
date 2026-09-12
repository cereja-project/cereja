import unittest

from cereja.http import BodyLimitExceeded, ProtocolError, ReadTimeout
from cereja.http.sync import Client
from ._server import running_server


class SyncClientTest(unittest.TestCase):
    def test_requests_reuse_stream_limits_redirects_and_errors(self):
        with running_server() as (base, handler):
            with Client(max_connections=2) as client:
                self.assertEqual(client.get(base + "/json").json(), {"ok": True})
                posted = client.post(base + "/fixed", content=b"\x00\xff").json()
                self.assertEqual(posted["body"].encode("latin1"), b"\x00\xff")
                self.assertEqual(client.get(base + "/fixed").content, b"hello")
            self.assertEqual(len(handler.seen_connections), 1)
        with running_server() as (base, _):
            with Client() as client:
                self.assertEqual(client.get(base + "/chunked").content, b"abcdefg")
                with client.stream("GET", base + "/chunked") as response:
                    self.assertEqual(b"".join(response.iter_bytes(2)), b"abcdefg")
                self.assertEqual(client.get(base + "/redirect").content, b"hello")
                with self.assertRaises(ProtocolError):
                    client.get(base + "/loop")
                with self.assertRaises(ProtocolError):
                    client.get(base + "/truncated")
            with Client(max_body_bytes=16) as client:
                with self.assertRaises(BodyLimitExceeded):
                    client.get(base + "/large")
            with Client(timeout=0.05) as client:
                with self.assertRaises(ReadTimeout):
                    client.get(base + "/slow")


if __name__ == "__main__":
    unittest.main()
