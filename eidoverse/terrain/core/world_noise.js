// Port of blender/eidoblend/terrain/core/world_noise.py at f90c6fc.
//
// World-space noise in metres (design sections 2.4 and 3: Ekigar's noise and field_cpu.snap_freq, moved).
//
// Inputs must be functions of world position (design finding 2): a level samples the same function at its own
// cells, so a place has the same uplift, erodibility and threshold at every level. A field spec is data:
//
//     { kind: 'const', value: v }
//     { kind: 'gradient' | 'fbm' | 'ridged', wavelength_m: w, octaves: 4, lacunarity: 2, gain: 0.5, seed: 0,
//       period_m: null, amp: 1, offset: 0 }                        -> offset + amp * noise
//     { kind: 'sum' | 'product', terms: [spec, ...] }
//     { kind: 'warp', amp_m: a, wavelength_m: w, seed: 0, of: spec }
//     a number (a constant)
// A spec's own `seed` adds to the call's seed. fbm is normalised to a standard deviation of 1/3 for any octaves and
// gain; ridged is 1 - 2 |n| / 0.7 per octave, summed by amplitude over the amplitude sum (about -1..1); warp moves the
// sample points by two independent fbm fields (std 1/3) scaled to amp_m metres.
//
//     import * as N from './core/world_noise.js';
//     const f = N.fieldGpu(spec, level, 3);              // the spec at the level's cell centres: an r32f GPU field
//     const g = N.fieldGpu(spec, level, 3, { disp });    // at the cell centres moved by disp (rg32f, metres)
//     N.snapWavelength(900, 8000)                        // 888.9 m: a whole number of lattice cells per tile
//     N.latticeOffset(seed, octave)                      // the integer lattice offset of a seed and octave
//
// Periodic tiles (dunes) pass period_m: each octave's lattice then wraps over the tile, which needs the wavelength
// to divide the period (snapWavelength) and an integer lacunarity; anything else throws rather than leaving a seam.
//
// The evaluation is field_gpu's (PORT_PLAN.md 3.2: term tables in JavaScript doubles, the lattice sums on the GPU,
// kernels/world_noise_field.wgsl with kernels/noise.wgsl): a sum of leaves (gradient, fbm, ridged, const, numbers;
// a sum's amp 1) is one dispatch; products, scaled sums and warps combine their parts. numpy's field() (float64 at
// any points) is the oracle (tests/core_inputs/), not ported: every caller samples a window's cells, or those cells
// moved by a displacement field.
//
// Where this differs from world_noise.py, and why:
//   - field_gpu combines the parts of a product, a scaled sum and a warp in numpy (float32 arrays and Python numbers:
//     float32 arithmetic); here the same operations run as GPU kernels (kernels/grid/arith.wgsl), in float32, so no
//     cell is touched by JavaScript. The result stays on the GPU (field_gpu reads it back); the caller owns it.
//   - The window may be a Level, or any { x0, y0, cell, n } or non-square { x0, y0, cell, h, w } (the tests' and the
//     solvers' supersampled grids).

import { ValueError, pyFormat, pyRound, pyReprValue } from './levels.js';
import * as Gd from './grid.js';

export const HASH_BIAS = 1 << 23;
export const GRADIENT_STD = 0.1761;                     // standard deviation of one lattice of gradient()
const OFFSET_RANGE = 1 << 20;
export const FIELD_KINDS = ['const', 'gradient', 'fbm', 'ridged', 'sum', 'product', 'warp'];

/** JS Math.round: halves round toward +infinity (world_noise.py round_half_up). */
export const roundHalfUp = (v) => Math.floor(v + 0.5);

/** Nearest frequency to `freq` whose period over `tile` is a whole number of cells (unchanged when not tiling).
 * Ekigar's field_cpu.snap_freq. */
export function snapFreq(freq, tile) {
    if (!(tile && tile > 0)) return freq;
    const n = Math.max(1, roundHalfUp(freq * tile));
    return n / tile;
}

/** The wavelength nearest `wavelengthM` that fits a whole number of times in `periodM` (unchanged when periodM is
 * null). */
export function snapWavelength(wavelengthM, periodM) {
    if (!periodM) return Number(wavelengthM);
    return Number(periodM) / Math.max(1, roundHalfUp(Number(periodM) / Number(wavelengthM)));
}

/** The 32-bit PCG hash of world_noise.py _pcg (common.wgsl pcg), on an integer (its low 32 bits). */
export function pcg(v) {
    v = Number(BigInt.asUintN(32, BigInt(Math.trunc(v))));
    const state = (Math.imul(v, 747796405) + 2891336453) >>> 0;
    const word = Math.imul(((state >>> ((state >>> 28) + 4)) ^ state) >>> 0, 277803737) >>> 0;
    return ((word >>> 22) ^ word) >>> 0;
}

