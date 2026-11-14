"""A made terrain as the judge's measures read it, from wherever it was saved (numpy; no bpy, no GPU):

    from surfacing_judge import terrain_data as TD
    st = TD.load('<cache key or its first characters>')         # an entry of the terrain cache
    st = TD.load('<dir>/canyon_overlook.npz')                   # a Terrain.save() snapshot (its .json beside it)
    st = TD.load('<dir>/c19_b_levels.npz', recipe='canyon')     # a generator's levels file (L<i>_<field>, L<i>_window)
    st.levels[i]          dict(x0, y0, side, cell, n, role)
    st.fields[i]['h']     the level's fields
    st.masks(i)           the level's masks (masks.py's): read from the file, or computed with the recipe's own mask
                          parameters for a levels file and kept in out/surfacing_judge/cache/ (keyed by the file,
                          masks.py and the parameters), since masks.compute_stack takes a minute or more per stack
    st.main               the main level's index
    st.constants(pal)     the terrain constants a palette's expressions read (base elevation, snowline, treeline)
    st.height_at(x, y)    bilinear height from the finest level holding each point (levels up to the last loaded)

Levels beyond the main one (the hero levels) are loaded only with heroes=True.
"""
from __future__ import annotations

import hashlib
import json
import os
import re

import numpy as np

from . import BLENDER_DIR, OUT, terrain_cache_root  # noqa: F401  (BLENDER_DIR is on sys.path through the package)

MASK_CACHE = os.path.join(OUT, 'cache')


def _eido():
    from eidoblend.terrain import masks as M
    from eidoblend.terrain import recipes as R
    from eidoblend.terrain.build import palettes as P
    return M, R, P


