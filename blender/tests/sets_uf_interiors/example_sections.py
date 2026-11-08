"""example_sections.py: the two interiors in the film's own sections, keyed frame by frame, rendered by jumping into
the keyed timeline (the .blend plays on its own).

  --plan film (default): UNKNOWN FORCE's conductor (eidoverse/examples/unknown_force/scene.js) over the two sets:
      its SHOTS rows (a cut at every row, each cam with its move: push = metres along the view over the shot,
      smoothed; orbit = radians about the target's vertical, u - 0.5), its setState curves, and the look it ran
      there: aeropittura 'argue' (the section's look), the set's plane family (SET_LOOK: the quiet room balla_sun,
      the showroom iridescent), the focal at the set's idol (the altar board; her face height), the reading shots'
      settled brush (move.read), her face spared, spin = t x 0.03, and the showroom's palette pulled to 0.22
      ("argue, cold": the white stage stays white).
        quiet room, verse 1 (40.8-61.5 s): altar (push 0.8), board (push 0.15, read), pews (orbit 0.12), essay
          (push 0.1, read), close (push 0.25), crate (read), altar (push -0.6); shipT = smooth ramp 55.4-58.0,
          sale = smooth ramp 57.6-59.0 x (1 - smooth ramp 61.0-61.5)
        showroom, pre-chorus 2 (163.0-174.6 s): reveal (push 0.6, read), toaster (read), emptySeats, close;
          spin = (t - 163) x 0.25; the conductor keeps her at the set origin facing the audience (the platter turns
          under her) and hides her on the toaster, emptySeats and wall cams (keyed at the cuts here)
  --plan doc: INTERIORS.md's suggested timing on the set cams as they are (no look): the boards on "mark my odds
      in red", the altar on "like a church needs a hell", the lectern and essay, shipT over "and ships another me",
      sale on "the fear is how they sell"; the showroom's spin = (t - 163.1) x 0.35.

    HEAVY_VRAM_GB=4 bash work/claude_body/work/tmp/heavy.sh 12 bash run_blender.sh \
        <worktree>/blender/tests/sets_uf_interiors/example_sections.py [--plan film|doc] [--set quiet_room|showroom|both]
        [--fps 30] [--outfit tuta|suit] [--no_look] [--no_plain] [--save] [--keep_blend] [--no_render]

The singer is the claudesona at the sets' scale (0.87) playing idle; --outfit tuta dresses her in the film's TuTa
(claude_suit_wardrobe.vrm, characters.claudesona.make_wardrobe), --outfit suit stands claude_suit.vrm. Her clips, her
own lights, the captions and the badges are the conductor's, not the sets'. Each still is rendered under the look
and, unless --no_plain, without it (out/sections/<plan>_<set>_<cam>_t<t>[_plain].png). --save writes the section's
.blend, opens it again in this Blender, renders the first still plain from the file alone and compares it with the
render made before saving (the keys, drivers and markers carry the shot); --keep_blend keeps the file.
"""
import math
import os
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import _common as T  # noqa: E402

import bpy  # noqa: E402
import numpy as np  # noqa: E402
from bpy_extras.object_utils import world_to_camera_view  # noqa: E402
from mathutils import Vector  # noqa: E402

from eidoblend.look import camera as LC  # noqa: E402
from eidoblend.sets.unknown_force import interiors_lib as L  # noqa: E402
from eidoblend.sets.unknown_force import quiet_room as QR  # noqa: E402
from eidoblend.sets.unknown_force import showroom as SR  # noqa: E402

A = T.args({'plan': 'film', 'fps': 30, 'set': 'both', 'samples': 16, 'res': '960x540', 'save': False,
            'keep_blend': False, 'no_vrm': False, 'no_render': False, 'no_look': False, 'no_plain': False,
            'outfit': 'tuta', 'step': 2})
OUT = os.path.join(T.OUT, 'sections')
os.makedirs(OUT, exist_ok=True)


def smooth(x):
    x = min(1.0, max(0.0, x))
    return x * x * (3 - 2 * x)


def sramp(t, a, b):
    """scene.js setState's ramp(a, b): smooth((t - a) / (b - a))"""
    return smooth((t - a) / (b - a))


def ramp(t, a, b):
    return min(1.0, max(0.0, (t - a) / (b - a)))


