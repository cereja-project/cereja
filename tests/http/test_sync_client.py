import unittest

from cereja.http import BodyLimitExceeded, ProtocolError, ReadTimeout
from cereja.http.sync import Client
from tests.http._server import running_server


class SyncClientTest(unittest.TestCase):
    def test_get_json_and_post_bytes(self):
        with running_server() as (base, _):
            with Client() as client:
                response = client.get(base + "/json")
                self.assertEqual(response.json(), {"ok": True})
                posted = client.post(base + "/fixed", content=b"\x00\xff").json()
                self.assertEqual(posted["body"].encode("latin1"), b"\x00\xff")

    def test_connection_reuse(self):
        with running_server() as (base, handler):
            with Client(max_connections=2) as client:
                self.assertEqual(client.get(base + "/fixed").content, b"hello")
                self.assertEqual(client.get(base + "/fixed").content, b"hello")
            self.assertEqual(len(handler.seen_connections), 1)

    def test_chunked_and_connection_close(self):
        with running_server() as (base, _):
            with Client() as client:
                self.assertEqual(client.get(base + "/chunked").content, b"abcdefg")
                self.assertEqual(client.get(base + "/close").content, b"bye")

    def test_streaming(self):
        with running_server() as (base, _):
            with Client() as client:
                with client.stream("GET", base + "/chunked") as response:
                    self.assertEqual(b"".join(response.iter_bytes(2)), b"abcdefg")

    def test_body_limit(self):
        with running_server() as (base, _):
            with Client(max_body_bytes=16) as client:
                with self.assertRaises(BodyLimitExceeded):
                    client.get(base + "/large")

    def test_redirect(self):
        with running_server() as (base, _):
            with Client() as client:
                self.assertEqual(client.get(base + "/redirect").content, b"hello")
                with self.assertRaises(ProtocolError):
                    client.get(base + "/loop")

    def test_read_timeout(self):
        with running_server() as (base, _):
            with Client(timeout=0.05) as client:
                with self.assertRaises(ReadTimeout):
                    client.get(base + "/slow")

    def test_truncated_body_is_protocol_error(self):
        with running_server() as (base, _):
            with Client() as client:
                with self.assertRaises(ProtocolError):
                    client.get(base + "/truncated")


if __name__ == "__main__":
    unittest.main()
