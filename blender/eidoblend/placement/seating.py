"""eidoblend.placement.seating: scene_placement.js's seating and emote helpers for the characters family's VRMs: the
engine's seatOn, sitOnGround, unseat, emote and faceCamera, with its seat-pan finder (findSeatSurface), the chair's
facing from its backrest (_detectChairFacing), the hips settle (_restHipsOnSeat), the butt clamp of a sit-down
(_clampSeatedButt) and the check that a sitter does not face the backrest. Guide: tools-guides/placement.md.

    from eidoblend.characters import load_vrm
    from eidoblend.placement import seat_on, sit_on_ground, unseat, emote, face_camera
    me = load_vrm('aletheia')
    seat_on(me, chair)                                   # the chair sit clip, facing out of the chair, on its pan
    seat_on(you, chair2, transition='stand_to_sit', t=1.0)   # stands before it at 1 s and lowers into it (keyed)
    sit_on_ground(them, at=(1.0, -0.5), ground=[floor])  # the ground sit clip, the lowest underside on the floor
    emote(me, 'cheer')                                   # an expressive clip on a planted VRM, looping
    face_camera(me, offset=0.4)                          # a three-quarter turn toward the scene camera

The engine did these at render time (a mixer it advanced, a settle queue its render loop ran). Here each call keys
what it decides when it is called: the clips are NLA strips (characters.vrma), a sit-down's root is keyed on every
frame of its descent, so a saved .blend renders any frame on its own. Headings are Blender's: radians about +Z,
0 facing -Y (a VRM's front as loaded); the engine's offsets keep their sign. A seated VRM carries
arm['eido_seated'] (the clipping and hovering audits leave it; unseat() clears it) and arm['eido_seat'] (its
chair's name, for check_seated_facing).
"""

from __future__ import annotations

import math

import bpy
from mathutils import Vector

from . import _world as W

SIT_CLIP = 'sitting_normal_chair'
GROUND_CLIP = 'sitting_on_ground'


def _log(tag, msg):
    print(f'[{tag}] {msg}', flush=True)


def _arm(h):
    return getattr(h, 'arm', h)


def _meshes(root):
    """Every visible mesh in root's subtree, whatever its audit flags: a chair marked no_clipping_check (so a sitter
    does not trip the clipping audit) is still a chair (the engine collected them directly for that reason)."""
    return [o for o in [root] + list(root.children_recursive) if o.type == 'MESH' and W.visible(o)]


def _box(objs, dg):
    mn = Vector((1e30, 1e30, 1e30))
    mx = Vector((-1e30, -1e30, -1e30))
    for o in objs:
        a, b = W.box_of_object(o, dg)
        mn = Vector((min(mn.x, a.x), min(mn.y, a.y), min(mn.z, a.z)))
        mx = Vector((max(mx.x, b.x), max(mx.y, b.y), max(mx.z, b.z)))
    return mn, mx


def heading_toward(dx, dy):
    """The heading (radians about +Z, 0 facing -Y) that faces the direction (dx, dy)."""
    return math.atan2(dx, -dy)


def _forward(th):
    return Vector((math.sin(th), -math.cos(th), 0.0))


_ROT_PATH = {'QUATERNION': 'rotation_quaternion', 'AXIS_ANGLE': 'rotation_axis_angle'}


def _heading(ob):
    """An object's heading (its world yaw)."""
    return ob.matrix_world.to_euler().z


def _set_heading(ob, th):
    """Turn an upright object to a heading through whichever rotation it uses (a VRM's armature rotates by
    quaternion, where rotation_euler does nothing)."""
    mode = ob.rotation_mode
    if mode == 'QUATERNION':
        from mathutils import Quaternion
        ob.rotation_quaternion = Quaternion((0.0, 0.0, 1.0), th)
    elif mode == 'AXIS_ANGLE':
        ob.rotation_axis_angle = (th, 0.0, 0.0, 1.0)
    else:
        e = ob.rotation_euler.copy()
        e.z = th
        ob.rotation_euler = e


