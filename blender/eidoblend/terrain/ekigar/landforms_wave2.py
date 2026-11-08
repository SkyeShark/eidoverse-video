"""Landform library, wave 2 (src/core/landforms_wave2.js): directed, linear and tectonic landforms.

Glacial Trough, Meander Belt, Fault Scarp, Graben, Dip Slope, Esker, Moraine Set, Streamform Field, Ocean Ridge and
Inverted Channel: each built in a period-closing directed frame (axis_frame), so channels and ridges meet themselves
at the tile seam.
"""
from __future__ import annotations

import math

import numpy as np

from ._tsl import Vec, clamp, mix, step01, dot, length, fract, sat
from .landform_shared import (P, TAU, EPS, H, G, field, sstep as smoothstep, wrapped_delta, sampled_add, fbm, ridged,
                              scatter_cell, ring, fan_profile, axis_frame, asym_ridge, bench_stack, snapped_axis,
                              surface_detail, js_round, js_mod)


def mask(name, doc):
    return {'name': name, 'type': 'mask', 'doc': doc}


def gate(cond):
    return step01(cond)


def one_minus(v):
    return 1.0 - v


def periodic_distance(x):
    f = fract(x)
    return np.minimum(f, one_minus(f))


def unit_axis(degrees):
    a = snapped_axis(degrees)
    n = math.hypot(a[0], a[1]) or 1.0
    return [a[0] / n, a[1] / n]


def reduced_base(f, added, amount):
    return field(H(added) - H(f) * amount, G(added) - G(f) * amount, added.w)


# --------------------------------------------------------------------------------------------- glacial trough ---

def _glacial_trough(f, p, ctx):
    def features(q):
        frame = axis_frame(q, p.direction, p.bends, p.sinuosity * 0.14, p.seed)
        w = np.abs(frame.w) / np.maximum(p.halfWidth, EPS)
        inside = one_minus(smoothstep(0.98, 1.015, w))
        floor_mask = one_minus(smoothstep(p.floorFrac - 0.018, p.floorFrac + 0.028, w))
        wall_coord = sat((w - p.floorFrac) / np.maximum(one_minus(p.floorFrac), EPS))
        wall = smoothstep(0.02, 0.14, wall_coord) * one_minus(smoothstep(0.82, 1.02, wall_coord))
        trimline = ring(w, 0.98, 0.055)
        basin_wave = np.sin(frame.along * (TAU * p.basins) + p.seed * 0.37) * 0.5 + 0.5
        depth = p.depth * (1.0 + p.overdeepen * (basin_wave - 0.35))
        cross = one_minus(np.power(wall_coord, p.profilePower)) * inside
        hanging = 0.0
        tributary_cut = 0.0
        if p.tributaries > 0:
            phase = periodic_distance(frame.along * p.tributaries + p.seed * 0.173)
            branch_width = p.halfWidth * p.tribWidth * 0.52
            branch = one_minus(smoothstep(branch_width * 0.55, branch_width, phase))
            aw = np.abs(frame.w)
            mouth = (smoothstep(p.halfWidth * 0.72, p.halfWidth * 1.05, aw)
                     * one_minus(smoothstep(p.halfWidth * 1.05, p.halfWidth * 2.25, aw)))
            hanging = branch * mouth
            tributary_cut = hanging * p.depth * one_minus(p.hangFrac)
        grooves = ridged(q, 17, 3, ctx, p.seed + 211) * wall * p.depth * 0.025
        return {'height': -depth * cross - tributary_cut + grooves, 'inside': inside, 'floor': floor_mask * inside,
                'wall': wall, 'trimline': trimline, 'spur': wall * smoothstep(0.74, 0.96, wall_coord),
                'hanging': hanging}

    z = features(ctx.p)
    added = sampled_add(f, ctx, lambda q: features(q)['height'], lambda q, h: z['wall'] + z['floor'] + z['hanging'])
    truncate = z['inside'] * one_minus(smoothstep(0.0, p.spurBlend, one_minus(z['inside'])))
    return {'field': reduced_base(f, added, truncate),
            'outs': {k: z[k] for k in ('floor', 'wall', 'trimline', 'spur', 'hanging')}}


glacialTrough = dict(
    label='Glacial Trough', category='terrain', optionalInput=True,
    doc='A parabolic U-shaped valley with a broad floor, truncated spurs, hanging tributaries and over-deepened '
        'basins.',
    params={
        'direction': P.float(0, 0, 360, structural=True, doc='strike, snapped to a lattice axis'),
        'halfWidth': P.float(0.18, 0.02, 0.6), 'depth': P.float(0.22, 0, 0.9),
        'profilePower': P.float(2, 1.1, 4, doc='2 is the parabolic U; toward 1 becomes a V'),
        'floorFrac': P.float(0.25, 0, 0.8, doc='flat floor as a fraction of half-width'),
        'bends': P.int(2, 1, 8, doc='whole bends along strike'),
        'sinuosity': P.float(0.25, 0, 1),
        'spurBlend': P.float(0.12, 0.01, 0.6, doc='small values truncate incoming spurs squarely'),
        'overdeepen': P.float(0.3, 0, 1, doc='along-strike basin and rock-bar alternation'),
        'basins': P.int(3, 1, 10), 'tributaries': P.int(2, 0, 8),
        'hangFrac': P.float(0.45, 0, 0.9, doc='height of tributaries above the trunk floor'),
        'tribWidth': P.float(0.35, 0.1, 1, doc='tributary width as a fraction of the trunk'),
        'seed': P.int(0, 0, 65535),
    },
    outputs=[mask('floor', 'wide glacial floor'), mask('wall', 'scoured trough walls'),
             mask('trimline', 'upper scour boundary'), mask('spur', 'truncated spur ends'),
             mask('hanging', 'hanging-valley mouths')],
    apply=_glacial_trough)


