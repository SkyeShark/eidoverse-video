"""Claude's Corner - the window. A traditional painted-wood double-hung window in a 1.00 x 1.25 m
opening of a 0.16 m wall.

Wall = Blender XZ plane at y = 0; ROOM side is -Y, outside +Y. ORIGIN = centre of the opening on
the room-side wall plane (opening x in [-0.5, 0.5], z in [-0.625, 0.625]).

Construction (what a joiner would make, one mass per real part):
  - two sashes, each ONE slab with its 2x2 pane openings pushed through (grid_slab), ovolo
    sticking on the room side of every opening, glazing chamfer outside
  - jamb liners over the reveal, interior stops / parting beads / blind stops in their channels
  - interior casing (profiled), head casing with a bullnose cap, stool with a rounded nose and
    horns, apron, sloped exterior sill with a drip kerf
  - brass crescent sash lock + keeper on the meeting rails, two brass bail lifts
Buried faces (against the wall, on the stool, under the cap) are deleted before bevelling.
Paint: PaintedWood009C in cream, chipped/worn edges showing wood, cavity grime, sill dust.
Exports glb/corner_window.glb: 'WindowFrame' (baked 2K) + 'WindowGlass' (flat 'GLASS').
"""
import sys, os, math
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import bpy, bmesh
from mathutils import Vector
from clib import *
from helpers_wcl import *

reset()
EPS = 1e-5
LOOKDEV_ONLY = os.environ.get('WIN_LOOKDEV') == '1'

def paint_color(nb, col, vec):
    """Thick old paint over wood: the grain only telegraphs (38%), plus faint brush strokes."""
    c = nb.mix(0.62, col, (0.80, 0.765, 0.665))
    mp = nb.n('ShaderNodeMapping')
    mp.inputs['Scale'].default_value = (2.0, 45.0, 2.0)
    nb.l(vec, mp.inputs['Vector'])
    strokes = nb.ramp(nb.noise(mp.outputs[0], 3.0, 3.0, 0.5), 0.3, 0.7)
    return nb.mix(nb.math('MULTIPLY', strokes, 0.06), c, (1.0, 0.98, 0.93))


m_paint = layered_mat('paint', 'PaintedWood009C', scale=1.15, extra_color=paint_color,
                      rough_mul=0.62, rough_add=0.02, nstr=0.45,
                      wear=dict(color=(0.47, 0.52, 0.45), radius=0.003, amount=1.0, rough=0.6, noise=26, gain=16),
                      grime=dict(color=(0.27, 0.23, 0.17), dist=0.04, amount=0.9, rough=0.2, gain=2.4, noise=6),
                      dust=dict(color=(0.62, 0.59, 0.54), amount=0.32, noise=14))


def chip_mask(nb):
    """Deeper chips down to bare wood: tight edge band x sparse spots."""
    geo = nb.n('ShaderNodeNewGeometry')
    bev = nb.n('ShaderNodeBevel', samples=8)
    bev.inputs['Radius'].default_value = 0.002
    dp = nb.n('ShaderNodeVectorMath', operation='DOT_PRODUCT')
    nb.l(bev.outputs['Normal'], dp.inputs[0]); nb.l(geo.outputs['Normal'], dp.inputs[1])
    edge = nb.math('MULTIPLY', nb.math('SUBTRACT', 1.0, dp.outputs['Value']), 30.0, clamp=True)
    oc = nb.n('ShaderNodeTexCoord').outputs['Object']
    spots = nb.ramp(nb.noise(oc, 55.0, 4.0, 0.6), 0.60, 0.66)
    return nb.math('MULTIPLY', edge, spots)


def touch_wear(nb):
    """hands lift the lower sash and rest on the stool: extra wear low on the window."""
    geo = nb.n('ShaderNodeNewGeometry')
    bev = nb.n('ShaderNodeBevel', samples=8)
    bev.inputs['Radius'].default_value = 0.004
    dp = nb.n('ShaderNodeVectorMath', operation='DOT_PRODUCT')
    nb.l(bev.outputs['Normal'], dp.inputs[0]); nb.l(geo.outputs['Normal'], dp.inputs[1])
    edge = nb.math('MULTIPLY', nb.math('SUBTRACT', 1.0, dp.outputs['Value']), 12.0, clamp=True)
    oc, sep = obj_sep(nb)
    low = maprange(nb, sep.outputs['Z'], -0.47, -0.54)     # 1 below z=-0.54 (stool, bottom rail)
    brk = nb.ramp(nb.noise(oc, 30.0, 5.0, 0.62), 0.45, 0.6)
    return nb.math('MULTIPLY', nb.math('MULTIPLY', edge, low), brk)


