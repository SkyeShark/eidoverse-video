"""Claude's Corner - the desk chair. A walnut spindle-back chair: a saddle-carved seat (one mass,
dished, rounded edges), four splayed turned legs socketed into the seat, an H-stretcher whose ends
terminate inside the legs, two raked back posts and five spindles socketed into the seat and into
a bent, bowed crest rail, and a folded checked wool throw draped over the rail.
Baked -> glb/corner_chair.glb ('Chair'). Origin floor centre; the sitter faces -Y.
"""
import sys, os, math, random
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import bpy, bmesh
from mathutils import Vector, Matrix
from clib import *
from props_util import *

reset()
SEAT_Z = 0.46
SEAT_T = 0.036
wal = dict(tint=(0.95, 0.80, 0.70), sat=0.95, val=0.95, rough_mul=0.62, rough_add=0.03, nstr=0.8,
           wear=dict(color=(0.55, 0.36, 0.22), radius=0.003, amount=0.9, rough=0.55, gain=16, noise=30),
           grime=dict(color=(0.05, 0.03, 0.02), dist=0.03, amount=0.75, gain=1.9),
           dust=dict(color=(0.50, 0.45, 0.38), amount=0.22))
wood = layered_mat('chair_walnut', 'Wood066', scale=1.1, **wal)


def throw_layer(nb, col, vec):
    # soft wool: fuzz noise + slight fade on the fold crests
    oc = nb.n('ShaderNodeTexCoord').outputs['Object']
    fz = nb.ramp(nb.noise(oc, 180.0, 3.0, 0.6), 0.4, 0.75)
    return nb.mix(nb.math('MULTIPLY', fz, 0.25), col, (0.75, 0.62, 0.48))


throwm = layered_mat('throw', 'Fabric083', scale=0.62, tint=(0.80, 0.36, 0.15), sat=1.0, rough_add=0.2, nstr=1.0,
                     extra_color=throw_layer,
                     grime=dict(color=(0.15, 0.07, 0.03), dist=0.02, amount=0.55, gain=1.6))
parts = []


def orient(o, p0, p1):
    """object built along +Z from 0 -> place so +Z runs p0->p1."""
    p0, p1 = Vector(p0), Vector(p1)
    d = (p1 - p0).normalized()
    q = Vector((0, 0, 1)).rotation_difference(d)
    o.data.transform(Matrix.Translation(p0) @ q.to_matrix().to_4x4())


def turned(name, L, prof_frac, segs=32):
    prof = [(r, f * L) for r, f in prof_frac]
    o = lathe_obj(name, prof, segs, wood)
    uv_tex_axis(o, 'Z', 1.0)          # grain along the turning
    return o


# ---------------------------------------------------------------- seat: one mass, saddle-carved
NX, NY = 22, 20
bm = bmesh.new()
top, bot = [], []
for j in range(NY + 1):
    rt, rb = [], []
    y = -0.20 + 0.40 * j / NY
    half = 0.21 - 0.022 * (j / NY) ** 1.3             # narrower toward the back
    for i in range(NX + 1):
        x = -half + 2 * half * i / NX
        dish = 0.0
        for sx in (-1, 1):
            dish += 0.0075 * math.exp(-(((x - sx * 0.075) / 0.085) ** 2 + ((y - 0.035) / 0.11) ** 2))
        pommel = 0.003 * math.exp(-((x / 0.03) ** 2 + ((y + 0.12) / 0.06) ** 2))
        rt.append(bm.verts.new((x, y, SEAT_Z - dish + pommel)))
        rb.append(bm.verts.new((x, y, SEAT_Z - SEAT_T)))
    top.append(rt); bot.append(rb)
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
seat = obj_from_bm('seat', bm, wood)
bv = bevel_mod(seat, 0.009, segments=4, angle=55)
apply_mods(seat)
smooth(seat, 50)
uv_tex_axis(seat, 'X', 1.0)
parts.append(seat)

# ---------------------------------------------------------------- legs (splayed, socketed 18 mm into the seat)
LEGP = [(0.0000, 0.000), (0.0160, 0.000), (0.0168, 0.010), (0.0172, 0.180), (0.0205, 0.215), (0.0212, 0.235),
        (0.0190, 0.255), (0.0186, 0.300), (0.0198, 0.420), (0.0208, 0.520), (0.0200, 0.640), (0.0214, 0.700),
        (0.0216, 0.735), (0.0190, 0.760), (0.0160, 0.800), (0.0150, 0.960), (0.0120, 1.000), (0.0000, 1.000)]
