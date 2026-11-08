"""Ekigar operators, part 2 (registry.js): the Derive nodes that turn terrain into masks (Height, Slope, Angle,
Curvature, Peaks, Texture Base), Seamless, Edge, and the Material Map declaration.

Derive nodes differentiate the HEIGHT (screen derivatives for first order, real neighbour re-evaluation through
ctx.sample_input for second order), never the carried gradient, which is ~29 degrees out under erosion.
"""
from __future__ import annotations

import numpy as np

from ._tsl import Vec, clamp, mix, lerp, fract, step01, EPS
from ._deriv import dfdx, dfdy
from .ops_shared import (P, H, G, AUX, field, texel, RES, smoothstep_soft, sstep, fbm_field, seed_offset,
                         js_round)

OPS = {}


def _height_mask(f, p, ctx):
    return field(smoothstep_soft(H(f), p.lo, p.hi, p.falloff), Vec(0.0, 0.0), AUX(f))


OPS['heightMask'] = dict(
    label='Height', category='derive',
    doc='Altitude as a mask, with an adjustable window. Wire into Material Map to drive elevation bands.',
    params={'lo': P.float(0.5, -1, 2), 'hi': P.float(2, -1, 2), 'falloff': P.float(0.08, 0.001, 0.5)},
    apply=_height_mask)


def _slope_mask(f, p, ctx):
    h = H(f)
    g = np.sqrt(dfdx(h) ** 2 + dfdy(h) ** 2) * p.gain * (RES(ctx) / 4)
    return field(smoothstep_soft(g, p.lo, p.hi, p.falloff), Vec(0.0, 0.0), AUX(f))


OPS['slopeMask'] = dict(
    label='Slope', category='derive',
    doc='Steepness as a mask, from screen-space derivatives of the height. The cliff/wall selector.',
    params={'lo': P.float(0, 0, 4), 'hi': P.float(1, 0, 4), 'falloff': P.float(0.08, 0.001, 0.5),
            'gain': P.float(1, 0.1, 8)},
    apply=_slope_mask)


def _angle_mask(f, p, ctx):
    gx = dfdx(H(f))
    gy = dfdy(H(f))
    ln = np.maximum(np.sqrt(gx * gx + gy * gy), 1e-7)
    dxv, dyv = np.cos(p.direction), np.sin(p.direction)
    facing = (-gx) / ln * dxv + (-gy) / ln * dyv
    return field(np.power(clamp(facing * 0.5 + 0.5, 0.0, 1.0), p.sharpness), Vec(0.0, 0.0), AUX(f))


OPS['angleMask'] = dict(
    label='Angle', category='derive',
    doc='Aspect as a directional component — sun-facing bias, melt, prevailing wind. A component, not a wrapped '
        'angle, so a mask window cannot tear at north.',
    params={'direction': P.float(0, 0, 6.283, unit='rad'), 'sharpness': P.float(1, 0.2, 6)},
    apply=_angle_mask)


def _stencil9(f, ctx, e):
    s = ctx.sample_input
    return (H(f), H(s(-e, 0)), H(s(e, 0)), H(s(0, -e)), H(s(0, e)),
            H(s(-e, -e)), H(s(e, e)), H(s(-e, e)), H(s(e, -e)))


