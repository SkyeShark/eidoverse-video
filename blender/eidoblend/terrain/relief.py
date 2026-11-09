"""Relief: real depth from a height map (the Blender form of eidoverse/parallax_material.js).

    from eidoblend.terrain import relief
    mat = relief.create_parallax_material(height_map=tex['displacement'], albedo_map=tex['color'],
                                          normal_map=tex['normal'], depth_scale=0.05, uv_scale=(4, 2),
                                          tile_metres=(2.25, 2.1))
    wall.data.materials.append(mat)
    relief.subdivide(wall, edge=0.01)                 # vertices for the displacement to move
    col = relief.create_relief_column(height_map=..., albedo_map=..., radius=0.5, height=3.2, around_tiles=3)

The engine's SPOM ray-marched a height field to fake depth and a silhouette in a real-time raster.
EEVEE 5.2 displaces real vertices at render time (material displacement), so in the render the relief IS
geometry: it casts and receives real shadows and carves a true silhouette. It happens in the render only: the
evaluated mesh, and with it every Python ray, placement helper and contact check, still sees the undisplaced
polygons (measure a relief in a render, as test_relief_bounds.py does). The names and options stay the engine's
where they still mean something:
  depth_scale   relief depth in UV-tile units (as the engine's); depth in metres = depth_scale x
                the tile's world size (tile_metres), or pass depth_metres directly
  uv_scale      tiles across the mesh's UVs (number or (u, v))
  silhouette    the relief carves inward from the surface (peaks at the polygon) as the engine's flat
                SPOM did, with silhouette True and with False (the engine's interior POM, e.g. a floor):
                what stands on the polygon stands on the peaks. True also lets silhouette_bounds cut
                the outline; False never cuts. A relief column inflates outward instead (its peaks
                overhang the base)
  contrast      the field notes' stretch: the map's own min..max is mapped to (floor, 1), so a
                low-contrast mid-grey Poly Haven _disp carves visibly and no well is full depth
The march's own knobs (minLayers, maxLayers, minViewZ, curvedSilhouette, curvature, the horizon trim,
the marched self-shadow, heightNormal) have nothing to do here: EEVEE shadows and shades the real surface.

The relief's bounds (parallax_occlusion.js), in the same scaled-UV space as the engine's (uv x uv_scale):
  silhouette_bounds  [lo, hi] or [[u_lo, u_hi], [v_lo, v_hi]]: the surface is cut away where its UV leaves
                     the bounds (the engine's coverage: 1 inside, feathered to 0 over 0.02 UV outside, clipped at
                     0.5). The displaced surface carries its own UV at every point, so this is the engine's test
                     on the marched landing UV exactly. None (default): no cut, the displaced border is the outline
  sample_bounds      same format: every map read (height, colour, normal, roughness ...) is clamped into the
                     region, so outside it the border texels continue: a tiling relief ends cleanly instead of
                     meeting a wrapped copy (pair it with silhouette_bounds to cut the streaks away)
  face_bounds        True: per-face bounds for world-UV merged boxes. face_bounds(obj) splits the mesh's sharp
                     edges (each face displaces along its own normal) and stores each face's UV rectangle as the
                     FACE attributes uv_min / uv_max (the engine's uvMin / uvMax); the material culls back faces,
                     so where a well meets a box's edge the outline notches and the box reads through, as the
                     engine's per-face discard did. The engine discarded where the MARCHED uv left the face's
                     rectangle; a displaced point carries its own face's uv, which never leaves it, so the
                     attributes are not read by the material (they are there for a custom node tree). As in the
                     engine, face_bounds replaces silhouette_bounds' cut. world_uv_boxes() builds such boxes
  debug_silhouette   paint the cut region magenta instead of cutting it; debug_march: show fract(uv) unlit
parallax_occlusion_uv(tree, height_map, ...) is the library call itself for custom node trees: it returns .uv,
.coverage, .missed, .sample(image) and .shadow() (1: EEVEE shadows the real relief) as sockets.
uv_map: the UV layer every read uses ('' = the mesh's active render UV layer, the default).
The engine's silhouetteBounds default ([0, 1], judged on the scaled UV) clipped march rays that left a one-tile plate
through its side; a displaced surface sends no rays out of itself, so here the default (None) cuts nothing and the
displaced border is the outline. Pass the engine's bounds explicitly to cut.
"""
import math

