"""DAISY finale prop: "a bicycle built for two" (props/tandem.js, ported to Blender 5.2 EEVEE).

An 1890s safety tandem (the hero asset, modelled and baked in Blender by the pack's build_tandem.py: lugged frame with
cast lugs, tangent-laced wheels, daisy-spider chainrings, rat-trap pedals, 1" block chain, sprung saddles, spoon brake
and bell; layered PBR baked to atlases), a rider rig for a VRM (the claudesona, claude_suit.vrm at scale 0.87) and the
Utah-teapot stoker.

    import sys; sys.path.insert(0, '<repo>/blender')
    from eidoblend.props import tandem as TD

    bike = TD.build()                                      # -> Tandem: group, parts, layout, extras, update, ...
    st = bike.update(t, {'speed': 2.2})                    # keyed at the frame of t; returns the state
    bike.group.location.x = st['distance']                 # the film owns the root: travel along +X
    from eidoblend.characters import load_vrm
    me = load_vrm('claude_suit')
    TD.pose_rider(me, st['crank_angle'], bike=bike, t=t)   # IK on the saddle, hands on the grips, feet on the pedals
    pot = TD.build_teapot_rider().mount(bike)              # the stoker on the rear saddle
    pot.update(t, st['crank_angle'])

Units: metres. The bike frame: +X = the direction of travel, Z up, -Y = the bike's right (drive) side (three's +Z):
the camera side in a side shot. Wheels rest on z = 0; the origin is on the ground between the hubs.

update(t, state): state['speed'] (m/s, a number or fn(t)) or state['distance'] (m); optional 'steer' (rad about the
steering axis), 'crank_angle' (overrides the geared one), 'crank_phase', 'shutter' (s; the spoke smear, default half a
frame). Deterministic in t. Returns {t, distance, wheel_angle, crank_angle, speed}. crank_angle 0 = right pedal at 12
o'clock, increasing as the bike rolls forward (fixed wheel: both cranks share it through the timing chain, and it is
locked to the rear wheel). Every value is keyed at the frame of t (wheels, cranks, pedals, steering, the chains'
phases and the spoke sweep), LINEAR, so a saved .blend plays on its own.

Blender translations:
  the chains   each is a Geometry Nodes object: the GLB's one-pitch link instanced N times round its belt path (two
               tangent runs, two arcs) from one keyed phase, the same walk the engine's vertex stage did.
  the spokes   the engine smeared them through the shutter (it had no motion blur): trailing vertices swing back by the
               angle the wheel turns while the shutter is open, and their coverage falls to wire width / swept arc. Here
               a Geometry Nodes rotation and the spoke material do the same from the keyed 'sweep'; the root property
               'spoke_smear' (1 / 0) switches it, and build() sets it off when the scene renders EEVEE motion blur,
               which blurs the keyed wheels for real (smear and motion blur together would blur twice).
  pose_rider   writes the VRM's normalized humanoid rotations (characters.VRMHandle.write_pose) and keys them; the
               engine's spring pre-roll is the characters family's bake_springs, run over the film after posing.
"""

from __future__ import annotations

import json
import math
import os

import numpy as np
import bpy
from mathutils import Euler, Matrix, Quaternion, Vector

from .. import common
from .voice_machines import voder as K

DEG = math.pi / 180.0
TAU = math.pi * 2.0
TANDEM_GLB = common.asset_path('models', 'tandem_1896', 'tandem.glb')
v3 = K.v3


def q3(q):
    """a three-frame mathutils Quaternion (w, x, y, z) -> the same rotation in Blender's axes"""
    return Quaternion((q[0], q[1], -q[3], q[2]))


def to_three(v):
    return Vector((v[0], v[2], -v[1]))


def euler_three(ax, ay, az):
    """three's Euler (ax, ay, az) 'XYZ' (R = Rx Ry Rz) in Blender axes: (rotation_mode, values). The axes map
    x -> x, y -> z, z -> -y, so R = Rx(ax) Rz(ay) Ry(-az): Blender's 'YZX' order."""
    return 'YZX', (ax, -az, ay)


# ===================================================================================================================
# THE BIKE
# ===================================================================================================================
def integrate(fn, t):
    """tandem.js integrate: Simpson's rule over [0, t], 2 ceil(30 t) intervals (at least 16)."""
    if t <= 0:
        return 0.0
    n = max(16, math.ceil(t * 30) * 2)
    h = t / n
    s = fn(0.0) + fn(t)
    for i in range(1, n):
        s += fn(i * h) * (4 if i % 2 else 2)
    return s * h / 3


class Belt:
    """One chain: the belt path (two tangent runs and two arcs round sprockets A and B) and its phase.
    point(s) -> (x, y) in the bike's side plane (three's x, y); phase(crank_angle) as tandem.js setPhase."""

    def __init__(self, belt, z, ident):
        self.b, self.z, self.id = belt, z, ident
        A, rA, B, rB = belt['A'], belt['rA'], belt['B'], belt['rB']
        dx, dy = B[0] - A[0], B[1] - A[1]
        D = math.hypot(dx, dy)
        self.u = (dx / D, dy / D)
        self.n = (-self.u[1], self.u[0])
        phi = math.asin((rA - rB) / D)
        self.Ls = D * math.cos(phi)
        self.arcB = rB * (math.pi - 2 * phi)
        self.angUp = math.pi / 2 - phi
        self.angLow = -self.angUp
        mUp, mLow = self._dir(self.angUp), self._dir(self.angLow)
        self.TAup = (A[0] + rA * mUp[0], A[1] + rA * mUp[1])
        TBup = (B[0] + rB * mUp[0], B[1] + rB * mUp[1])
        self.TBlow = (B[0] + rB * mLow[0], B[1] + rB * mLow[1])
        TAlow = (A[0] + rA * mLow[0], A[1] + rA * mLow[1])
        self.dUp = ((TBup[0] - self.TAup[0]) / self.Ls, (TBup[1] - self.TAup[1]) / self.Ls)
        self.dLow = ((TAlow[0] - self.TBlow[0]) / self.Ls, (TAlow[1] - self.TBlow[1]) / self.Ls)
        self.L, self.N, self.pp = belt['L'], belt['N'], belt['pp']

    def _dir(self, ang):
        u, n = self.u, self.n
        return (u[0] * math.cos(ang) + n[0] * math.sin(ang), u[1] * math.cos(ang) + n[1] * math.sin(ang))

    def point(self, s):
        b, Ls, arcB = self.b, self.Ls, self.arcB
        if s < Ls:
            return (self.TAup[0] + self.dUp[0] * s, self.TAup[1] + self.dUp[1] * s)
        if s < Ls + arcB:
            d = self._dir(self.angUp - (s - Ls) / b['rB'])
            return (b['B'][0] + d[0] * b['rB'], b['B'][1] + d[1] * b['rB'])
        if s < 2 * Ls + arcB:
            return (self.TBlow[0] + self.dLow[0] * (s - Ls - arcB), self.TBlow[1] + self.dLow[1] * (s - Ls - arcB))
        d = self._dir(self.angLow - (s - 2 * Ls - arcB) / b['rA'])
        return (b['A'][0] + d[0] * b['rA'], b['A'][1] + d[1] * b['rA'])

    def phase_unwrapped(self, crank_angle):
        return self.b['sOff'] + crank_angle * self.b['teethB'] * self.pp / TAU

    def phase(self, crank_angle):
        """the walked arc length of link 0 for this crank angle, wrapped to the belt (tandem.js uPhase)"""
        s = self.phase_unwrapped(crank_angle)
        return ((s % self.L) + self.L) % self.L

    def set_phase(self, crank_angle, frame=None, key=True, ctx=None):
        """tandem.js setPhase(crankAngle): walk the chain to this crank angle. The root property u_phase holds it
        UNWRAPPED (the Geometry Nodes wrap it), so keys interpolate across the wrap; keyed (LINEAR) at `frame` (or
        the current frame), through the bike's ctx when it has one. update() does this for both chains."""
        g = self.owner
        g[self.u_phase] = self.phase_unwrapped(crank_angle)
        if key:
            bike = self.machine
            f = (bike.scene if bike else bpy.context.scene).frame_current if frame is None else frame
            if bike is not None:
                bike.keyer.key(g, f'["{self.u_phase}"]', frame=f, ctx=ctx or bike.ctx, interpolation=bike.interpolation)
            else:
                g.keyframe_insert(f'["{self.u_phase}"]', frame=f)

    machine = None          # the Tandem (set by build)
    owner = None            # the bike's root Empty (set by build)
    mesh = None             # the chain's Geometry Nodes object
    u_phase = ''            # the root property the chain's nodes read

    def node_point(self, nb, s):
        """point(s) as shader / geometry nodes (floats in, the x and y sockets out)."""
        b, Ls, arcB = self.b, self.Ls, self.arcB

        def arc(center, r, ang):
            c, sn = nb.math('COSINE', ang), nb.sin(ang)
            return (nb.add(center[0], nb.mul(nb.add(nb.mul(c, self.u[0]), nb.mul(sn, self.n[0])), r)),
                    nb.add(center[1], nb.mul(nb.add(nb.mul(c, self.u[1]), nb.mul(sn, self.n[1])), r)))
        p1 = (nb.madd(s, self.dUp[0], self.TAup[0]), nb.madd(s, self.dUp[1], self.TAup[1]))
        p2 = arc(b['B'], b['rB'], nb.sub(self.angUp, nb.div(nb.sub(s, Ls), b['rB'])))
        s3 = nb.sub(s, Ls + arcB)
        p3 = (nb.madd(s3, self.dLow[0], self.TBlow[0]), nb.madd(s3, self.dLow[1], self.TBlow[1]))
        p4 = arc(b['A'], b['rA'], nb.sub(self.angLow, nb.div(nb.sub(s, 2 * Ls + arcB), b['rA'])))
        c1 = nb.math('LESS_THAN', s, Ls)
        c2 = nb.math('LESS_THAN', s, Ls + arcB)
        c3 = nb.math('LESS_THAN', s, 2 * Ls + arcB)
        return tuple(nb.select(c1, p1[k], nb.select(c2, p2[k], nb.select(c3, p3[k], p4[k]))) for k in range(2))


