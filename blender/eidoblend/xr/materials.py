"""eidoblend.xr.materials: materials that survive Blender's glTF exporter, for an XR page.

The exporter writes a Principled BSDF's constants and its IMAGE textures (through UV Map, Mapping as
KHR_texture_transform, Normal Map, Separate Color for packed channels, a Color Attribute multiplied in), emission with its
strength (KHR_materials_emissive_strength), alpha, and the unlit hookup (a colour into the output, a Background, or the
light-path trick: KHR_materials_unlit). Everything procedural (noise, voronoi, ramps, math on the geometry, attributes,
the camera, a box-projected image) it drops without a word, and the page shows a grey default.

    from eidoblend.xr import materials as M
    M.survey(bpy.data.materials)              # {material: {'kind', 'lost': [channels it would drop], ...}}
    rep = M.bake_for_gltf(objects, out_dir='work/<id>/vr/textures', texel_density=24)

bake_for_gltf bakes exactly the channels the exporter would lose, with Cycles (on the GPU: run it through the GPU slot),
into images on a dedicated UV map ('gltf_bake', Smart UV Project when the mesh has none), and gives each baked object ONE
material the exporter writes in full:
  - Principled: base colour (+ alpha), roughness and metallic packed as glTF's metallicRoughness (G, B), the normal
    (tangent space, bump included), the emission (colour x strength, normalised: the texture holds the colour, the
    strength the peak, as KHR_materials_emissive_strength); channels that are constants stay constants;
  - unlit (a colour into the output): the colour, still unlit;
  - anything else (mixes of shaders, groups): Cycles' own passes: diffuse colour, roughness, emission, normal; a Mix
    with a Transparent BSDF gives its factor as alpha.
Objects sharing a mesh and its materials (linked duplicates, the walkers an instance bake made) are baked once.
Objects with an `xr_material` custom property are drawn by the page with its own TSL material (the page's registry):
they get a flat fallback (the material's viewport colour) instead of a bake.
"""
from __future__ import annotations

import math
import os
import re

import bpy

from . import _bl

UV_NAME = 'gltf_bake'
# node types the exporter follows from a Principled input to an image
PASS_THROUGH = {'TEX_IMAGE', 'UVMAP', 'MAPPING', 'TEX_COORD', 'NORMAL_MAP', 'SEPARATE_COLOR', 'SEPRGB', 'REROUTE',
                'VERTEX_COLOR', 'RGB', 'VALUE'}
CHANNELS = ('Base Color', 'Alpha', 'Metallic', 'Roughness', 'Normal', 'Emission Color', 'Emission Strength')
IGNORED_LINKED = ('Subsurface Weight', 'Transmission Weight', 'Coat Weight', 'Coat Roughness', 'Sheen Weight',
                  'Specular IOR Level', 'IOR', 'Anisotropic', 'Thin Film Thickness')


# ------------------------------------------------------------------------------------------------ the survey ---

def _active_output(tree):
    outs = [n for n in tree.nodes if n.type == 'OUTPUT_MATERIAL']
    for n in outs:
        if n.is_active_output and n.target in ('ALL', 'CYCLES', 'EEVEE'):
            return n
    return outs[0] if outs else None


def _upstream(socket, seen=None):
    """Every node feeding a socket (through groups as opaque nodes)."""
    seen = set() if seen is None else seen
    out = []
    for link in socket.links if socket.is_linked else ():
        n = link.from_node
        if n.as_pointer() in seen:
            continue
        seen.add(n.as_pointer())
        out.append(n)
        for s in n.inputs:
            out += _upstream(s, seen)
    return out


CLIP_MATH = ('MULTIPLY', 'ROUND', 'GREATER_THAN', 'LESS_THAN', 'SUBTRACT')


def _image_chain_ok(socket):
    """True when the exporter writes what feeds `socket`: nothing, or images on UVs through the nodes it reads (UV Map,
    Mapping, Normal Map, Separate Color, a Color Attribute; an image times a constant or a Color Attribute (Mix
    Multiply: a factor), a scalar times a constant, an alpha clip (Round, x > cutoff, 1 - (x < cutoff)))."""
    if not socket.is_linked:
        return True
    for n in _upstream(socket):
        t = n.type
        if t in PASS_THROUGH:
            if t == 'TEX_IMAGE' and (n.image is None or n.projection != 'FLAT'):
                return False
            # texture coordinates other than the UVs (Object, Generated, Window ...), into an image or through a Mapping
            # node: the exporter writes the image on the UVs regardless
            for s in n.inputs:
                for lk in (s.links if s.is_linked else ()):
                    if lk.from_node.type == 'TEX_COORD' and lk.from_socket.name != 'UV':
                        return False
            continue
        if t == 'MIX' and n.blend_type == 'MULTIPLY':
            linked = [s for s in n.inputs if s.enabled and s.is_linked]
            if len(linked) <= 2 and all(s.links[0].from_node.type in ('TEX_IMAGE', 'VERTEX_COLOR', 'SEPARATE_COLOR',
                                                                       'REROUTE') for s in linked) \
                    and not n.inputs[0].is_linked:
                continue
            return False
        if t == 'MATH' and n.operation in CLIP_MATH and sum(1 for s in n.inputs if s.enabled and s.is_linked) <= 1:
            continue
        return False
    return True


