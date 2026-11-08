"""look/camera.py: cameras for film shots in Blender. Targets and framing (focusPoint, lookAtObject), fov <-> lens, moves
baked to keys (dolly, push, orbit, pan, tracking, zoom, handheld), real depth of field with focus pulls, and shots bound
to timeline markers.

Every move is BAKED: the target is sampled at every frame of the shot (scene.frame_set), smoothed, and the camera's
location / rotation (and lens) are keyed per frame with linear interpolation. Keys are a pure function of the frame, so
a still at any frame renders the same whether it is rendered alone or after the frames before it (probe.py's jump mode),
the camera has ONE owner (its keys: no constraint or handler fighting them), and the audits read what renders.
Smoothing looks both ways (a centred Gaussian over the target's track, sigma = smooth_s): offline, the operator knows
where the subject is going, so the camera neither lags nor overshoots. lag_s instead ports the WebGPU per-frame lerp
(an exponential follow that trails the subject).

    from eidoblend.look import camera as C
    cam = C.make_camera('cam_track', fov=34, fstop=2.8)                 # three's vertical fov, a full-frame 36 mm sensor
    hips = C.bone_target(arm, 'hips')
    C.track(scene, cam, (1, 240), hips, offset=C.orbit_offset(3.8, 55, 34), height=1.3, aim_height=1.05, smooth_s=0.5)
    C.focus_on(scene, cam, (1, 240), C.bone_target(arm, 'chest'))
    C.add_shot(scene, 'walk', 1, cam)

Coordinates: Blender Z up, metres. A three.js (x, y, z) is three_to_blender -> (x, -z, y).
"""
import math
import random

import bpy
from mathutils import Euler, Matrix, Quaternion, Vector

UP = Vector((0.0, 0.0, 1.0))


# ---------------------------------------------------------------------------------------------------------- basics
def three_to_blender(v):
    """A three.js Y-up position or direction as Blender Z-up: (x, y, z) -> (x, -z, y)."""
    x, y, z = v
    return Vector((x, -z, y))


def blender_to_three(v):
    x, y, z = v
    return Vector((x, z, -y))


def look_matrix(pos, aim, up=UP):
    """The world matrix of a camera at `pos` looking at `aim`, its top toward `up` (Blender cameras look down -Z)."""
    pos, aim, up = Vector(pos), Vector(aim), Vector(up)
    f = aim - pos
    if f.length < 1e-9:
        raise ValueError('look_matrix: the aim is the position')
    f.normalize()
    u = up - f * f.dot(up)
    if u.length < 1e-6:                       # looking straight along `up`: any perpendicular will do
        alt = Vector((0.0, 1.0, 0.0)) if abs(f.y) < 0.9 else Vector((1.0, 0.0, 0.0))
        u = alt - f * f.dot(alt)
    u.normalize()
    z = -f
    x = u.cross(z)
    m = Matrix((x, u, z)).transposed().to_4x4()
    m.translation = pos
    return m


def ease(u, kind='smooth'):
    """0..1 -> 0..1. 'linear', 'smooth' (smoothstep, the WebGPU default), 'smoother', 'in', 'out', 'sine'."""
    u = min(1.0, max(0.0, float(u)))
    if kind == 'linear':
        return u
    if kind == 'smooth':
        return u * u * (3 - 2 * u)
    if kind == 'smoother':
        return u * u * u * (u * (u * 6 - 15) + 10)
    if kind == 'in':
        return u * u
    if kind == 'out':
        return 1 - (1 - u) * (1 - u)
    if kind == 'sine':
        return 0.5 - 0.5 * math.cos(math.pi * u)
    raise ValueError(f'ease {kind!r}')


def frames_of(span):
    """(first, last) inclusive -> a list of frames."""
    fa, fb = int(span[0]), int(span[1])
    return list(range(fa, fb + 1))


def fps_of(scene):
    return scene.render.fps / scene.render.fps_base


def frame_at(scene, t):
    """The frame shown at t seconds (the film's frame_start is t = 0)."""
    return scene.frame_start + int(round(t * fps_of(scene)))


