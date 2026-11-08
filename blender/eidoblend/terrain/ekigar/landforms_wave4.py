"""Landform library, wave 4 (src/core/landforms_wave4.js): aeolian, depositional, coastal and flow landforms.

Dune Field (barchan, transverse, barchanoid, linear, star, dome, parabolic), Alluvial Fan, Sandur, Delta, Spit &
Barrier, Reef Ring, Beach Cusps, Lava Field and Rock Glacier.
"""
from __future__ import annotations

import math

import numpy as np

from ._tsl import Vec, clamp, mix, select, step01, dot, length, normalize, fract, sat
from .noise import hash2, noised
from .phacelle import phacelle_noise
from .landform_shared import (P, TAU, EPS, H, G, field, sstep as smoothstep, wrapped_delta, sampled_add, noise,
                              ridged, scatter_cell, ring, fan_profile, axis_frame, asym_ridge, streamline,
                              snapped_axis, surface_detail, js_round)


def seed_shift_w4(seed=0):
    t = js_round(seed) & 0xFFFFFFFF
    return [((t * 1103515245 + 12345) & 0xFFFFFFFF) % 4096, ((t * 22695477 + 1) & 0xFFFFFFFF) % 4096]


def one_minus(v):
    return 1.0 - v


def mask(name, doc):
    return {'name': name, 'type': 'mask', 'doc': doc}


def direction(degrees):
    a = snapped_axis(degrees)
    n = math.hypot(a[0], a[1]) or 1.0
    return [a[0] / n, a[1] / n]


# ------------------------------------------------------------------------------------------------- dune field ---

def star_dune_apply(f, p, ctx):
    """Star dunes, analytic path: the cellular crest-network model with closed-form gradients."""
    q = ctx.p
    nS = max(1, js_round(p.frequency))
    wind = direction(p.windDir)
    wind_v = Vec(wind[0], wind[1])
    slip_rad = p.slipAngle * (math.pi / 180)
    stoss_rad = p.stossAngle * (math.pi / 180)
    slip_w = np.cos(slip_rad) / np.maximum(np.sin(slip_rad), EPS)
    stoss_w = np.cos(stoss_rad) / np.maximum(np.sin(stoss_rad), EPS)
    warp_amp = (p.sinuosity * 0.5 + 0.28) * (1 / nS)
    qw = (q + Vec(noise(q, nS, ctx, p.seed + 11), noise(q, nS, ctx, p.seed + 57)) * warp_amp * 0.72
          + Vec(noise(q, nS * 2, ctx, p.seed + 23), noise(q, nS * 2, ctx, p.seed + 71)) * warp_amp * 0.28
          + wind_v * noise(q, nS, ctx, p.seed + 3) * p.anisotropy * (0.55 / nS))
    lat = Vec(float(nS), float(nS))
    sp = qw * lat
    base = sp.floor()
    fr = sp.fract()
    perx, pery = ctx.tile.x * nS, ctx.tile.y * nS
    sx, sy = seed_shift_w4(p.seed)
    F1 = F2 = F3 = 9.0
    v1 = v2 = v3 = Vec(9.0, 9.0)
    for oy in (-1, 0, 1):
        for ox in (-1, 0, 1):
            ax_, ay_ = hash2(base.x + ox + sx, base.y + oy + sy, perx, pery)
            dv = Vec(ox + 0.5 + ax_ * p.jitter * 0.5 - fr.x, oy + 0.5 + ay_ * p.jitter * 0.5 - fr.y)
            d = length(dv)
            lt1, lt2, lt3 = d < F1, d < F2, d < F3
            nF3 = np.where(lt1, F2, np.where(lt2, F2, np.where(lt3, d, F3)))
            nV3 = select(lt1, v2, select(lt2, v2, select(lt3, dv, v3)))
            nF2 = np.where(lt1, F1, np.where(lt2, d, F2))
            nV2 = select(lt1, v1, select(lt2, dv, v2))
            v1 = select(lt1, dv, v1)
            F1 = np.minimum(F1, d)
            F2, v2, F3, v3 = nF2, nV2, nF3, nV3
    u1 = v1 / np.maximum(F1, EPS)
    gF1 = -(u1 * lat)
    gF2 = -(v2 / np.maximum(F2, EPS) * lat)
    gF3 = -(v3 / np.maximum(F3, EPS) * lat)
    m2 = F2 - F1
    lee_side = sat(dot(u1, wind_v) * 2.5 + 0.5)
    w_ratio = clamp(slip_w / np.maximum(stoss_w, EPS), 0.35, 1.0)
    w_crest = np.maximum(p.armWidth * 0.5 * mix(1.0, w_ratio, lee_side), EPS)
    a2 = np.abs(m2) / w_crest
    crest = np.exp(-np.power(np.maximum(a2, EPS), p.crestPower))
    g_crest = ((gF2 - gF1) * np.sign(m2) * crest
               * (-p.crestPower * np.power(np.maximum(a2, EPS), p.crestPower - 1.0)) / w_crest)
    m3 = F3 - F1
    w_node = np.maximum(p.armWidth * 0.7, EPS)
    a3 = m3 / w_node
    node_bump = np.exp(-(a3 * a3))
    g_node = (gF3 - gF1) * (a3 * -2.0 / w_node) * node_bump
    sum12 = np.maximum(F1 + F2, EPS)
    u = F1 * 2.0 / sum12
    gU = (gF1 * F2 - gF2 * F1) * 2.0 / (sum12 * sum12)
    dome = u * u * 0.16
    g_dome = gU * u * 0.32
    nW = noise(q, nS, ctx, p.seed + 131) * 0.5 + 0.5
    arm16 = np.maximum(p.armWidth * 1.6, EPS)
    a_prox = m3 / arm16
    node_prox = np.exp(-(a_prox * a_prox))
    g_node_prox = (gF3 - gF1) / arm16 * (a_prox * -2.0) * node_prox
    amp_wall = (nW * 0.7 + 0.3) * (node_prox * 0.55 + 0.45)
    crest_h = crest * amp_wall
    g_crest_h = g_crest * amp_wall + g_node_prox * 0.55 * crest * (nW * 0.7 + 0.3)
    body_raw = crest_h + node_bump * p.nodeBoost + dome
    g_body_raw = g_crest_h + g_node * p.nodeBoost + g_dome
    pad = p.basinLevel * 0.5
    body = pad + (1.0 - pad) * body_raw
    g_body = g_body_raw * (1.0 - pad)
    vsx, vsy = seed_shift_w4(p.seed + 191)
    nz0, nz1, nz2 = noised(q.x + vsx, q.y + vsy, ctx.tile.x, ctx.tile.y)
    vary_m = 1.0 - p.heightVary * 0.6 * (1.0 - (nz0 * 0.5 + 0.5))
    g_vary = Vec(nz1, nz2) * (p.heightVary * 0.3)
    total = body * p.height * vary_m
    g_tot = (g_body * vary_m + g_vary * body) * p.height
    axr = snapped_axis(p.windDir)
    pr = [-axr[1], axr[0]]
    B1 = [axr[0] * 3 + pr[0], axr[1] * 3 + pr[1]]
    B2 = [axr[0] * 3 - pr[0], axr[1] * 3 - pr[1]]
    k1 = max(1, js_round(46 / math.hypot(B1[0], B1[1])))
    k2 = max(1, js_round(46 / math.hypot(B2[0], B2[1])))
    wob = noise(q, nS * 2, ctx, p.seed + 77)
    qr = q + g_body * 0.0012
    x1 = qr.x * (B1[0] * k1) + qr.y * (B1[1] * k1) + wob * 0.9
    x2 = qr.x * (B2[0] * k2) + qr.y * (B2[1] * k2) + wob * 0.7
    f1 = fract(x1) - 0.5
    f2 = fract(x2) - 0.5
    t1 = np.abs(f1) * 2.0
    t2 = np.abs(f2) * 2.0
    s1 = t1 * t1 * (3.0 - t1 * 2.0)
    s2 = t2 * t2 * (3.0 - t2 * 2.0)
    w2 = nz0 * 0.5 + 0.5
    w1 = 1.0 - w2
    rip = 1.0 - (1.0 - s1 * w1) * (1.0 - s2 * w2)
    gs1 = Vec(float(B1[0] * k1), float(B1[1] * k1)) * np.sign(f1) * 2.0 * (t1 * 6.0 * (1.0 - t1))
    gs2 = Vec(float(B2[0] * k2), float(B2[1] * k2)) * np.sign(f2) * 2.0 * (t2 * 6.0 * (1.0 - t2))
    g_rip = gs1 * w1 * (1.0 - s2 * w2) + gs2 * w2 * (1.0 - s1 * w1)
    flat = sat(1.0 - crest * 1.8) * sat(1.0 - node_bump * 2.0)
    amp_r = p.height * 0.013 * flat
    total = total + (rip - 0.4) * amp_r
    g_tot = g_tot + g_rip * amp_r
    coverage = sat((crest + node_bump) * p.density * 1.6)
    return {'field': field(H(f) + total, G(f) + g_tot, coverage),
            'outs': {'slipFace': lee_side * smoothstep(0.2, 0.7, crest), 'stoss': coverage * (1.0 - lee_side),
                     'crest': smoothstep(0.5, 0.9, crest), 'interdune': 1.0 - coverage, 'horns': node_bump}}


