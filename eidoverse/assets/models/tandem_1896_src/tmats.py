# tmats.py - layered source materials, atlas UVs, Cycles bakes, export materials, joins, GLB export.
#
# Each look is LAYERED (AmbientCG base set + wear/edge/cavity/dust masks + period details) and
# BAKED DOWN to one atlas per export material:
#   enamel  4096 colour / 2048 data   frame + fork: lined carriage enamel (clearcoat)
#   metal   2048                      nickel plate, japanned cantles, copper rivets, bolts
#   leather 2048, rubber 2048, wood 1024 (varnish coat), grips 1024 (cork + vulcanite),
#   spokes 512, chain 512
import os, math, json
import bpy
import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
TEX = os.path.abspath(os.path.join(HERE, '..', 'tex'))

GROUPS = {
    'enamel': dict(size=4096, data=2048, coat=True, margin=24),
    'metal': dict(size=2048, data=1024, coat=False, margin=10),
    'leather': dict(size=2048, data=1024, coat=False, margin=10),
    'rubber': dict(size=1024, data=1024, coat=False, margin=8),
    'wood': dict(size=1024, data=1024, coat=True, margin=8),
    'grips': dict(size=1024, data=512, coat=False, margin=6),
    'spokes': dict(size=512, data=512, coat=False, margin=4),
    'chain': dict(size=512, data=512, coat=False, margin=4),
}


def tex(id_, kind):
    for ext in ('jpg', 'png'):
        p = os.path.join(TEX, id_, '%s_%s.%s' % (id_, kind, ext))
        if os.path.exists(p):
            return p
    raise FileNotFoundError(id_ + ' ' + kind)


_IMG = {}


def load(path, data=False):
    key = (path, data)
    if key not in _IMG:
        im = bpy.data.images.load(path, check_existing=True)
        im.colorspace_settings.name = 'Non-Color' if data else 'sRGB'
        _IMG[key] = im
    return _IMG[key]