def sill_cracks(nb):
    """sun-crazed paint on up-facing faces: voronoi hairlines in patches."""
    geo = nb.n('ShaderNodeNewGeometry')
    oc, sep = obj_sep(nb)
    nz = nb.n('ShaderNodeSeparateXYZ'); nb.l(geo.outputs['Normal'], nz.inputs[0])
    up = nb.ramp(nz.outputs['Z'], 0.7, 0.95)
    vor = nb.n('ShaderNodeTexVoronoi', feature='DISTANCE_TO_EDGE')
    vor.inputs['Scale'].default_value = 110.0
    nb.l(oc, vor.inputs['Vector'])
    lines = nb.ramp(vor.outputs['Distance'], 0.0, 0.035, (1, 1, 1, 1), (0, 0, 0, 1))
    patch = nb.ramp(nb.noise(oc, 6.0, 3.0, 0.5), 0.5, 0.62)
    return nb.math('MULTIPLY', nb.math('MULTIPLY', nb.math('MULTIPLY', lines, up), patch), 0.55)


post_layer(m_paint, 'color', chip_mask, (0.36, 0.27, 0.19))
post_layer(m_paint, 'rough', chip_mask, 0.78)
post_layer(m_paint, 'color', touch_wear, (0.50, 0.53, 0.46))
post_layer(m_paint, 'rough', touch_wear, 0.55)
post_layer(m_paint, 'color', sill_cracks, (0.42, 0.39, 0.33))
m_brass = layered_mat('brass', 'Metal048B', scale=6.0, tint=(0.72, 0.52, 0.29), metal=1.0, rough_mul=0.85, rough_add=0.12,
                      wear=dict(color=(1.0, 0.84, 0.55), radius=0.0012, amount=1.0, rough=0.2, metal=1.0, gain=24),
                      grime=dict(color=(0.09, 0.07, 0.035), dist=0.008, amount=0.85, gain=2.2))
m_glass = flat_mat('GLASS', (0.86, 0.92, 0.94), rough=0.04, alpha=0.18)

parts = []


def near(a, b, eps=EPS):
    return abs(a - b) < eps


def mk(name, bm, mat=None, bevel=0.0015, segs=2, angle=40, tex='cube', axis='X', buried=()):
    if buried:
        bury(bm, *buried)
    o = obj_from_bm(name, bm, mat or m_paint)
    finish(o, bevel=bevel, segments=segs, angle=angle)
    if tex == 'cube':
        uv_tex(o, 1.0 if mat is None or mat is m_paint else 0.2)
    else:
        uv_tex_axis(o, axis, 1.0)
    parts.append(o)
    return o


# =============================================================================== sashes
SX0, SX1 = -0.4765, 0.4765
XS = [SX0, -0.4245, -0.011, 0.011, 0.4245, SX1]
HOLES = {(1, 1), (3, 1), (1, 3), (3, 3)}


def sash(name, y0, y1, zs):
    """ONE slab, 2x2 pane openings pushed through; ovolo sticking room side, glazing chamfer outside."""
    bm = bmesh.new()
    grid_slab(bm, XS, zs, HOLES, y0, y1)
    zlo, zhi = zs[0], zs[-1]
    bm.normal_update()

    def opening_edges(yface):
        out = []
        for e in bm.edges:
            a, b = e.verts[0].co, e.verts[1].co
            if not (near(a.y, yface) and near(b.y, yface)):
                continue
            mx, mz = (a.x + b.x) / 2, (a.z + b.z) / 2
            if not ((SX0 + 0.01 < mx < SX1 - 0.01) and (zlo + 0.01 < mz < zhi - 0.01)):
                continue
            if any(abs(f.normal.y) < 0.5 for f in e.link_faces):
                out.append(e)
        return out
    fe = opening_edges(y0)
    bmesh.ops.bevel(bm, geom=fe, offset=0.0055, offset_type='OFFSET', segments=3, profile=0.5,
                    affect='EDGES', clamp_overlap=True)
    bm.normal_update()
    be = opening_edges(y1)
    bmesh.ops.bevel(bm, geom=be, offset=0.004, offset_type='OFFSET', segments=1, profile=0.5,
                    affect='EDGES', clamp_overlap=True)
    print(f'[window] {name}: ovolo edges {len(fe)}, glazing edges {len(be)}', flush=True)
    return mk(name, bm, bevel=0.0012, segs=2, angle=40, tex='cube')


