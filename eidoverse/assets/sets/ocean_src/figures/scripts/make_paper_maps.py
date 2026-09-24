# make_paper_maps.py — per-page paper maps for pages.glb (system Python: PIL + numpy).
# Source: AmbientCG Paper001 (CC0) 2K: Color / Roughness / NormalGL.
# Output (tex/pages/): page_2023_color.jpg, page_2026_color.jpg, paper_orm.jpg (R=AO 1, G=roughness, B=metal 0),
# paper_normal.png. 1536x2048 (Letter aspect 0.773 -> 0.75, a 3% squeeze, invisible in fibre).
#
# ORIENTATION: pages.glb uses Blender v=0 at the page TOP (so three.js uv().y = 1 at the top, like
# THREE.PlaneGeometry). Blender samples image row "bottom" at v=0, so the page TOP shows the image's BOTTOM
# row. Wear is authored in PAGE space (row 0 = page top) and flipped vertically before saving.
import numpy as np
from PIL import Image, ImageFilter
import os, sys

HERE = os.path.dirname(os.path.abspath(__file__))
SRC = os.path.join(HERE, '..', 'tex', 'Paper001')
OUT = os.path.join(HERE, '..', 'tex', 'pages'); os.makedirs(OUT, exist_ok=True)
W, H = 1536, 2048
rng = np.random.default_rng(23)

def load(name, mode='RGB'):
    # Paper001 is LANDSCAPE (2048x1201): turn it portrait, scale uniformly to cover 1536x2048, centre-crop.
    im = Image.open(os.path.join(SRC, f'Paper001_{name}.jpg')).convert(mode).transpose(Image.ROTATE_90)
    k = max(W / im.width, H / im.height)
    im = im.resize((int(round(im.width * k)), int(round(im.height * k))), Image.LANCZOS)
    x0 = (im.width - W) // 2; y0 = (im.height - H) // 2
    return np.asarray(im.crop((x0, y0, x0 + W, y0 + H)), dtype=np.float32) / 255.0

col = load('Color'); rough = load('Roughness', 'L'); nrm = load('NormalGL')
# ROTATE_90 (counter-clockwise): new +x = old +y, new +y = old -x
nx, ny = nrm[..., 0].copy(), nrm[..., 1].copy()
nrm[..., 0] = ny; nrm[..., 1] = 1.0 - nx

# ---- distance to the nearest edge in mm (page 215.9 x 279.4 mm)
yy, xx = np.mgrid[0:H, 0:W].astype(np.float32)
mmx = 215.9 / W; mmy = 279.4 / H
de = np.minimum.reduce([xx * mmx, (W - 1 - xx) * mmx, yy * mmy, (H - 1 - yy) * mmy])

def noise(scale_px, seed):
    r = np.random.default_rng(seed)
    small = r.random((H // scale_px + 2, W // scale_px + 2)).astype(np.float32)
    im = Image.fromarray((small * 255).astype(np.uint8)).resize((W + 2 * scale_px, H + 2 * scale_px), Image.BICUBIC)
    a = np.asarray(im, dtype=np.float32)[scale_px:scale_px + H, scale_px:scale_px + W] / 255.0
    return a

def wear(tint, seed, corner):
    c = col.copy()
    base_lum = c.mean(axis=2, keepdims=True)
    c = c / np.maximum(base_lum.mean(), 1e-3) * 0.93             # normalise brightness: a clean printed sheet
    c = c * np.array(tint, np.float32)[None, None, :]
    # large, faint unevenness (sizing / handling)
    blotch = noise(180, seed) * 0.6 + noise(60, seed + 1) * 0.4
    c *= (1.0 - 0.025 * (blotch - 0.5))[..., None]
    # edge: a faint aged band (~1.2 mm) + ragged nicks along the cut
    ragged = noise(6, seed + 2)
    band = np.clip(1.0 - de / (0.6 + 1.4 * ragged), 0, 1) ** 1.5
    edge_tint = np.array([0.93, 0.90, 0.84], np.float32)
    c = c * (1 - 0.35 * band[..., None]) + c * edge_tint[None, None, :] * (0.35 * band[..., None])
    # a thumb-smudge at the handled corner (page space: row 0 = top)
    cy, cx = corner
    d = np.sqrt(((xx - cx * W) * mmx) ** 2 + ((yy - cy * H) * mmy) ** 2)
    smudge = np.exp(-(d / 28.0) ** 2) * (0.5 + 0.5 * noise(40, seed + 3))
    c *= (1.0 - 0.035 * smudge)[..., None]
    return np.clip(c, 0, 1)

def save_rgb(a, name, q=93):
    im = Image.fromarray((np.clip(a, 0, 1) * 255 + 0.5).astype(np.uint8))
    im = im.transpose(Image.FLIP_TOP_BOTTOM)                   # page space -> Blender/three UV space (see header)
    p = os.path.join(OUT, name)
    im.save(p, quality=q) if name.endswith('.jpg') else im.save(p)
    print('WROTE', p, im.size)

# 2023: a clean, slightly cool office white.   2026: warmer cream, a touch more handled.
save_rgb(wear((0.975, 0.985, 1.0), 11, (0.93, 0.92)), 'page_2023_color.jpg')
save_rgb(wear((1.0, 0.965, 0.9), 26, (0.95, 0.06)), 'page_2026_color.jpg')
r2 = np.clip(rough * 0.35 + 0.55, 0, 1)                            # paper: matte, a little breakup
orm = np.stack([np.ones_like(r2), r2, np.zeros_like(r2)], axis=-1)
save_rgb(orm, 'paper_orm.jpg', 95)
n2 = nrm.copy(); n2[..., :2] = (n2[..., :2] - 0.5) * 0.6 + 0.5          # subtler fibre relief
save_rgb(n2, 'paper_normal.png')
