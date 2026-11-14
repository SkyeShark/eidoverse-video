"""eidoblend.fx.stable_fluids in Blender: fluid_sim.js's uses in the engine's scenes, rendered.

    cd <main checkout> && bash run_blender.sh <worktree>/blender/tests/water3d/test_stable_fluids.py phase=bake
    cd <main checkout> && bash run_blender.sh <worktree>/blender/tests/water3d/test_stable_fluids.py [-- parts=1,2,3]
    (the render: a GPU job, 3 GB VRAM, 8 GB RAM cap; on a shared machine queue it with EIDO_GPU_WRAP,
    blender/tests/_where.py)

The bake (the numpy solver, several minutes of CPU) runs without the GPU; the render phase (the default once a bake is
on disk: out/fluid2d_cache/sf_bakes.json) reattaches it with load_bake.

1. The engine's panels (out/sf_panels_f####.png, out/sf_showcase_f0075.png): five scenes' createFluidSim setups, each
   baked with its own per-frame splats (30 fps) and shown as densityNode on an unlit panel, Standard view (the
   engine's canvas: sRGB out, no tone mapping):
     showcase  work/_showcase/fluid: balanced, curl 4, densityDissipation 0.985, splatRadius 0.004; two opposed splats
               and a wandering one, 2.5 s. Its preview.jpg is the reference for sf_showcase_f0075.png (its camera)
     neon      agentic_burning: balanced, curl 7, three coloured splats a frame (its 'dissipation' option is not one
               fluid_sim.js forwards, so the engine ignored it; it is left out here)
     unit      unit_test 16e: balanced, curl 4, one magenta splat on a wandering path
     expo      the helper expo's ink panel: performance, curl 32, near-zero dx, cycling colour
     dish      neuro_dish's options: quality, curl 2.4, dissipation density/velocity/dye 0.976/0.978/0.982, splatRadius
               0.0075, splatForce 2.1; shown at 0.62 (its colorNode multiplier); 1 s (the quality grids are 1024 dye)
2. The effects grid (out/sf_effects_f0060.png): the package's cursor use, attachPointerSplats on a path with coloured
   strokes; every overlay style, densityTint and every distortion as panel materials over the sky image:
       default volumeCursor trail oil velocity / colorful rainbowFish glaze burn smoke /
       artInk rainbowInk colorWater liquidLens densityTint / simple chromatic rgbShift water waterCaustics
3. Post-processing (out/sf_post_*.png): the oil overlay and the waterCaustics distortion as compositor graphs over a
   rendered 3D frame (the engine's PostProcessing outputNode use).

Checks: every bake writes its frames; vorticity curls the neon field; the showcase panel's left blob is wider than
tall (round in the square sim stretched over 16:9, as the engine's) and its red dominates the left third; the quality
profile runs its 384/1024 grids; pointer strokes lay dye that travels; each effect panel differs from the plain sky
where the fluid is; both compositor renders differ from the plain render and are not black.
"""

import math
import os
import sys
import time

import bpy
import numpy as np

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import _scene as S  # noqa: E402
from eidoblend.fx.stable_fluids import create_fluid_sim, OVERLAY_STYLES, DISTORTIONS, _plane  # noqa: E402

A = S.args()
PARTS = set(A.get('parts', '1,2,3').split(','))
FPS = 30
CACHE = os.path.join(S.OUT, 'fluid2d_cache')
# phase=bake runs the numpy solvers only (CPU: not a GPU job), phase=render reattaches those bakes
# (load_bake) and renders; the default renders when a bake is on disk, else does both
MANIFEST = os.path.join(CACHE, 'sf_bakes.json')
PHASE = A.get('phase', 'render' if os.path.exists(MANIFEST) else 'all')
BAKE, RENDER = PHASE in ('bake', 'all'), PHASE in ('render', 'all')
sc = S.fresh_scene(res=(1600, 900), fps=FPS, end=75, samples=1)
sc.view_settings.view_transform = 'Standard'          # the panels are unlit displays, as MeshBasic on a canvas
ok = True
t0 = time.time()


