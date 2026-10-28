from math import isfinite as _isfinite

from ..http import Client
from ..hashtools import base64_encode
from ..utils import get_zero_mask
from ._financial import FinancialData

__all__ = ["Share", "ShareNotFoundError", "ShareDataError", "MarketData", "MarketDataError"]
STOCK_EXCHANGES_CONFIG = {
    "B3": {"base_api_url": "https://sistemaswebb3-listados.b3.com.br/listedCompaniesProxy/CompanyCall",
           "regist_info_endpoint": "GetInitialCompanies",
           "head_lines_endpoint": "GetListedHeadLines",
           "financial_endpoint": "GetListedFinancial"}
}


class ShareNotFoundError(LookupError):
    """The company registry has no registration for the requested symbol."""


class ShareDataError(ValueError):
    """The provider request failed or returned unusable registration data."""


class MarketDataError(ValueError):
    """The market-data provider failed or returned unusable data."""


class MarketData:
    """Read B3 quotation and trading-floor JSON independently of company registration.

    Responses retain the provider's fields and timestamp strings. Message times
    do not establish trade times or the effective delay of a quotation.
    """

    _BASE_URL = "https://cotacao.b3.com.br/mds/api/v1"

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

    def _get(self, endpoint):
        if self._closed:
            raise RuntimeError("MarketData is closed")
        try:
            response = self._client.get(f"{self._BASE_URL}/{endpoint}", timeout=self._timeout)
            if response.status_code != 200:
                raise MarketDataError(f"B3 market-data request returned HTTP {response.status_code}.")
            payload = response.json()
        except MarketDataError:
            raise
        except Exception as err:
            raise MarketDataError("B3 market-data request or JSON decoding failed.") from err
        if not isinstance(payload, dict):
            raise MarketDataError("Invalid B3 market-data response.")
        status = payload.get("BizSts")
        if not isinstance(status, dict) or status.get("cd") != "OK":
            raise MarketDataError("B3 market-data business status is not OK.")
        message = payload.get("Msg")
        if not isinstance(message, dict) or not isinstance(message.get("dtTm"), str) or not message["dtTm"].strip():
            raise MarketDataError("Missing or invalid B3 message timestamp.")
        return payload

    def quote(self, symbol: str) -> dict:
        """Return the provider JSON for one symbol, including ``Trad`` and ``Msg``.

        Unavailable quotations raise MarketDataError, not ShareNotFoundError.
        """
        if not isinstance(symbol, str):
            raise TypeError("symbol must be a string")
        symbol = symbol.strip()
        if not symbol or not symbol.isascii() or not symbol.isalnum():
            raise ValueError("symbol must contain only ASCII letters and digits")
        symbol = symbol.upper()
        payload = self._get(f"instrumentQuotation/{symbol}")
        trades = payload.get("Trad")
        if not isinstance(trades, list) or len(trades) != 1 or not isinstance(trades[0], dict):
            raise MarketDataError("Expected one B3 quotation record.")
        security = trades[0].get("scty")
        if not isinstance(security, dict) or security.get("symb") != symbol:
            raise MarketDataError("B3 quotation symbol does not match the requested symbol.")
        quotation = security.get("SctyQtn")
        price = quotation.get("curPrc") if isinstance(quotation, dict) else None
        if (isinstance(price, bool) or not isinstance(price, (int, float))
                or (isinstance(price, float) and not _isfinite(price))):
            raise MarketDataError("Missing or invalid B3 quotation price.")
        return payload

    def trading_floor(self) -> dict:
        """Return provider JSON; preserve the trading-floor status code verbatim."""
        payload = self._get("TradingFloorInfo")
        floor = payload.get("TradgFlr")
        status = floor.get("TradgFlrSts") if isinstance(floor, dict) else None
        description = status.get("desc") if isinstance(status, dict) else None
        if not isinstance(description, str) or not description.strip():
            raise MarketDataError("Missing or invalid B3 trading-floor status.")
        return payload


class StockExchangeConfig:
    _instance = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance.config = STOCK_EXCHANGES_CONFIG
        return cls._instance

    def get_config(self, exchange):
        return self.config.get(exchange.upper())


