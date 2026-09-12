"""Private resolver contracts: real object identity, failures, and discovery."""

import io
import sys
import types
import unittest

from cereja._lazy import attach
from cereja._terminal import _supports_non_bmp


class LazyResolverTest(unittest.TestCase):
    def module(self, exports):
        module = types.ModuleType('_lazy_test_facade')
        attach(vars(module), exports)
        return module

    def test_returns_and_caches_the_actual_object(self):
        module = self.module({'number': ('builtins', 'int'), 'runtime': ('sys', None)})
        self.assertNotIn('number', vars(module))
        self.assertIs(module.number, int)
        self.assertIs(vars(module)['number'], int)
        self.assertIs(module.runtime, sys)
        module.number = str
        self.assertIs(module.number, str)

    def test_unknown_name_does_not_attempt_an_import(self):
        module = self.module({'known': ('_nonexistent_cereja_test_module', None)})
        before = set(sys.modules)
        with self.assertRaisesRegex(AttributeError, '_lazy_test_facade.*unknown'):
            module.unknown
        self.assertEqual(set(sys.modules), before)
        self.assertIn('known', dir(module))
        self.assertNotIn('known', vars(module))

    def test_dependency_failure_is_not_masked_or_cached(self):
        module = self.module({'broken': ('_nonexistent_cereja_test_module', None)})
        with self.assertRaises(ModuleNotFoundError) as caught:
            module.broken
        self.assertEqual(caught.exception.name, '_nonexistent_cereja_test_module')
        self.assertNotIn('broken', vars(module))

    def test_missing_target_attribute_is_not_cached(self):
        module = self.module({'broken': ('sys', '_nonexistent_cereja_attribute')})
        with self.assertRaises(AttributeError):
            module.broken
        self.assertNotIn('broken', vars(module))

    def test_terminal_probe_handles_real_encodings_without_writing(self):
        for encoding, expected in (('utf-8', True), ('ascii', False), ('cp1252', False), ('not-a-codec', False)):
            with self.subTest(encoding=encoding):
                self.assertIs(_supports_non_bmp(types.SimpleNamespace(encoding=encoding)), expected)
        stream = io.StringIO()
        self.assertTrue(_supports_non_bmp(stream))
        self.assertEqual(stream.getvalue(), '')
        self.assertFalse(_supports_non_bmp(None))


if __name__ == '__main__':
    unittest.main()
