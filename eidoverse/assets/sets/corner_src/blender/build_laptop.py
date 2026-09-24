"""Claude's Corner - the laptop. A modern 13-14" aluminium laptop, NO logo anywhere.

Base 0.305 x 0.215 x 0.014 (+1.5 mm rubber feet): one rounded-rectangle aluminium mass with the
keyboard well, the trackpad recess, two speaker-grille fields, the hinge channel and the front
lid-lift scoop cut in by boolean, perimeter rounds, 78 individual keycaps (rounded, slightly dished)
with faint printed legends, a glass trackpad, a hinge barrel and two rubber feet.
Lid 0.006: rounded aluminium slab, black glass bezel (1.5 mm aluminium lip), 16:10 display recess.

Objects:
  'LaptopBase'   baked; origin = bottom centre (desk contact, z = 0); the user sits at -Y.
  'LaptopLid'    baked; child of the base; ORIGIN ON THE HINGE AXIS (base-local (0, 0.103, 0.011));
                 rotates about its local X.  rotation.x = 0 -> CLOSED (lying on the deck, screen
                 down); exported OPEN at rotation.x = -110 deg (-1.9199 rad).
  'LaptopScreen' child of the lid, 0.291 x 0.1819 quad (16:10), 0.3 mm inside the bezel glass,
                 flat material 'SCREEN'; UV u left->right, v bottom->top as the user sees it.
Exports glb/corner_laptop.glb.
"""
import sys, os, math
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import bpy, bmesh
from mathutils import Vector
from clib import *
from helpers_wcl import *

reset()
EPS = 1e-6
BW, BD = 0.305, 0.215
Z0, Z1 = 0.0015, 0.0155                  # base body bottom / deck
HINGE = Vector((0.0, 0.1030, 0.0110))
OPEN_DEG = -110.0
WELL = (-0.1325, 0.1325, -0.009, 0.094)
U = 0.018                                # key pitch
GAP = 0.0022
KEY_TOP_Y = 0.092


def near(a, b, eps=1e-5):
    return abs(a - b) < eps


# ============================================================================ key layout
ROWS = [
    (0.55, [(1.5, 'esc')] + [(1, f'F{i}') for i in range(1, 13)] + [(1, 'o')]),
    (1, [(1, '`')] + [(1, c) for c in '1234567890-='] + [(1.5, 'delete')]),
    (1, [(1.5, 'tab')] + [(1, c) for c in 'QWERTYUIOP[]'] + [(1, '\\')]),
    (1, [(1.75, 'caps')] + [(1, c) for c in "ASDFGHJKL;'"] + [(1.75, 'return')]),
    (1, [(2.25, 'shift')] + [(1, c) for c in 'ZXCVBNM,./'] + [(2.25, 'shift')]),
    (1, [(1, 'fn'), (1, 'ctrl'), (1, 'alt'), (1.25, 'cmd'), (5, ''), (1.25, 'cmd'), (1, 'alt'),
         (1, '<'), (1, 'updown'), (1, '>')]),
]
keys = []                                 # (x0, x1, y0, y1, legend, kind)
y = KEY_TOP_Y
for h, row in ROWS:
    x = -14.5 * U / 2
    y1, y0 = y, y - h * U
    for w, leg in row:
        if leg == 'updown':
            ym = (y0 + y1) / 2
            keys.append((x + GAP / 2, x + w * U - GAP / 2, ym + GAP / 4, y1 - GAP / 2, '^', 'arrow'))
            keys.append((x + GAP / 2, x + w * U - GAP / 2, y0 + GAP / 2, ym - GAP / 4, 'v', 'arrow'))
        else:
            keys.append((x + GAP / 2, x + w * U - GAP / 2, y0 + GAP / 2, y1 - GAP / 2, leg,
                         'mod' if len(leg) > 1 and not leg.startswith('F') else 'char'))
        x += w * U
    y = y0
print(f'[laptop] {len(keys)} keycaps', flush=True)