import bmesh
import bpy
import numpy as np
from mathutils import Vector

from ._nodes import Graph, new_material, principled, output
from ._pbr import load_image


def _snake_key(k):
    out = ''
    for ch in k:
        out += ('_' + ch.lower()) if ch.isupper() else ch
    return out


def _pair(v, d=1.0):
    if v is None:
        return (d, d)
    if isinstance(v, (int, float)):
        return (float(v), float(v))
    return (float(v[0]), float(v[1]))


def _rgba(color):
    """an engine colour -> Blender linear RGBA: 0xRRGGBB or '#rrggbb' are sRGB (three's hex, converted as its
    ColorManagement does); an (r, g, b) tuple or {'r', 'g', 'b'} is linear already (three's setRGB / Color.set of an
    object)"""
    if isinstance(color, dict):
        return (float(color['r']), float(color['g']), float(color['b']), 1.0)
    if isinstance(color, str) or (isinstance(color, int) and not isinstance(color, bool)):
        c = int(color.lstrip('#'), 16) if isinstance(color, str) else int(color)
        v = (((c >> 16) & 255) / 255.0, ((c >> 8) & 255) / 255.0, (c & 255) / 255.0)
        return tuple(x / 12.92 if x <= 0.04045 else ((x + 0.055) / 1.055) ** 2.4 for x in v) + (1.0,)
    c = tuple(color)
    return (float(c[0]), float(c[1]), float(c[2]), 1.0)


def _range(img):
    if 'eido_hrange' in img:
        return tuple(img['eido_hrange'])
    n = img.size[0] * img.size[1] * img.channels
    px = np.empty(n, dtype=np.float32)
    img.pixels.foreach_get(px)
    v = px.reshape(-1, img.channels)[:, 0]
    lo, hi = float(np.percentile(v, 0.5)), float(np.percentile(v, 99.5))
    if hi - lo < 1e-3:
        hi = lo + 1e-3
    img['eido_hrange'] = (lo, hi)
    return lo, hi


FEATHER = 0.02                  # the library's coverage feather (UV units)


def _bounds(b):
    """[lo, hi] or [[u_lo, u_hi], [v_lo, v_hi]] -> ((u_lo, u_hi), (v_lo, v_hi)), or None"""
    if b is None:
        return None
    if isinstance(b[0], (list, tuple)):
        return (float(b[0][0]), float(b[0][1])), (float(b[1][0]), float(b[1][1]))
    return (float(b[0]), float(b[1])), (float(b[0]), float(b[1]))


class ReliefUV:
    """parallax_occlusion_uv's result in a material node tree (sockets): uv, coverage, missed, sample(), shadow()."""

    def __init__(self, g, uv, coverage, missed, coord_at, scale):
        self.g, self.uv, self.coverage, self.missed = g, uv, coverage, missed
        self.coord_at = coord_at
        self.scale = scale

    def sample(self, image, coord=None, interpolation='Linear'):
        """the image's Color at the relief UV (or `coord`), clamped into sample_bounds like every library fetch"""
        return self.g.tex(image, self.coord_at(coord if coord is not None else self.uv), interpolation).outputs['Color']

    def shadow(self, light_direction=None, steps=16, strength=8, bias=0.03):
        """the library's marched self-shadow factor: 1 here (EEVEE casts the displaced relief's real shadows)"""
        v = self.g.node('ShaderNodeValue')
        v.outputs[0].default_value = 1.0
        return v.outputs[0]


MARCH_OPTIONS = ('min_layers', 'max_layers', 'min_view_z', 'curved_silhouette', 'curvature', 'horizon_strength',
                 'horizon_safe_zone', 'horizon_falloff', 'horizon_bias', 'edge_erosion')
