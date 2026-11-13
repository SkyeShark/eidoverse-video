"""What the terrain material costs per frame, against grey clay on the same frame (one Blender process, through a GPU
slot; other jobs share the GPU, so each palette's textured and clay frames alternate and the best of each counts):

    cd <main checkout> && HEAVY_VRAM_GB=4 bash work/claude_body/work/tmp/heavy.sh 12 bash run_blender.sh \\
        <worktree>/blender/tests/terrain/surfacing/bench_material.py [--palettes alpine,desert_sandstone]
        [--variants full,no_far,...] [--reps 3] [--tag b1]

The scene: a 1.6 km square of ground (512 x 512 vertices) with gentle hills and two steep walls, every eido_<mask>
attribute the palettes read filled with plausible values (slopes from the surface, the rest from smooth noise), a
camera 120 m up looking across it at 35 mm so the ground fills the frame from 10 m to the horizon, make_sky-free
light (a sun lamp and a uniform world, so only the material's shading differs), EEVEE 960 x 540, 16 samples,
anisotropic filtering 16x. Variants (options over the palette's): full; no_far (far_scale 1); offset (detile
'offset', no far de-tiling, no macro map: the old material's reads); single (anti_tile off); and edits of the
palette: no_canopy, no_patches, no_fbm (fbm() read as the 2-octave noise()), bare (all three, no streaks, tone or
macro). Writes
out/surfacing/bench_<tag>.json: per palette and variant the first frame (shader compile), the best textured and clay
frames and their difference (the material's own cost), the node count and images.
"""
import json
import math
import sys
import time
from pathlib import Path

import bpy
import numpy as np

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parents[2]))
from eidoblend.terrain.build import palettes as P  # noqa: E402
from eidoblend.terrain.build import surfacing as S  # noqa: E402

OUT = HERE.parent / 'out' / 'surfacing'
VARIANTS = {'full': {}, 'no_far': dict(far_scale=1.0), 'offset': dict(detile='offset', far_detile=False, macro_mod=0.0),
            'single': dict(anti_tile=False, far_detile=False)}


def _no_canopy(pal):
    for L in pal['layers']:
        L.pop('canopy', None)


def _no_patches(pal):
    for L in pal['layers']:
        L.pop('patches', None)


def _no_fbm(pal):
    for L in pal['layers']:
        L['weight'] = str(L['weight']).replace('fbm(', 'noise(')


def _no_bump(pal):
    for L in pal['layers']:
        L['bump_m'] = 0.0
        L.pop('ripples', None)
        if L.get('canopy'):
            L['canopy'] = dict(L['canopy'], height_m=0.0)


def _bare(pal):
    _no_canopy(pal)
    _no_patches(pal)
    _no_fbm(pal)
    for L in pal['layers']:
        L.pop('streaks', None)
    pal['options'].update(tone=None, macro=[])


# palette edits (on the resolved palette dict) that isolate a feature's cost
EDITS = {'no_canopy': _no_canopy, 'no_patches': _no_patches, 'no_fbm': _no_fbm, 'no_bump': _no_bump, 'bare': _bare}


def argv():
    a = sys.argv[sys.argv.index('--') + 1:] if '--' in sys.argv else []

    def opt(k, d):
        return a[a.index(k) + 1] if k in a else d
    return dict(palettes=opt('--palettes', 'alpine,desert_sandstone').split(','),
                variants=opt('--variants', 'full,no_far,offset').split(','), reps=int(opt('--reps', '3')),
                tag=opt('--tag', 'b1'))