# legends (PIL, top-down over the keyboard well) - printed ink, texture only
from PIL import Image, ImageDraw, ImageFont
LW, LH = 2048, int(2048 * (WELL[3] - WELL[2]) / (WELL[1] - WELL[0]))
leg_img = Image.new('L', (LW, LH), 0)
dr = ImageDraw.Draw(leg_img)
fp = 'C:/Windows/Fonts/arial.ttf'
if not os.path.exists(fp):
    fp = os.path.join(ROOT, '..', '..', '..', '..', 'eidoverse', 'assets', 'fonts', 'Exo2.ttf')
px = lambda x: (x - WELL[0]) / (WELL[1] - WELL[0]) * LW
py = lambda y: (WELL[3] - y) / (WELL[3] - WELL[2]) * LH
for (x0, x1, y0, y1, leg, kind) in keys:
    if not leg:
        continue
    cx, cy = px((x0 + x1) / 2), py((y0 + y1) / 2)
    hh = py(y0) - py(y1)
    if leg == 'o':                                   # power: a circle glyph
        r = hh * 0.22
        dr.arc((cx - r, cy - r, cx + r, cy + r), 300, 240, fill=255, width=max(2, int(r * 0.22)))
        dr.line((cx, cy - r * 1.25, cx, cy - r * 0.2), fill=255, width=max(2, int(r * 0.22)))
        continue
    if kind == 'arrow':
        s = hh * 0.22
        pts = {'^': [(cx, cy - s), (cx - s, cy + s * 0.6), (cx + s, cy + s * 0.6)],
               'v': [(cx, cy + s), (cx - s, cy - s * 0.6), (cx + s, cy - s * 0.6)]}[leg]
        dr.polygon(pts, fill=255)
        continue
    if leg in '<>':
        s = hh * 0.12
        pts = [(cx - s, cy), (cx + s * 0.8, cy - s), (cx + s * 0.8, cy + s)] if leg == '<' else \
              [(cx + s, cy), (cx - s * 0.8, cy - s), (cx - s * 0.8, cy + s)]
        dr.polygon(pts, fill=255)
        continue
    if kind == 'char':
        f = ImageFont.truetype(fp, int(hh * (0.30 if not leg.startswith('F') else 0.42)))
        dr.text((cx, cy), leg, fill=255, font=f, anchor='mm')
    else:
        f = ImageFont.truetype(fp, int(hh * 0.20))
        ww = px(x1) - px(x0)
        dr.text((px(x0) + ww * 0.12, py(y0) - hh * 0.16), leg, fill=255, font=f, anchor='ls')
leg_path = os.path.join(BAKED, 'laptop_legends.png')
leg_img.save(leg_path)


# ============================================================================= materials
def alu_extra_base(nb, col, vec):
    """speaker-grille perforations (texture: finless grating), object space."""
    oc, sep = obj_sep(nb)
    x, y = sep.outputs['X'], sep.outputs['Y']
    ax = nb.math('ABSOLUTE', x)
    reg = nb.math('MULTIPLY', band(nb, ax, 0.1372, 0.1376, 0.1471, 0.1475), band(nb, y, -0.0058, -0.0054, 0.0896, 0.0900))
    top = maprange(nb, sep.outputs['Z'], Z1 - 0.0004, Z1 - 0.0002)
    P = 0.00155

    def cell(s):
        f = nb.math('FRACT', nb.math('DIVIDE', s, P))
        return nb.math('SUBTRACT', f, 0.5)
    dx = cell(x); dy = cell(y)
    d = nb.math('SQRT', nb.math('ADD', nb.math('MULTIPLY', dx, dx), nb.math('MULTIPLY', dy, dy)))
    dot = maprange(nb, d, 0.31, 0.24)
    m = nb.math('MULTIPLY', nb.math('MULTIPLY', dot, reg), top)
    return nb.mix(m, col, (0.012, 0.012, 0.014))