# createParallaxMaterial's march-only options on top of the library's: the marched self-shadow and its tuning, the
# marched shadow-map depth, the height-derived normal (EEVEE shades and shadows the displaced surface itself)
MATERIAL_MARCH_OPTIONS = MARCH_OPTIONS + ('light_dir', 'self_shadow', 'shadow_strength', 'shadow_steps',
                                          'shadow_bias', 'shadow_floor', 'relief_shadow', 'world_per_tile',
                                          'relief_world', 'height_normal', 'debug_march_lit')


def parallax_occlusion_uv(tree, height_map, uv_node=None, scale=0.05, silhouette=True, silhouette_bounds=(0, 1),
                          sample_bounds=None, uv_map='', **march):
    """The library call (parallax_occlusion.js's parallaxOcclusionUV) for a custom node tree: `tree` is a material's
    node tree (or a terrain._nodes.Graph). The surface is displaced for real (create_parallax_material), so the
    relief UV is the surface's own UV; the bounds are the library's. The march's options (MARCH_OPTIONS: min_layers,
    max_layers, min_view_z, curved_silhouette, curvature, horizon_strength / safe_zone / falloff / bias,
    edge_erosion) are accepted and have nothing to do: a real surface needs no march, no horizon and no curvature
    estimate. Their camelCase spellings are accepted too; any other keyword raises."""
    unknown = [k for k in march if _snake_key(k) not in MARCH_OPTIONS]
    if unknown:
        raise TypeError('parallax_occlusion_uv: unknown option(s) %s' % ', '.join(sorted(unknown)))
    g = tree if isinstance(tree, Graph) else Graph(tree)
    uv = uv_node if uv_node is not None else g.node('ShaderNodeUVMap', uv_map=uv_map or '').outputs['UV']
    sb = _bounds(sample_bounds)

    def coord_at(c):
        if sb is None:
            return c
        x, y, _z = g.separate_xyz(c)
        x = g.math('MINIMUM', g.math('MAXIMUM', x, sb[0][0]), sb[0][1])
        y = g.math('MINIMUM', g.math('MAXIMUM', y, sb[1][0]), sb[1][1])
        return g.combine_xyz(x, y, 0.0)

    coverage = missed = None
    bb = _bounds(silhouette_bounds) if silhouette else None
    if bb is not None:
        x, y, _z = g.separate_xyz(uv)
        over_u = g.math('MAXIMUM', g.sub(bb[0][0], x), g.sub(x, bb[0][1]))
        over_v = g.math('MAXIMUM', g.sub(bb[1][0], y), g.sub(y, bb[1][1]))
        coverage = g.math('SUBTRACT', 1.0, g.math('DIVIDE', g.math('MAXIMUM', over_u, over_v), FEATHER), clamp=True)
        missed = g.math('LESS_THAN', coverage, 0.5)
    return ReliefUV(g, uv, coverage, missed, coord_at, scale)


