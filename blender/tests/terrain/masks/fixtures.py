"""Fixtures for the masks package's tests and sheets: the real reference DEMs as a two-level stack (the wider context
DEM, then the main tile inside it), in the design's frame (row 0 = south, metres, centred on the tile centre), with
the drainage area every flow mask needs.

The drainage area: the exact depression fill, multiple-flow-direction routing (exponent 1.1, flats routed toward
their spill) and accumulation of solvers/hydro.py, on the CPU, so the tests run in plain Python. The main tile
receives the context's flow across its border where the outside drains in (each border cell gets the context's area
per metre of contour times its own width: the flux-conserving border pin), so a river entering the tile keeps its
catchment.
"""
import importlib.util
import math
import os
import sys
import time

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
TN = os.path.normpath(os.path.join(HERE, '..'))                   # blender/tests/terrain
BLENDER = os.path.normpath(os.path.join(TN, '..', '..'))          # blender/
TERRAIN = os.path.join(BLENDER, 'eidoblend', 'terrain')
OUT = os.path.join(TN, 'out', 'masks')
CACHE = os.path.join(OUT, 'cache')
sys.path.insert(0, os.path.join(TN, 'reference'))
import landform_refs as R  # noqa: E402


def _load(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    mod = importlib.util.module_from_spec(spec)
    sys.modules[name] = mod
    spec.loader.exec_module(mod)
    return mod


M = _load('terrain_masks', os.path.join(TERRAIN, 'masks.py'))
sys.path.insert(0, BLENDER)
from eidoblend.terrain.solvers import hydro as HY  # noqa: E402

SHEET_REFS = ['lauterbrunnen', 'grand_canyon_toroweap', 'mount_fuji', 'badlands_sd', 'great_sand_dunes']
# per-reference mask parameters a recipe would pass (the snowline is the only place-specific one here)
REF_PARAMS = {
    'lauterbrunnen': dict(snowline_m=2750.0, treeline_m=1900.0),
    'mount_fuji': dict(snowline_m=3300.0, treeline_m=2500.0),
}
# a DEM has no process history; where the landform is one process's product, the tests give the main tile the field
# that process's recipe would write (sand thickness, metres), so the masks that read it can be judged
SAND_TILES = {'great_sand_dunes': 10.0, 'namib_star_dunes': 10.0}
# the flat false-colour material the sheets and the renders paint from the masks (display sRGB), per reference: a
# preview of what the surfacing package builds, not its palettes
PREVIEW_PALETTES = {
    'alpine': dict(soil=(0.42, 0.36, 0.27), veg=(0.22, 0.38, 0.13), rock=(0.52, 0.51, 0.50), scree=(0.63, 0.60, 0.55),
                   snow=(0.95, 0.97, 1.0), water=(0.10, 0.22, 0.30), veg_k=1.0),
    'volcanic': dict(soil=(0.30, 0.25, 0.22), veg=(0.18, 0.33, 0.12), rock=(0.22, 0.21, 0.21), scree=(0.40, 0.30, 0.26),
                     snow=(0.95, 0.97, 1.0), water=(0.10, 0.22, 0.30), veg_k=1.0),
    'desert_sandstone': dict(soil=(0.72, 0.52, 0.36), veg=(0.45, 0.47, 0.30), rock=(0.70, 0.40, 0.27),
                             scree=(0.78, 0.60, 0.45), snow=(1, 1, 1), water=(0.10, 0.22, 0.30), veg_k=0.25),
    'badlands': dict(soil=(0.78, 0.72, 0.60), veg=(0.55, 0.55, 0.35), rock=(0.70, 0.62, 0.52), scree=(0.80, 0.72, 0.60),
                     snow=(1, 1, 1), water=(0.10, 0.22, 0.30), veg_k=0.6),
    'dunes': dict(soil=(0.80, 0.68, 0.50), veg=(0.55, 0.52, 0.35), rock=(0.60, 0.52, 0.42), scree=(0.72, 0.62, 0.48),
                  snow=(1, 1, 1), water=(0.10, 0.22, 0.30), veg_k=0.15),
}
PREVIEW_PALETTE_OF = {'lauterbrunnen': 'alpine', 'grand_canyon_toroweap': 'desert_sandstone', 'mount_fuji': 'volcanic',
                      'badlands_sd': 'badlands', 'great_sand_dunes': 'dunes'}


class Level(dict):
    """A level as the design describes it: x0, y0 (south-west corner, metres), cell, n, role."""
    def __getattr__(self, k):
        try:
            return self[k]
        except KeyError as e:
            raise AttributeError(k) from e


def south_up(a):
    return np.ascontiguousarray(np.flipud(a))


def reference_level(name, context=False):
    """(h float64 south-up metres, Level) of a reference or its context, centred on the tile centre."""
    h, meta = R.load(name, context=context)
    p = float(meta['pixel_size_m'])
    rows, cols = h.shape
    lv = Level(x0=-cols * p / 2.0, y0=-rows * p / 2.0, cell=p, n=cols, rows=rows, cols=cols,
               role='context' if context else 'main', name=name)
    return south_up(h).astype(np.float64), lv, meta


def lakes(h, filled, relief=None):
    """Lake depth (metres, 0 elsewhere) by the design's hydrology rule (4.3): a depression deeper than
    max(1 m, 0.2 % of the relief) holds water to its spill level; shallower ones stay dry ground."""
    depth = filled - h
    dep = depth > 1e-3
    out = np.zeros_like(h)
    if not dep.any():
        return out
    thr = max(1.0, 0.002 * (float(np.ptp(h)) if relief is None else relief))
    _lv, inv = np.unique(filled[dep], return_inverse=True)
    deepest = np.zeros(_lv.size)
    np.maximum.at(deepest, inv, depth[dep])
    lake = deepest[inv] > thr
    jj, ii = np.nonzero(dep)                              # the same row-major order as filled[dep] and depth[dep]
    out[jj[lake], ii[lake]] = depth[dep][lake]
    return out


def drainage_area(h, cell, inflow=None):
    """Converged MFD drainage area (m^2) of a south-up grid with open edges: exact fill, route, accumulate.
    inflow: extra m^2 entering at each cell (the border pin), or None. Across a filled depression the routing is a
    breadth-first walk to the spill (straight, arbitrary lines: dune hollows drew them in flow and wetness), so every
    cell of one depression (one spill level) takes the depression's outflow: everything that enters it collects
    there."""
    filled, _info = HY.fill_depressions(h, wrap=(False, False))
    recv, wgt, term = HY.route(filled, wrap=(False, False), method='mfd', exponent=1.1)
    area = np.full(h.size, cell * cell)
    if inflow is not None:
        area += np.asarray(inflow, np.float64).ravel()
    A = HY.accumulate(recv, wgt, term, area=area).reshape(h.shape)
    dep = (filled - h) > 1e-3
    if dep.any():
        _lv, inv = np.unique(filled[dep], return_inverse=True)
        top = np.zeros(_lv.size)
        np.maximum.at(top, inv, A[dep])
        A[dep] = top[inv]
    # dead-flat ground outside depressions (a river's surface in a DEM: stairs of the 16-bit quantisation) is routed
    # by the same walk; there the largest area within 64 m of flat ground spreads across the flat, so the river's
    # surface carries the river
    gy, gx = np.gradient(filled, cell)
    flat = np.hypot(gx, gy) < 0.002
    if flat.any():
        af = np.where(flat, A, 0.0)
        for _ in range(int(math.ceil(64.0 / cell))):
            p = np.pad(af, 1, mode='edge')
            m = np.maximum.reduce([p[1 + dj:1 + dj + h.shape[0], 1 + di:1 + di + h.shape[1]]
                                   for dj in (-1, 0, 1) for di in (-1, 0, 1)])
            af = np.where(flat, m, 0.0)
        A = np.where(flat, np.maximum(A, af), A)
    return A, filled


def border_inflow(h, lv, h_ctx, A_ctx, lv_ctx):
    """m^2 entering each border cell of the main tile from the context: where the context's ground just outside is
    higher than the border cell, the context's area per metre of contour there times the cell's width."""
    ny, nx = h.shape
    c = lv.cell
    S = M.StackSampler([(lv_ctx.x0, lv_ctx.y0, lv_ctx.cell, h_ctx)])
    Sa = M.StackSampler([(lv_ctx.x0, lv_ctx.y0, lv_ctx.cell, A_ctx / lv_ctx.cell)])
    inflow = np.zeros_like(h)
    xs = lv.x0 + (np.arange(nx) + 0.5) * c
    ys = lv.y0 + (np.arange(ny) + 0.5) * c
    for side in ('s', 'n', 'w', 'e'):
        if side in 'sn':
            j = 0 if side == 's' else ny - 1
            bx, by = xs, np.full(nx, ys[j])
            ox, oy = bx, by + (-c if side == 's' else c)
            hb = h[j, :]
        else:
            i = 0 if side == 'w' else nx - 1
            bx, by = np.full(ny, xs[i]), ys
            ox, oy = bx + (-c if side == 'w' else c), by
            hb = h[:, i]
        hout = S(ox, oy, cubic=True)
        a_out = Sa(bx, by, cubic=False)
        flux = np.where(np.isfinite(hout) & (hout > hb), np.nan_to_num(a_out) * c, 0.0)
        if side in 'sn':
            inflow[j, :] += flux
        else:
            inflow[:, i] += flux
    return inflow


def water_field(name, meta, shape):
    """A nominal 2 m depth on the reference's lake and sea cells (a DEM carries the water's surface, not its depth),
    or None."""
    w = R.load_water(name)
    if w is None:
        return None
    mask = south_up(w[0])
    if mask.shape != shape:
        return None
    return np.where(mask >= 128, 2.0, 0.0)


BORDER_BAND = 16          # cells: DESIGN.md 2.2, a child's border pinned to its parent


def pin_border(h, lv, h_parent, lv_parent, band=BORDER_BAND):
    """h with its outer `band` cells blended toward the parent (Catmull-Rom), weight 1 at the edge falling smoothly
    to 0 at `band` cells in: what the level runner does to every child level. The context DEM is smoother than the
    main tile (18 m median difference along Lauterbrunnen's border), so without it every scale-aware mask would draw
    a frame at the tile edge."""
    ny, nx = h.shape
    c = lv.cell
    X, Y = np.meshgrid(lv.x0 + (np.arange(nx) + 0.5) * c, lv.y0 + (np.arange(ny) + 0.5) * c)
    d = np.minimum.reduce([np.arange(nx)[None, :].repeat(ny, 0), np.arange(nx)[::-1][None, :].repeat(ny, 0),
                           np.arange(ny)[:, None].repeat(nx, 1), np.arange(ny)[::-1][:, None].repeat(nx, 1)])
    w = 1.0 - M.smoothstep(0.0, float(band), d.astype(np.float64))
    near = w > 0
    S = M.StackSampler([(lv_parent.x0, lv_parent.y0, lv_parent.cell, h_parent)])
    out = h.copy()
    out[near] = h[near] + w[near] * (S(X[near], Y[near], cubic=True) - h[near])
    return out


def reference_stack(name, log=print):
    """[context fields, main fields] and [context level, main level] of a reference, each fields dict with h, A and
    (where the reference has open water) water. The main tile's border band is pinned to the context, as the level
    runner pins every child. The drainage areas are cached in out/masks/cache/."""
    os.makedirs(CACHE, exist_ok=True)
    hc, lc, mc = reference_level(name, context=True)
    hm, lm, mm = reference_level(name)
    hm = pin_border(hm, lm, hc, lc)
    path = os.path.join(CACHE, f'{name}_A_lakes.npz')
    if os.path.exists(path):
        z = np.load(path)
        A_c, A_m, lake_m = z['A_ctx'], z['A_main'], z['lake_main']
    else:
        t0 = time.time()
        A_c, _ = drainage_area(hc, lc.cell)
        inflow = border_inflow(hm, lm, hc, A_c, lc)
        A_m, filled = drainage_area(hm, lm.cell, inflow)
        lake_m = lakes(hm, filled)
        np.savez_compressed(path, A_ctx=A_c.astype(np.float32), A_main=A_m.astype(np.float32),
                            lake_main=lake_m.astype(np.float32))
        log(f'[fixtures] {name}: drainage area of context + main in {time.time() - t0:.1f}s')
    fc = dict(h=hc, A=A_c.astype(np.float64))
    fm = dict(h=hm, A=A_m.astype(np.float64))
    wm = water_field(name, mm, hm.shape)
    if name not in SAND_TILES and lake_m.any():   # closed basins deeper than the rule hold water (dune hollows: dry)
        wm = np.maximum(wm, lake_m) if wm is not None else lake_m.astype(np.float64)
    if wm is not None:
        fm['water'] = wm
    if name in SAND_TILES:                    # the field a dunes recipe writes: the whole tile is a dune field
        fm['sand'] = np.full(hm.shape, SAND_TILES[name])
    return [fc, fm], [lc, lm], mm


def hero_stack(name='lauterbrunnen', at=(-300.0, -900.0), cells=(2.0, 0.5), n=1024, log=print):
    """A stack shaped like the design's (2.2): the reference's context and main tile, then hero levels of n x n cells
    at `cells` metres around `at` (local metres), each a Catmull-Rom refinement of the stack above it with its own
    drainage area (border inflow from its parent). Windows snap to twice their cell. Cached in out/masks/cache/."""
    fl, lv, meta = reference_stack(name, log=log)
    path = os.path.join(CACHE, f'{name}_hero_stack.npz')
    levels, fields = list(lv), list(fl)
    if os.path.exists(path):
        z = np.load(path)
        for k, (x0, y0, c) in enumerate(z['levels'][2:], start=2):
            levels.append(Level(x0=float(x0), y0=float(y0), cell=float(c), n=n, role='hero'))
            fields.append(dict(h=z[f'h{k}'], A=z[f'A{k}']))
        return fields, levels, meta
    t0 = time.time()
    for cell in cells:
        side = n * cell
        x0 = round((at[0] - side / 2) / (2 * cell)) * (2 * cell)
        y0 = round((at[1] - side / 2) / (2 * cell)) * (2 * cell)
        S = M.StackSampler([(l.x0, l.y0, l.cell, f['h']) for l, f in zip(levels, fields)])
        X, Y = np.meshgrid(x0 + (np.arange(n) + 0.5) * cell, y0 + (np.arange(n) + 0.5) * cell)
        h = S(X, Y, cubic=True)
        L = Level(x0=x0, y0=y0, cell=cell, n=n, role='hero', rows=n, cols=n)
        A, _ = drainage_area(h, cell, border_inflow(h, L, fields[-1]['h'], fields[-1]['A'], levels[-1]))
        levels.append(L)
        fields.append(dict(h=h, A=A))
    np.savez_compressed(path, levels=np.array([[l.x0, l.y0, l.cell] for l in levels]),
                        **{f'h{k}': f['h'] for k, f in enumerate(fields)},
                        **{f'A{k}': f['A'] for k, f in enumerate(fields)})
    log(f'[fixtures] {name}: hero stack in {time.time() - t0:.1f}s')
    return fields, levels, meta


def params_for(name, **kw):
    d = dict(REF_PARAMS.get(name, {}))
    d.update(kw)
    return M.MaskParams(**d)
