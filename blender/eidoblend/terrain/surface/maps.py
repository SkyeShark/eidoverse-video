"""The surface data's map registry (SURFACING_DESIGN.md 2.2): every map the bake makes, what it means, which image
family holds it and how it is stored there. No bpy, numpy only.

    from eidoblend.terrain.surface import maps as MP
    MP.MAPS['settle']                 # MapSpec(name, unit, family, channel, encoding, grid, made_by, doc, ...)
    MP.spec('convex_200m')            # a scaled curvature resolves by its suffix, as masks.parse_name does
    MP.FAMILIES['E']                  # the family's format, colour space and fixed channels
    v = MP.encode(spec, array, cell)  # physical values -> what the image holds (0..1 for the 8-bit families)
    a = MP.decode(spec, v, cell)      # and back
    MP.decode_rule(spec, cells, refs) # ('affine', a, b) | ('square', a, 0.0) | ('z_plus', 1.0, b): what a shader does

Families (each one atlas image holding every level):
    D   RGBA16F, linear   the field normal's x and y, the sub-cell relief's gradient gx and gy      (detail grid)
    E   RGBA8, linear     crease (signed), cavity, crest_fine (signed), grain                       (detail grid)
    M   RGBA8, linear     four maps to an image (M0, M1, ...), packed when a material asks for them (cell grid)
    F   RGBA16F, linear   metres: strata and src_strata, each less the pixel's own height and a per-level reference
    C   RGBA8, sRGB       the far albedo, the far roughness in the linear alpha                      (palette bake)
    P   RGBA8, sRGB       the colour sediment carries, the sediment share in the alpha               (palette bake)
'shader' maps are never stored: the material derives them (slope, aspect, northness and eastness from D's field
normal; height from the object z; insolation from the field normal and the sun). SurfaceData.maps() still returns
them, computed with the same definitions, so a rule written in the mask language reads one vocabulary everywhere.

Encodings:
    'unit'    0..1 as it is
    'signed'  -1..1 as 0.5 + 0.5 v
    'bend'    a curvature kappa (1/m) as its dimensionless bend kappa x scale, clamped to +-1 and stored signed; the
              scale is the map's (20 m for *_20m) or 2 x the level's cell for the unsuffixed ones, so their decode
              differs per level
    'thick'   a thickness in metres as sqrt(t / t_max): at 1 m with t_max 64 the 8-bit step is 6 cm
    'float'   the value itself (the half-float families)
    'z'       metres relative to the pixel's own height and a per-level reference: value = z + reference + texel
    'srgb'    a colour, sRGB-encoded in the image, linear in the arrays
"""
from __future__ import annotations

import re
from dataclasses import dataclass, replace

import numpy as np

F32 = np.float32


@dataclass(frozen=True)
class MapSpec:
    name: str
    unit: str                    # '0-1', '-1..1', 'm', '1/m', 'deg', 'rgb'
    family: str                  # 'D' | 'E' | 'M' | 'F' | 'C' | 'P' | 'shader'
    encoding: str                # see the module doc
    made_by: str                 # 'masks' (masks.py), a bake pass, 'plants' (the plant layer) or 'shader'
    doc: str
    channel: object = None       # the fixed channel (or channels) in D, E, F, C, P; None in M (packed on demand)
    grid: str = 'cell'           # 'cell' | 'detail'
    t_max: float = 64.0          # 'thick': metres stored as 1
    scale_m: object = None       # 'bend': the curvature's scale in metres; None = 2 x the level's cell
    pair: object = None          # the other channel of a two-channel map (n20_x <-> n20_y): packed side by side


# family -> (format, colour space, grid, fixed channel names or None)
FAMILIES = {
    'D': dict(format='RGBA16F', colorspace='Non-Color', grid='detail', is_float=True,
              channels=('normal_x', 'normal_y', 'detail_gx', 'detail_gy')),
    'E': dict(format='RGBA8', colorspace='Non-Color', grid='detail', is_float=False,
              channels=('crease', 'cavity', 'crest_fine', 'grain')),
    'M': dict(format='RGBA8', colorspace='Non-Color', grid='cell', is_float=False, channels=None),
    'F': dict(format='RGBA16F', colorspace='Non-Color', grid='cell', is_float=True,
              channels=('strata', 'src_strata', None, None)),
    'C': dict(format='RGBA8', colorspace='sRGB', grid='cell', is_float=False,
              channels=('far_colour', 'far_colour', 'far_colour', 'far_roughness')),
    'P': dict(format='RGBA8', colorspace='sRGB', grid='cell', is_float=False,
              channels=('down_colour', 'down_colour', 'down_colour', 'down_share')),
}

