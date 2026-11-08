// 'three/tsl', evaluated eagerly on the CPU over every pixel of a grid at once, in float64.
//
// The parity oracle for the Blender port of Ekigar. Ekigar builds its terrain as one TSL expression; with this module
// standing in for 'three/tsl' (deno --import-map), Ekigar's OWN compile.js / registry.js / landforms run unchanged and
// every node call computes its value immediately, lane by lane (one lane per pixel). So the field it produces is
// Ekigar's code, not a re-implementation of it: what the Python port is compared against.
//
// Values: a T holds components (1 for float, 2..4 for vecN), each a number (uniform across lanes) or a
// Float64Array(N). Kinds: float, uint, bool. JS numbers are float constants (uint when they meet a uint operand).
// Screen derivatives (dFdx/dFdy) need neighbours, which is why lanes cover the whole grid: they are quad differences
// over the grid set with __setGrid (coarse by default, as a GPU 2x2 quad: constant across the quad).
//
// Only what Ekigar's field path uses is here; anything else throws, so a gap cannot pass silently.

let N = 1, GW = 1, GH = 1, DMODE = 'coarse';

export function __setGrid(w, h, mode = 'coarse') { GW = w; GH = h; N = w * h; DMODE = mode; }
export function __lanes() { return N; }

const isArr = (a) => a instanceof Float64Array;

function ew1(f, a) {
    if (!isArr(a)) return f(a);
    const o = new Float64Array(N);
    for (let i = 0; i < N; i++) o[i] = f(a[i]);
    return o;
}
function ew2(f, a, b) {
    const A = isArr(a), B = isArr(b);
    if (!A && !B) return f(a, b);
    const o = new Float64Array(N);
    if (A && B) for (let i = 0; i < N; i++) o[i] = f(a[i], b[i]);
    else if (A) for (let i = 0; i < N; i++) o[i] = f(a[i], b);
    else for (let i = 0; i < N; i++) o[i] = f(a, b[i]);
    return o;
}
function ew3(f, a, b, c) {
    const A = isArr(a), B = isArr(b), C = isArr(c);
    if (!A && !B && !C) return f(a, b, c);
    const o = new Float64Array(N);
    for (let i = 0; i < N; i++) o[i] = f(A ? a[i] : a, B ? b[i] : b, C ? c[i] : c);
    return o;
}

export class T {
    constructor(c, k = 'float') { this.c = c; this.k = k; this.isNode = true; }
    get n() { return this.c.length; }
    comp(i) { return new T([this.c[i]], this.k); }
    toVar() { return new T(this.c.slice(), this.k); }
    assign(v) {
        // a var keeps its declared kind; Ekigar only ever assigns a value of the same kind
        this.c = bcast(toT(v, this.k), this.n).c;
        return this;
    }
    addAssign(v) { return this.assign(this.add(v)); }
    subAssign(v) { return this.assign(this.sub(v)); }
    mulAssign(v) { return this.assign(this.mul(v)); }
    divAssign(v) { return this.assign(this.div(v)); }

    add(b) { return bin(this, b, (x, y) => x + y, (x, y) => (x + y) >>> 0); }
    sub(b) { return bin(this, b, (x, y) => x - y, (x, y) => (x - y) >>> 0); }
    mul(b) { return bin(this, b, (x, y) => x * y, (x, y) => Math.imul(x, y) >>> 0); }
    div(b) { return bin(this, b, (x, y) => x / y, (x, y) => Math.floor(x / y) >>> 0); }
    bitXor(b) { return bin(this, b, null, (x, y) => (x ^ y) >>> 0); }
    bitAnd(b) { return bin(this, b, null, (x, y) => (x & y) >>> 0); }
    bitOr(b) { return bin(this, b, null, (x, y) => (x | y) >>> 0); }
    shiftRight(b) { return bin(this, b, null, (x, y) => x >>> y); }
    shiftLeft(b) { return bin(this, b, null, (x, y) => (x << y) >>> 0); }