def _dune_field(f, p, ctx):
    if p.type == 'star':
        return star_dune_apply(f, p, ctx)

    def features(q):
        frame = axis_frame(q, p.windDir, max(1, js_round(p.frequency)), p.sinuosity * 0.025, p.seed)
        cell = scatter_cell(q, p.frequency, ctx, p.seed, p.jitter)
        wind = direction(p.windDir)
        side = [-wind[1], wind[0]]
        along_cell = dot(cell.delta, Vec(wind[0], wind[1]))
        across_cell = dot(cell.delta, Vec(side[0], side[1]))
        slip_rad = p.slipAngle * (math.pi / 180)
        stoss_rad = p.stossAngle * (math.pi / 180)
        slip_width = np.cos(slip_rad) / np.maximum(np.sin(slip_rad), EPS) * (0.12 / 1.539865)
        stoss_width = np.cos(stoss_rad) / np.maximum(np.sin(stoss_rad), EPS) * (0.30 / 3.732051)
        section = -along_cell
        if p.type in ('transverse', 'barchanoid', 'linear'):
            crest_wobble = (np.sin(frame.across * (TAU * max(1, js_round(p.frequency / 2))) + p.seed * 0.37)
                            * p.sinuosity * 0.16)
            w = frame.w if p.type == 'linear' else fract(frame.along * p.frequency + crest_wobble) - 0.5
            section = w
            body = asym_ridge(w, steepWidth=slip_width, gentleWidth=slip_width if p.type == 'linear' else stoss_width,
                              steepPower=1.05, gentlePower=1.65)
        else:
            body = streamline(cell.delta, p.windDir, p.elongation, 0.55)
            if p.type == 'dome':
                body = np.power(sat(1.0 - cell.d * 1.7), 1.8)
            else:
                body = np.minimum(body * 1.15, asym_ridge(section, steepWidth=slip_width, gentleWidth=stoss_width,
                                                          steepPower=1.05, gentlePower=1.65))
        horns = 0.0
        if p.type in ('barchan', 'parabolic'):
            sign = -1 if p.type == 'parabolic' else 1
            scoop_r = length(Vec((along_cell - sign * 0.18) / 0.55, across_cell / 0.62))
            scoop = np.power(sat(1.0 - scoop_r), 1.5) * 0.72
            horn_rad = p.hornAngle * (math.pi / 180)
            reach = p.hornLength * 0.20 + 0.08
            enabled = smoothstep(0.0, 0.2, p.hornLength)

            def arm(side_sign):
                du = np.cos(horn_rad) * sign
                dv = np.sin(horn_rad) * side_sign
                centre_u = sign * 0.08 + du * reach * 0.48
                centre_v = side_sign * 0.27 + dv * reach * 0.48
                uu = along_cell - centre_u
                vv = across_cell - centre_v
                arm_along = uu * du + vv * dv
                arm_across = -(uu * dv) + vv * du
                rho = length(Vec(arm_along / np.maximum(reach * 0.58, 0.04), arm_across / 0.14))
                return np.power(sat(1.0 - rho), 1.45) * enabled

            horns = np.maximum(arm(1), arm(-1)) * 0.72
            body = np.maximum(body - scoop, horns)
        lee = sat(section * -8.0 + 0.5) * body
        coverage = sat(body * p.density * 1.35)
        crest = ring(body, 0.72, 0.18)
        return {'body': body, 'coverage': coverage, 'lee': lee, 'horns': horns, 'crest': crest}

    def shape(q):
        z = features(q)
        vary = scatter_cell(q, p.frequency, ctx, p.seed, p.jitter).random.x
        dunes = z['body'] * p.height * mix(1.0 - p.heightVary, 1.0, vary)
        mega = (asym_ridge(axis_frame(q, p.windDir, p.draaFreq, 0.05, p.seed + 31).w, steepWidth=0.16, gentleWidth=0.34)
                * p.height * p.draa * 1.6)
        return dunes + mega + surface_detail(q, ctx, p.seed + 71, 19, 2) * p.height * 0.045 * z['coverage']

    z = features(ctx.p)
    return {'field': sampled_add(f, ctx, shape, lambda q, h: z['coverage']),
            'outs': {'slipFace': z['lee'], 'stoss': z['coverage'] * (1.0 - z['lee']), 'crest': z['crest'] * z['coverage'],
                     'interdune': 1.0 - z['coverage'], 'horns': z['horns']}}


