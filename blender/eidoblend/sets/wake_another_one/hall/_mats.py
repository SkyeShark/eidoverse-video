"""The hall's materials (private to the set). Every one is a CC0 scan (ambientCG, fetched by ID into the shared library
on first use: harness.assets.fetch_pbr) under LAYERS, built as one would paint it:
   1 the scan at its real size (UVs in metres), its colour brought to the paint's own colour, its roughness and normal kept;
   2 large-scale variation of value and roughness, so no tile reads as a tile;
   3 roughness breakup: smudges and scratches (the edition's generators, eidoblend.materials.procedural, at 2048 px)
     and fine procedural grain;
   4 EDGE WEAR from the vertex attribute `wear` (_kit: 1 on an arris, 0 a wear-width in), multiplied by fine noise and
     kept out of crevices by `cavity`: through the paint to primer, then to bare metal;
   5 GRIME in the crevices from the attribute `cavity` multiplied by noise (never added and thresholded);
   6 DUST on what faces up, from the world-space normal;
   7 what use leaves there, per material (the floor's lanes, joints and tyre arcs; hand polish; grease).
Procedural layers are node textures (no pixels, so nothing can show a texel); image maps are read Linear with mipmaps.

A material that must be the SAME PICTURE on every unit of a line (rollers, track frames: a top view of one unit cut
against a top view of another) takes its noise from object space only (world_var=False): every instance is identical.
"""
import math
import os

import bpy
import numpy as np

REL = None            # the folder image paths are made relative to (the .blend's), or None
LOG = print
_IMG = {}
_GEN = {}
MAPS = (('color', 'diff', 'sRGB'), ('rough', 'rough', 'Non-Color'), ('normal', 'normal', 'Non-Color'),
        ('metal', 'metal', 'Non-Color'), ('disp', 'displacement', 'Non-Color'))


def setup(blend_dir=None, log=print):
    global REL, LOG
    REL, LOG = blend_dir, log


def srgb(h):
    v = [int(h[i:i + 2], 16) / 255.0 for i in (1, 3, 5)]
    return tuple(c / 12.92 if c <= 0.04045 else ((c + 0.055) / 1.055) ** 2.4 for c in v)


# ====================================================================================================== images
def scan(set_id, res):
    """{'color', 'rough', 'normal', 'metal', 'disp', 'mean' (linear rgb of the colour map), 'rmean'} of an ambientCG set,
    fetched into the shared library once (EIDO_NO_FETCH=1 forbids the download and names the fetch command)"""
    key = (set_id, res)
    if key in _IMG:
        return _IMG[key]
    from ....harness import assets
    files = assets.fetch_pbr(set_id, res)['files']
    out = {'id': set_id, 'res': res, 'px': int(res[0]) * 1024}
    for k, lib, cs in MAPS:
        p = files.get(lib)
        if not p or not os.path.isfile(p):
            continue
        im = bpy.data.images.load(p, check_existing=True)
        im.colorspace_settings.name = cs
        if REL:
            try:
                im.filepath = bpy.path.relpath(p, start=REL)
            except ValueError:
                pass
        im.name = 'pbr_%s_%s_%s' % (set_id, res, k)
        out[k] = im
    if 'color' not in out:
        raise FileNotFoundError(f'the CC0 set {set_id} ({res}) has no colour map in the shared library')
    out['mean'] = _mean(out['color'], True)
    out['rmean'] = _mean(out['rough'], False)[0] if 'rough' in out else 0.5
    _IMG[key] = out
    LOG('   scan %s %s: colour mean (linear) %s, roughness mean %.3f' % (set_id, res, tuple(round(c, 3) for c in out['mean']), out['rmean']))
    return out


def _mean(im, is_srgb):
    c = im.copy()
    c.scale(64, 64)
    a = np.empty(64 * 64 * 4, np.float32)
    c.pixels.foreach_get(a)
    bpy.data.images.remove(c)
    a = a.reshape(-1, 4)[:, :3].astype(np.float64)
    if is_srgb:
        a = np.where(a <= 0.04045, a / 12.92, ((a + 0.055) / 1.055) ** 2.4)
    return tuple(float(v) for v in a.mean(axis=0))


def generated(kind, size=2048):
    """the edition's own generators (eidoblend.materials.procedural), once each, at 2048 px: 'scratches',
    'scratches_fine', 'smudges', 'grunge'"""
    if kind in _GEN:
        return _GEN[kind]
    from ....materials import procedural as PM
    if kind == 'scratches':
        im = PM.scratches(size, size, density=0.55, depth=0.6, name='look_scratches')
    elif kind == 'scratches_fine':
        im = PM.scratches(size, size, density=0.9, depth=0.35, name='look_scratches_fine')
    elif kind == 'smudges':
        im = PM.smudges(size, size, amount=0.55, name='look_smudges')
    elif kind == 'grunge':
        im = PM.noise(size, size, scale=9, octaves=6, contrast=0.9, warp=True, name='look_grunge')
    else:
        raise KeyError(kind)
    im.colorspace_settings.name = 'Non-Color'
    _GEN[kind] = im
    return im


