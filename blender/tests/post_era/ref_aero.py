"""tests/post_era/ref_aero.py: aeropittura.js stages B, C and D (the colour structure tensor, the flow field, the
anisotropic Kuwahara underpainting) transcribed line for line into numpy, to check the compositor port against an
independent reading of the same shader. Test code, not a port.

Images are top-down float arrays (H, W, C), uv y DOWN (the WebGPU pass's own), bilinear sampling with clamped edges
at texel centres (a WebGPU texture with ClampToEdge and LinearFilter). S = H / 1080. The tensor and flow taps sit
d x S px out, as in the WebGPU pass. The Kuwahara's taps: tap_px = S is the WebGPU pass exactly; tap_px = 1 is the
Blender port, which keeps the 1080p brush at every size (the two agree at 1080p, where S = 1).
"""
import numpy as np


def smoothstep(e0, e1, x):
    t = np.clip((x - e0) / (e1 - e0), 0.0, 1.0)
    return t * t * (3.0 - 2.0 * t)


def sample(img, x, y):
    """img (H, W, C) at pixel coordinates x, y (pixel centres at i + 0.5): bilinear, edges clamped."""
    H, W = img.shape[:2]
    xf, yf = x - 0.5, y - 0.5
    x0, y0 = np.floor(xf), np.floor(yf)
    fx, fy = (xf - x0)[..., None], (yf - y0)[..., None]
    xa = np.clip(x0, 0, W - 1).astype(np.int32)
    xb = np.clip(x0 + 1, 0, W - 1).astype(np.int32)
    ya = np.clip(y0, 0, H - 1).astype(np.int32)
    yb = np.clip(y0 + 1, 0, H - 1).astype(np.int32)
    return (img[ya, xa] * (1 - fx) * (1 - fy) + img[ya, xb] * fx * (1 - fy) + img[yb, xa] * (1 - fx) * fy
            + img[yb, xb] * fx * fy)


def flow_field(s1, brush_angle=1.05, S=None):
    """Stages B and C: (t.x, t.y, A) per pixel, as aeropittura.js's flowT. S: the frame's H / 1080 (default: the
    picture's own height; give the frame's when s1 is a crop)."""
    H, W = s1.shape[:2]
    S = H / 1080.0 if S is None else S
    yy, xx = np.mgrid[0:H, 0:W].astype(np.float32)
    X, Y = xx + 0.5, yy + 0.5

    def at(src, dx, dy):
        return sample(src, X + dx * S, Y + dy * S)
    a, b, c = at(s1, -1, -1), at(s1, 0, -1), at(s1, 1, -1)
    d, f = at(s1, -1, 0), at(s1, 1, 0)
    g, h, i = at(s1, -1, 1), at(s1, 0, 1), at(s1, 1, 1)
    gx = (c + f * 2 + i - a - d * 2 - g) * 0.25
    gy = (g + h * 2 + i - a - b * 2 - c) * 0.25
    s2 = np.stack([(gx * gx).sum(-1), (gx * gy).sum(-1), (gy * gy).sum(-1)], -1).astype(np.float32)
    taps = [(0, 0, 4), (3, 0, 2), (-3, 0, 2), (0, 3, 2), (0, -3, 2), (3, 3, 1), (-3, 3, 1), (3, -3, 1), (-3, -3, 1),
            (6, 0, 1), (-6, 0, 1), (0, 6, 1), (0, -6, 1)]
    wsum = float(sum(t[2] for t in taps))
    acc = np.zeros_like(s2)
    for dx, dy, w in taps:
        acc += at(s2, dx, dy) * (w / wsum)
    E, F, G = acc[..., 0], acc[..., 1], acc[..., 2]
    disc = np.sqrt(np.maximum((E - G) ** 2 + F * F * 4, 0))
    l1, l2 = (E + G + disc) * 0.5, (E + G - disc) * 0.5
    tvx, tvy = l1 - E, -F
    defx, defy = np.cos(brush_angle), np.sin(brush_angle)
    sgn = np.where(tvx * defx + tvy * defy >= 0, 1.0, -1.0)
    tvx, tvy = tvx * sgn, tvy * sgn
    energy = E + G
    k = smoothstep(2e-5, 6e-4, energy) * (tvx * tvx + tvy * tvy >= 1e-12)
    nx, ny = tvx + 1e-9, tvy
    nl = np.sqrt(nx * nx + ny * ny)
    nx, ny = nx / np.maximum(nl, 1e-30), ny / np.maximum(nl, 1e-30)
    mx, my = defx + (nx - defx) * k + 1e-6, defy + (ny - defy) * k
    ml = np.sqrt(mx * mx + my * my)
    A = (l1 - l2) / (l1 + l2 + 1e-9) * k
    return np.stack([mx / ml, my / ml, A], -1).astype(np.float32)


