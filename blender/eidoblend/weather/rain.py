"""World-space rain streaks and ground splashes (weather_system.js), as Geometry Nodes generators with keyed inputs.

Streaks: every streak's world position is a pure function of (index, time, wind) tiled in WORLD space around the
camera, so the field stands still while the camera moves through it (mod-wrap in a 2 x rainRadius square, recycled
over rainHeight vertically on the integrated fall phase). A population of drop sizes (h1 squared, skewed small), width
at the drop texture's 1:8 aspect, thickened with distance so far rain reads as layers; the nearest ~2 m fade (no lens
blobs) and a circular feather hides the tile edge. Each streak faces the camera's right axis and runs along its own
velocity (wind shear tilts it). Colour is the lit rain colour with a sun-forward glint; opacity comes from the drop
texture's alpha, the world cell gate and the rain amount (a per-drop population gate, so light rain is fewer drops).

Splashes: expanding rings at the ground, tiled like the streaks, each on its own hash phase (2.4 Hz).

Blender additions, where the WebGPU edition had a flat groundY: with `occluders` (a collection), each streak is
hidden when a roof lies between it and the sky along the rain, and each splash sits on the first surface the rain
reaches (Raycast), on its slope, and only where that surface faces up. The geometry is built in three.js space
(the formulas read like the source) and rotated into Blender's Z-up at the end.
"""
import math

import bpy

from ._graph import G, gn_group, add_gn, empty_mesh_object, set_input
from .values import add_values_node

RAIN_TREE = 'eido_rain_streaks'
SPLASH_TREE = 'eido_rain_splashes'

RAIN_INPUTS = [
    ('Count', 'NodeSocketInt', 16000), ('Radius', 'NodeSocketFloat', 45.0), ('Height', 'NodeSocketFloat', 24.0),
    ('Camera', 'NodeSocketVector', None), ('Camera Right', 'NodeSocketVector', None),
    ('Fall Phase', 'NodeSocketFloat', 0.0), ('Wind Offset', 'NodeSocketVector', None), ('Wind', 'NodeSocketVector', None),
    ('Fall', 'NodeSocketFloat', 11.0), ('Streak Length', 'NodeSocketFloat', 0.4), ('Rain K', 'NodeSocketFloat', 0.0),
    ('Density', 'NodeSocketFloat', 1.0), ('Cell Lo', 'NodeSocketFloat', 0.9), ('Cell Hi', 'NodeSocketFloat', 1.45),
    ('Storm Canopy', 'NodeSocketFloat', 0.0), ('Sun Dir', 'NodeSocketVector', None),
    ('Cloud Start', 'NodeSocketFloat', 700.0), ('Cloud Drift', 'NodeSocketVector', None),
    ('Weather Scale', 'NodeSocketFloat', 1.0), ('Large T', 'NodeSocketFloat', 0.18), ('Large A', 'NodeSocketFloat', 3.0),
    ('Shelter Length', 'NodeSocketFloat', 600.0),
]
SPLASH_INPUTS = [
    ('Count', 'NodeSocketInt', 1200), ('Radius', 'NodeSocketFloat', 45.0), ('Camera', 'NodeSocketVector', None),
    ('Time', 'NodeSocketFloat', 0.0), ('Ground Y', 'NodeSocketFloat', 0.0), ('Wind', 'NodeSocketVector', None),
    ('Fall', 'NodeSocketFloat', 11.0), ('Rain K', 'NodeSocketFloat', 0.0), ('Cell Lo', 'NodeSocketFloat', 0.9),
    ('Cell Hi', 'NodeSocketFloat', 1.45), ('Storm Canopy', 'NodeSocketFloat', 0.0),
    ('Cloud Start', 'NodeSocketFloat', 700.0), ('Cloud Drift', 'NodeSocketVector', None),
    ('Weather Scale', 'NodeSocketFloat', 1.0), ('Large T', 'NodeSocketFloat', 0.18), ('Large A', 'NodeSocketFloat', 3.0),
]


def _coverage(b, weather_map, x, z, I):
    """sky.tslCoverage(x, z): clamp((map.r - largeT) * largeA, 0, 2) at uv = (z - drift.z, x - drift.x) x
    (-0.00005 wScale), the weather map repeat-wrapped and linearly filtered (three space). I = the group inputs."""
    dx, _dy, dz = b.vec(I['Cloud Drift']).xyz()
    s = b.s(I['Weather Scale']) * -0.00005
    col, _a = b.image_sample(weather_map, (z - dz) * s, (x - dx) * s, 'Linear', 'REPEAT')
    return b.clamp((b.red(col) - I['Large T']) * I['Large A'], 0.0, 2.0)