class N:
    """Tiny shader-node DSL: every method returns an output socket."""

    def __init__(self, mat):
        mat.use_nodes = True
        self.nt = mat.node_tree
        self.nt.nodes.clear()
        self.x = 0

    def node(self, t, **props):
        n = self.nt.nodes.new(t)
        n.location = (self.x, 0); self.x += 180
        for k, v in props.items():
            setattr(n, k, v)
        return n

    def link(self, out, inp):
        self.nt.links.new(out, inp)

    def val(self, v):
        n = self.node('ShaderNodeValue'); n.outputs[0].default_value = v
        return n.outputs[0]

    def _in(self, sock, v):
        if isinstance(v, (int, float)):
            sock.default_value = v
        elif isinstance(v, tuple):
            sock.default_value = v if len(v) == len(sock.default_value) else (*v, 1.0)[:len(sock.default_value)]
        else:
            self.link(v, sock)

    def math(self, op, a, b=None, c=None, clamp=False):
        n = self.node('ShaderNodeMath', operation=op, use_clamp=clamp)
        self._in(n.inputs[0], a)
        if b is not None:
            self._in(n.inputs[1], b)
        if c is not None:
            self._in(n.inputs[2], c)
        return n.outputs[0]

    def add(self, a, b, clamp=False): return self.math('ADD', a, b, clamp=clamp)
    def mul(self, a, b, clamp=False): return self.math('MULTIPLY', a, b, clamp=clamp)
    def sub(self, a, b, clamp=False): return self.math('SUBTRACT', a, b, clamp=clamp)
    def one_minus(self, a): return self.math('SUBTRACT', 1.0, a, clamp=True)
    def maxi(self, a, b): return self.math('MAXIMUM', a, b)
    def mini(self, a, b): return self.math('MINIMUM', a, b)

    def smooth(self, e0, e1, x):
        n = self.node('ShaderNodeMapRange', interpolation_type='SMOOTHSTEP', clamp=True)
        self._in(n.inputs['Value'], x)
        n.inputs['From Min'].default_value = e0
        n.inputs['From Max'].default_value = e1
        return n.outputs['Result']

    def remap(self, x, a, b, c, d):
        n = self.node('ShaderNodeMapRange', clamp=True)
        self._in(n.inputs['Value'], x)
        n.inputs['From Min'].default_value = a; n.inputs['From Max'].default_value = b
        n.inputs['To Min'].default_value = c; n.inputs['To Max'].default_value = d
        return n.outputs['Result']

    def mix(self, fac, a, b, blend='MIX'):
        n = self.node('ShaderNodeMix', data_type='RGBA', blend_type=blend, clamp_factor=True)
        self._in(n.inputs[0], fac)
        self._in(n.inputs[6], a)
        self._in(n.inputs[7], b)
        return n.outputs[2]

    def mixf(self, fac, a, b):
        n = self.node('ShaderNodeMix', data_type='FLOAT', clamp_factor=True)
        self._in(n.inputs[0], fac)
        self._in(n.inputs[2], a)
        self._in(n.inputs[3], b)
        return n.outputs[0]

    def rgb(self, r, g, b):
        n = self.node('ShaderNodeRGB'); n.outputs[0].default_value = (r, g, b, 1.0)
        return n.outputs[0]

    def srgb(self, hexv):
        c = [((hexv >> s) & 255) / 255.0 for s in (16, 8, 0)]
        lin = [x / 12.92 if x <= 0.04045 else ((x + 0.055) / 1.055) ** 2.4 for x in c]
        return self.rgb(*lin)

    def coord(self, kind='Object'):
        n = self.node('ShaderNodeTexCoord')
        return n.outputs[kind]

    def uvmap(self, name):
        n = self.node('ShaderNodeUVMap', uv_map=name)
        return n.outputs['UV']

    def xyz(self, v):
        n = self.node('ShaderNodeSeparateXYZ')
        self.link(v, n.inputs[0])
        return n.outputs['X'], n.outputs['Y'], n.outputs['Z']

    def combine(self, x, y, z):
        n = self.node('ShaderNodeCombineXYZ')
        self._in(n.inputs[0], x); self._in(n.inputs[1], y); self._in(n.inputs[2], z)
        return n.outputs[0]

    def scale_vec(self, v, s):
        n = self.node('ShaderNodeVectorMath', operation='SCALE')
        self.link(v, n.inputs[0]); n.inputs['Scale'].default_value = s
        return n.outputs[0]

    def img(self, path, vec, data=False, box=False, blend=0.25):
        n = self.node('ShaderNodeTexImage', interpolation='Cubic' if not data else 'Linear')
        n.image = load(path, data)
        if box:
            n.projection = 'BOX'; n.projection_blend = blend
        if vec is not None:
            self.link(vec, n.inputs['Vector'])
        return n.outputs['Color']

    def bw(self, c):
        n = self.node('ShaderNodeRGBToBW'); self.link(c, n.inputs[0])
        return n.outputs[0]

    def noise(self, vec, scale, detail=3.0, rough=0.55):
        n = self.node('ShaderNodeTexNoise')
        self._in(n.inputs['Vector'], vec)
        n.inputs['Scale'].default_value = scale
        n.inputs['Detail'].default_value = detail
        n.inputs['Roughness'].default_value = rough
        return n.outputs['Fac']

    def voronoi_edge(self, vec, scale):
        n = self.node('ShaderNodeTexVoronoi', feature='DISTANCE_TO_EDGE')
        self._in(n.inputs['Vector'], vec)
        n.inputs['Scale'].default_value = scale
        return n.outputs['Distance']

    def attr_obj(self, name):
        # per-part inputs are stored per vertex ('d' + name) so they survive joining the parts
        n = self.node('ShaderNodeAttribute', attribute_type='GEOMETRY', attribute_name='d' + name)
        return n.outputs['Fac']

    def geom(self, out):
        n = self.node('ShaderNodeNewGeometry')
        return n.outputs[out]

    def ao(self, dist=0.02, samples=24):
        n = self.node('ShaderNodeAmbientOcclusion', samples=samples, inside=False, only_local=False)
        n.inputs['Distance'].default_value = dist
        return n.outputs['AO']

    def edge_mask(self, radius=0.0025, lo=0.02, hi=0.18):
        """Curvature-style edge mask: how far the bevelled normal departs from the true one."""
        bv = self.node('ShaderNodeBevel', samples=8)
        bv.inputs['Radius'].default_value = radius
        ng = self.geom('Normal')
        d = self.node('ShaderNodeVectorMath', operation='DOT_PRODUCT')
        self.link(bv.outputs['Normal'], d.inputs[0]); self.link(ng, d.inputs[1])
        return self.smooth(lo, hi, self.one_minus(d.outputs['Value']))

    def normal_map(self, col, strength, uv=None):
        n = self.node('ShaderNodeNormalMap', space='TANGENT')
        if uv:
            n.uv_map = uv
        n.inputs['Strength'].default_value = strength
        self.link(col, n.inputs['Color'])
        return n.outputs['Normal']

    def bump(self, height, dist, normal=None, strength=1.0):
        n = self.node('ShaderNodeBump')
        n.inputs['Strength'].default_value = strength
        n.inputs['Distance'].default_value = dist
        self.link(height, n.inputs['Height'])
        if normal is not None:
            self.link(normal, n.inputs['Normal'])
        return n.outputs['Normal']

    def hsv(self, col, h=0.5, s=1.0, v=1.0):
        n = self.node('ShaderNodeHueSaturation')
        n.inputs['Hue'].default_value = h; n.inputs['Saturation'].default_value = s; n.inputs['Value'].default_value = v
        self.link(col, n.inputs['Color'])
        return n.outputs['Color']

    def world_height(self):
        n = self.node('ShaderNodeNewGeometry')
        _, _, z = self.xyz(n.outputs['Position'])
        return z

    def finish(self, color, rough, metal, normal=None, coat=None, coat_rough=None):
        b = self.node('ShaderNodeBsdfPrincipled')
        self._in(b.inputs['Base Color'], color)
        self._in(b.inputs['Roughness'], rough)
        self._in(b.inputs['Metallic'], metal)
        if normal is not None:
            self.link(normal, b.inputs['Normal'])
        if coat is not None:
            self._in(b.inputs['Coat Weight'], coat)
            self._in(b.inputs['Coat Roughness'], coat_rough if coat_rough is not None else 0.1)
        out = self.node('ShaderNodeOutputMaterial')
        self.link(b.outputs['BSDF'], out.inputs['Surface'])
        # named taps for the channel bakes
        taps = {}
        for k, s in (('color', color), ('rough', rough), ('metal', metal), ('coat', coat)):
            if s is None:
                continue
            r = self.node('NodeReroute'); r.name = 'TAP_' + k
            if isinstance(s, (int, float)):
                v = self.val(s); self.link(v, r.inputs[0])
            elif isinstance(s, tuple):
                c = self.rgb(*s[:3]); self.link(c, r.inputs[0])
            else:
                self.link(s, r.inputs[0])
            taps[k] = r
        return b, out


