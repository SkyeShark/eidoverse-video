"""Wetness and puddles: the eido_wet group in front of each Principled BSDF, fed by the 2D moisture history.

wrap_material(mat) inserts one eido_wet group between a Principled BSDF and the sources of its Base Color, Roughness,
Metallic, Normal and IOR (the WebGPU wrapMaterial rewrote colorNode / roughnessNode / metalnessNode / normalNode the
same way). The group is Eanpa's wetness response, which reads the moisture history (moisture.R thin wetness,
moisture.G pooled water, moisture.B the local rain cell):

- upward, exposed surfaces darken a little (porous dielectrics, wetPorosity 0.65) and gloss up: wetness reads
  through reflection, not blackness; metals keep their conductor response;
- puddles fill the procedural cavities first (value noise thresholded at its middle, domain-warped so outlines
  meander) and spread as pooled water rises; water is a dielectric of IOR 1.333 (F0 0.0204) at roughness 0.045,
  so it is a mirror toward grazing and a see-through sheen from above, over water-deepened ground;
- sparse expanding capillary rings ripple the water's normal while rain falls on that cell, fading past 8-35 m;
- detail fades to uniform sheen at 160-450 m.

wrap_material(mat, model='eidoverse') inserts eido_wet_eidoverse instead: eidoverse/weather_system.js's own
wrapMaterial, one global wetness (the state's wet x k, no history), for matching an eidoverse film.

Receivers opt out like the JS userData: object custom properties eido_dry = 1 (noWet), eido_no_puddles = 1
(noPuddles), eido_wet_reduce = 1 - wetnessFactor; material custom properties eido_noWet, eido_noPuddles,
eido_wetPorosity. unwrap_material restores the original links and values.
"""
import json
import os
import shutil

import bpy

from ._graph import G, shader_group
from .values import add_values_node

WET_GROUP = 'eido_wet'
UV_GROUP = 'eido_moisture_uv'
MOISTURE_IMAGE = 'eido_moisture'
SOCKETS = ('Base Color', 'Roughness', 'Metallic', 'Normal', 'IOR')
GROUND_LEVEL = 0.6       # metres above its line's lowest surface a fragment still reads the gust-soft mask (shelter.py)


