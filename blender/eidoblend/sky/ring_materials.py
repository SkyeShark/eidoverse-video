"""The ringworld's materials: ringworld.js's TSL node graphs as Blender shader node graphs (Eanpa's newest form).

eido_ring_keys       the per-frame values the band's engine-owned update() writes (keyed, LINEAR)
eido_ring_eclipse    ringSolarVisibilityNode: the band's own solar visibility at a point (Eanpa ring_eclipse.js), the
                     opposite arc eclipsing the sun with a penumbra as wide as the sun's disc
eido_ring_arc_shade  arcShade(): the arc's terminator (eclipsed per pixel), golden warm band, planetshine visibility,
                     per-channel transmittance over the height-integrated optical length (8 km scale height), the
                     sub-cloud rain veil with its drifting curtains, the inscatter that collapses at night and under the
                     eclipse, and the foot veil that dissolves the seam at the horizon
band / walls / cloud sheet / haze walls: the materials, each line named after its JS term.
Coordinates: Blender world space (Z up); a three.js constant direction (x, y, z) appears here as (x, -z, y). Every
ring object is translation-only, so its object space is world space about the ring axis.
"""
import math

import bpy

from .nodes import Graph, new_group, keyed_values_group, vnoise2_group, vnoise2_rep_group
from .sky_view import overlay_opaque, blended_surface

KEYS = 'eido_ring_keys'
ARC = 'eido_ring_arc_shade'
ECLIPSE = 'eido_ring_eclipse'
R_REF = 5000.0
HALF_WIDTH = 483.0
SUN_ANGULAR_RADIUS = 0.00465
LUMA = (0.2126, 0.7152, 0.0722)


def opt_on(o, key, default=True):
    """A boolean ringworld option: False, 0, 'false', 'off' and 'no' turn it off; None keeps the default."""
    v = o.get(key)
    if v is None:
        return default
    if isinstance(v, str):
        return v.strip().lower() not in ('0', 'false', 'off', 'no', '')
    return bool(v)


def ring_keys_group(ring):
    c = ring.band.matrix_world.translation
    vals = dict(sun_dir=(0.0, 0.0, 1.0), moon_dir=(0.0, 0.0, 1.0), day_f=1.0, gain=1.0, sun_col=(1.0, 1.0, 1.0),
                haze=(0.55, 0.62, 0.72), rain_haze=0.0, time=0.0, insc_night=1.0, veil=1.0, foot_w=0.022,
                cover=0.45, grey=0.0, dens=1.0, tint_sun=(1.0, 0.97, 0.9), tint_amb=(0.72, 0.78, 0.9), rad=1.0,
                disp=(0.0, 0.0, 0.0), center=(c.x, c.y, c.z))
    return keyed_values_group(KEYS, vals)


def _keys(g):
    return g.group(bpy.data.node_groups[KEYS]).outputs


def eclipse_group():
    """eido_ring_eclipse(Position, Sun, Center) -> Visibility: Eanpa ringSolarVisibilityNode, in Blender space.

    The dot products over (y, z) are the three.js ones unchanged ((x, y, z) -> (x, -z, y) keeps them), and the
    elevation is Blender z."""
    ng = bpy.data.node_groups.get(ECLIPSE)
    if ng is not None:
        return ng
    ng, gi, go = new_group(ECLIPSE, [('Position', 'NodeSocketVector'), ('Sun', 'NodeSocketVector'),
                                     ('Center', 'NodeSocketVector')], [('Visibility', 'NodeSocketFloat')])
    g = Graph(ng)
    px, py, pz = g.sep(g.vsub(gi.outputs['Position'], gi.outputs['Center']))
    sx, sy, sz = g.sep(gi.outputs['Sun'])
    a = g.max(g.add(g.mul(sy, sy), g.mul(sz, sz)), 1e-6)
    b = g.add(g.mul(py, sy), g.mul(pz, sz))
    c = g.sub(g.add(g.mul(py, py), g.mul(pz, pz)), R_REF * R_REF)
    disc = g.sub(g.mul(b, b), g.mul(a, c))
    inside = g.math('LESS_THAN', c, 2 * R_REF * max(0.001, R_REF * 1e-6) + 1e-6)      # c <= radialRoundoff(R)
    exit_d = g.div(g.add(g.neg(b), g.sqrt(g.max(disc, 0.0))), a)
    dist = g.max(exit_d, 0.0)
    across = g.abs(g.add(px, g.mul(sx, dist)))
    feather = g.max(g.div(g.mul(dist, math.tan(SUN_ANGULAR_RADIUS)), g.sqrt(a)), 1.0)
    visible = g.smoothstep(g.sub(HALF_WIDTH, feather), g.add(HALF_WIDTH, feather), across)
    # hit = inside or (disc >= 0 and exit >= 0)
    hit = g.max(inside, g.mul(g.step(0.0, disc), g.step(0.0, exit_d)))
    daylight = g.smoothstep(0.0, 0.05, sz)
    vis = g.lerp(1.0, visible, hit)                                    # select(hit, visible, 1)
    g.link(g.lerp(1.0, vis, daylight), go.inputs['Visibility'])
    return ng


