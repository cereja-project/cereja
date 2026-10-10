"""UI-11 requirement-derived collections and clean-copy checks."""
from dataclasses import replace
import threading
import unittest
from unittest.mock import patch
from cereja.ui.buffer import CellBuffer, Rect
from cereja.ui.collections import Row, Column, TreeNode, CollectionLimits, SelectableList, Table, TreeView
from cereja.ui.editing import TextContent, TextInput
from cereja.ui.events import KeyEvent, PasteEvent, ResizeEvent
from cereja.ui.focus import FocusManager, FocusScope, FocusTarget
from cereja.ui.layout import Constraint
from cereja.ui.scheduling import EventLoop
from cereja.ui.terminal import TerminalSession
from cereja.ui.testing import VirtualBackend
from cereja.ui.text import TextPolicy

def key(name, repeat=1, ctrl=False):
    return KeyEvent(name, repeat=repeat, modifiers=frozenset({'ctrl'} if ctrl else ()))

def rows(count):
    return (Row(str(i), (f'row {i}',)) for i in range(count))

def draw(widget, width=24, height=8, **kwargs):
    frame = CellBuffer(width, height, policy=kwargs.pop('policy', TextPolicy()))
    return frame, widget.paint(frame, Rect(0, 0, width, height), **kwargs)

def strings(frame):
    return tuple(''.join(cell.text for cell in row) for row in frame.rows)

class CollectionNavigationTest(unittest.TestCase):
    def test_empty_and_error(self):
        for widget in (SelectableList('list', []), Table('table', [Column('Name')], []), TreeView('tree', [])):
            frame, view = draw(widget)
            self.assertIsNone(widget.selected)
            self.assertEqual(view.visible_ids, ())
            self.assertTrue(any('Empty' in line for line in strings(frame)))
            for name in ('down', 'enter'):
                self.assertEqual(widget.handle(key(name)).kind, 'handled')
            widget.update([], state='error', message='Denied')
            frame, view = draw(widget)
            self.assertEqual(view.status.state, 'error')
            self.assertTrue(any('Error' in line for line in strings(frame)))

    def test_next_previous_empty_fallback(self):
        widget = SelectableList('list', [Row(i, (i,)) for i in ('a', 'b', 'c', 'd')])
        widget.select('b')
        for ids, expected in ((('d', 'c', 'a'), 'c'), (('d', 'a'), 'a'), (('d',), 'd'), ((), None)):
            widget.update([Row(i, (i,)) for i in ids])
            self.assertEqual(widget.selected, expected)
        widget.update([Row('z', ('z',))])
        self.assertEqual(widget.selected, 'z')

    def test_reorder_keeps_id_and_reveals(self):
        widget = SelectableList('list', rows(12))
        widget.select('8')
        widget.update(reversed(tuple(rows(12))))
        frame, view = draw(widget)
        self.assertEqual(widget.selected, '8')
        self.assertIn('8', view.visible_ids)
        self.assertTrue(any('>* row 8' in line for line in strings(frame)))

    def test_scroll_navigation_and_paging(self):
        widget = SelectableList('list', rows(100))
        draw(widget, height=5)
        widget.handle(key('down', 80))
        self.assertIn('80', draw(widget, height=5)[1].visible_ids)
        widget.scroll(-20)
        self.assertEqual(widget.selected, '80')
        self.assertNotIn('80', draw(widget, height=5)[1].visible_ids)
        widget.handle(key('down'))
        self.assertIn('81', draw(widget, height=5)[1].visible_ids)
        widget.handle(key('end'))
        self.assertEqual(widget.selected, '99')
        widget.handle(key('home'))
        widget.handle(key('page_down'))
        self.assertEqual(widget.selected, '4')

    def test_resize_preserves_requested_anchor(self):
        widget = SelectableList('list', rows(100))
        draw(widget, height=5)
        widget.select('90')
        draw(widget, height=5)
        anchor = widget.scroll_y
        for width, height in ((0, 0), (1, 1), (24, 100), (24, 5)):
            draw(widget, width, height)
            self.assertEqual((widget.selected, widget.scroll_y), ('90', anchor))
        self.assertIn('90', draw(widget, height=5)[1].visible_ids)

    def test_shrinking_visible_body_reveals_selection_but_not_manually_hidden_selection(self):
        widget = SelectableList('list', rows(100))
        draw(widget, height=15)
        widget.select('50')
        draw(widget, height=15)
        self.assertIn('50', draw(widget, height=5)[1].visible_ids)
        widget.scroll(-20)
        self.assertNotIn('50', draw(widget, height=8)[1].visible_ids)

    def test_focus_navigation_and_text_are_distinct(self):
        widget = SelectableList('list', rows(3))
        owner = FocusManager(FocusScope('base', (FocusTarget('composer'),) + widget.targets))
        owner.focus('list')
        owner.push(FocusScope('help', (FocusTarget('help'),)))
        self.assertEqual(widget.handle(key('down'), focused=False).kind, 'unhandled')
        self.assertEqual(owner.pop(), 'list')
        self.assertTrue(any(' * row 0' in line for line in strings(draw(widget, focused=False)[0])))
        self.assertEqual(widget.handle(PasteEvent('no edit')).kind, 'unhandled')
        self.assertEqual(widget.handle(key('c', ctrl=True)).kind, 'exit')

    def test_atomic_invalid_update(self):
        widget = SelectableList('list', rows(3))
        widget.select('1')
        with self.assertRaises(ValueError):
            widget.update([Row('x', ('x',)), Row('x', ('duplicate',))])
        self.assertEqual((widget.selected, widget.order), ('1', ('0', '1', '2')))
        with self.assertRaises(ValueError):
            widget.select('absent')
        with self.assertRaises(ValueError):
            widget.update([], state='unknown')

    def test_thread_ownership(self):
        widget = SelectableList('list', rows(3))
        failures = []
        def worker():
            for call in (lambda: widget.select('1'), lambda: widget.update([]),
                         lambda: draw(widget), lambda: widget.handle(key('down'))):
                try:
                    call()
                except RuntimeError:
                    failures.append(True)
        thread = threading.Thread(target=worker)
        thread.start()
        thread.join()
        self.assertEqual(len(failures), 4)
        self.assertEqual(widget.selected, '0')

