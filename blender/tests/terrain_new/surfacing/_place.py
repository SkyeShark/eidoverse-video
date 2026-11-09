"""Test fixture: a real DEM as a level stack with its masks and ring mesh, standing in for package 5's real_place
recipe until it lands. Runs inside Blender (make_object needs bpy; the rest is numpy).

    import _place as PL
    st = PL.stack('grand_canyon_toroweap', view='eye')     # levels, heights (metres above the tile's lowest point),
                                                           # masks per level, the RingMesh, samplers
    obj = PL.make_mesh(st, 'terrain')                      # package 5's make_object: eido_<mask> point attributes

The levels (core's frames: row 0 south, cell centres at x0 + (i + 0.5) cell, metres from the tile centre):
  context   the reference's _context DEM resampled to 4 x and 2 x the main cell over 4 x and 2 x its extent (only
            the levels its data covers), for the eye view's horizon
  main      the reference DEM itself (its pixel, 1000 cells), its border band blended 16 cells toward its parent
  hero      around the eye: each half the parent's cell, 512 cells, Catmull-Rom upsampled (no new detail: the detail
            stages are package 12's), down to about 0.5 m
The drainage area A is routed on the context and main levels (Ekigar's hydrology, moving to solvers/hydro.py; the
context's trunk rivers carry their upstream catchment into the main tile), and upsampled into the hero levels with
A / 2 per level (masks.py's specific catchment a = A / cell stays continuous). Masks come from package 4's
masks.compute_stack with the place's MaskParams (palettes.PLACES: snowline, treeline, sea level), base elevation =
the tile's lowest point, strata = absolute altitude.
"""
from __future__ import annotations

import importlib.util
import math
import os
import sys
import time
from pathlib import Path

import numpy as np

HERE = Path(__file__).resolve().parent
TN = HERE.parent                                   # blender/tests/terrain_new
BLENDER_DIR = TN.parents[1]                        # blender/
OUT = TN / 'out' / 'surfacing'
REF = TN / 'reference'
for p in (str(BLENDER_DIR), str(REF)):
    if p not in sys.path:
        sys.path.insert(0, p)

import landform_refs as R  # noqa: E402
from sites import SITES  # noqa: E402
from eidoblend.terrain import masks as M  # noqa: E402
from eidoblend.terrain.build import mesh as MESH  # noqa: E402
from eidoblend.terrain.build import palettes as P  # noqa: E402
from eidoblend.terrain.core import grid as G  # noqa: E402

R_EFF = R.EARTH_R * 7.0 / 6.0                      # the reference rig's Earth radius with refraction
BAND = 16