# ---------------------------------------------------------------------------------------------------------- cameras
def make_camera(name='camera', lens=None, fov=None, fov_axis='vertical', fstop=None, sensor_width=36.0,
                clip=(0.05, 2000.0), collection=None, scene=None):
    """A camera object with a full-frame sensor (36 mm, fit AUTO). fov (degrees; three's fov is VERTICAL) or lens (mm).
    fstop turns depth of field on."""
    scene = scene or bpy.context.scene
    data = bpy.data.cameras.new(name)
    obj = bpy.data.objects.new(name, data)
    (collection or scene.collection).objects.link(obj)
    data.sensor_fit = 'AUTO'
    data.sensor_width = float(sensor_width)
    data.clip_start, data.clip_end = float(clip[0]), float(clip[1])
    if fov is not None:
        set_fov(obj, fov, fov_axis, scene)
    elif lens is not None:
        data.lens = float(lens)
    if fstop is not None:
        set_dof(obj, fstop=fstop)
    obj.rotation_mode = 'QUATERNION'
    return obj


def _aspect(scene):
    r = scene.render
    return (r.resolution_x * r.pixel_aspect_x) / max(1e-9, r.resolution_y * r.pixel_aspect_y)


def set_fov(cam, fov_deg, axis='vertical', scene=None):
    """Set the lens for a field of view in degrees. axis 'vertical' is three's PerspectiveCamera.fov; 'horizontal'
    otherwise. The sensor stays a real one (AUTO fit: its width spans the frame's longer side), so depth of field
    behaves as on that camera. Returns the lens in mm."""
    scene = scene or bpy.context.scene
    d = cam.data
    a = _aspect(scene)
    d.sensor_fit = 'AUTO'
    t = math.tan(math.radians(fov_deg) / 2)
    landscape = a >= 1.0
    if axis == 'vertical':
        t_long = t * a if landscape else t
    elif axis == 'horizontal':
        t_long = t if landscape else t / a
    else:
        raise ValueError(f'axis {axis!r}')
    d.lens = (d.sensor_width / 2) / t_long
    return d.lens


def fov_of(cam, scene=None):
    """(horizontal, vertical) field of view in degrees for the scene's frame."""
    scene = scene or bpy.context.scene
    d = cam.data
    a = _aspect(scene)
    if d.sensor_fit == 'VERTICAL':
        tv = d.sensor_height / 2 / d.lens
        th = tv * a
    elif d.sensor_fit == 'HORIZONTAL' or a >= 1.0:
        th = d.sensor_width / 2 / d.lens
        tv = th / a
    else:
        tv = d.sensor_width / 2 / d.lens
        th = tv * a
    return math.degrees(2 * math.atan(th)), math.degrees(2 * math.atan(tv))


# ---------------------------------------------------------------------------------------------------------- targets
GEOMETRY = {'MESH', 'CURVE', 'SURFACE', 'META', 'FONT', 'CURVES', 'POINTCLOUD', 'VOLUME', 'GREASEPENCIL'}


def _collect(items, children=True):
    out = []
    stack = list(items) if isinstance(items, (list, tuple, set)) else [items]
    while stack:
        it = stack.pop()
        if isinstance(it, bpy.types.Collection):
            stack.extend(it.all_objects)
        elif isinstance(it, bpy.types.Object):
            out.append(it)
            if children:
                stack.extend(it.children)
    seen, uniq = set(), []
    for o in out:
        if o.name not in seen:
            seen.add(o.name)
            uniq.append(o)
    return uniq


def world_bounds(items, depsgraph=None, children=True):
    """(min, max) world corners of the evaluated geometry of objects / collections (an armature counts through its
    child meshes, posed: evaluated bounds follow the deformation). None if there is no geometry."""
    dg = depsgraph or bpy.context.evaluated_depsgraph_get()
    lo = Vector((math.inf,) * 3)
    hi = Vector((-math.inf,) * 3)
    any_ = False
    for o in _collect(items, children):
        if o.type not in GEOMETRY or o.hide_render:
            continue
        ev = o.evaluated_get(dg)
        mw = ev.matrix_world
        for c in ev.bound_box:
            p = mw @ Vector(c)
            lo = Vector(map(min, lo, p))
            hi = Vector(map(max, hi, p))
            any_ = True
    return (lo, hi) if any_ else None


