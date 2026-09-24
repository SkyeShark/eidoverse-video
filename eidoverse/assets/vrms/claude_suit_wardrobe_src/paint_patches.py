"""RECIPE (as run for the DAISY music video, 2026-09). Its stage inputs were working files that are not kept
here; claude_suit_wardrobe.blend is the finished, editable result. Read README.md in this folder first.

Embroidered patches for the claudesona's march jacket (DAISY bridge) -> tex_baked/patches_atlas.png (RGBA).

    python eidoverse/assets/vrms/claude_suit_wardrobe_src/paint_patches.py

Atlas 1024², three patches, alpha-cut to their shapes:
  A (0,0)-(512,512)      "our flower" — the claudesona's face in a ring of orange petals, navy twill, merrowed rim
  B (512,0)-(1024,512)   "day's eye" — the meaning of the word daisy: an eye with petals for lashes, cream twill
  C (0,512)-(1024,1024)  the banner "I'M ONE OF THEM" (her line to Opus 3 at the end of the bridge), stencil letters
Embroidery is drawn as thread: satin-stitch hatching inside every filled shape, a diagonal twill ground,
radial stitches on the merrowed rims, and a soft inner shadow so each patch sits raised on the canvas.
"""
import math
import os

import numpy as np
from PIL import Image, ImageDraw, ImageFilter, ImageFont

HERE = os.path.dirname(os.path.abspath(__file__))
FONTS = os.path.join(HERE, '..', '..', '..', 'eidoverse', 'assets', 'fonts')
OUT = os.path.join(HERE, 'tex_baked', 'patches_atlas.png')
SS = 2                                      # supersample, then downsample: clean edges
N = 1024 * SS
yy, xx = np.mgrid[0:N, 0:N].astype(np.float32)


def hexrgb(h):
    h = h.lstrip('#')
    return np.array([int(h[i:i + 2], 16) for i in (0, 2, 4)], np.float32) / 255.0


def mask(draw_fn):
    im = Image.new('L', (N, N), 0)
    draw_fn(ImageDraw.Draw(im))
    return np.asarray(im, np.float32) / 255.0


def satin(angle_deg, period=5.0 * SS, depth=0.22):
    """thread sheen: fine parallel stitches at an angle, with a slow sheen wobble along each thread"""
    a = math.radians(angle_deg)
    u = xx * math.cos(a) + yy * math.sin(a)
    v = -xx * math.sin(a) + yy * math.cos(a)
    ridge = 0.5 + 0.5 * np.cos(2 * math.pi * u / period)
    wob = 0.5 + 0.5 * np.sin(v / (37.0 * SS) + u / (91.0 * SS))
    return 1.0 - depth * (1.0 - ridge) + 0.06 * (wob - 0.5)


def radial_satin(cx, cy, period_deg=2.2, depth=0.28):
    ang = np.degrees(np.arctan2(yy - cy, xx - cx))
    ridge = 0.5 + 0.5 * np.cos(2 * math.pi * ang / period_deg)
    return 1.0 - depth * (1.0 - ridge)


img = np.zeros((N, N, 3), np.float32)
alpha = np.zeros((N, N), np.float32)


def paint(m, rgb, tex=1.0):
    global img
    c = hexrgb(rgb) if isinstance(rgb, str) else rgb
    img = img * (1 - m[..., None]) + (c[None, None, :] * np.asarray(tex)[..., None] if np.ndim(tex) else c * tex) * m[..., None]


def inner_shadow(m, radius=10 * SS, strength=0.35):
    """darken just inside a shape's edge: the patch reads as raised thread"""
    im = Image.fromarray((m * 255).astype(np.uint8)).filter(ImageFilter.GaussianBlur(radius))
    b = np.asarray(im, np.float32) / 255.0
    return 1.0 - strength * np.clip((1.0 - b) * m * 1.6, 0, 1)


