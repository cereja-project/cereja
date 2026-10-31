"""Header-only response metadata, independent of body framing and decoding."""

import re

_TOKEN = r"[!#$%&'*+.^_`|~0-9A-Za-z-]+"
_MEDIA_TYPE = re.compile(rf'{_TOKEN}/{_TOKEN}')
_PARAMETER = re.compile(
    rf'[ \t]*;[ \t]*(?:({_TOKEN})[ \t]*=[ \t]*({_TOKEN}|"(?:[^"\\]|\\.)*"))?[ \t]*'
)


def content_type_metadata(headers):
    """Return (media type, declared charset), with None for unusable metadata."""
    fields = headers.get_list('content-type')
    if len(fields) != 1:
        return None, None
    field = fields[0].strip(' \t')
    media_type = field.split(';', 1)[0].strip(' \t')
    if _MEDIA_TYPE.fullmatch(media_type) is None:
        return None, None
    position = field.find(';')
    charsets = []
    while position >= 0 and position < len(field):
        match = _PARAMETER.match(field, position)
        if match is None:
            return None, None
        key, value = match.groups()
        if key is not None and key.lower() == 'charset':
            if value.startswith('"'):
                value = re.sub(r'\\(.)', r'\1', value[1:-1])
            charsets.append(value)
        position = match.end()
    charset = None
    if len(charsets) == 1 and re.fullmatch(_TOKEN, charsets[0]):
        charset = charsets[0].lower()
    return media_type.lower(), charset


def content_length_metadata(headers):
    """Return the single declared non-negative byte length, or None."""
    fields = headers.get_list('content-length')
    if len(fields) != 1:
        return None
    value = fields[0].strip(' \t')
    if re.fullmatch(r'[0-9]+', value) is None:
        return None
    try:
        return int(value)
    except ValueError:
        # Respect the interpreter's integer conversion limit for huge fields.
        return None
