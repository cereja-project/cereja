import re
from typing import Callable, Literal

catalog_of_patterns = {
    "cpf":{
        "pattern": re.compile(r"(?<![0-9])[0-9]{3}\.[0-9]{3}\.[0-9]{3}-[0-9]{2}(?![0-9])"),
        "description": "Match formatted or unformatted CPF structures using ASCII digits.",
        "format": "DDD.DDD.DDD-DD or DDDDDDDDDDD, depending on mode",
        "options": ("mode",),
        "option_values": (("mode", ("formatted", "unformatted", "both")),),
        "option_defaults": (("mode", "formatted"),),
        "examples": ("000.000.000-00", "00000000000"),
        "limitations": (
            "Does not validate check digits.",
            "Matches cannot have an ASCII digit immediately before or after them.",
            "Other surrounding characters do not restrict matches.",
        ), 
    },
    "date": {
        "pattern": re.compile(r"(?<![0-9])[0-9]{4}-[0-9]{2}-[0-9]{2}(?![0-9])"),
        "description": "Match the YYYY-MM-DD date structure.",
        "format": "YYYY-MM-DD",
        "options": (),
        "examples": ("2026-10-03", "2025-02-31"),
        "limitations": (
            "Does not validate calendar dates.",
            "Matches cannot have an ASCII digit immediately before or after them.",
            "Other surrounding characters do not restrict matches.",
        ),
    } 
}


def _number_pattern(*, decimal_separator: str = ".", grouping_separator: str | None = None, sign: str = "optional" , min_fraction_digits: int = 0 , max_fraction_digits: int | None = None) -> re.Pattern[str]:

    if decimal_separator not in (",","."):
        raise ValueError("The decimal separator must be: (, or .). Others is not supported")

    if grouping_separator not in (None, ".", ","):
        raise ValueError(("The grouping separator must be: (, or . or None). Others is not supported"))

    if grouping_separator == decimal_separator:
        raise ValueError(f"The grouping separator:{grouping_separator}, can not be the same of decimal separator: {decimal_separator}. ")

    if sign not in ("optional", "forbidden", "required"):
        raise ValueError(
            f"Unsupported sign: {sign!r}. Expected 'forbidden', 'optional', or 'required'."
        )

    if not isinstance(min_fraction_digits, int):
        raise ValueError(f"The minimum fraction digit must be an int")

    if isinstance(min_fraction_digits, bool ):
        raise ValueError(f"minimum fraction digit can not be a bool.")


    if min_fraction_digits < 0:
        raise ValueError(f"minimum fraction digit must be zero or higher.")
    

    if max_fraction_digits is not None:
        if not isinstance(max_fraction_digits, int):
            raise ValueError(f"Max fraction digits must be integers ")
        if isinstance(max_fraction_digits, bool):
            raise ValueError(f"Max fraction digit: {max_fraction_digits}, can not be a bool")
        if max_fraction_digits < 0:
            raise ValueError(f'The max fraction digit must be zero or higher')
        if max_fraction_digits < min_fraction_digits:
            raise ValueError(f'The max fraction digit must be higher or equal to minimal fraction digit')

    sign_part = sign

    _decimal_separator = re.escape(decimal_separator)

    if grouping_separator:
        grouping = re.escape(grouping_separator)



        
    if sign == "required":
        sign_part = r"[-+]"
    elif sign == "optional":
        sign_part = r"[-+]?"
    else:
        sign_part = ""

    if grouping_separator is None:
        integer_part = r'[0-9]+'

    if grouping_separator is not None:
        integer_part = rf'[0-9]{{1,3}}(?:{grouping}[0-9]{{3}})+'
        integer_part = rf"(?:{integer_part}|[0-9]+)"
 

    if max_fraction_digits == 0:
        fraction_part = ""
    else:
        minimum_digits = max(1, min_fraction_digits)
        if max_fraction_digits is None:
            fraction_digits = rf"[0-9]{{{minimum_digits},}}"
        else:
            fraction_digits = rf"[0-9]{{{minimum_digits},{max_fraction_digits}}}"

        fraction_part = rf"{_decimal_separator}{fraction_digits}"
        if min_fraction_digits == 0:
            fraction_part = rf"(?:{fraction_part})?"

    body = sign_part + integer_part + fraction_part

  
    left_boundary = r"(?<![\w.,+-])"

    right_boundary = r"(?![\w+-]|[.,]+[0-9+-])"

    return re.compile(left_boundary + body + right_boundary)

catalog_of_patterns["number"] = {
    "pattern": _number_pattern(),
    "description": "Match configurable numeric structures using ASCII digits.",
    "format": "Sign, integer digits, and an optional decimal fraction",
    "options": (
        "decimal_separator", "grouping_separator", "sign",
        "min_fraction_digits", "max_fraction_digits",
    ),
    "option_values": (
        ("decimal_separator", (".", ",")),
        ("grouping_separator", (None, ".", ",")),
        ("sign", ("forbidden", "optional", "required")),
    ),
    "option_defaults": (
        ("decimal_separator", "."),
        ("grouping_separator", None),
        ("sign", "optional"),
        ("min_fraction_digits", 0),
        ("max_fraction_digits", None),
    ),
    "examples": ("1234", "-12.34", "+0.5"),
    "limitations": (
        "Does not include currency symbols, scientific notation, or automatic format detection.",
        "The integer part is required; grouping uses blocks of three digits.",
        "Decimal and grouping separators must differ.",
        "Fraction limits must be non-negative integers, excluding booleans; maximum may be None.",
        "Maximum fraction digits cannot be less than the minimum.",
        "A present decimal separator must be followed by at least one digit.",
        "Matches cannot start beside word characters, signs, dots, or commas.",
        "Matches cannot end beside word characters, signs, or dots/commas followed by digits or signs.",
        "Trailing dots and commas without digits or signs are treated as punctuation.",
    ),
}



