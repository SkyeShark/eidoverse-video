"""Ekigar operators, part 1 (registry.js): primitives, erosion and weathering, the crater stamp, terraces, strata,
height adjustments, warp, roughen and Combine.

Each operator is the registry's declaration: label, category, doc, params (the schema the UI, the API and the
defaults come from) and apply(f, p, ctx) -> field vec4, or {'field': vec4, 'outs': {name: mask}} when it also
produces named outputs. Parameter names stay Ekigar's (camelCase), so ekigar-project JSON files load unchanged.
"""
from __future__ import annotations

import math

import numpy as np

from ._tsl import Vec, clamp, mix, select, step01, dot, length, fract, EPS
from .noise import noised, hash2, fractal_noise
from .phacelle import erosion_operator
from .ops_shared import (P, H, G, AUX, field, remap, wrapped_delta, texel, seed_shift, seed_offset, sstep,
                         strata_fold, swiss_field, cell_search, euclid_metric, blend_field, js_round,
                         COMBINE_MODE_VALUES)

OPS = {}

TAPS8 = [(-1, 0), (1, 0), (0, -1), (0, 1), (-1, -1), (1, -1), (-1, 1), (1, 1)]


# --- primitives (generators) -------------------------------------------------------------------------------------

def _constant(f, p, ctx):
    return field(p.value, Vec(0.0, 0.0), AUX(f))


OPS['constant'] = dict(
    label='Constant', category='primitive', generator=True,
    doc='Flat value. Useful as a stack base or as a masked additive offset.',
    params={'value': P.float(0.5, -2, 2)}, apply=_constant)


def _gradient(f, p, ctx):
    d = Vec(np.cos(p.angle), np.sin(p.angle))
    return field(dot(ctx.p, d) * p.scale + 0.5, d * p.scale, AUX(f))


OPS['gradient'] = dict(
    label='Gradient', category='primitive', generator=True,
    doc='Linear ramp along an angle. The classic way to bias a whole terrain downhill.',
    params={'angle': P.float(0, 0, 6.283, unit='rad'), 'scale': P.float(1, -4, 4)}, apply=_gradient)


def _radial_gradient(f, p, ctx):
    d = wrapped_delta(ctx.p, p.centre, ctx.tile)
    r = length(d) / p.radius
    v = np.power(clamp(1.0 - r, 0.0, 1.0), p.falloff)
    dr = d / np.maximum(length(d), 1e-6) / p.radius
    dv = -(dr * (np.power(clamp(1.0 - r, 0.0, 1.0), np.maximum(p.falloff - 1.0, 0.0)) * p.falloff))
    return field(v, dv, AUX(f))


OPS['radialGradient'] = dict(
    label='Radial Gradient', category='primitive', generator=True,
    doc='Distance falloff from a centre — island bases, crater bowls, local blends.',
    params={'centre': P.vec2([0.5, 0.5]), 'radius': P.float(0.45, 0.01, 4), 'falloff': P.float(1.6, 0.2, 6)},
    apply=_radial_gradient)


def _fbm(f, p, ctx):
    n = fractal_noise(ctx.p, p.frequency, p.octaves, p.lacunarity, p.gain, ctx.tile)
    return field(n.x * p.amplitude * 0.5 + 0.5, Vec(n.y, n.z) * p.amplitude * 0.5, AUX(f))


OPS['fbm'] = dict(
    label='fBm Noise', category='primitive', generator=True,
    doc='Fractal Brownian motion with exact analytic derivatives. The default landform base.',
    params={
        'frequency': P.float(3, 0.25, 64, structural=True, periodFreq=True),
        'amplitude': P.float(0.125, 0, 2),
        'octaves': P.int(3, 1, 10),
        'lacunarity': P.int(2, 2, 4, doc='must be integral or tiling breaks'),
        'gain': P.float(0.5, 0.05, 0.95, structural=True, maskable=False),
    }, apply=_fbm)