duneField = dict(
    label='Dune Field', category='terrain', optionalInput=True,
    doc='A hierarchy of wind-built dunes with distinct stoss, crest, slip-face, horn and interdune surfaces.',
    params={
        'type': P.enum('barchan', ['barchan', 'transverse', 'barchanoid', 'linear', 'star', 'dome', 'parabolic']),
        'windDir': P.float(0, 0, 360, structural=True, doc='resultant wind, snapped to a seamless lattice direction'),
        'frequency': P.float(5, 1, 64, structural=True, periodFreq=True),
        'height': P.float(0.10, 0, 0.5), 'heightVary': P.float(0.5, 0, 1),
        'slipAngle': P.float(33, 28, 36, unit='deg'), 'stossAngle': P.float(15, 5, 25, unit='deg'),
        'elongation': P.float(2.5, 1, 12), 'hornAngle': P.float(30, 5, 80, unit='deg'),
        'hornLength': P.float(1.4, 0, 4), 'arms': P.int(4, 3, 8),
        'armWidth': P.float(0.7, 0.1, 0.9, doc='star style: crest-ridge footprint, in basin-spacing units'),
        'nodeBoost': P.float(0.55, 0, 1, doc='star style: extra summit height where arms meet'),
        'basinLevel': P.float(0.15, 0, 0.8, doc='star style: sand-sheet floor of the interdune basins'),
        'crestPower': P.float(1.6, 1, 4, doc='star style: slope concentration toward the crestline'),
        'anisotropy': P.float(0.35, 0, 1, structural=True, doc='star style: stretches the basin lattice into corridors'),
        'draa': P.float(0, 0, 1), 'draaFreq': P.float(2, 1, 12, structural=True, periodFreq=True),
        'sinuosity': P.float(0.3, 0, 1), 'density': P.float(0.8, 0.05, 1),
        'jitter': P.float(0.7, 0, 1), 'seed': P.int(0, 0, 65535),
    },
    outputs=[mask('slipFace', 'loose lee face'), mask('stoss', 'packed windward face'),
             mask('crest', 'dune crests'), mask('interdune', 'low flats between dunes'),
             mask('horns', 'crescent arms')],
    apply=_dune_field)


# ---------------------------------------------------------------------------------------------- alluvial fan ---

def _alluvial_fan(f, p, ctx):
    axis = direction(p.axis)
    front = direction(p.frontDir)

    def features(q):
        fan = proximal = distal = active = trench = 0.0
        for i in range(int(p.count)):
            offset = 0.0 if p.count == 1 else (i / (p.count - 1) - 0.5) * 0.72
            centre = p.apex + Vec(front[0] * offset, front[1] * offset)
            d = wrapped_delta(q, centre, ctx.tile)
            r = length(d) / np.maximum(p.reach, EPS)
            align = dot(normalize(d + Vec(EPS, 0.0)), Vec(axis[0], axis[1]))
            edge = np.cos(p.halfAngle * (math.pi / 180))
            wedge = smoothstep(edge, np.minimum(1.0, edge + 0.12), align)
            cross = sat(1.0 - (1.0 - align) * p.crossConvex * 2.5)
            v = fan_profile(r, p.concavity) * wedge * cross
            fan = np.maximum(fan, v)
            proximal = np.maximum(proximal, v * sat(1.0 - r * 2.4))
            distal = np.maximum(distal, v * smoothstep(0.52, 0.92, r))
            lobe_wave = (np.sin(dot(d, Vec(-axis[1], axis[0])) / np.maximum(p.reach, EPS) * (p.lobes * TAU)
                                + p.seed * 0.13) * 0.5 + 0.5)
            active = np.maximum(active, v * smoothstep(0.55, 0.8, lobe_wave))
            centreline = np.abs(dot(normalize(d + Vec(EPS, 0.0)), Vec(-axis[1], axis[0])))
            angular_width = np.sin(p.trenchWidth * (math.pi / 180))
            trench_band = 1.0 - smoothstep(angular_width * 0.35, np.maximum(angular_width, 0.01), centreline)
            trench_length = 1.0 - smoothstep(p.trenchReach * 0.72, np.maximum(p.trenchReach, 0.01), r)
            trench = np.maximum(trench, v * trench_band * trench_length)
        return {'fan': fan, 'proximal': proximal, 'distal': distal, 'active': active, 'trench': trench}

    def shape(q):
        z = features(q)
        relief = z['fan'] * p.apexSlope * 0.012 * (1.0 - p.veneer * 0.72)
        lobe_relief = z['active'] * p.apexSlope * 0.0035 * (1.0 - p.veneer * 0.55)
        micro = surface_detail(q, ctx, p.seed + 19, 13, 3) * 0.010 * z['fan']
        return relief + lobe_relief + micro - z['trench'] * p.trench * p.apexSlope * 0.012

    z = features(ctx.p)
    return {'field': sampled_add(f, ctx, shape, lambda q, h: z['fan']),
            'outs': {'fan': z['fan'], 'proximal': z['proximal'], 'distal': z['distal'], 'lobe': z['active'],
                     'trench': z['trench']}}


