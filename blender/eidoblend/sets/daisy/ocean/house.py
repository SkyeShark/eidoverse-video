"""ocean/house.py: the small house on the spit (port of eidoverse/sets/ocean/house.js): ocean_house.glb from the model
library (eidoverse/assets/models/), built in Blender by eidoverse/assets/sets/ocean_src/house/*.py.

One window, warm, switched on with the kick at bar 12 ("is there someone home"); the porch light, the most important
light of the verse, comes on at "on" (u 28.13): an incandescent swell with a breath of flicker, a halo in the sea air,
a pool of light on the porch, a glint on the cove (the sea reads porch_world / window_world).

    house = build_house(parent=layout_empty)  -> None (no GLB) | House: group (origin at grade, front -Y), porch_local,
                                                 window_local (house-local, three axes), porch_light, win_light, halo,
                                                 update(u, t, key, frame), state(u, t), targets()
    the uniforms porch / win / t are custom properties on house.group; the materials and lights follow by drivers
"""

from __future__ import annotations

import math
import os
import re

from .util import MODELS, smooth

WARM = (1.0, 0.6, 0.28)
LAMP = (1.0, 0.64, 0.32)
PORCH_CD, WIN_CD = 7.5, 1.6


def window_level(u):
    """someone home: the window on the downbeat of bar 12 (a lamp switched on inside)."""
    return 0.0 if u < 22.52 else smooth((u - 22.52) / 0.3)


def porch_level(u, t):
    """the porch light on "on": incandescent swell, a single catch, then steady with a faint breath."""
    if u < 28.13:
        return 0.0
    a = u - 28.13
    catch = 1 - 0.18 * math.exp(-((a - 0.2) / 0.035) ** 2) if a < 0.3 else 1.0
    return smooth(a / 0.14) * catch * (1 + 0.012 * math.sin(t * 7.3))


def _mats_by_name(objs, rx):
    """materials of meshes whose own name, an ancestor's or the material's name matches (glTF wraps meshes)."""
    out = []
    for o in objs:
        if o.type != 'MESH':
            continue
        n, hit = o, False
        while n is not None and not hit:
            hit = bool(rx.search(n.name))
            n = n.parent
        for m in o.data.materials:
            if m is not None and (hit or rx.search(m.name)) and m not in out:
                out.append(m)
    return out


def _driven_value(mat, label, source, prop, expr='x'):
    """a Value node in mat's tree, driven by source[prop]"""
    nt = mat.node_tree
    n = nt.nodes.get(label)
    if n is None:
        n = nt.nodes.new('ShaderNodeValue')
        n.name = n.label = label
        n.location = (-1200, -800 - 80 * len(nt.nodes))
    fc = nt.driver_add(f'nodes["{label}"].outputs[0].default_value')
    d = fc.driver
    d.type = 'SCRIPTED'
    for v in list(d.variables):
        d.variables.remove(v)
    v = d.variables.new()
    v.name = 'x'
    v.type = 'SINGLE_PROP'
    v.targets[0].id_type = 'OBJECT'
    v.targets[0].id = source
    v.targets[0].data_path = f'["{prop}"]'
    d.expression = expr
    return n


def _bsdf(mat):
    return next((n for n in mat.node_tree.nodes if n.type == 'BSDF_PRINCIPLED'), None)


def _base_color_socket(mat, bsdf):
    s = bsdf.inputs['Base Color']
    return s.links[0].from_socket if s.is_linked else None


def _emit(mat, factor_sock, color, base_sock=None, scale=1.0):
    """Principled emission = (base colour x) color x factor x scale"""
    nt = mat.node_tree
    b = _bsdf(mat)
    m1 = nt.nodes.new('ShaderNodeVectorMath')
    m1.operation = 'SCALE'
    m1.inputs[0].default_value = color
    nt.links.new(factor_sock, m1.inputs['Scale'])
    cur = m1.outputs[0]
    if base_sock is not None:
        m2 = nt.nodes.new('ShaderNodeVectorMath')
        m2.operation = 'MULTIPLY'
        nt.links.new(base_sock, m2.inputs[0])
        nt.links.new(cur, m2.inputs[1])
        cur = m2.outputs[0]
    nt.links.new(cur, b.inputs['Emission Color'])
    b.inputs['Emission Strength'].default_value = scale


def _glass(mat, alpha, rough):
    b = _bsdf(mat)
    b.inputs['Alpha'].default_value = alpha
    b.inputs['Roughness'].default_value = rough
    b.inputs['Metallic'].default_value = 0.0
    if hasattr(mat, 'surface_render_method'):
        mat.surface_render_method = 'BLENDED'


