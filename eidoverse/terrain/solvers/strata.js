// Port of blender/eidoblend/terrain/solvers/strata.py at f90c6fc.
//
// Layered rock (design section 4.9): a stratigraphic column in world z that the erosion reads at every cell's current
// height, so canyons step in cliffs and benches, mesas and buttes stand on talus over a flat floor, and badlands cut
// banded mudstone into knife ridges.
//
//     stage ops (OPS; run.js calls op(fields, level, params, seed, ctx)):
//       'strata'          the column and where it sits (dip, warp, faults, its height at h = 0), kept for the level's
//                         later stages (ctx.shared.strata), and the field zs (stratigraphic height, metres: the masks'
//                         `strata`, which the material reads its colour bands at)
//       'plateau'         the start (on a fresh level only): a structural surface at one stratigraphic height (so it
//                         follows the dip and warp of the beds), roughened, optionally with an escarpment
//       'strata_fluvial'  the fluvial backbone (solvers/fluvial.js's passes) in layered rock: the erodibility K x
//                         K(zs) in the stream-power incision, the composite threshold (each layer at its own angle,
//                         talus at repose) in place of a single Sc, creep only on soft rock and debris, weathering,
//                         and the base-level fall: a 'river_path' channel lowered from the starting surface to its
//                         final bed over the run (solvers/rivers.js); optionally stopped at a target caprock fraction
//
//     import * as S from './solvers/strata.js';
//     const col = S.column('colorado_plateau');       // bottom to top, zs = 0 at its base
//     col.tanAt(800.0), col.kAt(800.0), col.runAt(800.0), col.layerAt(800.0)
//     col.formations()                                // [[thickness_m, K_factor, Sc_deg, colour_id, name], ...]
//     await S.paletteFor('desert_sandstone', 'colorado_plateau')   // a palette whose strata layers read this column
//
// The column, the stratigraphic height zs = h + zs0 - tan(dip) (x cos az + y sin az) - warp - throws - fold, the
// composite threshold, the weathering and every parameter of 'strata_fluvial' are strata.py's (its module doc, the
// same names, units and meanings: FLUVIAL_DEFAULTS below and fluvial.js's DEFAULTS). Fields read: h, bed, K_factor, A,
// qs. Written: h, bed, A, qs, wear, deposit, talus, zs, U, K, Sc (the layer's own tan theta at each cell), G, river.
//
// The kernels are kernels/strata_threshold.wgsl and the inline kernels of strata.py as files of their names
// (PORT_PLAN.md 3.3): strata_cell.wgsl, strata_creep.wgsl, strata_weather.wgsl (FACIES_GLSL is
// kernels/strata/facies.wgsl, which it includes). Their numpy twins stay in Python (the oracles,
// tests/parity/fixtures.py).
//
// The dispatch log (PORT_PLAN.md 5.7): every Blender kernel (world_noise_field for the noise, then StrataRun's
// flow_weights, route_incise, strata_weather, strata_cell, h_keep, strata_creep, creep_layers, strata_threshold,
// threshold, lock_restrict, lock_apply) is dispatched in strata.py's order with its uniforms made in doubles as numpy
// makes them. The convergence loop this module names: the caprock check of the coarsest level's first pass (stop when
// the caprock left falls to the target, tested every check_every steps), whose step count may differ by whole check
// intervals (CONVERGENCE_LOOPS).
//
// Where this differs from strata.py, and why (PORT_PLAN.md 2.4, 3.2: per-cell work on the GPU):
//   - Fields are core/gpu.js fields; the ops are async. The numpy expressions over whole levels are the port's own
//     kernels in kernels/strata/ (each names the numpy lines it replaces): offset() (offset.wgsl: the dip plane,
//     warps, faults and fold), the plateau start (plateau.wgsl, acc.wgsl), joint_field (joints.wgsl), rock_mass
//     (acc.wgsl), rock_cores and _box_noise (cores.wgsl), the forcing pack (par.wgsl), the edge follow (ring.wgsl),
//     caprock_fraction (caprock.wgsl), fill_dry_basins (dry.wgsl, with solvers/hydro.js fillDepressions and
//     core/prims.js label: numpy's fill and labels to the bit), and the end fields zs, K and Sc with facies_factor
//     (final.wgsl). numpy evaluates them in float64 from the GPU's float32 noise; here they are float32 in numpy's
//     order, and a world-space plane or line is evaluated as its value at the level's first cell plus its steps per
//     column and per row, made in doubles, so the float32 arithmetic works on the level's extent. They are not Blender
//     kernels, so the dispatch-log comparison sets them aside.
//   - The plans over objects stay JavaScript in doubles (plan 2.4): the column and its tables, the cores' centres
//     (dart throwing), each core's box and its box noise's plane waves (numpy's Generator, core/np_random.js).
//   - The edge follow: strata.py reads the level back every pin_every steps to see whether any ring cell's pin must
//     come down (lower.any()), and re-pins only then or when the fall's fraction changed. Here the lowering is a
//     kernel and the pins are made again at every such step: where nothing moved they are the same pins (the same
//     kernels on the same inputs), so the run is the same and it never waits for a readback inside the loop (plan 4.5).
//     strata.py's set_pins uploads a texture, which the dispatch log does not see; here it is a pack (prims, set aside).
//   - caprock_fraction's zs is h - zoff in float32 (numpy: float64 h minus its float64 offset); a cell within a float32
//     step of the caprock's base can count the other way, which moves the fraction by one cell in the main window's
//     and the run's stop by at most one check interval.
//   - The river's channel the first pins call returns is copied (rivers.js's cache releases a channel when a growing
//     course changes, where numpy's array stays).
//   - palette_for() reads build/palettes.js (the surfacing wave's, PORT_PLAN.md 3.5) when it is in the checkout; until
//     then it returns the palette's name and its strata layers (material_column) without the named palette's other
//     entries, and says so in `pending`. It is async (a module that may not exist is imported when asked for).
//   - Python's round() is core/levels.js pyRound (half to even), its f-string formats are pyFormat.

import * as Gd from '../core/grid.js';
import { closeMatches, pyFormat, pyRound } from '../core/levels.js';
import { defaultRng } from '../core/np_random.js';
import { f32AtOrBelow, prims } from '../core/prims.js';
import * as RUN from '../run.js';
import * as FL from './fluvial.js';
import * as HS from './hillslope.js';
import * as HY from './hydro.js';
import * as RV from './rivers.js';

const DEG = Math.PI / 180.0;
export const DZ = 0.5;
export const PAD_M = 60.0;
/** The convergence loops of this module's ops, by op and kernel (PORT_PLAN.md 5.7): the caprock check every
 * check_every steps stops the coarsest level's first pass, so every kernel of the step may run fewer or more times by
 * whole check intervals (the interval is the stage's check_every, 40 by default). */
export const CONVERGENCE_LOOPS = Object.freeze({ 'strata_fluvial|*': 'check_every' });

const has = (o, k) => o !== null && o !== undefined && Object.prototype.hasOwnProperty.call(o, k);
const now = () => performance.now() / 1000;
class ValueError extends Error { constructor(m) { super(m); this.name = 'ValueError'; } }
class KeyError extends Error { constructor(m) { super(m); this.name = 'KeyError'; } }


// =============================================================================================== the columns ===
// Bottom to top. Thicknesses are the section's own; K_factor multiplies the stage's K; Sc_deg is the angle the rock
// stands at (cliffs 70-84, ledgy slopes 40-50, shale 28-34). Colour ids match build/palettes.LAYER_COLOURS. The
// sections' notes (how each was checked against its DEM and photographs) are strata.py's, at f90c6fc.

function _L(name, thicknessM, KFactor, ScDeg, colour = null, creep = null, beds = null) {
    const d = { name, thickness_m: Number(thicknessM), K_factor: Number(KFactor), Sc_deg: Number(ScDeg),
        colour: colour || name.split(/\s+/)[0].toLowerCase() };
    if (creep !== null) d.creep = Number(creep);
    if (beds !== null) d.beds = { ...beds };
    return d;
}

