"""Shared by package 9's tests and sheets (volcanoes and craters, the analytic profiles).

- import_solvers(): outside Blender the package is registered by its path alone and the solver modules import as
  usual (no package __init__ runs); inside Blender the real package loads.
- load_reference(name): a reference DEM in the design frame (row 0 south, x east / y north of the tile centre).
- load_sp_crater(): the triage's Terrain Tiles cache of SP Crater (8 km at 7.8 m); the judge's sp_crater reference
  is the 3DEP tile.
- generated(name): the analytic shape set on its reference (same extent, same pixel, the preset's parameters), on a
  placeholder base of low world noise (in the recipes the surroundings come from their fluvial stages).
- the measures: radial profiles, slopes, rim crests per azimuth, outline harmonics.
"""
import json
import math
import os
import sys
import types

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
BLENDER_DIR = os.path.normpath(os.path.join(HERE, '..', '..', '..'))          # <worktree>/blender
TERRAIN_DIR = os.path.join(BLENDER_DIR, 'eidoblend', 'terrain')
REFERENCE_DIR = os.path.normpath(os.path.join(HERE, '..', 'reference'))
OUT = os.path.normpath(os.path.join(HERE, '..', 'out', 'volcanoes_craters'))
SP_CACHE = os.environ.get('TRIAGE_CACHE', 'C:/Users/sdn52/AppData/Local/Temp/claude/58f6fc01d66e098b/'
                                          '7ba5a5b7-5eb0-446a-8f4f-977d471453ff/scratchpad/triage_cache')


def import_solvers():
    """(volcanic, impact) solver modules, with or without bpy."""
    if BLENDER_DIR not in sys.path:
        sys.path.insert(0, BLENDER_DIR)
    if 'eidoblend.terrain' not in sys.modules:
        try:
            import bpy  # noqa: F401  (inside Blender the real package loads)
        except ImportError:
            import eidoblend  # noqa: F401  (its __init__ imports nothing)
            pkg = types.ModuleType('eidoblend.terrain')        # outside: the package by its path alone
            pkg.__path__ = [TERRAIN_DIR]
            sys.modules['eidoblend.terrain'] = pkg
    from eidoblend.terrain.solvers import impact, volcanic
    return volcanic, impact


def refs():
    if REFERENCE_DIR not in sys.path:
        sys.path.insert(0, REFERENCE_DIR)
    import landform_refs
    return landform_refs


def grid(n, pixel_m):
    """Cell-centre X, Y (metres) of an n x n tile centred on 0, row 0 south."""
    c = (np.arange(n) + 0.5 - n / 2.0) * pixel_m
    return np.meshgrid(c, c)


def load_reference(name):
    """(h float64 metres row 0 south, meta, X, Y)."""
    R = refs()
    h, meta = R.load(name)
    h = h[::-1].astype(np.float64)
    X, Y = grid(h.shape[0], meta['pixel_size_m'])
    return h, meta, X, Y


def load_reference_water(name):
    """The water mask (uint8, row 0 south) and bodies, or None."""
    R = refs()
    w = R.load_water(name)
    if w is None:
        return None
    return w[0][::-1], w[1]


def load_sp_crater():
    """(h metres above the tile's lowest point, row 0 south, pixel_m, X, Y) from the triage's Terrain Tiles cache."""
    d = np.load(os.path.join(SP_CACHE, 'real_sp_crater.npz'), allow_pickle=False)
    meta = json.loads(str(d['meta']))
    h = d['height'].astype(np.float64) * meta['vs'] * meta['W']
    p = meta['W'] / h.shape[0]
    X, Y = grid(h.shape[0], p)
    return h, p, X, Y


# ---------------------------------------------------------------- measures

def slope_deg(h, pixel_m):
    gy, gx = np.gradient(h, pixel_m)
    return np.degrees(np.arctan(np.hypot(gx, gy)))


def radial_slope_deg(h, pixel_m, X, Y, centre):
    """The downhill-outward component of the slope, degrees (positive where the ground falls away from centre)."""
    gy, gx = np.gradient(h, pixel_m)
    dx, dy = X - centre[0], Y - centre[1]
    r = np.maximum(np.hypot(dx, dy), 1e-6)
    return np.degrees(np.arctan(-(gx * dx + gy * dy) / r))


def ring_median(v, X, Y, centre, radii, half_width):
    r = np.hypot(X - centre[0], Y - centre[1])
    return np.array([np.median(v[np.abs(r - q) < half_width]) for q in radii])


def compass_deg(X, Y, centre):
    return (np.degrees(np.arctan2(X - centre[0], Y - centre[1])) + 360.0) % 360.0


def sector_median(v, X, Y, centre, radius, half_width, azimuth, half_angle=22.5):
    r = np.hypot(X - centre[0], Y - centre[1])
    az = compass_deg(X, Y, centre)
    sel = (np.abs(r - radius) < half_width) & (np.abs(((az - azimuth + 180.0) % 360.0) - 180.0) < half_angle)
    return float(np.median(v[sel]))


def rim_crests(h, X, Y, centre, r_min, r_max, step_deg=5.0):
    """Per azimuth (every step_deg), the highest cell between r_min and r_max: (azimuths, radii, heights)."""
    r = np.hypot(X - centre[0], Y - centre[1])
    az = compass_deg(X, Y, centre)
    azs = np.arange(0.0, 360.0, step_deg)
    rr, zz = [], []
    for a in azs:
        sel = (np.abs(((az - a + 180.0) % 360.0) - 180.0) < step_deg / 2) & (r > r_min) & (r < r_max)
        k = np.argmax(np.where(sel, h, -1e30))
        rr.append(r.ravel()[k])
        zz.append(h.ravel()[k])
    return azs, np.array(rr), np.array(zz)