def _curvature_mask(f, p, ctx):
    e = texel(ctx, p.radius)
    h, hL, hR, hD, hU, hLD, hRU, hLU, hRD = _stencil9(f, ctx, e)
    inv, inv2 = 1.0 / (2 * e), 1.0 / (e * e)
    gx = (hR - hL) * inv
    gy = (hU - hD) * inv
    r = (hR + hL - h * 2.0) * inv2
    t = (hU + hD - h * 2.0) * inv2
    sxy = (hRU - hLU - hRD + hLD) * (inv2 * 0.25)
    p2, q2 = gx * gx, gy * gy
    g2 = np.maximum(p2 + q2, 1e-9)
    profile = -((p2 * r + gx * gy * sxy * 2.0 + q2 * t) / g2)
    plan = -((q2 * r - gx * gy * sxy * 2.0 + p2 * t) / g2)
    mean_c = -((r + t) * 0.5)
    k = p.gain * 0.05
    if p.mode == 'convex':
        v = clamp(profile * k, 0.0, 1.0)
    elif p.mode == 'profile':
        v = clamp(profile * k * 0.5 + 0.5, 0.0, 1.0)
    elif p.mode == 'plan':
        v = clamp(plan * k * 0.5 + 0.5, 0.0, 1.0)
    elif p.mode == 'mean':
        v = clamp(mean_c * k * 0.5 + 0.5, 0.0, 1.0)
    else:
        v = clamp(-(profile * k), 0.0, 1.0)
    return field(v, Vec(0.0, 0.0), AUX(f))


OPS['curvatureMask'] = dict(
    label='Curvature', category='derive',
    doc='Concave collects material, convex sheds it. Profile curvature runs along the slope (deposition); plan runs '
        'across it (drainage convergence).',
    params={
        'mode': P.enum('concave', ['concave', 'convex', 'profile', 'plan', 'mean']),
        'radius': P.float(1.5, 0.2, 8, structural=True, doc='neighbour distance in texels'),
        'gain': P.float(1, 0.05, 20),
    }, needsResample=True, apply=_curvature_mask)


def _peaks_mask(f, p, ctx):
    e = texel(ctx, p.radius)
    s = ctx.sample_input
    h = H(f)
    hL, hR, hD, hU = H(s(-e, 0)), H(s(e, 0)), H(s(0, -e)), H(s(0, e))
    lap = (h * 4.0 - hL - hR - hD - hU) * (1.0 / (e * e))
    conv = clamp(lap * p.gain * 0.02, 0.0, 1.0)
    high = smoothstep_soft(h, p.threshold, 2.0, p.falloff)
    return field(conv * high, Vec(0.0, 0.0), AUX(f))


OPS['peaksMask'] = dict(
    label='Peaks', category='derive',
    doc='High AND convex at once — ridgelines and summits, rather than merely high ground.',
    params={
        'threshold': P.float(0.5, 0, 1),
        'radius': P.float(2, 0.2, 12, structural=True, doc='neighbour distance in texels'),
        'gain': P.float(1, 0.05, 20),
        'falloff': P.float(0.12, 0.001, 0.5),
    }, needsResample=True, apply=_peaks_mask)