LOW_Y = (0.0595, 0.0995)
UP_Y = (0.1075, 0.1475)
LOW_Z = [-0.600, -0.532, -0.287, -0.265, -0.020, 0.020]
UP_Z = [-0.020, 0.020, 0.275, 0.297, 0.552, 0.605]
sash('sash_lower', LOW_Y[0], LOW_Y[1], LOW_Z)
sash('sash_upper', UP_Y[0], UP_Y[1], UP_Z)

# ======================================================================= liners + beads
for sx in (-1, 1):
    x0, x1 = sorted((sx * 0.480, sx * 0.500))
    mk('liner_side', box_obj('l', x0, x1, 0.0, 0.160, -0.600, 0.605), tex='axis', axis='Z',
       buried=(lambda c, n: abs(n.x) > 0.9 and abs(c.x) > 0.499, lambda c, n: abs(n.z) > 0.9))
mk('liner_head', box_obj('l', -0.500, 0.500, 0.0, 0.160, 0.605, 0.625), tex='axis', axis='X',
   buried=(lambda c, n: n.z > 0.9,))


def bead(name, ya, yb, round_front=False, round_back=False):
    for sx in (-1, 1):
        x0, x1 = sorted((sx * 0.468, sx * 0.480))
        bm = box_obj(name, x0, x1, ya, yb, -0.600, 0.593)
        bury(bm, lambda c, n: abs(n.x) > 0.9 and abs(c.x) > 0.479, lambda c, n: abs(n.z) > 0.9)
        if round_front:
            bevel_edges(bm, lambda a, b: near(a.y, ya) and near(b.y, ya) and near(a.x, sx * 0.468)
                        and near(b.x, sx * 0.468), 0.0045, 3, 0.5)
        if round_back:
            bevel_edges(bm, lambda a, b: near(a.y, yb) and near(b.y, yb) and near(a.x, sx * 0.468)
                        and near(b.x, sx * 0.468), 0.003, 2, 0.5)
        mk(name, bm, tex='axis', axis='Z', bevel=0.0008, segs=1)
    bm = box_obj(name + '_head', -0.480, 0.480, ya, yb, 0.593, 0.605)
    bury(bm, lambda c, n: n.z > 0.9, lambda c, n: abs(n.x) > 0.9)
    if round_front:
        bevel_edges(bm, lambda a, b: near(a.y, ya) and near(b.y, ya) and near(a.z, 0.593) and near(b.z, 0.593),
                    0.0045, 3, 0.5)
    mk(name + '_head', bm, tex='axis', axis='X', bevel=0.0008, segs=1)


bead('stop_int', 0.040, 0.058, round_front=True)
bead('parting', 0.1005, 0.1070, round_front=True, round_back=True)
bead('stop_blind', 0.1485, 0.160)

# ================================================================================ casing
CI, CO = 0.486, 0.561
for sx in (-1, 1):
    x0, x1 = sorted((sx * CI, sx * CO))
    bm = box_obj('casing', x0, x1, -0.020, 0.0, -0.600, 0.611)
    bury(bm, lambda c, n: n.y > 0.9, lambda c, n: abs(n.z) > 0.9)
    bevel_edges(bm, lambda a, b: near(a.y, -0.02) and near(b.y, -0.02) and near(a.x, sx * CO) and near(b.x, sx * CO),
                0.009, 4, 0.5)
    bevel_edges(bm, lambda a, b: near(a.y, -0.02) and near(b.y, -0.02) and near(a.x, sx * CI) and near(b.x, sx * CI),
                0.0025, 2, 0.5)
    mk('casing_side', bm, tex='axis', axis='Z', bevel=0.0008, segs=1)
