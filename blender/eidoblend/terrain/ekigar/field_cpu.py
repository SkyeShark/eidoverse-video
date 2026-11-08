"""Ekigar's CPU height field (src/core/field_cpu.js), vectorised: the periodic Phacelle base field, tiling arithmetic
and the finite-difference gradient that masks must use.

    cfg = default_config()                         # the reference demo's tuned defaults (Ekigar's v1 preset)
    field = make_field(cfg)                        # frequencies snapped so every lattice period is whole
    r = field.evaluate(x, y)                       # x, y: floats or arrays -> dict(height, dx, dy, ridge, ...)
    g = gradient_fd(field, x, y, h=1/1024)         # slope from central differences: use THIS for masks
    tiling_report(cfg) / snap_freq(freq, tile)     # report, then snap, never a silent seam

The carried gradient (r['dx'], r['dy']) is exact with erosion off and ~29 degrees / 0.42x off at default erosion
strength (the erosion filter drops the derivative of its own onset mask): fine for steering gullies, wrong for
deciding which face is a cliff. gradient_fd is the sanctioned path for slope, aspect and curvature.
"""
from __future__ import annotations

import copy
import math

import numpy as np

from ._tsl import Vec, clamp, lerp as mix      # field_cpu.js's own mix is a + (b - a) * t
from . import noise as _noise
from . import phacelle as _ph

TAU = 6.28318530717959
K0 = 0.3183099
K1 = 0.3678794


def wrap_cell(v, period):
    """Floor-based lattice wrap; period <= 0 (or not finite) means not periodic."""
    if not (period > 0):
        return v
    return v - period * np.floor(v / period)


def noised(x, y, px=0.0, py=0.0):
    """Gradient noise + analytic derivatives: (value, d/dx, d/dy)."""
    return _noise.noised(np.asarray(x, dtype=np.float64), np.asarray(y, dtype=np.float64), px, py)


def fractal_noise(x, y, freq, octaves, lacunarity, gain, tile_x, tile_y):
    """fBm over noised; periods in cell units scale with each octave's frequency, so tile_x / tile_y are given in
    world units. Returns (value, d/dx, d/dy)."""
    v = _noise.fractal_noise(Vec(np.asarray(x, dtype=np.float64), np.asarray(y, dtype=np.float64)),
                             freq, octaves, lacunarity, gain, (tile_x, tile_y))
    return v.x, v.y, v.z


def phacelle_noise(x, y, ndx, ndy, freq, offset, normalization, px=0.0, py=0.0):
    """Phacelle stripes perpendicular to (ndx, ndy): (cos, sin, sideDirX, sideDirY)."""
    r = _ph.phacelle_noise(Vec(np.asarray(x, dtype=np.float64), np.asarray(y, dtype=np.float64)),
                           Vec(ndx, ndy), freq, offset, normalization, (px, py))
    return r.x, r.y, r.z, r.w


def _pow_inv(t, power):
    return 1.0 - np.power(1.0 - clamp(t, 0.0, 1.0), power)


def _ease_out(t):
    v = 1.0 - clamp(t, 0.0, 1.0)
    return 1.0 - v * v


def _smooth_start(t, smoothing):
    # with smoothing == 0 the t >= smoothing arm returns t: no division by zero (t >= 0 at both call sites)
    with np.errstate(divide='ignore', invalid='ignore'):
        return np.where(t >= smoothing, t - 0.5 * smoothing, 0.5 * t * t / np.where(smoothing > 0, smoothing, 1.0))