def create_parallax_material(height_map, albedo_map=None, normal_map=None, roughness_map=None,
                             depth_scale=0.1, uv_scale=1.0, tile_metres=1.0, depth_metres=None,
                             silhouette=True, contrast=(0.15, 1.0), inflate=False, roughness=0.7,
                             roughness_scale=1.0, metalness=0.0, color=None, method='BOTH', space='WORLD',
                             interpolation='Auto', detail_distance=(4.0, 9.0), name='relief',
                             silhouette_bounds=None, sample_bounds=None, face_bounds=False, metalness_map=None,
                             debug_silhouette=False, debug_march=False, lambert=False, self_lit=None, uv_map='',
                             ao_map=None, **march):
    """A material whose height map displaces the surface along its normal (EEVEE vertex
    displacement; method 'BOTH' adds the finer-than-vertex detail as bump). Needs vertices: see
    subdivide(). inflate=True pushes outward (relief column) instead of carving inward.
    roughness: the value without a roughness_map; with one, the map times roughness_scale.
    space 'WORLD' (default): the depth is metres whatever the object's scale (an unapplied scale
    along the normal would otherwise stretch it); 'OBJECT' scales the depth with the object, for an
    assembly meant to be scaled as a whole (create_relief_column).
    interpolation: how the albedo and normal maps are read: 'Auto' (full-resolution Cubic within
    detail_distance of the camera, mipmapped Linear past it, as make_terrain's film material: Cubic
    alone crawls in motion once a pixel covers many texels), 'Cubic' or 'Linear'. The height map
    is always read Cubic: it moves vertices, and the geometry must not change with the camera.
    The relief's bounds (silhouette_bounds, sample_bounds, face_bounds) and the debug views: see the module's doc.
    color: the engine's 0xRRGGBB or '#rrggbb' (sRGB), or a linear (r, g, b); it multiplies the albedo map.
    metalness_map: its red channel is the metalness (the engine's metalnessNode). lambert=True: a plain diffuse
    surface (the engine's MeshLambertNodeMaterial escape hatch); self_lit={'sun_dir', 'ambient', 'sun_color'}: unlit,
    shaded by hand as rgb x (ambient + sun_color x max(N.sun_dir, 0)) (Blender axes). march: the march-only options
    (min_layers, max_layers, min_view_z, curved_silhouette, curvature, horizon_*, edge_erosion, light_dir,
    self_shadow, shadow_*, relief_shadow, world_per_tile, relief_world, height_normal), accepted, not needed.
    inflate may also be the engine's number, the relief's world height outward (inflate=0.05: the peaks 5 cm out,
    the floor on the surface). debug_march_lit=True shows debug_march's colours lit. ao_map: accepted and left
    unwired (EEVEE shades its own occlusion; recorded as eido_ao_map_unwired). Every march-only option is accepted
    (snake_case or the engine's camelCase); any other keyword raises."""
    unknown = [k for k in march if _snake_key(k) not in MATERIAL_MARCH_OPTIONS]
    if unknown:
        raise TypeError('create_parallax_material: unknown option(s) %s' % ', '.join(sorted(unknown)))
    mat = new_material(name)
    mat.displacement_method = method
    g = Graph(mat.node_tree)
    bsdf = principled(mat)
    out = output(mat)
    su, sv = _pair(uv_scale)
    tu, tv = _pair(tile_metres)
    depth = depth_metres if depth_metres is not None else depth_scale * math.sqrt(tu * tv)
    if not isinstance(inflate, bool) and isinstance(inflate, (int, float)) and inflate > 0:
        depth = float(inflate)                     # the engine's inflate: the shell pushed out by this world height
    march = {_snake_key(k): v for k, v in march.items()}
    debug_lit = bool(march.pop('debug_march_lit', False))
    uv = g.node('ShaderNodeUVMap', uv_map=uv_map or '').outputs['UV']
    vec = g.vmath('MULTIPLY', uv, (su, sv, 1.0))
    # the engine: libSil = sil && !faceBounds (per-face bounds replace the constant bounds' cut)
    pom = parallax_occlusion_uv(g, height_map, uv_node=vec, scale=depth_scale,
                                silhouette=bool(silhouette) and not face_bounds,
                                silhouette_bounds=silhouette_bounds, sample_bounds=sample_bounds)
    rgba = _rgba(color) if color is not None else None
    rv = pom.coord_at(vec)                         # every map read, clamped into sample_bounds
    himg = load_image(height_map, 'displacement')
    lo, hi = _range(himg)
    fl = contrast[0] if contrast else 0.0
    top = contrast[1] if contrast else 1.0
    h = g.tex(himg, rv, 'Cubic').outputs['Color']
    h = g.map_range(h, lo, hi, fl, top) if contrast else h
    far = g.handover(*detail_distance) if interpolation == 'Auto' else None
    base = None
    if albedo_map is not None:
        base = g.read(load_image(albedo_map, 'color'), rv, interpolation, far)
        if rgba is not None:
            base = g.mix('RGBA', 1.0, base, rgba, blend='MULTIPLY')
    elif rgba is not None:
        bsdf.inputs['Base Color'].default_value = rgba
    if debug_silhouette and pom.missed is not None:
        base = g.mix('RGBA', pom.missed, base if base is not None else bsdf.inputs['Base Color'].default_value[:],
                     (1.0, 0.0, 1.0, 1.0))
    if base is not None:
        g.set(bsdf.inputs['Base Color'], base)
    if roughness_map is not None:                  # the map as scanned, times roughness_scale
        g.set(bsdf.inputs['Roughness'], g.mul(g.tex(load_image(roughness_map, 'roughness'), rv).outputs['Color'],
                                              roughness_scale, clamp=True))
    else:
        bsdf.inputs['Roughness'].default_value = roughness
    if metalness_map is not None:
        r, _g, _b = g.separate_rgb(g.tex(load_image(metalness_map, 'metalness'), rv).outputs['Color'])
        g.set(bsdf.inputs['Metallic'], r)
    else:
        bsdf.inputs['Metallic'].default_value = metalness
    nsock = None
    if normal_map is not None:
        nm = g.node('ShaderNodeNormalMap', uv_map=uv_map or '')
        g.set(nm.inputs['Color'], g.read(load_image(normal_map, 'normal'), rv, interpolation, far))
        g.set(bsdf.inputs['Normal'], nm.outputs['Normal'])
        nsock = nm.outputs['Normal']
    surface = bsdf.outputs['BSDF']
    if lambert or self_lit:
        col = base if base is not None else tuple(bsdf.inputs['Base Color'].default_value)
        if self_lit:
            sl = {_snake_key(k): v for k, v in self_lit.items()} if isinstance(self_lit, dict) else {}
            sd = sl.get('sun_dir', (0.5, -0.4, 0.8))
            n = nsock if nsock is not None else g.geometry().outputs['Normal']
            ndl = g.math('MAXIMUM', g.vmath('DOT_PRODUCT', n, tuple(v / math.sqrt(sum(c * c for c in sd)) for v in sd)),
                         0.0)
            amb = sl.get('ambient', (0.35, 0.35, 0.35))
            sun = sl.get('sun_color', (1.0, 1.0, 1.0))
            light = g.vmath('ADD', tuple(amb), g.vmath('SCALE', tuple(sun), scale=ndl))
            em = g.node('ShaderNodeEmission')
            g.set(em.inputs['Color'], g.mix('RGBA', 1.0, col, light, blend='MULTIPLY'))
            surface = em.outputs['Emission']
        else:
            df = g.node('ShaderNodeBsdfDiffuse')
            g.set(df.inputs['Color'], col)
            if nsock is not None:
                g.set(df.inputs['Normal'], nsock)
            surface = df.outputs['BSDF']
    if debug_march or debug_lit:                   # the engine's debugMarch: fract(uv), unlit (or lit)
        x, y, _z = g.separate_xyz(rv)
        dbg = g.combine_xyz(g.math('FRACT', x), g.math('FRACT', y), 0.5)
        if debug_lit:
            g.set(bsdf.inputs['Base Color'], dbg)
        else:
            em = g.node('ShaderNodeEmission')
            g.set(em.inputs['Color'], dbg)
            surface = em.outputs['Emission']
    if pom.coverage is not None and not debug_silhouette:
        # the cut: alpha exactly 0 or 1 (coverage clipped at 0.5, the engine's alphaTest), so EEVEE's dithered
        # transparency draws it clean; its shadows follow the cut outline (maskShadowNode)
        tr = g.node('ShaderNodeBsdfTransparent')
        mx = g.node('ShaderNodeMixShader')
        g.set(mx.inputs['Fac'], g.math('GREATER_THAN', pom.coverage, 0.49999))
        g.links.new(tr.outputs['BSDF'], mx.inputs[1])
        g.links.new(surface, mx.inputs[2])
        surface = mx.outputs['Shader']
        mat.surface_render_method = 'DITHERED'
        mat.use_transparent_shadow = True
    if surface is not bsdf.outputs['BSDF']:
        g.links.new(surface, out.inputs['Surface'])
    if face_bounds:
        mat.use_backface_culling = True            # a notch where a well meets a box edge shows through
        mat['eido_face_bounds'] = True
    if silhouette_bounds is not None:
        mat['eido_silhouette_bounds'] = str(_bounds(silhouette_bounds))
    if sample_bounds is not None:
        mat['eido_sample_bounds'] = str(_bounds(sample_bounds))
    if ao_map is not None:
        mat['eido_ao_map_unwired'] = getattr(ao_map, 'name', str(ao_map))
    dn = g.node('ShaderNodeDisplacement', space=space)
    g.set(dn.inputs['Height'], h)
    # inward from the polygon (its top at the surface) whether or not the outline is cut: the engine's flat SPOM and
    # its interior POM both put the peaks on the polygon; inflate pushes the floor out from it instead
    dn.inputs['Midlevel'].default_value = 0.0 if inflate else top
    dn.inputs['Scale'].default_value = depth
    g.set(out.inputs['Displacement'], dn.outputs['Displacement'])
    mat['eido_relief_depth'] = depth
    mat['eido_relief_feature'] = min(tu / max(himg.size[0], 1), tv / max(himg.size[1], 1)) * 4
    return mat


