// Port of blender/eidoblend/terrain/core/levels.py at f90c6fc.
//
// Nested levels around the shot (design section 2.2): planLevels and the stage `levels` selector.
//
// A terrain is a stack of square windows, coarsest first: context levels for the horizon, the main tile, and hero
// levels around the camera. Each child has half its parent's cell; its window edges lie on its parent's EVEN grid
// lines (so the child's cells nest 2 x 2 inside the parent's, and the hole in the parent's stride-2 mesh lines up
// with the child's edge) and it stays at least `band` parent cells inside its parent.
//
//     const plan = planLevels(8000, 1024, { centre: [0, 0], context: 4, focus: [1200, -300], hero: 0.5 });
//     for (const lv of plan) console.log(String(lv));  // Level(0 context 32000 m @ 31.25 m x1024 ...), ...,
//                                                      // Level(6 hero 500 m @ 0.4883 m x1024)
//     lv.window                     // [x0, y0, side, cell, n]
//     lv.inParent(plan)             // [i0, j0, m]: the window in its parent's cells
//     selectLevels('cell<=40', plan) -> [indices];  'all' 'first' 'context' 'main' 'hero' 'cell>=30'
//                                     'resolves:2000' (the first level whose cell is at most 2000 / 8 m)
//     QUALITY.film                  // { resolution: 1024, hero_cell: 0.5, steps_scale: 1.0 }
//
// Rules (each one the design's):
// - context levels: ceil(log2(context)) of them, each twice the next's side, centred on the tile centre, all with
//   the main tile's cell count;
// - the coarsest level carries `prepass`: the cell counts it is solved at before its own (n / 2^k while >= 192:
//   256 and 512 for 1024), each upsampled into the next;
// - the main tile: `size` metres at `resolution` cells (a multiple of 8, so the nesting is exact);
// - hero levels, only with a focus and a hero cell: each half its parent's side but never smaller than the focus's
//   bounding box plus a margin (the border band plus 16 free cells, each side), centred on the focus, snapped and
//   kept inside its parent; they continue until the cell is at most `hero` metres. A large focus grows the cell
//   count, up to maxCells (2048); past that, or when the focus no longer fits inside the parent, the cell stops
//   shrinking and a warning says so;
// - the border band is 16 cells: there the child is pinned to its parent (core/grid.js borderRamp).
//
// Frames: Blender's (x east, y north, metres), as every array of the port keeps them (PORT_PLAN.md 2.2); api.js
// converts a three.js focus (x, z) to (x, -z) before it calls planLevels.
//
// Python's arithmetic, reproduced (PORT_PLAN.md 2.3, C10): every round() of levels.py is pyRound (half to even on
// doubles; Math.round rounds halves up), math.ceil / math.floor are Math.ceil / Math.floor with the same epsilons,
// int(x) truncates. This module also holds the Python behaviours the other core modules share: pyRound,
// pyFormat (str.format's 'g', 'f' and 'e' with Python's correctly rounded half-to-even digits), pyRepr (repr of a
// float) and closeMatches (difflib.get_close_matches, transcribed). build/mesh.js and api.js import pyRound.
//
// Where this differs from levels.py, and why:
//   - Level.xy() (float64 meshgrids of every cell centre) is not here: per-cell work runs on the GPU, where a kernel
//     makes a cell's centre from the window (common.wgsl world_xy; core/grid.js, compose.js and world_noise.js take
//     the window). contains() and indexOf() take numbers or plain arrays of points (a few, never a level's cells).
//   - Options are one object in the edition's camelCase (planLevels(size, resolution, { centre, context, focus,
//     hero, band, maxCells, warn })); Level's own members and toDict() keep Blender's names, so a plan's JSON is
//     Blender's.
//   - JavaScript has one number type: a stage's level index 2.0 is the integer 2 here (Python refuses the float).

export const BAND = 16;                                 // the border band, cells
export const FREE = 16;                                 // cells between the band and the focus, each side
export const MAX_CELLS = 2048;
export const PREPASS_MIN = 192;
export const QUALITY = {
    draft: { resolution: 512, hero_cell: null, steps_scale: 0.5 },
    film: { resolution: 1024, hero_cell: 0.5, steps_scale: 1.0 },
    hero: { resolution: 2048, hero_cell: 0.25, steps_scale: 1.0 },
};
export const ROLES = ['context', 'main', 'hero'];


