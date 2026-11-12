"""make_terrain and the Terrain it returns (design section 8).

    from eidoblend.terrain import make_terrain, recipes, describe
    t = make_terrain(recipe='real_place', params={'dem': 'lauterbrunnen'}, focus=(480, 1640), seed=1)
    obj, height_at, masks = t                     # or the members below
    t.height_at(x, y)        # metres at Blender (x, y), exactly on the rendered triangles (floats or arrays)
    t.normal_at(x, y)        # the shading normal there
    t.mask('slope').at(x, y) # any mask (masks.MASKS) at world points, from the finest level holding them
    t.viewpoint(target=(0, -3000), distance=1500)   # a standing point that sees the target (not a wall)
    t.preview('<dir>/name')  # hillshade and mask PNGs, to look at before a render

The call, in order: the recipe (a name, a Recipe, a recipe dict or a list of stages) and its knobs are resolved and
checked; the defaults come from the recipe, its DEM (real_place) and the quality; plan_levels lays out the levels
around the focus; the cache is read, or the level runner (terrain/run.py: run_levels) runs the stages and writes
it; the exact flatten pass; the masks; the ring mesh with the masks as point attributes; then, in Blender, the
object, the palette's material (palette=None: grey clay), lake and sea surfaces, and rocks near the focus. One
summary line is printed, naming any stage whose op is not registered yet (the runner skips it). The runner's
kernels need Blender's GPU module: run it in Blender (through a GPU slot on this machine).
"""
from __future__ import annotations

import difflib
import glob
import hashlib
import json
import math
import os
import time
from collections import namedtuple

import numpy as np

from . import recipes as _registry
from .build import mesh as _mesh
from .core import levels as _levels
from .core.fields import Fields

API_VERSION = 1
ARGS =('recipe', 'size', 'resolution', 'seed', 'params', 'focus', 'hero_cell', 'context', 'flatten', 'sea_level',
        'base_elevation_m', 'palette', 'dress', 'quality', 'cache', 'name', 'collection', 'mesh_res', 'log')
_HERE = os.path.dirname(os.path.abspath(__file__))


def _nearest(name, options):
    near = difflib.get_close_matches(str(name), list(options), n=3, cutoff=0.4)
    return f'; nearest: {", ".join(near)}' if near else f'; valid: {", ".join(sorted(options))}'


# ------------------------------------------------------------------------------------------------- masks ---

class Mask:
    """One mask over every level: .at(x, y) samples the finest level that holds each point (bilinear on its cell
    centres), .array(level) is a level's (n, n) float32 array (row 0 south), level by index or role."""

    def __init__(self, name, arrays, plan):
        self.name = name
        self._arrays = arrays
        self._plan = plan

    def array(self, level='main'):
        i = _level_index(self._plan, level)
        a = self._arrays[i]
        if a is None:
            raise KeyError(f'mask {self.name!r} was not made on level {i} ({self._plan[i]})')
        return a

    def at(self, x, y):
        from .core.grid import sample_bilinear
        x = np.asarray(x, np.float64)
        y = np.asarray(y, np.float64)
        x, y = np.broadcast_arrays(x, y)
        out = np.zeros(x.shape, np.float64)
        done = np.zeros(x.shape, bool)
        for i in range(len(self._plan) - 1, -1, -1):
            lv, a = self._plan[i], self._arrays[i]
            if a is None:
                continue
            m = ~done & lv.contains(x, y) if i else ~done
            if m.any():
                out[m] = sample_bilinear(a, lv.x0, lv.y0, lv.cell, x[m], y[m])
                done |= m
        return float(out) if out.ndim == 0 else out

    def __repr__(self):
        return f'Mask({self.name!r}, {sum(a is not None for a in self._arrays)} levels)'


class MaskSet:
    """Every mask of a terrain: t.masks['slope'].at(x, y), .array(level), .names()."""

    def __init__(self, stack, plan):
        self._stack = stack
        self._plan = plan
        self._names = sorted(set().union(*[set(m) for m in stack])) if stack else []

    def names(self):
        return list(self._names)

    def __getitem__(self, name):
        if name not in self._names:
            raise KeyError(f'no mask {name!r}' + _nearest(name, self._names))
        return Mask(name, [m.get(name) for m in self._stack], self._plan)

    def __contains__(self, name):
        return name in self._names

    def __iter__(self):
        return iter(self._names)

    def __len__(self):
        return len(self._names)

    def level(self, level='main'):
        """The masks of one level as a dict."""
        return self._stack[_level_index(self._plan, level)]

    def skipped(self):
        """{level index: {mask: why}} for masks the masks package left out (an input field absent)."""
        return {i: dict(getattr(m, 'skipped', {})) for i, m in enumerate(self._stack) if getattr(m, 'skipped', None)}


