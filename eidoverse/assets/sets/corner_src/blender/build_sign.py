"""Vibecamp march - one hand-made protest sign: a hand-cut corrugated board (0.60 x 0.45 x 0.005 m)
duct-taped and stapled to a pine lath stick. The painted FRONT is supplied per instance by the art
atlas (art/sign_art_*.jpg, 4x2 cells) through the second UV set 'ArtUV'; everything else is baked.

Output glb/camp_sign.glb, one mesh 'Sign':
    TEXCOORD_0 'BakeUV'  baked back / cut edges (corrugation flutes) / stick / tape / staples
    TEXCOORD_1 'ArtUV'   front face 0..1 (u left->right, v bottom->top seen from the front);
                         every other vertex (-1, -1)
    origin = the grip point on the stick axis, 0.45 m below the board's bottom edge; +Z up (glTF +Y);
    the painted front faces Blender -Y (glTF +Z).
Atlas cell k (0..7): atlas_uv = ((k % 4 + u) / 4, (1 - k // 4) / 2 - (1 - v) / 2 + 0.5)  i.e.
    row r = k // 4 occupies v_atlas in [0.5 - r/2, 1 - r/2]  (row 0 at the TOP of the image).
"""
import sys, os, math, random
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import bpy, bmesh
from mathutils import Vector
from clib import *

reset()
rnd = random.Random(11)
BW, BH, BT = 0.60, 0.45, 0.005
Z0 = 0.45                                # board bottom above the grip
STICK_W, STICK_T, STICK_L = 0.022, 0.012, 1.20
STICK_TOP = Z0 + BH - 0.06
YC = 0.0                                 # stick axis
Y_BACK = -STICK_T / 2                    # board back face touches the stick front face
Y_FRONT = Y_BACK - BT
ART = os.path.join(ROOT, 'art')

# ------------------------------------------------------------------ materials (layered, baked)
def flutes(nb, col, vec):
    """Corrugation on the cut edges: two liners + a sine medium between them (flutes run along Z)."""
    oc = nb.n('ShaderNodeTexCoord').outputs['Object']
    sep = nb.n('ShaderNodeSeparateXYZ'); nb.l(oc, sep.inputs[0])
    geo = nb.n('ShaderNodeNewGeometry')
    ns = nb.n('ShaderNodeSeparateXYZ'); nb.l(geo.outputs['Normal'], ns.inputs[0])
    side = nb.math('SUBTRACT', 1.0, nb.math('ABSOLUTE', ns.outputs['Y']))
    side = nb.math('GREATER_THAN', side, 0.6)
    yc = (Y_FRONT + Y_BACK) / 2
    wave = nb.math('MULTIPLY', nb.math('SINE', nb.math('MULTIPLY', sep.outputs['X'], 2 * math.pi / 0.0075)), 0.0017)
    d = nb.math('ABSOLUTE', nb.math('SUBTRACT', nb.math('SUBTRACT', sep.outputs['Y'], yc), wave))
    medium = nb.math('LESS_THAN', d, 0.00035)
    lf = nb.math('LESS_THAN', nb.math('ABSOLUTE', nb.math('SUBTRACT', sep.outputs['Y'], Y_FRONT)), 0.0005)
    lb = nb.math('LESS_THAN', nb.math('ABSOLUTE', nb.math('SUBTRACT', sep.outputs['Y'], Y_BACK)), 0.0005)
    lit = nb.math('MAXIMUM', medium, nb.math('MAXIMUM', lf, lb))
    edge_col = nb.mix(lit, (0.10, 0.07, 0.045), (0.60, 0.45, 0.30))
    return nb.mix(side, col, edge_col)