def preset(name: str, **options: object) -> re.Pattern[str]:
    """Return the compiled pattern for a named catalog preset.

    Args:
        name: Catalog key: "cpf", "date", or "number".
        **options: CPF accepts mode="formatted" (default), "unformatted",
            or "both". The date preset does not support options. Numbers
            accept decimal_separator, grouping_separator, sign,
            min_fraction_digits, and max_fraction_digits.

    Returns:
        A compiled pattern that can be passed to search(). The CPF preset
        matches DDD.DDD.DDD-DD, eleven unformatted digits, or either complete
        structure according to mode. The date preset matches YYYY-MM-DD.
        The number preset matches the configured numeric structure.
        All presets use ASCII digits.

    Raises:
        ValueError: If the name or an option name/value is unsupported.

    These presets match formats only; they do not validate CPF check digits
    or calendar dates. For CPF and date, an ASCII digit immediately before
    or after a match prevents it from matching; other surrounding characters
    do not restrict it. Number boundaries and constraints are described by
    inspect_preset("number").
    """
   
    preset_search = catalog_of_patterns.get(name)
    if preset_search is None:
        raise ValueError(f"Unsupported preset: {name!r}")

    unsupported_options = set(options) - set(preset_search["options"])
    if unsupported_options:
        raise ValueError(
            f"Unsupported options for {name!r}: {sorted(unsupported_options)}"
        )

    if name == "number":
        if not options:
            return preset_search["pattern"]
        return _number_pattern(**options)

    if name == "cpf":
        mode = options.get("mode", "formatted")
        if mode not in ("formatted", "unformatted", "both"):
            raise ValueError(f"Unsupported CPF mode: {mode!r}")

        if mode == "formatted":
            return preset_search["pattern"]

        unformatted = r"[0-9]{11}"
        if mode == "unformatted":
            body = unformatted
        else:
            formatted = r"[0-9]{3}\.[0-9]{3}\.[0-9]{3}-[0-9]{2}"
            body = f"(?:{formatted}|{unformatted})"

        return re.compile(r"(?<![0-9])" + body + r"(?![0-9])")

    return preset_search["pattern"]
    
       
    


def search(text: str, pattern: re.Pattern[str]) -> re.Match[str] | None:
    """Find the first match of a compiled pattern in the original text.

    Args:
        text: Text to search without preprocessing.
        pattern: Compiled pattern obtained from preset() or re.compile().

    Returns:
        A re.Match object, or None if no match is found. group() returns the
        matched text; span() returns zero-based positions in the original text,
        with an inclusive start and an exclusive end.

    The search uses the supplied pattern directly, including its flags and
    groups, without consulting the preset catalog.
    """

    search_match = re.search(pattern, text)
    return search_match
        
def list_presets() -> list[str]:
    """Return available preset names in alphabetical order as a new list.

    Modifying the returned list does not change the catalog.
    """
    new_list = []

    for presets in catalog_of_patterns:
        new_list.append(presets)
        new_list.sort(reverse=False)

    return new_list

def inspect_preset(name: str) -> dict:
    """Return descriptive metadata for a named preset.

    Args:
        name: Name of a preset in the catalog.

    Returns:
        A new dictionary containing name, description, format, options,
        examples, and limitations, without the compiled pattern. Configurable
        presets also include option_values and option_defaults as tuples of
        option/value pairs. The current metadata consists of strings and
        recursively immutable tuples; changing
        the returned dictionary does not change the catalog.

    Raises:
        ValueError: If the preset name is unknown.
    """
    preset_search = catalog_of_patterns.get(name)

    presets_info_dict = {}

    if preset_search is None:
            raise ValueError(f"The Preset: {name} is not a valid preset.")
    
    if preset_search:
        for key, value in preset_search.items():
            presets_info_dict.update({key:value})
        presets_info_dict.pop("pattern")
        presets_info_dict.update({'name':name})
    return presets_info_dict
   
def extract(text:str, pattern: re.Pattern[str]) -> list[re.Match[str]]:
    """Return all non-overlapping matches in their original text order.

    Args:
        text: Text to search without preprocessing.
        pattern: Compiled pattern obtained from preset() or re.compile().

    Returns:
        A list of re.Match objects, or an empty list if nothing matches.
        Each match retains its groups and zero-based positions in the original
        text, with an inclusive start and an exclusive end. Empty matches
        follow the behavior of re.finditer().
    """
    list_of_matches = []
    for match in re.finditer(pattern,text):
        list_of_matches.append(match)

    return list_of_matches

def regex_replace(text: str, pattern: re.Pattern[str], replacement: str | Callable[[re.Match[str]], str], *, count: int = 0) -> str:
    """Replace pattern matches using re.sub semantics.

    Args:
        text: Original text.
        pattern: Compiled pattern obtained from preset() or re.compile().
        replacement: Replacement string supporting regex backreferences, or
            a callable receiving each re.Match and returning a string.
        count: Keyword-only replacement limit. Zero replaces all matches;
            a positive integer replaces at most that many matches.

    Returns:
        The resulting string, or text unchanged if nothing matches.

    Raises:
        ValueError: If count is negative.

    This function performs regex substitution. DataStringIterator.replace
    retains its separate literal replacement behavior and iterator return type.
    """
    if count < 0:
        raise ValueError(f"The count can not be less than zero")
    
    result = re.sub(string=text, pattern=pattern, repl=replacement, count=count)
    

    return result


