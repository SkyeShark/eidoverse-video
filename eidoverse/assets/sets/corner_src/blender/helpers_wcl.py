"""helpers_wcl.py - extra modelling / look-dev helpers for the window, curtain and laptop builds.
(clib.py stays untouched; these sit on top of it.)"""
import bpy, bmesh, math, os
from mathutils import Vector, Matrix
from clib import *


# ------------------------------------------------------------------------------ bmesh helpers
def grid_slab(bm, xs, zs, holes, y0, y1):
    """A slab whose room face (y0, facing -Y) is the grid xs x zs; cells (i, j) in `holes` are
    through-openings. ONE closed mass with shared verts (front, back, outer walls, opening walls).
    xs/zs ascending breakpoints; cell (i, j) spans xs[i]..xs[i+1], zs[j]..zs[j+1]."""
    nx, nz = len(xs), len(zs)
    F = [[bm.verts.new((xs[i], y0, zs[j])) for j in range(nz)] for i in range(nx)]
    B = [[bm.verts.new((xs[i], y1, zs[j])) for j in range(nz)] for i in range(nx)]
    solid = lambda i, j: 0 <= i < nx - 1 and 0 <= j < nz - 1 and (i, j) not in holes
    for i in range(nx - 1):
        for j in range(nz - 1):
            if not solid(i, j):
                continue
            bm.faces.new((F[i][j], F[i + 1][j], F[i + 1][j + 1], F[i][j + 1]))
            bm.faces.new((B[i][j], B[i][j + 1], B[i + 1][j + 1], B[i + 1][j]))
            # walls where the neighbour is empty
            if not solid(i - 1, j):
                bm.faces.new((F[i][j], F[i][j + 1], B[i][j + 1], B[i][j]))
            if not solid(i + 1, j):
                bm.faces.new((F[i + 1][j], B[i + 1][j], B[i + 1][j + 1], F[i + 1][j + 1]))
            if not solid(i, j - 1):
                bm.faces.new((F[i][j], B[i][j], B[i + 1][j], F[i + 1][j]))
            if not solid(i, j + 1):
                bm.faces.new((F[i][j + 1], F[i + 1][j + 1], B[i + 1][j + 1], B[i][j + 1]))
    bmesh.ops.remove_doubles(bm, verts=bm.verts, dist=1e-7)
    loose = [v for v in bm.verts if not v.link_faces]
    bmesh.ops.delete(bm, geom=loose, context='VERTS')
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
    return bm


def bevel_edges(bm, pred, offset, segments=3, profile=0.5):
    """bmesh bevel of the edges whose two verts satisfy pred(co_a, co_b)."""
    es = [e for e in bm.edges if pred(e.verts[0].co, e.verts[1].co)]
    if es:
        bmesh.ops.bevel(bm, geom=es, offset=offset, offset_type='OFFSET', segments=segments,
                        profile=profile, affect='EDGES', clamp_overlap=True)
    return len(es)


def box_obj(name, x0, x1, y0, y1, z0, z1, mat=None):
    bm = bmesh.new()
    bm_box(bm, x1 - x0, y1 - y0, z1 - z0, (x0 + x1) / 2, (y0 + y1) / 2, (z0 + z1) / 2)
    return bm


def polygon_prism(bm, pts2d, z0, z1):
    """Closed prism from a CCW outline in XY between z0 and z1."""
    lo = [bm.verts.new((x, y, z0)) for x, y in pts2d]
    hi = [bm.verts.new((x, y, z1)) for x, y in pts2d]
    n = len(pts2d)
    bm.faces.new(list(reversed(lo)))
    bm.faces.new(hi)
    for i in range(n):
        j = (i + 1) % n
        bm.faces.new((lo[i], lo[j], hi[j], hi[i]))
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
    return lo, hi


def rounded_rect_pts(w, d, r, segs=8, cx=0.0, cy=0.0):
    pts = []
    for k, (sx, sy) in enumerate(((1, 1), (-1, 1), (-1, -1), (1, -1))):
        ccx, ccy = cx + sx * (w / 2 - r), cy + sy * (d / 2 - r)
        a0 = k * math.pi / 2
        for s in range(segs + 1):
            a = a0 + s * (math.pi / 2) / segs
            pts.append((ccx + r * math.cos(a), ccy + r * math.sin(a)))
    return pts


