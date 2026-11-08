"""Lightning in the Blender scene: the strike light, one bolt ribbon per event, and per local strike its sparks,
smoke puffs and scorch, all keyed or driven by Scene Time so a saved .blend replays them.

The light is the JS PointLight (12000 cd, range 900, decay 2, no shadows): Blender watts = 4 pi x candela (measured,
probe_eevee_facts.py F5), a custom 900 m cutoff, energy keyed per frame, colour and position per event. The bolt is
rebuildBolt's ribbon (bolt.py) frozen as a mesh per event, facing the camera the event began with; its channel
afterglow is a keyed object property read by the shared additive material. Sparks (octahedra on ballistic arcs),
puffs (the gyroid-FBM burn puffs, camera-facing with a slow roll) and the scorch disc are Geometry Nodes objects
that compute everything from Scene Time and their impact's data (lightning.impact_particles), and end when their
pool slot is taken by a newer impact, as the JS pool recycles its oldest slot.
"""
import math
import re

import bpy
from mathutils import Matrix, Vector
from mathutils.bvhtree import BVHTree

from . import lightning as L
from ._graph import G, gn_group, add_gn, set_input
from .bolt import bolt_ribbon
from .keys import key_series, changes_only

BLOCKED_NAMES = re.compile(r'orb|emitter|beam|fastener|decal|foliage|vegetation|cactus|joshua', re.I)


def b3(v):
    """three (x, y, z) -> Blender (x, -z, y)."""
    return (v[0], -v[2], v[1])


def t3(v):
    """Blender (x, y, z) -> three (x, z, -y)."""
    return (v[0], v[2], -v[1])


# ------------------------------------------------------------------------------------------ the strike light ---

def strike_light(collection):
    ld = bpy.data.lights.get('eido_lightning_light') or bpy.data.lights.new('eido_lightning_light', 'POINT')
    ld.energy = 0.0
    ld.use_shadow = False
    ld.shadow_soft_size = 0.0
    ld.use_custom_distance = True
    ld.cutoff_distance = L.LIGHTNING_LIGHT_RANGE
    ob = bpy.data.objects.get('eido_lightning_light') or bpy.data.objects.new('eido_lightning_light', ld)
    if ob.name not in collection.objects:
        collection.objects.link(ob)
    return ob


def key_strike_light(ob, frames, recs):
    """recs[i] = the scheduler's frame record: energy = intensity x 4 pi, colour per event, position per strike."""
    key_series(ob.data, 'energy', frames, [r['light_intensity'] * 4 * math.pi for r in recs], 'LINEAR')
    cf, cv = changes_only(frames, [tuple(r['color']) for r in recs])
    key_series(ob.data, 'color', cf, cv, 'CONSTANT')
    pos, last = [], (0.0, 0.0, 120.0)
    for r in recs:
        if r['light_pos'] is not None:
            last = b3(r['light_pos'])
        pos.append(last)
    pf, pv = changes_only(frames, pos)
    key_series(ob, 'location', pf, pv, 'CONSTANT')


# ---------------------------------------------------------------------------------------------- the bolt ---