// ------------------------------------------------------------------------------------ Python's arithmetic ---

/** The Blender core's exception kinds, so a caller can tell them apart (TypeError is JavaScript's own). */
export class ValueError extends Error {
    constructor(message) {
        super(message);
        this.name = 'ValueError';
    }
}
export class KeyError extends Error {
    constructor(message) {
        super(message);
        this.name = 'KeyError';
    }
}
export class IndexError extends Error {
    constructor(message) {
        super(message);
        this.name = 'IndexError';
    }
}

/** Python's round(x) for a float: the nearest integer, halves to the even one (x is a double, so a half is exact). */
export function pyRound(x) {
    if (!Number.isFinite(x)) {
        throw new ValueError(Number.isNaN(x) ? 'cannot convert float NaN to integer' : 'cannot convert float infinity to integer');
    }
    let r = Math.round(x);                              // the nearest integer, halves toward +infinity
    if (r - x === 0.5 && Math.abs(r % 2) === 1) r -= 1; // r - x is exact: a half is a tie, sent to the even side
    return r === 0 ? 0 : r;                             // Python's int has no -0
}

/** Python's int(x) of a float: toward zero. */
export const pyInt = (x) => {
    if (!Number.isFinite(x)) throw new ValueError(`cannot convert float ${x} to integer`);
    return Math.trunc(x) + 0;
};

// The exact decimal expansion of a finite double: { neg, digits, point } with |x| = 0.digits x 10^point (digits
// without leading or trailing zeros; '0' and point 1 for zero). Every double has a finite expansion.
const DV = new DataView(new ArrayBuffer(8));
function exactDecimal(x) {
    DV.setFloat64(0, x);
    const hi = DV.getUint32(0), lo = DV.getUint32(4);
    const neg = (hi >>> 31) === 1;
    let e = (hi >>> 20) & 0x7ff;
    let m = (BigInt(hi & 0xfffff) << 32n) | BigInt(lo);
    if (e === 0) e = 1;
    else m |= 1n << 52n;
    if (m === 0n) return { neg, digits: '0', point: 1 };
    const e2 = e - 1075;
    let s, point;
    if (e2 >= 0) {
        s = (m << BigInt(e2)).toString();
        point = s.length;
    } else {
        s = (m * 5n ** BigInt(-e2)).toString();     // m / 2^k = m 5^k / 10^k
        point = s.length + e2;
    }
    s = s.replace(/0+$/, '');
    return { neg, digits: s, point };
}

// digits rounded to keep `keep` of them (keep may be <= 0), half to even on the exact expansion
function roundDigits(digits, point, keep) {
    if (keep >= digits.length) return { digits, point };
    if (keep < 0) return { digits: '0', point: point, zero: true };
    const head = keep > 0 ? digits.slice(0, keep) : '0';
    const next = digits.charCodeAt(keep) - 48;
    const rest = digits.slice(keep + 1);
    const up = next > 5 || (next === 5 && (/[1-9]/.test(rest) || ((keep > 0 ? head.charCodeAt(keep - 1) - 48 : 0) % 2 === 1)));
    if (keep === 0) {
        // nothing kept: the result is 0 or one unit at this position
        return up ? { digits: '1', point: point + 1 } : { digits: '0', point, zero: true };
    }
    if (!up) return { digits: head.replace(/0+$/, '') || '0', point, zero: !/[1-9]/.test(head) };
    const carry = (BigInt(head) + 1n).toString();
    let p = point;
    if (carry.length > head.length) p += 1;
    return { digits: carry.replace(/0+$/, ''), point: p };
}

/** Python's format(x, spec) for spec 'g', '.Ng', '.Nf', '.Ne' (and '' = str): correctly rounded, halves to even,
 * as CPython formats floats. An integral number with spec '' or 'd' prints as an int. */
