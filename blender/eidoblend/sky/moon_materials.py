"""The shattered moon's materials and its debris river (asteroid_moon.js celestial-body shading, Eanpa's newest).

eido_moon_keys        the keyed values the moon's frame block writes: sun_dir (Blender), sun_col, gain, fade
fragment material     unlit, self-shaded: a Lommel-Seeliger/Lambert blend (particulate regolith keeps a broad lit face
                      and a defined terminator) with a geometric horizon guard, times sun colour and gain; under the
                      sky's shield and clouds (overlay); faded by the night-only visibility
speck system          the GRANULAR DEBRIS RIVER: 7000 octahedral grains streaming in braided lanes along the fragment
                      line (30% orbiting a parent fragment), power-law sizes, lambert-lit like the fragments. Geometry
                      Nodes evaluate the JS update() formulas from Scene Time, so every frame stands on its own.
asteroid material     makeAsteroidMoon's celestial lambert over the baked object-space normal atlas.
"""
import math

import bpy
import numpy as np

from .nodes import Graph, keyed_values_group
from .sky_view import overlay_opaque

KEYS = 'eido_moon_keys'


def moon_keys_group():
    ng = bpy.data.node_groups.get(KEYS)
    if ng is not None:
        return ng, {n.name: n for n in ng.nodes if n.bl_idname != 'NodeGroupOutput'}
    return keyed_values_group(KEYS, dict(sun_dir=(0.0, 0.9, 0.4), sun_col=(1.0, 0.62, 0.35), gain=2.0, fade=1.0))


def _faded(g, shader, fade):
    """fade 0..1: the moon is a night-sky body (Eanpa's one-uniform fade, stochastic here)."""
    tr = g.node('ShaderNodeBsdfTransparent')
    mix = g.node('ShaderNodeMixShader')
    g.link(fade, mix.inputs['Fac'])
    g.link(tr.outputs[0], mix.inputs[1])
    g.link(shader, mix.inputs[2])
    return mix.outputs[0]


def _emission(g, color):
    em = g.node('ShaderNodeEmission')
    g.link(color, em.inputs['Color'])
    em.inputs['Strength'].default_value = 1.0
    return em.outputs[0]


def fragment_material(ob):
    """Rewire a fragment's GLB material to the celestial body shading (scene-lit materials blow out to a white blob at
    sky distance)."""
    src = ob.data.materials[0] if ob.data.materials else None
    albedo_img = normal_img = None
    if src is not None and src.node_tree:
        for n in src.node_tree.nodes:
            if n.type == 'TEX_IMAGE' and n.image:
                if n.image.colorspace_settings.name.lower().startswith('srgb'):
                    albedo_img = n.image
                else:
                    normal_img = n.image
    name = 'eido_moon_fragment_%s' % (src.name if src else 'rock')
    m = bpy.data.materials.get(name)
    if m is None:
        m = bpy.data.materials.new(name)
        m.use_nodes = True
        m.surface_render_method = 'DITHERED'
        nt = m.node_tree
        nt.nodes.clear()
        g = Graph(nt)
        k = g.group(bpy.data.node_groups[KEYS]).outputs
        uvn = g.node('ShaderNodeUVMap')
        if albedo_img is not None:
            alb = g.image(albedo_img, uvn.outputs['UV'], label='fragment_albedo').outputs['Color']
        else:
            alb = (0.42, 0.38, 0.34)
        geo = g.node('ShaderNodeNewGeometry')
        n_geo = geo.outputs['Normal']
        n_w = n_geo
        if normal_img is not None:
            nt_img = g.image(normal_img, uvn.outputs['UV'], label='fragment_normal')
            nm = g.node('ShaderNodeNormalMap')
            g.link(nt_img.outputs['Color'], nm.inputs['Color'])
            n_w = nm.outputs['Normal']
        sun = k['sun_dir']
        incidence = g.max(g.vdot(n_w, sun), 0.0)
        emission = g.max(g.vdot(n_w, geo.outputs['Incoming']), 0.0)
        limb = g.smoothstep(-0.025, 0.065, g.vdot(n_geo, sun))
        particulate = g.div(incidence, g.max(g.add(incidence, emission), 0.05))
        lit = g.add(g.mul(g.add(g.mul(particulate, 0.75), g.mul(incidence, 0.25)), limb), 0.018)
        col = g.vscale(g.vmul(alb, k['sun_col']), g.mul(lit, k['gain']))
        surf = overlay_opaque(g, _emission(g, col))
        out = g.node('ShaderNodeOutputMaterial')
        g.link(_faded(g, surf, k['fade']), out.inputs['Surface'])
    ob.data.materials.clear()
    ob.data.materials.append(m)
    return m


