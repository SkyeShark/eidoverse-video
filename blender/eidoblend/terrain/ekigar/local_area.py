"""The circular local area of a terrain (Ekigar's src/export/local_area.js and the field side of mixed.js), over numpy:
a circle resolved once in WORLD METRES, wrap-aware, with every degenerate case reported, plus the pieces a local /
surround split is built from (the radial weight, the seam ring, area-average downsampling, the wrap-aware crop).

    rc = resolve_cut({'centreMetres': [200, 200], 'radiusMetres': 120, 'fadeMetres': 30},
                     resolve_geometry({'size': 1024, 'worldSize': 400, 'tile': {'x': 1, 'y': 1}}))
    wf = weight_field(rc)                       # weight per texel (1 inside, 0 outside, smooth annulus) + coverage
    crop = crop_local(field, rc)                # the local half at full resolution, wrap-aware, with its weight
    ring = seam_ring(field, rc, 512)            # heights on the cut circle: both halves' shared vertices
    coarse = area_downsample(field, 256, 256)   # the surround, an unbiased low-pass of the field
    split = split_field(field, cut, world_size=400, tile={'x': 1, 'y': 1})

A field is a dict {'data': flat row-major array (row = v), 'size' | 'width' + 'height', 'aux'?, 'worldSize'?}, as in
Ekigar; field_of(heightfield) makes one from a Heightfield (data = field height, aux = the ridge channel). Ekigar's own
frame: x and y in metres run from 0 to the world extent, texel (i, j) samples ((i + 0.5) * mpt, (j + 0.5) * mpt).
A Heightfield's Blender frame is that, shifted by -W/2 (its origin): to_ekigar_metres / from_ekigar_metres convert.

Every function returns what its JS twin returns, with the same keys (camelCase, because a manifest carries them
verbatim), and the parity test (blender/tests/terrain_ekigar/test_local_area_parity.py) runs local_area.js and
mixed.js against these.
"""
from __future__ import annotations

import math
from decimal import Decimal, ROUND_HALF_UP

import numpy as np

from .masks import masks_from_stencil


# ------------------------------------------------------------------------------------------------- JS helpers ---

def _js_num(v):
    """A number as JS's String(v) prints it (120 -> '120', 0.5 -> '0.5', 1e-7 -> '1e-7')."""
    f = float(v)
    if math.isnan(f):
        return 'NaN'
    if math.isinf(f):
        return 'Infinity' if f > 0 else '-Infinity'
    if f.is_integer() and abs(f) < 1e21:
        return str(int(f))
    s = repr(f)
    if 'e' in s:
        mant, ex = s.split('e')
        sign = '-' if ex.startswith('-') else '+'
        s = f'{mant}e{sign}{int(ex.lstrip("+-"))}'
    return s


def _to_fixed(v, digits):
    """JS Number.prototype.toFixed: the exact binary value rounded half away from zero."""
    q = Decimal(1).scaleb(-digits)
    return str(Decimal(float(v)).quantize(q, rounding=ROUND_HALF_UP)) if digits > 0 else \
        str(Decimal(float(v)).quantize(Decimal(1), rounding=ROUND_HALF_UP))


def _js_round(x):
    """Math.round: half toward +infinity."""
    return np.floor(np.asarray(x, dtype=np.float64) + 0.5)


def _get(d, *keys, default=None):
    """The first key of `d` that is present and not None (JS's a ?? b ?? c)."""
    for k in keys:
        v = d.get(k) if isinstance(d, dict) else None
        if v is not None:
            return v
    return default


# ------------------------------------------------------------------------------------------- local_area.js ---

def local_weight(dx, dy, radius, fade):
    """Radial weight: 1 inside the local area, 0 outside, smoothstep across the annulus. Unit-agnostic; arrays
    broadcast."""
    d = np.hypot(np.asarray(dx, dtype=np.float64), np.asarray(dy, dtype=np.float64))
    t = (radius - d) / max(fade, 1e-6)
    w = t * t * (3.0 - 2.0 * t)
    w = np.where(d >= radius, 0.0, w)
    w = np.where(d <= radius - fade, 1.0, w)
    return float(w) if np.ndim(w) == 0 else w


