"""Make geometry you BUILT look built: texel density and form-following wear (the port of
eidoverse/surface_layers.js).

    from eidoblend.terrain import layer_surface
    layer_surface([basin, steps], metres_per_tile=1.15, grunge={'scale': 0.55, 'seed': 7}, layers=[
        {'mask': 'cavity', 'scale': 0.75, 'color': 0x2b2419, 'roughness': 1.0, 'amount': 0.9,
         'range': (0.15, 0.72), 'grunge': 0.35},
        {'mask': 'edges', 'color': 0xc9bda0, 'roughness': 0.62, 'amount': 0.6, 'range': (0.2, 0.72)},
        {'mask': 'up', 'color': 0x8a7859, 'amount': 0.38, 'power': 3, 'grunge': 0.8},
        {'mask': 'below', 'z': WATERLINE, 'fade': 0.5, 'color': 0x11423c, 'roughness': 0.55, 'amount': 0.85}])

Masks, as the engine's: cavity / crease (concave curvature x `scale` metres), edges (convex),
up (geometry normal z ^ power), slope (1 - |geometry normal z|), below / above (world Z, `z` and `fade`;
the engine's `y`), grunge (seamless fbm alone). Each: smoothstep(range), times the grunge breakup
mix(1, g * 1.6, grunge), times amount; then mixes colour, roughness, metalness over what is under.

What changed in Blender, and why:
  - Curvature: shader nodes have no screen-space derivatives, so curvature is measured on the
    mesh (add_curvature: the engine's dot(dN, dP) / |dP|^2 taken along each triangle's edges with
    its corner normals, per face, in 1/metres: + convex, - concave, a sphere of radius R reads
    2/R) and read with an Attribute node. As in the engine, a bevelled or filleted edge gives the
    band its curvature and a flat-shaded (split-normal) corner gives none: model the fillet.
    It is measured on the mesh as built (the object's scale included); re-run after reshaping.
  - up / slope and the grunge's projection weights read the engine's normalWorldGeometry: the
    smooth interpolated vertex normal, never the shading normal. add_geometry_normal stores the
    mesh's corner normals (object space) as an attribute and the material turns them to world
    space every frame, so a moved or rotated object stays right; a material displacement's bump,
    which Blender folds into Geometry > Normal, never reaches the masks. Without the attribute
    (make_layered_material on a mesh layer_surface never saw) the masks read Geometry > Normal.
  - grunge is the engine's own seamless fbm image (grunge_texture: same LCG, same lattice, same
    rows) on the engine's world-space triplanar: three reads at world (x, -y), (-y, z), (x, z)
    (three's xz, zy, xy), weighted by |normal| / its sum, so the noise holds world scale on every
    face of a rotated or boolean'd solid.
  - layer_surface keeps the source material whole (its normal map, its textures) and inserts the
    layers between what fed the Principled BSDF's Base Color, Roughness and Metallic and the BSDF.
  - The engine ignored metalnessMap once any layer existed; here a base metalness map stays wired.
"""
import math

import bpy
import numpy as np

from ._nodes import Graph, new_material, principled, output
from ._pbr import load_image

MASKS = ('cavity', 'crease', 'edges', 'up', 'slope', 'below', 'above', 'grunge')


def _srgb_to_linear(c):
    return c / 12.92 if c <= 0.04045 else ((c + 0.055) / 1.055) ** 2.4


def _rgb(c):
    """0xRRGGBB (sRGB, like THREE.Color) or an (r, g, b) linear tuple -> linear RGBA."""
    if isinstance(c, int):
        return (_srgb_to_linear(((c >> 16) & 255) / 255), _srgb_to_linear(((c >> 8) & 255) / 255),
                _srgb_to_linear((c & 255) / 255), 1.0)
    c = tuple(c)
    return c[:3] + (1.0,)


# ── what these tools refuse ──────────────────────────────────────────────────────────────────
def fetched_reason(o):
    """Why a mesh is a FETCHED asset these tools must not rewrite (or None)."""
    if any(m.type == 'ARMATURE' for m in o.modifiers):
        return 'skinned (deforms: a bind-pose measurement would be wrong)'
    if o.data and getattr(o.data, 'shape_keys', None):
        return 'has shape keys'
    if o.get('eido_loaded_asset') or (o.data and o.data.get('eido_loaded_asset')):
        return 'loaded asset (GLB/VRM/kit)'
    for s in o.material_slots:
        mt = s.material
        if mt and ('mtoon' in mt.name.lower() or (mt.node_tree and any(
                n.bl_idname == 'ShaderNodeGroup' and n.node_tree and 'mtoon' in n.node_tree.name.lower()
                for n in mt.node_tree.nodes))):
            return 'MToon material (VRM)'
    p = o.parent
    while p is not None:
        if p.get('eido_loaded_asset'):
            return 'child of a loaded asset'
        p = p.parent
    return None