class Stack:
    """The levels of one saved terrain, coarsest first."""

    def __init__(self, source, recipe, knobs, levels, fields, masks, info):
        self.source = source
        self.recipe = recipe                       # the recipe's name (None when the file does not say)
        self.knobs = dict(knobs or {})
        self.levels = levels
        self.fields = fields
        self._masks = masks                        # per level: a dict, or None (not in the file)
        self.info = dict(info or {})
        roles = [lv['role'] for lv in levels]
        self.main = roles.index('main') if 'main' in roles else \
            max(i for i, r in enumerate(roles) if r != 'hero')

    # ------------------------------------------------------------------------------------ the recipe's settings
    def _defaults(self):
        M, R, _P = _eido()
        if not self.recipe:
            return {}
        rec = R.get(self.recipe)
        dfl = dict(rec.defaults)
        if getattr(rec, 'defaults_for', None) is not None:
            try:
                dfl.update(rec.defaults_for(dict(self.knobs)))
            except Exception:                      # noqa: BLE001  (a hook that wants knobs this file did not keep)
                pass
        return dfl

    @property
    def base_elevation_m(self):
        v = self.info.get('base_elevation_m')
        if v is None:
            v = self._defaults().get('base_elevation_m', 0.0)
        return float(v or 0.0)

    def mask_params(self):
        """The recipe's mask parameters as make_terrain passes them (its defaults' mask_params, the sea level, the
        base elevation): a dict of masks.MaskParams fields."""
        M, _R, _P = _eido()
        dfl = self._defaults()
        mp = dict(dfl.get('mask_params') or {})
        mp['base_elevation_m'] = self.base_elevation_m
        sea = self.info.get('sea_level')
        mp['sea_level'] = sea if sea is not None else dfl.get('sea_level')
        allowed = set(M.MaskParams.__dataclass_fields__)
        return {k: v for k, v in mp.items() if k in allowed}

    def constants(self, pal):
        """The terrain constants for a palette's expressions: the palette's defaults under the terrain's own base
        elevation, snowline and treeline (surfacing.terrain_constants' rule: knobs, then the recipe's mask
        parameters, then a real place's)."""
        _M, _R, P = _eido()
        c = dict(pal['constants'])
        c['base_elevation_m'] = self.base_elevation_m
        mp = self.mask_params()
        dem = self.knobs.get('dem')
        if isinstance(dem, str) and dem in P.PLACES:
            mp.update(P.PLACES[dem].get('mask_params') or {})
        for k in ('snowline_m', 'treeline_m'):
            if self.knobs.get(k) is not None:
                mp[k] = self.knobs[k]
            if mp.get(k) is not None:
                c[k] = float(mp[k])
        return c

    # ---------------------------------------------------------------------------------------------- masks
    def _mask_cache_file(self):
        M, _R, _P = _eido()
        h = hashlib.sha1()
        st = os.stat(self.source)
        h.update(f'{os.path.basename(self.source)}|{st.st_size}|{int(st.st_mtime)}|{self.main}'.encode())
        with open(M.__file__, 'rb') as f:
            h.update(f.read())
        h.update(json.dumps(self.mask_params(), sort_keys=True, default=str).encode())
        return os.path.join(MASK_CACHE, f'masks_{h.hexdigest()[:16]}.npz')

    def _compute_masks(self, log=print):
        M, _R, _P = _eido()
        path = self._mask_cache_file()
        n = self.main + 1
        if os.path.exists(path):
            with np.load(path) as z:
                for i in range(n):
                    pre = f'L{i}__'
                    self._masks[i] = {k[len(pre):]: np.asarray(z[k], np.float32) for k in z.files
                                      if k.startswith(pre)}
            return
        if log:
            log(f'[terrain_data] masks of {os.path.basename(self.source)} ({n} levels of '
                f"{self.levels[self.main]['n']} cells): computing")
        stack = M.compute_stack(self.fields[:n], self.levels[:n], main=self.main,
                                params=M.MaskParams(**self.mask_params()))
        arrays = {}
        for i, m in enumerate(stack):
            self._masks[i] = {k: np.asarray(v, np.float32) for k, v in m.items()}
            for k, v in m.items():
                arrays[f'L{i}__{k}'] = np.asarray(v, np.float32)
        os.makedirs(MASK_CACHE, exist_ok=True)
        tmp = path + '.tmp.npz'
        np.savez(tmp, **arrays)
        os.replace(tmp, path)

    def masks(self, level='main', log=print):
        i = self.main if level == 'main' else int(level)
        if self._masks[i] is None:
            if i > self.main:
                raise KeyError(f'{self.source}: level {i} carries no masks (a hero level of a levels file)')
            self._compute_masks(log)
        return self._masks[i]

    # ------------------------------------------------------------------------------------------- sampling
    def xy(self, level='main'):
        lv = self.levels[self.main if level == 'main' else int(level)]
        c = (np.arange(lv['n']) + 0.5) * lv['cell']
        return np.meshgrid(lv['x0'] + c, lv['y0'] + c)

    def height_at(self, x, y):
        """Bilinear height at world points from the finest loaded level holding each (the outermost level's edge
        beyond it)."""
        return self.field_at('h', x, y)

    def field_at(self, name, x, y, default=0.0):
        """A field (h, water, deposit ...) at world points, bilinear, from the finest loaded level holding each that
        has it; `default` where none has it."""
        x = np.asarray(x, np.float64)
        y = np.asarray(y, np.float64)
        x, y = np.broadcast_arrays(x, y)
        out = np.full(x.shape, float(default))
        done = np.zeros(x.shape, bool)
        for i in range(len(self.levels) - 1, -1, -1):
            lv = self.levels[i]
            if name not in self.fields[i]:
                continue
            m = ~done
            if i:
                m &= ((x >= lv['x0'] + lv['cell']) & (x <= lv['x0'] + lv['side'] - lv['cell'])
                      & (y >= lv['y0'] + lv['cell']) & (y <= lv['y0'] + lv['side'] - lv['cell']))
            if m.any():
                out[m] = bilinear(self.fields[i][name], lv, x[m], y[m])
                done |= m
        return float(out) if out.ndim == 0 else out

    def surface_at(self, x, y):
        """Where a ray from a camera stops: the ground, or the water over it (a lake's surface, the `water` field's
        depth over the ground; the sea at the terrain's sea level)."""
        z = np.asarray(self.height_at(x, y), np.float64) + np.maximum(
            np.asarray(self.field_at('water', x, y), np.float64), 0.0)
        sea = self.info.get('sea_level')
        if sea is not None:
            z = np.maximum(z, float(sea))
        return float(z) if np.ndim(z) == 0 else z


def bilinear(a, lv, x, y):
    """A cell-centred field of a level at world points, bilinear, clamped at the level's edge."""
    a = np.asarray(a)
    n = a.shape[0]
    fx = np.clip((np.asarray(x, np.float64) - lv['x0']) / lv['cell'] - 0.5, 0.0, n - 1.0)
    fy = np.clip((np.asarray(y, np.float64) - lv['y0']) / lv['cell'] - 0.5, 0.0, n - 1.0)
    i = np.minimum(np.floor(fx).astype(np.int64), n - 2)
    j = np.minimum(np.floor(fy).astype(np.int64), n - 2)
    tx, ty = fx - i, fy - j
    return ((a[j, i] * (1 - tx) + a[j, i + 1] * tx) * (1 - ty)
            + (a[j + 1, i] * (1 - tx) + a[j + 1, i + 1] * tx) * ty)


