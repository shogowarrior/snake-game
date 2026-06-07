class Pin:
    IN = 0
    OUT = 1
    PULL_UP = 2

    def __init__(self, *args, **kwargs):
        self._value = 1

    def value(self, v=None):
        if v is None:
            return self._value
        self._value = v