def subdivide(obj, edge=0.01, max_levels=9):
    """Add a Simple subdivision so obj's longest edge becomes about `edge` metres (the vertices
    the displacement moves; ~1 cm for brick mortar). Returns the levels used."""
    bpy.context.view_layer.update()          # matrix_world is stale right after a scale is set
    me = obj.data
    co = np.empty(len(me.vertices) * 3)
    me.vertices.foreach_get('co', co)
    co = co.reshape(-1, 3) * np.array(obj.matrix_world.to_scale())
    ed = np.empty(len(me.edges) * 2, dtype=np.int64)
    me.edges.foreach_get('vertices', ed)
    ed = ed.reshape(-1, 2)
    longest = float(np.linalg.norm(co[ed[:, 0]] - co[ed[:, 1]], axis=1).max()) if len(ed) else 0.0
    levels = int(min(max_levels, max(0, math.ceil(math.log2(max(longest / edge, 1.0))))))
    md = obj.modifiers.get('eido_relief_subdiv') or obj.modifiers.new('eido_relief_subdiv', 'SUBSURF')
    md.subdivision_type = 'SIMPLE'
    md.levels = levels
    md.render_levels = levels
    return levels


def check_relief_geometry(obj, label=None):
    """True when obj can carry its relief: it has UVs and its (subdivided) edges are no longer than
    about the relief's feature size; prints what to fix otherwise (the engine checked tangents)."""
    label = label or obj.name
    me = obj.data
    if not me.uv_layers:
        print('[check_relief_geometry] %s: no UVs: the height map has nowhere to sit' % label)
        return False
    mats = [s.material for s in obj.material_slots if s.material and 'eido_relief_depth' in s.material
            and s.material.displacement_method != 'BUMP']        # bump alone moves no vertices
    if not mats:
        return True
    dg = bpy.context.evaluated_depsgraph_get()
    ev = obj.evaluated_get(dg)
    m = ev.to_mesh()
    try:
        co = np.empty(len(m.vertices) * 3)
        m.vertices.foreach_get('co', co)
        co = co.reshape(-1, 3) * np.array(obj.matrix_world.to_scale())
        ed = np.empty(len(m.edges) * 2, dtype=np.int64)
        m.edges.foreach_get('vertices', ed)
        ed = ed.reshape(-1, 2)
        med = float(np.median(np.linalg.norm(co[ed[:, 0]] - co[ed[:, 1]], axis=1)))
    finally:
        ev.to_mesh_clear()
    feat = max(mt['eido_relief_feature'] for mt in mats)
    if med > feat * 4:
        print('[check_relief_geometry] %s: edges ~%.3f m against relief features ~%.3f m: the displacement '
              'has too few vertices to move (relief.subdivide(obj, edge=%.3f))' % (label, med, feat, feat))
        return False
    return True


