"""THE WEAVE TILES: each fabric's yarns as a small HIGH (a height field of the threads, built from their paths and round
sections at real pitch), baked to a tileable normal + cavity tile the garment's material repeats at the cloth's real
scale (the macro normal map at 3.4 px/mm cannot hold a 0.2-0.7 mm yarn: AAA garments carry it as a detail tile).

    jersey   single-jersey knit: wales of V loops (0.70 mm wale, 0.58 mm course), the loop legs as round yarns
    poplin   1/1 plain weave, fine (warp 0.20 mm, weft 0.24 mm), each yarn over / under its crossings
    twill    2/1 cotton twill (0.42 mm), the diagonal wale of chino / drill
    leather  calf grain: a cellular pebble with fine creases (the shoes' upper)
    tile(fabric, n=512) -> (height (n, n) in mm, tile size in mm, normal RGB uint8, cavity uint8)
"""
import numpy as np

TILE_MM = {'jersey': 7.0, 'poplin': 4.8, 'twill': 5.04, 'leather': 12.0, 'rib': 6.0}


def _round(d, r):
    """a yarn's height at distance d from its axis (radius r): a flattened round (a yarn is spun fibres, pressed into
    the cloth: its sides do not stand vertical, so the tile's slopes stay finite)"""
    return r * np.clip(1.0 - (d / r) ** 2, 0.0, None) ** 0.75


def height(fabric, n=512):
    s = TILE_MM[fabric]
    u = (np.arange(n) + 0.5) / n * s
    X, Y = np.meshgrid(u, u)                       # x across (weft / course), y along (warp / wale)
    if fabric == 'jersey':
        wale, course = s / 10, s / 12
        cx = (X % wale) - wale / 2                 # across the wale
        cy = (Y % course) / course                 # along the course 0..1
        # each loop: two legs leaning in a V from the course's top to the next's bottom
        lean = (0.5 - cy) * wale * 0.42
        dl = np.abs(cx + wale * 0.22 + lean)
        dr = np.abs(cx - wale * 0.22 - lean)
        r = wale * 0.26
        H = np.maximum(_round(dl, r), _round(dr, r))
        # the sinker loops between courses sit lower
        H *= 0.75 + 0.25 * np.cos(np.pi * (cy - 0.5)) ** 2
    elif fabric == 'rib':
        p = s / 8
        cx = (X % p) / p
        H = 0.25 * (0.5 + 0.5 * np.cos(2 * np.pi * cx)) + 0.05 * np.cos(2 * np.pi * Y / (s / 10)) ** 2
    elif fabric in ('poplin', 'twill'):
        nw = 24 if fabric == 'poplin' else 12
        p = s / nw
        i = np.floor(X / p).astype(int)
        j = np.floor(Y / p).astype(int)
        if fabric == 'poplin':
            warp_up = (i + j) % 2 == 0
        else:
            warp_up = (i + j) % 3 != 0                 # 2/1: the warp floats two, under one: a diagonal
        fx = (X % p) - p / 2
        fy = (Y % p) - p / 2
        r = p * 0.46
        hw = _round(fx, r) * np.where(warp_up, 1.0, 0.55)        # the warp yarn along y
        hf = _round(fy, r * 0.9) * np.where(warp_up, 0.55, 1.0)  # the weft along x
        # the crossings' undulation: a yarn rises toward its float's middle
        hw *= 0.8 + 0.2 * np.cos(np.pi * fy / p) ** 2
        hf *= 0.8 + 0.2 * np.cos(np.pi * fx / p) ** 2
        H = np.maximum(hw, hf)
    else:   # leather
        rng = np.random.default_rng(3)
        pts = rng.random((420, 2)) * s
        P = np.stack([X, Y], -1)
        d1 = np.full(X.shape, 1e9)
        d2 = np.full(X.shape, 1e9)
        for ox in (-s, 0, s):
            for oy in (-s, 0, s):
                for q in pts + [ox, oy]:
                    d = np.hypot(X - q[0], Y - q[1])
                    nd2 = np.minimum(d2, np.maximum(d1, d))
                    d1 = np.minimum(d1, d)
                    d2 = nd2
        H = np.clip((d2 - d1) / 0.25, 0, 1) ** 0.5 * 0.04
    return H, s


def tile(fabric, n=512, strength=1.0):
    H, s = height(fabric, n)
    px = s / n
    gx = (np.roll(H, -1, 1) - np.roll(H, 1, 1)) / (2 * px)
    gy = (np.roll(H, -1, 0) - np.roll(H, 1, 0)) / (2 * px)
    N = np.stack([-gx * strength, gy * strength, np.ones_like(H)], -1)     # image rows top-down: +g is up the image
    N /= np.linalg.norm(N, axis=-1, keepdims=True)
    # NO MEAN TILT: the tile's average normal is exactly +z (a skewed yarn profile left a mean tilt that a mirrored twin
    # half turned the other way: a half-shirt tone step in the engine, look/e02 vs gnoweave), at every mip level
    for _ in range(3):
        N[..., :2] -= N[..., :2].mean(axis=(0, 1))
        N /= np.linalg.norm(N, axis=-1, keepdims=True)
    nrm = np.clip((N * 0.5 + 0.5) * 255 + 0.5, 0, 255).astype(np.uint8)
    # cavity: the height against its blurred neighbourhood
    from scipy import ndimage
    b = ndimage.uniform_filter(H, size=max(3, n // 40), mode='wrap')
    cav = np.clip(0.5 + (H - b) / (np.ptp(H) + 1e-9) * 1.2, 0, 1)
    return H, s, nrm, (cav * 255).astype(np.uint8)
