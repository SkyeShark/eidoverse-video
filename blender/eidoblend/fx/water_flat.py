"""eidoblend.fx.water_flat: the flat waters for Blender 5.2 EEVEE: three's WaterMesh and water_compute.js.

    from eidoblend.fx.water_flat import create_water_mesh, create_sky_mesh, create_water_compute, make_water_normals

WaterMesh (three/addons/objects/WaterMesh.js, the flat reflective water eidoverse scenes put under a SkyMesh):

    lake = create_water_mesh(size_xy=(400, 400), location=(0, 0, 0), water_color='#001e0f', sun_color='#ffffff',
                             sun_object=sun_lamp, distortion_scale=3.7, size=1.0)

    Its colour formula, term for term, as nodes: the four scrolled samples of the water normal map at
    positionWorld.xz * size / (103, 107, (8907, 9803), (1091, 1027)) moved by time, surfaceNormal =
    normalize(noise.xzy * (1.5, 1, 1.5)), the sun's pow(.., 100) * 2 specular and 0.5 diffuse, the scatter
    max(0, n.eye) * waterColor and the Schlick reflectance (F0 0.02) mixing them with the mirror. The engine's
    reflector() (a planar render of the scene, UVs pushed by the normal * distortionScale / distance) is EEVEE's
    own: a Glossy closure on the rippled normal, tilted by the engine's push turned into an angle (strong near the
    camera, calm far off), reflecting the scene through a planar light probe made with the water (and ray-traced
    reflections where the probe does not reach).
    The water normal map is the caller's (water_normals=path) or a tileable one generated from an ocean spectrum
    (make_water_normals: no CC0 copy of three's waternormals.jpg was in the asset cache).

SkyMesh (three/addons/objects/SkyMesh.js, the sky liquids.md pairs with WaterMesh), as the scene's world:

    sky = create_sky_mesh(sun_position=(0.5, -0.2, 0.8), turbidity=10, rayleigh=2, cloud_coverage=0.4)

    Its colorNode term for term in shader nodes: the Preetham optical depths, the Rayleigh and Mie phases, the
    extinction, the in-scattering, the sun disc and the fbm cloud layer; sky_mesh_radiance() is the same formula in
    numpy, the reference the graph is checked against.

water_compute.js (createWaterCompute: a height-field wave-equation surface for puddles, ponds, basins, fountains,
rain; NOT 3D liquid):

    pool = create_water_compute(width=128, bounds=4.0, circular=True, location=(0, 0, 0.6))
    def controls(frame, t, w):
        w.disturb(0.3, -0.2, 0.08, 0.004)            # plane-local metres, once per frame (a one-frame impulse)
    pool.bake(1, 240, controls=controls, cache_dir='//pool_cache')

    The engine's kernel in numpy, step for step: h' = ((N + S + E + W) / 2 - h_prev) * viscosity + the cosine
    disturbance, clamped to +-max_height, prev = h, ping-pong; one step per frame as the engine's scenes call it.
    The bake writes each frame's heights as an OpenEXR data image; Geometry Nodes displaces the grid by them and
    stores the engine's shading normal (finite differences, as its normalNode, including its sign and scale), so
    the .blend plays with no Python. The material is the engine's MeshStandardMaterial as a Principled BSDF.
"""

from __future__ import annotations

import math
import os
import random

import numpy as np

from ._util import abspath, color, frame_file, scene_fps

# ------------------------------------------------------------------------------------------------------------
# the water normal map
# ------------------------------------------------------------------------------------------------------------


def make_water_normals(path, size=512, seed=7, wind=(1.0, 0.35), choppiness=1.0, strength=1.0, directional=0.5):
    """Write a tileable tangent-space water normal map (PNG, B up) synthesised from a Phillips ocean spectrum:
    the role three's waternormals.jpg plays for WaterMesh. Returns the path. Regenerable; nothing to license.

    The defaults match that map's statistics, which every WaterMesh scene was made with: a mean slope of about 12
    degrees (90 % under 21), about the same in x and y, some 35 ripples across a tile. directional mixes the wind's
    cos^2 spread with an isotropic one (1 = all along the wind). strength scales the slopes (6.0 gave a mean of 44
    degrees: the sea broke into white blotches wherever the mirror term saw a grazing normal)."""
    rng = np.random.default_rng(seed)
    n = int(size)
    k = np.fft.fftfreq(n) * n
    kx, ky = np.meshgrid(k, k)
    kk = np.hypot(kx, ky)
    kk[0, 0] = 1.0
    w = np.asarray(wind, dtype=np.float64)
    w = w / np.linalg.norm(w)
    L = n / 14.0                                            # the dominant wavelength, in texels
    cos = (kx * w[0] + ky * w[1]) / kk
    spread = (1.0 - directional) + directional * cos ** 2
    ph = np.exp(-1.0 / (kk * L / n * 2 * np.pi) ** 2) / kk ** 4 * spread
    ph *= np.exp(-(kk / (n * 0.35)) ** 2)                   # no aliasing near Nyquist
    ph[0, 0] = 0.0
    amp = np.sqrt(ph / 2) * (rng.standard_normal((n, n)) + 1j * rng.standard_normal((n, n)))
    gx = np.real(np.fft.ifft2(amp * 1j * kx))
    gy = np.real(np.fft.ifft2(amp * 1j * ky))
    s = strength * choppiness / max(np.std(gx), np.std(gy), 1e-12) * 0.18
    nx, ny = -gx * s, -gy * s
    nz = np.ones_like(nx)
    ln = np.sqrt(nx * nx + ny * ny + nz * nz)
    rgb = np.stack([nx / ln, ny / ln, nz / ln], axis=-1) * 0.5 + 0.5
    import OpenImageIO as oiio
    a = np.ascontiguousarray((np.clip(rgb, 0, 1) * 255 + 0.5).astype(np.uint8))
    spec = oiio.ImageSpec(n, n, 3, 'uint8')
    os.makedirs(os.path.dirname(os.path.abspath(path)), exist_ok=True)
    o = oiio.ImageOutput.create(path)
    o.open(path, spec)
    o.write_image(a)
    o.close()
    return path


# ------------------------------------------------------------------------------------------------------------
# WaterMesh
# ------------------------------------------------------------------------------------------------------------

