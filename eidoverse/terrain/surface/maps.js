// Port of blender/eidoblend/terrain/surface/maps.py at d67f19e.
//
// The surface data's map registry (SURFACING_DESIGN.md 2.2): every map the bake makes, what it means, which image
// family holds it and how it is stored there. Data, JSON-equal to maps.py (tests/surface_data/maps_test.mjs).
//
//     import * as MP from './surface/maps.js';
//     MP.MAPS.settle                    // MapSpec { name, unit, family, encoding, made_by, doc, channel, grid, ... }
//     MP.spec('convex_200m')            // a scaled curvature resolves by its suffix, as masks.parseName does
//     MP.FAMILIES.E                     // the family's format, colour space and fixed channels
//     MP.decodeRule(spec, cells, refs)  // ['affine', a, b] | ['square', a, 0] | ['z_plus', 1, b]: what a shader does
//     MP.encode1(spec, v, cell)         // one physical value -> what the image holds (a per-query helper)
//     MP.decode1(spec, v, cell)         // and back
//
// Families (each one data texture per level in this edition: surface/layers.js):
//     D   RGBA16F, linear   the field normal's x and y, the sub-cell relief's gradient gx and gy      (detail grid)
//     E   RGBA8, linear     crease (signed), cavity, crest_fine (signed), grain                       (detail grid)
//     M   RGBA8, linear     four maps to an image (M0, M1, ...), packed when a material asks for them (cell grid)
//     F   RGBA16F, linear   metres: strata and src_strata, each less the pixel's own height and a per-level reference
//     C   RGBA8, sRGB       the far albedo, the far roughness in the linear alpha                      (palette bake)
//     P   RGBA8, sRGB       the colour sediment carries, the sediment share in the alpha               (palette bake)
// 'shader' maps are never stored: the material derives them (slope, aspect, northness and eastness from D's field
// normal; height from the object z; insolation from the field normal and the sun). SurfaceData.maps() still returns
// them, computed with the same definitions, so a rule written in the mask language reads one vocabulary everywhere.
//
// Encodings:
//     'unit'    0..1 as it is
//     'signed'  -1..1 as 0.5 + 0.5 v
//     'bend'    a curvature kappa (1/m) as its dimensionless bend kappa x scale, clamped to +-1 and stored signed; the
//               scale is the map's (20 m for *_20m) or 2 x the level's cell for the unsuffixed ones, so their decode
//               differs per level
//     'thick'   a thickness in metres as sqrt(t / t_max): at 1 m with t_max 64 the 8-bit step is 6 cm
//     'float'   the value itself (the half-float families)
//     'z'       metres relative to the pixel's own height and a per-level reference: value = z + reference + texel
//     'srgb'    a colour, sRGB-encoded in the image, linear in the arrays
//
// Where this differs from maps.py, and why:
//   - encode() and decode() of whole arrays are kernels in this edition (surface/kernels/port/encode.wgsl and
//     decode.wgsl, run by surface/bake.js and surface/index.js: per-texel work is GPU compute). encode1 / decode1 are
//     maps.py's arithmetic on one float32 value (Math.fround at every step, as numpy's float32), for per-query reads
//     (SurfaceData.at) and the tests.
//   - spec() raises KeyError naming the nearest names (core/levels.js closeMatches, difflib's rule).

import { KeyError, ValueError, closeMatches, pyReprValue } from '../core/levels.js';

const f32 = Math.fround;

/** One map's registry entry (maps.py MapSpec). */
export class MapSpec {
    constructor(name, unit, family, encoding, madeBy, doc, opts = {}) {
        this.name = name;
        this.unit = unit;                                // '0-1', '-1..1', 'm', '1/m', 'deg', 'rgb'
        this.family = family;                            // 'D' | 'E' | 'M' | 'F' | 'C' | 'P' | 'shader'
        this.encoding = encoding;                        // see the module doc
        this.made_by = madeBy;                           // 'masks' (masks.py), a bake pass, 'plants' or 'shader'
        this.doc = doc;
        this.channel = opts.channel ?? null;             // the fixed channel (or channels) in D, E, F, C, P; null in M
        this.grid = opts.grid ?? 'cell';                 // 'cell' | 'detail'
        this.t_max = opts.t_max ?? 64.0;                 // 'thick': metres stored as 1
        this.scale_m = opts.scale_m ?? null;             // 'bend': the curvature's scale in metres; null = 2 x the cell
        this.pair = opts.pair ?? null;                   // the other channel of a two-channel map (n20_x <-> n20_y)
        Object.freeze(this);
    }

