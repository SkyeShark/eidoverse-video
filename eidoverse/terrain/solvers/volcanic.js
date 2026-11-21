// Port of blender/eidoblend/terrain/solvers/volcanic.py at f90c6fc.
//
// Volcanoes for the new makeTerrain (design section 4.7): the analytic profiles, the surroundings a volcano grows in,
// its aging by the fluvial backbone, its lava flows and its lakes.
//
// Every shape is a function of world position (metres: x east, y north, heights up) and a seed, so a level of any
// cell size evaluates the same landform at its own cell centres. Azimuths are compass degrees (0 north, 90 east), as
// the aspect mask is.
//
// The shapes (volcanic.py's names; the per-cell evaluation is a kernel of kernels/volcanic/):
//     stratovolcano      the exponential cone (or Karatson's log + linear option), its summit crater (and a flat
//                        summit ring), azimuthal asymmetry, flank craters, parasitic cones and a sector-collapse breach
//                        (kernels/volcanic/strato.wgsl, then piles_on)
//     cinder_cone        a cinder cone at repose (Wood 1980 / Porter 1972), aged by linear creep on its own patch
//                        (kernels/volcanic/cone.wgsl, cone_eval.wgsl, pile.wgsl)
//     rift_cones, cinder_field   the cone plans (numpy's Generator: core/np_random.js, draw for draw)
//     caldera_collapse   a ring-fault collapse with a layered face over talus (kernels/volcanic/caldera.wgsl)
//     FUJI, CRATER_LAKE, SP_CRATER   the reference presets, measured from the reference DEMs (fujiSurface,
//                        craterLakeSurface: the presets' analytic surfaces, fuji_surface and crater_lake_surface)
//
// Stage ops (OPS; run.js calls op(fields, level, params, seed, ctx)):
//   constructional  'stratovolcano', 'cinder_cones', 'caldera_collapse' (impact.js adds 'impact_crater'): stamped
//                   once and sharp on every level they run on (stampAdd, or for cones the pile form: pilesOn)
//   setting         'volcano_setting', 'volcano_plain'
//   processes       'volcano_age', 'lava_flows', 'lava_rubble', 'cone_rills', 'caldera_lake', 'volcano_lakes'
//
// Where this differs from volcanic.py, and why (PORT_PLAN.md 2.4, 3.2: every per-cell step runs on the GPU; each is
// checked against the numpy function it replaces, tests/volcanoes_craters/):
//   - The shapes are evaluated per cell by the port's own kernels (kernels/volcanic/, kernels/impact/: numpy code moved
//     to the GPU, float32 in numpy's order of operations, positions taken from the shape's centre with the window's
//     offset in doubles). Their 1D inputs stay JavaScript in doubles, as numpy computes them: the azimuth tables
//     (azimuth_noise, scallop_outline, embayment_outline, polygon_factor: AzTables, uploaded once as float32 rows), the
//     plans over objects (rift_cones, cinder_field, lava_vents, ravines_of, wall_column), and the few points numpy
//     evaluates one by one (a parasitic cone's base and ground slope, a flank crater's depth: outerAt, cinderConeAt).
//   - stamp_add keeps _evaluate_grid's row blocks: piles_on takes the support's minimum (`need`) per block, so a
//     cone's pile can reach deeper in one block than in the next; the port takes the same minimum per block on the GPU
//     (kernels/volcanic/rect_min.wgsl, one readback per cone) and decides each block's extension in doubles.
//   - The stamp keys ('stamp_<op>_<8 hex>', field names that reach the saves) hash Python's json.dumps of the params.
//     JavaScript has one number type, so the keys a Python int holds in the recipes (INT_KEYS: count, seed, sides ...)
//     print as ints and every other number as a Python float; tests/volcanoes_craters/ checks the keys against the
//     field names of the Blender runs' dumps.
//   - _AGED_PATCHES and _FACE_TABLES are per-process memos here too (GPU fields; clearMemos() empties them, as the
//     floor protocol clears Blender's).
//   - Fields are core/gpu.js fields; the ops are async. A child level's border band is pulled to its parent by
//     kernels/volcanic/band_pull.wgsl (volcanic.py's _pull_band rounds once, run.py's twice: two kernels).
//   - lava_flows: the DOWNFLOW walkers run in JavaScript (lavaWalkers: their draws depend on how many walkers are alive
//     each step, PORT_PLAN.md 2.4) on the level's surface read back once per flow unit (float32, as the level holds
//     it), each walker's local slope (dh_rel) taken in doubles at the cells it visits; from numpy's own float64
//     heights their passage equals numpy's at every cell (tests/volcanoes_craters/plans_test.mjs). Inside the op the
//     walkers' ground is the port's float32 field where numpy's is float64 (h + total, blurred), so a walker's choice
//     between near-equal neighbours can differ: the flows match in class (the recipes' floor runs), not cell for cell.
//     To keep such choices rare, every height a flow compares is held relative to the ground at its vent (they enter
//     only as differences: the same arithmetic, in the digits float32 has).
//   - lava_surface's noise is numpy's standard normals drawn on the GPU (standardNormalGpu, kernels/volcanic/
//     normal.wgsl: PCG64 and the ziggurat, the draws numpy makes in its order; the attempts float32 cannot decide are
//     settled in doubles by core/np_random.js's own generator). A value is float32: numpy's draw within 4 float32 steps
//     (measured 2.6), the stream left where numpy leaves it. The ziggurat's tables are read from core/np_random.js's
//     source (constants it does not export). lava_surface is float32 throughout (its blurs are core/prims.js's): its
//     footprint, smoothstep(0.5 p_edge, 2 p_edge) of the blurred passage, carries the blur's float32 error times
//     1 / p_edge into the margins (within 2.3e-5 of range of numpy's on the plan fixtures, 1e-4 being the grade).
//   - caldera_collapse's and the impact crater's strength (Sc) is a step function of a cell's run u from the face's
//     foot (the layered face's layers); u is float32 here (about 1e-3 m off numpy's at 5 km), so a cell within that of
//     a layer boundary reads the other layer (tens of cells of 262,144). tests/volcanoes_craters/replay_test.mjs grades
//     them by runs with every position moved by up to 1e-6 of its distance.
//   - volcano_lakes' max_lakes keeps the largest qualifying depressions as numpy's argsort of where(lake, area, -1)
//     reversed keeps them; between depressions of exactly equal area numpy's order is its sort's (an introsort, not
//     stable), the port's the larger label first.
//   - Blender defect kept (reported, not fixed): op_lava_flows sets units = 1 when a first unit leaves no passage over
//     0.05, but its range(units) runs on and the next unit unpacks the missing axis (a TypeError); the port raises the
//     same TypeError there.

import { createHash } from 'node:crypto';
import * as Gd from '../core/grid.js';
import { ValueError, pyFormat, pyRepr, pyRound } from '../core/levels.js';
import { defaultRng } from '../core/np_random.js';
import { f32AtOrBelow, keyToFloat, prims } from '../core/prims.js';
import * as N from '../core/world_noise.js';
import * as FL from './fluvial.js';
import * as HS from './hillslope.js';

export const TAU = 2.0 * Math.PI;
export const BIG = 1.0e9;                        // an "absent" height for the smooth unions (never wins a min)
export const AZ_SAMPLES = 8192;
/** A closed table of azimuths: the last entry is the first (volcanic.py AZ_TABLE_ANGLES). */
export const AZ_TABLE_ANGLES = Float64Array.from({ length: AZ_SAMPLES + 1 }, (_, i) => i * (TAU / AZ_SAMPLES));
const DEG = Math.PI / 180.0, RAD2DEG = 180.0 / Math.PI;
const radians = (d) => d * DEG;                  // math.radians: x * (pi / 180)
const degrees = (r) => r * RAD2DEG;              // math.degrees / np.degrees: x * (180 / pi)
const num = (v, d) => (v === undefined || v === null ? d : Number(v));
const int = (v, d) => (v === undefined || v === null ? d : Math.trunc(Number(v)));
const has = (o, k) => o !== null && o !== undefined && Object.prototype.hasOwnProperty.call(o, k);
const isDict = (v) => v !== null && typeof v === 'object' && !Array.isArray(v);
function pop(o, k, d) {
    if (!has(o, k)) return d;
    const v = o[k];
    delete o[k];
    return v;
}


// ===================================================================================== Python's arithmetic ===

/** Python's truth value (None, False, 0, '', [] and {} are false). */
export const truthy = FL.truthy;

/** Python's round(x, n) on the exact decimal value (half to even). */
export const pyRoundN = FL.pyRoundN;

/** numpy's np.mod(a, b) for b > 0: fmod, then + b when the remainder is negative (exact but the one addition). */
export function npMod(a, b) {
    const m = a % b;
    if (m !== 0 && (m < 0) !== (b < 0)) return m + b;
    return m === 0 ? 0 : m;
}

/** numpy's pairwise summation of a float64 array (np.sum's add.reduce: the first item plus the pairwise sum of the
 * rest, blocks of 8 accumulators up to 128 items, halves above), so a sum of a few hundred numbers rounds as numpy's. */
export function npSum(a) {
    if (!a.length) return 0.0;
    return a[0] + pairwise(a, 1, a.length - 1);
}

function pairwise(a, start, n) {
    if (n < 8) {
        let res = 0.0;
        for (let i = 0; i < n; i++) res += a[start + i];
        return res;
    }
    if (n <= 128) {
        const r = [0, 1, 2, 3, 4, 5, 6, 7].map((j) => a[start + j]);
        let i = 8;
        for (; i < n - (n % 8); i += 8) for (let j = 0; j < 8; j++) r[j] += a[start + i + j];
        let res = ((r[0] + r[1]) + (r[2] + r[3])) + ((r[4] + r[5]) + (r[6] + r[7]));
        for (; i < n; i++) res += a[start + i];
        return res;
    }
    let n2 = Math.floor(n / 2);
    n2 -= n2 % 8;
    return pairwise(a, start, n2) + pairwise(a, start + n2, n - n2);
}

/** np.percentile / np.quantile (numpy 2.3.4, 'linear') of a short float64 list (a few points numpy evaluates one by
 * one: a cone's ring of 64 samples), with a scalar q: float64 throughout, as numpy computes float64 data. pct: q in
 * [0, 100] (divided by 100). */
export function npQuantile64(values, q, pct = true) {
    const a = Float64Array.from(values).sort();
    const n = a.length;
    const quant = pct ? q / 100 : q;
    const virt = (n - 1) * quant;
    let prev = Math.floor(virt), next = prev + 1;
    if (virt >= n - 1) prev = next = n - 1;
    const gamma = virt - Math.floor(virt);
    const x = a[prev], y = a[Math.min(next, n - 1)];
    const diff = y - x;
    let r = x + diff * gamma;
    if (gamma >= 0.5) r = y - diff * (1 - gamma);
    return r;
}

// json.dumps(v, sort_keys=True, default=str) as Python writes it for a recipe's params: the keys whose values are
// Python ints in the Blender recipes print as ints, every other number as a float's repr
export const INT_KEYS = Object.freeze(new Set(['count', 'seed', 'sides', 'scallops', 'sectors', 'bands', 'units',
    'walkers', 'steps', 'max_steps', 'min_steps', 'octaves', 'terraces', 'vent_lines', 'max_lakes', 'iterations',
    'supersample', 'salt', 'k', 'sector_harmonics']));

function jsonString(s) {
    let out = '"';
    for (let i = 0; i < s.length; i++) {
        const c = s.charCodeAt(i), ch = s[i];
        if (ch === '"') out += '\\"';
        else if (ch === '\\') out += '\\\\';
        else if (ch === '\n') out += '\\n';
        else if (ch === '\r') out += '\\r';
        else if (ch === '\t') out += '\\t';
        else if (c < 0x20 || c > 0x7e) out += '\\u' + c.toString(16).padStart(4, '0');
        else out += ch;
    }
    return out + '"';
}

/** Python's json.dumps(v, sort_keys=True, default=str) of a recipe's params (see INT_KEYS). */
export function pyJsonDumps(v, intKey = false) {
    if (v === null || v === undefined) return 'null';
    if (v === true) return 'true';
    if (v === false) return 'false';
    if (typeof v === 'number') {
        if (Number.isNaN(v)) return 'NaN';
        if (!Number.isFinite(v)) return v > 0 ? 'Infinity' : '-Infinity';
        return intKey && Number.isInteger(v) ? String(v) : pyRepr(v);
    }
    if (typeof v === 'string') return jsonString(v);
    if (Array.isArray(v) || ArrayBuffer.isView(v)) return '[' + Array.from(v, (x) => pyJsonDumps(x, intKey)).join(', ') + ']';
    const keys = Object.keys(v).filter((k) => v[k] !== undefined).sort();
    return '{' + keys.map((k) => `${jsonString(k)}: ${pyJsonDumps(v[k], INT_KEYS.has(k))}`).join(', ') + '}';
}

/** volcanic.py _stamp_key: 'stamp_<op>_' + the first 8 hex digits of the SHA-1 of the params' JSON. */
export function stampKey(op, params) {
    return `stamp_${op}_` + createHash('sha1').update(pyJsonDumps(params)).digest('hex').slice(0, 8);
}

/** np.random.default_rng([abs(int(seed)), int(salt)]) (volcanic.py _rng). */
export function rngOf(seed, salt) {
    return defaultRng([Math.abs(Math.trunc(Number(seed))), Math.trunc(Number(salt))]);
}

/** The low 32 bits of an integer (volcanic.py _u32 of np.int64(seed)), as an unsigned number. */
export function u32of(v) {
    return Number(BigInt.asUintN(32, BigInt(Math.trunc(Number(v)))));
}


// ========================================================================== world-space helpers (doubles) ===

/** (r, azimuth) of a world point about centre: metres, radians clockwise from north (volcanic.py polar). */
export function polar(x, y, centre) {
    const dx = x - Number(centre[0]), dy = y - Number(centre[1]);
    return [Math.hypot(dx, dy), Math.atan2(dx, dy)];
}

/** The unit vector (east, north) of a compass azimuth in degrees. */
export function compass(azimuthDeg) {
    const a = radians(azimuthDeg);
    return [Math.sin(a), Math.cos(a)];
}

export function smoothstep(e0, e1, v) {
    const t = Math.min(Math.max((v - e0) / (e1 - e0), 0.0), 1.0);
    return t * t * (3.0 - 2.0 * t);
}

export function smoothMin(a, b, k) {
    if (k <= 0) return Math.min(a, b);
    const h = Math.min(Math.max(0.5 + 0.5 * (b - a) / k, 0.0), 1.0);
    return b + (a - b) * h - k * h * (1.0 - h);
}

export const smoothMax = (a, b, k) => -smoothMin(-a, -b, k);

export function crestUnion(a, b, k) {
    if (k <= 0) return Math.min(a, b);
    const u = Math.min(Math.max((a - b) / k, -1.0), 1.0);
    return smoothMin(a, b, k) + 0.25 * k * (1.0 - u * u) ** 2;
}


// ============================================================================================ azimuth tables ===

const NOISE_TABLES = new Map();

/** azimuth_noise's table: sum over k of a_k cos(k az + phi_k), a_k ~ k^-decay at unit RMS, the phases drawn from
 * (seed, salt): AZ_SAMPLES + 1 doubles (closed), as numpy builds it. Memoised (a pure function of its arguments). */
export function azimuthNoiseTable(seed, salt, kMin = 1, kMax = 6, decay = 1.5) {
    const key = `${seed}|${salt}|${kMin}|${kMax}|${decay}`;
    let t = NOISE_TABLES.get(key);
    if (t) return t;
    const rng = rngOf(seed, salt);
    const ks = [];
    for (let k = Math.trunc(kMin); k <= Math.trunc(kMax); k++) ks.push(k);
    const amp = Float64Array.from(ks, (k) => k ** -Number(decay));
    const sq = Float64Array.from(amp, (a) => a * a);
    const norm = Math.sqrt(npSum(sq) / 2.0);
    for (let i = 0; i < amp.length; i++) amp[i] /= norm;
    const phase = ks.length ? rng.uniform(0.0, TAU, ks.length) : [];
    t = new Float64Array(AZ_SAMPLES + 1);
    for (let n = 0; n < ks.length; n++) {
        const k = ks[n], a = amp[n], p = phase[n];
        for (let i = 0; i <= AZ_SAMPLES; i++) t[i] += a * Math.cos(k * AZ_TABLE_ANGLES[i] + p);
    }
    if (NOISE_TABLES.size > 512) NOISE_TABLES.delete(NOISE_TABLES.keys().next().value);
    NOISE_TABLES.set(key, t);
    return t;
}

/** AzimuthSampler at one azimuth (radians): [i, f] (volcanic.py, in doubles). */
export function azSampler(az) {
    const u = npMod(az, TAU) * (AZ_SAMPLES / TAU);
    const i = Math.min(Math.floor(u), AZ_SAMPLES - 1);
    return [i, u - i];
}

/** A table's linear read at a sampler (or an azimuth). */
export function azRead(table, s) {
    const [i, f] = typeof s === 'number' ? azSampler(s) : s;
    const a = table[i];
    return a + (table[i + 1] - a) * f;
}

/** The azimuth tables a kernel reads (the field `azt`: one float32 row of AZ_SAMPLES + 1 per table). add(table)
 * gives a table's row (the same table twice: one row); field(R) uploads them once. */
export class AzTables {
    constructor() {
        this.rows = [];
        this.index = new Map();
        this._field = null;
        this._uploaded = 0;
    }

    add(table) {
        let r = this.index.get(table);
        if (r === undefined) {
            r = this.rows.length;
            this.rows.push(table);
            this.index.set(table, r);
        }
        return r;
    }

    // the rows as a field, uploaded again when rows were added since (the old buffer is released once the commands
    // that read it are sent: core/gpu.js release)
    field(R) {
        if (!this._field || this._uploaded !== this.rows.length) {
            this.destroy();
            const n = Math.max(this.rows.length, 1), w = AZ_SAMPLES + 1;
            const a = new Float32Array(n * w);
            this.rows.forEach((t, r) => a.set(t, r * w));
            this._field = R.field(n, w, 1, a);
            this._uploaded = this.rows.length;
        }
        return this._field;
    }

    destroy() {
        if (this._field && !this._field.destroyed) this._field.destroy();
        this._field = null;
    }
}


// ============================================================================== the stratovolcano cone (4.7) ===

/** The exponential cone's length scale: lambda = H / tan(upper slope) (design 4.7). */
export function coneDecayM(heightM, upperSlopeDeg) {
    return Number(heightM) / Math.tan(radians(upperSlopeDeg));
}

/** The exponential cone at r (doubles): H (e^{-(r - rc)/lambda} - e_foot) / (1 - e_foot), 0 beyond R. */
export function expCone(r, heightM, radiusM, decayM, craterRadiusM) {
    const rc = Number(craterRadiusM), R = Number(radiusM), lam = Number(decayM);
    const eFoot = Math.exp(-(R - rc) / lam);
    const z = Number(heightM) * (Math.exp(-(r - rc) / lam) - eFoot) / (1.0 - eFoot);
    return r < R ? z : 0.0;
}

/** The exponential cone's slope in degrees at r. */
export function expConeSlopeDeg(r, heightM, radiusM, decayM, craterRadiusM) {
    const rc = Number(craterRadiusM), R = Number(radiusM), lam = Number(decayM);
    const eFoot = Math.exp(-(R - rc) / lam);
    const t = Number(heightM) / lam * Math.exp(-(r - rc) / lam) / (1.0 - eFoot);
    return degrees(Math.atan(t));
}

/** Where the log + linear profile's straight upper flank meets its logarithmic lower flank (bisection, 80 steps). */
export function loglinearBreakM(heightM, radiusM, upperSlopeDeg, craterRadiusM) {
    const t = Math.tan(radians(upperSlopeDeg)), H = Number(heightM), R = Number(radiusM), rc = Number(craterRadiusM);
    if (H >= t * (R - rc)) {
        throw new ValueError(`loglinear cone: H ${pyFormat(H, '.0f')} m needs a straight cone steeper than ${pyRepr(Number(upperSlopeDeg))} ` +
            `degrees over R ${pyFormat(R, '.0f')} m (the most this slope reaches is ${pyFormat(t * (R - rc), '.0f')} m): lower H or the ` +
            'slope, or raise R');
    }
    const g = (rb) => t * (rb * (Math.log(R / rb) + 1.0) - rc) - H;
    let lo = rc, hi = R;
    if (g(lo) >= 0.0) return rc;
    for (let i = 0; i < 80; i++) {
        const mid = 0.5 * (lo + hi);
        if (g(mid) < 0.0) lo = mid;
        else hi = mid;
    }
    return 0.5 * (lo + hi);
}

/** The cone of `profile` as numbers a kernel reads and a function of r in doubles (volcanic.py _cone_function):
 * { kind (0 exp, 1 loglinear), b1, b2, b3, zb, sRim (the slope tangent at the rim), z(r) }. */
export function coneFunction(profile, heightM, radiusM, upperSlopeDeg, craterRadiusM) {
    const H = Number(heightM), R = Number(radiusM), rc = Number(craterRadiusM);
    if (profile === 'exp') {
        const lam = coneDecayM(H, upperSlopeDeg);
        const eFoot = Math.exp(-(R - rc) / lam);
        const sRim = Math.tan(radians(expConeSlopeDeg(rc, H, R, lam, rc)));
        return { kind: 0, b1: lam, b2: eFoot, b3: 0.0, zb: 0.0, sRim, z: (r) => expCone(r, H, R, lam, rc) };
    }
    if (profile === 'loglinear') {
        const t = Math.tan(radians(upperSlopeDeg));
        let rb = loglinearBreakM(H, R, upperSlopeDeg, rc);
        let A;
        if (rb <= rc) {
            A = H / Math.log(R / rc);
            rb = rc;
        } else {
            A = rb * t;
        }
        const zb = A * Math.log(R / rb);
        const z = (r) => (r < R ? (r < rb ? zb + t * (rb - r) : A * Math.log(R / Math.max(r, 1e-6))) : 0.0);
        return { kind: 1, b1: t, b2: rb, b3: A, zb, sRim: Math.tan(radians(upperSlopeDeg)), z };
    }
    throw new ValueError(`stratovolcano profile ${JSON.stringify(profile).replaceAll('"', "'")}: use 'exp' (the default, Fuji) or ` +
        "'loglinear' (straight upper flanks, Karatson C-type)");
}

/** Everything stratovolcano() needs, from its keyword arguments (the op's params with `cones` resolved): the cone,
 * the tables, the flank craters, the breach and the parasitic cones with their bases and ground slopes (outer() at
 * five points each, in doubles, as numpy evaluates them). */
export function stratoPlan(p) {
    const H = num(p.height_m, 3700.0), R = num(p.radius_m, 18000.0), up = num(p.upper_slope_deg, 33.0);
    const profile = p.profile ?? 'exp';
    const rc = p.crater_radius_m === undefined || p.crater_radius_m === null ? 0.03 * R : Number(p.crater_radius_m);
    const dc = p.crater_depth_m === undefined || p.crater_depth_m === null ? 0.4 * rc : Number(p.crater_depth_m);
    if (!(rc > 0.0 && rc < R)) {
        throw new ValueError(`stratovolcano: crater radius ${pyFormat(rc, '.0f')} m must lie between 0 and R ${pyFormat(R, '.0f')} m`);
    }
    const f = num(p.crater_floor_frac, 0.0);
    if (!(f >= 0.0 && f < 0.95)) throw new ValueError('stratovolcano: crater_floor_frac must be in [0, 0.95)');
    const cf = coneFunction(profile, H, R, up, rc);
    const centre = [num(p.centre?.[0], 0.0), num(p.centre?.[1], 0.0)];
    const rift = radians(num(p.rift_azimuth_deg, 0.0));
    const wSp = num(p.summit_platform_m, 0.0);
    const rt = rc + wSp;
    const seed = int(p.seed, 0);
    const el = num(p.elongation, 1.0), rn = num(p.radius_noise, 0.0), hn = num(p.height_noise, 0.0);
    const rnT = rn ? azimuthNoiseTable(seed, 11, 1, 4) : null;
    const hnT = hn ? azimuthNoiseTable(seed, 12, 1, 3) : null;
    const bowl = dc / (1.0 - f * f);
    const wCrest = p.crest_round_m === undefined || p.crest_round_m === null ? 0.05 * rc : Number(p.crest_round_m);
    const plan = { H, R, rc, dc, cf, centre, rift, wSp, rt, seed, el, rn, hn, rnT, hnT, f, bowl, wCrest,
        kCrest: wCrest * (2.0 * bowl / rc + cf.sRim), flankCraters: [], breach: null, cones: [], bases: [], slopes: [] };
    // outer() as it runs after the summit crater: volcanic.py's closure reads `w` when it is called, and by then w
    // holds the crest's rounding, not the summit platform (it decides only at r <= rt, never where it is asked here)
    const later = (x, y) => outerAt(plan, x, y, wCrest);
    for (const fc of p.flank_craters ?? []) {
        const at = [Number(fc.at[0]), Number(fc.at[1])];
        plan.flankCraters.push({ at, rad: Number(fc.radius_m), dep: Number(fc.depth_m), rim: num(fc.rim_m, 0.0),
            z0: later(at[0], at[1]), down: Math.atan2(at[0] - centre[0], at[1] - centre[1]) });
    }
    if (truthy(p.breach)) {
        const b = p.breach;
        const [ex, ey] = compass(Number(b.azimuth_deg));
        plan.breach = { ex, ey, width: Number(b.width_m), widening: num(b.widening, 0.35),
            floor: H - num(b.depth_m, 2.0 * dc), tFloor: Math.tan(radians(num(b.floor_slope_deg, 8.0))),
            tWall: Math.tan(radians(num(b.wall_deg, 35.0))) };
    }
    if (truthy(p.cones)) {
        // each parasitic cone a pile at repose set on the flank at its vent (piles_on)
        for (const c of p.cones) {
            const cx = Number(c.at[0]), cy = Number(c.at[1]), e = 5.0;
            const zz = [later(cx, cy), later(cx + e, cy), later(cx - e, cy), later(cx, cy + e), later(cx, cy - e)];
            plan.cones.push(c);
            plan.bases.push(zz[0]);
            plan.slopes.push(Math.hypot(zz[1] - zz[2], zz[3] - zz[4]) / (2.0 * e));
        }
    }
    return plan;
}

/** stratovolcano's outer() at one point in doubles (the flank with its azimuthal modulation; w: the value volcanic.py's
 * closure reads for the summit platform's test). */
