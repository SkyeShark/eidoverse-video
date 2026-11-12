"""Probe: a book built from data opened to a chosen sweep, with its own case shape and trim cloth (make_book's spec path:
angle, page_angle, board_th, lip, round, u_joint, cover['trim']; makeBookFromSpec's input and options).

    cd <main checkout> && bash run_blender.sh <worktree>/blender/tests/media/test_book_lectern.py -- --no-render
    cd <main checkout> && HEAVY_VRAM_GB=4 bash work/claude_body/work/tmp/heavy.sh 12 bash run_blender.sh \
        <worktree>/blender/tests/media/test_book_lectern.py

Three books from the template covers and six spreads, open throughout, a leaf turned over frames 14..30:
  flat      the defaults (angle 180, page_angle 179)
  lectern   angle 110, page_angle 179, board_th 3.5 mm, lip 6.2 mm, round 3.1 mm, u_joint 0.452, a fabric trim image
  standing  angle 110, page_angle 150, a '#c9a227' trim
Checks (PASS/FAIL lines): the options reach the rig (book.json's rig spec and the rig's metrics); the boards' sweep
measured off the cached case at frame 40, in the plane across the spine (the angle between the back and front boards'
headings: 180 lies flat, 110 is a cradle); the landed leaf's angle off the front cover, page_angle - 180 as book_core
fans it; the board thickness measured off the case (outer cloth to lining); the trim's image and hex.
The render: the lectern book on a wooden cradle fitted to its boards, frames 10 (open), 22 (a leaf mid-turn) and
40 (landed) -> out/book_lectern_f010.png, _f022.png, _f040.png
"""
import math
import sys
from pathlib import Path

import bpy
import numpy as np
from mathutils import Matrix, Vector

sys.path.insert(0, str(Path(__file__).resolve().parent))
import _stage as S  # noqa: E402
from eidoblend.media import book, raster  # noqa: E402

OUT = S.OUT
T = S.ASSETS / 'book_template'
SPREADS = sorted((S.ASSETS / 'book_spreads').glob('*.jpg'))[:6]
COVER = {'front': T / 'front.png', 'back': T / 'back.png', 'spine': T / 'spine.png', 'color': '#1e4d2b'}
SHAPE = dict(board_th=0.0035, lip=0.0062, round=0.0031, u_joint=0.452)
FABRIC = S.cached('textures', 'Fabric031_1k')
F_LANDED = 40
FAILS = []


def check(ok, what):
    print(f"{'PASS' if ok else 'FAIL'} {what}", flush=True)
    if not ok:
        FAILS.append(what)


sc = S.fresh_scene(frames=(1, 48))
sc.eevee.shadow_ray_count = 4
sc.eevee.shadow_step_count = 12
plan = book.schedule((1, 48), open=1.0, turns=[(14, 30)])


def build(tag, trim=None, **kw):
    cover = dict(COVER, **({'trim': trim} if trim else {}))
    return book.make_book(OUT / f'book_lectern_{tag}', plan, size=(0.15, 0.222, 0.026), cover=cover, spreads=SPREADS,
                          lining=T / 'lining.png', wrap_res=2048, name=f'book_{tag}', **kw)


flat = build('flat')
lect = build('lectern', angle=110, page_angle=179, trim=FABRIC / 'Fabric031_Color.jpg', **SHAPE)
stand = build('standing', angle=110, page_angle=150, trim='#c9a227')
for b in (flat, stand):
    b.root.location.x += 0.6 if b is flat else -0.6                  # side by side, out of the lectern's frame

# ---- the options reach the rig
want = {'angle': 110, 'pageAngle': 179, 'boardTh': 0.0035, 'lip': 0.0062, 'round': 0.0031, 'uJoint': 0.452}
got = {k: lect.info['rig'].get(k) for k in want}
check(all(abs(got[k] - v) < 1e-9 for k, v in want.items()), f'the lectern book\'s spec reached the rig: {got}')
m = lect.metrics
check(abs(m['BOARD_TH'] - 0.0035) < 1e-9 and abs(m['LIP'] - 0.0062) < 1e-9 and abs(m['SPINE_D'] - 0.0031) < 1e-9
      and abs(m['U_JOINT'] - 0.452) < 1e-9, f"the rig's metrics: BOARD_TH {m['BOARD_TH']}, LIP {m['LIP']}, SPINE_D "
                                             f"{m['SPINE_D']}, U_JOINT {m['U_JOINT']}")
