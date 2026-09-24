"""Claude's Corner - the open notebook. A brown leather hardcover lying open flat: ONE cover mass
(two boards + hinge grooves + spine strip), the page block's head/tail/fore-edge walls following the
page curve (striated edges), headbands at the gutter ends, and a red satin ribbon lying in the
gutter and spilling over the writer's edge onto the desk. 'NotebookCover' is baked.
'NotebookPages' = both pages as ONE curved surface with a flat 'PAGE' material (the engine paints
paper + ink on it); UV is a planar top projection across the spread.
Origin: spread centre at desk height (z=0). Long axis X. Writer at -Y.

Page surface:  z(x) = 0.0025 + 0.0012 + 0.0095*(1 - exp(-|x|/0.016)) - 0.0022*(|x|/0.155)^2
for |x| <= 0.155, |y| <= 0.1075.  Min 0.0037 (gutter), max ~0.0126 (|x|~0.068), 0.0110 at the outer edges.
"""
import sys, os, math
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import bpy, bmesh
from mathutils import Vector
from clib import *
from props_util import *

reset()
PW, PH = 0.155, 0.215
BT = 0.0025                     # board thickness
SQ = 0.003                      # squares (cover overhang)
GW = 0.0065                     # half-width of the spine strip


def zpage(x):
    a = abs(x)
    return BT + 0.0012 + 0.0095 * (1 - math.exp(-a / 0.016)) - 0.0022 * (a / PW) ** 2


NX, NY = 120, 18
xs = [PW * math.copysign(abs(s) ** 1.6, s) for s in [-1 + 2 * i / NX for i in range(NX + 1)]]
ys = [-PH / 2 + PH * j / NY for j in range(NY + 1)]

def _stripes(nb, col):
    oc = nb.n('ShaderNodeTexCoord').outputs['Object']
    wv = nb.n('ShaderNodeTexWave', wave_type='BANDS', bands_direction='X')
    wv.inputs['Scale'].default_value = 450.0
    nb.l(oc, wv.inputs['Vector'])
    m = nb.ramp(wv.outputs['Fac'], 0.45, 0.55)
    return nb.mix(m, (0.55, 0.06, 0.07), (0.92, 0.86, 0.72))


leather = layered_mat('leather', 'Leather037', scale=3.5, tint=(0.95, 0.82, 0.70), val=0.95, rough_add=0.04, nstr=1.0,
                      wear=dict(color=(0.55, 0.38, 0.25), radius=0.0012, amount=1.0, rough=0.65, gain=24, noise=60),
                      grime=dict(color=(0.07, 0.04, 0.025), dist=0.004, amount=0.8, gain=2.2))


def page_edge(nb, col, vec):
    # striated page edges: signatures + sheets, darker toward the top (dust) and the gutter
    oc = nb.n('ShaderNodeTexCoord').outputs['Object']
    wv = nb.n('ShaderNodeTexWave', wave_type='BANDS', bands_direction='Z')
    wv.inputs['Scale'].default_value = 260.0
    wv.inputs['Distortion'].default_value = 3.0
    wv.inputs['Detail'].default_value = 2.0
    nb.l(oc, wv.inputs['Vector'])
    lines = nb.ramp(wv.outputs['Fac'], 0.25, 0.9)
    col = nb.mix(nb.math('MULTIPLY', nb.math('SUBTRACT', 1.0, lines), 0.38), col, (0.50, 0.44, 0.34))
    sig = nb.n('ShaderNodeTexWave', wave_type='BANDS', bands_direction='Z')
    sig.inputs['Scale'].default_value = 60.0
    nb.l(oc, sig.inputs['Vector'])
    col = nb.mix(nb.math('MULTIPLY', nb.ramp(sig.outputs['Fac'], 0.8, 1.0), 0.18), col, (0.62, 0.56, 0.44))
    return col


