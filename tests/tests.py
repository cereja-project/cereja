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

from cereja.arraytools import group_items_in_batches, is_iterable, remove_duplicate_items, theta_angle, flatten, \
    is_sequence, array_gen, get_shape
from cereja import filetools
from cereja.cj_types import Number
from cereja.datatools import Corpus
from cereja.datatools.pln import separate
from cereja.display import State, Progress, StateBar, StatePercent, StateTime
from cereja.path import Path
from cereja.unicode import Unicode
from cereja.utils import CjTest

logger = logging.getLogger(__name__)


class UtilsTestCase(unittest.TestCase):

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

    def test_array_gen(self):
        shapes = (2, 2, 3), (1, 3, 2, 1, 1), (2, 1, 1)
        sequences_expecteds = [
            [[[0.0, 0.0, 0.0], [0.0, 0.0, 0.0]], [[0.0, 0.0, 0.0], [0.0, 0.0, 0.0]]],

            [[[[[0.0]], [[0.0]]], [[[0.0]], [[0.0]]], [[[0.0]], [[0.0]]]]],

            [[[0.]], [[0.]]]
        ]

        for args, expecteds in zip(shapes, sequences_expecteds):
            data = array_gen(args)
            self.assertEqual(data, expecteds)

        with_kwargs = [({"shape": (2, 1, 1), "v": ['hail', 'pythonics!']}, [[['hail']], [['pythonics!']]])
                       ]

        for kwargs, expecteds in with_kwargs:
            result = array_gen(**kwargs)
            self.assertEqual(result, expecteds)

    def test_get_shape(self):
        sequences = [
            [[[0.0, 0.0, 0.0], [0.0, 0.0, 0.0]], [[0.0, 0.0, 0.0], [0.0, 0.0, 0.0]]],

            [[[[[0.0]], [[0.0]]], [[[0.0]], [[0.0]]], [[[0.0]], [[0.0]]]]],

            [[[0.]], [[0.]]]
        ]
        shapes_expecteds = (2, 2, 3), (1, 3, 2, 1, 1), (2, 1, 1)

        for seq, expected_shape in zip(sequences, shapes_expecteds):
            shape_received = get_shape(seq)
            self.assertEqual(shape_received, expected_shape)

    def test_randn(self):
        logger.warning("Awaiting tests!")


