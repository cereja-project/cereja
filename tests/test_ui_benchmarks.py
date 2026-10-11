"""Verify measurement boundaries and observable workload contracts."""

from pathlib import Path
import runpy
import sys
import tracemalloc
import unittest

ROOT = Path(__file__).resolve().parents[1]


class CoreBenchmarksTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        sys.path.insert(0, str(ROOT / 'benchmarks'))
        cls.rendering = runpy.run_path(str(ROOT / 'benchmarks/ui_rendering.py'))
        cls.scheduling = runpy.run_path(str(ROOT / 'benchmarks/ui_scheduling.py'))
        cls.operations = runpy.run_path(str(ROOT / 'benchmarks/ui_operations.py'))
        cls.feedback = runpy.run_path(str(ROOT / 'benchmarks/ui_feedback.py'))
        cls.helpers = runpy.run_path(str(ROOT / 'benchmarks/_ui_bench.py'))

    def test_p95_nearest_rank_and_dispersion(self):
        result = self.helpers['summary'](list(range(1, 32)))
        self.assertEqual(result, {'n': 31, 'median': 16, 'p95': 30,
                                  'mad': 8, 'min': 1, 'max': 31})

    def test_sparse_workloads_emit_and_unchanged_is_zero(self):
        for profile in ('ascii', 'unicode_styles'):
            unchanged = self.rendering['sample'](80, 24, 'unchanged', profile)
            self.assertEqual((unchanged['utf8_bytes'], unchanged['writes'], unchanged['flushes']), (0, 0, 0))
            self.assertEqual(unchanged['prepare_cell_constructions'], 80 * 24)
            for workload in ('one_cell', 'initial_full', 'resize_grow', 'resize_shrink'):
                result = self.rendering['sample'](80, 24, workload, profile)
                self.assertGreater(result['utf8_bytes'], 0)
                self.assertEqual((result['writes'], result['flushes']), (1, 1))

    def test_timers_and_render_attempts_are_separate_from_writes(self):
        for count in (1, 64, 1024):
            result = self.scheduling['timers'](80, 24, count)
            self.assertEqual(result['timer_events'], count)
            self.assertEqual(result['renders'], 2)
            self.assertEqual((result['writes'], result['flushes']), (1, 1))
            self.assertEqual(result['blocking_waits'], 0)

    def test_feedback_aggregate_idle_and_motion_boundaries(self):
        for mode in ('local', 'low-bandwidth', 'off', 'plain'):
            for output in (False, True):
                result = self.feedback['sample'](16, mode, output=output)
                active = mode in ('local', 'low-bandwidth')
                self.assertEqual(result['peak_timers'], 16 if active else 0)
                self.assertEqual(result['active_timer_events'], 64 if active else 0)
                self.assertEqual(result['active_paints'], 64 if active else 0)
                self.assertEqual(result['active_writes'], 4 if active and output else 0)
                self.assertEqual(result['ordered_keys'], 4)
                self.assertEqual(result['final_timers'], 0)
                for key in ('timer_events', 'renders', 'writes', 'flushes'):
                    self.assertEqual(result['idle_' + key], 0)
        for mode in ({}, {'motion': True, 'kind': 'dots'}, {'motion': True, 'plain': True}):
            rows = self.feedback['example'](**mode)
            self.assertTrue(any('3/8 (37%)' in row for row in rows))
            self.assertTrue(any('total unavailable' in row for row in rows))
            self.assertFalse(any('\x1b' in row for row in rows))


    def test_operations_real_producers_and_memory_boundary(self):
        for mode in ('local', 'low-bandwidth', 'off', 'plain'):
            result = self.operations['sample'](mode, output=True, pressure=True, duration=.02)
            self.assertEqual(result['final_events'], 1)
            self.assertTrue(result['worker_exited'])
            self.assertEqual(result['outcome'], 'Succeeded')
            self.assertGreater(result['attempted_progress'], 0)
            self.assertGreater(result['latency_ns']['n'], 0)
            self.assertGreater(result['pressure_events'], 0)
            self.assertLessEqual(result['peak_sampled_envelopes'], 1024)
            self.assertLessEqual(result['peak_sampled_payload_bytes'], 1048576)
            self.assertEqual(result['idle_periodic_work'], 0)
            self.assertTrue(result['editor_selection_preserved'])
            if mode in ('off', 'plain'):
                self.assertEqual(result['metrics']['timer_events'], 0)

    def test_tracing_retains_value_and_stops_after_window(self):
        result = self.helpers['traced'](lambda: bytearray(4096))
        self.assertGreaterEqual(result['retained_bytes'], 4096)
        self.assertGreaterEqual(result['peak_bytes'], result['retained_bytes'])
        self.assertGreater(result['live_traced_blocks'], 0)
        self.assertFalse(tracemalloc.is_tracing())


if __name__ == '__main__':
    unittest.main()
