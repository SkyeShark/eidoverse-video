"""eidoblend.course.csg: three-bvh-csg's boolean operations on Blender meshes, the two HOLLOW ones included.

    from eidoblend.course import csg
    cut = csg.evaluate(body, bore, csg.SUBTRACTION)                 # a new object: body minus bore (body untouched)
    shell = csg.evaluate(dome_skin, window, csg.HOLLOW_SUBTRACTION) # the open skin with a hole, no cap from the cutter
    live = csg.evaluate(body, bore, csg.HOLLOW_INTERSECTION, live=True)   # a Geometry Nodes modifier on body: moving
                                                                    # or keying bore re-cuts every frame
    csg.compute_mesh_volume(cut)                                    # m^3, world scale

The operations (three-bvh-csg's constants, the same names):
    ADDITION              A u B
    SUBTRACTION           A - B
    REVERSE_SUBTRACTION   B - A
    INTERSECTION          A n B
    DIFFERENCE            A xor B: the boundary of (A - B) and (B - A) together (three-bvh-csg's triangle rule:
                          A outside B kept, A inside B kept inverted, and the same for B)
    HOLLOW_SUBTRACTION    A's surface OUTSIDE B, and nothing of B: no cap where B cut. A may be an open surface
                          (a skin, a terrain, a sail); B must be a closed solid.
    HOLLOW_INTERSECTION   A's surface INSIDE B, nothing of B.
Each runs as a Geometry Nodes Mesh Boolean in A's space with B read through Object Info (relative), so B's transform
is honoured as three-bvh-csg reads a brush's world matrix (no updateMatrixWorld step to forget). For the HOLLOW ones
A's faces are tagged, the boolean runs (EXACT, hole tolerant, which lets A be open), and every face not from A is
deleted. live=False (default) bakes the result into a new mesh object; live=True leaves the modifier on A.

Evaluator mirrors three-bvh-csg's class: Evaluator(use_groups=True).evaluate(a, b, op). use_groups=True keeps each
input's materials on its faces (three's groups); False gives the whole result A's first material. Chain by feeding a
result back in as A or B. solver: 'EXACT' (default; any input, the only one that takes an open A), 'MANIFOLD' (fast,
watertight inputs only), 'FLOAT' (fast, fragile).
"""
import bmesh
import bpy

ADDITION = 'ADDITION'
SUBTRACTION = 'SUBTRACTION'
REVERSE_SUBTRACTION = 'REVERSE_SUBTRACTION'
INTERSECTION = 'INTERSECTION'
DIFFERENCE = 'DIFFERENCE'
HOLLOW_SUBTRACTION = 'HOLLOW_SUBTRACTION'
HOLLOW_INTERSECTION = 'HOLLOW_INTERSECTION'
OPERATIONS = (ADDITION, SUBTRACTION, REVERSE_SUBTRACTION, INTERSECTION, DIFFERENCE, HOLLOW_SUBTRACTION,
              HOLLOW_INTERSECTION)
TAG = 'eido_csg_from_a'