alluvialFan = dict(
    label='Alluvial Fan', category='terrain', optionalInput=True,
    doc='One or more concave depositional aprons with proximal gravel, distal fines, lobes and fanhead trenches.',
    params={
        'count': P.int(1, 1, 24), 'apex': P.vec2([0.5, 0.82]),
        'frontDir': P.float(0, 0, 360, structural=True), 'axis': P.float(270, 0, 360, structural=True),
        'halfAngle': P.float(35, 5, 90, unit='deg'), 'reach': P.float(0.35, 0.02, 1.5),
        'apexSlope': P.float(8, 1.5, 25, unit='deg'), 'concavity': P.float(2.5, 0, 8),
        'crossConvex': P.float(0.3, 0, 1), 'lobes': P.int(2, 1, 6),
        'trench': P.float(0.15, 0, 1), 'trenchWidth': P.float(6, 1, 40, unit='deg'),
        'trenchReach': P.float(0.4, 0, 1), 'veneer': P.float(0, 0, 1), 'seed': P.int(0, 0, 65535),
    },
    outputs=[mask('fan', 'whole depositional apron'), mask('proximal', 'coarse apex deposits'),
             mask('distal', 'fine toe deposits'), mask('lobe', 'fresh active lobe'),
             mask('trench', 'fanhead incision')],
    apply=_alluvial_fan)


# ---------------------------------------------------------------------------------------------------- sandur ---

def _sandur(f, p, ctx):
    def features(q):
        d = wrapped_delta(q, p.apex, ctx.tile)
        r = length(d) / np.maximum(p.reach, EPS)
        apron = fan_profile(r, p.concavity)
        a = direction(p.axis)
        side = Vec(-a[1], a[0])
        along = dot(q, Vec(a[0], a[1]))
        across = dot(q, side)
        downstream = sat(r)
        fining_scale = 1.0 - downstream * p.fining * 0.65
        warp = noise(q, p.warpFreq, ctx, p.seed + 17) * p.warp * 3.5 + np.sin(along * (TAU * 3)) * p.warp
        channel = 0.0
        amp = 1.0
        freq = max(2, js_round(p.braidFreq))
        for i in range(int(p.braidOctaves)):
            n = np.abs(np.sin(across * (TAU * freq) + warp + i * 1.7))
            sorted_width = p.braidWidth * fining_scale
            b = np.power(sat(1.0 - n / np.maximum(sorted_width, 0.01)), p.braidPower) * amp
            channel = np.maximum(channel, b)
            amp *= 0.62
            freq *= 2
        channel = sat(channel) * apron
        isotropic = ridged(q, p.braidFreq, 2, ctx, p.seed + 300) * 0.5 + 0.5
        long_bars = np.cos(across * (TAU * max(2, js_round(p.braidFreq / 2))) + warp * 0.25) * 0.5 + 0.5
        elongation = sat((p.barElongate - 1.0) / 11)
        bar_pattern = mix(isotropic, long_bars, elongation)
        bar = apron * (1.0 - channel) * smoothstep(0.05, 0.4, bar_pattern) * fining_scale
        return {'apron': apron, 'channel': channel, 'bar': bar, 'island': bar * smoothstep(0.45, 0.78, bar)}

    def shape(q):
        z = features(q)
        return (z['apron'] * p.gradient * 0.0065 - z['channel'] * p.braidDepth * 3.0 + z['bar'] * p.barHeight * 2.6
                + surface_detail(q, ctx, p.seed + 9, 25, 2) * 0.0045 * z['apron'])

    z = features(ctx.p)
    return {'field': sampled_add(f, ctx, shape, lambda q, h: z['apron']), 'outs': z}


sandur = dict(
    label='Sandur', category='terrain', optionalInput=True,
    doc='A low-gradient outwash apron cut by multiscale braided channels and lens-shaped gravel bars.',
    params={
        'apex': P.vec2([0.5, 0.95]), 'axis': P.float(270, 0, 360, structural=True),
        'reach': P.float(0.8, 0.05, 2), 'gradient': P.float(1.2, 0.2, 6, unit='deg'),
        'concavity': P.float(1.2, 0, 6), 'braidFreq': P.float(20, 2, 128, structural=True, periodFreq=True),
        'braidOctaves': P.int(2, 1, 4), 'braidWidth': P.float(0.2, 0.02, 0.8),
        'braidDepth': P.float(0.012, 0, 0.1), 'braidPower': P.float(2, 1, 5),
        'warp': P.float(0.3, 0, 1), 'warpFreq': P.float(4, 1, 24, structural=True, periodFreq=True),
        'barHeight': P.float(0.008, 0, 0.06), 'barElongate': P.float(3, 1, 12),
        'fining': P.float(0.5, 0, 1), 'seed': P.int(0, 0, 65535),
    },
    outputs=[mask('channel', 'active wet braid'), mask('bar', 'dry sorted gravel bar'),
             mask('island', 'high stable bar'), mask('apron', 'outwash coverage')],
    apply=_sandur)


# ----------------------------------------------------------------------------------------------------- delta ---

def _delta(f, p, ctx):
    axis = direction(p.axis)

    def features(q):
        d = wrapped_delta(q, p.apex, ctx.tile)
        r = length(d) / np.maximum(p.reach, EPS)
        align = dot(normalize(d + Vec(EPS, 0.0)), Vec(axis[0], axis[1]))
        sector_edge = np.cos(p.spread * (math.pi / 360))
        wedge = smoothstep(sector_edge - 0.07, sector_edge + 0.04, align)
        plain = fan_profile(r, 0.8) * wedge
        channel = levee = mouth_bar = 0.0
        count = max(1, 2 ** int(p.bifurcations))
        for i in range(count):
            offset = (i + 0.5) / count - 0.5
            angle = (p.spread * offset + p.axis) * (math.pi / 180)
            ray = Vec(np.cos(angle), np.sin(angle))
            along = dot(d, ray)
            across = np.abs(d.x * ray.y - d.y * ray.x)
            wiggle = noise(q, 4 + (i % 3), ctx, p.seed + i * 31) * p.sinuosity * 0.018
            ribbon = (sat(1.0 - np.abs(across + wiggle) / np.maximum(p.channelWidth, 0.001))
                      * smoothstep(0.0, p.reach * 0.12, along) * sat(1.0 - r))
            channel = np.maximum(channel, ribbon)
            bank = (ring(across, p.channelWidth * 1.8, p.channelWidth * 0.8) * smoothstep(0.0, p.reach * 0.12, along)
                    * sat(1.0 - r))
            levee = np.maximum(levee, bank)
            mouth_bar = np.maximum(mouth_bar, ring(r, 0.78, 0.13) * ribbon)
        front = ring(r, 0.9, p.frontWidth * 1.35) * wedge
        front_taper = 1.0 - smoothstep(1.0 - p.frontWidth, 1.0, r)
        inter = plain * (1.0 - channel)
        splay_noise = smoothstep(0.45, 0.8, noise(q, max(2, p.splays + 2), ctx, p.seed + 911) * 0.5 + 0.5)
        splay = levee * splay_noise
        return {'plain': plain, 'channel': sat(channel), 'levee': sat(levee), 'interdistributary': inter,
                'front': front, 'mouthBar': sat(mouth_bar), 'splay': splay, 'frontTaper': front_taper}

    def shape(q):
        z = features(q)
        lobate = z['mouthBar'] * (1.0 - p.avulsion) * 0.018
        deposit = z['plain'] * z['frontTaper'] * p.frontDepth * 0.24 + z['plain'] * p.gradient * 0.006
        return (deposit - z['channel'] * p.channelDepth + z['levee'] * p.leveeHeight + lobate
                + z['splay'] * p.leveeHeight * 0.7 + surface_detail(q, ctx, p.seed + 61, 18, 2) * 0.006 * z['plain'])

    z = features(ctx.p)
    return {'field': sampled_add(f, ctx, shape, lambda q, h: z['plain']),
            'outs': {k: z[k] for k in ('channel', 'levee', 'interdistributary', 'front', 'mouthBar', 'splay')}}


