import re
from typing import AnyStr, Sequence, Union
from unicodedata import normalize as _normalize

from cereja._constants import ENG_CONTRACTIONS, PUNCTUATION, VALID_LANGUAGE_CHAR

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
    return re.sub(f" +", " ", sentence)


def remove_non_language_elements(sentence: str) -> str:
    for invalid in set(sentence).difference(VALID_LANGUAGE_CHAR):
        sentence = sentence.replace(invalid, '')
    return sentence.strip()
