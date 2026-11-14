// core/np_random.js against numpy, draw for draw (PORT_PLAN.md 8.2, P1): fifty seeds in every form the terrain
// seeds default_rng with, every Generator method and call form it uses, in one stream per seed, and a long stream of
// a million normals and a million exponentials (np_random_expected.py made the numbers, with Blender's own Python and
// numpy: PORT_PLAN.md 5.1).
//
//     <blender>/<version>/python/bin/python -I eidoverse/terrain/tests/core_runner/np_random_expected.py
//     deno run --no-config --no-lock --allow-read --allow-write eidoverse/terrain/tests/core_runner/np_random_test.mjs [dir ...]
//
// No GPU. With no argument it reads every tests/out/core_runner/np_random_*/ it finds.
//
// The grade: the draws that are integer arithmetic and IEEE multiplies and adds (random, uniform, integers, choice,
// the ziggurats' first-test returns and their wedges) must be bit-equal. A draw that went through the C library's
// log1p (a ziggurat tail; np_random.js rounds it correctly, the C library on 99.85 % of inputs) may differ by an ulp
// where the C library rounds wrong: those are counted (none on these fixtures), and anything further, or any draw
// that falls out of step, fails.

import { NUMPY_VERSION, NpGenerator, defaultRng } from '../../core/np_random.js';
import { Checks, OUT, dirUrl } from './_common.mjs';

const T = new Checks('core_runner/np_random');

function dirs() {
    if (Deno.args.length) return Deno.args.map(dirUrl);
    const out = [];
    try {
        for (const e of Deno.readDirSync(OUT)) if (e.isDirectory && e.name.startsWith('np_random_')) out.push(new URL(e.name + '/', OUT));
    } catch (_e) { /* no outputs yet */ }
    return out.sort((a, b) => (a.href < b.href ? -1 : 1));
}

function draw(g, op) {
    const size = op.size ?? null;
    let v;
    if (op.m === 'random') v = g.random(size);
    else if (op.m === 'uniform') v = g.uniform(op.low, op.high, size);
    else if (op.m === 'integers') v = g.integers(op.low, op.high ?? null, size);
    else if (op.m === 'standard_normal') v = g.standard_normal(size);
    else if (op.m === 'normal') v = g.normal(op.loc, op.scale, size);
    else if (op.m === 'exponential') v = g.exponential(op.scale, size);
    else if (op.m === 'poisson') v = g.poisson(op.lam, size);
    else if (op.m === 'choice') v = g.choice(op.a, { size, replace: op.replace ?? true, p: op.p ?? null, shuffle: op.shuffle ?? true });
    else throw new Error(op.m);
    return typeof v === 'number' ? [v] : v;
}

const f64 = new Float64Array(1), u64 = new BigUint64Array(f64.buffer);
const ord = (v) => { f64[0] = v; const b = u64[0]; return b >> 63n ? -(b & 0x7fffffffffffffffn) : b; };
const ulps = (a, b) => { const d = ord(a) - ord(b); return Number(d < 0n ? -d : d); };

function replay(seedSpec, program, want, counts, stats) {
    const seed = typeof seedSpec === 'string' ? BigInt(seedSpec) : seedSpec;
    const g = new NpGenerator(seed);
    let at = 0, firstBad = null;
    program.forEach((op, k) => {
        const got = draw(g, op);
        const key = op.m === 'choice' ? 'choice' : op.m;
        const s = stats[key] ?? (stats[key] = { values: 0, exact: 0, within_1_ulp: 0, worse: 0 });
        if (got.length !== counts[k]) {
            s.worse += counts[k];
            firstBad = firstBad ?? `${op.m} #${k}: ${got.length} values, numpy drew ${counts[k]}`;
        } else {
            for (let i = 0; i < got.length; i++) {
                const w = want[at + i];
                s.values++;
                if (Object.is(got[i], w)) s.exact++;
                else if (ulps(got[i], w) <= 1) s.within_1_ulp++;
                else {
                    s.worse++;
                    firstBad = firstBad ?? `${op.m} #${k}[${i}]: ${got[i]} against numpy's ${w}`;
                }
            }
        }
        at += counts[k];
    });
    return firstBad;
}

