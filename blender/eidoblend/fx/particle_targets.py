"""Morph targets from anything: the infrastructure under make_particle_morph (eidoblend.fx.particle_morph).

The WebGPU engine's targets were point lists: ParticleMorph.fromMesh, fromText, neuralNet, neuronGraph, fromPoints. Those
generators are ported as they are in particle_morph.py. This module makes ANY 3D thing a target, with the colours of
the thing, so a cloud can dissolve one model and reform as another and look like each of them:

    from eidoblend.fx.particle_targets import target, from_object, from_file, from_image, shapes

    body  = from_object(vrm, 60000, live=True)              # a VRM / rig sampled in its live pose, every frame
    stool = from_file('polyhaven:wooden_stool_01', 60000, fit_height=1.4, at=(0, 0, 0.9))
    sign  = from_image('eidoverse/assets/vrms/claude_preview.jpg', 60000, width=2.5, mode='any')
    word  = target('text:CLAUDE', 60000, width=3.2, at=(0, 0, 1.2))
    m = make_particle_morph(targets=[body, stool, 'neural_net', word], count=60000)   # or the specs directly

A Target is points (m, 3) in Blender world coordinates, float32, with optional colours (m, 3) linear RGB and an
optional LIVE binding: per point, three vertex indices and barycentric weights into the joined evaluated meshes of a
set of objects (plus a jitter and a matrix). The morph's Geometry Nodes graph samples a live binding at every frame
(Object Info + Sample Index), so a walking, skinned character dissolves from the pose it has on that frame and a
reform lands on the pose it has then. A static Target is a snapshot.

Sources
  from_object      meshes (modifiers, shape keys, armatures evaluated), curves, text objects, surfaces, metaballs,
                   Geometry Nodes output (meshes, instances, point clouds), instancers (collection instances,
                   particle systems), whole collections, a VRMHandle, or a list of any of these.
                   mode 'surface' (area-weighted, the default), 'vertices' (the engine's vertex stride), 'volume'
                   (inside a closed mesh), 'edges' (along curves and wires).
  from_file        .glb .gltf .fbx .obj (harness.assets.import_model), .vrm (characters.load_vrm), .ply .stl .usd*
                   .abc .blend, .vdb (a volume), images, .npy .xyz .csv .txt (point arrays), 'polyhaven:<id>' (the
                   shared model library, fetched once by fetch_model.py), 'model:<name>' (the repo's own models in
                   eidoverse/assets/models, by name or a unique part of it), 'vrm:<name>', 'asset:<path under
                   eidoverse/assets>'. clip= plays an animated model's own clip (a VRM's VRMA slot) so live=True
                   follows it.
  from_image       an image or a path: alpha (a silhouette), luma, dark (ink on paper), any, edges; colours from the
                   pixels.
  from_silhouette  a model flattened to its outline from a view axis (a cut-out sign of the model), in its colours.
  from_point_cloud a POINTCLOUD object, a vertex-only mesh, a .ply / .npy / .xyz / .csv file or an (m, 3|6) array.
  from_volume      a Volume object or a .vdb file: points inside the density above a threshold (Geometry Nodes'
                   Distribute Points in Volume), coloured by density.
  shapes           the shapes the films hand-rolled for fromPoints: sphere, scatter, galaxy, ring, torus, helix,
                   spiral, disc, lattice, line, cube.
  target(spec)     one call for all of the above: an object, a collection, a VRMHandle, an image, an array, a Target,
                   'text:...', 'ascii:...', 'banner:...', 'neural_net', 'neuron_graph', a shape name, a file path,
                   'polyhaven:<id>', 'vrm:<name>', 'asset:<path>', or a dict {'text': 'HI', 'width': 5, ...}.

Colours. Each sampled point takes the colour of its material where it lies: the Principled BSDF's Base Color (its
image texture sampled at the point's UV, through a multiply tint if there is one, else its value), the VRM add-on's
MToon base colour and texture when MToon is enabled, a Diffuse / Emission / Toon colour, a colour attribute, plus the
material's emission. Alpha-cut texels (alpha < 0.5) get no points. Byte sRGB textures are linearised; textures are read
at most 1024 px across (enough for particles). A target without colours takes the morph's color / color2.

Equal counts. Every target is resampled to the cloud's count: the engine's resampleToN (cycle with a 1 cm jitter when
upsampling, stride when downsampling) for point lists; samplers draw exactly the count asked for. match_centroids moves
static targets so their centroids coincide (the engine's advice: "share centroids if a jump between A and B is not
wanted"); pair() orders points so particle i of one target goes to a nearby part of the next.
"""

from __future__ import annotations

import math
import os
from contextlib import contextmanager

import numpy as np

from ._util import srgb_to_linear

# ---------------------------------------------------------------------------------------------------- Target ---


class LiveBinding:
    """A live target's binding: per point three vertex indices (into the joined evaluated meshes of `objects`, in
    order) with barycentric weights, a jitter (Blender axes) and a 4x4 matrix applied after. `counts` are the
    objects' evaluated vertex counts when sampled (the morph graph needs them to stay fixed: an armature or shape keys
    keep them, a topology-changing modifier does not)."""

    __slots__ = ('objects', 'counts', 'idx', 'w', 'jitter', 'matrix')

    def __init__(self, objects, counts, idx, w, jitter=None, matrix=None):
        self.objects = list(objects)
        self.counts = [int(c) for c in counts]
        self.idx = np.asarray(idx, dtype=np.int64).reshape(-1, 3)
        self.w = np.asarray(w, dtype=np.float32).reshape(-1, 3)
        n = len(self.idx)
        self.jitter = (np.zeros((n, 3), np.float32) if jitter is None
                       else np.asarray(jitter, dtype=np.float32).reshape(-1, 3))
        self.matrix = np.eye(4) if matrix is None else np.asarray(matrix, dtype=np.float64).reshape(4, 4)

    def take(self, j, extra_jitter=None):
        jit = self.jitter[j].astype(np.float64)
        if extra_jitter is not None:
            jit = jit + extra_jitter
        return LiveBinding(self.objects, self.counts, self.idx[j], self.w[j], jit.astype(np.float32), self.matrix)

    def points(self, frame=None):
        """The binding's points at `frame` (default: the current frame), evaluated on the CPU as the graph does (a
        hidden object is made evaluable for the read: hidden ones keep their last evaluation otherwise)."""
        import bpy
        sc = bpy.context.scene
        f0 = sc.frame_current
        moved = frame is not None and int(frame) != f0
        try:
            if moved:
                sc.frame_set(int(frame))       # first: it re-applies keyed visibility, which the unhiding then lifts
            with _evaluable(self.objects):
                dg = bpy.context.evaluated_depsgraph_get()
                allv = []
                for o, c in zip(self.objects, self.counts):
                    v = _mesh_world_vertices(o, dg)
                    if len(v) != c:
                        raise RuntimeError(f'[particle_targets] live target: {o.name} has {len(v)} vertices now, '
                                           f'{c} when sampled')
                    allv.append(v)
        finally:
            if moved:
                sc.frame_set(f0)
        V = np.concatenate(allv, axis=0) if allv else np.zeros((1, 3))
        p = (V[self.idx] * self.w[..., None]).sum(1) + self.jitter
        M = self.matrix
        return (p @ M[:3, :3].T + M[:3, 3]).astype(np.float32)


class Target:
    """A morph target: points (m, 3) float32 in Blender world coordinates, colours (m, 3) linear RGB or None, a
    LiveBinding or None, a name, and the source objects it came from (`source`, e.g. an imported model, kept hidden).

    np.asarray(target) gives its points (a live target's at the current frame). Transforms return new Targets:
    t + (0, 0, 1) and t.translated(v), t * 2 and t.scaled(s, about), t.rotated(euler_xyz_radians, about),
    t.at(point, anchor='centroid'|'base'|'origin'), t.fit(height=, width=, size=), t.flattened(axis), t.tinted(c),
    t.with_colors(rgb_or_None). A live target transforms through its matrix (applied in the graph every frame)."""

    __slots__ = ('points', 'colors', 'live', 'name', 'source')

    def __init__(self, points, colors=None, live=None, name='', source=None):
        self.points = np.asarray(points, dtype=np.float32).reshape(-1, 3)
        self.colors = None if colors is None else np.asarray(colors, dtype=np.float32).reshape(-1, 3)
        self.live = live
        self.name = name
        self.source = source

    # ---------------------------------------------------------------------------------------------- basics
    def __len__(self):
        return len(self.live.idx) if self.live is not None else len(self.points)

    @property
    def count(self):
        return len(self)

    def current_points(self, frame=None):
        return self.live.points(frame) if self.live is not None else self.points

    def __array__(self, dtype=None, copy=None):
        p = self.current_points()
        return p.astype(dtype) if dtype is not None else p

    def __repr__(self):
        k = 'live' if self.live is not None else 'static'
        c = 'colours' if self.colors is not None else 'no colours'
        return f'<Target {self.name or "?"} {len(self)} points, {k}, {c}>'

    def copy(self, **kw):
        d = dict(points=self.points.copy(), colors=None if self.colors is None else self.colors.copy(),
                 live=self.live, name=self.name, source=self.source)
        d.update(kw)
        return Target(**d)

    def centroid(self, frame=None):
        return self.current_points(frame).astype(np.float64).mean(0)

    def bounds(self, frame=None):
        p = self.current_points(frame)
        return p.min(0).astype(np.float64), p.max(0).astype(np.float64)

    # ---------------------------------------------------------------------------------------------- transforms
    def transformed(self, M):
        """Apply a 4x4 matrix (numpy or mathutils)."""
        M = np.array(M, dtype=np.float64).reshape(4, 4)
        if self.live is not None:
            lb = LiveBinding(self.live.objects, self.live.counts, self.live.idx, self.live.w, self.live.jitter,
                             M @ self.live.matrix)
            return self.copy(live=lb, points=(self.points @ M[:3, :3].T + M[:3, 3]).astype(np.float32))
        return self.copy(points=(self.points.astype(np.float64) @ M[:3, :3].T + M[:3, 3]).astype(np.float32))

    def translated(self, v):
        M = np.eye(4)
        M[:3, 3] = np.asarray(v, dtype=np.float64).reshape(3)
        return self.transformed(M)

    def __add__(self, v):
        return self.translated(v)

    def __sub__(self, v):
        return self.translated(-np.asarray(v, dtype=np.float64))

    def scaled(self, s, about='centroid'):
        c = self._pivot(about)
        S = np.diag([*(np.broadcast_to(np.asarray(s, dtype=np.float64), (3,))), 1.0])
        return self.transformed(_about(S, c))

    def __mul__(self, s):
        return self.scaled(s, about='origin')

    def rotated(self, euler, about='centroid'):
        """Rotate by Euler XYZ angles in radians (Blender's convention) about the centroid, the origin or a point."""
        from mathutils import Euler
        R = np.eye(4)
        R[:3, :3] = np.array(Euler(tuple(float(a) for a in euler), 'XYZ').to_matrix())
        return self.transformed(_about(R, self._pivot(about)))

    def at(self, point, anchor='centroid'):
        """Move so the anchor sits at `point`: 'centroid', 'base' (the bottom centre of the bounds) or 'center'
        (the bounds' centre)."""
        lo, hi = self.bounds()
        if anchor == 'centroid':
            a = self.centroid()
        elif anchor == 'base':
            a = np.array([(lo[0] + hi[0]) / 2, (lo[1] + hi[1]) / 2, lo[2]])
        elif anchor == 'center':
            a = (lo + hi) / 2
        else:
            raise ValueError(f"[particle_targets] anchor {anchor!r}: 'centroid', 'base' or 'center'")
        return self.translated(np.asarray(point, dtype=np.float64) - a)

    def fit(self, height=None, width=None, size=None, about='centroid'):
        """Scale uniformly so the bounds' height (Z), width (X) or largest side is the given length."""
        lo, hi = self.bounds()
        ext = hi - lo
        cur, want = (ext[2], height) if height is not None else (ext[0], width) if width is not None else \
            (ext.max(), size)
        if want is None or cur <= 0:
            return self
        return self.scaled(float(want) / float(cur), about=about)

    def flattened(self, axis='y', at=None):
        """Squash onto the plane through the centroid (or `at`) normal to axis 'x' | 'y' | 'z' (a static copy)."""
        k = 'xyz'.index(axis.lower().lstrip('-+'))
        p = self.current_points().copy()
        p[:, k] = float(self.centroid()[k] if at is None else at)
        return Target(p, self.colors, None, self.name + ':flat', self.source)

    def tinted(self, c):
        """Every point one colour (an engine colour: '#rrggbb', 0xrrggbb, or a linear triple)."""
        from ._util import color
        rgb = np.asarray(color(c), dtype=np.float32)
        return self.copy(colors=np.broadcast_to(rgb, (len(self), 3)).copy())

    def with_colors(self, colors):
        return self.copy(colors=colors)

    def _pivot(self, about):
        if isinstance(about, str):
            return np.zeros(3) if about == 'origin' else self.centroid()
        return np.asarray(about, dtype=np.float64)

    # ---------------------------------------------------------------------------------------------- counts
    def resample(self, n, random=None, seed=1):
        """Exactly n points, the engine's resampleToN: cycle with a +-1 cm jitter when upsampling (three's axes, so
        the stream matches the engine's), stride when downsampling. Colours and live bindings follow their points.
        random: a JSRandom-like stream (.take(k)); default a mulberry32 stream from seed."""
        from .particle_morph import JSRandom, _plan
        from ._util import from_three
        rnd = random if random is not None else JSRandom(seed)
        n = int(n)
        m = len(self)
        if m == 0:
            return Target(np.zeros((n, 3), np.float32), None, None, self.name, self.source)
        j, jit3 = _plan(m, n, rnd)
        jit = from_three(jit3)
        cols = None if self.colors is None else self.colors[j]
        if self.live is not None:
            # the graph adds a binding's jitter BEFORE its matrix: a world-space jitter goes in through the inverse
            M3 = self.live.matrix[:3, :3]
            lb = self.live.take(j, jit if np.allclose(M3, np.eye(3)) else jit @ np.linalg.inv(M3).T)
            return Target(self.points[j] + jit.astype(np.float32), cols, lb, self.name, self.source)
        return Target((self.points[j].astype(np.float64) + jit).astype(np.float32), cols, None, self.name, self.source)

    def take(self, j):
        j = np.asarray(j)
        return Target(self.points[j], None if self.colors is None else self.colors[j],
                      None if self.live is None else self.live.take(j), self.name, self.source)


