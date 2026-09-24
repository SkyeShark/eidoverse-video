# house_mats.py — layered source materials for the beach cottage (evaluated by Cycles at bake time).
# Library PBR base (AmbientCG / Poly Haven, see tex/*/fetch.log + sources.json) + tint, then AO grime,
# rain streaks under eaves and the window sill, ground splash, salt bloom, bevel-driven edge wear
# (painted parts), rust (metal) and lichen (roof). bake_export.py bakes these down per object.

import bpy, os, math

class NT:
    def __init__(self, mat):
        mat.use_nodes = True
        self.t = mat.node_tree
        self.t.nodes.clear()

    def n(self, typ, loc=None, **props):
        nd = self.t.nodes.new(typ)
        for k, v in props.items():
            setattr(nd, k, v)
        if loc:
            nd.location = loc
        return nd

    def l(self, a, b):
        self.t.links.new(a, b)
        return b

    def math(self, op, a, b=None, clamp=False):
        m = self.n('ShaderNodeMath', operation=op, use_clamp=clamp)
        for i, v in enumerate((a, b)):
            if v is None:
                continue
            if isinstance(v, (int, float)):
                m.inputs[i].default_value = v
            else:
                self.l(v, m.inputs[i])
        return m.outputs[0]

    def mix(self, fac, a, b, blend='MIX'):
        m = self.n('ShaderNodeMix', data_type='RGBA', blend_type=blend, clamp_result=True)
        for idx, v in ((0, fac), (6, a), (7, b)):
            if isinstance(v, (int, float)):
                m.inputs[idx].default_value = v
            elif isinstance(v, tuple):
                m.inputs[idx].default_value = (*v, 1.0) if len(v) == 3 else v
            else:
                self.l(v, m.inputs[idx])
        return m.outputs[2]

    def vmath(self, op, a, b=None):
        m = self.n('ShaderNodeVectorMath', operation=op)
        for i, v in enumerate((a, b)):
            if v is None:
                continue
            if isinstance(v, (tuple, list)):
                m.inputs[i].default_value = v
            else:
                self.l(v, m.inputs[i])
        return m.outputs['Value'] if op == 'DOT_PRODUCT' else m.outputs['Vector']

    def maprange(self, v, a, b, c=0.0, d=1.0, clamp=True):
        m = self.n('ShaderNodeMapRange', clamp=clamp)
        self.l(v, m.inputs[0])
        m.inputs[1].default_value = a
        m.inputs[2].default_value = b
        m.inputs[3].default_value = c
        m.inputs[4].default_value = d
        return m.outputs[0]

    def noise(self, vec, scale, detail=4.0, rough=0.55, dist=0.0):
        m = self.n('ShaderNodeTexNoise')
        m.noise_dimensions = '3D'
        if vec is not None:
            self.l(vec, m.inputs['Vector'])
        m.inputs['Scale'].default_value = scale
        m.inputs['Detail'].default_value = detail
        m.inputs['Roughness'].default_value = rough
        m.inputs['Distortion'].default_value = dist
        return m.outputs[0]


def img(path, color=True):
    im = bpy.data.images.load(path, check_existing=True)
    im.colorspace_settings.name = 'sRGB' if color else 'Non-Color'
    return im


def texset(tex_root, name):
    d = os.path.join(tex_root, name)
    fs = sorted(os.listdir(d))

    def find(*keys):
        for k in keys:
            for f in fs:
                lf = f.lower()
                if lf.endswith(('.json', '.log')) or 'normaldx' in lf or lf.startswith('arm_'):
                    continue
                if k in lf:
                    return os.path.join(d, f)
        return None
    return dict(color=find('_color', 'diff_'), rough=find('roughness', 'rough_'),
                normal=find('normalgl', 'nor_gl'), ao=find('ambientocclusion', 'ao_'),
                metal=find('metalness', 'metal_'))


