"""eidoblend.sets.town.materials: the town's materials, by name. Blender:

    from eidoblend.sets.town.materials import M, clay
    M('plaster')       # -> the material 'town.plaster' (made once in a file; M('awn:3') -> 'town.awn_3')
    clay()             # one mid grey, no pattern: the form judged before the surface

Every surface is a CC0 photograph: each material takes PBR sets of the shared library (eidoverse/assets/cache/textures,
fetched by ID on first use through harness.assets.fetch_pbr; the sets, their real sizes and their measured means are
cc0_sets.json beside this file, measured by blender/tools/measure_cc0_sets.py). A few shared tiling sets at real scale,
read live in the shader and driven by masks from the geometry: no unique bakes for a town of instanced buildings.
- MAPPING: box projection in the OBJECT's own metres, at the set's measured tile size. Object space, not world space,
  so a town carried by an animated root keeps its textures on its walls. Each placed building shifts its projection by
  its own random number (forty copies of one mesh are forty different walls); heights are never shifted (what hangs
  under a slab stays under it).
- COLOUR: a set's colour map is divided by its own mean, so its grain, stains and hue shifts stay and its average
  becomes the building's own tint (sand, peach, bone, ochre; a grey render; a blue, pink or green house in twenty).
- LAYERS, in the order things happen: base -> broad variation -> what water did (runs from every ledge) -> splash at
  the foot -> grime in the inside corners -> what a strike did, when the town was built with damage (spalls to the
  block, pocks, soot over the openings that burned) -> dust on what faces up and drifted against what stands. Each
  cause has its mask from the geometry (eidoblend.sets.town.masks writes per-face data on every mesh: 'tl_edge' the
  water edge above a wall, 'tl_box' a flat face's extent, 'tl_corner' a wall face's inside corners, 'tl_soot' the
  opening below that burned, 'tl_lane' a road's lane frame), the object's 'tn_dust' (how near a strike it stands, 0
  in an intact town), its height and its normal.
- RELIEF: the set's displacement map through a bump node (box projection has no tangent frame for a normal map).
- THE ROADS' ENDS: every street is one quad of asphalt that stops where its track goes on; toward its end the road
  lies under the very track and plain it meets (track_surface and ground_plain, the same functions in the same object
  metres, so there is no seam), the cover breaking into lobes and wind streaks going in, the wheel paths driven clear
  first.
Albedos stay in the range of the real things: plaster at most about 0.5 (it prints near white under a desert sun);
dust is pale beside asphalt, never white.
The layout sets STRIKES and PAVED (module state) before it makes any material: one town per file.
"""
import json
import os

import bpy

from ...materials.layered import NT
from .signs import BOARDS

HERE = os.path.dirname(os.path.abspath(__file__))
REG = json.load(open(os.path.join(HERE, 'cc0_sets.json'), encoding='utf-8'))['sets']
MAPS = {'col': 'diff', 'rough': 'rough', 'disp': 'displacement', 'metal': 'metal'}     # the manifest's -> the library's
DUST = (0.37, 0.315, 0.23, 1.0)                                  # what lies on everything here
# what a strike lays on everything round it: plaster and concrete, ground fine; pale beside asphalt, not white
PALE = (0.40, 0.375, 0.335, 1.0)
SOOT = (0.016, 0.014, 0.012, 1.0)
STRIKES = []                                                     # (x, y, reach), town metres: the layout sets it (empty: intact)
# where the asphalt ends, town metres: the streets along x run to +-PAVED[0], those along y to +-PAVED[1], and each goes
# on as a track from there (the layout sets it from its extent; these are the numbers for extent (840, 300))
PAVED = [450.0, 160.0]
SAND_REACH = [34.0, 12.0]                                        # how far in from those ends the sand lies (the layout's)
SIGNS = []                                                     # the shop signs the layout was given (eidoblend.sets.town.signs)
# THE PLASTERS (linear albedo): sand, peach, bone and ochre, a grey render, and one house in twenty blue, pink or green
PLASTER = [(0.42, 0.33, 0.21), (0.46, 0.36, 0.23), (0.39, 0.30, 0.19), (0.47, 0.32, 0.23), (0.44, 0.33, 0.26), (0.50, 0.46, 0.37),
           (0.40, 0.28, 0.16), (0.43, 0.34, 0.22), (0.53, 0.49, 0.40), (0.44, 0.41, 0.35), (0.45, 0.31, 0.18), (0.49, 0.35, 0.26),
           (0.36, 0.30, 0.22), (0.41, 0.31, 0.21), (0.48, 0.44, 0.36), (0.37, 0.39, 0.39), (0.44, 0.35, 0.24), (0.46, 0.40, 0.31),
           (0.50, 0.37, 0.34), (0.38, 0.29, 0.18), (0.45, 0.37, 0.25), (0.43, 0.32, 0.19), (0.42, 0.36, 0.28), (0.47, 0.38, 0.24)]
CARS = [(0.60, 0.60, 0.58), (0.62, 0.62, 0.60), (0.58, 0.58, 0.56), (0.40, 0.40, 0.39), (0.45, 0.40, 0.30), (0.22, 0.05, 0.04), (0.05, 0.09, 0.18), (0.035, 0.035, 0.035),
        (0.50, 0.50, 0.47), (0.10, 0.16, 0.11), (0.55, 0.42, 0.10), (0.61, 0.61, 0.60)]
# the small things: (colour, roughness, metal, dust); each takes a photograph's grain where one fits (FAMILIES)
PLAIN = {
    'glass': ((0.012, 0.016, 0.02), 0.08, 0.0, 0.10), 'void': ((0.004, 0.004, 0.004), 1.0, 0.0, None), 'soot': ((0.012, 0.011, 0.010), 1.0, 0.0, None),
    'frame_alu': ((0.42, 0.42, 0.40), 0.45, 0.0, 0.15), 'frame_white': ((0.52, 0.51, 0.47), 0.5, 0.0, 0.15), 'frame_wood': ((0.16, 0.09, 0.05), 0.6, 0.0, 0.15),
    'door_green': ((0.07, 0.15, 0.11), 0.5, 0.0, 0.2), 'door_blue': ((0.08, 0.15, 0.24), 0.5, 0.0, 0.2), 'door_brown': ((0.14, 0.08, 0.05), 0.5, 0.0, 0.2),
    'door_grey': ((0.20, 0.21, 0.21), 0.5, 0.0, 0.2), 'door_rust': ((0.19, 0.09, 0.05), 0.75, 0.0, 0.2),
    'in_blue': ((0.30, 0.40, 0.43), 0.9, 0.0, 0.2), 'in_green': ((0.36, 0.44, 0.34), 0.9, 0.0, 0.2), 'in_white': ((0.56, 0.54, 0.48), 0.9, 0.0, 0.2),
    'in_pink': ((0.52, 0.38, 0.35), 0.9, 0.0, 0.2), 'in_cream': ((0.55, 0.48, 0.34), 0.9, 0.0, 0.2), 'ceiling': ((0.50, 0.49, 0.45), 0.9, 0.0, 0.0),
    'tank_white': ((0.60, 0.60, 0.56), 0.5, 0.0, 0.2), 'tank_black': ((0.025, 0.025, 0.028), 0.5, 0.0, 0.25), 'tank_blue': ((0.06, 0.16, 0.36), 0.5, 0.0, 0.2),
    'tank_red': ((0.30, 0.07, 0.04), 0.7, 0.0, 0.2), 'tank_cap': ((0.03, 0.03, 0.03), 0.6, 0.0, 0.1),
    'zinc': ((0.50, 0.52, 0.52), 0.42, 1.0, 0.2), 'zinc_old': ((0.36, 0.36, 0.34), 0.6, 0.6, 0.25), 'rust': ((0.17, 0.075, 0.035), 0.9, 0.0, 0.15),
    'steel_dark': ((0.05, 0.05, 0.05), 0.6, 0.6, 0.2), 'steel_paint': ((0.12, 0.13, 0.12), 0.55, 0.0, 0.2), 'rebar': ((0.10, 0.055, 0.035), 0.85, 0.0, 0.0),
    'cooler': ((0.56, 0.56, 0.52), 0.5, 0.0, 0.2), 'cooler_pad': ((0.20, 0.17, 0.11), 0.95, 0.0, 0.1), 'ac': ((0.58, 0.58, 0.54), 0.5, 0.0, 0.2),
    'ac_fan': ((0.03, 0.03, 0.03), 0.7, 0.0, 0.1), 'dish': ((0.55, 0.55, 0.52), 0.45, 0.0, 0.2), 'dish_dark': ((0.06, 0.06, 0.06), 0.5, 0.0, 0.25),
    'solar': ((0.015, 0.02, 0.05), 0.12, 0.0, 0.15), 'plastic_white': ((0.60, 0.60, 0.57), 0.45, 0.0, 0.15), 'plastic_blue': ((0.05, 0.14, 0.33), 0.45, 0.0, 0.15),
    'plastic_red': ((0.36, 0.04, 0.03), 0.45, 0.0, 0.15), 'mattress': ((0.42, 0.38, 0.33), 0.95, 0.0, 0.15), 'wood': ((0.20, 0.13, 0.07), 0.8, 0.0, 0.2),
    'wood_pale': ((0.36, 0.27, 0.16), 0.8, 0.0, 0.2), 'cardboard': ((0.33, 0.24, 0.13), 0.9, 0.0, 0.1),
    'tyre': ((0.018, 0.018, 0.018), 0.85, 0.0, 0.2), 'hub': ((0.30, 0.30, 0.30), 0.45, 0.8, 0.2), 'bumper': ((0.03, 0.03, 0.03), 0.6, 0.0, 0.2),
    'lamp_red': ((0.30, 0.02, 0.015), 0.3, 0.0, 0.1), 'lamp_clear': ((0.55, 0.55, 0.50), 0.2, 0.0, 0.1), 'car_glass': ((0.035, 0.04, 0.045), 0.1, 0.0, None),
    'car_in': ((0.03, 0.03, 0.03), 0.9, 0.0, None), 'car_burnt': ((0.035, 0.026, 0.02), 0.95, 0.0, 0.25), 'car_bed': ((0.10, 0.10, 0.10), 0.6, 0.3, 0.3),
    'frond': ((0.085, 0.14, 0.05), 0.55, 0.0, 0.0), 'frond_old': ((0.16, 0.17, 0.07), 0.6, 0.0, 0.0), 'frond_dead': ((0.26, 0.19, 0.10), 0.9, 0.0, 0.0),
    'dates': ((0.42, 0.24, 0.05), 0.6, 0.0, 0.0), 'leaf': ((0.07, 0.12, 0.045), 0.6, 0.0, 0.0), 'leaf_dry': ((0.14, 0.15, 0.07), 0.7, 0.0, 0.0),
    'wire': ((0.012, 0.012, 0.012), 0.8, 0.0, None), 'insulator': ((0.30, 0.20, 0.15), 0.3, 0.0, 0.0), 'lamp_head': ((0.42, 0.42, 0.40), 0.4, 0.5, 0.2),
    'cloth0': ((0.66, 0.66, 0.62), 0.95, 0.0, 0.0), 'cloth1': ((0.45, 0.06, 0.05), 0.95, 0.0, 0.0), 'cloth2': ((0.07, 0.17, 0.42), 0.95, 0.0, 0.0),
    'cloth3': ((0.62, 0.48, 0.10), 0.95, 0.0, 0.0), 'cloth4': ((0.10, 0.32, 0.17), 0.95, 0.0, 0.0), 'cloth5': ((0.03, 0.03, 0.035), 0.95, 0.0, 0.0),
    'cloth6': ((0.52, 0.22, 0.36), 0.95, 0.0, 0.0), 'cloth7': ((0.20, 0.42, 0.50), 0.95, 0.0, 0.0), 'cloth8': ((0.50, 0.24, 0.07), 0.95, 0.0, 0.0),
    'tarp_blue': ((0.05, 0.16, 0.40), 0.6, 0.0, 0.3), 'tarp_sand': ((0.42, 0.33, 0.18), 0.9, 0.0, 0.3), 'tarp_green': ((0.10, 0.20, 0.12), 0.8, 0.0, 0.3),
    'tarp_white': ((0.58, 0.57, 0.52), 0.8, 0.0, 0.3), 'tarp_red': ((0.42, 0.07, 0.05), 0.8, 0.0, 0.3),
    'fruit_orange': ((0.60, 0.25, 0.03), 0.6, 0.0, 0.0), 'fruit_red': ((0.45, 0.04, 0.03), 0.6, 0.0, 0.0), 'fruit_green': ((0.16, 0.34, 0.06), 0.6, 0.0, 0.0),
    'fruit_yellow': ((0.62, 0.50, 0.08), 0.6, 0.0, 0.0), 'crate': ((0.05, 0.12, 0.30), 0.6, 0.0, 0.1), 'sack': ((0.50, 0.46, 0.38), 0.95, 0.0, 0.1),
    'bike_red': ((0.40, 0.03, 0.03), 0.4, 0.0, 0.05), 'bike_blue': ((0.04, 0.14, 0.40), 0.4, 0.0, 0.05), 'chrome': ((0.6, 0.6, 0.6), 0.25, 1.0, 0.1),
    'dome': ((0.07, 0.30, 0.27), 0.35, 0.0, 0.12), 'dome_blue': ((0.05, 0.15, 0.36), 0.35, 0.0, 0.12), 'gold': ((0.60, 0.42, 0.12), 0.35, 1.0, 0.05),
    'tile_band': ((0.06, 0.20, 0.30), 0.3, 0.0, 0.1), 'speaker': ((0.40, 0.41, 0.40), 0.5, 0.0, 0.2),
    'barrel_blue': ((0.04, 0.12, 0.28), 0.55, 0.0, 0.2), 'barrel_rust': ((0.20, 0.09, 0.04), 0.85, 0.0, 0.2),
}
# the plants (palms, the built yard trees) take plain colours with a little noise, no photograph (_plant)
PLANTS = ('frond', 'frond_old', 'frond_dead', 'dates', 'leaf', 'leaf_dry', 'trunk', 'palm_trunk')