class CollectionPaintingTest(unittest.TestCase):
    def test_exact_ascii_snapshot(self):
        frame, view = draw(SelectableList('list', [Row('a', ('alpha',)), Row('b', ('beta',))]), 14, 4)
        self.assertEqual(strings(frame), ('>* alpha      ', '   beta       ', '              ', 'Complete | 2  '))
        self.assertEqual(view.visible_ids, ('a', 'b'))

    def test_unicode_truncation_and_full_inspection(self):
        text = 'e\u0301界😀 trailing'
        content = TextContent('source', 3, text)
        widget = SelectableList('list', [Row('a', (text,), content)])
        frame, view = draw(widget, 9, 3)
        self.assertIn('e\u0301界', strings(frame)[0])
        self.assertTrue(strings(frame)[0].rstrip().endswith('…'))
        self.assertEqual(widget.handle(key('enter')).content, content)
        self.assertEqual(view.formatted_cells, 1)
        frame, _ = draw(widget, 9, 3, policy=TextPolicy(ascii_only=True))
        self.assertTrue(all(ord(c) < 128 for line in strings(frame) for c in line))
        self.assertTrue(strings(frame)[0].rstrip().endswith('...'))

    def test_table_columns_and_read_only(self):
        widget = Table('table', [Column('Name', Constraint.fixed(6)), Column('Value')],
                       [Row('a', ('alpha', '界' * 20))])
        frame, view = draw(widget, 21, 4)
        self.assertTrue(strings(frame)[0].startswith('   Name   Value'))
        self.assertTrue(strings(frame)[1].startswith('>* alpha'))
        self.assertTrue(strings(frame)[1].rstrip().endswith('…'))
        self.assertEqual((view.painted_rows, view.formatted_cells), (1, 2))
        self.assertEqual(widget.handle(key('delete')).kind, 'unhandled')
        with self.assertRaises(ValueError):
            widget.update([Row('b', ('wrong arity',))])
        self.assertEqual(widget.order, ('a',))

    def test_ancestor_clip_limits_work(self):
        widget = SelectableList('list', rows(1000))
        frame = CellBuffer(25, 12)
        frame.draw_text(0, 0, 'outside')
        view = widget.paint(frame, Rect(1, 1, 22, 10), clip=Rect(3, 3, 8, 3))
        self.assertEqual(view.painted_rows, 3)
        self.assertEqual(frame.cell(0, 0).text, 'o')
        self.assertLessEqual(view.formatted_cells, 3)

    def test_offscreen_rows_not_formatted(self):
        widget = SelectableList('list', rows(4096))
        import cereja.ui.collections as module
        original, calls = module._truncate, []
        def measured(text, *args):
            calls.append(text)
            return original(text, *args)
        with patch.object(module, '_truncate', measured):
            _, view = draw(widget, height=8)
        self.assertEqual(view.painted_rows, 7)
        self.assertEqual(sum(value.startswith('row ') for value in calls), 7)

    def test_safe_labels_and_repaint_clear(self):
        widget = SelectableList('list', [Row('a', ('\x1b[31m forged',))])
        frame, _ = draw(widget, 30, 5)
        self.assertNotIn('\x1b', ''.join(strings(frame)))
        widget.update([Row('b', ('x',))])
        widget.paint(frame, Rect(0, 0, 30, 5))
        self.assertNotIn('forged', ''.join(strings(frame)))
        with self.assertRaises(ValueError):
            Row('multiline', ('a\nb',))