export function outerAt(plan, x, y, w = plan.wSp) {
    const [r, az] = polar(x, y, plan.centre);
    const s = azSampler(az);
    const c = Math.cos(az - plan.rift);
    let stretch = 1.0 + (plan.el - 1.0) * (c * c - 0.5);
    if (plan.rn) stretch = stretch * (1.0 + plan.rn * azRead(plan.rnT, s));
    const hfac = plan.hn ? 1.0 + plan.hn * azRead(plan.hnT, s) : 1.0;
    let rf;
    if (w > 0.0) rf = r > plan.rt ? plan.rc + (r - plan.rt) / stretch : plan.rc;
    else rf = r > plan.rc ? plan.rc + (r - plan.rc) / stretch : r;
    return hfac * plan.cf.z(rf);
}

// the cone's numbers as the texels kernels/volcanic/strato.wgsl reads (prm) and its flank craters (fc), for a grid
function stratoTables(R, plan, grid, tabs) {
    const rnRow = plan.rnT ? tabs.add(plan.rnT) : 0, hnRow = plan.hnT ? tabs.add(plan.hnT) : 0;
    const b = plan.breach;
    const prm = new Float32Array(7 * 4);
    prm.set([plan.H, plan.R, plan.rc, plan.dc], 0);
    prm.set([plan.cf.kind, plan.cf.b1, plan.cf.b2, plan.cf.b3], 4);
    prm.set([plan.cf.zb, plan.el, plan.rift, plan.rn], 8);
    prm.set([plan.hn, rnRow, hnRow, plan.wSp], 12);
    prm.set([plan.rt, plan.f, plan.bowl, plan.kCrest], 16);
    if (b) {
        prm.set([1, b.ex, b.ey, b.width], 20);
        prm.set([b.widening, b.floor, b.tFloor, b.tWall], 24);
    }
    const nf = Math.max(plan.flankCraters.length, 1);
    const fc = new Float32Array(8 * nf);
    plan.flankCraters.forEach((c, k) => {
        fc.set([grid.ox - c.at[0], grid.oy - c.at[1], c.rad, c.dep], 8 * k);
        fc.set([c.rim, c.z0, c.down, 0.0], 8 * k + 4);
    });
    return { prm: R.field(1, 7, 4, prm), fc: R.field(1, 2 * nf, 4, fc) };
}


// ===================================================================================== cinder cones (4.7) ===

/** The concave toe's width for a cone of these ratios: L = 2 (Rb - rcr - H / tan(flank)); raises when no toe fits. */
export function cinderConeToeM(widthM, hwRatio = 0.18, craterRatio = 0.40, flankDeg = 32.0) {
    const W = Number(widthM);
    const Rb = 0.5 * W, rcr = 0.5 * W * Number(craterRatio), H = Number(hwRatio) * W;
    const t = Math.tan(radians(flankDeg));
    const L = 2.0 * (Rb - rcr - H / t);
    const lo = degrees(Math.atan(H / (Rb - rcr)));
    const hi = degrees(Math.atan(2.0 * H / (Rb - rcr)));
    if (L < -1e-9 * W) {
        throw new ValueError(`cinder cone: flanks at ${pyRepr(Number(flankDeg))} degrees cannot reach H/W ${pyRepr(Number(hwRatio))} with crater/W ` +
            `${pyRepr(Number(craterRatio))}; use at least ${pyFormat(lo, '.1f')} degrees (a straight cone)`);
    }
    if (L > (Rb - rcr) * (1.0 + 1e-9)) {
        throw new ValueError(`cinder cone: flanks at ${pyRepr(Number(flankDeg))} degrees are too steep for H/W ${pyRepr(Number(hwRatio))} with ` +
            `crater/W ${pyRepr(Number(craterRatio))}; use at most ${pyFormat(hi, '.1f')} degrees`);
    }
    return Math.max(L, 0.0);
}

/** flank_deg clamped into the range a cone of these ratios can take (volcanic.py _feasible_flank). */
export function feasibleFlank(flankDeg, hwRatio, craterRatio) {
    const run = 0.5 - 0.5 * Number(craterRatio);
    const lo = degrees(Math.atan(Number(hwRatio) / run));
    const hi = degrees(Math.atan(2.0 * Number(hwRatio) / run));
    return Math.min(Math.max(Number(flankDeg), lo + 0.2), hi - 0.2);
}

/** How far below its base a pile-form cone's flank must reach to meet ground falling at groundSlope (tangent) on its
 * downhill side: at least 2.5 H, at most 8 H (volcanic.py pile_depth_m). */
export function pileDepthM(cone, groundSlope) {
    const W = num(cone.width_m, 800.0);
    const H = num(cone.hw_ratio, 0.18) * W * (1.0 + num(cone.rim_tilt, 0.0));
    const rcr = 0.5 * W * num(cone.crater_ratio, 0.4);
    const t = Math.tan(radians(num(cone.flank_deg, 32.0)));
    const s = Math.min(Number(groundSlope), 0.9 * t);
    const r = (H + t * rcr) / (t - s);
    return Math.min(Math.max(1.15 * (t * (r - rcr) - H), 2.5 * H), 8.0 * H);
}

/** How far a pile-form cone reaches (volcanic.py _pile_radius). */
export function pileRadius(cone) {
    const W = num(cone.width_m, 800.0);
    const H = num(cone.hw_ratio, 0.18) * W;
    const rcr = 0.5 * W * num(cone.crater_ratio, 0.4);
    const t = Math.tan(radians(num(cone.flank_deg, 32.0)));
    let r = rcr + (H * (1.0 + num(cone.rim_tilt, 0.0)) + (num(cone.extend_m, 0.0) || 0.0)) / t;
    r += (Math.max(1.0, num(cone.elongation, 1.0)) - 1.0) * 0.5 * W;
    return r * (1.02 + 3.5 * num(cone.outline_noise, 0.0));
}

/** cinder_cone's numbers (its keyword arguments resolved to their defaults): what coneTexels and cinderConeAt read.
 * Raises as cinder_cone does when the toe cannot fit. */
export function coneParams(cone) {
    const W = num(cone.width_m, 800.0), hw = num(cone.hw_ratio, 0.18), cr = num(cone.crater_ratio, 0.40);
    const fd = num(cone.flank_deg, 32.0);
    const ext = cone.extend_m === undefined || cone.extend_m === null ? null : Number(cone.extend_m);
    const Rb = 0.5 * W, rcr = 0.5 * W * cr, H = hw * W;
    const t = Math.tan(radians(fd));
    const L = ext === null ? cinderConeToeM(W, hw, cr, fd) : 0.0;
    const mode = ext !== null ? 0 : (L > 1e-6 * W ? 1 : 2);
    const tc = Math.tan(radians(num(cone.crater_wall_deg, 30.0)));
    const depth = Math.min(num(cone.crater_depth_frac, 0.45) * H, tc * rcr);
    const w = cone.crest_round_m === undefined || cone.crest_round_m === null ? 0.03 * W : Number(cone.crest_round_m);
    const el = num(cone.elongation, 1.0);
    const seed = int(cone.seed, 0);
    const on = num(cone.outline_noise, 0.0);
    const [ex, ey] = compass(num(cone.elongation_azimuth_deg, 0.0));
    const baz = cone.breach_azimuth_deg === undefined || cone.breach_azimuth_deg === null ? null : Number(cone.breach_azimuth_deg);
    return { at: [num(cone.at?.[0], 0.0), num(cone.at?.[1], 0.0)], W, H, Rb, rcr, t, L, mode, floor: ext === null ? 0.0 : -ext,
        ext, rimTilt: num(cone.rim_tilt, 0.0), tilt: radians(num(cone.tilt_azimuth_deg, 0.0)), tc, depth,
        k: w * (t + tc), breach: baz, baz: baz === null ? 0.0 : radians(baz), half: 0.5 * radians(num(cone.breach_width_deg, 50.0)),
        on, onT: on ? azimuthNoiseTable(seed, 33, 2, 5, 2.0) : null, el: el !== 1.0 && el > 1.0 ? el : 1.0, ex, ey };
}

/** cinder_cone at one point, in doubles (a fresh cone: what numpy evaluates at a few points, stack_piles' bases). */
export function cinderConeAt(cp, x, y) {
    let [r, az] = polar(x, y, cp.at);
    if (cp.el > 1.0) {
        const dx = x - cp.at[0], dy = y - cp.at[1];
        r = Math.hypot((dx * cp.ex + dy * cp.ey) / cp.el, -dx * cp.ey + dy * cp.ex);
    }
    if (cp.on) r = r / (1.0 + cp.on * azRead(cp.onT, az));
    const hrim = cp.rimTilt ? cp.H * (1.0 + cp.rimTilt * Math.cos(az - cp.tilt)) : cp.H;
    const rt = cp.Rb - cp.L;
    let flank;
    if (cp.mode === 0) flank = cp.H - cp.t * (r - cp.rcr);
    else if (cp.mode === 1) flank = r <= rt ? cp.H - cp.t * (r - cp.rcr) : (r < cp.Rb ? cp.t / (2.0 * cp.L) * (cp.Rb - r) ** 2 : 0.0);
    else flank = r < cp.Rb ? cp.H - cp.t * (r - cp.rcr) : 0.0;
    if (cp.rimTilt) flank = flank * (hrim / cp.H);
    const inner = Math.max(hrim + cp.tc * (r - cp.rcr), cp.H - cp.depth);
    let z = crestUnion(flank, inner, cp.k);
    if (cp.breach !== null) {
        const fl = cp.H - cp.depth;
        const d = npMod(az - cp.baz + Math.PI, TAU) - Math.PI;
        const lateral = Math.max(Math.abs(d) - cp.half, 0.0) * Math.max(r, cp.rcr);
        const ramp = fl * (1.0 - Math.min(Math.max((r - 0.5 * cp.rcr) / (cp.Rb - 0.5 * cp.rcr), 0.0), 1.0));
        const cut = ramp + Math.tan(radians(30.0)) * lateral + (Math.abs(d) < Math.PI / 2 ? 0.0 : BIG);
        z = smoothMin(z, cut, 0.02 * fl + 1e-3);
    }
    return Math.max(z, cp.floor);
}

// the eight texels of kernels/volcanic/cone.wgsl for a cone on a grid (patch: an aged cone's { field, half, pc, m })
function coneTexels(cp, grid, tabs, patch = null) {
    const t = new Float32Array(32);
    t.set([cp.W, cp.H, cp.rcr, cp.Rb], 0);
    t.set([cp.t, cp.L, cp.mode, cp.floor], 4);
    t.set([cp.rimTilt, cp.tilt, cp.tc, cp.depth], 8);
    t.set([cp.k, cp.breach !== null ? 1 : 0, cp.baz, cp.half], 12);
    t.set([cp.on, cp.on ? tabs.add(cp.onT) : 0, cp.el, 0.0], 16);
    t.set([cp.ex, cp.ey, 0.0, 0.0], 20);
    if (patch) {
        t.set([(grid.ox - (cp.at[0] - patch.half)) / patch.pc - 0.5, (grid.oy - (cp.at[1] - patch.half)) / patch.pc - 0.5,
            grid.step / patch.pc, patch.m], 24);
    }
    t.set([grid.ox - cp.at[0], grid.oy - cp.at[1], 0.0, 0.0], 28);
    return t;
}

const AGED_PATCHES = new Map();

/** Forget the per-process memos (aged patches, face tables, noise tables), as the floor protocol clears Blender's. */
export function clearMemos() {
    for (const p of AGED_PATCHES.values()) if (!p.field.destroyed) p.field.destroy();
    AGED_PATCHES.clear();
    for (const t of FACE_TABLES.values()) for (const f of [t.zst, t.s0t]) if (f && !f.destroyed) f.destroy();
    FACE_TABLES.clear();
    NOISE_TABLES.clear();
}

/** aged_cinder_cone's patch: the fresh cone on its own grid (cell min(W / 320, sigma / 3), at least 0.25 m and at most
 * a 1024^2 patch), blurred by FFT with sigma^2 = 2 kappa t (core/prims.js gaussianBlur 'periodic': _gauss_fft).
 * { field, half, pc, m }, kept per process under the cone's JSON (volcanic.py _AGED_PATCHES). */
export async function agedPatch(R, cone, kt) {
    const W = num(cone.width_m, 800.0);
    const sig = Math.sqrt(2.0 * kt);
    const ext = cone.extend_m === undefined || cone.extend_m === null ? null : cone.extend_m;
    const half = (ext !== null ? pileRadius(cone) : 0.5 * W * (1.02 + 3.5 * num(cone.outline_noise, 0.0)) *
        Math.max(1.0, num(cone.elongation, 1.0))) + 4.0 * sig;
    const pc = Math.max(Math.min(W / 320.0, sig / 3.0), 0.25, 2.0 * half / 1024.0);
    const m = Math.ceil(2.0 * half / pc);
    const key = pyJsonDumps({ ...cone, kappa_t_m2: kt });
    let rec = AGED_PATCHES.get(key);
    if (rec && !rec.field.destroyed) return rec;
    const cp = coneParams(cone);
    const tabs = new AzTables();
    const grid = new Grid(cp.at[0] - half, cp.at[1] - half, pc, m, m);
    const ctab = R.field(1, 8, 4, coneTexels(cp, grid, tabs));
    const z = R.field(m, m, 1);
    const D = Gd.dummies(R);
    R.run('volcanic/cone_eval', { azt: tabs.field(R), ctab, patch: D.f1 }, { outZ: z }, { uStep: pc });
    const field = prims(R).gaussianBlur(z, sig / pc, { mode: 'periodic' });
    for (const f of [ctab, z]) f.destroy();
    tabs.destroy();
    rec = { field, half, pc, m };
    if (AGED_PATCHES.size > 256) {
        const [k0, old] = AGED_PATCHES.entries().next().value;
        if (!old.field.destroyed) old.field.destroy();
        AGED_PATCHES.delete(k0);
    }
    AGED_PATCHES.set(key, rec);
    return rec;
}


// ============================================================================================ grids, blocks ===

/** The points of an evaluation: point (i, j) at world (ox + (i + 0.5) step, oy + (j + 0.5) step), w x h of them, as
 * numpy's meshgrid of ox + (arange(w) + 0.5) (c / s) (_evaluate_grid, cell_centres, Level.xy). */
export class Grid {
    constructor(ox, oy, step, w, h) {
        Object.assign(this, { ox: Number(ox), oy: Number(oy), step: Number(step), w: Math.trunc(w), h: Math.trunc(h) });
    }

    x(i) { return this.ox + (i + 0.5) * this.step; }
    y(j) { return this.oy + (j + 0.5) * this.step; }

    // np.searchsorted on the ascending axis: 'left' counts the points below v, 'right' those at or below v
    static search(f, lo, hi, v, right) {
        while (lo < hi) {
            const mid = (lo + hi) >> 1;
            const a = f(mid);
            if (right ? a <= v : a < v) lo = mid + 1;
            else hi = mid;
        }
        return lo;
    }

    /** support_slices over rows [r0, r1) of the grid: [row lo, row hi, col lo, col hi] (absolute, exclusive ends) of
     * the square of half-side `radius` about centre, or null when those rows are fewer than two (numpy's None:
     * not a meshgrid). */
    support(centre, radius, r0 = 0, r1 = this.h) {
        if (r1 - r0 < 2 || this.w < 2) return null;
        const cx = Number(centre[0]), cy = Number(centre[1]);
        const c0 = Grid.search((i) => this.x(i), 0, this.w, cx - radius, false);
        const c1 = Grid.search((i) => this.x(i), 0, this.w, cx + radius, true);
        const j0 = Grid.search((j) => this.y(j), r0, r1, cy - radius, false);
        const j1 = Grid.search((j) => this.y(j), r0, r1, cy + radius, true);
        return [j0, j1, c0, c1];
    }
}

/** The grid of a level's cells (cell_centres at supersample s). */
export function levelGrid(level, s = 1) {
    const [x0, y0, cell, n] = levelWindow(level);
    return new Grid(x0, y0, cell / s, n * s, n * s);
}

/** (x0, y0, cell, n) of a level given as an object, an object of those keys or a (x0, y0, side, cell, n) list. */
export function levelWindow(level) {
    if (Array.isArray(level)) return [Number(level[0]), Number(level[1]), Number(level[3]), Math.trunc(level[4])];
    return [Number(level.x0), Number(level.y0), Number(level.cell), Math.trunc(level.n)];
}

const STAMP_BLOCK = 65536;                       // points per evaluation block (_STAMP_BLOCK)

/** _evaluate_grid's row blocks of a grid: [[row lo, row hi], ...] (block false: one). */
export function gridBlocks(grid, s, block = true) {
    const rows = grid.h;
    const step = block ? Math.max(s, Math.floor(Math.max(Math.floor(STAMP_BLOCK / Math.max(grid.w, 1)), 1) / s) * s) : rows;
    const out = [];
    for (let j = 0; j < rows; j += step) out.push([j, Math.min(j + step, rows)]);
    return out;
}

const groupsOf = (w, h) => [Math.max(1, Math.ceil(w / 16)), Math.max(1, Math.ceil(h / 16)), 1];

// a copy of a field (the caller's)
function copyOf(f) {
    const c = f.runner.like(f);
    f.runner.copy(f, c);
    return c;
}

/** The element-wise glue of kernels/volcanic/ew.wgsl (modes listed there): a new field. */
export function ew(R, mode, a, b = null, c = null, d = null, k0 = 0.0, k1 = 0.0, shape = null) {
    const D = Gd.dummies(R);
    const ref = a ?? b ?? c ?? d;
    const [h, w] = shape ?? [ref.h, ref.w];
    const out = R.field(h, w, 1);
    R.run('volcanic/ew', { a: a ?? D.f1, b: b ?? D.f1, c: c ?? D.f1, d: d ?? D.f1 }, { outF: out },
        { uMode: mode, uK0: Number(k0), uK1: Number(k1) });
    return out;
}
export const EW = Object.freeze({ ADD: 0, SUB: 1, POS_DIFF: 2, BED: 3, MIN: 4, MAX: 5, SUB3: 6, STRENGTH: 7,
    MAX_DIFF: 8, CONST: 9, MUL: 10, LERP: 11, CLIP: 12, ADD_SCALED: 13 });


// ================================================================================================ piles_on ===

/** piles_on: cinder cones joined to the surface `out` (a GPU field of the grid's points, changed in place) as piles at
 * repose, each set at its base height, its straight flank continued below the base far enough to meet the ground
 * downhill (pileDepthM, deeper where the support's lowest ground in a row block asks for it) and joined by a smooth
 * maximum over toeFrac of its height (smooth false: a plain maximum). blocks: the row blocks numpy evaluated
 * separately ([[lo, hi], ...]; one block for a whole level). */
export async function pilesOn(R, out, grid, blocks, cones, bases, groundSlopes = null, toeFrac = 0.2, smooth = true) {
    const D = Gd.dummies(R);
    const slopes = groundSlopes ?? cones.map(() => 0.0);
    const nb = blocks.length;
    const blockRows = blocks.length > 1 ? blocks[0][1] - blocks[0][0] : Math.max(grid.h, 1);
    const tabs = new AzTables();
    for (let ci = 0; ci < cones.length; ci++) {
        const c = { ...cones[ci] };
        const b = Number(bases[ci]);
        const kt = Number(pop(c, 'kappa_t_m2', 0.0) || 0.0) || 0.0;
        const H = num(c.hw_ratio, 0.18) * num(c.width_m, 800.0);
        c.extend_m = pyRoundN(pileDepthM(c, slopes[ci]), 1);
        const aged = kt > 0 ? 4.0 * Math.sqrt(2.0 * kt) : 0.0;
        const rb0 = pileRadius(c) + aged;
        const at = [num(c.at?.[0], 0.0), num(c.at?.[1], 0.0)];
        // the support's lowest ground per block (numpy: out[sl0].min() in each block that has sl0)
        const sl0 = blocks.map(([lo, hi]) => grid.support(at, rb0, lo, hi));
        const rows = sl0.filter((s) => s && s[1] > s[0] && s[3] > s[2]);
        let mins = null;
        if (rows.length) {
            const lo = Math.min(...rows.map((s) => s[0])), hi = Math.max(...rows.map((s) => s[1]));
            const c0 = rows[0][2], c1 = rows[0][3];
            const keys = R.field(1, nb, 1, new Uint32Array(nb).fill(0xFFFFFFFF), 'u32');
            R.run('volcanic/rect_min', { src: out }, { mins: keys }, { uRect: [c0, lo, c1, hi], uBlockRows: blockRows },
                groupsOf(c1 - c0, hi - lo));
            const k = await R.read(keys);
            keys.destroy();
            mins = Array.from(k, keyToFloat);
        }
        const k = toeFrac * H;
        for (let bi = 0; bi < nb; bi++) {
            const [lo, hi] = blocks[bi];
            let ext = c.extend_m, rb = rb0;
            const s0 = sl0[bi];
            if (s0 && s0[1] > s0[0] && s0[3] > s0[2]) {
                const need = b - mins[bi] + 0.1 * H;
                if (need > ext) {
                    ext = pyRoundN(need, 1);
                    rb = pileRadius({ ...c, extend_m: ext }) + aged;
                }
            }
            const cb = { ...c, extend_m: ext };
            const sl = grid.support(at, rb, lo, hi);
            let rect, mode = smooth ? 0 : 1;
            if (sl) {
                if (!(sl[1] > sl[0] && sl[3] > sl[2])) continue;
                rect = [sl[2], sl[0], sl[3], sl[1]];
            } else {
                rect = [0, lo, grid.w, hi];
                mode += 2;
            }
            const patch = kt > 0 ? await agedPatch(R, cb, kt) : null;
            const ctab = R.field(1, 8, 4, coneTexels(coneParams(cb), grid, tabs, patch));
            R.run('volcanic/pile', { azt: tabs.field(R), ctab, patch: patch ? patch.field : D.f1 }, { outH: out },
                { uRect: rect, uStep: grid.step, uBase: b, uK: k, uMode: mode, uRb: rb },
                groupsOf(rect[2] - rect[0], rect[3] - rect[1]));
            ctab.destroy();
        }
    }
    tabs.destroy();
    return out;
}

/** stack_piles: cones built in order on a flat floor at floorM, each set on what the earlier ones built there (its
 * base: the floor plus the highest earlier cone at its vent), joined to `out` as piles (in place). */
export async function stackPiles(R, out, grid, blocks, cones, floorM, smooth = true) {
    const bases = [];
    for (let k = 0; k < cones.length; k++) {
        const c = cones[k];
        let b = Number(floorM);
        for (let e = 0; e < k; e++) {
            const ee = { ...cones[e] };
            const kt = Number(pop(ee, 'kappa_t_m2', 0.0) || 0.0) || 0.0;
            const v = kt > 0 ? await agedAt(R, ee, kt, Number(c.at[0]), Number(c.at[1]))
                : cinderConeAt(coneParams(ee), Number(c.at[0]), Number(c.at[1]));
            if (v > 0.0) b = Math.max(b, bases[e] + v);
        }
        bases.push(b);
    }
    return pilesOn(R, out, grid, blocks, cones, bases, null, 0.2, smooth);
}

// aged_cinder_cone at one point: its patch read on the GPU (one readback)
async function agedAt(R, cone, kt, x, y) {
    const patch = await agedPatch(R, cone, kt);
    const cp = coneParams(cone);
    const grid = new Grid(x - 0.5, y - 0.5, 1.0, 1, 1);
    const tabs = new AzTables();
    const ctab = R.field(1, 8, 4, coneTexels(cp, grid, tabs, patch));
    const out = Gd.fill(R, [1, 1], -1e30);
    R.run('volcanic/pile', { azt: tabs.field(R), ctab, patch: patch.field }, { outH: out },
        { uRect: [0, 0, 1, 1], uStep: 1.0, uBase: 0.0, uK: 0.0, uMode: 1, uRb: 0.0 }, [1, 1, 1]);
    const [v] = await R.read(out);
    for (const f of [ctab, out]) f.destroy();
    tabs.destroy();
    return v;
}

/** cinder_cones: several cones combined by their maximum (add_on_support with combine=np.maximum) over the grid, from
 * zero: a new field. */
export async function cinderConesGrid(R, grid, blocks, cones) {
    const D = Gd.dummies(R);
    const out = Gd.fill(R, [grid.h, grid.w], 0.0);
    const tabs = new AzTables();
    for (const c0 of cones) {
        const c = { ...c0 };
        const kt = Number(pop(c, 'kappa_t_m2', 0.0) || 0.0) || 0.0;
        let rb = 0.5 * num(c.width_m, 800.0) * (1.02 + 3.5 * num(c.outline_noise, 0.0)) * Math.max(1.0, num(c.elongation, 1.0));
        rb += kt > 0 ? 4.0 * Math.sqrt(2.0 * kt) : 0.0;
        const at = [num(c.at?.[0], 0.0), num(c.at?.[1], 0.0)];
        const patch = kt > 0 ? await agedPatch(R, c, kt) : null;
        const ctab = R.field(1, 8, 4, coneTexels(coneParams(c), grid, tabs, patch));
        for (const [lo, hi] of blocks) {
            const sl = grid.support(at, rb, lo, hi);
            let rect, mode = 1;
            if (sl) {
                if (!(sl[1] > sl[0] && sl[3] > sl[2])) continue;
                rect = [sl[2], sl[0], sl[3], sl[1]];
            } else {
                rect = [0, lo, grid.w, hi];
                mode = 3;
            }
            R.run('volcanic/pile', { azt: tabs.field(R), ctab, patch: patch ? patch.field : D.f1 }, { outH: out },
                { uRect: rect, uStep: grid.step, uBase: 0.0, uK: 0.0, uMode: mode, uRb: rb },
                groupsOf(rect[2] - rect[0], rect[3] - rect[1]));
        }
        ctab.destroy();
    }
    tabs.destroy();
    return out;
}


// ======================================================================================== the cone plans ===

/** Parasitic cones along a volcano's rift axis (both ways from the centre): cinder_cone argument objects, drawn as
 * numpy draws them (volcanic.py rift_cones). */
