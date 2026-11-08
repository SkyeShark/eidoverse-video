"""ocean/daisies.py: her flowers on the rise, a superbloom of daisies (the claudesona's own flower), on the flora
family's daisy (eidoblend.flora create_flora('daisy'): the modelled oxeye clump with its closable rays, real geometry,
wind as Geometry Nodes). This is the set's port of eidoverse/sets/ocean/daisies.js: its options map onto the brush.

    field = build(count=420, width=5.2, depth=4.6, center=(0.25, 0.5), seed=5, height_fn=coast.height_3,
                  face_dir=(0.1, 0.6, 1.0), clear=[{'a': (-0.25, 0), 'b': (0.25, 0), 'w': 1.25}], close=1.0,
                  stem_height=(0.16, 0.28), head_scale=1.2, design_to_world=f, world_to_design=g)
    field.update(t, {'close': 1, 'pulse': 0, 'wind': 0.35}, frame=f)      # keyed through the field's own controls
    bloom = build_example('superbloom')                                   # daisies.js's own example: 14000 on 60 m

daisies.js (design frame, three x / z) -> create_flora (world, Blender x / y):
    count            -> density: count / (the rectangle's area x 12 clumps/m2 x ~2.5 heads per clump)
    width, depth, center -> a stand around the rectangle's centre (through design_to_world), clipped to the rectangle
    heightFn(x, z)   -> height_fn(x, z) (three's design x, z), read through world_to_design
    faceDir / sunDir -> heading (the direction turned into the world); yawSpread -> heading_jitter = yawSpread / 2
    clear [{a, b, w}] -> clip_fn: no plant within w / 2 of a lane
    palette          -> color: [[r, g, b, weight], ...] (sRGB 0..1) becomes flora's mix {(r, g, b): weight}; the default
                        palette (white, cream, Claude orange, gold at .46 / .16 / .28 / .10) is flora's named mix
                        {'white', 'cream', 'orange', 'yellow'} ('white' keeps the modelled art); color= passes any flora mix
    stemHeight [a, b] -> height (a + b) / 2;  headScale -> head_scale x 1.4 (daisies.js heads were ~8.5 cm across at
                        1.2 on 0.22 m stems; flora's head is 5 cm at 1)
    close            -> close (0 open .. 1 shut, keyed through the prototype's close modifier)
    pulse            -> the kick: every ray grows 10 % about its hinge (a 'pulse' modifier before flora's close, as
                        daisies.js's grow = 1 + 0.1 pulse) and glows (1, 0.85, 0.6) x 0.25 pulse (the petals only, on this
                        field's own copy of the flora material); the custom property 'pulse' on field.group, keyable
    wind             -> set_wind(strength);  t -> flora's 'Time Offset' (the field sways on the scene's clock)
    parts {stems, discs, petals} -> one prototype in flora (stem, disc and rays are one plant mesh): parts['prototype']
"""

from __future__ import annotations

import math

DEFAULT_COLOR = {'white': 0.46, 'cream': 0.16, 'orange': 0.28, 'yellow': 0.10}
HEADS_PER_CLUMP = 2.5
CLUMPS_PER_M2 = 12.0
HEAD_SCALE_K = 1.4
PULSE_GROW, PULSE_GLOW, PULSE_COLOR = 0.1, 0.25, (1.0, 0.85, 0.6)

# daisies.js's header example: a superbloom 60 m square with a path cleared across it (its heightFn and sunDir are the
# caller's; build_example gives it a gentle meadow swell and the default sun)
EXAMPLES = {
    'superbloom': {'count': 14000, 'width': 60.0, 'depth': 60.0, 'seed': 7,
                   'clear': [{'a': (-30.0, 0.0), 'b': (30.0, 0.0), 'w': 2.2}]},
}


def meadow_height(x, z):
    """build_example's ground for the superbloom (design x, z): a gentle swell of about +-0.35 m."""
    import numpy as np
    x, z = np.asarray(x, np.float64), np.asarray(z, np.float64)
    h = 0.25 * np.sin(x * 0.09 + 0.4) * np.cos(z * 0.07) + 0.1 * np.sin(z * 0.21)
    return float(h) if h.ndim == 0 else h


