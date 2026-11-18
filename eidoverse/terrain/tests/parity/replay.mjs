// Stage replay (PORT_PLAN.md 5.1, 5.3, 5.7): a port op run once from the Blender edition's own input, its result
// against Blender's, with the port's dispatch log and step snapshots of the same call beside Blender's. The inputs
// are the stage dumps, logs and snapshots of a floor run's base (tests/parity/blender_chaos_floor.py).
//
//     import * as RP from '../parity/replay.mjs';
//     const run = await RP.loadRun(dir);                    // a floor run's base/ folder (W.floorRun(recipe, seed))
//     for (const st of run.stages.filter((s) => s.op === 'threshold')) {
//         const r = await RP.replayStage(R, G, run, st, op);    // op: the port's op, called as
//         ...                                                    // await op(fields, level, params, seed, ctx)
//     }
//     deno run --no-config --no-lock --unstable-webgpu --allow-all eidoverse/terrain/tests/parity/replay.mjs
//          <run>/base [--ops a,b] [--levels main|all|0,2] [--out <json>]
//                       replays every stage whose op the port has registered (recipes/index.js getOp), and names the
//                       ops it has not; --selfcheck reads every dump, sends each `after` through the GPU and back
//                       (bit for bit) and writes and reads a dispatch log, with no op at all
//
// What a replay checks, per stage (plan 5.3):
//   fields     every field after the op against Blender's `after` dump: max |d| <= max(1e-4 x the field's range,
//              1.25 x the largest of the stage's floor samples (<run>/base/stage_floors.json, made by
//              blender_stage_dump.py --floor for every op of the main level; another level's floor is 0, the kernel
//              grade), 16 float32 steps)
//   dispatches the call's dispatch log against the same call's lines of Blender's log (dispatch_parity.mjs): a loop
//              that stops on a convergence test may differ by whole test intervals when the solver names it
//              (opts.intervals) or the floor saw it move anywhere (dispatch_parity.knownIntervals)
//   warm-up    an op that keeps state between its calls outside its arguments (WARM below: karst) has the run's
//              earlier calls of it run first, unlogged, as the Blender stage floor does
//   snapshots  on the main level's own cells: each kernel's images and inputs after its 1st, 10th and 100th dispatch
//              in the call against Blender's snapshots, at max(1e-4 x range, 1.25 x the largest floor sample there)
//
// PortLog is the port's half of the dispatch log (plan 5.2): it turns core/gpu.js's onDispatch and onReadback records
// into dispatch_log.jsonl.gz, readbacks.jsonl.gz and snap/ in Blender's formats, with `blender_kernel` per dispatch.
// The level runner (run.js) tells it where it is through G.context: { op, call (the op-call counter, null outside
// ops, where op is '<runner>' or '<masks>'), level, pass, end ('lakes' | 'route' in the runner's end stages) }.
// JavaScript per cell here is test code (the edition's rule allows it in tests only).

import { Fields } from '../../core/fields.js';
import * as IO from '../../core/io.js';
import { Level } from '../../core/levels.js';
import * as C from './_common.mjs';
import * as DP from './dispatch_parity.mjs';

export const SNAP_AT = [1, 10, 100, 1000, 10000];
export const CALL_SNAP_AT = [1, 10, 100];
// Ops whose result on a finer level depends on state an earlier call of the same op left in its module, outside its
// arguments (tests/parity/blender_stage_dump.py WARM, which measured it): a replay of such a stage first runs the
// run's earlier calls of that op from their own dumps, unlogged and uncompared, as the Blender stage floor does.
export const WARM = Object.freeze({ karst: "op_karst's plan domain is set by the coarsest level's call (karst._DOMAINS)" });

/** The run's earlier calls a replay of `st` runs first (WARM): every earlier call of the same op, in call order. */
export const warmStages = (run, st) => (WARM[st.op] ? run.stages.filter((s) => s.op === st.op && s.call < st.call) : []);
const OUTSIDE = new Set(['<prepare>', '<runner>', '<masks>', '<after>']);
const FMT = (f) => f.format.toUpperCase();

