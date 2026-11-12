"""The shimmer probe (design section 3): how much the meadow's ground crawls when the camera moves, under the
surfacing material's 'Auto' filtering.

    cd <main checkout> && HEAVY_VRAM_GB=4 bash work/claude_body/work/tmp/heavy.sh 12 bash run_blender.sh \\
        <worktree>/blender/tests/terrain/surfacing/test_shimmer.py [--views eye,over,edge,top] [--tag new]
        [--samples 16] [--res 960x540]
    python <worktree>/blender/tests/terrain/surfacing/shimmer_metric.py new

The scene: make_terrain('meadow', seed=7) (160 m, a level clearing of 8 m at the origin) in the 'meadow' palette, the
probe's test daylight (a sun lamp at 24 degrees from 300 degrees plus a Sky Texture world), its cameras, 960 x 540 at
16 samples; for the shimmer, the 'edge' view with the camera turned about world Z by 0, 0.5 and 1 pixel.
shimmer_metric.py's OLD_AUTO holds the numbers the previous film material scored in this probe (distant 0.14,
middle 0.11, near 0.22): the surfacing material must do no worse.
Writes out/surfacing/meadow_<tag>_<view>.png and meadow_<tag>_shimmer_<k>.png.
"""
import math
import sys
import time
from pathlib import Path

import bpy
from mathutils import Matrix, Vector

HERE = Path(__file__).resolve().parent
BLENDER_DIR = HERE.parents[2]
OUT = HERE.parent / 'out' / 'surfacing'
sys.path.insert(0, str(BLENDER_DIR))

argv = sys.argv[sys.argv.index('--') + 1:] if '--' in sys.argv else []


def opt(name, default):
    return argv[argv.index(name) + 1] if name in argv else default


TAG = opt('--tag', 'new')
VIEWS = opt('--views', 'eye,over,edge').split(',')
SAMPLES = int(opt('--samples', '16'))
W, H = (int(v) for v in opt('--res', '960x540').split('x'))


# ------------------------------------------------------------------------------- the probe's fixture ---
def clean_scene():
    bpy.ops.wm.read_factory_settings(use_empty=True)


def render_settings(width, height, samples):
    sc = bpy.context.scene
    sc.render.engine = 'BLENDER_EEVEE'
    sc.render.resolution_x, sc.render.resolution_y = width, height
    sc.render.resolution_percentage = 100
    sc.render.film_transparent = False
    ee = sc.eevee
    ee.taa_render_samples = samples
    ee.use_raytracing = True
    ee.use_shadows = True
    ee.use_fast_gi = True
    sc.view_settings.view_transform = 'AgX'
    sc.view_settings.exposure = 0.0
    sc.render.image_settings.file_format = 'PNG'


def test_daylight(sun_elevation=24.0, sun_azimuth=300.0, sun_strength=4.0, sky_strength=0.03):
    """TEST FIXTURE ONLY: a sun lamp and a matching Sky Texture world."""
    sc = bpy.context.scene
    w = bpy.data.worlds.new('test_daylight_world')
    sc.world = w
    nt = w.node_tree
    for n in list(nt.nodes):
        nt.nodes.remove(n)
    sky = nt.nodes.new('ShaderNodeTexSky')
    sky.sky_type = 'MULTIPLE_SCATTERING'
    sky.sun_disc = False
    sky.sun_elevation = math.radians(sun_elevation)
    sky.sun_rotation = math.radians(sun_azimuth)
    bg = nt.nodes.new('ShaderNodeBackground')
    bg.inputs['Strength'].default_value = sky_strength
    out = nt.nodes.new('ShaderNodeOutputWorld')
    tc = nt.nodes.new('ShaderNodeTexCoord')
    sep = nt.nodes.new('ShaderNodeSeparateXYZ')
    nt.links.new(tc.outputs['Generated'], sep.inputs[0])
    below = nt.nodes.new('ShaderNodeMapRange')
    below.interpolation_type = 'SMOOTHSTEP'
    below.inputs['From Min'].default_value = 0.004
    below.inputs['From Max'].default_value = -0.02
    nt.links.new(sep.outputs['Z'], below.inputs['Value'])
    mix = nt.nodes.new('ShaderNodeMix')
    mix.data_type = 'RGBA'
    nt.links.new(below.outputs['Result'], mix.inputs[0])
    nt.links.new(sky.outputs['Color'], mix.inputs[6])
    mix.inputs[7].default_value = tuple(c / max(sky_strength, 1e-6) for c in (0.105, 0.098, 0.085)) + (1.0,)
    nt.links.new(mix.outputs[2], bg.inputs['Color'])
    nt.links.new(bg.outputs['Background'], out.inputs['Surface'])
    L = bpy.data.lights.new('test_sun', 'SUN')
    L.energy = sun_strength
    L.angle = math.radians(0.53)
    L.color = (1.0, 0.96, 0.9)
    o = bpy.data.objects.new('test_sun', L)
    sc.collection.objects.link(o)
    el, az = math.radians(sun_elevation), math.radians(sun_azimuth)
    toward = Vector((math.sin(az) * math.cos(el), math.cos(az) * math.cos(el), math.sin(el)))
    o.rotation_euler = (-toward).to_track_quat('-Z', 'Y').to_euler()


