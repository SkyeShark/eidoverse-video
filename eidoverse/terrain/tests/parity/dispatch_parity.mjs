// Dispatch-log parity (PORT_PLAN.md 5.7): what a solver asks of the GPU, compared directly. Two runs' logs of every
// dispatch (op, kernel, uniforms, bound images) and every readback are set side by side, op call by op call:
//   1. the sequence of kernels (run-length encoded, repeated blocks folded): names and order equal; counts equal,
//      except in a loop that stops on a convergence test, whose count may differ by whole test intervals;
//   2. every uniform: within 4 float32 steps up to the first uniform computed from a readback; after it, within
//      1.25 x the largest relative change the floor samples show for that uniform (never below 4 steps);
//   3. every readback's summary (min, max, sum);
//   4. the bound images' names, sizes and formats: equal.
// The port's own kernels (prims, the GPU replacements of numpy code: `blender_kernel` false in its log) are set
// aside first: they replace numpy code Blender runs on the CPU and have no Blender dispatch to match.
//
//     deno run --no-config --no-lock --allow-all eidoverse/terrain/tests/parity/dispatch_parity.mjs <run A> <run B>
//          [--floor <dispatch_floor.json>] [--out <json>]
//                 A the Blender run (a folder with dispatch_log.jsonl.gz and readbacks.jsonl.gz: a floor run's base/),
//                 B the port's run (tests/parity/replay.mjs PortLog writes the same files) or another Blender run
//     deno run ... dispatch_parity.mjs --floor-of <key>/<recipe>_s<seed>_<quality>
//                 the Blender edition against itself: base/ against each p<k>/; writes base/dispatch_floor.json
//                 (which counts move, by how much, and each uniform's largest relative change), the tolerances of
//                 point 2 and the measured answer to "which loops stop on a convergence test"
//
// As a module: compareLogs(a, b, { floor }) with a and b from loadRun(dir); floorOf(runDir). Exit code 0 when B
// passes, 1 when it does not, 2 on a missing input. JavaScript per dispatch (a test tool).

import * as C from './_common.mjs';

const OUTSIDE = new Set(['<prepare>', '<runner>', '<masks>', '<after>']);
export const ULPS = 4;

/** A run's log: { dir, dispatches: [[op, kernel, uniforms, images, samplers, meta]], readbacks, kernels }. */
export async function loadRun(dir) {
    const dl = `${dir}/dispatch_log.jsonl.gz`;
    if (!C.W.exists(dl)) return null;
    const dispatches = await C.readJsonLinesGz(dl);
    const rb = `${dir}/readbacks.jsonl.gz`;
    return { dir, dispatches, readbacks: C.W.exists(rb) ? await C.readJsonLinesGz(rb) : [],
        kernels: C.readJson(`${dir}/kernels.json`, {}) };
}

// the op call (or the runner's own stretch of work) a dispatch belongs to
function groupKey(d) {
    const m = d[5] ?? {};
    if (m.call != null && !OUTSIDE.has(d[0])) return `call ${m.call}`;
    return `${d[0]} L${m.level ?? '-'} p${m.pass ?? '-'}${m.end ? ' ' + m.end : ''}`;
}

/** The dispatches of Blender kernels grouped by op call, in order: [{ key, op, level, pass, items: [dispatch] }]. */
export function groups(run) {
    const out = [];
    let cur = null;
    run.dispatches.forEach((d, index) => {
        if (d[5]?.blender_kernel === false) return;
        const key = groupKey(d);
        if (!cur || cur.key !== key) {
            cur = { key, op: d[0], level: d[5]?.level ?? null, pass: d[5]?.pass ?? null, end: d[5]?.end ?? null, items: [] };
            out.push(cur);
        }
        cur.items.push({ d, index });
    });
    return out;
}

// run-length encoding of a group's kernels: [{ kernel, count, first (index into items) }]
function rle(items) {
    const out = [];
    for (let i = 0; i < items.length; i++) {
        const k = items[i].d[1];
        if (out.length && out[out.length - 1].kernel === k) out[out.length - 1].count++;
        else out.push({ kernel: k, count: 1, first: i });
    }
    return out;
}

