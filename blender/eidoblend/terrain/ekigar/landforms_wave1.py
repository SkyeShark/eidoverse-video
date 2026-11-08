"""Landform library, wave 1 (src/core/landforms_wave1.js): radial basins, rims, cones and erosional remnants.

Caldera, Impact Crater, Cinder Cone Field, Maar, Cirque Field, Basin Field, Mound Field, Volcanic Plug, Lava Dome and
Mesa. Each layers relief onto its incoming field (or stands alone), carries its gradient through sampled_add's
central differences, and emits named coverage masks.
"""
from __future__ import annotations

import math
import re

import numpy as np

from ._tsl import Vec, mix, step01, dot, length, normalize, sat
from .noise import noised, hash2
from .landform_shared import (P, EPS, TAU, sstep as smoothstep, sampled_add, wrapped_delta, scatter_cell, ring,
                              fan_profile, bench_stack, surface_detail, seed_shift, fbm, js_round, js_mod)


def mask_outputs(*names):
    out = []
    for n in names:
        words = re.sub(r'([A-Z])', r' \1', n).lower()
        out.append({'name': n, 'type': 'mask', 'doc': words + ' coverage produced by this landform'})
    return out


def gate(cond):
    return step01(cond)


def one_minus(v):
    return 1.0 - v


def direction_vector(degrees=0):
    a = float(degrees or 0) * math.pi / 180.0
    return Vec(math.cos(a), math.sin(a))


def snapped_axis_name(degrees=0):
    """wave1's own snappedAxis: the nearest of x / diag / y / anti, by 45-degree steps."""
    a = js_mod(js_mod(float(degrees or 0), 360) + 360, 360)
    return ['x', 'diag', 'y', 'anti'][js_round(a / 45) % 4]


def angular_gate(d, degrees, width_degrees, softness=0.035):
    n = normalize(d + Vec(EPS, 0.0))
    threshold = np.cos(width_degrees * (math.pi / 360))
    angular = smoothstep(threshold - softness, threshold + softness, dot(n, direction_vector(degrees)))
    return angular * smoothstep(0.0, 0.5, width_degrees)


def angular_gate_axis(d, axis, width_degrees, softness=0.035):
    threshold = np.cos(width_degrees * (math.pi / 360))
    return (smoothstep(threshold - softness, threshold + softness,
                       dot(normalize(d + Vec(EPS, 0.0)), normalize(axis + Vec(EPS, 0.0))))
            * smoothstep(0.0, 0.5, width_degrees))


def ellipse_radius(d, axis, elongation):
    side = Vec(-axis.y, axis.x)
    return length(Vec(dot(d, axis) / np.maximum(elongation, EPS), dot(d, side)))


def varied(base, amount, random, low=0.55, high=1.45):
    return base * mix(1.0 - amount * (1 - low), 1.0 + amount * (high - 1), random)


def angular_wobble(d, scale, seed=0):
    """Angular irregularity: noise on the direction circle, constant along each ray, periodic around it. Multiplying
    r by this breaks every circle downstream at once (the lathe look)."""
    dirv = d / np.maximum(length(d), EPS)
    sx = js_mod(seed * 37, 101)
    return noised(dirv.x * scale + sx, dirv.y * scale, 4096.0, 4096.0)[0]


def centred(q, ctx, centre, radius):
    d = wrapped_delta(q, centre, ctx.tile)
    return {'d': d, 'r': length(d) / np.maximum(radius, EPS), 'random': Vec(0.5, 0.5, 0.5, 0.5)}


def scattered(q, ctx, frequency, seed, jitter=0.86):
    c = scatter_cell(q, frequency, ctx, seed, jitter)
    return {'d': c.delta / c.cells, 'random': c.random, 'cells': c.cells}


def counted_placement(q, ctx, count, frequency, seed, centre=None):
    if count == 1:
        r = centred(q, ctx, centre if centre is not None else Vec(0.5, 0.5), 1.0)
        r['active'] = 1.0
        return r
    s = scattered(q, ctx, frequency, seed)
    density = min(1.0, max(1, count) / max(1, js_round(frequency) ** 2))
    s['active'] = gate(s['random'].x < density)
    return s


def radial_rays(d, count, seed, sharpness=28):
    if count <= 0:
        return 0.0
    n = normalize(d + Vec(EPS, 0.0))
    phase = js_mod(seed * 0.61803398875, 1) * TAU
    rays = 0.0
    for i in range(int(count)):
        a = phase + TAU * i / count
        rays = np.maximum(rays, np.power(np.maximum(dot(n, Vec(math.cos(a), math.sin(a))), 0.0), sharpness))
    return rays


def emit(f, p, ctx, build):
    centre = build(ctx.p, p, ctx)
    return {'field': sampled_add(f, ctx, lambda q: build(q, p, ctx)['height']), 'outs': centre['outs']}


def _seed(p):
    return 0 if p.seed is None else p.seed


# --------------------------------------------------------------------------------------------------- caldera ---

