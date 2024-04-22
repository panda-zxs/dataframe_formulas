# -*- coding: utf-8 -*-

import numpy as np
import regex
import schedula as sh

from ..exceptions import FormulaError, TokenError
from . import Token
from .parenthesis import _update_n_args


class XlError(sh.Token):
    pass


class Operand(Token):
    def ast(self, tokens, stack, builder):
        if tokens and isinstance(tokens[-1], Operand):
            raise TokenError()
        super(Operand, self).ast(tokens, stack, builder)
        builder.append(self)
        _update_n_args(stack)


class String(Operand):
    _re = regex.compile(r"""^\s*"(?P<name>(?>""|[^"])*)"\s*|^\s*'(?P<name>(?>''|[^'])*)'\s*""")

    def compile(self):
        return self.name.replace('""', '"').replace("''", "'")

    def set_expr(self, *tokens):
        self.attr['expr'] = '"%s"' % self.name


class Empty(Operand):
    def __init__(self):
        self.source, self.attr = None, {'name': ''}

    @staticmethod
    def compile():
        return 0


_re_error = regex.compile(
    r'''
    ^\s*(?>
        (?>
            '(\[(?>[^\[\]]+)\])?
            (?>(?>''|[^\?!*\/\[\]':"])+)?'
        |
            (\[(?>[0-9]+)\])(?>(?>''|[^\?!*\/\[\]':"])+)?
        |
            (?>[^\W\d][\w\.]*)
        |
            '(?>(?>''|[^\?!*\/\[\]':"])+)'
        )!
    )?(?P<name>\#(?>NULL!|DIV/0!|VALUE!|REF!|NUM!|NAME\?|N/A))\s*
''', regex.IGNORECASE | regex.X | regex.DOTALL)


class Error(Operand):
    _re = _re_error
    errors = {
        "#NULL!": None,
        "#N/A": np.nan,
        "#NAME?": None,
        "#NUM!": np.nan,
        "#REF!": None,
        "#VALUE!": np.nan,
        "#DIV/0!": np.nan,
    }

    def compile(self):
        return self.errors[self.name]


class Number(Operand):
    _re = regex.compile(
        r'^\s*(?P<name>[0-9]+(?>\.[0-9]+)?(?>E[+-][0-9]+)?|'
        r'TRUE(?!\(\))|FALSE(?!\(\)))(?!([a-z]|[0-9]|\.|\s*\:))\s*', regex.IGNORECASE)

    def compile(self):
        return eval(self.name.capitalize())


class Column(Operand):
    _re = regex.compile(r'^(?P<name>[\u4E00-\u9FA5A-Za-z0-9_]+)(?P<raise>[\(\.]?)',
                        regex.IGNORECASE | regex.X | regex.DOTALL)

    def process(self, match, context=None):
        return super(Column, self).process(match, context)

    def __repr__(self):
        if self.attr.get('is_ranges', False):
            return '{} <{}>'.format(self.name, Column.__name__)
        else:
            return '{} <{}>'.format(self.name, Column.__name__)

    def compile(self):
        if self.df is None:
            raise FormulaError("数据集不存在")
        if self.name.startswith("策略衍生_"):
            # raise FormulaError("公式暂不支持衍生变量")
            if not self.custom_var_map:
                raise FormulaError("衍生变量定义字典custom_var_map不存在")
            if self.name not in self.custom_var_map:
                raise FormulaError("衍生变量{}在字典中不存在".format(self.name))
            if self.custom_var_map[self.name]["var"] not in self.df.columns:
                raise FormulaError("变量名{}不存在".format(self.name))
            return self.df[self.custom_var_map[self.name]["var"]].to_numpy()
        if self.name not in self.df.columns:
            raise FormulaError("变量名{}不存在".format(self.name))
        arr = self.df[self.name].to_numpy()
        return arr


class CustomColumn(Operand):
    _re = regex.compile(r'^\[(?P<name>[\u4E00-\u9FA5A-Za-z0-9_]+)\](?P<raise>[\(\.]?)',
                        regex.IGNORECASE | regex.X | regex.DOTALL)

    def process(self, match, context=None):
        return super(CustomColumn, self).process(match, context)

    def __repr__(self):
        if self.attr.get('is_ranges', False):
            return '{} <{}>'.format(self.name, Column.__name__)
        else:
            return '{} <{}>'.format(self.name, Column.__name__)

    def compile(self):
        # raise FormulaError("公式暂不支持引用衍生变量")
        if self.df is None:
            raise FormulaError("数据集不存在")
        if not self.custom_var_map:
            raise FormulaError("衍生变量定义字典custom_var_map不存在")
        if "策略衍生_" + self.name not in self.custom_var_map:
            raise FormulaError("衍生变量{}在字典中不存在".format(self.name))
        if self.custom_var_map["策略衍生_" + self.name]["var"] not in self.df.columns:
            raise FormulaError("变量名{}不存在".format(self.name))
        return self.df[self.custom_var_map["策略衍生_" + self.name]["var"]].to_numpy()