// fold repeated blocks of up to 8 runs: [{ block: [{kernel, count}], repeat, first }]; a plain run is a block of one
function fold(runs) {
    const out = [];
    let i = 0;
    const same = (a, b) => a.kernel === b.kernel && a.count === b.count;
    while (i < runs.length) {
        let best = null;
        for (let p = 1; p <= 8 && i + 2 * p <= runs.length; p++) {
            let r = 1;
            for (;;) {
                let ok = i + (r + 1) * p <= runs.length;
                for (let q = 0; ok && q < p; q++) ok = same(runs[i + q], runs[i + r * p + q]);
                if (!ok) break;
                r++;
            }
            if (r > 1 && (!best || r * p > best.r * best.p)) best = { p, r };
        }
        if (best) {
            out.push({ block: runs.slice(i, i + best.p).map((x) => ({ kernel: x.kernel, count: x.count })), repeat: best.r, first: runs[i].first });
            i += best.p * best.r;
        } else {
            out.push({ block: [{ kernel: runs[i].kernel, count: runs[i].count }], repeat: 1, first: runs[i].first });
            i++;
        }
    }
    return out;
}

const text = (f) => f.map((b) => (b.block.length === 1 && b.repeat === 1 ? `${b.block[0].kernel} x${b.block[0].count}`
    : `(${b.block.map((x) => `${x.kernel} x${x.count}`).join(', ')}) x${b.repeat}`)).join(', ');

// the float32 steps between two numbers (0 when equal; Infinity when one is not finite and they differ)
function steps(a, b) {
    if (a === b) return 0;
    if (typeof a !== 'number' || typeof b !== 'number' || !Number.isFinite(a) || !Number.isFinite(b)) return Infinity;
    return Math.abs(a - b) / C.ulp32(Math.max(Math.abs(a), Math.abs(b)));
}
const rel = (a, b) => (a === b ? 0 : Math.abs(a - b) / Math.max(Math.abs(a), Math.abs(b), 1e-300));

// two dispatches of the same kernel: their uniforms and images compared; fills `acc`
function compareDispatch(a, b, gkey, acc) {
    const ua = new Map(a.d[2]), ub = new Map(b.d[2]);
    for (const [name, va] of ua) {
        if (!ub.has(name)) { acc.structure.push(`${gkey}: ${a.d[1]}: uniform ${name} is not in B`); continue; }
        const vb = ub.get(name);
        const xa = Array.isArray(va) ? va : [va], xb = Array.isArray(vb) ? vb : [vb];
        let s = xa.length === xb.length ? 0 : Infinity, r = 0;
        for (let i = 0; i < Math.min(xa.length, xb.length); i++) {
            s = Math.max(s, steps(xa[i], xb[i]));
            r = Math.max(r, rel(xa[i], xb[i]));
        }
        if (s === 0) continue;
        const key = `${gkey}|${a.d[1]}|${name}`;
        const e = acc.uniforms.get(key) ?? { group: gkey, op: a.d[0], kernel: a.d[1], uniform: name, steps: 0, rel: 0, n: 0,
            firstIndex: a.index, a: va, b: vb };
        e.n++;
        if (s > e.steps) { e.steps = s; e.a = va; e.b = vb; }
        e.rel = Math.max(e.rel, r);
        acc.uniforms.set(key, e);
        if (s > ULPS && (acc.firstOver === null || a.index < acc.firstOver.index)) {
            acc.firstOver = { index: a.index, group: gkey, op: a.d[0], kernel: a.d[1], uniform: name, a: va, b: vb, steps: s };
        }
    }
    for (const name of ub.keys()) if (!ua.has(name)) acc.structure.push(`${gkey}: ${a.d[1]}: uniform ${name} is not in A`);
    const ia = JSON.stringify(a.d[3]), ib = JSON.stringify(b.d[3]);
    if (ia !== ib && acc.images.length < 20) acc.images.push(`${gkey}: ${a.d[1]}: images ${ia} in A, ${ib} in B`);
    const sa = JSON.stringify(a.d[4]), sb = JSON.stringify(b.d[4]);
    if (sa !== sb && acc.images.length < 20) acc.images.push(`${gkey}: ${a.d[1]}: samplers ${sa} in A, ${sb} in B`);
    acc.compared++;
}

/** Compare two runs' logs (see the top). opts.floor: a dispatch_floor.json's content (the tolerances of the uniforms
 * after a readback, and the counts that move). Returns the report; report.ok is the verdict. */
