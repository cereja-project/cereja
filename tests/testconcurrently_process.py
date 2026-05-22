import threading
import time
import unittest

from cereja.concurrently.process import MultiProcess, Processor, WorkerQueue


class MultiProcessTest(unittest.TestCase):
    def test_map_with_on_result_waits_for_all_tasks(self):
        observed = []
        lock = threading.Lock()

        def task(value):
            time.sleep(0.02)
            return value * 2

        def on_result(payload):
            with lock:
                observed.append(payload)

        multi = MultiProcess(max_threads=2, on_result=on_result)
        result = multi.map(task, [1, 2, 3, 4], verbose=False)

        self.assertIsNone(result)
        self.assertEqual(len(observed), 4)
        self.assertEqual([item for _, item in sorted(observed)], [2, 4, 6, 8])


class WorkerQueueTest(unittest.TestCase):
    def test_get_available_response_returns_item_when_take_indx_false(self):
        worker = WorkerQueue(func_task=lambda value: value + 1, max_threads=1)
        worker.put(10)
        result = worker.get_available_response(timeout=2)
        self.assertEqual(result, 11)


class ProcessorTest(unittest.TestCase):
    def test_stop_process_before_start_is_safe(self):
        processor = Processor(use_progress=False)
        processor.stop_process()
        self.assertTrue(processor.stopped)

    def test_process_ensures_cleanup_when_input_iteration_fails(self):
        def failing_input():
            yield 1
            raise RuntimeError("input failure")

        processor = Processor(num_workers=1, use_progress=False)
        with self.assertRaises(RuntimeError):
            processor.process(lambda value: value, failing_input())

        self.assertTrue(processor.stopped)
        self.assertIsNone(processor._process_result_service)