paper_edge = layered_mat('pageedge', 'Paper001', scale=8.0, tint=(0.90, 0.82, 0.66), rough_add=0.1, nstr=0.3,
                         extra_color=page_edge,
                         grime=dict(color=(0.55, 0.47, 0.35), dist=0.004, amount=0.5, gain=1.6),
                         dust=dict(color=(0.70, 0.64, 0.52), amount=0.35))
satin = layered_mat('satin', 'Fabric036', scale=40.0, tint=(0.36, 0.018, 0.032), sat=1.3, rough_mul=0.0, rough_add=0.34,
                    nstr=0.15)
hband = layered_mat('headband', 'Fabric036', scale=60.0, rough_add=0.1, nstr=0.8,
                    extra_color=lambda nb, col, vec: _stripes(nb, col))


page_m = flat_mat('PAGE', color=(0.93, 0.90, 0.82), rough=0.85)
parts = []

# ---------------------------------------------------------------- cover: ONE leather-wrapped mass
CW = PW + SQ                   # each board reaches the fore-edge overhang
bm = bmesh.new()
bxs = [-CW, -GW - 0.0015, -GW, -GW + 0.0015, GW - 0.0015, GW, GW + 0.0015, CW]
# a cross-section with two shallow hinge grooves, extruded along Y
prof = []
for x in bxs:
    ztop = BT
    if abs(abs(x) - GW) < 1e-6:
        ztop = BT - 0.0009       # groove bottom
    prof.append((x, ztop))
Y0, Y1 = -PH / 2 - SQ, PH / 2 + SQ
ring0 = [bm.verts.new((x, Y0, z)) for x, z in prof] + [bm.verts.new((CW, Y0, 0.0)), bm.verts.new((-CW, Y0, 0.0))]
ring1 = [bm.verts.new((x, Y1, z)) for x, z in prof] + [bm.verts.new((CW, Y1, 0.0)), bm.verts.new((-CW, Y1, 0.0))]
n = len(ring0)
order = list(range(len(prof))) + [len(prof), len(prof) + 1]   # top profile, then bottom right, bottom left
for k in range(n):
    a, b = order[k], order[(k + 1) % n]
    bm.faces.new((ring0[a], ring0[b], ring1[b], ring1[a]))
bm.faces.new([ring0[i] for i in order][::-1])
bm.faces.new([ring1[i] for i in order])
bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
cover = obj_from_bm('cover', bm, leather)
finish(cover, bevel=0.0007, segments=3, angle=35)
uv_tex(cover, 1.0)
parts.append(cover)

# ---------------------------------------------------------------- page block walls (follow the page curve)
bm = bmesh.new()
for yy, flip in ((-PH / 2, False), (PH / 2, True)):       # tail (writer side) and head walls
    top = [bm.verts.new((x, yy, zpage(x))) for x in xs]
    bot = [bm.verts.new((x, yy, BT)) for x in xs]
    for i in range(NX):
        f = (bot[i], bot[i + 1], top[i + 1], top[i])
        bm.faces.new(f[::-1] if flip else f)
for xx, flip in ((-PW, True), (PW, False)):               # fore-edges
    top = [bm.verts.new((xx, y, zpage(xx))) for y in ys]
    bot = [bm.verts.new((xx, y, BT)) for y in ys]
    for j in range(NY):
        f = (bot[j], bot[j + 1], top[j + 1], top[j])
        bm.faces.new(f if flip else f[::-1])
bmesh.ops.remove_doubles(bm, verts=bm.verts, dist=1e-7)
bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
walls = obj_from_bm('pagewalls', bm, paper_edge)
# make sure normals point outward (away from the block centre)
for p in walls.data.polygons:
    c = p.center
    out = Vector((c.x, c.y, 0))
    if abs(c.x) > PW - 1e-4:
        out = Vector((c.x, 0, 0))
    elif abs(c.y) > PH / 2 - 1e-4:
        out = Vector((0, c.y, 0))
    if p.normal.dot(out) < 0:
        p.flip()
smooth(walls, 30)
uv_tex(walls, 0.05)
parts.append(walls)

