"""The recipe registry (design section 2.3). Every module in this folder that defines RECIPES (a list or dict of
core.recipe.Recipe) is collected on first use, so no package edits a shared list; one module per family.

    from eidoblend.terrain import recipes
    recipes()                          # {name: title}, every recipe
    recipes.get('alpine_valley')       # the Recipe; an unknown name raises naming the nearest
    recipes.resolve(x)                 # a name, a Recipe, a recipe dict or a list of stages -> a Recipe
    recipes.get_op('impact_crater')    # the function behind a stage op
    recipes.failed()                   # {module: error} for recipe modules that did not import

The module itself is callable (recipes() lists them), because the package's public name `recipes` is both this
folder and the listing function of the design's API.

Ops. A stage's op name maps to a function, found in this order: core.recipe's register_op table, then the OPS dict
of every recipe module here, then the OPS dict of every module in terrain/solvers/ (imported on the first miss).
The wave-1 solvers' convention is op(fields, level, params, seed), writing the level's Fields in place.

Recipe hooks a module may set on a Recipe object (attributes, not data, so they come from the registered recipe
when a dict of the same name is passed back):
    defaults_for(values) -> dict   defaults that depend on the knob values (real_place: the DEM's extent)
    prepare(values, plan)          called once before the levels run (load data, build a plan shared by levels)
"""
import difflib
import importlib
import pkgutil
import sys
import types

_RECIPES = None
_FAILED = {}
_OPS = None
_HOOKS = ('defaults_for', 'prepare')


def _core_recipe():
    return importlib.import_module('..core.recipe', __name__)


def _load():
    global _RECIPES
    if _RECIPES is not None:
        return _RECIPES
    found, where = {}, {}
    for m in sorted(pkgutil.iter_modules(__path__), key=lambda m: m.name):
        if m.name.startswith('_'):
            continue
        try:
            mod = importlib.import_module(f'{__name__}.{m.name}')
        except Exception as e:                       # one family's broken module must not hide every recipe
            _FAILED[m.name] = f'{type(e).__name__}: {e}'
            print(f'[terrain.recipes] recipe module {m.name!r} did not import: {_FAILED[m.name]}', flush=True)
            continue
        rs = getattr(mod, 'RECIPES', None)
        if rs is None:
            continue
        for r in (rs.values() if isinstance(rs, dict) else rs):
            if r.name in found:
                raise ValueError(f'recipe {r.name!r} is defined in both {where[r.name]} and {m.name}')
            found[r.name] = r
            where[r.name] = m.name
    _RECIPES = dict(sorted(found.items()))
    return _RECIPES


def names():
    """Every recipe's name, sorted."""
    return list(_load())


def listing():
    """{name: title} of every recipe."""
    return {k: r.title for k, r in _load().items()}


def failed():
    """{module: error} of the recipe modules that did not import."""
    _load()
    return dict(_FAILED)


def _unknown(name, options, what):
    near = difflib.get_close_matches(str(name), list(options), n=3, cutoff=0.4)
    msg = f'no {what} {name!r}'
    msg += f'; nearest: {", ".join(near)}' if near else f'; valid: {", ".join(sorted(options)) or "(none)"}'
    if _FAILED and what == 'recipe':
        msg += f' (recipe modules that did not import: {", ".join(f"{k} ({v})" for k, v in _FAILED.items())})'
    return msg


def get(name):
    """The registered Recipe called `name`; an unknown name raises KeyError naming the nearest."""
    reg = _load()
    if name not in reg:
        raise KeyError(_unknown(name, reg, 'recipe'))
    return reg[name]


def resolve(recipe):
    """A Recipe from a registered name, a Recipe, a recipe dict (to_dict's form; knob apply functions and hooks
    come from the registered recipe of the same name) or a list of stages (Stage objects or stage dicts)."""
    R = _core_recipe()
    if isinstance(recipe, R.Recipe):
        return recipe
    if isinstance(recipe, str):
        return get(recipe)
    if isinstance(recipe, dict):
        base = _load().get(recipe.get('name'))
        out = R.Recipe.from_dict(recipe, base=base)
        if base is not None:
            for h in _HOOKS:
                if getattr(base, h, None) is not None:
                    setattr(out, h, getattr(base, h))
        return out
    if isinstance(recipe, (list, tuple)):
        return R.Recipe.from_stages(list(recipe))
    raise TypeError(f'recipe must be a name, a Recipe, a recipe dict or a list of stages, got {type(recipe).__name__}')


def _collect_ops():
    global _OPS
    if _OPS is not None:
        return _OPS
    ops = {}

    def take(mod, label):
        for k, f in (getattr(mod, 'OPS', None) or {}).items():
            if k in ops and ops[k][0] is not f:
                raise ValueError(f'op {k!r} is defined by both {ops[k][1]} and {label}')
            ops.setdefault(k, (f, label))
    _load()
    for m in pkgutil.iter_modules(__path__):
        if not m.name.startswith('_') and f'{__name__}.{m.name}' in sys.modules:
            take(sys.modules[f'{__name__}.{m.name}'], f'recipes.{m.name}')
    try:
        solvers = importlib.import_module('..solvers', __name__)
        for m in sorted(pkgutil.iter_modules(solvers.__path__), key=lambda m: m.name):
            if m.name.startswith('_'):
                continue
            try:
                take(importlib.import_module(f'{solvers.__name__}.{m.name}'), f'solvers.{m.name}')
            except Exception as e:
                _FAILED['solvers.' + m.name] = f'{type(e).__name__}: {e}'
    except ImportError:
        pass
    _OPS = ops
    return ops


def get_op(name):
    """The function behind stage op `name` (see the module doc for where it is looked up); KeyError naming the
    nearest when there is none."""
    R = _core_recipe()
    if name in R.OPS:
        return R.OPS[name]
    ops = _collect_ops()
    if name in ops:
        return ops[name][0]
    raise KeyError(_unknown(name, set(R.OPS) | set(ops), 'op'))


def has_op(name):
    try:
        get_op(name)
        return True
    except KeyError:
        return False


def op_names():
    return sorted(set(_core_recipe().OPS) | set(_collect_ops()))


def reload():
    """Forget what was collected (a new recipe module dropped in during a session)."""
    global _RECIPES, _OPS
    _RECIPES, _OPS = None, None
    _FAILED.clear()


class _Registry(types.ModuleType):
    """This module's class: calling it lists the recipes."""

    def __call__(self):
        return listing()


sys.modules[__name__].__class__ = _Registry
