// The arithmetic backend the terrain port's surfacing is written against (PORT_PLAN.md 3.5): the mask language and
// Blender's shader noise are written once against it, so the material's TSL, the surface bake's compute kernels and the
// tests' plain-number oracle share one source. It began as the ops module of an earlier terrain prototype (Ekigar),
// whose comments below still name that prototype's files; its TSL(tsl) is tslBase(tsl) here, and the exported
// TSL(tsl) is it with the extension that follows.

// An arithmetic BACKEND, so one expression can be a shader and a CPU oracle at once.
//
// WHY THIS EXISTS. The mixed export has to bake the distance surround from the *same*
// layered stack the viewport shows, or the two halves disagree at the boundary and the
// whole feature is pointless. The stack currently lives only as TSL nodes
// (src/materials/layer_stack.js), which means it can only be evaluated on a GPU inside a
// render pass. A second, hand-written CPU copy of the height blend would be exactly the
// "two authored paths" failure mixed.js's own header warns about: it would agree today
// and drift silently the first time either side is touched, and nothing would catch it.
//
// So the maths is written ONCE against this interface and INSTANTIATED twice:
//
//   TSL(tslModule)  ->  three/tsl nodes    ->  compiles to WGSL, runs in the viewport
//   NUM             ->  plain JS numbers   ->  runs under `node --test`, no GPU needed
//
// test/export_kernel_parity.test.js asserts the two instantiations agree, and
// test/export_gpu_parity.mjs asserts the TSL instantiation agrees with the *existing*
// src/materials/layer_stack.js implementation pixel-for-pixel on a real GPU. That second
// check is what makes the factoring a refactor rather than a rewrite: the claim "same
// maths" is measured, not asserted.
//
// DESIGN NOTES
//
// * Function style (`ops.add(a, b)`), not method style (`a.add(b)`), because JS numbers
//   have no `.add`. The TSL backend re-wraps into method calls.
// * Vectors are first class (`v3`, `vmix`, `vmuls`) rather than three scalars, so the TSL
//   instantiation still emits vec3 ops and the proposed patch to layer_stack.js does not
//   de-vectorise the viewport shader. NUM represents a vec3 as a 3-element array.
// * `stepGT(a, b)` instead of a boolean type: TSL comparisons are nodes, JS comparisons
//   are booleans, and there is no need for either — every use here immediately selects
//   between two numbers.
// * A texture SAMPLER is `(u, v) => { r, g, b, a, rgb }`. Both backends can honour that;
//   neither has to expose a vec2 type across the seam.

/** Plain-number backend. Scalars are `number`, vec3 is `[x, y, z]`. */
export const NUM = {
    name: 'num',
    isNum: true,

    f: (x) => (typeof x === 'number' ? x : Number(x)),
    add: (a, b) => a + b,
    sub: (a, b) => a - b,
    mul: (a, b) => a * b,
    div: (a, b) => a / b,
    neg: (a) => -a,
    min: (a, b) => Math.min(a, b),
    max: (a, b) => Math.max(a, b),
    abs: Math.abs,
    sign: Math.sign,
    sqrt: Math.sqrt,
    pow: Math.pow,
    floor: Math.floor,
    clamp: (x, lo, hi) => (x < lo ? lo : x > hi ? hi : x),
    saturate: (x) => (x < 0 ? 0 : x > 1 ? 1 : x),
    mix: (a, b, t) => a + (b - a) * t,
    /** Hermite, matching TSL/WGSL smoothstep including the clamp. */
    smoothstep: (e0, e1, x) => {
        const t = Math.min(1, Math.max(0, (x - e0) / (e1 - e0 || 1e-30)));
        return t * t * (3 - 2 * t);
    },
    /** 1 when a > b, else 0. Replaces a boolean type across the seam. */
    stepGT: (a, b) => (a > b ? 1 : 0),

    v3: (x, y, z) => [x, y, z],
    vx: (v) => v[0],
    vy: (v) => v[1],
    vz: (v) => v[2],
    vadd: (a, b) => [a[0] + b[0], a[1] + b[1], a[2] + b[2]],
    vsub: (a, b) => [a[0] - b[0], a[1] - b[1], a[2] - b[2]],
    /** Component-wise vec3 * vec3. */
    vmulv: (a, b) => [a[0] * b[0], a[1] * b[1], a[2] * b[2]],
    /** vec3 * scalar. */
    vmuls: (a, s) => [a[0] * s, a[1] * s, a[2] * s],
    vmix: (a, b, t) => [a[0] + (b[0] - a[0]) * t, a[1] + (b[1] - a[1]) * t, a[2] + (b[2] - a[2]) * t],
    vnormalize: (a) => {
        const l = Math.hypot(a[0], a[1], a[2]) || 1e-30;
        return [a[0] / l, a[1] / l, a[2] / l];
    },
    vdot: (a, b) => a[0] * b[0] + a[1] * b[1] + a[2] * b[2],
};

