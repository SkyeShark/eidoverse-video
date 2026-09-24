"""Festoon string-light unit: G45 globe bulb hanging from a black rubber socket whose moulded clip
grips the festoon wire. ORIGIN = the wire attachment point (clip centre); the wire runs along X;
the bulb hangs along -Z.  -> glb/camp_bulb.glb
  BulbSocket   baked (rubber clip + ribbed socket + nickel E12 thread band)
  BulbGlass    flat material 'BULB'      (engine: warm translucent / emissive glass)
  BulbFilament flat material 'FILAMENT'  (engine: the hot LED loop, HDR emissive)
"""
import sys, os, math
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import bpy, bmesh
from mathutils import Vector, Matrix
from clib import *
from camp_lib import *

reset()

WIRE_R = 0.0032
rubber = layered_mat('rubber', 'Plastic012B', scale=14.0, tint=(1.35, 1.32, 1.28), rough_mul=1.0, rough_add=0.28,
                     nstr=0.6,
                     wear=dict(color=(0.16, 0.155, 0.15), radius=0.0006, amount=0.8, rough=0.55, noise=90, gain=24),
                     grime=dict(color=(0.20, 0.185, 0.16), dist=0.004, amount=0.9, rough=0.15, gain=2.2, noise=60),
                     dust=dict(color=(0.30, 0.28, 0.25), amount=0.35, noise=70))
nickel = layered_mat('nickel', 'Metal049A', scale=20.0, tint=(0.72, 0.66, 0.52), metal=1.0, rough_mul=1.0, rough_add=0.22,
                     grime=dict(color=(0.12, 0.10, 0.07), dist=0.002, amount=0.9, gain=2.5, noise=80))
parts = []

# ---- clip: a C-shaped moulded band around the wire (solid of revolution about X, 290 deg)
bm = bmesh.new()
r0, r1, w = WIRE_R + 0.0003, WIRE_R + 0.0027, 0.013
prof = [bm.verts.new(p) for p in ((r0, 0, -w / 2), (r1, 0, -w / 2), (r1, 0, w / 2), (r0, 0, w / 2))]
f = bm.faces.new(prof)
# the C opens on top (+Z side of the wire): start the sweep at +35deg past the top, go 290deg
bmesh.ops.rotate(bm, verts=prof, cent=(0, 0, 0), matrix=Matrix.Rotation(math.radians(215), 3, 'Z'))
res = bmesh.ops.spin(bm, geom=[f] + prof + list(f.edges), cent=(0, 0, 0), axis=(0, 0, 1),
                     angle=math.radians(290), steps=40, use_duplicate=False)
bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
clip = obj_from_bm('clip', bm, rubber)
# lathe axis Z -> wire axis X; the C's gap ends up facing +Z (the wire snaps in from above)
clip.rotation_euler = (0, math.radians(90), 0)
select_only(clip); bpy.ops.object.transform_apply(rotation=True)
finish(clip, bevel=0.0005, segments=2, angle=50)
parts.append(clip)

# ---- neck from clip to socket (moulded as one with the socket cap: rounded block)
bm = bmesh.new(); bm_box(bm, 0.009, 0.007, 0.0075, 0, 0, -(r1 + 0.0032))
neck = obj_from_bm('neck', bm, rubber); finish(neck, bevel=0.0012, segments=3, angle=40)
parts.append(neck)

# ---- ribbed socket body (lathe), flared lip
z0 = -(r1 + 0.0065)
prof = [(0.0001, z0), (0.0082, z0), (0.0099, z0 - 0.0009), (0.0107, z0 - 0.0026), (0.0110, z0 - 0.005)]
z = z0 - 0.011
for k in range(3):          # three grip ribs
    prof += [(0.0110, z), (0.01165, z - 0.0007), (0.01165, z - 0.0019), (0.0110, z - 0.0026)]
    z -= 0.0058
zb = z - 0.004
prof += [(0.0110, zb), (0.0121, zb - 0.0026), (0.0124, zb - 0.0042), (0.0116, zb - 0.0056), (0.0074, zb - 0.0058),
         (0.0068, zb - 0.0030), (0.0001, zb - 0.0030)]