def _texture_base(f, p, ctx):
    e = texel(ctx, p.radius)
    h, hL, hR, hD, hU, hLD, hRU, hLU, hRD = _stencil9(f, ctx, e)
    inv, inv2 = 1.0 / (2 * e), 1.0 / (e * e)
    gx = (hR - hL) * inv
    gy = (hU - hD) * inv
    rr = (hR + hL - h * 2.0) * inv2
    tt = (hU + hD - h * 2.0) * inv2
    ss = (hRU - hLU - hRD + hLD) * (inv2 * 0.25)
    g = np.sqrt(np.maximum(gx * gx + gy * gy, 1e-12))
    slope_t = clamp(g / np.maximum(p.slopeAngle, EPS), 0.0, 1.0)
    p2, q2 = gx * gx, gy * gy
    g2 = np.maximum(p2 + q2, 1e-9)
    profile = -((p2 * rr + gx * gy * ss * 2.0 + q2 * tt) / g2)
    plan = -((q2 * rr - gx * gy * ss * 2.0 + p2 * tt) / g2)
    cg = 0.05
    cavity_t = clamp(-(profile * cg), 0.0, 1.0)
    converge_t = clamp(-(plan * cg), 0.0, 1.0)
    flat = clamp(1.0 - g / np.maximum(p.soilAngle, EPS), 0.0, 1.0)
    deposition_t = flat * clamp(cavity_t + converge_t * 0.5 + 0.25, 0.0, 1.0)
    nf = max(1, js_round(p.patchScale))
    n = fbm_field(ctx, frequency=nf, octaves=2, offset=seed_offset(p.seed, nf))
    patch_t = clamp(n.v * 0.5 * p.patchContrast + 0.5, 0.0, 1.0)
    hess = np.sqrt(rr * rr + ss * ss * 2.0 + tt * tt + 1e-12)
    chaos_t = clamp(hess * p.chaosGain * 0.02, 0.0, 1.0)
    convex = clamp(-(rr + tt) * 0.02, 0.0, 1.0)
    peak_t = convex * smoothstep_soft(h, p.peakLevel, 2.0, 0.12)
    v = (0.5 + deposition_t * p.soil * 0.42 - slope_t * p.slope * 0.55 + peak_t * p.peaks * 0.45
         + (patch_t - 0.5) * p.patches * 0.42 - chaos_t * p.chaos * 0.30)
    v = clamp(v, 0.0, 1.0)
    v = lerp(v, sstep(0.0, 1.0, v).v, p.accentuate)
    if p.reverse:
        v = 1.0 - v
    if ctx.wired is not None and 'guide' in ctx.wired:
        v = v * clamp(H(ctx.inputs['guide']), 0.0, 1.0)
    return {'field': field(clamp(v, 0.0, 1.0), Vec(0.0, 0.0), AUX(f))}


OPS['textureBase'] = dict(
    label='Texture Base', category='derive',
    doc=('Classifies slope, deposition, breakup and peaks into stable positive value bands for Material Map, while '
         'exposing each terrain diagnostic as a named mask. Flow accumulation is deliberately absent because it needs '
         'ACCUMULATION — a transitive closure over the drainage network that no bounded neighbourhood computes — and '
         "phacelle's `flow` output is gully strength, which cannot tell a first-order rill from a trunk channel. "
         "Automatic level equalization needs the whole tile's min/max and is absent for the same reason."),
    params={
        'slope': P.float(0.6, 0, 1, doc='steep ground'),
        'soil': P.float(0.5, 0, 1, doc='where soil settles — flat AND concave'),
        'patches': P.float(0.3, 0, 1, doc='blotchy variation, so a material band is not uniform'),
        'chaos': P.float(0.4, 0, 1, doc='broken, high-curvature ground'),
        'peaks': P.float(0.35, 0, 1, doc='high and convex at once'),
        'slopeAngle': P.float(0.55, 0.05, 3, doc='|grad| that reads as fully steep'),
        'soilAngle': P.float(0.35, 0.05, 3, doc='|grad| above which soil no longer holds'),
        'patchScale': P.float(6, 1, 64, structural=True, periodFreq=True, doc='patches across the tile'),
        'patchContrast': P.float(2.5, 1, 8),
        'chaosGain': P.float(1, 0.05, 20),
        'peakLevel': P.float(0.6, -1, 2),
        'radius': P.float(1.5, 0.5, 8, structural=True, doc='neighbour distance in texels'),
        'accentuate': P.float(0.35, 0, 1, doc='separates strong from weak class evidence before classification'),
        'reverse': P.bool(False, doc='invert the resulting texture signal'),
        'seed': P.int(0, 0, 65535),
    }, needsResample=True, apply=_texture_base)


