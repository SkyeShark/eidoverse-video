"""eidoblend.characters.robotics.materials: materials.js prepareMaterials, in Blender.

The kit's GLBs carry finished, baked maps; Blender's glTF importer builds each material (base colour, metallic-
roughness, normal map, occlusion) as an ordinary Principled BSDF. This module then does what prepareMaterials does:

    prepare_materials(objects, gltf_dir, textures=True, color/primary, accent, filament) -> RobotMaterials
        every kit material with eidoverse_recolor extras gets the APPROVED LINEAR MASK COMPOSITION as its base colour:
            fixed.rgb + primary * mask.r + accent * mask.g  (+ filament * mask.b when filament_channel is 'b')
        the palette lives in one shader node group per robot (RGB nodes 'primary', 'accent', 'filament'), initialised
        from the first recolourable material's default_primary_linear / default_accent_linear, filament #218675
    RobotMaterials.set_color(primary, accent)        setColor: '#rrggbb' / 0xrrggbb / an sRGB triple
    RobotMaterials.set_filament(color)               the palette's filament colour (the dispenser's mask.b)
    RobotMaterials.palette / .materials / .colors()

textures=False (geometry-only inspection, the WebGPU edition's {textures: false}): every image node is removed and the
base colour is three's 1x1 (220, 220, 220) stand-in map, linear 0.863, times the material's own factor; no recolour.

Mirrored placements: never reflect normal-map green or tangent.w to compensate. The WebGPU runtime corrects the
tangent-frame parity per object from its world matrix's determinant (a 'parity' uniform on normalScale.y). Blender's
Normal Map node already does the same: its tangent-space bitangent carries the object's negative-scale sign, so a
reflected instance (the humanoid's left side, a child re-attached under a mirrored parent) shades like its source.
tests/robotics/test_normal_parity.py measures that on a mirrored kit module.

Occlusion: the importer routes a material's occlusion texture into its "glTF Material Output" group, which EEVEE does not
render. three's aoMap only darkens indirect light; EEVEE's horizon scan and ray-traced GI occlude the world light in the
crevices themselves, so the baked AO is not multiplied in (it would darken the direct light too).
"""

from __future__ import annotations

import os

import bpy

from . import io as kio

DEFAULT_FILAMENT = '#218675'


def to_linear(c):
    """'#rrggbb', 0xrrggbb or an (r, g, b) in sRGB 0..1 -> linear RGB (three's Color.set with colour management)"""
    if isinstance(c, str):
        h = c.lstrip('#')
        if len(h) == 3:
            h = ''.join(ch * 2 for ch in h)
        c = [int(h[i:i + 2], 16) / 255.0 for i in (0, 2, 4)]
    elif isinstance(c, int):
        c = [((c >> 16) & 255) / 255.0, ((c >> 8) & 255) / 255.0, (c & 255) / 255.0]
    return tuple((x / 12.92) if x <= 0.04045 else ((x + 0.055) / 1.055) ** 2.4 for x in list(c)[:3])


def to_srgb_hex(lin):
    def enc(x):
        x = max(0.0, min(1.0, x))
        return 12.92 * x if x <= 0.0031308 else 1.055 * x ** (1 / 2.4) - 0.055
    return '#' + ''.join(f'{int(round(enc(x) * 255)):02x}' for x in lin[:3])


def _plain(v):
    if hasattr(v, 'to_dict'):
        return v.to_dict()
    if hasattr(v, 'to_list'):
        return v.to_list()
    return v


def _palette_group(name):
    ng = bpy.data.node_groups.new(name, 'ShaderNodeTree')
    for k in ('primary', 'accent', 'filament'):
        ng.interface.new_socket(name=k, in_out='OUTPUT', socket_type='NodeSocketColor')
    out = ng.nodes.new('NodeGroupOutput')
    for i, k in enumerate(('primary', 'accent', 'filament')):
        n = ng.nodes.new('ShaderNodeRGB')
        n.name = n.label = k
        n.location = (-300, -200 * i)
        ng.links.new(n.outputs[0], out.inputs[k])
    return ng


class RobotMaterials:
    def __init__(self, palette, materials):
        self.palette, self.materials = palette, materials

    def _set(self, key, c):
        if c is not None:
            self.palette.nodes[key].outputs[0].default_value = tuple(to_linear(c)) + (1.0,)

    def set_color(self, primary=None, accent=None):
        self._set('primary', primary)
        self._set('accent', accent)

    def set_filament(self, color):
        self._set('filament', color)

    def colors(self):
        """{'primary', 'accent', 'filament'}: the palette as linear RGB"""
        return {k: tuple(self.palette.nodes[k].outputs[0].default_value[:3]) for k in ('primary', 'accent', 'filament')}


def _bsdf(nt):
    return next((n for n in nt.nodes if n.type == 'BSDF_PRINCIPLED'), None)


