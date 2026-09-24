"""Claude's Corner - the small rug. A 1.4 x 0.95 m woven rug, ~8 mm, lying slightly unevenly with
one corner lifting; PIL-painted village-rug design (indigo guard stripes, a deep-red main border
with an ochre/indigo running motif, a red field with a stepped-lozenge medallion, spandrels and
scattered stars, hand-dyed abrash banding) multiplied over Carpet015 pile, a faded walked-on patch
and dirt at the edges; knotted cotton fringes on both short ends.
'Rug' baked. Origin centre, bottom at z=0.
"""
import sys, os, math, random
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import bpy, bmesh
from mathutils import Vector
from clib import *
from props_util import *
from PIL import Image, ImageDraw, ImageFilter

reset()
RL, RW, RT = 1.40, 0.95, 0.008
S = 2048
SH = int(S * RW / RL)
PXM = S / RL
rnd = random.Random(5)

# ----------------------------------------------------------------------------- the design
RED = (128, 26, 28); RED2 = (150, 34, 32); OCH = (196, 134, 52); IND = (34, 44, 92); IVO = (226, 212, 180)
BRN = (70, 36, 24)
img = Image.new('RGB', (S, SH), RED2)
d = ImageDraw.Draw(img)


def rect(m, col):
    p = int(m * PXM)
    d.rectangle([p, p, S - 1 - p, SH - 1 - p], fill=col)


rect(0.000, IND)            # outer guard
rect(0.022, OCH)
rect(0.030, RED)            # main border ground
rect(0.118, IVO)
rect(0.124, IND)
rect(0.130, RED2)           # field
# running motif in the main border: stepped diamonds alternating ochre / indigo, with ivory hearts
bw0, bw1 = int(0.030 * PXM), int(0.118 * PXM)
mid = (bw0 + bw1) // 2
step = int(0.075 * PXM)


def diamond(cx, cy, r, col, inner=None):
    d.polygon([(cx, cy - r), (cx + r, cy), (cx, cy + r), (cx - r, cy)], fill=col)
    if inner:
        rr = r * 0.45
        d.polygon([(cx, cy - rr), (cx + rr, cy), (cx, cy + rr), (cx - rr, cy)], fill=inner)


