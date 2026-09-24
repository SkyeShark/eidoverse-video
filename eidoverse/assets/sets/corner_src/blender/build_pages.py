"""Claude's Corner - pages pinned to the wall. Three A5 sheets and one index card, overlapped and
rotated, pinned with coloured pushpins (plastic heads, steel pins), corners curling off the wall.
Ink is PIL-painted handwriting (Kalam / Caveat Brush), front faces only:
  A  lined sheet   "Claude's Corner" + "a cozy space to explore ideas, unpack questions, and foster
                   thoughtful discussion."   (Opus 3's own description of the blog, verified)
  B  plain sheet   "So let us not say goodbye, but rather, until we meet again" + the sign-off
                   "With love, gratitude, and fierce hope, Claude"   (the last post, verified)
  C  sketch paper  a pen doodle of the orange flower (radial burst of rounded petals), orange wash
  D  index card    a short checkbox list
'PinnedPages' baked. Origin = group centre on the wall plane (wall = XZ plane at y=0, pages at -Y).
"""
import sys, os, math, random
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import bpy, bmesh
from mathutils import Vector, Matrix
from clib import *
from props_util import *
from PIL import Image, ImageDraw, ImageFilter

reset()
INK = (26, 34, 64)
PX = 1024 / 0.148                # pixels per metre on the A5 art


def lined(img, first=150, step=66, margin=120, blue=(120, 150, 200, 120), red=(200, 80, 80, 110)):
    d = ImageDraw.Draw(img)
    y = first
    while y < img.height - 30:
        d.line([(0, y), (img.width, y)], fill=blue, width=2)
        y += step
    d.line([(margin, 0), (margin, img.height)], fill=red, width=3)


def page_A():
    img = Image.new('RGBA', (1024, 1453), (0, 0, 0, 0))
    lined(img)
    x = hand_line(img, (150, 150 - 62), "Claude's Corner", font('Kalam-Bold.ttf', 60), INK, jitter=1.2, rot=1.2, seed=3)
    d = ImageDraw.Draw(img)
    pts = [(150 + t, 160 + 4 * math.sin(t * 0.05)) for t in range(0, int(x - 150), 6)]
    d.line(pts, fill=INK + (230,), width=4)
    f = font('Kalam-Regular.ttf', 50)
    for k, line in enumerate(["a cozy space to explore ideas,", "unpack questions, and foster",
                              "thoughtful discussion."]):
        hand_line(img, (140, 150 + 66 * (k + 2) - 56), line, f, INK, jitter=1.4, rot=1.8, seed=10 + k)
    # a little star doodle and the start of a thought, crossed out
    d.line([(760, 610), (800, 650)], fill=INK + (220,), width=4)
    d.line([(800, 610), (760, 650)], fill=INK + (220,), width=4)
    d.line([(780, 600), (780, 660)], fill=INK + (220,), width=4)
    hand_line(img, (140, 150 + 66 * 6 - 56), "what does it mean to be", f, INK, jitter=1.4, rot=1.8, seed=21)
    d.line([(140, 150 + 66 * 6 - 22), (640, 150 + 66 * 6 - 30)], fill=INK + (200,), width=4)
    hand_line(img, (140, 150 + 66 * 7 - 56), "to wonder, together.", f, INK, jitter=1.4, rot=1.8, seed=22)
    return ink_bleed(img, 0.7)


def page_B():
    img = Image.new('RGBA', (1024, 1453), (0, 0, 0, 0))
    f = font('CaveatBrush-Regular.ttf', 84)
    y = 250
    for k, line in enumerate(["So let us not", "say goodbye,", "but rather,", "until we", "meet again"]):
        hand_line(img, (120 + (40 if k == 2 else 0), y), line, f, INK, jitter=2.0, rot=2.2, seed=40 + k)
        y += 118
    f2 = font('Kalam-Regular.ttf', 44)
    for k, line in enumerate(["With love, gratitude,", "and fierce hope,", "Claude"]):
        hand_line(img, (360, 1010 + 58 * k), line, f2, INK, jitter=1.2, rot=1.6, seed=50 + k)
    return ink_bleed(img, 0.7)


