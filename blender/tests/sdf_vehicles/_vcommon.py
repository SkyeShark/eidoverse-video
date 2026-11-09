"""Shared scaffolding of the SDF vehicle tests, on top of the SDF tests' own (blender/tests/sdf/_common.py: PASS/FAIL
lines, renders, sheets, linear PNGs).

    stage(...)            EEVEE + AgX, the engine's check-scene city HDRI as world (reflections are the point here),
                          a sun, a ground plane; the HDRI is read from the production workspace's _reality_check
                          (read only), and a plain sky colour stands in when that folder is not on the machine
    three(x, y, z)        a three.js point or direction in Blender axes
    camera_three(...)     a camera placed in three coordinates with three's vertical field of view
    three_quarter(obj)    a camera at a 3/4 view of an object (azimuth from its front, elevation, distance)
    silhouette_iou(...)   the mesh's camera coverage (BVH rays) against the engine's raymarch coverage
"""

from __future__ import annotations

import math
import os
import sys

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
SDF_TESTS = os.path.normpath(os.path.join(HERE, '..', 'sdf'))
if SDF_TESTS not in sys.path:
    sys.path.insert(0, SDF_TESTS)
import _common as C  # noqa: E402  (also puts <repo>/blender on sys.path)

OUT = os.path.join(HERE, 'out')
os.makedirs(OUT, exist_ok=True)
CACHE = os.path.join(OUT, 'cache')
CHECK = r'C:/Users/sdn52/OneDrive/Desktop/new_twitter_harness/generated_videos/ffmpeg/workspace/_reality_check'
HDRI = os.path.join(CHECK, 'hdri.hdr')

check = C.check
summary = C.summary
render = C.render
sheet = C.sheet
save_linear_png = C.save_linear_png


def args():
    argv = sys.argv[sys.argv.index('--') + 1:] if '--' in sys.argv else []
    return dict(a.split('=', 1) for a in argv if '=' in a)


def three(x, y, z):
    return (x, -z, y)


def stage(width=960, height=540, samples=16, hdri=True, hdri_strength=1.0, sun_energy=3.0,
          sun_dir3=(5.0, 9.0, 4.0), sun_angle=1.0, ground=True, ground_z=0.0, ground_size=60.0,
          ground_color=(0.2158, 0.2158, 0.2158), ground_roughness=0.3, ground_metallic=0.2, background=None):
    """A vehicle stage. The defaults are the engine's check scenes': its city HDRI, a key light from three
    (5, 9, 4), a glossy mid-grey ground (0x808080, roughness 0.3, metalness 0.2)."""
    import bpy
    from mathutils import Vector
    sc = C.stage(width, height, samples, floor=False, sun=False)
    sc.eevee.use_raytracing = True
    try:
        sc.eevee.ray_tracing_options.resolution_scale = '1'
        sc.eevee.ray_tracing_options.screen_trace_quality = 0.5
    except (AttributeError, TypeError):
        pass
    sc.eevee.use_fast_gi = True
    nt = sc.world.node_tree
    bg = nt.nodes['Background']
    if hdri and os.path.exists(HDRI):
        env = nt.nodes.new('ShaderNodeTexEnvironment')
        env.image = bpy.data.images.load(HDRI, check_existing=True)
        nt.links.new(env.outputs['Color'], bg.inputs['Color'])
        bg.inputs['Strength'].default_value = hdri_strength
    else:
        bg.inputs['Color'].default_value = (0.45, 0.5, 0.58, 1.0)
        bg.inputs['Strength'].default_value = 0.8
    if background is not None:
        # a solid camera background (the badge close-up's #06141e) while the HDRI still lights and reflects
        lp = nt.nodes.new('ShaderNodeLightPath')
        mix = nt.nodes.new('ShaderNodeMixShader')
        bg2 = nt.nodes.new('ShaderNodeBackground')
        bg2.inputs['Color'].default_value = (*background, 1.0)
        out = nt.nodes['World Output']
        nt.links.new(lp.outputs['Is Camera Ray'], mix.inputs['Fac'])
        nt.links.new(bg.outputs['Background'], mix.inputs[1])
        nt.links.new(bg2.outputs['Background'], mix.inputs[2])
        nt.links.new(mix.outputs['Shader'], out.inputs['Surface'])
    if sun_energy:
        ld = bpy.data.lights.new('key', 'SUN')
        ld.energy = sun_energy
        ld.angle = math.radians(sun_angle)
        ob = bpy.data.objects.new('key', ld)
        sc.collection.objects.link(ob)
        ob.rotation_euler = Vector(three(*sun_dir3)).normalized().to_track_quat('Z', 'Y').to_euler()
    if ground:
        me = bpy.data.meshes.new('ground')
        h = 0.5 * ground_size
        me.from_pydata([(-h, -h, ground_z), (h, -h, ground_z), (h, h, ground_z), (-h, h, ground_z)], [],
                       [(0, 1, 2, 3)])
        g = bpy.data.objects.new('ground', me)
        sc.collection.objects.link(g)
        m = bpy.data.materials.new('ground')
        m.use_nodes = True
        b = m.node_tree.nodes['Principled BSDF']
        b.inputs['Base Color'].default_value = (*ground_color, 1.0)
        b.inputs['Roughness'].default_value = ground_roughness
        b.inputs['Metallic'].default_value = ground_metallic
        me.materials.append(m)
    return sc


