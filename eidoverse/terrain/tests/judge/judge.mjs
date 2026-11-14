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
    const self = opt('--selfcheck'), runpy = flag('--runpy');
    if (self) Deno.exit(await selfcheck(W.absPath(self), runpy));
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
