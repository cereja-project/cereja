import unittest

from cereja import utils


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
        pass

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

    def test_sample(self):
        pass

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


if __name__ == '__main__':
    unittest.main()
