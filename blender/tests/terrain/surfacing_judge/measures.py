"""The surfacing judge's measures (SURFACING_DESIGN.md section 6), numpy and Pillow only. The look measures are
diagnostics: each sits beside a board, computed the same way on the place's reference (the matched photograph's
ground) and read against it, and the eye decides. Shimmer, seams, plants' spacing and cost are defect checks: they
gate.

    from surfacing_judge import measures as M

    one-material share     M.exclusive(cov) -> E;  M.one_material(E, valid) -> pure, largest (the audit's coverage)
                           M.reference_one_material(photo, ground, k) -> the photograph's own largest class region
    height-line index      M.contour_index(a, h, cell, sel);  M.layer_contours(E, h, cell, slope)
    repetition             M.repetition(lum, box, mode='2d' | 'rows') -> peak, lag and the window's high-pass energy
    within-layer variation M.block_stats(rgb, mask);  M.layer_variation(rgb, weights, ground)
    colour                 M.colour_compare(render, render_mask, photo, photo_mask) (after exposure matching);
                           M.hue_relation(...)
    seams                  M.seam_delta(rgb, line_px, normal_px, visible)
    plants                 M.stems_per_ha(x, y, area_m2);  M.pair_correlation(x, y, window, r_edges)
    reading                M.flag(name, value, reference) (diagnostics); M.verdict(name, value) (the gates)

Conventions: an image is float (H, W, 3) sRGB-encoded 0..1, row 0 at the top; a field is (n, n), row 0 south, on
cell centres `cell` metres apart; a weight stack E is (layers, H, W), bottom layer first, summing to at most 1.
"""
from __future__ import annotations

import math

import numpy as np

# ------------------------------------------------------------------------------------------ the reading ---
# SURFACING_DESIGN.md section 6. The gates: (lo, hi), the value passes inside the closed range; None = no bound.
GATES = {
    'shimmer_excess': (None, 0.02),          # the shimmer probe's score over the old material's
    'seam_delta_e': (None, 2.0),             # mean colour step across a window edge, over the picture's own (control)
    'plants_edge_ratio': (0.9, 1.1 / 0.9),   # stems per hectare either side of a window edge, inner over outer
}
# The diagnostics, each read against its reference (flag() says when a value is flagged for the read):
#   largest_region      the render's largest one-material region over the photograph's own (k-means classes): flagged
#                       when it passes the photograph's by more than 0.10 of the ground
#   variation_ratio     within-layer spread of 32 px block luminance over the photograph's ground blocks: flagged under
#                       0.5
#   repetition          the autocorrelation's second peak: flagged over the photographs' 0.11
#   repetition_energy   the window's high-pass energy over today's render's in the same crop: flagged under 0.8 (blur
#                       cannot pass for de-tiling)
#   height_line_index   read against today's render (0.77-0.94 on walls) and random (0.64), and against the board: a
#                       bedded place's boundaries follow its beds; never flagged on its own
#   colour_delta_e, colour_spread_ratio   read with the board after exposure matching; never flagged on their own
FLAGS = {
    'largest_region': lambda v, ref: ref is not None and v > ref + 0.10,
    'variation_ratio': lambda v, ref: v < 0.5,
    'repetition': lambda v, ref: v > 0.11,
    'repetition_energy': lambda v, ref: v < 0.8,
}
TARGETS = GATES                               # the earlier name of the gates
PHOTO_REPETITION = (0.03, 0.11)               # the photographs' peaks, measured by the audit
RANDOM_CONTOUR = 2.0 / math.pi


def verdict(name, value):
    """'pass' | 'fail' | None (no value, or not a gate) for a gate in GATES."""
    if value is None or name not in GATES:
        return None
    lo, hi = GATES[name]
    return 'pass' if (lo is None or value >= lo) and (hi is None or value <= hi) else 'fail'


def flag(name, value, reference=None):
    """True when a diagnostic is flagged for the read (FLAGS), False when not, None when it cannot say."""
    if value is None or name not in FLAGS:
        return None
    return bool(FLAGS[name](value, reference))


# ------------------------------------------------------------------------------------------- colour spaces ---

def srgb_to_linear(c):
    c = np.asarray(c, np.float64)
    return np.where(c <= 0.04045, c / 12.92, ((np.maximum(c, 0.0) + 0.055) / 1.055) ** 2.4)


def linear_to_srgb(c):
    c = np.clip(np.asarray(c, np.float64), 0.0, None)
    return np.where(c <= 0.0031308, c * 12.92, 1.055 * c ** (1 / 2.4) - 0.055)


_XYZ = np.array([[0.4124564, 0.3575761, 0.1804375], [0.2126729, 0.7151522, 0.0721750],
                 [0.0193339, 0.1191920, 0.9503041]])
_WHITE = _XYZ.sum(1)                          # D65, the white of sRGB (1, 1, 1)


def srgb_to_lab(rgb):
    """sRGB-encoded (..., 3) 0..1 -> CIELAB (L* 0..100, a*, b*), D65."""
    xyz = srgb_to_linear(rgb) @ _XYZ.T / _WHITE
    f = np.where(xyz > (6 / 29) ** 3, np.cbrt(np.maximum(xyz, 0.0)), xyz / (3 * (6 / 29) ** 2) + 4 / 29)
    return np.stack([116 * f[..., 1] - 16, 500 * (f[..., 0] - f[..., 1]), 200 * (f[..., 1] - f[..., 2])], -1)