def ground():
    n, side = 512, 1600.0
    x = (np.arange(n) + 0.5) / n * side - side / 2
    X, Y = np.meshgrid(x, x)
    h = 40.0 * np.sin(X / 230.0) * np.cos(Y / 310.0) + 25.0 * np.sin((X + Y) / 120.0)
    h += 180.0 / (1.0 + np.exp(-(Y - 300.0) / 18.0)) + 120.0 / (1.0 + np.exp(-(X + 450.0) / 12.0))
    gy, gx = np.gradient(h, side / n)
    slope = np.degrees(np.arctan(np.hypot(gx, gy)))
    lap = np.gradient(gx, side / n, axis=1) + np.gradient(gy, side / n, axis=0)
    rng = np.random.default_rng(3)

    def smooth(k):
        f = np.fft.rfft2(rng.standard_normal((n, n)))
        fy, fx = np.fft.fftfreq(n)[:, None], np.fft.rfftfreq(n)[None, :]
        g = np.exp(-(fx * fx + fy * fy) * (k ** 2))
        a = np.fft.irfft2(f * g, s=(n, n))
        return (a - a.min()) / (np.ptp(a) + 1e-9)
    masks = dict(slope=slope, height=h - h.min(), convex_20m=np.clip(-lap * 40, 0, 1),
                 concave_20m=np.clip(lap * 40, 0, 1), curv_plan_20m=np.clip(-lap * 0.3, -0.02, 0.02),
                 curv_profile_20m=np.clip(-lap * 0.2, -0.02, 0.02), flow=smooth(30) * 0.9, wetness=smooth(25),
                 occlusion=0.6 + 0.4 * smooth(20), northness=np.clip(-gy * 3, -1, 1), deposit=smooth(15) * 0.8,
                 talus=smooth(18) * 1.2, sand=np.zeros((n, n)), snow=np.clip(smooth(12) - 0.6, 0, 1) * 2,
                 rock_toe=smooth(22) * 0.5, strata=h + 800.0, lava=np.zeros((n, n)), water=np.zeros((n, n)))
    verts = np.stack([X.ravel(), Y.ravel(), h.ravel()], 1).astype(np.float32)
    ii = np.arange(n - 1)
    I, J = np.meshgrid(ii, ii)
    a = (J * n + I).ravel()
    quads = np.stack([a, a + 1, a + n + 1, a + n], 1)
    me = bpy.data.meshes.new('bench')
    me.vertices.add(len(verts))
    me.vertices.foreach_set('co', verts.ravel())
    me.loops.add(len(quads) * 4)
    me.loops.foreach_set('vertex_index', quads.ravel().astype(np.int32))
    me.polygons.add(len(quads))
    me.polygons.foreach_set('loop_start', (np.arange(len(quads)) * 4).astype(np.int32))
    me.polygons.foreach_set('loop_total', np.full(len(quads), 4, np.int32))
    me.update()
    me.shade_smooth()
    for k, v in masks.items():
        att = me.attributes.new('eido_' + k, 'FLOAT', 'POINT')
        att.data.foreach_set('value', np.asarray(v, np.float32).ravel())
    ob = bpy.data.objects.new('bench', me)
    bpy.context.scene.collection.objects.link(ob)
    return ob


def scene():
    bpy.ops.wm.read_factory_settings(use_empty=True)
    bpy.context.preferences.system.anisotropic_filter = 'FILTER_16'
    sc = bpy.context.scene
    sc.render.engine = 'BLENDER_EEVEE'
    sc.eevee.taa_render_samples = 16
    sc.eevee.use_raytracing = True
    sc.eevee.use_shadows = True
    sc.render.resolution_x, sc.render.resolution_y, sc.render.resolution_percentage = 960, 540, 100
    sc.view_settings.view_transform = 'AgX'
    w = bpy.data.worlds.new('w')
    w.color = (0.35, 0.45, 0.6)
    sc.world = w
    sun = bpy.data.objects.new('sun', bpy.data.lights.new('sun', 'SUN'))
    sun.data.energy = 4.0
    sun.rotation_euler = (math.radians(50), 0, math.radians(30))
    sc.collection.objects.link(sun)
    cam = bpy.data.objects.new('cam', bpy.data.cameras.new('cam'))
    cam.data.lens = 35
    cam.data.clip_start, cam.data.clip_end = 0.5, 5000
    cam.location = (-700.0, -760.0, 160.0)
    cam.rotation_euler = (math.radians(78), 0, math.radians(-40))
    sc.collection.objects.link(cam)
    sc.camera = cam
    return sc


def frame():
    t = time.time()
    bpy.ops.render.render(write_still=False)
    return time.time() - t


def main():
    a = argv()
    sc = scene()
    ob = ground()
    clay = S.clay_material('bench_clay')
    out = {}
    for pal in a['palettes']:
        for var in a['variants']:
            # aniso2: the full material at 2x anisotropic filtering (the factory preference) instead of 16x
            bpy.context.preferences.system.anisotropic_filter = 'FILTER_2' if var == 'aniso2' else 'FILTER_16'
            p = S.resolve(pal, constants=dict(base_elevation_m=800.0), options=dict(VARIANTS.get(var, {})))
            if var in EDITS:
                EDITS[var](p)
            mat = S.surface_material(p, name=f'bench_{pal}_{var}', log=None)
            grp = next(n.node_tree for n in mat.node_tree.nodes if n.bl_idname == 'ShaderNodeGroup')
            ob.data.materials.clear()
            ob.data.materials.append(mat)
            S.pack_masks(ob, mat)                        # a palette past ATTRS_DIRECT masks reads them packed
            t_first = frame()
            tex, cl = [], []
            for _ in range(a['reps']):
                ob.data.materials[0] = mat
                tex.append(frame())
                ob.data.materials[0] = clay
                cl.append(frame())
            rec = dict(first_s=round(t_first, 2), textured_s=round(min(tex), 2), clay_s=round(min(cl), 2),
                       material_s=round(min(tex) - min(cl), 2), nodes=len(grp.nodes), images=grp['eido_images'])
            out[f'{pal}/{var}'] = rec
            print(f'[bench] {pal}/{var}: {rec}', flush=True)
    sc.render.filepath = str(OUT / f'bench_{a["tag"]}.png')
    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / f'bench_{a["tag"]}.json').write_text(json.dumps(out, indent=1))
    print('[bench] done', flush=True)


main()
