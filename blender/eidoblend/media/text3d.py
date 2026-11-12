"""Extruded type as Blender text objects with real materials (text_3d.js, ported), and title cards.

    from eidoblend.media import text3d
    title = text3d.create_text_3d('EIDO', font='Audiowide', size=0.4, depth=0.04, bevel_size=0.004,
                                  bevel_thickness=0.004, material=text3d.material('enamel', color='#b6d8d5'))
    title.location = (0, 0, 0.25)                # stands up, reads from -Y (three's +Z-facing text, mapped)

Sizes are three.js TextGeometry's: ``size`` is the em, ``depth`` the extrusion before bevel, the bevel adds
``bevel_thickness`` front and back and grows the outline by ``bevel_size``. Blender's own size is the font's
(ascent - descent), so the conversion reads the TTF's hhea and head tables. The text is a FONT object (kerning,
bevel, resolution are Blender's), centred on its geometric box like three's ``geo.center()``.

    card = text3d.make_title_card('CLAUDE COMES HOME', camera, frames=(1, 72), fade=12, font='Michroma')

puts type in front of a camera (parented, so it holds frame), fading in and out through the material.
``reveal=(first_frame, chars_per_second)`` types a single line on, glyph by glyph.
"""
import struct
from functools import lru_cache
from pathlib import Path

import bpy
from mathutils import Vector

from . import raster
from .screens import new_material, set_interpolation


# ---------------------------------------------------------------------------------------------------- the font file
@lru_cache(maxsize=64)
def font_metrics(path):
    """units_per_em, the head table's y bounds, hhea ascender / descender / line gap and OS/2 cap height."""
    data = Path(path).read_bytes()
    n = struct.unpack('>H', data[4:6])[0]
    tables = {}
    for i in range(n):
        tag, _cs, off, ln = struct.unpack('>4sIII', data[12 + 16 * i: 28 + 16 * i])
        tables[tag.decode('latin-1')] = (off, ln)
    off = tables['head'][0]
    upem = struct.unpack('>H', data[off + 18: off + 20])[0]
    y_min, _x_max, y_max = struct.unpack('>hhh', data[off + 38: off + 44])
    off = tables['hhea'][0]
    asc, desc, gap = struct.unpack('>hhh', data[off + 4: off + 10])
    cap = None
    if 'OS/2' in tables:
        off, ln = tables['OS/2']
        ver = struct.unpack('>H', data[off: off + 2])[0]
        if ver >= 2 and ln >= 90:
            cap = struct.unpack('>h', data[off + 88: off + 90])[0]
    return {'units_per_em': upem, 'y_min': y_min, 'y_max': y_max, 'ascender': asc, 'descender': desc,
            'line_gap': gap, 'cap_height': cap}


def blender_size(em, font):
    """Blender text size for a three.js TextGeometry size (the em). Blender scales a font so its head-table
    bounding box (yMax - yMin) is one unit (vfontdata_freetype: scale = 1 / bbox height), measured on
    Audiowide, Michroma and Anton (hhea ascent - descent only matches where a font sets them equal)."""
    m = font_metrics(str(raster.font_path(font)))
    return em * (m['y_max'] - m['y_min']) / m['units_per_em']


def load_font(font):
    p = str(raster.font_path(font))
    for f in bpy.data.fonts:
        if bpy.path.abspath(f.filepath) == p:
            return f
    return bpy.data.fonts.load(p)


# ---------------------------------------------------------------------------------------------------- materials
PRESETS = {
    # name: Principled settings (colours sRGB hex; the material converts) - real surfaces, not flat colour
    'enamel': dict(color='#b6d8d5', metallic=0.0, roughness=0.28, coat=0.6, coat_roughness=0.08),
    'plastic': dict(color='#d8d4cc', metallic=0.0, roughness=0.42),
    'chrome': dict(color='#e8e8ea', metallic=1.0, roughness=0.06),
    'brushed': dict(color='#c9c9cc', metallic=1.0, roughness=0.32, grain=0.35),
    'gold': dict(color='#e6b85c', metallic=1.0, roughness=0.18),
    'copper': dict(color='#e09a72', metallic=1.0, roughness=0.24),
    'paper': dict(color='#efe8d8', metallic=0.0, roughness=0.85, sheen=0.3),
    'neon': dict(color='#ff2d95', metallic=0.0, roughness=0.15, emission=6.0, transmission=0.0),
}


