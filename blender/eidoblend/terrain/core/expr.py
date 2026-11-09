"""The mask expression language of stage `where` and of the surfacing layers' weights (design sections 2.3, 7).

    e = parse('smoothstep(32, 45, slope) + 0.5*wear - 2*deposit')
    e.names()                         # {'slope', 'wear', 'deposit'}
    w = e.eval({'slope': s, 'wear': w, 'deposit': d})      # numpy, broadcasting numbers; or eval(callable(name))
    str(e)                            # the canonical text; e.tree is the AST for other back ends (shader nodes)

Grammar: numbers, names (masks or fields), + - * /, unary minus, parentheses, and the functions
min(a, b, ...), max(a, b, ...), smoothstep(edge0, edge1, x), clamp(x, lo, hi), abs(x). smoothstep is GLSL's
(t = clamp((x - e0) / (e1 - e0), 0, 1); t^2 (3 - 2 t)), and with e0 > e1 it falls instead of rising.
Nothing else is evaluated: there is no Python eval. A mistake names the token and its position.

AST nodes (tuples): ('num', value) ('name', name) ('neg', x) ('bin', op, a, b) ('call', function, [args]).
"""

from __future__ import annotations

import difflib
import re

import numpy as np

FUNCTIONS = {'min': (2, None), 'max': (2, None), 'smoothstep': (3, 3), 'clamp': (3, 3), 'abs': (1, 1)}
_TOKEN = re.compile(r'\s*(?:(\d+\.\d*(?:[eE][+-]?\d+)?|\.\d+(?:[eE][+-]?\d+)?|\d+(?:[eE][+-]?\d+)?)|'
                    r'([A-Za-z_]\w*)|(.))')


class ExprError(ValueError):
    pass


def _tokens(text):
    out = []
    pos = 0
    while pos < len(text):
        m = _TOKEN.match(text, pos)
        if not m or m.end() == pos:
            break
        num, name, ch = m.groups()
        start = m.start(m.lastindex) if m.lastindex else pos
        if num is not None:
            out.append(('num', float(num), start))
        elif name is not None:
            out.append(('name', name, start))
        elif ch is not None:
            if ch not in '+-*/(),':
                raise ExprError(f'{text!r}: unexpected {ch!r} at {start} (allowed: numbers, names, + - * / ( ) , '
                                f'and {", ".join(FUNCTIONS)})')
            out.append(('op', ch, start))
        pos = m.end()
    out.append(('end', None, len(text)))
    return out


class _Parser:
    def __init__(self, text):
        self.text = text
        self.toks = _tokens(text)
        self.i = 0

    def peek(self):
        return self.toks[self.i]

    def take(self, kind=None, val=None):
        t = self.toks[self.i]
        if (kind and t[0] != kind) or (val is not None and t[1] != val):
            want = val if val is not None else kind
            got = 'the end' if t[0] == 'end' else repr(t[1])
            raise ExprError(f'{self.text!r}: expected {want!r} at {t[2]}, found {got}')
        self.i += 1
        return t

    def expr(self):
        node = self.term()
        while self.peek()[0] == 'op' and self.peek()[1] in '+-':
            op = self.take()[1]
            node = ('bin', op, node, self.term())
        return node

    def term(self):
        node = self.unary()
        while self.peek()[0] == 'op' and self.peek()[1] in '*/':
            op = self.take()[1]
            node = ('bin', op, node, self.unary())
        return node

    def unary(self):
        if self.peek()[0] == 'op' and self.peek()[1] == '-':
            self.take()
            return ('neg', self.unary())
        if self.peek()[0] == 'op' and self.peek()[1] == '+':
            self.take()
            return self.unary()
        return self.atom()

    def atom(self):
        t = self.peek()
        if t[0] == 'num':
            self.take()
            return ('num', t[1])
        if t[0] == 'name':
            self.take()
            if self.peek()[0] == 'op' and self.peek()[1] == '(':
                if t[1] not in FUNCTIONS:
                    near = difflib.get_close_matches(t[1], list(FUNCTIONS), n=2)
                    raise ExprError(f'{self.text!r}: unknown function {t[1]!r} at {t[2]}'
                                    + (f' (did you mean {near}?)' if near else f' (functions: {list(FUNCTIONS)})'))
                self.take('op', '(')
                args = [self.expr()]
                while self.peek()[0] == 'op' and self.peek()[1] == ',':
                    self.take()
                    args.append(self.expr())
                self.take('op', ')')
                lo, hi = FUNCTIONS[t[1]]
                if len(args) < lo or (hi is not None and len(args) > hi):
                    n = f'{lo}' if lo == hi else f'at least {lo}'
                    raise ExprError(f'{self.text!r}: {t[1]}() takes {n} arguments, got {len(args)}')
                return ('call', t[1], args)
            return ('name', t[1])
        if t[0] == 'op' and t[1] == '(':
            self.take()
            node = self.expr()
            self.take('op', ')')
            return node
        got = 'the end' if t[0] == 'end' else repr(t[1])
        raise ExprError(f'{self.text!r}: expected a number, a name or ( at {t[2]}, found {got}')


