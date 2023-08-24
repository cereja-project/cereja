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
from typing import AnyStr, Sequence, Union, List, Tuple
from unicodedata import normalize as _normalize

from ..config import (
    ENG_CONTRACTIONS,
    PUNCTUATION,
    VALID_LANGUAGE_CHAR,
    LANGUAGES,
    STOP_WORDS,
)

_NORMALIZE_VALUES = "".join(PUNCTUATION)


def split_by_punct(text: str, punct: str = '.!?') -> list:
    """
    split text by periods.

    :param text: any string
    :param punct: string of chars
    :return:
    """
    assert isinstance(punct, str), 'Send punct send the strings in string format: "!.?"'
    # Regular expression to split text by periods
    pattern = r'(?<=[%s])\s+' % punct
    texts = re.split(pattern, text)
    return texts


def decimal_por_extenso(extenso):
    unidades = {
        'um': 1, 'dois': 2, 'três': 3, 'quatro': 4, 'cinco': 5, 'seis': 6, 'sete': 7, 'oito': 8, 'nove': 9,
        'dez': 10, 'onze': 11, 'doze': 12, 'treze': 13, 'catorze': 14, 'quinze': 15, 'dezesseis': 16, 'dezessete': 17, 'dezoito': 18, 'dezenove': 19
    }
    dezenas = {
        'dez': 10, 'vinte': 20, 'trinta': 30, 'quarenta': 40, 'cinquenta': 50, 'sessenta': 60, 'setenta': 70, 'oitenta': 80, 'noventa': 90
    }
    centenas = {
        'cento': 100, 'duzentos': 200, 'trezentos': 300, 'quatrocentos': 400, 'quinhentos': 500, 'seiscentos': 600, 'setecentos': 700, 'oitocentos': 800, 'novecentos': 900
    }
    milhares = {
        'mil': 1000, 'milhão': 1000000, 'bilhão': 1000000000, 'trilhão': 1000000000000, 'quatrilhão': 1000000000000000,
        'quintilhão': 1000000000000000000, 'sextilhão': 1000000000000000000000
        # Adicione mais valores para números maiores, se necessário
    }

    def por_extenso_para_decimal(extenso):
        partes = extenso.split()
        resultado = 0
        soma_parcial = 0
        for palavra in partes:
            if palavra in unidades:
                soma_parcial += unidades[palavra]
            elif palavra in dezenas:
                soma_parcial += dezenas[palavra]
            elif palavra in centenas:
                soma_parcial += centenas[palavra]
            elif palavra in milhares:
                resultado += soma_parcial * milhares[palavra]
                soma_parcial = 0
        resultado += soma_parcial
        return resultado

    extenso = extenso.replace('vírgula', '')  # Remover 'vírgula', caso esteja presente
    extenso = extenso.replace(' e ', ' ')  # Remover ' e ' entre palavras
    extenso = extenso.replace('-', ' ')  # Remover hífens, se houver

    return por_extenso_para_decimal(extenso)


def remove_delimited_text(text, delimiters: Sequence[Tuple[AnyStr, AnyStr]] = (("*", '*'), ("(", ")"), ("[", "]"))):
    """
    Remove words or phrases delimited by bullets from the provided text.

    Arguments:
      text(str): The text to be processed.
      delimiters (Sequence[Tuple[AnyStr, AnyStr]], optional): A sequence of tuples that specify the start and end markers of the delimited words or phrases.
          The default is (("*", '*'), ("(", ")"), ("[", "]")).

    Returns:
      str: The rendered text, without the delimited words or phrases.

    Example:
      >>> text = "Hello world of *options*! [shows options] How are you (walks out and says)?"
      >>> clear_text = remove_delimited_text(text)
      >>> print(clear_text)
      "Hello world! How are you?"
    """
    pattern = '|'.join(f'({re.escape(start)}{r".*?"}{re.escape(end)})' for start, end in delimiters)
    text = re.sub(pattern, "", text)
    return text


