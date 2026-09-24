"""Claude's Corner - the desk lamp. A turned brass column lamp (stepped foot, knuckle, top nut),
a brown bakelite socket with a brass key switch and a bead pull-chain, a harp + finial, a
fabric cord leaving the back of the foot, and a linen drum shade with bound rims and a brass
spider. Baked: 'LampBody' (brass/bakelite/cord) and 'LampShade' (linen + spider).
'LampBulb' keeps a flat 'BULB' material for the engine.
Origin: base bottom centre. Front -Y.
"""
import sys, os, math
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import bpy, bmesh
from mathutils import Vector, Matrix
from clib import *
from props_util import *

reset()

def patina(nb, col):
    # soft darker, desaturated tarnish patches on the old brass
    oc = nb.n('ShaderNodeTexCoord').outputs['Object']
    m = nb.ramp(nb.noise(oc, 26.0, 6.0, 0.62), 0.52, 0.78)
    return nb.mix(nb.math('MULTIPLY', m, 0.45), col, (0.42, 0.30, 0.15))


def linen_slubs(nb, col, vec):
    # linen: horizontal slub threads + heat-browning toward the top rim inside and out
    mp = nb.n('ShaderNodeMapping'); mp.inputs['Scale'].default_value = (2.0, 90.0, 1.0); nb.l(vec, mp.inputs['Vector'])
    sl = nb.ramp(nb.noise(mp.outputs[0], 3.0, 3.0, 0.5), 0.55, 0.8)
    col = nb.mix(nb.math('MULTIPLY', sl, 0.22), col, (0.62, 0.52, 0.36))
    oc = nb.n('ShaderNodeTexCoord').outputs['Object']
    sep = nb.n('ShaderNodeSeparateXYZ'); nb.l(oc, sep.inputs[0])
    top = nb.ramp(sep.outputs['Z'], 0.40, 0.455)
    return nb.mix(nb.math('MULTIPLY', top, 0.18), col, (0.72, 0.56, 0.30))



brass = layered_mat('lamp_brass', 'Metal048B', scale=5.0, tint=(0.86, 0.63, 0.36), val=0.92, metal=1.0,
                    rough_mul=0.85, rough_add=0.10, nstr=0.5,
                    wear=dict(color=(1.0, 0.84, 0.56), radius=0.0012, amount=1.0, rough=0.16, metal=1.0, gain=26, noise=40),
                    grime=dict(color=(0.11, 0.085, 0.045), dist=0.014, amount=0.95, rough=0.28, gain=2.6, noise=30),
                    extra_color=lambda nb, col, vec: patina(nb, col))
bakelite = layered_mat('bakelite', 'Plastic006', scale=6.0, val=5.5, tint=(0.95, 0.50, 0.24), rough_mul=1.0, rough_add=0.12,
                       nstr=0.4,
                       wear=dict(color=(0.42, 0.24, 0.13), radius=0.0008, amount=0.7, rough=0.35, gain=24, noise=60),
                       grime=dict(color=(0.03, 0.015, 0.008), dist=0.008, amount=0.6, gain=2.0))
cordm = layered_mat('cord', 'Rope001', scale=60.0, tint=(0.36, 0.25, 0.15), val=0.85, rough_add=0.1, nstr=1.0,
                    grime=dict(color=(0.05, 0.035, 0.02), dist=0.006, amount=0.4))
linen = layered_mat('linen', 'Fabric019', scale=16.0, tint=(0.93, 0.83, 0.66), val=0.97, rough_add=0.05, nstr=0.9,
                    extra_color=linen_slubs,
                    grime=dict(color=(0.55, 0.45, 0.32), dist=0.01, amount=0.35, gain=1.5),
                    dust=dict(color=(0.80, 0.74, 0.62), amount=0.25))
binding = layered_mat('binding', 'Fabric019', scale=14.0, tint=(0.80, 0.70, 0.55), rough_add=0.05, nstr=1.0,
                      wear=dict(color=(0.9, 0.84, 0.72), radius=0.0008, amount=0.5, rough=0.8, gain=20, noise=50))
