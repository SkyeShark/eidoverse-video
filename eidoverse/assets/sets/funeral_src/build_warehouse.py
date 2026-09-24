# build_warehouse.py — the SoMa warehouse for the Claude 3 Sonnet funeral (DAISY bridge).
#   blender --background --python build_warehouse.py [-- preview]
# Writes work/daisy/sets/assets/warehouse.glb + funeral_layout.json (+ previews).
#
# Three.js space, metres: interior x in [-9, 9], z in [-12, 10] (stage end at +z),
# floor y = 0. Brick side walls on a poured stem wall, brick gables with an oculus,
# Howe timber trusses (bolted steel gussets, steel rods) at 3.6 m, purlins, plank
# decking with four skylights, a timber mezzanine along the back with a braced
# railing and a stair on the right wall, a corrugated rolling door + a steel
# pedestrian door (EXIT sign) under it, a skirted stage with a roll-down screen,
# RLM enamel pendants, conduit runs.
import sys
import os
import math
import json
import bpy
import bmesh
from mathutils import Vector

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import importlib
import fx_core
importlib.reload(fx_core)
from fx_core import Mesh, boolean, reuv_planar, export_glb, preview, reset_scene, ASSETS, empty

reset_scene()
col = bpy.context.scene.collection

X0, X1, Z0, Z1 = -9.0, 9.0, -12.0, 10.0
WT = 0.36
WALL_TOP = 6.5
BASE_H = 0.55
TRUSS_Z = [-10.2, -6.6, -3.0, 0.6, 4.2, 7.8]
SLOPE = 2.0 / 9.0
CH_TOP0 = 6.25            # top-chord upper edge at |x| = 9
def chord_top(x):         # upper edge of top chord
    return CH_TOP0 + (9.0 - abs(x)) * SLOPE
PURLIN_H = 0.18
def deck_under(x):
    return chord_top(x) + PURLIN_H
RIDGE_UNDER = deck_under(0.0)
MEZZ_Y = 3.2
MEZZ_Z = -9.2
STAGE = dict(x0=-4.6, x1=4.6, z0=6.4, z1=10.0, y=0.55)
LAMP_Z = [-6.6, -3.0, 0.6, 4.2]
LAMP_X = [-4.5, 0.0, 4.5]
WIN_Z = [-8.4, -4.8, -1.2, 2.4, 6.0]
WIN = dict(w=2.2, y0=3.9, y1=5.55)
SKY = [(-4.5, -4.8), (4.5, -4.8), (-4.5, 2.4), (4.5, 2.4)]
DOOR = dict(x0=-2.1, x1=2.1, h=2.55)
PDOOR = dict(x=6.3, w=0.95, h=2.15)
layout = {'interior': [X0, X1, Z0, Z1], 'wall_top': WALL_TOP, 'truss_z': TRUSS_Z, 'mezz_y': MEZZ_Y,
          'mezz_z': MEZZ_Z, 'stage': STAGE, 'lamps': [], 'windows': [], 'skylights': [], 'oculi': []}

# ───────────────────────────── floor ──────────────────────────────
fl = Mesh('wh_floor')
fl.face([(X0, 0, Z1), (X1, 0, Z1), (X1, 0, Z0), (X0, 0, Z0)], 'floor')
floor_ob = fl.finalize(weighted=False)

# ───────────────────────────── side walls ─────────────────────────
def side_wall(sign):
    """brick mass from BASE_H to WALL_TOP with pilasters unioned, windows cut."""
    x_in = X1 if sign > 0 else X0
    xc = x_in + sign * WT / 2
    m = Mesh('wall_side_%s' % ('R' if sign > 0 else 'L'))
    m.box((xc, (BASE_H + WALL_TOP) / 2, (Z0 + Z1) / 2), (WT, WALL_TOP - BASE_H, Z1 - Z0 + 2 * WT), 'brick')
    ob = m.finalize(weighted=False)
    pils = []
    for z in TRUSS_Z:
        p = Mesh('_pil')
        p.box((x_in - sign * 0.11, (BASE_H - 0.03 + 5.72) / 2, z), (0.28, 5.72 - BASE_H + 0.03, 0.62), 'brick')
        pils.append(p.finalize(weighted=False))
    boolean(ob, pils, op='UNION')
    cuts = []
    for z in WIN_Z:
        c = Mesh('_win')
        c.box((xc, (WIN['y0'] + WIN['y1']) / 2, z), (WT * 3, WIN['y1'] - WIN['y0'], WIN['w']), 'brick')
        cuts.append(c.finalize(weighted=False))
    boolean(ob, cuts, op='DIFFERENCE')
    for o in pils + cuts:
        bpy.data.objects.remove(o)
    reuv_planar(ob)
    return ob

