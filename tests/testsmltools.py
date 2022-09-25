import tempfile
import unittest

from cereja.mltools import preprocess

from cereja.system import Path
from cereja.mltools.preprocess import separate
from cereja.mltools.data import Tokenizer
from cereja.mltools.data import Freq


class BaseTest(unittest.TestCase):
    def loop_on_examples_pairs(self, func, examples):
        msg_ = f"Error on {func.__name__}"
        for example, expected_response, args, kwargs in examples:
            if args and kwargs:
                self.assertEqual(
                    func(example, *args, **kwargs), expected_response, msg=msg_
                )
            elif args:
                self.assertEqual(func(example, *args), expected_response, msg=msg_)
            elif kwargs:
                self.assertEqual(func(example, **kwargs), expected_response, msg=msg_)
            else:
                self.assertEqual(func(example), expected_response, msg=msg_)


class TokenizerTest(unittest.TestCase):
    data = None

    def test_sanity(self):
        with tempfile.TemporaryDirectory() as tempdir:
            to_encode = "oi tudo tranquilo"
            tokenizer = Tokenizer(
                ["oi amigo tudo bem"], preprocess_function=separate, use_unk=False
            )

            self.assertEqual(tokenizer.last_index, 13)
            encoded = tokenizer.encode([to_encode])
            valid_encode_tokens = [
                [
                    tokenizer._item_to_index["oi"],
                    tokenizer._item_to_index["tudo"],
                    tokenizer._item_to_index["tranquilo"],
                ]
            ]
            self.assertEqual(tokenizer.last_index, 14)
            self.assertEqual(encoded, valid_encode_tokens)
            decoded = tokenizer.decode(encoded[0])
            self.assertEqual(decoded, to_encode)
            temp_file = Path(tempdir).join("tokenizer.json")
            tokenizer.to_json(temp_file)

            # Valid.
            tokenizer = Tokenizer.load_from_json(temp_file)
            encoded = tokenizer.encode([to_encode])
            self.assertEqual(tokenizer.last_index, 14)
            self.assertEqual(encoded, valid_encode_tokens)
            decoded = tokenizer.decode(encoded[0])
            self.assertEqual(decoded, to_encode)


class PreprocessModuleTest(BaseTest):
    def test_sanity(self):
        self.assertEqual(preprocess.separate("how are you?", sep="?"), "how are you ?")
        self.assertEqual(
            preprocess.separate("how are you,man?", sep=("?", ","), between_char=True),
            "how are you , man ?",
        )
        self.assertEqual(preprocess.separate("how are! you?"), "how are ! you ?")

    def test_separate(self):
        examples = (
            ("how are you?", "how are you ?", (), {"sep": "?"}),
            (
                "how are you,man?",
                "how are you , man ?",
                (),
                {"sep": ("?", ","), "between_char": True},
            ),
            ("how are! you?", "how are ! you ?", (), {}),
        )
        self.loop_on_examples_pairs(preprocess.separate, examples)

    def test_accent_remove(self):
        examples = (
            (
                "olá tudo bem amigo? Você é um cara legal!",
                "ola tudo bem amigo? Voce e um cara legal!",
                (),
                {},
            ),
            ("isso é muito difícil", "isso e muito dificil", (), {}),
        )
        self.loop_on_examples_pairs(preprocess.accent_remove, examples)

    def test_replace_english_contractions(self):
        examples = (("i'll", "i shall", (), {}),)
        self.loop_on_examples_pairs(preprocess.replace_english_contractions, examples)

    def test_remove_extra_chars(self):
        examples = (("i   like it!!!", "i like it!", (), {}),)
        self.loop_on_examples_pairs(preprocess.remove_extra_chars, examples)

    def test_remove_non_language_elements(self):
        examples = (("\U0001F352 i like it!", "i like it!", (), {}),)
        self.loop_on_examples_pairs(preprocess.remove_non_language_elements, examples)

    def test_remove_punctuation(self):
        examples = (
            ("\U0001F352 i like it!", "\U0001F352 i like it", (), {}),
            (
                "olá tudo bem amigo?! Você é um cara legal!",
                "olá tudo bem amigo Você é um cara legal",
                (),
                {},
            ),
            ("e aí? quero R$ 40,00", "e aí quero R 4000", (), {}),
        )
        self.loop_on_examples_pairs(preprocess.remove_punctuation, examples)

        examples2 = (
            ("\U0001F352 i like it!", "\U0001F352 i like it", (), {}),
            (
                "olá tudo bem amigo?! Você é um cara legal!",
                "olá tudo bem amigo Você é um cara legal",
                (),
                {},
            ),
            ("e aí? quero R$ 40,00", "e aí quero R$ 40,00", (), {"punctuation": "?!"}),
        )
        self.loop_on_examples_pairs(preprocess.remove_punctuation, examples2)

    def test_remove_stop_words(self):
        examples = (
            ("my name is Joab", "my name Joab", (), {}),
            ("you are cool!", "you cool!", (), {}),
        )
        self.loop_on_examples_pairs(preprocess.remove_stop_words, examples)


class FreqTest(unittest.TestCase):
    def setUp(self) -> None:
        self.freq = Freq([1, 2, 3, 4, 4])

    def test_probability(self):
        self.assertEqual(self.freq.probability, {1: 0.2, 2: 0.2, 3: 0.2, 4: 0.4})

    def test_item_prob(self):
        self.assertEqual(self.freq.item_prob(4), 0.4)

    def test_sanity(self):
        self.assertEqual(preprocess.separate("how are you?", sep="?"), "how are you ?")
        self.assertEqual(
            preprocess.separate("how are you,man?", sep=("?", ","), between_char=True),
            "how are you , man ?",
        )
        self.assertEqual(preprocess.separate("how are! you?"), "how are ! you ?")

        freq = Freq([1, 1, 2, 2, 3, 3, 4, 5, 6, 7, 8, "hi", "o", "a"])
        self.assertEqual(
            freq.sample(max_freq=1),
            {4: 1, 5: 1, 6: 1, 7: 1, 8: 1, "hi": 1, "o": 1, "a": 1},
        )
        self.assertEqual(freq.sample(freq=2), {1: 2, 3: 2, 2: 2})

        self.assertRaises(AssertionError, freq.sample, freq=1, max_freq=2)
        self.assertRaises(AssertionError, freq.sample, freq=1, min_freq=2)

        freq = Freq([1, 2, 3, 3, 4, 5, 6, 7, 6, 7, 12, 31, 123, 5, 3])
        self.assertEqual(
            freq.least_freq(),
            {123: 1, 31: 1, 12: 1, 4: 1, 2: 1, 1: 1, 7: 2, 6: 2, 5: 2, 3: 3},
        )


if __name__ == "__main__":
    unittest.main()