/**
 * TSL backend.
 *
 * `tsl` is the imported `three/tsl` module, passed in rather than imported so this file
 * stays loadable in a runtime with no three (and so `node --test` never pulls the GPU
 * backend in just to run the CPU oracle).
 */
function tslBase(tsl) {
    const {
        float, vec3, add, sub, mul, div, min, max, abs, sign, sqrt, pow, floor,
        clamp, saturate, mix, smoothstep, normalize, dot,
    } = tsl;
    // TSL accepts numbers in most positions, but not all — `float()` on every literal is
    // the only spelling that is uniformly safe, and it is free (it folds at compile time).
    const F = (x) => (typeof x === 'number' ? float(x) : x);

    return {
        name: 'tsl',
        isNum: false,

        f: F,
        add: (a, b) => add(F(a), F(b)),
        sub: (a, b) => sub(F(a), F(b)),
        mul: (a, b) => mul(F(a), F(b)),
        div: (a, b) => div(F(a), F(b)),
        neg: (a) => F(a).negate(),
        min: (a, b) => min(F(a), F(b)),
        max: (a, b) => max(F(a), F(b)),
        abs: (a) => abs(F(a)),
        sign: (a) => sign(F(a)),
        sqrt: (a) => sqrt(F(a)),
        pow: (a, b) => pow(F(a), F(b)),
        floor: (a) => floor(F(a)),
        clamp: (x, lo, hi) => clamp(F(x), F(lo), F(hi)),
        saturate: (x) => saturate(F(x)),
        mix: (a, b, t) => mix(F(a), F(b), F(t)),
        smoothstep: (e0, e1, x) => smoothstep(F(e0), F(e1), F(x)),
        stepGT: (a, b) => F(a).greaterThan(F(b)).select(float(1), float(0)),

        v3: (x, y, z) => vec3(F(x), F(y), F(z)),
        vx: (v) => v.x,
        vy: (v) => v.y,
        vz: (v) => v.z,
        vadd: (a, b) => a.add(b),
        vsub: (a, b) => a.sub(b),
        vmulv: (a, b) => a.mul(b),
        vmuls: (a, s) => a.mul(F(s)),
        vmix: (a, b, t) => mix(a, b, F(t)),
        vnormalize: (a) => normalize(a),
        vdot: (a, b) => dot(a, b),
    };
}

/**
 * Bilinear sampler over a decoded RGBA byte plane, for the NUM backend.
 *
 * Repeat wrap and bilinear filter, to match the DataArrayTexture setup in
 * texture_arrays.js (RepeatWrapping + LinearFilter). `srgb` decodes the sRGB transfer
 * function, which is what three's WGSL backend does per-sample from
 * `texture.colorSpace = SRGBColorSpace` — so the albedo array must be decoded here too or
 * the CPU oracle compares linear GPU values against encoded CPU ones and reports a
 * fictional error of ~0.2 in mid grey.
 *
 * @param plane  Uint8Array, size*size*4, one material layer
 * @param size   square edge in texels
 */
export function planeSampler(plane, size, { srgb = false } = {}) {
    const dec = srgb ? SRGB_TO_LINEAR : IDENTITY_255;
    return (u, v) => {
        // Repeat wrap in continuous space first, then the half-texel shift, so a uv of
        // exactly 1.0 lands on texel 0 rather than clamping to size-1.
        const fu = (u - Math.floor(u)) * size - 0.5;
        const fv = (v - Math.floor(v)) * size - 0.5;
        const x0 = Math.floor(fu), y0 = Math.floor(fv);
        const tx = fu - x0, ty = fv - y0;
        const wrap = (i) => ((i % size) + size) % size;
        const x1 = wrap(x0 + 1), y1 = wrap(y0 + 1);
        const xa = wrap(x0), ya = wrap(y0);
        const o00 = (ya * size + xa) * 4, o10 = (ya * size + x1) * 4;
        const o01 = (y1 * size + xa) * 4, o11 = (y1 * size + x1) * 4;
        const out = [0, 0, 0, 0];
        for (let c = 0; c < 4; c++) {
            // Alpha is never transfer-encoded, in sRGB or anywhere else.
            const d = c === 3 ? IDENTITY_255 : dec;
            const a = d[plane[o00 + c]], b = d[plane[o10 + c]];
            const e = d[plane[o01 + c]], g = d[plane[o11 + c]];
            out[c] = (a + (b - a) * tx) + ((e + (g - e) * tx) - (a + (b - a) * tx)) * ty;
        }
        return { r: out[0], g: out[1], b: out[2], a: out[3], rgb: [out[0], out[1], out[2]] };
    };
}