def _cell_gate(b, weather_map, x, y, z, I, wx, wz, fall, storm_h):
    """rainCellAt: the coverage at the upwind column the drops fell from, through cellLo..cellHi, opened under a
    sealed storm canopy (there each drop keeps its own 0.82-1 storm gate)."""
    k = b.max(b.s(I['Cloud Start']) - y, 0.0) / b.max(fall, 1.0)
    cov = _coverage(b, weather_map, x - wx * k, z - wz * k, I)
    ordinary = b.sstep(I['Cell Lo'], I['Cell Hi'], cov)
    canopy = b.clamp(I['Storm Canopy'])
    return b.lerp(ordinary, storm_h * 0.18 + 0.82, canopy), canopy


def build_rain_tree(weather_map, rain_material, occluders=None):
    tree, gi, go, ids = gn_group(RAIN_TREE, [('Geometry', 'NodeSocketGeometry', None)] + RAIN_INPUTS)
    b = G(tree)
    I = gi.outputs
    idx = b.index()
    h1, h2, h3, h4 = (b.hash_i(idx, k) for k in (1, 2, 3, 4))
    cx, cy, cz = b.vec(I['Camera']).xyz()
    wox, _woy, woz = b.vec(I['Wind Offset']).xyz()
    rad = b.s(I['Radius'])
    P = rad * 2.0
    H = b.s(I['Height'])
    px = cx + (b.fract(h1 + (wox - cx) / P) - 0.5) * P
    pz = cz + (b.fract(h2 + (woz - cz) / P) - 0.5) * P
    py = cy + (b.fract(h3 - b.s(I['Fall Phase']) / H - cy / H) - 0.35) * H
    base = b.combine(px, py, pz)
    wx, _wy, wz = b.vec(I['Wind']).xyz()
    fall = b.s(I['Fall'])
    sdir = b.normalize(b.combine(wx, -fall, wz))
    cam = b.vec(I['Camera'])
    dist = b.length(base - cam)
    near_fade = b.sstep(0.9, 2.6, dist)
    field_fade = 1.0 - b.sstep(rad * 0.70, rad, b.length2(px - cx, pz - cz))
    length = b.s(I['Streak Length']) * (h1 * h1 * 1.1 + 0.45)
    width = length * 0.125 * (h2 * 0.8 + 0.55) * (dist * 0.012 + 1.0)
    view = b.normalize(base - cam)
    glint_raw = b.pow(b.max(b.dot(view, I['Sun Dir']), 0.0), 6.0) * 1.6 + 0.6
    gate, canopy = _cell_gate(b, weather_map, px, py, pz, I, wx, wz, fall, h4)
    glint = b.lerp(glint_raw, 1.0, canopy) * (h4 + 0.5) * 1.08
    rain_k = b.s(I['Rain K'])
    count_gate = b.sstep(h1, h1 + 0.001, rain_k)
    boost = b.lerp(1.0, 1.28, canopy * b.clamp(rain_k))
    alpha = (near_fade * field_fade * gate * (h3 * 0.125 + 0.075) * b.s(I['Density']) * count_gate
             * b.clamp(rain_k * 2.0) * boost)
    if occluders is not None:
        target = b.blender_to_three(b.collection_geometry(occluders))
        top = base + sdir * length
        hit, _hp, _hn = b.raycast(target, top, sdir * -1.0, I['Shelter Length'])
        alpha = alpha * (1.0 - hit)
    pts = b.points(I['Count'])
    pts = b.store(pts, 'eido_alpha', alpha)
    pts = b.store(pts, 'eido_glint', glint)
    quad = b.translate(b.grid(1.0, 1.0), (0.0, 0.5, 0.0))      # x in [-0.5, 0.5], y in [0, 1]: pivot at the streak
    inst = b.instance_on_points(pts, quad)
    mat = b.combine_matrix(b.vec(I['Camera Right']) * width, sdir * length, (0.0, 0.0, 1.0), base)
    inst = b.set_instance_transform(inst, mat)
    geo = b.three_to_blender(b.realize(inst))
    geo = b.set_material(geo, rain_material)
    tree.links.new(geo, go.inputs[0])
    return tree, ids


