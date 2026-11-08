"""Ekigar operators, part 4 (registry.js PRIMITIVE): Perlin, Cellular, Dot Noise, Line Noise, Cracks, Shape, Cone,
Hemisphere and Pattern, each with the exact gradient of what it adds.
"""
from __future__ import annotations

import math

import numpy as np

from ._tsl import Vec, clamp, mix, select, step01, dot, length, fract, EPS, TAU
from .noise import hash2
from .ops_shared import (P, H, G, AUX, field, wrapped_delta, seed_shift, seed_offset, snap_axis, sstep, js_round,
                         fbm_field, ridged_field, billowy_field, cell_search, cell_metric, euclid_metric, warp_jac)

OPS = {}


def _perlin(f, p, ctx):
    nf = p.frequency
    kw = dict(frequency=nf, octaves=p.octaves, lacunarity=p.lacunarity, gain=p.gain, offset=seed_offset(p.seed, nf))
    if p.type == 'ridged':
        n = ridged_field(ctx, **kw)
    elif p.type == 'billowy':
        n = billowy_field(ctx, **kw)
    else:
        n = fbm_field(ctx, **kw)
    k = p.height * 0.5
    return field(n.v * k + 0.5, n.g * k, AUX(f))


OPS['perlin'] = dict(
    label='Perlin', category='primitive', generator=True,
    doc='One coherent-noise node covering fBm, ridged and billowy variants.',
    params={
        'type': P.enum('fbm', ['fbm', 'ridged', 'billowy']),
        'frequency': P.float(3, 0.25, 64, structural=True, periodFreq=True, doc='noise cells across the tile'),
        'octaves': P.int(5, 1, 10),
        'lacunarity': P.int(2, 2, 4),
        'gain': P.float(0.5, 0.05, 0.95, structural=True, maskable=False),
        'height': P.float(0.6, 0, 2),
        'seed': P.int(0, 0, 65535),
    }, apply=_perlin)


def _cellular(f, p, ctx):
    cells = max(1, js_round(p.frequency))
    sa, sb = seed_shift(p.seed)
    period = (ctx.tile.x * cells, ctx.tile.y * cells)
    c = cell_search(ctx.p * cells, period, p.jitter, Vec(float(sa), float(sb)),
                    lambda d: cell_metric(p.distanceMetric, d, p.metricMorph))
    fn = p.distanceFunction
    if fn == 'hash':
        raw, d_raw = c.rand.x, Vec(0.0, 0.0)
    elif fn == 'distanceInv':
        raw, d_raw = 1.0 - c.f1, -c.g1
    elif fn == 'distance2Inv':
        raw, d_raw = 1.0 - c.f2, -c.g2
    elif fn == 'distanceToEdge':
        raw, d_raw = (c.f2 - c.f1) * 0.5, (c.g2 - c.g1) * 0.5
    else:
        raw, d_raw = c.f2 - c.f1, c.g2 - c.g1
    gate = step01((raw > 0) & (raw < 1))
    v = clamp(raw, 0.0, 1.0)
    return {'field': field(H(f) + v * p.height, G(f) + d_raw * (-cells) * p.height * gate, AUX(f)),
            'outs': {'cells': v}}


OPS['cellular'] = dict(
    label='Cellular', category='primitive', generator=True,
    doc='Cell-based patterns — mesas, plates, crack networks, per-cell random.',
    params={
        'frequency': P.float(8, 1, 64, structural=True, periodFreq=True, doc='cells across the tile'),
        'jitter': P.float(0.85, 0, 1),
        'distanceMetric': P.enum('euclidianManhattan', ['euclidianManhattan', 'euclidianChebyshev']),
        'metricMorph': P.float(0, 0, 1, doc='morphs Euclidian toward the metric named second'),
        'distanceFunction': P.enum('distanceDiff', ['hash', 'distanceInv', 'distance2Inv', 'distanceDiff',
                                                    'distanceToEdge']),
        'height': P.float(0.5, 0, 2),
        'seed': P.int(0, 0, 65535),
    }, apply=_cellular)