    /** dataclasses.asdict(): the fields in maps.py's order. */
    toDict() {
        return { name: this.name, unit: this.unit, family: this.family, encoding: this.encoding, made_by: this.made_by,
            doc: this.doc, channel: Array.isArray(this.channel) ? [...this.channel] : this.channel, grid: this.grid,
            t_max: this.t_max, scale_m: this.scale_m, pair: this.pair };
    }

    /** dataclasses.replace(): a copy with some fields changed. */
    replace(changes) {
        const d = { ...this.toDict(), ...changes };
        return new MapSpec(d.name, d.unit, d.family, d.encoding, d.made_by, d.doc, d);
    }
}

// family -> (format, colour space, grid, fixed channel names or null)
export const FAMILIES = Object.freeze({
    D: Object.freeze({ format: 'RGBA16F', colorspace: 'Non-Color', grid: 'detail', is_float: true,
        channels: Object.freeze(['normal_x', 'normal_y', 'detail_gx', 'detail_gy']) }),
    E: Object.freeze({ format: 'RGBA8', colorspace: 'Non-Color', grid: 'detail', is_float: false,
        channels: Object.freeze(['crease', 'cavity', 'crest_fine', 'grain']) }),
    M: Object.freeze({ format: 'RGBA8', colorspace: 'Non-Color', grid: 'cell', is_float: false, channels: null }),
    F: Object.freeze({ format: 'RGBA16F', colorspace: 'Non-Color', grid: 'cell', is_float: true,
        channels: Object.freeze(['strata', 'src_strata', null, null]) }),
    C: Object.freeze({ format: 'RGBA8', colorspace: 'sRGB', grid: 'cell', is_float: false,
        channels: Object.freeze(['far_colour', 'far_colour', 'far_colour', 'far_roughness']) }),
    P: Object.freeze({ format: 'RGBA8', colorspace: 'sRGB', grid: 'cell', is_float: false,
        channels: Object.freeze(['down_colour', 'down_colour', 'down_colour', 'down_share']) }),
});

const M_ = (name, unit, enc, by, doc, opts = {}) => new MapSpec(name, unit, 'M', enc, by, doc, opts);

