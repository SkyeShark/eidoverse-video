"""tests/harness/test_swept_clearance.py: the runner's motion.swept_clearance (harness/audits.py), on the T18 scene
(blender/tests/pipeline/swept/scene.py) built here and audited directly, without the runner (Blender, no render):

    rotor_B   sunk in its drum            WARN: sits inside 'mount_B' at every one of the 12 angles of its revolution
    rotor_C   blade tips in the cabinet   WARN: sweeps through 'cabinet_C' at some of the 12 angles, not all
    rotor_A   clear of its can            nothing
    radar     scans +-40 degrees          nothing (the pole stands where the bar would point at 90 degrees)
    control   the same radar turning a whole revolution, ending where it began (a turntable keyed 0 -> 360 degrees):
              WARN, it sweeps through 'pole_D' (the spin axis found from the sample turned furthest, not the last)

    bash run_blender.sh blender/tests/harness/test_swept_clearance.py
"""
import importlib.util
import os
import sys
import time
import traceback

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.normpath(os.path.join(HERE, '..', '..', '..'))
sys.path.insert(0, os.path.join(REPO, 'blender'))
sys.dont_write_bytecode = True

import bpy  # noqa: E402

from eidoblend.harness import audits, ledger as L  # noqa: E402

spec = importlib.util.spec_from_file_location('swept_scene', os.path.join(REPO, 'blender', 'tests', 'pipeline',
                                                                          'swept', 'scene.py'))
T18 = importlib.util.module_from_spec(spec)
spec.loader.exec_module(T18)
FAIL = []


def check(ok, what):
    print(f"[swept] {'PASS' if ok else 'FAIL'}: {what}", flush=True)
    if not ok:
        FAIL.append(what)


def key(ob, path, frame):
    ob.keyframe_insert(path, frame=frame)


def audit(radar_turns=False):
    bpy.ops.wm.read_homefile(use_empty=True)
    bpy.context.preferences.edit.keyframe_new_interpolation_type = 'LINEAR'   # the runner makes ctx.key's keys LINEAR
    sc = bpy.context.scene
    sc.render.fps, sc.render.fps_base = 24, 1.0
    sc.frame_start, sc.frame_end = 1, 48
    T18.build(sc, 1, 48, key, radar_turns=radar_turns)
    led = L.Ledger()
    t0 = time.perf_counter()
    audits.motion(led, sc, {'fps': 24, 'duration': 2.0}, L.snapshot_policy({}))
    dt = time.perf_counter() - t0
    recs = led.records
    for r in recs:
        if r['check'].startswith('motion.swept') or r['outcome'] != 'PASS':
            print(f"  {r['outcome']} {r['check']}: {r['message'][:220]}", flush=True)
    return recs, dt


def warns_for(recs, name):
    return [r for r in recs if r['check'] == 'motion.swept_clearance' and r['outcome'] == 'WARN'
            and r['bodies'] and r['bodies'][0] == name]


def main():
    recs, dt = audit()
    sk = [r for r in recs if r['outcome'] == 'SKIPPED']
    check(not sk, f'no check of the motion family failed: {[(r["check"], r["message"][:120]) for r in sk]}')
    b = warns_for(recs, 'rotor_B')
    check(len(b) == 1 and b[0]['bodies'] == ['rotor_B', 'mount_B'] and 'sits inside' in b[0]['message']
          and b[0]['metrics']['angles_hit'] == b[0]['metrics']['angles'] == 12 and b[0]['metrics']['full_revolution'],
          'rotor_B, sunk in its drum, sits inside mount_B at all 12 angles of its revolution: '
          + (f"{b[0]['metrics']}" if b else 'no record'))
    c = warns_for(recs, 'rotor_C')
    check(len(c) == 1 and c[0]['bodies'] == ['rotor_C', 'cabinet_C'] and 'sweeps through' in c[0]['message']
          and 0 < c[0]['metrics']['angles_hit'] < 12,
          'rotor_C sweeps through cabinet_C at some of its 12 angles, not all: '
          + (f"{c[0]['metrics']}" if c else 'no record'))
    check(not warns_for(recs, 'rotor_A'), 'rotor_A, 2.5 cm clear of its can, is not named')
    check(not warns_for(recs, 'radar'), 'the radar scanning +-40 degrees is not named (the pole is at 90 degrees)')
    env = [r for r in recs if r['check'] == 'motion.envelope' and r['outcome'] == 'WARN']
    check(not env, 'the rotors and the radar turn about their own centres: no wrong-pivot warning '
          + str([r['message'][:80] for r in env]))
    check(dt < 20.0, f'the motion audits took {dt:.1f} s on 48 frames and 4 turning parts')
    recs2, _dt = audit(radar_turns=True)
    r = warns_for(recs2, 'radar')
    check(len(r) == 1 and r[0]['bodies'] == ['radar', 'pole_D'] and r[0]['metrics']['full_revolution']
          and 0 < r[0]['metrics']['angles_hit'] < 12,
          'control: the radar turning a whole revolution (ending where it began) sweeps through pole_D: '
          + (f"{r[0]['metrics']}" if r else 'no record'))


if __name__ == '__main__':
    try:
        main()
    except Exception:                                                # noqa: BLE001
        traceback.print_exc()
        FAIL.append('raised')
    print(f"[swept] {'ALL PASS' if not FAIL else f'{len(FAIL)} FAIL'}", flush=True)
    sys.stdout.flush()
    os._exit(1 if FAIL else 0)