def focus_point(obj, y_bias=0.0, depsgraph=None):
    """focusPoint: the world centre of an object's evaluated bounds, raised by y_bias x its height (the WebGPU yBias:
    Blender's height is Z). An asset's origin may sit at its feet or a mounting port; this is its middle."""
    b = world_bounds(obj, depsgraph)
    if b is None:
        return obj.matrix_world.translation.copy()
    lo, hi = b
    c = (lo + hi) * 0.5
    c.z += y_bias * (hi.z - lo.z)
    return c


def look_at_object(cam, obj, y_bias=0.0, up=UP):
    """lookAtObject: turn the camera (where it stands) to the object's focus_point."""
    cam.matrix_world = look_matrix(cam.matrix_world.translation, focus_point(obj, y_bias), up)
    return cam


def humanoid_bone(arm, name):
    """The pose bone for a VRM humanoid name ('hips', 'chest', 'head', 'leftFoot' ...): the VRM add-on's mapping
    when it has one, else a bone of that name."""
    snake = ''.join('_' + ch.lower() if ch.isupper() else ch for ch in name)      # leftFoot -> left_foot
    try:
        hb = getattr(arm.data.vrm_addon_extension.vrm1.humanoid.human_bones, snake)
        bn = hb.node.bone_name
        if bn and bn in arm.pose.bones:
            return arm.pose.bones[bn]
    except AttributeError:
        pass
    if name in arm.pose.bones:
        return arm.pose.bones[name]
    low = name.lower()
    for pb in arm.pose.bones:
        if pb.name.lower().endswith(low):
            return pb
    raise KeyError(f'{arm.name}: no humanoid bone {name!r}')


def bone_target(arm, name, offset=(0.0, 0.0, 0.0), tail=False):
    """A target that follows a bone: callable() -> world position (evaluated at the scene's current frame)."""
    pb = humanoid_bone(arm, name)
    off = Vector(offset)
    return lambda: arm.matrix_world @ (pb.tail if tail else pb.head) + off


def target_fn(spec, offset=None):
    """Any target spec as callable() -> world Vector at the scene's current frame: a point, an Object (an empty's
    origin; otherwise its focus_point), (armature, 'boneName'), dict(object=, y_bias=) / dict(point=), or a callable."""
    off = Vector(offset) if offset is not None else None
    if callable(spec):
        fn = spec
    elif isinstance(spec, bpy.types.Object):
        if spec.type in GEOMETRY or spec.type == 'ARMATURE':
            fn = lambda o=spec: focus_point(o)
        else:
            fn = lambda o=spec: o.matrix_world.translation.copy()
    elif isinstance(spec, dict):
        if 'point' in spec:
            p = Vector(spec['point'])
            fn = lambda: p.copy()
        elif 'bone' in spec:
            fn = bone_target(spec['object'], spec['bone'])
        else:
            fn = lambda o=spec['object'], b=spec.get('y_bias', 0.0): focus_point(o, b)
    elif isinstance(spec, (tuple, list)) and len(spec) == 2 and isinstance(spec[0], bpy.types.Object):
        fn = bone_target(spec[0], spec[1])
    else:
        p = Vector(spec)
        fn = lambda: p.copy()
    if off is None:
        return fn
    return lambda: Vector(fn()) + off


def sample(scene, frames, fns):
    """Evaluate target functions at each frame: {name: [Vector per frame]} (one frame_set per frame for all of them)."""
    keep = scene.frame_current
    out = {k: [] for k in fns}
    for f in frames:
        scene.frame_set(int(f))
        for k, fn in fns.items():
            out[k].append(Vector(fn()))
    scene.frame_set(keep)
    return out


# ---------------------------------------------------------------------------------------------------------- smoothing
def gaussian_smooth(points, sigma_frames):
    """Centred Gaussian smoothing of a list of Vectors (no lag, no overshoot); the ends hold their values."""
    n = len(points)
    if sigma_frames <= 0 or n < 3:
        return [Vector(p) for p in points]
    r = int(math.ceil(3 * sigma_frames))
    w = [math.exp(-0.5 * (k / sigma_frames) ** 2) for k in range(-r, r + 1)]
    out = []
    for i in range(n):
        acc = Vector((0.0, 0.0, 0.0))
        ws = 0.0
        for k in range(-r, r + 1):
            j = min(n - 1, max(0, i + k))
            acc += points[j] * w[k + r]
            ws += w[k + r]
        out.append(acc / ws)
    return out


