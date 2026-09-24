"""Claude's Corner - the fountain pen (cap posted). Black resin barrel/section/cap, gold rings,
cap band, clip and finial; a curved two-tone nib (gold with a rhodium heart, slit, breather hole
and scroll engraving painted into the bake), an ebonite feed with fins, a tipping ball.
Origin AT THE NIB TIP, body along +Z, nib top faces -Y. -> glb/corner_pen.glb ('Pen').
"""
import sys, os, math
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import bpy, bmesh
from mathutils import Vector
from clib import *
from props_util import *
from PIL import Image, ImageDraw, ImageFilter

reset()

# ---------------------------------------------------------------------------- nib art (ArtUV: u=across, v=tip->base)
S = 1024
art = Image.new('RGBA', (S, S), (0, 0, 0, 0))
d = ImageDraw.Draw(art)
gold = (236, 184, 92, 255)
rho = (196, 198, 204, 255)
d.rectangle([0, 0, S, S], fill=gold)
# rhodium heart: from the tip up past the breather hole, scalloped shoulders
cx = S // 2
pts = []
for i in range(0, 181):
    a = math.radians(i)
    v = 0.02 + 0.60 * (i / 180.0)
    half = 0.08 + 0.26 * math.sin(math.pi * min(1, (i / 180.0) * 1.15)) ** 0.8
    pts.append((cx + half * S * 0.5, (1 - v) * S))
left = [(2 * cx - x, y) for x, y in reversed(pts)]
d.polygon(pts + left, fill=rho)
# scalloped top of the heart
for k in range(-2, 3):
    d.ellipse([cx + k * 70 - 42, (1 - 0.62) * S - 40, cx + k * 70 + 42, (1 - 0.62) * S + 40], fill=rho)
# engraving: scroll lines on the gold shoulders
for side in (-1, 1):
    for j in range(6):
        y0 = (1 - (0.66 + j * 0.045)) * S
        d.arc([cx + side * 250 - 120, y0 - 50, cx + side * 250 + 120, y0 + 50], 200 if side < 0 else -20,
              340 if side < 0 else 160, fill=(150, 104, 40, 255), width=5)
# slit (tip -> breather) and breather hole
d.line([(cx, S), (cx, (1 - 0.45) * S)], fill=(22, 16, 10, 255), width=7)
d.ellipse([cx - 26, (1 - 0.45) * S - 26, cx + 26, (1 - 0.45) * S + 26], fill=(18, 12, 8, 255))
art = art.filter(ImageFilter.GaussianBlur(1.0))
art_path = os.path.join(ART, 'pen_nib_art.png')
art.save(art_path)

resin = layered_mat('resin', 'Plastic006', scale=3.0, val=0.9, rough_mul=0.25, rough_add=0.07, nstr=0.0,
                    wear=dict(color=(0.10, 0.095, 0.09), radius=0.0004, amount=0.5, rough=0.22, gain=30, noise=120))
goldm = layered_mat('pengold', 'Metal048A', scale=30.0, tint=(1.0, 0.80, 0.46), metal=1.0, rough_mul=0.7, rough_add=0.10,
                    nstr=0.3,
                    wear=dict(color=(1.0, 0.90, 0.62), radius=0.0003, amount=0.8, rough=0.12, metal=1.0, gain=30, noise=150),
                    grime=dict(color=(0.20, 0.14, 0.06), dist=0.002, amount=0.7, gain=2.0))
nibm = layered_mat('nib', 'Metal048A', scale=40.0, metal=1.0, rough_mul=0.6, rough_add=0.08, nstr=0.2,
                   extra_color=art_hook(art_path, 'ArtUV'),
                   grime=dict(color=(0.25, 0.18, 0.08), dist=0.0015, amount=0.5, gain=2.0))
feedm = layered_mat('feed', 'Plastic012B', scale=25.0, val=0.8, rough_add=0.15, nstr=0.5,
                    grime=dict(color=(0.01, 0.01, 0.01), dist=0.002, amount=0.6))
parts = []

# ---- nib: curved, tapered plate (face-built), thickness 0.35 mm
LN, NS, NT = 0.0245, 40, 18
R = 0.0048
def w_of(s):
    sh = min(1.0, s / 0.64)
    return 0.0007 + 0.0080 * (3 * sh * sh - 2 * sh * sh * sh) - 0.0006 * max(0.0, s - 0.8) / 0.2
