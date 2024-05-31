from .._requests import request
from ..hashtools import base64_encode
from ..utils import get_zero_mask

__all__ = ["CompanyDetails", "compay_details"]
B3_COMPANY_DETAILS_ENDPOINT = "https://sistemaswebb3-listados.b3.com.br/listedCompaniesProxy/CompanyCall" \
                              "/GetInitialCompanies"


class CompanyDetails:
    def __init__(self, name, cnpj, company_code, code_cvm, segment):
        self.name = name
        self.cnpj = cnpj
        self.company_code = company_code
        self.code_cvm = code_cvm
        self.segment = segment

    @classmethod
    def load_from_b3(cls, company_code: str):
        details = _parse_b3_response(compay_details(company_code.upper()))
        return cls(company_code=company_code.upper(), **details)

    def __repr__(self):
        return f"{self.company_code}(cnpj={self.cnpj}, name={self.name})"


def _parse_b3_response(response):
    results = response.get("results")
    if results:
        for details in results:
            return {"code_cvm": details["codeCVM"],
                    "name":     details["companyName"],
                    "cnpj":     get_zero_mask(int(details["cnpj"]), 14),  # fix cnpj left-zero
                    "segment":  details["segment"]}


def _parse_url_query(company_code: str):
    query_base64_str = base64_encode(
            {"language": "pt-br", "pageNumber": 1, "pageSize": 20, "company": company_code}).decode()
    return f"{B3_COMPANY_DETAILS_ENDPOINT}/{query_base64_str}"


def compay_details(company_code) -> dict:
    return request.get(_parse_url_query(company_code=company_code), timeout=30).json()