/** The integer lattice offset [ox, oy] of a seed and octave: 0 .. 2^20. Seed 0, octave 0 is Ekigar's own lattice. */
export function latticeOffset(seed, octave = 0) {
    if (seed === 0 && octave === 0) return [0, 0];
    const a = pcg(pcg(seed) + Math.trunc(octave) * 0x9E3779B9);
    const b = pcg((a ^ 0x68E31DA4) >>> 0);
    return [a % OFFSET_RANGE, b % OFFSET_RANGE];
}

/** The lattice cells a period of periodM metres holds at wavelengthM (null without a period); throws, naming the
 * wavelength snapWavelength would give, when they do not divide. */
export function periodCells(periodM, wavelengthM) {
    if (!periodM) return null;
    const c = Number(periodM) / Number(wavelengthM);
    if (Math.abs(c - pyRound(c)) > 1e-6) {
        throw new ValueError(`wavelength ${pyFormat(wavelengthM, 'g')} m does not divide the tile period ${pyFormat(periodM, 'g')} m; use ` +
            `snap_wavelength(${pyFormat(wavelengthM, 'g')}, ${pyFormat(periodM, 'g')}) = ${pyFormat(snapWavelength(wavelengthM, periodM), 'g')}`);
    }
    return pyRound(c);
}

/** [[octave, wavelength, amplitude], ...] of an fbm or ridged spec. */
export function octaveList(wavelengthM, octaves, lacunarity, gain, periodM) {
    if (periodM && Math.abs(lacunarity - pyRound(lacunarity)) > 1e-9) {
        throw new ValueError(`a periodic fbm needs an integer lacunarity, got ${pyFormat(lacunarity, '')}`);
    }
    let w = Number(wavelengthM), a = 1.0;
    const out = [];
    for (let i = 0; i < Math.trunc(octaves); i++) {
        out.push([i, w, a]);
        w /= lacunarity;
        a *= gain;
    }
    return out;
}

const num = (v, d) => (v === undefined || v === null ? d : Number(v));
const int = (v, d) => (v === undefined || v === null ? d : Math.trunc(Number(v)));

/** A const / gradient / fbm / ridged spec as GPU lattice terms at a window whose origin is (x0, y0):
 * [[[mode, 1/w, amp, period, bx, by, fx, fy], ...], constant] (world_noise.py _leaf_terms, in doubles). A periodic
 * term's base is reduced modulo its period (the same cells, small numbers). */
export function leafTerms(spec, seed, x0, y0) {
    const kind = spec.kind;
    const s = Math.trunc(seed) + int(spec.seed, 0);
    const amp = num(spec.amp, 1.0), off = num(spec.offset, 0.0);
    if (kind === 'const') return [[], Number(spec.value)];
    const w0 = Number(spec.wavelength_m), per = spec.period_m ?? null;
    let octs, coef, constant, mode;
    if (kind === 'gradient') {
        octs = [[0, w0, 1.0]];
        coef = [amp];
        constant = off;
        mode = 0;
    } else {
        octs = octaveList(w0, int(spec.octaves, 4), num(spec.lacunarity, 2.0), num(spec.gain, 0.5), per);
        if (kind === 'fbm') {
            const norm = (1.0 / 3.0) / (GRADIENT_STD * Math.sqrt(octs.reduce((t, [, , a]) => t + a * a, 0)));
            coef = octs.map(([, , a]) => amp * a * norm);
            constant = off;
            mode = 0;
        } else {                                        // ridged: a (1 - 2|n|/0.7) / sum a
            const tot = octs.reduce((t, [, , a]) => t + a, 0);
            coef = octs.map(([, , a]) => (-amp * 2.0 * a) / (0.7 * tot));
            constant = off + amp;
            mode = 1;
        }
    }
    const terms = [];
    octs.forEach(([i, w], k) => {
        const pc = periodCells(per, w) || 0;
        const [ox, oy] = latticeOffset(s, i);
        let bx = Math.floor(x0 / w), by = Math.floor(y0 / w);
        const fx = x0 / w - bx, fy = y0 / w - by;
        bx += ox;
        by += oy;
        if (pc) {
            bx = ((bx % pc) + pc) % pc;
            by = ((by % pc) + pc) % pc;
        }
        terms.push([mode, 1.0 / w, coef[k], pc, bx, by, fx, fy]);
    });
    return [terms, constant];
}


// ------------------------------------------------------------------------------------- the GPU evaluation ---

