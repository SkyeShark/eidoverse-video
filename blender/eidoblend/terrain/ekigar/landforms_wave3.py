"""Landform library, wave 3 (src/core/landforms_wave3.js): level-keyed and karst landforms.

Terrace Stair, Wave-cut Platform, Playa / Polje, Planation Surface, Tower Karst, Cockpit Karst, Limestone Pavement,
Bornhardt, Badlands and Patterned Ground. These rebuild the height outright, so their gradient is taken from screen
derivatives of the new height (derivative_field), exactly as Ekigar does it.
"""
from __future__ import annotations

import math

import numpy as np

from ._tsl import Vec, mix, select, step01, dot, length, fract, sat
from ._deriv import dfdx, dfdy
from .noise import hash2
from .landform_shared import (P, TAU, EPS, H, G, field, sstep as smoothstep, fbm, ridged, scatter_cell, ring,
                              fan_profile, axis_frame, bench_stack, snapped_axis, piedmont_break, surface_detail,
                              js_round, js_mod)


def mask(name, doc):
    return {'name': name, 'type': 'mask', 'doc': doc}


def one_minus(v):
    return 1.0 - v


def gate(cond):
    return step01(cond)


def axis_vector(degrees, normalised=True):
    a = snapped_axis(degrees)
    if not normalised:
        return Vec(float(a[0]), float(a[1]))
    n = math.hypot(a[0], a[1]) or 1.0
    return Vec(a[0] / n, a[1] / n)


def derivative_field(h, ctx, aux=0.0):
    """The rebuilt height with its gradient from screen derivatives (per texel, times the field resolution)."""
    scale = max(1, ctx.resolution if ctx.resolution is not None else 1024)
    return field(h, Vec(dfdx(h), dfdy(h)) * scale, aux)


def has_input(ctx):
    return ctx.wired is not None and 'in' in ctx.wired


def seed_pair(seed=0):
    s = js_round(seed) & 0xFFFFFFFF
    return [((s * 1103515245 + 12345) & 0xFFFFFFFF) % 4096, ((s * 22695477 + 1) & 0xFFFFFFFF) % 4096]


def metric_distance(kind, d, morph):
    euclidean = length(d)
    if kind == 'euclidianChebyshev':
        return mix(euclidean, np.maximum(np.abs(d.x), np.abs(d.y)), morph)
    if kind == 'euclidianManhattan':
        return mix(euclidean, np.abs(d.x) + np.abs(d.y), morph)
    return euclidean


def cell_search3(q, cells, ctx, seed, jitter, metric=length):
    """Nearest three periodic sites, with stable nearest-site attributes: dict(f1, f2, f3, delta, random)."""
    n = max(1, js_round(cells))
    sx, sy = seed_pair(seed)
    sp = q * n
    base = sp.floor()
    fr = sp.fract()
    perx, pery = ctx.tile.x * n, ctx.tile.y * n
    f1, f2, f3 = 99.0, 100.0, 101.0
    delta = Vec(0.0, 0.0)
    random = Vec(0.0, 0.0, 0.0, 0.0)
    for oy in (-1, 0, 1):
        for ox in (-1, 0, 1):
            cx = base.x + ox
            cy = base.y + oy
            ax_, ay_ = hash2(cx + sx, cy + sy, perx, pery)
            bx_, by_ = hash2(cx + (sx + 733), cy + (sy + 197), perx, pery)
            d = Vec(ox + 0.5 + ax_ * jitter * 0.48 - fr.x, oy + 0.5 + ay_ * jitter * 0.48 - fr.y)
            v = metric(d)
            win1, win2, win3 = v < f1, v < f2, v < f3
            nf3 = np.where(win1, f2, np.where(win2, f2, np.where(win3, v, f3)))
            nf2 = np.where(win1, f1, np.where(win2, v, f2))
            delta = select(win1, d, delta)
            random = select(win1, Vec(ax_ * 0.5 + 0.5, ay_ * 0.5 + 0.5, bx_ * 0.5 + 0.5, by_ * 0.5 + 0.5), random)
            f1 = np.where(win1, v, f1)
            f2 = nf2
            f3 = nf3
    return {'f1': f1, 'f2': f2, 'f3': f3, 'delta': delta, 'random': random}


# ---------------------------------------------------------------------------------------------- terrace stair ---