def delta_e(lab1, lab2):
    """The CIELAB colour difference of 1976 (Euclidean in L*a*b*): 2.3 is about one just-noticeable step."""
    return float(np.linalg.norm(np.asarray(lab1, np.float64) - np.asarray(lab2, np.float64)))


def luma(rgb):
    """Rec. 709 luma of the sRGB-encoded values: what the repetition measure high-passes (the audit's)."""
    rgb = np.asarray(rgb, np.float64)
    return rgb[..., 0] * 0.2126 + rgb[..., 1] * 0.7152 + rgb[..., 2] * 0.0722


def mean_lab(rgb, mask=None):
    """CIELAB of the mean linear colour of the masked pixels (light averages linearly, so the mean is taken before
    the conversion)."""
    lin = srgb_to_linear(rgb)
    m = lin.reshape(-1, 3).mean(0) if mask is None else lin[np.asarray(mask, bool)].mean(0)
    return srgb_to_lab(linear_to_srgb(m))


# ------------------------------------------------------------------------------------------- image helpers ---

def load_rgb(path, width=None):
    """An image file as float (H, W, 3) sRGB 0..1; width: resized to that many pixels across first (Lanczos), as the
    photographs are for the measures (960, the renders' width)."""
    from PIL import Image
    im = Image.open(path).convert('RGB')
    if width and im.width != width:
        im = im.resize((int(width), int(round(im.height * width / im.width))), Image.LANCZOS)
    return np.asarray(im, np.float64) / 255.0


def load_rgba(path):
    """An RGBA image as float (H, W, 4) 0..1 (8 or 16 bits per channel)."""
    from PIL import Image
    im = Image.open(path)
    a = np.asarray(im)
    if a.dtype == np.uint16:
        a = a.astype(np.float64) / 65535.0
    elif a.dtype == np.uint8 and a.ndim == 3 and a.shape[2] == 4:
        a = a.astype(np.float64) / 255.0
    else:
        a = np.asarray(im.convert('RGBA'), np.float64) / 255.0
    if a.ndim == 2:
        a = np.repeat(a[..., None], 3, 2)
    if a.shape[2] == 3:
        a = np.concatenate([a, np.ones(a.shape[:2] + (1,))], 2)
    return a


def gaussian_blur(a, sigma_x, sigma_y=None):
    """A separable Gaussian blur with mirrored borders (the edge sample not repeated) and a kernel cut at 4 sigma:
    the filter OpenCV's GaussianBlur applies to a float image, which the audit's repetition numbers were made
    with. A sigma under 0.1 leaves that axis alone."""
    out = np.asarray(a, np.float64)
    for axis, s in ((1, sigma_x), (0, sigma_x if sigma_y is None else sigma_y)):
        if s is None or s < 0.1:
            continue
        k = int(round(s * 8 + 1)) | 1
        r = k // 2
        x = np.arange(k) - r
        g = np.exp(-(x * x) / (2.0 * s * s))
        g /= g.sum()
        n = out.shape[axis]
        idx = np.arange(-r, n + r)
        period = 2 * n - 2 if n > 1 else 1
        idx = np.abs(idx) % period if n > 1 else np.zeros_like(idx)
        idx = np.where(idx >= n, period - idx, idx)
        p = np.take(out, idx, axis=axis)
        acc = np.zeros_like(out)
        for j in range(k):
            acc += g[j] * np.take(p, np.arange(j, j + n), axis=axis)
        out = acc
    return out


def largest_region(mask):
    """(area of the largest 8-connected region of a boolean mask, number of regions). Runs along the rows joined
    with the runs they touch in the row above, labelled by pointer jumping: numpy only."""
    m = np.asarray(mask, bool)
    if m.ndim != 2 or not m.any():
        return 0, 0
    H, W = m.shape
    p = np.zeros((H, W + 2), np.int8)
    p[:, 1:-1] = m
    d = np.diff(p, axis=1)
    rs, cs = np.nonzero(d == 1)                   # a run [cs, ce) in row rs (row-major order: the two lists pair up)
    _re, ce = np.nonzero(d == -1)
    n = len(rs)
    first = np.searchsorted(rs, np.arange(H + 1))  # runs of row r: first[r] .. first[r + 1]
    us, vs = [], []
    for r in range(1, H):
        a0, a1, b0, b1 = first[r - 1], first[r], first[r], first[r + 1]
        if a0 == a1 or b0 == b1:
            continue
        # a run above [s', e') touches [s, e) when s' <= e and e' >= s (a diagonal touch counts)
        lo = a0 + np.searchsorted(ce[a0:a1], cs[b0:b1], side='left')
        hi = a0 + np.searchsorted(cs[a0:a1], ce[b0:b1], side='right')
        cnt = hi - lo
        k = cnt > 0
        if not k.any():
            continue
        b = np.repeat(np.arange(b0, b1)[k], cnt[k])
        start = np.repeat(lo[k], cnt[k])
        off = np.arange(len(b)) - np.repeat(np.cumsum(cnt[k]) - cnt[k], cnt[k])
        us.append(b)
        vs.append(start + off)
    lab = np.arange(n)
    if us:
        u, v = np.concatenate(us), np.concatenate(vs)
        while True:
            lu, lv = lab[u], lab[v]
            mn = np.minimum(lu, lv)
            np.minimum.at(lab, lu, mn)
            np.minimum.at(lab, lv, mn)
            while True:                            # every run points at its root
                l2 = lab[lab]
                if np.array_equal(l2, lab):
                    break
                lab = l2
            if np.array_equal(lab[u], lab[v]):
                break
    area = np.bincount(lab, weights=(ce - cs).astype(np.float64), minlength=n)
    return int(area.max()), int((area > 0).sum())


