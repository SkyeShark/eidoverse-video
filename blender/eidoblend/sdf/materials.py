"""The Principled material an SDF solid renders with: its surface() channels, baked per vertex or per texel.

The engine's shade() returned a lit colour from hand-placed lights. The Blender edition keeps what shade() knew about
the surface (albedo, roughness, metal, emissive parts, rim and wrap terms) and lets EEVEE light it: surface(p, n,
mat) returns an SdfSurface record, baked to one of two carriers:

  'vertex'  point attributes on the mesh (sdf_albedo, sdf_roughness, ...), read by Attribute nodes. Material detail
            is the mesh's vertex spacing (the voxel). What the animated PLY sequences carry.
  'atlas'   a texel block per quad in packed EXR atlases read through the mesh's UVMap, plus an object-space normal
            map from the field's gradient: material and relief detail several times finer than the mesh, as the
            engine's per-pixel shade() had. The default for static solids.

Channels whose value is the same everywhere are not stored: the BSDF input gets the constant.
"""

from __future__ import annotations

import numpy as np

# channel name -> (width, Principled input, default)
CHANNELS = [
    ('albedo', 3, 'Base Color', (0.8, 0.8, 0.8)),
    ('roughness', 1, 'Roughness', 0.5),
    ('metallic', 1, 'Metallic', 0.0),
    ('emission', 3, 'Emission Color', (0.0, 0.0, 0.0)),
    ('sheen', 1, 'Sheen Weight', 0.0),
    ('sheen_tint', 3, 'Sheen Tint', (1.0, 1.0, 1.0)),
    ('subsurface', 1, 'Subsurface Weight', 0.0),
    ('coat', 1, 'Coat Weight', 0.0),
    ('specular', 1, 'Specular IOR Level', 0.5),
    ('transmission', 1, 'Transmission Weight', 0.0),
]

# atlas images: four channels each (the surface kernel's targets 0..3), + the normal map
ATLAS_PACK = {
    'base': [('albedo', 3), ('roughness', 1)],
    'emit': [('emission', 3), ('metallic', 1)],
    'sheen': [('sheen_tint', 3), ('sheen', 1)],
    'extra': [('subsurface', 1), ('coat', 1), ('specular', 1), ('transmission', 1)],
}

DEFAULT_SETTINGS = {
    'subsurface_radius': (1.0, 0.2, 0.1),
    'subsurface_scale': 0.05,
    'ior': 1.5,
    'coat_roughness': 0.03,
    'sheen_roughness': 0.5,
    'emission_strength': 1.0,
    'normal_strength': 1.0,
    'interpolation': 'Linear',
}


def constant_channels(ch, eps=1e-5):
    """{name: constant value} for channels that do not vary (stored as BSDF defaults instead of data)."""
    out = {}
    for name, width, _inp, _d in CHANNELS:
        a = np.asarray(ch[name], np.float32).reshape(len(ch[name]), -1)
        if len(a) == 0:
            continue
        if float(np.max(a.max(axis=0) - a.min(axis=0))) < eps:
            v = a[0]
            out[name] = float(v[0]) if width == 1 else tuple(float(x) for x in v)
    return out


def _principled(nt):
    for n in nt.nodes:
        if n.type == 'BSDF_PRINCIPLED':
            return n
    return nt.nodes.new('ShaderNodeBsdfPrincipled')


def _apply_settings(bsdf, s):
    bsdf.inputs['Subsurface Radius'].default_value = tuple(s['subsurface_radius'])
    bsdf.inputs['Subsurface Scale'].default_value = s['subsurface_scale']
    bsdf.inputs['IOR'].default_value = s['ior']
    bsdf.inputs['Coat Roughness'].default_value = s['coat_roughness']
    bsdf.inputs['Sheen Roughness'].default_value = s['sheen_roughness']
    bsdf.inputs['Emission Strength'].default_value = s['emission_strength']


def _set_default(bsdf, inp, v):
    sock = bsdf.inputs[inp]
    if isinstance(v, tuple):
        sock.default_value = (*v, 1.0) if len(sock.default_value) == 4 else v
    else:
        sock.default_value = v


