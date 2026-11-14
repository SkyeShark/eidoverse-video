"""A palette's look on a saved terrain, top-down, in plain Python (numpy, Pillow; no bpy, no GPU): what each layer
covers and the colour the ground takes, so a weight or a ramp can be read on the landform in seconds before a
render through Blender shows it from a camera.

    python blender/tests/terrain/surface_look/preview.py --recipe canyon --terrain <saved terrain or level stack>
        [--level main|<index>] [--tag new] [--palettes <file.py>] [--size 900] [--crop x0,y0,x1,y1] [--step 2]

--terrain is a Terrain.save file (<name>.npz with its .json: render_look.py --snap writes them; fields and masks of
every level) or a level stack saved by a generator's test (L<i>_<field> arrays with L<i>_window = x0, y0, side, cell,
n; the masks are computed here with the recipe's mask parameters). --palettes builds from another palettes.py (the
file as it was before an edit).

It evaluates the palette as the material composites it (palettes.evaluate: each layer's weight clamped to 0..1, a
layer covering what lies below it), with the scatter's value noise standing in for the shader's (the breakup's
pattern differs, its statistics do not), colours each layer by its colour, ramp, patches and tints (the strata
column by formation and bed; canopies by their far colour; no scans, streaks or ledges), and measures on that level:

    share      each layer's mean weight
    pure       the share of the ground where one layer holds 90 % or more of the weight
    largest    the largest connected region one layer dominates, as a share of the ground
    contour    how closely layer boundaries follow height lines: the weight-gradient-weighted mean of |cos| between
               each layer's weight gradient and the height's (1: every boundary a height line; 2 / pi = 0.64 at
               random), on all ground and on slopes over 25 degrees
    noise      the share of each layer's coverage that its noise terms move (the mean |weight - weight with every
               noise at its mean| over the layer's mean weight)

Writes out/surface_look/preview/<recipe>_<tag>.png (colour under a hillshade | layer map | flat colour) and .json.
"""
import argparse
import importlib.util
import json
import math
import os
import sys
import time

import numpy as np
from PIL import Image, ImageDraw, ImageFont

HERE = os.path.dirname(os.path.abspath(__file__))
TN = os.path.normpath(os.path.join(HERE, '..'))
BLENDER_DIR = os.path.normpath(os.path.join(TN, '..', '..'))
OUT = os.path.join(TN, 'out', 'surface_look', 'preview')
DEBUG_COLOURS = [(0.55, 0.38, 0.25), (0.35, 0.55, 0.2), (0.85, 0.75, 0.45), (0.6, 0.35, 0.6), (0.2, 0.55, 0.85),
                 (0.95, 0.95, 0.95)]
SUN_AZ, SUN_EL = 315.0, 38.0               # the top view's light: from the north-west, the review rig's elevation


def load_modules(palettes_file=None):
    if BLENDER_DIR not in sys.path:
        sys.path.insert(0, BLENDER_DIR)
    if palettes_file:
        name = 'eidoblend.terrain.build.palettes'
        spec = importlib.util.spec_from_file_location(name, palettes_file)
        mod = importlib.util.module_from_spec(spec)
        sys.modules[name] = mod
        spec.loader.exec_module(mod)
    from eidoblend.terrain import masks as M
    from eidoblend.terrain import recipes as R
    from eidoblend.terrain.build import palettes as P
    return M, R, P