export function pyFormat(x, spec = '') {
    if (spec === '' ) return pyStr(x);
    if (spec === 'd') return String(pyInt(x));
    const m = /^\.?(\d*)([gfe])$/.exec(spec);
    if (!m) throw new Error(`pyFormat: spec '${spec}' is not g, .Ng, .Nf or .Ne`);
    const kind = m[2];
    let p = m[1] === '' ? 6 : parseInt(m[1], 10);
    if (Number.isNaN(x)) return 'nan';
    if (!Number.isFinite(x)) return x > 0 ? 'inf' : '-inf';
    const { neg, digits, point } = exactDecimal(x);
    const sign = neg ? '-' : '';
    const isZero = digits === '0';
    const fixed = (dg, pt, decimals) => {         // dg rounded already; pt the point; decimals after the point
        let intPart, frac;
        if (pt <= 0) {
            intPart = '0';
            frac = '0'.repeat(-pt) + dg;
        } else if (pt >= dg.length) {
            intPart = dg + '0'.repeat(pt - dg.length);
            frac = '';
        } else {
            intPart = dg.slice(0, pt);
            frac = dg.slice(pt);
        }
        frac = (frac + '0'.repeat(Math.max(0, decimals))).slice(0, Math.max(0, decimals));
        return decimals > 0 ? `${intPart}.${frac}` : intPart;
    };
    const sci = (dg, pt, decimals) => {
        const e = pt - 1;
        const mant = dg[0] + (decimals > 0 ? '.' + (dg.slice(1) + '0'.repeat(decimals)).slice(0, decimals) : '');
        return `${mant}e${e < 0 ? '-' : '+'}${String(Math.abs(e)).padStart(2, '0')}`;
    };
    if (kind === 'f') {
        if (isZero) return sign + fixed('0', 1, p);
        const r = roundDigits(digits, point, point + p);
        return sign + (r.zero ? fixed('0', 1, p) : fixed(r.digits, r.point, p));
    }
    if (kind === 'e') {
        if (isZero) return sign + sci('0', 1, p);
        const r = roundDigits(digits, point, p + 1);
        return sign + sci(r.digits, r.point, p);
    }
    // 'g'
    if (p === 0) p = 1;
    if (isZero) return sign + '0';
    const r = roundDigits(digits, point, p);
    const exp = r.point - 1;
    if (exp >= -4 && exp < p) {
        let s = fixed(r.digits, r.point, p - 1 - exp);
        if (s.includes('.')) s = s.replace(/0+$/, '').replace(/\.$/, '');
        return sign + s;
    }
    let s = sci(r.digits, r.point, p - 1);
    s = s.replace(/\.?0+e/, 'e');
    return sign + s;
}

/** Python's repr(float): the shortest digits that round-trip (JavaScript finds the same), laid out as Python lays
 * them out (scientific below 1e-4 and from 1e16, otherwise fixed with at least one decimal). */
export function pyRepr(x) {
    if (Number.isNaN(x)) return 'nan';
    if (!Number.isFinite(x)) return x > 0 ? 'inf' : '-inf';
    if (x === 0) return Object.is(x, -0) ? '-0.0' : '0.0';
    // Number::toString's digits: the shortest that round-trip, the closest of them to x (Python's repr rule too)
    const sign = x < 0 ? '-' : '';
    const t = String(Math.abs(x));
    let dg, e;
    if (t.includes('e')) {
        const [mant, ex] = t.split('e');
        dg = mant.replace('.', '');
        e = parseInt(ex, 10);
    } else {
        const [ip, fp = ''] = t.split('.');
        const all = (ip + fp).replace(/^0+/, '');
        dg = all.replace(/0+$/, '');
        e = ip !== '0' ? ip.length - 1 : -(fp.length - fp.replace(/^0+/, '').length) - 1;
        if (!dg) dg = '0';
    }
    if (e < -4 || e >= 16) {
        const m = dg.length > 1 ? `${dg[0]}.${dg.slice(1)}` : dg;
        return `${sign}${m}e${e < 0 ? '-' : '+'}${String(Math.abs(e)).padStart(2, '0')}`;
    }
    const point = e + 1;
    if (point <= 0) return `${sign}0.${'0'.repeat(-point)}${dg}`;
    if (point >= dg.length) return `${sign}${dg}${'0'.repeat(point - dg.length)}.0`;
    return `${sign}${dg.slice(0, point)}.${dg.slice(point)}`;
}

/** str() of a JSON-like value as Python prints it. JavaScript has one number type: an integral number prints as
 * a Python int, any other as a float's repr. Strings inside lists and dicts take repr's single quotes. */
