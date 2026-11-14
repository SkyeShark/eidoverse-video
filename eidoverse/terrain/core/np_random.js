// Port of numpy.random.Generator at numpy v2.3.4 (no Blender file: the Blender edition draws its plans from the numpy
// its Python carries, and Blender 5.2 carries 2.3.4).
//
// numpy's default_rng(seed) in JavaScript, draw for draw (PORT_PLAN.md sections 2.3 and 2.4, risk 6). The Blender
// edition draws its plans (karst towers, cinder cones, cirque order, wind schedules, river courses, strata cores,
// impact blocks, lava walkers) from np.random.default_rng(seed) or default_rng([seed, salt, ...]); the same recipe
// and seed give the same landform in this edition only when it draws the same numbers. Transcribed from numpy's
// source: SeedSequence (bit_generator.pyx), PCG64 (src/pcg64/pcg64.h: a 128-bit LCG with the XSL-RR output),
// Generator's methods (_generator.pyx, _bounded_integers.pyx.in) and their C kernels
// (src/distributions/distributions.c, ziggurat_constants.h).
//
//     import { NpGenerator, defaultRng } from './core/np_random.js';
//     const rng = defaultRng([seed, 0x4B41525354]);       // np.random.default_rng([seed, 0x4B41525354])
//     rng.random()                  rng.random(n)         // float64 in [0, 1)
//     rng.uniform(lo, hi)           rng.uniform(lo, hi, [N, K])
//     rng.integers(n)               rng.integers(lo, hi, n)        // [lo, hi), numpy's int64 path (Lemire)
//     rng.standard_normal()         rng.normal(loc, scale, n)      // the ziggurat
//     rng.exponential(scale)        rng.poisson(lam)
//     rng.choice(n, { size: k, replace: false })          // indices; rng.choice([-1, 1]) an element;
//     rng.choice(n, { p })                                // weighted
//
// A draw with no size returns a number; with a size (a count, or a shape whose product is the count) a Float64Array
// in numpy's C order (integers too: every value the terrain draws is exact in a double). choice() over an array
// returns its elements. Method names are numpy's (standard_normal); the camelCase spellings are aliases.
//
// What is exact. The bit generator, random, uniform and integers are integer arithmetic and IEEE double
// multiplications and additions: bit for bit numpy's on x86-64 (tests/core_runner/np_random_test.mjs). The ziggurats
// return from their first test 99.3 % (normal) and 98.9 % (exponential) of the time, exactly; the wedge tests compare
// against exp(), and the tail draws and poisson's rejection test go through log1p() and log(), which numpy takes
// from the C library. The tails here take a correctly rounded log1p (below), which agrees with the C library
// Blender's numpy calls on 99.85 % of inputs (V8's Math.log1p on 92.9 %); exp and log stay V8's, as they only decide
// a comparison, and one goes the other way only when its two sides agree to the last ulp. So a tail value can still
// differ from numpy's in the last ulp where the C library itself rounds wrong; the test counts it. numpy itself
// differs across platforms in exactly these places.
//
// The seed must be given: a non-negative integer (a number or a BigInt) or a list of them, as SeedSequence takes.
// numpy's None (entropy from the system) is refused: the terrain is deterministic.
//
// The ziggurat tables and the algorithms are numpy's, under its licence:
//
//     Copyright (c) 2005-2025, NumPy Developers. All rights reserved.
//
//     Redistribution and use in source and binary forms, with or without modification, are permitted provided that
//     the following conditions are met:
//
//         * Redistributions of source code must retain the above copyright notice, this list of conditions and the
//           following disclaimer.
//         * Redistributions in binary form must reproduce the above copyright notice, this list of conditions and
//           the following disclaimer in the documentation and/or other materials provided with the distribution.
//         * Neither the name of the NumPy Developers nor the names of any contributors may be used to endorse or
//           promote products derived from this software without specific prior written permission.
//
//     THIS SOFTWARE IS PROVIDED BY THE COPYRIGHT HOLDERS AND CONTRIBUTORS "AS IS" AND ANY EXPRESS OR IMPLIED
//     WARRANTIES, INCLUDING, BUT NOT LIMITED TO, THE IMPLIED WARRANTIES OF MERCHANTABILITY AND FITNESS FOR A
//     PARTICULAR PURPOSE ARE DISCLAIMED. IN NO EVENT SHALL THE COPYRIGHT OWNER OR CONTRIBUTORS BE LIABLE FOR ANY
//     DIRECT, INDIRECT, INCIDENTAL, SPECIAL, EXEMPLARY, OR CONSEQUENTIAL DAMAGES (INCLUDING, BUT NOT LIMITED TO,
//     PROCUREMENT OF SUBSTITUTE GOODS OR SERVICES; LOSS OF USE, DATA, OR PROFITS; OR BUSINESS INTERRUPTION) HOWEVER
//     CAUSED AND ON ANY THEORY OF LIABILITY, WHETHER IN CONTRACT, STRICT LIABILITY, OR TORT (INCLUDING NEGLIGENCE OR
//     OTHERWISE) ARISING IN ANY WAY OUT OF THE USE OF THIS SOFTWARE, EVEN IF ADVISED OF THE POSSIBILITY OF SUCH DAMAGE.
//
// numpy.random (Copyright (c) 2019 Kevin Sheppard) is dual-licensed under the NCSA licence and the same 3-clause BSD
// terms. Its ziggurat methods were derived from Julia (numpy/random/src/distributions/LICENSE.md):
//
//     Copyright (c) 2009-2019: Jeff Bezanson, Stefan Karpinski, Viral B. Shah, and other contributors:
//     https://github.com/JuliaLang/julia/contributors
//
//     Permission is hereby granted, free of charge, to any person obtaining a copy of this software and associated
//     documentation files (the "Software"), to deal in the Software without restriction, including without limitation
//     the rights to use, copy, modify, merge, publish, distribute, sublicense, and/or sell copies of the Software,
//     and to permit persons to whom the Software is furnished to do so, subject to the following conditions:
//
//     The above copyright notice and this permission notice shall be included in all copies or substantial portions
//     of the Software.
//
//     THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR IMPLIED, INCLUDING BUT NOT LIMITED
//     TO THE WARRANTIES OF MERCHANTABILITY, FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL
//     THE AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER LIABILITY, WHETHER IN AN ACTION OF
//     CONTRACT, TORT OR OTHERWISE, ARISING FROM, OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER
//     DEALINGS IN THE SOFTWARE.
//
// The PCG64 generator is Melissa O'Neill's (pcg-random.org; MIT / Apache 2.0, as numpy carries it).

export const NUMPY_VERSION = '2.3.4';                    // the source this file was transcribed from

const M32 = 0xFFFFFFFFn;

// ------------------------------------------------------------------------------------------- SeedSequence ---

// bit_generator.pyx _int_to_uint32_array: an integer as little-endian 32-bit words (0 is one zero word)
function wordsOf(n) {
    if (typeof n === 'number') {
        if (!Number.isSafeInteger(n)) throw new Error(`np_random: seed ${n} is not an integer a double holds exactly; pass a BigInt`);
        n = BigInt(n);
    } else if (typeof n !== 'bigint') {
        throw new Error(`np_random: a seed is a non-negative integer or a list of them, got ${typeof n}`);
    }
    if (n < 0n) throw new Error('np_random: expected non-negative integer');          // numpy's message
    if (n === 0n) return [0];
    const out = [];
    while (n > 0n) {
        out.push(Number(n & M32));
        n >>= 32n;
    }
    return out;
}

const mul32 = (a, b) => Math.imul(a, b) >>> 0;
const XSHIFT = 16;                                       // sizeof(uint32) * 8 / 2
const INIT_A = 0x43b0d7e5, MULT_A = 0x931e8875, INIT_B = 0x8b51f9dd, MULT_B = 0x58f38ded;
const MIX_MULT_L = 0xca01f9dd, MIX_MULT_R = 0x4973f715;
const POOL_SIZE = 4;

/** SeedSequence(entropy).pool: the four mixed 32-bit words (mix_entropy). No spawn key (the terrain spawns none). */
export function seedSequencePool(entropy) {
    if (entropy == null) throw new Error('np_random: a seed is needed (numpy would take entropy from the system; the terrain is deterministic)');
    const ent = (Array.isArray(entropy) ? entropy : [entropy]).flatMap(wordsOf);
    let hashConst = INIT_A;
    const hashmix = (value) => {
        value = (value ^ hashConst) >>> 0;
        hashConst = mul32(hashConst, MULT_A);
        value = mul32(value, hashConst);
        return (value ^ (value >>> XSHIFT)) >>> 0;
    };
    const mix = (x, y) => {
        const r = (mul32(MIX_MULT_L, x) - mul32(MIX_MULT_R, y)) >>> 0;
        return (r ^ (r >>> XSHIFT)) >>> 0;
    };
    const pool = new Array(POOL_SIZE).fill(0);
    // add in the entropy up to the pool size (the hash runs on past the entropy with zeros)
    for (let i = 0; i < POOL_SIZE; i++) pool[i] = hashmix(i < ent.length ? ent[i] : 0);
    // mix all bits together so late bits can affect earlier bits
    for (let src = 0; src < POOL_SIZE; src++) {
        for (let dst = 0; dst < POOL_SIZE; dst++) {
            if (src !== dst) pool[dst] = mix(pool[dst], hashmix(pool[src]));
        }
    }
    // add any remaining entropy, mixing each new word with each pool word
    for (let src = POOL_SIZE; src < ent.length; src++) {
        for (let dst = 0; dst < POOL_SIZE; dst++) pool[dst] = mix(pool[dst], hashmix(ent[src]));
    }
    return pool;
}

/** SeedSequence.generate_state(n, uint32): n 32-bit words from the pool. */
export function generateState32(pool, n) {
    let hashConst = INIT_B;
    const out = new Array(n);
    for (let i = 0; i < n; i++) {
        let v = (pool[i % POOL_SIZE] ^ hashConst) >>> 0;
        hashConst = mul32(hashConst, MULT_B);
        v = mul32(v, hashConst);
        out[i] = (v ^ (v >>> XSHIFT)) >>> 0;
    }
    return out;
}

// -------------------------------------------------------------------------------------------------- PCG64 ---

// the 128-bit multiplier 0x2360ED051FC65DA44385DF649FCCF645 (PCG_DEFAULT_MULTIPLIER_128) as 16-bit limbs, low first
const M0 = 0xF645, M1 = 0x9FCC, M2 = 0xDF64, M3 = 0x4385, M4 = 0x5DA4, M5 = 0x1FC6, M6 = 0xED05, M7 = 0x2360;

// a 32 x 32 -> 64 bit product as [high, low] words, through 16-bit halves (every partial product is exact)
let MUL_HI = 0, MUL_LO = 0;
function mul64(a, b) {
    const al = a & 0xFFFF, ah = a >>> 16, bl = b & 0xFFFF, bh = b >>> 16;
    const ll = al * bl, lh = al * bh, hl = ah * bl, hh = ah * bh;
    const mid = (ll >>> 16) + (lh & 0xFFFF) + (hl & 0xFFFF);
    MUL_LO = (((mid & 0xFFFF) << 16) | (ll & 0xFFFF)) >>> 0;
    MUL_HI = (hh + (lh >>> 16) + (hl >>> 16) + (mid >>> 16)) >>> 0;
}