def caldera_shape(q, p, ctx):
    d = wrapped_delta(q, p.centre, ctx.tile)
    cwob = angular_wobble(d, 2.1, _seed(p))
    r = length(d) / np.maximum(p.radius, EPS) * (1.0 + cwob * 0.10)
    outside = np.maximum(r - 1.0, 0.0)
    shield_out = p.shieldHeight * np.exp(-(outside * p.shieldDecay)) * one_minus(smoothstep(2.4, 3.2, r))
    floor_z = p.shieldHeight - p.depth
    wall_span = one_minus(p.floorRadius) * p.wallFraction
    wall_coord = sat((r - p.floorRadius) / np.maximum(wall_span, EPS))
    smooth_wall = smoothstep(0.0, 1.0, wall_coord)
    bwob = angular_wobble(d, 4.7, _seed(p) + 23)
    benches = (bench_stack(sat(wall_coord + bwob * 0.25 / max(1, p.terraces)), p.terraces, 0.7)
               if p.terraces > 0 else None)
    wall_rise = mix(smooth_wall, benches.value, 0.4) if benches else smooth_wall
    rim_top = p.shieldHeight + p.rimHeight * 0.3
    interior = floor_z + (rim_top - floor_z) * wall_rise
    gap = angular_gate(d, p.breachDir, p.breachWidth)
    sB = smoothstep(0.97, 1.08, r)
    in_blend = sB + gap * one_minus(sB)
    basin = mix(interior, shield_out, in_blend)
    floor_mask = one_minus(smoothstep(p.floorRadius - 0.025, p.floorRadius + 0.025, r))
    wall_mask = smoothstep(0.02, 0.18, wall_coord) * one_minus(smoothstep(0.78, 1.02, wall_coord))
    terrace_mask = benches.tread * wall_mask if benches else 0.0
    rim_mask = ring(r, 1.0, 0.065) * one_minus(gap)
    dr = r / np.maximum(p.domeRadius, EPS)
    dome_mask = np.power(sat(one_minus(dr * dr)), 0.55) * smoothstep(0.0, 0.002, p.domeRadius)
    cone_mask = np.power(sat(one_minus(r / np.maximum(p.coneRadius, EPS))), 1.4) * smoothstep(0.0, 0.002, p.coneHeight)
    detail_gate = (wall_mask * (p.depth * 0.12) + smoothstep(0.72, 0.98, r) * (p.shieldHeight * 0.035)
                   + dome_mask * (p.domeHeight * 0.025))
    detail = surface_detail(q, ctx, 101, 9, 4) * detail_gate
    mtn = fbm(q, 5, 3, ctx, _seed(p) + 177) * 0.5 + 0.5
    basin_tex = basin * (mtn * 0.3 + 0.7)
    return {'height': basin_tex + p.domeHeight * dome_mask + p.coneHeight * cone_mask + detail,
            'outs': {'floor': sat(floor_mask), 'wall': sat(wall_mask), 'terrace': sat(terrace_mask),
                     'rim': sat(rim_mask), 'dome': sat(dome_mask), 'breach': sat(gap * ring(r, 1.0, 0.18))}}


caldera = dict(
    label='Caldera', category='terrain', optionalInput=True,
    doc='Terraced collapse basin with a flat floor, ring fault, shield, breach and optional resurgence.',
    params={
        'centre': P.vec2([0.5, 0.5]), 'radius': P.float(0.3, 0.02, 0.9),
        'depth': P.float(0.24, 0, 0.6),
        'floorRadius': P.float(0.62, 0.05, 0.95, doc='flat floor as a fraction of rim radius'),
        'wallFraction': P.float(0.8, 0.1, 1, doc='lower values leave a collapse bench'),
        'terraces': P.int(3, 0, 8), 'rimHeight': P.float(0.35, 0, 2),
        'shieldHeight': P.float(0.3, 0, 1.5), 'shieldDecay': P.float(2.2, 0.5, 8),
        'domeRadius': P.float(0, 0, 0.8), 'domeHeight': P.float(0.35, 0, 1),
        'coneHeight': P.float(0, 0, 1), 'coneRadius': P.float(0.4, 0.05, 0.95),
        'breachDir': P.float(0, 0, 360, structural=True),
        'breachWidth': P.float(0, 0, 120, unit='deg'),
    },
    outputs=mask_outputs('floor', 'wall', 'terrace', 'rim', 'dome', 'breach'),
    apply=lambda f, p, ctx: emit(f, p, ctx, caldera_shape))


# ---------------------------------------------------------------------------------------------- impact crater ---

