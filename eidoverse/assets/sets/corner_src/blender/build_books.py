"""Claude's Corner - a stack of three cloth hardcovers (oxblood / navy / ochre), spines to the front.
Each case is ONE mass: a U cross-section (boards + rounded spine + hinge grooves) extruded along
the height; each page block has a rounded spine side and a concave fore-edge; headbands at both
ends; gilt spine rules stamped into the cloth (no titles). Baked -> glb/corner_books.glb ('Books').
Origin bottom centre of the stack; spines face -Y.
"""
import sys, os, math
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import bpy, bmesh
from mathutils import Vector, Matrix
from clib import *
from props_util import *

reset()
BT, SQ = 0.0022, 0.003
GILT = [0.070, 0.086, 0.300, 0.314, 0.686, 0.700, 0.914, 0.930]


def gilt_hook(state):
    def hook(nb, col, vec):
        uvn = nb.n('ShaderNodeUVMap', uv_map='BookUV')
        sep = nb.n('ShaderNodeSeparateXYZ'); nb.l(uvn.outputs[0], sep.inputs[0])
        u, v = sep.outputs['X'], sep.outputs['Y']
        spine = nb.math('LESS_THAN', v, state['vspine'])
        m = None
        for g in GILT:
            b = nb.math('SUBTRACT', 1.0, nb.math('MULTIPLY', nb.math('ABSOLUTE', nb.math('SUBTRACT', u, g)), 420.0), clamp=True)
            m = b if m is None else nb.math('MAXIMUM', m, b)
        m = nb.math('MULTIPLY', nb.ramp(m, 0.35, 0.6), spine)
        worn = nb.ramp(nb.noise(nb.n('ShaderNodeTexCoord').outputs['Object'], 300.0, 3.0, 0.5), 0.25, 0.55)
        m = nb.math('MULTIPLY', m, worn)
        state['mask'] = m
        return nb.mix(m, col, (0.78, 0.55, 0.22))
    return hook


def cloth(name, tint, vspine):
    st = {'vspine': vspine}
    m = layered_mat(name, 'Fabric030', scale=16.0, tint=tint, sat=0.85, rough_add=0.08, nstr=0.7, metal=0.0,
                    extra_color=gilt_hook(st),
                    wear=dict(color=tuple(min(1.0, c * 1.9 + 0.06) for c in tint), radius=0.0012, amount=0.9, rough=0.9,
                              gain=22, noise=70),
                    grime=dict(color=tuple(c * 0.35 for c in tint), dist=0.006, amount=0.6, gain=2.0),
                    dust=dict(color=(0.55, 0.52, 0.47), amount=0.10))
    nt = m.node_tree
    for key, val in (('OUT_METAL', 1.0), ('OUT_ROUGH', 0.28)):
        rr = nt.nodes[key]
        src = rr.inputs[0].links[0].from_socket
        mx = nt.nodes.new('ShaderNodeMixRGB')
        nt.links.new(st['mask'], mx.inputs[0]); nt.links.new(src, mx.inputs[1]); mx.inputs[2].default_value = (val, val, val, 1)
        nt.links.new(mx.outputs[0], rr.inputs[0])
    return m


def pages_layer(nb, col, vec):
    oc = nb.n('ShaderNodeTexCoord').outputs['Object']
    wv = nb.n('ShaderNodeTexWave', wave_type='BANDS', bands_direction='Z')
    wv.inputs['Scale'].default_value = 220.0
    wv.inputs['Distortion'].default_value = 3.0
    nb.l(oc, wv.inputs['Vector'])
    return nb.mix(nb.math('MULTIPLY', nb.math('SUBTRACT', 1.0, nb.ramp(wv.outputs['Fac'], 0.3, 0.9)), 0.35), col, (0.45, 0.39, 0.29))


pagesm = layered_mat('bookpages', 'Paper001', scale=8.0, tint=(0.82, 0.72, 0.54), rough_add=0.1, nstr=0.3,
                     extra_color=pages_layer,
                     grime=dict(color=(0.40, 0.32, 0.22), dist=0.004, amount=0.6, gain=1.8),
                     dust=dict(color=(0.55, 0.50, 0.42), amount=0.4))


def hb_layer(nb, col, vec):
    oc = nb.n('ShaderNodeTexCoord').outputs['Object']
    wv = nb.n('ShaderNodeTexWave', wave_type='BANDS', bands_direction='Z')
    wv.inputs['Scale'].default_value = 520.0
    nb.l(oc, wv.inputs['Vector'])
    return nb.mix(nb.ramp(wv.outputs['Fac'], 0.45, 0.55), (0.45, 0.04, 0.05), (0.80, 0.72, 0.55))


hbm = layered_mat('headband', 'Fabric036', scale=60.0, rough_add=0.1, nstr=0.8, extra_color=hb_layer)


def extrude_profile(bm, prof, y0, y1, uvbook=None, H=1.0, W=1.0):
    r0 = [bm.verts.new((x, y0, z)) for x, z in prof]
    r1 = [bm.verts.new((x, y1, z)) for x, z in prof]
    n = len(prof)
    for k in range(n):
        bm.faces.new((r0[k], r0[(k + 1) % n], r1[(k + 1) % n], r1[k]))
    bm.faces.new(r0[::-1])
    bm.faces.new(r1)


