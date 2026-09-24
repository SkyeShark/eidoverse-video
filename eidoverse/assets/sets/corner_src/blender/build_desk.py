"""Claude's Corner - the writing desk. A small walnut writing desk with tapered legs, aprons and
one drawer (recessed field panel, brass knob). Layered walnut: lacquer, worn-through edges,
cavity grime where legs meet aprons, a forearm-worn front band on the top and one faint mug
ring. Baked to a 2K atlas -> glb/corner_desk.glb (origin: floor, desk centre; front = -Y).
"""
import sys, os, math
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import bpy, bmesh
from mathutils import Vector
from clib import *

reset()
W, D, H = 1.16, 0.58, 0.76
TOP_T = 0.028
LEG_TOP, LEG_BOT = 0.048, 0.032
APRON_H, APRON_T = 0.100, 0.020
LX = W / 2 - 0.040 - LEG_TOP / 2
LY = D / 2 - 0.040 - LEG_TOP / 2


def wood_extra(nb, col, vec):
    """forearm band near the front edge + one faint mug ring (object space)."""
    oc = nb.n('ShaderNodeTexCoord').outputs['Object']
    sep = nb.n('ShaderNodeSeparateXYZ'); nb.l(oc, sep.inputs[0])
    top = nb.ramp(sep.outputs['Z'], H - 0.004, H - 0.001)                 # only the top face
    band = nb.ramp(sep.outputs['Y'], -D / 2 + 0.03, -D / 2 + 0.16)         # 1 at the front edge region
    inv = nb.math('SUBTRACT', 1.0, band)
    wnoise = nb.ramp(nb.noise(oc, 7.0, 5.0, 0.6), 0.35, 0.7)
    fb = nb.math('MULTIPLY', nb.math('MULTIPLY', inv, top), nb.math('MULTIPLY', wnoise, 0.12))
    col = nb.mix(fb, col, (0.42, 0.27, 0.16))
    # mug ring at (0.36, 0.13)
    dx = nb.math('SUBTRACT', sep.outputs['X'], 0.36)
    dy = nb.math('SUBTRACT', sep.outputs['Y'], 0.13)
    r = nb.math('SQRT', nb.math('ADD', nb.math('MULTIPLY', dx, dx), nb.math('MULTIPLY', dy, dy)))
    ring = nb.math('SUBTRACT', 1.0, nb.math('MULTIPLY', nb.math('ABSOLUTE', nb.math('SUBTRACT', r, 0.041)), 260.0), clamp=True)
    ring = nb.math('MULTIPLY', nb.math('MULTIPLY', ring, top), nb.ramp(nb.noise(oc, 40.0, 3.0, 0.5), 0.3, 0.8))
    col = nb.mix(nb.math('MULTIPLY', ring, 0.55), col, (0.12, 0.07, 0.04))
    return col


walnut = dict(scale=1.05, tint=(0.93, 0.78, 0.68), tint_amt=1.0, sat=0.95, val=0.84, rough_mul=0.62, rough_add=0.02,
              nstr=0.8,
              wear=dict(color=(0.52, 0.33, 0.20), radius=0.0035, amount=0.9, rough=0.55, noise=16, gain=16),
              grime=dict(color=(0.045, 0.028, 0.018), dist=0.05, amount=0.75, rough=0.2, gain=1.8))
m_top = layered_mat('walnut_top', 'Wood066', extra_color=wood_extra, **walnut)
m_wood = layered_mat('walnut', 'Wood066', **walnut)
m_leg = layered_mat('walnut_leg', 'Wood066', rot=math.pi / 2, **walnut)
m_brass = layered_mat('brass', 'Metal048B', scale=6.0, tint=(0.78, 0.56, 0.30), metal=1.0, rough_mul=0.9, rough_add=0.08,
                      wear=dict(color=(1.0, 0.82, 0.52), radius=0.0015, amount=1.0, rough=0.18, metal=1.0, gain=22),
                      grime=dict(color=(0.10, 0.08, 0.04), dist=0.01, amount=0.8, gain=2.0))
parts = []

# ---- top: one slab, profiled edge (3-seg round), grain along X
bm = bmesh.new(); bm_box(bm, W, D, TOP_T, 0, 0, H - TOP_T / 2)
top = obj_from_bm('top', bm, m_top)
finish(top, bevel=0.0055, segments=4, angle=50)
uv_tex_axis(top, 'X', 1.0)
parts.append(top)

# ---- legs: tapered square, top cap removed (buried under the top)
for sx in (-1, 1):
    for sy in (-1, 1):
        bm = bmesh.new()
        vs = bm_box(bm, 1, 1, 1)
        z0, z1 = 0.0, H - TOP_T
        for v in vs:
            t = 1 if v.co.z > 0 else 0
            s = LEG_TOP if t else LEG_BOT
            # taper only on the two inside faces: outer faces stay plumb
            ox = sx * (LEG_TOP / 2) if (v.co.x * sx) > 0 else sx * (LEG_TOP / 2) - (s if True else 0)
            x = sx * LX + (sx * LEG_TOP / 2 if v.co.x * sx > 0 else sx * (LEG_TOP / 2 - s))
            y = sy * LY + (sy * LEG_TOP / 2 if v.co.y * sy > 0 else sy * (LEG_TOP / 2 - s))
            v.co = Vector((x, y, z1 if t else z0))
        bm.faces.ensure_lookup_table()
        topf = [f for f in bm.faces if f.normal.z > 0.9 or all(v.co.z > z1 - 1e-6 for v in f.verts)]
        bmesh.ops.delete(bm, geom=topf, context='FACES_ONLY')
        lg = obj_from_bm(f'leg', bm, m_leg)
        finish(lg, bevel=0.0025, segments=3, angle=50)
        uv_tex_axis(lg, 'Z', 1.0)
        parts.append(lg)