walls = [side_wall(-1), side_wall(1)]

# ───────────────────────────── gable walls ────────────────────────
def gable(zc, name, openings):
    zin = Z1 if zc > 0 else Z0
    zmid = zin + (WT / 2 if zc > 0 else -WT / 2)
    xo = X1 + WT
    apex = RIDGE_UNDER + 0.12
    prof = [(-xo, BASE_H), (xo, BASE_H), (xo, WALL_TOP + 0.02), (0.0, apex), (-xo, WALL_TOP + 0.02)]
    m = Mesh(name)
    m.extrude_profile(prof, zmid - WT / 2, zmid + WT / 2, 'brick', axis='z')
    ob = m.finalize(weighted=False)
    cuts = []
    for kind, a in openings:
        c = Mesh('_cut')
        if kind == 'rect':
            x0, x1, y0, y1 = a
            c.box(((x0 + x1) / 2, (y0 + y1) / 2, zmid), (x1 - x0, y1 - y0, WT * 3), 'brick')
        else:
            cx, cy, r = a
            c.lathe([(r, -WT * 2), (r, WT * 2)], 40, (cx, cy, zmid), 'brick', cap_top=True, cap_bot=True)
            co = c.finalize(weighted=False)
            co.rotation_euler = (0, 0, 0)
            # lathe axis is +y; rotate to +z (three) -> blender: about x by 90deg
            co.data.transform(__import__('mathutils').Matrix.Rotation(math.radians(90), 4, 'X'))
            # re-centre (rotation happened about origin): move from (cx, -zmid?, cy) mapping
            me = co.data
            cB = Vector((cx, -zmid, cy))
            mean = sum((v.co for v in me.vertices), Vector()) / len(me.vertices)
            for v in me.vertices:
                v.co += cB - mean
            cuts.append(co)
            continue
        cuts.append(c.finalize(weighted=False))
    boolean(ob, cuts, 'DIFFERENCE')
    for o in cuts:
        bpy.data.objects.remove(o)
    reuv_planar(ob)
    return ob

walls.append(gable(1, 'wall_front', [('circle', (0.0, 7.15, 0.62))]))
walls.append(gable(-1, 'wall_back', [('rect', (DOOR['x0'], DOOR['x1'], -0.1, DOOR['h'])),
                                     ('rect', (PDOOR['x'] - PDOOR['w'] / 2, PDOOR['x'] + PDOOR['w'] / 2, -0.1, PDOOR['h'])),
                                     ('circle', (0.0, 7.05, 0.55))]))
layout['oculi'] = [[0.0, 7.15, Z1 + WT / 2, 0.62], [0.0, 7.05, Z0 - WT / 2, 0.55]]

# stem wall (poured concrete, a separate construction) with door gaps
stem = Mesh('stem_wall')
for sign in (-1, 1):
    xin = X1 if sign > 0 else X0
    stem.box((xin + sign * (WT / 2 - 0.02), BASE_H / 2, (Z0 + Z1) / 2), (WT + 0.04, BASE_H, Z1 - Z0 + 2 * WT + 0.04), 'concrete')
xo = X1 + WT + 0.02
stem.box((0, BASE_H / 2, Z1 + WT / 2), (2 * xo, BASE_H, WT + 0.04), 'concrete')
# back: leave the two doorways open
segs = [(-xo, DOOR['x0']), (DOOR['x1'], PDOOR['x'] - PDOOR['w'] / 2), (PDOOR['x'] + PDOOR['w'] / 2, xo)]
for a, b in segs:
    stem.box(((a + b) / 2, BASE_H / 2, Z0 - WT / 2), (b - a, BASE_H, WT + 0.04), 'concrete')
stem_ob = stem.finalize(bevel=0.012, bevel_segs=2)