def _new_gn(name):
    ng = bpy.data.node_groups.new(name, 'GeometryNodeTree')
    ng.interface.new_socket('Geometry', in_out='INPUT', socket_type='NodeSocketGeometry')
    ng.interface.new_socket('Geometry', in_out='OUTPUT', socket_type='NodeSocketGeometry')
    nb = K.NB(ng)
    gi, go = nb.new('NodeGroupInput'), nb.new('NodeGroupOutput')
    return ng, nb, gi, go


def _chain_group(name, belt, link, root, prop):
    """The walked chain: N instances of the link, link i at arc length i pp + phase along the belt, turned to the
    chord to the next pitch (tandem.js beltChain). Built in the bike frame: three (x, y, z) -> Blender (x, -z, y), the
    instance turned about Blender +Y by -atan2(t.y, t.x)."""
    ng, nb, gi, go = _new_gn(name)
    idx = nb.new('GeometryNodeInputIndex').outputs['Index']
    phase = nb.driven(root, prop, belt.b['sOff'])
    s0 = nb.mod(nb.madd(idx, belt.pp, phase), belt.L)
    s1 = nb.mod(nb.add(s0, belt.pp), belt.L)
    x0, y0 = belt.node_point(nb, s0)
    x1, y1 = belt.node_point(nb, s1)
    theta = nb.math('ARCTAN2', nb.sub(y1, y0), nb.sub(x1, x0))
    pts = nb.new('GeometryNodePoints')
    pts.inputs['Count'].default_value = int(belt.N)
    nb.put(pts.inputs['Position'], nb.comb(x0, -belt.z, y0))
    oi = nb.new('GeometryNodeObjectInfo', transform_space='ORIGINAL')
    oi.inputs['Object'].default_value = link
    rot = nb.new('FunctionNodeEulerToRotation')
    nb.put(rot.inputs['Euler'], nb.comb(0.0, nb.mul(theta, -1.0), 0.0))
    iop = nb.new('GeometryNodeInstanceOnPoints')
    ng.links.new(pts.outputs['Points'], iop.inputs['Points'])
    ng.links.new(oi.outputs['Geometry'], iop.inputs['Instance'])
    ng.links.new(rot.outputs['Rotation'], iop.inputs['Rotation'])
    ng.links.new(iop.outputs['Instances'], go.inputs['Geometry'])
    return ng


def _spoke_group(name, root):
    """The spoke smear's vertex half: trailing vertices (attribute _TRAIL) swing back about the axle (three's local Z,
    Blender's -Y) by trail x sweep x spoke_smear."""
    ng, nb, gi, go = _new_gn(name)
    sweep = nb.mul(nb.driven(root, 'sweep', 0.0), nb.driven(root, 'spoke_smear', 1.0))
    trail = nb.new('GeometryNodeInputNamedAttribute', data_type='FLOAT')
    trail.inputs['Name'].default_value = '_TRAIL'
    tr = trail.outputs['Attribute']
    tsel = nb.select(nb.step(0.0, sweep), tr, nb.sub(1.0, tr))
    rot = nb.new('ShaderNodeVectorRotate', rotation_type='AXIS_ANGLE')
    nb.put(rot.inputs['Vector'], nb.new('GeometryNodeInputPosition').outputs['Position'])
    rot.inputs['Axis'].default_value = (0.0, -1.0, 0.0)
    nb.put(rot.inputs['Angle'], nb.mul(tsel, sweep))
    sp = nb.new('GeometryNodeSetPosition')
    ng.links.new(gi.outputs['Geometry'], sp.inputs['Geometry'])
    ng.links.new(rot.outputs['Vector'], sp.inputs['Position'])
    ng.links.new(sp.outputs['Geometry'], go.inputs['Geometry'])
    return ng


def _base_color_image(mat):
    if mat is None or mat.node_tree is None:
        return None
    for n in mat.node_tree.nodes:
        if n.type == 'BSDF_PRINCIPLED' and n.inputs['Base Color'].links:
            src = n.inputs['Base Color'].links[0].from_node
            seen = 0
            while src is not None and src.type != 'TEX_IMAGE' and seen < 8:
                ins = [i for i in src.inputs if i.links]
                src = ins[0].links[0].from_node if ins else None
                seen += 1
            if src is not None and src.type == 'TEX_IMAGE':
                return src.image
    return None


def _spoke_material(name, base, root):
    """tandem.js spokeMaterial: bright nickel wire at rest; smeared, a soft haze that shades like the wheel disc
    (the normal leans to the axle on the wire's own side), its coverage wire width / swept arc."""
    m = K.new_material(name)
    t = m.node_tree
    t.nodes.clear()
    nb = K.NB(t)
    b = K.principled(nb)
    img = _base_color_image(base)
    if img is not None:
        nb.put(b.inputs['Base Color'], nb.tex(img, nb.uv('UVMap')).outputs['Color'])
    else:
        nb.put(b.inputs['Base Color'], (0.8, 0.8, 0.8))
    sweep = nb.mul(nb.driven(root, 'sweep', 0.0), nb.driven(root, 'spoke_smear', 1.0))
    asw = nb.abs(sweep)
    smear = nb.smoothstep(0.01, 0.08, asw)
    N = nb.geometry('Normal')
    vt = nb.new('ShaderNodeVectorTransform', vector_type='NORMAL', convert_from='OBJECT', convert_to='WORLD')
    vt.inputs[0].default_value = (0.0, -1.0, 0.0)             # three's local +Z (the axle), Blender's -Y
    axle0 = nb.vmath('NORMALIZE', vt.outputs[0])
    side = nb.sub(nb.mul(nb.step(0.0, nb.vdot(N, axle0)), 2.0), 1.0)
    axle = nb.vscale(axle0, side)
    nb.put(b.inputs['Normal'], nb.vmath('NORMALIZE', nb.vmix(N, axle, smear)))
    nb.put(b.inputs['Roughness'], nb.mix(0.2, 0.62, smear))
    nb.put(b.inputs['Metallic'], nb.mix(1.0, 0.45, smear))
    px, py, pz = nb.sep(nb.texcoord('Object'))
    rr = nb.mx(nb.vmath('LENGTH', nb.comb(px, pz, 0.0)), 0.02)
    nb.put(b.inputs['Alpha'], nb.div(0.0021, nb.add(0.0021, nb.mul(rr, asw))))
    m.surface_render_method = 'BLENDED'
    m.use_backface_culling = False
    m['eido_role'] = name
    return m


PART_NODES = {
    'steering': 'steer', 'front_wheel': 'wheel_front', 'rear_wheel': 'wheel_rear',
    'front_crank': 'crank_front', 'rear_crank': 'crank_rear',
    'front_pedal_r': 'pedal_front_R', 'front_pedal_l': 'pedal_front_L',
    'rear_pedal_r': 'pedal_rear_R', 'rear_pedal_l': 'pedal_rear_L',
    'front_seat': 'seat_front', 'rear_seat': 'seat_rear',
    'front_grip_l': 'grip_front_L', 'front_grip_r': 'grip_front_R',
    'rear_grip_l': 'grip_rear_L', 'rear_grip_r': 'grip_rear_R',
}


class Tandem(K.Machine):
    """tandem.build()'s result: group, root (the GLB's 'tandem' node: the bike frame), parts, layout, extras, state,
    chains {timing, drive} (Belt), update(t, state), set_pedal_pitch(pedal, crank_angle, pitch), dispose()."""
    name = 'tandem'

    def _update(self, t, st):
        L = self.layout
        sp = st.get('speed')
        if isinstance(st.get('distance'), (int, float)):
            dist = float(st['distance'])
        elif callable(sp):
            dist = integrate(sp, t)
        else:
            dist = float(sp or 0.0) * t
        speed_now = sp(t) if callable(sp) else float(sp or 0.0)
        wheel = dist / L['R']
        ca = st.get('crank_angle')
        crank = (float(ca) if ca is not None else wheel * self.gear) + float(st.get('crank_phase') or 0.0)
        P = self.parts
        for w in (P['rear_wheel'], P['front_wheel']):
            K.set_turn(w, 'z', -wheel)
            self.touch(w, 'rotation_euler')
        for c in (P['front_crank'], P['rear_crank']):
            K.set_turn(c, 'z', -crank)
            self.touch(c, 'rotation_euler')
        for p in (P['front_pedal_r'], P['front_pedal_l'], P['rear_pedal_r'], P['rear_pedal_l']):
            K.set_turn(p, 'z', crank)                     # pedals hang level unless a sole pitches them
            self.touch(p, 'rotation_euler')
        for key, belt in self.chains.items():
            self.group[f'chain_{key}'] = belt.phase_unwrapped(crank)
            self.touch(self.group, f'["chain_{key}"]')
        fps = self.scene.render.fps / self.scene.render.fps_base
        shutter = st.get('shutter')
        shutter = 0.5 / fps if shutter is None else float(shutter)
        self.group['sweep'] = max(-0.7, min(0.7, (speed_now / L['R']) * shutter))
        self.touch(self.group, '["sweep"]')
        steer = P['steering']
        steer.rotation_mode = 'QUATERNION'
        steer.rotation_quaternion = Quaternion(self._steer_axis, float(st.get('steer') or 0.0))
        self.touch(steer, 'rotation_quaternion')
        self.state = {'t': t, 'distance': dist, 'wheel_angle': wheel, 'crank_angle': crank, 'speed': speed_now}
        return self.state

    def dispose(self):
        """tandem.js dispose(): the bike's own objects, meshes, materials, maps, node groups and keys go; a rider or a
        teapot mounted on it stays in the scene where it is (unparented, its world transform kept)."""
        own = getattr(self, '_own', set())
        for o in list(self.group.children_recursive):
            if o.as_pointer() not in own and o.parent is not None and o.parent.as_pointer() in own:
                mw = o.matrix_world.copy()
                o.parent = None
                o.matrix_world = mw
        for k in [k for k, v in _RIGS.items() if v['bike'] is self]:      # its riders' rigs (a new bike re-seats them)
            del _RIGS[k]
        super().dispose()

    def set_pedal_pitch(self, pedal, crank_angle, pitch, t=None, frame=None, ctx=None, key=True):
        """tandem.js setPedalPitch: the pedal pitched by a sole (its rotation = crank_angle - pitch), keyed at the
        frame of t / frame (or the current frame)."""
        K.set_turn(pedal, 'z', crank_angle - pitch)
        if key:
            ctx = ctx or self.ctx
            f = frame if frame is not None else (self.frame_at(t, ctx) if t is not None else self.scene.frame_current)
            self.keyer.key(pedal, 'rotation_euler', frame=f, ctx=ctx, interpolation=self.interpolation)