def _from(socket):
    return socket.links[0].from_socket if socket.is_linked else None


def volume_only(mat):
    """True for a volume material with no surface (a haze or fog box: Principled Volume into the output's Volume, nothing
    into its Surface). glTF has no volumes, and Blender's exporter writes such a mesh with a default OPAQUE material: a
    grey box round the set."""
    if mat is None or not mat.use_nodes or mat.node_tree is None:
        return False
    out = _active_output(mat.node_tree)
    return out is not None and not out.inputs['Surface'].is_linked and out.inputs['Volume'].is_linked


def classify(mat):
    """{'kind': 'principled' | 'unlit' | 'emission' | 'other' | 'none', 'bsdf', 'surface' (the shader socket),
    'alpha' (a Mix-with-Transparent factor socket, or None), 'lost': channels the exporter would drop}."""
    info = {'kind': 'none', 'bsdf': None, 'surface': None, 'alpha': None, 'lost': [], 'ignored': []}
    if mat is None or not mat.use_nodes or mat.node_tree is None:
        return info
    out = _active_output(mat.node_tree)
    if out is None or not out.inputs['Surface'].is_linked:
        return info
    src = _from(out.inputs['Surface'])
    node = src.node
    # a Mix Shader with a Transparent BSDF: alpha is its factor
    if node.type == 'MIX_SHADER':
        a, b = node.inputs[1], node.inputs[2]
        if a.is_linked and a.links[0].from_node.type == 'BSDF_TRANSPARENT':
            info['alpha'] = node.inputs[0]
            src = _from(b)
            node = src.node if src is not None else None
    if node is None:
        return info
    info['surface'] = src
    if src.type == 'RGBA' or node.type == 'BACKGROUND':
        info['kind'] = 'unlit'
        col = src if src.type == 'RGBA' else node.inputs['Color']
        if src.type == 'RGBA':
            ok = _image_chain_ok_output(src)
        else:
            ok = _image_chain_ok(col)
        if not ok:
            info['lost'].append('Unlit Color')
        if info['alpha'] is not None and not _image_chain_ok(info['alpha']):
            info['lost'].append('Alpha')
        return info
    if node.type == 'BSDF_PRINCIPLED':
        info['kind'] = 'principled'
        info['bsdf'] = node
        for ch in CHANNELS:
            if not _image_chain_ok(node.inputs[ch]):
                info['lost'].append(ch)
        if info['alpha'] is not None and not _image_chain_ok(info['alpha']):
            info['lost'].append('Alpha')
        for ch in IGNORED_LINKED:
            if ch in node.inputs and node.inputs[ch].is_linked:
                info['ignored'].append(ch)
        return info
    if node.type == 'EMISSION':
        info['kind'] = 'emission'
        if not _image_chain_ok(node.inputs['Color']) or node.inputs['Strength'].is_linked:
            info['lost'].append('Emission Color')
        return info
    info['kind'] = 'other'
    info['lost'] = ['Base Color', 'Roughness', 'Normal', 'Emission Color']
    return info


def _image_chain_ok_output(out_socket):
    """An RGBA output socket (unlit): fine only when it IS an image (or a pass-through of one, or one times a
    constant)."""
    n = out_socket.node
    if n.type not in PASS_THROUGH and not (n.type == 'MIX' and n.blend_type == 'MULTIPLY'):
        return False
    for s in n.inputs:
        if s.enabled and not _image_chain_ok(s):
            return False
    if n.type == 'TEX_IMAGE' and (n.image is None or n.projection != 'FLAT'):
        return False
    return True


def survey(materials=None):
    """{material name: classify(...) without sockets} for every material (default: all in the file)."""
    out = {}
    for m in (materials if materials is not None else bpy.data.materials):
        c = classify(m)
        out[m.name] = {'kind': c['kind'], 'lost': c['lost'], 'ignored': c['ignored'],
                       'alpha_mix': c['alpha'] is not None}
    return out


# ---------------------------------------------------------------------------------------------- the bake ---

def _slug(s):
    return re.sub(r'[^A-Za-z0-9_.-]+', '_', s)[:60]


def _area(ob):
    me = ob.data
    sx, sy, sz = (abs(v) for v in ob.matrix_world.to_scale())
    k = (sx * sy * sz) ** (2.0 / 3.0) if sx * sy * sz > 0 else 1.0
    return sum(p.area for p in me.polygons) * k


def texture_size(ob, texel_density=24.0, min_size=256, max_size=2048, fill=0.6):
    """A power of two that gives the object about `texel_density` texels a metre on its UV atlas."""
    side = math.sqrt(max(_area(ob), 1e-6) / fill) * texel_density
    s = min_size
    while s < side and s < max_size:
        s *= 2
    return s