alu_common = dict(scale=3.0, tint=(0.27, 0.28, 0.30), metal=1.0, rough_mul=0.8, rough_add=0.34, nstr=0.35,
                  wear=dict(color=(0.80, 0.82, 0.85), radius=0.0007, amount=0.9, rough=0.16, metal=1.0, gain=22, noise=30),
                  grime=dict(color=(0.14, 0.14, 0.15), dist=0.006, amount=0.55, rough=0.08, gain=1.8))
m_alu = layered_mat('alu', 'Metal050A', extra_color=alu_extra_base, **alu_common)
m_alu_lid = layered_mat('alu_lid', 'Metal050A', **alu_common)
m_barrel = layered_mat('barrel', 'Metal050A', scale=3.0, tint=(0.22, 0.23, 0.25), metal=1.0, rough_mul=1.0, rough_add=0.2,
                       wear=dict(color=(0.55, 0.56, 0.58), radius=0.0006, amount=0.8, rough=0.2, metal=1.0, gain=22))
m_track = layered_mat('trackpad', 'Metal050A', scale=3.0, tint=(0.25, 0.26, 0.28), metal=1.0, rough_mul=0.8, rough_add=0.22,
                      nstr=0.15)
m_rubber = layered_mat('rubber', 'Plastic012B', scale=4.0, tint=(0.55, 0.55, 0.55), rough_mul=1.2, rough_add=0.3, nstr=0.3)


def key_extra(nb, col, vec):
    """printed legends, top faces only."""
    oc, sep = obj_sep(nb)
    mp = nb.n('ShaderNodeMapping')
    mp.inputs['Location'].default_value = (-WELL[0] / (WELL[1] - WELL[0]), -WELL[2] / (WELL[3] - WELL[2]), 0)
    mp.inputs['Scale'].default_value = (1 / (WELL[1] - WELL[0]), 1 / (WELL[3] - WELL[2]), 1)
    mp.vector_type = 'POINT'
    nb.l(oc, mp.inputs['Vector'])
    # Mapping POINT: out = (in * scale) + location
    mp.inputs['Location'].default_value = (-WELL[0] / (WELL[1] - WELL[0]), -WELL[2] / (WELL[3] - WELL[2]), 0)
    it = nb.n('ShaderNodeTexImage', extension='CLIP', interpolation='Cubic')
    it.image = load_img(leg_path, False)
    nb.l(mp.outputs[0], it.inputs['Vector'])
    geo = nb.n('ShaderNodeNewGeometry')
    nz = nb.n('ShaderNodeSeparateXYZ'); nb.l(geo.outputs['Normal'], nz.inputs[0])
    top = nb.ramp(nz.outputs['Z'], 0.85, 0.97)
    m = nb.math('MULTIPLY', nb.math('MULTIPLY', it.outputs['Color'], top), 0.62)
    return nb.mix(m, col, (0.46, 0.47, 0.48))


m_keys = layered_mat('keys', 'Plastic012B', scale=5.0, tint=(0.80, 0.80, 0.82), rough_mul=0.6, rough_add=0.40, nstr=0.25,
                     extra_color=key_extra,
                     wear=dict(color=(0.07, 0.07, 0.075), radius=0.0004, amount=0.5, rough=0.45, gain=20, noise=40),
                     grime=dict(color=(0.02, 0.02, 0.02), dist=0.002, amount=0.5, gain=1.6))
m_bezel = layered_mat('bezel', 'Plastic006', scale=4.0, tint=(0.30, 0.30, 0.32), rough_mul=0.25, rough_add=0.02, nstr=0.05)
m_screen = flat_mat('SCREEN', (0.02, 0.02, 0.025), rough=0.1)


def palm_smudges(nb):
    """fingerprint smudges: glossier blotches on the palm rest and around the trackpad."""
    oc, sep = obj_sep(nb)
    reg = nb.math('MULTIPLY', maprange(nb, sep.outputs['Y'], -0.004, -0.030), maprange(nb, sep.outputs['Z'], Z1 - 0.0006, Z1 - 0.0002))
    n1 = nb.ramp(nb.noise(oc, 55.0, 2.0, 0.45), 0.60, 0.78)
    n2 = nb.ramp(nb.noise(oc, 12.0, 2.0, 0.5), 0.45, 0.70)
    return nb.math('MULTIPLY', nb.math('MULTIPLY', n1, n2), nb.math('MULTIPLY', reg, 0.55))