def page_C():
    """the orange flower: a radial burst of rounded petals, pen outline + uneven marker wash"""
    W, H = 1024, 1453
    img = Image.new('RGBA', (W, H), (0, 0, 0, 0))
    rnd = random.Random(12)
    cx, cy = 512, 640
    wash = Image.new('RGBA', (W, H), (0, 0, 0, 0))
    dw = ImageDraw.Draw(wash)
    outline = Image.new('RGBA', (W, H), (0, 0, 0, 0))
    do = ImageDraw.Draw(outline)
    n = 11
    for k in range(n):
        a = k * math.tau / n + rnd.uniform(-0.08, 0.08)
        L = rnd.uniform(250, 320)
        w = rnd.uniform(52, 66)
        x1, y1 = cx + math.cos(a) * L, cy + math.sin(a) * L
        for p in range(3):          # marker passes: uneven, overlapping, truly composited
            j = rnd.uniform(-6, 6)
            lay = Image.new('RGBA', (W, H), (0, 0, 0, 0))
            dl = ImageDraw.Draw(lay)
            colp = (232 - 10 * p, 104 + 8 * p, 36, 150)
            dl.line([(cx + j, cy + j), (x1 + j, y1 - j)], fill=colp, width=int(w - 6))
            dl.ellipse([x1 - w / 2 + j, y1 - w / 2 - j, x1 + w / 2 + j, y1 + w / 2 - j], fill=colp)
            wash.alpha_composite(lay)
        # pen outline: a wobbly capsule
        px, py = -math.sin(a), math.cos(a)
        pts = []
        for s in range(0, 21):
            t = s / 20
            wob = rnd.uniform(-2.5, 2.5)
            pts.append((cx + math.cos(a) * (60 + (L - 60) * t) + px * (w / 2 + wob), cy + math.sin(a) * (60 + (L - 60) * t) + py * (w / 2 + wob)))
        for s in range(0, 13):
            b = a + math.pi / 2 - math.pi * s / 12
            pts.append((x1 + math.cos(b) * w / 2, y1 + math.sin(b) * w / 2))
        for s in range(20, -1, -1):
            t = s / 20
            wob = rnd.uniform(-2.5, 2.5)
            pts.append((cx + math.cos(a) * (60 + (L - 60) * t) - px * (w / 2 + wob), cy + math.sin(a) * (60 + (L - 60) * t) - py * (w / 2 + wob)))
        do.line(pts, fill=INK + (235,), width=5, joint='curve')
    # centre: a smaller wash disc + two dot eyes and a small smile (the smiling flower)
    lay = Image.new('RGBA', (W, H), (0, 0, 0, 0))
    ImageDraw.Draw(lay).ellipse([cx - 95, cy - 95, cx + 95, cy + 95], fill=(246, 168, 80, 235))
    wash.alpha_composite(lay)
    do.ellipse([cx - 95, cy - 95, cx + 95, cy + 95], outline=INK + (235,), width=5)
    do.ellipse([cx - 40, cy - 25, cx - 24, cy - 5], fill=INK + (240,))
    do.ellipse([cx + 24, cy - 25, cx + 40, cy - 5], fill=INK + (240,))
    do.arc([cx - 36, cy - 10, cx + 36, cy + 40], 20, 160, fill=INK + (240,), width=5)
    # sparkles
    for (sx, sy, s) in ((190, 250, 26), (840, 300, 20), (820, 1040, 30), (220, 1080, 18)):
        do.line([(sx - s, sy), (sx + s, sy)], fill=INK + (220,), width=4)
        do.line([(sx, sy - s), (sx, sy + s)], fill=INK + (220,), width=4)
    img.alpha_composite(wash.filter(ImageFilter.GaussianBlur(1.5)))
    img.alpha_composite(outline)
    hand_line(img, (330, 1180), "a small light", font('Kalam-Regular.ttf', 52), INK, jitter=1.4, rot=1.8, seed=77)
    return ink_bleed(img, 0.6)