export const COLUMNS = {
    // The Grand Canyon's Paleozoic section as it stands at Toroweap (east of the Toroweap fault)
    colorado_plateau: [
        _L('Vishnu schist', 200, 0.35, 65, 'vishnu'),
        _L('Tapeats sandstone', 60, 0.3, 70, 'tapeats'),
        _L('Bright Angel shale', 80, 2.5, 32, 'bright angel'),
        _L('Muav limestone, lower cliffs', 110, 0.4, 70, 'muav'),
        _L('Muav limestone, ledgy middle', 60, 0.55, 38, 'muav'),
        _L('Muav limestone, upper cliffs', 100, 0.4, 68, 'muav'),
        _L('Muav limestone, top ledges', 80, 0.5, 40, 'muav'),
        _L('Temple Butte formation', 60, 0.35, 64, 'muav'),
        _L('Redwall limestone', 170, 0.2, 74, 'redwall'),
        _L('Watahomigi formation (lower Supai ledges)', 70, 0.55, 48, 'supai'),
        _L('Manakacha formation (Supai cliffs and ledges)', 70, 0.4, 62, 'supai'),
        _L('Wescogame formation (Supai ledges)', 60, 0.5, 50, 'supai'),
        _L('Esplanade sandstone', 85, 0.18, 72, 'esplanade'),
        _L('Hermit shale', 265, 3.5, 25, 'hermit'),
        _L('Coconino sandstone', 50, 0.25, 74, 'coconino'),
        _L('Toroweap formation', 100, 0.9, 46, 'toroweap'),
        _L('Kaibab limestone, Fossil Mountain cliff', 90, 0.3, 70, 'kaibab'),
        _L('Kaibab limestone, Harrisburg ledges', 90, 0.8, 42, 'kaibab'),
    ],
    // The Goosenecks of the San Juan: the Paradox and Honaker Trail formations, limestone ledges and shaly slopes in
    // thin alternation, under the Halgaito's red slopes and a resistant bed the plateau is stripped to
    honaker_trail: [
        _L('Paradox formation, lower cliff', 50, 0.25, 76, 'limestone'),
        _L('Paradox formation, shaly ledge', 20, 0.9, 40, 'shale'),
        _L('Paradox formation, upper cliff', 70, 0.25, 74, 'limestone'),
        _L('lower Honaker Trail formation, slope', 25, 1.0, 36, 'shale'),
        _L('lower Honaker Trail formation, cliff', 35, 0.3, 70, 'limestone'),
        _L('lower Honaker Trail formation, ledges', 30, 0.9, 42, 'limestone'),
        _L('upper Honaker Trail formation, cliff', 25, 0.35, 66, 'limestone'),
        _L('upper Honaker Trail formation, slope', 35, 1.2, 34, 'shale'),
        _L('upper Honaker Trail formation, rim ledge', 30, 0.3, 66, 'limestone'),
        _L('Halgaito formation', 80, 9.0, 30, 'shale'),
        _L('Cedar Mesa sandstone (basal bed)', 30, 0.18, 64, 'cedar mesa'),
        _L('Cedar Mesa sandstone', 70, 0.5, 45, 'cedar mesa'),
    ],
    // Monument Valley: the Cedar Mesa sandstone the floor is stripped to, the Organ Rock shale's talus pedestals, the
    // De Chelly sandstone's sheer walls and the thin conglomerate cap the buttes' flat tops are
    monument_valley: [
        _L('Cedar Mesa sandstone', 150, 0.08, 62, 'cedar mesa'),
        _L('Organ Rock shale', 150, 2.5, 31, 'organ rock', null,
            { period_m: 18.0, ledge_frac: 0.2, ledge_K_factor: 0.5, ledge_Sc_deg: 55.0, jitter: 0.5 }),
        _L('De Chelly sandstone', 160, 0.08, 80, 'de chelly'),
        _L('Shinarump conglomerate', 20, 0.1, 78, 'shinarump'),
    ],
    // The Badlands Wall near Cedar Pass: Chadron clay mounds at the foot, the Brule's banded mudstone with thin
    // sandstone and ash ledges, the Rockyford ash and the Sharps formation at the top
    badlands: [
        _L('Chadron formation', 30, 2.0, 34, 'chadron', 1.0),
        _L('Brule formation, Scenic member', 46, 1.2, 49, 'brule', 0.1,
            { period_m: 3.5, ledge_frac: 0.25, ledge_K_factor: 0.4, ledge_Sc_deg: 65.0, jitter: 0.5 }),
        _L('Brule formation, channel sandstone', 4, 0.15, 70, 'sandstone'),
        _L('Brule formation, Poleslide member', 48, 1.0, 49, 'brule', 0.1,
            { period_m: 4.0, ledge_frac: 0.25, ledge_K_factor: 0.4, ledge_Sc_deg: 65.0, jitter: 0.5 }),
        _L('Rockyford ash', 6, 0.5, 62, 'ash'),
        _L('Sharps formation', 40, 1.0, 48, 'sharps', 0.15,
            { period_m: 5.0, ledge_frac: 0.2, ledge_K_factor: 0.45, ledge_Sc_deg: 62.0, jitter: 0.5 }),
    ],
    chalk: [_L('chalk with flint bands', 400, 0.8, 80, 'chalk')],
    limestone: [_L('limestone', 600, 0.4, 75, 'limestone')],
    granite: [_L('granite', 3000, 0.25, 65, 'granite')],
};

// The colour of each colour id in daylight photographs (desert varnish and staining included), with the material's
// roughness multiplier, mean bed thickness (m) and bed colour jitter: build/palettes' strata-column form. A colour is a
// hex or [[hex, weight], ...] (each bed draws one).
export const MATERIAL = {
    vishnu: ['#4f4844', 1.0, 6.0, 0.05], tapeats: ['#7d5b45', 1.0, 2.0, 0.07],
    'bright angel': ['#7a6f5e', 1.0, 2.0, 0.06], muav: ['#8c6553', 1.0, 3.0, 0.06],
    redwall: ['#a15b43', 0.95, 6.0, 0.05], supai: ['#8f4a33', 1.0, 2.5, 0.09],
    esplanade: ['#a8653f', 0.95, 4.0, 0.06], hermit: ['#9a4f37', 1.0, 2.0, 0.07],
    coconino: ['#cdb48c', 0.9, 6.0, 0.04], toroweap: ['#b19a7c', 1.0, 2.5, 0.06],
    kaibab: ['#c4b294', 0.95, 3.5, 0.05],
    limestone: ['#9e958a', 0.95, 2.5, 0.06], sandstone: ['#b0875f', 1.0, 2.5, 0.07],
    shale: ['#94634c', 1.0, 1.5, 0.07],
    'cedar mesa': ['#c7a17b', 1.0, 3.0, 0.06], 'organ rock': ['#9c4f37', 1.0, 2.0, 0.07],
    'de chelly': ['#b8663f', 0.95, 8.0, 0.04], moenkopi: ['#9a5940', 1.0, 1.5, 0.08],
    shinarump: ['#a7896c', 1.0, 2.0, 0.06],
    chadron: ['#a29e8b', 1.0, 3.0, 0.05],
    brule: [[['#cdae92', 0.55], ['#b47a62', 0.22], ['#9a6150', 0.12], ['#d9d1c2', 0.11]], 1.0, 0.9, 0.07],
    ash: ['#ddd6c8', 0.95, 1.5, 0.04], sharps: [[['#cdbfa8', 0.8], ['#b9a58c', 0.2]], 1.0, 1.6, 0.06],
    chalk: ['#e2ded3', 0.9, 1.2, 0.03], granite: ['#9d9890', 1.0, 40.0, 0.03],
};

/** The column as build/palettes' strata-column dict ({ base_m: 0, formations: [[name, thickness_m, colour,
 * roughness, bed_m, jitter], ...] }): the solver's own thicknesses, so the material's colour bands sit on the benches
 * the solver made (the mask `strata` is zs, from the column's base). */
export function materialColumn(spec, dz = null, seed = 0) {
    const col = column(spec, dz === null ? DZ : dz, seed);
    const rows = col.layers.map((d) => {
        const c = MATERIAL[String(d.colour).toLowerCase()] ?? ['#a39a8e', 1.0, 2.5, 0.06];
        return [d.name, d.thickness_m, ...structuredClone(c)];
    });
    return { base_m: 0.0, formations: rows };
}

/** A palette dict for a recipe's defaults.palette: the named palette (build/palettes.js PALETTES) with its strata
 * layers reading this column (materialColumn), from the attribute the masks write (zs). Async: build/palettes.js (the
 * surfacing wave's) is imported when it is in the checkout; until then the result is the palette's name and its
 * strata layers, with `pending` naming what is missing (module doc). */
export async function paletteFor(base, spec) {
    let P = null;
    try {
        P = await import(new URL('../build/palettes.js', import.meta.url).href);
    } catch (e) {
        if (!/not found|cannot find|No such file/i.test(String(e?.message ?? e))) throw e;
    }
    const name = `${base}+${typeof spec === 'string' ? spec : 'column'}`;
    const strata = { column: materialColumn(spec), source: 'attribute' };
    if (P && P.PALETTES && P.PALETTES[base]) return { ...structuredClone(P.PALETTES[base]), name, strata };
    return { name, base, strata, pending: 'build/palettes.js (the surfacing wave) holds the named palette' };
}

/** How much a rock creeps from the angle it stands at: shale and mudstone (<= 35 degrees) 1, ledgy rock less, cliff
 * rock (>= 62 degrees) 0.02: bare walls do not creep. */
export function defaultCreep(scDeg) {
    const t = Math.tan(Number(scDeg) * DEG);
    const lo = Math.tan(35.0 * DEG), hi = Math.tan(62.0 * DEG);
    return Math.min(1.0, Math.max(0.02, (hi - t) / (hi - lo)));
}

function _layerDict(row) {
    let d;
    if (!Array.isArray(row) && typeof row === 'object') {
        d = { ...row };
    } else {
        const r = [...row];
        d = { thickness_m: r[0], K_factor: r[1], Sc_deg: r[2], colour: r.length > 3 ? r[3] : null,
            name: r.length > 4 ? r[4] : `layer ${r.length > 3 ? r[3] : ''}` };
    }
    for (const k of ['thickness_m', 'K_factor', 'Sc_deg']) {
        if (!has(d, k)) throw new ValueError(`a column layer needs ${k}: ${JSON.stringify(row)}`);
    }
    d.thickness_m = Number(d.thickness_m);
    d.K_factor = Number(d.K_factor);
    d.Sc_deg = Number(d.Sc_deg);
    if (d.thickness_m <= 0 || d.K_factor <= 0 || !(d.Sc_deg >= 5.0 && d.Sc_deg <= 89.0)) {
        throw new ValueError(`column layer '${d.name}': thickness and K factor must be positive, Sc 5-89 degrees`);
    }
    if (!has(d, 'name')) d.name = 'layer';
    d.colour = d.colour || String(d.name).split(/\s+/)[0].toLowerCase();
    if (!has(d, 'creep')) d.creep = defaultCreep(d.Sc_deg);
    return d;
}

const ordSum = (s) => [...String(s)].reduce((a, c) => a + c.codePointAt(0), 0);

/** A stratigraphic column (strata.py Column): .layers (formations, bottom to top, with base_m and top_m), .fine (the
 * beds every table reads: [bottom, top, K, tan, creep, formation]), .top_m, and the tables .z0, .dz, .K, .tan, .creep,
 * .R, .zs (Float64Array) and .formation (Int32Array). */