def _lin(hexcol):
    r, g, b, _a = raster.color(hexcol)
    return tuple(float(raster.srgb_to_linear(c / 255.0)) for c in (r, g, b))


def material(preset='enamel', name=None, fade=False, **over):
    """A Principled material from a preset (``PRESETS``), with overrides: color, metallic, roughness, coat,
    coat_roughness, emission (strength, coloured by ``color`` or ``emission_color``), grain (a fine brushed /
    worn breakup on roughness and bump), sheen. ``fade``: a Transparent mix whose factor (the node 'fade',
    input 0 = clear, 1 = solid) a title keys."""
    p = dict(PRESETS[preset])
    p.update(over)
    m = new_material(name or f'type_{preset}')
    t = m.node_tree
    b = t.nodes.get('Principled BSDF') or t.nodes.new('ShaderNodeBsdfPrincipled')
    out = t.nodes.get('Material Output') or t.nodes.new('ShaderNodeOutputMaterial')
    b.inputs['Base Color'].default_value = (*_lin(p['color']), 1)
    b.inputs['Metallic'].default_value = p.get('metallic', 0.0)
    b.inputs['Roughness'].default_value = p.get('roughness', 0.4)
    if p.get('coat'):
        b.inputs['Coat Weight'].default_value = p['coat']
        b.inputs['Coat Roughness'].default_value = p.get('coat_roughness', 0.05)
    if p.get('sheen'):
        b.inputs['Sheen Weight'].default_value = p['sheen']
    if p.get('emission'):
        b.inputs['Emission Color'].default_value = (*_lin(p.get('emission_color', p['color'])), 1)
        b.inputs['Emission Strength'].default_value = p['emission']
    if p.get('grain'):
        # brushed metal: a noise stretched along the text's local X breaks up roughness and bumps the surface
        tc = t.nodes.new('ShaderNodeTexCoord')
        mp = t.nodes.new('ShaderNodeMapping')
        mp.inputs['Scale'].default_value = (4.0, 400.0, 400.0)
        nz = t.nodes.new('ShaderNodeTexNoise')
        nz.inputs['Scale'].default_value = 6.0
        nz.inputs['Detail'].default_value = 8.0
        t.links.new(tc.outputs['Object'], mp.inputs['Vector'])
        t.links.new(mp.outputs['Vector'], nz.inputs['Vector'])
        mr = t.nodes.new('ShaderNodeMapRange')
        mr.inputs['To Min'].default_value = max(0.0, p['roughness'] - p['grain'] * 0.4)
        mr.inputs['To Max'].default_value = min(1.0, p['roughness'] + p['grain'] * 0.4)
        t.links.new(nz.outputs['Fac'], mr.inputs['Value'])
        t.links.new(mr.outputs['Result'], b.inputs['Roughness'])
        bump = t.nodes.new('ShaderNodeBump')
        bump.inputs['Strength'].default_value = 0.08 * p['grain']
        t.links.new(nz.outputs['Fac'], bump.inputs['Height'])
        t.links.new(bump.outputs['Normal'], b.inputs['Normal'])
    if fade:
        tr = t.nodes.new('ShaderNodeBsdfTransparent')
        mix = t.nodes.new('ShaderNodeMixShader')
        mix.name = mix.label = 'fade'
        mix.inputs['Fac'].default_value = 1.0
        t.links.new(tr.outputs['BSDF'], mix.inputs[1])
        t.links.new(b.outputs['BSDF'], mix.inputs[2])
        t.links.new(mix.outputs['Shader'], out.inputs['Surface'])
        # blended, front surface only: solid type fading must not show its own back faces and bevels through
        # the front (measured: at fade 0.15 the layers summed to near full brightness)
        m.surface_render_method = 'BLENDED'
        m.use_transparency_overlap = False
        m.use_backface_culling = True
        m.use_transparent_shadow = True
    else:
        t.links.new(b.outputs['BSDF'], out.inputs['Surface'])
    return m