WATER_MESH_DEFAULTS = dict(resolution_scale=0.5, water_normals=None, alpha=1.0, size=1.0, sun_color=0xffffff,
                           sun_direction=(0.70707, 0.70707, 0.0), water_color=0x7f7f7f, distortion_scale=20.0)


def _three_dir_to_blender(v):
    v = np.asarray(v, dtype=np.float64)
    v = v / max(np.linalg.norm(v), 1e-12)
    return (float(v[0]), float(-v[2]), float(v[1]))


class WaterMesh:
    """What create_water_mesh returns: the object (mesh), the material, the planar probe, and the engine's
    uniforms as named nodes (alpha, size, sun_color, sun_direction, water_color, distortion_scale; set_uniform
    writes one, key_uniform keys it)."""

    def __init__(self, obj, material, probe, params):
        self.mesh = obj
        self.object = obj
        self.material = material
        self.probe = probe
        self.params = params
        self.is_water_mesh = True

    def set_uniform(self, key, value):
        n = self.material.node_tree.nodes.get('wm.' + key)
        if n is None:
            raise KeyError(key)
        self.params[key] = value
        if key in ('sun_color', 'water_color'):
            n.outputs[0].default_value = (*color(value), 1.0)
        elif key == 'sun_direction':
            d = _three_dir_to_blender(value)
            for i in range(3):
                n.inputs[i].default_value = d[i]
        else:
            n.outputs[0].default_value = float(value)

    def key_uniform(self, key, frame, value=None):
        if value is not None:
            self.set_uniform(key, value)
        n = self.material.node_tree.nodes['wm.' + key]
        socks = list(n.inputs)[:3] if key == 'sun_direction' else [n.outputs[0]]
        for s in socks:
            s.keyframe_insert('default_value', frame=frame)


