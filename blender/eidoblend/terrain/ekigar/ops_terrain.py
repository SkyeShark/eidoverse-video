"""Ekigar operators, part 6 (registry.js TERRAIN and UTILITY): the complete landform generators Mountain, Mountain
Range, Canyon, Island, Volcano and Rugged, and the utility nodes Math, Route, Switch and Compare.
"""
from __future__ import annotations

import math

import numpy as np

from ._tsl import Vec, Params, clamp, lerp, select, step01, length, fract, EPS, TAU
from .noise import noised
from .phacelle import erosion_operator
from .ops_shared import (P, H, G, AUX, field, remap, wrapped_delta, seed_shift, seed_offset, snap_axis, sstep,
                         strata_fold, swiss_field, fbm_field, bench_stack, breach, nonzero, js_round)

OPS = {}


def _mountain(f, p, ctx):
    d = wrapped_delta(ctx.p, Vec(p.x, p.y), ctx.tile)
    ln = np.maximum(length(d), 1e-6)
    sc = np.maximum(p.scale, EPS)
    r = ln / sc
    rc = clamp(r, 0.0, 1.0)
    env = np.cos(rc * math.pi) * 0.5 + 0.5
    inside = step01(r < 1)
    drdp = d / ln / sc
    denv = drdp * (np.sin(rc * math.pi) * (-0.5 * math.pi)) * inside
    K = {'low': 1.5, 'medium': 1.1, 'high': 0.75}[p.bulk]
    GAIN = {'basic': 0.5, 'eroded': 0.5, 'old': 0.42, 'alpine': 0.52, 'strata': 0.5}[p.style]
    oct_ = max(2, p.octaves - 2) if p.reduceDetails else p.octaves
    nf = max(1, js_round(p.frequency))
    off = seed_offset(p.seed, nf)
    nfa = max(1, js_round(nf * 1.5))
    if p.style == 'alpine':
        t = swiss_field(ctx, frequency=nfa, octaves=oct_, gain=GAIN + 0.02, warp=0.6, offset=seed_offset(p.seed, nfa))
    else:
        t = swiss_field(ctx, frequency=nf, octaves=oct_, gain=GAIN,
                        warp=0.1 if p.style == 'basic' else (0.5 if p.style == 'old' else 0.35), offset=off)
    mass_k = np.power(env, K)
    dmass_k = denv * (np.power(np.maximum(env, EPS), K - 1) * K)
    det = t.v * 0.55 + 0.45
    v = mass_k * det + t.v * 0.06
    g = dmass_k * det + t.g * 0.55 * mass_k + t.g * 0.06
    if p.style == 'strata':
        sf = strata_fold(v, 8.0, 0.5, 0.72)
        g = g * sf.d
        v = sf.v
    return field(H(f) + v * p.height, G(f) + g * p.height, AUX(f))


OPS['mountain'] = dict(
    label='Mountain', category='terrain',
    doc='A single mountain massif: a broad dome carrying swiss-turbulence ridges and radial spurs, with detail that '
        'survives to the summit.',
    params={
        'scale': P.float(0.52, 0.05, 2), 'height': P.float(0.8, 0, 2),
        'style': P.enum('eroded', ['basic', 'eroded', 'old', 'alpine', 'strata']),
        'bulk': P.enum('medium', ['low', 'medium', 'high']),
        'frequency': P.float(7, 1, 64, structural=True, periodFreq=True),
        'octaves': P.int(6, 1, 9),
        'reduceDetails': P.bool(False),
        'seed': P.int(0, 0, 65535),
        'x': P.float(0.5, -1, 2), 'y': P.float(0.5, -1, 2),
    }, apply=_mountain)


ALPINE_EROSION = dict(strength=0.13, scale=0.1, gullyWeight=0.55, detail=1.6, octaves=4, lacunarity=2, gain=0.5,
                      cellScale=0.7, normalization=0.35, ridgeRounding=0.22, creaseRounding=0.08)


