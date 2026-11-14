"""eidoblend.terrain.surface: the surface data bake (SURFACING_DESIGN.md 2.2, 2.3, 2.6, 2.7). A terrain's fields and
masks turned into maps per texel, packed into one atlas image per kind, for the material, the looks and the plants.

    from eidoblend.terrain.surface import bake_surface, SurfaceData, MAPS
    sd = bake_surface(t, palette='auto')        # t: a Terrain (api.generate, make_terrain, Terrain.load)
    sd.maps('main')                             # {name: float32 array} of a level (index or role), physical units
    sd.at('crest', x, y)                        # bilinear on the finest level holding each point (like MaskSet.at)
    sd.pack(names)                              # put these maps in the M atlases (the material's and plants' reads)
    sd.channel('settle')                        # ('M0', 2, ('affine', 1.0, 0.0)): family, channel(s), decode rule
    sd.layouts                                  # {family: Layout}: per level the atlas tile, its UV rectangle, texel
    sd.images()                                 # {family: bpy Image} (Blender): D, E, M0.., F, C, P
    sd.save_images(folder)                      # OpenEXR (D, F) and PNG (the rest); the images then read the files
    MAPS['settle'].doc                          # the registry (maps.py): every map's unit, family, encoding, meaning

bake_surface(terrain, palette=None, options=None, cache=True, extra=None)
    palette   None, 'auto', a name or a palette dict: its terrain constants (snowline, sun, wind) steer the snowpack,
              insolation and streaks, and with one the palette bake adds the far colour (C) and the provenance
              colour (P). None: the terrain's own constants and palettes.CONSTANTS, and no C or P.
    options   bake settings (bake.DEFAULTS): {'maps': 'masks'} packs the existing masks and the field normal only
              (no new kernels: what a material needs to read atlases at all); 'detail': 1 puts D and E at the cell.
    cache     True: the surface cache's own root (cache_root(): EIDO_SURFACE_CACHE, else
              <repo>/eidoverse/assets/cache/terrain_surface/), <root>/<terrain key>/surface_<bake key>_L<i>.npz and
              the atlas files beside them, one bake per terrain key, whole keys pruned past 8 GB; a folder path:
              there; False: in memory (the atlas files then go to a temporary folder).
    extra     {'canopy': [array per level], ...}: the plant layer's rasters, stored as M maps.

The bake runs on the GPU in Blender (core/gpu.py, the kernels in surface/kernels/) and through the numpy twins in
plain Python (surface/twins.py; for small grids). Levels run coarsest first; every map's outer 16 cells are pinned
to its parent's (masks.pin_band), and each atlas tile's gutter holds the coarser levels' maps at its own positions,
so one read per kind meets the next level with no seam.

What a reader must know (the material, the looks, the plants):
- Arrays are [row j, column i], row 0 south, texel centres at x0 + (i + 0.5) texel (the masks' frame). The detail
  maps (D, E) are at half the cell on the main and hero levels of at most 1024 cells (maps(level)[name].shape says).
- `flow`, `wetness` and `channels` on hero levels come from the bake's own routing (the parent's catchment pinned in
  across the border); elsewhere they are the masks'.
- `settle` is 0.5 on ground where the layer stayed (flat), toward 0 where it shed, toward 1 where it gathered.
- `src_strata` is metres of stratigraphic height (the masks' `strata` frame); the F atlas holds it, and `strata`,
  less the pixel's own height and a per-level reference: decode ('z_plus', 1, refs) = object z + refs[level] + texel.
- The unsuffixed curvatures' decode differs per level (their scale is 2 x the level's cell): decode rules with
  tuples hold one number per level, folded in with the level's other constants.
"""
from __future__ import annotations

import glob
import json
import math
import os
import time

import numpy as np

from . import atlas as AT
from . import maps as MP
from .maps import MAPS

F32 = np.float32
DETAIL_CAP = 2048                   # texels per level side, D and E
CELL_CAP = 1024                     # M, F, C, P
KEEP_BAKES = 1                      # surface bakes kept per terrain key (a new bake replaces the old)
# what a channel holds where its map is absent from a level (the open sky of cavity, a toe's coarse grain)
NEUTRAL = {'cavity': 1.0, 'grain': 1.0, 'settle': 0.5, 'valley': 0.5}
_FAMILY_ORDER = ('D', 'E', 'F', 'C', 'P')


def _level_index(levels, level):
    if isinstance(level, (int, np.integer)):
        return int(level) % len(levels)
    if hasattr(level, 'index'):
        return int(level.index)
    roles = [lv.role for lv in levels]
    if level == 'first':
        return 0
    if level == 'last':
        return len(levels) - 1
    if level in ('main', 'context', 'hero'):
        hit = [i for i, r in enumerate(roles) if r == level]
        if not hit:
            raise KeyError(f'no {level} level in this terrain ({roles})')
        return hit[-1] if level != 'context' else hit[0]
    raise KeyError(f"level {level!r}: an index, a Level, or 'main' | 'context' | 'hero' | 'first' | 'last'")


