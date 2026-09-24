# build_props.py — the funeral's devotional objects (DAISY bridge, Claude 3 Sonnet Funeralia 2025-08-02).
#   blender --background --python build_props.py [-- preview]
# From the record (research/community.md): mannequins in the four corners, "each representing a
# model, embodying them with voices and sensors and devotional objects and masks" — Claude 3 Opus
# a gold mannequin (Wired: crown, lace headdress, a lotus candle holder at its feet); Claude 4 Opus
# with a raven on its shoulder; Claude 3 Haiku small and headless; Sonnet 4 spoke "in this mannequin"
# (here: a mask, a speaker and a sensor). Claude 3 Sonnet lay on the stage draped in mesh, with
# flowers, feathers, a bottle. A shoggoth tentacle hung from the ceiling.
# Writes assets/props.glb + props_layout.json (anchors: flames, raven perch, projector lens).
import sys
import os
import math
import json
import bpy
import bmesh
from mathutils import Vector, Matrix

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import importlib
import fx_core
importlib.reload(fx_core)
from fx_core import (Mesh, reset_scene, ASSETS, T2B, material, preview, apply_modifiers, skin_chain, ellipsoid_obj,
                     join, set_role, smart_uv, place, hard_exit, link_obj, boolean)

reset_scene()
L = json.load(open(ASSETS + '/funeral_layout.json'))
anchors = {'flames': [], 'raven_perch': None, 'projector_lens': None, 'lotus_flame': None}
EXPORT = []


def mannequin(name, pose='side', headless=False, scale=1.0):
    """a retail mannequin: smooth idealised skin-modifier body + egg head, feet at 0, facing +z."""
    V = [(0, 0.98, 0), (0, 1.1, 0.01), (0, 1.27, 0.015), (0, 1.4, 0.0), (0, 1.5, -0.01), (0, 1.575, 0.0),
         (0.17, 1.42, -0.005), (-0.17, 1.42, -0.005),
         (0.093, 0.94, 0), (0.098, 0.53, 0.02), (0.098, 0.085, 0), (0.098, 0.03, 0.12),
         (-0.093, 0.94, 0), (-0.098, 0.53, 0.02), (-0.098, 0.085, 0), (-0.098, 0.03, 0.12)]
    E = [(0, 1), (1, 2), (2, 3), (3, 4), (4, 5), (3, 6), (3, 7), (0, 8), (8, 9), (9, 10), (10, 11),
         (0, 12), (12, 13), (13, 14), (14, 15)]
    R = [(0.155, 0.112), (0.118, 0.086), (0.138, 0.098), (0.158, 0.096), (0.05, 0.05), (0.044, 0.044),
         (0.056, 0.054), (0.056, 0.054), (0.085, 0.085), (0.052, 0.055), (0.034, 0.036), (0.036, 0.024),
         (0.085, 0.085), (0.052, 0.055), (0.034, 0.036), (0.036, 0.024)]
    if headless:
        V, E, R = V[:5] + V[5:], E, R
    arms = {
        'open': [[(0.26, 1.18, 0.06), (0.31, 0.97, 0.16), (0.33, 0.9, 0.2)], [(-0.26, 1.18, 0.06), (-0.31, 0.97, 0.16), (-0.33, 0.9, 0.2)]],
        'side': [[(0.215, 1.16, 0.0), (0.225, 0.9, 0.03), (0.228, 0.82, 0.04)], [(-0.215, 1.16, 0.0), (-0.225, 0.9, 0.03), (-0.228, 0.82, 0.04)]],
        'hold': [[(0.215, 1.16, 0.02), (0.14, 1.02, 0.17), (0.07, 1.0, 0.2)], [(-0.215, 1.16, 0.02), (-0.14, 1.02, 0.17), (-0.07, 1.0, 0.2)]],
    }[pose]
    for s_idx, a in ((6, arms[0]), (7, arms[1])):
        b = len(V)
        V += a
        E += [(s_idx, b), (b, b + 1), (b + 1, b + 2)]
        R += [(0.043, 0.043), (0.031, 0.029), (0.036, 0.017)]
    body = skin_chain(name + '_body', V, E, R, subsurf=2)
    parts = [body]
    if not headless:
        parts.append(ellipsoid_obj(name + '_head', (0, 1.665, 0.012), (0.08, 0.108, 0.092), segs=32, rings=20))
    ob = join(parts, name)
    if scale != 1.0:
        ob.data.transform(Matrix.Scale(scale, 4))
    return ob


