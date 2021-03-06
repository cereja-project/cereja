import tempfile
import unittest
from abc import abstractmethod

from cereja.system import Path
from cereja.mltools.preprocess import separate
from cereja.mltools.data import Tokenizer


class FileIOTest(unittest.TestCase):
    data = None

    def test_sanity(self):
        with tempfile.TemporaryDirectory() as tempdir:
            to_encode = 'oi tudo tranquilo'
            tokenizer = Tokenizer(['oi amigo tudo bem'], preprocess_function=separate, use_unk=False)

            self.assertEqual(tokenizer.last_index, 13)
            encoded = tokenizer.encode([to_encode])
            valid_encode_tokens = [[tokenizer._item_to_index['oi'], tokenizer._item_to_index['tudo'],
                                    tokenizer._item_to_index['tranquilo']]]
            self.assertEqual(tokenizer.last_index, 14)
            self.assertEqual(encoded, valid_encode_tokens)
            decoded = ' '.join(tokenizer.decode(encoded[0]))
            self.assertEqual(decoded, to_encode)
            temp_file = Path(tempdir).join('tokenizer.json')
            tokenizer.to_json(temp_file)

            # Valid.
            tokenizer = Tokenizer.load_from_json(temp_file)
            encoded = tokenizer.encode([to_encode])
            self.assertEqual(tokenizer.last_index, 14)
            self.assertEqual(encoded, valid_encode_tokens)
            decoded = ' '.join(tokenizer.decode(encoded[0]))
            self.assertEqual(decoded, to_encode)
