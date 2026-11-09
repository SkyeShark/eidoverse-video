"""Stages and recipes (design section 2.3): a recipe is data, an ordered list of stages plus a few named knobs.

    from eidoblend.terrain.core.recipe import Stage, Recipe, Knob

    def spacing_to_D(p):                                # a knob's apply: writes DERIVED stage parameters
        f = p.stage('fluvial')
        f['D'] = f['K'] * (p['valley_spacing_m'] / 6.5) ** 2

    RECIPES = [Recipe(
        'fluvial_range', 'A mountain range carved by rivers',
        references=['san_gabriel'],
        defaults={'size': 12000.0, 'resolution': 1024, 'context': 4, 'hero_cell': 0.5, 'palette': 'alpine'},
        knobs={'relief_m': Knob(2000.0, 'm', (200.0, 6000.0), 'p99.5 height above base on the coarsest level'),
               'valley_spacing_m': Knob(400.0, 'm', (60.0, 3000.0), 'the smallest valleys\\' spacing',
                                        apply=spacing_to_D)},
        stages=[Stage('uplift', {'shape': {'kind': 'ridge'}}, levels='all'),
                Stage('fluvial', {'K': 1.5e-5, 'relief_m': '$relief_m'}, levels='all'),
                Stage('breakup', {...}, levels='hero', where='smoothstep(30, 45, slope)')])]

    values, stages = recipe.resolve({'relief_m': 2800})   # knob values checked against unit and range; '$knob'
                                                           # strings replaced; each knob's apply run in order
    d = recipe.to_dict()                                   # JSON: print it, copy it, change a stage ...
    r2 = Recipe.from_dict(d, base=recipe)                  # ... and pass it back (knob apply functions come from
                                                           # the named base recipe; a dict cannot carry code)
    print(recipe.describe())

Stage(op, params, levels='all', where=None, name=None)
    levels  'all' | 'first' | 'last' | 'context' | 'main' | 'hero' | 'cell>=30' | 'cell<=2' | 'resolves:<metres>'
            | a level index | a list of these (core/levels.select_levels)
    where   a mask expression limiting the stage (core/expr): combined with * + - min max smoothstep(a, b, mask)
    name    optional, to tell two stages of one op apart (Params.stage('talus_hero'))

Knob(default, unit, range, doc, apply)
    unit    'm', 'yr', 'kyr', 'Myr', 'deg', 'm/yr', 'm2/yr', '' (a number without unit), 'choice', 'bool', 'list'
    range   (lo, hi) for numbers, the allowed values for a 'choice', None for no check

An op registry lets solver modules register the functions behind op names without a shared list
(register_op / get_op / op_names); the level runner decides how it calls them.
"""

from __future__ import annotations

import copy
import difflib
import json

import numpy as np

from . import expr as _expr
from . import levels as _levels

UNITS = ('m', 'yr', 'kyr', 'Myr', 'deg', 'm/yr', 'm2/yr', '', 'choice', 'bool', 'list', 'name')


def _nearest(name, names):
    near = difflib.get_close_matches(name, list(names), n=3, cutoff=0.5)
    return f'; did you mean {", ".join(near)}?' if near else f'; valid: {", ".join(sorted(names)) or "(none)"}'


def _jsonable(v, where='value'):
    """v as plain JSON types (numpy scalars and arrays converted); raises TypeError naming where it failed."""
    if isinstance(v, dict):
        return {str(k): _jsonable(x, f'{where}.{k}') for k, x in v.items()}
    if isinstance(v, (list, tuple)):
        return [_jsonable(x, f'{where}[{i}]') for i, x in enumerate(v)]
    if isinstance(v, np.ndarray):
        return v.tolist()
    if isinstance(v, np.generic):
        return v.item()
    if v is None or isinstance(v, (bool, int, float, str)):
        return v
    raise TypeError(f'{where}: {type(v).__name__} is not JSON data (recipes are data: use numbers, strings, lists, '
                    f'dicts, or a file path for an array)')


