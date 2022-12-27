from pydantic import BaseModel


class ConvertMixinS:
    def values_except_null(self):
        assert isinstance(self, BaseModel), 'Must be instance of `BaseModel`.'
        return {
            k: getattr(self, k)
            for k in self.__fields__.keys() if getattr(self, k)
        }