def _ridged(f, p, ctx):
    h = g = None
    nf, na = float(p.frequency), 1.0
    for _ in range(int(p.octaves)):
        nv, ndx, ndy = noised(ctx.p.x * nf, ctx.p.y * nf, ctx.tile.x * nf, ctx.tile.y * nf)
        s = np.sign(nv)
        term = (1.0 - np.abs(nv)) * na
        dterm = Vec(ndx, ndy) * (-s) * (na * nf)
        h = term if h is None else h + term
        g = dterm if g is None else g + dterm
        na *= p.gain
        nf *= p.lacunarity
    sharp = np.power(h, p.sharpness)
    dsharp = np.power(h, np.maximum(p.sharpness - 1.0, 0.0)) * p.sharpness
    return field(sharp * p.amplitude * 0.5 + 0.25, g * dsharp * p.amplitude * 0.5, AUX(f))


OPS['ridged'] = dict(
    label='Ridged Multifractal', category='primitive', generator=True,
    doc='Sharp ridgelines from folded noise — mountain spines and fault scarps.',
    params={
        'frequency': P.float(3, 0.25, 64, structural=True, periodFreq=True),
        'amplitude': P.float(0.35, 0, 2),
        'octaves': P.int(4, 1, 10),
        'lacunarity': P.int(2, 2, 4),
        'gain': P.float(0.5, 0.05, 0.95, structural=True, maskable=False),
        'sharpness': P.float(1, 0.2, 4),
    }, apply=_ridged)


def _voronoi(f, p, ctx):
    cells = max(1, js_round(p.frequency))
    period = (ctx.tile.x * cells, ctx.tile.y * cells)
    c = cell_search(ctx.p * cells, period, p.jitter, Vec(0.0, 0.0), euclid_metric)
    v = c.f2 - c.f1 if p.mode == 'f2-f1' else c.f1
    dv = c.g2 - c.g1 if p.mode == 'f2-f1' else c.g1
    return {'field': field(H(f) + v * p.amplitude, G(f) + dv * (-cells) * p.amplitude, AUX(f)),
            'outs': {'cells': clamp(v, 0.0, 1.0)}}


OPS['voronoi'] = dict(
    label='Voronoi', category='primitive', generator=True,
    doc='Cellular distance field — mesas, cracked plates, scree cells.',
    params={
        'frequency': P.float(8, 0.5, 64, structural=True, periodFreq=True),
        'amplitude': P.float(0.3, 0, 2),
        'jitter': P.float(0.9, 0, 1),
        'mode': P.enum('f1', ['f1', 'f2-f1']),
    }, apply=_voronoi)


# --- erosion & weathering ----------------------------------------------------------------------------------------

def _phacelle(f, p, ctx):
    out = erosion_operator(f, p, ctx)
    dh = H(f) - H(out)
    s_in = length(G(f))
    s_out = length(G(out))
    return {'field': out, 'outs': {
        'wear': clamp(dh / np.maximum(p.strength, EPS) * 2.0, 0.0, 1.0),
        'ridge': clamp(AUX(out) * 0.5 + 0.5, 0.0, 1.0),
        'flow': clamp((s_out - s_in) / np.maximum(s_in, 0.05), 0.0, 1.0),
    }}


def _phacelle_snap(p, tile, snap_freq):
    """Period is 1/(scale*cellScale) cells, so neither param alone can be snapped: hold cellScale, move scale."""
    t = tile.x if tile.x > 0 else tile.y
    if not (t > 0):
        return {'params': p, 'notes': []}
    want = 1.0 / (p['scale'] * p['cellScale'])
    got = snap_freq(want, t)
    if abs(want - got) < 1e-9:
        return {'params': p, 'notes': []}
    scale = 1.0 / (got * p['cellScale'])
    q = dict(p)
    q['scale'] = scale
    return {'params': q, 'notes': [f"erosion scale {p['scale']:.4f} gives a {want * t:.3f}-cell period; snapped to "
                                   f"{scale:.6f} ({js_round(got * t)} cells)"]}