# ───────────────────────────── layered source looks ─────────────────────────────
def m_enamel(mat, base_hex=0x4a1418, gold_hex=0xd8ad58):
    n = N(mat)
    obj = n.coord('Object')
    pm = n.scale_vec(obj, 3.2)                                # PaintedMetal004 tiles ~31 cm
    pcol = n.img(tex('PaintedMetal004', 'Color'), pm, box=True)
    pmet = n.bw(n.img(tex('PaintedMetal004', 'Metalness'), pm, data=True, box=True))
    prou = n.bw(n.img(tex('PaintedMetal004', 'Roughness'), pm, data=True, box=True))
    pnor = n.img(tex('PaintedMetal004', 'NormalGL'), pm, data=True, box=True)
    wearA = n.attr_obj('wear')
    edge = n.edge_mask(0.0025, 0.03, 0.22)
    ao = n.ao(0.02)
    nlow = n.noise(n.scale_vec(obj, 1.0), 6.0, 3.0)
    # where paint can come off: edges, joints, the per-part wear bias, broken by noise
    wear = n.add(n.add(n.mul(wearA, 0.7), n.mul(edge, 0.55)), n.mul(n.sub(nlow, 0.5), 0.45), clamp=True)
    chip = n.mul(n.smooth(0.35, 0.65, pmet), n.smooth(0.55, 0.85, n.add(wear, n.mul(pmet, 0.25))), clamp=True)
    bare = n.mul(chip, n.smooth(0.2, 0.6, n.noise(n.scale_vec(obj, 1.0), 90.0, 2.0)), clamp=True)
    rust = n.mul(bare, n.smooth(0.45, 0.7, n.noise(n.scale_vec(obj, 1.0), 160.0, 2.0)), clamp=True)
    # paint: the scan's value variation and scratches carried onto oxblood carriage enamel
    lum = n.bw(pcol)
    paint = n.mix(1.0, n.srgb(base_hex), n.combine(n.remap(lum, 0.05, 0.35, 0.72, 1.18), n.remap(lum, 0.05, 0.35, 0.72, 1.18), n.remap(lum, 0.05, 0.35, 0.72, 1.18)), 'MULTIPLY')
    mott = n.noise(n.scale_vec(obj, 1.0), 9.0, 4.0)
    paint = n.mix(n.mul(n.sub(mott, 0.5), 0.35, clamp=True), paint, n.srgb(0x5d1c1e))
    # gold lining along the tubes (TubeUV: metres along, 0..1 around) and bands at the lugs
    tuv = n.uvmap('TubeUV')
    u, v, _ = n.xyz(tuv)
    L = n.attr_obj('len'); rad = n.attr_obj('rad'); lined = n.attr_obj('lining')
    dEnd = n.mini(u, n.sub(L, u))
    circ = n.mul(rad, 2 * math.pi)
    hw = 0.00045

    def around(v0):
        d = n.math('FRACT', n.add(n.sub(v, v0), 0.5))
        return n.mul(n.math('ABSOLUTE', n.sub(d, 0.5)), circ)

    def line(dist):
        return n.one_minus(n.smooth(hw, hw + 0.00022, dist))
    lines = n.maxi(n.maxi(line(around(0.12)), line(around(-0.12))), n.maxi(line(around(0.38)), line(around(0.62))))
    panel = n.smooth(0.0572, 0.0592, dEnd)                     # panels start just past the lug points
    band = line(n.math('ABSOLUTE', n.sub(dEnd, 0.058)))
    rub = n.smooth(0.62, 0.8, n.add(n.noise(n.scale_vec(obj, 1.0), 55.0, 2.0), n.mul(wear, 0.25)))
    lining = n.mul(n.mul(n.maxi(n.mul(lines, panel), band), lined), n.mul(n.one_minus(rub), n.one_minus(chip)), clamp=True)
    # dust (desert road) low down and on upward faces; grime in the crevices
    zb = n.world_height()
    up = n.xyz(n.geom('Normal'))[2]
    dn = n.noise(n.scale_vec(obj, 1.0), 14.0, 3.0)
    dust = n.mul(n.add(n.mul(n.smooth(0.42, 0.02, zb), 0.32), n.mul(n.smooth(0.4, 0.95, up), 0.16), clamp=True), n.remap(dn, 0.3, 0.7, 0.4, 1.0))
    grime = n.mul(n.one_minus(n.smooth(0.25, 0.95, ao)), 0.75)
    col = n.mix(lining, paint, n.srgb(gold_hex))
    col = n.mix(chip, col, n.srgb(0x2b2522))
    col = n.mix(bare, col, n.mix(rust, n.srgb(0x6e6a64), n.srgb(0x5a2a12)))
    col = n.mix(grime, col, n.srgb(0x1c1210))
    col = n.mix(dust, col, n.srgb(0xb59b78))
    metal = n.maxi(n.mul(lining, 0.9), n.mul(bare, n.one_minus(rust)))
    rough = n.add(n.add(n.remap(prou, 0.0, 1.0, 0.30, 0.46), n.mul(chip, 0.25)), n.add(n.mul(dust, 0.45), n.mul(rust, 0.3)), clamp=True)
    rough = n.mixf(lining, rough, 0.32)
    coat = n.mul(n.one_minus(chip), n.one_minus(n.mul(dust, 1.4)), clamp=True)
    coat_rough = n.add(n.add(0.10, n.mul(n.sub(mott, 0.5), 0.06)), n.mul(dust, 0.5), clamp=True)
    nrm = n.normal_map(pnor, 0.55)
    nrm = n.bump(chip, 0.00008, nrm, 1.0)
    n.finish(col, rough, metal, nrm, coat, coat_rough)