def wet_group():
    if WET_GROUP in bpy.data.node_groups:
        return bpy.data.node_groups[WET_GROUP]
    tree, gi, go = shader_group(WET_GROUP, [
        ('Base Color', 'NodeSocketColor', (0.8, 0.8, 0.8, 1.0)), ('Roughness', 'NodeSocketFloat', 0.5),
        ('Metallic', 'NodeSocketFloat', 0.0), ('Normal', 'NodeSocketVector', (0.0, 0.0, 1.0)),
        ('IOR', 'NodeSocketFloat', 1.5), ('Moisture', 'NodeSocketColor', (0.0, 0.0, 0.0, 1.0)),
        ('Porosity', 'NodeSocketFloat', 0.65), ('Puddle Gate', 'NodeSocketFloat', 1.0),
        ('Cavity', 'NodeSocketFloat', 0.0), ('Use Cavity', 'NodeSocketFloat', 0.0), ('Exposure', 'NodeSocketFloat', 1.0),
        ('Shelter', 'NodeSocketColor', (0.0, 0.0, 1.0, 1.0)), ('Shelter Height', 'NodeSocketFloat', -1.0e4),
        ('Shelter Soft', 'NodeSocketColor', (0.0, -1.0e4, 0.0, 1.0)),
    ], [('Base Color', 'NodeSocketColor'), ('Roughness', 'NodeSocketFloat'), ('Metallic', 'NodeSocketFloat'),
        ('Normal', 'NodeSocketVector'), ('IOR', 'NodeSocketFloat'), ('Wet', 'NodeSocketFloat'),
        ('Puddle', 'NodeSocketFloat')])
    b = G(tree, x0=-1500, y0=900)
    I = gi.outputs
    vals = add_values_node(tree, -1700, 400)
    V = vals.outputs
    geo = b.node('ShaderNodeNewGeometry')
    P = b.vec(geo.outputs['Position'])
    Ng = b.vec(geo.outputs['Normal'])
    px, py, _pz = P.xyz()
    _nx, _ny, nz = Ng.xyz()
    x3, z3 = px, -py                                  # three's (x, z) ground coordinates

    def obj_attr(name):
        n = b.node('ShaderNodeAttribute', attribute_type='OBJECT')
        n.attribute_name = name
        return b.s(n.outputs['Fac'])

    wet_gate = (1.0 - obj_attr('eido_dry')) * (1.0 - obj_attr('eido_wet_reduce'))
    puddle_gate = b.s(I['Puddle Gate']) * (1.0 - obj_attr('eido_no_puddles'))
    msep = b.node('ShaderNodeSeparateColor')
    b.link(I['Moisture'], msep.inputs[0])
    m_wet, m_water, m_cell = (b.s(msep.outputs[i]) for i in range(3))
    incidence = b.clamp(b.dot(Ng, V['Source Dir']))
    # rain exposure (Eanpa's surface field): the fragment against the plane of the first surface its line of rain
    # meets, with 0.06 m of bias (+0.28 m where the rain grazes); outside the map, or where no surface was met, open.
    # Ground-level fragments (within GROUND_LEVEL of their line's lowest surface) read the gust-soft mask instead
    # (shelter.soft_map, filtered linearly): the rain shadow of a roof or an awning with the soft edge gusts give it.
    _px, _py, pz = P.xyz()
    dx, dy, dz = b.vec(V['Shelter Dir']).xyz()
    ox, oy, _o = b.vec(V['Shelter Origin']).xyz()
    sx, sy, _s = b.vec(V['Shelter Size']).xyz()
    rw, rh, _r = b.vec(V['Shelter Res']).xyz()
    lx = px - dx * (pz / dz)
    ly = py - dy * (pz / dz)
    u, v = (lx - ox) / sx, (ly - oy) / sy
    inside = b.gt(u, -1e-9) * b.lt(u, 1.0) * b.gt(v, -1e-9) * b.lt(v, 1.0)
    uc, vc = (b.floor(u * rw) + 0.5) / rw, (b.floor(v * rh) + 0.5) / rh
    zh = b.s(I['Shelter Height'])
    hx, hy = ox + uc * sx + dx * (zh / dz), oy + vc * sy + dy * (zh / dz)
    sn = b.vec(I['Shelter'])
    sep = b.dot(P - b.combine(hx, hy, zh), sn)
    bias = (1.0 - incidence) * 0.28 + 0.06
    exact = b.lerp(1.0, b.sstep(-bias - 0.025, -bias + 0.025, sep), b.gt(zh, -5000.0))
    ssep = b.node('ShaderNodeSeparateColor')
    b.link(I['Shelter Soft'], ssep.inputs[0])
    soft_blocked, z_low = b.s(ssep.outputs[0]), b.s(ssep.outputs[1])
    ground = b.lt(pz - z_low, GROUND_LEVEL)
    exposed = b.lerp(exact, 1.0 - soft_blocked, ground)
    exposure = b.lerp(1.0, exposed, inside * b.s(V['Shelter On'])) * I['Exposure']
    wet_amount = b.pow(incidence, 0.75) * m_wet * wet_gate * exposure
    flat = b.sstep(0.985, 0.998, nz)
    wx = (b.vnoise2(x3 * 0.045, z3 * 0.045) - 0.5) * 2.2
    wz = (b.vnoise2(x3 * 0.045 + 37.7, z3 * 0.045 + 11.3) - 0.5) * 2.2
    pn = b.vnoise2(x3 * 0.35 + wx, z3 * 0.35 + wz) + b.vnoise2(x3 * 0.09, z3 * 0.09) * 0.6
    cam = b.node('ShaderNodeCameraData')
    pdist = b.s(cam.outputs['View Distance'])
    cavity = b.lerp(b.clamp(pn / 1.6), b.s(I['Cavity']), b.s(I['Use Cavity']))
    fill = b.lerp(0.79, 0.56, m_water)
    pshape = (b.sstep(fill, fill + 0.055, cavity) * flat * b.s(V['Puddle K']) * puddle_gate * wet_gate * exposure
              * (1.0 - b.sstep(160.0, 450.0, pdist)))
    base_metal = b.s(I['Metallic'])
    puddle_amount = pshape * b.sstep(0.06, 0.42, m_water) * (1.0 - base_metal)
    active = b.max(b.gt(V['Wetness'], 0.001), b.gt(V['Surface Water'], 0.06))
    up = wet_amount * active
    puddle = puddle_amount * active
    porosity = b.s(I['Porosity'])
    base = b.vec(I['Base Color'])
    darkened = base * (1.0 - up * porosity * 0.5 * (1.0 - base_metal))
    tint = b.vec(V['Wet Tint'])
    k = up * 0.6
    wet_col = b.vmath('MULTIPLY', darkened, b.combine(1.0, 1.0, 1.0) + (tint - b.combine(1.0, 1.0, 1.0)) * k)
    pdepth = b.sstep(0.3, 1.0, puddle)
    water_floor = wet_col * b.lerp(0.98, 1.0 - porosity * 0.28, pdepth)
    final = wet_col + (water_floor - wet_col) * puddle
    rough0 = b.s(I['Roughness'])
    rough = b.lerp(b.lerp(rough0, b.max(0.045, rough0 * 0.48), up), b.s(V['Rain K']) * 0.025 + 0.045, puddle)
    metal = b.lerp(base_metal, 0.0, puddle)
    # capillary rings on the water while rain falls on this cell
    t = b.s(V['Time'])
    rx = ry = 0.0
    for off in (0.0, 0.537):
        qx, qz = x3 / 1.1 + off, z3 / 1.1 + off
        cx, cz = b.floor(qx), b.floor(qz)
        phase = b.fract(t * 1.7 + b.hash2(cx + 19.3, cz + 19.3))
        ccx = b.hash2(cx, cz) * 0.3 + 0.35
        ccz = b.hash2(cx + 47.1, cz + 47.1) * 0.3 + 0.35
        dx, dz = (b.fract(qx) - ccx) * 1.1, (b.fract(qz) - ccz) * 1.1
        radius = b.length2(dx, dz) + 0.0001
        wave = radius - (phase * 0.33 + 0.012)
        env = b.exp(wave * wave * -900.0) * b.sstep(0.02, 0.12, phase) * (1.0 - phase) * (1.0 - phase)
        amp = b.cos(wave * 110.0) * env * 0.075 / radius
        rx = rx + dx * amp
        ry = ry + dz * amp
    rain_k = b.s(V['Rain K'])
    rgate = (m_cell * rain_k * (1.0 - b.sstep(8.0, 35.0, pdist))
             * b.gt(rain_k, 0.001) * b.gt(V['Surface Water'], 0.06))
    rx, ry = rx * rgate, ry * rgate
    water_n = b.normalize(b.combine(-rx, ry, 1.0))       # three (-rx, 1, -ry) in Blender axes
    nrm = b.normalize(b.vec(I['Normal']) + (water_n - b.vec(I['Normal'])) * puddle)
    ior = b.lerp(b.s(I['IOR']), 1.333, puddle)
    for name, val in (('Base Color', final), ('Roughness', rough), ('Metallic', metal), ('Normal', nrm),
                      ('IOR', ior), ('Wet', up), ('Puddle', puddle)):
        b.link(val, go.inputs[name])
    return tree