def ensure_bake_uv(ob, name=UV_NAME, angle=66.0, margin=0.004, log=print):
    """A UV map `name` with no overlaps (Smart UV Project) on the object's mesh; made once per mesh."""
    me = ob.data
    if name in me.uv_layers:
        return me.uv_layers[name]
    keep_active = me.uv_layers.active.name if me.uv_layers.active else None
    keep_render = next((u.name for u in me.uv_layers if u.active_render), None)
    uv = me.uv_layers.new(name=name)
    me.uv_layers.active = uv
    vl = bpy.context.view_layer
    for o in vl.objects:
        o.select_set(False)
    ob.select_set(True)
    vl.objects.active = ob
    with bpy.context.temp_override(active_object=ob, object=ob, selected_objects=[ob],
                                   selected_editable_objects=[ob]):
        bpy.ops.object.mode_set(mode='EDIT')
        bpy.ops.mesh.select_all(action='SELECT')
        bpy.ops.uv.smart_project(angle_limit=math.radians(angle), island_margin=margin, area_weight=0.0,
                                 correct_aspect=True, scale_to_bounds=False)
        bpy.ops.object.mode_set(mode='OBJECT')
    if keep_active and keep_active in me.uv_layers:
        me.uv_layers.active = me.uv_layers[keep_active]
    if keep_render and keep_render in me.uv_layers:
        me.uv_layers[keep_render].active_render = True
    if log:
        log(f'[xr.materials] {ob.name}: made UV map {name!r} (Smart UV Project)')
    return uv


class _Routing:
    """Temporary nodes and links in a material for one bake; undo() puts the tree back."""

    def __init__(self, mat):
        self.mat, self.tree = mat, mat.node_tree
        self.nodes, self.saved = [], []

    def node(self, kind):
        n = self.tree.nodes.new(kind)
        self.nodes.append(n)
        return n

    def relink(self, to_socket, from_socket):
        prev = _from(to_socket)
        self.saved.append((to_socket, prev))
        for lk in list(to_socket.links):
            self.tree.links.remove(lk)
        if from_socket is not None:
            self.tree.links.new(from_socket, to_socket)

    def undo(self):
        for to_socket, prev in reversed(self.saved):
            for lk in list(to_socket.links):
                self.tree.links.remove(lk)
            if prev is not None:
                self.tree.links.new(prev, to_socket)
        for n in self.nodes:
            self.tree.nodes.remove(n)
        self.nodes, self.saved = [], []


def _emit_source(R, out, value_socket, constant=None, strength_socket=None, strength_constant=1.0):
    """Route a socket (or a constant) through an Emission node into the output: an EMIT bake then records it."""
    em = R.node('ShaderNodeEmission')
    if value_socket is not None:
        src = _from(value_socket) if hasattr(value_socket, 'is_linked') and value_socket.is_output is False \
            else value_socket
        if src is not None:
            R.tree.links.new(src, em.inputs['Color'])
        else:
            dv = value_socket.default_value
            em.inputs['Color'].default_value = _as_rgba(dv)
    elif constant is not None:
        em.inputs['Color'].default_value = _as_rgba(constant)
    if strength_socket is not None and strength_socket.is_linked:
        R.tree.links.new(_from(strength_socket), em.inputs['Strength'])
    else:
        em.inputs['Strength'].default_value = float(strength_socket.default_value if strength_socket is not None
                                                    else strength_constant)
    R.relink(out.inputs['Surface'], em.outputs[0])
    return em


def _as_rgba(v):
    try:
        t = tuple(v)
    except TypeError:
        return (float(v),) * 3 + (1.0,)
    if len(t) >= 4:
        return t[:4]
    if len(t) == 3:
        return t + (1.0,)
    return (t[0],) * 3 + (1.0,)


def _new_float_image(name, size, alpha=True):
    img = bpy.data.images.get(name)
    if img is not None:
        bpy.data.images.remove(img)
    img = bpy.data.images.new(name, size, size, alpha=alpha, float_buffer=True)
    img.colorspace_settings.name = 'Non-Color'
    return img


def _bake(ob, kind, images_by_mat, margin, pass_filter=None, normal_space='TANGENT'):
    """One Cycles bake of `ob` into the image node made active in each of its materials."""
    vl = bpy.context.view_layer
    for o in vl.objects:
        o.select_set(False)
    ob.select_set(True)
    vl.objects.active = ob
    kw = dict(type=kind, margin=margin, use_clear=True, target='IMAGE_TEXTURES', uv_layer=UV_NAME)
    if kind == 'NORMAL':
        kw['normal_space'] = normal_space
    if pass_filter:
        kw['pass_filter'] = pass_filter
    with bpy.context.temp_override(active_object=ob, object=ob, selected_objects=[ob],
                                   selected_editable_objects=[ob]):
        bpy.ops.object.bake(**kw)


def _pixels(img):
    import numpy as np
    a = np.empty(img.size[0] * img.size[1] * 4, dtype=np.float32)
    img.pixels.foreach_get(a)
    return a.reshape(img.size[1], img.size[0], 4)


def _linear_to_srgb(x):
    import numpy as np
    x = np.clip(x, 0.0, 1.0)
    return np.where(x <= 0.0031308, x * 12.92, 1.055 * np.power(x, 1 / 2.4) - 0.055)


def _write_png(name, arr, path, srgb):
    """An 8-bit PNG from a float array (H, W, 4) holding final display values (already encoded)."""
    import numpy as np
    h, w = arr.shape[:2]
    img = bpy.data.images.get(name)
    if img is not None:
        bpy.data.images.remove(img)
    img = bpy.data.images.new(name, w, h, alpha=True, float_buffer=False)
    img.colorspace_settings.name = 'sRGB' if srgb else 'Non-Color'
    img.pixels.foreach_set(np.ascontiguousarray(arr, dtype=np.float32).ravel())
    img.filepath_raw = path
    img.file_format = 'PNG'
    os.makedirs(os.path.dirname(path), exist_ok=True)
    img.save()
    img.source = 'FILE'
    img.filepath = path
    img.reload()
    return img


