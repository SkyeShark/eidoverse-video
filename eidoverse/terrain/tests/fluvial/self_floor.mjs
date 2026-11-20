// The fluvial op's own floor in the port, beside Blender's (a diagnostic of the stage replays, PORT_PLAN.md 5.3, 5.4):
// for the chosen stages of the Blender floor runs, the port's op replayed from Blender's dumped input
//   base      as it is (replay_test.mjs's replay: deterministic, so the same result)
//   entry k   every float32 field of the level moved by one ulp at the op's entry, up on a quarter of the cells and
//             down on another quarter (Blender's perturbation (a) of plan 5.4, tests/parity/_hooks.py nudge, drawn
//             from default_rng([k, call]) as the floor draws its patterns), k = 1..K
//   step k    the run's state h and A moved by one ulp the same way after EVERY step: a rounding difference in every
//             step, which is what a port has (its kernels differ from Blender's GLSL by the built-ins' rounding in
//             every dispatch, plan 2.3; route_incise's fixtures differ from the twins by up to 6e-5 of A's range in
//             one dispatch), where the floor perturbs twice per op call
// and every field after the op against the base (the port's own floor under each protocol), and the base against
// Blender's dumped output. The two questions it answers for a stage the replay grade fails:
//   1. Does the port's op respond to Blender's perturbation as Blender's does?  entry floor beside Blender's floor
//   2. Is the port's distance from Blender what a per-step rounding difference makes?  base vs Blender beside the
//      step floor
// JavaScript per cell here is test code. The 'step' variants add a test kernel (nudge, below) after each step; it is
// not part of any run.
//
//     deno run --no-config --no-lock --unstable-webgpu --allow-all eidoverse/terrain/tests/fluvial/self_floor.mjs
//         --stages alpine_valley:1:4,rolling_hills:2:7 [--k 5]          (on a shared machine, behind $EIDO_GPU_WRAP)
//
// Writes tests/out/fluvial/self_floor.json (merged by stage, so runs over different stages add up).

import * as G from '../../core/gpu.js';
import { defaultRng } from '../../core/np_random.js';
import { FluvialRun } from '../../solvers/fluvial.js';
import * as RP from '../parity/replay.mjs';
import * as C from '../parity/_common.mjs';

const W = C.W;
const args = [...Deno.args];
const opt = (name, dflt) => { const i = args.indexOf(name); return i >= 0 ? args[i + 1] : dflt; };
const STAGES = opt('--stages', 'alpine_valley:1:4').split(',').map((s) => {
    const [recipe, seed, call] = s.split(':');
    return { recipe, seed: Number(seed), call: Number(call) };
});
const K = Number(opt('--k', '5'));
const FIELDS = ['h', 'bed', 'A', 'qs', 'wear', 'deposit', 'talus', 'U'];

// one float32 step toward +inf (up) or -inf, by the bits; 0 stays 0 (as the floor's nextafter would make a subnormal)
const NUDGE = `
//! sampler st
//! image   outS rgba32f
//! uniform int uStep
//! uniform int uPat

fn step_ulp(v: f32, up: bool) -> f32 {
  if (v == 0.0) { return v; }
  let b = bitcast<u32>(v);
  return bitcast<f32>(select(b - 1u, b + 1u, (v > 0.0) == up));
}

fn kmain(p: vec2<i32>) {
  if (!inside(p, st_size())) { return; }
  var s = st_at(p);
  let r0 = cell_hash(p, u.uStep, u.uPat) >> 30u;
  let r1 = cell_hash(p, u.uStep, u.uPat + 7919) >> 30u;
  if (r0 == 0u) { s.x = step_ulp(s.x, true); } else if (r0 == 3u) { s.x = step_ulp(s.x, false); }
  if (r1 == 0u) { s.y = step_ulp(s.y, true); } else if (r1 == 3u) { s.y = step_ulp(s.y, false); }
  outS_store(p, s);
}
`;

const STEP = { on: false, pattern: 0, kernel: null };
const plainStep = FluvialRun.prototype.step;
FluvialRun.prototype.step = function (...a) {
    plainStep.apply(this, a);
    if (!STEP.on) return;
    STEP.kernel ??= this.R.kernel('test_nudge_state', NUDGE);
    this.R.run(STEP.kernel, { st: this.S.src }, { outS: this.S.dst }, { uStep: this.steps, uPat: STEP.pattern });
    this.S.swap();
};

const F32 = new Float32Array(1), U32 = new Uint32Array(F32.buffer);
function nextafter32(v, up) {
    if (v === 0) return v;
    F32[0] = v;
    U32[0] += ((v > 0) === up) ? 1 : -1;
    return F32[0];
}

// numpy's nudge: r = rng.random(shape); up where r < 0.25, down where r >= 0.75
function nudgeArray(a, rng) {
    const r = rng.random(a.length);
    const out = new Float32Array(a.length);
    for (let i = 0; i < a.length; i++) out[i] = r[i] < 0.25 ? nextafter32(a[i], true) : r[i] >= 0.75 ? nextafter32(a[i], false) : a[i];
    return out;
}

// [max, RMS, p99] of |got - ref| over the range of `rangeOf`, as the floor records them
function dist(got, ref, rangeOf) {
    let lo = Infinity, hi = -Infinity, amax = 0;
    for (const w of rangeOf) if (Number.isFinite(w)) { lo = Math.min(lo, w); hi = Math.max(hi, w); amax = Math.max(amax, Math.abs(w)); }
    const range = (hi - lo) || amax || 1.0;
    const e = new Float64Array(ref.length);
    let sq = 0, mx = 0;
    for (let i = 0; i < ref.length; i++) {
        const d = Math.abs(got[i] - ref[i]);
        e[i] = Number.isFinite(d) ? d : 0;
        sq += e[i] * e[i];
        mx = Math.max(mx, e[i]);
    }
    e.sort();
    const pos = 0.99 * (e.length - 1), k = Math.floor(pos);
    const p99 = e[k] + (pos - k) * (e[Math.min(k + 1, e.length - 1)] - e[k]);
    return [mx / range, Math.sqrt(sq / e.length) / range, p99 / range];
}