class Share:
    def __init__(self, trading_code, exchange="B3", language="pt-br", *, client=None):
        self.trading_code = trading_code.upper()
        self.language = language
        self.config = StockExchangeConfig().get_config(exchange)
        self._head_lines = None
        self._financial = None
        self._owns_client = client is None
        self._client = client or Client(timeout=30)
        if not self.config:
            self.close()
            raise ValueError(f"Exchange {exchange} is currently not supported.")
        try:
            self._get_share_info()
        except Exception:
            self.close()
            raise

    def close(self):
        if self._owns_client and self._client is not None:
            self._client.close()
            self._client = None

    def __enter__(self): return self
    def __exit__(self, exc_type, exc, tb): self.close()

    def _get(self, url_parsed, timeout=30) -> dict:
        response = self._client.get(url_parsed, timeout=timeout)
        if response.status_code == 200:
            return response.json()
        raise ConnectionRefusedError(response.content)

    def _get_share_info(self):
        try:
            query = {"language": self.language, "pageNumber": 1, "pageSize": 20, "company": self.trading_code}
            query_encoded = base64_encode(query).decode()
            url = f"{self.config['base_api_url']}/{self.config['regist_info_endpoint']}/{query_encoded}"
            response = self._get(url)
            if not isinstance(response, dict) or not isinstance(response.get("results"), list):
                raise ShareDataError("Invalid company registry response.")
            results = response["results"]
            if not results:
                raise ShareNotFoundError(f"No company registration found for {self.trading_code}.")
            reg_info = results[0]
            if not isinstance(reg_info, dict):
                raise ShareDataError("Invalid company registration record.")
            self.code_cvm = reg_info["codeCVM"]
            self.name = reg_info["companyName"]
            self.cnpj = get_zero_mask(int(reg_info["cnpj"]), 14)
            self.segment = reg_info["segment"]
            self.market_indicator = reg_info["marketIndicator"]
            self.bdr_type = reg_info["typeBDR"]
            self.date_listing = reg_info["dateListing"]
        except (ShareNotFoundError, ShareDataError):
            raise
        except Exception as err:
            raise ShareDataError(f"Erro ao processar dados de registro. {err}") from err

    def _get_headlines(self):
        try:
            query = {
                "agency": self.market_indicator,
                "dateInitial": "2024-05-02",
                "dateFinal": "2024-06-01",
                "issuingCompany": "".join(char for char in self.trading_code if not char.isnumeric()),
            }
            query_encoded = base64_encode(query).decode()
            url = f"{self.config['base_api_url']}/{self.config['head_lines_endpoint']}/{query_encoded}"
            response = self._get(url)
            self._head_lines = [
                {"headline": item["headline"], "date": item["dateTime"], "url": item["url"]}
                for item in response
            ]
        except Exception as err:
            raise Exception(f"Erro ao processar dados de eventos. {err}") from err

    def _get_financial(self):
        try:
            query = {"codeCVM": self.code_cvm, "language": "pt-br"}
            query_encoded = base64_encode(query).decode()
            url = f"{self.config['base_api_url']}/{self.config['financial_endpoint']}/{query_encoded}"
            response = self._get(url)
            if response:
                self._financial = FinancialData(
                    share=self,
                    title_initial=response.get("titleInitial", ""),
                    consolidated=response.get("consolidated", {}),
                    unconsolidated=response.get("consolidated", {}),
                    free_float_result=response.get("freeFloatResult", {}),
                    position_shareholders=response.get("positionShareholders", {}),
                    outstanding_shares=response.get("outstandingShares", {}),
                    capital_stock_composition=response.get("capitalStockComposition", {}),
                )
            else:
                self._financial = {}
        except Exception as err:
            raise Exception(f"Erro ao processar dados financeiros. {err}") from err

    @property
    def financial(self):
        if self._financial is None:
            self._get_financial()
        return self._financial

    @property
    def headlines(self):
        if self._head_lines is None:
            self._get_headlines()
        return self._head_lines

    @property
    def exchange(self):
        return self.config.get("exchange")

    @property
    def is_bdr(self):
        return bool(self.bdr_type)

    def to_dict(self):
        return {
            "trading_code": self.trading_code,
            "cnpj": self.cnpj,
            "name": self.name,
            "segment": self.segment,
            "market_indicator": self.market_indicator,
            "bdr_type": self.bdr_type,
            "date_listing": self.date_listing,
            "financial": self.financial.to_dict() if self.financial else None,
        }

    def __repr__(self):
        return f"{self.trading_code}(cnpj={self.cnpj}, name={self.name})"
