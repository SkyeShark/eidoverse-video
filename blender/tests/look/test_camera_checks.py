"""tests/look/test_camera_checks.py: the camera checks catch what they are for (no render; runs in seconds).

A wall, a ground, a statue-sized subject. Bad shots that each check must flag, and good ones it must pass:
  - a dolly straight through the wall               CameraSafety.check_camera: 'inside' / 'clip' / 'blocked'
  - a camera under the ground                       'inside'
  - a planned path with a key behind the wall       check_path: an issue with a clear suggestion; safe_position
  - a dolly driven by a 3 Hz sin()                  camera_motion_audit: WARN (bounce); a smooth dolly and a
                                                    hand-held camera: PASS
  - a camera 80 m off on a 50 mm lens                framing_audit: WARN (a speck); a close shot: PASS
  - focus on the wrong distance at f/1.4             focus_audit: WARN (soft); a rack that leaves the subject soft
                                                    late in a shot is its own run, not hidden by an allowed start
  - focus in empty air                               focus_audit: camera.focus_sharp WARN (nothing in the picture
                                                    is sharp); the subject in focus: PASS
  - posts scattered by Geometry Nodes on a sightline CameraSafety.exclude(scatter) excludes its instances; the
                                                    same source rendered on its own, or by a second scatter that is
                                                    not excluded, still blocks; a scatter's unrendered source has no
                                                    clearance
  - set_fov / fov_of, three_to_blender, look_at_object, rack focus distances (view depth), point_in_frame,
    track's held height with follow='xy'; CameraSafety.help() names every public method
    bash run_blender.sh blender/tests/look/test_camera_checks.py
"""
import math
import os
import sys

import bpy
from mathutils import Vector

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import fixtures as FX                                       # noqa: E402

from eidoblend.look import camera as C                       # noqa: E402
from eidoblend.look import camera_audit as CA                # noqa: E402
from eidoblend.look.camera_safety import CameraSafety        # noqa: E402

RESULTS = []


def check(name, ok, detail=''):
    RESULTS.append((name, bool(ok), detail))
    print(f"[check] {'PASS' if ok else 'FAIL'} {name}{': ' + str(detail) if detail else ''}", flush=True)


def box(sc, name, centre, size):
    bpy.ops.mesh.primitive_cube_add(size=1.0, location=centre)
    o = bpy.context.object
    o.name = name
    o.scale = size
    bpy.ops.object.transform_apply(location=False, rotation=False, scale=True)    # (all three default to True)
    return o


sc = FX.new_scene(fps=24, frames=(1, 96))
sc.render.resolution_x, sc.render.resolution_y = 1920, 1080
bpy.ops.mesh.primitive_plane_add(size=200, location=(0, 0, 0))
ground = bpy.context.object
ground.name = 'ground'
wall = box(sc, 'wall', (0, 0, 1.5), (6, 0.2, 3))
subject = box(sc, 'subject', (0, -3, 0.9), (0.5, 0.5, 1.8))
tgt = Vector((0, -3, 1.2))

# ---- maths
v = (1.0, 2.0, 3.0)
check('three_to_blender (x,y,z) -> (x,-z,y) and back', tuple(C.blender_to_three(C.three_to_blender(v))) == v
      and tuple(C.three_to_blender(v)) == (1.0, -3.0, 2.0), tuple(C.three_to_blender(v)))
cam = C.make_camera('cam_fov', fov=34, scene=sc)
h, vv = C.fov_of(cam, sc)
check('set_fov 34 deg vertical at 16:9 -> fov_of', abs(vv - 34) < 1e-4 and abs(h - 57.05) < 0.05, f'h {h:.2f} v {vv:.2f} lens {cam.data.lens:.2f}')
sc.render.resolution_x, sc.render.resolution_y = 1080, 1920
C.set_fov(cam, 50, 'horizontal', sc)
h, vv = C.fov_of(cam, sc)
check('set_fov 50 deg horizontal on a portrait frame', abs(h - 50) < 1e-4, f'h {h:.2f} v {vv:.2f}')
sc.render.resolution_x, sc.render.resolution_y = 1920, 1080
cam.location = (3, -8, 2)
bpy.context.view_layer.update()
C.look_at_object(cam, subject, y_bias=0.25)
bpy.context.view_layer.update()
fwd = -(cam.matrix_world.to_3x3() @ Vector((0, 0, 1)))
want = (C.focus_point(subject, 0.25) - cam.matrix_world.translation).normalized()
check('look_at_object aims at the bounds centre raised by y_bias x height', fwd.dot(want) > 0.99999,
      f'focus point {tuple(round(x, 3) for x in C.focus_point(subject, 0.25))}')