OPS['phacelle'] = dict(
    label='Erosion', category='simulate',
    doc='Analytic slope-aligned gully erosion (Rune Skovbo Johansen). Single pass, tileable, no iteration.',
    params={
        'strength': P.float(0.14, 0, 0.8),
        'scale': P.float(0.15, 0.02, 0.5, structural=True),
        'gullyWeight': P.float(0.42, 0, 1),
        'detail': P.float(1.25, 0.3, 4),
        'octaves': P.int(3, 1, 8),
        'lacunarity': P.int(2, 2, 4),
        'gain': P.float(0.5, 0.1, 0.95),
        'cellScale': P.float(0.7, 0.3, 1.5, structural=True),
        'normalization': P.float(0.35, 0, 1),
        'ridgeRounding': P.float(0.22, 0, 1),
        'creaseRounding': P.float(0.08, 0, 1),
        'offset': P.float(0, -1, 1, doc='flat raise (+) or lower (−) alongside the erosion'),
        'preserve': P.float(1, 0, 1, doc='peak-preserving mode — raise valleys, lower peaks, keep the extrema'),
    }, apply=_phacelle, snap=_phacelle_snap)


def _thermal(f, p, ctx):
    e = texel(ctx, p.radius)
    flux = flux_g = None
    for dx, dy in TAPS8:
        ln = math.hypot(dx, dy)
        s = ctx.sample_input(dx * e, dy * e)
        d = H(f) - H(s)
        limit = p.repose * (ln * e)
        active = np.abs(d) > limit
        q = np.where(active, d - np.sign(d) * limit, 0.0)
        qg = select(active, G(f) - G(s), Vec(0.0, 0.0))
        flux = q if flux is None else flux + q
        flux_g = qg if flux_g is None else flux_g + qg
    k = clamp(p.strength, 0.0, 1.0) / len(TAPS8)
    move = flux * k
    return {'field': field(H(f) - move, G(f) - flux_g * k, AUX(f)),
            'outs': {'talus': clamp(-move / np.maximum(p.repose * e, EPS), 0.0, 1.0)}}


OPS['thermal'] = dict(
    label='Thermal', category='simulate',
    doc='Conservatively moves material down unstable slopes and deposits it as talus.',
    params={
        'repose': P.float(0.55, 0.05, 2, doc='max stable |grad|'),
        'strength': P.float(0.9, 0, 1),
        'radius': P.float(2, 0.5, 12, structural=True, doc='reach of one relaxation step, in texels'),
    }, needsResample=True, apply=_thermal)


def _snow(f, p, ctx):
    e = texel(ctx, p.radius)
    mean_h = mean_g = None
    shelter = 0.0
    shelter_g = Vec(0.0, 0.0)
    side = {}
    for dx, dy in TAPS8:
        s = ctx.sample_input(dx * e, dy * e)
        mean_h = H(s) if mean_h is None else mean_h + H(s)
        mean_g = G(s) if mean_g is None else mean_g + G(s)
        relief = H(s) - H(f)
        win = relief > shelter
        shelter = np.where(win, relief, shelter)
        shelter_g = select(win, G(s) - G(f), shelter_g)
        side[(dx, dy)] = s
    sL, sR, sD, sU = side[(-1, 0)], side[(1, 0)], side[(0, -1)], side[(0, 1)]
    mean_h = mean_h / len(TAPS8)
    mean_g = mean_g / len(TAPS8)
    alt = sstep(p.line - p.softness * 0.5, p.line + p.softness * 0.5, H(f))
    slope = length(G(f))
    slope_step = sstep(p.maxSlope * 0.45, p.maxSlope, slope)
    retention = 1.0 - slope_step.v * 0.25
    grad_slope = Vec((length(G(sR)) - length(G(sL))) / (2 * e), (length(G(sU)) - length(G(sD))) / (2 * e))
    g_retention = grad_slope * (slope_step.d * -0.25)
    scale = np.maximum(p.maxSlope * e, EPS)
    sheltered = sstep(0.0, scale * 1.8, shelter)
    shelter_hold = 0.82 + sheltered.v * 0.18
    g_shelter_hold = shelter_g * (sheltered.d * 0.18)
    fill_cap = p.depth * 0.75
    fill_step = sstep(0.0, fill_cap, mean_h - H(f))
    fill = fill_step.v * fill_cap
    g_fill = (mean_g - G(f)) * (fill_step.d * fill_cap)
    blanket = alt.v * retention * shelter_hold
    g_blanket = (G(f) * alt.d * retention * shelter_hold + g_retention * alt.v * shelter_hold
                 + g_shelter_hold * alt.v * retention)
    deposit = blanket * p.depth + alt.v * fill * 0.8
    g_deposit = g_blanket * p.depth + G(f) * alt.d * fill * 0.8 + g_fill * alt.v * 0.8
    amount = clamp(deposit / np.maximum(p.depth, EPS), 0.0, 1.0)
    return {'field': field(H(f) + deposit, G(f) + g_deposit, amount), 'outs': {'depth': amount}}