export function compareLogs(A, B, opts = {}) {
    const ga = groups(A), gb = groups(B);
    const floor = opts.floor ?? null;
    const acc = { uniforms: new Map(), firstOver: null, structure: [], images: [], compared: 0 };
    const counts = [];                       // counts that differ: { group, op, kernel, a, b, kind }
    const rows = [];
    for (let i = 0; i < Math.max(ga.length, gb.length); i++) {
        const a = ga[i], b = gb[i];
        if (!a || !b) {
            acc.structure.push(`${(a ?? b).key} (${(a ?? b).op}): only in ${a ? 'A' : 'B'}`);
            continue;
        }
        if (a.key !== b.key || a.op !== b.op) {
            acc.structure.push(`op call ${i}: A is ${a.key} (${a.op}), B is ${b.key} (${b.op})`);
            continue;
        }
        const ra = rle(a.items), rb = rle(b.items);
        const fa = fold(ra), fb = fold(rb);
        const row = { group: a.key, op: a.op, level: a.level, pass: a.pass, dispatches: [a.items.length, b.items.length] };
        // 1. the kernel sequence: equal as folded blocks, or equal as plain runs
        let aligned = null;
        if (ra.length === rb.length && ra.every((x, k) => x.kernel === rb[k].kernel)) {
            aligned = ra.map((x, k) => [x, rb[k]]);
            ra.forEach((x, k) => {
                if (x.count !== rb[k].count) counts.push({ group: a.key, op: a.op, kernel: x.kernel, a: x.count, b: rb[k].count, run: k, kind: 'run' });
            });
        } else if (fa.length === fb.length && fa.every((x, k) => x.block.length === fb[k].block.length &&
            x.block.every((y, q) => y.kernel === fb[k].block[q].kernel))) {
            fa.forEach((x, k) => {
                const y = fb[k];
                if (x.repeat !== y.repeat) counts.push({ group: a.key, op: a.op, kernel: x.block.map((z) => z.kernel).join('+'), a: x.repeat, b: y.repeat, run: k, kind: 'block repeats' });
                x.block.forEach((z, q) => {
                    if (z.count !== y.block[q].count) counts.push({ group: a.key, op: a.op, kernel: z.kernel, a: z.count, b: y.block[q].count, run: k, kind: 'run in a block' });
                });
            });
            row.folded = true;
        } else {
            row.sequence = { a: text(fa).slice(0, 600), b: text(fb).slice(0, 600) };
            acc.structure.push(`${a.key} (${a.op}): the kernel sequences differ: A ${row.sequence.a} | B ${row.sequence.b}`);
        }
        // 2 and 4. uniforms and images of the dispatches that pair up
        if (aligned) {
            for (const [x, y] of aligned) {
                for (let k = 0; k < Math.min(x.count, y.count); k++) compareDispatch(a.items[x.first + k], b.items[y.first + k], a.key, acc);
            }
        } else if (row.folded) {
            // pair by position while the kernels agree
            for (let k = 0; k < Math.min(a.items.length, b.items.length) && a.items[k].d[1] === b.items[k].d[1]; k++) {
                compareDispatch(a.items[k], b.items[k], a.key, acc);
            }
        }
        rows.push(row);
    }
    // the counts: equal, or a loop the floor (or opts.intervals) knows to stop on a convergence test
    const moving = new Map(Object.entries(floor?.counts_that_move ?? {}));
    const countFails = [];
    for (const c of counts) {
        const known = moving.get(`${c.op}|${c.kernel}`) ?? opts.intervals?.[`${c.op}|${c.kernel}`] ?? opts.intervals?.[c.kernel] ?? null;
        const step = known?.interval ?? known ?? null;
        c.allowed = step ? (Math.abs(c.a - c.b) % step === 0) : false;
        if (!c.allowed) countFails.push(c);
    }
    // the uniforms: 4 steps before the first readback-dependent one; the floor's change after it
    const uniformFails = [];
    const fl = floor?.uniforms ?? {};
    for (const e of acc.uniforms.values()) {
        if (e.steps <= ULPS) continue;
        const f = fl[`${e.op}|${e.kernel}|${e.uniform}`];
        e.floor_rel = f?.rel ?? null;
        e.allowed = f ? e.rel <= 1.25 * f.rel : false;
        if (!e.allowed) uniformFails.push(e);
    }
    // 3. readbacks, by order within (op, name)
    const rbA = new Map(), rbB = new Map();
    for (const [run, map] of [[A, rbA], [B, rbB]]) {
        for (const r of run.readbacks) {
            const k = `${r[1]}|${r[2]}|${r[3]}x${r[4]}x${r[5]}`;
            if (!map.has(k)) map.set(k, []);
            map.get(k).push(r[6]);
        }
    }
    const readbacks = [];
    for (const [k, la] of rbA) {
        const lb = rbB.get(k) ?? [];
        let worst = 0;
        for (let i = 0; i < Math.min(la.length, lb.length); i++) {
            for (let q = 0; q < 3; q++) if (la[i][q] != null && lb[i][q] != null) worst = Math.max(worst, rel(la[i][q], lb[i][q]));
        }
        readbacks.push({ key: k, a: la.length, b: lb.length, worst_rel: worst });
    }
    const uniformList = [...acc.uniforms.values()].sort((x, y) => y.steps - x.steps);
    const report = {
        a: A.dir, b: B.dir, dispatches: [A.dispatches.length, B.dispatches.length], op_calls: [ga.length, gb.length],
        compared_dispatches: acc.compared,
        same_kernel_sequence: acc.structure.length === 0 && counts.length === 0,
        structure_differences: acc.structure.slice(0, 40), counts_that_differ: counts.slice(0, 200), count_failures: countFails.length,
        image_differences: acc.images,
        uniforms_that_differ: uniformList.length, uniforms_over_4_steps: uniformList.filter((e) => e.steps > ULPS).length,
        first_uniform_over_4_steps: acc.firstOver, uniform_failures: uniformFails.slice(0, 40),
        worst_uniforms: uniformList.slice(0, 12).map((e) => ({ group: e.group, op: e.op, kernel: e.kernel, uniform: e.uniform,
            steps: +e.steps.toPrecision(4), rel: +e.rel.toPrecision(4), dispatches: e.n, a: e.a, b: e.b, floor_rel: e.floor_rel ?? null })),
        readbacks: { a: A.readbacks.length, b: B.readbacks.length, keys: readbacks.length,
            worst: readbacks.sort((x, y) => y.worst_rel - x.worst_rel).slice(0, 8) },
        _uniforms: uniformList, _counts: counts,
    };
    report.ok = acc.structure.length === 0 && countFails.length === 0 && uniformFails.length === 0 && acc.images.length === 0;
    return report;
}

