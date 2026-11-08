"""Node trees for create_flora (Blender 5.2): the field's geometry nodes (instancing, 3-layer wind, pushers, the
daisy head fix), the daisy close group, the gust-envelope image and the leaf / bark materials.

The wind and the pushers are the WebGPU edition's vertex-stage maths (vegetation.js positionNode), evaluated per
vertex in geometry nodes on the realized field from Scene Time. Real geometry, so EEVEE's Vector pass, motion blur
and shadows all see the motion, and nothing needs a frame handler or Python at render time.
"""
import bpy
import numpy as np

GROUP_FIELD = 'EB Flora Field'
GROUP_CLOSE = 'EB Flora Daisy Close'
GUST_IMAGE = 'eb_flora_gust'
PUSH_SLOTS = 6          # pushers read per field (the WebGPU edition had 4 uniform slots)
NODES_VERSION = 4
# translucency: transmitted colour = albedo x min(1, map x sss x 2.2 x gain), the map read raw (Non-Color) as a
# thinness mask. The WebGPU edition's 2.2 x sss scaled a Barre-Brisebois lobe; the gain re-levels it for EEVEE's
# Translucent BSDF (calibrated by eye on backlit probes, tests/flora/t_lookdev.py)
TRANSL_GAIN = 4.0
# energy (verifier, 11-07): the Translucent lobe is added on top of the full Principled diffuse, so a bright sheet
# (white daisy rays, albedo ~0.88, map x gain clamped to 1) reflects ~0.88 AND transmits ~0.88. 'normalize' scales
# reflection and transmission together (one factor from the brightest channel, so the hue holds) whenever their sum
# would pass 0.95; darker sheets (grass, leaves: a + T well under 0.95) are untouched. Default None, the by-eye
# calibration: in the A/B (tests/flora/t_backlit.py) normalized backlit white rays read as grey paper against the
# grass and backlit sunflower petals went brown, while the add reads as backlit petals and never ran hot.
# Set eidoblend.flora.nodes.TRANSL_ENERGY = 'normalize' before building strokes for the strict budget.
TRANSL_ENERGY = None
SPEC_FACING = True       # fade the specular where the shading normal faces away from the camera (leaf_material,
                         # A/B in tests/flora/t_backlit.py)