const windowShape = (lv) => (lv.h !== undefined && lv.w !== undefined ? [lv.h, lv.w] : [lv.n, lv.n]);
const isNumber = (v) => typeof v === 'number';

/** The spec at a window's cell centres (moved by opts.disp, an rg32f field of metres, when given), evaluated on the
 * GPU as field_gpu evaluates it: a new r32f field the caller owns. `R` is the runner (core/gpu.js); `window` a Level
 * or { x0, y0, cell, n } / { x0, y0, cell, h, w }. */
export function fieldGpu(R, spec, window, seed = 0, opts = {}) {
    const [h, w] = windowShape(window);
    const k = R.kernel('world_noise_field');
    // field_gpu's G.empty((n, n), channels=2): the zero displacement the kernel reads when there is none
    const zero = opts.disp ? null : R.field(h, w, 2);

    // a sum of leaves as terms, or null when the spec needs more than one dispatch
    const leaves = (sp, s) => {
        const kind = isNumber(sp) ? 'num' : sp.kind;
        if (kind === 'num') return [[], Number(sp)];
        if (['const', 'gradient', 'fbm', 'ridged'].includes(kind)) return leafTerms(sp, s, window.x0, window.y0);
        if (kind === 'sum' && num(sp.amp, 1.0) === 1.0) {
            const ss = s + int(sp.seed, 0);
            let terms = [], constant = num(sp.offset, 0.0);
            for (const t of sp.terms) {
                const r = leaves(t, ss);
                if (r === null) return null;
                terms = terms.concat(r[0]);
                constant += r[1];
            }
            return [terms, constant];
        }
        return null;
    };

    const dispatch = (terms, constant, disp) => {
        const tt = new Float32Array(Math.max(2 * terms.length, 2) * 4);
        terms.forEach(([mode, iw, c, pc, bx, by, fx, fy], t) => {
            if (Math.abs(bx) >= 1 << 24 || Math.abs(by) >= 1 << 24) {
                throw new ValueError('world noise lattice base beyond float32 integers: world coordinates too large');
            }
            tt.set([mode, iw, c, pc], 8 * t);
            tt.set([bx, by, fx, fy], 8 * t + 4);
        });
        const table = R.field(1, Math.max(2 * terms.length, 2), 4, tt);
        const out = R.field(h, w, 1);
        R.run(k, { terms: table, disp }, { outF: out }, { uTerms: terms.length, uCell: window.cell, uConst: constant });
        table.destroy();
        return out;
    };

    // off + amp * x, in float32 as numpy (and nothing when it changes nothing)
    const affine = (x, amp, off) => {
        if (amp === 1.0 && off === 0.0) return x;
        const y = Gd.arith(R, 'affine', x, null, { amp, off });
        x.destroy();
        return y;
    };

    const ev = (sp, s, disp) => {
        const r = leaves(sp, s);
        if (r !== null) return dispatch(r[0], r[1], disp);
        const kind = sp.kind;
        const ss = s + int(sp.seed, 0);
        const amp = num(sp.amp, 1.0), off = num(sp.offset, 0.0);
        if (kind === 'sum' || kind === 'product') {
            let out = ev(sp.terms[0], ss, disp);
            for (const t of sp.terms.slice(1)) {
                const q = ev(t, ss, disp);
                const y = Gd.arith(R, kind === 'sum' ? 'add' : 'mul', out, q);
                out.destroy();
                q.destroy();
                out = y;
            }
            return affine(out, amp, off);
        }
        if (kind === 'warp') {
            // the warp's two fbm fields, read where this spec is read (disp), then the moved points
            const a = Number(sp.amp_m), wl = Number(sp.wavelength_m), octs = int(sp.octaves, 3), per = sp.period_m ?? null;
            const fb = (sd) => ev({ kind: 'fbm', wavelength_m: wl, octaves: octs, period_m: per, amp: a }, sd, disp);
            const dx = fb(ss * 2 + 101), dy = fb(ss * 2 + 102);
            const nd = Gd.addDisp(disp, dx, dy);
            dx.destroy();
            dy.destroy();
            const out = ev(sp.of, ss, nd);
            nd.destroy();
            return affine(out, amp, off);
        }
        throw new ValueError(`field kind ${pyReprValue(kind ?? null)} is not one of (${FIELD_KINDS.map(pyReprValue).join(', ')})`);
    };

    try {
        return ev(spec, Math.trunc(seed), opts.disp ?? zero);
    } finally {
        if (zero) zero.destroy();
    }
}
export { fieldGpu as field_gpu, snapWavelength as snap_wavelength, snapFreq as snap_freq, latticeOffset as lattice_offset };