# tile = metres per texture repeat; hsv on the library colour; tint multiplies after.
SPECS = {
    'siding':  dict(tex='WoodSiding010', tile=1.25, hsv=(0.49, 0.62, 1.45), tint=(1.0, 0.955, 0.90),
                    grime=0.55, streak=0.55, splash=0.75, salt=0.10, edge=0.0, ao_d=0.40, nstr=1.0),
    'found':   dict(tex='concrete_block_wall', tile=1.0, hsv=(0.5, 0.25, 1.45), tint=(0.92, 0.91, 0.88),
                    grime=0.45, streak=0.25, splash=0.8, salt=0.15, edge=0.0, ao_d=0.30, nstr=1.0),
    'trim':    dict(tex='PaintedWood009C', tile=1.1, hsv=(0.5, 0.30, 1.10), tint=(0.97, 0.965, 0.95),
                    grime=0.50, streak=0.40, splash=0.55, salt=0.06, edge=0.75, ao_d=0.25, nstr=0.8,
                    edge_col=(0.36, 0.34, 0.31), bevel=0.006),
    'roof':    dict(tex='grey_roof_01', tile=2.8, hsv=(0.5, 0.55, 1.0), tint=(0.90, 0.92, 0.95),
                    grime=0.30, streak=0.20, splash=0.0, salt=0.10, edge=0.0, ao_d=0.30, nstr=1.2, lichen=0.25),
    'porchfloor': dict(tex='blue_painted_planks', tile=1.0, hsv=(0.5, 0.55, 1.12), tint=(0.90, 0.93, 0.97),
                    grime=0.45, streak=0.0, splash=0.35, salt=0.10, edge=0.35, ao_d=0.25, nstr=1.0,
                    edge_col=(0.30, 0.28, 0.25), bevel=0.005),
    'ceiling': dict(tex='PaintedWood008A', tile=1.2, hsv=(0.5, 0.75, 1.20), tint=(0.95, 1.0, 1.0),
                    grime=0.35, streak=0.0, splash=0.0, salt=0.0, edge=0.0, ao_d=0.30, nstr=0.8),
    'door':    dict(tex='PaintedWood009A', tile=1.0, hsv=(0.545, 0.42, 0.78), tint=(0.92, 1.0, 0.98),
                    grime=0.40, streak=0.15, splash=0.3, salt=0.05, edge=0.55, ao_d=0.12, nstr=0.8,
                    edge_col=(0.40, 0.36, 0.30), bevel=0.004),
    'metal':   dict(tex='Metal027', tile=0.35, hsv=(0.5, 0.6, 1.0), tint=(1.0, 1.0, 1.0),
                    grime=0.35, streak=0.0, splash=0.0, salt=0.05, edge=0.30, ao_d=0.05, nstr=0.6,
                    edge_col=(0.55, 0.53, 0.50), bevel=0.0015, rust=0.55),
    'pier':    dict(tex='weathered_planks', tile=1.0, hsv=(0.5, 0.35, 1.25), tint=(0.92, 0.92, 0.92),
                    grime=0.45, streak=0.0, splash=0.9, salt=0.12, edge=0.0, ao_d=0.25, nstr=1.0),
    'curtain': dict(tex='rough_linen', tile=0.45, hsv=(0.5, 0.0, 1.05), tint=(1.0, 0.90, 0.74),
                    grime=0.15, streak=0.0, splash=0.0, salt=0.0, edge=0.0, ao_d=0.10, nstr=0.6),
    'interior': dict(tex='PaintedWood009C', tile=1.1, hsv=(0.5, 0.6, 0.55), tint=(0.95, 0.85, 0.70),
                    grime=0.60, streak=0.0, splash=0.0, salt=0.0, edge=0.0, ao_d=0.30, nstr=0.5),
}


