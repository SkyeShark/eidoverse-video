"""Weathered wooden light pole, 3.4 m: a peeled round pole (slightly irregular, bent, knots, drying
checks), sun-bleached silver-grey above, soil-stained bottom 0.3 m, galvanized screw-eye on the
front (-Y) with a carriage-bolted cross-arm behind it and two cup hooks under the arm ends.
Origin: base centre on the ground. -> glb/camp_pole.glb ('Pole')
"""
import sys, os, math
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import bpy, bmesh
from mathutils import Vector, Matrix, noise
from clib import *
from camp_lib import *

reset()
H = 3.40
R0, R1 = 0.047, 0.042
NZ, NA = 90, 32
EYE_Z = 3.20
ARM_Z = 3.30
KNOTS = [(1.05, 2.1), (1.92, 4.4), (2.61, 0.9), (0.62, 5.6)]


def axis_off(z):
    return Vector((0.013 * math.sin(z * 0.9 + 0.3) + 0.004 * math.sin(z * 2.7), 0.010 * math.sin(z * 0.7 + 1.1), 0))


def radius(z, a):
    r = R0 + (R1 - R0) * (z / H)
    r *= 1 + 0.035 * math.cos(2 * a + 0.8 * math.sin(z * 1.3)) + 0.012 * math.cos(3 * a + z * 2.1)
    r += 0.0025 * noise.noise(Vector((math.cos(a) * 3, math.sin(a) * 3, z * 2.2)))
    for kz, ka in KNOTS:                     # knots: local swellings
        da = math.atan2(math.sin(a - ka), math.cos(a - ka))
        d2 = ((z - kz) / 0.035) ** 2 + (da / 0.32) ** 2
        r += 0.0045 * math.exp(-d2)
    if z > H - 0.03:                          # weathered chamfer at the cut top
        r -= (z - (H - 0.03)) * 0.25
    return r


bm = bmesh.new()
rings = []
for i in range(NZ + 1):
    z = H * (i / NZ) ** 1.0
    c = axis_off(z)
    ring = []
    for j in range(NA):
        a = j / NA * math.tau
        r = radius(z, a)
        ring.append(bm.verts.new((c.x + r * math.cos(a), c.y + r * math.sin(a), z)))
    rings.append(ring)
for i in range(NZ):
    for j in range(NA):
        a, b = rings[i][j], rings[i][(j + 1) % NA]
        c_, d = rings[i + 1][(j + 1) % NA], rings[i + 1][j]
        bm.faces.new((a, b, c_, d))
top = bm.faces.new(list(rings[-1]))            # the weathered cut end (bottom end is buried: no cap)
bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
# a shallow drying-crack on the top end: inset + push
r = bmesh.ops.inset_region(bm, faces=[top], thickness=0.004, depth=-0.002)


def pole_extra(nb, col, vec):
    oc = obj_coord(nb)
    x, y, z = sep_xyz(nb, oc)
    # sun-bleach: lighter & greyer toward the top
    bleach = nb.ramp(z, 0.6, 3.2)
    col = nb.mix(nb.math('MULTIPLY', bleach, 0.22), col, (0.58, 0.57, 0.55))
    # vertical water streaks
    sv = nb.n('ShaderNodeMapping'); sv.inputs['Scale'].default_value = (9.0, 9.0, 0.35); nb.l(oc, sv.inputs['Vector'])
    streak = nb.ramp(nb.noise(sv.outputs[0], 3.0, 3.0, 0.5), 0.55, 0.75)
    col = nb.mix(nb.math('MULTIPLY', streak, 0.45), col, (0.13, 0.12, 0.10))
    # drying checks: long thin dark cracks along the grain
    cv = nb.n('ShaderNodeMapping'); cv.inputs['Scale'].default_value = (26.0, 26.0, 0.9); nb.l(oc, cv.inputs['Vector'])
    ck = voronoi_cracks(nb, cv.outputs[0], scale=1.0, width=0.05)
    ckn = nb.ramp(nb.noise(oc, 1.5, 2.0, 0.5), 0.38, 0.55)
    ck = nb.math('MULTIPLY', ck, ckn)
    col = nb.mix(nb.math('MULTIPLY', ck, 0.85), col, (0.05, 0.045, 0.04))
    # knots: dark ringed eyes
    for kz, ka in KNOTS:
        kc = axis_off(kz); kr = radius(kz, ka)
        kx, ky = kc.x + math.cos(ka) * kr, kc.y + math.sin(ka) * kr
        d = nb.n('ShaderNodeVectorMath', operation='DISTANCE')
        nb.l(oc, d.inputs[0]); d.inputs[1].default_value = (kx, ky, kz)
        k = nb.ramp(d.outputs['Value'], 0.008, 0.024, (1, 1, 1, 1), (0, 0, 0, 1))
        col = nb.mix(nb.math('MULTIPLY', k, 0.8), col, (0.10, 0.075, 0.05))
    # lichen specks, a few, on the shaded side
    lich = nb.ramp(nb.noise(oc, 38.0, 2.0, 0.5), 0.72, 0.78)
    side = nb.ramp(y, -0.02, 0.05)
    col = nb.mix(nb.math('MULTIPLY', nb.math('MULTIPLY', lich, side), 0.6), col, (0.52, 0.58, 0.44))
    # soil: damp dark band up to ~0.3 m with a ragged edge, splashes to 0.5
    edge = nb.math('ADD', z, nb.math('MULTIPLY', nb.noise(oc, 9.0, 3.0, 0.6), 0.10))
    soil = ramp_s(nb, edge, 0.36, 0.26)
    splash = nb.math('MULTIPLY', nb.ramp(nb.noise(oc, 60.0, 2.0, 0.5), 0.66, 0.70), ramp_s(nb, z, 0.55, 0.30))
    soil = nb.math('MAXIMUM', soil, nb.math('MULTIPLY', splash, 0.8))
    col = nb.mix(soil, col, (0.085, 0.065, 0.045))
    return col


