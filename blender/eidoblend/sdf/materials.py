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

What a bake cannot hold is the view: the engine's shade() saw the camera per pixel (fresnel rims, wrap lighting).
view_terms(b, s) is that part, per pixel, over the baked channels: a Python hook (as fx.iso_field's color_node is)
that builds shader nodes with the eidoblend.fx._nodes Builder `b` from the ViewInputs `s` (the normal, the direction
to the viewer, N.V, Layer Weight's fresnel and facing, the point, every baked channel) and returns
{Principled input name: value}. Each value replaces what fed that input:

    def rim(b, s):                                     # shade()'s pow(1 - N.V, 3) lavender rim, unlit, as the engine
        k = b.pow(1.0 - s.n_dot_v, 3.0) * 0.3
        return {'Emission Color': s.emission + b.combine(0.9 * k, 0.8 * k, 1.0 * k)}
    create_sdf_object(spec, view_terms=rim)
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


class ViewInputs:
    """What a view_terms hook reads, per pixel, as eidoblend.fx._nodes values on the material's node tree:

    position    the shading point, world                                                        Vec
    local       the point in the SDF's local frame, three's axes (y up): the engine's p          Vec
    normal      the shading normal, world: the atlas's normal map where there is one (the field's gradient, the
                engine's n), else the mesh's                                                     Vec
    incoming    the unit vector from the point toward the viewer, world                          Vec
    n_dot_v     max(0, normal . incoming): the engine's max(0, dot(n, normalize(cameraPosition - p)))   Expr
    fresnel, facing   Layer Weight's outputs on that normal (blend 0.5)                          Expr
    albedo, roughness, metallic, emission, sheen, sheen_tint, subsurface, coat, specular, transmission:
                the baked channels: what feeds each Principled input before the hook (the data, or its constant;
                RGB channels are Vec, the others Expr)
    """

    def __init__(self, b, bsdf):
        self._b, self._bsdf = b, bsdf
        self._cache = {}

    def _geo(self):
        if 'geo' not in self._cache:
            self._cache['geo'] = self._b.node('ShaderNodeNewGeometry')
        return self._cache['geo']

    @property
    def position(self):
        return self._b.vec(self._geo().outputs['Position'])

    @property
    def incoming(self):
        return self._b.vec(self._geo().outputs['Incoming'])

    @property
    def normal(self):
        if 'normal' not in self._cache:
            src = self._bsdf.inputs['Normal'].links[0].from_socket if self._bsdf.inputs['Normal'].is_linked else None
            self._cache['normal'] = self._b.vec(src if src is not None else self._geo().outputs['Normal'])
        return self._cache['normal']

    @property
    def local(self):
        if 'local' not in self._cache:
            x, y, z = self._b.vec(self._b.node('ShaderNodeTexCoord').outputs['Object']).xyz()
            self._cache['local'] = self._b.combine(x, z, -y)
        return self._cache['local']

    @property
    def n_dot_v(self):
        if 'ndv' not in self._cache:
            self._cache['ndv'] = self._b.max(self._b.vmath('DOT_PRODUCT', self.normal, self.incoming), 0.0)
        return self._cache['ndv']

    def _layer_weight(self):
        if 'lw' not in self._cache:
            lw = self._b.node('ShaderNodeLayerWeight')
            lw.inputs['Blend'].default_value = 0.5
            self._b.link(self.normal, lw.inputs['Normal'])
            self._cache['lw'] = lw
        return self._cache['lw']

    @property
    def fresnel(self):
        return self._b.s(self._layer_weight().outputs['Fresnel'])

    @property
    def facing(self):
        return self._b.s(self._layer_weight().outputs['Facing'])

    def __getattr__(self, name):
        ch = {c: (w, inp) for c, w, inp, _d in CHANNELS}
        if name.startswith('_') or name not in ch:
            raise AttributeError(name)
        if name not in self._cache:
            w, inp = ch[name]
            sock = self._bsdf.inputs[inp]
            b = self._b
            if sock.is_linked:
                src = sock.links[0].from_socket
                self._cache[name] = b.vec(src) if w == 3 else b.s(src)
            else:
                v = tuple(sock.default_value)[:3] if w == 3 else float(sock.default_value)
                self._cache[name] = b.combine(*v) if w == 3 else b.s(v)
        return self._cache[name]


def apply_view_terms(mat, view_terms):
    """Per-pixel, view-dependent terms over a solid's baked channels: view_terms(b, s) gets an eidoblend.fx._nodes
    Builder on mat's node tree and a ViewInputs s, and returns {Principled input name: value} (an RGB Vec or a 3- or
    4-tuple, a scalar Expr or a number). Each value replaces what fed that input; read the baked channel from s to
    keep it under the term. Returns the inputs it set."""
    from ..fx._nodes import Builder
    nt = mat.node_tree
    bsdf = _principled(nt)
    b = Builder(nt, x0=-2900, y0=-900)
    s = ViewInputs(b, bsdf)
    out = view_terms(b, s)
    if not isinstance(out, dict):
        raise TypeError(f'view_terms must return {{Principled input name: value}}, not {type(out).__name__}')
    for name in out:
        if name not in bsdf.inputs:
            raise ValueError(f'view_terms: the Principled BSDF has no input {name!r} (inputs: '
                             f'{", ".join(i.name for i in bsdf.inputs)})')
    for name, v in out.items():
        sock = bsdf.inputs[name]
        for lk in list(sock.links):
            nt.links.remove(lk)
        b.link(v, sock)
    mat['sdf_view_terms'] = sorted(out)
    return sorted(out)


def vertex_material(name, constants, settings=None, view_terms=None):
    """A material reading the sdf_* point attributes (constants become input defaults), then view_terms (if any)."""
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
    if view_terms is not None:
        apply_view_terms(mat, view_terms)
    return mat


def atlas_material(name, images, constants, settings=None, normal_image=None, uv_name='UVMap', view_terms=None):
    """A material reading packed atlas images {'base': img, 'emit': img, 'sheen': img, 'extra': img} through the UV
    map, plus an object-space normal map. Missing images mean their channels are constants. Then view_terms (if
    any)."""
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
    if view_terms is not None:
        apply_view_terms(mat, view_terms)
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
