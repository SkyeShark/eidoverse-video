"""eidoblend.fx.water_flat: three's WaterMesh (flat reflective water) and water_compute.js (a rippling height field).

    cd <main checkout> && HEAVY_VRAM_GB=4 bash work/claude_body/work/tmp/heavy.sh 8 \
        bash run_blender.sh <worktree>/blender/tests/water3d/test_water_flat.py [-- samples=32 parts=1,2,3,4,5]

1. A lake (out/wflat_lake_f####.png): a 300 m WaterMesh under the sky panorama, its sun bound to the scene's sun
   lamp, an island and a pier to reflect, frames 1 and 49 (the normal map scrolls with time).
2. A basin pool (out/wflat_pool_f####.png + sheet): createWaterCompute({width: 128, bounds: 0.67, circular: true}) in a
   stone basin, one drop then rain, 96 frames.
3. The engine's water_compute showcase (out/wflat_showcase_f0075.png): work/_showcase/water, option for option
   (width 128, bounds 20, color 0x2266aa; random disturbs of radius 2 and amplitude 0.4 on three of every four
   quarter-seconds), its camera, lights and background; its preview.jpg is the reference.
4. The helper expo's pool (out/wflat_expo_f0072.png): width 128, bounds 4.4, maxHeight 0.22, displaceScale 1,
   circular, inside a metal torus rim, a disturb every 6 frames circling the centre; left the engine's shading
   normal, right normals='surface'.
5. liquids.md's example (out/wflat_sea_sky_f0024.png): a 10 km WaterMesh (waterColor 0x285f66, distortionScale 3.7,
   sunDirection (0.5, 0.8, 0.2)) under a SkyMesh with its clouds; and the sky alone, cloudless, rendered to a linear
   EXR and read back against sky_mesh_radiance (the formula in numpy) at five directions.

Checks: the lake's material carries the WaterMesh uniforms and the sun drivers follow the lamp; two lake frames
differ; a drop's ripple ring spreads outward; heights stay inside +-max_height; the circular fade holds the rim
still; the player displaces the grid and stores the shading normal; the showcase's surface carries its disturbs.
"""

import math
import os
import random
import sys
import time

import bpy
import numpy as np

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import _scene as S  # noqa: E402
from eidoblend.fx.water_flat import create_water_mesh, create_water_compute, WATER_MESH_DEFAULTS  # noqa: E402

A = S.args()
SAMPLES = int(A.get('samples', 32))
PARTS = set(A.get('parts', '1,2,3,4,5').split(','))
ok = True
t0 = time.time()
sc = S.fresh_scene(res=(960, 540), fps=24, end=96, samples=SAMPLES)
SKY = os.path.join(S.HERE, '..', '..', '..', 'eidoverse', 'assets', 'sky', 'kloppenheim_puresky_ldr.png')


def clear():
    for ob in list(bpy.data.objects):
        bpy.data.objects.remove(ob, do_unlink=True)
    for p in list(bpy.data.lightprobes):
        bpy.data.lightprobes.remove(p)


# ---- 1. the lake --------------------------------------------------------------------------------------------
if '1' in PARTS:
    S.world_panorama(sc, SKY, strength=1.0, rotate_deg=180)
    sun = S.sun(sc, 'sun', azimuth_deg=95, elevation_deg=12, strength=3.0, col=(1.0, 0.88, 0.72))
    rock = S.pbr('island_rock', S.TEXCACHE + '/Concrete034_2k', 'Concrete034', scale=0.2, tint=(0.55, 0.52, 0.46))
    wood = S.pbr('pier_wood', S.TEXCACHE + '/Planks039_2k', 'Planks039', scale=0.8)
    S.lathe(sc, 'island', [(0, -2), (28, -2), (24, 1.5), (14, 6), (6, 9), (0, 9.5)], segments=48,
            loc=(60, 120, 0), mat=rock)
    for i in range(7):
        S.box(sc, f'pile{i}', (0.3, 0.3, 3.0), (-6 + i * 2.2, 14, 0.5), wood)
    S.box(sc, 'deck', (16, 2.4, 0.25), (0.6, 14, 2.0), wood)
    lake = create_water_mesh(size_xy=(300, 300), location=(0, 60, 0), sun_object=sun, water_color='#001e0f',
                             distortion_scale=3.7, size=1.0, normals_dir=os.path.join(S.OUT, 'water_normals'))
    nodes = lake.material.node_tree.nodes
    names = ['alpha', 'size', 'sun_color', 'sun_direction', 'water_color', 'distortion_scale']
    ok &= S.check('WaterMesh uniforms are named nodes', all(('wm.' + k) in nodes for k in names),
                  ', '.join(k for k in names if ('wm.' + k) not in nodes) or 'all six + time')
    ok &= S.check('every WaterMesh option is in params', all(k in lake.params for k in WATER_MESH_DEFAULTS))
    sc.frame_set(1)
    sd = nodes['wm.sun_direction']
    want = np.array(sun.matrix_world.to_3x3().col[2])
    got = np.array([sd.inputs[i].default_value for i in range(3)])
    ok &= S.check('sun_direction follows the lamp (drivers)', np.allclose(want, got, atol=1e-4), f'{got} vs {want}')
    S.camera_look(sc, (-4, -6, 2.2), (30, 90, 1.0), lens=32)
    pa, pb = os.path.join(S.OUT, 'wflat_lake_f0001.png'), os.path.join(S.OUT, 'wflat_lake_f0049.png')
    ok &= S.render(sc, 1, pa)
    ok &= S.render(sc, 49, pb)
    d = float(np.abs(S.read_png(pa).astype(np.float32) - S.read_png(pb).astype(np.float32)).mean())
    ok &= S.check('the lake surface animates (frames 1 and 49 differ)', d > 0.3, f'mean |diff| {d:.2f}')
    clear()

