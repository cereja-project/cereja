import re
import unittest
from cereja.utils.regex import search, preset, list_presets, inspect_preset, extract, regex_replace

class TestRegexSearch(unittest.TestCase):
    """Verify preset resolution and searches with preset and custom patterns."""

    def test_search_finds_date(self):
        """Find a YYYY-MM-DD date in a sentence and preserve its positions."""
        pattern = preset("date")
        result = search(text="Entrega: 2026-10-03.", pattern=pattern)

        self.assertIsInstance(result, re.Match)
        self.assertEqual(result.group(), "2026-10-03")
        self.assertEqual(result.span(), (9, 19))

    def test_search_finds_cpf(self):
        """Verify the matched text and positions for a formatted CPF."""
        pattern = preset("cpf")
        result = search(text="000.000.000-00", pattern=pattern)
        self.assertIsInstance(result, re.Match)
        self.assertEqual(result.group(), "000.000.000-00")
        self.assertEqual(result.span(), (0, 14))

    def test_search_non_match_text(self):
        """Return None when the text has no match for the resolved date pattern."""
        pattern = preset("date")
        result = search(text="No date given", pattern=pattern)
        self.assertIsNone(result)

    def test_search_unknow_preset(self):
        """Reject an unknown name when resolving a preset."""
        
        with self.assertRaises(ValueError):
            preset("inexistente")

    def test_return_preset_pattern(self):
        """Return a compiled regex pattern when resolving the date preset."""
        pattern = preset("date")

        self.assertIsInstance(pattern, re.Pattern )

    def test_custom_pattern(self):
        """Search with a custom compiled pattern and preserve match positions."""
        custom_pattern = re.compile(r"hello")
        result = search(text="Say hello!", pattern=custom_pattern)
        self.assertIsInstance(custom_pattern, re.Pattern)
        self.assertEqual(result.group(), "hello")
        self.assertEqual(result.span(), (4,9))
        
    def test_custom_options(self):
        """Reject an unsupported option for the known date preset."""
        
        with self.assertRaises(ValueError):
            preset("date",number=True)

    def test_list_presets(self):

        # list_of_presets = list_presets()
        # self.assertEqual(["cpf","date"], list_of_presets)

        list_of_presets = list_presets()
        list_of_presets.clear()
        list_of_presets = list_presets()
        self.assertEqual(["cpf", "date", "number"], list_of_presets)

    def test_inspect_presets(self):
        result = inspect_preset("cpf")

        self.assertIsInstance(result, dict)
        self.assertEqual(result['name'], "cpf")
        self.assertEqual(result['format'], "DDD.DDD.DDD-DD or DDDDDDDDDDD, depending on mode")
        self.assertEqual(result["options"], ("mode",))
        self.assertEqual(
            result["option_values"],
            (("mode", ("formatted", "unformatted", "both")),),
        )
        self.assertEqual(result["option_defaults"], (("mode", "formatted"),))
        self.assertEqual(result["examples"], ("000.000.000-00", "00000000000"))
        self.assertNotIn(member='pattern', container=result)

    def test_inspect_unknown_preset(self):
        """Reject an unknown name when inspecting a preset."""
        with self.assertRaises(ValueError):
            inspect_preset("inexistente")

    def test_inspect_result_does_not_change_catalog(self):
        """Keep catalog metadata unchanged when a caller modifies the result."""
        result = inspect_preset("cpf")
        result["description"] = "changed by the caller."

        fresh_result = inspect_preset("cpf")
        self.assertEqual(
            fresh_result["description"],
            "Match formatted or unformatted CPF structures using ASCII digits.",
        )

    def test_extract_data(self):
        result = extract(text="2026-10-03 e 2026-10-04", pattern=preset("date"))

        self.assertIsInstance(result, list)
        self.assertEqual(len(result), 2)

        self.assertEqual(result[0].group(), "2026-10-03")
        self.assertEqual(result[1].group(), "2026-10-04")
        self.assertEqual(result[0].span(), (0,10))
        self.assertEqual(result[1].span(), (13,23))

    def test_extract_no_match(self):
        result = extract(text="No date informed", pattern=preset("date"))

        self.assertEqual(result, [])

    def test_extract_data_with_custom_pattern(self):
        result = extract(text="Hello e Hello", pattern=re.compile("Hello"))

        self.assertIsInstance(result, list)
        
        self.assertEqual(result[0].group(), "Hello")
        self.assertEqual(result[1].group(), "Hello")

        self.assertEqual(result[0].span(), (0,5))
        self.assertEqual(result[1].span(), (8,13))

    def test_regex_replace(self):
        result = regex_replace("Hello e Hello", pattern=re.compile("Hello"), replacement="oi")

        self.assertEqual(result, "oi e oi")

    def test_regex_replace_with_limit(self):
        result = regex_replace("Hello e Hello", pattern=re.compile("Hello"), replacement="oi", count=1)

        self.assertEqual(result, "oi e Hello")

    def test_regex_replace_without_match(self):
        result = regex_replace("Sem correspondencia", pattern=re.compile("Hello"), replacement= "oi")

        self.assertEqual(result, "Sem correspondencia")

    def test_regex_replace_with_negative_limit(self):

        with self.assertRaises(ValueError):
            regex_replace("Hello e Hello", pattern=re.compile("Hello"), replacement="oi", count=-1)

    def test_regex_replace_preset(self):
        result = regex_replace(text="Entrega: 2026-10-03.", pattern=re.compile(preset("date")), replacement="<date>")

        self.assertEqual(result, "Entrega: <date>.")

    def test_regex_replace_backreference(self):
        result = regex_replace(text="hello", pattern=re.compile(r"(?P<word>hello)"),replacement=r"<\g<word>>")

        self.assertEqual(result, "<hello>")

    def test_regex_replace_callable(self):
        def replacement(match) -> str:
            return match.group().upper()

        result = regex_replace(text="hello e hello", pattern=re.compile("hello"), replacement=replacement)

        self.assertEqual(result, "HELLO e HELLO")

    def test_regex_limit_cpf(self):
        result = preset("cpf")

        search_result = search("CPF: 000.000.000-00.", pattern=result)

        self.assertIsInstance(search_result, re.Match)
        assert search_result is not None
        self.assertEqual(search_result.group(), "000.000.000-00")
        
    def test_regex_limit_cpf_with_parentesis(self):
        result = preset("cpf")

        search_result = search("(000.000.000-00)", pattern=result)

        self.assertIsInstance(search_result, re.Match)
        assert search_result is not None
        self.assertEqual(search_result.group(), "000.000.000-00")

    def test_cpf_rejects_extra_leading_digit(self):
        result = preset("cpf")
        search_result = search(text="(1000.000.000-00)", pattern=result)

        self.assertIsNone(search_result, msg="The text is not supported to start with a four digits")
           
    def test_cpf_rejects_extra_trailing_digit(self):
        result = preset("cpf")
        search_result = search(text="(000.000.000-001)", pattern=result)
        
        self.assertIsNone(search_result, msg="The text is not supported to finish with a three digits ")

    def test_cpf_rejects_mixed_punctuation(self):
        result = preset("cpf")
        search_result = search(text="(000.000-000.00)", pattern=result)
        
        self.assertIsNone(search_result, msg="The text is not on a correct formatation.")

    def test_cpf_rejects_unformatted_input_in_formatted_mode(self):
        result = preset("cpf")
        search_result = search(text="(00000000000)", pattern=result)
        
        self.assertIsNone(search_result, msg="The text is not on a correct formatation.")

    def test_date_matches_invalid_calendar_date(self):
        result = preset("date")
        search_result = search(text="Entrega: 2025-02-31.", pattern=result)
        self.assertIsInstance(search_result, re.Match)
        self.assertEqual(search_result.group(), "2025-02-31")

    def test_date_rejects_slash_separators(self):
        result = preset("date")
        search_result = search(text="2026/10/03", pattern=result)
        self.assertIsNone(search_result)

    def test_date_rejects_single_digit_month(self):
        result = preset("date")
        search_result = search(text="2026-1-03", pattern=result)
        self.assertIsNone(search_result)  

    def test_date_rejects_extra_leading_digit(self):
        result = preset("date")
        search_result = search(text="12026-10-03", pattern=result)

        self.assertIsNone(search_result,msg="The text is not supported to start with a five digits") 

    def test_date_rejects_extra_trailing_digit(self):
        result = preset("date")
        search_result = search(text="2026-10-031", pattern=result)

        self.assertIsNone(search_result,msg="The text is not supported to end with a three digits")

    def test_cpf_modes_select_complete_formats(self):
        """Select the documented format without accepting the other mode."""
        cases = (
            ("formatted", "000.000.000-00", True),
            ("formatted", "00000000000", False),
            ("unformatted", "000.000.000-00", False),
            ("unformatted", "00000000000", True),
            ("both", "000.000.000-00", True),
            ("both", "00000000000", True),
        )
        for mode, identifier, accepted in cases:
            with self.subTest(mode=mode, identifier=identifier):
                text = f"CPF: ({identifier})."
                result = search(text, preset("cpf", mode=mode))
                if accepted:
                    self.assertIsInstance(result, re.Match)
                    assert result is not None
                    self.assertEqual(result.group(), identifier)
                    self.assertEqual(result.span(), (6, 6 + len(identifier)))
                else:
                    self.assertIsNone(result)

    def test_cpf_modes_reject_malformed_identifiers(self):
        """Reject extra digits and mixed punctuation in every CPF mode."""
        for mode in ("formatted", "unformatted", "both"):
            for text in (
                "1000.000.000-00", "000.000.000-001",
                "100000000000", "000000000001",
                "000.000-000.00", "000.000.00000",
            ):
                with self.subTest(mode=mode, text=text):
                    self.assertIsNone(search(text, preset("cpf", mode=mode)))

    def test_cpf_rejects_invalid_modes(self):
        """Reject unsupported mode values with ValueError."""
        for mode in ("invalid", "", None, 1, ["formatted"]):
            with self.subTest(mode=mode):
                with self.assertRaises(ValueError):
                    preset("cpf", mode=mode)

    def test_cpf_rejects_unknown_options_with_valid_mode(self):
        """Do not silently ignore unknown options alongside a supported mode."""
        with self.assertRaises(ValueError):
            preset("cpf", mode="both", unknown_option=True)

    def test_extract_date_preset_rejects_partial_matches(self):
        """Extract complete dates while skipping dates beside extra digits."""
        text = "12026-10-03; 2026-10-031; 2025-02-31."
        result = extract(text, preset("date"))
        self.assertEqual(len(result), 1)
        self.assertEqual(result[0].group(), "2025-02-31")
        self.assertEqual(result[0].span(), (26, 36))