def build_splash_tree(weather_map, splash_material, occluders=None):
    tree, gi, go, ids = gn_group(SPLASH_TREE, [('Geometry', 'NodeSocketGeometry', None)] + SPLASH_INPUTS)
    b = G(tree)
    I = gi.outputs
    idx = b.index()
    s1, s2, s3 = (b.hash_i(idx, k) for k in (11, 12, 13))
    cx, cy, cz = b.vec(I['Camera']).xyz()
    sp = b.s(I['Radius'])
    px = cx + (b.fract(s1 - cx / (sp * 2.0)) - 0.5) * (sp * 2.0)
    pz = cz + (b.fract(s2 - cz / (sp * 2.0)) - 0.5) * (sp * 2.0)
    phase = b.fract(s3 * 9.7 + b.s(I['Time']) * 2.4)
    ring_r = phase * 0.13 + 0.015
    wx, _wy, wz = b.vec(I['Wind']).xyz()
    fall = b.s(I['Fall'])
    gy = b.s(I['Ground Y'])
    if occluders is not None:
        # the first surface the rain reaches through this column (Eanpa's surface field), on its own slope
        sdir = b.normalize(b.combine(wx, -fall, wz))
        target = b.blender_to_three(b.collection_geometry(occluders))
        start = b.combine(px, cy, pz) - sdir * 300.0          # the rain ray through this column at eye height
        hit, hp, hn = b.raycast(target, start, sdir, 2000.0)
        n = b.normalize(hn)
        _nx, ny, _nz = n.xyz()
        valid = hit * b.clamp(ny)
        center = hp + n * 0.015
        hx, hy, hz = hp.xyz()
    else:
        n = b.combine(0.0, 1.0, 0.0)
        valid = 1.0
        hx, hy, hz = px, gy, pz
        center = b.combine(px, gy + 0.015, pz)
    gate, _canopy = _cell_gate(b, weather_map, hx, hy, hz, I, wx, wz, fall, s3)
    rain_k = b.s(I['Rain K'])
    count_gate = b.sstep(s1, s1 + 0.001, rain_k)
    field_fade = 1.0 - b.sstep(sp * 0.70, sp, b.length2(px - cx, pz - cz))
    alpha = (1.0 - phase) * 0.30 * field_fade * gate * count_gate * b.clamp(rain_k * 2.0) * valid
    # ring frame: tangent = normalize(cross(axis, n)), bitangent = cross(n, tangent)
    _a, any_, _c = n.xyz()
    pick = b.lt(b.abs(any_), 0.95)
    axis = b.combine(1.0 - pick, pick, 0.0)
    tangent = b.normalize(b.cross(axis, n))
    bitangent = b.cross(n, tangent)
    pts = b.points(I['Count'])
    pts = b.store(pts, 'eido_alpha', alpha)
    quad = b.grid(1.0, 1.0)                                     # in its local XY plane, normal +Z
    inst = b.instance_on_points(pts, quad)
    mat = b.combine_matrix(tangent * (ring_r * 2.0), bitangent * (ring_r * 2.0), n, center)
    inst = b.set_instance_transform(inst, mat)
    geo = b.three_to_blender(b.realize(inst))
    geo = b.set_material(geo, splash_material)
    tree.links.new(geo, go.inputs[0])
    return tree, ids


# ------------------------------------------------------------------------------------------------ materials ---

def _new_material(name):
    m = bpy.data.materials.get(name)
    if m is not None:
        bpy.data.materials.remove(m)
    m = bpy.data.materials.new(name)
    m.use_nodes = True
    m.node_tree.nodes.clear()
    m.surface_render_method = 'BLENDED'
    m.use_backface_culling = False
    try:
        m.use_transparency_overlap = True
    except AttributeError:
        pass
    return m


