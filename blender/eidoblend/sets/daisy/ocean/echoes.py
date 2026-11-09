"""ocean/echoes.py: "faint echoes of the older voices, like distant lights" (port of eidoverse/sets/ocean/echoes.js).

Sixty-some small lights around and beneath her, each in the colour of an older machine voice (Voder tube glow, 1961
CRT white, teletype paper, Speak & Spell VFD cyan, C64 violet-blue, Mac white, DECtalk amber, green phosphor, VOCALOID
teal, Sydney violet). Most hang far out over the sea like boat lanterns, each with a glitter streak on the water; a
few drift near her like fireflies. As the ocean of faces rises they can sink into it (`sink`): the older voices are
part of the inheritance.

    echoes = build_echoes(coast, parent=layout_empty)   -> Echoes: group, control, objects, U, count, lights
    the uniforms are custom properties on echoes.control (t, level, sink); the streaks follow them through drivers

The WebGPU edition's two meshes (one draw each) stay two meshes of 4 vertices per light; their vertex stages (the
drift, the sink, the camera-facing glow, the streak aimed at the camera along the water) are Geometry Nodes reading
the active camera; the colours are additive emission.
"""

from __future__ import annotations

import math

import numpy as np

from .util import rng

ERA = [
    [1.0, 0.70, 0.36], [0.80, 0.87, 1.0], [1.0, 0.91, 0.76], [0.33, 0.95, 0.88], [0.55, 0.55, 1.0],
    [0.95, 0.95, 0.95], [1.0, 0.68, 0.25], [0.43, 1.0, 0.6], [0.22, 0.77, 0.73], [0.82, 0.44, 1.0],
]


def plan_echoes(coast, seed=23):
    """The lights of echoes.js from rng(seed): [{'p': (x, y, z) three design, 's', 'far', 'col', 'phase', 'freq'}]."""
    R = rng(seed)
    lights = []
    for _i in range(46):                                         # far lanterns over the sea
        a = -math.pi * 0.62 + R() * math.pi * 1.1 + math.pi
        d = 25 * math.pow(18, R())                               # 25 .. 450 m
        x, z = math.sin(a) * d, math.cos(a) * d
        if coast.sdist_3(x, z) < 3:
            continue
        lights.append({'p': (x, 0.6 + R() * 2.4 + d * 0.004, z), 's': 0.16 + R() * 0.2, 'far': 1})
    for _i in range(18):                                         # near: around and beneath her
        a, d = R() * math.pi * 2, 2.2 + R() * 9
        x, z = math.sin(a) * d, math.cos(a) * d - 1.5
        g = coast.height_3(x, z)
        y = max(g, 0) + 0.25 + R() * 1.6
        lights.append({'p': (x, y, z), 's': 0.045 + R() * 0.05, 'far': 0})
    for L in lights:
        L['col'] = ERA[int(math.floor(R() * len(ERA)))]
        L['phase'], L['freq'] = R() * 6.283, 0.4 + R() * 1.1
    return lights


class Echoes:
    def __init__(self, **kw):
        self.__dict__.update(kw)

    @property
    def U(self):
        return self.control


def _quad_mesh(name, lights):
    """4 vertices per light, the JS attributes: center (three -> Blender design-local), corner, ecol, prm."""
    from . import _bl
    from ._billboards import quad_arrays
    n = len(lights)
    idx, cor, tris = quad_arrays(n)
    cen = np.array([(L['p'][0], -L['p'][2], L['p'][1]) for L in lights], np.float32)[idx]
    me = _bl.mesh_from_arrays(name, cen, tris, smooth=False)
    _bl.add_point_attr(me, 'center', cen, 'FLOAT_VECTOR')
    _bl.add_point_attr(me, 'corner', np.c_[cor, np.zeros(len(cor))], 'FLOAT_VECTOR')
    _bl.add_point_attr(me, 'ecol', np.array([L['col'] for L in lights], np.float32)[idx], 'FLOAT_VECTOR')
    prm = np.array([(L['s'], L['phase'], L['freq']) for L in lights], np.float32)[idx]
    _bl.add_point_attr(me, 'prm', prm, 'FLOAT_VECTOR')
    _bl.add_point_attr(me, 'kind', np.array([L['far'] for L in lights], np.float32)[idx])
    return me


