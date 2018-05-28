#!/usr/bin/env python
# -*- coding: utf-8 -*-

from functools import update_wrapper, wraps


def disable(func):
    '''
    Disable a decorator by re-assigning the decorator's name
    to this function. For example, to turn off memoization:

    >>> memo = disable

    '''
    return func


def decorator(wrapped):
    '''
    Decorate a decorator so that it inherits the docstrings
    and stuff from the function it's decorating.
    '''

    def wrapper_decorator(wrapper):
        return update_wrapper(wrapper, wrapped)

    return wrapper_decorator


class Counter:
    def __init__(self):
        self.counter = 0

    def inc(self):
        self.counter += 1

    def dec(self):
        self.counter -= 1

    def __str__(self):
        return '{:d}'.format(self.counter)


def countcalls(func):
    '''Decorator that counts calls made to the function decorated.'''

    @wraps(func)
    def wrapper(*args):
        wrapper.calls.inc()
        return func(*args)

    wrapper.calls = Counter()
    return wrapper


def memo(func):
    '''
    Memoize a function so that it caches all return values for
    faster future lookups.
    '''

    @wraps(func)
    def wrapper(*args):
        if args not in wrapper.cache:
            wrapper.cache[args] = func(*args)
        return wrapper.cache[args]

    wrapper.cache = {}
    return wrapper


def n_ary(func):
    '''
    Given binary function f(x, y), return an n_ary function such
    that f(x, y, z) = f(x, f(y,z)), etc. Also allow f(x) = x.
    '''

    @wraps(func)
    def wrapper(*args):
        *x, z = args
        while (len(x) > 0):
            *x, y = x
            z = func(y, z)
        return z

    return wrapper


def trace(ident):
    '''Trace calls made to function decorated.

    @trace("____")
    def fib(n):
        ....

    >>> fib(3)
     --> fib(3)
    ____ --> fib(2)
    ________ --> fib(1)
    ________ <-- fib(1) == 1
    ________ --> fib(0)
    ________ <-- fib(0) == 1
    ____ <-- fib(2) == 2
    ____ --> fib(1)
    ____ <-- fib(1) == 1
     <-- fib(3) == 3

    '''

    def wrapper_trace(func):
        @wraps(func)
        def wrapper(*args):
            print('{:s} --> {:s}({!s})'.format(ident * wrapper.level.counter,
                                               func.__name__, *args))
            wrapper.level.inc()
            result = func(*args)
            wrapper.level.dec()
            print('{:s} <-- {:s}({!s}) == {!s}'.format(
                ident * wrapper.level.counter, func.__name__, *args, result))
            return result

        wrapper.level = Counter()
        return wrapper

    return wrapper_trace
    return


@memo
@countcalls
@n_ary
def foo(a, b):
    return a + b


@countcalls
@memo
@n_ary
def bar(a, b):
    return a * b


@countcalls
@trace("####")
@memo
def fib(n):
    """Some doc"""
    return 1 if n <= 1 else fib(n - 1) + fib(n - 2)


def main():
    print(foo(4, 3))
    print(foo(4, 3, 2))
    print(foo(4, 3))
    print("foo was called", foo.calls, "times")

    print(bar(4, 3))
    print(bar(4, 3, 2))
    print(bar(4, 3, 2, 1))
    print("bar was called", bar.calls, "times")

    print(fib.__doc__)
    fib(3)
    print(fib.calls, 'calls made')


if __name__ == '__main__':
    main()
