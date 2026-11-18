"""make_terrain and the Terrain it returns (design section 8; the surface and the plants: SURFACING_DESIGN.md 5.3).

    from eidoblend.terrain import make_terrain, recipes, describe
    t = make_terrain(recipe='real_place', params={'dem': 'lauterbrunnen'}, focus=(480, 1640), seed=1,
                     plants='auto', cameras=[cam])
    obj, height_at, masks = t                     # or the members below
    t.height_at(x, y)        # metres at Blender (x, y), exactly on the rendered triangles (floats or arrays)
    t.normal_at(x, y)        # the shading normal there
    t.mask('slope').at(x, y) # any mask (masks.MASKS) at world points, from the finest level holding them
    t.surface.at('crest', x, y)  # any baked surface map (surface.MAPS) at world points
    t.plants.names()         # the planted species; t.plant_objects their Blender objects
    t.viewpoint(target=(0, -3000), distance=1500)   # a standing point that sees the target (not a wall)
    t.preview('<dir>/name')  # hillshade and mask PNGs, to look at before a render

    t = generate('canyon', focus=(x, y))          # everything short of Blender (no object yet) ...
    vp = t.viewpoint(target=(x, y + 900), distance=900)
    t.build(plants='auto', cameras=[vp.eye])      # ... then the object, its surface and its plants

The call, in order: the recipe (a name, a Recipe, a recipe dict or a list of stages) and its knobs are resolved and
checked; the defaults come from the recipe, its DEM (real_place) and the quality; plan_levels lays out the levels
around the focus; the cache is read, or the level runner (terrain/run.py: run_levels) runs the stages and writes
it; the exact flatten pass; the masks; the ring mesh with the masks as point attributes; then, in Blender
(Terrain.build): the object; the surface data bake (terrain/surface: the maps per texel, cached in their own root)
with the plant layer's cover (the plan's, or the ecotope's expected cover with no plan) and the palette's far and
provenance colours; the per-texel material (palette=None: grey clay); lake and sea surfaces; rocks near the focus;
the plants. One summary line is printed, naming any stage whose op is not registered (the runner skips it). The
runner's kernels and the surface bake need Blender's GPU module: run it in Blender.
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
ARGS = ('recipe', 'size', 'resolution', 'seed', 'params', 'focus', 'hero_cell', 'context', 'flatten', 'sea_level',
        'base_elevation_m', 'palette', 'dress', 'quality', 'cache', 'name', 'collection', 'mesh_res', 'surface',
        'plants', 'cameras', 'mask_attributes', 'log')
# plants={...}: what a plan and its instancing take (plants.plan_plants, plant_instances.instance_plants)
PLANT_KEYS = ('ecotope', 'focus', 'radius_m', 'seed', 'exclude', 'stand_m', 'lod', 'wind', 'instance', 'spots')
# the plant layer's cover rasters (surface.maps.MAPS): a palette whose material reads any of them, or that has a
# canopy layer, gets them in its bake with plants or without (SURFACING_DESIGN.md 4.7)
PLANT_MAPS = frozenset(('canopy', 'canopy_expected', 'canopy_far', 'shrubs', 'shrubs_far', 'grass', 'grass_far'))
STAND_M = 1.5            # plants keep their crowns this far off every camera passed that stands near the ground
EYE_CAMERA_M = 50.0      # ... a camera at most this high over the ground at its feet
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
        self.surface = None          # the surface data bake (surface.SurfaceData), once built
        self.plants = None           # the plant layer's spots (plants.PlantSpots), when planted
        self.plant_objects = {}      # {species: [objects]} the instanced plants

    def build(self, name='terrain', collection=None, palette='auto', dress=True, surface='auto', plants=None,
              cameras=None, mask_attributes=True, cache=True, log=print):
        """Everything make_terrain does in Blender, for a Terrain from generate() or Terrain.load(build=False): the
        object, the surface bake, the material, water, rocks and plants (make_terrain's arguments of the same
        names; palette 'keep': the one it was generated or saved with). Build once per Terrain. Returns the
        object."""
        if self.obj is not None:
            raise RuntimeError(f"this Terrain is built already (object {self.obj.name!r}): load or generate it again")
        if palette == 'keep':
            palette = self.info.get('palette', 'auto')
        tb = time.perf_counter()
        _build_blender(self, name, collection, palette, dress, log, surface=surface, plants=plants, cameras=cameras,
                       mask_attributes=mask_attributes, cache=cache)
        self.info.setdefault('seconds', {})['blender'] = round(time.perf_counter() - tb, 2)
        return self.obj

    def bind_sun(self, sun=None):
        """Bind the instanced SeedThree plants to the scene's sun (the leaves' backlight, the sun the billboards cast
        from): call it once the sky and its sun are final (after make_sky). `sun` a sun lamp, default the scene's
        strongest. Returns the lamp, or None when there are no SeedThree plants or no sun."""
        if not any(self.plant_objects.values()):
            return None
        from .build import plant_instances as _pi
        return _pi.bind_sun(sun)

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
        <path>.npz with its description in <path>.json, and its plants' spots (when it has any) beside them in the
        plant layer's format (<path>.plants.json and <path>.plants.<species>.f32). Terrain.load reads it back. The
        surface bake is not written: it is a cache keyed by the terrain (surface.cache_root()), remade when missing."""
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
        if self.plants is not None:
            self.plants.save(base)
            meta['plants_file'] = os.path.basename(base) + '.plants.json'
        else:
            meta.pop('plants_file', None)
        with open(base + '.json', 'w', encoding='utf-8') as f:
            json.dump(_plain(meta), f, indent=1)
        return base + '.npz'

    @classmethod
    def load(cls, path, build=True, name=None, collection=None, palette='keep', dress=False, surface='auto',
             plants='keep', cameras=None, mask_attributes=True, log=print):
        """A Terrain from save(); build=True also makes its object (Terrain.build: palette 'keep' the one it was made
        with; surface, cameras and mask_attributes as make_terrain takes them). plants 'keep': the spots saved beside
        it (instanced when built), none when it was saved without; None: no plants; 'auto' or a dict: planned anew,
        as make_terrain plans them."""
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
        if plants == 'keep':
            plants = None
            if os.path.exists(base + '.plants.json'):
                from .build import plants as _pl
                t.plants = _pl.PlantSpots.load(base, terrain=t)
                plants = {'spots': t.plants}
        if build:
            pal = info.get('palette') if palette == 'keep' else palette
            t.build(name or info.get('name') or 'terrain', collection, pal, dress, surface=surface, plants=plants,
                    cameras=cameras, mask_attributes=mask_attributes, log=log)
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
                 quality='film', cache=True, name='terrain', collection=None, mesh_res=None, surface='auto',
                 plants=None, cameras=None, mask_attributes=True, log=print, **unknown):
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
    cache        read and write eidoverse/assets/cache/terrain/<key> (and the surface bake's and the plants' caches)
    mesh_res     vertices per side each level is drawn at (default 512: about 3.3M triangles for seven levels)
    surface      'auto': the surface data bake (terrain/surface.bake_surface: every map per texel on every level,
                 cached in its own root) and the per-texel material reading it, whenever a palette or the plants read
                 it; True: bake even for clay without plants; a dict: the bake's options (surface/bake.py DEFAULTS);
                 None or False: no bake (the material reads the mesh's mask attributes, the forest its fallback)
    plants       None: no plants (a palette with a canopy layer still gets the ecotope's expected cover in its bake,
                 so its forest stands where the plants would); 'auto': the palette's ecotope planned around the focus
                 (plants.plan_plants, kept in the terrain's cache entry) and instanced for a still shot
                 (plant_instances.instance_plants); a dict of any of: ecotope, focus, radius_m, seed, exclude (the
                 plan's), stand_m (the crowns kept off each camera near the ground, default 1.5 m; 0: none), lod,
                 wind (the instancing's), instance (False: plan and cover only, no objects), spots (a PlantSpots to
                 instance instead of planning)
    cameras      camera objects, (x, y[, z]) points, or arrays of points along a camera path: rings beyond 1.5 D0
                 of all of them take the far material (a cost saving only), and plants keep their crowns stand_m off
                 every one standing within 50 m of the ground
    mask_attributes  True: the eido_<mask> point attributes on the mesh (for agents' own shaders and Geometry Nodes;
                 the per-texel material reads none); False: only eido_level (thirty floats a vertex less)
    """
    t0 = time.perf_counter()
    if unknown:
        k = sorted(unknown)[0]
        raise TypeError(f'make_terrain() got an unexpected keyword {k!r}' + _nearest(k, ARGS))
    if recipe is None:
        raise TypeError('make_terrain needs a recipe: one of ' + ', '.join(_registry.names()))
    if quality not in _levels.QUALITY:
        raise ValueError(f'quality {quality!r}' + _nearest(quality, _levels.QUALITY))
    _check_surface_args(surface, plants, palette, mask_attributes)
    t = generate(recipe, size, resolution, seed or 0, params, focus, hero_cell, context, flatten, sea_level,
                 base_elevation_m, quality, cache, mesh_res, palette, log)
    t.build(name, collection, palette, dress, surface=surface, plants=plants, cameras=cameras,
            mask_attributes=mask_attributes, cache=cache, log=log)
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

def _check_surface_args(surface, plants, palette, mask_attributes):
    """Raise on a surface, plants or mask_attributes argument that cannot work, before any terrain is made."""
    if not (surface in (None, False, True, 'auto') or isinstance(surface, dict)):
        raise ValueError(f"surface={surface!r}: 'auto', True, a dict of bake options, or None")
    _plant_spec(plants)
    if mask_attributes is False and surface in (None, False) and palette is not None:
        raise ValueError('mask_attributes=False with surface=None: the material would have no masks to read (keep '
                         "the attributes, or let the material read the surface bake: surface='auto')")


def _plant_spec(plants):
    """plants= as a dict of PLANT_KEYS, or None for no plants."""
    if plants is None or plants is False:
        return None
    if plants is True or plants == 'auto':
        return {}
    if isinstance(plants, dict):
        bad = set(plants) - set(PLANT_KEYS)
        if bad:
            k = sorted(bad)[0]
            raise KeyError(f'plants: unknown key {k!r}' + _nearest(k, PLANT_KEYS))
        return dict(plants)
    if hasattr(plants, 'species') and hasattr(plants, 'array'):      # a PlantSpots
        return {'spots': plants}
    raise TypeError(f"plants={plants!r}: None, 'auto', a dict ({', '.join(PLANT_KEYS)}) or a PlantSpots")


def _camera_list(cameras):
    """cameras= as a list (a single camera object or point becomes a list of one)."""
    if cameras is None:
        return []
    if hasattr(cameras, 'matrix_world') or (isinstance(cameras, (tuple, list)) and len(cameras) in (2, 3)
                                            and all(isinstance(v, (int, float, np.floating)) for v in cameras)):
        return [cameras]
    if isinstance(cameras, np.ndarray) and cameras.ndim == 1:
        return [cameras]
    return list(cameras)


def _camera_xyz(cameras):
    """(N, 3) world positions of the cameras with a height (camera objects, (x, y, z) points, path arrays); 2-D
    points have none and are left out."""
    pts = []
    for c in _camera_list(cameras):
        if hasattr(c, 'matrix_world'):
            p = c.matrix_world.translation
            pts.append((float(p[0]), float(p[1]), float(p[2])))
            continue
        a = np.asarray(c, np.float64)
        if a.ndim == 2 and a.shape[1] >= 3:
            pts.extend((float(r[0]), float(r[1]), float(r[2])) for r in a)
        elif a.ndim == 1 and a.shape[0] >= 3:
            pts.append((float(a[0]), float(a[1]), float(a[2])))
    return np.asarray(pts, np.float64).reshape(-1, 3)


def _stand_discs(t, cameras, stand_m):
    """(x, y, stand_m, 'crown') discs at the cameras standing within EYE_CAMERA_M of the ground (a path thinned to
    one disc per stand_m): the plan keeps every plant's foot and crown off them (plants.plan_plants' exclude)."""
    if not stand_m or stand_m <= 0:
        return []
    p = _camera_xyz(cameras)
    if not len(p):
        return []
    near = (p[:, 2] - np.asarray(t.height_at(p[:, 0], p[:, 1]), np.float64)) <= EYE_CAMERA_M
    out = []
    for x, y, _z in p[near]:
        if out and math.hypot(x - out[-1][0], y - out[-1][1]) < float(stand_m):
            continue
        out.append((float(x), float(y), float(stand_m), 'crown'))
    return out


def _cover_tag(sd, names):
    """A hash of the plant rasters a palette bake reads (their bytes on every level): the far colour is a function
    of them, so its cache must change when they do."""
    h = hashlib.sha1()
    for nm in sorted(names):
        for i in range(len(sd.levels)):
            a = sd.maps(i).get(nm)
            h.update(nm.encode('utf-8'))
            h.update(b'-' if a is None else np.ascontiguousarray(a, np.float32).tobytes())
    return h.hexdigest()[:12]


def _far_reads(rpal):
    """The names the palette's far colour reads (surface/far_colour.py's kernel: its layers' weights, patches,
    streaks...), or the material's mask reads when that kernel cannot be compiled."""
    from .build import palettes as _pal
    try:
        from .surface import far_colour as _fc
        return set(_fc.kernel_source(rpal)[1])
    except Exception:                                    # noqa: BLE001 - the palette bake reports its own failure
        return set(_pal.material_masks(rpal))


def _plan(t, sd, spec, cameras, cache, log):
    """The plants' spots and their cover rasters (bake_surface's extra form): a given PlantSpots, else the plan kept
    in the terrain's cache entry (plants.cache_base), else a new plan (then kept there)."""
    from .build import plants as _pl
    spots = spec.get('spots')
    if spots is not None:
        spots.attach(t, sd)
        return spots, spots.cover_extra(), 'given'
    ecotope = spec.get('ecotope', 'auto')
    focus = spec.get('focus')
    exclude = spec.get('exclude')
    stand = _stand_discs(t, cameras, spec.get('stand_m', STAND_M))
    if exclude is None and stand:                        # plan_plants' own default (the flats) plus the cameras
        exclude = [(f['at'][0], f['at'][1], float(f.get('radius', 0.0))) for f in t.flats if f.get('radius')]
    if stand:
        exclude = list(exclude) + stand
    kw = dict(focus=focus, radius_m=spec.get('radius_m'), seed=int(spec.get('seed', 0)), data=sd, exclude=exclude)
    base = _pl.cache_base(t, ecotope, **kw) if cache else None
    how = 'planned'
    spots = None
    if base and os.path.exists(base + '.plants.json'):
        try:
            spots = _pl.PlantSpots.load(base, terrain=t, data=sd)
            how = 'cached'
        except (OSError, ValueError, KeyError) as e:
            log(f'[make_terrain] the cached plan does not load ({e}): planning again')
    if spots is None:
        spots = _pl.plan_plants(t, ecotope, log=log, **kw)
        if base:
            spots.save(base)
    cover = None
    if base and os.path.exists(base + '.cover.npz') and how == 'cached':
        with np.load(base + '.cover.npz', allow_pickle=False) as z:
            names = sorted({k.rsplit('_L', 1)[0] for k in z.files})
            cover = {k: [np.asarray(z[f'{k}_L{i}']) for i in range(len(t.levels))] for k in names}
    if cover is None:
        cover = spots.cover_extra()
        if base:
            np.savez_compressed(base + '.cover.npz', **{f'{k}_L{i}': v for k, per in cover.items()
                                                       for i, v in enumerate(per)})
    return spots, cover, how


def _bake_and_plant(t, pal, surface, spec, cameras, cache, log):
    """The surface data with the plant layer's cover and the palette's colours: (SurfaceData, PlantSpots or None).

    Order: the maps first (bake_surface with the palette's constants, which name the bake, and no palette bake),
    then the plan or the ecotope's expected cover on those maps (densities read the bake's crest, settle, snowpack
    ...), added to the data, then the palette bake (the far colour C reads the cover through the forest and scrub
    weights), keyed by the cover it read, then the M packing of the palette's material."""
    from . import surface as _sf
    from .build import palettes as _pal
    from .surface import bake as _sb
    rpal = _sb.resolve_palette(t, pal) if pal is not None else None
    opts = _sb.resolve_options(t, rpal, dict(surface) if isinstance(surface, dict) else None)
    sd = _sf.bake_surface(t, palette=None, options=opts, cache=cache, log=log)   # the same key as with the palette
    spots, cover, how = None, None, None
    reads = set()
    if rpal is not None:
        reads = _pal.material_masks(rpal) & PLANT_MAPS
        if any(L.get('canopy') for L in rpal['layers']):
            reads |= {'canopy_expected', 'canopy_far'}
    if spec is not None:
        t0 = time.perf_counter()
        spots, cover, how = _plan(t, sd, spec, cameras, cache, log)
        t.info['seconds']['plants_plan'] = round(time.perf_counter() - t0, 2)
    elif reads:
        from .build import plants as _pl
        t0 = time.perf_counter()
        cover = _pl.expected_cover(t, data=sd)
        how = 'expected'
        t.info['seconds']['plants_cover'] = round(time.perf_counter() - t0, 2)
    if cover:
        sd.add_maps(cover)
    rec = dict(key=str(sd.key), cache_hit=bool(sd.info.get('cache_hit')), cover=how,
               cover_maps=sorted(cover) if cover else [])
    if rpal is not None:
        sd.pack(sorted(_pal.material_masks(rpal)))
        if opts.get('maps', 'all') == 'all':
            pk = rpal
            far = _far_reads(rpal) & set(cover or ())
            if far:
                pk = dict(rpal, plant_cover=_cover_tag(sd, far))
            try:
                sd.bake_palette(pk, cache=sd.cache_dir, log=log)
            except (ValueError, KeyError, TypeError, RuntimeError) as e:
                # the material then reads no far colour (C) and no provenance colour (P): the ground keeps its
                # near look to the horizon, and sediment its debris' own column colour
                rec['palette_bake'] = f'failed: {type(e).__name__}: {e}'
                log(f"[make_terrain] the palette bake failed ({type(e).__name__}: {e}): no far colour")
        rec.setdefault('palette_bake', sd.info.get('palette_bake'))
    t.info['surface'] = rec
    return sd, spots


def _anisotropy_16(log):
    """16x anisotropic filtering, which the per-texel material's reader needs (SURFACING_DESIGN.md 2.4: a GPU
    texture keeps the filter it was made with, so it is set before any image is drawn). A session preference: the
    saved preferences keep the user's own."""
    import bpy
    prefs = bpy.context.preferences
    if prefs.system.anisotropic_filter == 'FILTER_16':
        return
    dirty = prefs.is_dirty
    old = prefs.system.anisotropic_filter
    prefs.system.anisotropic_filter = 'FILTER_16'
    try:
        prefs.is_dirty = dirty
    except (AttributeError, TypeError):
        pass
    log(f'[make_terrain] anisotropic filtering {old} -> FILTER_16 for this session (the terrain\'s atlases need it)')


def _surface_record(sd):
    """What terrain_surface(obj) relinks from: the bake's key, the terrain's, where its atlas files were, and each
    family's file name."""
    from .surface import bake as _sb
    files = {}
    for fam in sd.families():
        try:
            files[fam] = os.path.basename(sd.image_path(fam))
        except (KeyError, ValueError):
            continue
    return dict(key=str(sd.key), terrain_key=_sb.terrain_key(sd.terrain), cache_dir=sd.cache_dir, files=files,
                palette_bake=sd.info.get('palette_bake'))


def _build_blender(t, name, collection, palette, dress, log, surface='auto', plants=None, cameras=None,
                   mask_attributes=True, cache=True):
    from .build import water as _water
    _check_surface_args(surface, plants, palette, mask_attributes)
    spec = _plant_spec(plants)
    info = t.info
    info['name'] = name
    secs = info.setdefault('seconds', {})
    pal = palette
    if palette == 'auto' and info.get('place'):
        pal = info.get('palette') or 'auto'
    info['palette'] = pal                                 # the ecotope 'auto' reads it
    strata = None
    if info.get('place'):
        from .build import palettes as _pal
        strata = (_pal.PLACES.get(info['place']) or {}).get('strata')
    obj = _mesh.make_object(t.ring, name, collection, mask_attributes=bool(mask_attributes))
    t.obj = obj
    obj['trimesh_collider'] = True
    obj['eido_terrain'] = json.dumps(_plain(dict(
        recipe=t.recipe.to_dict(), knobs=t.knobs, seed=info['seed'], size=info['size'],
        resolution=info['resolution'], quality=info['quality'], focus=info['focus'],
        plan=[lv.to_dict() for lv in t.levels], cache_key=info['cache_key'], flats=t.flats,
        sea_level=info['sea_level'], base_elevation_m=info['base_elevation_m'], api_version=API_VERSION)))
    obj['eido_terrain_mesh'] = json.dumps(t.ring.layout())
    # the surface data and the plants' plan (the plan reads the bake's maps; the bake holds the plan's cover)
    bake = surface is True or isinstance(surface, dict) or (surface == 'auto' and (pal is not None or spec is not None))
    sd = spots = None
    if bake:
        ts = time.perf_counter()
        sd, spots = _bake_and_plant(t, pal, surface, spec, cameras, cache, log)
        secs['surface'] = round(time.perf_counter() - ts, 2)
    elif spec is not None:                               # plants on the masks alone (no bake)
        ts = time.perf_counter()
        spots, _cover, how = _plan(t, None, spec, cameras, cache, log)
        info['plants_cover'] = how
        secs['plants_plan'] = round(time.perf_counter() - ts, 2)
    t.surface = sd
    t.plants = spots
    # the material
    from .build import surfacing as _surf
    tm = time.perf_counter()
    if pal is None:
        obj.data.materials.append(_surf.clay_material(name + '_clay'))
    else:
        if sd is not None:
            _anisotropy_16(log)
        _surf.apply_surface(obj, palette=pal, recipe=t.recipe, strata=strata, log=log, data=sd,
                            cameras=_camera_list(cameras) if sd is not None else None)
    secs['material'] = round(time.perf_counter() - tm, 2)
    if sd is not None:
        obj['eido_surface'] = json.dumps(_plain(_surface_record(sd)))
    # water
    lakes = _water.lake_objects(t, name=name + '_lake', collection=collection)
    sea = (_water.sea_object(t, info['sea_level'], name=name + '_sea', collection=collection)
           if info.get('sea_level') is not None else None)
    t.water = {'lakes': lakes, 'sea': sea}
    # rocks near the focus
    if dress and info.get('focus') and pal is not None:
        try:
            from .build import dressing as _dress
            from .build import palettes as _pal
            dspec = _pal.get(pal, t.recipe).get('dressing')
        except (ImportError, KeyError, ValueError) as e:
            log(f'[make_terrain] no rocks: {e}')
            dspec = None
        if dspec:
            fx, fy = np.mean(np.asarray(info['focus'], np.float64), axis=0)

            def mask_at(nm, x, y):
                if nm in t.masks:
                    return t.masks[nm].at(x, y)
                if sd is not None and sd.has(nm):             # a baked map (the toe bias reads grain)
                    return sd.at(nm, x, y)
                return None
            exclude = [(f['at'][0], f['at'][1], float(f.get('radius', 0.0))) for f in t.flats if f.get('radius')]
            t.rocks = _dress.scatter_rocks(dspec, mask_at=mask_at, height_at=t.height_at, normal_at=t.normal_at,
                                           focus=(float(fx), float(fy)), seed=info['seed'], name=name + '_rocks',
                                           collection=collection, exclude=exclude, log=log)
    # the plants, instanced for the shot
    if spots is not None and spec.get('instance', True):
        from .build import plant_instances as _pi
        ti = time.perf_counter()
        t.plant_objects = _pi.instance_plants(spots, t, collection=collection, lod=spec.get('lod'),
                                              cache=bool(cache), wind=bool(spec.get('wind', False)), log=log)
        secs['plants_instance'] = round(time.perf_counter() - ti, 2)
    if spots is not None:
        info['plants'] = dict(ecotope=spots.meta.get('ecotope'), counts={n: spots.count(n) for n in spots.names()},
                              focus=spots.meta.get('focus'))
    return obj


def _summary(t, log):
    i = t.info
    lv = t.levels
    s = i['seconds']
    parts = ', '.join(f'{k} {v}' for k, v in s.items() if k not in ('total', 'generate'))
    skipped = f"; stages skipped (no op of that name is registered): {', '.join(i['skipped_stages'])}" \
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
    """Print (and return) a recipe's stages, knobs (unit, default, range, what each does) and references, with any
    stage whose op is not registered marked."""
    R = _registry.resolve(recipe)
    text = R.describe()
    missing = [s.op for s in R.stages if not _registry.has_op(s.op)]
    if missing:
        text += '\n  ops not registered (the runner skips these stages): ' + ', '.join(dict.fromkeys(missing))
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
    ring = _mesh.rebuild(json.loads(obj['eido_terrain_mesh']), _mesh.read_vertices(obj))
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


def _material_images(obj):
    """The surface atlas images a terrain object's materials read (Image Texture nodes, node groups included):
    {image name: image} of the images the surface bake made (they carry eido_family)."""
    seen, out = set(), {}

    def walk(nt):
        if nt is None or nt.name in seen:
            return
        seen.add(nt.name)
        for nd in nt.nodes:
            if nd.bl_idname == 'ShaderNodeTexImage' and nd.image is not None and nd.image.get('eido_family'):
                out[nd.image.name] = nd.image
            elif nd.bl_idname == 'ShaderNodeGroup':
                walk(nd.node_tree)
    for m in obj.data.materials:
        if m is not None and m.use_nodes:
            walk(m.node_tree)
    return out


def terrain_surface(obj, folder=None):
    """The surface bake's atlas images of a terrain object after its .blend is reopened, relinked (as
    terrain_height_at rebuilds height_at): every atlas the object's materials read is found where its file is
    (its own path, else `folder`, the .blend's folder, the bake's cache folder, then the surface cache's root for
    the object's terrain) and reloaded from there. The LUT and strata images are packed in the .blend and need
    nothing. Before moving a .blend to another machine, copy the files beside it: t.surface.save_images(folder).
    Returns the object's record (key, terrain_key, cache_dir, files, palette_bake) with images {family: path}.
    Raises FileNotFoundError naming the files it could not find (make_terrain with the same arguments bakes them
    again)."""
    import bpy
    raw = obj.get('eido_surface')
    if raw is None:
        raise ValueError(f"'{obj.name}' has no surface bake (no eido_surface property: made with surface=None, or "
                         f"not by make_terrain)")
    rec = json.loads(raw)
    from . import surface as _sf
    places = [folder, bpy.path.abspath('//') if bpy.data.filepath else None, rec.get('cache_dir'),
              os.path.join(_sf.cache_root(), str(rec.get('terrain_key') or ''))]
    places = [p for p in places if p]
    images, missing = {}, []
    for img in _material_images(obj).values():
        fam = str(img.get('eido_family'))
        path = bpy.path.abspath(img.filepath) if img.filepath else ''
        if path and os.path.exists(path):
            images[fam] = path
            continue
        base = os.path.basename(path.replace('\\', '/')) or rec.get('files', {}).get(fam, '')
        hit = next((os.path.join(p, base) for p in places if base and os.path.exists(os.path.join(p, base))), None)
        if hit is None:
            missing.append(base or img.name)
            continue
        img.filepath = hit
        img.reload()
        images[fam] = hit
    if missing:
        raise FileNotFoundError(f"'{obj.name}': surface atlas files not found ({', '.join(missing)}) in "
                                f"{', '.join(places)}; make_terrain with the same arguments bakes them again, and "
                                f"t.surface.save_images(folder) keeps copies beside a .blend")
    return dict(rec, images=images)


place_camera = _place_camera

__all__ = ['make_terrain', 'generate', 'Terrain', 'MaskSet', 'Mask', 'Viewpoint', 'recipes', 'describe',
           'terrain_height_at', 'terrain_surface', 'flatten_fields', 'place_camera', 'PLANT_KEYS', 'PLANT_MAPS']