def _meshes(objects, force=False, what='surface_layers'):
    lst = objects if isinstance(objects, (list, tuple, set)) else [objects]
    raw = []
    for o in lst:
        if o is None:
            continue
        for x in [o] + list(o.children_recursive):
            if x.type == 'MESH' and x not in raw:
                raw.append(x)
    out, skipped = [], []
    for m in raw:
        why = fetched_reason(m)
        if why and not force:
            skipped.append('%s: %s' % (m.name, why))
        else:
            out.append(m)
    if skipped:
        print('[%s] skipped %d FETCHED mesh(es): authored UVs/materials that rewriting would corrupt. '
              'Pass only geometry you built:\n  %s' % (what, len(skipped), '\n  '.join(skipped)))
    if force and len(raw) != len(out):
        print('[%s] ⚠ force=True: operating on fetched assets; their authored UVs and materials WILL be '
              'rewritten. This is almost never what you want.' % what)
    return out


# ── 1. texel density ─────────────────────────────────────────────────────────────────────────
def normalize_texel_density(objects, metres_per_tile=1.0, report=True, label='', force=False):
    """Scale each mesh's existing UVs so one texture tile spans `metres_per_tile` metres of surface,
    measured as the MEDIAN uv-per-metre over its triangles in world space (so a scaled copy is
    measured at the size it appears). Islands keep their layout; only their scale moves. A mesh
    shared by objects at another density gets a single-user copy. Returns rows of
    {'name', 'before', 'after', 'k'}."""
    target = 1.0 / metres_per_tile
    rows = []
    bpy.context.view_layer.update()          # world sizes: matrix_world is stale right after a move
    for o in _meshes(objects, force, 'normalize_texel_density'):
        me = o.data
        uvl = me.uv_layers.active
        if uvl is None:
            rows.append({'name': o.name, 'before': None, 'after': None, 'note': 'no UVs'})
            continue
        me.calc_loop_triangles()
        nt = len(me.loop_triangles)
        co = np.empty(len(me.vertices) * 3)
        me.vertices.foreach_get('co', co)
        co = co.reshape(-1, 3)
        M = np.array(o.matrix_world)
        co = co @ M[:3, :3].T + M[:3, 3]
        tv = np.empty(nt * 3, dtype=np.int64)
        me.loop_triangles.foreach_get('vertices', tv)
        tl = np.empty(nt * 3, dtype=np.int64)
        me.loop_triangles.foreach_get('loops', tl)
        uv = np.empty(len(me.loops) * 2)
        uvl.uv.foreach_get('vector', uv)
        uv = uv.reshape(-1, 2)
        P = co[tv.reshape(-1, 3)]
        U = uv[tl.reshape(-1, 3)]
        wa = np.linalg.norm(np.cross(P[:, 1] - P[:, 0], P[:, 2] - P[:, 0]), axis=1) * 0.5
        ua = np.abs((U[:, 1, 0] - U[:, 0, 0]) * (U[:, 2, 1] - U[:, 0, 1])
                    - (U[:, 2, 0] - U[:, 0, 0]) * (U[:, 1, 1] - U[:, 0, 1])) * 0.5
        ok = (wa >= 1e-9) & (ua >= 1e-12)
        if not ok.any():
            rows.append({'name': o.name, 'before': None, 'after': None, 'note': 'no usable UVs'})
            continue
        sc = np.sort(np.sqrt(ua[ok] / wa[ok]))
        median = float(sc[len(sc) >> 1])
        k = target / median
        prev = me.get('eido_texel_uv_per_metre')
        if prev is not None:
            if abs(prev - target) / target < 0.01:
                rows.append({'name': o.name, 'before': median, 'after': target, 'note': 'shared, already normalised'})
                continue
            o.data = me.copy()
            me = o.data
            uvl = me.uv_layers.active
        uvl.uv.foreach_set('vector', (uv * k).ravel())
        me['eido_texel_uv_per_metre'] = target
        rows.append({'name': o.name, 'before': median, 'after': target, 'k': k})
        for s in o.material_slots:
            mt = s.material
            if not mt or not mt.node_tree:
                continue
            for n in mt.node_tree.nodes:
                if n.bl_idname == 'ShaderNodeMapping':
                    scl = n.inputs['Scale'].default_value
                    if any(abs(v - 1) > 1e-3 for v in scl) and not n.inputs['Scale'].is_linked:
                        print("[normalize_texel_density] ⚠ %s: material '%s' has a Mapping scale %s that multiplies "
                              "ON TOP of the normalised UVs; set it to 1 and control tiling with metres_per_tile."
                              % (o.name, mt.name, tuple(round(v, 2) for v in scl)))
                if n.bl_idname == 'ShaderNodeTexImage' and n.extension != 'REPEAT':
                    print("[normalize_texel_density] %s: image '%s' in '%s' does not repeat (%s): set its "
                          "extension to REPEAT if this surface should tile." % (o.name, n.image.name if n.image else '?',
                                                                              mt.name, n.extension))
    if report and rows:
        okr = [r for r in rows if r.get('before') is not None]
        lo = min((r['before'] for r in okr), default=0)
        hi = max((r['before'] for r in okr), default=0)
        print('[normalize_texel_density]%s %d mesh(es) -> %g m/tile. Incoming density spread was %.3f-%.3f uv/m '
              '(%s x mismatch across the set).' % ((' ' + label) if label else '', len(okr), metres_per_tile, lo, hi,
                                                  ('%.1f' % (hi / lo)) if lo > 0 else 'inf'))
    return rows