def arc_shade_group():
    """eido_ring_arc_shade(Position) -> LitK, WarmT, PVis, Trans, Insc, Foot, FragD, Gain, DayF, Eclipse, DSun."""
    ng = bpy.data.node_groups.get(ARC)
    if ng is not None:
        return ng
    vn = vnoise2_group()
    ng, gi, go = new_group(ARC, [('Position', 'NodeSocketVector')],
                           [('LitK', 'NodeSocketFloat'), ('WarmT', 'NodeSocketVector'), ('PVis', 'NodeSocketFloat'),
                            ('Trans', 'NodeSocketVector'), ('Insc', 'NodeSocketVector'), ('Foot', 'NodeSocketFloat'),
                            ('FragD', 'NodeSocketFloat'), ('Gain', 'NodeSocketFloat'), ('DayF', 'NodeSocketFloat'),
                            ('Eclipse', 'NodeSocketFloat'), ('DSun', 'NodeSocketFloat')])
    g = Graph(ng)
    k = _keys(g)
    P = gi.outputs['Position']
    eclipse = g.group(eclipse_group(), Position=P, Sun=k['sun_dir'], Center=k['center']).outputs['Visibility']
    rel = g.vsub(P, k['center'])
    _rx, ry, rz = g.sep(rel)
    inward = g.vnorm(g.comb(0.0, g.neg(ry), g.neg(rz)))
    d_sun = g.vdot(inward, k['sun_dir'])
    lit_k = g.mul(g.smoothstep(-0.22, 0.30, d_sun), eclipse)                     # WIDE terminator, eclipsed
    warm_t = g.vlerp((1.14, 0.82, 0.55), (1.0, 1.0, 1.0), g.clamp(g.mul(d_sun, 2.0), 0.0, 1.0))
    p_vis = g.pow(g.smoothstep(-0.38, 0.48, g.vdot(inward, k['moon_dir'])), 0.8)  # planet-shine terminator
    geo = g.node('ShaderNodeNewGeometry')
    view_d = g.vscale(geo.outputs['Incoming'], -1.0)
    vx, vy, vz = g.sep(view_d)
    cam = g.node('ShaderNodeCameraData')
    frag_d = cam.outputs['View Distance']
    # transmittance over the height-integrated optical length (8 km scale height): a slant path through the
    # thinning air, not a flat-earth air mass
    elevation = g.max(vz, 1e-5)
    o_height = g.div(g.mul(elevation, frag_d), 8000.0)
    integral = g.div(g.mul(g.one_minus(g.exp(g.neg(o_height))), 8000.0), elevation)
    o_len = g.lerp(frag_d, integral, g.smoothstep(0.001, 0.005, o_height))
    trans0 = g.vexp_neg(g.vscale((0.000026, 0.000041, 0.000070), o_len))
    _ix, _iy, iz = g.sep(geo.outputs['Incoming'])
    _px, _py, pz = g.sep(P)
    cam_z = g.add(pz, g.mul(iz, frag_d))
    under_len = g.min(frag_d, g.div(g.clamp(g.sub(730.0, cam_z), 0.0, 1e5), g.max(vz, 0.02)))
    below_clouds = g.smoothstep(2200.0, 730.0, pz)
    c_d = g.mul(k['time'], 0.028)
    # RAIN CURTAINS: 2 octaves in view-direction space (three's viewD.xz = Blender (x, -y))
    nvy = g.neg(vy)
    q1 = g.comb(g.add(g.mul(vx, 6.0), c_d), g.add(g.mul(nvy, 6.0), g.mul(c_d, 0.3)), 0.0)
    q2 = g.comb(g.sub(g.mul(vx, 14.0), g.mul(c_d, 1.7)), g.mul(nvy, 14.0), 0.0)
    curt = g.add(g.mul(g.group(vn, P=q1).outputs['Value'], 0.65), g.mul(g.group(vn, P=q2).outputs['Value'], 0.35))
    rain_t = g.exp(g.neg(g.mul(g.mul(g.mul(under_len, k['rain_haze']), below_clouds),
                               g.mul(0.0018, g.add(g.mul(curt, 1.2), 0.4)))))
    trans = g.vscale(trans0, rain_t)
    veil = k['veil']
    one = (1.0, 1.0, 1.0)
    a = g.vscale(g.vmul(k['haze'], g.vsub(one, trans0)), g.mul(veil, rain_t))
    b = g.vscale(k['haze'], g.mul(g.mul(g.one_minus(rain_t), veil),
                                  g.mul(0.55, g.sub(1.08, g.mul(curt, 0.22)))))
    # NIGHT COLLAPSE of the inscatter, and its collapse under the eclipse
    insc = g.vscale(g.vadd(a, b), g.mul(k['insc_night'], g.lerp(0.12, 1.0, eclipse)))
    # FOOT VEIL, only on the band's true foot (faded in from 1.6 to 3.8 km)
    foot = g.mul(g.one_minus(g.smoothstep(0.0, k['foot_w'], vz)), g.smoothstep(1600.0, 3800.0, frag_d))
    for name, sock in (('LitK', lit_k), ('WarmT', warm_t), ('PVis', p_vis), ('Trans', trans), ('Insc', insc),
                       ('Foot', foot), ('FragD', frag_d), ('Gain', k['gain']), ('DayF', k['day_f']),
                       ('Eclipse', eclipse), ('DSun', d_sun)):
        g.link(sock, go.inputs[name])
    return ng