OPS['snow'] = dict(
    label='Snow', category='simulate',
    doc='Elevation, slope, concavity and shelter control accumulated snow depth.',
    params={
        'line': P.float(0.5, 0, 1, doc='snow line altitude'),
        'softness': P.float(0.16, 0.01, 0.5),
        'maxSlope': P.float(1.8, 0.05, 2),
        'depth': P.float(0.045, 0, 0.2),
        'radius': P.float(5, 0.5, 8, structural=True, doc='shelter reach in texels'),
    }, needsResample=True, apply=_snow)


# --- stamps ------------------------------------------------------------------------------------------------------

def _crater(f, p, ctx):
    d = wrapped_delta(ctx.p, p.centre, ctx.tile)
    ln = np.maximum(length(d), 1e-6)
    rad = np.maximum(p.radius, EPS)
    dirv = d / ln
    n_ang = noised(dirv.x * 2.3, dirv.y * 2.3, 1024.0, 1024.0)
    n_ray = noised(dirv.x * 7.1 + float(seed_shift(p.seed)[0] % 17), dirv.y * 7.1, 1024.0, 1024.0)
    r = ln / rad + n_ang[0] * p.irregular * 0.22
    drdp = d / ln / rad
    fl = clamp(p.floor, 0.02, 0.9)
    wall_s = sstep(fl, 1.0, r)
    bowl = -((1.0 - wall_s.v) * p.depth)
    dbowl = wall_s.d * p.depth
    rw = np.maximum(p.rimWidth, 0.05)
    rim_arg = (r - 1.0) / rw
    rim_g = np.exp(-(rim_arg * rim_arg))
    rim_h = p.rim * p.depth
    drim = rim_g * rim_arg * -2.0 / rw * rim_h
    reach = np.maximum(p.ejecta, 0.05)
    past = np.maximum(r - 1.0, 0.0)
    ej = np.exp(-(past / reach))
    on = sstep(0.92, 1.12, r)
    outside = on.v
    dej = -(ej / reach) * outside + ej * on.d
    ray_mod = np.abs(n_ray[0]) * p.rays + (1.0 - p.rays * 0.5)
    ej_h = rim_h * 0.35
    pk = p.peakHeight * p.depth
    pr = fl * 0.5 + 0.05
    peak_g = np.exp(-((r / pr) * (r / pr)))
    dpeak = peak_g * r * -2.0 / (pr * pr) * pk
    v = bowl + rim_g * rim_h + ej * ej_h * ray_mod * outside + peak_g * pk
    dvdr = dbowl + drim + dej * ej_h * ray_mod + dpeak
    nf = max(2, js_round(p.detailFrequency))
    det = swiss_field(ctx, frequency=nf, octaves=3, gain=0.5, warp=0.25, offset=seed_offset(p.seed, nf))
    near = np.exp(r * r * -0.6)
    amp = p.detail * p.depth * 0.32 * (near + 0.25)
    v = v + (det.v - 0.5) * amp
    g = drdp * dvdr + det.g * amp
    return {'field': field(H(f) + v, G(f) + g, AUX(f)),
            'outs': {'rim': clamp(rim_g, 0.0, 1.0), 'ejecta': clamp(ej * outside, 0.0, 1.0)}}


