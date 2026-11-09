"""The vehicles' part materials: one Principled material per map() material id, every pattern drawn per pixel.

The engine's shade() coloured each pixel by its material id with hand lights and a mirror lookup. Here each id is a
Blender material on the faces of that part (SdfObject's materials={id: material}); EEVEE lights it and reflects the
real scene. What shade() drew from the hit position is drawn again in nodes, from the object's own coordinates in
the SDF's three.js frame (Texture Coordinate > Object: Blender (x, y, z) is three (x, -z, y)), so it rides with the
object at any scale and stays sharp at any distance:

    modern sedan   the paint's two-scale metallic fleck (the same sin-hash on floor(p * 320) and floor(p * 80))
    cyberpunk      the racing stripes (decal images of stripeMaskFn, vehicles/livery.py, gated by the normal), the
                   uPaint rim glow pow(1 - N.V, 4) (Layer Weight, per pixel as the engine had it), the hex grille,
                   the badge plate's glyphs (vehicles/badge.py), the underglow and accent strips
    sleek car      the hex-tiled hubcaps on the folded wheel frame
    fighter jet    the camo (its fbm stored per vertex, thresholded per pixel), the nose cone, the wing pinstripes,
                   the ordnance bands, the plume's hot core fading to orange at the rim
    every vehicle  the lamps' view-dependent cores (bright head-on, dimmer at the rim)

Live uniforms are custom properties of the object, read by Attribute nodes (type Object): uPaint, uRough,
uMetalColor, uCamoMode. Change or key them and the render follows.
"""

from __future__ import annotations

import bpy

from ...fx._nodes import Builder, Expr, Vec
from . import parts as P

SQ3 = 1.7320508


class _Part:
    """One part material under construction: its Builder, Principled node and the shared inputs."""

    def __init__(self, car, part):
        self.name = f'{car.object.name}_{part}'
        mat = bpy.data.materials.new(self.name)
        mat.use_nodes = True
        nt = mat.node_tree
        self.mat = mat
        self.bsdf = next(n for n in nt.nodes if n.type == 'BSDF_PRINCIPLED')
        self.b = Builder(nt, x0=-1700, y0=700)
        self._p = self._n = self._facing = None
        self._attrs = {}
        mat['sdf_vehicle_part'] = part

    # the inputs ------------------------------------------------------------------------------------------------
    def p3(self):
        """The shading point in the SDF's three frame: (x, y, z) scalars."""
        if self._p is None:
            tc = self.b.node('ShaderNodeTexCoord')
            x, y, z = self.b.vec(tc.outputs['Object']).xyz()
            self._p = (x, z, -y)
            self._tc = tc
        return self._p

    def n3(self):
        """The object-space shading normal in the SDF's three frame."""
        if self._n is None:
            self.p3()
            nx, ny, nz = self.b.vec(self._tc.outputs['Normal']).xyz()
            self._n = (nx, nz, -ny)
        return self._n

    def facing(self):
        """1 - |N.V| (Layer Weight 'Facing' at blend 0.5): the engine's 1 - NdV."""
        if self._facing is None:
            lw = self.b.node('ShaderNodeLayerWeight')
            lw.inputs['Blend'].default_value = 0.5
            self._facing = Expr(self.b, lw.outputs['Facing'])
        return self._facing

    def fres(self):
        return self.b.pow(self.facing(), 5.0)

    def live(self, name, vector=False):
        """An object custom property (the car's live uniform), as a vector or a scalar."""
        key = (name, vector)
        if key not in self._attrs:
            n = self.b.node('ShaderNodeAttribute', attribute_type='OBJECT', attribute_name=name)
            n.label = name
            self._attrs[key] = Vec(self.b, n.outputs['Vector']) if vector else Expr(self.b, n.outputs['Fac'])
        return self._attrs[key]

    def geometry_attr(self, name):
        n = self.b.node('ShaderNodeAttribute', attribute_type='GEOMETRY', attribute_name=name)
        n.label = name
        return Expr(self.b, n.outputs['Fac'])

    # small vector tools ----------------------------------------------------------------------------------------
    def const(self, v):
        return self.b.combine(float(v[0]), float(v[1]), float(v[2]))

    def vmix(self, a, c, t):
        """mix(a, c, t) of vectors (tuples are constants)."""
        if isinstance(a, tuple) and isinstance(c, tuple):
            d = tuple(ci - ai for ai, ci in zip(a, c))
            return self.const(a) + self.const(d) * t
        a = self.const(a) if isinstance(a, tuple) else a
        c = self.const(c) if isinstance(c, tuple) else c
        return a + (c - a) * t

    def vscale(self, v, k):
        v = self.const(v) if isinstance(v, tuple) else v
        return v * k

    def gt(self, a, b):
        return self.b.math('GREATER_THAN', a, b)

    def lt(self, a, b):
        return self.b.math('LESS_THAN', a, b)

    # the BSDF --------------------------------------------------------------------------------------------------
    def put(self, socket, value):
        self.b.link(value, self.bsdf.inputs[socket])

    def constants(self, spec):
        """A parts-table entry's plain values onto the BSDF."""
        if 'albedo' in spec:
            self.put('Base Color', tuple(spec['albedo']))
        if 'roughness' in spec:
            self.put('Roughness', float(spec['roughness']))
        if 'metallic' in spec:
            self.put('Metallic', float(spec['metallic']))
        if 'specular' in spec:
            self.put('Specular IOR Level', float(spec['specular']))
        if spec.get('coat'):
            self.put('Coat Weight', float(spec['coat']))
            self.put('Coat Roughness', 0.03)

    def emit(self, color):
        self.put('Emission Color', color)
        self.put('Emission Strength', 1.0)

    def lamp_core(self, kind):
        """The engine's view-dependent lamp brightness, per pixel."""
        one_minus = 1.0 - self.fres()
        if kind == 'head':
            return 0.55 + 1.4 * self.b.pow(one_minus, 3.0)
        if kind == 'sleek_head':
            return 0.85 + 1.6 * self.b.pow(one_minus, 3.0)
        if kind == 'tail':
            return 0.7 + 0.5 * (one_minus * one_minus)
        if kind == 'sleek_tail':
            return 0.95 + 0.55 * (one_minus * one_minus)
        raise ValueError(kind)