def create_water_mesh(size_xy=(100.0, 100.0), location=(0.0, 0.0, 0.0), geometry=None, name='water',
                      scene=None, sun_object=None, planar_probe=True, normals_dir=None, **options):
    """three's new WaterMesh(geometry, options) in Blender. options: WATER_MESH_DEFAULTS (the engine's
    camelCase accepted). geometry: an existing mesh object to use instead of a size_xy plane. sun_object: a
    Blender sun lamp that drives sun_direction (and sun_color from its colour) by drivers. resolution_scale is the
    engine's reflector render scale: EEVEE's planar probe renders at the frame's resolution (kept in params)."""
    import bpy
    from ._nodes import Builder
    o = dict(WATER_MESH_DEFAULTS)
    camel = {'resolutionScale': 'resolution_scale', 'waterNormals': 'water_normals', 'sunColor': 'sun_color',
             'sunDirection': 'sun_direction', 'waterColor': 'water_color', 'distortionScale': 'distortion_scale'}
    for k, v in options.items():
        k2 = camel.get(k, k)
        if k2 not in WATER_MESH_DEFAULTS:
            raise TypeError(f'create_water_mesh: unknown option {k!r}')
        o[k2] = v
    sc = scene or bpy.context.scene
    fps, fs = scene_fps(sc), sc.frame_start
    normals = o['water_normals']
    generated = normals is None
    if generated:
        d = normals_dir or os.path.join(bpy.app.tempdir or os.path.abspath('.'), 'eido_water')
        normals = os.path.join(d, 'water_normals_ripples_512.png')
        if not os.path.exists(normals):
            make_water_normals(normals)
    if isinstance(normals, str):
        img = bpy.data.images.load(normals, check_existing=True)
    else:
        img = normals
    img.colorspace_settings.is_data = True
    if generated and not img.packed_file:
        # the generated map lives in Blender's session temp folder (deleted when Blender exits) unless normals_dir
        # says otherwise: packed, a saved .blend keeps its ripples
        img.pack()

    mat = bpy.data.materials.new(name + '_water')
    mat.use_nodes = True
    mat.surface_render_method = 'BLENDED' if float(o['alpha']) < 1.0 else 'DITHERED'
    nt = mat.node_tree
    nt.nodes.clear()
    out = nt.nodes.new('ShaderNodeOutputMaterial')
    out.location = (1500, 0)
    b = Builder(nt, x0=-2000, y0=700)

    def named_value(key, v):
        n = b.node('ShaderNodeValue')
        n.name = n.label = 'wm.' + key
        n.hide = False
        n.outputs[0].default_value = float(v)
        return b.s(n.outputs[0])

    def named_rgb(key, v):
        n = b.node('ShaderNodeRGB')
        n.name = n.label = 'wm.' + key
        n.hide = False
        n.outputs[0].default_value = (*color(v), 1.0)
        return b.vec(n.outputs[0])

    alpha = named_value('alpha', o['alpha'])
    size = named_value('size', o['size'])
    dist_scale = named_value('distortion_scale', o['distortion_scale'])
    sun_col = named_rgb('sun_color', o['sun_color'])
    water_col = named_rgb('water_color', o['water_color'])
    sd = b.node('ShaderNodeCombineXYZ')
    sd.name = sd.label = 'wm.sun_direction'
    sd.hide = False
    for i, c in enumerate(_three_dir_to_blender(o['sun_direction'])):
        sd.inputs[i].default_value = c
    sun_dir = b.vmath('NORMALIZE', b.vec(sd.outputs[0]))
    tnode = b.node('ShaderNodeValue')
    tnode.name = tnode.label = 'wm.time'
    tnode.hide = False
    drv = tnode.outputs[0].driver_add('default_value').driver
    drv.type = 'SCRIPTED'
    drv.expression = f'(frame - {int(fs)}) / {float(fps):.6g}'
    T = b.s(tnode.outputs[0])

    geo = b.node('ShaderNodeNewGeometry')
    px, py, _pz = b.vec(geo.outputs['Position']).xyz()
    # three's positionWorld.xz = (x, z_three) = (x, -y) in Blender, times size
    ux, uz = px * size, -py * size

    def tap(du, dv):
        n = b.node('ShaderNodeTexImage', interpolation='Linear', extension='REPEAT')
        n.image = img
        b.link(b.combine(du, dv, 0.0), n.inputs['Vector'])
        return b.vec(n.outputs['Color'])

    # getNoise: uv0 = uv / 103 + (t / 17, t / 29); uv1 = uv / 107 - (t / -19, t / 31);
    # uv2 = uv / (8907, 9803) + (t / 101, t / 97); uv3 = uv / (1091, 1027) - (t / 109, t / -113)
    s0 = tap(ux / 103.0 + T / 17.0, uz / 103.0 + T / 29.0)
    s1 = tap(ux / 107.0 + T / 19.0, uz / 107.0 - T / 31.0)
    s2 = tap(ux / 8907.0 + T / 101.0, uz / 9803.0 + T / 97.0)
    s3 = tap(ux / 1091.0 - T / 109.0, uz / 1027.0 + T / 113.0)
    noise = b.vscale(s0 + s1 + s2 + s3, 0.5) - (1.0, 1.0, 1.0)
    nr, ng, nb = noise.xyz()
    # surfaceNormal = normalize(noise.xzy * (1.5, 1, 1.5)) in three axes = (R 1.5, B, G 1.5) -> Blender (R 1.5, -G 1.5, B)
    N = b.vmath('NORMALIZE', b.combine(nr * 1.5, -(ng * 1.5), nb))
    eye = b.vec(geo.outputs['Incoming'])
    refl = b.vmath('NORMALIZE', b.vmath('REFLECT', b.vscale(sun_dir, -1.0), N))
    direction = b.max(b.vmath('DOT_PRODUCT', eye, refl), 0.0)
    spec = b.vscale(sun_col, b.pow(direction, 100.0) * 2.0)
    diffuse = b.vscale(sun_col, b.max(b.vmath('DOT_PRODUCT', sun_dir, N), 0.0) * 0.5)
    theta = b.max(b.vmath('DOT_PRODUCT', eye, N), 0.0)
    rf0 = 0.02
    reflectance = b.pow(1.0 - theta, 5.0) * (1.0 - rf0) + rf0
    scatter = b.vscale(water_col, b.max(b.vmath('DOT_PRODUCT', N, eye), 0.0))
    base = b.vmath('MULTIPLY', sun_col, diffuse)
    base = b.vscale(base, 0.3) + scatter
    em_base = b.node('ShaderNodeEmission')
    b.link(base, em_base.inputs['Color'])
    # the mirror: a glossy closure on the rippled normal. The engine pushed the reflector's screen lookup by
    # distortion = N.xz * (0.001 + 1 / distance) * distortionScale (screen units); a mirror normal tilted by half that
    # many radians of view (the push times ~0.42, half a 48-degree field of view) moves the reflection as far, near
    # water rippling hard and far water calm, as there
    cam = b.node('ShaderNodeCameraData')
    g = (0.001 + 1.0 / b.max(b.s(cam.outputs['View Distance']), 1e-3)) * dist_scale * 0.42
    MN = b.vmath('NORMALIZE', b.combine(nr * 1.5 * g, -(ng * 1.5 * g), nb))
    gl = b.node('ShaderNodeBsdfGlossy')
    gl.hide = False
    gl.inputs['Roughness'].default_value = 0.0
    gl.inputs['Color'].default_value = (1, 1, 1, 1)
    b.link(MN, gl.inputs['Normal'])
    em_spec = b.node('ShaderNodeEmission')
    b.link(spec, em_spec.inputs['Color'])
    add = b.node('ShaderNodeAddShader')
    nt.links.new(gl.outputs[0], add.inputs[0])
    nt.links.new(em_spec.outputs[0], add.inputs[1])
    mix = b.node('ShaderNodeMixShader')
    b.link(reflectance, mix.inputs['Fac'])
    nt.links.new(em_base.outputs[0], mix.inputs[1])
    nt.links.new(add.outputs[0], mix.inputs[2])
    shader = mix.outputs[0]
    tr = b.node('ShaderNodeBsdfTransparent')
    mo = b.node('ShaderNodeMixShader')
    b.link(alpha, mo.inputs['Fac'])
    nt.links.new(tr.outputs[0], mo.inputs[1])
    nt.links.new(shader, mo.inputs[2])
    nt.links.new(mo.outputs[0], out.inputs['Surface'])

    if sun_object is not None:
        _drive_sun(sd, sun_col_node=nt.nodes['wm.sun_color'], sun=sun_object)

    if geometry is None:
        w, h = size_xy
        me = bpy.data.meshes.new(name)
        me.from_pydata([(-w / 2, -h / 2, 0), (w / 2, -h / 2, 0), (w / 2, h / 2, 0), (-w / 2, h / 2, 0)], [],
                       [(0, 1, 2, 3)])
        obj = bpy.data.objects.new(name, me)
        sc.collection.objects.link(obj)
    else:
        obj = geometry
    obj.location = location if geometry is None else obj.location
    obj.data.materials.clear()
    obj.data.materials.append(mat)
    probe = None
    if planar_probe:
        pd = bpy.data.lightprobes.new(name + '_reflector', 'PLANE')
        probe = bpy.data.objects.new(name + '_reflector', pd)
        sc.collection.objects.link(probe)
        probe.location = obj.location
        dims = obj.dimensions if geometry is not None else (size_xy[0], size_xy[1], 0)
        probe.scale = (max(dims[0], 1e-3) / 2, max(dims[1], 1e-3) / 2, 1.0)
        # the water lies on the mirror's own plane: left in the probe's capture, its own surface covers the whole
        # mirrored scene and the lake reflects a blur of itself, no posts, no shore (measured:
        # probe_water_mesh_mirror.py). three's reflector clipped at its plane; this is that clip
        obj.hide_probe_plane = True
    params = dict(o)
    params['water_normals'] = normals if isinstance(normals, str) else img.filepath
    return WaterMesh(obj, mat, probe, params)


