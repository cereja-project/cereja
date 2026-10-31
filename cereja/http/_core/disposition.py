"""Conservative extraction of advisory HTTP response filenames."""

import re
import unicodedata
from urllib.parse import unquote_to_bytes

_TOKEN = r"[!#$%&'*+.^_`|~0-9A-Za-z-]+"
_PARAMETER = re.compile(
    rf'[ \t]*;[ \t]*({_TOKEN})[ \t]*=[ \t]*({_TOKEN}|"(?:[^"\\]|\\.)*")[ \t]*'
)
_RESERVED = frozenset({"CON", "PRN", "AUX", "NUL", "CLOCK$", "CONIN$", "CONOUT$"})


def _basename(value):
    name = value.replace("\\", "/").rsplit("/", 1)[-1].strip()
    if not name or name in {".", "..", "~"} or name.endswith("."):
        return None
    if any(char in '<>:"|?*' or unicodedata.category(char).startswith("C") for char in name):
        return None
    stem = name.split(".", 1)[0].rstrip().upper()
    if stem in _RESERVED or re.fullmatch(r"(?:COM|LPT)[1-9\u00b9\u00b2\u00b3]", stem):
        return None
    return name


def _extended_filename(value):
    parts = value.split("'", 2)
    if len(parts) != 3:
        return None
    charset, language, encoded = parts
    if charset.lower() not in {"utf-8", "iso-8859-1"}:
        return None
    if not re.fullmatch(r"[A-Za-z0-9-]*", language):
        return None
    if not re.fullmatch(r"(?:[A-Za-z0-9!#$&+.^_`|~-]|%[0-9A-Fa-f]{2})*", encoded):
        return None
    try:
        return _basename(unquote_to_bytes(encoded).decode(charset))
    except UnicodeError:
        return None


def response_filename(headers):
    """Return a usable Content-Disposition basename, or None.

    Prefer RFC 5987 filename* over filename. Ignore ambiguous or malformed
    fields and never infer a filename from the URL or read response body bytes.
    The returned name remains advisory, not a guarantee of filesystem validity.
    """
    fields = headers.get_list("content-disposition")
    if len(fields) != 1:
        return None
    field = fields[0]
    disposition = field.split(";", 1)[0].strip(" \t")
    if not re.fullmatch(_TOKEN, disposition):
        return None
    position = field.find(";")
    if position < 0:
        return None
    parameters = {}
    while position < len(field):
        match = _PARAMETER.match(field, position)
        if match is None:
            return None
        key, value = match.groups()
        key = key.lower()
        if key in parameters:
            return None
        parameters[key] = value
        position = match.end()
    extended = parameters.get("filename*")
    if extended is not None:
        name = _extended_filename(extended)
        if name is not None:
            return name
    plain = parameters.get("filename")
    if plain is None:
        return None
    if plain.startswith('"'):
        plain = re.sub(r"\\(.)", r"\1", plain[1:-1])
    return _basename(plain)
