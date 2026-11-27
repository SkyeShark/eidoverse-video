"""eidoblend.materials.layered: ONE layered material that reads a baked asset's maps, in the order things happen to it.

    from eidoblend.materials import layered as LY
    maps = LY.load_bake('work/my_prop/bake', 'my_prop')       # normal, masks_a, masks_b, id (+ marks, relief), packed
    subs = {1: LY.Substrate(base=(0.026, 0.031, 0.033), worn=(0.70, 0.71, 0.73), base_rough=0.46, worn_metal=1.0,
                            worn_rough=0.30, wear=1.0, polish=0.6, dust=0.6, grime=0.7, grain=0, mottle=0.05, rub=1.3,
                            scratches=0.6)}
    mat = LY.baked_material('my_prop.layered', maps, subs, hands=[((-15, -40, -160), (75, 40, -45), 6.0)])
    for o in low_parts: o.data.materials.append(mat)

The maps are what blender/tools/gpu_bake.py writes from a high and its low (eidoblend.props.hardsurface): the normal
map; masks_a (AO, cavity, fine curvature); masks_b (exposed-edge nearness, broad curvature, inside-corner nearness);
the substrate ID per texel; optionally marks (markings laid at real size) and relief (moulded detail the normal map
carries). Each layer is a whole material blended over the one below by one factor, each factor from a cause:

    SUBSTRATE  chosen per texel by the baked ID through a 16 x 1 table per column (Substrate: base and worn colours,
               roughness, metalness, how much it wears, polishes, dusts and grimes, its mottle, rub and scratches);
               each takes the grain of a CC0 photograph laid in the asset's millimetres by box projection: three grain
               sets (grain 0, 1, 2; colour variation and roughness, or roughness only), any other value none
    MARKINGS   the baked marks, a pale fill under the wear
    GRIME      in the cavities, from the baked AO and cavity, darker and rougher
    WEAR       two stages from the edge map and curvature: RUB (the coating thinned paler and smoother) within about
               1.3 mm of an arris, CHIP (down to what lies beneath) within about 0.4 mm, its outline broken by a
               photographed chip pattern, only where knocks go: open places (the baked AO) and the asset's
               extremities (knocks: ramps in its millimetres)
    HANDLING   polish and fingerprints where hands go (hands: soft boxes in its millimetres)
    DUST       in the cavities and on what faces up, thin (on near-black a third opaque)
    STAINS     with their causes (stains: products of ramps, each with an amount: soot at a muzzle, behind a port)
    then cavity and AO into the colour, the normal map, and a whisper of bump for a chip's lip and the dust's film.

Every number of the stack is the Substrate's or the call's; condition scales wear, polish, dust and grime together.
NT is the node-building layer the stack is written in (maths, smoothstep, mixes, noise, the point and the normal in the
asset's space, a picture laid square through its own rectangle); asset looks use it for their own layers.
Guide: tools-guides/procedural-materials.md ("A layered material on baked maps").
"""

from __future__ import annotations

import os
from collections import namedtuple

import bpy
import numpy as np


# ------------------------------------------------------------------------------------------- the node layer ---