const IDENTITY_255 = (() => {
    const t = new Float64Array(256);
    for (let i = 0; i < 256; i++) t[i] = i / 255;
    return t;
})();

/** The real sRGB EOTF, not pow(2.2). The piecewise toe matters below ~0.04. */
const SRGB_TO_LINEAR = (() => {
    const t = new Float64Array(256);
    for (let i = 0; i < 256; i++) {
        const c = i / 255;
        t[i] = c <= 0.04045 ? c / 12.92 : ((c + 0.055) / 1.055) ** 2.4;
    }
    return t;
})();

export { SRGB_TO_LINEAR };

/** The sRGB OETF. Used when writing an 8-bit albedo PNG that declares itself sRGB. */
export function linearToSRGB(v) {
    const c = v < 0 ? 0 : v > 1 ? 1 : v;
    return c <= 0.0031308 ? c * 12.92 : 1.055 * c ** (1 / 2.4) - 0.055;
}


// ============================================================== the port's extension (PORT_PLAN.md 3.5) ===
//
// What Blender's shader noise (surface/noise.js) and the mask language (surface/mask_expr.js) need beyond the layer
// stack's maths, in every backend:
//   - more float maths: exp exp2 log log2 sin cos atan atan2 trunc fract round (halves to even, as WGSL's) degrees
//     radians tanh, fmod(a, b) = a - b trunc(a / b) (C's)
//   - booleans: lt le gt ge eq ne (comparisons), and or not, select(c, a, b) (a where c, else b)
//   - integers, as WGSL's (wrapping arithmetic): u(x) and i(x) make a u32 or i32 (a literal, or a value cast: u() of an
//     i32 and i() of a u32 reinterpret the bits); utof itof (to float), ftoi (float to i32, truncated); uadd usub umul
//     uxor uand uor ushl ushr (logical), iadd isub imul ishr (arithmetic) iand ixor; ult ule ueq une ilt ige ieq for
//     integer comparisons
//   - vectors: v2 v4 vw, vabs vfloor vmin vmax vclamp vselect vlength vdiv vsqrt
//   - fn(name, params, ret, body): a function written once: NUM and NUM32 call body directly; TSL makes a Fn with a
//     layout (one WGSL function, not a copy of the graph per call); WGSL writes one `fn` into its module. params:
//     [[name, type], ...], types 'float' 'uint' 'int' 'bool' 'vec2' 'vec3' 'vec4'; body(ops, ...args) returns the
//     value (a list of values for ret ['float', 'float', ...] in NUM, NUM32 and WGSL, as a struct-free multi-return
//     the TSL backend does not offer: callers use it only where every backend can)
//   - vr(type, init) -> { get(), set(v) }: a mutable value; loop(start, end, body(i)): i from start to end - 1 (an i32;
//     end a number or a backend's int, a uniform), body sets values with set()
//   - WGSL only: ext(type, name, ...args), a call of a function the kernel's own text defines (surface/far_colour.js's
//     strata column and hue shift); module(), body(), code(v), reset() give the text
// Backends: NUM (doubles), NUM32 (every float result rounded to float32 with Math.fround: the oracle of float32 code,
// step for step, as numpy float32 evaluates it), TSL(tsl) (three/tsl nodes), WGSL() (WGSL text for the compute kernels
// core/gpu.js runs: each value names a `let` in the current block).

const fr = Math.fround;

// halves to even, as WGSL's round() and numpy's rint
function rintEven(x) {
    const r = Math.round(x);
    return (Math.abs(x % 1) === 0.5 && r % 2 !== 0) ? r - 1 : r;
}

// i32(f32) in WGSL: truncation toward zero, saturated at the range
function ftoi32(x) {
    if (Number.isNaN(x)) return 0;
    const t = Math.trunc(x);
    return t >= 2147483647 ? 2147483647 : t <= -2147483648 ? -2147483648 : t;
}