def _socket_value(sock):
    try:
        return tuple(sock.default_value)
    except TypeError:
        return float(sock.default_value)


def _group_key(ob):
    return (ob.data.as_pointer(), tuple(s.material.name if s.material else '' for s in ob.material_slots))


def used_materials(ob):
    """The materials the object's faces use (a slot no face uses, a VRM's outline material, does not count)."""
    me = ob.data
    n = len(ob.material_slots)
    if n == 0:
        return []
    idx = [0] * len(me.polygons)
    me.polygons.foreach_get('material_index', idx)
    used = sorted({min(i, n - 1) for i in idx}) if idx else []
    out = []
    for i in used:
        m = ob.material_slots[i].material
        if m is not None and m not in out:
            out.append(m)
    return out


def ensure_vrm_addon(log=print):
    """Enable the VRM add-on when the file holds a VRM cast's MToon materials (nodes the add-on names 'Mtoon1...').
    A .blend opened headless (export_cli.py) starts without add-ons: its MToon materials are then node groups this
    module cannot read (they would go out unconverted) and the add-on's UV drivers look like animated material
    values. True when the add-on is on (or nothing needs it)."""
    needs = any(n.name.startswith('Mtoon1') for m in bpy.data.materials if m.node_tree is not None
                for n in m.node_tree.nodes)
    if not needs:
        return True
    try:
        import addon_utils
        from ..characters.vrm import ADDON, enable_addon
        if not addon_utils.check(ADDON)[1]:
            enable_addon()
            if log:
                log('[xr.materials] the VRM add-on enabled: the cast\'s MToon materials are read as MToon')
        return bool(addon_utils.check(ADDON)[1])
    except Exception as e:                                # not installed: the materials go out as the exporter sees them
        if log:
            log(f'[xr.materials] the VRM add-on could not be enabled ({e}): MToon materials are not converted')
        return False


def mtoon(mat):
    """The VRM add-on's MToon settings of a material (its glTF-shaped mtoon1 group), or None."""
    ext = getattr(mat, 'vrm_addon_extension', None) if mat is not None else None
    m1 = getattr(ext, 'mtoon1', None) if ext is not None else None
    return m1 if m1 is not None and getattr(m1, 'enabled', False) else None


def _src(tex_info):
    try:
        return tex_info.index.source
    except AttributeError:
        return None


def mtoon_to_gltf(mat, unlit=False):
    """A VRM MToon material as one Blender's glTF exporter writes in full: the add-on's own glTF-shaped settings
    (base colour texture x factor, normal map, emissive texture x factor x strength, alpha mode and cutoff, double
    sided) on a Principled BSDF (roughness 0.9, no metal), or unlit with unlit=True. An outline material becomes its
    outline colour, unlit. The toon ramp itself (shade colour, shading shift, rim, matcap) is not glTF: three-vrm's
    MToon material would draw it; the page draws the PBR stand-in. Returns the new material."""
    m1 = mtoon(mat)
    new = _bl.new_material(f'gltf_{_slug(mat.name)}')
    T = _bl.Tree(new.node_tree)
    pbr = m1.pbr_metallic_roughness
    f = tuple(pbr.base_color_factor)
    if getattr(m1, 'is_outline_material', False):
        try:
            oc = tuple(m1.extensions.vrmc_materials_mtoon.outline_color_factor)[:3]
        except AttributeError:
            oc = (0.0, 0.0, 0.0)
        _bl.unlit_output(T, T.rgb(oc))
        new.diffuse_color = oc + (1.0,)
        new['xr_mtoon_outline'] = mat.name
        return new
    img = _src(pbr.base_color_texture)
    col = None
    if img is not None:
        tex = T.node('ShaderNodeTexImage')
        tex.image = img
        col = tex.outputs['Color']
        if any(abs(x - 1.0) > 1e-6 for x in f[:3]):
            col = T.mix_rgb(1.0, col, f[:3] + (1.0,), blend='MULTIPLY')
    mode = getattr(m1, 'alpha_mode', 'OPAQUE')
    if unlit:
        _bl.unlit_output(T, col if col is not None else T.rgb(f))
    else:
        b = T.node('ShaderNodeBsdfPrincipled', inputs={'Roughness': 0.9, 'Metallic': 0.0})
        if col is not None:
            T.link(col, b.inputs['Base Color'])
        else:
            b.inputs['Base Color'].default_value = f[:3] + (1.0,)
        nimg = _src(m1.normal_texture)
        if nimg is not None:
            nt = T.node('ShaderNodeTexImage')
            nt.image = nimg
            nimg.colorspace_settings.name = 'Non-Color'
            nm = T.node('ShaderNodeNormalMap')
            T.link(nt.outputs['Color'], nm.inputs['Color'])
            T.link(nm.outputs[0], b.inputs['Normal'])
        ef = tuple(m1.emissive_factor)
        try:
            es = float(m1.extensions.khr_materials_emissive_strength.emissive_strength)
        except AttributeError:
            es = 1.0
        eimg = _src(m1.emissive_texture)
        if eimg is not None:
            et = T.node('ShaderNodeTexImage')
            et.image = eimg
            T.link(T.mix_rgb(1.0, et.outputs['Color'], tuple(ef) + (1.0,), blend='MULTIPLY'), b.inputs['Emission Color'])
            b.inputs['Emission Strength'].default_value = es
        elif max(ef) > 0:
            b.inputs['Emission Color'].default_value = tuple(ef) + (1.0,)
            b.inputs['Emission Strength'].default_value = es
        if mode in ('MASK', 'BLEND') and img is not None:
            if mode == 'MASK':
                gt = T.math('GREATER_THAN', tex.outputs['Alpha'], float(getattr(m1, 'alpha_cutoff', 0.5)))
                T.link(gt, b.inputs['Alpha'])           # the exporter reads this as alphaMode MASK with the cutoff
            else:
                T.link(tex.outputs['Alpha'], b.inputs['Alpha'])
            new.surface_render_method = 'DITHERED'
        o = T.node('ShaderNodeOutputMaterial')
        T.link(b.outputs[0], o.inputs['Surface'])
    new.use_backface_culling = not bool(getattr(m1, 'double_sided', False))
    new.diffuse_color = f[:3] + (1.0,)
    new['xr_mtoon_from'] = mat.name
    return new