export class Column {
    constructor(layers, name = 'custom', dz = DZ, seed = 0) {
        this.name = name;
        this.dz = Number(dz);
        this.layers = [];
        let z = 0.0;
        for (const row of layers) {
            const d = _layerDict(row);
            d.base_m = z;
            d.top_m = z + d.thickness_m;
            z = d.top_m;
            this.layers.push(d);
        }
        if (!this.layers.length) throw new ValueError('a column needs at least one layer');
        this.top_m = z;
        const rng = defaultRng(Math.trunc(seed) * 977 + (ordSum(name) % 7919));
        const fine = [];
        this.layers.forEach((d, i) => {
            const b = d.base_m, t = d.top_m;
            const beds = d.beds;
            const base = [d.K_factor, Math.tan(d.Sc_deg * DEG), d.creep];
            if (!beds || !Object.keys(beds).length) {
                fine.push([b, t, ...base, i]);
                return;
            }
            const per = Number(beds.period_m ?? 10.0);
            const frac = Number(beds.ledge_frac ?? 0.4);
            const jit = Number(beds.jitter ?? 0.3);
            const lsc = Number(beds.ledge_Sc_deg ?? 70.0);
            const led = [Number(beds.ledge_K_factor ?? 0.3), Math.tan(lsc * DEG), defaultCreep(lsc)];
            let zz = b;
            while (zz < t - 1e-9) {
                const p = per * Math.exp(jit * rng.standard_normal());
                const lf = Math.min(Math.max(frac * (1.0 + 0.5 * jit * rng.standard_normal()), 0.08), 0.9);
                const z1 = Math.min(zz + p * (1.0 - lf), t);
                if (z1 > zz) fine.push([zz, z1, ...base, i]);
                const z2 = Math.min(z1 + p * lf, t);
                if (z2 > z1) fine.push([z1, z2, ...led, i]);
                zz = z2;
            }
        });
        this.fine = fine;
        this.z0 = -PAD_M;
        const n = Math.trunc(Math.ceil((this.top_m + 2.0 * PAD_M) / this.dz)) + 1;
        const zs = Float64Array.from({ length: n }, (_v, i) => this.z0 + i * this.dz);
        this.zs = zs;
        const bot = Float64Array.from(fine, (f) => f[0]);
        const nf = fine.length;
        this.K = new Float64Array(n);
        this.tan = new Float64Array(n);
        this.creep = new Float64Array(n);
        this.formation = new Int32Array(n);
        for (let i = 0; i < n; i++) {
            const zc = Math.min(Math.max(zs[i], 0.0), this.top_m - 1e-9);
            const k = Math.min(Math.max(RV.searchsorted(bot, zc, 'right') - 1, 0), nf - 1);
            this.K[i] = fine[k][2];
            this.tan[i] = fine[k][3];
            this.creep[i] = fine[k][4];
            this.formation[i] = k;
        }
        // R exactly at the samples: the run through every fine layer below, the end layers continuing past the ends
        const edges = Float64Array.from([...fine.map((f) => f[0]), fine[nf - 1][1]]);
        const inv = Float64Array.from(fine, (f) => 1.0 / f[3]);
        const cum = new Float64Array(nf + 1);
        for (let k = 0; k < nf; k++) cum[k + 1] = cum[k] + (edges[k + 1] - edges[k]) * inv[k];
        this.R = new Float64Array(n);
        for (let i = 0; i < n; i++) {
            const zc = Math.min(Math.max(zs[i], 0.0), this.top_m);
            const k = Math.min(Math.max(RV.searchsorted(edges, zc, 'right') - 1, 0), nf - 1);
            let r = cum[k] + (zc - edges[k]) * inv[k];
            r = r + (zs[i] < 0.0 ? zs[i] * inv[0] : 0.0) + (zs[i] > this.top_m ? (zs[i] - this.top_m) * inv[nf - 1] : 0.0);
            this.R[i] = r;
        }
    }

    // ------------------------------------------------------------------------ lookups (doubles, for a few values)
    _t(zs) { return Math.min(Math.max((Number(zs) - this.z0) / this.dz, 0.0), this.zs.length - 1.0); }

    _lerp(table, zs) {
        const one = (z) => {
            const t = this._t(z);
            const i0 = Math.floor(t);
            const i1 = Math.min(i0 + 1, table.length - 1);
            const f = t - i0;
            return table[i0] * (1.0 - f) + table[i1] * f;
        };
        return typeof zs === 'number' ? one(zs) : Float64Array.from(zs, one);
    }

    kAt(zs) { return this._lerp(this.K, zs); }
    tanAt(zs) { return this._lerp(this.tan, zs); }
    creepAt(zs) { return this._lerp(this.creep, zs); }

    /** R(zs), linearly continued past the table (as the kernel). */
    runAt(zs) {
        const one = (z) => {
            const t = (Number(z) - this.z0) / this.dz;
            const n = this.R.length;
            if (t <= 0) return this.R[0] + t * (this.R[1] - this.R[0]);
            if (t >= n - 1) return this.R[n - 1] + (t - (n - 1)) * (this.R[n - 1] - this.R[n - 2]);
            return this._lerp(this.R, z);
        };
        return typeof zs === 'number' ? one(zs) : Float64Array.from(zs, one);
    }

    /** The formation's name at a stratigraphic height. */
    layerAt(zs) {
        const z = Math.min(Math.max(Number(zs), 0.0), this.top_m - 1e-9);
        for (const d of this.layers) if (d.base_m <= z && z < d.top_m) return d.name;
        return this.layers[this.layers.length - 1].name;
    }

    _find(name) {
        for (const d of this.layers) {
            if (d.name === name || String(d.name).toLowerCase().startsWith(String(name).toLowerCase())) return d;
        }
        throw new KeyError(`column '${this.name}' has no layer '${name}'; layers: ${JSON.stringify(this.layers.map((d) => d.name))}`);
    }

    baseOf(name) { return this._find(name).base_m; }
    topOf(name) { return this._find(name).top_m; }

    /** The design's form, bottom to top from zs = 0: [[thickness_m, K_factor, Sc_deg, colour_id, name], ...]. */
    formations() { return this.layers.map((d) => [d.thickness_m, d.K_factor, d.Sc_deg, d.colour, d.name]); }

    /** (1, n, 4) float32, row-major: tan, creep factor, R, K factor per step (strata_cell, strata_threshold). */
    tableTexture() {
        const n = this.R.length;
        const t = new Float32Array(4 * n);
        for (let i = 0; i < n; i++) t.set([this.tan[i], this.creep[i], this.R[i], this.K[i]], 4 * i);
        return t;
    }

    describe() {
        const lines = [`column ${this.name}: ${pyFormat(this.top_m, 'g')} m, ${this.layers.length} formations, ${this.fine.length} beds`];
        for (const d of [...this.layers].reverse()) {
            lines.push(`  ${pyFormat(d.top_m, '.1f').padStart(7)} m  ${String(d.name).padEnd(36)} ` +
                `${pyFormat(d.thickness_m, '.1f').padStart(6)} m  K x${pyFormat(d.K_factor, 'g').padEnd(5)} ` +
                `${pyFormat(d.Sc_deg, '.0f').padStart(4)} deg  creep ${pyFormat(d.creep, '.2f')}` + (d.beds ? '  (ledges)' : ''));
        }
        return lines.join('\n');
    }

    toString() { return `Column('${this.name}', ${pyFormat(this.top_m, 'g')} m, ${this.layers.length} formations)`; }
}
Column.prototype.k_at = Column.prototype.kAt;
Column.prototype.tan_at = Column.prototype.tanAt;
Column.prototype.creep_at = Column.prototype.creepAt;
Column.prototype.run_at = Column.prototype.runAt;
Column.prototype.layer_at = Column.prototype.layerAt;
Column.prototype.base_of = Column.prototype.baseOf;
Column.prototype.top_of = Column.prototype.topOf;
Column.prototype.table_texture = Column.prototype.tableTexture;

export const _COLUMN_CACHE = new Map();

/** A Column from a COLUMNS name, a list of layers (bottom to top), { name, layers }, or a Column (cached per spec). */
export function column(spec, dz = DZ, seed = 0) {
    if (spec instanceof Column) return spec;
    let name, layers;
    if (spec !== null && typeof spec === 'object' && !Array.isArray(spec) && has(spec, 'layers')) {
        name = spec.name ?? 'custom';
        layers = spec.layers;
    } else if (typeof spec === 'string') {
        if (!has(COLUMNS, spec)) {
            const near = closeMatches(spec, Object.keys(COLUMNS), 3, 0.4);
            throw new KeyError(`no column '${spec}'` + (near.length ? `; nearest: ${near.join(', ')}` :
                `; columns: ${Object.keys(COLUMNS).sort().join(', ')}`));
        }
        name = spec;
        layers = COLUMNS[spec];
    } else {
        name = 'custom';
        layers = spec;
    }
    const key = `${JSON.stringify(layers)}|${Number(dz)}|${Math.trunc(seed)}|${name}`;
    if (!_COLUMN_CACHE.has(key)) _COLUMN_CACHE.set(key, new Column(layers, name, dz, seed));
    return _COLUMN_CACHE.get(key);
}


// ======================================================================================= where the beds sit ===

export const STRATA_DEFAULTS = Object.freeze({ column: 'colorado_plateau', zs0_m: 0.0, dip_deg: 0.0, azimuth_deg: 0.0,
    warp: Object.freeze([]), faults: Object.freeze([]), fold: null, dz_m: DZ, seed: 0 });

export function strataSpec(params) {
    const d = { ...STRATA_DEFAULTS };
    for (const [k, v] of Object.entries(params ?? {})) if (has(STRATA_DEFAULTS, k)) d[k] = v;
    return d;
}

const kernelOf = (R, name) => HS.kernelOf(R, name);
const IMAGE_DUMMIES = new WeakMap();
// a runner's own 1 x 1 stand-ins for images (core/grid.js dummies() are bound as samplers; a field may not be both)
function imageDummies(R) {
    let d = IMAGE_DUMMIES.get(R);
    if (!d) {
        d = { fa: R.field(1, 1, 1), fb: R.field(1, 1, 1), ua: R.field(1, 1, 1, null, 'u32'), ub: R.field(1, 1, 1, null, 'u32') };
        IMAGE_DUMMIES.set(R, d);
    }
    return d;
}

// the value at the level's first cell centre of a + b x + c y (x, y world metres), and its steps per column and row
function linear(level, a, b, c) {
    const xc = level.x0 + 0.5 * level.cell, yc = level.y0 + 0.5 * level.cell;
    return [a + b * xc + c * yc, b * level.cell, c * level.cell];
}

/** zoff = h - zs on a level's cells (strata.py offset): -zs0 + tan(dip) (x cos az + y sin az) + warp - throws +
 * fold. A new r32f field. The warps' noise is dispatched in strata.py's order (world_noise_field, one per warp). */