def m_nickel(mat, tint=0xd6cfbf, kind='nickel'):
    n = N(mat)
    obj = n.coord('Object')
    si = n.bw(n.img(tex('SurfaceImperfections003', 'Opacity'), n.scale_vec(obj, 4.0), data=True, box=True))
    fp = n.bw(n.img(tex('Fingerprints002', 'Roughness'), n.scale_vec(obj, 7.0), data=True, box=True))
    sm = n.bw(n.img(tex('Smear004', 'Roughness'), n.scale_vec(obj, 5.0), data=True, box=True))
    scn = n.img(tex('Scratches002', 'NormalGL'), n.scale_vec(obj, 6.0), data=True, box=True)
    ao = n.ao(0.015)
    edge = n.edge_mask(0.002, 0.03, 0.2)
    cav = n.one_minus(n.smooth(0.3, 0.95, ao))
    zb = n.world_height()
    dust = n.mul(n.smooth(0.34, 0.03, zb), 0.28)
    tarn = n.smooth(0.45, 0.8, n.noise(n.scale_vec(obj, 1.0), 4.0, 3.0))
    pits = n.mul(n.mul(n.one_minus(n.smooth(0.0, 0.02, n.voronoi_edge(n.scale_vec(obj, 1.0), 420.0))),
                       n.smooth(0.62, 0.82, n.noise(n.scale_vec(obj, 1.0), 12.0))), n.add(n.mul(cav, 0.8), 0.2), clamp=True)
    if kind == 'copper':
        base = n.srgb(0xc8835a); tarnc = n.srgb(0x5d4a2e)
    elif kind == 'japanned':
        base = n.srgb(0x141312); tarnc = n.srgb(0x2a2420)
    elif kind == 'chain':
        base = n.srgb(0x3a3531); tarnc = n.srgb(0x1c1917)
    else:
        base = n.srgb(tint); tarnc = n.srgb(0xb49f78)
    col = n.mix(n.mul(tarn, 0.35), base, tarnc)
    col = n.mix(n.mul(cav, 0.6), col, n.srgb(0x3a2e22) if kind != 'japanned' else n.srgb(0x0a0908))
    col = n.mix(n.mul(pits, 0.45), col, n.srgb(0x4a3526))
    if kind == 'japanned':                         # black japan worn to steel on the edges
        col = n.mix(n.smooth(0.3, 0.7, edge), col, n.srgb(0x8a8680))
    col = n.mix(dust, col, n.srgb(0xa6906f))
    rough = n.add(n.add(0.07, n.mul(si, 0.15)), n.add(n.mul(fp, 0.08), n.mul(sm, 0.07)))
    rough = n.add(rough, n.add(n.mul(cav, 0.25), n.add(n.mul(pits, 0.4), n.mul(dust, 0.6))), clamp=True)
    if kind == 'chain':
        rough = n.add(rough, 0.25, clamp=True)
    if kind == 'japanned':
        metal = n.smooth(0.3, 0.7, edge)
    else:
        metal = n.one_minus(n.add(n.mul(dust, 0.9), n.mul(pits, 0.5), clamp=True))
    nrm = n.normal_map(scn, {'japanned': 0.1, 'chain': 0.05}.get(kind, 0.22))
    n.finish(col, rough, metal, nrm)