def _about(M, c):
    T, Ti = np.eye(4), np.eye(4)
    T[:3, 3], Ti[:3, 3] = c, -np.asarray(c)
    return T @ M @ Ti


def as_target(x, name=''):
    """A Target from a Target, an (m, 3) array, a flat array of 3 m values or a list of [x, y, z]."""
    if isinstance(x, Target):
        return x
    return Target(np.asarray(x, dtype=np.float32).reshape(-1, 3), name=name)


# ------------------------------------------------------------------------------------------ pairing, centroids ---

def match_centroids(targets, ref=0, frame=None, point=None):
    """Move every static target so its centroid sits on the reference target's centroid (at `frame` for a live
    reference) or on `point`. Live targets stay where their objects are. Returns the new list."""
    if point is None:
        point = targets[ref].centroid(frame) if isinstance(targets[ref], Target) else np.asarray(targets[ref]).mean(0)
    out = []
    for t in targets:
        if isinstance(t, Target) and t.live is not None:
            out.append(t)
        else:
            t = as_target(t)
            out.append(t.at(point, 'centroid'))
    return out


def _morton(p, bits=10):
    lo, hi = p.min(0), p.max(0)
    q = ((p - lo) / np.maximum(hi - lo, 1e-9) * ((1 << bits) - 1)).astype(np.uint64)
    code = np.zeros(len(p), dtype=np.uint64)
    for b in range(bits):
        for k in range(3):
            code |= ((q[:, k] >> np.uint64(b)) & np.uint64(1)) << np.uint64(3 * b + k)
    return code


def pair(t, by='index', axis=None, seed=1):
    """Order a target's points so the same particle index lands on corresponding parts of every target ordered the
    same way: 'index' (as sampled: the engine's random pairing, the swirl of crossing paths), 'height' (top goes to
    top), 'axis' (along a direction), 'space' (a Morton curve through the bounds: nearby goes to nearby, a cleaner
    reform), 'random'."""
    t = as_target(t)
    if by == 'index':
        return t
    p = t.current_points().astype(np.float64)
    if by == 'height':
        order = np.argsort(-p[:, 2], kind='stable')
    elif by == 'axis':
        order = np.argsort(p @ np.asarray(axis, dtype=np.float64), kind='stable')
    elif by == 'space':
        order = np.argsort(_morton(p), kind='stable')
    elif by == 'random':
        order = np.random.default_rng(seed).permutation(len(p))
    else:
        raise ValueError(f"[particle_targets] pair by {by!r}: 'index', 'height', 'axis', 'space' or 'random'")
    return t.take(order)


# -------------------------------------------------------------------------------------------- Blender plumbing ---

def _bpy():
    import bpy
    return bpy


def _mesh_world_vertices(o, dg):
    ev = o.evaluated_get(dg)
    me = ev.to_mesh()
    try:
        v = np.empty(len(me.vertices) * 3, dtype=np.float64)
        me.vertices.foreach_get('co', v)
    finally:
        ev.to_mesh_clear()
    M = np.array(ev.matrix_world, dtype=np.float64)
    return v.reshape(-1, 3) @ M[:3, :3].T + M[:3, 3]


def _objects_of(src):
    """The objects a source names: a VRMHandle (its meshes), an Object (itself and every descendant), a Collection
    (all its objects, recursively), or a list of any of these. Ordered by name within each level, as the engine's
    traverse visited children in order."""
    bpy = _bpy()
    out = []

    def add(o):
        if o not in out:
            out.append(o)

    def walk(o):
        add(o)
        for c in sorted(o.children, key=lambda x: x.name):
            walk(c)
    if isinstance(src, (list, tuple)):
        for s in src:
            for o in _objects_of(s):
                add(o)
        return out
    if hasattr(src, 'meshes') and hasattr(src, 'arm'):                 # characters.VRMHandle
        return list(src.meshes)
    if isinstance(src, Target) and src.source is not None:
        return _objects_of(src.source)
    if isinstance(src, bpy.types.Collection):
        for o in sorted(src.all_objects, key=lambda x: x.name):
            add(o)
        return out
    if isinstance(src, bpy.types.Object):
        walk(src)
        return out
    raise TypeError(f'[particle_targets] not an object, collection or VRM handle: {src!r}')


@contextmanager
def _evaluable(objs):
    """Objects made visible to the viewport depsgraph for sampling (unhidden, their collections included), and put
    back afterwards."""
    bpy = _bpy()
    vl = bpy.context.view_layer
    saved_o, saved_lc = [], []
    lcs = {}

    def index(lc):
        lcs[lc.collection] = lc
        for c in lc.children:
            index(c)
    index(vl.layer_collection)
    for o in objs:
        try:
            saved_o.append((o, o.hide_viewport, o.hide_get(view_layer=vl)))
            o.hide_viewport = False
            o.hide_set(False, view_layer=vl)
        except RuntimeError:
            pass                                      # not in this view layer: its collection below
        for c in o.users_collection:
            lc = lcs.get(c)
            if lc is not None and (lc.exclude or lc.hide_viewport or c.hide_viewport):
                saved_lc.append((lc, lc.exclude, lc.hide_viewport, c.hide_viewport))
                lc.exclude = False
                lc.hide_viewport = False
                c.hide_viewport = False
    vl.update()
    try:
        yield
    finally:
        for lc, ex, hv, chv in saved_lc:
            lc.exclude, lc.hide_viewport, lc.collection.hide_viewport = ex, hv, chv
        for o, hv, hs in saved_o:
            try:
                o.hide_viewport = hv
                o.hide_set(hs, view_layer=vl)
            except RuntimeError:
                pass
        vl.update()


class _Piece:
    """One evaluated geometry: world vertices, triangles (vertex and loop indices, material index), edges, the
    active UVs per loop, a colour attribute, the materials, and whether the morph graph can sample it live."""

    __slots__ = ('obj', 'verts', 'tris', 'tri_loops', 'tri_mat', 'edges', 'uv', 'col', 'col_domain', 'materials',
                 'live_ok', 'radius')

    def __init__(self):
        self.tris = self.tri_loops = self.tri_mat = self.edges = self.uv = self.col = None
        self.col_domain = None
        self.materials = []
        self.live_ok = False
        self.radius = None


def _read_mesh(me, M):
    p = _Piece()
    nv = len(me.vertices)
    v = np.empty(nv * 3, dtype=np.float64)
    me.vertices.foreach_get('co', v)
    v = v.reshape(-1, 3)
    p.verts = v @ M[:3, :3].T + M[:3, 3]
    me.calc_loop_triangles()
    nt = len(me.loop_triangles)
    if nt:
        tv = np.empty(nt * 3, dtype=np.int64)
        me.loop_triangles.foreach_get('vertices', tv)
        tl = np.empty(nt * 3, dtype=np.int64)
        me.loop_triangles.foreach_get('loops', tl)
        mi = np.empty(nt, dtype=np.int64)
        me.loop_triangles.foreach_get('material_index', mi)
        p.tris, p.tri_loops, p.tri_mat = tv.reshape(-1, 3), tl.reshape(-1, 3), mi
    ne = len(me.edges)
    if ne:
        e = np.empty(ne * 2, dtype=np.int64)
        me.edges.foreach_get('vertices', e)
        p.edges = e.reshape(-1, 2)
    uvl = next((u for u in me.uv_layers if u.active_render), None) or me.uv_layers.active
    if uvl is not None and len(me.loops):
        uv = np.empty(len(me.loops) * 2, dtype=np.float32)
        uvl.uv.foreach_get('vector', uv)
        p.uv = uv.reshape(-1, 2)
    ca = getattr(me.color_attributes, 'active_color', None)
    if ca is not None and ca.domain in ('POINT', 'CORNER'):
        c = np.empty(len(ca.data) * 4, dtype=np.float32)
        ca.data.foreach_get('color', c)                    # linear (byte colours are converted by the API)
        p.col = c.reshape(-1, 4)[:, :3]
        p.col_domain = ca.domain
    return p


def _pieces(src, depsgraph=None, frame=None, with_materials=True):
    """Every evaluated geometry of a source: its objects' own evaluated data and every instance they make
    (Geometry Nodes instances, collection instances, particle-system instancers), in world space."""
    bpy = _bpy()
    objs = _objects_of(src)
    owners = set(objs)
    sc = bpy.context.scene
    f0 = sc.frame_current
    pieces = []
    moved = frame is not None and int(frame) != f0
    if moved:
        sc.frame_set(int(frame))               # first: it re-applies keyed visibility, which the unhiding then lifts
    found = []
    try:
        with _evaluable(objs):
            _collect_pieces(objs, owners, depsgraph or bpy.context.evaluated_depsgraph_get(), found)
    finally:
        if moved:
            sc.frame_set(f0)
    found.sort(key=lambda r: (r[0], r[1]))
    for _k, _inst, pc_, owner in found:
        pc_.obj = owner
        pieces.append(pc_)
    return pieces