def wrap_delta(d, period):
    """Signed shortest delta on a periodic axis of length `period` (period <= 0: not periodic, d unchanged)."""
    if not (period is not None and period > 0):
        return d
    h = period / 2.0
    v = np.fmod(np.asarray(d, dtype=np.float64), period)
    v = np.where(v > h, v - period, np.where(v < -h, v + period, v))
    return float(v) if np.ndim(v) == 0 else v


def resolve_geometry(g):
    """Field geometry, normalised: {width, height, worldX, worldY, mptX, mptY, wrapX, wrapY, tile} from
    {size | width + height, worldSize: number | {x, y}, tile?: {x, y}}."""
    width = _get(g, 'width', 'size')
    height = _get(g, 'height', 'size', default=width)
    if not (width is not None and width > 0) or not (height is not None and height > 0):
        raise ValueError('resolve_geometry: need size, or width and height')
    ws = _get(g, 'worldSize', default=400)
    if isinstance(ws, dict):
        world_x = ws['x']
        world_y = ws['y'] if ws.get('y') is not None else ws['x']
    else:
        world_x = world_y = ws
    tile = _get(g, 'tile', default={'x': 0, 'y': 0})
    return {
        'width': width, 'height': height,
        'worldX': world_x, 'worldY': world_y,
        'mptX': world_x / width, 'mptY': world_y / height,
        'wrapX': (tile.get('x') if tile.get('x') is not None else 0) > 0,
        'wrapY': (tile.get('y') if tile.get('y') is not None else 0) > 0,
        'tile': tile,
    }


def resolve_cut(cut, geometry):
    """A cut ({cx, cy, radius, fade} as fractions of the tile edge, or {centreMetres, radiusMetres, fadeMetres}) in
    metres, texels and diagnostics. Metres win when both are given, and the conflict is reported. Degenerate cases
    (fade wider than the radius, a circle swallowing the tile, a circle off a non-periodic edge, a sub-texel fade)
    become warnings, never silent changes."""
    G = geometry if geometry.get('mptX') else resolve_geometry(geometry)
    warnings = []

    def pick(metres, fraction, extent, name):
        if metres is not None and fraction is not None:
            warnings.append(f'{name}: both metres ({_js_num(metres)}) and fraction ({_js_num(fraction)}) given '
                            f'— metres win')
        if metres is not None:
            return float(metres)
        if fraction is not None:
            return float(fraction) * extent
        return None

    cm = cut.get('centreMetres') or [None, None]
    cx = pick(cm[0] if len(cm) > 0 else None, cut.get('cx'), G['worldX'], 'centre.x')
    cx = G['worldX'] / 2 if cx is None else cx
    cy = pick(cm[1] if len(cm) > 1 else None, cut.get('cy'), G['worldY'], 'centre.y')
    cy = G['worldY'] / 2 if cy is None else cy

    if cut.get('radiusMetres') is None and cut.get('radius') is not None and abs(G['worldX'] - G['worldY']) > 1e-9:
        warnings.append(f"radius given as a fraction on a non-square world ({_js_num(G['worldX'])}x"
                        f"{_js_num(G['worldY'])} m) — scaled against x; give radiusMetres to be unambiguous")
    r = pick(cut.get('radiusMetres'), cut.get('radius'), G['worldX'], 'radius')
    if r is None:
        r = 0.28 * G['worldX']
    f = pick(cut.get('fadeMetres'), cut.get('fade'), G['worldX'], 'fade')
    if f is None:
        f = 0.25 * r
    if not (r > 0):
        raise ValueError(f'resolve_cut: radius must be positive, got {_js_num(r)} m')
    if f < 0:
        warnings.append(f'fade {_js_num(f)} m is negative — clamped to 0')
        f = 0.0
    if f > r:
        warnings.append(f'fade {_to_fixed(f, 2)} m exceeds radius {_to_fixed(r, 2)} m — clamped to the radius, so '
                        f'the full-fidelity core is a single point. Reduce the fade.')
        f = r
    core = r - f
    if core <= 0:
        warnings.append('the local area has no full-fidelity core: every texel inside it is partly the surround')
    fade_texels = min(f / G['mptX'], f / G['mptY'])
    if f > 0 and fade_texels < 1:
        warnings.append(f"fade {_to_fixed(f, 3)} m is under one texel ({_to_fixed(G['mptX'], 3)} m) — it will read "
                        f"as a hard edge")
    farthest = 0.0
    for x, y in ((0, 0), (G['worldX'], 0), (0, G['worldY']), (G['worldX'], G['worldY'])):
        farthest = max(farthest, math.hypot(wrap_delta(x - cx, G['worldX'] if G['wrapX'] else 0),
                                            wrap_delta(y - cy, G['worldY'] if G['wrapY'] else 0)))
    vanishes = r >= farthest
    if vanishes:
        warnings.append(f'radius {_to_fixed(r, 1)} m covers the whole tile (farthest point is {_to_fixed(farthest, 1)} m)'
                        f' — the surround would be empty; use a plain local export instead')
    clipped = {
        'xMin': (not G['wrapX']) and cx - r < 0,
        'xMax': (not G['wrapX']) and cx + r > G['worldX'],
        'yMin': (not G['wrapY']) and cy - r < 0,
        'yMax': (not G['wrapY']) and cy + r > G['worldY'],
    }
    any_clip = any(clipped.values())
    if any_clip:
        warnings.append('the local circle runs off a non-periodic tile edge — the part outside the tile does not '
                        'exist, so the local area is a truncated disc there')
    rtx, rty = r / G['mptX'], r / G['mptY']
    ctx, cty = cx / G['mptX'], cy / G['mptY']
    x0, x1 = math.floor(ctx - rtx), math.ceil(ctx + rtx)
    y0, y1 = math.floor(cty - rty), math.ceil(cty + rty)
    if not G['wrapX']:
        x0, x1 = max(0, x0), min(G['width'], x1)
    if not G['wrapY']:
        y0, y1 = max(0, y0), min(G['height'], y1)
    return {
        'geometry': G,
        'centreMetres': [cx, cy],
        'centreFraction': [cx / G['worldX'], cy / G['worldY']],
        'radiusMetres': r,
        'fadeMetres': f,
        'coreRadiusMetres': core,
        'radiusFraction': r / G['worldX'],
        'fadeFraction': f / G['worldX'],
        'radiusTexels': [rtx, rty],
        'centreTexels': [ctx, cty],
        'crop': {'x0': x0, 'y0': y0, 'x1': x1, 'y1': y1, 'w': x1 - x0, 'h': y1 - y0},
        'clipped': clipped, 'anyClip': any_clip, 'surroundVanishes': vanishes,
        'farthestCornerMetres': farthest,
        'warnings': warnings,
    }


