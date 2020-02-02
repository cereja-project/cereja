import unittest
import logging

from cereja.arraytools import group_items_in_batches, is_iterable, remove_duplicate_items, theta_angle, flatten, \
    is_sequence, array_gen, get_shape

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


if __name__ == '__main__':
    unittest.main()
