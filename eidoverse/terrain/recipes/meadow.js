// Port of blender/eidoblend/terrain/recipes/meadow.py at f90c6fc.
//
// meadow: small-scale gentle ground with swales, low rises, rills and hummocks (design section 5), for the meadow
// films that used the old noise makeTerrain. No elevation reference exists at this scale: it is judged by slope p99
// < 15 degrees, no pits, and the look with grass from the old meadow probe's framing.
//
//     const t = await makeTerrain({ recipe: 'meadow', seed: 7, flatten: [{ at: [0, 0], radius: 8, falloff: 8 }] });
//
// The meadow is a 160 m tile in a countryside that reaches the horizon: the context levels run out to 10 km (context
// 64), each carrying the hills of its own scale.
//   uplift       the meadow's broad rise in a regional background of hills over the whole 10 km
//   fluvial      the backbone grows the countryside on the coarsest level (its relief steered to hills_relief_m over
//                the whole level) and refines it on every level, the valley spacing growing x1.6 per context level
//   soil_hills   the hillslopes between each level's channels at their steady soil-mantled form (solvers/
//                hillslope.js): on the main tile low rises relief_m over the swales 30 m apart, each larger scale's
//                relief growing as the square root of its spacing, and rill lines a few centimetres deep cut along
//                the swale bottoms on the finest levels
//   hydraulic    the detail package's rills on the finest level (knob `detail`)
//   hummocks     soil microrelief: frost mounds and tussock bases a hand or two high, a few metres apart
// A level clearing is the API's flatten.
//
// The recipe is data: the same stages, knobs and parameters as the Blender recipe (toDict() is to_dict()'s JSON); the
// knob functions and the op are transcribed. The op's per-cell numpy is kernels/fluvial/hummocks.wgsl (the port's own
// kernel, PORT_PLAN.md 3.2: recipes/meadow.py's hummocks on the GPU); its gradient is core/grid.js gradient (numpy's
// np.gradient, float32 central differences).

import * as Gd from '../core/grid.js';
import { Knob, Recipe, Stage } from '../core/recipe.js';
import * as N from '../core/world_noise.js';

const SPACING_GROWTH = 1.6;              // the valley spacing x1.6 per context level: 30 m -> about 500 m at 10 km

function start(p) {
    p.stage('uplift').start_m = 1.2 * Number(p.hills_relief_m);
}

function detail(p) {
    for (const s of p.stages('hydraulic')) s.enabled = Boolean(p.detail);
}

/** Stage 'hummocks' (meadow.py op_hummocks): soil microrelief added to h (loose soil: bed unchanged): low mounds and
 * hollows about amplitude_m high and deep, spacing_m apart (world-space noise, so every level that runs it agrees),
 * fading out on ground steeper than 18 degrees. Called without a stage context, as Blender's op (the runner pulls a
 * child level's band to its parent afterwards). */
export async function opHummocks(fields, level, params, seed = 0) {
    const amp = Number(params.amplitude_m ?? 0.08);
    const sp = Number(params.spacing_m ?? 4.0);
    if (sp < 6.0 * level.cell || amp <= 0) return fields;
    const R = fields.h.runner;
    const n = N.fieldGpu(R, { kind: 'fbm', wavelength_m: sp, octaves: 2, amp: 3.0 }, level, Math.trunc(seed) + 9001);
    const { gx, gy } = Gd.gradient(fields.h, level.cell);
    const out = R.field(level.n, level.n, 1);
    R.run('fluvial/hummocks', { h: fields.h, n, gx, gy }, { outH: out }, { uAmp: amp });
    for (const f of [n, gx, gy]) f.destroy();
    fields.h = out;
    return fields;
}

// lock_max_frac 2: the lock's block cap (an eighth of the level) was 20 m on the 160 m main level and 40 m on the
// 320 m one, under the swales' 30 and 48 m, so the refining levels could not form them
const FLUVIAL = { K: 1e-3, valley_spacing_m: '$valley_spacing_m', context_spacing_factor: SPACING_GROWTH,
    threshold_deg: 33.0, threshold_noise: 0.1, threshold_scale_m: 40.0, roughness: '$roughness',
    roughness_scales_m: [60.0, 15.0, 4.0], deposition: 0.3, age_myr: '$age_myr', relief_m: '$hills_relief_m',
    relief_over: 'level', control_levels: 'first', gullies: false, breakup: 0.0, outcrops: 0.0,
    lock_max_frac: 2 };

