"""verify_probes.py: the independent verifier's probes of the two interiors, the ones the step's own tests do not take.

  ibl       the env light per material (env_light='material', the engine's model: the chrome at x 2.2, the seats at
            x 0.25) against the env as the World ('world'), both against the engine's look-off probes (region means
            printed), and the camera-only World checked to light nothing.
  shared    both sets in ONE scene, parked apart, cut from the quiet room to the showroom by keyed show() (the
            engine's way: every set in the conductor's scene, each hidden off screen). env_switch gives each its own
            env while it is shown, and each probe bakes with its set alone; the two shots must render as the same
            shots in a scene of their own (mean |dRGB| in 8-bit levels). The same room shot under the other set's
            World renders the same too (its materials carry their own env). Dispose then empties the shared World.
  parked    the quiet room's root moved (and then turned) after the build: the hatch shot through make_camera must
            render as before when moved (cams, lights' targets, the probe and the keyed crate are the set's
            children); turned, it must still read (looked at). The showroom moved and turned a quarter: its toaster
            shot must render as at home (the materials' env light turns with the set).
  scale     singer_scale=1: the face-height cam follows (no render).
  showroom  the toaster shot, and the empty seats under the blackout (lights 0): what stays lit is the env, the LED
            wall, the EXIT signs.
  look      INTERIORS.md's note for the look, run as the guide writes it: the reveal under argue (the white deck
            paints warm) and with the palette at 0.22 (it stays cold).

    HEAVY_VRAM_GB=4 bash work/claude_body/work/tmp/heavy.sh 12 bash run_blender.sh \
        <worktree>/blender/tests/sets_uf_interiors/verify_probes.py [--only ibl,shared,parked,scale,showroom,look]

Stills: out/verify/*.png and out/verify/verify_sheet.jpg.
"""
import math
import os
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import _common as T  # noqa: E402

import bpy  # noqa: E402
import numpy as np  # noqa: E402
from mathutils import Vector  # noqa: E402

from eidoblend.sets.unknown_force import interiors_lib as L  # noqa: E402
from eidoblend.sets.unknown_force import quiet_room as QR  # noqa: E402
from eidoblend.sets.unknown_force import showroom as SR  # noqa: E402

A = T.args({'only': 'ibl,shared,parked,scale,showroom,look', 'samples': 16, 'res': '960x540'})
OUT = os.path.join(T.OUT, 'verify')
os.makedirs(OUT, exist_ok=True)
W, H = (int(v) for v in A['res'].split('x'))
STILLS = []


def fresh(name):
    bpy.ops.wm.read_factory_settings(use_empty=True)
    sc = bpy.context.scene
    sc.name = name
    sc.render.fps = 30
    T.render_setup(sc, (W, H), int(A['samples']), bloom=True)
    return sc


def quiet_room(sc, **kw):
    return QR.build(sc, art_cache=T.ART, probe_spacing=0.45, probe_samples=512, **kw)


def showroom(sc, **kw):
    return SR.build(sc, art_cache=T.ART, probe_spacing=0.6, probe_samples=512, **kw)


def shot(sc, cam, frame, name):
    p = os.path.join(OUT, name + '.png')
    T.render_still(sc, cam, frame, p)
    STILLS.append(p)
    return p


def rgb(p):
    from PIL import Image
    return np.asarray(Image.open(p).convert('RGB'), np.float32)


def mad(a, b):
    return float(np.abs(rgb(a) - rgb(b)).mean())