def _seamless(f, p, ctx):
    px, py = ctx.tile.x > 0, ctx.tile.y > 0
    if not px and not py:
        return f
    tx = ctx.tile.x if px else 1.0
    ty = ctx.tile.y if py else 1.0
    sx = (p.shiftX or 0) * tx
    sy = (p.shiftY or 0) * ty

    def at(dx, dy):
        return f if (dx == 0 and dy == 0) else ctx.sample_input(dx, dy)

    w = np.maximum(p.edge, 1e-4)
    half = 1.0 / (w * 2.0)

    def ramps(c, dirv, ln):
        lo = clamp(0.5 - c / w * 0.5, 0.0, 0.5)
        hi = clamp(0.5 - (1.0 - c) / w * 0.5, 0.0, 0.5)
        in_lo = step01((lo > 0) & (lo < 0.5))
        in_hi = step01((hi > 0) & (hi < 0.5))
        return {'lo': lo, 'hi': hi, 'dlo': dirv * (-half / ln * in_lo), 'dhi': dirv * (half / ln * in_hi)}

    ax = ramps(fract(ctx.p.x / tx), Vec(1.0, 0.0), tx)
    ay = ramps(fract(ctx.p.y / ty), Vec(0.0, 1.0), ty)

    def cross(A, B, C, k):
        h = A.x + (B.x - A.x) * k['lo'] + (C.x - A.x) * k['hi']
        ga = Vec(A.y, A.z)
        g = (ga + (Vec(B.y, B.z) - ga) * k['lo'] + (Vec(C.y, C.z) - ga) * k['hi']
             + k['dlo'] * (B.x - A.x) + k['dhi'] * (C.x - A.x))
        return Vec(h, g.x, g.y, A.w)

    def along_x(dy):
        A = at(sx, sy + dy)
        return cross(A, at(sx + tx, sy + dy), at(sx - tx, sy + dy), ax) if px else A

    M = along_x(0)
    return cross(M, along_x(ty), along_x(-ty), ay) if py else M


OPS['seamless'] = dict(
    label='Seamless', category='utility',
    doc='Makes an arbitrary terrain tile against itself by cross-blending opposite edges. Works on terrain that was '
        'never periodic — including imported heightmaps.',
    params={
        'edge': P.float(0.15, 0.01, 0.5, doc='width of the blended border, as a fraction of the tile'),
        'shiftX': P.float(0, 0, 1, structural=True),
        'shiftY': P.float(0, 0, 1, structural=True),
    }, needsResample=True, apply=_seamless)


def _edge_fade(f, p, ctx):
    t = 1.0
    u = fract(ctx.p.x / t)
    v = fract(ctx.p.y / t)
    dx = np.minimum(u, 1.0 - u)
    dy = np.minimum(v, 1.0 - v)
    if p.style == 'round':
        d = 1.0 - np.sqrt((0.5 - dx) ** 2 + (0.5 - dy) ** 2)
    else:
        d = np.minimum(dx, dy)
    k = clamp(d / np.maximum(p.size, 1e-4), 0.0, 1.0)
    soft = mix(k, k * k * (3.0 - k * 2.0), p.softness)
    return field(mix(p.level, H(f), soft), G(f) * soft, AUX(f))


OPS['edgeFade'] = dict(
    label='Edge', category='utility',
    doc='Fades the terrain toward a chosen level at its borders. Use before stamping, or to guarantee a flat frame.',
    params={
        'size': P.float(0.12, 0.005, 0.5),
        'softness': P.float(0.5, 0, 1),
        'style': P.enum('square', ['square', 'round']),
        'level': P.float(0.5, -1, 2, doc='height the border fades to'),
    }, apply=_edge_fade)


def _material_map_apply(f, p, ctx):
    raise ValueError('Material Map produces a material stack, not a terrain field')


MATERIAL_MAP = dict(
    label='Material Map', category='colorize',
    doc='Maps positive value bands from one required mask to an ordered stack of complete PBR materials. Materials, '
        'their bands and channel controls are edited inside the node; the graph emits one material stack.',
    params={'triplanarSharpness': P.float(4, 1, 12)},
    apply=_material_map_apply)

OPS['materialMap'] = MATERIAL_MAP
OPS['surface'] = dict(MATERIAL_MAP, hidden=True, label='Material Map (was Surface)',
                      doc=MATERIAL_MAP['doc'] + ' Legacy id, kept only so older saved projects load.')
