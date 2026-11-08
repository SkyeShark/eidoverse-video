"""The shallow water's erosion probe: the setup the water films used (The Shape the Water Left's wash).

A 17 x 17 m domain at 256^2 over the film's own ground (shape_water.js groundY, in Blender axes), erosion with
the film's parameters, the eroding terrain patch over a static ground built from the SAME bed_fn (sunk 1.5 m
under the patch interior, feathered to 0 at the rim, as liquids.md prescribes), rain set per frame, and the
film's 'seep' surge pour at the head of the valley. The storm is compressed: full rain (1e-4 m/s) from t = 0 and
the 0.05 m3/s seep from t = 2 s. Frame 1 is the dry patch (the case that used to z-fight black), later frames
the carved, braided wash with its rim.

    cd <main checkout> && bash run_blender.sh <worktree>/blender/tests/fx/test_swe_erosion.py -- render=0 end=720
    cd <main checkout> && HEAVY_VRAM_GB=4 bash work/claude_body/work/tmp/heavy.sh 12 \
        bash run_blender.sh <worktree>/blender/tests/fx/test_swe_erosion.py -- bake=0 end=720 frames=1,240,720

Soil maps: the film's soil_diff/rough/normal.jpg from maps=<dir> (default: the film's work folder, used when it
exists); without them the patch and the ground use the module's cut-colour soil.
Writes blender/tests/fx/out/swe_erosion_<cam>_f####.png (cams low, top, rim: a 2 m top crop of the domain rim).
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
from eidoblend.fx._util import color             # noqa: E402

args = dict(a.split('=', 1) for a in (sys.argv[sys.argv.index('--') + 1:] if '--' in sys.argv else []) if '=' in a)
OUT = os.path.join(HERE, 'out')
os.makedirs(OUT, exist_ok=True)
BLEND = os.path.join(OUT, 'swe_erosion.blend')
FPS = 24
END = int(args.get('end', 720))
FRAMES = [int(x) for x in args.get('frames', '1,240,720').split(',')]
CAMS = args.get('cams', 'low,top,rim').split(',')
MAPS = args.get('maps', 'E:/eidoverse-video-desktop-work-folder/erosion/assets/')
HAVE_MAPS = all(os.path.exists(os.path.join(MAPS, f'soil_{k}.jpg')) for k in ('diff', 'rough', 'normal'))


# ---- the film's ground (shape_water.js groundY), three (x, z) -> y; Blender bed_fn(x, y) = groundY(x, -y) -----
def _hsh(i, j):
    s = np.sin(i * 127.1 + j * 311.7) * 43758.5453
    return s - np.floor(s)


def _vn(x, z):
    ix, iz = np.floor(x), np.floor(z)
    fx, fz = x - ix, z - iz
    ux, uz = fx * fx * (3 - 2 * fx), fz * fz * (3 - 2 * fz)
    a, b, c, d = _hsh(ix, iz), _hsh(ix + 1, iz), _hsh(ix, iz + 1), _hsh(ix + 1, iz + 1)
    return (a * (1 - ux) + b * ux) * (1 - uz) + (c * (1 - ux) + d * ux) * uz


def _fbm(x, z):
    return _vn(x, z) * 0.55 + _vn(x * 2.13 + 7.7, z * 2.13 + 3.1) * 0.28 + _vn(x * 4.31 + 19, z * 4.31 + 11) * 0.17


def ground_y3(x, z):
    t = np.clip((z + 10) / 17, 0, 1)
    y = 2.4 * (1 - t * t * (3 - 2 * t))
    dm = np.maximum(0, 1 - np.maximum(np.abs(x), np.abs(z)) / 8.5)
    dmask = dm * dm * (3 - 2 * dm)
    y = y + 1.1 * (_fbm(x * 0.09 + 3, z * 0.09) - 0.5) * (1 - 0.75 * dmask)
    y = y + 0.24 * (_fbm(x * 0.55, z * 0.55) - 0.5) * (1 - 0.45 * t)
    y = y + dmask * 0.5 * ((x / 8.5) * (x / 8.5) - 0.55)
    y = y + np.exp(-((x + 15) ** 2 + (z + 15) ** 2) / 220) * 1.6
    return y


def bed_fn(x, y):
    return ground_y3(np.asarray(x, dtype=np.float64), -np.asarray(y, dtype=np.float64))


def soil_material(name):
    m = bpy.data.materials.new(name)
    if m.node_tree is None:
        m.use_nodes = True
    nt = m.node_tree
    bs = nt.nodes['Principled BSDF']
    bs.inputs['Roughness'].default_value = 0.95
    if not HAVE_MAPS:
        bs.inputs['Base Color'].default_value = (*[c * 1.35 for c in color('#4e3a24')], 1)
        return m
    tc = nt.nodes.new('ShaderNodeTexCoord')
    mp = nt.nodes.new('ShaderNodeMapping')
    mp.inputs['Scale'].default_value = (26 / 120, 26 / 120, 1)        # the film's world-locked period
    nt.links.new(tc.outputs['Object'], mp.inputs['Vector'])

    def tex(path, data):
        t = nt.nodes.new('ShaderNodeTexImage')
        t.image = bpy.data.images.load(path, check_existing=True)
        if data:
            t.image.colorspace_settings.is_data = True
        nt.links.new(mp.outputs['Vector'], t.inputs['Vector'])
        return t
    nt.links.new(tex(os.path.join(MAPS, 'soil_diff.jpg'), False).outputs['Color'], bs.inputs['Base Color'])
    nt.links.new(tex(os.path.join(MAPS, 'soil_rough.jpg'), True).outputs['Color'], bs.inputs['Roughness'])
    nm = nt.nodes.new('ShaderNodeNormalMap')
    nt.links.new(tex(os.path.join(MAPS, 'soil_normal.jpg'), True).outputs['Color'], nm.inputs['Color'])
    nt.links.new(nm.outputs['Normal'], bs.inputs['Normal'])
    return m


if args.get('bake', '1') != '0':
    for ob in list(bpy.data.objects):
        bpy.data.objects.remove(ob, do_unlink=True)
    sc = bpy.context.scene
    sc.render.engine = 'BLENDER_EEVEE'
    sc.render.resolution_x, sc.render.resolution_y = 960, 540
    sc.render.fps = FPS
    sc.frame_start, sc.frame_end = 1, END
    sc.eevee.taa_render_samples = 16
    sc.eevee.use_raytracing = True
    sc.eevee.use_shadows = True
    sc.view_settings.view_transform = 'AgX'

    # the static ground from the same bed_fn, 40 x 40 m, sunk 1.5 m under the patch interior (0 at the rim)
    n = 321
    xs = np.linspace(-20, 20, n)
    X, Y = np.meshgrid(xs, xs)
    dw = 8.5 - np.maximum(np.abs(X), np.abs(Y))
    s = np.clip(dw / 0.8, 0, 1)
    Z = bed_fn(X, Y) - 1.5 * s * s * (3 - 2 * s)
    verts = np.stack([X.ravel(), Y.ravel(), Z.ravel()], axis=1)
    a = np.arange(n * n).reshape(n, n)[:-1, :-1].ravel()
    quads = np.stack([a, a + 1, a + n + 1, a + n], axis=1)
    me = bpy.data.meshes.new('ground')
    me.vertices.add(len(verts))
    me.vertices.foreach_set('co', verts.astype(np.float32).ravel())
    me.loops.add(quads.size)
    me.loops.foreach_set('vertex_index', quads.ravel())
    me.polygons.add(len(quads))
    me.polygons.foreach_set('loop_start', np.arange(0, quads.size, 4))
    me.update(calc_edges=True)
    me.polygons.foreach_set('use_smooth', np.ones(len(quads), dtype=bool))
    ground = bpy.data.objects.new('ground', me)
    sc.collection.objects.link(ground)
    ground.data.materials.append(soil_material('ground_soil'))

    ero = dict(capacity=0.38, erode=0.5, deposit=0.38, bank=1.1, talus_slope=0.55, talus_rate=2.6, max_delta=0.4,
               cut_color='#4e3a24', silt_color='#a88a5e', wet_darken=0.5)
    if HAVE_MAPS:
        ero.update(terrain_maps=dict(albedo=os.path.join(MAPS, 'soil_diff.jpg'), rough=os.path.join(MAPS, 'soil_rough.jpg'),
                                     normal=os.path.join(MAPS, 'soil_normal.jpg')),
                   terrain_tex_period=120 / 26)
    swe = fxswe.create_water_swe(bed_fn, world_size=(17, 17), grid_size=(256, 256), domain_center=(0, 0, 0),
                                 spray_max=4096, shallow_color='#5f7a6e', absorption=2.1, rain_rate=4.6e-5,
                                 rain_patchiness=0.6, erosion=ero, cache_dir=os.path.join(OUT, 'swe_erosion_cache'),
                                 name='wash')
    S = swe.solver

    def controls(frame, t, w):
        w.set_rain(1.0e-4)
        q = 0.05 if t >= 2.0 else 0.0
        # the film's surge: three (0, 2.4, -7.9), v (0, -0.3, 1.4) -> Blender (0, 7.9, 2.4), v (0, -1.4, -0.3)
        w.set_pours([dict(x=0.0, y=7.9, z=2.4, vx=0.0, vy=-1.4, vz=-0.3, rate=q, style='seep', seep_width=3.6)]
                    if q > 0 else [])
        if frame % 120 == 0:
            d = S.dbed
            print(f'[test_swe_ero] t {t:5.1f} s  water {S.volume():7.3f} m3  wet cells {(S.h > 0.01).sum():6d}'
                  f'  dbed {float(d.min()):+.3f} .. {float(d.max()):+.3f}  silt max {float(S.silt.max()):.3f}')

    t0 = time.time()
    swe.bake(1, END, controls=controls)
    print(f'[test_swe_ero] bake {time.time() - t0:.1f} s')

    ld = bpy.data.lights.new('sun', 'SUN')
    ld.energy = 3.5
    ld.color = (1.0, 0.92, 0.82)
    ld.angle = math.radians(1.5)
    sun = bpy.data.objects.new('sun', ld)
    sc.collection.objects.link(sun)
    sun.rotation_euler = (math.radians(52), 0, math.radians(-35))
    world = bpy.data.worlds.new('sky')
    if world.node_tree is None:
        world.use_nodes = True
    wn = world.node_tree
    bg = wn.nodes['Background']
    wtc = wn.nodes.new('ShaderNodeTexCoord')
    sep = wn.nodes.new('ShaderNodeSeparateXYZ')
    wn.links.new(wtc.outputs['Generated'], sep.inputs[0])
    cr = wn.nodes.new('ShaderNodeValToRGB')
    cr.color_ramp.elements[0].color = (*color('#c9b7a2'), 1)
    cr.color_ramp.elements[1].color = (*color('#6a8fb8'), 1)
    wn.links.new(sep.outputs['Z'], cr.inputs['Fac'])
    wn.links.new(cr.outputs['Color'], bg.inputs['Color'])
    sc.world = world

    def camera(name, loc, look_at=None, angle=55, ortho=None):
        cd = bpy.data.cameras.new(name)
        if ortho:
            cd.type = 'ORTHO'
            cd.ortho_scale = ortho
        else:
            cd.angle = math.radians(angle)
        cd.clip_start, cd.clip_end = 0.05, 300
        c = bpy.data.objects.new(name, cd)
        sc.collection.objects.link(c)
        c.location = loc
        if look_at is not None:
            e = bpy.data.objects.new(name + '_look', None)
            sc.collection.objects.link(e)
            e.location = look_at
            k = c.constraints.new('TRACK_TO')
            k.target = e
            k.track_axis = 'TRACK_NEGATIVE_Z'
            k.up_axis = 'UP_Y'
        return c
    camera('low', (3.0, -13.0, 2.6), (0.0, 1.0, 0.3))
    camera('top', (0.0, 0.0, 40.0), ortho=21)
    camera('rim', (-8.5, -3.0, 40.0), ortho=2.0)
    sc.camera = sc.objects['low']
    bpy.ops.wm.save_as_mainfile(filepath=BLEND)
    print('[test_swe_ero] saved', BLEND)

if args.get('render', '1') != '0':
    bpy.ops.wm.open_mainfile(filepath=BLEND)
    sc = bpy.context.scene
    for f in FRAMES:
        for cam in CAMS:
            sc.frame_set(f)
            sc.camera = sc.objects[cam]
            res = (480, 480) if cam == 'rim' else (960, 540)
            sc.render.resolution_x, sc.render.resolution_y = res
            sc.render.filepath = os.path.join(OUT, f'swe_erosion_{cam}_f{f:04d}.png')
            t1 = time.time()
            bpy.ops.render.render(write_still=True)
            print(f'[test_swe_ero] {cam} f{f} {time.time() - t1:.1f} s -> {sc.render.filepath}')
    print('[test_swe_ero] DONE')