def weight_at_metres(rc, xm, ym):
    """The local weight at world positions in metres (Ekigar's frame), wrap-aware. Arrays broadcast."""
    G = rc['geometry']
    dx = wrap_delta(np.asarray(xm, dtype=np.float64) - rc['centreMetres'][0], G['worldX'] if G['wrapX'] else 0)
    dy = wrap_delta(np.asarray(ym, dtype=np.float64) - rc['centreMetres'][1], G['worldY'] if G['wrapY'] else 0)
    return local_weight(dx, dy, rc['radiusMetres'], rc['fadeMetres'])


def weight_at_texel(rc, ix, iy):
    """The local weight at texel centres (the one function both halves must agree on)."""
    G = rc['geometry']
    return weight_at_metres(rc, (np.asarray(ix, dtype=np.float64) + 0.5) * G['mptX'],
                            (np.asarray(iy, dtype=np.float64) + 0.5) * G['mptY'])


def weight_field(rc, width=None, height=None):
    """The weight at every texel of a (width x height) grid over the tile (default: the field's), float32 row-major,
    with the core / annulus / surround coverage fractions."""
    G = rc['geometry']
    W = width if width is not None else G['width']
    H = height if height is not None else G['height']
    mx, my = G['worldX'] / W, G['worldY'] / H
    X, Y = np.meshgrid((np.arange(W) + 0.5) * mx, (np.arange(H) + 0.5) * my)
    w = np.asarray(weight_at_metres(rc, X, Y), dtype=np.float64)
    n = W * H
    core = int((w >= 1).sum())
    ann = int(((w > 0) & (w < 1)).sum())
    return {'data': w.astype(np.float32).ravel(), 'width': W, 'height': H,
            'coverage': (core + ann) / n, 'coreCoverage': core / n, 'annulusCoverage': ann / n,
            'surroundCoverage': (n - core - ann) / n}


