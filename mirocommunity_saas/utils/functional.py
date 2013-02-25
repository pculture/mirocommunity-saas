MISSING = object()


class cached_property(object):
    def __init__(self, func):
        self.__name__ = func.__name__
        self.__module__ = func.__module__
        self.__doc__ = func.__doc__
        self.func = func

    def __get__(self, instance, owner):
        if instance is None:
            return self

        value = instance.__dict__.get(self.__name__, MISSING)
        if value is MISSING:
            value = self.func(instance)
            instance.__dict__[self.__name__] = value
        return value
