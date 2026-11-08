"""ocean/_sea_nodes.py: the sea's two node graphs, built from sea.SeaMath (the TSL of sea.js as node expressions).

    displace_group(tables, radius)        Geometry Nodes: sea.js positionNode (swells + the faces' relief) and the
                                          'rest' attribute (the undisplaced position, sea.js positionGeometry)
    sea_material(atlas, tables, radius)   the unlit material: sea.js colorNode, emitted
"""

from __future__ import annotations

import math

import bpy

from ._nodes import NB, E, new_tree, clear_material
from .sea import SeaMath, UNIFORMS, VECTOR_UNIFORMS, RIPPLES, G, N_ATLAS, ATLAS_LEVELS, GOLD, AMBER, ROSE, AQUA


# ------------------------------------------------------------------------------------------------- vertex stage
def displace_group(tables, radius=1500.0, name='ocean_sea_displace'):
    tree, gi, go = new_tree(name, 'GeometryNodeTree',
                            inputs=[('Geometry', 'NodeSocketGeometry'), ('Time', 'NodeSocketFloat', 0.0),
                                    ('Reveal', 'NodeSocketFloat', 0.0), ('Relief', 'NodeSocketFloat', 1.0),
                                    ('Calm', 'NodeSocketFloat', 1.0)],
                            outputs=[('Geometry', 'NodeSocketGeometry')])
    nb = NB(tree)
    pos = nb.node('GeometryNodeInputPosition')
    x, y, _z = nb.separate(pos.outputs[0])
    px, pz = x, -y                                             # three's design (x, z)
    shore = nb.attr('shore')
    t = E(nb, gi.outputs['Time'])
    U = {'reveal': E(nb, gi.outputs['Reveal']), 'relief': E(nb, gi.outputs['Relief'])}
    M = SeaMath(nb, U, tables, radius)
    damp = nb.smoothstep(0.0, 9.0, shore) * E(nb, gi.outputs['Calm'])
    sw = M.swell(px, pz, t, damp)
    c = M.cell_of(px, pz)
    fh, _ = M.relief(c, sw, t, nb.smoothstep(0.5, 6.0, shore), False)
    dx, dy, dz = sw['disp']
    new = nb.combine(px + dx, -(pz + dz), dy + fh)
    store = nb.node('GeometryNodeStoreNamedAttribute', data_type='FLOAT_VECTOR', domain='POINT')
    store.hide = False
    store.inputs['Name'].default_value = 'rest'
    tree.links.new(gi.outputs['Geometry'], store.inputs['Geometry'])
    tree.links.new(pos.outputs[0], store.inputs['Value'])
    setp = nb.node('GeometryNodeSetPosition')
    setp.hide = False
    tree.links.new(store.outputs['Geometry'], setp.inputs['Geometry'])
    tree.links.new(new, setp.inputs['Position'])
    tree.links.new(setp.outputs['Geometry'], go.inputs['Geometry'])
    return tree


# ------------------------------------------------------------------------------------------------- fragment stage
def _vt(nb, vec, frm, to, kind='VECTOR'):
    n = nb.node('ShaderNodeVectorTransform', vector_type=kind, convert_from=frm, convert_to=to)
    nb.link(vec, n.inputs['Vector'])
    return nb.separate(n.outputs['Vector'])


def _px_angle_driver(mat, node_name, scene):
    """The camera's angle per pixel (vertical): 2 tan(fov_y / 2) / rendered height, read live from the scene camera."""
    fc = mat.node_tree.driver_add(f'nodes["{node_name}"].outputs[0].default_value')
    d = fc.driver
    d.type = 'SCRIPTED'
    for v in list(d.variables):
        d.variables.remove(v)
    for vn, path in (('fov', 'camera.data.angle_y'), ('h', 'render.resolution_y'), ('p', 'render.resolution_percentage')):
        v = d.variables.new()
        v.name = vn
        v.type = 'SINGLE_PROP'
        v.targets[0].id_type = 'SCENE'
        v.targets[0].id = scene
        v.targets[0].data_path = path
    d.expression = '2*tan(fov/2)/max(h*p/100, 1)'
    return fc