# -------------------------------------------------------------------------------------- one-material share ---

def exclusive(cov):
    """Layer coverages (each 0..1, bottom first) composited as the material does, a layer covering what lies below
    it: E[i] = cov[i] * prod(1 - cov[j] for j above i). (layers, ...) float64."""
    cov = [np.clip(np.asarray(c, np.float64), 0.0, 1.0) for c in cov]
    out = [None] * len(cov)
    rem = np.ones_like(cov[0])
    for i in range(len(cov) - 1, -1, -1):
        out[i] = cov[i] * rem
        rem = rem * (1.0 - cov[i])
    return np.stack(out)


def one_material(E, valid=None, names=None, pure_at=0.9, dominant_at=0.5):
    """How much of the ground is one material (the audit's `pure` and `largest`). E: (layers, H, W) weights; valid:
    the ground (default everything). Returns
        pure_total   the share of the ground where one layer holds pure_at (0.9) of the weight or more
        largest      the largest connected region one layer dominates (it is the top layer there, over dominant_at),
                     as a share of the ground, and which layer it is
        layers       per layer: share (mean weight), pure, largest
    """
    E = np.asarray(E, np.float64)
    L = E.shape[0]
    v = np.ones(E.shape[1:], bool) if valid is None else np.asarray(valid, bool)
    nv = max(int(v.sum()), 1)
    top = E.argmax(0)
    topw = E.max(0)
    rows = []
    for i in range(L):
        dom = (top == i) & (topw > dominant_at) & v
        big, count = largest_region(dom)
        rows.append(dict(name=(names[i] if names else str(i)), share=float(E[i][v].sum() / nv),
                         pure=float(((top == i) & (topw >= pure_at) & v).sum() / nv), largest=big / nv,
                         regions=count))
    k = int(np.argmax([r['largest'] for r in rows]))
    return dict(pure_total=float(((topw >= pure_at) & v).sum() / nv), largest=rows[k]['largest'],
                largest_layer=rows[k]['name'], ground_px=int(v.sum()), layers=rows)


def kmeans(X, k, iters=25, seed=0, restarts=6):
    """k-means of the rows of X (n, d), k-means++ seeded, the best of `restarts` runs by their summed squared
    distance: (centres (k, d), labels (n,))."""
    X = np.asarray(X, np.float64)
    best = None
    for s in range(restarts):
        rng = np.random.default_rng(seed + s)
        C = [X[rng.integers(len(X))]]
        for _ in range(1, k):
            d2 = np.min(((X[:, None, :] - np.array(C)[None]) ** 2).sum(-1), 1)
            p = d2 / d2.sum() if d2.sum() > 0 else None
            C.append(X[rng.choice(len(X), p=p)])
        C = np.array(C)
        lab = np.zeros(len(X), int)
        for _ in range(iters):
            lab = ((X[:, None, :] - C[None]) ** 2).sum(-1).argmin(1)
            new = np.array([X[lab == j].mean(0) if (lab == j).any() else C[j] for j in range(k)])
            if np.allclose(new, C):
                break
            C = new
        inertia = float(((X - C[lab]) ** 2).sum())
        if best is None or inertia < best[0]:
            best = (inertia, C, lab)
    return best[1], best[2]


def reference_one_material(photo, ground, k, blur_px=2.0, contrast_px=4.0, sample=20000, seed=0):
    """The photograph's own one-material share, the reference the render's is read against (section 6): its ground
    clustered into k classes (k-means on CIELAB and local contrast, the photograph blurred blur_px first so the classes
    are materials, not grains), the labels smoothed over about 5 px, and the largest connected region one class
    covers, as a share of the ground. k is the number of layers the frame shows. Returns dict(largest, k, shares) or
    None when there is no ground."""
    g = np.asarray(ground, bool)
    if not g.any() or k < 1:
        return None
    rgb = np.asarray(photo, np.float64)
    lab = srgb_to_lab(np.stack([gaussian_blur(rgb[..., c], blur_px) for c in range(3)], -1))
    L = lab[..., 0]
    m1, m2 = gaussian_blur(L, contrast_px), gaussian_blur(L * L, contrast_px)
    contrast = np.sqrt(np.maximum(m2 - m1 * m1, 0.0))
    F = np.concatenate([lab, contrast[..., None]], -1)[g]
    F = np.clip((F - F.mean(0)) / np.maximum(F.std(0), 1e-9), -3.0, 3.0)   # the edges' contrast is no class
    F[:, 3] *= 0.5                                                          # of its own: texture weighs half
    rng = np.random.default_rng(seed)
    pick = rng.choice(len(F), min(sample, len(F)), replace=False)
    C, _ = kmeans(F[pick], int(k), seed=seed)
    labels = np.full(g.shape, -1)
    labels[g] = ((F[:, None, :] - C[None]) ** 2).sum(-1).argmin(1)
    votes = np.stack([gaussian_blur((labels == j).astype(np.float64), 2.0) for j in range(int(k))])
    smooth = np.where(g, votes.argmax(0), -1)
    n = int(g.sum())
    shares = [largest_region(smooth == j)[0] / n for j in range(int(k))]
    return dict(largest=float(max(shares)), k=int(k), shares=[float(s) for s in shares])


# ------------------------------------------------------------------------------------------ height-line index ---