const SPECS = [
    // ---- D and E: the detail grid
    new MapSpec('normal_x', '-1..1', 'D', 'float', 'field_normal',
        "the field normal's x: N = normalize(-dh/dx, -dh/dy, 1) of the level's height at D's texel (the mesh's " +
        'Catmull-Rom surface, central differences at the texel spacing); z is rebuilt', { channel: 0, grid: 'detail' }),
    new MapSpec('normal_y', '-1..1', 'D', 'float', 'field_normal', "the field normal's y", { channel: 1, grid: 'detail' }),
    new MapSpec('detail_gx', 'm/m', 'D', 'float', 'phacelle',
        'd/dx of the relief below the cell (metres of height per metre): flow-steered gullies on soil slopes, a ' +
        "spectrum from the terrain's top octave down to two texels, varied in spacing and depth, none on sand, " +
        "buried by the snowpack (info['relief_octaves'] lists each level's); rock ribs from the breakup strength " +
        "on bare rock. The material adds it to the field's own gradient",
        { channel: 2, grid: 'detail' }),
    new MapSpec('detail_gy', 'm/m', 'D', 'float', 'phacelle', 'd/dy of the relief below the cell', { channel: 3,
        grid: 'detail' }),
    new MapSpec('crease', '-1..1', 'E', 'signed', 'phacelle',
        "the sub-cell relief's curvature, normalised: gully floors and rock joints -, crests and ribs +",
        { channel: 0, grid: 'detail' }),
    new MapSpec('cavity', '0-1', 'E', 'unit', 'cavity',
        'short-radius sky view (2-32 texels of D, over the height plus the sub-cell relief): 1 open, low in ' +
        'creases and at wall feet', { channel: 1, grid: 'detail' }),
    new MapSpec('crest_fine', '-1..1', 'E', 'signed', 'blur',
        "each level's own finest convexity: the mean of the crest term at 1 and 2 texels of D, on the surface the " +
        'cavity march reads (the height plus the sub-cell relief): + on the finest crests, rims and sub-cell ' +
        'ribs, - in the finest creases and rills. Its meaning changes with the level by design: read it only for ' +
        'tone, faded with the footprint', { channel: 2, grid: 'detail' }),
    new MapSpec('grain', '0-1', 'E', 'unit', 'carry_src',
        'distance down the fall path from the bare rock above, over the reach (300 m): 0 at the apex of a talus ' +
        '(fine debris), 1 at its toe and beyond (boulders); 1 where no rock stands above. The fall paths are ' +
        'drawn among the upslope neighbours by slope, so they follow the fall line (cell grid, upsampled)',
        { channel: 3, grid: 'detail' }),
    // ---- F: metres
    new MapSpec('strata', 'm', 'F', 'z', 'masks',
        'stratigraphic height zs (the strata mask, or the height itself on a terrain without one): the material ' +
        'reads its rock column at it', { channel: 0 }),
    new MapSpec('src_strata', 'm', 'F', 'z', 'carry_src',
        "the stratigraphic height of the bare rock a debris cell's material came from (its fall path up to " +
        'exposed rock, within 300 m, drawn among the upslope neighbours by slope); the cell\'s own zs on bare ' +
        'rock and where no rock stands above', { channel: 1 }),
    // ---- C and P: the palette bake
    new MapSpec('far_colour', 'rgb', 'C', 'srgb', 'far_colour',
        "the palette's ground colour per texel (every layer at its scan's mean, composited by coverage): the " +
        "ground's colour at a distance and the context rings' whole material", { channel: [0, 1, 2] }),
    new MapSpec('far_roughness', '0-1', 'C', 'unit', 'far_colour', 'the roughness that goes with the far colour',
        { channel: 3 }),
    new MapSpec('down_colour', 'rgb', 'P', 'srgb', 'route_colour',
        'the colour of the sediment a cell carries: the bare rock colours upstream, weighted by where the ground ' +
        'is eroding, routed down the drainage', { channel: [0, 1, 2] }),
    new MapSpec('down_share', '0-1', 'P', 'unit', 'route_colour',
        'how much of the ground is carried sediment: q / (q + q0) of the routed production', { channel: 3 }),
    // ---- M: the existing masks (masks.py), name, unit and meaning unchanged
    M_('height_norm', '0-1', 'unit', 'masks', 'height normalised over the main tile'),
    M_('curv_profile', '1/m', 'bend', 'masks', 'profile curvature at 2 x the level cell (+ convex)'),
    M_('curv_plan', '1/m', 'bend', 'masks', 'plan curvature at 2 x the level cell (+ ridges and spurs)'),
    M_('convex', '0-1', 'unit', 'masks', 'convex ground at 2 x the level cell'),
    M_('concave', '0-1', 'unit', 'masks', 'concave ground at 2 x the level cell'),
    M_('curv_profile_20m', '1/m', 'bend', 'masks', 'profile curvature at 20 m', { scale_m: 20.0 }),
    M_('curv_plan_20m', '1/m', 'bend', 'masks', 'plan curvature at 20 m', { scale_m: 20.0 }),
    M_('convex_20m', '0-1', 'unit', 'masks', 'convex ground at 20 m'),
    M_('concave_20m', '0-1', 'unit', 'masks', 'concave ground at 20 m'),
    M_('peaks', '0-1', 'unit', 'masks', 'high and convex: summits and ridgelines'),
    M_('flow', '0-1', 'unit', 'masks+route',
        'log10 of the drainage area per metre of contour, normalised over the main tile; on hero levels from the ' +
        "bake's own routing (the parent's catchment pinned in across the border)"),
    M_('channels', '0-1', 'unit', 'masks+route', 'drainage area above the level threshold (hero levels: re-routed)'),
    M_('wetness', '0-1', 'unit', 'masks+route',
        'topographic wetness ln(a / tan slope) normalised over the main tile; 1 on water (hero levels: re-routed)'),
    M_('wear', 'm', 'thick', 'masks', 'eroded depth', { t_max: 256.0 }),
    M_('deposit', 'm', 'thick', 'masks', 'sediment thickness'),
    M_('talus', 'm', 'thick', 'masks', 'talus thickness'),
    M_('sand', 'm', 'thick', 'masks', 'sand thickness'),
    M_('lava', 'as written', 'thick', 'masks', 'lava-flow footprint as the volcanic solver writes it', { t_max: 4.0 }),
    M_('water', 'm', 'thick', 'masks', 'lake or sea depth'),
    M_('rock', '0-1', 'unit', 'masks', "the masks package's exposed rock (steep, or deeply worn under thin cover)"),
    M_('rock_toe', '0-1', 'unit', 'masks', 'the ground below exposed rock where fallen rock gathers'),
    M_('snow', '0-1', 'unit', 'masks', "the masks package's snow rule (altitude, aspect, hollows)"),
    M_('occlusion', '0-1', 'unit', 'masks', 'sky-view factor within 500 m: 1 open sky'),
    M_('vegetation', '0-1', 'unit', 'masks', "the masks package's plant suitability"),
    // ---- M: the new maps
    M_('crest', '-1..1', 'signed', 'blur',
        'multi-scale convexity at fixed metre scales: the mean of tanh((h - G h) / (tau sigma)) over sigma = 8, 16, ' +
        '32, 64, 128 m (those of at least one cell; a scale over 16 cells comes from the parent\'s pass), so a ' +
        'threshold on it means the same in a hero window and on the main level: + crests, rims, ribs, spurs; - ' +
        'creases, chutes, hollows. On gentle ground -crest is the soil-gathering term'),
    M_('settle', '0-1', 'unit', 'relax',
        'where a thin loose layer comes to rest: a 0.5 m layer relaxed at a 20-degree repose for 60 passes, fresh on ' +
        "every level (plus what the parent gathered beyond it, so the feet of long slopes stay gathered); 0 shed, " +
        '0.5 unmoved (flat ground), 1 a metre or more gathered (benches, ledges, crevices, slope feet)'),
    M_('snowpack', 'm', 'thick', 'relax',
        'snow thickness: snowfall by altitude and aspect, slid off at 38 degrees and gathered below, melted by ' +
        'insolation and under the snowline; or the pack that flowed down the drainage lines at 14 degrees, whichever ' +
        'is thicker (a fresh fall on every level, plus what the parent gathered beyond its fall)', { t_max: 16.0 }),
    M_('fresh', '0-1', 'unit', 'spi',
        'actively eroding ground: on ground under 30 degrees (faded over 25-35) stream power on ground bare of loose ' +
        "cover (scoured channel floors); on steeper ground only the slope over the rock's own threshold Sc (failing " +
        'faces), never stream power (it peaks at the pour-overs, where the varnish curtains hang); both on the 20 m ' +
        "slope. Water and basins deeper than the fill's cap end their flow, so no flat reads as scoured"),
    M_('spi', '0-1', 'unit', 'spi',
        'stream power log10(a tan S), a the specific catchment and S the slope at 20 m (the same on every level), ' +
        "normalised by the main tile's 5th-95th percentiles"),
    M_('valley', '0-1', 'unit', 'blur',
        'flat and low at 12 m and wider (an MRVBF-like index on the blur pyramid, the wider scales from the coarser ' +
        'levels): valley floors, fans, basins; about 0.5 on an open plain'),
    M_('streak', '0-1', 'unit', 'streak',
        "wind exposure on convex ground, trailed ten cells downwind along the palette's wind"),
    M_('n20_x', '-1..1', 'signed', 'blur', "the 20 m normal's x (the height blurred at 20 m): with n20_y the " +
        'azimuth and dip of a steep face, which do not twist on small bumps; z is rebuilt', { pair: 'n20_y' }),
    M_('n20_y', '-1..1', 'signed', 'blur', "the 20 m normal's y", { pair: 'n20_x' }),
    // ---- M: the plant layer's rasters (bake_surface(extra=...))
    M_('canopy', '0-1', 'unit', 'plants', "the placed crowns' cover, a fraction per texel"),
    M_('canopy_expected', '0-1', 'unit', 'plants',
        "the cover the ecotope's tree density implies, on every level whenever the palette has a canopy layer"),
    M_('canopy_far', '0-1', 'unit', 'plants', 'the part of canopy_expected the instances leave to the material'),
    M_('shrubs', '0-1', 'unit', 'plants', 'undergrowth density'),
    M_('shrubs_far', '0-1', 'unit', 'plants', 'the part of the undergrowth the instances leave to the material'),
    // ---- derived in the shader, never stored
    new MapSpec('slope', 'deg', 'shader', 'none', 'shader', "slope, from D's field normal: acos(N.z)"),
    new MapSpec('aspect', 'deg', 'shader', 'none', 'shader', 'compass bearing the slope faces (0 north, 90 east)'),
    new MapSpec('northness', '-1..1', 'shader', 'none', 'shader', 'cos(aspect), faded to 0 on ground under 3 degrees'),
    new MapSpec('eastness', '-1..1', 'shader', 'none', 'shader', 'sin(aspect), faded to 0 on ground under 3 degrees'),
    new MapSpec('height', 'm', 'shader', 'none', 'shader', 'the object z: the level height at every pixel of the mesh'),
    new MapSpec('slope_20m', 'deg', 'shader', 'none', 'shader',
        'the slope of the 20 m normal (n20): a slope that means the same on every level, for rules that must not ' +
        'step at a window edge'),
    new MapSpec('insolation', '0-1', 'shader', 'none', 'shader',
        "max(0, N_field . s), s the place's climatological sun (palettes.climate_sun from latitude_deg, or the " +
        'terrain constants sun_azimuth_deg and sun_elevation_deg where a palette sets them)'),
];