def impact_crater_shape(q, p, ctx):
    place = counted_placement(q, ctx, p.count, p.frequency, p.seed)
    rr = varied(p.radius, p.radiusVary, place['random'].y)
    wob = angular_wobble(place['d'], 2.6, p.seed)
    r = length(place['d']) / np.maximum(rr, EPS) * (1.0 + wob * 0.14)
    active = place['active']
    complexity = smoothstep(p.simpleMax, p.complexMin, rr)
    floor_frac = p.floorFrac * complexity + 0.04 * one_minus(complexity)
    wall_coord = sat((r - floor_frac) / np.maximum(one_minus(floor_frac), EPS))
    s_rise = smoothstep(0.0, 1.0, wall_coord)
    smooth_rise = np.power(np.maximum(s_rise, EPS), 1.7)
    t_wob = angular_wobble(place['d'], 5.3, p.seed + 41)
    terraces = (bench_stack(sat(wall_coord + t_wob * 0.22 / max(1, p.maxTerraces)), p.maxTerraces, 0.68)
                if p.maxTerraces > 0 else None)
    bench_gate = smoothstep(0.35, 0.62, wall_coord)
    rise = mix(smooth_rise, terraces.value, complexity * 0.45 * bench_gate) if terraces else smooth_rise
    floor_mask = one_minus(smoothstep(floor_frac - 0.025, floor_frac + 0.035, r)) * active
    wall_mask = smoothstep(0.03, 0.2, wall_coord) * one_minus(smoothstep(0.78, 1.01, wall_coord)) * active
    terrace_mask = terraces.tread * wall_mask * complexity if terraces else 0.0
    rim_mask = ring(r, 1.0, 0.11) * active
    blanket_reach = np.maximum(p.ejecta - 1.0, 0.05)
    apron_mask = (fan_profile(np.maximum(r - 1.0, 0.0), 3.2, blanket_reach) * gate(r > 1) * gate(r < p.ejecta)
                  * active)
    ray_pattern = radial_rays(place['d'], p.nRays, p.seed + 313, 34)
    rays_mask = ray_pattern * apron_mask
    rim_top_d = p.rimHeight * 0.6
    interior_d = -p.depth + (rim_top_d + p.depth) * rise
    decay_k = 3.2 / blanket_reach
    outer_d = (rim_top_d * np.exp(-(np.maximum(r - 1.0, 0.0) * decay_k)) * (1.0 + rays_mask * p.rayAmp)
               * one_minus(smoothstep(p.ejecta * 0.85, p.ejecta, r)))
    s_blend_c = smoothstep(0.93, 1.06, r)
    crater = mix(interior_d, outer_d, s_blend_c) * active
    ring_mode = smoothstep(p.ringOnset * 0.82, p.ringOnset, rr)
    peak_r = r / np.maximum(p.peakRadius, EPS)
    peak_mask = np.power(sat(one_minus(peak_r * peak_r)), 1.2) * complexity * one_minus(ring_mode) * active
    peak_ring = (ring(r, p.peakRadius * 1.8, np.maximum(p.peakRadius * 0.22, 0.025)) * complexity * ring_mode
                 * active)
    peak_relief = p.peakHeight * rr * (peak_mask + peak_ring * 0.72)
    detail_gate = (floor_mask * (p.depth * 0.035) + wall_mask * (p.depth * 0.16)
                   + apron_mask * (p.rimHeight * 0.025))
    detail = surface_detail(q, ctx, p.seed + 701, 13, 4) * detail_gate
    return {'height': crater + peak_relief + detail,
            'outs': {'floor': sat(floor_mask), 'wall': sat(wall_mask), 'terrace': sat(terrace_mask),
                     'rim': sat(rim_mask), 'ejecta': sat(apron_mask), 'peak': sat(peak_mask + peak_ring),
                     'rays': sat(rays_mask)}}


impactCrater = dict(
    label='Impact Crater', category='terrain', optionalInput=True,
    doc='Simple-to-complex impact morphology with terraced floors, central uplift, peak rings and rays.',
    params={
        'count': P.int(1, 1, 64),
        'frequency': P.float(4, 1, 32, structural=True, periodFreq=True),
        'radius': P.float(0.22, 0.004, 0.9), 'radiusVary': P.float(0.6, 0, 1),
        'depth': P.float(0.14, 0, 0.5), 'floorFrac': P.float(0.45, 0, 0.9),
        'simpleMax': P.float(0.05, 0.002, 0.5), 'complexMin': P.float(0.12, 0.004, 0.9),
        'maxTerraces': P.int(2, 0, 10), 'peakHeight': P.float(0.22, 0, 1.5),
        'peakRadius': P.float(0.18, 0.02, 0.6), 'ringOnset': P.float(0.35, 0.05, 0.9),
        'rimHeight': P.float(0.10, 0, 2), 'ejecta': P.float(1.8, 1, 5),
        'nRays': P.int(0, 0, 24), 'rayAmp': P.float(0.5, 0, 2),
        'seed': P.int(0, 0, 65535),
    },
    outputs=mask_outputs('floor', 'wall', 'terrace', 'rim', 'ejecta', 'peak', 'rays'),
    apply=lambda f, p, ctx: emit(f, p, ctx, impact_crater_shape))


# ------------------------------------------------------------------------------------------ cinder cone field ---

