"""Ekigar operators, part 5 (registry.js SURFACE): Steps, Fractal Terraces, Sandstone and Sand: height-domain
texture and stratum transforms, each carrying its chain-rule derivative.
"""
from __future__ import annotations

import numpy as np

from ._tsl import Vec, clamp, mix, step01, dot, fract, EPS, TAU
from .noise import hash2
from .ops_shared import (P, H, G, AUX, field, remap, seed_shift, seed_offset, snap_axis, strata_fold, fbm_field,
                         js_round)

OPS = {}


def _steps(f, p, ctx):
    s = H(f) * p.density
    i = np.floor(s)
    fr = fract(s)
    j = hash2(i, float(seed_shift(p.seed)[0]), 0.0, 0.0)[0] * 0.5 + 0.5
    w = clamp(p.scale * (j * 0.7 + 0.35), 0.02, 0.92)
    start = (1.0 - w) * 0.5
    k = clamp((fr - start) / w, 0.0, 1.0)
    inside = step01((k > 0) & (k < 1))
    rise = k * k * (3.0 - k * 2.0)
    drise = k * (1.0 - k) * 6.0 / w * inside
    return remap(f, (i + rise) / p.density, drise)


OPS['steps'] = dict(
    label='Steps', category='surface',
    doc='Hard stepped breaks in the terrain, with unequal risers.',
    params={
        'density': P.float(14, 2, 120, doc='steps through the height range'),
        'scale': P.float(0.45, 0.02, 1, doc='riser width; smaller values make harder steps'),
        'seed': P.int(0, 0, 65535),
    }, apply=_steps)


def _fractal_terraces(f, p, ctx):
    sa = seed_shift(p.seed)[0]
    h = H(f)
    dfdh = 1.0
    bands = 1.0 / np.maximum(p.spacing, 1e-3)
    amp = 1.0
    for o in range(int(p.octaves)):
        phase = ((sa * (o + 7) * 2654435761) % 1000) / 1000.0
        s = h * bands + phase
        i = np.floor(s)
        fr = fract(s)
        k = clamp(fr / p.shape, 0.0, 1.0)
        sm = k * k * (3.0 - k * 2.0)
        target = (i + sm - phase) / bands
        dtarget = k * (1.0 - k) * 6.0 / p.shape
        w = p.intensity * amp
        h = mix(h, target, w)
        dfdh = dfdh * mix(1.0, dtarget, w)
        bands = bands * 2.0
        amp = amp * 0.5
    return remap(f, h, dfdh)


OPS['fractalTerraces'] = dict(
    label='Fractal Terraces', category='surface',
    doc='Terraces within terraces — a stronger alternative to Terraces.',
    params={
        'spacing': P.float(0.12, 0.01, 0.5, doc='height between the coarsest terraces'),
        'octaves': P.int(3, 1, 5),
        'intensity': P.float(0.7, 0, 1),
        'shape': P.float(0.5, 0.02, 1),
        'seed': P.int(0, 0, 65535),
    }, apply=_fractal_terraces)


def _sandstone(f, p, ctx):
    ax, ay = snap_axis(p.direction)
    nf = max(1, js_round(p.chaosScale))
    n = fbm_field(ctx, frequency=nf, octaves=3, offset=seed_offset(p.seed, nf))
    tile_len = max(abs(ctx.tile.x if ax != 0 else ctx.tile.y), EPS)
    phase = dot(ctx.p, Vec(float(ax), float(ay))) * (TAU / tile_len)
    height_weight = 0.58
    tilt_amp = p.tilt * 0.75
    tilt_v = np.sin(phase) * tilt_amp
    tilt_g = Vec(float(ax), float(ay)) * (np.cos(phase) * tilt_amp * (TAU / tile_len))
    chaos_amp = p.chaos * p.spacing * 0.42
    u = H(f) * height_weight + tilt_v + n.v * chaos_amp
    du = G(f) * height_weight + tilt_g + n.g * chaos_amp
    lam_u, lam_du = u, du
    h, g = H(f), G(f)
    sp = np.maximum(p.spacing, 1e-3)
    amp = 1.0
    layer = None
    for _ in range(int(p.passes)):
        s = u / sp
        fr = fract(s)
        w = p.intensity * amp
        folded = strata_fold(u, 1.0 / sp, w, p.convexity)
        delta = folded.v - u
        d_delta = du * (folded.d - 1.0)
        h = h + delta
        g = g + d_delta
        u = folded.v
        du = du * folded.d
        if layer is None:
            layer = fr
        sp = sp * 0.5
        amp = amp * 0.5
    lam_k = TAU * 8 / np.maximum(p.spacing, 1e-3)
    lam_amp = p.spacing * p.intensity * 0.006
    lam_phase = lam_u * lam_k
    h = h + np.sin(lam_phase) * lam_amp
    g = g + lam_du * (np.cos(lam_phase) * lam_k * lam_amp)
    return {'field': field(h, g, layer), 'outs': {'layers': clamp(layer, 0.0, 1.0)}}


OPS['sandstone'] = dict(
    label='Sandstone', category='surface',
    doc='Layered sandstone terracing and sedimentary bedding. Emits a Layers mask.',
    params={
        'passes': P.int(1, 1, 4),
        'spacing': P.float(0.115, 0.005, 0.3),
        'intensity': P.float(0.96, 0, 1),
        'convexity': P.float(0.35, 0, 1),
        'tilt': P.float(0.24, 0, 0.6, doc='amplitude of a seamless directional bed warp'),
        'direction': P.float(0, 0, 360, structural=True,
                             doc='degrees, snapped to a lattice axis so bedding stays seamless'),
        'chaos': P.float(0.16, 0, 1, doc='irregularity; phase displacement stays below half a bed'),
        'chaosScale': P.float(6, 1, 32, structural=True, periodFreq=True),
        'seed': P.int(0, 0, 65535),
    }, apply=_sandstone)


def _sand(f, p, ctx):
    ax, ay = snap_axis(p.direction)
    cells = max(1, js_round(p.frequency))
    nf = max(1, js_round(p.chaosScale))
    t = ctx.tile.x if ctx.tile.x > 0 else 1.0
    n = fbm_field(ctx, frequency=nf, octaves=2, offset=seed_offset(p.seed, nf))
    wt = p.warpByTerrain * 4.0
    axv = Vec(float(ax), float(ay))
    phase = dot(ctx.p, axv) / t * cells + n.v * p.chaos * 2.0 + H(f) * wt
    dphase = axv * (cells / t) + n.g * p.chaos * 2.0 + G(f) * wt
    s = np.sin(phase * TAU)
    c = np.cos(phase * TAU)
    v = mix(np.abs(s), s * 0.5 + 0.5, p.softness)
    dv = mix(np.sign(s) * c, c * 0.5, p.softness) * TAU
    return field(H(f) + v * p.height, G(f) + dphase * dv * p.height, AUX(f))


OPS['sand'] = dict(
    label='Sand', category='surface',
    doc='Medium and small sand patterns, and dunes.',
    params={
        'frequency': P.float(28, 2, 200, structural=True, periodFreq=True, doc='ripples across the tile'),
        'direction': P.float(0, 0, 360, structural=True),
        'chaos': P.float(0.5, 0, 1),
        'softness': P.float(0.5, 0, 1),
        'height': P.float(0.03, 0, 0.3),
        'warpByTerrain': P.float(0, 0, 1),
        'chaosScale': P.float(4, 1, 32, structural=True, periodFreq=True),
        'seed': P.int(0, 0, 65535),
    }, apply=_sand)