def _masks_of(terrain, i):
    ms = terrain.masks
    return ms.level(i) if hasattr(ms, 'level') else ms[i]


def _fields_of(terrain, i):
    f = terrain.fields
    return f(i) if callable(f) else f[i]


# ---------------------------------------------------------------------------------------------- the data ---

class SurfaceData:
    """A terrain's baked surface maps: per level {name: array}, the atlas layouts, the M packing, and (in Blender)
    the images. Made by bake_surface."""

    def __init__(self, terrain, baked, info, options, key, palette=None, colour=None, cache_dir=None):
        from . import bake as B
        self.terrain = terrain
        self.levels = list(terrain.levels)
        self.key = key
        self.options = dict(options)
        self.info = dict(info or {})
        self.palette = palette
        self.cache_dir = cache_dir
        # a level's bake: a dict of arrays, or the path of its cached .npz, loaded on first use
        self._baked = [m if isinstance(m, (str, os.PathLike)) else dict(m) for m in baked]
        self._colour = [dict(c) for c in colour] if colour else None
        self._colour_tag = None
        self._extra = {}
        self._packing = None
        self._images = {}
        self._memo = {}
        self._atlas_code = None
        self.factors = [B.detail_factor(lv, self.options) for lv in self.levels]
        n_det = [AT.texel_count(lv, f, DETAIL_CAP) for lv, f in zip(self.levels, self.factors)]
        n_cell = [AT.texel_count(lv, 1, CELL_CAP) for lv in self.levels]
        self._grid_layouts = {'detail': AT.layout(self.levels, n_det, 'detail'),
                              'cell': AT.layout(self.levels, n_cell, 'cell')}
        refs = self.info.get('refs')
        self.refs = {k: list(v) for k, v in refs.items()} if refs else self._references()

    def __repr__(self):
        lv = self.levels
        return (f"SurfaceData({len(lv)} levels, {len(self.names())} maps, key {self.key[:10]}, "
                f"{'with' if self._colour else 'no'} palette colour)")

    # ---- what there is
    def _baked_level(self, i):
        b = self._baked[i]
        if isinstance(b, (str, os.PathLike)):
            cell = float(self.levels[i].cell)
            with np.load(b, allow_pickle=False) as z:
                b = _level_maps(z, cell)
            self._baked[i] = b
        return b

    def _names(self, i):
        """The names level i holds, without loading its arrays."""
        b = self._baked[i]
        own = set(self.info['names'][i]) if (isinstance(b, (str, os.PathLike)) and self.info.get('names')) \
            else {k for k in self._baked_level(i) if not k.startswith('_')}
        out = set(_masks_of(self.terrain, i)) | own
        out |= {k for k, per in self._extra.items() if per[i] is not None}
        if self._colour:
            out |= set(self._colour[i])
        if 'src_dz' in out:
            out.add('src_strata')
        if 'slope' in out and 'aspect' in out:
            out.add('insolation')
        if 'n20_x' in out and 'n20_y' in out:
            out.add('slope_20m')
        return out

    def names(self, level=None):
        """The map names a level holds (default: the finest), the shader-derived ones included."""
        i = len(self.levels) - 1 if level is None else _level_index(self.levels, level)
        return sorted(self._names(i))

    def has(self, name):
        if name in MP.PAIRS:
            return all(self.has(n) for n in MP.PAIRS[name])
        return name in self._names(len(self.levels) - 1)

    def maps(self, level):
        """{name: float32 array} of one level (an index or a role), physical units (maps.MAPS): the masks, the bake's
        maps (they replace the masks' flow, wetness and channels on hero levels), the plant rasters given to
        add_maps, the palette bake's colours, and the derived names src_strata, insolation (and the masks' slope,
        aspect, northness, eastness, height). Arrays are shared, not copies: do not write into them."""
        i = _level_index(self.levels, level)
        hit = self._memo.get(i)
        if hit is not None:
            return dict(hit)
        out = {}
        for k, v in _masks_of(self.terrain, i).items():
            out[k] = v
        out.update({k: v for k, v in self._baked_level(i).items() if not k.startswith('_')})
        for k, per in self._extra.items():
            if per[i] is not None:
                out[k] = per[i]
        if self._colour:
            out.update(self._colour[i])
        if 'src_dz' in out and 'h' not in out:
            h = np.asarray(_fields_of(self.terrain, i)['h'], np.float64)
            out['src_strata'] = (h + out['src_dz']).astype(F32)
        if 'slope' in out and 'aspect' in out:
            out['insolation'] = self._insolation(out)
        if 'n20_x' in out and 'n20_y' in out:
            nxy2 = np.minimum(out['n20_x'] * out['n20_x'] + out['n20_y'] * out['n20_y'], F32(0.9999))
            out['slope_20m'] = np.degrees(np.arctan(np.sqrt(nxy2 / (F32(1) - nxy2)))).astype(F32)
        self._memo[i] = out
        return dict(out)

    def _insolation(self, m):
        az = math.radians(float(self.options.get('sun_azimuth_deg') or 180.0))
        el = math.radians(float(self.options.get('sun_elevation_deg') or 45.0))
        s = np.radians(np.asarray(m['slope'], F32))
        a = np.radians(np.asarray(m['aspect'], F32))
        v = (np.sin(s) * (np.sin(a) * math.sin(az) + np.cos(a) * math.cos(az)) * math.cos(el)
             + np.cos(s) * math.sin(el))
        return np.maximum(v, 0.0).astype(F32)

    def at(self, name, x, y):
        """A map at world (x, y): bilinear on the finest level whose window holds each point (MaskSet.at's rule).
        Floats or arrays; a level lacking the map is skipped."""
        x = np.asarray(x, np.float64)
        y = np.asarray(y, np.float64)
        x, y = np.broadcast_arrays(x, y)
        out = np.zeros(x.shape, np.float64)
        done = np.zeros(x.shape, bool)
        for i in range(len(self.levels) - 1, -1, -1):
            a = self.maps(i).get(name)
            if a is None:
                continue
            lv = self.levels[i]
            m = (~done & lv.contains(x, y)) if i else ~done
            if m.any():
                texel = lv.side / a.shape[0]
                out[m] = AT.sample_bilinear(a, lv.x0, lv.y0, texel, x[m], y[m])
                done |= m
        if not done.all() and not any(name in self.maps(i) for i in range(len(self.levels))):
            raise KeyError(f'no surface map {name!r}; there are: {", ".join(self.names())}')
        return float(out) if out.ndim == 0 else out

    def add_maps(self, extra):
        """Add rasters per level ({'canopy': [array or None per level], ...}): M maps of the registry (the plant
        layer's), each (n, n) on its level's cells. Clears any M images made before."""
        for k, per in (extra or {}).items():
            MP.spec(k)
            per = list(per)
            if len(per) != len(self.levels):
                raise ValueError(f'extra map {k!r}: {len(per)} arrays for {len(self.levels)} levels')
            self._extra[k] = [None if a is None else np.asarray(a, F32) for a in per]
        self._memo.clear()
        for fam in [f for f in self._images if f.startswith('M')]:
            self._images.pop(fam)
        return self

    # ---- layouts and channels
    @property
    def layouts(self):
        """{family: Layout} for every family the data holds (D, E on the detail grid; M0.., F, C, P on the cell
        grid), plus 'detail' and 'cell'. Layout.tiles[i].rect(layout) is level i's (u0, v0, du, dv)."""
        out = dict(self._grid_layouts)
        for fam in self.families():
            out[fam] = self._grid_layouts['detail' if fam in ('D', 'E') else 'cell']
        return out

    def reader_constants(self):
        """What a material's reader folds in per level (SURFACING_DESIGN.md 2.4): {'detail': [...], 'cell': [...]},
        each a list by level of dict(x0, y0, side, texel, u0, v0, du, dv): the level's window (world metres), its
        texel on that layout and its data rectangle in the atlas' UV (u = u0 + du (x - x0) / side). D and E read
        the 'detail' layout, every other family the 'cell' one."""
        out = {}
        for g, lay in self._grid_layouts.items():
            out[g] = [dict(x0=t.x0, y0=t.y0, side=t.side, texel=t.texel, **dict(zip(('u0', 'v0', 'du', 'dv'),
                                                                                     t.rect(lay))))
                      for t in lay.tiles]
        return out

    def families(self):
        """The families the data holds now: D, E, F, C, P as present, and M0..Mk of the current packing."""
        have = self._names(len(self.levels) - 1)
        out = []
        for fam in _FAMILY_ORDER:
            chans = MP.FAMILIES[fam]['channels']
            if fam == 'F':
                if 'strata' in have or 'src_dz' in have:
                    out.append(fam)
            elif any(c is not None and c in have for c in chans):
                out.append(fam)
        out += [f'M{k}' for k in range(len(self.packing()))]
        return out

    def packing(self):
        """The M atlases: [[map, ...] (up to four), ...]. Set by pack(); by default the palette's mask reads (when
        the bake had a palette) or every M map present."""
        if self._packing is None:
            names = None
            if self.palette is not None:
                try:
                    from ..build import palettes as P
                    names = sorted(P.material_masks(self.palette))
                except Exception:                         # noqa: BLE001 - a palette the look package is changing
                    names = None
            if names is None:
                names = [k for k in self._names(len(self.levels) - 1) if self._is_m(k)]
            self.pack(names)
        return self._packing

    def _is_m(self, name):
        try:
            return MP.spec(name).family == 'M'
        except KeyError:
            return False

    def pack(self, names):
        """Put these maps (and only these) in the M atlases, four to an image: the maps a material and the plant
        layer read. Pair names ('n20') take both channels side by side; names that are not M maps, or that the data
        lacks, are left out (the material reads those through other families or as 0). Returns {name: (family,
        channel)}. Clears the M images made before."""
        have = self._names(len(self.levels) - 1)
        want = []
        for nm in names:
            for n in (MP.PAIRS.get(nm) or (nm,)):
                if n not in want and self._is_m(n) and n in have:
                    want.append(n)
        want = sorted(want)
        groups, cur = [], []
        for n in want:                                   # a pair stays in one image
            pair = MP.spec(n).pair
            if pair is not None and pair in want and want.index(pair) < want.index(n):
                continue
            unit = [n] + ([pair] if pair is not None and pair in want else [])
            if len(cur) + len(unit) > 4:
                groups.append(cur)
                cur = []
            cur += unit
        if cur:
            groups.append(cur)
        self._packing = groups
        for fam in [f for f in self._images if f.startswith('M')]:
            self._images.pop(fam)
        return {n: (f'M{k}', c) for k, g in enumerate(groups) for c, n in enumerate(g)}

    def channel(self, name):
        """(family, channel, decode) of a map: the image family ('D', 'E', 'M0'.., 'F', 'C', 'P'), the channel index
        (a tuple for a pair or a colour), and maps.decode_rule's (kind, a, b), a and b tuples with one number per
        level where they differ by level. The shader-derived names (slope, aspect, northness, eastness, height,
        insolation) give ('shader', None, None): the material derives them from D and the object z. Raises KeyError
        for a map the data does not hold (the material then keeps its Attribute path, which reads 0)."""
        if name in MP.PAIRS:
            parts = [self.channel(n) for n in MP.PAIRS[name]]
            fams = {p[0] for p in parts}
            if len(fams) != 1:
                raise KeyError(f'{name!r}: its channels are in different images ({parts})')
            return parts[0][0], tuple(p[1] for p in parts), parts[0][2]
        s = MP.spec(name)
        if s.family == 'shader':
            return ('shader', None, None)
        cells = [float(lv.cell) for lv in self.levels]
        if s.family == 'M':
            for k, g in enumerate(self.packing()):
                if name in g:
                    return (f'M{k}', g.index(name), MP.decode_rule(s, cells))
            raise KeyError(f'surface map {name!r} is not in the M atlases (pack() it; packed: '
                           f'{", ".join(n for g in self.packing() for n in g)})')
        if not self.has(name if s.family != 'F' else ('src_dz' if name == 'src_strata' else name)):
            raise KeyError(f'surface map {name!r} is not in this bake (maps: {", ".join(self.names())})')
        refs = self.refs.get(name, [0.0] * len(self.levels))
        return (s.family, s.channel, MP.decode_rule(s, cells, refs))

    def _references(self):
        """The F family's per-level references (metres): the median of each map's height above the ground."""
        out = {}
        for nm, src in (('strata', 'strata'), ('src_strata', 'src_dz')):
            per = []
            for i in range(len(self.levels)):
                dz = self._dz(i, src)
                per.append(0.0 if dz is None else float(np.round(np.median(dz), 1)))
            out[nm] = per
        return out

    def _dz(self, i, src):
        m = self.maps(i)
        if src == 'src_dz':
            return m.get('src_dz')
        if 'strata_dz' in m:
            return m['strata_dz']
        if 'strata' in m:
            h = np.asarray(_fields_of(self.terrain, i)['h'], np.float64)
            return (np.asarray(m['strata'], np.float64) - h).astype(F32)
        return None

    # ---- the atlases
    def family_maps(self, fam):
        """The four channel names of a family (None for an unused channel)."""
        if fam.startswith('M'):
            g = self.packing()[int(fam[1:])]
            return list(g) + [None] * (4 - len(g))
        return list(MP.FAMILIES[fam]['channels'])

    def tile(self, fam, level, out=None):
        """Level `level`'s tile of a family: (size, size, 4) float32, as the image stores it (encoded), its gutter
        filled from the coarser levels' maps at the gutter texels' own positions (the outermost level edge-extended).
        out: a (size, size, 4) view to fill (the atlas' own pixels) instead of a new array."""
        i = _level_index(self.levels, level)
        t = self.layouts[fam].tiles[i]
        if out is None:
            out = np.zeros((t.size, t.size, 4), F32)
        g, n = t.gutter, t.n
        if fam in ('C', 'P'):
            key = 'far_colour' if fam == 'C' else 'down_colour'
            alpha = 'far_roughness' if fam == 'C' else 'down_share'
            chans = [(key, 0), (key, 1), (key, 2), (alpha, None)]
        else:
            chans = []
            for nm in self.family_maps(fam):
                src = None if nm is None else ('src_dz' if (fam == 'F' and nm == 'src_strata') else
                                               ('strata_dz' if (fam == 'F' and nm == 'strata') else nm))
                chans.append((src, None) if nm is not None else (None, None))
        names = self.family_maps(fam) if fam not in ('C', 'P') else [None] * 4
        full = np.empty((t.size, t.size), F32)
        for c, (src, ch) in enumerate(chans):
            if src is None:
                out[..., c] = 0.0
                continue
            full[g:g + n, g:g + n] = self._channel_array(i, src, n, ch)
            for rows, cols, ys, xs in _strips(t):
                full[rows, cols] = self._gutter(i, src, xs, ys, ch)
            if fam in ('C', 'P'):
                out[..., c] = _linear_to_srgb(full) if c < 3 else full
            else:
                out[..., c] = self._encode(fam, names[c], full, i)
        return out

    def _gutter(self, i, name, xs, ys, ch=None):
        """A map on the lattice xs (columns) x ys (rows) of world points beyond level i's window: bilinear on the
        parent (separable, clamped to its outermost texel centres) at every point inside the parent's window, on the
        grandparent at points beyond that, ..., the outermost level clamped (edge extension; level 0 reads itself
        so). (A window 16 parent cells in has its gutter's last texel centres a quarter cell past the parent's last
        ones: still the parent's, never a coarser level's, next to the window.)"""
        src = [0] if i == 0 else list(range(i - 1, -1, -1))
        out, need = None, None
        for k in src:
            a = self._array(k, name)
            if a is None:
                return np.full((len(ys), len(xs)), NEUTRAL.get(name, 0.0), F32)
            if ch is not None:
                a = a[..., ch]
            lv = self.levels[k]
            vals = AT.sample_lattice(a, lv.x0, lv.y0, lv.side / a.shape[0], xs, ys)
            if k == 0:
                m = np.ones(vals.shape, bool)
            else:
                m = (((ys >= lv.y0) & (ys <= lv.y1))[:, None]) & (((xs >= lv.x0) & (xs <= lv.x1))[None, :])
            if out is None:
                out, need = vals, ~m
            else:
                out = np.where(need & m, vals, out)
                need &= ~m
            if not need.any():
                break
        return out

    def _array(self, i, name):
        """A map of level i as physical values (the F family's metres above the ground for strata_dz)."""
        if name == 'strata_dz':
            return self._dz(i, 'strata')
        m = self.maps(i)
        a = m.get(name)
        if a is None:
            return None
        return np.asarray(a, F32)

    def _channel_array(self, i, name, n, ch=None):
        a = self._array(i, name)
        if a is None:
            v = NEUTRAL.get(name, 0.0)
            return np.full((n, n), v, F32)
        if ch is not None:
            a = a[..., ch]
        return AT.resample(a, n)

    def _encode(self, fam, nm, a, i):
        s = MP.spec(nm)
        if fam == 'F':
            return (np.asarray(a, np.float64) - self.refs[nm][i]).astype(F32)
        return MP.encode(s, a, float(self.levels[i].cell))

    def atlas(self, fam):
        """The family's atlas array (H, W, 4) float32, as the image stores it."""
        lay = self.layouts[fam]
        out = np.zeros((lay.height, lay.width, 4), F32)
        for t in lay.tiles:
            x0, y0, x1, y1 = t.pixels()
            self.tile(fam, t.level, out=out[y0:y1, x0:x1])
        return out

    def images(self, names=None):
        """{family: Image} (Blender): one atlas image per family, named eido_surf_<key>_<family>. names: pack these
        maps into the M atlases first (pack()). Made once per family; pack() and add_maps() clear the M ones."""
        if names is not None:
            self.pack(names)
        fams = self.families()
        for fam in fams:
            if fam in self._images:
                try:
                    self._images[fam].name                # a removed image raises ReferenceError
                    continue
                except ReferenceError:
                    pass
            base = 'M' if fam.startswith('M') else fam
            spec = MP.FAMILIES[base]
            t0 = time.perf_counter()
            path = self.image_path(fam)
            made = False
            if not os.path.exists(path):
                AT.write_image(path, self.atlas(fam), spec['format'])
                made = True
                self._prune_images(fam, path)
            img = AT.load_image(path, f'eido_surf_{self.key[:8]}_{fam}', spec['format'], spec['colorspace'])
            img['eido_family'] = fam
            img['eido_maps'] = json.dumps(self.family_maps(fam))
            self.info.setdefault('image_seconds', {})[fam] = dict(seconds=round(time.perf_counter() - t0, 3),
                                                                 made=made)
            self._images[fam] = img
        return {f: self._images[f] for f in fams}

    def image_path(self, fam):
        """Where a family's atlas file is kept: beside the bake in its cache folder (else a temporary folder), named
        by the bake key and, for an M atlas, by the maps it holds, for C and P by the palette."""
        import hashlib
        import tempfile
        from . import bake as B
        folder = self.cache_dir or os.path.join(tempfile.gettempdir(), 'eido_surface', self.key[:16])
        base = 'M' if fam.startswith('M') else fam
        ext = '.exr' if MP.FAMILIES[base]['is_float'] else '.png'
        if self._atlas_code is None:
            self._atlas_code = B.code_hash(B.ATLAS_CODE)[:8]
        tag = f'{fam}_a{self._atlas_code}' if base != 'M' else ''
        if base == 'M':
            tag = 'M' + hashlib.sha1(','.join(n or '-' for n in self.family_maps(fam)).encode()).hexdigest()[:12]
            tag += f'_a{self._atlas_code}'
            extra = sorted(k for k in self._extra if k in self.family_maps(fam))
            if extra:                                     # plant rasters change between plans: by their bytes
                h = hashlib.sha1()
                for k in extra:
                    for a in self._extra[k]:
                        h.update(b'-' if a is None else np.ascontiguousarray(a).tobytes())
                tag += '_x' + h.hexdigest()[:10]
        elif base in ('C', 'P'):
            tag += '_' + (self._colour_tag or 'nocolour')
        return os.path.join(folder, f'surface_{self.key}_{tag}{ext}')

    def _prune_images(self, fam, keep):
        """Delete this bake's stale atlas files of a family: D, E, F, C, P files other than `keep` (an older atlas
        code or palette), M files of an older atlas code."""
        folder = os.path.dirname(keep)
        base = 'M' if fam.startswith('M') else fam
        pat = f'surface_{self.key}_{"M" if base == "M" else base + "_"}*'
        for p in glob.glob(os.path.join(folder, pat)):
            if os.path.abspath(p) == os.path.abspath(keep) or not p.endswith(('.png', '.exr')):
                continue
            if base == 'M' and f'_a{self._atlas_code}' in os.path.basename(p):
                continue
            try:
                os.remove(p)
            except OSError:
                pass

    def save_images(self, folder):
        """Copy every image's file (OpenEXR half for D and F, 8-bit PNG for the rest) into `folder` and switch the
        images to the copies: a .blend that renders on another machine then references them. Returns {family:
        path}."""
        import shutil
        out = {}
        for fam, img in self.images().items():
            src = self.image_path(fam)
            dst = os.path.join(folder, os.path.basename(src))
            os.makedirs(folder, exist_ok=True)
            if os.path.abspath(src) != os.path.abspath(dst):
                shutil.copyfile(src, dst)
            img.filepath = dst
            img.reload()
            out[fam] = dst
        return out

    def describe(self):
        """A text table: per level its maps' ranges, per family its layout and memory."""
        lines = [repr(self)]
        for fam in self.families():
            lay = self.layouts[fam]
            base = 'M' if fam.startswith('M') else fam
            lines.append(f'  {fam:3s} {lay.width} x {lay.height}  {AT.megabytes(lay, MP.FAMILIES[base]["format"]):.0f} '
                         f'MB  {self.family_maps(fam)}')
        return '\n'.join(lines)

    # ---- the palette bake
    def bake_palette(self, palette=None, cache=None, log=print, provenance='budget'):
        """The far colour (C) and provenance colour (P) of a palette (surface/palette_bake.py), cached beside the
        bake. provenance: 'budget' routes P only while the palette bake stays within its 30 s (past it P is
        deferred and the P family is absent), True always (a cached bake without P gains it), False never.
        info['palette_bake'] says what was made, cached or deferred. Returns self."""
        from . import palette_bake as PB
        pal = palette if palette is not None else self.palette
        if pal is None:
            raise ValueError('bake_palette needs a palette')
        self._colour = PB.bake(self, pal, cache=cache, log=log, p_mode=provenance)
        self._memo.clear()
        for fam in ('C', 'P'):
            self._images.pop(fam, None)
        return self