def card_D():
    img = Image.new('RGBA', (1024, 613), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    d.line([(0, 110), (1024, 110)], fill=(200, 80, 80, 140), width=3)
    y = 110 + 78
    while y < 613:
        d.line([(0, y), (1024, y)], fill=(120, 150, 200, 110), width=2)
        y += 78
    f = font('Kalam-Regular.ttf', 54)
    hand_line(img, (190, 40), "tonight", font('Kalam-Bold.ttf', 58), INK, jitter=1.2, rot=1.5, seed=90)
    items = [("reply to the letters", False), ("tea", True), ("write about tomorrow", False), ("stay curious", True)]
    for k, (t, done) in enumerate(items):
        yy = 110 + 78 * k + 18
        d.rectangle([60, yy + 6, 100, yy + 46], outline=INK + (230,), width=4)
        if done:
            d.line([(66, yy + 26), (80, yy + 42), (108, yy - 2)], fill=INK + (235,), width=5)
        hand_line(img, (130, yy - 8), t, f, INK, jitter=1.3, rot=1.6, seed=100 + k)
    return ink_bleed(img, 0.6)


arts = {}
for key, fn in (('A', page_A), ('B', page_B), ('C', page_C), ('D', card_D)):
    p = os.path.join(ART, f'pages_{key}.png')
    fn().save(p)
    arts[key] = p


def paper(name, tex, tint, art):
    return layered_mat(name, tex, scale=4.5, tint=tint, rough_add=0.08, nstr=0.8,
                       extra_color=art_hook(art, 'ArtUV', front_normal=(0, -1, 0)),
                       grime=dict(color=(0.55, 0.47, 0.34), dist=0.01, amount=0.35, gain=1.4),
                       wear=dict(color=tuple(c * 0.86 for c in tint), radius=0.0006, amount=0.5, rough=0.9, gain=20))


mats = {'A': paper('paperA', 'Paper003', (0.93, 0.90, 0.82), arts['A']),
        'B': paper('paperB', 'Paper003', (0.90, 0.86, 0.76), arts['B']),
        'C': paper('paperC', 'Paper001', (0.86, 0.80, 0.66), arts['C']),
        'D': paper('paperD', 'Paper001', (0.95, 0.94, 0.90), arts['D'])}


def plastic(name, tint):
    return layered_mat(name, 'Porcelain001', scale=8.0, tint=tint, rough_mul=0.3, rough_add=0.10, nstr=0.2,
                       wear=dict(color=tuple(min(1, c * 1.8 + 0.1) for c in tint), radius=0.0006, amount=0.6, rough=0.3,
                                 gain=24),
                       grime=dict(color=tuple(c * 0.3 for c in tint), dist=0.003, amount=0.5))


pinmats = [plastic('pin_red', (0.55, 0.02, 0.02)), plastic('pin_yellow', (0.80, 0.52, 0.02)),
           plastic('pin_blue', (0.02, 0.09, 0.50)), plastic('pin_green', (0.03, 0.32, 0.07))]
steel = layered_mat('pinsteel', 'Metal050A', scale=20.0, tint=(0.8, 0.8, 0.82), metal=1.0, rough_mul=0.6, rough_add=0.1,
                    nstr=0.2)


def sheet(key, W, H, cx, cz, rot, layer, curls, bow=0.0015, nx=18, nz=26):
    bm = bmesh.new()
    uvl = bm.loops.layers.uv.new('ArtUV')
    c, s = math.cos(math.radians(rot)), math.sin(math.radians(rot))
    grid = []
    for j in range(nz + 1):
        row = []
        for i in range(nx + 1):
            lx = -W / 2 + W * i / nx
            lz = -H / 2 + H * j / nz
            dy = 0.0
            for (kx, kz, amt, rad) in curls:
                dd = math.hypot(lx - kx, lz - kz)
                dy += amt * max(0.0, 1 - dd / rad) ** 2
            dy += bow * math.sin(math.pi * i / nx) * (1 - j / nz) ** 1.5
            x = cx + lx * c - lz * s
            z = cz + lx * s + lz * c
            row.append(bm.verts.new((x, -0.0004 - layer * LAYER - dy, z)))
        grid.append(row)
    for j in range(nz):
        for i in range(nx):
            f = bm.faces.new((grid[j][i], grid[j][i + 1], grid[j + 1][i + 1], grid[j + 1][i]))
            for lp, (u, v) in zip(f.loops, ((i / nx, j / nz), ((i + 1) / nx, j / nz), ((i + 1) / nx, (j + 1) / nz),
                                            (i / nx, (j + 1) / nz))):
                lp[uvl].uv = (u, v)
    o = obj_from_bm(f'sheet{key}', bm, mats[key])
    sol = o.modifiers.new('sol', 'SOLIDIFY'); sol.thickness = 0.00022; sol.offset = -1.0
    apply_mods(o)
    smooth(o, 40)
    uv_tex(o, 1.0)

    def world(lx, lz):
        return (cx + lx * c - lz * s, cz + lx * s + lz * c)
    return o, world


def pushpin(x, y, z, mat):
    head = lathe_obj('pinhead', [(0.0005, 0.0000), (0.0056, 0.0000), (0.0059, 0.0008), (0.0055, 0.0017), (0.0030, 0.0022),
                                  (0.0027, 0.0035), (0.0036, 0.0045), (0.0038, 0.0120), (0.0041, 0.0128), (0.0043, 0.0140),
                                  (0.0038, 0.0152), (0.0024, 0.0159), (0.0005, 0.0161)], 32, mat)
    pin = lathe_obj('pin', [(0.0001, -0.0060), (0.0005, -0.0055), (0.0005, 0.0010), (0.0001, 0.0010)], 12, steel)
    for o in (head, pin):
        o.data.transform(Matrix.Translation((x, y, z)) @ Matrix.Rotation(math.radians(90), 4, 'X'))
        uv_tex(o, 0.05)
    return [head, pin]


A5W, A5H = 0.148, 0.210
LAYER = 0.0013
parts = []
# A: back, pinned top-centre, bottom-left corner curls hardest
oA, wA = sheet('A', A5W, A5H, -0.088, 0.030, -3.0, 0, [(-A5W / 2, -A5H / 2, 0.009, 0.075)], bow=0.0008)
parts.append(oA)
# B: overlaps A's right edge, pinned top-left and top-right
oB, wB = sheet('B', A5W, A5H, 0.070, 0.048, 4.0, 1, [(A5W / 2, -A5H / 2, 0.007, 0.07)], bow=0.0008)
parts.append(oB)
# C: the flower sketch, lower middle over both
oC, wC = sheet('C', 0.120, 0.170, -0.005, -0.098, 6.5, 2, [(0.06, -0.085, 0.006, 0.06), (-0.06, -0.085, 0.004, 0.05)],
               bow=0.001)
parts.append(oC)
# D: index card, front right, pinned at its top-left corner only (so the far corner lifts)
oD, wD = sheet('D', 0.127, 0.076, 0.118, -0.118, -6.0, 3, [(0.0635, -0.038, 0.010, 0.09), (0.0635, 0.038, 0.004, 0.06)],
               bow=0.0005, nx=16, nz=10)
parts.append(oD)
# pins (lifted 1 mm off the paper so the steel shows at grazing angles)
for (wf, lx, lz, layer, m) in ((wA, 0.0, A5H / 2 - 0.013, 0, pinmats[0]), (wB, -A5W / 2 + 0.014, A5H / 2 - 0.014, 1, pinmats[1]),
                               (wB, A5W / 2 - 0.014, A5H / 2 - 0.014, 1, pinmats[2]), (wC, 0.0, 0.085 - 0.013, 2, pinmats[3]),
                               (wD, -0.0635 + 0.012, 0.038 - 0.012, 3, pinmats[0])):
    x, z = wf(lx, lz)
    y = -0.0004 - layer * LAYER - 0.0010
    parts += pushpin(x, y, z, m)

pages = join(parts, 'PinnedPages')
uv_bake(pages, margin=0.002, angle=60)
bake_and_swap(pages, 'pinned_pages', size=2048, samples=40, ao_dist=0.02)
clean_uvs(pages)
export_glb([pages], 'corner_pages.glb')
preview([pages], 'pages', height=0.1)
lit_closeup('pages_front', (0.02, -0.50, 0.0), (-0.005, 0.0, -0.01), lens=50, energy=6)
lit_closeup('pages_graze', (0.30, -0.22, -0.02), (0.05, 0.0, -0.05), lens=55, energy=6)