_M = lambda name, unit, enc, by, doc, **kw: MapSpec(name, unit, 'M', enc, by, doc, **kw)   # noqa: E731

_SPECS = [
    # ---- D and E: the detail grid
    MapSpec('normal_x', '-1..1', 'D', 'float', 'field_normal',
            "the field normal's x: N = normalize(-dh/dx, -dh/dy, 1) of the level's height at D's texel (the mesh's "
            "Catmull-Rom surface, central differences at the texel spacing); z is rebuilt", channel=0, grid='detail'),
    MapSpec('normal_y', '-1..1', 'D', 'float', 'field_normal', "the field normal's y", channel=1, grid='detail'),
    MapSpec('detail_gx', 'm/m', 'D', 'float', 'phacelle',
            "d/dx of the relief below the cell (metres of height per metre): flow-steered gullies on soil slopes, "
            "rock ribs from the breakup strength on bare rock. The material adds it to the field's own gradient",
            channel=2, grid='detail'),
    MapSpec('detail_gy', 'm/m', 'D', 'float', 'phacelle', "d/dy of the relief below the cell", channel=3,
            grid='detail'),
    MapSpec('crease', '-1..1', 'E', 'signed', 'phacelle',
            "the sub-cell relief's curvature, normalised: gully floors and rock joints -, crests and ribs +",
            channel=0, grid='detail'),
    MapSpec('cavity', '0-1', 'E', 'unit', 'cavity',
            'short-radius sky view (2-32 texels of D, over the height plus the sub-cell relief): 1 open, low in '
            'creases and at wall feet', channel=1, grid='detail'),
    MapSpec('crest_fine', '-1..1', 'E', 'signed', 'blur',
            "each level's own finest convexity: the mean of the crest term at 1 and 2 texels of D, on the surface the "
            "cavity march reads (the height plus the sub-cell relief): + on the finest crests, rims and sub-cell "
            "ribs, - in the finest creases and rills. Its meaning changes with the level by design: read it only for "
            "tone, faded with the footprint", channel=2, grid='detail'),
    MapSpec('grain', '0-1', 'E', 'unit', 'carry_src',
            'distance down the fall path from the bare rock above, over the reach (300 m): 0 at the apex of a talus '
            '(fine debris), 1 at its toe and beyond (boulders); 1 where no rock stands above. The fall paths are '
            'drawn among the upslope neighbours by slope, so they follow the fall line (cell grid, upsampled)',
            channel=3, grid='detail'),
    # ---- F: metres
    MapSpec('strata', 'm', 'F', 'z', 'masks',
            'stratigraphic height zs (the strata mask, or the height itself on a terrain without one): the material '
            'reads its rock column at it', channel=0),
    MapSpec('src_strata', 'm', 'F', 'z', 'carry_src',
            "the stratigraphic height of the bare rock a debris cell's material came from (its fall path up to "
            "exposed rock, within 300 m, drawn among the upslope neighbours by slope); the cell's own zs on bare "
            "rock and where no rock stands above", channel=1),
    # ---- C and P: the palette bake
    MapSpec('far_colour', 'rgb', 'C', 'srgb', 'far_colour',
            "the palette's ground colour per texel (every layer at its scan's mean, composited by coverage): the "
            "ground's colour at a distance and the context rings' whole material", channel=(0, 1, 2)),
    MapSpec('far_roughness', '0-1', 'C', 'unit', 'far_colour', 'the roughness that goes with the far colour',
            channel=3),
    MapSpec('down_colour', 'rgb', 'P', 'srgb', 'route_colour',
            'the colour of the sediment a cell carries: the bare rock colours upstream, weighted by where the ground '
            'is eroding, routed down the drainage', channel=(0, 1, 2)),
    MapSpec('down_share', '0-1', 'P', 'unit', 'route_colour',
            'how much of the ground is carried sediment: q / (q + q0) of the routed production', channel=3),
    # ---- M: the existing masks (masks.py), name, unit and meaning unchanged
    _M('height_norm', '0-1', 'unit', 'masks', 'height normalised over the main tile'),
    _M('curv_profile', '1/m', 'bend', 'masks', 'profile curvature at 2 x the level cell (+ convex)'),
    _M('curv_plan', '1/m', 'bend', 'masks', 'plan curvature at 2 x the level cell (+ ridges and spurs)'),
    _M('convex', '0-1', 'unit', 'masks', 'convex ground at 2 x the level cell'),
    _M('concave', '0-1', 'unit', 'masks', 'concave ground at 2 x the level cell'),
    _M('curv_profile_20m', '1/m', 'bend', 'masks', 'profile curvature at 20 m', scale_m=20.0),
    _M('curv_plan_20m', '1/m', 'bend', 'masks', 'plan curvature at 20 m', scale_m=20.0),
    _M('convex_20m', '0-1', 'unit', 'masks', 'convex ground at 20 m'),
    _M('concave_20m', '0-1', 'unit', 'masks', 'concave ground at 20 m'),
    _M('peaks', '0-1', 'unit', 'masks', 'high and convex: summits and ridgelines'),
    _M('flow', '0-1', 'unit', 'masks+route',
       'log10 of the drainage area per metre of contour, normalised over the main tile; on hero levels from the '
       "bake's own routing (the parent's catchment pinned in across the border)"),
    _M('channels', '0-1', 'unit', 'masks+route', 'drainage area above the level threshold (hero levels: re-routed)'),
    _M('wetness', '0-1', 'unit', 'masks+route',
       'topographic wetness ln(a / tan slope) normalised over the main tile; 1 on water (hero levels: re-routed)'),
    _M('wear', 'm', 'thick', 'masks', 'eroded depth', t_max=256.0),
    _M('deposit', 'm', 'thick', 'masks', 'sediment thickness'),
    _M('talus', 'm', 'thick', 'masks', 'talus thickness'),
    _M('sand', 'm', 'thick', 'masks', 'sand thickness'),
    _M('lava', 'as written', 'thick', 'masks', 'lava-flow footprint as the volcanic solver writes it', t_max=4.0),
    _M('water', 'm', 'thick', 'masks', 'lake or sea depth'),
    _M('rock', '0-1', 'unit', 'masks', "the masks package's exposed rock (steep, or deeply worn under thin cover)"),
    _M('rock_toe', '0-1', 'unit', 'masks', 'the ground below exposed rock where fallen rock gathers'),
    _M('snow', '0-1', 'unit', 'masks', "the masks package's snow rule (altitude, aspect, hollows)"),
    _M('occlusion', '0-1', 'unit', 'masks', 'sky-view factor within 500 m: 1 open sky'),
    _M('vegetation', '0-1', 'unit', 'masks', "the masks package's plant suitability"),
    # ---- M: the new maps
    _M('crest', '-1..1', 'signed', 'blur',
       "multi-scale convexity at fixed metre scales: the mean of tanh((h - G h) / (tau sigma)) over sigma = 8, 16, "
       "32, 64, 128 m (those of at least one cell; a scale over 16 cells comes from the parent's pass), so a "
       "threshold on it means the same in a hero window and on the main level: + crests, rims, ribs, spurs; - "
       "creases, chutes, hollows. On gentle ground -crest is the soil-gathering term"),
    _M('settle', '0-1', 'unit', 'relax',
       'where a thin loose layer comes to rest: a 0.5 m layer relaxed at a 20-degree repose for 60 passes, fresh on '
       "every level (plus what the parent gathered beyond it, so the feet of long slopes stay gathered); 0 shed, "
       '0.5 unmoved (flat ground), 1 a metre or more gathered (benches, ledges, crevices, slope feet)'),
    _M('snowpack', 'm', 'thick', 'relax',
       'snow thickness: snowfall by altitude and aspect, slid off at 38 degrees and gathered below, melted by '
       'insolation and under the snowline; or the pack that flowed down the drainage lines at 14 degrees, whichever '
       "is thicker (a fresh fall on every level, plus what the parent gathered beyond its fall)", t_max=16.0),
    _M('fresh', '0-1', 'unit', 'spi',
       "actively eroding ground: on ground under 30 degrees (faded over 25-35) stream power on ground bare of loose "
       "cover (scoured channel floors); on steeper ground only the slope over the rock's own threshold Sc (failing "
       "faces), never stream power (it peaks at the pour-overs, where the varnish curtains hang); both on the 20 m "
       "slope. Water and basins deeper than the fill's cap end their flow, so no flat reads as scoured"),
    _M('spi', '0-1', 'unit', 'spi',
       "stream power log10(a tan S), a the specific catchment and S the slope at 20 m (the same on every level), "
       "normalised by the main tile's 5th-95th percentiles"),
    _M('valley', '0-1', 'unit', 'blur',
       'flat and low at 12 m and wider (an MRVBF-like index on the blur pyramid, the wider scales from the coarser '
       'levels): valley floors, fans, basins; about 0.5 on an open plain'),
    _M('streak', '0-1', 'unit', 'streak',
       "wind exposure on convex ground, trailed ten cells downwind along the palette's wind"),
    _M('n20_x', '-1..1', 'signed', 'blur', "the 20 m normal's x (the height blurred at 20 m): with n20_y the "
       "azimuth and dip of a steep face, which do not twist on small bumps; z is rebuilt", pair='n20_y'),
    _M('n20_y', '-1..1', 'signed', 'blur', "the 20 m normal's y", pair='n20_x'),
    # ---- M: the plant layer's rasters (bake_surface(extra=...))
    _M('canopy', '0-1', 'unit', 'plants', "the placed crowns' cover, a fraction per texel"),
    _M('canopy_expected', '0-1', 'unit', 'plants',
       "the cover the ecotope's tree density implies, on every level whenever the palette has a canopy layer"),
    _M('canopy_far', '0-1', 'unit', 'plants', 'the part of canopy_expected the instances leave to the material'),
    _M('shrubs', '0-1', 'unit', 'plants', 'undergrowth density'),
    _M('shrubs_far', '0-1', 'unit', 'plants', 'the part of the undergrowth the instances leave to the material'),
    # ---- derived in the shader, never stored
    MapSpec('slope', 'deg', 'shader', 'none', 'shader', "slope, from D's field normal: acos(N.z)"),
    MapSpec('aspect', 'deg', 'shader', 'none', 'shader', 'compass bearing the slope faces (0 north, 90 east)'),
    MapSpec('northness', '-1..1', 'shader', 'none', 'shader',
            'cos(aspect), faded to 0 on ground under 3 degrees'),
    MapSpec('eastness', '-1..1', 'shader', 'none', 'shader', 'sin(aspect), faded to 0 on ground under 3 degrees'),
    MapSpec('height', 'm', 'shader', 'none', 'shader', 'the object z: the level height at every pixel of the mesh'),
    MapSpec('slope_20m', 'deg', 'shader', 'none', 'shader',
            "the slope of the 20 m normal (n20): a slope that means the same on every level, for rules that must not "
            "step at a window edge"),
    MapSpec('insolation', '0-1', 'shader', 'none', 'shader',
            "max(0, N_field . s), s the place's climatological sun (palettes.climate_sun from latitude_deg, or the "
            "terrain constants sun_azimuth_deg and sun_elevation_deg where a palette sets them)"),
]
MAPS = {s.name: s for s in _SPECS}