m_wood = layered_mat('pole_wood', 'Wood049', scale=1.6, tint=(0.95, 0.93, 0.9), sat=0.5, val=0.74,
                     rough_mul=1.0, rough_add=0.18, nstr=1.2, extra_color=pole_extra,
                     grime=dict(color=(0.06, 0.05, 0.04), dist=0.03, amount=0.6, gain=1.6))
def crack_height(nb):
    cv = nb.n('ShaderNodeMapping'); cv.inputs['Scale'].default_value = (26.0, 26.0, 0.9)
    nb.l(obj_coord(nb), cv.inputs['Vector'])
    return nb.math('SUBTRACT', 1.0, voronoi_cracks(nb, cv.outputs[0], scale=1.0, width=0.035))


add_bump(m_wood, crack_height, strength=0.55, distance=0.002)
for n in m_wood.node_tree.nodes:                 # straight pole grain: stretch along the length
    if n.type == 'MAPPING' and n.inputs['Scale'].default_value[0] == 1.6:
        n.inputs['Scale'].default_value = (0.9, 5.0, 1.0)
pole = obj_from_bm('pole', bm, m_wood)
smooth(pole, 70)
uv_tex_axis(pole, 'Z', 1.0)

# ---- galvanized metal
def galv_extra(nb, col, vec):
    oc = obj_coord(nb)
    sp = nb.n('ShaderNodeTexVoronoi'); sp.inputs['Scale'].default_value = 180.0; nb.l(oc, sp.inputs['Vector'])
    col = nb.mix(nb.math('MULTIPLY', sp.outputs['Distance'], 0.5), col, (0.42, 0.44, 0.45))   # zinc spangle
    rust = nb.ramp(nb.noise(oc, 90.0, 3.0, 0.6), 0.68, 0.74)
    return nb.mix(nb.math('MULTIPLY', rust, 0.7), col, (0.33, 0.16, 0.07))


m_galv = layered_mat('galv', 'Metal049A', scale=12.0, tint=(0.60, 0.62, 0.63), metal=1.0, rough_mul=1.0,
                     rough_add=0.40, extra_color=galv_extra,
                     grime=dict(color=(0.10, 0.09, 0.08), dist=0.01, amount=0.8, gain=2.0))
m_arm = layered_mat('arm_wood', 'Wood049', scale=1.6, tint=(0.95, 0.93, 0.9), sat=0.5, val=0.72, rough_add=0.2,
                    nstr=1.1, wear=dict(color=(0.55, 0.52, 0.47), radius=0.004, amount=0.9, rough=0.9, gain=14),
                    grime=dict(color=(0.07, 0.06, 0.05), dist=0.03, amount=0.7, gain=1.8))