# ----------------------------------------------------------------------------------------------- meander belt ---

def _meander_belt(f, p, ctx):
    def features(q):
        frame = axis_frame(q, p.direction, p.meanders, p.sinuosity * 0.18, p.seed)
        aw = np.abs(frame.w)
        phase = frame.along * (TAU * p.meanders) + p.seed * 0.754877666
        curvature = -np.sin(phase)
        outer = gate(frame.w * curvature > 0)
        inner = one_minus(outer)
        bend = np.abs(curvature)
        cw = p.channelWidth
        channel = one_minus(smoothstep(cw * 0.62, cw, aw))
        bank_band = (smoothstep(cw * 0.72, cw, aw)
                     * one_minus(smoothstep(cw, cw + np.maximum(p.cutBank, p.pointBar), aw)))
        cut_bank = bank_band * outer * one_minus(smoothstep(cw + p.cutBank * 0.72, cw + p.cutBank, aw))
        point_bar = bank_band * inner * one_minus(smoothstep(cw + p.pointBar * 0.76, cw + p.pointBar, aw))
        levee = ring(aw, cw + p.leveeWidth * 0.58, p.leveeWidth * 0.72)
        belt = one_minus(smoothstep(p.beltWidth * 0.82, p.beltWidth, aw))
        behind = smoothstep(cw + p.leveeWidth, cw + p.leveeWidth * 2.4, aw) * belt
        backswamp = behind * one_minus(levee)
        scrolls = 0.0
        if p.nScrolls > 0:
            scroll_wave = np.sin(aw / np.maximum(p.pointBar, EPS) * (TAU * p.nScrolls) + bend * 2.1) * 0.5 + 0.5
            scrolls = point_bar * smoothstep(0.58, 0.88, scroll_wave)
        oxbow = 0.0
        if p.oxbows > 0:
            selected = one_minus(smoothstep(0.13, 0.28, periodic_distance(frame.along * p.oxbows + p.seed * 0.311)))
            loop_band = ring(aw, cw + p.pointBar * 0.72, np.maximum(cw * 0.6, 0.006))
            oxbow = loop_band * inner * smoothstep(0.62, 0.9, bend) * selected
        pool_depth = p.channelDepth * (1.0 + p.apexDeepen * bend)
        channel_cut = -pool_depth * channel
        bars = p.channelDepth * 0.42 * point_bar + p.scrollAmp * scrolls
        confinement = smoothstep(p.beltWidth * 0.54, p.beltWidth, aw) * p.entrenchment * p.channelDepth * 2.4
        floodplain = p.floodLevel * 0.06 * belt * one_minus(p.entrenchment)
        wetlands = -(p.leveeHeight * 0.55 * backswamp)
        texture = surface_detail(q, ctx, p.seed + 407, 23, 3) * (
            p.channelDepth * 0.035 * channel + p.leveeHeight * 0.12 * levee + p.scrollAmp * 0.22 * point_bar)
        return {'height': (channel_cut + bars + p.leveeHeight * levee + confinement + floodplain + wetlands
                           - p.channelDepth * 0.45 * oxbow + texture),
                'channel': channel, 'cutBank': cut_bank, 'pointBar': point_bar, 'scrolls': scrolls, 'levee': levee,
                'backswamp': backswamp, 'oxbow': oxbow, 'belt': belt}

    z = features(ctx.p)
    return {'field': sampled_add(f, ctx, lambda q: features(q)['height'], lambda q, h: z['belt']),
            'outs': {k: z[k] for k in ('channel', 'cutBank', 'pointBar', 'scrolls', 'levee', 'backswamp', 'oxbow')}}


meanderBelt = dict(
    label='Meander Belt', category='terrain', optionalInput=True,
    doc='A curvature-aware river belt with asymmetric cut banks, point bars, levees, scrolls, backswamps and '
        'abandoned loops.',
    params={
        'direction': P.float(0, 0, 360, structural=True),
        'meanders': P.int(3, 1, 10, doc='whole meanders across the tile'),
        'sinuosity': P.float(0.5, 0, 1, doc='maps to sinuosity index approximately 1 to 4'),
        'beltWidth': P.float(0.3, 0.03, 0.9), 'channelWidth': P.float(0.04, 0.004, 0.3),
        'channelDepth': P.float(0.05, 0, 0.4),
        'cutBank': P.float(0.06, 0.005, 0.4, doc='outer-bank width'),
        'pointBar': P.float(0.22, 0.01, 0.9, doc='inner-bank width'),
        'apexDeepen': P.float(0.5, 0, 1, doc='extra depth at bend apices'),
        'leveeHeight': P.float(0.01, 0, 0.1), 'leveeWidth': P.float(0.03, 0.005, 0.2),
        'floodLevel': P.float(0.4, -1, 2),
        'entrenchment': P.float(0, 0, 1, doc='0 is a floodplain; 1 is entrenched in rock'),
        'oxbows': P.int(1, 0, 6), 'scrollAmp': P.float(0.008, 0, 0.06),
        'nScrolls': P.int(5, 0, 20), 'seed': P.int(0, 0, 65535),
    },
    outputs=[mask('channel', 'wetted channel bed'), mask('cutBank', 'eroding outer banks'),
             mask('pointBar', 'depositional inner bars'), mask('scrolls', 'ridge and swale arcs'),
             mask('levee', 'natural levee crests'), mask('backswamp', 'low ground behind levees'),
             mask('oxbow', 'abandoned channel loops')],
    apply=_meander_belt)


# ------------------------------------------------------------------------------------------------ fault scarp ---