export function riftCones(centre, riftAzimuthDeg, opts = {}) {
    const o = { count: 24, distance_m: [1500.0, 12000.0], spread_m: null, width_median_m: 450.0, width_m: [200.0, 1600.0],
        hw_ratio: [0.10, 0.18], crater_ratio: [0.25, 0.45], crater_depth_frac: [0.25, 0.45], flank_deg: [30.0, 33.0],
        breach_fraction: 0.25, outline_noise: 0.06, seed: 0, ...opts };
    const rng = rngOf(o.seed, 31);
    const dist = o.distance_m.map(Number);
    const spread = o.spread_m === null || o.spread_m === undefined ? 0.15 * dist[1] : Number(o.spread_m);
    const [ex, ey] = compass(Number(riftAzimuthDeg));
    const cones = [];
    let tries = 0;
    const count = Math.trunc(o.count);
    while (cones.length < count && tries < 50 * count) {
        tries += 1;
        const side = rng.random() < 0.5 ? 1.0 : -1.0;
        const d = Math.sqrt(rng.uniform(dist[0] ** 2, dist[1] ** 2));
        const lat = rng.normal(0.0, spread * d / dist[1]);
        const px = Number(centre[0]) + side * d * ex - lat * ey;
        const py = Number(centre[1]) + side * d * ey + lat * ex;
        const W = Math.min(Math.max(Number(o.width_median_m) * Math.exp(rng.normal(0.0, 0.55)), Number(o.width_m[0])), Number(o.width_m[1]));
        if (cones.some((c) => Math.hypot(px - c.at[0], py - c.at[1]) < 0.67 * 0.5 * (W + c.width_m))) continue;
        const hw = rng.uniform(Number(o.hw_ratio[0]), Number(o.hw_ratio[1]));
        const cr = rng.uniform(Number(o.crater_ratio[0]), Number(o.crater_ratio[1]));
        const cone = { at: [px, py], width_m: W, hw_ratio: hw, crater_ratio: cr,
            flank_deg: feasibleFlank(rng.uniform(Number(o.flank_deg[0]), Number(o.flank_deg[1])), hw, cr),
            crater_depth_frac: rng.uniform(Number(o.crater_depth_frac[0]), Number(o.crater_depth_frac[1])),
            outline_noise: Number(o.outline_noise), seed: rng.integers(1 << 30) };
        if (rng.random() < Number(o.breach_fraction)) {
            cone.breach_azimuth_deg = degrees(Math.atan2(px - Number(centre[0]), py - Number(centre[1])));
            cone.breach_width_deg = rng.uniform(35.0, 70.0);
        }
        cones.push(cone);
    }
    return cones;
}

/** A cinder cone field (the cinder_cones recipe): cones along vent lines, blue-noise spaced (volcanic.py cinder_field). */
export function cinderField(opts = {}) {
    const o = { count: 12, width_m: [330.0, 1400.0], hw_ratio: 0.18, crater_ratio: [0.30, 0.45], flank_deg: [31.0, 33.0],
        vent_lines: 2, line_trend_deg: null, line_spread_m: 350.0, age_yr: [0.0, 500e3], breach_fraction: 0.3,
        outline_noise: 0.05, avoid: [], elongation: 1.0, overlap: 0.2, breach_toward_deg: null, breach_spread_deg: 50.0,
        seed: 0, ...opts };
    const [x0, y0, size] = o.window.map(Number);
    const rng = rngOf(o.seed, 41);
    const trend = o.line_trend_deg === null || o.line_trend_deg === undefined ? rng.uniform(0.0, 180.0) : Number(o.line_trend_deg);
    const lines = [];
    for (let k = 0; k < Math.trunc(o.vent_lines); k++) {
        const a = trend + rng.uniform(-25.0, 25.0);
        const px = x0 + size * rng.uniform(0.3, 0.7), py = y0 + size * rng.uniform(0.3, 0.7);
        lines.push([px, py, ...compass(a)]);
    }
    const fixed = (o.avoid ?? []).map((c) => ({ at: [Number(c.at[0]), Number(c.at[1])], width_m: num(c.width_m, 800.0) }));
    const cones = [];
    let tries = 0;
    const margin = 0.06 * size;
    const scalarHw = typeof o.hw_ratio === 'number';
    const [hwLo, hwHi] = scalarHw ? [o.hw_ratio, o.hw_ratio] : o.hw_ratio.map(Number);
    const count = Math.trunc(o.count);
    while (cones.length < count && tries < 200 * count) {
        tries += 1;
        const [lx, ly, ex, ey] = lines[rng.integers(lines.length)];
        const s = rng.uniform(-0.6, 0.6) * size;
        const lat = rng.normal(0.0, Number(o.line_spread_m));
        const px = lx + s * ex - lat * ey, py = ly + s * ey + lat * ex;
        const W = Math.exp(rng.uniform(Math.log(Number(o.width_m[0])), Math.log(Number(o.width_m[1]))));
        if (!(x0 + margin + W / 2 < px && px < x0 + size - margin - W / 2 && y0 + margin + W / 2 < py && py < y0 + size - margin - W / 2)) continue;
        if ([...cones, ...fixed].some((c) => Math.hypot(px - c.at[0], py - c.at[1]) < 0.5 * (W + c.width_m) -
            Number(o.overlap) * Math.min(W, c.width_m))) continue;
        const hw = rng.uniform(hwLo, hwHi);
        const cr = rng.uniform(Number(o.crater_ratio[0]), Number(o.crater_ratio[1]));
        const cone = { at: [px, py], width_m: W, hw_ratio: hw, crater_ratio: cr,
            flank_deg: feasibleFlank(rng.uniform(Number(o.flank_deg[0]), Number(o.flank_deg[1])), hw, cr),
            crater_depth_frac: rng.uniform(0.3, 0.5), rim_tilt: rng.uniform(0.0, 0.12), tilt_azimuth_deg: rng.uniform(0.0, 360.0),
            outline_noise: Number(o.outline_noise), age_yr: rng.uniform(Number(o.age_yr[0]), Number(o.age_yr[1])),
            seed: rng.integers(1 << 30) };
        if (rng.random() < Number(o.breach_fraction)) {
            let baz;
            if (o.breach_toward_deg === null || o.breach_toward_deg === undefined) {
                baz = degrees(Math.atan2(px - (x0 + size / 2), py - (y0 + size / 2)));
            } else {                     // from the cone's own seed: the field's draws (and so its cones) stay as they were
                baz = Number(o.breach_toward_deg) + Number(o.breach_spread_deg) * rngOf(cone.seed, 43).uniform(-1.0, 1.0);
            }
            cone.breach_azimuth_deg = baz;
            cone.breach_width_deg = rng.uniform(40.0, 70.0);
        }
        const e = typeof o.elongation === 'number' ? Number(o.elongation) : rng.uniform(Number(o.elongation[0]), Number(o.elongation[1]));
        if (e !== 1.0) {
            // about its vent line, each dyke at its own angle
            cone.elongation = e;
            cone.elongation_azimuth_deg = degrees(Math.atan2(ex, ey)) + rng.normal(0.0, 30.0);
        }
        cones.push(cone);
    }
    return cones;
}

/** The cinder cones a 'cinder_cones' (or 'lava_flows') stage stands for: params cones and/or field (cinder_field's
 * arguments; its seed defaults to the stage seed), each aged when kappa_m2_per_yr is given (volcanic.py cones_of). */
export function conesOf(params, seed) {
    const cones = (params.cones ?? []).map((c) => ({ ...c }));
    if (truthy(params.field)) {
        const f = { ...params.field };
        if (!has(f, 'seed')) f.seed = seed;
        if (!has(f, 'avoid')) f.avoid = cones.map((c) => ({ ...c }));
        cones.push(...cinderField(f));
    }
    const kappa = Number(params.kappa_m2_per_yr ?? 0.0) || 0.0;
    if (kappa > 0.0) for (const c of cones) if (!has(c, 'kappa_t_m2')) c.kappa_t_m2 = kappa * num(c.age_yr, 0.0);
    return cones;
}


// ======================================================================================= stamped once (stamp_add) ===

/** _evaluate_grid: evaluate(grid, blocks) at the (m s)^2 sub-cell points of the m x m cells from (ox, oy) at c metres,
 * each key brought back to cells by its reduce rule (the mean, or 'nanmax'): { name: field (m x m) }. The fields
 * evaluate returns are consumed. */
export async function evaluateGrid(R, evaluate, ox, oy, c, m, s = 1, reduce = null, block = true) {
    const grid = new Grid(ox, oy, c / s, m * s, m * s);
    const blocks = gridBlocks(grid, s, block);
    const sub = await evaluate(grid, blocks);
    if (s === 1) return sub;
    const out = {};
    for (const [k, v] of Object.entries(sub)) {
        if ((reduce ?? {})[k] === 'nanmax') {
            out[k] = R.field(m, m, 1);
            R.run('volcanic/nanmax_down', { src: v }, { outF: out[k] }, { uS: s });
        } else {
            out[k] = Gd.boxDown(v, s);
        }
        v.destroy();
    }
    return out;
}

// the parent level's own evaluation of a stamp kept in ctx.shared (_parent_stamp): { i0, j0, arrays } or null
function parentStamp(ctx, key, x0, y0, cp, m, keys) {
    const store = ctx?.shared ?? null;
    const rec = store?._stamps?.[key];
    if (!rec || Math.abs(rec.cell - cp) > 1e-6 * cp || !keys.every((k) => rec.arrays?.[k] && !rec.arrays[k].destroyed)) return null;
    const fi = (x0 - rec.x0) / cp, fj = (y0 - rec.y0) / cp;
    const i0 = pyRound(fi), j0 = pyRound(fj);
    if (Math.abs(fi - i0) > 1e-4 || Math.abs(fj - j0) > 1e-4 || i0 < 2 || j0 < 2 || i0 + m + 2 > rec.n || j0 + m + 2 > rec.n) return null;
    return { i0, j0, arrays: rec.arrays };
}

/** stamp_add: a world-space shape's contributions added to a level's fields once per terrain (see the module doc of
 * volcanic.py's stage ops): evaluate(grid, blocks) returns { field name: metres to add } at the grid's points, 'h'
 * among them; a key naming no field is only evaluated and returned. On a level that inherited the stamp (fields[key]
 * exists) only what the parent's grid could not hold is added: the shape here less the parent-grid shape upsampled
 * as Fields.inherit upsamples (Catmull-Rom for h and bed, bilinear for the rest). The level's evaluation is kept in
 * ctx.shared._stamps for its child. Returns the evaluation at this level's cells ({ name: field }, the caller's). */
export async function stampAdd(fields, level, key, evaluate, supersample = 1, ctx = null, reduce = null, block = true) {
    const R = fields.R;
    const [x0, y0, cell, n] = levelWindow(level);
    const s = Math.trunc(supersample);
    const here = await evaluateGrid(R, evaluate, x0, y0, cell, n, s, reduce, block);
    const keys = Object.keys(here).filter((k) => k in fields || k === 'h');
    let add = Object.fromEntries(keys.map((k) => [k, here[k]]));
    const own = [];
    if (key in fields) {                          // inherited: the parent's h holds the shape at the parent's grid
        if (n % 2) throw new ValueError(`${key}: a level of ${n} cells cannot be a x2 child`);
        const m = n / 2, cp = 2.0 * cell;
        const rec = parentStamp(ctx, key, x0, y0, cp, m, keys);
        let up;
        if (rec) {
            up = Object.fromEntries(keys.map((k) => [k, Gd.cropUpsample2(rec.arrays[k], rec.i0, rec.j0, m,
                k === 'h' || k === 'bed' ? 'catmull' : 'bilinear')]));
        } else {                                  // the window and the 2 cells crop_upsample2 reads
            const parent = await evaluateGrid(R, async (g, b) => {
                const all = await evaluate(g, b);
                for (const [k, v] of Object.entries(all)) if (!keys.includes(k)) { v.destroy(); delete all[k]; }
                return all;
            }, x0 - 2.0 * cp, y0 - 2.0 * cp, cp, m + 4, s, reduce, block);
            up = Object.fromEntries(keys.map((k) => [k, Gd.cropUpsample2(parent[k], 2, 2, m, k === 'h' || k === 'bed' ? 'catmull' : 'bilinear')]));
            for (const f of Object.values(parent)) f.destroy();
        }
        add = {};
        for (const k of keys) {
            add[k] = ew(R, EW.SUB, here[k], up[k]);
            up[k].destroy();
            own.push(add[k]);
        }
    }
    for (const [k, v] of Object.entries(add)) {
        if (k in fields) fields[k] = ew(R, EW.ADD, fields[k], v);
    }
    for (const f of own) f.destroy();
    fields[key] = copyOf(here.h);
    const store = ctx?.shared ?? null;
    if (store) {
        const stamps = store._stamps ?? (store._stamps = {});
        const old = stamps[key];
        if (old?.arrays) for (const f of Object.values(old.arrays)) if (f && typeof f.destroy === 'function' && !f.destroyed) f.destroy();
        stamps[key] = { x0, y0, cell, n, arrays: Object.fromEntries(keys.map((k) => [k, copyOf(here[k])])) };
    }
    return here;
}

/** Release the fields of an evaluation (stampAdd's result). */
export function release(here) {
    for (const f of Object.values(here ?? {})) if (f && typeof f.destroy === 'function' && !f.destroyed) f.destroy();
}


// ======================================================================================= the runner's context ===

/** True on a coarse-to-fine pre-pass of the coarsest level. */
export function isPrepass(ctx) {
    return ctx !== null && ctx !== undefined && ctx.prepass !== null && ctx.prepass !== undefined;
}

/** The pins of a child level's border band, or null (on the coarsest level none; volcano_setting's own plain pins are
 * not a border band). */
export function bandPins(ctx) {
    const pins = ctx?.pins ?? null;
    if (pins === null || pins._setting) return null;
    return pins;
}

/** A child level's border band pulled to its parent's surface (volcanic.py _pull_band), in place. */
export function pullBand(fields, ctx) {
    const pins = bandPins(ctx);
    if (pins === null || !('h' in fields)) return;
    const R = fields.R, D = Gd.dummies(R);
    const hasBed = 'bed' in fields;
    const outH = R.like(fields.h), outB = hasBed ? R.like(fields.bed) : R.field(1, 1, 1);
    R.run('volcanic/band_pull', { h: fields.h, bed: hasBed ? fields.bed : D.f1, pinW: pins.pin_w, pinH: pins.pin_h },
        { outH, outB }, { uBed: hasBed ? 1 : 0 });
    fields.h = outH;
    if (hasBed) fields.bed = outB;
    else outB.destroy();
}

function runnerOf(fields, ctx) {
    const R = ctx?.device ?? fields.h?.runner ?? fields.R;
    if (!R) throw new Error('volcanic: no GPU runner (give the stage context a device, or fields on the GPU)');
    return R;
}



// ============================================================================== the stratovolcano, evaluated ===

/** stratovolcano() at a grid's points: { h, bed } (bed = h - cinder: all but the parasitic cones' scoria). blocks: the
 * row blocks piles_on runs in (stampAdd's). */
export async function evaluateStrato(R, plan, grid, blocks) {
    const tabs = new AzTables();
    const { prm, fc } = stratoTables(R, plan, grid, tabs);
    const z = R.field(grid.h, grid.w, 1);
    R.run('volcanic/strato', { azt: tabs.field(R), prm, fc }, { outZ: z },
        { uOrg: [grid.ox - plan.centre[0], grid.oy - plan.centre[1]], uStep: grid.step, uFc: plan.flankCraters.length });
    prm.destroy();
    fc.destroy();
    tabs.destroy();
    if (!plan.cones.length) return { h: z, bed: copyOf(z) };
    const out = copyOf(z);
    await pilesOn(R, out, grid, blocks, plan.cones, plan.bases, plan.slopes);
    const bed = ew(R, EW.BED, out, z);
    z.destroy();
    return { h: out, bed };
}


// ======================================================================================= the stage ops (1) ===

/** Stage op 'stratovolcano': params are stratovolcano's (plus rift: rift_cones' arguments, or a list of them each with
 * an optional azimuth_deg; and supersample). Adds the cone to h once (stampAdd); bed takes the rock (all but the
 * parasitic cones' scoria). Skips the coarsest level's pre-passes. */
export async function opStratovolcano(fields, level, params, seed = 0, ctx = null) {
    if (isPrepass(ctx)) return fields;
    const R = runnerOf(fields, ctx);
    const p = { ...params };
    const s = Math.trunc(Number(pop(p, 'supersample', 1)));
    const rift = pop(p, 'rift', null);
    if (!has(p, 'seed')) p.seed = seed;
    const rifts = isDict(rift) ? [rift] : (rift ?? []);
    rifts.forEach((r0, i) => {
        const r = { ...r0 };
        const az = Number(pop(r, 'azimuth_deg', p.rift_azimuth_deg ?? 0.0));
        p.cones = [...(p.cones ?? []), ...riftCones(p.centre ?? [0.0, 0.0], az, { ...r, seed: Math.trunc(p.seed) + 1009 * i })];
    });
    const plan = stratoPlan(p);
    const here = await stampAdd(fields, level, stampKey('stratovolcano', { ...params, seed: p.seed }),
        (grid, blocks) => evaluateStrato(R, plan, grid, blocks), s, ctx);
    release(here);
    pullBand(fields, ctx);
    return fields;
}

/** (base heights, ground slopes) at each cone's vent on a level's surface h (a GPU field): bilinear height and the
 * slope of the surface smoothed over the cone's footprint; with exact false (a surface that holds the cones already),
 * the 10th percentile of a ring just outside each cone (volcanic.py _ground_at). One gather, one readback. */
export async function groundAt(h, level, cones, exact) {
    const R = h.runner, P = prims(R);
    const [x0, y0, cell, n] = levelWindow(level);
    const B = HS.gaussianBlur(h, Math.max(150.0 / cell, 1.0));
    const idx = [], plan = [];
    const at = (j, i) => { idx.push(j * n + i); return idx.length - 1; };
    for (const c of cones) {
        const fx = (Number(c.at[0]) - x0) / cell - 0.5, fy = (Number(c.at[1]) - y0) / cell - 0.5;
        const i0 = Math.trunc(Math.min(Math.max(Math.floor(fx), 0), n - 2));
        const j0 = Math.trunc(Math.min(Math.max(Math.floor(fy), 0), n - 2));
        const tx = Math.min(Math.max(fx - i0, 0), 1), ty = Math.min(Math.max(fy - j0, 0), 1);
        // np.gradient: central differences inside, one-sided on the edge (i0 and j0 stop at n - 2)
        const gxI = i0 === 0 ? [at(j0, 1), at(j0, 0), cell] : [at(j0, i0 + 1), at(j0, i0 - 1), 2.0 * cell];
        const gyI = j0 === 0 ? [at(1, i0), at(0, i0), cell] : [at(j0 + 1, i0), at(j0 - 1, i0), 2.0 * cell];
        const rec = { i0, j0, tx, ty, gxI, gyI, nB: idx.length };
        if (exact) {
            rec.hI = [j0 * n + i0, j0 * n + i0 + 1, (j0 + 1) * n + i0, (j0 + 1) * n + i0 + 1];
        } else {
            const Rr = 0.6 * num(c.width_m, 800.0) * Math.max(1.0, num(c.elongation, 1.0));
            rec.ring = [];
            for (let k = 0; k < 64; k++) {
                const a = k * (TAU / 64);
                const ii = Math.min(Math.max(Math.trunc((Number(c.at[0]) + Rr * Math.sin(a) - x0) / cell), 0), n - 1);
                const jj = Math.min(Math.max(Math.trunc((Number(c.at[1]) + Rr * Math.cos(a) - y0) / cell), 0), n - 1);
                rec.ring.push(jj * n + ii);
            }
        }
        plan.push(rec);
    }
    const hIdx = plan.flatMap((r) => r.hI ?? r.ring);
    const gB = P.gather(B, P.list(Math.max(idx.length, 1), 'u32', Uint32Array.from(idx.length ? idx : [0])));
    const gH = P.gather(h, P.list(Math.max(hIdx.length, 1), 'u32', Uint32Array.from(hIdx.length ? hIdx : [0])));
    const [vb, vh] = await R.readAll([gB, gH]);
    for (const f of [B, gB, gH]) f.destroy();
    const bases = [], slopes = [];
    let o = 0;
    for (const r of plan) {
        const gx = (vb[r.gxI[0]] - vb[r.gxI[1]]) / r.gxI[2];
        const gy = (vb[r.gyI[0]] - vb[r.gyI[1]]) / r.gyI[2];
        const s = Math.hypot(gx, gy);
        let b;
        if (exact) {
            const [h00, h01, h10, h11] = [vh[o], vh[o + 1], vh[o + 2], vh[o + 3]];
            o += 4;
            b = (h00 * (1 - r.tx) + h01 * r.tx) * (1 - r.ty) + (h10 * (1 - r.tx) + h11 * r.tx) * r.ty;
        } else {
            b = npQuantile64(vh.slice(o, o + 64), 10);
            o += 64;
        }
        bases.push(b);
        slopes.push(s);
    }
    return [bases, slopes];
}

/** Stage op 'cinder_cones': params cones and/or field (cinder_field's arguments), kappa_m2_per_yr (each cone aged by
 * kappa x its age_yr). compose 'pile' (the default): each cone a pile at repose on the level's ground, set at the
 * ground's height at its vent, sampled on the first level the stage runs on and kept for the finer levels, which join
 * the same piles by a plain maximum; 'add': the cones added to h (stampAdd). toe_frac: the piles' concave toe (0.2).
 * bed is unchanged, so the cones are loose scoria for the talus stage. */
export async function opCinderCones(fields, level, params, seed = 0, ctx = null) {
    if (isPrepass(ctx)) return fields;
    const R = runnerOf(fields, ctx);
    const p = { ...params };
    const s = Math.trunc(Number(pop(p, 'supersample', 1)));
    const compose = pop(p, 'compose', 'pile');
    const toe = Number(pop(p, 'toe_frac', 0.2));
    const cones = conesOf(p, seed);
    const key = stampKey('cinder_cones', { ...params, seed });
    if (compose === 'add') {
        const here = await stampAdd(fields, level, key, async (grid, blocks) => ({ h: await cinderConesGrid(R, grid, blocks, cones) }), s, ctx);
        release(here);
        pullBand(fields, ctx);
        return fields;
    }
    const h = fields.h;
    const grid = levelGrid(level);
    const store = ctx ? (ctx.shared ?? (ctx.shared = {})) : {};
    const first = !(key in fields);
    if (first || !(key in store)) {
        const ground = first ? h : HS.gaussianBlur(h, 2.0);        // a cache hit upstream lost the stored bases
        const [bases, slopes] = await groundAt(ground, level, cones, first);
        if (ground !== h) ground.destroy();
        store[key] = { bases, slopes };
    }
    const rec = store[key];
    const out = copyOf(h);
    await pilesOn(R, out, grid, [[0, grid.h]], cones, rec.bases, rec.slopes, toe, first);
    if (first) fields[key] = ew(R, EW.SUB, out, h);
    fields.h = out;
    pullBand(fields, ctx);
    return fields;
}


// ============================================================================================ the presets ===
// The parameters that put each analytic shape on its reference (volcanic.py, measured from the reference DEMs by
// blender/tests/terrain/volcanoes_craters/test_references.py), in the reference's local metres.

export const FUJI = Object.freeze({
    centre: [300.0, 260.0], base_m: 755.0, height_m: 2983.0, radius_m: 19860.0, upper_slope_deg: 35.3,
    crater_radius_m: 300.0, crater_depth_m: 220.0, crater_floor_frac: 0.35, summit_platform_m: 120.0,
    elongation: 1.12, rift_azimuth_deg: 315.0, radius_noise: 0.05, height_noise: 0.004,
    flank_craters: [{ at: [1900.0, -1650.0], radius_m: 650.0, depth_m: 330.0, rim_m: 70.0 }],
    rift: { count: 18, distance_m: [2500.0, 11500.0], spread_m: 2800.0, width_median_m: 650.0,
        width_m: [300.0, 1800.0], hw_ratio: [0.10, 0.17], crater_ratio: [0.15, 0.32], crater_depth_frac: [0.08, 0.3] },
    seed: 3,
});

export const CRATER_LAKE = Object.freeze({
    centre: [95.0, 9.0], lake_m: 1880.5, floor_m: 1300.0,
    edifice: { base_m: 1512.0, height_m: 1639.0, radius_m: 25000.0, upper_slope_deg: 16.7, crater_radius_m: 300.0,
        height_noise: 0.15, radius_noise: 0.03 },
    flank_cones: { count: 5, distance_m: [5600.0, 8800.0], spread_m: 2500.0, width_median_m: 900.0,
        width_m: [450.0, 1500.0], hw_ratio: [0.10, 0.16], crater_ratio: [0.12, 0.25], crater_depth_frac: [0.05, 0.2],
        breach_fraction: 0.0 },
    flank_cone_azimuth_deg: 330.0,
    rim_radius_m: 4700.0, wall_deg: 38.0, talus_deg: 33.0, talus_frac: 0.6, scallops: 9, scallop_amp: 0.12,
    radius_noise: 0.025, edge_noise: 0.012, elongation: 1.214, elongation_azimuth_deg: 72.0,
    inner_cones: [{ at: [-2950.0, -280.0], width_m: 3409.0, hw_ratio: 0.1716, crater_ratio: 0.4283, flank_deg: 31.5,
        crater_depth_frac: 0.0, crest_round_m: 40.0, outline_noise: 0.12, seed: 21 },
    { at: [-2733.0, -385.0], width_m: 1100.0, hw_ratio: 0.205, crater_ratio: 0.082, flank_deg: 33.0,
        crater_depth_frac: 0.13, outline_noise: 0.04, seed: 22 }],
    seed: 5,
});

export const SP_CRATER = Object.freeze({
    at: [-12.0, -4.0], width_m: 1320.0, hw_ratio: 0.18, crater_ratio: 0.28, flank_deg: 32.0, crater_wall_deg: 30.0,
    crater_depth_frac: 0.41, rim_tilt: 0.05, tilt_azimuth_deg: 200.0, outline_noise: 0.04, seed: 9,
});

/** The FUJI preset's analytic surface (metres above sea level) at a grid's points: the cone, its crater, the Hoei
 * crater and the rift cones as piles, on a flat foot at base_m (volcanic.py fuji_surface: one evaluation over the
 * whole grid, so the piles' support is one block). A new field. */
export async function fujiSurface(R, grid, preset = FUJI) {
    const p = { ...preset };
    const rift = pop(p, 'rift');
    const base = Number(pop(p, 'base_m'));
    const cones = riftCones(p.centre, p.rift_azimuth_deg, { ...rift, seed: p.seed });
    const out = await evaluateStrato(R, stratoPlan({ ...p, cones }), grid, gridBlocks(grid, 1, false));
    const z = ew(R, EW.LERP, null, out.h, null, null, base, base + 1.0);
    release(out);
    return z;
}