def _dims(field):
    W = _get(field, 'width', 'size')
    H = _get(field, 'height', 'size', default=W)
    return int(W), int(H)


def _reader(field, G):
    """at(i, j) over integer arrays, wrapping on a periodic axis and clamping on the other."""
    W, H = _dims(field)
    data = np.asarray(field['data'], dtype=np.float64).ravel()

    def at(i, j):
        i = np.asarray(i, dtype=np.int64)
        j = np.asarray(j, dtype=np.int64)
        ii = np.mod(i, W) if G['wrapX'] else np.clip(i, 0, W - 1)
        jj = np.mod(j, H) if G['wrapY'] else np.clip(j, 0, H - 1)
        return data[jj * W + ii]
    return at


def _bilinear(at, fx, fy):
    xi = np.floor(fx)
    yi = np.floor(fy)
    tx, ty = fx - xi, fy - yi
    xi = xi.astype(np.int64)
    yi = yi.astype(np.int64)
    return (at(xi, yi) * (1 - tx) * (1 - ty) + at(xi + 1, yi) * tx * (1 - ty)
            + at(xi, yi + 1) * (1 - tx) * ty + at(xi + 1, yi + 1) * tx * ty)


def seam_ring(field, rc, samples=512):
    """Heights on the cut circle, `samples` points from angle 0: [{angle, metres, uv, height}, ...]. Two meshes
    stitched hard at the circle must both build their inner ring from this, or they crack. Bilinear from the
    full-resolution field, wrap-aware."""
    G = rc['geometry']
    W, H = _dims(field)
    at = _reader(field, G)
    a = np.arange(samples, dtype=np.float64) / samples * math.pi * 2
    xm = rc['centreMetres'][0] + np.cos(a) * rc['radiusMetres']
    ym = rc['centreMetres'][1] + np.sin(a) * rc['radiusMetres']
    h = _bilinear(at, xm / (G['worldX'] / W) - 0.5, ym / (G['worldY'] / H) - 0.5)
    return [{'angle': float(a[k]), 'metres': [float(xm[k]), float(ym[k])],
             'uv': [float(xm[k] / G['worldX']), float(ym[k] / G['worldY'])], 'height': float(h[k])}
            for k in range(samples)]


def _box_weights(n_in, n_out):
    """The (n_out, n_in) overlap matrix of area_downsample along one axis, JS loop bounds and clamps included."""
    s = n_in / n_out
    M = np.zeros((n_out, n_in))
    for y in range(n_out):
        j0, j1 = y * s, (y + 1) * s
        for j in range(math.floor(j0), math.ceil(j1)):
            wy = min(j + 1, j1) - max(j, j0)
            if wy <= 0:
                continue
            M[y, min(n_in - 1, j)] += wy
    return M


def area_downsample(field, out_w, out_h):
    """Downsample by area average (a box filter): the coarse field stays an unbiased low-pass of the fine one, where
    point sampling aliases its detail. Returns {data (flat float64), width, height}."""
    W, H = _dims(field)
    d = np.asarray(field['data'], dtype=np.float64).reshape(H, W)
    My, Mx = _box_weights(H, out_h), _box_weights(W, out_w)
    acc = My @ d @ Mx.T
    wsum = np.outer(My.sum(1), Mx.sum(1))
    out = np.where(wsum > 0, acc / np.where(wsum > 0, wsum, 1.0), 0.0)
    return {'data': out.ravel(), 'width': out_w, 'height': out_h}


def sample_field_metres(field, G, xm, ym):
    """Bilinear read at world positions (metres, Ekigar's frame), texel-centre convention, wrap-aware."""
    W, H = _dims(field)
    at = _reader(field, G)
    v = _bilinear(at, np.asarray(xm, dtype=np.float64) / (G['worldX'] / W) - 0.5,
                  np.asarray(ym, dtype=np.float64) / (G['worldY'] / H) - 0.5)
    return float(v) if np.ndim(v) == 0 else v


def sample_field_nearest_metres(field, G, xm, ym):
    """Nearest read (what point sampling costs, for comparison)."""
    W, H = _dims(field)
    at = _reader(field, G)
    i = _js_round(np.asarray(xm, dtype=np.float64) / (G['worldX'] / W) - 0.5).astype(np.int64)
    j = _js_round(np.asarray(ym, dtype=np.float64) / (G['worldY'] / H) - 0.5).astype(np.int64)
    v = at(i, j)
    return float(v) if np.ndim(v) == 0 else v


