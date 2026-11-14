// Whole-recipe field parity (PORT_PLAN.md 5.3 "recipe, field class", 5.4): two saved terrains of the same recipe
// and seed, level by level: RMS(h_b - h_a) / relief, the 99th percentile of |dh| / relief, and on every level with a
// drainage area the channel overlap (cells whose area is over max(1 km^2, 400 cells): intersection over union),
// against the tolerances the Blender edition's own chaos floor gives that recipe, seed and level (floor.json, made
// by blender_chaos_floor.py --summarise): RMS and p99 <= 1.25 x the largest of the floor's samples (never below
// 1e-4), overlap >= the smallest sample minus the samples' spread. Every other field the two saves share is listed
// with its largest difference over its range, for the eye.
//
//     deno run --no-config --no-lock --allow-all eidoverse/terrain/tests/parity/field_parity.mjs <save A> <save B>
//          [--floor <floor.json>] [--recipe R] [--seed S] [--out <json>]
//                 A the Blender edition's Terrain.save (<path>.npz + .json; a floor run's base/terrain), B the
//                 port's (or another Blender save). --recipe and --seed pick the floor's entry (default: the
//                 save's own recipe name and seed). Without a floor the numbers are printed and nothing is judged.
//
// As a module: compareSaves(aBase, bBase, { floorEntry }). A recipe of the distribution class (floor.json class_) is
// reported, not judged here: its fields differ by its own chaos, and the gate is the judge's numbers over seeds
// (tests/judge/judge.mjs). Exit code 0 when B passes or is not judged, 1 when it fails, 2 on a missing input.
// JavaScript per cell (a test tool); the saves are read entry by entry (core/io.js), never whole.

import * as IO from '../../core/io.js';
import * as C from './_common.mjs';

const bare = (name) => (name.endsWith('.npy') ? name.slice(0, -4) : name);
const strip = (p) => p.replace(/\.(npz|json)$/, '');

// np.percentile(a, q) for float64 data, a number q (linear): sorts a copy
function percentile(a, q) {
    const s = Float64Array.from(a).sort();
    const v = ((s.length - 1) * q) / 100, i = Math.floor(v), g = v - i;
    if (i + 1 >= s.length) return s[s.length - 1];
    const lo = s[i], hi = s[i + 1], d = hi - lo;
    return g >= 0.5 ? hi - d * (1 - g) : lo + d * g;
}

async function entry(path, name) {
    for (const key of [name, `${name}.npy`]) {
        const got = await IO.readNpz(path, { names: [key] });
        const k = Object.keys(got)[0];
        if (k) return got[k];
    }
    return null;
}

async function names(path) {
    return (await IO.npzDirectory(path)).map((e) => bare(e.name));
}

const f64 = (a) => (a.dtype === '<f8' ? a.data : Float64Array.from(a.data));

/** Compare two saves (their base paths, without .npz). Returns { levels: [...], fields: [...], ok, judged }. */
export async function compareSaves(aBase, bBase, opts = {}) {
    aBase = strip(aBase);
    bBase = strip(bBase);
    const ja = C.readJson(`${aBase}.json`), jb = C.readJson(`${bBase}.json`);
    if (!ja || !jb) throw new Error(`field_parity: no ${!ja ? aBase : bBase}.json`);
    const pa = ja.plan, pb = jb.plan;
    const planEqual = JSON.stringify(pa.map((l) => [l.index, l.role, l.x0, l.y0, l.side, l.cell, l.n])) ===
        JSON.stringify(pb.map((l) => [l.index, l.role, l.x0, l.y0, l.side, l.cell, l.n]));
    const na = new Set(await names(`${aBase}.npz`)), nb = new Set(await names(`${bBase}.npz`));
    const fl = opts.floorEntry ?? null;
    const out = { a: aBase, b: bBase, plan_equal: planEqual, levels: [], fields: [], only_a: [...na].filter((n) => !nb.has(n)),
        only_b: [...nb].filter((n) => !na.has(n)), class_: opts.class_ ?? null, judged: !!fl && opts.class_ !== 'distribution', ok: planEqual };
    if (!planEqual) return out;
    for (const lv of pa) {
        const i = lv.index, hk = `L${i}__f__h`;
        if (!na.has(hk) || !nb.has(hk)) continue;
        const ha = f64(await entry(`${aBase}.npz`, hk)), hb = f64(await entry(`${bBase}.npz`, hk));
        let lo = Infinity, hi = -Infinity, ss = 0, mx = 0;
        const ad = new Float64Array(ha.length);
        for (let q = 0; q < ha.length; q++) {
            const d = hb[q] - ha[q];
            ad[q] = Math.abs(d);
            ss += d * d;
            if (ad[q] > mx) mx = ad[q];
            if (ha[q] < lo) lo = ha[q];
            if (ha[q] > hi) hi = ha[q];
        }
        const relief = (hi - lo) || 1.0;
        const row = { index: i, role: lv.role, cell: lv.cell, n: lv.n, relief_m: hi - lo, rms_over_relief: Math.sqrt(ss / ha.length) / relief,
            p99_abs_over_relief: percentile(ad, 99) / relief, max_abs_m: mx, bit_identical: mx === 0, channel_overlap: null };
        const ak = `L${i}__f__A`;
        if (na.has(ak) && nb.has(ak)) {
            const Aa = (await entry(`${aBase}.npz`, ak)).data, Ab = (await entry(`${bBase}.npz`, ak)).data;
            const thr = Math.max(1e6, 400 * lv.cell * lv.cell);
            let inter = 0, union = 0;
            for (let q = 0; q < Aa.length; q++) {
                const x = Aa[q] > thr, y = Ab[q] > thr;
                if (x && y) inter++;
                if (x || y) union++;
            }
            row.channel_overlap = union ? inter / union : 1.0;
        }
        const f = fl?.levels?.find((x) => x.index === i);
        if (f && out.judged) {
            row.tol_rms = f.tol_rms;
            row.tol_p99 = f.tol_p99;
            row.overlap_min = f.overlap_min;
            row.ok = row.rms_over_relief <= f.tol_rms && row.p99_abs_over_relief <= f.tol_p99 &&
                (row.channel_overlap == null || f.overlap_min == null || row.channel_overlap >= f.overlap_min);
            if (!row.ok) out.ok = false;
        }
        out.levels.push(row);
    }
    // every other field and mask both saves hold: the largest difference over the range
    for (const name of [...na].filter((n) => nb.has(n) && !n.endsWith('__f__h')).sort()) {
        const a = await entry(`${aBase}.npz`, name), b = await entry(`${bBase}.npz`, name);
        if (a.data.length !== b.data.length) { out.fields.push({ name, shapes: [a.shape, b.shape] }); continue; }
        const g = C.gradeArray(b.data, a.data, { k: 0 });
        out.fields.push({ name, max_over_range: g.range ? g.err / g.range : (g.err ? Infinity : 0), max_abs: g.err, range: g.range });
    }
    return out;
}

