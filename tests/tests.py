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
from cereja import path as cj_path
from cereja.cj_types import Number
from cereja.display import State, Progress, StateBar, StatePercent, StateTime
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
        normalized_data = f'{filetools.LF}'.join(filetools.File.normalize_data(content_file))
        expected_values = ["LF", "teste.py", 'cereja', False, normalized_data, len(content_file), 0.006]
        self.battery_tests(file, expected_values)

        file = file.replace_file_sep("CRLF", save=False)
        normalized_data = f'{filetools.CRLF}'.join(filetools.File.normalize_data(content_file))
        expected_values[0] = "CRLF"
        expected_values[4] = normalized_data
        self.battery_tests(file, expected_values)

        file = file.replace_file_sep("CR", save=False)
        normalized_data = f'{filetools.CR}'.join(filetools.File.normalize_data(content_file))
        expected_values[0] = "CR"
        expected_values[4] = normalized_data
        self.battery_tests(file, expected_values)

    def get_file(self):
        content_file = [1, 2, 3]
        file = filetools.File(os.path.dirname(__file__), content_file)
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
