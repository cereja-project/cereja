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
import secrets
import math
from collections import Counter
from typing import Optional, Sequence, Dict, Any, List, Union, Tuple, Set

from cereja.array import is_iterable, is_sequence
from cereja.file.core import JsonFile
from cereja.utils import invert_dict
from cereja.mltools.preprocess import remove_punctuation, remove_stop_words, \
    replace_english_contractions

__all__ = ['ConnectValues', 'Freq', 'Tokenizer', 'TfIdf']
logger = logging.Logger(__name__)


class Freq(Counter):
    def __init__(self, data: Optional[Sequence] = ()):
        assert is_iterable(data), "Isn't iterable."
        self._elements_size = None
        super().__init__(data)

    @property
    def probability(self):
        """
        Return dict with percent
        """
        return dict(zip(self.keys(), map(self.item_prob, self.most_common())))

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
        if max_freq is not None or min_freq is not None:
            assert isinstance(max_freq, int), TypeError(f"freq {type(max_freq)} != {int}")
            assert isinstance(min_freq, int), TypeError(f"freq {type(min_freq)} != {int}")
            min_freq = max(1, min_freq)
            max_freq = max(1, max_freq)
            assert min_freq <= max_freq, 'min_freq > max_freq'
            query = filter(lambda item: max_freq >= item[1] >= min_freq, query)
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
        content = self.probability if probability else self
        JsonFile(path_=path_, data=content).save(**kwargs)


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

    def __init__(self, data: List[str]):
        self._lang_data = self.language_data(data)
        self._index_to_word = dict(enumerate(self._lang_data.words, self._n_unks))
        self._word_to_index = invert_dict(self._index_to_word)
        self._temp_unks = dict()
        self._hash = self.new_hash  # default

    @classmethod
    def language_data(cls, data):
        # because circular import
        # TODO: fix me
        from cereja.mltools.pln import LanguageData
        return LanguageData(data)

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

    def word_index(self, word: str) -> int:
        return self._word_to_index.get(word)

    def index_word(self, index: int) -> str:
        return self._index_to_word.get(index, self.unks.get(index))

    @classmethod
    def normalize(cls, data) -> List[Any]:
        data = data or []
        if isinstance(data, str):
            return [data]
        elif isinstance(data, (int, float, bytes)):
            return [data]
        assert is_sequence(data), TypeError(f'this data type is not supported, try sending a {str}, {list} or tuple')
        return data

    def _encode(self, data: List[str], hash__):
        if hash__ not in self._temp_unks:
            self._temp_unks[hash__] = {}
        n = 0
        result = []
        for word in self._lang_data.preprocess(data):
            index = self.word_index(word)
            if index is None:
                unk = f'{{{n % self._n_unks}}}'
                index = self.unks.get(unk)
                self._temp_unks[hash__].update({(n, f"{word}"): unk})
                n += 1
            result.append(index)
        return result

    def encode(self, data: Union[str, List[str]]) -> List[Tuple[List[int], str]]:
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
            __hash = self.new_hash
            result.append((self._encode(sentence.split(), __hash), __hash))
        return result

    def decode(self, data: Union[List[int], int]):
        return [self.index_word(index) for index in self.normalize(data)]

    def to_json(self, path_: str):
        JsonFile(path_, self._index_to_word).save(exist_ok=True)

    def replace_unks(self, sentence: str, hash_):
        assert isinstance(sentence, str), 'expected a string.'
        try:
            _temp_unks = self._temp_unks[hash_].copy()
            if not _temp_unks:
                return sentence
            for (indx, word), unk in _temp_unks.items():  # cannot have an exception
                sentence = sentence.replace(unk, word)
                self._temp_unks[hash_].pop((indx, word))
            self._temp_unks.pop(hash_)
        except KeyError as err:
            logger.error(
                    msg=f"{err}: There's something wrong open please issue "
                        f"https://github.com/jlsneto/cereja/issues/new?template=bug-report.md")
        return sentence


class TfIdf:

    def __init__(self, sentences: List[str]):
        self._sentences = self.clean_sentences(sentences)
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
    def _clean_sentence(cls, sentence: str, language: str = 'english') -> str:
        sentence = replace_english_contractions(sentence) if language == 'english' else sentence
        sentence = remove_punctuation(sentence)
        sentence = remove_stop_words(sentence, language=language)
        return sentence.lower()

    @classmethod
    def _corpus_bag_of_words(cls, sentences: List[str]):
        corpus_bow = {word.lower() for sentence in sentences for word in sentence.split()}
        print(f'{len(corpus_bow)} words on corpus')
        return corpus_bow

    def _sentence_num_of_words(self, sentence_bow: List[str]) -> Dict[str, int]:
        num_of_words = dict.fromkeys(self.corpus_bow, 0)
        for w in sentence_bow:
            num_of_words[w] += 1
        return num_of_words

    def _compute_idf(self, sentences: List[str]) -> Dict[str, Union[int, float]]:
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
    def clean_sentences(cls, sentences: List[str], language: str = 'english') -> List[str]:
        return [cls._clean_sentence(sentence, language) for sentence in sentences]

    @classmethod
    def ordered_tf_idf(cls, sentence_tf_idf: Set[Tuple[str, float]], reverse=True):
        return sorted([word_score for word_score in sentence_tf_idf], key=lambda x: x[1], reverse=reverse)

    @classmethod
    def sentence_tf(cls, sentence_num_of_words: Dict[str, int], sentence_bag_of_words: List[str]) -> Dict[str, float]:
        tf_dict = {}
        bow_count = len(sentence_bag_of_words)
        for word, count in sentence_num_of_words.items():
            tf_dict[word] = count / float(bow_count) if float(bow_count) else 0
        return tf_dict

    def sentence_tf_idf(self, sentence: str, language: str = 'english', use_filter: bool = True) -> \
            Union[Dict[str, float], Set[Tuple[str, float]]]:
        tf_idf = {}
        sentence = self._clean_sentence(sentence, language=language)
        sentence_bow = self.sentence_bag_of_words(sentence)
        sentence_now = self._sentence_num_of_words(sentence_bow)
        sentence_tf = self.sentence_tf(sentence_now, sentence_bow)
        for word, val in sentence_tf.items():
            tf_idf[word] = val * self.idf[word]
        tf_idf = set(filter(lambda x: x[1], tf_idf.items())) if use_filter else tf_idf
        return tf_idf

    def inverse_data_frequency_order(self, reverse=False):
        return sorted([(w, idf) for w, idf in self.idf.items()], key=lambda x: x[1], reverse=reverse)