def build(glb=None, name='tandem_1896', collection=None, scene=None, location=(0.0, 0.0, 0.0), spoke_smear=None,
          ctx=None):
    """tandem.js build(THREE, opts): opts.glb, another GLB as a path or as its bytes (the engine's Uint8Array /
    ArrayBuffer, e.g. ASSETS.tandem); without it the pack's tandem_1896/tandem.glb. spoke_smear: True / False, or
    None = on unless the scene renders EEVEE motion blur (the root property 'spoke_smear' switches it any time).
    ctx: a scene's ctx (its scene, and the default route of every key update / pose_rider make). Returns a Tandem."""
    scene = scene or (ctx.scene if ctx is not None else bpy.context.scene)
    tmp = None
    if isinstance(glb, (bytes, bytearray, memoryview)):
        import tempfile
        fd, tmp = tempfile.mkstemp(suffix='.glb', prefix='tandem_')
        with os.fdopen(fd, 'wb') as fh:
            fh.write(bytes(glb))
        path = tmp
    else:
        path = glb or TANDEM_GLB
    try:
        group, nodes, col = K.import_glb(path, name, collection, scene)
    finally:
        if tmp is not None:
            for im in bpy.data.images:            # the GLB's maps live in the blend, not in the temp file
                if im.filepath and os.path.normcase(os.path.abspath(bpy.path.abspath(im.filepath))).startswith(
                        os.path.normcase(os.path.dirname(tmp))) and not im.packed_file:
                    im.pack()
            os.remove(tmp)
    if tmp is not None:
        group['eido_src_asset'] = 'bytes'
    group.location = location
    bike = Tandem(group, col, scene, ctx=ctx)
    root = nodes.get('tandem') or group
    extras = json.loads(root.get('daisy_tandem') or next(
        (o['daisy_tandem'] for o in nodes.values() if 'daisy_tandem' in o), 'null'))
    if extras is None:
        raise RuntimeError('tandem.glb: no daisy_tandem extras')
    L = extras['layout']
    bike.root, bike.extras, bike.layout = root, extras, L
    bike.gear = L['sprocketTeeth'] / L['driveTeeth']
    parts = {}
    for k, nm in PART_NODES.items():
        o = nodes.get(nm)
        if o is None:
            raise KeyError(f'tandem.glb: missing node {nm}')
        parts[k] = o
    for o in nodes.values():
        if o.type == 'MESH':
            o.visible_shadow = True
    # seat frames: a rider parented here faces the direction of travel (+X): three's rotation (0, pi/2, 0)
    for k in ('front_seat', 'rear_seat'):
        parts[k].rotation_mode = 'QUATERNION'
        parts[k].rotation_quaternion = Quaternion((0.0, 0.0, 1.0), math.pi / 2)
    # grip frames: local +Z (three) along the handle, outboard; +Y up
    for k, key in (('front_grip_l', 'front_L'), ('front_grip_r', 'front_R'), ('rear_grip_l', 'rear_L'),
                   ('rear_grip_r', 'rear_R')):
        g = extras['grips'][key]
        z = Vector(g['axis']).normalized()
        y = (Vector((0, 1, 0)) - z * z.y).normalized()
        x = y.cross(z)
        q = Matrix((x, y, z)).transposed().to_quaternion()
        parts[k].rotation_mode = 'QUATERNION'
        parts[k].rotation_quaternion = q3(q)
    for k in ('front_wheel', 'rear_wheel', 'front_crank', 'rear_crank', 'front_pedal_r', 'front_pedal_l',
              'rear_pedal_r', 'rear_pedal_l'):
        K.remember_rest(parts[k])
    ax = Vector((L['axis'][0], L['axis'][1], 0.0)).normalized()
    bike._steer_axis = v3(ax.x, ax.y, ax.z)

    # spokes: smeared through the shutter (switchable; see the module docstring)
    if spoke_smear is None:
        spoke_smear = not scene.render.use_motion_blur
    K.Uniform(group, 'spoke_smear', 1.0 if spoke_smear else 0.0, description='1: smear the spokes through the shutter')
    K.Uniform(group, 'sweep', 0.0, lo=-0.7, hi=0.7, description='the wheels turn this much (rad) while the shutter is open')
    spoke_gn = _spoke_group(f'{name}_spoke_smear', group)
    bike.made['node_groups'].append(spoke_gn)
    spoke_mats, replaced = {}, {}
    for w in (parts['front_wheel'], parts['rear_wheel']):
        for o in w.children_recursive:
            if o.type == 'MESH' and '_TRAIL' in o.data.attributes:
                base = o.material_slots[0].material if o.material_slots else None
                key = base.name if base else ''
                if key not in spoke_mats:
                    spoke_mats[key] = _spoke_material(f'{name}_spokes', base, group)
                    bike.made['materials'].append(spoke_mats[key])
                for s in o.material_slots:
                    if s.material is not None and s.material is not spoke_mats[key]:
                        replaced[s.material.as_pointer()] = s.material
                    s.link = 'DATA'
                    s.material = spoke_mats[key]
                mod = o.modifiers.new('spoke_smear', 'NODES')
                mod.node_group = spoke_gn
    for m in replaced.values():                   # the importer's spoke material, now on nothing: it goes, and the maps
        if m.users == 0:                          # only it read (the spoke material keeps the base colour)
            imgs = {n.image for n in m.node_tree.nodes if getattr(n, 'image', None)} if m.node_tree else set()
            bpy.data.materials.remove(m)
            for im in imgs:
                if im.users == 0:
                    bpy.data.images.remove(im)

    # chains: the one-pitch link from the GLB, walked round each belt by Geometry Nodes
    link = next((o for o in nodes.values() if o.type == 'MESH' and 'chain' in o.name.lower()), None)
    if link is None:
        raise RuntimeError('tandem.glb: no chain link mesh')
    link.hide_render = link.hide_viewport = True
    belts = extras['belts']
    bike.chains = {'timing': Belt(belts['timing'], belts['zTiming'], 'T'), 'drive': Belt(belts['drive'], belts['zDrive'], 'D')}
    chain_obs = {}
    for key, belt in bike.chains.items():
        K.Uniform(group, f'chain_{key}', belt.b['sOff'], lo=-1e9, hi=1e9, description='the walked arc length (m)')
        ng = _chain_group(f'{name}_chain_{key}', belt, link, group, f'chain_{key}')
        bike.made['node_groups'].append(ng)
        me = bpy.data.meshes.new(f'{name}_chain_{key}')
        ob = bpy.data.objects.new(f'{name}_chain_{key}', me)
        col.objects.link(ob)
        ob.parent = root
        ob.modifiers.new('chain', 'NODES').node_group = ng
        ob.visible_shadow = False                         # the engine's chains cast no shadow
        chain_obs[key] = ob
        belt.owner, belt.mesh, belt.u_phase, belt.machine = group, ob, f'chain_{key}', bike
    parts['timing_chain'], parts['drive_chain'] = chain_obs['timing'], chain_obs['drive']
    parts['link'] = link
    bike.parts = parts
    bike.state = None
    bike.update(0.0, {'speed': 0.0}, key=False)
    bike._own = {o.as_pointer() for o in [group] + list(group.children_recursive)}
    return bike


# ===================================================================================================================
# THE RIDER RIG (a VRM on the front saddle)
# ===================================================================================================================
RIG_BONES = ['hips', 'spine', 'chest', 'upperChest', 'neck', 'head',
             'leftShoulder', 'leftUpperArm', 'leftLowerArm', 'leftHand', 'rightShoulder', 'rightUpperArm',
             'rightLowerArm', 'rightHand', 'leftUpperLeg', 'leftLowerLeg', 'leftFoot', 'leftToes', 'rightUpperLeg',
             'rightLowerLeg', 'rightFoot', 'rightToes']
REQUIRED = ['hips', 'leftUpperLeg', 'leftLowerLeg', 'leftFoot', 'rightUpperLeg', 'rightLowerLeg', 'rightFoot',
            'leftUpperArm', 'leftLowerArm', 'leftHand', 'rightUpperArm', 'rightLowerArm', 'rightHand']
FINGERS = ['Index', 'Middle', 'Ring', 'Little']
PHAL = ['Proximal', 'Intermediate', 'Distal']
_RIGS = {}


def ankle_pitch(theta, scale=1.0):
    """tandem.js anklePitch: toe-down pitch through the pedal stroke (theta: that pedal's crank angle, 0 at top)."""
    return (13 + 10 * math.cos(theta - 240 * DEG)) * DEG * scale


def _qe(x, y, z):
    """three's Quaternion.setFromEuler(Euler(x, y, z, 'YXZ')): R = Ry Rx Rz (Blender order string 'ZXY')."""
    return Euler((x, y, z), 'ZXY').to_quaternion()


def _qaxis(axis, a):
    return Quaternion(Vector(axis).normalized(), a)


def frame_quat(d0, f0, d1, f1):
    """tandem.js frameQuat: the rotation taking the frame (d0, f0) to (d1, f1)."""
    a0 = d0.normalized()
    b0 = (f0 - a0 * f0.dot(a0)).normalized()
    c0 = a0.cross(b0)
    a1 = d1.normalized()
    b1 = (f1 - a1 * f1.dot(a1)).normalized()
    c1 = a1.cross(b1)
    M0 = Matrix((a0, b0, c0)).transposed()
    M1 = Matrix((a1, b1, c1)).transposed()
    return (M1 @ M0.transposed()).to_quaternion()


