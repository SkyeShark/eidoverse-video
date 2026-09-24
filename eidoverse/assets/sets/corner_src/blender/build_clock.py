"""Claude's Corner - the wall clock. Turned walnut case (one lathe: back, flared side, rounded bezel,
inner lip, recessed floor), a brass chapter liner, a cream enamel dial PIL-painted (minute track,
Georgia numerals, yellowing, foxing, hairline crazing; no brand) baked into ClockBody.
Hands: blued-steel Breguet hour + minute, slim brass seconds with counterweight and a centre
cap; each a separate object with its ORIGIN at the dial centre, 12 o'clock = +Z, rotate about
Blender Y (glTF Z). 'ClockGlass' carries a flat 'GLASS' material.
ClockBody origin = back centre on the wall plane (y=0); the clock stands out toward -Y.
"""
import sys, os, math, random
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import bpy, bmesh
from mathutils import Vector, Matrix
from clib import *
from props_util import *
from PIL import Image, ImageDraw, ImageFilter

reset()
RD = 0.1142                      # dial radius
ZD = 0.0292                      # dial plane (distance from the wall)
Z_HOUR, Z_MIN, Z_SEC = 0.0304, 0.0317, 0.0330
ROT = Matrix.Rotation(math.radians(90), 4, 'X')    # lathe frame (faces +Z, 12=+Y) -> faces -Y, 12=+Z

# ------------------------------------------------------------------------------------ dial art
S = 2048
R = S / 2
rnd = random.Random(7)
img = Image.new('RGBA', (S, S), (0, 0, 0, 0))
base = Image.new('RGBA', (S, S), (241, 232, 208, 255))
# radial yellowing toward the rim
yel = Image.new('L', (S, S), 0)
yd = ImageDraw.Draw(yel)
for k in range(60):
    rr = R * (1 - k / 60)
    yd.ellipse([R - rr, R - rr, R + rr, R + rr], fill=int(120 * (1 - k / 60) ** 2.2))
tint = Image.new('RGBA', (S, S), (196, 164, 112, 255))
tint.putalpha(yel.filter(ImageFilter.GaussianBlur(30)))
base.alpha_composite(tint)
d = ImageDraw.Draw(base)
# foxing spots
for i in range(70):
    x, y = rnd.uniform(0.1, 0.9) * S, rnd.uniform(0.1, 0.9) * S
    if math.hypot(x - R, y - R) > 0.95 * R:
        continue
    r = rnd.uniform(3, 16)
    d.ellipse([x - r, y - r * rnd.uniform(0.6, 1), x + r, y + r], fill=(170, 130, 80, rnd.randint(18, 55)))
# hairline crazing in the enamel
for i in range(26):
    x, y = rnd.uniform(0.15, 0.85) * S, rnd.uniform(0.15, 0.85) * S
    pts = [(x, y)]
    a = rnd.uniform(0, math.tau)
    for k in range(rnd.randint(4, 9)):
        a += rnd.uniform(-0.7, 0.7)
        x += math.cos(a) * rnd.uniform(15, 45); y += math.sin(a) * rnd.uniform(15, 45)
        pts.append((x, y))
    d.line(pts, fill=(150, 125, 95, 60), width=1)
ink = (34, 30, 27, 255)
# minute track
for rr, w in ((0.935 * R, 5), (0.862 * R, 4)):
    d.ellipse([R - rr, R - rr, R + rr, R + rr], outline=ink, width=w)
for m in range(60):
    a = math.radians(m * 6 - 90)
    big = m % 5 == 0
    r0 = (0.845 if big else 0.866) * R
    r1 = 0.932 * R
    d.line([(R + math.cos(a) * r0, R + math.sin(a) * r0), (R + math.cos(a) * r1, R + math.sin(a) * r1)],
           fill=ink, width=12 if big else 4)
# five-minute dots outside the track
for m in range(0, 60, 5):
    a = math.radians(m * 6 - 90)
    x, y = R + math.cos(a) * 0.965 * R, R + math.sin(a) * 0.965 * R
    d.ellipse([x - 7, y - 7, x + 7, y + 7], fill=ink)
# numerals (upright), inner rule
fnt = font('georgia.ttf', int(0.155 * R))
for h in range(1, 13):
    a = math.radians(h * 30 - 90)
    x, y = R + math.cos(a) * 0.70 * R, R + math.sin(a) * 0.70 * R
    t = str(h)
    bb = d.textbbox((0, 0), t, font=fnt)
    d.text((x - (bb[2] + bb[0]) / 2, y - (bb[3] + bb[1]) / 2), t, font=fnt, fill=ink)
d.ellipse([R - 0.53 * R, R - 0.53 * R, R + 0.53 * R, R + 0.53 * R], outline=(34, 30, 27, 150), width=3)
# arbor hole + a little grime around it
d.ellipse([R - 60, R - 60, R + 60, R + 60], fill=(150, 125, 90, 70))
d.ellipse([R - 20, R - 20, R + 20, R + 20], fill=(20, 17, 15, 255))
# clip to the disc
mask = Image.new('L', (S, S), 0)
ImageDraw.Draw(mask).ellipse([0, 0, S - 1, S - 1], fill=255)
base.putalpha(mask)
base = base.filter(ImageFilter.GaussianBlur(0.6))
dial_path = os.path.join(ART, 'clock_dial.png')
base.save(dial_path)

