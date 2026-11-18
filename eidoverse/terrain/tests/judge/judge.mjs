// The judge harness (PORT_PLAN.md 6.3, 5.3 "judge"): a saved terrain judged by the Blender edition's own judge
// (blender/tests/terrain/judge: numpy, run by Blender's Python through tests/judge/judge_field.py), and its numbers
// set beside the Blender save's for the same recipe and seed. One judge, so a difference in a number is a difference
// in the ground. The port saves its terrain in the Terrain.save format (api.js) and hands the path here.
//
//     import * as J from '../judge/judge.mjs';
//     const v = await J.judgeSave(savePath, { recipe: 'tower_karst' });      // the verdict: numbers, bands, rows
//     const c = J.compareVerdicts(v, blenderVerdict, floorEntry);            // field class (plan 5.3)
//     const d = J.compareDistribution(portVerdicts, blenderVerdicts);        // distribution class, over seeds
//
//     deno run --no-config --no-lock --allow-all eidoverse/terrain/tests/judge/judge.mjs <save> (--recipe R |
//          --reference N) [--against <verdict.json>] [--seed S] [--floor <floor.json>] [--out <dir>]
//                    judges a save; with --against (a Blender run's verdict.json; default: the floor's base run of
//                    that recipe and seed) compares the numbers
//     deno run ... judge.mjs --selfcheck <floor run>/base [--runpy]
//                    the adapter on Blender's own save against the verdict that run's own judge() call wrote: the
//                    numbers must be equal. --runpy also runs the Blender edition's judge/run.py --field
//                    --no-render with the Python on the path (run.py needs Pillow) and compares its verdicts.json
//     deno run ... judge.mjs --selfcheck-all [--runpy] [--seeds 1,2]
//                    the same for every base run of the floor that has a verdict (tests/out/parity/
//                    judge_selfcheck_all.json sums them up)
//     deno run --unstable-webgpu ... judge.mjs --resave <dir> [--recipes a,b] [--seeds 1,2]
//                    a GPU job: every floor base run's Blender save loaded by the port (api.js Terrain.load) and
//                    written again by it (t.save) as <dir>/<recipe>_s<seed>: the Terrain.save format as the port
//                    writes it, until the port generates the recipes itself
//     deno run ... judge.mjs --judge-saves <dir> [--recipes a,b]
//                    every port save in <dir> judged by the Blender judge, its numbers against the Blender save's
//                    (compareVerdicts, the floor's class and changes) and its arrays against the Blender save's
//                    (tests/parity/field_parity.mjs); tests/out/parity/judge_port_saves.json sums them up
//
// The comparison of numbers, per the plan's judge grade:
//   field class         each number within max(1.25 x the largest change the floor's samples show in it, its
//                       quantisation step, 1e-4 of the number) of the Blender save's. The quantisation step is one
//                       band of the spectrum's 48 for the knee and the peak, and 1 % of the band's tolerance for a
//                       banded number. The 1e-4 is this harness's own floor (a correct port differs from Blender
//                       by the kernel grade even where Blender repeats itself to 1e-8, as tower_karst does).
//   distribution class  over seeds 1-4: each banded number's mean within half its band's tolerance of Blender's
//                       mean; every band Blender passes on 3 or more of 4 seeds, the port passes on 3 or more.
// Verdicts are reported, not compared: a number near a band's edge flips its verdict on noise.

import * as W from '../_where.mjs';
import * as C from '../parity/_common.mjs';

const HERE = W.urlPath(new URL('./', import.meta.url));

/** Judge a saved terrain with the Blender judge. opts: recipe or reference (one is needed), label, outDir (where
 * verdicts.json goes; default tests/out/judge/<label>/), sourceChain (false for a field that is the reference's own
 * data). Returns the verdict (judging.Verdict.to_dict()), or null after saying what is missing. */