def crop_local(field, rc):
    """The local half at full resolution, wrap-aware: {data (float64), mask (uint8 weight), maskF (float32 weight),
    w, h, x0, y0}, flat row-major. The window is resolve_cut's, so the two never disagree."""
    G = rc['geometry']
    c = rc['crop']
    at = _reader(field, G)
    X, Y = np.meshgrid(np.arange(c['w']) + c['x0'], np.arange(c['h']) + c['y0'])
    data = at(X, Y)
    v = np.asarray(weight_at_texel(rc, X, Y), dtype=np.float64)
    return {'data': data.ravel(), 'mask': _js_round(v * 255).astype(np.uint8).ravel(),
            'maskF': v.astype(np.float32).ravel(), 'w': c['w'], 'h': c['h'], 'x0': c['x0'], 'y0': c['y0']}


# ---------------------------------------------------------------------------------------- mixed.js (field) ---

def split_field(field, cut, world_size=None, tile=None, seam_samples=512):
    """Split a field into its local cutout and the surround's weight (mixed.js splitField): {cut, weight, local,
    localMask, coverage, coreCoverage, annulusCoverage, surroundCoverage, seam, warnings}."""
    W, H = _dims(field)
    G = resolve_geometry({'width': W, 'height': H,
                          'worldSize': world_size if world_size is not None else field.get('worldSize', 400),
                          'tile': tile if tile is not None else {'x': 0, 'y': 0}})
    rc = resolve_cut(cut, G)
    wf = weight_field(rc)
    crop = crop_local(field, rc)
    return {
        'cut': rc,
        'weight': wf['data'],
        'local': {'data': crop['data'], 'w': crop['w'], 'h': crop['h'], 'x0': crop['x0'], 'y0': crop['y0']},
        'localMask': {'data': crop['mask'], 'w': crop['w'], 'h': crop['h']},
        'coverage': wf['coverage'], 'coreCoverage': wf['coreCoverage'],
        'annulusCoverage': wf['annulusCoverage'], 'surroundCoverage': wf['surroundCoverage'],
        'seam': seam_ring(field, rc, seam_samples),
        'warnings': rc['warnings'],
    }


def masks_used_by(layers):
    """Legacy payload migration helper: the terrain mask sources an old per-layer mask stack used."""
    used = set()
    for layer in layers or []:
        legacy = (layer.get('legacy') or {}).get('maskStack') if isinstance(layer.get('legacy'), dict) else None
        for c in (legacy if legacy is not None else (layer.get('maskStack') or [])):
            if c.get('enabled') is False:
                continue
            if c.get('type') == 'terrain':
                used.add((c.get('params') or {}).get('source') or 'slope')
    return sorted(used)


def resolve_driver_field(driver, field):
    """One field-density driver from a number, a callable f(u, v), an array of W*H samples, a field dict, or None
    (the terrain height, the implicit driver)."""
    W, H = _dims(field)
    if isinstance(driver, dict) and driver.get('data') is not None:
        dw = _get(driver, 'width', 'size', default=W)
        dh = _get(driver, 'height', 'size', default=H)
        if dw != W or dh != H or len(driver['data']) != W * H:
            raise ValueError(f'driverMask must match the field resolution ({W}x{H})')
        return {'data': driver['data'], 'width': W, 'height': H, 'size': W}
    if isinstance(driver, np.ndarray):
        if driver.size != W * H:
            raise ValueError(f'driverMask must contain {W * H} samples')
        return {'data': driver.ravel(), 'width': W, 'height': H, 'size': W}
    if callable(driver):
        U, V = np.meshgrid((np.arange(W) + 0.5) / W, (np.arange(H) + 0.5) / H)
        data = np.asarray(np.vectorize(driver)(U, V), dtype=np.float64).ravel()
    elif isinstance(driver, (int, float)) and not isinstance(driver, bool):
        data = np.full(W * H, float(driver))
    else:
        data = np.asarray(field['data'], dtype=np.float64).ravel().copy()
    return {'data': data, 'width': W, 'height': H, 'size': W}


