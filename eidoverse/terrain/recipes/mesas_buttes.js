// Port of blender/eidoblend/terrain/recipes/mesas_buttes.py at f90c6fc.
//
// mesas_buttes: flat caprock remnants standing on talus over a broad desert floor (design section 5), judged against
// Monument Valley.
//
//     const t = await makeTerrain({ recipe: 'mesas_buttes', params: { caprock_fraction: 0.05 }, focus: [-1100, 40] });
//
// The stages (solvers/strata.js, solvers/rivers.js): Monument Valley's column (the Cedar Mesa sandstone the floor is
// stripped to, the Organ Rock shale's pedestal about 150 m, the De Chelly sandstone's sheer walls about 160 m and a
// thin conglomerate cap: the Mittens' proportions); a plateau at the cap's top; a winding wash across the tile as the
// base level, cut down to the floor over the first part of the run; then the walls retreat (weathering: the Organ Rock
// wears back under the De Chelly, which fails over it at 80 degrees and leaves its debris as talus pedestals), fastest
// where runoff gathers, so the escarpment frays into fingers, and it passes the massive cores of the De Chelly (blue
// noise, long along the joints, rounded and each its own outline), which it leaves standing as buttes and mesas. The run
// stops when the caprock left in the main tile (the ground at or above the De Chelly's base) falls to
// `caprock_fraction`. The floor follows the Cedar Mesa's top, which undulates a metre or two over 90-260 m. Rock breakup
// on the hero levels.
//
// Heights: z = 0 is the wash's final bed at the tile centre; base_elevation_m (1520 m) places it.
//
// The recipe is data: the same stages, knobs and parameters as the Blender recipe (toDict() is to_dict()'s JSON, but
// for defaults.palette until build/palettes.js lands: solvers/strata.js paletteFor); the knob functions are
// transcribed. The comments on the parameters are the Blender file's.

import { Knob, Recipe, Stage } from '../core/recipe.js';
import * as S from '../solvers/strata.js';

const COLUMN = 'monument_valley';
const CAP_BASE_ZS = S.column(COLUMN).baseOf('De Chelly');          // 330 m: the caprock is the De Chelly and above

function surface(p) {
    p.stage('plateau').surface_zs_m = Number(p.floor_zs_m) + Number(p.relief_m);
}

function cap(p) {
    const f = p.stage('strata_fluvial');
    f.caprock_target = Number(p.caprock_fraction);
    f.caprock_zs_m = CAP_BASE_ZS;
}

function detail(p) {
    for (const s of p.stages('breakup')) s.enabled = Boolean(p.detail);
}

// a 1.4-degree dip: the floor, stripped to the Cedar Mesa's top, rises about 195 m across the tile toward the west
// north-west, as Monument Valley's does; the beds also undulate a metre or two over 90-260 m, and the stripped floor
// follows them: low swells, ledges and swales
const STRATA = { column: COLUMN, zs0_m: '$floor_zs_m', dip_deg: 1.4, azimuth_deg: 160.0,
    warp: [[3500.0, 6.0], [800.0, 2.5], [260.0, 1.4], [90.0, 0.5]] };
// two joint sets (the De Chelly's fracture pattern): weathering and incision run faster along them, 60 degrees apart,
// the second weaker
const JOINTS = [{ strike_deg: 20.0, spacing_m: 650.0, width_m: 35.0 },
    { strike_deg: 80.0, spacing_m: 900.0, width_m: 35.0, strength: 0.7 }];
// massive cores in the De Chelly (strata.rockCores, blue noise about 1.8 km apart, 600-1300 m across, long along the
// joints, rounded and each its own outline): the escarpment retreats past them and leaves them standing
const CORES = { spacing_m: 1800.0, radius_m: [300.0, 650.0], elongation: [1.0, 2.2], angles_deg: [20.0, 80.0],
    strength: 3.0, region_m: 40000.0, exponent: 2.5, wobble: 0.2 };
