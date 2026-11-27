// eidoverse/sets/town/house.js — one building of the town, whole or as a strike left it. Metres; the building's own
// space (+Z up): its front along y = 0 looking toward -y (the street), x along the street from 0 to w, its lot running
// back to y = d.
//
//   const h = new House(rng, 14.5, 10.5, 4, { shops: true, dmg: 0, low: false, annex: 4.0 });
//   h.b   the mesh builder (mb.js);  h.anchors where a dish may stand;  h.zf each floor's height
//
// WHAT IT IS: a reinforced-concrete FRAME on a grid of bays (columns at the grid's nodes, a beam under the slab on every
// grid line, a 0.2 m slab at each floor), filled in with hollow-block walls and plastered. Its facades follow a grammar
// of bays and storeys: openings reserved first and built as true recesses with their reveals, frames and sills; a wall
// has its thickness wherever its section can be seen; everything stands on something; nothing hidden is built.
// THE MODEL: every bay, storey by storey, is a ROOM under its slab, a room OPEN TO THE SKY, a storey BEING BUILT, or
// nothing. A house is designed first (a lower wing, a terrace, a stair head, a room on the roof, a storey begun and
// left), then STRUCK (dmg), and only then built: so a slab knows whether its edge was cast or torn, a wall whether its
// far side was always the street or was somebody's room, and the frame is built exactly where it shows.
// dmg: 0 whole; 1 its front blown off over two or three bays; 2 a corner brought down; 3 half of it down; 4 a shell
// through the roof; 5 scarred (a hole or two through its walls).
// A port of the Blender edition's eidoblend.sets.town.house, draw for draw (the same seed builds the same house).
import { V, M4, MB, arc } from './mb.js';
import * as K from './kit.js';
import { pyRound, pyMod } from './pyrandom.js';

const H = 3.1, SLAB = 0.20, WALL = 0.25, PART = 0.15, COL = 0.35;
const SIDES = [['S', 0, -1], ['E', 1, 0], ['N', 0, 1], ['W', -1, 0]];
export const PAINTS = ['in_white', 'in_cream', 'in_blue', 'in_green', 'in_pink', 'in_white', 'in_cream'];
export const N_BOARDS = 8;

const ck = (c) => (c ? `${c[0]},${c[1]}` : '');
const cell = (k) => k.split(',').map(Number);

// a broken edge's height at a
function ev(prof, a) {
    if (a <= prof[0][0]) return prof[0][1];
    for (let i = 0; i < prof.length - 1; i++) {
        const [a0, b0] = prof[i], [a1, b1] = prof[i + 1];
        if (a <= a1) return a1 - a0 < 1e-9 ? b0 : b0 + (b1 - b0) * (a - a0) / (a1 - a0);
    }
    return prof[prof.length - 1][1];
}

// how a block wall breaks: along its courses, in steps -> [(a, height)], a rising from 0 to L
function jag(rng, L, base, amp, lo = 0.0, hi = 1e9, q = 0.2, run = [0.2, 0.7]) {
    const f = typeof base === 'function' ? base : () => base;
    const lvl = (a) => Math.min(hi, Math.max(lo, q * pyRound((f(a) + rng.uniform(-amp, amp)) / q)));
    const pts = [[0.0, lvl(0.0)]];
    let a = 0.0;
    while (a < L - 1e-6) {
        let a2 = Math.min(L, a + rng.uniform(run[0], run[1]));
        pts.push([a2, pts[pts.length - 1][1]]);
        if (a2 < L - 0.15) {
            const b2 = lvl(a2);
            if (Math.abs(b2 - pts[pts.length - 1][1]) > 1e-6) {
                a2 = a2 + rng.uniform(0.02, 0.1);
                pts.push([a2, b2]);
            }
        }
        a = a2;
    }
    return pts;
}

// the top edge of a wall that lost its upper part: ONE break, as walls go (a bite out of its middle, a run down from
// one standing end, or a stump), stepped along the block courses
function brokenTop(rng, L, h) {
    const kind = rng.choice(['bite', 'bite', 'down_l', 'down_r', 'stump']);
    const top = h * rng.uniform(0.6, 1.0), low = h * rng.uniform(0.04, 0.35);
    const c = rng.uniform(0.3, 0.7) * L, e = rng.uniform(1.2, 2.4);
    let f;
    if (kind === 'bite') f = (a) => low + (top - low) * Math.min(1.0, Math.abs(a - c) / (0.55 * L)) ** e;
    else if (kind === 'stump') f = () => low * 1.4;
    else f = (a) => { const t = kind === 'down_l' ? a / L : 1.0 - a / L; return top + (low - top) * t ** (1.0 / e); };
    return jag(rng, L, f, 0.14, 0.0, h, 0.2, [0.2, 0.55]);
}

// a wall with a hole blown through it, or most of it gone -> (the top edge of what stands below the hole, the bottom
// edge of what hangs above it); a block wall breaks round its blocks: level along a course, stepping at a joint
function holeProf(rng, L, h, gone) {
    const q = 0.2;
    let ac, hw, zl, zh;
    if (gone) {
        ac = L / 2.0 + rng.uniform(-0.3, 0.3); hw = L * rng.uniform(0.56, 0.95);
        zl = rng.choice([0.0, 0.0, 0.0, 0.2, 0.4]); zh = h - rng.choice([0.0, 0.0, 0.2, 0.4, 0.6]);
    } else {
        ac = rng.uniform(0.3, 0.7) * L; hw = rng.uniform(0.2, 0.42) * L;
        zl = rng.choice([0.0, 0.2, 0.6, 1.0]); zh = Math.min(h, rng.uniform(0.62, 1.0) * h);
    }
    const zm = q * pyRound(rng.uniform(0.38, 0.6) * h / q);
    const skew = rng.uniform(-0.5, 0.5);
    const lo = [], hi = [];
    let a = 0.0;
    while (a < L - 1e-6) {
        let a2 = Math.min(L, a + rng.choice([0.2, 0.2, 0.4, 0.4, 0.6]));
        if (L - a2 < 0.15) a2 = L;
        const s = ((a + a2) / 2.0 - ac) / hw;
        let l_, g;
        if (Math.abs(s) >= 1.0) { l_ = zm; g = zm; }
        else {
            const k = Math.sqrt(1.0 - s * s);
            l_ = Math.min(zm, Math.max(0.0, q * pyRound((zm - (zm - zl) * k * (1.0 + skew * s) + rng.uniform(-0.22, 0.22)) / q)));
            g = Math.max(zm, Math.min(h, q * pyRound((zm + (zh - zm) * k * (1.0 - skew * s) + rng.uniform(-0.22, 0.22)) / q)));
        }
        for (const [prof, v] of [[lo, l_], [hi, g]]) {
            prof.push([a + (a > 0 ? 0.03 : 0.0), v]);
            prof.push([a2, v]);
        }
        a = a2;
    }
    return [lo, hi];
}

// a bay's slab in plan, counter-clockwise from its south-west corner: straight where it was cast to an edge or runs on
// into the next bay, bitten in where it was torn -> (its points, what the edge leaving each point is)
function raggedRect(rng, x0, y0, x1, y1, modes, depth) {
    const cx = (x0 + x1) / 2.0, cy = (y0 + y1) / 2.0;
    const C = { S: [[x0, y0], [x1, y0]], E: [[x1, y0], [x1, y1]], N: [[x1, y1], [x0, y1]], W: [[x0, y1], [x0, y0]] };
    const order = 'SENW';
    const pts = [], kinds = [];
    for (let q_ = 0; q_ < 4; q_++) {
        const s = order[q_];
        const [[ax, ay], [bx, by]] = C[s];
        const torn = modes[s] === 'torn';
        if (torn && modes[order[pyMod(q_ - 1, 4)]] === 'torn') {     // a corner with both its sides torn goes too
            const f = Math.min(0.45, rng.uniform(depth[0], depth[1]) / Math.hypot(cx - ax, cy - ay));
            pts.push([ax + (cx - ax) * f, ay + (cy - ay) * f]);
        } else pts.push([ax, ay]);
        kinds.push(modes[s]);
        if (torn) {
            const n = Math.max(3, Math.trunc(Math.hypot(bx - ax, by - ay) / 0.45));
            let d = rng.uniform(depth[0], depth[1]);
            for (let k = 1; k < n; k++) {
                const t = (k + rng.uniform(-0.3, 0.3)) / n;
                d = Math.min(depth[1], Math.max(depth[0], d + rng.uniform(-0.35, 0.35)));
                const px = ax + (bx - ax) * t, py = ay + (by - ay) * t;
                const f = Math.min(0.8, d / Math.max(0.3, Math.hypot(cx - px, cy - py)));
                pts.push([px + (cx - px) * f, py + (cy - py) * f]);
                kinds.push('torn');
            }
        }
    }
    return [pts, kinds];
}

// directed edges [((x, y), (x, y))] joined end to end -> [(points, closed)], straight runs merged
export function chains(edges) {
    const key = (p) => `${p[0]},${p[1]}`;
    const nxt = new Map();
    for (const [a, c] of edges) {
        if (!nxt.has(key(a))) nxt.set(key(a), { p: a, to: [] });
        nxt.get(key(a)).to.push(c);
    }
    const ends = new Set(edges.map(([, c]) => key(c)));
    const out = [];
    const follow = (a) => {
        const pts = [a];
        let e = nxt.get(key(a));
        while (e && e.to.length) {
            a = e.to.pop();
            pts.push(a);
            if (key(a) === key(pts[0])) return [pts, true];
            e = nxt.get(key(a));
        }
        return [pts, false];
    };
    for (const s of edges.map(([a]) => a).filter((a) => !ends.has(key(a)))) {
        while (nxt.get(key(s))?.to.length) out.push(follow(s));
    }
    for (const [, e] of nxt) while (e.to.length) out.push(follow(e.p));
    const res = [];
    for (const [pts, closed] of out) {
        const keep = [];
        const n = pts.length - (closed ? 1 : 0);
        for (let k = 0; k < n; k++) {
            if (closed || (0 < k && k < n - 1)) {
                const p = pts[k], a = pts[pyMod(k - 1, n)], c = pts[pyMod(k + 1, n)];
                if (Math.abs((p[0] - a[0]) * (c[1] - p[1]) - (p[1] - a[1]) * (c[0] - p[0])) < 1e-9) continue;   // on a straight run
            }
            keep.push(pts[k]);
        }
        if (keep.length >= 2) res.push([keep, closed]);
    }
    return res;
}

export class House {
    // w x d: its main part on the street; annex: how deep a range of low rooms and small courts runs on behind it.
    // signs: the town's prepared signs (or none: painted boards)
    constructor(rng, w, d, floors, { shops = false, dmg = 0, low = false, annex = 0.0, signs = [] } = {}) {
        Object.assign(this, { rng, w, d, F: floors, shops, dmg, low, annex, signs });
        this.b = new MB();
        this.anchors = [];                                           // where a dish may stand: (x, y, z)
        this._par = [];
        this._grid();
        this._massing();
        this._strike();
        this._finishes();
        this._plan();
        this._slabs();
        this._walls();
        this._frame();
        this._balconies();
        this._parapets();
        this._roofThings();
        this._insides();
        this._fallen();
    }