def layered(name, spec, tex_root, geo_info):
    """geo_info: dict(u_top, win=(x0,x1,u0)) in Blender coords (Z up, front = -Y)."""
    m = bpy.data.materials.new(name)
    t = NT(m)
    ts = texset(tex_root, spec['tex'])
    out = t.n('ShaderNodeOutputMaterial', (1400, 0))
    bsdf = t.n('ShaderNodeBsdfPrincipled', (1100, 0))
    t.l(bsdf.outputs[0], out.inputs['Surface'])
    uvn = t.n('ShaderNodeUVMap', (-1600, 0), uv_map='tile')
    mp = t.n('ShaderNodeMapping', (-1400, 0))
    s = 1.0 / spec['tile']
    mp.inputs['Scale'].default_value = (s, s, 1.0)
    t.l(uvn.outputs[0], mp.inputs['Vector'])

    def tex(path, color):
        nd = t.n('ShaderNodeTexImage', (-1150, 0))
        nd.image = img(path, color)
        nd.interpolation = 'Linear'
        t.l(mp.outputs[0], nd.inputs['Vector'])
        return nd

    col = tex(ts['color'], True).outputs['Color']
    hs = t.n('ShaderNodeHueSaturation')
    hs.inputs['Hue'].default_value, hs.inputs['Saturation'].default_value, hs.inputs['Value'].default_value = spec['hsv']
    t.l(col, hs.inputs['Color'])
    base = t.mix(1.0, hs.outputs[0], spec['tint'], 'MULTIPLY')
    if ts['rough']:
        rough_v = t.math('MULTIPLY', tex(ts['rough'], False).outputs['Color'], 1.0)
    else:
        rough_v = t.math('ADD', 0.85, 0.0)
    metal_v = t.math('MULTIPLY', tex(ts['metal'], False).outputs['Color'], 1.0) if ts['metal'] else None
    nm = t.n('ShaderNodeNormalMap', space='TANGENT', uv_map='tile')
    nm.inputs['Strength'].default_value = spec.get('nstr', 1.0)
    t.l(tex(ts['normal'], False).outputs['Color'], nm.inputs['Color'])
    nrm = nm.outputs[0]
    geo = t.n('ShaderNodeNewGeometry')
    pos = geo.outputs['Position']
    sep = t.n('ShaderNodeSeparateXYZ')
    t.l(pos, sep.inputs[0])
    PX, PY, PZ = sep.outputs[0], sep.outputs[1], sep.outputs[2]

    # grime: AO cavities (other objects count: under trim, under the eaves, behind posts)
    ao = t.n('ShaderNodeAmbientOcclusion', samples=16, only_local=False)
    ao.inputs['Distance'].default_value = spec['ao_d']
    cav = t.math('POWER', t.math('SUBTRACT', 1.0, ao.outputs['AO'], clamp=True), 1.4)
    g = t.math('MULTIPLY', cav, spec['grime'] * 1.2)
    u_top = geo_info['u_top']
    wx0, wx1, wu0 = geo_info['win']
    if spec['streak'] > 0:
        smap = t.n('ShaderNodeMapping')
        smap.inputs['Scale'].default_value = (38.0, 38.0, 1.3)
        t.l(pos, smap.inputs['Vector'])
        sn = t.maprange(t.noise(smap.outputs[0], 1.0, 6.0, 0.6), 0.48, 0.78)
        top = t.maprange(PZ, u_top - 1.2, u_top - 0.05)
        wx = t.math('MULTIPLY', t.math('GREATER_THAN', PX, wx0 - 0.10), t.math('LESS_THAN', PX, wx1 + 0.10))
        wz = t.math('MULTIPLY', t.maprange(PZ, wu0 - 0.75, wu0 - 0.02), t.math('LESS_THAN', PZ, wu0))
        win = t.math('MULTIPLY', t.math('MULTIPLY', wx, wz), t.math('LESS_THAN', PY, -1.5))
        smask = t.math('MAXIMUM', top, win)
        g = t.math('ADD', g, t.math('MULTIPLY', t.math('MULTIPLY', sn, smask), spec['streak']))
    if spec['splash'] > 0:
        gz = t.maprange(PZ, 1.05, 0.25)
        sp = t.maprange(t.noise(pos, 7.0, 5.0, 0.6), 0.35, 0.75)
        g = t.math('ADD', g, t.math('MULTIPLY', t.math('MULTIPLY', gz, sp), spec['splash']))
    g = t.math('MINIMUM', g, 0.92)
    grime_col = t.mix(1.0, base, (0.32, 0.29, 0.25), 'MULTIPLY')
    c = t.mix(g, base, grime_col)
    if spec['salt'] > 0:
        sb = t.math('MULTIPLY', t.maprange(t.noise(pos, 1.6, 3.0, 0.5), 0.5, 0.8), spec['salt'])
        c = t.mix(sb, c, (0.80, 0.80, 0.78))
    if spec.get('lichen'):
        ln = t.maprange(t.noise(pos, 3.5, 6.0, 0.62, 0.3), 0.58, 0.72)
        lm = t.math('MULTIPLY', t.math('MULTIPLY', ln, t.math('ADD', cav, 0.35)), spec['lichen'])
        c = t.mix(lm, c, (0.36, 0.40, 0.28))
    edge = None
    if spec['edge'] > 0:
        bev = t.n('ShaderNodeBevel', samples=8)
        bev.inputs['Radius'].default_value = spec.get('bevel', 0.006)
        dp = t.vmath('DOT_PRODUCT', bev.outputs[0], geo.outputs['True Normal'])
        e = t.maprange(dp, 0.992, 0.93)
        en = t.maprange(t.noise(pos, 22.0, 6.0, 0.65), 0.38, 0.62)
        edge = t.math('MINIMUM', t.math('MULTIPLY', t.math('MULTIPLY', e, en), spec['edge'] * 1.6), 1.0)
        ec = spec.get('edge_col', (0.35, 0.33, 0.30))
        wood = t.mix(t.maprange(t.noise(pos, 60.0, 2.0, 0.5), 0.3, 0.7), ec, tuple(v * 0.8 for v in ec))
        c = t.mix(edge, c, wood)
        d = t.vmath('SUBTRACT', bev.outputs[0], geo.outputs['True Normal'])
        nrm = t.vmath('NORMALIZE', t.vmath('ADD', nrm, d))
    if spec.get('rust'):
        rs = texset(tex_root, 'Rust007')
        rc = tex(rs['color'], True).outputs['Color']
        rr = tex(rs['rough'], False).outputs['Color']
        rn = t.maprange(t.noise(pos, 30.0, 6.0, 0.6), 0.45, 0.7)
        under = t.maprange(t.vmath('DOT_PRODUCT', geo.outputs['True Normal'], (0, 0, -1)), 0.0, 0.8)
        rm = t.math('MINIMUM', t.math('MULTIPLY', t.math('ADD', t.math('MULTIPLY', cav, 1.5),
                                                          t.math('MULTIPLY', under, 0.5)),
                                      t.math('MULTIPLY', rn, spec['rust'] * 2.0)), 1.0)
        c = t.mix(rm, c, t.mix(1.0, rc, (0.75, 0.65, 0.6), 'MULTIPLY'))
        rough_v = t.math('ADD', t.math('MULTIPLY', rough_v, t.math('SUBTRACT', 1.0, rm)), t.math('MULTIPLY', rr, rm))
        if metal_v is not None:
            metal_v = t.math('MULTIPLY', metal_v, t.math('SUBTRACT', 1.0, rm))
    rough_v = t.math('ADD', rough_v, t.math('MULTIPLY', g, 0.18))
    if edge is not None:
        rough_v = t.math('ADD', rough_v, t.math('MULTIPLY', edge, 0.12))
    rough_v = t.math('MINIMUM', rough_v, 1.0)
    t.l(c, bsdf.inputs['Base Color'])
    t.l(rough_v, bsdf.inputs['Roughness'])
    if metal_v is not None:
        t.l(metal_v, bsdf.inputs['Metallic'])
    t.l(nrm, bsdf.inputs['Normal'])
    m['layered'] = 1
    return m


