import unittest

from cereja import utils
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
        pass

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