    // ------------------------------------------------------------------------------------------ the grid
    _grid() {
        const { rng, w, d, F } = this;
        const nb = Math.max(2, pyRound(w / 3.7)), ndm = Math.max(2, pyRound(d / 4.2));
        const nd = ndm + (this.annex > 0 ? 1 : 0);
        Object.assign(this, { nb, nd, ndm });
        this.cells = [];
        for (let i = 0; i < nb; i++) for (let j = 0; j < nd; j++) this.cells.push([i, j]);
        this.si = rng.randrange(nb); this.sj = ndm - 1;              // the stair's bay: at the back of the main part
        let wts = [];
        for (let i = 0; i < nb; i++) wts.push(rng.uniform(0.86, 1.14));
        if (nb >= 3) wts[this.si] = 0.74;
        const sum = (a) => a.reduce((s, x) => s + x, 0);
        const xs = [0.0];
        for (const q of wts) xs.push(xs[xs.length - 1] + w * q / sum(wts));
        xs[xs.length - 1] = w;
        wts = [];
        for (let j = 0; j < ndm; j++) wts.push(rng.uniform(0.9, 1.1));
        const ys = [0.0];
        for (const q of wts) ys.push(ys[ys.length - 1] + d * q / sum(wts));
        ys[ys.length - 1] = d;
        if (this.annex > 0) ys.push(d + this.annex);
        this.d = ys[ys.length - 1];                                  // (from here on: the whole depth it stands on)
        this.xs = xs; this.ys = ys;
        this.plinth = this.shops ? 0.15 : rng.choice([0.3, 0.45, 0.6]);
        const zf = [this.plinth];
        for (let f = 0; f < F; f++) zf.push(zf[zf.length - 1] + (f === 0 ? (this.shops ? 3.75 : H) : H));
        zf.push(zf[zf.length - 1] + 2.55);                           // the roof's own storey: a stair head, a room up there
        this.zf = zf;
        this.ov = (this.shops && F >= 2) ? rng.choice([0.0, 0.0, 0.6, 0.8]) : 0.0;
        this.band = !this.low ? rng.choice([0.08, 0.1, 0.12]) : rng.choice([0.1, 0.3, 0.45]);
        this.slots = [];
        for (let j = 0; j < nd + 1; j++) for (let i = 0; i < nb; i++) this.slots.push(['H', i, j]);
        for (let i = 0; i < nb + 1; i++) for (let j = 0; j < nd; j++) this.slots.push(['V', i, j]);
    }

    // a grid line across the building at storey f: the front line steps out above the ground floor
    Y(j, f) { return j > 0 ? this.ys[j] : (f >= 1 ? -this.ov : 0.0); }
    // the same for the slab at level L (it carries the storey above it)
    Yl(j, L) { return j > 0 ? this.ys[j] : (L >= 1 ? -this.ov : 0.0); }

    // the bays on a wall line's two sides: (south or west, north or east)
    cellsOf(kind, i, j) {
        if (kind === 'H') return [j >= 1 ? [i, j - 1] : null, j < this.nd ? [i, j] : null];
        return [i >= 1 ? [i - 1, j] : null, i < this.nb ? [i, j] : null];
    }

    slotsOf(c) {
        const [i, j] = c;
        return [['S', ['H', i, j]], ['N', ['H', i, j + 1]], ['W', ['V', i, j]], ['E', ['V', i + 1, j]]];
    }

    // ------------------------------------------------------------------------------------------ the design
    _massing() {
        const { rng, F, nb } = this;
        const nd = this.ndm;
        const n0 = new Map(this.cells.map((c) => [ck(c), F]));
        const cap0 = new Map();
        const r = rng.random();
        if (F >= 2 && nd >= 3 && r < 0.26) {                          // a lower range behind: a terrace at the back
            const drop = F >= 3 ? rng.choice([1, 1, 2]) : 1;
            for (let i = 0; i < nb; i++) n0.set(ck([i, nd - 1]), F - drop);
        } else if (F >= 2 && nb >= 3 && r < 0.46) {                  // one end lower
            const e = rng.choice([0, nb - 1]);
            for (let j = 0; j < nd; j++) n0.set(ck([e, j]), F - 1);
        } else if (F >= 2 && r < 0.62) {                             // a back corner stepped down
            const v = Math.max(1, F - rng.choice([1, 1, 2]));       // (Python evaluates the value before the key)
            n0.set(ck([rng.choice([0, nb - 1]), nd - 1]), v);
        } else if (nb >= 3 && nd >= 3 && r < 0.74) {                 // a light court let into the back
            n0.set(ck([rng.randrange(1, nb - 1), nd - 1]), 0);
        }
        if (this.annex > 0) {                                        // behind it: low rooms, and small courts between
            for (let i = 0; i < nb; i++) n0.set(ck([i, nd]), rng.random() < 0.62 ? 1 : 0);
        }
        const tops = this.cells.filter((c) => n0.get(ck(c)) === F);
        let mains = tops.filter((c) => c[1] < nd);
        if (!mains.length) mains = tops;
        const back = Math.max(...mains.map((c) => c[1]));
        const st = mains.filter((c) => c[1] === back);
        if (!st.some((c) => c[0] === this.si && c[1] === this.sj)) [this.si, this.sj] = rng.choice(st);
        n0.set(ck([this.si, this.sj]), F + 1);                       // the stair's head
        this.stair = [this.si, this.sj];
        let free = tops.filter((c) => !(c[0] === this.si && c[1] === this.sj));
        if (free.length && rng.random() < (this.low ? 0.5 : 0.28)) { // a room built on the roof
            let near = free.filter((c) => Math.abs(c[0] - this.si) + Math.abs(c[1] - this.sj) === 1);
            if (!near.length) near = free;
            n0.set(ck(rng.choice(near)), F + 1);
        }
        free = free.filter((c) => n0.get(ck(c)) === F);
        // a storey begun and left: block half laid, or (seldom) its frame standing; over three bays at most
        if (free.length && rng.random() < 0.14) {
            const c0 = rng.choice(free);
            const kind = rng.choice(['frame', 'build', 'build', 'build']);
            let got = 0;
            for (const c of free) {
                if (got < 3 && Math.abs(c[0] - c0[0]) <= 1 && Math.abs(c[1] - c0[1]) <= (rng.random() < 0.5 ? 1 : 0) && rng.random() < 0.8) {
                    cap0.set(ck(c), kind);
                    got += 1;
                }
            }
        }
        this.n0 = n0; this.cap0 = cap0;
    }

    // what stands in bay c at storey f: 'R' a room under its slab; 'U' a room open to the sky; 'C' a storey being
    // built; 'N' nothing
    st(c, f) {
        if (!c || !this.n1.has(ck(c))) return 'N';
        const n = this.n1.get(ck(c));
        if (f < n) return 'R';
        if (f === n) {
            const cp = this.cap1.get(ck(c));
            if (cp === 'roofless') return 'U';
            if (cp === 'frame' || cp === 'build') return 'C';
        }
        return 'N';
    }

    was(c, f) { return !!c && this.n0.has(ck(c)) && f < this.n0.get(ck(c)); }
    paint(c, f) { return PAINTS[(c[0] * 3 + c[1] * 5 + f * 7 + this.seed) % PAINTS.length]; }
    isOpened(c, f) { return this.opened.has(`${ck(c)},${f}`); }

    // ------------------------------------------------------------------------------------------ the strike
    _strike() {
        const { rng, F, nb, nd, dmg } = this;
        this.seed = rng.randrange(1000);
        const n1 = new Map(this.n0), cap1 = new Map(this.cap0), wst = new Map(), bite = new Set();
        const W = (f, kind, i, j) => `${f},${kind},${i},${j}`;
        this.blown = null;
        if (dmg === 1) {                                             // its front blown off over two or three bays
            const k0 = nb > 2 ? rng.randrange(0, nb - 1) : 0;
            const k1 = Math.min(nb - 1, k0 + rng.randrange(1, 3));
            const f0 = rng.randrange(0, Math.max(1, F - 1));
            this.blown = [k0, k1, f0];
            for (let f = f0; f < F; f++) {
                for (let k = k0; k <= k1; k++) {
                    if (this.n0.get(ck([k, 0])) > f) {
                        wst.set(W(f, 'H', k, 0), (k0 < k && k < k1) || rng.random() < 0.65 ? 'gone' : 'hole');
                        bite.add(`${f + 1},${k},0,S`);
                        if (f >= 1) bite.add(`${f},${k},0,S`);
                    }
                }
                if (k0 === 0 && rng.random() < 0.5) wst.set(W(f, 'V', 0, 0), rng.choice(['hole', 'gone']));
                if (k1 === nb - 1 && rng.random() < 0.5) wst.set(W(f, 'V', nb, 0), rng.choice(['hole', 'gone']));
            }
            if (rng.random() < 0.5) {                                // and the roof over its top rooms came down
                for (let k = k0; k <= k1; k++) {
                    if (n1.get(ck([k, 0])) === F && !cap1.has(ck([k, 0]))) { n1.set(ck([k, 0]), F - 1); cap1.set(ck([k, 0]), 'roofless'); }
                }
            }
        } else if (dmg === 2 || dmg === 3) {                         // a corner brought down; or half of it
            const ci = rng.choice([0, nb - 1]), cj = rng.choice([0, nd - 1]);
            const reach = rng.uniform(1.4, 2.2) * (dmg === 3 ? 1.6 : 1.0);
            for (const c of this.cells) {
                const dist = Math.hypot(c[0] - ci, c[1] - cj);
                if (dist < reach && this.n0.get(ck(c)) > 0) {
                    const keep = Math.max(0, Math.min(this.n0.get(ck(c)), Math.trunc(dist / reach * (F + 0.5) + rng.uniform(-0.6, 0.3))));
                    if (keep < this.n0.get(ck(c))) {
                        n1.set(ck(c), keep);
                        cap1.delete(ck(c));
                        if (rng.random() < (dist < reach * 0.45 ? 0.3 : 0.6)) cap1.set(ck(c), 'roofless');
                    }
                }
            }
        } else if (dmg === 4) {                                      // a shell through the roof
            const top = this.cells.filter((c) => this.n0.get(ck(c)) === F && !cap1.has(ck(c)) && F >= 1);
            if (top.length) {
                const c0 = rng.choice(top);
                for (const c of top) {
                    if ((c[0] === c0[0] && c[1] === c0[1]) || (Math.abs(c[0] - c0[0]) + Math.abs(c[1] - c0[1]) === 1 && rng.random() < 0.45)) {
                        n1.set(ck(c), F - 1); cap1.set(ck(c), 'roofless');
                    }
                }
            }
        } else if (dmg === 5) {                                      // scarred: a hole or two through its walls
            const nh = rng.randrange(1, 4);
            for (let q = 0; q < nh; q++) {
                const f = rng.randrange(F);
                if (rng.random() < 0.7) wst.set(W(f, 'H', rng.randrange(nb), 0), 'hole');
                else { const i_ = rng.choice([0, nb]); wst.set(W(f, 'V', i_, rng.randrange(nd)), 'hole'); }
            }
        }
        this.n1 = n1; this.cap1 = cap1;
        if (dmg === 2 || dmg === 3 || dmg === 4) {                   // what stood next to the fall has lost walls too
            for (let f = 0; f < F + 1; f++) {
                for (const s of this.slots) {
                    const [A, B] = this.cellsOf(...s);
                    for (const [X_, O_] of [[A, B], [B, A]]) {
                        if (this.st(X_, f) === 'R' && this.was(O_, f) && this.st(O_, f) !== 'R') {
                            const r = rng.random();
                            if (r < 0.5) wst.set(W(f, ...s), r < 0.3 ? 'hole' : 'gone');
                        } else if (this.st(X_, f) === 'R' && O_ === null && this.cells.some((c) => this.n1.get(ck(c)) < this.n0.get(ck(c)) && Math.abs(c[0] - X_[0]) + Math.abs(c[1] - X_[1]) <= 1)) {
                            if (rng.random() < 0.3) wst.set(W(f, ...s), 'hole');
                        }
                    }
                }
            }
        }
        this.wst = wst; this.bite = bite;
        this.opened = new Set();                                     // rooms a wall has gone from: their insides are built
        for (const c of this.cells) {
            for (let f = 0; f < n1.get(ck(c)); f++) {
                if (this.slotsOf(c).some(([, s]) => ['hole', 'gone'].includes(wst.get(W(f, ...s))))) this.opened.add(`${ck(c)},${f}`);
            }
        }
    }