MTOON_OUTLINE_GROUP = 'VRM Add-on MToon'          # the add-on's outline node group: 'VRM Add-on MToon 1.0 Outline ...'


def drop_mtoon_outlines(objects, log=print):
    """Switch off the VRM add-on's MToon outline modifiers (Geometry Nodes inverted hulls) on `objects`: the page has
    no MToon to draw them, and applied at the rest pose they would stand still while the body moves. Returns the
    object names."""
    off = []
    for ob in objects:
        for m in getattr(ob, 'modifiers', []):
            ng = getattr(m, 'node_group', None)
            if m.type == 'NODES' and ng is not None and ng.name.startswith(MTOON_OUTLINE_GROUP) and 'Outline' in ng.name:
                if m.show_render or m.show_viewport:
                    m.show_render = m.show_viewport = False
                    off.append(ob.name)
    if log and off:
        log(f'[xr.materials] MToon outlines off on {len(off)} mesh(es): {", ".join(sorted(set(off)))[:200]}')
    return sorted(set(off))


def convert_mtoon(objects, unlit=False, log=print):
    """Replace every MToon material on `objects` by mtoon_to_gltf's (one conversion per material). Returns
    {material name: new name}."""
    done = {}
    for ob in objects:
        if ob.type != 'MESH':
            continue
        for s in ob.material_slots:
            m = s.material
            if m is None or mtoon(m) is None:
                continue
            if m.name not in done:
                done[m.name] = mtoon_to_gltf(m, unlit=unlit)
            s.material = done[m.name]
    if log and done:
        log(f'[xr.materials] MToon -> glTF ({"unlit" if unlit else "PBR stand-in"}): {", ".join(sorted(done))}')
    return {k: v.name for k, v in done.items()}


def fallback_material(ob, name=None):
    """A flat material for an object the page draws with its own TSL material (xr_material): its viewport colour,
    unlit when the original is."""
    src = ob.material_slots[0].material if ob.material_slots and ob.material_slots[0].material else None
    kind = classify(src)['kind'] if src else 'principled'
    m = _bl.new_material(name or f'xr_fallback_{_slug(ob.name)}')
    T = _bl.Tree(m.node_tree)
    col = tuple(src.diffuse_color) if src else (0.5, 0.5, 0.5, 1.0)
    if kind == 'unlit':
        _bl.unlit_output(T, T.rgb(col))
    else:
        b = T.node('ShaderNodeBsdfPrincipled', inputs={'Base Color': col})
        o = T.node('ShaderNodeOutputMaterial')
        T.link(b.outputs[0], o.inputs['Surface'])
    m.diffuse_color = col
    if src is not None:
        m['xr_source_material'] = src.name
    ob.data.materials.clear()
    ob.data.materials.append(m)
    return m


def _tree_images(tree, seen_trees):
    """Every image an Image Texture node of a node tree (and the groups in it) reads."""
    for n in tree.nodes:
        if n.type == 'TEX_IMAGE' and n.image is not None:
            yield n.image
        elif n.type == 'GROUP' and n.node_tree is not None and n.node_tree.name not in seen_trees:
            seen_trees.add(n.node_tree.name)
            yield from _tree_images(n.node_tree, seen_trees)


def cap_images(objects, max_size=2048, log=print):
    """Scale the images the objects' materials read down to max_size pixels on the long side: the headset uploads every
    texture uncompressed (a 4096 RGBA map with its mips is about 90 MB of its GPU memory). In memory only (an export
    runs on a .blend it does not save): each image is scaled and its pixels written back, which marks it changed, so
    the glTF exporter encodes the scaled pixels (a JPEG as JPEG, anything else as PNG, or --images' format) instead of
    copying the file. Images already within the cap, sequences, movies and UDIM sets are left as they are. Returns
    [(image, (w, h) before, (w, h) after)]."""
    import numpy as np
    done, trees, out = set(), set(), []
    for ob in objects:
        if ob.type != 'MESH':
            continue
        for m in used_materials(ob):
            if m.node_tree is None:
                continue
            for img in _tree_images(m.node_tree, trees):
                if img.name in done:
                    continue
                done.add(img.name)
                if img.source not in ('FILE', 'GENERATED') or img.type != 'IMAGE':
                    continue
                w, h = img.size
                if not w or not h or max(w, h) <= max_size:
                    continue
                k = max_size / max(w, h)
                nw, nh = max(1, round(w * k)), max(1, round(h * k))
                img.scale(nw, nh)
                px = np.empty(len(img.pixels), np.float32)
                img.pixels.foreach_get(px)
                img.pixels.foreach_set(px)             # a scale alone leaves is_dirty off (the exporter's T95616 note)
                out.append((img.name, (w, h), (nw, nh)))
    if log and out:
        log(f'[xr.materials] {len(out)} image(s) scaled to {max_size} px at most: '
            + ', '.join(f'{n} {a[0]}x{a[1]} -> {b[0]}x{b[1]}' for n, a, b in out[:8]) + (' ...' if len(out) > 8 else ''))
    return out