def face_bounds(obj, angle_deg=1.0):
    """The engine's faceBounds geometry: every face of obj keeps its own UV rectangle as the FACE attributes
    uv_min / uv_max (FLOAT2, the engine's uvMin / uvMax), and an Edge Split (first in the stack, before the
    relief's subdivision) cuts the edges sharper than angle_deg, so each face displaces along its own normal: at a
    box's edge the relief ends at that face's own bounds. Pair with create_parallax_material(face_bounds=True)
    (back faces culled: the notches read through, as the engine's per-face discard). Returns the modifier."""
    me = obj.data
    uvl = me.uv_layers.active
    n = len(me.polygons)
    lo = np.zeros((n, 2), dtype=np.float32)
    hi = np.zeros((n, 2), dtype=np.float32)
    if uvl is not None:
        uv = np.empty(len(me.loops) * 2, dtype=np.float32)
        uvl.data.foreach_get('uv', uv)
        uv = uv.reshape(-1, 2)
        for p in me.polygons:
            s = uv[p.loop_start:p.loop_start + p.loop_total]
            lo[p.index], hi[p.index] = s.min(axis=0), s.max(axis=0)
    for nm, arr in (('uv_min', lo), ('uv_max', hi)):
        at = me.attributes.get(nm) or me.attributes.new(nm, 'FLOAT2', 'FACE')
        at.data.foreach_set('vector', arr.ravel())
    md = obj.modifiers.get('eido_face_bounds') or obj.modifiers.new('eido_face_bounds', 'EDGE_SPLIT')
    md.use_edge_angle = True
    md.split_angle = math.radians(angle_deg)
    md.use_edge_sharp = True
    i = obj.modifiers.find(md.name)
    if i > 0:
        obj.modifiers.move(i, 0)
    return md


