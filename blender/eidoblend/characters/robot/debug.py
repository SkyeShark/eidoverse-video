"""eidoblend.characters.robot.debug: RobotDebug (eidoverse/robot_debug.js), what the robot sees and knows, as keyed geometry.

    from eidoblend.characters.robot import RobotDebug
    dbg = RobotDebug(body)
    dbg.show_rays(True); dbg.show_map(True); dbg.show_path(True); dbg.show_landmarks(True)
    for f in ...:
        body.update(t, dt)
        dbg.update()                                  # after body.update, as the JS's renderFrame calls it
    rep = body.bake(f0=1)
    objs = dbg.build(rep)                             # the overlays on the film's frames (the bake's frame map)

The WebGPU helpers are line segments and a vertex-coloured grid rewritten each frame: the sensor cone (each ray from the
head to its hit, red; a miss to the full range, cyan; opacity 0.6), the occupancy grid as a 2.5D decal (one quad per cell
at its surface height + 2 cm: free green, blocked red, cliff yellow, hazard purple, unknown not drawn, each faded by its
confidence), the planned path (yellow, at 5 cm) and the landmarks (cyan balls at 0.5 m). In a film every frame must render
alone, so update() records what each helper shows at each frame, and build() makes ONE object per helper holding every
state with the frames it is shown on ([f0, f1) as attributes); a Geometry Nodes modifier keeps only the state whose span
holds the scene's current frame (Scene Time), then draws it: rays and path as thin tubes, cells as quads, landmarks as
spheres. Their materials are unlit (emission, blended alpha, no shadow), as the JS's basic materials. showX(False) after
build hides that helper (the object's hide_render); none of them is something the sensors can see (they are built after
the run). The rays start at the head where the BAKED body has it (the bake's map from film frames to the run's frames)
and end where each really ended (its hit, or the full range), so every hit lies on the surface it found.
"""

import math

import bpy
import numpy as np

STATE_COLOURS = {1: (40, 200, 80, 140), 2: (220, 40, 60, 220), 3: (220, 180, 0, 220), 4: (180, 60, 220, 220)}
HIT, MISS = (1.0, 0.2, 0.2), (0.0, 0.9, 1.0)


def _lin(c):
    return tuple((ch / 255.0) ** 2.2 for ch in c)


