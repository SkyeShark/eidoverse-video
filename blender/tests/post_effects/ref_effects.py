"""tests/post_effects/ref_effects.py: the WebGPU post effects in numpy, transcribed from eidoverse/effects_tsl/<name>.js
(and three's LensflareNode / AnamorphicNode / depthAwareBlend) independently of the Blender port, for parity checks.

Images are top-down (row 0 at the top) as the WebGPU passes saw them; uv is theirs (y down, pixel centres). Depth is
Blender's metric Depth pass (WebGPU's perspectiveDepthToViewZ of its depth buffer); normals are the world-space Normal
pass, turned to view space with the camera's axes where the shader reads view-space normals, the background being
WebGPU's cleared buffer decoded (-1, -1, -1) in view space. Effects whose noise is a fract(sin(x) * 43758)-style hash of
large arguments (jitter, hash_blur, vhs_tape, rain_on_camera, depth_fog's noise, blueprint's grain) differ in float
detail between any two GPUs and from float64; those are checked by structure, not here (or with the noise off).
"""
import math

import numpy as np

TAU = 2.0 * math.pi
LUM709 = np.array([0.2126, 0.7152, 0.0722])
LUM601 = np.array([0.299, 0.587, 0.114])


def grid(H, W):
    yy, xx = np.mgrid[0:H, 0:W].astype(np.float64)
    return (xx + 0.5) / W, (yy + 0.5) / H


def sample(img, u, v):
    """img (H, W, C) top-down at uv (y down): bilinear, edges clamped (ClampToEdge)."""
    H, W = img.shape[:2]
    x, y = u * W - 0.5, v * H - 0.5
    x0, y0 = np.floor(x), np.floor(y)
    fx, fy = (x - x0)[..., None], (y - y0)[..., None]
    xa, xb = np.clip(x0, 0, W - 1).astype(int), np.clip(x0 + 1, 0, W - 1).astype(int)
    ya, yb = np.clip(y0, 0, H - 1).astype(int), np.clip(y0 + 1, 0, H - 1).astype(int)
    return (img[ya, xa] * (1 - fx) * (1 - fy) + img[ya, xb] * fx * (1 - fy) + img[yb, xa] * (1 - fx) * fy
            + img[yb, xb] * fx * fy)


def sample_wrap(img, u, v):
    """Bilinear with RepeatWrapping (a DataTexture with wrapS/T Repeat, LinearFilter)."""
    H, W = img.shape[:2]
    x, y = u * W - 0.5, v * H - 0.5
    x0, y0 = np.floor(x), np.floor(y)
    fx, fy = (x - x0)[..., None], (y - y0)[..., None]
    xa, xb = np.mod(x0, W).astype(int), np.mod(x0 + 1, W).astype(int)
    ya, yb = np.mod(y0, H).astype(int), np.mod(y0 + 1, H).astype(int)
    return (img[ya, xa] * (1 - fx) * (1 - fy) + img[ya, xb] * fx * (1 - fy) + img[yb, xa] * (1 - fx) * fy
            + img[yb, xb] * fx * fy)


def sample_nearest(img, u, v):
    H, W = img.shape[:2]
    xi = np.clip(np.floor(u * W), 0, W - 1).astype(int)
    yi = np.clip(np.floor(v * H), 0, H - 1).astype(int)
    return img[yi, xi]


def smoothstep(e0, e1, x):
    t = np.clip((x - e0) / (e1 - e0), 0.0, 1.0)
    return t * t * (3.0 - 2.0 * t)


def step(edge, x):
    return (x >= edge).astype(np.float64)


def fract(x):
    return x - np.floor(x)


def mix(a, b, t):
    return a + (b - a) * t


def safe_pow(b, e):
    """Blender's Math Power on a negative base and a fractional exponent is 0 (WebGPU's NaN there is clamped away)."""
    b = np.asarray(b, np.float64)
    return np.where(b > 0, np.abs(b) ** e, np.where(b == 0, 0.0, 0.0))


def finish(src, rgb, alpha, opacity):
    """mix(orig, vec4(rgb, alpha), opacity) as (H, W, 4)."""
    out = np.empty(src.shape[:2] + (4,))
    out[..., :3] = src[..., :3] + (rgb - src[..., :3]) * opacity
    out[..., 3] = src[..., 3] + (alpha - src[..., 3]) * opacity
    return out


class Cam:
    """The source camera: world axes (Blender), position, tan(fov_y / 2) as the frame renders it, near, far."""

    def __init__(self, m):
        M = np.array(m['matrix'], np.float64)
        self.x, self.y, self.z, self.pos = M[:3, 0], M[:3, 1], M[:3, 2], M[:3, 3]
        W, H = m['res']
        if m['sensor_fit'] == 'VERTICAL':
            self.tan_y = m['sensor_height'] / (2 * m['lens'])
        elif m['sensor_fit'] == 'HORIZONTAL' or W >= H:
            self.tan_y = m['sensor_width'] / (2 * m['lens']) * H / W
        else:
            self.tan_y = m['sensor_width'] / (2 * m['lens'])
        self.near, self.far = m['clip_start'], m['clip_end']

    def view(self, n):
        """World normals (H, W, 3) -> view space; the background (0) -> (-1, -1, -1), WebGPU's cleared buffer."""
        nv = np.stack([n @ self.x, n @ self.y, n @ self.z], -1)
        bg = (n * n).sum(-1) < 1e-8
        nv[bg] = -1.0
        return nv


# ------------------------------------------------------------------------------------------------- melt
def rgb2hsv(c):
    r, g, b = c[..., 0], c[..., 1], c[..., 2]
    s1 = step(b, g)
    px, py, pz, pw = mix(b, g, s1), mix(g, b, s1), mix(-1.0, 0.0, s1), mix(2.0 / 3.0, -1.0 / 3.0, s1)
    s2 = step(px, r)
    qx, qy, qz, qw = mix(px, r, s2), py, mix(pw, pz, s2), mix(r, px, s2)
    d = qx - np.minimum(qw, qy)
    e = 1e-10
    return np.abs(qz + (qw - qy) / (d * 6.0 + e)), d / (qx + e), qx


def melt(src, t, speed=0.7, swirl=0.2, opacity=1.0):
    H, W = src.shape[:2]
    u, v = grid(H, W)
    c = src[..., :3]
    h, s, _ = rgb2hsv(c)
    ang = h + np.arctan2(v - 0.5, u - 0.5) + t * 0.1
    radius = math.log(max(math.sin(t * speed) * 0.5 + 0.3, 0.0) * swirl + 1.0)
    col = sample(src, u + np.cos(ang) * radius * s, v + np.sin(ang) * radius * s)[..., :3]
    return finish(src, col, src[..., 3], opacity)


