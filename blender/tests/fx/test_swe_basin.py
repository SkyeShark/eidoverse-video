"""The shallow-water port's first probe: the engine's swe_demo (an empty bowl filling from three rim spouts,
then a chrome wader breaching the pool), baked with eidoblend.fx.swe and rendered in EEVEE.

    cd <main checkout> && HEAVY_VRAM_GB=4 bash work/claude_body/work/tmp/heavy.sh 12 \
        bash run_blender.sh <worktree>/blender/tests/fx/test_swe_basin.py [-- end=288 frames=72,168,240,288]
    (more: style=demo|natural, bake=0 render=0, samples=64 tag=_s64 for the water's convergence)

The bake is CPU only (numpy, ~0.2 s a frame at 256^2 with 6144 spray slots); the render needs the GPU slot.
The wader follows the demo's SWE_TEST timeline (it drops at t = 4 s instead of 22 s), so a short bake shows
the breach. Writes blender/tests/fx/out/swe_basin_f####.png and the EXR caches under out/swe_cache/.
Reference: E:/eidoverse-video-desktop-work-folder/swe_demo/swe_fill_demo.mp4 (WebGPU).
"""

import math
import os
import sys
import time

import bpy
import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.normpath(os.path.join(HERE, '..', '..')))
from eidoblend.fx import swe as fxswe            # noqa: E402
from eidoblend.fx._util import color, from_three  # noqa: E402

args = dict(a.split('=', 1) for a in (sys.argv[sys.argv.index('--') + 1:] if '--' in sys.argv else []) if '=' in a)
FPS = int(args.get('fps', 24))
END = int(args.get('end', 288))
FRAMES = [int(x) for x in args.get('frames', '72,168,240,288').split(',')]
RES = [int(x) for x in args.get('res', '960x540').split('x')]
OUT = os.path.join(HERE, 'out')
os.makedirs(OUT, exist_ok=True)
BAKE = args.get('bake', '1') == '1'

for ob in list(bpy.data.objects):
    bpy.data.objects.remove(ob, do_unlink=True)
sc = bpy.context.scene
sc.render.engine = 'BLENDER_EEVEE'
sc.render.resolution_x, sc.render.resolution_y = RES
sc.render.fps = FPS
sc.frame_start, sc.frame_end = 1, END
sc.eevee.taa_render_samples = int(args.get('samples', 16))
sc.eevee.use_raytracing = True
sc.eevee.ray_tracing_method = 'SCREEN'
sc.eevee.use_shadows = True
sc.view_settings.view_transform = 'AgX'
sc.view_settings.exposure = float(args.get('exposure', 0.0))


# ---- the bed: ONE profile drives the sim and the visible basin (the demo's bedFn) --------------------
def sm(t):
    t = np.clip(t, 0.0, 1.0)
    return t * t * (3 - 2 * t)


def bed_fn(x, y):
    r = np.hypot(x, y)
    return np.where(r < 3.2, -1.6, np.where(r < 4.9, -1.6 + 1.6 * sm((r - 3.2) / 1.7),
                    np.where(r < 5.15, 0.02, 0.02 + 1.3 * sm((r - 5.15) / 0.2))))


rs = np.linspace(0.001, 5.4, 97)
prof = bed_fn(rs, np.zeros_like(rs))
SEG = 128
ang = np.arange(SEG) / SEG * 2 * math.pi
verts = np.array([(r * math.cos(a), r * math.sin(a), z) for r, z in zip(rs, prof) for a in ang])
faces = [(i * SEG + j, i * SEG + (j + 1) % SEG, (i + 1) * SEG + (j + 1) % SEG, (i + 1) * SEG + j)
         for i in range(len(rs) - 1) for j in range(SEG)]
me = bpy.data.meshes.new('basin')
me.from_pydata(verts.tolist(), [], faces)
for p in me.polygons:
    p.use_smooth = True
basin = bpy.data.objects.new('basin', me)
sc.collection.objects.link(basin)
bm = bpy.data.materials.new('basin_stone')
bm.use_nodes = True
nt = bm.node_tree
bs = nt.nodes['Principled BSDF']
nz = nt.nodes.new('ShaderNodeTexNoise')
nz.inputs['Scale'].default_value = 3.0
nz.inputs['Detail'].default_value = 8.0
ramp = nt.nodes.new('ShaderNodeValToRGB')
ramp.color_ramp.elements[0].color = (*color('#6f665b'), 1)
ramp.color_ramp.elements[1].color = (*color('#a39a8b'), 1)
nt.links.new(nz.outputs['Fac'], ramp.inputs['Fac'])
nt.links.new(ramp.outputs['Color'], bs.inputs['Base Color'])
bs.inputs['Roughness'].default_value = 0.88
bump = nt.nodes.new('ShaderNodeBump')
bump.inputs['Strength'].default_value = 0.25
nt.links.new(nz.outputs['Fac'], bump.inputs['Height'])
nt.links.new(bump.outputs['Normal'], bs.inputs['Normal'])
basin.data.materials.append(bm)

