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
import logging
import pickle
import random
import secrets
import math
from collections import Counter, OrderedDict
from typing import Optional, Sequence, Dict, Any, List, Union, Tuple, Set

from cereja.utils._utils import is_iterable, is_sequence
from cereja.file import FileIO
from cereja.utils import invert_dict, string_to_literal
from cereja.mltools.preprocess import remove_punctuation, remove_stop_words, \
    replace_english_contractions
from cereja.utils.decorators import thread_safe_generator

__all__ = ['ConnectValues', 'Freq', 'Tokenizer', 'TfIdf', 'DataGenerator']

logger = logging.Logger(__name__)


class Freq(Counter):
    def __init__(self, data: Optional[Sequence] = ()):
        assert is_iterable(data), "Isn't iterable."
        self._elements_size = None
        super().__init__(data)

    @property
    def probability(self) -> OrderedDict:
        """
        Return ordered dict with percent
        """
        return OrderedDict(map(lambda key: (key, self.item_prob(key)), self.most_common()))

    def __getattribute__(self, item):
        if item in ('probability', 'item_prob'):
            # ensures correct probability calculation
            self._elements_size = sum(self.values())
        return super(Freq, self).__getattribute__(item)

    def sample(self, freq: Optional[int] = None, min_freq: Optional[int] = 1, max_freq: Optional[int] = None,
               max_items: int = -1,
               order='most_common'):
        """
        :param freq: only this
        :param min_freq: limit sample by frequency
        :param max_freq: limit sample by frequency
        :param max_items: limit sample size
        :param order: choice order in ('most_common', 'least_common')
        :return: sample dictionary
        """
        assert not all((freq, max_freq or min_freq != 1)), "the <freq> parameter must be used without <max_freq> and " \
                                                           "<min_freq> "
        assert order in ('most_common', 'least_common'), ValueError(
                f"Order {order} not in ('most_common', 'least_common')")
        assert isinstance(max_items, int), TypeError(f"max_items {type(max_items)} != {int}")
        max_items = len(self) if max_items == -1 else max_items
        if order == 'least_common':
            query = super(Freq, self).most_common()[:-max_items - 1:-1]
        else:
            query = super(Freq, self).most_common(max_items)
        if freq is not None:
            assert isinstance(freq, int), TypeError(f"freq {type(freq)} != {int}")
            return dict(filter(lambda item: item[1] == freq, query))

        if max_freq is not None:
            assert min_freq <= max_freq, 'min_freq > max_freq'
            query = filter(lambda item: item[1] in range(min_freq, max_freq + 1), query)
        else:
            query = filter(lambda item: item[1] in range(min_freq, item[1] + 1), query)
        return dict(query)

    def most_common(self, n: Optional[int] = None) -> Dict[Any, int]:
        return dict(super(Freq, self).most_common(n))

    def least_freq(self, max_items: int = -1):
        return self.sample(max_items=max_items, order='least_common')

    def item_prob(self, item: Any) -> float:
        if item in self:
            return self.get(item) / self._elements_size or sum(self.values())
        return 0.0

    def to_json(self, path_, probability=False, **kwargs):
        content = self.probability if probability else self.most_common()
        FileIO.create(path_=path_, data=content).save(**kwargs)