def card_extra(nb, col, vec):
    col = flutes(nb, col, vec)
    # the back was a shipping box: faded generic print + the flattened fold (art/sign_back_print.png)
    oc = nb.n('ShaderNodeTexCoord').outputs['Object']
    sep = nb.n('ShaderNodeSeparateXYZ'); nb.l(oc, sep.inputs[0])
    u = nb.math('DIVIDE', nb.math('SUBTRACT', BW / 2, sep.outputs['X']), BW)
    v = nb.math('DIVIDE', nb.math('SUBTRACT', sep.outputs['Z'], Z0), BH)
    cmb = nb.n('ShaderNodeCombineXYZ'); nb.l(u, cmb.inputs[0]); nb.l(v, cmb.inputs[1])
    it = nb.n('ShaderNodeTexImage'); it.image = load_img(os.path.join(ART, 'sign_back_print.png'))
    it.extension = 'CLIP'
    nb.l(cmb.outputs[0], it.inputs[0])
    geo = nb.n('ShaderNodeNewGeometry')
    ns = nb.n('ShaderNodeSeparateXYZ'); nb.l(geo.outputs['Normal'], ns.inputs[0])
    back = nb.math('GREATER_THAN', ns.outputs['Y'], 0.9)
    a = nb.math('MULTIPLY', it.outputs['Alpha'], back)
    return nb.mix(a, col, it.outputs['Color'], 'MULTIPLY')


m_card = layered_mat('kraft', 'Cardboard002', scale=2.0, tint=(0.88, 0.80, 0.74), sat=0.8, rough_mul=1.0, rough_add=0.05,
                     nstr=0.8, extra_color=card_extra,
                     wear=dict(color=(0.62, 0.50, 0.36), radius=0.0012, amount=0.7, rough=0.95, noise=30, gain=10),
                     grime=dict(color=(0.16, 0.11, 0.07), dist=0.03, amount=0.6, gain=1.6))


def grip_grime(nb, col, vec):
    """Hands have been on the bottom half of the stick all night: darker, a little polished."""
    oc = nb.n('ShaderNodeTexCoord').outputs['Object']
    sep = nb.n('ShaderNodeSeparateXYZ'); nb.l(oc, sep.inputs[0])
    band = nb.ramp(nb.math('ABSOLUTE', nb.math('SUBTRACT', sep.outputs['Z'], 0.07)), 0.05, 0.22,
                   (1, 1, 1, 1), (0, 0, 0, 1))
    band = nb.math('MULTIPLY', band, nb.ramp(nb.noise(oc, 25.0, 4.0, 0.6), 0.25, 0.8))
    return nb.mix(nb.math('MULTIPLY', band, 0.55), col, (0.30, 0.20, 0.12))


m_stick = layered_mat('pine_lath', 'Wood092', scale=1.6, rot=math.pi / 2, tint=(0.95, 0.86, 0.72), sat=0.85, val=0.95,
                      rough_mul=1.0, rough_add=0.08, nstr=0.9, extra_color=grip_grime,
                      wear=dict(color=(0.86, 0.72, 0.52), radius=0.0015, amount=0.8, rough=0.7, noise=40, gain=14),
                      grime=dict(color=(0.20, 0.13, 0.07), dist=0.02, amount=0.6, gain=1.8))
m_tape = layered_mat('duct_tape', 'Fabric061', scale=45.0, tint=(0.70, 0.71, 0.70), sat=0.3, val=1.15, rough_mul=0.45,
                     rough_add=0.02, nstr=0.35,
                     wear=dict(color=(0.82, 0.82, 0.80), radius=0.0008, amount=0.6, rough=0.3, noise=60, gain=12),
                     grime=dict(color=(0.30, 0.29, 0.27), dist=0.01, amount=0.5, gain=1.5))
m_steel = layered_mat('staple', 'Metal032', scale=20.0, tint=(0.85, 0.86, 0.88), metal=1.0, rough_mul=0.8, nstr=0.3)

parts = []

# ------------------------------------------------------------------ the board (hand-cut outline)
def outline_pts():
    pts = []
    corners = [(-BW / 2, Z0), (BW / 2, Z0), (BW / 2, Z0 + BH), (-BW / 2, Z0 + BH)]
    for i in range(4):
        a, b = Vector(corners[i]), Vector(corners[(i + 1) % 4])
        L = (b - a).length
        n = int(L / 0.018)
        t_dir = (b - a).normalized()
        nrm = Vector((t_dir.y, -t_dir.x))          # outward for a CCW loop
        drift = 0.0
        for k in range(n):
            t = k / n
            drift = drift * 0.7 + rnd.gauss(0, 0.0011)
            p = a + (b - a) * t + nrm * drift
            if k == 0:                                # corners: one slightly clipped, one nibbled round
                if i == 1:
                    p = p + (-t_dir * 0.006) + nrm * -0.004
                if i == 3:
                    p = p + nrm * -0.002
            pts.append((p.x, p.y))
    return pts


