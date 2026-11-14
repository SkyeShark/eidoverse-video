"""three-bvh-csg's seven operations in Blender (eidoblend.course.csg), the HOLLOW ones on open and closed shells.

    cd <main checkout> && bash run_blender.sh <worktree>/blender/tests/terrain_extras/test_csg.py [--no-render]
    (renders are GPU jobs: on a shared machine queue them with EIDO_GPU_WRAP, blender/tests/_where.py)

Checks (PASS/FAIL, numeric):
  volumes  a 1 m box and a 0.75 m sphere overlapping: ADDITION = A + B - (A n B), SUBTRACTION = A - (A n B),
           REVERSE_SUBTRACTION = B - (A n B), DIFFERENCE = A + B - 2 (A n B), to 0.5 %
  hollow   HOLLOW_SUBTRACTION keeps only A's surface outside B: no face centre inside B, every face on A's own
           surface, an open boundary where B cut; HOLLOW_INTERSECTION keeps A's surface inside B; both work on an
           OPEN A (a terrain-like sheet), which the solid operations cannot take
  groups   use_groups=True keeps each input's material on its faces, False gives A's one material
  live     live=True: the cut follows a keyed cutter (frame 1 and frame 24 differ where it moved)
Renders (960 x 540, each result in its own labelled slot), joined on csg_board.png: csg_ops_a / csg_ops_b (the inputs
and the five solid operations), csg_difference_open (DIFFERENCE with its front half taken off by HOLLOW_SUBTRACTION:
the two touching solids' inner faces), csg_hollowed (the hollowed solid: a sphere's skin minus a box, open, looked
into, a pebble on its floor), csg_hollow_vs_solid (the capped SUBTRACTION beside the HOLLOW pair), csg_open_sheet (an
open sheet holed, and its piece inside the ball), csg_live_f01 / csg_live_f24 (live=True following a keyed cutter).
"""
import math
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parents[0] / 'terrain'))
sys.path.insert(0, str(HERE.parents[1]))
import _fixture as F  # noqa: E402

import bmesh  # noqa: E402
import bpy  # noqa: E402
import numpy as np  # noqa: E402
from mathutils import Vector  # noqa: E402
from mathutils.bvhtree import BVHTree  # noqa: E402
from eidoblend.course import csg  # noqa: E402

OUT = HERE / 'out'
OUT.mkdir(exist_ok=True)
RENDER = '--no-render' not in F.args()
FAILS = []


def check(ok, msg):
    print(('PASS ' if ok else 'FAIL ') + msg)
    if not ok:
        FAILS.append(msg)


F.clean_scene()
F.render_settings(960, 540, 16)
F.test_daylight(sun_elevation=38, sun_azimuth=215)
coll = bpy.context.scene.collection


def mat(name, rgb, rough=0.5, metal=0.0, two_sided=True):
    m = bpy.data.materials.new(name)
    m.use_nodes = True
    b = m.node_tree.nodes['Principled BSDF']
    b.inputs['Base Color'].default_value = tuple(rgb) + (1.0,)
    b.inputs['Roughness'].default_value = rough
    b.inputs['Metallic'].default_value = metal
    m.use_backface_culling = not two_sided
    return m


RED = mat('csg_a', (0.55, 0.12, 0.08), 0.45)
BLUE = mat('csg_b', (0.08, 0.2, 0.55), 0.35, 0.2)
GREY = mat('csg_sheet', (0.4, 0.38, 0.33), 0.8)


def mesh_obj(name, bm, material, loc=(0, 0, 0)):
    me = bpy.data.meshes.new(name)
    bm.to_mesh(me)
    bm.free()
    me.materials.append(material)
    ob = bpy.data.objects.new(name, me)
    ob.location = loc
    coll.objects.link(ob)
    return ob


def box(name, size, loc, material):
    bm = bmesh.new()
    bmesh.ops.create_cube(bm, size=size)
    return mesh_obj(name, bm, material, loc)


def ball(name, r, loc, material, seg=48, rings=24):
    bm = bmesh.new()
    bmesh.ops.create_uvsphere(bm, u_segments=seg, v_segments=rings, radius=r)
    for f in bm.faces:
        f.smooth = True
    return mesh_obj(name, bm, material, loc)