delta = dict(
    label='Delta', category='terrain', optionalInput=True,
    doc='A low depositional plain with distributary channels, natural levees, mouth bars, splays and a foreset front.',
    params={
        'apex': P.vec2([0.5, 0.9]), 'axis': P.float(270, 0, 360, structural=True),
        'reach': P.float(0.55, 0.03, 1.2), 'spread': P.float(70, 10, 180, unit='deg'),
        'gradient': P.float(0.4, 0.05, 3, unit='deg'), 'bifurcations': P.int(3, 0, 5),
        'channelWidth': P.float(0.015, 0.002, 0.15), 'channelDepth': P.float(0.014, 0, 0.1),
        'leveeHeight': P.float(0.008, 0, 0.06), 'avulsion': P.float(0.5, 0, 1),
        'frontDepth': P.float(0.20, 0, 0.8), 'frontWidth': P.float(0.08, 0.01, 0.4),
        'splays': P.int(2, 0, 8), 'sinuosity': P.float(0.25, 0, 1), 'seed': P.int(0, 0, 65535),
    },
    outputs=[mask('channel', 'active distributaries'), mask('levee', 'raised dry banks'),
             mask('interdistributary', 'wet ground between channels'), mask('front', 'subaqueous foreset slope'),
             mask('mouthBar', 'deposition at channel mouths'), mask('splay', 'crevasse splays')],
    apply=_delta)


# -------------------------------------------------------------------------------------------- spit & barrier ---

def _spit_bar(f, p, ctx):
    a = direction(p.driftDir)
    side = [-a[1], a[0]]

    def features(q):
        d = wrapped_delta(q, p.anchor, ctx.tile)
        if p.mode == 'barrier':
            d = d - Vec(side[0], side[1]) * p.standoff
        along = dot(d, Vec(a[0], a[1]))
        progress = sat(along / np.maximum(p.length, EPS))
        local_width = p.barWidth * mix(1.0, 0.38, progress * p.taper)
        seeded_bend = noise(q, 7, ctx, p.seed + 37) * p.barWidth * (p.sinuosity * 0.55 + 0.08)
        curve = (progress * progress * progress * p.recurve * p.barWidth * 5.0
                 + np.sin(progress * (math.pi * 1.25)) * p.sinuosity * p.barWidth + seeded_bend)
        across = dot(d, Vec(side[0], side[1])) - curve
        extent = smoothstep(0.0, local_width, along) * (1.0 - smoothstep(p.length - local_width, p.length, along))
        bar = asym_ridge(across, steepWidth=local_width * p.seawardSlope, gentleWidth=local_width, steepPower=1.1,
                         gentlePower=1.8) * extent
        if p.mode == 'cuspate':
            d2 = wrapped_delta(q, p.anchor2, ctx.tile)
            along2 = dot(d2, Vec(-a[0], -a[1]))
            cross2 = dot(d2, Vec(side[0], side[1])) + sat(along2 / np.maximum(p.length, EPS)) * p.recurve * p.barWidth
            bar = np.maximum(bar, asym_ridge(cross2, steepWidth=p.barWidth * 0.4, gentleWidth=p.barWidth)
                             * smoothstep(0.0, p.barWidth, along2)
                             * (1.0 - smoothstep(p.length - p.barWidth, p.length, along2)))
        lagoon = sat(1.0 - np.abs(across + local_width * 1.7) / (local_width * 2.8)) * extent * (1.0 - bar)
        tip = bar * smoothstep(0.72, 1.0, progress)
        beach = bar * sat(-across / np.maximum(local_width, EPS))
        dune = ring(np.abs(across), 0.0, local_width * 0.22) * bar * p.duneCrest
        return {'bar': sat(bar), 'lagoon': lagoon, 'tip': tip, 'beachFace': beach, 'dune': dune,
                'marsh': lagoon * ring(lagoon, 0.35, 0.28)}

    def shape(q):
        z = features(q)
        lower_to_lagoon = np.minimum(p.lagoonLevel - H(f), 0.0) - p.lagoonDepth
        return (z['bar'] * p.barHeight + z['dune'] * p.barHeight * 0.45 + z['lagoon'] * lower_to_lagoon
                + surface_detail(q, ctx, p.seed + 8, 27, 2) * 0.002 * z['bar'])

    z = features(ctx.p)
    return {'field': sampled_add(f, ctx, shape, lambda q, h: z['bar']), 'outs': z}


spitBar = dict(
    label='Spit & Barrier', category='terrain', optionalInput=True,
    doc='A drift-built beach ridge with attachment modes, recurved active tip, back-barrier lagoon, marsh and crest '
        'dunes.',
    params={
        'mode': P.enum('spit', ['spit', 'baymouth', 'tombolo', 'barrier', 'cuspate']),
        'driftDir': P.float(0, 0, 360, structural=True), 'anchor': P.vec2([0.25, 0.55]),
        'anchor2': P.vec2([0.75, 0.55]), 'length': P.float(0.42, 0.05, 1.5),
        'barWidth': P.float(0.04, 0.004, 0.3), 'barHeight': P.float(0.08, 0, 0.3),
        'seawardSlope': P.float(0.35, 0.05, 1), 'recurve': P.float(1.4, 0, 2),
        'taper': P.float(0.4, 0, 1), 'standoff': P.float(0.12, 0, 0.5),
        'lagoonLevel': P.float(0.28, -1, 2), 'lagoonDepth': P.float(0.03, 0, 0.3),
        'duneCrest': P.float(0.3, 0, 1), 'sinuosity': P.float(0.15, 0, 1), 'seed': P.int(0, 0, 65535),
    },
    outputs=[mask('bar', 'beach ridge'), mask('beachFace', 'steep seaward sand face'),
             mask('lagoon', 'enclosed back-barrier floor'), mask('marsh', 'sheltered marginal flat'),
             mask('dune', 'crest dune ridge'), mask('tip', 'active recurved distal end')],
    apply=_spit_bar)