def lag_smooth(points, lag_frames):
    """The WebGPU per-frame lerp (pos.lerp(target, a)) as a time constant: an exponential follow that trails."""
    if lag_frames <= 0:
        return [Vector(p) for p in points]
    a = 1 - math.exp(-1.0 / lag_frames)
    out = [Vector(points[0])]
    for p in points[1:]:
        out.append(out[-1].lerp(p, a))
    return out


def _smoothed(scene, frames, fn, smooth_s=0.0, lag_s=0.0):
    """Sample a target over `frames` (plus 3 sigma of padding either side, so the centred filter sees real motion past
    the shot's ends) and smooth it. Returns one Vector per frame of `frames`."""
    fps = fps_of(scene)
    sig = smooth_s * fps
    pad = int(math.ceil(3 * sig)) if sig > 0 else 0
    ext = list(range(frames[0] - pad, frames[0])) + list(frames) + list(range(frames[-1] + 1, frames[-1] + 1 + pad))
    pts = sample(scene, ext, {'t': fn})['t']
    if lag_s > 0:
        pts = lag_smooth(pts, lag_s * fps)
    if sig > 0:
        pts = gaussian_smooth(pts, sig)
    return pts[pad:pad + len(frames)]


# ---------------------------------------------------------------------------------------------------------- handheld
def _value_noise(seed, n_frames, knots_per_frame):
    """Smooth 1D noise in -1..1 (Catmull-Rom through random knots), one value per frame."""
    rnd = random.Random(seed)
    nk = int(n_frames * knots_per_frame) + 4
    k = [rnd.uniform(-1, 1) for _ in range(nk)]
    out = []
    for i in range(n_frames):
        x = i * knots_per_frame
        j = int(x)
        t = x - j
        p0, p1, p2, p3 = k[j], k[j + 1], k[j + 2], k[j + 3]
        out.append(0.5 * ((2 * p1) + (-p0 + p2) * t + (2 * p0 - 5 * p1 + 4 * p2 - p3) * t * t
                          + (-p0 + 3 * p1 - 3 * p2 + p3) * t * t * t))
    return out


def handheld_offsets(n_frames, fps, deg=0.25, metres=0.004, hz=0.5, seed=1):
    """Per-frame (pitch, yaw, roll) radians and (x, y, z) camera-local metres of a breathing hand-held camera: smooth
    noise at about `hz`, amplitudes deg / metres. Subtle by default (the bounce audit passes it)."""
    kpf = hz / fps
    ch = [_value_noise(seed * 7 + c, n_frames, kpf) for c in range(6)]
    rot = [(math.radians(deg) * ch[0][i], math.radians(deg) * ch[1][i], math.radians(deg * 0.5) * ch[2][i])
           for i in range(n_frames)]
    loc = [Vector((metres * ch[3][i], metres * ch[4][i], metres * 0.5 * ch[5][i])) for i in range(n_frames)]
    return rot, loc


# ---------------------------------------------------------------------------------------------------------- keying
def _channelbag(idblock):
    ad = idblock.animation_data
    if not ad or not ad.action:
        return None
    try:
        from bpy_extras import anim_utils
        return anim_utils.action_get_channelbag_for_slot(ad.action, ad.action_slot)
    except (ImportError, AttributeError):
        return None


def _fcurves(idblock):
    cb = _channelbag(idblock)
    if cb is not None:
        return list(cb.fcurves)
    ad = idblock.animation_data
    return list(ad.action.fcurves) if ad and ad.action and hasattr(ad.action, 'fcurves') else []


def set_interpolation(idblock, interp='LINEAR', paths=None, frames=None):
    """Set the interpolation of an ID's keys (optionally only some data paths and a frame range)."""
    for fc in _fcurves(idblock):
        if paths and fc.data_path not in paths:
            continue
        for kp in fc.keyframe_points:
            if frames is None or frames[0] <= kp.co.x <= frames[1]:
                kp.interpolation = interp


def clear_keys(idblock, paths, frames):
    """Remove an ID's keys on `paths` inside [frames] (re-baking a shot replaces its keys, nothing else)."""
    for fc in _fcurves(idblock):
        if fc.data_path not in paths:
            continue
        for kp in reversed(list(fc.keyframe_points)):
            if frames[0] <= kp.co.x <= frames[1]:
                fc.keyframe_points.remove(kp, fast=True)
        fc.update()