EIDOVERSE_WET_GROUP = 'eido_wet_eidoverse'


def eidoverse_wet_group():
    """eidoverse/weather_system.js wrapMaterial, formula for formula: one global wetness (w.wet x k, eased through a
    transition, no history), upward surfaces (normal.y squared) darken to 0.68 and gloss to roughness 0.10, puddles
    where the warped two-octave value noise passes 0.97-1.13 on flat ground (once wetness passes 0.35-0.9), deepened
    and cooled toward their centres, mirror-smooth (0.045) and never metallic, fading to sheen at 160-450 m. The
    same sockets as eido_wet, so wrap / unwrap are shared; Normal and IOR pass through (eidoverse left them)."""
    if EIDOVERSE_WET_GROUP in bpy.data.node_groups:
        return bpy.data.node_groups[EIDOVERSE_WET_GROUP]
    tree, gi, go = shader_group(EIDOVERSE_WET_GROUP, [
        ('Base Color', 'NodeSocketColor', (0.8, 0.8, 0.8, 1.0)), ('Roughness', 'NodeSocketFloat', 0.5),
        ('Metallic', 'NodeSocketFloat', 0.0), ('Normal', 'NodeSocketVector', (0.0, 0.0, 1.0)),
        ('IOR', 'NodeSocketFloat', 1.5), ('Moisture', 'NodeSocketColor', (0.0, 0.0, 0.0, 1.0)),
        ('Porosity', 'NodeSocketFloat', 0.65), ('Puddle Gate', 'NodeSocketFloat', 1.0),
        ('Cavity', 'NodeSocketFloat', 0.0), ('Use Cavity', 'NodeSocketFloat', 0.0), ('Exposure', 'NodeSocketFloat', 1.0),
        ('Shelter', 'NodeSocketColor', (0.0, 0.0, 1.0, 1.0)), ('Shelter Height', 'NodeSocketFloat', -1.0e4),
    ], [('Base Color', 'NodeSocketColor'), ('Roughness', 'NodeSocketFloat'), ('Metallic', 'NodeSocketFloat'),
        ('Normal', 'NodeSocketVector'), ('IOR', 'NodeSocketFloat'), ('Wet', 'NodeSocketFloat'),
        ('Puddle', 'NodeSocketFloat')])
    b = G(tree, x0=-1500, y0=900)
    I = gi.outputs
    V = add_values_node(tree, -1700, 400).outputs
    geo = b.node('ShaderNodeNewGeometry')
    P = b.vec(geo.outputs['Position'])
    px, py, _pz = P.xyz()
    _nx, _ny, nz = b.vec(geo.outputs['Normal']).xyz()      # three normalWorld.y is Blender's world z
    x3, z3 = px, -py

    def obj_attr(name):
        n = b.node('ShaderNodeAttribute', attribute_type='OBJECT')
        n.attribute_name = name
        return b.s(n.outputs['Fac'])

    wetness = b.s(V['Wet Target']) * (1.0 - obj_attr('eido_dry')) * (1.0 - obj_attr('eido_wet_reduce'))
    up = b.pow(b.clamp(nz), 2.0) * wetness
    puddle_gate = b.s(I['Puddle Gate']) * (1.0 - obj_attr('eido_no_puddles'))
    flat = b.sstep(0.985, 0.998, nz)
    wx = (b.vnoise2(x3 * 0.045, z3 * 0.045) - 0.5) * 2.2
    wz = (b.vnoise2(x3 * 0.045 + 37.7, z3 * 0.045 + 11.3) - 0.5) * 2.2
    pn = b.vnoise2(x3 * 0.35 + wx, z3 * 0.35 + wz) + b.vnoise2(x3 * 0.09, z3 * 0.09) * 0.6
    pdist = b.s(b.node('ShaderNodeCameraData').outputs['View Distance'])
    pshape = (b.sstep(0.97, 1.13, pn) * flat * b.s(V['Puddle K']) * puddle_gate * (1.0 - b.sstep(160.0, 450.0, pdist)))
    puddle = b.sstep(0.25, 0.6, pshape) * b.sstep(0.35, 0.9, wetness)
    base = b.vec(I['Base Color'])
    one = b.combine(1.0, 1.0, 1.0)
    darkened = base * b.lerp(1.0, 0.68, up * 0.85)
    wet_col = b.vmath('MULTIPLY', darkened, one + (b.vec(V['Wet Tint']) - one) * (up * 0.6))
    pdepth = b.sstep(0.3, 1.0, pshape)
    floor_tint = one + (b.combine(0.84, 0.91, 1.0) - one) * (pdepth * 0.7)
    water_floor = b.vmath('MULTIPLY', wet_col * b.lerp(0.96, 0.62, pdepth), floor_tint)
    final = wet_col + (water_floor - wet_col) * puddle
    rough = b.lerp(b.lerp(b.s(I['Roughness']), 0.10, up * 0.8), 0.045, puddle)
    metal = b.lerp(b.s(I['Metallic']), 0.0, puddle)
    for name, val in (('Base Color', final), ('Roughness', rough), ('Metallic', metal), ('Normal', I['Normal']),
                      ('IOR', I['IOR']), ('Wet', up), ('Puddle', puddle)):
        b.link(val, go.inputs[name])
    return tree