pts = outline_pts()
bm = bmesh.new()
vs = [bm.verts.new((x, Y_FRONT, z)) for x, z in pts]
front = bm.faces.new(vs)
bm.normal_update()
if front.normal.y > 0:                              # the painted face must look at -Y
    front.normal_flip()
ext = bmesh.ops.extrude_face_region(bm, geom=[front])
back_verts = [e for e in ext['geom'] if isinstance(e, bmesh.types.BMVert)]
bmesh.ops.translate(bm, verts=back_verts, vec=(0, BT, 0))
bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
board = obj_from_bm('board', bm, m_card)
finish(board, bevel=0.0006, segments=1, angle=60, smooth_angle=30)
uv_tex(board, 1.0)
parts.append(board)

# ------------------------------------------------------------------ the stick (pine lath, saw-cut ends)
bm = bmesh.new()
bm_box(bm, STICK_W, STICK_T, STICK_L, 0, YC, STICK_TOP - STICK_L / 2)
for v in bm.verts:                                   # a slightly skew saw cut at the bottom
    if v.co.z < STICK_TOP - STICK_L / 2:
        v.co.z += (v.co.x / STICK_W) * 0.006 + (v.co.y / STICK_T) * 0.002
st = obj_from_bm('stick', bm, m_stick)
finish(st, bevel=0.0012, segments=2, angle=50)
uv_tex_axis(st, 'Z', 1.0)
parts.append(st)

# ------------------------------------------------------------------ duct tape wrapping the stick onto the board
def tape_strip(zc, h, half_len, name):
    """Cross-section in XY: flat on the board back, up the stick's side, over its back, down, flat.
    Extruded along Z; torn, fibrous ends; 0.35 mm thick."""
    off = 0.0003
    xs = []
    sw = STICK_W / 2 + 0.0008
    sec = [(-half_len, Y_BACK + off), (-sw - 0.002, Y_BACK + off), (-sw, Y_BACK + off + 0.0015),
           (-sw, YC + STICK_T / 2 + off - 0.0012), (-sw + 0.0015, YC + STICK_T / 2 + off),
           (sw - 0.0015, YC + STICK_T / 2 + off), (sw, YC + STICK_T / 2 + off - 0.0012),
           (sw, Y_BACK + off + 0.0015), (sw + 0.002, Y_BACK + off), (half_len, Y_BACK + off)]
    # densify the flat runs so the torn ends can be jagged
    dense = []
    for i in range(len(sec) - 1):
        a, b = Vector(sec[i]), Vector(sec[i + 1])
        n = max(1, int((b - a).length / 0.004))
        for k in range(n):
            dense.append(a + (b - a) * (k / n))
    dense.append(Vector(sec[-1]))
    bm = bmesh.new()
    rows = 7
    grid = []
    for r in range(rows + 1):
        z = zc - h / 2 + h * r / rows
        row = []
        for j, p in enumerate(dense):
            x = p.x
            if j == 0 or j == len(dense) - 1:        # torn ends: zigzag along the tear
                x += (rnd.uniform(-0.004, 0.004)) * (1 if j == 0 else -1)
            row.append(bm.verts.new((x, p.y, z + rnd.gauss(0, 0.0002))))
        grid.append(row)
    for r in range(rows):
        for j in range(len(dense) - 1):
            bm.faces.new((grid[r][j], grid[r][j + 1], grid[r + 1][j + 1], grid[r + 1][j]))
    bm.normal_update()
    o = obj_from_bm(name, bm, m_tape)
    sol = o.modifiers.new('sol', 'SOLIDIFY')
    sol.thickness = 0.00035
    sol.offset = 1.0
    apply_mods(o)
    bmesh_fix = bmesh.new(); bmesh_fix.from_mesh(o.data)
    bmesh.ops.recalc_face_normals(bmesh_fix, faces=bmesh_fix.faces)
    bmesh_fix.to_mesh(o.data); bmesh_fix.free()
    smooth(o, 40)
    uv_tex(o, 1.0)
    return o