def rain_material(drop_texture=None):
    """eido_rain: the lit rain colour x rainLight x the per-drop glint; opacity = the drop texture's alpha (or the
    bright-core x-profile with end fades when there is no texture) x the per-streak opacity, capped at 0.72."""
    from ._graph import G
    m = _new_material('eido_rain')
    nt = m.node_tree
    b = G(nt, x0=-1400, y0=400)
    out = nt.nodes.new('ShaderNodeOutputMaterial')
    out.location = (600, 0)
    vals = add_values_node(nt)
    uv = b.vec(_attr(b, 'UVMap', 'Vector'))
    u, v, _w = uv.xyz()
    if drop_texture is not None:
        tex = b.node('ShaderNodeTexImage', interpolation='Linear', extension='EXTEND')
        tex.image = drop_texture
        b.link(b.combine(1.0 - u, 1.0 - v, 0.0), tex.inputs['Vector'])   # the drop is authored upside down
        shape = b.s(tex.outputs['Alpha'])
    else:
        xprof = b.pow(b.max(1.0 - b.abs(u * 2.0 - 1.0), 0.0), 1.6)
        shape = xprof * b.sstep(0.0, 0.18, v) * (1.0 - b.sstep(0.72, 1.0, v))
    alpha = b.clamp(shape * _attr(b, 'eido_alpha', 'Fac'), 0.0, 0.72)
    color = b.vec(vals.outputs['Rain Color']) * (b.s(vals.outputs['Rain Light']) * _attr(b, 'eido_glint', 'Fac'))
    _emit_mix(nt, b, out, color, alpha)
    return m


def splash_material():
    """eido_splash: rings (smoothstep 0.55-0.8 in, 0.85-1 out) in rainColor x 1.15."""
    from ._graph import G
    m = _new_material('eido_splash')
    nt = m.node_tree
    b = G(nt, x0=-1400, y0=400)
    out = nt.nodes.new('ShaderNodeOutputMaterial')
    out.location = (600, 0)
    vals = add_values_node(nt)
    uv = b.vec(_attr(b, 'UVMap', 'Vector'))
    u, v, _w = uv.xyz()
    rr = b.length2(u - 0.5, v - 0.5) * 2.0
    ring = b.sstep(0.55, 0.8, rr) * (1.0 - b.sstep(0.85, 1.0, rr))
    alpha = ring * _attr(b, 'eido_alpha', 'Fac')
    color = b.vec(vals.outputs['Rain Color']) * 1.15
    _emit_mix(nt, b, out, color, alpha)
    return m


def _attr(b, name, out='Fac'):
    n = b.node('ShaderNodeAttribute', attribute_type='GEOMETRY')
    n.attribute_name = name
    return b.s(n.outputs[out]) if out == 'Fac' else n.outputs[out]


def _emit_mix(nt, b, out, color, alpha):
    """Normal alpha blending of an unlit colour: Mix(Transparent, Emission(color), alpha)."""
    em = b.node('ShaderNodeEmission')
    b.link(color, em.inputs['Color'])
    em.inputs['Strength'].default_value = 1.0
    tr = b.node('ShaderNodeBsdfTransparent')
    mix = b.node('ShaderNodeMixShader')
    b.link(alpha, mix.inputs[0])
    nt.links.new(tr.outputs[0], mix.inputs[1])
    nt.links.new(em.outputs[0], mix.inputs[2])
    nt.links.new(mix.outputs[0], out.inputs['Surface'])


def build_rain_objects(collection, weather_map, drop_texture=None, occluders=None, rain_count=16000,
                       rain_radius=45.0, rain_height=24.0, splash_count=1200):
    """The two generator objects (eido_rain, eido_splashes) with their trees and materials."""
    rm = rain_material(drop_texture)
    sm = splash_material()
    rtree, rids = build_rain_tree(weather_map, rm, occluders)
    stree, sids = build_splash_tree(weather_map, sm, occluders)
    out = {}
    for name, tree, ids, mat, consts in (
            ('eido_rain', rtree, rids, rm, dict(Count=int(rain_count), Radius=float(rain_radius),
                                               Height=float(rain_height))),
            ('eido_splashes', stree, sids, sm, dict(Count=int(splash_count), Radius=float(rain_radius)))):
        ob = empty_mesh_object(name, collection)
        if not ob.data.materials:
            ob.data.materials.append(mat)
        else:
            ob.data.materials[0] = mat
        mod = add_gn(ob, tree, 'eido_weather')
        for k, v in consts.items():
            set_input(mod, ids[k], v)
        ob.visible_shadow = False
        try:
            ob.visible_volume_scatter = False
        except AttributeError:
            pass
        out[name] = dict(object=ob, modifier=mod, ids=ids)
    return out
