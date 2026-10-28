from copy import deepcopy
import unittest
from types import SimpleNamespace
from unittest.mock import Mock, patch

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


QUOTE = {
    "BizSts": {"cd": "OK"},
    "Msg": {"dtTm": "2026-10-28 13:05:08"},
    "Trad": [{
        "scty": {
            "symb": "WRLD11",
            "desc": "INVESTO WRLDCI",
            "mkt": {"nm": "ETF"},
            "SctyQtn": {"curPrc": 153.49, "prcFlcn": 0.5700432},
        },
        "ttlQty": 1765,
    }],
}
FLOOR = {
    "BizSts": {"cd": "OK"},
    "Msg": {"dtTm": "2026-10-28T11:50:02Z"},
    "TradgFlr": {"TradgFlrSts": {"desc": "A"}, "grssAmt": 16521886011.66, "qty": 2176225},
}


class MarketDataTest(unittest.TestCase):
    def make_client(self, payload=QUOTE, status=200):
        client = Mock()
        client.get.return_value = SimpleNamespace(status_code=status, json=lambda: payload)
        return client

    def test_quote_preserves_provider_fields_and_normalizes_only_input_symbol(self):
        for symbol in ("WRLD11", "BOVV11", "IBOV"):
            with self.subTest(symbol=symbol):
                payload = deepcopy(QUOTE)
                payload["Trad"][0]["scty"]["symb"] = symbol
                client = self.make_client(payload)
                with b3.MarketData(client=client, timeout=7) as market:
                    result = market.quote(" " + symbol.lower() + " ")
                self.assertEqual(result, payload)
                self.assertEqual(result["Msg"]["dtTm"], "2026-10-28 13:05:08")
                client.get.assert_called_once_with(
                    "https://cotacao.b3.com.br/mds/api/v1/instrumentQuotation/" + symbol,
                    timeout=7,
                )
                client.close.assert_not_called()

    def test_trading_floor_preserves_code_and_timestamp_without_interpretation(self):
        client = self.make_client(FLOOR)
        with b3.MarketData(client=client) as market:
            self.assertEqual(market.trading_floor(), FLOOR)
        client.get.assert_called_once_with(
            "https://cotacao.b3.com.br/mds/api/v1/TradingFloorInfo", timeout=30,
        )

    def test_invalid_symbols_are_rejected_before_request(self):
        client = self.make_client()
        with b3.MarketData(client=client) as market:
            for symbol in ("", " ", "../WRLD11", "WRLD11?x=1", "WRLD11/IBOV", "ＩＢＯＶ", "ß", None, 11):
                with self.subTest(symbol=symbol), self.assertRaises((ValueError, TypeError)):
                    market.quote(symbol)
        client.get.assert_not_called()

    def test_http_and_business_failures_are_not_missing_company_errors(self):
        cases = [(503, QUOTE), (404, {}), (200, {"BizSts": {"cd": "NOK"}})]
        for status, payload in cases:
            with self.subTest(status=status, payload=payload):
                for method in ("quote", "trading_floor"):
                    with b3.MarketData(client=self.make_client(payload, status)) as market:
                        with self.assertRaises(b3.MarketDataError) as caught:
                            if method == "quote":
                                market.quote("WRLD11")
                            else:
                                market.trading_floor()
                    self.assertNotIsInstance(caught.exception, b3.ShareNotFoundError)

    def test_transport_and_json_errors_preserve_original_cause(self):
        for error in (TimeoutError("timed out"), ValueError("invalid JSON")):
            with self.subTest(error=error):
                client = self.make_client()
                if isinstance(error, TimeoutError):
                    client.get.side_effect = error
                else:
                    client.get.return_value = SimpleNamespace(status_code=200, json=Mock(side_effect=error))
                with b3.MarketData(client=client) as market:
                    with self.assertRaises(b3.MarketDataError) as caught:
                        market.quote("WRLD11")
                self.assertIs(caught.exception.__cause__, error)
                client.close.assert_not_called()

    def test_invalid_envelopes_fail_for_both_methods(self):
        for payload in (None, [], {}, {"BizSts": []}, {"BizSts": {"cd": "OK"}},
                        {"BizSts": {"cd": "OK"}, "Msg": {"dtTm": 123}}):
            with self.subTest(payload=payload):
                with b3.MarketData(client=self.make_client(payload)) as market:
                    with self.assertRaises(b3.MarketDataError):
                        market.quote("WRLD11")
                    with self.assertRaises(b3.MarketDataError):
                        market.trading_floor()

    def test_quote_rejects_missing_malformed_and_wrong_symbol_data(self):
        for trades in ([], None, {}, [None], [{}], [{"scty": []}],
                       [{"scty": {"symb": "BOVV11", "SctyQtn": {"curPrc": 153.49}}}],
                       [{"scty": {"symb": "WRLD11", "SctyQtn": {}}}]):
            payload = deepcopy(QUOTE)
            payload["Trad"] = trades
            with self.subTest(trades=trades):
                with b3.MarketData(client=self.make_client(payload)) as market:
                    with self.assertRaises(b3.MarketDataError):
                        market.quote("WRLD11")

    def test_quote_rejects_non_numeric_or_non_finite_prices(self):
        for price in (None, "153.49", True, float("nan"), float("inf")):
            payload = deepcopy(QUOTE)
            payload["Trad"][0]["scty"]["SctyQtn"]["curPrc"] = price
            with self.subTest(price=price):
                with b3.MarketData(client=self.make_client(payload)) as market:
                    with self.assertRaises(b3.MarketDataError):
                        market.quote("WRLD11")

    def test_floor_rejects_missing_or_malformed_status(self):
        for floor in (None, [], {}, {"TradgFlrSts": []}, {"TradgFlrSts": {"desc": None}},
                      {"TradgFlrSts": {"desc": ""}}):
            payload = deepcopy(FLOOR)
            payload["TradgFlr"] = floor
            with self.subTest(floor=floor):
                with b3.MarketData(client=self.make_client(payload)) as market:
                    with self.assertRaises(b3.MarketDataError):
                        market.trading_floor()

    def test_construction_makes_no_requests_and_closes_owned_client_once(self):
        client = self.make_client()
        with patch.object(b3, "Client", return_value=client) as factory:
            with b3.MarketData(timeout=8) as market:
                factory.assert_called_once_with(timeout=8)
                client.get.assert_not_called()
                market.quote("WRLD11")
            market.close()
        client.close.assert_called_once_with()

    def test_owned_client_is_closed_on_request_or_validation_failure(self):
        for payload, error in (({}, None), (QUOTE, TimeoutError("timed out"))):
            client = self.make_client(payload)
            if error is not None:
                client.get.side_effect = error
            with self.subTest(error=error), patch.object(b3, "Client", return_value=client):
                with self.assertRaises(b3.MarketDataError):
                    with b3.MarketData() as market:
                        market.quote("WRLD11")
                client.close.assert_called_once_with()

    def test_closed_market_rejects_calls_without_using_borrowed_client(self):
        client = self.make_client()
        market = b3.MarketData(client=client)
        market.close()
        with self.assertRaises(RuntimeError):
            market.quote("WRLD11")
        with self.assertRaises(RuntimeError):
            market.trading_floor()
        client.get.assert_not_called()
        client.close.assert_not_called()


if __name__ == "__main__":
    unittest.main()
