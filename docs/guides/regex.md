# Regex Presets

Use `cereja.utils.regex` to recognize common text formats and work with Python's
regular expression match objects. The same module is available as `cj.regex`:

```python
import cereja as cj
from cereja.utils import regex

assert cj.regex is regex
assert regex.list_presets() == ["cpf", "date", "number"]
```

`preset(name, **options)` returns a compiled `re.Pattern[str]`. Unknown preset
names, unsupported options, and invalid option values raise `ValueError`.
`inspect_preset(name)` returns a new metadata dictionary with examples, options,
defaults where applicable, and limitations; it does not expose the pattern.

## Search and Extract

`search(text, pattern)` returns the first `re.Match`, or `None`. Matches retain
their positions in the original text. `extract(text, pattern)` returns a list of
non-overlapping matches in text order, or `[]` when nothing matches.

```python
from cereja.utils import regex

pattern = regex.preset("date")
text = "Dates: 2026-10-03 and 2026-10-04."
match = regex.search(text, pattern)
assert match.group() == "2026-10-03"
assert match.span() == (7, 17)
assert [m.group() for m in regex.extract(text, pattern)] == [
    "2026-10-03", "2026-10-04",
]
assert regex.search("No dates here", pattern) is None
assert regex.extract("No dates here", pattern) == []
```

These helpers also accept patterns created with `re.compile`, preserving their
flags and groups. They do not preprocess text or convert matches into numbers.

## CPF and Dates

CPF supports `mode="formatted"` (the default), `"unformatted"`, or `"both"`.
Dates support only `YYYY-MM-DD` and have no configurable options.

```python
from cereja.utils import regex

assert regex.preset("cpf").fullmatch("000.000.000-00")
assert regex.preset("cpf", mode="unformatted").fullmatch("00000000000")
assert [m.group() for m in regex.extract(
    "000.000.000-00; 00000000000", regex.preset("cpf", mode="both"),
)] == ["000.000.000-00", "00000000000"]
assert regex.preset("date").fullmatch("2025-02-31")
```

Both presets recognize **format only**. CPF does not validate check digits;
dates do not validate calendar dates. Both use ASCII digits. An ASCII digit
immediately before or after the format prevents a match; other surrounding
characters do not restrict these two presets.

## Configurable Numbers

The integer part is required. Numbers use ASCII digits and recognize a format;
they do not parse or normalize the matched value.

| Option | Default | Accepted values |
| --- | --- | --- |
| `decimal_separator` | `"."` | `"."` or `","` |
| `grouping_separator` | `None` | `None`, `"."`, or `","`; must differ from the decimal separator |
| `sign` | `"optional"` | `"forbidden"`, `"optional"`, or `"required"` |
| `min_fraction_digits` | `0` | Non-negative integer, excluding booleans |
| `max_fraction_digits` | `None` | `None` or a non-negative integer, excluding booleans; at least the minimum |

With grouping enabled, the first block contains one to three digits, followed
by one or more blocks of exactly three digits. Plain integers remain accepted.
A minimum of zero makes the fraction optional. If a fraction is present, its
separator must be followed by at least one digit. A maximum of zero disables
fractions; `None` leaves their length unlimited. Equal positive limits require
exactly that many fraction digits.

```python
from cereja.utils import regex

assert regex.preset("number").fullmatch("-1234.56")
pattern = regex.preset(
    "number", decimal_separator=",", grouping_separator=".",
    min_fraction_digits=2, max_fraction_digits=2,
)
assert pattern.fullmatch("-1.234,56")
assert pattern.fullmatch("1234,56")
assert regex.search("1.234,5", pattern) is None
assert regex.search("1.234,567", pattern) is None
assert regex.preset("number", sign="required").fullmatch("+12")
assert regex.search("12", regex.preset("number", sign="required")) is None
assert regex.search("-12", regex.preset("number", sign="forbidden")) is None
```

Numbers cannot start immediately after word characters (including letters,
Unicode digits, and underscores), signs, dots, or commas. They cannot end
immediately before word characters or signs. Dots or commas followed by digits or signs
continue the numeric token, preventing partial matches of malformed formats.
Trailing dots or commas without digits or signs are treated as punctuation.

```python
from cereja.utils import regex

pattern = regex.preset("number")
assert [m.group() for m in regex.extract("Values: (123), -7.8!", pattern)] == [
    "123", "-7.8",
]
for text in ("12,34", "1.2.3", ".5", "++12", "abc123", "1e3"):
    assert regex.search(text, pattern) is None
```

There is no automatic format detection or support for scientific notation.
Currency symbols are not part of a match; the preset does not interpret them.
For whole-string format checks, use `pattern.fullmatch(text)`; search and extract
find numbers within a larger text according to the boundaries above.

## Regex Replacement

`regex_replace(text, pattern, replacement, *, count=0)` returns a string and
supports backreferences or a callable receiving each match. Zero replaces all
matches; a positive count limits replacements. Negative counts raise `ValueError`.

```python
from cereja.utils import regex

pattern = regex.preset("number")
assert regex.regex_replace("12 and 3", pattern, r"[\g<0>]", count=1) == "[12] and 3"
assert regex.regex_replace(
    "12 and 3", pattern, lambda m: str(int(m.group()) * 2),
) == "24 and 6"
```

`DataStringIterator.replace(old, new)` retains literal substring replacement
and returns a new iterator. It does not interpret regex patterns or replacement
backreferences. Use `regex_replace` when regex substitution is intended.

## Custom Patterns

Use the same operations with a compiled custom pattern. Its flags, groups,
and boundaries retain normal Python `re` behavior.

```python
import re
from cereja.utils import regex

custom = re.compile(r"\b(?P<prefix>[A-Z]{2})-(?P<digits>[0-9]{3})\b")
text = "AA-007 BB-042"
assert regex.search(text, custom).span() == (0, 6)
assert [(m.group(), m.span()) for m in regex.extract(text, custom)] == [
    ("AA-007", (0, 6)), ("BB-042", (7, 13)),
]
assert regex.regex_replace(text, custom, r"\g<digits>/\g<prefix>", count=1) == "007/AA BB-042"
assert regex.regex_replace(text, custom, lambda m: m.group().lower()) == "aa-007 bb-042"
assert regex.search("no match", custom) is None
assert regex.extract("no match", custom) == []
assert regex.regex_replace("no match", custom, "X") == "no match"
```

## Accepted and Rejected Formats

These examples describe search/extraction behavior, not semantic validation.
The configured number rows use decimal `"."`, grouping `","`, optional signs,
and exactly two fraction digits.

| Preset/configuration | Accepted | Rejected without partial matches |
| --- | --- | --- |
| Configured number | `-1,234.50`, `7.00`, `1234.50` | `1,23.45`, `1.234`, `--12.34`, `12.34,+56.78` |
| Default number beside punctuation | `(123), -7.8!` | `.5`, `1.2.3`, `abc123` |
| CPF, formatted | `000.000.000-00` | `00000000000`, `000.000-000.00`, `1000.000.000-00` |
| CPF, unformatted | `00000000000` | `000.000.000-00`, `100000000000` |
| CPF, both | `000.000.000-00`, `00000000000` | `000.000-000.00`, `100000000000` |
| Date | `2026-10-03`, `2025-02-31` | `2026/10/03`, `2026-1-03`, `12026-10-03` |