parts = [pole]
c_eye = axis_off(EYE_Z)
front_r = radius(EYE_Z, -math.pi / 2)
# screw eye: threaded shank into the wood, eye loop in the YZ plane
y0 = c_eye.y - front_r + 0.02
y1 = c_eye.y - front_r - 0.030
parts.append(tube_obj('eye_shank', [(c_eye.x, y0, EYE_Z), (c_eye.x, y1, EYE_Z)], 0.0045, m_galv, bevel_res=2))
ER = 0.017
eye_c = Vector((c_eye.x, y1 - ER + 0.001, EYE_Z))
loop = [(eye_c.x, eye_c.y + ER * math.cos(t), eye_c.z + ER * math.sin(t))
        for t in [math.radians(15) + k * math.radians(330) / 40 for k in range(41)]]
parts.append(tube_obj('eye_loop', loop, 0.0045, m_galv, bevel_res=2))
parts.append(lathe_obj('eye_collar', [(0.0001, 0), (0.0085, 0), (0.0085, 0.003), (0.006, 0.005), (0.0001, 0.005)], 24, m_galv))
col_o = parts[-1]
col_o.rotation_euler = (math.radians(90), 0, 0)
col_o.location = (c_eye.x, c_eye.y - front_r + 0.0015, EYE_Z)
select_only(col_o); bpy.ops.object.transform_apply(location=True, rotation=True)
EYE_POINT = Vector((eye_c.x, eye_c.y - ER * 0.2, eye_c.z - ER * 0.85))   # where a hanging wire's hook sits

# cross-arm behind the pole (+Y), carriage bolt through both
c_arm = axis_off(ARM_Z)
back_r = radius(ARM_Z, math.pi / 2)
AL, AH, AT = 0.44, 0.070, 0.045
bm = bmesh.new(); bm_box(bm, AL, AT, AH, c_arm.x, c_arm.y + back_r + AT / 2 - 0.004, ARM_Z)
arm = obj_from_bm('arm', bm, m_arm); finish(arm, bevel=0.004, segments=3, angle=40)
uv_tex_axis(arm, 'X', 1.0)
parts.append(arm)
yb_front = c_arm.y - radius(ARM_Z, -math.pi / 2)
head = lathe_obj('bolt_head', [(0.0001, 0.0), (0.012, 0.0), (0.0118, 0.0018), (0.0095, 0.0048), (0.005, 0.0065),
                               (0.0001, 0.0070)], 32, m_galv)
head.rotation_euler = (math.radians(90), 0, 0)
head.location = (c_arm.x, yb_front + 0.0015, ARM_Z)
select_only(head); bpy.ops.object.transform_apply(location=True, rotation=True)
parts.append(head)
yb_back = c_arm.y + back_r + AT - 0.004
washer = lathe_obj('washer', [(0.0065, 0), (0.014, 0), (0.014, 0.0022), (0.0065, 0.0022)], 32, m_galv)
washer.rotation_euler = (math.radians(-90), 0, 0)
washer.location = (c_arm.x, yb_back, ARM_Z)
select_only(washer); bpy.ops.object.transform_apply(location=True, rotation=True)
parts.append(washer)
bm = bmesh.new()
bmesh.ops.create_cone(bm, cap_ends=True, segments=6, radius1=0.0105, radius2=0.0105, depth=0.009)
for v in bm.verts:
    v.co = Vector((v.co.x + c_arm.x, v.co.z + yb_back + 0.0022 + 0.0045, v.co.y + ARM_Z))
nut = obj_from_bm('nut', bm, m_galv); finish(nut, bevel=0.0008, segments=2)
parts.append(nut)
parts.append(tube_obj('bolt_end', [(c_arm.x, yb_back, ARM_Z), (c_arm.x, yb_back + 0.017, ARM_Z)], 0.0055, m_galv, bevel_res=2))
# cup hooks screwed up into the arm's underside near each end
for sx in (-1, 1):
    hx = c_arm.x + sx * (AL / 2 - 0.035)
    hy = c_arm.y + back_r + AT / 2 - 0.004
    hz = ARM_Z - AH / 2
    pts = [(hx, hy, hz + 0.008), (hx, hy, hz - 0.018)]
    for k in range(1, 15):
        t = math.pi * k / 14
        pts.append((hx, hy - 0.009 + 0.009 * math.cos(t), hz - 0.018 - 0.009 * math.sin(t)))
    parts.append(tube_obj('cup_hook', pts, 0.0022, m_galv, bevel_res=2))
    parts.append(lathe_obj('cup', [(0.0001, 0), (0.007, 0), (0.0045, -0.003), (0.0001, -0.003)], 20, m_galv))
    cup = parts[-1]; cup.location = (hx, hy, hz); select_only(cup); bpy.ops.object.transform_apply(location=True)