def bake_for_gltf(objects, out_dir, *, texel_density=24.0, min_size=256, max_size=2048, samples=4, margin=8,
                  device='GPU', bake_all=False, log=print):
    """Bake the channels the glTF exporter would drop on `objects` (meshes), into PNGs in out_dir. Returns
    {'baked': {object: {'size', 'channels', 'kind', 'images'}}, 'kept': [objects already exportable],
    'fallback': [objects with xr_material], 'seconds'}."""
    import time
    t0 = time.time()
    sc = bpy.context.scene
    keep_engine, keep_samples = sc.render.engine, sc.cycles.samples
    keep_device = sc.cycles.device
    rep = {'baked': {}, 'kept': [], 'fallback': [], 'ignored': {}}
    rep['mtoon'] = convert_mtoon(objects, log=log)          # the cast's MToon: converted, never baked
    groups = {}
    for ob in objects:
        if ob.type != 'MESH':
            continue
        if ob.get('xr_material'):
            fallback_material(ob)
            rep['fallback'].append(ob.name)
            continue
        infos = [classify(m) for m in used_materials(ob)]
        lost = sorted({c for i in infos for c in i['lost']})
        for i in infos:
            if i['ignored']:
                rep['ignored'][ob.name] = i['ignored']
        varies = len({i['kind'] for i in infos}) > 1
        if not infos or (not lost and not bake_all and not varies):
            rep['kept'].append(ob.name)
            continue
        groups.setdefault(_group_key(ob), []).append(ob)
    if not groups:
        rep['seconds'] = time.time() - t0
        return rep
    dev = _bl.cycles_gpu(sc, log) if device == 'GPU' else 'CPU'
    sc.render.engine = 'CYCLES'
    if dev == 'CPU':                                           # (a film saved with Cycles on the GPU stays off it)
        sc.cycles.device = 'CPU'
    sc.cycles.samples = int(samples)
    sc.render.bake.margin_type = 'EXTEND'
    try:
        for key, obs in groups.items():
            ob = obs[0]
            r = _bake_object(ob, out_dir, texel_density, min_size, max_size, margin, log)
            # the group shares the mesh, so its (data-linked) material is already the baked one; slots linked to the
            # OBJECT keep their own material: point them at the bake too
            for o in obs:
                for s in o.material_slots:
                    if s.link == 'OBJECT':
                        s.material = r['material']
            r['shared_by'] = [o.name for o in obs]
            r['device'] = dev
            mat = r.pop('material')
            r['material'] = mat.name
            rep['baked'][ob.name] = r
    finally:
        sc.render.engine, sc.cycles.samples, sc.cycles.device = keep_engine, keep_samples, keep_device
    rep['seconds'] = round(time.time() - t0, 2)
    return rep