export const MEADOW = new Recipe(
    'meadow', 'Small-scale gentle ground: swales, low rises, rills and hummocks (a meadow, 80-400 m)',
    [],
    { size: 160.0, context: 64, hero_cell: 0.5, palette: 'meadow', base_elevation_m: 300.0, lakes: 'sediment' },
    {
        relief_m: new Knob(0.9, 'm', [0.1, 8.0], "the low rises' height over the swales either side of them on the " +
            "main tile (0.5-1.5 m reads at eye level). A swale's bank at its channel is 4 x relief / spacing steep and the " +
            "rill's wall adds to it: slope p99 21 at 1.3 m, 15.7 at 1.0 m, 14.4 at 0.9 m"),
        valley_spacing_m: new Knob(30.0, 'm', [8.0, 400.0], "the swales' spacing on the main tile (20-40 m)"),
        hills_relief_m: new Knob(40.0, 'm', [0.0, 400.0], "the countryside's relief over the 10 km around the meadow " +
            "(the horizon's hills)", start),
        age_myr: new Knob(0.3, 'Myr', [0.002, 3.0], 'erosion time on the coarsest level (the countryside: K t about ' +
            '300, settled; the finer levels refine)'),
        roughness: new Knob(0.5, '', [0.0, 1.5], 'erodibility noise at 60, 15 and 4 m: irregular swales'),
        rill_depth_m: new Knob(0.12, 'm', [0.0, 0.5], 'the rills cut along the swale bottoms on the finest levels (up ' +
            'to 1.3 x where more drains, about 1.4 m wide; 6 cm did not show at eye level)'),
        undulation_m: new Knob(0.3, 'm', [0.0, 2.0], "the near-level ground's own swells at the swale scale before its " +
            'water gathers (soil_hills seed_m, on the levels finer than 1 m): where the countryside leaves the meadow ' +
            'level, the swales form in their hollows'),
        hummocks_m: new Knob(0.04, 'm', [0.0, 0.6], "soil hummocks' height (about 4 m apart; at 0.06-0.08 m they and " +
            'the rills held the slope p99 over 15 degrees)'),
        detail: new Knob(true, 'bool', null, "the detail package's hydraulic rills on the finest level", detail),
    },
    [
        new Stage('uplift', { shape: { kind: 'plateau', centre: [0.0, 0.0], radius_m: 450.0, edge_m: 350.0, texture: 0.2 },
            regional: { fraction: 0.9, wavelength_m: 2500.0, texture: 0.8, octaves: 3, blend: 0.1 },
            U_m_per_yr: 2e-4, start_m: 48.0, start_roughness: 0.4 }, 'all'),
        new Stage('fluvial', FLUVIAL, 'all'),
        // relief grows as the square root of the spacing: each larger scale gentler, so the scales' slopes do not
        // stack; the rills a Gaussian 1.0 m wide (sigma) on every level that cuts them, at most 1.25 x deeper where
        // more drains; the channel heads ease in (head_soft)
        new Stage('soil_hills', { valley_spacing_m: '$valley_spacing_m', context_spacing_factor: SPACING_GROWTH,
            relief_m: '$relief_m', relief_scaling: 0.5, channel_frac: 0.25,
            rill_depth_m: '$rill_depth_m', rill_max_cell_m: 0.7, rill_width_m: 1.0,
            rill_growth_max: 1.25, seed_m: '$undulation_m', seed_max_cell_m: 1.0,
            rise_cap: 0.8, head_soft: 2.0 }, 'all'),
        new Stage('hydraulic', {}, 'last'),
        new Stage('hummocks', { amplitude_m: '$hummocks_m', spacing_m: 4.0 }, 'last'),
    ],
    "A countryside of hills to the horizon (context 64), the meadow's broad rise in it; every level's " +
    'hillslopes at their steady soil-mantled form (low rises over 30 m swales on the main tile, rill lines ' +
    "in the swales), hydraulic rills, soil hummocks; pass flatten=[...] for a level clearing.");

export const RECIPES = [MEADOW];
export const OPS = { hummocks: opHummocks };