def ortho(scale):
    camd = bpy.data.cameras.new('ortho')
    camd.type = 'ORTHO'
    camd.ortho_scale = scale
    cam = bpy.data.objects.new('ortho', camd)
    sc.collection.objects.link(cam)
    cam.location = (0, -10, 0)
    cam.rotation_euler = (math.radians(90), 0, 0)
    sc.camera = cam
    return cam


def black_world():
    w_ = bpy.data.worlds.new('black')
    w_.use_nodes = True
    w_.node_tree.nodes['Background'].inputs['Color'].default_value = (0, 0, 0, 1)
    sc.world = w_


def clear_objects():
    for ob in list(bpy.data.objects):
        bpy.data.objects.remove(ob, do_unlink=True)


black_world()

# ---- 1. the engine's panels ---------------------------------------------------------------------------------
if '1' in PARTS:
    END = 75
    sims = {}

    def showcase(frame, t, F):
        F.splat(0.30, 0.5, 60, 20, [0.9, 0.2, 0.3])
        F.splat(0.70, 0.5, -60, -20, [0.2, 0.5, 1.0])
        rx, ry = 0.5 + math.sin(t * 1.3) * 0.3, 0.5 + math.cos(t * 1.9) * 0.3
        F.splat(rx, ry, math.cos(t * 3) * 50, math.sin(t * 3) * 50,
                [math.sin(t) * 0.5 + 0.5, 0.8, math.cos(t * 1.4) * 0.5 + 0.5])

    def neon(frame, t, F):
        at = t * 1.6
        x1, y1 = 0.3 + 0.18 * math.sin(at * 0.9), 0.5 + 0.3 * math.sin(at * 1.3)
        F.splat(x1, y1, math.cos(at * 1.7) * 1.4, math.sin(at * 1.3) * 1.1, [1.0, 0.08, 0.68])
        F.splat(1 - x1, 1 - y1, -math.sin(at * 1.5) * 1.2, math.cos(at * 1.1) * 1.0, [1.0, 0.42, 0.04])
        F.splat(0.5 + math.sin(at * 1.8) * 0.08, 0.5, 0.0, 1.2, [0.05, 0.85, 1.0])

    def unit(frame, t, F):
        F.splat(0.5 + math.sin(t * 1.3) * 0.25, 0.5 + math.cos(t * 1.7) * 0.25, math.cos(t * 2) * 3,
                math.sin(t * 2) * 3, [0.9, 0.3, 0.7])

    def expo(frame, t, F):
        a = t * 1.1
        F.splat(0.5 + 0.34 * math.cos(a), 0.5 + 0.3 * math.sin(a * 1.4), -math.sin(a) * 0.002,
                math.cos(a * 1.4) * 0.002, [abs(math.sin(t * 0.6)), abs(math.sin(t * 0.4 + 2)),
                                           abs(math.sin(t * 0.8 + 4))])

    def dish(frame, t, F):
        # neuro_dish's strokes, simplified: neurons firing along curved paths toward the centre
        for k in range(3):
            a = t * 1.2 + k * 2.09
            ux, uy = 0.5 + 0.32 * math.cos(a), 0.5 + 0.32 * math.sin(a)
            F.splat(ux, uy, (0.5 - ux) * 14 - math.sin(a) * 6, (0.5 - uy) * 14 + math.cos(a) * 6,
                    [(0.3, 0.9, 1.0), (1.0, 0.35, 0.8), (0.9, 0.85, 0.3)][k])

    setups = [
        ('showcase', dict(profile='balanced', curl_strength=4, density_dissipation=0.985, splat_radius=0.004),
         showcase, (3.2, 1.8), END, 1.0),
        ('neon', dict(profile='balanced', curl_strength=7.0), neon, (3.2, 1.8), END, 1.0),
        ('unit', dict(profile='balanced', curl_strength=4), unit, (1.8, 1.8), END, 1.0),
        ('expo', dict(profile='performance', curl_strength=32), expo, (3.2, 1.8), END, 1.0),
        ('dish', dict(profile='quality', curl_strength=2.4, density_dissipation=0.976, velocity_dissipation=0.978,
                      dye_dissipation=0.982, splat_radius=0.0075, splat_force=2.1), dish, (1.8, 1.8), 30, 0.62),
    ]
    for name, opts, ctl, size, end, gain in setups:
        F = create_fluid_sim(name=name, **opts)
        if BAKE:
            tb = time.time()
            F.bake(1, end, controls=ctl, cache_dir=CACHE, scene=sc, log=lambda *a: None)
            missing = [f for f in range(1, end + 1)
                       if not os.path.exists(os.path.join(CACHE, f'{name}_density_{f:04d}.exr'))]
            ok &= S.check(f'{name}: the bake wrote every frame', not missing, f'{end} frames in '
                          f'{time.time() - tb:.0f} s, sim {F.raw.sim_width}x{F.raw.sim_height}, '
                          f'dye {F.raw.dye_width}x{F.raw.dye_height}')
            if name == 'neon':
                curl = float(np.abs(F.raw.curl[..., 0]).max())
                ok &= S.check('vorticity curls the neon field (curl non-zero)', curl > 1e-3, f'max |curl| {curl:.3f}')
            if name == 'dish':
                ok &= S.check('the quality profile runs its 384 / 1024 grids',
                              (F.raw.sim_width, F.raw.dye_width) == (384, 1024))
        else:
            F.load_bake(CACHE, 1, end, scene=sc)
        sims[name] = (F, size, gain)