# ---- spouts, wader, lights, camera ---------------------------------------------------------------------
spouts = []
for deg in (78, 112, 146):
    a = math.radians(deg)
    spouts.append((math.cos(a) * 4.55, math.sin(a) * 4.55, a))
sp_mat = bpy.data.materials.new('spout')
sp_mat.use_nodes = True
spb = sp_mat.node_tree.nodes['Principled BSDF']
spb.inputs['Base Color'].default_value = (*color(0x1d3a38), 1)
spb.inputs['Metallic'].default_value = 0.4
spb.inputs['Roughness'].default_value = 0.6
for x3, z3, a in spouts:
    bpy.ops.mesh.primitive_cone_add(vertices=24, radius1=0.2, radius2=0.16, depth=0.5,
                                    location=tuple(from_three((x3 * 1.06, 0.3, z3 * 1.06))))
    bpy.context.active_object.data.materials.append(sp_mat)

bpy.ops.mesh.primitive_uv_sphere_add(segments=48, ring_count=32, radius=0.42)
wader = bpy.context.active_object
wader.name = 'wader'
for p in wader.data.polygons:
    p.use_smooth = True
wm = bpy.data.materials.new('chrome')
wm.use_nodes = True
wb = wm.node_tree.nodes['Principled BSDF']
wb.inputs['Base Color'].default_value = (*color(0xd8dde2), 1)
wb.inputs['Metallic'].default_value = 1.0
wb.inputs['Roughness'].default_value = 0.12
wader.data.materials.append(wm)


def wader_pos3(t):
    tw = t + 18.0                                 # the demo's SWE_TEST timeline
    if tw < 22:
        return (-2.6, 4.5, -1.2)
    if tw < 24:
        k = (tw - 22) / 2
        return (-2.6, 4.5 - 5.62 * k * k, -1.2)
    if tw < 38:
        k = (tw - 24) / 14
        return (-2.6 + 5.2 * k, -1.12, -1.2 + 2.4 * k)
    k = min(1, (tw - 38) / 3)
    return (2.6, -1.12 + 4.0 * k * k, 1.2)


def cam_pos3(t):
    k = min(1, t / 45)
    a = 0.25 * math.sin(k * math.pi)
    return (9.2 - 2.2 * k + 2 * a, 5.6 - 1.2 * k, 8.4 - 1.6 * k - 2 * a)


cd = bpy.data.cameras.new('cam')
cd.sensor_fit = 'VERTICAL'
cd.angle = math.radians(42)
cd.clip_start, cd.clip_end = 0.05, 400
cam = bpy.data.objects.new('cam', cd)
sc.collection.objects.link(cam)
look = bpy.data.objects.new('look', None)
sc.collection.objects.link(look)
look.location = tuple(from_three((0, -0.9, 0)))
cc = cam.constraints.new('TRACK_TO')
cc.target = look
cc.track_axis = 'TRACK_NEGATIVE_Z'
cc.up_axis = 'UP_Y'
sc.camera = cam
for f in range(1, END + 1):
    t = (f - 1) / FPS
    wader.location = tuple(from_three(wader_pos3(t)))
    wader.keyframe_insert('location', frame=f)
    cam.location = tuple(from_three(cam_pos3(t)))
    cam.keyframe_insert('location', frame=f)


def sun(name, dir3, col, strength):
    ld = bpy.data.lights.new(name, 'SUN')
    ld.energy = strength
    ld.color = color(col)
    ld.angle = math.radians(1.0)
    o = bpy.data.objects.new(name, ld)
    sc.collection.objects.link(o)
    d = -np.array(from_three(dir3), dtype=float)
    d /= np.linalg.norm(d)
    o.rotation_mode = 'QUATERNION'
    from mathutils import Vector
    o.rotation_quaternion = Vector(d).to_track_quat('-Z', 'Y')
    return o


