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
//     FUJI, CRATER_LAKE, SP_CRATER   the reference presets, measured from the reference DEMs
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

import { createHash } from 'node:crypto';
import * as Gd from '../core/grid.js';
import { ValueError, pyFormat, pyRepr, pyRound } from '../core/levels.js';
import { defaultRng } from '../core/np_random.js';
import { keyToFloat, prims } from '../core/prims.js';
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
    for (const t of FACE_TABLES.values()) for (const f of [t.Z, t.S, t.S0]) if (f && !f.destroyed) f.destroy();
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
    const P = prims(R);
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

const logOf = (ctx) => (ctx && typeof ctx.log === 'function' ? ctx.log : () => {});


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


// ================================================================================================= the ops ===

for (const op of [opStratovolcano, opCinderCones, opCalderaCollapse]) op.evolves = true;   // run.js calls them on every
                                                                          // pass of the coarsest level; the stamps skip the pre-passes
export const OPS = { stratovolcano: opStratovolcano, cinder_cones: opCinderCones, caldera_collapse: opCalderaCollapse };