legs = {}
for (sx, sy, tx, ty, bx, by) in ((-1, -1, 0.150, 0.130, 0.185, 0.178), (1, -1, 0.150, 0.130, 0.185, 0.178),
                                 (-1, 1, 0.140, 0.125, 0.172, 0.188), (1, 1, 0.140, 0.125, 0.172, 0.188)):
    p_top = Vector((sx * tx, sy * ty, SEAT_Z - SEAT_T + 0.018))
    p_bot = Vector((sx * bx, sy * by, 0.0))
    L = (p_top - p_bot).length
    lg = turned('leg', L, LEGP)
    orient(lg, p_bot, p_top)
    legs[(sx, sy)] = (p_bot, p_top)
    parts.append(lg)


def axis_at(key, h):
    b, t = legs[key]
    return b + (t - b) * (h / t.z)


# ---------------------------------------------------------------- H-stretcher (ends end on the member axes)
SH = 0.150
STRP = [(0.0000, 0.00), (0.0090, 0.00), (0.0092, 0.05), (0.0112, 0.12), (0.0122, 0.30), (0.0126, 0.50),
        (0.0122, 0.70), (0.0112, 0.88), (0.0092, 0.95), (0.0090, 1.00), (0.0000, 1.00)]
mids = []
for sx in (-1, 1):
    a, b = axis_at((sx, -1), SH), axis_at((sx, 1), SH + 0.012)
    st = turned('stretcher', (b - a).length, STRP, 24)
    orient(st, a, b)
    parts.append(st)
    mids.append((a + b) / 2)
mst = turned('midstretcher', (mids[1] - mids[0]).length, [(r * 0.9, f) for r, f in STRP], 24)
orient(mst, mids[0], mids[1])
parts.append(mst)


# ---------------------------------------------------------------- crest rail (bent, bowed, raked)
RAKE = math.radians(13)
def rail_c(x):
    return Vector((x, 0.232 + 0.034 * (1 - (x / 0.2) ** 2), 0.862 + 0.010 * (1 - (x / 0.2) ** 2)))


RH, RT = 0.056, 0.023
sec = []
for k in range(28):
    a = k / 28 * math.tau
    cx, cy = math.cos(a), math.sin(a)
    sec.append((math.copysign(abs(cx) ** 0.45, cx) * RT / 2, math.copysign(abs(cy) ** 0.35, cy) * RH / 2))
bm = bmesh.new()
rings = []
NXR = 30
for i in range(NXR + 1):
    x = -0.205 + 0.41 * i / NXR
    c = rail_c(x)
    dx = 0.001
    tvec = (rail_c(x + dx) - rail_c(x - dx)).normalized()
    upv = Vector((0, math.sin(RAKE), math.cos(RAKE)))           # raked 'up' of the rail section
    nv = tvec.cross(upv).normalized()
    upv = nv.cross(tvec).normalized()
    rings.append([bm.verts.new(c + nv * u + upv * v) for u, v in sec])
for i in range(NXR):
    for k in range(len(sec)):
        bm.faces.new((rings[i][k], rings[i][(k + 1) % len(sec)], rings[i + 1][(k + 1) % len(sec)], rings[i + 1][k]))
bm.faces.new(rings[0][::-1]); bm.faces.new(rings[-1])
bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
rail = obj_from_bm('crestrail', bm, wood)
smooth(rail, 50)
uv_tex_axis(rail, 'X', 1.0)
parts.append(rail)

# ---------------------------------------------------------------- back posts + spindles (seat -> rail axis)
POSTP = [(0.0000, 0.00), (0.0120, 0.00), (0.0150, 0.06), (0.0162, 0.10), (0.0150, 0.16), (0.0140, 0.40), (0.0150, 0.62),
         (0.0142, 0.80), (0.0120, 0.96), (0.0110, 1.00), (0.0000, 1.00)]
SPP = [(0.0000, 0.00), (0.0060, 0.00), (0.0068, 0.10), (0.0086, 0.40), (0.0088, 0.50), (0.0080, 0.70), (0.0066, 0.92),
       (0.0060, 1.00), (0.0000, 1.00)]