def _terrace_stair(f, p, ctx):
    frame = axis_frame(ctx.p, p.axis, 1, 0.0, p.seed)
    along = dot(ctx.p - Vec(0.5, 0.5), axis_vector(p.axis))
    total = p.spacing * p.treads
    wob = fbm(ctx.p, p.warpFreq, 3, ctx, p.seed + 19)
    w_warped = frame.w + wob * p.warp * p.beltWidth * 0.8
    ramp = np.abs(w_warped) / np.maximum(p.beltWidth, EPS) * total * 1.35
    datum = p.downValley * along + wob * p.warp * p.spacing * 0.4
    relative = H(f) + ramp - datum
    side_offset = gate(frame.w > 0) * one_minus(p.pairing) * 0.5
    uneven = fbm(ctx.p, p.warpFreq * 2, 2, ctx, p.seed + 101) * p.jitter * 0.32
    stair = bench_stack(np.maximum(relative, 0.0) / np.maximum(total, EPS), p.treads, p.convexity,
                        side_offset + uneven)
    belt = one_minus(smoothstep(p.beltWidth * 0.86, p.beltWidth, np.abs(w_warped)))
    vertical = (smoothstep(p.spacing * -0.12, 0.0, relative)
                * one_minus(smoothstep(total - p.spacing * 0.2, total, relative)))
    scope = belt * vertical
    stair_h = datum + stair.value * total
    retained = (H(f) - stair_h) * p.bedrock * stair.tread * 0.18
    detail = (surface_detail(ctx.p, ctx, p.seed + 313, 17, 3) * p.spacing * 0.12
              * (stair.tread * p.bedrock + stair.riser * 0.22))
    target = stair_h + retained + detail
    h = mix(H(f) + ramp, target, scope)
    return {'field': derivative_field(h, ctx, scope),
            'outs': {'tread': stair.tread * scope, 'riser': stair.riser * scope, 'index': sat(stair.index) * scope,
                     'belt': belt}}


terraceStair = dict(
    label='Terrace Stair', category='terrain', visualFixture='smooth',
    doc='Paired or unpaired level treads and steep risers keyed to a former valley-floor datum.',
    params={
        'treads': P.int(5, 1, 12, doc='terrace levels in the staircase'),
        'spacing': P.float(0.085, 0.004, 0.4, doc='height between successive treads'),
        'convexity': P.float(0.75, 0, 1, doc='hard riser under a flat tread'),
        'jitter': P.float(0.25, 0, 1, doc='irregular riser spacing; real staircases are uneven'),
        'downValley': P.float(0.08, -0.5, 0.5,
                              doc='gradient of the former floor along the valley; nonzero intentionally opens the '
                                  'axial seam'),
        'axis': P.float(0, 0, 360, structural=True, doc='valley axis, snapped to a lattice axis'),
        'warp': P.float(0.45, 0, 1, doc='meander of the valley and its terrace edges'),
        'warpFreq': P.float(3, 1, 16, structural=True, periodFreq=True),
        'beltWidth': P.float(0.3, 0.03, 1, doc='how far from the valley axis terraces extend'),
        'pairing': P.float(0.7, 0, 1, doc='1 fully paired, 0 fully unpaired'),
        'bedrock': P.float(0.4, 0, 1, doc='1 strath with surviving bedrock texture, 0 alluvial fill'),
        'seed': P.int(0, 0, 65535),
    },
    outputs=[mask('tread', 'level terrace surfaces'), mask('riser', 'steep terrace scarps'),
             mask('index', 'normalised relative terrace age'), mask('belt', 'terraced valley belt')],
    apply=_terrace_stair)


# ------------------------------------------------------------------------------------------ wave-cut platform ---

def _wave_cut_platform(f, p, ctx):
    original = H(f)
    rough_coast = fbm(ctx.p, p.irregFreq, 3, ctx, 731) * p.irregular * p.cliffHeight * 0.16
    h = original
    platform = cliff = notch = terrace = 0.0
    for j in range(int(p.levels)):
        level = p.seaLevel + p.uplift * j + rough_coast
        relative = original - level
        reach = smoothstep(level - p.platformMax, level - p.platformMax * 0.76, original)
        cliff_edge = p.cliffHeight * p.cliffSharp
        upper = one_minus(smoothstep(level + cliff_edge, level + p.cliffHeight, original))
        lower_band = 1.0 if j == 0 else smoothstep(level - p.uplift * 0.55, level - p.uplift * 0.45, original)
        cut = reach * upper * lower_band
        bench = level + np.minimum(relative, 0.0) * p.seaward
        groove = np.exp(-np.power(relative / np.maximum(p.notchWidth, EPS), 2))
        cliff_band = (smoothstep(level + cliff_edge * 0.72, level + cliff_edge, original)
                      * one_minus(smoothstep(level + p.cliffHeight * 0.94, level + p.cliffHeight, original)))
        h = mix(h, bench, cut) - groove * p.notchDepth
        platform = np.maximum(platform, cut * one_minus(cliff_band))
        cliff = np.maximum(cliff, cliff_band)
        notch = np.maximum(notch, groove)
        if j > 0:
            terrace = np.maximum(terrace, cut)
    h = h + surface_detail(ctx.p, ctx, 977, 31, 2) * p.notchDepth * 0.12 * platform
    submerged = one_minus(smoothstep(p.seaLevel - p.notchWidth, p.seaLevel + p.notchWidth, h))
    return {'field': derivative_field(h, ctx, platform + cliff),
            'outs': {'platform': sat(platform), 'cliff': sat(cliff), 'notch': sat(notch), 'terrace': sat(terrace),
                     'submerged': submerged}}


