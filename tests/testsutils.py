import unittest
from collections import OrderedDict

from cereja import utils, rescale_values
from cereja.utils.decorators import singleton


class UtilsTest(unittest.TestCase):

    def test_camel_to_snake(self):
        pass

    def test_class_methods(self):
        pass

    def test_combine_with_all(self):
        pass

    def test_fill(self):
        pass

    def test_get_attr_if_exists(self):
        pass

    def test_get_implements(self):
        pass

    def test_get_instances_of(self):
        pass

    def test_import_string(self):
        pass

    def test_install_if_not(self):
        pass

    def test_invert_dict(self):
        data = {"s": 0, "y": 1, "v": 2, "l": 3, "i": 4, "p": 5, "b": 6, "z": 7, "c": 8, "a": 9, "k": 10, "e": 11,
                "d": 12, "j": 13, "x": 14, "u": 15, "o"
                :    16, "n": 17, "t": 18, "f": 19, "g": 20, "h": 21, "r": 22, "w": 23, "m": 24, "q": 25}
        expected = {0:  's', 1: 'y', 2: 'v', 3: 'l', 4: 'i', 5: 'p', 6: 'b', 7: 'z', 8: 'c', 9: 'a', 10: 'k', 11: 'e',
                    12: 'd', 13: 'j', 14: 'x', 15: 'u', 16: 'o', 17: 'n', 18: 't', 19: 'f', 20: 'g', 21: 'h', 22: 'r',
                    23: 'w', 24: 'm', 25: 'q'}
        self.assertDictEqual(utils.invert_dict(data), expected)

        data = {1: 40, 2: 30, 3: 40, 30: 2}
        expected = {40: [1, 3], 30: 2, 2: 30}
        self.assertEqual(utils.invert_dict(data), expected)

    def test_logger_level(self):
        pass

    def test_module_references(self):
        pass

    def test_obj_repr(self):
        class Repr:
            def __init__(self, a, b, c):
                self.a = a
                self.b = b
                self.c = c

        expected = "Repr (\n    a = 1,\n    b = dict(oi:<class 'int'> ...),\n    c = oi\n    )"
        self.assertEqual(utils.obj_repr(Repr(1, {'oi': 1}, 'oi')), expected)

    def test_rescale_values(self):
        value = list(range(10))
        expected = [0, 0, 0, 1, 1, 2, 2, 3, 3, 4, 4, 5, 5, 6, 6, 7, 7, 8, 8, 9, 9]
        self.assertEqual(rescale_values(value, 21), expected)
        expected = [0, 0, 0, 1, 1, 1, 2, 2, 3, 3, 4, 4, 5, 5, 6, 6, 7, 7, 8, 8, 9, 9]
        self.assertEqual(rescale_values(value, 22), expected)
        expected = [0, 'joab', 'joab', 1, 'joab', 'joab', 2, 'joab', 3, 'joab', 4, 'joab', 5, 'joab', 6, 'joab', 7,
                    'joab', 8, 'joab', 9, 'joab']

        self.assertEqual(rescale_values(value, 22, fill_with='joab'), expected)

        expected = [0, 1, 2, 3, 4, 5, 6, 7, 8, 9, 'joab', 'joab', 'joab', 'joab', 'joab', 'joab', 'joab', 'joab',
                    'joab', 'joab', 'joab', 'joab']

        self.assertEqual(rescale_values(value, 22, fill_with='joab', filling='post'), expected)

        expected = ['joab', 'joab', 'joab', 'joab', 'joab', 'joab', 'joab', 'joab', 'joab', 'joab', 'joab', 'joab', 0,
                    1, 2, 3, 4, 5, 6, 7, 8, 9]

        self.assertEqual(rescale_values(value, 22, fill_with='joab', filling='pre'), expected)

        expected = [0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 1, 2, 3, 4, 5, 6, 7, 8, 9]
        self.assertEqual(rescale_values(value, 22, filling='pre'), expected)

        expected = [0, 1, 2, 3, 4, 5, 6, 7, 8, 9, 9, 9, 9, 9, 9, 9, 9, 9, 9, 9, 9, 9]
        self.assertEqual(rescale_values(value, 22, filling='post'), expected)

        expected = [0, 1.8, 3.6, 5.4, 7.2, 9]
        self.assertEqual(rescale_values(value, 6, True), expected)
        expected = [0, 0.5625, 1.125, 1.6875, 2.25, 2.8125, 3.375, 3.9375, 4.5, 5.0625, 5.625, 6.1875, 6.75, 7.3125,
                    7.875, 8.4375, 9]
        self.assertEqual(rescale_values(value, 17, True), expected)

    def test_can_do(self):
        class _A:
            def _m1(self):
                pass

            def __m2(self):
                pass

            def m(self):
                pass

            @property
            def m1(self):
                return self._m1()

        a_obj = _A()

        self.assertEqual(utils.can_do(a_obj), ['m', 'm1'])

    def test_sample(self):
        data = ['The', 'Cereja', 'is', 'for', 'everyone']

        self.assertEqual(utils.sample(data, 2), ['The', 'Cereja'])
        self.assertEqual(utils.sample(data, 3), ['The', 'Cereja', 'is'])
        self.assertEqual(utils.sample('Cereja'), list('Cereja'))  # test sent string
        self.assertEqual(utils.sample(b'Cereja'), list(b'Cereja'))  # test sent bytes
        self.assertEqual(utils.sample([12], 2), [12])  # test sent number

        data = {'The': 'Cereja', 'is': 'for', 'everyone': None}
        self.assertEqual(utils.sample(data, 2), {'The': 'Cereja', 'is': 'for'})

    def test_set_log_level(self):
        pass

    def test_string_to_literal(self):
        pass

    def test_time_format(self):
        pass

    def test_truncate(self):
        self.assertEqual(utils.truncate("Cereja is fun.", k=3), 'Cer...')
        self.assertEqual(utils.truncate(b"Cereja is fun.", k=3), b'Cer...')
        self.assertEqual(utils.truncate("Cereja is fun.", k=-1), "Cereja is fun.")
        self.assertEqual(utils.truncate("Cereja is fun.", k=1000), "Cereja is fun.")

        self.assertRaises(AssertionError, utils.truncate, 1123)

    def test_type_table_of(self):
        pass

    def test_sort_dict(self):
        val = {0: 1, 1: 2, 2: 1, 3: 4, 4: 1, 5: 43, 6: 1, 7: 10, 8: 22, 9: 0}
        self.assertDictEqual(utils.sort_dict(val), OrderedDict(
                [(0, 1), (1, 2), (2, 1), (3, 4), (4, 1), (5, 43), (6, 1), (7, 10), (8, 22), (9, 0)]))
        self.assertDictEqual(utils.sort_dict(val, by_values=True), OrderedDict(
                [(9, 0), (0, 1), (2, 1), (4, 1), (6, 1), (1, 2), (3, 4), (7, 10), (8, 22), (5, 43)]))
        self.assertDictEqual(utils.sort_dict(val, by_values=True, reverse=True), OrderedDict(
                [(5, 43), (8, 22), (7, 10), (3, 4), (1, 2), (0, 1), (2, 1), (4, 1), (6, 1), (9, 0)]))

        self.assertDictEqual(utils.sort_dict(val, by_keys=True), OrderedDict(
                [(0, 1), (1, 2), (2, 1), (3, 4), (4, 1), (5, 43), (6, 1), (7, 10), (8, 22), (9, 0)]))
        self.assertDictEqual(utils.sort_dict(val, by_keys=True, reverse=True), OrderedDict(
                [(9, 0), (8, 22), (7, 10), (6, 1), (5, 43), (4, 1), (3, 4), (2, 1), (1, 2), (0, 1)]))

    def test_dict_append(self):
        my_dict = {}
        utils.dict_append(my_dict, 'key_eg', 1, 2, 3, 4, 5, 6)
        self.assertDictEqual(my_dict, {'key_eg': [1, 2, 3, 4, 5, 6]})
        my_dict = utils.dict_append(my_dict, 'key_eg', [1, 2])

        self.assertDictEqual(my_dict, {'key_eg': [1, 2, 3, 4, 5, 6, [1, 2]]})

    def test_to_tuple(self):
        data = [[[0.0, 0.0, 0.0], [0.0, 0.0, 0.0], [0.0, 0.0, 0.0]],
                [[0.0, 0.0, 0.0], [0.0, 0.0, 0.0], [0.0, 0.0, 0.0]],
                [[0.0, 0.0, 0.0], [0.0, 0.0, 0.0], [0.0, 0.0, 0.0]]]
        expected = (
            ((0.0, 0.0, 0.0), (0.0, 0.0, 0.0), (0.0, 0.0, 0.0)), ((0.0, 0.0, 0.0), (0.0, 0.0, 0.0), (0.0, 0.0, 0.0)),
            ((0.0, 0.0, 0.0), (0.0, 0.0, 0.0), (0.0, 0.0, 0.0)))

        self.assertEqual(utils.to_tuple(data), expected)

        data = {1: [1, 2, [3, 100, [1000, 30, [12, 3]]], {1: 2, 3: 4}, 4], 2: [1, 2, 3, 4], 3: {1, 2, 3}}
        expected = ((1, (1, 2, (3, 100, (1000, 30, (12, 3))), ((1, 2), (3, 4)), 4)), (2, (1, 2, 3, 4)), (3, (1, 2, 3)))

        self.assertEqual(utils.to_tuple(data), expected)

    def test_chunk(self):
        tests = [([1, 2, 3, 4, 5, 6], 3, [[1, 2, 3], [4, 5, 6]]),
                 ([1, 2, 3, 4, 5, 6], 2, [[1, 2], [3, 4], [5, 6]]),
                 ([1, 2, 3, 4, 5, 6], 0, [[1, 2, 3, 4, 5, 6]]),
                 ([1, 2, 3, 4, 5, 6, 7], 3, [[1, 2, 3], [4, 5, 6], [7, 0, 0]]),
                 ({'oi': 'amigo', 'tudo': 'bem'}, 1, [{'oi': 'amigo'}, {'tudo': 'bem'}]),
                 ({'eu': 'gosto', 'do': 'cereja'}.items(), 1, [[('eu', 'gosto')], [('do', 'cereja')]]),
                 (('eu', 'gosto', 'do', 'cereja'), 2, [('eu', 'gosto'), ('do', 'cereja')])
                 ]

        for test_value, items_per_batch, expected_value in tests:
            print(test_value, items_per_batch, expected_value)
            msg = f"""Test failed for values {test_value}"""
            result = utils.chunk(test_value, batch_size=items_per_batch, fill_with=0)
            self.assertEqual(result, expected_value, msg)

        tests_raise = [
            ([1, 2, 3, 4, 5, 6], 'sd', TypeError)
        ]
        for test_value, items_per_batch, expected_error in tests_raise:
            self.assertRaises(expected_error, utils.chunk, test_value, items_per_batch)


class CjTestTest(unittest.TestCase):

    def test_add_check(self):
        pass

    def test_build_test(self):
        pass

    def test_check_all(self):
        pass

    def test_check_attr(self):
        pass

    def test_parse_attr(self):
        pass

    def test_remove_check(self):
        pass


class SourceTest(unittest.TestCase):

    def test_save(self):
        pass


class DecoratorTest(unittest.TestCase):

    def test_depreciation(self):
        pass

    def test_singleton(self):
        @singleton
        class A:
            def __init__(self, a, b, c=None):
                self.a = a
                self.b = b
                self.c = c

        obj_expected = A(1, b=2, c=3)
        obj_new = A(1, 2)
        self.assertEqual(obj_expected, obj_new, msg="Error on decorator singleton.")

    def test_synchronized(self):
        pass

    def test_thread_safe_generator(self):
        pass

    def test_time_exec(self):
        pass


if __name__ == '__main__':
    unittest.main()