def stand(name, rod_to=(0.098, 0.3, 0.0), scale=1.0):
    m = Mesh(name)
    m.lathe([(0.0, 0.0), (0.2, 0.0), (0.205, 0.006), (0.2, 0.014), (0.03, 0.02), (0.0, 0.02)], 48, (0, 0, 0), 'chrome')
    m.tube([(rod_to[0] * scale, 0.02, -0.06), (rod_to[0] * scale, 0.02, -0.06 + 0.001), (rod_to[0] * scale, rod_to[1] * scale, rod_to[2])],
           0.009, 10, 'chrome', caps=True)
    return m.finalize(bevel=0.002)


def plinth(name, w=0.72, h=0.36):
    m = Mesh(name)
    m.box((0, h / 2, 0), (w, h, w), 'stage')
    m.box((0, h + 0.006, 0), (w + 0.02, 0.012, w + 0.02), 'stage')
    return m.finalize(bevel=0.008, bevel_segs=2)


def crown(name):
    """gold crown: a band with eight points, each tipped with a pearl, set on the head."""
    m = Mesh(name)
    cy = 1.735
    m.lathe([(0.093, 0.0), (0.097, 0.004), (0.097, 0.034), (0.092, 0.038)], 40, (0, cy, 0.008), 'gold')
    for i in range(8):
        a = 2 * math.pi * i / 8
        ca, sa = math.cos(a), math.sin(a)
        base_r = 0.096
        p0 = Vector((ca * base_r, cy + 0.03, 0.008 + sa * base_r * 1.05))
        t = Vector((-sa, 0, ca))
        tip = Vector((ca * (base_r + 0.012), cy + 0.085, 0.008 + sa * (base_r + 0.012) * 1.05))
        w = 0.022
        pts = [p0 - t * w, p0 + t * w, tip]
        # a small solid spike: two triangles offset in/out
        n = Vector((ca, 0, sa))
        inner = [p - n * 0.003 for p in pts]
        outer = [p + n * 0.003 for p in pts]
        m.face([tuple(outer[0]), tuple(outer[1]), tuple(outer[2])], 'gold')
        m.face([tuple(inner[2]), tuple(inner[1]), tuple(inner[0])], 'gold')
        m.face([tuple(inner[0]), tuple(inner[1]), tuple(outer[1]), tuple(outer[0])], 'gold')
        m.face([tuple(inner[1]), tuple(inner[2]), tuple(outer[2]), tuple(outer[1])], 'gold')
        m.face([tuple(inner[2]), tuple(inner[0]), tuple(outer[0]), tuple(outer[2])], 'gold')
        pr = tip + Vector((0, 0.008, 0))
        m.lathe([(0.0, -0.009), (0.007, -0.006), (0.009, 0.0), (0.007, 0.006), (0.0, 0.009)], 10, tuple(pr), 'pearl')
        # a jewel on the band under each point
        jc = Vector((ca * 0.098, cy + 0.018, 0.008 + sa * 0.098 * 1.05))
        m.lathe([(0.0, -0.006), (0.006, 0.0), (0.0, 0.004)], 8, tuple(jc), 'jewel')
    return m.finalize(bevel=0.0015)