def sheet(name, size, loc, material, n=48):
    """an OPEN wavy sheet (no inside): what only the hollow operations take"""
    bm = bmesh.new()
    vs = [[bm.verts.new(((i / n - 0.5) * size, (j / n - 0.5) * size,
                         0.12 * math.sin(i / n * 7) * math.cos(j / n * 5))) for j in range(n + 1)] for i in range(n + 1)]
    for i in range(n):
        for j in range(n):
            f = bm.faces.new((vs[i][j], vs[i + 1][j], vs[i + 1][j + 1], vs[i][j + 1]))
            f.smooth = True
    return mesh_obj(name, bm, material, loc)


def faces_world(ob):
    me = ob.data
    M = ob.matrix_world
    return [(M @ p.center, p.material_index) for p in me.polygons]


_DIRS = [Vector((1.0, 0.0137, 0.0071)).normalized(), Vector((0.31, 0.77, -0.55)).normalized(),
         Vector((-0.2, -0.4, 0.89)).normalized()]


def inside(obj, p):
    """point-in-closed-mesh by ray parity, the majority of three directions (one ray can graze an edge)"""
    bvh = BVHTree.FromObject(obj, bpy.context.evaluated_depsgraph_get())
    q = obj.matrix_world.inverted() @ p
    votes = 0
    for d in _DIRS:
        n, o = 0, q.copy()
        for _ in range(64):
            hit = bvh.ray_cast(o, d)
            if hit[0] is None:
                break
            n += 1
            o = hit[0] + d * 1e-6
        votes += n % 2
    return votes >= 2


def open_edges(ob):
    bm = bmesh.new()
    bm.from_mesh(ob.data)
    k = sum(1 for e in bm.edges if e.is_boundary)
    bm.free()
    return k


# ----------------------------------------------------------------------------------- the solid operations ---
x0 = -6.3
A = box('A_box', 1.0, (x0, 0, 0.5), RED)
B = ball('B_ball', 0.75, (x0 + 0.55, -0.35, 0.85), BLUE)
bpy.context.view_layer.update()
va, vb = csg.compute_mesh_volume(A), csg.compute_mesh_volume(B)
inter = csg.evaluate(A, B, csg.INTERSECTION, hide_b=False, name='r_intersection')
vi = csg.compute_mesh_volume(inter)
want = {csg.ADDITION: va + vb - vi, csg.SUBTRACTION: va - vi, csg.REVERSE_SUBTRACTION: vb - vi,
        csg.DIFFERENCE: va + vb - 2 * vi}
results = {csg.INTERSECTION: inter}
for op in (csg.ADDITION, csg.SUBTRACTION, csg.REVERSE_SUBTRACTION, csg.DIFFERENCE):
    r = csg.evaluate(A, B, op, hide_b=False, name='r_' + op.lower())
    results[op] = r
    v = csg.compute_mesh_volume(r)
    if op == csg.DIFFERENCE:
        # A xor B's boundary is two touching solids: their volumes add
        v = csg.compute_mesh_volume(csg.evaluate(A, B, csg.SUBTRACTION, hide_b=False, name='_d1')) + \
            csg.compute_mesh_volume(csg.evaluate(A, B, csg.REVERSE_SUBTRACTION, hide_b=False, name='_d2'))
    check(abs(v - want[op]) <= 0.005 * want[op], '%-20s volume %.4f m^3, expected %.4f (A %.4f, B %.4f, A n B %.4f)'
          % (op, v, want[op], va, vb, vi))
for nm in ('_d1', '_d2'):
    bpy.data.objects.remove(bpy.data.objects[nm])
# groups: two materials kept, or A's one
mats_kept = {m.name for m in results[csg.ADDITION].data.materials if m}
one = csg.Evaluator(use_groups=False).evaluate(A, B, csg.ADDITION, name='r_union_onemat')
used = {one.data.materials[p.material_index].name for p in one.data.polygons}
check({'csg_a', 'csg_b'} <= mats_kept and used == {'csg_a'},
      'use_groups=True keeps both materials (%s); False gives A\'s alone (%s)' % (sorted(mats_kept), sorted(used)))
check([m.name for m in A.data.materials] == ['csg_a'],
      'evaluate leaves A\'s mesh as it was: its material slots %s (three-bvh-csg never touches a brush)'
      % [m.name for m in A.data.materials])