def _collect_pieces(objs, owners, dg, found):
    """_pieces' walk over the depsgraph's object instances: (order, is instance, _Piece, owner) rows into found."""
    order = {o: k for k, o in enumerate(objs)}
    for inst in dg.object_instances:
        ob = inst.object
        owner = inst.parent.original if (inst.is_instance and inst.parent is not None) else ob.original
        if owner not in owners:
            continue
        if ob.type not in ('MESH', 'CURVE', 'SURFACE', 'FONT', 'META', 'POINTCLOUD', 'CURVES'):
            continue
        M = np.array(inst.matrix_world, dtype=np.float64)
        if ob.type == 'POINTCLOUD':
            pc = ob.data
            n = len(pc.points)
            pos = np.empty(n * 3, dtype=np.float32)
            pc.attributes['position'].data.foreach_get('vector', pos)
            pc_ = _Piece()
            pc_.verts = pos.reshape(-1, 3).astype(np.float64) @ M[:3, :3].T + M[:3, 3]
            for nm in ('color', 'Col', 'Color', 'col'):
                a = pc.attributes.get(nm)
                if a is not None and a.data_type in ('FLOAT_COLOR', 'BYTE_COLOR', 'FLOAT_VECTOR'):
                    c = np.empty(n * (3 if a.data_type == 'FLOAT_VECTOR' else 4), dtype=np.float32)
                    a.data.foreach_get('vector' if a.data_type == 'FLOAT_VECTOR' else 'color', c)
                    pc_.col = c.reshape(n, -1)[:, :3]
                    pc_.col_domain = 'POINT'
                    break
            found.append((order.get(owner, 1 << 30), inst.is_instance, pc_, owner))
            continue
        if ob.type == 'CURVES':
            cv = ob.data
            n = len(cv.points)
            pos = np.empty(n * 3, dtype=np.float32)
            cv.attributes['position'].data.foreach_get('vector', pos)
            pc_ = _Piece()
            pc_.verts = pos.reshape(-1, 3).astype(np.float64) @ M[:3, :3].T + M[:3, 3]
            found.append((order.get(owner, 1 << 30), inst.is_instance, pc_, owner))
            continue
        try:
            # an instance's own mesh comes from a plain to_mesh(): with a depsgraph and all layers kept, Blender 5.2
            # re-evaluates the instancer itself (an empty mesh for a Geometry Nodes host)
            me = ob.to_mesh() if inst.is_instance else ob.to_mesh(preserve_all_data_layers=True, depsgraph=dg)
        except RuntimeError:
            continue
        if me is None:
            continue
        if not len(me.vertices):
            ob.to_mesh_clear()
            continue
        try:
            pc_ = _read_mesh(me, M)
            slots = [s.material.original if s.material is not None else None for s in ob.material_slots]
            if inst.is_instance or not slots:
                slots = [m.original if m is not None else None for m in me.materials] or slots
            pc_.materials = slots
            pc_.live_ok = (not inst.is_instance) and ob.original.type == 'MESH'
        finally:
            ob.to_mesh_clear()
        if pc_.tris is not None and slots and all(_is_outline(slots[i]) for i in np.unique(pc_.tri_mat)
                                                 if 0 <= i < len(slots)):
            continue                            # an MToon outline shell (the VRM add-on's): not the model
        found.append((order.get(owner, 1 << 30), inst.is_instance, pc_, owner))


# ------------------------------------------------------------------------------------------- material colours ---

_IMAGE_CACHE = {}


def _is_outline(mat):
    """The VRM add-on's MToon outline material: its outline shell (a Geometry Nodes instance of the body, inflated)
    is drawing, not the model, and gets no particles."""
    ext = getattr(mat, 'vrm_addon_extension', None) if mat is not None else None
    mt = getattr(ext, 'mtoon1', None) if ext is not None else None
    return bool(getattr(mt, 'is_outline_material', False)) if mt is not None else False


def image_rgba(img, max_size=1024):
    """(H, W, 4) float32 linear RGBA of a bpy image, row 0 = the BOTTOM row (Blender's order), at most max_size px
    across (a scaled copy is read for larger images). Byte sRGB images are linearised."""
    bpy = _bpy()
    key = (img.name, int(max_size), getattr(img, 'filepath', ''))
    if key in _IMAGE_CACHE:
        return _IMAGE_CACHE[key]
    w, h = img.size
    if w == 0 or h == 0:
        img.pixels[0:4]                                 # loads the buffer
        w, h = img.size
    src = img
    if max(w, h) > max_size:
        k = max_size / max(w, h)
        src = img.copy()
        src.scale(max(1, int(round(w * k))), max(1, int(round(h * k))))
    sw, sh = src.size
    ch = src.channels
    px = np.empty(sw * sh * ch, dtype=np.float32)
    src.pixels.foreach_get(px)
    if src is not img:
        bpy.data.images.remove(src)
    a = px.reshape(sh, sw, ch)
    if ch < 4:
        pad = np.ones((sh, sw, 4), dtype=np.float32)
        pad[..., :ch] = a
        if ch == 1:
            pad[..., 1] = pad[..., 2] = a[..., 0]
        a = pad
    cs = img.colorspace_settings.name
    if not img.is_float and 'sRGB' in cs and 'Linear' not in cs:
        a = a.copy()
        a[..., :3] = srgb_to_linear(a[..., :3])
    _IMAGE_CACHE[key] = a
    return a


def _sample_image(a, uv, wrap=True):
    """Bilinear sample of (H, W, 4) at uv (n, 2) (v = 0 at the bottom row)."""
    H, W = a.shape[:2]
    u = uv[:, 0].astype(np.float64)
    v = uv[:, 1].astype(np.float64)
    if wrap:
        u, v = u - np.floor(u), v - np.floor(v)
    x = np.clip(u * W - 0.5, 0, W - 1)
    y = np.clip(v * H - 0.5, 0, H - 1)
    x0, y0 = np.floor(x).astype(np.int64), np.floor(y).astype(np.int64)
    x1, y1 = np.minimum(x0 + 1, W - 1), np.minimum(y0 + 1, H - 1)
    fx, fy = (x - x0)[:, None], (y - y0)[:, None]
    c = (a[y0, x0] * (1 - fx) * (1 - fy) + a[y0, x1] * fx * (1 - fy) + a[y1, x0] * (1 - fx) * fy
         + a[y1, x1] * fx * fy)
    return c.astype(np.float32)


_SHADER_COLOR = {'ShaderNodeBsdfPrincipled': 'Base Color', 'ShaderNodeBsdfDiffuse': 'Color',
                 'ShaderNodeEmission': 'Color', 'ShaderNodeBsdfToon': 'Color', 'ShaderNodeBsdfGlossy': 'Color',
                 'ShaderNodeSubsurfaceScattering': 'Color', 'ShaderNodeBsdfSheen': 'Color',
                 'ShaderNodeBsdfMetallic': 'Base Color', 'ShaderNodeBsdfTranslucent': 'Color',
                 'ShaderNodeBsdfHairPrincipled': 'Color', 'ShaderNodeBsdfRefraction': 'Color',
                 'ShaderNodeBsdfGlass': 'Color'}
_GROUP_COLOR = ('Base Color', 'BaseColor', 'Lit Color', 'Color', 'Albedo', 'Diffuse', 'Main Color', 'Lit Color Texture')


def _upstream(sock, kinds, depth=8):
    """The first node of one of `kinds` upstream of an input socket (breadth first through any nodes)."""
    if not sock.is_linked:
        return None
    seen, front = set(), [sock.links[0].from_node]
    for _ in range(depth):
        nxt = []
        for n in front:
            if n in seen:
                continue
            seen.add(n)
            if n.bl_idname in kinds and (n.bl_idname != 'ShaderNodeTexImage' or n.image is not None):
                return n
            for i in n.inputs:
                if i.is_linked:
                    nxt.append(i.links[0].from_node)
        front = nxt
        if not front:
            break
    return None


class _ColorSource:
    """How to colour a point on one material: ('const', rgb) | ('image', rgba array, uv map name, tint) |
    ('attr', name) — plus an emission term and an alpha-from-image flag."""

    def __init__(self, mat, max_size=1024, skip_glass=True):
        self.kind, self.rgb, self.img, self.uvname, self.tint, self.attr = 'const', (0.8, 0.8, 0.8), None, None, \
            np.ones(3, np.float32), None
        self.em_kind, self.em_rgb, self.em_img, self.em_strength = None, None, None, 0.0
        self.alpha_img = False
        self.invisible = False             # glass / a mostly transparent sheet: no points (skip_glass)
        self.skip_glass = skip_glass
        self.max_size = max_size
        if mat is None:
            return
        self.rgb = tuple(mat.diffuse_color[:3])
        if _is_outline(mat):
            self.invisible = True
            return
        ext = getattr(mat, 'vrm_addon_extension', None)
        mt = getattr(ext, 'mtoon1', None) if ext is not None else None
        if mt is not None and getattr(mt, 'enabled', False):
            pbr = mt.pbr_metallic_roughness
            self.rgb = tuple(pbr.base_color_factor[:3])
            src = pbr.base_color_texture.index.source
            if src is not None:
                self.kind, self.img, self.tint = 'image', image_rgba(src, max_size), np.asarray(self.rgb, np.float32)
            emf = tuple(mt.emissive_factor[:3])
            ems = mt.emissive_texture.index.source
            if ems is not None:
                self.em_kind, self.em_img, self.em_rgb, self.em_strength = 'image', image_rgba(ems, max_size), emf, 1.0
            elif max(emf) > 0:
                self.em_kind, self.em_rgb, self.em_strength = 'const', emf, 1.0
            return
        if not mat.use_nodes or mat.node_tree is None:
            return
        nt = mat.node_tree
        out = next((n for n in nt.nodes if n.bl_idname == 'ShaderNodeOutputMaterial' and n.is_active_output), None) \
            or next((n for n in nt.nodes if n.bl_idname == 'ShaderNodeOutputMaterial'), None)
        if out is None or not out.inputs['Surface'].is_linked:
            return
        sh = _upstream(out.inputs['Surface'], set(_SHADER_COLOR) | {'ShaderNodeGroup'}, depth=12)
        if sh is None:
            return
        if sh.bl_idname == 'ShaderNodeGroup':
            sock = next((sh.inputs[k] for k in _GROUP_COLOR if k in sh.inputs), None)
        else:
            sock = sh.inputs.get(_SHADER_COLOR[sh.bl_idname])
        if sock is not None:
            self._from_socket(sock)
        if sh.bl_idname == 'ShaderNodeEmission':
            st = sh.inputs['Strength']
            if not st.is_linked and st.default_value != 1.0:
                self.tint = self.tint * float(st.default_value)
        if sh.bl_idname == 'ShaderNodeBsdfPrincipled':
            st = sh.inputs.get('Emission Strength')
            ec = sh.inputs.get('Emission Color')
            if st is not None and ec is not None and (st.is_linked or st.default_value > 0):
                s = 1.0 if st.is_linked else float(st.default_value)
                tex = _upstream(ec, {'ShaderNodeTexImage'})
                if tex is not None:
                    self.em_kind, self.em_img, self.em_rgb, self.em_strength = 'image', image_rgba(tex.image,
                                                                                                 max_size), \
                        (1.0, 1.0, 1.0), s
                elif max(ec.default_value[:3]) > 0:
                    self.em_kind, self.em_rgb, self.em_strength = 'const', tuple(ec.default_value[:3]), s
            al = sh.inputs.get('Alpha')
            if al is not None and al.is_linked and self.kind == 'image':
                self.alpha_img = _upstream(al, {'ShaderNodeTexImage'}) is not None
            tw = sh.inputs.get('Transmission Weight')
            see_through = (tw is not None and not tw.is_linked and tw.default_value > 0.5) or \
                (al is not None and not al.is_linked and al.default_value < 0.3)
            if see_through and self.skip_glass:
                self.invisible = True

    def _from_socket(self, sock):
        if not sock.is_linked:
            self.rgb = tuple(sock.default_value[:3])
            return
        src = sock.links[0].from_node
        if src.bl_idname == 'ShaderNodeMix' and getattr(src, 'blend_type', '') == 'MULTIPLY':
            ins = {s.identifier: s for s in src.inputs}
            a, b = ins.get('A_Color'), ins.get('B_Color')
            for x, y in ((a, b), (b, a)):
                if x is not None and y is not None and not x.is_linked and y.is_linked:
                    self.tint = np.asarray(x.default_value[:3], np.float32)
        tex = _upstream(sock, {'ShaderNodeTexImage', 'ShaderNodeVertexColor', 'ShaderNodeAttribute', 'ShaderNodeRGB'})
        if tex is None:
            return
        if tex.bl_idname == 'ShaderNodeTexImage':
            self.kind, self.img = 'image', image_rgba(tex.image, self.max_size)
            v = tex.inputs['Vector']
            if v.is_linked and v.links[0].from_node.bl_idname == 'ShaderNodeUVMap':
                self.uvname = v.links[0].from_node.uv_map or None
        elif tex.bl_idname == 'ShaderNodeRGB':
            self.rgb = tuple(tex.outputs[0].default_value[:3])
        else:
            self.kind = 'attr'
            self.attr = tex.layer_name if tex.bl_idname == 'ShaderNodeVertexColor' else tex.attribute_name

    def colors(self, uv, attr_col, n=None):
        """(n, 3) linear colours and (n,) alphas for n points with uv (n, 2) or None and colour-attribute values."""
        if n is None:
            n = len(uv) if uv is not None else (len(attr_col) if attr_col is not None else 0)
        alpha = np.ones(n, np.float32)
        if self.kind == 'image' and uv is not None:
            s = _sample_image(self.img, uv)
            c = s[:, :3] * self.tint
            if self.alpha_img:
                alpha = s[:, 3]
        elif self.kind == 'attr' and attr_col is not None:
            c = attr_col * self.tint
        else:
            c = np.broadcast_to(np.asarray(self.rgb, np.float32) * self.tint, (n, 3)).copy()
        if self.em_kind == 'image' and uv is not None:
            c = c + _sample_image(self.em_img, uv)[:, :3] * np.asarray(self.em_rgb, np.float32) * self.em_strength
        elif self.em_kind == 'const':
            c = c + np.asarray(self.em_rgb, np.float32) * self.em_strength
        if self.invisible:
            alpha = np.zeros(n, np.float32)
        return c.astype(np.float32), alpha