def speck_material():
    m = bpy.data.materials.get('eido_moon_specks')
    if m is not None:
        return m
    m = bpy.data.materials.new('eido_moon_specks')
    m.use_nodes = True
    m.surface_render_method = 'DITHERED'
    nt = m.node_tree
    nt.nodes.clear()
    g = Graph(nt)
    k = g.group(bpy.data.node_groups[KEYS]).outputs
    geo = g.node('ShaderNodeNewGeometry')
    lit = g.add(g.mul(g.max(g.vdot(geo.outputs['Normal'], k['sun_dir']), 0.0), 0.92), 0.08)
    col = g.vscale(g.vmul((0.42, 0.38, 0.34), k['sun_col']), g.mul(lit, k['gain']))
    out = g.node('ShaderNodeOutputMaterial')
    g.link(_faded(g, overlay_opaque(g, _emission(g, col)), k['fade']), out.inputs['Surface'])
    return m


def asteroid_material(ob, baked_path, normal_path=None):
    m = bpy.data.materials.new('eido_asteroid_moon')
    m.use_nodes = True
    nt = m.node_tree
    nt.nodes.clear()
    g = Graph(nt)
    k = g.group(bpy.data.node_groups[KEYS]).outputs
    uvn = g.node('ShaderNodeUVMap')
    img = bpy.data.images.load(baked_path, check_existing=True)
    alb = g.image(img, uvn.outputs['UV'], label='asteroid_baked').outputs['Color']
    if normal_path:
        nimg = bpy.data.images.load(normal_path, check_existing=True)
        nimg.colorspace_settings.name = 'Non-Color'
        n_obj = g.vsub(g.vscale(g.image(nimg, uvn.outputs['UV'], label='asteroid_normal').outputs['Color'], 2.0),
                       (1.0, 1.0, 1.0))
        # the atlas holds three.js object-space normals: (x, y, z) -> Blender object (x, -z, y), then to world
        nx, ny, nz = g.sep(n_obj)
        vt = g.node('ShaderNodeVectorTransform', vector_type='NORMAL', convert_from='OBJECT', convert_to='WORLD')
        g.link(g.comb(nx, g.neg(nz), ny), vt.inputs['Vector'])
        n_w = g.vnorm(vt.outputs['Vector'])
    else:
        n_w = g.node('ShaderNodeNewGeometry').outputs['Normal']
    lit = g.add(g.mul(g.max(g.vdot(n_w, k['sun_dir']), 0.0), 0.92), 0.08)
    col = g.vscale(g.vmul(alb, k['sun_col']), g.mul(lit, k['gain']))
    out = g.node('ShaderNodeOutputMaterial')
    g.link(_emission(g, col), out.inputs['Surface'])
    ob.data.materials.clear()
    ob.data.materials.append(m)
    return m


# ------------------------------------------------------------------------------------------ debris river ---

def _octahedron():
    me = bpy.data.meshes.get('eido_moon_speck_octahedron')
    if me is None:
        me = bpy.data.meshes.new('eido_moon_speck_octahedron')
        v = [(1, 0, 0), (-1, 0, 0), (0, 1, 0), (0, -1, 0), (0, 0, 1), (0, 0, -1)]
        f = [(0, 2, 4), (2, 1, 4), (1, 3, 4), (3, 0, 4), (2, 0, 5), (1, 2, 5), (3, 1, 5), (0, 3, 5)]
        me.from_pydata(v, [], f)
        me.update()
    return me