# a two-channel map by one name: SurfaceData.channel('n20') returns both channels
PAIRS = {'n20': ('n20_x', 'n20_y'), 'normal': ('normal_x', 'normal_y'), 'detail_g': ('detail_gx', 'detail_gy')}
SHADER = tuple(s.name for s in _SPECS if s.family == 'shader')
_SCALED = re.compile(r'^(curv_profile|curv_plan|convex|concave)_(\d+(?:p\d+)?)m$')


def spec(name):
    """The MapSpec of a map name; a scaled curvature (convex_200m, curv_plan_50m) resolves by its suffix. Raises
    KeyError naming the nearest names."""
    s = MAPS.get(name)
    if s is not None:
        return s
    m = _SCALED.match(name)
    if m:
        base = MAPS[m.group(1)]
        return replace(base, name=name, scale_m=float(m.group(2).replace('p', '.')),
                       doc=base.doc.replace('2 x the level cell', f'{m.group(2)} m'))
    import difflib
    near = difflib.get_close_matches(name, list(MAPS) + list(PAIRS), n=4, cutoff=0.4)
    raise KeyError(f'no surface map {name!r}' + (f'; nearest: {", ".join(near)}' if near else ''))


def known(name):
    """True when `name` is a surface map (a registry name, a pair name or a scaled curvature)."""
    if name in PAIRS:
        return True
    try:
        spec(name)
        return True
    except KeyError:
        return False