def bolt_material(bolt_texture=None):
    """eido_bolt: prof = 1 - |2u - 1|; core = prof^6 x 1.3 + prof^1.6 x 0.42 (white-hot core + wide glow); the top
    dissolves into the deck (smoothstep 0-0.14 of v); the trace texture's dense middle band shapes it; the core runs
    toward white; colour x channel x 26, added (the JS AdditiveBlending)."""
    m = bpy.data.materials.get('eido_bolt')
    if m is not None:
        bpy.data.materials.remove(m)
    m = bpy.data.materials.new('eido_bolt')
    m.use_nodes = True
    nt = m.node_tree
    nt.nodes.clear()
    m.surface_render_method = 'BLENDED'
    m.use_backface_culling = False
    b = G(nt, x0=-1300, y0=400)
    out = nt.nodes.new('ShaderNodeOutputMaterial')
    out.location = (500, 0)
    uvn = b.node('ShaderNodeAttribute', attribute_type='GEOMETRY')
    uvn.attribute_name = 'UVMap'
    u, v, _ = b.vec(uvn.outputs['Vector']).xyz()
    ch = b.node('ShaderNodeAttribute', attribute_type='OBJECT')
    ch.attribute_name = 'eido_channel'
    channel = b.s(ch.outputs['Fac'])
    col = b.node('ShaderNodeAttribute', attribute_type='GEOMETRY')
    col.attribute_name = 'eido_color'
    color = b.vec(col.outputs['Color'])
    prof = b.max(1.0 - b.abs(u * 2.0 - 1.0), 0.0)
    core = b.pow(prof, 6.0) * 1.3 + b.pow(prof, 1.6) * 0.42
    cloud_fade = b.sstep(0.0, 0.14, v)
    if bolt_texture is not None:
        tex = b.node('ShaderNodeTexImage', interpolation='Linear', extension='EXTEND')
        tex.image = bolt_texture
        b.link(b.combine(u, v * 0.44 + 0.28, 0.0), tex.inputs['Vector'])
        tex_a = b.s(tex.outputs['Alpha'])
    else:
        tex_a = 1.0
    k = b.pow(prof, 10.0) * 0.34
    core_tint = color + (b.combine(1.0, 1.0, 1.0) - color) * k
    opacity = core * tex_a * cloud_fade * b.clamp(channel * 3.0)
    emit = core_tint * (channel * 26.0 * opacity)
    em = b.node('ShaderNodeEmission')
    b.link(emit, em.inputs['Color'])
    tr = b.node('ShaderNodeBsdfTransparent')
    add = b.node('ShaderNodeAddShader')
    nt.links.new(tr.outputs[0], add.inputs[0])
    nt.links.new(em.outputs[0], add.inputs[1])
    nt.links.new(add.outputs[0], out.inputs['Surface'])
    return m


def make_bolt(event, collection, material, frames, recs):
    """The ribbon of one event as a mesh object (Blender space), with its channel afterglow keyed (and hidden from
    renders while it is not drawn, as the JS hides the bolt mesh)."""
    st = event['strike']
    pos, uvs, tris = bolt_ribbon(event['interval'], event['cam']['pos'], st['x'], st['z'], st['y'],
                                 event['cloud_start'])
    name = 'eido_bolt_%03d' % event['interval']
    old = bpy.data.objects.get(name)
    if old is not None:
        bpy.data.objects.remove(old, do_unlink=True)
    me = bpy.data.meshes.new(name)
    me.from_pydata([b3(p) for p in pos], [], tris)
    uvl = me.uv_layers.new(name='UVMap')
    for poly in me.polygons:
        for li in poly.loop_indices:
            uvl.data[li].uv = uvs[me.loops[li].vertex_index]
    ca = me.color_attributes.new('eido_color', 'FLOAT_COLOR', 'POINT')
    c = tuple(event['color']) + (1.0,)
    for d in ca.data:
        d.color = c
    me.materials.append(material)
    ob = bpy.data.objects.new(name, me)
    collection.objects.link(ob)
    ob.visible_shadow = False
    ob['eido_channel'] = 0.0
    ob['eido_interval'] = event['interval']
    I = event['interval']
    ch = [r['channel'] if r['bolt_seed'] == I else 0.0 for r in recs]
    vis = [1.0 if r['bolt_seed'] == I else 0.0 for r in recs]
    lo = next((i for i, x in enumerate(vis) if x), None)
    if lo is None:                             # the event began but was never drawn (no frame inside its glow)
        hide = [True] * len(frames)
    else:
        hide = [not x for x in vis]
    key_series(ob, '["eido_channel"]', frames, ch, 'LINEAR')
    hf, hv = changes_only(frames, [float(h) for h in hide])
    key_series(ob, 'hide_render', hf, hv, 'CONSTANT')
    key_series(ob, 'hide_viewport', hf, hv, 'CONSTANT')
    return ob


# ------------------------------------------------------------------------------------------ impact objects ---

def _octahedron(b):
    """OctahedronGeometry(1, 0): two open square pyramids, apexes on +-Z, equator on the X and Y axes."""
    cone = b.node('GeometryNodeMeshCone', fill_type='NONE')
    cone.inputs['Vertices'].default_value = 4
    cone.inputs['Radius Top'].default_value = 0.0
    cone.inputs['Radius Bottom'].default_value = 1.0
    cone.inputs['Depth'].default_value = 1.0
    up = b.node('GeometryNodeTransform')
    b.links.new(cone.outputs['Mesh'], up.inputs['Geometry'])
    up.inputs['Translation'].default_value = (0, 0, 0.5)
    down = b.node('GeometryNodeTransform')
    b.links.new(up.outputs['Geometry'], down.inputs['Geometry'])
    down.inputs['Scale'].default_value = (1, 1, -1)
    join = b.node('GeometryNodeJoinGeometry')
    b.links.new(down.outputs['Geometry'], join.inputs[0])
    b.links.new(up.outputs['Geometry'], join.inputs[0])
    return join.outputs['Geometry']