def speck_system(moon, scene):
    """The debris river as one point mesh with each grain's seeds as attributes and a Geometry Nodes tree that
    evaluates ShatteredMoon's update() formulas at Scene Time: free grains stream along the line and wrap at the
    span's ends; 30% orbit a parent fragment whose drift the tree evaluates too (Eanpa's motion, analytic)."""
    from .asteroid_moon import _h, SPECK_N
    fm = moon.motion
    hero_r = moon.hero_r
    arc_x = moon.arc_x
    n = SPECK_N
    seeds = {}
    cols = dict(x0=[], lane=[], yoff=[], zoff=[], s=[], v=[], wob=[], spin=[], near=[], orb_r=[], orb_ph=[],
                orb_w=[])
    for i in range(n):
        a, b, c, d, e = _h(i, 41), _h(i, 42), _h(i, 43), _h(i, 44), _h(i, 45)
        near = math.floor(_h(i, 47) * 16) if _h(i, 46) < 0.30 else -1
        cols['x0'].append((a * 2 - 1) * arc_x * 1.15)
        cols['lane'].append(math.floor(b * 3) * 2.1 + _h(i, 48) * 0.6)
        cols['yoff'].append((d - 0.5) * hero_r * 0.85)
        cols['zoff'].append((_h(i, 49) - 0.5) * hero_r * 1.1)
        cols['s'].append(hero_r * (0.007 + 0.030 * c ** 5))
        cols['v'].append((0.008 + 0.020 * e) * hero_r)
        cols['wob'].append(_h(i, 50) * math.pi * 2)
        cols['spin'].append(0.3 + _h(i, 51) * 1.4)
        cols['near'].append(near if near < len(fm.radii) else -1)
        cols['orb_r'].append(hero_r * (0.5 + _h(i, 52) * 1.6))
        cols['orb_ph'].append(_h(i, 53) * math.pi * 2)
        cols['orb_w'].append(0.02 + _h(i, 54) * 0.05)
    # each grain carries its parent's drift: position(t) = pb + pu cos(ph + t f) + pv sin(ph + t f) (three.js)
    pb, pu, pv, pph, pf = [], [], [], [], []
    for i in range(n):
        k = cols['near'][i]
        if k < 0:
            pb.append((0, 0, 0)), pu.append((0, 0, 0)), pv.append((0, 0, 0)), pph.append(0.0), pf.append(0.0)
            continue
        m = fm.motion[k]
        amp = fm.amplitudes[k]
        pb.append(fm.base_positions[k])
        pu.append(tuple(c * amp for c in m['u']))
        pv.append(tuple(c * amp * 0.6 for c in m['v']))
        pph.append(m['phase'])
        pf.append(m['frequency'])
    me = bpy.data.meshes.new('eido_moon_specks')
    me.vertices.add(n)
    me.vertices.foreach_set('co', np.zeros(n * 3, np.float32))
    for key, vals in cols.items():
        at = me.attributes.new(key, 'FLOAT', 'POINT')
        at.data.foreach_set('value', np.array(vals, np.float32))
    to_b = lambda t: (t[0], -t[2], t[1])
    for key, vals in (('pb', pb), ('pu', pu), ('pv', pv)):
        at = me.attributes.new(key, 'FLOAT_VECTOR', 'POINT')
        at.data.foreach_set('vector', np.array([to_b(v) for v in vals], np.float32).ravel())
    for key, vals in (('pph', pph), ('pf', pf)):
        at = me.attributes.new(key, 'FLOAT', 'POINT')
        at.data.foreach_set('value', np.array(vals, np.float32))
    ob = bpy.data.objects.new('eido_moon_specks', me)
    moon.collection.objects.link(ob)
    ob.parent = moon.group
    ob.visible_shadow = False
    oct_ob = bpy.data.objects.get('eido_moon_speck_octahedron')
    if oct_ob is None:
        oct_ob = bpy.data.objects.new('eido_moon_speck_octahedron', _octahedron())
        moon.collection.objects.link(oct_ob)
        oct_ob.hide_render = True
        oct_ob.hide_viewport = True
        oct_ob.parent = moon.group
    oct_ob.data.materials.clear()
    oct_ob.data.materials.append(speck_material())
    mod = ob.modifiers.new('eido_debris_river', 'NODES')
    mod.node_group = _speck_tree(oct_ob, scene, span=arc_x * 1.3, hero_r=hero_r)
    return ob