def two_bone(root, target, L1, L2, pole):
    """tandem.js twoBone: the analytic two-bone IK."""
    d = target - root
    dist = d.length
    reach = min((L1 + L2) * 0.9995, max(abs(L1 - L2) * 1.001 + 1e-4, dist))
    a = d / (dist or 1.0)
    b = pole - a * pole.dot(a)
    if b.length_squared < 1e-10:
        b = Vector((0.0, 0.0, 1.0))
    b.normalize()
    cosA = min(1.0, max(-1.0, (L1 * L1 + reach * reach - L2 * L2) / (2 * L1 * reach)))
    sinA = math.sqrt(1 - cosA * cosA)
    dir1 = a * cosA + b * sinA
    mid = root + dir1 * L1
    end = root + a * reach
    dir2 = (end - mid).normalized()
    hinge = a.cross(b).normalized()
    return {'dir1': dir1, 'dir2': dir2, 'mid': mid, 'end': end, 'hinge': hinge, 'reach': reach, 'dist': dist,
            'flex': math.acos(min(1.0, max(-1.0, dir1.dot(dir2))))}


def _rig_for(h, bike, opts):
    R = _RIGS.get(id(h))
    if R is not None and R['bike'] is bike:
        return R
    hum = h.humanoid
    node = {n: hum[n] for n in RIG_BONES if n in hum}
    for req in REQUIRED:
        if req not in node:
            raise ValueError(f'pose_rider: VRM lacks humanoid bone {req}')
    order = [n for n in RIG_BONES if n in node]
    by_bone = {b: n for n, b in node.items()}
    parent = {}
    for n in order:
        b = h.arm.data.bones[node[n]].parent
        hit = None
        while b is not None and hit is None:
            hit = by_bone.get(b.name)
            b = b.parent
        parent[n] = hit
    off = {}
    for n in order:
        p = parent[n]
        head = h.rest_head[node[n]]
        off[n] = to_three(head - h.rest_head[node[p]]) if p else to_three(head)
    fingers = {}
    for side in ('left', 'right'):
        for f in FINGERS:
            for ph in PHAL:
                k = side + f + ph
                if k in hum:
                    fingers[k] = hum[k]
        for ph in ('Metacarpal', 'Proximal', 'Distal'):
            k = side + 'Thumb' + ph
            if k in hum:
                fingers[k] = hum[k]
    S = opts.get('scale', 0.87)
    seat = bike.parts['front_seat']
    h.arm.parent = seat
    h.arm.matrix_parent_inverse.identity()
    h.arm.location = (0.0, 0.0, 0.0)
    h.arm.rotation_mode = 'QUATERNION'
    h.arm.rotation_quaternion = (1.0, 0.0, 0.0, 0.0)
    h.arm.scale = (S, S, S)
    tail = []
    if opts.get('tail', 'curl') == 'curl':
        b = h.arm.data.bones.get('tail_2')
        while b is not None:
            tail.append(b.name)
            b = next((c for c in b.children if 'tail' in c.name.lower()), None)
    R = {'bike': bike, 'node': node, 'order': order, 'parent': parent, 'off': off, 'fingers': fingers, 'S': S,
         'tail': tail, 'tail_mode': opts.get('tail', 'curl'), 'settle': bool(opts.get('settle', True))}
    _RIGS[id(h)] = R
    return R


def pose_rider(vrm, crank_angle, bike=None, t=0.0, frame=None, ctx=None, key=True, **opts):
    """tandem.js poseRider(vrm, crankAngle, opts): seat the VRM (a characters VRMHandle) on the front saddle at
    scale 0.87 and solve its pose for this crank angle: torso lean and sway, two-bone IK legs onto the pedals (with
    ankling), arms onto the grips (wrist twist shared with the forearm), fingers closed round the handles, the tail
    curled up behind (tail='curl'). Keys the pose (and the front pedals' pitch) at the frame of t / frame.

    opts (tandem.js's, snake_case): scale, tail ('curl' | 'spring'), lean, sway, head_pitch, head_yaw, hip_above_seat,
    hip_forward, sole, ankling, toe_out, foot_forward, grip_along, grip_palm, wrist_drop, finger_curl, tail_lift,
    settle (True: bake_rider_springs pre-rolls the springs on the first pose). scale, tail and settle are read on the
    first call for this VRM and bike, as the engine's rig read them.
    Returns {legs, arms, hips_pos} (three's model frame, model units; reach_err in metres). Once every frame is posed,
    bake_rider_springs(vrm, f0, f1) runs the springs (the mane, the tie) the way the engine ran them under a rider."""
    if bike is None or not hasattr(bike, 'parts'):
        raise ValueError('pose_rider: pass bike= (the tandem build() result)')
    o = {K._snake(k): v for k, v in opts.items()}
    h = vrm
    R = _rig_for(h, bike, o)
    S = R['S']
    th = float(crank_angle)
    bpy.context.view_layer.update()
    arm = h.arm
    inv = arm.matrix_world.inverted()
    inv_q = arm.matrix_world.decompose()[1].inverted()

    def to_model(obj):
        return to_three(inv @ obj.matrix_world.translation)
    X, Y, Z = Vector((1, 0, 0)), Vector((0, 1, 0)), Vector((0, 0, 1))

    lean = o.get('lean', 0.34)
    sway = o.get('sway', 1.0)
    roll, yaw = 0.022 * math.sin(th) * sway, 0.020 * math.cos(th) * sway
    breathe = 0.010 * math.sin(TAU * 0.27 * t)
    hp, hy = o.get('head_pitch', 0.0), o.get('head_yaw', 0.0)
    lq = {
        'hips': _qe(lean * 0.42, yaw, roll),
        'spine': _qe(lean * 0.22, -yaw * 0.7, -roll * 0.6),
        'chest': _qe(lean * 0.20 + breathe, -yaw * 0.4, -roll * 0.3),
        'upperChest': _qe(lean * 0.16 - breathe * 0.5, 0, 0),
        'neck': _qe(-lean * 0.34 + hp * 0.4, yaw * 0.3, roll * 0.3),
        'head': _qe(-lean * 0.40 + 0.010 * math.sin(2 * th) + hp * 0.6 + 0.06, hy + yaw * 0.4, roll * 0.5),
        'leftShoulder': _qe(0.0, -0.10, -0.04),
        'rightShoulder': _qe(0.0, 0.10, 0.04),
    }
    lay = bike.layout
    hip_above = o.get('hip_above_seat', lay['hipTarget'][1] - lay['frontSit'][1]) / S
    hip_fwd = o.get('hip_forward', lay['hipTarget'][0] - lay['frontSit'][0]) / S
    off, parent = R['off'], R['parent']
    mid_off = (off['leftUpperLeg'] + off['rightUpperLeg']) * 0.5
    hips_pos = Vector((0.0, hip_above, hip_fwd)) - lq['hips'] @ mid_off
    hips_pos.y += (0.0015 / S) * math.cos(2 * th)
    W = {}

    def fk(n):
        p = parent[n]
        q = lq.get(n, Quaternion())
        if not p:
            W[n] = (hips_pos.copy(), q.copy())
            return
        W[n] = (W[p][1] @ off[n] + W[p][0], W[p][1] @ q)
    for n in ('hips', 'spine', 'chest', 'upperChest', 'neck', 'head', 'leftShoulder', 'rightShoulder'):
        if n in R['node']:
            fk(n)

    def child_pos(n):
        p = parent[n]
        return W[p][1] @ off[n] + W[p][0]

    # ── legs ──
    legs, pedal_pitch = {}, {}
    pedal_top = lay.get('pedalTop', 0.016) / S
    sole = o.get('sole', 0.0214) / S
    for side in ('left', 'right'):
        is_r = side == 'right'
        pedal = bike.parts['front_pedal_r' if is_r else 'front_pedal_l']
        th_s = th if is_r else th + math.pi
        phi = ankle_pitch(th_s, o.get('ankling', 1.0))
        pedal_pitch[side] = phi
        toe_out = (-1 if is_r else 1) * o.get('toe_out', 3 * DEG)
        q_foot = _qaxis(X, phi) @ _qaxis(Y, toe_out)
        pc = to_model(pedal)
        up = q_foot @ Y
        ball = pc + up * (pedal_top + sole) + (q_foot @ Z) * (o.get('foot_forward', 0.0) / S)
        toes = off.get(side + 'Toes', Vector((0.0, -0.05, 0.1)))
        ankle = ball - q_foot @ toes
        ul, ll, ft = side + 'UpperLeg', side + 'LowerLeg', side + 'Foot'
        hip = child_pos(ul)
        L1, L2 = off[ll].length, off[ft].length
        pole = Vector((-0.10 if is_r else 0.10, 0.15, 1.0))
        s = two_bone(hip, ankle, L1, L2, pole)
        q_thigh = frame_quat(off[ll], Z, s['dir1'], s['hinge'].cross(s['dir1']))
        q_shin = frame_quat(off[ft], Z, s['dir2'], s['hinge'].cross(s['dir2']))
        lq[ul] = W['hips'][1].inverted() @ q_thigh
        lq[ll] = q_thigh.inverted() @ q_shin
        lq[ft] = q_shin.inverted() @ q_foot
        if side + 'Toes' in R['node']:
            lq[side + 'Toes'] = Quaternion()
        legs[side] = {'hip': hip, 'knee': s['mid'], 'ankle': ankle, 'ball': ball, 'pedal': pc, 'flex': s['flex'],
                      'reach_err': (s['dist'] - s['reach']) * S, 'phi': phi}

    # ── arms: shoulder -> elbow -> wrist, hands wrapped on the grips ──
    arms = {}
    for side in ('left', 'right'):
        is_r = side == 'right'
        grip = bike.parts['front_grip_r' if is_r else 'front_grip_l']
        G = to_model(grip)
        g_axis = to_three(inv_q @ (grip.matrix_world.decompose()[1] @ Vector((0.0, -1.0, 0.0)))).normalized()
        ua, la, hd = side + 'UpperArm', side + 'LowerArm', side + 'Hand'
        shoulder = child_pos(ua)
        L1, L2 = off[la].length, off[hd].length
        pole = Vector((-0.65 if is_r else 0.65, -0.55, -0.35))
        along, palm = o.get('grip_along', 0.074) / S, o.get('grip_palm', 0.028) / S
        drop = o.get('wrist_drop', 12 * DEG)
        dH = Z * math.cos(0.8) - Y * math.sin(0.8)
        s = wrist = nP = None
        for _it in range(3):
            dH = (dH - g_axis * dH.dot(g_axis)).normalized()
            nP = g_axis.cross(dH).normalized()
            if nP.y > 0:
                nP = -nP
            wrist = G - dH * along - nP * palm
            s = two_bone(shoulder, wrist, L1, L2, pole)
            fore = s['dir2'].copy()
            fore = (fore - g_axis * fore.dot(g_axis)).normalized()
            c, sn = math.cos(drop), math.sin(drop)
            cand = fore * c + g_axis.cross(fore) * sn
            cand2 = fore * c - g_axis.cross(fore) * sn
            dH = cand if cand.y < cand2.y else cand2
        back = Vector((0.0, 0.0, -1.0))
        q_upper = frame_quat(off[la], back, s['dir1'], s['hinge'].cross(s['dir1']))
        q_fore = frame_quat(off[hd], back, s['dir2'], s['hinge'].cross(s['dir2']))
        q_hand = frame_quat(off[hd], Vector((0.0, -1.0, 0.0)), dH, nP)
        parent_q = W[parent[ua]][1]
        lq[ua] = parent_q.inverted() @ q_upper
        q_fore_local = q_upper.inverted() @ q_fore
        q_hand_local = q_fore.inverted() @ q_hand
        t_axis = off[hd].normalized()
        r = Vector((q_hand_local.x, q_hand_local.y, q_hand_local.z))
        pr = t_axis * r.dot(t_axis)
        tw = Quaternion((q_hand_local.w, pr.x, pr.y, pr.z)).normalized()
        half = Quaternion().slerp(tw, 0.5)
        lq[la] = q_fore_local @ half
        lq[hd] = half.inverted() @ q_hand_local
        arms[side] = {'shoulder': shoulder, 'elbow': s['mid'], 'wrist': wrist, 'grip': G, 'flex': s['flex'],
                      'reach_err': (s['dist'] - s['reach']) * S}

    # ── fingers close round the handle ──
    curl = o.get('finger_curl', 1.0)
    sgn = {'left': -1, 'right': 1}
    seg = {'Proximal': 1.05, 'Intermediate': 1.20, 'Distal': 0.75}
    fq = {}
    for side in ('left', 'right'):
        for f in FINGERS:
            for ph in PHAL:
                k = side + f + ph
                if k in R['fingers']:
                    fq[k] = _qaxis(Z, sgn[side] * seg[ph] * curl)
        for ph, q in (('Metacarpal', Euler((0.25 * curl, sgn[side] * -0.25 * curl, sgn[side] * 0.35 * curl), 'ZYX').to_quaternion()),
                      ('Proximal', _qaxis(Z, sgn[side] * 0.45 * curl)), ('Distal', _qaxis(Z, sgn[side] * 0.55 * curl))):
            k = side + 'Thumb' + ph
            if k in R['fingers']:
                fq[k] = q

    # ── write the pose (normalized rotations, three's frame) and the hips position ──
    pose = {n: lq[n] for n in R['order'] if n in lq}
    pose.update(fq)
    h.write_pose(pose)
    hb = R['node']['hips']
    pb_h = arm.pose.bones[hb]
    delta = Vector((hips_pos.x, -hips_pos.z, hips_pos.y)) - h.rest_head[hb]
    pb_h.location = h.rest_q[hb].inverted() @ delta
    written = [arm.pose.bones[h.humanoid[n]] for n in pose]
    if len(R['tail']) > 1:
        written += _pose_tail(R, h, th, t, o)
    ctx = ctx or bike.ctx
    f = frame if frame is not None else (bike.frame_at(t, ctx) if t is not None else bike.scene.frame_current)
    bike.set_pedal_pitch(bike.parts['front_pedal_r'], th, pedal_pitch['right'], frame=f, ctx=ctx, key=key)
    bike.set_pedal_pitch(bike.parts['front_pedal_l'], th, pedal_pitch['left'], frame=f, ctx=ctx, key=key)
    if key:
        for pb in written:
            pb.rotation_mode = 'QUATERNION'
            bike.keyer.key(pb, 'rotation_quaternion', frame=f, ctx=ctx, interpolation='LINEAR')
        bike.keyer.key(pb_h, 'location', frame=f, ctx=ctx, interpolation='LINEAR')
    return {'legs': legs, 'arms': arms, 'hips_pos': hips_pos}