def find_seat_surface(chair, grid=7, bin_size=0.03):
    """findSeatSurface: the seat pan, not the box top (that is the backrest). Casts straight down over a grid across
    the inner 80 % of the chair's footprint and histograms the hit heights in 3 cm bins: the seat is the broadest
    horizontal surface, so it catches the most hits (a tie goes to the lower bin, so a flat-topped throne back loses
    to the seat). Returns {'z', 'x', 'y' (the pan's centre), 'pan_dx', 'pan_dy' (its extent), 'fallback'}; with no
    geometry to hit, an estimate 45 % up the box (fallback True)."""
    W.update()
    dg = W.depsgraph()
    meshes = _meshes(chair)
    if not meshes:
        p = chair.matrix_world.translation
        return {'z': p.z, 'x': p.x, 'y': p.y, 'fallback': True}
    lo, hi = _box(meshes, dg)
    rays = W.Rays(meshes, dg)
    hits = []
    for i in range(grid):
        for j in range(grid):
            x = lo.x + (0.1 + 0.8 * i / (grid - 1)) * (hi.x - lo.x)
            y = lo.y + (0.1 + 0.8 * j / (grid - 1)) * (hi.y - lo.y)
            h = rays.cast((x, y, hi.z + 0.5), (0, 0, -1))
            if h:
                hits.append((x, y, h[0].z))
    if not hits:
        return {'z': lo.z + 0.45 * (hi.z - lo.z), 'x': (lo.x + hi.x) / 2, 'y': (lo.y + hi.y) / 2, 'fallback': True}
    bins = {}
    for x, y, z in hits:
        bins.setdefault(round(z / bin_size), []).append((x, y, z))
    _k, best = max(bins.items(), key=lambda kv: (len(kv[1]), -kv[0]))
    xs, ys, zs = zip(*best)
    return {'z': sum(zs) / len(zs), 'x': sum(xs) / len(xs), 'y': sum(ys) / len(ys), 'fallback': False,
            'pan_dx': max(1e-3, max(xs) - min(xs)), 'pan_dy': max(1e-3, max(ys) - min(ys))}