# ------------------------------------------------------------------------------------------------- crt
def crt(src, t, opacity=1.0):
    H, W = src.shape[:2]
    u, v = grid(H, W)
    c0x, c0y = (u - 0.5) * 2.2, (v - 0.5) * 2.2
    c1x, c1y = c0x * (1 + (np.abs(c0y) / 5) ** 2), c0y * (1 + (np.abs(c0x) / 4) ** 2)
    cx, cy = (c1x / 2 + 0.5) * 0.92 + 0.04, (c1y / 2 + 0.5) * 0.92 + 0.04
    x = np.sin(t * 0.3 + cy * 21) * np.sin(t * 0.7 + cy * 29) * np.sin(t * 0.33 + 0.3 + cy * 31) * 0.0017
    sR = sample(src, x + cx + 0.001, cy + 0.001)[..., 0] + 0.05
    sG = sample(src, x + cx, cy - 0.002)[..., 1] + 0.05
    sB = sample(src, x + cx - 0.002, cy)[..., 2] + 0.05
    aR = sample(src, (x + 0.025) * 0.75 + cx + 0.001, -0.027 * 0.75 + cy + 0.001)[..., 0]
    aG = sample(src, (x - 0.022) * 0.75 + cx, -0.020 * 0.75 + cy - 0.002)[..., 1]
    aB = sample(src, (x - 0.020) * 0.75 + cx - 0.002, -0.018 * 0.75 + cy)[..., 2]
    col = np.stack([sR + aR * 0.08, sG + aG * 0.05, sB + aB * 0.08], -1)
    col = np.clip(col * 0.6 + col * col * 0.4, 0, 1)
    vig = 16 * cx * cy * (1 - cx) * (1 - cy)
    col = col * (np.maximum(vig, 0) ** 0.3)[..., None]
    col = col * np.array([0.95, 1.05, 0.95]) * 2.8
    scans = np.clip(0.35 + 0.35 * np.sin(t * 3.5 + cy * H * 1.5), 0, 1)
    col = col * (0.4 + scans ** 1.7 * 0.7)[..., None]
    col = col * (1 + 0.01 * math.sin(t * 110))
    inside = step(0, cx) * step(cx, 1) * step(0, cy) * step(cy, 1)
    grille = np.clip((np.mod(np.floor(u * W), 2) - 1) * 2, 0, 1)
    col = col * (inside * (1 - grille * 0.65))[..., None]
    return finish(src, col, 1.0, opacity)


# ------------------------------------------------------------------------------------------------- chromatic alpha
def chromatic_aberration_alpha(src, amount=0.005, angle=0.0, opacity=1.0):
    H, W = src.shape[:2]
    u, v = grid(H, W)
    ox, oy = math.cos(angle) * amount, math.sin(angle) * amount
    cr, cg, cb = sample(src, u + ox, v + oy), src, sample(src, u - ox, v - oy)
    r = mix(cg[..., 0], cr[..., 0], cr[..., 3])
    b = mix(cg[..., 2], cb[..., 2], cb[..., 3])
    a = np.maximum(cr[..., 3], np.maximum(cg[..., 3], cb[..., 3]))
    return finish(src, np.stack([r, cg[..., 1], b], -1), a, opacity)


# ------------------------------------------------------------------------------------------------- full toon
def full_toon(src, dep, nrm, cam, o):
    H, W = src.shape[:2]
    u, v = grid(H, W)
    g = lambda k, d: o.get(k, d)                                                    # noqa: E731
    far = cam.far
    zimg = np.clip(dep, 0.0, far)[..., None]
    nview = cam.view(nrm)

    def lin(du, dv):
        z = sample(zimg, u + du, v + dv)[..., 0]
        return z * 2.0 / (z + far)
    dC = np.maximum(lin(0, 0), 1e-4)
    rad = g('smooth_radius', 3.0)
    acc, ws = 0.0, 0.0
    for ox, oy, kw in ((-1, -1, 1), (0, -1, 2), (1, -1, 1), (-1, 0, 2), (0, 0, 4), (1, 0, 2), (-1, 1, 1), (0, 1, 2),
                       (1, 1, 1)):
        du, dv = ox * rad / W, oy * rad / H
        w = (1 - smoothstep(0.001, 0.02, np.abs(lin(du, dv) - dC))) * kw
        acc = acc + sample(src, u + du, v + dv)[..., :3] * w[..., None]
        ws = ws + w
    sm = acc / np.maximum(ws, 1e-4)[..., None]
    L = np.maximum(mix(g('near_levels', 4.0), g('far_levels', 2.0), np.clip(dC, 0, 1)), 1.0)
    lum = np.clip(sm @ LUM601, 0, 1)
    adj = np.clip((lum - 0.5) * g('contrast', 1.0) + 0.5, 0, 1)
    s = adj * L
    stepped = (np.floor(s) + smoothstep(0.0, max(g('band_softness', 0.015), 1e-4), fract(s))) / L
    raw = np.clip(sm * (stepped / np.maximum(lum, 1e-3))[..., None], 0, 1.5)
    base = np.clip(mix((raw @ LUM601)[..., None], raw, g('saturation', 1.4)), 0, 1.5)
    sh, mi, hi = (np.array(g(k, d)) for k, d in (('shadow_tint', (0.16, 0.20, 0.42)),
                                                  ('midtone_tint', (0.52, 0.48, 0.56)),
                                                  ('highlight_tint', (1.00, 0.96, 0.88))))
    st = stepped[..., None]
    low, high = mix(sh, mi, smoothstep(0.0, 0.5, st)), mix(mi, hi, smoothstep(0.5, 1.0, st))
    tint = mix(low, high, step(0.5, st))
    mult = tint / np.maximum(tint @ LUM601, 1e-3)[..., None]
    cel = base * mix(np.ones(3), mult, g('hue_shift', 0.0))
    d = {(x, y): lin(x / W, y / H) for x in (-1, 0, 1) for y in (-1, 0, 1) if (x, y) != (0, 0)}
    dD = (np.abs(d[(0, -1)] - d[(0, 1)]) + np.abs(d[(1, 0)] - d[(-1, 0)]) + np.abs(d[(-1, -1)] - d[(1, 1)])
          + np.abs(d[(1, -1)] - d[(-1, 1)])) / dC
    n = {(x, y): sample(nview, u + x / W, v + y / H) for x in (-1, 0, 1) for y in (-1, 0, 1) if (x, y) != (0, 0)}
    dN = 0.0
    for p, q in (((0, -1), (0, 1)), ((1, 0), (-1, 0)), ((-1, -1), (1, 1)), ((1, -1), (-1, 1))):
        dN = dN + np.maximum(0.0, 1.0 - (n[p] * n[q]).sum(-1))
    sig = g('outline_depth_weight', 0.5) * dD + g('outline_normal_weight', 1.0) * dN
    edge = np.clip(np.maximum(sig - g('outline_threshold', 0.5), 0) ** g('outline_sharpness', 5.0)
                   * g('outline_strength', 1.0), 0, 1)
    inked = np.clip(mix(cel, np.array(g('outline_color', (0.05, 0.05, 0.08))), edge[..., None]), 0, 1)
    return finish(src, inked, src[..., 3], g('opacity', 1.0))