class CollectionCopyTest(unittest.TestCase):
    def test_canonical_copy_preserves_all_source_whitespace(self):
        source = '  ' + chr(96) * 3 + 'python\n\tcode = 1  \n\n  ' + chr(96) * 3 + '\n'
        content = TextContent('snippet', 7, source)
        widget = Table('table', [Column('Preview')], [Row('a', ('short preview...',), content)])
        draw(widget, 10)
        widget.set_text_selection('a', 0, len(content.text))
        action = widget.handle(key('c', ctrl=True))
        self.assertEqual((action.kind, action.selection.text), ('copy', source))
        draw(widget, 2, 1)
        self.assertEqual(widget.handle(key('c', ctrl=True)).selection.text, source)
        self.assertEqual(widget.handle(key('c', ctrl=True)).kind, 'copy')

    def test_navigation_does_not_change_copy_revision_invalidation_refuses_exit(self):
        a = Row('a', ('a',), TextContent('a-text', 1, 'a\t \n\n'))
        b = Row('b', ('b',), TextContent('b-text', 1, 'other'))
        widget = SelectableList('list', [a, b])
        widget.set_text_selection('a', 0, len(a.content.text))
        widget.select('b')
        self.assertEqual(widget.handle(key('c', ctrl=True)).selection.text, a.content.text)
        widget.update([b, a])
        self.assertIsNotNone(widget.text_selection)
        widget.update([b, replace(a, content=TextContent('a-text', 2, 'changed'))])
        self.assertIsNone(widget.text_selection)
        self.assertTrue(widget.selection_notice)
        self.assertEqual(widget.handle(key('c', ctrl=True)).kind, 'rejected')
        widget.clear_text_selection()
        self.assertEqual(widget.handle(key('c', ctrl=True)).kind, 'exit')

    def test_equal_replacement_copy_uses_retained_snapshot_object(self):
        old = TextContent('text', 4, 'same payload')
        new = TextContent('text', 4, 'same payload')
        widget = SelectableList('list', [Row('a', ('a',), old)])
        widget.set_text_selection('a', 0, len(old.text))
        widget.update([Row('a', ('a',), new)])
        self.assertIs(widget.text_selection.content, new)
        self.assertEqual(widget.text_selection.text, old.text)

    def test_disappeared_copy_refuses_replacement_and_exit(self):
        widget = SelectableList('list', [Row('a', ('a',), TextContent('a', 0, 'safe'))])
        widget.set_text_selection('a', 0, 4)
        widget.update([])
        self.assertEqual(widget.handle(key('c', ctrl=True)).kind, 'rejected')
        with self.assertRaises(ValueError):
            widget.set_text_selection('missing', 0, 1)