def _age(b, gi, life):
    """(age, alive 0/1) on Scene Time: alive while 0 < age < min(life, end - birth)."""
    age = b.scene_seconds() - gi.outputs['Birth']
    end = b.min(life, b.s(gi.outputs['End']) - gi.outputs['Birth'])
    alive = b.gt(age, 0.0) * b.lt(age, end)
    return age, alive


def sparks_tree():
    name = 'eido_impact_sparks'
    if name in bpy.data.node_groups:
        return bpy.data.node_groups[name], _ids(bpy.data.node_groups[name])
    tree, gi, go, ids = gn_group(name, [('Geometry', 'NodeSocketGeometry', None), ('Birth', 'NodeSocketFloat', 0.0),
                                        ('End', 'NodeSocketFloat', 0.0), ('Origin', 'NodeSocketVector', None),
                                        ('Normal', 'NodeSocketVector', None), ('Color', 'NodeSocketColor', None)])
    b = G(tree)
    I = gi.outputs
    age, alive = _age(b, gi, L.SPARK_LIFE)
    v = b.named('velocity', 'FLOAT_VECTOR')
    ln = b.named('length')
    n = b.vec(I['Normal'])
    pos = b.vec(I['Origin']) + v * age + n * (age * age * -4.9)
    d = b.normalize(v + n * (age * -9.8))
    _dx, dy, _dz = d.xyz()
    pick = b.gt(b.abs(dy), 0.99)                           # any frame with Y on d: the octahedron is symmetric
    ref = b.combine(pick, 0.0, 1.0 - pick)
    xa = b.normalize(b.cross(d, ref))
    za = b.cross(xa, d)
    alpha = b.max(1.0 - age / L.SPARK_LIFE, 0.0)
    sy = ln * (1.0 - age / L.SPARK_LIFE * 0.65)
    pts = b.delete_where(gi.outputs['Geometry'], 1.0 - alive)
    pts = b.store(pts, 'eido_alpha', alpha)
    pts = b.store(pts, 'eido_color', I['Color'], 'FLOAT_COLOR')
    inst = b.instance_on_points(pts, _octahedron(b))
    inst = b.set_instance_transform(inst, b.combine_matrix(xa * 0.038, d * sy, za * 0.038, pos))
    geo = b.three_to_blender(b.realize(inst))
    geo = b.set_material(geo, spark_material())
    tree.links.new(geo, go.inputs[0])
    return tree, ids


def _ids(tree):
    return {it.name: it.identifier for it in tree.interface.items_tree if getattr(it, 'in_out', '') == 'INPUT'}


def spark_material():
    m = bpy.data.materials.get('eido_spark')
    if m is not None:
        return m
    m = bpy.data.materials.new('eido_spark')
    m.use_nodes = True
    nt = m.node_tree
    nt.nodes.clear()
    m.surface_render_method = 'BLENDED'
    m.use_backface_culling = False
    b = G(nt)
    out = nt.nodes.new('ShaderNodeOutputMaterial')
    a = b.node('ShaderNodeAttribute', attribute_type='GEOMETRY')
    a.attribute_name = 'eido_alpha'
    c = b.node('ShaderNodeAttribute', attribute_type='GEOMETRY')
    c.attribute_name = 'eido_color'
    alpha = b.s(a.outputs['Fac'])
    emit = b.vec(c.outputs['Color']) * (alpha * 9.0 * alpha)          # additive: colour x 9 alpha, times alpha
    em = b.node('ShaderNodeEmission')
    b.link(emit, em.inputs['Color'])
    tr = b.node('ShaderNodeBsdfTransparent')
    add = b.node('ShaderNodeAddShader')
    nt.links.new(tr.outputs[0], add.inputs[0])
    nt.links.new(em.outputs[0], add.inputs[1])
    nt.links.new(add.outputs[0], out.inputs['Surface'])
    return m


