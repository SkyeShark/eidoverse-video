"""tests/post_era/ref_era.py: era_looks.js transcribed line for line into numpy, for one frame, to check the compositor
port against an independent reading of the same shader. Test code, not a port.

Covers the looks whose maths is deterministic: sepia, deco (+ sunburst), bw, vector, vfd, amber, mac, websafe, c64
(+ raster), riso, kuwahara, feature, ascii, scan, vignette, and the pixel grid (px). Left out: the integer-hash noise
(glitch tears, grain, flicker, the halation grain: Blender's White Noise is a different hash with the same spread),
the blur pyramids (halation glow, CRT glass glow, watercolour) and the display-space looks (halftone, toon,
watercolor), which the renders are judged on instead.

Images are top-down float arrays (H, W, C) in scene-linear light, uv is y DOWN (the WebGPU pass's own), sampling is
bilinear with clamped edges at texel centres, as a WebGPU texture with ClampToEdge and LinearFilter.
"""
import numpy as np

LUM = np.array([0.2126, 0.7152, 0.0722])
RAMP = ' .:-=+*#%@'
C64 = ['#000000', '#FFFFFF', '#880000', '#AAFFEE', '#CC44CC', '#00CC55', '#0000AA', '#EEEE77',
       '#DD8855', '#664400', '#FF7777', '#333333', '#777777', '#AAFF66', '#0088FF', '#BBBBBB']
COLOUR_LOOKS = ['sepia', 'deco', 'bw', 'vector', 'vfd', 'amber', 'mac', 'c64', 'websafe', 'riso', 'halftone', 'toon',
                'watercolor']


def lin(h):
    """THREE.Color(hex): sRGB -> linear."""
    h = h.lstrip('#')
    c = np.array([int(h[i:i + 2], 16) / 255.0 for i in (0, 2, 4)])
    return np.where(c < 0.04045, c * 0.0773993808, (c * 0.9478672986 + 0.0521327014) ** 2.4)


PAL = np.array([lin(h) for h in C64])


def smoothstep(e0, e1, x):
    t = np.clip((x - e0) / (e1 - e0), 0.0, 1.0)
    return t * t * (3.0 - 2.0 * t)


def step(edge, x):
    return (x >= edge).astype(np.float64)


def fract(x):
    return x - np.floor(x)


def mix(a, b, t):
    return a + (b - a) * t


def sample(img, u, v):
    """img (H, W, C) top-down at uv (y down): bilinear, edges clamped."""
    H, W = img.shape[:2]
    x, y = u * W - 0.5, v * H - 0.5
    x0, y0 = np.floor(x), np.floor(y)
    fx, fy = (x - x0)[..., None], (y - y0)[..., None]
    xa, xb = np.clip(x0, 0, W - 1).astype(int), np.clip(x0 + 1, 0, W - 1).astype(int)
    ya, yb = np.clip(y0, 0, H - 1).astype(int), np.clip(y0 + 1, 0, H - 1).astype(int)
    return (img[ya, xa] * (1 - fx) * (1 - fy) + img[ya, xb] * fx * (1 - fy) + img[yb, xa] * (1 - fx) * fy
            + img[yb, xb] * fx * fy)


def bayer4(px, py):
    def b2(a, b):
        return a * 2.0 + b * 3.0 - a * b * 4.0
    lo = b2(np.mod(px, 2.0), np.mod(py, 2.0))
    hi = b2(np.mod(np.floor(px / 2.0), 2.0), np.mod(np.floor(py / 2.0), 2.0))
    return (lo * 4.0 + hi + 0.5) / 16.0