def lid_smudges(nb):
    oc, sep = obj_sep(nb)
    reg = maprange(nb, sep.outputs['Y'], -0.15, -0.205)          # near the free edge (where fingers lift)
    n1 = nb.ramp(nb.noise(oc, 50.0, 2.0, 0.45), 0.62, 0.78)
    n2 = nb.ramp(nb.noise(oc, 10.0, 2.0, 0.5), 0.40, 0.70)
    return nb.math('MULTIPLY', nb.math('MULTIPLY', n1, n2), nb.math('MULTIPLY', reg, 0.5))


post_layer(m_alu, 'rough', palm_smudges, 0.26)
post_layer(m_track, 'rough', palm_smudges, 0.16)
post_layer(m_alu_lid, 'rough', lid_smudges, 0.26)


def camera_dot(nb):
    oc, sep = obj_sep(nb)
    dx = sep.outputs['X']
    dy = nb.math('SUBTRACT', sep.outputs['Y'], -0.2057)
    d = nb.math('SQRT', nb.math('ADD', nb.math('MULTIPLY', dx, dx), nb.math('MULTIPLY', dy, dy)))
    return maprange(nb, d, 0.0013, 0.0009)


post_layer(m_bezel, 'color', camera_dot, (0.03, 0.035, 0.05))

# ================================================================================= base
bm = bmesh.new()
polygon_prism(bm, rounded_rect_pts(BW, BD, 0.011, 8), Z0, Z1)
bevel_edges(bm, lambda a, b: near(a.z, Z1) and near(b.z, Z1), 0.0015, 3, 0.5)
bevel_edges(bm, lambda a, b: near(a.z, Z0) and near(b.z, Z0), 0.0034, 4, 0.5)
base = obj_from_bm('LaptopBase', bm, m_alu)
base.data.materials.append(m_track)


def rr_cutter(x0, x1, y0, y1, r, z0, z1):
    bm = bmesh.new()
    polygon_prism(bm, rounded_rect_pts(x1 - x0, y1 - y0, r, 6, (x0 + x1) / 2, (y0 + y1) / 2), z0, z1)
    return obj_from_bm('cut', bm)


boolean(base, rr_cutter(*WELL, 0.003, Z1 - 0.0012, Z1 + 0.01))
boolean(base, rr_cutter(-0.0625, 0.0625, -0.097, -0.024, 0.006, Z1 - 0.0003, Z1 + 0.01))
for sx in (-1, 1):
    boolean(base, rr_cutter(*sorted((sx * 0.137, sx * 0.1475)), -0.006, 0.090, 0.002, Z1 - 0.0002, Z1 + 0.01))
boolean(base, cutter_cyl(0.0052, 0.250, (HINGE.x, HINGE.y, HINGE.z), 'X', 40))
bpy.ops.mesh.primitive_uv_sphere_add(segments=48, ring_count=24, radius=1.0, location=(0, -BD / 2, Z1))
sc = bpy.context.view_layer.objects.active
sc.scale = (0.019, 0.011, 0.0021)
select_only(sc); bpy.ops.object.transform_apply(location=False, rotation=False, scale=True)
boolean(base, sc)
# trackpad floor faces -> trackpad material
for p in base.data.polygons:
    c = p.center
    if p.normal.z > 0.9 and near(c.z, Z1 - 0.0003, 2e-5) and abs(c.x) < 0.0626 and -0.0971 < c.y < -0.0239:
        p.material_index = 1
finish(base, bevel=0.00028, segments=2, angle=28)
uv_tex(base, 1.0)