/** numpy's Generator(PCG64(SeedSequence(seed))): np.random.default_rng(seed). */
export class NpGenerator {
    constructor(seed) {
        // _pcg64.pyx: val = seed_seq.generate_state(4, uint64); pcg64_set_seed(state = val[0:2], inc = val[2:4]),
        // each pair (high, low). A uint64 is two of the 32-bit words, low first.
        const w = generateState32(seedSequencePool(seed), 8);
        // initstate = (val[0] << 64) | val[1]; initseq = (val[2] << 64) | val[3]: as 16-bit limbs, low first
        const limbs = (hiHi, hiLo, loHi, loLo) => [loLo & 0xFFFF, loLo >>> 16, loHi & 0xFFFF, loHi >>> 16,
            hiLo & 0xFFFF, hiLo >>> 16, hiHi & 0xFFFF, hiHi >>> 16];
        const initstate = limbs(w[1], w[0], w[3], w[2]);
        const initseq = limbs(w[5], w[4], w[7], w[6]);
        // pcg_setseq_128_srandom_r: state = 0; inc = (initseq << 1) | 1; step; state += initstate; step
        let carry = 1;
        this.c = new Array(8);
        for (let i = 0; i < 8; i++) {
            const v = initseq[i] * 2 + carry;
            this.c[i] = v & 0xFFFF;
            carry = v >>> 16;
        }
        this.s0 = this.s1 = this.s2 = this.s3 = this.s4 = this.s5 = this.s6 = this.s7 = 0;
        [this.c0, this.c1, this.c2, this.c3, this.c4, this.c5, this.c6, this.c7] = this.c;
        this._step();
        const s = [this.s0, this.s1, this.s2, this.s3, this.s4, this.s5, this.s6, this.s7];
        carry = 0;
        for (let i = 0; i < 8; i++) {
            const v = s[i] + initstate[i] + carry;
            s[i] = v & 0xFFFF;
            carry = v >>> 16;
        }
        [this.s0, this.s1, this.s2, this.s3, this.s4, this.s5, this.s6, this.s7] = s;
        this._step();
        this.hasU32 = false;                             // pcg64_next32's buffered high half
        this.bufU32 = 0;
        this.hi = 0;                                     // the last 64-bit output, as two words
        this.lo = 0;
    }

    // state = state * multiplier + inc (mod 2^128), on 16-bit limbs: every sum stays under 2^36, exact in a double
    _step() {
        const a0 = this.s0, a1 = this.s1, a2 = this.s2, a3 = this.s3, a4 = this.s4, a5 = this.s5, a6 = this.s6, a7 = this.s7;
        let t = a0 * M0 + this.c0;
        const r0 = t & 0xFFFF;
        t = (t - r0) / 65536 + a0 * M1 + a1 * M0 + this.c1;
        const r1 = t & 0xFFFF;
        t = (t - r1) / 65536 + a0 * M2 + a1 * M1 + a2 * M0 + this.c2;
        const r2 = t & 0xFFFF;
        t = (t - r2) / 65536 + a0 * M3 + a1 * M2 + a2 * M1 + a3 * M0 + this.c3;
        const r3 = t & 0xFFFF;
        t = (t - r3) / 65536 + a0 * M4 + a1 * M3 + a2 * M2 + a3 * M1 + a4 * M0 + this.c4;
        const r4 = t & 0xFFFF;
        t = (t - r4) / 65536 + a0 * M5 + a1 * M4 + a2 * M3 + a3 * M2 + a4 * M1 + a5 * M0 + this.c5;
        const r5 = t & 0xFFFF;
        t = (t - r5) / 65536 + a0 * M6 + a1 * M5 + a2 * M4 + a3 * M3 + a4 * M2 + a5 * M1 + a6 * M0 + this.c6;
        const r6 = t & 0xFFFF;
        t = (t - r6) / 65536 + a0 * M7 + a1 * M6 + a2 * M5 + a3 * M4 + a4 * M3 + a5 * M2 + a6 * M1 + a7 * M0 + this.c7;
        this.s0 = r0; this.s1 = r1; this.s2 = r2; this.s3 = r3; this.s4 = r4; this.s5 = r5; this.s6 = r6;
        this.s7 = t & 0xFFFF;
    }

    // pcg64_next64: step, then XSL-RR: rotr64((state >> 64) ^ state, state >> 122). Leaves the output in hi, lo.
    _next() {
        this._step();
        const xl = (((this.s1 ^ this.s5) << 16) | (this.s0 ^ this.s4)) >>> 0;
        const xh = (((this.s3 ^ this.s7) << 16) | (this.s2 ^ this.s6)) >>> 0;
        const rot = this.s7 >>> 10;
        if (rot === 0) {
            this.hi = xh; this.lo = xl;
        } else if (rot < 32) {
            this.lo = ((xl >>> rot) | (xh << (32 - rot))) >>> 0;
            this.hi = ((xh >>> rot) | (xl << (32 - rot))) >>> 0;
        } else if (rot === 32) {
            this.hi = xl; this.lo = xh;
        } else {
            const r = rot - 32;
            this.lo = ((xh >>> r) | (xl << (32 - r))) >>> 0;
            this.hi = ((xl >>> r) | (xh << (32 - r))) >>> 0;
        }
    }

    /** The next 64 bits, as a BigInt (tests; the draws below use the two words). */
    nextU64() {
        this._next();
        return (BigInt(this.hi) << 32n) | BigInt(this.lo);
    }

    /** pcg64_next32: the low half of a fresh 64 bits, then its high half on the next call. */
    nextU32() {
        if (this.hasU32) {
            this.hasU32 = false;
            return this.bufU32;
        }
        this._next();
        this.hasU32 = true;
        this.bufU32 = this.hi;
        return this.lo;
    }

    /** next_double: (next_uint64 >> 11) / 2^53. */
    nextDouble() {
        this._next();
        return (this.hi * 2097152 + (this.lo >>> 11)) * 1.1102230246251565e-16;
    }

    // ---- sizes

    static _count(size) {
        if (typeof size === 'number') return size;
        let n = 1;
        for (const d of size) n *= d;
        return n;
    }

    _fill(size, draw) {
        if (size == null) return draw();
        const n = NpGenerator._count(size);
        if (!Number.isInteger(n) || n < 0) throw new Error(`np_random: a size of ${JSON.stringify(size)}`);
        const out = new Float64Array(n);
        for (let i = 0; i < n; i++) out[i] = draw();
        return out;
    }

    // ---- the uniform draws

    /** Generator.random(size): float64 in [0, 1). */
    random(size = null) {
        return this._fill(size, () => this.nextDouble());
    }

    /** Generator.uniform(low, high, size): low + (high - low) * next_double (distributions.c random_uniform). */
    uniform(low = 0.0, high = 1.0, size = null) {
        const range = high - low;
        if (!Number.isFinite(range)) throw new Error('np_random: high - low range exceeds valid bounds');
        return this._fill(size, () => low + range * this.nextDouble());
    }

    // distributions.c buffered_bounded_lemire_uint32: a number in [0, rng], rng < 2^32 - 1
    _lemire32(rng) {
        const rngExcl = rng + 1;
        mul64(this.nextU32(), rngExcl);
        if (MUL_LO < rngExcl) {
            const threshold = (0xFFFFFFFF - rng) % rngExcl;
            while (MUL_LO < threshold) mul64(this.nextU32(), rngExcl);
        }
        return MUL_HI;
    }

    // distributions.c random_bounded_uint64 (off = 0, no mask): a number in [0, rng]
    _bounded(rng) {
        if (rng === 0) return 0;
        if (rng < 0xFFFFFFFF) return this._lemire32(rng);
        if (rng === 0xFFFFFFFF) return this.nextU32();
        // bounded_lemire_uint64, for ranges past 32 bits (none in the terrain; exact through BigInt)
        if (!Number.isSafeInteger(rng)) throw new Error(`np_random: a range of ${rng} is past what a double holds exactly`);
        const excl = BigInt(rng) + 1n, M64 = (1n << 64n) - 1n;
        let m = this.nextU64() * excl;
        let leftover = m & M64;
        if (leftover < excl) {
            const threshold = (M64 - BigInt(rng)) % excl;
            while (leftover < threshold) {
                m = this.nextU64() * excl;
                leftover = m & M64;
            }
        }
        return Number(m >> 64n);
    }

    /** Generator.integers(low, high, size): integers in [low, high), numpy's default int64 path; integers(n) is
     * [0, n). Scalar bounds (an array of bounds draws element by element, the same stream). */
    integers(low, high = null, size = null) {
        if (high == null) {
            high = low;
            low = 0;
        }
        if (!Number.isSafeInteger(low) || !Number.isSafeInteger(high)) throw new Error(`np_random: integers(${low}, ${high}): integer bounds are needed`);
        if (low >= high) throw new Error('np_random: low >= high');                     // numpy's message
        const rng = high - 1 - low;
        return this._fill(size, () => low + this._bounded(rng));
    }

    // ---- the ziggurats (distributions.c)

    /** random_standard_normal. */
    _normal() {
        for (;;) {
            // r = e3n52sb8: 8 bits of index, 1 of sign, 52 of mantissa
            this._next();
            const idx = this.lo & 0xff;
            const sign = (this.lo >>> 8) & 0x1;
            const rabs = (this.hi & 0x1FFFFFFF) * 8388608 + (this.lo >>> 9);        // bits 9..60: exact, under 2^52
            let x = rabs * WI_DOUBLE[idx];
            if (sign) x = -x;
            if (rabs < KI_DOUBLE[idx]) return x;                                     // 99.3 % of the time
            if (idx === 0) {
                for (;;) {
                    // 1 - U, to avoid log(0) (numpy gh-13361)
                    const xx = -ZIGGURAT_NOR_INV_R * log1p(-this.nextDouble());
                    const yy = -log1p(-this.nextDouble());
                    if (yy + yy > xx * xx) {
                        // (rabs >> 8) & 1: bit 17 of the draw
                        return ((this._tailBit(rabs)) ? -(ZIGGURAT_NOR_R + xx) : ZIGGURAT_NOR_R + xx);
                    }
                }
            } else if (((FI_DOUBLE[idx - 1] - FI_DOUBLE[idx]) * this.nextDouble() + FI_DOUBLE[idx]) < Math.exp(-0.5 * x * x)) {
                return x;
            }
        }
    }

    // (rabs >> 8) & 0x1 for a 52-bit rabs held in a double
    _tailBit(rabs) {
        return Math.floor(rabs / 256) % 2 === 1;
    }

    /** random_standard_exponential. */
    _exponential() {
        for (;;) {
            // ri = next_uint64 >> 3; idx = ri & 0xFF; ri >>= 8: the top 53 bits
            this._next();
            const idx = (this.lo >>> 3) & 0xFF;
            const ri = this.hi * 2097152 + (this.lo >>> 11);
            const x = ri * WE_DOUBLE[idx];
            if (ri < KE_DOUBLE[idx]) return x;                                       // 98.9 % of the time
            // standard_exponential_unlikely
            if (idx === 0) return ZIGGURAT_EXP_R - log1p(-this.nextDouble());
            if ((FE_DOUBLE[idx - 1] - FE_DOUBLE[idx]) * this.nextDouble() + FE_DOUBLE[idx] < Math.exp(-x)) return x;
        }
    }