# ------------------------------------------------------------------------------------------------- reef ring ---

def _reef_ring(f, p, ctx):
    def features(q):
        d = wrapped_delta(q, p.centre, ctx.tile)
        chaos = noise(q, 7, ctx, p.seed) * p.outlineChaos * p.reefWidth * 0.35
        r = length(d)
        rr = r + chaos
        reef = ring(rr, p.reefRadius, p.reefWidth)
        pass_ = 0.0
        for i in range(int(p.passes)):
            a = i * TAU / max(1, p.passes) + p.seed * 0.013
            alignment = dot(normalize(d + Vec(EPS, 0.0)), Vec(math.cos(a), math.sin(a)))
            edge = np.cos(p.passWidth * (math.pi / 360))
            pass_ = np.maximum(pass_, smoothstep(edge - 0.025, edge + 0.025, alignment))
        reef_active = 0.0 if p.guyot else 1.0
        flat_half = p.reefWidth * (p.flatWidth * 0.60 + 0.12)
        flat = ring(rr, p.reefRadius, np.maximum(flat_half, 0.002)) * (1.0 - pass_) * reef_active
        lagoon = sat(1.0 - rr / np.maximum(p.reefRadius - p.reefWidth, EPS)) * reef_active
        fore_run = sat(1.0 - np.maximum(rr - p.reefRadius, 0.0) / np.maximum(p.reefWidth * 2.5, EPS))
        fore_power = 0.65 + sat((p.foreSlope - 5.0) / 75) * 2.55
        outside = step01(rr > p.reefRadius)
        fore = np.power(np.maximum(fore_run, EPS), fore_power) * outside * (1.0 - pass_) * reef_active
        motu_pattern = smoothstep(0.62, 0.83, noise(q, max(2, p.motu), ctx, p.seed + 404) * 0.5 + 0.5)
        motu = flat * motu_pattern
        edifice_profile = sat(1.0 - r / np.maximum(p.edificeRadius, EPS))
        cone = edifice_profile * p.edificeHeight * (1.0 - p.subsidence)
        lagoon_floor = lagoon * (p.seaLevel - p.lagoonDepth)
        reef_top = np.maximum(flat, fore) * (p.seaLevel + p.motuHeight * 0.15)
        edifice = np.minimum(cone, p.seaLevel - p.lagoonDepth) if p.guyot else cone
        terrain = (np.maximum(edifice, np.maximum(lagoon_floor, reef_top)) + motu * p.motuHeight
                   + surface_detail(q, ctx, p.seed + 77, 24, 2) * 0.0018 * fore)
        footprint = sat(np.maximum(edifice_profile, np.maximum(lagoon, np.maximum(reef, fore))))
        depth_feather = np.maximum(p.lagoonDepth * 0.35, 0.002)
        submerged = sat(footprint * smoothstep(0.0, depth_feather, p.seaLevel - terrain))
        return {'reefFlat': flat, 'lagoon': lagoon, 'motu': motu, 'foreReef': fore,
                'pass': pass_ * reef * reef_active, 'submerged': submerged, 'terrain': terrain}

    z = features(ctx.p)
    return {'field': sampled_add(f, ctx, lambda q: features(q)['terrain'],
                                 lambda q, h: np.maximum(z['reefFlat'], z['lagoon'])),
            'outs': {k: z[k] for k in ('reefFlat', 'lagoon', 'motu', 'foreReef', 'pass', 'submerged')}}


reefRing = dict(
    label='Reef Ring', category='terrain', optionalInput=True,
    doc='A subsidence sequence from fringing reef to barrier reef and atoll, with reef flat, lagoon, motu and passes.',
    params={
        'centre': P.vec2([0.5, 0.5]), 'edificeRadius': P.float(0.3, 0.03, 1),
        'edificeHeight': P.float(0.5, 0, 2), 'subsidence': P.float(1, 0, 1), 'seaLevel': P.float(0.4, -1, 2),
        'reefRadius': P.float(0.28, 0.02, 1), 'reefWidth': P.float(0.05, 0.004, 0.3),
        'flatWidth': P.float(0.6, 0, 1), 'lagoonDepth': P.float(0.04, 0, 0.3),
        'motu': P.int(6, 0, 40), 'motuHeight': P.float(0.01, 0, 0.06),
        'passes': P.int(2, 0, 8), 'passWidth': P.float(12, 2, 60, unit='deg'),
        'foreSlope': P.float(35, 5, 80, unit='deg'), 'guyot': P.bool(False),
        'outlineChaos': P.float(0.3, 0, 1), 'seed': P.int(0, 0, 65535),
    },
    outputs=[mask('reefFlat', 'wave-washed reef crest'), mask('lagoon', 'enclosed shallow basin'),
             mask('motu', 'islets on the flat'), mask('foreReef', 'steep living outer face'),
             mask('pass', 'gaps through the rim'), mask('submerged', 'edifice below sea level')],
    apply=_reef_ring)


# ---------------------------------------------------------------------------------------------- beach cusps ---

