// Port of blender/eidoblend/terrain/surface/expr_glsl.py at d67f19e.
//
// The mask language (build/palettes.js parse trees) compiled into calls on an arithmetic backend (build/ops.js), for
// the palette bake's kernels and the material (SURFACING_DESIGN.md 2.1, 2.3; PORT_PLAN.md 3.5). Its cross-edition
// oracle is palettes.py's evaluate: on noise-free expressions the two agree to float32; noise(), fbm() and cells()
// compile to Blender's own noise (surface/noise.js) at the coordinates the material's nodes read (Blender's
// build/surfacing.py _Compiler), so a term evaluated in the bake equals the shader's.
//
//     import { Compiler } from './surface/mask_expr.js';
//     import * as ops from '../build/ops.js';
//     const W = ops.WGSL();
//     const c = new Compiler({ ops: W, read: (name) => ..., pos: [x, y, z], constants: pal.constants, texelM: 8.0 });
//     const v = c.expr('smoothstep(30, 45, slope + 5*(fbm(80, 3) - 0.5))');     // a value of the backend
//     c.names                                  // the maps it reads (read() was asked for each)
//
// pos: the position the noise reads (world x, y and the ground's z), values of the backend; read(name): a map's value
// (a backend value; a number for NUM / NUM32). texelM: the footprint the bake samples at: a noise term's deviation
// from its mean is scaled by smoothstep(1, 4, scale / texel) and fbm's detail dropped to log2(scale / (2 texel)), so a
// term finer than a texel reads its mean instead of aliasing (the material's footprint rule, SURFACING_DESIGN.md
// 3.2). texelM null keeps every term at full strength (the parity tests); texelM 'uniform' computes both from `foot`
// (a backend value, metres: a uniform), so one source serves every level. flat: noise(), fbm() and cells() read 0.5,
// palettes.py evaluate(flat=True).
//
// Where this differs from expr_glsl.py, and why:
//   - expr_glsl.py writes GLSL text (helpers xg_smooth, xg_div, xg_pow, xg_fade, xg_detail; the noise terms declared
//     once as floats, the expressions after them); here the same arithmetic is calls on a backend (build/ops.js), so
//     one source is the WGSL of the bake's kernels (ops.WGSL), the material's TSL (ops.TSL) and the float32 oracle
//     (ops.NUM32). The helpers are the backend's operations in the helpers' order; a noise term is computed once per
//     Compiler (its key: function, scale, seed), as expr_glsl declares it once.
//   - Literals reach every backend as the float32 of the double (expr_glsl.py's _f writes repr(v), which GLSL reads
//     as that float32).

import * as P from '../build/palettes.js';
import { noise } from './noise.js';

/** Expressions -> values of a backend over read(name) and pos (module doc). */
export class Compiler {
    constructor({ ops, read, pos = null, constants = null, noise3 = true, texelM = null, flat = false, foot = null }) {
        this.o = ops;
        this.read = read;
        this.pos = pos;
        this.consts = { ...P.CONSTANTS, ...(constants ?? {}) };
        this.noise3 = Boolean(noise3);
        this.texel = texelM;
        this.foot = foot;
        this.flat = Boolean(flat);
        this.names = new Set();
        this.noises = new Map();                         // key -> the term's value
        this.N = null;
    }

    expr(src) {
        const t = Array.isArray(src) ? src : P.parse(src);
        return this._c(t);
    }

    /** Forget the noise terms computed so far (a WGSL backend's block ended: its lets are out of scope). */
    resetBlock() { this.noises.clear(); }

    _c(t) {
        const o = this.o;
        const k = t[0];
        if (k === 'num') return o.f(t[1]);
        if (k === 'const') return o.f(Number(t[1] in this.consts ? this.consts[t[1]] : P.CONSTANTS[t[1]]));
        if (k === 'mask') {
            this.names.add(t[1]);
            return this.read(t[1]);
        }
        if (k === 'neg') return o.neg(this._c(t[1]));
        if (k === 'op') {
            const a = this._c(t[2]), b = this._c(t[3]);
            if (t[1] === '/') return this._div(a, b);
            if (t[1] === '+') return o.add(a, b);
            if (t[1] === '-') return o.sub(a, b);
            return o.mul(a, b);
        }
        const [, f, args] = t;
        if (f === 'noise' || f === 'fbm' || f === 'cells') {
            if (this.flat) return o.f(0.5);
            const seed = args.length > 1 ? Math.trunc(args[1][1]) : 0;
            const scale = Number(args[0][1]);
            if (f === 'cells') return this._cells(scale, seed, args.length > 2 ? Number(args[2][1]) : 0.0);
            return this._noise(f, scale, seed);
        }
        const v = args.map((a) => this._c(a));
        if (f === 'smoothstep') return this._smooth(v[0], v[1], v[2]);
        if (f === 'min' || f === 'max') {
            let out = v[0];
            for (const e of v.slice(1)) out = o[f](out, e);
            return out;
        }
        if (f === 'clamp') return o.clamp(v[0], v[1], v[2]);
        if (f === 'abs') return o.abs(v[0]);
        if (f === 'pow') return o.pow(o.max(v[0], 0.0), v[1]);
        if (f === 'mix') return o.add(v[0], o.mul(o.sub(v[1], v[0]), v[2]));
        throw new P.ExprError(f);
    }

    // xg_smooth: if (e1 == e0) return x >= e0 ? 1 : 0; t = clamp((x - e0) / (e1 - e0), 0, 1); t t (3 - 2 t)
    _smooth(e0, e1, x) {
        const o = this.o;
        const t = o.clamp(o.div(o.sub(x, e0), o.sub(e1, e0)), 0.0, 1.0);
        const s = o.mul(o.mul(t, t), o.sub(3.0, o.mul(2.0, t)));
        return o.select(o.eq(e1, e0), o.select(o.ge(x, e0), o.f(1.0), o.f(0.0)), s);
    }