def cinder_field_shape(q, p, ctx):
    n = max(1, js_round(p.frequency))
    sx, sy = seed_shift(p.seed)
    sp = q * n
    base = sp.floor()
    fr = sp.fract()
    perx, pery = ctx.tile.x * n, ctx.tile.y * n
    h = 0.0
    flank_m = crater_m = rim_m = breach_m = flow_m = 0.0
    grain_n = noised(q.x * (n * 6), q.y * (n * 6), ctx.tile.x * n * 6, ctx.tile.y * n * 6)[0]
    grain = one_minus(np.abs(grain_n))
    for oy in (-1, 0, 1):
        for ox in (-1, 0, 1):
            cx = base.x + ox
            cy = base.y + oy
            a = Vec(*hash2(cx + sx, cy + sy, perx, pery))
            b = Vec(*hash2(cx + (sx + 733), cy + (sy + 197), perx, pery))
            c = Vec(*hash2(cx + (sx + 291), cy + (sy + 941), perx, pery))
            jx, jy = a.x * 0.42, a.y * 0.42
            along_axis = Vec(ox + 0.5 + jx, oy + 0.5 + jy * (1.0 - p.alignment * 0.85))
            vent = along_axis - fr
            dvec = vent / n
            size_mul = np.exp(b.x * p.radiusVary * 0.55)
            R = np.maximum(p.radius * size_mul, EPS)
            age = c.x * 0.5 + 0.5
            dist = length(dvec) + EPS
            dirv = dvec / dist
            q0 = dist / R
            s3 = dirv.y * 3.0 - dirv.y * dirv.y * dirv.y * 4.0
            c3 = dirv.x * dirv.x * dirv.x * 4.0 - dirv.x * 3.0
            ph = b.y * math.pi
            mod3 = 1.0 + ((s3 * math.cos(1) + c3 * math.sin(1)) * 0.0 + (s3 * np.cos(ph) + c3 * np.sin(ph)) * 0.05)
            qq = q0 / mod3
            alpha = mix(p.reposeAngle * (math.pi / 180), 24 * math.pi / 180, age * p.aging)
            H0 = R * (np.sin(alpha) / np.maximum(np.cos(alpha), EPS))
            toe = mix(0.10, 0.22, age * p.aging)
            sT = sat(one_minus(qq) / toe)
            F = np.where(qq <= one_minus(toe), one_minus(qq), toe * (sT * sT * 2.0 - sT * sT * sT)) * gate(qq < 1)
            cone = H0 * F
            qc = np.maximum(p.craterFrac, 0.05)
            dc = H0 * p.craterDepth * mix(0.30, 0.08, age * p.aging)
            rim_z = H0 * F - dc + dc * (qq / qc) * (qq / qc)
            cone = np.where(qq < qc, np.minimum(cone, rim_z), cone)
            rim_band = np.exp((qq - qc) * (qq - qc) / (-2 * 0.03 * 0.03))
            cone = cone + rim_band * H0 * 0.035 * one_minus(age * p.aging * 0.8)
            breached = gate(c.y * 0.5 + 0.5 < p.breachFraction)
            baz = a.x * 3.1 + b.x * 1.7
            bdir = Vec(np.cos(baz), np.sin(baz))
            dotb = dirv.x * bdir.x + dirv.y * bdir.y
            widen = 0.7 + qq * 0.6
            ex = -one_minus(dotb) / np.maximum(widen * 0.16, EPS)
            notch = np.exp(ex + ex * 0.0)
            gQ = smoothstep(qc * 0.58, qc * 1.04, qq) * one_minus(smoothstep(0.98, 1.05, qq))
            cut = notch * gQ * 0.85 * breached
            cone = cone * one_minus(cut)
            flank_band = smoothstep(qc * 1.2, 0.55, qq) * one_minus(smoothstep(0.8, 1.0, qq))
            cone = cone - grain * flank_band * H0 * p.rugosity * 0.06
            bperp = Vec(-bdir.y, bdir.x)
            L = R * p.flowLength * (1.2 + (c.y * 0.5 + 0.5) * 2.2)
            s_along = dvec.x * bdir.x + dvec.y * bdir.y - R * 0.55
            sN = s_along / np.maximum(L, EPS)
            t_perp = dvec.x * bperp.x + dvec.y * bperp.y + np.sin(sN * 9.4 + b.y * 6.0) * L * 0.10
            w_half = R * (0.24 + sN * 0.5) * (1.0 + np.sin(sN * 21.0 + a.y * 9.0) * 0.18)
            in_s = smoothstep(0.0, R * 0.3, s_along) * one_minus(smoothstep(L * 0.8, L, s_along))
            in_t = one_minus(smoothstep(w_half * 0.6, w_half, np.abs(t_perp)))
            flow_mask = in_s * in_t * breached
            flow = flow_mask * H0 * p.flowThickness * 0.22 * (1.0 + grain * 0.25)
            contribution = np.maximum(cone, flow)
            h = np.maximum(h, contribution)
            flank_m = np.maximum(flank_m, F * gate(qq > qc))
            crater_m = np.maximum(crater_m, gate(qq < qc) * gate(qq < 1))
            rim_m = np.maximum(rim_m, rim_band * gate(qq < 1))
            breach_m = np.maximum(breach_m, cut)
            flow_m = np.maximum(flow_m, flow_mask)
    return {'height': h, 'outs': {'flank': sat(flank_m), 'crater': sat(crater_m), 'rim': sat(rim_m),
                                  'breach': sat(breach_m), 'tephra': sat(flow_m)}}


cinderConeField = dict(
    label='Cinder Cone Field', category='terrain', optionalInput=True,
    doc='A field of angle-of-repose cinder cones with summit craters, breached flanks and lobed lava flows, built '
        'from a measured aerial reference study. Cones overlap and bury one another freely.',
    params={
        'frequency': P.float(5, 1, 40, structural=True, periodFreq=True),
        'radius': P.float(0.085, 0.004, 0.5), 'radiusVary': P.float(0.7, 0, 1),
        'alignment': P.float(0.4, 0, 1, doc='pulls vents toward eruptive fissure lines'),
        'reposeAngle': P.float(31, 20, 42, unit='deg'),
        'aging': P.float(0.5, 0, 1,
                         doc='mixes in old, degraded cones: gentler slopes, filled craters, worn rims'),
        'craterFrac': P.float(0.34, 0.05, 0.7), 'craterDepth': P.float(0.6, 0, 1),
        'breachFraction': P.float(0.4, 0, 1, doc='fraction of cones with a breached flank and a lava flow'),
        'flowLength': P.float(2.4, 0, 6, doc='flow reach in cone radii'),
        'flowThickness': P.float(0.45, 0, 1),
        'rugosity': P.float(0.3, 0, 1),
        'seed': P.int(0, 0, 65535),
    },
    outputs=mask_outputs('flank', 'crater', 'rim', 'breach', 'tephra'),
    apply=lambda f, p, ctx: emit(f, p, ctx, cinder_field_shape))


# ------------------------------------------------------------------------------------------------------- maar ---