export function offset(spec, level, seed, R) {
    const sp = strataSpec(spec);
    const D = Gd.dummies(R);
    const az = Number(sp.azimuth_deg) * DEG;
    const td = Math.tan(Number(sp.dip_deg) * DEG);
    const xc = level.x0 + 0.5 * level.cell, yc = level.y0 + 0.5 * level.cell;
    const plane = [-Number(sp.zs0_m) + td * (xc * Math.cos(az) + yc * Math.sin(az)), td * (level.cell * Math.cos(az)),
        td * (level.cell * Math.sin(az))];
    const s = Math.trunc(seed) + Math.trunc(Number(sp.seed ?? 0));
    const warps = [];
    (sp.warp ?? []).forEach(([wl, amp], k) => {
        if (Number(amp) === 0.0) return;
        warps.push([FL.field({ kind: 'fbm', wavelength_m: Number(wl), octaves: 3, seed: 501 + k }, level, s, R), 3.0 * Number(amp)]);
    });
    let out = null;
    const step = (mode, un, w = []) => {
        const next = R.field(level.n, level.n, 1);
        const ws = [0, 1, 2, 3].map((i) => (w[i] ? w[i][0] : D.f1));
        R.run(kernelOf(R, 'strata/offset'), { prev: out ?? D.f1, w0: ws[0], w1: ws[1], w2: ws[2], w3: ws[3] }, { outZ: next },
            { uMode: mode, uW: [0, 1, 2, 3].map((i) => (w[i] ? w[i][1] : 0.0)), uP: un.P ?? [0, 0, 0], uF: un.F ?? [1, 0] });
        if (out) out.destroy();
        out = next;
    };
    step(0, { P: plane }, warps.slice(0, 4));
    for (let i = 4; i < warps.length; i += 4) step(1, {}, warps.slice(i, i + 4));
    for (const [f] of warps) f.destroy();
    for (const f of sp.faults ?? []) {
        const [ax, ay] = (f.at ?? [0.0, 0.0]).map(Number);
        const st = Number(f.strike_deg ?? 0.0) * DEG;
        const ux = Math.sin(st), uy = Math.cos(st);
        const sg = (f.down ?? 'left') === 'right' ? -1.0 : 1.0;
        const lin = linear(level, sg * (ax * uy - ay * ux), sg * -uy, sg * ux);
        step(2, { P: lin, F: [Math.max(Number(f.width_m ?? 20.0), 1e-6), Number(f.throw_m ?? 0.0)] });
    }
    const fd = sp.fold;
    if (fd && Object.keys(fd).length) {
        const [ax, ay] = (fd.through ?? [0.0, 0.0]).map(Number);
        const a = Number(fd.axis_deg ?? 0.0) * DEG;
        const lin = linear(level, -(ax * Math.cos(a)) + ay * Math.sin(a), Math.cos(a), -Math.sin(a));
        step(3, { P: lin, F: [Math.max(Number(fd.half_width_m ?? 4000.0), 1.0), Number(fd.rise_m ?? 0.0)] });
    }
    return out;
}

/** The stratigraphic height h - zoff of a level (strata.py zs_field): a new r32f field. */
export function zsField(h, spec, level, seed, R) {
    const zoff = offset(spec, level, seed, R);
    const zs = finalFields(R, h, zoff, null, null, null, level, null);
    zoff.destroy();
    return zs;
}

// final.wgsl: zs (mode 0), or zs, K col.k_at(zs) and col.tan_at(zs) / (Q facies) (mode 1, given the column's table)
function finalFields(R, h, zoff, kin, par, col, level, fac) {
    const D = Gd.dummies(R);
    const n = level.n;
    const zs = R.field(n, n, 1);
    const im = imageDummies(R);
    if (!col) {
        R.run(kernelOf(R, 'strata/final'), { h, zoff, kin: D.f1, par: D.f1, tab: D.f1 }, { outZ: zs, outK: im.fa, outS: im.fb },
            { uMode: 0, uZ0: 0.0, uDz: 1.0, uN: 1, uLv: [0, 0, 1], uFac: FACIES_OFF });
        return zs;
    }
    const tab = R.field(1, col.R.length, 4, col.tableTexture());
    const K = R.field(n, n, 1), Sc = R.field(n, n, 1);
    R.run(kernelOf(R, 'strata/final'), { h, zoff, kin, par, tab }, { outZ: zs, outK: K, outS: Sc },
        { uMode: 1, uZ0: col.z0, uDz: col.dz, uN: col.R.length, uLv: [level.x0, level.y0, level.cell], uFac: fac ?? FACIES_OFF });
    tab.destroy();
    return { zs, K, Sc };
}


// ================================================================================================ the facies ===

export const FACIES_OFF = Object.freeze([0.0, 1.0, 1.0, 0.0]);
export const FACIES_DEFAULTS = Object.freeze({ strength: 0.5, scale_m: 300.0, scale_z_m: 40.0, weather: 0.5, seed: 0 });

/** [the threshold's facies, the weathering's facies] as the kernels' uniforms (strength, L, Lz, seed) from a
 * 'strata_fluvial' stage's `facies` dict (null: both FACIES_OFF). The same noise drives both. */
export function faciesSpec(spec, seed = 0) {
    if (!spec || !Object.keys(spec).length) return [FACIES_OFF, FACIES_OFF];
    const p = { ...FACIES_DEFAULTS, ...spec };
    const v = Math.trunc(seed) * 7 + Math.trunc(Number(p.seed)) + 9001;
    const sd = ((v % 65536) + 65536) % 65536;
    const L = Number(p.scale_m), Lz = Number(p.scale_z_m);
    return [[Number(p.strength), L, Lz, sd], [Number(p.weather), L, Lz, sd]];
}


// =============================================================================================== the driver ===

/** The column's table (tan, creep, R, K factor) with the weathering's factor in its fourth channel (what
 * strata_weather reads; route_incise reads the K table on its own): the K factor, or K^kExp where it is under 1.
 * A Float32Array of (1, n, 4). */
export function weatherTable(col, kExp = 1.0) {
    const t = col.tableTexture();
    if (Number(kExp) !== 1.0) {
        for (let i = 3; i < t.length; i += 4) {
            const k = t[i];
            if (k < 1.0) t[i] = Math.fround(Math.max(k, 0.0) ** Number(kExp));
        }
    }
    return t;
}

/** FluvialRun (solvers/fluvial.js) in layered rock (strata.py StrataRun): route_incise with the column's K(zs); creep
 * through strata_cell + strata_creep; the threshold as strata_threshold's composite excess, then threshold.wgsl's
 * isotropic exchange; the weathering; the lock as the stock driver's. GPU fields throughout. */
export class StrataRun extends FL.FluvialRun {
    constructor(R, cell, fields, par, pins, col, zoff, lockH0 = null, lockB = 2, reposeTan = 0.67, weather = null,
        lv = [0.0, 0.0, 1.0], facies = FACIES_OFF, faciesW = FACIES_OFF, weatherKExp = 1.0) {
        const column = { k_factor: Float32Array.from(col.K), zoff, z0: col.z0, dz: col.dz };
        super(R, cell, fields, par, pins, FL.PINNED, column, lockH0, lockB);
        this.column = col;
        this.ctab = R.field(1, col.R.length, 4, weatherTable(col, weatherKExp));
        this.tcol = [Number(col.z0), Number(col.dz), col.R.length];
        this.C = R.field(this.shape[0], this.shape[1], 2);
        this.phiS = R.field(this.shape[0], this.shape[1], 1);
        this.repose = Number(reposeTan);
        // weathering: [rock rate W m/yr, tan of the slope it applies at, the stage's K0, the loose cover's rate m/yr,
        // the drainage-area boost, the slope term's cap, [the boost's slope ramp: tan lo, tan hi]] or null
        this.weather = weather && (Number(weather[0]) > 0 || Number(weather[3]) > 0) ? weather : null;
        this.lv = lv.map(Number);
        this.facies = facies.map(Number);
        this.facies_w = faciesW.map(Number);
        for (const name of ['strata_weather', 'strata_threshold', 'threshold', 'strata_cell', 'strata_creep']) {
            this.k[name] = HS.kernelOf(R, name);
        }
    }

    weatherPass(dt) {
        if (this.weather === null) return;
        const [W, s0, k0, wl, ac, sat, [as0, as1]] = this.weather;
        const [z0, dz, nt] = this.tcol;
        this.R.run(this.k.strata_weather, { st: this.S.src, zoff: this.zoff, ctab: this.ctab, par: this.P, pin: this.Q,
            mk: this.M.src }, { outS: this.S.dst, outM: this.M.dst },
        { uDx: this.cell, uDt: dt, uW: W, uS0: s0, uSat: sat, uK0: k0, uWl: wl, uAc: ac, uAs0: as0, uAs1: as1, uTZ0: z0,
            uTDz: dz, uTN: nt, uLv: this.lv, uFacW: this.facies_w, uBound: this.bound });
        this.S.swap();
        this.M.swap();
    }

    /** New pins ({ pin_w, pin_h, A_in, qs_in } fields): the pack is made from them (they are not kept). */
    setPins(pins) {
        const old = this.Q;
        this.Q = HS.pinsPack(this.R, pins);
        if (old && !old.destroyed) old.destroy();
    }

    threshold(iters, rate) {
        const R = this.R, S = this.S, M = this.M, b = this.bound;
        const [z0, dz, nt] = this.tcol;
        for (let i = 0; i < iters; i++) {
            R.run(this.k.strata_threshold, { st: S.src, zoff: this.zoff, mk: M.src, rtab: this.ctab, par: this.P },
                { outP: this.phiS }, { uDx: this.cell, uRZ0: z0, uRDz: dz, uRN: nt, uRepose: this.repose, uLv: this.lv,
                    uFac: this.facies, uBound: b });
            R.run(this.k.threshold, { st: S.src, par: this.P, pin: this.Q, mk: M.src, phiT: this.phiS },
                { outS: S.dst, outM: M.dst }, { uDx: this.cell, uRate: rate, uLoose: 0, uIso: 1, uBound: b });
            S.swap();
            M.swap();
        }
    }