def contour_index(a, h, cell, sel=None, min_grad=1e-4, min_slope_deg=0.5):
    """How closely the isolines of a field `a` follow height lines: the mean |cos| of the angle between grad a and
    grad h, weighted by |grad a|, over the cells of `sel` where a changes (|grad a| > min_grad per metre) and the
    ground slopes more than min_slope_deg. 1: every isoline of a is a contour; 0: they run straight down the slope
    (ribs, chutes); 2/pi = 0.64: at random to the contours. None when nothing qualifies. (The audit's contour index:
    coverage.py for layer weights, curv_contour.py for masks.)"""
    a = np.asarray(a, np.float64)
    h = np.asarray(h, np.float64)
    gy_h, gx_h = np.gradient(h, cell)
    gh = np.hypot(gx_h, gy_h)
    gy, gx = np.gradient(a, cell)
    ga = np.hypot(gx, gy)
    ok = (ga > min_grad) & (gh > math.tan(math.radians(min_slope_deg)))
    if sel is not None:
        ok &= np.asarray(sel, bool)
    if not ok.any():
        return None
    cosv = np.abs(gx * gx_h + gy * gy_h) / np.maximum(ga * gh, 1e-12)
    return float((cosv[ok] * ga[ok]).sum() / max(ga[ok].sum(), 1e-12))


def _contour_sums(a, h_grad, cell, ok0, min_grad):
    gx_h, gy_h, gh = h_grad
    gy, gx = np.gradient(a, cell)
    ga = np.hypot(gx, gy)
    ok = ok0 & (ga > min_grad)
    if not ok.any():
        return 0.0, 0.0
    cosv = np.abs(gx * gx_h + gy * gy_h) / np.maximum(ga * gh, 1e-12)
    return float((cosv[ok] * ga[ok]).sum()), float(ga[ok].sum())


def layer_contours(E, h, cell, slope_deg=None, names=None, steep_deg=25.0, border=8, min_grad=1e-4):
    """The height-line index of a palette's layer boundaries on a tile: per layer and over all layers together (every
    layer's weight gradient pooled), on all ground and on the ground steeper than steep_deg (the walls, where cliff,
    talus and ledge layers are placed). slope_deg: the tile's slope in degrees (default from h). The outer `border`
    cells are left out of the steep and pooled numbers, as the audit's mask index does; the per-layer `all` number
    takes the whole tile, as the audit's coverage does."""
    E = np.asarray(E, np.float64)
    h = np.asarray(h, np.float64)
    gy_h, gx_h = np.gradient(h, cell)
    gh = np.hypot(gx_h, gy_h)
    if slope_deg is None:
        slope_deg = np.degrees(np.arctan(gh))
    sloped = gh > math.tan(math.radians(0.5))
    inner = np.zeros(h.shape, bool)
    inner[border:h.shape[0] - border, border:h.shape[1] - border] = True
    steep = inner & (np.asarray(slope_deg, np.float64) > steep_deg)
    grad = (gx_h, gy_h, gh)
    rows = []
    pool = dict(all=[0.0, 0.0], steep=[0.0, 0.0])
    for i in range(E.shape[0]):
        s_all = _contour_sums(E[i], grad, cell, sloped, min_grad)
        s_in = _contour_sums(E[i], grad, cell, sloped & inner, min_grad)
        s_steep = _contour_sums(E[i], grad, cell, sloped & steep, min_grad)
        rows.append(dict(name=(names[i] if names else str(i)),
                         all=(s_all[0] / s_all[1] if s_all[1] > 0 else None),
                         steep=(s_steep[0] / s_steep[1] if s_steep[1] > 0 else None),
                         edge_weight=s_in[1]))
        for key, s in (('all', s_in), ('steep', s_steep)):
            pool[key][0] += s[0]
            pool[key][1] += s[1]
    return dict(all=(pool['all'][0] / pool['all'][1] if pool['all'][1] > 0 else None),
                steep=(pool['steep'][0] / pool['steep'][1] if pool['steep'][1] > 0 else None),
                steep_share=float(steep.mean()), random=RANDOM_CONTOUR, layers=rows)


# ------------------------------------------------------------------------------------------------ repetition ---

def _ac2d(win):
    h, w = win.shape
    x = win - gaussian_blur(win, 6.0)
    x = x / max(float(x.std()), 1e-9)
    hann = np.outer(np.hanning(h), np.hanning(w))
    H, W = 2 * h, 2 * w
    ac = np.fft.irfft2(np.abs(np.fft.rfft2(x * hann, s=(H, W))) ** 2, s=(H, W))
    acw = np.fft.irfft2(np.abs(np.fft.rfft2(hann, s=(H, W))) ** 2, s=(H, W))
    ac = ac / np.maximum(acw, 1e-6 * acw.max())
    return np.fft.fftshift(ac / ac[0, 0])


def _ac_rows(win):
    _h, w = win.shape
    x = win - gaussian_blur(win, 6.0, 0.0)
    x = x - x.mean(1, keepdims=True)
    x = x / np.maximum(x.std(1, keepdims=True), 1e-9)
    hann = np.hanning(w)[None, :]
    W = 2 * w
    ac = np.fft.irfft(np.abs(np.fft.rfft(x * hann, n=W, axis=1)) ** 2, n=W, axis=1).mean(0)
    acw = np.fft.irfft(np.abs(np.fft.rfft(hann, n=W, axis=1)) ** 2, n=W, axis=1)[0]
    ac = ac / np.maximum(acw, 1e-6 * acw.max())
    return ac / ac[0]