def _level_index(plan, level):
    if isinstance(level, (int, np.integer)):
        return int(level) % len(plan)
    if isinstance(level, _levels.Level):
        return int(level.index)
    if level in ('main', 'context', 'hero', 'first', 'last'):
        if level == 'first':
            return 0
        if level == 'last':
            return len(plan) - 1
        hit = [lv.index for lv in plan if lv.role == level]
        if not hit:
            raise KeyError(f'no {level} level in this terrain ({[lv.role for lv in plan]})')
        return hit[-1] if level != 'context' else hit[0]
    raise KeyError(f"level {level!r}: an index, a Level, or 'main' | 'context' | 'hero' | 'first' | 'last'")


# ---------------------------------------------------------------------------------------------- viewpoint ---

Viewpoint = namedtuple('Viewpoint', 'eye target ground_z heading_deg pitch_deg distance clearance_m lens_mm')


def _place_camera(vp, camera, lens_mm=None):
    """Set a Blender camera to a Viewpoint: at the eye, looking at the target, level horizon."""
    from mathutils import Vector
    eye, tgt = Vector(vp.eye), Vector(vp.target)
    d = tgt - eye
    camera.location = eye
    camera.rotation_mode = 'XYZ'
    camera.rotation_euler = (math.pi / 2 + math.atan2(d.z, math.hypot(d.x, d.y)), 0.0,
                             math.atan2(d.y, d.x) - math.pi / 2)
    if getattr(camera, 'data', None) is not None and hasattr(camera.data, 'lens'):
        camera.data.lens = float(lens_mm or vp.lens_mm)
    return camera


# ------------------------------------------------------------------------------------------------ terrain ---