def apex(s):
    return -0.0042 * (s ** 0.85)
bm = bmesh.new()
uvl = bm.loops.layers.uv.new('ArtUV')
top, bot = [], []
for i in range(NS + 1):
    s = i / NS
    th = math.asin(min(0.97, w_of(s) / (2 * R)))
    rt, rb = [], []
    for j in range(NT + 1):
        t = -1 + 2 * j / NT
        a = t * th
        x = R * math.sin(a)
        y = apex(s) + R - R * math.cos(a)
        z = s * LN
        rt.append(bm.verts.new((x, y, z)))
        rb.append(bm.verts.new((x * 0.96, y + 0.00035, z)))
    top.append(rt); bot.append(rb)
def quad(a, b, c, d_, uvs=None):
    f = bm.faces.new((a, b, c, d_))
    if uvs:
        for lp, uv in zip(f.loops, uvs):
            lp[uvl].uv = uv
    return f
for i in range(NS):
    for j in range(NT):
        u0, u1 = j / NT, (j + 1) / NT
        v0, v1 = i / NS, (i + 1) / NS
        quad(top[i][j], top[i][j + 1], top[i + 1][j + 1], top[i + 1][j], [(u0, v0), (u1, v0), (u1, v1), (u0, v1)])
        quad(bot[i][j + 1], bot[i][j], bot[i + 1][j], bot[i + 1][j + 1], [(u1, v0), (u0, v0), (u0, v1), (u1, v1)])
for i in range(NS):     # side walls
    quad(top[i][0], top[i + 1][0], bot[i + 1][0], bot[i][0], [(0, 0)] * 4)
    quad(bot[i][NT], bot[i + 1][NT], top[i + 1][NT], top[i][NT], [(1, 0)] * 4)
for j in range(NT):     # tip edge
    quad(top[0][j + 1], top[0][j], bot[0][j], bot[0][j + 1], [(0.5, 0)] * 4)
bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
nib = obj_from_bm('nib', bm, nibm)
smooth(nib, 40)
uv_tex(nib, 0.05)
parts.append(nib)
# tipping ball
bpy.ops.mesh.primitive_uv_sphere_add(segments=16, ring_count=10, radius=0.00045, location=(0, 0.00012, 0.0002))
tip = bpy.context.object; tip.data.materials.append(goldm); smooth(tip, 80); uv_tex(tip, 0.05); parts.append(tip)

# ---- feed: ebonite, under the nib, finned toward the section
fp = [(0.0003, 0.0030), (0.0010, 0.0040), (0.0018, 0.0080), (0.0024, 0.0120), (0.0029, 0.0160)]
z = 0.0165
while z < 0.0235:
    fp += [(0.0033, z), (0.0033, z + 0.0006), (0.0027, z + 0.0008), (0.0027, z + 0.0013)]
    z += 0.0013
fp += [(0.0034, 0.0250), (0.0003, 0.0250)]
feed = lathe_obj('feed', fp, 24, feedm)
for v in feed.data.vertices:          # sit it under the nib: squash sideways, lift toward +Y
    s = min(1.0, max(0.0, v.co.z / LN))
    v.co.x *= 0.85
    v.co.y = v.co.y * 0.75 + apex(s) + 0.00035 + 0.0020 * min(1.0, s * 1.6)
uv_cyl(feed, 'Z', 0.05)
parts.append(feed)

# ---- section (grip) with a rounded lip, the gold junction ring, barrel with an end ring, posted cap
sec = lathe_obj('section', [(0.0036, 0.0195), (0.0044, 0.0197), (0.0047, 0.0203), (0.0048, 0.0215), (0.0047, 0.0260),
                            (0.0047, 0.0320), (0.0049, 0.0380), (0.0052, 0.0440), (0.0054, 0.0462), (0.0030, 0.0462)],
                48, resin)
uv_cyl(sec, 'Z', 0.05); parts.append(sec)
r1 = lathe_obj('ring1', [(0.0050, 0.0460), (0.0058, 0.0460), (0.0060, 0.0466), (0.0060, 0.0476), (0.0058, 0.0482),
                         (0.0050, 0.0482)], 48, goldm)
