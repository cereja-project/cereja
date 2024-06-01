from .._requests import request
from ..hashtools import base64_encode
from ..utils import get_zero_mask
from ._financial import FinancialData

__all__ = ["Share"]
STOCK_EXCHANGES_CONFIG = {
    "B3": {"base_api_url":         "https://sistemaswebb3-listados.b3.com.br/listedCompaniesProxy/CompanyCall",
           "regist_info_endpoint": "GetInitialCompanies",
           "head_lines_endpoint":  "GetListedHeadLines",
           "financial_endpoint":   "GetListedFinancial",
           }
}


class StockExchangeConfig:
    _instance = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super(StockExchangeConfig, cls).__new__(cls)
            cls._instance._initialize()
        return cls._instance

    def _initialize(self):
        # Initializes the configurations for the stock exchange APIs
        self.config = STOCK_EXCHANGES_CONFIG

    def get_config(self, exchange):
        # Returns config for a specific stock exchange
        return self.config.get(exchange.upper())


class Share:
    def __init__(self, trading_code, exchange="B3", language="pt-br"):
        self.trading_code = trading_code.upper()
        self.language = language
        self.config = StockExchangeConfig().get_config(exchange)
        self._head_lines = None
        self._financial = None

        if not self.config:
            raise ValueError(f"Exchange {exchange} is currently not supported.")

        self._get_share_info()

    def _get(self, url_parsed, timeout=30) -> dict:
        response = request.get(url_parsed, timeout=timeout)
        if response.code == 200:
            return response.json()
        raise ConnectionRefusedError(response.data)

    def _get_share_info(self):

        try:
            # Fetches and processes the share information from the API
            query = {"language": self.language, "pageNumber": 1, "pageSize": 20, "company": self.trading_code}
            query_encoded = base64_encode(query).decode()
            url = f"{self.config['base_api_url']}/{self.config['regist_info_endpoint']}/{query_encoded}"
            response = self._get(url)
            results = response.get("results", [])

            if results:
                reg_info = results[0]
                self.code_cvm = reg_info["codeCVM"]
                self.name = reg_info["companyName"]
                self.cnpj = get_zero_mask(int(reg_info["cnpj"]), 14)
                self.segment = reg_info["segment"]
                self.market_indicator = reg_info["marketIndicator"]
                self.bdr_type = reg_info["typeBDR"]
                self.date_listing = reg_info["dateListing"]

        except Exception as err:
            raise Exception(f"Erro ao processar dados de registro. {err}")

    def _get_headlines(self):

        try:
            # Fetches and processes the headlines related to the share from the API
            query = {
                'agency':         self.market_indicator,
                'dateInitial':    '2024-05-02',
                'dateFinal':      '2024-06-01',
                'issuingCompany': ''.join(char for char in self.trading_code if not char.isnumeric())
            }
            query_encoded = base64_encode(query).decode()
            url = f"{self.config['base_api_url']}/{self.config['head_lines_endpoint']}/{query_encoded}"
            response = self._get(url)
            self._head_lines = []
            for headline in response:
                self._head_lines.append({
                    "headline": headline["headline"],
                    "date":     headline["dateTime"],
                    "url":      headline["url"]
                })

        except Exception as err:
            raise Exception(f"Erro ao processar dados de eventos. {err}")

    def _get_financial(self):
        try:
            # Fetches and processes the headlines related to the share from the API
            query = {"codeCVM":  self.code_cvm,
                     "language": "pt-br"}
            query_encoded = base64_encode(query).decode()
            url = f"{self.config['base_api_url']}/{self.config['financial_endpoint']}/{query_encoded}"
            response = self._get(url)
            if response:
                self._financial = FinancialData(
                        share=self,
                        title_initial=response.get("titleInitial", ''),
                        consolidated=response.get("consolidated", {}),
                        unconsolidated=response.get("consolidated", {}),
                        free_float_result=response.get("freeFloatResult", {}),
                        position_shareholders=response.get("positionShareholders", {}),
                        outstanding_shares=response.get("outstandingShares", {}),
                        capital_stock_composition=response.get("capitalStockComposition", {})
                )
            else:
                self._financial = {}
        except Exception as err:
            raise Exception(f"Erro ao processar dados financeiros. {err}")

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
        # Returns the stock exchange associated with the share
        return self.config.get("exchange")

    @property
    def is_bdr(self):
        # Checks if the share is a BDR (Brazilian Depositary Receipt)
        return bool(self.bdr_type)

    def __repr__(self):
        # String representation of the Share instance
        return f"{self.trading_code}(cnpj={self.cnpj}, name={self.name})"