def separate(
        text: AnyStr, sep: Union[AnyStr, Sequence[AnyStr]] = PUNCTUATION, between_char=False
) -> str:
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
    assert isinstance(
            sep, (tuple, list)
    ), f"{type(sep)} is not acceptable. Only (str, list and tuple) types"
    assert isinstance(text, str), f"{type(text)} is not acceptable. Only str type."
    new_text = []
    for word in text.split():
        for i in sep:
            if (word.startswith(i) or word.endswith(i)) or between_char is True:
                word = f" {i} ".join(word.split(i)).strip()
        new_text += word.split()
    return " ".join(new_text)


def accent_remove(text: AnyStr) -> AnyStr:
    return _normalize("NFD", text).encode("ascii", "ignore").decode("UTF-8")


def replace_english_contractions(sentence: AnyStr) -> str:
    """
    Returns phrase without contractions
    """
    replaced_sentence = []
    for word in sentence.split(" "):
        if word.lower() in ENG_CONTRACTIONS:
            # Todo: create function that chooses the appropriate value
            word = ENG_CONTRACTIONS.get(word.lower()).split(",")[0]
        replaced_sentence.append(word)
    return " ".join(replaced_sentence)


def remove_extra_chars(sentence: str) -> str:
    """
    Replaces unnecessary blanks and punctuation
    analyzed values -> ['?', '!', ',', '.', ' ']
    e.g
        'i   like it!!!' --> 'i like it!'
    """
    sentence = re.sub(f"([{_NORMALIZE_VALUES}])+", r"\1", sentence)
    return re.sub("[\t\n\r\x0b\x0c ]+", " ", sentence).strip()


def remove_non_language_elements(sentence: str) -> str:
    for invalid in set(sentence).difference(VALID_LANGUAGE_CHAR):
        sentence = sentence.replace(invalid, "")
    return sentence.strip()


def remove_punctuation(sentence: str, punctuation: str = None):
    """
    Default Punctuation -> [',', '!', '#', '$', '%', "'", '*', '+', '-', '.', '/', '?', '@', '\\', '^', '_', '~']
    """
    punctuation = punctuation or "".join(PUNCTUATION)
    for x in punctuation:
        sentence = sentence.replace(x, "")
    return sentence.strip()


def remove_stop_words(
        sentence: str, stop_words: List[str] = None, language: str = "english"
):
    """
    Default Stop Words -> ['is', 'are', 'am', 'at', 'a', 'an', 'of', 'the']
    """
    language = language.lower()
    if language not in LANGUAGES:
        print(f'Idioma "{language}" não encontrado. Idiomas disponíveis: {LANGUAGES}')

    stop_words = stop_words if stop_words else STOP_WORDS.get(language, None)
    sentence = (
        " ".join([word for word in sentence.split() if word.lower() not in stop_words])
        if stop_words
        else sentence
    )
    return sentence.strip()


def preprocess(
        text: str,
        is_destructive: bool = False,
        is_lower: bool = None,
        is_remove_accent: bool = None,
        is_remove_punctuation: bool = None,
):
    """
    Run pack of preprocess functions

    non-destructive functions: remove_extra_chars, remove_non_language_elements and separate
    destructive functions: lower, accent_remove and remove_punctuation

    @param text: any string data.
    @param is_destructive: is a bool value, if True exec non-destructive and destructive functions
    @param is_lower: bool
    @param is_remove_accent: bool
    @param is_remove_punctuation: bool
    @return: preprocessed text
    """
    if is_destructive or is_lower:
        text = text.lower()
    text = remove_extra_chars(text)
    text = remove_non_language_elements(text)
    if is_destructive or is_remove_accent:
        text = accent_remove(text)

    if is_destructive or is_remove_punctuation:
        text = remove_punctuation(text)
    else:
        text = separate(text)
    return text