dl = C.dof_limits(cam, 4.0)
check('dof_limits sane (near < 4 < far)', dl['near'] < 4.0 < dl['far'], {k: round(v, 3) for k, v in dl.items()})

cs = CameraSafety(sc, padding=0.5, min_distance=0.3)
cs.exclude(subject, sightline_only=True)

# ---- the API reference an agent discovers: every public method named, the gotchas there
ref = CameraSafety.help()
public = sorted(n for n in dir(CameraSafety) if not n.startswith('_') and callable(getattr(CameraSafety, n))
                and n != 'help')
missing = [n for n in public if f'{n}(' not in ref]
check('CameraSafety.help() returns the reference naming every public method', isinstance(ref, str) and not missing
      and 'sightline_only' in ref and 'Common gotchas' in ref, f'{len(public)} methods, missing {missing}')

# ---- a dolly straight through the wall
c1 = C.make_camera('cam_through_wall', fov=40, scene=sc)
C.dolly(sc, c1, (1, 48), (0, 5, 1.5), (0, -1.5, 1.5), tgt, ease_kind='linear')
iss = cs.check_camera(c1, (1, 48), target=tgt)
kinds = {i['kind'] for i in iss}
check('check_camera flags a dolly through a wall', bool(kinds & {'inside', 'clip'}) and 'blocked' in kinds, sorted(kinds))
inside = [i for i in iss if i['kind'] in ('inside', 'clip')]
if inside:
    f0 = inside[0]['frames'][0]
    sc.frame_set(f0)
    y = c1.matrix_world.translation.y
    check('  ... at the frames where the lens meets the wall', abs(y) < 0.4, f"first frame {f0}, camera y {y:.3f}")

# ---- under the ground
c2 = C.make_camera('cam_under', fov=40, scene=sc)
C.hold(sc, c2, (49, 60), (2, -6, -0.4), tgt)
iss = cs.check_camera(c2, (49, 60), target=tgt)
check('check_camera flags a camera under the ground', any(i['kind'] == 'inside' and i['object'] == 'ground' for i in iss),
      [(i['kind'], i['object']) for i in iss])

# ---- a clear shot passes
c3 = C.make_camera('cam_clear', fov=40, scene=sc)
C.dolly(sc, c3, (61, 96), (3, -7, 1.6), (1.5, -6, 1.5), tgt)
iss = cs.check_camera(c3, (61, 96), target=tgt)
check('check_camera passes a clear dolly', not iss, iss)

# ---- planned paths (the WebGPU API)
plan = [{'time': 0, 'position': (2, -7, 1.6), 'target': tuple(tgt)},
        {'time': 2, 'position': (0, 3, 1.6), 'target': tuple(tgt)}]
iss = cs.check_path(plan, samples_per_segment=12)
check('check_path flags a key behind the wall, with a suggestion', any(i['index'] == 1 and i['severity'] == 'blocked'
      and i['suggestion'] for i in iss), [(i['index'], i['severity'], i['suggestion']) for i in iss][:3])
sp = cs.safe_position(Vector((0, 3, 1.6)), tgt)
check('safe_position pulls a blocked camera in front of the wall', sp.y < -0.1 and cs.is_clear(sp, tgt)['clear'],
      tuple(round(x, 2) for x in sp))

