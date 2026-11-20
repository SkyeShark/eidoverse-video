// How often Blender fails the stage-replay grade against itself (a calibration of PORT_PLAN.md 5.3 "stage replay,
// evolving op", for the lead): each stage floor of the fluvial package's ops (blender_stage_dump.py --floor: five
// perturbed replays of the stage, each field's [max, RMS, p99] / range against the unperturbed one) taken leave one
// out: sample i graded as if it were the port, against a floor made of the other four, by the plan's grade (worst
// cell: max <= max(1e-4, 1.25 x the others' largest max)) and by the RMS-and-p99 form replay_test.mjs reports beside
// it. A stage fails when any of its fields does. The rate is what a port statistically like Blender would show with a
// four-sample floor (with five, somewhat less), to set beside the port's own failures, which it counts from
// replay_test.mjs's results (tests/out/fluvial/replay_*.json). No GPU.
//
//     deno run --no-config --no-lock --allow-all eidoverse/terrain/tests/fluvial/floor_rate.mjs
//         [--recipes rolling_hills,fluvial_range,meadow,...] [--seeds 1,2] [--ops fluvial,soil_hills,...]
//
// Writes tests/out/fluvial/floor_rate.json.

import * as C from '../parity/_common.mjs';

const W = C.W;
const args = [...Deno.args];
const opt = (name, dflt) => { const i = args.indexOf(name); return i >= 0 ? args[i + 1] : dflt; };
const RECIPES = opt('--recipes', 'rolling_hills,fluvial_range,meadow,alpine_valley,caldera,impact_crater,sea_cliffs,stratovolcano,tower_karst').split(',');
const SEEDS = opt('--seeds', '1,2').split(',').map(Number);
const OPS = opt('--ops', 'fluvial,soil_hills,creep,talus,threshold').split(',');

const out = { ops: OPS, stages: 0, samples: 0, fail_max: 0, fail_rms: 0, by_op: {}, worst: [] };
for (const recipe of RECIPES) {
    for (const seed of SEEDS) {
        const dir = W.floorRun(recipe, seed);
        const floors = dir ? C.readJson(`${dir}/stage_floors.json`) : null;
        for (const st of floors?.stages ?? []) {
            if (!OPS.includes(st.op)) continue;
            const fields = Object.entries(st.floor ?? {}).filter(([, f]) => (f.samples ?? []).length >= 5);
            if (!fields.length) continue;
            const k = fields[0][1].samples.length;
            out.stages++;
            const op = (out.by_op[st.op] ??= { stages: 0, samples: 0, fail_max: 0, fail_rms: 0 });
            op.stages++;
            for (let i = 0; i < k; i++) {
                let failMax = false, failRms = false, worst = null;
                for (const [name, f] of fields) {
                    const s = f.samples[i], others = f.samples.filter((_, j) => j !== i);
                    const omax = Math.max(...others.map((x) => x[0])), orms = Math.max(...others.map((x) => x[1])),
                        op99 = Math.max(...others.map((x) => x[2] ?? 0));
                    const r = s[0] / Math.max(1e-4, 1.25 * omax);
                    if (r > 1) {
                        failMax = true;
                        if (!worst || r > worst.ratio) worst = { field: name, ratio: +r.toFixed(3) };
                    }
                    if (s[1] > Math.max(1e-4, 1.25 * orms) || (s[2] ?? 0) > Math.max(1e-4, 1.25 * op99)) failRms = true;
                }
                out.samples++;
                op.samples++;
                if (failMax) { out.fail_max++; op.fail_max++; out.worst.push({ recipe, seed, call: st.call, op: st.op, level: st.level, sample: i + 1, ...worst }); }
                if (failRms) { out.fail_rms++; op.fail_rms++; }
            }
        }
    }
}
out.rate_max = out.samples ? +(out.fail_max / out.samples).toFixed(4) : null;
out.rate_rms = out.samples ? +(out.fail_rms / out.samples).toFixed(4) : null;
for (const o of Object.values(out.by_op)) {
    o.rate_max = +(o.fail_max / o.samples).toFixed(4);
    o.rate_rms = +(o.fail_rms / o.samples).toFixed(4);
}
out.worst.sort((a, b) => b.ratio - a.ratio);
out.worst = out.worst.slice(0, 30);
console.log(`stage floors of ${out.stages} stages (${out.samples} samples, each graded against the other four): ` +
    `the worst-cell grade fails ${out.fail_max} (${(100 * out.rate_max).toFixed(1)} %), the RMS-and-p99 grade ${out.fail_rms} ` +
    `(${(100 * out.rate_rms).toFixed(1)} %)`);
for (const [op, o] of Object.entries(out.by_op)) {
    console.log(`  ${op.padEnd(11)} ${o.stages} stages, ${o.samples} samples: worst cell fails ${o.fail_max} (${(100 * o.rate_max).toFixed(1)} %), ` +
        `RMS and p99 ${o.fail_rms} (${(100 * o.rate_rms).toFixed(1)} %)`);
}
for (const w of out.worst.slice(0, 8)) console.log(`  e.g. ${w.recipe} s${w.seed} L${w.level} ${w.op} (call ${w.call}) sample ${w.sample}: ${w.field} at ${w.ratio} x its grade`);

// beside it, the port's own replays (replay_test.mjs's results in tests/out/fluvial/replay_*.json, the latest file of
// each stage): per op, the stages replayed, those passing the plan's grade and the RMS-and-p99 form, dispatch logs
// and control records equal
const latest = new Map();
const files = [...Deno.readDirSync(W.out('fluvial'))].filter((e) => /^replay_.*\.json$/.test(e.name))
    .map((e) => ({ path: `${W.out('fluvial')}/${e.name}`, t: Deno.statSync(`${W.out('fluvial')}/${e.name}`).mtime?.getTime() ?? 0 }))
    .sort((a, b) => a.t - b.t);
for (const f of files) {
    const d = C.readJson(f.path);
    for (const r of d?.results ?? []) latest.set(`${d.recipe}|${d.seed}|${r.stage?.call}`, { ...r, recipe: d.recipe, seed: d.seed });
}
out.port = {};
for (const r of latest.values()) {
    const op = r.stage?.op;
    const o = (out.port[op] ??= { stages: 0, errors: 0, ok: 0, ok_rms: 0, dispatch_equal: 0, control_equal: 0 });
    o.stages++;
    if (r.error) { o.errors++; continue; }
    o.ok += r.ok ? 1 : 0;
    o.ok_rms += r.ok_rms ? 1 : 0;
    o.dispatch_equal += r.dispatch?.ok ? 1 : 0;
    o.control_equal += r.control?.ok ? 1 : 0;
}
for (const [op, o] of Object.entries(out.port)) {
    const ran = o.stages - o.errors;
    console.log(`  the port's replays, ${op.padEnd(12)} ${o.stages} stages${o.errors ? ` (${o.errors} could not run)` : ''}: the plan's grade ` +
        `${o.ok} of ${ran} (fails ${(100 * (ran - o.ok) / Math.max(ran, 1)).toFixed(1)} %), RMS and p99 ${o.ok_rms}, dispatch logs equal ` +
        `${o.dispatch_equal}` + (op === 'fluvial' ? `, control records equal ${o.control_equal}` : ''));
}
Deno.writeTextFileSync(`${W.out('fluvial')}/floor_rate.json`, JSON.stringify(out, null, 1));