    _finishes() {
        const rng = this.rng;
        const hit = [1, 2, 3, 4].includes(this.dmg);
        this.PL = hit ? 'plaster_dmg' : 'plaster';
        const brick = this.low && rng.random() < 0.3;
        if (brick) this.PL = 'brick';
        const side = rng.random();
        this.PLs = side < 0.5 ? this.PL : (side < 0.85 ? 'block' : 'brick');      // a wall on the lot's line is often bare
        this.PLb = rng.random() < 0.55 ? this.PL : this.PLs;
        this.PL2 = (!hit && !brick && rng.random() < 0.3) ? 'plaster_b' : this.PL;  // a second colour: the ground floor
        this.CO = 'concrete';
        this.band_m = rng.random() < 0.6 ? this.PL : 'concrete';
        this.hp = rng.choice([0.5, 0.7, 0.9, 0.9, 1.05]);            // the roof's parapet
        this.par_m = rng.choice([this.PL, this.PL, this.PL, 'block', 'claustra']);
        this.frame_m = rng.choice(['frame_alu', 'frame_alu', 'frame_white', 'frame_wood']);
        this.door_m = rng.choice(['door_green', 'door_blue', 'door_brown', 'door_grey', 'door_rust']);
        this.hoods = rng.random() < 0.35;
        this.canopy = this.shops && rng.random() < 0.4;              // one concrete canopy the length of the shops
        this.canopy_on = this.canopy && this.blown === null && ![2, 3].includes(this.dmg);
        this.blinds = rng.random() < 0.5;                            // roller blinds in the windows, as there
    }

    // ------------------------------------------------------------------------------------------ the facades' plan
    _plan() {
        const { rng, F, nb, nd } = this;
        const fac = new Map();
        const ent = nb > 2 ? this.si : rng.randrange(nb);
        this.ent = ent;
        const up = [], wcol = [];
        for (let i = 0; i < nb; i++) {
            const r = rng.random();
            up.push((i === ent && nb > 2) ? 'win' : r < 0.40 ? 'balc' : r < 0.54 ? 'win2' : r < 0.59 ? 'blank' : 'win');
            wcol.push(rng.choice([1.0, 1.2, 1.2, 1.4, 1.6]));
        }
        if (F >= 2 && !up.includes('balc') && rng.random() < 0.8) {
            let c = [...Array(nb).keys()].filter((i) => i !== ent);
            if (!c.length) c = [0];
            up[rng.choice(c)] = 'balc';
        }
        this.balc_kind = rng.choice(['solid', 'solid', 'solid', 'rail', 'claustra']);
        this.balc_round = rng.random() < 0.3;
        for (let f = 0; f < F; f++) {
            for (let i = 0; i < nb; i++) {
                let spec;
                if (f === 0 && this.shops && i !== ent) {
                    const shut = rng.randrange(6);
                    const open = rng.choice([0.0, 0.0, 0.0, 0.0, 0.0, 0.35, 0.8]);
                    const awn = (!this.canopy && rng.random() < 0.5) ? rng.randrange(6) : null;
                    const sign = rng.random() < 0.85;
                    spec = { type: 'shop', shut, open, awn, sign };
                } else if (f === 0 && i === ent) spec = { type: 'door' };
                else if (f === 0) spec = { type: 'win', w: wcol[i], sill: 1.1 };
                else spec = { type: up[i], w: wcol[i], sill: 0.95 };
                spec.shutter = this.blinds ? rng.choice([0.0, 0.0, 0.0, 0.3, 0.6, 1.0]) : 0.0;
                spec.ac = rng.random() < 0.12;
                fac.set(`${f},H,${i},0`, spec);
            }
            for (let i = 0; i < nb; i++) {                            // the back: fewer and smaller
                if (rng.random() < 0.55) {
                    const w = rng.choice([0.8, 1.0, 1.2]);
                    fac.set(`${f},H,${i},${nd}`, { type: 'win', w, sill: 1.0, shutter: 0.0, ac: rng.random() < 0.1 });
                } else fac.set(`${f},H,${i},${nd}`, { type: 'blank' });
            }
            for (let j = 0; j < nd; j++) {                            // the sides: on the lot's line, mostly blind
                for (const i_ of [0, nb]) {
                    fac.set(`${f},V,${i_},${j}`, rng.random() < 0.2 ? { type: 'win', w: 0.8, sill: 1.2, shutter: 0.0, ac: false } : { type: 'blank' });
                }
            }
        }
        this.fac = fac;
        this.balc = new Set();                                       // (storey, bay) of every balcony's door that stands
        this.roof_door = new Set();
    }

    // ------------------------------------------------------------------------------------------ slabs
    hasSlab(c, L) {
        if (!c || !this.n1.has(ck(c))) return false;
        if (L === 0) return this.n0.get(ck(c)) >= 1 || this.cap0.has(ck(c));
        return this.n1.get(ck(c)) >= L;
    }

    hadSlab(c, L) {
        if (!c || !this.n0.has(ck(c))) return false;
        if (L === 0) return this.n0.get(ck(c)) >= 1 || this.cap0.has(ck(c));
        return this.n0.get(ck(c)) >= L;
    }

    _slabs() {
        const { b, rng, xs, zf, F } = this;
        for (let L = 0; L < F + 2; L++) {
            for (const c of this.cells) {
                if (!this.hasSlab(c, L)) continue;
                const [i, j] = c;
                const x0 = xs[i], x1 = xs[i + 1], yA = this.Yl(j, L), yB = this.Yl(j + 1, L);
                const zt = zf[L];
                const zb = L ? zt - SLAB : 0.0;                      // (the ground floor's slab is the plinth, to the ground)
                const modes = {};
                for (const [s, di, dj] of SIDES) {
                    const nbc = [i + di, j + dj];
                    if (this.hasSlab(nbc, L)) modes[s] = 'shared';
                    else if ((L >= 1 && this.hadSlab(nbc, L)) || this.bite.has(`${L},${i},${j},${s}`)) modes[s] = 'torn';
                    else modes[s] = 'clean';
                }
                const top_vis = (L === this.n1.get(ck(c))) || this.isOpened(c, L);
                const bot_vis = L >= 1 && (this.isOpened(c, L - 1) || (j === 0 && L === 1 && this.ov > 0));
                const torn = [...'SENW'].filter((s) => modes[s] === 'torn');
                const band = L === 0 ? 0.0 : this.band;
                if (!top_vis && !bot_vis && !torn.length) {          // only its edge shows: a band proud of the wall
                    for (const s of 'SENW') {
                        if (modes[s] !== 'clean') continue;
                        if (band <= 0.0) {
                            const [[ax, ay], [bx, by]] = { S: [[x0, yA], [x1, yA]], E: [[x1, yA], [x1, yB]], N: [[x1, yB], [x0, yB]], W: [[x0, yB], [x0, yA]] }[s];
                            b.quad([ax, ay, zb], [bx, by, zb], [bx, by, zt], [ax, ay, zt], this.CO);
                        } else if (s === 'S' || s === 'N') {
                            const ew = modes.W === 'clean' ? band : 0.0;
                            const ee = modes.E === 'clean' ? band : 0.0;
                            const [lo, hi] = s === 'S' ? [[x0 - ew, yA - band, zb], [x1 + ee, yA, zt]] : [[x0 - ew, yB, zb], [x1 + ee, yB + band, zt]];
                            b.box(lo, hi, this.band_m, { skip: (s === 'S' ? 'y+' : 'y-') + (modes.W === 'shared' ? 'x-' : '') + (modes.E === 'shared' ? 'x+' : '') });
                        } else {
                            const [lo, hi] = s === 'E' ? [[x1, yA, zb], [x1 + band, yB, zt]] : [[x0 - band, yA, zb], [x0, yB, zt]];
                            b.box(lo, hi, this.band_m, { skip: (s === 'E' ? 'x-' : 'x+') + 'y-y+' });
                        }
                    }
                    continue;
                }
                const ex = Object.fromEntries(Object.entries(modes).map(([s, v]) => [s, v === 'clean' ? band : 0.0]));
                const collapse = SIDES.some(([, di, dj]) => L >= 1 && this.hadSlab([i + di, j + dj], L) && !this.hasSlab([i + di, j + dj], L));
                const [pts, kinds] = raggedRect(rng, x0 - ex.W, yA - ex.S, x1 + ex.E, yB + ex.N, modes, collapse ? [0.2, 1.3] : [0.12, 0.85]);
                let tm;
                if (L === this.n0.get(ck(c)) && this.n1.get(ck(c)) === this.n0.get(ck(c)) && !this.cap1.has(ck(c))) tm = 'roof';
                else if (this.cap1.has(ck(c)) && ['frame', 'build'].includes(this.cap1.get(ck(c))) && L === this.n1.get(ck(c))) tm = this.CO;
                else if (L === this.n0.get(ck(c))) tm = 'roof_dmg';
                else tm = 'floor';                                   // a floor nobody was meant to see from above
                b.poly(pts.map(([x, y]) => [x, y, zt]), tm);
                if (L >= 1) b.poly([...pts].reverse().map(([x, y]) => [x, y, zb]), 'ceiling');
                const n = pts.length;
                for (let k = 0; k < n; k++) {
                    if (kinds[k] === 'shared') continue;
                    const [ax, ay] = pts[k], [bx, by] = pts[(k + 1) % n];
                    b.quad([ax, ay, zb], [bx, by, zb], [bx, by, zt], [ax, ay, zt], kinds[k] === 'torn' ? 'concrete_broken' : (L ? this.band_m : this.CO));
                    if (kinds[k] === 'torn' && L >= 1 && rng.random() < 0.55) {
                        // the ceiling's plaster hangs from the broken edge in scallops: one face, two centimetres
                        const d1 = rng.uniform(0.05, 0.42), d2 = rng.uniform(0.05, 0.42);
                        b.poly([[ax, ay, zb], [bx, by, zb], [bx, by, zb - d2 * 0.4], [(ax + bx) / 2.0, (ay + by) / 2.0, zb - Math.max(d1, d2)], [ax, ay, zb - d1 * 0.3]], 'ceiling');
                    }
                }
                if (L >= 1) for (const s of torn) this._hanging(c, L, s, [x0, yA, x1, yB], tm, collapse);   // what is left of it hangs by its steel
            }
        }
    }