fr = flat.info['rig']
check(fr['angle'] == 180 and fr['pageAngle'] == 179 and abs(fr['boardTh'] - 0.0025) < 1e-9
      and abs(fr['lip'] - max(0.003, 0.026 * 0.21)) < 1e-9 and abs(fr['round'] - max(0.0015, 0.026 * 0.09)) < 1e-9,
      f"the flat book keeps makeBookFromSpec's defaults: angle {fr['angle']}, pageAngle {fr['pageAngle']}, boardTh "
      f"{fr['boardTh']}, lip {fr['lip']:.5f}, round {fr['round']:.5f}")


# ---- the measured sweep and leaf angle
def evaluated(obj, f):
    sc.frame_set(f)
    dg = bpy.context.evaluated_depsgraph_get()
    ev = obj.evaluated_get(dg)
    me = ev.to_mesh()
    co = np.empty(len(me.vertices) * 3)
    me.vertices.foreach_get('co', co)
    out = {'co': co.reshape(-1, 3)}
    if obj is not None and me.uv_layers.get('UVMap') is not None and len(me.polygons):
        nl = len(me.loops)
        vi = np.empty(nl, np.int64)
        me.loops.foreach_get('vertex_index', vi)
        uv = np.empty(nl * 2)
        me.uv_layers['UVMap'].data.foreach_get('uv', uv)
        np_ = len(me.polygons)
        mi, ls, lt = (np.empty(np_, np.int64) for _ in range(3))
        me.polygons.foreach_get('material_index', mi)
        me.polygons.foreach_get('loop_start', ls)
        me.polygons.foreach_get('loop_total', lt)
        out.update(vi=vi, uv=uv.reshape(-1, 2), mi=mi, ls=ls, lt=lt)
    ev.to_mesh_clear()
    return out


def loops_of(e, mat):
    return np.concatenate([np.arange(s, s + t) for s, t, m in zip(e['ls'], e['lt'], e['mi']) if m == mat])


def shape_at(b, f):
    """The case at frame f, in the plane across the spine: the spine axis (case_frame's Z), the middle of the spine,
    each board's outer cloth (picked by the wrap's U: back | spine | front) and its heading (spine -> fore-edge)."""
    st = b.frame_state(f)
    cf = Matrix(st['caseFrame'])
    axis = np.array(cf.col[2][:3])
    axis /= np.linalg.norm(axis)
    origin = np.array(cf.col[3][:3])                                   # case_frame sits on the back fore-edge
    e = evaluated(b.parts['case'], f)
    cl = loops_of(e, 0)
    u, vi = e['uv'][cl, 0], e['vi'][cl]
    uj = b.metrics['U_JOINT']
    ends = [e['co'][np.unique(vi[u < 0.75 * uj])], e['co'][np.unique(vi[u > 1 - 0.75 * uj])]]
    if np.linalg.norm(ends[0].mean(0) - origin) > np.linalg.norm(ends[1].mean(0) - origin):
        ends.reverse()                                                 # [back, front]: the back holds the origin
    spine_c = e['co'][np.unique(vi[np.abs(u - 0.5) < 0.03])].mean(0)

    def heading(pts):
        p = pts - spine_c
        p = p - np.outer(p @ axis, axis)
        c = p.mean(0)
        d = np.linalg.svd(p - c)[2][0]
        return d if d @ c > 0 else -d
    lining = e['co'][np.unique(e['vi'][loops_of(e, 1)])]
    return {'axis': axis, 'spine': spine_c, 'back': ends[0], 'front': ends[1], 'd_back': heading(ends[0]),
            'd_front': heading(ends[1]), 'heading': heading, 'lining': lining, 'case': e['co']}


def angle(a, b):
    return math.degrees(math.acos(max(-1.0, min(1.0, float(a @ b)))))


def leaf_heading(b, f, sh):
    """The landed leaf (window 0, left of the opening) away from the gutter: its outer 60 %."""
    pts = evaluated(b.parts['window0'], f)['co']
    p = pts - sh['spine']
    r = np.linalg.norm(p - np.outer(p @ sh['axis'], sh['axis']), axis=1)
    return sh['heading'](pts[r > 0.4 * r.max()])