# ------------------------------------------------------------------------------------------------ the plans
PLANS = {
    'film': {
        'quiet_room': {
            't0': 40.8, 't1': 61.5, 'look': 'argue', 'planes': 'balla_sun', 'palette': None,
            'shots': [(40.8, 'altar', {'push': 0.8}), (43.0, 'board', {'push': 0.15, 'read': True}),
                      (45.2, 'pews', {'orbit': 0.12}), (49.6, 'essay', {'push': 0.1, 'read': True}),
                      (52.4, 'close', {'push': 0.25}), (55.4, 'crate', {'read': True}),
                      (58.0, 'altar', {'push': -0.6})],
            'state': lambda t: {'shipT': sramp(t, 55.4, 58.0), 'sale': sramp(t, 57.6, 59.0) * (1 - sramp(t, 61.0, 61.5))},
            'stills': [41.9, 44.1, 47.4, 51.0, 53.9, 56.6, 59.5],
        },
        'showroom': {
            't0': 163.0, 't1': 174.6, 'look': 'argue', 'planes': 'iridescent', 'palette': 0.22,
            'shots': [(163.0, 'reveal', {'push': 0.6, 'read': True}), (168.0, 'toaster', {'read': True}),
                      (170.6, 'emptySeats', {}), (172.4, 'close', {})],
            'state': lambda t: {'spin': (t - 163.0) * 0.25},
            'stills': [165.5, 169.3, 171.5, 173.5],
            # the conductor puts her back at the set origin facing the audience every frame (the platter turns
            # under her, she does not ride it) and hides her on these cams
            'on_platter': False, 'hidden_on': ('toaster', 'emptySeats', 'wall'),
        },
    },
    'doc': {
        'quiet_room': {
            't0': 40.8, 't1': 60.0, 'look': None,
            'shots': [(40.8, 'board', {}), (43.0, 'close', {}), (45.2, 'altar', {}), (48.0, 'pews', {}),
                      (50.0, 'lectern', {}), (52.2, 'essay', {}), (54.3, 'hatch', {}), (57.6, 'crate', {})],
            'state': lambda t: {'shipT': ramp(t, 55.5, 57.3), 'sale': ramp(t, 58.1, 60.0), 'hell': 1.0},
            'stills': [41.5, 46.0, 51.0, 56.4, 59.6],
        },
        'showroom': {
            't0': 163.1, 't1': 173.7, 'look': None,
            'shots': [(163.1, 'reveal', {}), (165.4, 'close', {}), (166.8, 'wall', {}), (168.2, 'toaster', {}),
                      (170.7, 'emptySeats', {})],
            'state': lambda t: {'spin': (t - 163.1) * 0.35, 'seq': 0.997, 'lights': 1.0, 'beams': 1.0, 'screen': 1.0},
            'stills': [163.8, 166.0, 169.0, 172.5],
            'on_platter': True,                     # INTERIORS.md: parent her to the platter so she turns with it
        },
    },
}


def cam_pose(cam, u, move):
    """scene.js camPose for a set cam (three's axes): push along the view (smoothed), orbit about the target's
    vertical by orbit x (u - 0.5), rise. -> (pos, target, fov), three's axes."""
    pos, tgt = np.array(cam['pos'], float), np.array(cam['target'], float)
    d = tgt - pos
    d /= np.linalg.norm(d)
    if move.get('push'):
        pos = pos + d * move['push'] * smooth(u)
    if move.get('orbit'):
        a = move['orbit'] * (u - 0.5)
        r = pos - tgt
        c, s = math.cos(a), math.sin(a)
        r = np.array([r[0] * c + r[2] * s, r[1], -r[0] * s + r[2] * c])     # applyAxisAngle((0, 1, 0), a)
        pos = tgt + r
    if move.get('rise'):
        pos = pos + np.array([0.0, move['rise'] * smooth(u), 0.0])
    return pos, tgt, cam.get('fov', 40)


def new_scene(name, fps):
    """a fresh file for the section (headless Blender has no window to switch scenes in). characters.vrma's clip
    cache holds the previous file's Actions (load_clip reads a removed one's name and raises), so it is emptied."""
    from eidoblend.characters import vrma
    vrma._CACHE.clear()
    bpy.ops.wm.read_factory_settings(use_empty=True)
    sc = bpy.context.scene
    sc.name = name
    sc.render.fps = fps
    return sc


