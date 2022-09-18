"""

Copyright (c) 2019 The Cereja Project

Permission is hereby granted, free of charge, to any person obtaining a copy
of this software and associated documentation files (the "Software"), to deal
in the Software without restriction, including without limitation the rights
to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
copies of the Software, and to permit persons to whom the Software is
furnished to do so, subject to the following conditions:

The above copyright notice and this permission notice shall be included in all
copies or substantial portions of the Software.

THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
SOFTWARE.
"""
import itertools
import warnings
from typing import List, Dict, Union, Sequence, AnyStr, Any, Iterable

from ..file import FileIO
from ..config.cj_types import Number
from ..mltools import preprocess as _preprocess
from ..mltools.data import Freq
from ..config.conf import BasicConfig
from abc import ABCMeta, abstractmethod

from ..system import Path

__all__ = ["LanguageData", "Preprocessor", "LanguageDetector"]

_LANGUAGE_ISO_639_2 = {"eng": "English", "por": "Portuguese"}
_LANGUAGE_ISO_639_1 = {"pt": "English", "en": "Portuguese"}


def separate(
        text: AnyStr, sep: Union[str, Sequence[str]] = ("!", "?", "."), between_char=False
) -> str:
    warnings.warn(
            f"This function will be deprecated in future versions. " f"preprocess.separate",
            DeprecationWarning,
            2,
    )
    return _preprocess.separate(text=text, sep=sep, between_char=between_char)


class LanguageConfig(BasicConfig):
    def __init__(
            self,
            name="UNK_LANG",
            stop_words=(),
            punctuation="!?,.",
            to_lower=True,
            is_remove_punctuation=True,
            is_remove_stop_words=True,
            is_remove_accent=False,
            is_destructive=False,
            **kwargs,
    ):
        if not isinstance(stop_words, (tuple, list)):
            raise TypeError("Stop words must be in a list or tuple")
        if not isinstance(punctuation, str):
            raise TypeError("a string is expected for punctuation")
        super().__init__(
                name=name,
                stop_words=stop_words,
                punctuation=punctuation,
                to_lower=to_lower,
                is_remove_punctuation=is_remove_punctuation,
                is_remove_stop_words=is_remove_stop_words,
                is_remove_accent=is_remove_accent,
                is_destructive=is_destructive,
                **kwargs,
        )

    def _before(self, new_config: dict):
        super()._before(new_config)


class Preprocessor:
    def __init__(
            self,
            stop_words=(),
            punctuation="!?,.",
            to_lower=False,
            is_remove_punctuation=False,
            is_remove_stop_words=False,
            is_remove_accent=False,
            **kwargs,
    ):

        self.config = LanguageConfig(
                stop_words=stop_words,
                punctuation=punctuation,
                to_lower=to_lower,
                is_remove_punctuation=is_remove_punctuation,
                is_remove_stop_words=is_remove_stop_words,
                is_remove_accent=is_remove_accent,
                **kwargs,
        )

    def __repr__(self):
        return repr(self.config)

    def _preprocess(self, sentence, is_destructive: bool):
        if is_destructive or self.config.to_lower:
            sentence = sentence.lower()
        sentence = _preprocess.remove_extra_chars(sentence)
        sentence = _preprocess.remove_non_language_elements(sentence)
        if self.config.name == "en":
            sentence = _preprocess.replace_english_contractions(sentence)
        if is_destructive or self.config.is_remove_accent:
            sentence = _preprocess.accent_remove(sentence)
        sentence = _preprocess.separate(sentence)
        if is_destructive or self.config.is_remove_punctuation:
            sentence = _preprocess.remove_punctuation(sentence, self.config.punctuation)
        if is_destructive or self.config.is_remove_stop_words:
            sentence = " ".join(
                    [w for w in sentence.split() if w not in self.config.stop_words]
            )
        return _preprocess.remove_extra_chars(sentence)

    def preprocess(self, data, is_destructive=False):
        if isinstance(data, str):
            return self._preprocess(sentence=data, is_destructive=is_destructive)
        return map(
                lambda sentence: self._preprocess(sentence, is_destructive=is_destructive),
                data,
        )


class BaseData(metaclass=ABCMeta):
    def __init__(self, data: Any):
        self._data = []
        self._prepare_data(data)

    @property
    def data(self):
        return self._data

    @abstractmethod
    def _prepare_data(self, data: Any) -> Any:
        pass