def _pose_tail(R, h, th, t, o):
    """tandem.js poseTail on the raw tail bones: each segment aimed along a rising arc in the rider's frame, with a
    small sway travelling down the tail twice per crank turn (armature space here; the engine aimed in world space
    against each parent's current rotation, the same thing)."""
    arm = h.arm
    names = R['tail']
    n = len(names)
    lift = o.get('tail_lift', 1.0)
    out = []
    for k in range(n - 1):
        bpy.context.view_layer.update()
        pb = arm.pose.bones[names[k]]
        child = arm.data.bones[names[k + 1]]
        u = k / max(1, n - 2)
        alpha = (22 + 92 * u ** 0.7) * DEG * lift
        swy = 0.16 * u * u * math.sin(2 * th - 1.1 * k) + 0.05 * u * math.sin(TAU * 0.21 * t)
        d_model = Vector((swy, math.sin(alpha), -math.cos(alpha))).normalized()
        d_arm = Vector((d_model.x, -d_model.z, d_model.y))
        b = pb.bone
        if pb.parent is not None:
            P = pb.parent.matrix.to_quaternion()
            rest_local = (b.parent.matrix_local.to_quaternion().inverted() @ b.matrix_local.to_quaternion())
        else:
            P = Quaternion()
            rest_local = b.matrix_local.to_quaternion()
        R0 = P @ rest_local
        child_local = b.matrix_local.inverted() @ child.head_local
        cur = (R0 @ child_local).normalized()
        delta = cur.rotation_difference(d_arm)
        pb.rotation_mode = 'QUATERNION'
        pb.rotation_quaternion = R0.inverted() @ (delta @ R0)
        out.append(pb)
    return out


# ===================================================================================================================
# THE RIDER'S SPRINGS (the mane and the tie, as tandem.js left the VRM's spring manager)
# ===================================================================================================================
SETTLE_STEPS, SETTLE_DT = 120, 1.0 / 60.0         # tandem.js: 120 x springBoneManager.update(1 / 60) on the first pose
RIDER_ROOT = '<rider root>'                        # the spring center tandem.js gave every joint: vrm.scene


def _rider_spring_rig(h, drop_tail, center='rider'):
    """characters.springs.SpringRig as tandem.js's rigFor left three-vrm's manager: every joint's center is the VRM's
    root (vrm.scene; here its armature object), so the springs swing in the rider's own frame and the bike's travel
    never drags them; with the tail curled by the rig ('curl'), its joints are out of the solver (sbm.deleteJoint).
    center='vrm' keeps the centers the VRM file gives (a plain characters.springs bake)."""
    from ..characters.springs import SpringRig

    class RiderSprings(SpringRig):
        def world(self, bone):
            if bone == RIDER_ROOT:
                return self._root                 # the armature's world matrix as read_pose read it this frame
            return super().world(bone)
    rig = RiderSprings(h)
    rig.dropped = []
    if drop_tail:
        keep = [j for j in rig.joints if 'tail' not in j.bone.lower()]
        rig.dropped = [j.bone for j in rig.joints if 'tail' in j.bone.lower()]
        rig.joints = keep
        rig.by_bone = {j.bone: j for j in keep}
        rig.first = {}
        for j in keep:
            rig.first.setdefault(j.spring, j.bone)
        rig._below = set()                        # what the simulated chains carry (the dropped tail is posed)
        for b in h.arm.data.bones:
            p = b.parent
            while p is not None:
                if p.name in rig.by_bone:
                    rig._below.add(b.name)
                    break
                p = p.parent
        rig.springs = [s for s in rig.springs if any(b in rig.by_bone for b in s['joints'])]
    if center == 'rider':
        for j in rig.joints:
            j.center = RIDER_ROOT
    elif center != 'vrm':
        raise ValueError(f"bake_rider_springs center={center!r}: 'rider' (tandem.js) or 'vrm' (the file's own)")
    return rig