class Terrain:
    """A made terrain (design section 8's members). Iterating gives (obj, height_at, masks)."""

    def __init__(self, recipe, values, plan, fields, masks, ring, info):
        self.recipe = recipe
        self.knobs = values
        self.levels = plan
        self._fields = fields
        self.masks = masks
        self.ring = ring
        self.info = info
        self.obj = None
        self.water = {'lakes': [], 'sea': None}
        self.rocks = None
        self.flats = info.get('flats', [])

    def __iter__(self):
        return iter((self.obj, self.height_at, self.masks))

    def __repr__(self):
        return (f"Terrain({self.recipe.name!r}, {len(self.levels)} levels, {self.ring.triangle_count:,} triangles"
                + (f", object {self.obj.name!r}" if self.obj is not None else '') + ')')

    # sampling ---------------------------------------------------------------------------------------------------
    def height_at(self, x, y):
        """Metres at Blender (x, y), exactly on the rendered triangles of the finest ring holding the point (the
        mesh's float32 vertices; outside the outermost window, its edge). Floats or arrays."""
        return self.ring.height_at(x, y)

    def normal_at(self, x, y, smooth=True):
        """The surface normal at Blender (x, y): the shading normal (smooth=True) or the triangle's (False)."""
        return self.ring.normal_at(x, y, smooth)

    def mask(self, name):
        return self.masks[name]

    def fields(self, level='main'):
        """A level's raw arrays (core Fields: h, water, wear ...), level by index or role."""
        return self._fields[_level_index(self.levels, level)]

    @property
    def main(self):
        return self.levels[_level_index(self.levels, 'main')]

    def metrics(self, pixel_m=None):
        """The judge's generic numbers (core/metrics) of the main level, box-averaged to pixel_m first if given."""
        from .core import metrics as _metrics
        lv = self.main
        h = np.asarray(self.fields('main')['h'], np.float64)
        if pixel_m is not None and pixel_m > lv.cell * (1 + 1e-9):
            h = _metrics.to_pixel(h, lv.cell, pixel_m)
            return _metrics.metrics(h, pixel_m)
        return _metrics.metrics(h, lv.cell)

    # viewpoints --------------------------------------------------------------------------------------------------
    def viewpoint(self, target, distance, eye_height=1.7, heading=None, max_slope_deg=30.0, lens_mm=35.0,
                  look_dz=0.0, prefer=None, clearance_m=1.0, within='main'):
        """A standing point about `distance` metres from `target` ((x, y) or (x, y, z)) from which an eye
        `eye_height` above the ground sees the target: the sight line clears the terrain by clearance_m all the way
        (so an eye-level camera does not face a wall), the footing is under max_slope_deg, inside the `within`
        level. Candidates every 5 degrees around the target at 0.55-1.5 x the distance; the visible ones are ranked
        by the heading asked for (compass degrees the camera looks toward), then prefer 'low' (a valley floor) or
        'high' (a rim), then the distance asked for. Returns a Viewpoint (eye, target, ground_z, heading_deg,
        pitch_deg, distance, clearance_m, lens_mm); place_camera(vp, cam) sets a camera to it. Raises ValueError
        when no candidate sees the target."""
        tx, ty = float(target[0]), float(target[1])
        tz = (float(target[2]) if len(target) > 2 else float(self.height_at(tx, ty))) + look_dz
        lv = self.levels[_level_index(self.levels, within)]
        az = np.radians(np.arange(0.0, 360.0, 5.0))
        fac = np.array([1.0, 0.85, 1.15, 0.7, 1.3, 0.55, 1.5])
        A, F = np.meshgrid(az, fac)
        A, F = A.ravel(), F.ravel()
        D = F * float(distance)
        px, py = tx + D * np.sin(A), ty + D * np.cos(A)          # A: compass bearing from the target to the eye
        ok = lv.contains(px, py, margin=2 * lv.cell)
        if not ok.any():
            raise ValueError(f'viewpoint: no point {distance:g} m from ({tx:g}, {ty:g}) lies inside the {within} level')
        px, py, A, D = px[ok], py[ok], A[ok], D[ok]
        gz = self.height_at(px, py)
        nz = self.normal_at(px, py, smooth=False)[:, 2]
        flat = np.degrees(np.arccos(np.clip(nz, -1, 1))) <= max_slope_deg
        ez = gz + eye_height
        k = 160
        t0 = np.minimum(3.0 / np.maximum(D, 3.0), 0.5)[:, None]      # from 3 m out (the eye clears its own feet)
        t = t0 + (0.97 - t0) * np.linspace(0.0, 1.0, k)[None, :]
        lx = px[:, None] + (tx - px[:, None]) * t
        ly = py[:, None] + (ty - py[:, None]) * t
        lz = ez[:, None] + (tz - ez[:, None]) * t
        clear = (lz - self.height_at(lx, ly)).min(1)
        good = flat & (clear >= clearance_m)
        if not good.any():
            best = int(np.argmax(clear))
            raise ValueError(f'viewpoint: nothing {distance:g} m around ({tx:g}, {ty:g}) sees it (best clearance '
                             f'{clear[best]:.1f} m from ({px[best]:.0f}, {py[best]:.0f})): try another distance or '
                             f'look_dz')
        score = np.zeros(len(px))
        look_heading = (np.degrees(A) + 180.0) % 360.0              # the camera looks back toward the target
        if heading is not None:
            score -= np.abs((look_heading - heading + 180.0) % 360.0 - 180.0) / 10.0
        if prefer in ('low', 'high'):
            rel = (gz - gz.min()) / max(float(np.ptp(gz)), 1e-6)
            score += (1.0 - rel if prefer == 'low' else rel) * 6.0
        score -= np.abs(D / float(distance) - 1.0) * 4.0
        score += np.minimum(clear, 50.0) / 50.0
        score[~good] = -np.inf
        b = int(np.argmax(score))
        eye = (float(px[b]), float(py[b]), float(ez[b]))
        dist = float(math.hypot(tx - eye[0], ty - eye[1]))
        pitch = math.degrees(math.atan2(tz - eye[2], dist))
        return Viewpoint(eye, (tx, ty, tz), float(gz[b]), float(look_heading[b]), pitch, dist, float(clear[b]),
                         float(lens_mm))

    # files ---------------------------------------------------------------------------------------------------------
    def preview(self, path, masks=('slope', 'flow', 'rock', 'snow', 'vegetation', 'wetness', 'talus')):
        """Hillshade and mask PNGs for a look before a render: <path>_main_hillshade.png (north up, the hero windows
        outlined), <path>_hero_hillshade.png (the finest level), and <path>_mask_<name>.png (main level) for each
        mask present. Returns the paths written."""
        from .core import io as _io
        out = []
        os.makedirs(os.path.dirname(os.path.abspath(path)) or '.', exist_ok=True)
        lv = self.main
        h = np.asarray(self.fields('main')['h'], np.float64)
        hs = _io.hillshade(h, lv.cell)
        rgb = np.repeat(_io.to_u8(hs)[..., None], 3, 2)
        for c in self.levels[lv.index + 1:]:                 # the hero windows, outlined
            i0 = int(round((c.x0 - lv.x0) / lv.cell))
            j0 = int(round((c.y0 - lv.y0) / lv.cell))
            m = max(int(round(c.side / lv.cell)), 1)
            i1, j1 = min(i0 + m, lv.n - 1), min(j0 + m, lv.n - 1)
            for (a, b, cc, d) in ((j0, j0 + 1, i0, i1 + 1), (j1, j1 + 1, i0, i1 + 1), (j0, j1 + 1, i0, i0 + 1),
                                  (j0, j1 + 1, i1, i1 + 1)):
                rgb[a:b, cc:d] = (255, 200, 40)
        out.append(_io.write_png(path + '_main_hillshade.png', np.ascontiguousarray(rgb[::-1])))
        if self.levels[-1].role == 'hero':
            fl = self.levels[-1]
            hf = np.asarray(self._fields[-1]['h'], np.float64)
            out.append(_io.write_png(path + '_hero_hillshade.png',
                                     np.ascontiguousarray(_io.to_u8(_io.hillshade(hf, fl.cell))[::-1])))
        for name in masks:
            if name in self.masks:
                try:
                    a = np.asarray(self.masks[name].array('main'), np.float64)
                except KeyError:
                    continue
                lo, hi = np.percentile(a, 1), np.percentile(a, 99)
                t = np.clip((a - lo) / max(hi - lo, 1e-9), 0, 1)
                out.append(_io.write_png(path + f'_mask_{name}.png', np.ascontiguousarray(_io.to_u8(t)[::-1])))
        return out

    def save(self, path):
        """Write the terrain (every level's fields and masks, the plan, the recipe and knobs, the flats) to
        <path>.npz with its description in <path>.json. Terrain.load reads it back."""
        from . import masks as _masks
        arrays = {}
        for i, f in enumerate(self._fields):
            for k, v in f.items():
                arrays[f'L{i}__f__{k}'] = np.asarray(v)
        for i, m in enumerate(self.masks._stack):
            for k, v in m.items():
                arrays[f'L{i}__m__{k}'] = _cache_dtype(_masks, k, v)
        base = os.path.splitext(path)[0]
        os.makedirs(os.path.dirname(os.path.abspath(base)) or '.', exist_ok=True)
        np.savez(base + '.npz', **arrays)
        meta = dict(self.info, recipe=self.recipe.to_dict(), knobs=self.knobs,
                    plan=[lv.to_dict() for lv in self.levels], api_version=API_VERSION)
        with open(base + '.json', 'w', encoding='utf-8') as f:
            json.dump(_plain(meta), f, indent=1)
        return base + '.npz'

    @classmethod
    def load(cls, path, build=True, name=None, collection=None, palette='keep', dress=False, log=print):
        """A Terrain from save(); build=True also makes its object (palette 'keep': the one it was made with)."""
        base = os.path.splitext(path)[0]
        with open(base + '.json', encoding='utf-8') as f:
            meta = json.load(f)
        plan = [_levels.Level.from_dict(d) for d in meta['plan']]
        R = _registry.resolve(meta['recipe'])
        fields = [Fields(lv) for lv in plan]
        stack = [_Masks() for _ in plan]
        with np.load(base + '.npz', allow_pickle=False) as z:
            for k in z.files:
                lvl, kind, nm = k.split('__', 2)
                i = int(lvl[1:])
                if kind == 'f':
                    fields[i][nm] = z[k]
                else:
                    stack[i][nm] = np.asarray(z[k], np.float32)
        info = dict(meta)
        t = _assemble_terrain(R, meta['knobs'], plan, fields, stack, info)
        if build:
            pal = info.get('palette') if palette == 'keep' else palette
            _build_blender(t, name or info.get('name', 'terrain'), collection, pal, dress, log)
        return t