def load_terrain(path, M, rec, params=None):
    """[(level dict(x0, y0, cell, n, role), fields, masks)] coarsest first, and the terrain's info (or {})."""
    base = os.path.splitext(path)[0]
    z = np.load(base + '.npz')
    if os.path.exists(base + '.json') and any('__f__' in k for k in z.files):         # a Terrain.save file
        meta = json.load(open(base + '.json', encoding='utf-8'))
        out = []
        for i, lv in enumerate(meta['plan']):
            f = {k.split('__', 2)[2]: z[k] for k in z.files if k.startswith(f'L{i}__f__')}
            m = {k.split('__', 2)[2]: np.asarray(z[k], np.float32) for k in z.files if k.startswith(f'L{i}__m__')}
            out.append((dict(x0=lv['x0'], y0=lv['y0'], cell=lv['cell'], n=lv['n'], role=lv['role']), f, m))
        return out, meta
    names = sorted({k.split('_')[0] for k in z.files}, key=lambda s: int(s[1:]))       # a level stack
    dfl = dict(rec.defaults)
    if getattr(rec, 'defaults_for', None) is not None:
        try:
            dfl.update(rec.defaults_for(rec.resolve(params or None)[0]))
        except Exception:                                # noqa: BLE001 - a hook that needs more than the knobs
            pass
    main_side = float(dfl.get('size') or 0.0)
    levels, fields = [], []
    for nm in names:
        x0, y0, side, cell, n = (float(v) for v in z[nm + '_window'])
        role = ('main' if abs(side - main_side) < 1e-3 * side else 'context' if side > main_side else 'hero')
        levels.append(dict(x0=x0, y0=y0, cell=cell, n=int(n), role=role))
        fields.append({k.split('_', 1)[1]: z[k] for k in z.files if k.startswith(nm + '_') and
                       not k.endswith('_window')})
    if not any(lv['role'] == 'main' for lv in levels):
        levels[-1]['role'] = 'main'
    mp = dict(dfl.get('mask_params') or {})
    mp['base_elevation_m'] = float(dfl.get('base_elevation_m', 0.0) or 0.0)
    mp['sea_level'] = dfl.get('sea_level')
    allowed = set(M.MaskParams.__dataclass_fields__)
    main_i = next(i for i, lv in enumerate(levels) if lv['role'] == 'main')
    stack = M.compute_stack(fields, levels, main=main_i,
                            params=M.MaskParams(**{k: v for k, v in mp.items() if k in allowed}))
    info = dict(base_elevation_m=mp['base_elevation_m'], knobs={}, recipe=dict(defaults=dfl))
    return [(lv, f, dict(m)) for lv, f, m in zip(levels, fields, stack)], info


def terrain_constants(P, pal, info):
    """The constants the material folds in: the palette's, then the terrain's base elevation, snowline, treeline."""
    consts = dict(pal['constants'])
    if info.get('base_elevation_m') is not None:
        consts['base_elevation_m'] = float(info['base_elevation_m'])
    mp = {}
    rec = info.get('recipe') or {}
    dfl = rec.get('defaults') if isinstance(rec, dict) else None
    if isinstance(dfl, dict):
        mp.update(dfl.get('mask_params') or {})
    knobs = info.get('knobs') or {}
    dem = knobs.get('dem')
    if isinstance(dem, str) and dem in P.PLACES:
        mp.update(P.PLACES[dem].get('mask_params') or {})
    for key in ('snowline_m', 'treeline_m'):
        if knobs.get(key) is not None:
            mp[key] = knobs[key]
        if mp.get(key) is not None:
            consts[key] = float(mp[key])
    return consts


def evaluate(P, expr, masks, X, Y, consts, flat=False):
    """palettes.evaluate; flat: every noise at its mean (through the module's own noises, so a palettes.py from
    before evaluate() took `flat` is read the same way)."""
    if not flat:
        return P.evaluate(expr, masks, X, Y, consts)
    vn, vc = P.value_noise, P.voronoi_cells
    P.value_noise = lambda x, *a, **k: np.full(np.shape(x), 0.5)
    P.voronoi_cells = lambda x, *a, **k: np.full(np.shape(x), 0.5)
    try:
        return P.evaluate(expr, masks, X, Y, consts)
    finally:
        P.value_noise, P.voronoi_cells = vn, vc


def hillshade(h, cell, az=SUN_AZ, el=SUN_EL):
    gy, gx = np.gradient(h, cell)
    a, e = math.radians(az), math.radians(el)
    lx, ly, lz = math.cos(e) * math.sin(a), math.cos(e) * math.cos(a), math.sin(e)
    return np.clip((-gx * lx - gy * ly + lz) / np.sqrt(gx * gx + gy * gy + 1.0), 0.0, 1.0)