# ================================================================================================ the probes
def shared():
    """both sets in one scene, cut by keyed show(), against each set alone."""
    sc = fresh('verify_shared')
    room = quiet_room(sc)
    show = showroom(sc)
    show.root.location = (80.0, 0.0, 0.0)                       # parked beside the room (Blender metres)
    w = L.env_switch(sc, [room, show])
    T.check('env_switch: one World holding both sets\' envs is the scene\'s World', sc.world == w and
            room._env_switch is show._env_switch and len(w.node_tree.nodes) >= 6, f'{w.name}, {len(w.node_tree.nodes)} nodes')
    room.show(True, frame=1)
    show.show(False, frame=1)
    room.show(False, frame=11)
    show.show(True, frame=11)
    cam_r, cam_s = room.make_camera('altar'), show.make_camera('toaster')
    sc.timeline_markers.new('room', frame=1).camera = cam_r
    sc.timeline_markers.new('show', frame=11).camera = cam_s
    room.eevee_settings(sc)
    sc.frame_set(1)
    secs = {**room.bake_probes(sc), **show.bake_probes(sc)}
    T.check('each probe baked with its set alone (the scene left as it was)', len(secs) == 2, f'{secs}')
    states = {}
    for f in (5, 15):
        sc.frame_set(f)
        states[f] = (room.root['uf_env_on'], show.root['uf_env_on'], room.root.hide_render, show.root.hide_render,
                     room['probe'].hide_render, show['probe'].hide_render)
    T.check('the keyed cut: frame 5 the room (shown, its env on), frame 15 the showroom',
            states[5] == (1.0, 0.0, False, True, False, True) and states[15] == (0.0, 1.0, True, False, True, False),
            f'{states}')
    a_room = shot(sc, cam_r, 5, 'shared_quiet_room_altar_f005')
    a_show = shot(sc, cam_s, 15, 'shared_showroom_toaster_f015')
    sw_world = sc.world
    sc.world = show.env                                         # one scene.world: the last set's env lights both
    wrong = shot(sc, cam_r, 5, 'shared_quiet_room_altar_f005_under_showroom_world')
    sc.world = sw_world
    # dispose: the shared World lets go of each set's env, and goes with the last set
    n_w = len(bpy.data.worlds)
    show.dispose()
    left = sc.world == sw_world and sw_world.name in bpy.data.worlds
    room.dispose()
    T.check('dispose: the shared World survives the first set and goes with the last', left and sc.world is None and
            len(bpy.data.worlds) == n_w - 3, f'{n_w} worlds -> {len(bpy.data.worlds)}')

    # each set alone in its own scene: the same shots
    sc = fresh('verify_room_alone')
    room = quiet_room(sc)
    sc.world = room.env
    room.eevee_settings(sc)
    cam = room.make_camera('altar')
    sc.frame_set(1)
    room.bake_probes(sc)
    b_room = shot(sc, cam, 1, 'alone_quiet_room_altar')
    sc = fresh('verify_show_alone')
    show = showroom(sc)
    sc.world = show.env
    show.eevee_settings(sc)
    cam = show.make_camera('toaster')
    sc.frame_set(1)
    show.bake_probes(sc)
    b_show = shot(sc, cam, 1, 'alone_showroom_toaster')
    d_room, d_show, d_wrong = mad(a_room, b_room), mad(a_show, b_show), mad(wrong, b_room)
    T.check('two sets in one scene render as each alone (env_switch + keyed show)', d_room < 1.5 and d_show < 1.5,
            f'mean |dRGB| room {d_room:.2f}, showroom {d_show:.2f} / 255')
    # env_light='material' (the default): the materials carry their own set's env, so even the other set's World
    # leaves the room as it is (the World is seen by the camera only, and the room's sky dome hides it)
    T.check("under the other set's World the room still renders as alone (its materials carry its own env light)",
            d_wrong < 1.5, f'mean |dRGB| {d_wrong:.2f} / 255')
    return b_room