class LanguageData(BaseData):
    def __init__(
            self,
            data,
            stop_words=(),
            punctuation="!?,.",
            to_lower=False,
            is_remove_punctuation=False,
            is_remove_stop_words=False,
            is_remove_accent=False,
            **kwargs,
    ):

        self._preprocessor = Preprocessor(
                hook=self.re_build,
                stop_words=stop_words,
                punctuation=punctuation,
                to_lower=to_lower,
                is_remove_punctuation=is_remove_punctuation,
                is_remove_stop_words=is_remove_stop_words,
                is_remove_accent=is_remove_accent,
                **kwargs,
        )

        self._phrases_freq: Freq = ...
        self._words_freq: Freq = ...
        self.__recovery_phrase_freq: Freq = ...
        self.__recovery_word_freq: Freq = ...
        super().__init__(data=data)
        self._build = True

    @property
    def config(self):
        return self._preprocessor.config

    def re_build(self):
        if hasattr(self, "_build"):
            data = self._data.copy()
            self._data.clear()
            self._phrases_freq = None
            self._words_freq = None
            self.__recovery_phrase_freq = None
            self.__recovery_word_freq = None
            self._prepare_data(data)

    def reset_freq(self):
        self._phrases_freq = self.__recovery_phrase_freq.copy()
        self._words_freq = self.__recovery_word_freq.copy()

    @property
    def vocab_size(self):
        return len(self._words_freq)

    def __contains__(self, item):
        if item in self.words_freq:
            return True
        if item in self.phrases_freq:
            return True

    def __repr__(self):
        return f"LanguageData(examples: {len(self)} - vocab_size: {self.vocab_size})"

    def __len__(self):
        return len(self._data)

    def __iter__(self):
        return iter(self._data)

    @property
    def punctuation(self):
        return self.config.punctuation

    @property
    def words_freq(self) -> Freq:
        return self._words_freq

    @property
    def phrases_freq(self) -> Freq:
        return self._phrases_freq

    @property
    def data_prep(self):
        for phrase in self.data:
            yield self.preprocess(phrase)

    def word_freq(self, word: str):
        return self._words_freq.get(self.preprocess(word))

    @property
    def words(self):
        return set(self._words_freq)

    def preprocess(self, value: Union[str, List[str]]):
        return self._preprocessor.preprocess(value)

    def synergy(self, value: Union[Iterable[str], str]) -> Number:
        """
        Returns how important the value sent is in relation to the data set
        """
        if value is None:
            return 0.0
        if isinstance(value, str):
            value = [value]
        try:
            value = set(
                    itertools.chain(*map(lambda val: self.preprocess(val).split(), value))
            )
        except AttributeError:
            raise ValueError("Inconsistent data format.")
        result = list(map(self._words_freq.item_prob, value))
        zeros = result.count(0)
        if zeros:
            return sum(result) - (zeros / len(value))
        return round(sum(result), 3)

    def save_freq(
            self, save_on: str, prefix="freq", ext: str = "json", probability=False
    ):
        ext = ext.strip(".")  # normalize
        save_on = Path(save_on)

        path_words = save_on.join(f"{prefix}_words.{ext}")
        self.words_freq.to_json(path_words, probability=probability, exist_ok=True)

        path_phrases = save_on.join(f"{prefix}_phrases.{ext}")
        self.phrases_freq.to_json(path_phrases, probability=probability, exist_ok=True)

    def _prepare_data(self, data, save_preprocessed=False):
        words = []
        phrases = []
        for phrase in data:
            prep_phrase = self.preprocess(phrase)
            if save_preprocessed:
                self._data.append(prep_phrase)
            else:
                self._data.append(phrase)

            phrases.append(prep_phrase)

            words += (
                prep_phrase.split() if isinstance(prep_phrase, str) else [prep_phrase]
            )

        self._words_freq = Freq(words)
        self.__recovery_word_freq = self._words_freq.copy()

        self._phrases_freq = Freq(phrases)
        self.__recovery_phrase_freq = self._phrases_freq.copy()

    def sample_words_freq(
            self, freq: int = None, max_items: int = -1, order="most_common"
    ):
        return self._words_freq.sample(max_items=max_items, max_freq=freq, order=order)

    def sample_phrases_freq(
            self, freq: int = None, max_items: int = -1, order="most_common"
    ):
        return self._phrases_freq.sample(
                max_items=max_items, max_freq=freq, order=order
        )


class LanguageDetector:
    __language_data: Dict[str, Union[LanguageData, dict]] = {}
    __memory = {}

    def __init__(self):
        self._is_model = False

    def load(self, filepath: str):
        self._is_model = True
        self.__language_data = FileIO.load(filepath).data
        return self

    def add(self, language: str, data_: List[str]):
        if language not in self.__language_data:
            data_ = LanguageData(data_)
            self.__language_data[language] = (
                data_.words_freq if self._is_model else data_
            )

    def _get_most(self, word, n_max=5):
        if word not in self.__memory:
            result = []
            for lang, obj in self.__language_data.items():
                obj = obj if self._is_model else obj.words_freq
                if word in obj:
                    result.append((lang, obj[word]))
            if result:
                self.__memory[word] = list(
                        map(
                                lambda x: (x[0], x[1] / sum(dict(result).values())),
                                sorted(result, key=lambda x: x[1]),
                        )
                )
            else:
                return []
        return self.__memory[word][:n_max]

    def predict(self, sentence: str):
        result = {}
        sentence = LanguageData([sentence])
        for word in sentence.words_freq:
            if len(word) == 1:
                continue
            for lang, percent in self._get_most(word):
                percent = percent / len(sentence.words_freq)
                if lang in result:
                    result[lang] += percent
                    continue
                result[lang] = percent

        if result:
            result = sorted(result.items(), key=lambda x: x[1])
            if result[-1][1] > 0.1:
                return result[-1]
            return result

        return "UNDEFINED", 1.0

    def save(self, filepath: str):
        FileIO.create(filepath, data=self.__language_data).save(exist_ok=True)