# ============================================================================================ shared parts ===

def _plain(car, part, spec):
    m = _Part(car, part)
    m.constants(spec)
    if 'emission' in spec:
        m.emit(m.vscale(tuple(spec['emission']), m.lamp_core(spec['core'])))
    return m.mat


# ================================================================================================ modern sedan ===

def _modern_paint(car):
    """uPaint +- a two-scale fleck (shade()'s fract(sin(dot(floor(p * k), v)) * c) hash, per pixel), metallic
    0.55, base roughness max(uRough, 0.35); the clear coat carries the paint's sharp reflection, its roughness
    the paint roughness option (0 wax, 0.18 factory semi-gloss, 0.4 matte / wrap)."""
    m = _Part(car, 'paint')
    b = m.b
    x, y, z = m.p3()
    p = b.combine(x, y, z)
    hi = b.fract(b.sin(b.vmath('DOT_PRODUCT', b.vmath('FLOOR', p * 320.0), (12.9, 78.2, 37.7))) * 43758.5)
    lo = b.fract(b.sin(b.vmath('DOT_PRODUCT', b.vmath('FLOOR', p * 80.0), (45.3, 19.7, 91.1))) * 24831.7)
    fleck = lo + (hi - lo) * 0.6
    base = b.vmath('ADD', m.live('uPaint', vector=True), (fleck - 0.5) * 0.08)
    base = b.vmath('MINIMUM', b.vmath('MAXIMUM', base, (0.0, 0.0, 0.0)), (1.0, 1.0, 1.0))
    rough = m.live('uRough')
    m.put('Base Color', base)
    m.put('Metallic', P.MODERN['paint']['metallic'])
    m.put('Roughness', b.max(rough, P.PAINT_FLOOR['modern']))
    m.put('Coat Weight', P.MODERN['paint']['coat'])
    m.put('Coat Roughness', b.clamp(rough * COAT_ROUGHNESS_SCALE))
    return m.mat


# the clear coat's roughness as a share of paintRoughness: the engine's paint took its env reflection along the mirror
# direction at any roughness (only dimmer as roughness grew), so the coat stays glossy: 0.45 (the modern sedan's
# matte default) gives 0.11, 0.18 (factory semi-gloss) 0.045, 0 a mirror wax. The base keeps the floored roughness.
COAT_ROUGHNESS_SCALE = 0.25