def _uniform_values(mat, nb, owner):
    """The uniforms as Value nodes driven by the owner's custom properties (one per component). Drivers, not Attribute
    (Object) nodes: a material reads only a handful of object attributes (GPU_MAX_UNIFORM_ATTR), and the sea has 16."""
    U = {}
    for k, v in UNIFORMS.items():
        comps = range(3) if k in VECTOR_UNIFORMS else (None,)
        vals = []
        for i in comps:
            label = f'U_{k}' + ('' if i is None else f'_{i}')
            val = nb.value(v if i is None else v[i], label=label)
            fc = mat.node_tree.driver_add(f'nodes["{label}"].outputs[0].default_value')
            d = fc.driver
            d.type = 'SCRIPTED'
            for old in list(d.variables):
                d.variables.remove(old)
            var = d.variables.new()
            var.name = 'x'
            var.type = 'SINGLE_PROP'
            var.targets[0].id_type = 'OBJECT'
            var.targets[0].id = owner
            var.targets[0].data_path = f'["{k}"]' + ('' if i is None else f'[{i}]')
            d.expression = 'x'
            vals.append(val)
        U[k] = tuple(vals) if k in VECTOR_UNIFORMS else vals[0]
    return U


def sea_material(atlas, tables, radius=1500.0, name='ocean_of_faces', scene=None, lod_bias=-0.25, owner=None):
    """owner: the object whose custom properties are the uniforms (the sea mesh)."""
    mat = bpy.data.materials.get(name) or bpy.data.materials.new(name)
    mat.use_nodes = True
    nt, out = clear_material(mat)
    nb = NB(nt)
    rest = nb.attr('rest', 'GEOMETRY', 'Vector')
    px, pz = rest[0], -rest[1]
    shoreD = nb.attr('shore', 'GEOMETRY')
    U = _uniform_values(mat, nb, owner)
    t = U['t']
    M = SeaMath(nb, U, tables, radius)
    damp = nb.smoothstep(0.0, 9.0, shoreD) * U['calm']
    fdamp = nb.smoothstep(0.5, 6.0, shoreD)
    sw = M.swell(px, pz, t, damp)
    c = M.cell_of(px, pz)
    _h, g = M.relief(c, sw, t, fdamp, True)
    nL = [sw['n'][0] - g[0], sw['n'][1], sw['n'][2] - g[1]]
    # glitter ripples, faded with distance so they never alias into crawl
    geo = nb.node('ShaderNodeNewGeometry')
    P = nb.separate(geo.outputs['Position'])
    Vd = nb.separate(geo.outputs['Incoming'])
    cam = nb.node('ShaderNodeCameraData')
    dist = E(nb, cam.outputs['View Distance'])
    ripK = nb.smoothstep(260.0, 25.0, dist)
    rx = rz = 0.0
    for dx, dz, lam, a in RIPPLES:
        n = math.hypot(dx, dz)
        k = 2 * math.pi / lam
        om = math.sqrt(G * k)
        th = (nb.s(px) * (dx / n) + pz * (dz / n)) * k - t * om
        cc = nb.cos(th) * (a * k)
        rx = rx + cc * (dx / n)
        rz = rz + cc * (dz / n)
    rx, rz = nb.s(rx), nb.s(rz)
    nL = [nL[0] - rx * ripK, nL[1], nL[2] - rz * ripK]
    nW = nb.vnorm(_vt(nb, (nL[0], -nL[2], nL[1]), 'OBJECT', 'WORLD', 'NORMAL'))   # three local -> Blender -> world
    cosV = nb.max(nb.vdot(nW, Vd), 0.0)
    om5 = 1.0 - cosV
    F = 0.02 + (om5 * om5) * (om5 * om5) * om5 * 0.98
    VdotN = nb.vdot(Vd, nW)
    Rr = tuple(-nb.s(Vd[i]) + nW[i] * (VdotN * 2.0) for i in range(3))            # reflect(-Vd, nW)
    # the night sky seen in the water: the palette gradient + the moon's halo and disc glint
    ry = nb.max(Rr[2], 0.0)
    sky = nb.mix(U['hor'], U['zen'], nb.pow(ry, 0.5))
    md = nb.max(nb.vdot(Rr, U['moonW']), 0.0)
    moonGl = nb.pow(md, 2600.0) * 2.4 + nb.pow(md, 220.0) * 0.05 + nb.pow(md, 16.0) * 0.012
    mk = moonGl * U['moonI'] * (F * 0.6 + 0.4)
    col = [sky[i] * F + U['moonCol'][i] * mk for i in range(3)]
    # the water body: near-black blue, lifted a touch on crests facing the moon
    lift = nb.max(sw['disp'][1], 0.0) * 0.02
    body = [b + U['moonCol'][i] * lift for i, b in enumerate((0.0016, 0.0048, 0.0085))]
    col = [col[i] + body[i] * (1.0 - F) for i in range(3)]

    # ---- the screen footprint (sea.js's dFdx/dFdy of the continuous cell coordinates), for the atlas LOD
    pxa = nb.value(0.001, label='px_angle')
    _px_angle_driver(mat, pxa.v.node.name, scene or bpy.context.scene)
    R = _vt(nb, (1.0, 0.0, 0.0), 'CAMERA', 'WORLD')
    Up = _vt(nb, (0.0, 1.0, 0.0), 'CAMERA', 'WORLD')
    D = tuple(-nb.s(v) for v in Vd)
    Dz = nb.min(D[2], -0.02)
    k = dist * pxa
    dPx = _vt(nb, tuple((nb.s(R[i]) - D[i] * (R[2] / Dz)) * k for i in range(3)), 'WORLD', 'OBJECT')
    dPy = _vt(nb, tuple((nb.s(Up[i]) - D[i] * (Up[2] / Dz)) * k for i in range(3)), 'WORLD', 'OBJECT')
    dPx3, dPy3 = (dPx[0], -nb.s(dPx[1])), (dPy[0], -nb.s(dPy[1]))           # three (x, z)

    def lod(cc, extra=0.0):
        ir2 = 1.0 / cc['r2']
        gs = (-nb.s(cc['pz']) * ir2 * (cc['rRow'] / cc['W']), nb.s(cc['px']) * ir2 * (cc['rRow'] / cc['W']))
        gv = (nb.s(cc['px']) * ir2 * (1.0 / cc['DL']), nb.s(cc['pz']) * ir2 * (1.0 / cc['DL']))
        dsx = gs[0] * dPx3[0] + gs[1] * dPx3[1]
        dvx = gv[0] * dPx3[0] + gv[1] * dPx3[1]
        dsy = gs[0] * dPy3[0] + gs[1] * dPy3[1]
        dvy = gv[0] * dPy3[0] + gv[1] * dPy3[1]
        tex = 256.0 * cc['isc']                                # face units -> level-0 texels (2048 / N)
        ax = nb.sqrt(dsx * dsx + dvx * dvx) * tex
        ay = nb.sqrt(dsy * dsy + dvy * dvy) * tex
        Lg = nb.log(nb.max(ax * ay, 1e-12)) * (0.5 / math.log(2.0)) + (extra + lod_bias)
        return nb.clamp(Lg, 0.0, float(ATLAS_LEVELS - 1))

    def sample_atlas(u, v, Lv):
        acc = [0.0, 0.0, 0.0]
        for i, img in enumerate(atlas):
            w = nb.max(1.0 - nb.abs(Lv - float(i)), 0.0)
            r_, g_, b_, _a = nb.image(img, u, v, interpolation='Cubic', extension='EXTEND')
            acc = [acc[0] + r_ * w, acc[1] + g_ * w, acc[2] + b_ * w]
        return acc

    # ---- the faces' light, rising through the surface as they surface
    N = N_ATLAS
    inside = nb.step(nb.max(nb.abs(c['x']), nb.abs(c['y'])), 0.5)
    kk = nb.floor(c['h1'] * (N * N * 0.999))
    ay_ = nb.floor(kk * (1.0 / N))
    ax_ = kk - ay_ * N
    rk = ripK * (0.05) * c['isc']
    cxr = nb.clamp(c['x'] + rx * rk, -0.5, 0.5)
    cyr = nb.clamp(c['y'] + rz * rk, -0.5, 0.5)
    A = sample_atlas((ax_ + cxr + 0.5) * (1.0 / N), (ay_ + cyr + 0.5) * (1.0 / N), lod(c))
    em = M.crest_k(sw, c, t) * M.reveal_k(c['r']) * fdamp * inside
    hue = c['h2']
    tint = nb.mix(nb.mix(nb.mix(GOLD, AMBER, nb.smoothstep(0.35, 0.55, hue)), ROSE, nb.smoothstep(0.78, 0.86, hue)),
                  AQUA, nb.smoothstep(0.91, 0.96, hue))
    lines = A[0] + A[1] * 0.45 + A[2] * 0.05
    far = nb.exp(c['r'] * (-1.0 / 520.0)) * 0.7 + 0.3
    wave = M.reveal_wave(c['r'])
    kf = lines * em * U['glow'] * far * (1.0 - F * 0.6) * (wave * 1.6 + 1.0) * 0.62
    col = [col[i] + tint[i] * kf for i in range(3)]
    kw = wave * fdamp * 0.035 * (1.0 - F * 0.5)
    col = [col[i] + v * kw for i, v in enumerate((1.0, 0.7, 0.36))]

    # ---- the deep: older, larger faces far below, seen through the water (parallax, blurred, cold)
    VdL = nb.vnorm(_vt(nb, Vd, 'WORLD', 'OBJECT'))
    VdLx, VdLy, VdLz = VdL[0], VdL[2], -nb.s(VdL[1])                               # three local
    kd = 1.7 / nb.max(VdLy, 0.12)
    pdx, pdz = nb.s(px) - VdLx * kd, nb.s(pz) - VdLz * kd
    cd = M.cell_of(pdx, pdz, 'deep')
    kkd = nb.floor(cd['h1'] * (N * N * 0.999))
    ayd = nb.floor(kkd * (1.0 / N))
    axd = kkd - ayd * N
    # sea.js takes dFdx / dFdy of the SHIFTED cell coordinates, so the parallax's own change across a pixel blurs the
    # deep too: on the water plane pd = p (1 + 1.7 / h) about the camera's foot (h its height over the point; beyond
    # the 0.12 clamp the same law with h = dist x 0.12), so its footprint is the surface's x (1 + 1.7 / h)
    kpd = 1.0 + 1.7 / nb.max(dist * nb.max(VdLy, 0.12), 1e-3)
    Dp = sample_atlas((axd + nb.clamp(cd['x'], -0.5, 0.5) + 0.5) * (1.0 / N),
                      (ayd + nb.clamp(cd['y'], -0.5, 0.5) + 0.5) * (1.0 / N),
                      lod(cd, nb.log(kpd) * (1.0 / math.log(2.0)) + math.log2(3.5)))
    insideD = nb.step(nb.max(nb.abs(cd['x']), nb.abs(cd['y'])), 0.5) * cd['present']
    breathe = nb.sin(t * 0.45 + cd['h4'] * 6.28) * 0.35 + 0.65
    deepI = (Dp[1] * 0.8 + Dp[2] * 0.3) * insideD * breathe * M.reveal_k(cd['r']) * fdamp * (1.0 - F) \
        * nb.exp(cd['r'] * (-1.0 / 160.0))
    kdp = deepI * U['glow'] * 0.2
    col = [col[i] + v * kdp for i, v in enumerate((0.16, 0.46, 0.6))]

    # ---- the porch light and the window, glinting on the cove (zero until they are lit)
    def glint(Wp, kind):
        Lv = tuple(nb.s(Wp[i]) - P[i] for i in range(3))
        dl = nb.vlen(Lv)
        Ln = tuple(v / nb.max(dl, 1e-6) for v in Lv)
        H = nb.vnorm(tuple(Ln[i] + Vd[i] for i in range(3)))
        nh = nb.max(nb.vdot(nW, H), 0.0)
        att = 1.0 / (dl * dl * 0.012 + 1.0)
        if kind == 'porch':
            return (nb.pow(nh, 700.0) * 40.0 + nb.pow(nh, 60.0) * 0.25) * att
        return nb.pow(nh, 350.0) * 10.0 * att
    gp = glint(U['porchW'], 'porch') * U['porch']
    col = [col[i] + U['porchCol'][i] * gp for i in range(3)]
    gw = glint(U['winW'], 'win') * U['win']
    col = [col[i] + v * gw for i, v in enumerate((1.0, 0.72, 0.42))]

    # ---- the waterline: foam that runs up and slides back on the swell (only near the shore)
    swash = sw['s0'] * 0.55
    sd_ = shoreD + swash
    foamBand = nb.smoothstep(1.3, 0.15, sd_) * nb.smoothstep(-0.6, 0.1, sd_)
    fn = nb.noise3(nb.s(px) * 2.2, nb.s(pz) * 2.2, t * 0.35)
    foam = (foamBand * nb.smoothstep(0.45, 0.8, fn) * 0.55 + foamBand * 0.08) * nb.lt(shoreD, 2.2)
    col = [nb.mix(col[i], U['moonCol'][i] * 0.05, foam) for i in range(3)]

    # ---- distance haze into the night horizon
    fk = (1.0 - nb.exp(-(dist * U['fog']))) * 0.92
    col = [nb.mix(col[i], U['hor'][i] * 1.05, fk) for i in range(3)]

    em_node = nb.node('ShaderNodeEmission')
    em_node.hide = False
    nb.link(tuple(col), em_node.inputs['Color'])
    em_node.inputs['Strength'].default_value = 1.0
    nt.links.new(em_node.outputs['Emission'], out.inputs['Surface'])
    mat.use_backface_culling = True
    if hasattr(mat, 'surface_render_method'):
        mat.surface_render_method = 'DITHERED'
    mat['eido_nodes'] = nb.count
    return mat
