// Port of blender/eidoblend/terrain/recipes/canyon.py at f90c6fc.
//
// canyon: a canyon cut into layered plateau rock (design section 5), judged against the Grand Canyon at Toroweap.
//
//     const t = await makeTerrain({ recipe: 'canyon', params: { depth_m: 1400, flow_azimuth_deg: 235 }, focus: [300, 900] });
//
// The stages (solvers/strata.js, solvers/rivers.js):
//   strata          the stratigraphic column in world z (the Grand Canyon's Paleozoic section by default, as members
//                   20-180 m thick), dipping dip_deg, warped a little, and sagging sag_m toward the river (a syncline
//                   along the canyon, so the plateau drains into it)
//   plateau         the start: the plateau's structural surface at depth_m above the river's final bed, following the
//                   beds, roughened
//   river_path      the river's course across every level (a smoothed random walk flowing toward flow_azimuth_deg)
//   strata_fluvial  the river cuts down from the plateau to its final bed (the base-level fall), its tributaries cut
//                   side canyons back into the benches and the plateau, every wall stands at its layer's own angle
//                   (the composite threshold; the rock mass's strength varies, rock_variety), and the walls retreat
//                   by weathering, leaving the strong beds as benches; the debris rests at repose as talus aprons
//   breakup         joint-guided rock breakup on the hero levels (the detail package): buttresses, chutes and talus
//
// Heights: z = 0 is the river's final bed at the tile centre; base_elevation_m (505 m, Toroweap's river) places it.
//
// The recipe is data: the same stages, knobs and parameters as the Blender recipe (toDict() is to_dict()'s JSON, but
// for defaults.palette until build/palettes.js lands: solvers/strata.js paletteFor); the knob functions are
// transcribed. The comments on the parameters are the Blender file's.

import { Knob, Recipe, Stage } from '../core/recipe.js';
import * as S from '../solvers/strata.js';

/** The plateau's structural surface: depth_m above the river's final bed, in the column's height. */
function surface(p) {
    p.stage('plateau').surface_zs_m = Number(p.river_zs_m) + Number(p.depth_m);
}

/** The base-level fall in two stages, as the Grand Canyon's history: the river cuts quickly to the top of the bench
 * layer and holds there while the upper walls retreat across the bench (most of the run), then cuts the inner gorge
 * late, so its walls stay near their own angles. bench_layer null: one steady fall. */
function fall(p) {
    const g = Math.min(Math.max(Number(p.inner_gorge_frac), 0.05), 0.9);
    const depth = Number(p.depth_m);
    let sch;
    if (p.bench_layer && depth > 0) {
        const col = S.column(p.column);
        const hb = col.topOf(p.bench_layer) - Number(p.river_zs_m);       // the bench's top above the final bed
        const fb = Math.min(Math.max((depth - hb) / depth, 0.0), 1.0);
        sch = [[0.0, 0.0], [0.15, fb], [1.0 - g, fb], [1.0 - 0.3 * g, 1.0], [1.0, 1.0]];
    } else {
        sch = [[0.0, 0.0], [1.0 - g, 1.0], [1.0, 1.0]];
    }
    p.stage('river_path').schedule = sch;
}

function detail(p) {
    for (const s of p.stages('breakup')) s.enabled = Boolean(p.detail);
}

// the beds sag gently toward the river (a syncline along the canyon, rise_m at half_width_m from its axis): the
// plateau and the benches drain into the canyon from both sides, so tributaries cut side canyons back into them.
// The beds undulate 5 m over 4 km, and a metre or so over 80-250 m, which the stripped benches follow
const STRATA = { column: '$column', zs0_m: '$river_zs_m', dip_deg: '$dip_deg', azimuth_deg: '$dip_azimuth_deg',
    warp: [[4000.0, 5.0], [900.0, 3.0], [250.0, 1.2], [80.0, 0.4]],
    fold: { axis_deg: '$flow_azimuth_deg', through: [0.0, 0.0], rise_m: '$sag_m', half_width_m: 6000.0 } };
const PLATEAU = { surface_zs_m: 1765.0, roughness: [[3000.0, 6.0], [600.0, 2.5], [120.0, 0.8]] };
// pool and drop (rivers.js River.poolScour): pools about 600 m apart, scoured 6 m, parted by short riffles, each a
// closed basin the end stage fills with flat water (defaults.lakes 'lake')
const RIVER = { kind: 'walk', through: [0.0, 0.0], flow_azimuth_deg: '$flow_azimuth_deg', wiggle_deg: 16.0,
    wiggle_wavelength_m: 5000.0, width_m: '$river_width_m', bed_m: 0.0, gradient: 0.0015,
    schedule: [[0.0, 0.0], [0.6, 1.0], [1.0, 1.0]], pool_spacing_m: 600.0, pool_depth_m: 6.0, pool_riffle: 0.06 };
// K 1.5e-6: an arid plateau's; the rock mass varies (strata.rockMass, 35 m to 600 m); the debris washes off at 0.15 x
// the rock's rate; dry_basins: every closed basin off the river fills with sand and alluvium; cliff rock wears by
// failing over its undercut base (weather_k_exp 2); the beds' facies change along the walls (350 m along, 45 m up)
const FLUVIAL = { K: 1.5e-6, valley_spacing_m: '$valley_spacing_m', roughness: 0.4, roughness_scales_m: [2500.0, 500.0, 90.0],
    deposition: 0.1, age_myr: '$age_myr', repose_deg: 34.0, later: 'refine', weather_m_per_yr: '$weathering_m_per_yr',
    weather_area: '$side_canyons', weather_loose: 0.15, resist_scales_m: [600.0, 240.0, 90.0, 35.0], dry_basins: true,
    weather_k_exp: 2.0, facies: { strength: 0.5, scale_m: 350.0, scale_z_m: 45.0, weather: 0.6 } };