    /** Generator.standard_normal(size). */
    standard_normal(size = null) {
        return this._fill(size, () => this._normal());
    }

    /** Generator.normal(loc, scale, size): loc + scale * standard normal (random_normal). */
    normal(loc = 0.0, scale = 1.0, size = null) {
        if (!(scale >= 0)) throw new Error('np_random: scale < 0');
        return this._fill(size, () => loc + scale * this._normal());
    }

    /** Generator.standard_exponential(size) (the ziggurat method, numpy's default). */
    standard_exponential(size = null) {
        return this._fill(size, () => this._exponential());
    }

    /** Generator.exponential(scale, size): scale * standard exponential (random_exponential). */
    exponential(scale = 1.0, size = null) {
        if (!(scale >= 0)) throw new Error('np_random: scale < 0');
        return this._fill(size, () => scale * this._exponential());
    }

    // ---- poisson (distributions.c)

    // random_poisson_mult: lam < 10
    _poissonMult(lam) {
        const enlam = Math.exp(-lam);
        let X = 0, prod = 1.0;
        for (;;) {
            prod *= this.nextDouble();
            if (prod > enlam) X += 1;
            else return X;
        }
    }

    // random_poisson_ptrs: the transformed rejection method (W. Hoermann, 1993), lam >= 10
    _poissonPtrs(lam) {
        const slam = Math.sqrt(lam);
        const loglam = Math.log(lam);
        const b = 0.931 + 2.53 * slam;
        const a = -0.059 + 0.02483 * b;
        const invalpha = 1.1239 + 1.1328 / (b - 3.4);
        const vr = 0.9277 - 3.6224 / (b - 2);
        for (;;) {
            const U = this.nextDouble() - 0.5;
            const V = this.nextDouble();
            const us = 0.5 - Math.abs(U);
            const k = Math.floor((2 * a / us + b) * U + lam + 0.43);
            if ((us >= 0.07) && (V <= vr)) return k;
            if ((k < 0) || ((us < 0.013) && (V > us))) continue;
            // log(V) == log(0.0) ok here; if U == 0.0 so that us == 0.0, log is ok since it always returns
            if ((Math.log(V) + Math.log(invalpha) - Math.log(a / (us * us) + b)) <= (-lam + k * loglam - loggam(k + 1))) return k;
        }
    }

    /** Generator.poisson(lam, size) (random_poisson). */
    poisson(lam = 1.0, size = null) {
        if (!(lam >= 0)) throw new Error('np_random: lam < 0 or lam is NaN');
        if (lam > POISSON_LAM_MAX) throw new Error('np_random: lam value too large');
        return this._fill(size, () => (lam >= 10 ? this._poissonPtrs(lam) : (lam === 0 ? 0 : this._poissonMult(lam))));
    }

    // ---- choice (_generator.pyx)

    // _shuffle_int: shuffles data[n - 1], data[n - 2], ..., data[first]
    _shuffleInt(n, first, data) {
        for (let i = n - 1; i >= first; i--) {
            const j = this._bounded(i);
            const t = data[j];
            data[j] = data[i];
            data[i] = t;
        }
    }

    /** Generator.choice(a, size, replace, p, shuffle) for a population size or a 1-D array `a`:
     * choice(a, { size = null, replace = true, p = null, shuffle = true }). Returns indices when `a` is a count
     * (a number, or a Float64Array of them with a size), else the elements chosen. */
    choice(a, opts = {}) {
        const { replace = true, shuffle = true } = opts;
        let { size = null, p = null } = opts;
        const isCount = typeof a === 'number';
        const popSize = isCount ? a : a.length;
        const isScalar = size == null;
        const count = isScalar ? 1 : NpGenerator._count(size);
        if (isCount && !Number.isInteger(a)) throw new Error('np_random: a must be a sequence or an integer');
        if (popSize <= 0 && count !== 0) {
            throw new Error(isCount ? 'np_random: a must be a positive integer unless no samples are taken' :
                'np_random: a cannot be empty unless no samples are taken');
        }
        if (p != null) {
            p = Float64Array.from(p);
            if (p.length !== popSize) throw new Error('np_random: a and p must have same size');
            const atol = Math.sqrt(Number.EPSILON);
            // _common.pyx kahan_sum
            let sum = p[0], c = 0.0;
            for (let i = 1; i < p.length; i++) {
                const y = p[i] - c;
                const t = sum + y;
                c = (t - sum) - y;
                sum = t;
            }
            if (Number.isNaN(sum)) throw new Error('np_random: Probabilities contain NaN');
            if (p.some((v) => v < 0)) throw new Error('np_random: Probabilities are not non-negative');
            if (Math.abs(sum - 1.0) > atol) throw new Error('np_random: Probabilities do not sum to 1.');
        }
        const cdfOf = (pp) => {                              // p.cumsum(); cdf /= cdf[-1]
            const cdf = new Float64Array(pp.length);
            let s = 0.0;
            for (let i = 0; i < pp.length; i++) {
                s += pp[i];
                cdf[i] = s;
            }
            const last = cdf[cdf.length - 1];
            for (let i = 0; i < cdf.length; i++) cdf[i] /= last;
            return cdf;
        };
        const searchRight = (cdf, v) => {                    // cdf.searchsorted(v, side='right')
            let lo = 0, hi = cdf.length;
            while (lo < hi) {
                const mid = (lo + hi) >>> 1;
                if (v < cdf[mid]) hi = mid;
                else lo = mid + 1;
            }
            return lo;
        };
        let idx;
        if (replace) {
            if (p != null) {
                const cdf = cdfOf(p);
                idx = new Float64Array(count);
                for (let i = 0; i < count; i++) idx[i] = searchRight(cdf, this.nextDouble());
            } else {
                idx = new Float64Array(count);
                const rng = popSize - 1;
                for (let i = 0; i < count; i++) idx[i] = this._bounded(rng);     // integers(0, pop_size, size)
            }
        } else {
            if (count > popSize) throw new Error('np_random: Cannot take a larger sample than population when replace is False');
            if (p != null) {
                if (p.reduce((n, v) => n + (v > 0 ? 1 : 0), 0) < count) throw new Error('np_random: Fewer non-zero entries in p than size');
                let nUniq = 0;
                p = p.slice();
                idx = new Float64Array(count);
                while (nUniq < count) {
                    const x = this.random(count - nUniq);
                    if (nUniq > 0) for (let i = 0; i < nUniq; i++) p[idx[i]] = 0;
                    const cdf = cdfOf(p);
                    const seen = new Set();
                    for (let i = 0; i < x.length; i++) {         // the new values, each once, in order of first appearance
                        const v = searchRight(cdf, x[i]);
                        if (!seen.has(v)) {
                            seen.add(v);
                            idx[nUniq++] = v;
                        }
                    }
                }
            } else {
                const cutoff = shuffle ? 50 : 20;                // "a heuristic tuning"
                if (popSize > 10000 && count > Math.floor(popSize / cutoff)) {
                    // tail shuffle: the last `count` of a shuffle that stops early
                    const all = new Float64Array(popSize);
                    for (let i = 0; i < popSize; i++) all[i] = i;
                    this._shuffleInt(popSize, Math.max(popSize - count, 1), all);
                    idx = all.slice(popSize - count);
                } else {
                    // Floyd's algorithm, with a hash set of the smallest power of two above 1.2 * size
                    idx = new Float64Array(count);
                    let mask = 0;
                    const setSize0 = Math.floor(1.2 * count);
                    while (mask < setSize0) mask = mask * 2 + 1;           // _gen_mask
                    const setSize = mask + 1;
                    const hashSet = new Float64Array(setSize).fill(-1);
                    for (let j = popSize - count; j < popSize; j++) {
                        const val = this._bounded(j);
                        let loc = val % setSize;
                        while (hashSet[loc] !== -1 && hashSet[loc] !== val) loc = (loc + 1) % setSize;
                        if (hashSet[loc] === -1) {                         // val is not in the set
                            hashSet[loc] = val;
                            idx[j - popSize + count] = val;
                        } else {                                           // insert j instead
                            loc = j % setSize;
                            while (hashSet[loc] !== -1) loc = (loc + 1) % setSize;
                            hashSet[loc] = j;
                            idx[j - popSize + count] = j;
                        }
                    }
                    if (shuffle) this._shuffleInt(count, 1, idx);
                }
            }
        }
        if (isCount) return isScalar ? idx[0] : idx;
        return isScalar ? a[idx[0]] : Array.from(idx, (i) => a[i]);
    }
}

// the edition's spelling of numpy's names
NpGenerator.prototype.standardNormal = NpGenerator.prototype.standard_normal;
NpGenerator.prototype.standardExponential = NpGenerator.prototype.standard_exponential;

/** np.random.default_rng(seed). */
export function defaultRng(seed) {
    return new NpGenerator(seed);
}

const POISSON_LAM_MAX = 9.223372036854775807e18 - Math.sqrt(9.223372036854775807e18) * 10;   // _common.pyx

// ----------------------------------------------------------------------------------- log1p, rounded right ---
// The ziggurat tails call the C library's log1p (numpy's npy_log1p). V8's Math.log1p rounds differently from the C
// library numpy calls on this machine (Windows' UCRT, which Blender's numpy uses) on 7.1 % of the inputs the tails
// pass it, and the C library is the correctly rounded one on 99.85 % of them (measured on 200,000 uniform inputs
// against 45-digit decimal values). So the tails take a correctly rounded log1p, computed in double-double: what is
// left of the difference is the C library's own rounding error, which also differs between platforms' numpy.

const SPLIT = 134217729;                                 // 2^27 + 1: Dekker's split of a double into two halves
const LN2_HI = 6.93147180559945286227e-01, LN2_LO = 2.31904681384629955842e-17;   // ln 2 as a double-double
const SQRT2 = Math.SQRT2;
const F64 = new Float64Array(1), W32 = new Uint32Array(F64.buffer);

function twoSum(a, b) {
    const s = a + b, bb = s - a;
    return [s, (a - (s - bb)) + (b - bb)];
}
function quickTwoSum(a, b) {
    const s = a + b;
    return [s, b - (s - a)];
}
function twoProd(a, b) {
    const p = a * b;
    let t = SPLIT * a;
    const ah = t - (t - a), al = a - ah;
    t = SPLIT * b;
    const bh = t - (t - b), bl = b - bh;
    return [p, ((ah * bh - p) + ah * bl + al * bh) + al * bl];
}
function ddAdd(a, b) {
    let [s, e] = twoSum(a[0], b[0]);
    const [t, f] = twoSum(a[1], b[1]);
    e += t;
    [s, e] = quickTwoSum(s, e);
    e += f;
    return quickTwoSum(s, e);
}
function ddMul(a, b) {
    const [p, e] = twoProd(a[0], b[0]);
    return quickTwoSum(p, e + (a[0] * b[1] + a[1] * b[0]));
}
function ddMulD(a, d) {
    const [p, e] = twoProd(a[0], d);
    return quickTwoSum(p, e + a[1] * d);
}
function ddDiv(a, b) {
    const q1 = a[0] / b[0];
    let r = ddAdd(a, ddMulD(b, -q1));
    const q2 = r[0] / b[0];
    r = ddAdd(r, ddMulD(b, -q2));
    const q3 = r[0] / b[0];
    return ddAdd(quickTwoSum(q1, q2), [q3, 0]);
}
const ATANH_C = Array.from({ length: 25 }, (_, i) => ddDiv([1, 0], [2 * i + 1, 0]));      // 1 / (2i + 1)