for x0, prof, nm in ((-0.160, POSTP, 'post'), (0.160, POSTP, 'post'), (-0.090, SPP, 'spindle'), (-0.045, SPP, 'spindle'),
                     (0.0, SPP, 'spindle'), (0.045, SPP, 'spindle'), (0.090, SPP, 'spindle')):
    p0 = Vector((x0, 0.150, SEAT_Z - 0.020))
    xt = x0 * 1.12
    p1 = rail_c(xt)
    o = turned(nm, (p1 - p0).length, prof, 24)
    orient(o, p0, p1)
    parts.append(o)

chair = join(parts, 'ChairWood')

# ---------------------------------------------------------------- the throw, folded over the rail
W_T, TH = 0.34, 0.013
c0 = rail_c(0.0)
upv = Vector((0, math.sin(RAKE), math.cos(RAKE)))
fwd = Vector((0, -math.cos(RAKE), math.sin(RAKE)))          # toward the sitter, perpendicular to the raked rail
prof2d = [(-0.030, -0.135), (-0.031, -0.090), (-0.029, -0.040), (-0.024, 0.005), (-0.015, 0.030), (0.000, 0.040),
          (0.016, 0.031), (0.026, 0.006), (0.032, -0.050), (0.037, -0.120), (0.043, -0.190), (0.050, -0.245)]
# prof2d: (along fwd-negative -> back, along upv), front drop first
path = bezier_points([(0, p[0], p[1]) for p in prof2d], 6)
rnd = random.Random(3)
NXT = 26
bm = bmesh.new()
uvl = bm.loops.layers.uv.new('TexUV')
grid = []
arc = [0.0]
for i in range(1, len(path)):
    arc.append(arc[-1] + (path[i] - path[i - 1]).length)
for i in range(NXT + 1):
    x = -W_T / 2 + W_T * i / NXT
    rc = rail_c(x * 1.0)
    row = []
    for j, p in enumerate(path):
        hang = max(0.0, -p.z) / 0.245
        fold = (0.0060 * math.sin(x * 24 + 0.8) + 0.0025 * math.sin(x * 61 + j * 0.3)) * (0.25 + 0.75 * hang)
        fold += 0.006 * hang ** 2 * math.sin(x * 17 + 1.3)          # the hem flares a little
        droop = 0.010 * (abs(x) / (W_T / 2)) ** 2 * max(0.0, -p.z) / 0.245
        pos = rc - fwd * (p.y) + upv * (p.z - droop)
        # fold ripples along the normal of the drape (approx: fwd for the hanging parts)
        pos += fwd * fold * (1 if p.y < 0 else -1)
        row.append(bm.verts.new(pos))
    grid.append(row)
for i in range(NXT):
    for j in range(len(path) - 1):
        f = bm.faces.new((grid[i][j], grid[i + 1][j], grid[i + 1][j + 1], grid[i][j + 1]))
        for lp, (a, b) in zip(f.loops, ((i, j), (i + 1, j), (i + 1, j + 1), (i, j + 1))):
            lp[uvl].uv = ((-W_T / 2 + W_T * a / NXT) / 0.5, arc[b] / 0.5)
bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
throw = obj_from_bm('throw', bm, throwm)
# make the outward side face away from the rail
cen = c0
flip = 0
for p in throw.data.polygons:
    if p.normal.dot(p.center - cen) < 0:
        flip += 1
if flip > len(throw.data.polygons) / 2:
    for p in throw.data.polygons:
        p.flip()
sol = throw.modifiers.new('sol', 'SOLIDIFY'); sol.thickness = TH; sol.offset = -1.0
bevel_mod(throw, 0.004, segments=3, angle=40)
apply_mods(throw)
smooth(throw, 60)
chair_all = join([chair, throw], 'Chair')
uv_bake(chair_all, margin=0.003)
bake_and_swap(chair_all, 'chair', size=2048, samples=40, ao_dist=0.06)
clean_uvs(chair_all)
export_glb([chair_all], 'corner_chair.glb')
preview([chair_all], 'chair', height=0.45)
lit_closeup('chair_seat', (0.35, -0.55, 0.75), (0.0, -0.02, 0.45), lens=50, energy=12)
lit_closeup('chair_throw', (-0.35, 0.75, 0.95), (0.0, 0.25, 0.80), lens=50, energy=12)