# ---------------------------------------------------------------- headbands at the gutter ends
for yy in (-PH / 2 - 0.0006, PH / 2 + 0.0006):
    bpy.ops.mesh.primitive_cylinder_add(vertices=16, radius=0.0014, depth=0.013, location=(0, yy, zpage(0) + 0.0004),
                                        rotation=(0, math.radians(90), 0))
    hb = bpy.context.object
    hb.data.materials.append(hband)
    smooth(hb, 50)
    uv_tex(hb, 0.02)
    parts.append(hb)

# ---------------------------------------------------------------- satin ribbon (V in the gutter, flat on the desk)
path = [Vector((0.0, 0.035, 0)), Vector((0.0, -0.02, 0)), Vector((0.0, -PH / 2 + 0.002, 0)),
        Vector((0.0005, -PH / 2 - 0.0035, 0)), Vector((0.002, -PH / 2 - SQ - 0.002, 0)),
        Vector((0.006, -0.128, 0)), Vector((0.015, -0.142, 0)), Vector((0.021, -0.151, 0))]
samp = bezier_points([tuple(p) for p in path], 12)
RW = 0.0062
bm = bmesh.new()
rows = []
for i, p in enumerate(samp):
    y = p.y
    if y > -PH / 2:
        # lying in the gutter: follow the page surface across the width (a shallow V)
        pts = [(p.x + dx, y, zpage(p.x + dx) + 0.0003) for dx in (-RW / 2, 0.0, RW / 2)]
    else:
        # over the edge, down the cover, onto the desk
        over = (-PH / 2 - y)
        t = min(1.0, max(0.0, over / 0.0068))
        sm = t * t * (3 - 2 * t)
        zc = 0.00035 + (zpage(0) + 0.0003 - 0.00035) * (1 - sm)
        if over <= SQ:
            zc = max(zc, BT + 0.0003)
        pts = [(p.x - RW / 2, y, zc + 0.0002), (p.x, y, zc), (p.x + RW / 2, y, zc + 0.00015)]
    rows.append([bm.verts.new(q) for q in pts])
for i in range(len(rows) - 1):
    a, b = rows[i], rows[i + 1]
    for k in range(2):
        bm.faces.new((a[k], a[k + 1], b[k + 1], b[k]))
rib = obj_from_bm('ribbon', bm, satin)
sol = rib.modifiers.new('sol', 'SOLIDIFY'); sol.thickness = 0.00028; sol.offset = -1.0
apply_mods(rib)
smooth(rib, 40)
uv_tex(rib, 0.05)
parts.append(rib)

nb_cover = join(parts, 'NotebookCover')
uv_bake(nb_cover, margin=0.003)
bake_and_swap(nb_cover, 'notebook_cover', size=2048, samples=40, ao_dist=0.01)
clean_uvs(nb_cover)

# ---------------------------------------------------------------- the pages: ONE curved surface, engine-painted
bm = bmesh.new()
uvl = bm.loops.layers.uv.new('UVMap')
grid = [[bm.verts.new((x, y, zpage(x))) for x in xs] for y in ys]
for j in range(NY):
    for i in range(NX):
        f = bm.faces.new((grid[j][i], grid[j][i + 1], grid[j + 1][i + 1], grid[j + 1][i]))
        for lp in f.loops:
            co = lp.vert.co
            lp[uvl].uv = ((co.x + PW) / (2 * PW), (co.y + PH / 2) / PH)
pages = obj_from_bm('NotebookPages', bm, page_m)
for p in pages.data.polygons:
    p.use_smooth = True

export_glb([nb_cover, pages], 'corner_notebook.glb')
print('[notebook] page z: min %.4f max %.4f edge %.4f' % (zpage(0), max(zpage(x) for x in xs), zpage(PW)), flush=True)
preview([nb_cover, pages], 'notebook', height=0.9)
lit_closeup('notebook_gutter', (0.07, -0.20, 0.07), (0.0, -0.09, 0.005), lens=55, energy=3)
lit_closeup('notebook_edge', (-0.26, -0.20, 0.06), (-0.14, -0.06, 0.006), lens=60, energy=3)
