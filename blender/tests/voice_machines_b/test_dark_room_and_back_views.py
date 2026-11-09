"""The machines by their own light, and the views the other probes do not take: the Voder from behind; the Voder, the
Speak & Spell and the 7090 console in a dark room lit by their own glow (grille, pilot, dial, VFD, lamps), voice on
and then power off (the lights dying); the tandem from its left (non-drive) side at speed, where the spoke smear's
normal must lean to the axle on the wire's own side (tandem.js's NaN-sparkle guard).

    cd <main checkout> && bash run_blender.sh <worktree>/blender/tests/voice_machines_b/test_dark_room_and_back_views.py
    HEAVY_VRAM_GB=4 bash work/claude_body/work/tmp/heavy.sh 12 bash run_blender.sh <this> --render             # stills

The checks (PASS / FAIL) run without --render too; the luminance checks read the stills, so they need --render.
"""
import math
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import _stage as S  # noqa: E402

import bpy  # noqa: E402


def dark_scene(frames=(1, 48)):
    """an unlit museum at night: a near-black world and one faint cool fill far off"""
    sc = S.fresh_scene(frames=frames)
    bg = sc.world.node_tree.nodes['Background']
    bg.inputs['Color'].default_value = (0.0025, 0.0028, 0.0035, 1)
    S.floor(sc, 14.0, color=(0.12, 0.115, 0.11), rough=0.45)
    S.wall(sc, y=2.4, width=14.0, height=4.5, color=(0.22, 0.21, 0.2))
    S.area(sc, (-3.0, -4.0, 3.5), (0.0, 0.0, 0.8), 6.0, size=3.0, color=(0.75, 0.82, 1.0), name='night_fill')
    return sc


def lum_stats(path):
    """(mean Rec.709 luma, fraction of pixels brighter than 0.4) of a still, display-referred 0..1: the glow of a lamp,
    a tube or a backlit cloth shows as bright pixels that a dark room otherwise lacks"""
    import numpy as np
    from PIL import Image
    a = np.asarray(Image.open(path).convert('RGB'), np.float32) / 255.0
    y = a @ np.array([0.2126, 0.7152, 0.0722], np.float32)
    return float(y.mean()), float((y > 0.4).mean())


def glow_check(tag, p_on, p_off, what):
    (m_on, b_on), (m_off, b_off) = lum_stats(p_on), lum_stats(p_off)
    S.check(f'dark room: {what}', b_on > 0.0005 and b_on > 5 * b_off and m_on > m_off,
            f'{tag}: bright pixels {b_on * 100:.2f} % on, {b_off * 100:.3f} % off; mean luma {m_on:.4f} / {m_off:.4f}')


def voder_views(render):
    sc = dark_scene(frames=(1, 40))
    from eidoblend.props.voice_machines import voder as V
    vo = V.build()
    for f in range(1, 41):
        t = vo.time_at(f)
        st = {'voice': 0.85 + 0.15 * math.sin(t * 9.0), 'power': 1.0} if f <= 30 else {'voice': 0.0, 'power': 0.0}
        vo.update(t, st, frame=f)
    sc.frame_set(20)
    on = (vo.group['power'], vo.group['level'])
    sc.frame_set(40)
    off = (vo.group['power'], vo.group['level'])
    S.check('dark room: the Voder sings at frame 20 (power 1, level up) and is dark at frame 40 (keyed)',
            on[0] == 1.0 and on[1] > 0.6 and off == (0.0, 0.0), f'f20 {on}, f40 {off}')
    if not render:
        return
    cam = S.camera(sc, (1.25, -2.35, 1.45), (0.0, 0.3, 0.95), lens=35)
    p_on, p_off = S.OUT / 'voder_dark_room_voice_f020.png', S.OUT / 'voder_dark_room_power_off_f040.png'
    S.render(p_on, frame=20)
    S.render(p_off, frame=40)
    glow_check('voder', p_on, p_off, 'the Voder glows while it sings (grille cloth, dial, pilot jewel), dark when off')
    # from behind, lit: the back of the console and the tower (closed shells, nothing missing or see-through). The
    # camera stands where the back wall was: the wall goes, so the shot sees the machine and not the wall's back
    wall = bpy.data.objects['wall']
    wall.hide_render = wall.hide_viewport = True
    S.studio(sc, (0.0, 0.3, 0.9), dist=3.0, key=600)
    S.look_from(cam, (-1.55, 3.05, 1.6), (0.0, 0.35, 0.85), lens=32)
    sc.frame_set(20)
    dg = bpy.context.evaluated_depsgraph_get()
    own = {o.name for o in vo.group.children_recursive}
    seen = []
    for target in ((0.0, 0.35, 0.85), (0.0, 0.62, 1.45), (0.3, 0.1, 0.45)):        # console, tower, a leg
        d = (S.Vector(target) - cam.location).normalized()
        ok, _loc, _n, _i, ob, _m = sc.ray_cast(dg, cam.location, d)
        seen.append(ob.name if ok and ob else None)
    S.check('voder back view: the camera sees the machine (the first hit toward the console, tower and leg is the '
            "Voder's own)", all(s in own for s in seen), str(seen))
    S.render(S.OUT / 'voder_back_left_lit_f020.png', frame=20)