const maxOf = (rows) => rows.reduce((m, r) => m.map((v, i) => Math.max(v, r[i] ?? 0)), [0, 0, 0]);

const R = await G.init();
const registry = await import('../../recipes/index.js');
const outPath = `${W.out('fluvial')}/self_floor.json`;
const all = C.readJson(outPath, { stages: {} });
const T = new C.Checks('fluvial: the port\'s own floor beside Blender\'s, on the stages the replay grade fails');

for (const S of STAGES) {
    const dir = W.floorRun(S.recipe, S.seed);
    if (!dir) { T.ok(`${S.recipe} s${S.seed} c${S.call}: a floor run`, false, 'no floor run under the parity key'); continue; }
    const run = await RP.loadRun(dir);
    const st = run.stages.find((s) => s.call === S.call);
    const op = await registry.getOp(st.op);
    const want = await RP.npz(`${run.dir}/stages/${st.after}`);
    const blenderFloor = run.floors[st.call]?.floor ?? {};
    const rec = { recipe: S.recipe, seed: S.seed, call: S.call, op: st.op, level: st.level,
        blender_U_factor: st.shared_after?.U_factor ?? null, variants: [] };
    let base = null;
    const variants = [['base', 0], ...Array.from({ length: K }, (_, k) => ['entry', k + 1]), ...Array.from({ length: K }, (_, k) => ['step', k + 1])];
    for (const [kind, k] of variants) {
        const before = await RP.stageBefore(R, run, st);
        const ctx = RP.stageContext(run, st, before);
        if (kind === 'entry') {
            const rng = defaultRng([k, st.call]);
            for (const name of Object.keys(before.fields).sort()) {
                const f = before.fields[name];
                if (!f || f.kind !== 'f32' || f.channels !== 1) continue;
                R.write(f, nudgeArray(await R.read(f), rng));
            }
        }
        STEP.on = kind === 'step';
        STEP.pattern = k;
        const t0 = performance.now();
        await op(before.fields, before.level, structuredClone(st.params), st.seed, ctx);
        await R.idle();
        STEP.on = false;
        const got = {};
        for (const name of FIELDS) if (name in before.fields && want[name]) got[name] = await R.read(before.fields[name]);
        const v = { variant: `${kind}${k || ''}`, seconds: +((performance.now() - t0) / 1000).toFixed(2),
            U_factor: ctx.shared?.U_factor ?? null, controller: ctx.shared?.fluvial_log?.at(-1)?.controller ?? null,
            vs_blender: {}, vs_base: {} };
        for (const [name, g] of Object.entries(got)) {
            v.vs_blender[name] = dist(g, want[name].data, want[name].data);
            if (base) v.vs_base[name] = dist(g, base[name], want[name].data);
        }
        if (!base) base = got;
        rec.variants.push(v);
        for (const f of Object.values(before.pins)) f.destroy?.();
        for (const name of Object.keys(before.fields)) before.fields[name]?.destroy?.();
        console.log(`${S.recipe} s${S.seed} c${S.call} ${v.variant}: ${v.seconds} s, U factor ${v.U_factor}`);
    }
    // per field: the base against Blender, Blender's floor (largest of its samples), the port's entry and step floors
    rec.summary = {};
    const entry = rec.variants.filter((v) => v.variant.startsWith('entry')), step = rec.variants.filter((v) => v.variant.startsWith('step'));
    for (const name of Object.keys(base)) {
        const bf = blenderFloor[name]?.samples ?? [];
        rec.summary[name] = { port_vs_blender: rec.variants[0].vs_blender[name], blender_floor: maxOf(bf),
            port_entry_floor: maxOf(entry.map((v) => v.vs_base[name])), port_step_floor: maxOf(step.map((v) => v.vs_base[name])) };
    }
    const uf = (vs) => vs.map((v) => v.U_factor).filter((x) => x !== null);
    rec.U_factors = { blender: rec.blender_U_factor, port_base: rec.variants[0].U_factor, entry: uf(entry), step: uf(step) };
    all.stages[`${S.recipe}_s${S.seed}_c${S.call}`] = rec;
    console.log(`\n${S.recipe} s${S.seed} L${st.level} ${st.op} (call ${S.call}): [max, RMS, p99] / range`);
    const f3 = (a) => a.map((x) => C.sci(x)).join(' ');
    for (const [name, s] of Object.entries(rec.summary)) {
        console.log(`  ${name.padEnd(8)} port-Blender ${f3(s.port_vs_blender)} | Blender floor ${f3(s.blender_floor)} | port entry floor ` +
            `${f3(s.port_entry_floor)} | port step floor ${f3(s.port_step_floor)}`);
    }
    if (rec.U_factors.port_base !== null) {
        console.log(`  U factor: Blender ${rec.U_factors.blender}, port ${rec.U_factors.port_base}; entry ${rec.U_factors.entry.map((x) => x.toFixed(4))}; ` +
            `step ${rec.U_factors.step.map((x) => x.toFixed(4))}`);
    }
    T.ok(`${S.recipe} s${S.seed} c${S.call}: measured`, true);
}
all.date = new Date().toISOString();
Deno.writeTextFileSync(outPath, JSON.stringify(all, null, 1));
G.shutdown();
Deno.exit(C.finish(T, '../fluvial/self_floor_checks'));