def boolean(o, cutter, op='DIFFERENCE', solver='EXACT'):
    m = o.modifiers.new('bool', 'BOOLEAN')
    m.operation = op
    m.object = cutter
    m.solver = solver
    select_only(o)
    bpy.ops.object.modifier_apply(modifier=m.name)
    bpy.data.objects.remove(cutter)
    return o


def cutter_box(x0, x1, y0, y1, z0, z1):
    bm = bmesh.new()
    bm_box(bm, x1 - x0, y1 - y0, z1 - z0, (x0 + x1) / 2, (y0 + y1) / 2, (z0 + z1) / 2)
    return obj_from_bm('cutter', bm)


def cutter_cyl(r, length, center, axis='X', segs=48):
    bm = bmesh.new()
    bmesh.ops.create_cone(bm, cap_ends=True, cap_tris=False, segments=segs, radius1=r, radius2=r, depth=length)
    o = obj_from_bm('cutter_c', bm)
    if axis == 'X':
        o.rotation_euler = (0, math.radians(90), 0)
    elif axis == 'Y':
        o.rotation_euler = (math.radians(90), 0, 0)
    o.location = center
    select_only(o)
    bpy.ops.object.transform_apply(location=True, rotation=True, scale=True)
    return o


def xform(o, loc=(0, 0, 0), rot=(0, 0, 0), scale=None):
    o.location = loc
    o.rotation_euler = rot
    if scale is not None:
        o.scale = scale
    select_only(o)
    bpy.ops.object.transform_apply(location=True, rotation=True, scale=True)
    return o


def delete_faces(o, pred):
    """Delete faces whose centre satisfies pred(center, normal) (buried faces)."""
    bm = bmesh.new()
    bm.from_mesh(o.data)
    bm.normal_update()
    bm.faces.ensure_lookup_table()
    fs = [f for f in bm.faces if pred(f.calc_center_median(), f.normal)]
    bmesh.ops.delete(bm, geom=fs, context='FACES')
    bm.to_mesh(o.data)
    bm.free()
    o.data.update()
    return len(fs)


def uv_planar(o, name, axis_u=0, axis_v=2, box=None):
    """Planar 0..1 UV over the object's bbox (for engine-driven surfaces)."""
    me = o.data
    if name not in me.uv_layers:
        me.uv_layers.new(name=name)
    uvl = me.uv_layers[name]
    cos = [v.co for v in me.vertices]
    if box is None:
        umin = min(c[axis_u] for c in cos); umax = max(c[axis_u] for c in cos)
        vmin = min(c[axis_v] for c in cos); vmax = max(c[axis_v] for c in cos)
    else:
        umin, umax, vmin, vmax = box
    for poly in me.polygons:
        for li in poly.loop_indices:
            c = me.vertices[me.loops[li].vertex_index].co
            uvl.data[li].uv = ((c[axis_u] - umin) / (umax - umin), (c[axis_v] - vmin) / (vmax - vmin))


# ------------------------------------------------------------------------- material layers
def post_layer(mat, which, mask_fn, value, mode='MIX'):
    """Insert an extra layer before OUT_COLOR / OUT_ROUGH / OUT_METAL.
    mask_fn(nb) -> float socket (0..1). value: tuple color or float."""
    nb = NB(mat)
    rr = nb.N.get({'color': 'OUT_COLOR', 'rough': 'OUT_ROUGH', 'metal': 'OUT_METAL'}[which])
    src = rr.inputs[0].links[0].from_socket
    nb.L.remove(rr.inputs[0].links[0])
    mask = mask_fn(nb)
    if isinstance(value, (int, float)):
        value = (value, value, value)
    out = nb.mix(mask, src, tuple(value), mode)
    nb.l(out, rr.inputs[0])
    return mat


def obj_sep(nb):
    oc = nb.n('ShaderNodeTexCoord').outputs['Object']
    sep = nb.n('ShaderNodeSeparateXYZ')
    nb.l(oc, sep.inputs[0])
    return oc, sep


def maprange(nb, sock, a, b):
    """0 at a, 1 at b, clamped - works for ANY range (ColorRamp positions clamp to [0,1], so
    nb.ramp() silently breaks on coordinates outside 0..1; use this for object/UV metres)."""
    m = nb.n('ShaderNodeMapRange', clamp=True)
    m.inputs['From Min'].default_value = a
    m.inputs['From Max'].default_value = b
    m.inputs['To Min'].default_value = 0.0
    m.inputs['To Max'].default_value = 1.0
    nb.l(sock, m.inputs['Value'])
    return m.outputs['Result']