def _beach_cusps(f0, p, ctx):
    dd = wrapped_delta(ctx.p, Vec(0.5, 0.5), ctx.tile)
    rr = length(dd) * 2.2
    rc = clamp(rr, 0.0, 1.0)
    dome_v = (np.cos(rc * math.pi) * 0.5 + 0.5) * 0.62 * p.baseShore
    inside_d = step01(rr < 1)
    ddir = dd / np.maximum(length(dd), 1e-6)
    dome_g = ddir * (np.sin(rc * math.pi) * (-math.pi / 2 * 0.62 * 2.2)) * p.baseShore * inside_d
    f = field(H(f0) + dome_v, G(f0) + dome_g, f0.w)
    slope = np.maximum(length(G(f)), 0.002)
    normal_distance = (H(f) - p.waterLine) / slope
    swash = sat(1.0 - np.abs(normal_distance) / np.maximum(p.reach, EPS))
    cells = max(1, js_round(p.worldSize / max(0.5, p.wavelength)))
    gdir = G(f) / slope
    per_c = (ctx.tile.x * cells, ctx.tile.y * cells)

    def ph_c(q):
        return phacelle_noise(q * cells, gdir, 1.0, float(p.seed % 7 * 0.13), 1.0 - p.regularity * 0.7, per_c)

    wave = ph_c(ctx.p).x * 0.5 + 0.5
    horn = np.power(np.maximum(wave, EPS), p.hornSharp) * swash
    embayment = swash * (1.0 - horn)

    def shape(q):
        hq = np.power(np.maximum(ph_c(q).x * 0.5 + 0.5, EPS), p.hornSharp)
        embay_depth = p.crescent * 1.05 + 0.35
        return (hq - (1.0 - hq) * embay_depth) * p.amplitude * 6.0 * swash

    return {'field': sampled_add(f, ctx, shape, lambda q, h: swash),
            'outs': {'horn': horn, 'embayment': embayment, 'swash': swash}}


beachCusps = dict(
    label='Beach Cusps', category='terrain', optionalInput=True, visualFixture='coast',
    doc='Regular crescentic horns and embayments that follow an incoming water-line contour.',
    params={
        'waterLine': P.float(0.2, -1, 2, doc='height of the sea; the standalone island tops out near 0.31'),
        'wavelength': P.float(20, 0.5, 80, unit='m', structural=True),
        'worldSize': P.float(400, 10, 8000, unit='m', structural=True), 'amplitude': P.float(0.022, 0, 0.08),
        'reach': P.float(0.07, 0.002, 0.15), 'hornSharp': P.float(2, 0.5, 6),
        'crescent': P.float(0.35, 0, 0.6), 'regularity': P.float(0.8, 0, 1),
        'baseShore': P.float(0.5, 0, 1, doc='standalone island base the cusps ring; set 0 when a wired terrain '
                                           'supplies the shoreline'),
        'seed': P.int(0, 0, 65535),
    },
    outputs=[mask('horn', 'coarse cusp horn'), mask('embayment', 'fine sand between horns'),
             mask('swash', 'wetted contour band')],
    apply=_beach_cusps)


# ----------------------------------------------------------------------------------------------- lava field ---

def _lava_field(f, p, ctx):
    n = max(1, js_round(p.frequency))
    sxx, syy = seed_shift_w4(p.seed)

    def features(q):
        sp2 = q * n
        base = sp2.floor()
        fr = sp2.fract()
        perx, pery = ctx.tile.x * n, ctx.tile.y * n
        gmag = length(G(f))
        gdir = select(gmag > 0.02, -G(f) / np.maximum(gmag, EPS),
                      Vec(math.cos(p.seed * 0.7 + 1.1), math.sin(p.seed * 0.7 + 1.1)))
        h = flow_m = levee_m = chan_m = toe_m = 0.0
        density = min(1.0, p.vents / max(1, n * n))
        for oy in (-1, 0, 1):
            for ox in (-1, 0, 1):
                cx = base.x + ox
                cy = base.y + oy
                a = Vec(*hash2(cx + sxx, cy + syy, perx, pery))
                b = Vec(*hash2(cx + (sxx + 733), cy + (syy + 197), perx, pery))
                active = np.where(a.x * 0.5 + 0.5 < density, 1.0, 0.0)
                vent = Vec(ox + 0.5 + a.x * 0.42 - fr.x, oy + 0.5 + a.y * 0.42 - fr.y)
                dvec = vent / n
                L = p.reach * mix(1.0 - p.reachVary * 0.7, 1.3, b.x * 0.5 + 0.5)
                for t2 in (0, 1):
                    az0 = 0.9 if t2 == 0 else 3.7
                    azr = (a.y if t2 == 0 else b.y) * 2.6 + az0
                    own = Vec(np.cos(azr), np.sin(azr))
                    bdir0 = own * (1.0 - p.downhillBias) + gdir * p.downhillBias
                    bl = np.maximum(length(bdir0), EPS)
                    bdir = bdir0 / bl
                    bperp = Vec(-bdir.y, bdir.x)
                    sA = dvec.x * bdir.x + dvec.y * bdir.y
                    sN = sA / np.maximum(L, EPS)
                    tP = dvec.x * bperp.x + dvec.y * bperp.y + np.sin(sN * 5.2 + b.y * 7.0) * L * 0.06
                    w_half = L * (0.16 + sN * 0.24) * (1.0 + np.sin(sN * 9.0 + a.x * 9.0) * 0.16)
                    in_s = smoothstep(0.0, L * 0.1, sA) * one_minus(smoothstep(L * 0.94, L, sA))
                    across = np.abs(tP) / np.maximum(w_half, EPS)
                    in_t = one_minus(smoothstep(1.0 - p.toeWidth * 8.0, 1.0, across))
                    m = in_s * in_t * active
                    levee = smoothstep(0.62, 0.82, across) * one_minus(smoothstep(0.9, 1.0, across))
                    chan = one_minus(smoothstep(0.0, 0.34, across)) * one_minus(smoothstep(0.45, 0.8, sN))
                    ridges = ((np.cos(sN * (L / np.maximum(p.ridgeSpacing, 0.004)) + a.y * 5.0) * 0.5 + 0.5)
                              * smoothstep(0.3, 0.7, sN))
                    slab = p.thickness * m * (1.0 + levee * p.leveeHeight * 0.6 - chan * p.channelDepth * 0.5
                                              + ridges * p.ridgeAmp * 0.25)
                    h = np.maximum(h, slab)
                    flow_m = np.maximum(flow_m, m)
                    levee_m = np.maximum(levee_m, levee * m)
                    chan_m = np.maximum(chan_m, chan * m)
                    toe_m = np.maximum(toe_m, smoothstep(0.85, 0.97, across) * m)
        kip = smoothstep(0.7, 0.86, noise(q, 7, ctx, p.seed + 133) * 0.5 + 0.5)
        inund = flow_m * one_minus(kip)
        h = h * one_minus(kip * 0.9)
        rg = ridged(q, p.blockFreq, 2, ctx, p.seed + 81)
        clink = rg * p.blockiness * p.thickness * 0.14 * inund
        return {'h': h + clink, 'flow': inund, 'kipuka': kip * flow_m, 'levee': levee_m, 'channel': chan_m,
                'toe': toe_m, 'blocky': smoothstep(0.5, 0.8, rg * 0.5 + 0.5) * inund}

    z = features(ctx.p)
    out = sampled_add(f, ctx, lambda q: features(q)['h'], lambda q, h: z['flow'])
    return {'field': out, 'outs': {k: z[k] for k in ('flow', 'kipuka', 'levee', 'channel', 'toe', 'blocky')}}


