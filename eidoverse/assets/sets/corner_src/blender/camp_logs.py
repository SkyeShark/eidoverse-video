"""camp_logs.py - firewood / bench-log geometry: an irregular round log along its own axis with
bark sides (mat 0), end-grain caps (mat 1) and, optionally, a split face (mat 2). TexUV is written
per face kind: bark = (around, along) so Bark012's vertical furrows run along the log; split =
(along, across) so wood grain runs along it; caps = centred planar 0..1 onto TreeEnd003's disc."""
import bpy, bmesh, math
from mathutils import Vector, Matrix, noise
from clib import *
from camp_lib import *


def log_mesh(name, length, radius, seed=0, bend=0.012, split=None, na=28, nl=20, cut_tilt=0.08,
             mats=None, root_flare=0.0, bark_amp=0.05):
    """Log along +X from -L/2..L/2, axis through the origin.
    split: None | ('half', keep_below=True) keeps the half below the XY-plane (flat face up)."""
    rnd = rng(seed)
    ph = [rnd.uniform(0, 100) for _ in range(6)]

    def axis(x):
        return Vector((x, bend * math.sin(x * 2.1 + ph[0]) * 0.8, bend * math.sin(x * 1.7 + ph[1])))

    def rad(x, a):
        t = (x + length / 2) / length
        r = radius * (1 + 0.05 * math.cos(2 * a + ph[2]) + 0.03 * math.cos(3 * a + ph[3]))
        r *= 1 + bark_amp * noise.noise(Vector((math.cos(a) * 2.5, math.sin(a) * 2.5, x * 4 + ph[4])))
        r *= 1 + 0.035 * noise.noise(Vector((math.cos(a) * 9, math.sin(a) * 9, x * 18 + ph[5])))   # bark plates
        if root_flare:
            r *= 1 + root_flare * max(0.0, 0.25 - t) / 0.25 * (0.7 + 0.3 * math.cos(5 * a))
        return r

    bm = bmesh.new()
    rings = []
    # tilted chainsaw cuts: the end rings sit on slightly rotated planes
    tA = (rnd.uniform(-1, 1) * cut_tilt, rnd.uniform(-1, 1) * cut_tilt)
    tB = (rnd.uniform(-1, 1) * cut_tilt, rnd.uniform(-1, 1) * cut_tilt)
    for i in range(nl + 1):
        x = -length / 2 + length * i / nl
        c = axis(x)
        ring = []
        for j in range(na):
            a = j / na * math.tau
            r = rad(x, a)
            dy, dz = r * math.cos(a), r * math.sin(a)
            xx = x
            if i == 0:
                xx += tA[0] * dy + tA[1] * dz
            if i == nl:
                xx += tB[0] * dy + tB[1] * dz
            ring.append(bm.verts.new((xx, c.y + dy, c.z + dz)))
        rings.append(ring)
    side = []
    for i in range(nl):
        for j in range(na):
            f = bm.faces.new((rings[i][j], rings[i][(j + 1) % na], rings[i + 1][(j + 1) % na], rings[i + 1][j]))
            f.material_index = 0
            side.append(f)
    capA = bm.faces.new(list(reversed(rings[0])))
    capB = bm.faces.new(list(rings[-1]))
    capA.material_index = 1
    capB.material_index = 1
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
    if split:
        geom = bm.verts[:] + bm.edges[:] + bm.faces[:]
        res = bmesh.ops.bisect_plane(bm, geom=geom, plane_co=(0, 0, split.get('z', 0.0)), plane_no=(0, 0, 1),
                                     clear_outer=True, clear_inner=False)
        cut_edges = [e for e in res['geom_cut'] if isinstance(e, bmesh.types.BMEdge)]
        fill = bmesh.ops.edgeloop_fill(bm, edges=cut_edges) if cut_edges else {'faces': []}
        if not fill['faces']:
            fill = bmesh.ops.holes_fill(bm, edges=[e for e in bm.edges if e.is_boundary])
        for f in fill['faces']:
            f.material_index = 2
        bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
        # triangulate the big flat n-gon so the bake/shading is clean
        bmesh.ops.triangulate(bm, faces=[f for f in bm.faces if len(f.verts) > 4])
    o = obj_from_bm(name, bm)
    if mats:
        for m in mats:
            o.data.materials.append(m)
    write_log_uv(o, radius)
    return o


def write_log_uv(o, radius):
    me = o.data
    if 'TexUV' not in me.uv_layers:
        me.uv_layers.new(name='TexUV')
    uvl = me.uv_layers['TexUV']
    for p in me.polygons:
        mi = p.material_index
        cen = p.center
        # end caps: planar in the cap plane, centred on the cap centroid
        if mi == 1:
            n = p.normal
            cen = Vector((cen.x, 0.0, 0.0))          # rings centre on the log axis, not the cap centroid
            u_ax = n.cross(Vector((0, 0, 1)))
            if u_ax.length < 1e-3:
                u_ax = n.cross(Vector((0, 1, 0)))
            u_ax.normalize()
            v_ax = n.cross(u_ax).normalized()
            for li in p.loop_indices:
                d = me.vertices[me.loops[li].vertex_index].co - cen
                uvl.data[li].uv = (0.5 + d.dot(u_ax) * 0.45 / radius, 0.5 + d.dot(v_ax) * 0.45 / radius)
            continue
        ac = math.atan2(cen.z, cen.y)
        for li in p.loop_indices:
            co = me.vertices[me.loops[li].vertex_index].co
            if mi == 2:
                uvl.data[li].uv = (co.x, co.y)
            else:
                a = math.atan2(co.z, co.y)
                if a - ac > math.pi: a -= math.tau
                if ac - a > math.pi: a += math.tau
                uvl.data[li].uv = (a * radius, co.x)


def endgrain_clamp(mat):
    for n in mat.node_tree.nodes:
        if n.type == 'TEX_IMAGE':
            n.extension = 'EXTEND'
    return mat


def place_log(o, a, b):
    """Rotate/translate a +X log (built centred at the origin) so it spans point a -> point b."""
    a, b = Vector(a), Vector(b)
    d = b - a
    q = Vector((1, 0, 0)).rotation_difference(d.normalized())
    o.rotation_mode = 'QUATERNION'
    o.rotation_quaternion = q
    o.location = (a + b) / 2
    select_only(o)
    bpy.ops.object.transform_apply(location=True, rotation=True, scale=True)
    return o