STYLE = args.get('style', 'demo')     # demo: the swe_demo's glowing palette; natural: the engine's default water
sun('sun', (-8, 7, 4), 0xffd9b0, 5.5)
fill = sun('fill', (6, 5, 8), 0x86d2ff, 1.6)
fill.data.use_shadow = False
world = bpy.data.worlds.new('dusk')
world.use_nodes = True
wn = world.node_tree
bg = wn.nodes['Background']
bg.inputs['Color'].default_value = (*color(0xb08b78), 1)   # hemisphere + ambient light of the demo
bg.inputs['Strength'].default_value = 0.6
if STYLE == 'natural':
    # a plain vertical gradient (zenith to horizon) so the water has something to reflect: a test backdrop,
    # not a sky (the sky family's Eanpa port is the sky)
    tc = wn.nodes.new('ShaderNodeTexCoord')
    sep = wn.nodes.new('ShaderNodeSeparateXYZ')
    wn.links.new(tc.outputs['Generated'], sep.inputs[0])
    rmp = wn.nodes.new('ShaderNodeMapRange')
    rmp.inputs['From Min'].default_value = -0.1
    rmp.inputs['From Max'].default_value = 0.6
    wn.links.new(sep.outputs['Z'], rmp.inputs['Value'])
    cr = wn.nodes.new('ShaderNodeValToRGB')
    cr.color_ramp.elements[0].color = (*color('#d9c2ad'), 1)
    cr.color_ramp.elements[1].color = (*color('#5f86b0'), 1)
    wn.links.new(rmp.outputs['Result'], cr.inputs['Fac'])
    wn.links.new(cr.outputs['Color'], bg.inputs['Color'])
    bg.inputs['Strength'].default_value = 1.0
void = wn.nodes.new('ShaderNodeBackground')
void.inputs['Color'].default_value = (*color(0x40262c), 1)   # what the camera sees: the demo's dusk void
lp = wn.nodes.new('ShaderNodeLightPath')
mx = wn.nodes.new('ShaderNodeMixShader')
wn.links.new(lp.outputs['Is Camera Ray'], mx.inputs['Fac'])
wn.links.new(bg.outputs[0], mx.inputs[1])
wn.links.new(void.outputs[0], mx.inputs[2])
wn.links.new(mx.outputs[0], wn.nodes['World Output'].inputs['Surface'])
sc.world = world

# ---- THE WATER --------------------------------------------------------------------------------------
look = dict(deep_color='#04262a', shallow_color='#2ba393', absorption=2.45, surface_opacity=0.8,
            emissive_color='#1ee0c2', emissive_strength=0.45, emissive_falloff=3.8,
            foam_color='#e8f8f2', foam_strength=0.72) if STYLE == 'demo' else {}
swe = fxswe.create_water_swe(
    bed_fn, world_size=(10.8, 10.8), grid_size=(256, 256), domain_center=(0, 0, 0), substeps=3,
    spray_max=6144, spray_size=0.075, cache_dir=os.path.join(OUT, 'swe_cache'), name='swe', **look)
POURS = []
for x3, z3, a in spouts:
    POURS.append(dict(pos=from_three((x3 * 1.06 - math.cos(a) * 0.15, 0.53, z3 * 1.06 - math.sin(a) * 0.15)),
                      vel=from_three((-math.cos(a) * 1.7, -0.4, -math.sin(a) * 1.7))))


def controls(frame, t, w):
    rate = 0.5 if t < 34 else 0.0
    w.set_pours([dict(x=p['pos'][0], y=p['pos'][1], z=p['pos'][2], vx=p['vel'][0], vy=p['vel'][1], vz=p['vel'][2],
                      rate=rate) for p in POURS])


t0 = time.time()
if BAKE:
    swe.bake(1, END, controls=controls, track_spheres=[(wader, 0.42)])
else:
    swe._attach(1, END)
print(f'[test_swe] bake {time.time() - t0:.1f} s')
bpy.ops.wm.save_as_mainfile(filepath=os.path.join(OUT, 'swe_basin.blend'))
for f in (FRAMES if args.get('render', '1') == '1' else []):
    sc.frame_set(f)
    sc.render.filepath = os.path.join(OUT, f'swe_basin_{STYLE}{args.get("tag", "")}_f{f:04d}.png')
    t1 = time.time()
    bpy.ops.render.render(write_still=True)
    print(f'[test_swe] frame {f} rendered in {time.time() - t1:.1f} s -> {sc.render.filepath}')
print('[test_swe] DONE')
