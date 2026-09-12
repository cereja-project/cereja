import unittest

from cereja.http.async_ import AsyncClient
from cereja.http.sync import Client
from ._server import running_server


class SyncPoolRegressionTest(unittest.TestCase):
    def test_global_limit_can_move_idle_capacity_between_origins(self):
        with running_server() as (first, _), running_server() as (second, _):
            with Client(max_connections=1, timeout=0.5) as client:
                self.assertEqual(client.get(first + "/fixed").content, b"hello")
                self.assertEqual(client.get(second + "/fixed").content, b"hello")


class AsyncPoolRegressionTest(unittest.IsolatedAsyncioTestCase):
    async def test_global_limit_can_move_idle_capacity_between_origins(self):
        with running_server() as (first, _), running_server() as (second, _):
            async with AsyncClient(max_connections=1, timeout=0.5) as client:
                self.assertEqual((await client.get(first + "/fixed")).content, b"hello")
                self.assertEqual((await client.get(second + "/fixed")).content, b"hello")


if __name__ == "__main__":
    unittest.main()