# ------------------------------------------------------------------------------------------------- blueprint
def blueprint(src, dep, nrm, cam, o):
    """paper_grain must be 0 for parity (its hash is float-detail noise)."""
    H, W = src.shape[:2]
    u, v = grid(H, W)
    g = lambda k, d: o.get(k, d)                                                    # noqa: E731
    far = cam.far
    zimg = np.clip(dep, 0.0, far)[..., None]
    nv2 = cam.view(nrm) * 2.0 - 1.0                          # decoded twice, as blueprint.js does

    def D(x, y):
        z = sample(zimg, u + x / W, v + y / H)[..., 0]
        return z * 2.0 / (z + far)

    def N(x, y):
        return sample(nv2, u + x / W, v + y / H)
    dC = np.maximum(D(0, 0), 1e-4)
    d = {(x, y): D(x, y) for x in (-1, 0, 1) for y in (-1, 0, 1) if (x, y) != (0, 0)}
    dD = (np.abs(d[(0, -1)] - d[(0, 1)]) + np.abs(d[(1, 0)] - d[(-1, 0)]) + np.abs(d[(-1, -1)] - d[(1, 1)])
          + np.abs(d[(1, -1)] - d[(-1, 1)])) / dC
    n = {(x, y): N(x, y) for x in (-1, 0, 1) for y in (-1, 0, 1)}
    dN = 0.0
    for p, q in (((0, -1), (0, 1)), ((1, 0), (-1, 0)), ((-1, -1), (1, 1)), ((1, -1), (-1, 1))):
        dN = dN + np.maximum(0.0, 1.0 - (n[p] * n[q]).sum(-1))
    rim = safe_pow(1.0 - np.abs(n[(0, 0)][..., 2]), g('rim_sharpness', 2.4))
    es, th, sh = g('edge_strength', 1.8), g('threshold', 0.035), g('sharpness', 1.4)
    outline = np.clip(np.maximum(g('depth_weight', 0.6) * dD - th, 0) * es, 0, None) ** sh
    outline = np.clip(outline, 0, 1)
    nedge = np.clip(np.clip(np.maximum(g('normal_weight', 1.0) * dN - th, 0) * es, 0, None) ** sh, 0, 1)
    rim_ink = np.clip(rim * g('rim_weight', 0.95), 0, 1)
    fx, fy = u * W, v * H

    def dist(p):
        mx, my = fract(fx / p) * p, fract(fy / p) * p
        return np.minimum(np.minimum(mx, p - mx), np.minimum(my, p - my))
    lw, lw5, cell = g('minor_line_w', 1.0), g('major_line_w', 2.0), g('cell_px', 22.0)
    gl = smoothstep(lw * 0.5 + 0.5, lw * 0.5 - 0.5, dist(cell))
    gl5 = smoothstep(lw5 * 0.5 + 0.5, lw5 * 0.5 - 0.5, dist(cell * g('major_every', 5.0)))
    paper, gcol, ink = (np.array(g(k, d)) for k, d in (('paper_color', (0.04, 0.12, 0.30)),
                                                       ('grid_color', (0.12, 0.23, 0.46)),
                                                       ('ink_color', (0.93, 0.97, 1.0))))
    out = mix(paper, gcol, (gl * g('grid_strength', 1.0))[..., None])
    out = mix(out, gcol, (gl5 * g('major_strength', 1.0))[..., None])
    line = smoothstep(g('shade_line_width', 0.86), 0.99, np.abs(np.cos(v * H * math.pi / g('shade_stripe_px', 5.0))))
    checker = np.mod(np.floor(fx) + np.floor(fy), 2)
    lum = src[..., :3] @ LUM601
    hot = smoothstep(g('shade_mid', 0.45), g('shade_mid', 0.45) + 0.10, lum)
    cut = mix(1.0, checker, smoothstep(0.6, 0.95, lum))
    interior = np.maximum(nedge, np.maximum(rim_ink, hot)) * line * cut
    out = mix(out, ink, np.clip(np.maximum(outline, interior), 0, 1)[..., None])
    hsh = fract(np.sin(u * 127.1 + v * 311.7) * 43758.5453)
    out = out + ((hsh - 0.5) * g('paper_grain', 0.025))[..., None]
    r2 = ((u - 0.5) ** 2 + (v - 0.5) ** 2) * 2.0
    out = np.clip(out * (1 - g('vignette', 0.55) * r2)[..., None], 0, 1)
    return finish(src, out, src[..., 3], g('opacity', 1.0))


# ------------------------------------------------------------------------------------------------- cross hatch
def hatch_noise():
    """getNoiseTexture(): the 256 x 256 RGBA LCG bytes, rows top-down as the DataTexture held them (JS doubles)."""
    n = 256 * 256 * 4
    out = np.empty(n, np.uint8)
    s = 0x12345678
    for i in range(n):
        x = int(float(s) * 1103515245.0 + 12345.0) % (1 << 32)
        s = x - (1 << 32) if x >= (1 << 31) else x
        out[i] = (x >> 16) & 0xff
    return out.reshape(256, 256, 4).astype(np.float64) / 255.0