class TreeNavigationTest(unittest.TestCase):
    def fixture(self):
        return TreeView('tree', [TreeNode('a', 'alpha', branch=True), TreeNode('a1', 'first', parent='a'),
                               TreeNode('a2', 'second', parent='a', branch=True),
                               TreeNode('deep', 'deep', parent='a2'), TreeNode('b', 'beta')])

    def test_arrows(self):
        widget = self.fixture()
        self.assertEqual(widget.order, ('a', 'b'))
        widget.handle(key('right'))
        self.assertEqual(widget.order, ('a', 'a1', 'a2', 'b'))
        widget.handle(key('right'))
        self.assertEqual(widget.selected, 'a1')
        widget.handle(key('left'))
        self.assertEqual(widget.selected, 'a')
        widget.handle(key('left'))
        self.assertEqual((widget.order, widget.expanded), (('a', 'b'), frozenset()))
        widget.handle(key('down'))
        self.assertEqual(widget.selected, 'b')

    def test_update_resize_and_disappearance(self):
        widget = self.fixture()
        widget.expand('a')
        widget.expand('a2')
        widget.select('deep')
        draw(widget, height=4)
        expanded = widget.expanded
        widget.update([TreeNode('a', 'renamed', branch=True), TreeNode('a2', 'second', parent='a', branch=True),
                       TreeNode('deep', 'deep', parent='a2'), TreeNode('b', 'beta')])
        draw(widget, 4, 1)
        self.assertEqual((widget.selected, widget.expanded), ('deep', expanded))
        self.assertIn('deep', draw(widget, height=4)[1].visible_ids)
        widget.update([TreeNode('a', 'alpha', branch=True), TreeNode('b', 'beta')])
        self.assertEqual((widget.selected, widget.expanded), ('b', frozenset({'a'})))

    def test_collapse_selects_ancestor(self):
        widget = self.fixture()
        widget.expand('a')
        widget.select('a1')
        widget.collapse('a')
        self.assertEqual(widget.selected, 'a')

    def test_child_states_and_load_intents(self):
        for state in ('loading', 'incomplete', 'error'):
            widget = TreeView('tree', [TreeNode('root', 'root', branch=True, state=state,
                                               message='Denied' if state == 'error' else '')])
            action = widget.handle(key('right'))
            self.assertEqual(action.kind, 'changed' if state == 'loading' else 'load')
            frame, view = draw(widget, 40)
            self.assertIn(state.title(), strings(frame)[0])
            self.assertEqual(view.status.state, state)
            widget.update([TreeNode('root', 'root', branch=True), TreeNode('child', 'child', parent='root')])
            self.assertEqual(widget.order, ('root', 'child'))
            self.assertEqual(widget.status.state, 'complete')

    def test_tree_focus_flag_validation_does_not_mutate_navigation(self):
        widget = self.fixture()
        for event in (key('right'), key('left'), key('down')):
            with self.assertRaises(TypeError):
                widget.handle(event, focused='another-owner')
        self.assertEqual((widget.selected, widget.expanded), ('a', frozenset()))

    def test_invalid_hierarchy_atomic(self):
        widget = self.fixture()
        for nodes in ([TreeNode('orphan', 'orphan', parent='absent')],
                      [TreeNode('cycle', 'cycle', parent='cycle')],
                      [TreeNode('a', 'a'), TreeNode('a', 'duplicate')]):
            with self.assertRaises(ValueError):
                widget.update(nodes)
            self.assertEqual(widget.order, ('a', 'b'))
        with self.assertRaises(ValueError):
            TreeNode('x', 'x', state='unknown')