for zc, h, hl, nm in ((Z0 + 0.10, 0.048, 0.085, 'tape_low'), (Z0 + 0.33, 0.048, 0.075, 'tape_high')):
    parts.append(tape_strip(zc + rnd.gauss(0, 0.004), h, hl, nm))

# ------------------------------------------------------------------ staples through the tape into the stick
def staple(x, z, ang):
    bm = bmesh.new()
    crown, wire = 0.0125, 0.0007
    bm_box(bm, crown, wire, wire * 1.1, 0, 0, 0)
    for s in (-1, 1):                                # the legs disappear into the wood: tiny stubs
        bm_box(bm, wire, wire * 1.2, wire, s * (crown / 2 - wire / 2), -wire * 0.8, 0)
    o = obj_from_bm('staple', bm, m_steel)
    o.rotation_euler = (0, ang, 0)
    o.location = (x, YC + STICK_T / 2 + 0.00035 + 0.0004, z)
    select_only(o); bpy.ops.object.transform_apply(location=True, rotation=True, scale=True)
    finish(o, bevel=0.00025, segments=1)
    uv_tex(o, 0.1)
    return o


for zc in (Z0 + 0.10, Z0 + 0.33):
    for dz, a in ((-0.012, 0.25), (0.011, -0.2)):
        parts.append(staple(rnd.gauss(0, 0.001), zc + dz, math.radians(90) + a))

sign = join(parts, 'Sign')

# ------------------------------------------------------------------ bake (front island shrunk: the art atlas covers it)
uv_bake(sign, margin=0.003)
me = sign.data
bake_uv = me.uv_layers['BakeUV']
bm = bmesh.new(); bm.from_mesh(me)
luv = bm.loops.layers.uv['BakeUV']
bm.faces.ensure_lookup_table()
front_faces = [f for f in bm.faces if f.normal.y < -0.9 and all(abs(v.co.y - Y_FRONT) < 0.0012 for v in f.verts)]
if front_faces:
    cu = sum((l[luv].uv for f in front_faces for l in f.loops), Vector((0, 0))) / sum(len(f.loops) for f in front_faces)
    for f in front_faces:
        for l in f.loops:
            l[luv].uv = cu + (l[luv].uv - cu) * 0.08
bm.to_mesh(me); bm.free()
select_only(sign)
bpy.ops.object.mode_set(mode='EDIT'); bpy.ops.mesh.select_all(action='SELECT')
me.uv_layers.active = me.uv_layers['BakeUV']
bpy.ops.uv.select_all(action='SELECT')
try:
    bpy.ops.uv.pack_islands(margin=0.003, rotate=True, rotate_method='AXIS_ALIGNED', shape_method='CONCAVE')
except TypeError:
    bpy.ops.uv.pack_islands(margin=0.003, rotate=True)
bpy.ops.object.mode_set(mode='OBJECT')
print('[sign] front faces:', len(front_faces), flush=True)

bake_and_swap(sign, 'sign', size=2048, samples=40, ao_dist=0.05)
sign.data.materials[0].use_backface_culling = True      # closed solid: export single-sided

# ------------------------------------------------------------------ ArtUV (TEXCOORD_1)
art = me.uv_layers.new(name='ArtUV')
bm = bmesh.new(); bm.from_mesh(me)
lart = bm.loops.layers.uv['ArtUV']
nf = 0
for f in bm.faces:
    is_front = f.normal.y < -0.9 and all(abs(v.co.y - Y_FRONT) < 0.0012 for v in f.verts)
    for l in f.loops:
        if is_front:
            u = (l.vert.co.x + BW / 2) / BW
            v = (l.vert.co.z - Z0) / BH
            l[lart].uv = (min(0.998, max(0.002, u)), min(0.998, max(0.002, v)))
        else:
            l[lart].uv = (-1.0, -1.0)
    nf += is_front