def _strips(t):
    """A tile's gutter as four strips: [(rows, cols, the strip's world ys, its world xs)], south, north, west, east."""
    s, g, n = t.size, t.gutter, t.n
    xs, ys = t.centres()
    return [(slice(0, g), slice(0, s), ys[:g], xs),
            (slice(g + n, s), slice(0, s), ys[g + n:], xs),
            (slice(g, g + n), slice(0, g), ys[g:g + n], xs[:g]),
            (slice(g, g + n), slice(g + n, s), ys[g:g + n], xs[g + n:])]


def _linear_to_srgb(c):
    c = np.clip(np.asarray(c, np.float64), 0.0, 1.0)
    return np.where(c <= 0.0031308, c * 12.92, 1.055 * np.power(c, 1.0 / 2.4) - 0.055).astype(F32)


# --------------------------------------------------------------------------------------------- the cache ---

REPO = os.path.normpath(os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', '..', '..', '..'))
CACHE_GB = 8.0                      # the surface cache's own cap (whole terrain keys pruned, oldest first)


def cache_root():
    """The surface cache's own root: EIDO_SURFACE_CACHE, else <repo>/eidoverse/assets/cache/terrain_surface/
    (git-ignored, as the terrain cache is; never inside the terrain cache, whose prune must not count it)."""
    return os.environ.get('EIDO_SURFACE_CACHE') or os.path.join(REPO, 'eidoverse', 'assets', 'cache',
                                                                'terrain_surface')


def cache_folder(terrain, cache):
    """Where a terrain's bakes are cached: <cache_root()>/<terrain key>/ when cache is True, the folder when cache
    is a path, else None (in memory)."""
    if not cache:
        return None
    if isinstance(cache, (str, os.PathLike)):
        os.makedirs(cache, exist_ok=True)
        return str(cache)
    from . import bake as B
    folder = os.path.join(cache_root(), B.terrain_key(terrain))
    os.makedirs(folder, exist_ok=True)
    return folder


def prune_root(keep_gb=CACHE_GB, root=None):
    """Delete whole terrain keys from the surface cache's root, least recently used first, until it holds at most
    keep_gb. Returns the bytes freed."""
    import shutil
    root = root or cache_root()
    if not os.path.isdir(root):
        return 0
    ents = []
    for d in os.listdir(root):
        p = os.path.join(root, d)
        if os.path.isdir(p):
            files = [os.path.join(p, f) for f in os.listdir(p)]
            size = sum(os.path.getsize(f) for f in files if os.path.isfile(f))
            used = max([os.path.getmtime(f) for f in files if os.path.isfile(f)] or [os.path.getmtime(p)])
            ents.append((used, size, p))
    ents.sort()
    total = sum(e[1] for e in ents)
    freed = 0
    for _used, size, p in ents[:-1] if ents else []:
        if total - freed <= keep_gb * 1e9:
            break
        shutil.rmtree(p, ignore_errors=True)
        freed += size
    return freed


def _paths(folder, key, n):
    return [os.path.join(folder, f'surface_{key}_L{i}.npz') for i in range(n)], os.path.join(folder, f'surface_{key}.json')


def _stored(name, a, cell):
    """A map as the cache stores it: the 8-bit maps (E and M) as uint8 in their image encoding, the 16F ones (D,
    F) as float16, the drainage area (m^2 overflows half) and the routing surface (its tilt across a flat is
    millimetres) as float32."""
    a = np.asarray(a)
    if name == 'area' or name.startswith('_'):
        return np.asarray(a, np.float32)
    try:
        s = MP.spec(name)
    except KeyError:
        s = None
    if s is not None and s.family in ('E', 'M') and s.encoding in ('unit', 'signed', 'bend', 'thick'):
        return np.rint(MP.encode(s, a, cell) * F32(255.0)).astype(np.uint8)
    return np.asarray(a, np.float16)


def _unstored(name, a, cell):
    """The physical values of a map as _stored keeps it."""
    a = np.asarray(a)
    if a.dtype == np.uint8:
        return MP.decode(MP.spec(name), a.astype(F32) * F32(1.0 / 255.0), cell).astype(F32)
    return np.asarray(a, F32)


# the F family's arrays, kept in float16 less their level's reference (metres above the ground run to hundreds of
# metres, where a half float steps by 0.25-0.5 m; about the reference, the bed heights keep centimetres)
_REF_OF = {'strata_dz': 'strata', 'src_dz': 'src_strata'}


def _level_arrays(m, cell, refs=None, i=0):
    """{name: stored array} of a level's maps, with '_ref_<name>' (float64) beside each referenced one."""
    out = {}
    for k, v in m.items():
        r = None
        if refs and k in _REF_OF and _REF_OF[k] in refs:
            r = float(refs[_REF_OF[k]][i])
        if r is not None:
            out[k] = np.asarray(np.asarray(v, np.float64) - r, np.float16)
            out[f'_ref_{k}'] = np.asarray(r, np.float64)
        else:
            out[k] = _stored(k, v, cell)
    return out


def _level_maps(z, cell):
    """The physical maps of a level from its .npz (the inverse of _level_arrays)."""
    out = {k: _unstored(k, z[k], cell) for k in z.files if not k.startswith('_ref_')}
    for k in z.files:
        if k.startswith('_ref_') and k[5:] in out:
            out[k[5:]] = (out[k[5:]] + F32(float(z[k]))).astype(F32)
    return out


def load_cached(folder, key, n_levels, lazy=True, cells=None):
    """(baked maps per level, info) from a cache folder, or None when any file is missing. lazy: each level is its
    .npz path, which SurfaceData loads (and decodes) on first use: a cache hit that only makes images reads no
    arrays. lazy=False needs the levels' cells (the 8-bit maps decode by them)."""
    if folder is None:
        return None
    files, meta = _paths(folder, key, n_levels)
    if not (os.path.exists(meta) and all(os.path.exists(p) for p in files)):
        return None
    out = []
    for i, p in enumerate(files):
        if lazy:
            out.append(p)
            continue
        with np.load(p, allow_pickle=False) as z:
            out.append(_level_maps(z, float(cells[i])))
    with open(meta, encoding='utf-8') as f:
        info = json.load(f)
    try:
        os.utime(meta)
    except OSError:
        pass
    return out, info


def save_cached(folder, key, baked, info, keep=KEEP_BAKES, cells=None):
    """Write a bake to its cache folder (each level atomically, the json last; the 8-bit maps as uint8 in their
    encoding, which needs each level's cell; the F family less info['refs'], its level's reference) and delete the
    folder's surface bakes beyond the newest `keep`."""
    if folder is None:
        return
    os.makedirs(folder, exist_ok=True)
    files, meta = _paths(folder, key, len(baked))
    refs = info.get('refs') if isinstance(info, dict) else None
    for i, (p, m) in enumerate(zip(files, baked)):
        tmp = p + '.tmp.npz'
        cell = float(cells[i]) if cells is not None else 1.0
        np.savez(tmp, **_level_arrays(m, cell, refs, i))
        os.replace(tmp, p)
    with open(meta + '.tmp', 'w', encoding='utf-8') as f:
        json.dump(info, f, indent=1, default=str)
    os.replace(meta + '.tmp', meta)
    prune_bakes(folder, keep)


def prune_bakes(folder, keep=KEEP_BAKES):
    """Delete a folder's surface bakes (and their palette bakes) beyond the `keep` most recently used."""
    metas = [p for p in glob.glob(os.path.join(folder, 'surface_*.json')) if '_pal' not in os.path.basename(p)]
    metas.sort(key=os.path.getmtime, reverse=True)
    for p in metas[keep:]:
        k = os.path.basename(p)[len('surface_'):-len('.json')]
        for q in glob.glob(os.path.join(folder, f'surface_{k}*')):
            try:
                os.remove(q)
            except OSError:
                pass


# ----------------------------------------------------------------------------------------------- the call ---

def bake_surface(terrain, palette=None, options=None, cache=True, extra=None, log=print):
    """A terrain's SurfaceData (module doc). Cached by the terrain's key, the bake's code and its options."""
    from . import bake as B
    t0 = time.perf_counter()
    info0 = getattr(terrain, 'info', None) or {}
    if palette == 'auto' and info0.get('palette') not in (None, 'auto'):
        palette = info0['palette']                        # the one make_terrain resolved (a real place's own)
    pal = B.resolve_palette(terrain, palette) if palette is not None else None
    opts = B.resolve_options(terrain, pal, options)
    key = B.bake_key(terrain, opts)
    folder = cache_folder(terrain, cache)
    n = len(terrain.levels)
    hit = load_cached(folder, key, n)
    if hit is not None:
        baked, info = hit
        info = dict(info, cache_hit=True, load_seconds=round(time.perf_counter() - t0, 3))
        if log:
            log(f'[surface] bake {key[:10]}: cache hit, {n} levels in {info["load_seconds"]} s')
    else:
        baked, info, fills = B.bake_levels(terrain, opts, log=log)
        for m, w in zip(baked, fills):                   # the routing surface, for the palette bake's colour routing
            if w is not None:
                m['_fill'] = w
        info = dict(info, cache_hit=False, key=key, terrain=B.terrain_key(terrain), options=opts,
                    names=[sorted(k for k in m if not k.startswith('_')) for m in baked])
        info['refs'] = SurfaceData(terrain, baked, info, opts, key).refs
        t1 = time.perf_counter()
        save_cached(folder, key, baked, info, cells=[float(lv.cell) for lv in terrain.levels])
        if folder is not None and cache is True:
            prune_root()
        info['save_seconds'] = round(time.perf_counter() - t1, 3)
        if log:
            log(f'[surface] bake {key[:10]}: {n} levels in {info["seconds"]} s'
                + (f' (saved in {info["save_seconds"]} s to {folder})' if folder else ' (in memory)'))
    sd = SurfaceData(terrain, baked, info, opts, key, palette=pal, cache_dir=folder)
    if extra:
        sd.add_maps(extra)
    if pal is not None and opts.get('maps', 'all') == 'all':
        try:
            sd.bake_palette(pal, cache=folder, log=log)
        except ImportError as e:                          # the palette bake's pieces are not all there yet
            sd.info['palette_bake'] = f'skipped: {e}'
            if log:
                log(f'[surface] no palette bake: {e}')
    sd.info['seconds_total'] = round(time.perf_counter() - t0, 3)
    return sd


__all__ = ['bake_surface', 'SurfaceData', 'MAPS', 'cache_folder', 'load_cached', 'save_cached', 'prune_bakes']