bulb_m = flat_mat('BULB', color=(0.95, 0.92, 0.85), rough=0.35, emission=(1.0, 0.8, 0.55, 2.0))

body = []

# ---- turned brass column: foot steps, dome, collar, stem, knuckle, top nut (one lathe = one turned mass)
col_prof = [(0.0005, 0.000), (0.066, 0.000), (0.0715, 0.0012), (0.0748, 0.0045), (0.0752, 0.0080),
            (0.0742, 0.0108), (0.0705, 0.0124), (0.0662, 0.0129), (0.0642, 0.0152), (0.0627, 0.0190),
            (0.0592, 0.0218), (0.0545, 0.0234), (0.0502, 0.0246), (0.0472, 0.0282), (0.0412, 0.0340),
            (0.0322, 0.0400), (0.0222, 0.0452), (0.0165, 0.0480), (0.0147, 0.0500), (0.0162, 0.0520),
            (0.0162, 0.0560), (0.0137, 0.0580), (0.0101, 0.0598), (0.0096, 0.0620),
            (0.0096, 0.1400), (0.0106, 0.1418), (0.0141, 0.1460), (0.0164, 0.1520), (0.0170, 0.1580),
            (0.0164, 0.1640), (0.0141, 0.1700), (0.0106, 0.1742), (0.0096, 0.1760),
            (0.0096, 0.2520), (0.0110, 0.2536), (0.0126, 0.2550), (0.0126, 0.2620), (0.0110, 0.2632),
            (0.0090, 0.2640), (0.0005, 0.2640)]
column = lathe_obj('column', col_prof, 64, brass)
body.append(column)

# ---- harp saddle, harp wires, stud, finial (brass)
bm = bmesh.new(); bm_box(bm, 0.066, 0.012, 0.0028, 0, 0, 0.2655)
sad = obj_from_bm('saddle', bm, brass); finish(sad, bevel=0.0008, segments=2)
body.append(sad)
for s in (-1, 1):
    pts = bezier_points([(s * 0.030, 0, 0.2665), (s * 0.037, 0, 0.292), (s * 0.046, 0, 0.332), (s * 0.047, 0, 0.382),
                         (s * 0.040, 0, 0.421), (s * 0.021, 0, 0.4465), (0.0, 0, 0.4525)], 10)
    hw = tube_obj('harp', [tuple(p) for p in pts], 0.00135, brass, caps=False)
    body.append(hw)
stud = lathe_obj('stud', [(0.0005, 0.4500), (0.0030, 0.4500), (0.0030, 0.4600), (0.0005, 0.4600)], 16, brass)
body.append(stud)
fin = lathe_obj('finial', [(0.0005, 0.4565), (0.0075, 0.4565), (0.0082, 0.4580), (0.0060, 0.4600), (0.0048, 0.4620),
                           (0.0072, 0.4650), (0.0092, 0.4690), (0.0088, 0.4725), (0.0065, 0.4752), (0.0030, 0.4768),
                           (0.0005, 0.4772)], 40, brass)
body.append(fin)

# ---- bakelite socket shell with three grip grooves + top lip
sp = [(0.0005, 0.2665), (0.0150, 0.2665), (0.0165, 0.2685), (0.0171, 0.2722), (0.0181, 0.2752), (0.0186, 0.2780)]
z = 0.2780
for k in range(3):
    sp += [(0.0186, z + 0.0035), (0.0179, z + 0.0041), (0.0179, z + 0.0055), (0.0186, z + 0.0061)]
    z += 0.0061
sp += [(0.0186, 0.3000), (0.0180, 0.3030), (0.0176, 0.3060), (0.0176, 0.3180), (0.0168, 0.3212), (0.0150, 0.3232),
       (0.0122, 0.3232), (0.0119, 0.3220), (0.0119, 0.3000), (0.0005, 0.3000)]
sock = lathe_obj('socket', sp, 48, bakelite)
body.append(sock)