    _hanging(c, L, s, rect, tm, big) {
        const { b, rng } = this;
        if (rng.random() > (big ? 0.8 : 0.6)) return;
        const [x0, y0, x1, y1] = rect;
        const [[ax, ay], [bx, by], o] = { S: [[x0, y0], [x1, y0], [0.0, -1.0]], E: [[x1, y0], [x1, y1], [1.0, 0.0]], N: [[x1, y1], [x0, y1], [0.0, 1.0]], W: [[x0, y1], [x0, y0], [-1.0, 0.0]] }[s];
        const side = Math.hypot(bx - ax, by - ay);
        const drop = this.zf[L] - this.zf[L - 1];
        const reps = (big && rng.random() < 0.5) ? 2 : 1;
        for (let r_ = 0; r_ < reps; r_++) {
            const wp = rng.uniform(0.9, Math.max(1.0, Math.min(2.8, side * 0.8)));
            const lp = rng.uniform(0.9, Math.max(1.0, Math.min(2.7, drop - 0.45)));
            const t = rng.uniform(0.25, 0.75);
            const pull = rng.uniform(0.25, 0.6);
            const hx = ax + (bx - ax) * t - o[0] * pull, hy = ay + (by - ay) * t - o[1] * pull;
            const ov_ = [o[0], o[1], 0.0];
            const xv = V.cross(ov_, [0.0, 0.0, 1.0]);
            const M0 = M4.rows([[xv[0], ov_[0], 0.0, hx], [xv[1], ov_[1], 0.0, hy], [0.0, 0.0, 1.0, this.zf[L] - 0.02], [0.0, 0.0, 0.0, 1.0]]);
            const rx = -rng.uniform(50.0, 86.0) * Math.PI / 180;
            const M = M4.chain(M0, M4.R(rx, 'X'), M4.R(rng.uniform(-0.12, 0.12), 'Z'));
            const out = K.ragged(rng, wp, lp, 7, 0.3).map(([x, y]) => [x, y + lp / 2.0]);
            b.plate(out, M, SLAB * 0.9, tm, 'concrete_broken', 'ceiling');
            const nq = rng.randrange(2, 5);
            for (let q = 0; q < nq; q++) {                            // its steel: out of the slab's edge and down
                const e = (q / 3.0 - 0.5) * wp * 0.8;
                const p0 = M4.apply(M0, [e, -0.15, -0.08]);
                const u1 = rng.uniform(0.05, 0.3), u2 = rng.uniform(0.3, 0.7), u3 = rng.uniform(0.5, 1.2);
                b.path([p0, V.sub(V.add(p0, V.mul(ov_, 0.35)), [0, 0, u1]), V.sub(V.add(p0, V.mul(ov_, u2)), [0, 0, u3])], 0.011, 'rebar', { n: 3 });
            }
        }
    }

    // ------------------------------------------------------------------------------------------ walls
    // one wall panel between two columns. P0: where its OUTER face starts in plan; u: along it; n: out of it; it is t
    // thick, inward. mo, mi: its outer and inner faces (mi null: nobody sees its inside, an opening is a recess with
    // something at its back; mi given: its room stands open and an opening goes through). ops: [(a0, a1, b0, b1,
    // depth, kind)] reserved first. prof: (lo, hi) for a wall that was hit: what stands is below lo and above hi
    wall(P0, u, n, L, z0, h, t, mo, mi = null, { ops = [], prof = null, mc = 'block', spec = null, broken = false, col_m = null } = {}) {
        const b = this.b;
        const [ux, uy, nx, ny] = [u[0], u[1], n[0], n[1]];
        const P = (a, bb, dp = 0.0) => [P0[0] + ux * a - nx * dp, P0[1] + uy * a - ny * dp, z0 + bb];
        if (prof === null) {
            const cw = COL / 2.0 + 0.03;                             // where the wall is left bare, the frame shows in it
            const xs_ = [...new Set([0.0, L, ...ops.flatMap((o) => [o[0], o[1]]), ...(col_m ? [cw, L - cw] : [])])].sort((a, c) => a - c);
            const zs_ = [...new Set([0.0, h, ...ops.flatMap((o) => [o[2], o[3]])])].sort((a, c) => a - c);
            for (let i = 0; i < xs_.length - 1; i++) {
                for (let j = 0; j < zs_.length - 1; j++) {
                    const a0 = xs_[i], a1 = xs_[i + 1], b0 = zs_[j], b1 = zs_[j + 1];
                    if (a1 - a0 < 1e-6 || b1 - b0 < 1e-6) continue;
                    if (ops.some((o) => o[0] <= a0 + 1e-6 && a1 <= o[1] + 1e-6 && o[2] <= b0 + 1e-6 && b1 <= o[3] + 1e-6)) continue;
                    if (mo) b.quad(P(a0, b0), P(a1, b0), P(a1, b1), P(a0, b1), (col_m && (a1 <= cw + 1e-6 || a0 >= L - cw - 1e-6)) ? col_m : mo);
                    if (mi) b.quad(P(a1, b0, t), P(a0, b0, t), P(a0, b1, t), P(a1, b1, t), mi);
                }
            }
            for (const o of ops) {
                const [a0, a1, b0, b1, dp] = o;
                const rv = mi ? t : dp;
                const rm = mo || mi;
                b.quad(P(a0, b0), P(a1, b0), P(a1, b0, rv), P(a0, b0, rv), rm);
                b.quad(P(a0, b1, rv), P(a1, b1, rv), P(a1, b1), P(a0, b1), rm);
                b.quad(P(a0, b0), P(a0, b0, rv), P(a0, b1, rv), P(a0, b1), rm);
                b.quad(P(a1, b0, rv), P(a1, b0), P(a1, b1), P(a1, b1, rv), rm);
                this._fill(P, o, spec || {}, !!mi, broken);
            }
            return P;
        }
        const [lo, hi] = prof;
        mi = mi || mo;
        const A = [...new Set([...lo.map(([a]) => a), ...(hi ? hi.map(([a]) => a) : [])])].sort((a, c) => a - c);
        for (let k = 0; k < A.length - 1; k++) {
            const a0 = A[k], a1 = A[k + 1];
            if (a1 - a0 < 1e-6) continue;
            let l0 = ev(lo, a0), l1 = ev(lo, a1);
            let [g0, g1] = hi ? [ev(hi, a0), ev(hi, a1)] : [h, h];
            const gap = (g0 - l0 > 1e-3) || (g1 - l1 > 1e-3);       // is there a hole over this stretch at all
            if (!gap && hi) { l0 = l1 = g0 = g1 = h * 0.5; }
            if (l0 > 1e-3 || l1 > 1e-3) {
                if (mo) b.quad(P(a0, 0.0), P(a1, 0.0), P(a1, l1), P(a0, l0), mo);
                b.quad(P(a1, 0.0, t), P(a0, 0.0, t), P(a0, l0, t), P(a1, l1, t), mi);
                if (gap || !hi) b.quad(P(a0, l0), P(a1, l1), P(a1, l1, t), P(a0, l0, t), mc);
            }
            if (hi && (g0 < h - 1e-3 || g1 < h - 1e-3)) {
                if (mo) b.quad(P(a0, g0), P(a1, g1), P(a1, h), P(a0, h), mo);
                b.quad(P(a1, g1, t), P(a0, g0, t), P(a0, h, t), P(a1, h, t), mi);
                if (gap) b.quad(P(a0, g0, t), P(a1, g1, t), P(a1, g1), P(a0, g0), mc);
            }
        }
        for (const [a_, sgn] of [[0.0, -1], [L, 1]]) {               // its two ends, where it broke from the column
            const l_ = ev(lo, a_);
            if (l_ > 1e-3 && !hi) {
                if (sgn < 0) b.quad(P(a_, 0.0, t), P(a_, 0.0), P(a_, l_), P(a_, l_, t), mc);
                else b.quad(P(a_, 0.0), P(a_, 0.0, t), P(a_, l_, t), P(a_, l_), mc);
            }
        }
        return P;
    }

    // a box in a wall's own measures: along it a0..a1, up it b0..b1, from depth d0 to d1 (negative: proud of it)
    wbox(P, a0, a1, b0, b1, d0, d1, m, skip = '', top = null) {
        const p = [P(a0, b0, d0), P(a1, b0, d0), P(a1, b0, d1), P(a0, b0, d1), P(a0, b1, d0), P(a1, b1, d0), P(a1, b1, d1), P(a0, b1, d1)];
        this.b.hexa(p, m, skip, top);
    }

    // what stands in an opening: a window's frame and panes, a door, a shutter; or, where it was hit, a dark hole
    _fill(P, o, spec, through, broken) {
        const { b, rng } = this;
        const [a0, a1, b0, b1, dp, kind] = o;
        const fm = this.frame_m;
        if (kind === 'none' || kind === 'dark') {                    // a doorway in a partition: through, or onto a dark room
            if (!through) b.quad(P(a0, b0, dp), P(a1, b0, dp), P(a1, b1, dp), P(a0, b1, dp), 'void');
            return;
        }
        if (kind === 'shop') {
            const op = !broken ? (spec.open ?? 0.0) : rng.choice([0.0, 1.0, 1.0]);
            const zc = b0 + (b1 - b0) * op;                          // the shutter's foot
            const sm = `shutter:${spec.shut ?? 0}`;
            if (op < 0.98) {
                b.quad(P(a0, zc, dp), P(a1, zc, dp), P(a1, b1, dp), P(a0, b1, dp), sm);
                this.wbox(P, a0, a1, zc, zc + 0.06, dp - 0.025, dp, 'steel_dark', 'y+');
            }
            if (op > 0.02 && !through) {                             // the shop behind it, dark
                b.quad(P(a0, b0, dp + 0.9), P(a1, b0, dp + 0.9), P(a1, zc, dp + 0.9), P(a0, zc, dp + 0.9), 'void');
                b.quad(P(a0, b0, dp), P(a1, b0, dp), P(a1, b0, dp + 0.9), P(a0, b0, dp + 0.9), 'floor');
                b.quad(P(a0, b0, dp), P(a0, b0, dp + 0.9), P(a0, zc, dp + 0.9), P(a0, zc, dp), 'in_white');
                b.quad(P(a1, b0, dp + 0.9), P(a1, b0, dp), P(a1, zc, dp), P(a1, zc, dp + 0.9), 'in_white');
            }
            return;
        }
        if (through && (broken || kind !== 'door')) {
            if (rng.random() < 0.4 && (kind === 'win' || kind === 'balc')) {     // a frame still in it, the glass gone
                for (const bar of [[a0, a0 + 0.05, b0, b1], [a1 - 0.05, a1, b0, b1], [a0 + 0.05, a1 - 0.05, b1 - 0.05, b1]])
                    this.wbox(P, bar[0], bar[1], bar[2], bar[3], dp, dp + 0.04, fm);
            }
            return;
        }
        if (kind === 'door') {
            const dm = spec.m || this.door_m;
            const fan = (b1 - b0) > 2.2 ? b1 - 0.38 : b1;
            b.quad(P(a0 + 0.05, b0, dp), P(a1 - 0.05, b0, dp), P(a1 - 0.05, fan, dp), P(a0 + 0.05, fan, dp), dm);
            for (const bar of [[a0, a0 + 0.05, b0, b1], [a1 - 0.05, a1, b0, b1], [a0 + 0.05, a1 - 0.05, b1 - 0.05, b1], [a0 + 0.05, a1 - 0.05, fan - 0.03, fan + 0.03]])
                this.wbox(P, bar[0], bar[1], bar[2], bar[3], dp - 0.02, dp + 0.03, dm, 'y+');
            if (a1 - a0 > 1.0) this.wbox(P, (a0 + a1) / 2 - 0.02, (a0 + a1) / 2 + 0.02, b0, fan, dp - 0.012, dp, dm, 'y+');
            if (fan < b1) b.quad(P(a0 + 0.05, fan, dp + 0.02), P(a1 - 0.05, fan, dp + 0.02), P(a1 - 0.05, b1 - 0.05, dp + 0.02), P(a0 + 0.05, b1 - 0.05, dp + 0.02), 'glass');
            return;
        }
        if (broken) {                                                // the glass gone, the room dark behind it
            b.quad(P(a0, b0, dp + 0.3), P(a1, b0, dp + 0.3), P(a1, b1, dp + 0.3), P(a0, b1, dp + 0.3), 'void');
            for (const bar of [[a0, a0 + 0.05, b0, b1], [a1 - 0.05, a1, b0, b1], [a0 + 0.05, a1 - 0.05, b1 - 0.05, b1], [a0 + 0.05, a1 - 0.05, b0, b0 + 0.05]]) {
                if (rng.random() < 0.6) this.wbox(P, bar[0], bar[1], bar[2], bar[3], dp, dp + 0.04, fm, 'y+');
            }
            return;
        }
        // a window or a balcony's door: its frame, a mullion (a rail across a door), the panes set back in it
        const bars = [[a0, a0 + 0.05, b0, b1], [a1 - 0.05, a1, b0, b1], [a0 + 0.05, a1 - 0.05, b0, b0 + 0.05], [a0 + 0.05, a1 - 0.05, b1 - 0.05, b1]];
        if (a1 - a0 > 0.85) { const am = (a0 + a1) / 2.0; bars.push([am - 0.03, am + 0.03, b0 + 0.05, b1 - 0.05]); }
        if (kind === 'balc') bars.push([a0 + 0.05, a1 - 0.05, b0 + 0.9, b0 + 0.96]);
        for (const bar of bars) this.wbox(P, bar[0], bar[1], bar[2], bar[3], dp, dp + 0.045, fm, 'y+');
        b.quad(P(a0 + 0.05, b0 + 0.05, dp + 0.03), P(a1 - 0.05, b0 + 0.05, dp + 0.03), P(a1 - 0.05, b1 - 0.05, dp + 0.03), P(a0 + 0.05, b1 - 0.05, dp + 0.03), 'glass');
        const sh = spec.shutter ?? 0.0;
        if (sh > 0.02) {                                             // a roller blind let down in front of it
            const zs = b1 - (b1 - b0) * sh;
            b.quad(P(a0 + 0.02, zs, dp - 0.03), P(a1 - 0.02, zs, dp - 0.03), P(a1 - 0.02, b1, dp - 0.03), P(a0 + 0.02, b1, dp - 0.03), `shutter:${(this.seed + 5) % 6}`);
            this.wbox(P, a0 + 0.02, a1 - 0.02, zs - 0.04, zs, dp - 0.045, dp - 0.02, 'frame_alu');
        }
    }

