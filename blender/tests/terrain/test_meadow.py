"""Probe: a meadow-scale terrain with a level clearing, in EEVEE.

    cd <main checkout> && HEAVY_VRAM_GB=4 bash work/claude_body/work/tmp/heavy.sh 12 \
        bash run_blender.sh <worktree>/blender/tests/terrain/test_meadow.py [--cams eye,over,ground,edge,top]
        [--shading film|parity] [--variant soil|moss] [--grass] [--samples 16] [--res 960x540] [--tag name]
        [--shimmer] [--interp Auto|Cubic|Linear] [--detail 4,9] [--detile 1.2] [--no-detile]

Writes blender/tests/terrain/out/meadow_<tag>_<cam>.png and prints the heights it checked.
The daylight is a test fixture (sun lamp + Sky Texture), not a shipped sky; --grass adds the
test-only blade tufts (_grass_fixture.py) so the ground can be judged where it shows between blades.
'top' looks straight down on the clearing (13 m across): the place to judge tile repeats.
--shimmer also renders the 'edge' view with the camera turned by 0, 0.5 and 1 pixel
(meadow_<tag>_shimmer_<k>.png): run shimmer_metric.py (system Python) on them to measure how much the
ground crawls when the camera moves. --interp / --detail / --detile / --no-detile override the film
material's interpolation, detail_distance, detile_patch and anti_tile for like-for-like comparisons.

The terrain is 160 m at frequency 5: the same hill scale as the engine's 80 m / 2.5 default, wide
enough that a camera at eye height sees hills on the horizon instead of the mesh's edge.
"""
import math
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import _fixture as F  # noqa: E402

import bpy  # noqa: E402
from eidoblend.terrain import make_terrain  # noqa: E402

a = F.args()


def opt(name, default):
    return a[a.index(name) + 1] if name in a else default


cams = opt('--cams', 'eye,over,ground,edge').split(',')
shading = opt('--shading', 'film')
variant = opt('--variant', 'soil')
samples = int(opt('--samples', '16'))
W, H = (int(v) for v in opt('--res', '960x540').split('x'))
grass = '--grass' in a
tag = opt('--tag', '%s_%s%s' % (shading, variant, '_grass' if grass else ''))
mopts = {}
if '--interp' in a:
    mopts['interpolation'] = opt('--interp', 'Auto')
if '--detail' in a:
    mopts['detail_distance'] = tuple(float(v) for v in opt('--detail', '4,9').split(','))
if '--detile' in a:
    mopts['detile_patch'] = float(opt('--detile', '1.2'))
if '--no-detile' in a:
    mopts['anti_tile'] = False

VARIANTS = {
    # base (low ground + the clearing), mid (high ground, broken by noise), steep (banks)
    # withered_grass scans at luminance 0.32 against the soil's 0.14: a thatch that pale reads as
    # salt flats from eye height, so it is darkened toward the litter under a living sward.
    # Ground106's roughness map averages 0.64: looking toward the sun, dry soil that glossy sheens
    # like wet sand, so it is scaled up to ~0.87 (dry earth); the damp patches still lower it.
    'soil': [{'set': 'Ground106', 'tile_metres': 2.3, 'roughness': 1.35},
             {'set': 'withered_grass', 'tile_metres': 2.0, 'tint': (0.6, 0.58, 0.52)},
             {'set': 'coast_sand_01', 'tile_metres': 2.6}],
    'moss': [{'set': 'Ground106', 'tile_metres': 2.3, 'roughness': 1.35},
             {'set': 'Ground037', 'tile_metres': 2.0},
             {'set': 'coast_sand_01', 'tile_metres': 2.6}],
}

F.clean_scene()
F.render_settings(W, H, samples)
F.test_daylight(sun_elevation=24, sun_azimuth=300)
t = time.time()
terrain, height_at = make_terrain(size=160, segments=640, amplitude=2.5, seed=7, frequency=5,
                                  flat_radius=8, high_start=-0.2, slope_steep=(0.05, 0.1),
                                  layers=VARIANTS[variant], shading=shading, material_options=mopts)
print('[meadow] terrain %d verts, %d tris in %.2f s' % (len(terrain.data.vertices), len(terrain.data.polygons),
                                                        time.time() - t))
# the clearing is level: heights across it
ring = [height_at(r * math.cos(t), r * math.sin(t)) for r in (0, 2, 4, 6, 7.9) for t in (0, 1, 2, 3, 4, 5)]
print('[meadow] clearing heights: min %.4f max %.4f (flat_height 0)' % (min(ring), max(ring)))
if grass:
    import _grass_fixture
    _grass_fixture.add_test_grass(terrain, clear_radius=8.0, outer_radius=42.0)


def at(x, y, up):
    return (x, y, height_at(x, y) + up)


views = {
    'eye': (at(0, -7, 1.6), at(0, 30, 0.6), 35),
    'over': ((-26, -40, 18), (0, 2, 0), 35),
    'ground': (at(1.0, -3.0, 1.0), at(2.6, -1.2, 0), 35),
    'edge': (at(-3, -17, 1.4), at(9, -6, 0.2), 30),
    'top': ((0.0, 0.0, 9.0), (0.0, 0.0001, 0.0), 24),
}
F.OUT.mkdir(parents=True, exist_ok=True)
for c in cams:
    loc, look, lens = views[c]
    cam = F.camera('cam_' + c, loc, look, lens)
    F.render(cam, F.OUT / ('meadow_%s_%s.png' % (tag, c)))

if '--shimmer' in a:
    from mathutils import Matrix
    loc, look, lens = views['edge']
    cam = F.camera('cam_shimmer', loc, look, lens)
    bpy.context.view_layer.update()                  # matrix_world is stale until the depsgraph updates
    base = cam.matrix_world.copy()
    px = (cam.data.sensor_width / W) / cam.data.lens       # radians per pixel at the frame's centre
    for k in range(3):                                     # yaw about world Z through the camera
        p = base.translation.copy()
        cam.matrix_world = (Matrix.Translation(p) @ Matrix.Rotation(k * 0.5 * px, 4, 'Z')
                            @ Matrix.Translation(-p) @ base)
        bpy.context.view_layer.update()
        F.render(cam, F.OUT / ('meadow_%s_shimmer_%d.png' % (tag, k)))