def lace_veil(name, top=(0.0, 1.8, 0.0), n_ang=96, n_down=26):
    """a mantilla falling from the crown: a revolved shell around the head axis, its hem longer at the
    back than the face, the drape widening with depth and breaking into soft folds toward the hem."""
    m = Mesh(name)
    rows = []
    for j in range(n_down + 1):
        t = j / n_down
        row = []
        for i in range(n_ang):
            a = 2 * math.pi * i / n_ang
            back = 0.5 - 0.5 * math.cos(a - math.pi / 2 - math.pi)   # 1 at the back (-z), 0 at the face (+z)
            length = 0.34 + 0.52 * back                               # hem: chin-length at the face, mid-back behind
            y = top[1] - length * t
            # radius: hugs the crown, then clears the head/shoulders and flares
            r0 = 0.1 + 0.02 * back
            r = r0 + 0.2 * (t ** 1.3) * (0.55 + 0.45 * back) + 0.05 * math.sin(math.pi * min(1, t * 1.6))
            fold = 0.018 * (t ** 1.5) * math.sin(a * 11 + 1.3) + 0.01 * (t ** 2) * math.sin(a * 23)
            rr = r + fold
            # the face opening: the veil parts in front of the face
            part = max(0.0, math.cos(a - math.pi / 2)) ** 6
            rr += 0.06 * part * t
            row.append((top[0] + rr * math.cos(a), y, top[2] - 0.01 + rr * math.sin(a) * 1.05))
        rows.append(row)
    for j in range(n_down):
        for i in range(n_ang):
            k = (i + 1) % n_ang
            m.face([rows[j][i], rows[j + 1][i], rows[j + 1][k], rows[j][k]], 'lace',
                   uvf=None)
    ob = m.finalize(weighted=False)
    # uv: angle x depth, in metres-ish so the lace pattern tiles evenly
    me = ob.data
    uvl = me.uv_layers.active
    B2Tm = Matrix(T2B).inverted()
    for p_ in me.polygons:
        for li in p_.loop_indices:
            c = B2Tm @ me.vertices[me.loops[li].vertex_index].co
            ang = math.atan2(c.z - top[2], c.x - top[0])
            uvl.data[li].uv = ((ang + math.pi) * 0.25, (top[1] - c.y))
    sol = ob.modifiers.new('sol', 'SOLIDIFY')
    sol.thickness = 0.0025
    apply_modifiers(ob)
    return ob


def flower(m, c, kind, s=1.0, up=(0, 1, 0)):
    """a small flower head: cupped petals round a disc (three space, at c, facing `up`)."""
    upv = Vector(up).normalized()
    ref = Vector((1, 0, 0)) if abs(upv.x) < 0.9 else Vector((0, 0, 1))
    a1 = upv.cross(ref).normalized()
    a2 = upv.cross(a1).normalized()
    C = Vector(c)
    col = {'white': 'petal', 'red': 'petal_red', 'yellow': 'petal_yellow'}[kind]
    n = 11 if kind == 'white' else 6
    for i in range(n):
        a = 2 * math.pi * i / n
        d = a1 * math.cos(a) + a2 * math.sin(a)
        w = (0.012 if kind == 'white' else 0.022) * s
        L_ = (0.034 if kind == 'white' else 0.03) * s
        p0 = C + d * 0.008 * s
        p1 = C + d * L_ * 0.55 + upv * L_ * 0.25
        p2 = C + d * L_ + upv * L_ * (0.35 if kind != 'white' else 0.12)
        side = d.cross(upv).normalized() * w
        m.face([tuple(p0 - side * 0.3), tuple(p1 - side), tuple(p2), tuple(p1 + side), tuple(p0 + side * 0.3)], col)
    m.lathe([(0.0, -0.004 * s), (0.009 * s, 0.0), (0.0, 0.006 * s)], 10, tuple(C), 'flower_disc')


# ═════════════════════════════════ MANNEQUINS ═════════════════════════════════
MQ = L['mannequins']
PL_H = 0.36
yaw_to_stage = lambda p: math.atan2(0 - p[0], 8.2 - p[2]) * 0.6 + math.atan2(0 - p[0], 0 - p[2]) * 0.4