def _live_center(nb, t, sink):
    """liveCenter: a slow drift + bob, and the sink into the sea on the reveal (three's design axes in, Blender out)."""
    cb = nb.attr('center', out='Vector')
    c = (cb[0], cb[2], -nb.s(cb[1]))                             # three (x, y, z)
    prm = nb.attr('prm', out='Vector')
    kind = nb.attr('kind')
    ph, fr = prm[1], prm[2]
    drift = (nb.sin(t * (fr * 0.23) + ph) * 0.35, nb.sin(t * (fr * 0.6) + ph * 1.7) * 0.12, nb.cos(t * (fr * 0.19) + ph) * 0.35)
    sinkY = sink * (c[1] + 0.6) * nb.smoothstep(0.0, 1.0, sink * 1.4 - kind * 0.2)
    k = kind * 1.5 + 0.3
    live = (c[0] + drift[0] * k, c[1] + drift[1] * k - sinkY, c[2] + drift[2] * k)
    return live, prm, kind


def glow_group():
    import bpy
    from ._nodes import NB, E, new_tree
    from ._billboards import billboard_offset
    name = 'ocean_echo_glows'
    if name in bpy.data.node_groups:
        return bpy.data.node_groups[name]
    tree, gi, go = new_tree(name, 'GeometryNodeTree', inputs=[('Geometry', 'NodeSocketGeometry'),
                            ('Time', 'NodeSocketFloat', 0.0), ('Sink', 'NodeSocketFloat', 0.0)],
                            outputs=[('Geometry', 'NodeSocketGeometry')])
    nb = NB(tree)
    live, prm, _kind = _live_center(nb, E(nb, gi.outputs['Time']), E(nb, gi.outputs['Sink']))
    cor = nb.attr('corner', out='Vector')
    c_bl = (live[0], -nb.s(live[2]), live[1])
    p = billboard_offset(nb, c_bl, (cor[0] * 2.2, cor[1] * 2.2), prm[0], 0.0032)
    setp = nb.node('GeometryNodeSetPosition')
    setp.hide = False
    tree.links.new(gi.outputs['Geometry'], setp.inputs['Geometry'])
    nb.link(p, setp.inputs['Position'])
    tree.links.new(setp.outputs['Geometry'], go.inputs['Geometry'])
    return tree


def streak_group():
    """their glitter streaks on the water: a quad lying on the sea at the light's foot, aimed at the camera."""
    import bpy
    from ._nodes import NB, E, new_tree
    from ._billboards import camera_frame
    name = 'ocean_echo_streaks'
    if name in bpy.data.node_groups:
        return bpy.data.node_groups[name]
    tree, gi, go = new_tree(name, 'GeometryNodeTree', inputs=[('Geometry', 'NodeSocketGeometry'),
                            ('Time', 'NodeSocketFloat', 0.0), ('Sink', 'NodeSocketFloat', 0.0)],
                            outputs=[('Geometry', 'NodeSocketGeometry')])
    nb = NB(tree)
    live, prm, kind = _live_center(nb, E(nb, gi.outputs['Time']), E(nb, gi.outputs['Sink']))
    q = nb.attr('corner', out='Vector')
    loc, _R, _U = camera_frame(nb)
    cam3 = (loc[0], loc[2], -nb.s(loc[1]))                       # the camera in design three axes
    cw = (live[0], 0.04, live[2])                                # the light's foot on the water
    tc = (cam3[0] - cw[0], cam3[1] - cw[1], cam3[2] - cw[2])
    hl = nb.max(nb.sqrt(tc[0] * tc[0] + tc[2] * tc[2]), 1e-6)
    dx, dz = tc[0] / hl, tc[2] / hl
    px, pz = -nb.s(dz), dx
    dist = nb.vlen(tc)
    w = nb.max(prm[0] * 1.4, dist * 0.0022)
    ln = (live[1] + 1.0) * (dist * 0.035 + 1.2) * kind
    along = (q[1] * 0.5 + 0.5) * ln
    x = cw[0] + px * q[0] * w + dx * along
    z = cw[2] + pz * q[0] * w + dz * along
    setp = nb.node('GeometryNodeSetPosition')
    setp.hide = False
    tree.links.new(gi.outputs['Geometry'], setp.inputs['Geometry'])
    nb.link((x, -nb.s(z), cw[1]), setp.inputs['Position'])
    tree.links.new(setp.outputs['Geometry'], go.inputs['Geometry'])
    return tree