class NT:
    """Node-building helpers over a node tree (a material's, a world's or a group's): each returns an output socket.
    Numbers and tuples are written into inputs, sockets are linked."""

    def __init__(self, tree_, pictures=None):
        self.t, self.N, self.L = tree_, tree_.nodes, tree_.links
        self._pos = self._nrm = None
        self.pictures = pictures                                # the folder image() and picture() read from

    def put(self, sock, x):
        if isinstance(x, (int, float, tuple)):
            sock.default_value = x
        else:
            self.L.new(x, sock)

    def m(self, op, a, b=None, clamp=False):
        n = self.N.new('ShaderNodeMath')
        n.operation, n.use_clamp = op, clamp
        self.put(n.inputs[0], a)
        if b is not None:
            self.put(n.inputs[1], b)
        return n.outputs[0]

    def add(self, a, b):
        return self.m('ADD', a, b)

    def sub(self, a, b):
        return self.m('SUBTRACT', a, b)

    def mul(self, a, b, clamp=False):
        return self.m('MULTIPLY', a, b, clamp)

    def mx(self, a, b):
        return self.m('MAXIMUM', a, b)

    def mn(self, a, b):
        return self.m('MINIMUM', a, b)

    def inv(self, a):
        return self.m('SUBTRACT', 1.0, a)

    def sm(self, x, lo, hi):
        """smoothstep(lo, hi, x)"""
        n = self.N.new('ShaderNodeMapRange')
        n.interpolation_type = 'SMOOTHSTEP'
        self.put(n.inputs[0], x)
        self.put(n.inputs[1], lo)
        self.put(n.inputs[2], hi)
        return n.outputs[0]

    def lin(self, x, a0, a1, b0=0.0, b1=1.0, clamp=False):
        """x mapped linearly from a0..a1 to b0..b1"""
        n = self.N.new('ShaderNodeMapRange')
        n.clamp = clamp
        self.put(n.inputs[0], x)
        for i, v in zip((1, 2, 3, 4), (a0, a1, b0, b1)):
            n.inputs[i].default_value = v
        return n.outputs[0]

    def mixf(self, f, a, b):
        n = self.N.new('ShaderNodeMix')
        n.data_type = 'FLOAT'
        self.put(n.inputs[0], f)
        self.put(n.inputs[2], a)
        self.put(n.inputs[3], b)
        return n.outputs[0]

    def mixc(self, f, a, b):
        n = self.N.new('ShaderNodeMix')
        n.data_type = 'RGBA'
        self.put(n.inputs[0], f)
        self.put(n.inputs[6], a)
        self.put(n.inputs[7], b)
        return n.outputs[2]

    def value(self, color, v):
        """the colour's value scaled by v (Hue/Saturation/Value)"""
        n = self.N.new('ShaderNodeHueSaturation')
        self.put(n.inputs['Color'], color)
        self.put(n.inputs['Value'], v)
        return n.outputs[0]

    def obj(self):
        """the shading point in object space (metres)"""
        return self.N.new('ShaderNodeTexCoord').outputs['Object']

    def noise(self, vec, scale, detail=2.0, off=None, stretch=None, rough=0.5):
        if off is not None or stretch is not None:
            mp = self.N.new('ShaderNodeMapping')
            self.L.new(vec, mp.inputs['Vector'])
            if off is not None:
                mp.inputs['Location'].default_value = off
            if stretch is not None:
                mp.inputs['Scale'].default_value = stretch
            vec = mp.outputs[0]
        n = self.N.new('ShaderNodeTexNoise')
        n.inputs['Scale'].default_value, n.inputs['Detail'].default_value, n.inputs['Roughness'].default_value = scale, detail, rough
        self.L.new(vec, n.inputs['Vector'])
        return n.outputs[0]

    def voronoi(self, vec, scale, feature='DISTANCE_TO_EDGE', off=None):
        if off is not None:
            mp = self.N.new('ShaderNodeMapping')
            self.L.new(vec, mp.inputs['Vector'])
            mp.inputs['Location'].default_value = off
            vec = mp.outputs[0]
        n = self.N.new('ShaderNodeTexVoronoi')
        n.feature = feature
        n.inputs['Scale'].default_value = scale
        self.L.new(vec, n.inputs['Vector'])
        return n.outputs['Distance']

    def pos_mm(self):
        """the point in the asset's space, millimetres: (X, Y, Z)"""
        if self._pos is None:
            s = self.N.new('ShaderNodeVectorMath')
            s.operation = 'SCALE'
            self.L.new(self.obj(), s.inputs[0])
            s.inputs['Scale'].default_value = 1000.0
            x = self.N.new('ShaderNodeSeparateXYZ')
            self.L.new(s.outputs[0], x.inputs[0])
            self._pos = tuple(x.outputs)
        return self._pos

    def nrm(self):
        """the surface's normal in the asset's space: (x, y, z)"""
        if self._nrm is None:
            g = self.N.new('ShaderNodeNewGeometry')
            vt = self.N.new('ShaderNodeVectorTransform')
            vt.vector_type, vt.convert_from, vt.convert_to = 'NORMAL', 'WORLD', 'OBJECT'
            self.L.new(g.outputs['Normal'], vt.inputs[0])
            x = self.N.new('ShaderNodeSeparateXYZ')
            self.L.new(vt.outputs[0], x.inputs[0])
            self._nrm = tuple(x.outputs)
        return self._nrm

    def comb(self, x, y, z=0.0):
        n = self.N.new('ShaderNodeCombineXYZ')
        self.put(n.inputs[0], x)
        self.put(n.inputs[1], y)
        self.put(n.inputs[2], z)
        return n.outputs[0]

    def sep(self, sock):
        """(R, G, B) of a colour socket"""
        s = self.N.new('ShaderNodeSeparateColor')
        self.L.new(sock, s.inputs[0])
        return s.outputs

    def tex(self, im, vec, interp='Linear', proj='FLAT', blend=0.0, ext='REPEAT'):
        """an Image Texture node reading `im` at `vec`"""
        n = self.N.new('ShaderNodeTexImage')
        n.image, n.interpolation, n.projection, n.projection_blend, n.extension = im, interp, proj, blend, ext
        self.L.new(vec, n.inputs['Vector'])
        return n

    def box(self, im, vec, per_m, blend=0.25):
        """a photograph laid by box projection at `vec` (object space), per_m tiles a metre"""
        mp = self.N.new('ShaderNodeMapping')
        self.L.new(vec, mp.inputs['Vector'])
        mp.inputs['Scale'].default_value = (per_m, per_m, per_m)
        return self.tex(im, mp.outputs[0], proj='BOX', blend=blend)

    def image(self, name, vec, color=False, extend='CLIP'):
        """an image of the pictures folder, packed into the file, read at `vec`"""
        n = self.N.new('ShaderNodeTexImage')
        img = bpy.data.images.load(os.path.join(self.pictures, name), check_existing=True)
        img.colorspace_settings.name = 'sRGB' if color else 'Non-Color'
        if not img.packed_file:
            img.pack()
        n.image, n.extension, n.interpolation = img, extend, 'Cubic'
        self.L.new(vec, n.inputs['Vector'])
        return n

    def picture(self, spec, facing=None, color=False):
        """A picture drawn at real size, laid square through its own rectangle: spec {'file', 'u': [axis, mm0, mm1],
        'v': [axis, mm0, mm1]} (a rectangle given mm1 -> mm0 shows a picture drawn for the other side unmirrored);
        facing (normal's axis 0/1/2, sign): only faces that look that way. -> (the picture's node, its gate 0..1)"""
        P = self.pos_mm()
        uv = self.comb(self.lin(P['xyz'.index(spec['u'][0])], spec['u'][1], spec['u'][2]),
                       self.lin(P['xyz'.index(spec['v'][0])], spec['v'][1], spec['v'][2]))
        n = self.image(spec['file'], uv, color=color)
        gate = 1.0 if facing is None else self.sm(self.mul(self.nrm()[facing[0]], float(facing[1])), 0.6, 0.85)
        return n, gate