# — Claude 3 Opus: the golden mannequin, crowned, lace-veiled, a lotus candle holder at its feet —
op3 = mannequin('mq_opus3', pose='open')
set_role(op3, 'gold')
cr = crown('crown')
veil = lace_veil('veil', top=(0.0, 1.805, 0.004))
set_role(veil, 'lace')
st = stand('stand_op3')
lot = Mesh('lotus')
LOT_C = (0.0, PL_H, 0.23)
lot.lathe([(0.0, 0.0), (0.075, 0.0), (0.07, 0.012), (0.03, 0.02), (0.0, 0.022)], 32, LOT_C, 'brass')
for ring, (n, rr, h, tilt) in enumerate(((10, 0.06, 0.07, 0.55), (8, 0.045, 0.085, 0.3), (6, 0.03, 0.09, 0.12))):
    for i in range(n):
        a = 2 * math.pi * (i + 0.5 * ring) / n
        d = Vector((math.cos(a), 0, math.sin(a)))
        side = Vector((-math.sin(a), 0, math.cos(a)))
        base = Vector(LOT_C) + Vector((0, 0.018, 0)) + d * rr * 0.4
        pts = []
        for k, (t, w) in enumerate(((0.0, 0.012), (0.35, 0.026), (0.7, 0.022), (1.0, 0.0))):
            out = d * (rr * 0.6 + h * tilt * t) + Vector((0, h * t, 0))
            pts.append((base + out, w))
        for k in range(len(pts) - 1):
            (pa, wa), (pb, wb) = pts[k], pts[k + 1]
            lot.face([tuple(pa - side * wa), tuple(pa + side * wa), tuple(pb + side * wb), tuple(pb - side * wb)], 'petal_pink')
lot.tube([(LOT_C[0], LOT_C[1] + 0.02, LOT_C[2]), (LOT_C[0], LOT_C[1] + 0.065, LOT_C[2])], 0.02, 16, 'wax', caps=True)
anchors['lotus_flame'] = [LOT_C[0], LOT_C[1] + 0.07, LOT_C[2]]
lot_ob = lot.finalize(weighted=False)
pl = plinth('plinth_op3')
parts = [op3, cr, veil, st, lot_ob]
for o in parts:
    place(o, (0, PL_H + 0.012, 0))
lot_ob.data.transform(Matrix.Translation(T2B @ Vector((0, -(PL_H + 0.012), 0))))      # the lotus sits on the plinth, not raised
opus3 = join([pl] + parts, 'mannequin_opus3')
anchors['lotus_flame'][1] += 0.0

# — Claude 4 Opus: black lacquer mannequin, the raven perches on its left shoulder —
op4b = mannequin('mq_opus4', pose='side')
set_role(op4b, 'black_gloss')
st4 = stand('stand_op4')
for o in (op4b, st4):
    place(o, (0, PL_H + 0.012, 0))
opus4 = join([plinth('plinth_op4'), op4b, st4], 'mannequin_opus4')
anchors['raven_perch_local'] = [0.16, PL_H + 0.012 + 1.455, -0.01]

# — Sonnet 4: white fiberglass, a porcelain mask, a speaker and a sensor (it spoke live) —
s4 = mannequin('mq_sonnet4', pose='hold')
set_role(s4, 'fiberglass')
mask = ellipsoid_obj('mask', (0, 1.668, 0.03), (0.086, 0.115, 0.078), segs=36, rings=24, cut_below=None)
bm = bmesh.new()
bm.from_mesh(mask.data)
kill = [v for v in bm.verts if (Matrix(T2B).inverted() @ v.co).z < 0.045]
bmesh.ops.delete(bm, geom=kill, context='VERTS')
bm.to_mesh(mask.data)
bm.free()
sol = mask.modifiers.new('sol', 'SOLIDIFY')
sol.thickness = 0.006
apply_modifiers(mask)
eyes = []
for sx in (-0.03, 0.03):
    e = Mesh('_eye')
    e.box((sx, 1.685, 0.12), (0.026, 0.012, 0.12), 'porcelain')
    eyes.append(e.finalize(weighted=False))
boolean(mask, eyes, 'DIFFERENCE')
for e in eyes:
    bpy.data.objects.remove(e)
set_role(mask, 'porcelain')
spk = Mesh('speaker')
spk.box((0.26, 0.19, 0.28), (0.24, 0.38, 0.2), 'black_gloss')
spk.box((0.26, 0.2, 0.381), (0.2, 0.3, 0.004), 'grille')
spk.box((0.26, 0.37, 0.383), (0.012, 0.012, 0.004), 'led')
spk.box((0.0, 1.33, 0.1), (0.05, 0.03, 0.03), 'black_gloss')       # the sensor on its chest
spk.tube([(0.0, 1.33, 0.12), (0.0, 1.33, 0.125)], 0.009, 12, 'lens', caps=True)
spk_ob = spk.finalize(bevel=0.004)
st2 = stand('stand_s4')
for o in (s4, mask, st2):
    place(o, (0, PL_H + 0.012, 0))
