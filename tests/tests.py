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

import os
import time
import unittest
import logging

from cereja.array import group_items_in_batches, is_iterable, remove_duplicate_items, flatten, \
    is_sequence, array_gen, get_shape, Matrix
from cereja.array import prod
from cereja.mathtools import theta_angle
from cereja.config.cj_types import Number
from cereja.mltools import Corpus
from cereja.mltools.pln import LanguageData
from cereja.display import State, Progress
from cereja.system._path import Path
from cereja.system.unicode import Unicode
from cereja.utils import CjTest
from cereja.hashtools import base64_decode, base64_encode, is_base64, md5

logger = logging.getLogger(__name__)


class UtilsTestCase(unittest.TestCase):

    def setUp(self) -> None:
        self.shapes = (2, 2, 3), (1, 3, 2, 1, 1), (2, 1, 1)
        self.sequences = [
            [[[0.0, 0.0, 0.0], [0.0, 0.0, 0.0]], [[0.0, 0.0, 0.0], [0.0, 0.0, 0.0]]],

            [[[[[0.0]], [[0.0]]], [[[0.0]], [[0.0]]], [[[0.0]], [[0.0]]]]],

            [[[0.]], [[0.]]]
        ]

    def test_group_items_in_batches(self):
        tests = [([1, 2, 3, 4, 5, 6], 3, [[1, 2, 3], [4, 5, 6]]),
                 ([1, 2, 3, 4, 5, 6], 2, [[1, 2], [3, 4], [5, 6]]),
                 ([1, 2, 3, 4, 5, 6], 0, [1, 2, 3, 4, 5, 6]),
                 ([1, 2, 3, 4, 5, 6, 7], 3, [[1, 2, 3], [4, 5, 6], [7, 0, 0]]),
                 ]

        for test_value, items_per_batch, expected_value in tests:
            msg = f"""Test failed for values {test_value}"""
            result = group_items_in_batches(test_value, items_per_batch, 0)
            self.assertEqual(result, expected_value, msg)

        tests_raise = [([1, 2, 3, 4, 5, 6], -1, ValueError),
                       ([1, 2, 3, 4, 5, 6], 'sd', TypeError),
                       ([1, 2, 3, 4, 5, 6], 7, ValueError),
                       ]
        for test_value, items_per_batch, expected_error in tests_raise:
            self.assertRaises(expected_error, group_items_in_batches, test_value, items_per_batch)

    def test_is_iterable(self):
        self.assertFalse(is_iterable(1))
        self.assertTrue(is_iterable('hi'))
        self.assertTrue(is_iterable([]))

    def test_theta_angle(self):
        u = (2, 2)
        v = (0, -2)
        self.assertEqual(theta_angle(u, v), 135.0)

    def test_remove_duplicate_items(self):
        test_values_sample_list = [([1, 2, 1, 2, 1], [1, 2]),
                                   (['hi', 'hi', 'ih'], ['hi', 'ih']),
                                   ]
        test_values_list_of_list = [([['hi'], ['hi'], ['ih']], [['hi'], ['ih']]),
                                    ([[1, 2, 1, 2, 1], [1, 2, 1, 2, 1], [1, 2, 1, 2, 3]],
                                     [[1, 2, 1, 2, 1], [1, 2, 1, 2, 3]])
                                    ]

        for test_value, expected_value in test_values_sample_list:
            self.assertEqual(remove_duplicate_items(test_value), expected_value)

        for test_value, expected_value in test_values_list_of_list:
            self.assertEqual(remove_duplicate_items(test_value), expected_value)

    def test_flatten(self):
        sequence = [[1, 2, 3], [], [[2, [3], 4], 6]]
        expected_value = [1, 2, 3, 2, 3, 4, 6]
        self.assertEqual(flatten(sequence), expected_value)

        max_recursion = 2
        expected_value = [1, 2, 3, 2, [3], 4, 6]
        self.assertEqual(flatten(sequence, max_recursion=max_recursion), expected_value)

    def test_is_sequence(self):
        sequence = [[1, 2, 3], [], [[2, [3], 4], 6]]
        self.assertTrue(is_sequence(sequence))

        self.assertFalse(is_sequence('hi cereja'))
        self.assertTrue(is_sequence(dict({'k1': 1, 'k2': 2}).keys()))

    def test_array_gen(self):
        for args, expected in zip(self.shapes, self.sequences):
            data = array_gen(args)
            self.assertEqual(data, expected)

        with_kwargs = [({"shape": (2, 1, 1), "v": ['hail', 'pythonics!']}, [[['hail']], [['pythonics!']]])
                       ]

        for kwargs, expecteds in with_kwargs:
            result = array_gen(**kwargs)
            self.assertEqual(result, expecteds)

    def test_get_shape(self):
        for expected_shape, seq in zip(self.shapes, self.sequences):
            shape_received = get_shape(seq)
            sequence_length = len(flatten(seq))
            self.assertEqual(sequence_length, prod(shape_received), msg=f"array shape {shape_received} is inconsistent")
            self.assertEqual(shape_received, expected_shape)

    def test_randn(self):
        logger.warning("Awaiting tests!")

    def test_matrix(self):
        a = Matrix([[1, 2, 3], [1, 2, 3]])
        b = Matrix([[1, 2, 3], [1, 2, 3]])
        expected = Matrix([[1.0, 1.0, 1.0],
                           [1.0, 1.0, 1.0]])
        self.assertTrue((a / b) == expected)