def new_material(name):
    """A material with only its output node, and an NT on its tree. -> (material, NT, output node)"""
    m = bpy.data.materials.new(name)
    m.use_nodes = True
    nt = m.node_tree
    for n in list(nt.nodes):
        if n.type != 'OUTPUT_MATERIAL':
            nt.nodes.remove(n)
    return m, NT(nt), next(n for n in nt.nodes if n.type == 'OUTPUT_MATERIAL')


# ------------------------------------------------------------------------------------------- the bake's maps ---

def image(path, data=True, pack=True):
    """A map or a photograph as a bpy Image (data: Non-Color), packed into the file by default."""
    im = bpy.data.images.load(os.path.abspath(path), check_existing=True)
    im.colorspace_settings.name = 'Non-Color' if data else 'sRGB'
    if pack and not im.packed_file:
        im.pack()
    return im


def load_bake(bake_dir, name, pack=True):
    """gpu_bake.py's maps of a bake as images: normal, masks_a, masks_b, id, and marks / relief when they exist."""
    out = {}
    for k in ('normal', 'masks_a', 'masks_b', 'id', 'marks', 'relief'):
        p = os.path.join(bake_dir, f'{name}_{k}.png')
        if os.path.exists(p):
            out[k] = image(p, pack=pack)
        elif k in ('normal', 'masks_a', 'masks_b', 'id'):
            raise FileNotFoundError(f'load_bake: {p} is missing (run blender/tools/gpu_bake.py --bake {bake_dir} --name {name})')
    return out


