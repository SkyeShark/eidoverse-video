"""Claude's Corner - the tea mug. Thrown stoneware: one lathe mass (foot ring, recessed base,
wall, rounded rim, inner well) + a pulled strap handle. Honey-amber reactive glaze that breaks
brown on the rim, iron speckle, a wavy dip line above the raw speckled foot, a tea ring inside
at the liquid line. 'Mug' (baked) + 'Tea' (liquid surface 8 mm below the rim, meniscus, baked).
Origin base centre. Handle on +X.
"""
import sys, os, math
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import bpy, bmesh
from mathutils import Vector
from clib import *
from props_util import *

reset()
RIM = 0.095
TEA_Z = RIM - 0.008


def glaze_layers(nb, col, vec):
    oc = nb.n('ShaderNodeTexCoord').outputs['Object']
    sep = nb.n('ShaderNodeSeparateXYZ'); nb.l(oc, sep.inputs[0])
    # glaze runs: vertical streaks, darker where the glaze ran thick
    mp = nb.n('ShaderNodeMapping'); mp.inputs['Scale'].default_value = (70.0, 70.0, 7.0); nb.l(oc, mp.inputs['Vector'])
    st = nb.ramp(nb.noise(mp.outputs[0], 2.0, 4.0, 0.6), 0.45, 0.75)
    col = nb.mix(nb.math('MULTIPLY', st, 0.45), col, (0.30, 0.085, 0.015))
    # iron speckle through the glaze
    spk = nb.ramp(nb.noise(oc, 900.0, 2.0, 0.5), 0.70, 0.74)
    col = nb.mix(nb.math('MULTIPLY', spk, 0.8), col, (0.16, 0.08, 0.03))
    # glaze pooling: darker amber band just above the dip line
    wav = nb.math('MULTIPLY', nb.noise(oc, 40.0, 3.0, 0.5), 0.004)
    line = nb.math('ADD', 0.0105, wav)
    dz = nb.math('SUBTRACT', sep.outputs['Z'], line)
    pool = nb.math('SUBTRACT', 1.0, nb.math('MULTIPLY', nb.math('ABSOLUTE', nb.math('SUBTRACT', dz, 0.002)), 450.0), clamp=True)
    col = nb.mix(nb.math('MULTIPLY', pool, 0.6), col, (0.16, 0.05, 0.010))
    # raw stoneware below the dip line
    raw = nb.math('LESS_THAN', dz, 0.0)
    clay = nb.mix(nb.ramp(nb.noise(oc, 300.0, 3.0, 0.6), 0.45, 0.6), (0.42, 0.31, 0.20), (0.52, 0.40, 0.27))
    clay = nb.mix(nb.math('MULTIPLY', spk, 0.9), clay, (0.22, 0.15, 0.10))
    col = nb.mix(raw, col, clay)
    # tea ring inside the wall just above the liquid line
    r = nb.math('SQRT', nb.math('ADD', nb.math('MULTIPLY', sep.outputs['X'], sep.outputs['X']),
                                nb.math('MULTIPLY', sep.outputs['Y'], sep.outputs['Y'])))
    inner = nb.math('LESS_THAN', r, 0.0393)
    ring = nb.math('SUBTRACT', 1.0, nb.math('MULTIPLY', nb.math('ABSOLUTE', nb.math('SUBTRACT', sep.outputs['Z'], TEA_Z + 0.0013)), 900.0), clamp=True)
    ring = nb.math('MULTIPLY', nb.math('MULTIPLY', ring, inner), nb.ramp(nb.noise(oc, 120.0, 3.0, 0.5), 0.3, 0.7))
    col = nb.mix(nb.math('MULTIPLY', ring, 0.6), col, (0.25, 0.12, 0.05))
    # stash the raw mask for roughness (read back in _raw_rough)
    GLOBAL['raw'] = raw
    return col


GLOBAL = {}
glaze = layered_mat('glaze', 'Porcelain001', scale=6.0, tint=(0.56, 0.19, 0.040), sat=1.1, rough_mul=0.35, rough_add=0.03,
                    nstr=0.4, extra_color=glaze_layers,
                    wear=dict(color=(0.26, 0.085, 0.022), radius=0.0018, amount=1.0, rough=0.2, gain=14, noise=80),
                    grime=dict(color=(0.20, 0.10, 0.04), dist=0.004, amount=0.5, gain=1.8))
# raw foot is matte: patch OUT_ROUGH with the raw mask
nt = glaze.node_tree
rr = nt.nodes['OUT_ROUGH']
src = rr.inputs[0].links[0].from_socket
mx = nt.nodes.new('ShaderNodeMixRGB'); mx.blend_type = 'MIX'
nt.links.new(GLOBAL['raw'], mx.inputs[0]); nt.links.new(src, mx.inputs[1]); mx.inputs[2].default_value = (0.82, 0.82, 0.82, 1)
nt.links.new(mx.outputs[0], rr.inputs[0])

