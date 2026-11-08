"""ocean/apparitions.py: "not the robot from the movies, not a digital human, something new" (port of
eidoverse/sets/ocean/apparitions.js). Two figures rise out of the ocean of faces in the moon path and dissolve back:
  the movie ROBOT (ocean_robot.glb): a dark silhouette with a moonlit rim; it breaks up from the top down, every
    fragment's edge burning the faces' gold, and sinks as it goes; its lenses and lamps glow (red eyes, amber lights);
  the HUMAN OF LIGHT (ocean_human.glb): a figure of glowing points sampled from its surface plus a faint fresnel
    shell; it comes apart into rising sparks.
Both GLBs come from the model library (eidoverse/assets/models/); a missing file adds nothing.

    app = build_apparitions(base=(x, y, z) design three, yaw=..., parent=layout_empty)
        -> Apparitions: group, robot / human ({'holder', 'H'} or None), U (custom properties on the holders),
           update(u, t, key, frame), state(u, t), targets()
"""

from __future__ import annotations

import os
import re

import numpy as np

from .util import MODELS, rng, smooth

RIM, GOLD = (0.62, 0.72, 1.0), (1.0, 0.6, 0.24)
LENS, LAMP = (5.0, 0.4, 0.2), (2.5, 1.375, 0.375)               # (1, .08, .04) x 5 and (1, .55, .15) x 2.5
ROBOT_H, HUMAN_H = 10.5, 8.5


def robot_state(u, base_y=0.0):
    rise, diss = smooth((u - 15.0) / 0.65), smooth((u - 15.95) / 0.7)
    y = base_y - 1.3 - (1 - rise) * ROBOT_H * 0.75 - diss * 1.6       # knee-deep in the sea
    eyes = rise * (min(1.0, (u - 15.2) / 0.25) if u < 15.9 else 1.0)   # the eyes come on as it stands
    return {'visible': 14.95 < u < 16.8, 'y': y, 'rDiss': diss, 'rEyes': eyes}


def human_state(u, base_y=0.0):
    rise, diss = smooth((u - 16.45) / 0.5), smooth((u - 17.2) / 0.75)
    return {'visible': 16.4 < u < 18.3, 'y': base_y - 0.9 - (1 - rise) * HUMAN_H * 0.7, 'hDiss': diss}


def sample_surface(tris, n, seed=5):
    """area-weighted surface samples (sampleSurface): tris (M, 3, 3) -> (n, 3), the JS's rng draws in its order."""
    R = rng(seed)
    a, b, c = tris[:, 0], tris[:, 1], tris[:, 2]
    area = np.linalg.norm(np.cross(b - a, c - a), axis=1) * 0.5
    keep = area > 0
    a, b, c, area = a[keep], b[keep], c[keep], area[keep]
    cum = np.cumsum(area)
    total = cum[-1]
    out = np.empty((n, 3))
    for k in range(n):
        r = R() * total
        i = int(np.searchsorted(cum, r, side='left'))
        i = min(i, len(cum) - 1)
        u, v = R(), R()
        if u + v > 1:
            u, v = 1 - u, 1 - v
        out[k] = a[i] + (b[i] - a[i]) * u + (c[i] - a[i]) * v
    return out


_GLTF_TYPES = {5120: np.int8, 5121: np.uint8, 5122: np.int16, 5123: np.uint16, 5125: np.uint32, 5126: np.float32}
_GLTF_WIDTH = {'SCALAR': 1, 'VEC2': 2, 'VEC3': 3, 'VEC4': 4, 'MAT4': 16}


