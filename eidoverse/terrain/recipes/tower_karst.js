// Port of blender/eidoblend/terrain/recipes/tower_karst.py at f90c6fc.
//
// tower_karst: Guilin's karst. Fenglin (steep towers and peak clusters on a flat river plain, Yangshuo) or fengcong
// (peaks packed on a raised common base, closed star-shaped dolines between them). Design 4.10 and row `tower_karst` of
// section 5; the solver is solvers/karst.js.
//
//     const t = await makeTerrain({ recipe: 'tower_karst', seed: 7 });                          // Yangshuo-like fenglin, 8 km
//     const t = await makeTerrain({ recipe: 'tower_karst', params: { kind: 'fengcong' } });      // cone karst: no plain, no river
//     const t = await makeTerrain({ recipe: 'tower_karst', params: { spacing_m: 260, median_height_m: 180, cluster_cover: 0.6 } });
//
// Stages, in order:
//   karst      every level: the alluvial plain and its river (a flat water surface with cut banks and point bars,
//              written to `water` so the lake builder draws it), the towers (each a ledged wall from its footprint's
//              edge meeting its summit: a spire's needle, a peak's knobbed cone, a block's cliffed cap with knobs; deep
//              inside a cluster the broad concave fengcong cone, its flanks meeting its neighbours' at cols), inside the
//              clusters each tower's massif body (a walled skirt reaching toward its neighbours, so a cluster stands as
//              one massif with its peaks on it, cols between them and cockpits in the gaps), the raised ground between
//              a cluster's inner towers, the talus cones at their feet, the cockpits filled flat with soil (and slots
//              under 30 m to their outlet); vertical fluting on levels with cells of 2 m or less. Rebuilt per level from
//              world functions, so the walls are sharp at every scale (levels 'all', not the design's 'resolves:200': a
//              wall upsampled from a coarser level would be soft at 0.5 m).
//   threshold  at the op's Sc (87.5 degrees), a few iterations: trims texel spikes only (solvers/hillslope.js).
//
// Why no 'creep' and no 75-degree threshold any more (the design's "threshold pass at limestone Sc 75 degrees and light
// creep"): the review measured the towers' walls at a median of 55 degrees, 8 % over 70, beside photographs with 70-90
// degree walls. The creep stage is a Gaussian of sigma sqrt(2 kappa t) = 6.3 m at every level (13 cells on a 0.49 m hero
// level): it rounded every summit into a dome and flared every foot; the threshold at 75 degrees shaved the walls back.
// The walls' angles, their ledges and their brows are now the op's own (the wall table, the brow's smooth minimum).
//
// The palette (defaults.palette, karstPalette()): the surfacing package's karst palette with its bare limestone on the
// walls' sheerest bands only (79-87 degrees), so the steep towers wear its forest as Guilin's do.
//
// The cockpits and poljes between the towers are closed depressions by design (karst drains underground): the level
// runner's end stage must neither flood nor fill them, so the recipe sets defaults.lakes = false (run.js: "false skips
// them"); the karst op already gives each its flat soil floor, and writes the river's water itself.
//
// Where this differs from tower_karst.py, and why: karst_palette() builds its dict from build/palettes.py, the
// surfacing wave's module, whose port (build/palettes.js, PORT_PLAN.md 3.5, P14) is not in the checkout yet. Until it
// is, defaults.palette stays the palette's name, 'karst' (the value tower_karst.py's Recipe(...) itself is given before
// karst_palette() replaces it), and toDict() differs from to_dict() in that one key; karstPalette(P) is transcribed and
// takes the palettes module, so the recipe takes the dict as soon as build/palettes.js lands. Nothing else differs:
// the stages, knobs and their apply are tower_karst.py's.

import { Knob, Recipe, Stage } from '../core/recipe.js';
import { DEFAULTS, KIND_PRESETS } from '../solvers/karst.js';

// the knobs that are also karst parameters; their defaults are fenglin's, and kind 'fengcong' takes its own preset for
// every one of them left at that default
const KIND_DEPENDENT = ['spacing_m', 'median_height_m', 'cluster_cover', 'plinth_m', 'base_m', 'river'];

