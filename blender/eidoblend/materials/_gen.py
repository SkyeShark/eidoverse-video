"""The canvas maths of eidoverse/procedural_materials.js in numpy (private; plain Python, no bpy).

Every generator returns a uint8 array (h, w, 3) in CANVAS row order (row 0 = the image's top), the bytes the
engine's 2D canvas holds: the per-pixel generators truncate exactly as _fillPixels does ((c * 255) | 0, clamped),
so the maths ones (noise, voronoi, patches, weave, grain, height_to_normal, composite, the factories' maps) match
the engine to the byte (test_pm_parity.py measures it against the engine's own canvas under deno). The three drawn
ones (scratches, smudges, pores) replay the engine's Mulberry32 draw list call for call and rasterise each stroke,
gradient square and disc with box-filtered coverage composited source-over, the way Skia's canvas does; their pixels
agree with the engine's within its anti-aliasing (the test prints how closely).

Conventions kept from the engine: a texture is (h, w, 3) uint8; heights read the red channel / 255; normal maps are
the engine's (r = nx * 0.5 + 0.5, g = ny * 0.5 + 0.5, b = 1) with its signs.
"""
import math

import numpy as np

TWO32 = 4294967296.0


# ------------------------------------------------------------------------------------------- Mulberry32 ---

def _int32_bits(seed):
    """JS ToInt32(seed) as an unsigned 32-bit pattern (seed |= 0)."""
    if isinstance(seed, float):
        if not math.isfinite(seed):
            return 0
        seed = math.trunc(seed)
    return int(seed) & 0xFFFFFFFF


def rng(seed):
    """The engine's _rng: Mulberry32, bit for bit (uint32 arithmetic stands in for int32 + Math.imul)."""
    state = [_int32_bits(seed)]

    def r():
        s = (state[0] + 0x6D2B79F5) & 0xFFFFFFFF
        state[0] = s
        t = ((s ^ (s >> 15)) * (1 | s)) & 0xFFFFFFFF
        t = ((t + (((t ^ (t >> 7)) * (61 | t)) & 0xFFFFFFFF)) & 0xFFFFFFFF) ^ t
        return ((t ^ (t >> 14)) & 0xFFFFFFFF) / TWO32
    return r


# -------------------------------------------------------------------------------------- noise primitives ---

def hash2(x, y):
    h = np.sin(x * 127.1 + y * 311.7) * 43758.5453
    return h - np.floor(h)


def noise2(x, y):
    ix = np.floor(x)
    iy = np.floor(y)
    fx = x - ix
    fy = y - iy
    sx = fx * fx * (3 - 2 * fx)
    sy = fy * fy * (3 - 2 * fy)
    a = hash2(ix, iy)
    b = hash2(ix + 1, iy)
    c = hash2(ix, iy + 1)
    d = hash2(ix + 1, iy + 1)
    return a + (b - a) * sx + (c - a) * sy + (a - b - c + d) * sx * sy


def fbm(x, y, octaves=6):
    octaves = octaves or 6
    v = np.zeros(np.broadcast(x, y).shape)
    a = 0.5
    for _ in range(int(octaves)):
        v = v + a * noise2(x, y)
        nx = x * 1.6 + y * 1.2 + 1.7
        ny = -x * 1.2 + y * 1.6 + 9.2
        x, y = nx, ny
        a *= 0.5
    return v


def voronoi(x, y):
    """-> (d1, d2, edge, cell) arrays: the nearest and second-nearest feature distances, d2 - d1, the cell's hash."""
    ix = np.floor(x)
    iy = np.floor(y)
    fx = x - ix
    fy = y - iy
    shape = np.broadcast(x, y).shape
    d1 = np.full(shape, 8.0)
    d2 = np.full(shape, 8.0)
    cell = np.zeros(shape)
    for j in (-1, 0, 1):
        for i in (-1, 0, 1):
            px = hash2(ix + i, iy + j)
            py = hash2(ix + i + 99, iy + j + 99)
            dx = i + px - fx
            dy = j + py - fy
            d = dx * dx + dy * dy
            near = d < d1
            mid = ~near & (d < d2)
            cid = hash2(ix + i + 37, iy + j + 37)
            d2 = np.where(near, d1, np.where(mid, d, d2))
            cell = np.where(near, cid, cell)
            d1 = np.where(near, d, d1)
    d1 = np.sqrt(d1)
    d2 = np.sqrt(d2)
    return d1, d2, d2 - d1, cell