if '1' in PARTS and RENDER:
    # the showcase on its own, the engine's camera: PerspectiveCamera(50, 16:9) at z 2.2 looking at the panel
    sc.render.resolution_x, sc.render.resolution_y = 960, 540
    panel = sims['showcase'][0].panel(size=(3.2, 1.8), location=(0, 0, 0))
    cd = bpy.data.cameras.new('cam')
    cd.sensor_fit = 'VERTICAL'
    cd.angle = math.radians(50)
    cam = bpy.data.objects.new('cam', cd)
    sc.collection.objects.link(cam)
    cam.location = (0, -2.2, 0)
    cam.rotation_euler = (math.radians(90), 0, 0)
    sc.camera = cam
    p_sc = os.path.join(S.OUT, 'sf_showcase_f0075.png')
    ok &= S.render(sc, 75, p_sc)
    im = S.read_png(p_sc).astype(np.float32)
    H_, W_ = im.shape[:2]
    # the left blob (the red splat at uv 0.30): its saturated core, inside a box round it that the yellow trail
    # (which starts past 0.42 of the width) never enters
    left = im[int(0.3 * H_):int(0.7 * H_), int(0.15 * W_):int(0.42 * W_)]
    lum = left.sum(axis=2)
    ys, xs = np.nonzero(lum > 0.85 * lum.max())
    wide = (np.ptp(xs) + 1) / max(np.ptp(ys) + 1, 1)
    ok &= S.check('showcase: the left blob is wider than tall (a round splat in the square sim, stretched over 16:9 '
                  'as in the engine) with a red rim', wide > 1.3 and left[..., 0].mean() > left[..., 2].mean(),
                  f'core {np.ptp(xs) + 1} x {np.ptp(ys) + 1} px, box rgb {left.mean(axis=(0, 1)).round(1)}')
    # the engine's own field (engine_run_stable_fluids.mjs case=showcase): its preview.jpg went through the engine's
    # render pipeline's post (a wide glow), so the density itself is the reference
    ref_p = os.path.join(S.OUT, 'engine_fluid2d_showcase_density.f32')
    if os.path.exists(ref_p):
        from eidoblend.fx._util import read_exr
        eng = np.fromfile(ref_p, dtype='<f4').reshape(512, 512, 4)
        mine = read_exr(os.path.join(CACHE, 'showcase_density_0075.exr'))[::-1]       # row 0 = top, as the WGSL
        rel = float(np.sqrt(np.mean((mine[..., :3] - eng[..., :3]) ** 2)) / np.sqrt(np.mean(eng[..., :3] ** 2)))
        ok &= S.check('showcase: the baked density matches the package run on WebGPU (relative RMS < 5 %)',
                      rel < 0.05, f'{rel * 100:.2f} %')
    bpy.data.objects.remove(panel, do_unlink=True)
    bpy.data.objects.remove(cam, do_unlink=True)
    # all five panels side by side
    sc.render.resolution_x, sc.render.resolution_y = 1600, 900
    ortho(11.2)
    lay = [('showcase', (-3.6, 1.7)), ('neon', (0.0, 1.7)), ('expo', (3.6, 1.7)), ('unit', (-1.8, -0.6)),
           ('dish', (1.8, -0.6))]
    for name, (x, z) in lay:
        F, size, gain = sims[name]
        F.panel(size=size, location=(x, 0, z), strength=gain)
    shots = []
    for f in (30, 75):
        p = os.path.join(S.OUT, f'sf_panels_f{f:04d}.png')
        ok &= S.render(sc, f, p)
        shots.append(p)
    pimg = S.read_png(shots[-1]).astype(np.float32)
    ok &= S.check('the panels show ink (not flat)', float(pimg.std()) > 10.0, f'std {pimg.std():.1f}')
    clear_objects()
    black_world()