def harmonics(values, azimuths_deg, kmax=12):
    """Amplitude (fraction of the mean) and phase (degrees) of harmonics 1..kmax of a quantity sampled evenly in
    azimuth: values = mean (1 + sum a_k cos(k az + phase_k))."""
    th = np.radians(azimuths_deg)
    m = values.mean()
    out = {}
    for k in range(1, kmax + 1):
        c = np.sum(values * np.exp(-1j * k * th)) * 2.0 / len(th)
        out[k] = (float(abs(c) / m), float(np.degrees(np.angle(c))))
    return out


def spearman(a, b):
    ra = np.argsort(np.argsort(a)).astype(float)
    rb = np.argsort(np.argsort(b)).astype(float)
    ra -= ra.mean()
    rb -= rb.mean()
    return float(np.sum(ra * rb) / math.sqrt(np.sum(ra * ra) * np.sum(rb * rb)))


def box_down(a, s):
    if s == 1:
        return a
    n = a.shape[0] // s
    return a.reshape(n, s, n, s).mean(axis=(1, 3))


# ---------------------------------------------------------------- the analytic shapes on their references

def _base_noise(volcanic, X, Y, scales_amps, seed):
    out = np.zeros_like(X)
    for i, (scale, amp) in enumerate(scales_amps):
        out += amp * volcanic.fbm(X, Y, scale, seed + 13 * i, octaves=3)
    return out


TILES = dict(mount_fuji=(1000, 40.0), crater_lake=(1000, 14.0), meteor_crater=(1000, 3.0), sp_crater=(1024, 8000.0 / 1024),
             cinder_field=(1024, 8000.0 / 1024))
CONTEXTS = dict(mount_fuji=(1000, 120.0), crater_lake=(1000, 42.0), meteor_crater=(1000, 15.0))


def generated(name, supersample=2, n=None, pixel_m=None):
    """The analytic shape for a reference, on the reference's tile (same extent and pixel, row 0 south), evaluated at
    supersample x the pixel and box-averaged to it (as the judge compares); n and pixel_m override the tile (the
    eye view's wider context: the same world-space surface, coarser). Returns dict(h, pixel_m, X, Y, centre,
    water (mask uint8 row 0 south, bodies) or None, note)."""
    volcanic, impact = import_solvers()
    n0, p0 = TILES[name]
    n = n0 if n is None else int(n)
    p = p0 if pixel_m is None else float(pixel_m)
    if name == 'mount_fuji':
        P = volcanic.FUJI
        Xs, Ys = grid(n * supersample, p / supersample)
        h = volcanic.fuji_surface(Xs, Ys) + _base_noise(volcanic, Xs, Ys, [(6000.0, 25.0), (900.0, 6.0)], 101)
        centre = P['centre']
        water = None
        note = 'FUJI preset: exp cone + crater + Hoei + rift cones on a placeholder plain'
    elif name == 'crater_lake':
        P = volcanic.CRATER_LAKE
        Xs, Ys = grid(n * supersample, p / supersample)
        h = volcanic.crater_lake_surface(Xs, Ys) + _base_noise(volcanic, Xs, Ys, [(2500.0, 10.0), (400.0, 2.0)], 202)
        centre = P['centre']
        note = 'CRATER_LAKE preset: edifice + scalloped collapse + talus + Wizard Island'
        water = 'lake'
    elif name == 'meteor_crater':
        P = impact.METEOR_CRATER
        Xs, Ys = grid(n * supersample, p / supersample)
        plain = 1682.1
        h = plain + impact.impact_crater(Xs, Ys, **P)['delta'] + _base_noise(volcanic, Xs, Ys,
                                                                             [(600.0, 1.5), (120.0, 0.5)], 303)
        centre = P['centre']
        water = None
        note = 'METEOR_CRATER preset: Pike bowl + 0.143 D infill + square-ish rim + ejecta on a placeholder plain'
    elif name == 'sp_crater':
        P = volcanic.SP_CRATER
        Xs, Ys = grid(n * supersample, p / supersample)
        base = 158.0
        h = base + volcanic.cinder_cone(Xs, Ys, **P) + _base_noise(volcanic, Xs, Ys, [(1500.0, 4.0), (250.0, 1.0)], 404)
        centre = P['at']
        water = None
        note = 'SP_CRATER preset: Wood cone at repose on a placeholder plain'
    elif name == 'cinder_field':
        Xs, Ys = grid(n * supersample, p / supersample)
        cones = volcanic.cinder_field((-4000.0, -4000.0, 8000.0), count=12, seed=7)
        h = 1900.0 + volcanic.cinder_cones(Xs, Ys, cones) + _base_noise(volcanic, Xs, Ys,
                                                                       [(2500.0, 12.0), (400.0, 2.0)], 505)
        centre = (0.0, 0.0)
        water = None
        note = 'cinder_field: 12 fresh cones along 2 vent lines (aging comes later) on a placeholder lava plateau'
    else:
        raise KeyError(name)
    h = box_down(h, supersample)
    X, Y = grid(n, p)
    if water == 'lake':
        lake = P['lake_m']
        r = np.hypot(X - centre[0], Y - centre[1])
        inside = (h < lake) & (r < P['rim_radius_m'])
        mask = np.where(inside, 128, 0).astype(np.uint8)
        water = (mask, [dict(kind='lake', name='lake', mask_value=128, level_m=lake)])
    return dict(h=h, pixel_m=p, X=X, Y=Y, centre=centre, water=water, note=note)


def with_lake_surface(h, water):
    """The DEM's view of a lake: its flat surface where the mask says water."""
    if water is None:
        return h
    mask, bodies = water
    out = h.copy()
    for b in bodies:
        m = mask == b['mask_value']
        out[m] = b['level_m']
    return out