# ---- 2. the basin pool --------------------------------------------------------------------------------------
if '2' in PARTS:
    sc.frame_start, sc.frame_end = 1, 96
    stone = S.pbr('basin_stone2', S.TEXCACHE + '/Concrete034_2k', 'Concrete034', scale=1.6,
                  tint=(0.92, 0.88, 0.80))
    paving = S.pbr('paving2', S.TEXCACHE + '/PavingStones128_1k', 'PavingStones128', scale=0.55)
    S.lathe(sc, 'basin', [(0.0, 0.0), (0.26, 0.0), (0.26, 0.05), (0.17, 0.09), (0.13, 0.18), (0.12, 0.30),
                          (0.15, 0.36), (0.26, 0.39), (0.34, 0.44), (0.38, 0.52), (0.395, 0.60), (0.40, 0.665),
                          (0.39, 0.683), (0.37, 0.688), (0.35, 0.684), (0.34, 0.665), (0.33, 0.60), (0.31, 0.52),
                          (0.26, 0.46), (0.16, 0.432), (0.0, 0.425)], segments=96, mat=stone)
    S.box(sc, 'ground', (24.0, 24.0, 0.2), (0, 0, -0.1), paving)
    S.world_panorama(sc, SKY, strength=1.0, rotate_deg=40)
    S.sun(sc, 'sun2', azimuth_deg=-60, elevation_deg=38, strength=3.2)
    # the pool fills the basin at 0.62 m (inner radius ~0.335 there): a 0.67 m square grid, clipped to its disc
    pool = create_water_compute(width=128, bounds=0.67, circular=True, location=(0, 0, 0.62), color=0x335577,
                                roughness=0.08, metalness=0.0, opacity=0.9, viscosity=0.985)
    rng = np.random.default_rng(3)
    rings = []

    def controls(frame, t, w):
        if frame == 6:
            w.disturb(-0.12, 0.08, 0.025, 0.004)          # one drop, to measure its ring
        elif frame > 30 and frame % 3 == 0:
            x, y = rng.uniform(-0.25, 0.25, 2)
            w.disturb(float(x), float(y), 0.015, 0.0025)   # rain
        if 10 <= frame <= 30:
            h = w.heights
            W = w.W
            iz, ix = np.mgrid[0:W, 0:W]
            cx, cz = (-0.12 / w.B + 0.5) * W, (-0.08 / w.B + 0.5) * W
            r = np.hypot(ix - cx, iz - cz) * w.B / W
            prof = np.array([np.abs(h[(r >= a) & (r < a + 0.01)]).mean() if ((r >= a) & (r < a + 0.01)).any()
                             else 0 for a in np.arange(0, 0.3, 0.01)])
            rings.append((frame, float(np.argmax(prof[2:]) + 2) * 0.01))

    pool.bake(1, 96, controls=controls, cache_dir=os.path.join(S.OUT, 'pool_cache'))
    radii = [r for f, r in rings]
    ok &= S.check('a drop\'s ripple ring spreads outward', len(radii) > 4 and radii[-1] > radii[0] + 0.03,
                  f'ring radius {radii[0]:.2f} -> {radii[-1]:.2f} m over frames 10..30')
    ok &= S.check('heights stay inside +-max_height', float(np.abs(pool.heights).max()) <= pool.max_height + 1e-6,
                  f'{np.abs(pool.heights).max():.4f} <= {pool.max_height:.4f}')
    sc.frame_set(48)
    ev = pool.mesh.evaluated_get(bpy.context.evaluated_depsgraph_get())
    me = ev.to_mesh()
    co = np.zeros(len(me.vertices) * 3)
    me.vertices.foreach_get('co', co)
    co = co.reshape(-1, 3)
    has_n = 'wave_normal' in me.attributes
    ev.to_mesh_clear()
    rim = np.hypot(co[:, 0], co[:, 1]) >= 0.5 * 0.67                     # the disc's rim and the clipped corners
    ok &= S.check('the player displaces the grid and stores the shading normal',
                  float(np.abs(co[:, 2]).max()) > 1e-4 and has_n, f'max |dz| {np.abs(co[:, 2]).max():.4f} m')
    ok &= S.check('the circular fade holds the rim still', float(np.abs(co[rim, 2]).max()) < 1e-6)
    S.camera_look(sc, (-0.95, -1.15, 1.45), (0.0, 0.0, 0.58), lens=50)
    shots = []
    for f in (12, 24, 48, 72, 96):
        p = os.path.join(S.OUT, f'wflat_pool_f{f:04d}.png')
        ok &= S.render(sc, f, p)
        shots.append(p)
    S.contact_sheet(shots, os.path.join(S.OUT, 'wflat_pool_sheet.png'), cols=3)
    clear()