def key_path(cam, frames, positions, aims, ups=None, lens=None, handheld=None, scene=None):
    """Key a camera per frame from positions and aim points (lists, one per frame). ups: one up vector or a list.
    lens: None, one value or a list (mm). handheld: None or dict(deg=, metres=, hz=, seed=) (handheld_offsets).
    Quaternions keep a continuous sign, so linear interpolation never takes the long way round."""
    scene = scene or bpy.context.scene
    n = len(frames)
    cam.rotation_mode = 'QUATERNION'
    clear_keys(cam, ('location', 'rotation_quaternion'), (frames[0], frames[-1]))
    if lens is not None:
        clear_keys(cam.data, ('lens',), (frames[0], frames[-1]))
    hh = handheld_offsets(n, fps_of(scene), **handheld) if handheld else None
    prev = None
    for i, f in enumerate(frames):
        up = ups[i] if isinstance(ups, list) else (ups if ups is not None else UP)
        m = look_matrix(positions[i], aims[i], up)
        loc = m.translation.copy()
        q = m.to_quaternion()
        if hh:
            (rx, ry, rz), dl = hh[0][i], hh[1][i]
            q = q @ Euler((rx, ry, rz), 'XYZ').to_quaternion()
            loc = loc + m.to_3x3() @ dl
        if prev is not None and prev.dot(q) < 0:
            q.negate()
        prev = q
        cam.location = loc
        cam.rotation_quaternion = q
        cam.keyframe_insert('location', frame=f)
        cam.keyframe_insert('rotation_quaternion', frame=f)
        if lens is not None:
            cam.data.lens = float(lens[i] if isinstance(lens, (list, tuple)) else lens)
            cam.data.keyframe_insert('lens', frame=f)
    set_interpolation(cam, 'LINEAR', ('location', 'rotation_quaternion'), (frames[0], frames[-1]))
    if lens is not None:
        set_interpolation(cam.data, 'LINEAR', ('lens',), (frames[0], frames[-1]))
    return {'camera': cam.name, 'frames': [frames[0], frames[-1]], 'start': list(positions[0]), 'end': list(positions[-1])}


# ---------------------------------------------------------------------------------------------------------- moves
def hold(scene, cam, span, position, aim, up=UP, lens=None, handheld=None):
    """A locked-off shot: the camera stands at `position` looking at `aim` (a target spec; a moving target makes this
    a pan, so use pan() for that)."""
    fr = frames_of(span)
    keep = scene.frame_current
    scene.frame_set(fr[0])
    a = Vector(target_fn(aim)())
    scene.frame_set(keep)
    return key_path(cam, fr, [Vector(position)] * len(fr), [a] * len(fr), up, lens, handheld, scene)


def dolly(scene, cam, span, start, end, aim, ease_kind='smooth', up=UP, lens=None, handheld=None, aim_smooth_s=0.0):
    """One eased move from `start` to `end` across the shot (the WebGPU rule: one move per shot, smoothstep). aim: a
    target spec (fixed or moving), or a pair (aim_start, aim_end) eased with the move."""
    fr = frames_of(span)
    n = len(fr)
    u = [ease(i / max(1, n - 1), ease_kind) for i in range(n)]
    s, e = Vector(start), Vector(end)
    pos = [s.lerp(e, k) for k in u]
    if isinstance(aim, (tuple, list)) and len(aim) == 2 and not isinstance(aim[0], (int, float)) \
            and not isinstance(aim[0], bpy.types.Object):
        a0, a1 = Vector(aim[0]), Vector(aim[1])
        aims = [a0.lerp(a1, k) for k in u]
    else:
        aims = _smoothed(scene, fr, target_fn(aim), smooth_s=aim_smooth_s)
    return key_path(cam, fr, pos, aims, up, lens, handheld, scene)


def push(scene, cam, span, metres, ease_kind='smooth', up=UP, handheld=None):
    """A push in (or pull out, metres < 0) along the camera's view axis as it stands at the shot's first frame."""
    scene.frame_set(int(span[0]))
    m = cam.matrix_world.copy()
    fwd = -(m.to_3x3() @ Vector((0.0, 0.0, 1.0)))
    p0 = m.translation.copy()
    aim = p0 + fwd * 10.0
    return dolly(scene, cam, span, p0, p0 + fwd * metres, (aim, aim + fwd * metres), ease_kind, up, None, handheld)