def _image(path, colorspace='Non-Color'):
    img = bpy.data.images.load(path, check_existing=True)
    img.colorspace_settings.name = colorspace
    return img


def _new_material(name, method='DITHERED'):
    m = bpy.data.materials.get(name)
    if m is not None:
        bpy.data.materials.remove(m)
    m = bpy.data.materials.new(name)
    m.use_nodes = True
    m.surface_render_method = method
    m.node_tree.nodes.clear()
    return m


def night_tint(o):
    """The band's night tint: opts.nightTint, else the planetshine colour held at the authored night luma 0.343."""
    nt = o.get('nightTint')
    if nt:
        return tuple(float(c) for c in nt)
    ps = o.get('planetShineColor')
    if ps and len(ps) == 3:
        lum = LUMA[0] * ps[0] + LUMA[1] * ps[1] + LUMA[2] * ps[2]
        s = 0.343 / max(lum, 1e-4)
        return tuple(c * s for c in ps)
    return (0.369, 0.339, 0.302)


def _basic_debug_band(ob):
    """debugBand='basic': a flat red standard material (bisects geometry and placement from the material graph)."""
    m = _new_material('eido_ring_band')
    g = Graph(m.node_tree)
    bsdf = g.node('ShaderNodeBsdfPrincipled')
    bsdf.inputs['Base Color'].default_value = (1.0, 0.0144, 0.0144, 1.0)        # 0xff2020, linear
    out = g.node('ShaderNodeOutputMaterial')
    g.link(bsdf.outputs[0], out.inputs['Surface'])
    ob.data.materials.clear()
    ob.data.materials.append(m)
    return m