lavaField = dict(
    label='Lava Field', category='terrain', optionalInput=False, visualFixture='slope',
    doc='Overlapping lobed lava tongues from scattered vents: abrupt toes, levees around drained axial channels, '
        'transverse pressure ridges, clinker, and kipuka islands. Built from the SP Crater reference study.',
    params={
        'vents': P.int(3, 1, 24), 'frequency': P.float(4, 1, 24, structural=True, periodFreq=True),
        'reach': P.float(0.3, 0.02, 1.2), 'reachVary': P.float(0.5, 0, 1),
        'thickness': P.float(0.09, 0.002, 0.3), 'downhillBias': P.float(0.7, 0, 1),
        'toeWidth': P.float(0.05, 0.002, 0.15), 'leveeHeight': P.float(0.35, 0, 1),
        'channelDepth': P.float(0.25, 0, 1), 'ridgeAmp': P.float(0.2, 0, 1),
        'ridgeSpacing': P.float(0.05, 0.004, 0.2), 'blockiness': P.float(0.4, 0, 1),
        'blockFreq': P.float(60, 8, 300, structural=True, periodFreq=True), 'seed': P.int(0, 0, 65535),
    },
    outputs=[mask('flow', 'fresh lava sheet'), mask('kipuka', 'older ground isolated by lava'),
             mask('levee', 'raised flow margin'), mask('channel', 'drained flow centre'),
             mask('toe', 'rubbly flow front'), mask('blocky', 'rough clinker surface')],
    apply=_lava_field)


# --------------------------------------------------------------------------------------------- rock glacier ---

def _rock_glacier(f, p, ctx):
    a = direction(p.flowDir)
    stated = Vec(a[0], a[1])
    downhill = normalize(-G(f) + Vec(EPS, 0.0))
    flow_axis = normalize(mix(stated, downhill, p.downhillBias))
    flow_side = Vec(-flow_axis.y, flow_axis.x)

    def features(q):
        d = wrapped_delta(q, p.head, ctx.tile)
        if p.count > 1:
            c = scatter_cell(q, p.frequency, ctx, p.seed, 0.7)
            d = c.delta / p.frequency
            density = min(1.0, p.count / max(1, p.frequency * p.frequency))
            active = np.where(c.random.w < density, 1.0, 0.0)
            d = mix(Vec(8.0, 8.0), d, active)
        along = dot(d, flow_axis)
        across = dot(d, flow_side)
        s = along / np.maximum(p.length, EPS)
        w = across / np.maximum(p.width, EPS)
        angle = p.frontAngle * (math.pi / 180)
        front_run = clamp((p.thickness * np.cos(angle) / np.maximum(np.sin(angle), 0.01) + p.frontWidth)
                          / np.maximum(p.length, EPS), 0.04, 0.55)
        front_start = 1.0 - front_run
        tongue = np.power(sat(1.0 - w * w) * smoothstep(0.0, 0.08, s) * (1.0 - smoothstep(front_start, 1.0, s)), 1.25)
        phase = s / np.maximum(p.ridgeSpacing, 0.004) * TAU + w * w * 2.5
        wave = np.cos(phase) * 0.5 + 0.5
        ridges = np.power(np.maximum(wave, EPS), p.ridgeSharp) * tongue
        furrows = np.power(np.maximum(1.0 - wave, EPS), p.ridgeSharp) * tongue
        front = ring(s, 1.0 - front_run * 0.48, np.maximum(front_run * 0.48, 0.02)) * tongue
        head = sat(1.0 - length(Vec(s, w)) * 3.5)
        return {'tongue': tongue, 'ridges': ridges, 'furrows': furrows, 'front': front, 'head': head}

    def shape(q):
        z = features(q)
        lobe = np.sin(dot(q, flow_side) * (p.lobes * TAU)) * 0.5 + 0.5
        blocks = ridged(q, p.blockFreq, 2, ctx, p.seed + 77) * p.blockAmp * 0.12
        return (z['tongue'] * p.thickness * mix(0.78, 1.08, lobe) + z['ridges'] * p.ridgeAmp * p.thickness
                + blocks * p.thickness * z['tongue'])

    z = features(ctx.p)
    return {'field': sampled_add(f, ctx, shape, lambda q, h: z['tongue']), 'outs': z}


rockGlacier = dict(
    label='Rock Glacier', category='terrain', optionalInput=True,
    doc='Blocky lobate debris tongues with steep snouts and diagnostic transverse arcuate ridges and furrows.',
    params={
        'count': P.int(1, 1, 16), 'head': P.vec2([0.5, 0.8]),
        'frequency': P.float(5, 1, 24, structural=True, periodFreq=True),
        'flowDir': P.float(270, 0, 360, structural=True), 'length': P.float(0.45, 0.01, 1),
        'width': P.float(0.20, 0.005, 0.5), 'thickness': P.float(0.12, 0.002, 0.3),
        'frontAngle': P.float(37, 25, 45, unit='deg'), 'frontWidth': P.float(0.02, 0.002, 0.1),
        'lobes': P.int(2, 1, 6), 'ridgeAmp': P.float(0.25, 0, 1),
        'ridgeSpacing': P.float(0.04, 0.005, 0.3), 'ridgeSharp': P.float(1.5, 0.5, 5),
        'downhillBias': P.float(0.6, 0, 1), 'blockAmp': P.float(0.3, 0, 1),
        'blockFreq': P.float(70, 8, 300, structural=True, periodFreq=True), 'seed': P.int(0, 0, 65535),
    },
    outputs=[mask('tongue', 'blocky debris body'), mask('ridges', 'arcuate transverse ridges'),
             mask('furrows', 'snow-holding furrows'), mask('front', 'steep unstable snout'),
             mask('head', 'talus source area')],
    apply=_rock_glacier)


WAVE4_LANDFORMS = {
    'duneField': duneField,
    'alluvialFan': alluvialFan,
    'sandur': sandur,
    'delta': delta,
    'spitBar': spitBar,
    'reefRing': reefRing,
    'beachCusps': beachCusps,
    'lavaField': lavaField,
    'rockGlacier': rockGlacier,
}