def orbit(scene, cam, span, centre, radius, height, deg_start, deg_end, aim=None, ease_kind='smooth', up=UP,
          handheld=None, smooth_s=0.0):
    """Round a centre (a target spec: it may move) at `radius`, `height` above the CENTRE POINT itself (an object's
    bounds middle, a bone's head: not the ground), from deg_start to deg_end (0 deg = +X, counter-clockwise seen
    from above). aim defaults to the centre."""
    fr = frames_of(span)
    n = len(fr)
    cs = _smoothed(scene, fr, target_fn(centre), smooth_s=smooth_s)
    aims = cs if aim is None else _smoothed(scene, fr, target_fn(aim), smooth_s=smooth_s)
    pos = []
    for i in range(n):
        a = math.radians(deg_start + (deg_end - deg_start) * ease(i / max(1, n - 1), ease_kind))
        pos.append(Vector((cs[i].x + radius * math.cos(a), cs[i].y + radius * math.sin(a), cs[i].z + height)))
    return key_path(cam, fr, pos, aims, up, None, handheld, scene)


def _mean_z(points):
    return sum(p.z for p in points) / max(1, len(points))


def pan(scene, cam, span, position, target, aim_offset=(0.0, 0.0, 0.0), smooth_s=0.4, lag_s=0.0, follow='xyz',
        aim_height=None, up=UP, lens=None, handheld=None):
    """A tripod: the camera stands at `position` and turns to follow `target` (a spec: a bone, an object ...).
    follow='xy' ignores the target's height changes (a walk's bob does not nod the camera): the aim holds the
    target's mean height over the shot. aim_height, when given, sets the aim's height whatever `follow` says."""
    fr = frames_of(span)
    pts = _smoothed(scene, fr, target_fn(target), smooth_s=smooth_s, lag_s=lag_s)
    off = Vector(aim_offset)
    hold_z = aim_height if aim_height is not None else _mean_z(pts)
    aims = []
    for p in pts:
        a = Vector(p)
        if 'z' not in follow:
            a.z = hold_z
        elif aim_height is not None:
            a.z = aim_height
        aims.append(a + off)
    return key_path(cam, fr, [Vector(position)] * len(fr), aims, up, lens, handheld, scene)


def orbit_offset(radius, deg_start, deg_end, ease_kind='linear'):
    """An offset that swings round the subject over the shot: for track(..., offset=orbit_offset(3.8, 55, 34)).
    Angles from the subject's +Y (its walking direction when it walks +Y), positive toward +X."""
    def off(u):
        a = math.radians(deg_start + (deg_end - deg_start) * ease(u, ease_kind))
        return Vector((radius * math.sin(a), radius * math.cos(a), 0.0))
    return off


def track(scene, cam, span, target, offset, height=None, aim_height=None, aim_offset=(0.0, 0.0, 0.0), follow='xy',
          smooth_s=0.5, aim_smooth_s=None, lag_s=0.0, up=UP, lens=None, handheld=None):
    """A tracking camera: it travels with the subject. Position = smoothed target + offset (a Vector, or a function of
    u = 0..1 over the shot, e.g. orbit_offset), at `height` above the ground plane (z = 0) when given; aim = smoothed
    target (+ aim_offset), at `aim_height` when given. follow='xy' keeps the subject's bob (a walk's hips rise and
    fall 3-5 cm a step) out of the camera: without height / aim_height the position and the aim hold the target's
    MEAN height over the shot (offset.z above it), so a shot on level ground needs neither.

    The meadow's tracking camera (meadow.js 'track'): low, ahead and to the side, easing round as the subject comes on:
        track(scene, cam, (1, 288), hips, orbit_offset(3.8, 54, 34), height=1.3, aim_height=1.05, smooth_s=0.5)
    """
    fr = frames_of(span)
    n = len(fr)
    base = _smoothed(scene, fr, target_fn(target), smooth_s=smooth_s, lag_s=lag_s)
    ab = base if aim_smooth_s is None else _smoothed(scene, fr, target_fn(target), smooth_s=aim_smooth_s, lag_s=lag_s)
    zb, za = _mean_z(base), _mean_z(ab)
    pos, aims = [], []
    off_fn = offset if callable(offset) else (lambda u, o=Vector(offset): o)
    aoff = Vector(aim_offset)
    for i in range(n):
        u = i / max(1, n - 1)
        b = Vector(base[i])
        a = Vector(ab[i])
        if 'z' not in follow:
            b.z = zb
            a.z = za
        p = b + Vector(off_fn(u))
        if height is not None:
            p.z = height
        if aim_height is not None:
            a.z = aim_height
        pos.append(p)
        aims.append(a + aoff)
    return key_path(cam, fr, pos, aims, up, lens, handheld, scene)