# window sills (precast concrete, sloped top) + steel lintels + steel sashes
trim = Mesh('wall_trim')
sash = Mesh('window_sash')
glass = Mesh('window_glass')
for sign in (-1, 1):
    xin = X1 if sign > 0 else X0
    for z in WIN_Z:
        w = WIN['w']
        # sill: projects 0.05 inside, sloped
        trim.extrude_profile([(xin - sign * 0.06, WIN['y0'] - 0.07), (xin + sign * (WT + 0.05), WIN['y0'] - 0.07),
                              (xin + sign * (WT + 0.05), WIN['y0'] - 0.02), (xin - sign * 0.06, WIN['y0'] + 0.01)][::sign],
                             z - w / 2 - 0.08, z + w / 2 + 0.08, 'concrete', axis='z')
        # steel lintel angle over the head (inside face)
        trim.box((xin - sign * 0.005, WIN['y1'] + 0.05, z), (0.012, 0.1, w + 0.3), 'steel')
        trim.box((xin + sign * WT / 2, WIN['y1'] + 0.006, z), (WT, 0.012, w + 0.3), 'steel')
        # sash: perimeter frame + muntins (4 x 3 lights), set 0.12 into the opening
        xs = xin + sign * 0.12
        y0, y1 = WIN['y0'], WIN['y1']
        fw = 0.05
        sash.box((xs, y0 + fw / 2, z), (0.06, fw, w), 'steel')
        sash.box((xs, y1 - fw / 2, z), (0.06, fw, w), 'steel')
        sash.box((xs, (y0 + y1) / 2, z - w / 2 + fw / 2), (0.06, y1 - y0, fw), 'steel')
        sash.box((xs, (y0 + y1) / 2, z + w / 2 - fw / 2), (0.06, y1 - y0, fw), 'steel')
        for k in range(1, 4):
            zz = z - w / 2 + w * k / 4
            sash.box((xs, (y0 + y1) / 2, zz), (0.045, y1 - y0 - 2 * fw, 0.025), 'steel')
        for k in range(1, 3):
            yy = y0 + (y1 - y0) * k / 3
            sash.box((xs, yy, z), (0.045, 0.025, w - 2 * fw), 'steel')
        # a pivoting vent light in the middle row (opened a crack)
        glass.face([(xs, y0 + fw, z - w / 2 + fw), (xs, y0 + fw, z + w / 2 - fw), (xs, y1 - fw, z + w / 2 - fw),
                    (xs, y1 - fw, z - w / 2 + fw)][::sign], 'glass')
        layout['windows'].append([xin, (y0 + y1) / 2, z, w, y1 - y0, sign])
trim_ob = trim.finalize(bevel=0.006)
sash_ob = sash.finalize(bevel=0.003)
# (glass finalized at the end)

# oculus frames (steel rings with a cross)
ocf = Mesh('oculus_frames')
for (cx, cy, cz, r) in layout['oculi']:
    zin = cz - (WT / 2) * (1 if cz > 0 else -1)
    pts = [(cx + (r - 0.03) * math.cos(a), cy + (r - 0.03) * math.sin(a), zin + (0.08 if cz < 0 else -0.08))
           for a in [2 * math.pi * i / 48 for i in range(49)]]
    ocf.tube(pts, 0.03, 8, 'steel')
    ocf.beam((cx - r, cy, zin + (0.08 if cz < 0 else -0.08)), (cx + r, cy, zin + (0.08 if cz < 0 else -0.08)), 0.04, 0.04, 'steel')
    ocf.beam((cx, cy - r, zin + (0.08 if cz < 0 else -0.08)), (cx, cy + r, zin + (0.08 if cz < 0 else -0.08)), 0.04, 0.04, 'steel')
    glass.face([(cx + r * math.cos(a), cy + r * math.sin(a), zin + (0.1 if cz < 0 else -0.1)) for a in
                [2 * math.pi * i / 32 for i in range(32)]][::(1 if cz < 0 else -1)], 'glass')
ocf_ob = ocf.finalize(bevel=0.004)

