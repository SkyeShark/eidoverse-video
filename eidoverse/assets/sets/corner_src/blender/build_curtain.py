"""Claude's Corner - the curtain. A brass rod (d 0.018, 1.4 m with ball finials) on two wall brackets,
11 brass rings with eyelets and pinch clips, and ONE ochre linen panel gathered to the right side:
ripple folds that snake front/back between the clips (the fabric really passes through every clip),
flaring and softening toward a weighted hem. Stitching on the header, leading side hem and bottom
hem; fold crests a little sun-faded, cavities of the folds a little grimy.

ORIGIN = the wall-plane point behind the rod centre (rod axis at y = -0.08, z = 0; room is -Y).
Place it 0.10 above the window opening top, on the wall plane. The panel spans x in [0.29, 0.63]
at the hem (x in [0.33, 0.62] at the header) and ends 15 mm above the stool top
(z = -1.335 vs the stool at -1.35 in this frame). Exports glb/corner_curtain.glb ('Curtain', baked,
single-sided fabric exported doubleSided).
"""
import sys, os, math, random
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import bpy, bmesh
from mathutils import Vector
from clib import *
from helpers_wcl import *

reset()
ROD_Y, ROD_R = -0.080, 0.009
M = 11
X0, XR = 0.33, 0.62
TOP_Z, HEM_Z = -0.032, -1.335
DROP = TOP_Z - HEM_Z
FABRIC_U = 0.78                      # BakeUV share of the fabric (hardware packs into u 0.80..1)


def smoothstep(a, b, x):
    t = max(0.0, min(1.0, (x - a) / (b - a)))
    return t * t * (3 - 2 * t)


# =============================================================================== fabric
def fabric_point(s, t):
    k = s * (M - 1)
    fl = smoothstep(0.04, 1.0, t)
    left = X0 - 0.042 * fl * fl
    right = XR + 0.012 * fl
    # fold positions drift a little as the panel falls (the stack fans out)
    kw = k + 0.20 * math.sin(1.7 * k + 0.9) * fl + 0.10 * math.sin(3.1 * k + 2.0) * fl * fl
    x = left + (right - left) * (kw / (M - 1)) + 0.006 * math.sin(2.2 * t + 0.5) * fl
    # crisp even pleats at the header, softer and more individual toward the hem
    var = 1.0 + (0.30 * math.sin(2.3 * k + 1.1) + 0.15 * math.sin(5.1 * k + 0.3)) * fl
    amp = 0.027 * (1.0 - 0.34 * fl) * var
    ph = math.pi * kw
    wave = math.sin(ph) + 0.16 * math.sin(2 * ph + 0.5) * fl       # rounded crests, tighter troughs
    y = ROD_Y - amp * wave
    y += 0.0035 * math.sin(0.5 * math.pi * k + 3.0 * t) * fl
    y += -0.004 * smoothstep(0.965, 1.0, t) * math.sin(ph)           # the weighted hem rolls a little
    z = TOP_Z - DROP * t + 0.0035 * math.sin(2.1 * k + 0.4) * smoothstep(0.9, 1.0, t)
    y += -0.010 * fl * fl * (1 - s) ** 3                             # leading edge falls forward
    return Vector((x, y, z))


NS, NT = 150, 72
bm = bmesh.new()
grid = [[bm.verts.new(fabric_point(i / NS, j / NT)) for i in range(NS + 1)] for j in range(NT + 1)]
faces = []
for j in range(NT):
    for i in range(NS):
        f = bm.faces.new((grid[j][i], grid[j][i + 1], grid[j + 1][i + 1], grid[j + 1][i]))
        faces.append((f, i, j))
bm.normal_update()
avg_y = sum(f.normal.y for f, _, _ in faces) / len(faces)
if avg_y > 0:                                              # front side faces the room (-Y)
    for f, _, _ in faces:
        f.normal_flip()
# UVs: BakeUV = (s, 1 - t) squeezed into u 0..FABRIC_U ; TexUV = true fabric metres (arc length)
bake_l = bm.loops.layers.uv.new('BakeUV')
tex_l = bm.loops.layers.uv.new('TexUV')
bm.verts.index_update()
ij_of = {}
for j in range(NT + 1):
    for i in range(NS + 1):
        ij_of[grid[j][i].index] = (i, j)
