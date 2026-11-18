// What the fluvial package's tests share: the Blender kernel tests' random fields (core/twins.py random_field) and
// the float32 packs they build their inputs from. Test code (JavaScript per cell is allowed in tests only).

import { defaultRng } from '../../core/np_random.js';

/** core/twins.py _box(a, r): the separable box blur of radius r with edge clamping (float64 running sums). */
export function box(a, h, w, r) {
    let cur = a;
    for (const axis of [0, 1]) {
        const n = axis === 0 ? h : w, out = new Float64Array(h * w);
        for (let line = 0; line < (axis === 0 ? w : h); line++) {
            const c = new Float64Array(n + 2 * r + 1);
            let s = 0;
            for (let k = 0; k < n + 2 * r; k++) {
                const src = Math.min(Math.max(k - r, 0), n - 1);
                s += axis === 0 ? cur[src * w + line] : cur[line * w + src];
                c[k + 1] = s;
            }
            for (let k = 0; k < n; k++) {
                const v = (c[k + 2 * r + 1] - c[k]) / (2 * r + 1);
                if (axis === 0) out[k * w + line] = v; else out[line * w + k] = v;
            }
        }
        cur = out;
    }
    return cur;
}

/** core/twins.py random_field(shape, lo, hi, seed, smooth): numpy's default_rng(seed).random, box-smoothed `smooth`
 * times at radius 2, rescaled to [lo, hi], as float32. */
export function randomField(h, w, lo, hi, seed, smooth = 0) {
    let a = Float64Array.from(defaultRng(seed).random(h * w));
    for (let k = 0; k < smooth; k++) a = box(a, h, w, 2);
    let mn = Infinity, mx = -Infinity;
    for (const v of a) { if (v < mn) mn = v; if (v > mx) mx = v; }
    const span = Math.max(mx - mn, 1e-12);
    return Float32Array.from(a, (v) => lo + (hi - lo) * ((v - mn) / span));
}

/** An (n, 4) interleaved float32 pack of up to four channels (core/twins.py rgba; a missing channel is 0). */
export function rgba(n, ...chans) {
    const out = new Float32Array(n * 4);
    chans.forEach((c, k) => {
        if (c === null || c === undefined) return;
        if (typeof c === 'number') { for (let i = 0; i < n; i++) out[4 * i + k] = c; return; }
        for (let i = 0; i < n; i++) out[4 * i + k] = c[i];
    });
    return out;
}