def warped_fbm(x, y, t=0):
    qx = fbm(x, y, 4)
    qy = fbm(x + 5.2, y + 1.3, 4)
    t = t or 0
    return fbm(x + 4 * qx + t, y + 4 * qy + t, 5)


# --------------------------------------------------------------------------------------------- canvas ---

def uv_grid(w, h):
    """u = x / w, v = y / h for every pixel (canvas order), and the pixel indices."""
    px = np.arange(w, dtype=np.float64)
    py = np.arange(h, dtype=np.float64)
    X, Y = np.meshgrid(px, py)
    return X / w, Y / h, X, Y


def to_bytes(c):
    """_fillPixels' store: Math.min(255, Math.max(0, (c * 255) | 0)), NaN -> 0."""
    v = np.asarray(c, dtype=np.float64) * 255.0
    v = np.where(np.isfinite(v), v, 0.0)
    return np.clip(np.trunc(v), 0, 255).astype(np.uint8)


def fill(r, g=None, b=None):
    """Three channel arrays (0..1 floats) -> (h, w, 3) uint8, as _fillPixels writes them."""
    g = r if g is None else g
    b = r if b is None else b
    return np.stack([to_bytes(r), to_bytes(g), to_bytes(b)], axis=-1)


def parse_color(c):
    """_parseColor: 0xRRGGBB, '#rrggbb', {'r','g','b'} (0-1) or an (r, g, b) tuple (0-1) -> (r, g, b) floats.
    The values are the canvas's (sRGB-encoded) channel values, as in the engine."""
    if isinstance(c, dict) and 'r' in c:
        return (float(c['r']), float(c['g']), float(c['b']))
    if isinstance(c, (tuple, list)):
        return (float(c[0]), float(c[1]), float(c[2]))
    if isinstance(c, str):
        c = int(c.replace('#', ''), 16)
    c = int(c)
    return (((c >> 16) & 0xff) / 255, ((c >> 8) & 0xff) / 255, (c & 0xff) / 255)


def _js_floor_int(v):
    return int(math.floor(v))