bpy.data.objects.remove(one)
# chaining: (A - B) n a small box
small = box('C_small', 0.6, (x0 - 0.2, 0.0, 0.5), GREY)
chain = csg.evaluate(results[csg.SUBTRACTION], small, csg.INTERSECTION, name='r_chain')
check(csg.compute_mesh_volume(chain) < csg.compute_mesh_volume(results[csg.SUBTRACTION]),
      'chaining: a result feeds the next operation as a brush (%.4f m^3)' % csg.compute_mesh_volume(chain))
bpy.data.objects.remove(chain)
bpy.data.objects.remove(small)

# ------------------------------------------------------------------------------------- the hollow ones ---
HX = 17.0                                                             # the hollow group's slot (x)
S = ball('S_shell', 0.9, (HX, 0.0, 0.95), RED, 64, 32)               # a closed skin
CUT = box('cut_box', 1.0, (HX + 0.25, -0.75, 1.3), BLUE)
CUT.rotation_euler = (0.3, 0.2, 0.5)
bpy.context.view_layer.update()


def outside_by(cutter, obj, want_inside):
    """the worst distance by which a VERTEX of obj sits on the wrong side of the cutter's surface (a boolean's
    n-gons can be concave, so their centres prove nothing; their corners do)"""
    bvh = BVHTree.FromObject(cutter, bpy.context.evaluated_depsgraph_get())
    inv = cutter.matrix_world.inverted()
    worst = 0.0
    for v in obj.data.vertices:
        p = obj.matrix_world @ v.co
        if inside(cutter, p) != want_inside:
            worst = max(worst, bvh.find_nearest(inv @ p)[3])
    return worst


hs = csg.evaluate(S, CUT, csg.HOLLOW_SUBTRACTION, name='hollowed_sphere')
fw = faces_world(hs)
w1 = outside_by(CUT, hs, False)
on_a = max(abs((c - S.location).length - 0.9) for c, _ in fw)
check(w1 < 1e-4 and on_a < 0.01 and open_edges(hs) > 0 and len(hs.data.polygons) < len(S.data.polygons) + 200,
      'HOLLOW_SUBTRACTION: %d faces, no corner inside the cutter (worst %.1g m), all on the skin (%.4f m off), an '
      'open cut (%d boundary edges), no cap' % (len(fw), w1, on_a, open_edges(hs)))
hi = csg.evaluate(S, CUT, csg.HOLLOW_INTERSECTION, name='sphere_cap')
fw2 = faces_world(hi)
on_a2 = max(abs((c - S.location).length - 0.9) for c, _ in fw2)
w2 = outside_by(CUT, hi, True)
check(len(fw2) > 0 and w2 < 1e-4 and on_a2 < 0.01,
      'HOLLOW_INTERSECTION: %d faces, every corner inside the cutter or on its face (worst %.1g m), all on the skin'
      % (len(fw2), w2))
hi.location.x += 2.3
# an OPEN sheet: only the hollow operations take it
SH = sheet('S_sheet', 2.2, (HX + 5.2, 0.4, 0.6), GREY)
BALL = ball('cut_ball', 0.7, (HX + 5.3, 0.3, 0.75), BLUE)
bpy.context.view_layer.update()
cap = csg.evaluate(SH, BALL, csg.HOLLOW_INTERSECTION, name='sheet_in_ball')
fw3 = faces_world(cap)
# the ball is a 48 x 24 polygon: its facets sit up to r (1 - cos(pi / 48)) = 1.5 mm inside the true sphere
facet = 0.7 * (1 - math.cos(math.pi / 48)) + 1e-4
d3 = max((c - BALL.location).length for c, _ in fw3) if fw3 else 9
check(len(fw3) > 0 and d3 < 0.7 + 1e-4,
      'HOLLOW_INTERSECTION on an open sheet: %d faces, all inside the ball (farthest %.4f m from its centre)'
      % (len(fw3), d3))
holed = csg.evaluate(SH, BALL, csg.HOLLOW_SUBTRACTION, name='sheet_holed')
fw4 = faces_world(holed)
w4 = outside_by(BALL, holed, False)
check(len(fw4) > 0 and w4 < 1e-4 and len(fw3) + len(fw4) >= len(SH.data.polygons),
      'HOLLOW_SUBTRACTION on an open sheet: %d faces, a hole where the ball was (no corner inside it: worst %.1g m), '
      'no cap; with the intersection they cover the sheet' % (len(fw4), w4))