/** The registry: { name: MapSpec }, in maps.py's order. */
export const MAPS = Object.freeze(Object.fromEntries(SPECS.map((s) => [s.name, s])));

// a two-channel map by one name: SurfaceData.channel('n20') returns both channels
export const PAIRS = Object.freeze({ n20: Object.freeze(['n20_x', 'n20_y']), normal: Object.freeze(['normal_x', 'normal_y']),
    detail_g: Object.freeze(['detail_gx', 'detail_gy']) });
export const SHADER = Object.freeze(SPECS.filter((s) => s.family === 'shader').map((s) => s.name));
const SCALED = /^(curv_profile|curv_plan|convex|concave)_(\d+(?:p\d+)?)m$/;

/** The MapSpec of a map name; a scaled curvature (convex_200m, curv_plan_50m) resolves by its suffix. Throws
 * KeyError naming the nearest names. */
export function spec(name) {
    const s = MAPS[name];
    if (s !== undefined) return s;
    const m = SCALED.exec(name);
    if (m) {
        const base = MAPS[m[1]];
        return base.replace({ name, scale_m: parseFloat(m[2].replace('p', '.')),
            doc: base.doc.replaceAll('2 x the level cell', `${m[2]} m`) });
    }
    const near = closeMatches(String(name), [...Object.keys(MAPS), ...Object.keys(PAIRS)], 4, 0.4);
    throw new KeyError(`no surface map ${pyReprValue(name)}` + (near.length ? `; nearest: ${near.join(', ')}` : ''));
}