def _dot_noise(f, p, ctx):
    sa, sb = seed_shift(p.seed)
    h = g = None
    cells, amp = max(1, js_round(p.frequency)), 1.0
    for it in range(int(p.iterations)):
        perx, pery = ctx.tile.x * cells, ctx.tile.y * cells
        sp = ctx.p * cells
        cell = sp.floor()
        frc = sp.fract()
        hx, hy = hash2(cell.x + float(sa + it * 17), cell.y + float(sb + it * 29), perx, pery)
        hh = Vec(hx * 0.5 + 0.5, hy * 0.5 + 0.5)
        rad = p.size * 0.5
        jit = hh * (1.0 - p.size) + rad
        d = frc - jit
        ln = np.maximum(length(d), 1e-6)
        xw = np.abs(d.x) > np.abs(d.y)
        if p.style == 'square':
            r = np.maximum(np.abs(d.x), np.abs(d.y))
            drdd = Vec(np.where(xw, np.sign(d.x), 0.0), np.where(xw, 0.0, np.sign(d.y)))
        else:
            r = ln
            drdd = d / ln
        t = clamp(1.0 - r / np.maximum(rad, EPS), 0.0, 1.0)
        v = t * t * amp
        dv = t * -2.0 / np.maximum(rad, EPS) * amp * step01(t > 0)
        h = v if h is None else h + v
        gg = drdd * dv * cells
        g = gg if g is None else g + gg
        cells *= 2
        amp *= 0.5
    k = p.height * p.multiplier
    return field(H(f) + h * k, G(f) + g * k, AUX(f))


OPS['dotNoise'] = dict(
    label='Dot Noise', category='primitive', generator=True,
    doc='Dotted or speckled noise for texturing and breakup.',
    params={
        'style': P.enum('dot', ['dot', 'square']),
        'iterations': P.int(2, 1, 5),
        'frequency': P.float(12, 1, 96, structural=True, periodFreq=True),
        'size': P.float(0.6, 0.05, 1, doc='dot diameter as a fraction of its cell'),
        'multiplier': P.float(1, 0, 4),
        'height': P.float(0.2, 0, 1),
        'seed': P.int(0, 0, 65535),
    }, apply=_dot_noise)

_LINE_EXP = {'sharp': 1, 'soft': 2, 'flat': 0.4, 'vague': 3}


def _line_noise(f, p, ctx):
    ax, ay = snap_axis(p.direction)
    t = max(abs(ax) * ctx.tile.x + abs(ay) * ctx.tile.y, EPS)
    cells = max(1, js_round(p.frequency))
    sa = seed_shift(p.seed)[0]
    u = dot(ctx.p, Vec(float(ax), float(ay))) / t * cells
    dudp = Vec(float(ax), float(ay)) * (cells / t)
    band = np.floor(u)
    fr = fract(u)
    hx, hy = hash2(band + float(sa), 0.0, float(cells), 0.0)
    centre = mix(0.5, hx * 0.5 + 0.5, p.jitter)
    half_w = np.maximum(mix(0.4, hy * 0.22 + 0.3, p.jitter), EPS)
    off = fr - centre
    q = np.abs(off) / half_w
    t01 = clamp(1.0 - q, 0.0, 1.0)
    ex = _LINE_EXP[p.style]
    b = np.maximum(t01, EPS)
    raw = np.power(b, ex)
    d_raw = np.power(b, ex - 1) * (-ex) / half_w * np.sign(off) * step01(t01 > 0)
    lim = raw < p.clampAmount
    v = np.minimum(raw, p.clampAmount)
    return field(H(f) + v * p.height, G(f) + dudp * d_raw * p.height * step01(lim), AUX(f))


OPS['lineNoise'] = dict(
    label='Line Noise', category='primitive', generator=True,
    doc='Sets of lines that layer with other noises into ridges.',
    params={
        'frequency': P.float(10, 1, 64, structural=True, periodFreq=True),
        'direction': P.float(0, 0, 360, structural=True,
                             doc='degrees, snapped to a lattice axis so the tile stays seamless'),
        'style': P.enum('sharp', ['sharp', 'soft', 'flat', 'vague']),
        'jitter': P.float(0.5, 0, 1),
        'clampAmount': P.float(1, 0.05, 1, doc='maximum line intensity'),
        'height': P.float(0.35, 0, 2),
        'seed': P.int(0, 0, 65535),
    }, apply=_line_noise)

_CRACK_EXP = {'normal': 2, 'hard': 1, 'classic': 4}


