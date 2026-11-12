"""Probe: how EEVEE 5.2 renders water that is partly refracting, set up as EEVEE refracts (Dithered, ray-traced
refraction, a slab Thickness of the water's depth), at 16, 64 and 256 samples. Four wavy pools over a checker floor:

    clear           transmission 1                                     the refraction alone
    fractional      one Principled, Transmission Weight 0.5, tinted    a blend in one BSDF
    mix_foam        Mix Shader 0.5 of clear water and a white foam      a blend of two BSDFs
    pick            transmission 0 or 1 picked per sample by a white-noise hash of the position (the water3d and
                    shallow-water materials' pick), the same tint and share

Checks: the clear pool shows the floor refracted; the fractional and mixed pools keep a fixed pattern (their grain
does not fall from 64 to 256 samples) and lose the refraction (the floor's checker barely shows through them); the
pick converges (its grain falls with the samples) and shows the floor through its clear picks, over twice as plainly
as the fractional pool. This is why the water materials pick (fx/water3d/material.py, fx/swe.py).

    cd <main checkout> && HEAVY_VRAM_GB=4 bash work/claude_body/work/tmp/heavy.sh 12 \
        bash run_blender.sh <worktree>/blender/tests/water3d/probe_partial_transmission.py

Writes out/partial_transmission_<n>spp.png.
"""
import math
import os
import sys

import bpy
import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(HERE, 'out')
os.makedirs(OUT, exist_ok=True)
FAILS = []


def check(name, ok, detail=''):
    print(('PASS ' if ok else 'FAIL ') + name + (f'  ({detail})' if detail else ''), flush=True)
    if not ok:
        FAILS.append(name)


for o in list(bpy.data.objects):
    bpy.data.objects.remove(o, do_unlink=True)
sc = bpy.context.scene
sc.render.engine = 'BLENDER_EEVEE'
sc.render.resolution_x, sc.render.resolution_y = 960, 540
ee = sc.eevee
ee.use_raytracing = True
ee.ray_tracing_method = 'SCREEN'
ee.ray_tracing_options.resolution_scale = '1'
ee.ray_tracing_options.trace_max_roughness = 0.5
ee.use_fast_gi = True
ee.use_shadows = True
sc.view_settings.view_transform = 'AgX'
sc.render.image_settings.file_format = 'PNG'
w = bpy.data.worlds.new('sky')
sc.world = w
w.use_nodes = True
w.node_tree.nodes['Background'].inputs['Color'].default_value = (0.45, 0.6, 0.85, 1)
sd = bpy.data.lights.new('sun', 'SUN')
sd.energy = 4.0
sd.angle = math.radians(0.53)
sun = bpy.data.objects.new('sun', sd)
sc.collection.objects.link(sun)
sun.rotation_euler = (math.radians(40), 0, math.radians(30))

me = bpy.data.meshes.new('floor')
me.from_pydata([(-6, -6, 0), (6, -6, 0), (6, 6, 0), (-6, 6, 0)], [], [(0, 1, 2, 3)])
fl = bpy.data.objects.new('floor', me)
sc.collection.objects.link(fl)
fm = bpy.data.materials.new('checker')
fm.use_nodes = True
nt = fm.node_tree
ck = nt.nodes.new('ShaderNodeTexChecker')
ck.inputs['Scale'].default_value = 12.0
ck.inputs['Color1'].default_value = (0.75, 0.66, 0.5, 1)
ck.inputs['Color2'].default_value = (0.12, 0.10, 0.08, 1)
tc = nt.nodes.new('ShaderNodeTexCoord')
nt.links.new(tc.outputs['Object'], ck.inputs['Vector'])
nt.links.new(ck.outputs['Color'], nt.nodes['Principled BSDF'].inputs['Base Color'])
me.materials.append(fm)