export async function judgeSave(save, opts = {}) {
    const py = W.needBlenderPython('the judge');
    const edition = W.needBlenderEdition('the judge');
    if (!py || !edition) return null;
    const path = W.absPath(save);
    const label = opts.label ?? path.split('/').pop().replace(/\.(npz|json)$/, '');
    const outDir = opts.outDir ?? `${W.out('judge')}/${label}`;
    Deno.mkdirSync(outDir, { recursive: true });
    const out = `${outDir}/verdicts.json`;
    const argv = [py, '-I', `${HERE}/judge_field.py`, '--field', path, '--label', label, '--out', out];
    if (opts.recipe) argv.push('--recipe', opts.recipe);
    if (opts.reference) argv.push('--reference', opts.reference);
    if (opts.sourceChain === false) argv.push('--no-source-chain');
    const code = await W.run(argv, { cwd: edition, log: `${outDir}/judge.log`,
        env: { ...Deno.env.toObject(), EIDO_BLENDER_EDITION: edition, PYTHONDONTWRITEBYTECODE: '1' } });
    const res = C.readJson(out);
    if (code !== 0 || !res) {
        console.log(`[judge] failed (exit ${code}): see ${outDir}/judge.log`);
        return null;
    }
    return { ...res.verdicts[0], versions: res.versions };
}

const isNum = (x) => typeof x === 'number' && Number.isFinite(x);

// the tolerance half-width of a banded row: |g - r| allowed
function bandTolerance(row) {
    if (row.lo != null && row.hi != null) return (row.hi - row.lo) / 2;
    if (row.hi != null && isNum(row.ref)) return Math.abs(row.hi - row.ref);
    if (row.lo != null && isNum(row.ref)) return Math.abs(row.ref - row.lo);
    return null;
}

/** Every number of two verdicts (generic and family), port against Blender: { ok, rows: [{ metric, port, blender,
 * diff, tol, why, ok }], verdicts: [port passed, Blender passed] }. floorEntry: floor.json's recipes[r].seeds[s]
 * (its `judge` holds each number's largest change over the perturbed runs). */
export function compareVerdicts(port, blender, floorEntry = null) {
    const rows = [];
    const bands = new Map(blender.rows.filter((r) => r.passed !== null).map((r) => [r.metric, r]));
    const n = blender.extent_m / blender.pixel_m;
    const binRatio = Math.pow(0.5 * n, 1 / 48);                // radial_spectrum: 48 log bands from 1 / extent to Nyquist
    for (const kind of ['generated', 'generated_family']) {
        const pb = port.numbers?.[kind] ?? {}, bb = blender.numbers?.[kind] ?? {};
        for (const [metric, b] of Object.entries(bb)) {
            const p = pb[metric];
            if (Array.isArray(b)) {
                rows.push({ metric, port: p, blender: b, ok: JSON.stringify(p) === JSON.stringify(b), why: 'equal' });
                continue;
            }
            if (!isNum(b) || !isNum(p)) {
                rows.push({ metric, port: p ?? null, blender: b, ok: p === b || (p == null && b == null), why: 'equal (not a number)' });
                continue;
            }
            const change = floorEntry?.judge?.[metric]?.max_change ?? 0;
            let tol = Math.max(1.25 * change, 1e-4 * Math.abs(b)), why = change ? '1.25 x the floor\'s largest change' : '1e-4 of the number';
            if (1.25 * change < 1e-4 * Math.abs(b)) why = '1e-4 of the number';
            let ok;
            if (metric === 'spectrum_knee_m' || metric === 'spectrum_peak_m') {
                const bandsApart = Math.abs(Math.log(p / b)) / Math.log(binRatio);
                ok = bandsApart <= 1.0 + 1e-6 || Math.abs(p - b) <= tol;
                rows.push({ metric, port: p, blender: b, diff: Math.abs(p - b), tol, bands_apart: +bandsApart.toFixed(3), why: `one band of the spectrum, or ${why}`, ok });
                continue;
            }
            const row = bands.get(metric), bt = row ? bandTolerance(row) : null;
            if (bt != null && 0.01 * bt > tol) { tol = 0.01 * bt; why = '1 % of the band\'s tolerance'; }
            ok = Math.abs(p - b) <= tol;
            rows.push({ metric, port: p, blender: b, diff: Math.abs(p - b), tol, why, ok });
        }
    }
    return { ok: rows.every((r) => r.ok), rows, failures: rows.filter((r) => !r.ok).map((r) => r.metric),
        verdicts: [port.passed, blender.passed] };
}

/** The distribution class (plan 5.3): verdicts over seeds 1-4 of the port and of Blender. { ok, means: [{ metric,
 * port, blender, tol, ok }], bands: [{ metric, blender_passes, port_passes, ok }] }. */