def chair_facing(chair, seat=None):
    """_detectChairFacing: which way a chair opens, from its own geometry. The backrest is what stands more than
    18 cm above the pan; its weighted centroid (each sampled vertex weighted by the vertices it stands for and by its
    height above that line, so a backrest panel outvotes a screw and the backrest's top outvotes the armrests) lies
    toward the back, and a sitter faces away from it. Returns a heading, or None when the back is centred over the
    seat (a stool)."""
    seat = seat or find_seat_surface(chair)
    up = seat['z'] + 0.18
    dg = W.depsgraph()
    sx = sy = n = 0.0
    for o in _meshes(chair):
        co = W.world_verts(o, dg)
        step = max(1, len(co) // 300)                              # about 300 samples a mesh
        s = co[::step]
        m = s[:, 2] > up
        if not m.any():
            continue
        w = step * (s[m, 2] - up)
        sx += float((s[m, 0] * w).sum())
        sy += float((s[m, 1] * w).sum())
        n += float(w.sum())
    if n <= 0:
        return None
    bx, by = sx / n - seat['x'], sy / n - seat['y']                # toward the backrest
    ln = math.hypot(bx, by)
    if ln < 0.05:
        return None
    if ln < 0.10:
        _log('seat_on', 'the backrest signal is WEAK (near-symmetric chair geometry): the facing may be off; verify '
                        'the render or pass face=')
    return heading_toward(-bx / ln, -by / ln)


def _hips(h):
    arm = _arm(h)
    name = (getattr(h, 'humanoid', None) or {}).get('hips')
    if not name:
        from ..harness.audits import rig_feet
        name = rig_feet(arm)[0]
    pb = arm.pose.bones.get(name) if name else None
    return None if pb is None else arm.matrix_world @ pb.head


def _body_bvh(h):
    W.update()
    meshes = [o for o in (getattr(h, 'meshes', None) or _meshes(_arm(h))) if W.visible(o)]
    return W.world_bvh(meshes, W.depsgraph())                      # the posed body, built fresh (not cached)


def _support_bvh(h):
    """The posed body's skin that can bear it on the ground, as a world BVH (sit_on_ground's measure). The polygons
    the spring chains carry (tails, hair, a coat's tails: bake_springs swings them afterwards, through whatever they
    were measured against) and the loose layers that hang over the body (a coat's hem) are left out, as
    eidoblend.characters.emotes leaves them (_support_skin): measured with them, on her tails Aletheia lay propped
    ~15 cm up, and on her coat's hem she sat 6 cm up. A rig that is not a VRM handle is measured whole (_body_bvh)."""
    if not (hasattr(h, 'humanoid') and hasattr(h, 'meshes')):
        return _body_bvh(h)
    from mathutils.bvhtree import BVHTree
    from ..characters.emotes.verbs import _support_skin
    W.update()
    dg = W.depsgraph()
    verts, polys = [], []
    for o, keep in _support_skin(h):
        if not keep or not W.visible(o):
            continue
        ev = o.evaluated_get(dg)
        me = ev.to_mesh()
        M = ev.matrix_world
        base = len(verts)
        verts.extend(M @ v.co for v in me.vertices)
        mp = me.polygons
        polys.extend(tuple(base + i for i in mp[k].vertices) for k in keep if k < len(mp))
        ev.to_mesh_clear()
    if not polys:
        return _body_bvh(h)
    return BVHTree.FromPolygons(verts, polys)


def _lowest_up(bvh, pts, z0, reach):
    lowest = None
    if bvh is None:
        return None
    for x, y in pts:
        loc, _n, _i, _d = bvh.ray_cast(Vector((x, y, z0)), Vector((0.0, 0.0, 1.0)), reach)
        if loc is not None and (lowest is None or loc.z < lowest):
            lowest = loc.z
    return lowest


def _seat_grid(seat, n):
    """The engine's grid over the pan: +-0.20 m across x and +-0.22 m across y (world axes), (2n + 1)^2 points."""
    return [(seat['x'] + gi * 0.20 / n, seat['y'] + gj * 0.22 / n) for gi in range(-n, n + 1) for gj in range(-n, n + 1)]


def _key_root(arm, frame, interpolation='LINEAR'):
    paths = ('location', _ROT_PATH.get(arm.rotation_mode, 'rotation_euler'))
    for path in paths:
        arm.keyframe_insert(path, frame=frame)
    ad = arm.animation_data
    if ad and ad.action:
        from bpy_extras import anim_utils
        cb = anim_utils.action_get_channelbag_for_slot(ad.action, ad.action_slot)
        for fc in (cb.fcurves if cb else []):
            if fc.data_path in paths:
                for kp in fc.keyframe_points:
                    if abs(kp.co.x - frame) < 1e-6:
                        kp.interpolation = interpolation


def _mark_seated(h, chair):
    arm = _arm(h)
    arm['eido_seated'] = True
    if chair is not None:
        arm['eido_seat'] = chair.name


def unseat(h):
    """unseat: the VRM is no longer seated (the clipping and hovering audits judge it again)."""
    arm = _arm(h)
    for k in ('eido_seated', 'eido_seat'):
        if k in arm:
            del arm[k]


def _choose_heading(arm, seat, facing, face, camera):
    if face is not None:
        return face
    if facing is not None:
        return facing
    cam = camera or bpy.context.scene.camera
    if cam is not None:
        c = cam.matrix_world.translation
        return heading_toward(c.x - seat['x'], c.y - seat['y'])
    return _heading(arm)


def _warn_bad_seat(chair, seat, facing):
    if seat.get('fallback'):
        _log('seat_on', "no raycastable seat surface on the target: estimated from its box. If it is NOT a chair, or "
                        "she is meant to sit on the FLOOR, use sit_on_ground: the chair sit clip on the ground reads "
                        "wrong (legs dangle or clip). Otherwise verify she sits flush.")
    if not _meshes(chair):
        _log('seat_on', '⚠ the seat target has NO VISIBLE mesh: she will appear to SIT ON NOTHING. Use a real, visible '
                        'chair, not a placeholder: seat_on finds the seat surface itself.')
    if facing is None:
        lo, hi = _box(_meshes(chair), W.depsgraph()) if _meshes(chair) else (Vector(), Vector())
        short = '/too-short cube' if hi.z - lo.z < 0.55 else ''
        _log('seat_on', f'⚠ the seat has no detectable BACKREST (featureless{short}): the facing falls back to the '
                        'camera. A flat cube carries no facing; use a chair with a back, or pass face=.')


def seat_on(h, chair, clip=SIT_CLIP, face=None, sink=None, transition=None, t=0.0, fade=0.25, transition_dur=None,
            hip_back=0.46, then=None, camera=None):
    """seatOn: sit a VRM IN a chair (not on it). Plays the chair sit clip ('sitting_normal_chair', or
    'sitting_nervous_arm_rub_chair') from t seconds, puts the root at the seat pan's centre, turns her out of the
    chair (face= a heading, else the chair's own facing, else toward the camera), lifts her by the hips onto the seat,
    then rests her real underside (an up-ray through her seated mesh at the hips) on the pan, `sink` (0.02) pressed
    in. Returns the seat height.

    transition='stand_to_sit': she stands `hip_back` (0.46 m) in front of the seat, facing out, and the clip lowers
    her into it from t (its own hip travel carries the hips back over the pan). Her root is keyed on every frame of
    the descent: from 40 % in, a one-sided clamp lifts her whenever her underside would dip below the seat (it never
    pushes her down), and at the clip's end a settle recentres her hips over the pan (biased toward the backrest)
    and rests the lowest of her underside on it (sink 0). The last pose holds, as the engine's did; then=<slot> plays
    a seated loop after it (crossfaded over 0.25 s, the root keyed again where the crossfade ends so the loop's pose,
    whose hips sit over its root, is settled on the pan too)."""
    from ..characters.vrma import load_clip, play_vrma, play_vrma_default
    scene = bpy.context.scene
    fps = scene.render.fps / scene.render.fps_base
    arm = _arm(h)
    seat = find_seat_surface(chair)
    facing = chair_facing(chair, seat)
    _warn_bad_seat(chair, seat, facing)
    th = _choose_heading(arm, seat, facing, face, camera)
    if transition:
        return _seat_transition(h, chair, seat, th, transition, t, fade, transition_dur, hip_back,
                                0.0 if sink is None else sink, then, load_clip, play_vrma, fps)
    sink = 0.02 if sink is None else sink
    try:
        play_vrma_default(h, clip, t=t)
    except Exception as e:                                         # noqa: BLE001 - the engine warned and went on
        _log('seat_on', f"couldn't play '{clip}' ({e}); seating without a sit pose")
    scene.frame_set(1 + int(round((t + 0.5) * fps)))              # measured in the pose, 0.5 s into the clip
    arm.location.x, arm.location.y = seat['x'], seat['y']
    _set_heading(arm, th)
    W.update()
    hp = _hips(h)
    if hp is None:
        _log('seat_on', 'hips bone not found: the root at seat height; verify she sits, not floats')
        arm.location.z = seat['z'] - sink
    else:
        arm.location.z += seat['z'] - hp.z                       # rough: the hip bone at the seat's height
        hp = _hips(h)
        hit = _lowest_up(_body_bvh(h), [(hp.x, hp.y)], seat['z'] - 0.6, 1.4)
        if hit is not None:
            arm.location.z += (seat['z'] - hit) - sink            # her underside on the seat, pressed in
        else:
            arm.location.z += 0.09
            _log('seat_on', 'could not cast up through the seated mesh under the hips: a fixed pelvis offset; '
                            'verify she sits flush')
    W.update()
    _mark_seated(h, chair)
    return seat['z']


def _rest_hips_on_seat(h, chair, seat, sink):
    """_restHipsOnSeat: hips over the pan (biased toward the backrest: hips belong at the back of a pan, centred they
    leave a gap to the backrest and hang the knees past the front), the chair's real surface under the hips, the
    lowest of her seated underside over the pan (a 13 x 13 grid of up-rays) on it."""
    arm = _arm(h)
    tx, ty = seat['x'], seat['y']
    f = chair_facing(chair, seat)
    if f is not None and 'pan_dx' in seat:
        back = -_forward(f)
        depth = abs(back.x) * seat['pan_dx'] + abs(back.y) * seat['pan_dy']
        shift = min(0.12, depth * 0.18)
        tx, ty = tx + back.x * shift, ty + back.y * shift
    hp = _hips(h)
    if hp is None:
        arm.location.z = seat['z'] - (sink or 0.0)
        return
    arm.location.x += tx - hp.x
    arm.location.y += ty - hp.y
    W.update()
    hp = _hips(h)
    under = W.Rays(_meshes(chair)).cast((hp.x, hp.y, hp.z + 0.5), (0, 0, -1), 2.5)
    seat_here = under[0].z if under else seat['z']
    if not under:
        _log('seat_on', 'settle: no chair surface beneath the hips: she is NOT over the seat (check the standing spot, '
                        'hip_back, the facing); resting at the estimated seat height: verify she is not floating')
    arm.location.z += seat_here - hp.z
    W.update()
    lowest = _lowest_up(_body_bvh(h), _seat_grid(seat, 6), seat_here - 0.25, 0.6)
    arm.location.z += (seat_here - lowest) - (sink or 0.0) if lowest is not None else 0.09


THEN_FADE = 0.25            # s: the crossfade from a sit-down into its seated loop (then=)


def _fade_in(strip, fade, fps):
    """A strip's crossfade in, set with auto-blend off first: characters.vrma.play_vrma sets blend_in while the
    strip still auto-blends, which leaves it 0 (a pop instead of a crossfade)."""
    if strip is not None and fade and fade > 0:
        strip.use_auto_blend = False
        strip.blend_in = fade * fps
    return strip


def _seat_transition(h, chair, seat, th, transition, t, fade, dur, hip_back, sink, then, load_clip, play_vrma, fps):
    scene = bpy.context.scene
    arm = _arm(h)
    _set_heading(arm, th)
    fwd = _forward(th)
    arm.location.x, arm.location.y = seat['x'] + fwd.x * hip_back, seat['y'] + fwd.y * hip_back   # its own z kept
    tr = load_clip(h, transition)
    dur = tr.duration if dur is None else dur
    _fade_in(play_vrma(h, tr, t=t, loop=False, fade=fade), fade, fps)
    then_strip = None
    if then:
        then_strip = _fade_in(play_vrma(h, load_clip(h, then), t=t + dur, loop=True, fade=THEN_FADE), THEN_FADE, fps)
    f0 = 1 + int(round(t * fps))
    f_clamp = f0 + int(round(max(0.1, dur * 0.4) * fps))
    f_final = f0 + int(round(max(0.1, dur - 0.05) * fps))
    scene.frame_set(f0)
    _key_root(arm, f0)
    target = seat['z'] - sink
    lifts = 0
    for f in range(f_clamp, f_final):
        scene.frame_set(f)
        lowest = _lowest_up(_body_bvh(h), _seat_grid(seat, 3), seat['z'] - 0.25, 0.6)
        if lowest is not None and lowest < target:                # lift only: the descent plays until she meets it
            arm.location.z += target - lowest
            lifts += 1
        _key_root(arm, f)
    scene.frame_set(f_final)
    _rest_hips_on_seat(h, chair, seat, sink)
    _key_root(arm, f_final)
    then_note = ''
    if then_strip is not None:
        # The seated loop carries its hips over its root, where the sit-down's own hip travel had carried them
        # about 0.4 m back: left on the sit-down's root, she would end on the pan's front edge, in the air. Hold
        # the root through the crossfade's start, settle the loop's pose on the pan where the crossfade is done,
        # and key it there: LINEAR keys over the same frames as the linear blend keep the hips still through it.
        fa = int(round(then_strip.frame_start))
        fb = int(math.ceil(then_strip.frame_start + then_strip.blend_in))
        if fa > f_final:
            _key_root(arm, fa)
        scene.frame_set(fb)
        _rest_hips_on_seat(h, chair, seat, sink)
        _key_root(arm, fb)
        then_note = f"; '{then}' from frame {fa}, its pose settled on the pan by frame {fb}"
    W.update()
    _log('seat_on', f"'{arm.name}' lowers into '{chair.name}' over frames {f0}-{f_final} ({transition}, "
                    f'{dur:.2f} s; the clamp lifted her on {lifts} frame(s)), settled on the pan at {seat["z"]:.3f} m'
                    + then_note)
    _mark_seated(h, chair)
    return seat['z']


def sit_on_ground(h, at=None, clip=GROUND_CLIP, ground=None, z=0.0, sink=0.005, hip_height=0.08, face=None, t=0.0,
                  camera=None):
    """sitOnGround: sit a VRM on the floor with a ground-sit clip ('sitting_on_ground'; 'sit_laying_on_ground' to
    lie down), not a chair clip (its legs would dangle or clip). at=(x, y) (default: where she is); the floor height
    from `ground` (objects cast down onto) or z. Faces face=, else the camera. Lifts her by the hips, then rests the
    LOWEST of her underside (a grid of up-rays, hips +-0.35 m, so a forward shin or a lying back counts) on the floor,
    `sink` (5 mm) above it. Returns the floor height."""
    from ..characters.vrma import play_vrma_default
    scene = bpy.context.scene
    fps = scene.render.fps / scene.render.fps_base
    arm = _arm(h)
    try:
        play_vrma_default(h, clip, t=t)
    except Exception as e:                                         # noqa: BLE001
        _log('sit_on_ground', f"couldn't play '{clip}' ({e}); seating without a pose")
    scene.frame_set(1 + int(round((t + 0.5) * fps)))
    at = at if at is not None else (arm.location.x, arm.location.y)
    arm.location.x, arm.location.y = at[0], at[1]
    floor = z
    gm = [m for g in (ground or ()) for m in _meshes(g)]
    if gm:
        top = _box(gm, W.depsgraph())[1].z                       # cast from just above it: a BVH is float32, so a
        hit = W.Rays(gm).cast((at[0], at[1], top + 1.0), (0, 0, -1))   # ray from 10 km up loses a millimetre
        if hit:
            floor = hit[0].z
    cam = camera or scene.camera
    if face is not None:
        _set_heading(arm, face)
    elif cam is not None:
        c = cam.matrix_world.translation
        _set_heading(arm, heading_toward(c.x - at[0], c.y - at[1]))
    W.update()
    hp = _hips(h)
    if hp is None:
        _log('sit_on_ground', 'hips bone not found: the root at the floor; verify she sits, not floats')
        arm.location.z = floor + hip_height
    else:
        arm.location.z += (floor + 0.25) - hp.z                   # rough lift: her mesh above the floor
        hp = _hips(h)
        pts = [(hp.x + dx * 0.175, hp.y + dy * 0.175) for dx in range(-2, 3) for dy in range(-2, 3)]
        lowest = _lowest_up(_support_bvh(h), pts, floor - 0.6, 1.5)   # the skin that bears her: no tails, no hem
        if lowest is not None:
            arm.location.z += (floor - lowest) + sink              # the lowest underside on the floor
        else:
            arm.location.z += -0.25 + hip_height
            _log('sit_on_ground', 'could not cast the seated mesh: the hip_height fallback; verify she rests on the '
                                  'floor')
    W.update()
    _mark_seated(h, None)
    return floor


def emote(h, slot, t=0.0, **kw):
    """emote: an expressive clip on a planted VRM (talk, cheer, reach, raise, fist, salute, crazy, dance, any slot),
    looping, from t seconds (characters.vrma.play_vrma_default). For a VRM a controller is walking, the controller
    owns the body: let it stop first. Sitting goes through seat_on / sit_on_ground."""
    from ..characters.vrma import play_vrma_default
    if 'sit' in slot:
        _log('emote', f"'{slot}' is a sitting clip: seat_on / sit_on_ground place the body for it (emote does not)")
    return play_vrma_default(h, slot, t=t, **kw)


def face_camera(h, camera=None, offset=0.0, frame=None):
    """faceCamera: turn a planted VRM to face the camera (the scene's, or camera=), plus offset radians (0.4 for a
    three-quarter turn). frame= keys the turn there (a camera that moves between shots: turn her at the start of
    hers); without it the turn is set, as the engine set it, and an existing rotation key overrides it."""
    arm = _arm(h)
    cam = camera or bpy.context.scene.camera
    if cam is None:
        _log('face_camera', 'need a camera (scene.camera or camera=) and a VRM')
        return None
    W.update()
    p, c = arm.matrix_world.translation, cam.matrix_world.translation
    th = heading_toward(c.x - p.x, c.y - p.y) + offset
    _set_heading(arm, th)
    if frame is not None:
        arm.keyframe_insert(_ROT_PATH.get(arm.rotation_mode, 'rotation_euler'), frame=frame)
    W.update()
    return th


def check_seated_facing(scene=None):
    """The engine's deferred seat check: a sitter (eido_seat names its chair) whose heading is more than 110 deg off
    the chair's own facing faces the BACKREST (RE-RENDER REQUIRED: most often a rotation set after seat_on); more
    than 55 deg is worth a look. Returns [{'obj', 'chair', 'deg'}] for those over 55."""
    scene = scene or bpy.context.scene
    out = []
    for o in scene.objects:
        name = o.get('eido_seat') if o.type == 'ARMATURE' else None
        chair = bpy.data.objects.get(name) if name else None
        if chair is None:
            continue
        f = chair_facing(chair)
        if f is None:
            continue
        d = _heading(o) - f
        deg = abs(math.degrees(math.atan2(math.sin(d), math.cos(d))))
        if deg > 55:
            out.append({'obj': o, 'chair': chair, 'deg': deg})
            _log('seat_on', (f"⚠ RE-RENDER REQUIRED: '{o.name}' faces the BACKREST of '{chair.name}' ({deg:.0f} deg "
                             'off its natural facing). Most common cause: a rotation set AFTER seat_on; pass face= '
                             'to seat_on instead.') if deg > 110 else
                 f"'{o.name}' is {deg:.0f} deg off '{chair.name}''s natural facing: verify the render; pass face= to "
                 'seat_on if it is deliberate.')
    return out