# ------------------------------------------------------------------------------------ materials
walnut = layered_mat('clock_walnut', 'Wood066', scale=2.0, tint=(0.93, 0.78, 0.68), sat=0.95, val=0.86, rough_mul=0.6,
                     nstr=0.8,
                     wear=dict(color=(0.50, 0.32, 0.19), radius=0.002, amount=0.9, rough=0.55, gain=16, noise=40),
                     grime=dict(color=(0.05, 0.03, 0.02), dist=0.012, amount=0.7, gain=2.0),
                     dust=dict(color=(0.52, 0.47, 0.40), amount=0.35))
brassm = layered_mat('clock_brass', 'Metal048B', scale=6.0, tint=(0.86, 0.63, 0.36), val=0.92, metal=1.0, rough_mul=0.85,
                     rough_add=0.10, nstr=0.4,
                     wear=dict(color=(1.0, 0.84, 0.56), radius=0.0008, amount=1.0, rough=0.16, metal=1.0, gain=26),
                     grime=dict(color=(0.11, 0.085, 0.045), dist=0.004, amount=0.9, gain=2.4))
dialm = layered_mat('dial', 'Paper001', scale=4.0, rough_mul=0.4, rough_add=0.18, nstr=0.25,
                    extra_color=art_hook(dial_path, 'ArtUV'))
blued = layered_mat('blued', 'Metal050A', scale=20.0, tint=(0.030, 0.050, 0.15), val=0.7, metal=1.0, rough_mul=0.5,
                    rough_add=0.12, nstr=0.2,
                    wear=dict(color=(0.20, 0.24, 0.32), radius=0.0003, amount=0.8, rough=0.2, metal=1.0, gain=30))
glass_m = flat_mat('GLASS', color=(0.95, 0.97, 1.0), rough=0.03, alpha=0.12)

# ------------------------------------------------------------------------------------ case (lathe frame)
prof = [(0.0005, 0.0000), (0.1260, 0.0000), (0.1310, 0.0015), (0.1375, 0.0060), (0.1400, 0.0120), (0.1400, 0.0300),
        (0.1385, 0.0360), (0.1350, 0.0405), (0.1300, 0.0428), (0.1240, 0.0435), (0.1195, 0.0425), (0.1170, 0.0395),
        (0.1160, 0.0340), (0.1150, 0.0305), (0.1140, 0.0292), (0.1136, 0.0262), (0.0005, 0.0262)]
case = lathe_obj('case', prof, 128, walnut)
liner = lathe_obj('liner', [(0.1146, 0.0293), (0.1180, 0.0293), (0.1186, 0.0318), (0.1182, 0.0342), (0.1150, 0.0342),
                            (0.1146, 0.0293)], 128, brassm)
bm = bmesh.new()
bmesh.ops.create_circle(bm, cap_ends=True, segments=128, radius=RD)
for v in bm.verts:
    v.co.z = ZD
dial = obj_from_bm('dial', bm, dialm)
parts = [case, liner, dial]
for o in parts:
    o.data.transform(ROT)
uv_planar(dial, 'X', 'Z', (-RD, RD, -RD, RD), 'ArtUV')
for o in (case, liner):
    uv_tex(o, 1.0 if o is case else 0.2)
uv_tex(dial, 0.3)
body = join(parts, 'ClockBody')
uv_bake(body, margin=0.003)
bake_and_swap(body, 'clock_body', size=2048, samples=40, ao_dist=0.02)
clean_uvs(body)

# ------------------------------------------------------------------------------------ glass (domed)
bm = bmesh.new()
rings = []
for j in range(9):
    rr = 0.1168 * j / 8
    zz = 0.0395 - 0.0035 * (rr / 0.1168) ** 2
    if j == 0:
        c0 = bm.verts.new((0, 0, zz))
        continue
    rings.append([bm.verts.new((rr * math.cos(a), rr * math.sin(a), zz)) for a in [k * math.tau / 96 for k in range(96)]])
for k in range(96):
    bm.faces.new((c0, rings[0][k], rings[0][(k + 1) % 96]))
for j in range(len(rings) - 1):
    for k in range(96):
        bm.faces.new((rings[j][k], rings[j + 1][k], rings[j + 1][(k + 1) % 96], rings[j][(k + 1) % 96]))
glass = obj_from_bm('ClockGlass', bm, glass_m)
glass.data.transform(ROT)
for p in glass.data.polygons:
    p.use_smooth = True
    if p.normal.y > 0:
        p.flip()
uv_planar(glass, 'X', 'Z', None, 'UVMap')