/** The rock mass's variety: mostly in the angle a wall stands at (the composite threshold's run), a little in how fast
 * it wears. */
function rock(p) {
    const f = p.stage('strata_fluvial');
    f.resist_run = Number(p.rock_variety);
    f.resist = 0.35 * Number(p.rock_variety);
}

export const CANYON = new Recipe(
    'canyon', 'A canyon in layered plateau rock: stepped cliffs and benches, tributaries, an inner gorge',
    ['grand_canyon_toroweap'],
    { size: 8000.0, context: 2, hero_cell: 0.5, base_elevation_m: 505.0, lakes: 'lake',
        palette: await S.paletteFor('desert_sandstone', 'colorado_plateau') },
    {
        depth_m: new Knob(1420.0, 'm', [100.0, 3000.0], "the plateau's surface above the river's final bed at the " +
            'tile centre (Toroweap: the Kaibab rim 1445 m over the river)', surface),
        river_zs_m: new Knob(360.0, 'm', [0.0, 3000.0], "where in the column the river's final bed sits (metres " +
            "above the column's base: 360 is 20 m into the Muav's lower " +
            "cliff, so the inner gorge's foot is cliff, not shale that " +
            'wears back into a wide flat floor)', surface),
        column: new Knob('colorado_plateau', 'choice', Object.keys(S.COLUMNS),
            'the stratigraphic column (solvers/strata.COLUMNS); the material bands follow the default ' +
            "column: with another, pass palette=strata.palette_for('desert_sandstone', column)"),
        dip_deg: new Knob(0.3, 'deg', [0.0, 10.0], "the beds' dip (the plateau surface follows them)"),
        dip_azimuth_deg: new Knob(60.0, 'deg', [0.0, 360.0], 'the direction the beds rise toward (counter-clockwise ' +
            'from +x)'),
        flow_azimuth_deg: new Knob(235.0, 'deg', [0.0, 360.0], "the river's down-valley direction, compass degrees"),
        river_width_m: new Knob(80.0, 'm', [10.0, 400.0], "the river's channel width"),
        valley_spacing_m: new Knob(500.0, 'm', [60.0, 5000.0], "the smallest side canyons' spacing on the main level"),
        weathering_m_per_yr: new Knob(2.2e-4, 'm/yr', [0.0, 3e-3], 'how fast rock of erodibility factor 1 on a ' +
            '30-degree slope wears down (every contour then ' +
            'retreats this / tan 30 degrees a year, the Hermit ' +
            "shale x3.5, cliff rock x0.2): the upper walls' " +
            'retreat over the benches; 0: they stand where ' +
            'the river left them (a V canyon)'),
        side_canyons: new Knob(0.15, '', [0.0, 3.0], 'how much faster the walls wear back where runoff gathers ' +
            '(x 1 + this sqrt(area / 10 ha)): amphitheatres and side ' +
            'canyons cut into the benches (0.35 cut amphitheatres all ' +
            "along the north rim; Toroweap's Esplanade is broad, with few)"),
        sag_m: new Knob(120.0, 'm', [0.0, 600.0], 'how much the beds rise 6 km either side of the river (a syncline ' +
            'along the canyon): the plateau drains into the canyon and ' +
            'tributaries cut side canyons into it; 0: the beds level across'),
        rock_variety: new Knob(0.3, '', [0.0, 1.5], "how much the rock mass's strength varies (35 m to 600 m): " +
            'strong spots stand as sheer buttresses, weak ones lie back as ' +
            'chutes over talus; 0: every layer one angle along the whole ' +
            'wall', rock),
        age_myr: new Knob(2.0, 'Myr', [0.2, 10.0], "the time the coarsest level runs: the cut and then the walls' " +
            'retreat'),
        bench_layer: new Knob(null, 'name', null, 'a layer whose top the river holds at for most of the run (the ' +
            '"Esplanade": a wide bench the upper walls retreat across and a ' +
            'young inner gorge cut late below it); None: one steady fall (the ' +
            'default: the two-stage cut left the inner gorge a straight ' +
            'polygonal slot with planar walls and the bench too wide)', fall),
        inner_gorge_frac: new Knob(0.4, '', [0.05, 0.9], "two-stage: the share of the run left when the inner " +
            "gorge's cut begins (it takes 70 % of that; then the bed " +
            'holds); one steady fall: the share the bed holds at the end', fall),
        detail: new Knob(true, 'bool', null, 'rock breakup on the hero levels', detail),
    },
    [
        new Stage('strata', STRATA, 'all'),
        new Stage('plateau', PLATEAU, 'all'),
        new Stage('river_path', RIVER, 'all'),
        new Stage('strata_fluvial', FLUVIAL, 'all'),
        new Stage('breakup', { threshold: 'field', rock_slope_deg: [32.0, 45.0], spread_deg: 10.0 }, 'hero'),
    ],
    'Layered plateau -> strata column -> river path with a base-level fall -> fluvial with K(zs) and the ' +
    'composite threshold (every level) -> rock breakup on the hero levels.');

export const RECIPES = [CANYON];