def _mountain_range(f, p, ctx):
    GAIN = {'low': 0.44, 'medium': 0.5, 'high': 0.56}[p.bulk]
    nf = max(1, js_round(p.frequency))
    off = seed_offset(p.seed, nf)
    alpine = p.style == 'alpine'
    nfa = max(1, js_round(nf * 1.5))
    if alpine:
        t = swiss_field(ctx, frequency=nfa, octaves=p.octaves, gain=GAIN + 0.04, warp=0.6,
                        offset=seed_offset(p.seed, nfa))
    else:
        t = swiss_field(ctx, frequency=nf, octaves=p.octaves, gain=GAIN, warp=0.12 if p.style == 'basic' else 0.38,
                        offset=off)
    mf = max(1, js_round(nf / 2))
    mass = fbm_field(ctx, frequency=mf, octaves=2, offset=seed_offset(p.seed + 511, mf))
    env = 1.0 - p.relief * 0.5 + mass.v * p.relief * 0.5
    denv = mass.g * p.relief * 0.5
    v = t.v * env
    g = t.g * env + denv * t.v
    if p.style == 'stratified':
        sf = strata_fold(v, 9.0, 0.55, 0.7)
        g = g * sf.d
        v = sf.v
    out = field(H(f) + v * p.height, G(f) + g * p.height, AUX(f))
    if alpine:
        out = erosion_operator(out, Params(ALPINE_EROSION), ctx)
    return out


OPS['mountainRange'] = dict(
    label='Mountain Range', category='terrain',
    doc='A full mountainous terrain covering the whole tile: swiss/jordan turbulence with derivative feedback, so '
        'slopes carry water-carved flow lines and detail concentrates on the ridges.',
    params={
        'frequency': P.float(4, 0.5, 32, structural=True, periodFreq=True),
        'height': P.float(0.7, 0, 2),
        'style': P.enum('eroded', ['basic', 'eroded', 'stratified', 'alpine']),
        'bulk': P.enum('medium', ['low', 'medium', 'high']),
        'octaves': P.int(7, 1, 10),
        'relief': P.float(0.5, 0, 1,
                          doc='large-scale mass variation — lowlands and massifs rather than uniform mountains'),
        'seed': P.int(0, 0, 65535),
    }, apply=_mountain_range)


