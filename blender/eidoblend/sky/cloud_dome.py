"""The cloud dome: clouds drawn over distant geometry, as WebGPU's 3 km cloud dome draws them.

EEVEE's world is behind everything, so without this a mountain 10 km away draws over clouds that WebGPU's dome
(radius DOME_R * 0.96 = 3072 m, depth-tested against the scene) draws over it. The dome is a sphere around the camera
whose material shows the frame's CLOUD layer (premultiplied, through the keyed bake camera, sky_view): geometry nearer
than its radius occludes it, geometry beyond it gets the clouds over it. With the dome on, the world shows the sky
BEHIND the clouds (sky_back), the dome adds them; the sky elements keep compositing the shield, and the clouds only
where they are nearer than the dome (sky_view.overlay_group).

The dome is Blended; EEVEE draws Blended objects farthest ORIGIN first (probe_eevee_facts.py F4), so its origin is
parked far ahead of the camera: the dome draws first, under every other blended surface (the ringworld's cloud sheet
composites the clouds over itself, its haze walls draw over the clouds, as in WebGPU's draw order).
"""
import math

import bpy
import numpy as np

from .nodes import Graph
from .sky_view import project

DOME_R = 3200.0 * 0.96
ORIGIN_AHEAD = 1.0e6


def build_cloud_dome(scene, camera, cloud_img, frame_start, n_frames, radius=DOME_R, collection=None):
    from .world_nodes import _set_user
    name = 'eido_sky_cloud_dome'
    old = bpy.data.objects.get(name)
    if old is not None:
        me_old = old.data
        bpy.data.objects.remove(old, do_unlink=True)
        if me_old.users == 0:
            bpy.data.meshes.remove(me_old)
    # a UV sphere about the camera, in the object's frame whose origin sits ORIGIN_AHEAD down the view axis
    seg, rings = 96, 48
    verts = [(0.0, 0.0, radius)]
    for i in range(1, rings):
        ph = math.pi * i / rings
        for j in range(seg):
            a = 2 * math.pi * j / seg
            verts.append((radius * math.sin(ph) * math.cos(a), radius * math.sin(ph) * math.sin(a), radius * math.cos(ph)))
    verts.append((0.0, 0.0, -radius))
    faces = []
    for j in range(seg):
        faces.append((0, 1 + (j + 1) % seg, 1 + j))
    for i in range(rings - 2):
        for j in range(seg):
            a, b = 1 + i * seg + j, 1 + i * seg + (j + 1) % seg
            faces.append((a, b, b + seg, a + seg))
    last = len(verts) - 1
    base = 1 + (rings - 2) * seg
    for j in range(seg):
        faces.append((base + j, base + (j + 1) % seg, last))
    v = np.array(verts) + np.array([0.0, 0.0, ORIGIN_AHEAD])
    me = bpy.data.meshes.new(name)
    me.from_pydata([tuple(p) for p in v], [], faces)
    me.update()
    ob = bpy.data.objects.new(name, me)
    (collection or scene.collection).objects.link(ob)
    ob.parent = camera
    ob.matrix_parent_inverse.identity()
    ob.location = (0.0, 0.0, -ORIGIN_AHEAD)
    for attr in ('visible_diffuse', 'visible_glossy', 'visible_transmission', 'visible_volume_scatter',
                 'visible_shadow'):
        setattr(ob, attr, False)
    m = bpy.data.materials.new(name)
    m.use_nodes = True
    m.surface_render_method = 'BLENDED'
    m.use_backface_culling = False
    nt = m.node_tree
    nt.nodes.clear()
    g = Graph(nt)
    geo = g.node('ShaderNodeNewGeometry')
    uv, valid = project(g, g.vscale(geo.outputs['Incoming'], -1.0))
    t = g.image(cloud_img, uv, extension='EXTEND', label='eido_dome_cloud')
    _set_user(t, frame_start, n_frames)
    a = g.mul(t.outputs['Alpha'], valid)
    col = g.vscale(t.outputs['Color'], valid)
    em = g.node('ShaderNodeEmission')
    g.link(col, em.inputs['Color'])
    tr = g.node('ShaderNodeBsdfTransparent')
    om = g.one_minus(a)
    g.link(g.comb(om, om, om), tr.inputs['Color'])
    add = g.node('ShaderNodeAddShader')
    g.link(tr.outputs[0], add.inputs[0])
    g.link(em.outputs[0], add.inputs[1])
    out = g.node('ShaderNodeOutputMaterial')
    g.link(add.outputs[0], out.inputs['Surface'])
    me.materials.append(m)
    cd = camera.data
    if cd.clip_end < radius * 1.05:
        cd.clip_end = radius * 1.05
    return ob