    // a bay's openings from its plan
    _ops(spec, L, h) {
        const t = spec.type || 'blank';
        if (t === 'shop') return [[0.28, L - 0.28, 0.02, 2.75, 0.14, 'shop']];
        if (t === 'door') return [[L / 2.0 - 0.6, L / 2.0 + 0.6, 0.0, Math.min(2.45, h - 0.2), 0.2, 'door']];
        if (t === 'win') {
            const ww = Math.min(spec.w ?? 1.2, L - 0.7);
            const s = spec.sill ?? 0.95;
            return [[L / 2.0 - ww / 2.0, L / 2.0 + ww / 2.0, s, Math.min(s + 1.25, h - 0.25), 0.16, 'win']];
        }
        if (t === 'win2' && L > 3.0) return [0.27, 0.73].map((q) => [L * q - 0.42, L * q + 0.42, 0.95, 2.2, 0.16, 'win']);
        if (t === 'win2') return [[L / 2.0 - 0.6, L / 2.0 + 0.6, 0.95, 2.2, 0.16, 'win']];
        if (t === 'balc') {
            const dw = Math.min(1.4, L - 1.0);
            const out = [[L * 0.42 - dw / 2.0, L * 0.42 + dw / 2.0, 0.02, 2.2, 0.16, 'balc']];
            if (L > 3.9) out.push([L - 1.25, L - 0.45, 0.95, 2.2, 0.16, 'win']);
            return out;
        }
        return [];
    }

    // what is fixed to a bay's wall outside: a sill under each window, a hood over some, a cooler's condenser on its
    // brackets, a shop's sign and awning, a door's steps
    _dress(P, spec, ops, L, h, f, front, n, u) {
        const { b, rng } = this;
        const t = spec.type || 'blank';
        for (const [a0, a1, b0, b1, , kind] of ops) {
            if (kind === 'win') {
                this.wbox(P, a0 - 0.06, a1 + 0.06, b0 - 0.07, b0, -0.06, 0.1, this.CO, 'y+');
                if (this.hoods && front) this.wbox(P, a0 - 0.12, a1 + 0.12, b1 + 0.03, b1 + 0.11, -0.3, 0.0, this.CO, 'y+');
                if (spec.ac && b0 > 0.7) {
                    const a = a1 + 0.9 < L ? Math.min(L - 0.5, a1 + 0.1) : a0 - 0.5;
                    const c = P(a, b0 - 0.75, -0.19);
                    const M = M4.rows([[u[0], -n[0], 0.0, c[0]], [u[1], -n[1], 0.0, c[1]], [0.0, 0.0, 1.0, c[2]], [0.0, 0.0, 0.0, 1.0]]);
                    K.condenser(b, M);
                }
            }
        }
        if (t === 'shop') {
            const a0 = 0.28, a1 = L - 0.28;
            this.wbox(P, a0 - 0.08, a0, 0.02, 2.75, -0.02, 0.14, 'frame_alu', 'y+');         // the shutter's guides
            this.wbox(P, a1, a1 + 0.08, 0.02, 2.75, -0.02, 0.14, 'frame_alu', 'y+');
            this.wbox(P, 0.15, L - 0.15, -this.plinth + 0.0, 0.0, -0.3, 0.0, this.CO, 'y+z-');  // its step
            if (spec.sign) {
                // its sign: a boxed board over the shutter; or, where the shops share a canopy, standing on its edge.
                // The board carries the picture or the words the town was given, else plain paint
                const hh = Math.min(0.72, (L - 0.6) * 0.3125);
                const [zs0, d0, d1] = this.canopy_on ? [3.13, -1.35, -1.27] : [2.84, -0.09, 0.0];
                const zs1 = this.canopy_on ? zs0 + hh : Math.min(h - 0.06, zs0 + hh);
                this.wbox(P, 0.3, L - 0.3, zs0, zs1, d0, d1, 'frame_alu', this.canopy_on ? '' : 'y+');
                const k = rng.randrange(this.signs.length ? this.signs.length : N_BOARDS);
                const face = this.signs.length ? `sign:${k}` : `sign_board:${k}`;
                b.quad(P(0.34, zs0 + 0.04, d0 - 0.004), P(L - 0.34, zs0 + 0.04, d0 - 0.004), P(L - 0.34, zs1 - 0.04, d0 - 0.004), P(0.34, zs1 - 0.04, d0 - 0.004),
                    face, [[0.0, 0.0], [1.0, 0.0], [1.0, 1.0], [0.0, 1.0]]);
            }
            if (spec.awn !== null && spec.awn !== undefined) {       // canvas on a light frame, a valance at its edge
                const am = `awn:${spec.awn}`;
                const out = rng.uniform(1.1, 1.6), zt = 2.78, ze = 2.3;
                const G = [];
                for (let q = 0; q < 3; q++) {
                    const row = [];
                    for (let k = 0; k < 5; k++) row.push(P(0.12 + (L - 0.24) * k / 4.0, zt - (zt - ze) * q / 2.0 - 0.04 * Math.sin(Math.PI * k / 4.0) * (q > 0 ? 1 : 0), -0.02 - out * q / 2.0));
                    G.push(row);
                }
                this.b.grid(G, am, { smooth: true, flip: true });
                for (let k = 0; k < 8; k++) {                          // the valance, in tongues
                    const k0 = 0.12 + (L - 0.24) * k / 8.0, k1 = 0.12 + (L - 0.24) * (k + 1) / 8.0;
                    b.poly([P(k0, ze, -0.02 - out), P(k1, ze, -0.02 - out), P(k1, ze - 0.16, -0.02 - out), P((k0 + k1) / 2.0, ze - 0.24, -0.02 - out), P(k0, ze - 0.16, -0.02 - out)], am);
                }
                for (const a of [0.14, L - 0.14]) {
                    b.beam(P(a, zt - 0.05, 0.0), P(a, ze, -0.02 - out), 0.025, 0.025, 'steel_dark');
                    b.beam(P(a, zt - 0.9, 0.0), P(a, ze, -0.02 - out), 0.02, 0.02, 'steel_dark');
                }
            }
        }
        if (t === 'door' && f === 0) {
            const k = Math.max(1, pyRound(this.plinth / 0.15));
            for (let q = 0; q < k; q++)                              // its steps: each its own tread, down to the pavement
                this.wbox(P, L / 2.0 - 0.85, L / 2.0 + 0.85, -this.plinth, -this.plinth * q / k, -0.3 * (q + 1), -0.3 * q, this.CO, 'y+z-');
            this.wbox(P, L / 2.0 - 0.95, L / 2.0 + 0.95, Math.min(2.6, h - 0.15), Math.min(2.7, h - 0.05), -0.75, 0.0, this.CO, 'y+');
        }
    }