function numExtension(round) {
    const R = round;                                         // identity (NUM) or Math.fround (NUM32)
    const tanh = (x) => {
        if (x > 20) return 1;
        if (x < -20) return -1;
        const e = Math.exp(2 * x);
        return (e - 1) / (e + 1);
    };
    return {
        exp: (a) => R(Math.exp(a)), exp2: (a) => R(2 ** a), log: (a) => R(Math.log(a)), log2: (a) => R(Math.log2(a)),
        sin: (a) => R(Math.sin(a)), cos: (a) => R(Math.cos(a)), atan: (a) => R(Math.atan(a)),
        atan2: (y, x) => R(Math.atan2(y, x)), trunc: Math.trunc, fract: (a) => R(a - Math.floor(a)), round: rintEven,
        degrees: (a) => R(a * (180 / Math.PI)), radians: (a) => R(a * (Math.PI / 180)), tanh: (a) => R(tanh(a)),
        fmod: (a, b) => R(a - R(b * Math.trunc(R(a / b)))),
        lt: (a, b) => a < b, le: (a, b) => a <= b, gt: (a, b) => a > b, ge: (a, b) => a >= b, eq: (a, b) => a === b,
        ne: (a, b) => a !== b, and: (a, b) => a && b, or: (a, b) => a || b, not: (a) => !a,
        select: (c, a, b) => (c ? a : b),
        u: (x) => (typeof x === 'boolean' ? Number(x) : Number(x)) >>> 0, i: (x) => Number(x) | 0,
        utof: (x) => R(x), itof: (x) => R(x), ftoi: ftoi32, itou: (x) => x >>> 0, utoi: (x) => x | 0,
        uadd: (a, b) => (a + b) >>> 0, usub: (a, b) => (a - b) >>> 0, umul: (a, b) => Math.imul(a, b) >>> 0,
        uxor: (a, b) => (a ^ b) >>> 0, uand: (a, b) => (a & b) >>> 0, uor: (a, b) => (a | b) >>> 0,
        ushl: (a, k) => (a << k) >>> 0, ushr: (a, k) => a >>> k,
        iadd: (a, b) => (a + b) | 0, isub: (a, b) => (a - b) | 0, imul: (a, b) => Math.imul(a, b), ishr: (a, k) => a >> k,
        iand: (a, b) => a & b, ixor: (a, b) => a ^ b,
        ult: (a, b) => a < b, ule: (a, b) => a <= b, ueq: (a, b) => a === b, une: (a, b) => a !== b,
        ilt: (a, b) => a < b, ige: (a, b) => a >= b, ieq: (a, b) => a === b,
        v2: (x, y) => [x, y], v4: (x, y, z, w) => [x, y, z, w], vw: (v) => v[3],
        vabs: (a) => a.map(Math.abs), vfloor: (a) => a.map(Math.floor), vmin: (a, b) => a.map((x, k) => Math.min(x, b[k] ?? b)),
        vmax: (a, b) => a.map((x, k) => Math.max(x, b[k] ?? b)),
        vclamp: (a, lo, hi) => a.map((x, k) => Math.min(Math.max(x, lo[k] ?? lo), hi[k] ?? hi)),
        vselect: (c, a, b) => (c ? a : b),
        vlength: (a) => R(Math.sqrt(a.reduce((s, x) => R(s + R(x * x)), 0))),
        vdiv: (a, s) => a.map((x) => R(x / s)), vsqrt: (a) => a.map((x) => R(Math.sqrt(x))),
        fn: (name, params, ret, body) => function (...args) { return body(this, ...args); },
        vr: (_type, init) => ({ v: init, get() { return this.v; }, set(x) { this.v = x; } }),
        loop: (start, end, body) => { for (let k = start; k < end; k++) body(k); },
    };
}

Object.assign(NUM, numExtension((x) => x));
// fn's body gets the backend itself: bind it (a plain function's `this` is the object it is called on)
NUM.fn = (name, params, ret, body) => (...args) => body(NUM, ...args);

/** NUM with every float result rounded to float32: the oracle of float32 code, step for step. */
export const NUM32 = (() => {
    const o = { ...NUM, name: 'num32' };
    const r2 = (fnc) => (a, b) => fr(fnc(a, b));
    Object.assign(o, {
        f: (x) => fr(typeof x === 'number' ? x : Number(x)),
        add: r2((a, b) => a + b), sub: r2((a, b) => a - b), mul: r2((a, b) => a * b), div: r2((a, b) => a / b),
        sqrt: (a) => fr(Math.sqrt(a)), pow: r2(Math.pow),
        mix: (a, b, t) => fr(a + fr(fr(b - a) * t)),
        smoothstep: (e0, e1, x) => {
            const t = Math.min(1, Math.max(0, fr(fr(x - e0) / fr(e1 - e0 || 1e-30))));
            return fr(fr(t * t) * fr(3 - fr(2 * t)));
        },
        clamp: (x, lo, hi) => (x < lo ? lo : x > hi ? hi : x),
        vadd: (a, b) => a.map((x, k) => fr(x + b[k])), vsub: (a, b) => a.map((x, k) => fr(x - b[k])),
        vmulv: (a, b) => a.map((x, k) => fr(x * b[k])), vmuls: (a, s) => a.map((x) => fr(x * s)),
        vmix: (a, b, t) => a.map((x, k) => fr(x + fr(fr(b[k] - x) * t))),
        vdot: (a, b) => a.reduce((s, x, k) => fr(s + fr(x * b[k])), 0),
    }, numExtension(fr));
    o.fn = (name, params, ret, body) => (...args) => body(o, ...args);
    return o;
})();