class Daisies:
    def __init__(self, field, opts):
        self.field, self.opts = field, opts
        self.group = field.object
        self.parts = {'field': field, 'prototype': field.prototype, 'materials': list(field.materials),
                      'count': field.count, 'heads': opts.get('heads'),
                      'uniforms': {'close': opts['close'], 'wind': opts['wind'], 'pulse': opts.get('pulse', 0.0)}}

    def set_pulse(self, v, frame=None):
        """The kick's 0..1: rays grow 10 % and glow warm (keyed at frame when given)."""
        ob = self.group
        ob['pulse'] = float(v)
        ob.update_tag()
        if self.field.prototype is not None:
            self.field.prototype.update_tag()
        if frame is not None:
            ob.keyframe_insert('["pulse"]', frame=frame)
        self.parts['uniforms']['pulse'] = float(v)

    def update(self, t=None, state=None, frame=None):
        """daisies.js update(t, { close, pulse, wind }): close, pulse and wind go to the field's controls (keyed at
        frame); t sets flora's Time Offset so the sway at `frame` is the sway at film time t."""
        import bpy
        state = state or {}
        if state.get('close') is not None:
            self.field.set_close(state['close'], frame=frame)
        if state.get('pulse') is not None:
            self.set_pulse(state['pulse'], frame=frame)
        if state.get('wind') is not None:
            self.field.set_wind(strength=state['wind'], frame=frame)
        if t is not None and getattr(self.field, 'motion', True):
            sc = bpy.context.scene
            f = sc.frame_current if frame is None else frame
            off = float(t) - f * sc.render.fps_base / sc.render.fps
            self.field._set_input(self.field.modifier, 'Time Offset', off)
            self.group.update_tag()

    def remove(self):
        self.field.remove()

    dispose = remove


def _pulse_group():
    """On the prototype, before flora's close: each ray vertex (close_angle > 0) moves away from its petal's hinge by
    Pulse x 10 % (daisies.js: the part of the petal beyond the hinge grows by 1 + 0.1 pulse), and the rays are
    tagged (point attribute 'ocean_ray') for the material's glow."""
    import bpy
    from ._nodes import NB, E, new_tree
    name = 'ocean_daisy_pulse'
    if name in bpy.data.node_groups:
        return bpy.data.node_groups[name]
    tree, gi, go = new_tree(name, 'GeometryNodeTree', inputs=[('Geometry', 'NodeSocketGeometry'),
                                                                ('Pulse', 'NodeSocketFloat', 0.0)],
                            outputs=[('Geometry', 'NodeSocketGeometry')])
    nb = NB(tree)
    ray = nb.gt(nb.attr('close_angle'), 0.0)
    hinge = nb.attr('close_hinge_v', out='Vector')
    P = nb.separate(nb.node('GeometryNodeInputPosition').outputs[0])
    grow = 1.0 + E(nb, gi.outputs['Pulse']) * PULSE_GROW * ray
    new = tuple(hinge[i] + (P[i] - hinge[i]) * grow for i in range(3))
    setp = nb.node('GeometryNodeSetPosition')
    setp.hide = False
    tree.links.new(gi.outputs['Geometry'], setp.inputs['Geometry'])
    nb.link(new, setp.inputs['Position'])
    st = nb.node('GeometryNodeStoreNamedAttribute', data_type='FLOAT', domain='POINT')
    st.hide = False
    st.inputs['Name'].default_value = 'ocean_ray'
    tree.links.new(setp.outputs['Geometry'], st.inputs['Geometry'])
    nb.link(ray, st.inputs['Value'])
    tree.links.new(st.outputs['Geometry'], go.inputs['Geometry'])
    return tree


def _pulse_materials(field):
    """This field's own copies of the flora materials, each Principled BSDF emitting PULSE_COLOR x 0.25 x pulse on the
    rays only ('ocean_ray'), the strength read from field.object['pulse'] by a driver."""
    from ._nodes import NB
    me = field.prototype.data
    out = []
    for i, m in enumerate(list(me.materials)):
        if m is None:
            continue
        m2 = m.copy()
        m2.name = f'{field.object.name}_{m.name}_pulse'
        nt = m2.node_tree
        bsdf = next((n for n in nt.nodes if n.type == 'BSDF_PRINCIPLED'), None)
        if bsdf is None:
            bpy_remove(m2)
            continue
        nb = NB(nt, x0=bsdf.location.x - 900, y0=bsdf.location.y - 700, rows=8)
        ray = nb.attr('ocean_ray', 'GEOMETRY')
        k = nb.driven('ocean_pulse', field.object, '["pulse"]', 0.0)
        nb.link(ray * k * PULSE_GLOW, bsdf.inputs['Emission Strength'])
        bsdf.inputs['Emission Color'].default_value = (*PULSE_COLOR, 1.0)
        me.materials[i] = m2
        out.append(m2)
    return out