export function compareDistribution(port, blender) {
    const means = [], bands = [];
    const metrics = blender[0].rows.filter((r) => r.passed !== null).map((r) => r.metric);
    for (const metric of metrics) {
        const val = (vs) => vs.map((v) => v.rows.find((r) => r.metric === metric)).filter((r) => r && isNum(r.gen));
        const pr = val(port), br = val(blender);
        if (!pr.length || !br.length) continue;
        const mean = (rs) => rs.reduce((s, r) => s + r.gen, 0) / rs.length;
        const bt = br.map(bandTolerance).filter((x) => x != null);
        const tol = bt.length ? 0.5 * (bt.reduce((s, x) => s + x, 0) / bt.length) : null;
        const mp = mean(pr), mb = mean(br);
        means.push({ metric, port: mp, blender: mb, tol, ok: tol == null || Math.abs(mp - mb) <= tol });
        const bp = br.filter((r) => r.passed).length, pp = pr.filter((r) => r.passed).length;
        const need = Math.ceil(0.75 * br.length);
        bands.push({ metric, blender_passes: bp, port_passes: pp, of: [br.length, pr.length], ok: bp < need || pp >= Math.ceil(0.75 * pr.length) });
    }
    return { ok: means.every((m) => m.ok) && bands.every((b) => b.ok), means, bands };
}

// the floor's base runs: [{ recipe, seed, dir }] (the newest Blender key, tests/_where.mjs parityKeyDir)
function floorBases(recipes, seeds) {
    const key = W.parityKeyDir();
    if (!key) return [];
    const out = [];
    for (const e of [...Deno.readDirSync(key)].sort((a, b) => (a.name < b.name ? -1 : 1))) {
        const m = /^(.+)_s(\d+)_draft$/.exec(e.name);
        if (!e.isDirectory || !m || !seeds.includes(m[2]) || (recipes && !recipes.includes(m[1]))) continue;
        const dir = `${key}/${e.name}/base`;
        if (W.exists(`${dir}/done.json`) && W.exists(`${dir}/terrain.npz`)) out.push({ recipe: m[1], seed: m[2], dir });
    }
    return out;
}

/** --resave: each floor base run's Blender save loaded by the port and written again by it (a GPU job: Terrain.load
 * builds the ring mesh). [{ recipe, seed, blender, port, seconds }]; <dir>/resaved.json lists them. */
export async function resave(outDir, { recipes = null, seeds = ['1', '2'] } = {}) {
    const { Terrain } = await import('../../api.js');
    const G = await import('../../core/gpu.js');
    Deno.mkdirSync(outDir, { recursive: true });
    const done = [];
    for (const b of floorBases(recipes, seeds)) {
        const t0 = performance.now();
        const t = await Terrain.load(`${b.dir}/terrain`, { build: false, log: () => {} });
        const port = `${outDir}/${b.recipe}_s${b.seed}`;
        await t.save(port);
        t.dispose();
        done.push({ recipe: b.recipe, seed: Number(b.seed), blender: `${b.dir}/terrain`, port,
            seconds: +((performance.now() - t0) / 1000).toFixed(2) });
        console.log(`[resave] ${b.recipe} seed ${b.seed}: loaded and saved by the port in ${done[done.length - 1].seconds} s`);
    }
    Deno.writeTextFileSync(`${outDir}/resaved.json`, JSON.stringify({ date: new Date().toISOString(), saves: done }, null, 1));
    G.shutdown();
    return done;
}

/** --judge-saves: the port's saves in outDir (resaved.json) judged and compared with their Blender saves: the
 * numbers (compareVerdicts with the floor's entry) and every array (field_parity.compareSaves). */