def parked():
    """the quiet room's root moved, then turned, after the build."""
    sc = fresh('verify_parked')
    room = quiet_room(sc)
    sc.world = room.env
    room.eevee_settings(sc)
    cam = room.make_camera('hatch')
    room.update(16.4, {'shipT': 0.5}, frame=1)
    sc.frame_set(1)
    room.bake_probes(sc)
    p0 = shot(sc, cam, 1, 'parked_quiet_room_hatch_home')
    crate0 = room.parts['crate']['group'].matrix_world.translation.copy()
    room.root.location = (37.0, -21.0, 4.0)
    sc.frame_set(1)
    room.bake_probes(sc)
    p1 = shot(sc, cam, 1, 'parked_quiet_room_hatch_moved')
    crate1 = room.parts['crate']['group'].matrix_world.translation.copy()
    d = mad(p0, p1)
    T.check('moved: the hatch shot through make_camera renders as at home (cams, lights, probe, crate follow)',
            d < 1.5 and (crate1 - crate0 - Vector((37.0, -21.0, 4.0))).length < 1e-4,
            f'mean |dRGB| {d:.2f} / 255; crate moved by {tuple(round(v, 3) for v in crate1 - crate0)}')
    room.root.rotation_euler = (0.0, 0.0, math.radians(35))
    sc.frame_set(1)
    room.bake_probes(sc)
    p2 = shot(sc, cam, 1, 'parked_quiet_room_hatch_turned35')
    mean, clip, _black = T.stats(p2)
    k = room.parts['saleLights']['spots'][4]                     # the spot on the crate's stop: still aimed at it
    tgt = next(c.target for c in k.constraints if c.type == 'TRACK_TO')
    aim = -(k.matrix_world.to_3x3() @ Vector((0, 0, 1)))
    want = (tgt.matrix_world.translation - k.matrix_world.translation).normalized()
    T.check('turned 35 degrees: exposed, the lights still aimed at their targets', 0.02 < mean < 0.75 and
            aim.dot(want) > 0.9999, f'mean {mean:.3f}, aim dot {aim.dot(want):.6f}')
    # the showroom turned a quarter about Z: its env turns with it (the chrome, the plinth, the stage keep their light)
    sc = fresh('verify_parked_showroom')
    show = showroom(sc)
    sc.world = show.env
    show.eevee_settings(sc)
    cam = show.make_camera('toaster')
    sc.frame_set(1)
    show.bake_probes(sc)
    q0 = shot(sc, cam, 1, 'parked_showroom_toaster_home')
    show.root.location = (12.0, 30.0, 0.0)
    show.root.rotation_euler = (0.0, 0.0, math.radians(90))
    sc.frame_set(1)
    show.bake_probes(sc)
    q1 = shot(sc, cam, 1, 'parked_showroom_toaster_turned90')
    d = mad(q0, q1)
    T.check('turned 90 degrees and moved: the toaster shot renders as at home (the env turns with the set)', d < 1.5,
            f'mean |dRGB| {d:.2f} / 255')


def scale():
    """singer_scale=1: the face-height cam follows (no render)."""
    sc = fresh('verify_scale')
    a = QR.build(sc, art_cache=T.ART, probe=False)
    b = QR.build(sc, art_cache=T.ART, probe=False, singer_scale=1.0, name='set:quiet_room_s1')
    za, zb = a.cams['close']['pos'][2], b.cams['close']['pos'][2]
    T.check('singer_scale=1: the close cam rises with the face (1.53 m x scale + 0.08)',
            abs(za - (1.53 * 0.87 + 0.08)) < 1e-9 and abs(zb - (1.53 + 0.08)) < 1e-9, f'{za:.4f} -> {zb:.4f} m')
    s1 = SR.build(sc, art_cache=T.ART, probe=False, singerScale=1.0, name='set:showroom_s1')
    T.check("the engine's spelling singerScale works too (the showroom's close cam)",
            abs(s1.cams['close']['pos'][2] - (1.53 + 0.06)) < 1e-9, f"{s1.cams['close']['pos'][2]:.4f} m")


def showroom_probes():
    """the toaster shot; the empty seats under the blackout."""
    sc = fresh('verify_showroom')
    show = showroom(sc)
    sc.world = show.env
    show.eevee_settings(sc)
    cam_t, cam_e = show.make_camera('toaster'), show.make_camera('emptySeats')
    sc.frame_set(1)
    show.bake_probes(sc)
    sc.camera = cam_t
    pe = shot(sc, cam_t, 1, 'showroom_toaster_eevee')
    show.update(0.0, {'lights': 0.0}, key=False)
    pb = shot(sc, cam_e, 1, 'showroom_emptySeats_blackout')
    mean, clip, black = T.stats(pb)
    T.check('blackout over the empty seats: dark, not black (the env, the LED wall, the EXIT signs stay)',
            0.003 < mean < 0.2, f'mean {mean:.3f}, black {100 * black:.1f} %')
    return pe


