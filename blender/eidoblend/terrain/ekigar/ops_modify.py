"""Ekigar operators, part 3 (registry.js MODIFY): Invert, Clip, Threshold, Soft Clip, Gamma, Fold, and the
neighbourhood filters Blur, Sharpen, Median, Dilate and Recurve (which re-evaluate their input at offset positions
through ctx.sample_input, exactly as the compiler does on the GPU).
"""
from __future__ import annotations

import numpy as np

from ._tsl import clamp, select, step01, EPS
from .ops_shared import P, H, G, AUX, field, remap, texel, sstep, waveform, median_of

OPS = {}


OPS['invert'] = dict(
    label='Invert', category='modify',
    doc='Flips the height field about its midpoint.',
    params={'pivot': P.float(0.5, -1, 2)},
    apply=lambda f, p, ctx: field(p.pivot * 2.0 - H(f), -G(f), AUX(f)))


def _clip(f, p, ctx):
    span = np.maximum(p.max - p.min, EPS)
    t = (H(f) - p.min) / span
    inside = (t > 0) & (t < 1)
    return remap(f, clamp(t, 0.0, 1.0), np.where(inside, 1.0 / span, 0.0))


OPS['clip'] = dict(
    label='Clip', category='modify',
    doc='Cuts the terrain against two thresholds and rescales what survives to the full range. Unlike Clamp, which '
        'preserves scale.',
    params={'min': P.float(0.15, -1, 2), 'max': P.float(0.85, -1, 2)}, apply=_clip)


def _threshold(f, p, ctx):
    s = np.maximum(p.softness, EPS)
    g = sstep(p.level - s, p.level + s, H(f))
    return remap(f, H(f) * g.v, g.v + H(f) * g.d)


OPS['threshold'] = dict(
    label='Threshold', category='modify',
    doc='Retains what is above the level and discards what is below.',
    params={
        'level': P.float(0.4, -1, 2),
        'softness': P.float(0.03, 0.001, 0.5,
                            doc='transition width; prevents aliasing and preserves a usable derivative'),
    }, apply=_threshold)


def _soft_clip(f, p, ctx):
    above = p.clipMode == 'aboveThreshold'
    e = H(f) - p.threshold if above else p.threshold - H(f)
    s = np.maximum(p.softness, EPS)
    t = clamp(e / s, 0.0, 1.0)
    w = t * t * (3.0 - t * 2.0)
    dw = t * (1.0 - t) * 6.0 / s
    comp = 1.0 - p.clipping * w
    new_e = e * comp
    d_new_e = comp - e * p.clipping * dw
    active = e > 0
    h = p.threshold + new_e if above else p.threshold - new_e
    return remap(f, np.where(active, h, H(f)), np.where(active, d_new_e, 1.0))


OPS['softClip'] = dict(
    label='Soft Clip', category='modify',
    doc='Softly reduces the intensity of shapes past a threshold — like masking by Height and then clamping, but C1.',
    params={
        'clipMode': P.enum('aboveThreshold', ['aboveThreshold', 'belowThreshold']),
        'threshold': P.float(0.6, -1, 2),
        'softness': P.float(0.15, 0.005, 1),
        'clipping': P.float(0.7, 0, 1),
    }, apply=_soft_clip)


def _gamma(f, p, ctx):
    h = clamp(H(f), EPS, 1.0)
    inside = (H(f) > EPS) & (H(f) < 1)
    return remap(f, np.power(h, p.gamma), p.gamma * np.power(h, p.gamma - 1.0) * step01(inside))


OPS['gamma'] = dict(
    label='Gamma', category='modify',
    doc='Gamma on the height, exactly as in an image editor: below 1 lifts mid values, above 1 pushes them down.',
    params={'gamma': P.float(1, 0.05, 2.5)}, apply=_gamma)


def _fold(f, p, ctx):
    h = H(f)
    base = np.abs(h - 0.5) * 2.0 if p.symmetric else h
    dbase = np.sign(h - 0.5) * 2.0 if p.symmetric else 1.0
    w = waveform(p.waveform, base * p.folds)
    return remap(f, w.v, w.d * p.folds * dbase)


OPS['fold'] = dict(
    label='Fold', category='modify',
    doc='Folds the height range back on itself — slants, breaks and folds. Changes the shape drastically, so use it '
        'early.',
    params={
        'waveform': P.enum('sine', ['sine', 'triangle', 'sawtooth']),
        'folds': P.float(2, 0.5, 16),
        'symmetric': P.bool(False),
    }, apply=_fold)


def _blur(f, p, ctx):
    e = texel(ctx, p.radius)
    taps = [(0, 0, 4), (-1, 0, 2), (1, 0, 2), (0, -1, 2), (0, 1, 2), (-1, -1, 1), (1, -1, 1), (-1, 1, 1), (1, 1, 1)]
    h = g = None
    wsum = 0
    for dx, dy, k in taps:
        s = f if (dx == 0 and dy == 0) else ctx.sample_input(dx * e, dy * e)
        h = H(s) * k if h is None else h + H(s) * k
        g = G(s) * k if g is None else g + G(s) * k
        wsum += k
    return field(h / wsum, g / wsum, AUX(f))