def bpy_remove(mat):
    import bpy
    bpy.data.materials.remove(mat)


def _add_pulse(field):
    proto = field.prototype
    if proto is None:
        return []
    from . import _bl
    mod = proto.modifiers.new('pulse', 'NODES')
    mod.node_group = _pulse_group()
    idx = list(proto.modifiers).index(mod)
    if idx != 0:
        proto.modifiers.move(idx, 0)                                # before flora's close (which drops the records)
    field.object['pulse'] = 0.0
    _bl.drive_modifier_input(proto, mod, 'Pulse', field.object, 'pulse')
    return _pulse_materials(field)


def build(count=12000, width=50.0, depth=50.0, center=(0.0, 0.0), seed=7, height_fn=None, sun_dir=(0.3, 0.35, -0.9),
          face_dir=None, clear=(), palette=None, stem_height=(0.2, 0.34), head_scale=1.5, yaw_spread=1.3, close=0.0,
          wind=1.0, pulse=0.0, color=None, design_to_world=None, world_to_design=None, collection=None,
          name='ocean_daisies', motion=True):
    """build(THREE, opts) -> Daisies. design_to_world(x3, z3, y3=0) -> world (x, y, z); world_to_design(x, y) ->
    (x3, z3) (the identity when both are None: the design frame is the world, three z = -Blender y)."""
    from eidoblend.flora import create_flora
    d2w = design_to_world or (lambda x3, z3, y3=0.0: (x3, -z3, y3))
    w2d = world_to_design or (lambda x, y: (x, -y))
    cx, cz = center
    lanes = list(clear)

    def in_clear(x, z):
        for c in lanes:
            (ax, az), (bx, bz) = c['a'], c['b']
            dx, dz = bx - ax, bz - az
            L2 = dx * dx + dz * dz
            tt = max(0.0, min(1.0, ((x - ax) * dx + (z - az) * dz) / L2)) if L2 > 0 else 0.0
            px, pz = ax + dx * tt - x, az + dz * tt - z
            if px * px + pz * pz < (c['w'] / 2) ** 2:
                return True
        return False

    def clip_fn(x, y):
        x3, z3 = w2d(x, y)
        x3, z3 = float(x3), float(z3)
        return abs(x3 - cx) > width / 2 or abs(z3 - cz) > depth / 2 or in_clear(x3, z3)

    def ground(x, y):
        x3, z3 = w2d(x, y)
        return height_fn(x3, z3) + d2w(0.0, 0.0, 0.0)[2]
    hf = ground if height_fn is not None else None              # None: flat, at create_flora's z
    fd = face_dir or sun_dir
    o = d2w(0.0, 0.0, 0.0)
    e = d2w(fd[0], fd[2], fd[1])
    heading = (e[0] - o[0], e[1] - o[1], e[2] - o[2])
    c_w = d2w(cx, cz)
    if color is None and palette is not None:                   # daisies.js palette [[r, g, b, weight]] (sRGB)
        color = {tuple(float(v) for v in p[:3]): float(p[3]) for p in palette}
    area = width * depth
    density = count / (area * CLUMPS_PER_M2 * HEADS_PER_CLUMP)
    field = create_flora('daisy', size=math.hypot(width, depth) + 0.2, center=(c_w[0], c_w[1]), z=c_w[2], seed=seed,
                         density=density, height_fn=hf, clip_fn=clip_fn, heading=heading,
                         heading_jitter=yaw_spread / 2, height=(stem_height[0] + stem_height[1]) / 2,
                         head_scale=head_scale * HEAD_SCALE_K, color=color or DEFAULT_COLOR, close=close, wind=wind,
                         collection=collection, name=name, motion=motion)
    heads = field.count * len(field.plan.get('heads') or ())          # plants x the heads of the one plant geometry
    _add_pulse(field)
    D = Daisies(field, {'count': count, 'close': close, 'wind': wind, 'pulse': pulse, 'density': density,
                        'heading': heading, 'heads': heads, 'color': color or DEFAULT_COLOR})
    if pulse:
        D.set_pulse(pulse)
    return D


def build_example(name='superbloom', height_fn=meadow_height, **kw):
    """One of daisies.js's examples (EXAMPLES), with any option overridden by keyword."""
    opts = dict(EXAMPLES[name])
    opts.update(kw)
    return build(height_fn=height_fn, **opts)