HX = 0.571
bm = box_obj('casing_head', -HX, HX, -0.024, 0.0, 0.611, 0.701)
bury(bm, lambda c, n: n.y > 0.9, lambda c, n: n.z > 0.9)
bevel_edges(bm, lambda a, b: near(a.y, -0.024) and near(b.y, -0.024) and near(a.z, 0.701) and near(b.z, 0.701), 0.006, 3, 0.5)
bevel_edges(bm, lambda a, b: near(a.y, -0.024) and near(b.y, -0.024) and near(a.z, 0.611) and near(b.z, 0.611), 0.0025, 2, 0.5)
mk('casing_head', bm, tex='axis', axis='X', bevel=0.001, segs=1)
CAPX = 0.583
bm = box_obj('cap', -CAPX, CAPX, -0.034, 0.0, 0.701, 0.714)
bury(bm, lambda c, n: n.y > 0.9)
bevel_edges(bm, lambda a, b: near(a.y, -0.034) and near(b.y, -0.034) and near(a.z, 0.714) and near(b.z, 0.714), 0.0075, 4, 0.5)
bevel_edges(bm, lambda a, b: near(a.y, -0.034) and near(b.y, -0.034) and near(a.z, 0.701) and near(b.z, 0.701), 0.003, 2, 0.5)
mk('cap', bm, tex='axis', axis='X', bevel=0.001, segs=1)

# ================================================================== stool, apron, sill
bm = bmesh.new()
polygon_prism(bm, [(-0.60, -0.065), (0.60, -0.065), (0.60, 0.0), (0.50, 0.0), (0.50, 0.058),
                   (-0.50, 0.058), (-0.50, 0.0), (-0.60, 0.0)], -0.625, -0.600)
bury(bm, lambda c, n: n.y > 0.9 and c.y > 0.0575, lambda c, n: n.y > 0.9 and abs(c.x) > 0.5,
     lambda c, n: abs(n.x) > 0.9 and abs(c.x) < 0.51 and c.y > 0.001)
bevel_edges(bm, lambda a, b: near(a.y, -0.065) and near(b.y, -0.065) and near(a.z, -0.600) and near(b.z, -0.600), 0.011, 5, 0.5)
bevel_edges(bm, lambda a, b: near(a.y, -0.065) and near(b.y, -0.065) and near(a.z, -0.625) and near(b.z, -0.625), 0.005, 3, 0.5)
bevel_edges(bm, lambda a, b: abs(a.x) > 0.599 and abs(b.x) > 0.599 and near(a.x, b.x) and near(a.y, -0.065)
            and near(b.y, -0.065), 0.006, 3, 0.5)
mk('stool', bm, tex='axis', axis='X', bevel=0.0012, segs=2, angle=40)

bm = box_obj('apron', -CO, CO, -0.018, 0.0, -0.705, -0.625)
bury(bm, lambda c, n: n.y > 0.9, lambda c, n: n.z > 0.9)
bevel_edges(bm, lambda a, b: near(a.y, -0.018) and near(b.y, -0.018) and near(a.z, -0.705) and near(b.z, -0.705), 0.006, 3, 0.5)
mk('apron', bm, tex='axis', axis='X', bevel=0.001, segs=1)

# exterior sill: flat under the sashes, sloped outside, drip kerf underneath (profile along X)
prof = [(0.058, -0.625), (0.150, -0.625), (0.166, -0.625), (0.166, -0.6205), (0.170, -0.6205), (0.170, -0.625),
        (0.196, -0.625), (0.198, -0.614), (0.196, -0.611), (0.150, -0.600), (0.058, -0.600)]
bm = bmesh.new()
Lv = [bm.verts.new((-0.5, y, z)) for y, z in prof]
Rv = [bm.verts.new((0.5, y, z)) for y, z in prof]
bm.faces.new(Lv)
bm.faces.new(list(reversed(Rv)))
for i in range(len(prof)):
    j = (i + 1) % len(prof)
    bm.faces.new((Lv[i], Rv[i], Rv[j], Lv[j]))
bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
mk('sill_ext', bm, tex='axis', axis='X', bevel=0.0012, segs=2, angle=35,
   buried=(lambda c, n: n.y < -0.9 and c.y < 0.0585, lambda c, n: abs(n.x) > 0.9))

# =============================================================================== hardware
def brass(name, bm, buried=()):
    return mk(name, bm, mat=m_brass, bevel=0.0006, segs=2, angle=35, tex='cube', buried=buried)