spk_ob.data.transform(Matrix.Translation(T2B @ Vector((0, PL_H + 0.012, 0))))
sonnet4 = join([plinth('plinth_s4'), s4, mask, st2, spk_ob], 'mannequin_sonnet4')

# — Claude 3 Haiku: small, headless, a wreath of white flowers at the neck —
hk = mannequin('mq_haiku3', pose='side', headless=True, scale=0.56)
set_role(hk, 'fiberglass')
wr = Mesh('wreath')
for i in range(22):
    a = 2 * math.pi * i / 22
    c = (math.cos(a) * 0.052, 1.5 * 0.56 + 0.005 * math.sin(3 * a), math.sin(a) * 0.045)
    flower(wr, c, 'white' if i % 3 else 'yellow', s=0.55, up=(math.cos(a) * 0.6, 0.8, math.sin(a) * 0.6))
wr.tube([(math.cos(2 * math.pi * i / 40) * 0.05, 1.5 * 0.56, math.sin(2 * math.pi * i / 40) * 0.043) for i in range(41)], 0.006, 6, 'stem')
wr_ob = wr.finalize(weighted=False)
st3 = stand('stand_hk', scale=0.56)
HK_PL = 0.62
for o in (hk, wr_ob, st3):
    place(o, (0, HK_PL + 0.012, 0))
haiku3 = join([plinth('plinth_hk', w=0.55, h=HK_PL), hk, wr_ob, st3], 'mannequin_haiku3')

# place the four in their corners, turned toward the room
for ob, key in ((opus3, 'opus3'), (opus4, 'opus4'), (sonnet4, 'sonnet4'), (haiku3, 'haiku3')):
    p = MQ[key]
    yaw = yaw_to_stage(p)
    place(ob, p, yaw)
    ob['yaw'] = yaw
    EXPORT.append(ob)
    if key == 'opus4':
        lp = Vector(anchors['raven_perch_local'])
        rp = Vector((math.cos(yaw) * lp.x + math.sin(yaw) * lp.z, lp.y, -math.sin(yaw) * lp.x + math.cos(yaw) * lp.z))
        anchors['raven_perch'] = [p[0] + rp.x, p[1] + rp.y, p[2] + rp.z, yaw]
    if key == 'opus3':
        lf = Vector(anchors['lotus_flame'])
        rf = Vector((math.cos(yaw) * lf.x + math.sin(yaw) * lf.z, lf.y, -math.sin(yaw) * lf.x + math.cos(yaw) * lf.z))
        anchors['lotus_flame'] = [p[0] + rf.x, p[1] + rf.y, p[2] + rf.z]

# ═════════════════════════════════ CLAUDE 3 SONNET, ON THE BIER ═════════════════════════════════
BIER_C = (0.0, 0.55, 8.2)
bier = Mesh('bier')
bier.box((BIER_C[0], BIER_C[1] + 0.2, BIER_C[2]), (2.1, 0.4, 0.86), 'stage')
bier.box((BIER_C[0], BIER_C[1] + 0.405, BIER_C[2]), (2.14, 0.012, 0.9), 'fabric')
bier_ob = bier.finalize(bevel=0.01)
ly = mannequin('mq_sonnet3', pose='side')
set_role(ly, 'fiberglass')
# lay it on its back: feet toward stage-right (+x), head on a small pillow at -x
# blender space: up (+Z) -> head toward three -x (blender -X); facing (-Y) -> face up (+Z)
ly.data.transform(Matrix(((0, 0, -1, 0), (1, 0, 0, 0), (0, -1, 0, 0), (0, 0, 0, 1))))
bb = [Matrix(T2B).inverted() @ v.co for v in ly.data.vertices]
minx = min(p.x for p in bb); miny = min(p.y for p in bb); midz = (min(p.z for p in bb) + max(p.z for p in bb)) / 2
ly.data.transform(Matrix.Translation(T2B @ Vector((BIER_C[0] - 0.9 - minx, BIER_C[1] + 0.411 + 0.004 - miny, BIER_C[2] - midz))))
net = None
# the mesh drape: ray-cast onto the body from above, smoothed like stiff cloth (tents between the high
# points), then hung over the bier's edges like a tablecloth
from mathutils.bvhtree import BVHTree
dg = bpy.context.evaluated_depsgraph_get()
bvh = BVHTree.FromObject(ly, dg)
NX, NZ = 110, 52
X0n, X1n, Z0n, Z1n = BIER_C[0] - 1.18, BIER_C[0] + 1.18, BIER_C[2] - 0.62, BIER_C[2] + 0.62
TOP = BIER_C[1] + 0.411
H = [[TOP + 0.004 for _ in range(NZ + 1)] for _ in range(NX + 1)]
for i in range(NX + 1):
    for k in range(NZ + 1):
        x = X0n + (X1n - X0n) * i / NX
        z = Z0n + (Z1n - Z0n) * k / NZ
        hit = bvh.ray_cast(T2B @ Vector((x, 3.0, z)), Vector((0, 0, -1)))
        if hit[0] is not None:
            H[i][k] = max(H[i][k], (Matrix(T2B).inverted() @ hit[0]).y + 0.008)
