// Port of blender/eidoblend/terrain/recipes/badlands.py at f90c6fc.
//
// badlands: dense rills and knife-edge ridges cut into soft banded rock (design section 5), judged against the
// Badlands Wall near Cedar Pass, South Dakota (3 km at 3 m, and its 1.2 km detail at 1.2 m).
//
//     const t = await makeTerrain({ recipe: 'badlands', params: { relief_m: 140 }, focus: [600, 240] });
//
// The stages (solvers/strata.js): the Badlands' column (Chadron clay at the foot, the Brule's banded mudstone with
// thin sandstone and ash ledges, a channel sandstone the upper prairie is stripped to, the Rockyford ash and the Sharps
// formation at the crest); the wall as a band of high ground between a lower prairie (south) and an upper prairie
// (north), each held at its height at the coarsest level's edge (the base levels); then the fluvial backbone at fine
// valley spacing in very erodible rock with the composite threshold and weathering, which cuts the band's flanks into
// gullies, knife ridges and pinnacles; rock breakup and hydraulic rills on the hero levels. The prairies are sod: on the
// hero levels gentle ground keeps a tenth of its erodibility, so the rills stay on the bare walls.
//
// Heights: z = 0 is the lower prairie at the tile's south; base_elevation_m (735 m) places it.
//
// The recipe is data: the same stages, knobs and parameters as the Blender recipe (toDict() is to_dict()'s JSON, but
// for defaults.palette until build/palettes.js lands: solvers/strata.js paletteFor); the knob functions are
// transcribed. The comments on the parameters are the Blender file's.

import { Knob, Recipe, Stage } from '../core/recipe.js';
import * as S from '../solvers/strata.js';

const COLUMN = 'badlands';

/** The wall band: a broad ridge whose crest stands relief_m above the lower prairie, falling over long flanks to the
 * lower prairie (south) and the upper prairie (north, upper_prairie_m). Long flanks, not cliff edges round a flat top. */
function shape(p) {
    const pl = p.stage('plateau');
    const rel = Number(p.relief_m);
    const up = Number(p.upper_prairie_m);
    pl.surface_zs_m = Number(p.prairie_zs_m) + rel;
    const w = Number(p.wall_width_m);
    const c = -0.1 * w - 150.0;                           // the band south of the centre: the upper prairie the
    const fs = 0.3 * w, fn = 0.45 * w;                    // tile's northern part, the lower one along its south;
    pl.edges = [                                          // the southern wall the steeper (Cedar Pass faces south)
        { through: [0.0, c - 0.5 * w + 0.5 * fs], strike_deg: 90.0, drop_m: rel, width_m: fs,
            wiggle_m: 0.15 * w, wiggle_wavelength_m: 800.0 },
        { through: [0.0, c + 0.5 * w - 0.5 * fn], strike_deg: 270.0, drop_m: Math.max(rel - up, 0.0),
            width_m: fn, wiggle_m: 0.1 * w, wiggle_wavelength_m: 700.0 },
    ];
}

function detail(p) {
    for (const name of ['breakup', 'hydraulic']) for (const s of p.stages(name)) s.enabled = Boolean(p.detail);
}

const STRATA = { column: COLUMN, zs0_m: '$prairie_zs_m', dip_deg: 0.15, azimuth_deg: 110.0,
    warp: [[1200.0, 1.5], [250.0, 0.5]] };
// the start's roughness seeds drainage all over the band and its flanks; the prairies past the flanks' feet are
// sod-covered and smoother (x0.35, with the hero levels' sod)
const PLATEAU = { surface_zs_m: 165.0, roughness: [[700.0, 4.0], [180.0, 3.0], [50.0, 1.2]], roughness_low: 0.35,
    roughness_fade: 0.3 };
// Rills, not retreat, make badlands: the stream-power incision cuts the band into ravines about 120 m apart on the
// coarsest pass, and every later pass refines under the low-pass lock, adding the gullies and the rills on their walls
// without wearing the ridges down; slow weathering with a weak drainage boost; the rock mass varies from 8 m to 300 m;
// the prairies are sod on the hero levels (strata.py's notes)
const FLUVIAL = { K: '$incision_K', valley_spacing_m: '$gully_spacing_m', gullies: true, roughness: 0.5,
    roughness_scales_m: [800.0, 150.0, 30.0], deposition: 0.15, age_myr: '$age_myr',
    repose_deg: 36.0, later: 'refine', weather_m_per_yr: 6e-5,
    weather_area: 0.15, weather_loose: 1.5, edge_follow: false, resist: 0.3, resist_run: 0.35,
    resist_scales_m: [300.0, 120.0, 45.0, 18.0, 8.0], sod: { below_deg: 10.0, above_deg: 22.0, k: 0.1 } };
// the pipe model's micro-relief only steers the water: none of it is kept
const HYDRAULIC = { roughness_flat: 0.1, roughness_keep_m: [0.0, 0.01] };

export const BADLANDS = new Recipe(
    'badlands', 'Badlands: dense rills and knife-edge ridges in soft banded rock between flat prairies',
    ['badlands_sd', 'badlands_sd_detail'],
    { size: 3000.0, context: 2, hero_cell: 0.25, base_elevation_m: 735.0, lakes: 'sediment',
        palette: await S.paletteFor('badlands', COLUMN) },
    {
        relief_m: new Knob(125.0, 'm', [20.0, 600.0], "the crest of the start's band above the lower prairie (the " +
            "cut ridges stand a little higher: the Cedar Pass tile's relief " +
            'is about 148 m; a 150 m band gave 192)', shape),
        upper_prairie_m: new Knob(60.0, 'm', [0.0, 600.0], 'the upper prairie above the lower one (Cedar Pass: ' +
            'about 60 m in the reference tile)', shape),
        wall_width_m: new Knob(1600.0, 'm', [100.0, 10000.0], 'the band of high ground the wall is cut from, its ' +
            'flanks included', shape),
        incision_K: new Knob(3e-5, '', [1e-6, 1e-3], 'the stream-power erodibility of the mudstone (K per year: with ' +
            "m = 0.5 the law's unit is 1/yr): how fast the ravines and rills " +
            'cut into the band (1e-4 planed it to the lower prairie)'),
        prairie_zs_m: new Knob(5.0, 'm', [0.0, 170.0], 'where in the column the lower prairie sits', shape),
        gully_spacing_m: new Knob(60.0, 'm', [10.0, 1000.0], "the gullies' spacing on the main level (the coarsest " +
            'pass resolves ravines about 120 m apart; the hero levels ' +
            'halve it per level: rills 30, 15 m apart)'),
        age_myr: new Knob(0.12, 'Myr', [0.01, 5.0], 'the time the coarsest level runs (badlands erode centimetres a ' +
            'year: a wall is a hundred thousand years old)'),
        detail: new Knob(true, 'bool', null, 'rock breakup and hydraulic rills on the hero levels', detail),
    },
    [
        new Stage('strata', STRATA, 'all'),
        new Stage('plateau', PLATEAU, 'all'),
        new Stage('strata_fluvial', FLUVIAL, 'all'),
        new Stage('breakup', { threshold: 'field', rock_slope_deg: [30.0, 45.0], spread_deg: 8.0 }, 'hero'),
        new Stage('hydraulic', { ...HYDRAULIC }, 'hero'),
    ],
    'The wall band between two prairies -> fluvial at fine spacing in soft layered rock with the composite ' +
    'threshold and weathering -> rock breakup and hydraulic rills (hero).');

export const RECIPES = [BADLANDS];