WET_MODELS = {'moisture': wet_group, 'eidoverse': eidoverse_wet_group}


def moisture_uv_group():
    """World position -> the moisture image's UV: ((x, y) - centre) / span + 0.5."""
    if UV_GROUP in bpy.data.node_groups:
        return bpy.data.node_groups[UV_GROUP]
    tree, gi, go = shader_group(UV_GROUP, [], [('Vector', 'NodeSocketVector')])
    b = G(tree)
    vals = add_values_node(tree, -900, 200)
    geo = b.node('ShaderNodeNewGeometry')
    px, py, _ = b.vec(geo.outputs['Position']).xyz()
    cx, cy, span = b.vec(vals.outputs['Moisture Center']).xyz()
    b.link(b.combine((px - cx) / span + 0.5, (py - cy) / span + 0.5, 0.0), go.inputs['Vector'])
    return tree


SHELTER_UV_GROUP = 'eido_shelter_uv'
SHELTER_IMAGE = 'eido_shelter'
SHELTER_SOFT_IMAGE = 'eido_shelter_soft'


def shelter_uv_group():
    """World position -> its line of rain in the exposure maps: Vector, the texel centre (the exact map, sampled
    Closest); Smooth, the position itself (the gust-soft mask, sampled Linear)."""
    if SHELTER_UV_GROUP in bpy.data.node_groups:
        return bpy.data.node_groups[SHELTER_UV_GROUP]
    tree, gi, go = shader_group(SHELTER_UV_GROUP, [], [('Vector', 'NodeSocketVector'),
                                                       ('Smooth', 'NodeSocketVector')])
    b = G(tree)
    vals = add_values_node(tree, -900, 200)
    V = vals.outputs
    geo = b.node('ShaderNodeNewGeometry')
    px, py, pz = b.vec(geo.outputs['Position']).xyz()
    dx, dy, dz = b.vec(V['Shelter Dir']).xyz()
    ox, oy, _ = b.vec(V['Shelter Origin']).xyz()
    sx, sy, _ = b.vec(V['Shelter Size']).xyz()
    rw, rh, _ = b.vec(V['Shelter Res']).xyz()
    u = (px - dx * (pz / dz) - ox) / sx
    v = (py - dy * (pz / dz) - oy) / sy
    b.link(b.combine((b.floor(u * rw) + 0.5) / rw, (b.floor(v * rh) + 0.5) / rh, 0.0), go.inputs['Vector'])
    b.link(b.combine(u, v, 0.0), go.inputs['Smooth'])
    return tree