# ── curvature, measured on the mesh ──────────────────────────────────────────────────────────
def add_curvature(obj, name='eido_curvature'):
    """Store signed curvature (1/metres; + convex, - concave; a sphere of radius R reads 2/R) as a
    CORNER attribute: the engine's measure taken along each triangle's edges instead of screen
    axes, 2 * mean over the edges of dot(n_j - n_i, p_j - p_i) / |p_j - p_i|^2, with the CORNER
    normals (so flat-shaded or sharp-edged caps read zero, like the engine's split normals, and a
    bevel's band reads its curvature), area-averaged per face, then per corner over the faces that
    share its vertex and normal. World scale: the object's scale counts. Returns the per-face values."""
    bpy.context.view_layer.update()          # matrix_world is stale right after a scale is set
    me = obj.data
    me.calc_loop_triangles()
    nt = len(me.loop_triangles)
    co = np.empty(len(me.vertices) * 3)
    me.vertices.foreach_get('co', co)
    M = np.array(obj.matrix_world)
    co = co.reshape(-1, 3) @ M[:3, :3].T
    cn = np.empty(len(me.loops) * 3)
    me.corner_normals.foreach_get('vector', cn)
    cn = cn.reshape(-1, 3) @ np.linalg.inv(M[:3, :3])
    cn /= np.maximum(np.linalg.norm(cn, axis=1), 1e-12)[:, None]
    tv = np.empty(nt * 3, dtype=np.int64)
    me.loop_triangles.foreach_get('vertices', tv)
    tl = np.empty(nt * 3, dtype=np.int64)
    me.loop_triangles.foreach_get('loops', tl)
    tp = np.empty(nt, dtype=np.int64)
    me.loop_triangles.foreach_get('polygon_index', tp)
    P = co[tv.reshape(-1, 3)]
    N = cn[tl.reshape(-1, 3)]
    k = np.zeros(nt)
    for i, j in ((0, 1), (1, 2), (2, 0)):
        e = P[:, j] - P[:, i]
        k += ((N[:, j] - N[:, i]) * e).sum(1) / np.maximum((e * e).sum(1), 1e-12)
    ct = 2.0 * k / 3.0
    area = np.linalg.norm(np.cross(P[:, 1] - P[:, 0], P[:, 2] - P[:, 0]), axis=1) * 0.5 + 1e-12
    num = np.zeros(len(me.polygons))
    den = np.zeros(len(me.polygons))
    np.add.at(num, tp, ct * area)
    np.add.at(den, tp, area)
    curv = num / np.maximum(den, 1e-12)
    # per corner: average the faces that share this vertex AND this corner normal, so the value
    # runs smoothly over a smooth surface and never leaks across a sharp edge (a bevel band's
    # curvature stays off its flat cap)
    nl = len(me.loops)
    lv = np.empty(nl, dtype=np.int64)
    me.loops.foreach_get('vertex_index', lv)
    ptot = np.empty(len(me.polygons), dtype=np.int64)
    me.polygons.foreach_get('loop_total', ptot)
    lp = np.repeat(np.arange(len(me.polygons)), ptot)
    q = np.round(cn * 64).astype(np.int64)
    key = np.stack([lv, q[:, 0], q[:, 1], q[:, 2]], axis=1)
    _, grp = np.unique(key, axis=0, return_inverse=True)
    grp = grp.ravel()
    parea = den[lp]
    gs = np.zeros(grp.max() + 1)
    gw = np.zeros(grp.max() + 1)
    np.add.at(gs, grp, curv[lp] * parea)
    np.add.at(gw, grp, parea)
    corner = gs[grp] / np.maximum(gw[grp], 1e-12)
    at = me.attributes.get(name)
    if at is not None and at.domain != 'CORNER':
        me.attributes.remove(at)
        at = None
    at = at or me.attributes.new(name, 'FLOAT', 'CORNER')
    at.data.foreach_set('value', corner.astype(np.float32))
    return curv


