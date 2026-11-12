"""The SDF volumes inside a real scene: what the per-example probes do not cover.

    cd <main checkout> && HEAVY_VRAM_GB=4 bash work/claude_body/work/tmp/heavy.sh 12 bash run_blender.sh \
        <worktree>/blender/tests/sdf_volumes/test_volume_scene_integration.py \
        [-- cases=fog,cuts,inside,rotated,nuke_placed,fire_lamps,registry,probe_reflect]

Cases (renders in out/verify/, 480 x 270, 16 samples):
  fog          a fog box filling the stage and a bonfire: fit_volume_range must not drop the fog the fire's froxel
               range leaves out (EEVEE's one volume range clips every volume, not just the ones fitted); with a world
               volume the range keeps the camera's whole clip range
  cuts         two cameras switched by timeline markers (near, far): fit_volume_range keeps the fire inside the range
               of both cuts, so it renders in each
  inside       the camera inside the smoke column, looking up it: the medium renders round it
  rotated      a bonfire placed, turned and scaled 1.5: its lamps sit inside the fire in world space, with world power
  nuke_placed  nuclear_explosion at origin (15, 0, -30) (three), scale 0.6: the volumes and lamps land at (15, 30, 0)
  fire_lamps   the roaring `fire` on a floor: its keyed lamps light the floor, its volume alone does not
  registry     the post registry hook (custom_effects.register 'nuclear_explosion' as native), its options, uniforms,
               keys (the glow lamps fade with a key set through the registry) and undo, as the hooks_needed entry asks
  probe_reflect  (not in the default run) a chrome ball beside a bonfire, with and without a sphere light probe
               round it: whether a probe carries a volume into EEVEE's reflections (measured: it does not)
"""

import math
import os
import sys

import numpy as np

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import _vcommon as V  # noqa: E402

import bpy  # noqa: E402
from mathutils import Vector  # noqa: E402

from eidoblend.sdf import EXAMPLES  # noqa: E402
from eidoblend.sdf import nuclear_explosion as NX  # noqa: E402
from eidoblend.sdf.examples_volumes import fit_volume_range, light_from_emission, build_still  # noqa: E402

A = V.args()
CASES = A.get('cases', 'fog,cuts,inside,rotated,nuke_placed,fire_lamps,registry').split(',')
W, H = int(A.get('w', 480)), int(A.get('h', 270))
OUT = os.path.join(V.OUT, 'verify')
os.makedirs(OUT, exist_ok=True)
CACHE = os.path.join(OUT, 'cache_integration')


def lum(img):
    return img[..., :3] @ np.array([0.2126, 0.7152, 0.0722])


def shot(name, text):
    p = os.path.join(OUT, f'integ_{name}.png')
    ok = V.render(p)
    if ok:
        V.label(p, text)
    return p if ok else None


def fog_box(size=(80.0, 80.0, 14.0), density=0.035, colour=(0.85, 0.88, 0.92)):
    me = bpy.data.meshes.new('fog_box')
    hx, hy, hz = (s * 0.5 for s in size)
    v = [(sx * hx, sy * hy, sz * size[2]) for sx in (-1, 1) for sy in (-1, 1) for sz in (0, 1)]
    me.from_pydata(v, [], [(0, 1, 3, 2), (4, 6, 7, 5), (0, 4, 5, 1), (2, 3, 7, 6), (0, 2, 6, 4), (1, 5, 7, 3)])
    ob = bpy.data.objects.new('fog_box', me)
    bpy.context.scene.collection.objects.link(ob)
    m = bpy.data.materials.new('fog_mat')
    m.use_nodes = True
    nt = m.node_tree
    for n in list(nt.nodes):
        if n.type != 'OUTPUT_MATERIAL':
            nt.nodes.remove(n)
    pv = nt.nodes.new('ShaderNodeVolumePrincipled')
    pv.inputs['Density'].default_value = density
    pv.inputs['Color'].default_value = (*colour, 1.0)
    nt.links.new(pv.outputs[0], next(n for n in nt.nodes if n.type == 'OUTPUT_MATERIAL').inputs['Volume'])
    me.materials.append(m)
    return ob