class Surface:
    """A float RGBA canvas (straight alpha 1 everywhere: the generators fill an opaque background first) that
    strokes, discs and gradient rectangles composite onto source-over, then quantises once as Skia's 8-bit surface
    does at the end (to_bytes rounds like a canvas store: round half up of the 0..255 value)."""

    def __init__(self, w, h, rgb):
        self.w, self.h = w, h
        self.px = np.empty((h, w, 3), dtype=np.float64)
        self.px[...] = np.asarray(rgb, dtype=np.float64) / 255.0

    def _blend(self, x0, y0, cov, rgb, alpha):
        """composite colour rgb (0-255) with per-pixel coverage `cov` (a window at x0, y0) times globalAlpha."""
        a = (cov * alpha)[..., None]
        if not np.any(a):
            return
        h, w = cov.shape
        win = self.px[y0:y0 + h, x0:x0 + w]
        win *= (1.0 - a)
        win += a * (np.asarray(rgb, dtype=np.float64) / 255.0)

    def _window(self, xmin, xmax, ymin, ymax):
        x0 = max(0, int(math.floor(xmin)) - 1)
        x1 = min(self.w, int(math.ceil(xmax)) + 2)
        y0 = max(0, int(math.floor(ymin)) - 1)
        y1 = min(self.h, int(math.ceil(ymax)) + 2)
        if x1 <= x0 or y1 <= y0:
            return None
        X, Y = np.meshgrid(np.arange(x0, x1) + 0.5, np.arange(y0, y1) + 0.5)
        return x0, y0, X, Y

    def stroke_line(self, ax, ay, bx, by, width, rgb, alpha):
        """A butt-capped line of `width` px: box-filtered coverage of the stroke's rectangle (separable across and
        along the line); a stroke under 1 px is Skia's hairline, 1 px wide with its alpha scaled by the width."""
        dx, dy = bx - ax, by - ay
        L = math.hypot(dx, dy)
        if L <= 0:
            return
        if width < 1.0:
            alpha = alpha * width
            width = 1.0
        hw = width / 2
        win = self._window(min(ax, bx) - hw, max(ax, bx) + hw, min(ay, by) - hw, max(ay, by) + hw)
        if win is None:
            return
        x0, y0, X, Y = win
        ux, uy = dx / L, dy / L
        rx, ry = X - ax, Y - ay
        along = rx * ux + ry * uy
        perp = np.abs(-rx * uy + ry * ux)
        c_perp = np.clip(np.minimum(0.5, hw - perp) - np.maximum(-0.5, -hw - perp), 0, 1)
        c_along = np.clip(np.minimum(along + 0.5, L) - np.maximum(along - 0.5, 0.0), 0, 1)
        self._blend(x0, y0, c_perp * c_along, rgb, alpha)

    def fill_disc(self, cx, cy, r, rgb, alpha, ss=4):
        """ctx.arc(cx, cy, r, 0, 2pi); ctx.fill(): coverage by ss x ss supersampling of each pixel."""
        win = self._window(cx - r, cx + r, cy - r, cy + r)
        if win is None:
            return
        x0, y0, X, Y = win
        o = (np.arange(ss) + 0.5) / ss - 0.5
        cov = np.zeros(X.shape)
        r2 = r * r
        for oy in o:
            for ox in o:
                cov += ((X + ox - cx) ** 2 + (Y + oy - cy) ** 2) <= r2
        self._blend(x0, y0, cov / (ss * ss), rgb, alpha)

    def fill_radial_rect(self, cx, cy, radius, stops):
        """fillRect(cx - radius, cy - radius, 2 radius, 2 radius) with a radial gradient from (cx, cy, 0) to
        (cx, cy, radius); stops = [(offset, (r, g, b) 0-255, alpha)] interpolated unpremultiplied (Skia's default)
        and premultiplied after; past the last stop the last colour holds."""
        win = self._window(cx - radius, cx + radius, cy - radius, cy + radius)
        if win is None:
            return
        x0, y0, X, Y = win
        # the rectangle's own coverage (its edges sit at fractional pixels)
        cxv = np.clip(np.minimum(X + 0.5, cx + radius) - np.maximum(X - 0.5, cx - radius), 0, 1)
        cyv = np.clip(np.minimum(Y + 0.5, cy + radius) - np.maximum(Y - 0.5, cy - radius), 0, 1)
        t = np.sqrt((X - cx) ** 2 + (Y - cy) ** 2) / radius
        offs = np.array([s[0] for s in stops], dtype=np.float64)
        cols = np.array([s[1] for s in stops], dtype=np.float64)
        alps = np.array([s[2] for s in stops], dtype=np.float64)
        tt = np.clip(t, offs[0], offs[-1])
        col = np.stack([np.interp(tt, offs, cols[:, k]) for k in range(3)], axis=-1)
        al = np.interp(tt, offs, alps) * cxv * cyv
        a = al[..., None]
        win_px = self.px[y0:y0 + X.shape[0], x0:x0 + X.shape[1]]
        win_px *= (1.0 - a)
        win_px += a * (col / 255.0)

    def to_bytes(self):
        return np.clip(np.floor(self.px * 255.0 + 0.5), 0, 255).astype(np.uint8)


# ----------------------------------------------------------------------------------------- generators ---

def _nn(v, d):
    return d if v is None else v