def _drive_sun(sd_node, sun_col_node, sun):
    """sun_direction (towards the sun) = the lamp's +Z axis in world space; sun_color = the lamp's colour. The axis
    comes from the lamp's world-space rotation as a quaternion (Transform Channel variables, which the depsgraph
    orders after the lamp's transform; a matrix_world property path was read before it and lagged)."""
    exprs = ('2 * (qx * qz + qw * qy)', '2 * (qy * qz - qw * qx)', '1 - 2 * (qx * qx + qy * qy)')
    for i in range(3):
        fc = sd_node.inputs[i].driver_add('default_value')
        d = fc.driver
        d.type = 'SCRIPTED'
        for nm, ch in (('qw', 'ROT_W'), ('qx', 'ROT_X'), ('qy', 'ROT_Y'), ('qz', 'ROT_Z')):
            v = d.variables.new()
            v.name = nm
            v.type = 'TRANSFORMS'
            t = v.targets[0]
            t.id = sun
            t.transform_type = ch
            t.rotation_mode = 'QUATERNION'
            t.transform_space = 'WORLD_SPACE'
        d.expression = exprs[i]
    for i in range(3):
        fc = sun_col_node.outputs[0].driver_add('default_value', i)
        d = fc.driver
        d.type = 'AVERAGE'
        v = d.variables.new()
        v.type = 'SINGLE_PROP'
        v.targets[0].id_type = 'LIGHT'
        v.targets[0].id = sun.data
        v.targets[0].data_path = f'color[{i}]'


# ------------------------------------------------------------------------------------------------------------
# SkyMesh: the sky liquids.md pairs with WaterMesh (three/addons/objects/SkyMesh.js), as the scene's world
# ------------------------------------------------------------------------------------------------------------

SKY_MESH_DEFAULTS = dict(turbidity=2.0, rayleigh=1.0, mie_coefficient=0.005, mie_directional_g=0.8,
                         sun_position=(0.0, 0.0, 0.0), up=(0.0, 0.0, 1.0), cloud_scale=0.0002, cloud_speed=0.0001,
                         cloud_coverage=0.4, cloud_density=0.4, cloud_elevation=0.5, show_sun_disc=1.0)
_SKY_TOTAL_RAYLEIGH = (5.804542996261093e-6, 1.3562911419845635e-5, 3.0265902468824876e-5)
_SKY_MIE_CONST = (1.8399918514433978e14, 2.7798023919660528e14, 4.0790479543861094e14)


def sky_mesh_radiance(direction, o, t=0.0):
    """SkyMesh's colorNode in numpy (Blender axes, z up): the sky radiance along each unit `direction` (N, 3) for the
    options `o` (SKY_MESH_DEFAULTS' keys) at time t. The reference the node graph is checked against."""
    d = np.asarray(direction, dtype=np.float64).reshape(-1, 3)
    up = np.asarray(o['up'], dtype=np.float64)
    sp = np.asarray(o['sun_position'], dtype=np.float64)
    sd = sp / max(np.linalg.norm(sp), 1e-12)
    zc = np.clip(sd @ up, -1, 1)
    sun_e = 1000.0 * max(0.0, 1.0 - math.exp(-(1.6110731556870734 - math.acos(zc)) / 1.5))
    sunfade = 1.0 - min(max(1.0 - math.exp(float(sp @ up) / 450000.0), 0.0), 1.0)
    beta_r = np.array(_SKY_TOTAL_RAYLEIGH) * (o['rayleigh'] - (1.0 - sunfade))
    beta_m = 0.434 * (0.2 * o['turbidity'] * 10e-18) * np.array(_SKY_MIE_CONST) * o['mie_coefficient']
    zen = np.arccos(np.maximum(0.0, d @ up))
    inv = 1.0 / (np.cos(zen) + 0.15 * np.power(93.885 - zen * 180.0 / math.pi, -1.253))
    fex = np.exp(-(beta_r[None] * (8.4e3 * inv)[:, None] + beta_m[None] * (1.25e3 * inv)[:, None]))
    ct = d @ sd
    rphase = 0.05968310365946075 * (1.0 + (ct * 0.5 + 0.5) ** 2)
    g = o['mie_directional_g']
    mphase = 0.07957747154594767 * (1.0 - g * g) / np.power(1.0 - 2.0 * g * ct + g * g, 1.5)
    x = sun_e * (beta_r[None] * rphase[:, None] + beta_m[None] * mphase[:, None]) / (beta_r + beta_m)[None]
    lin = np.power(x * (1.0 - fex), 1.5)
    lin = lin * (1.0 + (np.sqrt(x * fex) - 1.0) * min(max((1.0 - float(up @ sd)) ** 5, 0.0), 1.0))
    l0 = 0.1 * fex
    e0 = 0.9999566769464484
    tdisc = np.clip((ct - e0) / 0.00002, 0, 1)
    l0 = l0 + sun_e * 19000.0 * fex * (tdisc * tdisc * (3 - 2 * tdisc) * o['show_sun_disc'])[:, None]
    col = (lin + l0) * 0.04 + np.array([0.0, 0.0003, 0.00075])
    # clouds on the plane above (three's direction.xz / direction.y = Blender (x, -y) / z)
    dz = d @ up
    if o['cloud_coverage'] > 0:
        def h(px, py):
            return np.modf(np.sin(px * 127.1 + py * 311.7) * 43758.5453123)[0] % 1.0

        def noise(px, py):
            ix, iy = np.floor(px), np.floor(py)
            fx, fy = px - ix, py - iy
            ux, uy = fx * fx * (3 - 2 * fx), fy * fy * (3 - 2 * fy)
            a, b_, c, e = h(ix, iy), h(ix + 1, iy), h(ix, iy + 1), h(ix + 1, iy + 1)
            return (a + (b_ - a) * ux) + ((c + (e - c) * ux) - (a + (b_ - a) * ux)) * uy

        def fbm(px, py):
            v, amp = 0.0, 0.5
            for _ in range(5):
                v = v + amp * noise(px, py)
                px, py = px * 2.0, py * 2.0
                amp *= 0.5
            return v

        el = 1.0 + (0.1 - 1.0) * o['cloud_elevation']
        with np.errstate(divide='ignore', invalid='ignore'):
            cu = d[:, 0] / (dz * el) * o['cloud_scale'] + t * o['cloud_speed']
            cv = -d[:, 1] / (dz * el) * o['cloud_scale'] + t * o['cloud_speed']
        cn = fbm(cu * 1000.0, cv * 1000.0) + fbm(cu * 2000.0 + 3.7, cv * 2000.0 + 3.7) * 0.5
        cn = cn * 0.5 + 0.5
        lo = 1.0 - o['cloud_coverage']
        tm = np.clip((cn - lo) / 0.3, 0, 1)
        mask = tm * tm * (3 - 2 * tm)
        hf = np.clip(dz / (0.1 + 0.2 * o['cloud_elevation']), 0, 1)
        mask = mask * hf * hf * (3 - 2 * hf)
        si = ct * 0.5 + 0.5
        daylight = max(0.0, float(sd @ up) * 2.0)
        cc = 0.3 + 0.7 * daylight
        ccol = cc + ((lin * 0.04 + 1.0) - cc) * (si * 0.5)[:, None]
        ccol = ccol * (sun_e * 0.00002)
        on = (dz > 0)[:, None]
        col = np.where(on, col + (ccol - col) * (mask * o['cloud_density'])[:, None], col)
    return col