class House:
    def __init__(self, **kw):
        self.__dict__.update(kw)

    @property
    def U(self):
        return self.group

    def update(self, u, t, key=None, frame=None):
        """the window at bar 12, the porch light on "on": writes (and keys) the uniforms; lights follow by driver."""
        from . import _bl
        for k, v in self.state(u, t).items():
            if k in ('porch', 'win', 't'):
                _bl.set_prop(self.group, k, v, key=key, frame=frame)

    def state(self, u, t):
        return {'porch': porch_level(u, t), 'win': window_level(u), 't': t}

    def targets(self):
        return {k: (self.group, f'["{k}"]', None, 'LINEAR') for k in ('porch', 'win', 't')}

    def porch_world(self):
        from mathutils import Vector
        return self.group.matrix_world @ Vector((self.porch_local[0], -self.porch_local[2], self.porch_local[1]))

    def window_world(self):
        from mathutils import Vector
        return self.group.matrix_world @ Vector((self.window_local[0], -self.window_local[2], self.window_local[1]))


def build_house(path=None, parent=None, collection=None):
    """buildHouse(THREE, { path }) -> None | House. The GLB's materials stay the importer's Principled (they carry
    their baked colour, normal and ORM maps); the window and the lamp get their emissive layers and glass."""
    import bpy
    from . import _bl
    from ._billboards import quad_arrays, additive_emission
    path = path or os.path.join(MODELS, 'ocean_house.glb')
    if not os.path.isfile(path):
        print('[ocean] house.glb not found:', path)
        return None
    col = collection or bpy.context.scene.collection
    root, objs = _bl.import_glb(path, 'ocean:house', collection=col, parent=parent)
    root.rotation_mode = 'XYZ'
    for k, v in (('porch', 0.0), ('win', 0.0), ('t', 0.0)):
        root[k] = v
    for o in objs:
        if o.type == 'MESH':
            o.visible_shadow = True
    # the window: warm light behind the curtain; the glass carries it
    for m in _mats_by_name(objs, re.compile('window_curtain', re.I)):
        b = _bsdf(m)
        if b is None:
            continue
        v = _driven_value(m, 'ocean_win', root, 'win')
        _emit(m, v.outputs[0], WARM, _base_color_socket(m, b), scale=2.4)
    for m in _mats_by_name(objs, re.compile('window_glass', re.I)):
        if _bsdf(m) is None:
            continue
        _glass(m, 0.55, 0.08)
        v = _driven_value(m, 'ocean_win', root, 'win')
        _emit(m, v.outputs[0], WARM, None, scale=0.9)
    # the porch lamp: glass and bulb come alive with the light
    for m in _mats_by_name(objs, re.compile('lamp_bulb', re.I)):
        if _bsdf(m) is None:
            continue
        v = _driven_value(m, 'ocean_porch', root, 'porch')
        _emit(m, v.outputs[0], (1.0, 0.78, 0.5), None, scale=9.0)
    for m in _mats_by_name(objs, re.compile('lamp_glass', re.I)):
        b = _bsdf(m)
        if b is None:
            continue
        _glass(m, 0.45, 0.12)
        nt = m.node_tree
        v = _driven_value(m, 'ocean_porch', root, 'porch')
        # fresnel rim: (1 - |n . v|)^1.5 * 1.6 + 0.9
        geo = nt.nodes.new('ShaderNodeNewGeometry')
        dp = nt.nodes.new('ShaderNodeVectorMath')
        dp.operation = 'DOT_PRODUCT'
        nt.links.new(geo.outputs['Normal'], dp.inputs[0])
        nt.links.new(geo.outputs['Incoming'], dp.inputs[1])
        ab = nt.nodes.new('ShaderNodeMath')
        ab.operation = 'ABSOLUTE'
        nt.links.new(dp.outputs['Value'], ab.inputs[0])
        om = nt.nodes.new('ShaderNodeMath')
        om.operation = 'SUBTRACT'
        om.inputs[0].default_value = 1.0
        nt.links.new(ab.outputs[0], om.inputs[1])
        pw = nt.nodes.new('ShaderNodeMath')
        pw.operation = 'POWER'
        nt.links.new(om.outputs[0], pw.inputs[0])
        pw.inputs[1].default_value = 1.5
        ma = nt.nodes.new('ShaderNodeMath')
        ma.operation = 'MULTIPLY_ADD'
        nt.links.new(pw.outputs[0], ma.inputs[0])
        ma.inputs[1].default_value = 1.6
        ma.inputs[2].default_value = 0.9
        mm = nt.nodes.new('ShaderNodeMath')
        mm.operation = 'MULTIPLY'
        nt.links.new(ma.outputs[0], mm.inputs[0])
        nt.links.new(v.outputs[0], mm.inputs[1])
        _emit(m, mm.outputs[0], LAMP, None, scale=1.0)
    # the light points (house-local, three axes)
    bpy.context.view_layer.update()
    inv = root.matrix_world.inverted()

    def local3(name, default):
        o = bpy.data.objects.get(name)
        if o is None or o not in objs:
            o = next((x for x in objs if x.name.startswith(name)), None)
        if o is None:
            return default
        p = inv @ o.matrix_world.translation
        return (p.x, p.z, -p.y)
    porch_local = local3('lamp_light_point', (0.7, 2.0, 2.3))
    window_local = local3('window_light_point', (-1.1, 1.9, 1.6))

    def point(name, color, pos3, cutoff, cd, prop):
        ld = bpy.data.lights.new(name, 'POINT')
        ld.color = color
        ld.shadow_soft_size = 0.04
        ld.use_custom_distance = True
        ld.cutoff_distance = cutoff
        ob = bpy.data.objects.new(name, ld)
        col.objects.link(ob)
        ob.parent = root
        ob.location = (pos3[0], -pos3[2], pos3[1])
        fc = ld.driver_add('energy')
        d = fc.driver
        d.type = 'SCRIPTED'
        v = d.variables.new()
        v.name = 'x'
        v.type = 'SINGLE_PROP'
        v.targets[0].id_type = 'OBJECT'
        v.targets[0].id = root
        v.targets[0].data_path = f'["{prop}"]'
        d.expression = f'x*{4 * math.pi * cd:.6f}'           # three candela -> W (4 pi I)
        return ob
    porch_light = point('ocean_porch_light', LAMP, porch_local, 13.0, PORCH_CD, 'porch')
    wl = (window_local[0], window_local[1] - 0.3, window_local[2] + 0.95)   # just outside the glass
    win_light = point('ocean_window_light', WARM, wl, 5.0, WIN_CD, 'win')
    # the porch lamp's halo in the salt air: a soft camera-facing glow, additive (a 1.1 m sprite)
    idx, cor, tris = quad_arrays(1)
    c = (porch_local[0], -porch_local[2], porch_local[1])
    me = _bl.mesh_from_arrays('ocean_porch_halo', [c] * 4, tris, smooth=False)
    _bl.add_point_attr(me, 'center', [c] * 4, 'FLOAT_VECTOR')
    import numpy as np
    _bl.add_point_attr(me, 'corner', np.c_[cor, np.zeros(4)], 'FLOAT_VECTOR')

    def halo_col(nb):
        q = nb.attr('corner', 'GEOMETRY', 'Vector')
        r2 = q[0] * q[0] + q[1] * q[1]
        k = (nb.exp(r2 * -4.0) * 0.9 + nb.exp(r2 * -22.0) * 1.4) * nb.driven('U_porch', root, '["porch"]')
        return tuple(c_ * k for c_ in LAMP)
    me.materials.append(additive_emission('ocean_porch_halo', halo_col))
    halo = bpy.data.objects.new('ocean_porch_halo', me)
    col.objects.link(halo)
    halo.parent = root
    halo.visible_shadow = False
    mod = halo.modifiers.new('billboard', 'NODES')
    mod.node_group = _halo_group()
    return House(group=root, objects=objs, porch_local=porch_local, window_local=window_local, porch_light=porch_light,
                 win_light=win_light, halo=halo)


def _halo_group():
    import bpy
    from ._nodes import NB, new_tree
    from ._billboards import billboard_offset
    name = 'ocean_halo_billboard'
    if name in bpy.data.node_groups:
        return bpy.data.node_groups[name]
    tree, gi, go = new_tree(name, 'GeometryNodeTree', inputs=[('Geometry', 'NodeSocketGeometry')],
                            outputs=[('Geometry', 'NodeSocketGeometry')])
    nb = NB(tree)
    c = nb.attr('center', out='Vector')
    q = nb.attr('corner', out='Vector')
    p = billboard_offset(nb, c, (q[0], q[1]), 0.55, 0.0)        # Sprite scale 1.1 = a 1.1 m square
    setp = nb.node('GeometryNodeSetPosition')
    setp.hide = False
    tree.links.new(gi.outputs['Geometry'], setp.inputs['Geometry'])
    nb.link(p, setp.inputs['Position'])
    tree.links.new(setp.outputs['Geometry'], go.inputs['Geometry'])
    return tree