def set_bookuv(o, H, W):
    me = o.data
    if 'BookUV' not in me.uv_layers:
        me.uv_layers.new(name='BookUV')
    uvl = me.uv_layers['BookUV']
    for li, lp in enumerate(me.loops):
        co = me.vertices[lp.vertex_index].co
        uvl.data[li].uv = (co.y / H + 0.5, co.x / W)


def book(H, W, T, clothm):
    xc = T / 2
    parts = []
    # ---- case cross-section (closed), hinge grooves on both boards
    out_top = [(W, T), (xc + 0.0095, T), (xc + 0.0078, T - 0.0008), (xc + 0.0058, T - 0.0008), (xc + 0.0042, T), (xc, T)]
    arc_out = [(xc - (T / 2) * math.sin(math.radians(a)), T / 2 + (T / 2) * math.cos(math.radians(a))) for a in range(10, 180, 10)]
    out_bot = [(xc, 0.0), (xc + 0.0042, 0.0), (xc + 0.0058, 0.0008), (xc + 0.0078, 0.0008), (xc + 0.0095, 0.0), (W, 0.0)]
    ri = T / 2 - BT
    in_bot = [(W, BT), (xc, BT)]
    arc_in = [(xc - ri * math.sin(math.radians(a)), T / 2 - ri * math.cos(math.radians(a))) for a in range(10, 180, 10)]
    in_top = [(xc, T - BT), (W, T - BT)]
    prof = out_top + arc_out + out_bot + in_bot + arc_in + in_top
    bm = bmesh.new()
    extrude_profile(bm, prof, -H / 2, H / 2)
    bmesh.ops.remove_doubles(bm, verts=bm.verts, dist=1e-7)
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
    case = obj_from_bm('case', bm, clothm)
    finish(case, bevel=0.0006, segments=2, angle=40)
    set_bookuv(case, H, W)
    uv_tex(case, 1.0)
    parts.append(case)
    # ---- page block: rounded spine side, concave fore-edge
    e = 0.00025
    rp = ri - e
    top = [(W - SQ, T - BT - e), (xc, T - BT - e)]
    arc = [(xc - rp * math.sin(math.radians(a)), T / 2 + rp * math.cos(math.radians(a))) for a in range(10, 180, 10)]
    bot = [(xc, BT + e), (W - SQ, BT + e)]
    fore = []
    for k in range(1, 12):
        z = BT + e + (T - 2 * BT - 2 * e) * k / 12
        s = (z - T / 2) / (T / 2 - BT)
        fore.append((W - SQ - 0.0025 * (1 - s * s), z))
    pprof = top + arc + bot + fore
    bm = bmesh.new()
    extrude_profile(bm, pprof, -H / 2 + SQ, H / 2 - SQ)
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
    pb = obj_from_bm('pages', bm, pagesm)
    finish(pb, bevel=0.0004, segments=1, angle=50)
    set_bookuv(pb, H, W)
    uv_tex(pb, 0.3)
    parts.append(pb)
    # ---- headbands: little rolls following the spine arc at each end
    for ys in (-1, 1):
        yy = ys * (H / 2 - SQ + 0.0006)
        pts = [(xc - (rp - 0.0006) * math.sin(math.radians(a)), yy, T / 2 + (rp - 0.0006) * math.cos(math.radians(a)))
               for a in range(20, 165, 8)]
        hb = tube_obj('hb', pts, 0.0011, hbm, caps=True)
        set_bookuv(hb, H, W)
        uv_tex(hb, 0.02)
        parts.append(hb)
    return parts


specs = [  # H, W, T, cloth tint (linear), yaw deg, dx, dy
    (0.235, 0.160, 0.034, (0.26, 0.018, 0.025), 3.0, 0.000, 0.000),
    (0.215, 0.145, 0.028, (0.018, 0.035, 0.12), -5.0, 0.006, -0.004),
    (0.195, 0.132, 0.022, (0.50, 0.26, 0.035), 8.0, -0.005, 0.007),
]
allp = []
z = 0.0
for i, (H, W, T, tint, yaw, dx, dy) in enumerate(specs):
    cm = cloth(f'cloth{i}', tint, (T / 2) / W)
    ps = book(H, W, T, cm)
    M = Matrix.Translation((dx, dy, z)) @ Matrix.Rotation(math.radians(90 + yaw), 4, 'Z') @ Matrix.Translation((-W / 2, 0, 0))
    for o in ps:
        o.data.transform(M)
    allp += ps
    z += T
books = join(allp, 'Books')
uv_bake(books, margin=0.003)
bake_and_swap(books, 'books', size=2048, samples=40, ao_dist=0.03)
clean_uvs(books)
export_glb([books], 'corner_books.glb')
preview([books], 'books', height=0.45)
lit_closeup('books_spines', (0.05, -0.30, 0.10), (0.0, -0.06, 0.04), lens=55, energy=4)
lit_closeup('books_corner', (0.22, 0.10, 0.14), (0.08, 0.06, 0.05), lens=55, energy=4)