    negate() { return map1(this, (x) => -x); }
    oneMinus() { return map1(this, (x) => 1 - x); }
    reciprocal() { return map1(this, (x) => 1 / x); }
    abs() { return map1(this, Math.abs); }
    sign() { return map1(this, Math.sign); }
    floor() { return map1(this, Math.floor); }
    ceil() { return map1(this, Math.ceil); }
    round() { return map1(this, Math.round); }
    fract() { return map1(this, (x) => x - Math.floor(x)); }
    sin() { return map1(this, Math.sin); }
    cos() { return map1(this, Math.cos); }
    exp() { return map1(this, Math.exp); }
    log() { return map1(this, Math.log); }
    sqrt() { return map1(this, Math.sqrt); }
    saturate() { return clamp(this, 0, 1); }
    pow(b) { return bin(this, b, Math.pow, null); }
    max(b) { return bin(this, b, Math.max, (x, y) => Math.max(x, y)); }
    min(b) { return bin(this, b, Math.min, (x, y) => Math.min(x, y)); }
    clamp(lo, hi) { return clamp(this, lo, hi); }
    length() { return length(this); }
    normalize() { return normalize(this); }
    dot(b) { return dot(this, b); }

    greaterThan(b) { return cmp(this, b, (x, y) => (x > y ? 1 : 0)); }
    lessThan(b) { return cmp(this, b, (x, y) => (x < y ? 1 : 0)); }
    greaterThanEqual(b) { return cmp(this, b, (x, y) => (x >= y ? 1 : 0)); }
    lessThanEqual(b) { return cmp(this, b, (x, y) => (x <= y ? 1 : 0)); }
    equal(b) { return cmp(this, b, (x, y) => (x === y ? 1 : 0)); }
    notEqual(b) { return cmp(this, b, (x, y) => (x !== y ? 1 : 0)); }
    and(b) { return cmp(this, b, (x, y) => (x && y ? 1 : 0)); }
    or(b) { return cmp(this, b, (x, y) => (x || y ? 1 : 0)); }
    not() { const t = map1(this, (x) => (x ? 0 : 1)); t.k = 'bool'; return t; }

    get x() { return this.comp(0); } get y() { return this.comp(1); }
    get z() { return this.comp(2); } get w() { return this.comp(3); }
    get r() { return this.comp(0); } get g() { return this.comp(1); }
    get b() { return this.comp(2); } get a() { return this.comp(3); }
}
// two- and three-letter swizzles (xy, yx, zw, xyz ...)
{
    const L = 'xyzw';
    for (const a of L) for (const b of L) {
        Object.defineProperty(T.prototype, a + b, { get() { return new T([this.c[L.indexOf(a)], this.c[L.indexOf(b)]], this.k); } });
        for (const c of L) {
            Object.defineProperty(T.prototype, a + b + c, {
                get() { return new T([this.c[L.indexOf(a)], this.c[L.indexOf(b)], this.c[L.indexOf(c)]], this.k); },
            });
        }
    }
}

class U extends T {
    constructor(v) { super([Number(v) || 0], 'float'); }
    get value() { return this.c[0]; }
    set value(v) { this.c = [Number(v) || 0]; }
}

function toT(v, kindHint = 'float') {
    if (v instanceof T) return v;
    if (typeof v === 'number') return new T([kindHint === 'uint' ? (v >>> 0) : v], kindHint === 'uint' ? 'uint' : 'float');
    if (typeof v === 'boolean') return new T([v ? 1 : 0], 'bool');
    if (Array.isArray(v)) return new T(v.map(Number), 'float');
    throw new Error(`tsl shim: cannot use ${typeof v} ${v} as a node`);
}

function bcast(t, n) {
    if (t.n === n) return t;
    if (t.n === 1) return new T(new Array(n).fill(t.c[0]), t.k);
    throw new Error(`tsl shim: size ${t.n} cannot broadcast to ${n}`);
}

function bin(a, b, ff, fu) {
    const A = toT(a);
    const B = toT(b, A.k === 'uint' ? 'uint' : 'float');
    const k = (A.k === 'uint' || B.k === 'uint') ? 'uint' : 'float';
    const n = Math.max(A.n, B.n);
    const a2 = bcast(A, n), b2 = bcast(B, n);
    const f = k === 'uint' ? fu : ff;
    if (!f) throw new Error(`tsl shim: operation not defined for ${k}`);
    return new T(a2.c.map((ca, i) => ew2(f, ca, b2.c[i])), k);
}