OPS['crater'] = dict(
    label='Crater', category='terrain',
    doc='An impact bowl with an irregular raised rim, rayed ejecta and floor sediment. The rim line is noise-broken '
        'so the circle reads as geology, not geometry.',
    params={
        'centre': P.vec2([0.5, 0.5]),
        'radius': P.float(0.28, 0.005, 1),
        'depth': P.float(0.12, 0, 0.5),
        'rim': P.float(0.35, 0, 2, doc='rim crest height, relative to the depth'),
        'floor': P.float(0.35, 0.02, 0.9, doc='flat floor radius, as a fraction of the crater'),
        'rimWidth': P.float(0.22, 0.05, 1, doc='width of the rim crest, in crater radii'),
        'irregular': P.float(0.5, 0, 1, doc='how far the rim line wanders from a circle'),
        'ejecta': P.float(1.2, 0.05, 4, doc='ejecta apron reach past the rim, in radii'),
        'rays': P.float(0.5, 0, 1, doc='strength of the radial ejecta rays'),
        'peakHeight': P.float(0.1, 0, 1.5, doc='central uplift, relative to depth'),
        'detail': P.float(0.5, 0, 1),
        'detailFrequency': P.float(26, 2, 64, structural=True, periodFreq=True),
        'seed': P.int(0, 0, 65535),
    }, apply=_crater)


# --- surface: terraces and strata --------------------------------------------------------------------------------

def _terrace(f, p, ctx):
    s = H(f) * p.steps
    i = np.floor(s)
    fr = fract(s)
    jitter = hash2(i, float(seed_shift(p.seed)[0]), 0.0, 0.0)[0] * 0.5 + 0.5
    w = np.maximum(p.sharpness * mix(jitter * 0.7 + 0.3, 1.0, p.uniformity), 1e-3)
    k = clamp(fr / w, 0.0, 1.0)
    smooth = k * k * (3.0 - k * 2.0)
    target = (i + smooth) / p.steps
    dtarget = k * (1.0 - k) * 6.0 / w
    return remap(f, mix(H(f), target, p.intensity), mix(1.0, dtarget, p.intensity))


OPS['terrace'] = dict(
    label='Terraces', category='surface',
    doc='Quantises height into steps with a controllable riser sharpness.',
    params={
        'steps': P.float(8, 2, 128, doc='number of terraces through one unit of height'),
        'sharpness': P.float(0.6, 0.01, 1, doc='fraction of each band occupied by its riser'),
        'uniformity': P.float(1, 0.2, 1),
        'intensity': P.float(1, 0, 1),
        'seed': P.int(0, 0, 65535),
    }, apply=_terrace)


def _stratify(f, p, ctx):
    s = strata_fold(H(f), p.bands, p.strength, p.convexity)
    return {'field': remap(f, s.v, s.d), 'outs': {'layers': fract(H(f) * p.bands)}}


OPS['stratify'] = dict(
    label='Stratify', category='surface',
    doc='Sedimentary beds with near-flat treads and smooth, bounded risers.',
    params={
        'bands': P.float(12, 2, 200),
        'strength': P.float(0.9, 0, 1),
        'convexity': P.float(0.82, 0, 1,
                             doc='bows the riser — 0 is a straight bed, 1 a hard riser under a flat tread'),
    }, apply=_stratify)


def _schlick(x, k):
    a = 1.0 / clamp(k, 0.02, 0.98) - 2.0
    den = a * (1.0 - x) + 1.0
    return x / den, (den + a * x) / (den * den)


def _curves(f, p, ctx):
    h = clamp(H(f), 0.0, 1.0)
    bv, bd = _schlick(h, p.bias)
    lo = bv < 0.5
    u = np.where(lo, bv * 2.0, 2.0 - bv * 2.0)
    gv, gd = _schlick(u, p.gain)
    return remap(f, np.where(lo, gv * 0.5, 1.0 - gv * 0.5), gd * bd)


