"""Public Coinbase spot quotations, without authentication or trading operations."""

from decimal import Decimal as _Decimal, InvalidOperation as _InvalidOperation

from ..http import Client

__all__ = ["MarketData", "MarketDataError"]


class MarketDataError(ValueError):
    """The cryptocurrency provider failed or returned unusable quotation data."""


def _normalize_code(value, name):
    if not isinstance(value, str):
        raise TypeError(f"{name} must be a string")
    value = value.strip()
    if not value or not value.isascii() or not value.isalnum():
        raise ValueError(f"{name} must contain only ASCII letters and digits")
    return value.upper()


class MarketData:
    """Read Coinbase spot prices; retain decimal amounts as provider strings.

    Use as a context manager or call close() to release an owned HTTP client.
    An injected client remains owned by its caller. No requests occur on creation.
    """

    _BASE_URL = "https://api.coinbase.com/v2/prices"

    def __init__(self, *, client=None, timeout=30):
        self._owns_client = client is None
        self._client = Client(timeout=timeout) if client is None else client
        self._timeout = timeout
        self._closed = False

    def close(self):
        if not self._closed:
            self._closed = True
            if self._owns_client:
                self._client.close()

    def __enter__(self):
        if self._closed:
            raise RuntimeError("MarketData is closed")
        return self

    def __exit__(self, exc_type, exc, tb):
        self.close()

    def quote(self, symbol: str, currency: str = "BRL") -> dict:
        """Return full spot-price JSON for a base symbol and quote currency.

        The payload has no last-trade timestamp. A missing pair is a provider
        error, not proof that a cryptocurrency does not exist.
        """
        if self._closed:
            raise RuntimeError("MarketData is closed")
        symbol = _normalize_code(symbol, "symbol")
        currency = _normalize_code(currency, "currency")
        try:
            response = self._client.get(f"{self._BASE_URL}/{symbol}-{currency}/spot", timeout=self._timeout)
            if response.status_code != 200:
                raise MarketDataError(f"Coinbase spot-price request returned HTTP {response.status_code}.")
            payload = response.json()
        except MarketDataError:
            raise
        except Exception as err:
            raise MarketDataError("Coinbase spot-price request or JSON decoding failed.") from err
        if not isinstance(payload, dict) or payload.get("errors") or payload.get("error"):
            raise MarketDataError("Invalid Coinbase spot-price response or provider error.")
        data = payload.get("data")
        if not isinstance(data, dict) or data.get("currency") != currency or data.get("base", symbol) != symbol:
            raise MarketDataError("Coinbase spot-price pair does not match the requested pair.")
        amount = data.get("amount")
        if not isinstance(amount, str):
            raise MarketDataError("Missing or invalid Coinbase decimal amount.")
        try:
            price = _Decimal(amount)
        except _InvalidOperation as err:
            raise MarketDataError("Invalid Coinbase decimal amount.") from err
        if not price.is_finite() or price <= 0:
            raise MarketDataError("Coinbase spot price must be finite and positive.")
        return payload