def kuwahara(s1, flow, tap_px=1.0, S=None):
    """Stage D: the anisotropic Kuwahara (8 polynomial sectors, zeta = 2 / RAD, eta = 0.33), RAD = max(3, round(8 S)),
    taps d x tap_px px apart over [-RAD, RAD]^2. Returns the filtered colour (H, W, 3). S as flow_field's."""
    H, W = s1.shape[:2]
    S = H / 1080.0 if S is None else S
    RAD = max(3, int(round(8 * S)))
    tx, ty, A = flow[..., 0], flow[..., 1], flow[..., 2]
    yy, xx = np.mgrid[0:H, 0:W].astype(np.float32)
    X, Y = xx + 0.5, yy + 0.5
    a, b = RAD * (A + 1.0), RAD / (A + 1.0)
    zeta, eta = 2.0 / RAD, 0.33
    m = np.zeros((8, H, W, 3), np.float32)
    s = np.zeros((8, H, W, 3), np.float32)
    w = np.zeros((8, H, W), np.float32)
    for j in range(-RAD, RAD + 1):
        for i in range(-RAD, RAD + 1):
            vx = (i * tx + j * ty) / a
            vy = (j * tx - i * ty) / b
            vv = vx * vx + vy * vy
            inside = vv <= 1.0
            if not inside.any():
                continue
            c = sample(s1, X + i * tap_px, Y + j * tap_px)
            cc = c * c
            vxx, vyy = zeta - vx * vx * eta, zeta - vy * vy * eta
            z = [np.maximum(0, vy + vxx), None, np.maximum(0, -vx + vyy), None, np.maximum(0, -vy + vxx), None,
                 np.maximum(0, vx + vyy), None]
            rx, ry = (vx - vy) * 0.70710678, (vx + vy) * 0.70710678
            vxx, vyy = zeta - rx * rx * eta, zeta - ry * ry * eta
            z[1], z[3], z[5], z[7] = (np.maximum(0, ry + vxx), np.maximum(0, -rx + vyy), np.maximum(0, -ry + vxx),
                                      np.maximum(0, rx + vyy))
            ws = [q * q for q in z]
            tot = ws[0] + ws[1] + ws[2] + ws[3] + ws[4] + ws[5] + ws[6] + ws[7]
            gw = np.exp(vv * -3.125) / (tot + 1e-6) * inside
            for k in range(8):
                wk = ws[k] * gw
                m[k] += c * wk[..., None]
                s[k] += cc * wk[..., None]
                w[k] += wk
    num = np.zeros((H, W, 3), np.float32)
    den = np.zeros((H, W), np.float32)
    for k in range(8):
        mk = m[k] / (w[k] + 1e-6)[..., None]
        vk = np.abs(s[k] / (w[k] + 1e-6)[..., None] - mk * mk)
        al = 1.0 / (((vk[..., 0] + vk[..., 1] + vk[..., 2]) * 255.0) ** 4 + 1.0)
        num += mk * al[..., None]
        den += al
    return num / (den + 1e-6)[..., None]