def maar_shape(q, p, ctx):
    c = centred(q, ctx, p.centre, p.radius)
    d, r0 = c['d'], c['r']
    mwob = angular_wobble(d, 2.9, _seed(p) + 7)
    r = r0 * (1.0 + mwob * 0.12)
    depth = p.radius * 2.0 / np.maximum(p.aspect, EPS)
    style = 3.2 if p.style == 'tuffCone' else (1.75 if p.style == 'tuffRing' else 1.0)
    wall_coord = sat((r - p.floorFrac) / np.maximum(one_minus(p.floorFrac), EPS))
    wall_rise = smoothstep(0.0, np.maximum(p.wallFraction, 0.05), wall_coord)
    floor_mask = one_minus(smoothstep(p.floorFrac - 0.025, p.floorFrac + 0.035, r))
    wall_mask = smoothstep(0.04, 0.28, wall_coord) * one_minus(smoothstep(0.72, 1.02, wall_coord))
    rim_mask = ring(r, 1.0, np.maximum(p.rimWidth * 0.22, 0.025))
    crater = -depth * one_minus(wall_rise) * gate(r < 1.04)
    tephra_mask = (fan_profile(np.maximum(r - 1.0, 0.0), 3.4, np.maximum(p.apron, EPS)) * gate(r > 1)
                   * gate(r < 1.0 + p.apron))
    ejecta = p.rimHeight * (0.24 * style) * tephra_mask
    detail_gate = (floor_mask * (depth * 0.035) + wall_mask * (depth * 0.14)
                   + (rim_mask + tephra_mask) * p.rimHeight * 0.035)
    detail = surface_detail(q, ctx, p.seed + 211, 11, 4) * detail_gate
    return {'height': crater + rim_mask * p.rimHeight * style + ejecta + detail,
            'outs': {'floor': sat(floor_mask), 'wall': sat(wall_mask), 'rim': sat(rim_mask),
                     'tephra': sat(tephra_mask)}}


maar = dict(
    label='Maar', category='terrain', optionalInput=True,
    doc='Broad below-datum phreatomagmatic crater with a low tuff ring and ejecta apron.',
    params={
        'style': P.enum('maar', ['maar', 'tuffRing', 'tuffCone']),
        'centre': P.vec2([0.5, 0.5]), 'radius': P.float(0.23, 0.01, 0.8),
        'aspect': P.float(14, 5, 60), 'floorFrac': P.float(0.4, 0.05, 0.9),
        'wallFraction': P.float(0.55, 0.1, 1), 'rimHeight': P.float(0.06, 0, 0.8),
        'rimWidth': P.float(0.35, 0.05, 1), 'apron': P.float(1.5, 1, 4),
        'seed': P.int(0, 0, 65535),
    },
    outputs=mask_outputs('floor', 'wall', 'rim', 'tephra'),
    apply=lambda f, p, ctx: emit(f, p, ctx, maar_shape))


# ----------------------------------------------------------------------------------------------- cirque field ---

def cirque_shape(q, p, ctx):
    place = counted_placement(q, ctx, p.count, p.frequency, p.seed)
    rr = varied(p.radius, p.radiusVary, place['random'].x)
    r = length(place['d']) / np.maximum(rr, EPS)
    base_facing = direction_vector(p.aspect)
    rnd = place['random']
    random_facing = normalize(Vec(rnd.z - 0.5, rnd.w - 0.5) + Vec(EPS, 0.0))
    facing = normalize(mix(random_facing, base_facing, p.aspectBias))
    opening = angular_gate_axis(place['d'], facing, p.openWidth) * place['active']
    closed = one_minus(opening)
    wall_coord = sat((r - p.floorFrac) / np.maximum(one_minus(p.floorFrac), EPS))
    rise = smoothstep(0.0, np.maximum(p.wallFraction, 0.05), wall_coord)
    cut_mask = one_minus(rise) * closed * place['active'] * gate(r < 1.03)
    floor_mask = one_minus(smoothstep(p.floorFrac - 0.03, p.floorFrac + 0.04, r)) * closed * place['active']
    wall_mask = (smoothstep(0.02, 0.22, wall_coord) * one_minus(smoothstep(0.72, 1.0, wall_coord)) * closed
                 * place['active'])
    lip_mask = ring(r, 0.96, 0.07) * opening * place['active']
    arete_mask = (ring(r, 1.06, 0.09) * closed * place['active']
                  * sat(surface_detail(q, ctx, p.seed + 307, 8, 3) * 0.5 + 0.65))
    detail_gate = wall_mask * (p.depth * 0.16) + floor_mask * (p.depth * 0.025) + lip_mask * (p.lipHeight * 0.04)
    detail = surface_detail(q, ctx, p.seed + 409, 12, 4) * detail_gate
    return {'height': -p.depth * cut_mask + p.lipHeight * lip_mask + arete_mask * p.depth * 0.07 + detail,
            'outs': {'headwall': sat(wall_mask), 'floor': sat(floor_mask), 'lip': sat(lip_mask),
                     'arete': sat(arete_mask)}}


cirque = dict(
    label='Cirque Field', category='terrain', optionalInput=True,
    doc='Aspect-biased open glacial amphitheatres with overdeepened floors, lips and residual aretes.',
    params={
        'count': P.int(3, 1, 24),
        'frequency': P.float(4, 1, 24, structural=True, periodFreq=True),
        'radius': P.float(0.14, 0.02, 0.6), 'radiusVary': P.float(0.5, 0, 1),
        'depth': P.float(0.14, 0, 0.6), 'floorFrac': P.float(0.35, 0.05, 0.8),
        'wallFraction': P.float(0.85, 0.2, 1),
        'openWidth': P.float(110, 40, 200, unit='deg'), 'lipHeight': P.float(0.03, 0, 0.2),
        'aspect': P.float(0, 0, 360, structural=True), 'aspectBias': P.float(0.6, 0, 1),
        'seed': P.int(0, 0, 65535),
    },
    outputs=mask_outputs('headwall', 'floor', 'lip', 'arete'),
    apply=lambda f, p, ctx: emit(f, p, ctx, cirque_shape))


# ------------------------------------------------------------------------------------------------ basin field ---