def bake_rider_springs(vrm, f0, f1, settle=None, center='rider', scene=None, log=None):
    """The rider's springs over frames f0..f1, simulated as tandem.js ran them under a rider and keyed: call it once
    pose_rider has keyed every frame (the springs follow the body's motion, as in the engine, where they stepped after
    the pose). Every joint swings in the rider's own frame (its center is the VRM's root, so a bike at speed does not
    drag the mane back); the tail's joints stay out of the solver while the rig curls it (tail='curl'); with settle
    (pose_rider's, default True) the springs are pre-rolled 120 steps of 1/60 s on frame f0's pose, so the mane and the
    tie do not swing in from the T-pose on camera; then one step per frame (the engine's vrm.update(dt)). The keys go
    on the NLA track '<name>|springs' as characters.springs.bake_springs keys them (LINEAR; the body's action keys no
    spring bone, so nothing fights it); characters.springs.remove_springs(vrm) removes them.

    center: 'rider' (tandem.js) or 'vrm' (the centers the VRM file gives: what a plain bake_springs simulates).
    Returns {joints, springs, dropped (the tail's bones), settle_steps, steps, keys, track, swing_deg, nan}."""
    from ..characters import springs as SP
    h = vrm
    R = _RIGS.get(id(h))
    if R is None:
        raise ValueError('bake_rider_springs: pose the rider with pose_rider(vrm, crank_angle, bike=...) first')
    settle = R['settle'] if settle is None else bool(settle)
    scene = scene or R['bike'].scene
    dt = 1.0 / (scene.render.fps / scene.render.fps_base)
    rig = _rider_spring_rig(h, R['tail_mode'] == 'curl', center)
    arm = h.arm
    tname = f'{h.name}|springs'
    SP.remove_springs(h)
    bones = [j.bone for j in rig.joints]
    for b in bones:
        pb = arm.pose.bones[b]
        pb.rotation_mode = 'QUATERNION'
        pb.rotation_quaternion = (1.0, 0.0, 0.0, 0.0)
        pb.scale = (1.0, 1.0, 1.0)
    hidden = [o for o in h.meshes if not o.hide_viewport]
    for o in hidden:                              # the meshes need no evaluation while the springs bake
        o.hide_viewport = True
    find = getattr(SP, '_addon_handler_module', None)
    mod = find() if find else None
    held = []
    if mod is not None:                           # the add-on's own frame-change step would run on every frame_set
        for fn in list(bpy.app.handlers.frame_change_pre):
            if fn is getattr(mod, 'frame_change_pre', None):
                bpy.app.handlers.frame_change_pre.remove(fn)
                held.append(fn)
    series = {b: [] for b in bones}
    swing, steps, nan, pre = {}, 0, 0, 0
    try:
        scene.frame_set(f0)
        rig.read_pose()
        rig.set_init_state()
        if settle:
            for _ in range(SETTLE_STEPS):
                rig.update(SETTLE_DT)
            pre = SETTLE_STEPS
        for f in range(f0, f1 + 1):
            scene.frame_set(f)
            rig.read_pose()
            rig.update(dt)
            steps += 1
            for j in rig.joints:
                q = j.basis.copy()
                if any(math.isnan(c) for c in q):
                    nan += 1
                    q = Quaternion()
                lst = series[j.bone]
                if lst and lst[-1][1].dot(q) < 0:          # the short way round between keys
                    q.negate()
                lst.append((f, q, j.scale))
                if rig.first.get(j.spring) == j.bone:
                    swing[j.spring] = max(swing.get(j.spring, 0.0), math.degrees(j.init_basis.rotation_difference(q).angle))
    finally:
        for fn in held:
            bpy.app.handlers.frame_change_pre.append(fn)
        for o in hidden:
            o.hide_viewport = False
    act, _track, n_keys = SP.key_track(h, tname, series, f0)
    for b in bones:                               # the track drives these bones now
        arm.pose.bones[b].rotation_quaternion = (1.0, 0.0, 0.0, 0.0)
    scene.frame_set(scene.frame_current)
    rep = {'joints': len(rig.joints), 'springs': len(rig.springs), 'dropped': rig.dropped, 'settle_steps': pre,
           'steps': steps, 'keys': n_keys, 'track': tname, 'action': act.name, 'center': center,
           'swing_deg': {k: round(v, 2) for k, v in swing.items()}, 'nan': nan, 'series': series}
    if log:
        log(f'[tandem] {h.name}: {rep["joints"]} spring joints baked over {f0}..{f1} '
            f'({pre} settle steps, tail {"curled" if rig.dropped else "springing"})')
    return rep


# ===================================================================================================================
# THE UTAH TEAPOT STOKER (Newell's original proportions, blinn = False)
# ===================================================================================================================
_MS = np.array([[-1.0, 3.0, -3.0, 1.0], [3.0, -6.0, 3.0, 0.0], [-3.0, 3.0, 0.0, 0.0], [1.0, 0.0, 0.0, 0.0]])


def teapot_geometry(size=50.0, segments=10, bottom=True, lid=True, body=True, fit_lid=True, blinn=True):
    """three's TeapotGeometry (Martin Newell's 32 Bezier patches): positions, normals and UVs as three built them,
    degenerate triangles at the cusps dropped. Returns a kit Geo (three axes)."""
    blinn_scale = 1.3
    max_h = 3.15 * (1 if blinn else blinn_scale)
    max_h2 = max_h / 2
    true_size = size / max_h2
    P = np.array(TEAPOT_PATCHES, np.int64).reshape(32, 4, 4)
    V = np.array(TEAPOT_VERTICES, float).reshape(-1, 3)
    vpr = segments + 1
    pos, nrm, uvs, tris = [], [], [], []
    surf_count = 0
    lo = 0 if body else 20
    hi = 32 if bottom else 28
    ss = np.arange(vpr) / segments
    for surf in range(lo, hi):
        if not (lid or surf < 20 or surf >= 28):
            continue
        G = V[P[surf]].copy()                              # (4 r, 4 c, 3)
        if fit_lid and 20 <= surf < 28:
            G[..., 0:2] *= 1.077
        if not blinn:
            G[..., 2] *= blinn_scale
        mgm = []
        for i in range(3):
            g = G[..., i].T                                # g[c * 4 + r]: transposed as three loads it
            mgm.append(_MS.T @ (g @ _MS))                  # three: mgm = mst * (gmx * ms)
        base = len(pos)
        for s in ss:
            sp = np.array([s ** 3, s ** 2, s, 1.0])
            dsp = np.array([3 * s * s, 2 * s, 1.0, 0.0])
            for t in ss:
                tp = np.array([t ** 3, t ** 2, t, 1.0])
                dtp = np.array([3 * t * t, 2 * t, 1.0, 0.0])
                vert = [sp @ mgm[i].T @ tp for i in range(3)]       # Vector4.applyMatrix4(m): m @ v, then . tp
                sdir = np.array([dsp @ mgm[i].T @ tp for i in range(3)])
                tdir = np.array([sp @ mgm[i].T @ dtp for i in range(3)])
                n = np.cross(tdir, sdir)
                ln = np.linalg.norm(n)
                n = n / ln if ln > 0 else n
                if vert[0] == 0 and vert[1] == 0:
                    no = (0.0, 1.0 if vert[2] > max_h2 else -1.0, 0.0)
                else:
                    no = (n[0], n[2], -n[1])
                pos.append((true_size * vert[0], true_size * (vert[2] - max_h2), -true_size * vert[1]))
                nrm.append(no)
                uvs.append((1 - t, 1 - s))
        Pa = np.array(pos[base:])

        def same(a, b):
            return np.array_equal(np.float32(Pa[a - base]), np.float32(Pa[b - base]))
        for si in range(segments):
            for ti in range(segments):
                v1 = base + si * vpr + ti
                v2, v4 = v1 + 1, v1 + vpr
                v3 = v2 + vpr
                if not (same(v1, v2) or same(v1, v3) or same(v2, v3)):
                    tris.append((v1, v2, v3))
                if not (same(v1, v3) or same(v1, v4) or same(v3, v4)):
                    tris.append((v1, v3, v4))
        surf_count += 1
    return K.Geo(pos, nrm, uvs, tris)


def _teapot_material(name, color, scene):
    """tandem.js's glazed ceramic: classic cream, mottled, fine crazing in the glaze (two Worley scales, each faded
    out as the camera's pixel grows past its line width), an unglazed foot ring."""
    m = K.new_material(name)
    t = m.node_tree
    t.nodes.clear()
    nb = K.NB(t)
    b = K.principled(nb)
    P = nb.texcoord('Object')
    _px, _py, pz = nb.sep(P)
    # the camera's pixel footprint at the surface (three's max(|dFdx(positionView)|, |dFdy(positionView)|))
    pix = nb.new('ShaderNodeValue')
    pix.label = 'pixel angle'
    pix.outputs[0].default_value = 1.0 / 1500.0
    d = pix.outputs[0].driver_add('default_value').driver
    d.type = 'SCRIPTED'
    for vn, path in (('a', 'camera.data.angle'), ('rx', 'render.resolution_x'), ('ry', 'render.resolution_y'),
                     ('p', 'render.resolution_percentage')):
        v = d.variables.new()
        v.name, v.type = vn, 'SINGLE_PROP'
        v.targets[0].id_type = 'SCENE'
        v.targets[0].id = scene
        v.targets[0].data_path = path
    d.expression = '2*tan(a/2)*100/(max(rx, ry)*p)'
    cam = nb.new('ShaderNodeCameraData')
    px = nb.mul(cam.outputs['View Z Depth'], pix.outputs[0])

    def craze(scale, offset, width, f0, f1):
        vor = []
        for feat in ('F1', 'F2'):
            n = nb.new('ShaderNodeTexVoronoi', voronoi_dimensions='3D', feature=feat, distance='EUCLIDEAN')
            nb.put(n.inputs['Vector'], nb.vadd(nb.vscale(P, 1.0 / scale), offset))
            n.inputs['Scale'].default_value = 1.0
            n.inputs['Randomness'].default_value = 1.0
            vor.append(n.outputs['Distance'])
        edge = nb.sub(nb.math('SQRT', vor[1]), nb.math('SQRT', vor[0]))
        return nb.mul(nb.sub(1.0, nb.smoothstep(0.0, width, edge)), nb.smoothstep(f0, f1, px))
    c1 = craze(0.018, (0.0, 0.0, 0.0), 0.045, 0.0045, 0.0015)
    c2 = craze(0.0065, (5.1, 2.3, 7.7), 0.04, 0.0018, 0.0006)
    cr = nb.mx(c1, nb.mul(c2, 0.55))
    mott = nb.fbm01(P, 9.0, 3)
    foot = nb.smoothstep(0.012, 0.0, pz)                   # three's P.y: height above the foot
    col = nb.vmix(K.lin(color), K.lin(0xc5a978), nb.mul(mott, 0.28))
    col = nb.vmix(col, K.lin(0x7a5a3a), nb.mul(cr, 0.32))
    col = nb.vmix(col, K.lin(0xb09a7c), nb.mul(foot, 0.7))
    nb.put(b.inputs['Base Color'], col)
    nb.put(b.inputs['Roughness'], nb.add(nb.add(0.30, nb.mul(cr, 0.2)), nb.mul(foot, 0.4)))
    nb.put(b.inputs['Coat Weight'], nb.sub(1.0, foot))
    nb.put(b.inputs['Coat Roughness'], nb.clamp(nb.add(nb.add(0.045, nb.mul(cr, 0.1)), nb.mul(mott, 0.03)), 0.02, 1.0))
    nb.put(b.inputs['Metallic'], 0.0)
    m.use_backface_culling = False
    m['eido_role'] = name
    return m