# ---------------------------------------------------------------------------------------------------- the type
def create_text_3d(text, font='Audiowide', size=1.0, depth=0.15, curve_segments=6, bevel=True,
                   bevel_thickness=0.02, bevel_size=0.015, bevel_segments=3, material=None, center=True,
                   name='text3d', align='CENTER', line_spacing=1.0, stand_up=True, scene=None, collection=None,
                   reveal=None):
    """A FONT object with three's TextGeometry measures (see the module doc). ``align``: LEFT / CENTER / RIGHT
    for multi-line text. ``stand_up``: rotate it upright, facing -Y (else it lies in the XY plane facing +Z).
    ``reveal=(first_frame, chars_per_second)`` types it on (single line), glyph by glyph."""
    scene = scene or bpy.context.scene
    cu = bpy.data.curves.new(name, 'FONT')
    cu.body = text
    cu.font = load_font(font)
    cu.size = blender_size(size, font)
    cu.align_x = align
    cu.align_y = 'TOP_BASELINE'
    cu.space_line = line_spacing
    cu.resolution_u = max(1, int(curve_segments))
    cu.render_resolution_u = 0
    bt = bevel_thickness if bevel else 0.0
    bs = bevel_size if bevel else 0.0
    # Blender extrudes both ways and its round bevel adds bevel_depth to the outline and to each face:
    # three's full depth (depth + 2 bevel_thickness) is kept, the outline grows by bevel_size
    cu.bevel_depth = bs
    cu.bevel_resolution = max(0, int(bevel_segments) - 1) if bevel else 0
    cu.extrude = max(0.0, depth / 2 + bt - bs)
    cu.fill_mode = 'BOTH'
    obj = bpy.data.objects.new(name, cu)
    (collection or scene.collection).objects.link(obj)
    if material is not None:
        cu.materials.append(material)
    if center:
        bpy.context.view_layer.update()
        c = _ink_box(obj)
        cu.offset_x -= (c[0][0] + c[1][0]) / 2
        cu.offset_y -= (c[0][1] + c[1][1]) / 2
    if stand_up:
        obj.rotation_euler = (1.5707963267948966, 0.0, 0.0)
    if reveal:
        _typewriter(obj, text, *reveal, scene=scene)
    return obj


def _ink_box(obj):
    """Local (min, max) corners of the text's whole geometry (a typewriter reveal is switched off to measure)."""
    hidden = [m for m in obj.modifiers if m.type == 'NODES' and m.show_viewport]
    for m in hidden:
        m.show_viewport = False
    try:
        bpy.context.view_layer.update()
        dg = bpy.context.evaluated_depsgraph_get()
        ev = obj.evaluated_get(dg)
        me = ev.to_mesh()
        try:
            if me is None or not len(me.vertices):
                return Vector((0, 0, 0)), Vector((0, 0, 0))
            xs = [v.co.x for v in me.vertices]
            ys = [v.co.y for v in me.vertices]
            zs = [v.co.z for v in me.vertices]
            return Vector((min(xs), min(ys), min(zs))), Vector((max(xs), max(ys), max(zs)))
        finally:
            ev.to_mesh_clear()
    finally:
        for m in hidden:
            m.show_viewport = True


def ink_size(obj):
    """Width, height, depth of the type's geometry in its own (unrotated) frame."""
    a, b = _ink_box(obj)
    return tuple(b - a)


def _reveal_group():
    g = bpy.data.node_groups.get('eido_type_reveal')
    if g:
        return g
    g = bpy.data.node_groups.new('eido_type_reveal', 'GeometryNodeTree')
    g.interface.new_socket('Geometry', in_out='INPUT', socket_type='NodeSocketGeometry')
    s = g.interface.new_socket('Reveal X', in_out='INPUT', socket_type='NodeSocketFloat')
    s.default_value = 1e6
    g.interface.new_socket('Geometry', in_out='OUTPUT', socket_type='NodeSocketGeometry')
    n = g.nodes
    gi, go = n.new('NodeGroupInput'), n.new('NodeGroupOutput')
    pos = n.new('GeometryNodeInputPosition')
    sep = n.new('ShaderNodeSeparateXYZ')
    cmp_ = n.new('FunctionNodeCompare')
    cmp_.data_type, cmp_.operation = 'FLOAT', 'GREATER_THAN'
    dele = n.new('GeometryNodeDeleteGeometry')
    dele.domain = 'FACE'
    g.links.new(pos.outputs['Position'], sep.inputs['Vector'])
    g.links.new(sep.outputs['X'], cmp_.inputs['A'])
    g.links.new(gi.outputs['Reveal X'], cmp_.inputs['B'])
    g.links.new(gi.outputs['Geometry'], dele.inputs['Geometry'])
    g.links.new(cmp_.outputs['Result'], dele.inputs['Selection'])
    g.links.new(dele.outputs['Geometry'], go.inputs['Geometry'])
    return g