def repetition(lum, box=None, mode='2d', tile_px=None):
    """Repetition in a window of an image's luma: how strongly the window correlates with itself shifted by some lag
    beyond the texture's own grain (the audit's repeat_metric). A tiled texture correlates again at its tile period
    (an exact repeat scores 1); a photograph of ground stays near 0 beyond its grain (0.03-0.11 measured).

    lum    (H, W) luma (M.luma of an image)
    box    (x0, y0, x1, y1) pixels, default the whole image
    mode   '2d'   the normalised 2-D autocorrelation of the window (luma minus a Gaussian blur of sigma 6 px, divided
                  by its deviation, Hann-windowed, zero-padded, divided by the window's own autocorrelation); the
                  central lobe (out to where the radial mean first falls under 0.05) is skipped; reported: the highest
                  local maximum beyond it within a third of the window, and its lag (dx, dy)
           'rows' for ground seen at a grazing angle, where a row lies at one depth and a tile repeats at one period
                  along it: each row's 1-D autocorrelation along x, averaged over the window's rows
    tile_px       the expected period, to read the correlation there as well (at_tile_px)
    Returns dict(mode, peak, lag, lobe_px, energy[, at_tile_px]); peak None when the window has no maximum beyond its
    lobe. energy: the deviation of the high-passed luma (luma minus its blur of sigma 6 px, along the rows in 'rows'
    mode) before it is normalised: the fine detail the window holds. A blurred render loses its repeats and its
    energy together, so a low peak is read with the energy beside today's render's in the same crop (section 6).
    """
    L = np.asarray(lum, np.float64)
    if box is not None:
        x0, y0, x1, y1 = (int(v) for v in box)
        L = L[y0:y1, x0:x1]
    h, w = L.shape
    out = dict(mode=mode)
    hp = L - (gaussian_blur(L, 6.0, 0.0) if mode == 'rows' else gaussian_blur(L, 6.0))
    if mode == 'rows':
        hp = hp - hp.mean(1, keepdims=True)
    out['energy'] = float(hp.std())
    if mode == 'rows':
        ac = _ac_rows(L)
        lim = w // 3
        r0 = int(np.argmax(ac[:lim] < 0.05)) if np.any(ac[:lim] < 0.05) else lim
        best, lag = -1.0, None
        for k in range(max(r0, 2), lim - 1):
            if ac[k] >= ac[k - 1] and ac[k] >= ac[k + 1] and ac[k] > best:
                best, lag = float(ac[k]), int(k)
        out.update(peak=(best if lag is not None else None), lag=lag, lobe_px=r0)
        if tile_px and tile_px < lim - 3:
            t = int(round(tile_px))
            out['at_tile_px'] = float(ac[max(t - 3, 0):t + 4].max())
        return out
    ac = _ac2d(L)
    cy, cx = h, w
    yy, xx = np.mgrid[-cy:cy, -cx:cx]
    r = np.hypot(xx, yy)
    rb = np.round(r).astype(int)
    rmax = min(h, w) // 3
    prof = np.bincount(rb.ravel(), ac.ravel()) / np.maximum(np.bincount(rb.ravel()), 1)
    below = np.flatnonzero(prof[:rmax] < 0.05)
    r0 = int(below[0]) if below.size else rmax
    pad = np.pad(ac, 1, mode='edge')
    nb = np.stack([pad[1 + dy:1 + dy + ac.shape[0], 1 + dx:1 + dx + ac.shape[1]]
                   for dy in (-1, 0, 1) for dx in (-1, 0, 1) if dy or dx])
    sel = (ac >= nb.max(0)) & (r > r0) & (np.abs(xx) <= w // 3) & (np.abs(yy) <= h // 3)
    if sel.any():
        k = int(np.argmax(np.where(sel, ac, -9.0)))
        j, i = np.unravel_index(k, ac.shape)
        out.update(peak=float(ac[j, i]), lag=[int(xx[j, i]), int(yy[j, i])], lobe_px=r0)
    else:
        out.update(peak=None, lag=None, lobe_px=r0)
    if tile_px and tile_px < w // 3 - 3:
        t = int(round(tile_px))
        out['at_tile_px'] = float(ac[cy - 2:cy + 3, cx + t - 3:cx + t + 4].max())
    return out


# ------------------------------------------------------------------------- variation and colour, by blocks ---

def block_means(rgb, mask=None, block=32, cover=0.9):
    """The mean colour of every block x block tile of the image that `mask` covers by `cover` or more: (n, 3) linear
    RGB means of the masked pixels, and the blocks' (row, col) indices."""
    lin = srgb_to_linear(rgb)
    H, W = lin.shape[:2]
    nh, nw = H // block, W // block
    if nh == 0 or nw == 0:
        return np.zeros((0, 3)), np.zeros((0, 2), int)
    m = np.ones((H, W)) if mask is None else np.asarray(mask, np.float64)
    mb = m[:nh * block, :nw * block].reshape(nh, block, nw, block)
    cb = (lin[:nh * block, :nw * block] * m[:nh * block, :nw * block, None]).reshape(nh, block, nw, block, 3)
    wsum = mb.sum((1, 3))
    keep = wsum >= cover * block * block
    means = cb.sum((1, 3))[keep] / wsum[keep][:, None]
    return means, np.argwhere(keep)


def block_stats(rgb, mask=None, block=32, cover=0.9):
    """The spread of an area's colour at the scale the eye reads as "one flat material or not": the block means of
    block_means in CIELAB, their mean, their standard deviation per axis, and how many blocks there were (under 6
    the spreads are None: too few to say)."""
    means, _ij = block_means(rgb, mask, block, cover)
    n = len(means)
    if n == 0:
        return dict(n=0, lab=None, L_std=None, a_std=None, b_std=None, chroma_std=None)
    lab = srgb_to_lab(linear_to_srgb(means))
    out = dict(n=n, lab=[float(v) for v in lab.mean(0)])
    if n < 6:
        out.update(L_std=None, a_std=None, b_std=None, chroma_std=None)
    else:
        sd = lab.std(0)
        out.update(L_std=float(sd[0]), a_std=float(sd[1]), b_std=float(sd[2]),
                   chroma_std=float(math.hypot(sd[1], sd[2])))
    return out


def _ratio(a, b):
    return None if a is None or b is None or b <= 1e-9 else float(a / b)


def layer_variation(rgb, weights, ground=None, names=None, photo_stats=None, block=32, inside=0.9):
    """Within-layer variation: per layer, the spread of the 32 px block mean lightness (CIELAB L*) over the blocks
    that lie inside the layer (its weight over `inside` on 0.9 of the block), and that spread over the photograph's
    ground blocks (photo_stats: block_stats of the photograph's ground). A layer that paints one flat colour scores
    near 0; the target is half the photograph's spread or more."""
    W = np.asarray(weights, np.float64)
    g = np.ones(W.shape[1:], bool) if ground is None else np.asarray(ground, bool)
    rows = []
    for i in range(W.shape[0]):
        st = block_stats(rgb, (W[i] >= inside) & g, block)
        st['name'] = names[i] if names else str(i)
        st['ratio'] = _ratio(st['L_std'], photo_stats['L_std']) if photo_stats else None
        rows.append(st)
    return rows


def match_exposure(render, render_mask, photo, photo_mask):
    """The render scaled in linear light so its ground's mean luminance equals the photograph's ground's (the means
    move with exposure and haze, section 6): (scaled sRGB image, the scale)."""
    Y = np.array([0.2126, 0.7152, 0.0722])
    lr, lp = srgb_to_linear(render), srgb_to_linear(photo)
    yr = float((lr[np.asarray(render_mask, bool)] @ Y).mean())
    yp = float((lp[np.asarray(photo_mask, bool)] @ Y).mean())
    k = yp / max(yr, 1e-6)
    return linear_to_srgb(np.clip(lr * k, 0.0, 1.0)), k


def colour_compare(render, render_mask, photo, photo_mask, block=32, exposure=True):
    """The ground's colour in a render against the photograph's (both float sRGB images with a ground mask), with
    the render's exposure first matched to the photograph's ground (match_exposure; exposure=False skips it):
        delta_e        CIELAB difference of the two ground means
        delta_e_raw    the same before the exposure is matched
        spread_ratio   the render's spread of 32 px block means over the photograph's, for L*, and for a*, b*
                       together: under 1 the render is flatter than the place
        exposure_scale what the render's linear light was multiplied by
        render, photo  each side's mean Lab, block count and spreads
    All read with the board (section 6); none is a pass line."""
    rm, pm = np.asarray(render_mask, bool), np.asarray(photo_mask, bool)
    if not rm.any() or not pm.any():
        return dict(render=None, photo=None, delta_e=None, delta_e_raw=None, spread_ratio_L=None,
                    spread_ratio_ab=None, exposure_scale=None)
    raw = delta_e(mean_lab(render, rm), mean_lab(photo, pm))
    scale = 1.0
    if exposure:
        render, scale = match_exposure(render, rm, photo, pm)
    r = block_stats(render, rm, block)
    p = block_stats(photo, pm, block)
    rl, pl = mean_lab(render, rm), mean_lab(photo, pm)
    out = dict(render=dict(r, lab_mean=[float(v) for v in rl]), photo=dict(p, lab_mean=[float(v) for v in pl]))
    out['delta_e'] = delta_e(rl, pl)
    out['delta_e_raw'] = raw
    out['exposure_scale'] = scale
    out['spread_ratio_L'] = _ratio(r['L_std'], p['L_std'])
    out['spread_ratio_ab'] = _ratio(r['chroma_std'], p['chroma_std'])
    return out


def hue_relation(render, render_a, render_b, photo, photo_a, photo_b):
    """The colour step between two regions (talus against cliff, floor against wall) in the render and in the
    photograph: each side's Lab difference b - a, and the cosine between the two differences (1: the render's step
    points the way the photograph's does; negative: the wrong way). None when a region is empty."""
    if not (np.asarray(render_a).any() and np.asarray(render_b).any() and np.asarray(photo_a).any()
            and np.asarray(photo_b).any()):
        return None
    dr = mean_lab(render, render_b) - mean_lab(render, render_a)
    dp = mean_lab(photo, photo_b) - mean_lab(photo, photo_a)
    nr, npn = float(np.linalg.norm(dr)), float(np.linalg.norm(dp))
    cos = float(dr @ dp / (nr * npn)) if nr > 1e-6 and npn > 1e-6 else None
    return dict(render=[float(v) for v in dr], photo=[float(v) for v in dp], cosine=cos,
                render_delta_e=nr, photo_delta_e=npn)


# ---------------------------------------------------------------------------------------------------- seams ---

def _bilinear(img, x, y):
    H, W = img.shape[:2]
    x = np.clip(x, 0.0, W - 1.001)
    y = np.clip(y, 0.0, H - 1.001)
    i, j = np.floor(x).astype(int), np.floor(y).astype(int)
    fx, fy = (x - i)[..., None], (y - j)[..., None]
    return ((img[j, i] * (1 - fx) + img[j, i + 1] * fx) * (1 - fy)
            + (img[j + 1, i] * (1 - fx) + img[j + 1, i + 1] * fx) * fy)


def line_samples(points_px, visible=None, step=2.0):
    """A polyline in the picture (a window edge projected point by point: (n, 2) pixel x, y) resampled every `step`
    pixels along its visible segments (both ends visible): (positions (m, 2), unit normals (m, 2), visible (m,)). A
    hidden segment adds no length, so a point projected far outside the picture (just in front of the camera's
    plane) costs nothing."""
    P = np.asarray(points_px, np.float64).reshape(-1, 2)
    vis = np.ones(len(P), bool) if visible is None else np.asarray(visible, bool)
    if len(P) < 2:
        return np.zeros((0, 2)), np.zeros((0, 2)), np.zeros(0, bool)
    a, b = P[:-1], P[1:]
    seg = np.hypot(*(b - a).T)
    on = vis[:-1] & vis[1:] & np.isfinite(seg) & (seg > 1e-6)
    s = np.r_[0.0, np.cumsum(np.where(on, seg, 0.0))]
    if s[-1] < step:
        return np.zeros((0, 2)), np.zeros((0, 2)), np.zeros(0, bool)
    t = np.arange(0.5 * step, s[-1], step)
    k = np.clip(np.searchsorted(s, t, side='right') - 1, 0, len(seg) - 1)
    f = ((t - s[k]) / np.maximum(seg[k], 1e-9))[:, None]
    pos = a[k] * (1 - f) + b[k] * f
    tan = (b[k] - a[k]) / np.maximum(seg[k], 1e-9)[:, None]
    return pos, np.stack([-tan[:, 1], tan[:, 0]], 1), on[k]


def seam_delta(rgb, line_px, normal_px, visible=None, band=(1.5, 7.5), ground=None, weights=None, same_at=0.15):
    """The colour step across a line in a render (a level window's edge, projected into the picture):
        delta_e   CIELAB difference between the mean colour of a band on one side of the line and of the band on the
                  other (band = (near, far) pixels from the line along its normal). Averaging along the line first
                  cancels the ground's own variation and keeps a step that follows the line: a seam.
        control   the same difference between two bands of that width and spacing lying wholly on one side of the
                  line (either side, averaged): what the picture's own gradient gives where there is no seam
        excess    delta_e over the control (0 when under it): the step the line itself makes, which section 6's
                  target (2 delta E) is read against
        n         the samples used
    line_px (n, 2) pixel positions (x, y) along the line and normal_px (n, 2) unit normals (line_samples), visible
    (n,) which samples to use, ground (H, W) bool: only samples whose bands lie on the ground (a layer map's terrain)
    count, so the horizon and the sky never read as a seam. weights (layers, H, W), a layer map's: only samples where
    the two bands hold the same layers (their mean weights differ by under same_at, summed over the layers) count,
    so a window edge that runs along a landform's own edge (a rim, a cliff band's foot) is not read as a seam: what
    is left is the same material drawn differently on the two sides. None when under 8 samples are usable."""
    P = np.asarray(line_px, np.float64).reshape(-1, 2)
    N = np.asarray(normal_px, np.float64).reshape(-1, 2)
    H, W = rgb.shape[:2]
    near, far = float(band[0]), float(band[1])
    width, spacing = far - near, far + near                  # the two bands' width and centre-to-centre distance
    centre = far + 0.5 * spacing + 0.5 * width + 1.0          # the control pair's middle, clear of the seam's bands
    reach = centre + 0.5 * spacing + 0.5 * width
    ok = np.ones(len(P), bool) if visible is None else np.asarray(visible, bool).copy()
    for s in (-reach, reach):
        q = P + s * N
        ok &= (q[:, 0] >= 0) & (q[:, 0] <= W - 1) & (q[:, 1] >= 0) & (q[:, 1] <= H - 1)
    if ground is not None:
        g = np.asarray(ground, bool)
        for s in np.linspace(-reach, reach, 13):
            q = np.clip(np.round(P + s * N), 0, [W - 1, H - 1]).astype(int)
            ok &= g[q[:, 1], q[:, 0]]
    if weights is not None:
        Wt = np.asarray(weights, np.float64)

        def band_w(d0, d1):
            acc = 0.0
            for s in np.linspace(d0, d1, 4):
                q = np.clip(np.round(P + s * N), 0, [W - 1, H - 1]).astype(int)
                acc = acc + Wt[:, q[:, 1], q[:, 0]]
            return acc / 4.0
        ok &= np.abs(band_w(-far, -near) - band_w(near, far)).sum(0) < same_at
    if int(ok.sum()) < 8:
        return None
    P, N = P[ok], N[ok]
    lin = srgb_to_linear(rgb)

    def band_lab(d0, d1):
        ds = np.linspace(d0, d1, 7)
        q = P[:, None, :] + ds[None, :, None] * N[:, None, :]
        return srgb_to_lab(linear_to_srgb(_bilinear(lin, q[..., 0], q[..., 1]).reshape(-1, 3).mean(0)))
    ctl = []
    for sgn in (-1.0, 1.0):
        a = band_lab(sgn * centre - 0.5 * spacing - 0.5 * width, sgn * centre - 0.5 * spacing + 0.5 * width)
        b = band_lab(sgn * centre + 0.5 * spacing - 0.5 * width, sgn * centre + 0.5 * spacing + 0.5 * width)
        ctl.append(delta_e(a, b))
    de, c = delta_e(band_lab(-far, -near), band_lab(near, far)), float(np.mean(ctl))
    return dict(delta_e=de, control=c, excess=max(0.0, de - c), n=int(ok.sum()))


# --------------------------------------------------------------------------------------------------- plants ---

def stems_per_ha(n, area_m2):
    """Plants per hectare."""
    return float(n) / max(float(area_m2), 1e-9) * 1.0e4


def pairs_within(x, y, r, centres=None):
    """Every ordered pair of points (a, b), a among `centres` (indices; default all), b any other point, no farther
    apart than r: yields (a, b, distance) arrays, a few chunks. A grid of cells r wide, so each point meets only
    the points of its own cell and the eight around it."""
    x = np.asarray(x, np.float64)
    y = np.asarray(y, np.float64)
    r = float(r)
    gx = np.floor((x - x.min()) / r).astype(np.int64)
    gy = np.floor((y - y.min()) / r).astype(np.int64)
    nx = int(gx.max()) + 1
    key = gy * nx + gx
    order = np.argsort(key, kind='stable')
    ks = key[order]
    ci = np.arange(len(x)) if centres is None else np.asarray(centres, np.int64)
    for dy in (-1, 0, 1):
        for dx in (-1, 0, 1):
            ok = (gx[ci] + dx >= 0) & (gx[ci] + dx < nx) & (gy[ci] + dy >= 0)
            if not ok.any():
                continue
            c = ci[ok]
            nk = (gy[c] + dy) * nx + gx[c] + dx
            lo = np.searchsorted(ks, nk, side='left')
            cnt = np.searchsorted(ks, nk, side='right') - lo
            k = cnt > 0
            if not k.any():
                continue
            a = np.repeat(c[k], cnt[k])
            off = np.arange(len(a)) - np.repeat(np.cumsum(cnt[k]) - cnt[k], cnt[k])
            b = order[np.repeat(lo[k], cnt[k]) + off]
            d = np.hypot(x[a] - x[b], y[a] - y[b])
            keep = (a != b) & (d <= r)
            if keep.any():
                yield a[keep], b[keep], d[keep]


def pair_correlation(x, y, window, r_edges, max_points=20000, seed=0):
    """The pair correlation function g(r) of a point pattern in a rectangle (Ripley's isotropic estimate with the
    border method: only points farther than r_max from the rectangle's edge count as centres, so no ring is cut by
    the edge). g = 1 for plants placed independently (Poisson); over 1 where they cluster at that distance; 0 below
    a hard core.

    x, y      positions, metres
    window    (x0, y0, x1, y1), the rectangle the pattern was observed in
    r_edges   increasing ring edges, metres
    Returns dict(r (ring centres), g, pairs (per ring), centres, density (per m2)). More than max_points points are
    thinned at random first (g does not change under independent thinning)."""
    x = np.asarray(x, np.float64).ravel()
    y = np.asarray(y, np.float64).ravel()
    x0, y0, x1, y1 = (float(v) for v in window)
    keep = (x >= x0) & (x <= x1) & (y >= y0) & (y <= y1)
    x, y = x[keep], y[keep]
    if len(x) > max_points:
        k = np.random.default_rng(seed).choice(len(x), max_points, replace=False)
        x, y = x[k], y[k]
    r_edges = np.asarray(r_edges, np.float64)
    rmax = float(r_edges[-1])
    n = len(x)
    area = (x1 - x0) * (y1 - y0)
    lam = n / max(area, 1e-9)
    centre = (x >= x0 + rmax) & (x <= x1 - rmax) & (y >= y0 + rmax) & (y <= y1 - rmax)
    nc = int(centre.sum())
    counts = np.zeros(len(r_edges) - 1)
    if nc and n > 1:
        for _a, _b, d in pairs_within(x, y, rmax, np.flatnonzero(centre)):
            counts += np.histogram(d, bins=r_edges)[0]
    ring = math.pi * (r_edges[1:] ** 2 - r_edges[:-1] ** 2)
    g = counts / np.maximum(nc * lam * ring, 1e-12) if nc and lam > 0 else np.full(len(ring), np.nan)
    return dict(r=(0.5 * (r_edges[1:] + r_edges[:-1])).tolist(), g=g.tolist(), pairs=counts.tolist(), centres=nc,
                density=lam, points=n)


def plant_pattern(x, y, window, core_m, sigma_m=None, r_max=None):
    """A species' spacing read from its pair correlation: inhibited below the hard core (g under 0.1 inside 0.8 x
    core_m), and, for a clustered species, clustered at the cluster scale (g over 1.2 between the core and
    2 sigma_m). Returns dict(inhibited, g_core, clustered, g_cluster, g_far, r, g)."""
    r_max = float(r_max or max(4.0 * (sigma_m or core_m), 6.0 * core_m))
    edges = np.unique(np.r_[np.linspace(0.0, core_m, 5), np.linspace(core_m, r_max, 25)])
    pc = pair_correlation(x, y, window, edges)
    r, g = np.asarray(pc['r']), np.asarray(pc['g'])
    inner = r < 0.8 * core_m
    g_core = float(np.nanmean(g[inner])) if inner.any() else None
    out = dict(g_core=g_core, inhibited=(None if g_core is None or math.isnan(g_core) else bool(g_core < 0.1)),
               r=pc['r'], g=pc['g'], centres=pc['centres'], density=pc['density'], points=pc['points'])
    far = r > 0.75 * r_max
    out['g_far'] = float(np.nanmean(g[far])) if far.any() else None
    if sigma_m:
        mid = (r > core_m) & (r < 2.0 * sigma_m)
        out['g_cluster'] = float(np.nanmean(g[mid])) if mid.any() else None
        out['clustered'] = None if out['g_cluster'] is None or math.isnan(out['g_cluster']) \
            else bool(out['g_cluster'] > 1.2)
    return out