def scratches(w=512, h=512, density=None, depth=None, direction=None, seed=None):
    w = w or 512
    h = h or 512
    density = _nn(density, 0.3)
    depth = _nn(depth, 0.5)
    seed = seed or 42
    rand = rng(seed)
    S = Surface(w, h, (0, 0, 0))
    count = _js_floor_int(w * density * 2.5)
    for _ in range(count):
        x = rand() * w
        y = rand() * h
        angle = direction + (rand() - 0.5) * 0.4 if direction is not None else rand() * math.pi
        ln = 8 + rand() * 50
        bright = _js_floor_int(depth * (100 + rand() * 155))
        lw = 0.3 + rand() * 1.2
        alpha = 0.3 + rand() * 0.7
        c, s = math.cos(angle), math.sin(angle)
        S.stroke_line(x - c * ln / 2, y - s * ln / 2, x + c * ln / 2, y + s * ln / 2, lw,
                      (bright, bright, bright), alpha)
    return S.to_bytes()


def smudges(w=512, h=512, amount=None, scale=None, seed=None):
    w = w or 512
    h = h or 512
    amount = _nn(amount, 0.3)
    scale = _nn(scale, 1.0)
    seed = seed or 123
    rand = rng(seed)
    S = Surface(w, h, (0, 0, 0))
    count = _js_floor_int(15 * amount * scale) + 3
    for _ in range(count):
        cx = rand() * w
        cy = rand() * h
        radius = 20 + rand() * 80 * scale
        bright = _js_floor_int(128 + rand() * 127)
        a1 = 0.3 + rand() * 0.5
        a2 = 0.1 + rand() * 0.2
        S.fill_radial_rect(cx, cy, radius, [(0.0, (bright,) * 3, a1), (0.6, (bright,) * 3, a2),
                                            (1.0, (0, 0, 0), 0.0)])
    return S.to_bytes()


def noise(w=512, h=512, scale=None, octaves=None, contrast=None, offset=None, warp=None):
    w = w or 512
    h = h or 512
    scale = _nn(scale, 5)
    octaves = octaves or 6
    contrast = _nn(contrast, 1)
    offset = offset or 0
    u, v, _X, _Y = uv_grid(w, h)
    if warp:
        n = warped_fbm(u * scale + offset, v * scale + offset, 0)
    else:
        n = fbm(u * scale + offset, v * scale + offset, octaves)
    n = np.maximum(0, np.minimum(1, (n - 0.5) * contrast + 0.5))
    return fill(n)


def voronoi_tex(w=512, h=512, scale=None, mode=None, edge_width=None):
    w = w or 512
    h = h or 512
    scale = _nn(scale, 8)
    mode = mode or 'cells'
    edge_width = _nn(edge_width, 0.08)
    u, v, _X, _Y = uv_grid(w, h)
    d1, _d2, edge, cell = voronoi(u * scale, v * scale)
    if mode == 'edges':
        val = (edge < edge_width).astype(np.float64)
    elif mode == 'distance':
        val = np.minimum(1, d1 * 2)
    else:
        val = cell
    return fill(val)


def patches(w=512, h=512, base_color=None, patch_color=None, scale=None, threshold=None, softness=None, shape=None):
    w = w or 512
    h = h or 512
    base = parse_color(base_color or 0xfff0e0)
    patch = parse_color(patch_color or 0x1a1a1a)
    scale = _nn(scale, 4)
    threshold = _nn(threshold, 0.55)
    softness = _nn(softness, 0.05)
    shape = shape or 'blob'
    u, v, _X, _Y = uv_grid(w, h)
    if shape == 'voronoi':
        _d1, _d2, edge, cell = voronoi(u * scale, v * scale)
        t = (cell > threshold).astype(np.float64)
        if softness > 0:
            t = t * np.minimum(1, edge / softness)
    elif shape == 'spots':
        d1, _d2, _edge, cell = voronoi(u * scale, v * scale)
        t = ((cell > threshold) & (d1 < 0.3)).astype(np.float64)
    else:
        n = fbm(u * scale, v * scale, 4)
        t = np.where(n > threshold, 0.0, 1.0)
        if softness > 0:
            e = np.abs(n - threshold)
            t = np.where(e < softness, t * (e / softness), t)
    return fill(base[0] + (patch[0] - base[0]) * t, base[1] + (patch[1] - base[1]) * t,
                base[2] + (patch[2] - base[2]) * t)


