"""The engine's own vehicle check scenes, rebuilt in EEVEE and set beside the frames the engine rendered of them.

    cd <main checkout> && bash run_blender.sh \
        <worktree>/blender/tests/sdf_vehicles/test_vehicles_check_scenes.py -- [scenes=a,b,...] [t=0] [w=960 h=540]
    (a GPU job: 8 GB VRAM, 16 GB RAM cap; on a shared machine queue it with EIDO_GPU_WRAP, blender/tests/_where.py)

The WebGL engine kept these regression scenes (scene script, config and the frame it rendered: three.js, ACES); the
frames, its city HDRI and the smoke test's chair are reference files outside this repo, read from the folder
$EIDO_ENGINE_CHECK_DIR names (without it the test prints SKIP):
  sdf_all_examples        Mr. Hege, the red shoggoth, the modern sedan (0xc8c8d2, 0.18) and the cyberpunk sedan
                          (0x00e7ff, 0.12) under the city HDRI on a glossy grey ground
  sdf_cyberpunk_palette   four cyberpunk sedans: cyan, magenta, acid, amber
  sdf_sleek_palette       four sleek cars: silver 0.08, gold 0.12, copper 0.10, anodized purple 0.15
  sdf_jet_palette         four jets a metre up: silver, sky, desert, forest camo
  sdf_sleek_3q            the silver sleek car from a 3/4 view
  sdf_modern_wheel        the modern sedan's front wheel close up (the dished rim, the chrome cap)
  sdf_wheel_closeup       the cyberpunk sedan's front wheel close up (the chrome dome)
  sdf_sleek_wheel         the sleek car's hex-tiled hubcap close up
  sdf_badge_closeup       the cyberpunk's ALETH8APO badge plate close up, on a dark stage
  sdf_jet_rain            the forest jet in the rain (rain_on_camera; the engine's depth_rain world rain is not
                          ported to the Blender edition, so the scene renders without it)
  sdf_underwater_smoke    the SDF + GLB + VRM + underwater smoke test: the neon-pink modern sedan (0xff2d95, 0.22)
                          and the cyberpunk sedan beside it, the red shoggoth at 0.45 scale, Aporia idling between
                          them, a Poly Haven chair fitted to 1 m, under the underwater effect (4 s clip)
Each scene's renderFrame(t) camera is keyed over its clip (3 s, the smoke test's 4 s; 30 fps, LINEAR), so the rebuilt
scene plays; the frame rendered is the engine frame's: the lineups match t = 0, the close-ups t = 2 (their orbits
face the wheel or the badge then); t= overrides both.
Each is rebuilt from its script's numbers in Blender axes, the vehicles placed by the engine's rule (bounds.min on
the ground: position.y = -1.35 - bounds.min.y). Two examples' bounds were corrected (examples_vehicles.py): the
engine's put the sleek car 0.5625 m and the jet 0.163 m above where their lowest points are, so here they stand
lower, and the camera of a scene that frames them moves down with them to keep the engine's framing.
out/engine_<scene>.png: EEVEE left, the engine's frame right. The engine frames are older than the GLSL backup the
port comes from (the cyberpunk palette's bodies were then painted uPaint all over; near-black since), and on the
stages without an HDRI (the badge close-up, the smoke test) the engine's shade() reflected a flat mid-grey fallback
while EEVEE reflects the scene's own dim world; the jets' fins lean inward there and splay outward here (the public
engine's TSL turn, examples_vehicles.py). So the frames are a guide to placement, framing and character, not a pixel
reference. PASS lines: each scene builds and renders, and every vehicle's mesh centre lands inside the frame where the
engine placed it.
"""

import math
import os
import sys
import time

import numpy as np

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import _vcommon as V  # noqa: E402

import bpy  # noqa: E402
from mathutils import Vector  # noqa: E402

from eidoblend import sdf  # noqa: E402