def brass_lathe(name, prof, loc, rot=(0, 0, 0), segs=24):
    o = lathe_obj(name, prof, segs, m_brass)
    xform(o, loc, rot)
    uv_tex(o, 0.2)
    parts.append(o)
    return o


LOCK_Y, KEEP_Y, RAIL_TOP = 0.0885, 0.1165, 0.020
bm = bmesh.new()
pts = []
for s in range(13):
    a = -math.pi / 2 + s * math.pi / 12
    pts.append((0.021 + 0.0095 * math.cos(a), LOCK_Y + 0.0095 * math.sin(a)))
for s in range(13):
    a = math.pi / 2 + s * math.pi / 12
    pts.append((-0.021 + 0.0095 * math.cos(a), LOCK_Y + 0.0095 * math.sin(a)))
polygon_prism(bm, pts, RAIL_TOP, RAIL_TOP + 0.0035)
bury(bm, lambda c, n: n.z < -0.9)
bevel_edges(bm, lambda a, b: near(a.z, RAIL_TOP + 0.0035) and near(b.z, RAIL_TOP + 0.0035), 0.0012, 2, 0.5)
brass('lock_base', bm)
for sx in (-1, 1):
    brass_lathe('screw', [(0.0001, 0), (0.0026, 0), (0.0024, 0.0008), (0.0014, 0.0013), (0.0001, 0.0015)],
                (sx * 0.021, LOCK_Y, RAIL_TOP + 0.0035), segs=16)
brass_lathe('boss', [(0.0001, 0), (0.0055, 0), (0.0055, 0.004), (0.004, 0.0052), (0.0001, 0.0055)],
            (0.0, LOCK_Y, RAIL_TOP + 0.0035))
bm = bmesh.new()
ro, ri = 0.030, 0.021
outer = [(ro * math.cos(math.radians(15 + 150 * s / 20)), ro * math.sin(math.radians(15 + 150 * s / 20))) for s in range(21)]
inner = [(ri * math.cos(math.radians(165 - 150 * s / 20)), ri * math.sin(math.radians(165 - 150 * s / 20))) for s in range(21)]
polygon_prism(bm, [(x, LOCK_Y + y) for x, y in outer + inner], RAIL_TOP + 0.0045, RAIL_TOP + 0.0075)
brass('crescent', bm)
arm = tube_obj('lever', [(0.0, LOCK_Y, RAIL_TOP + 0.0072), (0.020, LOCK_Y - 0.004, RAIL_TOP + 0.0075),
                         (0.036, LOCK_Y - 0.006, RAIL_TOP + 0.0085)], 0.0022, m_brass)
uv_tex(arm, 0.2); parts.append(arm)
brass_lathe('lever_knob', [(0.0001, 0), (0.004, 0.0005), (0.0048, 0.003), (0.004, 0.0055), (0.0001, 0.006)],
            (0.038, LOCK_Y - 0.006, RAIL_TOP + 0.006), segs=20)
bm = box_obj('keeper', -0.020, 0.020, KEEP_Y - 0.008, KEEP_Y + 0.008, RAIL_TOP, RAIL_TOP + 0.006)
bury(bm, lambda c, n: n.z < -0.9)
bevel_edges(bm, lambda a, b: near(a.z, RAIL_TOP + 0.006) and near(b.z, RAIL_TOP + 0.006), 0.002, 2, 0.5)
brass('keeper', bm)
ZL = (LOW_Z[0] + LOW_Z[1]) / 2
for x in (-0.25, 0.25):
    for dx in (-0.026, 0.026):
        brass_lathe('rosette', [(0.0001, 0), (0.0068, 0), (0.0066, 0.0012), (0.0045, 0.0028), (0.0001, 0.0032)],
                    (x + dx, LOW_Y[0], ZL), (math.radians(90), 0, 0))
    y0 = LOW_Y[0] - 0.002
    pts3 = [(x - 0.026, y0, ZL), (x - 0.026, y0 - 0.011, ZL - 0.004), (x - 0.017, y0 - 0.019, ZL - 0.012),
            (x + 0.017, y0 - 0.019, ZL - 0.012), (x + 0.026, y0 - 0.011, ZL - 0.004), (x + 0.026, y0, ZL)]
    bail = tube_obj('bail', [tuple(p) for p in bezier_points(pts3, 6)], 0.0032, m_brass)
    uv_tex(bail, 0.2); parts.append(bail)