def _flick(nb, t):
    prm = nb.attr('prm', 'GEOMETRY', 'Vector')
    ph, fr = prm[1], prm[2]
    return nb.sin(t * (fr * 2.1) + ph) * 0.18 + nb.sin(t * (fr * 5.3) + ph * 3.1) * 0.07 + 0.82


def glow_material(control):
    """the glows: a hot core and a soft halo, flickering, x level (the control's custom properties t / level)."""
    from ._billboards import additive_emission

    def col(nb):
        q = nb.attr('corner', 'GEOMETRY', 'Vector')
        r2 = q[0] * q[0] + q[1] * q[1]
        t, level = nb.driven('U_t', control, '["t"]'), nb.driven('U_level', control, '["level"]', 1.0)
        k = (nb.exp(r2 * -40.0) * 2.2 + nb.exp(r2 * -6.0) * 0.35) * _flick(nb, t) * level
        e = nb.attr('ecol', 'GEOMETRY', 'Vector')
        return tuple(e[i] * k for i in range(3))
    return additive_emission('ocean_echo_glow', col)


def streak_material(control):
    """the streaks: bright at the light's foot, rippling toward the camera, far lanterns only (kind)."""
    from ._billboards import additive_emission

    def col(nb):
        q = nb.attr('corner', 'GEOMETRY', 'Vector')
        prm = nb.attr('prm', 'GEOMETRY', 'Vector')
        kind = nb.attr('kind', 'GEOMETRY')
        t, level = nb.driven('U_t', control, '["t"]'), nb.driven('U_level', control, '["level"]', 1.0)
        v = q[1] * 0.5 + 0.5
        across = nb.exp(q[0] * q[0] * -5.0)
        ripple = nb.sin(v * 38.0 - t * 3.2 + prm[1]) * 0.5 + 0.5
        k = across * nb.pow(1.0 - v, 1.3) * (ripple * 0.8 + 0.2) * 0.55 * _flick(nb, t) * level * kind
        e = nb.attr('ecol', 'GEOMETRY', 'Vector')
        return tuple(e[i] * k for i in range(3))
    return additive_emission('ocean_echo_streak', col)


def build_echoes(coast, seed=23, parent=None, collection=None):
    """buildEchoes(THREE, { coast, seed }) -> Echoes."""
    import bpy
    from . import _bl
    col = collection or bpy.context.scene.collection
    lights = plan_echoes(coast, seed)
    group = _bl.empty('ocean:echoes', parent=parent, collection=col, size=0.5)
    objs = []
    for nm, gfn in (('ocean_echo_streaks', streak_group), ('ocean_echoes', glow_group)):
        me = _quad_mesh(nm, lights)
        ob = bpy.data.objects.new(nm, me)
        col.objects.link(ob)
        ob.parent = group
        ob.visible_shadow = False
        if hasattr(ob, 'visible_volume_scatter'):
            ob.visible_volume_scatter = False
        mod = ob.modifiers.new('echo', 'NODES')
        mod.node_group = gfn()
        objs.append(ob)
    streaks, glows = objs
    for k, v in (('t', 0.0), ('level', 1.0), ('sink', 0.0)):
        glows[k] = v
        streaks[k] = v
    glows.data.materials.append(glow_material(glows))
    streaks.data.materials.append(streak_material(glows))
    for ob in (glows, streaks):
        mod = ob.modifiers['echo']
        _bl.drive_modifier_input(ob, mod, 'Time', glows, 't')
        _bl.drive_modifier_input(ob, mod, 'Sink', glows, 'sink')
    for k in ('t', 'level', 'sink'):
        _bl.drive(streaks, f'["{k}"]', glows, k)
    return Echoes(group=group, control=glows, glows=glows, streaks=streaks, objects=[streaks, glows], count=len(lights),
                  lights=lights)