class SkyMesh:
    """What create_sky_mesh returns: the world, its uniforms as named nodes ('sky.<name>': set_uniform / key_uniform
    drive them), params, and is_sky_mesh."""

    def __init__(self, world, params):
        self.world = world
        self.params = params
        self.is_sky_mesh = True
        self.is_sky = True

    def set_uniform(self, key, value):
        n = self.world.node_tree.nodes.get('sky.' + key)
        if n is None:
            raise KeyError(key)
        self.params[key] = value
        if key in ('sun_position', 'up'):
            for i in range(3):
                n.inputs[i].default_value = float(value[i])
        else:
            n.outputs[0].default_value = float(value)

    def key_uniform(self, key, frame, value=None):
        if value is not None:
            self.set_uniform(key, value)
        n = self.world.node_tree.nodes['sky.' + key]
        socks = list(n.inputs)[:3] if key in ('sun_position', 'up') else [n.outputs[0]]
        for s in socks:
            s.keyframe_insert('default_value', frame=frame)


def create_sky_mesh(scene=None, name='sky', sun_object=None, **options):
    """three's SkyMesh as the scene's world: the Preetham sky of its colorNode, term for term, with its sun disc and
    its fbm cloud layer, in shader nodes. Options are SkyMesh's uniforms in snake_case (the engine's camelCase
    accepted), sun_position and up in Blender axes. sun_object: a Blender sun lamp whose direction drives
    sun_position (drivers). The world also lights the scene (the engine's box did not; bake an environment there
    to match). Returns a SkyMesh."""
    import bpy
    from ._nodes import Builder
    o = dict(SKY_MESH_DEFAULTS)
    camel = {'mieCoefficient': 'mie_coefficient', 'mieDirectionalG': 'mie_directional_g', 'sunPosition':
             'sun_position', 'upUniform': 'up', 'cloudScale': 'cloud_scale', 'cloudSpeed': 'cloud_speed',
             'cloudCoverage': 'cloud_coverage', 'cloudDensity': 'cloud_density', 'cloudElevation': 'cloud_elevation',
             'showSunDisc': 'show_sun_disc'}
    for k, v in options.items():
        k2 = camel.get(k, k)
        if k2 not in SKY_MESH_DEFAULTS:
            raise TypeError(f'create_sky_mesh: unknown option {k!r}')
        o[k2] = v
    sc = scene or bpy.context.scene
    fps, fs = scene_fps(sc), sc.frame_start
    w = bpy.data.worlds.new(name)
    w.use_nodes = True
    nt = w.node_tree
    nt.nodes.clear()
    out = nt.nodes.new('ShaderNodeOutputWorld')
    out.location = (2400, 0)
    b = Builder(nt, x0=-3000, y0=900)

    def val(key):
        n = b.node('ShaderNodeValue')
        n.name = n.label = 'sky.' + key
        n.hide = False
        n.outputs[0].default_value = float(o[key])
        return b.s(n.outputs[0])

    def vec(key):
        n = b.node('ShaderNodeCombineXYZ')
        n.name = n.label = 'sky.' + key
        n.hide = False
        for i in range(3):
            n.inputs[i].default_value = float(o[key][i])
        return n

    turb, ray, mie_c, mie_g = val('turbidity'), val('rayleigh'), val('mie_coefficient'), val('mie_directional_g')
    c_scale, c_speed, c_cov = val('cloud_scale'), val('cloud_speed'), val('cloud_coverage')
    c_den, c_elev, disc = val('cloud_density'), val('cloud_elevation'), val('show_sun_disc')
    sp_node, up_node = vec('sun_position'), vec('up')
    if sun_object is not None:
        for i in range(3):
            d = sp_node.inputs[i].driver_add('default_value').driver
            d.type = 'SCRIPTED'
            v = d.variables.new()
            v.name = 'm'
            v.type = 'SINGLE_PROP'
            v.targets[0].id = sun_object
            v.targets[0].data_path = f'matrix_world[{i}][2]'
            d.expression = 'm'
    tnode = b.node('ShaderNodeValue')
    tnode.name = tnode.label = 'sky.time'
    tnode.hide = False
    drv = tnode.outputs[0].driver_add('default_value').driver
    drv.type = 'SCRIPTED'
    drv.expression = f'(frame - {int(fs)}) / {float(fps):.6g}'
    T = b.s(tnode.outputs[0])

    sp = b.vec(sp_node.outputs[0])
    upv = b.vmath('NORMALIZE', b.vec(up_node.outputs[0]))
    sd = b.vmath('NORMALIZE', sp)
    sdx, sdy, sdz = sd.xyz()
    # the vertex stage: sun intensity, fade and the two extinction coefficients
    zc = b.clamp(b.vmath('DOT_PRODUCT', sd, upv), -1.0, 1.0)
    sun_e = 1000.0 * b.max(0.0, 1.0 - b.exp(-((1.6110731556870734 - b.math('ARCCOSINE', zc)) / 1.5)))
    sp_up = b.vmath('DOT_PRODUCT', sp, upv)
    sunfade = 1.0 - b.clamp(1.0 - b.exp(sp_up / 450000.0), 0.0, 1.0)
    rcoef = ray - (1.0 - sunfade)
    beta_r = [rcoef * k for k in _SKY_TOTAL_RAYLEIGH]
    beta_m = [turb * mie_c * (0.434 * 0.2 * 10e-18 * k) for k in _SKY_MIE_CONST]
    # the fragment: the view direction (world shaders see it as the generated coordinate)
    tc = b.node('ShaderNodeTexCoord')
    dvec = b.vmath('NORMALIZE', b.vec(tc.outputs['Generated']))
    dx, dy, dz = dvec.xyz()
    d_up = b.vmath('DOT_PRODUCT', upv, dvec)
    zen = b.math('ARCCOSINE', b.max(0.0, d_up))
    inv = 1.0 / (b.cos(zen) + 0.15 * b.pow(93.885 - zen * (180.0 / math.pi), -1.253))
    s_r, s_m = 8.4e3 * inv, 1.25e3 * inv
    fex = [b.exp(-(beta_r[i] * s_r + beta_m[i] * s_m)) for i in range(3)]
    ct = b.vmath('DOT_PRODUCT', dvec, sd)
    cc = ct * 0.5 + 0.5
    rphase = 0.05968310365946075 * (1.0 + cc * cc)
    g2 = mie_g * mie_g
    mphase = 0.07957747154594767 * (1.0 - g2) / b.pow(1.0 - 2.0 * mie_g * ct + g2, 1.5)
    hor = b.clamp(b.pow(1.0 - b.vmath('DOT_PRODUCT', upv, sd), 5.0), 0.0, 1.0)
    lin, col = [], []
    t0 = 0.9999566769464484
    td = b.clamp((ct - t0) / 0.00002)
    sundisc = td * td * (3.0 - 2.0 * td) * disc
    for i in range(3):
        x = sun_e * (beta_r[i] * rphase + beta_m[i] * mphase) / (beta_r[i] + beta_m[i])
        li = b.pow(x * (1.0 - fex[i]), 1.5)
        li = li * (1.0 + (b.sqrt(x * fex[i]) - 1.0) * hor)
        lin.append(li)
        l0 = 0.1 * fex[i] + sun_e * 19000.0 * fex[i] * sundisc
        col.append((li + l0) * 0.04 + (0.0, 0.0003, 0.00075)[i])

    # clouds: fbm on the plane above, three's hash / value noise / 5 octaves
    def hsh(px, py):
        return b.fract(b.sin(px * 127.1 + py * 311.7) * 43758.5453123)

    def noise(px, py):
        ix, iy = b.floor(px), b.floor(py)
        fx, fy = px - ix, py - iy
        ux, uy = fx * fx * (3.0 - 2.0 * fx), fy * fy * (3.0 - 2.0 * fy)
        a, bb, c, e = hsh(ix, iy), hsh(ix + 1.0, iy), hsh(ix, iy + 1.0), hsh(ix + 1.0, iy + 1.0)
        ab = a + (bb - a) * ux
        ce = c + (e - c) * ux
        return ab + (ce - ab) * uy

    def fbm(px, py):
        v, amp = None, 0.5
        for _ in range(5):
            term = noise(px, py) * amp
            v = term if v is None else v + term
            px, py = px * 2.0, py * 2.0
            amp *= 0.5
        return v

    el = 1.0 + (0.1 - 1.0) * c_elev
    dzs = b.max(dz, 1e-4)                               # the If(direction.y > 0) branch; masked below
    cu = dx / (dzs * el) * c_scale + T * c_speed
    cv = -dy / (dzs * el) * c_scale + T * c_speed
    cn = fbm(cu * 1000.0, cv * 1000.0) + fbm(cu * 2000.0 + 3.7, cv * 2000.0 + 3.7) * 0.5
    cn = cn * 0.5 + 0.5
    lo = 1.0 - c_cov
    tm = b.clamp((cn - lo) / 0.3)
    mask = tm * tm * (3.0 - 2.0 * tm)
    hf = b.clamp(dz / (0.1 + 0.2 * c_elev))
    mask = mask * hf * hf * (3.0 - 2.0 * hf)
    si = ct * 0.5 + 0.5
    daylight = b.max(0.0, b.vmath('DOT_PRODUCT', sd, upv) * 2.0)
    base = 0.3 + 0.7 * daylight
    on = b.math('GREATER_THAN', dz, 0.0) * b.math('GREATER_THAN', c_cov, 0.0)
    k = mask * c_den * on
    outc = []
    for i in range(3):
        cci = (base + ((lin[i] * 0.04 + 1.0) - base) * (si * 0.5)) * (sun_e * 0.00002)
        outc.append(col[i] + (cci - col[i]) * k)
    bg = b.node('ShaderNodeBackground')
    b.link(b.combine(*outc), bg.inputs['Color'])
    bg.inputs['Strength'].default_value = 1.0
    nt.links.new(bg.outputs[0], out.inputs['Surface'])
    sc.world = w
    return SkyMesh(w, dict(o))