def band(nb, sock, a0, a1, b0, b1):
    """1 inside [a1, b0], ramps 0->1 over a0..a1 and 1->0 over b0..b1 (any units)."""
    return nb.math('MULTIPLY', maprange(nb, sock, a0, a1), maprange(nb, sock, b1, b0))


# --------------------------------------------------------------------------------- lookdev
def lit_closeup(filename, cam_pos, target, lens=50, size=768, samples=64, key=None, fill=None, rim=None,
                world=(0.35, 0.38, 0.45, 0.25), extra=()):
    """Closeup render with a real light rig (clib.closeup has none)."""
    sc = bpy.context.scene
    sc.cycles.samples = samples
    try:
        sc.cycles.use_denoising = True
    except Exception:
        pass
    sc.render.resolution_x = size
    sc.render.resolution_y = size
    w = sc.world or bpy.data.worlds.new('w')
    sc.world = w
    w.use_nodes = True
    w.node_tree.nodes['Background'].inputs['Color'].default_value = (*world[:3], 1)
    w.node_tree.nodes['Background'].inputs['Strength'].default_value = world[3]
    tgt = Vector(target)
    made = []
    for spec in (key, fill, rim, *extra):
        if spec is None:
            continue
        pos, energy, size_l, col = spec
        ld = bpy.data.lights.new('cl', 'AREA')
        ld.energy = energy
        ld.size = size_l
        ld.color = col
        lo = bpy.data.objects.new('cl', ld)
        link(lo)
        lo.location = Vector(pos)
        lo.rotation_euler = (tgt - lo.location).to_track_quat('-Z', 'Y').to_euler()
        made.append(lo)
    cd = bpy.data.cameras.new('cu')
    cd.lens = lens
    cd.clip_start = 0.005
    cam = bpy.data.objects.new('cu', cd)
    link(cam)
    cam.location = Vector(cam_pos)
    cam.rotation_euler = (tgt - cam.location).to_track_quat('-Z', 'Y').to_euler()
    sc.camera = cam
    sc.render.filepath = os.path.join(PREV, f'{filename}.png')
    bpy.ops.render.render(write_still=True)
    bpy.data.objects.remove(cam)
    for lo in made:
        bpy.data.objects.remove(lo)
    print(f'[wcl] closeup {sc.render.filepath}', flush=True)
    return sc.render.filepath


def sheet(paths, out, cols=2, size=None):
    from PIL import Image
    ims = [Image.open(p).convert('RGB') for p in paths]
    w, h = ims[0].size
    rows = (len(ims) + cols - 1) // cols
    s = Image.new('RGB', (w * cols, h * rows), (20, 20, 20))
    for i, im in enumerate(ims):
        s.paste(im, ((i % cols) * w, (i // cols) * h))
    s.save(os.path.join(PREV, out))
    return os.path.join(PREV, out)


def bury(bm, *preds):
    """Delete buried faces on a bmesh BEFORE bevelling (so their edges stay unbevelled)."""
    bm.normal_update()
    fs = [f for f in bm.faces if any(p(f.calc_center_median(), f.normal) for p in preds)]
    if fs:
        bmesh.ops.delete(bm, geom=fs, context='FACES_ONLY')
    return len(fs)


def strip_uv(o, keep=('BakeUV', 'TexUV')):
    """Drop stray UV maps (curve->mesh, primitive ops and booleans add 'UVMap') so the exported
    mesh carries BakeUV alone as TEXCOORD_0."""
    me = o.data
    for uvl in [u for u in me.uv_layers if u.name not in keep]:
        me.uv_layers.remove(uvl)
    return [u.name for u in me.uv_layers]


def reencode_jpeg(key, which='normal', quality=85):
    """Re-save a baked JPEG smaller and reload it before export (the exporter embeds the file)."""
    from PIL import Image
    path = os.path.join(BAKED, f'{key}_{which}.jpg')
    Image.open(path).convert('RGB').save(path, quality=quality)
    for im in bpy.data.images:
        if im.filepath and os.path.normcase(bpy.path.abspath(im.filepath)) == os.path.normcase(path):
            im.reload()
    return os.path.getsize(path)
