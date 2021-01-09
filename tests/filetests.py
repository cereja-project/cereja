import unittest
from cereja.file import FileIO


class FileToolsTestCase(unittest.TestCase):

    def test_txt(self):
        data = ['first line', 'second line', 'third line']
        file = FileIO.create('test.txt', data)
        self.assertEqual(file.data, ['first line', 'second line', 'third line'])
        for line in file:
            pass

        self.assertEqual(file[0], 'first line')
        self.assertEqual(file[:3], ['first line', 'second line', 'third line'])
        # Insert Data
        file.add('other line', line=0)
        file.add('other line2', line=0)
        self.assertEqual(file.data, ['other line2', 'other line', 'first line', 'second line', 'third line'])
        # it is allowed to use index assignment
        file[0] = 'other line'

        file.add('test')  # append
        self.assertEqual(file.data,
                         ['other line', 'other line', 'first line', 'second line', 'third line', 'test'])

        # Data Recovery
        file.undo()  # You selected amendment 4
        file.undo()  # You selected amendment 3
        self.assertEqual(file.data, ['other line2', 'other line', 'first line', 'second line', 'third line'])
        file.redo()  # You selected amendment 4
        self.assertEqual(file.data,
                         ['other line', 'other line', 'first line', 'second line', 'third line'])

    def test_json(self):
        data = {'key': 'value', 'key2': 'value2', 'key3': 'value3'}
        file = FileIO.create('test.json', data)
        self.assertEqual(file.data, {'key': 'value', 'key2': 'value2', 'key3': 'value3'})

        # Iterable
        for key, value in file.items():
            pass

        self.assertEqual(file['key'], 'value')

        # Insert Data
        file['key4'] = 'value4'
        self.assertEqual(file.data, {'key': 'value', 'key2': 'value2', 'key3': 'value3', 'key4': 'value4'})

    def test_csv(self):
        file = FileIO.create('test.csv', data=[], cols=('col1', 'col2', 'col3'), fill_with=0)  # ram only, not yet saved
        file.add([1, 2, 3])
        self.assertEqual(file.data, [[1, 2, 3]])
        file.add([1, 2])
        self.assertEqual(file.data, [[1, 2, 3], [1, 2, 0]])

        # convert to dict
        self.assertEqual(file.to_dict(), {'col1': (1, 1), 'col2': (2, 2), 'col3': (3, 0)})

        # or get generation row by row with col
        self.assertEqual(list(file.data), [{'col1': 1, 'col2': 2, 'col3': 3}, {'col1': 1, 'col2': 2, 'col3': 0}])

        # Iterable
        for row in file:
            pass

        # indexing col values
        self.assertEqual(file['col1'], (1, 1))
        # or use index and get a row
        self.assertEqual(file[0], [1, 2, 3])
        self.assertEqual(file.flatten(), [1, 2, 3, 1, 2, 0])