def pores(w=512, h=512, density=None, depth=None, seed=None):
    w = w or 512
    h = h or 512
    density = _nn(density, 0.5)
    depth = _nn(depth, 0.3)
    seed = seed or 77
    rand = rng(seed)
    S = Surface(w, h, (128, 128, 255))
    count = _js_floor_int(w * h * density / 80)
    for _ in range(count):
        px = rand() * w
        py = rand() * h
        r = 0.8 + rand() * 2.5
        nx = (rand() - 0.5) * depth
        ny = (rand() - 0.5) * depth
        cr = _js_floor_int(128 + nx * 127)
        cg = _js_floor_int(128 + ny * 127)
        alpha = 0.3 + rand() * 0.5
        S.fill_disc(px, py, r, (cr, cg, 220), alpha)
    return S.to_bytes()


def weave(w=512, h=512, density=None, variation=None):
    w = w or 512
    h = h or 512
    density = density or 20
    variation = _nn(variation, 0.3)
    u, v, _X, _Y = uv_grid(w, h)
    t1 = np.sin(u * density * math.pi * 2) * 0.5 + 0.5
    t2 = np.sin(v * density * math.pi * 2) * 0.5 + 0.5
    cell = (np.floor(u * density) + np.floor(v * density)) % 2
    val = np.where(cell != 0, np.maximum(t1, t2), np.minimum(t1, t2))
    val = val + (noise2(u * 50, v * 50) - 0.5) * variation
    val = np.maximum(0, np.minimum(1, val))
    return fill(val)


def grain(w=512, h=512, scale=None, stretch=None, contrast=None):
    w = w or 512
    h = h or 512
    scale = scale or 4
    stretch = stretch or 8
    contrast = _nn(contrast, 1.2)
    u, v, _X, _Y = uv_grid(w, h)
    n = fbm(u * scale, v * scale * stretch, 5)
    n = np.maximum(0, np.minimum(1, (n - 0.5) * contrast + 0.5))
    return fill(n)


def height_to_normal(height, strength=None, flip_green=False):
    """height: (h, w, 3|4) uint8 (canvas order); the red channel / 255 is the height.
    The engine's green rises where the height falls toward the image's TOP (hU - hD): three (and Blender) read green
    as +v, the image's top, so a bump's vertical flanks shade as if lit from the opposite side. flip_green=True
    writes hD - hU instead (green-up maps, a bump lit right on both axes); the default keeps the engine's bytes."""
    strength = _nn(strength, 1.0)
    hgt = np.asarray(height)[..., 0].astype(np.float64) / 255
    hL = np.roll(hgt, 1, axis=1)          # getHeight(px - 1, py), wrapped
    hR = np.roll(hgt, -1, axis=1)
    hU = np.roll(hgt, 1, axis=0)          # getHeight(px, py - 1): the row above
    hD = np.roll(hgt, -1, axis=0)
    nx = (hL - hR) * strength
    ny = (hD - hU) * strength if flip_green else (hU - hD) * strength
    return fill(nx * 0.5 + 0.5, ny * 0.5 + 0.5, np.ones_like(nx))


MODES = ('multiply', 'add', 'screen', 'overlay', 'max', 'min')