def puffs_tree():
    name = 'eido_impact_puffs'
    if name in bpy.data.node_groups:
        return bpy.data.node_groups[name], _ids(bpy.data.node_groups[name])
    tree, gi, go, ids = gn_group(name, [
        ('Geometry', 'NodeSocketGeometry', None), ('Birth', 'NodeSocketFloat', 0.0), ('End', 'NodeSocketFloat', 0.0),
        ('Origin', 'NodeSocketVector', None), ('Normal', 'NodeSocketVector', None),
        ('Camera Right', 'NodeSocketVector', None), ('Camera Up', 'NodeSocketVector', None),
        ('Puff Color', 'NodeSocketColor', None), ('Glow Color', 'NodeSocketColor', None)])
    b = G(tree)
    I = gi.outputs
    age, alive = _age(b, gi, L.PUFF_LIFE)
    off = b.named('offset', 'FLOAT_VECTOR')
    drift = b.named('drift', 'FLOAT_VECTOR')
    size0 = b.named('size')
    jitter = b.named('jitter')
    roll = b.named('roll0') + b.named('roll_rate') * age
    n = b.vec(I['Normal'])
    pos = b.vec(I['Origin']) + off + drift * age + n * (age * age * 0.14)
    growth = b.pow(b.max(age, 0.0) / L.PUFF_LIFE, 0.25)
    size = size0 * (growth * 1.5 * jitter + 0.6)
    r, u = b.vec(I['Camera Right']), b.vec(I['Camera Up'])
    cr, sr = b.cos(roll), b.sin(roll)
    xa = r * cr + u * sr
    ya = u * cr - r * sr
    za = b.cross(r, u)
    seed = b.fract(b.index() * 0.6180339887 + 0.317)
    pts = b.delete_where(gi.outputs['Geometry'], 1.0 - alive)
    pts = b.store(pts, 'eido_seed', seed)                      # the slot's instanceIndex, before any deletion
    pts = b.store(pts, 'eido_alpha', b.min(1.0, age / 0.15))
    pts = b.store(pts, 'eido_age01', age / L.PUFF_LIFE)
    pts = b.store(pts, 'eido_glow', b.exp(age * -3.4) * 1.1 + b.exp(age * -0.8) * 0.30)
    pts = b.store(pts, 'eido_puff_color', I['Puff Color'], 'FLOAT_COLOR')
    pts = b.store(pts, 'eido_glow_color', I['Glow Color'], 'FLOAT_COLOR')
    ico = b.node('GeometryNodeMeshIcoSphere')
    ico.inputs['Radius'].default_value = 1.0
    ico.inputs['Subdivisions'].default_value = 2                 # 80 faces: three IcosahedronGeometry(1, 1)
    sphere = b.store(ico.outputs['Mesh'], 'eido_lp', b.position(), 'FLOAT_VECTOR')
    inst = b.instance_on_points(pts, sphere)
    inst = b.set_instance_transform(inst, b.combine_matrix(xa * size, ya * size, za * size, pos))
    geo = b.three_to_blender(b.realize(inst))
    geo = b.set_material(geo, puff_material())
    tree.links.new(geo, go.inputs[0])
    return tree, ids


