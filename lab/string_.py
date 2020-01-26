import string
import re
from typing import AnyStr, Sequence


def str_gen(pattern: AnyStr) -> Sequence[AnyStr]:
    regex = re.compile(pattern)
    return regex.findall(string.printable)


if __name__ == '__main__':
    print(str_gen('[0-9]'))
