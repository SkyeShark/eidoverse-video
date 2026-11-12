"""Clippy.set_weight (clippy.js setWeight(n, w), keyed): one morph on one frame, over the clip sequencer.

Greeting plays from 0.5 s (frames 13 .. 90 at 24 fps); over it: the eyes shut on frame 30 (blink 1), the whole wire
re-bent into the atom on frame 40 (shapeAtom 1), squash 2 on frame 50 (clamped to 1.25, as three clamps an influence),
a lean on frame 25 set and taken back (w=None), and browUp on frame 300, outside the bake (printed, not keyed). Checks:
the keyed value on each override frame, the sequencer's own value on the frames either side, the step in and out
(CONSTANT: no ramp at frame 29.5 or 30.5), the other keys still LINEAR, the scene's shape key at frames 30 and 31, the
clamp, the take-back, bake()'s report, and an unknown morph name raising. Prints PASS/FAIL lines.

    cd C:/Users/sdn52/OneDrive/Desktop/eidoverse-video-prealpha-0.01
    bash run_blender.sh C:/Users/sdn52/OneDrive/Desktop/eidoverse-video-blender/blender/tests/characters/test_clippy_set_weight.py
    # -- --render: frames 39, 40 and 41 on the studio floor, through the GPU slot (heavy.sh)
    #    -> out/clippy_set_weight_f039.png, _f040.png (the atom, for that frame only), _f041.png
"""

import os
import sys

sys.dont_write_bytecode = True
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import _stage as S  # noqa: E402

import bpy  # noqa: E402

from eidoblend.characters.clippy import make_clippy  # noqa: E402

FPS = 24
FAILS = []


def check(ok, what):
    print(f"{'PASS' if ok else 'FAIL'} {what}", flush=True)
    if not ok:
        FAILS.append(what)


sc = S.clean_scene(FPS)
sc.frame_start, sc.frame_end = 1, 60
clippy = make_clippy(height=1.2)
clippy.play('Greeting', 0.5)
clippy.set_weight('blink', 1.0, 30)
clippy.set_weight('shapeAtom', 1.0, 40)
clippy.set_weight('squash', 2.0, 50)
clippy.set_weight('lean', -0.5, 25)
clippy.set_weight('lean', None, 25)
clippy.set_weight('browUp', 0.7, 300)
try:
    clippy.set_weight('sneeze', 1.0, 20)
    raised = False
except KeyError:
    raised = True
info = clippy.bake(1, 60)
print('[set_weight] bake', info, flush=True)

sk = clippy.obj.data.shape_keys
fcs = {}
for ly in sk.animation_data.action.layers:
    for st in ly.strips:
        for cb in st.channelbags:
            for fc in cb.fcurves:
                fcs[fc.data_path] = fc


def seq(name, f):
    """The sequencer's own weight at film frame f (what bake keys without an override)."""
    return clippy.state((f - sc.frame_start) / FPS)[0][name]


def curve(name):
    return fcs[f'key_blocks["{name}"].value']


b = curve('blink')
check(abs(b.evaluate(30) - 1.0) < 1e-6 and abs(seq('blink', 30) - 1.0) > 0.5,
      f'blink 1 on frame 30 (the sequencer gives {seq("blink", 30):.3f} there, mid-wave)')
check(abs(b.evaluate(29) - seq('blink', 29)) < 1e-6 and abs(b.evaluate(31) - seq('blink', 31)) < 1e-6,
      f'the sequencer\'s blink on frames 29 and 31 ({b.evaluate(29):.3f}, {b.evaluate(31):.3f})')
check(abs(b.evaluate(29.5) - b.evaluate(29)) < 1e-6 and abs(b.evaluate(30.5) - 1.0) < 1e-6,
      f'it steps in at 30 and out at 31, no ramp (frame 29.5: {b.evaluate(29.5):.3f}, 30.5: {b.evaluate(30.5):.3f})')
wv = curve('wave')
lin = (wv.evaluate(20) + wv.evaluate(21)) / 2
check(abs(wv.evaluate(20) - wv.evaluate(21)) > 0.05 and abs(wv.evaluate(20.5) - lin) < 1e-6,
      f'the other keys stay LINEAR (the wave rising: frame 20 {wv.evaluate(20):.4f}, 20.5 {wv.evaluate(20.5):.4f}, '
      f'21 {wv.evaluate(21):.4f})')
a = curve('shapeAtom')
check(abs(a.evaluate(40) - 1.0) < 1e-6 and abs(a.evaluate(39) - seq('shapeAtom', 39)) < 1e-6
      and abs(a.evaluate(41) - seq('shapeAtom', 41)) < 1e-6, f'shapeAtom 1 on frame 40 only ({a.evaluate(39):.3f}, '
                                                               f'{a.evaluate(40):.3f}, {a.evaluate(41):.3f})')
check(abs(curve('squash').evaluate(50) - 1.25) < 1e-6, f'squash 2 clamped to 1.25 ({curve("squash").evaluate(50):.3f})')
check(abs(curve('lean').evaluate(25) - seq('lean', 25)) < 1e-6 and seq('lean', 25) > 0.1,
      f'a lean set and taken back (w=None): frame 25 keeps the sequencer\'s {seq("lean", 25):.3f}')
bu = curve('browUp')
check(all(abs(bu.evaluate(f) - seq('browUp', f)) < 1e-6 for f in range(1, 61)),
      'browUp keyed as the sequencer gives it everywhere (its override is on frame 300, outside the bake)')
check(info.get('overrides') == [['blink', 30, 1.0], ['shapeAtom', 40, 1.0], ['squash', 50, 1.25]],
      f'bake() reports the overrides it keyed: {info.get("overrides")}')
sc.frame_set(30)
v30 = sk.key_blocks['blink'].value
sc.frame_set(31)
v31 = sk.key_blocks['blink'].value
check(abs(v30 - 1.0) < 1e-6 and abs(v31 - seq('blink', 31)) < 1e-6,
      f'the scene\'s blink shape key reads {v30:.3f} at frame 30 and {v31:.3f} at 31')
check(raised, 'an unknown morph name raises KeyError, naming the morphs')

if '--render' in S.argv():
    S.probe_render(sc)
    S.studio_world(sc, 0.8, background=0x121214)
    S.sun('key', (-2.2, 3.2, 3.0), 0xfff4e8, 2.2, angle_deg=3.0)
    S.sun('rim', (2.5, 2.0, -3.0), 0xdfe8ff, 1.0, angle_deg=3.0)
    S.floor_disc()
    cam = S.camera('cam', 50.0)
    S.aim(cam, (1.35, -4.3, 1.15), (0.0, 0.0, 0.78))
    for f in (39, 40, 41):
        S.still(sc, cam, f, os.path.join(S.OUT, f'clippy_set_weight_f{f:03d}.png'))
print(f'[test_clippy_set_weight] {"ALL OK" if not FAILS else f"{len(FAILS)} FAILED"}', flush=True)