def shelter_image(path, name=SHELTER_IMAGE):
    """Load (or point at) an exposure map: the exact one (eido_shelter) or the gust-soft mask (eido_shelter_soft)."""
    img = bpy.data.images.get(name)
    if img is None:
        img = bpy.data.images.load(path, check_existing=False)
        img.name = name
    else:
        img.filepath = path
        img.reload()
    img.colorspace_settings.name = 'Non-Color'
    img.alpha_mode = 'CHANNEL_PACKED'
    if bpy.data.filepath:
        try:
            img.filepath = bpy.path.relpath(path)
        except ValueError:
            pass
    return img


def moisture_sequence(pattern, frame_start, n_frames):
    """The moisture image sequence (files numbered by frame), plus its hold copy before the first frame."""
    first = pattern % frame_start
    if frame_start - 1 >= 0:
        shutil.copyfile(first, pattern % (frame_start - 1))
    img = bpy.data.images.get(MOISTURE_IMAGE)
    if img is None:
        img = bpy.data.images.load(first, check_existing=False)
        img.name = MOISTURE_IMAGE
    else:
        img.filepath = first
    img.source = 'SEQUENCE' if n_frames > 1 else 'FILE'
    img.colorspace_settings.name = 'Non-Color'
    img.alpha_mode = 'CHANNEL_PACKED'
    if bpy.data.filepath:
        try:
            img.filepath = bpy.path.relpath(first)
        except ValueError:
            pass
    img.reload()
    return img


def _set_user(node, frame_start, n_frames):
    iu = node.image_user
    iu.frame_start = frame_start
    iu.frame_duration = n_frames
    iu.frame_offset = frame_start - 1
    iu.use_auto_refresh = True
    iu.use_cyclic = False


def _restore_record(socket):
    if socket.is_linked:
        lk = socket.links[0]
        return dict(node=lk.from_node.name, out=lk.from_socket.identifier)
    v = socket.default_value
    return dict(value=list(v) if hasattr(v, '__len__') else float(v))