ENGINE = os.path.normpath(os.path.join(T.BLENDER_DIR, '..', '..', 'eidoverse-video-prealpha-0.01', 'work',
                                        'unknown_force', 'sets', 'probes'))
# regions (x0, y0, x1, y1 at 960 x 540) of the engine's look-off probes and the same cams here
REGIONS = {
    'toaster': {'engine': 'sr_final_toaster_off_probe2.png',
                'chrome body': (447, 106, 528, 168), 'plinth front': (362, 200, 418, 470),
                'stage floor': (40, 300, 300, 520), 'drape': (40, 20, 300, 200)},
    'emptySeats': {'engine': 'sr_final_seats_cold_probe2.png',
                   'front rows': (30, 300, 280, 390), 'mid rows': (80, 200, 330, 260), 'stage deck': (150, 440, 500, 520)},
    'altar': {'engine': 'qr_final_altar_off_probe2.png',
              'centre board': (420, 200, 580, 270), 'right pews': (560, 330, 940, 520), 'left glass': (60, 120, 200, 250),
              'ceiling': (300, 10, 700, 80)},
}


def regions(path, cam):
    from PIL import Image
    a = np.asarray(Image.open(path).convert('RGB').resize((960, 540)), np.float32)
    out = {}
    for k, box in REGIONS[cam].items():
        if k != 'engine':
            x0, y0, x1, y1 = box
            out[k] = a[y0:y1, x0:x1].reshape(-1, 3).mean(0)
    return out


def world_light_check():
    """equirect_env(light=False): the World shows the env to the camera and lights nothing (EEVEE's Is Camera Ray)."""
    out = {}
    for light in (True, False):
        sc = fresh(f'verify_world_{light}')
        w = L.equirect_env(512, 256, SR.env_paint, name=f'w_{light}', light=light)
        sc.world = w
        me = bpy.data.meshes.new('plane')
        me.from_pydata([(-4, -4, 0), (4, -4, 0), (4, 4, 0), (-4, 4, 0)], [], [(0, 1, 2, 3)])
        ob = bpy.data.objects.new('plane', me)
        sc.collection.objects.link(ob)
        m = bpy.data.materials.new('white')
        m.use_nodes = True
        m.node_tree.nodes['Principled BSDF'].inputs['Base Color'].default_value = (0.9, 0.9, 0.9, 1)
        me.materials.append(m)
        cd = bpy.data.cameras.new('cam')
        cam = bpy.data.objects.new('cam', cd)
        sc.collection.objects.link(cam)
        cam.location = (0, 0, 3)
        p = os.path.join(OUT, f'world_light_{"on" if light else "camera_only"}.png')
        T.render_still(sc, cam, 1, p)
        out[light] = T.stats(p)[0]
    T.check("equirect_env(light=False): the World lights nothing (a white plane under it renders black)",
            out[False] < 0.01 < out[True] * 0.5, f'plane mean {out[True]:.3f} lit -> {out[False]:.4f} camera-only')