# ---- bounce: a sin() dolly, a smooth one, a hand-held one
sc.timeline_markers.clear()
cb = C.make_camera('cam_bounce', fov=40, scene=sc)
fr = C.frames_of((1, 96))
pos = [Vector((3 + 0.3 * math.sin(2 * math.pi * 3 * (f - 1) / 24), -8, 1.6)) for f in fr]
C.key_path(cb, fr, pos, [tgt] * len(fr), scene=sc)
r = CA.camera_motion_audit(sc, cam=cb, span=(1, 96))[0]
check('camera_motion_audit flags a 3 Hz sin() dolly', r['outcome'] == 'WARN', r['metrics'])
cm = C.make_camera('cam_smooth', fov=40, scene=sc)
C.dolly(sc, cm, (1, 96), (3, -9, 1.6), (1, -6, 1.4), tgt)
r = CA.camera_motion_audit(sc, cam=cm, span=(1, 96))[0]
check('camera_motion_audit passes one eased dolly', r['outcome'] == 'PASS', r['metrics'])
ch = C.make_camera('cam_handheld', fov=40, scene=sc)
C.hold(sc, ch, (1, 96), (3, -9, 1.6), tgt, handheld={'deg': 0.3, 'metres': 0.004, 'hz': 0.6, 'seed': 4})
r = CA.camera_motion_audit(sc, cam=ch, span=(1, 96))[0]
sc.frame_set(10)
q10 = ch.matrix_world.to_quaternion()
sc.frame_set(40)
moved = math.degrees(q10.rotation_difference(ch.matrix_world.to_quaternion()).angle)
check('hand-held moves (subtly) and passes the audit', r['outcome'] == 'PASS' and 0.02 < moved < 1.5,
      f'{moved:.3f} deg between frames 10 and 40; {r["metrics"]}')

# ---- framing: a speck, and a close shot (per shot, from markers)
far = C.make_camera('cam_far', lens=50, scene=sc)
C.hold(sc, far, (1, 48), (60, -60, 2), tgt)
near = C.make_camera('cam_near', lens=35, scene=sc)
C.hold(sc, near, (49, 96), (2.0, -6.5, 1.4), tgt)
C.add_shot(sc, 'far', 1, far)
C.add_shot(sc, 'near', 49, near)
recs = CA.framing_audit(sc, subject=subject)
far_r = [x for x in recs if x['metrics']['shot'] == 'far']
near_r = [x for x in recs if x['metrics']['shot'] == 'near']
check('framing_audit flags a speck', far_r and all(x['outcome'] == 'WARN' for x in far_r),
      [x['metrics'].get('coverage') for x in far_r])
check('framing_audit passes a close shot', near_r and all(x['outcome'] == 'PASS' for x in near_r),
      [x['metrics'].get('coverage') for x in near_r])
# the mass-cluster default (no subject named): the 200 m ground is backdrop, the wall + subject the subject
recs = CA.framing_audit(sc, subject=None, frames=[60])
check('framing_audit without a subject finds the mass cluster', all(x['outcome'] in ('PASS', 'WARN') for x in recs),
      [round(x['metrics'].get('coverage', 0), 3) for x in recs])

# ---- focus
def focus_recs(recs, shot, check_name='camera.focus'):
    return [x for x in recs if x['metrics'].get('shot') == shot and x['check'] == check_name]


C.set_dof(near, fstop=1.4)
e = bpy.data.objects.new('wrong_focus', None)
sc.collection.objects.link(e)
e.location = (1.8, -6.0, 1.4)
near.data.dof.focus_object = e
r = focus_recs(CA.focus_audit(sc, tgt, every=12), 'near')
check('focus_audit flags a subject outside the depth of field', any(x['outcome'] == 'WARN' for x in r),
      [x['message'] for x in r])
info = C.focus_on(sc, near, (49, 96), tgt, rack={'to': {'point': (2, -4.5, 1.2)}, 'frames': (60, 80)})
d0 = dict(info['distances'])[49]
d1 = dict(info['distances'])[96]
sc.frame_set(49)
check('focus_on racks from the subject to a nearer point (view depths)', d0 > d1 + 0.5
      and abs(d0 - C.view_depth(near, tgt)) < 1e-3, f'{d0:.2f} m -> {d1:.2f} m')
r = focus_recs(CA.focus_audit(sc, tgt, every=4), 'near')
soft = [x for x in r if x['outcome'] == 'WARN']
check('  ... and focus_audit sees the subject go soft after the rack', soft and soft[0]['metrics']['frames'][0] >= 60,
      [x['message'] for x in r])