# ───────────────────────────── trusses ────────────────────────────
tim = Mesh('trusses_timber')
stl = Mesh('trusses_steel')
BOLTS = []
for zt in TRUSS_Z:
    bc_y = 5.875
    # bottom chord (two members lapped at the centre gusset)
    tim.beam((X0 + 0.12, bc_y, zt), (X1 - 0.12, bc_y, zt), 0.2, 0.25, 'timber', up=(0, 1, 0))
    # top chords: centerline from above the chord end to the apex
    ya = chord_top(8.85) - 0.125
    yb = chord_top(0.0) - 0.125
    for s in (-1, 1):
        tim.beam((s * 8.85, ya, zt), (s * 0.12, yb, zt), 0.2, 0.25, 'timber', up=(0, 1, 0))
    # king post
    tim.beam((0, bc_y + 0.125, zt), (0, yb + 0.1, zt), 0.2, 0.2, 'timber', up=(0, 0, 1))
    # diagonals (compression, toward the centre going up)
    for s in (-1, 1):
        for xa, xb in ((6.0, 3.0), (3.0, 0.3)):
            top_y = chord_top(xb) - 0.26 if xb > 0.5 else yb - 0.35
            tim.beam((s * xa, bc_y + 0.12, zt), (s * xb, top_y, zt), 0.16, 0.16, 'timber', up=(0, 0, 1))
    # steel rods (tension verticals) at +-3, +-6 with nuts + washers
    for s in (-1, 1):
        for xr in (3.0, 6.0):
            y0 = bc_y - 0.14
            y1 = chord_top(xr) + 0.01
            stl.tube([(s * xr, y0 - 0.05, zt), (s * xr, y1 + 0.05, zt)], 0.018, 10, 'steel', caps=True)
            for yy, dn in ((y0, -1), (y1, 1)):
                stl.box((s * xr, yy + dn * 0.012, zt), (0.1, 0.012, 0.1), 'steel')      # plate washer
                stl.box((s * xr, yy + dn * 0.03, zt), (0.045, 0.03, 0.045), 'steel')    # nut
    # gusset plates at joints, both faces
    joints = [(0, bc_y + 0.05), (3.0, bc_y), (-3.0, bc_y), (6.0, bc_y), (-6.0, bc_y),
              (0, yb - 0.05), (3.0, chord_top(3.0) - 0.15), (-3.0, chord_top(3.0) - 0.15),
              (6.0, chord_top(6.0) - 0.15), (-6.0, chord_top(6.0) - 0.15)]
    for (jx, jy) in joints:
        for s in (-1, 1):
            stl.box((jx, jy, zt + s * 0.106), (0.52, 0.44, 0.012), 'steel')
            for i in range(6):
                a = i * math.pi / 3 + 0.3
                BOLTS.append((jx + math.cos(a) * 0.17, jy + math.sin(a) * 0.13, zt + s * 0.118))
    # heel: steel bearing shoe on the pilaster
    for s in (-1, 1):
        stl.box((s * (X1 - 0.18), 5.735, zt), (0.34, 0.02, 0.62), 'steel')
        stl.box((s * (X1 - 0.02), 5.9, zt), (0.012, 0.34, 0.3), 'steel')
tim_ob = tim.finalize(bevel=0.012, bevel_segs=2)
stl_ob = stl.finalize(bevel=0.002, bevel_segs=1)

# ── bolts, done right: one tiny mesh, placed per bolt (linked duplicates joined)
bolt_m = Mesh('bolt_src')
bolt_m.lathe([(0.0, 0.0), (0.032, 0.0), (0.032, 0.005), (0.02, 0.005), (0.02, 0.019), (0.012, 0.024), (0.0, 0.024)],
             6, (0, 0, 0), 'steel', cap_top=False)
bolt_src = bolt_m.finalize(weighted=False)
# the lathe axis is three +y; bolts on a truss face point along three +-z
bm_b = bmesh.new()
bm_b.from_mesh(bolt_src.data)
bpy.data.objects.remove(bolt_src)
from mathutils import Matrix
bolts_me = bpy.data.meshes.new('truss_bolts')
out = bmesh.new()
for (bx, by, bz) in BOLTS:
    sgn = 1 if bz > 0 else -1
    # blender coords: three (x,y,z)->(x,-z,y); bolt axis three +-z == blender -+y
    rot = Matrix.Rotation(math.radians(-90 * sgn), 4, 'X')      # blender z(up) -> blender -+y
    mtx = Matrix.Translation((bx, -bz, by)) @ rot
    tmp = bm_b.copy()
    bmesh.ops.transform(tmp, matrix=mtx, verts=tmp.verts)
    tmp_me = bpy.data.meshes.new('_b')
    tmp.to_mesh(tmp_me)
    out.from_mesh(tmp_me)
    bpy.data.meshes.remove(tmp_me)
    tmp.free()
out.to_mesh(bolts_me)
out.free()
bolts_me.materials.append(fx_core.material('steel'))
bolts_ob = bpy.data.objects.new('truss_bolts', bolts_me)
col.objects.link(bolts_ob)
for p in bolts_me.polygons:
    p.use_smooth = False
# ───────────────────────────── purlins + deck + skylights ─────────
pur = Mesh('roof_purlins')
for xp in (-7.5, -4.5, -1.5, 1.5, 4.5, 7.5):
    yc = chord_top(xp) + PURLIN_H / 2
    pur.beam((xp, yc, Z0 - WT), (xp, yc, Z1 + WT), 0.1, PURLIN_H, 'timber', up=(0, 1, 0))
# ridge board
pur.beam((0, deck_under(0) - 0.12, Z0 - WT), (0, deck_under(0) - 0.12, Z1 + WT), 0.06, 0.24, 'timber')
pur_ob = pur.finalize(bevel=0.008)