# ================================================================================= glass
gbm = bmesh.new()
for (zs, yg) in ((LOW_Z, LOW_Y[1] - 0.011), (UP_Z, UP_Y[1] - 0.011)):
    for (i, j) in sorted(HOLES):
        x0, x1, z0, z1 = XS[i] - 0.005, XS[i + 1] + 0.005, zs[j] - 0.005, zs[j + 1] + 0.005
        vs = [gbm.verts.new((x0, yg, z0)), gbm.verts.new((x0, yg, z1)), gbm.verts.new((x1, yg, z1)), gbm.verts.new((x1, yg, z0))]
        gbm.faces.new(vs)
gbm.normal_update()
for f in gbm.faces:
    if f.normal.y > 0:
        f.normal_flip()
glass = obj_from_bm('WindowGlass', gbm, m_glass)
uv_planar(glass, 'UVMap', 0, 2)

# ============================================================================== assemble
frame = join(parts, 'WindowFrame')
print('[window] uv maps', strip_uv(frame, keep=('TexUV',)), flush=True)
uv_bake(frame, margin=0.0025, angle=60)
bake_and_swap(frame, 'window', size=2048, samples=40, ao_dist=0.06)
export_glb([frame, glass], 'corner_window.glb')
bpy.ops.wm.save_as_mainfile(filepath=os.path.join(ROOT, 'blend', 'corner_window.blend'))

# ================================================================================ lookdev
# lookdev only: real transmissive glass so the renders show the muntin depth (engine swaps GLASS anyway)
gl = bpy.data.materials.new('glass_lookdev'); gl.use_nodes = True
bsdf = gl.node_tree.nodes.get('Principled BSDF')
bsdf.inputs['Transmission Weight'].default_value = 1.0
bsdf.inputs['Roughness'].default_value = 0.02
bsdf.inputs['IOR'].default_value = 1.5
bsdf.inputs['Base Color'].default_value = (0.92, 0.96, 0.95, 1)
glass.data.materials[0] = gl
preview([frame, glass], 'window', height=0.3)
wall_m = layered_mat('wall_ctx', 'PaintedPlaster017', scale=0.8, tint=(0.52, 0.62, 0.54), rough_mul=1.0)
wall = obj_from_bm('ctx_wall', box_obj('w', -1.3, 1.3, 0.0, 0.16, -1.65, 1.4), wall_m); uv_tex(wall, 1.0)
boolean(wall, cutter_box(-0.5, 0.5, -0.1, 0.3, -0.625, 0.625))
flr = obj_from_bm('ctx_floor', box_obj('f', -1.3, 1.3, -1.8, 0.16, -1.65, -1.625),
                  layered_mat('floor_ctx', 'WoodFloor064', scale=1.0)); uv_tex(flr, 1.0)
obj_from_bm('ctx_sky', box_obj('s', -6, 6, 3.0, 3.05, -4, 4),
            flat_mat('sky', (0.02, 0.03, 0.06), emission=(0.05, 0.08, 0.16, 1.0)))
key = ((-0.9, -1.2, -0.25), 90, 0.4, (1.0, 0.78, 0.52))
fill = ((0.9, -1.8, 0.9), 25, 1.0, (0.75, 0.82, 1.0))
moon = ((0.8, 2.6, 1.4), 300, 0.6, (0.6, 0.7, 1.0))
shots = [lit_closeup('window_c_full', (0.7, -2.6, 0.05), (0.0, 0.05, 0.02), lens=38, key=key, fill=fill, rim=moon),
         lit_closeup('window_c_lock', (0.10, -0.24, 0.17), (0.0, 0.10, 0.024), lens=55,
                     key=((-0.3, -0.5, 0.5), 25, 0.3, (1.0, 0.8, 0.55)), fill=fill, rim=moon),
         lit_closeup('window_c_stool', (0.85, -0.55, -0.40), (0.50, -0.03, -0.60), lens=50, key=key, fill=fill, rim=moon),
         lit_closeup('window_c_muntin', (0.18, -0.42, 0.40), (0.0, 0.07, 0.29), lens=60, key=key, fill=fill, rim=moon)]
sheet(shots, 'window_closeups.png', cols=2)