A = V.args()
W, H = int(A.get('w', '960')), int(A.get('h', '540'))
SAMPLES = int(A.get('samples', '16'))
T_OVERRIDE = float(A['t']) if 't' in A else None
CACHE = os.path.join(V.OUT, 'cache_checks')
GROUND_Y = -1.35
# the engine's declared bounds.min.y of each vehicle (what its placement rule read)
ENGINE_MIN_Y = {'stylized_modern_sedan': 0.0, 'stylized_cyberpunk_sedan': 0.0, 'stylized_sci_fi_sleek_car': -0.63,
                'stylized_fighter_jet': -0.9, 'mr_hege': -1.40, 'red_shoggoth': -1.1}
three = V.three


def srgb_lin(h):
    c = np.array([(h >> 16) & 255, (h >> 8) & 255, h & 255], float) / 255.0
    return tuple(float(x) for x in np.where(c <= 0.04045, c / 12.92, ((c + 0.055) / 1.055) ** 2.4))


def engine_stage(ground=60.0, ground_hex=0x808080, rough=0.3, metal=0.2, key=1.4, key_dir=(5.0, 9.0, 4.0),
                 hdri=True, background=None, ambient=None, exposure=1.0):
    V.purge()
    sc = V.stage(W, H, SAMPLES, hdri=hdri, sun_energy=key, sun_dir3=key_dir, sun_angle=0.5, ground_z=GROUND_Y,
                 ground_size=ground, ground_color=srgb_lin(ground_hex), ground_roughness=rough,
                 ground_metallic=metal, background=background)
    if ambient is not None:
        # AmbientLight(color, intensity): three adds irradiance color * intensity, scattered by albedo / pi. A uniform
        # world of radiance L gives an up-facing surface pi L of irradiance, so the same diffuse light is L = c k / pi
        bg = sc.world.node_tree.nodes['Background']
        col, k = ambient
        bg.inputs['Color'].default_value = (*[c * k / math.pi for c in srgb_lin(col)], 1.0)
        bg.inputs['Strength'].default_value = 1.0
    sc.view_settings.exposure = math.log2(exposure)
    return sc


def place(name, x, z, rot_y=0.0, hover=0.0, **make):
    """EXAMPLES[name].make(...) at position.y = groundY - bounds.min.y (+ hover), rotation.y = rot_y.
    Returns (object, dy): dy is how much lower than the engine's placement it stands (its bounds correction)."""
    ex = sdf.EXAMPLES[name]
    min_y = ex['bounds']['min'][1]
    y = GROUND_Y - min_y + hover
    obj = ex.make(name=f'chk_{name}', cache_dir=CACHE, location=three(x, y, z), rotation=(0.0, 0.0, rot_y),
                  log=None, **make)
    dy = (GROUND_Y - min_y) - (GROUND_Y - ENGINE_MIN_Y[name])
    return obj, dy


def camera(pos3, target3, fov, dy=0.0):
    return V.camera_three((pos3[0], pos3[1] + dy, pos3[2]), (target3[0], target3[1] + dy, target3[2]), fov)


FPS, SECONDS = 30, 3.0


def keyed_camera(at, fov, t_render, dy=0.0, seconds=SECONDS):
    """The scene's renderFrame(t) camera keyed over its clip (3 s unless said; 30 fps, LINEAR), so the rebuilt scene
    plays as the engine's did; the scene is left at the frame of t_render (the engine frame's). at(t) -> (pos3,
    target3)."""
    from mathutils import Vector
    sc = bpy.context.scene
    pos, tgt = at(0.0)
    cam = camera(pos, tgt, fov, dy)
    cam.rotation_mode = 'QUATERNION'
    n = int(round(FPS * seconds))
    sc.render.fps = FPS
    sc.frame_start, sc.frame_end = 1, n
    prev = None
    for f in range(1, n + 1):
        pos, tgt = at((f - 1) / FPS)
        p = Vector(three(pos[0], pos[1] + dy, pos[2]))
        q = (Vector(three(tgt[0], tgt[1] + dy, tgt[2])) - p).to_track_quat('-Z', 'Y')
        if prev is not None and prev.dot(q) < 0.0:
            q.negate()                                 # the short way round, key to key
        prev = q
        cam.location = p
        cam.rotation_quaternion = q
        cam.keyframe_insert('location', frame=f)
        cam.keyframe_insert('rotation_quaternion', frame=f)
    ad = cam.animation_data
    from bpy_extras import anim_utils
    bag = anim_utils.action_get_channelbag_for_slot(ad.action, ad.action_slot)
    for fc in bag.fcurves:
        for kp in fc.keyframe_points:
            kp.interpolation = 'LINEAR'
    sc.frame_set(int(round(t_render * FPS)) + 1)
    return cam