sock = lathe_obj('socket', prof, 48, rubber)
parts.append(sock)
z_lip = zb - 0.0058

# ---- nickel E12 thread band showing below the lip
tp = [(0.0001, z_lip + 0.002), (0.0063, z_lip + 0.002)]
zz = z_lip
for k in range(4):
    tp += [(0.0064, zz), (0.0059, zz - 0.0009), (0.0064, zz - 0.0018)]
    zz -= 0.0018
tp += [(0.0060, zz - 0.0006), (0.0056, zz - 0.0012), (0.0001, zz - 0.0012)]
thread = lathe_obj('thread', tp, 40, nickel)
parts.append(thread)
z_glass = zz - 0.0010

socket = join(parts, 'BulbSocket')
uv_tex(socket, 0.03)
uv_bake(socket, margin=0.006)
bake_and_swap(socket, 'bulb_socket', size=512, samples=40, ao_dist=0.006)
finalize_export_material(socket.data.materials[0])

# ---- glass: G45 globe (45 mm) with neck + exhaust tip
R = 0.0225
cz = z_glass - 0.0062 - math.sqrt(R * R - 0.0078 ** 2)
gp = [(0.0001, z_glass), (0.0058, z_glass), (0.0062, z_glass - 0.0025), (0.0078, z_glass - 0.0062)]
a0 = math.asin(0.0078 / R)
for i in range(1, 29):
    a = a0 + (math.pi - a0 - 0.12) * i / 28
    gp.append((R * math.sin(a), cz + R * math.cos(a)))
gp += [(0.0016, cz - R + 0.0003), (0.0011, cz - R - 0.0014), (0.0001, cz - R - 0.0018)]
m_bulb = flat_mat('BULB', (1.0, 0.88, 0.66), rough=0.04, emission=(1.0, 0.72, 0.42, 1.5))
glass = lathe_obj('BulbGlass', gp, 64, m_bulb)
uv_unit(glass)

# ---- LED filament: glass stem, two leads, and one vertical hairpin loop at the globe centre
m_fil = flat_mat('FILAMENT', (1.0, 0.62, 0.25), rough=0.4, emission=(1.0, 0.55, 0.18, 40.0))
fil_parts = []
stem = lathe_obj('stem', [(0.0001, z_glass - 0.001), (0.0017, z_glass - 0.001), (0.0014, cz + 0.006),
                          (0.0022, cz + 0.004), (0.0001, cz + 0.003)], 16, m_fil)
fil_parts.append(stem)
loop = []
for i in range(41):
    t = i / 40 * math.tau
    loop.append((0.0055 * math.sin(t), 0.0, cz - 0.001 - 0.0085 * math.cos(t) + 0.0005 * math.sin(3 * t)))
fil_parts.append(tube_obj('loop', loop, 0.00055, m_fil, bevel_res=2))
for sx in (-1, 1):
    fil_parts.append(tube_obj('lead', [(sx * 0.0012, 0, cz + 0.004), (sx * 0.0040, 0, cz + 0.0005),
                                       (sx * 0.0055, 0, cz - 0.001)], 0.00035, m_fil, bevel_res=1))
fil = join(fil_parts, 'BulbFilament')
uv_unit(fil)

for o in (glass, fil):
    o.parent = socket
print('[bulb] clip top z=%.4f  socket lip z=%.4f  glass centre z=%.4f  bottom z=%.4f' % (r1, z_lip, cz, cz - R - 0.0018))

export_glb([socket], 'camp_bulb.glb')

# ---- look-loop: lit sheet, then a night shot with the filament hot
preview([socket], 'bulb', height=0.3, key_energy=0.1)
wire = tube_obj('pv_wire', [(-0.08, 0, 0), (0.08, 0, 0)], WIRE_R, layered_mat('pv_wire', 'Plastic012B', scale=10))
uv_tex(wire, 0.05)
lit_shot('bulb_close', (0.07, -0.16, -0.03), (0, 0, -0.05), lens=60, size=768, energy=2.0)
lit_shot('bulb_night', (0.07, -0.16, -0.03), (0, 0, -0.05), lens=60, size=768, night=True,
         extra_lights=[((0.05, -0.08, 0.06), 0.4, (1, 0.8, 0.6), 0.02)])