arc = []
for j in range(NT + 1):
    row = [0.0]
    for i in range(NS):
        row.append(row[-1] + (grid[j][i + 1].co - grid[j][i].co).length)
    arc.append(row)
for f, i0, j0 in faces:
    for lp in f.loops:
        i, j = ij_of[lp.vert.index]
        lp[bake_l].uv = (FABRIC_U * i / NS, 1.0 - j / NT)
        lp[tex_l].uv = (arc[j][i], -DROP * j / NT)


def stitches(nb, col, vec):
    """header band + side hem + bottom hem stitching (in fabric metres, TexUV unscaled)."""
    uvn = nb.n('ShaderNodeUVMap', uv_map='TexUV')
    sep = nb.n('ShaderNodeSeparateXYZ'); nb.l(uvn.outputs['UV'], sep.inputs[0])
    u, v = sep.outputs['X'], sep.outputs['Y']                    # v: 0 at the top, -DROP at the hem

    def line(sock, at, w=0.0009):
        d = nb.math('ABSOLUTE', nb.math('SUBTRACT', sock, at))
        return nb.math('SUBTRACT', 1.0, nb.math('MULTIPLY', d, 1.0 / w), clamp=True)

    def dashes(sock, period=0.0042):
        return maprange(nb, nb.math('SINE', nb.math('MULTIPLY', sock, 2 * math.pi / period)), -0.2, 0.3)
    header = nb.math('MULTIPLY', line(v, -0.062), dashes(u))
    hem = nb.math('MULTIPLY', line(v, -(DROP - 0.045)), dashes(u))
    side = nb.math('MULTIPLY', line(u, 0.028), dashes(v))
    side = nb.math('MULTIPLY', side, maprange(nb, v, -(DROP - 0.03), -(DROP - 0.05)))
    st = nb.math('MAXIMUM', nb.math('MAXIMUM', header, hem), side)
    # double-layer header band and hem read a touch deeper
    band = nb.math('ADD', maprange(nb, v, -0.075, -0.068), maprange(nb, v, -(DROP - 0.058), -(DROP - 0.052)))
    col = nb.mix(nb.math('MULTIPLY', band, 0.10), col, (0.40, 0.28, 0.14))
    return nb.mix(nb.math('MULTIPLY', st, 0.75), col, (0.46, 0.33, 0.18))


m_linen = layered_mat('linen', 'Fabric036', scale=4.0, tint=(0.92, 0.50, 0.17), sat=1.0, val=1.0,
                      rough_mul=1.0, rough_add=0.05, nstr=0.9, extra_color=stitches,
                      wear=dict(color=(0.80, 0.68, 0.50), radius=0.012, amount=0.35, rough=0.9, noise=6, gain=10),
                      grime=dict(color=(0.24, 0.16, 0.08), dist=0.05, amount=0.55, rough=0.05, gain=1.6, noise=4))
fabric = obj_from_bm('fabric', bm, m_linen)
smooth(fabric, 180)

# ============================================================================== hardware
m_brass = layered_mat('brass', 'Metal048B', scale=6.0, tint=(0.72, 0.52, 0.29), metal=1.0, rough_mul=0.85, rough_add=0.12,
                      wear=dict(color=(1.0, 0.84, 0.55), radius=0.0012, amount=1.0, rough=0.2, metal=1.0, gain=24),
                      grime=dict(color=(0.09, 0.07, 0.035), dist=0.008, amount=0.85, gain=2.2))
hw = []


def lathe_x(name, prof, x, direction=1, segs=32):
    o = lathe_obj(name, prof, segs, m_brass)
    xform(o, (x, ROD_Y, 0.0), (0, math.radians(90 * direction), 0))
    hw.append(o)
    return o