def project(cam, world_pt):
    from bpy_extras.object_utils import world_to_camera_view
    v = world_to_camera_view(bpy.context.scene, cam, Vector(world_pt))
    return v.x * W, (1.0 - v.y) * H, v.z


def finish(scene_name, cars, cam, engine_jpg, subject3=None, dy=0.0):
    """Render, check the subject is where the engine framed it, and set the frame beside the engine's. The subject is
    every vehicle's centre (a lineup) or, for a close-up, the three point the engine's camera aimed at (moved by dy
    with its vehicle)."""
    p = os.path.join(V.OUT, f'_engine_{scene_name}_eevee.png')
    t0 = time.perf_counter()
    ok = V.render(p)
    V.check(f'{scene_name}: renders', ok, f'{p} in {time.perf_counter() - t0:.1f} s')
    bpy.context.view_layer.update()
    if subject3 is not None:
        pts = [three(subject3[0], subject3[1] + dy, subject3[2])]
    else:
        pts = [np.array([c.object.matrix_world @ Vector(v) for v in c.object.bound_box]).mean(axis=0) for c in cars]
    where = [project(cam, q) for q in pts]
    inside = [0 <= x <= W and 0 <= y <= H and z > 0 for x, y, z in where]
    V.check(f'{scene_name}: the subject is in the frame', all(inside),
            f'{sum(inside)} of {len(inside)} at ' + ', '.join(f'({x:.0f}, {y:.0f})' for x, y, _z in where))
    eng = V.engine_frame(engine_jpg, W, H)
    if eng is not None:
        ep = V.save_rgb(os.path.join(V.OUT, f'_engine_{scene_name}_engine.png'), eng)
        V.sheet([p, ep], os.path.join(V.OUT, f'engine_{scene_name}.png'), cols=2)
    V.free_images()


def t_of(default):
    return default if T_OVERRIDE is None else T_OVERRIDE


# ===================================================================================================== scenes ===

def sdf_all_examples():
    t = t_of(0.0)
    engine_stage()
    hege, _ = place('mr_hege', -5.0, 0.0)
    shog, _ = place('red_shoggoth', -2.5, 0.0)
    modern, _ = place('stylized_modern_sedan', 1.5, 0.0, -0.3, paint_color=0xc8c8d2, paint_roughness=0.18)
    cyber, _ = place('stylized_cyberpunk_sedan', 6.5, 0.0, -0.3, paint_color=0x00e7ff, paint_roughness=0.12)
    cam = keyed_camera(lambda t: ((math.sin(t * 0.2) * 2, 3.5 + math.sin(t * 0.3) * 0.4, 14.0), (0.0, 0.4, 0.0)),
                       38.0, t)
    finish('all_examples', [hege, shog, modern, cyber], cam, 'sdf_all_examples_frame.jpg')


def sdf_cyberpunk_palette():
    t = t_of(0.0)
    engine_stage()
    cars = [place('stylized_cyberpunk_sedan', x, 0.0, -0.45, paint_color=c, paint_roughness=0.12,
                  decal_text='ALETH8APO')[0]
            for x, c in ((-8.25, 0x00e7ff), (-2.75, 0xff2bd6), (2.75, 0x7dff00), (8.25, 0xff8a1a))]
    cam = keyed_camera(lambda t: ((math.sin(t * 0.25) * 4, 5.5 + math.sin(t * 0.4) * 0.8, 18.0), (0.0, 0.4, 0.0)),
                       35.0, t)
    finish('cyberpunk_palette', cars, cam, 'sdf_cyberpunk_palette_frame.jpg')