def _hydro():
    """Ekigar's hydrology (fill, route, accumulate), loaded by path: it moves to solvers/hydro.py at integration."""
    try:
        from eidoblend.terrain.solvers import hydro as H     # noqa: F401  (after integration)
        return H
    except Exception:
        pass
    path = BLENDER_DIR / 'eidoblend' / 'terrain' / 'ekigar' / 'hydrology.py'
    spec = importlib.util.spec_from_file_location('_ekigar_hydrology', path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def drainage_area(h, cell, cache_key=None):
    """Routed drainage area (m^2, MFD on the depression-filled surface; edges are outlets), cached in out/."""
    if cache_key:
        f = OUT / 'cache' / f'A_{cache_key}.npy'
        if f.exists():
            return np.load(f)
    H = _hydro()
    filled, _ = H.fill_depressions(np.asarray(h, np.float64), wrap=(False, False))
    recv, wgt, term = H.route(filled, wrap=(False, False), method='mfd')
    A = (H.accumulate(recv, wgt, term) * cell * cell).reshape(np.shape(h)).astype(np.float32)
    if cache_key:
        f.parent.mkdir(parents=True, exist_ok=True)
        np.save(f, A)
    return A


def _south_up(a):
    return np.ascontiguousarray(np.asarray(a)[::-1])


def _running_min(a, r):
    """The minimum over a (2r+1)-cell square window (edges held), by van Herk's running minimum on both axes."""
    out = np.asarray(a, np.float64)
    for axis in (0, 1):
        n = out.shape[axis]
        k = 2 * r + 1
        pad = np.pad(out, [(r, r + k) if ax == axis else (0, 0) for ax in (0, 1)], mode='edge')
        m = pad.shape[axis]
        nb = m // k
        pad = np.take(pad, np.arange(nb * k), axis=axis)
        sh = list(pad.shape)
        sh[axis:axis + 1] = [nb, k]
        blk = pad.reshape(sh)
        g = np.minimum.accumulate(blk, axis=axis + 1).reshape(pad.shape)
        h = np.flip(np.minimum.accumulate(np.flip(blk, axis + 1), axis=axis + 1), axis + 1).reshape(pad.shape)
        idx = np.arange(n)
        out = np.minimum(np.take(h, idx, axis=axis), np.take(g, idx + k - 1, axis=axis))
    return out


def dune_sand(h, cell, floor_radius_m=350.0, sheet_m=3.0):
    """A real-DEM stand-in for the dune solver's `sand` field (metres): the height above the local interdune floor
    (the lowest ground within floor_radius_m), less the sheet_m a stable, vegetated sand sheet stands. Package 8
    writes the real field; on a real DEM this keeps the masks package's vegetation off the active dunes and on the
    sheet around them."""
    r = max(1, int(round(floor_radius_m / cell)))
    floor = _running_min(h, r)
    return np.maximum(np.asarray(h, np.float64) - floor - sheet_m, 0.0)


def eye_xy(name):
    _, meta = R.load(name)
    ev = SITES[name]['views']['eye']
    ex, ey = R.latlon_to_xy(meta, *ev['at'])
    return float(ex), float(ey)


def _hero_window(parent, centre, n, band=BAND):
    """A hero window: half the parent's cell, n cells, centred on `centre`, snapped to the parent's grid and kept
    inside it by `band` parent cells."""
    cell = parent['cell'] / 2.0
    side = n * cell
    lo_x = parent['x0'] + band * parent['cell']
    hi_x = parent['x0'] + parent['n'] * parent['cell'] - band * parent['cell'] - side
    lo_y = parent['y0'] + band * parent['cell']
    hi_y = parent['y0'] + parent['n'] * parent['cell'] - band * parent['cell'] - side
    if hi_x < lo_x or hi_y < lo_y:
        return None
    x0 = min(max(centre[0] - side / 2.0, lo_x), hi_x)
    y0 = min(max(centre[1] - side / 2.0, lo_y), hi_y)
    x0 = parent['x0'] + round((x0 - parent['x0']) / parent['cell']) * parent['cell']
    y0 = parent['y0'] + round((y0 - parent['y0']) / parent['cell']) * parent['cell']
    return dict(x0=float(x0), y0=float(y0), cell=float(cell), n=int(n), role='hero')


def stack(name, view='eye', hero_cell=0.5, hero_n=512, max_hero=5, names=None, log=print):
    """The level stack of a reference for one view. view 'aerial': the main level alone (as the clay aerial shows
    the tile alone); 'eye': context levels, the main level and hero levels around the eye.
    Returns dict(levels, heights (metres above z0), A, masks (per level Masks), z0, meta, palette, place, eye, ...)."""
    t0 = time.time()
    h_n, meta = R.load(name)
    p = float(meta['pixel_size_m'])
    h_main = _south_up(h_n).astype(np.float64)
    n = h_main.shape[0]
    z0 = float(h_main.min())
    pal, place = P.for_place(name)
    main = dict(x0=-n / 2.0 * p, y0=-n / 2.0 * p, cell=p, n=n, role='main')
    levels, heights, As, waters = [], [], [], []
    # water (lakes in the main tile)
    wm = R.load_water(name)
    water_main = None
    if wm is not None:
        mask, bodies = wm
        mask = _south_up(mask)
        water_main = np.zeros_like(h_main)
        for b in bodies:
            if b['kind'] == 'lake':
                sel = mask == b['mask_value']
                water_main[sel] = np.maximum(b['level_m'] - h_main[sel], 0.0)
            elif b['kind'] == 'sea':
                sel = mask == 255
                water_main[sel] = np.maximum(b['level_m'] - h_main[sel], 0.0)
    if view == 'eye':
        try:
            hc_n, mc = R.load(name, context=True)
        except FileNotFoundError:
            hc_n, mc = None, None
        if hc_n is not None:
            half_c = mc['cols'] * mc['pixel_size_m'] / 2.0
            for f in (4, 2):
                ext = f * n * p
                if ext / 2.0 > half_c + 1e-6:
                    continue
                lv = dict(x0=-n / 2.0 * f * p, y0=-n / 2.0 * f * p, cell=f * p, n=n, role='context')
                X, Y = G.cell_centres(lv['x0'], lv['y0'], lv['cell'], n)
                hc = np.asarray(R.sample(hc_n.astype(np.float64), mc, X, Y), np.float64)
                if levels:                               # blend its border toward its parent
                    par, ph = levels[-1], heights[-1]
                    i0 = int(round((lv['x0'] - par['x0']) / par['cell']))
                    j0 = int(round((lv['y0'] - par['y0']) / par['cell']))
                    up = G.crop_upsample2(ph, i0, j0, n // 2).astype(np.float64)
                    w = G.border_ramp(n, BAND)
                    hc = w * up + (1 - w) * hc
                levels.append(lv)
                heights.append(hc)
                As.append(drainage_area(hc, lv['cell'], f'{name}_ctx{f}'))
                waters.append(None)
    # the main level, its border blended toward its parent
    hm = h_main.copy()
    if levels:
        par, ph = levels[-1], heights[-1]
        i0 = int(round((main['x0'] - par['x0']) / par['cell']))
        j0 = int(round((main['y0'] - par['y0']) / par['cell']))
        up = G.crop_upsample2(ph, i0, j0, n // 2).astype(np.float64)
        w = G.border_ramp(n, BAND)
        hm = w * up + (1 - w) * hm
    A = drainage_area(h_main, p, f'{name}_main')
    if levels:                                           # the trunk rivers' upstream catchment from the context
        par = levels[-1]
        i0 = int(round((main['x0'] - par['x0']) / par['cell']))
        j0 = int(round((main['y0'] - par['y0']) / par['cell']))
        A = np.maximum(A, G.crop_upsample2(As[-1], i0, j0, n // 2, 'bilinear') / 2.0)
    levels.append(main)
    heights.append(hm)
    As.append(A.astype(np.float64))
    waters.append(water_main)
    i_main = len(levels) - 1
    eye = eye_xy(name)
    if view == 'eye':
        while len(levels) - 1 - i_main < max_hero and levels[-1]['cell'] / 2.0 >= hero_cell * 0.99:
            par = levels[-1]
            lv = _hero_window(par, eye, hero_n)
            if lv is None:
                break
            i0 = int(round((lv['x0'] - par['x0']) / par['cell']))
            j0 = int(round((lv['y0'] - par['y0']) / par['cell']))
            m = hero_n // 2
            levels.append(lv)
            heights.append(G.crop_upsample2(heights[-1], i0, j0, m).astype(np.float64))
            As.append(G.crop_upsample2(As[-1], i0, j0, m, 'bilinear').astype(np.float64) / 2.0)
            wpar = waters[-1]
            waters.append(None if wpar is None else G.crop_upsample2(wpar, i0, j0, m, 'bilinear').astype(np.float64))
    mp = dict(place.get('mask_params') or {})
    sea = mp.pop('sea_level', None)
    # the masks' height is metres above base level: the tile's lowest point inland, sea level on a coast (design 2.1:
    # base level is sea level where there is a sea); the mesh keeps the reference rig's frame (above the lowest point)
    h_ref = z0 if sea is None else float(sea)
    params = M.MaskParams(base_elevation_m=h_ref, sea_level=(None if sea is None else 0.0),
                          strata=dict(dip_deg=0.0), **mp)
    want = sorted(set(names or []) | P.masks_used(pal) | {'slope', 'height'})
    want = [w for w in want if w not in ('wear', 'deposit', 'talus', 'sand', 'lava')] + \
        [w for w in want if w in ('wear', 'deposit', 'talus', 'sand', 'lava')]
    any_water = any(w is not None for w in waters)
    sands = [None] * len(levels)
    if pal['name'] == 'dunes':                           # the dune solver's sand field, stood in for (dune_sand)
        for k, lv in enumerate(levels):
            if lv['role'] != 'hero':
                sands[k] = dune_sand(heights[k], lv['cell'])
            else:
                par = levels[k - 1]
                i0 = int(round((lv['x0'] - par['x0']) / par['cell']))
                j0 = int(round((lv['y0'] - par['y0']) / par['cell']))
                sands[k] = G.crop_upsample2(sands[k - 1], i0, j0, lv['n'] // 2, 'bilinear').astype(np.float64)
    fields = []
    for hh, AA, ww, ss in zip(heights, As, waters, sands):
        f = {'h': hh - h_ref, 'A': AA}
        if ww is not None:
            f['water'] = ww
        elif any_water:
            f['water'] = np.zeros_like(hh)
        if ss is not None:
            f['sand'] = ss
        fields.append(f)
    proc = [w for w in want if w in M.PASS_THROUGH and w != 'water' and not all(w in f for f in fields)]
    names_now = [w for w in want if w not in proc]      # a real DEM has no process fields: they read 0
    if not any_water and sea is None:
        names_now = [w for w in names_now if w != 'water']
    if params.snowline_m is None:
        names_now = [w for w in names_now if w != 'snow']
    msk = M.compute_stack(fields, levels, main=i_main, names=names_now, params=params)
    if log:
        log(f'[place] {name} {view}: {len(levels)} levels '
            f'({", ".join("%g m" % l["cell"] for l in levels)}), masks {len(names_now)} in {time.time() - t0:.1f} s')
    return dict(name=name, view=view, levels=levels, heights=[h - z0 for h in heights], A=As, masks=msk, z0=z0,
                meta=meta, palette=pal, place=place, eye=eye, i_main=i_main, names=names_now, params=params)


def ring_mesh(st, mesh_res=1000, skirt=None):
    """Package 5's RingMesh of the stack (each level's masks as attributes)."""
    attrs = {nm: [st['masks'][k].get(nm) for k in range(len(st['levels']))] for nm in st['names']}
    if skirt is None:
        skirt = st['view'] == 'eye'
    return MESH.build_rings(st['levels'], st['heights'], attributes=attrs, cores=False, mesh_res=mesh_res, skirt=skirt)


def curvature_drop(x, y, eye):
    """The Earth's curvature below the eye's tangent plane (the reference rig's eye views), metres."""
    return ((np.asarray(x) - eye[0]) ** 2 + (np.asarray(y) - eye[1]) ** 2) / (2.0 * R_EFF)


def make_mesh(st, rm, name='terrain', curvature=None):
    """The Blender object of a RingMesh (package 5's make_object), with the Earth's curvature applied for the eye
    view (as the reference rig does). Returns the object."""
    if curvature is None:
        curvature = st['view'] == 'eye'
    if curvature:
        v = rm.verts.copy()
        v[:, 2] -= curvature_drop(v[:, 0], v[:, 1], st['eye']).astype(np.float32)
        rm.verts = v
    return MESH.make_object(rm, name)


def samplers(st, rm, curvature=None):
    """(height_at, normal_at, mask_at) on the mesh as built: height_at on its triangles (less the curvature drop),
    mask_at(name, x, y) bilinear from the finest level holding the point (None for a mask the stack lacks)."""
    if curvature is None:
        curvature = st['view'] == 'eye'
    eye = st['eye']

    def height_at(x, y):
        z = rm.height_at(x, y)
        return z - curvature_drop(x, y, eye) if curvature else z
    normal_at = rm.normal_at
    cache = {}

    def mask_at(nm, x, y):
        if nm not in cache:
            layers = [(l['x0'], l['y0'], l['cell'], m.get(nm)) for l, m in zip(st['levels'], st['masks'])
                      if m.get(nm) is not None]
            cache[nm] = M.StackSampler(layers) if layers else None
        s = cache[nm]
        if s is None:
            return None
        v = s(x, y, cubic=False)
        return np.where(np.isfinite(v), v, 0.0)
    return height_at, normal_at, mask_at


def lakes(st):
    """[(name, level_m in the mesh frame, mask (rows, cols) south-up bool)] of the main tile's water bodies."""
    wm = R.load_water(st['name'])
    if wm is None:
        return []
    mask, bodies = wm
    mask = _south_up(mask)
    out = []
    for b in bodies:
        sel = (mask == b['mask_value']) if b['kind'] == 'lake' else (mask == 255)
        out.append((b['name'], b['kind'], float(b['level_m']) - st['z0'], sel))
    return out