class _Masks(dict):
    skipped = {}


def _plain(v):
    if hasattr(v, 'to_dict'):
        return v.to_dict()
    if isinstance(v, dict):
        return {str(k): _plain(x) for k, x in v.items()}
    if isinstance(v, (list, tuple)):
        return [_plain(x) for x in v]
    if isinstance(v, np.ndarray):
        return v.tolist()
    if isinstance(v, np.generic):
        return v.item()
    return v


# ------------------------------------------------------------------------------------------------ flatten ---

def _flat_distance(spec, x, y):
    """Metres from the flat area's edge (0 inside): a disc (radius) or a rectangle (size (w, l), angle_deg)."""
    cx, cy = float(spec['at'][0]), float(spec['at'][1])
    if spec.get('size') is not None:
        w, l = (float(spec['size'][0]), float(spec['size'][1]))
        a = math.radians(float(spec.get('angle_deg', 0.0)))
        u = (x - cx) * math.cos(a) + (y - cy) * math.sin(a)
        v = -(x - cx) * math.sin(a) + (y - cy) * math.cos(a)
        return np.hypot(np.maximum(np.abs(u) - w / 2, 0.0), np.maximum(np.abs(v) - l / 2, 0.0))
    return np.maximum(np.hypot(x - cx, y - cy) - float(spec.get('radius', 10.0)), 0.0)


def _check_flatten(flatten):
    out = []
    for i, s in enumerate(flatten or []):
        s = dict(s)
        bad = set(s) - {'at', 'radius', 'falloff', 'height', 'size', 'angle_deg'}
        if bad:
            raise KeyError(f'flatten[{i}]: unknown key {sorted(bad)[0]!r}' +
                           _nearest(sorted(bad)[0], ['at', 'radius', 'falloff', 'height', 'size', 'angle_deg']))
        if 'at' not in s:
            raise KeyError(f"flatten[{i}] needs 'at': (x, y) metres")
        s.setdefault('falloff', float(s.get('radius', 10.0)) if s.get('size') is None else 10.0)
        out.append(s)
    return out