export function pyStr(v, inner = false) {
    if (v === null || v === undefined) return 'None';
    if (v === true) return 'True';
    if (v === false) return 'False';
    if (typeof v === 'number') return Number.isInteger(v) && Math.abs(v) < 1e16 ? String(v) : pyRepr(v);
    if (typeof v === 'string') return inner ? pyQuote(v) : v;
    if (Array.isArray(v)) return '[' + v.map((x) => pyStr(x, true)).join(', ') + ']';
    if (typeof v === 'object') return '{' + Object.entries(v).map(([k, x]) => `${pyQuote(k)}: ${pyStr(x, true)}`).join(', ') + '}';
    return String(v);
}

/** repr() of a JSON-like value (strings quoted as Python quotes them). */
export const pyReprValue = (v) => pyStr(v, true);

function pyQuote(s) {
    const q = s.includes("'") && !s.includes('"') ? '"' : "'";
    let out = '';
    for (const ch of s) {
        const c = ch.codePointAt(0);
        if (ch === '\\') out += '\\\\';
        else if (ch === q) out += '\\' + q;
        else if (ch === '\n') out += '\\n';
        else if (ch === '\r') out += '\\r';
        else if (ch === '\t') out += '\\t';
        else if (c < 0x20 || c === 0x7f) out += '\\x' + c.toString(16).padStart(2, '0');
        else out += ch;
    }
    return q + out + q;
}

// difflib.SequenceMatcher(None, a, b).ratio(), transcribed (no junk; autojunk only reaches strings of 200 or more)
function matcherRatio(a, b) {
    const b2j = new Map();
    for (let i = 0; i < b.length; i++) {
        const c = b[i];
        if (!b2j.has(c)) b2j.set(c, []);
        b2j.get(c).push(i);
    }
    if (b.length >= 200) {
        const ntest = Math.floor(b.length / 100) + 1;
        for (const [c, idx] of [...b2j]) if (idx.length > ntest) b2j.delete(c);
    }
    const longest = (alo, ahi, blo, bhi) => {
        let besti = alo, bestj = blo, bestsize = 0;
        let j2len = new Map();
        for (let i = alo; i < ahi; i++) {
            const next = new Map();
            for (const j of b2j.get(a[i]) ?? []) {
                if (j < blo) continue;
                if (j >= bhi) break;
                const k = (j2len.get(j - 1) ?? 0) + 1;
                next.set(j, k);
                if (k > bestsize) {
                    besti = i - k + 1;
                    bestj = j - k + 1;
                    bestsize = k;
                }
            }
            j2len = next;
        }
        while (besti > alo && bestj > blo && a[besti - 1] === b[bestj - 1]) {
            besti--;
            bestj--;
            bestsize++;
        }
        while (besti + bestsize < ahi && bestj + bestsize < bhi && a[besti + bestsize] === b[bestj + bestsize]) bestsize++;
        return [besti, bestj, bestsize];
    };
    let matches = 0;
    const queue = [[0, a.length, 0, b.length]];
    while (queue.length) {
        const [alo, ahi, blo, bhi] = queue.pop();
        const [i, j, k] = longest(alo, ahi, blo, bhi);
        if (k) {
            matches += k;
            if (alo < i && blo < j) queue.push([alo, i, blo, j]);
            if (i + k < ahi && j + k < bhi) queue.push([i + k, ahi, j + k, bhi]);
        }
    }
    const len = a.length + b.length;
    return len ? (2.0 * matches) / len : 1.0;
}

/** difflib.get_close_matches(word, possibilities, n, cutoff): the best matches, best first (ties: the larger
 * string first, as heapq.nlargest orders (score, word) pairs). */
export function closeMatches(word, possibilities, n = 3, cutoff = 0.6) {
    if (!(n > 0)) throw new ValueError(`n must be > 0: ${n}`);
    if (!(cutoff >= 0 && cutoff <= 1)) throw new ValueError(`cutoff must be in [0.0, 1.0]: ${cutoff}`);
    const w = [...String(word)];
    const res = [];
    for (const x of possibilities) {
        const r = matcherRatio([...String(x)], w);
        if (r >= cutoff) res.push([r, String(x)]);
    }
    res.sort((p, q) => (q[0] - p[0]) || (p[1] < q[1] ? 1 : p[1] > q[1] ? -1 : 0));
    return res.slice(0, n).map((p) => p[1]);
}


