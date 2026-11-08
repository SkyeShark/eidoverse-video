"""eidoblend.characters.robotics.studio: studio.js, the compact presentation the kit's examples and inspector share.

    studio(scene=None, grid=True, shadows=False) -> {'world', 'sun', 'grid', 'environment'}
        studio.js studio(renderer, {grid}): scene.background #c6cfd1 (what the camera sees); three's RoomEnvironment
        as the environment light at intensity 0.9; a HemisphereLight (sky #e6f2ff, ground #485654, 1); a
        DirectionalLight #fff3e4 at 2.3 from (2, 5, 3) toward the origin; an 8 m GridHelper of 80 divisions
        (centre lines #748b91, the rest #acb9bd) 1 mm under the floor.
        RoomEnvironment is PORTED, not substituted: room_environment() ray-casts its very room (the 31.7 x 28.3 x 28.6 m
        box seen from inside, its six boxes and six emissive panels, the 900 cd point light with its 28 m cutoff and
        inverse-square decay, white standard materials of roughness 1, no shadows, as the PMREM cube render sees it)
        into an equirect, blurred by the PMREM's sigma of 0.04 rad, packed into the file.
        The hemisphere light is the world radiance sky / pi above the horizon and ground / pi below: a world split at
        the horizon gives exactly three's irradiance mix(ground, sky, 0.5 + 0.5 n.z).
        shadows: the WebGPU studio's sun casts none (castShadow is never set); True turns the sun's shadow on.
        Tone mapping is AgX here (ACES there): the film contract.
    frame_camera(camera, objects, direction=(0.9, -1.5, 0.55), margin=1.25, aspect=None, visible_only=False)
        -> target Vector
        studio.js frameCamera: the camera on `direction` (Blender axes; three's [.9, .55, 1.5]) far enough that the
        world box of `objects` (objects, their mesh descendants, or (min, max) boxes) fits with `margin`, looking at
        the box centre; clip_start = max(.001, d / 2000), clip_end = max(20, d * 20). The aspect is the scene's
        render aspect unless given. visible_only: the inspector's fit (hidden meshes and overlays left out).
    world_box(objects, visible_only=False) -> (min, max)    three's Box3.expandByObject, world axes
    make_camera(fov_deg, name='camera', scene=None)   a camera with three's VERTICAL field of view
"""

from __future__ import annotations

import math

import bpy
import numpy as np
from mathutils import Vector

from .materials import to_linear

BACKGROUND = '#c6cfd1'
SKY, GROUND = '#e6f2ff', '#485654'
SUN_COLOR, SUN_INTENSITY, SUN_FROM_THREE = '#fff3e4', 2.3, (2.0, 5.0, 3.0)
ENV_INTENSITY = 0.9
ROOM_IMAGE = 'robotics_room_environment'

# three's RoomEnvironment (three/examples/jsm/environments/RoomEnvironment.js, MIT), three's axes, before its y -3.5
_ROOM = ((-0.757, 13.219, 0.717), 0.0, (31.713, 28.305, 28.591))
_BOXES = (((-10.906, 2.009, 1.846), -0.195, (2.328, 7.905, 4.651)),
          ((-5.607, -0.754, -0.758), 0.994, (1.970, 1.534, 3.955)),
          ((6.167, 0.857, 7.803), 0.561, (3.927, 6.285, 3.687)),
          ((-2.017, 0.018, 6.124), 0.333, (2.002, 4.566, 2.064)),
          ((2.291, -0.756, -2.621), -0.286, (1.546, 1.552, 1.496)),
          ((-2.193, -0.369, -5.547), 0.516, (3.875, 3.487, 2.986)))
_PANELS = (((-16.116, 14.37, 8.208), (0.1, 2.428, 2.739), 50.0),
           ((-16.109, 18.021, -8.207), (0.1, 2.425, 2.751), 50.0),
           ((14.904, 12.198, -1.832), (0.15, 4.265, 6.331), 17.0),
           ((-0.462, 8.89, 14.520), (4.38, 5.441, 0.088), 43.0),
           ((3.235, 11.486, -12.541), (2.5, 2.0, 0.1), 20.0),
           ((0.0, 20.0, 0.0), (1.0, 0.1, 1.0), 100.0))