/** True when `name` is a surface map (a registry name, a pair name or a scaled curvature). */
export function known(name) {
    if (name in PAIRS) return true;
    try {
        spec(name);
        return true;
    } catch (_e) {
        return false;
    }
}

/** The scale in metres a 'bend' map's curvature is multiplied by on a level of `cell` metres. */
export function bendScale(s, cell) {
    return s.scale_m !== null ? Number(s.scale_m) : 2.0 * Number(cell);
}

/** One physical value -> what the map's image holds (maps.py encode on one float32 value): 0..1 for the 8-bit
 * encodings, the value itself for 'float'. ('z' and 'srgb' maps are encoded by the bake and the layers: they need
 * the height and the transfer curve.) */
export function encode1(s, v, cell = 1.0) {
    const a = f32(v), e = s.encoding;
    const clip = (x, lo, hi) => Math.min(Math.max(x, lo), hi);
    if (e === 'unit') return clip(a, 0.0, 1.0);
    if (e === 'signed') return f32(f32(clip(a, -1.0, 1.0) * 0.5) + 0.5);
    if (e === 'bend') return f32(f32(clip(f32(a * f32(bendScale(s, cell))), -1.0, 1.0) * 0.5) + 0.5);
    if (e === 'thick') return f32(Math.sqrt(f32(clip(a, 0.0, s.t_max) * f32(1.0 / s.t_max))));
    if (e === 'float') return a;
    throw new ValueError(`map ${pyReprValue(s.name)}: encoding ${pyReprValue(e)} is not encoded per map`);
}