    creep(dt, D, nSub, cap) {
        const R = this.R, S = this.S, M = this.M, b = this.bound;
        const [z0, dz, nt] = this.tcol;
        R.run(this.k.strata_cell, { st: S.src, zoff: this.zoff, ctab: this.ctab }, { outC: this.C }, { uTZ0: z0, uTDz: dz, uTN: nt });
        R.run(this.k.h_keep, { st: S.src }, { outH: this.W }, {});
        for (let i = 0; i < nSub; i++) {
            R.run(this.k.strata_creep, { st: S.src, cell: this.C, pin: this.Q }, { outS: S.dst },
                { uDx: this.cell, uDtSub: dt / nSub, uD: D, uCap: cap, uBound: b });
            S.swap();
        }
        R.run(this.k.creep_layers, { st: S.src, h0: this.W, mk: M.src }, { outM: M.dst }, {});
        M.swap();
    }

    lockPass(lockGain = 1.0) {
        if (this.lock === null) return;
        const R = this.R, S = this.S, M = this.M, K = this.k;
        const [phases, Rf, stage1] = this.lock;
        const [off, tgt] = phases[this.steps % phases.length];
        if (stage1 !== null) {
            const [b1, zero, R1] = stage1;
            R.run(K.lock_restrict, { st: S.src, tgt: zero }, { outR: R1 }, { uB: b1, uOff: [0, 0] });
            R.run(K.lock_restrict, { st: R1, tgt }, { outR: Rf },
                { uB: Math.floor(this.lockB / b1), uOff: [Math.floor(off[0] / b1), Math.floor(off[1] / b1)] });
        } else {
            R.run(K.lock_restrict, { st: S.src, tgt }, { outR: Rf }, { uB: this.lockB, uOff: off });
        }
        R.run(K.lock_apply, { st: S.src, res: Rf, pin: this.Q, mk: M.src }, { outS: S.dst, outM: M.dst },
            { uGain: lockGain, uB: this.lockB, uOff: off });
        S.swap();
        M.swap();
    }

    step(dt, D, nSub, iters, rate, cap, m = 0.5, nexp = 1.0, p = 1.0, lockGain = 1.0, slope = 1, _iso = 1,
        pitFill = 1, pitEps = 1e-3) {
        const R = this.R, S = this.S, M = this.M, cell = this.cell, b = this.bound, K = this.k;
        R.run(K.flow_weights, { st: S.src }, { outW: this.W }, { uDx: cell, uP: p, uBound: b });
        const [z0, dz, nc] = this.col;
        R.run(K.route_incise, { st: S.src, wsumT: this.W, par: this.P, pin: this.Q, mk: M.src, kcol: this.kcol, zoff: this.zoff },
            { outS: S.dst, outM: M.dst },
            { uDx: cell, uDt: dt, uM: m, uN: nexp, uP: p, uColZ0: z0, uColDz: dz, uColN: nc, uSlope: Math.trunc(slope),
                uPitFill: Math.trunc(pitFill), uPitEps: pitEps, uBound: b });
        S.swap();
        M.swap();
        this.weatherPass(dt);
        if (D > 0 && nSub > 0) this.creep(dt, D, nSub, cap);
        this.threshold(iters, rate);
        this.lockPass(lockGain);
        this.steps += 1;
    }

    destroy() {
        super.destroy();
        for (const f of [this.ctab, this.C, this.phiS]) if (f && !f.destroyed) f.destroy();
    }
}
StrataRun.prototype.weather_pass = StrataRun.prototype.weatherPass;
StrataRun.prototype.set_pins = StrataRun.prototype.setPins;
StrataRun.prototype.lock_pass = StrataRun.prototype.lockPass;


// ================================================================================================== helpers ===

/** The share of the main window's cells (on `level`) whose stratigraphic height is at or above capZs (strata.py
 * caprock_fraction; h: a field whose channel 0 is the height). One readback. */
export async function caprockFraction(h, zoff, level, main, capZs, R) {
    const [j0, j1, i0, i1] = RUN.mainWindow(level, main);
    const f = R.field(level.n, level.n, 1);
    R.run(kernelOf(R, 'strata/caprock'), { st: h, zoff }, { outF: f }, { uWin: [j0, j1, i0, i1], uCap: Number(capZs) });
    const c = (await prims(R).stats(f)).nonzero;
    f.destroy();
    return c / ((j1 - j0) * (i1 - i0));
}

/** Fill every closed depression of a level's surface that does not touch `keep` (the river's channel, a field) with
 * sediment, in place (h and deposit; the bed stays), never within `hold` cells of the edge (strata.py
 * fill_dry_basins). Returns the cells filled. */
export async function fillDryBasins(fields, keep = null, hold = 0, R = null) {
    R = R ?? fields.h.runner;
    const D = Gd.dummies(R), im = imageDummies(R), P = prims(R);
    const h = fields.h, n = h.h;
    const { filled } = await HY.fillDepressions(h);
    const mask = R.field(n, n, 1, null, 'u32');
    const k = kernelOf(R, 'strata/dry');
    const un = { uThr: f32AtOrBelow(1e-4), uHold: Math.trunc(hold), uHasDep: 'deposit' in fields ? 1 : 0 };
    R.run(k, { h, filled, lab: D.u1, chan: D.f1, dep: D.f1 }, { outM: mask, kept: im.ua, outH: im.fa, outD: im.fb, cnt: im.ub },
        { ...un, uMode: 0 });
    const { labels, count } = await P.label(mask);
    mask.destroy();
    if (!count) {
        labels.destroy();
        filled.destroy();
        return 0;
    }
    const kept = R.field(1, count + 1, 1, null, 'u32');
    if (keep) {
        R.run(k, { h, filled, lab: labels, chan: keep, dep: D.f1 }, { outM: im.ua, kept, outH: im.fa, outD: im.fb, cnt: im.ub },
            { ...un, uMode: 1 });
    }
    const oh = R.field(n, n, 1), od = R.field(n, n, 1), cnt = R.field(1, 2, 1, null, 'u32');
    R.run(k, { h, filled, lab: labels, chan: D.f1, dep: 'deposit' in fields ? fields.deposit : D.f1 },
        { outM: im.ua, kept, outH: oh, outD: od, cnt }, { ...un, uMode: 2 });
    const [c] = await R.readAll([cnt]);
    for (const f of [labels, filled, kept, cnt]) f.destroy();
    if (!c[0]) {
        oh.destroy();
        od.destroy();
        return 0;
    }
    fields.h = oh;
    fields.deposit = od;
    return c[0];
}

function _strataOf(params, ctx) {
    const spec = (params ?? {}).strata || (ctx ? ctx.shared.strata : null);
    if (spec === null || spec === undefined) {
        throw new ValueError("no strata column: put a 'strata' stage before this one (or give params.strata)");
    }
    return strataSpec(spec);
}

/** Joint-guided weakness, 0..1 on a level's cells (strata.py joint_field; a new r32f field): for each set a Gaussian
 * ridge along every line, broken into segments; the sets combine by max. */
export function jointField(level, sets, seed, R) {
    const D = Gd.dummies(R);
    let out = null;
    (sets ?? []).forEach((js, k) => {
        const spacing = Math.max(Number(js.spacing_m ?? 500.0), 4.0 * level.cell);
        const a = Number(js.strike_deg ?? 0.0) * DEG;
        const lin = linear(level, 0.0, Math.cos(a) / spacing, -Math.sin(a) / spacing);
        const wig = Number(js.wiggle_m ?? 0.15 * spacing);
        const wf = wig ? FL.field({ kind: 'fbm', wavelength_m: 2.0 * spacing, octaves: 3, seed: 701 + 13 * k }, level, seed, R) : null;
        const w = Math.max(Number(js.width_m ?? 20.0), 1.5 * level.cell);
        const seg = FL.field({ kind: 'fbm', wavelength_m: Number(js.segment_m ?? 3.0 * spacing), octaves: 2, seed: 733 + 13 * k },
            level, seed, R);
        const next = R.field(level.n, level.n, 1);
        R.run(kernelOf(R, 'strata/joints'), { prev: out ?? D.f1, wig: wf ?? D.f1, seg }, { outJ: next },
            { uHas: [out ? 1 : 0, wf ? 1 : 0], uU: lin, uJ: [(3.0 * wig) / spacing, spacing, w, Number(js.strength ?? 1.0)] });
        for (const f of [out, wf, seg]) if (f) f.destroy();
        out = next;
    });
    return out ?? Gd.fill(R, [level.n, level.n], 0.0);
}

/** The rock mass's strength n (about N(0, 1), clipped at +-2.5) on a level's cells (strata.py rock_mass): fbm at each
 * of `scales` the level resolves (3 cells and up), every scale with the same weight. A new field, or null. */
export function rockMass(level, scales, seed, R) {
    const sc = (scales ?? []).map(Number);
    if (!sc.length) return null;
    const amp = 3.0 / Math.sqrt(sc.length);
    const D = Gd.dummies(R);
    let out = null;
    sc.forEach((wl, k) => {
        if (wl < 3.0 * level.cell) return;
        const f = FL.field({ kind: 'fbm', wavelength_m: wl, octaves: 2, seed: 811 + 7 * k }, level, seed, R);
        const next = R.field(level.n, level.n, 1);
        R.run(kernelOf(R, 'strata/acc'), { prev: out ?? D.f1, f }, { outA: next },
            { uMode: 0, uFirst: out ? 0 : 1, uW: amp, uClip: [0, 0] });
        if (out) out.destroy();
        f.destroy();
        out = next;
    });
    if (!out) return null;
    const c = R.field(level.n, level.n, 1);
    R.run(kernelOf(R, 'strata/acc'), { prev: out, f: D.f1 }, { outA: c }, { uMode: 1, uFirst: 0, uW: 0.0, uClip: [-2.5, 2.5] });
    out.destroy();
    return c;
}

export const CORES_DEFAULTS = Object.freeze({ spacing_m: 1800.0, radius_m: Object.freeze([200.0, 420.0]),
    elongation: Object.freeze([1.0, 2.2]), angles_deg: null, strength: 2.5, region_m: 40000.0, seed: 0, exponent: 4.0,
    wobble: 0.0 });

/** The strong cores' centres and shapes, world metres: [[x, y, a, b, angle_rad, strength], ...], blue noise (dart
 * throwing at spacing_m over a square region_m wide around the origin), the same on every level (strata.py
 * core_centres: numpy's Generator, core/np_random.js). */