OPS['curves'] = dict(
    label='Adjust', category='modify',
    doc='Push height toward peaks or valleys, and expand or compress midtones.',
    params={'bias': P.float(0.5, 0.02, 0.98), 'gain': P.float(0.5, 0.02, 0.98)}, apply=_curves)


def _clamp_op(f, p, ctx):
    inside = (H(f) > p.lo) & (H(f) < p.hi)
    gate = step01(inside)
    c = clamp(H(f), p.lo, p.hi)
    if p.mode == 'normalized':
        span = np.maximum(p.hi - p.lo, EPS)
        return field((c - p.lo) / span, G(f) * gate / span, AUX(f))
    return field(c - p.lo if p.drop else c, G(f) * gate, AUX(f))


OPS['clampOp'] = dict(
    label='Clamp', category='modify',
    doc='Hard floor and ceiling — sea floors, plateau caps.',
    params={
        'lo': P.float(0, -1, 2, doc='lower height bound'),
        'hi': P.float(1, -1, 2),
        'mode': P.enum('standard', ['standard', 'normalized']),
        'drop': P.bool(False, doc=''),
    }, apply=_clamp_op)


# --- warps and detail --------------------------------------------------------------------------------------------

def _warp_position(p, ctx):
    n1 = fractal_noise(ctx.p, p.frequency, p.octaves, 2, 0.5, ctx.tile)
    n2 = fractal_noise(ctx.p + Vec(37.2, 11.7), p.frequency, p.octaves, 2, 0.5, ctx.tile)
    return ctx.p + Vec(n1.x, n2.x) * p.strength


OPS['warp'] = dict(
    label='Warp', category='modify',
    doc='Displaces the sampling position by noise — the cheapest route to organic, non-gridded landforms.',
    params={
        'frequency': P.float(2, 0.25, 32, structural=True, periodFreq=True),
        'strength': P.float(0.12, 0, 1),
        'octaves': P.int(2, 1, 5),
    }, warpsPosition=True, apply=lambda f, p, ctx: f, warpPosition=_warp_position)


def _roughen(f, p, ctx):
    n = fractal_noise(ctx.p, p.frequency, p.octaves, 2, 0.5, ctx.tile)
    gate = mix(1.0, clamp(length(G(f)) * 2.0, 0.0, 1.0), p.slopeOnly)
    return field(H(f) + n.x * p.amplitude * gate, G(f) + Vec(n.y, n.z) * p.amplitude * gate, AUX(f))


OPS['roughen'] = dict(
    label='Roughen', category='surface',
    doc='Adds high-frequency detail, optionally only on slopes so flats stay clean.',
    params={
        'frequency': P.float(24, 1, 200, structural=True, periodFreq=True),
        'amplitude': P.float(0.08, 0, 0.2),
        'octaves': P.int(2, 1, 6),
        'slopeOnly': P.float(0, 0, 1, doc='blend toward slope-gated'),
    }, apply=_roughen)


def _combine(f, p, ctx):
    a = ctx.inputs.get('in', f) if ctx.inputs else f
    k = p.amount

    def has(n):
        return (n in ctx.wired) if ctx.wired is not None else True

    out = blend_field(a, ctx.inputs['in2'], p.mode, k) if has('in2') else a
    if has('in3'):
        out = blend_field(out, ctx.inputs['in3'], p.mode, k)
    if p.output == 'clamp':
        inside = (out.x > 0) & (out.x < 1)
        out = field(clamp(out.x, 0.0, 1.0), G(out) * step01(inside), AUX(out))
    return out


OPS['combine'] = dict(
    label='Combine', category='utility',
    doc='Merges up to three fields with any of 24 blend modes.',
    params={
        'mode': P.enum('add', COMBINE_MODE_VALUES),
        'amount': P.float(0.5, 0, 1, doc="how far the base moves toward the mode's result"),
        'output': P.enum('none', ['none', 'clamp']),
    }, apply=_combine)