def wrap_material(mat, receiver=None, seq=None, model='moisture'):
    """Insert eido_wet in front of every Principled BSDF of `mat`. Returns True when it wrapped something new.

    seq = (frame_start, n_frames) of the moisture sequence, set on the material's moisture image node.
    model: 'moisture' (eido_wet: Eanpa's response over the 2D moisture history) or 'eidoverse' (eido_wet_eidoverse:
    eidoverse/weather_system.js's one global wetness)."""
    if mat is None or not mat.use_nodes or mat.node_tree is None:
        return False
    if mat.get('eido_noWet') or mat.get('eido_wet_wrapped'):
        return False
    nt = mat.node_tree
    principled = [n for n in nt.nodes if n.bl_idname == 'ShaderNodeBsdfPrincipled']
    if not principled:
        return False
    if model not in WET_MODELS:
        raise ValueError("wrap_material: model must be one of %s, not '%s'" % (' | '.join(WET_MODELS), model))
    group = WET_MODELS[model]()
    img = bpy.data.images.get(MOISTURE_IMAGE)
    tex = nt.nodes.new('ShaderNodeTexImage')
    tex.name = tex.label = 'eido_moisture'
    tex.interpolation = 'Linear'
    tex.extension = 'EXTEND'
    tex.image = img
    if seq:
        _set_user(tex, *seq)
    uvn = nt.nodes.new('ShaderNodeGroup')
    uvn.node_tree = moisture_uv_group()
    uvn.name = 'eido_moisture_uv'
    nt.links.new(uvn.outputs[0], tex.inputs['Vector'])
    shu = nt.nodes.new('ShaderNodeGroup')          # the line of rain through the fragment in the exposure maps
    shu.node_tree = shelter_uv_group()
    shu.name = 'eido_shelter_uv'
    sht = nt.nodes.new('ShaderNodeTexImage')        # the exact first surface (Closest)
    sht.name = sht.label = 'eido_shelter'
    sht.interpolation = 'Closest'
    sht.extension = 'EXTEND'
    sht.image = bpy.data.images.get(SHELTER_IMAGE)
    nt.links.new(shu.outputs['Vector'], sht.inputs['Vector'])
    shs = nt.nodes.new('ShaderNodeTexImage')        # the gust-soft ground mask (Linear)
    shs.name = shs.label = 'eido_shelter_soft'
    shs.interpolation = 'Linear'
    shs.extension = 'EXTEND'
    shs.image = bpy.data.images.get(SHELTER_SOFT_IMAGE)
    nt.links.new(shu.outputs['Smooth'], shs.inputs['Vector'])
    geo = nt.nodes.new('ShaderNodeNewGeometry')
    geo.name = 'eido_wet_geometry'
    restore = {}
    for i, p in enumerate(principled):
        x, y = p.location
        tex.location = (x - 700, y - 500)
        uvn.location = (x - 950, y - 500)
        sht.location = (x - 700, y - 800)
        shs.location = (x - 700, y - 1080)
        shu.location = (x - 950, y - 900)
        geo.location = (x - 700, y - 1360)
        g = nt.nodes.new('ShaderNodeGroup')
        g.node_tree = group
        g.name = f'eido_wet_{i}'
        g.location = (x - 300, y)
        rec = {}
        for s in SOCKETS:
            inp = p.inputs[s]
            rec[s] = _restore_record(inp)
            if inp.is_linked:
                nt.links.new(inp.links[0].from_socket, g.inputs[s])
            elif s == 'Normal':
                nt.links.new(geo.outputs['Normal'], g.inputs[s])
            else:
                g.inputs[s].default_value = inp.default_value
            nt.links.new(g.outputs[s], inp)
        nt.links.new(tex.outputs['Color'], g.inputs['Moisture'])
        nt.links.new(sht.outputs['Color'], g.inputs['Shelter'])
        if sht.image is not None:
            nt.links.new(sht.outputs['Alpha'], g.inputs['Shelter Height'])
        if 'Shelter Soft' in g.inputs and shs.image is not None:      # eidoverse's own model reads no exposure
            nt.links.new(shs.outputs['Color'], g.inputs['Shelter Soft'])
        g.inputs['Porosity'].default_value = max(0.0, min(1.0, float(mat.get('eido_wetPorosity', 0.65))))
        g.inputs['Puddle Gate'].default_value = 0.0 if mat.get('eido_noPuddles') else 1.0
        restore[p.name] = dict(group=g.name, inputs=rec)
    mat['eido_wet_wrapped'] = 1
    mat['eido_wet_model'] = model
    mat['eido_wet_restore'] = json.dumps(restore)
    return True