def strata_colour(P, st, zs, X, Y, seed=0):
    """The column's linear colour at stratigraphic heights zs: formations split into beds of random thickness with a
    little colour jitter and darker bedding planes, as surfacing.strata_image draws them (its own random draws: the
    same statistics, not the same beds), read with the spec's warps."""
    layers = P.column_layers(st['column'], looks=bool(st.get('looks', False)))
    rep = P.column_repeats(st['column'])
    z_lo, z_hi = layers[0][1], layers[-1][2]
    pad = float(st.get('pad_m', 0.0))
    if not rep and pad > 0:
        z_lo, z_hi = z_lo - pad, z_hi + pad
        first, last = layers[0], layers[-1]
        layers = ([(first[0], z_lo, z_hi) + tuple(first[3:])] if len(layers) == 1 else
                  [(first[0], z_lo) + tuple(first[2:])] + layers[1:-1] + [tuple(last[:2]) + (z_hi,) + tuple(last[3:])])
    W = int(min(16384, max(64, math.ceil((z_hi - z_lo) * 2.0))))
    zc = z_lo + (np.arange(W) + 0.5) / W * (z_hi - z_lo)
    lut = np.zeros((W, 3))
    rng = np.random.default_rng(seed + 7)
    parting = float(st.get('parting', 0.0))
    for _nm, b, t, col, _rough, bed, jit in layers:
        z = b
        while z < t:
            th = max(0.3, float(rng.exponential(bed)))
            top = min(z + th, t)
            sel = (zc >= z) & (zc < top)
            v = math.exp(jit * float(rng.standard_normal()))
            hue = 1.0 + 0.3 * jit * rng.standard_normal(3)
            base = col[int(rng.choice(len(col), p=np.array([c[1] for c in col]) / sum(c[1] for c in col)))][0] \
                if isinstance(col, list) else col
            lut[sel] = np.clip(base * v * hue, 0.0, 0.95)
            if parting > 0.0 and sel.any():
                lut[int(np.argmax(sel))] *= max(0.0, 1.0 - parting * float(rng.uniform(0.5, 1.5)))
            z = top
    zs = np.asarray(zs, np.float64) + float(st.get('z_offset_m', 0.0))
    for k, (scale, amp) in enumerate(st.get('warp', []) or []):
        zs = zs + (P.value_noise(X, Y, float(scale), seed=41 + k) - 0.5) * 2.0 * float(amp)
    u = (zs - z_lo) / (z_hi - z_lo)
    u = np.mod(u, 1.0) if rep else np.clip(u, 0.0, 1.0)
    return lut[np.clip((u * W).astype(np.int64), 0, W - 1)]


def scan_mean(P, set_name):
    """A scan's mean linear albedo from its packed stats (the surface-set cache), or a mid grey-brown."""
    d = os.path.join(BLENDER_DIR, '..', 'eidoverse', 'assets', 'cache', 'terrain_surface_sets')
    try:
        for nm in os.listdir(d):
            if nm.lower().startswith(str(set_name).lower() + '_v'):
                return np.array(json.load(open(os.path.join(d, nm, 'stats.json')))['mean_albedo_linear'])
    except OSError:
        pass
    return np.array([0.2, 0.17, 0.13])


