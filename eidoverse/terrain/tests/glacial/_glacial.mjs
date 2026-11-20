// What the glacial package's tests share: the float64 forms of solvers/glacial.py's cross-section and jump-flood
// metric (_metric64, prof, cliff, fillz, seed_floor, decode_best, brute_force) as the Blender tests use them to judge
// the kernels, and small readers of the fixtures and dumps. Test code: JavaScript per cell is allowed in tests only.

import * as W from '../_where.mjs';

export const SEED_C_DEFAULT = [1.0, 1.0, 0.0, 0.0];

/** Write a test's result to tests/out/glacial/<name>.json (plan 8.1) and return its exit code. */
export function finish(T, name, extra = {}) {
    Object.assign(T.extra, extra);
    const failed = T.rows.filter((r) => !r.passed);
    const res = { test: T.title, deno: Deno.version.deno, date: new Date().toISOString(),
        seconds: +((performance.now() - T.t0) / 1000).toFixed(2), checks: T.rows.length,
        failed: failed.map((r) => r.check), ...T.extra, rows: T.rows };
    Deno.writeTextFileSync(`${W.out('glacial')}/${name}.json`, JSON.stringify(res, null, 1));
    console.log(`RESULT ${T.title}: ${T.rows.length - failed.length} of ${T.rows.length} checks passed` +
        (failed.length ? `; FAILED: ${failed.map((r) => r.check).join(' | ')}` : ''));
    return failed.length ? 1 : 0;
}

/** glacial.py cliff(t, toe, lip) in float64. */
export function cliff(t, toe, lip) {
    t = Math.min(Math.max(t, 0.0), 1.0);
    const c = 1.0 / (1.0 - 0.5 * (toe + lip));
    if (t < toe) return (c * t * t) / (2.0 * Math.max(toe, 1e-6));
    if (t > 1.0 - lip) {
        const s = 1.0 - t;
        return 1.0 - (c * s * s) / (2.0 * Math.max(lip, 1e-6));
    }
    return c * (t - 0.5 * toe);
}

/** glacial.py prof(rho, u, float64, ff). */
export function prof(rho, u, ff = null) {
    ff = ff ?? u.uFloorFrac;
    const inner = cliff((rho - ff) / (1.0 - ff), u.uToe, u.uLip);
    const out = u.uOut;
    if (u.uShW <= 0.0) return rho <= 1 ? inner : 1.0 + out * (rho - 1.0);
    const s = Math.max(rho - 1.0, 0.0) / u.uShW;
    if (rho <= 1) return inner;
    if (s <= 1) return 1.0 + u.uShH * s ** u.uShB;
    return 1.0 + u.uShH + out * (rho - 1.0 - u.uShW);
}

/** glacial.py fillz(rho, fill, H, u, float64, ff, rise). */
export function fillz(rho, fill, H, u, ff = null, rise = null) {
    ff = ff ?? u.uFloorFrac;
    rise = rise ?? u.uFloorRise;
    const t = Math.min(rho / Math.max(ff, 1e-3), 1.0);
    return fill + rise * H * t * t;
}

/** glacial.py seed_floor(u, Cc, float64): [ff, rise]. */
export function seedFloor(u, c) {
    return [Math.min(Math.max(u.uFloorFrac * c[0], 0.0), 0.95), u.uFloorRise * c[1]];
}

/** glacial.py _metric64 at distance r of a seed with seedA a, seedB b, seedC c (arrays of 4). */
export function metric64(r, a, b, u, metric, c = SEED_C_DEFAULT) {
    if (metric === 1) return r;
    const rho = r / b[0];
    const [ff, rise] = seedFloor(u, c);
    return a[2] + Math.max(a[3] * prof(rho, u, ff), fillz(rho, b[2], a[3], u, ff, rise));
}

const at4 = (arr, i) => [arr[4 * i], arr[4 * i + 1], arr[4 * i + 2], arr[4 * i + 3]];

/** glacial.py decode_best(cand, seedA, seedB, cell, prof_u, metric, slot='all', seedC): the metric of every cell's
 * four candidates in float64, Infinity where a slot is empty. Arrays are (n0, n1, 4) interleaved Float32Arrays. */
export function decodeBest(cand, seedA, seedB, seedC, n0, n1, cell, u, metric) {
    const out = new Float64Array(n0 * n1 * 4).fill(Infinity);
    for (let j = 0; j < n0; j++) {
        for (let i = 0; i < n1; i++) {
            const p = j * n1 + i;
            const xp = (i + 0.5) * cell, yp = (j + 0.5) * cell;
            for (let c = 0; c < 4; c++) {
                const ci = cand[4 * p + c];
                if (!(ci >= 0)) continue;
                const a = at4(seedA, ci), b = at4(seedB, ci), e = seedC ? at4(seedC, ci) : SEED_C_DEFAULT;
                const r = Math.hypot(xp - a[0], yp - a[1]);
                out[4 * p + c] = metric64(r, a, b, u, metric, e);
            }
        }
    }
    return out;
}

/** glacial.py brute_force(..., per_stream=True): the best metric of each stream at every cell, sorted, the four
 * best (Infinity where fewer streams), float64 over EVERY seed (the jump flood's oracle). seeds: flat cell indices. */
export function bruteForce(seeds, seedA, seedB, seedC, n0, n1, cell, u, metric) {
    const S = seeds.map((ci) => ({ a: at4(seedA, ci), b: at4(seedB, ci), c: seedC ? at4(seedC, ci) : SEED_C_DEFAULT }));
    const sids = [...new Set(S.map((s) => s.b[1]))].sort((x, y) => x - y);
    const bySid = sids.map((sid) => S.filter((s) => s.b[1] === sid));
    const out = new Float64Array(n0 * n1 * 4).fill(Infinity);
    const per = new Float64Array(sids.length);
    for (let j = 0; j < n0; j++) {
        for (let i = 0; i < n1; i++) {
            const xp = (i + 0.5) * cell, yp = (j + 0.5) * cell;
            bySid.forEach((list, k) => {
                let best = Infinity;
                for (const s of list) best = Math.min(best, metric64(Math.hypot(xp - s.a[0], yp - s.a[1]), s.a, s.b, u, metric, s.c));
                per[k] = best;
            });
            const sorted = Array.from(per).sort((x, y) => x - y);
            for (let c = 0; c < Math.min(4, sorted.length); c++) out[4 * (j * n1 + i) + c] = sorted[c];
        }
    }
    return out;
}
