"""Paint the modificanti's faces, their emissive rims, the ghost SDF atlas and Balla's sun disc (system Python: PIL+numpy).

    python eidoverse/assets/vrms/claude_suit_wardrobe_src/paint_badges.py

Reads badges.json (the outlines build_tuta.py extrudes) and writes into eidoverse/assets/vrms/claude_suit_wardrobe_tex/:
  mod_<key>.png / mod_<key>_emit.png   1024 px over uv_extent mm, centred on the badge origin. The bottom-right 32 px
                                       are the RIM swatch: build_tuta.py maps the badge's sides and chamfer there, so
                                       the edges glow (emit) in the badge's colour.
  badges_sdf.png                       the ghost atlas: one 256 px tile per badge (badge order in badges.json), the
                                       union of its pieces as a signed distance in mm: v = 128 + 8 * d (inside < 128)
  sundisc.png / sundisc_emit.png       Balla's segmented sun: rings x segments, dark seams between
Text and pictograms are MATERIAL (painted here), never geometry.
"""
import json
import math
import os
import random

import numpy as np
from PIL import Image, ImageDraw, ImageFilter, ImageFont

import uf_shapes as U

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = HERE
while REPO != os.path.dirname(REPO) and not os.path.exists(os.path.join(REPO, 'eido.py')):
    REPO = os.path.dirname(REPO)
TEX = os.path.join(REPO, 'eidoverse', 'assets', 'vrms', 'claude_suit_wardrobe_tex')
SPEC = json.load(open(os.path.join(HERE, 'badges.json'), encoding='utf-8'))
EXT = SPEC['uv_extent']
N = 1024
SS = 3                                                   # supersampling for the vector work
RIM = 32                                                 # the rim swatch (px): build_tuta.py maps sides to its centre


def hexc(h, a=255):
    h = h.lstrip('#')
    return tuple(int(h[i:i + 2], 16) for i in (0, 2, 4)) + (a,)


def to_px(x, y, n=N * SS):
    """badge mm -> texture pixel (row 0 = top = +y)"""
    return ((0.5 + x / EXT) * n, (0.5 - y / EXT) * n)


def mask_of(pieces, grow=0.0, n=N):
    """union of the pieces (optionally offset outward/inward by `grow` mm) as a float mask in [0,1]"""
    im = Image.new('L', (n * SS, n * SS), 0)
    d = ImageDraw.Draw(im)
    for poly in pieces:
        d.polygon([to_px(x, y, n * SS) for x, y in poly], fill=255)
    if grow:
        k = int(abs(grow) / EXT * n * SS) * 2 + 1
        im = im.filter(ImageFilter.MaxFilter(k) if grow > 0 else ImageFilter.MinFilter(k))
    im = im.resize((n, n), Image.LANCZOS)
    return np.asarray(im, dtype=np.float32) / 255.0


def sdf_mm(pieces, n=256):
    """signed distance (mm) of the union of pieces on an n x n grid over uv_extent (brute force, edges)"""
    ys, xs = np.mgrid[0:n, 0:n].astype(np.float64)
    X = (xs + 0.5) / n * EXT - EXT / 2
    Y = EXT / 2 - (ys + 0.5) / n * EXT
    best = np.full((n, n), 1e9)
    inside = np.zeros((n, n), bool)
    for poly in pieces:
        P = np.array(poly)
        A, B = P, np.roll(P, -1, axis=0)
        ins = np.zeros((n, n), bool)
        for (ax, ay), (bx, by) in zip(A, B):
            ex, ey = bx - ax, by - ay
            t = np.clip(((X - ax) * ex + (Y - ay) * ey) / (ex * ex + ey * ey + 1e-12), 0, 1)
            dx, dy = X - (ax + t * ex), Y - (ay + t * ey)
            best = np.minimum(best, np.sqrt(dx * dx + dy * dy))
            cond = ((ay > Y) != (by > Y)) & (X < (bx - ax) * (Y - ay) / (by - ay + 1e-12) + ax)
            ins ^= cond
        inside |= ins
    return np.where(inside, -best, best)