def _fault_scarp(f, p, ctx):
    def features(q):
        frame = axis_frame(q, p.direction, p.bends, p.sinuosity * 0.11, p.seed)
        segment = np.floor(fract(frame.along) * p.segments)
        offset = np.sin(segment * (TAU / p.segments) + p.seed * 0.21) * p.stepOver
        w = frame.w - offset
        w = w - np.floor(w + 0.5)
        aw = np.abs(w)
        remain = one_minus(p.maturity)
        free_angle = smoothstep(30.0, 89.0, p.freeAngle)
        repose_angle = smoothstep(20.0, 45.0, p.reposeAngle)
        wash_angle = smoothstep(2.0, 25.0, p.washAngle)
        free_width = np.maximum(p.scarpWidth * mix(0.72, 0.14, free_angle) * (0.45 + p.freeFrac * remain), EPS)
        debris_width = p.scarpWidth * mix(2.2, 0.82, repose_angle) * (0.75 + p.maturity * 1.3)
        wash_width = p.scarpWidth * mix(6.4, 2.0, wash_angle) * (0.72 + p.maturity * 1.2)
        sharp = smoothstep(-free_width, free_width, w)
        degraded = (smoothstep(-wash_width, 0.0, w) * 0.18 + smoothstep(-debris_width, debris_width, w) * 0.43
                    + smoothstep(-free_width, free_width, w) * 0.39)
        face = one_minus(smoothstep(free_width * 0.38, free_width, aw))
        lower = gate(w < 0)
        debris = (smoothstep(free_width * 0.7, debris_width * 0.72, aw)
                  * one_minus(smoothstep(debris_width * 0.72, debris_width, aw)) * lower)
        wash = (smoothstep(debris_width * 0.65, wash_width * 0.72, aw)
                * one_minus(smoothstep(wash_width * 0.72, wash_width, aw)) * lower)
        incision = 0.0
        facet = 0.0
        if p.facets > 0:
            incision = np.power(one_minus(np.abs(np.sin(frame.along * (math.pi * p.facets) + p.seed * 0.39))), 2.2)
            up_face = smoothstep(-wash_width, free_width, w) * one_minus(smoothstep(free_width, wash_width, w))
            facet = up_face * one_minus(incision)
        base_step = mix(sharp, degraded, p.maturity) * p.throw
        height_on_face = sat((w + wash_width) / np.maximum(wash_width + free_width, EPS))
        facet_cut = incision * height_on_face * p.throw * p.facetDepth * 0.58
        detail = surface_detail(q, ctx, p.seed + 521, 29, 3) * (p.throw * (face * 0.022 + debris * 0.055
                                                                           + wash * 0.026))
        return {'height': base_step - facet_cut + detail, 'face': face, 'debris': debris, 'wash': wash,
                'facet': facet, 'footwall': lower, 'hangingwall': one_minus(lower)}

    z = features(ctx.p)
    return {'field': sampled_add(f, ctx, lambda q: features(q)['height'],
                                 lambda q, h: z['face'] + z['debris'] + z['wash']),
            'outs': {'freeFace': z['face'], 'debris': z['debris'], 'wash': z['wash'], 'facet': z['facet'],
                     'footwall': z['footwall'], 'hangingwall': z['hangingwall']}}


faultScarp = dict(
    label='Fault Scarp', category='terrain', optionalInput=True,
    doc='A segmented tectonic step with fresh free face, debris and wash slopes plus drainage-cut triangular '
        'facets.',
    params={
        'direction': P.float(0, 0, 360, structural=True),
        'throw': P.float(0.12, 0, 0.8, doc='vertical offset across the fault'),
        'scarpWidth': P.float(0.03, 0.002, 0.3),
        'freeAngle': P.float(70, 30, 89, unit='deg', doc='bare free-face angle'),
        'freeFrac': P.float(0.3, 0, 1),
        'reposeAngle': P.float(33, 20, 45, unit='deg', doc='debris-slope angle'),
        'washAngle': P.float(8, 2, 25, unit='deg'),
        'maturity': P.float(0.3, 0, 1, doc='0 fresh; 1 degraded to a wash slope'),
        'bends': P.int(2, 1, 8), 'sinuosity': P.float(0.15, 0, 1),
        'segments': P.int(1, 1, 8, doc='en echelon segments'),
        'stepOver': P.float(0, 0, 0.3), 'facets': P.int(0, 0, 24),
        'facetDepth': P.float(0.4, 0, 1), 'seed': P.int(0, 0, 65535),
    },
    outputs=[mask('freeFace', 'bare fault face'), mask('debris', 'talus apron'),
             mask('wash', 'colluvial wash slope'), mask('facet', 'triangular remnants'),
             mask('footwall', 'lower fault block'), mask('hangingwall', 'upper fault block')],
    apply=_fault_scarp)


# ----------------------------------------------------------------------------------------------------- graben ---

def _graben(f, p, ctx):
    def features(q):
        frame = axis_frame(q, p.direction, p.bends, p.sinuosity * 0.05, p.seed)
        b = fract(frame.w * p.blocks + 0.5)
        local = b - 0.5
        dist = np.abs(local)
        half = p.grabenFrac * 0.5
        floor_mask = one_minus(smoothstep(half - p.faultWidth, half, dist))
        scarp = ring(dist, half, np.maximum(p.faultWidth, 0.006))
        if p.polarityFlips > 0:
            polarity = np.where(np.sin(frame.along * (TAU * p.polarityFlips) + p.seed * 0.17) > 0, 1.0, -1.0)
        else:
            polarity = 1.0
        master = ring(local, half * polarity, np.maximum(p.faultWidth, 0.006)) if p.style == 'halfGraben' else 0.0
        if p.style == 'halfGraben':
            floor_tilt = sat((local * polarity + half) / np.maximum(p.grabenFrac, EPS))
            relief = -p.throw * floor_mask * one_minus(p.tilt * floor_tilt * 0.68)
        elif p.style == 'horstGraben':
            relief = -p.throw * floor_mask + p.throw * 0.42 * one_minus(floor_mask)
        else:
            relief = -p.throw * floor_mask
        if p.style == 'pullApart':
            overlap = smoothstep(0.3, 0.78, np.sin(frame.along * (TAU * 2) + p.seed * 0.47) * 0.5 + 0.5)
            relief = relief - p.throw * floor_mask * overlap
        top = one_minus(floor_mask) * one_minus(scarp)
        detail = surface_detail(q, ctx, p.seed + 613, 17, 4) * (p.throw * (floor_mask * 0.018 + scarp * 0.045
                                                                           + top * 0.014))
        return {'height': relief + detail, 'floor': floor_mask, 'scarp': scarp, 'footwall': top, 'master': master}

    z = features(ctx.p)
    added = sampled_add(f, ctx, lambda q: features(q)['height'], lambda q, h: z['floor'] + z['scarp'])
    bury = z['floor'] * one_minus(p.floorFill)
    return {'field': reduced_base(f, added, bury),
            'outs': {k: z[k] for k in ('floor', 'scarp', 'footwall', 'master')}}