# ------------------------------------------------------------------------------------------------------------
# water_compute.js
# ------------------------------------------------------------------------------------------------------------

WATER_COMPUTE_DEFAULTS = dict(width=128, bounds=20.0, segments=None, viscosity=0.98, max_height=None,
                              color=0x335577, roughness=0.1, metalness=0.4, env_map=None, opacity=0.92,
                              displace_scale=1.0, circular=False,
                              # the Blender edition's: 'engine' keeps water_compute.js's shading normal (its finite
                              # difference has both slopes inverted, so a bump shades as a pit, and twice steep);
                              # 'surface' is the displaced surface's own normal
                              normals='engine')


class WaterCompute:
    """createWaterCompute's object: mesh, step(), disturb(x, y, radius, amplitude) (plane-local Blender metres;
    the engine's (x, z)), viscosity (live), heights (the current field), and the Blender edition's bake()."""

    def __init__(self, o, name, scene, location, seed):
        self.o = o
        self.name = name
        self.scene = scene
        self.W = int(o['width'])
        self.B = float(o['bounds'])
        self.max_height = float(o['max_height'] if o['max_height'] is not None else self.B * 0.12)
        self._visc = float(o['viscosity'])
        rnd = random.Random(seed)
        init = np.array([(rnd.random() - 0.5) * 0.001 for _ in range(self.W * self.W)], dtype=np.float32)
        self.a = init.reshape(self.W, self.W).copy()             # [row iz][column ix] (the engine's buffers)
        self.prev = self.a.copy()
        self.fresh_is_a = True
        self.b = self.a.copy()
        self._dist = None
        self.location = location
        self.images = {}
        self.mesh = None
        self.material = None
        iz, ix = np.mgrid[0:self.W, 0:self.W]
        # the engine's cell position for disturbances: (ix / W - 0.5) * bounds (not cell-centred: its quirk)
        self._wx = ((ix / self.W) - 0.5) * self.B
        self._wz = ((iz / self.W) - 0.5) * self.B

    @property
    def viscosity(self):
        return self._visc

    @viscosity.setter
    def viscosity(self, v):
        self._visc = float(v)

    @property
    def heights(self):
        return self.a if self.fresh_is_a else self.b

    def disturb(self, x, y, radius, amplitude):
        """A one-step cosine impulse at plane-local (x, y) Blender metres (the engine's (x, z) with z = -y)."""
        self._dist = (float(x), -float(y), float(radius), float(amplitude))

    def step(self):
        rd = self.a if self.fresh_is_a else self.b
        # the engine's getNeighbors: clamp(iz - 1u, 0u, W - 1u) on unsigned indices, so row 0's north neighbour
        # underflows and clamps to the LAST row (and column 0's west neighbour to the last column), while south and
        # east clamp to the edge: one-sided wrap-around, kept as it ran
        N, Wn = np.roll(rd, 1, axis=0), np.roll(rd, 1, axis=1)
        p = np.pad(rd, 1, mode='edge')
        S, E = p[2:, 1:-1], p[1:-1, 2:]
        new = ((N + S + E + Wn) * 0.5 - self.prev) * np.float32(self._visc)
        if self._dist is not None:
            dx, dz, r, amp = self._dist
            d = np.hypot(self._wx - dx, self._wz - dz)
            phase = np.clip(d * math.pi / (r + 1e-4), 0.0, math.pi)
            new = new + ((np.cos(phase) + 1.0) * amp * 0.5).astype(np.float32)
        new = np.clip(new, -self.max_height, self.max_height).astype(np.float32)
        self.prev = rd.copy()
        if self.fresh_is_a:
            self.b = new
        else:
            self.a = new
        self.fresh_is_a = not self.fresh_is_a
        self._dist = None                 # disturbAmp.value = 0: single calls are single-frame impulses

    def bake(self, frame_start=None, frame_end=None, controls=None, cache_dir='//water_compute_cache', log=print):
        """Per frame: controls(frame, t, water) then step() (once per frame, as the engine's scenes do), and the
        heights written as an OpenEXR data image <cache>/<name>_height_####.exr; then the Geometry Nodes player."""
        from ._util import write_exr
        sc = self.scene
        fs = sc.frame_start if frame_start is None else int(frame_start)
        fe = sc.frame_end if frame_end is None else int(frame_end)
        fps = scene_fps(sc)
        d = abspath(cache_dir)
        os.makedirs(d, exist_ok=True)
        for f in range(fs, fe + 1):
            if controls:
                controls(f, (f - fs) / fps, self)
            self.step()
            h = self.heights[::-1]                          # row 0 = the image's bottom = the plane's -y edge
            write_exr(frame_file(d, self.name + '_height', f, 'exr'), h[..., None].repeat(3, axis=2), half=False)
            if f == fs:
                write_exr(frame_file(d, self.name + '_height', f - 1, 'exr'), h[..., None].repeat(3, axis=2))
        import bpy
        nm = self.name + '_height'
        if nm in bpy.data.images:
            bpy.data.images.remove(bpy.data.images[nm])
        img = bpy.data.images.load(frame_file(d, nm, fs, 'exr'))
        img.name = nm
        img.source = 'SEQUENCE'
        img.colorspace_settings.is_data = True
        self.images['height'] = img
        self._attach_player(img, fs, fe)
        log(f'[water_compute] baked frames {fs}..{fe} -> {d}')
        return self

    def _attach_player(self, img, fs, fe):
        """Geometry Nodes: sample the frame's height image at each vertex's texel, displace along +Z (times
        displace_scale, faded at a disc rim when circular), and store the engine's shading normal."""
        from ._nodes import Builder, new_group
        tree, gi, go = new_group(self.name + '.player', 'GeometryNodeTree',
                                 [('Geometry', 'NodeSocketGeometry')], [('Geometry', 'NodeSocketGeometry')])
        b = Builder(tree, x0=-1600, y0=500)
        W, B = self.W, self.B
        uvn = b.node('GeometryNodeInputNamedAttribute', data_type='FLOAT_VECTOR')
        uvn.inputs['Name'].default_value = 'texel_uv'
        u, v, _ = b.vec(uvn.outputs['Attribute']).xyz()
        tm = b.node('GeometryNodeInputSceneTime')
        frame = b.min(b.max(b.s(tm.outputs['Frame']), float(fs)), float(fe))

        def h_at(du, dv, extension='EXTEND'):
            n = b.node('GeometryNodeImageTexture', interpolation='Closest', extension=extension)
            n.inputs['Image'].default_value = img
            b.link(b.combine(u + du, v + dv, 0.0), n.inputs['Vector'])
            b.link(frame, n.inputs['Frame'])
            r, _, _ = b.vec(n.outputs['Color']).xyz()
            return r

        h = h_at(0.0, 0.0)
        if self.o['circular']:
            # the engine's uv() is the PlaneGeometry's (ix / (W - 1)), so its distance from the centre is the vertex's
            # own |x, y| / bounds (the texel centres sit half a texel inside it)
            pos = b.node('GeometryNodeInputPosition')
            px, py, _ = b.vec(pos.outputs['Position']).xyz()
            d = b.sqrt(px * px + py * py) / B
            h = h * b.smoothstep(0.5, 0.44, d)
        sp = b.node('GeometryNodeSetPosition')
        tree.links.new(gi.outputs[0], sp.inputs['Geometry'])
        b.link(b.combine(0.0, 0.0, h * float(self.o['displace_scale'])), sp.inputs['Offset'])
        # the engine's normalNode: nx = (h_W - h_E) W / B, ny = (h_S - h_N) W / B, n = (-nx, -ny, 1) (plane-local)
        k = W / B
        t = 1.0 / W
        # the kernel's neighbours: north and west wrap past row / column 0 (its unsigned underflow), south and east
        # clamp to the edge
        hE, hW_ = h_at(t, 0.0), h_at(-t, 0.0, 'REPEAT')
        hN, hS = h_at(0.0, t, 'REPEAT'), h_at(0.0, -t)
        nx = (hW_ - hE) * k
        ny = (hS - hN) * k
        if self.o['normals'] == 'surface':
            # the displaced surface's own normal: central differences over two cells, times displace_scale
            ds = float(self.o['displace_scale']) * 0.5
            nrm = b.vmath('NORMALIZE', b.combine(nx * ds, ny * ds, 1.0))
        else:
            nrm = b.vmath('NORMALIZE', b.combine(-nx, -ny, 1.0))
        st = b.node('GeometryNodeStoreNamedAttribute', data_type='FLOAT_VECTOR', domain='POINT')
        st.inputs['Name'].default_value = 'wave_normal'
        tree.links.new(sp.outputs['Geometry'], st.inputs['Geometry'])
        b.link(nrm, st.inputs['Value'])
        tree.links.new(st.outputs['Geometry'], go.inputs[0])
        mod = self.mesh.modifiers.get('water_compute') or self.mesh.modifiers.new('water_compute', 'NODES')
        mod.node_group = tree
        return tree

    def dispose(self):
        self.a = self.b = self.prev = None