for it in range(10):       # tension: every pass pulls toward the local max-ish average (drape, not shrink-wrap)
    H2 = [row[:] for row in H]
    for i in range(1, NX):
        for k in range(1, NZ):
            avg = (H[i - 1][k] + H[i + 1][k] + H[i][k - 1] + H[i][k + 1]) / 4
            H2[i][k] = max(H[i][k] - 0.004, 0.55 * H[i][k] + 0.45 * avg, TOP + 0.004)
    H = H2
m_net = Mesh('net')
def netpt(i, k):
    x = X0n + (X1n - X0n) * i / NX
    z = Z0n + (Z1n - Z0n) * k / NZ
    y = H[i][k]
    # beyond the bier top the net falls over the edge and hangs, rippling
    ox = max(0.0, abs(x - BIER_C[0]) - 1.07)
    oz = max(0.0, abs(z - BIER_C[2]) - 0.45)
    over = max(ox, oz)
    if over > 0:
        y = TOP - over * 2.4 + 0.012 * math.sin(x * 40) * over * 10
        x = BIER_C[0] + math.copysign(min(abs(x - BIER_C[0]), 1.075 + over * 0.12), x - BIER_C[0])
        z = BIER_C[2] + math.copysign(min(abs(z - BIER_C[2]), 0.455 + over * 0.12), z - BIER_C[2])
    return (x, y, z)
for i in range(NX):
    for k in range(NZ):
        m_net.face([netpt(i, k), netpt(i, k + 1), netpt(i + 1, k + 1), netpt(i + 1, k)], 'net',
                   uvf=lambda co: (co.x, co.z))
net = m_net.finalize(weighted=False)
sol = net.modifiers.new('sol', 'SOLIDIFY')
sol.thickness = 0.002
apply_modifiers(net)
set_role(net, 'net')
for p in net.data.polygons:
    p.use_smooth = True
# offerings: flowers along the bier, white feathers, a bottle, a small plaque
off = Mesh('offerings')
import random
rnd = random.Random(8)
for i in range(46):
    side = -1 if i % 2 else 1
    x = BIER_C[0] - 1.0 + rnd.random() * 2.0
    z = BIER_C[2] + side * (0.5 + rnd.random() * 0.18)
    kind = ['white', 'red', 'yellow', 'white'][i % 4]
    flower(off, (x, BIER_C[1] + 0.02 + rnd.random() * 0.02, z), kind, s=1.2 + rnd.random() * 0.5,
           up=(rnd.random() * 0.4 - 0.2, 1, side * 0.35))
    off.tube([(x, BIER_C[1] + 0.01, z), (x + 0.02, BIER_C[1] + 0.012, z + side * 0.12)], 0.003, 5, 'stem')