def _cracks(f, p, ctx):
    sa, sb = seed_shift(p.seed)
    wf = max(1, js_round(p.warpSize))
    w = warp_jac(ctx, frequency=wf, octaves=2, strength=p.warpStrength * 0.15, offset=seed_offset(p.seed, wf))
    ex = _CRACK_EXP[p.style]
    vq = gq = None
    cells, amp = max(2, js_round(p.frequency)), 1.0
    for o in range(int(p.octaves)):
        period = (ctx.tile.x * cells, ctx.tile.y * cells)
        c = cell_search(w.q * cells, period, p.jitter, Vec(float(sa + o * 13), float(sb + o * 41)), euclid_metric)
        e = c.f2 - c.f1
        de = c.g2 - c.g1
        t = clamp(1.0 - e / p.width, 0.0, 1.0)
        b = np.maximum(t, EPS)
        prof = np.power(b, ex) * amp
        d_prof = np.power(b, ex - 1) * (-ex) / p.width * amp * step01(t > 0)
        vq = prof if vq is None else vq + prof
        gg = de * (-cells) * d_prof
        gq = gg if gq is None else gq + gg
        cells *= 2
        amp *= 0.5
    return {'field': field(H(f) - vq * p.depth, G(f) - w.pull(gq) * p.depth, AUX(f)),
            'outs': {'cracks': clamp(vq, 0.0, 1.0)}}


OPS['cracks'] = dict(
    label='Cracks', category='primitive', generator=True,
    doc='Large cracked patterns on a flat base.',
    params={
        'style': P.enum('normal', ['normal', 'hard', 'classic']),
        'octaves': P.int(2, 1, 4),
        'frequency': P.float(6, 1, 32, structural=True, periodFreq=True),
        'depth': P.float(0.3, 0, 1),
        'width': P.float(0.18, 0.02, 0.6, doc='border distance the crack reaches, in cell units'),
        'jitter': P.float(0.85, 0, 1),
        'warpStrength': P.float(0.25, 0, 1),
        'warpSize': P.float(3, 1, 24, structural=True, periodFreq=True),
        'seed': P.int(0, 0, 65535),
    }, apply=_cracks)


def _shape(f, p, ctx):
    d = wrapped_delta(ctx.p, Vec(p.x, p.y), ctx.tile)
    sc = np.maximum(p.scale, EPS)
    q = Vec(d.x / p.scaleX, d.y / p.scaleY) / sc

    def back(gq):
        return Vec(gq.x / p.scaleX, gq.y / p.scaleY) / sc

    if p.geometry == 'rectangle':
        xw = np.abs(q.x) > np.abs(q.y)
        sd = np.maximum(np.abs(q.x), np.abs(q.y)) - 1.0
        gsd = Vec(np.where(xw, np.sign(q.x), 0.0), np.where(xw, 0.0, np.sign(q.y)))
    elif p.sides >= 3:
        inr = math.cos(math.pi / p.sides)
        best = best_n = None
        for i in range(int(p.sides)):
            a = (i / p.sides) * TAU
            n = Vec(math.cos(a), math.sin(a))
            v = dot(q, n)
            if best is None:
                best, best_n = v, n
            else:
                win = v > best
                best_n = select(win, n, best_n)
                best = np.maximum(best, v)
        sd = best - inr
        gsd = best_n
    else:
        ln = np.maximum(length(q), 1e-6)
        sd = ln - 1.0
        gsd = q / ln
    fill = sstep(-p.falloff, p.falloff, sd)
    hole = sstep(-p.falloff, p.falloff, sd + p.thickness)
    v = hole.v - fill.v
    dvdsd = hole.d - fill.d
    return field(H(f) + v * p.height, G(f) + back(gsd) * dvdsd * p.height, AUX(f))


OPS['shape'] = dict(
    label='Shape', category='primitive', generator=True,
    doc='Basic geometric primitives for shapes and masks.',
    params={
        'geometry': P.enum('circle', ['circle', 'rectangle']),
        'sides': P.int(0, 0, 16, doc='0 is a true circle; 3 and up make a regular polygon'),
        'scale': P.float(0.35, 0.02, 2),
        'scaleX': P.float(1, 0.1, 4, structural=True),
        'scaleY': P.float(1, 0.1, 4, structural=True),
        'thickness': P.float(1.5, 0.02, 1.5, doc='1.5 is a filled shape; smaller leaves a ring of that width'),
        'height': P.float(0.5, 0, 2),
        'x': P.float(0.5, -1, 2),
        'y': P.float(0.5, -1, 2),
        'falloff': P.float(0.05, 0.002, 0.5),
    }, apply=_shape)