def _canyon(f, p, ctx):
    t = ctx.tile.x if ctx.tile.x > 0 else 1.0
    sa, sb = seed_shift(p.seed)
    ax, ay = snap_axis(p.direction)
    along = (ctx.p.x * ay + ctx.p.y * ax) / t
    across = (ctx.p.x * ax + ctx.p.y * ay) / t
    k1, k2 = p.meanders, p.meanders * 2 + 1
    ph1, ph2 = (sa % 360) * math.pi / 180, (sb % 360) * math.pi / 180
    a1, a2 = p.structuralWarp * 0.18, p.structuralWarp * 0.05
    s1 = along * (TAU * k1) + ph1
    s2 = along * (TAU * k2) + ph2
    cx = 0.5 + np.sin(s1) * a1 + np.sin(s2) * a2
    dcx = np.cos(s1) * a1 * (TAU * k1 / t) + np.cos(s2) * a2 * (TAU * k2 / t)
    dx = across - cx
    wx = dx - np.floor(dx + 0.5)
    sc = np.maximum(p.scale, EPS)
    r = np.abs(wx) / sc
    sg = np.sign(wx) / sc
    drdp = Vec(sg * (ax / t) - sg * dcx * (ay / t), sg * (ay / t) - sg * dcx * (ax / t))
    nf = max(1, js_round(p.detailFrequency))
    pf = max(1, js_round(nf / 4))
    pl = fbm_field(ctx, frequency=pf, octaves=3, offset=seed_offset(p.seed + 977, pf))
    plateau = pl.v * 0.1
    dplateau = pl.g * 0.1
    pl_w = fbm_field(ctx, frequency=pf, octaves=2, offset=seed_offset(p.seed + 1481, pf))
    pl_f = fbm_field(ctx, frequency=pf * 5, octaves=2, offset=seed_offset(p.seed + 733, pf * 5))
    w_narrow = clamp(1.0 - p.scale * 2.2, 0.0, 0.85)
    prof = sstep(clamp(p.slot, 0.02, 0.9), 1.0, r)
    kv = 1.0 + p.valley * 1.4
    pv0 = np.power(np.maximum(prof.v, EPS), kv)
    dpv0 = kv * np.power(np.maximum(prof.v, EPS), kv - 1.0) * prof.d
    ks = 1.0 + p.softness * 2.5
    om = np.maximum(1.0 - pv0, EPS)
    soft = 1.0 - np.power(om, ks)
    dsoft = ks * np.power(om, ks - 1.0)
    wgt = sstep(0.5 - w_narrow * 0.3, 1.0, pv0)
    pv = pv0 + wgt.v * (soft - pv0)
    dpvdpv0 = 1.0 + wgt.d * (soft - pv0) + wgt.v * (dsoft - 1.0)
    dpv = dpvdpv0 * dpv0
    v = plateau - (1.0 - pv) * p.depth
    g = dplateau + drdp * dpv * p.depth
    wall_mask = pv * (1.0 - pv) * 4.0
    dep = np.maximum(p.depth, EPS)
    b_inv = 1.0 / max(1, p.bands)
    s_in0 = v / dep + 1.0
    g_in0 = g / dep
    phi_b = p.bands * 2.39996
    bed_arg = s_in0 * phi_b + (p.seed % 7)
    m_ph = np.sin(bed_arg) * 0.5 + 0.5
    dm_ph = np.cos(bed_arg) * 0.5 * phi_b
    wob_broad = pl.v * m_ph + pl_w.v * (1.0 - m_ph)
    dwob_broad = pl.g * m_ph + pl_w.g * (1.0 - m_ph) + g_in0 * dm_ph * (pl.v - pl_w.v)
    wob = lerp(wob_broad, pl_f.v, w_narrow) * 0.55
    dwob = lerp(dwob_broad, pl_f.g, w_narrow) * 0.55
    strength_mod = np.sin(s_in0 * (p.bands * 1.13) + 2.1) * 0.45 + 0.55
    strength = (p.strata * 0.4 if p.style == 'classic' else p.strata) * (wall_mask * 0.85 + 0.15) * strength_mod
    s_in = s_in0 + wob * b_inv
    gs_in = g_in0 + dwob * b_inv
    bs = bench_stack(s_in, treads=p.bands, jitter=0.65, convexity=0.78, seed=p.seed)
    folded = lerp(s_in, bs.v, strength)
    dfold = lerp(1.0, bs.d, strength)
    g = (gs_in * dfold - dwob * b_inv) * dep
    v = (folded - wob * b_inv - 1.0) * dep
    det = swiss_field(ctx, frequency=nf, octaves=4, gain=0.5, warp=0.3, offset=seed_offset(p.seed, nf))
    wall_band = prof.d * sc * 0.6
    amp = p.detailWarp * 0.085 + wall_band * p.detailWarp * 0.05
    v = v + (det.v - 0.5) * amp
    g = g + det.g * amp
    keep = lerp(p.surrounding, 1.0, pv)
    dkeep_scale = 1.0 - p.surrounding
    cut = 1.0 - pv
    g_keep = G(f) * keep + drdp * dpv * dkeep_scale * H(f)
    return {'field': field(H(f) * keep + v, g_keep + g, clamp(cut, 0.0, 1.0)),
            'outs': {'depth': clamp(cut, 0.0, 1.0)}}


OPS['canyon'] = dict(
    label='Canyon', category='terrain',
    doc='A meandering canyon carved through stratified plateau country: flat floor, stepped strata walls that follow '
        'the CONTOURS, broad rim flare. Emits a Depth mask.',
    params={
        'style': P.enum('eroded', ['classic', 'eroded', 'strata']),
        'scale': P.float(0.4, 0.03, 1, doc='WIDTH of the whole canyon — valley half-width as a fraction of the tile'),
        'slot': P.float(0.18, 0.02, 0.7, doc='flat floor radius, relative to the valley'),
        'valley': P.float(0.5, 0, 1, doc='narrow inner gorge (0) to broad open valley (1)'),
        'surrounding': P.float(0.4, 0, 1, doc='how much of the incoming landform survives on the canyon floor'),
        'depth': P.float(0.6, 0, 1),
        'strata': P.float(0.55, 0, 1, doc='how strongly the walls terrace into beds'),
        'softness': P.float(0.35, 0, 1,
                            doc='rounds the canyon rim — 0 is a hard caprock edge, 1 a long soft shoulder'),
        'bands': P.int(10, 2, 24, doc='strata beds across the full depth'),
        'structuralWarp': P.float(0.35, 0, 1),
        'meanders': P.int(2, 1, 6, doc='whole meanders across the tile, so the channel closes on the seam'),
        'detailWarp': P.float(0.4, 0, 1),
        'detailFrequency': P.float(14, 1, 64, structural=True, periodFreq=True),
        'direction': P.float(90, 0, 360, structural=True,
                             doc='degrees, snapped to a lattice axis so the channel stays seamless'),
        'seed': P.int(0, 0, 65535),
    }, apply=_canyon)


