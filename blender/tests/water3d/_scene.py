"""Shared scene setup for the water3d probes: a clean EEVEE scene, the engine's camera and lights in Blender
axes, small materials. Test scaffolding only (the systems under test are eidoblend.fx.water3d, water_flat,
stable_fluids)."""

import math
import os
import sys

import bpy
import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.normpath(os.path.join(HERE, '..', '..')))
from eidoblend.fx._util import color, from_three  # noqa: E402

OUT = os.path.join(HERE, 'out')
os.makedirs(OUT, exist_ok=True)


def args():
    a = sys.argv[sys.argv.index('--') + 1:] if '--' in sys.argv else []
    return dict(x.split('=', 1) for x in a if '=' in x)


def fresh_scene(res=(960, 540), fps=30, end=180, samples=16):
    for ob in list(bpy.data.objects):
        bpy.data.objects.remove(ob, do_unlink=True)
    sc = bpy.context.scene
    sc.render.engine = 'BLENDER_EEVEE'
    sc.render.resolution_x, sc.render.resolution_y = res
    sc.render.fps = fps
    sc.frame_start, sc.frame_end = 1, end
    sc.eevee.taa_render_samples = samples
    sc.eevee.use_raytracing = True
    sc.eevee.ray_tracing_method = 'SCREEN'
    sc.eevee.use_shadows = True
    sc.view_settings.view_transform = 'AgX'
    sc.render.image_settings.file_format = 'PNG'
    return sc


def camera_three(sc, pos3, look3, fov_v_deg, name='cam'):
    cd = bpy.data.cameras.new(name)
    cd.sensor_fit = 'VERTICAL'
    cd.angle = math.radians(fov_v_deg)
    cd.clip_start, cd.clip_end = 0.05, 200
    cam = bpy.data.objects.new(name, cd)
    sc.collection.objects.link(cam)
    cam.location = tuple(from_three(pos3))
    from mathutils import Vector
    d = Vector(tuple(from_three(look3))) - cam.location
    cam.rotation_mode = 'QUATERNION'
    cam.rotation_quaternion = d.to_track_quat('-Z', 'Y')
    sc.camera = cam
    return cam


def sun_three(sc, name, pos3, col, strength, shadow=True, angle_deg=1.0):
    """A directional light shining from pos3 toward the origin (three's DirectionalLight)."""
    from mathutils import Vector
    ld = bpy.data.lights.new(name, 'SUN')
    ld.energy = strength
    ld.color = color(col)
    ld.angle = math.radians(angle_deg)
    ld.use_shadow = shadow
    o = bpy.data.objects.new(name, ld)
    sc.collection.objects.link(o)
    d = -Vector(tuple(from_three(pos3))).normalized()
    o.rotation_mode = 'QUATERNION'
    o.rotation_quaternion = d.to_track_quat('-Z', 'Y')
    return o


def world_backdrop(sc, camera_col, ambient_col, ambient_strength, sky_grad=None, glossy=None, match_display=False):
    """Camera rays see camera_col (the engine's scene.background); everything else is lit by an ambient world
    (the engine's AmbientLight), or by a zenith-to-horizon gradient when sky_grad=(zenith, horizon, strength).
    glossy=(colour, strength): what reflections see (EEVEE's world tells glossy from diffuse rays). With
    match_display the camera colour is display-matched: the scene's view shows it as the engine's sRGB canvas."""
    if match_display and camera_col is not None:
        from eidoblend.fx.water3d.material import display_matched
        camera_col = display_matched(sc, color(camera_col))
    w = bpy.data.worlds.new('backdrop')
    w.use_nodes = True
    nt = w.node_tree
    bg = nt.nodes['Background']
    out = nt.nodes['World Output']
    if sky_grad:
        tc = nt.nodes.new('ShaderNodeTexCoord')
        sep = nt.nodes.new('ShaderNodeSeparateXYZ')
        nt.links.new(tc.outputs['Generated'], sep.inputs[0])
        mr = nt.nodes.new('ShaderNodeMapRange')
        mr.inputs['From Min'].default_value = -0.1
        mr.inputs['From Max'].default_value = 0.7
        nt.links.new(sep.outputs['Z'], mr.inputs['Value'])
        mx = nt.nodes.new('ShaderNodeMix')
        mx.data_type = 'RGBA'
        mx.inputs['A'].default_value = (*color(sky_grad[1]), 1)
        mx.inputs['B'].default_value = (*color(sky_grad[0]), 1)
        nt.links.new(mr.outputs['Result'], mx.inputs['Factor'])
        nt.links.new(mx.outputs['Result'], bg.inputs['Color'])
        bg.inputs['Strength'].default_value = sky_grad[2]
    else:
        bg.inputs['Color'].default_value = (*color(ambient_col), 1)
        bg.inputs['Strength'].default_value = ambient_strength
    if glossy is not None:
        gl_bg = nt.nodes.new('ShaderNodeBackground')
        gl_bg.inputs['Color'].default_value = (*color(glossy[0]), 1)
        gl_bg.inputs['Strength'].default_value = glossy[1]
        lpg = nt.nodes.new('ShaderNodeLightPath')
        mixg = nt.nodes.new('ShaderNodeMixShader')
        nt.links.new(lpg.outputs['Is Glossy Ray'], mixg.inputs['Fac'])
        nt.links.new(bg.outputs[0], mixg.inputs[1])
        nt.links.new(gl_bg.outputs[0], mixg.inputs[2])
        bg = mixg
    if camera_col is not None:
        cam_bg = nt.nodes.new('ShaderNodeBackground')
        cam_bg.inputs['Color'].default_value = (*color(camera_col), 1)
        lp = nt.nodes.new('ShaderNodeLightPath')
        mix = nt.nodes.new('ShaderNodeMixShader')
        nt.links.new(lp.outputs['Is Camera Ray'], mix.inputs['Fac'])
        nt.links.new(bg.outputs[0], mix.inputs[1])
        nt.links.new(cam_bg.outputs[0], mix.inputs[2])
        nt.links.new(mix.outputs[0], out.inputs['Surface'])
    else:
        nt.links.new(bg.outputs[0], out.inputs['Surface'])
    sc.world = w
    return w


