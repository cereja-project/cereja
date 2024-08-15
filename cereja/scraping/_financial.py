from ..utils import camel_to_snake
try:
    from .b3 import Share
except ImportError:
    # noinspection PyUnresolvedReferences
    Share = None
__all__ = ["FinancialData"]


def _parse_keys_to_snake(obj: dict):
    if isinstance(obj, dict):
        return {camel_to_snake(k): v for k, v in obj.items()}
    return obj


class FinancialResult:
    def __init__(self, describle, value, value2='-'):
        self.describle = describle
        self.value = value
        self.value2 = value2

    def __repr__(self):
        return f"FinancialResult(describle={self.describle}, value={self.value}, value2={self.value2})"


class FinancialResultShareholders:
    def __init__(self, describle, on, pn, total):
        self.describle = describle
        self.on = on
        self.pn = pn
        self.total = total

    def __repr__(self):
        return f"FinancialResultShareholders(describle={self.describle}, on={self.on}, pn={self.pn}, total={self.total})"


class FinancialStatement:
    def __init__(self, title, date_inicial, date_final, results):
        self.title = title
        self.date_inicial = date_inicial
        self.date_final = date_final
        self.results = [FinancialResult(**result) for result in results]

    def __repr__(self):
        return f"FinancialStatement(title={self.title}, date_inicial={self.date_inicial}, date_final={self.date_final}, results={self.results})"


class FreeFloatResult:
    def __init__(self, title, describle, quantity, perc, results):
        self.title = title
        self.describle = describle
        self.quantity = quantity
        self.perc = perc
        self.results = [FinancialResult(**result) for result in results]

    def __repr__(self):
        return f"FreeFloatResult(title={self.title}, describle={self.describle}, quantity={self.quantity}, perc={self.perc}, results={self.results})"


class ShareholderPosition:
    def __init__(self, information_received, name, on, pn, total, results):
        self.information_received = information_received
        self.name = name
        self.on = on
        self.pn = pn
        self.total = total
        self.results = [FinancialResultShareholders(**result) for result in results]

    def __repr__(self):
        return f"ShareholderPosition(information_received={self.information_received}, name={self.name}, on={self.on}, pn={self.pn}, total={self.total}, results={self.results})"


class CapitalStockComposition:
    def __init__(self, title, results):
        self.title = title
        self.results = [FinancialResult(**result) for result in results]

    def __repr__(self):
        return f"CapitalStockComposition(title={self.title}, results={self.results})"


class FinancialData:
    def __init__(self, share: "Share", title_initial, consolidated, unconsolidated, free_float_result,
                 position_shareholders,
                 outstanding_shares, capital_stock_composition):
        self._share = share
        self.title_initial = title_initial
        self.consolidated = [FinancialStatement(**_parse_keys_to_snake(statement)) for statement in consolidated]
        self.unconsolidated = [FinancialStatement(**_parse_keys_to_snake(statement)) for statement in unconsolidated]
        self.free_float_result = FreeFloatResult(**_parse_keys_to_snake(free_float_result))
        self.position_shareholders = ShareholderPosition(**_parse_keys_to_snake(position_shareholders))
        self.outstanding_shares = _parse_keys_to_snake(outstanding_shares)
        self.capital_stock_composition = CapitalStockComposition(**_parse_keys_to_snake(capital_stock_composition))

    @property
    def share(self):
        return self._share

    def __repr__(self):
        return f"FinancialData({self._share.name})"