if (import.meta.main) {
    const args = [...Deno.args];
    const opt = (n) => { const i = args.indexOf(n); return i >= 0 ? args.splice(i, 2)[1] : null; };
    const floorFile = opt('--floor'), recipeOpt = opt('--recipe'), seedOpt = opt('--seed'), outFile = opt('--out');
    if (args.length < 2) {
        console.log('usage: field_parity.mjs <save A> <save B> [--floor <floor.json>] [--recipe R] [--seed S] [--out <json>]');
        Deno.exit(2);
    }
    const [a, b] = args.map((p) => strip(C.W.absPath(p)));
    for (const p of [a, b]) if (!C.W.exists(`${p}.npz`) || !C.W.exists(`${p}.json`)) { console.log(`no ${p}.npz + .json`); Deno.exit(2); }
    const ja = C.readJson(`${a}.json`);
    const recipe = recipeOpt ?? ja.recipe?.name ?? ja.info?.recipe ?? null, seed = String(seedOpt ?? ja.info?.seed ?? ja.seed ?? 1);
    const key = C.W.parityKeyDir();
    const floor = C.readJson(floorFile ?? (key ? `${key}/floor.json` : ''));
    const rec = floor?.recipes?.[recipe];
    const r = await compareSaves(a, b, { floorEntry: rec?.seeds?.[seed] ?? null, class_: rec?.class_ ?? null });
    if (outFile) Deno.writeTextFileSync(outFile, JSON.stringify(r, null, 1));
    console.log(`${recipe ?? 'terrain'} seed ${seed}: ${r.plan_equal ? 'the same plan' : 'THE PLANS DIFFER'}` +
        (rec ? `; the floor's class: ${rec.class_} (largest main-level sample ${C.sci(rec.main_level_largest_rms)})` : '; no floor entry: not judged'));
    for (const l of r.levels) {
        console.log(`  L${l.index} ${l.role} ${l.cell} m: RMS ${C.sci(l.rms_over_relief)} of relief` + (l.tol_rms != null ? ` (<= ${C.sci(l.tol_rms)})` : '') +
            `, p99 ${C.sci(l.p99_abs_over_relief)}` + (l.tol_p99 != null ? ` (<= ${C.sci(l.tol_p99)})` : '') +
            (l.channel_overlap != null ? `, channel overlap ${l.channel_overlap.toFixed(3)}` + (l.overlap_min != null ? ` (>= ${l.overlap_min.toFixed(3)})` : '') : '') +
            (l.bit_identical ? ', bit-identical' : '') + (l.ok === false ? '   <-- OVER' : ''));
    }
    const worst = r.fields.filter((f) => f.max_over_range != null).sort((x, y) => y.max_over_range - x.max_over_range).slice(0, 6);
    if (worst.length) console.log('  other fields, largest difference over range: ' + worst.map((f) => `${f.name} ${C.sci(f.max_over_range, 2)}`).join(', '));
    if (r.only_a.length || r.only_b.length) console.log(`  only in A: ${r.only_a.length} arrays; only in B: ${r.only_b.length}` + (r.only_b.length ? ` (${r.only_b.slice(0, 6).join(', ')})` : ''));
    console.log(r.judged ? (r.ok ? 'PASS (field class)' : 'FAIL (field class)') : (rec?.class_ === 'distribution'
        ? 'not judged here: a distribution-class recipe (the judge\'s numbers over seeds decide)' : 'not judged (no floor entry)'));
    Deno.exit(r.judged && !r.ok ? 1 : 0);
}