# ====================================================================================================== a node language
class G:
    """node trees in a few words: every method returns an OUTPUT SOCKET; an input takes a socket or a constant"""

    def __init__(self, mat, clear=True):
        self.mat = mat
        if not mat.node_tree:
            mat.use_nodes = True
        self.t = mat.node_tree
        if clear:
            self.t.nodes.clear()
        self.k = 0
        self._tc = self._geo = None

    def node(self, kind, **kw):
        n = self.t.nodes.new(kind)
        n.location = (230 * (self.k % 14), -190 * (self.k // 14))
        self.k += 1
        for a, v in kw.items():
            setattr(n, a, v)
        return n

    def put(self, sock, v):
        if v is None:
            return
        if isinstance(v, bpy.types.NodeSocket):
            self.t.links.new(v, sock)
            return
        if sock.type == 'RGBA' and not isinstance(v, (int, float)) and len(v) == 3:
            v = (*v, 1.0)
        if sock.type == 'RGBA' and isinstance(v, (int, float)):
            v = (v, v, v, 1.0)
        if sock.type == 'VECTOR' and isinstance(v, (int, float)):
            v = (v, v, v)
        sock.default_value = v

    # ---- scalars
    def math(self, op, a, b=None, c=None, clamp=False):
        n = self.node('ShaderNodeMath', operation=op, use_clamp=clamp)
        self.put(n.inputs[0], a)
        self.put(n.inputs[1], b)
        self.put(n.inputs[2], c)
        return n.outputs[0]

    def add(self, a, b):
        return self.math('ADD', a, b)

    def sub(self, a, b):
        return self.math('SUBTRACT', a, b)

    def mul(self, a, b, clamp=False):
        return self.math('MULTIPLY', a, b, clamp=clamp)

    def clamp(self, a):
        return self.math('ADD', a, 0.0, clamp=True)

    def ramp(self, x, a, b, c=0.0, d=1.0, smooth=True):
        """x from a..b -> c..d, clamped (smoothstep unless smooth=False); a > b turns it round"""
        n = self.node('ShaderNodeMapRange', interpolation_type='SMOOTHSTEP' if smooth else 'LINEAR')
        n.clamp = True
        self.put(n.inputs[0], x)
        for i, v in ((1, a), (2, b), (3, c), (4, d)):
            self.put(n.inputs[i], v)
        return n.outputs[0]

    def mixf(self, f, a, b):
        n = self.node('ShaderNodeMix', data_type='FLOAT')
        self.put(n.inputs[0], f)
        self.put(n.inputs[2], a)
        self.put(n.inputs[3], b)
        return n.outputs[0]

    # ---- colours and vectors
    def mixc(self, f, a, b, blend='MIX'):
        n = self.node('ShaderNodeMix', data_type='RGBA')
        n.blend_type = blend
        n.clamp_factor = True
        self.put(n.inputs[0], f)
        self.put(n.inputs[6], a)
        self.put(n.inputs[7], b)
        return n.outputs[2]

    def scale(self, v, s):
        n = self.node('ShaderNodeVectorMath', operation='SCALE')
        self.put(n.inputs[0], v)
        self.put(n.inputs[3], s)
        return n.outputs[0]

    def vmath(self, op, a, b=None):
        n = self.node('ShaderNodeVectorMath', operation=op)
        self.put(n.inputs[0], a)
        self.put(n.inputs[1], b)
        return n.outputs['Value'] if op in ('LENGTH', 'DOT_PRODUCT', 'DISTANCE') else n.outputs[0]

    def xyz(self, v):
        n = self.node('ShaderNodeSeparateXYZ')
        self.put(n.inputs[0], v)
        return n.outputs[0], n.outputs[1], n.outputs[2]

    def vec(self, x=0.0, y=0.0, z=0.0):
        n = self.node('ShaderNodeCombineXYZ')
        self.put(n.inputs[0], x)
        self.put(n.inputs[1], y)
        self.put(n.inputs[2], z)
        return n.outputs[0]

    def rotz(self, v, angle):
        n = self.node('ShaderNodeVectorRotate', rotation_type='Z_AXIS')
        self.put(n.inputs['Vector'], v)
        self.put(n.inputs['Angle'], angle)
        return n.outputs[0]

    def hsv(self, c, sat=1.0, val=1.0):
        n = self.node('ShaderNodeHueSaturation')
        self.put(n.inputs['Saturation'], sat)
        self.put(n.inputs['Value'], val)
        self.put(n.inputs['Color'], c)
        return n.outputs[0]

    # ---- inputs
    def tc(self, name):
        if self._tc is None:
            self._tc = self.node('ShaderNodeTexCoord')
        return self._tc.outputs[name]

    def geo(self, name):
        if self._geo is None:
            self._geo = self.node('ShaderNodeNewGeometry')
        return self._geo.outputs[name]

    def attr(self, name):
        return self.node('ShaderNodeAttribute', attribute_type='GEOMETRY', attribute_name=name).outputs['Factor']

    # ---- textures
    def noise(self, v, scale, detail=2.0, rough=0.5, dims='3D', distortion=0.0, lac=2.0):
        n = self.node('ShaderNodeTexNoise', noise_dimensions=dims)
        self.put(n.inputs['Vector'], v)
        for k, x in (('Scale', scale), ('Detail', detail), ('Roughness', rough), ('Distortion', distortion), ('Lacunarity', lac)):
            self.put(n.inputs[k], x)
        return n.outputs['Factor']

    def voronoi(self, v, scale, feature='F1', random=1.0, out='Distance'):
        n = self.node('ShaderNodeTexVoronoi', feature=feature)
        self.put(n.inputs['Vector'], v)
        self.put(n.inputs['Scale'], scale)
        self.put(n.inputs['Randomness'], random)
        return n.outputs[out]

    def white(self, v):
        n = self.node('ShaderNodeTexWhiteNoise', noise_dimensions='3D')
        self.put(n.inputs['Vector'], v)
        return n.outputs['Value']

    def img(self, image, v, alpha=False):
        n = self.node('ShaderNodeTexImage', image=image, interpolation='Linear', extension='REPEAT')
        self.put(n.inputs[0], v)
        return n.outputs['Alpha' if alpha else 'Color']

    def normal_map(self, colour, strength=1.0, space='TANGENT'):
        n = self.node('ShaderNodeNormalMap', space=space)
        if space == 'TANGENT':
            n.uv_map = 'UVMap'
        self.put(n.inputs['Strength'], strength)
        self.put(n.inputs['Color'], colour)
        return n.outputs[0]

    def bump(self, height, distance=0.001, strength=1.0, normal=None):
        n = self.node('ShaderNodeBump')
        self.put(n.inputs['Strength'], strength)
        self.put(n.inputs['Distance'], distance)
        self.put(n.inputs['Height'], height)
        self.put(n.inputs['Normal'], normal)
        return n.outputs[0]

    def ao(self, distance=0.1):
        n = self.node('ShaderNodeAmbientOcclusion')
        n.inputs['Distance'].default_value = distance
        return n.outputs['AO']

    # ---- the end
    def principled(self, colour, rough, metal=0.0, normal=None, **more):
        b = self.node('ShaderNodeBsdfPrincipled')
        o = self.node('ShaderNodeOutputMaterial')
        self.put(b.inputs['Base Color'], colour)
        self.put(b.inputs['Roughness'], rough)
        self.put(b.inputs['Metallic'], metal)
        self.put(b.inputs['Normal'], normal)
        for k, v in more.items():
            self.put(b.inputs[k], v)
        self.t.links.new(b.outputs[0], o.inputs['Surface'])
        return b


def material(name):
    """the material of that name (the layout's, rebuilt in place, or a new one)"""
    m = bpy.data.materials.get(name) or bpy.data.materials.new(name)
    m['look'] = 'eidoblend.sets.wake_another_one.hall'
    return m


# ====================================================================================================== the layered kind
def layered(name, scan_id=None, res='2k', tile=0.6, tint=None, rough=0.45, metal=0.0, normal=0.6, var=1.0, world_var=True,
            chips=None, polish=0.0, dirt=0.5, dirt_col=(0.055, 0.048, 0.040), dust=0.3, dust_col=(0.50, 0.48, 0.45),
            scratches=0.3, smudges=0.3, spangle=0.0, grain=1.0, coat=0.0, post=None, rough_span=1.0, uv_rot=0.0, fine=1.0):
    """A scan under the layers of this file's head. tint: the paint's linear colour (the scan's variation is kept, its
    mean moved to the tint). chips: {'amount', 'primer', 'metal', 'metal_rough'} wears paint through on the arrises.
    polish: bare metal burnished on its arrises. spangle: zinc crystals (galvanized steel). post(g, S, X): a hook that
    may change S = {'C', 'R', 'M', 'H'} (colour, roughness, metallic, a height in metres for the bump) before the BSDF.
    fine < 1 lays the two generated maps smaller, for what a lens meets at a hand's width"""
    mat = material(name)
    g = G(mat)
    uv = g.tc('UV')
    if uv_rot:
        uv = g.rotz(uv, uv_rot)
    P = g.tc('Object')
    PV = g.geo('Position') if world_var else P
    n_macro = g.noise(PV, 0.55, 3.0, 0.55)
    n_mid = g.noise(P, 11.0, 3.0, 0.6)
    n_fine = g.noise(P, 130.0, 2.0, 0.6)
    S = {}
    if scan_id:
        sc = scan(scan_id, res)
        suv = g.scale(uv, 1.0 / tile)
        c0 = g.img(sc['color'], suv)
        if tint is not None:
            k = tuple(tint[i] / max(sc['mean'][i], 1e-3) for i in range(3))
            S['C'] = g.mixc(1.0, c0, k, 'MULTIPLY')
        else:
            S['C'] = c0
        r0 = g.img(sc['rough'], suv) if 'rough' in sc else sc['rmean']
        S['R'] = g.math('MULTIPLY_ADD', g.sub(r0, sc['rmean']), rough_span * rough / max(sc['rmean'], 0.05), rough)
        nrm = g.normal_map(g.img(sc['normal'], suv), normal) if ('normal' in sc and normal) else None
        if metal == 'map' and 'metal' in sc:
            S['M'] = g.img(sc['metal'], suv)
        else:
            S['M'] = float(metal) if metal != 'map' else 1.0
    else:
        S['C'], S['R'], S['M'], nrm = (tint or (0.5, 0.5, 0.5)), rough, float(metal), None
    S['H'] = 0.0
    wear, cav = g.attr('wear'), g.attr('cavity')
    # 2 large-scale variation
    if var:
        S['C'] = g.scale(S['C'], g.ramp(n_macro, 0.25, 0.75, 1.0 - 0.07 * var, 1.0 + 0.07 * var))
        S['R'] = g.add(S['R'], g.ramp(n_macro, 0.2, 0.8, -0.05 * var, 0.05 * var))
    # zinc spangle: crystals a couple of centimetres across, each its own brightness and sheen
    if spangle:
        cell = g.voronoi(P, 62.0, 'F1', 1.0, 'Color')
        cv = g.xyz(cell)[0]
        S['C'] = g.scale(S['C'], g.ramp(cv, 0.0, 1.0, 1.0 - 0.16 * spangle, 1.0 + 0.10 * spangle, smooth=False))
        S['R'] = g.add(S['R'], g.ramp(cv, 0.0, 1.0, -0.07 * spangle, 0.09 * spangle, smooth=False))
        bloom = g.mul(g.ramp(g.noise(PV, 2.3, 4.0, 0.65), 0.52, 0.75), 0.5 * spangle)          # white rust: pale matt blooms
        S['C'] = g.mixc(bloom, S['C'], (0.62, 0.63, 0.64))
        S['R'] = g.mixf(bloom, S['R'], 0.72)
        S['M'] = g.mixf(bloom, S['M'], 0.55) if isinstance(S['M'], bpy.types.NodeSocket) else g.mixf(bloom, S['M'], 0.55 * S['M'])
    # 3 roughness breakup
    if smudges:
        sm = g.img(generated('smudges'), g.scale(uv, 1.0 / (0.45 * fine)))
        S['R'] = g.add(S['R'], g.ramp(sm, 0.0, 1.0, -0.10 * smudges, 0.16 * smudges, smooth=False))
    if scratches:
        sr = g.img(generated('scratches'), g.scale(g.rotz(uv, 0.7), 1.0 / (0.52 * fine)))
        S['R'] = g.add(S['R'], g.mul(sr, 0.30 * scratches))
        S['C'] = g.scale(S['C'], g.ramp(sr, 0.0, 1.0, 1.0, 1.0 + 0.22 * scratches, smooth=False))
        S['H'] = g.mul(sr, -0.00004 * scratches)
    if grain:
        S['R'] = g.add(S['R'], g.ramp(n_fine, 0.25, 0.75, -0.035 * grain, 0.035 * grain))
    # 4 edge wear, kept out of crevices
    weff = g.mul(wear, g.ramp(cav, 0.25, 0.7, 1.0, 0.0))
    if chips:
        a = chips.get('amount', 0.5)
        cn = g.add(g.mul(g.noise(P, 260.0, 3.0, 0.65), 0.6), g.mul(g.noise(P, 37.0, 2.0, 0.5), 0.55))      # 0 .. 1.15
        x = g.mul(weff, g.ramp(cn, 0.25, 0.85, 0.15, 1.25, smooth=False))
        dings = g.mul(g.ramp(g.noise(P, 70.0, 4.0, 0.7), 0.74 - 0.05 * a, 0.78 - 0.05 * a), 0.9 * min(1.0, a * 1.4))  # sparse knocks
        x = g.math('MAXIMUM', x, dings)
        t1 = 1.02 - 0.5 * a
        pm = g.ramp(x, t1 - 0.22, t1 - 0.16)                 # the primer's rim
        mm = g.ramp(x, t1 - 0.05, t1 + 0.01)                 # bare metal inside it
        S['C'] = g.mixc(pm, S['C'], chips.get('primer', (0.33, 0.34, 0.35)))
        S['C'] = g.mixc(mm, S['C'], chips.get('metal', (0.56, 0.57, 0.58)))
        S['R'] = g.mixf(pm, S['R'], 0.62)
        S['R'] = g.mixf(mm, S['R'], chips.get('metal_rough', 0.34))
        S['M'] = g.mixf(mm, S['M'], 1.0)
        S['H'] = g.add(S['H'], g.mul(g.add(pm, mm), -0.00006))
    if polish:
        pol = g.mul(weff, g.ramp(n_mid, 0.2, 0.8, 0.35, 1.0))
        S['R'] = g.mixf(g.mul(pol, polish), S['R'], g.mul(S['R'], 0.55))
        S['C'] = g.scale(S['C'], g.ramp(pol, 0.0, 1.0, 1.0, 1.0 + 0.22 * polish, smooth=False))
    # 5 grime where the surface is closed in
    if dirt:
        dm = g.mul(g.mul(g.ramp(cav, 0.12, 0.8), g.ramp(n_mid, 0.15, 0.85, 0.3, 1.0)), min(1.0, dirt))
        S['C'] = g.mixc(g.mul(dm, 0.8), S['C'], dirt_col)
        S['R'] = g.mixf(dm, S['R'], 0.82)
        S['M'] = g.mixf(g.mul(dm, 0.8), S['M'], 0.0)
    # 6 dust on what faces up
    if dust:
        nz = g.xyz(g.geo('Normal'))[2]
        up = g.mul(g.math('POWER', g.clamp(nz), 3.0), g.ramp(g.noise(PV, 4.5, 3.0, 0.6), 0.2, 0.8, 0.35, 1.0))
        up = g.mul(up, dust)
        S['C'] = g.mixc(g.mul(up, 0.55), S['C'], dust_col)
        S['R'] = g.mixf(g.mul(up, 0.8), S['R'], 0.9)
        S['M'] = g.mixf(g.mul(up, 0.5), S['M'], 0.0)
    if post:
        post(g, S, dict(P=P, PV=PV, uv=uv, wear=weff, cav=cav, n_mid=n_mid, n_fine=n_fine, n_macro=n_macro))
    S['R'] = g.math('MAXIMUM', g.math('MINIMUM', S['R'], 0.97), 0.045)
    S['H'] = g.add(S['H'], g.mul(g.noise(P, 900.0, 2.0, 0.5), 0.000012 * grain))
    nrm = g.bump(S['H'], distance=1.0, strength=1.0, normal=nrm)
    extra = {}
    if coat:
        extra = {'Coat Weight': coat, 'Coat Roughness': 0.08}
    g.principled(S['C'], S['R'], S['M'], nrm, **extra)
    return mat


# ====================================================================================================== the floor
def floor(name, L, racks_x, lanes, joints=6.0):
    """Polished concrete: the scan read twice at scales that never agree (3 m and 4.1 m, turned), each slab a pour of
    its own, saw-cut joints, lanes that traffic has polished and marked, dust and a grime line where no sweeper reaches
    under the racks, tyre arcs at the dock, a sealer coat. Everything is laid out in WORLD metres from the layout"""
    mat = material(name)
    g = G(mat)
    s4 = scan('Concrete034', '4k')
    P = g.geo('Position')
    x, y, _z = g.xyz(P)
    uva = g.scale(P, 1.0 / 3.0)
    uvb = g.vmath('ADD', g.scale(g.rotz(P, 0.61), 1.0 / 4.1), (0.37, 0.11, 0.0))
    blend = g.ramp(g.noise(P, 0.23, 2.0, 0.5), 0.38, 0.62)
    k = 0.31 / max(sum(s4['mean']) / 3, 1e-3)
    c = g.scale(g.mixc(blend, g.img(s4['color'], uva), g.img(s4['color'], uvb)), k)
    r0 = g.mixf(blend, g.img(s4['rough'], uva), g.img(s4['rough'], uvb))
    # each slab its own pour; a slow drift over tens of metres
    jx, jy = g.math('DIVIDE', g.sub(x, 3.0), joints), g.math('DIVIDE', g.sub(y, 3.0), joints)
    cell = g.vec(g.math('FLOOR', jx), g.math('FLOOR', jy), 0.0)
    slab = g.white(cell)
    slab2 = g.white(g.vmath('ADD', cell, (17.0, 5.0, 0.0)))
    c = g.scale(c, g.ramp(slab, 0.0, 1.0, 0.89, 1.10, smooth=False))
    c = g.scale(c, g.ramp(g.noise(P, 0.05, 2.0, 0.5), 0.3, 0.7, 0.90, 1.10))
    # a pour is darker where its water stood longest: slow clouds inside each slab, a paler margin along its edges
    c = g.scale(c, g.ramp(g.noise(P, 0.42, 3.0, 0.6), 0.25, 0.75, 0.93, 1.06))
    R = g.math('MULTIPLY_ADD', g.sub(r0, s4['rmean']), 0.55, 0.21)
    R = g.add(R, g.ramp(g.noise(P, 1.3, 3.0, 0.6), 0.25, 0.75, -0.05, 0.06))                    # the sealer's own mottle
    R = g.add(R, g.ramp(slab2, 0.0, 1.0, -0.05, 0.07, smooth=False))                            # every pour took its polish differently
    # saw-cut joints every `joints` metres (offset so one runs down the station's aisle and none under the hero track):
    # the cut and its grey sealant (8 mm), the arris spalled in places, the film a scrubber leaves along it
    dx = g.mul(g.math('ABSOLUTE', g.sub(g.math('FRACT', jx), 0.5)), joints)
    dy = g.mul(g.math('ABSOLUTE', g.sub(g.math('FRACT', jy), 0.5)), joints)
    dj = g.sub(joints / 2.0, g.math('MAXIMUM', dx, dy))      # metres to the nearest joint
    jm = g.ramp(dj, 0.0032, 0.0048, 1.0, 0.0)
    spall = g.mul(g.ramp(dj, 0.0045, 0.016, 1.0, 0.0), g.ramp(g.noise(P, 70.0, 3.0, 0.7), 0.56, 0.68))
    jh = g.mul(g.ramp(dj, 0.004, 0.085, 1.0, 0.0), g.ramp(g.noise(P, 5.0, 3.0, 0.6), 0.3, 0.8, 0.25, 1.0))
    margin = g.ramp(dj, 0.05, 0.45, 1.0, 0.0)                # the slab's paler, more open edge
    # lanes: where people and wheels go
    lane = None
    for cx, half in lanes['fixed']:
        m = g.ramp(g.math('ABSOLUTE', g.sub(x, cx)), half * 0.45, half, 1.0, 0.0)
        lane = m if lane is None else g.math('MAXIMUM', lane, m)
    if lanes.get('periodic'):
        x0, pitch, half, x_max = lanes['periodic']
        dper = g.mul(g.math('ABSOLUTE', g.sub(g.math('FRACT', g.add(g.math('DIVIDE', g.sub(x, x0), pitch), 0.5)), 0.5)), pitch)
        m = g.mul(g.ramp(dper, half * 0.45, half, 1.0, 0.0), g.ramp(x, x_max - 0.2, x_max + 0.2, 1.0, 0.0))
        lane = g.math('MAXIMUM', lane, m)
    for (cx0, cx1, cy, half) in lanes.get('cross', []):       # the cross aisle at the dock end, and its like
        m = g.mul(g.ramp(g.math('ABSOLUTE', g.sub(y, cy)), half * 0.45, half, 1.0, 0.0),
                  g.mul(g.ramp(x, cx0 - 1.0, cx0 + 1.0), g.ramp(x, cx1 - 1.0, cx1 + 1.0, 1.0, 0.0)))
        lane = g.math('MAXIMUM', lane, m)
    edge = g.mul(g.ramp(lane, 0.02, 0.35), g.ramp(lane, 0.35, 0.9, 1.0, 0.0))                  # where the dust is pushed to
    streak = g.noise(g.vec(g.mul(x, 5.0), g.mul(y, 0.11), 0.0), 1.0, 3.0, 0.6)
    lm = g.mul(lane, g.ramp(streak, 0.2, 0.8, 0.45, 1.0))
    # rubber: long straight marks down the lane, and the S of a truck that weaves (the lane's own coordinate bent)
    xw = g.add(x, g.mul(g.math('SINE', g.mul(y, 0.31)), 0.55))
    wheel = g.math('MAXIMUM', g.ramp(g.noise(g.vec(g.mul(x, 19.0), g.mul(y, 0.03), 7.0), 1.0, 2.0, 0.5), 0.66, 0.74),
                   g.ramp(g.noise(g.vec(g.mul(xw, 13.0), g.mul(y, 0.045), 23.0), 1.0, 2.0, 0.5), 0.70, 0.77))
    wheel = g.mul(g.mul(wheel, lane), g.ramp(g.noise(P, 0.45, 2.0, 0.5), 0.38, 0.66))
    # under the racks, their foot line, and the pale scrapes where loads are dragged out across the face
    under, foot, scrape = None, None, None
    for a, b, faces in racks_x:
        u = g.mul(g.ramp(x, a - 0.04, a + 0.04), g.ramp(x, b - 0.04, b + 0.04, 1.0, 0.0))
        under = u if under is None else g.math('MAXIMUM', under, u)
        for fx in faces:
            dfx = g.math('ABSOLUTE', g.sub(x, fx))
            f = g.ramp(dfx, 0.015, 0.10, 1.0, 0.0)
            foot = f if foot is None else g.math('MAXIMUM', foot, f)
            s = g.ramp(dfx, 0.10, 0.75, 1.0, 0.0)
            scrape = s if scrape is None else g.math('MAXIMUM', scrape, s)
    foot = g.mul(foot, g.ramp(g.noise(g.vec(g.mul(x, 9.0), g.mul(y, 1.7), 3.0), 1.0, 3.0, 0.6), 0.25, 0.8, 0.25, 1.0))
    scrape = g.mul(g.mul(scrape, g.ramp(under, 0.0, 0.5, 1.0, 0.0)),
                   g.mul(g.ramp(g.noise(g.vec(g.mul(x, 1.1), g.mul(y, 46.0), 11.0), 1.0, 2.0, 0.5), 0.63, 0.72),
                         g.ramp(g.noise(P, 1.9, 2.0, 0.5), 0.42, 0.62)))
    # tyre arcs where things turn at the dock
    dk = L['dock']
    cdoor = ((dk['door_x'][0] + dk['door_x'][1]) / 2, dk['wall_y'] + 5.0, 0.0)
    rad = g.vmath('DISTANCE', P, cdoor)
    arcs = g.ramp(g.noise(g.vec(g.mul(rad, 7.5), g.mul(g.add(x, y), 0.09), 2.0), 1.0, 2.0, 0.5), 0.66, 0.74)
    arcs = g.mul(g.mul(arcs, g.ramp(y, dk['wall_y'] - 11.0, dk['wall_y'] - 3.5)), g.ramp(g.noise(P, 0.8, 2.0, 0.5), 0.36, 0.62))
    arcs = g.mul(arcs, g.ramp(under, 0.0, 0.5, 1.0, 0.0))
    scr = g.img(generated('scratches_fine'), g.scale(g.rotz(P, 0.33), 1.0 / 1.45))
    # colour
    c = g.mixc(g.mul(margin, 0.10), c, g.scale(c, 1.12))
    c = g.mixc(g.mul(lm, 0.55), c, g.scale(c, 0.78))
    c = g.mixc(g.mul(edge, 0.30), c, (0.36, 0.35, 0.33))
    c = g.mixc(g.mul(wheel, 0.62), c, (0.035, 0.033, 0.030))
    c = g.mixc(g.mul(under, 0.38), c, (0.40, 0.385, 0.36))
    c = g.mixc(g.mul(foot, 0.62), c, (0.075, 0.068, 0.060))
    c = g.mixc(g.mul(scrape, 0.55), c, (0.50, 0.49, 0.47))
    c = g.mixc(g.mul(arcs, 0.68), c, (0.032, 0.030, 0.028))
    c = g.mixc(g.mul(jh, 0.36), c, g.scale(c, 0.68))
    c = g.mixc(g.mul(spall, 0.7), c, g.scale(c, 0.45))
    c = g.mixc(jm, c, (0.060, 0.060, 0.062))
    # roughness
    R = g.sub(R, g.mul(lm, 0.10))
    R = g.add(R, g.mul(edge, 0.16))
    R = g.add(R, g.mul(g.mul(scr, 0.18), g.ramp(lane, 0.0, 1.0, 0.35, 1.0)))
    R = g.add(R, g.mul(wheel, 0.24))
    R = g.add(R, g.mul(under, 0.30))
    R = g.add(R, g.mul(foot, 0.36))
    R = g.add(R, g.mul(scrape, 0.34))
    R = g.add(R, g.mul(arcs, 0.26))
    R = g.add(R, g.mul(jh, 0.14))
    R = g.add(R, g.mul(margin, 0.05))
    R = g.mixf(spall, R, 0.8)
    R = g.mixf(jm, R, 0.62)
    R = g.math('MAXIMUM', g.math('MINIMUM', R, 0.95), 0.07)
    # relief: the scan's own (its tangent frame IS the floor's world frame), the joints, pores
    nrm = g.normal_map(g.img(s4['normal'], uva), 0.32, 'OBJECT')
    H = g.add(g.add(g.mul(jm, -0.0026), g.mul(spall, -0.0018)), g.mul(g.noise(P, 760.0, 2.0, 0.5), 0.00005))
    nrm = g.bump(H, distance=1.0, strength=1.0, normal=nrm)
    coat = g.mul(g.mul(g.ramp(under, 0.0, 1.0, 0.36, 0.06), g.ramp(g.math('MAXIMUM', jm, spall), 0.0, 1.0, 1.0, 0.0)),
                 g.ramp(g.add(edge, scrape), 0.0, 1.0, 1.0, 0.45))
    coat_r = g.add(g.add(0.085, g.mul(scr, 0.10)), g.mul(wheel, 0.2))
    g.principled(c, R, 0.0, nrm, **{'Coat Weight': coat, 'Coat Roughness': coat_r})
    return mat


def floor_paint(name, colour=(0.70, 0.71, 0.70), stripes=None, floor_mat_scan=('Concrete034', '4k')):
    """the painted floor lines: a traffic paint worn through to the concrete in patches (the same scan at the same world
    place as the floor under it, so a worn patch IS the floor)"""
    mat = material(name)
    g = G(mat)
    s4 = scan(*floor_mat_scan)
    P = g.geo('Position')
    x, y, _z = g.xyz(P)
    k = 0.31 / max(sum(s4['mean']) / 3, 1e-3)
    conc = g.scale(g.img(s4['color'], g.scale(P, 1.0 / 3.0)), k)
    # THE MESH'S UV: u = metres in from the line's nearer edge (0 on both edges), v = metres along the line
    u, v, _w = g.xyz(g.tc('UV'))
    fine = g.noise(P, 55.0, 3.0, 0.6)
    ragged = g.ramp(g.add(u, g.mul(g.sub(fine, 0.5), 0.014)), 0.0005, 0.0035)                   # the chipped edge: 0 outside the paint
    thin = g.ramp(u, 0.0, 0.02, 0.35, 0.0)                                                    # the paint is thinner toward its edges
    ride = g.noise(g.vec(g.mul(u, 70.0), g.mul(v, 0.9), 5.0), 1.0, 3.0, 0.6)                    # wheels riding ALONG the line
    cross = g.noise(g.vec(g.mul(v, 2.3), 0.0, 9.0), 1.0, 2.0, 0.5, dims='3D')                   # places where traffic CROSSES it
    wn = g.add(g.add(g.mul(g.noise(P, 6.0, 4.0, 0.7), 0.45), g.mul(fine, 0.30)), g.add(g.mul(ride, 0.35), thin))
    worn = g.ramp(g.add(wn, g.mul(g.ramp(cross, 0.5, 0.75), 0.32)), 0.74, 0.84)
    scuff = g.ramp(g.noise(g.vec(g.mul(x, 14.0), g.mul(y, 0.5), 0.0), 1.0, 3.0, 0.6), 0.45, 0.8)
    rubber = g.mul(g.ramp(g.noise(g.vec(g.mul(u, 6.0), g.mul(v, 31.0), 3.0), 1.0, 2.0, 0.5), 0.68, 0.76), g.ramp(cross, 0.45, 0.7))
    paint = g.scale(tuple(colour), g.ramp(scuff, 0.0, 1.0, 1.0, 0.76))
    if stripes:                                              # black-and-yellow: diagonal bands, `stripes` metres from one to the next
        sb = g.ramp(g.math('ABSOLUTE', g.sub(g.math('FRACT', g.math('DIVIDE', g.add(x, y), stripes)), 0.5)), 0.245, 0.255)
        paint = g.mixc(sb, paint, (0.03, 0.03, 0.032))
    paint = g.mixc(g.mul(rubber, 0.7), paint, (0.04, 0.04, 0.04))
    gone = g.math('MAXIMUM', worn, g.sub(1.0, ragged))
    c = g.mixc(gone, paint, conc)
    R = g.mixf(gone, g.add(g.add(0.40, g.mul(scuff, 0.2)), g.mul(rubber, 0.2)), 0.24)
    H = g.mul(gone, -0.0004)
    g.principled(c, R, 0.0, g.bump(H, distance=1.0))
    return mat


# ====================================================================================================== the shell
def wall_liner(name, sheet=1.0, lap_v=7.6, scuff=True, value=0.72):
    """profiled steel liner sheets, the hall's inner skin above the concrete dado. THE RIBS ARE GEOMETRY (_shell's
    ribbed sheet); the mesh's UV is (metres along the wall, height). Over the scan: every sheet its own tone, the side
    laps (a hairline at a rib each `sheet` metres), the horizontal lap at lap_v with the weep runs under its fixings, a
    scuffed band over the dado, and a slow drift so a long wall is never one value"""
    mat = material(name)
    g = G(mat)
    sc = scan('Metal049A', '2k')
    uvn = g.tc('UV')
    u, v, _w = g.xyz(uvn)
    P = g.geo('Position')
    uv = g.scale(uvn, 1.0 / 0.9)
    k = tuple(value * t / max(m, 1e-3) for t, m in zip((1.0, 1.01, 1.015), sc['mean']))
    c = g.mixc(1.0, g.img(sc['color'], uv), k, 'MULTIPLY')
    R = g.math('MULTIPLY_ADD', g.sub(g.img(sc['rough'], uv), sc['rmean']), 0.8, 0.40)
    upper = g.ramp(v, lap_v - 0.001, lap_v + 0.001, smooth=False)
    tone = g.white(g.vec(g.math('FLOOR', g.math('DIVIDE', u, sheet)), upper, 0.0))
    c = g.scale(c, g.ramp(tone, 0.0, 1.0, 0.955, 1.035, smooth=False))
    c = g.scale(c, g.ramp(g.noise(P, 0.045, 2.0, 0.5), 0.3, 0.7, 0.93, 1.05))
    side = g.mul(g.math('ABSOLUTE', g.sub(g.math('FRACT', g.math('DIVIDE', u, sheet)), 0.5)), sheet)
    side = g.ramp(g.sub(sheet / 2.0, side), 0.0008, 0.0022, 1.0, 0.0)
    lap = g.ramp(g.math('ABSOLUTE', g.sub(v, lap_v)), 0.0015, 0.004, 1.0, 0.0)
    lap_sh = g.mul(g.ramp(g.sub(lap_v, v), 0.0, 0.035, 1.0, 0.0), g.ramp(v, lap_v - 0.036, lap_v, 0.0, 1.0, smooth=False))
    runs = g.mul(g.ramp(g.noise(g.vec(g.mul(u, 11.0), g.mul(v, 0.22), 0.0), 1.0, 3.0, 0.6), 0.56, 0.82),
                 g.mul(g.ramp(v, lap_v - 3.2, lap_v, 0.0, 1.0), g.ramp(v, lap_v, lap_v + 0.01, 1.0, 0.0)))
    low = g.mul(g.ramp(v, 2.4, 3.3, 1.0 if scuff else 0.0, 0.0),
                g.ramp(g.noise(g.vec(g.mul(u, 2.2), g.mul(v, 2.2), 1.0), 1.0, 4.0, 0.65), 0.3, 0.75, 0.15, 1.0))
    sm = g.img(generated('smudges'), g.scale(uvn, 1.0 / 1.7))
    c = g.mixc(g.mul(runs, 0.13), c, (0.22, 0.21, 0.19))
    c = g.mixc(g.mul(low, 0.30), c, (0.30, 0.29, 0.27))
    c = g.mixc(g.mul(lap_sh, 0.25), c, g.scale(c, 0.6))
    c = g.mixc(g.math('MAXIMUM', side, lap), c, g.scale(c, 0.32))
    R = g.add(R, g.add(g.mul(low, 0.2), g.mul(runs, 0.14)))
    R = g.add(R, g.ramp(sm, 0.0, 1.0, -0.07, 0.10, smooth=False))
    R = g.add(R, g.ramp(g.noise(P, 0.6, 3.0, 0.6), 0.2, 0.8, -0.05, 0.05))
    H = g.add(g.mul(g.math('MAXIMUM', side, lap), -0.0012), g.mul(g.noise(P, 700.0, 2.0, 0.5), 0.00001))
    g.principled(c, g.math('MAXIMUM', g.math('MINIMUM', R, 0.95), 0.12), 0.0,
                 g.bump(H, distance=1.0, normal=g.normal_map(g.img(sc['normal'], uv), 0.25)))
    return mat


def dado(g, S, X):
    """a precast concrete dado: the pale bloom of its casting in slow vertical drifts, form-oil stains, and the dark band
    that mops, pallets and tyres leave along its foot"""
    x, y, z = g.xyz(g.geo('Position'))
    drift = g.noise(g.vec(g.mul(g.add(x, y), 0.9), g.mul(z, 0.18), 3.0), 1.0, 3.0, 0.6)
    S['C'] = g.scale(S['C'], g.ramp(drift, 0.25, 0.75, 0.90, 1.08))
    foot = g.mul(g.ramp(z, 0.02, 0.32, 1.0, 0.0), g.ramp(X['n_mid'], 0.2, 0.8, 0.45, 1.0))
    marks = g.mul(g.ramp(g.noise(g.vec(g.mul(g.add(x, y), 1.3), g.mul(z, 22.0), 0.0), 1.0, 2.0, 0.5), 0.62, 0.72),
                  g.ramp(z, 0.05, 0.6, 1.0, 0.0))
    S['C'] = g.mixc(g.mul(foot, 0.5), S['C'], (0.10, 0.095, 0.088))
    S['C'] = g.mixc(g.mul(marks, 0.6), S['C'], (0.045, 0.043, 0.040))
    S['R'] = g.add(S['R'], g.mul(foot, 0.1))
    S['R'] = g.mixf(g.mul(marks, 0.7), S['R'], 0.5)


def field(name):
    """the open ground beyond the yard's fence: dry verge grass seen at a grazing angle from far away (a sliver of the
    frame: its colour and its breakup are what reads)"""
    mat = material(name)
    g = G(mat)
    sa = scan('Asphalt012', '2k')
    P = g.geo('Position')
    c0 = g.img(sa['color'], g.scale(P, 1.0 / 5.0))
    k = tuple(t / max(m, 1e-3) for t, m in zip((0.19, 0.17, 0.075), sa['mean']))
    c = g.mixc(1.0, c0, k, 'MULTIPLY')
    patch = g.noise(P, 0.035, 4.0, 0.6)
    c = g.mixc(g.ramp(patch, 0.35, 0.7), c, g.scale(c, 0.62))
    c = g.mixc(g.ramp(g.noise(P, 0.4, 3.0, 0.7), 0.55, 0.8), c, (0.24, 0.20, 0.11))
    g.principled(c, g.add(0.82, g.mul(patch, 0.12)), 0.0, g.normal_map(g.img(sa['normal'], g.scale(P, 1.0 / 5.0)), 1.5, 'OBJECT'))
    return mat


def world_sky(name, hdr_path, sun_dir, gain=1.0, clamp=30.0, ground=(0.19, 0.19, 0.185), fill=0.06):
    """the photo-sky option: a CC0 sky photograph turned so that ITS sun stands where the dock's sun lamp is (sun_dir:
    the unit vector toward the sun). The picture's own sun disc is clamped out of the light (the lamp is the sun: one
    hard patch, one shadow); what is left is the sky's glow, seen whole by the lens and given as light at `fill` (at
    full strength a sky leaks into the hall through the coarse volume probe). Returns (world, the gain node, the
    picture's sun elevation in degrees)"""
    im = bpy.data.images.load(hdr_path, check_existing=True)
    if REL:
        try:
            im.filepath = bpy.path.relpath(hdr_path, start=REL)
        except ValueError:
            pass
    im.name = 'sky_' + os.path.splitext(os.path.basename(hdr_path))[0]
    small = im.copy()
    small.scale(512, 256)
    a = np.empty(512 * 256 * 4, np.float32)
    small.pixels.foreach_get(a)
    bpy.data.images.remove(small)
    lum = a.reshape(256, 512, 4)[:, :, :3].sum(axis=2)
    iy, ix = np.unravel_index(int(lum.argmax()), lum.shape)
    phi = ((ix + 0.5) / 512.0 - 0.5) * 2.0 * math.pi
    elev = ((iy + 0.5) / 256.0 - 0.5) * math.pi
    az_h = math.atan2(math.sin(phi), -math.cos(phi))             # the photograph's sun, as an angle in the XY plane
    az_s = math.atan2(sun_dir[1], sun_dir[0])
    w = bpy.data.worlds.new(name)
    if not w.node_tree:
        w.use_nodes = True
    try:
        w.sun_threshold = 0.0                                # no second sun drawn out of the picture: the lamp is the sun
    except AttributeError as ex:
        LOG('   world: %r' % ex)
    t = w.node_tree
    t.nodes.clear()
    tc = t.nodes.new('ShaderNodeTexCoord')
    mp = t.nodes.new('ShaderNodeMapping')
    mp.vector_type = 'POINT'
    mp.inputs['Rotation'].default_value = (0.0, 0.0, az_h - az_s)
    env = t.nodes.new('ShaderNodeTexEnvironment')
    env.image = im
    env.interpolation = 'Linear'
    mn = t.nodes.new('ShaderNodeMix')
    mn.data_type, mn.blend_type = 'RGBA', 'DARKEN'
    mn.inputs[0].default_value = 1.0
    mn.inputs[7].default_value = (clamp, clamp, clamp, 1.0)
    gn = t.nodes.new('ShaderNodeVectorMath')
    gn.operation, gn.name = 'SCALE', 'sky_gain'
    gn.inputs[3].default_value = gain
    sep = t.nodes.new('ShaderNodeSeparateXYZ')
    below = t.nodes.new('ShaderNodeMapRange')
    below.inputs[1].default_value, below.inputs[2].default_value = -0.03, 0.0
    grd = t.nodes.new('ShaderNodeMix')
    grd.data_type = 'RGBA'
    grd.inputs[6].default_value = (*ground, 1.0)
    bg = t.nodes.new('ShaderNodeBackground')
    out = t.nodes.new('ShaderNodeOutputWorld')
    t.links.new(tc.outputs['Generated'], mp.inputs['Vector'])
    t.links.new(mp.outputs[0], env.inputs['Vector'])
    t.links.new(env.outputs[0], mn.inputs[6])
    t.links.new(mn.outputs[2], gn.inputs[0])
    t.links.new(tc.outputs['Generated'], sep.inputs[0])
    t.links.new(sep.outputs[2], below.inputs[0])
    t.links.new(below.outputs[0], grd.inputs[0])
    t.links.new(gn.outputs[0], grd.inputs[7])
    t.links.new(grd.outputs[2], bg.inputs[0])
    lp = t.nodes.new('ShaderNodeLightPath')
    st = t.nodes.new('ShaderNodeMapRange')
    st.inputs[3].default_value, st.inputs[4].default_value = fill, 1.0
    t.links.new(lp.outputs['Is Camera Ray'], st.inputs[0])
    t.links.new(st.outputs[0], bg.inputs['Strength'])
    t.links.new(bg.outputs[0], out.inputs['Surface'])
    LOG('   sky %s: its sun at azimuth %.1f, elevation %.1f degrees; turned %.1f degrees to the dock sun'
        % (im.name, math.degrees(az_h), math.degrees(elev), math.degrees(az_h - az_s)))
    return w, gn, math.degrees(elev)


def yard(name):
    """the dock's apron: a broom-finished concrete yard in slabs of 5 m, the trucks' wheel lanes worn dark"""
    mat = material(name)
    g = G(mat)
    sc, sa = scan('Concrete034', '2k'), scan('Asphalt012', '2k')
    P = g.geo('Position')
    x, y, _z = g.xyz(P)
    uv = g.scale(P, 1.0 / 3.7)
    k = 0.27 / max(sum(sc['mean']) / 3, 1e-3)
    c = g.scale(g.img(sc['color'], uv), k)
    c = g.scale(c, g.ramp(g.noise(P, 0.06, 3.0, 0.6), 0.25, 0.75, 0.85, 1.12))
    cell = g.vec(g.math('FLOOR', g.math('DIVIDE', x, 5.0)), g.math('FLOOR', g.math('DIVIDE', y, 5.0)), 0.0)
    c = g.scale(c, g.ramp(g.white(cell), 0.0, 1.0, 0.92, 1.08, smooth=False))
    dx = g.mul(g.math('ABSOLUTE', g.sub(g.math('FRACT', g.math('DIVIDE', x, 5.0)), 0.5)), 5.0)
    dy = g.mul(g.math('ABSOLUTE', g.sub(g.math('FRACT', g.math('DIVIDE', y, 5.0)), 0.5)), 5.0)
    jm = g.ramp(g.sub(2.5, g.math('MAXIMUM', dx, dy)), 0.006, 0.012, 1.0, 0.0)
    lanes = g.mul(g.ramp(g.noise(g.vec(g.mul(x, 0.55), g.mul(y, 0.02), 4.0), 1.0, 3.0, 0.6), 0.5, 0.72),
                  g.ramp(g.noise(P, 0.4, 3.0, 0.6), 0.3, 0.7, 0.3, 1.0))
    c = g.mixc(g.mul(lanes, 0.5), c, g.scale(g.img(sa['color'], g.scale(P, 1.0 / 2.6)), 1.3))
    c = g.mixc(jm, c, g.scale(c, 0.3))
    R = g.add(g.math('MULTIPLY_ADD', g.sub(g.img(sc['rough'], uv), sc['rmean']), 0.6, 0.78), g.mul(lanes, -0.12))
    nrm = g.normal_map(g.img(sc['normal'], uv), 1.0, 'OBJECT')
    g.principled(c, g.clamp(R), 0.0, g.bump(g.mul(jm, -0.004), distance=1.0, normal=nrm))
    return mat


# ====================================================================================================== lamps and glass
def emitter(name, colour, strength, body=(0.9, 0.9, 0.9), falloff=None, back=None):
    """a lamp's diffuser: it glows (the light itself is an area light beside it); `falloff`: the UV axis (0 or 1) and
    the half width in metres across which an opal lens dims toward its edges; back: the share its back side gives"""
    one_sided = back is not None
    mat = material(name)
    g = G(mat)
    e = strength
    if falloff is not None:
        u = g.xyz(g.tc('Object'))[falloff[0]]
        e = g.mul(g.ramp(g.math('ABSOLUTE', u), falloff[1] * 0.35, falloff[1], 1.0, 0.72), strength)
    if one_sided:
        e = g.mul(g.sub(1.0, g.mul(g.geo('Backfacing'), 1.0 - back)), e)
    g.principled(body, 0.35, 0.0, None, **{'Emission Color': colour, 'Emission Strength': e})
    return mat


def frosted_office(name, colour, strength):
    """the office window: frosted glass lit from behind, the slats of a blind as faint bands, uneven where the lamp is"""
    mat = material(name)
    g = G(mat)
    P = g.geo('Position')
    _x, y, z = g.xyz(P)
    slat = g.ramp(g.math('SINE', g.mul(z, 2.0 * math.pi / 0.05)), -0.2, 0.6, 0.80, 1.0)
    pool = g.ramp(g.noise(g.vec(g.mul(y, 0.35), g.mul(z, 0.5), 0.0), 1.0, 2.0, 0.5), 0.2, 0.8, 0.55, 1.15)
    e = g.mul(g.mul(slat, pool), strength)
    R = g.add(0.5, g.mul(g.noise(P, 40.0, 3.0, 0.6), 0.2))
    c = g.mixc(g.ramp(g.noise(g.vec(g.mul(y, 3.0), g.mul(z, 0.6), 0.0), 1.0, 3.0, 0.6), 0.3, 0.7), (0.74, 0.73, 0.70), (0.80, 0.79, 0.76))
    g.principled(c, R, 0.0, g.bump(g.noise(P, 300.0, 2.0, 0.5), distance=0.00008),
                 **{'Emission Color': colour, 'Emission Strength': e})
    return mat


def glass(name, tint=(0.92, 0.96, 0.95), rough=0.03):
    mat = material(name)
    g = G(mat)
    sm = g.img(generated('smudges'), g.scale(g.tc('Object'), 1.0 / 0.25))
    R = g.add(rough, g.mul(sm, 0.06))
    g.principled(tint, R, 0.0, None, **{'Transmission Weight': 1.0, 'IOR': 1.5})
    mat.use_raytrace_refraction = True
    mat.surface_render_method = 'DITHERED'
    mat.use_transparent_shadow = True
    mat.thickness_mode = 'SLAB'                              # a pane, not a ball of glass
    next(n for n in g.t.nodes if n.type == 'OUTPUT_MATERIAL').inputs['Thickness'].default_value = 0.004
    return mat