async function writeGzLines(path, lines) {
    const text = lines.map((l) => JSON.stringify(l)).join('\n') + (lines.length ? '\n' : '');
    const gz = new Response(new Blob([text]).stream().pipeThrough(new CompressionStream('gzip')));
    await Deno.writeFile(path, new Uint8Array(await gz.arrayBuffer()));
}


// ------------------------------------------------------------------------------------------- the port's log ---

/** The port's dispatch log, readbacks and step snapshots (see the top). new PortLog(G, dir, { mainLevel, snapshots
 * (true), inputs (true: a snapshot also holds each sampler's field as in__<name>) }); start(); ...; await stop(). */
export class PortLog {
    constructor(G, dir, opts = {}) {
        this.G = G;
        this.dir = dir;
        this.opts = { snapshots: true, inputs: true, mainLevel: null, ...opts };
        this.lines = [];
        this.reads = [];
        this.kernels = {};
        this.callCounts = new Map();
        this.pending = [];
        this.index = {};
        this.base = null;
        this.snapBytes = 0;
    }

    start() {
        Deno.mkdirSync(this.dir, { recursive: true });
        this.G.onDispatch((r) => this._dispatch(r));
        this.G.onReadback((r) => this._readback(r));
        return this;
    }

    _dispatch(r) {
        const ctx = this.G.context;
        if (this.base === null) this.base = r.index - 1;
        const d = r.index - 1 - this.base;
        const inOp = ctx.call != null && !OUTSIDE.has(ctx.op);
        const names = Object.keys(r.samplers ?? {}).sort();
        const uniforms = Object.entries(r.uniforms ?? {}).sort(([a], [b]) => (a < b ? -1 : 1))
            .map(([n, v]) => [n, typeof v === 'number' ? v : Array.from(v)]);
        const images = Object.entries(r.images ?? {}).sort(([a], [b]) => (a < b ? -1 : 1)).map(([n, f]) => [n, f.h, f.w, FMT(f)]);
        const meta = { g: r.groups, call: inOp ? ctx.call : null, level: ctx.level ?? null, pass: ctx.pass ?? null,
            s: names.map((n) => [r.samplers[n].h, r.samplers[n].w, FMT(r.samplers[n])]), blender_kernel: !!r.blender };
        if (ctx.end) meta.end = ctx.end;
        this.lines.push([ctx.op ?? null, r.kernel, uniforms, images, names, meta]);
        if (!(r.kernel in this.kernels)) {
            this.kernels[r.kernel] = { samplers: names, images: Object.fromEntries(images.map((x) => [x[0], x[3]])),
                uniforms: uniforms.map((u) => u[0]), blender: !!r.blender };
        }
        if (!this.opts.snapshots || !r.blender || !images.length) return;
        const keys = [];
        if (SNAP_AT.includes(r.count)) keys.push(`${r.kernel}#${r.count}`);
        if (inOp) {
            const ck = `${ctx.call} ${r.kernel}`;
            const cc = (this.callCounts.get(ck) ?? 0) + 1;
            this.callCounts.set(ck, cc);
            if (CALL_SNAP_AT.includes(cc) && this.opts.mainLevel != null && ctx.level === this.opts.mainLevel && !ctx.prepass) {
                keys.push(`L${ctx.level}_c${ctx.call}_${ctx.op}_${r.kernel}#${cc}`);
            }
        }
        if (!keys.length) return;
        const fields = Object.entries(r.images).map(([n, f]) => [n, f]);
        if (this.opts.inputs) for (const n of names) fields.push([`in__${n}`, r.samplers[n]]);
        const copies = r.runner.snapshot(fields.map(([, f]) => f));
        this.pending.push({ keys, d, kernel: r.kernel, op: ctx.op, call: meta.call, level: meta.level, runner: r.runner,
            names: fields.map(([n]) => n), copies });
    }

    _readback(r) {
        const ctx = this.G.context;
        const [h, w, c] = r.shape;
        let lo = Infinity, hi = -Infinity, sum = 0;
        for (let i = 0; i < r.data.length; i++) {
            const v = r.data[i];
            if (v < lo) lo = v;
            if (v > hi) hi = v;
            sum += v;
        }
        const fin = (x) => (Number.isFinite(x) ? x : null);
        this.reads.push([r.afterDispatch - 1 - (this.base ?? r.afterDispatch), ctx.op ?? null, r.name ?? '?', h, w, c,
            r.data.length ? [fin(lo), fin(hi), fin(sum)] : [null, null, 0],
            { call: ctx.call != null && !OUTSIDE.has(ctx.op) ? ctx.call : null, level: ctx.level ?? null, pass: ctx.pass ?? null,
                ...(ctx.end ? { end: ctx.end } : {}), first: r.first, count: r.count }]);
    }