    // xg_div: a / (abs(b) < 1e-12 ? 1e-12 : b)
    _div(a, b) {
        const o = this.o;
        return o.div(a, o.select(o.lt(o.abs(b), 1e-12), o.f(1e-12), b));
    }

    /** The footprint fade of a term of `scale` metres: a number, or a backend value with texelM 'uniform'. */
    _fade(scale) {
        if (this.texel === null || this.texel === undefined) return 1.0;
        const o = this.o;
        if (this.texel === 'uniform') {
            // xg_fade: t = clamp((s / uFoot - 1) / 3, 0, 1); t t (3 - 2 t)
            const t = o.clamp(o.div(o.sub(o.div(o.f(scale), this.foot), 1.0), 3.0), 0.0, 1.0);
            return o.mul(o.mul(t, t), o.sub(3.0, o.mul(2.0, t)));
        }
        const r = scale / Number(this.texel);
        const t = Math.min(Math.max((r - 1.0) / 3.0, 0.0), 1.0);
        return t * t * (3.0 - 2.0 * t);
    }

    _detail(scale, detail) {
        if (this.texel === null || this.texel === undefined) return detail;
        const o = this.o;
        if (this.texel === 'uniform') {
            // xg_detail: min(d, max(0, log2(max(s / (2 uFoot), 1e-9))))
            return o.min(o.f(detail), o.max(0.0, o.log2(o.max(o.div(o.f(scale), o.mul(2.0, this.foot)), 1e-9))));
        }
        return Math.min(detail, Math.max(0.0, Math.log2(Math.max(scale / (2.0 * Number(this.texel)), 1e-9))));
    }

    _mulFade(k, fade) {
        return typeof fade === 'number' ? this.o.f(k * fade) : this.o.mul(k, fade);
    }

    _noiseLib() {
        this.N = this.N ?? noise(this.o);
        return this.N;
    }

    /** noise(): 3D (landscape palettes) or 4D noise, detail 2, roughness 0.5, stretched x2.5 about 0.5; fbm(): 3D,
     * detail 5, roughness 0.6, stretched x3; both clamped to 0..1 (surfacing._Compiler.noise / .fbm). */
    _noise(f, scale, seed) {
        const key = `${f}:${scale}:${seed}`;
        if (!this.noises.has(key)) {
            const o = this.o;
            const fade = this._fade(scale);
            let body;
            if (f === 'fbm') {
                const n = this.node3(scale, this._detail(scale, 5.0), 0.6, 5.3 + 1.9 * seed);
                body = o.clamp(o.add(o.mul(o.sub(n, 0.5), this._mulFade(3.0, fade)), 0.5), 0.0, 1.0);
            } else {
                let n;
                if (this.noise3) {
                    n = this.node3(scale, this._detail(scale, 2.0), 0.5, 0.37 + 7.31 * seed);
                } else {
                    const [x, y, z] = this.pos;
                    n = this._noiseLib().noiseNode4(x, y, z, o.f(0.37 + 7.31 * seed + 0.013 * scale), o.f(1.0 / scale),
                        typeof this._detail(scale, 2.0) === 'number' ? o.f(this._detail(scale, 2.0)) : this._detail(scale, 2.0), 0.5);
                }
                body = o.clamp(o.add(o.mul(o.sub(n, 0.5), this._mulFade(2.5, fade)), 0.5), 0.0, 1.0);
            }
            this.noises.set(key, body);
        }
        return this.noises.get(key);
    }

    /** surfacing._noise3: a 3D Noise Texture at (pos + off scale_m) x (1 / scale_m), off from the seed. */
    node3(scaleM, detail, roughness, seed) {
        const o = this.o;
        const off = [37.7 * seed + 11.3, -51.9 * seed + 7.1, 23.3 * seed - 3.7].map((v) => o.f(v * Number(scaleM)));
        const [x, y, z] = this.pos;
        return this._noiseLib().noiseNode3(o.add(x, off[0]), o.add(y, off[1]), o.add(z, off[2]),
            o.f(1.0 / Math.max(Number(scaleM), 1e-6)), typeof detail === 'number' ? o.f(detail) : detail, o.f(roughness));
    }

    /** cells(): Blender's Voronoi F1 cell colour (red) of (x, y) + (97.13 seed, -61.7 seed), or of (x, y, k z) (3D)
     * with z_stretch k. A cell value has no mean to fade to: kept as it is. */
    _cells(scale, seed, k) {
        const key = `cells:${scale}:${seed}:${k}`;
        if (!this.noises.has(key)) {
            const o = this.o;
            const [x, y, z] = this.pos;
            const px = o.add(x, o.f(97.13 * seed)), py = o.add(y, o.f(-61.7 * seed));
            const inv = o.f(1.0 / Math.max(scale, 1e-6));
            const N = this._noiseLib();
            let v;
            if (k > 0.0) {
                // (uPos + off) * vec3(1, 1, k): x and y as they are, z times k (z + 0.0 is z but for a zero's sign,
                // which no cell index sees)
                v = N.voronoiF1Colour3(px, py, o.mul(z, o.f(k)), inv, o.f(1.0));
            } else {
                v = N.voronoiF1Colour2(px, py, inv, o.f(1.0));
            }
            this.noises.set(key, o.vx(v));
        }
        return this.noises.get(key);
    }
}

/** palettes.evaluate with every noise at its mean: what Compiler({ flat: true }) computes, per point. */
export function flatTwin(expr, maps, constants = null) {
    return P.evaluate(expr, maps, { constants, flat: true });
}

export { flatTwin as flat_twin };