def _level(d, role=None):
    return dict(x0=float(d['x0']), y0=float(d['y0']), side=float(d.get('side', d['cell'] * d['n'])),
                cell=float(d['cell']), n=int(d['n']), role=role or d.get('role', 'main'))


def _recipe_name(r):
    return r if isinstance(r, str) else (r or {}).get('name')


def load(source, recipe=None, heroes=False, main_side=None):
    """A saved terrain as a Stack (see the module doc). source: a terrain cache key (or its first characters), a
    Terrain.save() .npz, or a generator's *_levels.npz with recipe= its recipe's name. A levels file does not say
    which level is the main one: its finest is taken, or the one main_side metres across when the file holds hero
    levels too."""
    source = str(source)
    if not source.endswith('.npz'):
        root = terrain_cache_root()
        hits = [d for d in os.listdir(root) if d.startswith(source)] if os.path.isdir(root) else []
        if len(hits) != 1:
            raise FileNotFoundError(f'terrain cache entry {source!r}: {len(hits)} matches in {root}')
        d = os.path.join(root, hits[0])
        with open(os.path.join(d, 'meta.json'), encoding='utf-8') as f:
            meta = json.load(f)
        levels, fields, masks = [], [], []
        for i, L in enumerate(meta['plan']):
            if L['role'] == 'hero' and not heroes:
                break
            with np.load(os.path.join(d, f'level_{i}.npz')) as z:
                fields.append({k[3:]: z[k] for k in z.files if k.startswith('f__')})
                masks.append({k[3:]: np.asarray(z[k], np.float32) for k in z.files if k.startswith('m__')})
            levels.append(_level(L))
        return Stack(d, _recipe_name(meta.get('recipe')) or recipe, meta.get('knobs'), levels, fields, masks,
                     dict(cache_key=hits[0], seed=meta.get('seed'), focus=meta.get('focus')))
    with np.load(source) as z:
        files = list(z.files)
        if any('__f__' in k for k in files):                # Terrain.save
            with open(os.path.splitext(source)[0] + '.json', encoding='utf-8') as f:
                meta = json.load(f)
            levels, fields, masks = [], [], []
            for i, L in enumerate(meta['plan']):
                if L['role'] == 'hero' and not heroes:
                    break
                pre_f, pre_m = f'L{i}__f__', f'L{i}__m__'
                fields.append({k[len(pre_f):]: z[k] for k in files if k.startswith(pre_f)})
                masks.append({k[len(pre_m):]: np.asarray(z[k], np.float32) for k in files if k.startswith(pre_m)})
                levels.append(_level(L))
            return Stack(source, _recipe_name(meta.get('recipe')) or meta.get('recipe_name') or recipe,
                         meta.get('knobs'), levels, fields, masks,
                         {k: meta.get(k) for k in ('base_elevation_m', 'sea_level', 'seed', 'focus', 'cache_key')})
        idx = sorted({int(m.group(1)) for k in files for m in [re.match(r'L(\d+)_window$', k)] if m})
        if not idx:
            raise ValueError(f'{source}: not a terrain file (no L<i>__f__ or L<i>_window arrays)')
        if not recipe:
            raise ValueError(f'{source}: a levels file does not name its recipe: pass recipe=')
        wins = {i: [float(v) for v in z[f'L{i}_window']] for i in idx}
        main = idx[-1]
        if main_side:                                       # a file that also holds hero levels
            near = [i for i in idx if abs(wins[i][2] - float(main_side)) < 1e-3 * float(main_side)]
            if not near:
                raise ValueError(f'{source}: no level {main_side:g} m across (sides: '
                                 f'{", ".join(f"{wins[i][2]:g}" for i in idx)})')
            main = near[-1]
        levels, fields, masks = [], [], []
        for i in idx:
            if i > main and not heroes:
                break
            x0, y0, side, cell, n = wins[i]
            role = 'main' if i == main else ('context' if i < main else 'hero')
            pre = f'L{i}_'
            fields.append({k[len(pre):]: z[k] for k in files if k.startswith(pre) and k != f'L{i}_window'})
            masks.append(None)
            levels.append(dict(x0=x0, y0=y0, side=side, cell=cell, n=int(n), role=role))
        return Stack(source, recipe, None, levels, fields, masks, {})