    _walls() {
        const { rng, xs, zf, F } = this;
        const hit = [1, 2, 3, 4].includes(this.dmg);
        for (let f = 0; f < F + 1; f++) {
            const z0 = zf[f], hs = zf[f + 1] - zf[f];
            const h = hs - SLAB;
            for (const s of this.slots) {
                const [kind, i, j] = s;
                const [A, B] = this.cellsOf(kind, i, j);
                const sa = this.st(A, f), sb = this.st(B, f);
                if ('NC'.includes(sa) && 'NC'.includes(sb)) continue;
                const [pa, pb] = kind === 'H' ? [[xs[i], this.Y(j, f)], [xs[i + 1], this.Y(j, f)]] : [[xs[i], this.Y(j, f)], [xs[i], this.Y(j + 1, f)]];
                const L = Math.hypot(pb[0] - pa[0], pb[1] - pa[1]);
                const state = this.wst.get(`${f},${kind},${i},${j}`) || 'ok';
                if ('RU'.includes(sa) && 'RU'.includes(sb)) {          // a partition between two rooms
                    const oa = this.isOpened(A, f) || sa === 'U', ob = this.isOpened(B, f) || sb === 'U';
                    if (!(oa || ob)) continue;                       // (nobody can see it)
                    const n = kind === 'H' ? [0.0, 1.0] : [1.0, 0.0];  // out of A, into B: its 'outer' face is B's wall
                    const u = [-n[1], n[0]];
                    let P0 = (u[0] * (pb[0] - pa[0]) + u[1] * (pb[1] - pa[1])) > 0 ? pa : pb;
                    P0 = [P0[0] + n[0] * PART / 2.0, P0[1] + n[1] * PART / 2.0];
                    const ma = this.paint(A, f), mb = this.paint(B, f);
                    if (sa === 'U' && sb === 'U') {
                        if (rng.random() < 0.6) {                    // (a thin partition between two fallen rooms mostly went)
                            const hh = h * rng.choice([0.3, 0.6, 1.0]);
                            this.wall(P0, u, n, L, z0, h, PART, mb, ma, { prof: [brokenTop(rng, L, hh), null] });
                        }
                    } else if (state === 'hole' || state === 'gone') {
                        this.wall(P0, u, n, L, z0, h, PART, mb, ma, { prof: holeProf(rng, L, h, state === 'gone') });
                    } else {
                        const ops = (L > 2.2 && rng.random() < 0.55) ? [[L * 0.3 - 0.45, L * 0.3 + 0.45, 0.0, 2.05, 0.1, 'none']] : [];
                        if (oa && ob) this.wall(P0, u, n, L, z0, h, PART, mb, ma, { ops });
                        else if (ob) this.wall(P0, u, n, L, z0, h, PART, mb, null, { ops: ops.map((o) => [o[0], o[1], o[2], o[3], 0.1, 'dark']) });
                        else this.wall(P0, u, n, L, z0, h, PART, null, ma, { ops: [] });
                    }
                    continue;
                }
                // one side is a room, the other is air
                const [ins, out_, s_in] = 'RU'.includes(sa) ? [A, B, sa] : [B, A, sb];
                const insIsA = ins === A;
                const n = kind === 'H' ? (insIsA ? [0.0, 1.0] : [0.0, -1.0]) : (insIsA ? [1.0, 0.0] : [-1.0, 0.0]);
                const u = [-n[1], n[0]];
                const P0 = (u[0] * (pb[0] - pa[0]) + u[1] * (pb[1] - pa[1])) > 0 ? pa : pb;
                const indoors = this.was(out_, f);                   // its far side was a room until the strike
                const front = kind === 'H' && j === 0;
                let mo, t;
                if (indoors) { mo = this.paint(out_, f); t = PART; }
                else if (out_ === null) {
                    mo = front ? this.PL : (kind === 'H' ? this.PLb : this.PLs); t = WALL;
                    if (front && f === 0) mo = this.PL2;
                } else { mo = this.PL; t = WALL; }                   // over the house's own lower roof
                const mi = this.paint(ins, f);
                if (s_in === 'U') {                                  // broken off in courses, open to the sky
                    this.wall(P0, u, n, L, z0, h, t, mo, mi, { prof: [brokenTop(rng, L, h), null] });
                    continue;
                }
                const opened = this.isOpened(ins, f);
                if (state === 'hole' || state === 'gone') {
                    if (state === 'gone' && rng.random() < 0.3) continue;
                    this.wall(P0, u, n, L, z0, h, t, mo, mi, { prof: holeProf(rng, L, h, state === 'gone') });
                    continue;
                }
                if (indoors) {
                    const ops = (L > 2.2 && rng.random() < 0.4 && !opened) ? [[L * 0.3 - 0.45, L * 0.3 + 0.45, 0.0, 2.05, 0.1, 'dark']] : [];
                    this.wall(P0, u, n, L, z0, h, t, mo, opened ? mi : null, { ops });
                    continue;
                }
                let spec = out_ === null ? (this.fac.get(`${f},${kind},${i},${j}`) || null) : null;
                if (spec === null) {                                 // a wall the plan did not know: on the roof, over a terrace
                    if (f === F && !this.roof_door.has(ck(ins)) && out_ !== null && this.st(out_, f - 1) === 'R' && this.n1.get(ck(out_)) === f) {
                        spec = { type: 'door', m: this.door_m };
                        this.roof_door.add(ck(ins));
                    } else if (rng.random() < 0.4) spec = { type: 'win', w: 0.9, sill: 1.0, shutter: 0.0, ac: false };
                    else spec = { type: 'blank' };
                }
                const ops = this._ops(spec, L, h);
                const broken = hit && rng.random() < 0.75;
                const P = this.wall(P0, u, n, L, z0, h, t, mo, opened ? mi : null, { ops, spec, broken, col_m: (mo === 'block' || mo === 'brick') ? this.CO : null });
                this._dress(P, spec, ops, L, h, f, front, n, u);
                if (spec.type === 'balc' && front && f >= 1) this.balc.add(`${f},${i}`);
            }
        }
    }

    // ------------------------------------------------------------------------------------------ the frame, where it shows
    _frame() {
        const { b, rng, xs, zf, F, nb, nd } = this;
        const expo = (c, f) => { const s = this.st(c, f); return s === 'U' || s === 'C' || (s === 'R' && this.isOpened(c, f)); };
        for (let f = 0; f < F + 1; f++) {
            const z0 = zf[f], z1 = zf[f + 1];
            for (let i = 0; i < nb + 1; i++) {
                for (let j = 0; j < nd + 1; j++) {
                    let around = [[i - 1, j - 1], [i - 1, j], [i, j - 1], [i, j]];
                    around = around.filter((c) => this.n1.has(ck(c)));
                    if (!around.some((c) => expo(c, f))) continue;
                    // (a finger's width inside the wall's face: where the wall still stands its plaster covers the frame)
                    const cx = Math.min(Math.max(xs[i], COL / 2.0 + 0.02), this.w - COL / 2.0 - 0.02);
                    const cy = Math.min(Math.max(this.Y(j, f), this.Y(0, f) + COL / 2.0 + 0.02), this.d - COL / 2.0 - 0.02);
                    const under = around.some((c) => this.st(c, f) === 'R');          // a slab rests on it
                    const built = around.some((c) => ['frame', 'build'].includes(this.cap1.get(ck(c))) && this.st(c, f) === 'C');
                    if (under) b.box([cx - COL / 2, cy - COL / 2, z0], [cx + COL / 2, cy + COL / 2, z1 - SLAB], this.CO, { skip: 'z-z+' });
                    else if (built) {
                        const full = around.some((c) => this.cap1.get(ck(c)) === 'frame') || rng.random() < 0.6;
                        K.stub(b, rng, cx, cy, z0, full ? (z1 - z0) : rng.uniform(0.5, 1.6), 4, COL);
                    } else {                                         // snapped, its steel standing out of it
                        const hh = (z1 - z0) * rng.uniform(0.35, 1.0);
                        K.stub(b, rng, cx, cy, z0, hh, rng.randrange(3, 6), COL);
                    }
                }
            }
            for (const s of this.slots) {
                const [kind, i, j] = s;
                const [A, B] = this.cellsOf(kind, i, j);
                const inA = A && this.n1.has(ck(A)), inB = B && this.n1.has(ck(B));
                if (!((inA && expo(A, f)) || (inB && expo(B, f)))) continue;
                const slab = this.st(A, f) === 'R' || this.st(B, f) === 'R';
                const framed = [A, B].some((c) => c && this.n1.has(ck(c)) && this.cap1.get(ck(c)) === 'frame' && this.st(c, f) === 'C');
                if (!(slab || framed)) continue;
                const zt = slab ? z1 - SLAB : z1;
                const zb = z1 - 0.5;
                if (kind === 'H') {
                    const y = Math.min(Math.max(this.Y(j, f), this.Y(0, f) + 0.17), this.d - 0.17);
                    b.box([xs[i] + COL / 2, y - 0.15, zb], [xs[i + 1] - COL / 2, y + 0.15, zt], this.CO, { skip: 'x-x+' + (slab ? 'z+' : '') });
                } else {
                    const x = Math.min(Math.max(xs[i], 0.17), this.w - 0.17);
                    b.box([x - 0.15, this.Y(j, f) + COL / 2, zb], [x + 0.15, this.Y(j + 1, f) - COL / 2, zt], this.CO, { skip: 'y-y+' + (slab ? 'z+' : '') });
                }
            }
        }
        // block half laid for the storey being built: clean courses, stepped where the day's work stopped
        for (const [key, cp] of this.cap1) {
            if (cp !== 'build') continue;
            const c = cell(key);
            const f = this.n1.get(key);
            if (f > F) continue;
            for (const [sd, [kind, i, j]] of this.slotsOf(c)) {
                const [A, B] = this.cellsOf(kind, i, j);
                const other = (A && A[0] === c[0] && A[1] === c[1]) ? B : A;
                if (other && this.n1.has(ck(other)) && this.st(other, f) !== 'N') continue;
                if (rng.random() < 0.3) continue;
                const n = { S: [0.0, -1.0], N: [0.0, 1.0], W: [-1.0, 0.0], E: [1.0, 0.0] }[sd];
                const u = [-n[1], n[0]];
                const [pa, pb] = kind === 'H' ? [[xs[i], this.Y(j, f)], [xs[i + 1], this.Y(j, f)]] : [[xs[i], this.Y(j, f)], [xs[i], this.Y(j + 1, f)]];
                const P0 = (u[0] * (pb[0] - pa[0]) + u[1] * (pb[1] - pa[1])) > 0 ? pa : pb;
                const L = Math.hypot(pb[0] - pa[0], pb[1] - pa[1]);
                const base = rng.uniform(0.6, 1.8);
                this.wall(P0, u, n, L, zf[f], zf[f + 1] - zf[f], 0.2, 'block', 'block', { prof: [jag(rng, L, base, 0.25, 0.2, 2.2, 0.2, [0.8, 2.0]), null] });
            }
        }
    }

    // ------------------------------------------------------------------------------------------ balconies
    _balconies() {
        const { b, rng, xs, zf } = this;
        this.balc_dish = false;
        for (let f = 1; f < this.F; f++) {
            let k = 0;
            while (k < this.nb) {
                if (!this.balc.has(`${f},${k}`)) { k += 1; continue; }
                let k1 = k;
                while (k1 + 1 < this.nb && this.balc.has(`${f},${k1 + 1}`)) k1 += 1;
                const xa = xs[k] + 0.12, xb = xs[k1 + 1] - 0.12;
                const yf = this.Y(0, f);
                const out = rng.choice([1.05, 1.2, 1.3]);
                const z = zf[f] - 0.03;
                const R = this.balc_round ? 0.45 : 0.0;
                const line = R ? [[xa, yf], ...arc([xa + R, yf - out + R], R, 180.0, 270.0, 4), ...arc([xb - R, yf - out + R], R, 270.0, 360.0, 4), [xb, yf]]
                    : [[xa, yf], [xa, yf - out], [xb, yf - out], [xb, yf]];
                b.prism(line, z - 0.14, z, this.CO, { top: 'floor', sides: [...Array(line.length - 1).fill(true), false] });    // its slab
                const pm = this.PL2;
                if (this.balc_kind === 'solid') b.run(line, 0.12, z, z + 0.95, pm, { top: this.CO });
                else if (this.balc_kind === 'claustra') {
                    b.run(line, 0.12, z, z + 0.3, pm);
                    b.run(line, 0.1, z + 0.3, z + 0.9, 'claustra');
                    b.run(line, 0.14, z + 0.9, z + 0.97, this.CO);
                } else {                                             // a kerb, posts, three rails
                    b.run(line, 0.1, z, z + 0.12, this.CO);
                    for (const q of [0.4, 0.68, 0.96]) for (let s = 0; s < line.length - 1; s++) b.beam([line[s][0], line[s][1], z + q], [line[s + 1][0], line[s + 1][1], z + q], 0.03, 0.03, 'steel_paint');
                    const nseg = Math.max(2, Math.trunc((xb - xa) / 0.9));
                    for (let q = 0; q <= nseg; q++) {
                        const px = xa + (xb - xa) * q / nseg;
                        const py = (!R || (xa + R < px && px < xb - R)) ? yf - out : yf - out + R;
                        b.beam([px, py, z + 0.1], [px, py, z + 0.96], 0.03, 0.03, 'steel_paint', { up: [1.0, 0.0, 0.0] });
                    }
                }
                if (rng.random() < 0.3 && !R) {                      // washing over its parapet: side by side
                    let px = xa + rng.uniform(0.3, 0.8);
                    for (;;) {
                        const ww = rng.choice([0.5, 0.6, 0.8, 1.0, 1.4]);
                        if (px + ww > xb - 0.3) break;
                        K.rug_over(b, rng, [px + ww / 2.0, yf - out], [1.0, 0.0], [0.0, -1.0], z + 0.95, 0.12, rng.choice(K.CLOTH), ww);
                        px += ww + rng.uniform(0.08, 0.5);
                    }
                }
                if (!this.balc_dish && rng.random() < 0.18) {        // one family's dish, on its balcony
                    this.balc_dish = true;
                    this.anchors.push([rng.uniform(xa + 0.4, xb - 0.4), yf - out + 0.35, z]);
                }
                k = k1 + 1;
            }
        }
        if (this.canopy_on) {                                        // the shops' canopy, cast with the first floor
            const z = this.zf[0] + 3.0;
            b.box([-0.1, -1.35, z], [this.w + 0.1, 0.0, z + 0.12], this.CO, { skip: 'y+' });
        }
    }

