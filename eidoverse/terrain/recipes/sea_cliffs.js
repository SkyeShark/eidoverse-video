// Port of blender/eidoblend/terrain/recipes/sea_cliffs.py at f90c6fc.
//
// sea_cliffs: sea cliffs cut back into the land, a wave-cut platform at their foot, beaches in sheltered bays, stacks
// off strong headlands (design section 4.11 and row `sea_cliffs` of section 5). Judged against the Seven Sisters (chalk,
// 2 m lidar) and the Cliffs of Moher (layered shale and sandstone, 30 m radar).
//
//     const t = await makeTerrain({ recipe: 'sea_cliffs', seed: 3 });                               // chalk: the Seven Sisters
//     const t = await makeTerrain({ recipe: 'sea_cliffs', params: { rock: 'layered' } });             // shale and sandstone: Moher
//     const t = await makeTerrain({ recipe: 'sea_cliffs', params: { retreat_m: 500, azimuth_deg: 180 }, seaLevel: 0.0 });
//
// Stages, in order:
//   coast_land  the land the sea cuts into (coarsest level, every coarse-to-fine pass): an old surface sloping from the
//               uplands down past the original coastline (offset_m + retreat_m seaward of the tile centre, facing
//               azimuth_deg, bent into headlands and bays by headlands_m) to a base level kilometres out: the plain of
//               the low sea levels the land was carved under, drowned and planed since
//   fluvial     the fluvial backbone on the coarsest level, no uplift: the rivers cut into that surface from the distant
//               base level for age_myr, so the valleys run down its slope (chalk: the dry valleys between the 'sisters';
//               Moher: shallow streams on a plateau dipping inland) and the surface between them survives as broad
//               interfluves. The finer levels inherit the land (Catmull-Rom)
//   creep       hillslope's linear creep (kappa t) on the coarsest level: the valley sides and crests rounded
//               (coast_land runs on every level: on the finer ones down to the main level it refines the land with the
//               same backbone before the sea cuts it, REFINE, then rounds it by creep, refine_creep_m2; before, every
//               finer level's downland was the 23 m coarsest level's upsampled, blurred and printed with its grid)
//   coast       every level: exposure (16-direction fetch) and retreat from the original shore, the cliff at the
//               retreat line as high as the land there, the platform, talus apron, collapse scars with their debris, the
//               shingle beach, Dean beaches in bays, stacks (solvers/coast.js)
//   breakup     the detail package's rock breakup on the hero levels' cliff faces: buttresses, joints, scars (knob
//               `detail`)
//
// rock 'chalk' (the default) is the Seven Sisters: downland on a dip slope toward the sea, consequent dry valleys about
// 450 m apart cut 20-60 m into it, a near-straight cliff line at about 79 degrees whose top rises and falls across the
// valleys, its face stepped by the chalk's beds and flint bands and recessed by fresh collapse scars with their fallen
// blocks at the foot, a flint shingle beach (a 3.6 m crest, 25-60 m wide) and beyond it a 300 m platform just under the
// mid-tide sea, a few ledges awash. rock 'layered' is Moher: a flat plateau highest at the cliffs and dipping inland, an
// indented coast of coves and headlands with stacks, the face stepped by its beds (sandstone 82-85 degrees, siltstone and
// shale 55-60). A knob left at its default takes the rock's own value.
//
// Why no uplift (the steady-state regime of rolling_hills was tried first): with uplift balancing erosion the backbone
// dissects the whole surface into a uniform network of planar facets ("folded paper"), and at film quality the relief
// controller cut U to 0.2x and left the coastal land 20 m low. The real downs are an old tilted surface whose valleys
// were cut into it, with broad smooth interfluves left between them; the reference's steepest 1 % of ground is the
// narrow steep sides of those valleys. Start noise is kept below the regional slope (gradients of 1 % against 1.5-2 %),
// or undrained hollows survive the short run (6 % of the tile; filled with sediment they became large flat basins).
//
// The sea is makeTerrain's seaLevel (default 0 m here); the end stage's lake filling is off (defaults.lakes false), so
// the masks' `water` is the sea's depth.
//
// Where this differs from sea_cliffs.py, and why: chalk_palette(), layered_palette() and defaults_for build their dicts
// from build/palettes.py, the surfacing wave's module, whose port (build/palettes.js, PORT_PLAN.md 3.5, P14) is not in
// the checkout yet. Until it is, defaults.palette stays the palette's name, 'chalk_coast' (the value sea_cliffs.py's
// Recipe(...) itself is given before chalk_palette() replaces it), defaultsFor gives nothing for the layered rock, and
// toDict() differs from to_dict() in that one key; the three functions are transcribed and take the palettes module,
// so the recipe takes them as soon as build/palettes.js lands. _flint_column() is ported (numpy's default_rng(1907)
// through core/np_random.js). Nothing else differs: the stages, knobs and their apply are sea_cliffs.py's.