waveCutPlatform = dict(
    label='Wave-cut Platform', category='terrain', visualFixture='coast',
    doc='Absolute sea-level truncation with a low-tide platform, sea cliff, waterline groove and uplifted benches.',
    params={
        'seaLevel': P.float(0.35, -1, 2),
        'levels': P.int(2, 1, 8, doc='>1 gives an uplifted marine terrace staircase'),
        'uplift': P.float(0.10, 0.002, 0.4, doc='height between successive palaeo-shorelines'),
        'seaward': P.float(0.04, 0, 0.3, doc='gentle seaward gradient of the platform'),
        'cliffHeight': P.float(0.22, 0, 0.8),
        'cliffSharp': P.float(0.6, 0.1, 1, doc='smaller is a more vertical cliff'),
        'notchDepth': P.float(0.008, 0, 0.05, doc='waterline groove; a heightfield cannot represent an undercut'),
        'notchWidth': P.float(0.01, 0.002, 0.06),
        'platformMax': P.float(0.40, 0.01, 1, doc='maximum vertical reach of the seaward platform cut'),
        'irregular': P.float(0.3, 0, 1, doc='plan irregularity of the cliff line, including geos and headlands'),
        'irregFreq': P.float(12, 1, 64, structural=True, periodFreq=True),
    },
    outputs=[mask('platform', 'bare wet rock exposed at low tide'), mask('cliff', 'sea cliffs'),
             mask('notch', 'waterline erosion groove'), mask('terrace', 'uplifted former platforms'),
             mask('submerged', 'ground below modern sea level')],
    apply=_wave_cut_platform)


# --------------------------------------------------------------------------------------------- playa / polje ---

def _playa(f, p, ctx):
    source = H(f)
    apron_width = p.bajadaReach * (1.0 - p.sharpness * 0.92)
    broken = piedmont_break(source, p.level, apron_width)
    excess = np.maximum(source - p.level, 0.0)
    floor = one_minus(smoothstep(p.level - 0.003, p.level + 0.003, source))
    above = gate(source > p.level)
    bajada_mask = above * one_minus(smoothstep(p.bajadaReach * 0.76, p.bajadaReach, excess))
    apron = fan_profile(excess / np.maximum(p.bajadaReach, EPS), p.concavity, 1.0) * p.bajada * bajada_mask
    shoreline = np.exp(-np.power(excess / np.maximum(p.bajadaReach * 0.12, EPS), 2)) * above
    cells = max(4, min(400, js_round(1 / p.polygonSize)))
    cracks = cell_search3(ctx.p, cells, ctx, p.seed, 0.72)
    border = one_minus(smoothstep(0.015, 0.095, cracks['f2'] - cracks['f1'])) * floor
    salt_style = p.style in ('playa', 'saltPan', 'chott')
    crust_mask = (np.abs(surface_detail(ctx.p, ctx, p.seed + 271, min(400, cells * 2), 2)) * floor
                  if salt_style else 0.0)
    ponor = 0.0
    if p.style == 'polje' and p.ponors > 0:
        holes = scatter_cell(ctx.p, p.ponors, ctx, p.seed + 809, 0.82)
        ponor = one_minus(smoothstep(0.05, 0.2, holes.d)) * smoothstep(0.18, 0.82, shoreline)
    relief = apron - border * p.crackDepth + crust_mask * p.crust - ponor * (p.crackDepth + 0.008)
    h = broken.value + relief
    return {'field': derivative_field(h, ctx, floor + bajada_mask),
            'outs': {'floor': floor, 'crust': sat(crust_mask), 'polygons': sat(border), 'bajada': sat(bajada_mask),
                     'shoreline': sat(shoreline), 'ponor': sat(ponor)}}


playa = dict(
    label='Playa / Polje', category='terrain', visualFixture='smooth',
    doc='A level-contour-defined closed floor with an abrupt piedmont break, apron, desiccation network and optional '
        'ponors.',
    params={
        'style': P.enum('playa', ['playa', 'saltPan', 'polje', 'lacustrinePlain', 'chott']),
        'level': P.float(0.46, -1, 2, doc='floor elevation; its outline is the input contour at this level'),
        'sharpness': P.float(0.85, 0, 1, doc='abruptness of the break of slope'),
        'bajada': P.float(0.12, 0, 0.5, doc='alluvial apron rising from the break'),
        'bajadaReach': P.float(0.15, 0.01, 0.8),
        'concavity': P.float(2.5, 0, 8),
        'polygonSize': P.float(0.01, 0.001, 0.1, structural=True, maskable=False, doc='desiccation polygon width'),
        'crackDepth': P.float(0.002, 0, 0.02),
        'crust': P.float(0.001, 0, 0.02, doc='salt-crust micro-relief'),
        'ponors': P.int(0, 0, 8, doc='polje mode: swallow holes at the floor margin'),
        'seed': P.int(0, 0, 65535),
    },
    outputs=[mask('floor', 'flat salt, clay or pasture floor'), mask('crust', 'salt crust'),
             mask('polygons', 'desiccation crack network'), mask('bajada', 'coalescing alluvial apron'),
             mask('shoreline', 'break-of-slope strandline'), mask('ponor', 'karst swallow holes')],
    apply=_playa)