# ============================================================================================== cyberpunk ===

def _cyber_paint(car):
    """The near-black gunmetal body with the racing stripes (decal images of stripeMaskFn, gated per pixel by the
    normal, the side and the wheel arches), the uPaint rim glow pow(1 - N.V, 4) * 0.55 off the stripes, and the
    stripes' own faint self-light (stripe_glow, the engine's 0.45)."""
    from .livery import SIDE_DOMAIN, TOP_DOMAIN, stripe_livery_images
    side_img, top_img = stripe_livery_images(car.program.extra, car.cache_dir)
    if car.spec.pack_images:                    # make(pack_images=True): the .blend carries the livery too
        for img in (side_img, top_img):
            if img.packed_file is None:
                img.pack()
    spec = P.CYBER['paint']
    m = _Part(car, 'paint')
    b = m.b
    x, y, z = m.p3()
    nx, ny, _nz = m.n3()
    (z0, z1), (y0, y1) = SIDE_DOMAIN['z'], SIDE_DOMAIN['y']
    (tx0, tx1), (tz0, tz1) = TOP_DOMAIN['x'], TOP_DOMAIN['z']
    side = b.node('ShaderNodeTexImage', image=side_img, interpolation='Linear', extension='EXTEND')
    b.link(b.combine((z - z0) / (z1 - z0), (y - y0) / (y1 - y0), 0.0), side.inputs['Vector'])
    right, left, _b = b.vec(side.outputs['Color']).xyz()
    top = b.node('ShaderNodeTexImage', image=top_img, interpolation='Linear', extension='EXTEND')
    b.link(b.combine((x - tx0) / (tx1 - tx0), (z - tz0) / (tz1 - tz0), 0.0), top.inputs['Vector'])
    topm, _g, _b2 = b.vec(top.outputs['Color']).xyz()
    right = right * m.gt(nx, 0.6) * m.gt(x, 0.05)
    left = left * m.lt(nx, -0.6) * m.lt(x, -0.05)
    topm = topm * m.gt(ny, 0.6)
    sm = b.max(b.max(right, left), topm)
    # suppressed inside the wheel arches (curved interiors read wrong with stripes designed for flat panels)
    a_f = b.sqrt((y - 0.36) * (y - 0.36) + (z - 1.40) * (z - 1.40)) - 0.48
    a_r = b.sqrt((y - 0.36) * (y - 0.36) + (z + 1.40) * (z + 1.40)) - 0.48
    in_arch = m.gt(b.abs(x), 0.45) * m.lt(b.min(a_f, a_r), 0.0)
    sm = sm * (1.0 - in_arch)
    stripe = tuple(spec['stripe'])
    rough = m.live('uRough')
    m.put('Base Color', m.vmix(tuple(spec['albedo']), stripe, sm))
    m.put('Metallic', 1.0 - sm)
    m.put('Roughness', b.max(rough, P.PAINT_FLOOR['cyber']) + (spec['stripe_roughness']
                                                                 - b.max(rough, P.PAINT_FLOOR['cyber'])) * sm)
    m.put('Coat Weight', spec['coat'] * (1.0 - sm))
    m.put('Coat Roughness', b.clamp(rough * COAT_ROUGHNESS_SCALE))
    rim = b.pow(m.facing(), 4.0) * spec['rim_glow'] * (1.0 - sm)
    glow = m.live('uPaint', vector=True) * rim + m.const(stripe) * (sm * car.stripe_glow)
    m.emit(glow)
    m.mat['stripe_images'] = [side_img.name, top_img.name]
    return m.mat


def _cyber_glow(car, part):
    """Underglow / accent strips: uPaint * (k0 + k1 (1 - fres)^2), unlit."""
    spec = P.CYBER[part]
    m = _Part(car, part)
    m.constants(spec)
    one_minus = 1.0 - m.fres()
    k0, k1 = spec['glow']
    m.emit(m.live('uPaint', vector=True) * (k0 + k1 * (one_minus * one_minus)))
    return m.mat