def band_material(ring, ob, authored=False):
    """The TERRAIN. Lit band (the default): real albedo, roughness and normal under the band's own two lamps and the
    sky's light; the air's inscatter and foot veil in emission; night water glinting under planetshine.
    litBand=False: the analytic emissive path (litArc / nightSide / sparkle painted through emission, black albedo).
    authored: the GLB's own terrain mesh (geometryRelief=False), whose imported UVs are Blender-flipped in v."""
    A, o = ring.A, ring.opts
    debug = o.get('debugBand')
    if debug == 'basic':
        return _basic_debug_band(ob)
    lit_band = opt_on(o, 'litBand', True)
    m = _new_material('eido_ring_band')
    g = Graph(m.node_tree)
    k = _keys(g)
    arc = g.group(arc_shade_group(), Position=g.node('ShaderNodeNewGeometry').outputs['Position'])
    uvn = g.node('ShaderNodeUVMap', uv_map=ob.data.uv_layers.active.name if ob.data.uv_layers else 'UVMap')
    u, v_raw, _ = g.sep(uvn.outputs['UV'])
    vg = g.one_minus(v_raw) if authored else v_raw          # the glTF-convention v the JS uv() reads
    rep = float(ring.info['repeat'])
    u_t = g.mul(u, rep)
    img_uv = g.comb(u_t, g.one_minus(vg), 0.0)             # every map: Blender image space (uvF of the JS)
    land = g.image(ring.map_image, img_uv, label='band_albedo').outputs['Color']
    m_soft = g.image(_image(ring.mask_soft_path), img_uv, label='landmask_soft').outputs['Color']
    ms, _, _ = g.sep(m_soft)
    m_sel = ms if opt_on(o, 'waterWhite', False) else g.one_minus(ms)
    kw = g.smoothstep(0.30, 0.70, m_sel)                                       # water = landmask BLACK
    shore = g.clamp(g.one_minus(g.mul(g.abs(g.sub(kw, 0.5)), 2.0)), 0.0, 1.0)  # WET SHORE
    vn = vnoise2_group()
    drift = g.mul(k['time'], 0.012)
    s1 = g.group(vn, P=g.comb(g.add(g.mul(u, 900.0), drift), g.add(g.mul(vg, 30.0), g.mul(drift, 0.7)), 0.0))
    s2 = g.group(vn, P=g.comb(g.sub(g.mul(u, 1700.0), g.mul(drift, 1.6)), g.sub(g.mul(vg, 56.0), drift), 0.0))
    shim_raw = g.mul(g.add(s1.outputs['Value'], s2.outputs['Value']), 0.5)
    far_k = g.smoothstep(2500.0, 9000.0, arc.outputs['FragD'])
    shim = g.lerp(shim_raw, 0.5, far_k)
    s8 = g.pow(shim, 8.0)
    water_col = g.vadd(g.vlerp((0.020, 0.042, 0.055), (0.055, 0.10, 0.115), shim), g.comb(*(g.mul(s8, 0.3),) * 3))
    albedo = g.vlerp(land, water_col, kw)
    albedo = g.vscale(albedo, g.one_minus(g.mul(shore, float(o.get('shoreWetness', 0.20)))))
    night_ao = None
    if A.get('bandAO'):
        ao_n = g.image(_image(A['bandAO']), img_uv, label='band_ao')
        ao_s = ao_n.outputs['Alpha'] if opt_on(o, 'bandAOPackedNormal', False) else g.sep(ao_n.outputs['Color'])[0]
        ao_k = g.lerp(g.lerp(float(o.get('bandAOFloor', 0.62)), 1.06, ao_s), 1.0, kw)  # baked cavity AO, land only
        albedo = g.vscale(albedo, ao_k)
        night_ao = g.lerp(g.mul(g.mul(ao_s, ao_s), 1.15), 1.0, kw)              # deeper valleys under moonlight
    rough = g.clamp(g.sub(g.lerp(0.95, g.add(0.07, g.mul(shim, 0.16)), kw), g.mul(shore, 0.34)), 0.05, 1.0)
    # ---- the analytic cylinder frame (Eanpa: object space is world space for the translation-only band) ----
    tco = g.node('ShaderNodeTexCoord')
    ox, oy, oz = g.sep(tco.outputs['Object'])
    geo = g.node('ShaderNodeNewGeometry')
    if opt_on(o, 'analyticBandNormal', True):
        nn = g.vnorm(g.comb(0.0, g.neg(oy), g.neg(oz)))                        # inner-surface normal
    else:
        nn = geo.outputs['Normal']                                             # the mesh's own normals
    t_n = g.vnorm(g.comb(0.0, g.neg(oz), oy))                                  # three's Tn: -u around the ring
    tv = (1.0, 0.0, 0.0)                                                       # Bn: across the band
    nsc = float(o.get('bandNormalScale', 1.4))
    have_nm = bool(A.get('bandNormal'))
    if have_nm:
        nm = g.image(_image(A['bandNormal']), img_uv, label='band_normal').outputs['Color']
        nx, ny, nz = g.sep(g.vsub(g.vscale(nm, 2.0), (1.0, 1.0, 1.0)))
        # landV = (-x NSC, -y NSC, z) in (Tn, Bn, Nn): both texture axes oppose the analytic frame
        land_n = g.vnorm(g.vadd(g.vadd(g.vscale(t_n, g.mul(nx, -nsc)), g.vscale(tv, g.mul(ny, -nsc))),
                                g.vscale(nn, nz)))
    else:
        land_n = nn
    lb0, lb1 = ring.info.get('localReliefBlend', (0.0, 0.0))
    if lb1 > lb0:
        arc_d = g.mul(g.abs(g.atan2(g.neg(oy), g.neg(oz))), R_REF)
        land_n = g.vnorm(g.vlerp(nn, land_n, g.smoothstep(float(lb0), float(lb1), arc_d)))
    waves = o.get('waves', 'lightweight')
    wave_mode = 'off' if waves is False or waves in ('off', 'false', 0) else (
        'lightweight' if waves == 'lightweight' else 'full')
    surface_n = land_n
    water_night = None
    wave_slope = None
    if wave_mode == 'lightweight' and have_nm:
        wc = g.mul(k['time'], float(o.get('lightweightWaveSpeed', 0.0065)))
        wimg = _image(A.get('waterWaveNormal') or A['bandNormal'])
        w0 = g.image(wimg, g.comb(g.add(g.mul(u_t, 28.0), wc),
                                  g.add(g.mul(g.one_minus(vg), 7.0), g.mul(wc, 0.31)), 0.0),
                     label='wave0').outputs['Color']
        w1 = g.image(wimg, g.comb(g.add(g.sub(g.mul(u_t, 44.0), g.mul(wc, 1.37)), 0.37),
                                  g.add(g.sub(g.mul(g.one_minus(vg), 11.0), g.mul(wc, 0.53)), 0.61), 0.0),
                     label='wave1').outputs['Color']
        w0x, w0y, _ = g.sep(g.vsub(g.vscale(w0, 2.0), (1.0, 1.0, 1.0)))
        w1x, w1y, _ = g.sep(g.vsub(g.vscale(w1, 2.0), (1.0, 1.0, 1.0)))
        amp = g.mul(g.mul(float(o.get('lightweightWaveAmp', 0.26)), g.lerp(1.0, 0.42, far_k)),
                    g.add(g.mul(shim_raw, 0.18), 0.87))
        wave_slope = (g.mul(g.add(w0x, g.mul(w1y, 0.52)), amp), g.mul(g.sub(w0y, g.mul(w1x, 0.52)), amp))
    elif wave_mode == 'full':
        # the full procedural field (offline look-dev): two tileable value-noise octaves, finite differences
        vr = vnoise2_rep_group()
        w_spd = g.mul(k['time'], 1.2)
        q1 = (g.mul(u, 12320.0), g.mul(vg, 385.0))
        q2 = (g.mul(u, 24640.0), g.mul(vg, 770.0))

        def field(ox_, oy_):
            a1 = g.group(vr, P=g.comb(g.add(g.add(q1[0], w_spd), ox_), g.add(g.add(q1[1], g.mul(w_spd, 0.35)), oy_),
                                      0.0), Rep=(32.0, 1e6, 1.0)).outputs['Value']
            a2 = g.group(vr, P=g.comb(g.add(g.sub(q2[0], g.mul(w_spd, 1.7)), 2 * ox_),
                                      g.add(g.sub(q2[1], g.mul(w_spd, 0.6)), 2 * oy_), 0.0),
                         Rep=(44.0, 1e6, 1.0)).outputs['Value']
            return g.add(a1, g.mul(a2, 0.5))

        h0, hx, hy = field(0.0, 0.0), field(0.5, 0.0), field(0.0, 0.5)
        amp = g.mul(g.mul(float(o.get('waveAmp', 0.55)), g.add(g.mul(shim_raw, 0.8), 0.5)), g.one_minus(far_k))
        wave_slope = (g.mul(g.sub(h0, hx), amp), g.mul(g.sub(h0, hy), amp))
    if wave_slope is not None:
        sx, sy = wave_slope
        wave_n = g.vnorm(g.vadd(g.vadd(nn, g.vscale(t_n, sx)), g.vscale(tv, sy)))
        surface_n = g.vnorm(g.vlerp(land_n, wave_n, kw))
        # NIGHT WATER: exaggerated animated wave normals glinting under grazing planet light
        wave_nn = g.vnorm(g.vadd(g.vadd(nn, g.vscale(t_n, g.mul(sx, 3.2))), g.vscale(tv, g.mul(sy, 3.2))))
        moon = k['moon_dir']
        m_tan = g.vnorm(g.vadd(g.vsub(moon, g.vscale(nn, g.vdot(moon, nn))), (0.02, -0.01, 0.0)))
        rake_p = g.clamp(g.mul(g.vdot(wave_nn, m_tan), 1.6), 0.0, 1.0)
        glint = g.add(g.add(g.mul(g.mul(rake_p, rake_p), 0.6), g.mul(rake_p, 0.14)), 0.05)
        shine_w = g.add(0.30, g.mul(arc.outputs['PVis'], 0.70))
        scal = g.mul(g.mul(g.mul(glint, shine_w), kw), g.mul(g.one_minus(k['day_f']), g.one_minus(arc.outputs['LitK'])))
        water_night = g.vscale(g.vmul(arc.outputs['Trans'], (0.30, 0.36, 0.55)), g.mul(scal, 0.85))
    if not authored:
        # the skirt strips keep their own geometric normal (Eanpa ringSkirt)
        skirt = g.node('ShaderNodeAttribute', attribute_name='ringSkirt')
        surface_n = g.vnorm(g.vlerp(surface_n, geo.outputs['Normal'], skirt.outputs['Fac']))
    # ---- emission ----
    insc = arc.outputs['Insc']
    insc_on = opt_on(o, 'inscatterEnabled', True)
    relief = night_relief = None
    if lit_band:
        # atmosphere only: no painted sun
        arc_out = g.vscale(insc, 0.68) if insc_on else (0.0, 0.0, 0.0)
    else:
        relief, night_relief = _arc_relief(g, k, A, img_uv, nn if have_nm else None)
        arc_out = _analytic_arc(g, k, arc, o, albedo, kw, shim, relief, night_relief, night_ao, insc)
    if debug == 'lighting':
        if night_relief is None:
            _rl, night_relief = _arc_relief(g, k, A, img_uv, nn if have_nm else None)
        emis = g.comb(arc.outputs['LitK'], arc.outputs['PVis'], g.mul(night_relief, 0.4))
    else:
        if opt_on(o, 'footVeil', True):
            emis = g.vlerp(arc_out, k['haze'], g.mul(arc.outputs['Foot'], 0.8))
        else:
            emis = arc_out
        if water_night is not None:
            emis = g.vadd(emis, water_night)
    bsdf = g.node('ShaderNodeBsdfPrincipled')
    if lit_band and debug != 'lighting':
        g.link(albedo, bsdf.inputs['Base Color'])
    else:
        bsdf.inputs['Base Color'].default_value = (0.0, 0.0, 0.0, 1.0)
    g.link(rough, bsdf.inputs['Roughness'])
    bsdf.inputs['Metallic'].default_value = 0.0
    g.link(surface_n, bsdf.inputs['Normal'])
    g.link(emis, bsdf.inputs['Emission Color'])
    bsdf.inputs['Emission Strength'].default_value = 1.0
    out = g.node('ShaderNodeOutputMaterial')
    g.link(overlay_opaque(g, bsdf.outputs[0]), out.inputs['Surface'])
    ob.data.materials.clear()
    ob.data.materials.append(m)
    if not authored:
        _mark_skirt(ob)
    return m