// ------------------------------------------------------------------------------------------------- Level ---

const LEVEL_KEYS = ['index', 'role', 'x0', 'y0', 'side', 'cell', 'n', 'parent', 'stride', 'prepass', 'band', 'depth',
    'notes'];

/** One square window: (x0, y0, side, cell, n) plus its place in the stack. */
export class Level {
    constructor(index, role, x0, y0, side, cell, n, parent = null, stride = 2, prepass = [], band = BAND, depth = 0,
        notes = []) {
        this.index = index;
        this.role = role;                                // 'context' | 'main' | 'hero'
        this.x0 = x0;
        this.y0 = y0;
        this.side = side;
        this.cell = cell;
        this.n = n;
        this.parent = parent;                            // the index of the next coarser level
        this.stride = stride;                            // the ring mesh's vertex stride (1 on hero levels, 2 elsewhere)
        this.prepass = [...prepass];                     // coarse-to-fine cell counts before this level's own
        this.band = band;
        this.depth = depth;                              // main = 0; context levels > 0; hero < 0
        this.notes = [...notes];
    }

    get window() { return [this.x0, this.y0, this.side, this.cell, this.n]; }
    get x1() { return this.x0 + this.side; }
    get y1() { return this.y0 + this.side; }
    get centre() { return [this.x0 + 0.5 * this.side, this.y0 + 0.5 * this.side]; }
    /** [x0, y0, cell]: what a kernel's world_xy takes. */
    get lv() { return [this.x0, this.y0, this.cell]; }
    /** [h, w]: a level's arrays are n x n. */
    get shape() { return [this.n, this.n]; }

    /** Whether world points are inside the window (margin metres in from its edge): a boolean for a point (x, y),
     * an array of booleans for arrays of x and y. */
    contains(x, y, margin = 0.0) {
        const one = (a, b) => a >= this.x0 + margin && a <= this.x1 - margin && b >= this.y0 + margin && b <= this.y1 - margin;
        if (Array.isArray(x)) return x.map((a, i) => one(a, y[i]));
        return one(x, y);
    }

    /** Fractional [i, j] of a world point; cell centres are whole numbers. */
    indexOf(x, y) {
        return [(x - this.x0) / this.cell - 0.5, (y - this.y0) / this.cell - 0.5];
    }

    /** [i0, j0, m]: this window in its parent's cells (whole numbers by construction), or null for level 0. */
    inParent(levels) {
        if (this.parent === null || this.parent === undefined) return null;
        const p = levels[this.parent];
        return [pyRound((this.x0 - p.x0) / p.cell), pyRound((this.y0 - p.y0) / p.cell), pyRound(this.side / p.cell)];
    }

    /** The same window at m cells (a coarse-to-fine pre-pass of the coarsest level). */
    withCells(m) {
        return new Level(this.index, this.role, this.x0, this.y0, this.side, this.side / m, pyInt(m), this.parent,
            this.stride, [], this.band, this.depth, [`prepass of level ${this.index}`]);
    }

    toDict() {
        const d = {};
        for (const k of LEVEL_KEYS) d[k] = Array.isArray(this[k]) ? [...this[k]] : this[k];
        return d;
    }

    static fromDict(d) {
        const extra = Object.keys(d).filter((k) => !LEVEL_KEYS.includes(k));
        if (extra.length) throw new TypeError(`Level.__init__() got an unexpected keyword argument '${extra[0]}'`);
        return new Level(d.index, d.role, d.x0, d.y0, d.side, d.cell, d.n, d.parent ?? null, d.stride ?? 2,
            d.prepass ?? [], d.band ?? BAND, d.depth ?? 0, d.notes ?? []);
    }

    toString() {
        return `Level(${this.index} ${this.role} ${pyFormat(this.side, 'g')} m @ ${pyFormat(this.cell, '.4g')} m x${this.n}, ` +
            `x0 ${pyFormat(this.x0, 'g')} y0 ${pyFormat(this.y0, 'g')}` +
            (this.prepass.length ? `, prepass ${pyStr(this.prepass)}` : '') + ')';
    }
}
Level.prototype.to_dict = Level.prototype.toDict;
Level.from_dict = Level.fromDict;