/** What the image holds -> one physical value (the inverse of encode1, up to its clamps). */
export function decode1(s, v, cell = 1.0) {
    const [kind, a0, b0] = decodeRule(s, [cell]);
    const a = Array.isArray(a0) ? a0[0] : a0, b = Array.isArray(b0) ? b0[0] : b0;
    const x = f32(v);
    if (kind === 'square') return f32(f32(x * x) * f32(a));
    return f32(f32(x * f32(a)) + f32(b));
}

/** How a shader turns the map's texel into its value: [kind, a, b] (maps.py decode_rule).
 *      ['affine', a, b]    value = a * texel + b
 *      ['square', a, 0.0]  value = a * texel * texel                       (thicknesses)
 *      ['z_plus', 1.0, b]  value = object z + b + texel                    (F: b the level's reference, metres)
 * a and b are numbers, or arrays with one number per level when they differ by level (the unsuffixed curvatures,
 * whose scale is 2 x the level's cell; F's references): the material folds those in with the level's other
 * constants. cells: every level's cell; refs: every level's reference (F). */
export function decodeRule(s, cells = null, refs = null) {
    const e = s.encoding;
    if (e === 'unit' || e === 'float' || e === 'srgb') return ['affine', 1.0, 0.0];
    if (e === 'signed') return ['affine', 2.0, -1.0];
    if (e === 'thick') return ['square', Number(s.t_max), 0.0];
    if (e === 'bend') {
        if (s.scale_m !== null) return ['affine', 2.0 / Number(s.scale_m), -1.0 / Number(s.scale_m)];
        const cs = (cells ?? [1.0]).map(Number);
        return ['affine', cs.map((c) => 2.0 / (2.0 * c)), cs.map((c) => -1.0 / (2.0 * c))];
    }
    if (e === 'z') return ['z_plus', 1.0, (refs ?? [0.0]).map(Number)];
    throw new ValueError(`map ${pyReprValue(s.name)} (${e}) is not stored in an image`);
}

/** One line per map: name, family, unit, how it is made, meaning. */
export function describe() {
    const pad = (v, n) => String(v).padEnd(n);              // Python's '{:16s}'
    return SPECS.map((s) => `${pad(s.name, 16)} ${pad(s.family, 6)} ${pad(s.unit, 10)} ${pad(s.made_by, 13)} ${s.doc}`).join('\n');
}

export { decodeRule as decode_rule, bendScale as bend_scale };