/** The CRATER_LAKE preset's analytic surface (metres above sea level) on a square level: the edifice with its flank
 * cones, collapsed at the rim's mean height round rim_radius_m (720 points, in doubles), the inner cones stacked on
 * the floor at floor_m; the lake is not filled (volcanic.py crater_lake_surface). A new field. */
export async function craterLakeSurface(R, level, preset = CRATER_LAKE) {
    const p = { ...preset };
    const e = { ...p.edifice };
    const base = Number(pop(e, 'base_m'));
    const cones = riftCones(p.centre, p.flank_cone_azimuth_deg, { ...p.flank_cones, seed: p.seed });
    const plan = stratoPlan({ ...e, centre: p.centre, seed: p.seed });
    const grid = levelGrid(level);
    const blocks = gridBlocks(grid, 1, false);
    const ed = await evaluateStrato(R, plan, grid, blocks);
    const at = ew(R, EW.LERP, null, ed.h, null, null, base, base + 1.0);
    release(ed);
    const cz = await cinderConesGrid(R, grid, blocks, cones);
    const edifice = ew(R, EW.ADD, at, cz);
    at.destroy();
    cz.destroy();
    // _ring_mean of the edifice without its cones: on the ring the summit crater's bowl is BIG, and numpy's
    // crest_union(z, BIG, k) returns BIG + (z - BIG), rounded as here
    const c = p.centre.map(Number), Rr = Number(p.rim_radius_m);
    const vals = new Float64Array(720);
    for (let k = 0; k < 720; k++) {
        const a = k * (TAU / 720);
        vals[k] = base + (BIG + (outerAt(plan, c[0] + Rr * Math.sin(a), c[1] + Rr * Math.cos(a)) - BIG));
    }
    const rimH = npSum(vals) / 720;
    const keys = ['wall_deg', 'talus_deg', 'talus_frac', 'scallops', 'scallop_amp', 'radius_noise', 'edge_noise',
        'elongation', 'elongation_azimuth_deg', 'seed'];
    const out = await calderaCollapse(R, level, edifice, { centre: p.centre, rim_radius_m: Rr, rim_height_m: rimH,
        floor_m: Number(p.floor_m), ...Object.fromEntries(keys.map((k) => [k, p[k]])) });
    edifice.destroy();
    for (const k of ['talus', 'floor', 'strength']) if (out[k] && !out[k].destroyed) out[k].destroy();
    await stackPiles(R, out.height, grid, blocks, p.inner_cones, Number(p.floor_m));
    return out.height;
}


// ============================================================================================== calderas (4.7) ===

// CPython's math.gamma (Modules/mathmodule.c m_tgamma: the Lanczos sum with g = 6.0246800407767296, its error term,
// and the exact factorials for integers up to 23), for positive arguments: _scallop_table's mean
const LANCZOS_G = 6.024680040776729583740234375, LANCZOS_G_MINUS_HALF = 5.524680040776729583740234375;
const LANCZOS_NUM = [23531376880.410759688572007674451636754734846804940, 42919803642.649098768957899047001988850926355848959,
    35711959237.355668049440185451547166705960488635843, 17921034426.037209699919755754458931112671403265390,
    6039542586.3520280050642916443072979210699388420708, 1439720407.3117216736632230727949123939715485786772,
    248874557.86205415651146038641322942321632125127801, 31426415.585400194380614231628318205362874684987640,
    2876370.6289353724412254090516208496135991145378768, 186056.26539522349504029498971604569928220784236328,
    8071.6720023658162106380029022722506138218516325024, 210.82427775157934587250973392071336271166969580291,
    2.5066282746310002701649081771338373386264310793408];
const LANCZOS_DEN = [0.0, 39916800.0, 120543840.0, 150917976.0, 105258076.0, 45995730.0, 13339535.0, 2637558.0,
    357423.0, 32670.0, 1925.0, 66.0, 1.0];

function lanczosSum(x) {
    let num = 0.0, den = 0.0;
    if (x < 5.0) {
        for (let i = 12; i >= 0; i--) {
            num = num * x + LANCZOS_NUM[i];
            den = den * x + LANCZOS_DEN[i];
        }
    } else {
        for (let i = 0; i < 13; i++) {
            num = num / x + LANCZOS_NUM[i];
            den = den / x + LANCZOS_DEN[i];
        }
    }
    return num / den;
}

/** math.gamma(x) for 0 < x <= 140, as CPython computes it. */
export function pyGamma(x) {
    if (!(x > 0.0) || x > 140.0) throw new ValueError(`pyGamma: ${x} is outside (0, 140]`);
    if (Number.isInteger(x) && x <= 23) {
        let f = 1.0;
        for (let k = 2; k < x; k++) f *= k;
        return f;
    }
    const absx = Math.abs(x);
    const y = absx + LANCZOS_G_MINUS_HALF;
    let z;
    if (absx > LANCZOS_G_MINUS_HALF) {
        const q = y - absx;
        z = q - LANCZOS_G_MINUS_HALF;
    } else {
        const q = y - LANCZOS_G_MINUS_HALF;
        z = q - absx;
    }
    z = z * LANCZOS_G / y;
    let r = lanczosSum(absx) / Math.exp(y);
    r += z * r;
    return r * Math.pow(y, absx - 0.5);
}

// an in-place radix-2 complex FFT in doubles (inverse: the unscaled inverse transform): the 1D tables' smoothing
function fft(re, im, inverse = false) {
    const n = re.length;
    for (let i = 1, j = 0; i < n; i++) {
        let bit = n >> 1;
        for (; j & bit; bit >>= 1) j ^= bit;
        j ^= bit;
        if (i < j) {
            [re[i], re[j]] = [re[j], re[i]];
            [im[i], im[j]] = [im[j], im[i]];
        }
    }
    for (let len = 2; len <= n; len *= 2) {
        const th = ((inverse ? 2 : -2) * Math.PI) / len;
        for (let k = 0; k < len / 2; k++) {
            const wr = Math.cos(th * k), wi = Math.sin(th * k);
            for (let i = k; i < n; i += len) {
                const j = i + len / 2;
                const xr = re[j] * wr - im[j] * wi, xi = re[j] * wi + im[j] * wr;
                re[j] = re[i] - xr;
                im[j] = im[i] - xi;
                re[i] += xr;
                im[i] += xi;
            }
        }
    }
}

/** np.interp(x, xp, fp) at one x (numpy's compiled interp: the left / right values outside, fp[j] on a point, the
 * segment's slope times the distance plus fp[j] between). */
export function npInterp(x, xp, fp) {
    const n = xp.length;
    if (x > xp[n - 1]) return fp[n - 1];
    if (x < xp[0]) return fp[0];
    let lo = 0, hi = n - 1;
    while (hi - lo > 1) {                          // xp[lo] <= x < xp[hi]
        const mid = (lo + hi) >> 1;
        if (xp[mid] <= x) lo = mid;
        else hi = mid;
    }
    if (x === xp[n - 1]) return fp[n - 1];
    if (xp[lo] === x) return fp[lo];
    const slope = (fp[lo + 1] - fp[lo]) / (xp[lo + 1] - xp[lo]);
    return slope * (x - xp[lo]) + fp[lo];
}

// np.searchsorted(a, v, side) on an ascending array of doubles
function searchSorted(a, v, side = 'left') {
    return Grid.search((i) => a[i], 0, a.length, v, side === 'right');
}

// np.linspace(start, stop, num) (endpoint: the last value set to stop)
function linspace(start, stop, num) {
    const step = (stop - start) / (num - 1);
    const y = Float64Array.from({ length: num }, (_, i) => i * step + start);
    y[num - 1] = stop;
    return y;
}

/** _scallop_table: `count` arcs bulging outward between inward cusps, each its own size, zero mean (doubles). */
export function scallopTable(count, amp, seed, salt = 51, sharpness = 0.6, sizes = [0.3, 1.7]) {
    const rng = rngOf(seed, salt);
    const n = Math.trunc(count);
    const jit = rng.uniform(-0.4, 0.4, n);
    const rot = rng.uniform(0.0, TAU);
    const cusps = Float64Array.from({ length: n }, (_, k) => npMod((k + jit[k]) * TAU / n + rot, TAU)).sort();
    const size = rng.uniform(Number(sizes[0]), Number(sizes[1]), n);
    const s = Number(sharpness);
    const mean = pyGamma(s + 1.0) ** 2 / pyGamma(2.0 * s + 2.0) * 4.0 ** s;   // E[(4t(1-t))^s]
    const out = new Float64Array(AZ_SAMPLES + 1);
    for (let q = 0; q <= AZ_SAMPLES; q++) {
        const a = npMod(AZ_TABLE_ANGLES[q], TAU);
        const i = searchSorted(cusps, a, 'right') - 1;
        const c0 = i >= 0 ? cusps[((i % n) + n) % n] : cusps[n - 1] - TAU;
        let c1 = i + 1 < n ? cusps[(i + 1) % n] : cusps[0] + TAU;
        if (i < 0) c1 = cusps[0];
        const t = Math.min(Math.max((a - c0) / (c1 - c0), 0.0), 1.0);
        const bulge = (4.0 * t * (1.0 - t)) ** s;
        out[q] = Number(amp) * size[((i % n) + n) % n] * (bulge - mean);
    }
    return out;
}

/** scallop_outline's table: _scallop_table with its cusps rounded by a Gaussian of round_deg along the ring (by FFT,
 * as numpy rounds it). */
export function scallopOutlineTable(count, amp, seed, salt = 51, sharpness = 0.6, roundDeg = 1.5, sizes = [0.3, 1.7]) {
    let table = scallopTable(count, amp, seed, salt, sharpness, sizes);
    if (roundDeg > 0) {
        const sig = Number(roundDeg) / 360.0 * AZ_SAMPLES;
        const re = Float64Array.from(table.subarray(0, AZ_SAMPLES)), im = new Float64Array(AZ_SAMPLES);
        fft(re, im);
        for (let k = 0; k <= AZ_SAMPLES / 2; k++) {
            const g = Math.exp(-0.5 * (TAU * k * sig / AZ_SAMPLES) ** 2);
            re[k] *= g;
            im[k] *= g;
            if (k > 0 && k < AZ_SAMPLES / 2) {
                re[AZ_SAMPLES - k] *= g;
                im[AZ_SAMPLES - k] *= g;
            }
        }
        im[0] = 0.0;
        im[AZ_SAMPLES / 2] = 0.0;
        fft(re, im, true);
        table = new Float64Array(AZ_SAMPLES + 1);
        for (let i = 0; i < AZ_SAMPLES; i++) table[i] = re[i] / AZ_SAMPLES;
        table[AZ_SAMPLES] = table[0];
    }
    return table;
}

/** embayment_outline's table: `count` smooth outward bights (raised cosines) at drawn azimuths, zero mean. */
export function embaymentTable(count, amp, widthDeg, seed, salt = 55) {
    const rng = rngOf(seed, salt);
    const t = new Float64Array(AZ_SAMPLES + 1);
    const a = Float64Array.from(AZ_TABLE_ANGLES, (v) => npMod(v, TAU));
    for (let q = 0; q < Math.trunc(count); q++) {
        const c = rng.uniform(0.0, TAU);
        const w = radians(rng.uniform(Number(widthDeg[0]), Number(widthDeg[1])));
        const amt = rng.uniform(Number(amp[0]), Number(amp[1]));
        for (let i = 0; i <= AZ_SAMPLES; i++) {
            const d = Math.abs(npMod(a[i] - c + Math.PI, TAU) - Math.PI);
            t[i] += amt * (d < w ? 0.5 * (1.0 + Math.cos(Math.PI * d / w)) : 0.0);
        }
    }
    const mean = npSum(t.subarray(0, AZ_SAMPLES)) / AZ_SAMPLES;
    for (let i = 0; i <= AZ_SAMPLES; i++) t[i] -= mean;
    return t;
}

/** A rock wall's column from its foot up, as the layers of its cliffs and benches: [[thickness_m, angle_deg], ...]
 * (volcanic.py wall_column). */
export function wallColumn(heightM, wallDeg, opts = {}) {
    const o = { strong_deg: 72.0, strong_frac: 0.35, layer_m: [25.0, 110.0], weak_min_deg: 24.0, seed: 0, salt: 55, ...opts };
    const H = Number(heightM);
    const rng = rngOf(o.seed, o.salt);
    const lay = [];
    let z = 0.0, strong = rng.random() < 0.5;
    const sf = Math.min(Math.max(Number(o.strong_frac), 0.0), 0.9);
    while (z < H) {
        let th = rng.uniform(Number(o.layer_m[0]), Number(o.layer_m[1])) * (strong ? 0.7 : 1.0);
        th *= strong ? (sf / 0.5) : ((1.0 - sf) / 0.5);
        lay.push([Math.max(th, 1.0), strong]);
        z += lay[lay.length - 1][0];
        strong = !strong;
    }
    const k = H / z;
    for (const L of lay) L[0] *= k;
    let hs = 0.0;
    for (const [t, s] of lay) if (s) hs += t;
    const hw = H - hs;
    const ts = Math.tan(radians(o.strong_deg));
    const run = H / Math.tan(radians(wallDeg)) - hs / ts;
    let weak = hw <= 1e-6 ? Number(wallDeg) : (run > 1e-6 ? degrees(Math.atan(hw / run)) : Number(wallDeg));
    weak = Math.min(Math.max(weak, Number(o.weak_min_deg)), Number(wallDeg));
    return lay.map(([t, s]) => [t, s ? Number(o.strong_deg) : weak]);
}

/** (u, z) of a wall built from its column over a talus apron talus_m high at talus_deg (volcanic.py column_profile). */
export function columnProfile(column, talusM = 0.0, talusDeg = 35.0) {
    const us = [0.0], zs = [0.0];
    if (talusM > 0) {
        us.push(talusM / Math.tan(radians(talusDeg)));
        zs.push(Number(talusM));
    }
    for (const [t, a] of column) {
        us.push(us[us.length - 1] + t / Math.tan(radians(a)));
        zs.push(zs[zs.length - 1] + t);
    }
    return [Float64Array.from(us), Float64Array.from(zs)];
}

/** The horizontal run of a caldera wall: a talus apron over talus_frac of the height, then the rock face. */
export function calderaWallRunM(wallHeightM, wallDeg = 42.0, talusDeg = 35.0, talusFrac = 0.35) {
    const th = Number(talusFrac) * Number(wallHeightM);
    return th / Math.tan(radians(talusDeg)) + (Number(wallHeightM) - th) / Math.tan(radians(wallDeg));
}

const FACE_AZ = 720, FACE_RUN = 4096;
const FACE_TABLES = new Map();

/** _face_table: the layered face's sector blend tabulated once per wall (kept per process): { U, zst (the 721 x 4097
 * (Z, S) field), s0t (S0, 1 x 721), S0 }. The sectors' columns, profiles and weights are 1D (doubles, as numpy); the
 * blend of every (azimuth, run) is kernels/volcanic/face_table.wgsl. */
export function faceTable(R, heightM, wallDeg, spec, seed) {
    const key = pyJsonDumps([Number(heightM), Number(wallDeg), spec, Math.trunc(seed)]);
    const hit = FACE_TABLES.get(key);
    if (hit && !hit.zst.destroyed) return hit;
    const sp = { ...spec };
    const n = Math.trunc(Number(pop(sp, 'sectors', 7)));
    const rng = rngOf(seed, 57);
    const phase = rng.uniform(0.0, TAU);
    const tw = Math.tan(radians(wallDeg));
    const cols = [];
    for (let k = 0; k < n; k++) cols.push(columnProfile(wallColumn(heightM, wallDeg, { ...sp, seed: Math.trunc(seed) * 31 + k })));
    let U = 0.0;
    for (const [uk] of cols) U = Math.max(U, uk[uk.length - 1]);
    const ut = linspace(0.0, U, FACE_RUN + 1), at = linspace(0.0, TAU, FACE_AZ + 1);
    const zs = new Float32Array(n * (FACE_RUN + 1) * 2), ws = new Float32Array((n + 1) * (FACE_AZ + 1));
    const W = new Float64Array(FACE_AZ + 1), S0 = new Float64Array(FACE_AZ + 1);
    cols.forEach(([uk, zk], k) => {
        const top = uk[uk.length - 1];
        for (let i = 0; i <= FACE_RUN; i++) {
            const u = ut[i];
            const z = u > top ? zk[zk.length - 1] + tw * (u - top) : npInterp(u, uk, zk);
            const seg = Math.min(Math.max(searchSorted(uk, u) - 1, 0), uk.length - 2);
            const s = u > top ? tw : (zk[seg + 1] - zk[seg]) / Math.max(uk[seg + 1] - uk[seg], 1e-9);
            zs[2 * (k * (FACE_RUN + 1) + i)] = z;
            zs[2 * (k * (FACE_RUN + 1) + i) + 1] = s;
        }
        const s0 = zk[1] / Math.max(uk[1], 1e-9);
        for (let j = 0; j <= FACE_AZ; j++) {
            const w = Math.exp(8.0 * (Math.cos(at[j] - (phase + TAU * k / n)) - 1.0));
            ws[k * (FACE_AZ + 1) + j] = w;
            S0[j] += w * s0;
            W[j] += w;
        }
    });
    for (let j = 0; j <= FACE_AZ; j++) {
        ws[n * (FACE_AZ + 1) + j] = W[j];
        S0[j] /= W[j];
    }
    const zf = R.field(n, FACE_RUN + 1, 2, zs), wf = R.field(n + 1, FACE_AZ + 1, 1, ws);
    const zst = R.field(FACE_AZ + 1, FACE_RUN + 1, 2);
    R.run('volcanic/face_table', { zs: zf, ws: wf }, { outZS: zst }, { uSectors: n });
    zf.destroy();
    wf.destroy();
    const rec = { U, zst, s0t: R.field(1, FACE_AZ + 1, 1, Float32Array.from(S0)), S0 };
    if (FACE_TABLES.size > 32) {
        const [k0, old] = FACE_TABLES.entries().next().value;
        for (const f of [old.zst, old.s0t]) if (!f.destroyed) f.destroy();
        FACE_TABLES.delete(k0);
    }
    FACE_TABLES.set(key, rec);
    return rec;
}

/** caldera_collapse's numbers and tables from its keyword arguments (rim_height_m and floor_m resolved): what
 * kernels/volcanic/caldera.wgsl reads. Raises as caldera_collapse does. */
export async function calderaPlan(R, p) {
    const o = { wall_deg: 42.0, talus_deg: 35.0, talus_frac: 0.35, scallops: 8, scallop_amp: 0.05, radius_noise: 0.02,
        edge_noise: 0.01, elongation: 1.0, elongation_azimuth_deg: 0.0, crest_round_m: 40.0, round_crest: true,
        cliffs: null, edge_decay: 1.0, scallop_sizes: [0.3, 1.7], talus_vary: 0.0, polygon: null, embayments: null,
        seed: 0, ...p };
    const floorM = Number(o.floor_m), rimH = Number(o.rim_height_m), rimR = Number(o.rim_radius_m);
    const Hw = rimH - floorM;
    if (Hw <= 0.0) throw new ValueError(`caldera: the floor ${pyFormat(floorM, '.0f')} m must lie below the rim ${pyFormat(rimH, '.0f')} m`);
    const wallDeg = Number(o.wall_deg), talusDeg = Number(o.talus_deg), tf = Number(o.talus_frac);
    const run = calderaWallRunM(Hw, wallDeg, talusDeg, tf);
    const rFloor = rimR - run;
    if (rFloor <= 0.05 * rimR) {
        throw new ValueError(`caldera: walls of ${pyFormat(Hw, '.0f')} m at ${pyRepr(wallDeg)}/${pyRepr(talusDeg)} degrees run ` +
            `${pyFormat(run, '.0f')} m, wider than the rim radius ${pyFormat(rimR, '.0f')} m allows; widen the caldera or steepen the walls`);
    }
    const seed = Math.trunc(o.seed);
    const tabs = new AzTables();
    const rows = { rn: 0, en: 0, sc: 0, pg: 0, eb: 0, tv: 0 };
    const rn = Number(o.radius_noise), en = Number(o.edge_noise), tv = Number(o.talus_vary);
    if (rn) rows.rn = tabs.add(azimuthNoiseTable(seed, 52, 1, 5));
    if (en) rows.en = tabs.add(azimuthNoiseTable(seed, 53, 10, 48, Number(o.edge_decay)));
    if (truthy(o.scallops)) {
        rows.sc = tabs.add(scallopOutlineTable(o.scallops, Number(o.scallop_amp), seed, 51, 0.6, 1.5, o.scallop_sizes.map(Number)));
    }
    if (truthy(o.polygon)) {
        const { polygonTable } = await import('./impact.js');
        const pg = o.polygon;
        rows.pg = tabs.add(polygonTable(Math.trunc(pg.sides), Number(pg.strength), num(pg.azimuth_deg, 0.0), num(pg.roundness, 0.08)));
    }
    if (truthy(o.embayments)) {
        const eb = o.embayments;
        rows.eb = tabs.add(embaymentTable(Math.trunc(eb.count), eb.amp, eb.width_deg, seed, int(eb.salt, 55)));
    }
    if (tv) rows.tv = tabs.add(azimuthNoiseTable(seed, 54, 3, 24, 0.6));
    const tt = Math.tan(radians(talusDeg)), tw = Math.tan(radians(wallDeg));
    const th = tf * Hw;
    const face = truthy(o.cliffs) ? faceTable(R, Hw - th, wallDeg, { ...o.cliffs }, seed) : null;
    const prm = new Float32Array(28);
    prm.set([Hw, rFloor, tt, tw], 0);
    prm.set([th, floorM, 0.02 * Hw, Number(o.crest_round_m) * (tw + 0.1)], 4);
    prm.set([Number(o.elongation), radians(Number(o.elongation_azimuth_deg)), rn, en], 8);
    prm.set([truthy(o.scallops) ? 1 : 0, truthy(o.polygon) ? 1 : 0, truthy(o.embayments) ? 1 : 0, tv], 12);
    prm.set([rows.rn, rows.en, rows.sc, rows.pg], 16);
    prm.set([rows.eb, rows.tv, truthy(o.round_crest) ? 1 : 0, face ? 1 : 0], 20);
    prm.set([face ? face.U : 0.0, tw, 0.0, 0.0], 24);
    return { o, Hw, rFloor, tabs, face, prm, centre: [Number(o.centre[0]), Number(o.centre[1])] };
}

/** caldera_collapse at a level's cells over the surface hb (a GPU field): { height, talus, floor, strength } fields
 * (strength only with cliffs; the caller's). */
export async function calderaCollapse(R, level, hb, p) {
    const plan = await calderaPlan(R, p);
    const [x0, y0, cell, n] = levelWindow(level);
    const D = Gd.dummies(R);
    const prm = R.field(1, 7, 4, plan.prm);
    const out = { height: R.field(n, n, 1), talus: R.field(n, n, 1), floor: R.field(n, n, 1), strength: R.field(n, n, 1) };
    R.run('volcanic/caldera', { azt: plan.tabs.field(R), zst: plan.face ? plan.face.zst : D.f2, s0t: plan.face ? plan.face.s0t : D.f1,
        prm, hb }, { outH: out.height, outT: out.talus, outF: out.floor, outS: out.strength },
    { uOrg: [x0 - plan.centre[0], y0 - plan.centre[1]], uStep: cell });
    prm.destroy();
    plan.tabs.destroy();
    if (!plan.face) {
        out.strength.destroy();
        delete out.strength;
    }
    return out;
}

/** Stage op 'caldera_collapse': params are caldera_collapse's (centre, rim_radius_m, floor_m or floor_below_rim_m,
 * cliffs, ...), plus inner_cones (cinder_cone objects, `at` from the centre) standing on the floor. rim_height_m
 * defaults to the mean of h within a cell of the rim circle on the first level, kept in 'caldera_rim_m' for the finer
 * levels. Lowers h and bed to the collapse surface; talus takes the apron's thickness; with cliffs, Sc takes the
 * strength the walls were built at (tan 40 degrees elsewhere); 'caldera_floor' marks the floor. */
export async function opCalderaCollapse(fields, level, params, seed = 0, ctx = null) {
    if (isPrepass(ctx)) return fields;
    const R = runnerOf(fields, ctx), P = prims(R);
    const p = { ...params };
    if (!has(p, 'seed')) p.seed = seed;
    const inner = pop(p, 'inner_cones', []);
    const below = pop(p, 'floor_below_rim_m', null);
    const key = stampKey('caldera_collapse', { ...params, seed: p.seed });
    const [x0, y0, cell, n] = levelWindow(level);
    if (!has(p, 'rim_height_m')) {
        if ('caldera_rim_m' in fields) {
            p.rim_height_m = (await P.stats(fields.caldera_rim_m)).mean;
        } else {
            // the cells within a cell of the rim circle (|r - rim_radius| < max(cell, 1e-6)): their mean height
            const ring = R.field(n, n, 1);
            R.run('volcanic/ring', {}, { outF: ring }, { uOrg: [x0 - Number(p.centre[0]), y0 - Number(p.centre[1])],
                uStep: cell, uR: Number(p.rim_radius_m), uW: Math.max(cell, 1e-6) });
            const s = await P.stats(fields.h, { mask: ring });
            ring.destroy();
            if (!s.count) throw new ValueError('caldera_collapse: the rim circle lies outside this level; pass rim_height_m');
            p.rim_height_m = s.sum / s.count;
        }
    }
    if (!has(p, 'floor_m')) {
        if (below === null || below === undefined) throw new ValueError('caldera_collapse: give floor_m (the field frame) or floor_below_rim_m');
        p.floor_m = Number(p.rim_height_m) - Number(below);
    }
    const out = await calderaCollapse(R, level, fields.h, { ...p, round_crest: !(key in fields) });
    fields.h = out.height;
    if ('bed' in fields) {
        const rockTop = ew(R, EW.SUB, out.height, out.talus);
        fields.bed = ew(R, EW.MIN, fields.bed, rockTop);
        rockTop.destroy();
    }
    if ('talus' in fields) fields.talus = ew(R, EW.MAX, fields.talus, out.talus);
    out.talus.destroy();
    if (truthy(inner)) {
        const c0 = p.centre;
        const cones = inner.map((c) => ({ ...c, at: [Number(c0[0]) + Number(c.at[0]), Number(c0[1]) + Number(c.at[1])] }));
        const grid = levelGrid(level);
        const h = copyOf(fields.h);
        await stackPiles(R, h, grid, [[0, grid.h]], cones, Number(p.floor_m), !(key in fields));
        fields.h = h;
    }
    if (out.strength) {
        fields.Sc = ew(R, EW.STRENGTH, out.strength, null, null, null, Math.tan(radians(33.0)), Math.tan(radians(40.0)));
        out.strength.destroy();
    }
    fields[key] = out.floor;
    fields.caldera_floor = copyOf(out.floor);
    fields.caldera_rim_m = Gd.fill(R, [n, n], Math.fround(Number(p.rim_height_m)));
    pullBand(fields, ctx);
    return fields;
}