class ConnectValues(dict):
    def __init__(self, name: str = None):
        super().__init__()
        self._name = name

    @property
    def name(self):
        return self._name

    @property
    def all(self):
        for connection in self._get_connections():
            yield connection, set(self._get_connections(connection))

    def _get_connections(self, value=None):
        if value is not None:
            connections_ = filter(lambda x: value in x, self)
        else:
            connections_ = self
        for k in connections_:
            for v in k:
                yield v

    def connect(self, a, b, confidence=0.0):
        self.update({tuple(sorted((a, b))): confidence})

    def get(self, a):
        return set(self._get_connections(a))

    def confidence(self, a, b):
        return self[(tuple(sorted((a, b))))]

    def clusters(self):
        segment_matches = {}
        # I create a map containing all matches (value) of a given segment (including itself)
        for k, v in self.all:
            segment_matches[k] = v
        # cluster identifier
        cluster = 0
        clusters = {}
        while segment_matches:
            temp_matches = iter(list(segment_matches.items()))
            # remove and store all matches from this segment (set A)
            segment_id, _ = next(temp_matches)
            clusters[cluster] = segment_matches.pop(segment_id)
            while clusters[cluster].intersection(segment_matches):
                # If there is an intersection between set A and set B
                # it is understood that A is equal to B
                for k in clusters[cluster].intersection(segment_matches):
                    # for each item that is in A and B at the same time I add A and remove it from B
                    clusters[cluster].update(segment_matches.pop(k))
            cluster += 1
        return clusters


class Tokenizer:
    _n_unks = 10
    __unks = dict({f'{{{i}}}': i for i in range(_n_unks)})
    __unks.update(invert_dict(__unks))

    def __init__(self, data: Union[List[str], dict], preprocess_function=None, load_mode=False, use_unk=True):
        self._temp_unks = dict()
        self._hash = self.new_hash  # default
        self._unk_memory_max = 10000  # prevents memory leak
        self._use_unk = use_unk
        self._preprocess_function = preprocess_function
        self._warning_not_use_unk = False
        if isinstance(data, dict) and load_mode:
            logger.info("Building from file.")
            keys = data.keys()
            assert '_metadata' in keys and 'data' in keys, 'Invalid content.'
            for k, v in data['_metadata'].items():
                if k == '_preprocess_function':
                    # load function
                    if v is not None:
                        v = pickle.loads(string_to_literal(v))
                setattr(self, k, v)
            self._uniques = set(data['data'].values())
            self._index_to_item = {int(k): v for k, v in data['data'].items()}
        else:
            self._uniques = self.get_uniques(data)
            self._index_to_item = dict(enumerate(self._uniques, self._n_unks))
        self._item_to_index = invert_dict(self._index_to_item)

    @property
    def preprocess_function(self):
        return self._preprocess_function or (lambda x: x)

    @property
    def last_index(self):
        return self._n_unks + len(self._index_to_item) - 1

    def add_item(self, item):
        index_ = self.last_index + 1
        self._index_to_item[index_] = item
        self._item_to_index[item] = index_

    @property
    def unks(self):
        return self.__unks

    @property
    def unk_memory(self):
        return self._temp_unks

    @property
    def hash_default(self):
        return self._hash

    @property
    def new_hash(self):
        return secrets.token_hex(7)

    @classmethod
    def normalize(cls, data) -> List[Any]:
        if data is None:
            data = []
        if isinstance(data, str):
            return [data]
        elif isinstance(data, (int, float, bytes)):
            return [data]
        assert is_sequence(data), TypeError(f'this data type is not supported, try sending a {str}, {list} or tuple')
        return data

    def get_uniques(self, values: List[str]) -> set:
        data = self.normalize(values)
        result = []
        for v in data:
            result += v.split()
        return set(map(self.preprocess_function, result))

    def item_index(self, word: str) -> int:
        return self._item_to_index.get(word)

    def index_item(self, index: int) -> str:
        return self._index_to_item.get(index, self.unks.get(index))

    def _encode(self, data: List[str], hash__):
        if hash__ not in self._temp_unks and self._use_unk:
            if len(self._temp_unks) > self._unk_memory_max:
                self._temp_unks = {}
                logger.warning("Memory Leak Detected. Cleaned temp UNK's")
            self._temp_unks[hash__] = {}
        n = 0
        result = []
        for word in map(self.preprocess_function, data):
            index = self.item_index(word)
            if index is None:
                if not self._use_unk:
                    if not self._warning_not_use_unk:
                        logger.warning(
                                "use_unk is False. All unknown item encoded will be added to tokenizer don't forget "
                                "to save your "
                                "tokenizer after encoding.")
                        self._warning_not_use_unk = True
                    self.add_item(word)
                    index = self.last_index
                    result.append(index)
                    continue
                unk = f'{{{n % self._n_unks}}}'
                index = self.unks.get(unk)
                self._temp_unks[hash__].update({(n, f"{word}"): unk})
                n += 1
            result.append(index)
        return result

    def encode(self, data: Union[str, List[str]]) -> Union[Tuple[List[int], str], List[List[int]]]:
        """
        Encodes values in a sequence of numbers

        the hash is used to decode "unks" in the correct order.

        e.g:
            tokenizer = Tokenizer(data=['i like it', 'my name is Joab', 'hello'])
            sequences = tokenizer.encode(data=['hello my friend, how are you?', 'my name is mário'])
            # [([9, 7, 15, 10, 16, 5], 'e9bc59cb0d1564'), ([7, 13, 2, 15], '9f92140ebb0e19')]

        """
        result = []
        for sentence in self.normalize(data):
            assert isinstance(sentence, str), "send List[str] or str"
            if not self._use_unk:
                result.append(self._encode(sentence.split(), None))
                continue
            __hash = self.new_hash
            result.append((self._encode(sentence.split(), __hash), __hash))
        return result

    def decode(self, data: Union[List[int], int]):
        return [self.index_item(index) for index in self.normalize(data)]

    def to_json(self, path_: str):
        try:
            preprocess_function = str(pickle.dumps(self._preprocess_function)) if self._preprocess_function else None
        except Exception as err:
            raise Exception(f'Error on preprocess function save: {err}')
        use_unk = self._use_unk
        tokenizer_data = {'_metadata': {'_preprocess_function': preprocess_function, '_use_unk': use_unk},
                          'data':      self._index_to_item
                          }
        FileIO.create(path_, tokenizer_data).save(exist_ok=True)

    @classmethod
    def load_from_json(cls, path_: str):
        data = FileIO.load(path_)
        return cls(data.data, load_mode=True)

    def replace_unks(self, sentence: str, hash_):
        assert isinstance(sentence, str), 'expected a string.'
        try:
            _temp_unks = self._temp_unks[hash_].copy()
            if not _temp_unks:
                return sentence
            for (indx, word), unk in _temp_unks.items():  # cannot have an exception
                sentence = sentence.replace(unk, word, 1)
                self._temp_unks[hash_].pop((indx, word))
            self._temp_unks.pop(hash_)
        except KeyError as err:
            logger.error(
                    msg=f"{err}: There's something wrong open please issue "
                        f"https://github.com/jlsneto/cereja/issues/new?template=bug-report.md")
        return sentence