graben = dict(
    label='Graben', category='terrain', optionalInput=True,
    doc='Periodic rift blocks with paired inward-facing scarps, half-graben polarity changes, horsts and pull-apart '
        'basins.',
    params={
        'style': P.enum('graben', ['graben', 'halfGraben', 'horstGraben', 'pullApart']),
        'direction': P.float(0, 0, 360, structural=True),
        'blocks': P.int(1, 1, 16, doc='fault blocks across the tile'),
        'grabenFrac': P.float(0.5, 0.1, 0.9), 'throw': P.float(0.15, 0, 0.8),
        'faultWidth': P.float(0.06, 0.005, 0.4, doc='scarp width as a fraction of a block'),
        'tilt': P.float(0.5, 0, 1, doc='half-graben floor tilt'),
        'polarityFlips': P.int(2, 0, 8), 'bends': P.int(1, 1, 6),
        'sinuosity': P.float(0.1, 0, 1),
        'floorFill': P.float(0.3, 0, 1, doc='share of incoming relief retained on the floor'),
        'seed': P.int(0, 0, 65535),
    },
    outputs=[mask('floor', 'rift-floor sediment trap'), mask('scarp', 'bounding normal faults'),
             mask('footwall', 'upthrown block tops'), mask('master', 'master fault of a half-graben')],
    apply=_graben)


# -------------------------------------------------------------------------------------------------- dip slope ---

def _dip_slope(f, p, ctx):
    def features(q):
        frame = axis_frame(q, p.direction, p.bends, p.sinuosity * 0.045, p.seed)
        local = fract(frame.w * p.ridges + 0.5) - 0.5
        dip_t = smoothstep(2.0, 90.0, p.dip)
        scarp_t = smoothstep(20.0, 85.0, p.scarpAngle)
        gentle_width = mix(0.47, 0.13, dip_t)
        steep_width = mix(0.22, 0.075, scarp_t)
        analytic = asym_ridge(local, steepWidth=steep_width, gentleWidth=gentle_width, steepPower=1.22,
                              gentlePower=1.02)
        right = gate(local >= 0)
        left = one_minus(right)
        ridge = analytic
        tread_mask = 0.0
        if p.benches > 0:
            coord = sat(local / np.maximum(gentle_width, EPS))
            steps = bench_stack(coord, p.benches, 0.62)
            stepped = one_minus(steps.value) * right + analytic * left
            ridge = mix(analytic, stepped, right * 0.72)
            tread_mask = steps.tread * right * analytic
        scarp_mask = analytic * left
        backslope = analytic * right
        incision = 0.0
        flatiron = 0.0
        if p.flatirons > 0:
            incision = np.power(one_minus(np.abs(np.sin(frame.along * (math.pi * p.flatirons) + p.seed * 0.43))), 2.4)
            flatiron = scarp_mask * one_minus(incision)
        crest = smoothstep(0.66, 0.9, ridge)
        strike = ring(np.abs(local), 0.0, np.maximum(steep_width * 0.22, 0.012))
        facets = incision * scarp_mask * p.flatironDepth * p.bedThickness * 0.62
        detail = surface_detail(q, ctx, p.seed + 733, 21, 3) * (p.bedThickness * (
            backslope * 0.018 + scarp_mask * 0.038 + tread_mask * 0.012))
        return {'height': ridge * p.bedThickness - facets + detail, 'dipSlope': backslope, 'scarp': scarp_mask,
                'crest': crest, 'flatiron': flatiron, 'strike': strike}

    z = features(ctx.p)
    return {'field': sampled_add(f, ctx, lambda q: features(q)['height'], lambda q, h: z['dipSlope'] + z['scarp']),
            'outs': {k: z[k] for k in ('dipSlope', 'scarp', 'crest', 'flatiron', 'strike')}}


dipSlope = dict(
    label='Dip Slope', category='terrain', optionalInput=True,
    doc='Asymmetric strike ridges spanning cuesta, homoclinal ridge and hogback forms with structural benches and '
        'flatirons.',
    params={
        'direction': P.float(0, 0, 360, structural=True, doc='strike, snapped to a lattice axis'),
        'dip': P.float(12, 2, 90, unit='deg', doc='bed dip; low is cuesta, high is hogback'),
        'scarpAngle': P.float(55, 20, 85, unit='deg'),
        'bedThickness': P.float(0.12, 0.01, 0.6),
        'ridges': P.int(3, 1, 16, doc='parallel strike ridges across the tile'),
        'bends': P.int(2, 1, 8), 'sinuosity': P.float(0.2, 0, 1),
        'benches': P.int(0, 0, 10), 'flatirons': P.int(0, 0, 24),
        'flatironDepth': P.float(0.4, 0, 1), 'seed': P.int(0, 0, 65535),
    },
    outputs=[mask('dipSlope', 'bedding-plane backslope'), mask('scarp', 'steep frontslope'),
             mask('crest', 'ridge crest'), mask('flatiron', 'triangular scarp remnants'),
             mask('strike', 'resistant-bed outcrop belt')],
    apply=_dip_slope)