function cmp(a, b, f) {
    const A = toT(a), B = toT(b);
    const n = Math.max(A.n, B.n);
    const a2 = bcast(A, n), b2 = bcast(B, n);
    return new T(a2.c.map((ca, i) => ew2(f, ca, b2.c[i])), 'bool');
}

function map1(a, f) { const A = toT(a); return new T(A.c.map((c) => ew1(f, c)), A.k); }

// ------------------------------------------------------------------------------------------------- constructors ---

function flat(args) {
    const out = [];
    for (const a of args) {
        if (a === undefined) continue;
        const t = toT(a);
        for (const c of t.c) out.push(t.k === 'bool' ? c : c);
    }
    return out;
}
function vecN(n, args) {
    const c = flat(args);
    if (c.length === 0) return new T(new Array(n).fill(0), 'float');
    if (c.length === 1) return new T(new Array(n).fill(c[0]), 'float');
    if (c.length !== n) throw new Error(`tsl shim: vec${n} from ${c.length} components`);
    return new T(c, 'float');
}
export const vec2 = (...a) => vecN(2, a);
export const vec3 = (...a) => vecN(3, a);
export const vec4 = (...a) => vecN(4, a);
export const ivec2 = (...a) => vecN(2, a);
export const float = (v) => {
    if (v instanceof T) return new T(v.c.slice(), 'float');
    return toT(Number(v));
};
export const int = (v) => {
    const t = toT(v);
    return new T(t.c.map((c) => ew1(Math.trunc, c)), 'float');
};
export const uint = (v) => {
    if (typeof v === 'number') return new T([v >>> 0], 'uint');
    const t = toT(v);
    if (t.k === 'uint') return t;
    // WGSL u32(f32): truncation toward zero, saturating at the type's range
    return new T(t.c.map((c) => ew1((x) => Math.min(4294967295, Math.max(0, Math.trunc(x))) >>> 0, c)), 'uint');
};
export const bool = (v) => { const t = toT(v); return new T(t.c.slice(), 'bool'); };
export const uniform = (v) => new U(v);

// ---------------------------------------------------------------------------------------------------- functions ---

export const floor = (a) => toT(a).floor();
export const ceil = (a) => toT(a).ceil();
export const fract = (a) => toT(a).fract();
export const abs = (a) => toT(a).abs();
export const sign = (a) => toT(a).sign();
export const sin = (a) => toT(a).sin();
export const cos = (a) => toT(a).cos();
export const exp = (a) => toT(a).exp();
export const log = (a) => toT(a).log();
export const sqrt = (a) => toT(a).sqrt();
export const negate = (a) => toT(a).negate();
export const oneMinus = (a) => toT(a).oneMinus();
export const reciprocal = (a) => toT(a).reciprocal();
export const max = (a, b) => toT(a).max(b);
export const min = (a, b) => toT(a).min(b);
export const pow = (a, b) => toT(a).pow(b);
export const clamp = (x, lo = 0, hi = 1) => toT(x).max(lo).min(hi);
export const saturate = (x) => clamp(x, 0, 1);
// WGSL mix: e1 * (1 - e3) + e2 * e3
export const mix = (a, b, t) => {
    const A = toT(a), B = toT(b), Tt = toT(t);
    const n = Math.max(A.n, B.n, Tt.n);
    const a2 = bcast(A, n), b2 = bcast(B, n), t2 = bcast(Tt, n);
    return new T(a2.c.map((ca, i) => ew3((x, y, s) => x * (1 - s) + y * s, ca, b2.c[i], t2.c[i])), 'float');
};
export const smoothstep = (e0, e1, x) => {
    const X = toT(x), E0 = toT(e0), E1 = toT(e1);
    const n = Math.max(X.n, E0.n, E1.n);
    const x2 = bcast(X, n), a2 = bcast(E0, n), b2 = bcast(E1, n);
    return new T(x2.c.map((cx, i) => ew3((v, lo, hi) => {
        const t = Math.min(Math.max((v - lo) / (hi - lo), 0), 1);
        return t * t * (3 - 2 * t);
    }, cx, a2.c[i], b2.c[i])), 'float');
};
export const step = (edge, x) => float(toT(x).greaterThanEqual(edge));
export const select = (c, a, b) => {
    const C = toT(c), A = toT(a), B = toT(b);
    const n = Math.max(A.n, B.n);
    const a2 = bcast(A, n), b2 = bcast(B, n);
    const k = A.k === 'uint' && B.k === 'uint' ? 'uint' : 'float';
    return new T(a2.c.map((ca, i) => ew3((cc, x, y) => (cc ? x : y), C.n === n ? C.c[i] : C.c[0], ca, b2.c[i])), k);
};
export const dot = (a, b) => {
    const A = toT(a), B = toT(b);
    let acc = 0;
    for (let i = 0; i < A.n; i++) acc = ew2((x, y) => x + y, acc, ew2((x, y) => x * y, A.c[i], B.c[i]));
    return new T([acc], 'float');
};
export const length = (a) => dot(a, a).sqrt();
export const normalize = (a) => { const A = toT(a); return A.div(length(A)); };
export const distance = (a, b) => length(toT(a).sub(b));
export const atan = (y, x) => {
    if (x === undefined) return map1(y, Math.atan);
    const Y = toT(y), X = toT(x);
    return new T([ew2(Math.atan2, Y.c[0], X.c[0])], 'float');
};
export const atan2 = (y, x) => atan(y, x);