# ---- 2. the effects: the package's cursor use ----------------------------------------------------------------
if '2' in PARTS:
    END2 = 60
    # a larger splat and slower decay than the package's defaults, so every effect has ink to work on across the
    # panel (the package's 0.91 a frame keeps a short comet behind a cursor)
    cursor = create_fluid_sim(profile='balanced', curl_strength=0.55, name='cursor', splat_radius=0.0016,
                              density_dissipation=0.99, dye_dissipation=0.99)
    cursor.resize(1600, 900)
    path = lambda t: (0.5 + 0.38 * math.sin(1.1 * t + 0.3), 0.5 + 0.34 * math.sin(1.7 * t + 0.9))   # noqa: E731
    cursor.attach(path, size=(1600, 900), colored_strokes=True)
    cent = []

    def cursor_controls(frame, t, fluid):
        if frame % 15 == 0:
            d = np.linalg.norm(fluid.dye[..., :3], axis=-1)
            h, w = d.shape
            ys, xs = np.mgrid[0:h, 0:w]
            m = d.sum()
            cent.append((xs * d).sum() / max(m, 1e-9) / w if m > 0 else None)

    if BAKE:
        cursor.bake(1, END2, controls=cursor_controls, cache_dir=CACHE, scene=sc, log=lambda *a: None)
        moved = [c for c in cent if c is not None]
        ok &= S.check('pointer strokes lay dye that travels', len(moved) >= 2 and np.ptp(moved) > 0.02,
                      f'dye centroid x {[round(float(c), 3) for c in moved]}')
    else:
        cursor.load_bake(CACHE, 1, END2, scene=sc)
