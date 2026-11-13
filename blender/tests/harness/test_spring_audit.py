"""tests/harness/test_spring_audit.py: the runner's motion.springs record (harness/audits.py), on Aletheia's VRM (hair and
cat tails: spring chains) and my robot body's (none), audited directly with audits.motion, without the runner (Blender,
no render):

    unbaked             Aletheia's chains, nothing keying them           WARN (REVIEW): N spring chains and no baked
                                                                         springs track, her hair and tails will not move
    baked               characters.springs.bake_springs over the frames  PASS (INFO): baked on 'aletheia|springs'
    track muted         the springs track muted                          WARN again: a muted track plays nothing
    renamed             the armature renamed after the bake              PASS: the track found by its '|springs' name
    keyed by hand       the bake removed, one spring bone keyed          PASS (INFO): keyed on 1 of its spring bones
    hidden              her meshes kept out of the render                no record
    no chains           my robot body                                    no record

    cd C:/Users/sdn52/OneDrive/Desktop/eidoverse-video-prealpha-0.01
    bash run_blender.sh <worktree>/blender/tests/harness/test_spring_audit.py
"""
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.normpath(os.path.join(HERE, '..', '..', '..'))
sys.path.insert(0, os.path.join(REPO, 'blender'))
sys.dont_write_bytecode = True

import bpy  # noqa: E402

from eidoblend.characters import load_vrm, springs as SP  # noqa: E402
from eidoblend.harness import audits, ledger as L  # noqa: E402

FAIL = []


def check(ok, what):
    print(f"[springs-audit] {'PASS' if ok else 'FAIL'}: {what}", flush=True)
    if not ok:
        FAIL.append(what)


def springs_records(sc):
    led = L.Ledger()
    audits.motion(led, sc, {'fps': 24}, L.snapshot_policy({}))
    recs = led.records
    bad = [r for r in recs if r['outcome'] == 'SKIPPED' and r['check'].startswith('motion')]
    if bad:
        print('  SKIPPED:', [(r['check'], r['message'][:200]) for r in bad], flush=True)
    out = [r for r in recs if r['check'] == 'motion.springs']
    for r in out:
        print(f"  {r['outcome']} {r['class']} {r['bodies']}: {r['message']}  {r['metrics']}", flush=True)
    return out, bad


def main():
    bpy.ops.wm.read_homefile(use_empty=True)
    sc = bpy.context.scene
    sc.render.fps, sc.render.fps_base = 24, 1.0
    sc.frame_start, sc.frame_end = 1, 12
    her = load_vrm('aletheia', location=(0.0, 0.0, 0.0))
    bot = load_vrm('claude_robot_2k', name='robot', location=(2.0, 0.0, 0.0))
    chains = sum(1 for s in her.arm.data.vrm_addon_extension.spring_bone1.springs
                 if any(j.node.bone_name for j in list(s.joints)[:-1]))
    print(f'[springs-audit] aletheia: {chains} spring chains, {len(SP.spring_bones(her))} spring bones; '
          f'the robot: {len(bot.arm.data.vrm_addon_extension.spring_bone1.springs)} springs', flush=True)

    recs, bad = springs_records(sc)
    w = [r for r in recs if r['bodies'] == ['aletheia']]
    check(not bad and len(w) == 1 and w[0]['outcome'] == 'WARN' and w[0]['class'] == 'REVIEW'
          and w[0]['metrics']['chains'] == chains and chains > 0
          and w[0]['message'] == (f"VRM 'aletheia': {chains} spring chains and no baked springs track: its hair and "
                                  'tails will not move; Locomotion.bake bakes them by default, '
                                  'characters.springs.bake_springs for a hand-keyed body'),
          f"unbaked: one REVIEW for Aletheia's {chains} chains, worded as the guide has it")
    check(not [r for r in recs if r['bodies'] == ['robot']], 'my robot body has no spring chains: no record')

    rep = SP.bake_springs(her, 1, 12, preroll=0.25)
    recs, bad = springs_records(sc)
    w = [r for r in recs if r['bodies'] == ['aletheia']]
    check(not bad and len(w) == 1 and w[0]['outcome'] == 'PASS' and w[0]['class'] == 'INFO'
          and w[0]['metrics']['track'] == 'aletheia|springs' and 'aletheia|springs' in w[0]['message'],
          f"baked by bake_springs ({rep['keys']} keys): PASS, baked on its track")

    tr = SP.spring_track(her)
    tr.mute = True
    recs, _bad = springs_records(sc)
    w = [r for r in recs if r['bodies'] == ['aletheia']]
    check(len(w) == 1 and w[0]['outcome'] == 'WARN', 'the springs track muted: WARN again (a muted track plays nothing)')
    tr.mute = False

    her.arm.name = 'aletheia_take2'
    recs, _bad = springs_records(sc)
    w = [r for r in recs if r['bodies'] == ['aletheia_take2']]
    check(len(w) == 1 and w[0]['outcome'] == 'PASS' and w[0]['metrics']['track'] == 'aletheia|springs',
          "renamed after the bake: the track still found by its '|springs' name (PASS)")
    her.arm.name = 'aletheia'

    SP.remove_springs(her)
    b = SP.spring_bones(her)[0]
    pb = her.arm.pose.bones[b]
    pb.rotation_mode = 'QUATERNION'
    for f, w_ in ((1, 1.0), (12, 0.97)):
        pb.rotation_quaternion = (w_, (1 - w_ * w_) ** 0.5, 0.0, 0.0)
        pb.keyframe_insert('rotation_quaternion', frame=f)
    recs, _bad = springs_records(sc)
    w = [r for r in recs if r['bodies'] == ['aletheia']]
    check(SP.spring_track(her) is None and len(w) == 1 and w[0]['outcome'] == 'PASS'
          and w[0]['metrics']['keyed_bones'] == 1 and 'keyed on 1 of its' in w[0]['message'],
          'no track, one spring bone keyed by hand (its active action): PASS, keyed')
    her.arm.animation_data_clear()

    for o in her.meshes:
        o.hide_render = True
    recs, _bad = springs_records(sc)
    check(not recs, 'her meshes kept out of the render: no record for her')
    print(f'[springs-audit] {"FAIL" if FAIL else "PASS"}: {len(FAIL)} failed', flush=True)
    return len(FAIL)


if __name__ == '__main__':
    rc = main()
    sys.stdout.flush()
    if rc:
        sys.exit(1)