def mean_of(im, ch=None):
    """an image's mean (its luminance, or one channel), sampled every 97th pixel"""
    px = np.empty(len(im.pixels), np.float32)
    im.pixels.foreach_get(px)
    px = px.reshape(-1, 4)[::97]
    return float(px[:, :3].mean()) if ch is None else float(px[:, ch].mean())


# --------------------------------------------------------------------------------------------- the substrates ---

Substrate = namedtuple('Substrate', 'base worn base_rough base_metal worn_metal worn_rough wear polish dust grime grain '
                                    'mottle rub scratches',
                       defaults=(0.45, 0.0, 1.0, 0.30, 1.0, 0.5, 0.6, 0.7, 4, 0.05, 1.0, 0.3))
Substrate.__doc__ = """One substrate's row of the stack's tables: base / worn colours (linear RGB); base_rough,
base_metal; worn_metal, worn_rough (what a chip shows); wear, polish, dust, grime (how much of each layer it takes);
grain (0, 1, 2: the photograph grain set; 4: none); mottle (slow tone variation), rub (how much paler a rub reads),
scratches (fine scratch roughness)."""

GRAIN_SETS = (('Metal027', '2k', 0.8, 5.0, 0.35, 5.0),       # (id, res, colour power, colour tiles/m, rough amount, rough tiles/m)
              ('Metal063', '2k', 0.35, 10.0, 0.4, 6.0),      # 0 anodised aluminium's satin, 1 phosphated steel's crystal,
              ('Plastic013A', '2k', None, None, 0.5, 4.0))   # 2 moulded polymer's smudged roughness (no colour)
PHOTOS = {'fingerprints': ('Fingerprints008', '2k', 'opacity'), 'chips': ('Metal021', '2k', 'displacement'),
          'scratches': ('Metal008', '1k', 'rough')}


def _rows(substrates, condition):
    c = {'wear': 1.0, 'polish': 1.0, 'dust': 1.0, 'grime': 1.0}
    c.update(condition or {})
    rows = {}
    for i, s in substrates.items():
        s = Substrate(*s) if not isinstance(s, Substrate) else s
        rows[int(i)] = (tuple(s.base), tuple(s.worn), (s.base_rough, s.base_metal, s.worn_metal),
                        (s.worn_rough, s.wear * c['wear'], s.polish * c['polish']), (s.dust * c['dust'], s.grime * c['grime'], s.grain),
                        (s.mottle, s.rub, s.scratches))
    return rows


def table(name, rows, k):
    """A 16 x 1 lookup of one column of the substrate rows, made as DATA from the start (a generated image whose colour
    space is set after its pixels are written comes back blank), packed, read back to check."""
    im = bpy.data.images.new(name, 16, 1, alpha=True, float_buffer=True, is_data=True)
    px = np.zeros((16, 4), np.float32)
    px[:, 3] = 1.0
    for i, row in rows.items():
        v = row[k]
        px[i, :3] = (v[0], v[1], v[2] / 8.0) if k == 4 else v
    im.pixels.foreach_set(px.ravel())
    im.update()
    im.pack()
    back = np.empty(64, np.float32)
    im.pixels.foreach_get(back)
    assert np.allclose(back.reshape(16, 4)[:, :3], px[:, :3], atol=2e-3), (name, back.reshape(16, 4)[:4])
    return im


def photos(grain_sets=GRAIN_SETS, extra=PHOTOS):
    """The CC0 photographs the stack reads, fetched into the shared library on first use (harness.assets.fetch_pbr):
    {'grain': [(colour image | None, roughness image, spec)], 'fingerprints', 'chips', 'scratches': image}."""
    from ..harness import assets
    out = {'grain': []}
    for spec in grain_sets:
        f = assets.fetch_pbr(spec[0], spec[1])['files']
        out['grain'].append((image(f['diff'], data=False) if spec[2] is not None else None, image(f['rough']), spec))
    for k, (id_, res, mp) in extra.items():
        out[k] = image(assets.fetch_pbr(id_, res)['files'][mp])
    return out