/** Write the knob values into the karst stage's parameters. With kind other than 'fenglin', a knob left at its
 * (fenglin) default is not written, so the kind's preset in solvers/karst.js decides it. */
function applyKnobs(p) {
    const st = p.stage('karst');
    st.kind = p.kind;
    const knobs = p.recipe !== null && p.recipe !== undefined ? p.recipe.knobs : {};
    for (const k of ['spacing_m', 'median_height_m', 'wall_deg', 'cluster_cover', 'plinth_m', 'base_m', 'river',
        'river_width_m']) {
        if (!(k in p)) continue;
        const v = p[k];
        if (p.kind !== 'fenglin' && KIND_DEPENDENT.includes(k) && k in KIND_PRESETS[p.kind] && k in knobs &&
            v === knobs[k].default) continue;
        st[k] = k === 'river' ? Boolean(v) : Number(v);
    }
}

export const TOWER_KARST = new Recipe(
    'tower_karst', 'Tower karst: fenglin towers on a river plain (Guilin), or fengcong cones over dolines',
    ['guilin_karst'],
    { size: 8000.0, resolution: 1024, context: 4, hero_cell: 0.5, palette: 'karst', base_elevation_m: 110.0, lakes: false },
    {
        kind: new Knob('fenglin', 'choice', ['fenglin', 'fengcong'],
            'fenglin: peak clusters and steep isolated towers on a flat alluvial plain with a river ' +
            '(Yangshuo); fengcong: peaks packed on a raised common base with closed dolines between ' +
            '(the Li River gorge, Guizhou)', applyKnobs),
        spacing_m: new Knob(DEFAULTS.spacing_m, 'm', [60.0, 1000.0],
            'Poisson-disc spacing of the towers inside the clusters (fengcong: 210)'),
        median_height_m: new Knob(DEFAULTS.median_height_m, 'm', [15.0, 600.0],
            'median summit height above the plain (fengcong: 190, above the plain under its base)'),
        wall_deg: new Knob(DEFAULTS.wall_deg, 'deg', [70.0, 89.0],
            "the towers' cliffed walls: their median angle (each tower +-4 degrees, ledges between)"),
        cluster_cover: new Knob(DEFAULTS.cluster_cover, '', [0.0, 1.0],
            'the share of the ground inside peak clusters; the rest is plain (fengcong: 0.97)'),
        plinth_m: new Knob(DEFAULTS.plinth_m, 'm', [0.0, 300.0],
            "fengcong's common base under the clusters: the cockpit floors' height above the plain " +
            '(fengcong: 60)'),
        base_m: new Knob(DEFAULTS.base_m, 'm', [0.0, 200.0],
            "fenglin: the raised ground between a cluster's inner towers (none at its edge)"),
        river: new Knob(DEFAULTS.river, 'bool', null, 'a river meandering across the plain (fengcong: none)'),
        river_width_m: new Knob(DEFAULTS.river_width_m, 'm', [5.0, 600.0], "the river's mean width"),
    },
    [
        new Stage('karst', {}, 'all'),
        new Stage('threshold', { iterations: 24 }, 'all'),
    ],
    'Towers from blue-noise centres in clusters along the joint strike and scattered on the plain: spires, peaks ' +
    'and cliffed blocks, each a ledged wall of 76-88 degrees from its foot meeting a pointed or knobby summit; ' +
    'a river at plain level with cut banks and point bars; judged against guilin_karst (Copernicus 30 m, through ' +
    'the radar chain: its spacing, heights and plain, not its walls) and the Li River photographs.');

/** The towers' material (tower_karst.py karst_palette): the surfacing package's karst palette (its scans, colours,
 * forest canopy and fields), with two layers placed from this terrain's own fields:
 *   - bare limestone on the towers' sheer walls and on the benches' risers, from 76 to 86 degrees, the threshold
 *     broken by noise at 40 m and 12 m, bared a little lower on convex ribs and held under forest in gullies, without
 *     the convex bonus that bared the pointed summits;
 *   - river gravel and sand on the Li's banks and point bars: the ground under the plain's level by 0.7 m and more and
 *     the bed under shallow water, broken at 25 m;
 * and the plain's fields: the paddies a patchwork of whole fields (young and ripening rice), and one field in eleven
 * ploughed brown laterite, never on the damp ground by the river. P: the palettes module (build/palettes.js). */
