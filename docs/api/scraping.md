# `cereja.scraping`

```{eval-rst}
.. automodule:: cereja.scraping
```

## B3 company registration

`cereja.scraping.b3.Share` reads the B3 company registry. It does not provide
market prices. ETFs and funds may have no record in this particular registry;
a missing company record does not establish that the instrument does not exist.

```python
from cereja.scraping.b3 import Share, ShareNotFoundError, ShareDataError

try:
    with Share("PETR4") as share:
        print(share.name)
except ShareNotFoundError:
    print("No company registration available for this symbol")
except ShareDataError:
    print("The registration provider failed or returned unusable data")
```

An explicit empty `results` list raises `ShareNotFoundError` (`LookupError`).
A failed request, missing/malformed `results`, or an incomplete record raises
`ShareDataError` (`ValueError`), preserving the original cause when available.
These errors replace partially initialized objects and generic registration
exceptions. Successful registration fields remain unchanged.

`Share` closes its own HTTP client if construction fails or its context manager
exits. An injected client remains owned by the caller.

## B3 quotations and trading floor

`MarketData` queries B3's market-data endpoints independently of `Share` and
its company registry. It can query instruments such as ETFs and indices without
requiring a company registration:

```python
from cereja.scraping.b3 import MarketData, MarketDataError

try:
    with MarketData(timeout=10) as market:
        for symbol in ("WRLD11", "BOVV11", "IBOV"):
            data = market.quote(symbol)
            security = data["Trad"][0]["scty"]
            print(security["symb"], security["SctyQtn"]["curPrc"], data["Msg"]["dtTm"])
        floor = market.trading_floor()
        print(floor["TradgFlr"]["TradgFlrSts"]["desc"])
except MarketDataError:
    print("B3 market data is unavailable or unusable")
```

Both methods return the full decoded provider JSON, retaining additional fields,
timestamp strings and status codes. `quote()` trims surrounding whitespace and
uppercases input symbols; only ASCII letters and digits are accepted. It checks
that the response contains one record for the requested symbol and a finite
numeric current price. `trading_floor()` checks for a nonempty status code without
interpreting it as an open or closed session.

HTTP failures, transport/JSON errors, non-`OK` business status and malformed
responses raise `MarketDataError` (`ValueError`). Transport and JSON failures
preserve their original cause. A quotation reported as unavailable does not
establish that the instrument does not exist. Invalid input raises `TypeError`
or `ValueError` before sending a request. Calls after `close()` raise `RuntimeError`.

Use the context manager or call `close()` to release an owned HTTP client.
`MarketData(client=client)` borrows an existing `cereja.http.Client` and never
closes it. The timeout defaults to 30 seconds and is passed to each request.
Construction does not send requests; no prices are cached or persisted.

Provider endpoints:

- [Instrument quotation](https://cotacao.b3.com.br/mds/api/v1/instrumentQuotation/WRLD11)
- [Trading floor](https://cotacao.b3.com.br/mds/api/v1/TradingFloorInfo)

On 2026-10-28, direct requests returned successful quotation JSON for IBOV,
WRLD11 and BOVV11. This observation does not establish coverage for every symbol,
historical prices, a stable schema or future availability. The official
[WRLD11](https://borainvestir.b3.com.br/cotacoes/etfs/wrld11/) and
[BOVV11](https://borainvestir.b3.com.br/cotacoes/etfs/BOVV11/) pages declare a
15-minute delay, but it was not independently measured for these endpoints.
`Msg.dtTm` is retained as a message timestamp, not treated as the last trade's
time or proof of real-time data. Timestamp formats differ between the quotation
and trading-floor responses; no timezone conversion is inferred.

## Cryptocurrency spot quotations

`cereja.scraping.crypto.MarketData` reads the public
[Coinbase spot-price API](https://docs.cdp.coinbase.com/coinbase-app/track-apis/prices).
The endpoint does not require an account or API key:

```python
from decimal import Decimal
from cereja.scraping.crypto import MarketData, MarketDataError

try:
    with MarketData(timeout=10) as market:
        bitcoin = market.quote("BTC")                 # BRL by default
        ethereum = market.quote("ETH", currency="USD")
    print(bitcoin["data"]["amount"], bitcoin["data"]["currency"])
    print(Decimal(ethereum["data"]["amount"]))
except MarketDataError:
    print("The cryptocurrency quotation is unavailable or unusable")
```

`quote()` returns the full provider JSON from
`https://api.coinbase.com/v2/prices/{symbol}-{currency}/spot`. The `data.amount`
field remains a decimal string, preserving precision. Convert it with
`decimal.Decimal` for calculations. The returned currency must match the
requested currency, and the base symbol must match when the provider supplies
it. The amount must be a finite, positive decimal string.

Symbols and currency codes are trimmed and uppercased; only ASCII letters and
digits are accepted. Invalid codes raise `TypeError` or `ValueError` before any
request. HTTP errors (including unavailable pairs and rate limits), transport or
JSON errors, provider errors and invalid response data raise this module's
`MarketDataError` (`ValueError`). Transport and JSON errors retain their cause.
An unavailable pair does not establish that an asset does not exist.

The timeout defaults to 30 seconds per request. Use the context manager or
`close()` to release an owned client; `MarketData(client=client)` never closes
the caller's `cereja.http.Client`. Calls after closure raise `RuntimeError`.
No requests occur on construction. No prices are cached or persisted, and no
automatic retries are added.

The quote comes from Coinbase; supported symbols/currencies and availability
depend on that provider. BTC/BRL and ETH/USD were observed working on
2026-10-28. The response does not supply a last-trade timestamp, so this adapter
does not assert a measured delay or invent a trade time. Historical prices,
streaming updates and trading operations are outside this adapter's scope.