# rod (buried ends inside the finial collars)
bm = bmesh.new()
bmesh.ops.create_cone(bm, cap_ends=False, segments=32, radius1=ROD_R, radius2=ROD_R, depth=1.31)
rod = obj_from_bm('rod', bm, m_brass)
xform(rod, (0, ROD_Y, 0), (0, math.radians(90), 0))
smooth(rod, 60)
hw.append(rod)
fin = [(0.0001, 0), (0.0115, 0), (0.0118, 0.002), (0.0118, 0.006), (0.0095, 0.008), (0.0065, 0.011),
       (0.0068, 0.014), (0.0120, 0.019), (0.0162, 0.026), (0.0165, 0.030), (0.0125, 0.038), (0.0065, 0.0425),
       (0.0025, 0.045), (0.0001, 0.0458)]
lathe_x('finial', fin, 0.652, 1)
lathe_x('finial', fin, -0.652, -1)
# brackets: domed wall rosette + arm + J cradle around the rod bottom, ball tip
for bx in (-0.635, 0.635):
    ros = lathe_obj('rosette', [(0.0001, 0), (0.021, 0), (0.021, 0.002), (0.018, 0.0045), (0.009, 0.0068),
                                (0.0062, 0.0072), (0.0001, 0.0074)], 32, m_brass)
    xform(ros, (bx, 0.0, -0.0125), (math.radians(90), 0, 0))
    hw.append(ros)
    pts = [(bx, -0.004, -0.0125), (bx, -0.040, -0.0125), (bx, -0.080, -0.0125)]
    for s in range(1, 13):
        psi = math.radians(118 * s / 12)
        pts.append((bx, ROD_Y - 0.0125 * math.sin(psi), -0.0125 * math.cos(psi)))
    arm = tube_obj('bracket_arm', pts, 0.0034, m_brass, bevel_res=3)
    hw.append(arm)
    tip = lathe_obj('tip', [(0.0001, -0.0045), (0.0032, -0.0036), (0.0045, 0.0), (0.0032, 0.0036), (0.0001, 0.0045)], 16, m_brass)
    xform(tip, pts[-1])
    hw.append(tip)
# rings (hang on the rod), eyelets and pinch clips gripping the header
RING_R, RING_T = 0.0145, 0.0022
RING_Z = -(RING_R - ROD_R - RING_T)                 # ring top inner edge rests on the rod
for i in range(M):
    x = X0 + (XR - X0) * i / (M - 1)
    bpy.ops.mesh.primitive_torus_add(major_radius=RING_R, minor_radius=RING_T, major_segments=28, minor_segments=8,
                                     location=(x, ROD_Y, RING_Z), rotation=(0, math.radians(90), 0))
    ring = bpy.context.view_layer.objects.active
    ring.name = 'ring'
    ring.data.materials.append(m_brass)
    select_only(ring); bpy.ops.object.transform_apply(location=True, rotation=True, scale=True)
    smooth(ring, 60)
    hw.append(ring)
    ez = RING_Z - RING_R - 0.0022
    bpy.ops.mesh.primitive_torus_add(major_radius=0.0029, minor_radius=0.0011, major_segments=14, minor_segments=6,
                                     location=(x, ROD_Y, ez), rotation=(math.radians(90), 0, 0))
    ey = bpy.context.view_layer.objects.active
    ey.name = 'eyelet'
    ey.data.materials.append(m_brass)
    select_only(ey); bpy.ops.object.transform_apply(location=True, rotation=True, scale=True)
    smooth(ey, 60)
    hw.append(ey)
    bm = box_obj('clip', x - 0.0038, x + 0.0038, ROD_Y - 0.0026, ROD_Y + 0.0026, -0.0415, -0.0255)
    bevel_edges(bm, lambda a, b: True, 0.0009, 2, 0.5)
    clip = obj_from_bm('clip', bm, m_brass)
    smooth(clip, 40)
    hw.append(clip)
    # the clip's tiny hanger wire up into the eyelet
    w = tube_obj('clip_wire', [(x, ROD_Y, -0.0258), (x, ROD_Y, ez - 0.0022)], 0.0007, m_brass)
    hw.append(w)
for o in hw:
    uv_tex(o, 0.2)
hwo = join(hw, 'hardware')
strip_uv(hwo, keep=('TexUV',))
uv_bake(hwo, margin=0.004, angle=60)
# squeeze the hardware islands into u 0.80..1.0, then repack them inside that box (uniform scale)
uvl = hwo.data.uv_layers['BakeUV']
for d in uvl.data:
    d.uv = (0.80 + 0.20 * d.uv[0], d.uv[1])