_LIGHT = ((0.418, 16.199, 0.300), 900.0, 28.0)
_OFFSET_Y = -3.5


def _box_hits(o, d, pos, ry, scale, inside):
    """ray (origin o (3,), directions d (N, 3)) against a unit box at pos, turned ry about Y, scaled: t and the
    outward world normal at the entry (or, inside, at the exit)"""
    c, s = math.cos(ry), math.sin(ry)
    R = np.array([[c, 0, s], [0, 1, 0], [-s, 0, c]])                  # three's rotation about Y
    S = np.array(scale, float)
    lo = (R.T @ (o - np.asarray(pos))) / S
    ld = (d @ R) / S                                                     # R^T d, row-wise
    with np.errstate(divide='ignore', invalid='ignore'):
        inv = 1.0 / ld
        t1 = (-0.5 - lo) * inv
        t2 = (0.5 - lo) * inv
    tmin = np.minimum(t1, t2)
    tmax = np.maximum(t1, t2)
    tn = np.nanmax(tmin, axis=1)
    tf = np.nanmin(tmax, axis=1)
    hit = tf >= np.maximum(tn, 0.0)
    if inside:
        t = tf
        axis = np.nanargmin(tmax, axis=1)
    else:
        t = tn
        axis = np.nanargmax(tmin, axis=1)
        hit &= tn > 1e-6
    p = lo + ld * t[:, None]
    sign = np.sign(p[np.arange(len(p)), axis])
    nl = np.zeros_like(p)
    nl[np.arange(len(p)), axis] = sign
    nw = (nl / S) @ R.T                                                  # inverse-transpose of R S
    nw /= np.linalg.norm(nw, axis=1, keepdims=True)
    return np.where(hit, t, np.inf), nw