def simple(name, color, rough=0.5, metal=0.0, alpha=1.0, transmission=0.0, emission=None, estr=0.0):
    m = bpy.data.materials.new(name)
    t = NT(m)
    out = t.n('ShaderNodeOutputMaterial', (400, 0))
    b = t.n('ShaderNodeBsdfPrincipled', (100, 0))
    t.l(b.outputs[0], out.inputs['Surface'])
    b.inputs['Base Color'].default_value = (*color, 1.0)
    b.inputs['Roughness'].default_value = rough
    b.inputs['Metallic'].default_value = metal
    b.inputs['Alpha'].default_value = alpha
    b.inputs['Transmission Weight'].default_value = transmission
    b.inputs['IOR'].default_value = 1.5
    if emission:
        b.inputs['Emission Color'].default_value = (*emission, 1.0)
        b.inputs['Emission Strength'].default_value = estr
    if alpha < 1.0:
        m.surface_render_method = 'BLENDED'
    return m


def make_screen_texture(root):
    """Charcoal fibreglass insect screen, woven over-under. Real pitch is ~1.4 mm; it is drawn at
    2.6 mm so the weave survives mip filtering as a translucent charcoal veil."""
    import numpy as np
    N = 512
    period = 20.0
    yy, xx = np.mgrid[0:N, 0:N].astype(np.float32)
    wx = 1.0 - np.abs(((xx + 0.5) % period) - period / 2) / (period / 2)      # 1 at a wire centre
    wy = 1.0 - np.abs(((yy + 0.5) % period) - period / 2) / (period / 2)
    cov_v = np.clip((wx - 0.70) * 10.0, 0, 1)
    cov_h = np.clip((wy - 0.70) * 10.0, 0, 1)
    over = ((np.floor((xx + 0.5) / period) + np.floor((yy + 0.5) / period)) % 2).astype(np.float32)
    shade_v = 0.70 + 0.30 * np.cos((1 - wx) * math.pi * 1.6) * (0.6 + 0.4 * over)
    shade_h = 0.70 + 0.30 * np.cos((1 - wy) * math.pi * 1.6) * (0.6 + 0.4 * (1 - over))
    cov = np.clip(cov_v + cov_h, 0, 1)
    shade = np.where(cov_v >= cov_h, shade_v, shade_h)
    rgb = np.stack([0.19 * shade, 0.195 * shade, 0.205 * shade], -1)
    a = cov * 0.92 + 0.04
    arr = np.concatenate([rgb, a[..., None]], -1).astype(np.float32)
    im = bpy.data.images.new('screen_weave', N, N, alpha=True, float_buffer=False)
    im.pixels.foreach_set(arr[::-1].ravel())
    path = os.path.join(root, 'textures', 'screen_weave.png')
    os.makedirs(os.path.dirname(path), exist_ok=True)
    im.filepath_raw = path
    im.file_format = 'PNG'
    im.save()
    return im


