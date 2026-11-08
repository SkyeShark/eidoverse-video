"""eidoblend.characters.robot.example: eidoverse/examples/claude_robot.js, the whole scene, in Blender.

    from eidoblend.characters.robot import claude_robot_example
    ex = claude_robot_example()            # the studio, my body, 8 s at 30 fps, every frame keyed; ex['camera'] keyed too
    bpy.ops.render.render(animation=True)

My body (claude_robot.vrm) plays the stock idle through its hardware limits for 8 s: the OLED face runs through a few
expressions (a blink, happy, a spoken "hello" one vowel at a time, surprised, relaxed), the eyes look left then right,
the head and the crown's petals follow the face, and the camera eases in from the whole body to the head and shoulders.
The example's frame order, all of it (round one's port ran only its face track): restoreArmPose, the clip, keepArmPose,
rehomeBody, applyHardwareDOF, applyLegClearance (my feet kept clear of each other: wider than a human's), applyArmDOF,
applyHandDOF (every finger pin, the thumb's rotor), the face, applyHeadExpression, applyCrown, then the body set down onto
the floor. Its studio is the example's own: the key softbox front left, the fill front right and the rim behind as an
equirect made here (no HDRI file), the key and rim lights, the dark floor disc and the 0x121214 background; its bloom
takes only the face's light (threshold 3.2).
"""

import math

import bpy
import numpy as np
from mathutils import Vector

from .._math import ease, smooth
from ..ground import Ground
from ..vrm import load_vrm
from ..vrma import load_clip
from .rig import RobotRig, perform_robot

FPS, DURATION = 30, 8.0
LINE = [(3.3, 3.55, 'ee'), (3.55, 3.75, 'ih'), (3.75, 4.2, 'oh')]       # "hello", one vowel preset at a time
ROUND = {'oh', 'ou'}


def bump(t, t0, t1):
    """a 0 -> 1 -> 0 bump over [t0, t1]"""
    return 0.0 if (t <= t0 or t >= t1) else math.sin(math.pi * ease((t - t0) / (t1 - t0)))


def face(t):
    """the example's face(vrm, t): the expressions, and the mouth (each vowel fades in and out over 60 ms, a round
    shape eased in quickly: halfway it passes a heart; the mouth's weights kept summing to at most 1)"""
    s = {'happy': bump(t, 1.2, 3.1), 'surprised': bump(t, 4.5, 6.0), 'relaxed': smooth(6.0, 6.6, t),
         'blink': bump(t, 0.7, 0.95) + bump(t, 6.1, 6.35)}
    mouth = {}
    for t0, t1, v in LINE:
        w = min(1.0, max(0.0, (t - t0 + 0.03) / 0.06)) * min(1.0, max(0.0, (t1 + 0.03 - t) / 0.06))
        mouth[v] = mouth.get(v, 0.0) + (smooth(0.15, 0.6, w) if v in ROUND else w)
    sm = sum(mouth.values())
    for v in ('aa', 'ih', 'ou', 'ee', 'oh'):
        s[v] = mouth.get(v, 0.0) / max(1.0, sm)
    return {k: min(1.0, v) for k, v in s.items()}


def look(t):
    """vrm.lookAt.yaw: the eyes look left, then right (deg)"""
    return 20.0 * (bump(t, 6.4, 7.2) - bump(t, 7.2, 8.0))


def camera_at(t):
    """the example's camera: the whole body, then easing in to the head and shoulders -> (position, aim), Blender axes"""
    k = ease(min(1.0, max(0.0, (t - 1.2) / 4.3)))
    dist, a = 3.9 + (1.6 - 3.9) * k, 0.35 - 0.2 * k
    return (Vector((math.sin(a) * dist, -math.cos(a) * dist, 1.0 + 0.55 * k)), Vector((0.0, 0.0, 0.88 + 0.57 * k)))


def studio_environment(scene, strength=0.8, background=0x121214, size=(512, 256)):
    """studioEnvironment(): a key softbox front left, a fill front right, a rim behind, as an equirect (no HDRI file),
    the same boxes and formula; the camera sees `background` instead (three's scene.background beside its environment)"""
    W, H = size
    boxes = [((-0.55, 0.55, 0.63), 9.0, 0.3), ((0.75, 0.25, 0.6), 1.6, 0.45), ((0.45, 0.5, -0.75), 5.0, 0.22)]
    boxes = [(np.array(d) / np.linalg.norm(d), k, w) for d, k, w in boxes]
    u = (np.arange(W) + 0.5) / W
    v = (np.arange(H) + 0.5) / H
    PH, EL = np.meshgrid((0.5 - u) * 2 * math.pi, (v - 0.5) * math.pi)      # Blender's equirect: u = -atan2(y, x) / 2pi + .5
    bx, by, bz = np.cos(EL) * np.cos(PH), np.cos(EL) * np.sin(PH), np.sin(EL)
    tx, ty, tz = bx, bz, -by                                                  # the direction in three's axes
    val = 0.05 + 0.08 * np.maximum(0, ty)
    for d, k, w in boxes:
        val = val + k * np.exp((tx * d[0] + ty * d[1] + tz * d[2] - 1) / (w * w))
    img = bpy.data.images.new('studio_env', W, H, float_buffer=True)
    px = np.ones((H, W, 4), dtype=np.float32)
    px[..., 0] = px[..., 1] = px[..., 2] = val
    img.pixels.foreach_set(px.ravel())
    img.pack()
    wd = bpy.data.worlds.new('studio')
    scene.world = wd
    wd.use_nodes = True
    nt = wd.node_tree
    for n in list(nt.nodes):
        nt.nodes.remove(n)
    tex = nt.nodes.new('ShaderNodeTexEnvironment')
    tex.image = img
    bg = nt.nodes.new('ShaderNodeBackground')
    bg.inputs['Strength'].default_value = strength
    out = nt.nodes.new('ShaderNodeOutputWorld')
    nt.links.new(tex.outputs['Color'], bg.inputs['Color'])
    if background is None:
        nt.links.new(bg.outputs['Background'], out.inputs['Surface'])
        return wd
    flat = nt.nodes.new('ShaderNodeBackground')
    flat.inputs['Color'].default_value = _lin(background) + (1.0,)
    lp = nt.nodes.new('ShaderNodeLightPath')
    mix = nt.nodes.new('ShaderNodeMixShader')
    nt.links.new(lp.outputs['Is Camera Ray'], mix.inputs['Fac'])
    nt.links.new(bg.outputs['Background'], mix.inputs[1])
    nt.links.new(flat.outputs['Background'], mix.inputs[2])
    nt.links.new(mix.outputs['Shader'], out.inputs['Surface'])
    return wd