def m_leather(mat):
    n = N(mat)
    obj = n.coord('Object')
    lv = n.scale_vec(obj, 4.5)
    lc = n.img(tex('Leather014', 'Color'), lv, box=True)
    lr = n.bw(n.img(tex('Leather014', 'Roughness'), lv, data=True, box=True))
    ln = n.img(tex('Leather014', 'NormalGL'), lv, data=True, box=True)
    edge = n.edge_mask(0.004, 0.02, 0.2)
    ao = n.ao(0.02)
    # sit-bone polish: two lobes either side of the centre, just behind the sit point
    pos = n.geom('Position')
    x, y, z = n.xyz(pos)
    sx = n.attr_obj('sitx')
    lat = n.math('ABSOLUTE', y)
    fwd = n.sub(x, sx)
    lobe = n.mul(n.one_minus(n.smooth(0.02, 0.085, n.math('ABSOLUTE', n.sub(fwd, 0.0)))), n.one_minus(n.smooth(0.02, 0.06, n.math('ABSOLUTE', n.sub(lat, 0.045)))))
    top = n.smooth(0.2, 0.7, n.xyz(n.geom('Normal'))[2])
    sit = n.mul(lobe, top)
    col = n.hsv(lc, 0.515, 0.95, 1.25)
    col = n.mix(n.mul(n.add(n.smooth(0.15, 0.6, edge), n.one_minus(n.smooth(0.3, 0.95, ao))), 0.6, clamp=True), col, n.srgb(0x2c160a))
    col = n.mix(n.mul(sit, 0.45), col, n.srgb(0xa0663a))
    rough = n.add(n.remap(lr, 0.0, 1.0, 0.42, 0.72), n.mul(sit, -0.2), clamp=True)
    nrm = n.normal_map(ln, 0.8)
    n.finish(col, rough, 0.0, nrm)


def m_gum(mat):
    n = N(mat)
    obj = n.coord('Object')
    rv = n.scale_vec(obj, 7.0)
    rr = n.bw(n.img(tex('Rubber004', 'Roughness'), rv, data=True, box=True))
    rn = n.img(tex('Rubber004', 'NormalGL'), rv, data=True, box=True)
    x, y, z = n.xyz(obj)
    rad = n.math('SQRT', n.add(n.mul(x, x), n.mul(z, z)))        # wheel-local radius (Blender x/z plane)
    tread = n.smooth(0.3225, 0.3275, rad)
    rimline = n.one_minus(n.smooth(0.0, 0.006, n.math('ABSOLUTE', n.sub(rad, 0.3005))))
    mott = n.noise(rv, 3.0, 4.0)
    col = n.mix(n.mul(n.sub(mott, 0.5), 0.5, clamp=True), n.srgb(0xaa9d84), n.srgb(0x93866e))
    col = n.mix(n.mul(tread, 0.55), col, n.srgb(0x80786b))
    col = n.mix(n.mul(tread, n.smooth(0.45, 0.75, mott)), col, n.srgb(0xc3b293))
    col = n.mix(n.mul(rimline, 0.5), col, n.srgb(0x5b4d3b))
    rough = n.add(n.remap(rr, 0.0, 1.0, 0.72, 0.9), n.mul(tread, 0.05), clamp=True)
    nrm = n.normal_map(rn, 0.35)
    n.finish(col, rough, 0.0, nrm)


def m_wood(mat):
    n = N(mat)
    tuv = n.uvmap('TubeUV')
    u, v, _ = n.xyz(tuv)                                        # lathe: u = profile metres, v = 0..1 around
    grain = n.combine(n.mul(v, 1.82), n.mul(u, 1.0), 0.0)
    wc = n.img(tex('Wood092', 'Color'), grain)
    wr = n.bw(n.img(tex('Wood092', 'Roughness'), grain, data=True))
    wn = n.img(tex('Wood092', 'NormalGL'), grain, data=True)
    obj = n.coord('Object')
    x, y, z = n.xyz(obj)
    rad = n.math('SQRT', n.add(n.mul(x, x), n.mul(z, z)))
    ply = n.smooth(0.34, 0.5, n.math('ABSOLUTE', n.sub(n.math('FRACT', n.math('DIVIDE', rad, 0.0024)), 0.5)))
    side = n.smooth(0.6, 0.9, n.math('ABSOLUTE', n.xyz(n.geom('Normal'))[1]))
    ao = n.ao(0.012)
    col = n.hsv(wc, 0.5, 1.05, 0.92)
    col = n.mix(n.mul(ply, n.mul(side, 0.4)), col, n.srgb(0x5a3110))
    col = n.mix(n.mul(n.one_minus(n.smooth(0.3, 0.95, ao)), 0.6), col, n.srgb(0x2e1a0c))
    rough = n.remap(wr, 0.0, 1.0, 0.4, 0.6)
    nrm = n.normal_map(wn, 0.4)
    n.finish(col, rough, 0.0, nrm, 1.0, n.add(0.12, n.mul(n.noise(obj, 30.0), 0.1)))