class NB:
    """A tiny node-graph writer: math helpers take sockets or constants and return output sockets."""

    def __init__(self, tree):
        self.t = tree
        self.n = 0

    def node(self, kind, **props):
        nd = self.t.nodes.new(kind)
        for k, v in props.items():
            setattr(nd, k, v)
        nd.location = ((self.n // 14) * 220, -(self.n % 14) * 160)
        self.n += 1
        return nd

    def put(self, sock, v):
        if isinstance(v, bpy.types.NodeSocket):
            self.t.links.new(v, sock)
        elif v is not None:
            sock.default_value = v

    def math(self, op, a, b=None, c=None):
        nd = self.node('ShaderNodeMath', operation=op)
        self.put(nd.inputs[0], a)
        if b is not None:
            self.put(nd.inputs[1], b)
        if c is not None:
            self.put(nd.inputs[2], c)
        return nd.outputs[0]

    def vmath(self, op, a, b=None, scale=None, out=0, c=None):
        nd = self.node('ShaderNodeVectorMath', operation=op)
        self.put(nd.inputs[0], a)
        if b is not None:
            self.put(nd.inputs[1], b)
        if c is not None:
            self.put(nd.inputs[2], c)
        if scale is not None:
            self.put(nd.inputs[3], scale)
        return nd.outputs[out]

    def length(self, v):
        return self.vmath('LENGTH', v, out=1)

    def dot(self, a, b):
        return self.vmath('DOT_PRODUCT', a, b, out=1)

    def scale(self, v, s):
        return self.vmath('SCALE', v, scale=s)

    def combine(self, x=0.0, y=0.0, z=0.0):
        nd = self.node('ShaderNodeCombineXYZ')
        for i, v in enumerate((x, y, z)):
            self.put(nd.inputs[i], v)
        return nd.outputs[0]

    def separate(self, v):
        nd = self.node('ShaderNodeSeparateXYZ')
        self.put(nd.inputs[0], v)
        return nd.outputs

    def smoothstep(self, lo, hi, v):
        nd = self.node('ShaderNodeMapRange', interpolation_type='SMOOTHSTEP')
        self.put(nd.inputs['Value'], v)
        self.put(nd.inputs['From Min'], lo)
        self.put(nd.inputs['From Max'], hi)
        return nd.outputs['Result']

    def mix_vec(self, fac, a, b):
        """Mix node, vector mode (its sockets share names, so by index: 0 float factor, 4/5 vector A/B, out 1)."""
        nd = self.node('ShaderNodeMix', data_type='VECTOR')
        self.put(nd.inputs[0], fac)
        self.put(nd.inputs[4], a)
        self.put(nd.inputs[5], b)
        return nd.outputs[1]

    def attr(self, name, data_type='FLOAT'):
        nd = self.node('GeometryNodeInputNamedAttribute', data_type=data_type)
        nd.inputs['Name'].default_value = name
        return nd.outputs['Attribute']


def gust_image():
    """The shared gust-envelope texture, generated in Python (vegetation.js gustTex, identical values), packed into
    the .blend so a saved film renders anywhere."""
    im = bpy.data.images.get(GUST_IMAGE)
    if im is not None:
        return im
    from .vegetation import gust_pixels
    n = 256
    px = gust_pixels(n).astype(np.float32) / 255.0
    im = bpy.data.images.new(GUST_IMAGE, n, n, alpha=False, float_buffer=True)
    im.colorspace_settings.name = 'Non-Color'
    rgba = np.ones((n, n, 4), np.float32)
    rgba[..., 0] = rgba[..., 1] = rgba[..., 2] = px
    im.pixels.foreach_set(rgba.ravel())
    im.pack()
    return im


def _socket(tree, name, kind, in_out='INPUT', default=None, lo=None, hi=None):
    s = tree.interface.new_socket(name, in_out=in_out, socket_type=kind)
    if default is not None:
        s.default_value = default
    if lo is not None:
        s.min_value = lo
    if hi is not None:
        s.max_value = hi
    return s


def field_group():
    """The shared field group: points (one per plant, carrying flora_xform, root, color_var, phase, head_fix) ->
    instance the prototype -> realize -> wind + pushers + daisy head fix as one Set Position offset."""
    g = bpy.data.node_groups.get(GROUP_FIELD)
    if g is not None and g.get('eb_version') == NODES_VERSION:
        return g
    if g is not None:
        g.name = GROUP_FIELD + ' (old)'
    g = bpy.data.node_groups.new(GROUP_FIELD, 'GeometryNodeTree')
    g['eb_version'] = NODES_VERSION
    _socket(g, 'Geometry', 'NodeSocketGeometry')
    _socket(g, 'Geometry', 'NodeSocketGeometry', 'OUTPUT')
    _socket(g, 'Prototype', 'NodeSocketObject')
    _socket(g, 'Variants', 'NodeSocketCollection')
    _socket(g, 'Pick Variant', 'NodeSocketBool', default=False)
    _socket(g, 'Pushers', 'NodeSocketCollection')
    _socket(g, 'Wind Dir', 'NodeSocketVector', default=(1.0, -0.3, 0.0))
    _socket(g, 'Sway', 'NodeSocketFloat', default=0.35, lo=0.0)
    _socket(g, 'Gust', 'NodeSocketFloat', default=0.7, lo=0.0)
    _socket(g, 'Gust Freq', 'NodeSocketFloat', default=0.3, lo=0.0)
    _socket(g, 'Flutter', 'NodeSocketFloat', default=0.05, lo=0.0)
    _socket(g, 'Push Scale', 'NodeSocketFloat', default=1.0, lo=0.0)
    _socket(g, 'Time Offset', 'NodeSocketFloat', default=0.0)
    _socket(g, 'Keep Length', 'NodeSocketBool', default=True)
    b = NB(g)
    gi = b.node('NodeGroupInput')
    go = b.node('NodeGroupOutput')
    I = gi.outputs

    # instancing: the prototype's evaluated geometry (its own modifiers, e.g. the daisy close, already applied) on
    # every point, then each instance's full transform from the per-point matrix
    oi = b.node('GeometryNodeObjectInfo', transform_space='ORIGINAL')
    b.put(oi.inputs['Object'], I['Prototype'])
    # scanned plants (Poly Haven): several variant meshes in a collection, one picked per plant by its 'variant'
    vc = b.node('GeometryNodeCollectionInfo', transform_space='ORIGINAL')
    b.put(vc.inputs['Collection'], I['Variants'])
    vc.inputs['Separate Children'].default_value = True
    vc.inputs['Reset Children'].default_value = True
    sw = b.node('GeometryNodeSwitch', input_type='GEOMETRY')
    b.put(sw.inputs['Switch'], I['Pick Variant'])
    b.put(sw.inputs['False'], oi.outputs['Geometry'])
    b.put(sw.inputs['True'], vc.outputs[0])
    iop = b.node('GeometryNodeInstanceOnPoints')
    b.put(iop.inputs['Points'], I['Geometry'])
    b.put(iop.inputs['Instance'], sw.outputs[0])
    b.put(iop.inputs['Pick Instance'], I['Pick Variant'])
    b.put(iop.inputs['Instance Index'], b.attr('variant', 'INT'))
    sit = b.node('GeometryNodeSetInstanceTransform')
    b.put(sit.inputs['Instances'], iop.outputs[0])
    b.put(sit.inputs['Transform'], b.attr('flora_xform', 'FLOAT4X4'))
    rm = b.node('GeometryNodeRemoveAttribute')           # the matrix must not ride onto every realized vertex
    b.put(rm.inputs['Geometry'], sit.outputs[0])
    rm.inputs['Name'].default_value = 'flora_xform'
    real = b.node('GeometryNodeRealizeInstances')
    b.put(real.inputs['Geometry'], rm.outputs[0])

    # ── wind: three layers x aH^2, horizontal only (vegetation.js positionNode) ──
    P = b.node('GeometryNodeInputPosition').outputs[0]
    wdx, wdy, _ = b.separate(I['Wind Dir'])
    wd = b.vmath('NORMALIZE', b.combine(wdx, wdy, 0.0))
    t = b.math('ADD', b.node('GeometryNodeInputSceneTime').outputs['Seconds'], I['Time Offset'])
    dw = b.dot(P, wd)
    # layer 1: global sway
    g_sway = b.scale(wd, b.math('MULTIPLY', b.math('SINE', b.math('MULTIPLY_ADD', dw, 0.5, b.math('MULTIPLY', t, 1.2))), I['Sway']))
    # layer 2: gust fronts rolled by the noise envelope; three's texture coordinate (x, z) is Blender's (x, -y)
    px, py, _ = b.separate(P)
    tg = b.math('MULTIPLY', t, 0.3 / 8)
    guv = b.combine(b.math('MULTIPLY_ADD', px, 0.02, tg), b.math('MULTIPLY_ADD', py, -0.02, tg), 0.0)
    tex = b.node('GeometryNodeImageTexture', interpolation='Linear', extension='REPEAT')
    tex.inputs['Image'].default_value = gust_image()
    b.put(tex.inputs['Vector'], guv)
    env = b.smoothstep(0.3, 0.7, tex.outputs['Color'])
    gust_ph = b.math('MULTIPLY_ADD', dw, I['Gust Freq'], b.math('MULTIPLY', t, 2.5))
    g_gust = b.scale(wd, b.math('MULTIPLY', b.math('MULTIPLY', b.math('SINE', gust_ph), I['Gust']), env))
    # layer 3: per-instance flutter; three's (sin, cos) on (x, z) is Blender's (sin, -cos) on (x, y)
    tph = b.math('MULTIPLY_ADD', t, 3.0, b.attr('phase'))
    fl = b.math('MULTIPLY', I['Flutter'], 0.1)
    turb = b.combine(b.math('MULTIPLY', b.math('SINE', tph), fl),
                     b.math('MULTIPLY', b.math('COSINE', b.math('MULTIPLY', tph, 0.7)), b.math('MULTIPLY', fl, -1.0)), 0.0)
    aH = b.attr('aH')
    h2 = b.math('MULTIPLY', aH, aH)
    wind = b.scale(b.vmath('ADD', b.vmath('ADD', g_sway, g_gust), turb), h2)

    # ── pushers: each object of the Pushers collection is a pusher at its world location, radius = its world X
    # scale. Direction and the root distance are per plant (its root), strength falls off from the closer of root
    # and vertex (so a long leaf whose root is out of reach still yields), squared, with a soft tanh ceiling ──
    ci = b.node('GeometryNodeCollectionInfo', transform_space='RELATIVE')
    b.put(ci.inputs['Collection'], I['Pushers'])
    ci.inputs['Separate Children'].default_value = True
    ci.inputs['Reset Children'].default_value = False
    itp = b.node('GeometryNodeInstancesToPoints')
    b.put(itp.inputs['Instances'], ci.outputs[0])
    b.put(itp.inputs['Radius'], b.separate(b.node('GeometryNodeInputInstanceScale').outputs[0])[0])
    pts = itp.outputs[0]
    root = b.attr('root', 'FLOAT_VECTOR')
    flat = (1.0, 1.0, 0.0)
    push = None
    for i in range(PUSH_SLOTS):
        sp = b.node('GeometryNodeSampleIndex', data_type='FLOAT_VECTOR', domain='POINT')
        sp.clamp = False
        b.put(sp.inputs['Geometry'], pts)
        b.put(sp.inputs['Value'], b.node('GeometryNodeInputPosition').outputs[0])
        sp.inputs['Index'].default_value = i
        sr = b.node('GeometryNodeSampleIndex', data_type='FLOAT', domain='POINT')
        sr.clamp = False
        b.put(sr.inputs['Geometry'], pts)
        b.put(sr.inputs['Value'], b.node('GeometryNodeInputRadius').outputs[0])
        sr.inputs['Index'].default_value = i
        Pi, ri = sp.outputs[0], sr.outputs[0]
        delta = b.vmath('MULTIPLY', b.vmath('SUBTRACT', root, Pi), flat)
        d_true = b.length(delta)
        d = b.math('MAXIMUM', d_true, 0.3)
        v_dist = b.length(b.vmath('MULTIPLY', b.vmath('SUBTRACT', P, Pi), flat))
        s = b.math('SUBTRACT', 1.0, b.smoothstep(0.0, b.math('MAXIMUM', ri, 0.001), b.math('MINIMUM', d_true, v_dist)))
        live = b.math('GREATER_THAN', ri, 0.000999)
        k = b.math('MULTIPLY', b.math('MULTIPLY', b.math('MULTIPLY', s, s), b.math('MULTIPLY', I['Push Scale'], 1.35)), live)
        c = b.scale(delta, b.math('DIVIDE', k, d))
        push = c if push is None else b.vmath('ADD', push, c)
    p_len = b.math('MAXIMUM', b.length(push), 1e-4)
    capped = b.scale(push, b.math('DIVIDE', b.math('MULTIPLY', b.math('TANH', b.math('DIVIDE', p_len, 0.6)), 0.6), p_len))
    push_h = b.math('MULTIPLY_ADD', aH, 0.7, 0.3)
    disp = b.vmath('ADD', wind, b.scale(capped, push_h))
    # Keep Length (Blender edition, default on): the WebGPU edition moves vertices sideways only, so a gust shears a
    # blade and stretches it. Keep its apparent lean (the sheared vertex's direction from the root plane) but pull
    # it back to its own height hv above the root: k = hv / sqrt(hv^2 + d^2), sideways d*k, down hv*(1 - k)
    hv = b.math('MAXIMUM', b.math('SUBTRACT', b.separate(P)[2], b.separate(root)[2]), 0.02)
    dl = b.length(disp)
    k = b.math('DIVIDE', hv, b.math('SQRT', b.math('MULTIPLY_ADD', hv, hv, b.math('MULTIPLY', dl, dl))))
    drop = b.math('MULTIPLY', hv, b.math('SUBTRACT', 1.0, k))
    arc = b.vmath('ADD', b.scale(disp, k), b.combine(0.0, 0.0, b.math('MULTIPLY', drop, -1.0)))
    ksw = b.node('GeometryNodeSwitch', input_type='VECTOR')
    b.put(ksw.inputs['Switch'], I['Keep Length'])
    b.put(ksw.inputs['False'], disp)
    b.put(ksw.inputs['True'], arc)
    disp = ksw.outputs[0]
    # daisy heads keep their round shape under the instance's non-uniform scale (0 on every other species)
    head = b.scale(b.attr('head_fix', 'FLOAT_VECTOR'), b.attr('head_dz'))
    setp = b.node('GeometryNodeSetPosition')
    b.put(setp.inputs['Geometry'], real.outputs[0])
    b.put(setp.inputs['Offset'], b.vmath('ADD', disp, head))
    b.put(go.inputs[0], setp.outputs[0])
    return g


GROUP_STATIC = 'EB Flora Static'


def static_group():
    """A still stroke (create_flora(..., motion=False)): the same instancing, no realize, no wind, no pushers, no
    Scene Time, so EEVEE treats the stroke as static instanced geometry. For the far strokes of a big stand: EEVEE's
    velocity buffer for deforming geometry runs out somewhere between 10 and 39 M realized vertices (t_scale.py)."""
    g = bpy.data.node_groups.get(GROUP_STATIC)
    if g is not None and g.get('eb_version') == NODES_VERSION:
        return g
    if g is not None:
        g.name = GROUP_STATIC + ' (old)'
    g = bpy.data.node_groups.new(GROUP_STATIC, 'GeometryNodeTree')
    g['eb_version'] = NODES_VERSION
    _socket(g, 'Geometry', 'NodeSocketGeometry')
    _socket(g, 'Geometry', 'NodeSocketGeometry', 'OUTPUT')
    _socket(g, 'Prototype', 'NodeSocketObject')
    _socket(g, 'Variants', 'NodeSocketCollection')
    _socket(g, 'Pick Variant', 'NodeSocketBool', default=False)
    b = NB(g)
    gi, go = b.node('NodeGroupInput'), b.node('NodeGroupOutput')
    I = gi.outputs
    oi = b.node('GeometryNodeObjectInfo', transform_space='ORIGINAL')
    b.put(oi.inputs['Object'], I['Prototype'])
    vc = b.node('GeometryNodeCollectionInfo', transform_space='ORIGINAL')
    b.put(vc.inputs['Collection'], I['Variants'])
    vc.inputs['Separate Children'].default_value = True
    vc.inputs['Reset Children'].default_value = True
    sw = b.node('GeometryNodeSwitch', input_type='GEOMETRY')
    b.put(sw.inputs['Switch'], I['Pick Variant'])
    b.put(sw.inputs['False'], oi.outputs['Geometry'])
    b.put(sw.inputs['True'], vc.outputs[0])
    iop = b.node('GeometryNodeInstanceOnPoints')
    b.put(iop.inputs['Points'], I['Geometry'])
    b.put(iop.inputs['Instance'], sw.outputs[0])
    b.put(iop.inputs['Pick Instance'], I['Pick Variant'])
    b.put(iop.inputs['Instance Index'], b.attr('variant', 'INT'))
    sit = b.node('GeometryNodeSetInstanceTransform')
    b.put(sit.inputs['Instances'], iop.outputs[0])
    b.put(sit.inputs['Transform'], b.attr('flora_xform', 'FLOAT4X4'))
    rm = b.node('GeometryNodeRemoveAttribute')
    b.put(rm.inputs['Geometry'], sit.outputs[0])
    rm.inputs['Name'].default_value = 'flora_xform'
    b.put(go.inputs[0], rm.outputs[0])
    return g


def _color_var(b):
    """The per-plant variable: on the realized field it rides each vertex (GEOMETRY), on a still stroke's instances
    it lives on the instancer; the missing one reads 0, so their sum serves both."""
    g = b.node('ShaderNodeAttribute', attribute_type='GEOMETRY', attribute_name='color_var').outputs['Fac']
    i = b.node('ShaderNodeAttribute', attribute_type='INSTANCER', attribute_name='color_var').outputs['Fac']
    return b.math('ADD', g, i)


def close_group():
    """Daisy petal close on the prototype: each ray vertex rotates about its petal's hinge (Rodrigues, the angle
    growing toward the tip, from the generator's records) by Close x its angle; then head_dz (height above the
    head centre, after closing) is stored for the field's round-head fix."""
    g = bpy.data.node_groups.get(GROUP_CLOSE)
    if g is not None and g.get('eb_version') == NODES_VERSION:
        return g
    if g is not None:
        g.name = GROUP_CLOSE + ' (old)'
    g = bpy.data.node_groups.new(GROUP_CLOSE, 'GeometryNodeTree')
    g['eb_version'] = NODES_VERSION
    _socket(g, 'Geometry', 'NodeSocketGeometry')
    _socket(g, 'Geometry', 'NodeSocketGeometry', 'OUTPUT')
    _socket(g, 'Close', 'NodeSocketFloat', default=0.0, lo=0.0, hi=1.0)
    b = NB(g)
    gi, go = b.node('NodeGroupInput'), b.node('NodeGroupOutput')
    rot = b.node('ShaderNodeVectorRotate', rotation_type='AXIS_ANGLE')
    b.put(rot.inputs['Vector'], b.node('GeometryNodeInputPosition').outputs[0])
    b.put(rot.inputs['Center'], b.attr('close_hinge_v', 'FLOAT_VECTOR'))
    b.put(rot.inputs['Axis'], b.attr('close_axis_v', 'FLOAT_VECTOR'))
    b.put(rot.inputs['Angle'], b.math('MULTIPLY', b.attr('close_angle'), gi.outputs['Close']))
    setp = b.node('GeometryNodeSetPosition')
    b.put(setp.inputs['Geometry'], gi.outputs[0])
    b.put(setp.inputs['Selection'], b.math('GREATER_THAN', b.attr('close_angle'), 0.0))
    b.put(setp.inputs['Position'], rot.outputs[0])
    st = b.node('GeometryNodeStoreNamedAttribute', data_type='FLOAT', domain='POINT')
    st.inputs['Name'].default_value = 'head_dz'
    b.put(st.inputs['Geometry'], setp.outputs[0])
    pz = b.separate(b.node('GeometryNodeInputPosition').outputs[0])[2]
    cz = b.separate(b.attr('close_center_v', 'FLOAT_VECTOR'))[2]
    b.put(st.inputs['Value'], b.math('MULTIPLY', b.math('SUBTRACT', pz, cz), b.attr('is_head')))
    geo = st.outputs[0]
    # the records have done their work: keep them off the realized field (48 bytes a vertex otherwise)
    for nm in ('close_angle', 'close_axis_v', 'close_center_v', 'close_hinge_v', 'is_head', 'lod_class'):
        rm = b.node('GeometryNodeRemoveAttribute')
        b.put(rm.inputs['Geometry'], geo)
        rm.inputs['Name'].default_value = nm
        geo = rm.outputs[0]
    b.put(go.inputs[0], geo)
    return g


# ── materials ─────────────────────────────────────────────────────────────────────────────────────────────────────
def load_map(path, color, alpha_mode='CHANNEL_PACKED'):
    im = bpy.data.images.load(path, check_existing=True)
    im.colorspace_settings.name = 'sRGB' if color else 'Non-Color'
    im.alpha_mode = alpha_mode
    return im


def leaf_material(name, maps, *, rough=0.6, sss=0.5, translucency=1.0, normal_mode='up', tint=None, recolor=None,
                  region_tint=None, palette=None, uv='UVMap', specular=0.5, grazing_damp=False, curl=0.0):
    """The foliage sheet material: albedo (alpha cutout at 0.35, binary, dithered), roughness map x rough, the
    tangent normal map's relief added to a light-gather base normal (normal_mode 'up' = world up, the turf law;
    'mesh_unflip' = the generator's own normals, the same from both sides; 'mesh' = two-sided, flipped toward the
    viewer, the daisy heads), and translucency: a Translucent lobe on the card's own normal, coloured by the albedo
    and scaled by the translucency map (so backlit leaves glow their own green) - EEVEE's GI, shadows and raytracing
    replace the WebGPU edition's emissive fill and Barre-Brisebois term. Per-plant shade 1 + 0.15 (color_var - 0.5)."""
    mat = bpy.data.materials.get(name)
    if mat is not None:
        return mat
    mat = bpy.data.materials.new(name)
    mat.surface_render_method = 'DITHERED'
    mat.use_transparent_shadow = True
    mat.use_backface_culling = False
    mat.use_backface_culling_shadow = False
    mat.thickness_mode = 'SLAB'
    nt = mat.node_tree
    nt.nodes.clear()
    b = NB(nt)
    uvn = b.node('ShaderNodeUVMap')
    uvn.uv_map = uv

    def tex(im, interp='Linear'):
        nd = b.node('ShaderNodeTexImage', interpolation=interp, extension='EXTEND')
        nd.image = im
        b.put(nd.inputs['Vector'], uvn.outputs[0])
        return nd
    alb = tex(maps['albedo'])
    rgb = alb.outputs['Color']
    if tint is not None:
        rgb = b.vmath('MULTIPLY', rgb, tuple(tint))
    lum_coef = (0.2126, 0.7152, 0.0722)
    if recolor is not None:
        rgb = b.scale(tuple(recolor), b.dot(rgb, lum_coef))
    if region_tint is not None:
        rt = region_tint
        u, v, _ = b.separate(uvn.outputs[0])
        inside = b.math('MULTIPLY', b.math('MULTIPLY', b.math('GREATER_THAN', u, rt['u0'] - 1e-6), b.math('LESS_THAN', u, rt['u1'] + 1e-6)),
                        b.math('MULTIPLY', b.math('GREATER_THAN', v, rt['v0'] - 1e-6), b.math('LESS_THAN', v, rt['v1'] + 1e-6)))
        rgb = b.vmath('MULTIPLY', rgb, b.mix_vec(inside, (1.0, 1.0, 1.0), tuple(rt['mul'])))
    cv = _color_var(b)
    if palette:
        rgb = _daisy_palette(b, rgb, uvn.outputs[0], cv, palette, lum_coef)
    shade = b.math('MULTIPLY_ADD', b.math('SUBTRACT', cv, 0.5), 0.15, 1.0)
    base = b.scale(rgb, shade)
    alpha = b.math('GREATER_THAN', alb.outputs['Alpha'], 0.35)
    rough_v = b.math('MULTIPLY', tex(maps['rough']).outputs['Color'], rough)
    geo = b.node('ShaderNodeNewGeometry')
    nrm = geo.outputs['Normal']
    if normal_mode == 'up':
        base_n = b.combine(0.0, 0.0, 1.0)
    elif normal_mode == 'mesh_unflip':
        base_n = b.scale(nrm, b.math('MULTIPLY_ADD', geo.outputs['Backfacing'], -2.0, 1.0))
    elif isinstance(normal_mode, (int, float)):
        # a share of the light-gather up normal over the card's own (two-sided) normal
        base_n = b.vmath('NORMALIZE', b.vmath('MULTIPLY_ADD', nrm, (1 - normal_mode,) * 3, c=(0.0, 0.0, float(normal_mode))))
    else:
        base_n = nrm
    if curl:
        # a blade is curved / folded across its width, a flat card is not: bend the normal across the card (along
        # the UV tangent, u runs edge to edge) by the vertex 'across' coordinate, so a low sun glints on a thin line
        # of each blade instead of mirroring off the whole card, and the blade shades round
        tg = b.node('ShaderNodeTangent', direction_type='UV_MAP', uv_map=uv)
        ac = b.node('ShaderNodeAttribute', attribute_type='GEOMETRY', attribute_name='across').outputs['Fac']
        base_n = b.vmath('NORMALIZE', b.vmath('ADD', base_n, b.scale(tg.outputs[0], b.math('MULTIPLY', ac, curl))))
    if maps.get('normal') is not None:
        nm_t = tex(maps['normal'])
        nm = b.node('ShaderNodeNormalMap', space='TANGENT', uv_map=uv)
        b.put(nm.inputs['Color'], nm_t.outputs['Color'])
        relief = b.vmath('SUBTRACT', nm.outputs[0], nrm)
        shade_n = b.vmath('NORMALIZE', b.vmath('MULTIPLY_ADD', relief, (0.85, 0.85, 0.85), c=base_n))
    else:
        shade_n = base_n
    trc = None
    if maps.get('transl') is not None and translucency > 0:
        tr_t = tex(maps['transl'])
        k = b.math('MINIMUM', b.math('MULTIPLY', tr_t.outputs['Color'], sss * 2.2 * TRANSL_GAIN * translucency), 1.0)
        trc = b.scale(base, k)
        if TRANSL_ENERGY == 'normalize':
            # what a sheet transmits it does not also reflect: R + T <= 0.95 (the rest absorbed, ~5 % to the
            # specular), one factor for both from the brightest channel of R + T = base x (1 + k)
            bx, by, bz = b.separate(base)
            peak = b.math('MULTIPLY', b.math('MAXIMUM', b.math('MAXIMUM', bx, by), bz), b.math('ADD', k, 1.0))
            f = b.math('MINIMUM', b.math('DIVIDE', 0.95, b.math('MAXIMUM', peak, 1e-4)), 1.0)
            base = b.scale(base, f)
            trc = b.scale(trc, f)
    pr = b.node('ShaderNodeBsdfPrincipled')
    b.put(pr.inputs['Base Color'], base)
    b.put(pr.inputs['Roughness'], rough_v)
    b.put(pr.inputs['Normal'], shade_n)
    pr.inputs['Metallic'].default_value = 0.0
    spec_lvl = specular
    if grazing_damp:
        # flat blade cards seen edge-on mirror a low sun across their whole width (Fresnel -> 1 at grazing, whatever
        # the roughness): white streaks. Real blades are curved and hairy, so that sheen lives on thin lines. Damp the
        # specular only as the view grazes the card: x (1 - facing^3), full sheen from 45 deg and nearer head-on
        lw = b.node('ShaderNodeLayerWeight')
        lw.inputs['Blend'].default_value = 0.5
        b.put(lw.inputs['Normal'], shade_n)
        f3 = b.math('POWER', lw.outputs['Facing'], 3.0)
        spec_lvl = b.math('MULTIPLY', b.math('SUBTRACT', 1.0, f3), specular)
    if SPEC_FACING:
        # a shading normal turned away from the camera (the back of a light-gather card, a curled or normal-mapped
        # edge seen edge-on) has no specular the camera could see, yet EEVEE's lobe still answers it, and under a
        # sun behind the plant it lights white specks (backlit sunflower heads, verifier 11-07): fade the specular
        # out as N.V falls from 0.1 to 0
        vis = b.smoothstep(0.0, 0.1, b.dot(shade_n, geo.outputs['Incoming']))
        spec_lvl = b.math('MULTIPLY', spec_lvl, vis)
    b.put(pr.inputs['Specular IOR Level'], spec_lvl)
    surf = pr.outputs[0]
    if trc is not None:
        tl = b.node('ShaderNodeBsdfTranslucent')
        b.put(tl.inputs['Color'], trc)
        b.put(tl.inputs['Normal'], nrm)
        add = b.node('ShaderNodeAddShader')
        b.put(add.inputs[0], surf)
        b.put(add.inputs[1], tl.outputs[0])
        surf = add.outputs[0]
    tp = b.node('ShaderNodeBsdfTransparent')
    mix = b.node('ShaderNodeMixShader')
    b.put(mix.inputs['Fac'], alpha)
    b.put(mix.inputs[1], tp.outputs[0])
    b.put(mix.inputs[2], surf)
    out = b.node('ShaderNodeOutputMaterial', target='ALL')
    b.put(out.inputs['Surface'], mix.outputs[0])
    out.inputs['Thickness'].default_value = 0.0
    return mat


def bark_material(name, maps, *, tint=(1.0, 1.0, 1.0), uv='UVMap'):
    """Shrub wood: the bark set tiled along the tube network's wrapped UVs (REPEAT), albedo x stemTint (the lift
    that matches each species' painted card stems) x per-plant shade, roughness map x 0.95, and the bark set's own
    normal map (the WebGPU edition sampled the leaf sheet's normal map at bark UVs; the bark normals were never
    loaded). Opaque; casts solid shadows."""
    mat = bpy.data.materials.get(name)
    if mat is not None:
        return mat
    mat = bpy.data.materials.new(name)
    nt = mat.node_tree
    nt.nodes.clear()
    b = NB(nt)
    uvn = b.node('ShaderNodeUVMap')
    uvn.uv_map = uv

    def tex(im):
        nd = b.node('ShaderNodeTexImage', interpolation='Linear', extension='REPEAT')
        nd.image = im
        b.put(nd.inputs['Vector'], uvn.outputs[0])
        return nd
    cv = _color_var(b)
    shade = b.math('MULTIPLY_ADD', b.math('SUBTRACT', cv, 0.5), 0.15, 1.0)
    base = b.scale(b.vmath('MULTIPLY', tex(maps['albedo']).outputs['Color'], tuple(tint)), shade)
    pr = b.node('ShaderNodeBsdfPrincipled')
    b.put(pr.inputs['Base Color'], base)
    if maps.get('rough') is not None:
        b.put(pr.inputs['Roughness'], b.math('MULTIPLY', tex(maps['rough']).outputs['Color'], 0.95))
    else:
        pr.inputs['Roughness'].default_value = 0.9
    if maps.get('normal') is not None:
        nm = b.node('ShaderNodeNormalMap', space='TANGENT', uv_map=uv)
        b.put(nm.inputs['Color'], tex(maps['normal']).outputs['Color'])
        b.put(pr.inputs['Normal'], nm.outputs[0])
    out = b.node('ShaderNodeOutputMaterial', target='ALL')
    b.put(out.inputs['Surface'], pr.outputs[0])
    return mat


def _daisy_palette(b, rgb, uv, cv, palette, lum_coef):
    """vegetation_daisy_gen.js daisyColorNode, rays only (the petal cells: u >= 428 px, v >= 605 px): luminance of the
    white ray art / 0.74 x a base -> tip tint along the ray; one colour per plant, picked by fract(7.919 cv + 0.137)
    over the cumulative weights."""
    from .vegetation_daisy_gen import PET, LUM_WHITE
    u, v, _ = b.separate(uv)
    in_pet = b.math('MULTIPLY', b.math('GREATER_THAN', u, PET['u0'] - 1e-7), b.math('GREATER_THAN', v, PET['v0'] - 1e-7))
    t = b.math('FRACT', b.math('DIVIDE', b.math('SUBTRACT', v, PET['v0']), PET['rowH']))
    tt = b.smoothstep(0.05, 0.75, t)
    lum = b.math('DIVIDE', b.dot(rgb, lum_coef), LUM_WHITE)

    def col_of(e):
        if e.get('white'):
            return rgb
        return b.scale(b.mix_vec(tt, tuple(e['base']), tuple(e['tip'])), lum)
    col = col_of(palette[0])
    if len(palette) > 1 or palette[0].get('cum') is not None:
        pick = b.math('FRACT', b.math('MULTIPLY_ADD', cv, 7.919, 0.137))
        for k in range(1, len(palette)):
            col = b.mix_vec(b.math('GREATER_THAN', pick, palette[k - 1]['cum'] - 1e-9), col, col_of(palette[k]))
    return b.mix_vec(in_pet, rgb, col)
