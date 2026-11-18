// The interleaved benchmark's verdict (tests/fluvial/bench_interleaved.sh): per size and variant, the median of the
// repeats' milliseconds per step in each edition and their ratio, gated at 1.25 (PORT_PLAN.md 8.2 row P6). Writes
// <folder>/summary.json and tests/out/fluvial/bench_test.json.
//
//     deno run --no-config --no-lock --allow-all eidoverse/terrain/tests/fluvial/bench_summary.mjs <folder> <repeats>

import * as C from '../parity/_common.mjs';

const [dir, repeats] = [Deno.args[0], Number(Deno.args[1] ?? 5)];
const T = new C.Checks('fluvial: the step within 1.25 x Blender\'s cost (interleaved, median of the repeats)');
const runs = { blender: [], port: [] };
for (let r = 1; r <= repeats; r++) {
    for (const ed of ['blender', 'port']) {
        const j = C.readJson(`${dir}/${ed}_${r}.json`);
        if (j) runs[ed].push(j);
    }
}
const median = (xs) => {
    const s = [...xs].sort((a, b) => a - b);
    return s.length % 2 ? s[(s.length - 1) / 2] : 0.5 * (s[s.length / 2 - 1] + s[s.length / 2]);
};
const out = { repeats: { blender: runs.blender.length, port: runs.port.length }, sizes: {} };
for (const size of Object.keys(runs.blender[0]?.sizes ?? {})) {
    for (const v of ['step_ms', 'step_with_lock_ms']) {
        const b = runs.blender.map((x) => x.sizes[size]?.[v]).filter(Number.isFinite);
        const p = runs.port.map((x) => x.sizes[size]?.[v]).filter(Number.isFinite);
        if (!b.length || !p.length) continue;
        const mb = median(b), mp = median(p), ratio = mp / mb;
        (out.sizes[size] ??= {})[v] = { blender: b, port: p, blender_median: mb, port_median: mp, ratio: +ratio.toFixed(3) };
        T.ok(`${size}^2 ${v === 'step_ms' ? 'step' : 'step with the lock'}: the port's median within 1.25 x Blender's`,
            ratio <= 1.25 && b.length >= 5 && p.length >= 5,
            `port ${mp.toFixed(3)} ms, Blender ${mb.toFixed(3)} ms (ratio ${ratio.toFixed(3)}; ${p.length} and ${b.length} repeats)`);
    }
}
Deno.writeTextFileSync(`${dir}/summary.json`, JSON.stringify(out, null, 1));
Deno.exit(C.finish(T, '../fluvial/bench_test', out));