# two old rusted nails from past uses
for (nz, na) in ((1.62, -1.3), (2.35, -2.2)):
    c = axis_off(nz); rr = radius(nz, na)
    d = Vector((math.cos(na), math.sin(na), 0))
    p0 = Vector((c.x, c.y, nz)) + d * (rr - 0.01); p1 = Vector((c.x, c.y, nz)) + d * (rr + 0.012)
    parts.append(tube_obj('nail', [tuple(p0), tuple(p1 + Vector((0, 0, -0.004)))], 0.0016, m_galv, bevel_res=1))
    nh = lathe_obj('nail_head', [(0.0001, 0), (0.0035, 0), (0.0033, 0.0012), (0.0001, 0.0014)], 16, m_galv)
    nh.rotation_euler = d.to_track_quat('Z', 'Y').to_euler(); nh.location = p1 + Vector((0, 0, -0.004))
    select_only(nh); bpy.ops.object.transform_apply(location=True, rotation=True)
    parts.append(nh)

for o in parts[1:]:
    if 'TexUV' not in o.data.uv_layers:
        uv_tex(o, 0.1)
# -- hardware + arm: smart-project, then squeeze into the top band of the atlas
hw = join(parts[1:], 'hw')
for uvl in list(hw.data.uv_layers):
    if uvl.name not in ('TexUV',):
        hw.data.uv_layers.remove(uvl)
uv_bake(hw, margin=0.006, angle=55)
bl = hw.data.uv_layers['BakeUV']
for d in bl.data:
    d.uv = (0.02 + d.uv.x * 0.255, 0.738 + d.uv.y * 0.255)
# -- pole: cylinder unwrap in 4 length chunks laid side by side (0.6 mm/texel both ways at 2K)
me = pole.data
pb = me.uv_layers.new(name='BakeUV')
S = 0.76
NCH = 4
for poly in me.polygons:
    zc = sum(me.vertices[i].co.z for i in poly.vertices) / len(poly.vertices)
    ch = min(NCH - 1, int(zc / (H / NCH)))
    # face azimuth centre decides which side of the seam its loops live on
    cx = sum(me.vertices[i].co.x for i in poly.vertices) / len(poly.vertices)
    cy = sum(me.vertices[i].co.y for i in poly.vertices) / len(poly.vertices)
    ac = math.atan2(cy - axis_off(zc).y, cx - axis_off(zc).x) % math.tau
    for li in poly.loop_indices:
        v = me.vertices[me.loops[li].vertex_index].co
        c = axis_off(v.z)
        a = math.atan2(v.y - c.y, v.x - c.x) % math.tau
        if a - ac > math.pi: a -= math.tau
        if ac - a > math.pi: a += math.tau
        rr = (R0 + (R1 - R0) * v.z / H)
        u = 0.012 + ch * 0.245 + (a / math.tau) * (math.tau * rr) * S
        vv = 0.045 + (v.z - ch * H / NCH) * S
        if poly.normal.z > 0.9:                      # the top cap: its own little disc island
            u = 0.40 + (v.x - c.x) * S * 1.5
            vv = 0.86 + (v.y - c.y) * S * 1.5
        pb.data[li].uv = (u, vv)
P = join([pole, hw], 'Pole')
bake_and_swap(P, 'pole', size=2048, samples=40, ao_dist=0.06)
finalize_export_material(P.data.materials[0])
P['hook_point'] = [round(EYE_POINT.x, 4), round(EYE_POINT.z, 4), round(-EYE_POINT.y, 4)]   # glTF (x, y, z)
P['arm_hooks_z'] = round(ARM_Z - AH / 2 - 0.027, 4)
print('[pole] eye-hook point (Blender) =', tuple(round(v, 4) for v in EYE_POINT), ' glTF =', P['hook_point'])
export_glb([P], 'camp_pole.glb')

g = ground_plane(4.0)
preview([P], 'pole', height=0.4)
lit_shot('pole_top', (0.35, -0.55, 3.35), (0.0, 0.0, 3.22), lens=55, size=768)
lit_shot('pole_base', (0.45, -0.75, 0.55), (0.0, 0.0, 0.28), lens=45, size=768)
lit_shot('pole_full', (2.2, -4.2, 1.9), (0.0, 0.0, 1.7), lens=35, size=768)
lit_shot('pole_seam', (0.25, -0.45, 0.9), (0.0, 0.0, 0.85), lens=50, size=768)
