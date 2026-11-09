"""Composition: world-space shapes, stamps, uplift fields and flatten areas (design sections 4.1 and 4.13).

Every shape is a function of world (x, y) metres, given as a JSON spec, so a level samples the same shape at its own
cells (inputs are functions of world position) and a recipe stays data.

    from eidoblend.terrain.core import compose as C
    x, y = level.xy()
    s = C.shape({'kind': 'cone', 'centre': [0, 0], 'radius_m': 18000, 'height_m': 3700}, x, y)
    h = C.stamp(h, s, 'smooth_max', width_m=40.0)            # add | max | min | smooth_max | smooth_min | blend
    U = 3e-3 * C.uplift({'kind': 'ridge', 'centre': [0, 0], 'azimuth_deg': 30, 'length_m': 14000,
                         'width_m': 7000, 'spurs': 6}, x, y, seed=3)          # 0..1, no creases
    h0 = C.start_surface(spec, x, y, seed=3, height_m=600)  # the uplift shape as a rough 600 m start (a flat start
                                                            # makes corduroy for millions of years)
    rigid = C.flatten_mask(areas, x, y)                     # 1 inside flatten areas: U = K = 0 there while eroding
    heights = C.resolve_flat_heights(areas, [(level, h), ...])   # each area's height (default: its median on the
    h2 = C.flatten_exact(h, x, y, areas, heights)                # finest level holding it); exact, C1 falloff

Shapes (all lengths in metres, heights in metres, angles in degrees):
    cone      centre, radius_m, height_m, profile 'linear' | 'cosine' | 'exp' (lambda_m), crater_radius_m
    bowl      centre, radius_m, depth_m, exponent (2: parabolic): negative inside the radius, 0 outside
    profile   centre, r_m [...], z_m [...]: a radial profile table, linearly interpolated (constant past its ends)
    array     path (.npy, metres, row 0 south) or values, x0, y0, cell: a painted array, sampled bilinearly
    dome / ridge / plateau / massif: the uplift shapes, 0..1 (see uplift())
    field     any core/world_noise field spec ({'kind': 'fbm', ...}) under 'of'
"""

from __future__ import annotations

import math

import numpy as np

from . import grid
from . import world_noise as N


# ---------------------------------------------------------------------------------------------- blending ---

def smooth_min(a, b, k):
    """Polynomial smooth minimum (C1) with a blend width of k metres; min(a, b) when k <= 0."""
    if k <= 0:
        return np.minimum(a, b)
    hh = np.maximum(k - np.abs(a - b), 0.0) / k
    return np.minimum(a, b) - hh * hh * k * 0.25


def smooth_max(a, b, k):
    return -smooth_min(-np.asarray(a, np.float64), -np.asarray(b, np.float64), k)


def stamp(h, s, mode='add', width_m=0.0, mask=None):
    """Apply shape values s to heights h: 'add', 'max', 'min', 'smooth_max' / 'smooth_min' (C1, width_m metres)
    or 'blend' (h (1 - mask) + s mask). Returns float32."""
    h = np.asarray(h, np.float64)
    s = np.asarray(s, np.float64)
    if mode == 'add':
        out = h + s
    elif mode == 'max':
        out = np.maximum(h, s)
    elif mode == 'min':
        out = np.minimum(h, s)
    elif mode == 'smooth_max':
        out = smooth_max(h, s, float(width_m))
    elif mode == 'smooth_min':
        out = smooth_min(h, s, float(width_m))
    elif mode == 'blend':
        if mask is None:
            raise ValueError("stamp mode 'blend' needs a mask")
        m = np.clip(np.asarray(mask, np.float64), 0.0, 1.0)
        out = h * (1.0 - m) + s * m
    else:
        raise ValueError(f"stamp mode {mode!r} is one of 'add', 'max', 'min', 'smooth_max', 'smooth_min', 'blend'")
    return out.astype(np.float32)


# ------------------------------------------------------------------------------------------------- shapes ---

def _xy0(spec):
    c = spec.get('centre', (0.0, 0.0))
    return float(c[0]), float(c[1])


def _radial(spec, x, y):
    cx, cy = _xy0(spec)
    return np.hypot(np.asarray(x, np.float64) - cx, np.asarray(y, np.float64) - cy)