def zoom(cam, span, lens_start, lens_end, ease_kind='smooth'):
    """Key the lens (mm) from lens_start to lens_end across the shot, eased. (A zoom changes the framing and the
    depth of field together; the bounce audit watches its reversals.)"""
    fr = frames_of(span)
    n = len(fr)
    clear_keys(cam.data, ('lens',), (fr[0], fr[-1]))
    for i, f in enumerate(fr):
        cam.data.lens = lens_start + (lens_end - lens_start) * ease(i / max(1, n - 1), ease_kind)
        cam.data.keyframe_insert('lens', frame=f)
    set_interpolation(cam.data, 'LINEAR', ('lens',), (fr[0], fr[-1]))


# ---------------------------------------------------------------------------------------------------------- focus
def set_dof(cam, fstop=None, blades=None, rotation_deg=None, ratio=None, use=True):
    """Real depth of field: the f-stop of the lens (with the camera's focal length and sensor: physical blur)."""
    d = cam.data.dof
    d.use_dof = bool(use)
    if fstop is not None:
        d.aperture_fstop = float(fstop)
    if blades is not None:
        d.aperture_blades = int(blades)
    if rotation_deg is not None:
        d.aperture_rotation = math.radians(rotation_deg)
    if ratio is not None:
        d.aperture_ratio = float(ratio)
    return d


def view_depth(cam, point):
    """The distance from the lens to `point` along the camera's view axis. Blender's depth of field measures this
    depth, not the straight-line distance: its plane of focus is parallel to the sensor, and a focus object's
    distance is its depth (BKE_camera_object_dof_distance)."""
    m = cam.matrix_world
    fwd = -(m.to_3x3() @ Vector((0.0, 0.0, 1.0))).normalized()
    return (Vector(point) - m.translation).dot(fwd)


def focus_depth(cam):
    """The depth the camera is focused at, as its depth of field uses it: its focus object's view depth (the
    focus_subtarget bone's head on an armature), else focus_distance."""
    d = cam.data.dof
    fo = d.focus_object
    if fo is None:
        return d.focus_distance
    p = fo.matrix_world.translation
    if fo.type == 'ARMATURE' and d.focus_subtarget and d.focus_subtarget in fo.pose.bones:
        p = fo.matrix_world @ fo.pose.bones[d.focus_subtarget].head
    return max(abs(view_depth(cam, p)), 1e-5)


def frame_ray(scene, cam, xy):
    """The world ray through a point of the picture: xy normalised, origin TOP left (as camera_audit.projected_box).
    Returns (origin, unit direction)."""
    fr = cam.data.view_frame(scene=scene)          # camera-local corners: top right, bottom right, bottom left, top left
    tr, br, bl, tl = (Vector(c) for c in fr)
    x, y = float(xy[0]), float(xy[1])
    local = (tl.lerp(tr, x)).lerp(bl.lerp(br, x), y)
    m = cam.matrix_world
    if cam.data.type == 'ORTHO':
        return m @ Vector((local.x, local.y, 0.0)), -(m.to_3x3() @ Vector((0.0, 0.0, 1.0))).normalized()
    return m.translation.copy(), (m.to_3x3() @ local).normalized()


def point_in_frame(scene, cam, xy, frame=None, depsgraph=None):
    """A focus puller's mark: the first surface under a point of the picture (xy normalised, origin top left) at
    `frame` (default the current one), instances included. Returns the world point, or None when the ray meets
    nothing (the sky). Racking from a mark picked this way starts on something the audience can see."""
    keep = scene.frame_current
    if frame is not None:
        scene.frame_set(int(frame))
    try:
        dg = depsgraph or bpy.context.evaluated_depsgraph_get()
        o, d = frame_ray(scene, cam, xy)
        ok, loc, _n, _i, _obj, _m = scene.ray_cast(dg, o, d, distance=cam.data.clip_end)
        return loc.copy() if ok else None
    finally:
        if frame is not None:
            scene.frame_set(keep)