def add_geometry_normal(obj, name='eido_geometry_normal'):
    """Store the mesh's corner normals (object space: smooth across smooth faces, split at sharp
    edges, the way the engine's vertex normals are) as a CORNER vector attribute, for the masks
    and the grunge projection (the engine's normalWorldGeometry). The material turns them to world
    space each frame, so moving or rotating the object needs nothing; re-run after reshaping."""
    me = obj.data
    cn = np.empty(len(me.loops) * 3, dtype=np.float32)
    me.corner_normals.foreach_get('vector', cn)
    at = me.attributes.get(name)
    if at is not None and (at.domain != 'CORNER' or at.data_type != 'FLOAT_VECTOR'):
        me.attributes.remove(at)
        at = None
    at = at or me.attributes.new(name, 'FLOAT_VECTOR', 'CORNER')
    at.data.foreach_set('vector', cn)
    return at


# ── the engine's grunge: a seamlessly tiling fbm image ────────────────────────────────────────
def grunge_texture(size=256, seed=1):
    """The engine's periodic value-noise fbm (same LCG, 16-cell lattice, 5 octaves), as an image."""
    nm = 'eido_grunge_%d_%d' % (size, seed)
    img = bpy.data.images.get(nm)
    if img is not None:
        return img
    s = int(seed) & 0xFFFFFFFF

    def rand():
        nonlocal s
        s = (s * 1664525 + 1013904223) & 0xFFFFFFFF
        return s / 4294967296.0
    P = 16
    lat = np.array([rand() for _ in range(P * P)], dtype=np.float32).astype(np.float64)
    g = np.arange(size, dtype=np.float64)
    X, Y = np.meshgrid(g, g)
    v = np.zeros_like(X)
    amp, f = 0.5, 1
    for _ in range(5):
        x = X / size * P * f
        y = Y / size * P * f
        xi, yi = np.floor(x), np.floor(y)
        xf, yf = x - xi, y - yi
        xi, yi = xi.astype(np.int64), yi.astype(np.int64)
        gv = lambda a, b: lat[np.mod(b, P) * P + np.mod(a, P)]
        u = xf * xf * (3 - 2 * xf)
        w = yf * yf * (3 - 2 * yf)
        a0, b0 = gv(xi, yi), gv(xi + 1, yi)
        c0, d0 = gv(xi, yi + 1), gv(xi + 1, yi + 1)
        v += amp * ((a0 + (b0 - a0) * u) + ((c0 + (d0 - c0) * u) - (a0 + (b0 - a0) * u)) * w)
        amp *= 0.5
        f *= 2
    v /= 0.96875
    c = np.clip(np.round(v * 255), 0, 255) / 255.0
    img = bpy.data.images.new(nm, size, size, alpha=False, float_buffer=False, is_data=True)
    px = np.ones((size, size, 4), dtype=np.float32)
    # row for row: three's DataTexture (flipY false) puts its first data row at v = 0, and so does
    # Blender's first pixel row
    px[..., 0] = px[..., 1] = px[..., 2] = c
    img.pixels.foreach_set(px.ravel())
    img.pack()
    try:
        img.colorspace_settings.name = 'Non-Color'
    except TypeError:
        pass
    return img


# ── 3. the layered material ───────────────────────────────────────────────────────────────────
def _incoming(g, sock, default):
    if sock.is_linked:
        return sock.links[0].from_socket
    v = sock.default_value
    try:
        return tuple(v)
    except TypeError:
        return float(v)