# ==================================================================================================== the node vocabulary
class T(NT):
    """materials.layered's node helpers, and what a photographic, layered town needs besides"""

    def __init__(self, tree_):
        super().__init__(tree_)
        self._c = {}

    def once(self, key, make):
        if key not in self._c:
            self._c[key] = make()
        return self._c[key]

    def vm(self, op, a, b=None, c=None):
        n = self.N.new('ShaderNodeVectorMath')
        n.operation = op
        self.put(n.inputs[0], a)
        if b is not None:
            self.put(n.inputs[1], b)
        if c is not None:
            self.put(n.inputs[2], c)
        return n.outputs['Value'] if op in ('DOT_PRODUCT', 'LENGTH', 'DISTANCE') else n.outputs['Vector']

    def P0(self):
        """the point in the object's own metres"""
        return self.once('P0', lambda: self.N.new('ShaderNodeTexCoord').outputs['Object'])

    def xyz0(self):
        def mk():
            s = self.N.new('ShaderNodeSeparateXYZ')
            self.L.new(self.P0(), s.inputs[0])
            return s.outputs[0], s.outputs[1], s.outputs[2]
        return self.once('xyz0', mk)

    def rnd(self):
        return self.once('rnd', lambda: self.N.new('ShaderNodeObjectInfo').outputs['Random'])

    def rnd2(self, k):
        """a second, third ... number of the placing's own, unrelated to the first"""
        return self.m('FRACT', self.mul(self.add(self.rnd(), 0.137 * k), 7.919 + 3.1 * k))

    def Ps(self):
        """the point slid sideways by the placing's random number; heights left alone"""
        return self.once('Ps', lambda: self.vm('ADD', self.P0(), self.comb(self.mul(self.rnd(), 613.0), self.mul(self.rnd(), 377.0), 0.0)))

    def oattr(self, name):
        def mk():
            a = self.N.new('ShaderNodeAttribute')
            a.attribute_type, a.attribute_name = 'OBJECT', name
            return a.outputs['Fac']
        return self.once('o:' + name, mk)

    def gattr(self, name):
        def mk():
            a = self.N.new('ShaderNodeAttribute')
            a.attribute_type, a.attribute_name = 'GEOMETRY', name
            return a
        return self.once('g:' + name, mk)

    def nz(self):
        return self.nrm()[2]

    def wall(self):
        """1 on what stands upright"""
        return self.once('wall', lambda: self.inv(self.sm(self.m('ABSOLUTE', self.nz()), 0.3, 0.55)))

    def up(self, lo=0.55, hi=0.92):
        return self.sm(self.nz(), lo, hi)

    def along(self):
        """the coordinate along an upright face (x on a face that looks along y, y on one that looks along x), unshifted"""
        def mk():
            X, Y, Z = self.xyz0()
            side = self.sm(self.m('ABSOLUTE', self.nrm()[0]), 0.5, 0.6)
            return self.mixf(side, X, Y)
        return self.once('along', mk)

    def near(self):
        """how near a strike, 0..1: the placing's own number; or, on the town's ground and streets (one object each, in the
        town's own metres), the strike field where the point is"""
        def mk():
            sf = strike_field(self)
            return self.mx(self.oattr('tn_dust'), self.mul(self.oattr('tn_space'), sf))
        return self.once('near', mk)

    # ------------------------------------------------------------------------------------------------ the photographs
    def tex(self, key, kind, vec, proj='BOX', blend=0.22, color=False, scale=1.0):
        """one map of a set ('col', 'rough', 'disp', 'metal'), projected at the set's real size. proj 'FLAT': on x, y
        (the ground, in plan). None when the set has no such map"""
        s = REG[key]
        f = set_files(key).get(MAPS[kind])
        if not f or not os.path.isfile(f):
            return None
        w, h = s['tile'][0] * scale, s['tile'][1] * scale
        mp = self.N.new('ShaderNodeMapping')
        mp.inputs['Scale'].default_value = (1.0 / w, 1.0 / w, 1.0 / h) if proj == 'BOX' else (1.0 / w, 1.0 / h, 1.0)
        self.L.new(vec, mp.inputs['Vector'])
        n = self.N.new('ShaderNodeTexImage')
        n.image = image(f, color)
        n.projection = proj
        if proj == 'BOX':
            n.projection_blend = blend
        n.interpolation, n.extension = 'Linear', 'REPEAT'
        self.L.new(mp.outputs[0], n.inputs['Vector'])
        return n.outputs['Color']

    def ncol(self, key, vec, proj='BOX', k=1.0, scale=1.0):
        """a set's colour divided by its own mean: the photograph's grain about 1; k: how much of its contrast"""
        c = self.tex(key, 'col', vec, proj, color=True, scale=scale)
        n = self.vm('DIVIDE', c, tuple(max(1e-3, v) for v in REG[key]['mean']))
        if k != 1.0:
            n = self.vm('MULTIPLY_ADD', n, (k, k, k), (1.0 - k, 1.0 - k, 1.0 - k))
        return n

    def lum(self, v):
        return self.vm('DOT_PRODUCT', v, (0.2126, 0.7152, 0.0722))

    def tint(self, n, rgb):
        """grain n (about 1) times a tint (a tuple or a colour socket), kept under a real surface's top albedo"""
        return self.vm('MINIMUM', self.vm('MULTIPLY', n, rgb if not isinstance(rgb, tuple) else tuple(rgb[:3])), (0.82, 0.82, 0.82))

    def rough(self, key, vec, proj='BOX', lo=0.55, hi=1.0, scale=1.0):
        r = self.tex(key, 'rough', vec, proj, scale=scale)
        return self.lin(r, 0.0, 1.0, lo, hi) if r is not None else (lo + hi) / 2.0

    def height(self, key, vec, proj='BOX', scale=1.0, k=1.0):
        d = self.tex(key, 'disp', vec, proj, scale=scale)
        return self.mul(self.sub(d, 0.5), REG[key]['relief'] * k * scale) if d is not None else 0.0

    def palette(self, fac, colors):
        r = self.N.new('ShaderNodeValToRGB')
        r.color_ramp.interpolation = 'CONSTANT'
        el = r.color_ramp.elements
        el[0].position, el[0].color = 0.0, (*colors[0], 1.0)
        el[1].position, el[1].color = 1.0 / len(colors), (*colors[1], 1.0)
        for k in range(2, len(colors)):
            el.new(k / len(colors)).color = (*colors[k], 1.0)
        self.put(r.inputs[0], fac)
        return r.outputs[0]

    def wnoise(self, vec, dims='3D'):
        wn = self.N.new('ShaderNodeTexWhiteNoise')
        wn.noise_dimensions = dims
        self.L.new(vec, wn.inputs['Vector'])
        return wn.outputs['Value']

    def vor(self, vec, scale, feature='F1', dims='2D', rand=1.0):
        n = self.N.new('ShaderNodeTexVoronoi')
        n.voronoi_dimensions, n.feature = dims, feature
        n.inputs['Scale'].default_value = scale
        n.inputs['Randomness'].default_value = rand
        self.L.new(vec, n.inputs['Vector'])
        return n


_IMG = {}
_FILES = {}