class TeapotRider:
    """build_teapot_rider()'s result: group, parts {tilt, bob, body, lid, lid_pivot}, height, update(t, crank_angle),
    mount(bike), dispose()."""

    def __init__(self, group, parts, height, lid_base, collection, made, scene, ctx=None):
        self.group, self.parts, self.height = group, parts, height
        self._lid_base = lid_base
        self.collection, self.made, self.scene, self.ctx = collection, made, scene, ctx
        self.keyer = K.Keyer()

    def update(self, t, crank_angle=0.0, frame=None, ctx=None, key=True):
        """tandem.js teapot update(t, crankAngle): a little bob twice per crank turn, a sway, the lid's rattle. Keyed
        at the frame of t (or `frame`), through ctx (or the ctx it was built with) when there is one."""
        ctx = ctx or self.ctx
        th = float(crank_angle)
        P = self.parts
        bob, lid_pivot, lid = P['bob'], P['lid_pivot'], P['lid']
        bob.location = (0.0, 0.0, 0.0028 * (0.5 - 0.5 * math.cos(2 * th)))
        mode, e = euler_three(0.012 * math.sin(2 * th + 0.8), 0.0, 0.018 * math.sin(th))
        bob.rotation_mode = mode
        bob.rotation_euler = e
        rattle = max(0.0, math.sin(2 * th + 1.3)) ** 6
        lb = self._lid_base
        lid_pivot.location = v3(lb[0], lb[1] + 0.0011 * rattle, lb[2])
        lid.rotation_mode = 'XYZ'
        lid.rotation_euler = (0.0, 0.0, 0.025 * math.sin(2 * th))          # three's rotation.y = Blender's z
        if key:
            sc = self.scene
            f = frame if frame is not None else (ctx.frame_at(t) if ctx is not None else
                                                 common.frame_at(t, sc.render.fps / sc.render.fps_base, sc.frame_start))
            for ob, path in ((bob, 'location'), (bob, 'rotation_euler'), (lid_pivot, 'location'), (lid, 'rotation_euler')):
                self.keyer.key(ob, path, frame=f, ctx=ctx)

    def mount(self, bike, contact=None, seat_offset=None):
        """tandem.js mount(bike): onto the rear saddle (spout forward, the base just touching the leather)."""
        o = self._opts
        g = self.group
        g.parent = bike.parts['rear_seat']
        g.matrix_parent_inverse.identity()
        g.location = v3(0.0, o.get('contact', 0.0005) if contact is None else contact,
                        o.get('seat_offset', -0.004) if seat_offset is None else seat_offset)
        return self

    def dispose(self):
        """tandem.js dispose(): the teapot's objects, meshes, glaze and keys go (and its collection, when
        build_teapot_rider made it)."""
        objs = [self.group] + list(self.group.children_recursive)
        meshes = {o.data for o in objs if o.type == 'MESH'}
        actions = {o.animation_data.action for o in objs if o.animation_data and o.animation_data.action}
        for ob in objs:
            bpy.data.objects.remove(ob, do_unlink=True)
        for me in meshes:
            if me.users == 0:
                bpy.data.meshes.remove(me)
        for m in self.made:
            if m.users == 0:
                bpy.data.materials.remove(m)
        for a in actions:
            if a.users == 0:
                bpy.data.actions.remove(a)
        col = self.collection
        if getattr(self, '_own_collection', False) and col is not None and col.name in bpy.data.collections \
                and not col.all_objects:
            bpy.data.collections.remove(col)


def build_teapot_rider(height=0.35, segments=20, color=0xe0cc9f, pitch=-0.035, roll=0.055, contact=0.0005,
                       seat_offset=-0.004, name='teapot_rider', collection=None, scene=None, ctx=None):
    """tandem.js buildTeapotRider(THREE, opts): the Utah teapot at `height` (Newell's proportions), body and lid as
    separate meshes (the lid rattles), glazed ceramic; upright, a little jaunty (pitch, roll); contact and
    seat_offset place it on the rear saddle at mount(). ctx: a scene's ctx (the default route of update's keys)."""
    scene = scene or (ctx.scene if ctx is not None else bpy.context.scene)
    col = collection or bpy.data.collections.new(name)
    if col.name not in scene.collection.children and col is not scene.collection:
        scene.collection.children.link(col)
    body = teapot_geometry(1, segments, True, False, True, True, False)
    lid = teapot_geometry(1, segments, False, True, False, True, False)
    allp = np.concatenate([body.pos, lid.pos])
    bmin, bmax = allp.min(axis=0), allp.max(axis=0)
    s = height / (bmax[1] - bmin[1])
    for g in (body, lid):
        g.translate(0.0, -bmin[1], 0.0)
        g.apply(np.diag([s, s, s, 1.0]))
        g.rotate_y(-math.pi / 2)                         # the spout (+X) now points +Z: forward on the seat
    lmin, lmax = lid.pos.min(axis=0), lid.pos.max(axis=0)
    lid_base = ((lmin[0] + lmax[0]) / 2, lmin[1], (lmin[2] + lmax[2]) / 2)
    lid.translate(-lid_base[0], -lid_base[1], -lid_base[2])
    mat = _teapot_material(f'{name}_glaze', color, scene)

    def empty(nm, parent):
        e = bpy.data.objects.new(nm, None)
        e.empty_display_size = 0.05
        col.objects.link(e)
        e.parent = parent
        return e
    group = empty(name, None)
    tilt = empty(f'{name}_tilt', group)
    mode, e = euler_three(pitch, 0.0, roll)
    tilt.rotation_mode = mode
    tilt.rotation_euler = e
    bob = empty(f'{name}_bob', tilt)
    m_body = K.mesh_object(f'{name}_body', body, [mat], col, parent=bob)
    lid_pivot = empty(f'{name}_lid_pivot', bob)
    lid_pivot.location = v3(*lid_base)
    m_lid = K.mesh_object(f'{name}_lid', lid, [mat], col, parent=lid_pivot)
    tp = TeapotRider(group, {'tilt': tilt, 'bob': bob, 'body': m_body, 'lid': m_lid, 'lid_pivot': lid_pivot}, height,
                     lid_base, col, [mat], scene, ctx=ctx)
    tp._opts = {'contact': contact, 'seat_offset': seat_offset}
    tp._own_collection = collection is None
    tp.update(0.0, 0.0, key=False)
    return tp


