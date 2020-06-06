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
import collections
import os
import warnings
from abc import ABCMeta, abstractmethod
from typing import Any

from cereja.arraytools import get_cols
from cereja.conf import _BasicConfig
from cereja.filetools import File
import random
import csv
import json
from cereja.path import normalize_path


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

        self._phrases_freq = None
        self._words_freq = None
        self.__recovery_phrase_freq = None
        self.__recovery_word_freq = None
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
    def words_freq(self) -> collections.Counter:
        return self._words_freq

    @property
    def phrases_freq(self) -> collections.Counter:
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

    def save_freq(self, save_on: str, prefix='freq', ext: str = 'json'):
        ext = ext.strip('.')  # normalize
        save_on = normalize_path(save_on)

        path_words = os.path.join(save_on, f'{prefix}_words.{ext}')
        with open(path_words, 'w+', encoding='utf-8') as fp:
            json.dump(self.sample_words_freq(), fp, indent=True)

        path_phrases = os.path.join(save_on, f'{prefix}_phrases.{ext}')
        with open(path_phrases, 'w+', encoding='utf-8') as fp:
            json.dump(self.sample_phrases_freq(), fp, indent=True)

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

        self._words_freq = collections.Counter(words)
        self.__recovery_word_freq = self._words_freq.copy()

        self._phrases_freq = collections.Counter(phrases)
        self.__recovery_phrase_freq = self._phrases_freq.copy()

    @staticmethod
    def _freq_by_counter(counter, max_freq, max_items, order='most_common'):
        assert order in ('most_common', 'least_common'), ValueError(
                f"Order {order} not in ('most_common', 'least_common')")
        assert isinstance(max_items, int), TypeError(f"max_items {type(max_items)} != {int}")
        max_items = len(counter) if max_items == -1 else max_items
        if order == 'least_common':
            query = counter.most_common()[:-max_items - 1:-1]
        else:
            query = counter.most_common(max_items)
        if max_freq is not None:
            assert isinstance(max_freq, int), TypeError(f"freq {type(max_freq)} != {int}")
            query = list(filter(lambda item: item[1] <= max_freq, query))
        return dict(query)

    def sample_words_freq(self, freq: int = None, max_items: int = -1, order='most_common'):
        return self._freq_by_counter(self._words_freq, max_items=max_items, max_freq=freq, order=order)

    def sample_phrases_freq(self, freq: int = None, max_items: int = -1, order='most_common'):
        return self._freq_by_counter(self._phrases_freq, max_items=max_items, max_freq=freq, order=order)