def flatten_fields(fields, plan, flatten):
    """The exact flatten pass (design 4.13), in place on every level's h (and bed, kept under it): inside each area
    the ground is exactly its height (given, or the median of the finest level's h there), blended back over
    `falloff` metres with a C1 smoothstep. Returns the resolved areas (Terrain.flats)."""
    flats = []
    for s in flatten:
        fin = None
        for lv in reversed(plan):
            if lv.contains(s['at'][0], s['at'][1], margin=float(s.get('radius', 0.0))):
                fin = lv
                break
        fin = fin or plan[0]
        X, Y = fin.xy()
        d = _flat_distance(s, X, Y)
        h0 = fields[fin.index]['h']
        inside = d <= 0.0
        if s.get('height') is not None:
            z = float(s['height'])
        else:                                   # the area's median (an area smaller than a cell: its nearest cell)
            z = float(np.median(h0[inside])) if inside.any() else float(h0.flat[np.argmin(d)])
        fo = max(float(s['falloff']), 1e-6)
        for lv, f in zip(plan, fields):
            X, Y = lv.xy()
            d = _flat_distance(s, X, Y)
            if d.min() > fo:
                continue
            t = np.clip(d / fo, 0.0, 1.0)
            w = 1.0 - t * t * (3.0 - 2.0 * t)
            f['h'] = f['h'] * (1.0 - w) + z * w
            if 'bed' in f:
                f['bed'] = np.minimum(f['bed'], f['h'])
        flats.append(dict(s, height=z, at=[float(s['at'][0]), float(s['at'][1])], level=fin.index))
    return flats


# ------------------------------------------------------------------------------------------- the levels ---

def _run_levels(plan, R, values, stages, seed, flatten, sea_level, base_elevation_m, cache, log):
    """The levels' fields from the level runner (terrain/run.py): (fields, the stage labels it skipped because their
    op is not registered yet)."""
    from . import run as _run
    info = {}
    out = _run.run_levels(plan, R, values, stages, seed=seed, flatten=flatten, sea_level=sea_level,
                          base_elevation_m=base_elevation_m, log=log, cache=bool(cache), info=info)
    return list(out), _run.skipped_stages(info)


def _code_hash():
    """The code outside core's cache hash that shapes a cached terrain: the masks and the recipe modules."""
    h = hashlib.sha1()
    for p in sorted(glob.glob(os.path.join(_HERE, 'recipes', '*.py')) + [os.path.join(_HERE, 'masks.py')]):
        if os.path.exists(p):
            with open(p, 'rb') as f:
                h.update(f.read())
    return h.hexdigest()


_HALF_UNITS = ('0-1', '-1..1', 'deg')


def _cache_dtype(masks_mod, name, a):
    """A mask as the cache stores it: float16 for the bounded ones (0-1, -1..1, degrees: a 0.05-degree step at most),
    float32 for metres and curvatures (heights need the precision, curvatures the range). Seven levels of 1000
    cells hold about 700 MB of masks at float32; this keeps about 60 % of it."""
    try:
        unit = masks_mod.MASKS[masks_mod.parse_name(name)[0]][0]
    except KeyError:
        unit = None
    return np.asarray(a, np.float16 if unit in _HALF_UNITS else np.float32)


def _scaled_resolution(res, quality):
    if not res:
        return None
    f = {'draft': 0.5, 'film': 1.0, 'hero': 2.0}[quality]
    return int(max(64, round(res * f / 8.0) * 8))


# ----------------------------------------------------------------------------------------------- the call ---