def _recolour(mat, palette, gltf_dir):
    """base colour = fixed + primary * mask.r + accent * mask.g (+ filament * mask.b)"""
    r = _plain(mat.get('eidoverse_recolor'))
    nt = mat.node_tree
    bsdf = _bsdf(nt)
    if bsdf is None:
        return False

    def img(rel, colour):
        n = nt.nodes.new('ShaderNodeTexImage')
        n.image = kio.shared_image(os.path.normpath(os.path.join(gltf_dir, rel)), colour)
        n.extension = 'EXTEND'                       # io.js: ClampToEdgeWrapping
        return n
    fixed, mask = img(r['fixed'], True), img(r['mask'], False)
    fixed.label, mask.label = 'recolor fixed', 'recolor mask'
    old = bsdf.inputs['Base Color'].links[0].from_node if bsdf.inputs['Base Color'].is_linked else None
    if old is not None and old.type == 'TEX_IMAGE' and old.inputs['Vector'].is_linked:
        uv = old.inputs['Vector'].links[0].from_socket
        nt.links.new(uv, fixed.inputs['Vector'])
        nt.links.new(uv, mask.inputs['Vector'])
    g = nt.nodes.new('ShaderNodeGroup')
    g.node_tree = palette
    g.label = 'robot palette'
    sep = nt.nodes.new('ShaderNodeSeparateColor')
    nt.links.new(mask.outputs['Color'], sep.inputs['Color'])
    acc = fixed.outputs['Color']
    terms = [('primary', 'Red'), ('accent', 'Green')] + ([('filament', 'Blue')] if r.get('filament_channel') == 'b' else [])
    for key, ch in terms:
        mul = nt.nodes.new('ShaderNodeVectorMath')
        mul.operation = 'SCALE'
        nt.links.new(g.outputs[key], mul.inputs[0])
        nt.links.new(sep.outputs[ch], mul.inputs['Scale'])
        add = nt.nodes.new('ShaderNodeVectorMath')
        add.operation = 'ADD'
        nt.links.new(acc, add.inputs[0])
        nt.links.new(mul.outputs[0], add.inputs[1])
        acc = add.outputs[0]
    nt.links.new(acc, bsdf.inputs['Base Color'])
    return True


def _strip_textures(mat):
    """textures=False: three's 1x1 (220, 220, 220) stand-in for every map, so base colour 0.863 x the factor; the
    metallic-roughness and normal maps dropped (geometry-only inspection)"""
    nt = mat.node_tree
    bsdf = _bsdf(nt)
    for n in [n for n in nt.nodes if n.type == 'TEX_IMAGE']:
        nt.nodes.remove(n)
    if bsdf is None:
        return
    for name in ('Base Color', 'Roughness', 'Metallic', 'Normal', 'Emission Color', 'Alpha'):
        s = bsdf.inputs.get(name)
        if s is not None:
            for ln in list(s.links):
                nt.links.remove(ln)
    k = 220 / 255
    bc = bsdf.inputs['Base Color'].default_value
    bsdf.inputs['Base Color'].default_value = (bc[0] * k, bc[1] * k, bc[2] * k, 1.0)


def dedupe_images(materials):
    """every image node of these materials onto the session's one shared image per file and colour space (io.js's
    image cache): a second robot never loads or uploads the kit's maps again"""
    for mat in materials:
        if not mat.use_nodes:
            continue
        for n in mat.node_tree.nodes:
            if n.type != 'TEX_IMAGE' or n.image is None or n.image.source != 'FILE':
                continue
            n.extension = 'EXTEND'                       # io.js: every kit map ClampToEdgeWrapping
            old = n.image
            path = bpy.path.abspath(old.filepath)
            if not os.path.exists(path):
                continue
            shared = kio.shared_image(path, old.colorspace_settings.name == 'sRGB')
            if shared != old:
                n.image = shared
                if old.users == 0:
                    bpy.data.images.remove(old)


def prepare_materials(objects, gltf_dir, textures=True, color=None, primary=None, accent=None, filament=None,
                      name='robot'):
    mats = []
    seen = set()
    for o in objects:
        if o.type != 'MESH':
            continue
        for s in o.material_slots:
            m = s.material
            if m is not None and m.name not in seen:
                seen.add(m.name)
                mats.append(m)
    palette = _palette_group(f'robot_palette|{name}')
    rm = RobotMaterials(palette, mats)
    rm.set_filament(filament if filament is not None else DEFAULT_FILAMENT)
    initialized = False
    recoloured = 0
    if textures:
        dedupe_images(mats)
    for m in mats:
        if not m.use_nodes:
            continue
        r = m.get('eidoverse_recolor')
        if r is not None:
            r = _plain(r)
            if not initialized and 'default_primary_linear' in r:
                palette.nodes['primary'].outputs[0].default_value = tuple(r['default_primary_linear'][:3]) + (1.0,)
                palette.nodes['accent'].outputs[0].default_value = tuple(r['default_accent_linear'][:3]) + (1.0,)
                initialized = True
            if textures:
                recoloured += _recolour(m, palette, gltf_dir)
        if not textures:
            _strip_textures(m)
    rm.set_color(color if color is not None else primary, accent)
    rm.recoloured = recoloured
    return rm