# ------------------------------------------------------------------------------------------------------ esker ---

def _esker(f, p, ctx):
    axis = unit_axis(p.direction)
    side = [-axis[1], axis[0]]
    e = 1.0 / max(512, ctx.resolution if ctx.resolution is not None else 512)
    low = H(ctx.sample_input(side[0] * -e, side[1] * -e))
    high = H(ctx.sample_input(side[0] * e, side[1] * e))
    gradient = (high - low) / (2 * e)
    seek = -clamp(gradient * p.width * 0.32, p.width * -1.5, p.width * 1.5) * p.lowSeek

    def features(q):
        frame = axis_frame(q, p.direction, p.bends, p.sinuosity * 0.15, p.seed)
        local = (fract((frame.w - seek) * p.count + 0.5) - 0.5) / p.count
        r = np.abs(local) / np.maximum(p.width, EPS)
        cross = np.power(sat(one_minus(r)), p.crestSharp)
        amplitude = 1.0
        gaps = 0.0
        if p.beads > 0:
            beads = np.cos(frame.along * (TAU * p.beads) + p.seed * 0.63) * 0.5 + 0.5
            amplitude = np.power(np.maximum(one_minus(p.beadDepth * beads), 0.001), 1.7)
            gaps = one_minus(smoothstep(0.04, 0.3, amplitude)) * cross
        knobby = fbm(q, p.knobFreq, 3, ctx, p.seed + 809) * p.knob * 0.24
        body = cross * amplitude * np.maximum(0.12, 1.0 + knobby)
        crest = smoothstep(0.62, 0.9, cross) * amplitude
        flank = smoothstep(0.08, 0.72, cross) * one_minus(smoothstep(0.72, 0.94, cross)) * amplitude
        texture = surface_detail(q, ctx, p.seed + 857, 31, 3) * p.height * (flank * 0.045 + crest * 0.018)
        return {'height': body * p.height + texture, 'crest': crest, 'flank': flank, 'gaps': gaps}

    z = features(ctx.p)
    return {'field': sampled_add(f, ctx, lambda q: features(q)['height'], lambda q, h: z['crest'] + z['flank']),
            'outs': {'crest': z['crest'], 'flank': z['flank'], 'gaps': z['gaps']}}


esker = dict(
    label='Esker', category='terrain', optionalInput=True, needsResample=True,
    doc='Sinuous sharp- or broad-crested gravel ridges with knobby beading, true gaps and low-ground seeking.',
    params={
        'direction': P.float(0, 0, 360, structural=True),
        'height': P.float(0.10, 0, 0.4), 'width': P.float(0.04, 0.002, 0.15),
        'crestSharp': P.float(0.7, 0.3, 3, doc='below 1 is sharp-crested; above 1 broad-crested'),
        'bends': P.int(4, 1, 12), 'sinuosity': P.float(0.6, 0, 1),
        'beads': P.int(6, 0, 24), 'beadDepth': P.float(0.5, 0, 1, doc='1 opens gaps'),
        'knob': P.float(0.2, 0, 1),
        'knobFreq': P.float(24, 2, 96, structural=True, periodFreq=True),
        'lowSeek': P.float(0.3, 0, 1, doc='bias toward incoming terrain lows'),
        'count': P.int(1, 1, 6), 'seed': P.int(0, 0, 65535),
    },
    outputs=[mask('crest', 'well-sorted gravel crest'), mask('flank', 'steep ridge flanks'),
             mask('gaps', 'breaks between ridge segments')],
    apply=_esker)


# ------------------------------------------------------------------------------------------------ moraine set ---

def _moraine_set(f, p, ctx):
    comp = p.components

    def features(q):
        frame = axis_frame(q, p.flowDirection, 2, 0.025, p.seed)
        inner_t = smoothstep(30.0, 85.0, p.innerAngle)
        outer_t = smoothstep(20.0, 45.0, p.outerAngle)
        inner_width = mix(p.ridgeWidth * 1.35, p.ridgeWidth * 0.42, inner_t)
        outer_width = mix(p.ridgeWidth * 1.5, p.ridgeWidth * 0.82, outer_t)
        lateral = medial = terminal = rogen = 0.0
        if comp in ('lateral', 'all'):
            a = asym_ridge(frame.w - p.lateralOffset, steepWidth=inner_width, gentleWidth=outer_width,
                           steepPower=1.05, gentlePower=1.55)
            b = asym_ridge(-(frame.w + p.lateralOffset), steepWidth=inner_width, gentleWidth=outer_width,
                           steepPower=1.05, gentlePower=1.55)
            lateral = np.maximum(a, b)
        if comp in ('medial', 'all'):
            medial = asym_ridge(frame.w, steepWidth=p.ridgeWidth, gentleWidth=p.ridgeWidth, steepPower=1.4,
                                gentlePower=1.4)
        d = wrapped_delta(q, p.snout, ctx.tile)
        radius = length(d)
        if comp in ('terminal', 'all'):
            for i in range(int(p.nested)):
                retreat = np.maximum(p.snoutRadius * one_minus(p.arcSpacing * i), p.ridgeWidth * 2.5)
                terminal = np.maximum(terminal, ring(radius, retreat, p.ridgeWidth))
        if comp in ('rogen', 'all') and p.ribs > 0:
            rib_dist = periodic_distance(frame.along * p.ribs) / p.ribs
            rogen = one_minus(smoothstep(p.ridgeWidth * 0.42, p.ridgeWidth, rib_dist)) * p.ribDepth
        ground_on = comp in ('ground', 'all')
        ground_mask = sat(fbm(q, 11, 4, ctx, p.seed + 919) * 0.5 + 0.5) if ground_on else 0.0
        ridges = np.maximum(np.maximum(lateral, medial), np.maximum(terminal, rogen))
        arc_domain = one_minus(smoothstep(p.snoutRadius * 0.22, p.snoutRadius * 1.12, radius))
        hollows = arc_domain * one_minus(terminal) * (ground_mask * 0.4 + 0.6)
        ice_contact = lateral * smoothstep(p.lateralOffset - inner_width, p.lateralOffset, np.abs(frame.w))
        trimline = ring(np.abs(frame.w), p.lateralOffset, np.maximum(p.ridgeWidth * 0.35, 0.006))
        ground_height = fbm(q, 11, 4, ctx, p.seed + 977) * p.groundRelief if ground_on else 0.0
        texture = surface_detail(q, ctx, p.seed + 1009, 27, 3) * p.crest * (ridges * 0.04 + ground_mask * 0.018)
        return {'height': ridges * p.crest + ground_height - hollows * p.groundRelief * 0.45 + texture,
                'crest': smoothstep(0.62, 0.9, ridges), 'iceContact': ice_contact, 'trimline': trimline,
                'till': sat(ridges + ground_mask * 0.72), 'hollows': hollows}

    z = features(ctx.p)
    return {'field': sampled_add(f, ctx, lambda q: features(q)['height'], lambda q, h: z['till']),
            'outs': {k: z[k] for k in ('crest', 'iceContact', 'trimline', 'till', 'hollows')}}