def puff_material():
    """The gyroid-FBM burn puff: abs(gyroid) FBM with z feedback (6 octaves), its finite-difference normal top-lights
    the smoke, power curves drive growth / burn / fade, an ember core in the strike colour dies into ash grey."""
    m = bpy.data.materials.get('eido_puff')
    if m is not None:
        return m
    m = bpy.data.materials.new('eido_puff')
    m.use_nodes = True
    nt = m.node_tree
    nt.nodes.clear()
    m.surface_render_method = 'BLENDED'
    m.use_backface_culling = False
    b = G(nt, x0=-3000, y0=1200)
    out = nt.nodes.new('ShaderNodeOutputMaterial')
    out.location = (800, 0)

    def attr(name, o='Fac'):
        a = b.node('ShaderNodeAttribute', attribute_type='GEOMETRY')
        a.attribute_name = name
        return b.s(a.outputs[o]) if o == 'Fac' else b.vec(a.outputs[o])

    lpx, lpy, lpz = attr('eido_lp', 'Vector').xyz()
    seed = attr('eido_seed')
    age01, alpha, glow_k = attr('eido_age01'), attr('eido_alpha'), attr('eido_glow')
    puff_color = attr('eido_puff_color', 'Color')
    glow_color = attr('eido_glow_color', 'Color')
    t = b.clamp(age01 * 1.1 - seed * 0.10)
    growth = b.pow(t, 0.2)
    fade = 1.0 - b.pow(t, 7.0)
    burn = 1.0 - b.pow(t, 0.4)
    scroll = b.pow(t, 0.4) * 1.1 + seed * 196.128
    px = lpx * 2.2 + seed * 17.3
    py = lpy * 2.2 + seed * 17.3
    pz = lpz * 2.2 + scroll + seed * 17.3

    def gyroid(x, y, z):
        return b.cos(x) * b.sin(y) + b.cos(y) * b.sin(z) + b.cos(z) * b.sin(x)

    def fbm(x, y, z):
        result = 0.0
        amp = 0.5
        for _ in range(6):
            z = z + result * 0.1
            result = result + b.abs(gyroid(x / amp, y / amp, z / amp) * amp)
            amp /= 1.7
        return result

    noise = fbm(px, py, pz)
    nx = fbm(px + 0.15, py, pz)
    ny = fbm(px, py + 0.15, pz)
    nrm = b.normalize(b.combine(noise - nx, noise - ny, noise - 1.0))
    _a, nyv, _c = nrm.xyz()
    shade = nyv * 0.5 + 0.5
    smoke = noise - burn * 2.6
    white = b.combine(1.0, 1.0, 1.0)
    ember = (white + (glow_color - white) * 0.55) * (4.6 * (shade * 0.45 + 0.75) * (glow_k * 0.5 + 1.0))
    grey = b.clamp(smoke * shade, 0.0, 1.6)
    smoke_col = puff_color * (grey * 1.2 + 0.15) + glow_color * (glow_k * 0.35)
    col = ember + (smoke_col - ember) * b.sstep(0.0, 0.1, smoke)
    radius = noise * growth * 0.5
    shape = 1.0 - b.sstep(0.0, 0.05, b.length2(lpx, lpy) - radius)
    a = shape * fade * (seed * 0.3 + 0.82) * alpha
    em = b.node('ShaderNodeEmission')
    b.link(col, em.inputs['Color'])
    tr = b.node('ShaderNodeBsdfTransparent')
    mix = b.node('ShaderNodeMixShader')
    b.link(a, mix.inputs[0])
    nt.links.new(tr.outputs[0], mix.inputs[1])
    nt.links.new(em.outputs[0], mix.inputs[2])
    nt.links.new(mix.outputs[0], out.inputs['Surface'])
    return m


def scorch_tree():
    name = 'eido_impact_scorch'
    if name in bpy.data.node_groups:
        return bpy.data.node_groups[name], _ids(bpy.data.node_groups[name])
    tree, gi, go, ids = gn_group(name, [
        ('Geometry', 'NodeSocketGeometry', None), ('Birth', 'NodeSocketFloat', 0.0), ('End', 'NodeSocketFloat', 0.0),
        ('Axis X', 'NodeSocketVector', None), ('Axis Y', 'NodeSocketVector', None), ('Axis Z', 'NodeSocketVector', None),
        ('Center', 'NodeSocketVector', None), ('Strike Color', 'NodeSocketColor', None)])
    b = G(tree)
    I = gi.outputs
    age, alive = _age(b, gi, L.SCORCH_LIFETIME)
    hot = b.max(1.0 - age / 1.4, 0.0)
    fade = b.lerp(1.0, b.max(1.0 - (age - 65.0) / 25.0, 0.0), b.gt(age, 65.0))
    alpha = (0.62 - hot * 0.10) * fade * alive
    sr, sg, sb = b.vec(I['Strike Color']).xyz()
    color = b.combine(sr * 0.22 * hot + 0.018, sg * 0.18 * hot + 0.011, sb * 0.14 * hot + 0.007)
    circ = b.node('GeometryNodeMeshCircle', fill_type='TRIANGLE_FAN')
    circ.inputs['Vertices'].default_value = 32
    circ.inputs['Radius'].default_value = 1.0
    disc = b.store(circ.outputs['Mesh'], 'eido_lp', b.position(), 'FLOAT_VECTOR')
    disc = b.store(disc, 'eido_alpha', alpha)
    disc = b.store(disc, 'eido_color', color, 'FLOAT_COLOR')
    pt = b.points(1)
    inst = b.instance_on_points(pt, disc)
    inst = b.set_instance_transform(inst, b.combine_matrix(I['Axis X'], I['Axis Y'], I['Axis Z'], I['Center']))
    geo = b.three_to_blender(b.realize(inst))
    geo = b.set_material(geo, scorch_material())
    tree.links.new(geo, go.inputs[0])
    return tree, ids