cap.location.z += 1.2
cap.location.x += 0.0
# an open cutter has no inside (three-bvh-csg's result is undefined there too): the call says so
import contextlib  # noqa: E402
import io  # noqa: E402
buf = io.StringIO()
with contextlib.redirect_stdout(buf):
    junk = csg.evaluate(BALL, SH, csg.SUBTRACTION, hide_b=False, name='_open_cutter')
bpy.data.objects.remove(junk)
check(csg.open_edges(SH) > 0 and 'is open' in buf.getvalue() and csg.open_edges(BALL) == 0,
      'an open cutter is named in a warning (%d boundary edges on the sheet; the ball closed)' % csg.open_edges(SH))
SH.hide_render = True

# --------------------------------------------------------------------------------------------- live ---
LX = HX + 10.0                                                        # the live cut's slot
LA = ball('live_skin', 0.5, (LX, 0.0, 0.6), RED, 48, 24)
LB = box('live_cutter', 0.5, (LX - 0.6, -0.2, 0.8), BLUE)
LB.keyframe_insert('location', frame=1)
LB.location.x = LX + 0.6
LB.keyframe_insert('location', frame=24)
csg.evaluate(LA, LB, csg.HOLLOW_SUBTRACTION, live=True)
sc = bpy.context.scene


def eval_faces(ob):
    dg = bpy.context.evaluated_depsgraph_get()
    ev = ob.evaluated_get(dg)
    me = ev.to_mesh()
    c = np.array([tuple(p.center) for p in me.polygons])
    ev.to_mesh_clear()
    return c


sc.frame_set(1)
f1 = eval_faces(LA)
sc.frame_set(24)
f24 = eval_faces(LA)
check(LA.modifiers and LA.modifiers[-1].type == 'NODES' and (len(f1) != len(f24) or np.abs(f1 - f24).max() > 1e-4),
      'live=True: the cut follows the keyed cutter (%d faces at frame 1, %d at frame 24)' % (len(f1), len(f24)))
sc.frame_set(1)

# --------------------------------------------------------------------------------------------- renders ---
# one slot per result along x, 3 m apart, each labelled on the floor in front of it; the inputs (A and B as given)
# keep slot 0. The originals of the hollow group (S, the sheet) stay hidden: only results render.
PITCH = 3.0
order = [csg.ADDITION, csg.SUBTRACTION, csg.REVERSE_SUBTRACTION, csg.INTERSECTION, csg.DIFFERENCE]
for i, op in enumerate(order):
    results[op].location.x = x0 + (i + 1) * PITCH
B.hide_render = False
B.display_type = 'TEXTURED'
A.hide_render = False
S.hide_render = True
# DIFFERENCE cut open: its front half taken off with HOLLOW_SUBTRACTION (no cap), so the two touching solids show
# their inner faces: the box's spherical dent and the ball's bitten corner
diff2 = csg.evaluate(A, B, csg.DIFFERENCE, hide_b=False, name='r_difference_open_src')
diff2.location.x = x0 + 6 * PITCH
halfbox = box('half_space', 4.0, (x0 + 6 * PITCH, -2.0 - 0.35, 0.5), GREY)
bpy.context.view_layer.update()
cutaway = csg.evaluate(diff2, halfbox, csg.HOLLOW_SUBTRACTION, name='r_difference_cutaway')
diff2.hide_render = True
check(open_edges(cutaway) > 0 and len(cutaway.data.polygons) > 0,
      'DIFFERENCE cut open with HOLLOW_SUBTRACTION: %d faces, %d open edges' % (len(cutaway.data.polygons),
                                                                             open_edges(cutaway)))
# a pebble resting inside the hollowed sphere (tangent to its inner bottom), seen through the window
GOLD = mat('pebble', (0.8, 0.55, 0.15), 0.3, 0.9)
pebble = ball('pebble', 0.18, (HX, 0.0, 0.95 - 0.9 + 0.18 + 0.002), GOLD, 32, 16)
# the solid SUBTRACTION of the same box from the same sphere, beside the hollow one: capped, the inside shut
solid_cut = csg.evaluate(S, CUT, csg.SUBTRACTION, name='sphere_minus_box_solid')
solid_cut.location.x = HX - 2.5
LB.display_type = 'TEXTURED'
bpy.ops.mesh.primitive_plane_add(size=90, location=(HX, 0, 0))
floor = bpy.context.active_object
floor.data.materials.append(mat('floor', (0.18, 0.18, 0.18), 0.9))
LBL = mat('label', (0.9, 0.9, 0.85), 0.6)


