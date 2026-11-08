"""Phacelle erosion: Ekigar's src/nodes/phacelle.js (credit: Rune Skovbo Johansen's Phacelle noise), over numpy.

Directional stripe noise aligned perpendicular to the slope, carrying its phase derivative, with each octave feeding
its gradient back into the gully direction so the next octave's gullies follow the terrain the previous one carved.
Single pass, analytic, no iteration; periodic once the lattice is wrapped (period = tile * octave frequency cells).

    phacelle_noise(p, norm_dir, freq, offset, normalization, period) -> vec4(cos, sin, sideDirX, sideDirY)
    erosion_operator(f, p, ctx)      the registry form: field vec4 (h, dh/dx, dh/dy, aux) in, eroded field out
    ekigar_field(p, cfg)             the M0 base field (fBm + erosion) of field_cpu.js's defaultConfig

The returned gradient is the erosion's CARRIED gradient: approximate by the reference's design (it drops the spatial
derivative of its own onset mask). Slope and curvature masks come from finite differences of the height instead.
"""
from __future__ import annotations

import numpy as np

from ._tsl import Vec, clamp, mix, select, length
from .noise import hash2, fractal_noise

TAU = 6.28318530717959          # phacelle.js's own constant (the registry's TAU has more digits)


def phacelle_noise(p: Vec, norm_dir: Vec, freq, offset, normalization, period) -> Vec:
    """vec4(cos, sin, sideDirX, sideDirY). `freq` is the cell scale; p is already scaled by the octave frequency."""
    perx, pery = (period.x, period.y) if isinstance(period, Vec) else period
    sdx = -norm_dir.y * freq * TAU
    sdy = norm_dir.x * freq * TAU
    off = offset * TAU
    pix = np.floor(p.x)
    piy = np.floor(p.y)
    pfx = p.x - pix
    pfy = p.y - piy
    phx = 0.0
    phy = 0.0
    wsum = 0.0
    # 4x4 neighbourhood: cell points jitter by up to 0.5, so the nearest point outside it is 1.5 away, where the bell
    # weight is already exactly 0. 4x4 is exact, not an approximation.
    for i in range(-1, 3):
        for j in range(-1, 3):
            rx, ry = hash2(pix + i, piy + j, perx, pery)
            vx = pfx - i - rx * 0.5
            vy = pfy - j - ry * 0.5
            sqr = vx * vx + vy * vy
            # -0.01111 makes the weight reach exactly 0 at 1.5, which removes the grid-line artefact.
            w = np.maximum(0.0, np.exp(sqr * -2.0) - 0.01111)
            wsum = wsum + w
            wave = vx * sdx + vy * sdy + off
            phx = phx + np.cos(wave) * w
            phy = phy + np.sin(wave) * w
    ix = phx / wsum
    iy = phy / wsum
    mag = np.maximum(1.0 - normalization, np.sqrt(ix * ix + iy * iy))
    return Vec(ix / mag, iy / mag, sdx, sdy)


def pow_inv(t, power):
    return 1.0 - np.power(1.0 - clamp(t, 0.0, 1.0), power)


def ease_out(t):
    # squared by multiplication, as the reference does (pow(x, 2) is inexact at x == 0 on the GPU)
    v = 1.0 - clamp(t, 0.0, 1.0)
    return 1.0 - v * v


def smooth_start(t, smoothing):
    return select(t >= smoothing, t - smoothing * 0.5, t * t * 0.5 / np.maximum(smoothing, 1e-20))


def safe_normalize(n: Vec) -> Vec:
    ln = length(n)
    big = ln > 1e-10
    return Vec(np.where(big, n.x / np.where(big, ln, 1.0), n.x), np.where(big, n.y / np.where(big, ln, 1.0), n.y))


def erosion_operator(f: Vec, p, ctx) -> Vec:
    """Phacelle erosion as a graph operator (phacelle.js erosionOperator).

    p: strength, gullyWeight, detail, gain, normalization, ridgeRounding, creaseRounding, offset, preserve (floats);
       scale, cellScale (structural: they set each octave's lattice period), octaves, lacunarity (ints).
    Returns vec4(height, dh/dx, dh/dy, ridgeMap)."""
    hx = f.x
    hy = f.y
    hz = f.z
    in_x = f.x
    fade = clamp((hx - 0.5) * 2.0 / 0.6, -1.0, 1.0)
    R0, R1 = p.ridgeRounding, p.creaseRounding
    R2, R3 = 0.1, 2.0
    O = (0.7, 1.25, 2.8, 1.5)
    AS = (0.7, 1.0)

    slope_len = np.maximum(np.sqrt(hy * hy + hz * hz), 1e-10)
    magnitude = 0.0
    rounding_in = mix(R1, R0, clamp(fade + 0.5, 0.0, 1.0)) * R2
    combi = ease_out(smooth_start(slope_len * O[0], rounding_in * O[0]))
    ridge_mask = ease_out(slope_len * O[2])
    ridge_fade = fade
    gsx = mix(hy, hy / slope_len * AS[0], AS[1])
    gsy = mix(hz, hz / slope_len * AS[0], AS[1])

    strength = p.strength * p.scale
    freq = 1.0 / (p.scale * p.cellScale)
    rmult = 1.0
    tile = ctx.tile
    for _ in range(int(p.octaves)):
        period = (tile.x * freq, tile.y * freq)
        ph = phacelle_noise(ctx.p * freq, safe_normalize(Vec(gsx, gsy)), float(p.cellScale), 0.25,
                            p.normalization, period)
        pz = ph.z * -freq
        pw = ph.w * -freq
        sloping = np.abs(ph.y)
        sg = np.sign(ph.y)
        gsx = gsx + pz * sg * strength * p.gullyWeight
        gsy = gsy + pw * sg * strength * p.gullyWeight
        gul_x = ph.x
        fg_x = mix(fade, gul_x * p.gullyWeight, combi)
        fg_y = mix(0.0, ph.y * pz * p.gullyWeight, combi)
        fg_z = mix(0.0, ph.y * pw * p.gullyWeight, combi)
        hx = hx + fg_x * strength
        hy = hy + fg_y * strength
        hz = hz + fg_z * strength
        magnitude = magnitude + strength
        fade = fg_x
        rfo = mix(R1, R0, clamp(gul_x + 0.5, 0.0, 1.0)) * rmult
        combi = pow_inv(combi, p.detail) * ease_out(smooth_start(sloping * O[1], rfo * O[1]))
        ridge_fade = mix(ridge_fade, gul_x, ridge_mask)
        ridge_mask = ridge_mask * ease_out(sloping * O[3])
        strength = strength * p.gain
        freq *= p.lacunarity
        rmult *= R3
    # Peak-preserving raise/lower (the reference's TERRAIN_HEIGHT_OFFSET): mix a flat bias toward the negated fade
    # target, which raises valleys and lowers peaks so the extrema survive the erosion.
    off_p = 0.0 if p.offset is None else p.offset
    pres = 1.0 if p.preserve is None else p.preserve
    offset = mix(off_p, -fade, pres)
    return Vec(in_x + (hx - in_x) + offset * magnitude, hy, hz, ridge_fade * (1.0 - ridge_mask))