    // ------------------------------------------------------------------------------------------ the roofs' edges
    _parapets() {
        const { b, xs, zf, F } = this;
        const levels = [...new Set(this.cells.map((c) => this.n1.get(ck(c))).filter((v) => v >= 1))].sort((a, c) => a - c);
        this.roofs = new Map();                                      // level -> its bays that are a roof as built
        for (const L of levels) {
            const edges = [];
            for (const c of this.cells) {
                if (this.n1.get(ck(c)) !== L || this.n0.get(ck(c)) !== L || this.cap1.has(ck(c))) continue;
                if (!this.roofs.has(L)) this.roofs.set(L, []);
                this.roofs.get(L).push(c);
                const [i, j] = c;
                const x0 = pyRound(xs[i], 3), x1 = pyRound(xs[i + 1], 3), y0 = pyRound(this.Yl(j, L), 3), y1 = pyRound(this.Yl(j + 1, L), 3);
                for (const [s, di, dj] of SIDES) {
                    const nbc = ck([i + di, j + dj]);
                    if (this.n1.has(nbc)) {
                        if (this.n1.get(nbc) > L || this.n1.get(nbc) === L) continue;       // a higher part's wall, or the roof runs on
                        if (this.n0.get(nbc) >= L) continue;                                // that side fell: the parapet went with it
                    }
                    if (this.bite.has(`${L},${i},${j},${s}`)) continue;
                    edges.push({ S: [[x0, y0], [x1, y0]], E: [[x1, y0], [x1, y1]], N: [[x1, y1], [x0, y1]], W: [[x0, y1], [x0, y0]] }[s]);
                }
            }
            const top = L === F + 1;
            const hp = top ? 0.14 : (L === F ? this.hp : Math.min(this.hp, 0.9));
            for (const [pts, closed] of chains(edges)) {
                if (top) b.run(pts, 0.15, zf[L], zf[L] + hp, this.CO, { closed });
                else {
                    b.run(pts, 0.2, zf[L], zf[L] + hp, this.par_m, { closed, top: this.CO });
                    b.run(pts, 0.2, zf[L] + hp, zf[L] + hp + 0.06, this.CO, { closed });       // its coping
                }
                this._par.push([L, pts, closed, hp]);
            }
        }
        // a low wall across the roof between two households' halves, a gap left in it to step through
        const rng = this.rng;
        const rf = new Set((this.roofs.get(F) || []).map(ck));
        if (rf.size >= 4 && rng.random() < 0.45) {
            const cands = [];
            for (let i = 1; i < this.nb; i++) {
                let cnt = 0;
                for (let j = 0; j < this.nd; j++) if (rf.has(ck([i - 1, j])) && rf.has(ck([i, j]))) cnt++;
                if (cnt >= 2) cands.push(i);
            }
            if (cands.length) {
                const i = rng.choice(cands);
                const js = [...Array(this.nd).keys()].filter((j) => rf.has(ck([i - 1, j])) && rf.has(ck([i, j])));
                const gap = rng.choice(js);
                for (const j of js) {
                    const ya = this.Yl(j, F) + (!rf.has(ck([i, j - 1])) ? 0.2 : 0.0);
                    let yb = this.Yl(j + 1, F) - (!rf.has(ck([i, j + 1])) ? 0.2 : 0.0);
                    if (j === gap) yb -= 1.1;
                    if (yb - ya > 0.4) b.box([xs[i] - 0.08, ya, zf[F]], [xs[i] + 0.08, yb, zf[F] + this.hp * 0.85], this.par_m, { skip: 'z-', top: this.CO });
                }
            }
        }
    }

    // ------------------------------------------------------------------------------------------ what lives on the roofs
    _roofThings() {
        const { b, rng, xs, zf, F } = this;
        const taken = [];
        const spot = (c, L, r, tries = 10, edge = null) => {
            const [i, j] = c;
            const x0 = xs[i] + 0.4 + r, x1 = xs[i + 1] - 0.4 - r, y0 = this.Yl(j, L) + 0.4 + r, y1 = this.Yl(j + 1, L) - 0.4 - r;
            if (x1 <= x0 || y1 <= y0) return null;
            for (let q = 0; q < tries; q++) {
                let x = rng.uniform(x0, x1), y = rng.uniform(y0, y1);
                if (edge === 'corner') { x = rng.choice([x0, x1]); y = rng.choice([y0, y1]); }
                if (taken.every(([tx, ty, tr]) => Math.hypot(x - tx, y - ty) > r + tr)) { taken.push([x, y, r]); return [x, y]; }
            }
            return null;
        };
        const top = this.roofs.get(F + 1) || [];
        const main = [];
        for (const [L, cs] of this.roofs) if (L <= F) main.push(...cs);
        const lvl = new Map(main.map((c) => [ck(c), this.n1.get(ck(c))]));
        if (!main.length && !top.length) return;
        const tankM = () => rng.choice(['tank_white', 'tank_white', 'tank_black', 'tank_blue', 'tank_black']);
        let n_tanks = 0;
        for (const c of top) {                                       // the tank on the stair's head, where the pressure is
            if (rng.random() < 0.55) {
                const p = spot(c, F + 1, 0.7);
                if (p) {
                    const z = zf[F + 1];
                    if (rng.random() < 0.6) {
                        b.box([p[0] - 0.6, p[1] - 0.6, z], [p[0] + 0.6, p[1] + 0.6, z + 0.2], 'block', { skip: 'z-' });
                        K.tank_poly(b, p[0], p[1], z + 0.2, tankM());
                    } else {
                        const rz = rng.uniform(-0.1, 0.1);
                        K.tank_steel(b, rng, p[0], p[1], z, rz, rng.choice(['zinc', 'zinc_old', 'rust']));
                    }
                    n_tanks += 1;
                }
            }
            if (rng.random() < 0.3) {
                const p = spot(c, F + 1, 0.2);
                if (p) K.antenna(b, rng, p[0], p[1], zf[F + 1]);
            }
        }
        if (!main.length) return;
        const pick = () => rng.choice(main);
        const nt = n_tanks === 0 ? rng.choice([1, 1, 2]) : rng.choice([0, 0, 1]);
        for (let q = 0; q < nt; q++) {
            const c = pick();
            const p = spot(c, lvl.get(ck(c)), 0.8);
            if (!p) continue;
            const z = zf[lvl.get(ck(c))], k = rng.random();
            let hs_;
            if (k < 0.45) {
                hs_ = rng.choice([0.6, 0.9, 1.2, 1.6]);
                K.stand(b, p[0], p[1], z, 1.15, 1.15, hs_);
                K.tank_poly(b, p[0], p[1], z + hs_, tankM());
            } else if (k < 0.75) {
                hs_ = rng.choice([0.5, 0.8, 1.2]);
                K.stand(b, p[0], p[1], z, 1.25, 1.25, hs_);
                K.tank_steel(b, rng, p[0], p[1], z + hs_, 0.0, rng.choice(['zinc', 'zinc_old', 'rust', 'tank_red']));
            } else {
                hs_ = 0.3;
                const rz = rng.choice([0.0, Math.PI / 2.0]);
                K.tank_lying(b, p[0], p[1], z, rz, rng.choice(['zinc', 'zinc_old', 'tank_red']));
            }
            // its pipe: down from it, across the roof to the edge, and over (the pale lines every roof there has)
            const [i, j] = c;
            const ex = p[0] - xs[i] < xs[i + 1] - p[0] ? xs[i] + 0.3 : xs[i + 1] - 0.3;
            const sgn = ex > p[0] ? 1.0 : -1.0;
            const du = rng.uniform(1.0, 2.5), ds = rng.choice([-1, 1]);
            const ye = Math.min(Math.max(p[1] + 0.2 + du * ds, this.Yl(j, lvl.get(ck(c))) + 0.3), this.Yl(j + 1, lvl.get(ck(c))) - 0.3);
            b.path([[p[0] + sgn * 0.3, p[1] + 0.2, z + hs_ + 0.05], [p[0] + sgn * 0.62, p[1] + 0.2, z + hs_ - 0.1], [p[0] + sgn * 0.66, p[1] + 0.2, z + 0.05],
                [ex, p[1] + 0.2, z + 0.05], [ex, ye, z + 0.05]], 0.028, rng.choice(['plastic_white', 'plastic_white', 'zinc_old']), { n: 4 });
        }
        const nc = rng.choice([0, 1, 1, 2, 2, 3, 4]);
        for (let q = 0; q < nc; q++) {                               // coolers, in ones and twos
            const c = pick();
            const p = spot(c, lvl.get(ck(c)), 0.75);
            if (p) K.cooler(b, p[0], p[1], zf[lvl.get(ck(c))], rng.choice([0.0, Math.PI / 2.0, Math.PI, -Math.PI / 2.0]));
        }
        if (rng.random() < (this.low ? 0.85 : 0.65)) {               // washing
            let c = null, best = -Infinity;
            for (const q of main) {
                const v = (xs[q[0] + 1] - xs[q[0]]) * (this.ys[q[1] + 1] - this.ys[q[1]]) * rng.uniform(0.6, 1.0);
                if (v > best) { best = v; c = q; }
            }
            const [i, j] = c;
            const L = lvl.get(ck(c));
            const x0 = xs[i] + 0.6, y0 = this.Yl(j, L) + 0.7, y1 = this.Yl(j + 1, L) - 0.7;
            let x1 = xs[i + 1] - 0.6;
            if (x1 - x0 > 1.6 && y1 - y0 > 0.4) {
                const y = rng.uniform(y0, y1);
                if (lvl.has(ck([i + 1, j])) && lvl.get(ck([i + 1, j])) === L && rng.random() < 0.6) x1 = xs[i + 2] - 0.6;     // across two bays
                K.washing(b, rng, [x0, y], [x1, y], zf[L], { lines: rng.choice([1, 2, 2]) });
                taken.push([(x0 + x1) / 2.0, y, (x1 - x0) / 2.0]);
            }
        }
        for (const [kind, pr] of [['solar', 0.16], ['bed', 0.22], ['table', 0.14], ['shade', 0.18], ['junk', 0.6], ['junk', 0.35], ['blocks', 0.14], ['antenna', 0.4], ['bed', 0.1], ['junk', 0.15]]) {
            if (rng.random() > pr) continue;
            const c = pick();
            const L = lvl.get(ck(c));
            const z = zf[L];
            if (kind === 'shade') {
                const p = spot(c, L, 1.5);
                if (p) {
                    K.shade(b, rng, p[0] - 1.3, p[1] - 1.1, p[0] + 1.3, p[1] + 1.1, z);
                    if (rng.random() < 0.6) K.table_and_chairs(b, rng, p[0], p[1], z);
                }
                continue;
            }
            const p = spot(c, L, { solar: 1.3, bed: 1.1, table: 1.1, junk: 1.0, blocks: 0.9, antenna: 0.2 }[kind]);
            if (!p) continue;
            if (kind === 'solar') K.solar_heater(b, p[0], p[1], z, Math.PI);
            else if (kind === 'bed') { const rz = rng.choice([0.0, Math.PI / 2.0]) + rng.uniform(-0.1, 0.1); K.bed(b, rng, p[0], p[1], z, rz); }
            else if (kind === 'table') K.table_and_chairs(b, rng, p[0], p[1], z);
            else if (kind === 'junk') K.junk(b, rng, p[0], p[1], z);
            else if (kind === 'blocks') K.block_pile(b, rng, p[0], p[1], z, rng.uniform(0.0, 1.5));
            else K.antenna(b, rng, p[0], p[1], z);
        }
        const na = rng.choice([1, 1, 2, 2, 3]);
        for (let q = 0; q < na; q++) {                               // where the dishes stand (the town turns them one way)
            const c = pick();
            const p = spot(c, lvl.get(ck(c)), 0.55);
            if (p) this.anchors.push([p[0], p[1], zf[lvl.get(ck(c))]]);
        }
        const nv = rng.randrange(1, 3);
        for (let q = 0; q < nv; q++) {                               // a vent, a soil pipe's head
            const c = pick();
            const L = lvl.get(ck(c));
            const p = spot(c, L, 0.15, 10, 'corner');
            if (p) b.tube([p[0], p[1], zf[L]], [p[0], p[1], zf[L] + rng.uniform(0.5, 0.9)], 0.05, 'zinc_old', { n: 6 });
        }
        if (rng.random() < 0.3 && this.roofs.has(F)) {              // the next storey's columns, begun: round the roof's edge
            const rF = new Set(this.roofs.get(F).map(ck));
            for (let i = 0; i < this.nb + 1; i++) {
                for (let j = 0; j < this.nd + 1; j++) {
                    const around = [[i - 1, j - 1], [i - 1, j], [i, j - 1], [i, j]];
                    if (!around.some((c) => rF.has(ck(c))) || around.some((c) => this.n1.has(ck(c)) && this.n1.get(ck(c)) > F)) continue;
                    if (rng.random() < 0.8) {
                        const cx = Math.min(Math.max(xs[i], 0.36), this.w - 0.36);
                        const cy = Math.min(Math.max(this.Yl(j, F), this.Yl(0, F) + 0.36), this.d - 0.36);
                        K.stub(b, rng, cx, cy, zf[F], rng.uniform(0.5, 1.3));
                    }
                }
            }
        }
        for (const [L, pts, , hp] of this._par) {                    // a carpet aired over a parapet
            if (L <= F && rng.random() < 0.22 && pts.length >= 2) {
                const k = rng.randrange(pts.length - 1);
                const a = [pts[k][0], pts[k][1], 0], c = [pts[k + 1][0], pts[k + 1][1], 0];
                if (V.len(V.sub(c, a)) > 2.6) {
                    const u = V.norm(V.sub(c, a));
                    K.rug_over(b, rng, V.lerp(a, c, rng.uniform(0.3, 0.7)), u, [u[1], -u[0]], zf[L] + hp + 0.06, 0.2);
                }
            }
        }
    }

