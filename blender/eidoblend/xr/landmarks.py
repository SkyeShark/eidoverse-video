"""eidoblend.xr.landmarks: stand in the Blender scene itself, in a headset (Blender's VR Scene Inspection add-on).

A .blend opened in Blender with a headset on OpenXR (a Quest through Quest Link or Air Link) shows the scene with EEVEE
in the headset (View3D sidebar > VR > Start VR Session). The add-on's landmarks say where a session starts and at what
scale. These are the kit's WorldRig.standAt and toTable, as landmarks saved in the .blend:

    from eidoblend.xr import landmarks as LM
    LM.stand_at(scene, (0, -10, 0), facing=(0, 1, 0), street=0.25, name='street')   # 25 cm a unit, eyes 1.6 m
    LM.to_table(scene, centre=(0, 0, 0), table=0.01, name='table')                   # the world at 1:100 before you
    LM.activate(scene, 'street')
    LM.session_settings(scene)              # the kit page's view in Blender's session: rays, clip planes, walk speed
    cam = LM.view_camera(scene, 'street')   # a camera where the headset starts: render what the session will show

Blender's base pose (wm_xr_session.cc): with absolute tracking off, the head starts AT the landmark's location, turned by
its angle about Z (angle 0 looks along +Y; a turns the view to (-sin a, cos a)); base_scale scales the viewer, in world
units per room metre. So street = 0.25 m a unit is base_scale 4 with the eyes eye_height x 4 above the ground point,
and a table at 0.01 m a unit is base_scale 100 with the head back and up from the centre so it lies `distance` m ahead
of the eyes and at the kit's table height below them (toTable's rule: 75 cm below the eyes, kept between 0.6 and
1.05 m off the floor, for eyes at eye_height).
"""
from __future__ import annotations

import math

import bpy
from mathutils import Euler, Vector

ADDON = 'viewport_vr_preview'
# the kit page's camera (example.html, xr_page.html): near 2 cm, far 400 m, in room metres; WorldRig.walk's speed
PAGE_NEAR, PAGE_FAR, WALK_SPEED = 0.02, 400.0, 2.6


def ensure_addon():
    """Enable VR Scene Inspection (bundled with Blender). True when its landmarks exist."""
    import addon_utils
    if not addon_utils.check(ADDON)[1]:
        addon_utils.enable(ADDON, default_set=True)
    return hasattr(bpy.types.Scene, 'vr_landmarks')


def _angle(facing):
    fx, fy = float(facing[0]), float(facing[1])
    if abs(fx) < 1e-9 and abs(fy) < 1e-9:
        return 0.0
    return math.atan2(-fx, fy)


def _get(scene, name):
    for i, lm in enumerate(scene.vr_landmarks):
        if lm.name == name:
            return i, lm
    return None, None


def add(scene, name, location, angle=0.0, base_scale=1.0):
    """A CUSTOM landmark (replaced when one of that name exists). Returns it."""
    ensure_addon()
    i, lm = _get(scene, name)
    if lm is None:
        lm = scene.vr_landmarks.add()
        scene.vr_landmarks_selected = len(scene.vr_landmarks) - 1
    else:
        scene.vr_landmarks_selected = i
    lm.name = name
    lm.type = 'CUSTOM'
    lm.base_pose_location = tuple(location)
    lm.base_pose_angle = float(angle)
    lm.base_scale = float(base_scale)
    return lm


def stand_at(scene, point, facing=(0.0, 1.0, 0.0), street=1.0, eye_height=1.6, name='street'):
    """WorldRig.standAt as a landmark: stand on the ground point (Blender metres/units), facing a direction, at
    `street` room metres a unit (the kit's street scale; standAt's `scale` option)."""
    s = 1.0 / float(street)
    loc = (float(point[0]), float(point[1]), float(point[2] if len(point) > 2 else 0.0) + eye_height * s)
    return add(scene, name, loc, _angle(facing), s)


def table_height(eye_height=1.6, height=None):
    """The kit's toTable height: `height`, else 75 cm below the eyes, kept between 0.6 and 1.05 m (room metres)."""
    return float(height) if height is not None else min(1.05, max(0.6, float(eye_height) - 0.75))