/** log1p(x), correctly rounded (to 2^-100 or so before the one rounding): ln(1 + x) with 1 + x kept exact as a
 * double-double, scaled to m 2^k with m in [sqrt(1/2), sqrt(2)), and ln m = 2 atanh((m - 1) / (m + 1)). */
export function log1p(x) {
    if (x === 0 || !(x > -1) || x === Infinity) return Math.log1p(x);
    if (Math.abs(x) < 2 ** -54) return x;                // x - x^2 / 2 rounds to x
    const [s, e] = twoSum(1, x);
    F64[0] = s;
    let k = ((W32[1] >>> 20) & 0x7FF) - 1023;
    let scale = 2 ** -k;
    if (s * scale > SQRT2) {
        k += 1;
        scale *= 0.5;
    }
    const m = s * scale, em = e * scale;                 // exact: powers of two
    const t = ddDiv([m - 1, 0], twoSum(m, 1));           // m - 1 is exact (m is within a factor of 2 of 1)
    const t2 = ddMul(t, t);
    let S = ATANH_C[24];
    for (let i = 23; i >= 0; i--) S = ddAdd(ddMul(S, t2), ATANH_C[i]);
    let r = ddMulD(ddMul(t, S), 2);                      // ln m
    r = ddAdd(r, [em / m, 0]);                           // ln(m + em) = ln m + em / m, |em / m| < 2^-52
    r = ddAdd(r, ddAdd(twoProd(k, LN2_HI), [k * LN2_LO, 0]));
    return r[0] + r[1];
}

// distributions.c random_loggam: log-gamma (Zhang and Jin, "Computation of Special Functions", 1996)
const LOGGAM_A = [8.333333333333333e-02, -2.777777777777778e-03, 7.936507936507937e-04, -5.952380952380952e-04,
    8.417508417508418e-04, -1.917526917526918e-03, 6.410256410256410e-03, -2.955065359477124e-02,
    1.796443723688307e-01, -1.39243221690590e+00];

function loggam(x) {
    let n = 0;
    if ((x === 1.0) || (x === 2.0)) return 0.0;
    if (x < 7.0) n = Math.trunc(7 - x);
    let x0 = x + n;
    const x2 = (1.0 / x0) * (1.0 / x0);
    const lg2pi = 1.8378770664093453e+00;                // log(2 * M_PI)
    let gl0 = LOGGAM_A[9];
    for (let k = 8; k >= 0; k--) {
        gl0 *= x2;
        gl0 += LOGGAM_A[k];
    }
    let gl = gl0 / x0 + 0.5 * lg2pi + (x0 - 0.5) * Math.log(x0) - x0;
    if (x < 7.0) {
        for (let k = 1; k <= n; k++) {
            gl -= Math.log(x0 - 1.0);
            x0 -= 1.0;
        }
    }
    return gl;
}

// ----------------------------------------------------------------------------------- the ziggurat tables ---
// numpy/random/src/distributions/ziggurat_constants.h at v2.3.4, the double-precision tables, literal for literal
// (the 64-bit integers ki and ke without their leading zeros: each is under 2^53, exact in a double).