export async function judgeSaves(outDir, { recipes = null } = {}) {
    const FP = await import('../parity/field_parity.mjs');
    const list = C.readJson(`${outDir}/resaved.json`, { saves: [] }).saves.filter((s) => !recipes || recipes.includes(s.recipe));
    const key = W.parityKeyDir();
    const floor = C.readJson(key ? `${key}/floor.json` : '', null);
    const rows = [];
    for (const s of list) {
        const rec = floor?.recipes?.[s.recipe] ?? null, ent = rec?.seeds?.[String(s.seed)] ?? null;
        const fp = await FP.compareSaves(s.blender, s.port, { floorEntry: ent, class_: rec?.class_ ?? null });
        const arraysEqual = fp.plan_equal && !fp.only_a.length && !fp.only_b.length && fp.levels.every((l) => l.bit_identical) &&
            fp.fields.every((f) => f.max_abs === 0);
        const row = { recipe: s.recipe, seed: s.seed, class_: rec?.class_ ?? null, plan_equal: fp.plan_equal,
            arrays_identical: arraysEqual, arrays_compared: fp.fields.length + fp.levels.length, field_parity_ok: fp.ok };
        const bv = C.readJson(`${s.blender.replace(/\/terrain$/, '')}/verdict.json`);
        if (bv) {
            const v = await judgeSave(s.port, { recipe: s.recipe, label: `${s.recipe}_seed${s.seed}`, outDir: `${outDir}/judge_${s.recipe}_s${s.seed}`,
                sourceChain: s.recipe === 'real_place' ? false : undefined });
            if (!v) {
                row.judge = 'the judge failed: see its judge.log';
            } else {
                const c = compareVerdicts(v, bv, ent);
                let same = 0, n = 0;
                for (const kind of ['generated', 'generated_family']) {
                    for (const [k, b] of Object.entries(bv.numbers?.[kind] ?? {})) {
                        n++;
                        if (JSON.stringify(v.numbers?.[kind]?.[k]) === JSON.stringify(b)) same++;
                    }
                }
                Object.assign(row, { numbers: n, numbers_bit_equal: same, numbers_within_tolerance: c.ok, failures: c.failures,
                    verdicts: c.verdicts, judge_note: v.judge_note ?? null });
            }
        } else {
            row.judge = 'no reference: the recipe has no Blender verdict (meadow)';
        }
        rows.push(row);
        console.log(`[judge-saves] ${s.recipe} seed ${s.seed}: arrays ${arraysEqual ? 'byte for byte the Blender save\'s' : 'DIFFER'}` +
            (row.numbers ? `, judge numbers ${row.numbers_bit_equal}/${row.numbers} bit-equal, ${row.numbers_within_tolerance ? 'all within tolerance' : 'OVER: ' + row.failures.join(', ')}` : `, ${row.judge}`));
    }
    const ok = rows.every((r) => r.arrays_identical && (r.numbers == null || (r.numbers_within_tolerance && r.numbers_bit_equal === r.numbers)));
    Deno.writeTextFileSync(`${W.out('parity')}/judge_port_saves.json`, JSON.stringify({ date: new Date().toISOString(), dir: outDir,
        saves: rows.length, ok, rows }, null, 1));
    return { ok, rows };
}

function printComparison(c, limit = 60) {
    for (const r of c.rows.slice(0, limit)) {
        if (typeof r.port !== 'number') continue;
        console.log(`  ${r.ok ? 'ok  ' : 'OVER'} ${r.metric.padEnd(26)} ${String(+r.port.toPrecision(7)).padStart(13)} ${String(+r.blender.toPrecision(7)).padStart(13)}  |d| ${C.sci(r.diff, 2)} <= ${C.sci(r.tol, 2)} (${r.why})`);
    }
}