def erosion_filter(x, y, hs, fade_target_in, p, tile_x, tile_y):
    """The erosion filter, additive over an existing height + gradient field (field_cpu.js erosionFilter).

    hs: (height, dh/dx, dh/dy); p: the 'erosion' block of default_config(). Returns dict(dh, dsx, dsy, magnitude,
    ridgeMap, fadeTarget, combiMask, _lastSloping, _lastGulX)."""
    x = np.asarray(x, dtype=np.float64)
    y = np.asarray(y, dtype=np.float64)
    strength = p['strength'] * p['scale']
    fade = clamp(np.asarray(fade_target_in, dtype=np.float64), -1.0, 1.0)
    hx, hy, hz = hs
    in_x, in_y, in_z = hx, hy, hz
    freq = 1.0 / (p['scale'] * p['cellScale'])
    slope_len = np.maximum(np.hypot(hy, hz), 1e-10)
    magnitude = 0.0
    rmult = 1.0
    R, O, AS = p['rounding'], p['onset'], p['assumedSlope']
    rounding_in = mix(R[1], R[0], clamp(fade + 0.5, 0.0, 1.0)) * R[2]
    combi = _ease_out(_smooth_start(slope_len * O[0], rounding_in * O[0]))
    rm_combi = _ease_out(slope_len * O[2])
    rm_fade = fade
    gsx = mix(hy, (hy / slope_len) * AS[0], AS[1])
    gsy = mix(hz, (hz / slope_len) * AS[0], AS[1])
    last_sloping = 0.0
    last_gul = 0.0
    for _ in range(int(p['octaves'])):
        gl = np.hypot(gsx, gsy)
        big = np.abs(gl) > 1e-10
        nx = np.where(big, gsx / np.where(big, gl, 1.0), gsx)
        ny = np.where(big, gsy / np.where(big, gl, 1.0), gsy)
        c, s, sdx, sdy = phacelle_noise(x * freq, y * freq, nx, ny, p['cellScale'], 0.25, p['normalization'],
                                        tile_x * freq, tile_y * freq)
        pzw0 = sdx * -freq
        pzw1 = sdy * -freq
        sloping = np.abs(s)
        last_sloping = sloping
        sgn = np.sign(s)
        gsx = gsx + sgn * pzw0 * strength * p['gullyWeight']
        gsy = gsy + sgn * pzw1 * strength * p['gullyWeight']
        gul_x, gul_y, gul_z = c, s * pzw0, s * pzw1
        last_gul = gul_x
        fg_x = mix(fade, gul_x * p['gullyWeight'], combi)
        fg_y = mix(0.0, gul_y * p['gullyWeight'], combi)
        fg_z = mix(0.0, gul_z * p['gullyWeight'], combi)
        hx = hx + fg_x * strength
        hy = hy + fg_y * strength
        hz = hz + fg_z * strength
        magnitude += strength
        fade = fg_x
        rfo = mix(R[1], R[0], clamp(gul_x + 0.5, 0.0, 1.0)) * rmult
        new_mask = _ease_out(_smooth_start(sloping * O[1], rfo * O[1]))
        combi = _pow_inv(combi, p['detail']) * new_mask
        rm_fade = mix(rm_fade, gul_x, rm_combi)
        rm_combi = rm_combi * _ease_out(sloping * O[3])
        strength *= p['gain']
        freq *= p['lacunarity']
        rmult *= R[3]
    return {'dh': hx - in_x, 'dsx': hy - in_y, 'dsy': hz - in_z, 'magnitude': magnitude,
            'ridgeMap': rm_fade * (1.0 - rm_combi), 'fadeTarget': fade, 'combiMask': combi,
            '_lastSloping': last_sloping, '_lastGulX': last_gul}


# ------------------------------------------------------------------------------------------- tiling arithmetic ---

def snap_freq(freq, tile):
    """Nearest frequency to `freq` whose period over `tile` is a whole number of cells (unchanged when not tiling)."""
    if not (tile > 0):
        return freq
    n = max(1, round_half_up(freq * tile))
    return n / tile


def round_half_up(v):
    """JS Math.round: halves round toward +infinity."""
    return int(math.floor(v + 0.5))


def tiling_report(cfg):
    """Report, don't silently fix: a stack that cannot tile says so instead of shipping a seam."""
    notes = []
    tile, base, ero = cfg['tile'], cfg['base'], cfg['erosion']
    any_tile = (tile['x'] > 0) or (tile['y'] > 0)
    if not any_tile:
        return {'tiling': False, 'notes': ['not periodic on either axis']}
    if not float(base['lacunarity']).is_integer():
        notes.append(f"base lacunarity {base['lacunarity']} is not an integer — octaves above the first cannot tile")
    if not float(ero['lacunarity']).is_integer():
        notes.append(f"erosion lacunarity {ero['lacunarity']} is not an integer — octaves above the first cannot tile")
    for axis in ('x', 'y'):
        t = tile[axis]
        if not (t > 0):
            continue
        bf = base['frequency']
        ef = 1.0 / (ero['scale'] * ero['cellScale'])
        bp, ep = bf * t, ef * t
        if abs(bp - round_half_up(bp)) > 1e-9:
            notes.append(f'base frequency {_js_num(bf)} gives a {bp:.4f}-cell period on {axis} — snapped to '
                         f'{_js_num(snap_freq(bf, t))}')
        if abs(ep - round_half_up(ep)) > 1e-9:
            notes.append(f"erosion scale {_js_num(ero['scale'])} gives a {ep:.4f}-cell period on {axis} — snapped via "
                         f"scale {1.0 / (snap_freq(ef, t) * ero['cellScale']):.6f}")
    return {'tiling': True, 'notes': notes}


def _js_num(v):
    """A number as JS template strings print it (3 not 3.0)."""
    f = float(v)
    return str(int(f)) if f.is_integer() else repr(f)