select_only(hwo)
hwo.data.uv_layers.active = uvl
bpy.ops.object.mode_set(mode='EDIT')
bpy.ops.mesh.select_all(action='SELECT')
bpy.context.scene.tool_settings.use_uv_select_sync = True
try:
    bpy.ops.uv.pack_islands(udim_source='ORIGINAL_AABB', rotate=True, margin=0.004)
except Exception as e:
    print('[curtain] pack_islands ORIGINAL_AABB failed:', e)
bpy.ops.object.mode_set(mode='OBJECT')
uvl = hwo.data.uv_layers['BakeUV']
us = [d.uv[0] for d in uvl.data]; vs_ = [d.uv[1] for d in uvl.data]
print(f'[curtain] hardware BakeUV u {min(us):.3f}..{max(us):.3f} v {min(vs_):.3f}..{max(vs_):.3f}', flush=True)

curtain = join([fabric, hwo], 'Curtain')
print('[curtain] uv maps', strip_uv(curtain), flush=True)
bake_and_swap(curtain, 'curtain', size=2048, samples=40, ao_dist=0.06)
print('[curtain] normal jpeg', reencode_jpeg('curtain', 'normal', 82), flush=True)
for m in curtain.data.materials:
    m.use_backface_culling = False
export_glb([curtain], 'corner_curtain.glb')

# ================================================================================ lookdev
preview([curtain], 'curtain', height=0.3)
# context: the window we built, a sage wall with the opening, the floor
with bpy.data.libraries.load(os.path.join(ROOT, 'blend', 'corner_window.blend')) as (src, dst):
    dst.objects = [n for n in src.objects if n in ('WindowFrame', 'WindowGlass')]
for o in dst.objects:
    link(o)
    o.location = (0.0, 0.0, -0.725)                  # window origin = opening centre, 0.725 below the rod
    if o.name.startswith('WindowGlass'):
        gl = bpy.data.materials.new('glass_lookdev'); gl.use_nodes = True
        b = gl.node_tree.nodes.get('Principled BSDF')
        b.inputs['Transmission Weight'].default_value = 1.0
        b.inputs['Roughness'].default_value = 0.02
        o.data.materials[0] = gl
wall_m = layered_mat('wall_ctx', 'PaintedPlaster017', scale=0.8, tint=(0.52, 0.62, 0.54), rough_mul=1.0)
wall = obj_from_bm('ctx_wall', box_obj('w', -1.4, 1.5, 0.0, 0.16, -2.45, 0.6), wall_m); uv_tex(wall, 1.0)
boolean(wall, cutter_box(-0.5, 0.5, -0.1, 0.3, -1.35, -0.10))
obj_from_bm('ctx_sky', box_obj('s', -6, 6, 3.0, 3.05, -5, 4),
            flat_mat('sky', (0.02, 0.03, 0.06), emission=(0.05, 0.08, 0.16, 1.0)))
lamp = ((-0.4, -1.1, -0.95), 110, 0.35, (1.0, 0.74, 0.46))
fill = ((1.2, -1.6, 0.2), 30, 1.2, (0.78, 0.84, 1.0))
top = ((0.5, -0.8, 0.9), 40, 0.6, (1.0, 0.95, 0.9))
shots = [lit_closeup('curtain_c_full', (-0.35, -2.4, -0.55), (0.3, -0.05, -0.62), lens=35, key=lamp, fill=fill, rim=top),
         lit_closeup('curtain_c_head', (0.28, -0.42, 0.06), (0.52, -0.07, -0.03), lens=55, key=lamp, fill=fill, rim=top),
         lit_closeup('curtain_c_hem', (0.10, -0.62, -1.18), (0.45, -0.07, -1.33), lens=45, key=lamp, fill=fill, rim=top),
         lit_closeup('curtain_c_side', (1.25, -0.70, -0.50), (0.46, -0.06, -0.62), lens=40, key=lamp, fill=fill, rim=top)]
sheet(shots, 'curtain_closeups.png', cols=2)
