from .._requests import request
from ..hashtools import base64_encode
from ..utils import get_zero_mask

__all__ = ["Share"]
STOCK_EXCHANGES_CONFIG = {
    "B3": {"base_api_url":         "https://sistemaswebb3-listados.b3.com.br/listedCompaniesProxy/CompanyCall",
           "regist_info_endpoint": "GetInitialCompanies",
           "head_lines_endpoint":  "GetListedHeadLines"}
}


def _parse_b3_url_query(query):
    query_base64_str = base64_encode(query).decode()
    return f"{STOCK_EXCHANGES_CONFIG['B3']}/{query_base64_str}"


class Share:
    name: str
    cnpj: str
    trading_code: str
    code_cvm: str
    date_listing: str  # dd/mm/yyyy
    bdr_type: str
    is_bdr: bool
    market_indicator: int

    language: str = "pt-br"

    def __init__(self, trading_code, exchange="B3"):
        assert exchange in STOCK_EXCHANGES_CONFIG, f"Exchange {exchange} is currently not supported."

        self.trading_code = trading_code.upper()  # TODO: need validation
        self._exchange = exchange.upper()
        self._api_config = STOCK_EXCHANGES_CONFIG[self._exchange]
        self._head_lines = []

        if self._exchange == "B3":
            try:
                # Regist info
                query = {"language": self.language, "pageNumber": 1, "pageSize": 20, "company": self.trading_code}
                # need convert base64
                query = base64_encode(query).decode()
                query_url_parsed = f"{self._api_config['base_api_url']}/{self._api_config['regist_info_endpoint']}/{query}"
                resp = request.get(query_url_parsed, timeout=30)
                if resp.code == 200:
                    results = resp.json()["results"]
                    if len(results) >= 1:
                        reg_info = results[0]
                        self.code_cvm = reg_info["codeCVM"]
                        self.name = reg_info["companyName"]
                        self.cnpj = get_zero_mask(int(reg_info["cnpj"]), 14)  # fix cnpj left-zero
                        self.segment = reg_info["segment"]
                        self.market_indicator = reg_info["marketIndicator"]
                        self.bdr_type = reg_info["typeBDR"]
                        self.date_listing = reg_info["dateListing"]
            except Exception as err:
                raise Exception(f"Erro ao processar dados de registro. {err}")

            try:
                # headlines info
                query = {'agency':         self.market_indicator, 'dateInitial': '2024-05-02',
                         'dateFinal':      '2024-06-01',
                         'issuingCompany': ''.join(char for char in self.trading_code if not char.isnumeric())}
                # need convert base64
                query = base64_encode(query).decode()
                query_url_parsed = f"{self._api_config['base_api_url']}/{self._api_config['head_lines_endpoint']}/{query}"
                resp = request.get(query_url_parsed, timeout=30).json()
                for headline in resp:
                    self._head_lines.append({
                        "headline": headline["headline"],
                        "date":     headline["dateTime"],
                        "url":      headline["url"]
                    })
            except Exception as err:
                raise Exception(f"Erro ao processar dados de eventos. {err}")

    @property
    def exchange(self) -> str:
        return self._exchange

    @property
    def is_bdr(self):
        return bool(self.bdr_type)

    def __repr__(self):
        return f"{self.trading_code}(cnpj={self.cnpj}, name={self.name})"