def default_config():
    """The author's tuned defaults from the reference demo, as Ekigar's v1 preset. `tile` is in world units; 0 disables
    periodicity on that axis (the ring band is periodic in x only)."""
    return {
        'tile': {'x': 1, 'y': 1},
        'base': {'frequency': 3.0, 'amplitude': 0.125, 'octaves': 3, 'lacunarity': 2, 'gain': 0.1},
        'erosion': {
            'strength': 0.22, 'gullyWeight': 0.5, 'detail': 1.5,
            'rounding': [0.1, 0.0, 0.1, 2.0],     # ridge, crease, input mult, octave mult
            'onset': [1.25, 1.25, 2.8, 1.5],      # input, octave, ridge-input, ridge-octave
            'assumedSlope': [0.7, 1.0],
            'scale': 0.15, 'octaves': 5, 'lacunarity': 2, 'gain': 0.5,
            'cellScale': 0.7, 'normalization': 0.5,
        },
        'heightOffset': [-0.65, 0.0],             # raise/lower bias, peak-preserving mix
    }


class Field:
    """make_field's evaluator: .evaluate(x, y), .config (snapped), .report, .requested."""

    def __init__(self, config, report, requested):
        self.config = config
        self.report = report
        self.requested = requested

    def evaluate(self, x, y):
        c = self.config
        tile, base, ero, hoff = c['tile'], c['base'], c['erosion'], c['heightOffset']
        x = np.asarray(x, dtype=np.float64)
        y = np.asarray(y, dtype=np.float64)
        n0, n1, n2 = fractal_noise(x, y, base['frequency'], base['octaves'], base['lacunarity'], base['gain'],
                                   tile['x'], tile['y'])
        h = n0 * base['amplitude']
        dx = n1 * base['amplitude']
        dy = n2 * base['amplitude']
        fade = clamp(h / (base['amplitude'] * 0.6), -1.0, 1.0)
        h = h * 0.5 + 0.5
        dx = dx * 0.5
        dy = dy * 0.5
        e = erosion_filter(x, y, (h, dx, dy), fade, ero, tile['x'], tile['y'])
        offset = mix(hoff[0], -e['fadeTarget'], hoff[1])
        return {'height': h + e['dh'] + offset * e['magnitude'], 'dx': dx + e['dsx'], 'dy': dy + e['dsy'],
                'ridge': e['ridgeMap'], 'erosionDelta': e['dh'], 'combiMask': e['combiMask'],
                'lastSloping': e['_lastSloping'], 'lastGulX': e['_lastGulX']}


def make_field(cfg=None):
    """Build an evaluator. Frequencies are snapped once, up front, so every sample sees the same lattice; the snap is
    reported on the returned object rather than hidden. If both axes tile and disagree, the x axis wins."""
    cfg = default_config() if cfg is None else cfg
    c = copy.deepcopy(cfg)
    report = tiling_report(c)
    t_ref = c['tile']['x'] if c['tile']['x'] > 0 else c['tile']['y']
    if t_ref > 0:
        c['base']['frequency'] = snap_freq(c['base']['frequency'], t_ref)
        ef = snap_freq(1.0 / (c['erosion']['scale'] * c['erosion']['cellScale']), t_ref)
        c['erosion']['scale'] = 1.0 / (ef * c['erosion']['cellScale'])
    return Field(c, report, cfg)


# ----------------------------------------------- the reference demo's vegetation mask (phacelle_bufferA_erosion) ---

GRASS_HEIGHT = 0.465           # phacelle_common_render.glsl's defines, in the demo's height units
WATER_HEIGHT = 0.36


def reference_hash(x, y):
    """The demo's fract-product hash (phacelle_common_render.glsl hash): only for its tree noise. Ekigar's lattice uses
    the integer hash2 instead, because this one loses all precision at large lattice coordinates."""
    kx, ky = K0, K1
    xx = x * kx + ky
    yy = y * ky + kx
    v = (xx * yy * (xx + yy)) % 1.0
    return -1.0 + 2.0 * ((16.0 * kx * v) % 1.0), -1.0 + 2.0 * ((16.0 * ky * v) % 1.0)