def pool(name, x, y, mat):
    """a 1.6 x 1.6 m pool 0.25 m deep with a wavy top"""
    n = 64
    verts, faces = [], []
    for j in range(n + 1):
        for i in range(n + 1):
            u, v = i / n * 1.6 - 0.8, j / n * 1.6 - 0.8
            verts.append((u, v, 0.25 + 0.012 * math.sin(u * 9.0) * math.cos(v * 7.0) + 0.006 * math.sin(u * 23 + v * 17)))
    for j in range(n):
        for i in range(n):
            a = j * (n + 1) + i
            faces.append((a, a + 1, a + n + 2, a + n + 1))
    m = bpy.data.meshes.new(name)
    m.from_pydata(verts, [], faces)
    for p in m.polygons:
        p.use_smooth = True
    ob = bpy.data.objects.new(name, m)
    sc.collection.objects.link(ob)
    ob.location = (x, y, 0.0)
    m.materials.append(mat)
    return ob


def water(name):
    """EEVEE's refraction set-up: Dithered, ray-traced refraction, a slab of the pool's depth"""
    m = bpy.data.materials.new(name)
    m.use_nodes = True
    m.surface_render_method = 'DITHERED'
    m.use_raytrace_refraction = True
    m.thickness_mode = 'SLAB'
    nt = m.node_tree
    th = nt.nodes.new('ShaderNodeValue')
    th.outputs[0].default_value = 0.25
    nt.links.new(th.outputs[0], nt.nodes['Material Output'].inputs['Thickness'])
    p = nt.nodes['Principled BSDF']
    p.inputs['IOR'].default_value = 1.333
    p.inputs['Roughness'].default_value = 0.05
    return m, nt, p


CLEAR, TINT = (0.85, 0.95, 0.95, 1), (0.20, 0.42, 0.40, 1)
m_clear, _n, p = water('clear')
p.inputs['Base Color'].default_value = CLEAR
p.inputs['Transmission Weight'].default_value = 1.0
m_frac, _n, p = water('fractional')
p.inputs['Base Color'].default_value = TINT
p.inputs['Transmission Weight'].default_value = 0.5
m_mix, nt, p = water('mix_foam')
p.inputs['Base Color'].default_value = CLEAR
p.inputs['Transmission Weight'].default_value = 1.0
foam = nt.nodes.new('ShaderNodeBsdfPrincipled')
foam.inputs['Base Color'].default_value = (0.9, 0.92, 0.92, 1)
foam.inputs['Roughness'].default_value = 0.65
mx = nt.nodes.new('ShaderNodeMixShader')
mx.inputs['Fac'].default_value = 0.5
nt.links.new(p.outputs[0], mx.inputs[1])
nt.links.new(foam.outputs[0], mx.inputs[2])
nt.links.new(mx.outputs[0], nt.nodes['Material Output'].inputs['Surface'])
m_pick, nt, p = water('pick')
geo = nt.nodes.new('ShaderNodeNewGeometry')
wn = nt.nodes.new('ShaderNodeTexWhiteNoise')
wn.noise_dimensions = '3D'
nt.links.new(geo.outputs['Position'], wn.inputs['Vector'])
lt = nt.nodes.new('ShaderNodeMath')
lt.operation = 'LESS_THAN'
lt.inputs[1].default_value = 0.5
nt.links.new(wn.outputs['Value'], lt.inputs[0])
nt.links.new(lt.outputs[0], p.inputs['Transmission Weight'])
mc = nt.nodes.new('ShaderNodeMix')
mc.data_type = 'RGBA'
mc.inputs['A'].default_value = TINT
mc.inputs['B'].default_value = CLEAR
nt.links.new(lt.outputs[0], mc.inputs['Factor'])
nt.links.new(mc.outputs['Result'], p.inputs['Base Color'])