def m_cork(mat):
    n = N(mat)
    obj = n.coord('Object')
    cv = n.scale_vec(obj, 9.0)
    cc = n.img(tex('Cork003', 'Color'), cv, box=True)
    cr = n.bw(n.img(tex('Cork003', 'Roughness'), cv, data=True, box=True))
    cn = n.img(tex('Cork003', 'NormalGL'), cv, data=True, box=True)
    tuv = n.uvmap('TubeUV')
    u, v, _ = n.xyz(tuv)
    L = n.attr_obj('len')
    mid = n.one_minus(n.mul(n.math('ABSOLUTE', n.sub(n.math('DIVIDE', u, n.maxi(L, 0.01)), 0.5)), 2.0))
    grime = n.mul(n.smooth(0.15, 0.75, mid), 0.55)
    col = n.hsv(cc, 0.5, 0.85, 0.95)
    col = n.mix(grime, col, n.srgb(0x6a4a2c))
    rough = n.add(n.remap(cr, 0.0, 1.0, 0.7, 0.95), n.mul(grime, -0.25), clamp=True)
    nrm = n.normal_map(cn, 0.7)
    n.finish(col, rough, 0.0, nrm)


def m_vulcanite(mat):
    n = N(mat)
    obj = n.coord('Object')
    mott = n.noise(n.scale_vec(obj, 1.0), 80.0, 3.0)
    edge = n.edge_mask(0.002, 0.02, 0.2)
    col = n.mix(n.smooth(0.55, 0.85, mott), n.srgb(0x1c1917), n.srgb(0x3a2a20))
    col = n.mix(n.mul(edge, 0.5), col, n.srgb(0x4a3a30))
    rough = n.add(0.34, n.mul(mott, 0.18))
    n.finish(col, rough, 0.0, None)


def m_spoke(mat):
    m_nickel(mat, tint=0xcfc8b7)


SOURCE = {
    'enamel': m_enamel, 'nickel': m_nickel, 'japanned': lambda m: m_nickel(m, kind='japanned'),
    'copper': lambda m: m_nickel(m, kind='copper'), 'leather': m_leather, 'gum': m_gum, 'wood': m_wood,
    'cork': m_cork, 'vulcanite': m_vulcanite, 'chainsteel': lambda m: m_nickel(m, kind='chain'), 'spoke': m_spoke,
}


# ───────────────────────────── UVs ─────────────────────────────────────────────
def select_only(objs, active=None):
    bpy.ops.object.select_all(action='DESELECT') if bpy.context.mode == 'OBJECT' else None
    for o in bpy.context.view_layer.objects:
        o.select_set(False)
    for o in objs:
        o.select_set(True)
    bpy.context.view_layer.objects.active = active or objs[0]


def smart_uv(objs, log):
    """Boolean casts and the leather carry no usable UVs: project them per part (before joining)."""
    for ob in objs:
        me = ob.data
        me.uv_layers.active = me.uv_layers['UVMap']
        me.uv_layers['UVMap'].active_render = True
        if not ob.get('smartuv'):
            continue                    # sweeps / lathes / plates carry clean metric UVs already
        select_only([ob])
        bpy.ops.object.mode_set(mode='EDIT')
        bpy.ops.mesh.select_all(action='SELECT')
        bpy.ops.uv.smart_project(angle_limit=math.radians(55), island_margin=0.002, area_weight=0.0, scale_to_bounds=False)
        bpy.ops.object.mode_set(mode='OBJECT')


def pack(objs, log):
    """One atlas per export group: equal texel density across its parts, packed."""
    for g in GROUPS:
        grp = [o for o in objs if o['mgroup'] == g]
        if not grp:
            continue
        select_only(grp)
        bpy.ops.object.mode_set(mode='EDIT')
        bpy.ops.mesh.select_all(action='SELECT')
        bpy.ops.uv.select_all(action='SELECT')
        bpy.ops.uv.average_islands_scale()
        bpy.ops.uv.pack_islands(udim_source='CLOSEST_UDIM', rotate=True, margin=0.003)
        bpy.ops.object.mode_set(mode='OBJECT')
        log('uv packed', g, len(grp))


# ───────────────────────────── bake ────────────────────────────────────────────
def new_image(name, size, data):
    im = bpy.data.images.new(name, size, size, alpha=False, float_buffer=False)
    im.colorspace_settings.name = 'Non-Color' if data else 'sRGB'
    im.generated_color = (0.5, 0.5, 1.0, 1.0) if name.endswith('normal') else (0, 0, 0, 1)
    return im


def set_target(mats, im):
    for m in mats:
        nt = m.node_tree
        n = nt.nodes.get('BAKE_TARGET') or nt.nodes.new('ShaderNodeTexImage')
        n.name = 'BAKE_TARGET'
        n.image = im
        nt.nodes.active = n
        for other in nt.nodes:
            other.select = False
        n.select = True