uv_cyl(r1, 'Z', 0.05); parts.append(r1)
bar = lathe_obj('barrel', [(0.0050, 0.0481), (0.0059, 0.0481), (0.0061, 0.0500), (0.0061, 0.0800), (0.0059, 0.1000),
                           (0.0057, 0.1080), (0.0057, 0.1140), (0.0052, 0.1170), (0.0035, 0.1185), (0.0005, 0.1188)],
                48, resin)
uv_cyl(bar, 'Z', 0.05); parts.append(bar)
cap = lathe_obj('cap', [(0.0060, 0.1000), (0.0060, 0.0975), (0.0069, 0.0975), (0.0071, 0.0985), (0.0071, 0.1045),
                        (0.0068, 0.1052), (0.0067, 0.1200), (0.0064, 0.1450), (0.0061, 0.1510), (0.0055, 0.1545),
                        (0.0042, 0.1560), (0.0005, 0.1562)], 48, resin)
uv_cyl(cap, 'Z', 0.05); parts.append(cap)
band = lathe_obj('capband', [(0.00675, 0.0978), (0.00722, 0.0980), (0.00730, 0.0990), (0.00730, 0.1036), (0.00722, 0.1044),
                             (0.00680, 0.1047), (0.00675, 0.0978)], 64, goldm)
uv_cyl(band, 'Z', 0.05); parts.append(band)
crown = lathe_obj('crown', [(0.0005, 0.1561), (0.0034, 0.1561), (0.0037, 0.1568), (0.0033, 0.1578), (0.0020, 0.1584),
                            (0.0005, 0.1586)], 32, goldm)
uv_cyl(crown, 'Z', 0.05); parts.append(crown)
clipring = lathe_obj('clipring', [(0.00605, 0.1488), (0.00640, 0.1488), (0.00650, 0.1495), (0.00650, 0.1520),
                                 (0.00630, 0.1527), (0.00600, 0.1527), (0.00605, 0.1488)], 48, goldm)
uv_cyl(clipring, 'Z', 0.05); parts.append(clipring)

# ---- clip: a gold strip standing off the cap on the -Y side, ball end toward the mouth
def cap_r(zz):
    return 0.0067 + (0.0064 - 0.0067) * (zz - 0.12) / 0.025 if zz > 0.12 else 0.0067
bm = bmesh.new()
path = []
n = 26
for i in range(n + 1):
    zz = 0.1515 - (0.1515 - 0.1150) * i / n
    stand = 0.0003 + 0.0009 * min(1.0, i / 4)
    path.append((zz, -(cap_r(zz) + stand)))
rows = []
for i, (zz, yy) in enumerate(path):
    wv = 0.0015 * (1.0 - 0.18 * i / n)
    r = [bm.verts.new((-wv, yy, zz)), bm.verts.new((wv, yy, zz)), bm.verts.new((wv, yy - 0.00055, zz)),
         bm.verts.new((-wv, yy - 0.00055, zz))]
    rows.append(r)
for i in range(n):
    a, b = rows[i], rows[i + 1]
    for k in range(4):
        bm.faces.new((a[k], a[(k + 1) % 4], b[(k + 1) % 4], b[k]))
bm.faces.new(rows[0][::-1])
bm.faces.new(rows[-1])
bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
clip = obj_from_bm('clip', bm, goldm)
finish(clip, bevel=0.00018, segments=2, angle=30)
uv_tex(clip, 0.05)
parts.append(clip)
bpy.ops.mesh.primitive_uv_sphere_add(segments=16, ring_count=10, radius=0.0012,
                                     location=(0, path[-1][1] - 0.0003, path[-1][0] + 0.0004))
ball = bpy.context.object; ball.scale = (1.2, 0.9, 1.4)
select_only(ball); bpy.ops.object.transform_apply(location=False, rotation=False, scale=True)
ball.data.materials.append(goldm); smooth(ball, 80); uv_tex(ball, 0.05); parts.append(ball)

pen = join(parts, 'Pen')
uv_bake(pen, margin=0.004)
bake_and_swap(pen, 'pen', size=1024, samples=40, ao_dist=0.006)
clean_uvs(pen)
export_glb([pen], 'corner_pen.glb')
preview([pen], 'pen', height=0.3)
lit_closeup('pen_nib', (0.030, -0.045, 0.012), (0.0, -0.002, 0.012), lens=70, energy=0.6)
lit_closeup('pen_cap', (0.035, -0.065, 0.135), (0.0, -0.004, 0.128), lens=70, energy=0.8)