class _Tree:
    def __init__(self, name):
        self.ng = bpy.data.node_groups.new(name, 'GeometryNodeTree')
        self.ng.interface.new_socket('Geometry', in_out='INPUT', socket_type='NodeSocketGeometry')
        self.ng.interface.new_socket('Geometry', in_out='OUTPUT', socket_type='NodeSocketGeometry')
        self.n = self.ng.nodes
        self.l = self.ng.links
        self.gin = self.n.new('NodeGroupInput')
        self.gout = self.n.new('NodeGroupOutput')
        self.x = 0

    def node(self, idname, **props):
        nd = self.n.new(idname)
        for k, v in props.items():
            setattr(nd, k, v)
        self.x += 180
        nd.location = (self.x, 0)
        return nd

    def obj(self, ob):
        oi = self.node('GeometryNodeObjectInfo', transform_space='RELATIVE')
        oi.inputs['Object'].default_value = ob
        return oi.outputs['Geometry']

    def boolean(self, op, mesh1, mesh2s, solver, hole_tolerant=False):
        bn = self.node('GeometryNodeMeshBoolean', operation=op, solver=solver)
        if mesh1 is not None:
            self.l.new(mesh1, bn.inputs['Mesh 1'])
        for m in mesh2s:
            self.l.new(m, bn.inputs['Mesh 2'])
        if solver == 'EXACT':
            bn.inputs['Hole Tolerant'].default_value = hole_tolerant
        return bn.outputs['Mesh']

    def tag(self, geo):
        st = self.node('GeometryNodeStoreNamedAttribute', data_type='BOOLEAN', domain='FACE')
        self.l.new(geo, st.inputs['Geometry'])
        st.inputs['Name'].default_value = TAG
        st.inputs['Value'].default_value = True
        return st.outputs['Geometry']

    def keep_tagged(self, geo):
        na = self.node('GeometryNodeInputNamedAttribute', data_type='BOOLEAN')
        na.inputs['Name'].default_value = TAG
        nt = self.node('FunctionNodeBooleanMath', operation='NOT')
        self.l.new(na.outputs['Attribute'], nt.inputs[0])
        dl = self.node('GeometryNodeDeleteGeometry', domain='FACE', mode='ALL')
        self.l.new(geo, dl.inputs['Geometry'])
        self.l.new(nt.outputs[0], dl.inputs['Selection'])
        ra = self.node('GeometryNodeRemoveAttribute')
        self.l.new(dl.outputs['Geometry'], ra.inputs['Geometry'])
        ra.inputs['Name'].default_value = TAG
        return ra.outputs['Geometry']

    def one_material(self, geo, mat):
        sm = self.node('GeometryNodeSetMaterial')
        self.l.new(geo, sm.inputs['Geometry'])
        sm.inputs['Material'].default_value = mat
        return sm.outputs['Geometry']

    def out(self, geo):
        self.l.new(geo, self.gout.inputs[0])


def _tree(a, b, op, solver, use_groups):
    if op not in OPERATIONS:
        raise ValueError('unknown CSG operation %r (one of %s)' % (op, ', '.join(OPERATIONS)))
    hollow = op in (HOLLOW_SUBTRACTION, HOLLOW_INTERSECTION)
    if hollow and solver != 'EXACT':
        solver = 'EXACT'                         # only the exact solver takes an open A
    T = _Tree('csg_%s_%s_%s' % (op.lower(), a.name, b.name))
    A = T.gin.outputs[0]
    B = T.obj(b)
    if op == ADDITION:
        r = T.boolean('UNION', None, [A, B], solver)
    elif op == SUBTRACTION:
        r = T.boolean('DIFFERENCE', A, [B], solver)
    elif op == REVERSE_SUBTRACTION:
        r = T.boolean('DIFFERENCE', B, [A], solver)
    elif op == INTERSECTION:
        r = T.boolean('INTERSECT', None, [A, B], solver)
    elif op == DIFFERENCE:
        j = T.node('GeometryNodeJoinGeometry')
        T.l.new(T.boolean('DIFFERENCE', B, [A], solver), j.inputs[0])
        T.l.new(T.boolean('DIFFERENCE', A, [B], solver), j.inputs[0])
        r = j.outputs[0]
    elif op == HOLLOW_SUBTRACTION:
        r = T.keep_tagged(T.boolean('DIFFERENCE', T.tag(A), [B], solver, hole_tolerant=True))
    else:
        r = T.keep_tagged(T.boolean('INTERSECT', None, [T.tag(A), B], solver, hole_tolerant=True))
    if not use_groups and a.data.materials:
        r = T.one_material(r, a.data.materials[0])
    T.out(r)
    return T.ng


def _ensure_slots(a, b):
    """Geometry Nodes keeps each face's material by name; A needs B's materials in its slots to show them"""
    for m in getattr(b.data, 'materials', []):
        if m is not None and m.name not in [s.name for s in a.data.materials if s]:
            a.data.materials.append(m)