def scorch_material():
    """The char decal: a broken-edged disc (two angular sines) with seven thin tendrils, a slightly lighter core."""
    m = bpy.data.materials.get('eido_scorch')
    if m is not None:
        return m
    m = bpy.data.materials.new('eido_scorch')
    m.use_nodes = True
    nt = m.node_tree
    nt.nodes.clear()
    m.surface_render_method = 'BLENDED'
    m.use_backface_culling = False
    b = G(nt)
    out = nt.nodes.new('ShaderNodeOutputMaterial')

    def attr(name, o='Fac'):
        a = b.node('ShaderNodeAttribute', attribute_type='GEOMETRY')
        a.attribute_name = name
        return b.s(a.outputs[o]) if o == 'Fac' else b.vec(a.outputs[o])

    lx, ly, _lz = attr('eido_lp', 'Vector').xyz()
    radius = b.length2(lx, ly)                       # length(uv - 0.5) * 2 for CircleGeometry's uv
    angle = b.atan2(ly, lx)
    broken = b.sin(angle * 5.0 + 1.7) * 0.075 + b.sin(angle * 11.0 - 0.8) * 0.038
    edge = broken + 0.91
    char = 1.0 - b.sstep(edge - 0.18, edge + 0.045, radius)
    tendril = b.pow(b.max(b.sin(angle * 7.0 + 0.6), 0.0), 18.0)
    band = b.sstep(0.46, 0.84, radius) * (1.0 - b.sstep(0.88, 1.18, radius))
    shape = b.max(char, tendril * band * 0.24)
    core = (1.0 - b.sstep(0.0, 0.72, radius)) * 0.22 + 0.78
    color = attr('eido_color', 'Color') * core
    alpha = shape * attr('eido_alpha')
    em = b.node('ShaderNodeEmission')
    b.link(color, em.inputs['Color'])
    tr = b.node('ShaderNodeBsdfTransparent')
    mix = b.node('ShaderNodeMixShader')
    b.link(alpha, mix.inputs[0])
    nt.links.new(tr.outputs[0], mix.inputs[1])
    nt.links.new(em.outputs[0], mix.inputs[2])
    nt.links.new(mix.outputs[0], out.inputs['Surface'])
    return m


def _point_mesh(name, rows):
    """A point cloud mesh (all points at the origin) carrying per-point float / vector attributes."""
    me = bpy.data.meshes.new(name)
    me.from_pydata([(0.0, 0.0, 0.0)] * len(rows), [], [])
    for key in rows[0]:
        v0 = rows[0][key]
        if isinstance(v0, (tuple, list)):
            a = me.attributes.new(key, 'FLOAT_VECTOR', 'POINT')
            a.data.foreach_set('vector', [c for r in rows for c in r[key]])
        else:
            a = me.attributes.new(key, 'FLOAT', 'POINT')
            a.data.foreach_set('value', [float(r[key]) for r in rows])
    return me


def _host(name, mesh, collection):
    old = bpy.data.objects.get(name)
    if old is not None:
        bpy.data.objects.remove(old, do_unlink=True)
    ob = bpy.data.objects.new(name, mesh)
    collection.objects.link(ob)
    ob.visible_shadow = False
    return ob


def quat_from_units(a, b):
    """three Quaternion.setFromUnitVectors(a, b) as (x, y, z, w)."""
    r = a[0] * b[0] + a[1] * b[1] + a[2] * b[2] + 1
    if r < 1e-8:
        q = (-a[1], a[0], 0.0) if abs(a[0]) > abs(a[2]) else (0.0, -a[2], a[1])
        r = 0.0
    else:
        q = (a[1] * b[2] - a[2] * b[1], a[2] * b[0] - a[0] * b[2], a[0] * b[1] - a[1] * b[0])
    n = math.sqrt(q[0] ** 2 + q[1] ** 2 + q[2] ** 2 + r * r)
    return (q[0] / n, q[1] / n, q[2] / n, r / n)


def _rotate(q, v):
    x, y, z, w = q
    qv = (x, y, z)
    t = [2 * c for c in (qv[1] * v[2] - qv[2] * v[1], qv[2] * v[0] - qv[0] * v[2], qv[0] * v[1] - qv[1] * v[0])]
    return (v[0] + w * t[0] + (qv[1] * t[2] - qv[2] * t[1]), v[1] + w * t[1] + (qv[2] * t[0] - qv[0] * t[2]),
            v[2] + w * t[2] + (qv[0] * t[1] - qv[1] * t[0]))


