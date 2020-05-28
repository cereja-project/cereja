import collections
import os
from typing import Tuple, Iterable

from cereja.arraytools import get_cols
from cereja.filetools import File
import random


class Corpus(object):
    punctuation = '!,?.'

    def __init__(self, paralel_data: Iterable[Tuple[str, str]], source_language: str = "X", target_language: str = "Y"):
        self._x = []
        self._y = []

        self._x_words_counter = None
        self._y_words_counter = None

        self._x_sentences_counter = None
        self._y_sentences_counter = None

        self.source_language = source_language
        self.target_language = target_language

        self._prepare_data(paralel_data=paralel_data)

        self._percent_train = 0.8
        self._n_train = self.n_train

    @property
    def n_train(self):
        return int(self._percent_train * len(self._x))

    @property
    def n_test(self):
        return len(self._x) - self.n_train

    def _preprocess(self, value: str, remove_punctuation=True, lower_case=True):
        cleaned_data = []
        for w in value.split():
            if remove_punctuation:
                w = w.strip(self.punctuation)
            w = " '".join(w.split("'"))
            cleaned_data.append(w)
        cleaned_data = ' '.join(cleaned_data)
        return cleaned_data if not lower_case else cleaned_data.lower()

    def _can_go_test(self, x, y):
        x = self._preprocess(x)
        y = self._preprocess(y)
        if self._x_sentences_counter.get(x) == 1:
            x, y = x.split(), y.split()
            if len(x) < 4:
                return False
            for i in x:
                if self._x_words_counter.get(i) == 1:
                    return False
            for i in y:
                if self._y_words_counter.get(i) == 1:
                    return False
            return True
        return False

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

    def _prepare_data(self, paralel_data: Iterable[Tuple[str, str]]):
        x_words = []
        y_words = []
        x_sentences = []
        y_sentences = []
        for x, y in paralel_data:
            self._x.append(x)
            self._y.append(y)
            x, y = self._preprocess(x), self._preprocess(y)
            x_sentences.append(x)
            y_sentences.append(y)

            x_words += x.split()
            y_words += y.split()

        self._x_sentences_counter = collections.Counter(x_sentences)
        self._y_sentences_counter = collections.Counter(y_sentences)
        self._x_words_counter = collections.Counter(x_words)
        self._y_words_counter = collections.Counter(y_words)

    def _update_filters(self, x, y):
        x = self._preprocess(x)
        y = self._preprocess(y)
        for i in x.split():
            self._x_words_counter.subtract(i)

        for i in y.split():
            self._y_words_counter.subtract(i)

        self._x_sentences_counter.subtract(x)
        self._y_sentences_counter.subtract(y)

    def source_words_freq(self, freq: int = None, max_items: int = -1, order='most_common'):
        return self._freq_by_counter(self._x_words_counter, max_items=max_items, max_freq=freq, order=order)

    def source_sentence_freq(self, freq: int = None, max_items: int = -1, order='most_common'):
        return self._freq_by_counter(self._x_sentences_counter, max_items=max_items, max_freq=freq, order=order)

    def target_words_freq(self, freq: int = None, max_items: int = -1, order='most_common'):
        return self._freq_by_counter(self._x_words_counter, max_items=max_items, max_freq=freq, order=order)

    def target_sentence_freq(self, freq: int = None, max_items: int = -1, order='most_common'):
        return self._freq_by_counter(self._x_sentences_counter, max_items=max_items, max_freq=freq, order=order)

    def _get_vocab_data(self, source_vocab_size: int = None, target_vocab_size: int = None, order='most_common'):
        source_vocab_data = {}
        target_vocab_data = {}
        if source_vocab_size is not None:
            source_vocab_data = self.source_words_freq(max_items=source_vocab_size, order=order)
        if target_vocab_size is not None:
            target_vocab_data = self.target_words_freq(max_items=target_vocab_size, order=order)

        for x, y in zip(self._x, self._y):
            if source_vocab_size:
                if not all(list(map(lambda w: w in source_vocab_data, self._preprocess(x).split()))):
                    continue
            if target_vocab_size:
                if not all(list(map(lambda w: w in target_vocab_data, self._preprocess(y).split()))):
                    continue
            yield [x, y]

    def split_data(self, test_max_size: int = None, source_vocab_size: int = None, target_vocab_size: int = None,
                   take_paralel_data=True, shuffle=True):
        train = []
        test = []
        test_max_size = test_max_size if test_max_size is not None and isinstance(test_max_size, (int, float)) else len(
                self._x) - self.n_train
        if source_vocab_size is not None or target_vocab_size is not None:
            data = list(self._get_vocab_data(source_vocab_size=source_vocab_size,
                                             target_vocab_size=target_vocab_size))
        else:
            data = list(zip(self._x, self._y))

        if shuffle:
            random.shuffle(data)

        for x, y in data:
            if self._can_go_test(x, y) and len(test) < test_max_size:
                test.append([x, y])
                self._update_filters(x, y)
                continue
            train.append([x, y])
        if take_paralel_data is False:
            return (*get_cols(train), *get_cols(test))
        return train, test

    def split_data_and_save(self, save_on_dir: str, test_max_size: int = None, source_vocab_size: int = None,
                            target_vocab_size: int = None, shuffle=True, ext='align', **kwargs):
        x_train, y_train, x_test, y_test = self.split_data(test_max_size=test_max_size,
                                                           source_vocab_size=source_vocab_size,
                                                           target_vocab_size=target_vocab_size, take_paralel_data=False,
                                                           shuffle=shuffle)

        for prefix, x, y in (('train', x_train, y_train), ('test', x_test, y_test)):
            save_on = os.path.join(save_on_dir, f'{prefix}_{self.source_language}.{ext.strip(".")}')
            File(save_on, x).save(**kwargs)
            save_on = os.path.join(save_on_dir, f'{prefix}_{self.target_language}.{ext.strip(".")}')
            File(save_on, y).save(**kwargs)