def evaluate(a, b, operation, live=False, solver='EXACT', use_groups=True, name=None, hide_b=True):
    """A op B -> the result object (a new object, or A itself with the modifier when live=True).
    hide_b: hide B from the render (three-bvh-csg's brushes are not in the scene; here B stays as the live cutter)."""
    bpy.context.view_layer.update()            # matrix_world is stale right after a transform is set
    ng = _tree(a, b, operation, solver, use_groups)
    if use_groups:
        _ensure_slots(a, b)
    if hide_b:
        b.hide_render = True
        b.display_type = 'WIRE'
    if live:
        md = a.modifiers.new('csg_' + operation.lower(), 'NODES')
        md.node_group = ng
        a['eido_csg'] = operation
        return a
    holder = a.copy()                          # A's own modifiers stay: the boolean takes A as it renders
    holder.data = a.data.copy()
    for c in a.users_collection:
        c.objects.link(holder)
    md = holder.modifiers.new('csg', 'NODES')
    md.node_group = ng
    bpy.context.view_layer.update()
    dg = bpy.context.evaluated_depsgraph_get()
    me = bpy.data.meshes.new_from_object(holder.evaluated_get(dg), preserve_all_data_layers=True, depsgraph=dg)
    me.name = name or '%s_%s' % (a.name, operation.lower())
    res = bpy.data.objects.new(me.name, me)
    res.matrix_world = a.matrix_world.copy()
    for c in a.users_collection:
        c.objects.link(res)
    bpy.data.objects.remove(holder)
    bpy.data.node_groups.remove(ng)
    res['eido_csg'] = operation
    return res


class Evaluator:
    """three-bvh-csg's Evaluator: evaluate(a, b, operation) -> a new object. use_groups as above; solver too."""

    def __init__(self, use_groups=True, solver='EXACT'):
        self.use_groups = use_groups
        self.solver = solver

    def evaluate(self, a, b, operation, live=False, name=None):
        return evaluate(a, b, operation, live=live, solver=self.solver, use_groups=self.use_groups, name=name)


def compute_mesh_volume(obj):
    """three-bvh-csg's computeMeshVolume: the enclosed volume (m^3) of obj's evaluated mesh, with its world scale.
    Meaningful for a closed mesh only."""
    dg = bpy.context.evaluated_depsgraph_get()
    ev = obj.evaluated_get(dg)
    me = ev.to_mesh()
    try:
        bm = bmesh.new()
        bm.from_mesh(me)
        bm.transform(obj.matrix_world)
        v = abs(bm.calc_volume(signed=False))
        bm.free()
    finally:
        ev.to_mesh_clear()
    return v


def union_all(objs, name='union', solver='EXACT'):
    """ADDITION over many objects at once: their meshes joined in world space and unioned with self intersection
    (one boolean instead of a chain). Returns a new object; the inputs are removed."""
    bpy.context.view_layer.update()            # matrix_world is stale right after a transform is set
    bm = bmesh.new()
    mats = []
    for o in objs:
        me = o.data
        tmp = bmesh.new()
        tmp.from_mesh(me)
        tmp.transform(o.matrix_world)
        offset = len(mats)
        for m in me.materials:
            mats.append(m)
        for f in tmp.faces:
            f.material_index += offset
        tmp_me = bpy.data.meshes.new('_tmp_union')
        tmp.to_mesh(tmp_me)
        tmp.free()
        bm.from_mesh(tmp_me)
        bpy.data.meshes.remove(tmp_me)
    me = bpy.data.meshes.new(name)
    bm.to_mesh(me)
    bm.free()
    for m in mats:
        me.materials.append(m)
    ob = bpy.data.objects.new(name, me)
    for c in objs[0].users_collection:
        c.objects.link(ob)
    T = _Tree('csg_union_' + name)
    bn = T.node('GeometryNodeMeshBoolean', operation='UNION', solver=solver)
    T.l.new(T.gin.outputs[0], bn.inputs['Mesh 2'])
    if solver == 'EXACT':
        bn.inputs['Self Intersection'].default_value = True
    T.out(bn.outputs['Mesh'])
    md = ob.modifiers.new('csg_union', 'NODES')
    md.node_group = T.ng
    bpy.context.view_layer.update()
    dg = bpy.context.evaluated_depsgraph_get()
    out = bpy.data.meshes.new_from_object(ob.evaluated_get(dg), preserve_all_data_layers=True, depsgraph=dg)
    ob.modifiers.clear()
    old = ob.data
    ob.data = out
    out.name = name
    bpy.data.meshes.remove(old)
    bpy.data.node_groups.remove(T.ng)
    for o in objs:
        bpy.data.objects.remove(o)
    return ob