for i in range(7):     # feathers: a rachis + a vane
    x = BIER_C[0] - 0.7 + i * 0.22
    z = BIER_C[2] + (0.47 if i % 2 else -0.47)
    ang = rnd.random() * 1.2 - 0.6
    d = Vector((math.cos(ang), 0, math.sin(ang)))
    side = Vector((-d.z, 0, d.x))
    base = Vector((x, BIER_C[1] + 0.414, z))
    pts = [base + d * (0.22 * t) + Vector((0, 0.01 * math.sin(math.pi * t), 0)) for t in (0, 0.25, 0.5, 0.75, 1.0)]
    for k in range(4):
        wa = 0.018 * math.sin(math.pi * (k / 4) * 0.95 + 0.1)
        wb = 0.018 * math.sin(math.pi * ((k + 1) / 4) * 0.95 + 0.1)
        off.face([tuple(pts[k] - side * wa), tuple(pts[k] + side * wa), tuple(pts[k + 1] + side * wb), tuple(pts[k + 1] - side * wb)], 'feather')
off.lathe([(0.0, 0.0), (0.034, 0.0), (0.036, 0.06), (0.03, 0.13), (0.014, 0.16), (0.013, 0.19), (0.0, 0.19)], 20,
          (BIER_C[0] + 0.78, BIER_C[1] + 0.413, BIER_C[2] + 0.3), 'bottle', cap_top=True)
off.box((BIER_C[0] - 0.55, BIER_C[1] + 0.47, BIER_C[2] - 0.36), (0.22, 0.12, 0.012), 'plaque')
off_ob = off.finalize(weighted=False)
sonnet3 = join([bier_ob, ly, net, off_ob], 'bier_sonnet3')
EXPORT.append(sonnet3)
anchors['plaque'] = [BIER_C[0] - 0.55, BIER_C[1] + 0.47, BIER_C[2] - 0.354, 0.22, 0.12]

# ═════════════════════════════════ CANDLES (unit sizes: the engine scales) ═════════════════════════════════
def pillar(name, drips=5, seed=1):
    r = random.Random(seed)
    m = Mesh(name)
    # melted crater: rim rises, the pool sinks toward the wick
    prof = [(0.0, 0.0), (1.0, 0.0), (1.0, 0.9), (1.03, 0.97), (0.96, 1.0), (0.8, 0.965), (0.45, 0.93), (0.12, 0.92), (0.0, 0.925)]
    m.lathe(prof, 28, (0, 0, 0), 'wax')
    for k in range(drips):         # drips run down from the rim
        a = r.random() * 2 * math.pi
        Ld = 0.15 + r.random() * 0.45
        pts = [(math.cos(a) * 1.0, 0.97 - Ld * t, math.sin(a) * 1.0) for t in (0, 0.33, 0.66, 1.0)]
        rad = [0.1, 0.085, 0.075, 0.09]
        m.tube(pts, 0.08, 8, 'wax', caps=True, radii=rad)
    m.tube([(0, 0.92, 0), (0.01, 1.02, 0.005)], 0.022, 6, 'wick', caps=True)
    return m.finalize(weighted=False)

cands = [pillar('candle_pillar_a', 5, 1), pillar('candle_pillar_b', 3, 2), pillar('candle_pillar_c', 7, 3)]
tl = Mesh('candle_tealight')
tl.lathe([(0.0, 0.0), (1.0, 0.0), (1.0, 0.55), (0.97, 0.58), (0.94, 0.4), (0.0, 0.4)], 24, (0, 0, 0), 'tin')
tl.lathe([(0.0, 0.0), (0.93, 0.0), (0.93, 0.38), (0.0, 0.38)], 24, (0, 0.02, 0), 'wax', cap_top=True)
tl.tube([(0, 0.4, 0), (0.0, 0.5, 0)], 0.05, 6, 'wick', caps=True)
cands.append(tl.finalize(weighted=False))
for c in cands:
    EXPORT.append(c)