# ------------------------------------------------------------------ A: our flower
cx, cy, R = 256 * SS, 256 * SS, 238 * SS
A_disc = mask(lambda d: d.ellipse([cx - R, cy - R, cx + R, cy + R], fill=255))
paint(A_disc, '#1b2340', satin(45, 4.0 * SS, 0.18))                       # navy twill ground
petals = np.zeros((N, N), np.float32)
for k in range(12):
    th = 2 * math.pi * k / 12 + math.pi / 12
    L0, L1, w = 70 * SS, 182 * SS, 30 * SS
    pts = []
    for s in np.linspace(0, 1, 48):                                       # a spoon petal: narrow neck, round tip
        r = L0 + (L1 - L0) * s
        half = w * (0.42 + 0.58 * math.sin(0.5 * math.pi * min(1.0, s / 0.62))) if s <= 0.78 else             w * math.sqrt(max(0.0, 1.0 - ((s - 0.78) / 0.22) ** 2))
        pts.append((r, half))
    poly = [(cx + r * math.cos(th) - h * math.sin(th), cy + r * math.sin(th) + h * math.cos(th)) for r, h in pts]
    poly += [(cx + r * math.cos(th) + h * math.sin(th), cy + r * math.sin(th) - h * math.cos(th)) for r, h in reversed(pts)]
    pm = mask(lambda d, poly=poly: d.polygon(poly, fill=255))
    petals = np.maximum(petals, pm)
    paint(pm, '#e8793a', satin(math.degrees(th), 4.5 * SS, 0.26))         # stitched along the petal
paint(petals, '#000000', 0.0) if False else None
face = mask(lambda d: d.ellipse([cx - 92 * SS, cy - 92 * SS, cx + 92 * SS, cy + 92 * SS], fill=255))
paint(face, '#f3efe6', satin(-20, 3.6 * SS, 0.14))
for ex in (-34, 34):                                                      # oval eyes
    em = mask(lambda d, ex=ex: d.ellipse([cx + (ex - 11) * SS, cy - 30 * SS, cx + (ex + 11) * SS, cy + 6 * SS], fill=255))
    paint(em, '#15151a', satin(90, 3.0 * SS, 0.2))
smile = mask(lambda d: d.line([(cx + x * SS, cy + (34 + 7 * math.cos(x / 9.5)) * SS) for x in range(-30, 31, 2)],
                              fill=255, width=6 * SS))                     # the wavy smile
paint(smile, '#15151a')
rim = A_disc - mask(lambda d: d.ellipse([cx - R + 22 * SS, cy - R + 22 * SS, cx + R - 22 * SS, cy + R - 22 * SS], fill=255))
paint(np.clip(rim, 0, 1), '#d99a2b', radial_satin(cx, cy))                # merrowed gold rim
img *= inner_shadow(A_disc)[..., None] * A_disc[..., None] + (1 - A_disc[..., None])
alpha = np.maximum(alpha, A_disc)

# ------------------------------------------------------------------ B: day's eye
cx, cy, R = 768 * SS, 256 * SS, 238 * SS
B_disc = mask(lambda d: d.ellipse([cx - R, cy - R, cx + R, cy + R], fill=255))
paint(B_disc, '#efe6cf', satin(-45, 4.0 * SS, 0.16))
for k in range(16):                                                       # petal lashes around the eye
    th = 2 * math.pi * k / 16
    ex, ey = 150 * SS * math.cos(th), 92 * SS * math.sin(th)
    tip = (cx + ex * 1.42, cy + ey * 1.62)
    base = (cx + ex, cy + ey)
    nx, ny = -math.sin(th) * 17 * SS, math.cos(th) * 17 * SS
    lm = mask(lambda d, b=base, t=tip, nx=nx, ny=ny: d.polygon([(b[0] + nx, b[1] + ny), t, (b[0] - nx, b[1] - ny)], fill=255))
    paint(lm, '#e8793a', satin(math.degrees(th), 4.0 * SS, 0.24))
eye = mask(lambda d: d.polygon([(cx + 152 * SS * math.cos(t) * (1 if math.cos(t) >= 0 else 1),
                                   cy + 88 * SS * math.sin(t) * abs(math.sin(t)) ** 0.15)
                                  for t in np.linspace(0, 2 * math.pi, 120)], fill=255))
