// The glacial package's recipe judged whole (PORT_PLAN.md 5.3 "recipe, distribution class" and "judge", 5.5, 8.4):
// alpine_valley's draft saves made by the port (bake.mjs --save, the floor runs' own calls: the recipe's defaults,
// Lauterbrunnen's extent) and the Blender floor runs' saves of the same seeds (base/terrain.npz), each judged by the
// Blender edition's judge (tests/judge/judge.mjs judgeSave: blender/tests/terrain/judge run by Blender's Python;
// the run's own verdict.json when its save cannot be judged). alpine_valley is of the
// distribution class (floor.json: one ulp moves its main level by 8.3 % of relief), so the gate is over seeds 1-4, as
// judge.mjs compareDistribution has it: each banded number's mean within half its band's tolerance of Blender's mean,
// and every band Blender passes on 3 or more of 4 seeds passed by the port on 3 or more. Each seed's numbers are kept.
//
//     <bake the saves> deno run ... eidoverse/terrain/bake.mjs --recipe alpine_valley --seed S --quality draft
//                      --no-cache --save --out eidoverse/terrain/tests/out/glacial/saves          (a GPU job each)
//     deno run --no-config --no-lock --allow-all eidoverse/terrain/tests/glacial/judge_test.mjs [--seeds 1,2,3,4]
//          [--saves <dir>] [--blender-saves <dir>]
//
// A seed's floor run missing under the parity key is looked for under the keys of the same Blender terrain code, then
// in --blender-saves (the Blender edition's bake.py --save of the same call: <dir>/alpine_valley_s<seed>.npz), for
// seeds beyond the floor runs' four. Writes tests/out/glacial/judge_test.json.

import * as J from '../judge/judge.mjs';
import * as C from '../parity/_common.mjs';
import { finish } from './_glacial.mjs';

const W = C.W;
const args = [...Deno.args];
const opt = (name, dflt) => { const i = args.indexOf(name); return i >= 0 ? args[i + 1] : dflt; };
const SEEDS = opt('--seeds', '1,2,3,4').split(',');
const SAVES = opt('--saves', `${W.out('glacial')}/saves`);
const BLENDER_SAVES = opt('--blender-saves', null);
const T = new C.Checks('glacial: alpine_valley judged whole, beside the Blender floor runs');
const KEY = W.parityKeyDir();
const out = { key: KEY && KEY.split('/').pop(), seeds: {} };

function floorRunOfCode(recipe, seed) {
    const own = W.floorRun(recipe, seed);
    if (own) return [own, KEY.split('/').pop()];
    const code = (dir) => { const k = C.readJson(`${dir}/manifest.json`)?.key; return k ? `${k.field_hash}|${k.terrain_hash}` : null; };
    const mine = KEY ? code(KEY) : null;
    if (!mine) return null;
    for (const k of W.parityKeys()) {
        const dir = `${k.dir}/${recipe}_s${seed}_draft/base`;
        if (k.dir !== KEY && code(k.dir) === mine && W.exists(`${dir}/done.json`)) return [dir, k.name];
    }
    return null;
}

const recipe = 'alpine_valley';
const port = [], blender = [], judged = [];
for (const seed of SEEDS) {
    let found = floorRunOfCode(recipe, Number(seed));
    const baked = BLENDER_SAVES ? `${W.absPath(BLENDER_SAVES)}/${recipe}_s${seed}` : null;
    if (!found && baked && W.exists(`${baked}.npz`)) found = [null, 'bake.py', `${baked}.npz`];
    const base = found?.[0] ?? null;
    const bsave = found ? found[2] ?? `${base}/terrain.npz` : null;
    const save = `${SAVES}/${recipe}_s${seed}.npz`;
    if (!found || !W.exists(save)) {
        out.seeds[seed] = { missing: !found ? 'the Blender floor run' : 'the port save' };
        console.log(`${recipe} s${seed}: missing ${out.seeds[seed].missing}`);
        continue;
    }
    // both saves judged now by the same judge (the floor run's own verdict.json was made by the judge of its day: seeds
    // 3 and 4 may have been run at a later commit of the same terrain code)
    const bv = await J.judgeSave(bsave, { recipe, label: `${recipe}_blender_seed${seed}`,
        outDir: `${SAVES}/judge_${recipe}_blender_s${seed}` }) ?? (base ? C.readJson(`${base}/verdict.json`) : null);
    const pv = await J.judgeSave(save, { recipe, label: `${recipe}_seed${seed}`, outDir: `${SAVES}/judge_${recipe}_s${seed}` });
    if (!bv || !pv) {
        out.seeds[seed] = { missing: !bv ? 'the Blender verdict' : 'the port verdict (see its judge.log)' };
        continue;
    }
    port.push(pv);
    blender.push(bv);
    judged.push(seed);
    const rows = (v) => Object.fromEntries(v.rows.filter((r) => r.passed !== null).map((r) => [r.metric, { gen: r.gen, passed: r.passed }]));
    out.seeds[seed] = { port: rows(pv), blender: rows(bv), port_passed: pv.rows.filter((r) => r.passed).length,
        blender_passed: bv.rows.filter((r) => r.passed).length, bands: pv.rows.filter((r) => r.passed !== null).length,
        floor_key: found[1] };
    console.log(`${recipe} s${seed}: bands passed: port ${out.seeds[seed].port_passed}, Blender ${out.seeds[seed].blender_passed} of ` +
        `${out.seeds[seed].bands}: ` + Object.entries(out.seeds[seed].port).map(([m, r]) => `${m} ${Number(r.gen).toPrecision(4)} ` +
        `(Blender ${Number(out.seeds[seed].blender[m]?.gen).toPrecision(4)})${r.passed ? '' : ' x'}`).join(', '));
}
if (port.length >= 2) {
    // the plan's gate over the first four seeds judged; with more seeds, the same rule over all of them beside it (the
    // means of a chaotic recipe's numbers settle as the seeds add up)
    const sets = [[judged.slice(0, 4), port.slice(0, 4), blender.slice(0, 4), 'distribution']];
    if (port.length > 4) sets.push([judged, port, blender, 'distribution_all']);
    for (const [seeds, p, b, key] of sets) {
        const d = J.compareDistribution(p, b);
        out[key] = { seeds, ...d };
        T.ok(`${recipe}: the distribution class over seeds ${seeds.join(', ')}: every banded number's mean within half its band's ` +
            'tolerance of Blender\'s, every band Blender passes on 3 of 4 of the seeds passed by the port as often', d.ok && p.length >= 4,
        (p.length < 4 ? `only ${p.length} seeds; ` : '') + d.means.filter((m) => !m.ok).map((m) => `${m.metric} port ${m.port.toPrecision(4)} ` +
            `Blender ${m.blender.toPrecision(4)} (tol ${m.tol?.toPrecision(3)})`).concat(d.bands.filter((x) => !x.ok).map((x) =>
            `${x.metric}: Blender passes ${x.blender_passes}, port ${x.port_passes}`)).join('; '));
    }
} else {
    T.ok(`${recipe}: judged over seeds`, false, `${port.length} seeds with both a port save and a Blender run`);
}
Deno.exit(finish(T, 'judge_test', out));