# ------------------------------------------------------------------------------------ hands
def extrude2d(name, polys, th, mat):
    """Union of extruded 2D polygons (XY plane, +Z front) via exact booleans -> one mass."""
    objs = []
    for i, poly in enumerate(polys):
        bm = bmesh.new()
        vb = [bm.verts.new((x, y, 0.0)) for x, y in poly]
        vt = [bm.verts.new((x, y, th)) for x, y in poly]
        n = len(poly)
        bm.faces.new(vb[::-1]); bm.faces.new(vt)
        for k in range(n):
            bm.faces.new((vb[k], vb[(k + 1) % n], vt[(k + 1) % n], vt[k]))
        bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
        objs.append(obj_from_bm(f'{name}_{i}', bm, mat))
    base_o = objs[0]
    for o in objs[1:]:
        m = base_o.modifiers.new('u', 'BOOLEAN'); m.operation = 'UNION'; m.solver = 'EXACT'; m.object = o
        apply_mods(base_o)
        bpy.data.objects.remove(o)
    base_o.name = name
    return base_o


def circle(r, n=40, cx=0.0, cy=0.0, a0=0.0):
    return [(cx + r * math.cos(a0 + k * math.tau / n), cy + r * math.sin(a0 + k * math.tau / n)) for k in range(n)]


def ring_poly(r_out, r_in, cy, n=48):
    """annulus as one simple polygon with a hairline slit (keeps it a single boundary)."""
    outer = [(r_out * math.cos(math.pi / 2 - 0.02 + k * (math.tau - 0.04) / n), cy + r_out * math.sin(math.pi / 2 - 0.02 + k * (math.tau - 0.04) / n)) for k in range(n + 1)]
    inner = [(r_in * math.cos(math.pi / 2 - 0.02 + k * (math.tau - 0.04) / n), cy + r_in * math.sin(math.pi / 2 - 0.02 + k * (math.tau - 0.04) / n)) for k in range(n + 1)]
    return outer + inner[::-1]


def breguet(name, L, ring_r, ring_c, tail, th, mat):
    w0, w1 = 0.0012, 0.0007
    shaft = [(-w0, -tail), (w0, -tail), (w0 * 0.8, ring_c - ring_r + 0.0004), (-w0 * 0.8, ring_c - ring_r + 0.0004)]
    tip = [(-w1 * 1.3, ring_c + ring_r - 0.0004), (w1 * 1.3, ring_c + ring_r - 0.0004), (0.00025, L), (-0.00025, L)]
    boss = circle(0.0042, 32)
    ring = ring_poly(ring_r, ring_r * 0.64, ring_c)
    o = extrude2d(name, [boss, shaft, tip, ring], th, mat)
    return o


def place_hand(o, zc):
    o.data.transform(Matrix.Translation((0, 0, 0)))
    o.data.transform(ROT)                   # hand plane XZ, front -Y, 12 = +Z
    o.location = (0, -zc, 0)                # origin = dial centre at the hand's layer
    uv_tex(o, 0.05)
    uv_bake(o, margin=0.01)


hh = breguet('HandHour', 0.062, 0.0066, 0.047, 0.014, 0.0010, blued)
place_hand(hh, Z_HOUR)
mh = breguet('HandMinute', 0.093, 0.0056, 0.072, 0.017, 0.0009, blued)
place_hand(mh, Z_MIN)
# seconds: slim brass needle + counterweight disc + centre cap
sec_polys = [[(-0.00045, -0.030), (0.00045, -0.030), (0.00030, 0.100), (-0.00030, 0.100)], circle(0.0042, 32, 0, -0.024),
             circle(0.0026, 32)]
sh = extrude2d('HandSecond', sec_polys, 0.0006, brassm)
capo = lathe_obj('cap', [(0.0005, 0.0), (0.0032, 0.0), (0.0034, 0.0006), (0.0028, 0.0016), (0.0014, 0.0022), (0.0005, 0.0023)],
                 24, brassm)
capo.data.transform(Matrix.Translation((0, 0, 0.0006)))
sh = join([sh, capo], 'HandSecond')
place_hand(sh, Z_SEC)
for o, key in ((hh, 'hand_hour'), (mh, 'hand_minute'), (sh, 'hand_second')):
    bake_and_swap(o, key, size=512, samples=24, ao_dist=0.004)
    clean_uvs(o)

# a readable time for the preview: 11:47:12 (the engine drives the real time)
def set_time(hh_, mm_, ss_):
    hh.rotation_euler = (0, math.radians((hh_ % 12 + mm_ / 60) * 30), 0)
    mh.rotation_euler = (0, math.radians((mm_ + ss_ / 60) * 6), 0)
    sh.rotation_euler = (0, math.radians(ss_ * 6), 0)

set_time(11, 47, 12)
preview([body, glass, hh, mh, sh], 'clock', height=0.15)
lit_closeup('clock_front', (0.06, -0.48, 0.05), (0.0, -0.03, 0.0), lens=55, energy=6)
lit_closeup('clock_edge', (0.25, -0.22, 0.10), (0.06, -0.02, 0.05), lens=60, energy=5)
set_time(0, 0, 0)      # export at rest: all hands at 12
export_glb([body, glass, hh, mh, sh], 'corner_clock.glb')