export function karstPalette(P) {
    const pal = P.get('karst');
    const cliff = P._cliff ?? null;
    const rockW = cliff !== null ? cliff(76, 86, ' - 6*convex_20m', ' * 0') :
        'smoothstep(76, 86, slope + 6*(fbm(40, 2) - 0.5) + 2.5*(fbm(12, 0) - 0.5))';
    const gravel = { name: 'river gravel', set: 'Gravel041', tile_m: 2.0, colour: '#8b8170', roughness: 1.1,
        patches: [{ scale_m: 14.0, colour: '#a39a86', amount: 0.45 }],
        weight: 'max(smoothstep(0.05, 0.3, water), smoothstep(-0.6, -1.3, height + 0.5*(fbm(25, 2) - 0.5)) ' +
            '* smoothstep(18, 9, slope))' };
    // the plain's paddies as a patchwork of whole fields (70 m Voronoi cells with straight boundaries)
    const fields = [{ scale_m: null, colour: '#6d8f3a', amount: 0.55, where: 'smoothstep(0.66, 0.665, cells(70, 5))' },
        { scale_m: null, colour: '#8c8f48', amount: 0.5, where: 'smoothstep(0.2, 0.195, cells(70, 5))' }];
    // ploughed fields as one field in eleven (90 m cells), brown laterite under the crop stubble
    const soilW = 'smoothstep(0.91, 0.915, cells(90, 3)) * smoothstep(5, 2, slope) * smoothstep(0.75, 0.55, wetness)';
    const layers = [];
    for (let L of pal.layers) {
        if (L.name === 'limestone') {
            // the fresh faces of the collapse scarps (concave) a warm orange-grey, the weathered walls grey
            L = { ...L, weight: rockW, patches: [{ scale_m: null, colour: '#9d8370', amount: 0.6,
                where: 'smoothstep(0.3, 0.75, concave_20m + 0.25*(fbm(25, 7) - 0.5))' }, ...(L.patches ?? [])] };
        }
        if (L.name === 'paddies') L = { ...L, patches: [...fields, ...(L.patches ?? [])] };
        if (L.name === 'red soil') L = { ...L, colour: '#7b5c46', weight: soilW };
        if (L.name === 'forest') {
            layers.push(gravel);
            // the north-facing flanks' forest darker and denser, the sunny south faces lighter and yellower; the crowns
            // from afar softer and broader
            if (L.canopy !== null && typeof L.canopy === 'object' && !Array.isArray(L.canopy)) {
                L = { ...L, canopy: { ...L.canopy, crown_m: 8.0, light: '#577b40', gap: '#27361f' } };
            }
            L = { ...L, patches: [...(L.patches ?? []),
                { scale_m: null, tint: [0.8, 0.86, 0.8], amount: 0.5, where: 'smoothstep(0.1, 0.8, northness) * smoothstep(12, 25, slope)' },
                { scale_m: null, tint: [1.12, 1.1, 0.92], amount: 0.45, where: 'smoothstep(-0.1, -0.8, northness) * smoothstep(12, 25, slope)' }] };
        }
        layers.push(L);
    }
    if (!layers.some((L) => L.name === 'river gravel')) layers.splice(Math.min(2, layers.length), 0, gravel);
    const out = { ...pal, layers: layers.slice(0, P.MAX_LAYERS),
        title: pal.title + " (tower_karst: rock on the sheer walls, gravel on the river's banks and bars)" };
    delete out.name;
    return out;
}

// the surfacing wave's palettes module, when it is in the checkout (see the header)
let Pal = null;
try {
    Deno.statSync(new URL('../build/palettes.js', import.meta.url));
    Pal = await import(new URL('../build/palettes.js', import.meta.url).href);
} catch (_e) { /* not ported yet: the palette's name stands */ }
if (Pal) TOWER_KARST.defaults.palette = karstPalette(Pal);

export const RECIPES = [TOWER_KARST];
export { karstPalette as karst_palette };