class RobotDebug:
    def __init__(self, body, scene=None, opts=None):
        self.body = body
        self.scene = scene or bpy.context.scene
        self.opts = opts or {}
        self._enabled = {'rays': False, 'map': False, 'path': False, 'landmarks': False}
        self._objects = {}
        self.rays = []           # (run frame, reading)
        self.maps = []           # (run frame, cells copy, surface copy)
        self.path_states = []    # (run frame, path or None)
        self.marks = []          # (run frame, [(name, x, y)])
        self._last_reading = None
        self._last_obs = None
        self._last_path = 'none'
        self._last_marks = None

    # ------------------------------------------------------------------------------------------------- toggles
    def _show(self, k, on):
        self._enabled[k] = bool(on)
        ob = self._objects.get(k)
        if ob is not None:
            ob.hide_render = ob.hide_viewport = not on

    def show_rays(self, on):
        self._show('rays', on)

    def show_map(self, on):
        self._show('map', on)

    def show_path(self, on):
        self._show('path', on)

    def show_landmarks(self, on):
        self._show('landmarks', on)

    # ------------------------------------------------------------------------------------------------- per frame
    def update(self):
        """record what each enabled helper shows at this frame (after body.update)"""
        b, i = self.body, self.body.frame_count - 1
        if self._enabled['rays'] and b.last_reading is not None and b.last_reading is not self._last_reading:
            self._last_reading = b.last_reading
            self.rays.append((i, b.last_reading))
        m = b.memory
        if self._enabled['map'] and m.observation_count != self._last_obs:
            self._last_obs = m.observation_count
            self.maps.append((i, m.cells.copy(), m.surface_z.copy()))
        if self._enabled['path']:
            p = b._current_path
            key = None if not p or len(p) < 2 else tuple((round(q['x'], 4), round(q['y'], 4)) for q in p)
            if key != self._last_path:
                self._last_path = key
                self.path_states.append((i, [dict(q) for q in p] if key else None))
        if self._enabled['landmarks']:
            lms = tuple((lm['name'], lm['x'], lm['y']) for lm in m.list_landmarks())
            if lms != self._last_marks:
                self._last_marks = lms
                self.marks.append((i, list(lms)))

    # ------------------------------------------------------------------------------------------------- the build
    def build(self, rep=None, f0=1, film_end=None, collection=None, ray_radius=0.003, path_radius=0.012):
        """the recorded states as keyed geometry on the film's frames. rep: the bake's report (its map from film frames to
        the run's frames, and its frames for the head's place); without it a run frame i shows at film frame f0 + i"""
        col = collection or self.scene.collection
        frames = rep['_frames'] if rep else None
        sim_of = rep['map'] if rep else None
        if sim_of:
            film_of = {}
            for j, i in enumerate(sim_of):
                film_of.setdefault(i, rep['frames'][0] + j)
            last = rep['frames'][1] + 1
        else:
            film_of, last = None, None
        end = film_end or last or (f0 + self.body.frame_count)

        def film(i):
            if film_of is None:
                return f0 + i
            while i not in film_of and i > 0:
                i -= 1
            return film_of.get(i, f0)
        heads = {}
        if frames is not None:
            rig = self.body.controller.char_ctrl.rig
            for fr in frames:
                p, W = rig.bone_world(fr, 'head')
                heads[fr['f']] = p
        objs = {}
        if self.rays:
            objs['rays'] = self._build_rays(film, end, heads, col, ray_radius)
        if self.maps:
            objs['map'] = self._build_map(film, end, col)
        if self.path_states:
            objs['path'] = self._build_path(film, end, col, path_radius)
        if self.marks:
            objs['landmarks'] = self._build_marks(film, end, col)
        for k, ob in objs.items():
            if ob is None:
                continue
            self._objects[k] = ob
            ob.hide_render = ob.hide_viewport = not self._enabled[k]
        return objs

    def _spans(self, states, film, end):
        out = []
        for n, st in enumerate(states):
            a = film(st[0])
            b = film(states[n + 1][0]) if n + 1 < len(states) else end
            if b > a:
                out.append((a, b, st))
        return out

    def _build_rays(self, film, end, heads, col, radius):
        P, F0, F1, RGB = [], [], [], []
        for a, b, (i, reading) in self._spans(self.rays, film, end):
            o = heads.get(a, reading['origin'])
            for h in reading['hits']:
                # from the head the film shows to where the ray really ended (a hit on its surface, a miss at the full
                # range): the JS draws origin -> point, and the keyed head can stand a little off the live one
                P += [tuple(o), tuple(h['point'])]
                c = HIT if h['hit'] else MISS
                RGB += [c, c]
                F0 += [a, a]
                F1 += [b, b]
        n = len(P)
        edges = [(2 * k, 2 * k + 1) for k in range(n // 2)]
        ob = _mesh_object('robot_debug_rays', P, edges, [], col)
        _attrs(ob.data, 'POINT', {'f0': F0, 'f1': F1}, {'rgb': [c + (1.0,) for c in RGB]})
        _timeline_nodes(ob, 'POINT', 'tube', radius, _overlay_material('robot_debug_rays', None, 0.6, 2.0))
        return ob

    def _build_map(self, film, end, col):
        m = self.body.memory
        n = m.n
        spans = self._spans(self.maps, film, end)
        if not spans:
            return None
        cells = np.stack([st[1] for _a, _b, st in spans])          # (S, n, n)
        surf = np.stack([st[2] for _a, _b, st in spans])
        state = (cells & 0x0F).astype(np.int16)
        conf = (cells >> 4).astype(np.int16)
        alpha_lvl = np.minimum(conf + 1, 8)                          # (conf + 1) / 8, capped at 1: eight levels
        code = np.where(state > 0, state * 16 + alpha_lvl, 0)
        zq = np.where(np.isnan(surf), -9999, np.round(surf * 100)).astype(np.int32)
        A = [a for a, _b, _s in spans]
        B = [b for _a, b, _s in spans]
        verts, faces, F0, F1, RGB, AL = [], [], [], [], [], []
        half = m.cell_size * 0.49
        ys, xs = np.nonzero((code > 0).any(axis=0))
        for cy, cx in zip(ys, xs):
            seq, zs = code[:, cy, cx], zq[:, cy, cx]
            k = 0
            S = len(seq)
            while k < S:
                if seq[k] == 0:
                    k += 1
                    continue
                j = k
                while j + 1 < S and seq[j + 1] == seq[k] and zs[j + 1] == zs[k]:
                    j += 1
                s_, lvl = int(seq[k]) // 16, int(seq[k]) % 16
                c = STATE_COLOURS.get(s_, (0, 0, 0, 0))
                wx, wy = m.cell_to_world(int(cx), int(cy))
                z = (0.0 if zs[k] == -9999 else zs[k] / 100.0) + 0.02
                b0 = len(verts)
                verts += [(wx - half, wy - half, z), (wx + half, wy - half, z), (wx + half, wy + half, z),
                          (wx - half, wy + half, z)]
                faces.append((b0, b0 + 1, b0 + 2, b0 + 3))
                F0.append(A[k])
                F1.append(B[j])
                RGB.append(_lin(c[:3]) + (1.0,))
                AL.append((c[3] / 255.0) * min(1.0, lvl / 8.0))
                k = j + 1
        ob = _mesh_object('robot_debug_map', verts, [], faces, col)
        _attrs(ob.data, 'FACE', {'f0': F0, 'f1': F1, 'a': AL}, {'rgb': RGB})
        _timeline_nodes(ob, 'FACE', None, 0.0, _overlay_material('robot_debug_map', None, None, 1.0))
        return ob

    def _build_path(self, film, end, col, radius):
        P, E, F0, F1 = [], [], [], []
        for a, b, (i, path) in self._spans(self.path_states, film, end):
            if not path:
                continue
            b0 = len(P)
            for q in path:
                z = 0.0 if (q.get('z') is None or math.isnan(q['z'])) else q['z']
                P.append((q['x'], q['y'], z + 0.05))
                F0.append(a)
                F1.append(b)
            E += [(b0 + k, b0 + k + 1) for k in range(len(path) - 1)]
        if not P:
            return None
        ob = _mesh_object('robot_debug_path', P, E, [], col)
        _attrs(ob.data, 'POINT', {'f0': F0, 'f1': F1}, {})
        _timeline_nodes(ob, 'POINT', 'tube', radius, _overlay_material('robot_debug_path', _lin((255, 255, 0)), 0.85, 2.0))
        return ob

    def _build_marks(self, film, end, col):
        P, F0, F1 = [], [], []
        for a, b, (i, lms) in self._spans(self.marks, film, end):
            for _name, x, y in lms:
                P.append((x, y, 0.5))
                F0.append(a)
                F1.append(b)
        if not P:
            return None
        ob = _mesh_object('robot_debug_landmarks', P, [], [], col)
        _attrs(ob.data, 'POINT', {'f0': F0, 'f1': F1}, {})
        _timeline_nodes(ob, 'POINT', 'sphere', 0.15, _overlay_material('robot_debug_landmarks', _lin((0, 221, 255)), 0.9, 2.0))
        return ob


# ------------------------------------------------------------------------------------------------------------ helpers
def _mesh_object(name, verts, edges, faces, col):
    me = bpy.data.meshes.new(name)
    me.from_pydata([tuple(v) for v in verts], edges, faces)
    me.update()
    ob = bpy.data.objects.new(name, me)
    col.objects.link(ob)
    ob.visible_shadow = False
    ob['no_motion_check'] = True
    ob['no_support_check'] = True
    ob['no_walkable'] = True
    return ob


def _attrs(me, domain, floats, colours):
    for k, vals in floats.items():
        a = me.attributes.new(k, 'FLOAT', domain)
        a.data.foreach_set('value', np.asarray(vals, dtype=np.float32))
    for k, vals in colours.items():
        a = me.attributes.new(k, 'FLOAT_COLOR', domain)
        a.data.foreach_set('color', np.asarray(vals, dtype=np.float32).ravel())


def _timeline_nodes(ob, domain, draw, radius, mat):
    """a Geometry Nodes modifier: delete every element whose [f0, f1) does not hold the current frame, then draw what is
    left (tubes along its edges, spheres on its points, or the faces as they are) with `mat`"""
    ng = bpy.data.node_groups.new(ob.name + '_timeline', 'GeometryNodeTree')
    ng.interface.new_socket(name='Geometry', in_out='INPUT', socket_type='NodeSocketGeometry')
    ng.interface.new_socket(name='Geometry', in_out='OUTPUT', socket_type='NodeSocketGeometry')
    N, L = ng.nodes, ng.links
    gi, go = N.new('NodeGroupInput'), N.new('NodeGroupOutput')
    tm = N.new('GeometryNodeInputSceneTime')
    a0 = N.new('GeometryNodeInputNamedAttribute')
    a0.data_type = 'FLOAT'
    a0.inputs['Name'].default_value = 'f0'
    a1 = N.new('GeometryNodeInputNamedAttribute')
    a1.data_type = 'FLOAT'
    a1.inputs['Name'].default_value = 'f1'
    c0 = N.new('FunctionNodeCompare')
    c0.data_type, c0.operation = 'FLOAT', 'LESS_EQUAL'
    L.new(a0.outputs['Attribute'], c0.inputs[0])
    L.new(tm.outputs['Frame'], c0.inputs[1])
    c1 = N.new('FunctionNodeCompare')
    c1.data_type, c1.operation = 'FLOAT', 'LESS_THAN'
    L.new(tm.outputs['Frame'], c1.inputs[0])
    L.new(a1.outputs['Attribute'], c1.inputs[1])
    nand = N.new('FunctionNodeBooleanMath')
    nand.operation = 'NAND'
    L.new(c0.outputs['Result'], nand.inputs[0])
    L.new(c1.outputs['Result'], nand.inputs[1])
    dl = N.new('GeometryNodeDeleteGeometry')
    dl.domain = domain
    L.new(gi.outputs['Geometry'], dl.inputs['Geometry'])
    L.new(nand.outputs['Boolean'], dl.inputs['Selection'])
    geo = dl.outputs['Geometry']
    if draw == 'tube':
        m2c = N.new('GeometryNodeMeshToCurve')
        L.new(geo, m2c.inputs['Mesh'])
        circ = N.new('GeometryNodeCurvePrimitiveCircle')
        circ.inputs['Resolution'].default_value = 6
        circ.inputs['Radius'].default_value = radius
        c2m = N.new('GeometryNodeCurveToMesh')
        L.new(m2c.outputs['Curve'], c2m.inputs['Curve'])
        L.new(circ.outputs['Curve'], c2m.inputs['Profile Curve'])
        geo = c2m.outputs['Mesh']
    elif draw == 'sphere':
        sph = N.new('GeometryNodeMeshUVSphere')
        sph.inputs['Segments'].default_value = 16
        sph.inputs['Rings'].default_value = 8
        sph.inputs['Radius'].default_value = radius
        iop = N.new('GeometryNodeInstanceOnPoints')
        L.new(geo, iop.inputs['Points'])
        L.new(sph.outputs['Mesh'], iop.inputs['Instance'])
        rl = N.new('GeometryNodeRealizeInstances')
        L.new(iop.outputs['Instances'], rl.inputs['Geometry'])
        geo = rl.outputs['Geometry']
    sm = N.new('GeometryNodeSetMaterial')
    sm.inputs['Material'].default_value = mat
    L.new(geo, sm.inputs['Geometry'])
    L.new(sm.outputs['Geometry'], go.inputs['Geometry'])
    mod = ob.modifiers.new('timeline', 'NODES')
    mod.node_group = ng
    return mod


def _overlay_material(name, colour, opacity, strength):
    """unlit and see-through, as three's Line/MeshBasicMaterial: emission of `colour` (or the 'rgb' attribute), alpha
    `opacity` (or the 'a' attribute), blended"""
    mat = bpy.data.materials.new(name)
    mat.use_nodes = True
    nt = mat.node_tree
    for n in list(nt.nodes):
        nt.nodes.remove(n)
    out = nt.nodes.new('ShaderNodeOutputMaterial')
    em = nt.nodes.new('ShaderNodeEmission')
    em.inputs['Strength'].default_value = strength
    if colour is None:
        at = nt.nodes.new('ShaderNodeAttribute')
        at.attribute_type = 'GEOMETRY'
        at.attribute_name = 'rgb'
        nt.links.new(at.outputs['Color'], em.inputs['Color'])
    else:
        em.inputs['Color'].default_value = tuple(colour) + (1.0,)
    tr = nt.nodes.new('ShaderNodeBsdfTransparent')
    mix = nt.nodes.new('ShaderNodeMixShader')
    if opacity is None:
        aa = nt.nodes.new('ShaderNodeAttribute')
        aa.attribute_type = 'GEOMETRY'
        aa.attribute_name = 'a'
        nt.links.new(aa.outputs['Fac'], mix.inputs['Fac'])
    else:
        mix.inputs['Fac'].default_value = opacity
    nt.links.new(tr.outputs['BSDF'], mix.inputs[1])
    nt.links.new(em.outputs['Emission'], mix.inputs[2])
    nt.links.new(mix.outputs['Shader'], out.inputs['Surface'])
    try:
        mat.surface_render_method = 'BLENDED'
    except (AttributeError, TypeError):
        mat.blend_method = 'BLEND'
    mat.use_backface_culling = False
    return mat