# ---- fog: the fitted range must not clip the scene's other volumes ------------------------------------------------
if 'fog' in CASES:
    V.stage(W, H, 16, world=0.05, sun=0.6, floor=True, floor_size=200.0, sun_rot=(70.0, 0.0, 20.0))
    sc = bpy.context.scene
    cam = V.camera((0.0, -9.0, 1.7), (0.0, 0.0, 1.2), lens=35)
    fog = fog_box()
    ee = sc.eevee
    ee.use_volume_custom_range = True
    ee.volumetric_start, ee.volumetric_end = 0.1, 120.0
    ee.volumetric_tile_size = '4'
    p_fog = shot('fog_only', 'fog box alone, range 0.1..120 m')
    fire = EXAMPLES['bonfire'].make(cells=120, cache_dir=CACHE, name='fog_bonfire', build=False)
    build_still(fire, 1.3)
    rng = fit_volume_range(sc, cam, [fire], frames=[1])
    print(f'[integ] fog: fitted range {rng}', flush=True)
    p_fit = shot('fog_fire_fitted', f'fog + bonfire, fit_volume_range -> {rng[0]:.1f}..{rng[1]:.1f} m')
    a, b = V.read_png(p_fog), V.read_png(p_fit)
    # the fog's veil over the far floor and the horizon: the image's top third, away from the fire
    band = (slice(30, H // 3), slice(0, W // 3))
    la, lb = float(lum(a[band]).mean()), float(lum(b[band]).mean())
    V.check('fog: fit_volume_range keeps the fog the fire\'s range would clip', abs(lb - la) < 0.15 * la,
            f'mean luminance over the far fog: fog alone {la:.4f}, with the fitted fire {lb:.4f} (range {rng})')
    V.sheet([p_fog, p_fit], os.path.join(OUT, 'integ_fog_sheet.png'), cols=2)
    # a world volume fills the view: the fitted range must keep the camera's whole clip range
    w = sc.world
    wout = next(n for n in w.node_tree.nodes if n.type == 'OUTPUT_WORLD')
    wv = w.node_tree.nodes.new('ShaderNodeVolumePrincipled')
    wv.inputs['Density'].default_value = 0.002
    w.node_tree.links.new(wv.outputs[0], wout.inputs['Volume'])
    ee.use_volume_custom_range = False
    rng_w = fit_volume_range(sc, cam, [fire], frames=[1])
    V.check('fog: with a world volume the range keeps the camera clip range', rng_w[0] <= cam.data.clip_start + 1e-6
            and rng_w[1] >= cam.data.clip_end - 1e-3, f'range {rng_w}, camera clip {cam.data.clip_start} .. '
            f'{cam.data.clip_end}')
    w.node_tree.nodes.remove(wv)

# ---- cuts: two cameras switched by markers ------------------------------------------------------------------------
if 'cuts' in CASES:
    V.stage(W, H, 16, world=0.03, sun=0.15, floor=True, floor_size=400.0)
    sc = bpy.context.scene
    near = V.camera((0.0, -5.5, 1.6), (0.0, 0.0, 1.1), lens=35, name='cam_near')
    far = V.camera((25.0, -60.0, 6.0), (0.0, 0.0, 1.0), lens=135, name='cam_far')
    sc.camera = near
    sc.frame_start, sc.frame_end = 1, 2
    for f, c in ((1, near), (2, far)):
        mk = sc.timeline_markers.new(f'cut{f}', frame=f)
        mk.camera = c
    fire = EXAMPLES['bonfire'].make(cells=120, cache_dir=CACHE, name='cuts_bonfire', build=False)
    fire.bake(1, 2, time_offset=1.0, log=None)
    rng = fit_volume_range(sc, None, [fire], frames=[1, 2])
    print(f'[integ] cuts: fitted range {rng}', flush=True)
    base = []
    for f in (1, 2):
        sc.frame_set(f)
        fire.object.hide_render = True
        pb = shot(f'cuts_empty_f{f}', f'frame {f}: empty')
        fire.object.hide_render = False
        pf = shot(f'cuts_f{f}', f'frame {f}: {sc.camera.name}, range {rng[0]:.1f}..{rng[1]:.1f} m')
        d = np.abs(lum(V.read_png(pf)) - lum(V.read_png(pb)))
        d[:30] = 0
        V.check(f'cuts: the fire renders through the {sc.camera.name} cut (frame {f})', float((d > 0.05).mean()) > 0.002,
                f'{(d > 0.05).mean() * 100:.2f}% of the frame changed')
        base.append(pf)
    V.sheet(base, os.path.join(OUT, 'integ_cuts_sheet.png'), cols=2)

# ---- inside: the camera in the smoke -------------------------------------------------------------------------------
if 'inside' in CASES:
    V.stage(W, H, 16, world=0.15, sun=1.5, floor=True, floor_size=60.0)
    sc = bpy.context.scene
    # on the column's axis, looking up it: two metres of the plume's core in front of the lens
    cam = V.camera((0.0, 0.0, 0.45), (0.0, 0.35, 2.6), lens=24)
    smoke = EXAMPLES['smoke'].make(cells=140, cache_dir=CACHE, name='inside_smoke', build=False)
    build_still(smoke, 3.0)
    rng = fit_volume_range(sc, cam, [smoke], frames=[1])
    smoke.object.hide_render = True
    pe = shot('inside_empty', 'camera in the smoke column, looking up it: empty')
    smoke.object.hide_render = False
    pi = shot('inside', f'camera inside the smoke, looking up, range {rng[0]:.2f}..{rng[1]:.2f} m')
    img = V.read_png(pi)
    d = np.abs(lum(img) - lum(V.read_png(pe)))
    d[:30] = 0
    V.check('inside: the medium renders round a camera inside it', np.isfinite(img).all() and rng[0] <= 0.02
            and float((d > 0.02).mean()) > 0.2, f'{(d > 0.02).mean() * 100:.1f}% of the frame veiled by the smoke; '
            f'range starts at {rng[0]:.3f} m (the camera is inside the box)')
    V.sheet([pe, pi], os.path.join(OUT, 'integ_inside_sheet.png'), cols=2)

# ---- rotated: lamps of a placed, turned, scaled fire --------------------------------------------------------------
if 'rotated' in CASES:
    V.stage(W, H, 16, world=0.004, sun=0.0, floor=True, floor_size=40.0)
    sc = bpy.context.scene
    cam = V.camera((2.0, -8.0, 2.6), (2.0, 1.0, 1.2), lens=35)
    fire = EXAMPLES['bonfire'].make(cells=110, cache_dir=CACHE, name='rot_bonfire', build=False,
                                    location=(2.0, 1.0, 0.0), rotation=(0.0, 0.0, math.radians(30.0)), scale=1.5)
    build_still(fire, 1.3)
    fit_volume_range(sc, cam, [fire], frames=[1])
    rig = light_from_emission(fire, log=None)
    dg = bpy.context.evaluated_depsgraph_get()
    M = fire.object.matrix_world
    lo_w = M @ Vector(fire.lo)
    hi_w = M @ Vector(fire.hi)
    ok = True
    info = []
    for lo in rig.lights:
        p = lo.evaluated_get(dg).matrix_world.translation
        loc = M.inverted() @ p
        inside = all(fire.lo[i] - 1e-6 <= loc[i] <= fire.hi[i] + 1e-6 for i in range(3))
        ok &= inside
        info.append(f'{lo.name} world {tuple(round(x, 2) for x in p)} local {tuple(round(x, 2) for x in loc)} '
                    f'{lo.data.energy:.2f} W r {lo.data.shadow_soft_size:.3f}')
    V.check('rotated: the lamps sit inside the placed fire', ok, '; '.join(info))
    # the same fire unscaled: power scales with volume (x 1.5^3 at the same emission per metre)
    plain = EXAMPLES['bonfire'].make(cells=110, cache_dir=CACHE, name='rot_bonfire_plain', build=False)
    build_still(plain, 1.3)
    rig0 = light_from_emission(plain, log=None)
    for ob in [plain.object] + list(rig0.lights):
        ob.hide_render = True
    r = rig.total_power(None) / max(1e-9, rig0.total_power(None))
    # x 1.5^3 for a thin medium (emission per metre over 3.4 x the volume), x 1.5^2 for an opaque one (its skin):
    # the flames are thick, so their escaping light grows nearly as the area
    V.check('rotated: lamp power follows the object scale (between x 1.5^2 and x 1.5^3)', 2.0 < r < 3.5,
            f'{rig.total_power(None):.2f} W vs {rig0.total_power(None):.2f} W unscaled: x {r:.2f}')
    # a second call replaces the lamps instead of stacking a second rig (which would double the light)
    n0 = len([o for o in bpy.data.objects if o.type == 'LIGHT' and o.parent == fire.object])
    rig = light_from_emission(fire, log=None)
    n1 = len([o for o in bpy.data.objects if o.type == 'LIGHT' and o.parent == fire.object])
    V.check('rotated: a second light_from_emission replaces the lamps', n1 == n0 == len(rig.lights),
            f'{n0} lamps, then {n1} after the second call')
    shot('rotated', 'bonfire at (2, 1, 0), turned 30 deg, scale 1.5, with its lamps')

# ---- nuke_placed: origin and scale ---------------------------------------------------------------------------------
if 'nuke_placed' in CASES:
    V.stage(W, H, 16, world=0.035, sun=0.25, floor=True, floor_size=600.0, sun_rot=(70.0, 0.0, -40.0))
    sc = bpy.context.scene
    cam = V.camera((15.0 + 10.0, 30.0 - 38.0, 4.0), (15.0, 30.0, 4.0), lens=28)
    cam.data.clip_end = 1000.0
    fx = NX.apply_to(sc, cam, {'origin': [15, 0, -30], 'scale': 0.6, 'timeOffset': 1.0}, cache_dir=CACHE,
                     quality='fast', name='nuke_placed')
    fx.update(5.5, log=None)
    locs = [tuple(round(x, 3) for x in v.object.location) for v in fx.volumes]
    V.check('nuke_placed: the volumes sit at three (15, 0, -30) -> Blender (15, 30, 0)',
            all(np.allclose(l, (15.0, 30.0, 0.0)) for l in locs), str(locs))
    dg = bpy.context.evaluated_depsgraph_get()
    lamp_pos = [lo.evaluated_get(dg).matrix_world.translation for rig in fx.lights for lo in rig.lights]
    dist = [((p - Vector((15.0, 30.0, 0.0))).xy.length, p.z) for p in lamp_pos]
    V.check('nuke_placed: the glow lamps are in the cloud round ground zero',
            all(r < 21.0 * 0.6 and -0.01 < z < 13.3 * 0.6 for r, z in dist), str([tuple(round(x, 2) for x in d)
                                                                                  for d in dist]))
    V.check('nuke_placed: uniforms read back', fx.uniforms['scale'] == 0.6 and fx.uniforms['time_offset'] == 1.0
            and fx.uniforms['origin'] == (15.0, 0.0, -30.0), repr(fx.uniforms))
    shot('nuke_placed', 'nuclear_explosion origin (15, 0, -30) scale 0.6, t = 5.5 s (+1 s offset)')

# ---- fire_lamps: the big fire's lamps light the floor; its volume alone does not ------------------------------------
if 'fire_lamps' in CASES:
    V.stage(W, H, 16, world=0.004, sun=0.0, floor=True, floor_color=(0.5, 0.5, 0.5), floor_size=60.0)
    sc = bpy.context.scene
    sc.frame_start = sc.frame_end = 1
    floor = bpy.data.objects['floor']
    floor.data.materials[0].node_tree.nodes['Principled BSDF'].inputs['Roughness'].default_value = 0.9
    cam = V.camera((0.0, -13.0, 3.5), (0.0, 0.0, 1.8), lens=35)
    fire = EXAMPLES['fire'].make(cells=140, cache_dir=CACHE, time=1.2, name='fire_lit_probe')
    fit_volume_range(sc, cam, [fire], frames=[1], tile_size='2', samples=96)
    rig = light_from_emission(fire, log=None)
    imgs = {}
    for tag, vis, lights in (('base', False, False), ('volume', True, False), ('lamps', True, True)):
        fire.object.hide_render = not vis
        for lo in rig.lights:
            lo.hide_render = not lights
        exr = os.path.join(OUT, f'integ_fire_{tag}.exr')
        imgs[tag] = V.render_linear(exr)
        V.label(V.save_linear_png(os.path.join(OUT, f'integ_fire_{tag}.png'), imgs[tag][::-1]), f'fire: {tag}')
    from bpy_extras.object_utils import world_to_camera_view
    rows = []
    for p in [(-2.6, -1.0, 0.0), (2.6, -1.0, 0.0), (-1.6, -2.6, 0.0), (1.8, -2.4, 0.0), (-4.0, 1.0, 0.0),
              (4.0, 1.5, 0.0), (0.0, -4.0, 0.0)]:
        co = world_to_camera_view(sc, cam, Vector(p))
        x, y = int(co.x * W), int((1.0 - co.y) * H)
        win = {t: float(lum(imgs[t][max(0, y - 3):y + 4, max(0, x - 3):x + 4, :3]).mean()) for t in imgs}
        rows.append(win)
    g_l = np.mean([r['lamps'] - r['base'] for r in rows])
    g_v = np.mean([r['volume'] - r['base'] for r in rows])
    print(f'[integ] fire: floor gain lamps {g_l:.4f}, the volume alone {g_v:.4f}; lamps {len(rig.lights)}, '
          f'{rig.total_power(None):.3g} W', flush=True)
    V.check('fire_lamps: the fire\'s lamps light the floor, its volume alone does not', g_l > 1e-3 and g_v < 0.1 * g_l,
            f'floor gain {g_l:.4f} with the lamps, {g_v:.4f} from the volume')
    V.sheet([os.path.join(OUT, f'integ_fire_{t}.png') for t in ('base', 'volume', 'lamps')],
            os.path.join(OUT, 'integ_fire_sheet.png'), cols=3)

# ---- registry: the hook as hooks_needed asks for it ----------------------------------------------------------------
if 'registry' in CASES:
    from eidoblend.look.post import custom_effects as CE
    V.stage(W, H, 16, world=0.035, sun=0.25, floor=True, floor_size=400.0)
    sc = bpy.context.scene
    sc.frame_start, sc.frame_end = 1, 3
    cam = V.camera((0.0, -30.0, 4.0), (0.0, 0.0, 4.0), lens=32)
    cam.data.clip_end = 1000.0
    if CE.REGISTRY.get('nuclear_explosion', {}).get('kind') == 'missing':
        CE.register('nuclear_explosion', NX.native_build, kind='native', params=[('opacity', 1.0, 0, 1)],
                    build_opts={'origin': (0.0, 0.0, 0.0), 'scale': 1.0, 'time_offset': 0.0, 'loop_seconds': 20.0,
                                'vol_steps': 96, 'quality': 'balanced', 'voxel': None, 'lights': 3, 'light_scale': 1.0,
                                'cache_dir': '//sdf_cache', 'disable_for_perf_test': False, 'bake': 'scene'},
                    unsupported=dict(NX.OPTION_NOTES), undo=NX.native_undo,
                    doc='the SDF mushroom cloud as two volumes in the scene (eidoblend.sdf.nuclear_explosion)')
        print('[integ] registry: registered nuclear_explosion as the hook asks (the file is not edited)', flush=True)
    n0 = len(bpy.data.objects)
    fx = CE.apply_to(sc, 'nuclear_explosion', {'nuclear_explosion': {
        'origin': [0, 0, 0], 'scale': 0.5, 'timeOffset': 6.0, 'maxT': 80, 'surfSteps': 64, 'quality': 'fast',
        'cache_dir': CACHE, 'opacity': 0.8}})
    made = len(bpy.data.objects) - n0
    u = fx.uniforms['opacity'] if 'opacity' in fx.uniforms else None
    V.check('registry: apply_to builds the cloud (volumes + lamps) and gives its opacity socket',
            made >= 2 and u is not None and abs(u.default_value - 0.8) < 1e-6, f'{made} objects; opacity {u}')
    fx.key('nuclear_explosion', 'opacity', 1, 0.0)
    fx.key('nuclear_explosion', 'opacity', 3, 1.0)
    sc.frame_set(2)
    V.check('registry: the opacity keys through FX.key', abs(u.default_value - 0.5) < 1e-3, f'{u.default_value:.3f}')
    # the lamps follow the keyed socket by themselves (the registry hands out only the socket, no cloud object to
    # call sync_lights() on)
    dg = bpy.context.evaluated_depsgraph_get()
    lamps = [o for o in bpy.data.objects if o.type == 'LIGHT' and o.name.startswith('nuclear_explosion')]
    e = {}
    for f in (1, 2, 3):
        sc.frame_set(f)
        dg = bpy.context.evaluated_depsgraph_get()
        e[f] = sum(o.evaluated_get(dg).data.energy for o in lamps)
    V.check('registry: the glow lamps fade with the keyed opacity', e[1] < 1e-6 and e[3] > 0 and 0 < e[2] < e[3],
            f'lamp energy at frames 1, 2, 3: {e[1]:.3g}, {e[2]:.3g}, {e[3]:.3g} W ({len(lamps)} lamps)')
    sc.frame_set(2)
    shot('registry', 'post registry nuclear_explosion, scale 0.5, t = 6 s, opacity keyed 0 -> 1 (frame 2)')
    CE.remove(sc, 'nuclear_explosion')
    left = [o.name for o in bpy.data.objects if o.name.startswith('nuclear_explosion')]
    V.check('registry: remove takes the cloud back out (native_undo)', not left, f'left {left}')

# ---- probe_reflect: does a sphere light probe carry a volume into EEVEE's reflections? ------------------------------
if 'probe_reflect' in CASES:
    V.stage(W, H, 16, world=0.004, sun=0.0, floor=True, floor_size=40.0)
    sc = bpy.context.scene
    cam = V.camera((0.0, -6.5, 2.0), (0.0, 0.0, 0.9), lens=40)
    bpy.ops.mesh.primitive_uv_sphere_add(radius=0.6, location=(1.6, 0.6, 0.6), segments=48, ring_count=24)
    ball = bpy.context.active_object
    bpy.ops.object.shade_smooth()
    m = bpy.data.materials.new('chrome')
    m.use_nodes = True
    b = m.node_tree.nodes['Principled BSDF']
    b.inputs['Metallic'].default_value = 1.0
    b.inputs['Roughness'].default_value = 0.05
    ball.data.materials.append(m)
    fire = EXAMPLES['bonfire'].make(cells=120, cache_dir=CACHE, name='refl_bonfire', build=False)
    build_still(fire, 1.3)
    fit_volume_range(sc, cam, [fire], frames=[1])
    p0 = shot('reflect_no_probe', 'chrome ball, no sphere probe')
    pd = bpy.data.lightprobes.new('ball_probe', 'SPHERE')
    po = bpy.data.objects.new('ball_probe', pd)
    sc.collection.objects.link(po)
    po.location = ball.location
    for attr, v in (('influence_distance', 3.0), ('clip_start', 0.65)):
        if hasattr(pd, attr):
            setattr(pd, attr, v)
    ball.hide_probe_sphere = True if hasattr(ball, 'hide_probe_sphere') else False
    p1 = shot('reflect_sphere_probe', 'chrome ball inside a sphere probe')
    a, b2 = V.read_png(p0), V.read_png(p1)
    print(f'[integ] probe_reflect: mean |diff| {float(np.abs(a - b2).mean()):.4f}', flush=True)
    V.sheet([p0, p1], os.path.join(OUT, 'integ_reflect_sheet.png'), cols=2)
V.summary()
