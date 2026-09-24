import random
import threading
import unittest

from model import Cell, Frame, Mailbox, Timers, conservative_width, diff, encode, sanitize


class ModelTests(unittest.TestCase):
    def test_reference_detects_missing_invalidation(self):
        old = Frame(4, 1)
        new = old.clone()
        new.put(0, 0, 'x')
        new.dirty.clear()  # Deliberate candidate fault, caught by reference.
        self.assertNotEqual(diff(old, new), diff(old, new, True))

    def test_random_overwrites_match_full_reference(self):
        rng = random.Random(293)
        for width, height in [(1, 1), (8, 4), (80, 24)]:
            old = Frame(width, height)
            for _ in range(100):
                new = old.clone()
                for _ in range(20):
                    wide = rng.choice([1, 2])
                    new.put(rng.randrange(width), rng.randrange(height),
                            '界' if wide == 2 else 'x', wide, rng.randrange(8))
                reference = diff(old, new)
                candidate = diff(old, new, True)
                self.assertEqual(reference, candidate)
                applied = old.cells.copy()
                for index, cell in candidate:
                    applied[index] = cell
                self.assertEqual(applied, new.cells)
                for i, cell in enumerate(new.cells):
                    if cell.width == 0:
                        self.assertGreater(i % width, 0)
                        self.assertEqual(new.cells[i - 1].width, 2)
                    if cell.width == 2:
                        self.assertLess(i % width, width - 1)
                        self.assertEqual(new.cells[i + 1].width, 0)
                old = new

    def test_continuation_overwrite_clears_lead(self):
        old = Frame(4, 1)
        old.put(0, 0, '界', 2)
        new = old.clone()
        new.put(1, 0, 'x')
        self.assertEqual(new.cells, [Cell(), Cell('x'), Cell(), Cell()])
        self.assertEqual([i for i, _ in diff(old, new, True)], [0, 1])

    def test_style_unchanged_and_clipping(self):
        old = Frame(4, 1)
        new = old.clone()
        self.assertEqual(encode(diff(old, new), 4), b'')
        self.assertFalse(new.put(3, 0, '界', 2))
        self.assertEqual(new.cells, old.cells)
        new.put(0, 0, ' ', style=2)
        self.assertEqual(len(diff(old, new, True)), 1)
        with self.assertRaises(ValueError):
            diff(old, Frame(8, 1))

    def test_untrusted_controls(self):
        payload = '\x1b[2J\x1b]52;c;secret\x07\x9b31m\r\n\t'
        safe = sanitize(payload)
        self.assertTrue(all(ord(c) >= 32 and not 127 <= ord(c) <= 159 for c in safe))
        self.assertEqual(sanitize(safe), safe)
        self.assertNotIn('\x1b', safe)

    def test_unicode_subset(self):
        for value, width in [('abc', 3), ('á', 1), ('a\u0301', 1), ('中文', 4)]:
            self.assertEqual(conservative_width(value), width)
        for value in ['🙂', '❤️', '👨‍👩‍👧‍👦', '🇧🇷', '\u0301', '\ufe0f']:
            self.assertIsNone(conservative_width(value))

    def test_bounded_mailbox_no_silent_loss(self):
        box = Mailbox(2)
        self.assertTrue(box.post('a'))
        self.assertTrue(box.post('b'))
        self.assertFalse(box.post('c'))
        self.assertEqual(box.drain(1), ['a'])
        self.assertTrue(box.wakeup.is_set())
        self.assertEqual(box.drain(1), ['b'])
        self.assertFalse(box.wakeup.is_set())

    def test_cross_thread_wakes_waiter(self):
        box = Mailbox()
        started = threading.Event()
        result = []
        def wait():
            started.set()
            result.append(box.wakeup.wait(1))
        worker = threading.Thread(target=wait)
        worker.start()
        self.assertTrue(started.wait(1))
        box.post('wake')
        worker.join(2)
        self.assertFalse(worker.is_alive())
        self.assertEqual(result, [True])
        self.assertEqual(box.drain(1), ['wake'])

    def test_timers_idle_order_and_budget(self):
        timers = Timers()
        self.assertIsNone(timers.timeout(0))
        timers.schedule(10, 'first')
        timers.schedule(10, 'second')
        self.assertEqual(timers.timeout(4), 6)
        self.assertEqual(timers.due(9, 8), [])
        self.assertEqual(timers.due(10, 1), ['first'])
        self.assertEqual(timers.timeout(10), 0)
        self.assertEqual(timers.due(10, 1), ['second'])
        self.assertIsNone(timers.timeout(10))


if __name__ == '__main__':
    unittest.main()