const found = dirs();
if (!found.length) {
    console.log('SKIP: no expected draws. Make them with the Python whose numpy draws the plans (Blender\'s):\n' +
        '    <blender>/<version>/python/bin/python -I eidoverse/terrain/tests/core_runner/np_random_expected.py');
    Deno.exit(0);
}
T.extra.transcribed_from_numpy = NUMPY_VERSION;
T.extra.by_numpy = {};
T.extra.fixture_versions = {};
for (const dir of found) {
    const man = JSON.parse(Deno.readTextFileSync(new URL('manifest.json', dir)));
    const tag = `numpy ${man.numpy}`;
    T.extra.fixture_versions[tag] = { python: man.python ?? null, numpy: man.numpy ?? null, zlib: man.zlib ?? null };
    const load = (file) => new Float64Array(Deno.readFileSync(new URL(file, dir)).buffer);
    const stats = {};
    const bad = [];
    for (const c of man.cases) {
        const b = replay(c.seed, man.program, load(c.file), c.counts, stats);
        if (b) bad.push(`seed ${JSON.stringify(c.seed)}: ${b}`);
    }
    const longStats = {};
    const t0 = performance.now();
    const lb = replay(man.long.seed, man.long_program, load(man.long.file), man.long.counts, longStats);
    const longMs = performance.now() - t0;
    if (lb) bad.push(`long stream: ${lb}`);
    const exactOnly = ['random', 'uniform', 'integers', 'choice', 'poisson'];
    const sum = (st, k) => Object.values(st).reduce((n, s) => n + s[k], 0);
    T.ok(`${tag}: ${man.cases.length} seeds, every draw in step and within an ulp`, !bad.length, bad.slice(0, 3).join(' | '));
    for (const m of exactOnly) {
        T.ok(`${tag}: ${m} bit for bit`, stats[m] && stats[m].exact === stats[m].values, JSON.stringify(stats[m]));
    }
    for (const m of ['standard_normal', 'normal', 'exponential']) {
        const s = stats[m], l = longStats[m] ?? { values: 0, exact: 0, within_1_ulp: 0, worse: 0 };
        const all = { values: s.values + l.values, exact: s.exact + l.exact, within_1_ulp: s.within_1_ulp + l.within_1_ulp, worse: s.worse + l.worse };
        T.ok(`${tag}: ${m}: no draw further than an ulp from numpy's`, all.worse === 0 && all.exact + all.within_1_ulp === all.values,
            `${all.exact} of ${all.values} bit for bit, ${all.within_1_ulp} an ulp off (where the C library's log1p rounds wrong)`);
    }
    T.extra.by_numpy[man.numpy] = { python: man.python, seeds: man.cases.length, draws_per_seed: man.program.length,
        values: sum(stats, 'values') + sum(longStats, 'values'), exact: sum(stats, 'exact') + sum(longStats, 'exact'),
        within_1_ulp: sum(stats, 'within_1_ulp') + sum(longStats, 'within_1_ulp'), worse: sum(stats, 'worse') + sum(longStats, 'worse'),
        per_method: stats, long_stream: longStats, long_stream_ms: +longMs.toFixed(0) };
}

// ---- the generator's own rules (no numpy needed)
T.throws('a negative seed is refused, as numpy refuses it', () => new NpGenerator(-1), 'non-negative');
T.throws('no seed is refused', () => new NpGenerator(), 'a seed is needed');
T.throws('a fractional seed is refused', () => new NpGenerator(1.5), 'not an integer');
T.throws('integers: low >= high is refused', () => defaultRng(1).integers(5, 5), 'low >= high');
T.throws('choice: weights that do not sum to 1 are refused', () => defaultRng(1).choice(3, { p: [0.5, 0.2, 0.2] }), 'do not sum to 1');
T.throws('choice: a sample larger than the population is refused', () => defaultRng(1).choice(3, { size: 4, replace: false }), 'larger sample');
T.ok('the camelCase names are the same methods', NpGenerator.prototype.standardNormal === NpGenerator.prototype.standard_normal);
{
    // speed: what a plan that draws per cell would pay (volcanic.py draws standard_normal(np.shape(P)) four times)
    const g = defaultRng(7);
    let t = performance.now();
    g.standard_normal(1 << 20);
    const nMs = performance.now() - t;
    t = performance.now();
    g.random(1 << 20);
    const rMs = performance.now() - t;
    T.extra.speed = { standard_normal_ms_per_million: +(nMs / 1.048576).toFixed(1), random_ms_per_million: +(rMs / 1.048576).toFixed(1) };
    T.ok('speed: a million normals in under two seconds', nMs < 2000, `${nMs.toFixed(0)} ms for 2^20 normals, ${rMs.toFixed(0)} ms for 2^20 uniforms`);
}

Deno.exit(T.done('np_random_test.json'));