def _geometry_normal_world(g, geo, name='eido_geometry_normal'):
    """The engine's normalWorldGeometry: the stored corner normal (add_geometry_normal) turned to
    world space (the inverse transpose, live), or Geometry > Normal on a mesh without it."""
    at = g.attribute(name).outputs['Vector']
    vt = g.node('ShaderNodeVectorTransform', vector_type='NORMAL', convert_from='OBJECT', convert_to='WORLD')
    g.set(vt.inputs['Vector'], at)
    stored = g.vmath('NORMALIZE', vt.outputs['Vector'])
    has = g.math('GREATER_THAN', g.vmath('LENGTH', at), 0.5)        # a missing attribute reads (0, 0, 0)
    return g.mix('VECTOR', has, geo.outputs['Normal'], stored)


def _triplanar(g, img, pos, nw, scale):
    """The engine's triplanar(): world position x scale read on three planes and weighted by the
    absolute geometry normal over its sum. three (x, y, z) is Blender (x, -y, z) read as (x, z, -y):
    its xz plane is Blender (x, -y), zy is (-y, z), xy is (x, z)."""
    x, y, z = g.separate_xyz(g.vmath('SCALE', pos, scale=scale))
    my = g.mul(y, -1.0)

    def read(u, v):
        return g.separate_rgb(g.tex(img, g.combine_xyz(u, v), 'Linear').outputs['Color'])[0]
    ax, ay, az = g.separate_xyz(g.vmath('ABSOLUTE', nw))
    s = g.math('MAXIMUM', g.add(g.add(ax, ay), az), 1e-4)
    acc = g.add(g.add(g.mul(read(x, my), az), g.mul(read(my, z), ax)), g.mul(read(x, z), ay))
    return g.math('DIVIDE', acc, s)


def _apply_layers(mat, layers, grunge=None):
    """Insert the layer stack between what feeds the material's Principled BSDF and the BSDF."""
    grunge = grunge or {}
    g = Graph(mat.node_tree)
    bsdf = principled(mat)
    if bsdf is None:
        raise ValueError("material '%s' has no Principled BSDF to layer onto" % mat.name)
    col = _incoming(g, bsdf.inputs['Base Color'], None)
    rough = _incoming(g, bsdf.inputs['Roughness'], None)
    metal = _incoming(g, bsdf.inputs['Metallic'], None)
    for sock in ('Base Color', 'Roughness', 'Metallic'):
        for lk in list(bsdf.inputs[sock].links):
            mat.node_tree.links.remove(lk)
    geo = g.geometry()
    pos = geo.outputs['Position']
    nw = _geometry_normal_world(g, geo)
    nx, ny, nz = g.separate_xyz(nw)
    _, _, pz = g.separate_xyz(pos)
    gimg = grunge.get('texture') or grunge_texture(grunge.get('size', 256), grunge.get('seed', 1))
    gnoise = _triplanar(g, gimg, pos, nw, grunge.get('scale', 0.4))
    curv = None
    for L in layers:
        mk = L.get('mask')
        rng = L.get('range', (0.2, 0.8))
        if mk in ('cavity', 'crease', 'edges'):
            if curv is None:
                curv = g.attribute('eido_curvature').outputs['Fac']
            sc = L.get('scale', 0.05 if mk == 'crease' else 0.6)
            raw = g.mul(curv, (sc if mk == 'edges' else -sc), clamp=True)
            m = g.smoothstep(rng[0], rng[1], raw)
        elif mk == 'up':
            m = g.smoothstep(rng[0], rng[1], g.math('POWER', g.math('MAXIMUM', nz, 0.0), L.get('power', 2)))
        elif mk == 'slope':
            m = g.smoothstep(rng[0], rng[1], g.sub(1.0, g.math('ABSOLUTE', nz)))
        elif mk in ('below', 'above'):
            z = L.get('z', L.get('y', 0.0))
            fade = L.get('fade', 0.4)
            m = g.smoothstep(z, z - fade if mk == 'below' else z + fade, pz)
        elif mk == 'grunge':
            m = g.smoothstep(rng[0], rng[1], gnoise)
        else:
            print("[make_layered_material] unknown mask '%s': expected %s" % (mk, '|'.join(MASKS)))
            continue
        gk = L.get('grunge', 0)
        if gk > 0:
            m = g.mul(m, g.mix('FLOAT', gk, 1.0, g.mul(gnoise, 1.6)))
        m = g.mul(m, L.get('amount', 1.0), clamp=True)
        lc = _rgb(L.get('color', 0xffffff))
        if L.get('map') is not None:
            t = g.tex(load_image(L['map'], 'color'), None)
            lc = g.mix('RGBA', 1.0, t.outputs['Color'], lc, blend='MULTIPLY')
        col = g.mix('RGBA', m, col, lc)
        if L.get('roughness') is not None:
            rough = g.mix('FLOAT', m, rough, L['roughness'])
        if L.get('metalness') is not None:
            metal = g.mix('FLOAT', m, metal, L['metalness'])
    g.set(bsdf.inputs['Base Color'], col)
    g.set(bsdf.inputs['Roughness'], g.math('MINIMUM', g.math('MAXIMUM', rough, 0.02), 1.0))
    g.set(bsdf.inputs['Metallic'], g.math('MINIMUM', g.math('MAXIMUM', metal, 0.0), 1.0))
    mat['eido_layers'] = len(layers)
    return mat