moraineSet = dict(
    label='Moraine Set', category='terrain', optionalInput=True,
    doc='A glacial assemblage of lateral, medial, terminal, recessional, ribbed and hummocky ground moraines.',
    params={
        'components': P.enum('all', ['lateral', 'medial', 'terminal', 'rogen', 'ground', 'all']),
        'flowDirection': P.float(0, 0, 360, structural=True),
        'crest': P.float(0.05, 0, 0.3), 'ridgeWidth': P.float(0.025, 0.003, 0.2),
        'lateralOffset': P.float(0.2, 0.02, 0.6),
        'innerAngle': P.float(70, 30, 85, unit='deg', doc='ice-contact face'),
        'outerAngle': P.float(32, 20, 45, unit='deg', doc='outer till face'),
        'snout': P.vec2([0.5, 0.85]), 'snoutRadius': P.float(0.35, 0.05, 1),
        'nested': P.int(3, 1, 10, doc='terminal and recessional retreat arcs'),
        'arcSpacing': P.float(0.12, 0.02, 0.5),
        'ribs': P.int(0, 0, 32, doc='ribbed moraines across flow'),
        'ribDepth': P.float(0.5, 0, 1),
        'groundRelief': P.float(0.015, 0, 0.1, doc='hummocky ground moraine relief'),
        'seed': P.int(0, 0, 65535),
    },
    outputs=[mask('crest', 'bouldery till ridges'), mask('iceContact', 'steep ice-contact faces'),
             mask('trimline', 'upper lateral-moraine boundary'), mask('till', 'whole till coverage'),
             mask('hollows', 'kettles and lows between retreat arcs')],
    apply=_moraine_set)


# ------------------------------------------------------------------------------------------- streamform field ---

def _streamform(f, p, ctx):
    base = unit_axis(p.flowDirection)
    cross_base = [-base[1], base[0]]

    def features(q):
        cell = scatter_cell(q, p.frequency, ctx, p.seed, p.jitter)
        delta = cell.delta / cell.cells
        centre = q + delta
        from_focus = wrapped_delta(centre, Vec(0.5, 0.5), ctx.tile)
        fan_side = dot(from_focus, Vec(cross_base[0], cross_base[1])) / np.maximum(length(from_focus), EPS)
        rnd = cell.random
        turn = (rnd.y - 0.5) * p.azimuthJitter * math.pi + fan_side * p.splay * (math.pi * 0.45)
        ca, sa = np.cos(turn), np.sin(turn)
        axis = Vec(base[0] * ca - base[1] * sa, base[0] * sa + base[1] * ca)
        side = Vec(-axis.y, axis.x)
        form_length = p.length * mix(one_minus(p.elongVary * 0.38), 1.0 + p.elongVary * 0.38, rnd.z)
        elongation = p.elongation * mix(one_minus(p.elongVary * 0.32), 1.0 + p.elongVary * 0.45, rnd.x)
        form_width = form_length / np.maximum(elongation, 1.0)
        along = dot(delta, axis) / np.maximum(form_length * 0.5, EPS)
        across = dot(delta, side) / np.maximum(form_width * 0.5, EPS)
        asymmetry = p.asymmetry
        if p.mode == 'rocheMoutonnee':
            asymmetry = -p.asymmetry
        elif p.mode == 'whaleback':
            asymmetry = 0.0
        directed = along * asymmetry
        taper = np.maximum(0.28, one_minus(np.maximum(directed, 0.0) * p.bluntness * 0.72))
        rho = along * along + (across / taper) * (across / taper)
        body = np.power(sat(one_minus(rho)), 1.55)
        active = gate(rnd.w < p.density)
        forms = body * active
        h_vary = mix(one_minus(p.heightVary * 0.56), 1.0 + p.heightVary * 0.48, rnd.x)
        relief = forms * p.height * h_vary
        corridor = 0.0
        if p.mode == 'yardang':
            corridor = one_minus(forms)
            relief = -p.corridorDepth + forms * (p.corridorDepth + p.height * h_vary)
        stoss = forms * gate(along < 0)
        lee = forms * gate(along >= 0)
        crest = forms * smoothstep(0.58, 0.88, body)
        texture = (surface_detail(q, ctx, p.seed + 1123, max(4, js_round(p.frequency * 3)), 3)
                   * (p.height + p.corridorDepth) * (forms * 0.032 + corridor * 0.012))
        return {'height': relief + texture, 'forms': forms, 'stoss': stoss, 'lee': lee, 'corridor': corridor,
                'crest': crest}

    z = features(ctx.p)
    return {'field': sampled_add(f, ctx, lambda q: features(q)['height'], lambda q, h: z['forms'] + z['corridor']),
            'outs': {k: z[k] for k in ('forms', 'stoss', 'lee', 'corridor', 'crest')}}