async function selfcheck(dir, withRunPy) {
    const T = new C.Checks('judge/adapter selfcheck');
    const info = C.readJson(`${dir}/run.json`), mine = C.readJson(`${dir}/verdict.json`);
    if (!info || !mine) { console.log(`no run.json and verdict.json under ${dir} (a floor run's base folder of a recipe with a reference)`); return 2; }
    const outDir = `${W.out('judge')}/selfcheck_${info.recipe}_s${info.seed}`;
    const v = await judgeSave(`${dir}/terrain`, { recipe: info.recipe, label: `${info.recipe}_seed${info.seed}`, outDir });
    if (!v) return 2;
    // the same save judged in the run's own process (judge(t, ...) on the Terrain) and by the adapter (the saved file)
    const diffs = [];
    for (const kind of ['generated', 'reference', 'generated_family', 'reference_family']) {
        for (const [k, b] of Object.entries(mine.numbers?.[kind] ?? {})) {
            const p = v.numbers?.[kind]?.[k];
            if (JSON.stringify(p) !== JSON.stringify(b)) diffs.push(`${kind}.${k}: ${JSON.stringify(p)} vs ${JSON.stringify(b)}`);
        }
    }
    const rowsEq = JSON.stringify(v.rows) === JSON.stringify(mine.rows);
    T.ok(`${info.recipe} seed ${info.seed}: the adapter's numbers on Blender's own save equal the numbers of the run's own judge() call, every one, bit for bit`,
        !diffs.length && rowsEq && v.passed === mine.passed, diffs.slice(0, 4).join('; ') ||
        `${Object.keys(mine.numbers.generated).length} generic and ${Object.keys(mine.numbers.generated_family ?? {}).length} family numbers, ${mine.rows.length} rows; verdict ${v.passed ? 'PASS' : 'FAIL'}; numpy ${v.versions?.numpy}`);
    const c = compareVerdicts(v, mine, null);
    T.ok('compareVerdicts of a verdict with itself passes', c.ok && c.rows.length > 20, `${c.rows.length} numbers`);
    if (withRunPy) {
        const edition = W.blenderEdition(), py = W.which('python') ?? W.which('python3');
        const rdir = `${outDir}/runpy`;
        Deno.mkdirSync(rdir, { recursive: true });
        const argv = [py, `${edition}/blender/tests/terrain/judge/run.py`, '--field', `${dir}/terrain.npz`, '--reference', mine.reference, '--no-render', '--out', rdir];
        if (info.recipe === 'real_place') console.log('  (run.py --field applies the source chain; a real_place save is judged without it by the adapter)');
        const code = py ? await W.run(argv, { cwd: edition, log: `${rdir}/run.log` }) : -1;
        const rv = C.readJson(`${rdir}/verdicts.json`)?.[0];
        if (!rv) {
            T.ok('judge/run.py --field --no-render on the same save (the Python on the path)', false, `exit ${code}: see ${rdir}/run.log`);
        } else {
            let worst = 0, worstKey = '', n = 0;
            for (const [k, b] of Object.entries(rv.numbers.generated)) {
                const p = v.numbers.generated[k];
                if (!isNum(b) || !isNum(p)) continue;
                n++;
                const e = Math.abs(p - b) / Math.max(Math.abs(b), 1e-300);
                if (e > worst) { worst = e; worstKey = k; }
            }
            const sys = C.readJson(`${rdir}/verdicts.json`);
            T.ok('the adapter\'s numbers equal judge/run.py\'s on the same save (run.py under the Python on the path, whose numpy may be another)',
                worst <= 1e-9 && !!sys, `${n} numbers, the largest relative difference ${C.sci(worst)}${worstKey ? ' (' + worstKey + ')' : ''}; run.py exit ${code}`);
        }
    }
    return C.finish(T, `judge_selfcheck_${info.recipe}_s${info.seed}`, { run: dir });
}

