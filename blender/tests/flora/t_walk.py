"""t_walk.py: pushers part the meadow round a walking body. Claude's robot body (eidoverse/assets/vrms/
claude_robot_2k.vrm) plays walk.vrma (an in-place cycle) while its armature object travels at the speed its planted
foot slides back, so the feet stay put on the ground; its feet and hips are the pushers. Renders frames with the
pushers on and the same frames with them off.
    bash run_blender.sh blender/tests/flora/t_walk.py [--frames 30,42] [--off] [--res 960x540] [--seq out_dir]
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import _scene as S  # noqa: E402

import bpy  # noqa: E402
import numpy as np  # noqa: E402
from eidoblend.flora import create_flora, reset_flora_occupancy  # noqa: E402

ASSETS = os.path.join(S.WORKTREE, 'eidoverse', 'assets')
res = tuple(int(x) for x in S.arg('--res', '960x540').split('x'))
sc = S.new_scene(res, samples=16)
S.lights(sun_elev_deg=36, sun_az_deg=-35, strength=4.5, sky_strength=0.7, gradient=True)
S.ground()
reset_flora_occupancy()
fields = [
    create_flora('grass', size=14, seed=3, height=0.42, blades='fine'),
    create_flora('grass', size=9, seed=17, center=(0.8, 0.5), density=0.5, height=0.55, blades='fine'),
    create_flora('daisy', size=8, seed=5, center=(0.3, 0.4), density=0.5, color='white'),
    create_flora('daisy', size=6, seed=29, center=(-0.8, 1.0), density=0.4, color='orange'),
]

# the body and its walk
bpy.ops.preferences.addon_enable(module='bl_ext.blender_org.vrm')
bpy.ops.import_scene.vrm(filepath=os.path.join(ASSETS, 'vrms', 'claude_robot_2k.vrm'))
arm = next(o for o in bpy.data.objects if o.type == 'ARMATURE')
bpy.context.view_layer.objects.active = arm
bpy.ops.import_scene.vrma(filepath=os.path.join(ASSETS, 'animations', 'walk.vrma'), armature_object_name=arm.name)
hb = arm.data.vrm_addon_extension.vrm1.humanoid.human_bones
B = {k: getattr(hb, k).node.bone_name for k in ('hips', 'left_foot', 'right_foot')}
ad = arm.animation_data
act = ad.action
f0, f1 = (int(x) for x in act.frame_range)
cyc = f1 - f0
# the stance: frames where the left foot is lowest; its backward slide there is the body's walking speed
ys, zs = [], []
for f in range(f0, f1 + 1):
    sc.frame_set(f)
    p = arm.matrix_world @ arm.pose.bones[B['left_foot']].head
    ys.append(p.y)
    zs.append(p.z)
ys, zs = np.array(ys), np.array(zs)
low = zs < zs.min() + 0.01
vy = np.gradient(ys)[low].mean() * sc.render.fps          # m/s of the planted foot, relative to the body
speed = -vy
print(f'[walk] cycle {cyc} frames, planted-foot slide {vy:.3f} m/s -> body speed {speed:.3f} m/s along +y')
# loop the clip through the NLA for the whole shot
track = ad.nla_tracks.new()
strip = track.strips.new('walk', f0, act)
strip.repeat = 6
ad.action = None
# travel along +y through the stand, the hips passing the origin at frame 36
sc.frame_start, sc.frame_end = 1, 72
bpy.context.preferences.edit.keyframe_new_interpolation_type = 'LINEAR'
for f in (1, 72):
    arm.location = (0.0, speed * (f - 36) / sc.render.fps, 0.0)
    arm.keyframe_insert('location', frame=f)
if speed < 0:
    print('[walk] WARNING: the clip walks toward -y')

pushers = fields[0].set_pushers([(arm, B['left_foot'], 0.32), (arm, B['right_foot'], 0.32), (arm, B['hips'], 0.42)])
cam = S.camera((2.3, -1.2, 0.75), (0.0, 0.2, 0.45), 30)
if S.arg('--seq'):
    out = S.arg('--seq')
    os.makedirs(out, exist_ok=True)
    for f in range(int(S.arg('--from', '12')), int(S.arg('--to', '60')) + 1):
        S.render(os.path.join(out, f'{f:04d}.png'), f)
else:
    frames = [int(x) for x in S.arg('--frames', '30,42').split(',')]
    for f in frames:
        S.render(os.path.join(S.OUT, f'walk_push_f{f}.png'), f)
    if '--blur' in S.args():
        # EEVEE motion blur: the wind and the parting blades smear only if the deformation reaches its velocity
        sc.render.use_motion_blur = True
        sc.render.motion_blur_shutter = 1.0
        S.render(os.path.join(S.OUT, f'walk_blur_f{frames[0]}.png'), frames[0])
        sc.render.use_motion_blur = False
    if '--off' in S.args():
        for p in pushers:
            bpy.data.objects.remove(p)
        for f in frames:
            S.render(os.path.join(S.OUT, f'walk_nopush_f{f}.png'), f)
bpy.ops.wm.save_as_mainfile(filepath=os.path.join(S.OUT, 'walk.blend'))
print('[walk] done')