def set_files(key, manifest=None):
    """{library map name: path} of a manifest set (cc0_sets.json: its 'id' and 'res'), fetched into the shared library on
    first use (harness.assets.fetch_pbr; EIDO_NO_FETCH=1 forbids the download and names the fetch command)"""
    s = (manifest or REG)[key]
    k = (s['id'], s['res'])
    if k not in _FILES:
        from ...harness import assets
        _FILES[k] = assets.fetch_pbr(s['id'], s['res'])['files']
    return _FILES[k]


def image(path, color):
    key = (path, color)
    if key not in _IMG:
        img = bpy.data.images.load(path, check_existing=True)
        img.colorspace_settings.name = 'sRGB' if color else 'Non-Color'
        _IMG[key] = img
    return _IMG[key]


# ==================================================================================================== masks by cause
def strike_field(t):
    """on the town's own ground: 0..1, how thick a strike's fall lies here (thickest where it fell, nothing at about one
    and a half times its ruin's reach, its edge broken by its own noise); 0 in an intact town"""
    X, Y, Z = t.xyz0()
    best = None
    for sx, sy, sr in STRIKES:
        d = t.m('SQRT', t.add(t.m('POWER', t.sub(X, sx), 2.0), t.m('POWER', t.sub(Y, sy), 2.0)))
        k = t.inv(t.sm(d, sr * 0.25, sr * 1.35))
        best = k if best is None else t.mx(best, k)
    if best is None:
        return 0.0
    n = t.noise(t.P0(), 0.11, 3.0, off=(13.0, 5.0, 0.0))
    return t.sm(t.add(best, t.mul(t.sub(n, 0.5), 0.5)), 0.15, 0.9)


def drips(t, strength=1.0):
    """what rain carried over every ledge and down the wall under it: runs that start at the ledge's edge and fade
    within a metre or two, each its own length, in gravity's direction (never along a face's UVs); and right under the
    ledge the band the rain never washed. The ledge is the geometry's: 'tl_edge', the height of the nearest edge over
    this face (a sill, a slab's band, a balcony, a coping; eidoblend.sets.town.masks)."""
    X, Y, Z = t.xyz0()
    d = t.sub(t.gattr('tl_edge').outputs['Fac'], Z)
    u = t.along()
    streak = t.sm(t.noise(t.comb(u, t.mul(Z, 0.11), t.mul(t.rnd(), 31.0)), 4.2, 3.0), 0.42, 0.64)
    reach = t.add(0.45, t.mul(t.noise(t.comb(t.mul(u, 0.45), t.mul(t.rnd(), 7.0), 0.0), 1.3, 2.0), 2.2))
    fall = t.inv(t.sm(d, 0.0, reach))
    under = t.inv(t.sm(d, 0.0, t.add(0.06, t.mul(t.noise(t.comb(t.mul(u, 2.0), 0.0, 0.0), 1.0, 2.0), 0.16))))
    gate = t.sm(d, -0.04, 0.0)
    k = t.mul(t.add(0.45, t.mul(t.rnd2(3), 0.55)), strength)
    return t.mul(t.mul(t.mul(t.mx(t.mul(streak, fall), t.mul(under, 0.55)), gate), t.wall()), k, clamp=True)


def splash(t, height=1.0):
    """the street's dirt thrown up a wall's foot, ragged at its top"""
    X, Y, Z = t.xyz0()
    top = t.add(height * 0.5, t.mul(t.noise(t.comb(t.mul(t.along(), 1.3), Z, 0.0), 1.0, 2.0), height * 0.9))
    return t.mul(t.inv(t.sm(Z, 0.03, top)), t.wall())


def corner_grime(t):
    """grime against an inside corner (a wall meeting a column, a stair head, a neighbour's wall), ramped over a few
    tens of centimetres, ragged; the face's own extent and which of its ends is a corner are the geometry's
    ('tl_corner', eidoblend.sets.town.masks); an opening's edge is an arris and stays clean"""
    a = t.gattr('tl_corner')
    sc = t.N.new('ShaderNodeSeparateColor')
    t.L.new(a.outputs['Color'], sc.inputs[0])
    u0, u1, c0 = sc.outputs[0], sc.outputs[1], sc.outputs[2]
    c1 = a.outputs['Alpha']
    u = t.along()
    d0 = t.add(t.mul(t.sub(u, u0), c0), t.mul(t.inv(c0), 100.0))
    d1 = t.add(t.mul(t.sub(u1, u), c1), t.mul(t.inv(c1), 100.0))
    X, Y, Z = t.xyz0()
    w = t.add(0.12, t.mul(t.noise(t.comb(u, t.mul(Z, 0.5), 0.0), 2.0, 3.0), 0.42))
    return t.mul(t.inv(t.sm(t.mn(d0, d1), 0.0, w)), t.wall())


def edge_drift(t):
    """dust and grit blown against whatever stands at a flat face's edges (a parapet, a wall, a kerb): the face's own
    extent, 'tl_box', against the point -> 0..1 within half a metre or so of an edge"""
    X, Y, Z = t.xyz0()
    a = t.gattr('tl_box')
    sc = t.N.new('ShaderNodeSeparateColor')
    t.L.new(a.outputs['Color'], sc.inputs[0])
    x0, y0, x1 = sc.outputs[0], sc.outputs[1], sc.outputs[2]
    y1 = a.outputs['Alpha']
    e = t.mn(t.mn(t.sub(X, x0), t.sub(x1, X)), t.mn(t.sub(Y, y0), t.sub(y1, Y)))
    w = t.add(0.12, t.mul(t.noise(t.P0(), 0.9, 3.0, off=(4.0, 1.0, 0.0)), 0.75))
    return t.mul(t.inv(t.sm(e, 0.02, w)), t.sm(t.sub(x1, x0), 0.5, 0.8))


def soot_plume(t):
    """soot over an opening whose room burned: it leaves the opening's head and climbs, widening, fading in two or
    three metres; 'tl_soot' (the opening's middle along the wall, its head's height, its half width, how hard it
    burned) is the geometry's: eidoblend.sets.town.masks"""
    X, Y, Z = t.xyz0()
    a = t.gattr('tl_soot')
    sc = t.N.new('ShaderNodeSeparateColor')
    t.L.new(a.outputs['Color'], sc.inputs[0])
    su, sz, sw = sc.outputs[0], sc.outputs[1], sc.outputs[2]
    sk = a.outputs['Alpha']
    du = t.m('ABSOLUTE', t.sub(t.along(), su))
    dz = t.sub(Z, sz)
    wid = t.add(t.add(sw, 0.15), t.mul(t.mx(dz, 0.0), 0.5))
    n = t.noise(t.comb(t.mul(t.along(), 1.6), t.mul(Z, 0.35), 3.0), 2.5, 3.0)
    f = t.mul(t.mul(t.inv(t.sm(t.m('DIVIDE', du, wid), 0.5, 1.1)), t.sm(dz, -0.35, 0.1)), t.inv(t.sm(dz, 0.8, t.add(2.8, t.mul(n, 1.6)))))
    return t.mul(t.mul(t.mul(f, sk), t.add(0.7, t.mul(n, 0.7))), t.wall(), clamp=True)


def pocks(t, density, vec2, cell=0.16):
    """what fragments and rounds leave in plaster or concrete: a dark hole and a paler ring where the coat flaked
    round it, in clusters, at centimetre scale -> (hole 0..1, halo 0..1, a relief)"""
    v = t.vor(vec2, 1.0 / cell, 'F1', '2D')
    d = v.outputs['Distance']
    cr = t.N.new('ShaderNodeSeparateColor')
    t.L.new(v.outputs['Color'], cr.inputs[0])
    keep = t.sm(cr.outputs[0], t.inv(density), t.add(t.inv(density), 0.02))
    r = t.add(0.10, t.mul(cr.outputs[1], 0.16))
    hole = t.mul(t.inv(t.sm(d, t.mul(r, 0.55), r)), keep)
    halo = t.mx(t.sub(t.mul(t.inv(t.sm(d, r, t.mul(r, 2.3))), keep), hole), 0.0)
    return hole, halo, t.add(t.mul(hole, -0.03), t.mul(halo, -0.004))


def litter(t, vec2, density, col):
    """what a street collects: scraps of paper, bags, cardboard, a bottle: each a cell of its own colour, a hand
    across, thickest where the wind and the brooms leave it (the gutters). A scrap is flat, torn, crumpled, mostly pale
    or dark, and its cell is warped by noise so none is round"""
    nz = t.N.new('ShaderNodeTexNoise')
    nz.inputs['Scale'].default_value, nz.inputs['Detail'].default_value = 9.0, 2.0
    t.L.new(vec2, nz.inputs['Vector'])
    wv = t.vm('ADD', vec2, t.vm('MULTIPLY', t.vm('SUBTRACT', nz.outputs['Color'], (0.5, 0.5, 0.5)), (0.5, 0.5, 0.0)))
    v = t.vor(t.vm('MULTIPLY', wv, (1.0, 1.7, 1.0)), 1.0 / 0.42, 'F1', '2D')
    cr = t.N.new('ShaderNodeSeparateColor')
    t.L.new(v.outputs['Color'], cr.inputs[0])
    keep = t.sm(cr.outputs[0], t.inv(density), t.add(t.inv(density), 0.01))
    blob = t.mul(t.inv(t.sm(v.outputs['Distance'], t.add(0.05, t.mul(cr.outputs[2], 0.08)), t.add(0.08, t.mul(cr.outputs[2], 0.1)))), keep)
    c = t.palette(cr.outputs[1], [(0.52, 0.50, 0.45), (0.46, 0.44, 0.40), (0.06, 0.06, 0.07), (0.03, 0.03, 0.03), (0.36, 0.27, 0.16),
                                  (0.30, 0.10, 0.07), (0.50, 0.49, 0.46), (0.12, 0.16, 0.20)])
    return t.mixc(t.mul(blob, 0.85), col, c)


def dusted(t, col, rough, base=0.06, up_k=0.35, near=None, color=None, P=None):
    """dust on what faces up and a thin film on everything, broken at its edge by noise; near a strike, the paler fall
    of what was brought down, on everything -> (colour, roughness, how much dust)"""
    P = P if P is not None else t.Ps()
    near = near if near is not None else t.near()
    n1, n2 = t.noise(P, 0.6, 3.0, off=(2.0, 3.0, 1.0)), t.noise(P, 5.0, 2.0, off=(7.0, 1.0, 4.0))
    lay = t.add(t.add(t.add(base, t.mul(near, 0.08)), t.mul(t.up(), t.add(up_k, t.mul(near, 0.18)))), t.add(t.mul(t.sub(n1, 0.5), 0.36), t.mul(t.sub(n2, 0.5), 0.14)))
    d = t.mul(t.sm(lay, 0.22, 0.86), 0.88, clamp=True)
    dc = color if color is not None else t.mixc(t.mul(near, 0.6), DUST, PALE)
    dc = t.value(dc, t.add(0.92, t.mul(n2, 0.16)))
    return t.mixc(d, col, dc), t.mixf(d, rough, 0.95), d