# ---- aprons (side/back plain boards; ends buried in the legs are removed)
za = H - TOP_T - APRON_H / 2
inner_x = LX - LEG_TOP / 2 + 0.002
inner_y = LY - LEG_TOP / 2 + 0.002
face_y = LY + LEG_TOP / 2 - 0.006          # aprons sit 6 mm behind the leg faces
for sy in (1,):                             # back apron
    bm = bmesh.new(); bm_box(bm, 2 * inner_x, APRON_T, APRON_H, 0, sy * (face_y - APRON_T / 2), za)
    ap = obj_from_bm('apron_back', bm, m_wood); finish(ap, bevel=0.0015, segments=2); uv_tex_axis(ap, 'X', 1.0)
    parts.append(ap)
for sx in (-1, 1):
    bm = bmesh.new(); bm_box(bm, APRON_T, 2 * inner_y, APRON_H, sx * (LX + LEG_TOP / 2 - 0.006 - APRON_T / 2), 0, za)
    ap = obj_from_bm('apron_side', bm, m_wood); finish(ap, bevel=0.0015, segments=2); uv_tex_axis(ap, 'Y', 1.0)
    parts.append(ap)

# ---- front apron: ONE board, the drawer opening is an inset region pushed through (a real reveal)
DW, DH = 0.50, 0.074
bm = bmesh.new()
bm_box(bm, 2 * inner_x, APRON_T, APRON_H, 0, -(face_y - APRON_T / 2), za)
bm.faces.ensure_lookup_table()
front = max(bm.faces, key=lambda f: -f.calc_center_median().y)
# cut the drawer rectangle into the front face: inset to the drawer outline, then extrude through
ins = bmesh.ops.inset_individual(bm, faces=[front], thickness=0.0, depth=0.0)
fr = front
# reshape the inner face to the exact drawer rectangle
cx, cz = 0.0, za - 0.002
for v in fr.verts:
    v.co.x = cx + (DW / 2 if v.co.x > 0 else -DW / 2)
    v.co.z = cz + (DH / 2 if v.co.z > za else -DH / 2)
ext = bmesh.ops.extrude_face_region(bm, geom=[fr])
nv = [e for e in ext['geom'] if isinstance(e, bmesh.types.BMVert)]
bmesh.ops.translate(bm, verts=nv, vec=(0, APRON_T + 0.001, 0))
nf = [e for e in ext['geom'] if isinstance(e, bmesh.types.BMFace)]
bmesh.ops.delete(bm, geom=nf, context='FACES')
bmesh.ops.delete(bm, geom=[fr], context='FACES') if fr.is_valid else None
bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
fa = obj_from_bm('apron_front', bm, m_wood)
finish(fa, bevel=0.0015, segments=2, angle=50)
uv_tex_axis(fa, 'X', 1.0)
parts.append(fa)

# ---- drawer front: separate part, 2 mm reveal, chamfered edge, recessed field (inset + push)
gap = 0.002
bm = bmesh.new()
dy = -(face_y) + 0.0
bm_box(bm, DW - 2 * gap, 0.018, DH - 2 * gap, cx, dy + 0.009 - 0.0015, cz)
bm.faces.ensure_lookup_table()
dface = min(bm.faces, key=lambda f: f.calc_center_median().y)
r = bmesh.ops.inset_region(bm, faces=[dface], thickness=0.012, depth=0.0)
r2 = bmesh.ops.inset_region(bm, faces=[dface], thickness=0.004, depth=-0.0025)   # the field steps down 2.5 mm
drawer = obj_from_bm('drawer', bm, m_wood)
finish(drawer, bevel=0.0012, segments=2, angle=30)
uv_tex_axis(drawer, 'X', 1.0)
parts.append(drawer)

# ---- brass knob (lathe): rose, neck, mushroom head
kn = lathe_obj('knob', [(0.0001, 0.0), (0.011, 0.0), (0.0115, 0.0015), (0.010, 0.003), (0.0045, 0.005),
                        (0.0042, 0.012), (0.009, 0.016), (0.0105, 0.020), (0.0095, 0.0235), (0.006, 0.0255),
                        (0.0001, 0.026)], 40, m_brass)
kn.rotation_euler = (math.radians(90), 0, 0)
kn.location = (cx, dy - 0.0015 - 0.0005, cz)
select_only(kn); bpy.ops.object.transform_apply(location=True, rotation=True, scale=True)
uv_tex(kn, 0.2)
parts.append(kn)

desk = join(parts, 'Desk')
uv_bake(desk, margin=0.003)
bake_and_swap(desk, 'desk', size=2048, samples=40, ao_dist=0.12)
export_glb([desk], 'corner_desk.glb')
preview([desk], 'desk', height=0.55)
closeup('desk_drawer', (0.25, -0.75, 0.82), (0.0, -0.22, 0.70), lens=50)