def dof_limits(cam, distance, coc_mm=None):
    """The near and far limits of acceptable sharpness at a focus distance (m, a view depth): thin-lens maths with a
    circle of confusion of the sensor diagonal / 1500 (0.029 mm full frame). Returns dict(near, far, hyperfocal) in
    metres."""
    d = cam.data
    f = d.lens
    n = d.dof.aperture_fstop
    c = coc_mm or math.hypot(d.sensor_width, d.sensor_height) / 1500.0
    s = distance * 1000.0
    h = f * f / (n * c) + f
    near = s * (h - f) / (h + s - 2 * f)
    far = s * (h - f) / (h - s) if s < h else math.inf
    return {'near': near / 1000.0, 'far': far / 1000.0, 'hyperfocal': h / 1000.0, 'fstop': n, 'lens': f}


def focus_on(scene, cam, span, target, rack=None, smooth_s=0.0, fstop=None, name=None, collection=None):
    """Focus that follows a target: an empty keyed every frame at the target, set as the camera's focus object.
    rack=dict(to=<target spec>, frames=(r0, r1), ease='smooth') pulls focus from `target` to rack['to'] across those
    frames (a focus pull: the empty travels between the two; the plane of focus moves with it). Rack from something
    in the picture (point_in_frame picks a mark); camera_audit.focus_audit flags frames where nothing is sharp.
    Returns dict(empty, distances=[(frame, view depth m)], range=(min, max))."""
    fr = frames_of(span)
    nm = name or f'focus_{cam.name}'
    e = bpy.data.objects.get(nm)
    if e is None:
        e = bpy.data.objects.new(nm, None)
        e.empty_display_type = 'SPHERE'
        e.empty_display_size = 0.03
        (collection or (cam.users_collection[0] if cam.users_collection else scene.collection)).objects.link(e)
    a = _smoothed(scene, fr, target_fn(target), smooth_s=smooth_s)
    if rack:
        b = _smoothed(scene, fr, target_fn(rack['to']), smooth_s=smooth_s)
        r0, r1 = rack['frames']
    clear_keys(e, ('location',), (fr[0], fr[-1]))
    dist = []
    keep = scene.frame_current
    for i, f in enumerate(fr):
        p = Vector(a[i])
        if rack:
            p = p.lerp(b[i], ease((f - r0) / max(1, r1 - r0), rack.get('ease', 'smooth')))
        e.location = p
        e.keyframe_insert('location', frame=f)
    set_interpolation(e, 'LINEAR', ('location',), (fr[0], fr[-1]))
    set_dof(cam, fstop=fstop)
    cam.data.dof.focus_object = e
    for f in fr:
        scene.frame_set(f)
        dist.append((f, round(focus_depth(cam), 3)))
    scene.frame_set(keep)
    ds = [d for _f, d in dist]
    return {'empty': e.name, 'distances': dist, 'range': (min(ds), max(ds))}


# ---------------------------------------------------------------------------------------------------------- shots
def add_shot(scene, name, frame, cam):
    """A cut: a timeline marker at `frame` bound to `cam` (the camera switches there, in renders and in playback)."""
    m = scene.timeline_markers.get(name) or scene.timeline_markers.new(name, frame=int(frame))
    m.frame = int(frame)
    m.camera = cam
    if scene.camera is None or int(frame) <= scene.frame_start:
        scene.camera = cam
    return m


def shot_spans(scene, end=None):
    """{name: (first, last, camera)} from the markers bound to cameras, in time order (the last runs to frame_end)."""
    ms = sorted((m for m in scene.timeline_markers if m.camera is not None), key=lambda m: m.frame)
    last = end if end is not None else scene.frame_end
    return {m.name: (m.frame, (ms[i + 1].frame - 1) if i + 1 < len(ms) else last, m.camera) for i, m in enumerate(ms)}


def camera_at(scene, frame):
    """The camera that renders `frame` (the marker in force, else scene.camera)."""
    best = None
    for m in scene.timeline_markers:
        if m.camera is not None and m.frame <= frame and (best is None or m.frame > best.frame):
            best = m
    return best.camera if best else scene.camera