def principled(name, col, rough=0.5, metal=0.0, alpha=None, blended=False, transmission=0.0, ior=1.45):
    m = bpy.data.materials.new(name)
    m.use_nodes = True
    p = m.node_tree.nodes['Principled BSDF']
    p.inputs['Base Color'].default_value = (*color(col), 1)
    p.inputs['Roughness'].default_value = rough
    p.inputs['Metallic'].default_value = metal
    p.inputs['IOR'].default_value = ior
    if transmission:
        p.inputs['Transmission Weight'].default_value = transmission
        m.use_raytrace_refraction = True
    if alpha is not None:
        p.inputs['Alpha'].default_value = alpha
    if blended:
        m.surface_render_method = 'BLENDED'
        m.use_transparency_overlap = True
    return m


def texset(name):
    """A CC0 texture set's folder in the shared texture cache, the first root that has it
    (eidoblend.terrain.texture_roots: this checkout's, $EIDO_TEXTURE_CACHE, $EIDO_ASSET_CACHE, the main checkout's
    when this one is a git worktree). Without it the bare name comes back, a folder that is not there: pbr() then
    leaves the maps off."""
    from eidoblend.terrain import texture_roots
    return next((str(r / name) for r in texture_roots() if (r / name).is_dir()), name)


def pbr(name, tex_dir, stem, scale=1.0, tint=None, rough_mul=1.0, normal_strength=1.0, metal=None):
    """A CC0 PBR set (the shared texture cache) box-projected on object coordinates, so lathes and boxes need no
    UVs. tint multiplies the colour map."""
    m = bpy.data.materials.new(name)
    m.use_nodes = True
    nt = m.node_tree
    p = nt.nodes['Principled BSDF']
    tc = nt.nodes.new('ShaderNodeTexCoord')
    mp = nt.nodes.new('ShaderNodeMapping')
    mp.inputs['Scale'].default_value = (scale, scale, scale)
    nt.links.new(tc.outputs['Object'], mp.inputs['Vector'])

    def tex(suffix, data):
        path = os.path.join(tex_dir, f'{stem}_{suffix}.jpg')
        if not os.path.exists(path):
            return None
        n = nt.nodes.new('ShaderNodeTexImage')
        n.image = bpy.data.images.load(path, check_existing=True)
        if data:
            n.image.colorspace_settings.is_data = True
        n.projection = 'BOX'
        n.projection_blend = 0.25
        nt.links.new(mp.outputs['Vector'], n.inputs['Vector'])
        return n

    c = tex('Color', False)
    if c is not None:
        if tint is not None:
            mx = nt.nodes.new('ShaderNodeMix')
            mx.data_type = 'RGBA'
            mx.blend_type = 'MULTIPLY'
            mx.inputs['Factor'].default_value = 1.0
            nt.links.new(c.outputs['Color'], mx.inputs['A'])
            mx.inputs['B'].default_value = (*color(tint), 1)
            nt.links.new(mx.outputs['Result'], p.inputs['Base Color'])
        else:
            nt.links.new(c.outputs['Color'], p.inputs['Base Color'])
    r = tex('Roughness', True)
    if r is not None:
        mr = nt.nodes.new('ShaderNodeMath')
        mr.operation = 'MULTIPLY'
        mr.inputs[1].default_value = rough_mul
        nt.links.new(r.outputs['Color'], mr.inputs[0])
        nt.links.new(mr.outputs[0], p.inputs['Roughness'])
    nrm = tex('NormalGL', True)
    if nrm is not None:
        nm = nt.nodes.new('ShaderNodeNormalMap')
        nm.inputs['Strength'].default_value = normal_strength
        nt.links.new(nrm.outputs['Color'], nm.inputs['Color'])
        nt.links.new(nm.outputs['Normal'], p.inputs['Normal'])
    mt = tex('Metalness', True)
    if mt is not None:
        nt.links.new(mt.outputs['Color'], p.inputs['Metallic'])
    elif metal is not None:
        p.inputs['Metallic'].default_value = metal
    return m