def _arc_relief(g, k, A, img_uv, nn):
    """relief and nightRelief of the analytic path (ringworld.js): the normal map in the analytic frame against the
    true sun, raked when the light goes face-on; at night a bi-directional hillshade raked from the planet."""
    tco = g.node('ShaderNodeTexCoord')
    _ox, oy, oz = g.sep(tco.outputs['Object'])
    n_geo = g.vnorm(g.comb(0.0, g.neg(oy), g.neg(oz)))                         # -rHat
    r_hat = g.vscale(n_geo, -1.0)
    x_ax = (1.0, 0.0, 0.0)
    t_around = g.vnorm(g.vcross(x_ax, r_hat))
    sun, moon = k['sun_dir'], k['moon_dir']
    if nn is None:
        geo = g.node('ShaderNodeNewGeometry')
        relief = g.clamp(g.vdot(geo.outputs['Normal'], sun), 0.0, 1.0)
        return relief, relief
    nm = g.image(_image(A['bandNormal']), img_uv, label='band_normal_arc').outputs['Color']
    nx, ny, nz = g.sep(g.vsub(g.vscale(nm, 2.0), (1.0, 1.0, 1.0)))
    pert_n = g.vnorm(g.vadd(g.vadd(g.vscale(t_around, g.neg(nx)), g.vscale(x_ax, g.neg(ny))), g.vscale(n_geo, nz)))
    nm_l = g.vnorm(g.vadd(g.vadd(g.vscale(t_around, g.mul(nx, 2.3)), g.vscale(x_ax, g.mul(ny, 2.3))),
                          g.vscale(n_geo, nz)))
    off = (0.02, -0.01, 0.0)                                                   # three (0.02, 0, 0.01)
    s_tan = g.vnorm(g.vadd(g.vsub(sun, g.vscale(n_geo, g.vdot(sun, n_geo))), off))
    s_rake1 = g.vnorm(g.vadd(s_tan, g.vscale(n_geo, 0.35)))
    s_rake2 = g.vnorm(g.vadd(g.vcross(n_geo, s_tan), g.vscale(n_geo, 0.35)))
    lit_rake = g.clamp(g.add(g.add(0.22, g.mul(g.vdot(nm_l, s_rake1), 1.05)),
                             g.mul(g.abs(g.vdot(nm_l, s_rake2)), 0.45)), 0.08, 1.4)
    face_on = g.clamp(g.add(g.mul(g.sub(g.abs(g.vdot(sun, n_geo)), 0.05), 1.8), 0.38), 0.38, 1.0)
    relief = g.lerp(g.clamp(g.vdot(pert_n, sun), 0.0, 1.0), lit_rake, face_on)
    m_tan = g.vnorm(g.vadd(g.vsub(moon, g.vscale(n_geo, g.vdot(moon, n_geo))), off))
    rake1 = g.vnorm(g.vadd(m_tan, g.vscale(n_geo, 0.35)))
    t_perp = g.vnorm(g.vcross(n_geo, m_tan))
    rake2 = g.vnorm(g.vadd(t_perp, g.vscale(n_geo, 0.35)))
    s1 = g.vdot(nm_l, rake1)
    s2 = g.abs(g.vdot(nm_l, rake2))
    night_relief = g.clamp(g.add(g.add(0.22, g.mul(s1, 1.15)), g.mul(s2, 0.5)), 0.08, 1.5)
    return relief, night_relief