import { Knob, Recipe, Stage } from '../core/recipe.js';
import { defaultRng } from '../core/np_random.js';

// what each rock sets: the land stage, the fluvial stage, the creep and the coast stage (a knob the caller sets away
// from its default overrides its rock's value)
export const ROCKS = {
    chalk: {
        // (relief 140 m: with the downs refined, no longer blurred, 160 m stood their uplands at 213 m against the
        // reference's 167 and the cliff tops at 72 m against its 63)
        knobs: { relief_m: 140.0, valley_spacing_m: 450.0, azimuth_deg: 200.0, offset_m: 390.0, headlands_m: 120.0,
            irregularity: 0.06, stacks: 0.0, face_deg: 78.0 },
        // (the refined downland rounded by creep, 120 m^2: the refine alone left knife-edged crests and V notches; at
        // 300 m^2, a 24 m Gaussian on 5.9 m cells, it blurred the downs into a smooth upsampled field)
        land: { wiggle_scale_m: 2500.0, coast_frac: 0.65, rise_m: 3000.0, inland_gain: 0.25, tilt_m: 5000.0,
            texture: 0.08, refine_creep_m2: 120.0 },
        // the downs refined 3000 steps (225 kyr on the 5.9 m main level): the combes branching off the dry valleys,
        // crisp valley sides under rounded interfluves
        refine: { refine_steps: 3000 },
        fluvial: { K: 8e-6, age_myr: 0.4, threshold_deg: 32.0, roughness: 0.3 },
        creep: { kappa_t_m2: 200.0 },
        // chalk is uniform: weak zones only at kilometre scales. The face: the chalk's beds and flint bands (column
        // 'chalk'), dipping 1 degree east; its crenellation at 60 m and 25 m only; collapse scars with their fallen
        // blocks at the foot; a flint shingle beach (Birling Gap: a 3-4 m crest, 25-60 m wide), and beyond it the chalk
        // platform just under mid-tide water, a few ledges awash
        coast: { column: 'chalk', column_dip_deg: 1.0, column_dip_azimuth_deg: 90.0,
            weakness_scales_m: [1500.0, 600.0], crenel_m: 1.0, crenel_scales_m: [60.0, 25.0],
            talus_frac: 0.07, talus_max_m: 14.0, face_spread_deg: 4.0, shingle_m: 3.6, shingle_w_m: 45.0,
            shingle_berm: 0.35, shingle_var: 0.3, platform_top_m: -0.4, platform_rough_m: 0.2,
            platform_slope_deg: 0.4, scars: 0.45, beach_exposure: [0.25, 0.33] },
    },
    layered: {
        knobs: { relief_m: 165.0, valley_spacing_m: 600.0, azimuth_deg: 300.0, offset_m: 180.0, headlands_m: 350.0,
            irregularity: 0.45, stacks: 0.35, face_deg: 74.0 },
        // the cliff tops rise and fall along the coast (Moher's from about 30 m to 200 m at O'Brien's Tower): a broad
        // swell of the plateau, its gradients under the inland dip's
        land: { wiggle_scale_m: 1800.0, coast_frac: 0.95, rise_m: 300.0, inland_gain: -0.35, tilt_m: 3000.0,
            texture: 0.2, texture_scales_m: [8000.0, 5000.0] },
        // a flat moorland plateau (the reference: 84 % of the tile under 5 degrees): fewer, shallower valleys
        fluvial: { K: 5e-6, age_myr: 0.4, threshold_deg: 30.0, roughness: 0.3 },
        creep: { kappa_t_m2: 150.0 },
        // a few stacks off strong headlands, not a speckle of knobs along the whole coast; coves and headlands at
        // 300-900 m
        coast: { column: 'moher', column_dip_deg: 1.5, column_dip_azimuth_deg: 160.0,
            weakness_scales_m: [900.0, 300.0], crenel_m: 5.0, crenel_scales_m: [60.0, 20.0],
            stack_scale_m: 250.0, talus_frac: 0.05, talus_max_m: 10.0, face_spread_deg: 3.0, shingle_m: 1.6,
            platform_top_m: -0.5, beach_exposure: [0.25, 0.33] },
    },
};

