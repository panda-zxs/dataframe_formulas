# -*- coding: utf-8 -*-

import datetime
import random
import string
import time

import numpy as np
import pandas as pd
import regex
import schedula
import vaex

from .builder import AstBuilder
from .exceptions import BaseError, FormulaError, TokenError
from .functions import Array, get_functions
from .tokens.function import Function
from .tokens.operand import Column, CustomColumn, Error, Number, String
from .tokens.operator import OperatorToken, Separator
from .tokens.parenthesis import Parenthesis


class Parser(object):
    formula_check = regex.compile(r"""
        (?P<value>^=\s*(?P<name>\S.*)$)
        """, regex.IGNORECASE | regex.X | regex.DOTALL)
    ast_builder = AstBuilder
    # 错误、字符串、数字、列名、运算符、逗号、方法、括号
    filters = [
        Error,
        Number,
        String,
        Column,
        CustomColumn,
        OperatorToken,
        Separator,
        Function,
        Parenthesis,
    ]

    def __init__(self, df=vaex.dataframe.DataFrameLocal(), custom_var_map=None):
        """
        params: df: 数据集
        params: custom_var_map: 变量映射关系 {column_alias: {
            "var": new_column,
            # 前端展示名称
            "alias": column_alias,
            "role": "predict",
            # 格式化后的自定义生成公式
            "format_formula": self.format_formula,
            # 原始自定义生成公式
            "formula": self.formula,
            # 是否为自定义
            "is_custom": 1,
            "type": _type,
            "extra": {},
            "group_var": 1,
            "delete_var": 0,
            "sample_data": self.df[new_column].head(50).unique().tolist(),
            "binning_type": binning_type,
            # 是否禁用
            "disable": 0,
            "iv": 0,
        }}
        """
        self.format_formula = None
        self.formula = None
        self.df = df
        self.custom_var_map = {i["alias"]: i for i in custom_var_map.values()}
        self.formula_columns = []
        self.formula_custom_columns = []

    def set_df(self, df):
        self.df = df

    def open_file(self, df_path):
        self.df = vaex.open(df_path)

    def is_formula(self, value):
        return bool(self._formula(value)) or False

    def _formula(self, value):
        return self.formula_check.match(value)

    def _set_format_formula(self, tokens):
        __format_formula = ["="]
        for t in tokens:
            if isinstance(t, String):
                __format_formula.append("'{}'".format(t.name))
            elif isinstance(t, Function):
                __format_formula.append(t.name.upper())
            elif isinstance(t, Column) and t.name.startswith("策略衍生_"):
                __format_formula.append(self.custom_var_map[t.name]["format_formula"].strip("="))
            elif isinstance(t, CustomColumn):
                __format_formula.append(self.custom_var_map["策略衍生_" + t.name]["format_formula"].strip("="))
            else:
                __format_formula.append(t.name)
        self.format_formula = "".join(__format_formula)

    def ast(self, expression, context=None):
        try:
            self.formula = expression
            match = self._formula(expression).groupdict()
            # match = self._formula(expression.replace('\n', '').replace('    ',
            #                                                            '').replace(' ', '').replace('"',
            #                                                                                         "'")).groupdict()
            expr = match['name']
            # self.format_formula = "=" + match['name']
        except (AttributeError, KeyError):
            raise FormulaError
        builder = self.ast_builder(match=match, df=self.df, custom_var_map=self.custom_var_map)
        filters, tokens, stack = self.filters, [], []
        Parenthesis('(').ast(tokens, stack, builder)
        while expr:
            for f in filters:
                try:
                    token = f(expr, context)
                    token.ast(tokens, stack, builder)
                    expr = expr[token.end_match:]
                    if isinstance(token, Column):
                        if token.name.startswith("策略衍生_"):
                            self.formula_custom_columns.append(token.name)
                            subp = Parser(df=self.df, custom_var_map=self.custom_var_map)
                            subp.ast(self.custom_var_map[token.name]["format_formula"])
                            self.formula_columns.extend(subp.formula_columns)
                        else:
                            self.formula_columns.append(token.name)
                    elif isinstance(token, CustomColumn):
                        subp = Parser(df=self.df, custom_var_map=self.custom_var_map)
                        subp.ast(self.custom_var_map["策略衍生_" + token.name]["format_formula"])
                        self.formula_columns.extend(subp.formula_columns)
                        self.formula_custom_columns.append("策略衍生_" + token.name)
                    break
                except TokenError:
                    pass
            else:
                raise FormulaError()
        Parenthesis(')').ast(tokens, stack, builder)
        tokens = tokens[1:-1]
        self._set_format_formula(tokens)
        while stack:
            if isinstance(stack[-1], Parenthesis):
                raise FormulaError()
            builder.append(stack.pop())
        if len(builder) != 1:
            raise FormulaError()
        builder.finish()
        self.formula_columns = list(set(self.formula_columns))
        return tokens, builder

    def run(self, expression):
        if len(self.df) == 0:
            raise BaseError("未发现数据集, 请配置")
        try:
            _, builder = self.ast(expression)
            f = builder.compile()
            rst = f()
            if not isinstance(rst, np.ndarray):
                rst = np.array([rst])
            elif isinstance(rst, Array):
                rst = np.array(rst.tolist())
        except ValueError:
            raise BaseError("公式运算错误")
        except schedula.DispatcherError:
            raise BaseError("公式运算错误")
        if len(rst) < len(self.df):
            if len(rst) == 1:
                rst = np.full(len(self.df), rst[0])
            else:
                rst = rst.resize(range(len(self.df)))
        return rst

    def test(self, expression):
        try:
            self.df = self.df.head(10)
            arr = self.run(expression)
            sr = pd.Series(arr)
            sr = sr.infer_objects()
            context = str(sr)
            # if arr.dtype in (np.float64, np.float32, np.int32, np.int64):
            # if np.all(np.isnan(arr)):
            #     context = "逻辑生成的变量存在空值, 不可进行当前操作"
            # else:
            #     sr = pd.Series(arr)
            #     sr = sr.infer_objects()
            #     context = str(sr)
            # else:
            #     sr = pd.Series(arr)
            #     sr = sr.infer_objects()
            #     context = str(sr)
            return "运算成功", context
        except BaseError as e:
            return "运算失败", e.msg
        except Exception as e:
            import traceback
            print(traceback.format_exc())
            return "运算失败", str(e)

    def _new_var_name(self, prefix):
        while True:
            _prefix = "{}_{}_".format(prefix, datetime.datetime.now().strftime("%Y%m%d")[2:])
            words = string.ascii_lowercase + string.digits
            random.seed(time.time())

            new_column = _prefix + ''.join(random.sample(words, 10))
            if new_column not in self.df.columns:
                break
        return new_column

    def add_column(self, formula, dtype=None, prefix="custom", column_name=None, force=False):
        if column_name:
            if force:
                new_column = column_name
            else:
                if column_name not in self.df.columns:
                    new_column = column_name
                else:
                    new_column = self._new_var_name(prefix)
        else:
            new_column = self._new_var_name(prefix)
        arr = self.run(formula)
        sr = pd.Series(arr, name=new_column)
        if dtype:
            try:
                sr = sr[column_name].astype(dtype)
            except Exception:
                raise BaseError("衍生列不支持转换为{}类型".format(dtype))
        else:
            sr = sr.infer_objects()
        # if sr.isna().values.any():
        #     raise BaseError("逻辑生成的变量存在空值, 不可进行当前操作")
        _dtype = sr.dtype
        ndf = vaex.from_dict({new_column: sr.tolist()})
        if _dtype == "object":
            _type = "str"
            binning_type = "scatter"
            if new_column in self.df.get_column_names():
                self.df[new_column] = ndf[new_column].values
                self.df[new_column] = self.df[new_column].astype("string")
            else:
                self.df.add_column(new_column, ndf[new_column].values, dtype="string")
        elif _dtype == "float64":
            _type = "float"
            binning_type = "continuous"
            if new_column in self.df.get_column_names():
                self.df[new_column] = ndf[new_column].values
                self.df[new_column] = self.df[new_column].astype("float64")
            else:
                self.df.add_column(new_column, ndf[new_column].values, dtype="float64")
        elif _dtype == "int64":
            _type = "int"
            binning_type = "continuous"
            if new_column in self.df.get_column_names():
                self.df[new_column] = ndf[new_column].values
                self.df[new_column] = self.df[new_column].astype("int64")
            else:
                self.df.add_column(new_column, ndf[new_column].values, dtype="int64")
        else:
            _type = "str"
            binning_type = "scatter"
            if new_column in self.df.get_column_names():
                self.df[new_column] = ndf[new_column].values
                self.df[new_column] = self.df[new_column].astype("string")
            else:
                self.df.add_column(new_column, ndf[new_column].values, dtype="string")
        sample_data_rows = self.df.head(50).dropna(column_names=[new_column])
        new_column_dict = {
            "var": new_column,
            # 格式化后的自定义生成公式
            "format_formula": self.format_formula,
            # 原始自定义生成公式
            "formula": self.formula,
            "type": _type,
            "sample_data": sample_data_rows.unique(new_column),
        }
        return new_column_dict, self.df

    def edit_column(self, formula, column_name, column_alias=None, dtype=None):
        arr = self.run(formula)
        sr = pd.Series(arr, name=column_name)
        if dtype:
            try:
                sr = sr[column_name].astype(dtype)
            except Exception:
                raise BaseError("衍生列不支持转换为{}类型".format(dtype))
        else:
            sr = sr.infer_objects()
        # if sr.isna().values.any():
        #     raise BaseError("逻辑生成的变量存在空值, 不可进行当前操作")
        _dtype = sr.dtype
        ndf = vaex.from_dict({column_name: sr.tolist()})
        if _dtype == "object":
            _type = "str"
            binning_type = "scatter"
            if column_name in self.df.get_column_names():
                self.df[column_name] = ndf[column_name].values
                self.df[column_name] = self.df[column_name].astype("string")
            else:
                self.df.add_column(column_name, ndf[column_name].values, dtype="string")
        elif _dtype == "float64":
            _type = "float"
            binning_type = "continuous"
            if column_name in self.df.get_column_names():
                self.df[column_name] = ndf[column_name].values
                self.df[column_name] = self.df[column_name].astype("float64")
            else:
                self.df.add_column(column_name, ndf[column_name].values, dtype="float64")
        elif _dtype == "int64":
            _type = "int"
            binning_type = "continuous"
            if column_name in self.df.get_column_names():
                self.df[column_name] = ndf[column_name].values
                self.df[column_name] = self.df[column_name].astype("int64")
            else:
                self.df.add_column(column_name, ndf[column_name].values, dtype="int64")
        else:
            _type = "str"
            binning_type = "scatter"
            if column_name in self.df.get_column_names():
                self.df[column_name] = ndf[column_name].values
                self.df[column_name] = self.df[column_name].astype("string")
            else:
                self.df.add_column(column_name, ndf[column_name].values, dtype="string")
        sample_data_rows = self.df.head(50).dropna(column_names=[column_name])
        new_column_dict = {
            "var": column_name,
            # 格式化后的自定义生成公式
            "format_formula": self.format_formula,
            # 原始自定义生成公式
            "formula": self.formula,
            "type": _type,
            "sample_data": sample_data_rows.unique(column_name),
        }
        return new_column_dict, self.df

    def replace_custom(self, expression, column_map, context=None):
        """
        :params expression string formula
        :params column_map origin_var: target_var
        """
        result_formula_element = ["="]
        try:
            self.formula = expression
            match = self._formula(expression.replace('\n', '').replace('    ',
                                                                       '').replace(' ', '').replace('"',
                                                                                                    "'")).groupdict()
            expr = match['name']
            self.format_formula = "=" + match['name']
        except (AttributeError, KeyError):
            raise FormulaError
        builder = self.ast_builder(match=match, df=self.df, custom_var_map=self.custom_var_map)
        filters, tokens, stack = self.filters, [], []
        Parenthesis('(').ast(tokens, stack, builder)
        while expr:
            for f in filters:
                try:
                    token = f(expr, context)
                    token.ast(tokens, stack, builder)
                    expr = expr[token.end_match:]
                    if isinstance(token, Column):
                        if token.name not in column_map:
                            raise BaseError("变量映射不存在{}".format(token.name))
                        result_formula_element.append(column_map[token.name])
                    elif isinstance(token, CustomColumn):
                        if token.name not in column_map:
                            raise BaseError("变量映射不存在{}".format("策略衍生_" + token.name))
                        result_formula_element.append(column_map["策略衍生_" + token.name])
                    elif isinstance(token, Function):
                        result_formula_element.append(token.name + "(")
                    elif isinstance(token, String):
                        result_formula_element.append("'{}'".format(token.name))
                    else:
                        result_formula_element.append(token.name)
                    break
                except TokenError:
                    pass
            else:
                raise FormulaError()
        Parenthesis(')').ast(tokens, stack, builder)
        while stack:
            if isinstance(stack[-1], Parenthesis):
                raise FormulaError()
            builder.append(stack.pop())
        if len(builder) != 1:
            raise FormulaError()
        builder.finish()
        return "".join(result_formula_element)