def ekigar_field(p: Vec, cfg: dict, debug: str | None = None) -> Vec:
    """The M0 base field (phacelle.js ekigarField / buildField): fBm base + the reference's erosion half.

    cfg is field_cpu.default_config()'s shape: {tile, base, erosion, heightOffset}. Returns
    vec4(height, dh/dx, dh/dy, ridge)."""
    tile = cfg['tile']
    tx, ty = (tile['x'], tile['y']) if isinstance(tile, dict) else tile
    base, ero, hoff = cfg['base'], cfg['erosion'], cfg['heightOffset']
    n = fractal_noise(p, base['frequency'], base['octaves'], base['lacunarity'], base['gain'], (tx, ty))
    h0 = n.x * base['amplitude']
    dx0 = n.y * base['amplitude']
    dy0 = n.z * base['amplitude']
    fade0 = clamp(h0 / (base['amplitude'] * 0.6), -1.0, 1.0)
    hx = h0 * 0.5 + 0.5
    hy = dx0 * 0.5
    hz = dy0 * 0.5
    in_x = hx
    strength = ero['strength'] * ero['scale']
    freq = 1.0 / (ero['scale'] * ero['cellScale'])
    rmult = 1.0
    R, O, AS = ero['rounding'], ero['onset'], ero['assumedSlope']
    slope_len = np.maximum(np.sqrt(hy * hy + hz * hz), 1e-10)
    magnitude = 0.0
    fade = fade0
    rounding_in = mix(R[1], R[0], clamp(fade + 0.5, 0.0, 1.0)) * R[2]
    combi = ease_out(smooth_start(slope_len * O[0], rounding_in * O[0]))
    ridge_mask = ease_out(slope_len * O[2])
    ridge_fade = fade0
    gsx = mix(hy, hy / slope_len * AS[0], AS[1])
    gsy = mix(hz, hz / slope_len * AS[0], AS[1])
    last_sloping = 0.0
    last_gul = 0.0
    for _ in range(int(ero['octaves'])):
        period = (tx * freq, ty * freq)
        ph = phacelle_noise(p * freq, safe_normalize(Vec(gsx, gsy)), float(ero['cellScale']), 0.25,
                            float(ero['normalization']), period)
        pz = ph.z * -freq
        pw = ph.w * -freq
        sloping = np.abs(ph.y)
        last_sloping = sloping
        sg = np.sign(ph.y)
        gsx = gsx + pz * sg * (strength * ero['gullyWeight'])
        gsy = gsy + pw * sg * (strength * ero['gullyWeight'])
        gul_x = ph.x
        gul_y = ph.y * pz
        gul_z = ph.y * pw
        last_gul = gul_x
        fg_x = mix(fade, gul_x * ero['gullyWeight'], combi)
        fg_y = mix(0.0, gul_y * ero['gullyWeight'], combi)
        fg_z = mix(0.0, gul_z * ero['gullyWeight'], combi)
        hx = hx + fg_x * strength
        hy = hy + fg_y * strength
        hz = hz + fg_z * strength
        magnitude = magnitude + strength
        fade = fg_x
        rfo = mix(R[1], R[0], clamp(gul_x + 0.5, 0.0, 1.0)) * rmult
        new_mask = ease_out(smooth_start(sloping * O[1], rfo * O[1]))
        combi = pow_inv(combi, float(ero['detail'])) * new_mask
        ridge_fade = mix(ridge_fade, gul_x, ridge_mask)
        ridge_mask = ridge_mask * ease_out(sloping * O[3])
        strength *= ero['gain']
        freq *= ero['lacunarity']
        rmult *= R[3]
    if debug == 'combiMask':
        return Vec(combi, 0.0, 0.0, 0.0)
    if debug == 'sloping':
        return Vec(last_sloping, 0.0, 0.0, 0.0)
    if debug == 'gulX':
        return Vec(last_gul, 0.0, 0.0, 0.0)
    dh = hx - in_x
    ridge = ridge_fade * (1.0 - ridge_mask)
    offset = mix(float(hoff[0]), -fade, float(hoff[1]))
    return Vec(in_x + dh + offset * magnitude, hy, hz, ridge)