# ---- 3. the engine's water_compute showcase -------------------------------------------------------------------
if '3' in PARTS:
    sc.render.fps = 30
    sc.frame_start, sc.frame_end = 1, 75
    # background 0x16202c, AmbientLight 0x445566 x 1.0, DirectionalLight (5, 12, 8) x 2.5 (ACES there, AgX here)
    # the engine's material had no envMap: its reflections saw nothing, so the world's glossy rays see black here
    S.world_backdrop(sc, camera_col=0x16202c, ambient_col=0x445566, ambient_strength=1.0, match_display=True,
                     glossy=(0x000000, 0.0))
    S.sun_three(sc, 'key', (5, 12, 8), 0xffffff, 2.5)
    S.camera_three(sc, (0, 8, 14), (0, 0, 0), 50)
    show = create_water_compute(name='showcase', width=128, bounds=20.0, color=0x2266aa)
    rnd = random.Random(11)

    def show_controls(frame, t, w):
        if math.floor(t * 4) % 3 == 0:
            w.disturb((rnd.random() - 0.5) * 12, (rnd.random() - 0.5) * 12, 2.0, 0.4)

    show.bake(1, 75, controls=show_controls, cache_dir=os.path.join(S.OUT, 'showcase_cache'))
    hmax = float(np.abs(show.heights).max())
    ok &= S.check('the showcase surface carries its disturbances', hmax > 0.1, f'max |h| {hmax:.3f} m')
    ok &= S.render(sc, 75, os.path.join(S.OUT, 'wflat_showcase_f0075.png'))
    clear()

# ---- 4. the expo pool: engine normals vs surface normals ------------------------------------------------------
if '4' in PARTS:
    sc.render.fps = 30
    sc.frame_start, sc.frame_end = 1, 72
    S.world_panorama(sc, SKY, strength=0.8, rotate_deg=0)
    S.sun(sc, 'sun4', azimuth_deg=30, elevation_deg=40, strength=3.0)
    metal = S.principled('rim_metal', 0x50545a, rough=0.6, metal=0.5)
    for side, nm in ((-2.9, 'engine'), (2.9, 'surface')):
        p = create_water_compute(name='expo_' + nm, width=128, bounds=4.4, color=0x1e64b4, circular=True,
                                 max_height=0.22, displace_scale=1.0, normals=nm, location=(side, 0, 0.07))

        def expo_controls(frame, t, w):
            if frame % 6 == 0:
                a = t * 0.9
                w.disturb(math.cos(a) * 1.2, math.sin(a) * 1.2, 0.32, 0.55)

        p.bake(1, 72, controls=expo_controls, cache_dir=os.path.join(S.OUT, 'expo_cache'))
        bpy.ops.mesh.primitive_torus_add(major_radius=2.55, minor_radius=0.14, major_segments=48, minor_segments=10,
                                         location=(side, 0, 0.1))
        bpy.context.active_object.data.materials.append(metal)
    S.box(sc, 'floor', (30, 30, 0.1), (0, 0, -0.3), S.principled('floor4', 0x3a3d42, rough=0.8))
    S.camera_look(sc, (0, -8.5, 5.0), (0, 0, 0), lens=30)
    ok &= S.render(sc, 72, os.path.join(S.OUT, 'wflat_expo_f0072.png'))
    clear()