def material_colors(material, uv=None, attr_col=None, max_size=1024, n=None):
    """The colours (n, 3) and alphas (n,) a material shows at points with these UVs (the sampler from_object uses)."""
    return _ColorSource(material, max_size).colors(uv, attr_col, n)


# ---------------------------------------------------------------------------------------------- from_object ---

def _sample_surface(pieces, n, rng, colors=True, live=False, alpha_cut=True, max_size=1024):
    """Area-weighted points on the pieces' triangles: exactly n. -> (points, colours or None, LiveBinding or None)."""
    rows = []
    for pi, pc in enumerate(pieces):
        if pc.tris is None or not len(pc.tris):
            continue
        V = pc.verts
        a, b, c = V[pc.tris[:, 0]], V[pc.tris[:, 1]], V[pc.tris[:, 2]]
        area = 0.5 * np.linalg.norm(np.cross(b - a, c - a), axis=1)
        rows.append((pi, area))
    if not rows:
        return None
    areas = np.concatenate([r[1] for r in rows])
    total = float(areas.sum())
    if total <= 0:
        return None
    cum = np.cumsum(areas) / total
    piece_of = np.concatenate([np.full(len(r[1]), r[0]) for r in rows])
    tri_of = np.concatenate([np.arange(len(r[1])) for r in rows])
    srcs = {}
    out_p, out_c, out_i, out_w = [], [], [], []
    need = n
    for _round in range(6):
        k = int(math.ceil(need * (1.15 if _round else 1.0))) + 8
        g = np.minimum(np.searchsorted(cum, rng.random(k), side='right'), len(cum) - 1)
        r1, r2 = rng.random(k), rng.random(k)
        s = np.sqrt(r1)
        w = np.stack([1 - s, s * (1 - r2), s * r2], 1)
        P = np.empty((k, 3))
        C = np.ones((k, 3), np.float32) if colors else None
        A = np.ones(k, np.float32)
        I = np.empty((k, 3), np.int64)
        for pi in np.unique(piece_of[g]):
            sel = np.nonzero(piece_of[g] == pi)[0]
            pc = pieces[pi]
            t = tri_of[g[sel]]
            tv = pc.tris[t]
            P[sel] = (pc.verts[tv] * w[sel][..., None]).sum(1)
            I[sel] = tv
            if colors:
                uv = None
                if pc.uv is not None:
                    uv = (pc.uv[pc.tri_loops[t]] * w[sel][..., None].astype(np.float32)).sum(1)
                acol = None
                if pc.col is not None:
                    src = pc.tri_loops[t] if pc.col_domain == 'CORNER' else tv
                    acol = (pc.col[src] * w[sel][..., None].astype(np.float32)).sum(1)
                mats = pc.tri_mat[t]
                for mi in np.unique(mats):
                    ss = sel[mats == mi]
                    mat = pc.materials[mi] if 0 <= mi < len(pc.materials) else None
                    key = (id(pc), int(mi))
                    if key not in srcs:
                        srcs[key] = _ColorSource(mat, max_size)
                    m_ = mats == mi
                    C[ss], A[ss] = srcs[key].colors(None if uv is None else uv[m_],
                                                    None if acol is None else acol[m_], n=len(ss))
        keep = A >= 0.5 if (colors and alpha_cut) else np.ones(k, bool)
        out_p.append(P[keep])
        if colors:
            out_c.append(C[keep])
        out_i.append(np.stack([piece_of[g][keep]], 1))
        out_w.append((I[keep], w[keep]))
        need -= int(keep.sum())
        if need <= 0:
            break
    P = np.concatenate(out_p)[:n]
    C = np.concatenate(out_c)[:n] if colors else None
    if len(P) < n:                                     # an almost fully alpha-cut model: top up by cycling
        j = np.arange(n) % max(1, len(P))
        P = P[j]
        C = C[j] if C is not None else None
    lb = None
    if live:
        pidx = np.concatenate(out_i)[:n, 0]
        I = np.concatenate([x[0] for x in out_w])[:n]
        W = np.concatenate([x[1] for x in out_w])[:n]
        if len(pidx) < n:
            j = np.arange(n) % max(1, len(pidx))
            pidx, I, W = pidx[j], I[j], W[j]
        lb = _bind(pieces, pidx, I, W)
    return P.astype(np.float32), C, lb


def _bind(pieces, pidx, I, W):
    """A LiveBinding for samples on live-able pieces (I: vertex indices within their piece)."""
    live_pieces = [k for k, pc in enumerate(pieces) if pc.live_ok]
    if not all(pieces[k].live_ok for k in np.unique(pidx)):
        bad = sorted({pieces[k].obj.name for k in np.unique(pidx) if not pieces[k].live_ok})
        raise ValueError(f'[particle_targets] live: {bad} are instanced or not meshes; sample them static '
                         f'(live=False), or make them real mesh objects')
    offs, counts, objs, off = {}, [], [], 0
    for k in live_pieces:
        offs[k] = off
        counts.append(len(pieces[k].verts))
        objs.append(pieces[k].obj)
        off += len(pieces[k].verts)
    shift = np.array([offs.get(int(k), 0) for k in pidx], dtype=np.int64)
    return LiveBinding(objs, counts, I + shift[:, None], W)


def _sample_edges(pieces, n, rng):
    rows = []
    for pi, pc in enumerate(pieces):
        if pc.edges is None or not len(pc.edges):
            continue
        L = np.linalg.norm(pc.verts[pc.edges[:, 1]] - pc.verts[pc.edges[:, 0]], axis=1)
        rows.append((pi, L))
    if not rows:
        return None
    L = np.concatenate([r[1] for r in rows])
    if L.sum() <= 0:
        return None
    cum = np.cumsum(L) / L.sum()
    piece_of = np.concatenate([np.full(len(r[1]), r[0]) for r in rows])
    e_of = np.concatenate([np.arange(len(r[1])) for r in rows])
    g = np.minimum(np.searchsorted(cum, rng.random(n), side='right'), len(cum) - 1)
    t = rng.random(n)[:, None]
    P = np.empty((n, 3))
    for pi in np.unique(piece_of[g]):
        sel = np.nonzero(piece_of[g] == pi)[0]
        pc = pieces[pi]
        e = pc.edges[e_of[g[sel]]]
        P[sel] = pc.verts[e[:, 0]] * (1 - t[sel]) + pc.verts[e[:, 1]] * t[sel]
    return P.astype(np.float32)


def _vertex_colors(pc, max_size=1024):
    """A colour per vertex of a piece: its first corner's UV and material (or the colour attribute)."""
    nv = len(pc.verts)
    C = np.full((nv, 3), 0.8, np.float32)
    if pc.tris is None:
        if pc.col is not None and pc.col_domain == 'POINT':
            return pc.col.astype(np.float32)
        return C
    first_tri = np.full(nv, -1, np.int64)
    first_k = np.zeros(nv, np.int64)
    for k in (2, 1, 0):
        first_tri[pc.tris[::-1, k]] = np.arange(len(pc.tris))[::-1]
        first_k[pc.tris[::-1, k]] = k
    has = first_tri >= 0
    t = first_tri[has]
    loops = pc.tri_loops[t, first_k[has]]
    uv = pc.uv[loops] if pc.uv is not None else None
    acol = None
    if pc.col is not None:
        acol = pc.col[loops] if pc.col_domain == 'CORNER' else pc.col[np.nonzero(has)[0]]
    mats = pc.tri_mat[t]
    out = np.full((int(has.sum()), 3), 0.8, np.float32)
    for mi in np.unique(mats):
        sel = mats == mi
        mat = pc.materials[mi] if 0 <= mi < len(pc.materials) else None
        out[sel] = _ColorSource(mat, max_size).colors(None if uv is None else uv[sel],
                                                      None if acol is None else acol[sel], n=int(sel.sum()))[0]
    C[has] = out
    return C