POOLS = {'clear': m_clear, 'fractional': m_frac, 'mix_foam': m_mix, 'pick': m_pick}
for i, (nm, mt) in enumerate(POOLS.items()):
    pool(nm, -0.9 + (i % 2) * 1.8, 0.9 - (i // 2) * 1.8, mt)
cd = bpy.data.cameras.new('cam')
cd.lens = 28
cam = bpy.data.objects.new('cam', cd)
sc.collection.objects.link(cam)
cam.location = (0.0, -3.2, 3.6)
cam.rotation_euler = (math.radians(42), 0, 0)
sc.camera = cam
bpy.context.view_layer.update()


def box_of(ob):
    """the pool's top in pixels (x0, y0, x1, y1), its middle 60 %"""
    from bpy_extras.object_utils import world_to_camera_view
    cs = [world_to_camera_view(sc, cam, ob.matrix_world @ v.co) for v in ob.data.vertices]
    xs, ys = [c.x * 960 for c in cs], [(1 - c.y) * 540 for c in cs]
    cx, cy, hw, hh = (min(xs) + max(xs)) / 2, (min(ys) + max(ys)) / 2, (max(xs) - min(xs)) * 0.3, (max(ys) - min(ys)) * 0.3
    return int(cx - hw), int(cy - hh), int(cx + hw), int(cy + hh)


def luma(path):
    im = bpy.data.images.load(path, check_existing=False)
    W, H = im.size
    px = np.empty(W * H * 4, np.float32)
    im.pixels.foreach_get(px)
    bpy.data.images.remove(im)
    return px.reshape(H, W, 4)[::-1, :, :3].mean(2)


def grain(a, box):
    """each pixel's departure from its 3 x 3 mean: the per-pixel grain"""
    x0, y0, x1, y1 = box
    r = a[y0:y1, x0:x1]
    k = sum(np.roll(np.roll(r, dy, 0), dx, 1) for dy in (-1, 0, 1) for dx in (-1, 0, 1)) / 9.0
    d = (r - k)[2:-2, 2:-2]
    return float(np.sqrt((d * d).mean()))


def checker_contrast(a, box):
    """how far the floor's checker shows through: the spread of the 8 x 8 px block means"""
    x0, y0, x1, y1 = box
    r = a[y0:y1, x0:x1]
    h, w = (r.shape[0] // 8) * 8, (r.shape[1] // 8) * 8
    blocks = r[:h, :w].reshape(h // 8, 8, w // 8, 8).mean((1, 3))
    return float(blocks.std())


res = {}
for spp in (16, 64, 256):
    ee.taa_render_samples = spp
    p = os.path.join(OUT, f'partial_transmission_{spp}spp.png')
    sc.render.filepath = p
    bpy.ops.render.render(write_still=True)
    a = luma(p)
    for nm in POOLS:
        b = box_of(bpy.data.objects[nm])
        res.setdefault(nm, {})[spp] = (grain(a, b), checker_contrast(a, b))
for nm in POOLS:
    print(f'[partial] {nm}: grain ' + ' / '.join(f'{res[nm][s][0]:.4f}' for s in (16, 64, 256))
          + ' at 16 / 64 / 256 spp; checker through it ' + f'{res[nm][256][1]:.4f}', flush=True)
g = {nm: res[nm][256][0] / max(res[nm][64][0], 1e-9) for nm in POOLS}
c = {nm: res[nm][256][1] for nm in POOLS}
check('the clear pool shows the floor refracted', c['clear'] > 0.03, f"checker {c['clear']:.4f}")
check('a fractional transmission keeps a fixed pattern (its grain does not fall from 64 to 256 samples) and loses '
      'the refraction', g['fractional'] > 0.9 and c['fractional'] < 0.5 * c['pick'],
      f"grain 256/64 {g['fractional']:.2f}, checker {c['fractional']:.4f} (the pick's {c['pick']:.4f})")
check('a Mix Shader of refraction and foam keeps a fixed pattern too', g['mix_foam'] > 0.9,
      f"grain 256/64 {g['mix_foam']:.2f}")
check('the per-sample pick converges (its grain falls with the samples) and shows the floor through its clear picks',
      g['pick'] < 0.85 and c['pick'] > 0.15 * c['clear'] and c['pick'] > 2 * c['fractional'],
      f"grain 256/64 {g['pick']:.2f}, checker {c['pick']:.4f} (clear {c['clear']:.4f}, fractional {c['fractional']:.4f})")
print(f'[partial] done: {len(FAILS)} FAIL', flush=True)
sys.exit(1 if FAILS else 0)