export function coreCentres(spec, seed = 0) {
    const p = { ...CORES_DEFAULTS, ...(spec ?? {}) };
    const sp = Number(p.spacing_m);
    const half = 0.5 * Number(p.region_m);
    const rng = defaultRng((Math.trunc(seed) + Math.trunc(Number(p.seed))) * 7919 + 4243);
    const N = Math.trunc(25 * ((2 * half) / sp) ** 2);
    const cand = rng.uniform(-half, half, [N, 2]);
    const gcell = sp / Math.sqrt(2.0);
    const grid = new Map();
    const out = [];
    const [r0, r1] = p.radius_m.map(Number), [e0, e1] = p.elongation.map(Number);
    const angles = p.angles_deg;
    for (let c = 0; c < N; c++) {
        const x = cand[2 * c], y = cand[2 * c + 1];
        const gi = Math.floor(x / gcell), gj = Math.floor(y / gcell);
        let ok = true;
        for (const di of [-2, -1, 0, 1, 2]) {
            for (const dj of [-2, -1, 0, 1, 2]) {
                const q = grid.get(`${gi + di},${gj + dj}`);
                if (q !== undefined && (q[0] - x) ** 2 + (q[1] - y) ** 2 < sp * sp) {
                    ok = false;
                    break;
                }
            }
            if (!ok) break;
        }
        if (!ok) continue;
        grid.set(`${gi},${gj}`, [x, y]);
        const r = rng.uniform(r0, r1);
        const e = rng.uniform(e0, e1);
        let ang;
        if (angles && angles.length) {
            const pick = Number(angles[rng.integers(angles.length)]);
            ang = (pick + rng.uniform(-12.0, 12.0)) * DEG;
        } else {
            ang = rng.uniform(0.0, Math.PI);
        }
        out.push([x, y, r * Math.sqrt(e), r / Math.sqrt(e), ang, Number(p.strength) * rng.uniform(0.75, 1.25)]);
    }
    return out;
}

/** _box_noise's plane waves for one core (strata.py: numpy's Generator seeded per core): [[th, lam, phase] x 4]. */
export function boxWaves(wavelength, seed) {
    const rng = defaultRng(Math.trunc(seed));
    const out = [];
    for (let i = 0; i < 4; i++) {
        const th = rng.uniform(0.0, Math.PI);
        const lam = wavelength * rng.uniform(0.7, 1.4);
        const ph = rng.uniform(0.0, 2.0 * Math.PI);
        out.push([th, lam, ph]);
    }
    return out;
}

/** _box_noise(x, y, wavelength, seed) in doubles at a few points (the GPU evaluates it per cell in cores.wgsl). */
export function boxNoise(x, y, wavelength, seed) {
    const w = boxWaves(wavelength, seed);
    const one = (px, py) => w.reduce((s, [th, lam, ph]) => s + Math.sin((2.0 * Math.PI * (px * Math.cos(th) + py * Math.sin(th))) / lam + ph), 0.0) / 2.0;
    return Array.isArray(x) || ArrayBuffer.isView(x) ? Float64Array.from(x, (px, i) => one(px, y[i])) : one(x, y);
}

/** Strong cores of the rock mass on a level's cells (strata.py rock_cores; a new r32f field, or null without a spec):
 * each a rounded block of strength s, flat inside, its outline wobbling, written over its own box only. */
export function rockCores(level, spec, seed, R) {
    if (!spec || !Object.keys(spec).length) return null;
    const p = { ...CORES_DEFAULTS, ...spec };
    const pw = Math.max(Number(p.exponent), 1.0);
    const wob = Number(p.wobble);
    const ci = [], cf = [];
    const TWO_PI = 2.0 * Math.PI;
    coreCentres(spec, seed).forEach(([cx, cy, a, b, ang, s], k) => {
        const reach = 1.6 * (1.0 + wob) * Math.max(a, b);
        if (cx + reach < level.x0 || cx - reach > level.x0 + level.side || cy + reach < level.y0 || cy - reach > level.y0 + level.side) return;
        const i0 = Math.max(Math.trunc((cx - reach - level.x0) / level.cell), 0);
        const i1 = Math.min(Math.trunc((cx + reach - level.x0) / level.cell) + 1, level.n);
        const j0 = Math.max(Math.trunc((cy - reach - level.y0) / level.cell), 0);
        const j1 = Math.min(Math.trunc((cy + reach - level.y0) / level.cell) + 1, level.n);
        if (i1 <= i0 || j1 <= j0) return;
        const X0 = level.x0 + (i0 + 0.5) * level.cell, Y0 = level.y0 + (j0 + 0.5) * level.cell;
        ci.push(i0, i1, j0, j1);
        cf.push(X0 - cx, Y0 - cy, Math.sin(ang), Math.cos(ang), a, b, s, 0.0);
        const waves = wob > 0.0 ? boxWaves(0.7 * (a + b), Math.trunc(seed) * 131 + 977 * k + 5) : [];
        for (let w = 0; w < 4; w++) {
            if (!waves.length) { cf.push(0, 0, 0, 0); continue; }
            const [th, lam, ph] = waves[w];
            const c0 = (TWO_PI * (X0 * Math.cos(th) + Y0 * Math.sin(th))) / lam + ph;
            cf.push(c0 - TWO_PI * Math.round(c0 / TWO_PI), (TWO_PI * level.cell * Math.cos(th)) / lam,
                (TWO_PI * level.cell * Math.sin(th)) / lam, 0.0);
        }
    });
    const nc = ci.length / 4;
    const fi = R.field(1, Math.max(ci.length, 4), 1, Int32Array.from(ci.length ? ci : [0, 0, 0, 0]), 'i32');
    const ff = R.field(1, Math.max(6 * nc, 1), 4, Float32Array.from(cf.length ? cf : [0, 0, 0, 0]));
    const out = R.field(level.n, level.n, 1);
    R.run(kernelOf(R, 'strata/cores'), { ci: fi, cf: ff }, { outC: out }, { uN: nc, uCell: level.cell, uPw: pw, uWob: wob });
    fi.destroy();
    ff.destroy();
    return out;
}

/** Roughness in metres: [[wavelength_m, amp_m], ...] as fbm (amp the standard deviation), scales the level resolves
 * only (strata.py _noise_m). A new r32f field, or null where no scale contributes (numpy's zeros). */
export function noiseM(scales, level, seed, R, base) {
    const D = Gd.dummies(R);
    let out = null;
    (scales ?? []).forEach(([wl, amp], k) => {
        if (Number(amp) === 0.0 || Number(wl) < 3.0 * level.cell) return;
        const f = FL.field({ kind: 'fbm', wavelength_m: Number(wl), octaves: 4, seed: base + k }, level, seed, R);
        const next = R.field(level.n, level.n, 1);
        R.run(kernelOf(R, 'strata/acc'), { prev: out ?? D.f1, f }, { outA: next },
            { uMode: 0, uFirst: out ? 0 : 1, uW: 3.0 * Number(amp), uClip: [0, 0] });
        if (out) out.destroy();
        f.destroy();
        out = next;
    });
    return out;
}


// =================================================================================================== the ops ===

const runnerOf = (fields, ctx) => (ctx && ctx.device) || fields.h?.runner || fields.R;

/** Stage 'strata' (module doc): the column spec into ctx.shared.strata for the level's later stages, and zs.
 * params: column (a COLUMNS name or a list of layers), zs0_m, dip_deg, azimuth_deg, warp, faults, fold, dz_m, seed. */
export async function opStrata(fields, level, params, seed = 0, ctx = null) {
    ctx = await FL.asContext(ctx, fields, level);
    const R = runnerOf(fields, ctx);
    const sp = strataSpec(params);
    const col = column(sp.column, Number(sp.dz_m), Math.trunc(Number(sp.seed ?? 0)));
    ctx.shared.strata = sp;
    if ('h' in fields) fields.zs = zsField(fields.h, sp, level, seed, R);
    ctx.log(`[terrain.strata] column ${col.name} (${pyFormat(col.top_m, 'g')} m, ${col.layers.length} formations, ` +
        `${col.fine.length} beds), dip ${sp.dip_deg} deg toward ${sp.azimuth_deg} deg`);
    return fields;
}

export const PLATEAU_DEFAULTS = Object.freeze({ surface_zs_m: null, height_m: 0.0, follow_strata: true, follow_warp: true,
    tilt_deg: 0.0, tilt_azimuth_deg: 0.0, roughness: Object.freeze([[3000.0, 6.0], [600.0, 2.5], [120.0, 0.8]]), edge: null,
    edges: Object.freeze([]), roughness_low: 1.0, roughness_fade: 0.25 });

/** The start of 'plateau' on a level's cells (strata.py plateau_surface; a new r32f field): a structural surface at
 * surface_zs_m (following the beds' dip, fold, faults and, with follow_warp, their warp) or a plane at height_m tilted
 * tilt_deg, plus roughness and optional escarpments (`edge`, `edges`), the roughness faded on the low ground beyond an
 * edge's foot by roughness_low. The noise is dispatched in strata.py's order: the offset's warps, the roughness, each
 * edge's wiggle. */
