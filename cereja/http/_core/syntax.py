"""Small HTTP syntax primitives shared by request preparation."""

TOKEN_CHARS = frozenset(
    "!#$%&'*+-.^_`|~0123456789abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ"
)


def validate_token(value, *, label):
    text = str(value)
    if not text or any(char not in TOKEN_CHARS for char in text):
        raise ValueError(f"Invalid HTTP {label}: {text!r}")
    return text