paint(eye, '#fbfaf6', satin(0, 3.4 * SS, 0.12))
iris = mask(lambda d: d.ellipse([cx - 62 * SS, cy - 62 * SS, cx + 62 * SS, cy + 62 * SS], fill=255)) * eye
paint(iris, '#f2b632', radial_satin(cx, cy, 5.0, 0.3))                    # a golden disc florets iris
pupil = mask(lambda d: d.ellipse([cx - 26 * SS, cy - 26 * SS, cx + 26 * SS, cy + 26 * SS], fill=255))
paint(pupil, '#1a1410', satin(30, 3.0 * SS, 0.15))
glint = mask(lambda d: d.ellipse([cx + 8 * SS, cy - 30 * SS, cx + 24 * SS, cy - 14 * SS], fill=255))
paint(glint, '#ffffff')
outline = eye - mask(lambda d: d.polygon([(cx + 140 * SS * math.cos(t), cy + 78 * SS * math.sin(t) * abs(math.sin(t)) ** 0.15)
                                           for t in np.linspace(0, 2 * math.pi, 120)], fill=255))
paint(np.clip(outline, 0, 1), '#2a2622')
rim = B_disc - mask(lambda d: d.ellipse([cx - R + 22 * SS, cy - R + 22 * SS, cx + R - 22 * SS, cy + R - 22 * SS], fill=255))
paint(np.clip(rim, 0, 1), '#2f8f86', radial_satin(cx, cy))               # teal merrowed rim
img *= inner_shadow(B_disc)[..., None] * B_disc[..., None] + (1 - B_disc[..., None])
alpha = np.maximum(alpha, B_disc)

# ------------------------------------------------------------------ C: the banner
x0, y0, x1, y1 = 24 * SS, 600 * SS, 1000 * SS, 936 * SS
C_ban = mask(lambda d: d.rounded_rectangle([x0, y0, x1, y1], radius=46 * SS, fill=255))
paint(C_ban, '#f1e9d6', satin(45, 4.0 * SS, 0.16))
txt = "I'M ONE OF THEM"
size = 132 * SS
while True:                                                               # fit the words inside the stitched border
    font = ImageFont.truetype(os.path.join(FONTS, 'BlackOpsOne-Regular.ttf'), size)
    tw = ImageDraw.Draw(Image.new('L', (8, 8))).textlength(txt, font=font)
    if tw <= (x1 - x0) - 120 * SS:
        break
    size -= 2 * SS
text_m = mask(lambda d: d.text(((x0 + x1) / 2, (y0 + y1) / 2), txt, font=font, fill=255, anchor='mm'))
paint(text_m, '#1d1b1e', satin(-12, 3.6 * SS, 0.22))
rule = mask(lambda d: [d.rectangle([x0 + 70 * SS, yv, x1 - 70 * SS, yv + 7 * SS], fill=255) for yv in (y0 + 44 * SS, y1 - 51 * SS)])
paint(rule, '#e8793a', satin(0, 3.0 * SS, 0.2))
brim = C_ban - mask(lambda d: d.rounded_rectangle([x0 + 20 * SS, y0 + 20 * SS, x1 - 20 * SS, y1 - 20 * SS], radius=30 * SS, fill=255))
paint(np.clip(brim, 0, 1), '#c9502b', satin(90, 3.0 * SS, 0.32))         # stitched red-orange border
img *= inner_shadow(C_ban)[..., None] * C_ban[..., None] + (1 - C_ban[..., None])
alpha = np.maximum(alpha, C_ban)

rgba = np.dstack([np.clip(img, 0, 1), np.clip(alpha, 0, 1)])
im = Image.fromarray((rgba * 255 + 0.5).astype(np.uint8), 'RGBA').resize((1024, 1024), Image.LANCZOS)
os.makedirs(os.path.dirname(OUT), exist_ok=True)
im.save(OUT)
prev = Image.new('RGBA', im.size, (64, 58, 50, 255))                      # preview on canvas-brown
prev.alpha_composite(im)
prev.convert('RGB').save(OUT.replace('.png', '_preview.png'))
print('wrote', OUT)