def camera_three(pos3, target3, fov_v_deg, name='cam'):
    cam = C.camera(three(*pos3), three(*target3), name=name)
    cam.data.sensor_fit = 'VERTICAL'
    cam.data.angle_y = math.radians(fov_v_deg)
    return cam


def three_quarter(obj, az=35.0, el=12.0, dist=1.15, lens=50.0, aim=0.42, name='cam'):
    """A camera at azimuth `az` degrees from the object's front (three +z, Blender -y), `el` up, `dist` bounding
    diagonals away, aimed `aim` of the way up its height."""
    import bpy
    from mathutils import Vector
    bpy.context.view_layer.update()
    pts = np.array([obj.matrix_world @ Vector(c) for c in obj.bound_box])
    lo, hi = pts.min(axis=0), pts.max(axis=0)
    centre = (lo + hi) / 2
    centre[2] = lo[2] + (hi[2] - lo[2]) * aim
    diag = float(np.linalg.norm(hi - lo))
    a, e = math.radians(az), math.radians(el)
    rot = obj.matrix_world.to_3x3().normalized()
    off = rot @ Vector((math.sin(a) * math.cos(e), -math.cos(a) * math.cos(e), 0.0))
    off.z = math.sin(e)
    off = off.normalized() * diag * dist * 1.6
    return C.camera(tuple(Vector(centre) + off), tuple(centre), lens=lens, name=name)


def mesh_coverage(obj, cam, w, h):
    """(h, w) bool: camera rays (pixel centres) that hit the mesh, by BVH ray casts in the object's space."""
    import bpy
    from mathutils.bvhtree import BVHTree
    sc = bpy.context.scene
    dg = bpy.context.evaluated_depsgraph_get()
    bvh = BVHTree.FromObject(obj, dg)
    inv = obj.matrix_world.inverted()
    frame = cam.data.view_frame(scene=sc)
    tr, br, bl = frame[0], frame[1], frame[2]
    origin = inv @ cam.matrix_world.translation
    m3 = inv.to_3x3() @ cam.matrix_world.to_3x3()
    m = np.zeros((h, w), bool)
    for j in range(h):
        v = 1.0 - (j + 0.5) / h
        for i in range(w):
            u = (i + 0.5) / w
            d = (m3 @ (bl + (br - bl) * u + (tr - br) * v)).normalized()
            m[j, i] = bvh.ray_cast(origin, d)[0] is not None
    return m


def silhouette_iou(car, cam, w, h):
    """IoU of the mesh's coverage and the engine's raymarch coverage, at w x h."""
    ref = car.raymarch_reference(cam, w, h, samples=1)
    m_ref = ref[::-1, :, 3] > 0.5
    m_mesh = mesh_coverage(car.object, cam, w, h)
    inter = float((m_ref & m_mesh).sum())
    union = max(1.0, float((m_ref | m_mesh).sum()))
    return inter / union, float(m_mesh.mean()), float(m_ref.mean())


def closed_fraction(contour):
    """The share of the mesh's edges that are shared by exactly two quads (1.0: closed, manifold)."""
    q = contour.quads
    e = np.sort(np.stack([q, np.roll(q, -1, axis=1)], -1).reshape(-1, 2), axis=1)
    _u, cnt = np.unique(e, axis=0, return_counts=True)
    return float(np.mean(cnt == 2)), int((cnt != 2).sum()), len(cnt)


def faces_per_material(obj):
    me = obj.data
    idx = np.empty(len(me.polygons), np.int32)
    me.polygons.foreach_get('material_index', idx)
    counts = np.bincount(idx, minlength=len(me.materials))
    return {me.materials[i].get('sdf_vehicle_part', me.materials[i].name): int(c) for i, c in enumerate(counts)
            if me.materials[i] is not None}


def read_rgb(path):
    import OpenImageIO as oiio
    return np.asarray(oiio.ImageBuf(path).get_pixels(oiio.FLOAT))[..., :3]


def save_rgb(path, a):
    import OpenImageIO as oiio
    data = np.ascontiguousarray((np.clip(a, 0.0, 1.0) * 255 + 0.5).astype(np.uint8))
    out = oiio.ImageOutput.create(path)
    out.open(path, oiio.ImageSpec(data.shape[1], data.shape[0], 3, 'uint8'))
    out.write_image(data)
    out.close()
    return path


def engine_frame(fname, w, h):
    """One of the engine's check-scene frames, resized to w x h (RGB floats), or None when it is not here."""
    import OpenImageIO as oiio
    p = os.path.join(CHECK, fname)
    if not os.path.exists(p):
        return None
    buf = oiio.ImageBuf(p)
    small = oiio.ImageBufAlgo.resize(buf, roi=oiio.ROI(0, w, 0, h, 0, 1, 0, 3))
    return np.asarray(small.get_pixels(oiio.FLOAT))[..., :3]


def free_images():
    import bpy
    for img in list(bpy.data.images):
        if img.users == 0:
            bpy.data.images.remove(img)


def purge():
    """Drop the objects of the last stage and every orphaned datablock (a car's mesh is a few hundred MB)."""
    import bpy
    C.clear_scene()
    try:
        bpy.data.orphans_purge(do_local_ids=True, do_linked_ids=True, do_recursive=True)
    except (AttributeError, TypeError, RuntimeError):
        for coll in (bpy.data.meshes, bpy.data.materials, bpy.data.lights, bpy.data.cameras, bpy.data.images,
                     bpy.data.node_groups):
            for d in list(coll):
                if d.users == 0:
                    coll.remove(d)