def make_terrain(recipe=None, size=None, resolution=None, seed=None, params=None, focus=None, hero_cell=None,
                 context=None, flatten=None, sea_level=None, base_elevation_m=None, palette='auto', dress=True,
                 quality='film', cache=True, name='terrain', collection=None, mesh_res=None, log=print, **unknown):
    """A terrain (design section 8). Returns a Terrain; `obj, height_at, masks = make_terrain(...)` also works.

    recipe       a name from recipes(), a Recipe, a recipe dict (recipe.to_dict(), edited) or a list of stages
    size         metres, the main tile's side (default: the recipe's; real_place: the DEM's extent)
    resolution   cells across the main tile (default: the quality's 512 / 1024 / 2048, or the recipe's, scaled)
    seed         the random seed of every stage
    params       the recipe's knobs, in their units ({'relief_m': 2800}); an unknown knob names the nearest
    focus        (x, y), [(x, y), ...], a camera object or a list of camera positions: hero levels around it
    hero_cell    metres, the finest cell around the focus (default 0.5, 0.25 at quality 'hero'; draft: none)
    context      the horizon levels' extent multiplier (default the recipe's)
    flatten      [{'at': (x, y), 'radius': r, 'falloff': f, 'height': None}, ...]: flat areas (or 'size': (w, l)
                 and 'angle_deg' for a rectangle); height None = the area's median
    sea_level    metres (Blender z), or None
    base_elevation_m  the altitude of z = 0 (snowline, treeline, ELA)
    palette      'auto' (the recipe's or the place's), a palette name, a palette dict, or None (grey clay)
    dress        rocks on the talus and rock-toe masks near the focus
    quality      'draft' | 'film' | 'hero'
    cache        read and write eidoverse/assets/cache/terrain/<key>
    mesh_res     vertices per side each level is drawn at (default 512: about 3.3M triangles for seven levels)
    """
    t0 = time.perf_counter()
    if unknown:
        k = sorted(unknown)[0]
        raise TypeError(f'make_terrain() got an unexpected keyword {k!r}' + _nearest(k, ARGS))
    if recipe is None:
        raise TypeError('make_terrain needs a recipe: one of ' + ', '.join(_registry.names()))
    if quality not in _levels.QUALITY:
        raise ValueError(f'quality {quality!r}' + _nearest(quality, _levels.QUALITY))
    t = generate(recipe, size, resolution, seed or 0, params, focus, hero_cell, context, flatten, sea_level,
                 base_elevation_m, quality, cache, mesh_res, palette, log)
    tb = time.perf_counter()
    _build_blender(t, name, collection, palette, dress, log)
    t.info['seconds']['blender'] = round(time.perf_counter() - tb, 2)
    t.info['seconds']['total'] = round(time.perf_counter() - t0, 2)
    _summary(t, log)
    return t


def generate(recipe, size=None, resolution=None, seed=0, params=None, focus=None, hero_cell=None, context=None,
             flatten=None, sea_level=None, base_elevation_m=None, quality='film', cache=True, mesh_res=None,
             palette='auto', log=print):
    """Everything make_terrain does short of Blender: the levels, their fields and masks, and the ring mesh as numpy
    (height_at, normal_at, masks work). bake.py uses it."""
    secs = {}
    t0 = time.perf_counter()
    R = _registry.resolve(recipe)
    values, stages = R.resolve(params)
    dfl = dict(R.defaults)
    if getattr(R, 'defaults_for', None) is not None:
        dfl.update(R.defaults_for(values))
    Q = _levels.QUALITY[quality]
    size = float(size if size is not None else dfl.get('size') or 0.0)
    if size <= 0:
        raise ValueError(f'recipe {R.name!r} has no default size: pass size= (metres)')
    res = int(resolution or _scaled_resolution(dfl.get('resolution'), quality) or Q['resolution'])
    ctxm = context if context is not None else dfl.get('context')
    if hero_cell is not None:
        hero = float(hero_cell)
    elif Q['hero_cell'] is None:
        hero = None
    else:
        hero = min(float(dfl.get('hero_cell', Q['hero_cell'])), float(Q['hero_cell']))
    if sea_level is None:
        sea_level = dfl.get('sea_level')
    if base_elevation_m is None:
        base_elevation_m = float(dfl.get('base_elevation_m', 0.0))
    centre = tuple(dfl.get('centre', (0.0, 0.0)))
    flatten = _check_flatten(flatten)
    warnings = []

    def warn(m):
        warnings.append(m)
        log('[make_terrain] ' + m)
    plan = _levels.plan_levels(size, res, centre, ctxm, focus, hero, warn=warn)
    pts = _levels.focus_points(focus)
    focus_list = pts.tolist() if pts is not None else None
    mask_params = dict(dfl.get('mask_params') or {})
    mask_params['sea_level'] = sea_level                  # z's frame, as MaskParams wants it
    mask_params['base_elevation_m'] = base_elevation_m
    secs['plan'] = round(time.perf_counter() - t0, 2)

    # the cache: everything that decides the fields and masks
    from .core import cache as _cache
    key = _cache.make_key(R.to_dict(), values, size, res, seed, plan, focus_list,
                          extra=dict(flatten=flatten, sea_level=sea_level, base_elevation_m=base_elevation_m,
                                     mask_params=mask_params, quality=quality, api=API_VERSION, code=_code_hash()))
    C = _cache.Cache(key)
    hit = bool(cache) and C.complete()
    skipped, flats = [], []
    t1 = time.perf_counter()
    if hit:
        fields, stack = [], []
        for i, lv in enumerate(plan):
            arrays = C.load_level(i)
            fields.append(Fields(lv, {k[3:]: v for k, v in arrays.items() if k.startswith('f__')}))
            m = _Masks({k[3:]: np.asarray(v, np.float32) for k, v in arrays.items() if k.startswith('m__')})
            stack.append(m)
        meta = C.read_meta() or {}
        flats, skipped = meta.get('flats', []), meta.get('skipped', [])
        secs['load'] = round(time.perf_counter() - t1, 2)
    else:
        if getattr(R, 'prepare', None) is not None:
            R.prepare(values, plan)
        fields, skipped = _run_levels(plan, R, values, stages, seed, flatten, sea_level, base_elevation_m, cache, log)
        secs['levels'] = round(time.perf_counter() - t1, 2)
        t2 = time.perf_counter()
        if flatten:
            flats = flatten_fields(fields, plan, flatten)
        from . import masks as _masks
        allowed = set(_masks.MaskParams.__dataclass_fields__)
        bad = set(mask_params) - allowed
        if bad:
            raise KeyError(f'mask parameter {sorted(bad)[0]!r}' + _nearest(sorted(bad)[0], allowed))
        stack = _masks.compute_stack(fields, plan, params=_masks.MaskParams(**mask_params))
        secs['masks'] = round(time.perf_counter() - t2, 2)
        if cache:
            for i, (f, m) in enumerate(zip(fields, stack)):
                arrays = {'f__' + k: v for k, v in f.items()}
                arrays.update({'m__' + k: _cache_dtype(_masks, k, v) for k, v in m.items()})
                C.save_level(i, arrays)
            C.write_meta(dict(recipe=R.name, knobs=values, size=size, resolution=res, seed=seed,
                              levels=len(plan), plan=plan, focus=focus_list, flats=flats, skipped=skipped))
            # a film terrain is about 450 MB here: keep the cache to EIDO_TERRAIN_CACHE_GB (default 8), oldest out
            _cache.prune(keep_gb=float(os.environ.get('EIDO_TERRAIN_CACHE_GB', 8.0)))
    info = dict(name=None, recipe_name=R.name, size=size, resolution=res, seed=int(seed), quality=quality,
                focus=focus_list, hero_cell=hero, context=ctxm, sea_level=sea_level,
                base_elevation_m=base_elevation_m, palette=(dfl.get('palette') if palette == 'auto' else palette),
                place=dfl.get('place'), cache_key=key, cache_hit=hit, skipped_stages=skipped, flats=flats,
                warnings=warnings, mesh_res=int(mesh_res or _mesh.MESH_RES), seconds=secs,
                attribution=dfl.get('attribution'))
    tm = time.perf_counter()
    t = _assemble_terrain(R, values, plan, fields, stack, info)
    secs['mesh'] = round(time.perf_counter() - tm, 2)
    secs['generate'] = round(time.perf_counter() - t0, 2)
    return t