def _island(f, p, ctx):
    nf = max(1, js_round(p.coastFrequency))
    cn = fbm_field(ctx, frequency=nf, octaves=4, offset=seed_offset(p.seed, nf))
    d = wrapped_delta(ctx.p, Vec(p.x, p.y), ctx.tile)
    ln = np.maximum(length(d), 1e-6)
    sz = np.maximum(p.size, EPS)
    r = ln / sz + cn.v * p.chaos * 0.9
    drdp = d / ln / sz + cn.g * p.chaos * 0.9
    coast = sstep(0.62, 1.05, r)
    mask = 1.0 - coast.v
    dmask = -coast.d
    inf2 = max(1, js_round(p.frequency))
    sw = swiss_field(ctx, frequency=inf2, octaves=p.octaves, gain=0.5, warp=0.32, offset=seed_offset(p.seed + 131, inf2))
    core = np.power(np.maximum(mask, EPS), 1.7)
    dcore = drdp * dmask * (np.power(np.maximum(mask, EPS), 0.7) * 1.7)
    mtn = sw.v * p.relief * 0.85 + (1.0 - p.relief) * 0.25
    v = mask * 0.22 + core * mtn
    g = drdp * dmask * 0.22 + dcore * mtn + sw.g * p.relief * 0.85 * core
    b = np.maximum(p.beach, 1e-4)
    hb = v + b
    shelf = v * v / hb
    dshelf = (v * v + v * b * 2.0) / (hb * hb)
    v = shelf * p.height
    g = g * dshelf * p.height
    return field(H(f) + v, G(f) + g, AUX(f))


OPS['island'] = dict(
    label='Island', category='terrain',
    doc='A volcanic-style island: warped coastline with bays and headlands, interior mountains falling through '
        'foothills to a coastal plain, and a beach shelf at the waterline.',
    params={
        'size': P.float(0.35, 0.05, 1), 'chaos': P.float(0.45, 0, 1),
        'coastFrequency': P.float(4, 1, 32, structural=True, periodFreq=True),
        'height': P.float(0.7, 0, 2),
        'relief': P.float(0.6, 0, 1, doc='interior mountains (1) down to a low atoll (0)'),
        'beach': P.float(0.05, 0, 0.3, doc='width of the flat shelf at the waterline'),
        'frequency': P.float(9, 2, 64, structural=True, periodFreq=True, doc='interior detail frequency'),
        'octaves': P.int(6, 1, 9),
        'x': P.float(0.5, -1, 2), 'y': P.float(0.5, -1, 2),
        'seed': P.int(0, 0, 65535),
    }, apply=_island)


VOLCANO_EROSION = dict(scale=0.12, gullyWeight=0.5, detail=2.0, octaves=4, lacunarity=2, gain=0.5, cellScale=0.7,
                       normalization=0.35, ridgeRounding=0.22, creaseRounding=0.08)