def sdf_sleek_palette():
    t = t_of(0.0)
    engine_stage()
    cars, dy = [], 0.0
    for x, c, r in ((-7.5, 0xf3eee0, 0.08), (-2.5, 0xffb44a, 0.12), (2.5, 0xf2a387, 0.10), (7.5, 0x8b4dcc, 0.15)):
        car, dy = place('stylized_sci_fi_sleek_car', x, 0.0, -0.3, metal_color=c, paint_roughness=r)
        cars.append(car)
    cam = keyed_camera(lambda t: ((math.sin(t * 0.25) * 3, 4.0 + math.sin(t * 0.4) * 0.6, 16.0), (0.0, 0.4, 0.0)),
                       35.0, t, dy)
    finish('sleek_palette', cars, cam, 'sdf_sleek_palette_frame.jpg')


def sdf_jet_palette():
    t = t_of(0.0)
    engine_stage(ground=80.0)
    cars, dy = [], 0.0
    for x, camo in ((-7.5, 'silver'), (-2.5, 'sky'), (2.5, 'desert'), (7.5, 'forest')):
        car, dy = place('stylized_fighter_jet', x, 0.0, -0.25, hover=1.0, camo=camo)
        cars.append(car)
    cam = keyed_camera(lambda t: ((math.sin(t * 0.25) * 2, 6.5 + math.sin(t * 0.4) * 0.5, 22.0), (0.0, 0.4, 0.0)),
                       35.0, t, dy)
    finish('jet_palette', cars, cam, 'sdf_jet_palette_frame.jpg')


def sdf_sleek_3q():
    t = t_of(0.0)
    engine_stage(ground=40.0)
    car, dy = place('stylized_sci_fi_sleek_car', 0.0, 0.0, -0.3, metal_color=0xf3eee0, paint_roughness=0.15)
    r, tgt = 4.5, (0.0, -0.2, 0.0)

    def at(t):
        a = -0.7 + math.sin(t * 0.4) * 0.15
        return (tgt[0] + r * math.sin(a), tgt[1] + 0.3 + math.sin(t * 0.3) * 0.1, tgt[2] + r * math.cos(a)), tgt

    cam = keyed_camera(at, 35.0, t, dy)
    finish('sleek_3q', [car], cam, 'sdf_sleek_3q_frame.jpg')


def _wheel_cam(t, tgt, r, a0, rate, y_of_t, fov, dy=0.0):
    def at(tt):
        a = a0 + tt * rate
        return (tgt[0] + r * math.cos(a), y_of_t(tt), tgt[2] + r * math.sin(a)), tgt
    return keyed_camera(at, fov, t, dy)


def sdf_modern_wheel():
    t = t_of(2.0)
    engine_stage(ground=20.0)
    car, _ = place('stylized_modern_sedan', 0.0, 0.0, paint_color=0xc8c8d2, paint_roughness=0.45)
    cam = _wheel_cam(t, (0.85, -0.95, 1.40), 1.4, -0.4, 0.2, lambda t: -0.7 + math.sin(t * 0.3) * 0.15, 28.0)
    finish('modern_wheel', [car], cam, 'sdf_modern_wheel_frame.jpg', subject3=(0.85, -0.95, 1.40))


def sdf_wheel_closeup():
    t = t_of(2.0)
    engine_stage(ground=20.0)
    car, _ = place('stylized_cyberpunk_sedan', 0.0, 0.0, paint_color=0x00e7ff, paint_roughness=0.12)
    cam = _wheel_cam(t, (0.85, -0.95, 1.40), 1.4, -0.4, 0.2, lambda t: -0.7 + math.sin(t * 0.3) * 0.15, 28.0)
    finish('wheel_closeup', [car], cam, 'sdf_wheel_closeup_frame.jpg', subject3=(0.85, -0.95, 1.40))