# ==================================================================================================== the families
def fam_plaster(t, base, arg):
    """a building's render: its tint, the photograph's grain, a weathered coat in patches, runs from every ledge, the
    street's splash, and where it was hit, the strike's whole story"""
    hit = base == 'plaster_dmg'
    Ps, near = t.Ps(), t.near()
    if base == 'plaster_w':                                          # (the yard walls are one object: each stretch takes its own number)
        X, Y, Z = t.xyz0()
        rnd = t.wnoise(t.comb(t.m('FLOOR', t.m('DIVIDE', X, 13.0)), t.m('FLOOR', t.m('DIVIDE', Y, 9.0)), 0.0))
    else:
        rnd = t.rnd()
    tint = t.palette(t.m('FRACT', t.add(rnd, 0.37 if base == 'plaster_b' else 0.0)), PLASTER)
    g_a = t.ncol('render_sand', Ps, k=1.6)                           # cement render, brushed (its contrast is low: 0.08)
    g_c = t.ncol('stucco', Ps, k=1.2)
    which = t.sm(t.m('FRACT', t.mul(rnd, 5.31)), 0.62, 0.64)         # a third of the houses are stuccoed
    g = mixv(t, which, g_a, g_c)
    # the coat weathered in patches: the old paint gone in flakes (its own photograph), more on the struck and the old;
    # at most 0.7 of a patch, so the flakes stay a texture on a light wall and never print as spots
    g_w = t.ncol('plaster_worn', Ps, k=0.6)
    patch = t.sm(t.add(t.noise(Ps, 0.35, 3.0, off=(3.0, 9.0, 1.0)), t.mul(t.rnd2(5), 0.16 if not hit else 0.34)), 0.64, 0.72)
    g = mixv(t, t.mul(patch, 0.7), g, g_w)
    col = t.tint(g, tint)
    # broad variation: a few per cent over metres, and the building's own
    mac = t.add(t.add(1.0, t.mul(t.sub(t.noise(Ps, 0.12, 3.0), 0.5), 0.16)), t.mul(t.sub(t.rnd2(7), 0.5), 0.10))
    col = t.value(col, mac)
    rough = t.rough('render_sand', Ps, lo=0.78, hi=0.98)
    h = t.add(t.height('render_sand', Ps), t.mul(t.height('plaster_worn', Ps), patch))
    # what water did: strong enough to show from 70 m, under the 0.85 at which a pale block reads as a barcode
    dr = drips(t, 1.0 if not hit else 0.8)
    col = t.mixc(t.mul(dr, 0.72), col, t.value(col, 0.5))
    col = t.mixc(t.mul(dr, 0.35), col, (0.20, 0.17, 0.13, 1.0))
    sp = splash(t, 1.1)
    col = t.mixc(t.mul(sp, 0.55), col, t.value(t.mixc(0.5, DUST, col), 0.85))
    col = t.mixc(t.mul(corner_grime(t), 0.55), col, t.value(t.mixc(0.3, (0.20, 0.17, 0.13, 1.0), col), 0.7))
    X, Y, Z = t.xyz0()
    hole = halo = None
    if STRIKES:
        # every house near a strike took fragments: pocks in clusters, by how near it stood
        dens = t.mul(t.mul(near, 0.30 if hit else 0.16), t.sm(t.noise(Ps, 0.25, 2.0, off=(5.0, 5.0, 5.0)), 0.35, 0.65))
        hole, halo, ph = pocks(t, dens, t.comb(t.along(), Z, t.mul(rnd, 50.0)))
        h = t.add(h, ph)
    if hit:
        # spalls: the render gone in patches to the block under it, a paler rim of fresh-broken coat round each; most
        # round the openings that were blown (where the plume is), few on the open wall: a struck wall stands mostly
        # in its render, pocked
        sp_ = soot_plume(t)
        ns = t.add(t.noise(Ps, 1.5, 4.0, off=(1.0, 2.0, 3.0), rough=0.62), t.mul(t.sub(t.noise(Ps, 6.0, 2.0), 0.5), 0.16))
        th = t.sub(t.sub(0.71, t.mul(near, 0.06)), t.mul(t.sm(sp_, 0.05, 0.45), 0.10))
        spall = t.sm(ns, th, t.add(th, 0.012))
        rim = t.mx(t.sub(t.sm(ns, t.sub(th, 0.03), th), spall), 0.0)
        blk = t.tint(t.ncol('block', Ps, k=0.6), (0.34, 0.32, 0.29))
        col = t.mixc(spall, col, t.value(blk, 0.92))
        col = t.mixc(t.mul(rim, 0.7), col, t.value(t.mixc(0.5, col, (0.55, 0.53, 0.48, 1.0)), 1.1))
        h = t.add(h, t.add(t.mul(spall, -0.014), t.mul(t.height('block', Ps), spall)))
        rough = t.mixf(spall, rough, 0.92)
        # smoke: blotches where it burned, and the plumes over the openings
        sm_ = t.mul(t.sm(t.noise(Ps, 0.16, 3.0, off=(7.0, 2.0, 4.0)), 0.55, 0.78), 0.45)
        col = t.mixc(sm_, col, t.value(col, 0.45))
        col = t.mixc(sp_, col, SOOT)
        rough = t.mixf(sp_, rough, 0.97)
    if hole is not None:
        col = t.mixc(t.mul(hole, 0.9), col, (0.035, 0.032, 0.028, 1.0))
        col = t.mixc(t.mul(halo, 0.75), col, t.value(t.mixc(0.45, col, (0.56, 0.53, 0.47, 1.0)), 1.08))
    col, rough, _ = dusted(t, col, rough, 0.05 if not hit else 0.16, 0.42)
    return col, rough, 0.0, h


def mixv(t, f, a, b):
    """a mix of two vectors (photographs' grains) by f"""
    n = t.N.new('ShaderNodeMix')
    n.data_type = 'VECTOR'
    t.put(n.inputs[0], f)
    t.put(n.inputs[4], a)
    t.put(n.inputs[5], b)
    return n.outputs[1]


def fam_masonry(t, base, arg):
    """a wall never plastered: the grey hollow block, or the buff brick, in its courses"""
    Ps, near = t.Ps(), t.near()
    key = 'block' if base in ('block', 'claustra') else 'brick'
    # block weathered in a dry country is a warm grey with its joints a little darker, no more: the set's own contrast
    # (near-black joints) would draw every bare wall as a blue-grey grid from 100 m
    g = t.ncol(key, Ps, k=0.55 if key == 'block' else 0.8)
    tint = (0.335, 0.315, 0.285) if key == 'block' else (0.43, 0.30, 0.17)
    col = t.tint(g, tint)
    col = t.value(col, t.add(t.add(1.0, t.mul(t.sub(t.noise(Ps, 0.15, 3.0), 0.5), 0.18)), t.mul(t.sub(t.rnd2(2), 0.5), 0.12)))
    rough = t.rough(key, Ps, lo=0.8, hi=0.98)
    h = t.height(key, Ps)
    if base == 'claustra':
        # pierced block: each unit a dark opening in a pale frame (drawn, not built: from 70 m a 12 cm hole is two pixels)
        X, Y, Z = t.xyz0()
        U = t.along()
        fu, fz = t.m('FRACT', t.m('DIVIDE', U, 0.2)), t.m('FRACT', t.m('DIVIDE', Z, 0.2))
        d = t.mn(t.mn(fu, t.inv(fu)), t.mn(fz, t.inv(fz)))
        hole = t.mul(t.sm(d, 0.26, 0.30), t.inv(t.sm(t.nz(), 0.5, 0.7)))
        col = t.mixc(hole, t.value(col, 1.25), (0.045, 0.04, 0.035, 1.0))
    dr = drips(t, 0.8)
    col = t.mixc(t.mul(dr, 0.7), col, t.value(col, 0.55))
    col = t.mixc(t.mul(splash(t, 0.9), 0.5), col, t.value(t.mixc(0.5, DUST, col), 0.85))
    col = t.mixc(t.mul(corner_grime(t), 0.5), col, t.value(col, 0.68))
    X, Y, Z = t.xyz0()
    if STRIKES:
        hole, halo, ph = pocks(t, t.mul(near, 0.2), t.comb(t.along(), Z, t.mul(t.rnd(), 50.0)), 0.14)
        col = t.mixc(t.mul(hole, 0.9), col, (0.03, 0.028, 0.025, 1.0))
        col = t.mixc(t.mul(halo, 0.6), col, t.value(col, 1.2))
        h = t.add(h, ph)
    col, rough, _ = dusted(t, col, rough, 0.08, 0.45)
    return col, rough, 0.0, h


def fam_concrete(t, base, arg):
    """cast concrete (the frame, slab edges, sills, copings, canopies, steps) with its blowholes; broken concrete,
    paler where it is fresh"""
    Ps, near = t.Ps(), t.near()
    broken = base == 'concrete_broken'
    g = t.ncol('concrete', Ps, k=0.85, scale=0.6 if broken else 1.0)
    tint = (0.34, 0.33, 0.30) if broken else (0.30, 0.285, 0.26)
    col = t.tint(g, tint)
    col = t.value(col, t.add(t.add(1.0, t.mul(t.sub(t.noise(Ps, 0.2, 3.0), 0.5), 0.16)), t.mul(t.sub(t.rnd2(4), 0.5), 0.1)))
    rough = t.rough('concrete', Ps, lo=0.72, hi=0.97)
    h = t.height('concrete', Ps, scale=0.6 if broken else 1.0, k=4.0 if broken else 1.0)
    if broken:
        gr = t.ncol('gravel', Ps, k=0.8, scale=0.5)
        col = t.mixc(t.mul(t.sm(t.noise(Ps, 3.0, 2.0), 0.4, 0.7), 0.5), col, t.tint(gr, (0.36, 0.34, 0.30)))
        h = t.add(h, t.height('gravel', Ps, scale=0.5, k=0.6))
    else:
        dr = drips(t, 0.8)
        col = t.mixc(t.mul(dr, 0.75), col, t.value(col, 0.5))
        col = t.mixc(t.mul(splash(t, 0.8), 0.45), col, t.value(t.mixc(0.5, DUST, col), 0.85))
        col = t.mixc(t.mul(corner_grime(t), 0.5), col, t.value(col, 0.68))
    # (the up-facing dust kept at 0.3 and the strike's pale at 0.3 of it: more, and a broken piece lying in a struck
    #  street prints as a white box)
    col, rough, _ = dusted(t, col, rough, 0.08 if not broken else 0.14, 0.3, color=t.mixc(t.mul(near, 0.3), DUST, PALE))
    return col, rough, 0.0, h


