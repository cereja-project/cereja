import unittest
from types import SimpleNamespace
from unittest.mock import patch

from cereja.scraping import b3


REGISTRATION = {
    "codeCVM": "9512",
    "companyName": "PETROLEO BRASILEIRO S.A. PETROBRAS",
    "cnpj": "33000167000101",
    "segment": "Oil",
    "marketIndicator": "1",
    "typeBDR": "",
    "dateListing": "1968-08-27",
}


class RegistryClient:
    def __init__(self, payload=None, *, status=200, error=None):
        self.payload = payload
        self.status = status
        self.error = error
        self.closed = False

    def get(self, url, **kwargs):
        if self.error is not None:
            raise self.error
        return SimpleNamespace(
            status_code=self.status,
            content=b"provider unavailable",
            json=lambda: self.payload,
        )

    def close(self):
        self.closed = True


class ShareRegistrationTest(unittest.TestCase):
    def test_success_preserves_registration_fields(self):
        client = RegistryClient({"results": [REGISTRATION]})
        share = b3.Share("petr4", client=client)
        self.assertEqual(share.trading_code, "PETR4")
        self.assertEqual(share.name, REGISTRATION["companyName"])
        self.assertEqual(share.cnpj, "33000167000101")
        self.assertEqual(share.code_cvm, "9512")
        self.assertEqual(share.segment, "Oil")
        self.assertEqual(share.date_listing, "1968-08-27")
        self.assertFalse(client.closed)

    def test_empty_company_results_raise_lookup_error_for_each_symbol(self):
        for symbol in ("WRLD11", "BOVV11", "HGLG11", "INVALIDO"):
            with self.subTest(symbol=symbol):
                with self.assertRaisesRegex(LookupError, symbol):
                    b3.Share(symbol, client=RegistryClient({"results": []}))

    def test_missing_or_malformed_results_are_provider_data_errors(self):
        for payload in ({}, None, [], {"results": None}, {"results": {}},
                        {"results": "unexpected"}, {"results": [None]}):
            with self.subTest(payload=payload):
                with self.assertRaises(ValueError):
                    b3.Share("PETR4", client=RegistryClient(payload))

    def test_incomplete_registration_is_a_provider_data_error(self):
        with self.assertRaises(ValueError) as caught:
            b3.Share("PETR4", client=RegistryClient({"results": [{"codeCVM": "9512"}]}))
        self.assertIsInstance(caught.exception.__cause__, KeyError)

    def test_http_failure_is_distinct_from_missing_registration(self):
        with self.assertRaises(ValueError) as caught:
            b3.Share("PETR4", client=RegistryClient(status=503))
        self.assertNotIsInstance(caught.exception, LookupError)
        self.assertIsInstance(caught.exception.__cause__, ConnectionRefusedError)

    def test_transport_failure_preserves_its_cause(self):
        error = TimeoutError("upstream timed out")
        with self.assertRaises(ValueError) as caught:
            b3.Share("PETR4", client=RegistryClient(error=error))
        self.assertIs(caught.exception.__cause__, error)

    def test_failed_constructor_closes_owned_client(self):
        client = RegistryClient({"results": []})
        with patch.object(b3, "Client", return_value=client):
            with self.assertRaises(LookupError):
                b3.Share("WRLD11")
        self.assertTrue(client.closed)

    def test_failed_constructor_preserves_borrowed_client(self):
        client = RegistryClient({"results": []})
        with self.assertRaises(LookupError):
            b3.Share("WRLD11", client=client)
        self.assertFalse(client.closed)

    def test_context_manager_closes_owned_client(self):
        client = RegistryClient({"results": [REGISTRATION]})
        with patch.object(b3, "Client", return_value=client):
            with b3.Share("PETR4") as share:
                self.assertEqual(share.trading_code, "PETR4")
                self.assertFalse(client.closed)
        self.assertTrue(client.closed)


if __name__ == "__main__":
    unittest.main()