def cross_hatch(src, dep, nrm, cam, t, o, noise=None):
    H, W = src.shape[:2]
    u, v = grid(H, W)
    g = lambda k, d: o.get(k, d)                                                    # noqa: E731
    nz = hatch_noise() if noise is None else noise
    wig, flk = g('wiggle', 1.0), g('flicker', 1.0)
    far = cam.far

    def get_rand(px, py):                                     # uvSmooth(pos / 256, 256), wrapped, linear
        uu = px / 256.0 + np.sin(px / 256.0 * 256.0 * TAU) * 0.6 / TAU / 256.0
        vv = py / 256.0 + np.sin(py / 256.0 * 256.0 * TAU) * 0.6 / TAU / 256.0
        return sample_wrap(nz, uu, vv)

    def get_col(px, py, ramp, rsc, sc):
        r1 = (get_rand(px * 0.05 * rsc / sc + t * 131.0 * flk, py * 0.05 * rsc / sc + t * 131.0 * flk) - 0.5) \
            * 10 * ramp * wig
        return sample(src, (px + r1[..., 0] * sc) / W, (py + r1[..., 1] * sc) / H)

    def get_val(px, py, ramp, rsc, sc):
        c = get_col(px, py, ramp, rsc, sc)[..., :3]
        tm = c / (c + 1.0)
        return np.clip(tm @ np.array([0.333, 0.333, 0.333]), 0, 1)
    fx, fy = u * W, v * H
    sc = max(W / 600.0, 0.5)
    sq = math.sqrt(sc)
    rpx, rpy = fx * 1.2 / sq, fy * 1.2 / sq
    r = get_rand(rpx, rpy) - get_rand(rpx + 1.5, rpy - 1.5)
    r2 = get_rand(rpx, rpy)
    zimg = np.clip(dep, 0.0, far)[..., None]

    def z(x, y):
        return sample(zimg, u + x / W, v + y / H)[..., 0]
    dC = np.maximum(z(0, 0), 1e-4)
    d = {(x, y): z(x, y) for x in (-1, 0, 1) for y in (-1, 0, 1) if (x, y) != (0, 0)}
    dD = (np.abs(d[(0, -1)] - d[(0, 1)]) + np.abs(d[(1, 0)] - d[(-1, 0)]) + np.abs(d[(-1, -1)] - d[(1, 1)])
          + np.abs(d[(1, -1)] - d[(-1, 1)])) / dC
    th = g('depth_outline_thresh', 0.05)
    depth_edge = smoothstep(th, th * 8.0, dD)
    br = 0.0
    for i in range(3):
        fi = i / 2.0
        tt = 0.03 + fi * 0.25
        wb = tt * 2.0
        for ramp, rsc, w0, w1 in ((0.15 * 1.3 ** (fi * 5), 1.7 * 1.3 ** (-fi * 5), 0.6, 0.5 + fi),
                                  (0.30 * 1.3 ** (fi * 5), 10.7 * 1.3 ** (-fi * 5), 0.4, 0.2 + fi)):
            eps = sc * 0.4
            gx = get_val(fx + eps, fy, ramp, rsc, sc) - get_val(fx - eps, fy, ramp, rsc, sc)
            gy = get_val(fx, fy + eps, ramp, rsc, sc) - get_val(fx, fy - eps, ramp, rsc, sc)
            glen = np.sqrt(gx * gx + gy * gy) / eps / 2.0 * sc
            br = br + smoothstep(tt - wb * 0.5, tt + wb * 0.5, glen) * (w0 * w1)
    jit = 0.5 + r2[..., 2] * 0.5
    total = np.clip(br * g('outline_strength', 1.4) * 0.7 * jit + depth_edge * g('depth_outline_strength', 0.9) * jit,
                    0, 0.6)
    col = np.clip(1.0 - total, 0, 1)[..., None] * np.ones(3)
    rj = get_rand(fx * 0.02 + t * 1120.0, fy * 0.02 + t * 1120.0)[..., :2] - 0.5
    jk = 1.5 * sc * min(max(flk, -1.0), 1.0)
    val_jit = get_val(fx + rj[..., 0] * jk, fy + rj[..., 1] * jk, 0.0, 1.0, sc) * 1.7
    is_obj = 1.0 - smoothstep(far * 0.08, far * 0.18, dC)
    hatch, hatch2, hsum = 0.0, 0.0, 0.0
    alive = np.ones((H, W))
    for i in range(5):
        fi = float(i)
        if i >= 2:
            alive = alive * (1.0 - (fi > (1.0 - val_jit) * 5.0))
        ang = -0.5 - fi * fi * 0.08 + is_obj * (math.pi / 2)
        c0, c1 = np.cos(ang), np.cos(ang - 1.6)
        hx = (c0 * fx - c1 * fy) / sq * 0.05 * 1.3
        hy = (c1 * fx + c0 * fy) / sq * 1.3
        drift = t * 1003.123 * flk
        rh = get_rand(hx + np.sin(hy) + drift, hy + drift)
        contrib = 1.0 - smoothstep(0.5, 1.5, rh[..., 0] + val_jit) - np.abs(r[..., 2]) * 0.3
        hatch = hatch + contrib * alive
        hatch2 = np.where(alive > 0, np.maximum(hatch2, contrib), hatch2)
        hsum = hsum + alive
    nzv = (nrm @ cam.z) * 2.0 - 1.0
    boost = mix(1.2, 0.7, np.clip(np.abs(nzv), 0, 1))
    is_geo = 1.0 - smoothstep(far * 0.85, far * 0.99, dC)
    shade = mix(1.0, boost, is_geo)
    amount = np.clip(mix(hatch / np.maximum(hsum, 1e-4), hatch2, 0.5) * g('hatch_strength', 0.85) * shade, 0, 1)
    col = col * (1.0 - amount)[..., None]
    col = 1.0 - (1.0 - col) * 0.92
    col = col * (0.95 + r[..., 0:1] * 0.06 + r[..., :3] * 0.06)
    sx, sy = (fx - W * 0.5) / W, (fy - H * 0.5) / W
    vign = (1 - (sx * sx + sy * sy) * 0.15) * (1 - np.exp(np.sin(u * math.pi) * -40.0) * 0.3) \
        * (1 - np.exp(np.sin(v * math.pi) * -20.0) * 0.3)
    col = col * vign[..., None]
    col = mix(col, smoothstep(0.15, 0.85, col), 0.6)
    return finish(src, np.clip(col, 0, 1), 1.0, g('opacity', 1.0))


# ------------------------------------------------------------------------------------------------- underwater
def caustic2d(x, y, t):
    ppx, ppy = np.mod(x * TAU, TAU) - 250.0, np.mod(y * TAU, TAU) - 250.0
    tt = t * 0.5 + 23.0
    ix, iy, c = ppx, ppy, 1.0
    with np.errstate(divide='ignore', invalid='ignore'):
        for i in range(5):
            tn = tt * (1.0 - 3.5 / (i + 1))
            ix, iy = ppx + np.cos(tn - ix) + np.sin(tn + iy), ppy + np.sin(tn - iy) + np.cos(tn + ix)
            dx, dy = np.sin(ix + tn) / 0.005, np.cos(iy + tn) / 0.005
            ln = np.sqrt((ppx / dx) ** 2 + (ppy / dy) ** 2)
            c = c + np.where(np.isfinite(ln) & (ln > 0), 1.0 / ln, 0.0)
    cf = 1.17 - (c / 5.0) ** 1.4
    return np.clip(np.abs(cf) ** 8, 0, 2)


def caustic1d(x, power, gt):
    pp = np.mod(x * TAU, TAU) - 250.0
    tt = gt * 0.5 + 23.0
    ii, c = pp, 1.0
    with np.errstate(divide='ignore', invalid='ignore'):
        for i in range(2):
            tn = tt * (1.0 - 3.5 / (i + 1))
            ii = pp + np.cos(tn - ii) + np.sin(tn + ii)
            q = np.abs(pp / (np.sin(ii + tn) / 0.005))
            c = c + np.where(np.isfinite(q) & (q > 0), 1.0 / q, 0.0)
    return 1.17 - (c / 5.0) ** power