k = 0
for x in range(bw1 + step // 2, S - bw1, step):
    c1 = OCH if k % 2 == 0 else IND
    diamond(x, mid, (bw1 - bw0) * 0.38, c1, IVO)
    diamond(x, SH - 1 - mid, (bw1 - bw0) * 0.38, IND if k % 2 == 0 else OCH, IVO)
    k += 1
for y in range(bw1 + step // 2, SH - bw1, step):
    diamond(mid, y, (bw1 - bw0) * 0.38, OCH, IVO)
    diamond(S - 1 - mid, y, (bw1 - bw0) * 0.38, IND, IVO)
# corner squares
for cx in (mid, S - 1 - mid):
    for cy in (mid, SH - 1 - mid):
        d.rectangle([cx - 38, cy - 38, cx + 38, cy + 38], fill=IND)
        d.rectangle([cx - 18, cy - 18, cx + 18, cy + 18], fill=OCH)
# field: stepped lozenge medallion
cx, cy = S // 2, SH // 2


def stepped(cx, cy, rx, ry, col, steps=9):
    q = []
    for i in range(steps):
        x0 = cx + rx * i / steps; x1 = cx + rx * (i + 1) / steps
        y0 = cy - ry * (1 - i / steps)
        q += [(x0, y0), (x1, y0)]
    q += [(cx + rx, cy)]
    q2 = [(x, 2 * cy - y) for (x, y) in reversed(q)]
    q3 = [(2 * cx - x, y) for (x, y) in reversed(q2)]
    q4 = [(2 * cx - x, y) for (x, y) in reversed(q)]
    d.polygon(q + q2 + q3 + q4, fill=col)


stepped(cx, cy, 0.40 * PXM, 0.25 * PXM, OCH)
stepped(cx, cy, 0.33 * PXM, 0.20 * PXM, IND)
stepped(cx, cy, 0.24 * PXM, 0.145 * PXM, RED)
diamond(cx, cy, 0.075 * PXM, IVO, OCH)
for sx in (-1, 1):
    diamond(cx + sx * int(0.15 * PXM), cy, int(0.035 * PXM), OCH, IND)
# spandrels in the field corners
f0 = int(0.130 * PXM)
for (ax, ay, sx, sy) in ((f0, f0, 1, 1), (S - 1 - f0, f0, -1, 1), (f0, SH - 1 - f0, 1, -1), (S - 1 - f0, SH - 1 - f0, -1, -1)):
    r = int(0.14 * PXM)
    d.polygon([(ax, ay), (ax + sx * r, ay), (ax, ay + sy * r)], fill=IND)
    r2 = int(0.07 * PXM)
    d.polygon([(ax, ay), (ax + sx * r2, ay), (ax, ay + sy * r2)], fill=OCH)


def star(x, y, r, col):
    for a in (0, 45):
        rr = r
        pts = []
        for kk in range(4):
            ang = math.radians(a + kk * 90)
            pts.append((x + math.cos(ang) * rr, y + math.sin(ang) * rr))
        d.polygon([pts[0], pts[1], pts[2], pts[3]], fill=col)
    d.ellipse([x - r * 0.3, y - r * 0.3, x + r * 0.3, y + r * 0.3], fill=RED)


for i in range(26):
    x = rnd.uniform(f0 + 60, S - f0 - 60); y = rnd.uniform(f0 + 60, SH - f0 - 60)
    if abs(x - cx) < 0.44 * PXM and abs(y - cy) < 0.28 * PXM:
        continue
    star(x, y, rnd.uniform(12, 20), rnd.choice([IVO, OCH, IND]))
# abrash: hand-dyed horizontal banding
abr = Image.new('L', (S, SH), 128)
ad = ImageDraw.Draw(abr)
y = 0
while y < SH:
    h = rnd.randint(18, 90)
    ad.rectangle([0, y, S, y + h], fill=rnd.randint(112, 146))
    y += h
abr = abr.filter(ImageFilter.GaussianBlur(6))
import numpy as np
a = np.asarray(img).astype(np.float32) * (np.asarray(abr).astype(np.float32)[..., None] / 128.0)
img = Image.fromarray(np.clip(a, 0, 255).astype(np.uint8))
img = img.filter(ImageFilter.GaussianBlur(1.2))          # the knots soften every edge
art_path = os.path.join(ART, 'rug_design.png')
img.save(art_path)


def rug_layers(nb, col, vec):
    # pile = the design x the carpet's luminance; worn patch; edge dirt
    hs = nb.n('ShaderNodeHueSaturation'); hs.inputs['Saturation'].default_value = 0.0
    nb.l(col, hs.inputs['Color'])
    grey = nb.math('MULTIPLY', hs.outputs['Color'], 2.6)
    uvn = nb.n('ShaderNodeUVMap', uv_map='ArtUV')
    t = nb.n('ShaderNodeTexImage'); t.image = load_img(art_path); t.extension = 'EXTEND'
    nb.l(uvn.outputs[0], t.inputs[0])
    c = nb.mix(1.0, t.outputs['Color'], grey, 'MULTIPLY')
    oc = nb.n('ShaderNodeTexCoord').outputs['Object']
    sep = nb.n('ShaderNodeSeparateXYZ'); nb.l(oc, sep.inputs[0])
    ex = nb.math('MULTIPLY', nb.math('SUBTRACT', sep.outputs['X'], 0.05), 1 / 0.42)
    ey = nb.math('MULTIPLY', nb.math('SUBTRACT', sep.outputs['Y'], 0.02), 1 / 0.30)
    r2 = nb.math('ADD', nb.math('MULTIPLY', ex, ex), nb.math('MULTIPLY', ey, ey))
    worn = nb.math('MULTIPLY', nb.math('SUBTRACT', 1.0, r2, clamp=True), nb.ramp(nb.noise(oc, 9.0, 4.0, 0.6), 0.3, 0.8))
    c = nb.mix(nb.math('MULTIPLY', worn, 0.35), c, (0.55, 0.42, 0.32))
    return c


rugm = layered_mat('rug', 'Carpet015', scale=3.0, rough_add=0.05, nstr=1.0, extra_color=rug_layers,
                   wear=dict(color=(0.60, 0.50, 0.36), radius=0.003, amount=0.6, rough=0.95, gain=12, noise=40),
                   grime=dict(color=(0.10, 0.06, 0.04), dist=0.03, amount=0.45, gain=1.4),
                   dust=dict(color=(0.45, 0.40, 0.34), amount=0.08))
cotton = layered_mat('fringe', 'Fabric019', scale=30.0, tint=(0.86, 0.80, 0.68), rough_add=0.1, nstr=0.6,
                     grime=dict(color=(0.45, 0.38, 0.30), dist=0.01, amount=0.5, gain=1.6),
                     dust=dict(color=(0.55, 0.50, 0.42), amount=0.2))

# ----------------------------------------------------------------------------- the rug body
NX, NY = 70, 48


def lift(x, y):
    z = 0.0012 * math.sin(x * 4.1 + 0.5) * math.sin(y * 5.3 + 1.1) + 0.0008 * math.sin(x * 9.0 - y * 7.0)
    dc = math.hypot(x - RL / 2, y + RW / 2)                      # the front-right corner curls up
    z += 0.009 * max(0.0, 1 - dc / 0.26) ** 2.2
    return max(z, 0.0)


bm = bmesh.new()
top = [[bm.verts.new((-RL / 2 + RL * i / NX, -RW / 2 + RW * j / NY, 0)) for i in range(NX + 1)] for j in range(NY + 1)]
for j in range(NY + 1):
    for i in range(NX + 1):
        v = top[j][i]
        v.co.z = RT + lift(v.co.x, v.co.y)
bot = [[bm.verts.new((top[j][i].co.x, top[j][i].co.y, lift(top[j][i].co.x, top[j][i].co.y))) for i in range(NX + 1)]
       for j in range(NY + 1)]
for j in range(NY):
    for i in range(NX):
        bm.faces.new((top[j][i], top[j][i + 1], top[j + 1][i + 1], top[j + 1][i]))
        bm.faces.new((bot[j][i + 1], bot[j][i], bot[j + 1][i], bot[j + 1][i + 1]))
for j in range(NY):
    bm.faces.new((top[j][0], top[j + 1][0], bot[j + 1][0], bot[j][0]))
    bm.faces.new((bot[j][NX], bot[j + 1][NX], top[j + 1][NX], top[j][NX]))
for i in range(NX):
    bm.faces.new((top[0][i + 1], top[0][i], bot[0][i], bot[0][i + 1]))
    bm.faces.new((top[NY][i], top[NY][i + 1], bot[NY][i + 1], bot[NY][i]))
bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
body = obj_from_bm('rugbody', bm, rugm)
bevel_mod(body, 0.0028, segments=3, angle=50)
apply_mods(body)
smooth(body, 55)
uv_planar(body, 'X', 'Y', (-RL / 2, RL / 2, -RW / 2, RW / 2), 'ArtUV')
uv_tex(body, 1.0)
parts = [body]

# ----------------------------------------------------------------------------- knotted fringes
for sx in (-1, 1):
    ngroups = 44
    for g in range(ngroups):
        y0 = -RW / 2 + 0.018 + (RW - 0.036) * g / (ngroups - 1)
        x0 = sx * (RL / 2 + 0.002)
        z0 = lift(x0, y0) + 0.004
        bpy.ops.mesh.primitive_uv_sphere_add(segments=10, ring_count=6, radius=0.0032, location=(x0 + sx * 0.004, y0, z0))
        kn = bpy.context.object; kn.scale = (1.3, 1.0, 0.7)
        select_only(kn); bpy.ops.object.transform_apply(location=False, rotation=False, scale=True)
        kn.data.materials.append(cotton); smooth(kn, 80); uv_tex(kn, 0.05)
        parts.append(kn)
        for s in range(3):
            L = rnd.uniform(0.040, 0.062)
            ang = rnd.uniform(-0.35, 0.35)
            yy = y0 + (s - 1) * 0.0026
            pts = []
            for k in range(7):
                t = k / 6
                bend = ang * t + 0.25 * math.sin(t * 3 + g + s) * t
                pts.append((x0 + sx * (0.006 + L * t), yy + math.sin(bend) * L * t * 0.5,
                            max(0.0011, z0 - 0.003 - 0.004 * t)))
            st = tube_obj('strand', pts, 0.00105, cotton, bevel_res=1, caps=True)
            uv_tex(st, 0.05)
            parts.append(st)

rug = join(parts, 'Rug')
uv_bake(rug, margin=0.002, angle=60)
bake_and_swap(rug, 'rug', size=2048, samples=32, ao_dist=0.05)
clean_uvs(rug)
export_glb([rug], 'corner_rug.glb')
preview([rug], 'rug', height=1.1)
lit_closeup('rug_fringe', (0.95, -0.35, 0.18), (0.66, -0.05, 0.0), lens=50, energy=10)
lit_closeup('rug_center', (0.10, -0.75, 0.55), (0.0, 0.0, 0.0), lens=45, energy=14)