def fam_roof(t, base, arg):
    """a roof's screed: trowelled concrete in its strips, darker where water stood and dried, black where a leak was
    tarred over, dust over all of it and drifted against the parapets"""
    Ps, near = t.Ps(), t.near()
    dmg = base == 'roof_dmg'
    g = t.ncol('concrete_smooth', Ps, k=1.6)
    tint = t.palette(t.m('FRACT', t.mul(t.rnd(), 3.7)), [(0.33, 0.29, 0.22), (0.36, 0.32, 0.25), (0.30, 0.28, 0.24), (0.38, 0.33, 0.24), (0.34, 0.31, 0.27)])
    col = t.tint(g, tint)
    col = t.value(col, t.add(1.0, t.mul(t.sub(t.noise(Ps, 0.25, 3.0), 0.5), 0.2)))
    # where water stood and dried: small, ragged, faint, a darker tide line at each edge (large dark ponds with the
    # dust's blots would print every roof as camouflage)
    pn = t.noise(Ps, 1.1, 3.0, off=(2.0, 9.0, 0.0), rough=0.6)
    pond = t.mul(t.sm(pn, 0.63, 0.70), t.sm(t.noise(Ps, 0.2, 2.0, off=(4.0, 4.0, 0.0)), 0.45, 0.6))
    ring = t.mul(t.mx(t.sub(t.sm(pn, 0.61, 0.63), t.sm(pn, 0.63, 0.65)), 0.0), t.sm(t.noise(Ps, 0.2, 2.0, off=(4.0, 4.0, 0.0)), 0.45, 0.6))
    col = t.value(col, t.sub(1.0, t.add(t.mul(pond, 0.10), t.mul(ring, 0.14))))
    tar = t.mul(t.sm(t.noise(Ps, 0.17, 1.0, off=(5.0, 1.0, 0.0)), 0.70, 0.705), t.sm(t.noise(Ps, 0.7, 3.0), 0.35, 0.5))
    col = t.mixc(t.mul(tar, 0.85), col, (0.03, 0.028, 0.026, 1.0))
    X, Y, Z = t.xyz0()
    fx = t.m('FRACT', t.m('DIVIDE', X, 3.0))                         # the screed laid in strips 3 m wide, a joint between
    jn = t.inv(t.sm(t.mn(fx, t.inv(fx)), 0.0, 0.006))
    col = t.value(col, t.sub(1.0, t.mul(jn, 0.2)))
    rough = t.mixf(tar, t.rough('concrete_smooth', Ps, lo=0.8, hi=0.97), 0.45)
    h = t.add(t.height('concrete_smooth', Ps, k=2.0), t.mul(jn, -0.003))
    dr = edge_drift(t)
    col, rough, d = dusted(t, col, rough, 0.06 if not dmg else 0.18, 0.12, P=t.vm('MULTIPLY', Ps, (3.2, 3.2, 3.2)))
    col = t.mixc(t.mul(dr, 0.7), col, t.value(t.mixc(t.mul(near, 0.6), DUST, PALE), 1.0))
    if dmg:
        rb = t.tint(t.ncol('gravel_ground', Ps, k=0.9), (0.38, 0.36, 0.32))
        col = t.mixc(t.mul(t.sm(t.noise(Ps, 0.8, 3.0), 0.45, 0.6), 0.8), col, rb)
        h = t.add(h, t.height('gravel_ground', Ps, k=0.5))
    return col, rough, 0.0, h


def ground_plain(t, P):
    """the plain's grounds as fam_ground's 'ground' draws them -> (colour, height): one function, so a road's sanded
    end (fam_road) goes over into exactly the ground beside it"""
    # each ground sampled at two unrelated sizes and blended by a slow field, so a 2.5 m tile never repeats as a fine
    # checker over the plain in a long lens
    two = t.sm(t.noise(P, 1.0 / 30.0, 2.0, off=(7.0, 2.0, 0.0)), 0.3, 0.7)
    c_s = mixv(t, two, t.ncol('sand', P, 'FLAT', k=0.65), t.ncol('sand', P, 'FLAT', k=0.65, scale=3.9))
    c_d = mixv(t, two, t.ncol('dry_ground', P, 'FLAT', k=0.75, scale=2.7), t.ncol('dry_ground', P, 'FLAT', k=0.75))
    c_g = t.ncol('gravel_ground', P, 'FLAT', k=0.75)
    c_w = t.ncol('dry_grass', P, 'FLAT', k=0.9)
    s1 = t.noise(P, 1.0 / 70.0, 3.0, off=(3.0, 1.0, 0.0))
    s2 = t.noise(P, 1.0 / 26.0, 3.0, off=(9.0, 4.0, 0.0))
    s3 = t.noise(P, 1.0 / 7.0, 2.0, off=(1.0, 7.0, 0.0))
    w_d = t.sm(t.add(s1, t.mul(t.sub(s3, 0.5), 0.3)), 0.53, 0.60)
    w_g = t.sm(t.add(s2, t.mul(t.sub(s3, 0.5), 0.3)), 0.57, 0.63)
    w_w = t.mul(t.sm(t.add(t.noise(P, 1.0 / 45.0, 3.0, off=(6.0, 6.0, 0.0)), t.mul(t.sub(s3, 0.5), 0.3)), 0.62, 0.68), 0.9)
    g = mixv(t, w_d, c_s, c_d)
    g = mixv(t, t.mul(w_g, 0.85), g, c_g)
    g = mixv(t, w_w, g, c_w)
    tint = t.mixc(t.sm(t.noise(P, 1.0 / 380.0, 3.0, off=(31.0, 7.0, 0.0)), 0.35, 0.65), (0.40, 0.335, 0.24, 1.0), (0.35, 0.28, 0.19, 1.0))
    tint = t.mixc(t.mul(t.sm(t.noise(P, 1.0 / 130.0, 3.0, off=(3.0, 17.0, 0.0)), 0.5, 0.72), 0.6), tint, (0.31, 0.27, 0.21, 1.0))
    col = t.tint(g, tint)
    col = t.value(col, t.add(0.9, t.mul(t.noise(P, 1.0 / 900.0, 3.0, off=(1.0, 2.0, 0.0)), 0.22)))
    scrub = t.mul(t.sm(t.noise(P, 0.55, 2.0, off=(9.0, 9.0, 0.0)), 0.66, 0.74), t.sm(t.noise(P, 0.018, 3.0, off=(5.0, 2.0, 0.0)), 0.52, 0.66))
    col = t.mixc(t.mul(scrub, 0.65), col, (0.12, 0.12, 0.07, 1.0))
    h = t.add(t.mul(t.height('sand', P, 'FLAT'), 1.0), t.mul(t.height('dry_ground', P, 'FLAT'), w_d))
    return col, h


def track_surface(t, P, across):
    """a track's packed gravel with two ruts where the wheels go, packed and darker (across: from its middle line)
    -> (colour, height): one function, so a road's sanded end (fam_road) goes over into exactly the track it meets"""
    col = t.tint(t.ncol('gravel_ground', P, 'FLAT', k=0.85), (0.38, 0.32, 0.23))
    col = t.value(col, t.add(0.9, t.mul(t.noise(P, 0.08, 3.0), 0.22)))
    rut = t.inv(t.sm(t.m('ABSOLUTE', t.sub(t.m('ABSOLUTE', across), 0.82)), 0.08, 0.3))
    col = t.mixc(t.mul(rut, 0.5), col, t.value(col, 0.8))
    return col, t.height('gravel_ground', P, 'FLAT')


def fam_ground(t, base, arg):
    """THE GROUND, in plan, in the town's own metres: the plain is several grounds in ragged fronts (grit-sand, cracked
    dry ground, gravel, dry grass where water gathers) graded into one hue band by a slow regional tint; yards packed
    and darker; tracks with their ruts; fields in rows; a strike's pale fall when the town has damage"""
    P = t.P0()
    X, Y, Z = t.xyz0()
    if base in ('ground',):
        col, h = ground_plain(t, P)
        rough = 0.95
    elif base == 'track':
        col, h = track_surface(t, P, lane_frame(t, arg)[0])
        rough = 0.95
    elif base == 'yard':
        col = t.tint(t.ncol('dry_ground', P, 'FLAT', k=0.85), (0.29, 0.24, 0.17))
        col = t.value(col, t.add(0.9, t.mul(t.noise(P, 0.08, 3.0), 0.22)))
        rough = 0.95
        h = t.height('dry_ground', P, 'FLAT')
    else:                                                            # fields: a crop in rows, or a dry bed
        key = 'grass' if base == 'field' else 'mud_cracked'
        c = t.ncol(key, P, 'FLAT', k=0.8)
        tint = (0.10, 0.15, 0.055) if base == 'field' else (0.30, 0.24, 0.16)
        col = t.tint(c, tint)
        fx = t.m('FRACT', t.m('DIVIDE', X, 0.75))
        rows = t.sm(t.m('ABSOLUTE', t.sub(fx, 0.5)), 0.18, 0.34)
        col = t.mixc(t.mul(rows, 0.6), col, (0.25, 0.20, 0.13, 1.0))
        rough = 0.93
        h = t.add(t.height(key, P, 'FLAT'), t.mul(rows, -0.03))
    # a strike's pale fall, and the ground burnt at its middle
    sf = t.near()
    col = t.mixc(t.mul(sf, 0.42), col, t.value(PALE, t.add(0.9, t.mul(t.noise(P, 2.0, 2.0), 0.2))))
    return col, rough, 0.0, h


def lane_frame(t, arg):
    """(across, half width, along) of a road's lane frame: 'tl_lane' holds its middle line and half width (masks.py)"""
    X, Y, Z = t.xyz0()
    lane = t.gattr('tl_lane')
    sc = t.N.new('ShaderNodeSeparateColor')
    t.L.new(lane.outputs['Color'], sc.inputs[0])
    across = t.sub(X if arg == 'y' else Y, sc.outputs[0])
    return across, sc.outputs[1], (Y if arg == 'y' else X)