    // ------------------------------------------------------------------------------------------ in the opened rooms
    _insides() {
        const { rng, xs, zf } = this;
        const opened = [...this.opened].map((k) => k.split(',').map(Number)).sort((a, c) => a[0] - c[0] || a[1] - c[1] || a[2] - c[2]);
        for (const [i, j, f] of opened) {
            const c = [i, j];
            const x0 = xs[i] + 0.2, x1 = xs[i + 1] - 0.2, y0 = this.Y(j, f) + 0.2, y1 = this.Y(j + 1, f) - 0.2;
            if (rng.random() < 0.75) K.furniture(this.b, rng, x0, y0, x1, y1, zf[f], zf[f + 1] - zf[f] - SLAB);
            // along each wall that went: a band of what it was, lying on the floor's very edge and over it
            const X0 = xs[i] + 0.04, X1 = xs[i + 1] - 0.04, Y0 = this.Y(j, f) + 0.04, Y1 = this.Y(j + 1, f) - 0.04;
            for (const [sd, s] of this.slotsOf(c)) {
                if (!['hole', 'gone'].includes(this.wst.get(`${f},${s[0]},${s[1]},${s[2]}`))) continue;
                const paints = [this.PL, this.paint(c, f)];
                if (sd === 'S' || sd === 'N') {
                    const yy = sd === 'S' ? Y0 + 0.4 : Y1 - 0.4;
                    const rx = (X1 - X0) / 2.0 * rng.uniform(0.75, 1.0), ry = rng.uniform(0.6, 1.0), hh = rng.uniform(0.3, 0.6);
                    K.heap(this.b, rng, (X0 + X1) / 2.0, yy, rx, ry, hh, zf[f], { pieces: rng.randrange(10, 18), paints, clip: [X0, Y0, X1, Y1], field: false, over: 0.3 });
                } else {
                    const xx = sd === 'W' ? X0 + 0.4 : X1 - 0.4;
                    const rx = rng.uniform(0.6, 1.0), ry = (Y1 - Y0) / 2.0 * rng.uniform(0.75, 1.0), hh = rng.uniform(0.3, 0.6);
                    K.heap(this.b, rng, xx, (Y0 + Y1) / 2.0, rx, ry, hh, zf[f], { pieces: rng.randrange(10, 18), paints, clip: [X0, Y0, X1, Y1], field: false, over: 0.3 });
                }
            }
        }
        for (const c of this.cells) {                                // on a floor that is the top now: what fell onto it
            const n = this.n1.get(ck(c));
            if (n >= this.n0.get(ck(c)) || n < 1) continue;
            const [i, j] = c;
            const x0 = xs[i] + 0.25, x1 = xs[i + 1] - 0.25, y0 = this.Yl(j, n) + 0.25, y1 = this.Yl(j + 1, n) - 0.25;
            const lost = this.n0.get(ck(c)) - n;
            const cx = (x0 + x1) / 2.0 + rng.uniform(-0.4, 0.4), cy = (y0 + y1) / 2.0 + rng.uniform(-0.4, 0.4);
            const pieces = rng.randrange(12, 22), plates = rng.randrange(1, 3);
            K.heap(this.b, rng, cx, cy, (x1 - x0) * 0.46, (y1 - y0) * 0.46, Math.min(1.5, 0.35 + 0.3 * lost), zf[n],
                { pieces, plates, paints: [this.PL, this.paint(c, n)], clip: [x0, y0, x1, y1], field: false, plate_top: 'roof_dmg' });
            if (this.cap1.get(ck(c)) === 'roofless' && rng.random() < 0.5) K.furniture(this.b, rng, x0, y0, x1, y1, zf[n], 2.9);
        }
    }

    // ------------------------------------------------------------------------------------------ at its foot
    _fallen() {
        const { rng, xs } = this;
        const down = this.cells.filter((c) => this.n1.get(ck(c)) < this.n0.get(ck(c)));
        if (down.length && (this.dmg === 2 || this.dmg === 3)) {
            const vol = down.reduce((s, c) => s + (this.n0.get(ck(c)) - this.n1.get(ck(c))) * (this.n1.get(ck(c)) === 0 ? 1.0 : 0.35), 0);
            let gx = down.reduce((s, c) => s + (xs[c[0]] + xs[c[0] + 1]) / 2.0, 0) / down.length;
            let gy = down.reduce((s, c) => s + (this.ys[c[1]] + this.ys[c[1] + 1]) / 2.0, 0) / down.length;
            const ex = Math.max(...down.map((c) => xs[c[0] + 1])) - Math.min(...down.map((c) => xs[c[0]]));
            const ey = Math.max(...down.map((c) => this.ys[c[1] + 1])) - Math.min(...down.map((c) => this.ys[c[1]]));
            gx += (gx - this.w / 2.0) * 0.25;                        // it spills outward, away from what still stands
            gy += (gy - this.d / 2.0) * 0.25;
            const rx = ex / 2.0 + rng.uniform(1.6, 2.8), ry = ey / 2.0 + rng.uniform(1.6, 2.8);
            const h = Math.min(4.6, 0.9 + 0.55 * vol ** 0.65, 0.55 * Math.min(rx, ry));
            K.heap(this.b, rng, gx, gy, rx, ry, h, 0.0, { pieces: Math.trunc(30 + 10 * rx * ry ** 0.5), plates: rng.randrange(3, 7),
                paints: [this.PL, PAINTS[this.seed % 7], PAINTS[(this.seed + 3) % 7]], plate_top: 'floor' });
            for (const c of down) {                                  // the floors that came down, one on another
                if (this.n1.get(ck(c)) !== 0) continue;
                const cx = (xs[c[0]] + xs[c[0] + 1]) / 2.0, cy = (this.ys[c[1]] + this.ys[c[1] + 1]) / 2.0;
                const hz = h * (1.0 - K.smooth(Math.min(1.0, Math.hypot((cx - gx) / rx, (cy - gy) / ry)))) ** 1.1;
                const nk = Math.min(this.n0.get(ck(c)), 4);
                for (let k = 0; k < nk; k++) {
                    const last = k === nk - 1;
                    const px = cx + rng.uniform(-0.8, 0.8), py = cy + rng.uniform(-0.8, 0.8);
                    const w = (xs[c[0] + 1] - xs[c[0]]) * rng.uniform(0.7, 1.0), d = (this.ys[c[1] + 1] - this.ys[c[1]]) * rng.uniform(0.7, 1.0);
                    K.slab_piece(this.b, rng, [px, py, hz + 0.25 + 0.4 * k], w, d, 0.3, last ? 'roof_dmg' : 'floor', { rz: rng.uniform(-0.3, 0.3) });
                }
            }
        }
        if (this.blown !== null) {                                   // under a blown front: its walls, on the pavement
            const [k0, k1, f0] = this.blown;
            const cx = (xs[k0] + xs[k1 + 1]) / 2.0;
            const n_f = this.F - f0;
            const hx = cx + rng.uniform(-0.6, 0.6), rx = (xs[k1 + 1] - xs[k0]) / 2.0 + rng.uniform(0.8, 1.8), ry = rng.uniform(2.0, 3.0);
            K.heap(this.b, rng, hx, -1.2, rx, ry, Math.min(2.2, 0.5 + 0.35 * n_f), 0.0, { pieces: Math.trunc(26 + 8 * (k1 - k0 + 1) * n_f), plates: rng.randrange(2, 5),
                paints: [this.PL, this.PL, PAINTS[this.seed % 7]], plate_top: this.PL });
        }
    }
}
