# -*- coding: utf-8 -*-
"""
Parser is the base class for generated parsers and for the bootstrap parser
(the parser that parses Grako grammars).

Parser does memoization at the rule invocation level, and provides the
decorators, context managers, and iterators needed to make generated parsers
simple.

Parser is also in charge of dealing with comments, with the help of
the .buffering module.

Parser.parse() will take the text to parse directly, or an instance of the
.buffeing.Buffer class.
"""
from __future__ import (absolute_import, division, print_function,
                        unicode_literals)

import functools

from .contexts import ParseContext
from .exceptions import (FailedCut, FailedPattern, FailedRef,
                         FailedToken, MissingSemanticFor)


class CheckSemanticsMixin(object):
    def _find_semantic_rule(self, name):
        result = super(CheckSemanticsMixin, self)._find_semantic_rule(name)
        if result is None:
            raise MissingSemanticFor(name)
        return result


class Parser(ParseContext):

    def parse(self,
              text,
              rule_name,
              filename=None,
              semantics=None,
              trace=False,
              whitespace=None,
              **kwargs):
        try:
            self.parseinfo = kwargs.pop('parseinfo', self.parseinfo)
            self._reset(
                text=text,
                filename=filename,
                semantics=semantics,
                trace=trace or self.trace,
                whitespace=whitespace if whitespace is not None else self.whitespace,
                **kwargs
            )
            rule = self._find_rule(rule_name)
            result = rule()
            self.ast[rule_name] = result
            return result
        except FailedCut as e:
            raise e.nested
        finally:
            self._clear_cache()

    @classmethod
    def rule_list(cls):
        import inspect
        methods = inspect.getmembers(cls, predicate=inspect.ismethod)
        result = []
        for m in methods:
            name = m[0]
            if name[0] != '_' or name[-1] != '_':
                continue
            if not name[1:-1].isalnum():
                continue
            result.append(name[1:-1])
        return result

    def result(self):
        return self.ast

    def _token(self, token, node_name=None, force_list=False):
        self._next_token()
        if self._buffer.match(token) is None:
            self._error(token, etype=FailedToken)
        self._trace_match(token, node_name)
        self._add_ast_node(node_name, token, force_list)
        self._add_cst_node(token)
        self._last_node = token
        return token

    def _try_token(self, token, node_name=None, force_list=False):
        p = self._pos
        self._next_token()
        self._last_node = None
        if self._buffer.match(token) is None:
            self._goto(p)
            return None
        self._trace_match(token, node_name)
        self._add_ast_node(node_name, token, force_list)
        self._add_cst_node(token)
        self._last_node = token
        return token

    def _pattern(self, pattern, node_name=None, force_list=False):
        token = self._buffer.matchre(pattern)
        if token is None:
            self._error(pattern, etype=FailedPattern)
        self._trace_match(token, pattern)
        self._add_ast_node(node_name, token, force_list)
        self._add_cst_node(token)
        self._last_node = token
        return token

    def _try_pattern(self, pattern, node_name=None, force_list=False):
        p = self._pos
        token = self._buffer.matchre(pattern)
        self._last_node = None
        if token is None:
            self._goto(p)
            return None
        self._trace_match(token)
        self._add_ast_node(node_name, token, force_list)
        self._add_cst_node(token)
        self._last_node = token
        return token

    def _find_rule(self, name):
        rule = getattr(self, '_' + name + '_', None)
        if isinstance(rule, type(self._find_rule)):
            return rule
        rule = getattr(self, name, None)
        if isinstance(rule, type(self._find_rule)):
            return rule
        self._error(name, etype=FailedRef)

    def _eof(self):
        return self._buffer.atend()

    def _eol(self):
        return self._buffer.ateol()

    def _check_eof(self):
        self._next_token()
        if not self._buffer.atend():
            self._error('Expecting end of text.')


# decorator for rule implementation methods
def graken(*params, **kwparams):
    def decorator(rule):
        @functools.wraps(rule)
        def wrapper(self, *args, **kwargs):
            name = rule.__name__.strip('_')
            return self._call(rule, name, *params, **kwparams)
        return wrapper
    return decorator