def sdf_sleek_wheel():
    t = t_of(2.0)
    engine_stage(ground=20.0)
    # a macro shot: the hubcap rim against the tyre is a right-angle crease 7.5 mm from the disc's edge, which the
    # default 5 mm voxel steps; 2.5 mm resolves it (as a film's close-up would ask with voxel=)
    car, dy = place('stylized_sci_fi_sleek_car', 0.0, 0.0, metal_color=0xf3eee0, paint_roughness=0.15, voxel=0.0025)
    tgt = (0.63, -0.42, 1.43)
    cam = _wheel_cam(t, tgt, 0.75, -0.4, 0.3, lambda t: tgt[1] + 0.15 + math.sin(t * 0.4) * 0.08, 28.0, dy)
    finish('sleek_wheel', [car], cam, 'sdf_sleek_wheel_frame.jpg', subject3=tgt, dy=dy)


def sdf_badge_closeup():
    t = t_of(2.0)
    engine_stage(ground=20.0, ground_hex=0x1a2028, rough=0.6, metal=0.1, key=1.8, key_dir=(5.0, 8.0, 4.0),
                 hdri=False, background=srgb_lin(0x06141e), ambient=(0x445566, 0.7), exposure=1.05)
    for ob in bpy.data.objects:
        if ob.type == 'LIGHT' and ob.name == 'key':
            ob.data.color = srgb_lin(0xffeedd)
    car, _ = place('stylized_cyberpunk_sedan', 0.0, 0.0, paint_color=0x00e7ff, paint_roughness=0.12,
                   decal_text='ALETH8APO')
    tgt = (0.834, -0.25, -0.95)

    def at(tt):
        a = -0.5 + tt * 0.25
        return (tgt[0] + 1.7 * math.cos(a), -0.05 + math.sin(tt * 0.3) * 0.10, tgt[2] + 1.7 * math.sin(a)), tgt

    cam = keyed_camera(at, 35.0, t)
    finish('badge_closeup', [car], cam, 'sdf_badge_closeup_frame.jpg', subject3=tgt)


def sdf_jet_rain():
    t = t_of(0.0)
    engine_stage(ground=60.0, ground_hex=0x707070, rough=0.55, metal=0.15)
    car, dy = place('stylized_fighter_jet', 0.0, 0.0, -0.3, hover=0.2, camo='forest')
    cam = keyed_camera(lambda t: ((4.0 + math.sin(t * 0.2) * 1.5, 2.0 + math.sin(t * 0.4) * 0.3, 9.0), (0.0, 0.0, 0.0)),
                       35.0, t, dy)
    try:
        from eidoblend.look.post import custom_effects as fx
        fx.apply_to(bpy.context.scene, 'rain_on_camera', {'rain_on_camera': {'amount': 0.55}})
    except Exception as e:  # noqa: BLE001 - the scene still renders the jet
        print(f'[checks] rain_on_camera not applied: {e}', flush=True)
    finish('jet_rain', [car], cam, 'sdf_jet_rain_frame.jpg')


def _import_fitted_gltf(path, centre_x, centre_z, fit=1.0):
    """The smoke test's Poly Haven model: imported, scaled so its largest side is `fit` metres, centred on (x, z) in
    three's axes and stood on the ground (y = -1.35), as the scene's Box3 fit did."""
    before = set(bpy.data.objects)
    bpy.ops.import_scene.gltf(filepath=path)
    new = [o for o in bpy.data.objects if o not in before]
    roots = [o for o in new if o.parent is None or o.parent not in new]
    bpy.context.view_layer.update()

    def box():
        pts = np.array([o.matrix_world @ Vector(c) for o in new if o.type == 'MESH' for c in o.bound_box])
        return pts.min(axis=0), pts.max(axis=0)

    lo, hi = box()
    s = fit / float(max(hi - lo))
    for r in roots:
        r.scale = tuple(x * s for x in r.scale)
        r.location = tuple(x * s for x in r.location)
    bpy.context.view_layer.update()
    lo, hi = box()
    want = Vector(three(centre_x, GROUND_Y, centre_z))
    shift = Vector((want.x - 0.5 * (lo[0] + hi[0]), want.y - 0.5 * (lo[1] + hi[1]), GROUND_Y - lo[2]))
    for r in roots:
        r.location = r.location + shift
    bpy.context.view_layer.update()
    return new


