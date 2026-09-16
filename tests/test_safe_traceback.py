"""Privacy and formatting contracts for exception snapshots."""

import linecache
import unittest
from unittest.mock import patch

from cereja.utils import format_safe_traceback


class SafeTracebackTest(unittest.TestCase):
    def test_syntax_error_hides_source_and_filename_without_mutation(self):
        exc = SyntaxError('invalid', ('/private/build/file.py', 1, 1, 'hidden_source'))
        result = format_safe_traceback(exc)
        self.assertIn('"file.py"', result)
        self.assertNotIn('/private', result)
        self.assertNotIn('hidden_source', result)
        self.assertEqual(exc.filename, '/private/build/file.py')
        self.assertEqual(exc.text, 'hidden_source')

    def test_source_opt_in_and_literal_secrets(self):
        exc = SyntaxError('invalid', ('file.py', 1, 1, 'password = "a.b*"'))
        result = format_safe_traceback(exc, include_source=True, secrets=['a.b*'])
        self.assertIn('password = "<redacted>"', result)
        self.assertNotIn('a.b*', result)

    def test_frames_never_capture_locals_or_lookup_source_by_default(self):
        namespace = {}
        code = compile('local_secret = "hidden_value"\nraise ValueError("bad")',
                       '/private/build/module.py', 'exec')
        try:
            exec(code, namespace)
        except ValueError as exc:
            with patch.object(linecache, 'getline', side_effect=AssertionError):
                result = format_safe_traceback(exc)
        self.assertIn('"module.py"', result)
        self.assertNotIn('hidden_value', result)
        self.assertNotIn('/private/build', result)

    def test_paths_normalize_explicit_overrides_and_keep_suffixes(self):
        exc = SyntaxError('C:/project/file.py', (r'C:\project\pkg\x.py', 1, 1, 'x'))
        with patch('os.getcwd', return_value='C:/project'):
            result = format_safe_traceback(exc, path_prefixes={'C:\\project\\': '<app>'})
        self.assertIn('<app>/pkg/x.py', result)
        self.assertIn('<app>/file.py', result)
        self.assertNotIn('<cwd>', result)

    def test_secret_crossing_prefix_is_fully_removed(self):
        result = format_safe_traceback(ValueError('/project/TOKEN-tail'),
                                       secrets=['TOKEN-tail'],
                                       path_prefixes={'/project/TOKEN': '<app>'})
        self.assertNotIn('tail', result)
        self.assertNotIn('TOKEN', result)

    def test_replacements_do_not_cascade(self):
        result = format_safe_traceback(ValueError('/alpha /beta abc ab'),
                                       path_prefixes={'/alpha': '/beta', '/beta': '<b>'},
                                       secrets=['ab', 'abc'])
        self.assertIn('/beta <b> <redacted> <redacted>', result)

    def test_roots_are_not_global_replacements(self):
        result = format_safe_traceback(ValueError('/x C:/x'),
                                       path_prefixes={'/': '<root>', 'C:\\': '<drive>'})
        self.assertIn('/x C:/x', result)

    def test_filename_labels_do_not_cascade(self):
        exc = SyntaxError('bad', ('/alpha/file.py', 1, 1, 'x'))
        result = format_safe_traceback(exc, path_prefixes={
            '/alpha': '/beta', '/beta': '<b>'})
        self.assertIn('"/beta/file.py"', result)

    def test_source_frame_opt_in(self):
        source = 'raise ValueError("frame_secret")\n'
        name = '/private/source.py'
        with patch.dict(linecache.cache, {name: (len(source), None, [source], name)}):
            try:
                exec(compile(source, name, 'exec'), {})
            except ValueError as exc:
                result = format_safe_traceback(exc, include_source=True,
                                               secrets=['frame_secret'])
        self.assertIn('raise ValueError("<redacted>")', result)
        self.assertNotIn('frame_secret', result)

    def test_groups_chains_notes_and_suppression(self):
        cause = ValueError('secret')
        cause.add_note('note secret')
        inner = RuntimeError('outer')
        inner.__cause__ = cause
        group = ExceptionGroup('group secret', [inner, SyntaxError(
            'invalid', ('/private/file.py', 1, 1, 'hidden_source'))])
        result = format_safe_traceback(group, secrets=['secret'])
        self.assertIn('direct cause', result)
        self.assertIn('note <redacted>', result)
        self.assertNotIn('secret', result)
        self.assertNotIn('hidden_source', result)
        inner.__cause__ = None
        inner.__context__ = cause
        inner.__suppress_context__ = False
        self.assertIn('During handling', format_safe_traceback(inner))
        inner.__suppress_context__ = True
        self.assertNotIn('ValueError', format_safe_traceback(inner))

    def test_input_validation(self):
        for secrets in ('secret', [None], ['']):
            with self.subTest(secrets=secrets), self.assertRaises((TypeError, ValueError)):
                format_safe_traceback(ValueError(), secrets=secrets)
        for prefixes in ([], {'': 'x'}, {'x': None}, {1: 'x'}):
            with self.subTest(prefixes=prefixes), self.assertRaises((TypeError, ValueError)):
                format_safe_traceback(ValueError(), path_prefixes=prefixes)
        with self.assertRaises(TypeError):
            format_safe_traceback('error')

    def test_top_level_export(self):
        import cereja
        self.assertIs(cereja.format_safe_traceback, format_safe_traceback)