# ---- bulb screw base (exposed thread) - brass/aluminium-ish
thr = [(0.0005, 0.3170), (0.0121, 0.3170)]
z = 0.3170
while z < 0.3320:
    thr += [(0.0129, z + 0.0012), (0.0121, z + 0.0024)]
    z += 0.0024
thr += [(0.0118, 0.3345), (0.0005, 0.3345)]
base = lathe_obj('screwbase', thr, 32, brass)
body.append(base)

# ---- key switch on the socket (+X): stub + knurled paddle
stub = lathe_obj('keystub', [(0.0005, 0.0), (0.0026, 0.0), (0.0026, 0.0075), (0.0005, 0.0075)], 16, brass)
stub.rotation_euler = (0, math.radians(90), 0)
stub.location = (0.0178, 0, 0.2875)
select_only(stub); bpy.ops.object.transform_apply(location=True, rotation=True, scale=True)
body.append(stub)
bm = bmesh.new(); bm_box(bm, 0.0032, 0.0140, 0.0105, 0.0268, 0, 0.2875)
pad = obj_from_bm('keypaddle', bm, brass); finish(pad, bevel=0.0009, segments=3)
body.append(pad)

# ---- pull chain: guide boss (-X), bead chain, bell pull
boss = lathe_obj('chainboss', [(0.0005, 0.0), (0.0030, 0.0), (0.0030, 0.0045), (0.0018, 0.0060), (0.0005, 0.0060)], 16, brass)
boss.rotation_euler = (0, math.radians(-90), 0)
boss.location = (-0.0182, 0, 0.2960)
select_only(boss); bpy.ops.object.transform_apply(location=True, rotation=True, scale=True)
body.append(boss)
bx = -0.0245
zb = 0.2930
beads = []
k = 0
while zb > 0.2230:
    swing = 0.0006 * math.sin(k * 0.7)
    bpy.ops.mesh.primitive_uv_sphere_add(segments=10, ring_count=6, radius=0.00125, location=(bx + swing, 0.0, zb))
    b = bpy.context.object; b.data.materials.append(brass); smooth(b, 80); beads.append(b)
    # tiny link between beads
    if zb - 0.0032 > 0.2230:
        lk = tube_obj('link', [(bx + swing, 0, zb - 0.0012), (bx + swing, 0, zb - 0.0020)], 0.00035, brass, caps=True)
        beads.append(lk)
    zb -= 0.0032
    k += 1
bell = lathe_obj('bellpull', [(0.0005, 0.000), (0.0022, 0.0006), (0.0040, 0.0030), (0.0046, 0.0060), (0.0040, 0.0092),
                              (0.0024, 0.0118), (0.0012, 0.0130), (0.0009, 0.0142), (0.0005, 0.0145)], 24, brass)
bell.location = (bx, 0, zb + 0.0020 - 0.0145)       # narrow neck up, hanging off the last bead
select_only(bell); bpy.ops.object.transform_apply(location=True, rotation=True, scale=True)
body += beads + [bell]

# ---- fabric cord: brass grommet on the foot's back, cord drops to the desk and runs to the wall
grom = lathe_obj('grommet', [(0.0028, 0.0), (0.0042, 0.0), (0.0045, 0.0012), (0.0042, 0.0024), (0.0028, 0.0024),
                             (0.0028, 0.0)], 20, brass)
grom.rotation_euler = (math.radians(-90), 0, 0)
grom.location = (0, 0.0738, 0.0062)
select_only(grom); bpy.ops.object.transform_apply(location=True, rotation=True, scale=True)
body.append(grom)
cpts = bezier_points([(0, 0.070, 0.0062), (0, 0.082, 0.0060), (0.004, 0.096, 0.0036), (0.012, 0.118, 0.0028),
                      (0.030, 0.160, 0.0028), (0.022, 0.210, 0.0028), (-0.010, 0.255, 0.0028), (-0.018, 0.300, 0.0028)], 8)
cord = tube_obj('cord', [tuple(p) for p in cpts], 0.0027, cordm, bevel_res=3, caps=True)
body.append(cord)