// ====================================================================== the surroundings (design 4.7, 5) ===

export const SETTING_DEFAULTS = Object.freeze({ centre: [0.0, 0.0], basin_m: 12000.0, ramp_m: 6000.0, cover: 0.6,
    patch_m: 9000.0, texture: 0.35, U_m_per_yr: 3e-3, start_m: 600.0, start_roughness: 0.4, keep_m: null, far_m: null,
    tilt_azimuth_deg: 0.0, tilt: 0.0, plain: 0.0, plain_m: 0.0, plain_slope: 0.0, plain_slope_up: null,
    plain_down_azimuth_deg: 180.0, plain_extent_m: 30000.0, open_azimuth_deg: null, open_half_deg: 60.0, plain_k: 1.0,
    plain_rough_m: 0.0, plain_rough_scale_m: 2500.0, plain_blend_m: 25.0, plain_radius_m: null, plain_taper_m: 8000.0,
    shield_m: 0.0, shield_radius_m: 1500.0, plain_fill_max_m: null, plain_rough_inner: null });

/** Python's statistics.NormalDist().inv_cdf(p) (Wichura's AS241, as statistics._normal_dist_inv_cdf computes it). */
export function normalInvCdf(p) {
    const q = p - 0.5;
    let num, den, r;
    if (Math.abs(q) <= 0.425) {
        r = 0.180625 - q * q;
        num = (((((((2.5090809287301226727e+3 * r + 3.3430575583588128105e+4) * r + 6.7265770927008700853e+4) * r +
            4.5921953931549871457e+4) * r + 1.3731693765509461125e+4) * r + 1.9715909503065514427e+3) * r +
            1.3314166789178437745e+2) * r + 3.3871328727963666080e+0) * q;
        den = (((((((5.2264952788528545610e+3 * r + 2.8729085735721942674e+4) * r + 3.9307895800092710610e+4) * r +
            2.1213794301586595867e+4) * r + 5.3941960214247511077e+3) * r + 6.8718700749205790830e+2) * r +
            4.2313330701600911252e+1) * r + 1.0);
        return num / den;
    }
    r = q <= 0.0 ? p : 1.0 - p;
    r = Math.sqrt(-Math.log(r));
    if (r <= 5.0) {
        r = r - 1.6;
        num = (((((((7.7454501427834140764e-4 * r + 2.2723844989269184583e-2) * r + 2.4178072517745061177e-1) * r +
            1.2704582524523683826e+0) * r + 3.6478483247632045505e+0) * r + 5.7694972214606914055e+0) * r +
            4.6303378461565452959e+0) * r + 1.4234371107496835773e+0);
        den = (((((((1.0507500716444168432e-9 * r + 5.4759380849953449460e-4) * r + 1.5198666563616457197e-2) * r +
            1.4810397642748007459e-1) * r + 6.8976733498510000455e-1) * r + 1.6763848301838038494e+0) * r +
            2.0531916266377588219e+0) * r + 1.0);
    } else {
        r = r - 5.0;
        num = (((((((2.0103343992922881326e-7 * r + 2.7115555687434875782e-5) * r + 1.2426609473880784386e-3) * r +
            2.6532189526576123093e-2) * r + 2.9656057182850489123e-1) * r + 1.7848265399172913358e+0) * r +
            5.4637849111641143699e+0) * r + 6.6579046435011037772e+0);
        den = (((((((2.0442631033899397856e-15 * r + 1.4215117583164458887e-7) * r + 1.8463183175100546818e-5) * r +
            7.8686913114561329059e-4) * r + 1.4875361290850614852e-2) * r + 1.3692988092273580531e-1) * r +
            5.9983220655588793769e-1) * r + 1.0);
    }
    let x = num / den;
    if (q < 0.0) x = -x;
    return x;
}

/** gradient-noise terms as the kernels' `ntab` reads them, for a grid: two texels each, [scale, seed] per term (the
 * lattice's integer base and the float32 offset of the grid's origin in doubles; the seed's low 32 bits). */
export function noiseTexels(grid, terms) {
    const out = new Float32Array(8 * Math.max(terms.length, 1));
    const bits = new Uint32Array(out.buffer);
    terms.forEach(([scale, seed], k) => {
        const bx = Math.floor(grid.ox / scale), by = Math.floor(grid.oy / scale);
        out.set([bx, by, grid.ox / scale - bx, grid.oy / scale - by], 8 * k);
        out[8 * k + 4] = grid.step / scale;
        bits[8 * k + 5] = u32of(seed);
    });
    return out;
}

/** fbm's octave terms: scale / 2^o at int(seed) * 7919 + 101 o + 17. */
export const fbmTerms = (scale, seed, octaves = 2) =>
    Array.from({ length: octaves }, (_, o) => [scale / 2.0 ** o, Math.trunc(seed) * 7919 + 101 * o + 17]);

/** _unit_fbm: core/world_noise.js fbm of unit standard deviation (3 x the field's 1/3) at a level's cells, on the GPU
 * (Blender's _world_field on its GPU device: field_gpu). A new field. */
export function unitFbm(R, level, wavelengthM, seed, octaves = 3) {
    const f = N.fieldGpu(R, { kind: 'fbm', wavelength_m: Number(wavelengthM), octaves: Math.trunc(octaves) }, level, Math.trunc(seed));
    const g = ew(R, EW.LERP, null, f, null, null, 0.0, 3.0, [f.h, f.w]);
    f.destroy();
    return g;
}

// the setting's numbers as kernels/volcanic/setting.wgsl reads them
function settingTexels(p, extra = {}) {
    const t = new Float32Array(40);
    const cover = Number(p.cover);
    const tcov = cover < 0.999 ? normalInvCdf(Math.min(Math.max(1.0 - cover, 1e-3), 1.0 - 1e-3)) : 0.0;
    const [tex, tey] = compass(Number(p.tilt_azimuth_deg));
    const [dex, dey] = compass(Number(p.plain_down_azimuth_deg));
    const s = Number(p.plain_slope), su = p.plain_slope_up === null || p.plain_slope_up === undefined ? s : Number(p.plain_slope_up);
    const s0 = Math.max(s, Number(p.plain_slope_up ?? 0.0) || 0.0);
    const inner = truthy(p.plain_rough_inner) ? p.plain_rough_inner : null;
    t.set([Number(p.basin_m), Number(p.ramp_m), cover < 0.999 ? 1 : 0, tcov], 0);
    t.set([Number(p.texture), p.open_azimuth_deg === null || p.open_azimuth_deg === undefined ? 0 : 1,
        radians(Number(p.open_azimuth_deg ?? 0.0)), Number(p.open_half_deg)], 4);
    t.set([Number(p.plain), Number(p.tilt), tex, tey], 8);
    t.set([Number(p.plain_m), Number(p.shield_m), Number(p.shield_radius_m), s], 12);
    t.set([su, dex, dey, Number(p.plain_extent_m)], 16);
    t.set([Number(p.plain_rough_m), s0, inner ? 1 : 0, inner ? num(inner.factor, 0.3) : 0.0], 20);
    t.set([inner ? Number(inner.r0_m) : 0.0, inner ? Number(inner.r1_m) : 0.0,
        p.plain_radius_m === null || p.plain_radius_m === undefined ? -1.0 : Number(p.plain_radius_m), Number(p.plain_taper_m)], 24);
    t.set([extra.keep ?? 0.0, extra.far ?? 0.0, extra.plain ? 1 : 0, Number(p.plain_k)], 28);
    t.set([Number(p.start_m), Number(p.start_roughness), extra.pk ?? 1.0, Number(p.plain_blend_m)], 32);
    t.set([Number(p.plain_fill_max_m ?? 0.0) || 0.0, 0.3 * Number(p.basin_m), extra.limit ? 1 : 0, extra.apron ? 1 : 0], 36);
    return t;
}

const OUT_DUMMIES = new WeakMap();

/** A runner's 1 x 1 stand-ins for the images a kernel's mode does not write: never bound as samplers (core/gpu.js
 * refuses one field as a sampler and an image, or as two images, of one dispatch). */
export function outDummies(R) {
    let d = OUT_DUMMIES.get(R);
    if (!d) {
        d = { f: [R.field(1, 1, 1), R.field(1, 1, 1), R.field(1, 1, 1)], u: R.field(1, 1, 1, null, 'u32') };
        OUT_DUMMIES.set(R, d);
    }
    return d;
}

// one mode of kernels/volcanic/setting.wgsl at a level's cells: [outF, outG (modes 7 and 9)]
function settingRun(R, level, p, mode, inputs = {}, extra = {}) {
    const [x0, y0, cell, n] = levelWindow(level);
    const D = Gd.dummies(R);
    const prm = R.field(1, 10, 4, settingTexels(p, extra));
    const two = mode === 7 || mode === 9;
    const f = R.field(n, n, 1), g = two ? R.field(n, n, 1) : outDummies(R).f[0];
    const c = [Number(p.centre[0]), Number(p.centre[1])];
    R.run('volcanic/setting', { a: inputs.a ?? D.f1, b: inputs.b ?? D.f1, c: inputs.c ?? D.f1, d: inputs.d ?? D.f1, prm },
        { outF: f, outG: g }, { uMode: mode, uOrg: [x0 - c[0], y0 - c[1]], uStep: cell }, groupsOf(n, n));
    prm.destroy();
    return two ? [f, g] : [f];
}

/** setting_shape: the uplift shape of a volcano's surroundings, about 0..1 at the level's cells (a new field). */
export function settingShape(R, level, params, seed) {
    const p = { ...SETTING_DEFAULTS, ...(params ?? {}) };
    const a = Number(p.cover) < 0.999 ? unitFbm(R, level, Number(p.patch_m), Math.trunc(seed) + 501) : null;
    const b = Number(p.texture) > 0.0 ? unitFbm(R, level, Number(p.patch_m) / 3.0, Math.trunc(seed) + 503) : null;
    const [out] = settingRun(R, level, p, 0, { a, b });
    for (const f of [a, b]) if (f) f.destroy();
    return out;
}

/** plain_surface: setting_plain plus the apron's lobes and swells (world noise) at a level's cells (a new field). */
export function plainSurface(R, level, params, seed) {
    const p = { ...SETTING_DEFAULTS, ...(params ?? {}) };
    let a = null, b = null;
    if (Number(p.plain_rough_m) > 0.0) {
        const sc = Number(p.plain_rough_scale_m);
        a = unitFbm(R, level, sc, Math.trunc(seed) + 37, 4);
        b = unitFbm(R, level, 0.25 * sc, Math.trunc(seed) + 39, 3);
    }
    const [out] = settingRun(R, level, p, 1, { a, b });
    for (const f of [a, b]) if (f) f.destroy();
    return out;
}

/** _apron_limit: 1 where the apron may reach (a new field). */
export function apronLimit(R, level, params) {
    const p = { ...SETTING_DEFAULTS, ...(params ?? {}) };
    return settingRun(R, level, p, 2)[0];
}

/** _reach: 1 on the 8-connected parts of `mask` (a u32 field, nonzero on) holding a seed, 0 elsewhere: the vent's cell
 * when the level holds it, plus `seeds` (a float field, > 0.5 on); every part when no part holds a seed. A new field. */
export async function reach(R, mask, level, params, seeds = null) {
    const P = prims(R), D = Gd.dummies(R);
    const { labels, count } = await P.label(mask);
    const [x0, y0, cell, n] = levelWindow(level);
    if (!count) {
        labels.destroy();
        return Gd.fill(R, [n, n], 0.0);
    }
    const c = (params ?? {}).centre ?? [0.0, 0.0];
    const i = Math.floor((Number(c[0]) - x0) / cell), j = Math.floor((Number(c[1]) - y0) / cell);
    const vent = i >= 0 && i < n && j >= 0 && j < n ? [i, j] : [-1, -1];
    const keep = R.field(1, count + 1, 1, null, 'u32');
    R.run('volcanic/reach', { lab: labels, seeds: seeds ?? D.f1 }, { keep, outF: outDummies(R).f[0] },
        { uMode: 0, uSeeds: seeds ? 1 : 0, uVent: vent, uAll: 0 }, groupsOf(n, n));
    const k = await R.read(keep);
    let any = false;
    for (let L = 1; L <= count; L++) if (k[L]) { any = true; break; }
    const out = R.field(n, n, 1);
    R.run('volcanic/reach', { lab: labels, seeds: D.f1 }, { keep, outF: out }, { uMode: 1, uSeeds: 0, uVent: [-1, -1], uAll: any ? 0 : 1 },
        groupsOf(n, n));
    keep.destroy();
    labels.destroy();
    return out;
}

/** Stage op 'volcano_setting': the ground a volcano grows on, for a fluvial stage to carve before the cone is stamped
 * (volcanic.py op_volcano_setting; its docstring holds). On the coarsest level U = U_m_per_yr x the shape and, with a
 * plain, the plain pinned as the ranges' base level for the fluvial stage of the same pass (ctx.pins, _setting); on
 * the fresh pass h = bed = the plain plus the shape scaled to start_m, roughened. Every level gets K_factor (plain_k)
 * and 'volcano_far'. */
export async function opVolcanoSetting(fields, level, params, seed = 0, ctx = null) {
    const R = runnerOf(fields, ctx), P = prims(R);
    const p = { ...SETTING_DEFAULTS, ...(params ?? {}) };
    const grow = ctx === null || ctx === undefined || (ctx.role ?? 'grow') === 'grow';
    const fresh = ctx === null || ctx === undefined || !!ctx.fresh;
    const [, , , n] = levelWindow(level);
    const shape = settingShape(R, level, p, seed);
    const own = [shape];
    if (grow) fields.U = ew(R, EW.LERP, null, shape, null, null, 0.0, Number(p.U_m_per_yr));
    if (Number(p.plain_k) !== 1.0) fields.K_factor = settingRun(R, level, p, 4, { a: shape })[0];
    let plainW = null;
    if (Number(p.plain_m) !== 0.0 || Number(p.plain_slope) !== 0.0) {
        const low = P.where(shape, '<', 0.12);
        const rc = await reach(R, low, level, p);
        low.destroy();
        const lim = apronLimit(R, level, p);
        plainW = settingRun(R, level, p, 5, { a: shape, b: rc, c: lim })[0];
        rc.destroy();
        lim.destroy();
        own.push(plainW);
    }
    const plain = plainW !== null || fresh ? plainSurface(R, level, p, seed) : null;
    if (plain) own.push(plain);
    let smax = null;
    if (fresh) {
        const nf = N.fieldGpu(R, { kind: 'fbm', wavelength_m: 0.3 * Number(p.patch_m), octaves: 5 }, level, Math.trunc(seed) + 31);
        smax = (await P.stats(shape)).max;
        const pk = Math.max(smax, 1e-9);
        const h0 = settingRun(R, level, p, 6, { a: plain, b: shape, c: nf }, { pk })[0];
        nf.destroy();
        fields.h = h0;
        fields.bed = copyOf(h0);
    }
    if (grow && plainW !== null && ctx && Number(p.U_m_per_yr) > 0.0) {
        smax = smax ?? (await P.stats(shape)).max;
        if (smax > 0.0) {                         // only when there are ranges to grow on it
            const edge = FL.edgePins(R, n, fields.h);
            const [w, ph] = settingRun(R, level, p, 7, { a: edge.pin_w, b: edge.pin_h, c: plainW, d: plain });
            edge.pin_w.destroy();
            edge.pin_h.destroy();
            releaseSettingPins(ctx);
            ctx.pins = { pin_w: w, pin_h: ph, A_in: edge.A_in, qs_in: edge.qs_in, _setting: true };
        }
    }
    if (grow) {
        fields.volcano_far = Gd.fill(R, [n, n], 1.0);
    } else {
        const keep = Number(p.keep_m ?? p.basin_m);
        const far = Number(p.far_m ?? Number(p.basin_m) + Number(p.ramp_m));
        fields.volcano_far = settingRun(R, level, p, 3, { a: shape }, { keep, far, plain: plainW !== null })[0];
    }
    for (const f of own) if (!f.destroyed) f.destroy();
    return fields;
}

// volcano_setting's pins (its own fields) released when they are dropped
function releaseSettingPins(ctx) {
    const pins = ctx?.pins;
    if (pins && pins._setting) for (const k of ['pin_w', 'pin_h', 'A_in', 'qs_in']) if (pins[k] && !pins[k].destroyed) pins[k].destroy();
}

/** Stage op 'volcano_plain': the apron and lava plain a volcano spreads over its surroundings, filling the low ground
 * its flows reach (volcanic.py op_volcano_plain): h = smooth_max(h, plain) over the parts of (plain above the ground)
 * connected to the vent or to what the parent filled, dilated by 2 cells, fading out in deep valleys and beyond the
 * apron's reach; the fill is deposit; 'apron' marks the reach. Skips the coarsest level's pre-passes. */
export async function opVolcanoPlain(fields, level, params, seed = 0, ctx = null) {
    if (ctx?.pins?._setting) {
        releaseSettingPins(ctx);
        ctx.pins = null;                          // volcano_setting's plain pins served the fluvial stage of this pass
    }
    if (isPrepass(ctx)) return fields;
    const R = runnerOf(fields, ctx), P = prims(R);
    const p = { ...SETTING_DEFAULTS, ...(params ?? {}) };
    const plain = plainSurface(R, level, p, seed);
    const keep = p.plain_radius_m !== null && p.plain_radius_m !== undefined ? apronLimit(R, level, p) : null;
    const h = fields.h;
    const [mask, seeds] = settingRun(R, level, p, 9, { a: h, b: plain, c: 'apron' in fields ? fields.apron : null },
        { apron: 'apron' in fields });
    const mu = P.where(mask, '>', 0.5);
    mask.destroy();
    const rc = await reach(R, mu, level, p, seeds);
    mu.destroy();
    seeds.destroy();
    const dil = P.dilate(rc, 2);
    const fill = settingRun(R, level, p, 8, { a: h, b: plain, c: dil, d: keep }, { limit: keep !== null })[0];
    for (const f of [dil, plain, keep]) if (f) f.destroy();
    fields.apron = rc;
    fields.h = ew(R, EW.ADD, h, fill);
    fields.deposit = 'deposit' in fields ? ew(R, EW.ADD, fields.deposit, fill) : fill;
    if (fields.deposit !== fill) fill.destroy();
    pullBand(fields, ctx);
    return fields;
}


// =================================================================================== radial streaks, ravines ===

/** radial_streaks (or with rills, cone_rills' cone) on a grid about centre: unit-RMS streaks running down a cone in
 * bands of log radius, wandering sideways, sparse troughs only. A new field (mode 0), or the rills combined into
 * `into` over rect (mode 1). */
function streaksRun(R, grid, centre, st, seed, opts = {}) {
    const k = st.k ?? [40, 160], decay = num(st.decay, 0.6), rr = (st.r_m ?? [1000.0, 10000.0]).map(Number);
    const bands = Math.trunc(num(st.bands, 3));
    const wander = num(st.wander_m, 0.0), wsc = num(st.wander_scale_m, 2000.0);
    const sparse = st.sparse === undefined || st.sparse === null ? null : Number(st.sparse);
    const tabs = new AzTables();
    for (let b = 0; b < bands; b++) tabs.add(azimuthNoiseTable(Math.trunc(seed), 600 + b, Math.trunc(k[0]), Math.trunc(k[1]), decay));
    const l0 = Math.log(rr[0]), l1 = Math.log(rr[1]);
    const wid = (l1 - l0) / Math.max(bands, 1);
    const prm = R.field(1, 3, 4, Float32Array.from([l0, l1, wid, bands, sparse === null ? 0 : 1, sparse ?? 0.0, wander,
        0.25 * wsc, 0, opts.fade ?? 0.0, opts.rcr ?? 0.0, opts.R ?? 0.0]));
    const ntab = R.field(1, 4, 4, noiseTexels(grid, fbmTerms(wsc, Math.trunc(seed) + 613, 2)));
    const out = opts.into ?? R.field(grid.h, grid.w, 1);
    const rect = opts.rect ?? [0, 0, grid.w, grid.h];
    R.run('volcanic/streaks', { azt: tabs.field(R), prm, ntab }, { outF: out },
        { uMode: opts.into ? 1 : 0, uOrg: [grid.ox - Number(centre[0]), grid.oy - Number(centre[1])], uStep: grid.step, uRect: rect },
        opts.into ? groupsOf(rect[2] - rect[0], rect[3] - rect[1]) : groupsOf(grid.w, grid.h));
    prm.destroy();
    ntab.destroy();
    tabs.destroy();
    return out;
}

/** radial_streaks at a level's cells about centre (volcanic.py; st: { k, decay, r_m, bands, wander_m, wander_scale_m,
 * sparse }). A new field. */
export function radialStreaks(R, level, centre, st, seed) {
    return streaksRun(R, levelGrid(level), centre, st, seed);
}

/** cone_rills: rills down cinder cones' flanks, metres to cut (>= 0), on a grid (volcanic.py cone_rills). A new field. */
export function coneRills(R, grid, blocks, cones, depthM = 1.5, spacingM = 25.0, seed = 0) {
    const out = Gd.fill(R, [grid.h, grid.w], 0.0);
    cones.forEach((c, k) => {
        const W = num(c.width_m, 800.0);
        const Rr = 0.5 * W * Math.max(1.0, num(c.elongation, 1.0));
        const rcr = 0.5 * W * num(c.crater_ratio, 0.4);
        const fade = Math.exp(-(Number(c.kappa_t_m2 ?? 0.0) || 0.0) / 400.0);
        if (fade < 0.05 || Rr <= rcr * 1.5) return;
        const rMid = 0.5 * (rcr + Rr);
        const kMid = TAU * rMid / Number(spacingM);
        const at = [Number(c.at[0]), Number(c.at[1])];
        const sd = Math.trunc(num(c.seed, 0)) * 13 + Math.trunc(seed) * 7 + k;
        const st = { k: [Math.max(Math.trunc(0.5 * kMid), 4), Math.max(Math.trunc(2.0 * kMid), 8)], decay: 0.5, r_m: [rcr, Rr],
            bands: 2, wander_m: 4.0, wander_scale_m: 80.0, sparse: 0.0 };
        for (const [lo, hi] of blocks) {
            const sl = grid.support(at, 1.05 * Rr, lo, hi);
            if (!sl || !(sl[1] > sl[0] && sl[3] > sl[2])) continue;
            streaksRun(R, grid, at, st, sd, { into: out, rect: [sl[2], sl[0], sl[3], sl[1]], fade: Number(depthM) * fade, rcr, R: Rr });
        }
    });
    return out;
}

/** ravine_cut: the depth (>= 0) of radial ravines cut into a cone at a level's cells (volcanic.py). A new field. */
export function ravineCut(R, level, centre, ravines, seed = 0) {
    const [x0, y0, cell, n] = levelWindow(level);
    const t = new Float32Array(8 * Math.max(ravines.length, 1));
    const bits = new Uint32Array(t.buffer);
    ravines.forEach((rv, k) => {
        t.set([radians(Number(rv.azimuth_deg)), Number(rv.r_m[0]), Number(rv.r_m[1]), Number(rv.depth_m)], 8 * k);
        t.set([Number(rv.width_m), num(rv.wander_m, 0.0), k, 0.0], 8 * k + 4);
        bits[8 * k + 7] = u32of(Math.trunc(seed) + 97 + k);
    });
    const rtab = R.field(1, 2 * Math.max(ravines.length, 1), 4, t);
    const out = R.field(n, n, 1);
    R.run('volcanic/ravines', { rtab }, { outF: out }, { uOrg: [x0 - Number(centre[0]), y0 - Number(centre[1])], uStep: cell,
        uCount: ravines.length });
    rtab.destroy();
    return out;
}

/** The ravines a 'volcano_age' stage cuts: params ravines plus ravine_field's, drawn (volcanic.py ravines_of). */
export function ravinesOf(params, seed) {
    const out = (params.ravines ?? []).map((rv) => ({ ...rv }));
    const f = params.ravine_field;
    if (truthy(f)) {
        const rng = rngOf(seed, 93);
        for (let i = 0; i < Math.trunc(num(f.count, 4)); i++) {
            const r0 = rng.uniform(Number(f.r_m[0]), Number(f.r_m[1]));
            out.push({ azimuth_deg: rng.uniform(0.0, 360.0), r_m: [r0, r0 + rng.uniform(Number(f.length_m[0]), Number(f.length_m[1]))],
                depth_m: rng.uniform(Number(f.depth_m[0]), Number(f.depth_m[1])),
                width_m: rng.uniform(Number(f.width_m[0]), Number(f.width_m[1])), wander_m: num(f.wander_m, 0.0) });
        }
    }
    return out;
}


// ===================================================================================== rubble and rills ===

/** lava_rubble: an aa flow's rubbly top on a grid (metres to add, >= 0): ridged gradient noise at each scale. */
export function lavaRubble(R, grid, scales = [8.0, 3.0, 1.2], amps = [1.2, 0.6, 0.3], seed = 0) {
    const D = Gd.dummies(R);
    const terms = scales.map((s, i) => [Number(s), Math.trunc(seed) * 7907 + 131 * i + 29]);
    const ntab = R.field(1, 2 * Math.max(terms.length, 1), 4, noiseTexels(grid, terms));
    const af = R.field(1, Math.max(amps.length, 1), 1, Float32Array.from(amps.length ? amps.map(Number) : [0]));
    const out = R.field(grid.h, grid.w, 1);
    R.run('volcanic/rubble', { ntab, amps: af, lava: D.f1, rub: D.f1 }, { outF: out }, { uMode: 0, uCount: terms.length });
    ntab.destroy();
    af.destroy();
    return out;
}

// stampAdd on a temporary Fields holding h = 0 (and the stamp's own field when inherited): the shape's share here
async function tempStamp(fields, level, key, evaluate, ctx, block = true) {
    const R = fields.R;
    const { Fields } = await import('../core/fields.js');
    const [, , , n] = levelWindow(level);
    const tmp = new Fields(level, { h: Gd.fill(R, [n, n], 0.0) }, R);
    if (key in fields) tmp[key] = copyOf(fields[key]);
    const here = await stampAdd(tmp, level, key, evaluate, 1, ctx, null, block);
    release(here);
    return tmp;
}

