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
import warnings

from cereja import FileIO
from cereja.array import get_cols
from cereja.mltools.pln import LanguageData
import random
import csv
from cereja.system import Path

__all__ = ['Corpus']


class Corpus(object):
    def __init__(self, source_data, target_data, source_name=None, percent_train=0.8, target_name=None, stop_words=(),
                 punctuation='!?,.', to_lower=True, is_remove_punctuation=True, is_remove_stop_words=True,
                 is_remove_accent=False, is_destructive=False):
        self.source = LanguageData(source_data, name=source_name, stop_words=stop_words,
                                   punctuation=punctuation, to_lower=to_lower,
                                   is_remove_punctuation=is_remove_punctuation,
                                   is_remove_stop_words=is_remove_stop_words,
                                   is_remove_accent=is_remove_accent, is_destructive=is_destructive)
        self.target = LanguageData(target_data, name=target_name, stop_words=stop_words,
                                   punctuation=punctuation, to_lower=to_lower,
                                   is_remove_punctuation=is_remove_punctuation,
                                   is_remove_stop_words=is_remove_stop_words,
                                   is_remove_accent=is_remove_accent, is_destructive=is_destructive)
        self._percent_train = percent_train
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
        save_on_dir = Path(save_on_dir)
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
            save_on = save_on_dir.join(f'{prefix}_{self.source_language}.{ext.strip(".")}')
            FileIO.create(save_on, data=x).save(**kwargs)
            save_on = save_on_dir.join(f'{prefix}_{self.target_language}.{ext.strip(".")}')
            FileIO.create(save_on, data=y).save(**kwargs)

    @classmethod
    def load_corpus_from_csv(cls, path_: str, src_col_name: str, trg_col_name: str, source_name=None,
                             target_name=None):

        csv_read = csv.DictReader(FileIO.load(path_).data)
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