class TfIdf:

    def __init__(self, sentences: List[str], language: str = 'english', punctuation: str = None,
                 stop_words: List[str] = None):
        self._sentences = self.clean_sentences(sentences,
                                               language=language,
                                               punctuation=punctuation,
                                               stop_words=stop_words)
        self._corpus_bow = self._corpus_bag_of_words(self.sentences)
        self._idf = self._compute_idf(self.sentences)

    @property
    def sentences(self):
        return self._sentences

    @property
    def corpus_bow(self):
        return self._corpus_bow

    @property
    def idf(self):
        return self._idf

    @classmethod
    def sentence_bag_of_words(cls, sentence: str) -> List[str]:
        return sentence.split()

    @classmethod
    def _clean_sentence(cls, sentence: str, language: str = 'english', punctuation: str = None,
                        stop_words: List[str] = None) -> str:
        sentence = replace_english_contractions(sentence) if language == 'english' else sentence
        sentence = remove_punctuation(sentence, punctuation=punctuation)
        sentence = remove_stop_words(sentence, language=language, stop_words=stop_words)
        return sentence.lower()

    @classmethod
    def _corpus_bag_of_words(cls, sentences: List[str]):
        corpus_bow = {word.lower() for sentence in sentences for word in sentence.split()}
        print(f'{len(corpus_bow)} words on corpus')
        return corpus_bow

    @classmethod
    def _sentence_num_of_words(cls, sentence_bow: List[str]) -> Dict[str, int]:
        num_of_words = dict.fromkeys(sentence_bow, 0)
        for w in sentence_bow:
            num_of_words[w] += 1
        return num_of_words

    def _compute_idf(self, sentences: List[str]) -> Dict[str, int]:
        n = len(sentences)
        print('Computing idf...')
        idf_dict = dict.fromkeys(self.corpus_bow, 0.0)
        for sentence in sentences:
            num_of_words = self._sentence_num_of_words(self.sentence_bag_of_words(sentence))
            for word, val in num_of_words.items():
                if val > 0:
                    idf_dict[word] += 1
        for word, val in idf_dict.items():
            idf_dict[word] = math.log(n / (val + 1))
        print('idf computed!')
        return idf_dict

    @classmethod
    def clean_sentences(cls, sentences: List[str], language: str = 'english', punctuation: str = None, \
                        stop_words: List[str] = None) -> List[str]:
        return [cls._clean_sentence(sentence.lower(),
                                    language=language,
                                    punctuation=punctuation,
                                    stop_words=stop_words) for sentence in sentences]

    @classmethod
    def ordered_tf_idf(cls, sentence_tf_idf: Set[Tuple[str, float]], reverse=True):
        return sorted([word_score for word_score in sentence_tf_idf], key=lambda x: x[1], reverse=reverse)

    @classmethod
    def sentence_tf(cls, sentence_num_of_words: Dict[str, int],
                    sentence_bag_of_words: List[str]) -> Dict[str, float]:
        tf_dict = {}
        bow_count = len(sentence_bag_of_words)
        for word, count in sentence_num_of_words.items():
            tf_dict[word] = count / float(bow_count) if float(bow_count) else 0
        return tf_dict

    def sentence_tf_idf(self, sentence: str, language: str = 'english', punctuation: str = None,
                        stop_words: List[str] = None,
                        use_filter: bool = True) -> Union[Dict[str, float], Set[Tuple[str, float]]]:
        tf_idf = {}
        sentence = self._clean_sentence(sentence, language=language, punctuation=punctuation, stop_words=stop_words)
        sentence_bow = self.sentence_bag_of_words(sentence)
        sentence_now = self._sentence_num_of_words(sentence_bow)
        sentence_tf = self.sentence_tf(sentence_now, sentence_bow)
        for word, val in sentence_tf.items():
            tf_idf[word] = val * self.idf[word]
        tf_idf = set(filter(lambda x: x[1], tf_idf.items())) if use_filter else tf_idf
        return tf_idf

    def inverse_data_frequency_order(self, reverse=False):
        return sorted([(w, idf) for w, idf in self.idf.items()], key=lambda x: x[1], reverse=reverse)


class DataGenerator:
    def __init__(self, data, use_random=False):
        self._data = data
        self._use_random = use_random

    @thread_safe_generator
    def take(self, batch_size=1):
        """
        infinite loop on data

        @param batch_size: is a integer
        @return: batch of data
        """
        assert batch_size <= len(self._data), f'batch_size > data length! Send value <= {len(self._data)}'
        data = iter(self._data)
        while True:
            result = []
            if self._use_random:
                result += random.sample(self._data, k=batch_size)
            else:
                for _ in range(batch_size):
                    try:
                        result.append(next(data))
                    except StopIteration:
                        data = iter(self._data)
                        result.append(next(data))
            yield result


if __name__ == '__main__':
    tokenizer = Tokenizer(data=['i like it', 'my name is Joab', 'hello'])
    sequences = tokenizer.encode(data=['hello my friend, how are you?', 'my name is joab'])
    decoded = []
    print(sequences)
    for encoded_sequence, hash_ in sequences:
        dec = ' '.join(tokenizer.decode(encoded_sequence))
        print(dec)
        decoded.append(tokenizer.replace_unks(dec, hash_))

    print(decoded)