def bend_scale(s, cell):
    """The scale in metres a 'bend' map's curvature is multiplied by on a level of `cell` metres."""
    return float(s.scale_m) if s.scale_m is not None else 2.0 * float(cell)


def encode(s, a, cell=1.0):
    """Physical values -> what the map's image holds: float32, 0..1 for the 8-bit encodings, the value itself for
    'float'. ('z' and 'srgb' maps are encoded by the atlas builder: they need the height and the transfer curve.)"""
    a = np.asarray(a, F32)
    e = s.encoding
    if e == 'unit':
        return np.clip(a, 0.0, 1.0)
    if e == 'signed':
        return np.clip(a, -1.0, 1.0) * F32(0.5) + F32(0.5)
    if e == 'bend':
        return np.clip(a * F32(bend_scale(s, cell)), -1.0, 1.0) * F32(0.5) + F32(0.5)
    if e == 'thick':
        return np.sqrt(np.clip(a, 0.0, s.t_max) * F32(1.0 / s.t_max))
    if e == 'float':
        return a
    raise ValueError(f'map {s.name!r}: encoding {e!r} is not encoded per map')


def decode(s, v, cell=1.0):
    """What the image holds -> physical values (the inverse of encode, up to its clamps)."""
    v = np.asarray(v, F32)
    kind, a, b = decode_rule(s, [cell])
    a = a[0] if isinstance(a, (list, tuple)) else a
    b = b[0] if isinstance(b, (list, tuple)) else b
    if kind == 'square':
        return v * v * F32(a)
    return v * F32(a) + F32(b)