def from_object(src, count, mode='surface', live=False, frame=None, colors=True, seed=1, alpha_cut=True,
                max_texture=1024, voxel=None, name=None, random=None):
    """Points sampled off anything Blender draws, in world space, in the colours of its materials.

    src: an Object (and its children), a Collection, a VRMHandle, a list of these, or a Target that remembers its
    source. Evaluated: modifiers, shape keys, armatures, Geometry Nodes (meshes, instances, point clouds),
    collection instances and particle-system instancers, curves, text, surfaces and metaballs (as their meshes).

    mode  'surface'   area-weighted on the triangles (a mesh with no faces falls back to its edges, then its
                      vertices); exactly `count` points, coloured from the materials at their UVs
          'vertices'  the engine's fromMesh sampling: every mesh's vertices with a stride of max(1, V // 8000), then
                      resampled to count (colours: each vertex's first corner)
          'volume'    inside the closed meshes (Mesh to Volume, Distribute Points in Volume), coloured by the nearest
                      surface sample; voxel = the voxel size (default: the bounds' diagonal / 96)
          'edges'     along the edges (curves without bevel, wireframes)
    live  True: a binding the morph graph samples every frame (mesh objects only: a skinned or shape-keyed body
          follows its animation); False: a snapshot at `frame` (default the current frame).
    alpha_cut  no points where the material's alpha (from its texture) is under 0.5 (leaves, decals).
    random: for mode 'vertices', the engine's stream (a JSRandom) to resample with; default mulberry32(seed)."""
    rng = np.random.default_rng(seed)
    count = int(count)
    label = name or _label(src)
    if mode == 'vertices':
        return _from_vertices(src, count, live, frame, colors, seed, max_texture, label, random)
    pieces = _pieces(src, frame=frame, with_materials=colors)
    if not pieces:
        print(f'[particle_targets] from_object {label}: nothing to sample')
        return Target(np.zeros((count, 3), np.float32), name=label)
    if mode == 'volume':
        return _from_volume_fill(src, pieces, count, rng, colors, voxel, max_texture, label, seed)
    if mode == 'surface':
        r = _sample_surface(pieces, count, rng, colors, live, alpha_cut, max_texture)
        if r is not None:
            P, C, lb = r
            return Target(P, C, lb, label, src)
        mode = 'edges'
    if live:
        print(f'[particle_targets] from_object {label}: no faces to bind live; sampling a snapshot')
    if mode == 'edges':
        P = _sample_edges(pieces, count, rng)
        if P is not None:
            return Target(P, _nearest_colors(pieces, P, colors, max_texture), None, label, src)
    V = np.concatenate([pc.verts for pc in pieces], axis=0)
    if not len(V):
        print(f'[particle_targets] from_object {label}: no geometry to sample')
        return Target(np.zeros((count, 3), np.float32), name=label)
    C = None
    if colors:
        C = np.concatenate([pc.col if (pc.col is not None and pc.col_domain == 'POINT') else
                            _vertex_colors(pc, max_texture) for pc in pieces], axis=0)
    j = rng.integers(0, len(V), count) if len(V) < count else rng.choice(len(V), count, replace=False)
    return Target(V[j].astype(np.float32), None if C is None else C[j], None, label, src)


def _nearest_colors(pieces, P, colors, max_texture):
    if not colors:
        return None
    V = np.concatenate([pc.verts for pc in pieces], axis=0)
    C = np.concatenate([_vertex_colors(pc, max_texture) for pc in pieces], axis=0)
    return C[_nearest(V, P)]


def _nearest(V, P):
    """Index of the nearest of V for each P (mathutils KD-tree)."""
    from mathutils.kdtree import KDTree
    kd = KDTree(len(V))
    for i, v in enumerate(V):
        kd.insert(v, i)
    kd.balance()
    return np.array([kd.find(p)[1] for p in P], dtype=np.int64)