def _analytic_arc(g, k, arc, o, albedo, kw, shim, relief, night_relief, night_ao, insc):
    """litBand=False (ringworld.js's analytic emissive path): litArc, nightSide and sparkle painted through
    emission over a black albedo, plus the air."""
    day_f = arc.outputs['DayF']
    lit_k = arc.outputs['LitK']
    trans = arc.outputs['Trans']
    _sx, _sy, sun_el = g.sep(k['sun_dir'])
    arch = g.smoothstep(0.10, -0.06, sun_el)
    sun_term = g.vscale(k['sun_col'], g.lerp(0.22, 1.0, day_f))
    lit_col = g.vlerp(g.vscale(sun_term, k['gain']), (0.90 * 0.24, 0.93 * 0.24, 0.24), arch)
    lit_arc = g.vscale(g.vmul(g.vmul(albedo, arc.outputs['WarmT']), lit_col), g.add(0.22, g.mul(relief, 1.05)))
    night_vis = g.one_minus(day_f)
    shine = g.add(0.40, g.mul(arc.outputs['PVis'], 0.60))
    nt = night_tint(o)
    n_base = g.vmul(albedo, nt)
    n_lum = g.vdot(n_base, LUMA)
    n_base = g.vmath('MAXIMUM', g.vlerp(g.comb(n_lum, n_lum, n_lum), n_base, float(o.get('nightSat', 1.3))),
                     (0.0, 0.0, 0.0))
    n_scale = g.mul(g.mul(night_relief, shine), g.mul(float(o.get('nightLevel', 1.20)), night_vis))
    if night_ao is not None:
        n_scale = g.mul(n_scale, night_ao)
    night_side = g.vscale(n_base, n_scale)
    sparkle = g.mul(g.mul(g.mul(kw, g.pow(shim, 8.0)), 0.55),
                    g.add(g.mul(lit_k, g.lerp(0.35, 1.0, day_f)), g.mul(night_vis, 0.5)))
    out = g.vadd(g.vscale(g.vmul(lit_arc, trans), lit_k),
                 g.vscale(g.vmul(night_side, trans), g.one_minus(lit_k)))
    if opt_on(o, 'inscatterEnabled', True):
        out = g.vadd(out, g.vscale(insc, 0.68))
    return g.vadd(out, g.comb(sparkle, sparkle, sparkle))