    /** Read the snapshots taken so far and write them (call between ops: the copies hold GPU memory until then). */
    async drain() {
        const todo = this.pending;
        this.pending = [];
        if (!todo.length) return;
        Deno.mkdirSync(`${this.dir}/snap`, { recursive: true });
        this.G.onReadback(null);                              // the snapshots' own reads are not the run's readbacks
        try {
            for (const s of todo) {
                const data = await s.runner.readAll(s.copies);
                const arrays = {};
                s.copies.forEach((f, i) => { arrays[s.names[i]] = IO.npArray(data[i], [f.h, f.w, f.channels]); });
                const file = `d${String(s.d).padStart(7, '0')}.npz`;
                this.snapBytes += await IO.writeNpz(`${this.dir}/snap/${file}`, arrays, { compress: true });
                for (const key of s.keys) {
                    this.index[key] = { d: s.d, file, kernel: s.kernel, op: s.op, call: s.call, level: s.level,
                        images: Object.fromEntries(s.copies.map((f, i) => [s.names[i], [f.h, f.w, f.channels]])) };
                }
                for (const f of s.copies) f.destroy();
            }
        } finally {
            this.G.onReadback((r) => this._readback(r));
        }
    }

    /** Stop logging and write the files. Returns { dispatches, readbacks, snapshots }. */
    async stop() {
        await this.drain();
        this.G.onDispatch(null);
        this.G.onReadback(null);
        await writeGzLines(`${this.dir}/dispatch_log.jsonl.gz`, this.lines);
        await writeGzLines(`${this.dir}/readbacks.jsonl.gz`, this.reads);
        Deno.writeTextFileSync(`${this.dir}/kernels.json`, JSON.stringify(this.kernels, null, 1));
        if (this.opts.snapshots) {
            Deno.mkdirSync(`${this.dir}/snap`, { recursive: true });
            Deno.writeTextFileSync(`${this.dir}/snap/index.json`, JSON.stringify({ snap_at: SNAP_AT, call_snap_at: CALL_SNAP_AT,
                bytes: this.snapBytes, snapshots: this.index }, null, 1));
        }
        return { dispatches: this.lines.length, readbacks: this.reads.length, snapshots: Object.keys(this.index).length };
    }
}


// ------------------------------------------------------------------------------------------ Blender's dumps ---

const bare = (name) => (name.endsWith('.npy') ? name.slice(0, -4) : name);

/** The arrays of an npz as { name: { dtype, shape, data } } (np.savez or np.savez_compressed). */
export async function npz(path) {
    const raw = await IO.readNpz(path);
    return Object.fromEntries(Object.entries(raw).map(([k, v]) => [bare(k), v]));
}

/** A floor run's base folder: { dir, info (run.json), header (the run: plan, recipe, values, seed ...), stages
 * (one record per op call, with .before / .after / .where file names), endStages, levels (Level objects), floors
 * (stage_floors.json's stages by call, or {}), snapIndex, snapFloor }. */
export async function loadRun(dir) {
    const header = C.readJson(`${dir}/stages/stages.json`);
    if (!header) return null;
    const floors = {};
    for (const s of C.readJson(`${dir}/stage_floors.json`, { stages: [] }).stages) floors[s.call] = s;
    // the largest difference the perturbed runs show at each snapshot, per image and channel (their sample.json)
    const snapFloor = {};
    for (let p = 1; p <= 9; p++) {
        const s = C.readJson(`${dir}/../p${p}/sample.json`);
        for (const [key, rec] of Object.entries(s?.snapshots ?? {})) {
            for (const [im, chans] of Object.entries(rec)) {
                if (!Array.isArray(chans)) continue;
                const cur = (snapFloor[key] ??= {})[im] ??= chans.map(() => 0);
                chans.forEach((v, c) => { if (v && v[0] != null) cur[c] = Math.max(cur[c], v[0]); });
            }
        }
    }
    return { dir, info: C.readJson(`${dir}/run.json`, {}), header, stages: header.stages, endStages: header.end_stages,
        levels: header.plan.map((d) => Level.fromDict(d)), floors, snapFloor,
        snapIndex: C.readJson(`${dir}/snap/index.json`, { snapshots: {} }).snapshots };
}