def _hex(c):
    return tuple(((c >> s) & 255) / 255.0 for s in (16, 8, 0))


def _lin(c):
    return tuple(ch ** 2.2 for ch in _hex(c))


def directional(name, pos_three, colour, strength, angle_deg=3.0, target=(0.0, 0.0, 0.0)):
    """a three DirectionalLight at pos (three's axes) shining at target, as a Blender sun"""
    x, y, z = pos_three
    p = Vector((x, -z, y))
    ld = bpy.data.lights.new(name, 'SUN')
    ld.energy = strength
    ld.color = _lin(colour)
    ld.angle = math.radians(angle_deg)
    ob = bpy.data.objects.new(name, ld)
    bpy.context.scene.collection.objects.link(ob)
    ob.rotation_mode = 'QUATERNION'
    ob.rotation_quaternion = Vector((0, 0, -1)).rotation_difference((Vector(target) - p).normalized())
    return ob


def floor_disc(radius=6.0, colour=0x2a2a2e, roughness=0.7, name='floor'):
    """the example's CircleGeometry(6, 96) floor, MeshStandard colour 0x2a2a2e, roughness 0.7"""
    import bmesh
    me = bpy.data.meshes.new(name)
    bm = bmesh.new()
    bmesh.ops.create_circle(bm, cap_ends=True, segments=96, radius=radius)
    bm.to_mesh(me)
    bm.free()
    ob = bpy.data.objects.new(name, me)
    bpy.context.scene.collection.objects.link(ob)
    mat = bpy.data.materials.new(name)
    mat.use_nodes = True
    b = mat.node_tree.nodes['Principled BSDF']
    b.inputs['Base Color'].default_value = _lin(colour) + (1.0,)
    b.inputs['Roughness'].default_value = roughness
    me.materials.append(mat)
    return ob


def claude_robot_example(scene=None, fps=FPS, duration=DURATION, vrm='claude_robot', render=True, key_camera=True,
                         bloom=True):
    """the whole example scene, every frame performed and keyed -> {'h', 'rig', 'rep', 'camera', 'floor', 'lights'}"""
    sc = scene or bpy.context.scene
    sc.render.fps, sc.render.fps_base = fps, 1.0
    nfr = int(round(duration * fps))
    sc.frame_start, sc.frame_end = 1, nfr
    if render:
        from ...look import render_settings as rs
        rs.apply_auto_enhance(sc, 'probe')
        sc.view_settings.exposure = 0.0
    studio_environment(sc, 0.8, 0x121214)
    lights = [directional('key', (-2.2, 3.2, 3.0), 0xfff4e8, 2.2), directional('rim', (2.5, 2.0, -3.0), 0xdfe8ff, 1.0)]
    floor = floor_disc()
    if bloom:
        try:
            from ...look.post import chain
            chain.set_bloom(sc, strength=0.25, size=0.5, threshold=3.2)
        except Exception as e:  # noqa: BLE001 (the bloom is the look's; the example plays without it)
            print('[claude_robot_example] bloom skipped:', e, flush=True)
    h = load_vrm(vrm, name='claude')
    rig = RobotRig(h)
    rep = perform_robot(h, load_clip(h, 'idle'), 1, nfr, rig=rig, ground=Ground(fn=lambda x, y: 0.0 * x), face=face,
                        look=look, action_name='claude|claude_robot_example')
    cam = None
    if key_camera:
        from ...look import camera as lc
        cam = lc.make_camera('claude_robot_cam', fov=30.0, scene=sc)
        frames = list(range(1, nfr + 1))
        pa = [camera_at((f - 1) / fps) for f in frames]
        lc.key_path(cam, frames, [p for p, _a in pa], [a for _p, a in pa], scene=sc)
        sc.camera = cam
    return {'h': h, 'rig': rig, 'rep': rep, 'camera': cam, 'floor': floor, 'lights': lights}