class Corpus(object):
    def __init__(self, source_data, target_data, source_name=None, target_name=None, **kwargs):
        self.source = LanguageData(source_data, name=source_name, **kwargs)
        self.target = LanguageData(target_data, name=target_name, **kwargs)
        self._percent_train = 0.8
        self._n_train = self.n_train
        self._valid_parallel_data(self.source.data, self.target.data)

    def __iter__(self):
        return zip(self.source, self.target)

    def __len__(self):
        return len(self.source)

    def __repr__(self):
        return f'Corpus(examples: {len(self)} - source_vocab_size: {self.source.vocab_size} - target_vocab_size:{self.target.vocab_size})'

    def __getitem__(self, item):
        if isinstance(item, int):
            return self.source.data[item], self.target.data[item]
        return list(zip(self.source.data[item], self.target.data[item]))

    @property
    def source_language(self):
        """
        Only read. The setter function is `Corpus.source.config.set_config(name="new name")`
        """
        return self.source.config.name

    @property
    def target_language(self):
        """
        Only read. The setter function is `Corpus.target.config.set_config(name="new name")`
        """
        return self.target.config.name

    @property
    def config(self):
        """
        Only read. The setter function is `Corpus.<source or target>.config.set_config`
        """
        return {'source': self.source.config.get(), 'target': self.source.config.get()}

    def set_config(self, **kwargs):
        """
        you can use `Corpus.config` which returns a dictionary with the current configuration.
        And then just use the this method `Corpus.set_config` by sending the changed dictionary.

        :param kwargs: dictionary like this:
                    {
                     'source': {'name': 'SOURCE_NAME',
                                'punctuation': '',
                                'remove_punctuation': False,
                                'remove_stop_words': False,
                                'stop_words': (),
                                'to_lower': False
                                },
                     'target': {'name':'TARGET_NAME',
                                'punctuation': '',
                                'remove_punctuation': False,
                                'remove_stop_words': False,
                                'stop_words': (),
                                'to_lower': False
                                }
                    }
        """
        source_config = kwargs.get('source')
        target_config = kwargs.get('target')
        if source_config:
            self.source.config.set_config(**source_config)
        if target_config:
            self.target.config.set_config(**target_config)

    @staticmethod
    def is_parallel(data):
        try:
            for x, y in data:
                if isinstance(x, (str, int, float)) and isinstance(y, (str, int, float)):
                    return True
                break
        except:
            pass
        return False

    @classmethod
    def distinct_from_parallel(cls, data):
        return get_cols(data)

    @classmethod
    def load_from_parallel_data(cls, data, source_name: str = None, target_name: str = None, **kwargs):
        if cls.is_parallel(data):
            source_data, target_data = cls.distinct_from_parallel(data)
            return cls(source_data, target_data, source_name=source_name, target_name=target_name, **kwargs)
        raise ValueError("isn't valid parallel data")

    @property
    def n_train(self):
        return int(self._percent_train * len(self.source.data))

    @property
    def n_test(self):
        return len(self.source.data) - self.n_train

    def _can_go_test(self, x, y):
        x = self.source.preprocess(x)
        y = self.target.preprocess(y)
        if self.source.phrases_freq.get(x) == 1 and len(x.split()) >= 4:
            x, y = x.split(), y.split()
            for i in x:
                if self.source.words_freq.get(i) <= x.count(i):
                    return False
            for i in y:
                if self.target.words_freq.get(i) <= y.count(i):
                    return False
            return True
        return False

    def _valid_parallel_data(self, x, y):
        assert len(x) == len(y), f"Size of {self.source_language} ({len(x)}) != {self.target_language} ({len(y)})"

    def _update_filters(self, x, y):
        x = self.source.preprocess(x)
        y = self.target.preprocess(y)
        for i in x.split():
            self.source.words_freq.subtract([i])

        for i in y.split():
            self.target.words_freq.subtract([i])

        self.source.phrases_freq.subtract([x])
        self.target.phrases_freq.subtract([y])

    def _get_vocab_data(self, source_vocab_size: int = None, target_vocab_size: int = None, order='most_common'):
        source_vocab_data = {}
        target_vocab_data = {}
        if source_vocab_size is not None:
            source_vocab_data = self.source.sample_words_freq(max_items=source_vocab_size, order=order)
        if target_vocab_size is not None:
            target_vocab_data = self.target.sample_words_freq(max_items=target_vocab_size, order=order)

        for x, y in zip(self.source.data, self.target.data):
            if source_vocab_size:
                if not all(list(map(lambda w: w in source_vocab_data, self.source.preprocess(x).split()))):
                    continue
            if target_vocab_size:
                if not all(list(map(lambda w: w in target_vocab_data, self.target.preprocess(y).split()))):
                    continue
            yield [x, y]

    def save(self, save_on_dir: str, take_split: bool = True, test_max_size: int = None, source_vocab_size: int = None,
             target_vocab_size: int = None, shuffle=True, prefix=None, ext='align', **kwargs):

        if take_split:
            x_train, y_train, x_test, y_test = self.split_data(test_max_size=test_max_size,
                                                               source_vocab_size=source_vocab_size,
                                                               target_vocab_size=target_vocab_size,
                                                               take_parallel_data=False,
                                                               shuffle=shuffle)
            train_prefix, test_prefix = (f'{prefix}_train', f'{prefix}_test') if prefix is not None else (
                'train', 'test')
            data_to_save = ((train_prefix, x_train, y_train), (test_prefix, x_test, y_test))
        else:
            data_to_save = ((prefix, self.source.data, self.target.data),)

        for prefix, x, y in data_to_save:
            save_on = os.path.join(save_on_dir, f'{prefix}_{self.source_language}.{ext.strip(".")}')
            File(save_on, x).save(**kwargs)
            save_on = os.path.join(save_on_dir, f'{prefix}_{self.target_language}.{ext.strip(".")}')
            File(save_on, y).save(**kwargs)

    @classmethod
    def load_corpus_from_dir(cls, path_: str, src: str, trg: str, ext='align', name_not_contains_: tuple = ()):
        files_ = File.load_files(path_=path_, ext=ext, contains_in_name=[src, trg],
                                 not_contains_in_name=name_not_contains_)
        src_data = []
        trg_data = []
        for file in files_:
            if file is None:
                continue
            if ext not in file.ext:
                continue
            if src in file.file_name_without_ext:
                src_data += file.lines
            if trg in file.file_name_without_ext:
                trg_data += file.lines
        return cls(src_data, trg_data, source_name=src, target_name=trg)

    @classmethod
    def load_corpus_from_csv(cls, path_: str, src_col_name: str, trg_col_name: str, source_name=None,
                             target_name=None):

        csv_read = csv.DictReader(File.read(path_).lines)
        src_data = []
        trg_data = []
        for i in csv_read:
            for col_name in (src_col_name, trg_col_name):
                if col_name not in i:
                    raise ValueError(f"Not found col <{col_name}> in {list(i.keys())}")
            src_data.append(i[src_col_name])
            trg_data.append(i[trg_col_name])
        return cls(src_data, trg_data, source_name=source_name, target_name=target_name)

    def split_data(self, test_max_size: int = None, source_vocab_size: int = None, target_vocab_size: int = None,
                   shuffle=True, take_parallel_data=True, take_corpus_instances=False, legacy_test=None):
        """
        Guarantees test data without data identical to training and only with vocabulary that exists in training


        :param test_max_size: int = max examples on test data
        :param source_vocab_size: int = restrict most common vocab
        :param target_vocab_size: int = restrict most common vocab
        :param shuffle: bool = randomize
        :param take_parallel_data: bool = zipped data if true else return (x_train, y_train, x_test, y_test)
        :param take_corpus_instances: bool = return new instances for train data and test data
        :param legacy_test: List[Tuple[str,str]] = parallel data
        """
        self.source.reset_freq()
        self.target.reset_freq()
        train = []
        test = []

        if legacy_test is not None:
            test = Corpus(*self.distinct_from_parallel(legacy_test), source_name=self.source_language,
                          target_name=self.target_language)

        test_max_size = test_max_size if test_max_size is not None and isinstance(test_max_size, (int, float)) else len(
                self.source.data) - self.n_train
        if source_vocab_size is not None or target_vocab_size is not None:
            data = list(self._get_vocab_data(source_vocab_size=source_vocab_size,
                                             target_vocab_size=target_vocab_size))
        else:
            data = list(zip(self.source.data, self.target.data))

        if shuffle:
            random.shuffle(data)

        for x, y in data:
            # remove blank line
            if x == '' or y == '':
                continue
            if legacy_test is not None:
                # remove sentence from train.
                if self.source.preprocess(x) in test.source.phrases_freq:
                    continue
            if (self._can_go_test(x, y) and len(test) < test_max_size) and legacy_test is None:
                test.append([x, y])
                self._update_filters(x, y)
                continue
            train.append([x, y])
            
        if take_parallel_data is False:
            return (*get_cols(train), *get_cols(test))
        if take_corpus_instances is True:
            train = self.load_from_parallel_data(train, self.source_language, self.target_language)
            test = self.load_from_parallel_data(test, self.source_language, self.target_language)
            return train, test
        return train, test

    def split_data_and_save(self, **kwargs):
        alternative = f"You can use <Corpus.save>"
        warnings.warn(f"This function has been deprecated and will be removed in future versions. "
                      f"{alternative}", DeprecationWarning, 2)
        self.save(**kwargs)