def _smoothstep(e0, e1, x):
    t = np.clip((x - e0) / (e1 - e0), 0.0, 1.0)
    return t * t * (3.0 - 2.0 * t)


def _eval(node, get):
    kind = node[0]
    if kind == 'num':
        return node[1]
    if kind == 'name':
        return get(node[1])
    if kind == 'neg':
        return -_eval(node[1], get)
    if kind == 'bin':
        a, b = _eval(node[2], get), _eval(node[3], get)
        return {'+': lambda: a + b, '-': lambda: a - b, '*': lambda: a * b, '/': lambda: a / b}[node[1]]()
    args = [_eval(a, get) for a in node[2]]
    f = node[1]
    if f == 'min':
        out = args[0]
        for a in args[1:]:
            out = np.minimum(out, a)
        return out
    if f == 'max':
        out = args[0]
        for a in args[1:]:
            out = np.maximum(out, a)
        return out
    if f == 'smoothstep':
        return _smoothstep(*args)
    if f == 'clamp':
        return np.clip(args[0], args[1], args[2])
    return np.abs(args[0])


def _text(node):
    kind = node[0]
    if kind == 'num':
        return repr(node[1]) if not float(node[1]).is_integer() else str(int(node[1]))
    if kind == 'name':
        return node[1]
    if kind == 'neg':
        return '-' + _wrap(node[1], 3)
    if kind == 'bin':
        prec = 1 if node[1] in '+-' else 2
        right = _wrap(node[3], prec + (1 if node[1] in '-/' else 0))
        return f'{_wrap(node[2], prec)} {node[1]} {right}'
    return f"{node[1]}({', '.join(_text(a) for a in node[2])})"


def _prec(node):
    if node[0] == 'bin':
        return 1 if node[1] in '+-' else 2
    if node[0] == 'neg':
        return 3
    return 4


def _wrap(node, need):
    t = _text(node)
    return f'({t})' if _prec(node) < need else t


class Expr:
    """A parsed mask expression: .tree (the AST), .names(), .eval(env), str()."""

    def __init__(self, text):
        self.source = text
        p = _Parser(text)
        self.tree = p.expr()
        p.take('end')

    def names(self):
        out = set()

        def walk(n):
            if n[0] == 'name':
                out.add(n[1])
            elif n[0] == 'neg':
                walk(n[1])
            elif n[0] == 'bin':
                walk(n[2])
                walk(n[3])
            elif n[0] == 'call':
                for a in n[2]:
                    walk(a)
        walk(self.tree)
        return out

    def eval(self, env):
        """Evaluate over `env`: a mapping name -> array (or number), or a callable(name) -> array. An unknown name
        names the nearest available ones."""
        if callable(env) and not hasattr(env, 'keys'):
            get = env
        else:
            def get(name):
                if name in env:
                    return np.asarray(env[name], dtype=np.float64) if not np.isscalar(env[name]) else env[name]
                near = difflib.get_close_matches(name, list(env), n=3)
                raise KeyError(f'{self.source!r}: no mask or field {name!r}'
                               + (f' (did you mean {near}?)' if near else f' (have: {sorted(env)})'))
        return _eval(self.tree, get)

    def __str__(self):
        return _text(self.tree)

    def __repr__(self):
        return f'Expr({str(self)!r})'


def parse(text):
    """Parse a mask expression (an Expr is returned as it is)."""
    if isinstance(text, Expr):
        return text
    if not isinstance(text, str) or not text.strip():
        raise ExprError(f'a mask expression is a non-empty string, got {text!r}')
    return Expr(text)
