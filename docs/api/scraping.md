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