def sdf_underwater_smoke():
    """The engine's SDF + GLB + VRM + underwater smoke test: two sedans made by make(), a scaled SDF, a VRM and a
    fetched model on one ground, under the depth-keyed underwater effect."""
    t = t_of(0.0)
    sc = engine_stage(ground=30.0, ground_hex=0x1a2028, rough=0.6, metal=0.1, key=1.6, key_dir=(5.0, 8.0, 4.0),
                      hdri=False, background=srgb_lin(0x06141e), ambient=(0x223344, 0.5), exposure=1.05)
    for ob in bpy.data.objects:
        if ob.type == 'LIGHT' and ob.name == 'key':
            ob.data.color = srgb_lin(0xddeeff)
    chair = os.path.join(V.CHECK, 'sdf_smoke_assets', 'greenchair_01_embedded.gltf')
    if os.path.exists(chair):
        _import_fitted_gltf(chair, -2.4, 0.0, 1.0)
    try:
        from eidoblend.characters import load_vrm, play_vrma_default
        aporia = load_vrm('aporia', location=three(2.2, GROUND_Y, 0.0))
        play_vrma_default(aporia, 'idle')
    except Exception as e:  # noqa: BLE001 - the scene's subject is the sedans; say why Aporia is missing
        print(f'[checks] Aporia not loaded: {e}', flush=True)
    shog_scale = 0.45
    sdf.EXAMPLES['red_shoggoth'].make(name='chk_red_shoggoth', cache_dir=CACHE, scale=shog_scale,
                                      location=three(-4.2, GROUND_Y + 1.1 * shog_scale, -0.5), log=None)
    car, _ = place('stylized_modern_sedan', 0.0, 0.0, paint_color=0xff2d95, paint_roughness=0.22)
    cyber, _ = place('stylized_cyberpunk_sedan', 3.2, 0.0, paint_color=0x00e7ff, paint_roughness=0.12,
                     decal_text='ALETH8APO')

    def at(tt):
        ang = 0.4 + tt * 0.25
        return (math.sin(ang) * 9.0, 0.8 + math.sin(tt * 0.5) * 0.2, math.cos(ang) * 9.0), (0.0, -0.4, 0.0)

    cam = keyed_camera(at, 45.0, t, seconds=4.0)
    cam.data.clip_end = 60.0
    from eidoblend.look.post import custom_effects as fx
    # the WebGL underwater's options that the WebGPU effect (the ported one) has: opacity, the caustics, the rays;
    # waterY, raySteps and depthFade were the WebGL pass's own
    fx.apply_to(sc, 'underwater', {'underwater': {'opacity': 0.9, 'caustic_amt': 0.9, 'caustic_scale': 0.5,
                                                  'godray_amt': 1.6, 'bubble_count': 0}})
    finish('underwater_smoke', [car, cyber], cam, 'sdf_underwater_smoke_frame.jpg')


SCENES = {f.__name__: f for f in (sdf_all_examples, sdf_cyberpunk_palette, sdf_sleek_palette, sdf_jet_palette,
                                   sdf_sleek_3q, sdf_modern_wheel, sdf_wheel_closeup, sdf_sleek_wheel,
                                   sdf_badge_closeup, sdf_jet_rain, sdf_underwater_smoke)}

if V.CHECK is None or not os.path.isdir(V.CHECK):
    print(f'SKIP vehicle check scenes: {V.CHECK} is not a folder' if V.CHECK else
          'SKIP vehicle check scenes: no check-scene folder (EIDO_ENGINE_CHECK_DIR)', flush=True)
    V.summary()
    sys.exit(0)

for name in (A['scenes'].split(',') if 'scenes' in A else SCENES):
    key = name if name.startswith('sdf_') else 'sdf_' + name
    t0 = time.perf_counter()
    SCENES[key]()
    print(f'[checks] {key}: {time.perf_counter() - t0:.1f} s', flush=True)

V.summary()