def _cyber_grille(car):
    """The hex grille: shade()'s two offset hex lattices on the plate face (22 cells a metre), cells glowing
    uPaint * 0.85, walls a dark mesh."""
    spec = P.CYBER['grille']
    m = _Part(car, 'grille')
    b = m.b
    x, y, _z = m.p3()
    gx = x * 22.0
    gy = (y - 0.55) * 22.0
    c1x = b.floor(gx) + 0.5
    c1y = (b.floor(gy / SQ3) + 0.5) * SQ3
    c2x = b.floor(gx - 0.5) + 1.0
    c2y = (b.floor((gy - 0.5 * SQ3) / SQ3) + 0.5) * SQ3 + 0.5 * SQ3
    d1 = b.sqrt((gx - c1x) * (gx - c1x) + (gy - c1y) * (gy - c1y))
    d2 = b.sqrt((gx - c2x) * (gx - c2x) + (gy - c2y) * (gy - c2y))
    wall = b.smoothstep(0.55, 0.78, b.min(d1, d2))
    glow = m.live('uPaint', vector=True) * spec['cell_glow']
    cell = b.vmath('MINIMUM', glow, (1.0, 1.0, 1.0)) * 0.4
    m.put('Base Color', m.vmix(cell, tuple(spec['albedo']), wall))
    m.put('Roughness', spec['roughness'])
    m.put('Specular IOR Level', spec['specular'])
    m.emit(glow * ((1.0 - wall) * 0.6))
    return m.mat


def _cyber_badge(car):
    """The badge plate: its local position unwrapped onto the canvas (z walks u, reversed on the right side so the
    text reads left to right from outside), the canvas alpha as glyph ink on the outward faces."""
    from .badge import badge_image
    spec = P.CYBER['badge']
    m = _Part(car, 'badge')
    b = m.b
    x, y, z = m.p3()
    nx, _ny, _nz = m.n3()
    v = (y - 1.105) / 0.09
    right = m.gt(x, 0.0)
    u_r = (-0.79 - z) / 0.32
    u_l = (z + 1.11) / 0.32
    u = u_l + (u_r - u_l) * right
    img = badge_image(car.decal_text, name=f'{car.object.name}_badge')
    tex = b.node('ShaderNodeTexImage', image=img, interpolation='Linear', extension='CLIP')
    tex['badge_decal'] = True
    b.link(b.combine(u, v, 0.0), tex.inputs['Vector'])
    alpha = Expr(b, tex.outputs['Alpha'])
    inside = (m.gt(u, 0.0) * m.lt(u, 1.0)) * (m.gt(v, 0.0) * m.lt(v, 1.0))
    ink = alpha * b.step(0.7, b.abs(nx)) * inside
    m.put('Base Color', m.vmix(tuple(spec['albedo']), (0.8, 0.8, 0.8), ink))
    m.put('Roughness', spec['roughness'])
    m.put('Specular IOR Level', spec['specular'])
    m.emit(m.vscale(tuple(spec['ink']), ink))
    return m.mat


# ============================================================================================== sleek car ===

def _sleek_paint(car):
    """Pure metal: uMetalColor is F0 (Principled metallic tints it, Schlick to white at grazing), roughness
    max(uRough, 0.06)."""
    m = _Part(car, 'paint')
    m.put('Base Color', m.live('uMetalColor', vector=True))
    m.put('Metallic', 1.0)
    m.put('Roughness', m.b.max(m.live('uRough'), P.PAINT_FLOOR['sleek']))
    return m.mat


def _sleek_hubcap(car):
    """The hex-tiled hubcaps: the wheel fold (|x| - 0.42, |z| - 0.95 at pre-scale 1.5), 60-degree hex cells on
    the disc plane at 12 a unit; mirror cells, a darker rougher border."""
    spec = P.SLEEK['chrome']
    m = _Part(car, 'chrome')
    b = m.b
    _x, y, z = m.p3()
    wy = y / 1.5 - 0.20
    wz = b.abs(z / 1.5) - 0.95
    ux, uy = wy * 12.0, wz * 12.0
    ax = b.mod(ux, 1.0) - 0.5
    ay = b.mod(uy, SQ3) - 0.5 * SQ3
    bx = b.mod(ux - 0.5, 1.0) - 0.5
    by = b.mod(uy - 0.5 * SQ3, SQ3) - 0.5 * SQ3
    sel = m.lt(ax * ax + ay * ay, bx * bx + by * by)
    gx = bx + (ax - bx) * sel
    gy = by + (ay - by) * sel
    hexd = b.max(b.abs(gx) * 0.866 + b.abs(gy) * 0.5, b.abs(gy))
    edge = b.smoothstep(0.40, 0.47, hexd)
    f0 = tuple(spec['albedo'])
    m.put('Base Color', m.vmix(f0, tuple(c * spec['edge_scale'] for c in f0), edge))
    m.put('Metallic', 1.0)
    m.put('Roughness', spec['roughness'] + (spec['edge_roughness'] - spec['roughness']) * edge)
    return m.mat