def _gauss_rows(img, sig_rows, wrap):
    out = np.empty_like(img)
    H, W, _ = img.shape
    for j in range(H):
        sg = sig_rows[j]
        if sg < 0.3:
            out[j] = img[j]
            continue
        r = int(min(W // 2 - 1 if wrap else H - 1, math.ceil(3 * sg)))
        k = np.exp(-0.5 * (np.arange(-r, r + 1) / sg) ** 2)
        k /= k.sum()
        row = img[j]
        if wrap:
            pad = np.concatenate([row[-r:], row, row[:r]], axis=0)
        else:
            pad = np.concatenate([np.repeat(row[:1], r, 0), row, np.repeat(row[-1:], r, 0)], axis=0)
        for ch in range(3):
            out[j, :, ch] = np.convolve(pad[:, ch], k, mode='valid')
    return out


def room_environment(width=1024, sigma=0.04):
    """three's RoomEnvironment as the PMREM generator sees it from the origin, as a Blender equirect (packed, cached)"""
    im = bpy.data.images.get(ROOM_IMAGE)
    if im is not None and im.size[0] == width:
        return im
    H, W = width // 2, width
    u = (np.arange(W) + 0.5) / W
    v = (np.arange(H) + 0.5) / H
    phi = (0.5 - u) * 2 * math.pi                     # Blender's equirect: u = 0.5 - atan2(y, x) / 2pi
    el = (v - 0.5) * math.pi
    PH, EL = np.meshgrid(phi, el)
    bx, by, bz = np.cos(EL) * np.cos(PH), np.cos(EL) * np.sin(PH), np.sin(EL)
    d = np.stack([bx, bz, -by], axis=-1).reshape(-1, 3)   # Blender -> three
    o = np.zeros(3)
    off = np.array([0.0, _OFFSET_Y, 0.0])
    best = np.full(len(d), np.inf)
    normal = np.zeros_like(d)
    emit = np.zeros(len(d))
    t, n = _box_hits(o, d, np.asarray(_ROOM[0]) + off, _ROOM[1], _ROOM[2], inside=True)
    sel = t < best
    best[sel], normal[sel] = t[sel], -n[sel]
    for pos, ry, sc in _BOXES:
        t, n = _box_hits(o, d, np.asarray(pos) + off, ry, sc, inside=False)
        sel = t < best
        best[sel], normal[sel], emit[sel] = t[sel], n[sel], 0.0
    for pos, sc, k in _PANELS:
        t, n = _box_hits(o, d, np.asarray(pos) + off, 0.0, sc, inside=False)
        sel = t < best
        best[sel], emit[sel] = t[sel], k
    p = d * best[:, None]
    lp = np.asarray(_LIGHT[0]) + off
    L = lp - p
    dist = np.linalg.norm(L, axis=1)
    l = L / dist[:, None]
    V = -d
    nl = np.clip(np.sum(normal * l, axis=1), 0, 1)
    nv = np.clip(np.sum(normal * V, axis=1), 1e-4, 1)
    fall = 1.0 / np.maximum(dist ** 2, 0.01) * np.clip(1 - (dist / _LIGHT[2]) ** 4, 0, 1) ** 2
    irr = nl * _LIGHT[1] * fall
    h = l + V
    h /= np.linalg.norm(h, axis=1, keepdims=True)
    vh = np.clip(np.sum(V * h, axis=1), 0, 1)
    F = 0.04 + 0.96 * (1 - vh) ** 5
    spec = F * (0.5 / np.maximum(nl + nv, 1e-6)) / math.pi             # GGX at roughness 1: D = 1/pi, V = .5/(nl+nv)
    rad = np.where(emit > 0, emit, irr * (1 / math.pi + spec))
    img = np.repeat(rad.reshape(H, W, 1), 3, axis=2).astype(np.float64)
    sig_v = sigma / (math.pi / H)
    img = np.transpose(_gauss_rows(np.transpose(img, (1, 0, 2)), np.full(W, sig_v), wrap=False), (1, 0, 2))
    sig_h = sigma / (2 * math.pi / W) / np.maximum(np.cos(el), 1e-3)
    img = _gauss_rows(img, sig_h, wrap=True)
    px = np.ones((H, W, 4), np.float32)
    px[..., :3] = img
    if im is not None:
        bpy.data.images.remove(im)
    im = bpy.data.images.new(ROOM_IMAGE, W, H, alpha=False, float_buffer=True)
    im.pixels.foreach_set(px.ravel())
    im.pack()
    return im


def _world(scene, background, env_strength):
    wd = bpy.data.worlds.new('robotics studio')
    scene.world = wd
    wd.use_nodes = True
    nt = wd.node_tree
    for n in list(nt.nodes):
        nt.nodes.remove(n)
    env = nt.nodes.new('ShaderNodeTexEnvironment')
    env.image = room_environment()
    env.location = (-700, 200)
    scale = nt.nodes.new('ShaderNodeVectorMath')
    scale.operation = 'SCALE'
    scale.inputs['Scale'].default_value = env_strength
    scale.location = (-450, 200)
    nt.links.new(env.outputs['Color'], scale.inputs[0])
    tc = nt.nodes.new('ShaderNodeTexCoord')
    tc.location = (-900, -150)
    sep = nt.nodes.new('ShaderNodeSeparateXYZ')
    sep.location = (-700, -150)
    nt.links.new(tc.outputs['Generated'], sep.inputs[0])
    up = nt.nodes.new('ShaderNodeMath')
    up.operation = 'GREATER_THAN'
    up.inputs[1].default_value = 0.0
    up.location = (-500, -150)
    nt.links.new(sep.outputs['Z'], up.inputs[0])
    hemi = nt.nodes.new('ShaderNodeMix')
    hemi.data_type = 'RGBA'
    hemi.location = (-300, -150)
    sock = lambda coll, ident: next(s for s in coll if s.identifier == ident)  # noqa: E731  (Mix: A/B per type)
    sock(hemi.inputs, 'A_Color').default_value = tuple(c / math.pi for c in to_linear(GROUND)) + (1.0,)
    sock(hemi.inputs, 'B_Color').default_value = tuple(c / math.pi for c in to_linear(SKY)) + (1.0,)
    nt.links.new(up.outputs[0], sock(hemi.inputs, 'Factor_Float'))
    add = nt.nodes.new('ShaderNodeVectorMath')
    add.operation = 'ADD'
    add.location = (-150, 50)
    nt.links.new(scale.outputs[0], add.inputs[0])
    nt.links.new(sock(hemi.outputs, 'Result_Color'), add.inputs[1])
    light = nt.nodes.new('ShaderNodeBackground')
    light.location = (50, 50)
    nt.links.new(add.outputs[0], light.inputs['Color'])
    flat = nt.nodes.new('ShaderNodeBackground')
    flat.location = (50, -120)
    flat.inputs['Color'].default_value = tuple(to_linear(background)) + (1.0,)
    lp = nt.nodes.new('ShaderNodeLightPath')
    lp.location = (50, 300)
    mix = nt.nodes.new('ShaderNodeMixShader')
    mix.location = (250, 50)
    nt.links.new(lp.outputs['Is Camera Ray'], mix.inputs['Fac'])
    nt.links.new(light.outputs['Background'], mix.inputs[1])
    nt.links.new(flat.outputs['Background'], mix.inputs[2])
    out = nt.nodes.new('ShaderNodeOutputWorld')
    out.location = (450, 50)
    nt.links.new(mix.outputs['Shader'], out.inputs['Surface'])
    return wd


def _grid(scene, size=8.0, divisions=80, center='#748b91', line='#acb9bd', width=0.0012):
    """three's GridHelper(8, 80): unlit lines on the floor plane, 1 mm under it"""
    verts, faces, cols = [], [], []
    half, step = size / 2, size / divisions
    for i in range(divisions + 1):
        k = -half + i * step
        is_c = abs(k) < 1e-9
        for a in ((k - width / 2, -half, k + width / 2, half), (-half, k - width / 2, half, k + width / 2)):
            x0, y0, x1, y1 = a
            b = len(verts)
            verts += [(x0, y0, -0.001), (x1, y0, -0.001), (x1, y1, -0.001), (x0, y1, -0.001)]
            faces.append((b, b + 1, b + 2, b + 3))
            cols.append(is_c)
    me = bpy.data.meshes.new('robotics grid')
    me.from_pydata(verts, [], faces)
    me.update()
    mats = []
    for nm, hexc in (('grid line', line), ('grid centre line', center)):
        m = bpy.data.materials.get('robotics ' + nm) or bpy.data.materials.new('robotics ' + nm)
        m.use_nodes = True
        nt = m.node_tree
        for n in list(nt.nodes):
            nt.nodes.remove(n)
        em = nt.nodes.new('ShaderNodeEmission')
        em.inputs['Color'].default_value = tuple(to_linear(hexc)) + (1.0,)
        em.inputs['Strength'].default_value = 1.0
        out = nt.nodes.new('ShaderNodeOutputMaterial')
        nt.links.new(em.outputs[0], out.inputs['Surface'])
        mats.append(m)
        me.materials.append(m)
    me.polygons.foreach_set('material_index', [1 if c else 0 for c in cols])
    ob = bpy.data.objects.new('robotics grid', me)
    scene.collection.objects.link(ob)
    ob.visible_shadow = False
    ob.visible_volume_scatter = False
    ob['no_support_check'] = True
    ob['no_z_fight_check'] = True          # three's GridHelper: unlit lines 1 mm under the floor, not a surface
    ob['no_clipping_check'] = True
    return ob


def studio(scene=None, grid=True, shadows=False):
    """studio.js studio(): background, room environment, hemisphere, sun, grid (see the module docstring)"""
    scene = scene or bpy.context.scene
    wd = _world(scene, BACKGROUND, ENV_INTENSITY)
    ld = bpy.data.lights.new('robotics studio sun', 'SUN')
    ld.energy = SUN_INTENSITY
    ld.color = to_linear(SUN_COLOR)
    ld.angle = 0.0
    ld.use_shadow = bool(shadows)
    sun = bpy.data.objects.new('robotics studio sun', ld)
    scene.collection.objects.link(sun)
    x, y, z = SUN_FROM_THREE
    p = Vector((x, -z, y))
    sun.location = p
    sun.rotation_mode = 'QUATERNION'
    sun.rotation_quaternion = Vector((0, 0, -1)).rotation_difference((-p).normalized())
    g = _grid(scene) if grid else None
    scene.view_settings.view_transform = 'AgX'
    return {'world': wd, 'sun': sun, 'grid': g, 'environment': wd.node_tree.nodes[0].image}


def make_camera(fov_deg, name='camera', scene=None):
    scene = scene or bpy.context.scene
    cd = bpy.data.cameras.new(name)
    cd.sensor_fit = 'VERTICAL'
    cd.angle_y = math.radians(fov_deg)
    ob = bpy.data.objects.new(name, cd)
    scene.collection.objects.link(ob)
    ob.rotation_mode = 'QUATERNION'
    return ob


def _world_matrix(ob):
    """ob's world matrix even when the depsgraph does not evaluate it: an object disabled in the viewports
    (hide_viewport: the inspector's hidden overlays, load_part's hidden donor meshes) keeps a STALE matrix_world, so
    such an object's matrix is composed from its parent chain instead (parent world @ parent inverse @ basis)"""
    if not ob.hide_viewport and ob.visible_get():
        return ob.matrix_world
    m = ob.matrix_basis
    if ob.parent is not None:
        m = _world_matrix(ob.parent) @ ob.matrix_parent_inverse @ m
    return m


def world_box(objects, visible_only=False):
    """three's Box3.expandByObject over objects and their descendants (mesh bounding boxes, world), or (min, max)
    boxes. visible_only: viewer.js's fit (traverseVisible, overlays skipped): meshes hidden from the render and the
    inspector's overlays are left out; by default every mesh counts, visible or not, as expandByObject counts them."""
    lo = Vector((math.inf,) * 3)
    hi = Vector((-math.inf,) * 3)

    def take(p):
        for i in range(3):
            lo[i] = min(lo[i], p[i])
            hi[i] = max(hi[i], p[i])
    bpy.context.view_layer.update()
    for o in objects:
        if isinstance(o, (tuple, list)) and len(o) == 2:
            take(Vector(o[0]))
            take(Vector(o[1]))
            continue
        stack = [o]
        while stack:
            x = stack.pop()
            if visible_only and (x.hide_render or x.get('overlay')):
                continue                                   # traverseVisible: a hidden node hides its subtree
            stack.extend(x.children)
            if x.type == 'MESH' and len(x.data.vertices):
                m = _world_matrix(x)
                for c in x.bound_box:
                    take(m @ Vector(c))
    return lo, hi


def frame_camera(camera, objects, direction=(0.9, -1.5, 0.55), margin=1.25, aspect=None, visible_only=False):
    lo, hi = world_box(objects, visible_only)
    if lo.x > hi.x:
        return Vector()
    target = (lo + hi) / 2
    toward = Vector(direction).normalized()
    up = Vector((0, 0, 1))
    right = up.cross(toward)
    sc = bpy.context.scene
    if aspect is None:
        aspect = (sc.render.resolution_x * sc.render.pixel_aspect_x) / (sc.render.resolution_y * sc.render.pixel_aspect_y)
    cd = camera.data
    fit = cd.sensor_fit
    if fit == 'AUTO':
        fit = 'HORIZONTAL' if aspect >= 1 else 'VERTICAL'
    if fit == 'VERTICAL':
        tanV = math.tan(cd.angle_y / 2)               # three's PerspectiveCamera.fov is this vertical angle
    else:
        tanV = math.tan(cd.angle_x / 2) / aspect
    tanH = tanV * aspect
    if right.length_squared < 1e-8:
        right = Vector((1, 0, 0))
    right.normalize()
    upv = toward.cross(right).normalized()
    d = 0.01
    for x in (lo.x, hi.x):
        for y in (lo.y, hi.y):
            for z in (lo.z, hi.z):
                p = Vector((x, y, z)) - target
                d = max(d, p.dot(toward) + margin * max(abs(p.dot(right)) / tanH, abs(p.dot(upv)) / tanV))
    camera.location = target + toward * d
    cd.clip_start = max(0.001, d / 2000)
    cd.clip_end = max(20.0, d * 20)
    camera.rotation_mode = 'QUATERNION'
    camera.rotation_quaternion = (-toward).to_track_quat('-Z', 'Y')
    return target