/** The TSL backend with the extension: `tsl` the imported three/tsl module. */
export function TSL(tsl) {
    const base = tslBase(tsl);
    const { float, uint, int, bool, vec2, vec4, select, Fn, Loop, exp, exp2, log, log2, sin, cos, atan, trunc, fract,
        round, degrees, radians, abs, floor, min, max, clamp, length, sqrt, tanh } = tsl;
    const F = base.f;
    const U = (x) => (typeof x === 'number' ? uint(x >>> 0) : uint(x));
    const I = (x) => (typeof x === 'number' ? int(x | 0) : int(x));
    const ops = {
        ...base,
        exp: (a) => exp(F(a)), exp2: (a) => exp2(F(a)), log: (a) => log(F(a)), log2: (a) => log2(F(a)),
        sin: (a) => sin(F(a)), cos: (a) => cos(F(a)), atan: (a) => atan(F(a)), atan2: (y, x) => atan(F(y), F(x)),
        trunc: (a) => trunc(F(a)), fract: (a) => fract(F(a)), round: (a) => round(F(a)), degrees: (a) => degrees(F(a)),
        radians: (a) => radians(F(a)), tanh: (a) => tanh(F(a)),
        fmod: (a, b) => F(a).sub(F(b).mul(trunc(F(a).div(F(b))))),
        lt: (a, b) => F(a).lessThan(F(b)), le: (a, b) => F(a).lessThanEqual(F(b)), gt: (a, b) => F(a).greaterThan(F(b)),
        ge: (a, b) => F(a).greaterThanEqual(F(b)), eq: (a, b) => F(a).equal(F(b)), ne: (a, b) => F(a).notEqual(F(b)),
        and: (a, b) => a.and(b), or: (a, b) => a.or(b), not: (a) => a.not(),
        select: (c, a, b) => select(c, typeof a === 'number' ? float(a) : a, typeof b === 'number' ? float(b) : b),
        u: U, i: I, utof: (x) => float(x), itof: (x) => float(x), ftoi: (x) => int(F(x)), itou: (x) => uint(x),
        utoi: (x) => int(x),
        uadd: (a, b) => U(a).add(U(b)), usub: (a, b) => U(a).sub(U(b)), umul: (a, b) => U(a).mul(U(b)),
        uxor: (a, b) => U(a).bitXor(U(b)), uand: (a, b) => U(a).bitAnd(U(b)), uor: (a, b) => U(a).bitOr(U(b)),
        ushl: (a, k) => U(a).shiftLeft(uint(k)), ushr: (a, k) => U(a).shiftRight(uint(k)),
        iadd: (a, b) => I(a).add(I(b)), isub: (a, b) => I(a).sub(I(b)), imul: (a, b) => I(a).mul(I(b)),
        ishr: (a, k) => I(a).shiftRight(uint(k)), iand: (a, b) => I(a).bitAnd(I(b)), ixor: (a, b) => I(a).bitXor(I(b)),
        ult: (a, b) => U(a).lessThan(U(b)), ule: (a, b) => U(a).lessThanEqual(U(b)), ueq: (a, b) => U(a).equal(U(b)),
        une: (a, b) => U(a).notEqual(U(b)), ilt: (a, b) => I(a).lessThan(I(b)), ige: (a, b) => I(a).greaterThanEqual(I(b)),
        ieq: (a, b) => I(a).equal(I(b)),
        v2: (x, y) => vec2(F(x), F(y)), v4: (x, y, z, w) => vec4(F(x), F(y), F(z), F(w)), vw: (v) => v.w,
        vabs: (a) => abs(a), vfloor: (a) => floor(a), vmin: (a, b) => min(a, b), vmax: (a, b) => max(a, b),
        vclamp: (a, lo, hi) => clamp(a, lo, hi), vselect: (c, a, b) => select(c, a, b), vlength: (a) => length(a),
        vdiv: (a, s) => a.div(F(s)), vsqrt: (a) => sqrt(a),
        vr: (_type, init) => {
            const v = (typeof init === 'number' ? float(init) : typeof init === 'boolean' ? bool(init) : init).toVar();
            return { get: () => v, set: (x) => v.assign(x) };
        },
        loop: (start, end, body) => {
            Loop({ start: I(start), end: typeof end === 'number' ? int(end) : end, type: 'int', condition: '<' },
                ({ i }) => body(i));
        },
    };
    const TYPES = { float: 'float', uint: 'uint', int: 'int', bool: 'bool', vec2: 'vec2', vec3: 'vec3', vec4: 'vec4' };
    ops.fn = (name, params, ret, body) => Fn((args) => body(ops, ...args)).setLayout({ name, type: TYPES[ret],
        inputs: params.map(([n, t]) => ({ name: n, type: TYPES[t] })) });
    return ops;
}

