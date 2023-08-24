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

from ..system.unicode import Unicode
import string

NUMBER_WORDS = {
    'pt':
        {
            'um':         1, 'dois': 2, 'três': 3, 'quatro': 4, 'cinco': 5, 'seis': 6, 'sete': 7, 'oito': 8,
            'nove':       9,
            'dez':        10, 'onze': 11, 'doze': 12, 'treze': 13, 'catorze': 14, 'quinze': 15, 'dezesseis': 16,
            'dezessete':  17, 'dezoito': 18, 'dezenove': 19,
            'vinte':      20, 'trinta': 30, 'quarenta': 40, 'cinquenta': 50, 'sessenta': 60, 'setenta': 70,
            'oitenta':    80, 'noventa': 90,
            'cem':        100, 'cento': 100, 'duzentos': 200, 'trezentos': 300, 'quatrocentos': 400,
            'quinhentos': 500,
            'seiscentos': 600, 'setecentos': 700, 'oitocentos': 800, 'novecentos': 900,
            'mil':        1000, 'milhão': 1000000, 'bilhão': 1000000000, 'trilhão': 1000000000000
        },
    'en':
        {
            'one':       1, 'two': 2, 'three': 3, 'four': 4, 'five': 5, 'six': 6, 'seven': 7, 'eight': 8, 'nine': 9,
            'ten':       10, 'eleven': 11, 'twelve': 12, 'thirteen': 13, 'fourteen': 14, 'fifteen': 15, 'sixteen': 16,
            'seventeen': 17, 'eighteen': 18, 'nineteen': 19,
            'twenty':    20, 'thirty': 30, 'forty': 40, 'fifty': 50, 'sixty': 60, 'seventy': 70, 'eighty': 80,
            'ninety':    90,
            'hundred':   100, 'thousand': 1000, 'million': 1000000, 'billion': 1000000000, 'trillion': 1000000000000
        }}

ENG_CONTRACTIONS = {
    "ain't":        "am not,are not,is not,has not,have not",
    "aren't":       "are not,am not",
    "can't":        "cannot",
    "can't've":     "cannot have",
    "'cause":       "because",
    "could've":     "could have",
    "couldn't":     "could not",
    "couldn't've":  "could not have",
    "didn't":       "did not",
    "doesn't":      "does not",
    "don't":        "do not",
    "hadn't":       "had not",
    "hadn't've":    "had not have",
    "hasn't":       "has not",
    "haven't":      "have not",
    "he'd":         "he had,he would",
    "he'd've":      "he would have",
    "he'll":        "he shall,he will",
    "he'll've":     "he shall have,he will have",
    "he's":         "he has,he is",
    "how'd":        "how did",
    "how'd'y":      "how do you",
    "how'll":       "how will",
    "how's":        "how has,how is,how does",
    "i'd":          "i had,i would",
    "i'd've":       "i would have",
    "i'll":         "i shall,i will",
    "i'll've":      "i shall have,i will have",
    "i'm":          "i am",
    "i've":         "i have",
    "isn't":        "is not",
    "it'd":         "it had,it would",
    "it'd've":      "it would have",
    "it'll":        "it shall,it will",
    "it'll've":     "it shall have,it will have",
    "it's":         "it has,it is",
    "let's":        "let us",
    "ma'am":        "madam",
    "mayn't":       "may not",
    "might've":     "might have",
    "mightn't":     "might not",
    "mightn't've":  "might not have",
    "must've":      "must have",
    "mustn't":      "must not",
    "mustn't've":   "must not have",
    "needn't":      "need not",
    "needn't've":   "need not have",
    "o'clock":      "of the clock",
    "oughtn't":     "ought not",
    "oughtn't've":  "ought not have",
    "shan't":       "shall not",
    "sha'n't":      "shall not",
    "shan't've":    "shall not have",
    "she'd":        "she had,she would",
    "she'd've":     "she would have",
    "she'll":       "she shall,she will",
    "she'll've":    "she shall have,she will have",
    "she's":        "she has,she is",
    "should've":    "should have",
    "shouldn't":    "should not",
    "shouldn't've": "should not have",
    "so've":        "so have",
    "so's":         "so as,so is",
    "that'd":       "that would,that had",
    "that'd've":    "that would have",
    "that's":       "that has,that is",
    "there'd":      "there had,there would",
    "there'd've":   "there would have",
    "there's":      "there has,there is",
    "they'd":       "they had,they would",
    "they'd've":    "they would have",
    "they'll":      "they shall,they will",
    "they'll've":   "they shall have,they will have",
    "they're":      "they are",
    "they've":      "they have",
    "to've":        "to have",
    "wasn't":       "was not",
    "we'd":         "we had,we would",
    "we'd've":      "we would have",
    "we'll":        "we will",
    "we'll've":     "we will have",
    "we're":        "we are",
    "we've":        "we have",
    "weren't":      "were not",
    "what'll":      "what shall,what will",
    "what'll've":   "what shall have,what will have",
    "what're":      "what are",
    "what's":       "what has,what is",
    "what've":      "what have",
    "when's":       "when has,when is",
    "when've":      "when have",
    "where'd":      "where did",
    "where's":      "where has,where is",
    "where've":     "where have",
    "who'll":       "who shall,who will",
    "who'll've":    "who shall have,who will have",
    "who's":        "who has,who is",
    "who've":       "who have",
    "why's":        "why has,why is",
    "why've":       "why have",
    "will've":      "will have",
    "won't":        "will not",
    "won't've":     "will not have",
    "would've":     "would have",
    "wouldn't":     "would not",
    "wouldn't've":  "would not have",
    "y'all":        "you all",
    "y'all'd":      "you all would",
    "y'all'd've":   "you all would have",
    "y'all're":     "you all are",
    "y'all've":     "you all have",
    "you'd":        "you had,you would",
    "you'd've":     "you would have",
    "you'll":       "you shall,you will",
    "you'll've":    "you shall have,you will have",
    "you're":       "you are",
    "you've":       "you have",
}
PUNCTUATION = [
    ",",
    "!",
    "#",
    "$",
    "%",
    "'",
    "*",
    "+",
    "-",
    ".",
    "/",
    "?",
    "@",
    "\\",
    "^",
    "_",
    "~",
]
STOP_WORDS = {
    "english":    ["is", "are", "am", "at", "a", "an", "of", "the"],
    "portuguese": [
        "em",
        "do",
        "da",
        "de",
        "pro",
        "pra",
        "no",
        "dos",
        "na",
        "os",
        "à",
        "pela",
        "nas",
        "num",
        "das",
        "numa",
        "nos",
        "às",
        "pelas",
        "as",
        "uns",
        "umas",
        "lhe",
        "é",
        "o",
        "a",
    ],
}
LANGUAGES = {"english", "portuguese"}
VALID_LANGUAGE_CHAR = {chr(i) for i in range(10000) if "LETTER" in Unicode(i).name}
VALID_LANGUAGE_CHAR.update(string.digits)
VALID_LANGUAGE_CHAR.update(",!%$?-.")
VALID_LANGUAGE_CHAR.update(" ")

DATA_UNIT_MAP = {"B": 1.0e0, "KB": 1.0e3, "MB": 1.0e6, "GB": 1.0e9, "TB": 1.0e12}

PROXIES_URL = "https://raw.githubusercontent.com/jetkai/proxy-list/main/online-proxies/json/proxies.json"