def underwater(src, dep, nrm, cam, t, o, aspect):
    H, W = src.shape[:2]
    u, v = grid(H, W)
    g = lambda k, d: o.get(k, d)                                                    # noqa: E731
    z = np.clip(dep, cam.near, cam.far)
    vx, vy, vz = (u * 2 - 1) * cam.tan_y * aspect * z, (1 - v * 2) * cam.tan_y * z, -z
    dist = np.sqrt(vx * vx + vy * vy + vz * vz)
    world = cam.pos + cam.x * vx[..., None] + cam.y * vy[..., None] + cam.z * vz[..., None]
    d01 = cam.far * (z - cam.near) / (z * (cam.far - cam.near))
    is_far = np.clip((d01 - 0.999) * 1000.0, 0, 1)[..., None]
    px, py = u * 2 - 1, v * 2 - 1
    shallow, horizon = np.array(g('shallow_color', (0.18, 0.45, 0.55))), np.array(g('horizon_color', (0.0, 0.05, 0.2)))
    sky_mask = np.clip(0.8 * (1 - (py + 0.8) * 2.5), 0, 1)
    cs1, cs2 = caustic2d(px, py, t), caustic2d(px, py * 2.7, t)
    py4 = py ** 4
    sky = mix(shallow * sky_mask[..., None] + shallow * ((cs1 * 0.3 + cs2 * 0.3) * py4)[..., None], horizon,
              ((1 - py4) ** 20)[..., None])
    cs = g('caustic_scale', 0.5)
    cval = caustic2d((world[..., 0] + world[..., 2] * 0.2) * cs, (-world[..., 1] + world[..., 2] * 0.2) * cs, t)
    n_up = np.clip(nrm @ cam.y, 0, 1)
    fog = (1 - np.exp(-(dist ** g('fog_power', 1.0) * g('fog_density', 0.3))))[..., None]
    base = src[..., :3]
    scene_c = base * (cval * g('caustic_amt', 1.4) * n_up + 0.7)[..., None]
    out = mix(mix(scene_c, horizon, fog), sky, is_far)
    gr1 = np.abs(caustic1d((px + py * 0.08) / 1.7 + 0.5, 1.8, t * 0.65)) ** 10 * 0.05
    c2 = caustic1d(np.sin(px), 0.3, t * 0.7)
    gr2 = np.sign(c2) * np.abs(c2) ** 9 * 0.4
    gr3 = np.abs(caustic1d(np.cos(px * 2.3), 0.3, t * 1.3)) ** 4 * 0.1
    f1, f2 = ((1 + py) * 0.3) ** 2 * 0.2, ((1 + py) * 0.3) ** 3
    rays = np.clip(gr1 + gr2 + gr3 - f1 - f2, 0, 1) * g('godray_amt', 0.6)
    out = out + np.array([0.7, 1.0, 1.0]) * (rays * mix(np.linalg.norm(shallow), 1.0, py * py))[..., None]
    return finish(src, out, src[..., 3], g('opacity', 1.0))


# ------------------------------------------------------------------------------------------------- the flares
def lensflare(src, o):
    """three's LensflareNode as WebGPU ran it: the ghosts evaluated at the quarter-size target's pixel centres, read
    back bilinearly at full size."""
    H, W = src.shape[:2]
    g = lambda k, d: o.get(k, d)                                                    # noqa: E731
    Hq, Wq = int(round(H / 4)), int(round(W / 4))
    uq, vq = grid(Hq, Wq)
    tx, ty = 1 - uq, 1 - vq
    sp = g('ghost_spacing', 0.25)
    gx, gy = (0.5 - tx) * sp, (0.5 - ty) * sp
    tint = np.array(g('ghost_tint', (1.0, 1.0, 1.0)))
    acc = 0.0
    for i in range(max(1, int(g('ghost_samples', 4)))):
        su, sv = fract(tx + gx * i), fract(ty + gy * i)
        w = (1 - np.sqrt((su - 0.5) ** 2 + (sv - 0.5) ** 2)) ** g('ghost_attenuation', 25.0)
        acc = acc + np.maximum(sample(src, su, sv)[..., :3] - g('threshold', 4.0), 0) * tint * w[..., None]
    u, v = grid(H, W)
    flare = sample(acc, u, v)
    out = src[..., :3] + flare * g('strength', 0.4)
    return finish(src, out, src[..., 3], g('opacity', 1.0))


def anamorphic_flare(src, o):
    """three's AnamorphicNode: its threshold's luminance(color) is TSL's dot() of the RGBA sample with the vec3
    weights padded to vec4(w, 1.0) (WGSLNodeBuilder.format, checked under deno 11-08): Y + alpha."""
    H, W = src.shape[:2]
    u, v = grid(H, W)
    g = lambda k, d: o.get(k, d)                                                    # noqa: E731
    half = max(1, int(g('samples', 32))) // 2
    acc = 0.0
    for i in range(-half, half):
        soft = 1 - abs(i) / half
        s = sample(src, u + i * g('scale', 1.5) / W, v)
        c = s[..., :3]
        acc = acc + c * (np.maximum(c @ LUM709 + s[..., 3] - g('threshold', 3.0), 0) * soft)[..., None]
    out = src[..., :3] + acc * np.array(g('color', (0.1, 0.0, 1.0))) * g('strength', 0.6)
    return finish(src, out, src[..., 3], g('opacity', 1.0))


# ------------------------------------------------------------------------------------------------- round one's groups
# (y-dependent ones, checked for WebGPU's y-down uv: their centre, offsets and scroll direction)
def rgb_shift(src, amount=0.005, angle=0.0, opacity=1.0):
    H, W = src.shape[:2]
    u, v = grid(H, W)
    ox, oy = math.cos(angle) * amount, math.sin(angle) * amount
    r = sample(src, u + ox, v + oy)[..., 0]
    b = sample(src, u - ox, v - oy)[..., 2]
    return finish(src, np.stack([r, src[..., 1], b], -1), src[..., 3], opacity)


def glitch_bars(src, t, bar_freq=20.0, scroll_speed=3.0, shift=0.025, opacity=1.0):
    """(its shader writes vec4(col, 1.0): alpha mixes toward 1 by opacity)"""
    H, W = src.shape[:2]
    u, v = grid(H, W)
    bar = step(0.7, fract(v * bar_freq + t * scroll_speed))
    sh = bar * shift * np.sin(t * 12.0 + v * 50.0)
    r = sample(src, u + sh, v)[..., 0]
    b = sample(src, u - sh, v)[..., 2]
    return finish(src, np.stack([r, src[..., 1], b], -1), 1.0, opacity)


def radial_blur(src, center_x=0.5, center_y=0.5, weight=0.9, decay=0.95, exposure=1.5, count=32, opacity=1.0):
    H, W = src.shape[:2]
    u, v = grid(H, W)
    yy, xx = np.mgrid[0:H, 0:W].astype(np.float64)
    noise = fract(52.9829189 * fract((xx + 0.5) * 0.06711056 + (yy + 0.5) * 0.00583715))   # screenCoordinate
    du, dv = (center_x - u) / count, (center_y - v) / count
    su, sv = u + du * noise, v + dv * noise
    blur, w = 0.0, weight
    for _k in range(count):
        su, sv = su + du, sv + dv
        blur = blur + sample(src, su, sv)[..., :3] * w
        w *= decay
    blur = blur / count * exposure
    col = blur * 0.5 + src[..., :3]                              # mix(blur, base * 2, 0.5)
    return finish(src, col, src[..., 3], opacity)


