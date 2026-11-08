"""eidoblend.course.stage: the locomotion template's scene around a course (eidoverse/terrain_base.js's setup).

    from eidoblend.course import build_course, course_stage
    course = build_course(PRESETS['ramp15'])
    st = course_stage(bpy.context.scene, course)        # sun, ambient, backdrop, camera, 30 fps

What the engine set up, in Blender's terms:
  backdrop   scene.background 0x182030: what the camera sees past the course (three's background lights nothing)
  ambient    AmbientLight(0xffffff, 0.5): a uniform world light. three's ambient gives albedo * 0.5 / pi of
             radiance, a uniform world of strength W gives albedo * W, so the world lights at 0.5 / pi
  sun        DirectionalLight(0xffffee, 3) from three (4, 8, 4) toward the origin, shadows on (2048 px over a 30 x 40 m
             frustum): a Blender sun of strength 3 (three's physical lights: the same irradiance), 1 degree across
  camera     PerspectiveCamera(45, w / h, 0.1, 200): 45 degrees VERTICAL field of view
  fps        30 (the template's dt is 1 / 30): course_stage(..., fps=FPS) sets it; a harness scene keeps its config's
The engine's ACES tone mapping is the contract's AgX here; the film preset (eidoblend.harness.settings) owns the rest.
"""
import math

import bpy
from mathutils import Vector

from .builder import b

BACKGROUND = 0x182030
AMBIENT = 0.5
SUN_COLOR = 0xffffee
SUN_INTENSITY = 3.0
SUN_POSITION = (4.0, 8.0, 4.0)          # three
FOV_V = 45.0
FPS = 30


def _lin(c):
    v = ((c >> 16) & 255) / 255, ((c >> 8) & 255) / 255, (c & 255) / 255
    return tuple(x / 12.92 if x <= 0.04045 else ((x + 0.055) / 1.055) ** 2.4 for x in v)


def course_world(name='course_world', background=BACKGROUND, ambient=AMBIENT):
    """camera rays see the backdrop colour, every other ray the ambient light (0.5 / pi uniform white)"""
    w = bpy.data.worlds.new(name)
    try:
        w.use_nodes = True
    except Exception:
        pass
    nt = w.node_tree
    for n in list(nt.nodes):
        nt.nodes.remove(n)
    lp = nt.nodes.new('ShaderNodeLightPath')
    amb = nt.nodes.new('ShaderNodeBackground')
    amb.inputs['Color'].default_value = (1.0, 1.0, 1.0, 1.0)
    amb.inputs['Strength'].default_value = ambient / math.pi
    bg = nt.nodes.new('ShaderNodeBackground')
    bg.inputs['Color'].default_value = _lin(background) + (1.0,)
    bg.inputs['Strength'].default_value = 1.0
    mix = nt.nodes.new('ShaderNodeMixShader')
    out = nt.nodes.new('ShaderNodeOutputWorld')
    nt.links.new(lp.outputs['Is Camera Ray'], mix.inputs['Fac'])
    nt.links.new(amb.outputs['Background'], mix.inputs[1])
    nt.links.new(bg.outputs['Background'], mix.inputs[2])
    nt.links.new(mix.outputs['Shader'], out.inputs['Surface'])
    w['eido_course_ambient'] = ambient
    return w


def course_sun(collection, name='course_sun', intensity=SUN_INTENSITY, color=SUN_COLOR, position=SUN_POSITION,
               angle_deg=1.0):
    ld = bpy.data.lights.new(name, 'SUN')
    ld.energy = intensity
    ld.color = _lin(color)
    ld.angle = math.radians(angle_deg)
    ld.use_shadow = True
    ob = bpy.data.objects.new(name, ld)
    to_light = Vector(b(*position)).normalized()
    ob.rotation_euler = (-to_light).to_track_quat('-Z', 'Y').to_euler()
    ob.location = Vector(b(*position))
    collection.objects.link(ob)
    return ob


def course_camera(collection, name='course_camera', fov_v=FOV_V, near=0.1, far=200.0):
    cd = bpy.data.cameras.new(name)
    cd.sensor_fit = 'VERTICAL'
    cd.angle = math.radians(fov_v)
    cd.clip_start, cd.clip_end = near, far
    ob = bpy.data.objects.new(name, cd)
    collection.objects.link(ob)
    return ob


class Stage:
    def __init__(self, world, sun, camera):
        self.world, self.sun, self.camera = world, sun, camera


def course_stage(scene, course=None, collection=None, camera=True, fps=None):
    """the template's lights, backdrop and camera on `scene` (the course's own collection by default).
    fps: the template ran at FPS (30); pass it to set the scene's rate (a harness scene's config owns its rate)."""
    coll = collection or (course.collection if course is not None else scene.collection)
    w = course_world()
    scene.world = w
    sun = course_sun(coll)
    cam = None
    if camera:
        cam = course_camera(coll)
        scene.camera = cam
        if course is not None:              # the side mode on a body at the start (hips ~0.9 m up)
            look_at(cam, (5.0, course.start[1], 0.9 + 0.2), (0.0, course.start[1], 0.9 - 0.5))
    if fps:
        scene.render.fps = int(fps)
        scene.render.fps_base = 1.0
    return Stage(w, sun, cam)


def look_at(cam, position, target):
    cam.location = Vector(position)
    d = Vector(target) - Vector(position)
    cam.rotation_euler = d.to_track_quat('-Z', 'Y').to_euler()