def make_impact(impact, collection, frames, times, recs_cam, scene_offset):
    """The sparks, puffs and scorch of one local impact. recs_cam[i] = (right, up) three-space camera axes at
    frames[i] (weather time times[i]); scene_offset = frame_start / fps (Scene Time seconds minus weather time)."""
    I = impact['interval']
    d = impact['data']
    n = d['normal']
    origin = impact['point']
    birth = impact['birth'] + scene_offset
    col = tuple(impact['color'])
    sp_tree, sp_ids = sparks_tree()
    pf_tree, pf_ids = puffs_tree()
    sc_tree, sc_ids = scorch_tree()
    sparks = _host('eido_impact_sparks_%03d' % I, _point_mesh('eido_impact_sparks_%03d' % I, [
        dict(velocity=s['velocity'], length=s['length']) for s in d['sparks']]), collection)
    mod = add_gn(sparks, sp_tree, 'eido_weather')
    for k, v in (('Birth', birth), ('End', impact['fx_end'] + scene_offset), ('Origin', origin), ('Normal', n),
                 ('Color', col + (1.0,))):
        set_input(mod, sp_ids[k], v)
    puffs = _host('eido_impact_puffs_%03d' % I, _point_mesh('eido_impact_puffs_%03d' % I, [
        dict(offset=p['offset'], drift=p['drift'], size=p['size'], jitter=p['jitter'], roll0=p['roll0'],
             roll_rate=p['roll_rate']) for p in d['puffs']]), collection)
    mod = add_gn(puffs, pf_tree, 'eido_weather')
    puff_col = (0.16 + col[0] * 0.10, 0.17 + col[1] * 0.10, 0.185 + col[2] * 0.11, 1.0)
    for k, v in (('Birth', birth), ('End', impact['fx_end'] + scene_offset), ('Origin', origin), ('Normal', n),
                 ('Puff Color', puff_col), ('Glow Color', col + (1.0,))):
        set_input(mod, pf_ids[k], v)
    # the camera axes the puffs face, keyed over their life (one frame of margin either side)
    from ._graph import mod_path
    ks = [(f, rc) for f, t, rc in zip(frames, times, recs_cam)
          if impact['birth'] - 0.1 <= t <= min(impact['fx_end'], impact['birth'] + L.PUFF_LIFE) + 0.1]
    if ks:
        key_series(puffs, mod_path(mod, pf_ids['Camera Right']), [f for f, _ in ks], [rc[0] for _, rc in ks], 'LINEAR')
        key_series(puffs, mod_path(mod, pf_ids['Camera Up']), [f for f, _ in ks], [rc[1] for _, rc in ks], 'LINEAR')
    # the scorch disc: the JS mesh quaternion setFromUnitVectors(+Z, n), scaled, 1.8 cm above the surface
    q = quat_from_units((0.0, 0.0, 1.0), n)
    s = d['scorch_size']
    ax = [tuple(c * s for c in _rotate(q, e)) for e in ((1, 0, 0), (0, 1, 0), (0, 0, 1))]
    center = tuple(origin[i] + n[i] * 0.018 for i in range(3))
    scorch = _host('eido_impact_scorch_%03d' % I, bpy.data.meshes.new('eido_impact_scorch_%03d' % I), collection)
    mod = add_gn(scorch, sc_tree, 'eido_weather')
    for k, v in (('Birth', birth), ('End', impact['scorch_end'] + scene_offset), ('Axis X', ax[0]), ('Axis Y', ax[1]),
                 ('Axis Z', ax[2]), ('Center', center), ('Strike Color', col + (1.0,))):
        set_input(mod, sc_ids[k], v)
    return dict(sparks=sparks, puffs=puffs, scorch=scorch)


# --------------------------------------------------------------------------------- the local-strike ray cast ---

def _blocked(ob):
    """blockedStrikeReceiver: hidden, flagged, named like an emitter / decal / plant (up the parent chain and its
    collections), or a transparent first material."""
    node = ob
    while node is not None:
        if node.hide_render or node.get('eido_noLightningStrike') or BLOCKED_NAMES.search(node.name or ''):
            return True
        node = node.parent
    for c in ob.users_collection:
        if BLOCKED_NAMES.search(c.name or ''):
            return True
    mats = [s.material for s in ob.material_slots if s.material]
    if mats:
        m = mats[0]
        if getattr(m, 'surface_render_method', 'DITHERED') == 'BLENDED':
            return True
        if m.use_nodes and m.node_tree:
            p = next((n for n in m.node_tree.nodes if n.bl_idname == 'ShaderNodeBsdfPrincipled'), None)
            if p is not None and not p.inputs['Alpha'].is_linked and p.inputs['Alpha'].default_value < 0.95:
                return True
    return False