def _cone(f, p, ctx):
    d = wrapped_delta(ctx.p, Vec(p.x, p.y), ctx.tile)
    ln = np.maximum(length(d), 1e-6)
    sc = np.maximum(p.scale, EPS)
    r = ln / sc
    v = clamp(1.0 - r, 0.0, 1.0)
    gate = step01(r < 1)
    return field(H(f) + v * p.height, G(f) - d / ln / sc * p.height * gate, AUX(f))


OPS['cone'] = dict(
    label='Cone', category='primitive', generator=True,
    doc='A simple conical gradient.',
    params={'scale': P.float(0.45, 0.02, 2), 'height': P.float(0.6, 0, 2),
            'x': P.float(0.5, -1, 2), 'y': P.float(0.5, -1, 2)},
    apply=_cone)


def _hemisphere(f, p, ctx):
    d = wrapped_delta(ctx.p, Vec(p.x, p.y), ctx.tile)
    ln = np.maximum(length(d), 1e-6)
    sc = np.maximum(p.scale, EPS)
    r = ln / sc
    u = clamp(1.0 - r * r, 0.0, 1.0)
    inside = r < 1
    if p.flatten:
        s = u * 1.6
        v = clamp(s, 0.0, 1.0)
        dvdr = r * -3.2 * step01(s < 1)
    else:
        v = np.sqrt(u)
        dvdr = -r / np.maximum(np.sqrt(u), 1e-3)
    return field(H(f) + v * p.height, G(f) + d / ln / sc * dvdr * p.height * step01(inside), AUX(f))


OPS['hemisphere'] = dict(
    label='Hemisphere', category='primitive', generator=True,
    doc='A hemispherical gradient for domes, mounds and radial falloffs.',
    params={'scale': P.float(0.45, 0.02, 2), 'height': P.float(0.6, 0, 2),
            'x': P.float(0.5, -1, 2), 'y': P.float(0.5, -1, 2), 'flatten': P.bool(False)},
    apply=_hemisphere)


def _pattern(f, p, ctx):
    n = max(1, js_round(p.steps))
    t = ctx.tile.x if ctx.tile.x > 0 else 1.0
    ax, ay = snap_axis(p.direction)
    along = Vec(float(ax), float(ay))
    across = Vec(float(-ay), float(ax))
    u = dot(ctx.p, along) / t * n
    w = dot(ctx.p, across) / t * n
    k = n / t

    def band(c):
        off = fract(c) - 0.5
        hw = np.maximum(p.dotSize * p.spacing * 0.5, EPS)
        v = clamp(1.0 - np.abs(off) / hw, 0.0, 1.0)
        return v, -np.sign(off) / hw * step01(v > 0)

    if p.type == 'dots':
        av, ad = band(u)
        bv, bd = band(w)
        v = av * bv
        g = along * (ad * bv * k) + across * (bd * av * k)
        return field(H(f) + v * p.height, G(f) + g * p.height, AUX(f))
    if p.type == 'grid':
        av, ad = band(u)
        bv, bd = band(w)
        v = np.maximum(av, bv)
        aw = step01(av > bv)
        g = along * (ad * aw * k) + across * (bd * (1.0 - aw) * k)
        return field(H(f) + v * p.height, G(f) + g * p.height, AUX(f))
    av, ad = band(u)
    s = -1 if p.type == 'engraving' else 1
    return field(H(f) + av * p.height * s, G(f) + along * (ad * k) * p.height * s, AUX(f))


OPS['pattern'] = dict(
    label='Pattern', category='primitive', generator=True,
    doc='Repeatable geometric patterns for masking and stylised work.',
    params={
        'type': P.enum('lines', ['lines', 'engraving', 'grid', 'dots']),
        'steps': P.float(12, 1, 200, structural=True, periodFreq=True, doc='repetitions across the tile'),
        'dotSize': P.float(0.4, 0.02, 1),
        'spacing': P.float(0.5, 0.05, 1),
        'direction': P.float(0, 0, 360, structural=True, doc='degrees, snapped to a lattice axis'),
        'height': P.float(0.3, 0, 2),
    }, apply=_pattern)