TEAPOT_PATCHES = (
    0, 1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12, 13, 14, 15,
    3, 16, 17, 18, 7, 19, 20, 21, 11, 22, 23, 24, 15, 25, 26, 27,
    18, 28, 29, 30, 21, 31, 32, 33, 24, 34, 35, 36, 27, 37, 38, 39,
    30, 40, 41, 0, 33, 42, 43, 4, 36, 44, 45, 8, 39, 46, 47, 12,
    12, 13, 14, 15, 48, 49, 50, 51, 52, 53, 54, 55, 56, 57, 58, 59,
    15, 25, 26, 27, 51, 60, 61, 62, 55, 63, 64, 65, 59, 66, 67, 68,
    27, 37, 38, 39, 62, 69, 70, 71, 65, 72, 73, 74, 68, 75, 76, 77,
    39, 46, 47, 12, 71, 78, 79, 48, 74, 80, 81, 52, 77, 82, 83, 56,
    56, 57, 58, 59, 84, 85, 86, 87, 88, 89, 90, 91, 92, 93, 94, 95,
    59, 66, 67, 68, 87, 96, 97, 98, 91, 99, 100, 101, 95, 102, 103, 104,
    68, 75, 76, 77, 98, 105, 106, 107, 101, 108, 109, 110, 104, 111, 112, 113,
    77, 82, 83, 56, 107, 114, 115, 84, 110, 116, 117, 88, 113, 118, 119, 92,
    120, 121, 122, 123, 124, 125, 126, 127, 128, 129, 130, 131, 132, 133, 134, 135,
    123, 136, 137, 120, 127, 138, 139, 124, 131, 140, 141, 128, 135, 142, 143, 132,
    132, 133, 134, 135, 144, 145, 146, 147, 148, 149, 150, 151, 68, 152, 153, 154,
    135, 142, 143, 132, 147, 155, 156, 144, 151, 157, 158, 148, 154, 159, 160, 68,
    161, 162, 163, 164, 165, 166, 167, 168, 169, 170, 171, 172, 173, 174, 175, 176,
    164, 177, 178, 161, 168, 179, 180, 165, 172, 181, 182, 169, 176, 183, 184, 173,
    173, 174, 175, 176, 185, 186, 187, 188, 189, 190, 191, 192, 193, 194, 195, 196,
    176, 183, 184, 173, 188, 197, 198, 185, 192, 199, 200, 189, 196, 201, 202, 193,
    203, 203, 203, 203, 204, 205, 206, 207, 208, 208, 208, 208, 209, 210, 211, 212,
    203, 203, 203, 203, 207, 213, 214, 215, 208, 208, 208, 208, 212, 216, 217, 218,
    203, 203, 203, 203, 215, 219, 220, 221, 208, 208, 208, 208, 218, 222, 223, 224,
    203, 203, 203, 203, 221, 225, 226, 204, 208, 208, 208, 208, 224, 227, 228, 209,
    209, 210, 211, 212, 229, 230, 231, 232, 233, 234, 235, 236, 237, 238, 239, 240,
    212, 216, 217, 218, 232, 241, 242, 243, 236, 244, 245, 246, 240, 247, 248, 249,
    218, 222, 223, 224, 243, 250, 251, 252, 246, 253, 254, 255, 249, 256, 257, 258,
    224, 227, 228, 209, 252, 259, 260, 229, 255, 261, 262, 233, 258, 263, 264, 237,
    265, 265, 265, 265, 266, 267, 268, 269, 270, 271, 272, 273, 92, 119, 118, 113,
    265, 265, 265, 265, 269, 274, 275, 276, 273, 277, 278, 279, 113, 112, 111, 104,
    265, 265, 265, 265, 276, 280, 281, 282, 279, 283, 284, 285, 104, 103, 102, 95,
    265, 265, 265, 265, 282, 286, 287, 266, 285, 288, 289, 270, 95, 94, 93, 92,
)
TEAPOT_VERTICES = (
    1.4, 0, 2.4, 1.4, -0.784, 2.4, 0.784, -1.4, 2.4, 0, -1.4, 2.4,
    1.3375, 0, 2.53125, 1.3375, -0.749, 2.53125, 0.749, -1.3375, 2.53125, 0, -1.3375, 2.53125,
    1.4375, 0, 2.53125, 1.4375, -0.805, 2.53125, 0.805, -1.4375, 2.53125, 0, -1.4375, 2.53125,
    1.5, 0, 2.4, 1.5, -0.84, 2.4, 0.84, -1.5, 2.4, 0, -1.5, 2.4,
    -0.784, -1.4, 2.4, -1.4, -0.784, 2.4, -1.4, 0, 2.4, -0.749, -1.3375, 2.53125,
    -1.3375, -0.749, 2.53125, -1.3375, 0, 2.53125, -0.805, -1.4375, 2.53125, -1.4375, -0.805, 2.53125,
    -1.4375, 0, 2.53125, -0.84, -1.5, 2.4, -1.5, -0.84, 2.4, -1.5, 0, 2.4,
    -1.4, 0.784, 2.4, -0.784, 1.4, 2.4, 0, 1.4, 2.4, -1.3375, 0.749, 2.53125,
    -0.749, 1.3375, 2.53125, 0, 1.3375, 2.53125, -1.4375, 0.805, 2.53125, -0.805, 1.4375, 2.53125,
    0, 1.4375, 2.53125, -1.5, 0.84, 2.4, -0.84, 1.5, 2.4, 0, 1.5, 2.4,
    0.784, 1.4, 2.4, 1.4, 0.784, 2.4, 0.749, 1.3375, 2.53125, 1.3375, 0.749, 2.53125,
    0.805, 1.4375, 2.53125, 1.4375, 0.805, 2.53125, 0.84, 1.5, 2.4, 1.5, 0.84, 2.4,
    1.75, 0, 1.875, 1.75, -0.98, 1.875, 0.98, -1.75, 1.875, 0, -1.75, 1.875,
    2, 0, 1.35, 2, -1.12, 1.35, 1.12, -2, 1.35, 0, -2, 1.35,
    2, 0, 0.9, 2, -1.12, 0.9, 1.12, -2, 0.9, 0, -2, 0.9,
    -0.98, -1.75, 1.875, -1.75, -0.98, 1.875, -1.75, 0, 1.875, -1.12, -2, 1.35,
    -2, -1.12, 1.35, -2, 0, 1.35, -1.12, -2, 0.9, -2, -1.12, 0.9,
    -2, 0, 0.9, -1.75, 0.98, 1.875, -0.98, 1.75, 1.875, 0, 1.75, 1.875,
    -2, 1.12, 1.35, -1.12, 2, 1.35, 0, 2, 1.35, -2, 1.12, 0.9,
    -1.12, 2, 0.9, 0, 2, 0.9, 0.98, 1.75, 1.875, 1.75, 0.98, 1.875,
    1.12, 2, 1.35, 2, 1.12, 1.35, 1.12, 2, 0.9, 2, 1.12, 0.9,
    2, 0, 0.45, 2, -1.12, 0.45, 1.12, -2, 0.45, 0, -2, 0.45,
    1.5, 0, 0.225, 1.5, -0.84, 0.225, 0.84, -1.5, 0.225, 0, -1.5, 0.225,
    1.5, 0, 0.15, 1.5, -0.84, 0.15, 0.84, -1.5, 0.15, 0, -1.5, 0.15,
    -1.12, -2, 0.45, -2, -1.12, 0.45, -2, 0, 0.45, -0.84, -1.5, 0.225,
    -1.5, -0.84, 0.225, -1.5, 0, 0.225, -0.84, -1.5, 0.15, -1.5, -0.84, 0.15,
    -1.5, 0, 0.15, -2, 1.12, 0.45, -1.12, 2, 0.45, 0, 2, 0.45,
    -1.5, 0.84, 0.225, -0.84, 1.5, 0.225, 0, 1.5, 0.225, -1.5, 0.84, 0.15,
    -0.84, 1.5, 0.15, 0, 1.5, 0.15, 1.12, 2, 0.45, 2, 1.12, 0.45,
    0.84, 1.5, 0.225, 1.5, 0.84, 0.225, 0.84, 1.5, 0.15, 1.5, 0.84, 0.15,
    -1.6, 0, 2.025, -1.6, -0.3, 2.025, -1.5, -0.3, 2.25, -1.5, 0, 2.25,
    -2.3, 0, 2.025, -2.3, -0.3, 2.025, -2.5, -0.3, 2.25, -2.5, 0, 2.25,
    -2.7, 0, 2.025, -2.7, -0.3, 2.025, -3, -0.3, 2.25, -3, 0, 2.25,
    -2.7, 0, 1.8, -2.7, -0.3, 1.8, -3, -0.3, 1.8, -3, 0, 1.8,
    -1.5, 0.3, 2.25, -1.6, 0.3, 2.025, -2.5, 0.3, 2.25, -2.3, 0.3, 2.025,
    -3, 0.3, 2.25, -2.7, 0.3, 2.025, -3, 0.3, 1.8, -2.7, 0.3, 1.8,
    -2.7, 0, 1.575, -2.7, -0.3, 1.575, -3, -0.3, 1.35, -3, 0, 1.35,
    -2.5, 0, 1.125, -2.5, -0.3, 1.125, -2.65, -0.3, 0.9375, -2.65, 0, 0.9375,
    -2, -0.3, 0.9, -1.9, -0.3, 0.6, -1.9, 0, 0.6, -3, 0.3, 1.35,
    -2.7, 0.3, 1.575, -2.65, 0.3, 0.9375, -2.5, 0.3, 1.125, -1.9, 0.3, 0.6,
    -2, 0.3, 0.9, 1.7, 0, 1.425, 1.7, -0.66, 1.425, 1.7, -0.66, 0.6,
    1.7, 0, 0.6, 2.6, 0, 1.425, 2.6, -0.66, 1.425, 3.1, -0.66, 0.825,
    3.1, 0, 0.825, 2.3, 0, 2.1, 2.3, -0.25, 2.1, 2.4, -0.25, 2.025,
    2.4, 0, 2.025, 2.7, 0, 2.4, 2.7, -0.25, 2.4, 3.3, -0.25, 2.4,
    3.3, 0, 2.4, 1.7, 0.66, 0.6, 1.7, 0.66, 1.425, 3.1, 0.66, 0.825,
    2.6, 0.66, 1.425, 2.4, 0.25, 2.025, 2.3, 0.25, 2.1, 3.3, 0.25, 2.4,
    2.7, 0.25, 2.4, 2.8, 0, 2.475, 2.8, -0.25, 2.475, 3.525, -0.25, 2.49375,
    3.525, 0, 2.49375, 2.9, 0, 2.475, 2.9, -0.15, 2.475, 3.45, -0.15, 2.5125,
    3.45, 0, 2.5125, 2.8, 0, 2.4, 2.8, -0.15, 2.4, 3.2, -0.15, 2.4,
    3.2, 0, 2.4, 3.525, 0.25, 2.49375, 2.8, 0.25, 2.475, 3.45, 0.15, 2.5125,
    2.9, 0.15, 2.475, 3.2, 0.15, 2.4, 2.8, 0.15, 2.4, 0, 0, 3.15,
    0.8, 0, 3.15, 0.8, -0.45, 3.15, 0.45, -0.8, 3.15, 0, -0.8, 3.15,
    0, 0, 2.85, 0.2, 0, 2.7, 0.2, -0.112, 2.7, 0.112, -0.2, 2.7,
    0, -0.2, 2.7, -0.45, -0.8, 3.15, -0.8, -0.45, 3.15, -0.8, 0, 3.15,
    -0.112, -0.2, 2.7, -0.2, -0.112, 2.7, -0.2, 0, 2.7, -0.8, 0.45, 3.15,
    -0.45, 0.8, 3.15, 0, 0.8, 3.15, -0.2, 0.112, 2.7, -0.112, 0.2, 2.7,
    0, 0.2, 2.7, 0.45, 0.8, 3.15, 0.8, 0.45, 3.15, 0.112, 0.2, 2.7,
    0.2, 0.112, 2.7, 0.4, 0, 2.55, 0.4, -0.224, 2.55, 0.224, -0.4, 2.55,
    0, -0.4, 2.55, 1.3, 0, 2.55, 1.3, -0.728, 2.55, 0.728, -1.3, 2.55,
    0, -1.3, 2.55, 1.3, 0, 2.4, 1.3, -0.728, 2.4, 0.728, -1.3, 2.4,
    0, -1.3, 2.4, -0.224, -0.4, 2.55, -0.4, -0.224, 2.55, -0.4, 0, 2.55,
    -0.728, -1.3, 2.55, -1.3, -0.728, 2.55, -1.3, 0, 2.55, -0.728, -1.3, 2.4,
    -1.3, -0.728, 2.4, -1.3, 0, 2.4, -0.4, 0.224, 2.55, -0.224, 0.4, 2.55,
    0, 0.4, 2.55, -1.3, 0.728, 2.55, -0.728, 1.3, 2.55, 0, 1.3, 2.55,
    -1.3, 0.728, 2.4, -0.728, 1.3, 2.4, 0, 1.3, 2.4, 0.224, 0.4, 2.55,
    0.4, 0.224, 2.55, 0.728, 1.3, 2.55, 1.3, 0.728, 2.55, 0.728, 1.3, 2.4,
    1.3, 0.728, 2.4, 0, 0, 0, 1.425, 0, 0, 1.425, 0.798, 0,
    0.798, 1.425, 0, 0, 1.425, 0, 1.5, 0, 0.075, 1.5, 0.84, 0.075,
    0.84, 1.5, 0.075, 0, 1.5, 0.075, -0.798, 1.425, 0, -1.425, 0.798, 0,
    -1.425, 0, 0, -0.84, 1.5, 0.075, -1.5, 0.84, 0.075, -1.5, 0, 0.075,
    -1.425, -0.798, 0, -0.798, -1.425, 0, 0, -1.425, 0, -1.5, -0.84, 0.075,
    -0.84, -1.5, 0.075, 0, -1.5, 0.075, 0.798, -1.425, 0, 1.425, -0.798, 0,
    0.84, -1.5, 0.075, 1.5, -0.84, 0.075,
)