// start noise below the regional slope (module doc): one kilometre-scale term
const LAND = { azimuth_deg: '$azimuth_deg', offset_m: '$offset_m', retreat_m: '$retreat_m', wiggle_m: '$headlands_m',
    U_m_per_yr: 0.0, start_m: 150.0, start_roughness: 0.04, start_scales_m: [3000.0],
    texture_scales_m: [6000.0, 3000.0] };

// the rivers cutting into the old surface (no uplift, so no relief controller: the start sets the heights)
const FLUVIAL = { K: 8e-6, valley_spacing_m: '$valley_spacing_m', threshold_deg: 32.0, threshold_noise: 0.1,
    threshold_scale_m: 400.0, roughness: 0.3, roughness_scales_m: [1500.0, 400.0], deposition: 0.3,
    age_myr: 0.4, relief_m: null, gullies: false, breakup: 0.0, outcrops: 0.0 };

const COAST = { retreat_m: '$retreat_m', weakness: '$irregularity', stacks: '$stacks', face_deg: '$face_deg' };

// the land's refinement on the finer levels, down to the main level (coast.refineLand): the backbone in refine mode
// (no uplift; the lock holds what the coarser level made), 600 steps (a rock's `refine` takes its own)
const REFINE = { refine_steps: 600, gullies: false };

/** The rock's preset, then every knob the caller set away from its (chalk) default. */
function apply(p) {
    const rock = ROCKS[p.rock];
    const knobs = p.recipe !== null && p.recipe !== undefined ? p.recipe.knobs : {};
    const val = (k) => {
        const v = p[k];
        if (k in rock.knobs && k in knobs && v === knobs[k].default) return rock.knobs[k];
        return v;
    };
    const land = p.stage('coast_land');
    Object.assign(land, structuredClone(rock.land));
    for (const [k, dst] of [['azimuth_deg', 'azimuth_deg'], ['offset_m', 'offset_m'], ['headlands_m', 'wiggle_m']]) {
        land[dst] = Number(val(k));
    }
    land.retreat_m = Number(p.retreat_m);
    land.start_m = Number(val('relief_m'));
    const fl = p.stage('fluvial');
    Object.assign(fl, structuredClone(rock.fluvial));
    fl.valley_spacing_m = Number(val('valley_spacing_m'));
    // the finer levels refine the land with the same backbone before the sea cuts it (coast.refineLand)
    land.refine = structuredClone({ ...fl, ...REFINE, ...(rock.refine ?? {}) });
    Object.assign(p.stage('creep'), structuredClone(rock.creep));
    const co = p.stage('coast');
    Object.assign(co, structuredClone(rock.coast));
    co.retreat_m = Number(p.retreat_m);
    co.weakness = Number(val('irregularity'));
    co.stacks = Number(val('stacks'));
    co.face_deg = Number(val('face_deg'));
    for (const s of p.stages('breakup')) s.enabled = Boolean(p.detail);
}