deck = Mesh('roof_deck')
T = 0.05
for s in (-1, 1):
    xa, xb = s * (X1 + WT + 0.45), 0.0
    ya, yb = deck_under(X1 + WT + 0.45), deck_under(0.0)
    # underside + top as a slab
    p0 = (xa, ya, Z0 - WT - 0.3); p1 = (xb, yb, Z0 - WT - 0.3)
    p2 = (xb, yb, Z1 + WT + 0.3); p3 = (xa, ya, Z1 + WT + 0.3)
    deck.extrude_profile([(xa, ya), (xb, yb), (xb, yb + T), (xa, ya + T)][::(-s)], Z0 - WT - 0.3, Z1 + WT + 0.3, 'planks', axis='z')
deck_ob = deck.finalize(weighted=False)
skcut = []
for (sx, sz) in SKY:
    c = Mesh('_sk')
    c.box((sx, deck_under(sx) + 0.1, sz), (1.2, 1.2, 2.4), 'planks')
    skcut.append(c.finalize(weighted=False))
boolean(deck_ob, skcut, 'DIFFERENCE')
for o in skcut:
    bpy.data.objects.remove(o)
# roof deck UVs: planks run DOWN the slope (u along x), metres
me = deck_ob.data
uvl = me.uv_layers.active
for p in me.polygons:
    for li in p.loop_indices:
        c = me.vertices[me.loops[li].vertex_index].co   # blender coords
        uvl.data[li].uv = (c.x / math.cos(math.atan(SLOPE)), -c.y)
skyl = Mesh('skylight_curbs')
for (sx, sz) in SKY:
    yb = deck_under(sx)
    for dz in (-1.2, 1.2):
        skyl.box((sx, yb + 0.14, sz + dz), (1.3, 0.3, 0.08), 'timber')
    for dx in (-0.61, 0.61):
        skyl.box((sx + dx, yb + 0.14, sz), (0.08, 0.3 + abs(dx) * SLOPE * 2, 2.48), 'timber')
    glass.face([(sx - 0.6, yb + 0.33, sz + 1.2), (sx + 0.6, yb + 0.33, sz + 1.2), (sx + 0.6, yb + 0.33, sz - 1.2),
                (sx - 0.6, yb + 0.33, sz - 1.2)], 'glass')
    layout['skylights'].append([sx, yb + 0.3, sz, 1.2, 2.4])
skyl_ob = skyl.finalize(bevel=0.006)

# ───────────────────────────── mezzanine + stair ──────────────────
mz = Mesh('mezz_timber')
BEAM_Z = MEZZ_Z - 0.14
mz.beam((X0 + 0.02, MEZZ_Y - 0.05 - 0.2 - 0.2, BEAM_Z), (X1 - 0.02, MEZZ_Y - 0.05 - 0.2 - 0.2, BEAM_Z), 0.26, 0.4, 'timber')
for xp in (-6.0, -2.0, 2.0, 6.0):
    mz.beam((xp, 0.02, BEAM_Z), (xp, MEZZ_Y - 0.65, BEAM_Z), 0.24, 0.24, 'timber', up=(0, 0, 1))
jz = -12.0
nj = 0
x = X0 + 0.3
while x < X1 - 0.2:
    mz.beam((x, MEZZ_Y - 0.05 - 0.1, Z0 + 0.02), (x, MEZZ_Y - 0.05 - 0.1, MEZZ_Z - 0.02), 0.08, 0.2, 'timber')
    x += 0.6
mz.box((0, MEZZ_Y - 0.025, (Z0 + MEZZ_Z) / 2), (X1 - X0, 0.05, MEZZ_Z - Z0), 'planks')
mz.box((0, MEZZ_Y - 0.1, MEZZ_Z + 0.015), (X1 - X0, 0.2, 0.03), 'timber')     # rim board
# railing: posts socketed into the rim, top + mid rails, X braces per bay (stair gap at the right)
rx = [-8.9, -7.1, -5.3, -3.5, -1.7, 0.1, 1.9, 3.7, 5.5, 7.3]
RZ = MEZZ_Z + 0.06
for xp in rx:
    mz.beam((xp, MEZZ_Y - 0.18, RZ), (xp, MEZZ_Y + 1.02, RZ), 0.09, 0.09, 'timber', up=(0, 0, 1))