OPS['blur'] = dict(
    label='Blur', category='modify',
    doc='Diffuses sharp shapes and softens the terrain.',
    params={'radius': P.float(2, 0.5, 24, structural=True,
                              doc='kernel radius in texels; sets the neighbour tap distance')},
    needsResample=True, apply=_blur)


def _sharpen(f, p, ctx):
    e = texel(ctx, p.radius)
    taps = ([(-1, 0), (1, 0), (0, -1), (0, 1), (-1, -1), (1, -1), (-1, 1), (1, 1)] if p.method == 'frequency'
            else [(-1, 0), (1, 0), (0, -1), (0, 1)])
    lh = lg = None
    for dx, dy in taps:
        s = ctx.sample_input(dx * e, dy * e)
        lh = H(s) if lh is None else lh + H(s)
        lg = G(s) if lg is None else lg + G(s)
    lh = lh / len(taps)
    lg = lg / len(taps)
    return field(H(f) + (H(f) - lh) * p.amount, G(f) + (G(f) - lg) * p.amount, AUX(f))


OPS['sharpen'] = dict(
    label='Sharpen', category='modify',
    doc='Enhances edges and small structures.',
    params={
        'method': P.enum('edge', ['edge', 'frequency']),
        'amount': P.float(1, 0, 4),
        'radius': P.float(1.5, 0.5, 12, structural=True, doc='tap distance in texels'),
    }, needsResample=True, apply=_sharpen)


def _median(f, p, ctx):
    e = texel(ctx, p.radius)
    offs = ([(0, 0), (-1, 0), (1, 0), (0, -1), (0, 1), (-1, -1), (1, -1), (-1, 1), (1, 1)] if p.mode == 'advanced'
            else [(0, 0), (-1, 0), (1, 0), (0, -1), (0, 1)])
    fs = [f if (dx == 0 and dy == 0) else ctx.sample_input(dx * e, dy * e) for dx, dy in offs]
    med = median_of([H(s) for s in fs])
    g = G(fs[0])
    best = np.abs(H(fs[0]) - med)
    for s in fs[1:]:
        d = np.abs(H(s) - med)
        g = select(d < best, G(s), g)
        best = np.minimum(best, d)
    return field(med, g, AUX(f))


OPS['median'] = dict(
    label='Median', category='modify',
    doc='Removes spikes and speckles while preserving edges far better than blur.',
    params={
        'mode': P.enum('advanced', ['classic', 'advanced'], doc='classic = 5-tap cross, advanced = full 3x3'),
        'radius': P.float(2, 0.5, 8, structural=True),
    }, needsResample=True, apply=_median)

_DILATE_KERNELS = {
    'cross': [(-1, 0), (1, 0), (0, -1), (0, 1)],
    'rectangle': [(-1, 0), (1, 0), (0, -1), (0, 1), (-1, -1), (1, -1), (-1, 1), (1, 1)],
    'line': [(-1, 0), (1, 0)],
    'lineVertical': [(0, -1), (0, 1)],
}


def _dilate(f, p, ctx):
    base = texel(ctx, p.size)
    out = f
    for it in range(1, int(p.iterations) + 1):
        e = base * it
        for dx, dy in _DILATE_KERNELS[p.kernel]:
            s = ctx.sample_input(dx * e, dy * e)
            win = (H(s) < out.x) if p.invert else (H(s) > out.x)
            out = select(win, s, out)
    return out


OPS['dilate'] = dict(
    label='Dilate', category='modify',
    doc='Morphological dilation — grows features outward. Invert makes it an erosion instead.',
    params={
        'size': P.float(2, 0.5, 16, structural=True, doc='structuring-element radius in texels'),
        'iterations': P.int(1, 1, 3),
        'kernel': P.enum('cross', ['cross', 'rectangle', 'line', 'lineVertical']),
        'invert': P.bool(False, doc='select local minima instead, producing morphological erosion'),
    }, needsResample=True, apply=_dilate)


def _recurve(f, p, ctx):
    e = texel(ctx, p.scale)
    lh = lg = None
    n = 0
    for it in range(1, int(p.iterations) + 1):
        for dx, dy in ((-1, 0), (1, 0), (0, -1), (0, 1)):
            s = ctx.sample_input(dx * e * it, dy * e * it)
            lh = H(s) if lh is None else lh + H(s)
            lg = G(s) if lg is None else lg + G(s)
            n += 1
    lh = lh / n
    lg = lg / n
    k = p.power * (-1 if p.style == 'inward' else 1)
    return field(H(f) + (H(f) - lh) * k, G(f) + (G(f) - lg) * k, AUX(f))


OPS['recurve'] = dict(
    label='Recurve', category='modify',
    doc='Curvature-based expander: inflates or deflates the terrain into stronger slopes and larger, softer '
        'formations.',
    params={
        'power': P.float(0.6, 0, 3),
        'scale': P.float(4, 1, 24, structural=True, doc='radius of the shapes being inflated, in texels'),
        'iterations': P.int(2, 1, 3),
        'style': P.enum('outward', ['outward', 'inward']),
    }, needsResample=True, apply=_recurve)