/** The Blender edition against itself: base/ against each p<k>/ of a floor run folder. Writes and returns
 * base/dispatch_floor.json: { samples, counts_that_move: { 'op|kernel': { interval, values, largest } }, uniforms:
 * { 'op|kernel|uniform': { rel (the largest relative change over the samples), steps } }, first_readback_uniform,
 * structure (kernel sequences that changed shape) }. */
export async function floorOf(runDir) {
    const base = await loadRun(`${runDir}/base`);
    if (!base) return null;
    const out = { run: runDir, samples: 0, counts_that_move: {}, uniforms: {}, first_uniform_over_4_steps: [], structure: [], per_sample: [] };
    const gcd = (a, b) => (b ? gcd(b, a % b) : a);
    for (let p = 1; p <= 9; p++) {
        const run = await loadRun(`${runDir}/p${p}`);
        if (!run) continue;
        out.samples++;
        const r = compareLogs(base, run);
        for (const c of r._counts) {
            const k = `${c.op}|${c.kernel}`;
            const e = out.counts_that_move[k] ?? (out.counts_that_move[k] = { interval: 0, largest: 0, kind: c.kind, examples: [] });
            e.interval = gcd(e.interval, Math.abs(c.a - c.b));
            e.largest = Math.max(e.largest, Math.abs(c.a - c.b));
            if (e.examples.length < 6) e.examples.push([c.a, c.b]);
        }
        for (const e of r._uniforms) {
            const k = `${e.op}|${e.kernel}|${e.uniform}`;
            const f = out.uniforms[k] ?? (out.uniforms[k] = { rel: 0, steps: 0 });
            f.rel = Math.max(f.rel, e.rel);
            f.steps = Math.max(f.steps, Number.isFinite(e.steps) ? e.steps : 0);
        }
        if (r.first_uniform_over_4_steps) out.first_uniform_over_4_steps.push({ pattern: p, ...r.first_uniform_over_4_steps });
        for (const s of r.structure_differences) if (out.structure.length < 20) out.structure.push(`p${p}: ${s}`);
        out.per_sample.push({ pattern: p, dispatches: r.dispatches, same_kernel_sequence: r.same_kernel_sequence,
            counts_that_differ: r._counts.length, uniforms_over_4_steps: r.uniforms_over_4_steps,
            structure_differences: r.structure_differences.length });
    }
    if (out.samples) Deno.writeTextFileSync(`${runDir}/base/dispatch_floor.json`, JSON.stringify(out, null, 1));
    return out;
}

