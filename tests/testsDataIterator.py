import unittest
from cereja.utils import DataIterator


class TestDataIterator(unittest.TestCase):

    def test_init_with_list(self):
        data = [1, 2, 3]
        iterator = DataIterator(data)
        self.assertListEqual(list(iterator), data)

    def test_init_with_dict(self):
        data = {'a': 1, 'b': 2}
        iterator = DataIterator(data)
        self.assertEqual(list(iterator), list(data.items()))

    def test_init_with_empty_list(self):
        data = []
        iterator = DataIterator(data)
        self.assertTrue(iterator.is_empty)

    def test_init_with_non_iterable(self):
        with self.assertRaises(AssertionError):
            DataIterator(123)

    def test_get_first_element(self):
        data = [1, 2, 3]
        iterator = DataIterator(data)
        self.assertEqual(iterator.first, 1)

    def test_get_last_element(self):
        data = [1, 2, 3]
        iterator = DataIterator(data)
        self.assertEqual(iterator.last, 3)

    def test_get_next_element(self):
        data = [1, 2, 3]
        iterator = DataIterator(data)
        self.assertEqual(next(iterator), 1)
        self.assertEqual(next(iterator), 2)

    def test_batch_elements(self):
        data = [1, 2, 3, 4, 5]
        iterator = DataIterator(data)
        batches = iterator.batch(batch_size=2)
        self.assertEqual(list(batches), [[1, 2], [3, 4], [5]])

    def test_cycle_elements(self):
        data = [1, 2, 3]
        iterator = DataIterator(data)
        cycle = iterator.cycle()
        self.assertEqual(next(cycle), 1)
        self.assertEqual(next(cycle), 2)
        self.assertEqual(next(cycle), 3)
        self.assertEqual(next(cycle), 1)

    def test_take_elements(self):
        data = [1, 2, 3, 4, 5]
        iterator = DataIterator(data)
        self.assertEqual(iterator.take(3), [1, 2, 3])

    def test_random_elements(self):
        data = [1, 2, 3, 4, 5]
        iterator = DataIterator(data)
        random_iterator = iterator.random()
        self.assertNotEqual(list(random_iterator), data)

    def test_filter_elements(self):
        data = [1, 2, 3, 4, 5]
        iterator = DataIterator(data)
        filtered = iterator.filter(lambda x: x % 2 == 0)
        self.assertEqual(list(filtered), [2, 4])

    def test_map_elements(self):
        data = [1, 2, 3]
        iterator = DataIterator(data)
        mapped = iterator.map(lambda x: x * 2)
        self.assertEqual(list(mapped), [2, 4, 6])

    def test_reduce_elements(self):
        data = [1, 2, 3, 4]
        iterator = DataIterator(data)
        result = iterator.reduce(lambda x,
                                        y: x + y, 0)
        self.assertEqual(result, 10)

    def test_sort_elements(self):
        data = [3, 1, 2]
        iterator = DataIterator(data)
        sorted_iterator = iterator.sort()
        self.assertEqual(list(sorted_iterator), [1, 2, 3])

    def test_enumerate_elements(self):
        data = ['a', 'b', 'c']
        iterator = DataIterator(data)
        enumerated = iterator.enumerate()
        self.assertEqual(list(enumerated), [(0, 'a'), (1, 'b'), (2, 'c')])

    def test_group_by_elements(self):
        data = ['apple', 'banana', 'cherry']
        iterator = DataIterator(data)
        grouped = iterator.group_by(lambda x: x[0])
        self.assertEqual(grouped['a'], ['apple'])
        self.assertEqual(grouped['b'], ['banana'])
        self.assertEqual(grouped['c'], ['cherry'])

    def test_str_conversion(self):
        data = [1, 2, 3]
        iterator = DataIterator(data)
        str_iterator = iterator.str
        self.assertEqual(list(str_iterator), ['1', '2', '3'])

    def test_int_conversion(self):
        data = ['1', '2', '3']
        iterator = DataIterator(data)
        int_iterator = iterator.int
        self.assertEqual(list(int_iterator), [1, 2, 3])

    def test_float_conversion(self):
        data = ['1.1', '2.2', '3.3']
        iterator = DataIterator(data)
        float_iterator = iterator.float
        self.assertEqual(list(float_iterator), [1.1, 2.2, 3.3])

    def test_summary_report(self):
        data = [1, 2, 3]
        iterator = DataIterator(data)
        summary = iterator.summary()
        self.assertIsInstance(summary, dict)

    def test_frequency_report(self):
        data = [1, 2, 2, 3, 3, 3]
        iterator = DataIterator(data)
        freq = iterator.freq
        self.assertEqual(freq[1], 1)
        self.assertEqual(freq[2], 2)
        self.assertEqual(freq[3], 3)