class CollectionBoundsTest(unittest.TestCase):
    def test_infinite_source_cap_plus_one(self):
        seen = []
        def infinite():
            i = 0
            while True:
                seen.append(i)
                yield Row(str(i), (str(i),))
                i += 1
        widget = SelectableList('list', infinite(), limits=CollectionLimits(max_items=10))
        self.assertEqual(len(seen), 11)
        self.assertEqual((widget.status.retained_count, widget.status.examined_count), (10, 11))
        self.assertEqual((widget.status.state, widget.status.limit), ('truncated', 'items'))

    def test_exact_complete_and_empty_incomplete(self):
        widget = SelectableList('list', rows(10), limits=CollectionLimits(max_items=10))
        self.assertEqual(widget.status.state, 'complete')
        widget.update([], state='incomplete', message='More may exist')
        frame, _ = draw(widget, 40)
        self.assertTrue(any('Incomplete' in line for line in strings(frame)))
        self.assertFalse(any('Empty' in line for line in strings(frame)))

    def test_bytes_include_canonical_payload(self):
        widget = SelectableList('list', [Row('a', ('aaa',)), Row('b', ('bbb',))],
                                limits=CollectionLimits(max_bytes=5))
        self.assertEqual((widget.order, widget.status.limit), (('a',), 'bytes'))
        widget.update([Row('a', ('a',), TextContent('source', 0, 'large payload'))])
        self.assertEqual((widget.status.retained_count, widget.status.state), (0, 'truncated'))

    def test_broad_and_deep_bounds(self):
        broad = TreeView('broad', (TreeNode(str(i), str(i)) for i in range(10000)),
                         limits=CollectionLimits(max_items=128))
        self.assertEqual((broad.status.retained_count, broad.status.examined_count), (128, 129))
        self.assertEqual(draw(broad, height=8)[1].painted_rows, 7)
        deep = TreeView('deep', (TreeNode(str(i), str(i), parent=str(i-1) if i else None, branch=True)
                                 for i in range(10000)), limits=CollectionLimits(max_depth=64))
        self.assertEqual((deep.status.retained_count, deep.status.limit), (65, 'depth'))
        for i in range(65):
            deep.expand(str(i))
        deep.select('64')
        frame, view = draw(deep, 16, 4)
        self.assertIn('64', view.visible_ids)
        self.assertEqual(deep.status.state, 'truncated')
        self.assertLessEqual(view.painted_rows, 3)
        self.assertTrue(any('Truncated' in line for line in strings(frame)))

    def test_old_nodes_and_expansion_not_retained(self):
        widget = TreeView('tree', [TreeNode('old', 'old', branch=True)])
        widget.expand('old')
        widget.update([TreeNode('new', 'new')])
        self.assertEqual((widget.expanded, widget.status.retained_count, widget.selected), (frozenset(), 1, 'new'))

class CollectionVirtualReplayTest(unittest.TestCase):
    def test_existing_scheduler_no_timers_composer_untouched(self):
        widget = TreeView('tree', [TreeNode('r', 'root', branch=True), TreeNode('c', 'child', parent='r')])
        composer, size = TextInput('composer', '/draft'), [24, 8]
        backend = VirtualBackend(size=lambda: tuple(size))
        actions, loop = [], None
        def handler(event):
            if isinstance(event, ResizeEvent):
                size[:] = event.width, event.height
            else:
                actions.append(widget.handle(event))
            loop.request_render(draw(widget, *size)[0])
        with TerminalSession(backend) as session:
            loop = EventLoop(session, handler, clock=backend.clock)
            try:
                backend.inject_input(key('right'), key('right'), ResizeEvent(12, 4), key('enter'))
                loop.turn()
                self.assertEqual((widget.selected, actions[-1].kind, composer.text), ('c', 'inspect', '/draft'))
                self.assertEqual(loop.timer_count, 0)
                before = session.write_count
                loop.turn(block=True)
                self.assertEqual(session.write_count, before)
            finally:
                loop.close()