# keycaps: rounded prisms, dished tops (inset + push), bottoms buried on the well floor
kbm = bmesh.new()
KZ0, KZ1 = Z1 - 0.0012, Z1 - 0.0002
for (x0, x1, y0, y1, leg, kind) in keys:
    lo, hi = polygon_prism(kbm, rounded_rect_pts(x1 - x0, y1 - y0, 0.0011, 3, (x0 + x1) / 2, (y0 + y1) / 2), KZ0, KZ1)
kbm.normal_update()
tops = [f for f in kbm.faces if f.normal.z > 0.9]
bots = [f for f in kbm.faces if f.normal.z < -0.9]
bmesh.ops.delete(kbm, geom=bots, context='FACES_ONLY')
for f in tops:
    bmesh.ops.inset_region(kbm, faces=[f], thickness=0.0011, depth=-0.00012)
keys_o = obj_from_bm('keys', kbm, m_keys)
finish(keys_o, bevel=0.00032, segments=2, angle=28)
uv_tex(keys_o, 0.2)

# hinge barrel (sits in the channel) and rubber feet
bm = bmesh.new()
bmesh.ops.create_cone(bm, cap_ends=True, segments=40, radius1=0.0045, radius2=0.0045, depth=0.240)
barrel = obj_from_bm('barrel', bm, m_barrel)
xform(barrel, tuple(HINGE), (0, math.radians(90), 0))
finish(barrel, bevel=0.0009, segments=3, angle=40)
uv_tex(barrel, 0.2)
feet = []
for fy in (-0.090, 0.090):
    bm = bmesh.new()
    pts = rounded_rect_pts(0.230, 0.0065, 0.0032, 6, 0.0, fy)
    polygon_prism(bm, pts, 0.0, Z0 + 0.0004)
    bury(bm, lambda c, n: n.z > 0.9)
    bevel_edges(bm, lambda a, b: near(a.z, 0.0) and near(b.z, 0.0), 0.0007, 2, 0.5)
    f_ = obj_from_bm('foot', bm, m_rubber)
    smooth(f_, 40)
    uv_tex(f_, 0.2)
    feet.append(f_)

base = join([base, keys_o, barrel] + feet, 'LaptopBase')

# ================================================================================== lid
LY0, LY1 = -0.2095, 0.0045            # lid-local y (free edge .. hinge side)
LZ0, LZ1 = 0.0050, 0.0110             # inner (screen) face .. outer face
bm = bmesh.new()
polygon_prism(bm, rounded_rect_pts(BW, LY1 - LY0, 0.011, 8, 0.0, (LY0 + LY1) / 2), LZ0, LZ1)
bevel_edges(bm, lambda a, b: near(a.z, LZ1) and near(b.z, LZ1), 0.0020, 3, 0.5)
bevel_edges(bm, lambda a, b: near(a.z, LZ0) and near(b.z, LZ0), 0.0008, 2, 0.5)
lid = obj_from_bm('LaptopLid', bm, m_alu_lid)
lid.data.materials.append(m_bezel)
LIP = 0.0015
boolean(lid, rr_cutter(-BW / 2 + LIP, BW / 2 - LIP, LY0 + LIP, LY1 - LIP, 0.0095, LZ0 - 0.01, LZ0 + 0.0003))
DX0, DX1, DY0, DY1 = -0.1455, 0.1455, -0.2015, -0.2015 + 0.291 * 10 / 16
boolean(lid, rr_cutter(DX0, DX1, DY0, DY1, 0.0008, LZ0 - 0.01, LZ0 + 0.0008))
for p in lid.data.polygons:
    c = p.center
    if p.normal.z < -0.9 and c.z > LZ0 + 0.0002:
        p.material_index = 1
    # the recess walls of the glass/display belong to the glass too
    if abs(p.normal.z) < 0.5 and LZ0 + 0.00005 < c.z < LZ0 + 0.00085 and abs(c.x) < BW / 2 - LIP + 0.0001 \
            and LY0 + LIP - 0.0001 < c.y < LY1 - LIP + 0.0001:
        p.material_index = 1
finish(lid, bevel=0.00025, segments=1, angle=28)
uv_tex(lid, 1.0)