def shape(spec, x, y, seed=0):
    """A world-space shape's values at (x, y) (see the module doc). float64 like x."""
    kind = spec.get('kind')
    if kind == 'cone':
        r = _radial(spec, x, y)
        R, H = float(spec['radius_m']), float(spec['height_m'])
        prof = spec.get('profile', 'linear')
        t = np.clip(r / R, 0.0, 1.0)
        if prof == 'linear':
            z = H * (1.0 - t)
        elif prof == 'cosine':
            z = H * 0.5 * (1.0 + np.cos(np.pi * t))
        elif prof == 'exp':                                       # the stratovolcano's (design 4.7), crater excluded
            lam = float(spec['lambda_m'])
            rc = float(spec.get('crater_radius_m', 0.0))
            e_r = np.exp(-(np.maximum(r, rc) - rc) / lam)
            e_R = math.exp(-(R - rc) / lam)
            z = H * np.clip((e_r - e_R) / (1.0 - e_R), 0.0, None)
        else:
            raise ValueError(f"cone profile {prof!r} is 'linear', 'cosine' or 'exp'")
        return z
    if kind == 'bowl':
        r = _radial(spec, x, y)
        R, D, p = float(spec['radius_m']), float(spec['depth_m']), float(spec.get('exponent', 2.0))
        return np.where(r < R, -D * (1.0 - (r / R) ** p), 0.0)
    if kind == 'profile':
        r = _radial(spec, x, y)
        return np.interp(r, np.asarray(spec['r_m'], np.float64), np.asarray(spec['z_m'], np.float64))
    if kind == 'array':
        a = np.load(spec['path']) if 'path' in spec else np.asarray(spec['values'], np.float64)
        return grid.sample_bilinear(a, float(spec['x0']), float(spec['y0']), float(spec['cell']), x, y)
    if kind in ('dome', 'ridge', 'plateau', 'massif'):
        return uplift(spec, x, y, seed)
    if kind == 'field':
        return N.field(spec['of'], x, y, seed)
    raise ValueError(f"shape kind {kind!r} is one of 'cone', 'bowl', 'profile', 'array', 'dome', 'ridge', "
                     f"'plateau', 'massif', 'field'")


# ------------------------------------------------------------------------------------------- uplift shapes ---

def _segment_dist(x, y, ax, ay, bx, by):
    """Distance from (x, y) to the segment a-b (C1 in x, y away from the segment itself)."""
    vx, vy = bx - ax, by - ay
    L2 = max(vx * vx + vy * vy, 1e-12)
    t = np.clip(((x - ax) * vx + (y - ay) * vy) / L2, 0.0, 1.0)
    return np.hypot(x - (ax + t * vx), y - (ay + t * vy))


def _gauss(d, sigma):
    return np.exp(-0.5 * (d / max(sigma, 1e-9)) ** 2)


class _Noise:
    """fbm and warp at the sample points: numpy at any (x, y) (the twin), or on the GPU when `level` is given, in
    which case (x, y) must be level.xy() (core/world_noise.field_gpu)."""

    def __init__(self, x, y, level=None):
        self.x0, self.y0, self.level = x, y, level
        self.dx = self.dy = None                                   # the warp, once applied

    def fbm(self, wavelength, octaves, seed):
        if self.level is None:
            x = self.x0 if self.dx is None else self.x0 + self.dx
            y = self.y0 if self.dy is None else self.y0 + self.dy
            return N.fbm(x, y, wavelength, octaves, seed=seed)
        spec = {'kind': 'fbm', 'wavelength_m': wavelength, 'octaves': octaves}
        disp = None if self.dx is None else (self.dx, self.dy)
        return N.field_gpu(spec, self.level, seed, disp=disp).astype(np.float64)

    def warp(self, amp, wavelength, seed, octaves=3):
        """Apply N.warp's displacement (the same fields and seeds, both read at the unwarped point); returns the
        warped (x, y)."""
        dx = amp * self.fbm(wavelength, octaves, seed * 2 + 101)
        dy = amp * self.fbm(wavelength, octaves, seed * 2 + 102)
        self.dx, self.dy = dx, dy
        return self.x0 + self.dx, self.y0 + self.dy