export function plateauSurface(level, params, seed, R, strata = null) {
    const p = { ...PLATEAU_DEFAULTS, ...(params ?? {}) };
    const D = Gd.dummies(R), im = imageDummies(R);
    const n = level.n;
    const s = Math.trunc(seed) + Math.trunc(Number(p.seed ?? 0));
    let base;
    if (p.surface_zs_m !== null && p.surface_zs_m !== undefined && (p.follow_strata ?? true)) {
        if (!strata) throw new ValueError("stage 'plateau' with surface_zs_m needs the 'strata' stage before it");
        const sp = (p.follow_warp ?? true) ? strata : { ...strata, warp: [] };
        const zoff = offset(sp, level, seed, R);
        base = Gd.arith(R, 'affine', zoff, null, { amp: 1.0, off: Number(p.surface_zs_m) });
        zoff.destroy();
    } else {
        const az = Number(p.tilt_azimuth_deg ?? 0.0) * DEG;
        const t = Math.tan(Number(p.tilt_deg ?? 0.0) * DEG);
        base = R.field(n, n, 1);
        R.run(kernelOf(R, 'strata/offset'), { prev: D.f1, w0: D.f1, w1: D.f1, w2: D.f1, w3: D.f1 }, { outZ: base },
            { uMode: 0, uW: [0, 0, 0, 0], uP: linear(level, Number(p.height_m ?? 0.0), t * Math.cos(az), t * Math.sin(az)), uF: [1, 0] });
    }
    const rough = noiseM(p.roughness, level, s, R, 601);
    const edges = [...(p.edge ? [p.edge] : []), ...(p.edges ?? [])];
    const low = Number(p.roughness_low ?? 1.0);
    let keep = null;
    const drops = [];
    edges.forEach((e, k) => {
        const [ax, ay] = (e.through ?? [0.0, 0.0]).map(Number);
        const st = Number(e.strike_deg ?? 90.0) * DEG;
        const ux = Math.sin(st), uy = Math.cos(st);
        const wig = Number(e.wiggle_m ?? 0.0);
        const wf = wig ? FL.field({ kind: 'fbm', wavelength_m: Number(e.wiggle_wavelength_m ?? 2000.0), octaves: 4, seed: 641 + 7 * k },
            level, s, R) : null;
        const w = Math.max(Number(e.width_m ?? 200.0), 1e-6);
        const drop = R.field(n, n, 1), kept = R.field(n, n, 1);
        R.run(kernelOf(R, 'strata/plateau'), { keepIn: keep ?? D.f1, wig: wf ?? D.f1, base: D.f1, rough: D.f1 },
            { outD: drop, outK: kept },
            { uMode: 0, uHas: [keep ? 1 : 0, wf ? 1 : 0, 0, low !== 1.0 ? 1 : 0],
                uS: linear(level, -(ax * uy) + ay * ux, uy, -ux),
                uE: [3.0 * wig, w, Number(e.drop_m ?? 100.0), Number(p.roughness_fade ?? 0.25) * w] });
        if (wf) wf.destroy();
        if (keep) keep.destroy();
        keep = kept;
        drops.push(drop);
    });
    let h = R.field(n, n, 1);
    R.run(kernelOf(R, 'strata/plateau'), { keepIn: keep ?? D.f1, wig: D.f1, base, rough: rough ?? D.f1 }, { outD: h, outK: im.fa },
        { uMode: 1, uHas: [keep ? 1 : 0, 0, rough ? 1 : 0, low !== 1.0 ? 1 : 0], uS: [0, 0, 0], uE: [low, 1, 0, 0] });
    for (const f of [base, rough, keep]) if (f) f.destroy();
    for (const d of drops) {
        const next = R.field(n, n, 1);
        R.run(kernelOf(R, 'strata/acc'), { prev: h, f: d }, { outA: next }, { uMode: 0, uFirst: 0, uW: -1.0, uClip: [0, 0] });
        h.destroy();
        d.destroy();
        h = next;
    }
    return h;
}

/** Stage 'plateau' (plateauSurface): the start surface, on a fresh level only (a level that inherited one keeps it).
 * Writes h and bed (all rock), and zs. */
export async function opPlateau(fields, level, params, seed = 0, ctx = null) {
    ctx = await FL.asContext(ctx, fields, level);
    const R = runnerOf(fields, ctx);
    if (!ctx.fresh && 'h' in fields && (await prims(R).stats(fields.h)).nonzero > 0) return fields;
    const sp = ctx.shared.strata ?? null;
    const h = plateauSurface(level, params, seed, R, sp);
    const bed = R.like(h);
    R.copy(h, bed);
    fields.h = h;
    fields.bed = bed;
    if (sp) fields.zs = zsField(h, sp, level, seed, R);
    const st = await prims(R).stats(h);
    ctx.log(`[terrain.strata] plateau start on ${level.n}^2 @ ${pyFormat(level.cell, '.3g')} m: ${pyFormat(st.min, '.0f')}..` +
        `${pyFormat(st.max, '.0f')} m`);
    return fields;
}

export const FLUVIAL_DEFAULTS = Object.freeze({ U_m_per_yr: 0.0, threshold_iters: 3, threshold_rate: 0.12, repose_deg: 34.0,
    later: 'refine', later_frac: 0.25, pin_every: 8, caprock_zs_m: null, caprock_target: null, check_every: 40,
    roughness: 0.3, deposition: 0.5, weather_m_per_yr: 0.0, weather_slope_deg: 30.0, weather_sat: 1000.0,
    weather_loose: 2.0, weather_area: 0.0, weather_area_slope_deg: Object.freeze([20.0, 35.0]), weather_refine: 0.0,
    weather_loose_refine: 0.5, weather_k_exp: 1.0, joints: Object.freeze([]), joint_gain: 0.0, resist: 0.0, resist_run: 0.0,
    resist_noise: 1.0, resist_scales_m: Object.freeze([1400.0, 600.0]), edge_follow: true });

/** strata.py _q: the stage's value, else FLUVIAL_DEFAULTS', else fluvial.js's default. */
export function _q(params, key) {
    if (has(params, key) && params[key] !== null && params[key] !== undefined) return params[key];
    if (has(FLUVIAL_DEFAULTS, key)) return FLUVIAL_DEFAULTS[key];
    return FL._p(params, key);
}

/** Stage 'strata_fluvial' (module doc): the coarsest level's first pass grows the landform under the base-level fall;
 * its later passes, and every finer level, refine it under the low-pass lock with the channel at its final bed. */