# ------------------------------------------------------------------------------------------------- hash-noise effects
# (float64 here: compared after an 8x box downsample, where their per-pixel hash detail averages out)
def hash_blur(src, amount=0.05, repeats=45, opacity=1.0):
    H, W = src.shape[:2]
    u, v = grid(H, W)
    s = u + v
    acc = 0.0
    for i in range(max(8, int(repeats))):
        ang = math.degrees(i / repeats * 360.0)
        rnd = fract(np.sin(np.mod(i * 12.9898 + s * 78.233, math.pi)) * 43758.5453)
        k = (rnd + amount) * amount
        acc = acc + sample(src, u + k * math.cos(ang), v + k * math.sin(ang))[..., :3]
    return finish(src, acc / repeats, src[..., 3], opacity)


def three_gauss(img, sigma):
    """three's gaussianBlur(tex, null | 1, sigma) (GaussianBlurNode): kernelSize = 3 + 2 sigma, taps at 0 and
    +-1 .. +-(kernelSize - 1) px, weights 0.39894 exp(-i^2 / 2 s^2) / s with s = kernelSize / 3, not normalised; the
    horizontal pass, then the vertical; edges clamped. (sigma 1: a 1.67 px Gaussian over +-4 px.)"""
    k = 3 + 2 * int(sigma)
    s = k / 3.0
    w = [0.39894 * math.exp(-0.5 * i * i / (s * s)) / s for i in range(k)]
    taps = np.array([w[abs(i)] for i in range(-(k - 1), k)])
    out = img
    for ax in (1, 0):                                              # x (columns) first, then y
        pad = [(0, 0)] * img.ndim
        pad[ax] = (k - 1, k - 1)
        p = np.pad(out, pad, mode='edge')
        out = sum(wt * np.take(p, np.arange(i, i + img.shape[ax]), axis=ax) for i, wt in enumerate(taps))
    return out


def vhs_tape(src, t, intensity=1.0, opacity=1.0):
    H, W = src.shape[:2]
    u0, v0 = grid(H, W)
    k = math.floor(t / 100)
    tph = t - k * 100
    time = tph + (k * 61.8034) % 100

    def rnd(x, y):
        return fract(np.sin(x * 127.1 + y * 311.7) * 43758.5453)
    blur = three_gauss(src[..., :3], 1)
    u, v = u0.copy(), v0.copy()
    u = u + (rnd(v / 10, time / 10) - 0.5) / W * intensity + (rnd(v, time * 10) - 0.5) / W * intensity
    tc_rand = rnd(time * 0.67, time * 0.59)
    tc_phase = smoothstep(0.9, 0.96, np.sin(v * 8 - (tph + tc_rand * 0.14) * 3.769911))
    tc_noise = smoothstep(0.3, 1.0, rnd(v * 4.77, time))
    u = u - tc_phase * tc_noise / W * 8 * intensity
    sn = smoothstep(6.0 / H, 0.0, v)
    snx = (rnd(v0 * 100, time * 10) - 0.5) / W * 24 * intensity
    u, v = u + sn * snx, v + sn * 0.3 * intensity

    def yiq(c):
        return (c[..., 0] * 0.299 + c[..., 1] * 0.587 + c[..., 2] * 0.114,
                c[..., 0] * 0.596 - c[..., 1] * 0.274 - c[..., 2] * 0.322,
                c[..., 0] * 0.211 - c[..., 1] * 0.523 + c[..., 2] * 0.312)

    def rgb(y, i, q):
        return np.stack([y + i * 0.956 + q * 0.621, y - i * 0.272 - q * 0.647, y - i * 1.106 + q * 1.703], -1)
    Y = I = Q = 0.0
    for i in range(6):
        yy, ii, qq = yiq(sample(blur, u - i / W, v))
        Y, I, Q = Y + yy * ((5 - i) / 5) * 2 / 6, I + ii * (i / 5) * 2 / 6, Q + qq * (i / 5) * 2 / 6
    rot = tc_phase * 0.2 + sn * 2.0
    cs, sr = np.cos(rot), np.sin(rot)
    col = rgb(Y, cs * I + sr * Q, -sr * I + cs * Q)
    cn = tc_noise * (0.3 + tc_phase * 0.7)
    utx, uty = u * 0.1, v + rnd(v, time)
    n0, n1 = rnd(utx, uty), rnd(utx, uty + 1.0 / W)
    drop = step(0.29, cn) * step(n1, n0)
    col = mix(col, 2.0, (drop * n0 ** 10)[..., None])
    ac = rnd(0.0, (v0 + time * 0.2) * 0.01)
    col = col * (1 + 0.1 * smoothstep(0.4, 0.6, ac))[..., None]
    gu, gv = u + time * 5.97, v + time * 4.45
    gr = np.stack([rnd(np.mod(gu, 1), np.mod(gv, 1)), rnd(np.mod(gu + 17.3, 1), np.mod(gv + 23.1, 1)),
                   rnd(np.mod(gu + 43.7, 1), np.mod(gv + 11.9, 1))], -1)
    col = np.clip(col * (0.9 + gr * 0.1), 0, 1)
    y2, i2, q2 = yiq(col)
    col = rgb(y2 * 0.95 + 0.05, i2 - 0.02, q2)
    return finish(src, col, src[..., 3], opacity)


