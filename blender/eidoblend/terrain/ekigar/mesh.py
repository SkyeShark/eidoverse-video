"""Blender side of the Ekigar port: a Heightfield becomes a real displaced grid mesh, with every mask as a point
attribute, and Ekigar's preview shading as a material.

    from eidoblend.terrain import ekigar
    hf = ekigar.generate('volcano', resolution=512, world_size=400)
    obj = ekigar.build_mesh(hf, name='Volcano')                  # true displacement, masks as attributes
    obj.data.materials.append(ekigar.preview_material('grey'))   # or 'shaded' / a mask diagnostic
    z = hf.height_at(10.0, -42.0)                                # on that mesh, exactly

The mesh puts one vertex on every texel centre (Ekigar's terrain_mesh.js layout), quads split by Blender along
their first diagonal, which is the split hf.height_at() assumes. side='auto' or side=N builds Ekigar's display grid
instead (N x N vertices on their own texel centres, bilinear heights; hf.height_at(x, y, side=N) matches it);
crop=cut builds only a local circle's window at full resolution. wrap=True adds the seam row and column of a
periodic tile, so copies laid at multiples of world_size join without a slit. export_glb writes the mesh as binary
glTF.
"""
from __future__ import annotations

import os

import numpy as np

import bpy

from .display_grid import terrain_vertex_side, field_height_bilinear

PREVIEW_MODES = ['grey', 'shaded', 'height', 'slope', 'aspect', 'curvProfile', 'curvPlan', 'ridge']


def wrap_axes(hf, wrap):
    """Which axes get the seam row / column: (x, y) bools, only where the tile is periodic."""
    if not wrap:
        return False, False
    return bool(hf.tile.x > 0), bool(hf.tile.y > 0)