/** Stage op 'lava_rubble': the flows' rough aa top on the levels fine enough to show it, where the 'lava' field says
 * a flow lies, as strong as its footprint there, into h and bed (stampAdd: the same world function on every level). */
export async function opLavaRubble(fields, level, params, seed = 0, ctx = null) {
    if (isPrepass(ctx) || !('lava' in fields)) return fields;
    const R = runnerOf(fields, ctx);
    const sc = (params.scales_m ?? [8.0, 3.0, 1.2]).map(Number), am = (params.amps_m ?? [1.2, 0.6, 0.3]).map(Number);
    const sd = Math.trunc(Number(params.seed ?? seed));
    const key = stampKey('lava_rubble', { scales_m: sc, amps_m: am, seed: sd });
    const tmp = await tempStamp(fields, level, key, async (grid) => ({ h: lavaRubble(R, grid, sc, am, sd) }), ctx);
    const D = Gd.dummies(R);
    const add = R.like(fields.h);
    R.run('volcanic/rubble', { ntab: D.f1, amps: D.f1, lava: fields.lava, rub: tmp.h }, { outF: add }, { uMode: 1, uCount: 0 });
    fields.h = ew(R, EW.ADD, fields.h, add);
    if ('bed' in fields) fields.bed = ew(R, EW.ADD, fields.bed, add);
    add.destroy();
    fields[key] = copyOf(tmp[key]);
    tmp.dispose();
    pullBand(fields, ctx);
    return fields;
}

/** Stage op 'cone_rills': cone_rills cut into h on the levels fine enough to hold them (stampAdd), in the loose scoria
 * only (h never below bed). params: the cinder_cones stage's cones / field / kappa_m2_per_yr, depth_m, spacing_m. */
export async function opConeRills(fields, level, params, seed = 0, ctx = null) {
    if (isPrepass(ctx)) return fields;
    const R = runnerOf(fields, ctx);
    const cones = conesOf(params, seed);
    const d = num(params.depth_m, 1.5), sp = num(params.spacing_m, 25.0);
    const key = stampKey('cone_rills', { ...params, seed });
    const tmp = await tempStamp(fields, level, key, async (grid, blocks) => {
        const c = coneRills(R, grid, blocks, cones, d, sp, seed);
        const neg = ew(R, EW.LERP, null, c, null, null, 0.0, -1.0);
        c.destroy();
        return { h: neg };
    }, ctx, false);
    let h = ew(R, EW.ADD, fields.h, tmp.h);
    if ('bed' in fields) {
        const hb = ew(R, EW.MAX, h, fields.bed);
        h.destroy();
        h = hb;
    }
    fields.h = h;
    fields[key] = copyOf(tmp[key]);
    tmp.dispose();
    pullBand(fields, ctx);
    return fields;
}


// ============================================================================== lakes, with dry craters ===

export const LAKE_NONE = -1.0e6;                // 'lake_level_m' off the lakes

// kernels/volcanic/lakes.wgsl, one mode at the cells of `lab` (or of ins.a): out fields as given ({ outF, outG, outH }),
// stand-ins of their own elsewhere; stats the atomic per-label words
function lakesRun(R, mode, lab, ins = {}, outs = {}, u = {}, stats = null, flags = null) {
    const D = Gd.dummies(R), O = outDummies(R);
    const ref = lab ?? ins.a;
    R.run('volcanic/lakes', { a: ins.a ?? D.f1, b: ins.b ?? D.f1, c: ins.c ?? D.f1, d: ins.d ?? D.f1, lab: lab ?? D.u1,
        flags: flags ?? D.u1 }, { stats: stats ?? O.u, outF: outs.outF ?? O.f[0], outG: outs.outG ?? O.f[1], outH: outs.outH ?? O.f[2] },
    { uMode: mode, uOrg: u.uOrg ?? [0, 0], uStep: u.uStep ?? 1.0, uR: u.uR ?? -1.0, uK: u.uK ?? 0.0, uBand: u.uBand ?? 0,
        uLabel: u.uLabel ?? 0 }, groupsOf(ref.w, ref.h));
}

/** A float 0 / 1 mask (kernels/volcanic/mask.wgsl): mode 0 lab == L, 1 lab != 0, 2 f > t. A new field. */
function maskOf(R, mode, { lab = null, f = null, L = 0, t = 0.0 } = {}) {
    const D = Gd.dummies(R);
    const ref = lab ?? f;
    const out = R.field(ref.h, ref.w, 1);
    R.run('volcanic/mask', { lab: lab ?? D.u1, f: f ?? D.f1 }, { outF: out }, { uMode: mode, uLabel: L, uT: t }, groupsOf(ref.w, ref.h));
    return out;
}

/** _carried_lakes: water on this level under the parent's lakes (the inherited lake levels grown by one cell), or null
 * when there are none. A new field. */
async function carriedLakes(R, fields) {
    if (!('lake_level_m' in fields)) return null;
    const P = prims(R);
    const s = await P.stats(fields.lake_level_m);
    if (!(s.max > 0.5 * LAKE_NONE)) return null;
    const g = P.dilate(fields.lake_level_m, 1);
    const out = R.like(fields.h);
    lakesRun(R, 4, null, { a: g, b: fields.h }, { outF: out });
    g.destroy();
    return out;
}

// the largest labels by area, at most `count` (np.argsort(np.where(lake, area, -1))[::-1][:count]); ties of equal
// area go to the larger label, as a stable ascending sort reversed gives them
function largest(lake, area, count) {
    const idx = Array.from({ length: lake.length }, (_, i) => i).filter((i) => lake[i]);
    idx.sort((a, b) => (area[b] - area[a]) || (b - a));
    return new Set(idx.slice(0, count));
}

/** Stage op 'volcano_lakes': the lakes of a volcanic or cratered landscape (volcanic.py op_volcano_lakes; its
 * docstring holds): dry craters (and every cinder cone's crater with dry_cones), a depression of the design's depth
 * and the given area holds water at its spill level (mode 'lake') within lake_radius_m, at most max_lakes (chosen on
 * the coarsest level, kept below), every other one filled with sediment; playas in dry craters; the parent's lakes
 * carried down. Writes water and lake_level_m; the fill goes into h and deposit. Skips the coarsest level's pre-passes. */
export async function opVolcanoLakes(fields, level, params, seed = 0, ctx = null) {
    if (isPrepass(ctx)) return fields;
    const R = runnerOf(fields, ctx), P = prims(R);
    const HY = await import('./hydro.js');
    const p = { ...(params ?? {}) };
    if (truthy(p.dry_cones)) {
        p.dry = [...(p.dry ?? []), ...conesOf(p.dry_cones, seed).map((c) => ({ at: c.at,
            radius_m: 0.5 * num(c.width_m, 800.0) * num(c.crater_ratio, 0.4) + 20.0 }))];
    }
    const [x0, y0, cell, n] = levelWindow(level);
    const h = fields.h;
    const sea = ctx?.sea_level ?? null;
    const { filled } = await HY.fillDepressions(h, { seaLevel: sea });
    const depth = ew(R, EW.SUB, filled, h);
    filled.destroy();
    const dm = P.where(depth, '>', 1e-4);
    const { labels: lab, count: nlab } = await P.label(dm);
    dm.destroy();
    const water = Gd.fill(R, [n, n], 0.0), add = Gd.fill(R, [n, n], 0.0);
    let nl = 0, filledAny = false;
    const child = bandPins(ctx) !== null;
    const band = Math.trunc(level.band ?? 16);
    if (nlab) {
        // per depression: its deepest depth, area, whether it reaches the lake radius and the border band
        const init = new Uint32Array(5 * (nlab + 1));
        for (let L = 0; L <= nlab; L++) init[5 * L + 4] = 0xFFFFFFFF;
        const stats = R.field(1, 5 * (nlab + 1), 1, init, 'u32');
        const c0 = p.centre ?? [0.0, 0.0];
        const lr = p.lake_radius_m === undefined || p.lake_radius_m === null ? -1.0 : Number(p.lake_radius_m);
        lakesRun(R, 0, lab, { a: depth }, {}, { uOrg: [x0 - Number(c0[0]), y0 - Number(c0[1])], uStep: cell, uR: lr,
            uBand: child ? band : -1 }, stats);
        lakesRun(R, 1, lab, { a: depth }, {}, {}, stats);
        const st = await R.read(stats);
        stats.destroy();
        const F = new Float32Array(st.buffer);
        const maxd = new Float64Array(nlab + 1), area = new Float64Array(nlab + 1), near = new Uint8Array(nlab + 1);
        const inBand = new Uint8Array(nlab + 1), deepest = new Int32Array(nlab + 1);
        for (let L = 1; L <= nlab; L++) {
            maxd[L] = F[5 * L];
            area[L] = st[5 * L + 1] * cell ** 2;
            near[L] = st[5 * L + 2];
            inBand[L] = st[5 * L + 3];
            deepest[L] = st[5 * L + 4];
        }
        const rel = ctx?.shared?.relief ?? null;
        let thr;
        if (p.min_depth_m !== undefined && p.min_depth_m !== null) thr = Number(p.min_depth_m);
        else {
            let r0 = rel;
            if (!r0) {
                const s = await P.stats(h);
                r0 = s.max - s.min;
            }
            thr = HY.depressionThreshold(r0);
        }
        const dry = new Uint8Array(nlab + 1);
        const playa = new Map();
        if (truthy(p.dry)) {
            for (const c of p.dry) {
                const amin = Number(c.min_area_m2 ?? 0.02 * Math.PI * Number(c.radius_m) ** 2);
                for (let L = 1; L <= nlab; L++) {
                    const k = deepest[L];
                    const xs = x0 + ((k % n) + 0.5) * cell, ys = y0 + (Math.floor(k / n) + 0.5) * cell;
                    if (!(Math.hypot(xs - Number(c.at[0]), ys - Number(c.at[1])) < Number(c.radius_m))) continue;
                    if (!(area[L] >= amin)) continue;
                    dry[L] = 1;
                    if (truthy(c.playa_frac)) playa.set(L, Number(c.playa_frac));
                }
            }
        }
        let lake = new Uint8Array(nlab + 1);
        if ((p.mode ?? 'lake') === 'lake') {
            for (let L = 1; L <= nlab; L++) {
                let ok = maxd[L] > thr && area[L] >= num(p.min_area_m2, 0.0) && !dry[L] && !(child && inBand[L]);
                if (ok && p.max_area_m2 !== undefined && p.max_area_m2 !== null) ok = area[L] <= Number(p.max_area_m2);
                if (ok && lr >= 0.0) ok = near[L] > 0;
                lake[L] = ok ? 1 : 0;
            }
            if (p.max_lakes !== undefined && p.max_lakes !== null) {
                let cnt = 0;
                for (let L = 1; L <= nlab; L++) cnt += lake[L];
                if (cnt > Math.trunc(p.max_lakes)) {
                    const keepSet = largest(lake, area, Math.trunc(p.max_lakes));
                    lake = new Uint8Array(nlab + 1);
                    for (const L of keepSet) lake[L] = 1;
                }
                if (child) {
                    // the lakes were chosen on the coarsest level: keep the depressions holding the parent's lakes
                    const held = await carriedLakes(R, fields);
                    lake = new Uint8Array(nlab + 1);
                    if (held) {
                        const hm = R.field(1, nlab + 1, 1, null, 'u32');
                        lakesRun(R, 8, lab, { a: held }, {}, { uK: 1e-3 }, hm);
                        held.destroy();
                        const hc = await R.read(hm);
                        hm.destroy();
                        for (let L = 1; L <= nlab; L++) if (hc[L]) lake[L] = 1;
                    }
                }
            }
        }
        lake[0] = 0;
        const flags = new Uint32Array(nlab + 1);
        for (let L = 1; L <= nlab; L++) flags[L] = (lake[L] ? 1 : 0) | (dry[L] ? 2 : 0) | (inBand[L] ? 4 : 0);
        const ff = R.field(1, nlab + 1, 1, flags, 'u32');
        const ed = child ? Gd.edgeDistance(R, n) : null;
        const hero = level.role === 'hero' && p.hero_pits === 'keep';
        lakesRun(R, 2, lab, { a: depth, b: ed }, { outF: water, outG: add }, { uBand: (child ? 1 : 0) | (hero ? 2 : 0) }, null, ff);
        ff.destroy();
        if (ed) ed.destroy();
        for (const [L, frac] of playa) {
            if (inBand[L]) continue;               // a hero window inside the crater holds only part of it
            const cells = maskOf(R, 0, { lab, L });
            const top = await P.quantile(h, Math.min(Math.max(frac + 0.06, 0.0), 0.95), { mask: cells, dtype: 'float64' });
            const s = await P.stats(h, { mask: cells });
            const k = Math.max(0.08 * (s.max - s.min), 1e-3);
            cells.destroy();
            lakesRun(R, 3, lab, { a: h }, { outF: add }, { uR: top, uK: k, uLabel: L });
        }
        for (let L = 1; L <= nlab; L++) nl += lake[L];
        filledAny = true;
    }
    lab.destroy();
    depth.destroy();
    const carried = await carriedLakes(R, fields) ?? Gd.fill(R, [n, n], 0.0);
    const h2 = R.like(h), w2 = R.like(h), ll = R.like(h);
    lakesRun(R, 5, null, { a: h, b: add, c: water, d: carried }, { outF: h2, outG: w2, outH: ll });
    carried.destroy();
    water.destroy();
    const addStats = filledAny ? await P.stats(add, { mask: add }) : { count: 0 };
    fields.h = h2;
    if (addStats.count) fields.deposit = 'deposit' in fields ? ew(R, EW.ADD, fields.deposit, add) : copyOf(add);
    add.destroy();
    fields.water = w2;
    fields.lake_level_m = ll;
    if (ctx && typeof ctx.log === 'function') {
        ctx.log(`[terrain.volcanic] lakes on ${n}^2 @ ${pyFormat(cell, '.3g')} m: ${nl} lakes, ` +
            `${pyFormat(addStats.count / (n * n), '.4f')} of the level filled with sediment, ${(p.dry ?? []).length} dry craters`);
    }
    return fields;
}

/** Stage op 'caldera_lake': a lake at its own level in a caldera, not at its spill (volcanic.py op_caldera_lake; its
 * docstring holds): the level below the caldera's lowest notch on the first level, kept in 'caldera_lake_m'; the water
 * the connected region under the level that holds the centre; every other closed depression filled with sediment.
 * Skips the coarsest level's pre-passes. */
export async function opCalderaLake(fields, level, params, seed = 0, ctx = null) {
    if (isPrepass(ctx)) return fields;
    const R = runnerOf(fields, ctx), P = prims(R);
    const HY = await import('./hydro.js');
    const [x0, y0, cell, n] = levelWindow(level);
    const h = fields.h;
    const sea = ctx?.sea_level ?? null;
    let L;
    if ('caldera_lake_m' in fields) L = await P.median(fields.caldera_lake_m);
    else if (params.level_m !== undefined && params.level_m !== null) L = Number(params.level_m);
    else {
        if (!('caldera_rim_m' in fields)) throw new ValueError("caldera_lake: no 'caldera_rim_m' (run caldera_collapse first) and no level_m");
        L = (await P.stats(fields.caldera_rim_m)).mean - num(params.below_rim_m, 300.0);
    }
    const c = params.centre ?? [0.0, 0.0];
    const fi = (Number(c[0]) - x0) / cell - 0.5, fj = (Number(c[1]) - y0) / cell - 0.5;
    if (!('caldera_lake_m' in fields) && 'caldera_floor' in fields) {
        const mf = maskOf(R, 2, { f: fields.caldera_floor, t: 0.5 });
        const any = (await P.stats(mf, { mask: mf })).count > 0;
        if (any) {
            const { filled } = await HY.fillDepressions(h, { seaLevel: sea });
            const spill = await P.median(filled, { mask: mf, dtype: 'float64' });
            filled.destroy();
            if (L > spill - 2.0) {
                ctx?.log?.(`[terrain.volcanic] caldera lake: the rim's lowest notch is at ${pyFormat(spill, '.1f')} m: the lake at ` +
                    `${pyFormat(spill - 2.0, '.1f')} m, not ${pyFormat(L, '.1f')} m`);
                L = spill - 2.0;
            }
        }
        mf.destroy();
        fields.caldera_lake_m = Gd.fill(R, [n, n], Math.fround(L));
    }
    const below = whereLess(P, h, L);
    const { labels: lab, count } = await P.label(below);
    below.destroy();
    const water = Gd.fill(R, [n, n], 0.0);
    const Lhi = Math.fround(L), Llo = L - Lhi;
    if (count) {
        const ci = Math.min(Math.max(pyRound(fi), 0), n - 1), cj = Math.min(Math.max(pyRound(fj), 0), n - 1);
        const [kk] = await R.readRange(lab, cj * n + ci, 1);
        let k = kk;
        if (k === 0 && 'caldera_floor' in fields) {           // an island at the centre: the largest region on the floor
            const cnt = R.field(1, count + 1, 1, null, 'u32');
            lakesRun(R, 8, lab, { a: fields.caldera_floor }, {}, { uK: 0.5 }, cnt);
            const bc = await R.read(cnt);
            cnt.destroy();
            let best = -1, bi = 0;
            for (let i = 0; i <= count; i++) if (bc[i] > best) { best = bc[i]; bi = i; }
            if (best > 0) k = bi;
        }
        if (k > 0) lakesRun(R, 6, lab, { a: h }, { outF: water }, { uR: Lhi, uK: Llo, uLabel: k });
    }
    lab.destroy();
    // the surface over the lake (numpy's h + water is L there, exactly), its depressions, the caldera's own basin kept
    const surf = R.like(h);
    lakesRun(R, 7, null, { a: h, b: water }, { outF: surf }, { uR: Lhi });
    const { filled } = await HY.fillDepressions(surf, { seaLevel: sea });
    const depth = R.like(h);
    lakesRun(R, 9, null, { a: filled, b: surf }, { outF: depth });
    filled.destroy();
    surf.destroy();
    const dm = P.where(depth, '>', 1e-4);
    const { labels: dl, count: dn } = await P.label(dm);
    dm.destroy();
    let pit = depth;
    const wpos = await P.stats(water, { mask: water });
    if (dn && wpos.count) {
        const wd = P.dilate(water, 1);
        const own = R.field(1, dn + 1, 1, null, 'u32');
        lakesRun(R, 10, dl, { a: water, b: wd }, {}, {}, own);
        wd.destroy();
        pit = R.like(h);
        lakesRun(R, 11, dl, { a: depth, b: water }, { outF: pit }, {}, own);
        own.destroy();
        depth.destroy();
    } else {
        pit = R.like(h);
        const none = R.field(1, Math.max(dn + 1, 1), 1, null, 'u32');
        lakesRun(R, 11, dl, { a: depth, b: water }, { outF: pit }, {}, none);
        none.destroy();
        depth.destroy();
    }
    dl.destroy();
    const ps = await P.stats(pit, { mask: pit });
    if (ps.count) {
        fields.h = ew(R, EW.ADD, h, pit);
        fields.deposit = 'deposit' in fields ? ew(R, EW.ADD, fields.deposit, pit) : copyOf(pit);
    }
    pit.destroy();
    fields.water = water;
    pullBand(fields, ctx);
    return fields;
}

// `h < L` for a double L, exactly as numpy's float64 comparison of float32 values: a u32 field
function whereLess(P, f, L) {
    if (Math.fround(L) === L) return P.where(f, '<', L);
    return P.where(f, '<=', f32AtOrBelow(L));      // the float32 values below a double that is not one
}


// ======================================================================= aging: the fluvial backbone for an age ===

export const AGE_DEFAULTS = Object.freeze({ age_yr: 1.0e5, K: 2.0e-6, m: 0.5, n: 1.0, threshold_deg: 38.0,
    threshold_noise: 0.15, threshold_scale_m: 400.0, deposition: 1.0, roughness: 0.6, roughness_scales_m: [2000.0, 300.0, 50.0],
    valley_spacing_m: 300.0, gullies: false, steps: null, max_steps: 3000, min_steps: 200, dt_target_yr: null, lock: true,
    fill_pits: true, young_radius_m: 0.0, young_factor: 1.0, centre: [0.0, 0.0], strength_from_field: false,
    threshold_gain: 0.0, breakup: 0.0, k_breakup: 0.0, breakup_scales_m: [60.0, 20.0, 7.0], seed_texture_m: 0.0,
    seed_texture_scale_m: 150.0, sector_contrast: 0.0, sector_harmonics: [2, 6], keep_craters: [], k_profile: null,
    ravines: [], ravine_field: null, seed_streaks: null });

// kernels/volcanic/age.wgsl, one mode at a level's cells: [outF, outG (mode 3)]
function ageRun(R, level, centre, mode, ins = {}, u = {}, tabs = null, ktab = null) {
    const [x0, y0, cell, n] = levelWindow(level);
    const D = Gd.dummies(R), O = outDummies(R);
    const f = R.field(n, n, 1), g = mode === 3 ? R.field(n, n, 1) : O.f[0];
    R.run('volcanic/age', { azt: tabs ? tabs.field(R) : D.f1, a: ins.a ?? D.f1, b: ins.b ?? D.f1, c: ins.c ?? D.f1, ktab: ktab ?? D.f1 },
        { outF: f, outG: g }, { uMode: mode, uOrg: [x0 - Number(centre[0]), y0 - Number(centre[1])], uStep: cell,
            uK0: u.k0 ?? 0.0, uK1: u.k1 ?? 0.0, uRow: u.row ?? 0, uCount: u.count ?? 0 }, groupsOf(n, n));
    return mode === 3 ? [f, g] : f;
}

// the streak sets of a 'volcano_age' stage (volcanic.py _streak_sets)
function streakSets(p) {
    const sets = p.seed_streaks;
    if (!truthy(sets)) return [];
    return (Array.isArray(sets) ? sets : [sets]).map((s) => ({ ...s }));
}

// _streak_set: one seed_streaks entry at a level's cells (radial_streaks' signal, before amp_m)
const streakSet = (R, level, centre, st, seed, i) => radialStreaks(R, level, centre, st, Math.trunc(seed) + 709 + 31 * i);

// np.interp(r, k_profile) about the centre at a level's cells (core/compose.js's 'profile' shape: numpy's interp)
async function kProfile(R, level, centre, prof) {
    const C = await import('../core/compose.js');
    return C.shape(R, { kind: 'profile', centre, r_m: prof.map((q) => Number(q[0])), z_m: prof.map((q) => Number(q[1])) }, level);
}

/** furrow_k_factor: the erodibility gathered into a 'volcano_age' stage's furrows and ravines (k_floor..1), or null
 * when no streak set is sparse with a k_floor (volcanic.py). A new field. */
export function furrowKFactor(R, level, p, seed) {
    const gul = streakSets(p).map((st, i) => [i, st]).filter(([, st]) => st.sparse !== undefined && st.sparse !== null &&
        st.k_floor !== undefined && st.k_floor !== null);
    if (!gul.length) return null;
    const [, , cell, n] = levelWindow(level);
    const centre = p.centre;
    let m = Gd.fill(R, [n, n], 0.0);
    for (const [i, st] of gul) {
        const s = streakSet(R, level, centre, st, seed, i);
        const m2 = ageRun(R, level, centre, 4, { a: m, b: s });
        s.destroy();
        m.destroy();
        m = m2;
    }
    const rvs = ravinesOf(p, seed);
    if (rvs.length) {
        const cut = ravineCut(R, level, centre, rvs, seed);
        const m2 = ageRun(R, level, centre, 5, { a: m, b: cut }, { k0: Math.max(Math.max(...rvs.map((rv) => Number(rv.depth_m))), 1e-6) });
        cut.destroy();
        m.destroy();
        m = m2;
    }
    const mb = HS.gaussianBlur(m, Math.max(25.0 / cell, 0.5));
    m.destroy();
    const rHi = Math.max(...gul.map(([, st]) => Number((st.r_m ?? [1000.0, 10000.0])[1])));
    const kFloor = Math.min(...gul.map(([, st]) => Number(st.k_floor)));
    const out = ageRun(R, level, centre, 6, { a: mb }, { k0: rHi, k1: kFloor });
    mb.destroy();
    return out;
}

/** basins_kept: the filled surface with every closed depression deeper than minDepthM left as it is (a sink the
 * drainage gathers in). A new field. */
export async function basinsKept(R, h, filled, minDepthM) {
    const P = prims(R);
    const depth = ew(R, EW.SUB, filled, h);
    const dm = P.where(depth, '>', 1e-4);
    const { labels: lab, count } = await P.label(dm);
    dm.destroy();
    if (!count) {
        depth.destroy();
        lab.destroy();
        return copyOf(filled);
    }
    const init = new Uint32Array(5 * (count + 1));
    for (let L = 0; L <= count; L++) init[5 * L + 4] = 0xFFFFFFFF;
    const stats = R.field(1, 5 * (count + 1), 1, init, 'u32');
    lakesRun(R, 0, lab, { a: depth }, {}, { uR: -1.0, uBand: -1 }, stats);
    const out = R.like(h);
    lakesRun(R, 12, lab, { a: h, b: filled }, { outF: out }, { uR: Number(minDepthM) }, stats);
    for (const f of [depth, lab, stats]) f.destroy();
    return out;
}

/** Stage op 'volcano_age': the fluvial backbone (solvers/fluvial.js) run on a constructional shape for its age with no
 * uplift (volcanic.py op_volcano_age; its docstring holds): time-faithful on the first level it runs on (from the
 * drainage routed to convergence on the start surface, no lock), refined under the lock below; seed texture, sparse
 * furrows and ravines first; K x the young summit, the k_profile, the sector contrast and the furrows' gathering;
 * Sc from the field for walls built with their strength; kept craters lowered but never raised. Skips the coarsest
 * level's pre-passes. */