/** A stage's level (its window as dumped: a pre-pass has its own cell count) as a Level. */
export const stageLevel = (st) => Level.fromDict(st.window);

/** The stage's `before` dump on the GPU: { fields (a Fields of every float32 field of the level's shape), pins
 * ({ name: field }), shared (arrays of ctx.shared by path), other (arrays that are not fields: kept as read) }. */
export async function stageBefore(R, run, st) {
    const arrays = await npz(`${run.dir}/stages/${st.before}`);
    const level = stageLevel(st);
    const fields = new Fields(level, null, R);
    const pins = {}, shared = {}, other = {};
    for (const [name, a] of Object.entries(arrays)) {
        const is2d = a.shape.length === 2 && a.shape[0] === level.n && a.shape[1] === level.n;
        const f32 = a.dtype === '<f4' ? a.data : (a.dtype === '<f8' && is2d ? Float32Array.from(a.data) : null);
        if (name.startsWith('pin__')) pins[name.slice(5)] = is2d && f32 ? R.field(level.n, level.n, 1, f32) : a;
        else if (name.startsWith('shared__')) shared[name.slice(8)] = a;
        else if (is2d && a.dtype === '<f4') fields.set(name, a.data);
        else other[name] = a;
    }
    return { level, fields, pins, shared, other, arrays };
}

/** The context a port op receives for a stage: the dump's JSON context with the plan's levels, the pins as fields
 * and `shared` as dumped (JSON, with its arrays under their paths in sharedArrays). A plain object: run.js's own
 * StageContext (P5) takes it from here. */
export function stageContext(run, st, before) {
    const c = st.context;
    if (!c) return null;
    return { plan: run.levels, index: c.index, level: before.level, prepass: c.prepass, fresh: c.fresh, role: c.role,
        pins: Object.keys(before.pins).length ? before.pins : null, shared: structuredClone(c.shared ?? {}),
        sharedArrays: before.shared, seed: st.seed, sea_level: c.sea_level, base_elevation_m: c.base_elevation_m,
        flatten: c.flatten, values: c.values, grow_levels: c.grow_levels, evolved: false, log: () => {} };
}

/** The fields after a replay against the stage's `after` dump: { ok, fields: { name: { ok, err, tol, range, over
 * (err / range), floor } }, missing, extra }. tolerance: max(1e-4 x range, 1.25 x the stage's floor for that field,
 * 16 float32 steps of the field's largest value). */
export async function compareAfter(run, st, fields) {
    const want = await npz(`${run.dir}/stages/${st.after}`);
    const floor = run.floors[st.call]?.floor ?? {};
    const out = { ok: true, fields: {}, missing: [], extra: [] };
    const R = fields.R;
    for (const [name, a] of Object.entries(want)) {
        if (name.startsWith('shared__')) continue;
        if (!(a.shape.length === 2 && a.dtype === '<f4')) continue;
        if (!(name in fields)) { out.missing.push(name); out.ok = false; continue; }
        const got = await R.read(fields[name]);
        const fl = floor[name]?.max_over_range ?? 0;
        const g = C.gradeArray(got, a.data, { k: Math.max(1e-4, 1.25 * fl), m: 16 });
        out.fields[name] = { ok: g.ok, err: g.err, tol: g.tol, range: g.range, over: g.range ? g.err / g.range : 0, floor: fl,
            bit_identical: g.err === 0 && g.nonFinite === 0 };
        if (!g.ok) out.ok = false;
    }
    for (const name of Object.keys(fields)) if (!(name in want)) out.extra.push(name);
    return out;
}

/** The port's step snapshots (a PortLog's snap/) against Blender's (run.dir/snap), at the keys both have:
 * { ok, compared, worst, failures: [{ key, image, channel, over, tol }] }. */