# a rack from far to the subject (soft by design at the start, allowed), then away again late in the shot: the late
# softness is its own run and still a WARN
far_pt = Vector((2.0, 2.5, 1.2))
info = C.focus_on(sc, near, (49, 96), {'point': far_pt}, rack={'to': tgt, 'frames': (52, 58)})
fe = bpy.data.objects[info['empty']]
for f in range(84, 97):
    fe.location = tgt.lerp(far_pt, min(1.0, (f - 84) / 6.0))
    fe.keyframe_insert('location', frame=f)
recs = focus_recs(CA.focus_audit(sc, tgt, every=2, allow_soft={'near': (49, 60)}), 'near')
allowed = [x for x in recs if x['outcome'] == 'PASS' and x['class'] == 'INFO']
late = [x for x in recs if x['outcome'] == 'WARN']
check('focus_audit: an allowed soft start is INFO, a late soft run is still a WARN',
      allowed and allowed[0]['metrics']['frames'][1] <= 60 and late and late[0]['metrics']['frames'][0] >= 84,
      [(x['outcome'], x['metrics']['frames']) for x in recs])
# nothing sharp: f/1.4 focused 1 m out in empty air, then on the subject
air = C.make_camera('cam_air', lens=35, fstop=1.4, scene=sc)
C.hold(sc, air, (1, 12), (2.0, -6.5, 1.4), tgt)
sc.frame_set(1)
fwd = -(air.matrix_world.to_3x3() @ Vector((0, 0, 1)))
C.focus_on(sc, air, (1, 12), {'point': air.matrix_world.translation + fwd * 1.0})
r = [x for x in CA.focus_audit(sc, tgt, cam=air, span=(1, 12), every=4) if x['check'] == 'camera.focus_sharp']
check('focus_audit flags a picture with nothing sharp (focus in empty air)', r and r[0]['outcome'] == 'WARN',
      [x['message'] for x in r])
C.focus_on(sc, air, (1, 12), tgt)
r = [x for x in CA.focus_audit(sc, tgt, cam=air, span=(1, 12), every=4) if x['check'] == 'camera.focus_sharp']
check('  ... and passes it focused on the subject', r and r[0]['outcome'] == 'PASS', [x['message'] for x in r])
# point_in_frame: the mark lands where it was picked in the picture
from bpy_extras.object_utils import world_to_camera_view   # noqa: E402
marks = []
for xy in ((0.5, 0.5), (0.25, 0.85), (0.8, 0.3)):
    p = C.point_in_frame(sc, air, xy, frame=1)
    sc.frame_set(1)
    v = world_to_camera_view(sc, air, p) if p is not None else None
    marks.append((xy, None if v is None else (round(v.x, 4), round(1 - v.y, 4))))
check('point_in_frame returns the surface under the picked point', all(v and abs(v[0] - xy[0]) < 1e-3
      and abs(v[1] - xy[1]) < 1e-3 for xy, v in marks), marks)

# ---- track(follow='xy') without height / aim_height: the target's mean height, not the ground
bob = bpy.data.objects.new('bobbing', None)
sc.collection.objects.link(bob)
for f in range(1, 49):
    bob.location = (0.1 * f, -20.0, 1.0 + 0.05 * math.sin(f * 0.8))
    bob.keyframe_insert('location', frame=f)
ct = C.make_camera('cam_track_mean', fov=40, scene=sc)
C.track(sc, ct, (1, 48), bob, offset=(0, -3, 0.5), follow='xy', smooth_s=0.0)
zs, az = [], []
for f in (1, 12, 24, 36, 48):
    sc.frame_set(f)
    zs.append(ct.matrix_world.translation.z)
    d = -(ct.matrix_world.to_3x3() @ Vector((0, 0, 1)))
    az.append(math.degrees(math.asin(max(-1.0, min(1.0, d.z)))))
check("track(follow='xy') holds the target's mean height + offset.z (no bob, not the ground)",
      all(abs(z - 1.5) < 0.02 for z in zs) and max(az) - min(az) < 0.05, f'camera z {[round(z, 3) for z in zs]}, '
      f'pitch {[round(a, 2) for a in az]}')