const KI_DOUBLE = new Float64Array([
    0xEF33D8025EF6A, 0x0, 0xC08BE98FBC6A8, 0xDA354FABD8142, 0xE51F67EC1EEEA, 0xEB255E9D3F77E, 0xEEF4B817ECAB9,
    0xF19470AFA44AA, 0xF37ED61FFCB18, 0xF4F469561255C, 0xF61A5E41BA396, 0xF707A755396A4, 0xF7CB2EC28449A,
    0xF86F10C6357D3, 0xF8FA6578325DE, 0xF9724C74DD0DA, 0xF9DA907DBF509, 0xFA360F581FA74, 0xFA86FDE5B4BF8,
    0xFACF160D354DC, 0xFB0FB6718B90F, 0xFB49F8D5374C6, 0xFB7EC2366FE77, 0xFBAECE9A1E50E, 0xFBDAB9D040BED,
    0xFC03060FF6C57, 0xFC2821037A248, 0xFC4A67AE25BD1, 0xFC6A2977AEE31, 0xFC87AA92896A4, 0xFCA325E4BDE85,
    0xFCBCCE902231A, 0xFCD4D12F839C4, 0xFCEB54D8FEC99, 0xFD007BF1DC930, 0xFD1464DD6C4E6, 0xFD272A8E2F450,
    0xFD38E4FF0C91E, 0xFD49A9990B478, 0xFD598B8920F53, 0xFD689C08E99EC, 0xFD76EA9C8E832, 0xFD848547B08E8,
    0xFD9178BAD2C8C, 0xFD9DD07A7ADD2, 0xFDA9970105E8C, 0xFDB4D5DC02E20, 0xFDBF95C5BFCD0, 0xFDC9DEBB99A7D,
    0xFDD3B8118729D, 0xFDDD288342F90, 0xFDE6364369F64, 0xFDEEE708D514E, 0xFDF7401A6B42E, 0xFDFF46599ED40,
    0xFE06FE4BC24F2, 0xFE0E6C225A258, 0xFE1593C28B84C, 0xFE1C78CBC3F99, 0xFE231E9DB1CAA, 0xFE29885DA1B91,
    0xFE2FB8FB54186, 0xFE35B33558D4A, 0xFE3B799D0002A, 0xFE410E99EAD7F, 0xFE46746D47734, 0xFE4BAD34C095C,
    0xFE50BAED29524, 0xFE559F74EBC78, 0xFE5A5C8E41212, 0xFE5EF3E138689, 0xFE6366FD91078, 0xFE67B75C6D578,
    0xFE6BE661E11AA, 0xFE6FF55E5F4F2, 0xFE73E5900A702, 0xFE77B823E9E39, 0xFE7B6E37070A2, 0xFE7F08D774243,
    0xFE8289053F08C, 0xFE85EFB35173A, 0xFE893DC840864, 0xFE8C741F0CEBC, 0xFE8F9387D4EF6, 0xFE929CC879B1D,
    0xFE95909D388EA, 0xFE986FB939AA2, 0xFE9B3AC714866, 0xFE9DF2694B6D5, 0xFEA0973ABE67C, 0xFEA329CF166A4,
    0xFEA5AAB32952C, 0xFEA81A6D5741A, 0xFEAA797DE1CF0, 0xFEACC85F3D920, 0xFEAF07865E63C, 0xFEB13762FEC13,
    0xFEB3585FE2A4A, 0xFEB56AE3162B4, 0xFEB76F4E284FA, 0xFEB965FE62014, 0xFEBB4F4CF9D7C, 0xFEBD2B8F449D0,
    0xFEBEFB16E2E3E, 0xFEC0BE31EBDE8, 0xFEC2752B15A15, 0xFEC42049DAFD3, 0xFEC5BFD29F196, 0xFEC75406CEEF4,
    0xFEC8DD2500CB4, 0xFECA5B6911F12, 0xFECBCF0C427FE, 0xFECD38454FB15, 0xFECE97488C8B3, 0xFECFEC47F91B7,
    0xFED1377358528, 0xFED278F844903, 0xFED3B10242F4C, 0xFED4DFBAD586E, 0xFED605498C3DD, 0xFED721D414FE8,
    0xFED8357E4A982, 0xFED9406A42CC8, 0xFEDA42B85B704, 0xFEDB3C8746AB4, 0xFEDC2DF416652, 0xFEDD171A46E52,
    0xFEDDF813C8AD3, 0xFEDED0F909980, 0xFEDFA1E0FD414, 0xFEE06AE124BC4, 0xFEE12C0D95A06, 0xFEE1E579006E0,
    0xFEE29734B6524, 0xFEE34150AE4BC, 0xFEE3E3DB89B3C, 0xFEE47EE2982F4, 0xFEE51271DB086, 0xFEE59E9407F41,
    0xFEE623528B42E, 0xFEE6A0B5897F1, 0xFEE716C3E077A, 0xFEE7858327B82, 0xFEE7ECF7B06BA, 0xFEE84D2484AB2,
    0xFEE8A60B66343, 0xFEE8F7ACCC851, 0xFEE94207E25DA, 0xFEE9851A829EA, 0xFEE9C0E13485C, 0xFEE9F557273F4,
    0xFEEA22762CCAE, 0xFEEA4836B42AC, 0xFEEA668FC2D71, 0xFEEA7D76ED6FA, 0xFEEA8CE04FA0A, 0xFEEA94BE8333B,
    0xFEEA950296410, 0xFEEA8D9C0075E, 0xFEEA7E7897654, 0xFEEA678481D24, 0xFEEA48AA29E83, 0xFEEA21D22E4DA,
    0xFEE9F2E352024, 0xFEE9BBC26AF2E, 0xFEE97C524F2E4, 0xFEE93473C0A3A, 0xFEE8E40557516, 0xFEE88AE369C7A,
    0xFEE828E7F3DFD, 0xFEE7BDEA7B888, 0xFEE749BFF37FF, 0xFEE6CC3A9BD5E, 0xFEE64529E007E, 0xFEE5B45A32888,
    0xFEE51994E57B6, 0xFEE474A0006CF, 0xFEE3C53E12C50, 0xFEE30B2E02AD8, 0xFEE2462AD8205, 0xFEE175EB83C5A,
    0xFEE09A22A1447, 0xFEDFB27E349CC, 0xFEDEBEA76216C, 0xFEDDBE422047E, 0xFEDCB0ECE39D3, 0xFEDB964042CF4,
    0xFEDA6DCE938C9, 0xFED937237E98D, 0xFED7F1C38A836, 0xFED69D2B9C02B, 0xFED538D06AE00, 0xFED3C41DEA422,
    0xFED23E76A2FD8, 0xFED0A732FE644, 0xFECEFDA07FE34, 0xFECD4100EB7B8, 0xFECB708956EB4, 0xFEC98B61230C1,
    0xFEC790A0DA978, 0xFEC57F50F31FE, 0xFEC356686C962, 0xFEC114CB4B335, 0xFEBEB948E6FD0, 0xFEBC429A0B692,
    0xFEB9AF5EE0CDC, 0xFEB6FE1C98542, 0xFEB42D3AD1F9E, 0xFEB13B00B2D4B, 0xFEAE2591A02E9, 0xFEAAEAE992257,
    0xFEA788D8EE326, 0xFEA3FCFFD73E5, 0xFEA044C8DD9F6, 0xFE9C5D62F563B, 0xFE9843BA947A4, 0xFE93F471D4728,
    0xFE8F6BD76C5D6, 0xFE8AA5DC4E8E6, 0xFE859E07AB1EA, 0xFE804F690A940, 0xFE7AB488233C0, 0xFE74C751F6AA5,
    0xFE6E8102AA202, 0xFE67DA0B6ABD8, 0xFE60C9F38307E, 0xFE5947338F742, 0xFE51470977280, 0xFE48BD436F458,
    0xFE3F9BFFD1E37, 0xFE35D35EEB19C, 0xFE2B5122FE4FE, 0xFE20003995557, 0xFE13C82788314, 0xFE068C4EE67B0,
    0xFDF82B02B71AA, 0xFDE87C57EFEAA, 0xFDD7509C63BFD, 0xFDC46E529BF13, 0xFDAF8F82E0282, 0xFD985E1B2BA75,
    0xFD7E6EF48CF04, 0xFD613ADBD650B, 0xFD40149E2F012, 0xFD1A1A7B4C7AC, 0xFCEE204761F9E, 0xFCBA8D85E11B2,
    0xFC7D26ECD2D22, 0xFC32B2F1E22ED, 0xFBD6581C0B83A, 0xFB606C4005434, 0xFAC40582A2874, 0xF9E971E014598,
    0xF89FA48A41DFC, 0xF66C5F7F0302C, 0xF1A5A4B331C4A,
]);
const WI_DOUBLE = new Float64Array([
    8.68362706080130616677e-16, 4.77933017572773682428e-17, 6.35435241740526230246e-17, 7.45487048124769627714e-17,
    8.32936681579309972857e-17, 9.06806040505948228243e-17, 9.71486007656776183958e-17, 1.02947503142410192108e-16,
    1.08234302884476839838e-16, 1.13114701961090307945e-16, 1.17663594570229211411e-16, 1.21936172787143633280e-16,
    1.25974399146370927864e-16, 1.29810998862640315416e-16, 1.33472037368241227547e-16, 1.36978648425712032797e-16,
    1.40348230012423820659e-16, 1.43595294520569430270e-16, 1.46732087423644219083e-16, 1.49769046683910367425e-16,
    1.52715150035961979750e-16, 1.55578181694607639484e-16, 1.58364940092908853989e-16, 1.61081401752749279325e-16,
    1.63732852039698532012e-16, 1.66323990584208352778e-16, 1.68859017086765964015e-16, 1.71341701765596607184e-16,
    1.73775443658648593310e-16, 1.76163319230009959832e-16, 1.78508123169767272927e-16, 1.80812402857991522674e-16,
    1.83078487648267501776e-16, 1.85308513886180189386e-16, 1.87504446393738816849e-16, 1.89668097007747596212e-16,
    1.91801140648386198029e-16, 1.93905129306251037069e-16, 1.95981504266288244037e-16, 1.98031606831281739736e-16,
    2.00056687762733300198e-16, 2.02057915620716538808e-16, 2.04036384154802118313e-16, 2.05993118874037063144e-16,
    2.07929082904140197311e-16, 2.09845182223703516690e-16, 2.11742270357603418769e-16, 2.13621152594498681022e-16,
    2.15482589785814580926e-16, 2.17327301775643674990e-16, 2.19155970504272708519e-16, 2.20969242822353175995e-16,
    2.22767733047895534948e-16, 2.24552025294143552381e-16, 2.26322675592856786566e-16, 2.28080213834501706782e-16,
    2.29825145544246839061e-16, 2.31557953510408037008e-16, 2.33279099280043561128e-16, 2.34989024534709550938e-16,
    2.36688152357916037468e-16, 2.38376888404542434981e-16, 2.40055621981350627349e-16, 2.41724727046750252175e-16,
    2.43384563137110286400e-16, 2.45035476226149539878e-16, 2.46677799523270498158e-16, 2.48311854216108767769e-16,
    2.49937950162045242375e-16, 2.51556386532965786439e-16, 2.53167452417135826983e-16, 2.54771427381694417303e-16,
    2.56368581998939683749e-16, 2.57959178339286723500e-16, 2.59543470433517070146e-16, 2.61121704706701939097e-16,
    2.62694120385972564623e-16, 2.64260949884118951286e-16, 2.65822419160830680292e-16, 2.67378748063236329361e-16,
    2.68930150647261591777e-16, 2.70476835481199518794e-16, 2.72019005932773206655e-16, 2.73556860440867908686e-16,
    2.75090592773016664571e-16, 2.76620392269639032183e-16, 2.78146444075954410103e-16, 2.79668929362423005309e-16,
    2.81188025534502074329e-16, 2.82703906432447923059e-16, 2.84216742521840606520e-16, 2.85726701075460149289e-16,
    2.87233946347097994381e-16, 2.88738639737848191815e-16, 2.90240939955384233230e-16, 2.91741003166694553259e-16,
    2.93238983144718163965e-16, 2.94735031409293489611e-16, 2.96229297362806647792e-16, 2.97721928420902891115e-16,
    2.99213070138601307081e-16, 3.00702866332133102993e-16, 3.02191459196806151971e-16, 3.03678989421180184427e-16,
    3.05165596297821922381e-16, 3.06651417830895451744e-16, 3.08136590840829717032e-16, 3.09621251066292253306e-16,
    3.11105533263689296831e-16, 3.12589571304399892784e-16, 3.14073498269944617203e-16, 3.15557446545280064031e-16,
    3.17041547910402852545e-16, 3.18525933630440648871e-16, 3.20010734544401137886e-16, 3.21496081152744704901e-16,
    3.22982103703941557538e-16, 3.24468932280169778077e-16, 3.25956696882307838340e-16, 3.27445527514370671802e-16,
    3.28935554267536967851e-16, 3.30426907403912838589e-16, 3.31919717440175233652e-16, 3.33414115231237245918e-16,
    3.34910232054077845412e-16, 3.36408199691876507948e-16, 3.37908150518594979994e-16, 3.39410217584148914282e-16,
    3.40914534700312603713e-16, 3.42421236527501816058e-16, 3.43930458662583133920e-16, 3.45442337727858401604e-16,
    3.46957011461378353333e-16, 3.48474618808741370700e-16, 3.49995300016538099813e-16, 3.51519196727607440975e-16,
    3.53046452078274009054e-16, 3.54577210797743572160e-16, 3.56111619309838843415e-16, 3.57649825837265051035e-16,
    3.59191980508602994994e-16, 3.60738235468235137839e-16, 3.62288744989419151904e-16, 3.63843665590734438546e-16,
    3.65403156156136995766e-16, 3.66967378058870090021e-16, 3.68536495289491401456e-16, 3.70110674588289834952e-16,
    3.71690085582382297792e-16, 3.73274900927794352614e-16, 3.74865296456848868882e-16, 3.76461451331202869131e-16,
    3.78063548200896037651e-16, 3.79671773369794425924e-16, 3.81286316967837738238e-16, 3.82907373130524317507e-16,
    3.84535140186095955858e-16, 3.86169820850914927119e-16, 3.87811622433558721164e-16, 3.89460757048192620674e-16,
    3.91117441837820542060e-16, 3.92781899208054153270e-16, 3.94454357072087711446e-16, 3.96135049107613542983e-16,
    3.97824215026468259474e-16, 3.99522100857856502444e-16, 4.01228959246062907451e-16, 4.02945049763632792393e-16,
    4.04670639241074995115e-16, 4.06406002114225038723e-16, 4.08151420790493873480e-16, 4.09907186035326643447e-16,
    4.11673597380302570170e-16, 4.13450963554423599878e-16, 4.15239602940268833891e-16, 4.17039844056831587498e-16,
    4.18852026071011229572e-16, 4.20676499339901510978e-16, 4.22513625986204937320e-16, 4.24363780509307796137e-16,
    4.26227350434779809917e-16, 4.28104737005311666397e-16, 4.29996355916383230161e-16, 4.31902638100262944617e-16,
    4.33824030562279080411e-16, 4.35760997273684900553e-16, 4.37714020125858747008e-16, 4.39683599951052137423e-16,
    4.41670257615420348435e-16, 4.43674535190656726604e-16, 4.45696997211204306674e-16, 4.47738232024753387312e-16,
    4.49798853244554968009e-16, 4.51879501313005876278e-16, 4.53980845187003400947e-16, 4.56103584156742206384e-16,
    4.58248449810956667052e-16, 4.60416208163115281428e-16, 4.62607661954784567754e-16, 4.64823653154320737780e-16,
    4.67065065671263059081e-16, 4.69332828309332890697e-16, 4.71627917983835129766e-16, 4.73951363232586715165e-16,
    4.76304248053313737663e-16, 4.78687716104872284247e-16, 4.81102975314741720538e-16, 4.83551302941152515162e-16,
    4.86034051145081195402e-16, 4.88552653135360343280e-16, 4.91108629959526955862e-16, 4.93703598024033454728e-16,
    4.96339277440398725619e-16, 4.99017501309182245754e-16, 5.01740226071808946011e-16, 5.04509543081872748637e-16,
    5.07327691573354207058e-16, 5.10197073234156184149e-16, 5.13120268630678373200e-16, 5.16100055774322824569e-16,
    5.19139431175769859873e-16, 5.22241633800023428760e-16, 5.25410172417759732697e-16, 5.28648856950494511482e-16,
    5.31961834533840037535e-16, 5.35353631181649688145e-16, 5.38829200133405320160e-16, 5.42393978220171234073e-16,
    5.46053951907478041166e-16, 5.49815735089281410703e-16, 5.53686661246787600374e-16, 5.57674893292657647836e-16,
    5.61789555355541665830e-16, 5.66040892008242216739e-16, 5.70440462129138908417e-16, 5.75001376891989523684e-16,
    5.79738594572459365014e-16, 5.84669289345547900201e-16, 5.89813317647789942685e-16, 5.95193814964144415532e-16,
    6.00837969627190832234e-16, 6.06778040933344851394e-16, 6.13052720872528159123e-16, 6.19708989458162555387e-16,
    6.26804696330128439415e-16, 6.34412240712750598627e-16, 6.42623965954805540945e-16, 6.51560331734499356881e-16,
    6.61382788509766415145e-16, 6.72315046250558662913e-16, 6.84680341756425875856e-16, 6.98971833638761995415e-16,
    7.15999493483066421560e-16, 7.37242430179879890722e-16, 7.65893637080557275482e-16, 8.11384933765648418565e-16,
]);
const FI_DOUBLE = new Float64Array([
    1.00000000000000000000e+00, 9.77101701267671596263e-01, 9.59879091800106665211e-01, 9.45198953442299649730e-01,
    9.32060075959230460718e-01, 9.19991505039347012840e-01, 9.08726440052130879366e-01, 8.98095921898343418910e-01,
    8.87984660755833377088e-01, 8.78309655808917399966e-01, 8.69008688036857046555e-01, 8.60033621196331532488e-01,
    8.51346258458677951353e-01, 8.42915653112204177333e-01, 8.34716292986883434679e-01, 8.26726833946221373317e-01,
    8.18929191603702366642e-01, 8.11307874312656274185e-01, 8.03849483170964274059e-01, 7.96542330422958966274e-01,
    7.89376143566024590648e-01, 7.82341832654802504798e-01, 7.75431304981187174974e-01, 7.68637315798486264740e-01,
    7.61953346836795386565e-01, 7.55373506507096115214e-01, 7.48892447219156820459e-01, 7.42505296340151055290e-01,
    7.36207598126862650112e-01, 7.29995264561476231435e-01, 7.23864533468630222401e-01, 7.17811932630721960535e-01,
    7.11834248878248421200e-01, 7.05928501332754310127e-01, 7.00091918136511615067e-01, 6.94321916126116711609e-01,
    6.88616083004671808432e-01, 6.82972161644994857355e-01, 6.77388036218773526009e-01, 6.71861719897082099173e-01,
    6.66391343908750100056e-01, 6.60975147776663107813e-01, 6.55611470579697264149e-01, 6.50298743110816701574e-01,
    6.45035480820822293424e-01, 6.39820277453056585060e-01, 6.34651799287623608059e-01, 6.29528779924836690007e-01,
    6.24450015547026504592e-01, 6.19414360605834324325e-01, 6.14420723888913888899e-01, 6.09468064925773433949e-01,
    6.04555390697467776029e-01, 5.99681752619125263415e-01, 5.94846243767987448159e-01, 5.90047996332826008015e-01,
    5.85286179263371453274e-01, 5.80559996100790898232e-01, 5.75868682972353718164e-01, 5.71211506735253227163e-01,
    5.66587763256164445025e-01, 5.61996775814524340831e-01, 5.57437893618765945014e-01, 5.52910490425832290562e-01,
    5.48413963255265812791e-01, 5.43947731190026262382e-01, 5.39511234256952132426e-01, 5.35103932380457614215e-01,
    5.30725304403662057062e-01, 5.26374847171684479008e-01, 5.22052074672321841931e-01, 5.17756517229756352272e-01,
    5.13487720747326958914e-01, 5.09245245995747941592e-01, 5.05028667943468123624e-01, 5.00837575126148681903e-01,
    4.96671569052489714213e-01, 4.92530263643868537748e-01, 4.88413284705458028423e-01, 4.84320269426683325253e-01,
    4.80250865909046753544e-01, 4.76204732719505863248e-01, 4.72181538467730199660e-01, 4.68180961405693596422e-01,
    4.64202689048174355069e-01, 4.60246417812842867345e-01, 4.56311852678716434184e-01, 4.52398706861848520777e-01,
    4.48506701507203064949e-01, 4.44635565395739396077e-01, 4.40785034665803987508e-01, 4.36954852547985550526e-01,
    4.33144769112652261445e-01, 4.29354541029441427735e-01, 4.25583931338021970170e-01, 4.21832709229495894654e-01,
    4.18100649837848226120e-01, 4.14387534040891125642e-01, 4.10693148270188157500e-01, 4.07017284329473372217e-01,
    4.03359739221114510510e-01, 3.99720314980197222177e-01, 3.96098818515832451492e-01, 3.92495061459315619512e-01,
    3.88908860018788715696e-01, 3.85340034840077283462e-01, 3.81788410873393657674e-01, 3.78253817245619183840e-01,
    3.74736087137891138443e-01, 3.71235057668239498696e-01, 3.67750569779032587814e-01, 3.64282468129004055601e-01,
    3.60830600989648031529e-01, 3.57394820145780500731e-01, 3.53974980800076777232e-01, 3.50570941481406106455e-01,
    3.47182563956793643900e-01, 3.43809713146850715049e-01, 3.40452257044521866547e-01, 3.37110066637006045021e-01,
    3.33783015830718454708e-01, 3.30470981379163586400e-01, 3.27173842813601400970e-01, 3.23891482376391093290e-01,
    3.20623784956905355514e-01, 3.17370638029913609834e-01, 3.14131931596337177215e-01, 3.10907558126286509559e-01,
    3.07697412504292056035e-01, 3.04501391976649993243e-01, 3.01319396100803049698e-01, 2.98151326696685481377e-01,
    2.94997087799961810184e-01, 2.91856585617095209972e-01, 2.88729728482182923521e-01, 2.85616426815501756042e-01,
    2.82516593083707578948e-01, 2.79430141761637940157e-01, 2.76356989295668320494e-01, 2.73297054068577072172e-01,
    2.70250256365875463072e-01, 2.67216518343561471038e-01, 2.64195763997261190426e-01, 2.61187919132721213522e-01,
    2.58192911337619235290e-01, 2.55210669954661961700e-01, 2.52241126055942177508e-01, 2.49284212418528522415e-01,
    2.46339863501263828249e-01, 2.43408015422750312329e-01, 2.40488605940500588254e-01, 2.37581574431238090606e-01,
    2.34686861872330010392e-01, 2.31804410824338724684e-01, 2.28934165414680340644e-01, 2.26076071322380278694e-01,
    2.23230075763917484855e-01, 2.20396127480151998723e-01, 2.17574176724331130872e-01, 2.14764175251173583536e-01,
    2.11966076307030182324e-01, 2.09179834621125076977e-01, 2.06405406397880797353e-01, 2.03642749310334908452e-01,
    2.00891822494656591136e-01, 1.98152586545775138971e-01, 1.95425003514134304483e-01, 1.92709036903589175926e-01,
    1.90004651670464985713e-01, 1.87311814223800304768e-01, 1.84630492426799269756e-01, 1.81960655599522513892e-01,
    1.79302274522847582272e-01, 1.76655321443734858455e-01, 1.74019770081838553999e-01, 1.71395595637505754327e-01,
    1.68782774801211288285e-01, 1.66181285764481906364e-01, 1.63591108232365584074e-01, 1.61012223437511009516e-01,
    1.58444614155924284882e-01, 1.55888264724479197465e-01, 1.53343161060262855866e-01, 1.50809290681845675763e-01,
    1.48286642732574552861e-01, 1.45775208005994028060e-01, 1.43274978973513461566e-01, 1.40785949814444699690e-01,
    1.38308116448550733057e-01, 1.35841476571253755301e-01, 1.33386029691669155683e-01, 1.30941777173644358090e-01,
    1.28508722279999570981e-01, 1.26086870220185887081e-01, 1.23676228201596571932e-01, 1.21276805484790306533e-01,
    1.18888613442910059947e-01, 1.16511665625610869035e-01, 1.14145977827838487895e-01, 1.11791568163838089811e-01,
    1.09448457146811797824e-01, 1.07116667774683801961e-01, 1.04796225622487068629e-01, 1.02487158941935246892e-01,
    1.00189498768810017482e-01, 9.79032790388624646338e-02, 9.56285367130089991594e-02, 9.33653119126910124859e-02,
    9.11136480663737591268e-02, 8.88735920682758862021e-02, 8.66451944505580717859e-02, 8.44285095703534715916e-02,
    8.22235958132029043366e-02, 8.00305158146630696292e-02, 7.78493367020961224423e-02, 7.56801303589271778804e-02,
    7.35229737139813238622e-02, 7.13779490588904025339e-02, 6.92451443970067553879e-02, 6.71246538277884968737e-02,
    6.50165779712428976156e-02, 6.29210244377581412456e-02, 6.08381083495398780614e-02, 5.87679529209337372930e-02,
    5.67106901062029017391e-02, 5.46664613248889208474e-02, 5.26354182767921896513e-02, 5.06177238609477817000e-02,
    4.86135532158685421122e-02, 4.66230949019303814174e-02, 4.46465522512944634759e-02, 4.26841449164744590750e-02,
    4.07361106559409394401e-02, 3.88027074045261474722e-02, 3.68842156885673053135e-02, 3.49809414617161251737e-02,
    3.30932194585785779961e-02, 3.12214171919203004046e-02, 2.93659397581333588001e-02, 2.75272356696031131329e-02,
    2.57058040085489103443e-02, 2.39022033057958785407e-02, 2.21170627073088502113e-02, 2.03510962300445102935e-02,
    1.86051212757246224594e-02, 1.68800831525431419000e-02, 1.51770883079353092332e-02, 1.34974506017398673818e-02,
    1.18427578579078790488e-02, 1.02149714397014590439e-02, 8.61658276939872638800e-03, 7.05087547137322242369e-03,
    5.52240329925099155545e-03, 4.03797259336302356153e-03, 2.60907274610215926189e-03, 1.26028593049859797236e-03,
]);
const KE_DOUBLE = new Float64Array([
    0x1C5214272497C6, 0x0, 0x137D5BD79C317E, 0x186EF58E3F3C10, 0x1A9BB7320EB0AE, 0x1BD127F719447C, 0x1C951D0F88651A,
    0x1D1BFE2D5C3972, 0x1D7E5BD56B18B2, 0x1DC934DD172C70, 0x1E0409DFAC9DC8, 0x1E337B71D47836, 0x1E5A8B177CB7A2,
    0x1E7B42096F046C, 0x1E970DAF08AE3E, 0x1EAEF5B14EF09E, 0x1EC3BD07B46556, 0x1ED5F6F08799CE, 0x1EE614AE6E5688,
    0x1EF46ECA361CD0, 0x1F014B76DDD4A4, 0x1F0CE313A796B6, 0x1F176369F1F77A, 0x1F20F20C452570, 0x1F29AE1951A874,
    0x1F31B18FB95532, 0x1F39125157C106, 0x1F3FE2EB6E694C, 0x1F463332D788FA, 0x1F4C10BF1D3A0E, 0x1F51874C5C3322,
    0x1F56A109C3ECC0, 0x1F5B66D9099996, 0x1F5FE08210D08C, 0x1F6414DD445772, 0x1F6809F6859678, 0x1F6BC52A2B02E6,
    0x1F6F4B3D32E4F4, 0x1F72A07190F13A, 0x1F75C8974D09D6, 0x1F78C71B045CC0, 0x1F7B9F12413FF4, 0x1F7E5346079F8A,
    0x1F80E63BE21138, 0x1F835A3DAD9162, 0x1F85B16056B912, 0x1F87ED89B24262, 0x1F8A10759374FA, 0x1F8C1BBA3D39AC,
    0x1F8E10CC45D04A, 0x1F8FF102013E16, 0x1F91BD968358E0, 0x1F9377AC47AFD8, 0x1F95204F8B64DA, 0x1F96B878633892,
    0x1F98410C968892, 0x1F99BAE146BA80, 0x1F9B26BC697F00, 0x1F9C85561B717A, 0x1F9DD759CFD802, 0x1F9F1D6761A1CE,
    0x1FA058140936C0, 0x1FA187EB3A3338, 0x1FA2AD6F6BC4FC, 0x1FA3C91ACE0682, 0x1FA4DB5FEE6AA2, 0x1FA5E4AA4D097C,
    0x1FA6E55EE46782, 0x1FA7DDDCA51EC4, 0x1FA8CE7CE6A874, 0x1FA9B793CE5FEE, 0x1FAA9970ADB858, 0x1FAB745E588232,
    0x1FAC48A3740584, 0x1FAD1682BF9FE8, 0x1FADDE3B5782C0, 0x1FAEA008F21D6C, 0x1FAF5C2418B07E, 0x1FB012C25B7A12,
    0x1FB0C41681DFF4, 0x1FB17050B6F1FA, 0x1FB2179EB2963A, 0x1FB2BA2BDFA84A, 0x1FB358217F4E18, 0x1FB3F1A6C9BE0C,
    0x1FB486E10CACD6, 0x1FB517F3C793FC, 0x1FB5A500C5FDAA, 0x1FB62E2837FE58, 0x1FB6B388C9010A, 0x1FB7353FB50798,
    0x1FB7B368DC7DA8, 0x1FB82E1ED6BA08, 0x1FB8A57B0347F6, 0x1FB919959A0F74, 0x1FB98A85BA7204, 0x1FB9F861796F26,
    0x1FBA633DEEE286, 0x1FBACB2F41EC16, 0x1FBB3048B49144, 0x1FBB929CAEA4E2, 0x1FBBF23CC8029E, 0x1FBC4F39D22994,
    0x1FBCA9A3E140D4, 0x1FBD018A548F9E, 0x1FBD56FBDE729C, 0x1FBDAA068BD66A, 0x1FBDFAB7CB3F40, 0x1FBE491C7364DE,
    0x1FBE9540C9695E, 0x1FBEDF3086B128, 0x1FBF26F6DE6174, 0x1FBF6C9E828AE2, 0x1FBFB031A904C4, 0x1FBFF1BA0FFDB0,
    0x1FC03141024588, 0x1FC06ECF5B54B2, 0x1FC0AA6D8B1426, 0x1FC0E42399698A, 0x1FC11BF9298A64, 0x1FC151F57D1942,
    0x1FC1861F770F4A, 0x1FC1B87D9E74B4, 0x1FC1E91620EA42, 0x1FC217EED505DE, 0x1FC2450D3C83FE, 0x1FC27076864FC2,
    0x1FC29A2F90630E, 0x1FC2C23CE98046, 0x1FC2E8A2D2C6B4, 0x1FC30D654122EC, 0x1FC33087DE9C0E, 0x1FC3520E0B7EC6,
    0x1FC371FADF66F8, 0x1FC390512A2886, 0x1FC3AD137497FA, 0x1FC3C844013348, 0x1FC3E1E4CCAB40, 0x1FC3F9F78E4DA8,
    0x1FC4107DB85060, 0x1FC4257877FD68, 0x1FC438E8B5BFC6, 0x1FC44ACF15112A, 0x1FC45B2BF447E8, 0x1FC469FF6C4504,
    0x1FC477495001B2, 0x1FC483092BFBB8, 0x1FC48D3E457FF6, 0x1FC495E799D21A, 0x1FC49D03DD30B0, 0x1FC4A29179B432,
    0x1FC4A68E8E07FC, 0x1FC4A8F8EBFB8C, 0x1FC4A9CE16EA9E, 0x1FC4A90B41FA34, 0x1FC4A6AD4E28A0, 0x1FC4A2B0C82E74,
    0x1FC49D11E62DE2, 0x1FC495CC852DF4, 0x1FC48CDC265EC0, 0x1FC4823BEC237A, 0x1FC475E696DEE6, 0x1FC467D6817E82,
    0x1FC458059DC036, 0x1FC4466D702E20, 0x1FC433070BCB98, 0x1FC41DCB0D6E0E, 0x1FC406B196BBF6, 0x1FC3EDB248CB62,
    0x1FC3D2C43E593C, 0x1FC3B5DE0591B4, 0x1FC396F599614C, 0x1FC376005A4592, 0x1FC352F3069370, 0x1FC32DC1B22818,
    0x1FC3065FBD7888, 0x1FC2DCBFCBF262, 0x1FC2B0D3B99F9E, 0x1FC2828C8FFCF0, 0x1FC251DA79F164, 0x1FC21EACB6D39E,
    0x1FC1E8F18C6756, 0x1FC1B09637BB3C, 0x1FC17586DCCD10, 0x1FC137AE74D6B6, 0x1FC0F6F6BB2414, 0x1FC0B348184DA4,
    0x1FC06C898BAFF0, 0x1FC022A092F364, 0x1FBFD5710F72B8, 0x1FBF84DD29488E, 0x1FBF30C52FC60A, 0x1FBED907770CC6,
    0x1FBE7D80327DDA, 0x1FBE1E094BA614, 0x1FBDBA7A354408, 0x1FBD52A7B9F826, 0x1FBCE663C6201A, 0x1FBC757D2C4DE4,
    0x1FBBFFBF63B7AA, 0x1FBB84F23FE6A2, 0x1FBB04D9A0D18C, 0x1FBA7F351A70AC, 0x1FB9F3BF92B618, 0x1FB9622ED4ABFC,
    0x1FB8CA33174A16, 0x1FB82B76765B54, 0x1FB7859C5B895C, 0x1FB6D840D55594, 0x1FB622F7D96942, 0x1FB5654C6F37E0,
    0x1FB49EBFBF69D2, 0x1FB3CEC803E746, 0x1FB2F4CF539C3E, 0x1FB21032442852, 0x1FB1203E5A9604, 0x1FB0243042E1C2,
    0x1FAF1B31C479A6, 0x1FAE045767E104, 0x1FACDE9DBF2D72, 0x1FABA8E640060A, 0x1FAA61F399FF28, 0x1FA908656F66A2,
    0x1FA79AB3508D3C, 0x1FA61726D1F214, 0x1FA47BD48BEA00, 0x1FA2C693C5C094, 0x1FA0F4F47DF314, 0x1F9F04336BBE0A,
    0x1F9CF12B79F9BC, 0x1F9AB84415ABC4, 0x1F98555B782FB8, 0x1F95C3ABD03F78, 0x1F92FDA9CEF1F2, 0x1F8FFCDA9AE41C,
    0x1F8CB99E7385F8, 0x1F892AEC479606, 0x1F8545F904DB8E, 0x1F80FDC336039A, 0x1F7C427839E926, 0x1F7700A3582ACC,
    0x1F71200F1A241C, 0x1F6A8234B7352A, 0x1F630000A8E266, 0x1F5A66904FE3C4, 0x1F50724ECE1172, 0x1F44C7665C6FDA,
    0x1F36E5A38A59A2, 0x1F26143450340A, 0x1F113E047B0414, 0x1EF6AEFA57CBE6, 0x1ED38CA188151E, 0x1EA2A61E122DB0,
    0x1E5961C78B267C, 0x1DDDF62BAC0BB0, 0x1CDB4DD9E4E8C0,
]);
const WE_DOUBLE = new Float64Array([
    9.655740063209182975e-16, 7.089014243955414331e-18, 1.163941249669122378e-17, 1.524391512353216015e-17,
    1.833284885723743916e-17, 2.108965109464486630e-17, 2.361128077843138196e-17, 2.595595772310893952e-17,
    2.816173554197752338e-17, 3.025504130321382330e-17, 3.225508254836375280e-17, 3.417632340185027033e-17,
    3.602996978734452488e-17, 3.782490776869649048e-17, 3.956832198097553231e-17, 4.126611778175946428e-17,
    4.292321808442525631e-17, 4.454377743282371417e-17, 4.613133981483185932e-17, 4.768895725264635940e-17,
    4.921928043727962847e-17, 5.072462904503147014e-17, 5.220704702792671737e-17, 5.366834661718192181e-17,
    5.511014372835094717e-17, 5.653388673239667134e-17, 5.794088004852766616e-17, 5.933230365208943081e-17,
    6.070922932847179572e-17, 6.207263431163193485e-17, 6.342341280303076511e-17, 6.476238575956142121e-17,
    6.609030925769405241e-17, 6.740788167872722244e-17, 6.871574991183812442e-17, 7.001451473403929616e-17,
    7.130473549660643409e-17, 7.258693422414648352e-17, 7.386159921381791997e-17, 7.512918820723728089e-17,
    7.639013119550825792e-17, 7.764483290797848102e-17, 7.889367502729790548e-17, 8.013701816675454434e-17,
    8.137520364041762206e-17, 8.260855505210038174e-17, 8.383737972539139383e-17, 8.506196999385323132e-17,
    8.628260436784112996e-17, 8.749954859216182511e-17, 8.871305660690252281e-17, 8.992337142215357066e-17,
    9.113072591597909173e-17, 9.233534356381788123e-17, 9.353743910649128938e-17, 9.473721916312949566e-17,
    9.593488279457997317e-17, 9.713062202221521206e-17, 9.832462230649511362e-17, 9.951706298915071878e-17,
    1.007081177024294931e-16, 1.018979547484694078e-16, 1.030867374515421954e-16, 1.042746244856188556e-16,
    1.054617701794576406e-16, 1.066483248011914702e-16, 1.078344348241948498e-16, 1.090202431758350473e-16,
    1.102058894705578110e-16, 1.113915102286197502e-16, 1.125772390816567488e-16, 1.137632069661684705e-16,
    1.149495423059009298e-16, 1.161363711840218308e-16, 1.173238175059045788e-16, 1.185120031532669434e-16,
    1.197010481303465158e-16, 1.208910707027385520e-16, 1.220821875294706151e-16, 1.232745137888415193e-16,
    1.244681632985112523e-16, 1.256632486302898513e-16, 1.268598812200397542e-16, 1.280581714730749379e-16,
    1.292582288654119552e-16, 1.304601620412028847e-16, 1.316640789066572582e-16, 1.328700867207380889e-16,
    1.340782921828999433e-16, 1.352888015181175458e-16, 1.365017205594397770e-16, 1.377171548282880964e-16,
    1.389352096127063919e-16, 1.401559900437571538e-16, 1.413796011702485188e-16, 1.426061480319665444e-16,
    1.438357357315790180e-16, 1.450684695053687684e-16, 1.463044547929475721e-16, 1.475437973060951633e-16,
    1.487866030968626066e-16, 1.500329786250736949e-16, 1.512830308253539427e-16, 1.525368671738125550e-16,
    1.537945957544996933e-16, 1.550563253257577148e-16, 1.563221653865837505e-16, 1.575922262431176140e-16,
    1.588666190753684151e-16, 1.601454560042916733e-16, 1.614288501593278662e-16, 1.627169157465130500e-16,
    1.640097681172717950e-16, 1.653075238380036909e-16, 1.666103007605742067e-16, 1.679182180938228863e-16,
    1.692313964762022267e-16, 1.705499580496629830e-16, 1.718740265349031656e-16, 1.732037273081008369e-16,
    1.745391874792533975e-16, 1.758805359722491379e-16, 1.772279036068006489e-16, 1.785814231823732619e-16,
    1.799412295642463721e-16, 1.813074597718501559e-16, 1.826802530695252266e-16, 1.840597510598587828e-16,
    1.854460977797569461e-16, 1.868394397994192684e-16, 1.882399263243892051e-16, 1.896477093008616722e-16,
    1.910629435244376536e-16, 1.924857867525243818e-16, 1.939163998205899420e-16, 1.953549467624909132e-16,
    1.968015949351037382e-16, 1.982565151475019047e-16, 1.997198817949342081e-16, 2.011918729978734671e-16,
    2.026726707464198289e-16, 2.041624610503588774e-16, 2.056614340951917875e-16, 2.071697844044737034e-16,
    2.086877110088159721e-16, 2.102154176219292789e-16, 2.117531128241075913e-16, 2.133010102535779087e-16,
    2.148593288061663316e-16, 2.164282928437604723e-16, 2.180081324120784027e-16, 2.195990834682870728e-16,
    2.212013881190495942e-16, 2.228152948696180545e-16, 2.244410588846308588e-16, 2.260789422613173739e-16,
    2.277292143158621037e-16, 2.293921518837311354e-16, 2.310680396348213318e-16, 2.327571704043534613e-16,
    2.344598455404957859e-16, 2.361763752697773994e-16, 2.379070790814276700e-16, 2.396522861318623520e-16,
    2.414123356706293277e-16, 2.431875774892255956e-16, 2.449783723943070217e-16, 2.467850927069288738e-16,
    2.486081227895851719e-16, 2.504478596029557040e-16, 2.523047132944217013e-16, 2.541791078205812227e-16,
    2.560714816061770759e-16, 2.579822882420530896e-16, 2.599119972249746917e-16, 2.618610947423924219e-16,
    2.638300845054942823e-16, 2.658194886341845120e-16, 2.678298485979525166e-16, 2.698617262169488933e-16,
    2.719157047279818500e-16, 2.739923899205814823e-16, 2.760924113487617126e-16, 2.782164236246436081e-16,
    2.803651078006983464e-16, 2.825391728480253184e-16, 2.847393572388174091e-16, 2.869664306419817679e-16,
    2.892211957417995598e-16, 2.915044901905293183e-16, 2.938171887070028633e-16, 2.961602053345465687e-16,
    2.985344958730045276e-16, 3.009410605012618141e-16, 3.033809466085003416e-16, 3.058552518544860874e-16,
    3.083651274815310004e-16, 3.109117819034266344e-16, 3.134964845996663118e-16, 3.161205703467105734e-16,
    3.187854438219713117e-16, 3.214925846206797361e-16, 3.242435527309451638e-16, 3.270399945182240440e-16,
    3.298836492772283149e-16, 3.327763564171671408e-16, 3.357200633553244075e-16, 3.387168342045505162e-16,
    3.417688593525636996e-16, 3.448784660453423890e-16, 3.480481301037442286e-16, 3.512804889222979418e-16,
    3.545783559224791863e-16, 3.579447366604276541e-16, 3.613828468219060593e-16, 3.648961323764542545e-16,
    3.684882922095621322e-16, 3.721633036080207290e-16, 3.759254510416256532e-16, 3.797793587668874387e-16,
    3.837300278789213687e-16, 3.877828785607895292e-16, 3.919437984311428867e-16, 3.962191980786774996e-16,
    4.006160751056541688e-16, 4.051420882956573177e-16, 4.098056438903062509e-16, 4.146159964290904582e-16,
    4.195833672073398926e-16, 4.247190841824385048e-16, 4.300357481667470702e-16, 4.355474314693952008e-16,
    4.412699169036069903e-16, 4.472209874259932285e-16, 4.534207798565834480e-16, 4.598922204905932469e-16,
    4.666615664711475780e-16, 4.737590853262492027e-16, 4.812199172829237933e-16, 4.890851827392209900e-16,
    4.974034236191939753e-16, 5.062325072144159699e-16, 5.156421828878082953e-16, 5.257175802022274839e-16,
    5.365640977112021618e-16, 5.483144034258703912e-16, 5.611387454675159622e-16, 5.752606481503331688e-16,
    5.909817641652102998e-16, 6.087231416180907671e-16, 6.290979034877557049e-16, 6.530492053564040799e-16,
    6.821393079028928626e-16, 7.192444966089361564e-16, 7.706095350032096755e-16, 8.545517038584027421e-16,
]);
const FE_DOUBLE = new Float64Array([
    1.000000000000000000e+00, 9.381436808621747003e-01, 9.004699299257464817e-01, 8.717043323812035949e-01,
    8.477855006239896074e-01, 8.269932966430503241e-01, 8.084216515230083777e-01, 7.915276369724956185e-01,
    7.759568520401155522e-01, 7.614633888498962833e-01, 7.478686219851951034e-01, 7.350380924314234843e-01,
    7.228676595935720206e-01, 7.112747608050760117e-01, 7.001926550827881623e-01, 6.895664961170779872e-01,
    6.793505722647653622e-01, 6.695063167319247333e-01, 6.600008410789997004e-01, 6.508058334145710999e-01,
    6.418967164272660897e-01, 6.332519942143660652e-01, 6.248527387036659775e-01, 6.166821809152076561e-01,
    6.087253820796220127e-01, 6.009689663652322267e-01, 5.934009016917334289e-01, 5.860103184772680329e-01,
    5.787873586028450257e-01, 5.717230486648258170e-01, 5.648091929124001709e-01, 5.580382822625874484e-01,
    5.514034165406412891e-01, 5.448982376724396115e-01, 5.385168720028619127e-01, 5.322538802630433219e-01,
    5.261042139836197284e-01, 5.200631773682335979e-01, 5.141263938147485613e-01, 5.082897764106428795e-01,
    5.025495018413477233e-01, 4.969019872415495476e-01, 4.913438695940325340e-01, 4.858719873418849144e-01,
    4.804833639304542103e-01, 4.751751930373773747e-01, 4.699448252839599771e-01, 4.647897562504261781e-01,
    4.597076156421376902e-01, 4.546961574746155033e-01, 4.497532511627549967e-01, 4.448768734145485126e-01,
    4.400651008423538957e-01, 4.353161032156365740e-01, 4.306281372884588343e-01, 4.259995411430343437e-01,
    4.214287289976165751e-01, 4.169141864330028757e-01, 4.124544659971611793e-01, 4.080481831520323954e-01,
    4.036940125305302773e-01, 3.993906844752310725e-01, 3.951369818332901573e-01, 3.909317369847971069e-01,
    3.867738290841376547e-01, 3.826621814960098344e-01, 3.785957594095807899e-01, 3.745735676159021588e-01,
    3.705946484351460013e-01, 3.666580797815141568e-01, 3.627629733548177748e-01, 3.589084729487497794e-01,
    3.550937528667874599e-01, 3.513180164374833381e-01, 3.475804946216369817e-01, 3.438804447045024082e-01,
    3.402171490667800224e-01, 3.365899140286776059e-01, 3.329980687618089852e-01, 3.294409642641363267e-01,
    3.259179723935561879e-01, 3.224284849560891675e-01, 3.189719128449572394e-01, 3.155476852271289490e-01,
    3.121552487741795501e-01, 3.087940669345601852e-01, 3.054636192445902565e-01, 3.021634006756935276e-01,
    2.988929210155817917e-01, 2.956517042812611962e-01, 2.924392881618925744e-01, 2.892552234896777485e-01,
    2.860990737370768255e-01, 2.829704145387807457e-01, 2.798688332369729248e-01, 2.767939284485173568e-01,
    2.737453096528029706e-01, 2.707225967990600224e-01, 2.677254199320447947e-01, 2.647534188350622042e-01,
    2.618062426893629779e-01, 2.588835497490162285e-01, 2.559850070304153791e-01, 2.531102900156294577e-01,
    2.502590823688622956e-01, 2.474310756653276266e-01, 2.446259691318921070e-01, 2.418434693988772144e-01,
    2.390832902624491774e-01, 2.363451524570596429e-01, 2.336287834374333461e-01, 2.309339171696274118e-01,
    2.282602939307167011e-01, 2.256076601166840667e-01, 2.229757680581201940e-01, 2.203643758433594946e-01,
    2.177732471487005272e-01, 2.152021510753786837e-01, 2.126508619929782795e-01, 2.101191593889882581e-01,
    2.076068277242220372e-01, 2.051136562938377095e-01, 2.026394390937090173e-01, 2.001839746919112650e-01,
    1.977470661050988732e-01, 1.953285206795632167e-01, 1.929281499767713515e-01, 1.905457696631953912e-01,
    1.881811994042543179e-01, 1.858342627621971110e-01, 1.835047870977674633e-01, 1.811926034754962889e-01,
    1.788975465724783054e-01, 1.766194545904948843e-01, 1.743581691713534942e-01, 1.721135353153200598e-01,
    1.698854013025276610e-01, 1.676736186172501919e-01, 1.654780418749360049e-01, 1.632985287519018169e-01,
    1.611349399175920349e-01, 1.589871389693142123e-01, 1.568549923693652315e-01, 1.547383693844680830e-01,
    1.526371420274428570e-01, 1.505511850010398944e-01, 1.484803756438667910e-01, 1.464245938783449441e-01,
    1.443837221606347754e-01, 1.423576454324722018e-01, 1.403462510748624548e-01, 1.383494288635802039e-01,
    1.363670709264288572e-01, 1.343990717022136294e-01, 1.324453279013875218e-01, 1.305057384683307731e-01,
    1.285802045452281717e-01, 1.266686294375106714e-01, 1.247709185808309612e-01, 1.228869795095451356e-01,
    1.210167218266748335e-01, 1.191600571753276827e-01, 1.173168992115555670e-01, 1.154871635786335338e-01,
    1.136707678827443141e-01, 1.118676316700562973e-01, 1.100776764051853845e-01, 1.083008254510337970e-01,
    1.065370040500016602e-01, 1.047861393065701724e-01, 1.030481601712577161e-01, 1.013229974259536315e-01,
    9.961058367063713170e-02, 9.791085331149219917e-02, 9.622374255043279756e-02, 9.454918937605585882e-02,
    9.288713355604354127e-02, 9.123751663104015530e-02, 8.960028191003285847e-02, 8.797537446727021759e-02,
    8.636274114075691288e-02, 8.476233053236811865e-02, 8.317409300963238272e-02, 8.159798070923741931e-02,
    8.003394754231990538e-02, 7.848194920160642130e-02, 7.694194317048050347e-02, 7.541388873405840965e-02,
    7.389774699236474620e-02, 7.239348087570873780e-02, 7.090105516237182881e-02, 6.942043649872875477e-02,
    6.795159342193660135e-02, 6.649449638533977414e-02, 6.504911778675374900e-02, 6.361543199980733421e-02,
    6.219341540854099459e-02, 6.078304644547963265e-02, 5.938430563342026597e-02, 5.799717563120065922e-02,
    5.662164128374287675e-02, 5.525768967669703741e-02, 5.390531019604608703e-02, 5.256449459307169225e-02,
    5.123523705512628146e-02, 4.991753428270637172e-02, 4.861138557337949667e-02, 4.731679291318154762e-02,
    4.603376107617516977e-02, 4.476229773294328196e-02, 4.350241356888818328e-02, 4.225412241331623353e-02,
    4.101744138041481941e-02, 3.979239102337412542e-02, 3.857899550307485742e-02, 3.737728277295936097e-02,
    3.618728478193142251e-02, 3.500903769739741045e-02, 3.384258215087432992e-02, 3.268796350895953468e-02,
    3.154523217289360859e-02, 3.041444391046660423e-02, 2.929566022463739317e-02, 2.818894876397863569e-02,
    2.709438378095579969e-02, 2.601204664513421735e-02, 2.494202641973178314e-02, 2.388442051155817078e-02,
    2.283933540638524023e-02, 2.180688750428358066e-02, 2.078720407257811723e-02, 1.978042433800974303e-02,
    1.878670074469603046e-02, 1.780620041091136169e-02, 1.683910682603994777e-02, 1.588562183997316302e-02,
    1.494596801169114850e-02, 1.402039140318193759e-02, 1.310916493125499106e-02, 1.221259242625538123e-02,
    1.133101359783459695e-02, 1.046481018102997894e-02, 9.614413642502209895e-03, 8.780314985808975251e-03,
    7.963077438017040002e-03, 7.163353183634983863e-03, 6.381905937319179087e-03, 5.619642207205483020e-03,
    4.877655983542392333e-03, 4.157295120833795314e-03, 3.460264777836904049e-03, 2.788798793574076128e-03,
    2.145967743718906265e-03, 1.536299780301572356e-03, 9.672692823271745359e-04, 4.541343538414967652e-04,
]);
const ZIGGURAT_NOR_R = 3.6541528853610087963519472518;
const ZIGGURAT_NOR_INV_R = 0.27366123732975827203338247596;         // 1.0 / ziggurat_nor_r
const ZIGGURAT_EXP_R = 7.6971174701310497140446280481;