def to_table(scene, centre=(0.0, 0.0, 0.0), table=0.01, distance=0.45, height=None, eye_height=1.6,
             facing=(0.0, 1.0, 0.0), name='table'):
    """WorldRig.toTable as a landmark: the world at `table` m a unit, the stage point `centre` `distance` m ahead of the
    eyes at the kit's table height (table_height: `height`, else 75 cm below eyes at eye_height, kept in 0.6-1.05 m).
    toTable's `at` (an exact room point) has no landmark form: Blender places the head, not the room."""
    s = 1.0 / float(table)
    drop = float(eye_height) - table_height(eye_height, height)
    f = Vector((float(facing[0]), float(facing[1]), 0.0))
    f = f.normalized() if f.length > 1e-9 else Vector((0.0, 1.0, 0.0))
    c = Vector(centre)
    loc = c - f * (distance * s) + Vector((0.0, 0.0, drop * s))
    lm = add(scene, name, tuple(loc), _angle(f), s)
    lm['xr_table'] = {'centre': list(c), 'distance': distance, 'drop': drop}
    return lm


def activate(scene, name):
    """Make a landmark the session's start (the add-on's 'Activate' button): the session settings take its pose."""
    i, lm = _get(scene, name)
    if lm is None:
        raise KeyError(f'no VR landmark {name!r}')
    scene.vr_landmarks_active = i
    wm = bpy.context.window_manager
    ss = wm.xr_session_settings
    ss.base_pose_type = 'CUSTOM'
    ss.base_pose_location = lm.base_pose_location
    ss.base_pose_angle = lm.base_pose_angle
    ss.base_scale = lm.base_scale
    return lm


def session_settings(scene=None, laser=True, floor=False, walk_speed=WALK_SPEED, near=PAGE_NEAR, far=PAGE_FAR,
                     passthrough=False):
    """The kit page's view in Blender's own VR session, at the active landmark's scale: the controllers drawn with a
    pointing ray (makeLaser; Blender's rays are light or dark, not the kit's orange), no floor grid (the set has its
    own ground), the page camera's clip planes (2 cm to 400 m in the room), fly speed = the kit's walk speed (2.6 room
    m/s), positional tracking on and absolute tracking off (the head starts AT the landmark). Returns the settings as
    set (a dict). These are the session's settings; what a running session does with them needs a headset."""
    ss = bpy.context.window_manager.xr_session_settings
    k = float(ss.base_scale) or 1.0                      # world units per room metre at the active landmark
    ss.show_controllers = True
    ss.controller_draw_style = 'LIGHT_RAY' if laser else 'LIGHT'
    ss.show_floor = bool(floor)
    ss.show_passthrough = bool(passthrough)
    ss.clip_start = near * k
    ss.clip_end = far * k
    ss.fly_speed = walk_speed * k
    ss.use_positional_tracking = True
    ss.use_absolute_tracking = False
    keys = ('show_controllers', 'controller_draw_style', 'show_floor', 'show_passthrough', 'clip_start', 'clip_end',
            'fly_speed', 'use_positional_tracking', 'use_absolute_tracking', 'base_scale', 'base_pose_type')
    return {key: getattr(ss, key) for key in keys}


def read(scene):
    """[{name, type, location, angle, base_scale}] of the scene's landmarks."""
    out = []
    for lm in getattr(scene, 'vr_landmarks', []):
        out.append({'name': lm.name, 'type': lm.type, 'location': tuple(lm.base_pose_location),
                    'angle': lm.base_pose_angle, 'base_scale': lm.base_scale})
    return out


def head_pose(scene, name):
    """(eye position, forward unit vector, base_scale) where a session started on that landmark puts your head."""
    _, lm = _get(scene, name)
    if lm is None:
        raise KeyError(f'no VR landmark {name!r}')
    a = lm.base_pose_angle
    return Vector(lm.base_pose_location), Vector((-math.sin(a), math.cos(a), 0.0)), lm.base_scale


def view_camera(scene, name, fov_v=70.0, look_at_table=True, aspect=16 / 9, cam_name=None):
    """A camera at the landmark's head, looking along its forward (and down at the table centre for a table
    landmark): a render from it is what the session shows first. fov_v: vertical degrees (the kit page's 70)."""
    from . import _bl
    eye, fwd, s = head_pose(scene, name)
    _, lm = _get(scene, name)
    cd = bpy.data.cameras.new(cam_name or f'vr_{name}')
    _bl.vertical_fov_lens(cd, fov_v, aspect)
    cd.clip_start = PAGE_NEAR * s
    cd.clip_end = PAGE_FAR * s
    ob = bpy.data.objects.new(cam_name or f'vr_{name}', cd)
    scene.collection.objects.link(ob)
    ob.location = eye
    tbl = lm.get('xr_table') if lm is not None else None
    if tbl is not None and look_at_table:
        ob.rotation_euler = _bl.look_at_rotation(eye, Vector(tuple(tbl['centre'])))
    else:
        ob.rotation_euler = Euler((math.pi / 2, 0.0, lm.base_pose_angle))
    return ob