streamform = dict(
    label='Streamform Field', category='terrain', optionalInput=True,
    doc='Fields of streamlined drumlins, rock forms, whalebacks or erosional yardangs with distinct stoss and lee '
        'faces.',
    params={
        'mode': P.enum('drumlin', ['drumlin', 'rocheMoutonnee', 'whaleback', 'yardang']),
        'flowDirection': P.float(0, 0, 360, structural=True),
        'frequency': P.float(5, 1, 64, structural=True, periodFreq=True),
        'density': P.float(0.7, 0.05, 1),
        'length': P.float(0.09, 0.005, 0.5),
        'elongation': P.float(2.8, 1, 12, doc='long-axis to width ratio'),
        'elongVary': P.float(0.4, 0, 1), 'height': P.float(0.06, 0, 0.3),
        'heightVary': P.float(0.6, 0, 1),
        'asymmetry': P.float(0.6, -1, 1, doc='positive steepens stoss; negative steepens lee'),
        'bluntness': P.float(0.5, 0, 1),
        'corridorDepth': P.float(0.06, 0, 0.4, doc='yardang corridor excavation'),
        'splay': P.float(0, 0, 1), 'azimuthJitter': P.float(0.08, 0, 1),
        'jitter': P.float(0.85, 0, 1), 'seed': P.int(0, 0, 65535),
    },
    outputs=[mask('forms', 'whole streamlined bodies'), mask('stoss', 'upstream faces'),
             mask('lee', 'downstream taper or plucked face'), mask('corridor', 'scoured yardang lows'),
             mask('crest', 'form crests')],
    apply=_streamform)


# ------------------------------------------------------------------------------------------------ ocean ridge ---

def _ocean_ridge(f, p, ctx):
    def features(q):
        frame = axis_frame(q, p.direction, 1, 0.0, p.seed)
        segment_coord = frame.along * p.segments
        seg_phase = fract(segment_coord)
        segment = np.floor(segment_coord)
        segment_angle = TAU / max(1, p.segments)

        def offset_at(index):
            return np.sin(index * segment_angle + p.seed * 0.29) * p.stepOver

        prev_off = offset_at(segment - 1.0)
        seg_off = offset_at(segment)
        next_off = offset_at(segment + 1.0)
        transform_half = 0.16
        entering = mix(prev_off, seg_off, smoothstep(0.0, transform_half, seg_phase) * 0.5 + 0.5)
        leaving = mix(seg_off, next_off, smoothstep(1.0 - transform_half, 1.0, seg_phase) * 0.5)
        offset = np.where(seg_phase < transform_half, entering,
                          np.where(seg_phase > 1.0 - transform_half, leaving, seg_off))
        w = frame.w - offset
        w = w - np.floor(w + 0.5)
        aw = np.abs(w)
        age = sat(aw / np.maximum(p.flankWidth, EPS))
        in_flank = one_minus(smoothstep(p.flankWidth * 0.92, p.flankWidth, aw))
        axis_mask = one_minus(smoothstep(p.riftWidth * 0.28, p.riftWidth, aw))
        rift = one_minus(smoothstep(p.riftWidth * 0.58, p.riftWidth * 1.22, aw))
        flank = smoothstep(p.riftWidth * 0.9, p.riftWidth * 2.3, aw) * in_flank
        fz_cross = one_minus(smoothstep(0.015, 0.09, periodic_distance(seg_phase)))
        fracture_zone = fz_cross * smoothstep(p.riftWidth, p.riftWidth * 2.2, aw) * in_flank
        fast = smoothstep(40.0, 90.0, p.spreadRate)
        rough_scale = mix(1.0, 0.22, fast)
        rough = surface_detail(q, ctx, p.seed + 1201, p.hillFreq, 4)
        hill_mask = sat(np.abs(rough) * p.hills * 1.3) * flank
        if p.mode == 'trench':
            trench = one_minus(np.power(age, 0.5)) * in_flank
            outer = ring(aw, p.flankWidth * 0.72, p.flankWidth * 0.16)
            relief = -p.trenchDepth * trench + p.outerRise * outer
        elif p.mode == 'abyssalPlain':
            relief = rough * p.hills * 0.012
        else:
            thermal = one_minus(np.power(age, 0.5)) * in_flank * p.rise
            axial = mix(-p.riftDepth, p.riftDepth * 0.34, fast) * rift
            abyssal = rough * p.hills * rough_scale * (p.rise * 0.055 + 0.006) * flank
            scarps = fracture_zone * p.fzRelief * np.where(w > 0, 1.0, -1.0)
            relief = thermal + axial + abyssal + scarps
        return {'height': relief, 'axis': axis_mask, 'rift': rift, 'flank': flank, 'fractureZone': fracture_zone,
                'hills': hill_mask, 'age': age}

    z = features(ctx.p)
    return {'field': sampled_add(f, ctx, lambda q: features(q)['height'], lambda q, h: z['axis'] + z['flank']),
            'outs': {k: z[k] for k in ('axis', 'rift', 'flank', 'fractureZone', 'hills', 'age')}}