export async function opStrataFluvial(fields, level, params, seed = 0, ctx = null) {
    ctx = await FL.asContext(ctx, fields, level);
    const R = runnerOf(fields, ctx);
    const D0 = Gd.dummies(R);
    const t0 = now();
    const lv = level;
    const n = lv.n;
    const cell = Number(lv.cell);
    const p = { ...(params ?? {}) };
    for (const k of ['roughness', 'deposition']) if (!has(p, k)) p[k] = FLUVIAL_DEFAULTS[k];
    const sp = _strataOf(p, ctx);
    const col = column(sp.column, Number(sp.dz_m), Math.trunc(Number(sp.seed ?? 0)));
    const s = Math.trunc(seed) + Math.trunc(Number(p.seed ?? 0));
    if (!('h' in fields)) throw new ValueError(`stage 'strata_fluvial' on ${lv}: no height yet (put a 'plateau' stage before it)`);
    const own = [];
    const zoff = offset(sp, lv, seed, R);
    own.push(zoff);
    const h = fields.h;
    const main = ctx.main;
    const mainCell = main ? Number(main.cell) : cell;
    const depth = ctx.depth;
    const first = ctx.role === 'grow' && ctx.fresh && (ctx.prepass === null || ctx.prepass === undefined || ctx.prepass === 0);
    const later = ctx.role === 'grow' && !first;
    const refine = ctx.role === 'refine' || (later && _q(p, 'later') === 'refine');

    // the inputs (world functions; the column's K(zs) and threshold come from the tables in the kernels)
    const rigid = await FL.seaFlat(fields, ctx, lv, R);
    if (rigid) own.push(rigid);
    const K0 = FL.erodibility(lv, p, s, R, { kFactor: 'K_factor' in fields ? fields.K_factor : null });
    own.push(K0);
    let J = null;
    if (FL.truthy(p.joints) && Number(_q(p, 'joint_gain')) > 0) {
        J = jointField(lv, p.joints, s, R);
        own.push(J);
    }
    // the rock mass (rock_mass): strong patches erode and weather slower and stand steeper
    let NZ = null, CO = null;
    if (Number(_q(p, 'resist')) > 0 || Number(_q(p, 'resist_run')) > 0) {
        NZ = rockMass(lv, _q(p, 'resist_scales_m'), s, R);
        CO = rockCores(lv, p.resist_cores, s, R);
        for (const f of [NZ, CO]) if (f) own.push(f);
    }
    const sod = p.sod;
    let SL = null;
    if (FL.truthy(sod) && refine && (lv.role === 'hero' || !(sod.hero_only ?? true))) {
        // the sod cover (the hero levels): grass holds gentle ground (strata.py's note)
        SL = Gd.slopeDeg(h, cell);
        own.push(SL);
    }
    const Kf = R.field(n, n, 1);
    const par = R.field(n, n, 4);
    own.push(Kf);
    R.run(kernelOf(R, 'strata/par'), { kin: K0, jw: J ?? D0.f1, nz: NZ ?? D0.f1, co: CO ?? D0.f1, sl: SL ?? D0.f1, rig: rigid ?? D0.f1 },
        { outP: par, outK: Kf },
        { uHas: [J ? 1 : 0, NZ ? 1 : 0, CO ? 1 : 0, SL ? 1 : 0], uRigid: rigid ? 1 : 0, uGain: Number(_q(p, 'joint_gain')),
            uResist: Number(_q(p, 'resist')), uResistRun: Number(_q(p, 'resist_run')), uNoise: Number(_q(p, 'resist_noise')),
            uSod: SL ? [Number(sod.below_deg ?? 10.0), Number(sod.above_deg ?? 22.0), Number(sod.k ?? 0.1)] : [0, 1, 1],
            uU: Number(_q(p, 'U_m_per_yr')), uG: Number(_q(p, 'deposition')) });

    // pins: the level's (edge or border band), and the river's channel
    const ownBase = ctx.pins === null || ctx.pins === undefined;
    const base0 = ownBase ? FL.edgePins(R, n, h, ctx.sea_level ?? null) : ctx.pins;
    let base = base0;
    const rv = ctx.shared.river;
    const chanCache = {};
    let pins, chan = null;
    if (rv instanceof RV.River) {
        // (on a child level the river_path stage already eased the channel into the parent's at the border band:
        // hold keeps that, since its weight is 1 on the channel there)
        const [pk, m] = await rv.pins(lv, base, first ? 0.0 : 1.0, { cache: chanCache, hold: ctx.role === 'refine' ? base.pin_w : null });
        pins = pk;
        chan = R.like(m);
        R.copy(m, chan);
    } else {
        pins = base;
    }

    const [Dc, spacing] = FL.diffusivity(p, cell, depth, mainCell);
    let dt, steps;
    if (ctx.role === 'refine') {
        dt = (Number(FL._p(p, 'dt_ref_yr')) * Math.max(cell, mainCell)) / FL.CELL_REF_M;
        steps = Math.trunc(Number(has(p, 'steps') ? p.steps : FL._p(p, 'refine_steps')));
    } else {
        dt = (Number(FL._p(p, 'dt_ref_yr')) * cell) / FL.CELL_REF_M;
        let dur;
        if (first) dur = Number(FL._p(p, 'age_myr')) * 1e6;
        else dur = Number(ctx.shared.strata_years ?? Number(FL._p(p, 'age_myr')) * 1e6) * Number(_q(p, 'later_frac'));
        steps = Math.trunc(Number(has(p, 'steps') ? p.steps : pyRound(dur / dt)));
    }
    steps = Math.min(Math.max(steps, Math.trunc(Number(FL._p(p, 'min_steps')))), Math.trunc(Number(FL._p(p, 'max_steps'))));
    const cap = Number(FL._p(p, 'creep_cap'));
    const [nSub, Dused] = FL.creepSubsteps(dt, cell, Dc, cap, Math.trunc(Number(FL._p(p, 'max_creep_sub'))));
    let lockH0 = null, lockB = 2, lockM = null;
    if (refine && FL.truthy(FL._p(p, 'lock'))) {
        let pcell, pdepth;
        if (ctx.role === 'refine') {
            const pi = ctx.plan && ctx.plan[ctx.index]?.parent !== null && ctx.plan[ctx.index]?.parent !== undefined
                ? ctx.plan[ctx.plan[ctx.index].parent] : null;
            pcell = pi ? Number(pi.cell) : 2.0 * cell;
            pdepth = pi?.depth ?? depth + 1;
        } else {
            pcell = 2.0 * cell;                                  // the previous coarse-to-fine pass
            pdepth = depth;
        }
        lockM = p.lock_m !== null && p.lock_m !== undefined ? Number(p.lock_m)
            : FL.LOCK_SCALE * FL.diffusivity(p, pcell, pdepth, mainCell)[1];
        lockB = FL.lockBlock(lockM, cell, n);
        lockH0 = h;
    }
    // weathering grows the landform (the walls' retreat); under the low-pass lock the rock's is scaled by
    // weather_refine and the loose cover's by weather_loose_refine (strata.py's note)
    const W0 = Number(_q(p, 'weather_m_per_yr'));
    const wf = refine ? Number(_q(p, 'weather_refine')) : 1.0;
    const wl = W0 * Number(_q(p, 'weather_loose')) * (refine ? Number(_q(p, 'weather_loose_refine')) : 1.0);
    const [aLo, aHi] = _q(p, 'weather_area_slope_deg').map((v) => Math.tan(Number(v) * DEG));
    const weather = [wf * W0, Math.tan(Number(_q(p, 'weather_slope_deg')) * DEG), Number(FL._p(p, 'K')), wl,
        Number(_q(p, 'weather_area')), Number(_q(p, 'weather_sat')), [aLo, aHi]];
    const [fac, facW] = faciesSpec(p.facies, s);
    const run = new StrataRun(R, cell, fields, par, pins, col, zoff, lockH0, lockB, Math.tan(Number(_q(p, 'repose_deg')) * DEG),
        weather, [lv.x0, lv.y0, lv.cell], fac, facW, Number(_q(p, 'weather_k_exp')));
    if (pins !== base) { pins.pin_w.destroy(); pins.pin_h.destroy(); }
    const iters = Math.trunc(Number(_q(p, 'threshold_iters')));
    const rate = Number(_q(p, 'threshold_rate'));
    const mexp = Number(FL._p(p, 'm')), nexp = Number(FL._p(p, 'n')), pexp = Number(FL._p(p, 'p'));
    const slopeMode = { dinf: 1, d8: 0 }[FL._p(p, 'slope')];
    const pit = FL.truthy(FL._p(p, 'fill_pits')) ? 1 : 0;
    const peps = Number(FL._p(p, 'pit_eps_m'));
    const pinEvery = Math.max(Math.trunc(Number(_q(p, 'pin_every'))), 1);
    const target = _q(p, 'caprock_target');
    const capZs = _q(p, 'caprock_zs_m');
    const check = Math.max(Math.trunc(Number(_q(p, 'check_every'))), 1);
    const falling = first && rv instanceof RV.River;
    // the coarsest level's outer ring follows the ground inside it down (never up) while the landform grows
    // (strata.py's note); badlands keep their prairies' edges as fixed base levels (edge_follow false)
    const coarsest = !ctx.plan || !ctx.plan.length || ctx.plan[ctx.index].parent === null || ctx.plan[ctx.index].parent === undefined;
    const follow = first && coarsest && FL.truthy(_q(p, 'edge_follow'));
    if (follow) {
        const ph = R.like(base0.pin_h);
        R.copy(base0.pin_h, ph);
        base = { ...base0, pin_h: ph };
        own.push(ph);
    }
    const history = [];
    let done = steps;
    let fNow = falling ? 0.0 : 1.0;
    for (let i = 0; i < steps; i++) {
        if ((falling || follow) && i % pinEvery === 0) {
            // the module doc: the ring is lowered by a kernel and the pins made again at every such step
            if (follow && i > 0) R.run(kernelOf(R, 'strata/ring'), { st: run.height() }, { ph: base.pin_h }, {});
            fNow = falling ? RV.scheduleAt(rv.schedule, i / Math.max(steps - 1, 1)) : 1.0;
            if (rv instanceof RV.River) {
                const [pk] = await rv.pins(lv, base, fNow, { cache: chanCache });
                run.setPins(pk);
                pk.pin_w.destroy();
                pk.pin_h.destroy();
            } else {
                run.setPins(base);
            }
        }
        run.step(dt, Dused, nSub, iters, rate, cap, mexp, nexp, pexp, 1.0, slopeMode, 1, pit, peps);
        if (first && target !== null && target !== undefined && capZs !== null && capZs !== undefined &&
            (i + 1) % check === 0 && fNow >= 0.999) {
            const frac = await caprockFraction(run.height(), zoff, lv, main, capZs, R);
            history.push([i + 1, FL.pyRoundN(frac, 4)]);
            if (frac <= Number(target)) {
                done = i + 1;
                break;
            }
        }
    }
    RV.releaseChannel(chanCache);
    const out = run.readback();
    if (first) ctx.shared.strata_years = done * dt;
    const capFrac = capZs !== null && capZs !== undefined ? await caprockFraction(out.h, zoff, lv, main, capZs, R) : null;
    for (const k of ['h', 'A', 'qs', 'wear', 'deposit', 'talus']) fields[k] = out[k];
    fields.bed = HS.ew(R, HS.EW.SUB, out.h, out.loose);
    out.loose.destroy();
    let dry = 0;
    if (FL.truthy(p.dry_basins)) {
        // the basins off the river fill with sand and alluvium (fill_dry_basins); the river's pools stay
        dry = await fillDryBasins(fields, chan, ctx.plan && ctx.plan.length && ctx.plan[ctx.index].parent !== null &&
            ctx.plan[ctx.index].parent !== undefined ? 2 : 0, R);
    }
    const fin = finalFields(R, fields.h, zoff, Kf, run.P, col, lv, fac);
    const ug = R.unpack(run.P, ['U', null, null, 'G']);
    fields.zs = fin.zs;
    fields.U = ug.U;
    // the layer's angle where the rock is strong or weak (the rock mass and the facies)
    fields.K = fin.K;
    fields.Sc = fin.Sc;
    fields.G = ug.G;
    if (chan) fields.river = chan;
    run.destroy();
    if (ownBase) for (const f of Object.values(base0)) if (!f.destroyed) f.destroy();
    for (const f of own) if (f && !f.destroyed) f.destroy();
    ctx.evolved = true;
    const rec = { level: String(lv), prepass: ctx.prepass ?? null, role: first ? 'first' : (refine ? 'refine' : 'evolve'),
        steps: done, dt_yr: FL.pyRoundN(dt, 2), years: pyRound(done * dt), D: Dused, spacing_m: FL.pyRoundN(spacing, 1),
        creep_sub: nSub, lock_block_cells: lockH0 !== null ? lockB : null, lock_m: lockM, caprock: history.slice(-4),
        dry_basin_cells: dry, seconds: FL.pyRoundN(now() - t0, 3) };
    if (capFrac !== null) rec.caprock_frac = FL.pyRoundN(capFrac, 4);
    (ctx.shared.fluvial_log ??= []).push(rec);
    ctx.log(`[terrain.strata] ${rec.role} ${n}^2 @ ${pyFormat(cell, '.3g')} m` +
        (ctx.prepass !== null && ctx.prepass !== undefined ? ` (pre-pass ${ctx.prepass})` : '') +
        `: ${done} steps x ${pyFormat(dt, '.0f')} yr, D ${pyFormat(Dused, '.3g')} (valleys ${pyFormat(spacing, '.0f')} m), creep x${nSub}` +
        (falling ? ', base level falling' : '') +
        (has(rec, 'caprock_frac') ? `, caprock ${pyFormat(rec.caprock_frac, '.3f')}` : '') +
        (lockH0 !== null ? `, locked above ${lockB} cells (${pyFormat(lockB * cell, '.0f')} m)` : '') + `, ${rec.seconds} s`);
    return fields;
}

opStrataFluvial.evolves = true;
opStrata.evolves = true;              // every coarse-to-fine pass: zs on each
for (const op of [opStrata, opPlateau, opStrataFluvial]) op.takesCtx = true;

export const OPS = { strata: opStrata, plateau: opPlateau, strata_fluvial: opStrataFluvial };

export {
    materialColumn as material_column, paletteFor as palette_for, defaultCreep as default_creep, strataSpec as strata_spec,
    zsField as zs_field, faciesSpec as facies_spec, weatherTable as weather_table, caprockFraction as caprock_fraction,
    fillDryBasins as fill_dry_basins, jointField as joint_field, rockMass as rock_mass, coreCentres as core_centres,
    rockCores as rock_cores, boxNoise as _box_noise, noiseM as _noise_m, opStrata as op_strata,
    plateauSurface as plateau_surface, opPlateau as op_plateau, opStrataFluvial as op_strata_fluvial,
};