if (import.meta.main) {
    const args = [...Deno.args];
    const flag = (n) => { const i = args.indexOf(n); if (i < 0) return false; args.splice(i, 1); return true; };
    const opt = (n) => { const i = args.indexOf(n); return i >= 0 ? args.splice(i, 2)[1] : null; };
    const self = opt('--selfcheck'), runpy = flag('--runpy'), all = flag('--selfcheck-all'), seedsOpt = opt('--seeds');
    const resaveDir = opt('--resave'), judgeDir = opt('--judge-saves'), recipesOpt = opt('--recipes')?.split(',') ?? null;
    if (self) Deno.exit(await selfcheck(W.absPath(self), runpy));
    if (resaveDir) {
        const done = await resave(W.absPath(resaveDir), { recipes: recipesOpt, seeds: (seedsOpt ?? '1,2').split(',') });
        console.log(`${done.length} Blender saves loaded and written again by the port -> ${W.absPath(resaveDir)}`);
        Deno.exit(done.length ? 0 : 2);
    }
    if (judgeDir) {
        const r = await judgeSaves(W.absPath(judgeDir), { recipes: recipesOpt });
        console.log(`${r.rows.length} port saves: ${r.ok ? 'every array byte for byte the Blender save\'s and every judge number equal' : 'NOT all equal: see judge_port_saves.json'}`);
        Deno.exit(r.ok ? 0 : 1);
    }
    if (all) {
        const key = W.parityKeyDir();
        if (!key) { console.log('no floor runs: tests/parity/floor_runs.sh makes them'); Deno.exit(2); }
        const seeds = (seedsOpt ?? '1,2').split(',').filter(Boolean);
        const runs = [];
        for (const e of [...Deno.readDirSync(key)].sort((a, b) => (a.name < b.name ? -1 : 1))) {
            const m = /^(.+)_s(\d+)_draft$/.exec(e.name);
            if (!e.isDirectory || !m || !seeds.includes(m[2])) continue;
            const dir = `${key}/${e.name}/base`;
            if (!W.exists(`${dir}/verdict.json`)) continue;              // meadow has no reference
            const code = await selfcheck(dir, runpy);
            const res = C.readJson(`${W.out('parity')}/judge_selfcheck_${m[1]}_s${m[2]}.json`, {});
            runs.push({ recipe: m[1], seed: Number(m[2]), ok: code === 0, failed: res.failed ?? ['no result'],
                rows: (res.rows ?? []).map((r) => ({ check: r.check.split(': ').slice(1).join(': ') || r.check, passed: r.passed, detail: r.detail })) });
        }
        const bad = runs.filter((r) => !r.ok);
        Deno.writeTextFileSync(`${W.out('parity')}/judge_selfcheck_all.json`, JSON.stringify({ date: new Date().toISOString(),
            key, runpy, runs: runs.length, passed: runs.length - bad.length, failed: bad.map((r) => `${r.recipe} s${r.seed}`), results: runs }, null, 1));
        console.log(`judge adapter: ${runs.length - bad.length} of ${runs.length} Blender saves judged equal to their runs' own verdicts` +
            (runpy ? ' and to judge/run.py --field' : '') + (bad.length ? `; FAILED: ${bad.map((r) => `${r.recipe} s${r.seed}`).join(', ')}` : ''));
        Deno.exit(bad.length ? 1 : 0);
    }
    const recipe = opt('--recipe'), reference = opt('--reference'), against = opt('--against'), seed = opt('--seed') ?? '1',
        floorFile = opt('--floor'), outDir = opt('--out');
    if (!args.length || !(recipe || reference)) {
        console.log('usage: judge.mjs <save> (--recipe R | --reference N) [--against <verdict.json>] [--seed S] [--floor <floor.json>] [--out <dir>]\n' +
            '       judge.mjs --selfcheck <floor run>/base [--runpy]');
        Deno.exit(2);
    }
    const v = await judgeSave(args[0], { recipe, reference, outDir: outDir ? W.absPath(outDir) : undefined,
        sourceChain: recipe === 'real_place' ? false : undefined });
    if (!v) Deno.exit(2);
    const judged = v.rows.filter((r) => r.passed !== null);
    console.log(`${v.label} vs ${v.reference} (${v.family}): ${v.passed ? 'PASS' : 'FAIL'} (${judged.filter((r) => r.passed).length}/${judged.length} bands)`);
    for (const r of judged) console.log(`  ${r.passed ? 'PASS' : 'FAIL'} ${r.metric.padEnd(26)} generated ${String(+Number(r.gen).toPrecision(6)).padStart(12)}  reference ${String(+Number(r.ref).toPrecision(6)).padStart(12)}  band ${r.band}`);
    const base = recipe ? W.floorRun(recipe, Number(seed), 'base') : null;
    const bv = C.readJson(against ?? (base ? `${base}/verdict.json` : ''));
    if (!bv) {
        console.log('no Blender verdict to compare with (--against <verdict.json>, or the floor\'s base run of the recipe and seed)');
        Deno.exit(0);
    }
    const key = W.parityKeyDir();
    const floor = C.readJson(floorFile ?? (key ? `${key}/floor.json` : ''));
    const rec = floor?.recipes?.[recipe];
    const c = compareVerdicts(v, bv, rec?.seeds?.[seed] ?? null);
    console.log(`against the Blender save's numbers (${rec ? `the floor's class: ${rec.class_}` : 'no floor entry: 1e-4 and the quantisation steps only'}):`);
    printComparison(c);
    console.log(rec?.class_ === 'distribution' ? 'a distribution-class recipe: the gate is compareDistribution over seeds 1-4, not this single seed'
        : (c.ok ? 'PASS: every number within its tolerance' : `FAIL: ${c.failures.join(', ')}`));
    Deno.exit(c.ok || rec?.class_ === 'distribution' ? 0 : 1);
}