export async function compareSnapshots(run, portDir) {
    const mine = C.readJson(`${portDir}/snap/index.json`, { snapshots: {} }).snapshots;
    const out = { ok: true, compared: 0, keys: 0, worst: 0, failures: [], only_port: [], shapes: [] };
    for (const [key, ent] of Object.entries(mine)) {
        const base = run.snapIndex[key];
        if (!base) { out.only_port.push(key); continue; }
        out.keys++;
        const a = await npz(`${run.dir}/snap/${base.file}`), b = await npz(`${portDir}/snap/${ent.file}`);
        for (const [im, want] of Object.entries(a)) {
            const got = b[im];
            if (!got) continue;                               // an input the port does not bind under that name
            if (want.data.length !== got.data.length) { out.shapes.push(`${key} ${im}: ${want.shape} in Blender, ${got.shape} here`); out.ok = false; continue; }
            const ch = want.shape[2] ?? 1, n = want.data.length / ch;
            for (let c = 0; c < ch; c++) {
                let lo = Infinity, hi = -Infinity, amax = 0, err = 0;
                for (let i = 0; i < n; i++) {
                    const w = want.data[i * ch + c], g = got.data[i * ch + c];
                    if (!Number.isFinite(w) || !Number.isFinite(g)) { if (!(w === g || (w !== w && g !== g))) err = Infinity; continue; }
                    if (w < lo) lo = w;
                    if (w > hi) hi = w;
                    amax = Math.max(amax, Math.abs(w));
                    err = Math.max(err, Math.abs(g - w));
                }
                const range = (hi - lo) || amax || 1.0;
                const fl = run.snapFloor[key]?.[im]?.[c] ?? 0;
                const tol = Math.max(1e-4, 1.25 * fl) * range + 16 * C.ulp32(amax);
                out.compared++;
                out.worst = Math.max(out.worst, err / range);
                if (!(err <= tol)) {
                    out.ok = false;
                    if (out.failures.length < 40) out.failures.push({ key, image: im, channel: c, over: err / range, tol: tol / range, floor: fl });
                }
            }
        }
    }
    return out;
}

/** Blender's dispatch-log lines and readbacks of one op call, as a run for dispatch_parity.compareLogs. */
export async function blenderCall(run, call) {
    run._log ??= await DP.loadRun(run.dir);
    return { dir: `${run.dir} (call ${call})`, dispatches: run._log.dispatches.filter((d) => d[5]?.call === call),
        readbacks: run._log.readbacks.filter((r) => r[7]?.call === call), kernels: run._log.kernels };
}

/** Replay one stage with the port's op (see the top). opts: logDir (where the port's log of the call goes; default
 * a folder under tests/out/parity/replay/), invoke(op, { fields, level, params, seed, ctx }) to call an op another
 * way, floor (a dispatch_floor.json's content), intervals (the solver's named convergence loops), warm (the stages
 * run first; default warmStages). Returns { stage, seconds, fields, dispatch, snapshots, ok }. */