def fam_road(t, base, arg):
    """asphalt as it is driven: the dust swept into the gutters, two darker, smoother wheel paths a lane, a thin oil
    line between them, cracks in the wheel paths, lane-square patches; sand and the track over its ends; near a strike
    its pale fall"""
    P = t.P0()
    near = t.near()
    g = t.ncol('asphalt', P, 'FLAT', k=0.8)
    col = t.tint(g, (0.085, 0.082, 0.077))
    col = t.value(col, t.add(0.86, t.mul(t.noise(P, 0.025, 3.0, off=(4.0, 4.0, 0.0)), 0.28)))
    rough = t.rough('asphalt', P, 'FLAT', lo=0.75, hi=0.95)
    across, hw, alo = lane_frame(t, arg)
    a_ = t.m('ABSOLUTE', across)
    e = t.sub(hw, a_)                                                # from the kerb
    main = t.sm(hw, 4.0, 4.5)                                        # the 11 m road: a median, two lanes each way
    lc = t.add(t.mul(hw, 0.5), t.mul(main, 0.3))
    wp = t.mn(t.m('ABSOLUTE', t.sub(a_, t.sub(lc, 0.85))), t.m('ABSOLUTE', t.sub(a_, t.add(lc, 0.85))))
    stretch = t.comb(t.mul(alo, 0.08), t.mul(across, 1.0), 0.0)
    wpath = t.mul(t.inv(t.sm(wp, 0.12, 0.42)), t.add(0.7, t.mul(t.noise(stretch, 3.0, 2.0), 0.6)))
    col = t.mixc(t.mul(wpath, 0.6), col, t.value(col, 0.78))
    rough = t.mixf(t.mul(wpath, 0.7), rough, 0.62)
    oil = t.mul(t.inv(t.sm(t.m('ABSOLUTE', t.sub(a_, lc)), 0.04, 0.28)), t.sm(t.noise(stretch, 6.0, 2.0), 0.45, 0.7))
    col = t.mixc(t.mul(oil, 0.55), col, (0.02, 0.019, 0.018, 1.0))
    # patches: lane-square repairs, a thin sealant line round each, one cell in twenty-two (many more, and from the air
    # the road reads as ruled in boxes)
    cu, ca = t.m('FLOOR', t.m('DIVIDE', alo, 4.5)), t.m('FLOOR', t.m('DIVIDE', across, 1.7))
    pr = t.wnoise(t.comb(cu, ca, 3.0))
    fu, fa = t.m('FRACT', t.m('DIVIDE', alo, 4.5)), t.m('FRACT', t.m('DIVIDE', across, 1.7))
    inside = t.mul(t.sm(t.mn(fu, t.inv(fu)), 0.03, 0.05), t.sm(t.mn(fa, t.inv(fa)), 0.05, 0.08))
    patch = t.mul(t.sm(pr, 0.955, 0.96), inside)
    seal = t.mul(t.sm(pr, 0.955, 0.96), t.sub(t.sm(t.mn(t.mn(fu, t.inv(fu)), t.mn(fa, t.inv(fa))), 0.0, 0.03), inside))
    col = t.mixc(t.mul(patch, 0.7), col, t.value(col, t.add(0.8, t.mul(t.wnoise(t.comb(cu, ca, 9.0)), 0.35))))
    col = t.mixc(t.mul(t.mx(seal, 0.0), 0.35), col, (0.03, 0.03, 0.03, 1.0))
    rough = t.mixf(t.mul(t.mx(seal, 0.0), 0.5), rough, 0.4)
    # alligator cracks in the wheel paths where the base is weak
    cr = t.vor(t.comb(t.mul(alo, 1.0), across, 0.0), 1.0 / 0.16, 'DISTANCE_TO_EDGE', '2D')
    crack = t.mul(t.mul(t.inv(t.sm(cr.outputs['Distance'], 0.0, 0.035)), wpath), t.sm(t.noise(P, 1.0 / 7.0, 2.0, off=(8.0, 3.0, 0.0)), 0.55, 0.66))
    col = t.mixc(t.mul(crack, 0.75), col, (0.012, 0.012, 0.012, 1.0))
    # dust: swept into the gutters, thin drifts across the lanes, the wheel paths driven clean
    gut = t.inv(t.sm(e, 0.12, t.add(0.5, t.mul(t.noise(t.comb(t.mul(alo, 0.15), 0.0, 0.0), 1.0, 2.0), 1.1))))
    drift = t.mul(t.sm(t.add(t.noise(t.comb(t.mul(alo, 0.04), t.mul(across, 0.6), 0.0), 2.0, 3.0), t.mul(t.sub(t.noise(P, 0.06, 2.0), 0.5), 0.6)), 0.52, 0.85), t.inv(wpath))
    dl = t.mx(t.mul(gut, 0.85), t.mul(drift, 0.35))
    dc = t.value(t.mixc(t.mul(near, 0.6), DUST, PALE), t.add(0.85, t.mul(t.noise(P, 3.0, 2.0), 0.3)))
    col = t.mixc(dl, col, dc)
    rough = t.mixf(dl, rough, 0.95)
    col = litter(t, t.comb(alo, across, 0.0), t.add(0.006, t.mul(gut, 0.14)), col)
    h = t.add(t.height('asphalt', P, 'FLAT', k=1.0), t.mul(crack, -0.004))
    # THE SAND OVER THE ASPHALT'S ENDS. Each street is one quad of asphalt that stops where its track goes on (the
    # streets along x at +-PAVED[0], those along y at +-PAVED[1]). Sand blows in off the open ground and the trucks bring
    # the track in on their wheels: at its end the road lies under the very track and plain it meets (the same
    # functions, the same object coordinates: no seam, no hard edge); going in, the cover breaks into lobes and wind
    # streaks, the wheel paths driven clear first, and is gone SAND_REACH[0] m in on the long streets (past the town's
    # last cross street) and SAND_REACH[1] m on the cross streets (their ends run past the outer street). A field in the
    # town's metres, not per quad, so it runs on unbroken where a cross street meets a street.
    X, Y, Z = t.xyz0()
    dx = t.sub(PAVED[0], t.m('ABSOLUTE', X))                         # metres in from the asphalt's end
    dy = t.sub(PAVED[1], t.m('ABSOLUTE', Y))
    lobe = t.mul(t.sub(t.noise(P, 1.0 / 16.0, 3.0, off=(11.0, 5.0, 0.0)), 0.5), 18.0)   # the drifts' fronts, +-9 m,
    rx = t.inv(t.sm(t.add(dx, t.mul(lobe, t.sm(dx, 0.0, 8.0))), 0.0, SAND_REACH[0]))    # none at the very end: whole there
    ry = t.inv(t.sm(t.add(dy, t.mul(lobe, t.mul(t.sm(dy, 0.0, 4.0), 0.4))), 0.0, SAND_REACH[1]))
    reach = t.mx(rx, ry)
    u_ = t.add(t.mul(X, 0.8), t.mul(Y, 0.6))                         # the wind: from the north-west, streaks along it
    v_ = t.sub(t.mul(Y, 0.8), t.mul(X, 0.6))
    streak = t.noise(t.comb(u_, t.mul(v_, 7.0), 0.0), 0.2, 3.0, off=(3.0, 9.0, 0.0))
    cover = t.sm(t.add(reach, t.mul(t.sub(streak, 0.5), 0.6)), 0.3, 0.7)
    clear = t.mul(t.mn(wpath, 1.0), t.mul(t.inv(t.sm(reach, 0.7, 0.98)), 0.75))
    cover = t.mul(cover, t.inv(clear))
    c_tr, h_tr = track_surface(t, P, across)
    c_gr, h_gr = ground_plain(t, P)
    tw = t.mul(hw, 0.7)                                              # the track is 0.7 of the road's width, on its middle
    side = t.sm(a_, t.sub(tw, 0.3), t.add(tw, 0.3))
    col = t.mixc(cover, col, t.mixc(side, c_tr, c_gr))
    rough = t.mixf(cover, rough, 0.95)
    h = t.mixf(cover, h, t.mixf(side, h_tr, h_gr))
    # a strike: its pale fall across the road, the scorch where it burned
    col = t.mixc(t.mul(near, 0.42), col, t.value(PALE, t.add(0.85, t.mul(t.noise(P, 1.5, 2.0), 0.3))))
    return col, rough, 0.0, h


def fam_walk(t, base, arg):
    """the pavement (and the mosque's square): concrete pavers, dust lying in their joints, stains; the median's top
    is earth, its sides concrete"""
    P = t.P0()
    if base == 'median':
        dirt = t.tint(t.ncol('dirt', P, 'FLAT', k=0.8), (0.20, 0.16, 0.11))
        side = t.tint(t.ncol('concrete', t.Ps(), k=0.8), (0.30, 0.285, 0.26))
        col = t.mixc(t.up(), side, dirt)
        rough = 0.93
        col, rough, _ = dusted(t, col, rough, 0.1, 0.25)
        return col, rough, 0.0, t.mul(t.height('dirt', P, 'FLAT'), t.up())
    g = t.ncol('pavers', P, 'BOX', k=0.4)                            # (at 0.75 the set's stones printed as a busy blue-grey quilt)
    col = t.tint(g, (0.33, 0.305, 0.265))
    col = t.value(col, t.add(0.9, t.mul(t.noise(P, 0.2, 3.0), 0.2)))
    d = t.tex('pavers', 'disp', P, 'BOX')
    joint = t.inv(t.sm(d, 0.18, 0.42))
    col = t.mixc(t.mul(joint, 0.75), col, DUST)
    stain = t.mul(t.sm(t.noise(P, 0.6, 3.0, off=(2.0, 2.0, 0.0)), 0.66, 0.74), 0.4)
    col = t.mixc(stain, col, t.value(col, 0.6))
    rough = t.rough('pavers', P, 'BOX', lo=0.8, hi=0.97)
    col, rough, _ = dusted(t, col, rough, 0.12, 0.18)
    X, Y, Z = t.xyz0()
    col = litter(t, t.comb(X, Y, 0.0), 0.03, col)
    return col, rough, 0.0, t.height('pavers', P, 'BOX')


def fam_kerb(t, base, arg):
    """kerb stones painted in bands, black and white on the town's streets, yellow and black round the median, the
    paint mostly worn off their tops, clinging in the stone's pores"""
    Ps = t.Ps()
    g = t.ncol('concrete_smooth', Ps, k=1.3)
    stone = t.tint(g, (0.32, 0.31, 0.28))
    X, Y, Z = t.xyz0()
    band = t.sm(t.m('FRACT', t.m('DIVIDE', t.add(X, Y), 1.6)), 0.48, 0.52)
    paint = t.mixc(band, (0.04, 0.04, 0.04, 1.0), (0.55, 0.53, 0.47, 1.0) if arg != 'y' else (0.58, 0.44, 0.05, 1.0))
    wear = t.sm(t.add(t.noise(Ps, 1.2, 4.0), t.mul(t.up(), 0.25)), 0.5, 0.62)
    col = t.mixc(t.mul(wear, 0.85), paint, stone)
    rough = t.mixf(wear, 0.6, 0.9)
    col, rough, _ = dusted(t, col, rough, 0.14, 0.35)
    return col, rough, 0.0, t.height('concrete_smooth', Ps)