def speakspell_view(render):
    sc = dark_scene(frames=(1, 24))
    from eidoblend.props.voice_machines import speakspell as SS
    ss = SS.build(text='daisy', screen_dir=str(S.OUT / 'dark_room_screens'))
    for f in range(1, 25):
        t = (f - sc.frame_start) / 24.0
        ss.update(t, {'power': 1.0 if f <= 16 else 0.0, 'voice': 0.5 + 0.5 * math.sin(t * 14.0)}, frame=f)
    sc.frame_set(12)
    on = (ss.group['power'], ss.group['speaker'])
    sc.frame_set(20)
    off = (ss.group['power'], ss.group['speaker'])
    S.check('dark room: the Speak & Spell VFD is lit and the grille glows at frame 12, dark at frame 20 (keyed)',
            on[0] == 1.0 and on[1] > 0.05 and off == (0.0, 0.0), f'f12 power, speaker {on}; f20 {off}')
    if not render:
        return
    S.camera(sc, (0.18, -0.5, 0.24), (0.0, 0.0, 0.14), lens=40)
    p_on, p_off = S.OUT / 'speakspell_dark_room_voice_f012.png', S.OUT / 'speakspell_dark_room_power_off_f020.png'
    S.render(p_on, frame=12)
    S.render(p_off, frame=20)
    glow_check('speakspell', p_on, p_off, 'the VFD and the grille glow while the toy speaks, dark when off')
    ss.dispose(files=True)


def mainframe_view(render):
    sc = dark_scene(frames=(1, 48))
    from eidoblend.props.voice_machines import mainframe as MF
    room = MF.build()
    room.animate(lambda t: {'tape_speed': 1.0, 'voice': 0.6, 'power': 1.0 if t < 40 / 24 else 0.0}, frames=(1, 48))
    sc.frame_set(40)
    p40 = room.group['power']
    sc.frame_set(44)
    p44 = room.group['power']
    S.check('dark room: the 7090 room is powered at frame 40 and dark at frame 44 (keyed)', p40 == 1.0 and p44 == 0.0,
            f'{p40} -> {p44}')
    if not render:
        return
    con = room.parts['console'].matrix_world.translation
    S.camera(sc, (con.x - 0.55, con.y - 1.35, 1.55), (con.x - 0.05, con.y + 0.05, 1.05), lens=35)
    p_on, p_off = S.OUT / 'mainframe_dark_room_lamps_f040.png', S.OUT / 'mainframe_dark_room_power_off_f044.png'
    S.render(p_on, frame=40)
    S.render(p_off, frame=44)
    glow_check('mainframe', p_on, p_off, 'the lamp field and the drive lenses glow, nothing glows with the power off')


def tandem_left_side(render):
    sc = S.fresh_scene(frames=(1, 30))
    S.floor(sc, 16.0)
    S.wall(sc, y=-3.5, width=16.0, height=5.0)               # behind the bike, seen from its left (+Y) side
    from eidoblend.props import tandem as TD
    bike = TD.build()
    for f in range(1, 31):
        bike.update(bike.time_at(f), {'speed': 4.5}, frame=f)
    sc.frame_set(30)
    S.check('tandem left side: the spoke smear is on at speed (sweep keyed, smear switched on)',
            abs(bike.group['sweep']) > 0.05 and bike.group['spoke_smear'] == 1.0, f"sweep {bike.group['sweep']:.3f}")
    if not render:
        return
    S.studio(sc, (0.0, 0.0, 0.6), dist=3.4, key=380)
    for o in [o for o in bpy.data.objects if o.type == 'LIGHT']:   # the studio's key on the camera side (+Y)
        o.location.y = -o.location.y
        S.look_at(o, (0.0, 0.0, 0.6))
    cam = S.camera(sc, (0.35, 4.3, 0.85), (0.0, 0.0, 0.55), lens=40)
    S.render(S.OUT / 'tandem_left_side_spoke_smear_f030.png', frame=30)
    S.look_from(cam, (-0.95, 1.35, 0.55), (-0.82, 0.0, 0.36), lens=45)
    S.render(S.OUT / 'tandem_left_rear_wheel_spoke_smear_f030.png', frame=30)


def run(render=False):
    for fn in (voder_views, speakspell_view, mainframe_view, tandem_left_side):
        fn(render)
    return S


if __name__ == '__main__':
    run(render='--render' in sys.argv)
    sys.exit(1 if S.summary('dark_room_and_back_views') else 0)