def signed(sh):
    """The turn from the back board's heading to the front's about the spine axis, degrees in (-180, 180]."""
    d_b, d_f = sh['d_back'], sh['d_front']
    return math.degrees(math.atan2(float(np.cross(d_b, d_f) @ sh['axis']), float(d_b @ d_f)))


meas, shapes = {}, {}
for tag, b, ang, pang in (('flat', flat, 180, 179), ('lectern', lect, 110, 179), ('standing', stand, 110, 150)):
    sh = shapes[tag] = shape_at(b, F_LANDED)
    vis = b.frame_state(F_LANDED)['slots'][0]['visible']
    off = angle(leaf_heading(b, F_LANDED, sh), sh['d_front']) if vis else float('nan')
    meas[tag] = off
    check(vis and abs(off - (180 - pang)) < 2.5, f'{tag}: the landed leaf lies {off:.2f} deg off the front cover '
                                                 f'(page_angle {pang}: {180 - pang} deg, plus the fan\'s 1.2 at most)')
    if tag in ('flat', 'lectern'):
        n = np.linalg.svd(sh['back'] - sh['back'].mean(0))[2][2]       # the back board's normal
        near = sh['lining'][np.abs((sh['lining'] - sh['back'].mean(0)) @ sh['d_back']) < 0.04]
        meas[tag + '_th'] = float(np.median(np.abs((near - sh['back'].mean(0)) @ n)))
# the sweep in the opening sense (the lectern's is under 180, so its sign is the sense), so past 180 reads past 180.
# book_core lets the front board fall past the sweep by its prop, asin(groove height / hinge radius): the drop that
# lands a flat-open cover's edge on the desk; it depends on the case, not on the angle
sense = 1.0 if signed(shapes['lectern']) > 0 else -1.0
sweep = {t: (sense * signed(s)) % 360.0 for t, s in shapes.items()}
prop = {t: sweep[t] - a for t, a in (('flat', 180), ('lectern', 110), ('standing', 110))}
print('[book_lectern] sweeps', {t: round(v, 2) for t, v in sweep.items()}, 'props', {t: round(v, 2)
                                                                                      for t, v in prop.items()})
check(abs((sweep['standing'] - sweep['flat']) - (110 - 180)) < 0.05,
      f'angle moves the cover by what it asks on the same case: {sweep["flat"]:.2f} deg at 180, '
      f'{sweep["standing"]:.2f} at 110 ({sweep["standing"] - sweep["flat"]:+.2f})')
check(all(0.0 < p < 10.0 for p in prop.values()) and abs(prop['flat'] - prop['standing']) < 0.05,
      f'each opens to angle + the rig\'s prop: flat {prop["flat"]:.2f}, standing {prop["standing"]:.2f} (the same '
      f'case), lectern {prop["lectern"]:.2f} (its own board, lip and round)')
check(meas['lectern_th'] - meas['flat_th'] > 0.0007, f'board_th reaches the case: the back board measures '
                                                    f'{meas["flat_th"] * 1000:.2f} mm cloth to lining at the default '
                                                    f'2.5 mm, {meas["lectern_th"] * 1000:.2f} mm at 3.5 mm')

# ---- the trim: an image, a hex


def trim_image(b):
    return next((n.image for n in b.materials['trim'].node_tree.nodes if n.bl_idname == 'ShaderNodeTexImage'), None)


ti = trim_image(lect)
check(ti is not None and 'Fabric031' in ti.name, f'cover trim image on the rims and turn-ins: {ti.name if ti else None}')
bc = stand.materials['trim'].node_tree.nodes['Principled BSDF'].inputs['Base Color'].default_value[:3]
wl = [float(raster.srgb_to_linear(c / 255)) for c in raster.color('#c9a227')[:3]]
check(trim_image(stand) is None and np.allclose(bc, wl, atol=1e-5), f"cover trim '#c9a227': base colour "
                                                                     f"{np.round(bc, 4).tolist()} (linear)")
fl = flat.materials['trim'].node_tree.nodes['Principled BSDF'].inputs['Base Color'].default_value[:3]
wf = [float(raster.srgb_to_linear(c / 255)) for c in raster.color('#1e4d2b')[:3]]
check(trim_image(flat) is None and np.allclose(fl, wf, atol=1e-5), 'no trim given: the flat cover colour, as book.js')