def glb_triangles(path):
    """three.js's view of a GLB's triangles: GLTFLoader's scene traversed as Object3D.traverse visits it (each node,
    its primitives, then its child nodes, depth first), the node transforms (matrix or TRS) applied, in three's axes
    (glTF's own, Y up) -> ((M, 3, 3) float64, the lowest y of every position: Box3.setFromObject's min.y).
    sampleSurface draws from exactly this list, so the same rng stream picks the same points. None when the file is
    missing or not a plain GLB (no Draco / sparse accessors)."""
    import json
    import struct
    if not os.path.isfile(path):
        return None
    b = open(path, 'rb').read()
    if b[:4] != b'glTF':
        return None
    jl = struct.unpack('<I', b[12:16])[0]
    gj = json.loads(b[20:20 + jl])
    off = 20 + jl
    bin_chunk = b[off + 8: off + 8 + struct.unpack('<I', b[off:off + 4])[0]] if off < len(b) else b''

    def accessor(i):
        a = gj['accessors'][i]
        if 'sparse' in a or 'bufferView' not in a:
            raise ValueError('sparse accessor')
        bv = gj['bufferViews'][a['bufferView']]
        dt = np.dtype(_GLTF_TYPES[a['componentType']])
        w = _GLTF_WIDTH[a['type']]
        start = bv.get('byteOffset', 0) + a.get('byteOffset', 0)
        stride = bv.get('byteStride', 0) or dt.itemsize * w
        n = a['count']
        raw = np.frombuffer(bin_chunk, np.uint8, count=stride * (n - 1) + dt.itemsize * w, offset=start)
        rows = np.lib.stride_tricks.as_strided(raw, shape=(n, dt.itemsize * w), strides=(stride, 1))
        return np.ascontiguousarray(rows).view(dt).reshape(n, w)

    def local(node):
        if 'matrix' in node:
            return np.array(node['matrix'], np.float64).reshape(4, 4).T       # glTF matrices are column-major
        t = np.array(node.get('translation', (0, 0, 0)), np.float64)
        x, y, z, w = node.get('rotation', (0, 0, 0, 1))
        s = np.array(node.get('scale', (1, 1, 1)), np.float64)
        R = np.array([[1 - 2 * (y * y + z * z), 2 * (x * y - z * w), 2 * (x * z + y * w)],
                      [2 * (x * y + z * w), 1 - 2 * (x * x + z * z), 2 * (y * z - x * w)],
                      [2 * (x * z - y * w), 2 * (y * z + x * w), 1 - 2 * (x * x + y * y)]])
        M = np.eye(4)
        M[:3, :3] = R * s[None, :]
        M[:3, 3] = t
        return M

    out, lows = [], []

    def visit(ni, parent):
        node = gj['nodes'][ni]
        M = parent @ local(node)
        if 'mesh' in node:
            for pr in gj['meshes'][node['mesh']]['primitives']:
                if pr.get('mode', 4) != 4 or 'KHR_draco_mesh_compression' in pr.get('extensions', {}):
                    raise ValueError('not plain triangles')
                P = accessor(pr['attributes']['POSITION']).astype(np.float64)
                P = P @ M[:3, :3].T + M[:3, 3]
                lows.append(P[:, 1].min())
                idx = accessor(pr['indices']).reshape(-1).astype(np.int64) if 'indices' in pr else np.arange(len(P))
                out.append(P[idx[: len(idx) // 3 * 3].reshape(-1, 3)])
        for c in node.get('children', ()):
            visit(c, M)

    try:
        for ni in gj['scenes'][gj.get('scene', 0)]['nodes']:
            visit(ni, np.eye(4))
    except (ValueError, KeyError):
        return None
    return (np.concatenate(out), float(min(lows))) if out else None


def _world_tris(objs):
    """every mesh triangle in world space (Blender axes)"""
    import bpy
    out = []
    dg = bpy.context.evaluated_depsgraph_get()
    for o in objs:
        if o.type != 'MESH':
            continue
        me = o.evaluated_get(dg).to_mesh()
        me.calc_loop_triangles()
        co = np.empty(len(me.vertices) * 3, np.float64)
        me.vertices.foreach_get('co', co)
        co = co.reshape(-1, 3)
        tri = np.empty(len(me.loop_triangles) * 3, np.int64)
        me.loop_triangles.foreach_get('vertices', tri)
        M = np.array(o.matrix_world)
        w = co @ M[:3, :3].T + M[:3, 3]
        out.append(w[tri.reshape(-1, 3)])
        o.evaluated_get(dg).to_mesh_clear()
    return np.concatenate(out) if out else np.zeros((0, 3, 3))


def _bbox(objs):
    import bpy
    from mathutils import Vector
    bpy.context.view_layer.update()
    pts = [o.matrix_world @ Vector(c) for o in objs if o.type == 'MESH' for c in o.bound_box]
    a = np.array([tuple(p) for p in pts])
    return a.min(0), a.max(0)


def _driven(nt, label, source, prop):
    from .house import _driven_value

    class _M:
        node_tree = nt
    return _driven_value(_M, label, source, prop)


def silhouette_material(name, glow, root):
    """the robot's silhouette family: unlit, a moonlit fresnel rim (or a glow for lenses / lamps), the top-down dissolve
    (a point goes when (1 - height) * 0.55 + noise * 0.45 < progress), each fragment's edge burning gold."""
    import bpy
    from ._nodes import NB, E, clear_material
    mat = bpy.data.materials.new(name)
    mat.use_nodes = True
    nt, out = clear_material(mat)
    nb = NB(nt, x0=-1600, y0=500, rows=30)
    U = {k: E(nb, _driven(nt, f'ocean_{k}', root, k).outputs[0]) for k in ('rDiss', 'rEyes', 'rBase', 'rTop')}
    geo = nb.node('ShaderNodeNewGeometry')
    N = nb.separate(geo.outputs['Normal'])
    V = nb.separate(geo.outputs['Incoming'])
    P = nb.separate(geo.outputs['Position'])
    fres = nb.pow(1.0 - nb.abs(nb.vdot(N, V)), 2.5)
    hN = nb.clamp((P[2] - U['rBase']) / (U['rTop'] - U['rBase']), 0.0, 1.0)
    tc = nb.node('ShaderNodeTexCoord')
    ob = nb.separate(tc.outputs['Object'])
    n = nb.noise3(ob[0] * 14.0, ob[2] * 14.0, -nb.s(ob[1]) * 14.0)   # mx_noise(positionLocal * 14) * .5 + .5, three axes
    key = (1.0 - hN) * 0.55 + n * 0.45
    thr = U['rDiss'] * 1.08
    edge = nb.smoothstep(thr + 0.09, thr, key) * nb.step(0.001, U['rDiss'])
    if glow is not None:
        base = tuple(g * U['rEyes'] for g in glow)
    else:
        base = tuple(nb.mix(d, r, fres * 0.55) for d, r in zip((0.012, 0.013, 0.02), RIM))
    col = tuple(base[i] + GOLD[i] * (edge * edge) * 9.0 for i in range(3))
    em = nb.node('ShaderNodeEmission')
    em.hide = False
    nb.link(col, em.inputs['Color'])
    tr = nb.node('ShaderNodeBsdfTransparent')
    mix = nb.node('ShaderNodeMixShader')
    mix.hide = False
    nb.link(nb.step(thr, key), mix.inputs['Fac'])                 # opacity step(thr, key), alpha test 0.5
    nt.links.new(tr.outputs[0], mix.inputs[1])
    nt.links.new(em.outputs[0], mix.inputs[2])
    nt.links.new(mix.outputs[0], out.inputs['Surface'])
    mat.use_backface_culling = False
    if hasattr(mat, 'surface_render_method'):
        mat.surface_render_method = 'DITHERED'
    return mat


def shell_material(name, root):
    from ._billboards import additive_emission
    from ._nodes import E

    def col(nb):
        geo = nb.node('ShaderNodeNewGeometry')
        N = nb.separate(geo.outputs['Normal'])
        V = nb.separate(geo.outputs['Incoming'])
        f = nb.pow(1.0 - nb.abs(nb.vdot(N, V)), 3.0)
        d = E(nb, _driven(nb.tree, 'ocean_hDiss', root, 'hDiss').outputs[0])
        k = (f * 0.9 + 0.02) * (1.0 - d)
        return tuple(c * k for c in (0.55, 0.85, 1.0))
    m = additive_emission(name, col)
    m.use_backface_culling = True
    return m


def points_material(name, root):
    from ._billboards import additive_emission
    from ._nodes import E

    def col(nb):
        q = nb.attr('corner', 'GEOMETRY', 'Vector')
        r = nb.attr('rnd', 'GEOMETRY', 'Vector')
        rw = nb.attr('rnd_w', 'GEOMETRY')
        t = E(nb, _driven(nb.tree, 'ocean_t', root, 't').outputs[0])
        d = E(nb, _driven(nb.tree, 'ocean_hDiss', root, 'hDiss').outputs[0])
        k = nb.exp((q[0] * q[0] + q[1] * q[1]) * -3.2)
        tw = nb.sin(t * (r[0] * 9.0 + 2.0) + r[1] * 6.28) * 0.25 + 0.75
        fade = 1.0 - nb.smoothstep(r[2] * 0.5 + 0.35, 1.0, d)
        kk = k * tw * fade * 0.75
        return tuple(nb.mix(a, b, rw) * kk for a, b in zip((0.55, 0.85, 1.0), (1.0, 0.95, 0.85)))
    return additive_emission(name, col)


def points_group(S):
    """the points' vertex stage: each point lifts and drifts outward as the figure dissolves, a little twinkle while it
    holds; camera-facing, size max(0.012 + 0.012 rnd.w, distance * 0.0018) in world units (the holder is scaled S)."""
    import bpy
    from ._nodes import NB, E, new_tree
    from ._billboards import billboard_offset
    name = f'ocean_human_points_{S:.4f}'
    if name in bpy.data.node_groups:
        return bpy.data.node_groups[name]
    tree, gi, go = new_tree(name, 'GeometryNodeTree', inputs=[('Geometry', 'NodeSocketGeometry'),
                            ('Time', 'NodeSocketFloat', 0.0), ('Dissolve', 'NodeSocketFloat', 0.0)],
                            outputs=[('Geometry', 'NodeSocketGeometry')])
    nb = NB(tree)
    cb = nb.attr('center', out='Vector')
    c = (cb[0], cb[2], -nb.s(cb[1]))                              # three local
    r = nb.attr('rnd', out='Vector')
    rw = nb.attr('rnd_w')
    q = nb.attr('corner', out='Vector')
    d, t = E(nb, gi.outputs['Dissolve']), E(nb, gi.outputs['Time'])
    ko = d * 1.6 * (r[0] + 0.3)
    up = d * d * (r[1] * 2.2 + 0.6)
    sway = nb.sin(t * 1.7 + r[2] * 6.28) * 0.01
    p3 = (c[0] + c[0] * ko + sway, c[1] + up, c[2] + c[2] * ko)
    p = billboard_offset(nb, (p3[0], -nb.s(p3[2]), p3[1]), (q[0], q[1]), rw * 0.012 + 0.012, 0.0018, local_scale=S)
    setp = nb.node('GeometryNodeSetPosition')
    setp.hide = False
    tree.links.new(gi.outputs['Geometry'], setp.inputs['Geometry'])
    nb.link(p, setp.inputs['Position'])
    tree.links.new(setp.outputs['Geometry'], go.inputs['Geometry'])
    return tree


class Apparitions:
    def __init__(self, **kw):
        self.__dict__.update(kw)

    def state(self, u, t):
        out = {'t': t}
        by = self.base[1]
        if self.robot:
            r = robot_state(u, by)
            out.update({'robot.visible': r['visible'], 'robot.z': r['y'], 'robot.rDiss': r['rDiss'], 'robot.rEyes': r['rEyes']})
            # rBase / rTop: the holder's world height (the dissolve's 0 at the feet .. 1 at the head)
            wz = self._world_z(self.robot['holder'], r['y'])
            out['robot.rBase'], out['robot.rTop'] = wz, wz + ROBOT_H
        if self.human:
            h = human_state(u, by)
            out.update({'human.visible': h['visible'], 'human.z': h['y'], 'human.hDiss': h['hDiss']})
        return out

    def _world_z(self, holder, y_design):
        from mathutils import Vector
        p = holder.parent.matrix_world @ Vector((holder.location.x, holder.location.y, y_design))
        return p.z

    def targets(self):
        m = {}
        if self.robot:
            h = self.robot['holder']
            m['robot.visible'] = ('visible', self.robot['objects'], None, 'CONSTANT')
            m['robot.z'] = (h, 'location', 'i2', 'LINEAR')
            for k in ('rDiss', 'rEyes', 'rBase', 'rTop'):
                m['robot.' + k] = (h, f'["{k}"]', None, 'LINEAR')
        if self.human:
            h = self.human['holder']
            m['human.visible'] = ('visible', self.human['objects'], None, 'CONSTANT')
            m['human.z'] = (h, 'location', 'i2', 'LINEAR')
            m['human.hDiss'] = (h, '["hDiss"]', None, 'LINEAR')
            m['t'] = (h, '["t"]', None, 'LINEAR')
        return m

    def update(self, u, t, key=None, frame=None):
        from . import _bl
        for k, v in self.state(u, t).items():
            tgt = self.targets().get(k)
            if tgt is None:
                continue
            idb, path, _n, _i = tgt
            if idb == 'visible':
                for o in path:
                    o.hide_render = o.hide_viewport = not v
                    if key:
                        o.keyframe_insert('hide_render', frame=frame)
                continue
            if path == 'location':
                idb.location.z = v
                if key:
                    idb.keyframe_insert('location', index=2, frame=frame)
            else:
                _bl.set_prop(idb, path[2:-2], v, key=key, frame=frame)


def build_apparitions(base=(0.0, 0.0, 0.0), yaw=0.0, dir_prefix=None, parent=None, collection=None):
    """buildApparitions(THREE, { dir, base, yaw }) -> Apparitions (robot / human None when their GLB is missing)."""
    import bpy
    from . import _bl
    from ._billboards import quad_arrays
    col = collection or bpy.context.scene.collection
    prefix = dir_prefix or os.path.join(MODELS, 'ocean_')
    group = _bl.empty('ocean:apparitions', parent=parent, collection=col, size=1.0)
    out = Apparitions(group=group, robot=None, human=None, base=base)
    base_bl = (base[0], -base[2], base[1])

    def holder_for(name):
        h = _bl.empty(name, parent=group, collection=col, size=1.0)
        h.location = base_bl
        h.rotation_euler = (0.0, 0.0, yaw)
        return h

    # ---------------------------------------------------------------- the robot
    root, objs = _bl.import_glb(prefix + 'robot.glb', 'ocean_robot_src', collection=col)
    if root is not None:
        lo, hi = _bbox(objs)
        S = ROBOT_H / max(0.1, hi[2] - lo[2])
        holder = holder_for('ocean_robot')
        for k, v in (('rDiss', 0.0), ('rEyes', 0.0), ('rBase', 0.0), ('rTop', 9.0)):
            holder[k] = v
        root.parent = holder
        root.location = (0.0, 0.0, -lo[2])                       # robot.position.y = -box.min.y
        holder.scale = (S, S, S)
        mats = {}
        for o in objs:
            if o.type != 'MESH':
                continue
            o.visible_shadow = False
            for i, m in enumerate(o.data.materials):
                nm = m.name if m else ''
                glow = LENS if re.search('lens', nm, re.I) else LAMP if re.search('lamp', nm, re.I) else None
                key = 'lens' if glow is LENS else 'lamp' if glow is LAMP else 'body'
                if key not in mats:
                    mats[key] = silhouette_material(f'ocean_robot_{key}', glow, holder)
                o.data.materials[i] = mats[key]
        out.robot = {'holder': holder, 'H': ROBOT_H, 'objects': [o for o in objs if o.type == 'MESH']}

    # ---------------------------------------------------------------- the human of light
    root, objs = _bl.import_glb(prefix + 'human.glb', 'ocean_human_src', collection=col)
    if root is not None:
        lo, hi = _bbox(objs)
        S = HUMAN_H / max(0.1, hi[2] - lo[2])
        root.location = (0.0, 0.0, -lo[2])
        holder = holder_for('ocean_human')
        holder['hDiss'] = 0.0
        holder['t'] = 0.0
        root.parent = holder
        holder.scale = (S, S, S)
        bpy.context.view_layer.update()
        shell = shell_material('ocean_human_shell', holder)
        meshes = [o for o in objs if o.type == 'MESH']
        for o in meshes:
            o.data.materials.clear()
            o.data.materials.append(shell)
            o.visible_shadow = False
        # points of light on its surface, holder-local: the film's own points (the GLB's triangles as three.js reads
        # them, shifted by -box.min.y as apparitions.js does, then sampled with the same rng(13) draws); Blender's
        # imported triangles only when the file is not a plain GLB
        g3 = glb_triangles(prefix + 'human.glb')
        if g3 is not None:
            pts3 = sample_surface(g3[0], 5200, 13)
            pts3[:, 1] -= g3[1]                                  # human.position.y = -box.min.y
            loc = np.stack([pts3[:, 0], -pts3[:, 2], pts3[:, 1]], 1)
        else:
            tris = _world_tris(meshes)
            pts = sample_surface(tris, 5200, 13)
            inv = np.array(holder.matrix_world.inverted())
            loc = pts @ inv[:3, :3].T + inv[:3, 3]
        R = rng(17)
        rnd = np.array([[R(), R(), R(), R()] for _ in range(len(loc))])
        idx, cor, qt = quad_arrays(len(loc))
        me = _bl.mesh_from_arrays('ocean_human_points', loc[idx], qt, smooth=False)
        _bl.add_point_attr(me, 'center', loc[idx], 'FLOAT_VECTOR')
        _bl.add_point_attr(me, 'corner', np.c_[cor, np.zeros(len(cor))], 'FLOAT_VECTOR')
        _bl.add_point_attr(me, 'rnd', rnd[idx, :3], 'FLOAT_VECTOR')
        _bl.add_point_attr(me, 'rnd_w', rnd[idx, 3])
        me.materials.append(points_material('ocean_human_points', holder))
        pob = bpy.data.objects.new('ocean_human_points', me)
        col.objects.link(pob)
        pob.parent = holder
        pob.visible_shadow = False
        mod = pob.modifiers.new('points', 'NODES')
        mod.node_group = points_group(S)
        _bl.drive_modifier_input(pob, mod, 'Time', holder, 't')
        _bl.drive_modifier_input(pob, mod, 'Dissolve', holder, 'hDiss')
        out.human = {'holder': holder, 'H': HUMAN_H, 'objects': meshes + [pob], 'points': pob, 'count': len(loc)}
    for a in (out.robot, out.human):
        if a:
            for o in a['objects']:
                o.hide_render = o.hide_viewport = True
    return out