def shot_cameras(scene, s, plan, f_of):
    """one Blender camera per shot row, its pose keyed every frame of the shot (LINEAR), a timeline marker binding
    it at the cut. -> [(f0, f1, cam, row)]"""
    keyer = L.Keyer()
    rows = plan['shots']
    out = []
    for i, (s0, nm, move) in enumerate(rows):
        s1 = rows[i + 1][0] if i + 1 < len(rows) else plan['t1']
        f0, f1 = f_of(s0), f_of(s1) - 1
        cam = s.make_camera(nm)
        cam.name = f'{cam.name}:{i:02d}'
        cam.rotation_mode = 'XYZ'
        base = s['cams_three'][nm]
        prev = None
        for f in range(f0, f1 + 1):
            t = plan['t0'] + (f - 1) / scene.render.fps
            u = (t - s0) / (s1 - s0)
            pos, tgt, _fov = cam_pose(base, u, move)
            M = LC.look_matrix(Vector(L.to_blender(pos)), Vector(L.to_blender(tgt)))
            cam.location = M.translation
            e = M.to_3x3().to_euler('XYZ', prev) if prev is not None else M.to_3x3().to_euler('XYZ')
            cam.rotation_euler = e
            prev = e
            keyer.key(cam, 'location', f)
            keyer.key(cam, 'rotation_euler', f)
        m = scene.timeline_markers.new(f'cut_{i:02d}_{nm}', frame=f0)
        m.camera = cam
        out.append((f0, f1, cam, (s0, nm, move)))
    scene.camera = out[0][2]
    return out


def shot_at(shots, f):
    return max((sh for sh in shots if sh[0] <= f), key=lambda sh: sh[0])


def key_singer_visibility(h, shots, hidden_on):
    """the conductor's vrm.scene.visible per shot: hidden on the cams in hidden_on, keyed CONSTANT at each cut.
    Only her objects that render now are keyed (the wardrobe's hidden layers stay hidden)."""
    keyer = L.Keyer()
    obs = [o for o in h.objects if not o.hide_render]
    for f0, _f1, _cam, (_s0, nm, _move) in shots:
        hide = nm in hidden_on
        for o in obs:
            o.hide_render = o.hide_viewport = hide
            keyer.key(o, 'hide_render', f0, interpolation='CONSTANT')
            keyer.key(o, 'hide_viewport', f0, interpolation='CONSTANT')
    return obs


def singer(s, mark, parent=None):
    if A['no_vrm']:
        return None
    vrm, wear = ('claude_suit_wardrobe', 'tuta') if A['outfit'] == 'tuta' else ('claude_suit', None)
    try:
        h = T.load_singer(L.to_blender(mark['pos']), 0.0, 0.87, parent=parent, vrm=vrm, wear=wear)
    except Exception as e:                                                   # the wardrobe is another package's
        print(f'[sections] the {A["outfit"]} outfit did not load ({type(e).__name__}: {e}); standing claude_suit',
              flush=True)
        h = T.load_singer(L.to_blender(mark['pos']), 0.0, 0.87, parent=parent)
    return h


def look_keys(scene, s, plan, shots, h, fps, f_last):
    """the film's look over the section, keyed: argue + the set's plane family at frame 1, the showroom's palette,
    the reading shots' settled brush, then focal (the set's idol), spare (her face) and spin every `step` frames."""
    from eidoblend.look.post import custom_effects as fx, aeropittura as AP
    e = fx.apply_to(scene, 'aeropittura', {'aeropittura': {'layer': 'under'}})
    U = e.uniforms['aeropittura']
    AP.apply_look(U, AP.LOOKS[plan['look']], 1.0, frame=1)
    if plan.get('palette') is not None:
        U['palette'].default_value = float(plan['palette'])
        U['palette'].keyframe_insert('default_value', frame=1)
    AP.set_planes(U, AP.PLANES[plan['planes']], frame=1)
    e.cut(*[sh[0] for sh in shots[1:]])
    for f0, f1, _cam, (_s0, _nm, move) in shots:
        if move.get('read'):
            AP.ease_reading(U, f0, f1, 0.6, 0.45, fps=fps)
    step = max(1, int(A['step']))
    bad, behind = 0, 0
    for f in list(range(1, f_last + 1, step)) + [f_last]:
        scene.frame_set(f)
        cam = scene.camera
        t = plan['t0'] + (f - 1) / fps
        # the focal as the film resolved it: three's project() (a perspective divide, mirrored when the idol is
        # behind the camera, as on the essay and crate shots), used whenever it is finite, else (0.5, 0.42).
        # world_to_camera_view is the same divide.
        co = world_to_camera_view(scene, cam, s.focal.matrix_world.translation)
        uv = (co.x, 1.0 - co.y)
        behind += co.z <= 0
        if not all(math.isfinite(v) for v in uv):
            uv, bad = (0.5, 0.42), bad + 1
        AP.set_focal(U, *uv, frame=f)
        U['spin'].default_value = t * 0.03
        U['spin'].keyframe_insert('default_value', frame=f)
        if h is not None:
            head = h.arm.matrix_world @ h.pb('head').head + Vector((0, 0, 0.12))
            co = world_to_camera_view(scene, cam, head)
            dist = (cam.matrix_world.translation - head).length
            seen = co.z > 0 and not h.arm.hide_render              # the conductor: vrm.scene.visible && in front
            r = min(1.0, max(0.0, 0.55 / max(0.6, dist))) * 0.9 if seen else 0.0
            AP.set_spare(U, co.x, 1.0 - co.y, r, frame=f)
    return U, bad, behind