def _layout(hf, side=None, step=None, crop=None, wrap=False):
    """Vertex positions, heights and uv of the mesh build_mesh makes, and how to read a field-sized array onto it:
    (xs, ys, z, us, vs, read) with read(array) -> the array at the vertices."""
    nx, ny = hf.resolution
    w = hf.world_size
    ex, ey = (0, 0) if crop is not None else tuple(int(b) for b in wrap_axes(hf, wrap))
    if crop is not None:
        c = crop['crop']
        G = crop['geometry']
        X, Y = np.meshgrid(np.arange(c['w']) + c['x0'], np.arange(c['h']) + c['y0'])
        ii = np.mod(X, nx) if G['wrapX'] else np.clip(X, 0, nx - 1)
        jj = np.mod(Y, ny) if G['wrapY'] else np.clip(Y, 0, ny - 1)
        xs = (X + 0.5) / nx * w - w / 2 + hf.origin[0]
        ys = (Y + 0.5) / ny * w - w / 2 + hf.origin[1]
        return xs, ys, hf.heights_m[jj, ii], (X + 0.5) / nx, (Y + 0.5) / ny, (lambda a: np.asarray(a)[jj, ii])
    if step and step > 1 and side is None:
        side = max(2, nx // int(step))
    if side == 'auto':
        side = terrain_vertex_side(nx)
    if side is None or int(side) == nx == ny:
        if not (ex or ey):
            xs, ys = hf.grid_xy()
            U, V = np.meshgrid((np.arange(nx) + 0.5) / nx, (np.arange(ny) + 0.5) / ny)
            return xs, ys, hf.heights_m, U, V, (lambda a: np.asarray(a))
        # the seam row / column: one more vertex past the last texel centre, reading texel 0, so the mesh spans
        # exactly world_size and a copy at +world_size starts where this one ends (same position, same height)
        X, Y = np.meshgrid(np.arange(nx + ex), np.arange(ny + ey))
        ii, jj = np.mod(X, nx), np.mod(Y, ny)
        xs = (X + 0.5) / nx * w - w / 2 + hf.origin[0]
        ys = (Y + 0.5) / ny * w - w / 2 + hf.origin[1]
        return xs, ys, hf.heights_m[jj, ii], (X + 0.5) / nx, (Y + 0.5) / ny, (lambda a: np.asarray(a)[jj, ii])
    n = int(side)
    X, Y = np.meshgrid(np.arange(n + ex), np.arange(n + ey))
    xs = (X + 0.5) / n * w - w / 2 + hf.origin[0]
    ys = (Y + 0.5) / n * w - w / 2 + hf.origin[1]
    U, V = (X + 0.5) / n, (Y + 0.5) / n
    z = hf.display_z(n)[np.mod(Y, n), np.mod(X, n)]
    return xs, ys, z, U, V, (lambda a: field_height_bilinear(a, U, V))


def build_mesh(hf, name='EkigarTerrain', side=None, collection=None, attributes=True, mask_names=None,
               smooth=True, location=(0.0, 0.0, 0.0), crop=None, step=None, wrap=False):
    """A grid mesh of a Heightfield, displaced to the true height (metres), with a UV map in tile space (uv on the
    vertices' texel centres) and a FLOAT point attribute per mask ('ekigar_' + name) plus 'ekigar_height' (field
    units) and 'ekigar_hnorm' (height normalised to the field's range). Returns the object.

    side   None: one vertex per field texel (exact). 'auto': Ekigar's policy, terrain_vertex_side (1:1 up to 2048 a
           side). An int N: an N x N display grid on its own texel centres, heights and masks read bilinear (a box
           average when coarser than the field, never an alias). hf.height_at(x, y, side=N) samples that mesh.
    crop   a resolved cut (local_area.cut_for / resolve_cut): only that circle's crop window, at full resolution,
           wrapping across a periodic edge, with the local weight as 'ekigar_local_weight'
           (hf.height_at(x, y, wrap=True) samples it).
    wrap   True: on each periodic axis of the tile, one more vertex row / column past the last texel centre, reading
           texel 0 (the next tile's first texel), so the mesh spans exactly world_size and copies laid at multiples
           of world_size meet with no slit: the last vertices of one copy sit where the next copy's first ones do,
           at the same height. hf.height_at(x, y, wrap=True) samples it (and the copies, any distance out). Without
           it the vertices stop at the outermost texel centres, half a texel inside each edge.
    step   older spelling of side = resolution // step."""
    xs, ys, z, U, V, read = _layout(hf, side, step, crop, wrap)
    ny, nx = z.shape
    if nx < 2 or ny < 2:
        raise ValueError('build_mesh: need at least 2x2 vertices')
    me = bpy.data.meshes.new(name)
    nv = nx * ny
    me.vertices.add(nv)
    co = np.stack([xs.ravel(), ys.ravel(), z.ravel()], axis=1).astype(np.float32)
    me.vertices.foreach_set('co', co.ravel())
    j, i = np.mgrid[0:ny - 1, 0:nx - 1]
    a = (j * nx + i).ravel()
    quads = np.stack([a, a + 1, a + 1 + nx, a + nx], axis=1).astype(np.int32)     # (a, b, c, d), CCW from +z
    nf = quads.shape[0]
    me.loops.add(nf * 4)
    me.loops.foreach_set('vertex_index', quads.ravel())
    me.polygons.add(nf)
    me.polygons.foreach_set('loop_start', (np.arange(nf, dtype=np.int32) * 4))
    me.update(calc_edges=True)
    me.validate(clean_customdata=False)
    if smooth:
        me.polygons.foreach_set('use_smooth', np.ones(nf, dtype=bool))
    uv = me.uv_layers.new(name='UVMap')
    vid = quads.ravel()
    uv.data.foreach_set('uv', np.stack([U.ravel()[vid], V.ravel()[vid]], axis=1).astype(np.float32).ravel())
    if attributes:
        h = read(hf.height)
        lo, hi = float(hf.height.min()), float(hf.height.max())
        layers = {'height': h, 'hnorm': np.clip((h - lo) / max(hi - lo, 1e-4), 0.0, 1.0)}
        masks = dict(hf.masks())
        masks.update(hf.hydrology_masks())                 # those already computed (hf.hydrology() first to have them)
        for k in (mask_names if mask_names is not None else masks.keys()):
            layers[k] = read(masks[k] if k in masks else hf.mask(k))
        if crop is not None:
            from .local_area import weight_at_texel
            c = crop['crop']
            X, Y = np.meshgrid(np.arange(c['w']) + c['x0'], np.arange(c['h']) + c['y0'])
            layers['local_weight'] = weight_at_texel(crop, X, Y)
        for k, arr in layers.items():
            att = me.attributes.new('ekigar_' + k, 'FLOAT', 'POINT')
            att.data.foreach_set('value', np.asarray(arr, dtype=np.float32).ravel())
    obj = bpy.data.objects.new(name, me)
    obj.location = location
    (collection or bpy.context.scene.collection).objects.link(obj)
    obj['ekigar_world_size'] = hf.world_size
    obj['ekigar_vertical_scale'] = hf.vertical_scale
    obj['ekigar_resolution'] = list(hf.resolution)
    obj['ekigar_side'] = [nx, ny]
    obj['ekigar_crop'] = bool(crop is not None)
    obj['ekigar_wrap'] = list(wrap_axes(hf, wrap)) if crop is None else [False, False]
    return obj


def build_lake_mesh(hf, name='EkigarLakes', min_depth_m=0.5, collection=None, location=(0.0, 0.0, 0.0), **hydro):
    """The water surfaces of a Heightfield's filled depressions (hydrology.fill_depressions): a flat mesh at each
    lake's spill level over all its water, for every lake at least min_depth_m deep somewhere, grown one texel
    under the shore so the waterline is where the plane meets the ground, with the depth (metres) as
    'ekigar_lake_depth'. None when there is no lake that deep. Keyword arguments go to
    hf.hydrology() (sea_level, method ...)."""
    h = hf.hydrology(**hydro) if hydro else hf.hydrology()
    depth = h['lakeDepth_m']
    # a lake is every texel filled to one spill level; keep the lakes whose deepest point reaches min_depth_m, with
    # ALL their water (their shallows too, or the plane's edge would hang over the ground), then grow them one
    # texel at their own level so the water runs under the shore and the waterline is where plane meets ground
    filled = h['filled']
    wet_any = depth > 1e-9
    keep = np.zeros_like(wet_any)
    if wet_any.any():
        levels, inv = np.unique(filled[wet_any], return_inverse=True)
        deepest = np.zeros(len(levels))
        np.maximum.at(deepest, inv, depth[wet_any])
        keep[wet_any] = deepest[inv] >= min_depth_m
    lev = np.where(keep, filled, -np.inf)
    grown = lev.copy()
    for dj in (-1, 0, 1):
        for di in (-1, 0, 1):
            if di or dj:
                grown = np.maximum(grown, np.roll(np.roll(lev, dj, 0), di, 1))
    wet = np.isfinite(grown)
    quad = wet[:-1, :-1] & wet[1:, :-1] & wet[:-1, 1:] & wet[1:, 1:]
    if not quad.any():
        return None
    ny, nx = depth.shape
    used = np.zeros_like(wet)
    used[:-1, :-1] |= quad
    used[1:, :-1] |= quad
    used[:-1, 1:] |= quad
    used[1:, 1:] |= quad
    vid = -np.ones(depth.shape, dtype=np.int64)
    vid[used] = np.arange(int(used.sum()))
    xs, ys = hf.grid_xy()
    zf = (np.where(wet, grown, h['filled']) - hf.z_base) * hf.metres_per_unit
    me = bpy.data.meshes.new(name)
    co = np.stack([xs[used], ys[used], zf[used]], axis=1).astype(np.float32)
    me.vertices.add(len(co))
    me.vertices.foreach_set('co', co.ravel())
    j, i = np.nonzero(quad)
    quads = np.stack([vid[j, i], vid[j, i + 1], vid[j + 1, i + 1], vid[j + 1, i]], axis=1).astype(np.int32)
    nf = len(quads)
    me.loops.add(nf * 4)
    me.loops.foreach_set('vertex_index', quads.ravel())
    me.polygons.add(nf)
    me.polygons.foreach_set('loop_start', (np.arange(nf, dtype=np.int32) * 4))
    me.update(calc_edges=True)
    me.validate(clean_customdata=False)
    att = me.attributes.new('ekigar_lake_depth', 'FLOAT', 'POINT')
    att.data.foreach_set('value', depth[used].astype(np.float32))
    obj = bpy.data.objects.new(name, me)
    obj.location = location
    (collection or bpy.context.scene.collection).objects.link(obj)
    return obj


def export_glb(hf, path, side='auto', name='EkigarTerrain', material=None, attributes=False):
    """Ekigar's missing exportGLB, in Blender: the terrain mesh (Ekigar's display grid by default) written as a
    binary glTF through Blender's own exporter, with a material if given. Returns the path. The mesh is removed
    from the scene afterwards."""
    obj = build_mesh(hf, name=name, side=side, attributes=attributes)
    if material is not None:
        obj.data.materials.append(material)
    for o in bpy.context.scene.objects:
        o.select_set(False)
    obj.select_set(True)
    bpy.context.view_layer.objects.active = obj
    os.makedirs(os.path.dirname(os.path.abspath(path)) or '.', exist_ok=True)
    bpy.ops.export_scene.gltf(filepath=path, export_format='GLB', use_selection=True, export_apply=False,
                              export_attributes=bool(attributes), export_yup=True)
    me = obj.data
    bpy.data.objects.remove(obj, do_unlink=True)
    bpy.data.meshes.remove(me)
    return path


def _attr(nt, name, loc):
    n = nt.nodes.new('ShaderNodeAttribute')
    n.attribute_type = 'GEOMETRY'
    n.attribute_name = 'ekigar_' + name
    n.location = loc
    return n


def preview_material(mode='grey', name=None):
    """Ekigar's preview shading (src/nodes/preview_material.js) as a Blender material, reading build_mesh's
    attributes. 'grey' is a plain clay (albedo 0.5, roughness 0.92) for reading form; 'shaded' is Ekigar's rock ramp
    by height darkened on slopes; the other modes are its unlit diagnostics (height, slope, aspect, curvProfile and
    curvPlan as a diverging blue-red ramp, ridge red-blue). 'mask:<name>' is Ekigar's diagnostic view of any one mask
    or named output (grey, unlit), e.g. 'mask:wear', 'mask:floor'."""
    diagnostic = mode.startswith('mask:')
    if mode not in PREVIEW_MODES and not diagnostic:
        raise ValueError(f"preview_material: mode {mode!r} not in {PREVIEW_MODES} or 'mask:<name>'")
    mat = bpy.data.materials.new(name or f'ekigar_{mode}')
    mat.use_nodes = True
    nt = mat.node_tree
    nt.nodes.clear()
    out = nt.nodes.new('ShaderNodeOutputMaterial')
    out.location = (600, 0)
    if mode in ('grey', 'shaded'):
        bsdf = nt.nodes.new('ShaderNodeBsdfPrincipled')
        bsdf.location = (300, 0)
        bsdf.inputs['Roughness'].default_value = 0.92
        bsdf.inputs['Metallic'].default_value = 0.0
        if mode == 'grey':
            bsdf.inputs['Base Color'].default_value = (0.5, 0.5, 0.5, 1.0)
        else:
            hn = _attr(nt, 'hnorm', (-700, 120))
            sl = _attr(nt, 'slope', (-700, -120))
            rock = nt.nodes.new('ShaderNodeMix')
            rock.data_type = 'RGBA'
            rock.location = (-400, 120)
            rock.inputs[6].default_value = (0.21, 0.19, 0.17, 1.0)
            rock.inputs[7].default_value = (0.60, 0.55, 0.46, 1.0)
            nt.links.new(hn.outputs['Fac'], rock.inputs[0])
            ss = nt.nodes.new('ShaderNodeMapRange')
            ss.interpolation_type = 'SMOOTHSTEP'
            ss.location = (-400, -120)
            ss.inputs['From Min'].default_value = 0.25
            ss.inputs['From Max'].default_value = 0.75
            nt.links.new(sl.outputs['Fac'], ss.inputs['Value'])
            mix = nt.nodes.new('ShaderNodeMix')
            mix.data_type = 'RGBA'
            mix.location = (-100, 0)
            nt.links.new(ss.outputs['Result'], mix.inputs[0])
            nt.links.new(rock.outputs[2], mix.inputs[6])
            mix.inputs[7].default_value = (0.34, 0.28, 0.24, 1.0)
            nt.links.new(mix.outputs[2], bsdf.inputs['Base Color'])
        nt.links.new(bsdf.outputs['BSDF'], out.inputs['Surface'])
        return mat
    # unlit diagnostics: emission only (a mask must not be lit; shading it means reading the light, not the data)
    em = nt.nodes.new('ShaderNodeEmission')
    em.location = (300, 0)
    src = mode[5:] if diagnostic else {'height': 'hnorm'}.get(mode, mode)
    a = _attr(nt, src, (-600, 0))
    if diagnostic or mode in ('height', 'slope'):
        nt.links.new(a.outputs['Fac'], em.inputs['Color'])
    else:
        ramp = nt.nodes.new('ShaderNodeMix')
        ramp.data_type = 'RGBA'
        ramp.location = (0, 0)
        lo, hi = {'aspect': ((0.0, 0.35, 1.0), (1.0, 0.35, 0.0)),
                  'curvProfile': ((0.25, 0.45, 0.85), (0.88, 0.42, 0.28)),
                  'curvPlan': ((0.25, 0.45, 0.85), (0.88, 0.42, 0.28)),
                  'ridge': ((0.85, 0.25, 0.20), (0.20, 0.50, 0.90))}[mode]
        ramp.inputs[6].default_value = (*lo, 1.0)
        ramp.inputs[7].default_value = (*hi, 1.0)
        nt.links.new(a.outputs['Fac'], ramp.inputs[0])
        nt.links.new(ramp.outputs[2], em.inputs['Color'])
    nt.links.new(em.outputs['Emission'], out.inputs['Surface'])
    return mat