def rain_on_camera(src, t_s, amount=1.0, speed=1.0, drop_size=0.2, resolution=(1920, 1080), directions=12, quality=3,
                   blur_size=9.0):
    H, W = src.shape[:2]
    u, v = grid(H, W)
    aspect = resolution[0] / resolution[1]
    ds = drop_size

    def S(a, b, x):
        return smoothstep(a, b, x)

    def N(x):
        return fract(np.sin(x * 12345.564) * 7658.76)

    def saw(b, x):
        return S(0.0, b, x) * S(1.0, b, x)

    def n13(p):
        p3 = [fract(p * 0.1031), fract(p * 0.11369), fract(p * 0.13787)]
        dd = p3[0] * (p3[1] + 19.19) + p3[1] * (p3[2] + 19.19) + p3[2] * (p3[0] + 19.19)
        p3 = [x + dd for x in p3]
        return fract((p3[0] + p3[1]) * p3[2]), fract((p3[0] + p3[2]) * p3[1]), fract((p3[1] + p3[2]) * p3[0])

    def drops(ux, uy, t):
        gx, gy = ux, uy + t * 0.8
        idx = np.floor(gx * 12)
        gy = gy + N(idx)
        idy = np.floor(gy * 2)
        nx, _ny, nz = n13(idx * 35.2 + idy * 2376.1)
        stx, sty = fract(gx * 12) - 0.5, fract(gy * 2)
        x = nx - 0.5
        yv = uy * 20
        x = (x + np.sin(yv + np.sin(yv)) * (0.5 - np.abs(x)) * (nz - 0.5)) * 0.7
        y = (saw(0.85, fract(t + nz)) - 0.5) * 0.9 + 0.5
        drop = S(ds, 0.0, np.sqrt((stx - x) ** 2 + ((sty - y) * 6) ** 2))
        r = np.sqrt(S(1.0, y, sty))
        trail = S((ds * 0.5 + 0.03) * r, (ds * 0.5 - 0.05) * r, np.abs(stx - x))
        front = S(-0.02, 0.02, sty - y)
        y2 = fract((uy + N(idx)) * 10) + (sty - 0.5)
        droplets = S(ds * N(idx), 0.0, np.sqrt((stx - x) ** 2 + (sty - y2) ** 2))
        return drop + droplets * r * front, trail * front

    def static(ux, uy, t):
        gx, gy = ux * 30, uy * 30
        idx, idy = np.floor(gx), np.floor(gy)
        fx, fy = fract(gx) - 0.5, fract(gy) - 0.5
        nx, ny, nz = n13(idx * 107.45 + idy * 3543.654)
        d = np.sqrt((fx - (nx - 0.5) * 0.5) ** 2 + (fy - (ny - 0.5) * 0.5) ** 2)
        return S(ds, 0.0, d) * fract(nz * 10) * saw(0.025, fract(t + nz))

    def rain(ux, uy, t):
        m1, t1 = drops(ux, uy, t)
        m2, t2 = drops(ux * 1.8, uy * 1.8, t)
        return S(0.3, 1.0, static(ux, uy, t) + m1 + m2), np.maximum(t1, t2)
    t = t_s * 0.2 * speed
    rx, ry = (u - 0.5) * aspect, (v - 0.5) * -1.0
    c, trail = rain(rx, ry, t)
    cx, _ = rain(rx + 0.001, ry, t)
    cy, _ = rain(rx, ry + 0.001, t)
    bu, bv = (u - 0.5) * 0.9 + 0.5 + (cx - c) * amount, (v - 0.5) * 0.9 + 0.5 + (c - cy) * amount
    tex = sample(src, bu, bv)[..., :3]
    col, taps = tex.copy(), 1
    for di in range(directions):
        d = di / directions * TAU
        for qi in range(1, quality + 1):
            i = qi / quality
            col = col + sample(src, bu + math.cos(d) * i * blur_size / resolution[0],
                               bv + math.sin(d) * i * blur_size / resolution[1])[..., :3]
            taps += 1
    col = col / taps
    focus = np.maximum(S(0.1, 0.3, c), np.clip(trail * amount, 0, 1))[..., None]
    return finish(src, mix(col, tex, focus), 1.0, 1.0)


def box8(img):
    """An 8 x 8 box downsample (H, W, C) -> (H / 8, W / 8, C)."""
    H, W = img.shape[:2]
    h, w = H // 8, W // 8
    return img[:h * 8, :w * 8].reshape(h, 8, w, 8, -1).mean(axis=(1, 3))


# ------------------------------------------------------------------------------------------------- depth fog (screen)
POISSON8 = ((0.493393, 0.394269), (0.798547, 0.885922), (0.259143, 0.650754), (0.605322, 0.023588),
            (-0.574681, 0.137452), (-0.430397, -0.638423), (-0.849487, -0.366258), (0.170621, -0.569941))


def depth_fog(src, dep, cam, o):
    """noise_amount 0 for parity (the value noise's hash is float-detail noise)."""
    H, W = src.shape[:2]
    u, v = grid(H, W)
    g = lambda k, d: o.get(k, d)                                                    # noqa: E731
    near, far = cam.near, cam.far
    zimg = np.clip(dep, near, far)[..., None]
    z = sample_nearest(zimg, u, v)[..., 0]
    amt, ns = g('noise_amount', 0.4), g('noise_scale', 6.0)

    def hsh(x, y):
        return fract(np.sin(x * 127.1 + y * 311.7) * 43758.5453)
    nx, ny = u * ns, v * ns
    ix, iy = np.floor(nx), np.floor(ny)
    fx, fy = nx - ix, ny - iy
    sx, sy = fx * fx * (3 - 2 * fx), fy * fy * (3 - 2 * fy)
    noise = mix(mix(hsh(ix, iy), hsh(ix + 1, iy), sx), mix(hsh(ix, iy + 1), hsh(ix + 1, iy + 1), sx), sy)
    fog = np.clip(1 - np.exp(-(z * g('density', 0.04) * (1 - amt + amt * noise))), 0, 1)
    er = g('edge_radius', 2)
    dc = (z - near) / (far - near)
    pdx, pdy, cnt = 0.0, 0.0, 0.0
    for ox, oy in POISSON8:
        ox, oy = ox * er, oy * er
        zs = sample_nearest(zimg, u + ox / W, v + oy / H)[..., 0]
        same = (np.abs((zs - near) / (far - near) - dc) < 0.05 * dc).astype(np.float64)
        pdx, pdy, cnt = pdx + same * ox, pdy + same * oy, cnt + same
    cnt = np.where(cnt == 0, 1.0, cnt)
    pdx, pdy = pdx / cnt, pdy / cnt
    moved = (pdx * pdx + pdy * pdy) > 0
    es = g('edge_strength', 2.0)
    best = sample(fog[..., None], u + np.where(moved, es * pdx / W, 0), v + np.where(moved, es * pdy / H, 0))[..., 0]
    col = np.array(g('color', (0.55, 0.62, 0.72)))
    out = mix(src[..., :3], col, best[..., None])
    a = mix(src[..., 3], 1.0, best)
    return finish(src, out, a, g('opacity', 1.0))


# ------------------------------------------------------------------------------------------------- the verifier's
# (effects the parity suite had only looked at: wavy, kaleidoscope, dithering, bw_halftone, bleach_bypass; three's
# DepthOfFieldNode behind focus_blur's screen mode)
def wavy(src, t, amplitude=10.0, frequency=0.1, phase=0.0, animate=0.0, anim_speed=1.0, opacity=1.0):
    H, W = src.shape[:2]
    u, v = grid(H, W)
    p = phase + float(animate) * t * anim_speed
    eff = sample(src, u + amplitude * np.sin(frequency * (v * H) + p) / W, v)
    return finish(src, eff[..., :3], eff[..., 3], opacity)