mz.beam((rx[0] - 0.05, MEZZ_Y + 1.07, RZ), (rx[-1] + 0.05, MEZZ_Y + 1.07, RZ), 0.14, 0.09, 'timber', up=(0, 1, 0))
mz.beam((rx[0], MEZZ_Y + 0.5, RZ), (rx[-1], MEZZ_Y + 0.5, RZ), 0.07, 0.09, 'timber', up=(0, 1, 0))
for i in range(len(rx) - 1):
    a, b = rx[i] + 0.05, rx[i + 1] - 0.05
    mz.beam((a, MEZZ_Y + 0.08, RZ - 0.01), (b, MEZZ_Y + 0.46, RZ - 0.01), 0.05, 0.035, 'timber', up=(0, 0, 1))
    mz.beam((a, MEZZ_Y + 0.46, RZ + 0.01), (b, MEZZ_Y + 0.08, RZ + 0.01), 0.05, 0.035, 'timber', up=(0, 0, 1))
# stair along the right wall: 18 risers, open treads on steel channel stringers
SX0, SX1 = 7.55, 8.85
NR = 18
rise = MEZZ_Y / NR
run = 0.33
z_top = MEZZ_Z
z_bot = MEZZ_Z + run * (NR - 1)
st = Mesh('stair')
for sxs in (SX0 + 0.04, SX1 - 0.04):
    st.beam((sxs, 0.12, z_bot + 0.2), (sxs, MEZZ_Y - 0.1, z_top - 0.05), 0.06, 0.3, 'steel', up=(0, 1, 0))
for i in range(NR - 1):
    y = rise * (i + 1)
    zc = z_bot - run * i
    st.box(((SX0 + SX1) / 2, y - 0.025, zc), (SX1 - SX0 - 0.14, 0.05, run - 0.01), 'planks')
# handrail on the open side (galvanised pipe on posts)
hr = [(SX0 - 0.05, 0.95, z_bot + 0.35), (SX0 - 0.05, MEZZ_Y + 0.95, z_top + 0.1)]
st.tube(hr, 0.022, 10, 'galv', caps=True)
for k in range(4):
    f = k / 3
    zz = z_bot + 0.35 + (z_top + 0.1 - z_bot - 0.35) * f
    yy = 0.95 + MEZZ_Y * f
    st.tube([(SX0 - 0.05, yy - 0.95 + rise * 0.6, zz), (SX0 - 0.05, yy, zz)], 0.02, 8, 'galv')
mz_ob = mz.finalize(bevel=0.008)
st_ob = st.finalize(bevel=0.004)

# ───────────────────────────── rolling door + pedestrian door ─────
rd = Mesh('rolling_door')
zf = Z0 + 0.06
w = DOOR['x1'] - DOOR['x0']
# curtain: corrugated profile in (y, z) extruded along x
prof = []
H = DOOR['h']
pitch = 0.076
n = int(H / pitch * 8)
for i in range(n + 1):
    y = H * i / n
    prof.append((0.012 * math.sin(2 * math.pi * y / pitch), y))
# build as a thin closed profile: front wave then back wave reversed
closed = [(zf + dz, y) for dz, y in prof] + [(zf + dz - 0.012, y) for dz, y in reversed(prof)]
rd.extrude_profile(closed, DOOR['x0'] - 0.05, DOOR['x1'] + 0.05, 'corrugated', axis='x')
# bottom bar, guides, hood, chain hoist
rd.box((0, 0.04, zf + 0.02), (w + 0.1, 0.08, 0.07), 'steel')
for s in (-1, 1):
    rd.box((s * (w / 2 + 0.06), H / 2 + 0.05, zf + 0.02), (0.1, H + 0.1, 0.1), 'steel')
rd.extrude_profile([(zf - 0.02, H + 0.02), (zf + 0.42, H + 0.02), (zf + 0.46, H + 0.2), (zf + 0.4, H + 0.36), (zf - 0.02, H + 0.36)],
                   DOOR['x0'] - 0.18, DOOR['x1'] + 0.18, 'steel', axis='x')
rd.box((DOOR['x1'] + 0.26, H - 0.2, zf + 0.12), (0.18, 0.28, 0.16), 'steel')          # hoist box
rd.tube([(DOOR['x1'] + 0.22, H - 0.35, zf + 0.2), (DOOR['x1'] + 0.22, 0.9, zf + 0.2)], 0.008, 6, 'steel')
rd.tube([(DOOR['x1'] + 0.3, H - 0.35, zf + 0.2), (DOOR['x1'] + 0.3, 1.1, zf + 0.2)], 0.008, 6, 'steel')
rd.box((0.0, 0.62, zf + 0.04), (0.35, 0.05, 0.04), 'steel')                         # pull handle
rd_ob = rd.finalize(bevel=0.003, weighted=True)
# pedestrian door: steel leaf with panel inset, frame, push bar, EXIT sign above
pd = Mesh('ped_door')
px, pw, ph = PDOOR['x'], PDOOR['w'], PDOOR['h']
pd.box((px, ph / 2, Z0 + 0.05), (pw - 0.04, ph - 0.02, 0.05), 'steel')
for s in (-1, 1):
    pd.box((px + s * (pw / 2 + 0.02), ph / 2, Z0 + 0.03), (0.06, ph + 0.06, 0.12), 'steel')