def basin_field_shape(q, p, ctx):
    place = scattered(q, ctx, p.frequency, p.seed, p.jitter)
    rnd = place['random']
    active = gate(rnd.x < p.density)
    rr = varied(p.radius, p.radiusVary, rnd.y)
    base_axis = direction_vector(p.orientation)
    random_axis = normalize(Vec(rnd.z - 0.5, rnd.w - 0.5) + Vec(EPS, 0.0))
    axis = normalize(mix(base_axis, random_axis, p.orientJitter))
    r = ellipse_radius(place['d'], axis, p.elongation) / np.maximum(rr, EPS)
    if p.profile == 'cone':
        cut = sat(one_minus(r))
    elif p.profile == 'cylinder':
        cut = one_minus(smoothstep(0.82, 1.0, r))
    elif p.profile == 'dish':
        cut = sat(one_minus(r * r))
    else:
        cut = one_minus(smoothstep(0.28, 1.0, r))
    cut = cut * active
    floor_mask = (one_minus(smoothstep(0.7, 0.8, r)) if p.profile == 'cylinder'
                  else one_minus(smoothstep(0.22, 0.43, r))) * active
    wall_mask = smoothstep(0.18, 0.48, r) * one_minus(smoothstep(0.82, 1.03, r)) * active
    rim_mask = ring(r, 1.0, 0.07) * active
    depth = varied(p.depth, p.depthVary, rnd.z)
    basin_mask = one_minus(smoothstep(0.82, 1.08, r)) * active
    detail_gate = floor_mask * (depth * 0.035) + wall_mask * (depth * 0.15) + rim_mask * (p.rimHeight * 0.035)
    detail = surface_detail(q, ctx, p.seed + 503, 15, 3) * detail_gate
    return {'height': -depth * cut + p.rimHeight * rim_mask + detail,
            'outs': {'floor': sat(floor_mask), 'wall': sat(wall_mask), 'rim': sat(rim_mask),
                     'basins': sat(basin_mask)}}


basinField = dict(
    label='Basin Field', category='terrain', optionalInput=True,
    doc='Tileable closed-depression fields ranging from solution bowls to oriented collapse basins.',
    params={
        'profile': P.enum('bowl', ['bowl', 'cone', 'cylinder', 'dish']),
        'frequency': P.float(10, 1, 64, structural=True, periodFreq=True),
        'density': P.float(0.7, 0.05, 1), 'radius': P.float(0.05, 0.003, 0.4),
        'radiusVary': P.float(0.7, 0, 1), 'depth': P.float(0.05, 0, 0.5),
        'depthVary': P.float(0.6, 0, 1), 'elongation': P.float(1, 1, 6),
        'orientation': P.float(0, 0, 360, structural=True), 'orientJitter': P.float(0.2, 0, 1),
        'rimHeight': P.float(0, 0, 0.3), 'jitter': P.float(0.9, 0, 1),
        'seed': P.int(0, 0, 65535),
    },
    outputs=mask_outputs('floor', 'wall', 'rim', 'basins'),
    apply=lambda f, p, ctx: emit(f, p, ctx, basin_field_shape))


# ------------------------------------------------------------------------------------------------ mound field ---

def mound_field_shape(q, p, ctx):
    place = scattered(q, ctx, p.frequency, p.seed, p.jitter)
    rnd = place['random']
    active = gate(rnd.x < p.density)
    rr = varied(p.radius, p.radiusVary, rnd.y)
    r = ellipse_radius(place['d'], direction_vector(p.orientation), p.elongation) / np.maximum(rr, EPS)
    height = varied(p.height, p.heightVary, rnd.z)
    mound_profile = np.power(np.maximum(sat(one_minus(r * r)), EPS), p.bulk) * gate(r < 1)
    crater_r = r / np.maximum(p.craterFrac, EPS)
    crater_mask = sat(one_minus(crater_r * crater_r)) * smoothstep(0.28, 0.72, p.maturity) * active
    collapse = smoothstep(0.72, 1.0, p.maturity)
    young = height * mound_profile * (0.68 + p.maturity * 0.52) - height * 0.52 * crater_mask
    collapsed = -height * 0.72 * one_minus(smoothstep(0.2, 1.0, r))
    rampart_mask = ring(r, 0.92, 0.09) * collapse * active
    mounds_mask = mound_profile * one_minus(collapse) * active
    summit_mask = one_minus(smoothstep(0.12, 0.45, r)) * one_minus(crater_mask) * one_minus(collapse) * active
    hollows_mask = smoothstep(0.94, 1.12, r) * one_minus(smoothstep(1.28, 1.62, r)) * active
    relief = mix(young, collapsed, collapse) * active + rampart_mask * height * p.rampart
    detail_gate = mounds_mask * (height * 0.08) + rampart_mask * (height * 0.09) + hollows_mask * (height * 0.018)
    detail = surface_detail(q, ctx, p.seed + 607, 18, 3) * detail_gate
    return {'height': relief + detail,
            'outs': {'mounds': sat(mounds_mask), 'summit': sat(summit_mask), 'crater': sat(crater_mask),
                     'rampart': sat(rampart_mask), 'hollows': sat(hollows_mask)}}


moundField = dict(
    label='Mound Field', category='terrain', optionalInput=True,
    doc='Ice-cored and earth mounds with a continuous growth, summit-crater and collapse life cycle.',
    params={
        'frequency': P.float(14, 1, 96, structural=True, periodFreq=True),
        'density': P.float(0.6, 0.05, 1), 'radius': P.float(0.04, 0.002, 0.3),
        'radiusVary': P.float(0.6, 0, 1), 'height': P.float(0.05, 0, 0.4),
        'heightVary': P.float(0.7, 0, 1), 'bulk': P.float(0.6, 0.2, 3),
        'maturity': P.float(0.3, 0, 1), 'craterFrac': P.float(0.3, 0.05, 0.7),
        'rampart': P.float(0.3, 0, 1), 'elongation': P.float(1, 1, 4),
        'orientation': P.float(0, 0, 360, structural=True), 'jitter': P.float(0.9, 0, 1),
        'seed': P.int(0, 0, 65535),
    },
    outputs=mask_outputs('mounds', 'summit', 'crater', 'rampart', 'hollows'),
    apply=lambda f, p, ctx: emit(f, p, ctx, mound_field_shape))