def _volcano(f, p, ctx):
    d = wrapped_delta(ctx.p, Vec(p.x, p.y), ctx.tile)
    ln = np.maximum(length(d), 1e-6)
    sc = np.maximum(p.scale, EPS)
    dir_v = d / ln
    n_foot = noised(dir_v.x * 1.9, dir_v.y * 1.9, 1024.0, 1024.0)[0]
    stretch = 1.0 + n_foot * 0.16
    r = ln / sc * stretch
    drdp = d / ln / sc * stretch
    prof_k = {'cone': 1.25, 'shield': 0.7, 'strato': 2.0, 'pyroclasticShield': 1.0}[p.profile]
    ex_prof = p.bulk * (prof_k / 1.8)

    def ed_at(rr):
        rc = clamp(rr, 0.0, 1.0)
        env0 = np.cos(rc * math.pi) * 0.5 + 0.5
        env = np.power(np.maximum(env0, EPS), ex_prof)
        inside = step01(rr < 1)
        denv = ex_prof * np.power(np.maximum(env0, EPS), ex_prof - 1.0) * (np.sin(rc * math.pi) * (-0.5 * math.pi)) \
            * inside
        return env, denv

    ed_v, ed_dvdr = ed_at(r)
    n_rim = noised(dir_v.x * 3.7, dir_v.y * 3.7, 1024.0, 1024.0)[0]
    mw0 = np.maximum(p.mouth, EPS)
    mw_w = mw0 * (1.0 + n_rim * 0.10)
    e_rim_v, _ = ed_at(mw0)
    rim_top = e_rim_v + p.rimHeight * 0.25
    floor_z = e_rim_v - p.craterDepth
    wall = sstep(mw_w * clamp(p.craterFloor, 0.02, 0.9), mw_w, r)
    wexp = p.craterWall * 1.8 + 1.2
    w_rise = np.power(np.maximum(wall.v, EPS), wexp)
    dw_rise = wexp * np.power(np.maximum(wall.v, EPS), wexp - 1.0) * wall.d
    interior = floor_z + (rim_top - floor_z) * w_rise
    d_interior = (rim_top - floor_z) * dw_rise
    s_blend = sstep(mw_w * (1.0 - p.rimWidth * 0.35), mw_w * (1.0 + p.rimWidth * 0.8), r)
    br = breach(d, p.breachDir, p.breachWidth)
    open_ = br.w
    in_blend = s_blend.v + open_ * (1.0 - s_blend.v)
    v = lerp(interior, ed_v, in_blend)
    d_rad = lerp(d_interior, ed_dvdr, in_blend) + s_blend.d * (1.0 - open_) * (ed_v - interior)
    dv = drdp * d_rad + br.dwdp * (1.0 - s_blend.v) * (ed_v - interior)
    nfs = max(1, js_round(p.frequency / 3))
    t_sw = swiss_field(ctx, frequency=nfs, octaves=5, gain=0.5, warp=0.4, offset=seed_offset(p.seed, nfs))
    detail = t_sw.v * 0.55 + 0.45
    v0 = v
    v = v * detail
    dv = dv * detail + t_sw.g * v0 * 0.55
    gate = step01(r < 1)
    out_field = field(H(f) + v * p.height * gate, G(f) + dv * p.height * gate, AUX(f))
    if p.surface == 'eroded':
        out_field = erosion_operator(out_field, Params(VOLCANO_EROSION, strength=p.erosion * 0.22), ctx)
    return {'field': out_field, 'outs': {
        'crater': clamp(1.0 - r / mw_w, 0.0, 1.0) * (1.0 - open_),
        'rim': (1.0 - sstep(0.0, np.maximum(p.rimWidth, EPS), np.abs(r / mw_w - 1.0)).v) * (1.0 - open_),
        'breach': open_,
    }}


OPS['volcano'] = dict(
    label='Volcano', category='terrain',
    doc=('A volcanic edifice with a summit crater or caldera. The flanks are CONCAVE-UP — steepest at the summit, '
         'shallowing outward — which is what a real cone does and what a `pow` cone cannot; the summit hollow is a '
         'full four-zone bowl, so widening `mouth` and `craterFloor` turns the cone into a flat-floored caldera with '
         'terraced walls.'),
    params={
        'scale': P.float(0.52, 0.05, 1), 'height': P.float(0.85, 0, 2),
        'profile': P.enum('strato', ['cone', 'shield', 'strato', 'pyroclasticShield'], doc='large-scale flank family'),
        'mouth': P.float(0.24, 0.02, 0.9, doc='summit hollow radius, as a fraction of the edifice'),
        'bulk': P.float(1.8, 0.5, 4, doc='flank concavity within the selected profile'),
        'craterDepth': P.float(0.22, 0, 2, doc='depth of the summit hollow, relative to the edifice height'),
        'craterFloor': P.float(0.18, 0.02, 0.9,
                               doc='flat floor radius within the hollow — large values make a caldera plain'),
        'craterWall': P.float(0.95, 0.1, 1,
                              doc='how much of floor-to-rim is cliff; below 1 leaves a slump terrace'),
        'rimHeight': P.float(0.10, 0, 1.5, doc='raised crater rim'),
        'rimWidth': P.float(0.12, 0.02, 1),
        'breachDir': P.float(0, 0, 360, structural=True, doc='azimuth of the outflow gap'),
        'breachWidth': P.float(0, 0, 120, unit='deg', doc='0 is an unbroken rim'),
        'surface': P.enum('eroded', ['smooth', 'eroded']),
        'erosion': P.float(0.3, 0, 1, doc='gully strength on the flanks (eroded surface only)'),
        'frequency': P.float(20, 1, 64, structural=True, periodFreq=True),
        'x': P.float(0.5, -1, 2), 'y': P.float(0.5, -1, 2),
        'seed': P.int(0, 0, 65535),
    }, apply=_volcano)