def lathe(sc, name, profile, segments=64, loc=(0, 0, 0), mat=None):
    """A closed solid of revolution about +Z from an (r, z) profile that starts and ends on the axis (r = 0): a
    watertight mesh, so the water's ray-parity voxeliser reads it as solid."""
    verts, rings = [], []
    for r, z in profile:
        if r <= 1e-9:
            rings.append([len(verts)])
            verts.append((0.0, 0.0, z))
        else:
            ring = []
            for s in range(segments):
                a = 2 * math.pi * s / segments
                ring.append(len(verts))
                verts.append((r * math.cos(a), r * math.sin(a), z))
            rings.append(ring)
    faces = []
    for a, b in zip(rings[:-1], rings[1:]):
        if len(a) == 1 and len(b) == 1:
            continue
        if len(a) == 1:
            faces += [(a[0], b[(s + 1) % segments], b[s]) for s in range(segments)]
        elif len(b) == 1:
            faces += [(a[s], a[(s + 1) % segments], b[0]) for s in range(segments)]
        else:
            faces += [(a[s], a[(s + 1) % segments], b[(s + 1) % segments], b[s]) for s in range(segments)]
    me = bpy.data.meshes.new(name)
    me.from_pydata(verts, [], faces)
    me.validate()
    for poly in me.polygons:
        poly.use_smooth = True
    ob = bpy.data.objects.new(name, me)
    sc.collection.objects.link(ob)
    ob.location = loc
    if mat:
        me.materials.append(mat)
    return ob


def world_panorama(sc, path, strength=1.0, rotate_deg=0.0):
    """An equirectangular sky image as the world (what the camera, reflections and diffuse light all see)."""
    w = bpy.data.worlds.new('panorama')
    w.use_nodes = True
    nt = w.node_tree
    bg = nt.nodes['Background']
    env = nt.nodes.new('ShaderNodeTexEnvironment')
    env.image = bpy.data.images.load(path, check_existing=True)
    tc = nt.nodes.new('ShaderNodeTexCoord')
    mp = nt.nodes.new('ShaderNodeMapping')
    mp.inputs['Rotation'].default_value = (0, 0, math.radians(rotate_deg))
    nt.links.new(tc.outputs['Generated'], mp.inputs['Vector'])
    nt.links.new(mp.outputs['Vector'], env.inputs['Vector'])
    nt.links.new(env.outputs['Color'], bg.inputs['Color'])
    bg.inputs['Strength'].default_value = strength
    sc.world = w
    return w


def sun(sc, name, azimuth_deg, elevation_deg, strength, col=(1.0, 0.96, 0.9), angle_deg=0.6):
    """A sun lamp shining from (azimuth from +X toward +Y, elevation) in Blender axes."""
    from mathutils import Vector
    ld = bpy.data.lights.new(name, 'SUN')
    ld.energy = strength
    ld.color = col
    ld.angle = math.radians(angle_deg)
    o = bpy.data.objects.new(name, ld)
    sc.collection.objects.link(o)
    az, el = math.radians(azimuth_deg), math.radians(elevation_deg)
    to_sun = Vector((math.cos(el) * math.cos(az), math.cos(el) * math.sin(az), math.sin(el)))
    o.rotation_mode = 'QUATERNION'
    o.rotation_quaternion = (-to_sun).to_track_quat('-Z', 'Y')
    return o