# ---------------------------------------------------------------------------------------- planation surface ---

def _planation_surface(f, p, ctx):
    datum = p.base - p.stripDepth + p.tilt * dot(ctx.p - Vec(0.5, 0.5), axis_vector(p.axis))
    resistance = sat(fbm(ctx.p, p.resistFreq, 4, ctx, p.seed) * 0.5 + 0.5)
    hard = smoothstep(p.coverage - 0.12, p.coverage + 0.12, resistance)
    residual_mask = np.power(hard, p.selectivity)
    plain = one_minus(residual_mask)
    original_relief = np.maximum(H(f) - datum, 0.0)
    relief = original_relief * p.residual * residual_mask
    foot_width = 0.07 - p.piedmont * 0.064
    foot = smoothstep(0.0, foot_width, relief)
    piedmont = ring(relief / np.maximum(foot_width, EPS), 1.0, 0.55) * residual_mask
    detail = surface_detail(ctx.p, ctx, p.seed + 463, 19, 3) * (plain * 0.0015 + residual_mask * 0.006)
    h = datum + relief * foot + detail
    return {'field': derivative_field(h, ctx, residual_mask),
            'outs': {'plain': sat(plain), 'residual': sat(residual_mask), 'piedmont': sat(piedmont)}}


planationSurface = dict(
    label='Planation Surface', category='terrain', visualFixture='detailed-base',
    doc='Selective truncation to a gently sloping datum while resistant rock survives as abrupt-footed residuals.',
    params={
        'base': P.float(0.3, -1, 2, doc='the planation datum'),
        'tilt': P.float(0.05, -0.5, 0.5),
        'axis': P.float(0, 0, 360, structural=True),
        'resistFreq': P.float(5, 1, 32, structural=True, periodFreq=True),
        'selectivity': P.float(2.5, 0.5, 8, doc='higher leaves fewer, sharper residuals'),
        'coverage': P.float(0.55, 0, 1, doc='fraction of the tile planed flat'),
        'residual': P.float(0.9, 0, 1, doc='original relief retained on resistant ground'),
        'piedmont': P.float(0.8, 0, 1, doc='sharpness of the residual foot'),
        'stripDepth': P.float(0, 0, 0.5, doc='lower the datum so residuals grow in relative height'),
        'seed': P.int(0, 0, 65535),
    },
    outputs=[mask('plain', 'planed low-relief surface'), mask('residual', 'inselbergs and monadnocks'),
             mask('piedmont', 'sharp break and debris apron at residual feet')],
    apply=_planation_surface)


# ----------------------------------------------------------------------------------------------- tower karst ---

def _tower_karst(f, p, ctx):
    cell = scatter_cell(ctx.p, p.frequency, ctx, p.seed, p.jitter)
    rnd = cell.random
    radius_vary = mix(one_minus(p.radiusVary), 1.0 + p.radiusVary, rnd.x)
    radius = np.maximum(p.radius * p.frequency * radius_vary, EPS)
    rho = -99.0
    for j in range(int(p.jointSets)):
        angle = rnd.z * TAU + j * TAU / p.jointSets
        rho = np.maximum(rho, dot(cell.delta, Vec(np.cos(angle), np.sin(angle))) / radius)
    body = one_minus(smoothstep(one_minus(p.wallSoft), 1.0, rho))
    flared_rho = rho / (1.0 + p.flare * np.power(one_minus(body), 2))
    body = one_minus(smoothstep(one_minus(p.wallSoft), 1.0, flared_rho))
    active = gate(rnd.w < p.density)
    body = body * active
    tower_height = p.height * mix(one_minus(p.heightVary), 1.0 + p.heightVary, rnd.y)
    notch = 0.0
    if p.benches > 0:
        phase = fract(body * p.benches)
        notch = ring(phase, 0.5, 0.14) * body
    wall = smoothstep(0.04, 0.35, body) * one_minus(smoothstep(0.72, 0.96, body))
    piedmont = ring(flared_rho, 1.04, 0.16) * active
    source = piedmont_break(H(f), p.plainLevel, 0.035).value if has_input(ctx) else p.plainLevel
    detail = surface_detail(ctx.p, ctx, p.seed + 619, 23, 3) * tower_height * 0.018 * wall
    h = (source + tower_height * body - tower_height * 0.025 * notch + tower_height * 0.035 * p.piedmont * piedmont
         + detail)
    return {'field': derivative_field(h, ctx, body),
            'outs': {'tower': sat(body), 'wall': sat(wall), 'notch': sat(notch), 'plain': one_minus(sat(body)),
                     'piedmont': sat(piedmont)}}


