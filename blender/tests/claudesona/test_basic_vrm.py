"""eidoverse/examples/basic_vrm.js ported (blender/tests/claudesona/basic_vrm/scene.py), built and rendered without the
runner: the scene's own setup(ctx) and render_frame(ctx, t, i), with a ctx that keys as the runner's does (LINEAR),
over the whole film, then stills at 0, 3 and 6 s, for the example's own asset (claude.vrm, basic_vrm.json's
character_vrm), for aletheia and for the claudesona (claude_suit.vrm, as the example loads any VRM: unscaled). The
runner (eido_blender.py render basic_vrm/scene.json) is the way to run it once its keying snapshot reads Blender 5.2's
Geometry Nodes modifiers (see the step report's hooks).

Checks: the camera on the example's orbit at every still (radius 2.5 m, 1.4 m up, aimed at 1.1 m: three's
(cos 0.4t r, 1.4, sin 0.4t r) looking at (0, 1.1, 0)); the idle clip moves the body between stills; the springs and the
fog are in the scene; each still written.

    cd C:/Users/sdn52/OneDrive/Desktop/eidoverse-video-prealpha-0.01
    HEAVY_VRAM_GB=4 bash work/claude_body/work/tmp/heavy.sh 12 bash run_blender.sh \
        C:/Users/sdn52/OneDrive/Desktop/eidoverse-video-blender/blender/tests/claudesona/test_basic_vrm.py
"""

import json
import math
import os
import runpy
import sys
import traceback

sys.dont_write_bytecode = True
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import _stage as S  # noqa: E402

import bpy  # noqa: E402
from mathutils import Vector  # noqa: E402

FPS, DURATION = 30, 8.0
SCENE = os.path.join(S.HERE, 'basic_vrm', 'scene.py')
OUT = os.path.join(S.OUT, 'basic_vrm')


class Ctx:
    """what the scene's hooks read from the runner's ctx, and its key() (LINEAR)"""

    def __init__(self, scene, vrm):
        self.scene, self.fps, self.duration = scene, FPS, DURATION
        self.frame_start, self.frame_end = 1, 1 + int(round(DURATION * FPS))
        self.total_frames = self.frame_end - self.frame_start + 1
        self.assets = {'character_vrm': vrm}
        self._keyed = []

    def frame_at(self, t):
        return self.frame_start + t * self.fps

    def time_at(self, frame):
        return (frame - self.frame_start) / self.fps

    def key(self, target, data_path, index=-1, frame=None, interpolation='LINEAR'):
        f = self.scene.frame_current if frame is None else frame
        target.keyframe_insert(data_path, index=index, frame=f)
        self._keyed.append((target, data_path))

    def linear(self):
        from bpy_extras import anim_utils
        for target in {id(t): t for t, _p in self._keyed}.values():
            ad = target.animation_data
            for slot in (ad.action.slots if ad and ad.action else []):
                cb = anim_utils.action_get_channelbag_for_slot(ad.action, slot)
                for fc in (cb.fcurves if cb else []):
                    for kp in fc.keyframe_points:
                        kp.interpolation = 'LINEAR'


def build(vrm_path, tag, C, R):
    sc = S.clean_scene(FPS)
    from eidoblend.characters import vrma
    vrma._CACHE.clear()
    for w in list(bpy.data.worlds):
        if w.users == 0:
            bpy.data.worlds.remove(w)
    S.probe_render(sc, res=(960, 540), samples=16)
    from eidoblend.look.post import custom_effects as FX
    FX.clear(sc)                                   # apply_to adds to the scene's chain: one fog per build
    ctx = Ctx(sc, vrm_path)
    sc.frame_start, sc.frame_end = ctx.frame_start, ctx.frame_end
    ns = runpy.run_path(SCENE)
    ns['setup'](ctx)
    for f in range(ctx.frame_start, ctx.frame_end + 1):
        sc.frame_set(f)
        ns['render_frame'](ctx, ctx.time_at(f), f - ctx.frame_start)
    ctx.linear()
    arm = next(o for o in sc.objects if o.type == 'ARMATURE')
    hips = next((b for b in arm.pose.bones if b.name.lower() in ('hips', 'j_bip_c_hips')), arm.pose.bones[0])
    os.makedirs(OUT, exist_ok=True)
    cam_err, cam_deg, poses, paths = 0.0, 0.0, [], []
    for t in (0.0, 3.0, 6.0):
        f = int(round(ctx.frame_at(t)))
        sc.frame_set(f)
        a = 0.4 * t
        want = Vector((math.cos(a) * 2.5, -math.sin(a) * 2.5, 1.4))
        cam = sc.camera
        cam_err = max(cam_err, (cam.matrix_world.translation - want).length)
        aim = (Vector((0, 0, 1.1)) - want).normalized()
        look = -(cam.matrix_world.to_3x3() @ Vector((0, 0, 1))).normalized()
        cam_deg = max(cam_deg, math.degrees(look.angle(aim, 0.0)))
        poses.append([round(x, 5) for x in (arm.matrix_world @ arm.pose.bones[hips.name].matrix).to_quaternion()] +
                     [round(x, 5) for x in arm.pose.bones[1].matrix.to_quaternion()])
        p = os.path.join(OUT, f'basic_vrm_{tag}_t{int(t)}.png')
        sc.render.filepath = p
        sc.render.image_settings.media_type = 'IMAGE'
        sc.render.image_settings.file_format = 'PNG'
        bpy.ops.render.render(write_still=True)
        paths.append(p)
    R[tag] = {'stills': paths, 'cam_err_m': cam_err, 'cam_err_deg': cam_deg,
              'tracks': [t.name for t in arm.animation_data.nla_tracks],
              'fog': 'look_depth_fog' in bpy.data.objects}
    C.check(f'{tag}: the camera on the example\'s orbit at 0, 3 and 6 s (2.5 m round, 1.4 m up, aimed at 1.1 m)',
            cam_err < 1e-3 and cam_deg < 0.01, f'{1000 * cam_err:.3f} mm, {cam_deg:.4f} deg')
    C.check(f'{tag}: the idle clip and the baked springs are on the armature; the idle moves the body between stills',
            any(t.startswith('idle') for t in R[tag]['tracks']) and any(t.endswith('|springs') for t in R[tag]['tracks'])
            and len({tuple(p) for p in poses}) > 1, f"{R[tag]['tracks']}")
    C.check(f'{tag}: the depth fog is in the scene and every still is written', R[tag]['fog'] and all(map(os.path.exists, paths)),
            f'{len(paths)} stills')
    return paths


def main():
    R, C = {}, S.Checks('basic_vrm')
    try:
        e = build(os.path.join(S.VRMS, 'claude.vrm'), 'claude', C, R)          # the example's own character_vrm
        a = build(os.path.join(S.VRMS, 'aletheia.vrm'), 'aletheia', C, R)
        c = build(os.path.join(S.VRMS, 'claude_suit.vrm'), 'claudesona', C, R)
        R['sheet'] = S.sheet(e + a + c, os.path.join(OUT, 'basic_vrm_sheet.png'), cols=3)
    except Exception:
        traceback.print_exc()
        R['error'] = traceback.format_exc()
        C.check('ran without an exception', False)
    R['checks'] = C.rows
    R['all_pass'] = C.all_pass and 'error' not in R
    os.makedirs(OUT, exist_ok=True)
    with open(os.path.join(OUT, 'basic_vrm.json'), 'w', encoding='utf-8') as f:
        json.dump(R, f, indent=1, default=str)
    print('[basic_vrm] ALL PASS' if R['all_pass'] else '[basic_vrm] SOME FAILED', flush=True)


main()