def _mark_skirt(ob):
    """A per-vertex 'ringSkirt' attribute: 1 on the two edge strips (the vertices past the surface rows)."""
    import numpy as np
    me = ob.data
    n = len(me.vertices)
    attr = me.attributes.get('ringSkirt') or me.attributes.new('ringSkirt', 'FLOAT', 'POINT')
    co = np.empty(n * 3, np.float32)
    me.vertices.foreach_get('co', co)
    co = co.reshape(-1, 3)
    r = np.hypot(co[:, 1], co[:, 2])
    vals = (r > R_REF + 0.5).astype(np.float32)        # the skirts' outer rim sits 2 m outside the band radius
    attr.data.foreach_set('value', vals)


def walls_material(ring, ob):
    """WALLS: the authored emissive panel look under the same arc rules (terminator'd, seen through the air)."""
    A = ring.A
    m = _new_material('eido_ring_walls')
    g = Graph(m.node_tree)
    arc = g.group(arc_shade_group(), Position=g.node('ShaderNodeNewGeometry').outputs['Position'])
    uvn = g.node('ShaderNodeUVMap', uv_map=ob.data.uv_layers.active.name)
    col = g.image(_image(A['solarColor'], 'sRGB'), uvn.outputs['UV'], label='panel_color').outputs['Color']
    nrm = g.image(_image(A['solarNormal']), uvn.outputs['UV'], label='panel_normal').outputs['Color']
    rgh = g.image(_image(A['solarRough']), uvn.outputs['UV'], label='panel_rough').outputs['Color']
    mtl = g.image(_image(A['solarMetal']), uvn.outputs['UV'], label='panel_metal').outputs['Color']
    nmap = g.node('ShaderNodeNormalMap', uv_map=ob.data.uv_layers.active.name)
    g.link(nrm, nmap.inputs['Color'])
    wall_lit = g.vscale(g.vmul(col, arc.outputs['WarmT']), 0.55)
    wall_night = g.vscale(col, 0.05)
    emis = g.vmul(g.vlerp(wall_night, wall_lit, arc.outputs['LitK']), arc.outputs['Trans'])
    emis = g.vadd(g.vscale(emis, g.max(arc.outputs['Gain'], 0.20)), g.vscale(arc.outputs['Insc'], 0.85))
    bsdf = g.node('ShaderNodeBsdfPrincipled')
    bsdf.inputs['Base Color'].default_value = (0.0, 0.0, 0.0, 1.0)
    g.link(g.sep(rgh)[0], bsdf.inputs['Roughness'])
    g.link(g.sep(mtl)[0], bsdf.inputs['Metallic'])
    g.link(nmap.outputs['Normal'], bsdf.inputs['Normal'])
    g.link(emis, bsdf.inputs['Emission Color'])
    bsdf.inputs['Emission Strength'].default_value = 1.0
    out = g.node('ShaderNodeOutputMaterial')
    g.link(overlay_opaque(g, bsdf.outputs[0]), out.inputs['Surface'])
    ob.data.materials.clear()
    ob.data.materials.append(m)
    return m