towerKarst = dict(
    label='Tower Karst', category='terrain', optionalInput=True,
    doc='Joint-faceted limestone towers with near-vertical walls, solution benches, basal flare and an alluvial '
        'plain.',
    params={
        'frequency': P.float(7, 1, 40, structural=True, periodFreq=True),
        'density': P.float(0.55, 0.05, 1),
        'radius': P.float(0.05, 0.005, 0.3),
        'radiusVary': P.float(0.5, 0, 1),
        'height': P.float(0.35, 0, 1.2),
        'heightVary': P.float(0.4, 0, 1),
        'jointSets': P.int(6, 3, 12, doc='joint-controlled facets; low values read most strongly as karst'),
        'wallSoft': P.float(0.08, 0.01, 0.5, doc='smaller is more vertical'),
        'flare': P.float(0.25, 0, 1, doc='basal flared slope'),
        'benches': P.int(2, 0, 8, doc='solution notches at former water-table levels'),
        'plainLevel': P.float(0.2, -1, 2),
        'piedmont': P.float(0.9, 0, 1),
        'jitter': P.float(0.85, 0, 1),
        'seed': P.int(0, 0, 65535),
    },
    outputs=[mask('tower', 'exposed limestone towers'), mask('wall', 'near-vertical facets'),
             mask('notch', 'solution benches'), mask('plain', 'alluvial floor between towers'),
             mask('piedmont', 'talus and soil around tower feet')],
    apply=_tower_karst)


# --------------------------------------------------------------------------------------------- cockpit karst ---

def _cockpit_karst(f, p, ctx):
    cells = cell_search3(ctx.p, p.frequency, ctx, p.seed, p.jitter,
                         lambda d: metric_distance(p.distanceMetric, d, p.metricMorph))
    cockpit = np.power(sat(1.0 - cells['f1'] / 0.72), p.cockpitPower)
    edge = cells['f2'] - cells['f1']
    divide = one_minus(smoothstep(0.0, p.divideWidth * 0.42, edge))
    third = cells['f3'] - cells['f1']
    junction = divide * one_minus(smoothstep(p.divideWidth * 0.34, p.divideWidth * 0.95, third))
    cone = sat(np.power(divide, p.ridgePower) + junction * p.coneBoost)
    varying_depth = p.depth * mix(one_minus(p.depthVary), 1.0 + p.depthVary, cells['random'].x)
    base = H(f) if has_input(ctx) else 0.3
    detail = surface_detail(ctx.p, ctx, p.seed + 347, 29, 3) * p.crest * 0.025 * cone
    h = (base - varying_depth * cockpit + p.crest * np.power(divide, p.ridgePower) + p.crest * p.coneBoost * junction
         + detail)
    return {'field': derivative_field(h, ctx, cockpit + cone),
            'outs': {'cockpit': sat(cockpit), 'cone': cone, 'divide': sat(divide), 'junction': sat(junction)}}


cockpitKarst = dict(
    label='Cockpit Karst', category='terrain', optionalInput=True,
    doc='A periodic polygonal sink network whose cell divides and triple junctions survive as cone-karst ridges.',
    params={
        'frequency': P.float(12, 2, 64, structural=True, periodFreq=True, doc='cockpits across the tile'),
        'depth': P.float(0.12, 0, 0.6),
        'depthVary': P.float(0.5, 0, 1),
        'cockpitPower': P.float(1.6, 0.5, 4, doc='floor curvature; above 1 gives a pointed sink'),
        'crest': P.float(0.15, 0, 0.6, doc='height of residual cone ridges'),
        'divideWidth': P.float(0.3, 0.02, 1, doc='ridge width; small values coalesce cockpits into uvalas'),
        'ridgePower': P.float(1.4, 0.5, 4),
        'coneBoost': P.float(0.4, 0, 1, doc='extra height at triple-junction cone summits'),
        'distanceMetric': P.enum('euclidianManhattan', ['euclidianManhattan', 'euclidianChebyshev']),
        'metricMorph': P.float(0.25, 0, 1, doc='morph round cockpits toward angular star-shaped plans'),
        'jitter': P.float(0.85, 0, 1),
        'seed': P.int(0, 0, 65535),
    },
    outputs=[mask('cockpit', 'closed soil-filled depressions'), mask('cone', 'residual karst hills'),
             mask('divide', 'ridge network between sinks'), mask('junction', 'bare-rock cone summits')],
    apply=_cockpit_karst)


# ---------------------------------------------------------------------------------------- limestone pavement ---