class Stage:
    """One step of a recipe: an op with parameters (metres, years, degrees), the levels it runs on, an optional
    region."""

    def __init__(self, op, params=None, levels='all', where=None, name=None):
        if not isinstance(op, str) or not op:
            raise ValueError(f'a stage op is a name, got {op!r}')
        self.op = op
        self.params = dict(params or {})
        self.levels = levels
        _levels.parse_levels_spec(levels)                        # fail at construction, not mid-run
        self.where = where
        self.where_expr = _expr.parse(where) if where is not None else None
        self.name = name

    @property
    def label(self):
        return self.name or self.op

    def select(self, plan, warn=None):
        """The indices of the levels of `plan` this stage runs on."""
        return _levels.select_levels(self.levels, plan, warn)

    def to_dict(self):
        d = {'op': self.op, 'params': _jsonable(self.params, f'stage {self.label}.params'),
             'levels': _jsonable(self.levels), 'where': self.where}
        if self.name:
            d['name'] = self.name
        return d

    @classmethod
    def from_dict(cls, d):
        if isinstance(d, Stage):
            return d
        extra = set(d) - {'op', 'params', 'levels', 'where', 'name'}
        if extra:
            raise KeyError(f'stage keys {sorted(extra)} unknown' + _nearest(sorted(extra)[0],
                                                                           ['op', 'params', 'levels', 'where',
                                                                            'name']))
        return cls(d['op'], d.get('params'), d.get('levels', 'all'), d.get('where'), d.get('name'))

    def copy(self):
        return Stage(self.op, copy.deepcopy(self.params), copy.deepcopy(self.levels), self.where, self.name)

    def __repr__(self):
        return (f'Stage({self.op!r}' + (f', name={self.name!r}' if self.name else '') + f', levels={self.levels!r}'
                + (f', where={self.where!r}' if self.where else '') + f', params={self.params})')


class Knob:
    """A named recipe input in its own unit; apply(params) writes the stage parameters it derives."""

    def __init__(self, default, unit='', range=None, doc='', apply=None):
        if unit not in UNITS:
            raise ValueError(f'knob unit {unit!r} is not one of {UNITS}')
        self.default = default
        self.unit = unit
        self.range = range
        self.doc = doc
        self.apply = apply

    def check(self, name, value):
        """The value, checked against the unit and range; raises ValueError naming the knob."""
        if self.unit == 'choice':
            if self.range is not None and value not in self.range:
                raise ValueError(f'knob {name}: {value!r} is not one of {list(self.range)}')
            return value
        if self.unit == 'bool':
            return bool(value)
        if self.unit in ('list', 'name'):
            return value
        if isinstance(value, bool) or not isinstance(value, (int, float, np.integer, np.floating)):
            raise ValueError(f'knob {name}: expected a number in {self.unit or "(no unit)"}, got {value!r}')
        v = float(value)
        if not np.isfinite(v):
            raise ValueError(f'knob {name}: {value!r} is not finite')
        if self.range is not None:
            lo, hi = self.range
            if (lo is not None and v < lo) or (hi is not None and v > hi):
                raise ValueError(f'knob {name} = {v:g} {self.unit} is outside its range [{lo}, {hi}] {self.unit}')
        return v

    def to_dict(self):
        return {'default': _jsonable(self.default), 'unit': self.unit, 'range': _jsonable(self.range),
                'doc': self.doc, 'derives': self.apply is not None}


class Params(dict):
    """What a knob's apply() receives: the resolved knob values by name, and the stages' parameter dicts to write
    derived values into (p.stage(op_or_name) for the first match, p.stages(op_or_name) for all)."""

    def __init__(self, values, stages, recipe=None):
        super().__init__(values)
        self._stages = stages
        self.recipe = recipe

    def stages(self, sel):
        hit = [s.params for s in self._stages if s.name == sel or s.op == sel]
        return hit

    def stage(self, sel):
        hit = self.stages(sel)
        if not hit:
            raise KeyError(f'no stage named or of op {sel!r}' + _nearest(sel, {s.label for s in self._stages}))
        return hit[0]


def _substitute(v, values, where):
    if isinstance(v, str) and v.startswith('$'):
        k = v[1:]
        if k not in values:
            raise KeyError(f'{where}: {v!r} names no knob' + _nearest(k, values))
        return values[k]
    if isinstance(v, dict):
        return {kk: _substitute(x, values, f'{where}.{kk}') for kk, x in v.items()}
    if isinstance(v, list):
        return [_substitute(x, values, f'{where}[{i}]') for i, x in enumerate(v)]
    return v


