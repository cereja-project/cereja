"""Legacy terminal capability flag without writing an import-time banner."""

import sys as _sys


def _supports_non_bmp(stream) -> bool:
    if stream is None:
        return False
    # StringIO and other text-only streams commonly have no encoding attribute.
    encoding = getattr(stream, "encoding", None) or "utf-8"
    try:
        "\U0001F352".encode(encoding, errors="strict")
    except (UnicodeError, LookupError):
        return False
    return True


NON_BMP_SUPPORTED = _supports_non_bmp(_sys.stdout)