def uplift(spec, x, y, seed=0, level=None):
    """An uplift shape, about 0..1, smooth everywhere (Gaussian falloffs of distances in a domain-warped plane,
    unions by smooth maximum: no creases, design 4.1), with multi-scale texture at kilometre scales. Common keys:
    centre [x, y], warp_m (default 8 % of the size), texture (about 1.5 x the texture's relative standard
    deviation; default 0.25, about +-17 %).
      dome      radius_m
      ridge     azimuth_deg, length_m, width_m (the spine's half-width scale), spurs (count), spur_length_m
      plateau   radius_m, edge_m (the width of the rim's fall)
      massif    radius_m, peaks (count)
    With `level` (and x, y = level.xy()) the noise is evaluated on the GPU: numpy needs about a second per noise
    lattice at 1024^2, and an uplift uses a dozen."""
    kind = spec['kind']
    s = int(seed) + int(spec.get('seed', 0))
    x = np.asarray(x, np.float64)
    y = np.asarray(y, np.float64)
    noise = _Noise(x, y, level)
    cx, cy = _xy0(spec)
    size = float(spec.get('radius_m', spec.get('length_m', 10000.0) * 0.5))
    wm = float(spec.get('warp_m', 0.08 * size))
    if wm > 0:
        x, y = noise.warp(wm, max(size * 0.6, 1.0), s + 11)
    rng = np.random.default_rng(abs(s) * 7919 + 17)
    if kind == 'dome':
        f = _gauss(np.hypot(x - cx, y - cy), size * 0.5)
    elif kind == 'plateau':
        edge = float(spec.get('edge_m', 0.2 * size))
        r = np.hypot(x - cx, y - cy)
        t = np.clip((size - r) / max(edge, 1e-9), 0.0, 1.0)
        f = t * t * (3.0 - 2.0 * t)
    elif kind == 'ridge':
        az = math.radians(float(spec.get('azimuth_deg', 0.0)))
        L, W = float(spec.get('length_m', 10000.0)), float(spec.get('width_m', 4000.0))
        dx, dy = math.sin(az), math.cos(az)                      # azimuth from north, clockwise
        ax, ay, bx, by = cx - dx * L / 2, cy - dy * L / 2, cx + dx * L / 2, cy + dy * L / 2
        f = _gauss(_segment_dist(x, y, ax, ay, bx, by), W * 0.5)
        n_sp = int(spec.get('spurs', 0))
        sl = float(spec.get('spur_length_m', 0.45 * W))
        for k in range(n_sp):
            t = (k + 0.5 + rng.uniform(-0.3, 0.3)) / n_sp
            px, py = ax + (bx - ax) * t, ay + (by - ay) * t
            side = 1.0 if k % 2 == 0 else -1.0
            ang = az + side * math.radians(90.0 + rng.uniform(-25.0, 25.0))
            ln = sl * rng.uniform(0.6, 1.3)
            ex, ey = px + math.sin(ang) * ln, py + math.cos(ang) * ln
            sp = 0.8 * _gauss(_segment_dist(x, y, px, py, ex, ey), W * 0.22)
            f = smooth_max(f, sp, 0.15)
    elif kind == 'massif':
        n_pk = int(spec.get('peaks', 5))
        f = 0.6 * _gauss(np.hypot(x - cx, y - cy), size * 0.55)
        for _ in range(n_pk):
            a, r = rng.uniform(0, 2 * math.pi), size * math.sqrt(rng.uniform(0.0, 0.5))
            px, py = cx + r * math.cos(a), cy + r * math.sin(a)
            f = smooth_max(f, rng.uniform(0.6, 1.0) * _gauss(np.hypot(x - px, y - py), size * rng.uniform(0.18, 0.35)),
                           0.2)
    else:
        raise ValueError(f"uplift kind {kind!r} is 'dome', 'ridge', 'plateau' or 'massif'")
    tex = float(spec.get('texture', 0.25))
    if tex > 0:
        # kilometre-scale texture only (half the shape's size down to an eighth): peaks and saddles along a spine.
        # Finer roughness belongs to the erodibility (the fluvial `roughness` knob), not to the crust's uplift
        n = noise.fbm(size * 0.5, 3, s + 21)
        f = f * np.clip(1.0 + tex * 2.0 * n, 0.0, None)
    return np.clip(f, 0.0, None)