/** The WGSL text backend: a fresh one per kernel (it keeps the kernel's functions and statements). module() is the
 * functions' WGSL, body() the statements of the outermost block, and a value's .code its expression (a let's name or
 * a literal). Literals are written so WGSL reads exactly the float32 of the double given (shortest round-trip
 * decimals). */
export function WGSL() {
    const T = { float: 'f32', f32: 'f32', uint: 'u32', u32: 'u32', int: 'i32', i32: 'i32', bool: 'bool', vec2: 'vec2<f32>',
        vec3: 'vec3<f32>', vec4: 'vec4<f32>' };
    const fns = [];
    const defined = new Map();
    let block = [];
    let id = 0;
    const val = (code, type) => ({ code, type, wgsl: true });
    const flit = (x) => {
        if (x === Infinity) return '3.4e38';
        if (x === -Infinity) return '-3.4e38';
        let s = String(fr(x) === x ? x : fr(x));
        s = String(Number(s));
        if (!/[.eE]/.test(s)) s += '.0';
        return s;
    };
    const F = (x) => (typeof x === 'number' ? val(flit(x), 'f32') : typeof x === 'boolean' ? val(String(x), 'bool') : x);
    const U = (x) => (typeof x === 'number' ? val(`${x >>> 0}u`, 'u32') : x.type === 'u32' ? x : emit('u32', `bitcast<u32>(${x.code})`));
    const I = (x) => (typeof x === 'number' ? val(`${x | 0}i`, 'i32') : x.type === 'i32' ? x : emit('i32', `bitcast<i32>(${x.code})`));
    const emit = (type, expr) => {
        const n = `t${id++}`;
        block.push(`let ${n} = ${expr};`);
        return val(n, type);
    };
    const bin = (type, op) => (a, b) => emit(type, `(${F(a).code} ${op} ${F(b).code})`);
    const call = (type, f) => (...a) => emit(type, `${f}(${a.map((x) => F(x).code).join(', ')})`);
    const ty = (a) => F(a).type;
    const vecOf = (t) => t.startsWith('vec');
    const splat = (type, b) => (F(b).type === type ? F(b).code : `${type}(${F(b).code})`);
    const ops = {
        name: 'wgsl', isNum: false, f: F,
        add: (a, b) => emit(vecOf(ty(a)) ? ty(a) : ty(b), `(${F(a).code} + ${F(b).code})`),
        sub: (a, b) => emit(vecOf(ty(a)) ? ty(a) : ty(b), `(${F(a).code} - ${F(b).code})`),
        mul: (a, b) => emit(vecOf(ty(a)) ? ty(a) : ty(b), `(${F(a).code} * ${F(b).code})`),
        div: (a, b) => emit(vecOf(ty(a)) ? ty(a) : ty(b), `(${F(a).code} / ${F(b).code})`),
        neg: (a) => emit(ty(a), `(-${F(a).code})`),
        min: (a, b) => emit(ty(a), `min(${F(a).code}, ${F(b).code})`), max: (a, b) => emit(ty(a), `max(${F(a).code}, ${F(b).code})`),
        abs: (a) => emit(ty(a), `abs(${F(a).code})`), sign: (a) => emit(ty(a), `sign(${F(a).code})`),
        sqrt: (a) => emit(ty(a), `sqrt(${F(a).code})`), pow: call('f32', 'pow'), floor: (a) => emit(ty(a), `floor(${F(a).code})`),
        clamp: (x, lo, hi) => emit(ty(x), `clamp(${F(x).code}, ${F(lo).code}, ${F(hi).code})`),
        saturate: (x) => emit(ty(x), `saturate(${F(x).code})`),
        mix: (a, b, t) => emit(ty(a), `mix(${F(a).code}, ${F(b).code}, ${F(t).code})`),
        smoothstep: call('f32', 'smoothstep'),
        stepGT: (a, b) => emit('f32', `select(0.0, 1.0, ${F(a).code} > ${F(b).code})`),
        v3: (x, y, z) => emit('vec3<f32>', `vec3<f32>(${F(x).code}, ${F(y).code}, ${F(z).code})`),
        vx: (v) => val(`${v.code}.x`, 'f32'), vy: (v) => val(`${v.code}.y`, 'f32'), vz: (v) => val(`${v.code}.z`, 'f32'),
        vw: (v) => val(`${v.code}.w`, 'f32'),
        vadd: (a, b) => emit(a.type, `(${a.code} + ${b.code})`), vsub: (a, b) => emit(a.type, `(${a.code} - ${b.code})`),
        vmulv: (a, b) => emit(a.type, `(${a.code} * ${b.code})`), vmuls: (a, s) => emit(a.type, `(${a.code} * ${F(s).code})`),
        vmix: (a, b, t) => emit(a.type, `mix(${a.code}, ${b.code}, ${F(t).code})`),
        vnormalize: (a) => emit(a.type, `normalize(${a.code})`), vdot: (a, b) => emit('f32', `dot(${a.code}, ${b.code})`),
        exp: call('f32', 'exp'), exp2: call('f32', 'exp2'), log: call('f32', 'log'), log2: call('f32', 'log2'),
        sin: call('f32', 'sin'), cos: call('f32', 'cos'), atan: call('f32', 'atan'), atan2: call('f32', 'atan2'),
        trunc: (a) => emit(ty(a), `trunc(${F(a).code})`), fract: (a) => emit(ty(a), `fract(${F(a).code})`),
        round: (a) => emit(ty(a), `round(${F(a).code})`), degrees: call('f32', 'degrees'), radians: call('f32', 'radians'),
        tanh: call('f32', 'tanh'),
        fmod: (a, b) => emit('f32', `(${F(a).code} - ${F(b).code} * trunc(${F(a).code} / ${F(b).code}))`),
        lt: bin('bool', '<'), le: bin('bool', '<='), gt: bin('bool', '>'), ge: bin('bool', '>='), eq: bin('bool', '=='),
        ne: bin('bool', '!='), and: (a, b) => emit('bool', `(${a.code} && ${b.code})`),
        or: (a, b) => emit('bool', `(${a.code} || ${b.code})`), not: (a) => emit('bool', `(!${a.code})`),
        select: (c, a, b) => emit(F(a).type, `select(${F(b).code}, ${F(a).code}, ${c.code})`),
        u: U, i: I,
        utof: (x) => emit('f32', `f32(${x.code})`), itof: (x) => emit('f32', `f32(${x.code})`),
        ftoi: (x) => emit('i32', `i32(${F(x).code})`), itou: (x) => U(x), utoi: (x) => I(x),
        uadd: (a, b) => emit('u32', `(${U(a).code} + ${U(b).code})`), usub: (a, b) => emit('u32', `(${U(a).code} - ${U(b).code})`),
        umul: (a, b) => emit('u32', `(${U(a).code} * ${U(b).code})`), uxor: (a, b) => emit('u32', `(${U(a).code} ^ ${U(b).code})`),
        uand: (a, b) => emit('u32', `(${U(a).code} & ${U(b).code})`), uor: (a, b) => emit('u32', `(${U(a).code} | ${U(b).code})`),
        ushl: (a, k) => emit('u32', `(${U(a).code} << ${k}u)`), ushr: (a, k) => emit('u32', `(${U(a).code} >> ${k}u)`),
        iadd: (a, b) => emit('i32', `(${I(a).code} + ${I(b).code})`), isub: (a, b) => emit('i32', `(${I(a).code} - ${I(b).code})`),
        imul: (a, b) => emit('i32', `(${I(a).code} * ${I(b).code})`), ishr: (a, k) => emit('i32', `(${I(a).code} >> ${k}u)`),
        iand: (a, b) => emit('i32', `(${I(a).code} & ${I(b).code})`), ixor: (a, b) => emit('i32', `(${I(a).code} ^ ${I(b).code})`),
        ult: (a, b) => emit('bool', `(${U(a).code} < ${U(b).code})`), ule: (a, b) => emit('bool', `(${U(a).code} <= ${U(b).code})`),
        ueq: (a, b) => emit('bool', `(${U(a).code} == ${U(b).code})`), une: (a, b) => emit('bool', `(${U(a).code} != ${U(b).code})`),
        ilt: (a, b) => emit('bool', `(${I(a).code} < ${I(b).code})`), ige: (a, b) => emit('bool', `(${I(a).code} >= ${I(b).code})`),
        ieq: (a, b) => emit('bool', `(${I(a).code} == ${I(b).code})`),
        v2: (x, y) => emit('vec2<f32>', `vec2<f32>(${F(x).code}, ${F(y).code})`),
        v4: (x, y, z, w) => emit('vec4<f32>', `vec4<f32>(${F(x).code}, ${F(y).code}, ${F(z).code}, ${F(w).code})`),
        vabs: (a) => emit(a.type, `abs(${a.code})`), vfloor: (a) => emit(a.type, `floor(${a.code})`),
        // WGSL's min, max and clamp take one type: a scalar bound is splat to the vector's
        vmin: (a, b) => emit(a.type, `min(${a.code}, ${splat(a.type, b)})`), vmax: (a, b) => emit(a.type, `max(${a.code}, ${splat(a.type, b)})`),
        vclamp: (a, lo, hi) => emit(a.type, `clamp(${a.code}, ${splat(a.type, lo)}, ${splat(a.type, hi)})`),
        vselect: (c, a, b) => emit(a.type, `select(${b.code}, ${a.code}, ${c.code})`),
        vlength: (a) => emit('f32', `length(${a.code})`), vdiv: (a, s) => emit(a.type, `(${a.code} / ${F(s).code})`),
        vsqrt: (a) => emit(a.type, `sqrt(${a.code})`),
        vr: (type, init) => {
            const n = `v${id++}`;
            const t = T[type] ?? type;
            const i0 = typeof init === 'number' ? (t === 'u32' ? `${init >>> 0}u` : t === 'i32' ? `${init | 0}i` : flit(init))
                : typeof init === 'boolean' ? String(init) : init.code;
            block.push(`var ${n}: ${t} = ${i0};`);
            return { get: () => val(n, t), set: (x) => block.push(`${n} = ${(typeof x === 'number' ? F(x) : x).code};`) };
        },
        loop: (start, end, body) => {
            const n = `li${id++}`;               // not i<n>: i8, i16, i32 and i64 are WGSL's words
            const e = typeof end === 'number' ? `${end | 0}i` : I(end).code;
            block.push(`for (var ${n}: i32 = ${typeof start === 'number' ? `${start | 0}i` : start.code}; ${n} < ${e}; ${n}++) {`);
            const outer = block;
            block = [];
            body(val(n, 'i32'));
            const inner = block;
            block = outer;
            block.push(...inner.map((s) => '  ' + s), '}');
        },
        fn: (name, params, ret, body) => {
            const call1 = (...args) => {
                if (!defined.has(name)) {
                    const outer = block;
                    block = [];
                    const r = body(ops, ...params.map(([n, t]) => val(n, T[t])));
                    const rets = Array.isArray(ret) ? ret : [ret];
                    const rs = Array.isArray(r) ? r : [r];
                    let text;
                    if (rets.length === 1) {
                        text = `fn ${name}(${params.map(([n, t]) => `${n}: ${T[t]}`).join(', ')}) -> ${T[rets[0]]} {\n` +
                            block.map((s) => '  ' + s).join('\n') + `\n  return ${F(rs[0]).code};\n}`;
                    } else {
                        // several results: a struct of them
                        const sname = `${name}_out`;
                        fns.push(`struct ${sname} { ${rets.map((t, k) => `r${k}: ${T[t]}`).join(', ')} }`);
                        text = `fn ${name}(${params.map(([n, t]) => `${n}: ${T[t]}`).join(', ')}) -> ${sname} {\n` +
                            block.map((s) => '  ' + s).join('\n') + `\n  return ${sname}(${rs.map((x) => F(x).code).join(', ')});\n}`;
                    }
                    block = outer;
                    fns.push(text);
                    defined.set(name, rets);
                }
                const rets = defined.get(name);
                const r = emit(rets.length === 1 ? T[rets[0]] : `${name}_out`, `${name}(${args.map((a, k) => {
                    const t = params[k][1];
                    if (t === 'uint') return U(a).code;
                    if (t === 'int') return I(a).code;
                    return F(a).code;
                }).join(', ')})`);
                if (rets.length === 1) return r;
                return rets.map((t, k) => val(`${r.code}.r${k}`, T[t]));
            };
            return call1;
        },
        /** A call of a WGSL function the kernel itself defines (its own text, outside these ops): a `let` of `type`. */
        ext: (type, name, ...args) => emit(T[type] ?? type, `${name}(${args.map((x) => F(x).code).join(', ')})`),
        /** The functions written so far (WGSL). */
        module: () => fns.join('\n\n'),
        /** The statements of the outermost block, indented. */
        body: (indent = '  ') => block.map((s) => indent + s).join('\n'),
        /** A value as a WGSL expression (a let's name or a literal). */
        code: (v) => F(v).code,
        /** Start a new outermost block (a kernel's body), keeping the functions. */
        reset: () => { block = []; },
    };
    return ops;
}