# ---- body: one thrown mass (outer foot -> wall -> rim -> inner well)
prof = [(0.0005, 0.0026), (0.0275, 0.0026), (0.0292, 0.0012), (0.0302, 0.0), (0.0342, 0.0), (0.0358, 0.0012),
        (0.0367, 0.0040), (0.0384, 0.0120), (0.0403, 0.0300), (0.0417, 0.0550), (0.0424, 0.0800), (0.0426, 0.0900),
        (0.0425, 0.0935), (0.0419, 0.0947), (0.0409, 0.0951), (0.0399, 0.0946), (0.0393, 0.0934), (0.0391, 0.0800),
        (0.0383, 0.0550), (0.0369, 0.0300), (0.0346, 0.0160), (0.0302, 0.0106), (0.0200, 0.0086), (0.0005, 0.0081)]
body = lathe_obj('body', prof[::-1], 72, glaze)
uv_cyl(body, 'Z', 1.0)

# ---- handle: rounded-rect strap swept along a loop on +X, ends buried in the wall
path = bezier_points([(0.0385, 0, 0.0775), (0.0520, 0, 0.0808), (0.0655, 0, 0.0745), (0.0718, 0, 0.0585),
                      (0.0692, 0, 0.0405), (0.0585, 0, 0.0285), (0.0455, 0, 0.0245), (0.0372, 0, 0.0262)], 10)
W2, T2, RC = 0.0060, 0.0038, 0.0022
sec = []
for k in range(24):
    a = k / 24 * math.tau
    cx, cy = math.cos(a), math.sin(a)
    # superellipse-ish rounded rectangle
    px = math.copysign(abs(cx) ** 0.55, cx) * T2
    py = math.copysign(abs(cy) ** 0.55, cy) * W2 * (1 - 0.12 * max(0.0, -px / T2))   # slight taper on the inside
    sec.append((px, py))
bm = bmesh.new()
rings = []
for i, p in enumerate(path):
    t = (path[min(i + 1, len(path) - 1)] - path[max(i - 1, 0)]).normalized()
    side = Vector((0, 1, 0))
    nrm = t.cross(side).normalized()
    thin = 1.0 - 0.18 * math.sin(math.pi * i / (len(path) - 1))        # thinner in the middle of the loop
    rings.append([bm.verts.new(p + nrm * sx * thin + side * sy) for sx, sy in sec])
for i in range(len(rings) - 1):
    a, b = rings[i], rings[i + 1]
    for k in range(len(sec)):
        bm.faces.new((a[k], a[(k + 1) % len(sec)], b[(k + 1) % len(sec)], b[k]))
bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
handle = obj_from_bm('handle', bm, glaze)
smooth(handle, 60)
uv_tex(handle, 0.2)
mug = join([body, handle], 'Mug')
uv_bake(mug, margin=0.004)
bake_and_swap(mug, 'mug', size=1024, samples=40, ao_dist=0.02)
clean_uvs(mug)


# ---- tea: surface with a meniscus lip at the wall
def tea_layer(nb, col, vec):
    oc = nb.n('ShaderNodeTexCoord').outputs['Object']
    sep = nb.n('ShaderNodeSeparateXYZ'); nb.l(oc, sep.inputs[0])
    r = nb.math('SQRT', nb.math('ADD', nb.math('MULTIPLY', sep.outputs['X'], sep.outputs['X']),
                                nb.math('MULTIPLY', sep.outputs['Y'], sep.outputs['Y'])))
    edge = nb.ramp(r, 0.030, 0.0392)
    col = nb.mix(edge, (0.075, 0.032, 0.010), (0.30, 0.15, 0.05))
    dust = nb.ramp(nb.noise(oc, 700.0, 2.0, 0.5), 0.72, 0.76)
    return nb.mix(nb.math('MULTIPLY', dust, 0.5), col, (0.28, 0.17, 0.08))


team = layered_mat('tea', 'Porcelain001', scale=4.0, rough_mul=0.0, rough_add=0.04, nstr=0.0, extra_color=tea_layer)
RIN = 0.03915
bm = bmesh.new()
ctr = bm.verts.new((0, 0, TEA_Z))
rings = []
for j, rr_ in enumerate([0.012, 0.024, 0.032, 0.036, 0.0380, 0.0388, RIN]):
    lift = 0.0011 * max(0.0, (rr_ - 0.034) / (RIN - 0.034)) ** 2
    rings.append([bm.verts.new((rr_ * math.cos(a), rr_ * math.sin(a), TEA_Z + lift))
                  for a in [k * math.tau / 72 for k in range(72)]])
for k in range(72):
    bm.faces.new((ctr, rings[0][k], rings[0][(k + 1) % 72]))
for j in range(len(rings) - 1):
    for k in range(72):
        bm.faces.new((rings[j][k], rings[j + 1][k], rings[j + 1][(k + 1) % 72], rings[j][(k + 1) % 72]))
bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
tea = obj_from_bm('Tea', bm, team)
for p in tea.data.polygons:
    if p.normal.z < 0:
        p.flip()
    p.use_smooth = True
uv_tex(tea, 0.2)
uv_bake(tea, margin=0.004)
bake_and_swap(tea, 'tea', size=512, samples=24, ao_dist=0.01)
clean_uvs(tea)

export_glb([mug, tea], 'corner_mug.glb')
preview([mug, tea], 'mug', height=0.5)
lit_closeup('mug_rim', (0.10, -0.12, 0.16), (0.0, 0.0, 0.07), lens=55, energy=1.5)
lit_closeup('mug_foot', (0.09, -0.13, 0.03), (0.0, 0.0, 0.025), lens=55, energy=1.5)