def world_uv_boxes(boxes, tile_metres=1.0, name='relief_boxes', collection=None):
    """World-UV merged boxes, the case faceBounds was made for: boxes = [(centre, size), ...] in Blender metres,
    one mesh, each face's UVs its WORLD position on the face's own axes divided by tile_metres (u along the face
    as seen from outside, v up on walls), so a tiling relief runs on unbroken across the boxes' coplanar faces.
    Returns the object (face_bounds(obj) and a relief material next)."""
    tu, tv = _pair(tile_metres)
    bm = bmesh.new()
    for centre, size in boxes:
        geom = bmesh.ops.create_cube(bm, size=1.0)
        vs = geom['verts']
        bmesh.ops.scale(bm, vec=Vector(size), verts=vs)
        bmesh.ops.translate(bm, vec=Vector(centre), verts=vs)
    bm.normal_update()
    uvl = bm.loops.layers.uv.new('UVMap')          # named: bmesh's default layer name is 'Float2'
    for f in bm.faces:
        nx, ny, nz = f.normal
        ax = max(range(3), key=lambda i: abs(f.normal[i]))
        for lp in f.loops:
            x, y, z = lp.vert.co
            if ax == 0:
                u, v = (y if nx > 0 else -y), z
            elif ax == 1:
                u, v = (-x if ny > 0 else x), z
            else:
                u, v = x, (y if nz > 0 else -y)
            lp[uvl].uv = (u / tu, v / tv)
    me = bpy.data.meshes.new(name)
    bm.to_mesh(me)
    bm.free()
    ob = bpy.data.objects.new(name, me)
    (collection or bpy.context.scene.collection).objects.link(ob)
    return ob


