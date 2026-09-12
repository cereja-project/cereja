import unittest

from cereja._requests import request as legacy_request
from ._server import running_server


class LegacyFacadeTest(unittest.TestCase):
    def test_legacy_request_functions_route_through_new_http_stack(self):
        with running_server() as (base, _):
            response = legacy_request.get(base + "/json")
            self.assertEqual(response.code, 200)
            self.assertTrue(response.success)
            self.assertEqual(response.json(), {"ok": True})
            self.assertEqual(response.data, {"ok": True})


if __name__ == "__main__":
    unittest.main()