def _typewriter(obj, text, first_frame, cps, scene):
    """Faces right of a keyed X are deleted (a Geometry Nodes modifier); the X steps glyph by glyph, at the right
    edge of each prefix's ink, so a glyph appears whole."""
    from .timebase import Timebase
    tb = Timebase.of(scene)
    cu = obj.data
    edges = []
    probe = obj.copy()
    probe.data = cu.copy()
    scene.collection.objects.link(probe)
    try:
        for k in range(len(text) + 1):
            probe.data.body = text[:k] if k else ' '
            bpy.context.view_layer.update()
            a, b = _ink_box(probe)
            edges.append(b.x if k and text[:k].strip() else -1e6)
    finally:
        d = probe.data
        bpy.data.objects.remove(probe)
        bpy.data.curves.remove(d)
    mod = obj.modifiers.new('reveal', 'NODES')
    mod.node_group = _reveal_group()
    key = next(s.identifier for s in mod.node_group.interface.items_tree
               if getattr(s, 'in_out', None) == 'INPUT' and s.name == 'Reveal X')
    item = getattr(mod.properties.inputs, key)     # 5.x: modifier inputs are mod.properties.inputs.<id>.value
    last = None
    for k in range(len(text) + 1):
        f = int(round(tb.frame(tb.t(first_frame) + k / cps)))
        x = edges[k] + 1e-4 if edges[k] > -1e5 else -1e6
        if x == last:
            continue
        item.value = x
        item.keyframe_insert('value', frame=f)
        last = x
    set_interpolation(obj, 'CONSTANT', 'modifiers["reveal"]')
    return mod


# ---------------------------------------------------------------------------------------------------- title cards
def make_title_card(text, camera, frames, fade=12, font='Michroma', height_frac=0.08, y=0.0, distance=1.0,
                    preset='enamel', mat=None, depth_frac=0.12, bevel_frac=0.04, name='title', **mat_over):
    """Type in front of ``camera`` (parented, so it holds its place in frame) visible over ``frames`` = (first,
    last), fading in and out over ``fade`` frames through its material. ``height_frac``: the cap height as a
    fraction of the frame height; ``y``: its centre, -0.5 (bottom) .. 0.5 (top) of the frame. The default is
    an emissive-free enamel lit by the scene; pass preset='neon' (or emission=...) for a title that glows."""
    scene = bpy.context.scene
    cam = camera.data
    import math
    if cam.sensor_fit == 'VERTICAL':
        half_h = math.tan(cam.angle_y / 2) * distance
    else:
        r = scene.render
        aspect = (r.resolution_y * r.pixel_aspect_y) / (r.resolution_x * r.pixel_aspect_x)
        half_h = math.tan(cam.angle_x / 2) * distance * aspect
    m = font_metrics(str(raster.font_path(font)))
    cap = (m['cap_height'] or 0.7 * m['units_per_em']) / m['units_per_em']
    em = 2 * half_h * height_frac / cap
    material_ = mat or material(preset, name=f'{name}_mat', fade=True, **mat_over)
    obj = create_text_3d(text, font=font, size=em, depth=em * depth_frac, bevel_size=em * bevel_frac,
                         bevel_thickness=em * bevel_frac, material=material_, name=name, stand_up=False)
    obj.parent = camera
    obj.location = (0.0, y * 2 * half_h, -distance)
    obj.rotation_euler = (0.0, 0.0, 0.0)
    a, b = frames
    fade_node = material_.node_tree.nodes.get('fade')
    if fade_node is not None:
        s = fade_node.inputs['Fac']
        for f, v in ((a - 1, 0.0), (a, 0.0), (a + fade, 1.0), (b - fade, 1.0), (b, 0.0)):
            s.default_value = v
            s.keyframe_insert('default_value', frame=f)
        set_interpolation(material_.node_tree, 'LINEAR', 'nodes["fade"]')
    return obj
