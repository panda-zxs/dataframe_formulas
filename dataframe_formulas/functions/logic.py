# -*- coding: utf-8 -*-

import functools

import numpy as np

from . import (Error, flatten, get_error, raise_errors, value_return,
               wrap_func, wrap_ufunc)

FUNCTIONS = {}


def xif(condition, x=1, y=0):
    return x if condition else y


def solve_cycle(*args):
    return not args[0]


def xifs(*cond_vals):
    if len(cond_vals) % 2:
        cond_vals += 0,
    for b, v in zip(cond_vals[::2], cond_vals[1::2]):
        err = get_error(b)
        if err:
            return err
        if isinstance(b, str):
            raise ValueError
        if b:
            return v
    return Error.errors['#N/A']


def xand(logical, *logicals, func=np.logical_and.reduce):
    check, arr = lambda x: not raise_errors(x) and not isinstance(x, str), []
    for a in (logical, ) + logicals:
        v = list(flatten(a, check=check))
        arr.extend(v)
        if not v and not isinstance(a, np.ndarray):
            return Error.errors['#VALUE!']
    return func(arr) if arr else Error.errors['#VALUE!']


def _true():
    return True


def _false():
    return False


def _null():
    return None


def _nan():
    return np.NAN


FUNCTIONS['AND'] = {'function': wrap_ufunc(xand)}
FUNCTIONS['OR'] = {'function': wrap_ufunc(functools.partial(xand, func=np.logical_or.reduce))}
FUNCTIONS['NOT'] = {'function': wrap_ufunc(np.logical_not, input_parser=lambda *a: a, return_func=value_return)}

FUNCTIONS['TRUE'] = wrap_func(_true)
FUNCTIONS['FALSE'] = wrap_func(_false)
FUNCTIONS['NULL'] = wrap_func(_null)
FUNCTIONS['NAN'] = wrap_func(_nan)
FUNCTIONS['IF'] = {
    'function':
    wrap_ufunc(xif, input_parser=lambda *a: a, return_func=value_return, check_error=lambda cond, *a: get_error(cond)),
    'solve_cycle':
    solve_cycle
}