const PLATEAU = { surface_zs_m: 480.0, roughness: [[3000.0, 5.0], [600.0, 2.0], [120.0, 0.6]] };
// the wash winds (32 degrees at 3.5 km): the escarpment retreating from it is embayed, not one straight front
const RIVER = { kind: 'walk', through: [0.0, 0.0], flow_azimuth_deg: 20.0, wiggle_deg: 32.0,
    wiggle_wavelength_m: 3500.0, width_m: 40.0, bed_m: 0.0, gradient: 0.004,
    schedule: [[0.0, 0.0], [0.25, 1.0], [1.0, 1.0]] };
// buttes outlive the escarpment's passage when it retreats mainly up its washes (the drainage boost, fraying) and a
// cut-off block only wears back slowly (the base weathering, the cores); the rock mass's noise at half strength, the
// joints at 2.5... (strata.py's notes: resist_noise 0.5, joint_gain 1.8, resist_run 0.3; the later passes 0.12 of
// the first's time)
const FLUVIAL = { K: 1.5e-6, valley_spacing_m: 600.0, roughness: 0.6, roughness_scales_m: [3000.0, 700.0, 150.0],
    deposition: 0.6, age_myr: 6.0, max_steps: 8000, repose_deg: 33.0, later: 'refine',
    later_frac: 0.12,
    weather_m_per_yr: '$weathering_m_per_yr', weather_area: '$fraying', weather_loose: 0.6,
    joints: JOINTS, joint_gain: 1.8, resist: 0.8, resist_run: 0.3, resist_noise: 0.5,
    resist_scales_m: [1500.0, 600.0, 240.0, 90.0, 35.0], resist_cores: CORES,
    caprock_target: 0.08, caprock_zs_m: CAP_BASE_ZS, check_every: 40 };

export const MESAS_BUTTES = new Recipe(
    'mesas_buttes', 'Mesas and buttes: flat caprock remnants, sheer walls over talus pedestals, a broad desert floor',
    ['monument_valley'],
    { size: 8000.0, context: 2, hero_cell: 0.5, base_elevation_m: 1520.0, lakes: 'sediment',
        palette: await S.paletteFor('desert_sandstone', COLUMN) },
    {
        caprock_fraction: new Knob(0.08, '', [0.005, 0.6], 'the share of the main tile still at or above the ' +
            "De Chelly's base when the run stops (Monument Valley: its " +
            'butte and mesa tops and walls about 0.06-0.08; a young ' +
            'plateau edge 0.3+)', cap),
        relief_m: new Knob(340.0, 'm', [50.0, 2000.0], "the cap rock's top above the wash's final bed (the Mittens " +
            'stand about 300-330 m over the floor; 340 puts the start at ' +
            "the Shinarump's top)", surface),
        floor_zs_m: new Knob(140.0, 'm', [0.0, 500.0], "where in the column the wash's bed sits (140: 10 m under " +
            "the Cedar Mesa's top, which the floor is stripped to)", surface),
        weathering_m_per_yr: new Knob(2e-4, 'm/yr', [0.0, 3e-3], 'how fast rock of erodibility factor 1 on a ' +
            '30-degree slope wears down (the Organ Rock shale ' +
            "x2.5, the De Chelly x0.08): the walls' retreat (at " +
            '1e-4 the escarpment had not retreated far enough ' +
            'to free the buttes by the end of the run)'),
        fraying: new Knob(3.0, '', [0.0, 6.0], 'how much faster the walls wear back where runoff gathers (x 1 + ' +
            'this sqrt(area / 10 ha)): the escarpment frays into fingers that ' +
            'part into buttes'),
        detail: new Knob(true, 'bool', null, 'joint-guided rock breakup on the hero levels', detail),
    },
    [
        new Stage('strata', STRATA, 'all'),
        new Stage('plateau', PLATEAU, 'all'),
        new Stage('river_path', RIVER, 'all'),
        new Stage('strata_fluvial', FLUVIAL, 'all'),
        new Stage('breakup', { threshold: 'field', rock_slope_deg: [35.0, 50.0], spread_deg: 8.0 }, 'hero'),
    ],
    'Plateau of layered rock -> a wash cut to the floor (base-level fall) -> the walls retreat by weathering ' +
    'and failure until the caprock fraction is reached (talus pedestals, buttes) -> rock breakup (hero).');

export const RECIPES = [MESAS_BUTTES];