def reference_noised(x, y):
    """The demo's gradient noise (phacelle_common_render.glsl noised) on reference_hash: (value, d/dx, d/dy)."""
    x = np.asarray(x, dtype=np.float64)
    y = np.asarray(y, dtype=np.float64)
    ix, iy = np.floor(x), np.floor(y)
    fx, fy = x - ix, y - iy
    ux = fx * fx * fx * (fx * (fx * 6 - 15) + 10)
    uy = fy * fy * fy * (fy * (fy * 6 - 15) + 10)
    dux = 30 * fx * fx * (fx * (fx - 2) + 1)
    duy = 30 * fy * fy * (fy * (fy - 2) + 1)
    gax, gay = reference_hash(ix, iy)
    gbx, gby = reference_hash(ix + 1, iy)
    gcx, gcy = reference_hash(ix, iy + 1)
    gdx, gdy = reference_hash(ix + 1, iy + 1)
    va = gax * fx + gay * fy
    vb = gbx * (fx - 1) + gby * fy
    vc = gcx * fx + gcy * (fy - 1)
    vd = gdx * (fx - 1) + gdy * (fy - 1)
    q = va - vb - vc + vd
    return (va + ux * (vb - va) + uy * (vc - va) + ux * uy * q,
            gax + ux * (gbx - gax) + uy * (gcx - gax) + ux * uy * (gax - gbx - gcx + gdx) + dux * (uy * q + vb - va),
            gay + ux * (gby - gay) + uy * (gcy - gay) + ux * uy * (gay - gby - gcy + gdy) + duy * (ux * q + vc - va))


def _smoothstep(e0, e1, x):
    t = np.clip((x - e0) / (e1 - e0), 0.0, 1.0)
    return t * t * (3.0 - 2.0 * t)


def get_trees_amount(height, normal_y, occlusion, ridge_map, grass_height=GRASS_HEIGHT, water_height=WATER_HEIGHT):
    """The reference's GetTreesAmount: altitude band x flatness x occlusion x ridge avoidance (x above water), the
    plan's v1 vegetation density. Inputs are the demo's: height in its units, the surface normal's up component,
    occlusion = erosion delta / magnitude + 0.5, and the ridge map. water_height=None leaves the water term out."""
    a = (_smoothstep(grass_height + 0.05, grass_height + 0.01, height + 0.01 + (occlusion - 0.8) * 0.05)
         * _smoothstep(0.0, 0.4, occlusion) * _smoothstep(0.95, 1.0, normal_y) * _smoothstep(-1.4, 0.0, ridge_map))
    if water_height is not None:
        a = a * _smoothstep(water_height + 0.0, water_height + 0.007, height)
    return (a - 0.5) / 0.6


def reference_trees(field, x, y, grass_height=GRASS_HEIGHT, water_height=WATER_HEIGHT):
    """The demo's tree layer over a make_field() terrain: dict(trees, amount, occlusion, normalY). trees > 0 is
    forest; the demo raises the ground by trees / 300 there."""
    x = np.asarray(x, dtype=np.float64)
    y = np.asarray(y, dtype=np.float64)
    c = field.config
    tile, base, ero, hoff = c['tile'], c['base'], c['erosion'], c['heightOffset']
    n0, n1, n2 = fractal_noise(x, y, base['frequency'], base['octaves'], base['lacunarity'], base['gain'],
                               tile['x'], tile['y'])
    h0 = n0 * base['amplitude']
    fade = clamp(h0 / (base['amplitude'] * 0.6), -1.0, 1.0)
    h = h0 * 0.5 + 0.5
    dx, dy = n1 * base['amplitude'] * 0.5, n2 * base['amplitude'] * 0.5
    e = erosion_filter(x, y, (h, dx, dy), fade, ero, tile['x'], tile['y'])
    eroded = h + e['dh'] + mix(hoff[0], -e['fadeTarget'], hoff[1]) * e['magnitude']
    gx, gy = dx + e['dsx'], dy + e['dsy']
    normal_y = 1.0 / np.sqrt(1.0 + gx * gx + gy * gy)
    occlusion = e['dh'] / e['magnitude'] + 0.5
    amount = get_trees_amount(eroded, normal_y, occlusion, e['ridgeMap'], grass_height, water_height)
    nz = reference_noised((x + 0.5) * 200.0, (y + 0.5) * 200.0)[0]
    trees = (1.0 - np.power(nz * 0.5 + 0.5, 2.0) - 1.0 + 1.0 * amount) * 1.5
    return {'trees': trees, 'amount': amount, 'occlusion': occlusion, 'normalY': normal_y, 'height': eroded}


def gradient_fd(field, x, y, h=None):
    """Slope from central differences of the final height: USE THIS FOR MASKS. `h` should match the texel spacing of
    whatever the mask is baked at. Returns dict(dx, dy, slope, aspect)."""
    hx = 1e-4 if h is None else h
    xp = field.evaluate(x + hx, y)['height']
    xm = field.evaluate(x - hx, y)['height']
    yp = field.evaluate(x, y + hx)['height']
    ym = field.evaluate(x, y - hx)['height']
    dx = (xp - xm) / (2 * hx)
    dy = (yp - ym) / (2 * hx)
    return {'dx': dx, 'dy': dy, 'slope': np.hypot(dx, dy), 'aspect': np.arctan2(dy, dx)}