def get_func_list():
    funcs = list(get_functions().keys())
    funcs.remove("ARRAY")
    funcs.remove("ARRAYROW")
    funcs.remove("CEILING.MATH")
    funcs.remove("TRUE")
    funcs.remove("FALSE")
    funcs.remove("NULL")
    funcs.remove("DEGREES")
    funcs.remove("EVEN")
    funcs.remove("PROPER")
    return sorted(funcs)


def _get_formula_contain_vars(df, custom_var_map, formula_columns, dataset_map):
    vars = []
    custom_vars = []
    for i in formula_columns:
        if i.startswith("策略衍生_"):
            custom_vars.append(i)
            parser = Parser(df=df, custom_var_map=custom_var_map)
            parser.ast(dataset_map[i]["formula"])
            _vars, _custom_vars = _get_formula_contain_vars(df, custom_var_map, parser.formula_columns, dataset_map)
            vars.extend(_vars)
            custom_vars.extend(_custom_vars)
        else:
            vars.append(i)
    return vars, custom_vars


# 获取公式预测变量列表和衍生变量列表
def get_formula_contain_vars(df, custom_var_map, formula_columns, dataset_map):
    vars, custom_vars = _get_formula_contain_vars(df, custom_var_map, formula_columns, dataset_map)
    return list(set(vars)), list(set(custom_vars))