def camera(name, location, look_at, lens):
    cd = bpy.data.cameras.new(name)
    cd.lens = lens
    cd.clip_start = 0.05
    cd.clip_end = 2000
    o = bpy.data.objects.new(name, cd)
    bpy.context.scene.collection.objects.link(o)
    o.location = Vector(location)
    o.rotation_euler = (Vector(look_at) - Vector(location)).to_track_quat('-Z', 'Y').to_euler()
    return o


def render(cam, path):
    sc = bpy.context.scene
    sc.camera = cam
    sc.render.filepath = str(path)
    t = time.time()
    bpy.ops.render.render(write_still=True)
    print(f'[shimmer] wrote {Path(path).name} ({time.time() - t:.1f} s)', flush=True)


# ------------------------------------------------------------------------------------------- the probe ---
def meadow():
    """The meadow terrain object and its height_at: make_terrain('meadow') with the probe's clearing."""
    from eidoblend.terrain import make_terrain
    t = make_terrain('meadow', seed=7, flatten=[{'at': (0.0, 0.0), 'radius': 8.0, 'falloff': 8.0}],
                     palette='meadow', dress=False, name='meadow')
    return t.obj, t.height_at


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    clean_scene()
    render_settings(W, H, SAMPLES)
    test_daylight()
    terrain, height_at = meadow()
    h0 = float(height_at(0.0, 0.0))

    def at(x, y, up):
        return (x, y, height_at(x, y) + up)
    views = {
        'eye': (at(0, -7, 1.6), at(0, 30, 0.6), 35),
        'over': ((-26, -40, h0 + 18), (0, 2, h0), 35),
        'ground': (at(1.0, -3.0, 1.0), at(2.6, -1.2, 0), 35),
        'edge': (at(-3, -17, 1.4), at(9, -6, 0.2), 30),
        'top': ((0.0, 0.0, h0 + 9.0), (0.0, 0.0001, h0), 24),
    }
    for v in VIEWS:
        loc, look, lens = views[v]
        render(camera('cam_' + v, loc, look, lens), OUT / f'meadow_{TAG}_{v}.png')
    loc, look, lens = views['edge']
    cam = camera('cam_shimmer', loc, look, lens)
    bpy.context.view_layer.update()
    base = cam.matrix_world.copy()
    px = (cam.data.sensor_width / W) / cam.data.lens            # radians per pixel at the frame's centre
    for k in range(3):                                          # yaw about world Z through the camera
        p = base.translation.copy()
        cam.matrix_world = Matrix.Translation(p) @ Matrix.Rotation(k * 0.5 * px, 4, 'Z') @ Matrix.Translation(-p) @ base
        bpy.context.view_layer.update()
        render(cam, OUT / f'meadow_{TAG}_shimmer_{k}.png')
    print('[shimmer] done', flush=True)


main()