function quadDeriv(c, axis) {
    if (!isArr(c)) return 0;
    const o = new Float64Array(N);
    for (let r = 0; r < GH; r++) {
        for (let q = 0; q < GW; q++) {
            const qx = q & ~1, qy = r & ~1;
            let v;
            if (DMODE === 'coarse') {
                v = axis === 0 ? c[qy * GW + Math.min(qx + 1, GW - 1)] - c[qy * GW + qx]
                    : c[Math.min(qy + 1, GH - 1) * GW + qx] - c[qy * GW + qx];
            } else if (DMODE === 'fine') {
                v = axis === 0 ? c[r * GW + Math.min(qx + 1, GW - 1)] - c[r * GW + qx]
                    : c[Math.min(qy + 1, GH - 1) * GW + q] - c[qy * GW + q];
            } else {                                     // central, clamped at the grid edge
                if (axis === 0) {
                    const a = Math.max(q - 1, 0), b = Math.min(q + 1, GW - 1);
                    v = (c[r * GW + b] - c[r * GW + a]) / Math.max(b - a, 1);
                } else {
                    const a = Math.max(r - 1, 0), b = Math.min(r + 1, GH - 1);
                    v = (c[b * GW + q] - c[a * GW + q]) / Math.max(b - a, 1);
                }
            }
            o[r * GW + q] = v;
        }
    }
    return o;
}
export const dFdx = (a) => { const A = toT(a); return new T(A.c.map((c) => quadDeriv(c, 0)), 'float'); };
export const dFdy = (a) => { const A = toT(a); return new T(A.c.map((c) => quadDeriv(c, 1)), 'float'); };

/** Fn: the body runs immediately on the arguments, as TSL runs it at build time. */
export const Fn = (body) => {
    const call = (...args) => {
        if (args.length === 1 && args[0] && args[0].constructor === Object) return body(args[0]);
        return body(args.map((a) => (typeof a === 'number' ? float(a) : a)));
    };
    call.setLayout = () => call;
    return call;
};

export const If = () => { throw new Error('tsl shim: If() is not used on the field path; add masked assignment first'); };
export const Loop = () => { throw new Error('tsl shim: Loop() is not used on the field path'); };
export const texture = () => { throw new Error('tsl shim: texture() is not part of the field path'); };
export const uv = () => { throw new Error('tsl shim: uv() — pass p explicitly'); };

/** A T's component as a full Float64Array (numbers broadcast). */
export function __lanesOf(t, i = 0) {
    const c = toT(t).c[i];
    if (isArr(c)) return c;
    const o = new Float64Array(N);
    o.fill(c);
    return o;
}