def camera_look(sc, pos, target, lens=40.0, name='cam'):
    from mathutils import Vector
    cd = bpy.data.cameras.new(name)
    cd.lens = lens
    cd.clip_start, cd.clip_end = 0.02, 300
    cam = bpy.data.objects.new(name, cd)
    sc.collection.objects.link(cam)
    cam.location = pos
    cam.rotation_mode = 'QUATERNION'
    cam.rotation_quaternion = (Vector(target) - Vector(pos)).to_track_quat('-Z', 'Y')
    sc.camera = cam
    return cam


def box(sc, name, size, loc, mat=None):
    me = bpy.data.meshes.new(name)
    sx, sy, sz = (s / 2 for s in size)
    v = [(-sx, -sy, -sz), (sx, -sy, -sz), (sx, sy, -sz), (-sx, sy, -sz),
         (-sx, -sy, sz), (sx, -sy, sz), (sx, sy, sz), (-sx, sy, sz)]
    f = [(0, 3, 2, 1), (4, 5, 6, 7), (0, 1, 5, 4), (1, 2, 6, 5), (2, 3, 7, 6), (3, 0, 4, 7)]
    me.from_pydata(v, [], f)
    ob = bpy.data.objects.new(name, me)
    sc.collection.objects.link(ob)
    ob.location = loc
    if mat:
        me.materials.append(mat)
    return ob


def render(sc, frame, path):
    sc.frame_set(frame)
    sc.render.filepath = path
    bpy.ops.render.render(write_still=True)
    ok = os.path.exists(path)
    print(('PASS' if ok else 'FAIL') + f' render frame {frame} -> {path}', flush=True)
    return ok


def fcurves_of(idb):
    """The F-curves of an ID's action (Blender 5's layered actions: the slot's channelbag)."""
    ad = getattr(idb, 'animation_data', None)
    if ad is None or ad.action is None:
        return []
    try:
        from bpy_extras import anim_utils
        cb = anim_utils.action_get_channelbag_for_slot(ad.action, ad.action_slot)
        return list(cb.fcurves) if cb is not None else []
    except Exception:
        return list(getattr(ad.action, 'fcurves', []))


def key_path(obj, frames_values, data_path='location'):
    """Key obj.<data_path> at each (frame, value), LINEAR (Python inserts ignore the interpolation preference)."""
    for f, v in frames_values:
        setattr(obj, data_path, v)
        obj.keyframe_insert(data_path, frame=f)
    for fc in fcurves_of(obj):
        if fc.data_path == data_path:
            for kp in fc.keyframe_points:
                kp.interpolation = 'LINEAR'


def check(name, ok, detail=''):
    print(('PASS ' if ok else 'FAIL ') + name + (('  ' + detail) if detail else ''), flush=True)
    return ok


def read_png(path):
    """(H, W, 3) uint8 of a PNG, row 0 = top (OpenImageIO, which Blender ships)."""
    import OpenImageIO as oiio
    inp = oiio.ImageInput.open(path)
    a = inp.read_image('uint8')
    inp.close()
    a = np.asarray(a)
    return a[..., :3] if a.ndim == 3 else np.repeat(a[..., None], 3, axis=2)


def write_png(path, a):
    import OpenImageIO as oiio
    a = np.ascontiguousarray(np.asarray(a, dtype=np.uint8))
    spec = oiio.ImageSpec(a.shape[1], a.shape[0], a.shape[2], 'uint8')
    o = oiio.ImageOutput.create(path)
    o.open(path, spec)
    o.write_image(a)
    o.close()


def contact_sheet(paths, out, cols=4, half=True):
    """Tile rendered PNGs (2x2-averaged to half size by default) into one sheet in the order given, so a run's
    frames are judged side by side."""
    ims = [read_png(p) for p in paths if os.path.exists(p)]
    if not ims:
        return None
    if half:
        def _half(a):
            hh, ww = a.shape[0] // 2, a.shape[1] // 2
            return a[:hh * 2, :ww * 2].reshape(hh, 2, ww, 2, 3).mean(axis=(1, 3)).astype(np.uint8)
        ims = [_half(a) for a in ims]
    h, w = ims[0].shape[:2]
    rows = (len(ims) + cols - 1) // cols
    sheet = np.zeros((h * rows, w * cols, 3), dtype=np.uint8)
    for i, a in enumerate(ims):
        r, c = divmod(i, cols)
        sheet[r * h:(r + 1) * h, c * w:(c + 1) * w] = a[:h, :w]
    write_png(out, sheet)
    print('sheet ->', out, flush=True)
    return out