// -------------------------------------------------------------------------------------------------- the focus ---

const shapeText = (a) => `(${a.join(', ')}${a.length === 1 ? ',' : ''})`;

/** A focus as an array of world [x, y] points: a point, a list of points, a camera (anything with .location), or
 * a list of camera positions (x, y[, z]). null for none. Blender frame (x east, y north). */
export function focusPoints(focus) {
    if (focus === null || focus === undefined) return null;
    if (typeof focus === 'object' && !Array.isArray(focus) && focus.location) {
        return [[Number(focus.location[0]), Number(focus.location[1])]];
    }
    if (Array.isArray(focus) && focus.length && focus[0] && typeof focus[0] === 'object' && !Array.isArray(focus[0]) && focus[0].location) {
        return focus.map((f) => [Number(f.location[0]), Number(f.location[1])]);
    }
    const arr = Array.isArray(focus) ? focus : [focus];
    let rows;
    if (arr.every((v) => typeof v === 'number')) rows = [arr];
    else if (arr.every((v) => Array.isArray(v) && v.every((x) => typeof x === 'number'))) rows = arr;
    else rows = null;
    const shape = rows === null ? [arr.length] : [rows.length, rows.length ? rows[0].length : 0];
    if (rows === null || !rows.length || rows.some((r) => r.length !== rows[0].length) || rows[0].length < 2) {
        throw new ValueError(`focus must be (x, y), a list of (x, y[, z]) or a camera; got shape ${shapeText(shape)}`);
    }
    return rows.map((r) => [Number(r[0]), Number(r[1])]);
}
export const focus_points = focusPoints;

const snap = (v, origin, step) => origin + step * pyRound((v - origin) / step);


// --------------------------------------------------------------------------------------------- planLevels ---

const defaultWarn = (m) => console.log('[terrain.levels] ' + m);

/** The level stack, coarsest first (see the module doc for the rules). size: the main tile's side in metres;
 * resolution: its cell count (a multiple of 8); opts.context: the horizon's extent multiplier (null or <= 1: none);
 * opts.focus: a point, points or camera(s) inside the main tile; opts.hero: the finest cell in metres around the
 * focus (null: no hero levels); opts.centre [x, y]; opts.band; opts.maxCells; opts.warn(message). Throws for a
 * focus outside the main tile or a bad resolution. */