def _limestone_pavement(f, p, ctx):
    bedding = p.level + p.bedTilt * dot(ctx.p - Vec(0.5, 0.5), axis_vector(p.axis))
    grike = 0.0
    irregularity = one_minus(p.regularity)
    for j in range(int(p.sets)):
        direction = axis_vector(p.jointAngle + j * 90, False)
        warp = fbm(ctx.p, max(1, js_round(p.frequency / 4)), 3, ctx, p.seed + j * 127) * irregularity * 0.34
        phase = dot(ctx.p, direction) * p.frequency + warp + js_mod(p.seed * 0.173 + j * 0.317, 1)
        distance = np.abs(fract(phase) - 0.5) * 2.0
        fissure = one_minus(smoothstep(0.0, p.grikeWidth, distance))
        grike = np.maximum(grike, fissure)
    clint = one_minus(sat(grike))
    karren_signal = np.abs(surface_detail(ctx.p, ctx, p.seed + 541, p.karrenFreq, 3)) * clint
    base = mix(bedding, H(f), 0.18) if has_input(ctx) else bedding
    h = base - p.grikeDepth * np.power(grike, p.grikeSharp) + karren_signal * p.karren * p.grikeDepth * 0.18
    return {'field': derivative_field(h, ctx, grike),
            'outs': {'clint': sat(clint), 'grike': sat(grike), 'karren': sat(karren_signal * p.karren)}}


limestonePavement = dict(
    label='Limestone Pavement', category='terrain', optionalInput=True,
    doc='A near-horizontal limestone bed incised by intersecting parallel joint sets into clints, grikes and karren.',
    params={
        'level': P.float(0.4, -1, 2),
        'bedTilt': P.float(0.01, -0.2, 0.2),
        'axis': P.float(0, 0, 360, structural=True),
        'sets': P.int(2, 1, 4, doc='joint sets; two orthogonal sets gives rectangular clints'),
        'jointAngle': P.float(0, 0, 360, structural=True, doc='snapped; successive sets are 90 degrees apart'),
        'frequency': P.float(28, 4, 200, structural=True, periodFreq=True, doc='fissures across the tile'),
        'grikeWidth': P.float(0.08, 0.01, 0.4, doc='fraction of clint spacing occupied by fissures'),
        'grikeDepth': P.float(0.02, 0, 0.15),
        'grikeSharp': P.float(3, 1, 8, doc='higher gives a more vertical slot wall'),
        'regularity': P.float(0.7, 0, 1, doc='1 is paving-stone regular; 0 is irregular karren'),
        'karren': P.float(0.2, 0, 1, doc='solution flutes on clint tops'),
        'karrenFreq': P.float(90, 8, 400, structural=True, periodFreq=True),
        'seed': P.int(0, 0, 65535),
    },
    outputs=[mask('clint', 'bare limestone slab tops'), mask('grike', 'deep damp fissures'),
             mask('karren', 'solution flutes on exposed slabs')],
    apply=_limestone_pavement)


# ------------------------------------------------------------------------------------------------- bornhardt ---

def _bornhardt(f, p, ctx):
    cell = scatter_cell(ctx.p, p.frequency, ctx, p.seed, 0.82)
    rnd = cell.random
    density = min(1.0, p.count / max(1, p.frequency * p.frequency))
    active = gate(rnd.w < density)
    requested = p.radius * p.frequency * mix(one_minus(p.radiusVary), 1.0 + p.radiusVary, rnd.x)
    radius = 0.48 * one_minus(np.exp(-(requested / 0.48)))
    rho = cell.d / np.maximum(radius, EPS)
    dome = np.power(sat(1.0 - np.power(rho, p.bulge)), 1.0 / p.bulge)
    flared = rho / (1.0 + p.flare * np.power(one_minus(dome), 2))
    dome = np.power(sat(1.0 - np.power(flared, p.bulge)), 1.0 / p.bulge) * active
    ideal_height = p.height * dome
    depth_below = np.maximum(p.height - ideal_height, 0.0)
    shell_phase = np.abs(fract(depth_below / np.maximum(p.sheetSpacing, EPS)) - 0.5) * 2.0
    sheets = one_minus(smoothstep(0.04, 0.3, shell_phase)) * dome
    block_noise = sat(surface_detail(ctx.p, ctx, p.seed + 887, 21, 3) * 0.5 + 0.5)
    corestones = smoothstep(0.54, 0.76, block_noise) * dome * p.weathering
    sheet_cut = p.sheetSpacing * p.sheetDepth * np.power(sheets, p.sheetSharp) * (0.45 + p.weathering)
    weathered = ideal_height * (1.0 - p.weathering * 0.55) + corestones * p.height * p.weathering * 0.28
    piedmont = ring(flared, 1.02, 0.16) * active
    base = piedmont_break(H(f), p.plainLevel, 0.04).value if has_input(ctx) else p.plainLevel
    face_detail = surface_detail(ctx.p, ctx, p.seed + 109, 33, 3) * p.height * 0.012 * dome
    h = base + weathered - sheet_cut + p.height * 0.035 * p.piedmont * piedmont + face_detail
    return {'field': derivative_field(h, ctx, dome),
            'outs': {'dome': sat(dome), 'sheets': sat(sheets), 'corestones': sat(corestones),
                     'piedmont': sat(piedmont), 'plain': one_minus(sat(dome))}}