def era(frame_rgb, w, t, atlas=None):
    """The era pass on one frame. frame_rgb: (H, W, 3) linear; w: {weight: value} (px included); t: seconds;
    atlas: the glyph atlas (h, w) top-down, 0..1, for ascii. Returns (H, W, 3)."""
    tex = frame_rgb.astype(np.float64)
    H, W = tex.shape[:2]
    S = H / 1080.0
    g = lambda k: float(w.get(k, 0.0))                                       # noqa: E731
    yy, xx = np.mgrid[0:H, 0:W].astype(np.float64)
    u0, v0 = (xx + 0.5) / W, (yy + 0.5) / H
    fcx, fcy = u0 * W, v0 * H
    px = max(g('px') if 'px' in w else 1.0, 1.0)
    cx, cy = px / W, px / H
    on = 1.0 if px >= 1.5 else 0.0
    su = mix(u0, (np.floor(u0 / cx) + 0.5) * cx, on)
    sv = mix(v0, (np.floor(v0 / cy) + 0.5) * cy, on)
    pix_x, pix_y = np.floor(fcx / px), np.floor(fcy / px)
    if g('glitch') or g('halation') or g('phosphor'):
        raise ValueError('ref_era: glitch, halation and phosphor are not in the reference')
    ca = g('riso') * 0.0035
    base = sample(tex, su, sv)
    split = np.stack([sample(tex, su + ca, sv)[..., 0], base[..., 1], sample(tex, su - ca, sv)[..., 2]], -1)
    col = mix(base, split, min(g('glitch') + g('riso'), 1.0))
    if g('kuwahara') > 0.001:
        best = np.zeros_like(col)
        best_var = np.full(col.shape[:2], 1e9)
        R = 3
        for sx, sy in ((-1, -1), (1, -1), (-1, 1), (1, 1)):
            acc = np.zeros_like(col)
            acc2 = np.zeros(col.shape[:2])
            for j in range(R + 1):
                for i in range(R + 1):
                    c = sample(tex, u0 + sx * i * 2.6 * S / W, v0 + sy * j * 2.6 * S / H)
                    lc = c @ LUM
                    acc += c
                    acc2 += lc * lc
            n = (R + 1) ** 2
            mean = acc / n
            lm = mean @ LUM
            var = acc2 / n - lm * lm
            better = step(var, best_var)[..., None]
            best = mix(best, mean, better)
            best_var = np.minimum(best_var, var)
        col = mix(col, best, g('kuwahara'))
    lum = col @ LUM
    plum = np.sqrt(np.clip(lum, 0.0, 1.0))
    thr = bayer4(pix_x, pix_y)
    looks = {}
    looks['sepia'] = np.stack([lum * 1.10, lum * 0.86, lum * 0.58], -1)
    dk = smoothstep(0.08, 0.95, plum)[..., None]
    looks['deco'] = mix(np.array([0.03, 0.018, 0.01]), np.array([1.05, 0.72, 0.30]), dk) * mix(0.6, 1.35, dk)
    looks['bw'] = np.stack([lum, lum, lum], -1)
    looks['vector'] = np.stack([lum * 0.18, lum * 1.30, lum * 0.38], -1)
    looks['vfd'] = np.stack([lum * 0.30, lum * 1.20, lum * 1.02], -1)
    looks['amber'] = np.stack([lum * 1.30, lum * 0.70, lum * 0.10], -1)
    bit = step(thr, plum)
    looks['mac'] = np.stack([bit, bit, bit], -1) * 0.92
    q = np.floor(np.sqrt(np.clip(col, 0.0, 1.0)) * 5.0 + thr[..., None]) / 5.0
    looks['websafe'] = q * q
    pc = np.sqrt(np.clip(col, 0.0, 1.0)) + ((thr - 0.5) * 0.12)[..., None]
    bestc = np.broadcast_to(PAL[0], pc.shape).copy()
    bd = ((pc - PAL[0]) ** 2).sum(-1)
    for p in PAL[1:]:
        d = ((pc - p) ** 2).sum(-1)
        better = step(d, bd)[..., None]
        bestc = mix(bestc, p, better)
        bd = np.minimum(bd, d)
    looks['c64'] = bestc * bestc
    paper = np.array([0.93, 0.9, 0.84])
    rx = (fcx * 0.866 - fcy * 0.5) / (6.0 * S)
    ry = (fcx * 0.5 + fcy * 0.866) / (6.0 * S)
    halft = np.sqrt((fract(rx) - 0.5) ** 2 + (fract(ry) - 0.5) ** 2)
    mid = smoothstep(0.08, 0.5, plum) * (1 - smoothstep(0.55, 0.95, plum))
    dotsA = step(halft, mid * 0.62)[..., None]
    lumB = sample(tex, u0 + 0.004, v0 - 0.0028) @ LUM
    shadow = 1 - smoothstep(0.12, 0.42, np.sqrt(np.clip(lumB, 0.0, 1.0)))
    dotsB = step(thr * 0.9, shadow)[..., None]
    looks['riso'] = paper * mix(np.ones(3), np.array([1.0, 0.36, 0.62]), dotsA * 0.9) \
        * mix(np.ones(3), np.array([0.08, 0.2, 0.62]), dotsB * 0.92)
    for k in ('halftone', 'toon', 'watercolor'):
        if g(k):
            raise ValueError(f'ref_era: {k} is not in the reference')
        looks[k] = np.zeros_like(col)
    ws = sum(g(k) for k in COLOUR_LOOKS)
    norm = max(ws, 1.0)
    outc = col * min(max(1.0 - ws, 0.0), 1.0)
    for k in COLOUR_LOOKS:
        outc = outc + looks[k] * (g(k) / norm)
    # deco sunburst
    dx, dy = (u0 - 0.5) * (W / H), v0 + 0.15
    ang = np.arctan2(dy, dx)
    rays = step(0.5, fract(ang * (24.0 / 6.2832)))
    outc = outc * mix(1.0, mix(0.78, 1.12, rays), g('deco') * 0.5)[..., None]
    # raster bars
    if g('raster'):
        bars = np.zeros_like(col)
        ramp = [np.array(c) for c in ((0.0, 0.0, 0.67), (0.0, 0.53, 1.0), (0.67, 1.0, 0.93), (1.0, 1.0, 1.0))]
        for i in range(5):
            cyb = 0.5 + 0.36 * np.sin(t * 1.25 + i * 0.62)
            k = np.exp(-((v0 - cyb) / 0.032) ** 2)
            band = np.floor(k * 3.99)[..., None]
            c = mix(mix(ramp[0], ramp[1], step(1.0, band)), mix(ramp[2], ramp[3], step(3.0, band)), step(2.0, band))
            bars = np.maximum(bars, c * step(0.05, k)[..., None])
        dark = 1 - smoothstep(0.015, 0.07, lum)
        outc = mix(outc, bars * bars, (dark * g('raster'))[..., None])
    # feature map
    if g('feature'):
        o = 1.5 * S

        def L(ddx, ddy):
            return sample(tex, u0 + ddx * o / W, v0 + ddy * o / H) @ LUM
        gx = L(1, -1) + L(1, 0) * 2 + L(1, 1) - L(-1, -1) - L(-1, 0) * 2 - L(-1, 1)
        gy = L(-1, 1) + L(0, 1) * 2 + L(1, 1) - L(-1, -1) - L(0, -1) * 2 - L(1, -1)
        mag = np.clip(np.sqrt(gx * gx + gy * gy) * 3.0, 0.0, 1.0)
        a = np.arctan2(gy, gx) / 6.2832 + 0.5
        hue = np.stack([np.abs(a * 6 - 3) - 1, 2 - np.abs(a * 6 - 2), 2 - np.abs(a * 6 - 4)], -1)
        edge = np.clip(hue, 0.0, 1.0) * (mag * 2.2)[..., None]
        tile = step(0.97, np.maximum(fract(fcx / (64 * S)), fract(fcy / (64 * S))))
        field = (np.floor(plum * 4.0) / 4.0 * 0.22)[..., None] * np.array([0.5, 0.35, 0.9])
        feat = field + edge + np.array([0.1, 0.08, 0.2]) * tile[..., None]
        outc = mix(outc, feat, g('feature'))
    # line printer
    if g('ascii'):
        csx, csy = 12.0 * S, 20.0 * S
        cix, ciy = np.floor(fcx / csx), np.floor(fcy / csy)
        clx, cly = fract(fcx / csx), fract(fcy / csy)
        L2 = sample(tex, (cix + 0.5) * csx / W, (ciy + 0.5) * csy / H) @ LUM
        gi = np.floor(np.clip(1 - np.sqrt(np.clip(L2, 0.0, 1.0)) * 1.1, 0.0, 0.999) * len(RAMP))
        ink = sample(atlas[..., None], (gi + clx) / len(RAMP), cly)[..., 0]     # the glyph upright: its top up
        bar = np.mod(np.floor(ciy / 3.0), 2.0)[..., None]
        pap = mix(np.array([0.95, 0.95, 0.9]), np.array([0.8, 0.9, 0.78]), bar)
        holes = np.clip(step(fcx, 22.0 * S) + step(W - 22.0 * S, fcx), 0, 1)
        hx, hy = np.mod(fcx, 22.0 * S) - 11.0 * S, np.mod(fcy, 26.0 * S) - 13.0 * S
        hole = (step(np.sqrt(hx * hx + hy * hy), 5.0 * S) * holes)[..., None]
        printed = mix(pap, np.array([0.06, 0.06, 0.09]), ink[..., None] * (1 - hole))
        outc = mix(outc, mix(printed, np.full(3, 0.02), hole), g('ascii'))
    # film layers (grain and flicker are hashes: not in the reference)
    sl = np.abs(fract(v0 * H * 0.5) - 0.5) * 2.0
    outc = outc * (1.0 - g('scan') * 0.38 * sl)[..., None]
    r = np.sqrt((u0 - 0.5) ** 2 + (v0 - 0.5) ** 2) * 1.35
    outc = outc * mix(1.0, 1.0 - smoothstep(0.35, 1.05, r), g('vignette'))[..., None]
    return outc
