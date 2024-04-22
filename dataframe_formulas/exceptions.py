# -*- coding: utf-8 -*-

class BaseError(Exception):
    def __init__(self, msg=""):
        super(Exception, self).__init__(msg)
        self.msg = msg


class FormulaError(BaseError):
    def __init__(self, msg="公式解析错误"):
        super(FormulaError, self).__init__(msg=msg)


class RangeValueError(Exception):
    ...


class InvalidRangeError(Exception):
    ...


class ParenthesesError(BaseError):
    def __init__(self, msg="缺少括号"):
        super(ParenthesesError, self).__init__(msg=msg)


class TokenError(Exception):
    ...


class BroadcastError(Exception):
    ...


class FoundError(Exception):
    ...