export function planLevels(size, resolution, opts = {}) {
    const { centre = [0.0, 0.0], context = null, focus = null, hero = null, band = BAND, maxCells = MAX_CELLS } = opts;
    const warn = opts.warn ?? defaultWarn;
    size = Number(size);
    const n = pyInt(Number(resolution));
    if (size <= 0) throw new ValueError(`size must be positive metres, got ${pyStr(size)}`);
    if (n < 64 || n % 8) {
        const lo = Math.max(64, n - (((n % 8) + 8) % 8)), hi = Math.max(64, n - (((n % 8) + 8) % 8) + 8);
        throw new ValueError(`resolution ${n} must be a multiple of 8 (at least 64) so the levels nest exactly; nearest: ${lo} or ${hi}`);
    }
    const cx = Number(centre[0]), cy = Number(centre[1]);
    const mainCell = size / n;
    const nctx = context && context > 1 ? pyInt(Math.ceil(Math.log2(context) - 1e-9)) : 0;

    // context levels, outermost first, each on its child's even grid lines
    const main = new Level(0, 'main', cx - size / 2, cy - size / 2, size, mainCell, n, null, 2, [], band, 0);
    const levels = [main];
    for (let d = 1; d <= nctx; d++) {
        const child = levels[0];
        const cell = mainCell * 2 ** d;
        const off = 2 * pyRound(n / 8.0);               // n / 4 parent cells: the child centred (n % 8 == 0: exact)
        levels.unshift(new Level(0, 'context', child.x0 - off * cell, child.y0 - off * cell, n * cell, cell, n, null, 2, [],
            band, d));
    }

    // hero levels
    const pts = focusPoints(focus);
    if (pts !== null) {
        const bad = pts.find(([x, y]) => !main.contains(x, y));
        if (bad) {
            throw new ValueError(`focus (${pyFormat(bad[0], 'g')}, ${pyFormat(bad[1], 'g')}) is outside the main tile ` +
                `[${pyFormat(main.x0, 'g')}, ${pyFormat(main.x1, 'g')}] x [${pyFormat(main.y0, 'g')}, ${pyFormat(main.y1, 'g')}] m`);
        }
    }
    if (pts !== null && hero) {
        const bx0 = Math.min(...pts.map((p) => p[0])), by0 = Math.min(...pts.map((p) => p[1]));
        const bx1 = Math.max(...pts.map((p) => p[0])), by1 = Math.max(...pts.map((p) => p[1]));
        const fcx = 0.5 * (bx0 + bx1), fcy = 0.5 * (by0 + by1);
        const extent = Math.max(bx1 - bx0, by1 - by0);
        let parent = levels[levels.length - 1];
        while (parent.cell > hero * (1.0 + 1e-9)) {
            const cell = parent.cell / 2.0;
            const step = 2.0 * parent.cell;                // the parent's even grid lines
            const margin = (band + FREE) * cell;
            let side = Math.max(parent.side / 2.0, extent + 2.0 * margin);
            side = step * Math.ceil(side / step - 1e-9);
            const m = pyRound(side / cell);
            const limit = parent.side - 2.0 * band * parent.cell;
            if (side > limit + 1e-6) {
                warn(`the focus (${pyFormat(extent, '.0f')} m across) does not fit a hero window inside the ` +
                    `${pyFormat(parent.side, 'g')} m level: the hero cell stops at ${pyFormat(parent.cell, '.3g')} m instead of ${pyFormat(hero, 'g')} m`);
                break;
            }
            if (m > maxCells) {
                warn(`a hero window around the focus (${pyFormat(extent, '.0f')} m across) at ${pyFormat(cell, '.3g')} m cells would need ` +
                    `${m} cells (> ${maxCells}): the hero cell stops at ${pyFormat(parent.cell, '.3g')} m instead of ${pyFormat(hero, 'g')} m`);
                break;
            }
            const loX = parent.x0 + band * parent.cell, hiX = parent.x1 - band * parent.cell - side;
            const loY = parent.y0 + band * parent.cell, hiY = parent.y1 - band * parent.cell - side;
            // centred on the focus, on an even grid line, clamped inside the parent (both bounds are even lines:
            // band is even and the parent's cell count a multiple of 4), then rounded back onto the line exactly
            const x0 = snap(Math.min(Math.max(snap(fcx - side / 2.0, parent.x0, step), loX), hiX), parent.x0, step);
            const y0 = snap(Math.min(Math.max(snap(fcy - side / 2.0, parent.y0, step), loY), hiY), parent.y0, step);
            const lv = new Level(0, 'hero', x0, y0, side, cell, m, null, 1, [], band, parent.depth - 1);
            if (!pts.every(([x, y]) => lv.contains(x, y, band * cell))) {
                warn(`the focus is too close to the edge of the ${pyFormat(parent.side, 'g')} m level for a hero window at ` +
                    `${pyFormat(cell, '.3g')} m: the hero cell stops at ${pyFormat(parent.cell, '.3g')} m`);
                break;
            }
            levels.push(lv);
            parent = lv;
        }
    }

    levels.forEach((lv, i) => {
        lv.index = i;
        lv.parent = i > 0 ? i - 1 : null;
    });
    // the coarsest level grows coarse-to-fine on its own window first
    const first = levels[0];
    const pre = [];
    let m = first.n;
    while (m % 2 === 0 && Math.floor(m / 2) >= PREPASS_MIN) {
        m = Math.floor(m / 2);
        pre.unshift(m);
    }
    first.prepass = pre;
    checkPlan(levels);
    return levels;
}
export const plan_levels = planLevels;

/** Assert the nesting rules: each child has half its parent's cell, sits on the parent's even grid lines, and
 * stays `band` parent cells inside. Throws naming the level. */