export async function replayStage(R, G, run, st, op, opts = {}) {
    for (const w of opts.warm ?? warmStages(run, st)) {       // the module state the run had (WARM), unlogged
        const wb = await stageBefore(R, run, w);
        if (opts.invoke) await opts.invoke(op, { fields: wb.fields, level: wb.level, params: structuredClone(w.params), seed: w.seed, ctx: stageContext(run, w, wb) });
        else await op(wb.fields, wb.level, structuredClone(w.params), w.seed, stageContext(run, w, wb));
        for (const f of Object.values(wb.pins)) f.destroy?.();
        for (const name of Object.keys(wb.fields)) wb.fields[name]?.destroy?.();
    }
    const before = await stageBefore(R, run, st);
    const ctx = stageContext(run, st, before);
    const main = run.header.main_index;
    const logDir = opts.logDir ?? `${C.W.out('parity')}/replay/${run.header.recipe?.name ?? 'run'}_s${run.header.seed}/c${st.call}_${st.op}`;
    const log = new PortLog(G, logDir, { mainLevel: main }).start();
    Object.assign(G.context, { op: st.op, call: st.call, level: st.level, pass: st.pass_index, prepass: ctx?.prepass ?? null, end: null });
    const t0 = performance.now();
    let error = null;
    try {
        if (opts.invoke) await opts.invoke(op, { fields: before.fields, level: before.level, params: structuredClone(st.params), seed: st.seed, ctx });
        else await op(before.fields, before.level, structuredClone(st.params), st.seed, ctx);
        await R.idle?.();
    } catch (e) {
        error = `${e?.name ?? 'Error'}: ${e?.message ?? e}`;
    }
    const seconds = (performance.now() - t0) / 1000;
    Object.assign(G.context, { op: null, call: null, level: null, pass: null, prepass: null, end: null });
    const summary = await log.stop();
    const out = { stage: { call: st.call, level: st.level, pass: st.pass_index, n: st.n, op: st.op, evolved: st.evolved ?? null },
        seconds: +seconds.toFixed(3), blender_seconds: st.seconds, log: summary, error };
    if (!error) {
        out.fields = await compareAfter(run, st, before.fields);
        const floor = opts.floor ?? C.readJson(`${run.dir}/dispatch_floor.json`);
        const mineRun = await DP.loadRun(logDir);
        run._known ??= DP.knownIntervals(C.W.norm(`${run.dir}/../..`));
        const d = DP.compareLogs(await blenderCall(run, st.call), mineRun, { floor, known: run._known, intervals: opts.intervals });
        delete d._uniforms;
        delete d._counts;
        out.dispatch = d;
        out.snapshots = await compareSnapshots(run, logDir);
    }
    out.ok = !error && out.fields.ok && out.dispatch.ok && out.snapshots.ok;
    for (const f of Object.values(before.pins)) f.destroy?.();
    for (const name of Object.keys(before.fields)) before.fields[name]?.destroy?.();
    return out;
}


// --------------------------------------------------------------------------------------------- the command ---

async function selfcheck(dir) {
    const G = await import('../../core/gpu.js');
    const T = new C.Checks('parity/replay selfcheck');
    const run = await loadRun(dir);
    if (!run) { console.log(`no stages/stages.json under ${dir}`); return 2; }
    const R = await G.init();
    let arrays = 0, fieldsN = 0, exact = 0, bad = [];
    for (const st of run.stages) {
        const b = await stageBefore(R, run, st);
        arrays += Object.keys(b.arrays).length;
        const after = await npz(`${run.dir}/stages/${st.after}`);
        // an op that hands back Blender's own result: the comparison must find it identical
        for (const [name, a] of Object.entries(after)) {
            if (a.shape.length === 2 && a.dtype === '<f4' && a.shape[0] === b.level.n) b.fields.set(name, a.data);
        }
        const cmp = await compareAfter(run, st, b.fields);
        for (const [name, g] of Object.entries(cmp.fields)) {
            fieldsN++;
            if (g.bit_identical) exact++;
            else bad.push(`${st.before.replace('_before.npz', '')} ${name}`);
        }
        if (cmp.missing.length) bad.push(`${st.op}: missing ${cmp.missing}`);
        for (const name of Object.keys(b.fields)) b.fields[name]?.destroy?.();
        for (const f of Object.values(b.pins)) f.destroy?.();
    }
    T.ok(`every stage dump of ${run.stages.length} op calls reads, and Blender's own result sent through the GPU compares bit for bit`,
        !bad.length && exact === fieldsN, bad.slice(0, 5).join('; ') || `${arrays} arrays read, ${fieldsN} fields compared`);
    // the log writer: two dispatches and a read through PortLog, read back by dispatch_parity
    const tmp = `${C.W.out('parity')}/replay/_selfcheck`;
    const log = new PortLog(G, tmp, { mainLevel: 0 }).start();
    Object.assign(G.context, { op: 'selfcheck', call: 0, level: 0, pass: 0 });
    // marked as a Blender kernel, so its snapshots are taken
    const k = R.kernel('parity_selfcheck', { blender: true, source: `//! sampler a\n//! image o r32f\n//! uniform float uK\nfn kmain(p: vec2<i32>) {\n  if (!inside(p, a_size())) { return; }\n  o_store(p, vec4<f32>(a_at(p).x * u.uK, 0.0, 0.0, 0.0));\n}` });
    const a = R.field(4, 6, 1, Float32Array.from({ length: 24 }, (_, i) => i)), o = R.field(4, 6, 1), o2 = R.field(4, 6, 1);
    R.run(k, { a }, { o }, { uK: 2.0 });
    R.run(k, { a: o }, { o: o2 }, { uK: 0.5 });
    const back = await R.read(o2);
    Object.assign(G.context, { op: null, call: null, level: null, pass: null });
    const s = await log.stop();
    const mine = await DP.loadRun(tmp);
    const self = DP.compareLogs(mine, mine);
    const snap = await npz(`${tmp}/snap/d0000000.npz`);
    T.ok('PortLog writes the plan\'s files: 2 dispatches, 1 readback, a snapshot of the first dispatch with its input', s.dispatches === 2 &&
        s.readbacks === 1 && mine.dispatches.length === 2 && mine.dispatches[0][1] === 'parity_selfcheck' &&
        mine.dispatches[0][5].blender_kernel === true && mine.dispatches[0][5].call === 0 && self.ok &&
        snap.o?.data[5] === 10 && snap.in__a?.data[5] === 5 && back[5] === 5,
        `${JSON.stringify(mine.dispatches[0]).slice(0, 160)}`);
    for (const f of [a, o, o2]) f.destroy();
    const code = C.finish(T, 'replay_selfcheck', { run: dir });
    G.shutdown();
    return code;
}