oceanRidge = dict(
    label='Ocean Ridge', category='terrain', optionalInput=True,
    doc='Square-root age subsidence around a segmented spreading ridge, trench or abyssal plain with axial and '
        'transform structure.',
    params={
        'mode': P.enum('ridge', ['ridge', 'trench', 'abyssalPlain']),
        'direction': P.float(0, 0, 360, structural=True),
        'rise': P.float(0.3, 0, 1, doc='ridge height above the abyssal plain'),
        'flankWidth': P.float(0.45, 0.05, 2),
        'spreadRate': P.float(30, 5, 150, unit='mm/yr', doc='slow rates form axial rifts; fast rates axial highs'),
        'riftDepth': P.float(0.12, 0, 0.5), 'riftWidth': P.float(0.04, 0.002, 0.3),
        'segments': P.int(4, 1, 16), 'stepOver': P.float(0.08, 0, 0.4),
        'fzRelief': P.float(0.05, 0, 0.3), 'hills': P.float(0.5, 0, 1),
        'hillFreq': P.float(30, 2, 128, structural=True, periodFreq=True),
        'trenchDepth': P.float(0.4, 0, 1), 'outerRise': P.float(0.08, 0, 0.4),
        'seed': P.int(0, 0, 65535),
    },
    outputs=[mask('axis', 'fresh spreading-centre surface'), mask('rift', 'axial valley'),
             mask('flank', 'subsiding ridge flanks'), mask('fractureZone', 'transform scars'),
             mask('hills', 'abyssal-hill roughness'), mask('age', 'normalised crustal age')],
    apply=_ocean_ridge)


# ------------------------------------------------------------------------------------------- inverted channel ---

def _inverted_channel(f, p, ctx):
    def profile(w, width):
        r = np.abs(w) / np.maximum(width, EPS)
        inner = one_minus(p.margin)
        on_top = gate(r < inner)
        margin_t = smoothstep(inner, 1.0, r)
        cap_body = np.where(r < 1.0, mix(1.0, p.talus * 0.55, margin_t), 0.0)
        outside = np.maximum(r - 1.0, 0.0)
        apron = fan_profile(outside, 3.0, 1.25) * gate(r >= 1) * p.talus * 0.55
        edge = ring(r, inner + p.margin * 0.55, np.maximum(p.margin * 0.38, 0.025))
        return {'height': (cap_body + apron) * p.height, 'cap': on_top, 'edge': edge,
                'talus': apron / np.maximum(p.talus * 0.55, EPS), 'channel': sat(cap_body + apron)}

    def features(q):
        frame = axis_frame(q, p.direction, p.meanders, p.sinuosity * 0.16, p.seed)
        width_cycle = np.sin(frame.along * TAU + p.seed * 0.19) * 0.5 + 0.5
        width = p.halfWidth * (1.0 + p.widen * width_cycle * 0.34)
        main = profile(frame.w, width)
        relief, cap, edge, talus, channel = main['height'], main['cap'], main['edge'], main['talus'], main['channel']
        if p.branches > 0:
            angle = p.branchAngle * (math.pi / 180)
            slope = np.sin(angle) / np.maximum(np.cos(angle), 0.08)
            for i in range(int(p.branches)):
                phase = (i + 0.5) / p.branches + js_mod(p.seed * 0.1031, 1)
                u = fract(frame.along + phase) - 0.5
                side = 1 if i % 2 == 0 else -1
                branch_w = frame.w - u * slope * side
                branch = profile(branch_w, width * 0.58)
                length_gate = one_minus(smoothstep(0.18, 0.38, np.abs(u)))
                relief = np.maximum(relief, branch['height'] * length_gate)
                cap = np.maximum(cap, branch['cap'] * length_gate)
                edge = np.maximum(edge, branch['edge'] * length_gate)
                talus = np.maximum(talus, branch['talus'] * length_gate)
                channel = np.maximum(channel, branch['channel'] * length_gate)
        texture = surface_detail(q, ctx, p.seed + 1303, 25, 3) * p.height * (edge * 0.026 + talus * 0.042)
        return {'height': relief + texture, 'cap': cap, 'edge': edge, 'talus': talus, 'channel': channel}

    z = features(ctx.p)
    added = sampled_add(f, ctx, lambda q: features(q)['height'], lambda q, h: z['channel'])
    return {'field': reduced_base(f, added, p.burial), 'outs': {k: z[k] for k in ('cap', 'edge', 'talus', 'channel')}}


invertedChannel = dict(
    label='Inverted Channel', category='terrain', optionalInput=True,
    doc='A sinuous, flat-topped resistant palaeochannel with caprock edges, talus and preserved tributary branches.',
    params={
        'direction': P.float(0, 0, 360, structural=True),
        'meanders': P.int(3, 1, 10, doc='whole meanders across the tile'),
        'sinuosity': P.float(0.55, 0, 1), 'halfWidth': P.float(0.035, 0.004, 0.25),
        'widen': P.float(0.4, 0, 2, doc='downstream widening'),
        'height': P.float(0.07, 0, 0.4),
        'margin': P.float(0.15, 0.02, 0.6, doc='caprock edge width'),
        'talus': P.float(0.3, 0, 1), 'branches': P.int(2, 0, 6),
        'branchAngle': P.float(35, 10, 80, unit='deg'),
        'burial': P.float(0.3, 0, 1, doc='1 strips the surrounding incoming surface'),
        'seed': P.int(0, 0, 65535),
    },
    outputs=[mask('cap', 'resistant former channel fill'), mask('edge', 'caprock rim'),
             mask('talus', 'debris below the caprock'), mask('channel', 'whole preserved drainage trace')],
    apply=_inverted_channel)


WAVE2_LANDFORMS = {
    'glacialTrough': glacialTrough,
    'meanderBelt': meanderBelt,
    'faultScarp': faultScarp,
    'graben': graben,
    'dipSlope': dipSlope,
    'esker': esker,
    'moraineSet': moraineSet,
    'streamform': streamform,
    'oceanRidge': oceanRidge,
    'invertedChannel': invertedChannel,
}