def _bake_object(ob, out_dir, texel_density, min_size, max_size, margin, log):
    import numpy as np
    size = texture_size(ob, texel_density, min_size, max_size)
    ensure_bake_uv(ob, log=log)
    # the bake's UV map becomes the mesh's ACTIVE one (its active render map, which the film's own image textures read,
    # stays). Blender 5.2's tangent-space normal bake writes its texels on the bake's uv_layer but in the tangent frame
    # of the ACTIVE map (measured: three maps turned against each other, the bake follows the active one), and the glTF
    # exporter computes the GLB's TANGENT attribute on the active map too. Left on the film's own map, the two agreed
    # with each other but not with the texture's own texCoord: right in three while the GLB carries its tangents, half a
    # turn wrong on a plane (bumps read as dents) wherever tangents are made again from the normal texture's UVs, as
    # glTF prescribes (a viewer, or a compressor that drops them). On the bake's map all three agree
    ob.data.uv_layers.active = ob.data.uv_layers[UV_NAME]
    mats = used_materials(ob)
    infos = {m.name: classify(m) for m in mats}
    kinds = {i['kind'] for i in infos.values()}
    unlit = kinds == {'unlit'}
    tag = _slug(ob.name)
    images = {}

    def bake_channel(ch, how):
        """how(material, routing, output) sets up one material for the bake; returns the float pixels."""
        img = _new_float_image(f'_bake_{tag}_{ch}', size)
        routs = []
        for m in mats:
            R = _Routing(m)
            out = _active_output(m.node_tree)
            tex = R.node('ShaderNodeTexImage')
            tex.image = img
            m.node_tree.nodes.active = tex
            how(m, R, out)
            routs.append(R)
        kind = 'NORMAL' if ch == 'normal' else ('DIFFUSE' if ch == 'diffuse' else
                                                 ('ROUGHNESS' if ch == 'pass_roughness' else 'EMIT'))
        try:
            _bake(ob, kind, None, margin, pass_filter={'COLOR'} if kind == 'DIFFUSE' else None)
        finally:
            for R in routs:
                R.undo()
        px = _pixels(img).copy()
        bpy.data.images.remove(img)
        return px

    def principled_input(name):
        def how(m, R, out):
            i = infos[m.name]
            if i['kind'] == 'principled':
                s = i['bsdf'].inputs[name]
                _emit_source(R, out, s)
            elif i['kind'] == 'unlit':
                # an unlit slot on a lit object: its colour as the base colour, black emission
                _emit_source(R, out, i['surface'] if name == 'Base Color' else None,
                             constant=(0, 0, 0, 1) if name != 'Base Color' else None)
            else:
                _emit_source(R, out, None, constant={'Metallic': 0.0, 'Roughness': 0.5, 'Alpha': 1.0}.get(name, 0.0))
        return how

    def emission_how(m, R, out):
        i = infos[m.name]
        if i['kind'] == 'principled':
            b = i['bsdf']
            _emit_source(R, out, b.inputs['Emission Color'], strength_socket=b.inputs['Emission Strength'])
        elif i['kind'] == 'emission':
            em = out.inputs['Surface'].links[0].from_node if out.inputs['Surface'].is_linked else None
            if em is not None and em.type == 'EMISSION':
                _emit_source(R, out, em.inputs['Color'], strength_socket=em.inputs['Strength'])
        elif i['kind'] == 'unlit':
            _emit_source(R, out, None, constant=(0, 0, 0, 1))
        # 'other': the shader as it is (an EMIT bake records its emission)

    def unlit_how(m, R, out):
        i = infos[m.name]
        src = i['surface']
        if i['kind'] == 'unlit':
            if src.type == 'RGBA':
                _emit_source(R, out, src)
            else:
                bg = src.node
                _emit_source(R, out, bg.inputs['Color'])
        else:
            _emit_source(R, out, None, constant=(0.5, 0.5, 0.5, 1))

    def alpha_how(m, R, out):
        i = infos[m.name]
        if i['alpha'] is not None:
            _emit_source(R, out, i['alpha'])
        elif i['kind'] == 'principled':
            _emit_source(R, out, i['bsdf'].inputs['Alpha'])
        else:
            _emit_source(R, out, None, constant=1.0)

    def normal_how(m, R, out):
        pass                                                   # the material as it is: a NORMAL bake reads its normal

    def need(ch):
        return any(ch in i['lost'] for i in infos.values()) or len(mats) > 1

    def all_const(name, default):
        vals = set()
        for m in mats:
            i = infos[m.name]
            if i['kind'] != 'principled':
                return None
            s = i['bsdf'].inputs[name]
            if s.is_linked:
                return None
            v = _socket_value(s)
            vals.add(v if not isinstance(v, tuple) else tuple(round(x, 5) for x in v))
        return vals.pop() if len(vals) == 1 else (None if vals else default)

    has_alpha = any(i['alpha'] is not None or (i['kind'] == 'principled' and (
        i['bsdf'].inputs['Alpha'].is_linked or i['bsdf'].inputs['Alpha'].default_value < 0.999)) for i in infos.values())
    baked = []
    new = _bl.new_material(f'gltf_{tag}')
    T = _bl.Tree(new.node_tree)
    uvn = T.node('ShaderNodeUVMap', uv_map=UV_NAME)

    def tex_node(img, non_color=False):
        n = T.node('ShaderNodeTexImage')
        n.image = img
        n.interpolation = 'Linear'
        T.link(uvn.outputs[0], n.inputs['Vector'])
        if non_color:
            img.colorspace_settings.name = 'Non-Color'
        return n

    if unlit:
        col = bake_channel('unlit', unlit_how)
        alpha = bake_channel('alpha', alpha_how)[..., 0] if has_alpha else None
        rgba = np.empty_like(col)
        rgba[..., :3] = _linear_to_srgb(col[..., :3])
        rgba[..., 3] = 1.0 if alpha is None else np.clip(alpha, 0, 1)
        path = os.path.join(out_dir, f'{tag}_color.png')
        img = _write_png(f'{tag}_color', rgba, path, srgb=True)
        images['color'] = path
        baked.append('unlit colour')
        t = tex_node(img)
        if has_alpha:
            # the exporter's unlit + alpha pattern: Mix(alpha) of Transparent and the colour
            mix = T.node('ShaderNodeMixShader')
            tr = T.node('ShaderNodeBsdfTransparent')
            T.link(t.outputs['Alpha'], mix.inputs[0])
            T.link(tr.outputs[0], mix.inputs[1])
            T.link(t.outputs['Color'], mix.inputs[2])
            o = T.node('ShaderNodeOutputMaterial')
            T.link(mix.outputs[0], o.inputs['Surface'])
            new.surface_render_method = 'DITHERED'
        else:
            _bl.unlit_output(T, t.outputs['Color'])
    else:
        bsdf = T.node('ShaderNodeBsdfPrincipled')
        o = T.node('ShaderNodeOutputMaterial')
        T.link(bsdf.outputs[0], o.inputs['Surface'])
        generic = any(i['kind'] == 'other' for i in infos.values())
        # base colour (+ alpha)
        base_const = all_const('Base Color', None)
        if base_const is not None and not need('Base Color') and not generic:
            bsdf.inputs['Base Color'].default_value = base_const
        else:
            col = bake_channel('diffuse', lambda m, R, out: None) if generic else \
                bake_channel('base', principled_input('Base Color'))
            alpha = None
            if has_alpha:
                alpha = bake_channel('alpha', alpha_how)[..., 0]
            rgba = np.empty_like(col)
            rgba[..., :3] = _linear_to_srgb(col[..., :3])
            rgba[..., 3] = 1.0 if alpha is None else np.clip(alpha, 0, 1)
            path = os.path.join(out_dir, f'{tag}_base.png')
            img = _write_png(f'{tag}_base', rgba, path, srgb=True)
            images['base'] = path
            baked.append('base colour' + (' + alpha' if alpha is not None else ''))
            t = tex_node(img)
            T.link(t.outputs['Color'], bsdf.inputs['Base Color'])
            if alpha is not None:
                T.link(t.outputs['Alpha'], bsdf.inputs['Alpha'])
                new.surface_render_method = 'DITHERED'
        # roughness + metallic -> metallicRoughness (G = roughness, B = metallic)
        r_const = all_const('Roughness', 0.5)
        m_const = all_const('Metallic', 0.0)
        need_r = generic or need('Roughness') or r_const is None
        need_m = (not generic) and (need('Metallic') or m_const is None)
        if need_r or need_m:
            if generic:
                rough = bake_channel('pass_roughness', lambda m, R, out: None)[..., 0]
            elif need_r:
                rough = bake_channel('rough', principled_input('Roughness'))[..., 0]
            else:
                rough = None
            metal = bake_channel('metal', principled_input('Metallic'))[..., 0] if need_m else None
            h, w = (rough if rough is not None else metal).shape
            orm = np.ones((h, w, 4), dtype=np.float32)
            orm[..., 1] = np.clip(rough, 0, 1) if rough is not None else float(r_const)
            orm[..., 2] = np.clip(metal, 0, 1) if metal is not None else float(m_const or 0.0)
            path = os.path.join(out_dir, f'{tag}_orm.png')
            img = _write_png(f'{tag}_orm', orm, path, srgb=False)
            images['orm'] = path
            baked.append('roughness' * bool(rough is not None) + ' + metallic' * bool(metal is not None))
            t = tex_node(img, non_color=True)
            sep = T.node('ShaderNodeSeparateColor')
            T.link(t.outputs['Color'], sep.inputs[0])
            T.link(sep.outputs['Green'], bsdf.inputs['Roughness'])
            T.link(sep.outputs['Blue'], bsdf.inputs['Metallic'])
        else:
            bsdf.inputs['Roughness'].default_value = float(r_const)
            bsdf.inputs['Metallic'].default_value = float(m_const or 0.0)
        # normal
        if generic or need('Normal'):
            nrm = bake_channel('normal', normal_how)
            path = os.path.join(out_dir, f'{tag}_normal.png')
            nrm[..., 3] = 1.0
            img = _write_png(f'{tag}_normal', np.clip(nrm, 0, 1), path, srgb=False)
            images['normal'] = path
            baked.append('normal')
            t = tex_node(img, non_color=True)
            nm = T.node('ShaderNodeNormalMap', uv_map=UV_NAME)
            T.link(t.outputs['Color'], nm.inputs['Color'])
            T.link(nm.outputs[0], bsdf.inputs['Normal'])
        # emission
        e_needed = generic or need('Emission Color') or need('Emission Strength') or \
            any(i['kind'] == 'emission' for i in infos.values())
        e_const = all_const('Emission Color', (0, 0, 0, 1))
        s_const = all_const('Emission Strength', 0.0)
        if e_needed or e_const is None or s_const is None:
            em = bake_channel('emit', emission_how)[..., :3]
            peak = float(np.max(em)) if em.size else 0.0
            if peak > 1e-5:
                rgba = np.ones(em.shape[:2] + (4,), dtype=np.float32)
                rgba[..., :3] = _linear_to_srgb(em / peak)
                path = os.path.join(out_dir, f'{tag}_emission.png')
                img = _write_png(f'{tag}_emission', rgba, path, srgb=True)
                images['emission'] = path
                baked.append(f'emission (peak {peak:.3g})')
                t = tex_node(img)
                T.link(t.outputs['Color'], bsdf.inputs['Emission Color'])
                bsdf.inputs['Emission Strength'].default_value = peak
        else:
            bsdf.inputs['Emission Color'].default_value = e_const
            bsdf.inputs['Emission Strength'].default_value = float(s_const)
    new['xr_baked_from'] = ', '.join(m.name for m in mats)
    new.diffuse_color = mats[0].diffuse_color
    ob.data.materials.clear()
    ob.data.materials.append(new)
    for p in ob.data.polygons:
        p.material_index = 0
    if log:
        log(f'[xr.materials] {ob.name}: baked {", ".join(baked) or "nothing"} at {size} px -> {new.name}')
    return {'size': size, 'channels': baked, 'kind': 'unlit' if unlit else 'principled', 'images': images,
            'material': new, 'from': [m.name for m in mats]}