def _speck_tree(oct_ob, scene, span, hero_r):
    """Geometry Nodes: the JS speck update(t) per point, then octahedra instanced, rotated and scaled."""
    name = 'eido_moon_debris_river'
    old = bpy.data.node_groups.get(name)
    if old:
        bpy.data.node_groups.remove(old)
    ng = bpy.data.node_groups.new(name, 'GeometryNodeTree')
    ng.interface.new_socket('Geometry', in_out='INPUT', socket_type='NodeSocketGeometry')
    ng.interface.new_socket('Geometry', in_out='OUTPUT', socket_type='NodeSocketGeometry')
    N, L = ng.nodes, ng.links
    gi, go = N.new('NodeGroupInput'), N.new('NodeGroupOutput')
    fps = scene.render.fps / scene.render.fps_base
    fs = float(scene.frame_start)
    col = [0]

    def node(kind, **props):
        nd = N.new(kind)
        nd.location = (col[0] * 160, 0)
        col[0] += 1
        for k_, v_ in props.items():
            setattr(nd, k_, v_)
        return nd

    def setin(sock, v):
        if isinstance(v, bpy.types.NodeSocket):
            L.new(v, sock)
        elif isinstance(v, (tuple, list)):
            sock.default_value = v
        else:
            sock.default_value = float(v)

    def m(op, a, b=None, c=None):
        nd = node('ShaderNodeMath', operation=op)
        for i, v in enumerate((a, b, c)):
            if v is not None:
                setin(nd.inputs[i], v)
        return nd.outputs[0]

    def vm(op, a, b=None, scale=None):
        nd = node('ShaderNodeVectorMath', operation=op)
        setin(nd.inputs[0], a)
        if b is not None:
            setin(nd.inputs[1], b)
        if scale is not None:
            setin(nd.inputs['Scale'], scale)
        return nd.outputs['Vector']

    def attr(nm, typ='FLOAT'):
        nd = node('GeometryNodeInputNamedAttribute', data_type=typ)
        nd.inputs['Name'].default_value = nm
        return nd.outputs['Attribute']

    def comb(x, y, z):
        nd = node('ShaderNodeCombineXYZ')
        setin(nd.inputs[0], x)
        setin(nd.inputs[1], y)
        setin(nd.inputs[2], z)
        return nd.outputs[0]

    st = node('GeometryNodeInputSceneTime')
    t = m('DIVIDE', m('SUBTRACT', st.outputs['Frame'], fs), fps)
    # free grains: x = wrap(x0 + v t) into [-SPAN, SPAN); lanes y, z are sines of x (three.js), Blender (x, -z, y)
    x = m('ADD', attr('x0'), m('MULTIPLY', attr('v'), t))
    x = m('SUBTRACT', m('FLOORED_MODULO', m('ADD', x, span), 2 * span), span)
    lane = attr('lane')
    y3 = m('ADD', m('MULTIPLY', m('SINE', m('ADD', m('MULTIPLY', x, 0.9 / hero_r), lane)), hero_r * 0.45), attr('yoff'))
    z3 = m('ADD', m('MULTIPLY', m('SINE', m('ADD', m('MULTIPLY', x, 0.6 / hero_r), m('MULTIPLY', lane, 1.7))),
                    hero_r * 0.5), attr('zoff'))
    free = comb(x, m('MULTIPLY', z3, -1.0), y3)
    # grains near a fragment: the parent's drift + an orbit (three.js offsets (cos th r, sin(.7 th + wob) r .45,
    # sin th r .6))
    ph = m('ADD', attr('pph'), m('MULTIPLY', t, attr('pf')))
    parent = vm('ADD', vm('ADD', attr('pb', 'FLOAT_VECTOR'), vm('SCALE', attr('pu', 'FLOAT_VECTOR'), scale=m('COSINE', ph))),
                vm('SCALE', attr('pv', 'FLOAT_VECTOR'), scale=m('SINE', ph)))
    th = m('ADD', attr('orb_ph'), m('MULTIPLY', t, attr('orb_w')))
    orb_r = attr('orb_r')
    ox = m('MULTIPLY', m('COSINE', th), orb_r)
    oy3 = m('MULTIPLY', m('SINE', m('ADD', m('MULTIPLY', th, 0.7), attr('wob'))), m('MULTIPLY', orb_r, 0.45))
    oz3 = m('MULTIPLY', m('SINE', th), m('MULTIPLY', orb_r, 0.6))
    orbit = vm('ADD', parent, comb(ox, m('MULTIPLY', oz3, -1.0), oy3))
    is_near = m('GREATER_THAN', attr('near'), -0.5)
    sw = node('GeometryNodeSwitch', input_type='VECTOR')
    L.new(is_near, sw.inputs['Switch'])
    L.new(free, sw.inputs['False'])
    L.new(orbit, sw.inputs['True'])
    sp = node('GeometryNodeSetPosition')
    L.new(gi.outputs['Geometry'], sp.inputs['Geometry'])
    L.new(sw.outputs['Output'], sp.inputs['Position'])
    oi = node('GeometryNodeObjectInfo', transform_space='ORIGINAL')
    oi.inputs['Object'].default_value = oct_ob
    if 'As Instance' in oi.inputs:
        oi.inputs['As Instance'].default_value = False
    iop = node('GeometryNodeInstanceOnPoints')
    L.new(sp.outputs['Geometry'], iop.inputs['Points'])
    L.new(oi.outputs['Geometry'], iop.inputs['Instance'])
    # tumble: axis (0.42, 0.75, 0.51) three.js -> Blender (0.42, -0.51, 0.75), angle wob + t spin
    ax = (0.42, 0.75, 0.51)
    nrm = math.sqrt(sum(c * c for c in ax))
    axb = (ax[0] / nrm, -ax[2] / nrm, ax[1] / nrm)
    aa = node('FunctionNodeAxisAngleToRotation')
    aa.inputs['Axis'].default_value = axb
    L.new(m('ADD', attr('wob'), m('MULTIPLY', t, attr('spin'))), aa.inputs['Angle'])
    L.new(aa.outputs['Rotation'], iop.inputs['Rotation'])
    s = attr('s')
    L.new(comb(s, s, s), iop.inputs['Scale'])
    L.new(iop.outputs['Instances'], go.inputs['Geometry'])     # the octahedron mesh carries the speck material
    return ng