def make_layered_material(base=None, layers=(), grunge=None, name='layered'):
    """A Principled material from `base` ({color (0xRRGGBB or linear rgb), map, roughness,
    roughness_map (its G channel, like the engine), normal_map, metalness, metalness_map}) with the
    layer stack on top."""
    base = base or {}
    mat = new_material(name)
    g = Graph(mat.node_tree)
    bsdf = principled(mat)
    uv = g.node('ShaderNodeUVMap', uv_map='UVMap').outputs['UV']
    c = _rgb(base.get('color', 0xffffff))
    if base.get('map') is not None:
        t = g.tex(load_image(base['map'], 'color'), uv)
        g.set(bsdf.inputs['Base Color'], g.mix('RGBA', 1.0, t.outputs['Color'], c, blend='MULTIPLY'))
    else:
        bsdf.inputs['Base Color'].default_value = c
    r = base.get('roughness', 0.9)
    if base.get('roughness_map') is not None:
        t = g.tex(load_image(base['roughness_map'], 'roughness'), uv)
        g.set(bsdf.inputs['Roughness'], g.mul(g.separate_rgb(t.outputs['Color'])[1], r))
    else:
        bsdf.inputs['Roughness'].default_value = r
    mtl = base.get('metalness', 0.0)
    if base.get('metalness_map') is not None:
        t = g.tex(load_image(base['metalness_map'], 'metalness'), uv)
        g.set(bsdf.inputs['Metallic'], g.mul(t.outputs['Color'], mtl))
    else:
        bsdf.inputs['Metallic'].default_value = mtl
    if base.get('normal_map') is not None:
        nm = g.node('ShaderNodeNormalMap', uv_map='UVMap')
        g.set(nm.inputs['Color'], g.tex(load_image(base['normal_map'], 'normal'), uv).outputs['Color'])
        g.set(bsdf.inputs['Normal'], nm.outputs['Normal'])
    if layers:
        _apply_layers(mat, list(layers), grunge)
    return mat


def layer_surface(objects, layers=(), grunge=None, metres_per_tile=None, force=False, label=''):
    """The one-liner: normalise texel density (when metres_per_tile is given), measure curvature
    when a curvature mask is asked for, and layer each mesh's own material (one layered copy per
    source material). Refuses fetched assets unless force=True. Returns {source: layered}."""
    meshes = _meshes(objects, force, 'layer_surface')
    if not meshes:
        print('[layer_surface] nothing to do: every mesh handed in was a fetched asset. These tools are '
              'for geometry you BUILT (lathe / extrude / boolean).')
        return {}
    if metres_per_tile:
        normalize_texel_density(meshes, metres_per_tile, label=label, force=force)
    layers = list(layers)
    for m in meshes:
        add_geometry_normal(m)
    if any(L.get('mask') in ('cavity', 'crease', 'edges') for L in layers):
        for m in meshes:
            add_curvature(m)
    cache = {}
    for m in meshes:
        if not m.material_slots or m.material_slots[0].material is None:
            if not m.data.materials:
                m.data.materials.append(make_layered_material({}, [], name=m.name + '_base'))
            else:
                m.material_slots[0].material = make_layered_material({}, [], name=m.name + '_base')
        src = m.material_slots[0].material
        out = cache.get(src.name)
        if out is None:
            out = src.copy()
            out.name = src.name + '_layered'
            _apply_layers(out, layers, grunge)
            cache[src.name] = out
        m.material_slots[0].material = out
    print('[layer_surface] %d mesh(es) -> %d layered material(s), %d layer(s) each.'
          % (len(meshes), len(cache), len(layers)))
    return cache