def compose(base_rgb, layers):
    """base_rgb HxWx3 float 0..1; layers: [(rgb_array_or_tuple, alpha HxW)]"""
    out = base_rgb.copy()
    for rgb, a in layers:
        rgb = np.asarray(rgb, np.float32)
        if rgb.ndim == 1:
            rgb = rgb[None, None, :3] / (255.0 if rgb.max() > 1 else 1.0)
        out = out * (1 - a[..., None]) + rgb * a[..., None]
    return out


def save(arr, name):
    im = Image.fromarray(np.clip(arr * 255 + 0.5, 0, 255).astype(np.uint8), 'RGB')
    im.save(os.path.join(TEX, name))


def rim_swatch(arr, rgb):
    arr[-RIM:, -RIM:, :] = np.asarray(rgb, np.float32)[:3] / 255.0
    return arr


def noise(n, scale, seed):
    rng = np.random.default_rng(seed)
    small = rng.random((max(2, n // scale), max(2, n // scale))).astype(np.float32)
    return np.asarray(Image.fromarray((small * 255).astype(np.uint8)).resize((n, n), Image.BICUBIC), np.float32) / 255.0


yy, xx = np.mgrid[0:N, 0:N].astype(np.float32)
MMX = (xx + 0.5) / N * EXT - EXT / 2
MMY = EXT / 2 - (yy + 0.5) / N * EXT


def edge_bands(pieces):
    """inner distance (mm) from the outline, per pixel (inside only): for bevels and glow bands"""
    d = sdf_mm(pieces, N)
    return np.clip(-d, 0, None), d


def paint_red(b, pieces):
    din, d = edge_bands(pieces)
    inside = (d < 0).astype(np.float32)
    g = np.clip((MMX + 80) / 160, 0, 1)
    base = np.stack([0.58 + 0.24 * g, 0.03 + 0.04 * g, 0.06 + 0.04 * g], -1)              # cadmium enamel, lighter at the base
    hatch = (np.sin((MMX * 0.6 + MMY * 0.8) * 2 * math.pi / 1.6) > 0.6).astype(np.float32) * 0.05
    base *= (1 - hatch)[..., None]
    gloss = np.exp(-((MMY - 0.13 * MMX - 7) / 3.6) ** 2) * 0.38                          # a gloss streak along the wedge
    base = compose(base, [((1.0, 0.75, 0.75), gloss * inside)])
    bevel = np.clip(1 - np.abs(din - 2.6) / 0.7, 0, 1)                                   # an engraved inner line
    base = compose(base, [((0.32, 0.0, 0.02), bevel * 0.7)])
    edge = np.clip(1 - din / 1.4, 0, 1) * inside
    base = compose(base, [((1.0, 0.28, 0.3), edge)])
    alb = base * inside[..., None] + 0.05 * (1 - inside[..., None])
    emi = np.zeros((N, N, 3), np.float32)
    emi = compose(emi, [((1.0, 0.12, 0.16), edge), ((0.25, 0.0, 0.02), inside * 0.5)])
    return alb, emi


def paint_gold(b, pieces):
    din, d = edge_bands(pieces)
    inside = (d < 0).astype(np.float32)
    band = 0.5 + 0.5 * np.sin(MMY * 0.32 + MMX * 0.05)                                  # polished metal: soft bands
    lo, hi = np.array([0.55, 0.36, 0.06]), np.array([1.0, 0.86, 0.42])
    base = lo + (hi - lo) * band[..., None] ** 1.6
    groove = np.clip(1 - np.abs(din - 3.2) / 0.6, 0, 1)                                  # engraved inner outline
    base = compose(base, [((0.35, 0.2, 0.02), groove * 0.85)])
    spark = (noise(N, 3, 7) > 0.93).astype(np.float32) * 0.25                            # sparkle of the polish
    base = compose(base, [((1, 0.97, 0.85), spark * inside)])
    edge = np.clip(1 - din / 1.3, 0, 1) * inside
    base = compose(base, [((1.0, 0.92, 0.55), edge)])
    alb = base * inside[..., None] + 0.05 * (1 - inside[..., None])
    emi = compose(np.zeros((N, N, 3), np.float32), [((1.0, 0.72, 0.18), edge), ((0.2, 0.12, 0.0), inside * 0.6)])
    return alb, emi


def paint_chrome(b, pieces):
    din, d = edge_bands(pieces)
    inside = (d < 0).astype(np.float32)
    # chrome = the world reflected: a bright sky band, a dark horizon, ground below; tinted dollar green
    yb = MMY * 0.9 + MMX * 0.25
    sky = np.clip((yb + 6) / 30, 0, 1)
    refl = np.where(yb > -2, 0.55 + 0.45 * sky, 0.12 + 0.18 * np.clip((yb + 40) / 38, 0, 1))
    horizon = np.exp(-((yb + 2) / 1.2) ** 2) * 0.6
    tint = np.array([0.62, 0.86, 0.6])
    base = refl[..., None] * tint[None, None, :] + horizon[..., None] * np.array([0.9, 1.0, 0.9])
    # banknote guilloche: interleaved sine ribbons, engraved
    gl = np.zeros((N, N), np.float32)
    for k in range(8):
        yk = -80 + k * 24
        w = np.abs(MMY - (yk + 5.0 * np.sin(MMX * 0.3 + k)))
        gl = np.maximum(gl, np.clip(1 - w / 0.5, 0, 1))
    base = compose(base, [((0.12, 0.25, 0.12), gl * 0.4 * inside)])
    edge = np.clip(1 - din / 1.3, 0, 1) * inside
    base = compose(base, [((0.75, 1.0, 0.8), edge)])
    alb = base * inside[..., None] + 0.05 * (1 - inside[..., None])
    emi = compose(np.zeros((N, N, 3), np.float32), [((0.3, 1.0, 0.55), edge), ((0.0, 0.12, 0.05), inside * 0.5)])
    return alb, emi


def paint_warning(b, pieces):
    din, d = edge_bands(pieces)
    inside = (d < 0).astype(np.float32)
    base = np.full((N, N, 3), 0.94, np.float32) * np.array([1.0, 0.995, 0.97])
    border = ((din > 3.2) & (din < 9.6)).astype(np.float32)
    # the pictogram: a toaster with two slices up (the showroom's appliance) -- painted, not geometry
    im = Image.new('L', (N * SS, N * SS), 0)
    dr = ImageDraw.Draw(im)
    def P(x, y):
        return to_px(x * 1.45, y * 1.45 + 1.0)
    px_mm = N * SS / EXT * 1.45
    for x0 in (-8.6, 1.4):                                                                         # the slices (bread)
        dr.rounded_rectangle([P(x0, 6.5), P(x0 + 7.2, -3)], radius=2.4 * px_mm, fill=255)
        dr.rounded_rectangle([P(x0 + 1.1, 5.4), P(x0 + 6.1, -3)], radius=1.6 * px_mm, fill=0)     # crust line
    dr.rounded_rectangle([P(-13, -1.2), P(13, -15.5)], radius=4.2 * px_mm, fill=255)               # the body
    dr.rectangle([P(-10.5, -2.2), P(10.5, -3.6)], fill=0)                                           # slot rims
    dr.rectangle([P(13, -5.5), P(16.2, -7.6)], fill=255)                                            # the lever
    dr.rectangle([P(-10.5, -15.5), P(-7, -17.6)], fill=255)                                         # feet
    dr.rectangle([P(7, -15.5), P(10.5, -17.6)], fill=255)
    picto = np.asarray(im.resize((N, N), Image.LANCZOS), np.float32) / 255.0
    base = compose(base, [((0.06, 0.06, 0.07), border), ((0.06, 0.06, 0.07), picto)])
    grime = noise(N, 24, 3) * 0.08
    base = base * (1 - grime[..., None])
    edge = np.clip(1 - din / 1.3, 0, 1) * inside
    alb = base * inside[..., None] + 0.05 * (1 - inside[..., None])
    emi = compose(np.zeros((N, N, 3), np.float32), [((0.85, 0.95, 1.0), edge), ((0.1, 0.1, 0.11), inside * (1 - border) * (1 - picto) * 0.8)])
    return alb, emi



def paint_spray(b, pieces):
    """a tall canvas patch down the sleeve: CLANKER sprayed through a cut stencil, reading top to bottom"""
    din, d = edge_bands(pieces)
    inside = (d < 0).astype(np.float32)
    # the patch: black twill canvas
    tw = 0.5 + 0.5 * np.sin((MMX + MMY) * 2 * math.pi / 1.5)
    base = np.stack([0.11 + 0.03 * tw, 0.11 + 0.03 * tw, 0.125 + 0.03 * tw], -1)
    base *= (0.85 + 0.3 * noise(N, 40, 11))[..., None]
    # merrowed edge: dense diagonal satin stitch in fluoro magenta thread
    merrow = (din < 3.6).astype(np.float32) * inside
    st = 0.6 + 0.4 * np.sin((MMX - MMY) * 2 * math.pi / 1.2)
    base = compose(base, [((1.0, 0.31, 0.85), merrow * st)])
    # the stencil, fitted to the patch: 104 mm along it, at most 42 mm across
    text = 'CLANKER'
    fpath = None
    for f in ('impact.ttf', 'arialbd.ttf', 'arial.ttf'):
        if os.path.exists(os.path.join('C:/Windows/Fonts', f)):
            fpath = os.path.join('C:/Windows/Fonts', f)
            break
    if fpath is None:                                               # not Windows: the bundled condensed grotesk
        fpath = os.path.join(REPO, 'eidoverse', 'assets', 'fonts', 'Anton-Regular.ttf')
    px = N * SS / EXT                                               # supersampled px per mm
    size = 40.0
    for _ in range(3):
        font = ImageFont.truetype(fpath, int(size * px))
        bx = ImageDraw.Draw(Image.new('L', (8, 8))).textbbox((0, 0), text, font=font)
        w_mm, h_mm = (bx[2] - bx[0]) / px, (bx[3] - bx[1]) / px
        size *= min(104.0 / w_mm, 42.0 / h_mm)
    font = ImageFont.truetype(fpath, int(size * px))
    tile = Image.new('L', (N * SS, N * SS), 0)
    dr = ImageDraw.Draw(tile)
    bx = dr.textbbox((0, 0), text, font=font)
    w, h = bx[2] - bx[0], bx[3] - bx[1]
    cx, cy = N * SS / 2, N * SS / 2
    dr.text((cx - w / 2 - bx[0], cy - h / 2 - bx[1]), text, font=font, fill=255)
    sw = int(0.8 * px)                                              # the stencil's bridges: a gap through every letter
    dr.rectangle([0, int(cy) - sw, N * SS, int(cy) + sw], fill=0)
    tile = tile.rotate(-90 - 3, resample=Image.BICUBIC, center=(cx, cy))      # down the sleeve, a hair off true
    ox, oy = to_px(0, 0)
    canvas = Image.new('L', (N * SS, N * SS), 0)
    canvas.paste(tile, (int(ox - cx), int(oy - cy)))
    sharp = np.asarray(canvas.resize((N, N), Image.LANCZOS), np.float32) / 255.0
    over = np.asarray(canvas.resize((N, N), Image.LANCZOS).filter(ImageFilter.GaussianBlur(9)), np.float32) / 255.0
    rng = random.Random(5)
    speck = (noise(N, 2, 21) > 0.82).astype(np.float32) * over * 1.4
    drip = np.zeros((N, N), np.float32)
    for k in range(2):                                              # two runs below the last letter
        x0 = rng.uniform(-12, 12)
        y0 = -50.0 + rng.uniform(-1, 1)
        L = rng.uniform(5, 9)
        m = (np.abs(MMX - x0) < 0.7) & (MMY < y0) & (MMY > y0 - L)
        drip = np.maximum(drip, m.astype(np.float32) * np.clip((MMY - (y0 - L)) / L + 0.3, 0, 1))
    paint = np.clip(sharp * 0.95 + over * 0.22 + speck * 0.5 + drip * 0.9, 0, 1) * inside * (1 - merrow)
    spray = (1.0, 0.27, 0.08)
    base = compose(base, [(spray, paint)])
    edge = np.clip(1 - din / 1.0, 0, 1) * inside
    alb = base * inside[..., None] + 0.05 * (1 - inside[..., None])
    emi = compose(np.zeros((N, N, 3), np.float32), [((0.95, 0.2, 0.75), merrow * st * 0.75), ((0.9, 0.22, 0.05), paint * 0.45), ((1.0, 0.3, 0.86), edge)])
    return alb, emi


PAINTERS = {'mod_red': paint_red, 'mod_gold': paint_gold, 'mod_chrome': paint_chrome, 'mod_warning': paint_warning, 'mod_spray': paint_spray}

os.makedirs(TEX, exist_ok=True)
tiles = []
for key, b in SPEC['badges'].items():
    pieces = U.pieces_of(b)
    alb, emi = PAINTERS[key](b, pieces)
    alb = rim_swatch(alb, hexc(b['colour']))
    emi = rim_swatch(emi, hexc(b['glow']))
    save(alb, f'{key}.png')
    save(emi, f'{key}_emit.png')
    d = sdf_mm(pieces, 256)
    tiles.append(np.clip(128 + 8 * d, 0, 255).astype(np.uint8))
    print('painted', key, 'pieces', len(pieces))
Image.fromarray(np.concatenate(tiles, axis=1), 'L').save(os.path.join(TEX, 'badges_sdf.png'))

# ---- Balla's segmented sun disc (behind the petal ring): a warm sun of concentric segmented rings, a few neon accents
M = 1024
ys, xs = np.mgrid[0:M, 0:M].astype(np.float32)
u = (xs + 0.5) / M * 2 - 1
v = 1 - (ys + 0.5) / M * 2
r = np.sqrt(u * u + v * v)
a = (np.arctan2(v, u) / (2 * math.pi)) % 1.0
R0 = 0.17 / 0.34                                                  # the face hole / the disc radius (build_tuta.py)
rings = 4
fr_all = (r - R0) / (1 - R0) * rings
ri = np.clip(fr_all.astype(int), 0, rings - 1)
nseg = np.array([7, 9, 12, 15])[ri]
off = np.array([0.13, 0.41, 0.07, 0.29])[ri]
sj = np.floor((a + off) * nseg).astype(int) % nseg
base = np.array([hexc('#f2dfae')[:3], hexc('#e3a447')[:3], hexc('#e46a2a')[:3], hexc('#7a2a3c')[:3]], np.float32) / 255.0
col = base[ri]
rng = np.random.default_rng(14)
val = rng.uniform(0.78, 1.08, size=(rings, 16)).astype(np.float32)
col = col * val[ri, sj][..., None]
acc = {(1, 3): '#ff3fa4', (2, 7): '#29e7ff', (3, 2): '#ff3fa4', (3, 10): '#29e7ff', (0, 5): '#29e7ff'}
for (rk, sk), h in acc.items():
    m = (ri == rk) & (sj == sk)
    col[m] = np.array(hexc(h)[:3], np.float32) / 255.0
fr = fr_all % 1.0
fa = ((a + off) * nseg) % 1.0
seam = np.minimum(np.minimum(fr, 1 - fr) * (1 - R0) / rings * M / 2 / 1.2, np.minimum(fa, 1 - fa) * 2 * math.pi * r / nseg * M / 2 / 1.2)
seam = np.clip(seam, 0, 1)
shade = 0.82 + 0.25 * (1 - fr)                                    # each band brighter toward the centre (a sun)
inside = ((r >= R0) & (r <= 1.0)).astype(np.float32)
alb = (col * shade[..., None] * seam[..., None] + np.array([0.025, 0.02, 0.03]) * (1 - seam[..., None])) * inside[..., None]
emi = col * (0.42 * seam * shade)[..., None] * inside[..., None]
save(alb, 'sundisc.png')
save(emi, 'sundisc_emit.png')
print('sundisc ok')