export async function opVolcanoAge(fields, level, params, seed = 0, ctx = null) {
    if (isPrepass(ctx)) return fields;
    const R = runnerOf(fields, ctx), P = prims(R);
    const HY = await import('./hydro.js');
    const p = { ...AGE_DEFAULTS, ...(params ?? {}) };
    ctx = await FL.asContext(ctx, fields, level);
    if (ctx.pins?._setting) {
        releaseSettingPins(ctx);
        ctx.pins = null;          // volcano_setting's plain pins were for its ranges' growth, not for the aging
    }
    const key = 'aged_' + stampKey('volcano_age', { ...params, seed }).slice('stamp_'.length);
    const first = !(key in fields);
    const [, , cell, n] = levelWindow(level);
    const main = ctx.main;
    const mainCell = main ? Number(main.cell) : cell;
    const grow = ctx.role === 'grow';
    const age = Number(p.age_yr);
    let steps;
    if (truthy(p.steps)) {
        steps = Math.trunc(Number(p.steps));
    } else {
        const dtT = p.dt_target_yr;
        steps = truthy(dtT) ? Math.trunc(pyRound(age / Number(dtT))) : Math.trunc(Number(p.max_steps));
        steps = Math.min(Math.max(steps, Math.trunc(Number(p.min_steps))), Math.trunc(Number(p.max_steps)));
    }
    let dt = age / Math.max(steps, 1);
    if (!first) {
        // refine at the first level's step (a finer level adds detail as deep in cells, not more years per cell)
        dt = (await R.readRange(fields[key], 0, 1))[0];
        steps = Math.max(Math.trunc(pyRound(age / dt)), 1);
    }
    const dtRef = dt * FL.CELL_REF_M / (grow ? cell : Math.max(cell, mainCell));
    const centre = [Number(p.centre[0]), Number(p.centre[1])];
    if (first && (Number(p.seed_texture_m) > 0 || truthy(p.seed_streaks))) {
        let tx = Gd.fill(R, [n, n], 0.0);
        if (Number(p.seed_texture_m) > 0) {
            const u = unitFbm(R, level, Number(p.seed_texture_scale_m), Math.trunc(seed) + 707, 3);
            tx.destroy();
            tx = ew(R, EW.LERP, null, u, null, null, 0.0, Number(p.seed_texture_m));
            u.destroy();
        }
        if (truthy(p.seed_streaks)) {
            // radial furrows of many sizes: the flow gathers in them and cuts gullies down the cone
            for (const [i, st] of streakSets(p).entries()) {
                const s = streakSet(R, level, centre, st, seed, i);
                const t2 = ew(R, EW.ADD_SCALED, tx, s, null, null, Number(st.amp_m));
                s.destroy();
                tx.destroy();
                tx = t2;
            }
        }
        if (truthy(p.k_profile)) {                // the seed texture only where the run is meant to cut
            const kp = await kProfile(R, level, centre, p.k_profile);
            const t2 = ageRun(R, level, centre, 7, { a: tx, b: kp });
            kp.destroy();
            tx.destroy();
            tx = t2;
        }
        fields.h = ew(R, EW.ADD, fields.h, tx);
        if ('bed' in fields) fields.bed = ew(R, EW.ADD, fields.bed, tx);
        tx.destroy();
    }
    if (first && (truthy(p.ravines) || truthy(p.ravine_field))) {
        // a few deep ravines seeded before the run: the stream power gathers the drainage into them
        const cut = ravineCut(R, level, centre, ravinesOf(p, seed), seed);
        fields.h = ew(R, EW.SUB, fields.h, cut);
        if ('bed' in fields) {
            const b = ew(R, EW.SUB, fields.bed, cut);
            fields.bed = ew(R, EW.MIN, b, fields.h);
            b.destroy();
        }
        cut.destroy();
    }
    const closed = !truthy(p.fill_pits);
    let pinsSaved = null;
    if (closed && !first && ctx.pins) {
        // a closed basin's refine level: the window drains on its own (no inflow across the floor)
        pinsSaved = ctx.pins;
        ctx.pins = { ...ctx.pins, A_in: Gd.fill(R, [n, n], 0.0), qs_in: Gd.fill(R, [n, n], 0.0) };
    }
    if (first || closed) {
        const h0 = fields.h;
        let surf;
        if (first) {
            let { filled } = await HY.fillDepressions(h0, { seaLevel: ctx.sea_level ?? null });
            if (closed) {
                const s = await P.stats(h0);
                const kept = await basinsKept(R, h0, filled, HY.depressionThreshold(s.max - s.min));
                filled.destroy();
                filled = kept;
            }
            surf = await HY.routingSurface(filled, { seaLevel: ctx.sea_level ?? null });
            filled.destroy();
        } else {
            surf = copyOf(h0);                    // routed on its own surface (its pits hold their drainage)
        }
        const A_in = ctx.pins && first ? ctx.pins.A_in : null;
        const routed = await HY.routeToConvergence(R, surf, cell, { A0: first && 'A' in fields ? fields.A : null, A_in });
        surf.destroy();
        fields.A = routed.A;
    }
    const saved = {};
    for (const k of ['U', 'K_factor', 'Sc_factor']) if (k in fields) saved[k] = copyOf(fields[k]);
    fields.U = Gd.fill(R, [n, n], 0.0);
    let kf = Gd.fill(R, [n, n], 1.0);
    if (Number(p.young_radius_m) > 0 && Number(p.young_factor) !== 1.0) {
        kf.destroy();
        kf = ageRun(R, level, centre, 0, {}, { k0: Number(p.young_factor), k1: Number(p.young_radius_m) });
    }
    if (truthy(p.k_profile)) {
        const kp = await kProfile(R, level, centre, p.k_profile);
        const k2 = ew(R, EW.MUL, kf, kp);
        kp.destroy();
        kf.destroy();
        kf = k2;
    }
    const sc = Number(p.sector_contrast);
    if (sc > 0.0) {
        const tabs = new AzTables();
        const row = tabs.add(azimuthNoiseTable(Math.trunc(seed), 91, Math.trunc(p.sector_harmonics[0]), Math.trunc(p.sector_harmonics[1]), 0.8));
        const k2 = ageRun(R, level, centre, 1, { a: kf }, { k0: sc, row }, tabs);
        tabs.destroy();
        kf.destroy();
        kf = k2;
    }
    const fk = furrowKFactor(R, level, p, seed);
    if (fk) {
        const k2 = ew(R, EW.MUL, kf, fk);
        fk.destroy();
        kf.destroy();
        kf = k2;
    }
    fields.K_factor = kf;
    const keep = p.keep_craters ?? [];
    const hKeep = keep.length ? copyOf(fields.h) : null;
    const t0 = Math.tan(radians(Number(p.threshold_deg)));
    if (truthy(p.strength_from_field) && 'Sc' in fields) fields.Sc_factor = ew(R, EW.LERP, null, fields.Sc, null, null, 0.0, 1.0 / t0);
    else if ('Sc_factor' in fields) delete fields.Sc_factor;
    const fp = {};
    for (const k of ['K', 'm', 'n', 'threshold_deg', 'threshold_noise', 'threshold_scale_m', 'deposition', 'roughness',
        'roughness_scales_m', 'valley_spacing_m', 'gullies', 'threshold_gain', 'breakup', 'k_breakup', 'breakup_scales_m']) fp[k] = p[k];
    Object.assign(fp, { steps, min_steps: 1, max_steps: Math.max(steps, 1), dt_ref_yr: dtRef, relief_m: null,
        lock: truthy(p.lock) && !first, fill_pits: truthy(p.fill_pits), mode: 'evolve', Sc_from_fields: false });
    await FL.opFluvial(fields, level, fp, seed, ctx);
    if (keep.length) {
        const kt = new Float32Array(4 * keep.length);
        const [x0, y0] = levelWindow(level);
        keep.forEach((c, k) => kt.set([x0 - Number(c.at[0]), y0 - Number(c.at[1]), Number(c.radius_m), 0.0], 4 * k));
        const ktab = R.field(1, keep.length, 4, kt);
        const w = ageRun(R, level, [0, 0], 2, {}, { count: keep.length }, null, ktab);
        ktab.destroy();
        const [lowered, cut] = ageRun(R, level, centre, 3, { a: fields.h, b: hKeep, c: w });
        w.destroy();
        hKeep.destroy();
        fields.h = lowered;
        if ('deposit' in fields) fields.deposit = ew(R, EW.MAX_DIFF, fields.deposit, cut, null, null, 0.0);
        cut.destroy();
        if ('bed' in fields) fields.bed = ew(R, EW.MIN, fields.bed, fields.h);
    }
    for (const k of ['U', 'K_factor', 'Sc_factor']) {
        if (k in saved) fields[k] = saved[k];
        else if (k in fields) delete fields[k];
    }
    if (pinsSaved) {
        for (const k of ['A_in', 'qs_in']) if (ctx.pins[k] && !ctx.pins[k].destroyed) ctx.pins[k].destroy();
        ctx.pins = pinsSaved;                     // the runner's pins for the level's later stages
    }
    fields[key] = Gd.fill(R, [n, n], Math.fround(dt));      // the step the first level used (and a marker)
    return fields;
}


// ===================================================================== numpy's standard normals on the GPU ===
// lava_surface draws numpy's standard normals per cell of a flow's window (rng.standard_normal(np.shape(P))); the edition
// puts per-cell work on the GPU and field-class parity needs numpy's very draws, so they come from
// kernels/volcanic/normal.wgsl: PCG64's words per segment of 256 (the segments' start states advanced here in BigInt),
// every word classified as the start of a ziggurat attempt, the attempts chained segment by segment (a walk per
// segment and entry offset on the GPU, the chain of segments here), the values written where numpy puts them. The
// attempts the float32 classification cannot decide (the tail, and wedge tests within 1e-5 of a tie) are settled in
// doubles by core/np_random.js's own generator placed at that word. The ziggurat's tables are core/np_random.js's,
// read from its source (module constants it does not export).

const U128 = (1n << 128n) - 1n;
const PCG_MULT = 0x2360ED051FC65DA44385DF649FCCF645n;
const LIMBS = ['s0', 's1', 's2', 's3', 's4', 's5', 's6', 's7'], INCS = ['c0', 'c1', 'c2', 'c3', 'c4', 'c5', 'c6', 'c7'];
const bigOf = (g, names) => names.reduceRight((v, k) => (v << 16n) | BigInt(g[k]), 0n);
function setBig(g, names, v) {
    names.forEach((k, i) => { g[k] = Number((v >> BigInt(16 * i)) & 0xFFFFn); });
}

/** The LCG's jump of `delta` steps: [A, C] with state' = A state + C (mod 2^128) (pcg_advance_lcg_128). */
export function pcgJump(inc, delta) {
    let accMult = 1n, accPlus = 0n, curMult = PCG_MULT, curPlus = inc, d = BigInt(delta);
    while (d > 0n) {
        if (d & 1n) {
            accMult = (accMult * curMult) & U128;
            accPlus = (accPlus * curMult + curPlus) & U128;
        }
        curPlus = ((curMult + 1n) * curPlus) & U128;
        curMult = (curMult * curMult) & U128;
        d >>= 1n;
    }
    return [accMult, accPlus];
}

const advanceState = (state, inc, delta) => {
    const [A, C] = pcgJump(inc, delta);
    return (A * state + C) & U128;
};

let ZIGGURAT = null;

// core/np_random.js's KI_DOUBLE, WI_DOUBLE and FI_DOUBLE, read from its source
function zigguratTables() {
    if (ZIGGURAT) return ZIGGURAT;
    const src = Deno.readTextFileSync(new URL('../core/np_random.js', import.meta.url));
    const grab = (name) => {
        const m = new RegExp(`const ${name} = new Float64Array\\(\\[([\\s\\S]*?)\\]\\);`).exec(src);
        if (!m) throw new Error(`volcanic: core/np_random.js holds no ${name} (the ziggurat's tables)`);
        return m[1].split(',').map((s) => s.trim()).filter(Boolean).map(Number);
    };
    const ki = grab('KI_DOUBLE'), wi = grab('WI_DOUBLE'), fi = grab('FI_DOUBLE');
    if (ki.length !== 256 || wi.length !== 256 || fi.length !== 256) throw new Error('volcanic: the ziggurat tables are not 256 long');
    ZIGGURAT = { ki, wi, fi };
    return ZIGGURAT;
}

const ZIG_FIELDS = new WeakMap();

function zigguratFields(R) {
    let z = ZIG_FIELDS.get(R);
    if (!z) {
        const { ki, wi, fi } = zigguratTables();
        const kt = new Uint32Array(512), wf = new Float32Array(512);
        for (let i = 0; i < 256; i++) {
            kt[2 * i] = Math.floor(ki[i] / 8388608);          // rabs's high 29 bits and low 23 bits
            kt[2 * i + 1] = ki[i] % 8388608;
            wf[2 * i] = wi[i];
            wf[2 * i + 1] = fi[i];
        }
        z = { kt: R.field(1, 512, 1, kt, 'u32'), wf: R.field(1, 256, 2, wf) };
        ZIG_FIELDS.set(R, z);
    }
    return z;
}

let SETTLER = null;

// one ziggurat attempt that starts at word k of the stream (S0, inc), in doubles: core/np_random.js's own _normal()
// from that word. The tail always returns; a wedge returned at k when its attempt read exactly its two words.
function settleAttempt(S0, inc, k, idx) {
    if (!SETTLER) SETTLER = defaultRng(0);
    const g = SETTLER;
    setBig(g, LIMBS, advanceState(S0, inc, k));
    setBig(g, INCS, inc);
    g.hasU32 = false;
    let steps = 0;
    const step0 = Object.getPrototypeOf(g)._step;
    g._step = function () { steps++; step0.call(this); };
    try {
        const v = g._normal();
        if (idx === 0) return { cons: steps, out: 1, value: v };
        return steps === 2 ? { cons: 2, out: 1, value: v } : { cons: 2, out: 0, value: 0.0 };
    } finally {
        delete g._step;
    }
}

const NSEG = 256, NENTRY = 32;

/** numpy's gen.standard_normal((rows, cols)) on the GPU: a new (rows, cols) field, draw for draw (float32 values of
 * numpy's), and `gen` (a core/np_random.js NpGenerator) advanced past them, as numpy leaves it. count draws of
 * (rows, cols) each come out as `count` fields, consecutive in the stream (one call: one chain). */
export async function standardNormalGpu(R, gen, rows, cols, count = 1) {
    const P = prims(R), Z = zigguratFields(R);
    const N = rows * cols * count;
    const S0 = bigOf(gen, LIMBS), inc = bigOf(gen, INCS);
    let M = Math.ceil((Math.ceil(N * 1.02) + 2 * NSEG) / NSEG) * NSEG;
    const groups = (k) => [Math.ceil(Math.min(Math.max(k, 1), 4096) / 16), Math.ceil(Math.ceil(Math.max(k, 1) / 4096) / 16), 1];
    const D = Gd.dummies(R), O = outDummies(R);
    for (;;) {
        const nseg = M / NSEG;
        // the segments' start states (one more segment: the words an attempt near the end reads)
        const [A, C] = pcgJump(inc, NSEG);
        const st = new Uint32Array(4 * (nseg + 1));
        let s = S0;
        for (let k = 0; k <= nseg; k++) {
            for (let w = 0; w < 4; w++) st[4 * k + w] = Number((s >> BigInt(32 * w)) & 0xFFFFFFFFn);
            s = (A * s + C) & U128;
        }
        const incw = new Uint32Array(4);
        for (let w = 0; w < 4; w++) incw[w] = Number((inc >> BigInt(32 * w)) & 0xFFFFFFFFn);
        const starts = P.list(4 * (nseg + 1), 'u32', st), incF = R.field(1, 4, 1, incw, 'u32');
        const words = P.list(2 * (M + NSEG), 'u32');
        const run = (mode, sm, im, count, u = {}) => R.run('volcanic/normal', { a: sm.a ?? D.u1, b: sm.b ?? D.u1, c: sm.c ?? D.u1,
            wf: sm.wf ?? D.f1, c2: sm.c2 ?? D.u1 }, { o1: im.o1 ?? O.u, o2: im.o2 ?? P.dummyU, o3: im.o3 ?? O.f[0] },
        { uMode: mode, uSeg: NSEG, uCount: count, uE: u.e ?? NENTRY }, groups(count));
        run(0, { a: starts, b: incF }, { o1: words }, nseg + 1);
        starts.destroy();
        incF.destroy();
        const cons = P.list(M, 'u32'), flags = P.list(M, 'u32'), vals = P.list(M, 'f32');
        run(1, { a: words, b: Z.kt, wf: Z.wf }, { o1: cons, o2: flags, o3: vals }, M);
        // the attempts float32 could not decide, settled in doubles
        const dm = P.list(M, 'u32');
        run(5, { a: flags }, { o1: dm }, M);
        const { index, n: nd } = await P.nonzero(dm, { count: M });
        dm.destroy();
        if (nd) {
            const idx = await R.readRange(index, 0, nd);
            const w0 = await R.readParts(Array.from(idx, (k) => ({ field: words, first: 2 * k, count: 1 })));
            const patch = new Uint32Array(4 * nd), pf = new Float32Array(patch.buffer);
            idx.forEach((k, i) => {
                const r = settleAttempt(S0, inc, k, w0[i][0] & 0xFF);
                patch[4 * i] = k;
                patch[4 * i + 1] = r.cons;
                patch[4 * i + 2] = r.out;
                pf[4 * i + 3] = r.value;
            });
            const pl = P.list(4 * nd, 'u32', patch);
            run(4, { a: pl }, { o1: cons, o2: flags, o3: vals }, nd);
            pl.destroy();
        }
        index.destroy();
        // the walk of every segment from every entry offset, then the chain of segments
        const exits = P.list(nseg * NENTRY, 'u32'), counts = P.list(nseg * NENTRY, 'u32');
        run(2, { b: cons, c: flags }, { o1: exits, o2: counts }, nseg * NENTRY);
        const [ex, ct] = await R.readAll([exits, counts]);
        exits.destroy();
        counts.destroy();
        const segs = [];
        let ent = 0, total = 0;
        for (let k = 0; k < nseg && total < N; k++) {
            segs.push(ent, total);
            total += ct[k * NENTRY + ent];
            ent = ex[k * NENTRY + ent];
            if (ent >= NENTRY) throw new Error(`volcanic standardNormalGpu: an attempt reads past ${NENTRY} words (a tail of ${ent} words)`);
        }
        if (total < N) {                            // not enough words for the draws: more words (rare)
            for (const f of [words, cons, flags, vals]) f.destroy();
            M = Math.ceil((M * 1.5) / NSEG) * NSEG;
            continue;
        }
        const sf = P.list(segs.length, 'u32', Uint32Array.from(segs));
        const out = R.field(rows * count, cols, 1);
        const end = R.field(1, 1, 1, null, 'u32');
        run(3, { b: cons, c: flags, wf: vals, c2: sf }, { o1: end, o3: out }, segs.length / 2, { e: N });
        const [T] = await R.read(end);
        for (const f of [words, cons, flags, vals, sf, end]) f.destroy();
        setBig(gen, LIMBS, advanceState(S0, inc, T));
        if (count === 1) return out;
        const parts = [];
        for (let i = 0; i < count; i++) {
            const f = R.field(rows, cols, 1);
            R.run('hydro/crop', { src: out }, { outF: f }, { uOrigin: [0, i * rows] });
            parts.push(f);
        }
        out.destroy();
        return parts;
    }
}


// ============================================================================== lava flows (DOWNFLOW, design 4.7) ===

export const LAVA_DEFAULTS = Object.freeze({ walkers: 400, length_m: 6000.0, thickness_m: 12.0, dh_m: null, dh_factor: 0.25,
    dh_rel: 1.5, age: 0.0, levee: 0.3, rough: 0.12, p_edge: 0.01, width_m: null, front_deg: null, levee_frac: 0.1,
    stop_spread: 0.0, front_spread: 0.0, vent_taper: 0.6, no_climb: false, units: 1, bury: false, spread_slope_deg: null,
    channel: null });

/** The vents of a 'lava_flows' stage (volcanic.py lava_vents): params vents, rift, breaches, feet, scatter. */
export function lavaVents(params, seed) {
    const out = (params.vents ?? []).map((v) => ({ ...v }));
    const rng = rngOf(seed, 81);
    const rangeOf = (o, k, d) => (o[k] ?? d).map(Number);
    if (truthy(params.rift)) {
        const rp = { ...params.rift };
        const c0 = rp.centre ?? [0.0, 0.0];
        const [ex, ey] = compass(num(rp.azimuth_deg, 0.0));
        for (let i = 0; i < Math.trunc(num(rp.count, 3)); i++) {
            const side = rng.random() < 0.5 ? 1.0 : -1.0;
            const dr = rangeOf(rp, 'distance_m', [3000.0, 8000.0]);
            const d = rng.uniform(dr[0], dr[1]);
            const lat = rng.normal(0.0, num(rp.spread_m, 1500.0));
            const lr = rangeOf(rp, 'length_m', [5000.0, 10000.0]), tr = rangeOf(rp, 'thickness_m', [10.0, 25.0]);
            const ar = rangeOf(rp, 'age', [0.0, 0.6]);
            const v = { at: [Number(c0[0]) + side * d * ex - lat * ey, Number(c0[1]) + side * d * ey + lat * ex] };
            v.length_m = rng.uniform(lr[0], lr[1]);
            v.thickness_m = rng.uniform(tr[0], tr[1]);
            v.age = rng.uniform(ar[0], ar[1]);
            v.width_m = truthy(rp.width_m) ? rng.uniform(Number(rp.width_m[0]), Number(rp.width_m[1])) : null;
            out.push(v);
        }
    }
    if (truthy(params.breaches)) {
        const bp = { ...params.breaches };
        for (const c of conesOf(bp, seed)) {
            if (c.breach_azimuth_deg === undefined || c.breach_azimuth_deg === null) continue;
            const [ex, ey] = compass(Number(c.breach_azimuth_deg));
            const rb = 0.5 * Number(c.width_m);
            const youth = 1.0 - Math.min(num(c.age_yr, 0.0) / num(bp.age_span_yr, 5e5), 1.0);
            const v = { at: [Number(c.at[0]) + 0.92 * rb * ex, Number(c.at[1]) + 0.92 * rb * ey] };
            v.length_m = num(bp.length_m, 4000.0) * (0.5 + 0.5 * youth) * rng.uniform(0.7, 1.3);
            v.thickness_m = num(bp.thickness_m, 12.0) * rng.uniform(0.7, 1.2);
            v.age = 1.0 - youth;
            v.width_m = truthy(bp.width_m) ? Number(bp.width_m) * rng.uniform(0.6, 1.4) : null;
            out.push(v);
        }
    }
    if (truthy(params.feet)) {
        const fp = { ...params.feet };
        const frng = rngOf(seed, 83);
        for (const c of conesOf(fp, seed)) {
            if (frng.random() >= num(fp.fraction, 1.0)) continue;
            const az = num(fp.downhill_azimuth_deg, 0.0) + frng.uniform(-1.0, 1.0) * num(fp.spread_deg, 60.0);
            const [ex, ey] = compass(az);
            const rb = 0.5 * Number(c.width_m) * Math.max(1.0, num(c.elongation, 1.0));
            const lr = rangeOf(fp, 'length_m', [2000.0, 6000.0]), tr = rangeOf(fp, 'thickness_m', [6.0, 15.0]);
            const ar = rangeOf(fp, 'age', [0.5, 1.0]);
            const v = { at: [Number(c.at[0]) + rb * ex, Number(c.at[1]) + rb * ey] };
            v.length_m = frng.uniform(lr[0], lr[1]);
            v.thickness_m = frng.uniform(tr[0], tr[1]);
            v.age = frng.uniform(ar[0], ar[1]);
            v.width_m = truthy(fp.width_m) ? frng.uniform(Number(fp.width_m[0]), Number(fp.width_m[1])) : null;
            out.push(v);
        }
    }
    if (truthy(params.scatter)) {
        const sp = { ...params.scatter };
        const [x0, y0, size] = sp.window.map(Number);
        for (let i = 0; i < Math.trunc(num(sp.count, 6)); i++) {
            const ax = x0 + size * rng.uniform(0.1, 0.9);
            const ay = y0 + size * rng.uniform(0.1, 0.9);
            const lr = rangeOf(sp, 'length_m', [2000.0, 6000.0]), tr = rangeOf(sp, 'thickness_m', [5.0, 15.0]);
            const ar = rangeOf(sp, 'age', [0.4, 1.0]);
            const v = { at: [ax, ay] };
            v.length_m = rng.uniform(lr[0], lr[1]);
            v.thickness_m = rng.uniform(tr[0], tr[1]);
            v.age = rng.uniform(ar[0], ar[1]);
            v.width_m = truthy(sp.width_m) ? rng.uniform(Number(sp.width_m[0]), Number(sp.width_m[1])) : null;
            out.push(v);
        }
    }
    return out;
}

const NB_DI = [-1, 0, 1, -1, 1, -1, 0, 1], NB_DJ = [-1, -1, -1, 0, 0, 1, 1, 1];
const NB_LEN = NB_DI.map((a, k) => Math.hypot(a, NB_DJ[k]));

/** DOWNFLOW (Favalli et al. 2005), volcanic.py lava_walkers: walkers stepping from the start cell to the neighbour
 * of steepest perturbed descent on h (a Float32Array or Float64Array of ny x nx, row 0 south: the level's surface
 * read back once), numpy's draws in numpy's order. JavaScript over the walkers (PORT_PLAN.md 2.4: their draws depend
 * on how many are alive each step); the local slope (dh_rel) is taken in doubles at the cells they visit, from the
 * same heights numpy's np.gradient reads there. Returns { visits (Float32Array of counts, ny x nx), N, cells (the
 * visited cells' row-major indices, ascending) }: the passage fraction is min(visits / N, 1). */