pd.box((px, ph + 0.05, Z0 + 0.03), (pw + 0.12, 0.06, 0.12), 'steel')
pd.box((px, 1.0, Z0 + 0.1), (pw - 0.2, 0.05, 0.06), 'galv')
pd.box((px, ph + 0.34, Z0 + 0.1), (0.42, 0.2, 0.1), 'exit')
layout['exit'] = [px, ph + 0.34, Z0 + 0.155, 0.36, 0.14]
pd_ob = pd.finalize(bevel=0.004)

# ───────────────────────────── stage + screen ─────────────────────
sg = Mesh('stage')
sx0, sx1, sz0, sz1, sy = STAGE['x0'], STAGE['x1'], STAGE['z0'], STAGE['z1'], STAGE['y']
sg.box(((sx0 + sx1) / 2, sy - 0.02, (sz0 + sz1) / 2), (sx1 - sx0, 0.04, sz1 - sz0), 'stage')
# pleated skirt on the three open sides (a sine curtain)
def skirt(p0, p1, out):
    L = (Vector(p1) - Vector(p0)).length
    n = max(8, int(L / 0.05))
    d = (Vector(p1) - Vector(p0)).normalized()
    o = Vector(out)
    top, bot = [], []
    for i in range(n + 1):
        f = i / n
        base = Vector(p0) + d * (L * f) + o * (0.035 + 0.03 * math.sin(2 * math.pi * f * L / 0.14))
        top.append((base.x, sy - 0.04, base.z))
        bot.append((base.x, 0.005, base.z))
    for i in range(n):
        sg.face([bot[i], bot[i + 1], top[i + 1], top[i]], 'fabric',
                uvf=lambda co, d=d, p0=p0: (Vector((co.x - p0[0], 0, co.z - p0[2])).dot(d), co.y))
skirt((sx0, 0, sz0), (sx1, 0, sz0), (0, 0, -1))
skirt((sx0, 0, sz1), (sx0, 0, sz0), (-1, 0, 0))
skirt((sx1, 0, sz0), (sx1, 0, sz1), (1, 0, 0))
# stage steps on the left side
for k in range(3):
    h = sy * (k + 1) / 4
    sg.box((sx0 - 0.9 + k * 0.3 + 0.15, h / 2, 7.9), (0.3 * (3 - k) + 0.0 if False else 0.3, h, 1.2), 'stage')
sg_ob = sg.finalize(bevel=0.006)
# roll-down screen on the front wall
sc = Mesh('screen')
SW, SH, SY0 = 4.4, 2.48, 3.15
sc.box((0, SY0 + SH / 2, Z1 - 0.02), (SW, SH, 0.006), 'screen')
sc.box((0, SY0 + SH + 0.12, Z1 - 0.09), (SW + 0.35, 0.2, 0.16), 'steel')     # case
sc.tube([(-SW / 2 - 0.02, SY0 - 0.02, Z1 - 0.03), (SW / 2 + 0.02, SY0 - 0.02, Z1 - 0.03)], 0.018, 10, 'steel', caps=True)
for s in (-1, 1):
    sc.box((s * (SW / 2 + 0.2), SY0 + SH + 0.12, Z1 - 0.05), (0.05, 0.3, 0.1), 'steel')
sc_ob = sc.finalize(bevel=0.003)
layout['screen'] = [0.0, SY0 + SH / 2, Z1 - 0.026, SW, SH]