class TestNumberPreset(unittest.TestCase):
    def test_default_numbers(self):
        pattern = preset("number")
        self.assertIsInstance(pattern, re.Pattern)
        for text in ("0", "1234", "+12", "-12.34", "0.12345"):
            with self.subTest(text=text):
                self.assertIsNotNone(pattern.fullmatch(text))

    def test_grouped_and_plain_numbers(self):
        cases = (
            ({"grouping_separator": ","},
             ("1234", "1,234", "12,345,678", "-1,234.56")),
            ({"decimal_separator": ",", "grouping_separator": "."},
             ("1234", "1.234", "-1.234,56")),
        )
        for options, numbers in cases:
            pattern = preset("number", **options)
            for text in numbers:
                with self.subTest(options=options, text=text):
                    self.assertIsNotNone(pattern.fullmatch(text))

    def test_malformed_numbers_are_not_partially_matched(self):
        cases = (
            ({}, (".5", "1,234", "12,34", "1.2.3", "1..23", "1,,23")),
            ({"grouping_separator": ","},
             ("12,34", "1234,567", "1,2345", "1,234,56", "1,,234")),
            ({"decimal_separator": ",", "grouping_separator": "."},
             ("12.34", "1.234,5,6")),
        )
        for options, numbers in cases:
            pattern = preset("number", **options)
            for text in numbers:
                with self.subTest(options=options, text=text):
                    self.assertIsNone(search(text, pattern))
                    self.assertEqual(extract(text, pattern), [])

    def test_sign_modes(self):
        cases = (
            ("optional", ("123", "+123", "-123"), ()),
            ("required", ("+123", "-123"), ("123",)),
            ("forbidden", ("123",), ("+123", "-123")),
        )
        for sign, accepted, rejected in cases:
            pattern = preset("number", sign=sign)
            for text in accepted:
                with self.subTest(sign=sign, text=text):
                    self.assertIsNotNone(pattern.fullmatch(text))
            for text in rejected + ("++123", "--123", "+-123", "-+123"):
                with self.subTest(sign=sign, text=text):
                    self.assertIsNone(search(text, pattern))

    def test_separators_before_signs_do_not_allow_partial_matches(self):
        configurations = (
            {},
            {"grouping_separator": ",", "min_fraction_digits": 2, "max_fraction_digits": 2},
        )
        for options in configurations:
            pattern = preset("number", **options)
            for text in ("12.34,+56.78", "12.34.-56.78", "12.34,++56.78", "12.34,+"):
                with self.subTest(options=options, text=text):
                    self.assertIsNone(search(text, pattern))
                    self.assertEqual(extract(text, pattern), [])
                    self.assertEqual(regex_replace(text, pattern, "X"), text)

    def test_fraction_limits(self):
        cases = (
            (0, None, ("123", "123.4", "123.4567"), ()),
            (0, 0, ("123",), ("123.4",)),
            (0, 2, ("123", "123.4", "123.45"), ("123.456",)),
            (2, 2, ("123.45",), ("123", "123.4", "123.456")),
            (2, None, ("123.45", "123.4567"), ("123", "123.4")),
            (1, 3, ("123.4", "123.45", "123.456"), ("123", "123.4567")),
        )
        for minimum, maximum, accepted, rejected in cases:
            pattern = preset(
                "number", min_fraction_digits=minimum, max_fraction_digits=maximum,
            )
            for text in accepted:
                with self.subTest(minimum=minimum, maximum=maximum, text=text):
                    self.assertIsNotNone(pattern.fullmatch(text))
            for text in rejected:
                with self.subTest(minimum=minimum, maximum=maximum, text=text):
                    self.assertIsNone(search(text, pattern))

    def test_fraction_limits_with_comma(self):
        pattern = preset(
            "number", decimal_separator=",", grouping_separator=".",
            min_fraction_digits=2, max_fraction_digits=2,
        )
        self.assertIsNotNone(pattern.fullmatch("-1.234,56"))
        for text in ("1.234", "1.234,5", "1.234,567"):
            with self.subTest(text=text):
                self.assertIsNone(search(text, pattern))

    def test_common_punctuation_and_match_positions(self):
        text = "Valor: (123), -7.8! 456..."
        matches = extract(text, preset("number"))
        self.assertEqual([m.group() for m in matches], ["123", "-7.8", "456"])
        self.assertEqual([m.span() for m in matches], [(8, 11), (14, 18), (20, 23)])
        self.assertEqual(search(text, preset("number")).span(), (8, 11))

    def test_ascii_digits_and_word_boundaries(self):
        for text in ("１２３", "١٢٣", "abc123", "123abc", "x_123", "123_", "1e3", "1e+3"):
            with self.subTest(text=text):
                self.assertIsNone(search(text, preset("number")))

    def test_invalid_options(self):
        invalid = (
            {"decimal_separator": ";"}, {"decimal_separator": None},
            {"grouping_separator": ";"},
            {"grouping_separator": "."},
            {"decimal_separator": ",", "grouping_separator": ","},
            {"sign": "invalid"}, {"sign": None}, {"sign": ["optional"]},
            {"min_fraction_digits": True}, {"min_fraction_digits": False},
            {"min_fraction_digits": -1}, {"min_fraction_digits": 1.0},
            {"min_fraction_digits": "1"}, {"min_fraction_digits": None},
            {"max_fraction_digits": True}, {"max_fraction_digits": False},
            {"max_fraction_digits": -1}, {"max_fraction_digits": 1.0},
            {"max_fraction_digits": "1"},
            {"min_fraction_digits": 2, "max_fraction_digits": 1},
            {"unknown_option": True}, {"sign": "required", "unknown_option": True},
        )
        for options in invalid:
            with self.subTest(options=options):
                with self.assertRaises(ValueError):
                    preset("number", **options)

    def test_number_metadata_and_defaults(self):
        info = inspect_preset("number")
        defaults = dict(info["option_defaults"])
        self.assertEqual(info["name"], "number")
        self.assertEqual(info["options"], (
            "decimal_separator", "grouping_separator", "sign",
            "min_fraction_digits", "max_fraction_digits",
        ))
        self.assertEqual(defaults, {
            "decimal_separator": ".", "grouping_separator": None,
            "sign": "optional", "min_fraction_digits": 0, "max_fraction_digits": None,
        })
        self.assertNotIn("pattern", info)
        self.assertEqual(preset("number").pattern, preset("number", **defaults).pattern)
        for example in info["examples"]:
            with self.subTest(example=example):
                self.assertIsNotNone(preset("number").fullmatch(example))
        info["option_defaults"] = ()
        self.assertEqual(dict(inspect_preset("number")["option_defaults"]), defaults)

    def test_options_do_not_change_the_default_pattern(self):
        default_pattern = preset("number")
        preset("number", decimal_separator=",", sign="required")
        self.assertIs(preset("number"), default_pattern)
        self.assertIsNotNone(default_pattern.fullmatch("12.34"))
        self.assertIsNone(default_pattern.search("12,34"))

    def test_replace_numbers_with_callable_and_backreference(self):
        self.assertEqual(
            regex_replace("A: 12; B: -3.5", preset("number"), r"[\g<0>]", count=1),
            "A: [12]; B: -3.5",
        )
        self.assertEqual(
            regex_replace("12 e 3", preset("number"), lambda m: str(int(m.group()) * 2)),
            "24 e 6",
        )


class TestDataStringIteratorReplaceCompatibility(unittest.TestCase):
    def test_replace_is_literal_and_returns_a_new_iterator(self):
        from cereja.utils._utils import DataStringIterator

        original = ["a.b", "axb", "."]
        source = DataStringIterator(original)
        result = source.replace(".", r"\1")
        self.assertIsInstance(result, DataStringIterator)
        self.assertIsNot(result, source)
        self.assertEqual(list(result), [r"a\1b", "axb", r"\1"])
        self.assertEqual(list(source), original)
        self.assertEqual(list(result.upper()), [r"A\1B", "AXB", r"\1"])

    def test_replace_preserves_empty_and_regex_like_literal_behavior(self):
        from cereja.utils._utils import DataStringIterator

        source = DataStringIterator(["123 [0-9]+", "abc"])
        self.assertEqual(list(source.replace("[0-9]+", "X")), ["123 X", "abc"])
        self.assertEqual(list(source.replace("", "-")), [
            "-1-2-3- -[-0---9-]-+-", "-a-b-c-",
        ])

    
