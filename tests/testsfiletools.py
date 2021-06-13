import tempfile
import unittest
from abc import abstractmethod

from cereja.system import Path
from cereja.file import FileIO
from cereja.display import console


class FileIOTest(unittest.TestCase):
    data = None

    @property
    def name(self):
        return self.__class__.__name__

    @abstractmethod
    def create(self):
        file = FileIO.create('test', data=self.data)  # generic
        return file

    def setUp(self) -> None:
        self.file = self.create()

    def test_sanity(self):
        console.log(f'Testing {self.name}')
        with tempfile.TemporaryDirectory() as tempdir:
            self.file.set_path(Path(tempdir).join(self.file.name))
            data_before_save = self.file.data
            self.file.save(exist_ok=True)
            file = FileIO.load(self.file.path)
            self.assertTrue(file.path.exists, msg="File don't exist.")
            self.assertEqual(file.data, data_before_save, msg='Data corrupted')
            file.delete()
            self.assertFalse(file.path.exists)


class FileIOTxtTest(FileIOTest):
    data = ['first line', 'second line', 'third line']

    def create(self):
        file = FileIO.txt('test.txt', data=self.data, creation_mode=True)
        return file

    def test_history(self):
        for line in self.file:
            pass

        self.assertEqual(self.file[0], 'first line')
        self.assertEqual(self.file[:3], ['first line', 'second line', 'third line'])
        # Insert Data
        self.file.add('other line', line=0)
        self.file.add('other line2', line=0)
        self.assertEqual(self.file.data, ['other line2', 'other line', 'first line', 'second line', 'third line'])
        # it is allowed to use index assignment
        self.file[0] = 'other line'

        self.file.add('test')  # append
        self.assertEqual(self.file.data,
                         ['other line', 'other line', 'first line', 'second line', 'third line', 'test'])

        # Data Recovery
        self.file.undo()  # You selected amendment 4
        self.file.undo()  # You selected amendment 3
        self.assertEqual(self.file.data, ['other line2', 'other line', 'first line', 'second line', 'third line'])
        self.file.redo()  # You selected amendment 4
        self.assertEqual(self.file.data,
                         ['other line', 'other line', 'first line', 'second line', 'third line'])

    def test_eval(self):
        with tempfile.TemporaryDirectory() as tempdir:
            eval_data = [1, 2, 3, 'hi', ['oi']]
            file = FileIO.create(Path(tempdir).join(self.file.name), eval_data)
            self.assertEqual(file.data, eval_data)
            file.save()
            file = FileIO.load(file.path)
            self.assertEqual(file.data, eval_data)


class FileIOJsonTest(FileIOTest):
    data = {'key': 'value', 'key2': 'value2', 'key3': 'value3'}

    def create(self):
        return FileIO.json('test.json', data=self.data, creation_mode=True)

    def test_commons_operations(self):
        self.assertEqual(self.file.data, {'key': 'value', 'key2': 'value2', 'key3': 'value3'})

        # Iterable
        for key, value in self.file.items():
            pass

        self.assertEqual(self.file['key'], 'value')

        # Insert Data
        self.file['key4'] = 'value4'
        self.assertEqual(self.file.data, {'key': 'value', 'key2': 'value2', 'key3': 'value3', 'key4': 'value4'})

    def test_sample_items(self):
        self.assertEqual(self.file.sample_items(), {'key': 'value'})
        self.assertEqual(self.file.sample_items(k=3), {'key': 'value', 'key2': 'value2', 'key3': 'value3'})
        self.assertRaises(AssertionError, self.file.sample_items, -1)
        self.assertRaises(AssertionError, self.file.sample_items, 0.5)


class FileCsvTest(FileIOTest):
    data = [[1, 2, 3]]
    cols = ['col1', 'col2', 'col3']

    def create(self):
        return FileIO.csv('test.csv', data=self.data, creation_mode=True, cols=self.cols)

    def test_commons_operations(self):
        self.assertEqual(self.file.data, [[1, 2, 3]])
        self.file.add([1, 2], fill_with=0)
        self.assertEqual(self.file.data, [[1, 2, 3], [1, 2, 0]])

        # convert to dict
        self.assertEqual(self.file.to_dict(), {'col1': (1, 1), 'col2': (2, 2), 'col3': (3, 0)})

        # or get generation row by row with col
        self.assertEqual(list(self.file.rows), [{'col1': 1, 'col2': 2, 'col3': 3}, {'col1': 1, 'col2': 2, 'col3': 0}])

        # Iterable
        for row in self.file:
            pass

        # indexing col values
        self.assertEqual(self.file['col1'], (1, 1))
        # or use index and get a row
        self.assertEqual(self.file[0], [1, 2, 3])
        self.assertEqual(self.file.flatten(), [1, 2, 3, 1, 2, 0])


class FilePyObjTest(FileIOTest):
    data = [[1, 2, 3]]

    def create(self):
        return FileIO.create('test.pkl', data=self.data)

    def test_commons_operations(self):
        self.assertEqual(self.file.data, [[1, 2, 3]])


if __name__ == '__main__':
    unittest.main()