def resolve_targets(targets):
    """strikeTargets (objects, collections, or a callable returning them) -> mesh objects."""
    value = targets() if callable(targets) else targets
    if value is None:
        return []
    if not isinstance(value, (list, tuple, set)):
        value = [value]
    out = []
    for v in value:
        if isinstance(v, bpy.types.Collection):
            out.extend(o for o in v.all_objects if o.type == 'MESH')
        elif isinstance(v, bpy.types.Object) and v.type == 'MESH':
            out.append(v)
    return [o for o in out if not o.name.startswith('eido_')]


def make_strike_finder(targets, strike_height_at=None):
    """find_local_strike(interval, cam, sky, prefer_forward) for the scheduler: candidates from lightning.py, every
    surface along each column (downward rays, world-space BVH of the evaluated meshes), the JS receiver rules."""
    def column_hits(trees, x, y, top_z, far):
        hits = []
        for ob, bvh in trees:
            origin = Vector((x, y, top_z))
            d = Vector((0.0, 0.0, -1.0))
            travelled = 0.0
            while travelled < far:
                loc, nrm, _i, dist = bvh.ray_cast(origin, d, far - travelled)
                if loc is None:
                    break
                travelled += dist
                hits.append((travelled, loc.copy(), nrm.normalized(), ob))
                origin = loc + d * 1e-4
                travelled += 1e-4
        return sorted(hits, key=lambda h: h[0])

    def find(interval, cam, sky, prefer_forward):
        objs = resolve_targets(targets)
        dg = bpy.context.evaluated_depsgraph_get()
        trees = []
        for ob in objs:
            ev = ob.evaluated_get(dg)
            me = ev.to_mesh()
            mw = ev.matrix_world
            verts = [mw @ v.co for v in me.vertices]
            polys = [tuple(p.vertices) for p in me.polygons]
            ev.to_mesh_clear()
            if polys:
                trees.append((ob, BVHTree.FromPolygons(verts, polys)))
        cloud_top = float(sky['cloudStart']) + float(sky['cloudHeight']) + 100
        cp = cam['pos']
        top_y = max(cloud_top, cp[1] + 700)
        far = max(2400.0, top_y + 1200)
        for x3, z3 in L.strike_candidates(interval, cp, cam['forward'], prefer_forward):
            for _dist, loc, nrm, ob in column_hits(trees, x3, -z3, top_y, far):
                if _blocked(ob):
                    continue
                n3 = t3(nrm)
                if n3[1] < L.UPWARD_NORMAL_MIN:
                    continue
                p3 = t3(loc)
                if math.hypot(p3[0] - cp[0], p3[2] - cp[2]) < L.LOCAL_STRIKE_PLAYER_GUARD:
                    continue
                return dict(point=p3, normal=n3, kind=ob.name or 'upward_surface', object=ob)
            hit = _terrain_fallback(strike_height_at, x3, z3, cp)
            if hit:
                return hit
        return None
    return find


def _terrain_fallback(height_at, x3, z3, cp):
    """fallbackTerrainStrike with a Blender heightfield height_at(x, y) -> z (None or non-finite: no surface)."""
    if height_at is None:
        return None
    if math.hypot(x3 - cp[0], z3 - cp[2]) < L.LOCAL_STRIKE_PLAYER_GUARD:
        return None
    e = 0.75
    bx, by = x3, -z3
    try:
        y, xlo, xhi, zlo, zhi = (float(height_at(*xy)) for xy in ((bx, by), (bx - e, by), (bx + e, by),
                                                                     (bx, by + e), (bx, by - e)))
    except (TypeError, ValueError):
        return None
    if not all(math.isfinite(v) for v in (y, xlo, xhi, zlo, zhi)):
        return None
    n = (-(xhi - xlo) / (e * 2), 1.0, -(zhi - zlo) / (e * 2))      # three z = -Blender y: zlo at by + e
    ln = math.sqrt(sum(c * c for c in n))
    n = tuple(c / ln for c in n)
    if n[1] < L.UPWARD_NORMAL_MIN:
        return None
    return dict(point=(x3, y, z3), normal=n, kind='terrain_heightfield', object=None)