# ------------------------------------------------------------------------------------------------ the stack ---

def _ramp(t, P, spec):
    """('x' | 'y' | 'z', a, b) in mm: rising smoothstep a -> b when a < b, else falling (1 - smoothstep(b, a))"""
    c = P['xyz'.index(spec[0])]
    a, b = spec[1], spec[2]
    return t.sm(c, a, b) if a < b else t.inv(t.sm(c, b, a))


def _soft_box(t, P, lo, hi, soft):
    g = 1.0
    for c, a, b in zip(P, lo, hi):
        g = t.mul(g, t.mul(t.sm(c, a - soft, a + soft), t.inv(t.sm(c, b - soft, b + soft))))
    return g


def _fold_max(t, items):
    acc = None
    for s in items:
        acc = s if acc is None else t.mx(acc, s)
    return acc


def baked_material(name, maps, substrates, photo_set=None, hands=(), knocks=(), stains=(), condition=None,
                   mark_color=(0.55, 0.55, 0.53, 1.0), dust_color=(0.40, 0.34, 0.25, 1.0),
                   soot_color=(0.012, 0.011, 0.010, 1.0), uv_map='UVMap', aovs=True):
    """The layered material (see the module doc). maps: load_bake's images; substrates: {ID: Substrate}; photo_set:
    photos()'s images (fetched when None); hands: [(lo mm, hi mm, soft mm)] soft boxes; knocks: [ramp] (an
    extremity); stains: [([ramp, ...], amount)] (a product of ramps); condition: {'wear', 'polish', 'dust', 'grime'}
    scales; aovs: the masks as AOVs (ao, cavity, curv, edge, chip, dust, hands) for probes."""
    rows = _rows(substrates, condition)
    TBL = [table(f'{name}_table_{k}', rows, k) for k in range(6)]
    PH = photo_set or photos()
    MEAN = {}
    m, t, out = new_material(name)
    uvn = t.N.new('ShaderNodeUVMap')
    uvn.uv_map = uv_map
    UV = uvn.outputs['UV']
    P = t.obj()
    X, Y, Z = t.pos_mm()
    ao, cav, cfine = t.sep(t.tex(maps['masks_a'], UV).outputs['Color'])
    edge, cbroad, _corner = t.sep(t.tex(maps['masks_b'], UV).outputs['Color'])
    markg = t.sep(t.tex(maps['marks'], UV).outputs['Color'])[0] if 'marks' in maps else 0.0
    idr = t.tex(maps['id'], UV, interp='Closest', ext='EXTEND').outputs['Color']
    idv = t.m('ROUND', t.mul(t.sep(idr)[0], 255.0 / 16.0))
    lookup = t.comb(t.mul(t.add(idv, 0.5), 1.0 / 16.0), 0.5)
    T = [t.tex(im, lookup, interp='Closest', ext='EXTEND').outputs['Color'] for im in TBL]
    base_col, worn_col = T[0], T[1]
    b_rough, b_metal, w_metal = t.sep(T[2])
    w_rough, wear_amt, pol_amt = t.sep(T[3])
    dust_amt, grime_amt, setv = t.sep(T[4])
    mottle, rub_val, scr_amt = t.sep(T[5])
    sel = t.mul(setv, 8.0)
    msk = [t.inv(t.sm(sel, 0.4, 0.6)), t.mul(t.sm(sel, 0.4, 0.6), t.inv(t.sm(sel, 1.4, 1.6))),
           t.mul(t.sm(sel, 1.4, 1.6), t.inv(t.sm(sel, 2.4, 2.6)))]
    n_macro, n_meso, n_fine = t.noise(P, 16.0, 2.0), t.noise(P, 85.0, 3.0), t.noise(P, 650.0, 2.0)
    n_gate = t.noise(P, 11.0, 2.0, off=(3.1, 1.7, 0.4))
    c_macro, c_meso, c_fine = t.sub(n_macro, 0.5), t.sub(n_meso, 0.5), t.sub(n_fine, 0.5)

    def mean(key, im):
        if key not in MEAN:
            MEAN[key] = mean_of(im)
        return MEAN[key]

    # 1. THE SUBSTRATE: tint x the photograph's own variation around 1, grain in roughness
    vs, ms, rs = [], [], []
    for g, (col_im, rgh_im, spec) in enumerate(PH['grain'][:3]):
        if col_im is not None:
            bw = t.N.new('ShaderNodeRGBToBW')
            t.L.new(t.box(col_im, P, spec[3]).outputs['Color'], bw.inputs[0])
            vs.append(t.mul(t.m('POWER', t.mul(bw.outputs[0], 1.0 / max(mean(f'c{g}', col_im), 1e-3)), spec[2]), msk[g]))
            ms.append(msk[g])
        r_ = t.sub(t.box(rgh_im, P, spec[5]).outputs['Color'], mean(f'r{g}', rgh_im))
        rs.append(t.mul(r_, t.mul(msk[g], spec[4])))
    var = t.add(_fold_and(t, vs), t.inv(_fold_and(t, ms))) if vs else 1.0
    rough = t.add(b_rough, _fold_and(t, rs)) if rs else b_rough
    colr = t.value(base_col, t.mul(var, t.add(1.0, t.add(t.mul(t.mul(c_macro, 2.0), mottle), t.mul(c_meso, mottle)))))
    rough = t.add(rough, t.add(t.mul(c_fine, 0.04), t.mul(c_macro, 0.04)))
    scr = t.sub(t.box(PH['scratches'], P, 4.0).outputs['Color'], mean('s', PH['scratches']))
    rough = t.add(rough, t.mul(scr, t.mul(scr_amt, 0.35)))
    metal = b_metal
    # 2. MARKINGS: a pale fill in the coating
    if 'marks' in maps:
        colr = t.mixc(t.mul(markg, 0.9), colr, mark_color)
        rough = t.mixf(markg, rough, 0.6)
    if 'relief' in maps:                                       # (what a texel averages away goes into roughness)
        rough = t.add(rough, t.mul(t.sep(t.tex(maps['relief'], UV).outputs['Color'])[0], 0.08))
    # 3. GRIME in the cavities
    gr = t.mul(t.add(t.mul(t.sm(t.inv(ao), 0.2, 0.7), 0.6), t.mul(t.sm(t.inv(cav), 0.1, 0.5), 0.9)),
               t.mul(grime_amt, t.add(0.6, t.mul(c_meso, 0.8))), clamp=True)
    colr = t.value(colr, t.sub(1.0, t.mul(gr, 0.6)))
    rough = t.add(rough, t.mul(gr, 0.12))
    # 4. WEAR, two stages, where knocks go
    chips = t.sub(mean('chips', PH['chips']), t.box(PH['chips'], P, 3.0, blend=0.3).outputs['Color'])
    e_rub = t.sm(edge, 0.68, 0.96)
    e_chip = t.sm(edge, 0.88, 0.99)
    drv = t.add(t.mx(e_rub, t.mul(t.sm(cfine, 0.6, 0.85), 0.9)), t.mul(t.sm(cbroad, 0.55, 0.75), 0.2))
    ends = _fold_max(t, [_ramp(t, (X, Y, Z), k) for k in knocks])
    knock = t.mul(t.sm(ao, 0.5, 0.85), t.add(0.6, t.mul(ends, 0.4)) if ends is not None else 0.6)
    gate = t.sm(n_gate, 0.35, 0.7)
    rub = t.sm(t.add(t.mul(drv, t.add(0.6, t.mul(gate, 0.5))), t.mul(c_fine, 0.2)), 0.5, 0.6)
    rub = t.mul(rub, wear_amt, clamp=True)
    chip = t.sm(t.add(t.add(t.mul(e_chip, t.mul(knock, t.add(0.5, t.mul(gate, 0.8)))), t.mul(chips, 1.0)), t.mul(c_fine, 0.2)),
                0.78, 0.84)
    chip = t.mul(chip, wear_amt, clamp=True)
    colr = t.value(colr, t.add(1.0, t.mul(rub, rub_val)))
    rough = t.add(rough, t.mul(rub, -0.07))
    colr = t.mixc(chip, colr, worn_col)
    metal = t.mixf(chip, metal, w_metal)
    rough = t.mixf(chip, rough, w_rough)
    # 5. HANDLING: polish and fingerprints where hands go
    hand = _fold_max(t, [_soft_box(t, (X, Y, Z), lo, hi, soft) for lo, hi, soft in hands])
    if hand is not None:
        fp = t.mul(t.box(PH['fingerprints'], P, 5.0).outputs['Color'], hand)
        pol = t.mul(t.mul(hand, pol_amt), t.add(0.5, t.mul(gate, 0.5)))
        rough = t.sub(rough, t.add(t.mul(pol, 0.12), t.mul(fp, t.mul(pol_amt, 0.14))))
        colr = t.value(colr, t.add(1.0, t.mul(pol, 0.08)))
    # 6. DUST: thin, in the cavities and on what faces up (the asset's own up)
    nz = t.nrm()[2]
    lay = t.mx(t.add(t.mul(t.sm(t.inv(cav), 0.12, 0.55), 0.9), t.mul(t.sm(t.inv(ao), 0.3, 0.8), 0.55)), t.mul(t.sm(nz, 0.55, 0.95), 0.25))
    dust = t.mul(t.mul(t.sm(t.add(lay, t.add(t.mul(c_fine, 0.55), t.mul(c_meso, 0.3))), 0.42, 0.78), dust_amt), t.inv(chip), clamp=True)
    colr = t.mixc(t.mul(dust, 0.5), colr, dust_color)
    rough = t.mixf(t.mul(dust, 0.7), rough, 0.9)
    metal = t.mul(metal, t.inv(t.mul(dust, 0.5)))
    # 7. STAINS with their causes
    soot = _fold_max(t, [t.mul(_fold_and(t, [_ramp(t, (X, Y, Z), r) for r in ramps], op='mul'), amount) for ramps, amount in stains])
    if soot is not None:
        st = t.sm(t.add(soot, t.mul(c_meso, 0.5)), 0.3, 0.8)
        colr = t.mixc(t.mul(st, 0.9), colr, soot_color)
        rough = t.mixf(st, rough, 0.85)
        metal = t.mul(metal, t.inv(st))
    # cavity and occlusion into the colour (EEVEE's own reaches only screen scale)
    colr = t.value(colr, t.mul(t.add(0.45, t.mul(cav, 0.55)), t.add(0.45, t.mul(ao, 0.55))))
    nm = t.N.new('ShaderNodeNormalMap')
    nm.space, nm.uv_map = 'TANGENT', uv_map
    t.L.new(t.tex(maps['normal'], UV).outputs['Color'], nm.inputs['Color'])
    h = t.add(t.sub(t.mul(dust, 6e-6), t.mul(chip, 10e-6)), t.mul(scr, t.mul(scr_amt, 2e-6)))
    bump = t.N.new('ShaderNodeBump')
    bump.inputs['Strength'].default_value, bump.inputs['Distance'].default_value = 1.0, 1.0
    t.L.new(h, bump.inputs['Height'])
    t.L.new(nm.outputs['Normal'], bump.inputs['Normal'])
    bs = t.N.new('ShaderNodeBsdfPrincipled')
    t.L.new(colr, bs.inputs['Base Color'])
    t.L.new(t.m('MINIMUM', t.m('MAXIMUM', metal, 0.0), 1.0), bs.inputs['Metallic'])
    t.L.new(t.m('MAXIMUM', rough, 0.08, clamp=True), bs.inputs['Roughness'])
    t.L.new(bump.outputs[0], bs.inputs['Normal'])
    t.L.new(bs.outputs[0], out.inputs[0])
    if aovs:
        for nm_, sock in (('ao', ao), ('cavity', cav), ('curv', cfine), ('edge', edge), ('chip', chip), ('dust', dust),
                          ('hands', hand if hand is not None else 0.0)):
            a = t.N.new('ShaderNodeOutputAOV')
            a.aov_name = nm_
            t.put(a.inputs['Value'], sock)
    return m


def _fold_and(t, items, op='add'):
    """items combined left to right by add (or mul)"""
    acc = None
    for s in items:
        acc = s if acc is None else (t.add(acc, s) if op == 'add' else t.mul(acc, s))
    return acc