def _water_compute_material(name, o):
    """MeshStandardNodeMaterial({color, roughness, metalness, transparent, opacity}) with the engine's normalNode
    (the stored wave_normal) and, when circular, the disc clip (alpha 0 outside the inscribed disc)."""
    import bpy
    from ._nodes import Builder
    mat = bpy.data.materials.new(name)
    mat.use_nodes = True
    mat.surface_render_method = 'BLENDED'
    mat.use_transparency_overlap = False
    nt = mat.node_tree
    p = nt.nodes['Principled BSDF']
    p.inputs['Base Color'].default_value = (*color(o['color']), 1.0)
    p.inputs['Roughness'].default_value = float(o['roughness'])
    p.inputs['Metallic'].default_value = float(o['metalness'])
    b = Builder(nt, x0=-1200, y0=400)
    at = b.node('ShaderNodeAttribute', attribute_name='wave_normal', attribute_type='GEOMETRY')
    vt = b.node('ShaderNodeVectorTransform', vector_type='NORMAL', convert_from='OBJECT', convert_to='WORLD')
    nt.links.new(at.outputs['Vector'], vt.inputs['Vector'])
    nt.links.new(vt.outputs['Vector'], p.inputs['Normal'])
    alpha = float(o['opacity'])
    if o['circular']:
        # uv() - 0.5 of the engine's PlaneGeometry is the object-space (x, y) / bounds
        tc = b.node('ShaderNodeTexCoord')
        ox, oy, _ = b.vec(tc.outputs['Object']).xyz()
        d = b.sqrt(ox * ox + oy * oy) / float(o['bounds'])
        b.link(b.math('LESS_THAN', d, 0.5) * alpha, p.inputs['Alpha'])     # the alphaTest hard discard
    else:
        p.inputs['Alpha'].default_value = alpha
    return mat


