from copy import deepcopy
from types import SimpleNamespace
import unittest
from unittest.mock import Mock, patch

from cereja.scraping import crypto


QUOTE = {"data": {"amount": "432045.7657565002922797395", "base": "BTC", "currency": "BRL"}}


class CryptoMarketDataTest(unittest.TestCase):
    def make_client(self, payload=QUOTE, status=200):
        client = Mock()
        client.get.return_value = SimpleNamespace(status_code=status, json=lambda: payload)
        return client

    def test_default_brl_quote_preserves_decimal_string_and_provider_fields(self):
        payload = deepcopy(QUOTE)
        payload["provider_extension"] = {"value": 1}
        client = self.make_client(payload)
        with crypto.MarketData(client=client, timeout=7) as market:
            result = market.quote(" btc ")
        self.assertEqual(result, payload)
        self.assertEqual(result["data"]["amount"], "432045.7657565002922797395")
        client.get.assert_called_once_with("https://api.coinbase.com/v2/prices/BTC-BRL/spot", timeout=7)
        client.close.assert_not_called()

    def test_explicit_currency_and_symbol_are_normalized_independently(self):
        payload = {"data": {"base": "ETH", "currency": "USD", "amount": "2331.03"}}
        client = self.make_client(payload)
        with crypto.MarketData(client=client) as market:
            self.assertEqual(market.quote("eth", currency=" usd "), payload)
        client.get.assert_called_once_with("https://api.coinbase.com/v2/prices/ETH-USD/spot", timeout=30)

    def test_documented_response_without_base_is_accepted_without_adding_fields(self):
        payload = {"data": {"currency": "USD", "amount": "1015.00"}}
        with crypto.MarketData(client=self.make_client(payload)) as market:
            self.assertEqual(market.quote("BTC", "USD"), payload)

    def test_invalid_codes_are_rejected_before_request(self):
        client = self.make_client()
        with crypto.MarketData(client=client) as market:
            for code in ("", " ", "BTC-BRL", "../BTC", "BTC?x=1", "BT C", "ß", "ＢＴＣ", None, 5):
                for field in ("symbol", "currency"):
                    with self.subTest(field=field, code=code), self.assertRaises((TypeError, ValueError)):
                        market.quote(**{field: code, **({"symbol": "BTC"} if field == "currency" else {})})
        client.get.assert_not_called()

    def test_http_failures_and_provider_errors_are_explicit(self):
        cases = [(404, {}), (429, {}), (503, {}), (200, {"errors": [{"id": "invalid_request"}]}),
                 (200, {"data": QUOTE["data"], "errors": [{"id": "invalid_request"}]}),
                 (200, {"error": "unavailable", "data": QUOTE["data"]})]
        for status, payload in cases:
            with self.subTest(status=status, payload=payload):
                with crypto.MarketData(client=self.make_client(payload, status)) as market:
                    with self.assertRaises(crypto.MarketDataError):
                        market.quote("BTC")

    def test_transport_and_json_errors_keep_the_cause(self):
        for error in (TimeoutError("timed out"), ValueError("not JSON")):
            client = self.make_client()
            if isinstance(error, TimeoutError):
                client.get.side_effect = error
            else:
                client.get.return_value = SimpleNamespace(status_code=200, json=Mock(side_effect=error))
            with self.subTest(error=error), crypto.MarketData(client=client) as market:
                with self.assertRaises(crypto.MarketDataError) as caught:
                    market.quote("BTC")
                self.assertIs(caught.exception.__cause__, error)
            client.close.assert_not_called()

    def test_missing_or_malformed_quote_data_is_rejected(self):
        for payload in (None, [], {}, {"data": None}, {"data": []}, {"data": {}},
                        {"data": {"currency": "BRL"}}, {"data": {"amount": "1"}}):
            with self.subTest(payload=payload), crypto.MarketData(client=self.make_client(payload)) as market:
                with self.assertRaises(crypto.MarketDataError):
                    market.quote("BTC")

    def test_wrong_base_or_currency_is_rejected(self):
        for field, value in (("base", "ETH"), ("base", None), ("currency", "USD"), ("currency", None)):
            payload = deepcopy(QUOTE)
            payload["data"][field] = value
            with self.subTest(field=field, value=value):
                with crypto.MarketData(client=self.make_client(payload)) as market:
                    with self.assertRaises(crypto.MarketDataError):
                        market.quote("BTC")

    def test_invalid_non_finite_nonpositive_or_numeric_amounts_are_rejected(self):
        for amount in (None, 1.5, 1, True, "", "garbage", "NaN", "sNaN", "Infinity", "-Infinity", "0", "-1"):
            payload = deepcopy(QUOTE)
            payload["data"]["amount"] = amount
            with self.subTest(amount=amount), crypto.MarketData(client=self.make_client(payload)) as market:
                with self.assertRaises(crypto.MarketDataError):
                    market.quote("BTC")

    def test_construction_does_not_request_and_owned_client_closes_once(self):
        client = self.make_client()
        with patch.object(crypto, "Client", return_value=client) as factory:
            with crypto.MarketData(timeout=9) as market:
                factory.assert_called_once_with(timeout=9)
                client.get.assert_not_called()
                market.quote("BTC")
            market.close()
        client.close.assert_called_once_with()

    def test_owned_client_closes_when_request_or_validation_fails(self):
        for error in (None, TimeoutError("timed out")):
            client = self.make_client({})
            if error is not None:
                client.get.side_effect = error
            with self.subTest(error=error), patch.object(crypto, "Client", return_value=client):
                with self.assertRaises(crypto.MarketDataError):
                    with crypto.MarketData() as market:
                        market.quote("BTC")
            client.close.assert_called_once_with()

    def test_closed_market_rejects_requests_and_reentry(self):
        client = self.make_client()
        market = crypto.MarketData(client=client)
        market.close()
        with self.assertRaises(RuntimeError):
            market.quote("BTC")
        with self.assertRaises(RuntimeError):
            with market:
                pass
        client.get.assert_not_called()
        client.close.assert_not_called()


if __name__ == "__main__":
    unittest.main()