if '--no-render' in sys.argv:
    print(f'[test_book_lectern] checks only: {"ALL OK" if not FAILS else f"{len(FAILS)} FAILED"}', flush=True)
    raise SystemExit(0)

# ---- the render: the lectern book on a wooden cradle fitted to its boards
for b in (flat, stand):
    for o in [b.root, *b.root.children_recursive]:
        o.hide_render = True
sh = shape_at(lect, 10)
bis = Vector(sh['d_back'] + sh['d_front']).normalized()              # into the open V, where the pages are
R = bis.rotation_difference(Vector((0, 0, 1))).to_matrix().to_4x4()   # about the spine: the V opens upward
lect.root.matrix_world = R
bpy.context.view_layer.update()
case_w = np.array([R @ Vector(p) for p in sh['case']])
lift = 0.004 - case_w[:, 2].min()                                    # the spine 4 mm over the desk, in the gap
lect.root.matrix_world = Matrix.Translation((0, 0, lift)) @ R
bpy.context.view_layer.update()
M = np.array(lect.root.matrix_world)


def to_w(p):
    return p @ M[:3, :3].T + M[:3, 3]


wood = S.pbr_material('cradle_wood', S.cached('textures', 'Wood096_1k'), scale=3.0)


def wedge(name, top):
    """A block under a board: the four top corners on the board's outer face, the bottom on the desk (z = 0)."""
    bot = [(x, y, 0.0) for x, y, _z in top]
    verts = [tuple(v) for v in top] + bot
    faces = [(0, 1, 2, 3), (7, 6, 5, 4), (0, 4, 5, 1), (1, 5, 6, 2), (2, 6, 7, 3), (3, 7, 4, 0)]
    me = bpy.data.meshes.new(name)
    me.from_pydata(verts, [], faces)
    me.update()
    if sum(p.normal.z for p in me.polygons if p.index == 0) < 0:
        me.flip_normals()
    uvl = me.uv_layers.new(name='UVMap')
    for p in me.polygons:
        ax = max(range(3), key=lambda i: abs(p.normal[i]))
        a_, b_ = [(1, 2), (0, 2), (0, 1)][ax]
        for li in p.loop_indices:
            co = me.vertices[me.loops[li].vertex_index].co
            uvl.data[li].uv = (co[a_], co[b_])
    o = bpy.data.objects.new(name, me)
    sc.collection.objects.link(o)
    me.materials.append(wood)
    return o


axis_w = M[:3, :3] @ sh['axis']
for side in ('back', 'front'):
    pts = to_w(sh[side])
    c = pts.mean(0)
    n = np.linalg.svd(pts - c)[2][2]
    d = M[:3, :3] @ sh['d_' + side]
    if n[2] > 0:
        n = -n                                                          # the outer face looks down, onto the block
    rel = pts - c
    s, h = rel @ d, rel @ axis_w
    face = c + n * 0.0003
    corners = [face + d * s.min() + axis_w * (h.min() - 0.012), face + d * (s.max() + 0.012) + axis_w * (h.min() - 0.012),
               face + d * (s.max() + 0.012) + axis_w * (h.max() + 0.012), face + d * s.min() + axis_w * (h.max() + 0.012)]
    wedge(f'cradle_{side}', corners)
S.box(sc, 'desk', (2.4, 2.4, 0.04), (0.0, 0.0, -0.02),
      S.pbr_material('desk_wood', S.cached('textures', 'PaintedWood009C_2k'), scale=1.4))
S.area_light(sc, (-0.6, -0.5, 0.8), (0, 0, 0.08), 30.0, size=0.7, color=(1.0, 0.93, 0.84), name='window')
S.area_light(sc, (0.7, 0.3, 0.6), (0, 0, 0.08), 6.0, size=0.8, color=(0.8, 0.86, 1.0), name='fill')
head = Vector(axis_w).normalized()                                    # case_frame's Z runs tail -> head
centre = Vector(to_w(sh['spine'])) + Vector((0, 0, 0.06))
S.camera(sc, tuple(centre - head * 0.56 + Vector((0, 0, 0.40))), tuple(centre + Vector((0, 0, -0.03))), lens=35)
for f in (10, 22, F_LANDED):
    S.render_still(sc, f, OUT / f'book_lectern_f{f:03d}.png')
print(f'[test_book_lectern] {"ALL OK" if not FAILS else f"{len(FAILS)} FAILED"}', flush=True)