def route(mats, channel):
    """Wire TAP_<channel> -> Emission -> output (or restore the BSDF when channel is None)."""
    for m in mats:
        nt = m.node_tree
        out = [n for n in nt.nodes if n.type == 'OUTPUT_MATERIAL'][0]
        bsdf = [n for n in nt.nodes if n.type == 'BSDF_PRINCIPLED'][0]
        em = nt.nodes.get('BAKE_EMIT') or nt.nodes.new('ShaderNodeEmission')
        em.name = 'BAKE_EMIT'
        for l in list(out.inputs['Surface'].links):
            nt.links.remove(l)
        if channel is None:
            nt.links.new(bsdf.outputs['BSDF'], out.inputs['Surface'])
            continue
        tap = nt.nodes.get('TAP_' + channel)
        for l in list(em.inputs['Color'].links):
            nt.links.remove(l)
        if tap is None:
            em.inputs['Color'].default_value = (0, 0, 0, 1) if channel != 'coat' else (0, 0, 0, 1)
        else:
            nt.links.new(tap.outputs[0], em.inputs['Color'])
        em.inputs['Strength'].default_value = 1.0
        nt.links.new(em.outputs['Emission'], out.inputs['Surface'])


def bake_group(g, objs, mats, sc, bake_dir, log):
    cfg = GROUPS[g]
    size, dsize = cfg['size'], cfg['data']
    select_only(objs)
    sc.render.bake.margin = cfg['margin']
    sc.render.bake.margin_type = 'EXTEND'
    sc.render.bake.use_clear = True
    sc.render.bake.target = 'IMAGE_TEXTURES'
    out = {}
    plan = [('color', 'EMIT', size, False), ('rough', 'EMIT', dsize, True), ('metal', 'EMIT', dsize, True),
            ('normal', 'NORMAL', dsize, True), ('ao', 'AO', dsize, True)]
    if cfg['coat']:
        plan.append(('coat', 'EMIT', dsize, True))
    for ch, typ, sz, data in plan:
        im = new_image('tandem_%s_%s' % (g, ch), sz, data)
        set_target(mats, im)
        if typ == 'EMIT':
            route(mats, ch)
            sc.cycles.samples = 4
        else:
            route(mats, None)
            sc.cycles.samples = 32 if typ == 'AO' else 2
        kw = {}
        if typ == 'NORMAL':
            kw = dict(normal_space='TANGENT')
        bpy.ops.object.bake(type=typ, **kw)
        out[ch] = im
        log('baked', g, ch, sz)
    route(mats, None)
    # pack ORM (R = AO, G = roughness, B = metallic) at data size
    def arr(im):
        a = np.empty(im.size[0] * im.size[1] * 4, dtype=np.float32)
        im.pixels.foreach_get(a)
        return a.reshape(im.size[1], im.size[0], 4)
    orm = new_image('tandem_%s_orm' % g, dsize, True)
    A = np.ones((dsize, dsize, 4), dtype=np.float32)
    A[..., 0] = arr(out['ao'])[..., 0]
    A[..., 1] = arr(out['rough'])[..., 0]
    A[..., 2] = arr(out['metal'])[..., 0]
    orm.pixels.foreach_set(A.ravel())
    out['orm'] = orm
    os.makedirs(bake_dir, exist_ok=True)
    save = {'color': 'JPEG', 'orm': 'JPEG', 'normal': 'PNG', 'coat': 'JPEG'}
    for ch, fmt in save.items():
        if ch not in out:
            continue
        im = out[ch]
        p = os.path.join(bake_dir, 'tandem_%s_%s.%s' % (g, ch, 'jpg' if fmt == 'JPEG' else 'png'))
        im.filepath_raw = p
        im.file_format = fmt
        im.save()
        im.source = 'FILE'
        im.reload()
    return out


def gltf_output_group():
    ng = bpy.data.node_groups.get('glTF Material Output')
    if ng:
        return ng
    ng = bpy.data.node_groups.new('glTF Material Output', 'ShaderNodeTree')
    ng.interface.new_socket('Occlusion', in_out='INPUT', socket_type='NodeSocketFloat')
    ng.interface.new_socket('Thickness', in_out='INPUT', socket_type='NodeSocketFloat')
    return ng


def export_material(g, maps):
    m = bpy.data.materials.new('tandem_' + g)
    m.use_nodes = True
    nt = m.node_tree
    nt.nodes.clear()
    b = nt.nodes.new('ShaderNodeBsdfPrincipled')
    o = nt.nodes.new('ShaderNodeOutputMaterial')
    nt.links.new(b.outputs['BSDF'], o.inputs['Surface'])
    uv = nt.nodes.new('ShaderNodeUVMap'); uv.uv_map = 'UVMap'
    def im(ch):
        n = nt.nodes.new('ShaderNodeTexImage')
        n.image = maps[ch]
        nt.links.new(uv.outputs['UV'], n.inputs['Vector'])
        return n
    c = im('color')
    nt.links.new(c.outputs['Color'], b.inputs['Base Color'])
    orm = im('orm')
    sep = nt.nodes.new('ShaderNodeSeparateColor')
    nt.links.new(orm.outputs['Color'], sep.inputs['Color'])
    nt.links.new(sep.outputs['Green'], b.inputs['Roughness'])
    nt.links.new(sep.outputs['Blue'], b.inputs['Metallic'])
    grp = nt.nodes.new('ShaderNodeGroup'); grp.node_tree = gltf_output_group()
    nt.links.new(sep.outputs['Red'], grp.inputs['Occlusion'])
    nm = nt.nodes.new('ShaderNodeNormalMap'); nm.uv_map = 'UVMap'
    nt.links.new(im('normal').outputs['Color'], nm.inputs['Color'])
    nt.links.new(nm.outputs['Normal'], b.inputs['Normal'])
    if 'coat' in maps:
        cn = im('coat')
        sc2 = nt.nodes.new('ShaderNodeSeparateColor')
        nt.links.new(cn.outputs['Color'], sc2.inputs['Color'])
        nt.links.new(sc2.outputs['Red'], b.inputs['Coat Weight'])
        b.inputs['Coat Roughness'].default_value = 0.14 if g == 'enamel' else 0.16
    if g == 'spokes':
        m['daisy_role'] = 'spokes'
    return m