def fam_rubble(t, base, arg):
    """what a strike left lying: broken concrete and block as gravel and grit, pale with its own dust; a crater's
    floor burnt dark under the dust that came back down"""
    Ps = t.Ps()
    if base == 'crater':
        c = t.ncol('burnt', Ps, 'BOX', k=0.6)
        col = t.tint(c, (0.11, 0.10, 0.09))
        col = t.mixc(t.mul(t.sm(t.noise(Ps, 1.0, 3.0), 0.5, 0.75), 0.5), col, PALE)
        return col, 0.95, 0.0, t.height('burnt', Ps)
    a = t.ncol('gravel_ground', Ps, k=0.9)
    b = t.ncol('gravel', Ps, k=0.8)
    g = mixv(t, t.sm(t.noise(Ps, 1.2, 3.0), 0.4, 0.6), a, b)
    col = t.tint(g, (0.33, 0.31, 0.28) if base == 'rubble' else (0.32, 0.30, 0.27))
    col = t.value(col, t.add(0.85, t.mul(t.noise(Ps, 0.5, 3.0), 0.3)))
    col, rough, _ = dusted(t, col, 0.93, 0.12, 0.22)
    return col, rough, 0.0, t.add(t.height('gravel_ground', Ps, k=0.8), t.height('gravel', Ps, k=0.5))


def fam_interior(t, base, arg):
    """the rooms that stand open: painted plaster on walls and ceilings (its fine photograph in the room's colour), the
    floors' terrazzo; soot and the fall's dust where a strike reached in"""
    Ps, near = t.Ps(), t.near()
    if base == 'floor':
        g = t.ncol('terrazzo', Ps, k=0.55)
        col = t.tint(g, (0.34, 0.31, 0.27))
        col, rough, _ = dusted(t, col, 0.45, 0.16, 0.2)
        return col, rough, 0.0, 0.0
    rgb = PLAIN[base][0] if base in PLAIN else (0.5, 0.49, 0.45)
    g = t.ncol('plaster_fine', Ps, k=2.0)
    col = t.tint(g, rgb)
    w = t.ncol('plaster_worn', Ps, k=1.0)
    col = t.mixc(t.mul(t.sm(t.noise(Ps, 0.5, 3.0), 0.6, 0.7), 0.6), col, t.tint(w, rgb))
    sm_ = t.mul(t.mul(t.sm(t.noise(Ps, 0.3, 3.0, off=(3.0, 3.0, 3.0)), 0.45, 0.75), near), 0.85)
    col = t.mixc(sm_, col, SOOT)
    col, rough, _ = dusted(t, col, 0.9, 0.06, 0.3)
    return col, rough, 0.0, t.height('plaster_fine', Ps)


def fam_mosque(t, base, arg):
    """the mosque: bone stucco; its dome's glazed tiles in their courses, each its own shade; the finial's gilt"""
    Ps = t.Ps()
    if base == 'mosque':
        g = t.ncol('stucco', Ps, k=1.1)
        col = t.tint(g, (0.53, 0.49, 0.40))
        dr = drips(t, 0.8)
        col = t.mixc(t.mul(dr, 0.45), col, t.value(col, 0.6))
        col = t.mixc(t.mul(splash(t, 1.0), 0.45), col, t.value(t.mixc(0.5, DUST, col), 0.85))
        col, rough, _ = dusted(t, col, 0.88, 0.04, 0.4)
        return col, rough, 0.0, t.height('stucco', Ps)
    if base == 'gold':
        return (0.62, 0.45, 0.16, 1.0), 0.32, 1.0, 0.0
    rgb, rough, metal, dust = PLAIN[base]
    X, Y, Z = t.xyz0()
    tile = t.vor(t.comb(t.mul(t.add(X, Y), 1.0), t.mul(Z, 1.0), 0.0), 1.0 / 0.11, 'F1', '2D', rand=0.0)
    cr = t.N.new('ShaderNodeSeparateColor')
    t.L.new(tile.outputs['Color'], cr.inputs[0])
    col = t.value((*rgb, 1.0), t.add(0.82, t.mul(cr.outputs[0], 0.36)))
    edge = t.vor(t.comb(t.mul(t.add(X, Y), 1.0), t.mul(Z, 1.0), 0.0), 1.0 / 0.11, 'DISTANCE_TO_EDGE', '2D', rand=0.0)
    grout = t.inv(t.sm(edge.outputs['Distance'], 0.0, 0.05))
    col = t.mixc(t.mul(grout, 0.8), col, (0.30, 0.29, 0.26, 1.0))
    col, rough_, _ = dusted(t, col, rough, 0.04, 0.2)
    return col, t.mixf(grout, rough_, 0.85), 0.0, t.mul(grout, -0.002)


def fam_paint_metal(t, base, arg):
    """painted steel (doors, gates, tanks, stands, cooler cabinets, a dish): the paint's colour over the steel's own
    grain; rust where the paint failed and water sat: low on the door, at its edges, in runs below; dust"""
    Ps = t.Ps()
    rgb, rough, metal, dust = PLAIN.get(base, ((0.3, 0.3, 0.3), 0.5, 0.0, 0.2))
    g = t.ncol('metal', Ps, k=1.0)
    paint = t.tint(t.vm('MULTIPLY_ADD', t.vm('SUBTRACT', g, (1.0, 1.0, 1.0)), (0.5, 0.5, 0.5), (1.0, 1.0, 1.0)), rgb)
    rust = t.tint(t.ncol('rust', Ps, k=0.9), (0.16, 0.07, 0.035))
    X, Y, Z = t.xyz0()
    amount = {'door_rust': 0.75, 'steel_dark': 0.35, 'steel_paint': 0.3, 'cooler': 0.25, 'dish': 0.12, 'dish_dark': 0.1, 'tank_red': 0.35,
              'lamp_head': 0.15, 'car_bed': 0.25, 'barrel_rust': 0.9, 'rust': 1.2, 'rebar': 1.2}.get(base, 0.2)
    low = t.inv(t.sm(Z, 0.05, 0.6))
    rmask = t.sm(t.add(t.add(t.noise(Ps, 2.2, 4.0, rough=0.65), t.mul(low, 0.25)), amount - 0.2), 0.66, 0.70)
    runs = t.mul(t.sm(t.noise(t.comb(t.mul(t.along(), 6.0), t.mul(Z, 0.4), 0.0), 3.0, 2.0), 0.55, 0.75), t.mul(t.wall(), amount))
    col = t.mixc(rmask, paint, rust)
    col = t.mixc(t.mul(runs, 0.35), col, t.value(rust, 1.2))
    rough = t.mixf(rmask, rough, 0.88)
    metal_ = 0.0                                                     # (paint and rust are dielectrics, even on steel)
    col, rough, _ = dusted(t, col, rough, dust or 0.1, 0.45)
    return col, rough, metal_, t.mul(t.height('rust', Ps), rmask)


def fam_shutter(t, base, arg):
    """a roller shutter: the photograph's slats in the shutter's paint, rust coming through at its foot, dust on every
    slat's lip"""
    Ps = t.Ps()
    pal = [(0.30, 0.32, 0.34), (0.22, 0.27, 0.23), (0.36, 0.34, 0.28), (0.18, 0.23, 0.31), (0.34, 0.20, 0.13), (0.42, 0.42, 0.40)]
    g = t.ncol('shutter', Ps, k=1.2)
    col = t.tint(g, pal[int(arg or 0) % len(pal)])
    rust = t.tint(t.ncol('rust', Ps, k=0.9), (0.16, 0.07, 0.035))
    X, Y, Z = t.xyz0()
    rm = t.sm(t.add(t.noise(Ps, 1.5, 4.0), t.mul(t.inv(t.sm(t.m('FRACT', t.m('DIVIDE', Z, 2.8)), 0.0, 0.5)), 0.2)), 0.68, 0.72)
    col = t.mixc(rm, col, rust)
    col, rough, _ = dusted(t, col, t.mixf(rm, 0.5, 0.85), 0.16, 0.3)
    return col, rough, t.mul(0.3, t.inv(rm)), t.height('shutter', Ps)


def fam_zinc(t, base, arg):
    """galvanised steel: 'zinc_old', a corrugated sheet (a shed's roof, a fence), the photograph's sheet with its zinc
    gone white and dull with age and rust where it is oldest; 'zinc', smooth galvanised work (lamp posts, poles,
    stands): the steel's own grain, never the sheet's corrugations (box-mapped round a post they wind as a spiral)"""
    Ps = t.Ps()
    old = base == 'zinc_old'
    g = t.ncol('corrugated', Ps, k=0.9) if old else t.vm('MULTIPLY_ADD', t.vm('SUBTRACT', t.ncol('metal', Ps), (1.0, 1.0, 1.0)), (0.6, 0.6, 0.6), (1.0, 1.0, 1.0))
    col = t.tint(g, (0.48, 0.49, 0.48) if not old else (0.40, 0.40, 0.38))
    rust = t.tint(t.ncol('rust', Ps, k=0.9), (0.16, 0.07, 0.035))
    rm = t.sm(t.noise(Ps, 1.1, 4.0), 0.62 if old else 0.72, 0.66 if old else 0.75)
    col = t.mixc(rm, col, rust)
    col, rough, d = dusted(t, col, t.mixf(rm, 0.42 if not old else 0.6, 0.85), 0.15, 0.45)
    return col, rough, t.mul(t.inv(rm), t.inv(d)), (t.height('corrugated', Ps) if old else 0.0)    # (bare zinc is metal; rust and dust are not)


def fam_fabric(t, base, arg):
    """canvas, tarps, washing, sacks, a mattress: a woven cloth's grain in the cloth's colour, faded where the sun
    reaches, dust on what lies flat; an awning's stripes a hand wide"""
    Ps = t.Ps()
    g = t.ncol('fabric', Ps, k=0.7)
    if base == 'awn':
        X, Y, Z = t.xyz0()
        pal = [((0.42, 0.07, 0.05), (0.55, 0.52, 0.45)), ((0.06, 0.20, 0.40), (0.55, 0.52, 0.45)), ((0.58, 0.44, 0.10), (0.42, 0.10, 0.06)),
               ((0.10, 0.28, 0.15), (0.52, 0.50, 0.42)), ((0.42, 0.36, 0.26), (0.36, 0.30, 0.20)), ((0.50, 0.22, 0.06), (0.52, 0.46, 0.30))][int(arg or 0) % 6]
        s = t.sm(t.m('FRACT', t.m('DIVIDE', t.add(X, Y), 0.36)), 0.47, 0.53)
        rgb = t.mixc(s, (*pal[0], 1.0), (*pal[1], 1.0))
    elif base == 'rug':
        pal = [(0.30, 0.04, 0.035), (0.05, 0.08, 0.22), (0.34, 0.12, 0.05), (0.22, 0.05, 0.12)][int(arg or 0) % 4]
        rgb = t.value((*pal, 1.0), t.add(0.62, t.mul(t.noise(Ps, 2.2, 3.0), 0.76)))
    else:
        rgb = (*PLAIN[base][0], 1.0)
    col = t.tint(g, rgb)
    fade = t.mul(t.up(0.3, 0.9), 0.35)
    col = t.mixc(fade, col, t.value(t.mixc(0.5, col, (0.6, 0.58, 0.52, 1.0)), 1.05))
    col, rough, _ = dusted(t, col, 0.92, 0.05, 0.3)
    return col, rough, 0.0, t.height('fabric', Ps)