def kaleidoscope(src, segments=6.0, rotate=0.0, opacity=1.0):
    H, W = src.shape[:2]
    u, v = grid(H, W)
    px, py = u - 0.5, v - 0.5
    r = np.hypot(px, py)
    seg = TAU / segments
    a = np.abs(np.mod(np.arctan2(py, px) + rotate, seg) - seg * 0.5)          # TSL mod: floored (tsl_mod_float)
    col = sample(src, np.clip(np.cos(a) * r + 0.5, 0.001, 0.999), np.clip(np.sin(a) * r + 0.5, 0.001, 0.999))
    return finish(src, col[..., :3], 1.0, opacity)


def dithering(src, levels=8.0, opacity=1.0):
    """three's bayerDither at screenUV x screenSize (pixel centres, y down) on sqrt(rgb), quantised, squared back."""
    H, W = src.shape[:2]
    yy, xx = np.mgrid[0:H, 0:W].astype(np.float64)
    x, y = np.mod(xx, 4.0), np.mod(yy, 4.0)
    bayer = np.mod(np.floor(x + 1) * np.floor(y + 1) * 17.0, 16.0) / 16.0 - 0.5
    dith = np.sqrt(np.maximum(src[..., :3], 0.0)) + (bayer / levels)[..., None]
    q = np.floor(dith * (levels - 1) + 0.5) / (levels - 1)
    return finish(src, q * q, src[..., 3], opacity)


def bw_halftone(src, threshold=0.4, dot_size=1.8, angle=45.0, ink_color=(0.0, 0.0, 0.0), paper_color=(1.0, 1.0, 1.0),
                opacity=1.0):
    H, W = src.shape[:2]
    u, v = grid(H, W)
    ratio = H / W
    shx, shy = u - 0.5, v * ratio - ratio * 0.5
    a = math.radians(angle)
    sa, ca = math.sin(a), math.cos(a)
    d = math.pi / dot_size * 680.0
    raster = 0.5 + np.cos((shx * sa + shy * ca + 0.5) * d) * 0.25 + np.cos((shx * ca - shy * sa + ratio * 0.5) * d) * 0.25
    avg = src[..., :3] @ np.array([0.2125, 0.7154, 0.0721])
    gray = np.clip((raster * threshold + avg - threshold) / max(1.0 - threshold, 1e-4), 0, 1)[..., None]
    ink, paper = np.array(ink_color), np.array(paper_color)
    return finish(src, ink + (paper - ink) * gray, 1.0, opacity)


def bleach_bypass(src, amount=1.0, opacity=1.0):
    """three's bleach(orig.rgb, amount): its base.a is the vec3's pad (1.0), so A2 = amount on every pixel."""
    base = src[..., :3]
    lum = (base @ LUM709)[..., None]
    L = np.clip((lum - 0.45) * 10.0, 0.0, 1.0)
    new = mix(lum * base * 2.0, 1.0 - 2.0 * (1.0 - lum) * (1.0 - base), L)
    return finish(src, new * amount + base * (1.0 - amount), src[..., 3], opacity)


def bokeh_kernels():
    """DepthOfFieldNode._generateKernels: (points64, points16) on the golden-angle spiral."""
    p64, p16 = [], []
    for i in range(80):
        th, r = i * 2.39996323, math.sqrt(i) / math.sqrt(80)
        (p16 if i % 5 == 0 else p64).append((r * math.cos(th), r * math.sin(th)))
    return p64, p16


def focus_blur(src, dep, cam, o, half=True):
    """three's DepthOfFieldNode under focus_blur.js. half=True: as three runs it (the CoC at full size; the near
    CoC's blur, blur64 and blur16 on round(W / 2) x round(H / 2) targets, read back bilinearly by the composite);
    half=False: every pass at full size, the port's structure."""
    H, W = src.shape[:2]
    g = lambda k, d: o.get(k, d)                                                    # noqa: E731
    fd, fl, bs = g('focus_distance', 5.0), g('focal_length', 2.0), g('bokeh_scale', 1.0)
    z = np.clip(dep, cam.near, cam.far)
    sd = z - fd
    coc = smoothstep(0.0, fl, np.abs(sd))
    near_f, far_f = (sd <= 0) * coc, (sd >= 0) * coc
    near_b = three_gauss(near_f[..., None], 2)[..., 0]
    p64, p16 = bokeh_kernels()
    Hh, Wh = (int(round(H / 2)), int(round(W / 2))) if half else (H, W)
    uh, vh = grid(Hh, Wh)

    def passes(coc_full):
        cc = sample(coc_full[..., None], uh, vh)[..., 0]               # the CoC at this target's texel centres
        acc = 0.0
        for kx, ky in p64:
            acc = acc + sample(src, uh + kx * bs * cc / W, vh + ky * bs * cc / H)[..., :3]
        b64 = acc / len(p64)
        m = b64.copy()
        for kx, ky in p16:
            m = np.maximum(sample(b64, uh + kx * bs * cc / W, vh + ky * bs * cc / H), m)
        return np.concatenate([m, cc[..., None]], -1)
    u, v = grid(H, W)
    nr, fr = sample(passes(near_b), u, v), sample(passes(far_f), u, v)
    res = mix(src[..., :3], fr[..., :3], (np.minimum(fr[..., 3], 0.5) * 2.0)[..., None])
    res = mix(res, nr[..., :3], (np.minimum(nr[..., 3], 0.5) * 2.0)[..., None])
    return finish(src, res, 1.0, g('opacity', 1.0))


def simplex_stats(n=200000, seed=7):
    """old_bw_film.js simplexNoise over random points with a random gradient per lattice corner (the shader's
    structure; its uint hash only decides which corner gets which gradient): (mean, std, share above 0.7, share in
    the region band smoothstep(0.70, 0.88), share below 0.3), for the Blender field's statistics to be held to."""
    rng = np.random.default_rng(seed)
    p = rng.uniform(0.0, 4000.0, (n, 2))
    grads = {}

    def grad(ix, iy):
        out = np.empty((len(ix), 2))
        for k, key in enumerate(zip(ix.astype(np.int64), iy.astype(np.int64))):
            if key not in grads:
                grads[key] = rng.uniform(-1.0, 1.0, 2)
            out[k] = grads[key]
        return out
    k1, k2 = 0.366025404, 0.211324865
    s = (p[:, 0] + p[:, 1]) * k1
    i = np.floor(p + s[:, None])
    si = (i[:, 0] + i[:, 1]) * k2
    a = p - i + si[:, None]
    o = np.where((a[:, 0] >= a[:, 1])[:, None], [1.0, 0.0], [0.0, 1.0])
    b = a - o + k2
    c = a - 1.0 + 0.42264973
    tot = 0.0
    for d, j in ((a, i), (b, i + o), (c, i + 1.0)):
        h = np.clip(0.5 - (d * d).sum(1), 0.0, 1.0)
        tot = tot + h ** 4 * (d * grad(j[:, 0], j[:, 1])).sum(1)
    v = tot * 35.0 + 0.5
    return (float(v.mean()), float(v.std()), float((v > 0.7).mean()), float(smoothstep(0.70, 0.88, v).mean()),
            float((v < 0.3).mean()))