def vertex_material(name, constants, settings=None):
    """A material reading the sdf_* point attributes (constants become input defaults)."""
    import bpy
    s = dict(DEFAULT_SETTINGS, **(settings or {}))
    mat = bpy.data.materials.new(name)
    mat.use_nodes = True
    nt = mat.node_tree
    bsdf = _principled(nt)
    _apply_settings(bsdf, s)
    y = 300
    for cname, width, inp, default in CHANNELS:
        if cname in constants:
            _set_default(bsdf, inp, constants[cname])
            continue
        at = nt.nodes.new('ShaderNodeAttribute')
        at.attribute_type = 'GEOMETRY'
        at.attribute_name = 'sdf_' + cname
        at.location = (-500, y)
        y -= 170
        nt.links.new(at.outputs['Color' if width == 3 else 'Fac'], bsdf.inputs[inp])
    mat['sdf_carrier'] = 'vertex'
    return mat


def atlas_material(name, images, constants, settings=None, normal_image=None, uv_name='UVMap'):
    """A material reading packed atlas images {'base': img, 'emit': img, 'sheen': img, 'extra': img} through the UV
    map, plus an object-space normal map. Missing images mean their channels are constants."""
    import bpy
    s = dict(DEFAULT_SETTINGS, **(settings or {}))
    mat = bpy.data.materials.new(name)
    mat.use_nodes = True
    nt = mat.node_tree
    bsdf = _principled(nt)
    _apply_settings(bsdf, s)
    uv = nt.nodes.new('ShaderNodeUVMap')
    uv.uv_map = uv_name
    uv.location = (-1300, 0)
    y = 400
    for key, layout in ATLAS_PACK.items():
        img = images.get(key)
        names = [c for c, _w in layout]
        if img is None:
            for c in names:
                if c in constants:
                    _set_default(bsdf, dict((n, i) for n, _w, i, _d in CHANNELS)[c], constants[c])
            continue
        tex = nt.nodes.new('ShaderNodeTexImage')
        tex.image = img
        tex.interpolation = s['interpolation']
        tex.extension = 'EXTEND'
        tex.location = (-1000, y)
        nt.links.new(uv.outputs['UV'], tex.inputs['Vector'])
        sep = nt.nodes.new('ShaderNodeSeparateColor')
        sep.location = (-700, y)
        nt.links.new(tex.outputs['Color'], sep.inputs['Color'])
        y -= 320
        comp = 0
        for c, w in layout:
            inp = dict((n, i) for n, _w, i, _d in CHANNELS)[c]
            if c in constants:
                _set_default(bsdf, inp, constants[c])
                comp += w
                continue
            if w == 3:
                nt.links.new(tex.outputs['Color'], bsdf.inputs[inp])
            else:
                src = tex.outputs['Alpha'] if comp == 3 else sep.outputs[comp]      # Red / Green / Blue in 5.x
                nt.links.new(src, bsdf.inputs[inp])
            comp += w
    if normal_image is not None:
        tex = nt.nodes.new('ShaderNodeTexImage')
        tex.image = normal_image
        tex.interpolation = s['interpolation']
        tex.extension = 'EXTEND'
        tex.location = (-1000, y)
        nt.links.new(uv.outputs['UV'], tex.inputs['Vector'])
        nm = nt.nodes.new('ShaderNodeNormalMap')
        nm.space = 'OBJECT'
        nm.inputs['Strength'].default_value = s['normal_strength']
        nm.location = (-500, y)
        nt.links.new(tex.outputs['Color'], nm.inputs['Color'])
        nt.links.new(nm.outputs['Normal'], bsdf.inputs['Normal'])
    mat['sdf_carrier'] = 'atlas'
    return mat


def load_atlas_image(path, name, alpha_packed=True, sequence=None):
    """An atlas EXR as a Non-Color bpy image (alpha as its own channel). sequence = (frame_start, count)."""
    import bpy
    img = bpy.data.images.load(path, check_existing=False)
    img.name = name
    img.colorspace_settings.name = 'Non-Color'
    img.alpha_mode = 'CHANNEL_PACKED' if alpha_packed else 'STRAIGHT'
    if sequence is not None:
        img.source = 'SEQUENCE'
    return img