def start_surface(spec, x, y, seed=0, height_m=600.0, roughness=0.4, level=None, peak=None):
    """The rough start of an erosion run: the uplift shape scaled so its peak is height_m, times
    (1 - roughness + roughness noise), as the design probe's start (a flat start makes corduroy for millions of
    years). `peak` is the shape's maximum over the whole terrain (pass the coarsest level's, so every level scales
    alike); default: the maximum here. `level` as in uplift()."""
    u = uplift(spec, x, y, seed, level) if spec.get('kind') in ('dome', 'ridge', 'plateau', 'massif') else \
        shape(spec, x, y, seed)
    size = float(spec.get('radius_m', spec.get('length_m', 10000.0) * 0.5))
    n = 0.5 + 1.5 * _Noise(np.asarray(x, np.float64), np.asarray(y, np.float64), level).fbm(size * 0.3, 5,
                                                                                            int(seed) + 31)
    pk = float(np.max(u)) if peak is None else float(peak)
    return (height_m * u / max(pk, 1e-9) * ((1.0 - roughness) + roughness * n)).astype(np.float32)


# ------------------------------------------------------------------------------------------------- flatten ---

def _areas(areas):
    out = []
    for a in areas or []:
        at = a.get('at')
        if at is None or float(a.get('radius', 0)) <= 0:
            raise ValueError(f"a flatten area needs 'at' (x, y) and a positive 'radius' in metres: {a}")
        out.append({'at': (float(at[0]), float(at[1])), 'radius': float(a['radius']),
                    'falloff': float(a.get('falloff', 0.0)), 'height': a.get('height')})
    return out


def flatten_weight(area, x, y):
    """1 inside the radius, a C1 smoothstep down to 0 at radius + falloff."""
    r = np.hypot(np.asarray(x, np.float64) - area['at'][0], np.asarray(y, np.float64) - area['at'][1])
    if area['falloff'] <= 0:
        return (r <= area['radius']).astype(np.float64)
    t = np.clip((area['radius'] + area['falloff'] - r) / area['falloff'], 0.0, 1.0)
    return t * t * (3.0 - 2.0 * t)


def flatten_mask(areas, x, y):
    """The rigid-block mask of the erosion stages: 1 inside any area's radius plus its falloff (U = K = 0 there, so
    rivers route around or fill against it instead of being dammed by a pinned plate)."""
    m = np.zeros(np.shape(x), np.float32)
    for a in _areas(areas):
        r = np.hypot(np.asarray(x, np.float64) - a['at'][0], np.asarray(y, np.float64) - a['at'][1])
        m = np.maximum(m, (r <= a['radius'] + a['falloff']).astype(np.float32))
    return m


def resolve_flat_heights(areas, level_fields):
    """Each area's flat height: its own 'height', or the median of h inside its radius on the finest level that
    holds the area whole. level_fields: [(Level, h array), ...], coarsest first. Returns [height, ...]."""
    out = []
    for a in _areas(areas):
        if a['height'] is not None:
            out.append(float(a['height']))
            continue
        val = None
        for lv, h in level_fields:
            ext = a['radius'] + a['falloff']
            if lv.contains(a['at'][0] - ext, a['at'][1] - ext) and lv.contains(a['at'][0] + ext, a['at'][1] + ext):
                xs, ys = lv.xy()
                inside = np.hypot(xs - a['at'][0], ys - a['at'][1]) <= a['radius']
                if inside.any():
                    val = float(np.median(np.asarray(h)[inside]))
        if val is None:
            raise ValueError(f"flatten area at {a['at']} (radius {a['radius']} m) is not inside any level")
        out.append(val)
    return out


def flatten_exact(h, x, y, areas, heights):
    """The exact post pass: each area flattened to its height inside its radius, blended with a C1 falloff of
    `falloff` metres. Areas apply in order. Returns float32."""
    out = np.asarray(h, np.float64).copy()
    for a, z in zip(_areas(areas), heights):
        w = flatten_weight(a, x, y)
        out = out * (1.0 - w) + float(z) * w
    return out.astype(np.float32)