def unwrap_material(mat):
    """Remove eido_wet from `mat` and restore every Principled input it touched."""
    if mat is None or not mat.get('eido_wet_wrapped'):
        return False
    nt = mat.node_tree
    restore = json.loads(mat.get('eido_wet_restore', '{}'))
    for pname, rec in restore.items():
        p = nt.nodes.get(pname)
        g = nt.nodes.get(rec['group'])
        if p is None:
            continue
        for s, r in rec['inputs'].items():
            inp = p.inputs[s]
            for lk in list(inp.links):
                nt.links.remove(lk)
            if 'node' in r and r['node'] in nt.nodes:
                src = nt.nodes[r['node']]
                out = next((o for o in src.outputs if o.identifier == r['out']), None)
                if out is not None:
                    nt.links.new(out, inp)
            elif 'value' in r:
                v = r['value']
                inp.default_value = v if not isinstance(v, list) else tuple(v)
        if g is not None:
            nt.nodes.remove(g)
    for name in ('eido_moisture', 'eido_moisture_uv', 'eido_wet_geometry', 'eido_shelter', 'eido_shelter_soft',
                 'eido_shelter_uv'):
        n = nt.nodes.get(name)
        if n is not None:
            nt.nodes.remove(n)
    del mat['eido_wet_wrapped']
    for key in ('eido_wet_restore', 'eido_wet_model'):
        if key in mat:
            del mat[key]
    return True


def set_sequence(mat, frame_start, n_frames):
    """Point a wrapped material at the moisture sequence of the bake, and at the exposure map when there is one."""
    nt = mat.node_tree if mat else None
    n = nt.nodes.get('eido_moisture') if nt else None
    if n is not None:
        n.image = bpy.data.images.get(MOISTURE_IMAGE)
        _set_user(n, frame_start, n_frames)
    link_shelter(mat)


def link_shelter(mat):
    """Point a wrapped material's exposure lookups at the bake's maps (the exact first surface, the gust-soft mask)."""
    nt = mat.node_tree if mat else None
    img = bpy.data.images.get(SHELTER_IMAGE)
    if nt is None or img is None:
        return
    groups = [g for g in nt.nodes if g.bl_idname == 'ShaderNodeGroup' and g.node_tree
              and g.node_tree.name in (WET_GROUP, EIDOVERSE_WET_GROUP)]
    s = nt.nodes.get('eido_shelter')
    if s is not None:
        s.image = img
        for g in groups:
            if not g.inputs['Shelter Height'].is_linked:
                nt.links.new(s.outputs['Alpha'], g.inputs['Shelter Height'])
    soft = bpy.data.images.get(SHELTER_SOFT_IMAGE)
    ss = nt.nodes.get('eido_shelter_soft')
    if ss is not None and soft is not None:
        ss.image = soft
        for g in groups:
            if 'Shelter Soft' in g.inputs and not g.inputs['Shelter Soft'].is_linked:
                nt.links.new(ss.outputs['Color'], g.inputs['Shelter Soft'])


def write_moisture_frame(pattern, frame, field, cell_image):
    """One frame of the moisture sequence: R wet, G water (as receivers see them now), B the local rain cell."""
    import numpy as np
    from ..sky.bake.baker import write_exr
    d = field.displayed()
    arr = np.zeros((field.size, field.size, 4), np.float32)
    arr[..., 0] = d[..., 0]
    arr[..., 1] = d[..., 1]
    arr[..., 2] = cell_image
    arr[..., 3] = 1.0
    write_exr(pattern % frame, arr, half=True)


def cleanup_sequence(cache_dir):
    for f in os.listdir(cache_dir):
        if f.startswith('moisture_') and f.endswith('.exr'):
            os.remove(os.path.join(cache_dir, f))