class CollectionAdditionalContractsTest(unittest.TestCase):
    def test_iterator_exception_leaves_snapshot_and_copy_intact(self):
        row = Row('a', ('a',), TextContent('source', 0, 'retained'))
        widget = SelectableList('list', [row])
        widget.set_text_selection('a', 0, 8)
        def failed():
            yield Row('b', ('b',))
            raise OSError('not leaked into widget')
        with self.assertRaises(OSError):
            widget.update(failed())
        self.assertEqual(widget.order, ('a',))
        self.assertEqual(widget.handle(key('c', ctrl=True)).selection.text, 'retained')

    def test_collapsed_tree_copy_is_textual_not_node_navigation(self):
        content = TextContent('tree-text', 8, '\t  tree\n\n')
        widget = TreeView('tree', [TreeNode('r', 'r', branch=True),
                                   TreeNode('c', 'short', parent='r', content=content)])
        widget.expand('r')
        widget.select('c')
        widget.set_text_selection('c', 0, len(content.text))
        widget.collapse('r')
        self.assertEqual(widget.selected, 'r')
        self.assertEqual(widget.handle(key('c', ctrl=True)).selection.text, content.text)

    def test_previous_fallback_when_last_item_disappears(self):
        widget = SelectableList('list', rows(4))
        widget.select('3')
        widget.update([Row('0', ('0',)), Row('2', ('2',))])
        self.assertEqual(widget.selected, '2')

    def test_byte_cutoff_does_not_retain_rejected_node_id(self):
        widget = TreeView('tree', [TreeNode('a', 'aaa'), TreeNode('b', 'bbb')],
                          limits=CollectionLimits(max_bytes=5))
        self.assertEqual(widget.order, ('a',))
        self.assertEqual(set(widget._depths), {'a'})

    def test_hidden_header_and_footer_are_not_formatted(self):
        import cereja.ui.collections as module
        widget = Table('table', [Column('invisible header')], rows(100))
        frame = CellBuffer(30, 10)
        calls, original = [], module._truncate
        def measured(text, *args):
            calls.append(text)
            return original(text, *args)
        with patch.object(module, '_truncate', measured):
            view = widget.paint(frame, Rect(0, 0, 30, 10), clip=Rect(0, 3, 30, 2))
        self.assertEqual(view.painted_rows, 2)
        self.assertNotIn('invisible header', calls)

    def test_bad_limits_and_oversized_metadata_are_rejected(self):
        for kw in ({'max_items': 0}, {'max_bytes': 0}, {'max_depth': -1}):
            with self.assertRaises(ValueError):
                CollectionLimits(**kw)
        with self.assertRaises(ValueError):
            Row('huge', ('x' * 16385,))
        with self.assertRaises(ValueError):
            Table('table', (Column(str(i)) for i in range(33)), [])

class CollectionExamplesTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        from pathlib import Path
        import runpy
        import sys
        root = Path(__file__).resolve().parents[1]
        cls.old_path = sys.path[:]
        sys.path.insert(0, str(root / 'benchmarks'))
        cls.example = runpy.run_path(str(root / 'benchmarks/ui_collections.py'))

    @classmethod
    def tearDownClass(cls):
        import sys
        sys.path[:] = cls.old_path

    def test_all_bounded_examples_have_safe_ascii_copy_and_independent_composer(self):
        for size in ((120, 40), (80, 24), (40, 12)):
            for kind in ('table', 'list', 'tree'):
                for state in ('complete', 'empty', 'error', 'loading', 'incomplete', 'truncated'):
                    value = self.example['example'](kind, size, state)
                    self.assertEqual(value['status'], 'complete' if state == 'empty' else state)
                    self.assertTrue(all(len(row) == size[0] and row[-1] == ' ' for row in value['rows']))
                    self.assertTrue(all(ord(char) < 128 for row in value['rows'] for char in row))
                    self.assertEqual(value['composer'], '/draft remains independent')
                    if state != 'empty':
                        self.assertEqual(value['copy'], '  source\ttext  \n\n  final\n')

    def test_measurement_checks_visible_work_and_retained_prefix(self):
        for workload in self.example['WORKLOADS']:
            value = self.example['sample'](workload, (40, 12))
            self.assertGreater(value['event_to_buffer_us'], 0)
            self.assertLessEqual(value['painted_rows'], 11)
            self.assertLessEqual(value['retained_items'], 4096)
            self.assertLessEqual(value['canonical_payload_bytes'], 1048576)
            self.assertLessEqual(value['examined_items'], value['retained_items'] + 1)
            self.assertEqual(value['result_state'], 'truncated' if workload in
                             ('tree_cap_100000', 'tree_deep_10000', 'canonical_byte_cap') else 'complete')


if __name__ == '__main__':
    unittest.main()