bornhardt = dict(
    label='Bornhardt', category='terrain', optionalInput=True,
    doc='Abrupt-footed granite domes whose exfoliation sheets evolve toward nubbins, tors and corestone stacks.',
    params={
        'count': P.int(1, 1, 24),
        'frequency': P.float(4, 1, 24, structural=True, periodFreq=True),
        'radius': P.float(0.20, 0.01, 0.5),
        'radiusVary': P.float(0.4, 0, 1),
        'height': P.float(0.40, 0, 1),
        'bulge': P.float(3, 2, 10, doc='superellipse exponent; higher is flatter-crowned'),
        'sheetSpacing': P.float(0.03, 0.003, 0.2, doc='exfoliation-shell spacing measured into the rock'),
        'sheetDepth': P.float(0.15, 0, 1, doc='cut depth as a fraction of shell spacing'),
        'sheetSharp': P.float(2, 0.5, 6),
        'weathering': P.float(0.2, 0, 1, doc='0 intact dome, 0.5 nubbin, 1 tor or castle koppie'),
        'flare': P.float(0.2, 0, 1, doc='basal flared slope'),
        'plainLevel': P.float(0.25, -1, 2),
        'piedmont': P.float(0.85, 0, 1),
        'seed': P.int(0, 0, 65535),
    },
    outputs=[mask('dome', 'bare exfoliating rock'), mask('sheets', 'exfoliation-shell edges'),
             mask('corestones', 'weathered tor blocks'), mask('piedmont', 'debris ring at the foot'),
             mask('plain', 'low plain surrounding the residuals')],
    apply=_bornhardt)


# -------------------------------------------------------------------------------------------------- badlands ---

def _badlands_snap(p, tile, snap_freq):
    t = tile.x if tile.x > 0 else tile.y
    if not (t > 0):
        return {'params': p, 'notes': []}
    wanted = p['drainageDensity'] * p['worldSize']
    got = snap_freq(wanted, t)
    if abs(wanted - got) < 1e-9:
        return {'params': p, 'notes': []}
    density = got / p['worldSize']
    q = dict(p)
    q['drainageDensity'] = density
    return {'params': q, 'notes': [
        f"drainage density {p['drainageDensity']:.3f} at {p['worldSize']:.3f} km gives {wanted * t:.3f} cells; "
        f"snapped to {density:.6f} ({js_round(got * t)} cells)"]}


def _badlands(f, p, ctx):
    frequency = max(2, js_round(p.drainageDensity * p.worldSize))
    ef = max(1, js_round(p.escarpFreq))
    lf = fbm(ctx.p, ef, 3, ctx, p.seed + 401)
    esc = smoothstep(0.02, 0.3, lf)
    upland = esc * p.reliefHeight
    face = smoothstep(-0.06, 0.1, lf) * one_minus(smoothstep(0.26, 0.46, lf))
    carve = face * 0.9 + esc * 0.04 + 0.02
    ridge_signal = sat(ridged(ctx.p, frequency, p.octaves, ctx, p.seed) * 0.5 + 0.5)
    interfluve = np.power(ridge_signal, p.sharpness)
    channel = np.power(one_minus(interfluve), p.incisionPower)
    cap_h = H(f) + upland
    caprock = one_minus(smoothstep(p.capThickness, p.capThickness * 2.0, np.abs(cap_h - p.capLevel)))
    protection = one_minus(caprock * p.capStrength)
    column = caprock * smoothstep(0.72, 0.94, interfluve) * face
    bands = np.sin(cap_h * p.strataBands * TAU) * 0.5 + 0.5
    band_relief = (bands - 0.5) * p.strata * 0.004 * interfluve * (carve * 1.6)
    mineral = (surface_detail(ctx.p, ctx, p.seed + 701, max(5, js_round(frequency / 3)), 3) * p.depth * 0.018
               * interfluve * (carve + 0.2))
    h = cap_h - p.depth * channel * protection * carve * 2.2 + band_relief + mineral
    return {'field': derivative_field(h, ctx, (channel + interfluve) * (face + 0.1)),
            'outs': {'channel': sat(channel * (carve * 1.8)), 'interfluve': sat(interfluve * (face + 0.15)),
                     'caprock': sat(caprock * esc), 'column': sat(column), 'bands': sat(bands)}}