def create_water_compute(location=(0.0, 0.0, 0.0), name='water_compute', scene=None, seed=1, **options):
    """water_compute.js createWaterCompute(renderer, opts) in Blender (the engine's camelCase accepted). The grid
    lies in the object's XY plane at `location` (the engine rotated a PlaneGeometry flat), row 0 at +y.
    env_map: the scene's world and light probes give EEVEE's reflections (the option is kept in params)."""
    import bpy
    o = dict(WATER_COMPUTE_DEFAULTS)
    camel = {'maxHeight': 'max_height', 'envMap': 'env_map', 'displaceScale': 'displace_scale'}
    for k, v in options.items():
        k2 = camel.get(k, k)
        if k2 not in WATER_COMPUTE_DEFAULTS:
            raise TypeError(f'create_water_compute: unknown option {k!r}')
        o[k2] = v
    sc = scene or bpy.context.scene
    wc = WaterCompute(o, name, sc, location, seed)
    W, B = wc.W, wc.B
    seg = int(o['segments'] or W)
    if seg != W:
        print(f'[water_compute] segments {seg} != width {W}: the engine maps vertexIndex onto the grid, so only '
              f'segments == width lines up; using {W}')
    # vertex (ix, iz) at x = -B/2 + ix B/(W-1), y = +B/2 - iz B/(W-1): three's PlaneGeometry rotated flat
    ix, iz = np.meshgrid(np.arange(W), np.arange(W))
    xs = -B / 2 + ix * B / (W - 1)
    ys = B / 2 - iz * B / (W - 1)
    verts = np.stack([xs.ravel(), ys.ravel(), np.zeros(W * W)], axis=1)
    q = (iz[:-1, :-1] * W + ix[:-1, :-1]).ravel()
    faces = np.stack([q, q + W, q + W + 1, q + 1], axis=1)
    me = bpy.data.meshes.new(name)
    me.from_pydata(verts.tolist(), [], faces.tolist())
    # each vertex's own texel centre in the height image (row 0 of the image = the bottom = the last grid row)
    tu = ((ix + 0.5) / W).ravel()
    tv = (1.0 - (iz + 0.5) / W).ravel()
    attr = me.attributes.new('texel_uv', 'FLOAT_VECTOR', 'POINT')
    attr.data.foreach_set('vector', np.stack([tu, tv, np.zeros_like(tu)], axis=1).ravel().astype(np.float32))
    for poly in me.polygons:
        poly.use_smooth = True
    if o['normals'] not in ('engine', 'surface'):
        raise ValueError(f"create_water_compute: normals must be 'engine' or 'surface', not {o['normals']!r}")
    obj = bpy.data.objects.new(name, me)
    sc.collection.objects.link(obj)
    obj.location = location
    obj.visible_shadow = False                    # the engine's mesh received shadows and cast none
    wc.mesh = obj
    wc.material = _water_compute_material(name + '_mat', o)
    me.materials.append(wc.material)
    return wc


__all__ = ['create_water_mesh', 'WaterMesh', 'WATER_MESH_DEFAULTS', 'make_water_normals', 'create_sky_mesh', 'SkyMesh',
           'SKY_MESH_DEFAULTS', 'sky_mesh_radiance', 'create_water_compute', 'WaterCompute', 'WATER_COMPUTE_DEFAULTS']