# ---- 5. liquids.md's example: WaterMesh under a SkyMesh, and the sky against its own formula ----------------------
if '5' in PARTS:
    from eidoblend.fx.water_flat import create_sky_mesh, sky_mesh_radiance
    from eidoblend.fx._util import read_exr
    sc.render.fps = 24
    sc.frame_start, sc.frame_end = 1, 48
    # sunDirection (0.5, 0.8, 0.2) in three axes = Blender (0.5, -0.2, 0.8); the sky's sunPosition set to match
    sd = np.array([0.5, -0.2, 0.8])
    sd = sd / np.linalg.norm(sd)
    # (a) the sky alone, cloudless, rendered to linear EXR and read back against the formula at known directions
    sky = create_sky_mesh(sun_position=(0.3, -1.0, 0.5), turbidity=10.0, rayleigh=2.0, cloud_coverage=0.0)
    S.camera_look(sc, (0, 0, 0), (0, 10, 2.5), lens=24)
    cam = sc.camera
    sc.view_settings.view_transform = 'Standard'
    sc.render.resolution_x, sc.render.resolution_y = 320, 180
    sc.eevee.taa_render_samples = 1
    sc.render.image_settings.media_type = 'IMAGE'
    sc.render.image_settings.file_format = 'OPEN_EXR'
    p_exr = os.path.join(S.OUT, 'wflat_sky_check.exr')
    sc.frame_set(1)
    sc.render.filepath = p_exr
    bpy.ops.render.render(write_still=True)
    img = read_exr(p_exr)[::-1, :, :3]                   # read_exr gives row 0 = bottom: flip to row 0 = top
    Hh, Ww = img.shape[:2]
    cd = cam.data
    sw = cd.sensor_width
    sh = sw * Hh / Ww
    R = np.array(cam.matrix_world.to_3x3())
    errs = []
    for (u, v) in ((0.2, 0.25), (0.5, 0.5), (0.8, 0.7), (0.35, 0.85), (0.65, 0.15)):
        px, py = int(u * Ww), int(v * Hh)
        dcam = np.array([((px + 0.5) / Ww - 0.5) * sw, (0.5 - (py + 0.5) / Hh) * sh, -cd.lens])
        dw = R @ (dcam / np.linalg.norm(dcam))
        ref = sky_mesh_radiance(dw[None], sky.params)[0]
        got = img[py, px]
        errs.append(float(np.abs(got - ref).max() / max(ref.max(), 1e-6)))
    ok &= S.check('SkyMesh: the world matches its formula (cloudless, 5 directions, max rel err < 3 %)',
                  max(errs) < 0.03, ', '.join(f'{e * 100:.2f} %' for e in errs))
    sc.render.image_settings.file_format = 'PNG'
    sc.view_settings.view_transform = 'AgX'
    sc.render.resolution_x, sc.render.resolution_y = 960, 540
    sc.eevee.taa_render_samples = SAMPLES
    # (b) the example itself: a 10 km WaterMesh (waterColor 0x285f66, distortionScale 3.7) under a cloudy SkyMesh
    sky = create_sky_mesh(sun_position=tuple(sd), turbidity=10.0, rayleigh=2.0, mie_coefficient=0.005,
                          mie_directional_g=0.8, cloud_coverage=0.4, cloud_density=0.4, cloud_elevation=0.5)
    sea = create_water_mesh(size_xy=(10000, 10000), location=(0, 0, 0), sun_direction=(0.5, 0.8, 0.2),
                            sun_color=0xffffff, water_color=0x285f66, distortion_scale=3.7,
                            normals_dir=os.path.join(S.OUT, 'water_normals'))
    S.camera_look(sc, (0, -30, 6), (0, 60, 4), lens=30)
    sc.view_settings.exposure = -1.0                  # three's ocean example renders at toneMappingExposure 0.5
    ok &= S.render(sc, 24, os.path.join(S.OUT, 'wflat_sea_sky_f0024.png'))
    sc.view_settings.exposure = 0.0
bpy.ops.wm.save_as_mainfile(filepath=os.path.join(S.OUT, 'wflat_water_flat.blend'))
print('ALL PASS' if ok else 'SOME FAIL', f'({time.time() - t0:.1f} s)')
