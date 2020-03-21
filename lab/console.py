from abc import ABCMeta as ABC, abstractmethod


class ConsoleArea(metaclass=ABC):
    def __init__(self, name: str, length: int, text_color: str = "default"):
        self.__text = None
        self.name = name
        self.length = length
        self.text_color = text_color

    @property
    def text(self):
        return self.__text

    @text.setter
    def text(self, value):
        self.__text = value

    def print_(self):
        print(self.name +" " + self.__text)

    @abstractmethod
    def write(self, value):
        self.__text = value

    @abstractmethod
    def clean(self):
        self.__text = ''

    @abstractmethod
    def flush(self):
        pass


class ConsoleBase(metaclass=ABC):
    __MAX_LENGTH = 120
    __MAX_AREAS = 5
    __AREAS = []

    def __init__(self, name="Cereja", length=10):
        self.__text = None
        self.__length = length
        self.__name = name

    @property
    def name(self):
        return self.__name

    @name.setter
    def name(self, name):
        self.__name = name

    def say(self, txt):
        for i in self.__AREAS:
            i.text = txt
            i.print_()

    @classmethod
    def register(cls, area):
        if len(cls.__AREAS) < cls.__MAX_AREAS:
            cls.__AREAS.append(area)
        else:
            raise Exception("CHEIO")
        return cls


class Console(ConsoleArea):

    def clean(self):
        pass

    def flush(self):
        pass

    def write(self, value):
        pass


class T(ConsoleBase):
    def new_area(self, console):
        self.register(console)


if __name__ == '__main__':
    console = T("Cereja")
    for i in range(5):
        a = Console(f"Test {i}", 10)
        console.register(a)
    console.say("oi")