def colours(P, pal, masks, h, X, Y, consts):
    """Each layer's linear colour (H, W, 3) as the material makes it, without the scans' detail."""
    def ev(e, flat=False):
        return np.clip(np.broadcast_to(np.asarray(evaluate(P, e, masks, X, Y, consts, flat), np.float64),
                                       h.shape), 0.0, 1.0)
    st = pal.get('strata')
    zs = None
    if st and any(L['strata'] for L in pal['layers']):
        if st.get('source', 'attribute') == 'attribute':
            zs = np.asarray(masks.get('strata', np.zeros_like(h)), np.float64)
        else:
            dip = math.tan(math.radians(float(st.get('dip_deg', 0.0))))
            az = math.radians(float(st.get('dip_azimuth_deg', st.get('azimuth_deg', 0.0))))
            zs = h - (X * math.cos(az) + Y * math.sin(az)) * dip
    out = []
    for i, L in enumerate(pal['layers']):
        own = np.array(P.hex_linear(L['colour'])) if L['colour'] else None
        smix = float(L['strata']) if L['strata'] is not True else 1.0
        if smix > 0 and zs is not None:
            band = strata_colour(P, st, zs + float(L.get('strata_offset_m', 0.0)), X, Y)
            col = band if (smix >= 1.0 or own is None) else own + smix * (band - own)
        else:
            col = np.broadcast_to(own if own is not None else scan_mean(P, L['set']), h.shape + (3,)).copy()
        if L['tint'] is not None:
            col = col * np.array(L['tint'][:3])
        cn = L.get('canopy')
        if cn:                                           # seen from afar: the crowns' two tones and their gaps
            far = 0.5 * (np.array(P.hex_linear(cn.get('colour', '#26371f')))
                         + np.array(P.hex_linear(cn.get('light', '#3d522c'))))
            col = np.broadcast_to(0.82 * far + 0.18 * np.array(P.hex_linear(cn.get('gap', '#11160d'))),
                                  h.shape + (3,)).copy()
        for k, pt in enumerate(P._patches(L)):
            amount = float(pt.get('amount', 0.6))
            if pt.get('scale_m') is None:
                pm = np.full(h.shape, amount)
            else:
                n = P.value_noise(X, Y, float(pt['scale_m']), seed=337 + 23 * i + 51 * k, octaves=3)
                pm = P._smooth(float(pt.get('lo', 0.42)), float(pt.get('hi', 0.62)), n) * amount
            if pt.get('where'):
                pm = pm * ev(pt['where'])
            if pt.get('tint'):
                ratio = np.array(pt['tint'][:3], np.float64)
            else:
                ref = np.array(P.hex_linear(L['colour'])) if L['colour'] else scan_mean(P, L['set'])
                ratio = np.array(P.hex_linear(pt['colour'])) / np.maximum(ref, 1e-4)
            col = col + pm[..., None] * (col * ratio - col)
        col = col * float(L.get('value', 1.0))
        out.append(np.clip(col, 0.0, 0.95))
    return out


def composite(P, pal, masks, h, X, Y, consts):
    """(coverages, exclusive weights (L, H, W), the same with every noise at its mean)."""
    def cov(flat):
        c = [np.clip(np.broadcast_to(np.asarray(evaluate(P, L['weight'], masks, X, Y, consts, flat), np.float64),
                                     h.shape), 0.0, 1.0) for L in pal['layers']]
        e = [None] * len(c)
        rem = np.ones_like(h)
        for i in range(len(c) - 1, -1, -1):
            e[i] = c[i] * rem
            rem = rem * (1.0 - c[i])
        return c, np.stack(e)
    c, E = cov(False)
    _cf, Ef = cov(True)
    return c, E, Ef


def blend(E, depth=0.2):
    """The height blend with every scan height equal: keep what lies within `depth` of the heaviest layer."""
    b = np.maximum(E - (E.max(0, keepdims=True) - depth), 0.0)
    return b / np.maximum(b.sum(0, keepdims=True), 1e-9)


def largest_region(dom):
    """The largest 8-connected region of a boolean array, in cells."""
    try:
        import cv2
        k, _lab, stats, _c = cv2.connectedComponentsWithStats(dom.astype(np.uint8), connectivity=8)
        return int(stats[1:, cv2.CC_STAT_AREA].max()) if k > 1 else 0
    except ImportError:
        best, seen = 0, np.zeros(dom.shape, bool)
        H, W = dom.shape
        for j0, i0 in zip(*np.nonzero(dom)):
            if seen[j0, i0]:
                continue
            stack, n = [(j0, i0)], 0
            seen[j0, i0] = True
            while stack:
                j, i = stack.pop()
                n += 1
                for dj in (-1, 0, 1):
                    for di in (-1, 0, 1):
                        a, b = j + dj, i + di
                        if 0 <= a < H and 0 <= b < W and dom[a, b] and not seen[a, b]:
                            seen[a, b] = True
                            stack.append((a, b))
            best = max(best, n)
        return best