class Recipe:
    """Recipe(name, title, references, defaults, knobs, stages): see the module doc."""

    def __init__(self, name, title, references=(), defaults=None, knobs=None, stages=(), doc=''):
        self.name = name
        self.title = title
        self.references = list(references)
        self.defaults = dict(defaults or {})
        self.knobs = dict(knobs or {})
        for k, v in self.knobs.items():
            if not isinstance(v, Knob):
                raise TypeError(f'recipe {name}: knob {k} is a {type(v).__name__}, not a Knob')
        self.stages = [Stage.from_dict(s) if isinstance(s, dict) else s for s in stages]
        self.doc = doc

    def knob_values(self, params=None):
        """Every knob's value (defaults overridden by `params`), checked. An unknown knob names the nearest."""
        params = dict(params or {})
        for k in params:
            if k not in self.knobs:
                raise KeyError(f'recipe {self.name!r} has no knob {k!r}' + _nearest(k, self.knobs))
        return {k: kn.check(k, params.get(k, kn.default)) for k, kn in self.knobs.items()}

    def resolve(self, params=None):
        """(knob values, stages): deep copies of the stages with '$knob' references replaced by the values, then
        each knob's apply() run in declaration order to write its derived parameters."""
        values = self.knob_values(params)
        stages = [s.copy() for s in self.stages]
        for s in stages:
            s.params = _substitute(s.params, values, f'stage {s.label}')
        p = Params(values, stages, self)
        for k, kn in self.knobs.items():
            if kn.apply is not None:
                kn.apply(p)
        return values, stages

    def to_dict(self):
        d = {'name': self.name, 'title': self.title, 'references': list(self.references),
             'defaults': _jsonable(self.defaults, f'recipe {self.name}.defaults'),
             'knobs': {k: v.to_dict() for k, v in self.knobs.items()},
             'stages': [s.to_dict() for s in self.stages]}
        if self.doc:
            d['doc'] = self.doc
        json.dumps(d)                                             # it is JSON, or this raises
        return d

    @classmethod
    def from_dict(cls, d, base=None):
        """A recipe from its dict. Knob apply functions are code, which a dict cannot carry: they come from `base`
        (the registered recipe of the same name, passed by the registry) for the knobs it shares."""
        if isinstance(d, Recipe):
            return d
        knobs = {}
        for k, kd in (d.get('knobs') or {}).items():
            src = base.knobs.get(k) if base is not None else None
            knobs[k] = Knob(kd.get('default'), kd.get('unit', ''), kd.get('range'), kd.get('doc', ''),
                            src.apply if src is not None else None)
        return cls(d.get('name', base.name if base else 'custom'), d.get('title', base.title if base else ''),
                   d.get('references', []), d.get('defaults', {}), knobs,
                   [Stage.from_dict(s) for s in d.get('stages', [])], d.get('doc', ''))

    @classmethod
    def from_stages(cls, stages, name='custom', title='a list of stages', defaults=None):
        return cls(name, title, (), defaults, {}, [Stage.from_dict(s) if isinstance(s, dict) else s
                                                   for s in stages])

    def describe(self):
        lines = [f'{self.name}: {self.title}']
        if self.doc:
            lines.append('  ' + self.doc)
        if self.references:
            lines.append('  judged against: ' + ', '.join(self.references))
        if self.defaults:
            lines.append('  defaults: ' + ', '.join(f'{k}={v}' for k, v in self.defaults.items()))
        if self.knobs:
            lines.append('  knobs:')
            for k, kn in self.knobs.items():
                rng = f' in {list(kn.range)}' if kn.range is not None else ''
                lines.append(f"    {k} = {kn.default!r} {kn.unit}{rng}{' (derives stage parameters)' if kn.apply else ''}"
                             + (f': {kn.doc}' if kn.doc else ''))
        lines.append('  stages:')
        for i, s in enumerate(self.stages):
            lines.append(f'    {i}. {s.label} on {s.levels}' + (f' where {s.where}' if s.where else '')
                         + (f': {json.dumps(_jsonable(s.params))}' if s.params else ''))
        return '\n'.join(lines)

    def __repr__(self):
        return f'Recipe({self.name!r}, {len(self.stages)} stages, knobs {list(self.knobs)})'


# --------------------------------------------------------------------------------------------- op registry ---

OPS = {}


def register_op(name, fn=None):
    """Register the function behind a stage op (usable as a decorator: @register_op('fluvial')). The level
    runner (run.py) owns the calling convention; this only maps names to functions without a shared list."""
    def deco(f):
        OPS[name] = f
        return f
    return deco(fn) if fn is not None else deco


def get_op(name):
    if name in OPS:
        return OPS[name]
    raise KeyError(f'no op {name!r} is registered' + _nearest(name, OPS) +
                   ' (ops register when their solver module is imported)')


def op_names():
    return sorted(OPS)