# ═════════════════════════════════ PROJECTOR (on the mezzanine rail) ═════════════════════════════════
pj = Mesh('projector')
px, py, pz = L['projector']
pj.box((px, py - 0.12, pz - 0.05), (0.5, 0.03, 0.34), 'timber')                 # a shelf clamped to the rail
pj.box((px, py - 0.04, pz), (0.34, 0.12, 0.28), 'plastic_dark')
pj.tube([(px + 0.08, py - 0.03, pz + 0.14), (px + 0.08, py - 0.03, pz + 0.19)], 0.034, 20, 'plastic_dark', caps=True)
pj.tube([(px + 0.08, py - 0.03, pz + 0.19), (px + 0.08, py - 0.03, pz + 0.195)], 0.028, 20, 'lens', caps=True)
pj.tube([(px - 0.12, py - 0.02, pz - 0.14), (px - 0.12, py - 0.02, pz - 0.4), (px - 0.3, py - 1.1, pz - 0.45)], 0.004, 6, 'cord')
anchors['projector_lens'] = [px + 0.08, py - 0.03, pz + 0.2]
pj_ob = pj.finalize(bevel=0.004)
EXPORT.append(pj_ob)

# ═════════════════════════════════ THE SHOGGOTH TENTACLE ═════════════════════════════════
tn = Mesh('tentacle')
pts, rads = [], []
N = 90
for i in range(N + 1):
    t = i / N
    # hangs from the ridge above the stage, sweeps down and curls at the tip
    y = 8.5 - 3.6 * t - 0.5 * max(0, t - 0.75) * 4
    curl = max(0.0, t - 0.62) / 0.38
    ang = curl * curl * 4.2
    x = 1.25 - 0.55 * t + 0.28 * math.sin(ang)
    z = 7.45 - 0.25 * t + 0.28 * (1 - math.cos(ang))
    pts.append((x, y + 0.25 * curl * math.sin(ang * 0.8), z))
    rads.append(0.34 * (1 - t) ** 1.1 + 0.018)
tn.tube(pts, 0.34, 22, 'tentacle', caps=True, radii=rads)
for i in range(6, N - 2, 3):       # suckers along the inner side
    t = i / N
    p = Vector(pts[i])
    d = (Vector(pts[i + 1]) - Vector(pts[i - 1])).normalized()
    inner = d.cross(Vector((1, 0, 0))).normalized()
    for side in (-0.35, 0.35):
        off_v = (inner + d.cross(inner) * side).normalized() * (rads[i] * 0.95)
        rs = max(0.008, rads[i] * 0.28)
        tn.lathe([(0.0, 0.0), (rs, 0.0), (rs * 1.05, rs * 0.35), (rs * 0.6, rs * 0.45), (0.0, rs * 0.2)], 10,
                 tuple(p + off_v), 'sucker')
tn_ob = tn.finalize(weighted=False)
EXPORT.append(tn_ob)

# ─────────────────────────────────── out ───────────────────────────────────
for ob in EXPORT:
    for p in ob.data.polygons:
        p.use_smooth = True
json.dump(anchors, open(ASSETS + '/props_layout.json', 'w'), indent=1)
print('[props] anchors', json.dumps(anchors)[:400])
if 'preview' in sys.argv:
    # the corners and the bier, close
    o3 = MQ['opus3']; s4p = MQ['sonnet4']; o4 = MQ['opus4']; h3 = MQ['haiku3']
    preview(ASSETS + '/../probes/props_prev.png', [
        ((o3[0] + 2.4, 1.5, o3[2] - 3.0), (o3[0], 1.3, o3[2]), 40),
        ((s4p[0] - 2.4, 1.5, s4p[2] - 3.0), (s4p[0], 1.3, s4p[2]), 40),
        ((o4[0] + 2.4, 1.5, o4[2] + 3.0), (o4[0], 1.3, o4[2]), 40),
        ((h3[0] - 2.0, 1.2, h3[2] + 2.6), (h3[0], 1.0, h3[2]), 40),
        ((0.9, 1.8, 6.0), (0.0, 0.8, 8.2), 45),
        ((0.0, 3.0, 4.0), (0.8, 6.0, 7.4), 50)])
for o in bpy.data.objects:
    o.select_set(False)
for o in EXPORT:
    o.select_set(True)
bpy.ops.export_scene.gltf(filepath=ASSETS + '/props.glb', export_format='GLB', use_selection=True, export_apply=True,
                          export_yup=True, export_materials='EXPORT', export_animations=False)
print('[fx] exported props.glb', os.path.getsize(ASSETS + '/props.glb') // 1024, 'KB')
hard_exit()