export function checkPlan(levels) {
    const assert = (c, msg) => {
        if (!c) throw Object.assign(new Error(msg), { name: 'AssertionError' });
    };
    for (const lv of levels.slice(1)) {
        const p = levels[lv.parent];
        assert(Math.abs(lv.cell * 2.0 - p.cell) <= 1e-9 * p.cell, `${lv}: cell is not half of ${p}`);
        for (const [a, b] of [[lv.x0, p.x0], [lv.y0, p.y0], [lv.x1, p.x0], [lv.y1, p.y0]]) {
            const k = (a - b) / (2.0 * p.cell);
            assert(Math.abs(k - pyRound(k)) < 1e-6, `${lv}: an edge is not on an even grid line of ${p}`);
        }
        const m = lv.band * p.cell - 1e-6 * p.cell;
        assert(lv.x0 - p.x0 >= m && lv.y0 - p.y0 >= m && p.x1 - lv.x1 >= m && p.y1 - lv.y1 >= m,
            `${lv}: closer than ${lv.band} cells to the edge of ${p}`);
        assert(Math.abs(lv.n * lv.cell - lv.side) < 1e-6 * lv.side, `${lv}: n x cell != side`);
    }
}
export const check_plan = checkPlan;

export const planDict = (levels) => levels.map((lv) => lv.toDict());
export const plan_dict = planDict;


// ------------------------------------------------------------------------------------------- level selection ---

const SPEC = /^\s*(?:(all|first|last|context|main|hero)|cell\s*(<=|>=|<|>)\s*([0-9.eE+-]+)|resolves\s*:\s*([0-9.eE+-]+))\s*$/;
export const SPEC_FORMS = ["'all'", "'first'", "'last'", "'context'", "'main'", "'hero'", "'cell>=30'", "'cell<=2'",
    "'resolves:<metres>'", 'a level index, or a list of these'];

// Python's float() of a number token the pattern let through
function pyFloat(s) {
    const t = s.trim();
    if (!/^[+-]?(\d+\.?\d*|\.\d+)([eE][+-]?\d+)?$/.test(t)) throw new ValueError(`could not convert string to float: '${s}'`);
    return Number(t);
}

/** Check a stage's `levels` value; returns it normalised (an array of strings and integers). Throws naming the
 * forms allowed. */
export function parseLevelsSpec(spec) {
    const items = Array.isArray(spec) ? spec : [spec];
    const out = [];
    for (const s of items) {
        if (typeof s === 'number' && Number.isInteger(s)) {
            out.push(s);
            continue;
        }
        if (typeof s !== 'string' || !SPEC.test(s)) throw new ValueError(`levels ${pyReprValue(s)} is not one of ${SPEC_FORMS.join(', ')}`);
        out.push(s.trim());
    }
    return out;
}
export const parse_levels_spec = parseLevelsSpec;

/** The indices of the levels a stage runs on, sorted. A 'resolves:<m>' that no level resolves picks the finest
 * level, with a warning. */
export function selectLevels(spec, levels, warn = null) {
    warn = warn ?? defaultWarn;
    const picked = new Set();
    const L = levels.length;
    for (const s of parseLevelsSpec(spec)) {
        if (typeof s === 'number') {
            if (!(-L <= s && s < L)) throw new IndexError(`level index ${s} out of range for ${L} levels`);
            picked.add(((s % L) + L) % L);
            continue;
        }
        const [, word, op, val, res] = SPEC.exec(s);
        if (word === 'all') {
            for (let i = 0; i < L; i++) picked.add(i);
        } else if (word === 'first') {
            picked.add(0);
        } else if (word === 'last') {
            picked.add(L - 1);
        } else if (word) {
            for (const lv of levels) if (lv.role === word) picked.add(lv.index);
        } else if (op) {
            const v = pyFloat(val);
            const f = { '<=': (c) => c <= v * (1 + 1e-9), '>=': (c) => c >= v * (1 - 1e-9), '<': (c) => c < v, '>': (c) => c > v }[op];
            for (const lv of levels) if (f(lv.cell)) picked.add(lv.index);
        } else {
            const need = pyFloat(res) / 8.0;
            const hit = levels.filter((lv) => lv.cell <= need * (1 + 1e-9)).map((lv) => lv.index);
            if (hit.length) {
                picked.add(hit[0]);
            } else {
                warn(`no level resolves ${pyFormat(pyFloat(res), 'g')} m (cell <= ${pyFormat(need, 'g')} m; the finest is ` +
                    `${pyFormat(levels[L - 1].cell, '.3g')} m): using the finest`);
                picked.add(L - 1);
            }
        }
    }
    return [...picked].sort((a, b) => a - b);
}
export const select_levels = selectLevels;