def cloud_sheet_material(ring, ob):
    """RING CLOUD LAYER: satellite-imagery clouds coupled to the sky's cloud uniforms, through the arc's air."""
    m = _new_material('eido_ring_clouds', 'BLENDED')
    m.use_transparent_shadow = True
    m.use_backface_culling = False
    g = Graph(m.node_tree)
    k = _keys(g)
    arc = g.group(arc_shade_group(), Position=g.node('ShaderNodeNewGeometry').outputs['Position'])
    uvn = g.node('ShaderNodeUVMap', uv_map='UVMap')
    u, v, _ = g.sep(uvn.outputs['UV'])
    dx, dy, _ = g.sep(k['disp'])
    fu = g.sub(u, dx)
    fv = g.sub(v, dy)
    field = g.image(_image(ring.cloud_field_path), g.comb(fu, g.one_minus(fv), 0.0), label='ring_cloud_field')
    f, _, _ = g.sep(field.outputs['Color'])
    th = g.sub(0.88, g.mul(k['cover'], 0.55))
    cov = g.mul(g.mul(g.smoothstep(th, g.add(th, 0.15), f), g.sub(0.85, g.mul(k['grey'], 0.12))), k['dens'])
    cov = g.clamp(cov, 0.0, 1.0)
    edge = g.mul(g.smoothstep(0.02, 0.15, v), g.one_minus(g.smoothstep(0.85, 0.98, v)))
    coverage = g.mul(cov, edge)
    core = g.smoothstep(0.2, 0.9, f)
    bright = g.vlerp(k['tint_sun'], k['tint_amb'], core)
    local = g.vscale(bright, g.mul(g.add(0.22, g.mul(arc.outputs['LitK'], 0.78)), arc.outputs['Gain']))
    far = g.vscale((0.90 * 0.24, 0.93 * 0.24, 0.24), g.lerp(1.0, 0.7, core))
    lit = g.vlerp(local, far, g.mul(g.one_minus(arc.outputs['DayF']), arc.outputs['LitK']))
    emis = g.vadd(g.vscale(g.vmul(lit, arc.outputs['Trans']), k['rad']), g.vscale(arc.outputs['Insc'], 0.35))
    alpha = g.mul(coverage, g.smoothstep(3500.0, 7000.0, arc.outputs['FragD']))   # NEAR FADE
    out = g.node('ShaderNodeOutputMaterial')
    g.link(blended_surface(g, g.vscale(emis, alpha), alpha, with_overlay=True), out.inputs['Surface'])
    ob.data.materials.clear()
    ob.data.materials.append(m)
    return m


def haze_wall_material(ring, ob, rain=False):
    """FOG BOUNDARY (a low haze band) or RAIN WALL (up to the cloud base, only in real rain): local haze, drawn over
    the clouds as WebGPU's transparent pass did, so no overlay."""
    m = _new_material('eido_ring_rain_wall' if rain else 'eido_ring_fog_wall', 'BLENDED')
    m.use_backface_culling = True
    g = Graph(m.node_tree)
    k = _keys(g)
    uvn = g.node('ShaderNodeUVMap', uv_map='UVMap')
    _, v, _ = g.sep(uvn.outputs['UV'])
    if rain:
        alpha = g.mul(g.mul(g.smoothstep(0.9, 0.12, v), 0.7), k['rain_haze'])
        col = g.vscale(k['haze'], 1.28)
    else:
        alpha = g.mul(g.smoothstep(0.62, 0.16, v), 0.78)
        col = k['haze']
    out = g.node('ShaderNodeOutputMaterial')
    g.link(blended_surface(g, g.vscale(col, alpha), alpha, with_overlay=False), out.inputs['Surface'])
    ob.data.materials.clear()
    ob.data.materials.append(m)
    ob.visible_shadow = False
    return m


def eclipse_proxy_material():
    """The shadow-only eclipse proxy: opaque to the band sun's shadow rays, never seen."""
    m = bpy.data.materials.get('eido_ring_eclipse_proxy')
    if m is not None:
        return m
    m = bpy.data.materials.new('eido_ring_eclipse_proxy')
    m.use_nodes = True
    nt = m.node_tree
    nt.nodes.clear()
    g = Graph(nt)
    bsdf = g.node('ShaderNodeBsdfDiffuse')
    bsdf.inputs['Color'].default_value = (0.0, 0.0, 0.0, 1.0)
    out = g.node('ShaderNodeOutputMaterial')
    g.link(bsdf.outputs[0], out.inputs['Surface'])
    return m