# ───────────────────────────── pendants (RLM) ─────────────────────
pn = Mesh('pendant_shades')
cords = Mesh('pendant_cords')
SHADE_Y = 4.62
for zt in LAMP_Z:
    for xl in LAMP_X:
        # outside: enamel green; rim roll; inside white (separate lathe, normals inward)
        prof = [(0.035, 0.2), (0.06, 0.197), (0.1, 0.185), (0.14, 0.16), (0.175, 0.125), (0.203, 0.085), (0.222, 0.048), (0.234, 0.018), (0.24, 0.0)]
        pn.lathe(prof, 48, (xl, SHADE_Y - 0.2, zt), 'enamel')
        pin = [(p[0] - 0.006, p[1] - 0.004) for p in prof][::-1]
        pn.lathe(pin, 48, (xl, SHADE_Y - 0.2, zt), 'enamel_in')
        pn.lathe([(0.234, 0.0), (0.246, -0.004), (0.25, 0.004), (0.24, 0.0)], 48, (xl, SHADE_Y - 0.2, zt), 'enamel')
        # socket housing + canopy
        pn.lathe([(0.0, 0.0), (0.032, 0.0), (0.034, 0.09), (0.02, 0.12), (0.0, 0.12)], 16,
                 (xl, SHADE_Y - 0.03, zt), 'steel', cap_bot=True)
        pn.lathe([(0.0, 0.0), (0.06, 0.0), (0.05, 0.03), (0.0, 0.03)], 16, (xl, 5.72, zt), 'steel')
        cords.tube([(xl, SHADE_Y + 0.09, zt), (xl, 5.72, zt)], 0.005, 6, 'cord')
        layout['lamps'].append([xl, SHADE_Y - 0.12, zt])
pn_ob = pn.finalize(weighted=True)
cd_ob = cords.finalize(weighted=False)
# stage spots clamped to the truss over the stage
ss = Mesh('stage_spots')
layout['stage_spots'] = []
for xs in (-2.1, 2.1):
    p = Vector((xs, 5.55, 7.8))
    tgt = Vector((xs * 0.2, 1.0, 8.2))
    d = (tgt - p).normalized()
    ss.tube([tuple(p - d * 0.14), tuple(p + d * 0.2)], 0.09, 20, 'steel', caps=True)
    ss.tube([tuple(p + d * 0.2), tuple(p + d * 0.24)], 0.1, 20, 'steel', caps=True)
    ss.box((xs, 5.72, 7.8), (0.06, 0.18, 0.06), 'steel')
    layout['stage_spots'].append([p.x, p.y, p.z, tgt.x, tgt.y, tgt.z])
ss_ob = ss.finalize(bevel=0.003)

# ───────────────────────────── conduit + boxes ────────────────────
cn = Mesh('conduit')
for sign in (-1, 1):
    xw = (X1 if sign > 0 else X0) - sign * 0.035
    cn.tube([(xw, 2.55, Z0 + 0.4), (xw, 2.55, Z1 - 0.5)], 0.013, 8, 'galv')
    for z in TRUSS_Z:
        cn.box((xw - sign * 0.26, 2.55, z), (0.06, 0.12, 0.12), 'galv')
        cn.tube([(xw - sign * 0.26, 2.61, z), (xw - sign * 0.26, 5.6, z)], 0.012, 8, 'galv')
# breaker panel by the pedestrian door
cn.box((PDOOR['x'] + 1.2, 1.55, Z0 + 0.07), (0.5, 0.75, 0.12), 'steel')
cn.tube([(PDOOR['x'] + 1.2, 1.93, Z0 + 0.06), (PDOOR['x'] + 1.2, 2.55, Z0 + 0.06), (X1 - 0.05, 2.55, Z0 + 0.06)], 0.013, 8, 'galv')
cn_ob = cn.finalize(bevel=0.002)

glass_ob = glass.finalize(weighted=False)

# brick masses: bevel after booleans; walls get chipped arrises
for ob in walls:
    m = ob.modifiers.new('bevel', 'BEVEL')
    m.width = 0.015
    m.segments = 2
    m.limit_method = 'ANGLE'
    m.angle_limit = math.radians(40)
    m.use_clamp_overlap = True
    m2 = ob.modifiers.new('wn', 'WEIGHTED_NORMAL')
    m2.keep_sharp = True
bevel_deck = deck_ob.modifiers.new('wn', 'WEIGHTED_NORMAL')

layout['mannequins'] = {'opus3': [-7.55, 0, 8.7], 'sonnet4': [7.55, 0, 8.7], 'opus4': [-7.55, 0, -10.95],
                        'haiku3': [7.2, 0, -10.95]}
layout['projector'] = [0.0, MEZZ_Y + 1.25, MEZZ_Z - 0.05]
os.makedirs(ASSETS, exist_ok=True)
json.dump(layout, open(ASSETS + '/funeral_layout.json', 'w'), indent=1)
export_glb(ASSETS + '/warehouse.glb')

if 'preview' in sys.argv:
    out = ASSETS + '/../probes/wh_prev.png'
    preview(out, [((0.0, 2.0, 9.0), (0.0, 3.0, -12.0), 60), ((-8.0, 5.0, 9.0), (4.0, 2.0, -8.0), 55),
                  ((6.0, 1.6, -2.0), (-6.0, 5.0, -6.0), 60), ((0.0, 4.0, -8.0), (0.0, 3.0, 10.0), 60)])