def label(text, x, y=-1.55, size=0.2):
    cu = bpy.data.curves.new('lbl', 'FONT')
    cu.body = text
    cu.size = size
    cu.align_x = 'CENTER'
    ob = bpy.data.objects.new('lbl_' + text[:16], cu)
    ob.location = (x, y, 0.003)
    cu.materials.append(LBL)
    coll.objects.link(ob)
    return ob


label('inputs: A (box) and B (ball)', x0 + 0.4)
for i, op in enumerate(order):
    label(op, x0 + (i + 1) * PITCH + 0.4)
label('DIFFERENCE, front half cut away', x0 + 6 * PITCH + 0.4)
label('SUBTRACTION (solid)', HX - 2.5, y=-1.35)
label('HOLLOW_SUBTRACTION', HX, y=-1.35)
label('HOLLOW_INTERSECTION', HX + 2.3, y=-1.35)
label('open sheet: HOLLOW_SUB / HOLLOW_INT', HX + 5.2, y=-1.35)
if RENDER:
    shots = []

    def shot(tag, text, loc, look, lens, frame=1):
        sc.frame_set(frame)
        cam = F.camera(tag, loc, look, lens=lens)
        p = OUT / ('csg_%s.png' % tag)
        F.render(cam, p)
        shots.append((p, text))

    cx = x0 + PITCH + 0.4
    shot('ops_a', 'the inputs, ADDITION, SUBTRACTION', (cx, -7.6, 3.4), (cx, 0.0, 0.45), 30)
    cx = x0 + 4 * PITCH + 0.4
    shot('ops_b', 'REVERSE_SUBTRACTION, INTERSECTION, DIFFERENCE', (cx, -7.6, 3.4), (cx, 0.0, 0.45), 30)
    cx = x0 + 6 * PITCH + 0.4
    shot('difference_open', 'DIFFERENCE cut open: A - B and B - A touching', (cx - 1.4, -3.4, 2.3),
         (cx, 0.2, 0.55), 38)
    shot('hollowed', 'HOLLOW_SUBTRACTION: the sphere\'s skin with a window, no cap: the hollow inside, a pebble on '
         'its floor', (HX + 0.9, -3.2, 2.5), (HX + 0.05, 0.0, 0.8), 40)
    shot('hollow_vs_solid', 'SUBTRACTION (capped) | HOLLOW_SUBTRACTION | HOLLOW_INTERSECTION (the window\'s skin)',
         (HX + 0.2, -6.6, 3.2), (HX + 0.1, 0.0, 0.7), 32)
    shot('open_sheet', 'an OPEN sheet: HOLLOW_SUBTRACTION (holed) and HOLLOW_INTERSECTION (its piece in the ball, '
         'raised)',
         (HX + 5.2, -4.8, 3.4), (HX + 5.2, 0.3, 1.0), 32)
    shot('live_f01', 'live=True, frame 1: the window where the keyed (hidden) cutter starts, left',
         (LX, -3.0, 1.9), (LX, 0.0, 0.6), 40, 1)
    shot('live_f24', 'live=True, frame 24: the window followed the cutter right', (LX, -3.0, 1.9), (LX, 0.0, 0.6),
         40, 24)
    sc.frame_set(1)
    for p, _t in shots:
        check(p.exists(), 'rendered %s' % p.name)
    try:
        from PIL import Image, ImageDraw
        cols, tw, th = 2, 960, 540
        rows = (len(shots) + cols - 1) // cols
        Sh = Image.new('RGB', (cols * tw, rows * (th + 24)), (14, 16, 20))
        dr = ImageDraw.Draw(Sh)
        for i, (p, t) in enumerate(shots):
            r, c = divmod(i, cols)
            if p.exists():
                Sh.paste(Image.open(p).convert('RGB'), (c * tw, r * (th + 24)))
            dr.text((c * tw + 8, r * (th + 24) + th + 5), t, fill=(225, 225, 225))
        Sh.save(OUT / 'csg_board.png')
    except ImportError as ex:
        print('no sheet (%s)' % ex)
print('%s: %d failing' % ('FAIL' if FAILS else 'PASS', len(FAILS)))
