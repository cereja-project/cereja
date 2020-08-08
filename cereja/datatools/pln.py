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

from typing import List, Dict, Union, Sequence, AnyStr, Any

from cereja.datatools.data import Freq
from cereja.filetools import File, JsonFile
from cereja.conf import _BasicConfig
from abc import ABCMeta, abstractmethod

from cereja.path import Path

__all__ = ['separate', 'LanguageConfig', 'LanguageData']


def separate(text: AnyStr, sep: Union[str, Sequence[str]] = ('!', '?', '.'), between_char=False) -> str:
    """
    Creating a space between an element in sep values
    e.g:

    >>> separate('how are you?', sep='?')
    'how are you ?'
    >>> separate('how are you,man?', sep=('?',','), between_char=True)
    'how are you , man ?'

    :param text: Any text
    :param sep: values that will be separated. Accepted types (str, list and tuple)
    :param between_char: if True the sep values that's on between chars it will be separated.
                         eg. "it's" -> "it ' s"
    :return: processed text
    """
    if isinstance(sep, str):
        sep = (sep,)
    assert isinstance(sep, (tuple, list)), f"{type(sep)} is not acceptable. Only (str, list and tuple) types"
    assert isinstance(text, str), f"{type(text)} is not acceptable. Only str type."
    new_text = []
    for word in text.split():
        for i in sep:
            if (word.startswith(i) or word.endswith(i)) or between_char is True:
                word = f' {i} '.join(word.split(i)).strip()
        new_text += word.split()
    return ' '.join(new_text)


class LanguageConfig(_BasicConfig):
    name = 'UNK_LANG'
    stop_words = ()
    punctuation = '!?,.'
    to_lower = True
    remove_punctuation = True
    remove_stop_words = True

    def __init__(self, **kwargs):
        name = kwargs.pop('name') if kwargs.get('name') is not None else self.name
        stop_words = kwargs.pop('stop_words') if kwargs.get('stop_words') is not None else self.stop_words
        punctuation = kwargs.pop('punctuation') if kwargs.get('punctuation') is not None else self.punctuation
        if not isinstance(stop_words, (tuple, list)):
            raise TypeError("Stop words must be in a list or tuple")
        if not isinstance(punctuation, str):
            raise TypeError("a string is expected for punctuation")
        super().__init__(name=name, stop_words=stop_words, punctuation=punctuation, **kwargs)

    def _before(self, new_config: dict):
        super()._before(new_config)


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

    def __init__(self, data, **kwargs):

        self.config = LanguageConfig(hook=self.re_build, **kwargs)

        self._phrases_freq: Freq = ...
        self._words_freq: Freq = ...
        self.__recovery_phrase_freq: Freq = ...
        self.__recovery_word_freq: Freq = ...
        super().__init__(data=data)
        self._build = True

    def re_build(self):
        if hasattr(self, '_build'):
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
        return f'LanguageData(examples: {len(self)} - vocab_size: {self.vocab_size})'

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
            yield self._preprocess(phrase)

    def preprocess(self, value: str):
        return self._preprocess(value)

    def word_freq(self, word: str):
        return self._words_freq.get(self._preprocess(word))

    def _preprocess(self, value: str):
        if not isinstance(value, str):
            return value
        value = value if not self.config.to_lower else value.lower()
        cleaned_data = []
        for w in value.split():
            if self.config.remove_punctuation:
                w = w.strip(self.punctuation)
            w = " '".join(w.split("'"))
            if self.config.remove_stop_words:
                if w in self.config.stop_words:
                    continue
            cleaned_data.append(w)
        cleaned_data = ' '.join(cleaned_data)
        return cleaned_data

    def save_freq(self, save_on: str, prefix='freq', ext: str = 'json', probability=False):
        ext = ext.strip('.')  # normalize
        save_on = Path(save_on)

        path_words = save_on.join(f'{prefix}_words.{ext}')
        self.words_freq.to_json(path_words, probability=probability, exist_ok=True)

        path_phrases = save_on.join(f'{prefix}_phrases.{ext}')
        self.phrases_freq.to_json(path_phrases, probability=probability, exist_ok=True)

    def _prepare_data(self, data, save_preprocessed=False):
        words = []
        phrases = []
        for phrase in data:
            prep_phrase = self._preprocess(phrase)
            if save_preprocessed:
                self._data.append(prep_phrase)
            else:
                self._data.append(phrase)

            phrases.append(prep_phrase)

            words += prep_phrase.split() if isinstance(prep_phrase, str) else [prep_phrase]

        self._words_freq = Freq(words)
        self.__recovery_word_freq = self._words_freq.copy()

        self._phrases_freq = Freq(phrases)
        self.__recovery_phrase_freq = self._phrases_freq.copy()

    def sample_words_freq(self, freq: int = None, max_items: int = -1, order='most_common'):
        return self._words_freq.sample(max_items=max_items, max_freq=freq, order=order)

    def sample_phrases_freq(self, freq: int = None, max_items: int = -1, order='most_common'):
        return self._phrases_freq.sample(max_items=max_items, max_freq=freq, order=order)


class LanguageDetector:
    __language_data: Dict[str, Union[LanguageData, dict]] = {}
    __memory = {}

    def __init__(self):
        self._is_model = False

    def load(self, filepath: str):
        self._is_model = True
        self.__language_data = File.read(filepath)
        return self

    def add(self, language: str, data_: List[str]):
        if language not in self.__language_data:
            data_ = LanguageData(data_)
            self.__language_data[language] = data_.words_freq if self._is_model else data_

    def _get_most(self, word, n_max=5):
        if word not in self.__memory:
            result = []
            for lang, obj in self.__language_data.items():
                obj = obj if self._is_model else obj.words_freq
                if word in obj:
                    result.append((lang, obj[word]))
            if result:
                self.__memory[word] = list(
                        map(lambda x: (x[0], x[1] / sum(dict(result).values())), sorted(result, key=lambda x: x[1])))
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
        JsonFile(filepath, data=self.__language_data).save(exist_ok=True)


if __name__ == '__main__':
    freq = Freq(JsonFile.read("C:/Users/handtalk/Downloads/lang_predict.json").data['por'])
    freq.to_json('teste.json', exist_ok=True)