def screen_material(root):
    m = bpy.data.materials.new('screen')
    t = NT(m)
    out = t.n('ShaderNodeOutputMaterial', (500, 0))
    b = t.n('ShaderNodeBsdfPrincipled', (200, 0))
    t.l(b.outputs[0], out.inputs['Surface'])
    uvn = t.n('ShaderNodeUVMap', uv_map='tile')
    mp = t.n('ShaderNodeMapping')
    mp.inputs['Scale'].default_value = (1 / 0.052, 1 / 0.052, 1)
    t.l(uvn.outputs[0], mp.inputs['Vector'])
    tx = t.n('ShaderNodeTexImage')
    tx.image = make_screen_texture(root)
    t.l(mp.outputs[0], tx.inputs['Vector'])
    t.l(tx.outputs['Color'], b.inputs['Base Color'])
    t.l(tx.outputs['Alpha'], b.inputs['Alpha'])
    b.inputs['Roughness'].default_value = 0.55
    b.inputs['Metallic'].default_value = 0.25
    m.surface_render_method = 'BLENDED'
    return m


def make_materials(tex_root, root, geo_info):
    M = {k: layered(k, v, tex_root, geo_info) for k, v in SPECS.items()}
    M['glass'] = simple('glass', (0.80, 0.85, 0.88), rough=0.04, alpha=0.20, transmission=0.0)
    M['jar'] = simple('jar_glass', (0.84, 0.90, 0.87), rough=0.08, alpha=0.20, transmission=0.0)
    M['bulb'] = simple('bulb_glass', (1.0, 0.96, 0.88), rough=0.20, alpha=0.45, transmission=0.0)
    M['filament'] = simple('filament', (1.0, 0.62, 0.25), rough=0.4, metal=0.8, emission=(1.0, 0.55, 0.18), estr=0.0)
    M['screen'] = screen_material(root)
    M['vent'] = simple('vent_dark', (0.035, 0.034, 0.033), rough=0.9)
    M['wire'] = simple('bulb_wire', (0.62, 0.60, 0.56), rough=0.35, metal=1.0)
    return M