# screen quad (display plane, just in front of the display floor, behind the glass)
bm = bmesh.new()
SZ = LZ0 + 0.0006
vs = [bm.verts.new((DX0, DY0, SZ)), bm.verts.new((DX1, DY0, SZ)), bm.verts.new((DX1, DY1, SZ)), bm.verts.new((DX0, DY1, SZ))]
f = bm.faces.new(vs)
bm.normal_update()
if f.normal.z > 0:
    f.normal_flip()
uvl = bm.loops.layers.uv.new('UVMap')
for lp in f.loops:
    c = lp.vert.co
    lp[uvl].uv = ((c.x - DX0) / (DX1 - DX0), (DY1 - c.y) / (DY1 - DY0))   # v = 1 at the free (top) edge
screen = obj_from_bm('LaptopScreen', bm, m_screen)

# ========================================================================== bake, rig
# bake each part alone (the other hidden) so AO is the part's own
print('[laptop] uv maps', strip_uv(base, keep=('TexUV',)), strip_uv(lid, keep=('TexUV',)), flush=True)
uv_bake(base, margin=0.002, angle=60)
uv_bake(lid, margin=0.003, angle=60)
lid.hide_render = True; screen.hide_render = True
bake_and_swap(base, 'laptop_base', size=2048, samples=40, ao_dist=0.02)
lid.hide_render = False; base.hide_render = True
bake_and_swap(lid, 'laptop_lid', size=2048, samples=40, ao_dist=0.02)
base.hide_render = False; screen.hide_render = False

lid.parent = base
lid.location = tuple(HINGE)
screen.parent = lid
screen.location = (0, 0, 0)
lid.rotation_euler = (math.radians(OPEN_DEG), 0, 0)
bpy.context.view_layer.update()
export_glb([base], 'corner_laptop.glb')
bpy.ops.wm.save_as_mainfile(filepath=os.path.join(ROOT, 'blend', 'corner_laptop.blend'))

# ================================================================================ lookdev
lookdev_screen = bpy.data.materials.new('screen_lookdev'); lookdev_screen.use_nodes = True
b = lookdev_screen.node_tree.nodes.get('Principled BSDF')
b.inputs['Base Color'].default_value = (0.0, 0.0, 0.0, 1)
b.inputs['Emission Color'].default_value = (0.20, 0.22, 0.28, 1)
b.inputs['Emission Strength'].default_value = 1.0
screen.data.materials[0] = lookdev_screen
preview([base], 'laptop', height=0.5)
desk = obj_from_bm('ctx_desk', box_obj('d', -0.6, 0.6, -0.4, 0.4, -0.03, 0.0),
                   layered_mat('desk_ctx', 'Wood066', scale=1.0, tint=(0.9, 0.75, 0.65), val=0.85, rough_mul=0.6))
uv_tex(desk, 1.0)
lamp = ((-0.45, -0.25, 0.45), 7, 0.25, (1.0, 0.80, 0.58))
fill = ((0.5, -0.6, 0.35), 2.5, 0.6, (0.75, 0.82, 1.0))
rim = ((0.2, 0.6, 0.4), 4, 0.5, (1.0, 1.0, 1.0))
shots = [lit_closeup('laptop_c_open', (0.25, -0.52, 0.32), (0.0, 0.02, 0.07), lens=45, key=lamp, fill=fill, rim=rim),
         lit_closeup('laptop_c_keys', (-0.05, -0.16, 0.12), (0.0, 0.03, 0.014), lens=55, key=lamp, fill=fill, rim=rim),
         lit_closeup('laptop_c_hinge', (0.28, 0.02, 0.06), (0.12, 0.10, 0.016), lens=60, key=lamp, fill=fill, rim=rim)]
# closed pose
lid.rotation_euler = (0.0, 0, 0)
bpy.context.view_layer.update()
shots.append(lit_closeup('laptop_c_closed', (0.30, -0.45, 0.28), (0.0, 0.0, 0.01), lens=45, key=lamp, fill=fill, rim=rim))
sheet(shots, 'laptop_closeups.png', cols=2)