# ---------------------------------------------------------------- UVs for the body
for o in body:
    if o.name.startswith('cord'):
        uv_tex(o, 0.05)
    elif o.name.startswith(('column', 'socket', 'finial', 'screwbase', 'stud', 'bellpull')):
        uv_cyl(o, 'Z', 1.0)
    else:
        uv_tex(o, 0.2)
lamp = join(body, 'LampBody')
uv_bake(lamp, margin=0.003)
bake_and_swap(lamp, 'lamp_body', size=2048, samples=40, ao_dist=0.03)
clean_uvs(lamp)

# ---------------------------------------------------------------- the shade (linen drum)
RB, ZB, RT, ZT, TH = 0.1400, 0.2750, 0.1100, 0.4550, 0.0016
shade_parts = []
wall = lathe_obj('shadewall', [(RB, ZB), (RT, ZT), (RT - TH, ZT), (RB - TH, ZB), (RB, ZB)], 96, linen)
shade_parts.append(wall)
for (r, zz) in ((RB - TH / 2, ZB), (RT - TH / 2, ZT)):
    prof = [(r + 0.0023 * math.cos(a), zz + 0.0023 * math.sin(a)) for a in [i * math.tau / 10 for i in range(11)]]
    rim = lathe_obj('rim', prof, 96, binding)
    shade_parts.append(rim)
# spider: wire ring inside the top rim, three spokes, centre washer (brass)
ring = lathe_obj('spiderring', [((RT - 0.004) + 0.0011 * math.cos(a), ZT - 0.004 + 0.0011 * math.sin(a))
                                for a in [i * math.tau / 8 for i in range(9)]], 64, brass)
shade_parts.append(ring)
for k in range(3):
    a = k * math.tau / 3 + math.pi / 2
    p0 = (math.cos(a) * 0.0105, math.sin(a) * 0.0105, 0.4535)
    p1 = (math.cos(a) * (RT - 0.0045), math.sin(a) * (RT - 0.0045), ZT - 0.004)
    shade_parts.append(tube_obj('spoke', [p0, p1], 0.0011, brass, caps=False))
wash = lathe_obj('washer', [(0.0032, 0.4520), (0.0110, 0.4520), (0.0110, 0.4545), (0.0032, 0.4545), (0.0032, 0.4520)], 32, brass)
shade_parts.append(wash)
for o in shade_parts:
    if o.name.startswith(('shadewall', 'rim')):
        uv_cyl(o, 'Z', 1.0, r_ref=0.125)
    else:
        uv_tex(o, 0.2)
shade = join(shade_parts, 'LampShade')
uv_bake(shade, margin=0.003)
bake_and_swap(shade, 'lamp_shade', size=2048, samples=40, ao_dist=0.05)
clean_uvs(shade)

# ---------------------------------------------------------------- the bulb (engine-driven glass)
bprof = [(0.0118, 0.3345), (0.0132, 0.3400), (0.0164, 0.3500), (0.0214, 0.3620), (0.0261, 0.3750), (0.0289, 0.3880),
         (0.0299, 0.3980), (0.0296, 0.4100), (0.0279, 0.4220), (0.0244, 0.4320), (0.0180, 0.4390), (0.0100, 0.4425),
         (0.0005, 0.4435)]
bulb = lathe_obj('LampBulb', bprof, 48, bulb_m)
uv_cyl(bulb, 'Z', 0.1, uvname='UVMap')

export_glb([lamp, shade, bulb], 'corner_lamp.glb')
print('[lamp] bulb centre z = 0.398 (glass widest ring), glass top 0.4435, shade z 0.275..0.455', flush=True)
preview([lamp, shade, bulb], 'lamp', height=0.35)
lit_closeup('lamp_foot', (0.16, -0.26, 0.10), (0.0, 0.0, 0.03), lens=60)
lit_closeup('lamp_socket', (0.10, -0.20, 0.18), (0.0, 0.0, 0.285), lens=60)
lit_closeup('lamp_shade', (0.22, -0.40, 0.42), (0.0, 0.0, 0.36), lens=50)