# ---------------------------------------------------------------------------------------------- volcanic plug ---

def volcanic_plug_shape(q, p, ctx):
    place = counted_placement(q, ctx, p.count, p.frequency, p.seed)
    pd, active = place['d'], place['active']
    r0 = length(pd) / np.maximum(p.radius, EPS)
    r = r0 * (1.0 + p.taper * sat(one_minus(r0)) * 0.32)
    column_mask = one_minus(smoothstep(one_minus(p.wallSoft), 1.0, r)) * active
    dikes_mask = 0.0
    phase = js_mod(p.seed * 0.38196601125, 1) * TAU
    for i in range(int(p.nDikes)):
        a = phase + TAU * i / max(1, p.nDikes)
        axis = Vec(math.cos(a), math.sin(a))
        side = Vec(-math.sin(a), math.cos(a))
        along = dot(pd, axis)
        across = np.abs(dot(pd, side))
        fin = (one_minus(smoothstep(0.0, p.dikeWidth, across))
               * one_minus(smoothstep(p.radius, p.radius * p.dikeReach, along)) * gate(along > 0) * active)
        dikes_mask = np.maximum(dikes_mask, fin)
    tail_axis = direction_vector(p.tailDir)
    tail_side = Vec(-tail_axis.y, tail_axis.x)
    tail_along = dot(pd, tail_axis)
    tail_across = dot(pd, tail_side)
    ta = tail_along - p.radius * 2.1
    tail_mask = (np.exp(-(tail_across * tail_across / np.maximum(p.radius * p.radius * 0.32, EPS)))
                 * np.exp(-(ta * ta / np.maximum(p.radius * p.radius * 5.0, EPS)))
                 * gate(tail_along > 0) * one_minus(column_mask) * active)
    talus_mask = (fan_profile(np.maximum(r0 - 1.0, 0.0), 4.0, 0.85) * gate(r0 > 1) * gate(r0 < 1.85) * active)
    plain_mask = one_minus(sat(column_mask + dikes_mask + talus_mask + tail_mask))
    structural = (p.height * column_mask + p.height * p.dikeHeight * dikes_mask + p.tailHeight * tail_mask
                  + p.height * 0.12 * talus_mask + p.plainLevel * 0.02 * talus_mask)
    detail_gate = (column_mask * (p.height * 0.035) + dikes_mask * (p.height * p.dikeHeight * 0.07)
                   + talus_mask * (p.height * 0.035))
    detail = surface_detail(q, ctx, p.seed + 809, 17, 4) * detail_gate
    return {'height': structural + detail,
            'outs': {'column': sat(column_mask), 'dikes': sat(dikes_mask), 'talus': sat(talus_mask),
                     'plain': sat(plain_mask)}}


volcanicPlug = dict(
    label='Volcanic Plug', category='terrain', optionalInput=True,
    doc='Near-vertical erosional necks with radiating dike fins, debris skirts and optional lee tails.',
    params={
        'count': P.int(1, 1, 16),
        'frequency': P.float(3, 1, 16, structural=True, periodFreq=True),
        'radius': P.float(0.11, 0.005, 0.3), 'height': P.float(0.42, 0, 1.2),
        'wallSoft': P.float(0.12, 0.01, 0.6), 'taper': P.float(0.15, 0, 1),
        'nDikes': P.int(5, 0, 8), 'dikeHeight': P.float(0.5, 0, 1),
        'dikeWidth': P.float(0.01, 0.002, 0.08), 'dikeReach': P.float(4, 1, 12),
        'tailHeight': P.float(0, 0, 0.5), 'tailDir': P.float(0, 0, 360, structural=True),
        'plainLevel': P.float(0.3, -1, 2), 'seed': P.int(0, 0, 65535),
    },
    outputs=mask_outputs('column', 'dikes', 'talus', 'plain'),
    apply=lambda f, p, ctx: emit(f, p, ctx, volcanic_plug_shape))


# -------------------------------------------------------------------------------------------------- lava dome ---

def dome_profile(r, bulge):
    return np.power(np.maximum(one_minus(np.power(r, bulge)), EPS), 1.0 / np.maximum(bulge, EPS)) * gate(r < 1)


def lava_dome_shape(q, p, ctx):
    d = wrapped_delta(q, p.centre, ctx.tile)
    axis = direction_vector(p.flowDir)
    side = Vec(-axis.y, axis.x)
    shifted = d - axis * p.radius * p.coulee * 0.18
    r = length(shifted) / np.maximum(p.radius, EPS)
    main = dome_profile(r, p.bulge)
    along = dot(d, axis) / np.maximum(p.radius * (1.0 + p.coulee * 1.8), EPS)
    across = dot(d, side) / np.maximum(p.radius, EPS)
    lobe_r = length(Vec(along - p.coulee * 0.25, across))
    lobe = dome_profile(lobe_r, np.maximum(p.bulge * 0.72, 2.0)) * p.coulee
    body = np.maximum(main, lobe * 0.82)
    carapace_mask = sat(body * 1.18)
    toe_mask = np.maximum(ring(r, 0.96, 0.055), ring(lobe_r, 0.96, 0.055) * p.coulee)
    raw_spines = surface_detail(q, ctx, p.seed + 911, p.spineFreq, 4)
    spines_mask = np.power(sat(raw_spines * 0.5 + 0.55), 4.0) * carapace_mask
    edge_r = np.minimum(r, lobe_r + one_minus(p.coulee) * 10.0)
    talus_mask = (fan_profile(np.maximum(edge_r - 1.0, 0.0), 4.0, np.maximum(p.apron, EPS)) * gate(edge_r > 1)
                  * gate(edge_r < 1.0 + p.apron))
    geologic = surface_detail(q, ctx, p.seed + 1013, 12, 4) * (carapace_mask * (p.height * 0.035)
                                                               + talus_mask * (p.height * 0.04))
    return {'height': p.height * body + p.spineHeight * 0.4 * spines_mask + p.height * 0.14 * talus_mask + geologic,
            'outs': {'carapace': sat(carapace_mask), 'spines': sat(spines_mask), 'toe': sat(toe_mask),
                     'talus': sat(talus_mask)}}