def _assemble_terrain(R, values, plan, fields, stack, info):
    names = sorted(set().union(*[set(m) for m in stack]))
    attrs = {n: [m.get(n) for m in stack] for n in names}
    cores = any(lv.role == 'hero' for lv in plan)
    ring = _mesh.build_rings(plan, [f['h'] for f in fields], attrs, cores=cores,
                             mesh_res=int(info.get('mesh_res') or _mesh.MESH_RES))
    t = Terrain(R, values, plan, fields, MaskSet(stack, plan), ring, info)
    return t


# --------------------------------------------------------------------------------------------- in Blender ---

def _build_blender(t, name, collection, palette, dress, log):
    import bpy
    from .build import water as _water
    info = t.info
    info['name'] = name
    obj = _mesh.make_object(t.ring, name, collection)
    t.obj = obj
    obj['trimesh_collider'] = True
    obj['eido_terrain'] = json.dumps(_plain(dict(
        recipe=t.recipe.to_dict(), knobs=t.knobs, seed=info['seed'], size=info['size'],
        resolution=info['resolution'], quality=info['quality'], focus=info['focus'],
        plan=[lv.to_dict() for lv in t.levels], cache_key=info['cache_key'], flats=t.flats,
        sea_level=info['sea_level'], base_elevation_m=info['base_elevation_m'], api_version=API_VERSION)))
    obj['eido_terrain_mesh'] = json.dumps(t.ring.layout())
    # the material
    try:
        from .build import surfacing as _surf
    except ImportError:
        _surf = None
    pal = palette
    if palette == 'auto' and info.get('place'):
        pal = info.get('palette') or 'auto'
    if _surf is None:
        log('[make_terrain] build/surfacing.py is not in yet: the terrain is grey clay')
        mat = bpy.data.materials.new(name + '_clay')
        mat.use_nodes = True
        b = mat.node_tree.nodes['Principled BSDF']
        b.inputs['Base Color'].default_value = (0.18, 0.18, 0.18, 1.0)
        b.inputs['Roughness'].default_value = 0.9
        obj.data.materials.append(mat)
    elif pal is None:
        obj.data.materials.append(_surf.clay_material(name + '_clay'))
    else:
        strata = None
        if info.get('place'):
            from .build import palettes as _pal
            strata = (_pal.PLACES.get(info['place']) or {}).get('strata')
        _surf.apply_surface(obj, palette=pal, recipe=t.recipe, strata=strata, log=log)
    info['palette'] = pal
    # water
    lakes = _water.lake_objects(t, name=name + '_lake', collection=collection)
    sea = (_water.sea_object(t, info['sea_level'], name=name + '_sea', collection=collection)
           if info.get('sea_level') is not None else None)
    t.water = {'lakes': lakes, 'sea': sea}
    # rocks near the focus
    if dress and info.get('focus') and pal is not None and _surf is not None:
        try:
            from .build import dressing as _dress
            from .build import palettes as _pal
            spec = _pal.get(pal, t.recipe).get('dressing')
        except (ImportError, KeyError, ValueError) as e:
            log(f'[make_terrain] no rocks: {e}')
            spec = None
        if spec:
            fx, fy = np.mean(np.asarray(info['focus'], np.float64), axis=0)

            def mask_at(nm, x, y):
                return t.masks[nm].at(x, y) if nm in t.masks else None
            exclude = [(f['at'][0], f['at'][1], float(f.get('radius', 0.0))) for f in t.flats if f.get('radius')]
            t.rocks = _dress.scatter_rocks(spec, mask_at=mask_at, height_at=t.height_at, normal_at=t.normal_at,
                                           focus=(float(fx), float(fy)), seed=info['seed'], name=name + '_rocks',
                                           collection=collection, exclude=exclude, log=log)
    return obj