def rasterise_local_masks(field, cut, names, vertical_scale=0.3):
    """The terrain masks over the local crop at the FIELD's density (the stencil is the field's texel, as in the
    viewport, so no layer boundary moves), each a uint8 array (crop h x w, flat)."""
    G = cut['geometry']
    W, H = _dims(field)
    at = _reader(field, G)
    c = cut['crop']
    X, Y = np.meshgrid(np.arange(c['w']) + c['x0'], np.arange(c['h']) + c['y0'])
    u = (X + 0.5) / W
    v = (Y + 0.5) / H
    e = 1.0 / W                    # one FIELD texel in uv, on both axes (as mixed.js reads it)

    def read(du, dv):
        return _bilinear(at, (u + du) * W - 0.5, (v + dv) * H - 0.5)

    aux = None
    if field.get('aux') is not None:
        # nearest and CLAMPED on both axes, as mixed.js reads the aux channel (its height read wraps on a periodic
        # axis, its aux read does not: a crop across a periodic seam takes the edge texel's ridge there)
        a = np.asarray(field['aux'], dtype=np.float64).ravel()
        jj = np.clip(_js_round(v * H - 0.5), 0, H - 1).astype(np.int64)
        ii = np.clip(_js_round(u * W - 0.5), 0, W - 1).astype(np.int64)
        aux = a[jj * W + ii]
    m = masks_from_stencil(read(0, 0), read(-e, 0), read(e, 0), read(0, -e), read(0, e), read(-e, -e), read(e, -e),
                           read(-e, e), read(e, e), e, G['worldX'], vertical_scale, aux)
    out = {}
    for n in names:
        val = m.get(n)
        a = np.zeros(X.shape) if val is None else np.broadcast_to(val, X.shape)
        out[n] = _js_round(np.clip(a, 0, 1) * 255).astype(np.uint8).ravel()
    return out


# --------------------------------------------------------------------------------------------- Heightfields ---

def field_of(hf, channel='height'):
    """A Heightfield as an Ekigar field dict: {'data', 'width', 'height', 'size', 'aux', 'worldSize', 'tile'}."""
    nx, ny = hf.resolution
    data = hf.height if channel == 'height' else hf.mask(channel)
    return {'data': np.asarray(data, dtype=np.float64).ravel(), 'width': nx, 'height': ny, 'size': nx,
            'aux': np.asarray(hf.aux, dtype=np.float64).ravel(), 'worldSize': hf.world_size,
            'tile': hf.tile.as_dict()}


def to_ekigar_metres(hf, x, y):
    """Blender (x, y) on a Heightfield -> Ekigar's metres (0 .. W from the tile's corner)."""
    return (np.asarray(x) - hf.origin[0] + hf.world_size / 2, np.asarray(y) - hf.origin[1] + hf.world_size / 2)


def from_ekigar_metres(hf, xm, ym):
    """Ekigar's metres -> Blender (x, y) on a Heightfield."""
    return (np.asarray(xm) + hf.origin[0] - hf.world_size / 2, np.asarray(ym) + hf.origin[1] - hf.world_size / 2)


def cut_for(hf, centre_xy, radius_m, fade_m=None):
    """A resolved cut around a Blender (x, y) on a Heightfield (metres), on its tile's periodicity."""
    cx, cy = to_ekigar_metres(hf, centre_xy[0], centre_xy[1])
    nx, ny = hf.resolution
    G = resolve_geometry({'width': nx, 'height': ny, 'worldSize': hf.world_size, 'tile': hf.tile.as_dict()})
    cut = {'centreMetres': [float(cx), float(cy)], 'radiusMetres': float(radius_m)}
    if fade_m is not None:
        cut['fadeMetres'] = float(fade_m)
    return resolve_cut(cut, G)


__all__ = ['local_weight', 'wrap_delta', 'resolve_geometry', 'resolve_cut', 'weight_at_texel', 'weight_at_metres',
           'weight_field', 'seam_ring', 'area_downsample', 'sample_field_metres', 'sample_field_nearest_metres',
           'crop_local', 'split_field', 'masks_used_by', 'resolve_driver_field', 'rasterise_local_masks',
           'field_of', 'to_ekigar_metres', 'from_ekigar_metres', 'cut_for']