def contour_index(e, h, cell, sel):
    gy_h, gx_h = np.gradient(h, cell)
    gh = np.hypot(gx_h, gy_h)
    gy, gx = np.gradient(e, cell)
    ge = np.hypot(gx, gy)
    ok = sel & (ge > 1e-4) & (gh > math.tan(math.radians(0.5)))
    if not ok.any():
        return None, 0.0
    cosv = np.abs(gx * gx_h + gy * gy_h) / np.maximum(ge * gh, 1e-12)
    return float((cosv[ok] * ge[ok]).sum() / max(ge[ok].sum(), 1e-12)), float(ge[ok].sum())


def measure(pal, E, Ef, h, cell, masks):
    n = h.shape[0]
    inner = np.zeros(h.shape, bool)
    b = max(8, n // 64)
    inner[b:n - b, b:n - b] = True
    water = np.asarray(masks.get('water', np.zeros_like(h)), np.float64) > 0.05
    ground = inner & ~water
    steep = ground & (np.asarray(masks['slope'], np.float64) > 25.0)
    top, topw = E.argmax(0), E.max(0)
    res = dict(layers=[], ground_cells=int(ground.sum()))
    tot = {'all': [0.0, 0.0], 'steep': [0.0, 0.0]}
    for i, L in enumerate(pal['layers']):
        e = E[i]
        dom = (top == i) & (topw > 0.5) & ground
        ca, wa = contour_index(e, h, cell, ground)
        cs, ws = contour_index(e, h, cell, steep)
        for key, c, w in (('all', ca, wa), ('steep', cs, ws)):
            if c is not None:
                tot[key][0] += c * w
                tot[key][1] += w
        share = float(e[ground].mean())
        res['layers'].append(dict(
            name=L['name'], share=round(share, 4), pure=round(float(((top == i) & (topw >= 0.9))[ground].mean()), 4),
            largest=round(largest_region(dom) / max(int(ground.sum()), 1), 4),
            contour=None if ca is None else round(ca, 3), contour_steep=None if cs is None else round(cs, 3),
            noise=round(float(np.abs(e - Ef[i])[ground].mean()) / max(share, 1e-6), 3)))
    res['pure_total'] = round(float((topw >= 0.9)[ground].mean()), 4)
    res['largest'] = max(L['largest'] for L in res['layers'])
    res['contour'] = round(tot['all'][0] / tot['all'][1], 3) if tot['all'][1] else None
    res['contour_steep'] = round(tot['steep'][0] / tot['steep'][1], 3) if tot['steep'][1] else None
    res['steep_share'] = round(float(steep.sum()) / max(int(ground.sum()), 1), 4)
    return res


def tone_and_macro(P, pal, albedo, masks, h, X, Y, consts):
    opt = pal['options']
    if opt.get('tone'):
        tv = np.broadcast_to(np.asarray(P.evaluate(opt['tone'], masks, X, Y, consts), np.float64), h.shape)
        albedo = albedo * np.clip(1.0 + tv, 0.4, 1.6)[..., None]
    val = np.ones_like(h)
    for k, o in enumerate(opt.get('macro') or []):
        if o.get('value'):
            n = P.value_noise(X, Y, float(o['scale_m']), seed=900 + k, octaves=3, stretch=1.0)
            val = val * (1.0 + float(o['value']) * np.clip((n - 0.5) / 0.2, -1.0, 1.0))
    albedo = albedo * val[..., None]
    if opt.get('damp_where'):
        dm = np.clip(np.broadcast_to(np.asarray(P.evaluate(opt['damp_where'], masks, X, Y, consts), np.float64),
                                     h.shape), 0.0, 1.0)
        albedo = albedo * (1.0 - 0.38 * dm)[..., None]
    return np.clip(albedo, 0.0, 0.95)


def memo_noise(P):
    """Each (scale, seed, octaves) of the module's value noise evaluated once per run: the layers share their
    breakup noises, and a million cells of five octaves is the preview's whole cost."""
    raw, memo = P.value_noise, {}

    def value_noise(x, y, scale_m, seed=0, octaves=2, gain=0.5, stretch=1.6):
        key = (np.shape(x), float(np.ravel(x)[0]), float(np.ravel(y)[0]), float(scale_m), int(seed), int(octaves),
               float(gain), float(stretch))
        if key not in memo:
            memo[key] = raw(x, y, scale_m, seed, octaves, gain, stretch)
        return memo[key]
    P.value_noise = value_noise


def run(recipe, terrain, level='main', tag='new', palettes_file=None, size=900, crop=None, params=None, log=print,
        step=1):
    t0 = time.time()
    M, R, P = load_modules(palettes_file)
    if getattr(P.value_noise, '__name__', '') != 'value_noise' or P.value_noise.__module__ != __name__:
        memo_noise(P)
    rec = R.get(recipe)
    levels, info = load_terrain(terrain, M, rec, params)
    if level == 'main':
        li = next(i for i, (lv, _f, _m) in enumerate(levels) if lv['role'] == 'main')
    else:
        li = int(level) % len(levels)
    lv, fields, masks = levels[li]
    place = (info.get('knobs') or {}).get('dem')
    if recipe == 'real_place' and place in P.PLACES:
        pal, _place = P.for_place(place)
    else:
        pal = P.get('auto', recipe=rec)
    consts = terrain_constants(P, pal, info)
    h = np.asarray(fields['h'], np.float64)
    n, cell = h.shape[0], float(lv['cell'])
    masks = {k: np.asarray(v, np.float64) for k, v in masks.items()}
    masks.setdefault('height', h)
    if crop:
        i0, j0, i1, j1 = (int(round((v - o) / cell)) for v, o in zip(crop, (lv['x0'], lv['y0'], lv['x0'], lv['y0'])))
        sl = (slice(max(j0, 0), min(j1, n)), slice(max(i0, 0), min(i1, n)))
        h = h[sl]
        masks = {k: v[sl] for k, v in masks.items()}
        x_off, y_off = lv['x0'] + sl[1].start * cell, lv['y0'] + sl[0].start * cell
    else:
        x_off, y_off = lv['x0'], lv['y0']
    hs = hillshade(h, cell)[..., None]
    if step > 1:                                         # every step-th cell: a quick look (the measures coarsen)
        h, hs = h[::step, ::step], hs[::step, ::step]
        masks = {k: v[::step, ::step] for k, v in masks.items()}
        x_off, y_off, cell = x_off + 0.5 * (step - 1) * cell, y_off + 0.5 * (step - 1) * cell, cell * step
    X, Y = np.meshgrid(x_off + (np.arange(h.shape[1]) + 0.5) * cell, y_off + (np.arange(h.shape[0]) + 0.5) * cell)
    _c, E, Ef = composite(P, pal, masks, h, X, Y, consts)
    cols = colours(P, pal, masks, h, X, Y, consts)
    Wb = blend(E, float(pal['options'].get('blend_depth', 0.2)))
    albedo = sum(Wb[i][..., None] * cols[i] for i in range(len(cols)))
    albedo = tone_and_macro(P, pal, albedo, masks, h, X, Y, consts)
    res = measure(pal, E, Ef, h, cell, masks) if h.shape[0] == h.shape[1] else dict(layers=[])
    res.update(recipe=recipe, palette=pal['name'], level=str(lv), cell_m=cell, tag=tag, constants=consts,
               seconds=round(time.time() - t0, 1))
    # the sheet
    lit = P.linear_to_srgb(np.clip(albedo * (0.5 + 1.9 * hs), 0.0, 1.0))
    lay = sum(E[i][..., None] * np.array(DEBUG_COLOURS[i % len(DEBUG_COLOURS)]) for i in range(len(cols)))
    lay = np.clip(lay * (0.5 + 0.7 * hs), 0.0, 1.0)
    flat = P.linear_to_srgb(albedo)
    tiles = [Image.fromarray((np.clip(a[::-1], 0, 1) * 255).astype(np.uint8)).resize(
        (size, int(size * h.shape[0] / h.shape[1])), Image.LANCZOS) for a in (lit, lay, flat)]
    th = tiles[0].size[1]
    rows = len(pal['layers'])
    sheet = Image.new('RGB', (3 * size, th + 34 + 19 * (rows + 1)), (18, 18, 18))
    for k, im in enumerate(tiles):
        sheet.paste(im, (k * size, 34))
    dr = ImageDraw.Draw(sheet)
    try:
        f = ImageFont.truetype('arial.ttf', 14)
    except OSError:
        f = ImageFont.load_default()
    dr.text((6, 8), f"{recipe} [{tag}] {pal['name']}: {h.shape[1] * cell / 1000:g} km at {cell:.3g} m, north up. "
                    f"colour under a hillshade | layers | flat colour", fill=(255, 220, 120), font=f)
    for i, Ly in enumerate(res['layers']):
        y0 = th + 40 + 19 * i
        dr.rectangle([8, y0, 24, y0 + 13], fill=tuple(int(255 * v) for v in DEBUG_COLOURS[i % len(DEBUG_COLOURS)]))
        dr.text((32, y0 - 1), f"{Ly['name']}: share {100 * Ly['share']:.1f} %, pure {100 * Ly['pure']:.1f} %, largest "
                              f"region {100 * Ly['largest']:.1f} %, height-line index {Ly['contour']} (steep "
                              f"{Ly['contour_steep']}), noise share {Ly['noise']}", fill=(230, 230, 230), font=f)
    if res['layers']:
        dr.text((32, th + 39 + 19 * rows), f"all layers: one layer at 90 % or more over {100 * res['pure_total']:.1f} % "
                                           f"of the ground, largest one-layer region {100 * res['largest']:.1f} %, "
                                           f"height-line index {res['contour']} (slopes over 25 degrees: "
                                           f"{res['contour_steep']}, {100 * res['steep_share']:.0f} % of the ground)",
                fill=(255, 220, 120), font=f)
    os.makedirs(OUT, exist_ok=True)
    path = os.path.join(OUT, f'{recipe}_{tag}.png')
    sheet.save(path)
    with open(os.path.join(OUT, f'{recipe}_{tag}.json'), 'w', encoding='utf-8') as fh:
        json.dump(res, fh, indent=1, default=float)
    if log:
        log(f"[preview] {recipe} [{tag}]: pure {res.get('pure_total')}, largest {res.get('largest')}, height-line "
            f"index {res.get('contour')} (steep {res.get('contour_steep')}), {res['seconds']} s -> {path}")
        for Ly in res['layers']:
            log(f"    {Ly['name']:<14} share {Ly['share']:.3f} pure {Ly['pure']:.3f} largest {Ly['largest']:.3f} "
                f"contour {Ly['contour']} steep {Ly['contour_steep']} noise {Ly['noise']}")
    return res


def main():
    ap = argparse.ArgumentParser(description=__doc__.split('\n')[0])
    ap.add_argument('--recipe', required=True)
    ap.add_argument('--terrain', required=True)
    ap.add_argument('--level', default='main')
    ap.add_argument('--tag', default='new')
    ap.add_argument('--palettes')
    ap.add_argument('--size', type=int, default=900)
    ap.add_argument('--crop')
    ap.add_argument('--params')
    ap.add_argument('--step', type=int, default=1)
    a = ap.parse_args()
    params = None
    if a.params:
        params = {}
        for kv in a.params.split(','):
            k, v = kv.split('=', 1)
            try:
                params[k] = float(v)
            except ValueError:
                params[k] = v
    crop = [float(v) for v in a.crop.split(',')] if a.crop else None
    run(a.recipe, a.terrain, a.level, a.tag, a.palettes, a.size, crop, params, step=a.step)


if __name__ == '__main__':
    main()