export const SEA_CLIFFS = new Recipe(
    'sea_cliffs', 'Sea cliffs: a cliffed coast with a wave-cut platform, beaches in bays and stacks (chalk or layered)',
    ['seven_sisters', 'cliffs_of_moher'],
    { size: 6000.0, resolution: 1024, context: 4, hero_cell: 0.5, palette: 'chalk_coast', base_elevation_m: 0.0,
        sea_level: 0.0, lakes: false },
    {
        rock: new Knob('chalk', 'choice', Object.keys(ROCKS),
            'chalk: the Seven Sisters (downland with dry valleys, a straight white face); layered: Moher (a ' +
            'plateau, an indented coast with stacks, a face stepped by its beds)', apply),
        relief_m: new Knob(140.0, 'm', [10.0, 1500.0],
            'the height of the old land surface the valleys cut into, its uplands above sea level ' +
            '(layered: 165)'),
        retreat_m: new Knob(300.0, 'm', [0.0, 5000.0],
            "how far an open straight coast has been cut back: the wave-cut platform's width"),
        valley_spacing_m: new Knob(450.0, 'm', [60.0, 5000.0],
            "the land's valleys (chalk: the dry valleys the cliff cuts across; layered: 600)"),
        azimuth_deg: new Knob(200.0, 'deg', [0.0, 360.0], 'the compass direction the coast faces, toward the sea ' +
            '(layered: 300)'),
        offset_m: new Knob(390.0, 'm', [-20000.0, 20000.0],
            "the cliff line's distance from the tile centre toward the sea (layered: 180)"),
        headlands_m: new Knob(120.0, 'm', [0.0, 5000.0],
            "the original coastline's headlands and bays, metres (std; layered: 350)"),
        irregularity: new Knob(0.06, '', [0.0, 1.5], 'rock weakness spread (ln std): coves where weak, headlands ' +
            'where strong (layered: 0.45)'),
        stacks: new Knob(0.0, '', [0.0, 1.0], 'strong knobs that stand as stacks when the retreat passes both sides ' +
            '(layered: 0.35)'),
        face_deg: new Knob(78.0, 'deg', [40.0, 89.0], "the cliff face's angle (chalk; the layered face follows its " +
            'beds)'),
        detail: new Knob(true, 'bool', null, "the detail package's rock breakup on the hero levels' faces"),
    },
    [
        new Stage('coast_land', LAND, 'all'),
        new Stage('fluvial', FLUVIAL, 'first'),
        new Stage('creep', { kappa_t_m2: 200.0 }, 'first'),
        new Stage('coast', COAST, 'all'),
        new Stage('breakup', { rock_slope_deg: [50.0, 62.0], threshold: 'field', max_fail_m: 1.5 }, 'hero'),
    ],
    'An old land surface (sloping to a base level kilometres out) cut by rivers without uplift, rounded by creep, ' +
    'then cut back by the sea: exposure x weakness sets the retreat; the cliff stands at the retreat line as ' +
    'high as the land, over a wave-cut platform, a talus apron and shingle; beaches in sheltered bays; stacks.');

/** The chalk face's bands for the material, by stratigraphic height (the coast stage's zs): white chalk beds 1.1-2.9 m
 * thick, each topped by a grey band of flint nodules (0.5 m), from 40 m below sea level to 260 m above it
 * (sea_cliffs.py _flint_column; numpy's default_rng(1907) draw for draw). */
export function flintColumn() {
    const rng = defaultRng(1907);
    const rows = [];
    let z = -40.0;
    while (z < 260.0) {
        const t = rng.uniform(1.1, 2.9);
        rows.push(['chalk', t, '#e4e0d6', 0.9, t, 0.02]);
        rows.push(['flint band', 0.5, '#a19d94', 0.75, 0.5, 0.04]);
        z += t + 0.5;
    }
    return { base_m: -40.0, formations: rows };
}