if '2' in PARTS and RENDER:
    scene_img = bpy.data.images.load(os.path.join(S.HERE, '..', '..', '..', 'eidoverse', 'assets', 'sky',
                                                  'kloppenheim_puresky_ldr.png'), check_existing=True)
    # the distortions move a scene texture's lookup by a few pixels (simple: density.rg * 3e-4 of the frame), which a
    # smooth sky hides: they warp the paving stones' edges instead
    edge_img = bpy.data.images.load(os.path.join(S.texset('PavingStones128_1k'), 'PavingStones128_Color.jpg'),
                                    check_existing=True)
    effects = [('overlay', s) for s in OVERLAY_STYLES] + [('overlay', 'densityTint')] + \
        [('distortion', d) for d in DISTORTIONS]
    cols, pw, ph, gap = 5, 3.2, 1.8, 0.12
    for i, (kind, nm) in enumerate(effects):
        if kind == 'overlay':
            mat = cursor.overlay_node(scene_img, style=nm)
        else:
            mat = cursor.distortion(edge_img, 1.0, kind=nm)
        r, c = divmod(i, cols)
        _plane(sc, f'fx_{nm}', (pw, ph), ((c - (cols - 1) / 2) * (pw + gap), 0.0,
                                          ((len(effects) // cols - 1) / 2 - r) * (ph + gap)),
               (math.radians(90), 0, 0), mat)
    ortho(cols * (pw + gap))
    p_fx = os.path.join(S.OUT, f'sf_effects_f{END2:04d}.png')
    ok &= S.render(sc, END2, p_fx)
    img = S.read_png(p_fx).astype(np.float32)
    H, Wd = img.shape[:2]
    plain_mat = cursor.material(lambda g: g.tap('scene', *g.uv), 'plain_scene', scene_src=scene_img)
    plain_edges = cursor.material(lambda g: g.tap('scene', *g.uv), 'plain_edges', scene_src=edge_img)
    for ob in [o for o in sc.objects if o.name.startswith('fx_')]:
        ob.data.materials[0] = plain_edges if ob.name[3:] in DISTORTIONS else plain_mat
    p_plain = os.path.join(S.OUT, 'sf_effects_plain.png')
    S.render(sc, END2, p_plain)
    plain = S.read_png(p_plain).astype(np.float32)
    diffs = []
    rows = (len(effects) + cols - 1) // cols
    for i, (kind, nm) in enumerate(effects):
        r, c = divmod(i, cols)
        y0, y1 = int(r * H / rows) + 8, int((r + 1) * H / rows) - 8
        x0, x1 = int(c * Wd / cols) + 8, int((c + 1) * Wd / cols) - 8
        d = np.abs(img[y0:y1, x0:x1] - plain[y0:y1, x0:x1]).max(axis=2)
        # the effects act along the stroke only: the share of the panel visibly changed (more than 8 of 255)
        diffs.append((nm, float((d > 8).mean()) * 100))
    flat = [nm for nm, d in diffs if d < 0.75]
    ok &= S.check('every effect visibly changes its panel along the stroke (> 0.75 % of it by more than 8/255)',
                  not flat, ', '.join(f'{nm} {d:.1f} %' for nm, d in diffs) if not flat else f'unchanged: {flat}')
    clear_objects()

# ---- 3. post-processing over a render (compositor) ---------------------------------------------------------
if '3' in PARTS and RENDER:
    if '2' not in PARTS:
        raise SystemExit('part 3 composites the cursor fluid of part 2: run parts 2 and 3 together')
    sc.view_settings.view_transform = 'AgX'
    sc.eevee.taa_render_samples = 16
    sc.render.resolution_x, sc.render.resolution_y = 960, 540
    S.box(sc, 'floor', (12, 12, 0.1), (0, 0, -0.05), S.principled('floor_m', 0x8a7f72, rough=0.6))
    import bmesh  # noqa: E402
    me = bpy.data.meshes.new('ball')
    bm = bmesh.new()
    bmesh.ops.create_uvsphere(bm, u_segments=48, v_segments=24, radius=0.8)
    bm.to_mesh(me)
    bm.free()
    for poly in me.polygons:
        poly.use_smooth = True
    ball = bpy.data.objects.new('ball', me)
    sc.collection.objects.link(ball)
    ball.location = (0, 0, 0.8)
    me.materials.append(S.principled('ball_m', 0x3a6fd0, rough=0.25))
    S.sun(sc, 'sun', 40, 45, 3.0)
    S.world_backdrop(sc, None, 0x7f93ad, 0.8)
    S.camera_look(sc, (0.0, -5.5, 2.2), (0, 0, 0.7), lens=40)
    sc.render.use_compositing = False
    p_raw = os.path.join(S.OUT, 'sf_post_plain.png')
    S.render(sc, 60, p_raw)
    raw = S.read_png(p_raw).astype(np.float32)
    for tag, build in (('oil', lambda: cursor.overlay_node('render', style='oil', target='compositor', intensity=1.2)),
                       ('caustics', lambda: cursor.distortion('render', 1.0, kind='waterCaustics',
                                                             target='compositor'))):
        build()
        p = os.path.join(S.OUT, f'sf_post_{tag}.png')
        ok &= S.render(sc, 60, p)
        im = S.read_png(p).astype(np.float32)
        d = float(np.abs(im - raw).mean())
        ok &= S.check(f'the {tag} effect composites over the render (changed, not black)',
                      0.3 < d and im.mean() > 0.5 * raw.mean(), f'mean |diff| {d:.2f}, mean {im.mean():.1f} vs '
                      f'{raw.mean():.1f}')
if BAKE and ok:
    import json
    with open(MANIFEST, 'w') as fh:
        json.dump({'parts': sorted(PARTS), 'baked': time.strftime('%Y-%m-%d %H:%M')}, fh)
if RENDER:
    bpy.ops.wm.save_as_mainfile(filepath=os.path.join(S.OUT, 'sf_stable_fluids.blend'))
print('ALL PASS' if ok else 'SOME FAIL', f'({PHASE}, {time.time() - t0:.1f} s)')