# ---- Geometry Nodes instances on a sightline (posts 2 m tall, 30 cm square, on x = 20)
src = bpy.data.collections.new('posts_src')
sc.collection.children.link(src)
pm = bpy.data.meshes.new('post')
import bmesh                                                 # noqa: E402
bm = bmesh.new()
bmesh.ops.create_cube(bm, size=1.0)
bmesh.ops.scale(bm, vec=(0.3, 0.3, 2.0), verts=bm.verts)
bmesh.ops.translate(bm, vec=(0, 0, 1.0), verts=bm.verts)
bm.to_mesh(pm)
bm.free()
post = bpy.data.objects.new('post', pm)
post.location = (20, -9.5, 0)                                # where it stands when it renders on its own
src.objects.link(post)
bpy.context.view_layer.layer_collection.children[src.name].exclude = True


def scatter(name, points):
    me = bpy.data.meshes.new(name)
    me.from_pydata(points, [], [])
    ob = bpy.data.objects.new(name, me)
    sc.collection.objects.link(ob)
    ng = bpy.data.node_groups.new(name, 'GeometryNodeTree')
    ng.interface.new_socket('Geometry', in_out='INPUT', socket_type='NodeSocketGeometry')
    ng.interface.new_socket('Geometry', in_out='OUTPUT', socket_type='NodeSocketGeometry')
    gi, go = ng.nodes.new('NodeGroupInput'), ng.nodes.new('NodeGroupOutput')
    ci = ng.nodes.new('GeometryNodeCollectionInfo')
    ci.inputs['Collection'].default_value = src
    ci.inputs['Separate Children'].default_value = True
    ci.inputs['Reset Children'].default_value = True
    iop = ng.nodes.new('GeometryNodeInstanceOnPoints')
    ng.links.new(gi.outputs[0], iop.inputs['Points'])
    ng.links.new(ci.outputs[0], iop.inputs['Instance'])
    ng.links.new(iop.outputs[0], go.inputs[0])
    ob.modifiers.new('scatter', 'NODES').node_group = ng
    bpy.context.view_layer.update()
    return ob


gt, gc = Vector((20, 0, 1.0)), Vector((20, -12, 1.0))
sa = scatter('scatter_a', [(20, -3, 0), (20, -5, 0)])
r0 = CameraSafety(sc).is_clear(gc, gt)
check('a scattered post blocks the sightline (ray_cast reports the source object)', not r0['clear']
      and r0['object'] == 'post' and abs(r0['distance'] - 2.85) < 0.01, r0)
csa = CameraSafety(sc).exclude(sa)
r1 = csa.is_clear(gc, gt)
check('exclude(scatter) excludes its instances', r1['clear'], (r1, sorted(csa._excluded), csa._index()))
c_in = csa.clearance(Vector((20, -9.5, 1.0)))
check("a scatter's unrendered source (in an excluded collection) has no clearance", c_in is None, c_in)
sc.collection.objects.link(post)                             # the same post now also renders on its own
bpy.context.view_layer.update()
csa = CameraSafety(sc).exclude(sa)
r2 = csa.is_clear(gc, gt)
check('  ... but the same source rendering on its own still blocks', not r2['clear'] and abs(r2['distance'] - 9.35) < 0.01,
      (r2, csa._index()))
c_in = csa.clearance(Vector((20, -9.5, 1.0)))
check('  ... and has clearance (a camera inside it is inside)', c_in is not None and c_in['behind'], c_in)
sb = scatter('scatter_b', [(20, -7, 0)])
r3 = CameraSafety(sc).exclude(sa).is_clear(gc, gt)
check('  ... and a second scatter of it that is not excluded still blocks', not r3['clear']
      and abs(r3['distance'] - 6.85) < 0.01, r3)
r4 = CameraSafety(sc).exclude(sa, sb).is_clear(gc, gt)
check('  ... excluding both leaves only the post on its own', not r4['clear'] and abs(r4['distance'] - 9.35) < 0.01, r4)

bad = [n for n, ok, _d in RESULTS if not ok]
print(f"[camera-checks] {'PASS' if not bad else 'FAIL'}: {len(RESULTS) - len(bad)}/{len(RESULTS)}", flush=True)
for n in bad:
    print('  - FAILED', n, flush=True)