def _summary(t, log):
    i = t.info
    lv = t.levels
    s = i['seconds']
    parts = ', '.join(f'{k} {v}' for k, v in s.items() if k not in ('total', 'generate'))
    skipped = f"; stages not run (their solver is not in yet): {', '.join(i['skipped_stages'])}" \
        if i['skipped_stages'] else ''
    log(f"[make_terrain] {t.recipe.name}{' ' + repr(t.knobs.get('dem')) if 'dem' in t.knobs else ''}: "
        f"{len(lv)} levels ({lv[0].side / 1000:g} km @ {lv[0].cell:.3g} m .. {lv[-1].side:g} m @ {lv[-1].cell:.3g} m), "
        f"cache {'hit' if i['cache_hit'] else 'miss'}, {s.get('total', s.get('generate'))} s ({parts}), "
        f"{t.ring.triangle_count:,} triangles{skipped}")


# ------------------------------------------------------------------------------------------- discovery ---

def recipes():
    """{name: title} of every recipe."""
    return _registry.listing()


def describe(recipe, log=print):
    """Print (and return) a recipe's stages, knobs (unit, default, range, what each does) and references, with the
    stages whose op is not registered yet marked."""
    R = _registry.resolve(recipe)
    text = R.describe()
    missing = [s.op for s in R.stages if not _registry.has_op(s.op)]
    if missing:
        text += '\n  ops not registered yet (skipped until their package lands): ' + ', '.join(dict.fromkeys(missing))
    if R.name == 'real_place':
        from .recipes import real_place as _rp
        text += '\n  DEMs here: ' + ', '.join(_rp.dem_names())
    if log:
        log(text)
    return text


def terrain_height_at(obj):
    """height_at for a terrain object after its .blend is reopened: the ring layout stored on the object and its own
    vertices rebuild the exact sampler (no cache and no regeneration needed)."""
    p = obj.get('eido_terrain')
    if p is None:
        raise ValueError(f"'{obj.name}' was not made by make_terrain (no eido_terrain property)")
    ring =_mesh.rebuild(json.loads(obj['eido_terrain_mesh']), _mesh.read_vertices(obj))
    loc = obj.matrix_world.translation
    rot_scale = obj.matrix_world.to_3x3()
    if any(abs(rot_scale[i][j] - (1.0 if i == j else 0.0)) > 1e-9 for i in range(3) for j in range(3)):
        raise ValueError(f"'{obj.name}' is rotated or scaled: height_at reads an unrotated, unscaled terrain")
    ox, oy, oz = float(loc.x), float(loc.y), float(loc.z)

    def height_at(x, y):
        """Ground height (Blender z, metres) at Blender (x, y), on the object's triangles. Floats or arrays."""
        h = ring.height_at(np.asarray(x, np.float64) - ox, np.asarray(y, np.float64) - oy)
        return h + oz
    height_at.ring = ring
    return height_at


place_camera = _place_camera

__all__ = ['make_terrain', 'generate', 'Terrain', 'MaskSet', 'Mask', 'Viewpoint', 'recipes', 'describe',
           'terrain_height_at', 'flatten_fields', 'place_camera']