def resize_bilinear(px, w, h):
    """drawImage(src, 0, 0, w, h) of a different-sized source: bilinear (the canvas's default smoothing)."""
    px = np.asarray(px)
    sh, sw = px.shape[:2]
    if (sw, sh) == (w, h):
        return px
    xs = (np.arange(w) + 0.5) * sw / w - 0.5
    ys = (np.arange(h) + 0.5) * sh / h - 0.5
    x0 = np.clip(np.floor(xs).astype(int), 0, sw - 1)
    y0 = np.clip(np.floor(ys).astype(int), 0, sh - 1)
    x1 = np.clip(x0 + 1, 0, sw - 1)
    y1 = np.clip(y0 + 1, 0, sh - 1)
    fx = np.clip(xs - np.floor(xs), 0, 1)[None, :, None]
    fy = np.clip(ys - np.floor(ys), 0, 1)[:, None, None]
    f = px.astype(np.float64)
    top = f[y0][:, x0] * (1 - fx) + f[y0][:, x1] * fx
    bot = f[y1][:, x0] * (1 - fx) + f[y1][:, x1] * fx
    return np.clip(np.floor(top * (1 - fy) + bot * fy + 0.5), 0, 255).astype(np.uint8)


def composite(a, b, mode='multiply', strength=None):
    """a, b: (h, w, 3|4) uint8 canvas arrays; b is resampled to a's size. Uint8Clamped store of
    ((a (1 - s) + result s) * 255) | 0."""
    mode = mode or 'multiply'
    strength = _nn(strength, 1.0)
    A = np.asarray(a)[..., :3].astype(np.float64) / 255
    h, w = A.shape[:2]
    B = resize_bilinear(np.asarray(b)[..., :3], w, h).astype(np.float64) / 255
    if mode == 'add':
        res = np.minimum(1, A + B)
    elif mode == 'screen':
        res = 1 - (1 - A) * (1 - B)
    elif mode == 'overlay':
        res = np.where(A < 0.5, 2 * A * B, 1 - 2 * (1 - A) * (1 - B))
    elif mode == 'max':
        res = np.maximum(A, B)
    elif mode == 'min':
        res = np.minimum(A, B)
    else:
        res = A * B
    v = (A * (1 - strength) + res * strength) * 255
    v = np.where(np.isfinite(v), v, 0.0)
    return np.clip(np.trunc(v), 0, 255).astype(np.uint8)


# ------------------------------------------------------------------------------- the factories' own maps ---

def skin_variation(size, color, var_scale):
    c = parse_color(color)
    u, v, _X, _Y = uv_grid(size, size)
    n = fbm(u * var_scale, v * var_scale, 4)
    darken = 0.85 + n * 0.3
    return fill(c[0] * darken, c[1] * darken * 0.95, c[2] * darken * 0.9)


def scaly_maps(size, color, scale, bump_strength, flip_green=False):
    """createScaly's colour and normal maps. Its normal map has the engine's green sign (see height_to_normal):
    flip_green=True for green-up."""
    base = parse_color(color)
    u, v, _X, _Y = uv_grid(size, size)
    _d1, _d2, edge, cell = voronoi(u * scale, v * scale)
    shade = 0.7 + cell * 0.6
    d = shade * np.minimum(1, edge / 0.1)
    col = fill(base[0] * d, base[1] * d, base[2] * d)
    eps = 1.0 / size
    h0 = edge
    hR = voronoi((u + eps) * scale, v * scale)[2]
    hU = voronoi(u * scale, (v + eps) * scale)[2]
    bump = bump_strength or 2
    nx = (h0 - hR) * bump
    ny = (h0 - hU) * bump
    if flip_green:
        ny = -ny
    nor = fill(0.5 + nx * 0.5, 0.5 + ny * 0.5, np.ones_like(nx))
    return col, nor


def worn_metal_maps(size, paint_color, metal_color, wear_amount, wear_scale):
    pc = parse_color(paint_color)
    mc = parse_color(metal_color)
    X, Y = np.meshgrid(np.arange(size, dtype=np.float64), np.arange(size, dtype=np.float64))
    n = fbm(X / size * wear_scale, Y / size * wear_scale, 5)
    worn = (n > (1 - wear_amount)).astype(np.float64)
    col = fill(pc[0] * (1 - worn) + mc[0] * worn, pc[1] * (1 - worn) + mc[1] * worn,
               pc[2] * (1 - worn) + mc[2] * worn)
    rough = fill(np.where(worn > 0, 0.6, 0.3))
    metal = fill(np.where(worn > 0, 0.9, 0.3))
    return col, rough, metal