def create_relief_column(height_map, albedo_map=None, normal_map=None, radius=0.5, height=3.0,
                         around_tiles=3, depth_scale=0.15, relief_factor=1.0, segments=None, caps=True,
                         cap_color=(0.033, 0.040, 0.054), roughness=0.55, metalness=0.18, name='relief_column',
                         collection=None, light_dir=None, core_color=None, **mat_opts):
    """A column / pipe whose relief overhangs its round outline: a UV'd cylinder displaced OUTWARD by
    height x relief depth (relief depth = depth_scale x relief_factor x one tile's width around), with
    flat end caps at radius + 0.95 x that depth. Returns the root Empty (rotate it to lay a pipe down);
    root['relief_world'] and root['shell'] are the engine's group.userData.reliefWorld and .shell.
    light_dir: the engine's key-light direction for its marched shadow: accepted, unused (EEVEE shadows the relief).
    core_color: the engine's fill core inside the clipping shell: a displaced cylinder never clips, so it needs no
    core (recorded on the root). Any other keyword goes to create_parallax_material (roughness_map, color, ...)."""
    coll = collection or bpy.context.scene.collection
    tile_around = 2 * math.pi * radius / around_tiles
    ring_tiles = max(2, round(height / tile_around))
    relief_world = depth_scale * relief_factor * tile_around
    na = segments or 384
    nh = max(8, int(ring_tiles * 128))
    a = np.linspace(0, 2 * math.pi, na, endpoint=False)
    z = np.linspace(-height / 2, height / 2, nh + 1)
    A, Z = np.meshgrid(a, z)
    co = np.stack([np.cos(A) * radius, np.sin(A) * radius, Z], axis=-1).reshape(-1, 3)
    faces = []
    for i in range(nh):
        for j in range(na):
            p, q = i * na + j, i * na + (j + 1) % na
            faces.append((p, q, q + na, p + na))
    me = bpy.data.meshes.new(name + '_shell')
    me.from_pydata(co.tolist(), [], faces)
    uvl = me.uv_layers.new(name='UVMap')
    uv = []
    for i in range(nh):
        for j in range(na):
            u0, u1 = j / na, (j + 1) / na
            v0, v1 = i / nh, (i + 1) / nh
            uv += [(u0, v0), (u1, v0), (u1, v1), (u0, v1)]
    uvl.uv.foreach_set('vector', np.asarray(uv, dtype=np.float32).ravel())
    me.shade_smooth()
    # object space: the column is an assembly (shell + caps sized to the relief); scaling its root
    # scales the relief with the caps, so the caps keep covering the bricks' overhang
    mat = create_parallax_material(height_map, albedo_map, normal_map, uv_scale=(around_tiles, ring_tiles),
                                   depth_metres=relief_world, inflate=True, roughness=roughness,
                                   metalness=metalness, space='OBJECT', name=name + '_relief', **mat_opts)
    me.materials.append(mat)
    root = bpy.data.objects.new(name, None)
    coll.objects.link(root)
    shell = bpy.data.objects.new(name + '_shell', me)
    coll.objects.link(shell)
    shell.parent = root
    root['assembly'] = name
    shell['assembly'] = name
    if caps:
        cap_r = radius + relief_world * 0.95
        cm = new_material(name + '_cap')
        cb = principled(cm)
        cb.inputs['Base Color'].default_value = _rgba(cap_color)
        cb.inputs['Roughness'].default_value = 0.5
        cb.inputs['Metallic'].default_value = 0.3
        for end in (-1, 1):
            bpy.ops.mesh.primitive_cylinder_add(radius=cap_r, depth=0.07, vertices=96,
                                                location=(0, 0, end * (height / 2 + 0.02)))
            cap = bpy.context.active_object
            for c in list(cap.users_collection):
                c.objects.unlink(cap)
            coll.objects.link(cap)
            cap.name = name + ('_cap_top' if end > 0 else '_cap_bottom')
            cap.data.materials.append(cm)
            cap.parent = root
            cap['assembly'] = name
    root['relief_world'] = relief_world
    root['shell'] = shell
    if core_color is not None:
        root['eido_core_color_unused'] = str(core_color)
    return root