bm.to_mesh(me); bm.free()
me.uv_layers['BakeUV'].active = True
me.uv_layers['BakeUV'].active_render = True
print('[sign] ArtUV front faces:', nf, 'uv layers:', [u.name for u in me.uv_layers], flush=True)

# a preview-only material pass: art cell k on ArtUV >= 0, baked elsewhere (not exported)
export_glb([sign], 'camp_sign.glb')
# a library copy for other build scripts (Blender 5.2's glTF IMPORTER trips on 'Iridescence Factor')
bpy.data.libraries.write(os.path.join(BAKED, 'camp_sign_lib.blend'), {sign}, fake_user=True)
tris = sum(len(p.vertices) - 2 for p in me.polygons)
print('[sign] tris', tris, flush=True)

baked = me.materials[0]


def preview_mat(k):
    m = baked.copy()
    m.name = f'sign_preview_{k}'
    nb = NB(m)
    bs = nb.N.get('Principled BSDF')
    base_link = bs.inputs['Base Color'].links[0].from_socket
    au = nb.n('ShaderNodeUVMap', uv_map='ArtUV')
    sp = nb.n('ShaderNodeSeparateXYZ'); nb.l(au.outputs[0], sp.inputs[0])
    col, row = k % 4, k // 4
    u = nb.math('DIVIDE', nb.math('ADD', sp.outputs['X'], col), 4.0)
    v = nb.math('ADD', nb.math('MULTIPLY', sp.outputs['Y'], 0.5), 0.5 - row * 0.5)
    cmb = nb.n('ShaderNodeCombineXYZ'); nb.l(u, cmb.inputs[0]); nb.l(v, cmb.inputs[1])
    it = nb.n('ShaderNodeTexImage'); it.image = load_img(os.path.join(ART, 'sign_art_color.jpg'))
    it.extension = 'EXTEND'
    nb.l(cmb.outputs[0], it.inputs[0])
    isf = nb.math('GREATER_THAN', sp.outputs['X'], -0.5)
    mixc = nb.mix(isf, base_link, it.outputs['Color'])
    nb.l(mixc, bs.inputs['Base Color'])
    return m


demo = []
for i, k in enumerate((0, 1, 3, 7)):
    o = sign.copy(); o.data = sign.data.copy(); link(o)
    o.data.materials.clear(); o.data.materials.append(preview_mat(k))
    o.location = ((i - 1.5) * 0.72, 0.0, 0.0)
    o.rotation_euler = (0, math.radians(rnd.uniform(-6, 6)), math.radians(rnd.uniform(-12, 12)))
    demo.append(o)
sign.hide_render = True
preview(demo, 'sign_demo', height=0.25, size=640)
for o in demo:
    o.hide_render = True
sign.hide_render = False


def closeup_lit(name, cam, tgt, lens=50):
    ls = []
    for loc, e in (((cam[0] + 0.4, cam[1] - 0.2, cam[2] + 0.6), 9.0), ((cam[0] - 0.6, cam[1], cam[2] - 0.1), 3.0)):
        ld = bpy.data.lights.new('cl', 'AREA'); ld.energy = e; ld.size = 0.5
        lo = bpy.data.objects.new('cl', ld); link(lo); lo.location = loc
        lo.rotation_euler = (Vector(tgt) - Vector(loc)).to_track_quat('-Z', 'Y').to_euler()
        ls.append(lo)
    closeup(name, cam, tgt, lens=lens)
    for lo in ls:
        bpy.data.objects.remove(lo)


closeup_lit('sign_back', (0.30, 0.50, Z0 + 0.30), (0.0, 0.0, Z0 + 0.22), lens=40)
closeup_lit('sign_edge', (0.40, -0.22, Z0 + 0.50), (0.29, -0.008, Z0 + 0.445), lens=90)
closeup_lit('sign_grip', (0.12, -0.30, 0.10), (0.0, 0.0, 0.05), lens=55)