# ───────────────────────────── orchestration ───────────────────────────────────
def run_full(kit, root, L, extras, sc, bake_dir, out_glb, log):
    sc.render.engine = 'CYCLES'
    prefs = bpy.context.preferences.addons['cycles'].preferences
    prefs.compute_device_type = 'OPTIX'
    prefs.get_devices()
    for d in prefs.devices:
        d.use = d.type == 'OPTIX'
    sc.cycles.device = 'GPU'
    if sc.world is None:
        sc.world = bpy.data.worlds.new('bake_world')
    sc.world.light_settings.distance = 0.02
    # per-part shader inputs become per-vertex attributes (they must survive the join)
    for ob in kit.objs:
        if ob['smat'] == 'leather':
            ob['sitx'] = L['frontSit'][0] if 'front' in ob.name else L['rearSit'][0]
        me = ob.data
        nv = len(me.vertices)
        for k, dflt in (('wear', 0.3), ('lining', 0.0), ('len', 0.0), ('rad', 0.0), ('sitx', 0.0)):
            a = me.attributes.new('d' + k, 'FLOAT', 'POINT')
            a.data.foreach_set('value', [float(ob.get(k, dflt))] * nv)
    # source materials
    mats = {}
    for ob in kit.objs:
        k = ob['smat']
        if k not in mats:
            m = bpy.data.materials.new('src_' + k)
            SOURCE[k](m)
            mats[k] = m
        ob.data.materials.clear()
        ob.data.materials.append(mats[k])
    log('source materials', sorted(mats))
    smart_uv(kit.objs, log)
    # join per (pivot, group): one Cycles bake session per group-part instead of one per piece
    joined = []
    buckets = {}
    for ob in kit.objs:
        buckets.setdefault((ob.parent.name, ob['mgroup']), []).append(ob)
    for (pv, g), objs in buckets.items():
        tgt = objs[0]
        if len(objs) > 1:
            with bpy.context.temp_override(active_object=tgt, object=tgt, selected_objects=objs, selected_editable_objects=objs):
                bpy.ops.object.join()
        tgt.name = '%s__%s' % (pv, g)
        tgt.data.name = tgt.name
        tgt.data.uv_layers.active = tgt.data.uv_layers['UVMap']
        tgt.data.uv_layers['UVMap'].active_render = True
        joined.append(tgt)
    log('joined meshes:', len(joined))
    pack(joined, log)
    for g in GROUPS:
        objs = [o for o in joined if o['mgroup'] == g]
        if not objs:
            continue
        gmats = []
        for o in objs:
            for m in o.data.materials:
                if m and m not in gmats:
                    gmats.append(m)
        maps = bake_group(g, objs, gmats, sc, bake_dir, log)
        em = export_material(g, maps)
        for o in objs:
            o.data.materials.clear()
            o.data.materials.append(em)
            for poly in o.data.polygons:
                poly.material_index = 0
    # drop the parametric UV and the bake-only attributes (the look is baked into the atlases)
    for ob in joined:
        tu = ob.data.uv_layers.get('TubeUV')
        if tu:
            ob.data.uv_layers.remove(tu)
        for k in ('dwear', 'dlining', 'dlen', 'drad', 'dsitx'):
            a = ob.data.attributes.get(k)
            if a:
                ob.data.attributes.remove(a)
    for ob in joined:
        if ob.data.validate(verbose=False, clean_customdata=False):
            log('validated (fixed) mesh', ob.name)
    # export
    for o in bpy.context.view_layer.objects:
        o.select_set(False)
    coll = bpy.data.collections['tandem']
    for o in coll.objects:
        o.select_set(True)
    bpy.context.view_layer.objects.active = root
    bpy.ops.export_scene.gltf(filepath=out_glb, export_format='GLB', use_selection=True, export_yup=True, export_extras=True,
                              export_attributes=True, export_image_format='AUTO', export_apply=True, export_texcoords=True,
                              export_normals=True, export_materials='EXPORT', export_cameras=False, export_lights=False,
                              export_animations=False)
    log('exported', out_glb, '%.1f MB' % (os.path.getsize(out_glb) / 1e6))
    return joined
