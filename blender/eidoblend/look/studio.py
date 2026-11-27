"""eidoblend.look.studio: the judging room for an asset's look, in EEVEE.

    from eidoblend.look import studio
    shoot = studio.studio(bpy.context.scene, balls_at=(-0.16, 0.05, 0.06), ball_r=0.02)
    shoot('out/left_three_quarter.png', centre=(0.2, 0.0, -0.03), pos=(0.35, 1.15, 0.45), lens=50, res=(960, 540))

studio(scene) replaces the scene's lights, camera and world with a lookdev room: a world that is a soft gradient with
three softboxes in it (a key from front-left above, a fill, a rim) which the lens never sees (camera rays see flat
0.07 grey), an area key that casts the shadow and an area rim, both re-aimed for each shot from the side the camera
stands on, and (balls_at) an 18 % grey ball and a mirror ball beside the asset: read the grey ball's lit side to judge
exposure (under AgX at level 0.36 it reads near 120-136 of 255) and the mirror ball to see the room. Everything it adds
is in the collection 'lookdev_only'. shoot(path, centre, pos, ...) aims the camera from centre + pos at centre (metres;
ortho= an orthographic width), places the lights for that side (reach: their distance as a multiple of a hand-held
prop's set-up; a room's furniture wants 3-5) and renders a still. eevee(scene, samples) sets EEVEE with ray tracing and
AgX, which studio() also does.
"""

from __future__ import annotations

import math

import bmesh
import bpy
from mathutils import Vector

from ..materials.layered import NT


def eevee(sc, samples=64):
    """EEVEE with ray tracing and shadows, `samples` render samples, AgX with no look."""
    sc.render.engine = 'BLENDER_EEVEE'
    sc.eevee.use_raytracing = True
    sc.eevee.taa_render_samples = samples
    sc.eevee.use_shadows = True
    sc.view_settings.view_transform = 'AgX'
    sc.view_settings.look = 'None'


def studio(sc, balls_at=None, ball_r=0.02, level=0.36, samples=64):
    """The room (see the module doc) -> shoot(path, centre, pos, lens=50, ortho=None, res=(1920, 1080),
    key_from=(-0.9, -1.0, 1.0), key_w=22.0, reach=1.0)."""
    eevee(sc, samples)
    for o in list(sc.objects):
        if o.type in ('LIGHT', 'CAMERA'):
            bpy.data.objects.remove(o, do_unlink=True)
    look = bpy.data.collections.new('lookdev_only')
    sc.collection.children.link(look)
    w = bpy.data.worlds.new('studio')
    w.use_nodes = True
    sc.world = w
    t = NT(w.node_tree)
    for n in list(t.N):
        if n.type != 'OUTPUT_WORLD':
            t.N.remove(n)
    tc = t.N.new('ShaderNodeTexCoord')
    dsep = t.N.new('ShaderNodeSeparateXYZ')
    t.L.new(tc.outputs['Generated'], dsep.inputs[0])
    lum = t.lin(t.sm(dsep.outputs[2], -0.4, 0.9), 0.0, 1.0, 0.03, 0.42)

    def box(direction, half_deg, power):
        dn = t.N.new('ShaderNodeVectorMath')
        dn.operation = 'DOT_PRODUCT'
        t.L.new(tc.outputs['Generated'], dn.inputs[0])
        dn.inputs[1].default_value = Vector(direction).normalized()
        c = math.cos(math.radians(half_deg))
        return t.mul(t.sm(dn.outputs['Value'], c - 0.02, c + 0.02), power)
    lum = t.add(t.add(lum, box((-0.55, -0.6, 0.6), 24.0, 7.0)), t.add(box((0.8, -0.35, 0.3), 30.0, 1.6), box((0.25, 0.85, 0.45), 18.0, 4.0)))
    lum = t.mul(lum, level)
    lp = t.N.new('ShaderNodeLightPath')
    bg = t.N.new('ShaderNodeBackground')
    t.L.new(t.mixf(lp.outputs['Is Camera Ray'], lum, 0.07), bg.inputs['Strength'])
    bg.inputs['Color'].default_value = (1, 1, 1, 1)
    t.L.new(bg.outputs[0], next(n for n in t.N if n.type == 'OUTPUT_WORLD').inputs[0])

    def lamp(name, energy, size):
        o = bpy.data.objects.new(name, bpy.data.lights.new(name, 'AREA'))
        o.data.energy, o.data.size = energy, size
        look.objects.link(o)
        return o
    key, rim = lamp('studio_key', 22.0, 0.9), lamp('studio_rim', 9.0, 0.5)
    cd = bpy.data.cameras.new('studio_camera')
    cd.clip_start = 0.01
    cam = bpy.data.objects.new('studio_camera', cd)
    look.objects.link(cam)
    sc.camera = cam
    if balls_at is not None:
        for nm, dx, mt in (('grey_ball', 0.0, (0.18, 0.9, 0.0)), ('mirror_ball', 2.5 * ball_r, (0.9, 0.02, 1.0))):
            bm = bmesh.new()
            bmesh.ops.create_uvsphere(bm, u_segments=48, v_segments=24, radius=ball_r)
            me = bpy.data.meshes.new(nm)
            bm.to_mesh(me)
            bm.free()
            for p in me.polygons:
                p.use_smooth = True
            mm = bpy.data.materials.new(nm)
            mm.use_nodes = True
            b_ = mm.node_tree.nodes['Principled BSDF']
            b_.inputs['Base Color'].default_value = (mt[0], mt[0], mt[0], 1)
            b_.inputs['Roughness'].default_value, b_.inputs['Metallic'].default_value = mt[1], mt[2]
            me.materials.append(mm)
            ob = bpy.data.objects.new(nm, me)
            ob.location = (balls_at[0] + dx, balls_at[1], balls_at[2])
            look.objects.link(ob)

    def aim(o, at, frm):
        o.location = Vector(at) + Vector(frm)
        o.rotation_euler = (Vector(at) - o.location).to_track_quat('-Z', 'Y').to_euler()

    def shoot(path, centre, pos, lens=50, ortho=None, res=(1920, 1080), key_from=(-0.9, -1.0, 1.0), key_w=22.0, reach=1.0):
        aim(cam, centre, pos)
        if ortho:
            cd.type, cd.ortho_scale = 'ORTHO', ortho
        else:
            cd.type, cd.lens = 'PERSP', lens
        side = 1.0 if pos[1] < 0 else -1.0
        aim(key, centre, (key_from[0] * reach, key_from[1] * side * reach, key_from[2] * reach))
        aim(rim, centre, (0.5 * reach, 1.0 * side * reach, 0.5 * reach))
        key.data.energy, rim.data.energy = key_w * reach * reach, 9.0 * reach * reach
        key.data.size, rim.data.size = 0.9 * reach, 0.5 * reach
        sc.render.resolution_x, sc.render.resolution_y = res
        sc.render.resolution_percentage = 100
        sc.render.filepath = path
        bpy.ops.render.render(write_still=True)
        return path
    return shoot