export function lavaWalkers(h, ny, nx, cell, start, walkers = 400, lengthM = 6000.0, dhM = 3.0, seed = 0, salt = 0,
    dhRel = null, pondM = null, stopSpread = 0.0, frontSpread = 0.0) {
    const N = Math.trunc(walkers);
    const sd = Math.abs(Math.trunc(seed)) % 4294967296;
    const rng = defaultRng([sd, 7177, Math.trunc(salt)]);
    const i = new Int32Array(N).fill(Math.min(Math.max(pyRound(start[0]), 1), nx - 2));
    const j = new Int32Array(N).fill(Math.min(Math.max(pyRound(start[1]), 1), ny - 2));
    const dist = new Float64Array(N);
    const alive = new Uint8Array(N).fill(1);
    const visits = new Float32Array(ny * nx);
    const seen = new Set();
    const visit = (k, c) => { visits[k] += c; seen.add(k); };
    const lim = new Float64Array(N).fill(Number(lengthM));
    if (stopSpread) {
        const r = defaultRng([sd, 7179, Math.trunc(salt)]).random(N);
        for (let w = 0; w < N; w++) lim[w] = Number(lengthM) * (1.0 - Number(stopSpread) * r[w]);
    }
    const fs = Number(frontSpread);
    const at = (jj, ii) => (ii < 0 || jj < 0 || ii >= nx || jj >= ny ? Infinity : h[jj * nx + ii]);
    // np.gradient's slope at a cell (central inside, one-sided on the edges), times cell x dh_rel
    const S = dhRel ? (jj, ii) => {
        const gx = ii === 0 ? (h[jj * nx + 1] - h[jj * nx]) / cell : ii === nx - 1 ? (h[jj * nx + ii] - h[jj * nx + ii - 1]) / cell
            : (h[jj * nx + ii + 1] - h[jj * nx + ii - 1]) / (2.0 * cell);
        const gy = jj === 0 ? (h[nx + ii] - h[ii]) / cell : jj === ny - 1 ? (h[jj * nx + ii] - h[(jj - 1) * nx + ii]) / cell
            : (h[(jj + 1) * nx + ii] - h[(jj - 1) * nx + ii]) / (2.0 * cell);
        return Math.max(Math.hypot(gx, gy), 1e-5) * cell * Number(dhRel);
    } : null;
    const budget = new Float64Array(N).fill(pondM ? Number(pondM) : 0.0);
    const back = new Int32Array(N).fill(-1);
    visit(j[0] * nx + i[0], N);
    const drop = new Float64Array(8);
    for (;;) {
        const a = [];
        for (let w = 0; w < N; w++) if (alive[w]) a.push(w);
        if (!a.length) break;
        const da = new Float64Array(a.length);
        a.forEach((w, q) => {
            let d = S ? Math.min(S(j[w], i[w]), Number(dhM)) : Number(dhM);
            if (fs) d = d * (1.0 + fs * (dist[w] / lim[w]) ** 2);
            da[q] = d;
        });
        const uh = rng.uniform(-1.0, 1.0, a.length);
        const un = rng.uniform(-1.0, 1.0, a.length * 8);
        const ks = new Int32Array(a.length), ok = new Uint8Array(a.length);
        a.forEach((w, q) => {
            const here = h[j[w] * nx + i[w]] + uh[q] * da[q];
            let best = -Infinity, bk = 0;
            for (let k = 0; k < 8; k++) {
                const nb = at(j[w] + NB_DJ[k], i[w] + NB_DI[k]) + un[8 * q + k] * da[q];
                drop[k] = (here - nb) / (NB_LEN[k] * cell);
                if (drop[k] > best) { best = drop[k]; bk = k; }
            }
            ks[q] = bk;
            ok[q] = drop[bk] > 0.0 ? 1 : 0;
        });
        if (pondM) {
            // pond: the lowest neighbour that is not the way back, paid for from the budget
            a.forEach((w, q) => {
                if (ok[q]) return;
                let lo = Infinity, kk = 0;
                for (let k = 0; k < 8; k++) {
                    const raw = k === back[w] ? Infinity : at(j[w] + NB_DJ[k], i[w] + NB_DI[k]);
                    if (raw < lo) { lo = raw; kk = k; }
                }
                const rise = lo - h[j[w] * nx + i[w]];
                if (Number.isFinite(rise) && rise <= budget[w]) {
                    budget[w] -= Math.max(rise, 0.0);
                    ks[q] = kk;
                    ok[q] = 1;
                }
            });
        }
        a.forEach((w, q) => {
            if (!ok[q]) { alive[w] = 0; return; }
            const k = ks[q];
            back[w] = 7 - k;
            i[w] += NB_DI[k];
            j[w] += NB_DJ[k];
            dist[w] += NB_LEN[k] * cell;
        });
        // np.add.at counts every moved walker (one that left the grid or its length too), then the stopped ones die
        a.forEach((w, q) => {
            if (!ok[q]) return;
            visit(j[w] * nx + i[w], 1);
        });
        a.forEach((w, q) => {
            if (!ok[q]) return;
            if (i[w] <= 0 || j[w] <= 0 || i[w] >= nx - 1 || j[w] >= ny - 1 || dist[w] >= lim[w]) alive[w] = 0;
        });
    }
    return { visits, N, cells: Int32Array.from(seen).sort() };
}

// kernels/volcanic/lava.wgsl, one mode over the size of `a` (outF new or given; outG for the modes that write it)
function lavaRun(R, mode, ins, u = {}, outs = {}) {
    const D = Gd.dummies(R), O = outDummies(R);
    const two = [11, 12, 13, 20].includes(mode);
    const ref = ins.a;
    const outF = outs.outF ?? R.field(ref.h, ref.w, 1);
    const outG = two ? (outs.outG ?? R.field(ref.h, ref.w, 1)) : O.f[1];
    R.run('volcanic/lava', { a: ins.a, b: ins.b ?? D.f1, c: ins.c ?? D.f1, d: ins.d ?? D.f1, e: ins.e ?? D.f1 }, { outF, outG },
        { uMode: mode, uOrg: u.org ?? [0, 0], uStep: u.step ?? 1.0, uK0: u.k0 ?? 0.0, uK1: u.k1 ?? 0.0, uLen: u.len ?? 1.0,
            uFlag: u.flag ?? 0, uAt: u.at ?? [0, 0] }, groupsOf(ref.w, ref.h));
    return two ? [outF, outG] : outF;
}

/** np.std of a field (population: sqrt of the mean square deviation), from a fixed-tree float32 sum (numpy's pairwise
 * float64: relative 1e-7). */
async function stdOf(R, f) {
    const P = prims(R);
    const s = await P.stats(f);
    const mean = s.sum / s.count;
    const dev = lavaRun(R, 10, { a: f }, { k0: mean });
    const q = await P.stats(dev);
    dev.destroy();
    return Math.sqrt(q.sum / q.count);
}

const blur = (f, s) => HS.gaussianBlur(f, s);       // solvers/hillslope.py gaussian_blur: numpy's FFT blur, reflect

/** lava_surface: a flow's added height and footprint from the walkers' passage fraction P (a GPU field of the flow's
 * window), as volcanic.py makes them (its docstring holds; front_deg: the aa flow of _lava_surface_aa). The noise is
 * numpy's standard normals (standardNormalGpu, the same draws). Returns [T (metres), F (the footprint 0..1)]. */
export async function lavaSurface(R, P, cell, thicknessM, opts = {}) {
    const o = { p_edge: 0.04, margin_m: null, levee: 0.3, rough: 0.12, age: 0.0, seed: 0, width_m: null, front_deg: null,
        levee_frac: 0.1, width_scale: null, ...opts };
    const th = Number(thicknessM), sd = Math.abs(Math.trunc(o.seed)) % 4294967296;
    const [rows, cols] = [P.h, P.w];
    const own = [];
    const keep = (f) => { own.push(f); return f; };
    const sqrtTau = Math.sqrt(TAU);
    const pb = keep(blur(P, 0.8));
    const path = keep(lavaRun(R, 1, { a: pb }, { k0: Number(o.p_edge) }));
    const W = truthy(o.width_m) && Number(o.width_m) > 2.0 * cell ? Number(o.width_m) : null;
    let T, plate;
    if (o.front_deg !== null && o.front_deg !== undefined) {
        // _lava_surface_aa: one generator for the lobes and the rough top
        const rng = defaultRng([sd, 9097]);
        const draws = (W ? 2 : 0) + (truthy(o.rough) ? 2 : 0);
        const noise = draws ? await standardNormalGpu(R, rng, rows, cols, draws) : [];
        const nz = Array.isArray(noise) ? noise : [noise];
        nz.forEach(keep);
        let core = path;
        if (W) {
            const sig = 0.25 * W / cell;
            const bs = keep(blur(path, sig));
            let b = keep(ew(R, EW.LERP, null, bs, null, null, 0.0, sqrtTau * sig));
            if (o.width_scale) {
                // the band's width cell by cell: the band at half, the full and twice the width, read in log2 of the scale
                const blo = keep(ew(R, EW.LERP, null, keep(blur(path, 0.5 * sig)), null, null, 0.0, sqrtTau * 0.5 * sig));
                const bhi = keep(ew(R, EW.LERP, null, keep(blur(path, 2.0 * sig)), null, null, 0.0, sqrtTau * 2.0 * sig));
                b = keep(lavaRun(R, 2, { a: b, b: blo, c: bhi, d: o.width_scale }));
            }
            let lobes = keep(Gd.fill(R, [rows, cols], 0.0));
            for (const [q, [frac, a]] of [[0, [0.12, 0.5]], [1, [0.04, 0.3]]]) {
                const g = keep(blur(nz[q], Math.max(frac * W / cell, 0.7)));
                const s = Math.max(await stdOf(R, g), 1e-9);
                lobes = keep(lavaRun(R, 9, { a: lobes, b: g }, { k0: a, k1: s }));
            }
            core = keep(lavaRun(R, 3, { a: b, b: lobes }, { k0: 0.92, k1: 1.08 }));
        }
        let margin = o.margin_m === null || o.margin_m === undefined ? th / Math.tan(radians(Number(o.front_deg))) : Number(o.margin_m);
        margin *= 1.0 + 2.0 * Number(o.age);
        plate = lavaRun(R, 4, { a: keep(blur(core, Math.max(margin / (1.05 * cell), 0.7))) }, { k0: 0.3 });
        T = ew(R, EW.LERP, null, plate, null, null, 0.0, th);
        if (truthy(o.levee)) {
            const lw = Number(o.levee_frac) * (W ? W : 8.0 * th);           // each levee's width
            const f2 = keep(blur(core, Math.max(0.6 * lw / cell, 0.7)));
            const T2 = lavaRun(R, 5, { a: plate, b: f2 }, { k0: th, k1: Number(o.levee) });
            T.destroy();
            T = T2;
        }
        let r = keep(Gd.fill(R, [rows, cols], 0.0)), coef = 0.0;
        if (truthy(o.rough)) {
            // pressure ridges and rubble: ridged noise (sharp crests, broad troughs) at 3 and 1.2 x the thickness
            const base = W ? 2 : 0;
            for (const [q, [wl, a]] of [[0, [3.0, 1.0]], [1, [1.2, 0.55]]]) {
                const g = keep(blur(nz[base + q], Math.max(wl * th / (4.0 * cell), 0.7)));
                const s = Math.max(await stdOf(R, g), 1e-9);
                r = keep(lavaRun(R, 6, { a: r, b: g }, { k0: a, k1: s }));
            }
            coef = Number(o.rough) * (1.0 - 0.7 * Number(o.age)) * th;
        }
        const T3 = lavaRun(R, 7, { a: T, b: r, c: plate }, { k0: coef });
        T.destroy();
        T = T3;
    } else {
        // the soft margin: two generators, the lobes' (9097) and the rough top's (9091)
        let mm = o.margin_m === null || o.margin_m === undefined ? 1.5 * th : Number(o.margin_m);
        mm *= 1.0 + 2.0 * Number(o.age);
        const mc = Math.max(mm / cell, 1.2);
        let core = path;
        if (W) {
            const sig = 0.25 * W / cell;
            const b0 = keep(ew(R, EW.LERP, null, keep(blur(path, sig)), null, null, 0.0, sqrtTau * sig));
            const nz = await standardNormalGpu(R, defaultRng([sd, 9097]), rows, cols, 2);
            nz.forEach(keep);
            let lobes = keep(Gd.fill(R, [rows, cols], 0.0));
            for (const [q, [frac, a]] of [[0, [0.12, 0.5]], [1, [0.04, 0.3]]]) {
                const g = keep(blur(nz[q], Math.max(frac * W / cell, 0.7)));
                const s = Math.max(await stdOf(R, g), 1e-9);
                lobes = keep(lavaRun(R, 9, { a: lobes, b: g }, { k0: a, k1: s }));
            }
            core = keep(lavaRun(R, 3, { a: b0, b: lobes }, { k0: 0.8, k1: 1.25 }));
        }
        const f1 = keep(blur(core, mc));
        plate = lavaRun(R, 4, { a: f1 }, { k0: 0.2 });
        const f2 = keep(blur(core, 3.0 * mc));
        T = lavaRun(R, 8, { a: plate, b: f2 }, { k0: th, k1: Number(o.levee) });
        let r = keep(Gd.fill(R, [rows, cols], 0.0)), coef = 0.0;
        if (truthy(o.rough)) {
            // pressure ridges and blocks: isotropic noise blurred at 6 and 2 x the thickness
            const nz = await standardNormalGpu(R, defaultRng([sd, 9091]), rows, cols, 2);
            nz.forEach(keep);
            for (const [q, [wl, a]] of [[0, [6.0, 1.0]], [1, [2.0, 0.5]]]) {
                const g = keep(blur(nz[q], Math.max(wl * th / (4.0 * cell), 0.7)));
                const s = Math.max(await stdOf(R, g), 1e-9);
                r = keep(lavaRun(R, 9, { a: r, b: g }, { k0: a, k1: s }));
            }
            coef = Number(o.rough) * (1.0 - 0.7 * Number(o.age)) * th;
        }
        const T3 = lavaRun(R, 7, { a: T, b: r, c: plate }, { k0: coef });
        T.destroy();
        T = T3;
    }
    for (const f of own) if (f && !f.destroyed && f !== T && f !== plate) f.destroy();
    return [T, plate];
}

// a window [j0, j1) x [i0, i1) of a level field, cropped (hydro/crop)
function cropOf(R, f, j0, j1, i0, i1) {
    const w = R.field(j1 - j0, i1 - i0, 1);
    R.run('hydro/crop', { src: f }, { outF: w }, { uOrigin: [i0, j0] });
    return w;
}

/** Stage op 'lava_flows' (design 4.7): flows from the vents (lavaVents) by DOWNFLOW walkers on this level's surface,
 * each the lava_surface of its walkers' passage, in lobed units, the later flows over the earlier ones (volcanic.py
 * op_lava_flows; its docstring holds). The walkers walk in JavaScript on the surface read back once per unit (their
 * draws depend on how many are alive each step, PORT_PLAN.md 2.4); everything per cell is on the GPU. The flows go into
 * h and bed (lava is rock) and their footprint, dulled with age, into 'lava'. Runs on the first level it selects. */
export async function opLavaFlows(fields, level, params, seed = 0, ctx = null) {
    if (isPrepass(ctx)) return fields;
    const key = stampKey('lava_flows', { ...params, seed });
    if (key in fields) return fields;
    const R = runnerOf(fields, ctx);
    const p = { ...LAVA_DEFAULTS };
    for (const [k, v] of Object.entries(params ?? {})) if (k in LAVA_DEFAULTS) p[k] = v;
    const vents = lavaVents(params ?? {}, seed);
    const [x0, y0, cell, n] = levelWindow(level);
    const h = fields.h;
    let total = Gd.fill(R, [n, n], 0.0);
    let foot = 'lava' in fields ? copyOf(fields.lava) : Gd.fill(R, [n, n], 0.0);
    const sd = Math.abs(Math.trunc(seed)) % 4294967296;
    for (let k = 0; k < vents.length; k++) {
        const v = { ...p };
        for (const [kk, vv] of Object.entries(vents[k])) if (vv !== null && vv !== undefined) v[kk] = vv;
        const at = [Number(v.at[0]), Number(v.at[1])];
        const fi = (at[0] - x0) / cell - 0.5, fj = (at[1] - y0) / cell - 0.5;
        if (!(fi >= 2 && fi < n - 2 && fj >= 2 && fj < n - 2)) continue;
        const th0 = Number(v.thickness_m), W0 = Number(v.width_m ?? 0.0) || 0.0;
        const dh = v.dh_m !== null && v.dh_m !== undefined ? Number(v.dh_m) : Number(v.dh_factor) * th0;
        // every height the flow compares (its walkers' ground, the onlap and the vent's level, the buried hollows) is
        // taken relative to the ground at the vent: they enter only as differences, which numpy forms in float64,
        // and float32 holds h - z_vent far finer than h itself (a tenth of a millimetre at 2 km), so fewer of the
        // walkers' near-ties are decided otherwise than numpy decides them
        const [zr] = await R.readRange(h, pyRound(fj) * n + pyRound(fi), 1);
        const zf = Gd.fill(R, [1, 1], zr);
        const hr = ew(R, EW.SUB, h, zf);
        zf.destroy();
        const ht = ew(R, EW.ADD, hr, total);
        hr.destroy();
        // the walkers' ground: the surface smoothed at the flow's own scale
        const g = copyOf(ht);
        const sig = Math.max(2.0 * th0, 0.5 * W0) / cell;
        if (sig > 0.5) {
            const r0 = Math.ceil(Number(v.length_m) / cell + 8.0 * sig);
            const ci = pyRound(fi), cj = pyRound(fj);
            const j0 = Math.max(cj - r0, 0), j1 = Math.min(cj + r0 + 1, n), i0 = Math.max(ci - r0, 0), i1 = Math.min(ci + r0 + 1, n);
            const win = cropOf(R, g, j0, j1, i0, i1);
            const bw = blur(win, sig);
            win.destroy();
            lavaRun(R, 16, { a: bw }, { at: [i0, j0] }, { outF: g });
            bw.destroy();
        }
        let units = Math.max(Math.trunc(Number(v.units || 1)), 1);
        const unitCount = units;                  // volcanic.py's range(units), fixed before units = 1 below
        const urng = defaultRng([sd, 9113, k]);
        let tv = Gd.fill(R, [n, n], 0.0);
        const fv = Gd.fill(R, [n, n], 0.0);
        let start = [fi, fj], axis = null;
        for (let u = 0; u < unitCount; u++) {
            const vu = { ...v };
            if (u) {
                // a first unit with no passage over 0.05 leaves no axis: volcanic.py sets units = 1 but its range runs
                // on, and unpacking None raises (a Blender defect, kept: the port runs as the edition does)
                if (axis === null) throw new TypeError('cannot unpack non-iterable NoneType object');
                const [[ai, aj], [di, dj], Lax] = axis;
                vu.length_m = Number(v.length_m) * urng.uniform(0.25, 0.6);
                vu.thickness_m = Number(v.thickness_m) * urng.uniform(0.7, 1.0);
                if (W0) vu.width_m = W0 * urng.uniform(0.35, 0.7);
                let s, lat;
                if (urng.random() < 0.5) {                     // from a side, alongside the first unit
                    s = urng.uniform(0.2, 0.8) * Lax;
                    lat = urng.choice([-1.0, 1.0]) * (0.5 * W0 + 0.15 * (Number(vu.width_m ?? 0.0) || 0.0)) / cell;
                } else {                                       // from the front, pushing it on
                    s = urng.uniform(0.8, 1.0) * Lax;
                    lat = urng.uniform(-0.3, 0.3) * W0 / cell;
                }
                if (truthy(v.channel)) {
                    s = Math.max(s, Math.min(num(v.channel.until, 0.45) * Number(v.length_m) / cell, Lax));
                }
                start = [Math.min(Math.max(ai + s * di - lat * dj, 2), n - 3), Math.min(Math.max(aj + s * dj + lat * di, 2), n - 3)];
            }
            // a later unit sees the earlier ones smoothed at the walkers' scale
            let gu = g;
            if (u) {
                const bt = blur(tv, Math.max(sig, 1.0));
                gu = ew(R, EW.ADD, g, bt);
                bt.destroy();
            }
            const host = await R.read(gu);
            const th = Number(vu.thickness_m);
            const walk = lavaWalkers(host, n, n, cell, start, Math.trunc(vu.walkers), Number(vu.length_m), dh, seed,
                u === 0 ? k : k * 16 + u, v.dh_rel, th, Number(v.stop_spread), u === 0 ? Number(v.front_spread) : 0.0);
            if (u === 0 && units > 1) {
                // the first unit's axis: from its vent toward the passage's centroid, twice that far (np.nonzero's
                // order, numpy's pairwise sums)
                const pj = [], pi = [], w = [];
                for (const c of walk.cells) {
                    const pv = Math.min(walk.visits[c] / walk.N, 1.0);
                    if (pv > 0.05) { pj.push(Math.floor(c / n)); pi.push(c % n); w.push(pv); }
                }
                if (pj.length) {
                    const sw = npSum(Float64Array.from(w));
                    const cj = npSum(Float64Array.from(pj, (x, q) => x * w[q])) / sw;
                    const ci = npSum(Float64Array.from(pi, (x, q) => x * w[q])) / sw;
                    const dist = Math.max(Math.hypot(ci - fi, cj - fj), 1.0);
                    axis = [[fi, fj], [(ci - fi) / dist, (cj - fj) / dist], 2.0 * dist];
                } else {
                    units = 1;
                }
            }
            // the unit's own window: where walkers went, plus room for its width, margins and levees
            let jmin = n, jmax = -1, imin = n, imax = -1;
            for (const c of walk.cells) {
                const jj = Math.floor(c / n), ii = c % n;
                jmin = Math.min(jmin, jj); jmax = Math.max(jmax, jj); imin = Math.min(imin, ii); imax = Math.max(imax, ii);
            }
            const mc = Math.max(1.5 * th * (1.0 + 2.0 * Number(v.age)) / cell, 1.2);
            const pad = Math.ceil(12.0 * mc + 2.0 * (Number(vu.width_m ?? 0.0) || 0.0) / cell + 8);
            const j0 = Math.max(jmin - pad, 0), j1 = Math.min(jmax + pad + 1, n), i0 = Math.max(imin - pad, 0), i1 = Math.min(imax + pad + 1, n);
            const vf = R.field(n, n, 1, walk.visits);
            const Pfull = lavaRun(R, 0, { a: vf }, { k0: walk.N });
            vf.destroy();
            const Pw = cropOf(R, Pfull, j0, j1, i0, i1);
            Pfull.destroy();
            const worg = [x0 + i0 * cell - at[0], y0 + j0 * cell - at[1]];
            let wsc = null;
            if (truthy(v.spread_slope_deg) && truthy(vu.width_m)) {
                // lava spreads where the ground levels out: the width x sqrt(tan(spread_slope) / tan(slope)), 0.5-1.6
                const gw = cropOf(R, gu, j0, j1, i0, i1);
                const { gx, gy } = Gd.gradient(gw, cell);
                wsc = lavaRun(R, 15, { a: gx, b: gy }, { k0: Math.tan(radians(Number(v.spread_slope_deg))) });
                for (const f of [gw, gx, gy]) f.destroy();
            }
            if (u === 0 && truthy(v.channel) && truthy(vu.width_m)) {
                // a channelled reach: the first unit leaves its vent at frac of its width, opening to the full width
                const ch = v.channel;
                const ramp = lavaRun(R, 14, { a: wsc ?? Pw }, { org: worg, step: cell, k0: num(ch.frac, 0.4), k1: num(ch.until, 0.45),
                    len: Number(vu.length_m), flag: wsc ? 1 : 0 });
                if (wsc) wsc.destroy();
                wsc = ramp;
            }
            let [T, F] = await lavaSurface(R, Pw, cell, th, { p_edge: Number(v.p_edge), margin_m: null, levee: Number(v.levee),
                rough: Number(v.rough), age: Number(v.age), seed: Math.trunc(seed) + 13 * k + 7 * u, width_m: vu.width_m,
                front_deg: v.front_deg, levee_frac: Number(v.levee_frac), width_scale: wsc });
            if (wsc) wsc.destroy();
            if (v.no_climb === 'local') {
                // the flow's top at most 1.3 x its thickness over the ground its own paths run on nearby
                const gw = cropOf(R, ht, j0, j1, i0, i1);
                const [pw, gwpw] = lavaRun(R, 20, { a: Pw, b: gw });
                const sg = Math.max(0.25 * (Number(vu.width_m ?? 0.0) || 4.0 * th) / cell, 1.0);
                const bw = blur(pw, sg), bgw = blur(gwpw, sg);
                const [T2, F2] = lavaRun(R, 11, { a: T, b: F, c: gw, d: bw, e: bgw }, { k0: th });
                for (const f of [gw, pw, gwpw, bw, bgw, T, F]) f.destroy();
                T = T2;
                F = F2;
            } else if (truthy(v.no_climb)) {
                // none of it on the cone it left: the ground at and below its vent
                const sj = pyRound(start[1]), si = pyRound(start[0]);
                const [zv] = await R.readRange(ht, sj * n + si, 1);
                const gw = cropOf(R, ht, j0, j1, i0, i1);
                const [T2, F2] = lavaRun(R, 12, { a: T, b: F, c: gw }, { k0: zv, k1: th });
                for (const f of [gw, T, F]) f.destroy();
                T = T2;
                F = F2;
            }
            if (u === 0 && truthy(v.width_m) && Number(v.vent_taper) > 0.0) {
                // a flow leaves its vent narrow and spreads downstream
                const [T2, F2] = lavaRun(R, 13, { a: T, b: F }, { org: worg, step: cell, k0: Number(v.vent_taper) * Number(v.width_m) });
                T.destroy();
                F.destroy();
                T = T2;
                F = F2;
            }
            lavaRun(R, 17, { a: T }, { at: [i0, j0] }, { outF: tv });
            lavaRun(R, 17, { a: F }, { at: [i0, j0] }, { outF: fv });
            for (const f of [T, F, Pw]) f.destroy();
            if (gu !== g) gu.destroy();
        }
        if (truthy(v.bury)) {
            // the flow fills the gullies and hollows it runs over: its base is the walkers' ground g
            const t2 = lavaRun(R, 18, { a: tv, b: g, c: ht, d: fv });
            tv.destroy();
            tv = t2;
        }
        const t3 = ew(R, EW.ADD, total, tv);
        total.destroy();
        total = t3;
        const f3 = lavaRun(R, 19, { a: foot, b: fv }, { k0: Number(v.age) });
        foot.destroy();
        foot = f3;
        for (const f of [tv, fv, g, ht]) f.destroy();
    }
    fields.h = ew(R, EW.ADD, h, total);
    if ('bed' in fields) fields.bed = ew(R, EW.ADD, fields.bed, total);
    fields.lava = foot;
    fields[key] = total;
    pullBand(fields, ctx);
    return fields;
}


// ================================================================================================= the ops ===

for (const op of [opStratovolcano, opCinderCones, opCalderaCollapse, opVolcanoSetting, opVolcanoPlain, opVolcanoAge,
    opLavaFlows, opCalderaLake, opVolcanoLakes]) op.evolves = true;   // run.js calls them on every pass of the coarsest
                                                                      // level; the stamps skip the pre-passes
export const OPS = { stratovolcano: opStratovolcano, cinder_cones: opCinderCones, caldera_collapse: opCalderaCollapse,
    volcano_setting: opVolcanoSetting, volcano_plain: opVolcanoPlain, volcano_age: opVolcanoAge, lava_flows: opLavaFlows,
    lava_rubble: opLavaRubble, cone_rills: opConeRills, caldera_lake: opCalderaLake, volcano_lakes: opVolcanoLakes };