_RUGGED_STYLES = {'a': (0.5, 0.35), 'b': (0.6, 0.55), 'c': (0.42, 0.2), 'd': (0.55, 0.85), 'e': (0.5, 0.45)}


def _rugged(f, p, ctx):
    gain, warp = _RUGGED_STYLES[p.style]
    nf = max(2, js_round(p.frequency))
    rg = swiss_field(ctx, frequency=nf, octaves=p.octaves, gain=gain, warp=warp, offset=seed_offset(p.seed, nf))
    return field(H(f) + (rg.v - 0.5) * p.amount, G(f) + rg.g * p.amount, AUX(f))


OPS['rugged'] = dict(
    label='Rugged', category='terrain',
    doc='A strong rocky surface on any terrain, preserving the overall shape.',
    params={
        'style': P.enum('a', ['a', 'b', 'c', 'd', 'e']),
        'frequency': P.float(20, 2, 120, structural=True, periodFreq=True),
        'amount': P.float(0.08, 0, 0.4),
        'octaves': P.int(4, 1, 8),
        'seed': P.int(0, 0, 65535),
    }, apply=_rugged)


# --- utility -----------------------------------------------------------------------------------------------------

def _math(f, p, ctx):
    h, v = H(f), p.value
    op = p.operation
    if op == 'add':
        return remap(f, h + v, 1.0)
    if op == 'subtract':
        return remap(f, h - v, 1.0)
    if op == 'divide':
        d = nonzero(np.asarray(v, dtype=np.float64))
        return remap(f, h / d, 1.0 / d)
    if op == 'power':
        b = np.maximum(h, EPS)
        return remap(f, np.power(b, v), v * np.power(b, v - 1.0))
    if op == 'min':
        return remap(f, np.minimum(h, v), step01(h < v))
    if op == 'max':
        return remap(f, np.maximum(h, v), step01(h > v))
    if op == 'abs':
        return remap(f, np.abs(h), np.sign(h))
    if op == 'oneMinus':
        return remap(f, 1.0 - h, -1.0)
    if op == 'sqrt':
        b = np.maximum(h, EPS)
        return remap(f, np.sqrt(b), 0.5 / np.sqrt(b))
    if op == 'floor':
        q = nonzero(np.asarray(v, dtype=np.float64))
        return remap(f, np.floor(h * q) / q, 0.0)
    if op == 'fract':
        q = nonzero(np.asarray(v, dtype=np.float64))
        return remap(f, fract(h * q) / q, 1.0)
    return remap(f, h * v, v)


OPS['math'] = dict(
    label='Math', category='utility',
    doc='Applies one selected arithmetic operation to the height field.',
    params={
        'operation': P.enum('multiply', ['add', 'subtract', 'multiply', 'divide', 'power', 'min', 'max', 'abs',
                                         'oneMinus', 'sqrt', 'floor', 'fract']),
        'value': P.float(1, -8, 8),
    }, apply=_math)


def _route(f, p, ctx):
    got = (ctx.inputs or {}).get(f'in{p.choice}')
    return f if got is None else got


OPS['route'] = dict(
    label='Route', category='utility',
    doc='Routes one of four inputs through, chosen by an integer.',
    params={'choice': P.int(1, 1, 4)}, apply=_route)


def _switch(f, p, ctx):
    got = (ctx.inputs or {}).get('in2' if p.switchRoute else 'in')
    return f if got is None else got


OPS['switchOp'] = dict(
    label='Switch', category='utility',
    doc='Chooses between two inputs with a boolean.',
    params={'switchRoute': P.bool(False)}, apply=_switch)


def _compare(f, p, ctx):
    ins = ctx.inputs or {}
    a = ins.get('in', f)
    b = ins.get('in2', Vec(0.0, 0.0, 0.0, 0.0))
    first, second = (b, a) if p.swap else (a, b)
    t = ctx.tile.x if ctx.tile.x > 0 else 1.0
    u = fract((ctx.p.y if p.perpendicular else ctx.p.x) / t)
    return select(u < p.ab, first, second)


OPS['compare'] = dict(
    label='Compare', category='utility',
    doc='Splits the tile to show two inputs side by side — a review tool, not a blend.',
    params={
        'ab': P.float(0.5, 0, 1, doc='where the comparison split sits'),
        'perpendicular': P.bool(False),
        'swap': P.bool(False),
    }, apply=_compare)