lavaDome = dict(
    label='Lava Dome', category='terrain', optionalInput=True,
    doc='Bulbous steep-toed viscous dome with spines, asymmetric coulee and blocky talus apron.',
    params={
        'centre': P.vec2([0.5, 0.5]), 'radius': P.float(0.22, 0.01, 0.6),
        'height': P.float(0.32, 0, 0.8), 'bulge': P.float(4, 2, 12),
        'spineHeight': P.float(0.15, 0, 0.6),
        'spineFreq': P.float(16, 2, 64, structural=True, periodFreq=True),
        'coulee': P.float(0.35, 0, 1), 'flowDir': P.float(0, 0, 360, structural=True),
        'apron': P.float(0.5, 0, 2), 'seed': P.int(0, 0, 65535),
    },
    outputs=mask_outputs('carapace', 'spines', 'toe', 'talus'),
    apply=lambda f, p, ctx: emit(f, p, ctx, lava_dome_shape))


# ------------------------------------------------------------------------------------------------------- mesa ---

def mesa_shape(q, p, ctx):
    place = counted_placement(q, ctx, p.count, p.frequency, p.seed)
    rnd, active = place['random'], place['active']
    rr = varied(p.radius, p.radiusVary, rnd.y)
    raw_r = length(place['d']) / np.maximum(rr, EPS)
    outline = surface_detail(q, ctx, p.seed + 1103, p.outlineFreq, 4)
    r = raw_r / np.maximum(1.0 + outline * p.outlineChaos * 0.16, 0.7)
    wall_coord = sat((r - p.capFrac) / np.maximum(p.scarpWidth, EPS))
    smooth_fall = one_minus(smoothstep(0.0, 1.0, wall_coord))
    benches = bench_stack(wall_coord, p.benches, 0.74, rnd.z * 0.24) if p.benches > 0 else None
    stepped_fall = mix(smooth_fall, one_minus(benches.value), 0.82) if benches else smooth_fall
    toe = p.capFrac + p.scarpWidth
    cap_mask = one_minus(smoothstep(p.capFrac - 0.025, p.capFrac + 0.025, r)) * active
    scarp_mask = (smoothstep(p.capFrac - 0.025, p.capFrac + 0.04, r) * one_minus(smoothstep(toe - 0.04, toe + 0.035, r))
                  * active)
    bench_mask = benches.tread * scarp_mask if benches else 0.0
    talus_mask = (fan_profile(np.maximum(r - toe, 0.0), 3.6, np.maximum(p.apron, EPS)) * gate(r > toe)
                  * gate(r < toe + p.apron) * active)
    plain_mask = one_minus(sat(cap_mask + scarp_mask + talus_mask))
    relief = (p.height * stepped_fall * gate(r < toe + 0.03) * active + p.height * p.talusHeight * talus_mask
              + p.plainLevel * 0.02 * talus_mask)
    detail_gate = (cap_mask * (p.height * 0.009) + scarp_mask * (p.height * 0.045)
                   + talus_mask * (p.height * p.talusHeight * 0.055))
    detail = surface_detail(q, ctx, p.seed + 1217, 14, 4) * detail_gate
    return {'height': relief + detail,
            'outs': {'cap': sat(cap_mask), 'scarp': sat(scarp_mask), 'benches': sat(bench_mask),
                     'talus': sat(talus_mask), 'plain': sat(plain_mask)}}


mesa = dict(
    label='Mesa', category='terrain', optionalInput=True,
    doc='Flat caprock remnants with warped outlines, stepped scarps and a distinct debris apron.',
    params={
        'count': P.int(1, 1, 32),
        'frequency': P.float(4, 1, 24, structural=True, periodFreq=True),
        'radius': P.float(0.22, 0.01, 0.6), 'radiusVary': P.float(0.5, 0, 1),
        'height': P.float(0.34, 0, 1), 'capFrac': P.float(0.7, 0.1, 0.98),
        'scarpWidth': P.float(0.12, 0.01, 0.5), 'outlineChaos': P.float(0.35, 0, 1),
        'outlineFreq': P.float(6, 1, 32, structural=True, periodFreq=True),
        'benches': P.int(3, 0, 12), 'talusHeight': P.float(0.25, 0, 1),
        'apron': P.float(0.5, 0, 2), 'plainLevel': P.float(0.25, -1, 2),
        'seed': P.int(0, 0, 65535),
    },
    outputs=mask_outputs('cap', 'scarp', 'benches', 'talus', 'plain'),
    apply=lambda f, p, ctx: emit(f, p, ctx, mesa_shape))


WAVE1_LANDFORMS = {
    'caldera': caldera,
    'impactCrater': impactCrater,
    'cinderConeField': cinderConeField,
    'maar': maar,
    'cirque': cirque,
    'basinField': basinField,
    'moundField': moundField,
    'volcanicPlug': volcanicPlug,
    'lavaDome': lavaDome,
    'mesa': mesa,
}