class FileToolsTestCase(unittest.TestCase):

    def battery_tests(self, cj_file_instance, expected_values):
        self.assertEqual(cj_file_instance.new_line_sep_repr, expected_values[0])
        self.assertEqual(cj_file_instance.file_name, expected_values[1])
        self.assertEqual(cj_file_instance.dir_name, expected_values[2])
        self.assertEqual(cj_file_instance.is_empty, expected_values[3])
        self.assertEqual(cj_file_instance.string, expected_values[4])
        self.assertEqual(cj_file_instance.n_lines, expected_values[5])

    def test_file_obj(self):
        content_file = [1, 2, 3]
        file = filetools.File('cereja/teste.py', content_file)
        normalized_data = f'{filetools.LF}'.join(filetools.FileBase.normalize_data(content_file))
        expected_values = ["LF", "teste.py", 'cereja', False, normalized_data, len(content_file), 0.006]
        self.battery_tests(file, expected_values)

        file = file.replace_file_sep("CRLF", save=False)
        normalized_data = f'{filetools.CRLF}'.join(filetools.FileBase.normalize_data(content_file))
        expected_values[0] = "CRLF"
        expected_values[4] = normalized_data
        self.battery_tests(file, expected_values)

        file = file.replace_file_sep("CR", save=False)
        normalized_data = f'{filetools.CR}'.join(filetools.FileBase.normalize_data(content_file))
        expected_values[0] = "CR"
        expected_values[4] = normalized_data
        self.battery_tests(file, expected_values)

    def test_base_sanity(self):
        data = ['first line', 'second line', 'third line']
        file = filetools.File('test.txt', data)
        self.assertTrue(str(file) == "FileBase<test.txt>")
        self.assertEqual(file.data, ['first line', 'second line', 'third line'])
        for line in file:
            pass

        self.assertEqual(file[0], 'first line')
        self.assertEqual(file[:3], ['first line', 'second line', 'third line'])

        # Insert Data
        file.insert(0, 'other line')
        file.insert(0, 'other line2')
        self.assertEqual(file.data, ['other line2', 'other line', 'first line', 'second line', 'third line'])
        # it is allowed to use index assignment
        file[0] = 'other line'

        # Data Recovery
        file.undo()  # You selected amendment 3
        self.assertEqual(file.data, ['other line2', 'other line', 'first line', 'second line', 'third line'])
        file.redo()  # You selected amendment 4
        self.assertEqual(file.data,
                         ['other line', 'other line2', 'other line', 'first line', 'second line', 'third line'])

    def test_json_sanity(self):
        data = {'key': 'value', 'key2': 'value2', 'key3': 'value3'}
        file = filetools.File('test.json', data)
        self.assertEqual(str(file), 'JsonFile<test.json>')
        self.assertEqual(file.data, {'key': 'value', 'key2': 'value2', 'key3': 'value3'})

        # Iterable
        for key, value in file.items():
            pass

        self.assertEqual(file['key'], 'value')

        # Insert Data
        file['key4'] = 'value4'
        self.assertEqual(file.data, {'key': 'value', 'key2': 'value2', 'key3': 'value3', 'key4': 'value4'})

        # Data Recovery
        file.undo()  # You selected amendment 1
        self.assertEqual(file.data, {'key': 'value', 'key2': 'value2', 'key3': 'value3'})
        file.redo()  # You selected amendment 2
        self.assertEqual(file.data, {'key': 'value', 'key2': 'value2', 'key3': 'value3', 'key4': 'value4'})

    def test_csv_sanity(self):
        file = filetools.CsvFile('test.csv', fieldnames=['col1', 'col2', 'col3'])  # ram only, not yet saved
        self.assertEqual(str(file), "CsvFile<test.csv>")
        file.add_row([1, 2, 3])
        self.assertEqual(file.lines, [[1, 2, 3]])
        file.add_row([1, 2], fill_with=0)
        self.assertEqual(file.lines, [[1, 2, 3], [1, 2, 0]])

        # convert to dict
        self.assertEqual(file.to_dict(), {'col1': (1, 1), 'col2': (2, 2), 'col3': (3, 0)})

        # or get generation row by row with col
        self.assertEqual(list(file.data), [{'col1': 1, 'col2': 2, 'col3': 3}, {'col1': 1, 'col2': 2, 'col3': 0}])

        # Iterable
        for row in file:
            pass

        # indexing col values
        self.assertEqual(file['col1'], (1, 1))
        # or use index and get a row
        self.assertEqual(file[0], [1, 2, 3])
        self.assertEqual(file.flatten(), [1, 2, 3, 1, 2, 0])

    def get_file(self):
        content_file = [1, 2, 3]
        file = filetools.File(f"{os.path.dirname(__file__)}.txt", content_file)
        return file

    def test_insertion_content(self):
        file = self.get_file()
        file.insert(3, [4, 5])
        self.assertEqual(file.lines, ["1", "2", "3", "4", "5"])

    def test_prevent_data_loss(self):
        file = self.get_file()
        original_lines = file.lines.copy()
        file.insert(0, [1, 3, 4, 5])
        file.insert(0, 2)
        file.undo()
        file.undo()
        self.assertEqual(file.lines, original_lines)
        file.redo()
        self.assertEqual(file.lines, ['1', '3', '4', '5'] + original_lines)
        file.insert(0, [1])
        file.undo()
        self.assertEqual(file.lines, ['1', '3', '4', '5'] + original_lines)

    def test_json_file(self):
        data = [(1, 2), ('four', 4), ('six', 6)]
        expected = {'1': 2, 'four': 4, 'six': 6}

        # Normalize test
        self.assertDictEqual(filetools.JsonFile.normalize_data(data), expected)
        self.assertDictEqual(filetools.JsonFile.normalize_data(expected.items()), expected)
        self.assertDictEqual(filetools.JsonFile.normalize_data(1), {'1': None})
        self.assertDictEqual(filetools.JsonFile.normalize_data(()), {})
        self.assertDictEqual(filetools.JsonFile.normalize_data((1, 2, 3)), {'1': None, '2': None, '3': None})


class PathTest(unittest.TestCase):
    def test_sanity(self):
        p_test = 'cereja/test/sanity'
        p = Path(p_test)
        self.assertTrue(p.name, 'sanity')
        self.assertTrue(p.parent.name, 'test')
        self.assertTrue(p == p_test)
        self.assertTrue('sanity' in p)
        p = p + ['con', 'cat']
        p_test = Path('cereja/test/sanity').join('con', 'cat')
        self.assertTrue(p == p_test)


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


class DataToolsFunctionsTestCase(unittest.TestCase):
    def test_sanity(self):
        self.assertEqual(separate('how are you?', sep='?'), 'how are you ?')
        self.assertEqual(separate('how are you,man?', sep=('?', ','), between_char=True), 'how are you , man ?')
        self.assertEqual(separate('how are! you?'), 'how are ! you ?')


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
                progress_test.states == StateBar, StatePercent, StateTime, state,
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


if __name__ == '__main__':
    unittest.main()