def decode_rule(s, cells=None, refs=None):
    """How a shader turns the map's texel into its value: (kind, a, b).
        ('affine', a, b)    value = a * texel + b
        ('square', a, 0.0)  value = a * texel * texel                       (thicknesses)
        ('z_plus', 1.0, b)  value = object z + b + texel                    (F: b the level's reference, metres)
    a and b are floats, or tuples with one number per level when they differ by level (the unsuffixed curvatures,
    whose scale is 2 x the level's cell; F's references): the material folds those in with the level's other
    constants. cells: every level's cell; refs: every level's reference (F)."""
    e = s.encoding
    if e in ('unit', 'float', 'srgb'):
        return ('affine', 1.0, 0.0)
    if e == 'signed':
        return ('affine', 2.0, -1.0)
    if e == 'thick':
        return ('square', float(s.t_max), 0.0)
    if e == 'bend':
        if s.scale_m is not None:
            return ('affine', 2.0 / float(s.scale_m), -1.0 / float(s.scale_m))
        cs = [float(c) for c in (cells or [1.0])]
        return ('affine', tuple(2.0 / (2.0 * c) for c in cs), tuple(-1.0 / (2.0 * c) for c in cs))
    if e == 'z':
        return ('z_plus', 1.0, tuple(float(r) for r in (refs or [0.0])))
    raise ValueError(f'map {s.name!r} ({e}) is not stored in an image')


def describe():
    """One line per map: name, family, unit, how it is made, meaning."""
    return '\n'.join(f'{s.name:16s} {s.family:6s} {s.unit:10s} {s.made_by:13s} {s.doc}' for s in _SPECS)


__all__ = ['MAPS', 'MapSpec', 'FAMILIES', 'PAIRS', 'SHADER', 'spec', 'known', 'encode', 'decode', 'decode_rule',
           'bend_scale', 'describe']
