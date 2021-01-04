"""

Copyright (c) 2019 The Cereja Project

Permission is hereby granted, free of charge, to any person obtaining a copy
of this software and associated documentation files (the "Software"), to deal
in the Software without restriction, including without limitation the rights
to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
copies of the Software, and to permit persons to whom the Software is
furnished to do so, subject to the following conditions:

The above copyright notice and this permission notice shall be included in all
copies or substantial portions of the Software.

THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
SOFTWARE.
"""

import re
from typing import AnyStr, Sequence, Union, List
from unicodedata import normalize as _normalize

from cereja.config._constants import ENG_CONTRACTIONS, PUNCTUATION, VALID_LANGUAGE_CHAR, LANGUAGES, STOP_WORDS

_NORMALIZE_VALUES = ''.join(PUNCTUATION)


def separate(text: AnyStr, sep: Union[AnyStr, Sequence[AnyStr]] = PUNCTUATION, between_char=False) -> str:
    """
    Creating a space between an element in sep values
    PUNCTUATION = {'?', '!', ',', '.'}
    e.g:

    >>> separate('how are you?', sep='?')
    'how are you ?'
    >>> separate('how are you,man?', sep=('?',','), between_char=True)
    'how are you , man ?'

    :param text: Any text
    :param sep: values that will be separated. Accepted types (str, list and tuple)
    :param between_char: if True the sep values that's on between chars it will be separated.
                         eg. "it's" -> "it ' s"
    :return: processed text
    """
    if isinstance(sep, str):
        sep = (sep,)
    assert isinstance(sep, (tuple, list)), f"{type(sep)} is not acceptable. Only (str, list and tuple) types"
    assert isinstance(text, str), f"{type(text)} is not acceptable. Only str type."
    new_text = []
    for word in text.split():
        for i in sep:
            if (word.startswith(i) or word.endswith(i)) or between_char is True:
                word = f' {i} '.join(word.split(i)).strip()
        new_text += word.split()
    return ' '.join(new_text)


def accent_remove(text: AnyStr) -> AnyStr:
    return _normalize("NFD", text).encode("ascii", "ignore").decode("UTF-8")


def replace_english_contractions(sentence: AnyStr) -> str:
    """
    Returns phrase without contractions
    """
    replaced_sentence = []
    for word in sentence.split(' '):
        if word.lower() in ENG_CONTRACTIONS:
            # Todo: create function that chooses the appropriate value
            word = ENG_CONTRACTIONS.get(word.lower()).split(',')[0]
        replaced_sentence.append(word)
    return ' '.join(replaced_sentence)


def remove_extra_chars(sentence: str) -> str:
    """
    Replaces unnecessary blanks and punctuation
    analyzed values -> ['?', '!', ',', '.', ' ']
    e.g
        'i   like it!!!' --> 'i like it!'
    """
    sentence = re.sub(f"([{_NORMALIZE_VALUES}])+", r'\1', sentence)
    return re.sub('[\t\n\r\x0b\x0c ]+', " ", sentence).strip()


def remove_non_language_elements(sentence: str) -> str:
    for invalid in set(sentence).difference(VALID_LANGUAGE_CHAR):
        sentence = sentence.replace(invalid, '')
    return sentence.strip()


def remove_punctuation(sentence: str, punctuation: str = None):
    """
    Default Punctuation -> [',', '!', '#', '$', '%', "'", '*', '+', '-', '.', '/', '?', '@', '\\', '^', '_', '~']
    """
    punctuation = punctuation or ''.join(PUNCTUATION)
    for x in punctuation:
        sentence = sentence.replace(x, '')
    return sentence.strip()


def remove_stop_words(sentence: str, stop_words: List[str] = None, language: str = 'english'):
    """
    Default Stop Words -> ['is', 'are', 'am', 'at', 'a', 'an', 'of', 'the']
    """
    language = language.lower()
    if language not in LANGUAGES:
        print(f'Idioma "{language}" não encontrado. Idiomas disponíveis: {LANGUAGES}')

    stop_words = stop_words if stop_words else STOP_WORDS.get(language, None)
    sentence = ' '.join([word for word in sentence.split() if word.lower() not in stop_words]) if stop_words \
               else sentence
    return sentence.strip()