def ibl():
    """the showroom and the quiet room with each material lit by its own env (env_light='material', the engine's
    model) against the env as the World ('world'), and against the engine's look-off probes."""
    world_light_check()
    rows = {}
    for mode in ('world', 'material'):
        sc = fresh(f'verify_ibl_sr_{mode}')
        tb = time.perf_counter()
        show = showroom(sc, env_light=mode)
        dt = time.perf_counter() - tb
        sc.world = show.env
        show.eevee_settings(sc)
        cams = {nm: show.make_camera(nm) for nm in ('toaster', 'emptySeats', 'reveal')}
        sc.frame_set(1)
        show.bake_probes(sc)
        for nm, cam in cams.items():
            rows[(mode, nm)] = shot(sc, cam, 1, f'ibl_{mode}_showroom_{nm}')
        print(f'[verify] showroom {mode}: built in {dt:.1f} s', flush=True)
        sc = fresh(f'verify_ibl_qr_{mode}')
        room = quiet_room(sc, env_light=mode)
        sc.world = room.env
        room.eevee_settings(sc)
        cams = {nm: room.make_camera(nm) for nm in ('altar', 'pews')}
        sc.frame_set(1)
        room.bake_probes(sc)
        for nm, cam in cams.items():
            rows[(mode, nm)] = shot(sc, cam, 1, f'ibl_{mode}_quiet_room_{nm}')
    if mode == 'material':
        n_ibl = sum(1 for m in bpy.data.materials if m.get('uf_env_intensity') is not None and m.node_tree and any(
            n.bl_idname == 'ShaderNodeTexEnvironment' for n in m.node_tree.nodes))
        n_env = sum(1 for m in bpy.data.materials if m.get('uf_env_intensity') is not None)
        T.check("env_light='material': every material the engine gave the env carries its own env light",
                n_ibl == n_env and n_env > 20, f'{n_ibl} of {n_env}')
    for cam in ('toaster', 'emptySeats', 'altar'):
        eng = os.path.join(ENGINE, REGIONS[cam]['engine'])
        if not os.path.isfile(eng):
            continue
        e = regions(eng, cam)
        w_, m_ = regions(rows[('world', cam)], cam), regions(rows[('material', cam)], cam)
        for k in e:
            print(f'[verify] {cam:10s} {k:14s} engine {np.round(e[k]).astype(int)}  world {np.round(w_[k]).astype(int)}'
                  f'  material {np.round(m_[k]).astype(int)}', flush=True)
    return rows


def look_note():
    """INTERIORS.md's 'note for the look', as the guide writes it: under argue the white stage paints peach; a palette
    weight of 0.22 keeps it white. The reveal rendered both ways; the deck's warmth (R - B) measured."""
    from eidoblend.look.post import custom_effects as fx, aeropittura as AP
    from bpy_extras.object_utils import world_to_camera_view
    sc = fresh('verify_look')
    show = showroom(sc)
    sc.world = show.env
    show.eevee_settings(sc)
    cam = show.make_camera('reveal')
    sc.camera = cam
    sc.frame_set(1)
    show.bake_probes(sc)
    # the guide's snippet, as written there
    U = fx.apply_to(sc, 'aeropittura', {'aeropittura': {'layer': 'under'}}).uniforms['aeropittura']
    AP.apply_look(U, AP.LOOKS['argue'], 1.0, frame=1)
    p = world_to_camera_view(sc, sc.camera, show.focal.matrix_world.translation)
    AP.set_focal(U, p.x, 1.0 - p.y, frame=1)
    warm = {}
    for pal, nm in ((None, 'argue'), (0.22, 'argue_palette022')):
        if pal is not None:
            U['palette'].default_value = pal
            U['palette'].keyframe_insert('default_value', frame=1)
        path = shot(sc, cam, 1, f'look_showroom_reveal_{nm}')
        from PIL import Image
        a = np.asarray(Image.open(path).convert('RGB'), np.float32)
        deck = a[300:340, 120:840].reshape(-1, 3).mean(0)          # the white stage deck across the frame
        warm[nm] = float(deck[0] - deck[2])
    T.check("the look note: argue paints the white deck warm, the palette at 0.22 keeps it cold (the guide's snippet)",
            warm['argue_palette022'] < warm['argue'] - 5 and warm['argue_palette022'] < 8,
            f"deck R - B: argue {warm['argue']:.1f}, palette 0.22 {warm['argue_palette022']:.1f} (8-bit)")


def main():
    only = set(A['only'].split(','))
    t0 = time.perf_counter()
    if 'look' in only:
        look_note()
    if 'ibl' in only:
        ibl()
    if 'shared' in only:
        shared()
    if 'parked' in only:
        parked()
    if 'scale' in only:
        scale()
    if 'showroom' in only:
        showroom_probes()
    if STILLS:
        T.sheet(STILLS, os.path.join(OUT, 'verify_sheet.jpg'), cols=3, width=1440)
    print(f'[verify] {time.perf_counter() - t0:.0f} s', flush=True)
    return T.done()


if __name__ == '__main__':
    rc = main()
    sys.stdout.flush()
    if rc:
        sys.exit(rc)