/** The chalk coast's material (sea_cliffs.py chalk_palette: its doc), from the palettes module P (build/palettes.js). */
export function chalkPalette(P) {
    const pal = P.get('chalk_coast');
    const keep = Object.fromEntries(pal.layers.map((L) => [L.name, L]));
    const down = { ...keep.downland };
    // the turf by the ground's own shape: grazed fields (600 m), the dry valleys' south-facing sides drier and yellower
    // (aspect), the valley floors lusher (flow), over the palette's 150 m and 9 m patches
    down.patches = [{ scale_m: 600.0, colour: '#7f8a4c', amount: 0.45, detail: 2.0, lo: 0.45, hi: 0.62 },
        { scale_m: null, colour: '#8e8c55', amount: 0.4, where: 'smoothstep(0.1, -0.7, northness) * smoothstep(3, 12, slope)' },
        { scale_m: null, colour: '#5d7536', amount: 0.35, where: 'smoothstep(0.55, 0.8, flow + 0.1*(fbm(40, 5) - 0.5))' },
        ...(down.patches ?? [])];
    const platform = { ...keep.platform, colour: '#666b52', projection: 'planar', normal: 0.8,
        patches: [{ scale_m: 10.0, colour: '#c6c1b1', amount: 0.55, lo: 0.52, hi: 0.7 }],
        weight: 'smoothstep(1.4, 0.5, height + 0.4*(fbm(18, 3) - 0.5)) * (1 - smoothstep(0.15, 0.5, deposit + talus))' };
    // (flint shingle is dark grey-brown under the white cliffs, Birling Gap's photograph)
    const shingle = { ...keep.shingle, colour: '#736d65',
        patches: [{ scale_m: null, tint: [0.72, 0.72, 0.74], amount: 1.0, where: 'smoothstep(0.9, 0.2, height + 0.3*(fbm(6, 1) - 0.5))' }],
        weight: 'smoothstep(0.12, 0.5, deposit) * smoothstep(6.5, 4.5, height) * (1 - smoothstep(0.6, 1.5, talus))' };
    const rubble = { name: 'chalk rubble', set: 'Gravel041', tile_m: 3.0, colour: '#d3cec1', roughness: 1.1,
        patches: [{ scale_m: 8.0, colour: '#bdb8ab', amount: 0.4 }],
        weight: 'smoothstep(0.3, 1.2, talus + 0.4*(fbm(15, 2) - 0.5)) * smoothstep(52, 40, slope)' };
    const chalk = { ...keep.chalk, edge_noise: 0.1, strata: 0.75, streaks: [2.5, 0.22, 0.5, 0.72],
        // fresh white in the scars' recesses (concave), the weathered face a little greyer, and the splash zone's
        // grey-green stain on the lowest metres
        patches: [{ scale_m: null, colour: '#f1eee6', amount: 0.7, where: 'smoothstep(0.25, 0.7, concave_20m + 0.3*(fbm(14, 2) - 0.5))' },
            { scale_m: null, tint: [0.82, 0.88, 0.78], amount: 0.5, where: 'smoothstep(4.0, 1.5, height + 1.5*(fbm(9, 3) - 0.5))' }],
        // the face by slope, its threshold low (40-52 degrees), the talus taking it only where the debris lies at its
        // repose, and every face over 58-66 degrees chalk whatever lies on it
        weight: 'max(smoothstep(40, 52, slope + 6*(fbm(40, 1) - 0.5) + 3*(fbm(10, 0) - 0.5) + 4*concave_20m) ' +
            '* (1 - smoothstep(0.8, 2.0, talus) * smoothstep(50, 40, slope)), smoothstep(58, 66, slope))' };
    const out = { ...pal, layers: [down, platform, shingle, rubble, chalk],
        title: pal.title + ' (sea_cliffs: layers from the coast fields, flint bands, chalk rubble)' };
    out.options = { ...pal.options, tone: '0.05*convex_20m - 0.07*concave_20m' };
    out.strata = { column: flintColumn(), source: 'attribute' };
    if (out.dressing !== null && typeof out.dressing === 'object' && !Array.isArray(out.dressing)) {
        out.dressing = { ...out.dressing, density: '1.2*smoothstep(0.3, 2.5, talus) + 1.0*rock_toe*smoothstep(6, 1, height) + 0.02' };
    }
    delete out.name;
    return out;
}

/** Moher's material (sea_cliffs.py layered_palette: its doc), from the palettes module P. */
export function layeredPalette(P) {
    const pal = P.get('alpine');
    const keep = Object.fromEntries(pal.layers.map((L) => [L.name, L]));
    const layers = [keep.pasture, keep.scree, keep.rock];
    layers[0] = { ...layers[0], colour: '#5c7834' };
    layers[1] = { ...layers[1], colour: '#6c6961',
        weight: 'max(smoothstep(0.2, 1.5, talus), smoothstep(0.25, 0.6, rock_toe), smoothstep(3.0, 1.0, height) * smoothstep(14, 6, slope))' };
    layers[2] = { ...layers[2], colour: '#57534b', streaks: [4.0, 0.5], weight: 'smoothstep(38, 52, slope + 6*(noise(40) - 0.5))' };
    const out = { title: "Moher's coast: dark grey-brown shale and sandstone walls with water streaks, boulders at the " +
        'foot, pasture on the plateau', layers, options: pal.options, dressing: { ...pal.dressing, colour: '#5d5a54' } };
    delete out.name;
    return out;
}

// the surfacing wave's palettes module, when it is in the checkout (see the header)
let Pal = null;
try {
    Deno.statSync(new URL('../build/palettes.js', import.meta.url));
    Pal = await import(new URL('../build/palettes.js', import.meta.url).href);
} catch (_e) { /* not ported yet: the palette's name stands */ }

/** The palette by rock: the chalk palette for chalk (also the recipe's static default), Moher's for the layered rock
 * (sea_cliffs.py defaults_for); nothing until the palettes module is in the checkout. */
export function defaultsFor(values) {
    return values.rock === 'layered' && Pal ? { palette: layeredPalette(Pal) } : {};
}

if (Pal) SEA_CLIFFS.defaults.palette = chalkPalette(Pal);
SEA_CLIFFS.defaultsFor = defaultsFor;
SEA_CLIFFS.defaults_for = defaultsFor;

export const RECIPES = [SEA_CLIFFS];
export { flintColumn as _flint_column, chalkPalette as chalk_palette, layeredPalette as layered_palette, defaultsFor as defaults_for };