if (import.meta.main) {
    const args = [...Deno.args];
    const flag = (n) => { const i = args.indexOf(n); if (i < 0) return false; args.splice(i, 1); return true; };
    const opt = (n) => { const i = args.indexOf(n); return i >= 0 ? args.splice(i, 2)[1] : null; };
    const self = flag('--selfcheck'), ops = opt('--ops')?.split(',') ?? null, levels = opt('--levels') ?? 'main', outFile = opt('--out');
    if (!args.length) {
        console.log('usage: replay.mjs <floor run>/base [--ops a,b] [--levels main|all|0,2] [--out <json>] [--selfcheck]');
        Deno.exit(2);
    }
    const dir = C.W.absPath(args[0]);
    if (self) Deno.exit(await selfcheck(dir));
    const run = await loadRun(dir);
    if (!run) { console.log(`no stages/stages.json under ${dir}`); Deno.exit(2); }
    const G = await import('../../core/gpu.js');
    const registry = await import('../../recipes/index.js');
    const R = await G.init();
    const want = levels === 'all' ? null : levels === 'main' ? [run.header.main_index] : levels.split(',').map(Number);
    const results = [], notPorted = new Set();
    for (const st of run.stages) {
        if (ops && !ops.includes(st.op)) continue;
        if (want && !want.includes(st.level)) continue;
        if (!(await registry.hasOp(st.op))) { notPorted.add(st.op); continue; }
        const r = await replayStage(R, G, run, st, await registry.getOp(st.op));
        results.push(r);
        const worst = Object.entries(r.fields?.fields ?? {}).sort((a, b) => b[1].over - a[1].over)[0];
        console.log(`${r.ok ? 'ok  ' : 'FAIL'} L${st.level} p${st.pass_index} ${st.op} (call ${st.call}): ` + (r.error ? r.error :
            `fields ${r.fields.ok ? 'within tolerance' : 'OVER'} (worst ${worst ? `${worst[0]} ${C.sci(worst[1].over)} of range` : 'none'}), ` +
            `dispatch log ${r.dispatch.ok ? 'equal' : 'DIFFERS'}, ${r.snapshots.compared} snapshot channels ${r.snapshots.ok ? 'within tolerance' : 'OVER'}; ${r.seconds} s (Blender ${st.seconds} s)`));
    }
    const out = { run: dir, date: new Date().toISOString(), replayed: results.length, passed: results.filter((r) => r.ok).length,
        ops_not_ported: [...notPorted].sort(), results };
    Deno.writeTextFileSync(outFile ?? `${C.W.out('parity')}/replay_${run.header.recipe?.name ?? 'run'}_s${run.header.seed}.json`, JSON.stringify(out, null, 1));
    console.log(`${out.passed} of ${out.replayed} stages pass` + (notPorted.size ? `; ops the port has not registered yet: ${out.ops_not_ported.join(', ')}` : ''));
    G.shutdown();
    Deno.exit(out.replayed && out.passed === out.replayed ? 0 : 1);
}