class PathTest(unittest.TestCase):
    def test_sanity(self):
        self.assertEqual(Path(__file__).parent, Path(os.path.realpath(__file__)).parent)
        p_test = 'cereja/test/sanity'
        p = Path(p_test)
        self.assertTrue(p.name, 'sanity')
        self.assertTrue(p.parent.name, 'test')
        self.assertTrue(p == p_test)
        self.assertTrue('sanity' in p)
        p = p + ['con', 'cat']
        p_test = Path('cereja/test/sanity').join('con', 'cat')
        self.assertEqual(p_test.parts[-2:], ('con', 'cat'))
        self.assertTrue(p == p_test)
        self.assertListEqual(Path.list_dir(Path(__file__).parent, only_name=True),
                             list(map(lambda x: x.rsplit('.')[0], os.listdir(Path(__file__).parent))))


class UnicodeToolTestCase(unittest.TestCase):
    def test_sanity(self):
        unicode_ = 0x1F352
        # instance
        instance_ = Unicode.parse(unicode_)
        # expected
        test_ = CjTest(instance_)
        test_.add_check(test_.name == "CHERRIES",
                        test_.value == '\U0001F352',
                        test_.decimal == 127826,
                        test_.bin == "0b11111001101010010",
                        test_.hex == "0x1f352",
                        test_.oct == '0o371522'
                        )

        test_.check_all()


class CorpusTestCase(unittest.TestCase):
    def test_sanity(self):
        source = ['how are you?', 'my name is Joab', 'I like coffee', 'how are you joab?', 'how', 'we are the world']
        target = ['como você está?', 'meu nome é Joab', 'Eu gosto de café', 'Como você está joab?', 'como',
                  'Nós somos o mundo']

        corpus = Corpus(source_data=source, target_data=target, source_name='en', target_name='pt')
        self.assertEqual(str(corpus), 'Corpus(examples: 6 - source_vocab_size: 13 - target_vocab_size:15)')
        self.assertEqual(str(corpus.source), 'LanguageData(examples: 6 - vocab_size: 13)')
        self.assertEqual(str(corpus.target), 'LanguageData(examples: 6 - vocab_size: 15)')

        self.assertDictEqual(dict(corpus.source.phrases_freq.items()),
                             {'how are you': 1, 'my name is joab': 1, 'i like coffee': 1, 'how are you joab': 1,
                              'how':         1, 'we are the world': 1})

        self.assertDictEqual(dict(corpus.source.words_freq.items()),
                             {'how':  3, 'are': 3, 'you': 2, 'joab': 2, 'my': 1, 'name': 1, 'is': 1, 'i': 1,
                              'like': 1, 'coffee': 1, 'we': 1, 'the': 1, 'world': 1})
        self.assertDictEqual(dict(corpus.target.phrases_freq.items()),
                             {'como você está':      1, 'meu nome é joab': 1, 'eu gosto de café': 1,
                              'como você está joab': 1, 'como': 1, 'nós somos o mundo': 1})
        self.assertDictEqual(dict(corpus.target.words_freq.items()),
                             {'como':  3, 'você': 2, 'está': 2, 'joab': 2, 'meu': 1, 'nome': 1, 'é': 1, 'eu': 1,
                              'gosto': 1, 'de': 1, 'café': 1, 'nós': 1, 'somos': 1, 'o': 1, 'mundo': 1})


class ProgressTestCase:
    def test_sanity(self):
        progress = Progress("Cereja Progress Test")
        progress_test = CjTest(progress)

        class MyCustomSate(State):

            def display(self, current_value: Number, max_value: Number, current_percent: Number, time_it: Number,
                        n_times: int) -> str:
                return "RUNNING"

            def done(self, current_value: Number, max_value: Number, current_percent: Number, time_it: Number,
                     n_times: int) -> str:
                return "FINISHED"

        state = MyCustomSate()
        progress.add_state(state)

        progress_test.add_check(
                progress_test.name == "Cereja Progress Test",
                progress_test._awaiting_update == True,
                progress_test._show == False,
                progress_test.started_time == None,
                progress_test._err == False,
                progress_test._was_done == False,
                progress_test._with_context == False
        )
        progress_test.check_all()

        with Progress("p") as p:
            test_p = CjTest(p)
            test_p.add_check(test_p.name == 'p',
                             test_p._with_context == True,
                             test_p.started == True,
                             test_p._awaiting_update == True,
                             test_p.max_value == 100
                             )
            test_p.check_all()
            time.sleep(3)
            p_iterator = p(range(1, 500))
            test_p.add_check(test_p.max_value == 499)
            test_p.check_all()
            for i in p_iterator:
                time.sleep(1 / i)
                if i == 1:
                    test_p.add_check(
                            test_p._awaiting_update == False,
                            test_p.max_value == 499,
                            test_p._current_value == 2
                    )
                    test_p.check_all()

            for i in p(range(1, 500)):
                time.sleep(1 / i)

            for i in p(range(1, 500)):
                time.sleep(1 / i)


class LanguageDataTestCase(unittest.TestCase):
    def test_sanity(self):
        data = LanguageData(['how are you?', 'I like it', 'cereja', 'cherry'])
        self.assertEqual(data.synergy(['how are you?', 'I like it', 'cereja', 'cherry']), 1)
        self.assertEqual(data.synergy(['how are you?', 'I like it', 'cereja']), 0.875)


class HashToolsTestCase(unittest.TestCase):
    def test_sanity(self):
        vals = ([1, 2, '3'],
                (1, '2', '1'),
                {'hi': 1, 'hello': 3, 'deep': {'oi'}},
                1,
                2,
                b'a')
        for val in vals:
            res = base64_encode(val)
            self.assertTrue(is_base64(res))
            self.assertEqual(val, base64_decode(res))

        self.assertEqual('fc4d5dcfe7146d09b7fbad980fb90797', md5('set the alarm clock for seven of the clock .'))


if __name__ == '__main__':
    unittest.main()