if (import.meta.main) {
    const args = [...Deno.args];
    const opt = (name) => {
        const i = args.indexOf(name);
        return i >= 0 ? args.splice(i, 2)[1] : null;
    };
    const floorDir = opt('--floor-of'), floorFile = opt('--floor'), outFile = opt('--out');
    if (floorDir) {
        const f = await floorOf(C.W.absPath(floorDir));
        if (!f) { console.log(`no base/dispatch_log.jsonl.gz under ${floorDir}`); Deno.exit(2); }
        console.log(`${floorDir}: ${f.samples} perturbed run(s) against the base`);
        for (const s of f.per_sample) console.log(`  p${s.pattern}: ${s.dispatches[1]} dispatches (base ${s.dispatches[0]}); same kernel sequence ${s.same_kernel_sequence}; ${s.counts_that_differ} counts differ; ${s.uniforms_over_4_steps} uniforms over 4 float32 steps; ${s.structure_differences} op calls changed shape`);
        for (const [k, e] of Object.entries(f.counts_that_move)) console.log(`  count moves: ${k}: by multiples of ${e.interval} (largest ${e.largest}; ${e.kind}; e.g. ${JSON.stringify(e.examples.slice(0, 3))})`);
        const u = Object.entries(f.uniforms).sort((a, b) => b[1].rel - a[1].rel).slice(0, 8);
        for (const [k, e] of u) console.log(`  uniform moves: ${k}: up to ${C.sci(e.rel)} relative (${C.sci(e.steps, 2)} float32 steps)`);
        for (const s of f.structure) console.log(`  shape: ${s.slice(0, 300)}`);
        Deno.exit(0);
    }
    if (args.length < 2) {
        console.log('usage: dispatch_parity.mjs <run A> <run B> [--floor <dispatch_floor.json>] [--out <json>]  |  --floor-of <recipe run folder>');
        Deno.exit(2);
    }
    const [A, B] = [await loadRun(C.W.absPath(args[0])), await loadRun(C.W.absPath(args[1]))];
    if (!A || !B) { console.log(`no dispatch_log.jsonl.gz in ${!A ? args[0] : args[1]}`); Deno.exit(2); }
    const floor = floorFile ? C.readJson(floorFile) : C.readJson(`${A.dir}/dispatch_floor.json`);
    const r = compareLogs(A, B, { floor });
    delete r._uniforms;
    delete r._counts;
    if (outFile) Deno.writeTextFileSync(outFile, JSON.stringify(r, null, 1));
    console.log(`${r.ok ? 'PASS' : 'FAIL'} dispatch parity: ${r.dispatches[0]} and ${r.dispatches[1]} dispatches in ${r.op_calls[0]} and ${r.op_calls[1]} op calls; ` +
        `${r.compared_dispatches} paired; same kernel sequence ${r.same_kernel_sequence}; ${r.counts_that_differ.length} counts differ (${r.count_failures} not at a known convergence loop); ` +
        `${r.uniforms_over_4_steps} uniforms over 4 float32 steps (${r.uniform_failures.length} over the floor); ${r.image_differences.length} image differences`);
    for (const s of r.structure_differences.slice(0, 10)) console.log(`  shape: ${s.slice(0, 300)}`);
    for (const c of r.counts_that_differ.slice(0, 10)) console.log(`  count: ${c.group} ${c.op} ${c.kernel}: ${c.a} in A, ${c.b} in B (${c.kind})${c.allowed ? ' (a convergence loop)' : ''}`);
    if (r.first_uniform_over_4_steps) console.log(`  first uniform over 4 steps: dispatch ${r.first_uniform_over_4_steps.index}, ${r.first_uniform_over_4_steps.op} ${r.first_uniform_over_4_steps.kernel}.${r.first_uniform_over_4_steps.uniform}: ${JSON.stringify(r.first_uniform_over_4_steps.a)} in A, ${JSON.stringify(r.first_uniform_over_4_steps.b)} in B`);
    for (const e of r.uniform_failures.slice(0, 10)) console.log(`  uniform: ${e.group} ${e.op} ${e.kernel}.${e.uniform}: ${C.sci(e.rel)} relative (floor ${e.floor_rel == null ? 'none' : C.sci(e.floor_rel)})`);
    Deno.exit(r.ok ? 0 : 1);
}