def fam_car(t, base, arg):
    """a car's paint under its clear coat, dusty on the roof and bonnet, dirty low down; a burnt car's shell: rust over
    char, grey ash on what faces up"""
    Ps = t.Ps()
    X, Y, Z = t.xyz0()
    if base == 'car_burnt':
        rust = t.tint(t.ncol('rust', Ps, k=1.0), (0.12, 0.05, 0.025))
        char = t.value(rust, 0.25)
        col = t.mixc(t.sm(t.noise(Ps, 1.4, 4.0), 0.45, 0.6), char, rust)
        col = t.mixc(t.mul(t.up(), 0.6), col, (0.30, 0.29, 0.27, 1.0))
        return col, 0.92, 0.0, t.height('rust', Ps, k=2.0)
    paint = t.palette(t.rnd(), CARS)
    low = t.inv(t.sm(Z, 0.15, 0.75))
    col = t.mixc(t.mul(low, 0.55), paint, t.value(t.mixc(0.5, DUST, paint), 0.85))
    col, rough, d = dusted(t, col, 0.32, 0.06, 0.55)
    return col, rough, 0.0, 0.0


def fam_plastic(t, base, arg):
    """plastic in the sun: its colour, chalky where the sun has worked on it longest (what faces up), dust"""
    rgb, rough, metal, dust = PLAIN[base]
    Ps = t.Ps()
    col = t.value((*rgb, 1.0), t.add(0.94, t.mul(t.noise(Ps, 1.5, 3.0), 0.12)))
    col = t.mixc(t.mul(t.up(0.2, 0.9), 0.25), col, t.value(t.mixc(0.5, col, (0.62, 0.62, 0.6, 1.0)), 1.0))
    col, rough, _ = dusted(t, col, rough, dust or 0.08, 0.5)
    return col, rough, metal, 0.0


def fam_wood(t, base, arg):
    Ps = t.Ps()
    key = 'cardboard' if base == 'cardboard' else 'wood'
    rgb = PLAIN[base][0]
    col = t.tint(t.ncol(key, Ps, k=0.6), rgb)
    col, rough, _ = dusted(t, col, 0.85, 0.12, 0.45)
    return col, rough, 0.0, t.height(key, Ps)


# ==================================================================================================== by name
FAMILIES = {
    'plaster': fam_plaster, 'plaster_b': fam_plaster, 'plaster_w': fam_plaster, 'plaster_dmg': fam_plaster,
    'block': fam_masonry, 'brick': fam_masonry, 'claustra': fam_masonry,
    'concrete': fam_concrete, 'concrete_broken': fam_concrete, 'pole': fam_concrete,
    'roof': fam_roof, 'roof_dmg': fam_roof,
    'ground': fam_ground, 'yard': fam_ground, 'track': fam_ground, 'field': fam_ground, 'field_dry': fam_ground,
    'road': fam_road, 'walk': fam_walk, 'median': fam_walk, 'kerb': fam_kerb,
    'rubble': fam_rubble, 'crater': fam_rubble,
    'floor': fam_interior, 'ceiling': fam_interior, 'in_blue': fam_interior, 'in_green': fam_interior, 'in_white': fam_interior,
    'in_pink': fam_interior, 'in_cream': fam_interior,
    'mosque': fam_mosque, 'dome': fam_mosque, 'dome_blue': fam_mosque, 'tile_band': fam_mosque, 'gold': fam_mosque,
    'door_green': fam_paint_metal, 'door_blue': fam_paint_metal, 'door_brown': fam_paint_metal, 'door_grey': fam_paint_metal,
    'door_rust': fam_paint_metal, 'steel_dark': fam_paint_metal, 'steel_paint': fam_paint_metal, 'cooler': fam_paint_metal,
    'dish': fam_paint_metal, 'dish_dark': fam_paint_metal, 'tank_red': fam_paint_metal, 'lamp_head': fam_paint_metal,
    'car_bed': fam_paint_metal, 'ac': fam_paint_metal, 'speaker': fam_paint_metal,
    'rust': fam_paint_metal, 'rebar': fam_paint_metal, 'barrel_rust': fam_paint_metal,
    'shutter': fam_shutter, 'zinc': fam_zinc, 'zinc_old': fam_zinc,
    'awn': fam_fabric, 'rug': fam_fabric, 'sack': fam_fabric, 'mattress': fam_fabric, 'cooler_pad': fam_fabric,
    'car': fam_car, 'car_burnt': fam_car,
    'tank_white': fam_plastic, 'tank_black': fam_plastic, 'tank_blue': fam_plastic, 'plastic_white': fam_plastic,
    'plastic_blue': fam_plastic, 'plastic_red': fam_plastic, 'crate': fam_plastic, 'barrel_blue': fam_plastic,
    'bike_red': fam_plastic, 'bike_blue': fam_plastic, 'ac_fan': fam_plastic,
    'wood': fam_wood, 'wood_pale': fam_wood, 'cardboard': fam_wood,
}
for _k in list(PLAIN):
    if _k.startswith(('cloth', 'tarp_')):
        FAMILIES[_k] = fam_fabric
for _k in ('rust', 'rebar', 'barrel_rust'):                         # (all rust: the paint is the rust)
    PLAIN[_k] = (PLAIN[_k][0], 0.9, 0.0, 0.15)


def _new(name):
    m = bpy.data.materials.new('town.' + name)
    m.use_nodes = True
    nt = m.node_tree
    for n in list(nt.nodes):
        if n.type != 'OUTPUT_MATERIAL':
            nt.nodes.remove(n)
    t = T(nt)
    bs = t.N.new('ShaderNodeBsdfPrincipled')
    t.L.new(bs.outputs[0], next(n for n in nt.nodes if n.type == 'OUTPUT_MATERIAL').inputs[0])
    return m, t, bs


def _plant(t, base):
    """the palms' and the built yard trees' materials: plain colours with a little noise; the palm's trunk ringed"""
    if base in ('trunk', 'palm_trunk'):
        rgb = {'trunk': (0.16, 0.12, 0.085), 'palm_trunk': (0.20, 0.155, 0.105)}[base]
        P = t.Ps()
        n_big, n_mid, n_fine = t.noise(P, 0.06, 3.0), t.noise(P, 0.7, 3.0), t.noise(P, 6.0, 2.0)
        col = t.value((*rgb, 1.0), t.add(t.add(1.0, t.mul(t.sub(n_big, 0.5), 0.34)), t.add(t.mul(t.sub(n_mid, 0.5), 0.2), t.mul(t.sub(n_fine, 0.5), 0.1))))
        h = None
        if base == 'palm_trunk':
            X, Y, Z = t.xyz0()
            fz = t.m('FRACT', t.m('DIVIDE', Z, 0.16))
            col = t.value(col, t.add(0.7, t.mul(fz, 0.6)))
            h = t.mul(fz, 0.02)
        return col, 0.92, 0.0, h
    rgb, rough, metal, dust = PLAIN[base]
    col = t.value((*rgb, 1.0), t.add(0.8, t.mul(t.noise(t.obj(), 1.7, 2.0), 0.4)))
    return col, rough, metal, None


def M(name):
    """the material of a face's name ('plaster', 'awn:3', 'shutter:2', 'sign:0' ...), made once in a file"""
    key = 'town.' + name.replace(':', '_')
    got = bpy.data.materials.get(key)
    if got is not None:
        return got
    base, _, arg = name.partition(':')
    m, t, bs = _new(name.replace(':', '_'))
    coat = 0.0
    if base in PLANTS:
        col, rough, metal, h = _plant(t, base)
    elif base == 'sign':                                             # a sign given as a picture: laid on the board's UVs
        tc = t.N.new('ShaderNodeTexCoord')
        im = t.N.new('ShaderNodeTexImage')
        img = bpy.data.images.load(SIGNS[int(arg)]['image'], check_existing=True)
        if not img.packed_file:
            img.pack()
        im.image = img
        t.L.new(tc.outputs['UV'], im.inputs['Vector'])
        col = t.value(im.outputs['Color'], 0.92)
        col, rough, _ = dusted(t, col, 0.55, 0.12, 0.3)
        metal, h = 0.0, None
    elif base in ('sign_board', 'sign_text'):                        # a painted board, and the letters painted on it
        board, ink = BOARDS[int(arg or 0) % len(BOARDS)]
        Ps = t.Ps()
        col = t.value((*(board if base == 'sign_board' else ink), 1.0), t.add(0.9, t.mul(t.noise(Ps, 1.4, 3.0), 0.2)))
        col, rough, _ = dusted(t, col, 0.6, 0.12 if base == 'sign_board' else 0.08, 0.3)
        metal, h = 0.0, None
    elif base in FAMILIES:
        col, rough, metal, h = FAMILIES[base](t, base, arg)
        if base == 'car':
            coat = 0.7
    else:
        rgb, rough, metal, dust = PLAIN.get(base, ((0.3, 0.3, 0.3), 0.8, 0.0, 0.1))
        col, h = (*rgb, 1.0), None
        if dust is not None:
            col, rough, _ = dusted(t, col, rough, dust, 0.4)
        if base in ('glass', 'car_glass', 'solar'):
            # a window in a dusty town is dusty: a film on the glass, heavier at its foot
            X, Y, Z = t.xyz0()
            col, rough = t.mixc(0.18, col, DUST), t.mixf(0.18, rough, 0.5)
    t.put(bs.inputs['Base Color'], col)
    t.put(bs.inputs['Roughness'], rough)
    t.put(bs.inputs['Metallic'], metal)
    if coat:
        bs.inputs['Coat Weight'].default_value, bs.inputs['Coat Roughness'].default_value = coat, 0.12
    if h is not None and not isinstance(h, float):
        bp = t.N.new('ShaderNodeBump')
        bp.inputs['Strength'].default_value, bp.inputs['Distance'].default_value = 1.0, 1.0
        t.L.new(h, bp.inputs['Height'])
        t.L.new(bp.outputs[0], bs.inputs['Normal'])
    return m


def clay():
    """the clay a form is judged in before its surface: one mid grey, no pattern"""
    m = bpy.data.materials.get('town.clay')
    if m is None:
        m, t, bs = _new('clay')
        bs.inputs['Base Color'].default_value = (0.42, 0.42, 0.42, 1.0)
        bs.inputs['Roughness'].default_value = 0.75
    return m