# ================================================================================================ fighter jet ===

def _jet_hull(car):
    """_jetCamoColor per pixel: the camo blobs smoothstep(0.50, 0.52, fbm(p * 1.6)) from the per-vertex fbm, the
    scheme's (light, dark) chosen by uCamoMode, the dark nose cone past z = 1.5, the wing pinstripes past |x| 0.6."""
    spec = P.JET['hull']
    m = _Part(car, 'hull')
    b = m.b
    x, _y, z = m.p3()
    t = b.smoothstep(0.50, 0.52, m.geometry_attr('jet_camo_fbm'))
    mode = m.live('uCamoMode')
    m0, m1, m2 = m.lt(mode, 0.5), m.lt(mode, 1.5), m.lt(mode, 2.5)

    def pick(i):
        c = [P.CAMO_COLORS[k][i] for k in range(4)]
        v = m.vmix(c[3], c[2], m2)
        v = m.vmix(v, c[1], m1)
        return m.vmix(v, c[0], m0)

    col = m.vmix(pick(0), pick(1), t)
    col = m.vmix(col, (0.20, 0.21, 0.22), b.smoothstep(1.5, 1.52, z))
    ax = b.abs(x)
    striped = m.vmix((0.13, 0.13, 0.13), col, b.smoothstep(0.38, 0.40, b.abs(ax - 2.0)))
    striped = m.vmix((0.55, 0.55, 0.55), striped, b.smoothstep(0.08, 0.10, b.abs(ax - 1.4)))
    col = m.vmix(col, striped, m.gt(ax, 0.6))
    m.put('Base Color', col)
    m.put('Roughness', spec['roughness'])
    m.put('Specular IOR Level', spec['specular'])
    return m.mat


def _jet_weapon(car):
    spec = P.JET['weapon']
    m = _Part(car, 'weapon')
    b = m.b
    _x, _y, z = m.p3()
    band = b.smoothstep(0.92, 1.0, b.abs(b.sin(z * 15.0)))
    m.put('Base Color', m.vscale(tuple(spec['albedo']), 1.0 - spec['band'] * band))
    m.put('Roughness', spec['roughness'])
    m.put('Specular IOR Level', spec['specular'])
    return m.mat


def _jet_plume(car):
    """The plume: mix(cool orange, hot white, smoothstep(0, 0.7, N.V)) per pixel, unlit."""
    spec = P.JET['plume']
    m = _Part(car, 'plume')
    m.constants(spec)
    core = m.b.smoothstep(0.0, 0.7, 1.0 - m.facing())
    m.emit(m.vmix(tuple(spec['cool']), tuple(spec['hot']), core))
    return m.mat


# ============================================================================================ the builders ===

_SPECIAL = {
    'modern': {'paint': _modern_paint},
    'cyber': {'paint': _cyber_paint, 'underglow': lambda c: _cyber_glow(c, 'underglow'),
              'accent': lambda c: _cyber_glow(c, 'accent'), 'grille': _cyber_grille, 'badge': _cyber_badge},
    'sleek': {'paint': _sleek_paint, 'chrome': _sleek_hubcap},
    'jet': {'hull': _jet_hull, 'weapon': _jet_weapon, 'plume': _jet_plume},
}


def part_materials(car):
    """{part name: Material} for every part of car.kind (P.IDS gives the ids that map onto them)."""
    out = {}
    table = P.PARTS[car.kind]
    special = _SPECIAL[car.kind]
    for part in sorted(set(P.IDS[car.kind].values())):
        fn = special.get(part)
        out[part] = fn(car) if fn is not None else _plain(car, part, table[part])
    return out
