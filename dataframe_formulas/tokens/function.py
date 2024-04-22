# -*- coding: utf-8 -*-

import inspect

import regex

from ..exceptions import BaseError
from . import Token
from .parenthesis import Parenthesis


class Function(Token):
    _re = regex.compile(r'^\s*@?(?P<name>[A-Z_][\w\.]*)\(\s*', regex.IGNORECASE)

    def ast(self, tokens, stack, builder, check_n=lambda *args: True):
        super(Function, self).ast(tokens, stack, builder)
        stack.append(self)
        t = Parenthesis('(')
        t.attr['check_n'] = check_n
        t.ast(tokens, stack, builder)

    def compile(self):
        from ..functions import get_functions
        return get_functions()[self.name.upper()]

    def set_expr(self, *tokens):
        func = self.compile()
        if isinstance(func, dict):
            func = func["function"]
        if func.__name__ == "not_implemented":
            raise BaseError("方法{}定义不存在".format(self.name.upper()))
        try:
            parameters = inspect.signature(func).parameters
            required_parameters = [
                name for name, param in parameters.items() if param.default == inspect.Parameter.empty
            ]
            required_parameter_count = len(required_parameters)
            if len(tokens) < required_parameter_count:
                raise BaseError("方法{}缺少入参".format(self.name.upper()))
        except Exception:
            pass
        args = ', '.join(t.get_expr for t in tokens)
        self.attr['expr'] = '%s(%s)' % (self.name.upper(), args)