badlands = dict(
    label='Badlands', category='terrain', visualFixture='smooth',
    doc='Scale-derived high-density rills cut soft strata while resistant caprock preserves buttes and vertical-sided '
        'columns.',
    params={
        'drainageDensity': P.float(50, 20, 500, unit='km/km²', structural=True, maskable=False,
                                   doc='measured badlands span 48–464 kilometres of channel per square kilometre'),
        'worldSize': P.float(1, 0.1, 200, unit='km', structural=True, maskable=False,
                             doc='kilometres across the tile; combines with drainage density to set the lattice'),
        'depth': P.float(0.24, 0, 0.6),
        'octaves': P.int(5, 1, 9),
        'sharpness': P.float(1.8, 0.5, 4, doc='higher gives sharper interfluves'),
        'incisionPower': P.float(1.4, 0.5, 4),
        'capLevel': P.float(0.55, -1, 2, doc='resistant caprock-bed elevation'),
        'capThickness': P.float(0.03, 0, 0.2),
        'capStrength': P.float(0.9, 0, 1, doc='how completely caprock resists incision'),
        'strata': P.float(0.4, 0, 1, doc='stratigraphic relief banding through the section'),
        'strataBands': P.float(30, 2, 200),
        'reliefHeight': P.float(0.32, 0, 1,
                                doc='escarpment relief between the prairie upland and the lower plain'),
        'escarpFreq': P.float(2, 1, 8, structural=True, periodFreq=True,
                              doc='scale of the escarpment front and its outliers'),
        'seed': P.int(0, 0, 65535),
    },
    outputs=[mask('channel', 'rill and gully floors'), mask('interfluve', 'short sharp ridges'),
             mask('caprock', 'resistant flat tops'), mask('column', 'vertical-sided hoodoo remnants'),
             mask('bands', 'stratigraphic section bands')],
    snap=_badlands_snap, apply=_badlands)


# ------------------------------------------------------------------------------------------ patterned ground ---

def _patterned_ground(f, p, ctx):
    resolution = max(1, ctx.resolution if ctx.resolution is not None else 1024)
    hf = H(f)
    screen_gradient = Vec(dfdx(hf), dfdy(hf)) * resolution
    slope = length(screen_gradient)
    uphill = screen_gradient / np.maximum(slope, EPS)
    downhill = -uphill
    degrees = np.arctan(slope) * (180 / math.pi)
    lower = np.minimum(p.polygonMax, p.stripeMin)
    upper = np.maximum(p.polygonMax, p.stripeMin)
    stripe_morph = smoothstep(lower, upper, degrees)

    def metric(raw):
        shifted = raw - downhill * p.lobeCreep * stripe_morph * 0.18
        along = dot(shifted, downhill)
        stretched = shifted + downhill * along * stripe_morph * (p.stretch - 1.0)
        return length(stretched)

    cells = cell_search3(ctx.p, p.frequency, ctx, p.seed, p.jitter, metric)
    borders = one_minus(smoothstep(0.015, 0.12, cells['f2'] - cells['f1']))
    centres = one_minus(smoothstep(0.12, 0.55, cells['f1']))
    front_coord = dot(cells['delta'], downhill)
    lobe_band = smoothstep(0.08, 0.24, front_coord) * one_minus(smoothstep(0.24, 0.43, front_coord))
    lobe_front = lobe_band * stripe_morph * p.lobeCreep
    sorted_relief = borders * p.borderRaise - centres * p.centreLower + lobe_front * 0.65
    frost = surface_detail(ctx.p, ctx, p.seed + 257, max(5, js_round(p.frequency / 2)), 2) * centres * 0.08
    relief = (sorted_relief + frost) * p.amplitude
    relief_gradient = Vec(dfdx(relief), dfdy(relief)) * resolution
    return {'field': field(H(f) + relief, G(f) + relief_gradient, borders),
            'outs': {'borders': sat(borders), 'centres': sat(centres), 'stripes': sat(stripe_morph * borders),
                     'lobeFront': sat(lobe_front)}}


patternedGround = dict(
    label='Patterned Ground', category='terrain', visualFixture='slope',
    doc='Slope-controlled sorted cells that morph from circles and polygons through steps into downslope stripes and '
        'lobes.',
    params={
        'frequency': P.float(14, 4, 400, structural=True, periodFreq=True, doc='cells across the tile'),
        'amplitude': P.float(0.055, 0, 0.06, doc='centimetre-to-metre relief'),
        'polygonMax': P.float(2, 0, 10, unit='deg', doc='below this slope the pattern is polygonal'),
        'stripeMin': P.float(7, 1, 25, unit='deg',
                             doc='above this slope it is striped; the observed transition spans 2–7 degrees'),
        'stretch': P.float(6, 1, 30, doc='cell elongation in the stripe regime'),
        'borderRaise': P.float(0.7, 0, 1, doc='coarse clasts raised on cell borders'),
        'centreLower': P.float(0.5, 0, 1, doc='fines settling in cell centres'),
        'lobeCreep': P.float(0, 0, 1, doc='downslope bulge that turns steps into solifluction lobes'),
        'jitter': P.float(0.7, 0, 1),
        'seed': P.int(0, 0, 65535),
    },
    outputs=[mask('borders', 'coarse sorted clasts'), mask('centres', 'fine vegetated cell centres'),
             mask('stripes', 'slope-aligned stripe regime'), mask('lobeFront', 'bulging solifluction toe')],
    apply=_patterned_ground)


WAVE3_LANDFORMS = {
    'terraceStair': terraceStair,
    'waveCutPlatform': waveCutPlatform,
    'playa': playa,
    'planationSurface': planationSurface,
    'towerKarst': towerKarst,
    'cockpitKarst': cockpitKarst,
    'limestonePavement': limestonePavement,
    'bornhardt': bornhardt,
    'badlands': badlands,
    'patternedGround': patternedGround,
}