def render(scene, path, plain=False):
    scene.render.use_compositing = not plain
    scene.render.filepath = path
    tr = time.perf_counter()
    bpy.ops.render.render(write_still=True)
    return time.perf_counter() - tr


def section(name, build, mark, parent_of=None, update_kw=None):
    plan = PLANS[A['plan']][name]
    fps = int(A['fps'])
    sc = new_scene(f'{A["plan"]}_{name}', fps)
    W, H = (int(v) for v in A['res'].split('x'))
    tb = time.perf_counter()
    s = build(sc)
    T.render_setup(sc, (W, H), int(A['samples']), bloom=True,
                   bloom_opts=T.FILM_BLOOM if A['plan'] == 'film' else T.PROBE_BLOOM)
    sc.world = s.env
    s.eevee_settings(sc)
    h = singer(s, mark, parent=parent_of(s) if parent_of else None)
    T.check(f'{A["plan"]}/{name}: set built, singer at her mark', True, f'{time.perf_counter() - tb:.1f} s')
    f_of = lambda t: 1 + int(round((t - plan['t0']) * fps))                       # noqa: E731
    n = f_of(plan['t1']) - 1
    sc.frame_start, sc.frame_end = 1, n
    tk = time.perf_counter()
    shots = shot_cameras(sc, s, plan, f_of)
    if h is not None and plan.get('hidden_on'):
        obs = key_singer_visibility(h, shots, plan['hidden_on'])
        wrong = []
        for f0, f1, _cam, (_s0, nm, _m) in shots:
            sc.frame_set((f0 + f1) // 2)
            if any(o.hide_render != (nm in plan['hidden_on']) for o in obs):
                wrong.append(nm)
        T.check(f'{A["plan"]}/{name}: the singer hidden on {", ".join(plan["hidden_on"])} and shown on the other '
                'shots, as the conductor does (keyed at the cuts)', not wrong, f'{len(obs)} objects; wrong on {wrong}')
    for f in range(1, n + 1):
        t = plan['t0'] + (f - 1) / fps
        kw = update_kw(shot_at(shots, f)[2]) if update_kw else {}
        s.update(t, plan['state'](t), frame=f, **kw)
    T.check(f'{A["plan"]}/{name}: {n} frames keyed ({plan["t0"]}-{plan["t1"]} s at {fps} fps), {len(shots)} shots '
            'with their moves', True, f'{time.perf_counter() - tk:.2f} s')
    # read back: the song clock uT and the state the set keyed, at frames across the section
    worst = 0.0
    for f in (1, n // 3, (2 * n) // 3, n):
        sc.frame_set(f)
        t = plan['t0'] + (f - 1) / fps
        worst = max(worst, abs(s.root['uT'] - t))
        st = plan['state'](t)
        if 'spin' in st:
            worst = max(worst, abs(s.parts['turntable']['platter'].rotation_euler.z - st['spin']))
        if 'sale' in st:
            worst = max(worst, abs(s.root['uSale'] - min(1.0, max(0.0, st['sale']))))
    T.check(f'{A["plan"]}/{name}: the keys read back (uT, and spin or sale) at 4 frames', worst < 1e-3,
            f'worst {worst:.2e}')
    # every shot's camera is on at its cut and only there
    wrong = []
    for f0, f1, cam, row in shots:
        for f in (f0, (f0 + f1) // 2, f1):
            sc.frame_set(f)
            if sc.camera is not cam:
                wrong.append((row[1], f))
    T.check(f'{A["plan"]}/{name}: the markers cut to each shot camera on its frames', not wrong, f'{wrong[:4]}')
    # the moves: each shot camera at its last frame where camPose puts it
    devs = []
    for f0, f1, cam, (s0, nm, move) in shots:
        sc.frame_set(f1)
        t = plan['t0'] + (f1 - 1) / fps
        nxt = [r[0] for r in plan['shots'] if r[0] > s0]
        u = (t - s0) / ((nxt[0] if nxt else plan['t1']) - s0)
        pos, _tgt, _ = cam_pose(s['cams_three'][nm], u, move)
        want = s.root.matrix_world @ Vector(L.to_blender(pos))
        devs.append((cam.matrix_world.translation - want).length)
    T.check(f'{A["plan"]}/{name}: shot cameras on their keyed paths (end of each shot)', max(devs) < 1e-4,
            f'worst {max(devs):.2e} m')
    if not A['no_render']:
        tb = time.perf_counter()
        s.bake_probes(sc)
        T.check(f'{A["plan"]}/{name}: probe baked', True, f'{time.perf_counter() - tb:.1f} s')
    U = None
    if plan.get('look') and not A['no_look']:
        U, bad, behind = look_keys(sc, s, plan, shots, h, fps, n)
        T.check(f'{A["plan"]}/{name}: the {plan["look"]} look keyed (planes {plan["planes"]}, focal on the idol, '
                'her face spared, reading shots); the focal finite on every keyed frame', bad == 0,
                f'{bad} non-finite; behind the camera (mirrored, as three projects it) on {behind}')
    outs = []
    if A['no_render']:
        return outs
    first_plain = None
    for t in plan['stills']:
        f = f_of(t)
        sc.frame_set(f)
        nm = shot_at(shots, f)[3][1]
        base = os.path.join(OUT, f'{A["plan"]}_{name}_{nm}_t{t:.1f}')
        todo = []
        if U is not None:
            todo.append((base + '.png', False))
        if U is None or not A['no_plain']:
            todo.append((base + ('_plain' if U is not None else '') + '.png', True))
        for path, plain in todo:
            dt = render(sc, path, plain)
            mean, clip, _b = T.stats(path)
            T.check(f'{os.path.basename(path)}: rendered from the keys (frame {f}, cam {nm})',
                    os.path.isfile(path) and 0.02 < mean < 0.7, f'mean {mean:.3f}, clipped {100 * clip:.1f} %, '
                    f'{dt:.1f} s')
            outs.append(path)
            if plain and first_plain is None:
                first_plain = (f, path)
    if A['save'] and first_plain:
        blend = os.path.join(OUT, f'{A["plan"]}_{name}.blend')
        bpy.ops.wm.save_as_mainfile(filepath=blend, compress=True)
        mb = os.path.getsize(blend) / 2 ** 20
        bpy.ops.wm.open_mainfile(filepath=blend)
        sc2 = bpy.context.scene
        f, ref = first_plain
        sc2.frame_set(f)
        p2 = ref.replace('.png', '_reloaded.png')
        render(sc2, p2, plain=True)
        from PIL import Image
        a = np.asarray(Image.open(ref).convert('RGB'), np.float32)
        b = np.asarray(Image.open(p2).convert('RGB'), np.float32)
        mad = float(np.abs(a - b).mean())
        T.check(f'{A["plan"]}/{name}: the saved .blend plays on its own (frame {f} re-rendered from the file)',
                mad < 2.0, f'mean |dRGB| {mad:.2f} / 255, {mb:.0f} MB')
        if not A['keep_blend']:
            os.remove(blend)
            os.remove(p2)
    return outs


def main():
    outs = []
    if A['set'] in ('quiet_room', 'both'):
        outs += section('quiet_room', lambda sc: QR.build(sc, art_cache=T.ART, probe_spacing=0.5, probe_samples=512),
                        QR.MARK)
    if A['set'] in ('showroom', 'both'):
        on_platter = PLANS[A['plan']]['showroom'].get('on_platter', True)
        outs += section('showroom', lambda sc: SR.build(sc, art_cache=T.ART, probe_spacing=0.6, probe_samples=512),
                        SR.MARK, parent_of=(lambda s: s.parts['turntable']['platter']) if on_platter else None,
                        update_kw=lambda cam: {'camera': cam})
    if outs:
        T.sheet(outs, os.path.join(OUT, f'{A["plan"]}_sheet.jpg'), cols=4)
    return T.done()


if __name__ == '__main__':
    rc = main()
    sys.stdout.flush()
    if rc:
        sys.exit(rc)