def _from_vertices(src, count, live, frame, colors, seed, max_texture, label, random=None):
    """The engine's fromMesh: vertices with a stride of max(1, V // 8000) per mesh, then resampleToN."""
    from .particle_morph import JSRandom
    pieces = [pc for pc in _pieces(src, frame=frame, with_materials=colors) if pc.verts is not None]
    picks, pts, cols, pidx = [], [], [], []
    for k, pc in enumerate(pieces):
        V = len(pc.verts)
        step = max(1, V // 8000)
        idx = np.arange(0, V, step)
        picks.append(idx)
        pidx.append(np.full(len(idx), k))
        pts.append(pc.verts[idx])
        if colors:
            cols.append(_vertex_colors(pc, max_texture)[idx])
    if not pts:
        print(f'[particle_morph] fromMesh {label}: no vertices found')
        return Target(np.zeros((count, 3), np.float32), name=label)
    t = Target(np.concatenate(pts).astype(np.float32), np.concatenate(cols) if colors else None, None, label, src)
    if live:
        I = np.concatenate(picks)
        t.live = _bind(pieces, np.concatenate(pidx), np.stack([I, I, I], 1),
                       np.tile(np.array([1.0, 0.0, 0.0], np.float32), (len(I), 1)))
    return t.resample(count, random if random is not None else JSRandom(seed))


def _from_volume_fill(src, pieces, count, rng, colors, voxel, max_texture, label, seed):
    """Points inside the closed meshes: Mesh to Volume -> Distribute Points in Volume in a scratch graph."""
    objs = [pc.obj for pc in pieces]
    allv = np.concatenate([pc.verts for pc in pieces], axis=0)
    lo, hi = allv.min(0), allv.max(0)
    diag = float(np.linalg.norm(hi - lo)) or 1.0
    vox = float(voxel) if voxel else diag / 96.0
    vol_est = float(np.prod(np.maximum(hi - lo, vox)))
    density = min(max(10.0, 3.0 * count / max(vol_est * 0.3, 1e-6)), 5e7)

    def build(b, gi, go, L):
        join = b.node('GeometryNodeJoinGeometry')
        for o in dict.fromkeys(objs):
            oi = b.node('GeometryNodeObjectInfo', transform_space='RELATIVE')
            oi.inputs['Object'].default_value = o
            L.new(oi.outputs['Geometry'], join.inputs[0])
        real = b.node('GeometryNodeRealizeInstances')
        L.new(join.outputs[0], real.inputs[0])
        m2v = b.node('GeometryNodeMeshToVolume')
        _set_mode(m2v, 'resolution_mode', 'Resolution Mode', 'VOXEL_SIZE', 'Size')
        _set_input(m2v, ('Voxel Size',), vox)
        L.new(real.outputs[0], m2v.inputs['Mesh'])
        dpv = b.node('GeometryNodeDistributePointsInVolume')
        _set_mode(dpv, 'mode', 'Mode', 'DENSITY_RANDOM', 'Random')
        _set_input(dpv, ('Density',), density)
        _set_input(dpv, ('Seed',), int(seed))
        L.new(m2v.outputs[0], dpv.inputs['Volume'])
        p2v = b.node('GeometryNodePointsToVertices')
        L.new(dpv.outputs[0], p2v.inputs[0])
        L.new(p2v.outputs[0], go.inputs[0])
    with _evaluable(objs):
        P, _a = _gn_points(build)
    if not len(P):
        print(f'[particle_targets] from_object {label} volume: no interior (open mesh?); using the surface')
        P = _sample_surface(pieces, count, rng, False)[0]
    j = rng.choice(len(P), count, replace=len(P) < count)
    P = P[j]
    C = None
    if colors:
        S = _sample_surface(pieces, min(20000, max(2000, count // 3)), np.random.default_rng(seed + 1), True,
                            False, True, max_texture)
        C = S[1][_nearest(S[0], P)]
    return Target(P.astype(np.float32), C, None, label, src)


def _set_mode(node, prop, sock, enum, menu_item):
    """A node option that is a property in some Blender versions and a menu socket in others."""
    if hasattr(node, prop):
        try:
            setattr(node, prop, enum)
            return
        except (TypeError, AttributeError):
            pass
    s = node.inputs.get(sock)
    if s is not None:
        try:
            s.default_value = menu_item
        except TypeError:
            s.default_value = enum


def _set_input(node, names, value):
    for nm in names:
        s = node.inputs.get(nm)
        if s is not None:
            s.default_value = value
            return True
    return False


def _gn_points(build, attrs=()):
    """Run a scratch Geometry Nodes graph on an empty mesh object and read back its vertices and named float
    attributes (the graph ends in Points to Vertices). -> (points (n, 3), {name: (n,) array})."""
    bpy = _bpy()
    from ._nodes import Builder, new_group
    tree, gi, go = new_group('eido.ptargets.scratch', 'GeometryNodeTree', [('Geometry', 'NodeSocketGeometry')],
                             [('Geometry', 'NodeSocketGeometry')])
    me = bpy.data.meshes.new('eido.ptargets.scratch')
    ob = bpy.data.objects.new('eido.ptargets.scratch', me)
    bpy.context.scene.collection.objects.link(ob)
    try:
        mod = ob.modifiers.new('scratch', 'NODES')
        mod.node_group = tree
        build(Builder(tree), gi, go, tree.links)
        bpy.context.view_layer.update()
        dg = bpy.context.evaluated_depsgraph_get()
        ev = ob.evaluated_get(dg)
        m = ev.to_mesh()
        try:
            P = np.empty(len(m.vertices) * 3, dtype=np.float64)
            m.vertices.foreach_get('co', P)
            out = {}
            for nm in attrs:
                a = m.attributes.get(nm)
                if a is not None:
                    v = np.empty(len(a.data), dtype=np.float32)
                    a.data.foreach_get('value', v)
                    out[nm] = v
        finally:
            ev.to_mesh_clear()
    finally:
        bpy.data.objects.remove(ob)
        bpy.data.meshes.remove(me)
        bpy.data.node_groups.remove(tree)
    return P.reshape(-1, 3), out


def _label(src):
    if isinstance(src, (list, tuple)):
        return '+'.join(_label(s) for s in src[:3])
    return getattr(src, 'name', None) or getattr(getattr(src, 'arm', None), 'name', None) or type(src).__name__


# ----------------------------------------------------------------------------------------------- from_volume ---

def from_volume(src, count, threshold=0.05, grid='density', colors=('#3a1a0a', '#ffd9a0'), seed=1, density=None,
                name=None):
    """Points inside a volume: a Volume object (a .vdb, a smoke or fire cache, a Geometry Nodes volume) or a .vdb
    path. Geometry Nodes' Distribute Points in Volume scatters where the grid exceeds `threshold`; the points are
    coloured along colors=(thin, dense) by the grid's value there (None: no colours). -> Target (count points)."""
    bpy = _bpy()
    made = None
    if isinstance(src, str):
        vol = bpy.data.volumes.new(os.path.splitext(os.path.basename(src))[0])
        vol.filepath = os.path.abspath(src)
        made = bpy.data.objects.new(vol.name, vol)
        bpy.context.scene.collection.objects.link(made)
        made.hide_render = True
        src_obj = made
    else:
        src_obj = src
    rng = np.random.default_rng(seed)
    # the density is measured, not guessed: an object whose Geometry Nodes make the volume reports no useful bounds,
    # and a guess from them asked Distribute Points in Volume for billions of points
    dens = float(density) if density else 2000.0
    with _evaluable([src_obj]):
        P, at = _volume_points(src_obj, dens, seed, threshold, grid)
        if not density and 0 < len(P) < 1.5 * count:
            dens = min(dens * 2.0 * count / len(P), 5e7)
            P, at = _volume_points(src_obj, dens, seed, threshold, grid)
    if made is not None:
        made.hide_viewport = True
    lbl = name or _label(src_obj)
    if not len(P):
        print(f'[particle_targets] from_volume {lbl}: no voxels above {threshold}')
        return Target(np.zeros((count, 3), np.float32), name=lbl)
    j = rng.choice(len(P), count, replace=len(P) < count)
    C = None
    if colors is not None:
        from ._util import color
        d = at.get('vdens')
        d = d[j] if d is not None else np.ones(count, np.float32)
        k = np.clip((d - threshold) / max(np.percentile(d, 95) - threshold, 1e-6), 0, 1)[:, None]
        c0, c1 = np.asarray(color(colors[0]), np.float32), np.asarray(color(colors[1]), np.float32)
        C = (c0 + (c1 - c0) * k).astype(np.float32)
    return Target(P[j].astype(np.float32), C, None, lbl, made or src_obj)


def _volume_points(src_obj, dens, seed, threshold, grid):
    """Distribute Points in Volume over an object's evaluated volume at `dens` points per cubic metre, with the
    grid's value at each point ('vdens'). -> (points, {'vdens': values})."""
    def build(b, gi, go, L):
        oi = b.node('GeometryNodeObjectInfo', transform_space='RELATIVE')
        oi.inputs['Object'].default_value = src_obj
        real = b.node('GeometryNodeRealizeInstances')
        L.new(oi.outputs['Geometry'], real.inputs[0])
        dpv = b.node('GeometryNodeDistributePointsInVolume')
        _set_mode(dpv, 'mode', 'Mode', 'DENSITY_RANDOM', 'Random')
        _set_input(dpv, ('Density',), float(dens))
        _set_input(dpv, ('Seed',), int(seed))
        _set_input(dpv, ('Threshold',), float(threshold))
        L.new(real.outputs[0], dpv.inputs['Volume'])
        geo = dpv.outputs[0]
        try:
            gg = b.node('GeometryNodeGetNamedGrid', data_type='FLOAT')
            L.new(real.outputs[0], gg.inputs['Volume'])
            gg.inputs['Name'].default_value = grid
            sg = b.node('GeometryNodeSampleGrid', data_type='FLOAT')
            L.new(gg.outputs['Grid'], sg.inputs['Grid'])
            L.new(b.node('GeometryNodeInputPosition').outputs[0], sg.inputs['Position'])
            st = b.node('GeometryNodeStoreNamedAttribute', data_type='FLOAT', domain='POINT')
            st.inputs['Name'].default_value = 'vdens'
            L.new(geo, st.inputs['Geometry'])
            L.new(sg.outputs['Value'], st.inputs['Value'])
            geo = st.outputs[0]
        except (RuntimeError, KeyError, TypeError) as e:
            print('[particle_targets] from_volume: no grid sampling here:', e)
        p2v = b.node('GeometryNodePointsToVertices')
        L.new(geo, p2v.inputs[0])
        L.new(p2v.outputs[0], go.inputs[0])
    return _gn_points(build, ('vdens',))


# ------------------------------------------------------------------------------------------------ from_image ---

def from_image(image, count, width=4.0, mode='alpha', threshold=0.5, depth=0.0, colors=True, at=(0.0, 0.0, 0.0),
               plane='xz', seed=1, max_size=512, invert=False, density='weight', name=None):
    """Particles in the shape of an image: a silhouette (its alpha), a bright drawing on black (luma), ink on paper
    (dark), every pixel (any), or the outlines (edges of the alpha or luma). The image is laid in the XZ plane facing
    -Y (plane='xy': lying flat), `width` metres across, centred on `at`; points sit anywhere inside their pixels
    (no grid), their density following the mask's strength (density='weight') or even (density='uniform') above
    `threshold`. colours: the pixels' own (linear). image: a bpy image, a path, or an (H, W, 3|4) array (row 0 at the
    top, display-referred 0..1)."""
    bpy = _bpy()
    rng = np.random.default_rng(seed)
    if isinstance(image, np.ndarray):
        a = np.asarray(image, dtype=np.float32)
        if a.max() > 1.5:
            a = a / 255.0
        if a.ndim == 2:
            a = np.stack([a, a, a, np.ones_like(a)], -1)
        if a.shape[2] == 3:
            a = np.concatenate([a, np.ones(a.shape[:2] + (1,), np.float32)], -1)
        a = a[::-1].copy()
        a[..., :3] = srgb_to_linear(a[..., :3])
        lbl = name or 'image'
    else:
        img = image
        if isinstance(image, str):
            path = _resolve_path(image)
            img = bpy.data.images.load(path, check_existing=True)
        a = image_rgba(img, max_size)
        lbl = name or img.name
    H, W = a.shape[:2]
    rgb, alpha = a[..., :3], a[..., 3]
    lum = (rgb @ np.array([0.2126, 0.7152, 0.0722], np.float32))
    lum_d = lum ** (1 / 2.2)                     # a perceptual luma for thresholds
    if mode == 'alpha':
        m = alpha
    elif mode == 'luma':
        m = lum_d * alpha
    elif mode == 'dark':
        m = (1.0 - lum_d) * alpha
    elif mode == 'any':
        m = np.ones_like(alpha)
    elif mode == 'edges':
        base = alpha if float(alpha.min()) < 0.99 else lum_d
        gy, gx = np.gradient(base)
        m = np.hypot(gx, gy)
        m = m / max(float(m.max()), 1e-6)
    else:
        raise ValueError(f"[particle_targets] from_image mode {mode!r}: alpha, luma, dark, any or edges")
    if invert:
        m = 1.0 - m
    ys, xs = np.nonzero(m > (threshold if mode != 'edges' else threshold * 0.3))
    if not len(xs):
        print(f'[particle_targets] from_image {lbl}: nothing above the threshold')
        return Target(np.zeros((int(count), 3), np.float32), name=lbl)
    wts = m[ys, xs].astype(np.float64) if density == 'weight' else np.ones(len(xs))
    j = rng.choice(len(xs), int(count), p=wts / wts.sum())
    u = (xs[j] + rng.random(len(j))) / W
    v = (ys[j] + rng.random(len(j))) / H
    height = float(width) * H / W
    x = (u - 0.5) * float(width)
    z = (v - 0.5) * height
    y = (rng.random(len(j)) - 0.5) * float(depth) if depth else np.zeros(len(j))
    P = np.stack([x, y, z], 1) if plane == 'xz' else np.stack([x, z, y], 1)
    C = rgb[ys[j], xs[j]].astype(np.float32) if colors else None
    return Target((P + np.asarray(at, np.float64)).astype(np.float32), C, None, lbl, None)


def from_silhouette(src, count, axis='-y', res=320, colors=True, seed=1, frame=None, name=None):
    """A model's silhouette seen along `axis` ('-y' = from the front, the camera convention; 'x', '-x', 'y', 'z'
    ...), filled flat in the plane through its centroid at world scale: a cut-out sign of it, in its colours (each
    pixel takes the mean colour of the surface seen there)."""
    rng = np.random.default_rng(seed)
    dense = from_object(src, max(int(count) * 2, 120000), frame=frame, colors=colors, seed=seed + 3)
    P = dense.points.astype(np.float64)
    ax = axis.lower()
    k = 'xyz'.index(ax[-1])
    uax = [i for i in range(3) if i != k]
    if k == 1:
        uax = [0, 2]
    if k == 0:
        uax = [1, 2]
    U, V = P[:, uax[0]], P[:, uax[1]]
    lo_u, hi_u, lo_v, hi_v = U.min(), U.max(), V.min(), V.max()
    span = max(hi_u - lo_u, hi_v - lo_v) or 1.0
    px = span / res
    nu, nv = int(math.ceil((hi_u - lo_u) / px)) + 3, int(math.ceil((hi_v - lo_v) / px)) + 3
    iu = ((U - lo_u) / px).astype(np.int64) + 1
    iv = ((V - lo_v) / px).astype(np.int64) + 1
    hit = np.zeros((nv, nu), np.float32)
    np.add.at(hit, (iv, iu), 1.0)
    mask = hit > 0
    for _ in range(1):                                 # close one-pixel gaps
        g = mask.copy()
        g[1:] |= mask[:-1]
        g[:-1] |= mask[1:]
        g[:, 1:] |= mask[:, :-1]
        g[:, :-1] |= mask[:, 1:]
        mask = g
    col = None
    if colors and dense.colors is not None:
        csum = np.zeros((nv, nu, 3), np.float64)
        np.add.at(csum, (iv, iu), dense.colors.astype(np.float64))
        cnt = np.maximum(hit, 1)[..., None]
        col = csum / cnt
    ys, xs = np.nonzero(mask)
    j = rng.integers(0, len(xs), int(count))
    uu = lo_u + (xs[j] - 1 + rng.random(len(j))) * px
    vv = lo_v + (ys[j] - 1 + rng.random(len(j))) * px
    out = np.empty((len(j), 3))
    out[:, uax[0]], out[:, uax[1]] = uu, vv
    out[:, k] = P[:, k].mean()
    C = None
    if col is not None:
        C = col[ys[j], xs[j]].astype(np.float32)
        empty = hit[ys[j], xs[j]] == 0                  # a closed gap pixel: the nearest seen pixel's colour
        if empty.any():
            hy, hx = np.nonzero(hit > 0)
            near = _nearest(np.stack([hx, hy, np.zeros(len(hx))], 1).astype(np.float64),
                            np.stack([xs[j][empty], ys[j][empty], np.zeros(int(empty.sum()))], 1).astype(np.float64))
            C[empty] = col[hy[near], hx[near]].astype(np.float32)
    return Target(out.astype(np.float32), C, None, name or (_label(src) + ':silhouette'), None)


# ------------------------------------------------------------------------------------------ from_point_cloud ---

def from_point_cloud(src, count=None, colors=True, seed=1, name=None):
    """A point cloud as a target: a POINTCLOUD object or a vertex-only mesh (evaluated, world space, with a colour
    attribute if it has one), a .ply (Blender's importer), .npy, .xyz / .txt / .csv / .pts (x y z [r g b], 0..1 or
    0..255) file, or an (m, 3|6) array. count: resampled to it (None keeps every point)."""
    bpy = _bpy()
    lbl = name or (os.path.basename(src) if isinstance(src, str) else _label(src) if not isinstance(src, np.ndarray)
                   else 'points')
    P = C = None
    srcobj = None
    if isinstance(src, str):
        path = _resolve_path(src)
        ext = os.path.splitext(path)[1].lower()
        if ext == '.ply':
            before = set(bpy.data.objects)
            bpy.ops.wm.ply_import(filepath=path)
            new = [o for o in bpy.data.objects if o not in before]
            t = from_point_cloud(new[0], count, colors, seed, lbl)
            for o in new:
                o.hide_render = o.hide_viewport = True
            t.source = new[0]
            return t
        if ext == '.npy':
            arr = np.load(path)
        else:
            rows = []
            with open(path, encoding='utf-8', errors='replace') as f:
                for ln in f:
                    parts = ln.replace(',', ' ').split()
                    try:
                        rows.append([float(x) for x in parts[:6]])
                    except ValueError:
                        continue
            w = min(len(r) for r in rows) if rows else 3
            arr = np.array([r[:w] for r in rows], dtype=np.float64)
        src = arr
    if isinstance(src, (np.ndarray, list, tuple)) and not hasattr(src, 'bl_rna'):
        arr = np.asarray(src, dtype=np.float64)
        arr = arr.reshape(-1, arr.shape[-1] if arr.ndim == 2 and arr.shape[-1] in (3, 6) else 3)
        P = arr[:, :3]
        if colors and arr.shape[1] >= 6:
            c = arr[:, 3:6]
            if c.max() > 1.5:
                c = c / 255.0
            C = srgb_to_linear(c).astype(np.float32)
    else:
        srcobj = src
        pcs = _pieces(src, with_materials=False)
        P = np.concatenate([pc.verts for pc in pcs], axis=0) if pcs else np.zeros((0, 3))
        if colors and pcs and all(pc.col is not None and pc.col_domain == 'POINT' for pc in pcs):
            C = np.concatenate([pc.col for pc in pcs], axis=0)
    t = Target(P.astype(np.float32), C, None, lbl, srcobj)
    if count is not None and int(count) != len(t):
        from .particle_morph import JSRandom
        t = t.resample(int(count), JSRandom(seed))
    return t


# ------------------------------------------------------------------------------------------------- from_file ---

MODEL_EXTS = ('.glb', '.gltf', '.fbx', '.obj', '.vrm', '.stl', '.usd', '.usda', '.usdc', '.usdz', '.abc', '.blend',
              '.dae', '.x3d', '.wrl')
IMAGE_EXTS = ('.png', '.jpg', '.jpeg', '.webp', '.tga', '.bmp', '.exr', '.hdr', '.tif', '.tiff')
POINT_EXTS = ('.ply', '.npy', '.xyz', '.txt', '.csv', '.pts')


def _repo():
    from .. import common
    return common


def _resolve_path(p):
    """'asset:<path under eidoverse/assets>', 'model:<name>' (model_path), a repository-relative path, or an
    absolute path."""
    common = _repo()
    if p.startswith('asset:'):
        return os.path.join(common.ASSETS_DIR, p[6:])
    if p.startswith('model:'):
        return model_path(p[6:])
    if os.path.isabs(p) or os.path.exists(p):
        return p
    return common.repo_path(p)


def model_path(name):
    """A model of the repo's own library (eidoverse/assets/models/*.glb) by its file name, with or without .glb, or by
    a part of the name that only one model has ('crow' -> crow_bird_animated_corvid_..., 'camp_fire')."""
    d = os.path.join(_repo().ASSETS_DIR, 'models')
    stem = name[:-4] if name.lower().endswith(('.glb', '.fbx', '.obj')) else name
    files = sorted(f for f in os.listdir(d) if f.lower().endswith(('.glb', '.gltf', '.fbx', '.obj')))
    exact = [f for f in files if os.path.splitext(f)[0] == stem]
    if exact:
        return os.path.join(d, exact[0])
    key = stem.lower()
    words = [w for w in key.replace('-', '_').replace(' ', '_').split('_') if w]
    hits = []
    for rule in (lambda f: all(w in os.path.splitext(f)[0].lower().split('_') for w in words),   # whole words
                 lambda f: key in f.lower()):                                                    # any part
        hits = [f for f in files if rule(f)]
        if hits:
            break
    if len(hits) == 1:
        return os.path.join(d, hits[0])
    if not hits:
        raise FileNotFoundError(f"[particle_targets] model:{name}: no model in eidoverse/assets/models has that name")
    raise ValueError(f"[particle_targets] model:{name} matches {len(hits)} models, name one: {hits[:8]}")


def load_model(spec, hide=True, location=(0.0, 0.0, 0.0), clip=None):
    """Import a model for use as a target and return its root (an Object, or a VRMHandle for VRMs):
    'polyhaven:<id>[:<res>]' (the shared library, fetched once), 'model:<name>' (the repo's eidoverse/assets/models),
    'vrm:<name>' (eidoverse/assets/vrms), 'asset:<path>', or a .glb / .gltf / .fbx / .obj / .vrm / .stl / .usd* /
    .abc / .dae / .blend path. hide: the model is hidden in the viewport and the render (the cloud stands for it);
    its objects stay evaluable for sampling. clip: play the model's own animation (an index or a name, 'all';
    harness.assets.play_model_animations), or a VRM's VRMA slot (characters.play_vrma_default), over the scene's
    range."""
    bpy = _bpy()
    if spec.startswith('polyhaven:'):
        from ..harness import assets
        parts = spec.split(':')
        path = assets.fetch_model_file(parts[1], parts[2] if len(parts) > 2 else '1k')
        root = assets.import_model(path, location=location)
    elif spec.startswith('vrm:') or spec.lower().endswith('.vrm'):
        from ..characters import load_vrm
        name = spec[4:] if spec.startswith('vrm:') else _resolve_path(spec)
        root = load_vrm(name, location=location)
    else:
        path = _resolve_path(spec)
        ext = os.path.splitext(path)[1].lower()
        if ext in ('.glb', '.gltf', '.fbx', '.obj'):
            from ..harness import assets
            root = assets.import_model(path, location=location)
        else:
            before = set(bpy.data.objects)
            coll = bpy.data.collections.new(os.path.splitext(os.path.basename(path))[0])
            bpy.context.scene.collection.children.link(coll)
            if ext == '.stl':
                bpy.ops.wm.stl_import(filepath=path)
            elif ext in ('.usd', '.usda', '.usdc', '.usdz'):
                bpy.ops.wm.usd_import(filepath=path)
            elif ext == '.abc':
                bpy.ops.wm.alembic_import(filepath=path)
            elif ext == '.ply':
                bpy.ops.wm.ply_import(filepath=path)
            elif ext == '.dae':
                bpy.ops.wm.collada_import(filepath=path)
            elif ext == '.blend':
                with bpy.data.libraries.load(path) as (src, dst):
                    dst.objects = list(src.objects)
                for o in dst.objects:
                    if o is not None:
                        coll.objects.link(o)
            else:
                raise ValueError(f'[particle_targets] load_model: {ext} is not a model format here')
            new = [o for o in bpy.data.objects if o not in before]
            for o in new:
                for c in list(o.users_collection):
                    if c is not coll:
                        c.objects.unlink(o)
                if coll not in o.users_collection:
                    coll.objects.link(o)
            root = bpy.data.objects.new(coll.name, None)
            coll.objects.link(root)
            for o in new:
                if o.parent is None:
                    o.parent = root
            root.location = location
    if clip is not None:
        if hasattr(root, 'meshes') and hasattr(root, 'arm'):
            from ..characters import play_vrma_default
            play_vrma_default(root, clip)
        else:
            from ..harness import assets
            if not assets.play_model_animations(root, clip=clip):
                print(f'[particle_targets] load_model {spec}: no animation clip {clip!r} to play')
    if hide:
        set_visible(root, False)
    return root


def set_visible(src, visible):
    """Show or hide a source's objects in the viewport and the render (not keyed; see particle_morph.key_visibility).
    Armatures are left alone: they never render, and a hidden armature stops posing its meshes."""
    for o in _objects_of(src):
        if o.type in ('ARMATURE', 'CAMERA'):
            continue
        o.hide_render = not visible
        o.hide_viewport = not visible


def from_file(spec, count, mode=None, colors=True, seed=1, fit_height=None, fit_width=None, fit_size=None,
              at=None, anchor='centroid', rotate=None, live=False, frame=None, hide=True, name=None, alpha_cut=True,
              max_texture=1024, voxel=None, threshold=None, clip=None, **image_opts):
    """A target from a file or a library name: a model (load_model; sampled with from_object: mode 'surface' by
    default, live, frame, alpha_cut, max_texture, voxel; clip plays its own animation first, so live=True follows
    it), an image (from_image: mode 'alpha' by default, threshold and image_opts: width, depth, plane, max_size,
    invert, density), a point cloud (.ply .npy .xyz .csv .txt .pts) or a volume (.vdb, threshold). Then fit_height /
    fit_width / fit_size (metres), rotate (Euler XYZ radians, about the centroid) and at (anchor point: 'centroid',
    'base' or 'center'). The model's root is the Target's .source (hidden by default)."""
    path = spec
    low = spec.lower()
    if low.startswith(('polyhaven:', 'vrm:', 'model:')) or low.endswith(MODEL_EXTS):
        root = load_model(spec, hide=hide, clip=clip)
        t = from_object(root, count, mode=mode or 'surface', live=live, frame=frame, colors=colors, seed=seed,
                        alpha_cut=alpha_cut, max_texture=max_texture, voxel=voxel,
                        name=name or os.path.basename(spec))
        t.source = root
    elif low.endswith(IMAGE_EXTS):
        t = from_image(path, count, mode=mode or 'alpha', threshold=0.5 if threshold is None else threshold,
                       colors=colors, seed=seed, name=name, **image_opts)
    elif low.endswith('.vdb'):
        t = from_volume(_resolve_path(path), count, threshold=0.05 if threshold is None else threshold, seed=seed,
                        name=name)
    elif low.endswith(POINT_EXTS):
        t = from_point_cloud(path, count, colors=colors, seed=seed, name=name)
    else:
        raise ValueError(f'[particle_targets] from_file: what is {spec!r}? (a model, image, point cloud or .vdb)')
    return place(t, fit_height=fit_height, fit_width=fit_width, fit_size=fit_size, rotate=rotate, at=at,
                 anchor=anchor)


def place(t, fit_height=None, fit_width=None, fit_size=None, rotate=None, at=None, anchor='centroid'):
    """Fit, rotate and move a target (in that order)."""
    if fit_height is not None or fit_width is not None or fit_size is not None:
        t = t.fit(height=fit_height, width=fit_width, size=fit_size)
    if rotate is not None:
        t = t.rotated(rotate)
    if at is not None:
        t = t.at(at, anchor)
    return t


# ----------------------------------------------------------------------------------------------------- shapes ---

def _basis(normal):
    n = np.asarray(normal, dtype=np.float64)
    n = n / (np.linalg.norm(n) or 1.0)
    a = np.array([0.0, 0.0, 1.0]) if abs(n[2]) < 0.9 else np.array([1.0, 0.0, 0.0])
    u = np.cross(a, n)
    u /= np.linalg.norm(u)
    v = np.cross(n, u)
    return u, v, n


def _gradient(t, colors):
    if colors is None:
        return None
    from ._util import color
    cs = [np.asarray(color(c), np.float32) for c in colors]
    t = np.clip(np.asarray(t, np.float64), 0, 1)
    if len(cs) == 1:
        return np.broadcast_to(cs[0], (len(t), 3)).copy()
    x = t * (len(cs) - 1)
    i = np.minimum(x.astype(np.int64), len(cs) - 2)
    f = (x - i)[:, None]
    stack = np.stack(cs)
    return (stack[i] * (1 - f) + stack[i + 1] * f).astype(np.float32)


class shapes:
    """The shapes the films hand-rolled for ParticleMorph.fromPoints, as targets (Blender coordinates, centred on
    `center`). Each takes count, seed and colors (a gradient: one colour, or two or more along the shape's natural
    parameter: radius, height, arm, ...; None = the morph's color / color2)."""

    @staticmethod
    def sphere(count, radius=1.0, center=(0, 0, 0), shell=True, colors=None, seed=1):
        rng = np.random.default_rng(seed)
        d = rng.normal(size=(int(count), 3))
        d /= np.linalg.norm(d, axis=1, keepdims=True)
        r = radius if shell else radius * np.cbrt(rng.random(int(count)))[:, None]
        P = d * r + np.asarray(center)
        return Target(P, _gradient((d[:, 2] + 1) / 2, colors), name='sphere')

    @staticmethod
    def scatter(count, size=4.0, center=(0, 0, 0), ball=False, colors=None, seed=1):
        """A random cloud: a box of size (x, y, z) (or a cube), or a ball of radius size / 2."""
        rng = np.random.default_rng(seed)
        s = np.broadcast_to(np.asarray(size, np.float64), (3,))
        if ball:
            d = rng.normal(size=(int(count), 3))
            d /= np.linalg.norm(d, axis=1, keepdims=True)
            P = d * (np.cbrt(rng.random(int(count)))[:, None] * s / 2)
        else:
            P = (rng.random((int(count), 3)) - 0.5) * s
        return Target(P + np.asarray(center), _gradient(rng.random(int(count)), colors), name='scatter')

    @staticmethod
    def galaxy(count, radius=2.2, arms=3, twist=3.0, thickness=0.08, core=0.3, spread=0.35, center=(0, 0, 0),
               normal=(0, 0, 1), colors=None, seed=1):
        """A spiral galaxy: a bright core bulge and `arms` logarithmic arms wound `twist` radians from core to rim,
        in the plane normal to `normal` (default lying flat). colors run core -> rim."""
        rng = np.random.default_rng(seed)
        n = int(count)
        nc = int(n * core)
        u, v, w = _basis(normal)
        r_core = np.abs(rng.normal(scale=radius * 0.12, size=nc))
        th_core = rng.random(nc) * 2 * np.pi
        r = radius * rng.random(n - nc) ** 0.7
        arm = rng.integers(0, max(1, int(arms)), n - nc)
        th = arm * 2 * np.pi / max(1, int(arms)) + twist * (r / radius) + rng.normal(scale=spread, size=n - nc) * \
            (1.0 - 0.5 * r / radius)
        R = np.concatenate([r_core, r])
        TH = np.concatenate([th_core, th])
        h = rng.normal(scale=thickness, size=n) * (1.0 - 0.7 * np.clip(R / radius, 0, 1)) + \
            np.concatenate([rng.normal(scale=radius * 0.06, size=nc), np.zeros(n - nc)])
        P = np.cos(TH)[:, None] * R[:, None] * u + np.sin(TH)[:, None] * R[:, None] * v + h[:, None] * w
        return Target(P + np.asarray(center), _gradient(R / radius, colors), name='galaxy')

    @staticmethod
    def ring(count, radius=1.5, tube=0.04, center=(0, 0, 0), normal=(0, -1, 0), colors=None, seed=1):
        """A thin ring (a portal), standing facing -Y by default."""
        rng = np.random.default_rng(seed)
        u, v, w = _basis(normal)
        th = rng.random(int(count)) * 2 * np.pi
        off = rng.normal(scale=tube, size=(int(count), 3))
        P = np.cos(th)[:, None] * radius * u + np.sin(th)[:, None] * radius * v + off
        return Target(P + np.asarray(center), _gradient(th / (2 * np.pi), colors), name='ring')

    @staticmethod
    def torus(count, radius=1.2, tube=0.35, center=(0, 0, 0), normal=(0, 0, 1), colors=None, seed=1):
        rng = np.random.default_rng(seed)
        u, v, w = _basis(normal)
        n = int(count)
        th = rng.random(n) * 2 * np.pi
        ph = rng.random(n) * 2 * np.pi
        # area-uniform: accept the outer side more often
        keep = rng.random(n) < (radius + tube * np.cos(ph)) / (radius + tube)
        th, ph = th[keep], ph[keep]
        j = np.arange(n) % len(th)
        th, ph = th[j], ph[j]
        rr = radius + tube * np.cos(ph)
        P = (np.cos(th) * rr)[:, None] * u + (np.sin(th) * rr)[:, None] * v + (tube * np.sin(ph))[:, None] * w
        return Target(P + np.asarray(center), _gradient((np.sin(ph) + 1) / 2, colors), name='torus')

    @staticmethod
    def helix(count, radius=0.8, height=3.0, turns=4.0, strands=2, tube=0.03, center=(0, 0, 0), colors=None,
              seed=1):
        """`strands` interleaved helices (2: a double helix) around Z, `height` tall."""
        rng = np.random.default_rng(seed)
        n = int(count)
        t = rng.random(n)
        k = rng.integers(0, max(1, int(strands)), n)
        th = t * turns * 2 * np.pi + k * 2 * np.pi / max(1, int(strands))
        P = np.stack([np.cos(th) * radius, np.sin(th) * radius, (t - 0.5) * height], 1)
        P += rng.normal(scale=tube, size=(n, 3))
        return Target(P + np.asarray(center), _gradient(t, colors), name='helix')

    @staticmethod
    def spiral(count, radius=2.0, turns=3.0, width=0.06, center=(0, 0, 0), normal=(0, -1, 0), colors=None, seed=1):
        """A flat Archimedean spiral (facing -Y by default)."""
        rng = np.random.default_rng(seed)
        u, v, w = _basis(normal)
        t = np.sqrt(rng.random(int(count)))
        th = t * turns * 2 * np.pi
        r = t * radius
        P = np.cos(th)[:, None] * r[:, None] * u + np.sin(th)[:, None] * r[:, None] * v
        P += rng.normal(scale=width, size=(int(count), 3)) * np.array([1, 1, 1]) * 0.5
        return Target(P + np.asarray(center), _gradient(t, colors), name='spiral')

    @staticmethod
    def disc(count, radius=1.5, center=(0, 0, 0), normal=(0, -1, 0), colors=None, seed=1):
        rng = np.random.default_rng(seed)
        u, v, w = _basis(normal)
        r = radius * np.sqrt(rng.random(int(count)))
        th = rng.random(int(count)) * 2 * np.pi
        P = np.cos(th)[:, None] * r[:, None] * u + np.sin(th)[:, None] * r[:, None] * v
        return Target(P + np.asarray(center), _gradient(r / radius, colors), name='disc')

    @staticmethod
    def lattice(count, size=(3.0, 3.0, 3.0), cells=(6, 6, 6), center=(0, 0, 0), jitter=0.015, colors=None, seed=1):
        """Points on the edges of a cubic lattice (a crystal / data grid)."""
        rng = np.random.default_rng(seed)
        n = int(count)
        s = np.asarray(size, np.float64)
        c = np.asarray(cells, np.int64)
        ax = rng.integers(0, 3, n)
        P = np.empty((n, 3))
        for k in range(3):
            node = rng.integers(0, c[k] + 1, n) / c[k]
            P[:, k] = node
        t = rng.random(n)
        P[np.arange(n), ax] = t
        P = (P - 0.5) * s + rng.normal(scale=jitter, size=(n, 3))
        return Target(P + np.asarray(center), _gradient((P[:, 2] / s[2]) + 0.5, colors), name='lattice')

    @staticmethod
    def line(count, a=(-2, 0, 0), b=(2, 0, 0), jitter=0.01, colors=None, seed=1):
        rng = np.random.default_rng(seed)
        t = rng.random(int(count))
        A, B = np.asarray(a, np.float64), np.asarray(b, np.float64)
        P = A + (B - A) * t[:, None] + rng.normal(scale=jitter, size=(int(count), 3))
        return Target(P, _gradient(t, colors), name='line')

    @staticmethod
    def cube(count, size=1.5, center=(0, 0, 0), surface=True, colors=None, seed=1):
        rng = np.random.default_rng(seed)
        n = int(count)
        P = rng.random((n, 3)) - 0.5
        if surface:
            ax = rng.integers(0, 3, n)
            P[np.arange(n), ax] = np.where(rng.random(n) < 0.5, -0.5, 0.5)
        P = P * size
        return Target(P + np.asarray(center), _gradient(P[:, 2] / size + 0.5, colors), name='cube')


SHAPES = ('sphere', 'scatter', 'galaxy', 'ring', 'torus', 'helix', 'spiral', 'disc', 'lattice', 'line', 'cube')


# ------------------------------------------------------------------------------------------------- the resolver ---

def target(spec, count, seed=1, random=None, **opts):
    """Any target spec -> a Target of `count` points:

        a Target                    (resampled to count if it has another size)
        an (m, 3) array, a flat array, [[x, y, z], ...]                  -> resampled (the engine's fromPoints)
        a bpy Object / Collection / VRMHandle / list of them              -> from_object(**opts)
        a bpy Image                                                       -> from_image(**opts)
        'text:HELLO'  'ascii:<art>'  'banner:HELLO'                       -> particle_morph.from_text (+ at, fit)
        'neural_net'  'neuron_graph'                                      -> the engine's generators (opts as theirs)
        'galaxy' 'sphere' 'scatter' 'ring' 'torus' 'helix' 'spiral' 'disc' 'lattice' 'line' 'cube' -> shapes
        'polyhaven:<id>'  'model:<name>'  'vrm:<name>'  'asset:<path>'  a file path   -> from_file(**opts)
        {'text': 'HI', ...}  {'shape': 'galaxy', ...}  {'file': ...}  {'object': obj, ...}  {'image': ...}
        (spec, {opts})                                                    -> the spec with these options

    Common options for the generated kinds: at (move the centroid there), fit_height / fit_width / fit_size, rotate,
    colors (a gradient for shapes, a colour for text: tints every point)."""
    import bpy
    from . import particle_morph as PM
    count = int(count)
    if isinstance(spec, tuple) and len(spec) == 2 and isinstance(spec[1], dict):
        spec, extra = spec
        opts = {**extra, **opts}
    if isinstance(spec, dict):
        d = dict(spec)
        for k in ('text', 'ascii', 'banner', 'shape', 'file', 'object', 'image', 'points', 'volume', 'generator'):
            if k in d:
                v = d.pop(k)
                key = {'text': 'text:', 'ascii': 'ascii:', 'banner': 'banner:'}.get(k)
                if key:
                    return target(key + v, count, seed, random, **{**d, **opts})
                if k in ('shape', 'generator'):
                    return target(v, count, seed, random, **{**d, **opts})
                if k == 'file':
                    return target(v, count, seed, random, **{**d, **opts})
                if k == 'volume':
                    return place(from_volume(v, count, seed=seed, **_pick(d, ('threshold', 'grid', 'colors')),
                                             name=d.get('name')), **_placing({**d, **opts}))
                return target(v, count, seed, random, **{**d, **opts})
        raise ValueError(f'[particle_targets] target dict {spec!r}: give text, ascii, banner, shape, file, object, '
                         f'image, points or volume')
    placing = _placing(opts)
    if isinstance(spec, Target):
        t = spec
        if len(t) != count:
            t = t.resample(count, random, seed)
        return place(t, **placing)
    if isinstance(spec, bpy.types.Image):
        return place(from_image(spec, count, seed=seed, **_pick(opts, _IMAGE_OPTS)), **placing)
    if isinstance(spec, (bpy.types.Object, bpy.types.Collection)) or (hasattr(spec, 'meshes') and hasattr(spec, 'arm')) \
            or (isinstance(spec, (list, tuple)) and spec and not isinstance(spec[0], (int, float, list, tuple,
                                                                                     np.ndarray))):
        return place(from_object(spec, count, seed=seed, **_pick(opts, _OBJECT_OPTS)), **placing)
    if isinstance(spec, str):
        low = spec.lower()
        if low.startswith(('text:', 'ascii:', 'banner:')):
            kind, _, txt = spec.partition(':')
            o = _pick(opts, ('width', 'depth', 'font_size', 'font_family', 'font', 'pixel_stride', 'weight'))
            if 'font' in o:
                o['font_family'] = o.pop('font')
            if kind.lower() == 'banner':
                txt = PM.ascii_banner(txt, **_pick(opts, ('banner_font', 'cell_px', 'fill')))
            pts = PM.from_text(txt, count, o, random=random, seed=seed, ascii=kind.lower() != 'text')
            t = Target(pts, name=spec[:24])
            if opts.get('color') is not None:
                t = t.tinted(opts['color'])
            return place(t, **placing)
        if low in ('neural_net', 'neuralnet'):
            o = _pick(opts, ('layers', 'width', 'height', 'node_r', 'depth_jit', 'node_frac'))
            return place(Target(PM.neural_net(dict(count=count, **o), random=random, seed=seed), name='neural_net'),
                         **placing)
        if low in ('neuron_graph', 'neurongraph'):
            o = _pick(opts, ('nodes', 'rx', 'ry', 'rz', 'k', 'node_frac'))
            return place(Target(PM.neuron_graph(dict(count=count, **o), random=random, seed=seed),
                                name='neuron_graph'), **placing)
        if low in SHAPES:
            fn = getattr(shapes, low)
            import inspect
            names = set(inspect.signature(fn).parameters) - {'count'}
            return place(fn(count, seed=seed, **_pick(opts, names)), **placing)
        return from_file(spec, count, seed=seed, **_pick(opts, _OBJECT_OPTS + _IMAGE_OPTS + ('hide', 'clip')),
                         **placing)
    pts = np.asarray(spec, dtype=np.float32).reshape(-1, 3)
    return place(Target(pts, name='points').resample(count, random, seed), **placing)


_OBJECT_OPTS = ('mode', 'live', 'frame', 'colors', 'alpha_cut', 'max_texture', 'voxel', 'name')
_IMAGE_OPTS = ('width', 'mode', 'threshold', 'depth', 'colors', 'plane', 'max_size', 'invert', 'density', 'name')


def _pick(d, keys):
    return {k: d[k] for k in keys if k in d}


def _placing(opts):
    p = _pick(opts, ('fit_height', 'fit_width', 'fit_size', 'rotate', 'at', 'anchor'))
    return p
