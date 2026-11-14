// The production runner (core/gpu.js) against its acceptance (PORT_PLAN.md 8.2, P1): the header grammar, exact round
// trips, the refusals, batching and per-dispatch uniforms, packs, textures, the plan's 46 fixture cases of the
// Blender numpy twins (with the hashes and the world noise) run through this runner instead of the prototype on a
// plain device (scene_device_test.mjs runs them on render_common's), a u32(0) kernel, and the dispatch hook.
//
//     <Blender's python> -I eidoverse/terrain/tests/core_runner/twin_fixtures.py
//     deno run --no-config --no-lock --unstable-webgpu --allow-all eidoverse/terrain/tests/core_runner/runner_test.mjs [fixtures]
//
// The kernels of the 46 cases are the design probes' transcriptions (tests/design_probes/wgsl/), read as they are:
// their production copies belong to the packages that own them (plan 3.3). On a shared machine put $EIDO_GPU_WRAP
// in front of the deno command.

import * as G from '../../core/gpu.js';
import { Checks, PROBES, bitsEqual, lcg } from './_common.mjs';
import { twinChecks, twinFixtures, u32ZeroCheck } from './_twins.mjs';

const T = new Checks('core_runner/runner');

// ---- 1. the header grammar (no GPU)
{
    const s = G.parseSpec(`//! sampler st          x: h (m); y, z, w carried
//! sampler lab r32ui   labels
//! image   outS rgba32f
//! image   outW r32f   x: wsum
//! image   outD
//! image   hist atomic_u32
//! uniform float uDx   the cell, metres
//! uniform ivec2 uOff;
//! uniform int uBound
//! local 8 4
//! include noise
fn kmain(p: vec2<i32>) {}`, 'demo');
    T.eq('parseSpec: samplers', s.samplers, ['st', 'lab']);
    T.eq('parseSpec: sampler formats', s.samplerFormats, { lab: 'r32ui' });
    T.eq('parseSpec: images, default rgba32f', s.images, { outS: 'rgba32f', outW: 'r32f', outD: 'rgba32f', hist: 'atomic_u32' });
    T.eq('parseSpec: uniforms keep their order, a trailing ; is dropped', s.uniforms, { uDx: 'float', uOff: 'ivec2', uBound: 'int' });
    T.eq('parseSpec: local and include', [s.local, s.includes], [[8, 4], ['noise']]);
    T.eq('parseSpec: Blender push-constant bytes', s.pushBytes(), 16);
    T.throws('parseSpec: a kernel needs an image', () => G.parseSpec('//! sampler st\n', 'k'), 'at least one');
    T.throws('parseSpec: unknown uniform type names the line', () => G.parseSpec('//! image o\n//! uniform mat4 m\n', 'k'), 'k:2:');
    T.throws('parseSpec: unknown format', () => G.parseSpec('//! image o rgba8\n', 'k'), "format 'rgba8'");
    T.throws('parseSpec: declared twice', () => G.parseSpec('//! sampler a\n//! image a\n', 'k'), 'declared twice');
    T.throws('parseSpec: a bad declaration', () => G.parseSpec('//! texture a\n//! image o\n', 'k'), 'cannot read the declaration');
    T.throws('parseSpec: more than 128 bytes of uniforms', () => G.parseSpec('//! image o\n' +
        Array.from({ length: 9 }, (_, i) => `//! uniform vec4 u${i}`).join('\n'), 'k'), '144 bytes');
    // every Blender-style header of the design probes parses to the bindings the plan's table gives (3.3)
    const want = { flow_weights: 2, route_incise: 9, creep: 4, threshold: 7, threshold_excess: 3, h_keep: 2, creep_layers: 4, world_noise_field: 3 };
    const got = {};
    for (const name of Object.keys(want)) {
        const sp = G.loadSource(name, { url: new URL(`wgsl/${name}.wgsl`, PROBES).href }).spec;
        got[name] = sp.samplers.length + Object.keys(sp.images).length;
    }
    T.eq("parseSpec: the probes' kernels bind what plan 3.3 lists", got, want);
    T.eq('nearestNames', G.nearestNames('uDX', ['uDx', 'uDt', 'uBound']), ['uDx', 'uDt']);
}

// ---- 2. the device and the self test
const R = await G.init();
const info = R.info ?? {};
T.extra.adapter = info.description ?? null;
T.extra.limits = { maxStorageBuffersPerShaderStage: R.device.limits.maxStorageBuffersPerShaderStage,
    maxStorageBufferBindingSize: R.device.limits.maxStorageBufferBindingSize,
    maxComputeWorkgroupStorageSize: R.device.limits.maxComputeWorkgroupStorageSize,
    minUniformBufferOffsetAlignment: R.device.limits.minUniformBufferOffsetAlignment };
T.ok('init: the self test read one dispatch back exactly', true, `${info.description ?? ''} ${info.backend ?? ''}`);
T.ok('init: the device offers nine storage buffers per stage', R.device.limits.maxStorageBuffersPerShaderStage >= 9,
    String(R.device.limits.maxStorageBuffersPerShaderStage));
T.ok('init: a second init returns the same runner', (await G.init()) === R);
T.throws('Runner: a device with the default limit of 8 is refused, naming the limit', () => new G.Runner(
    { createBuffer() {}, limits: { maxStorageBuffersPerShaderStage: 8 } }), 'maxStorageBuffersPerShaderStage');

// ---- 3. round trips, exact
{
    const rnd = lcg(3);
    for (const [h, w, c, kind] of [[1, 1, 1, 'f32'], [3, 5, 1, 'f32'], [80, 96, 2, 'f32'], [257, 300, 4, 'f32'], [1024, 1024, 4, 'f32'],
        [7, 9, 1, 'u32'], [33, 17, 1, 'i32']]) {
        const Arr = kind === 'f32' ? Float32Array : kind === 'u32' ? Uint32Array : Int32Array;
        const a = new Arr(h * w * c);
        const bits = new Uint32Array(a.buffer);
        for (let i = 0; i < bits.length; i++) bits[i] = (rnd() * 4294967296) >>> 0;        // every bit pattern, NaNs included
        const f = R.field(h, w, c, a, kind);
        const back = await R.read(f);
        T.ok(`round trip ${h} x ${w} x ${c} ${kind}`, back instanceof Arr && bitsEqual(a, back));
        if (h === 257) {
            const into = new Float32Array(h * w * c);
            const r2 = await R.read(f, into);
            T.ok('read into a preallocated array', r2 === into && bitsEqual(a, into));
            const part = await R.readRange(f, 4 * (100 * w + 7), 12);
            T.ok('readRange: 12 elements from cell (7, 100)', bitsEqual(part, a.subarray(4 * (100 * w + 7), 4 * (100 * w + 7) + 12)));
            const g = R.like(f);
            R.copy(f, g);
            const z = R.like(f);
            const [cg, cz] = await R.readAll([g, z]);
            T.ok('copy on the GPU, and readAll in one wait', bitsEqual(cg, a) && cz.every((v) => v === 0));
            R.clear(g);
            const b2 = a.map((v, i) => i);
            R.write(f, b2);
            const [cg2, cf2] = await R.readAll([g, f]);
            T.ok('clear and write', cg2.every((v) => v === 0) && bitsEqual(cf2, b2));
            g.destroy(); z.destroy();
        }
        f.destroy();
    }
    T.throws('field: three channels are refused', () => R.field(4, 4, 3), 'pad three channels');
    T.throws('field: data of the wrong type is refused', () => R.field(2, 2, 1, new Float64Array(4)), 'Float32Array');
    T.throws('field: data of the wrong length is refused', () => R.field(2, 2, 4, new Float32Array(4)), '= 16 values');
}

// ---- 4. dispatch: accessors, widening, bounds, local size, refusals
{
    const k = R.kernel('probe_accessors', `//! sampler a
//! sampler b
//! sampler lab r32ui
//! image outS rgba32f
//! image outR r32f
//! image outG rg32f
//! image outU r32ui
//! uniform float uF
//! uniform int uI
//! uniform vec3 uV
//! uniform ivec2 uJ
//! local 8 8
fn kmain(p: vec2<i32>) {
  let n = outS_size();
  // no inside() test on purpose: a store outside a field must do nothing (imageStore's rule)
  let q = clamp(p, vec2<i32>(0, 0), n - 1);
  let va = a_at(q);                 // one channel: (r, 0, 0, 1)
  let vb = b_at(q);                 // two channels: (r, g, 0, 1)
  outS_store(p, vec4<f32>(va.x + u.uF, vb.y + f32(u.uI), va.w + vb.w + u.uV.z, f32(a_size().x * 1000 + b_size().y)));
  outR_store(p, vec4<f32>(va.y + va.z + vb.z + u.uV.x, 9.0, 9.0, 9.0));
  outG_store(p, vec4<f32>(f32(u.uJ.x), f32(u.uJ.y) + u.uV.y, 9.0, 9.0));
  outU_store(p, lab_at(q) * 2u + u32(p.x));
}`);
    const h = 13, w = 21;
    const a = Float32Array.from({ length: h * w }, (_, i) => i * 0.5);
    const b = Float32Array.from({ length: h * w * 2 }, (_, i) => -i);
    const lab = Uint32Array.from({ length: h * w }, (_, i) => 0x80000000 + i);
    const fa = R.field(h, w, 1, a), fb = R.field(h, w, 2, b), fl = R.field(h, w, 1, lab, 'u32');
    const oS = R.empty([h, w], 4), oR = R.empty([h, w], 1), oG = R.empty([h, w], 2), oU = R.empty([h, w], 1, 'u32');
    const guard = R.empty([h, w], 4);                               // nothing may write here
    R.run(k, { a: fa, b: fb, lab: fl }, { outS: oS, outR: oR, outG: oG, outU: oU }, { uF: 0.25, uI: -3, uV: [1.5, 2.5, 3.5], uJ: [7, -9] });
    const [S, Rr, Gg, U, gz] = await R.readAll([oS, oR, oG, oU, guard]);
    let ok = true;
    for (let j = 0; j < h && ok; j++) {
        for (let i = 0; i < w && ok; i++) {
            const c = j * w + i;
            ok = S[4 * c] === Math.fround(a[c] + 0.25) && S[4 * c + 1] === b[2 * c + 1] - 3 && S[4 * c + 2] === 1 + 1 + 3.5 &&
                S[4 * c + 3] === w * 1000 + h && Rr[c] === 1.5 && Gg[2 * c] === 7 && Gg[2 * c + 1] === -9 + 2.5 &&
                U[c] === ((lab[c] * 2 + i) >>> 0);
        }
    }
    T.ok('run: accessors, widening to (r, 0, 0, 1) and (r, g, 0, 1), sizes, every uniform type, u32 in and out, local 8 x 8', ok);
    T.ok('run: stores outside a field do nothing (13 x 21 under 8 x 8 groups)', gz.every((v) => v === 0));
    const un = { uF: 0, uI: 0, uV: [0, 0, 0], uJ: [0, 0] }, sm = { a: fa, b: fb, lab: fl }, img = { outS: oS, outR: oR, outG: oG, outU: oU };
    T.throws('run: a missing uniform is refused', () => R.run(k, sm, img, { uF: 0, uI: 0, uV: [0, 0, 0] }), 'uniforms not given: uJ');
    T.throws('run: an undeclared uniform names the nearest', () => R.run(k, sm, img, { ...un, uf: 1 }), "did you mean 'uF'");
    T.throws('run: a missing sampler is refused', () => R.run(k, { a: fa, b: fb }, img, un), 'samplers not given: lab');
    T.throws('run: a missing image is refused', () => R.run(k, sm, { outS: oS, outR: oR, outG: oG }, un), 'images not given: outU');
    T.throws('run: a field as sampler and image is refused', () => R.run(k, { a: oR, b: fb, lab: fl }, img, un), 'use a Pair');
    T.throws('run: a vec3 uniform given two numbers is refused', () => R.run(k, sm, img, { ...un, uV: [0, 0] }), 'needs 3 numbers');
    T.throws('run: a float uniform given a list is refused', () => R.run(k, sm, img, { ...un, uF: [1] }), "uniform 'uF' (float)");
    const k2 = R.kernel('probe_two_images', '//! image o1 r32f\n//! image o2 r32f\nfn kmain(p: vec2<i32>) {}');
    T.throws('run: one field as two images is refused', () => R.run(k2, {}, { o1: oR, o2: oR }, {}), "one field bound as images 'o1' and 'o2'");
    T.throws('run: an image of the wrong format is refused', () => R.run(k, sm, { ...img, outR: guard }, un), 'declared r32f, the field is rgba32f');
    T.throws('run: a float field on an integer sampler is refused', () => R.run(k, { a: fa, b: fb, lab: fa }, img, un), 'declared r32ui');
    T.throws('run: an integer field on a float sampler is refused', () => R.run(k, { a: fl, b: fb, lab: fl }, img, un), 'float sampler');
    const dead = R.empty([h, w], 1);
    dead.destroy();
    T.throws('run: a released field is refused', () => R.run(k, { a: dead, b: fb, lab: fl }, img, un), 'released field');
    T.throws('kernel: a missing file names the nearest kernel', () => R.kernel('comon'), "did you mean 'common'");
    await T.rejects('kernel: a compile error names the kernel and lists the source', async () => {
        const bad = R.kernel('broken_kernel', '//! image o r32f\nfn kmain(p: vec2<i32>) { o_store(p, vec4<f32>(nope)); }');
        R.run(bad, {}, { o: R.empty([2, 2], 1) }, {});
        await R.idle();
    }, "kernel 'broken_kernel' failed to compile");
    T.ok('kernel: the same source gives the same Kernel', R.kernel('x', '//! image o r32f\nfn kmain(p: vec2<i32>) {}') ===
        R.kernel('x', '//! image o r32f\nfn kmain(p: vec2<i32>) {}'));
    const kd = R.kernel('with_defines', { source: '//! image o r32f\nfn kmain(p: vec2<i32>) { o_store(p, vec4<f32>(f32(RAYS) * SCALE)); }',
        defines: { RAYS: 12, SCALE: '0.5' }, common: false });
    const od = R.empty([2, 2], 1);
    R.run(kd, {}, { o: od }, {});
    T.ok('kernel: defines become consts; common.wgsl can be left out', (await R.read(od)).every((v) => v === 6));
    for (const f of [fa, fb, fl, oS, oR, oG, oU, guard, od]) f.destroy();
}

// ---- 5. a Pair, a uniform slot per dispatch, batches that span several command buffers
{
    const k = R.kernel('probe_step', `//! sampler st
//! image outS rg32f
//! uniform float uAdd
//! uniform int uIter
fn kmain(p: vec2<i32>) {
  let n = st_size();
  if (!inside(p, n)) { return; }
  let c = st_at(p);
  // x accumulates this dispatch's own uniform; y counts the dispatches whose index arrived in order
  outS_store(p, vec4<f32>(c.x + u.uAdd, c.y + select(0.0, 1.0, i32(c.y) == u.uIter), 0.0, 0.0));
}`);
    const pp = R.pair(40, 24, 2);
    const N = 20000;                                                // more than one ring (16384 slots)
    const d0 = R.dispatches, s0 = R.submits;
    let want = 0;
    for (let i = 0; i < N; i++) {
        const add = (i % 7) + 1;
        R.run(k, { st: pp.src }, { outS: pp.dst }, { uAdd: add, uIter: i });
        pp.swap();
        want += add;
    }
    const out = await pp.read();
    T.ok(`pair: ${N} dispatches, each with its own uniforms, in order`, out.every((v, i) => v === (i % 2 ? N : want)),
        `x ${out[0]} (want ${want}), y ${out[1]}`);
    T.ok('batching: 512 dispatches a submit', R.dispatches - d0 === N && R.submits - s0 === Math.ceil(N / G.SUBMIT_EVERY),
        `${R.submits - s0} submits`);
    T.eq('bind groups: two for the pair', [...R.bindGroups.keys()].filter((key) => key.includes(`,${pp.src.id}`) || key.includes(`,${pp.dst.id}`)).length, 2);
    const before = R.bindGroups.size;
    pp.destroy();
    T.eq('release: a field takes its bind groups with it', before - R.bindGroups.size, 2);
    // per-dispatch uniforms through cell_hash: the iteration index reaches common.wgsl's hash (dune decisions)
    const kh = R.kernel('probe_hash', `//! image outH r32ui
//! uniform int uIter
//! uniform int uSeed
fn kmain(p: vec2<i32>) { outH_store(p, cell_hash(p, u.uIter, u.uSeed)); }`);
    const a = R.empty([4, 4], 1, 'u32'), b = R.empty([4, 4], 1, 'u32'), c = R.empty([4, 4], 1, 'u32');
    R.run(kh, {}, { outH: a }, { uIter: 3, uSeed: 11 });
    R.run(kh, {}, { outH: b }, { uIter: 4, uSeed: 11 });
    R.run(kh, {}, { outH: c }, { uIter: 3, uSeed: 11 });
    const [ha, hb, hc] = await R.readAll([a, b, c]);
    T.ok('uniform slots: three dispatches of one batch keep their own values', bitsEqual(ha, hc) && !bitsEqual(ha, hb));
    for (const f of [a, b, c]) f.destroy();
}

// ---- 6. packs on the GPU, a texture, the GPU's clock
{
    const h = 37, w = 53, rnd = lcg(9);
    const mk = () => Float32Array.from({ length: h * w }, () => Math.fround(rnd() * 2000 - 1000));
    const A = mk(), B = mk(), C = mk();
    const fields = { h: R.field(h, w, 1, A), A: R.field(h, w, 1, B), carried: R.field(h, w, 1, C) };
    const st = R.pack(fields, ['h', 'A', null, 'carried']);
    const P = await R.read(st);
    let ok = true;
    for (let i = 0; i < h * w && ok; i++) ok = P[4 * i] === A[i] && P[4 * i + 1] === B[i] && P[4 * i + 2] === 0 && P[4 * i + 3] === C[i];
    T.ok('pack: four named fields into one RGBA pack, a missing name zero', ok);
    const un = R.unpack(st, ['h', null, null, 'carried']);
    const [uh, uc] = await R.readAll([un.h, un.carried]);
    T.ok('unpack: the named channels back, exact', bitsEqual(uh, A) && bitsEqual(uc, C) && Object.keys(un).length === 2);
    for (const [fmt, c] of [['rgba32float', 4], ['r32float', 1]]) {
        const src = c === 4 ? st : fields.h;
        const tex = R.device.createTexture({ size: [w, h], format: fmt, usage: GPUTextureUsage.COPY_DST | GPUTextureUsage.COPY_SRC });
        R.toTexture(src, tex);
        R.flush();
        const stride = Math.ceil((w * c * 4) / 256) * 256;
        const rb = R.device.createBuffer({ size: stride * h, usage: GPUBufferUsage.COPY_DST | GPUBufferUsage.MAP_READ });
        const enc = R.device.createCommandEncoder();
        enc.copyTextureToBuffer({ texture: tex }, { buffer: rb, bytesPerRow: stride, rowsPerImage: h }, [w, h, 1]);
        R.device.queue.submit([enc.finish()]);
        await rb.mapAsync(GPUMapMode.READ);
        const got = new Float32Array(rb.getMappedRange().slice(0));
        rb.unmap();
        const ref = c === 4 ? P : A;
        let same = true;
        for (let j = 0; j < h && same; j++) for (let i = 0; i < w * c && same; i++) same = got[(j * stride) / 4 + i] === ref[j * w * c + i];
        T.ok(`toTexture: a ${c}-channel field into an ${fmt} texture (rows of ${w * c * 4} bytes)`, same);
        rb.destroy(); tex.destroy();
    }
    const ms = await R.timed(() => { for (let i = 0; i < 8; i++) R.pack(fields, ['h', 'A', null, 'carried']).destroy(); });
    T.ok("timed: the GPU's own time of a pass", ms === null ? !R.device.features.has('timestamp-query') : ms > 0 && ms < 1000, `${ms} ms`);
    for (const f of [st, ...Object.values(fields), ...Object.values(un)]) f.destroy();
}

// ---- 7. the 46 fixture cases of the Blender numpy twins, the hashes and the world noise, through this runner (on
// this plain device; scene_device_test.mjs runs them on render_common's), and a u32(0) kernel (plan 4.2, C7)
await u32ZeroCheck(R, T, 'a plain device');
const FIX = twinFixtures(Deno.args[0]);
if (FIX) {
    const r = await twinChecks(R, T, FIX, 'a plain device');
    T.extra.twin_cases = r.cases;
    T.extra.twin_cases_worst = r.worst;
    T.extra.world_noise_ratio = r.worldNoise;
    T.extra.twin_fixture_versions = r.versions;
}

// ---- 8. the dispatch hook (plan 4.2, 5.7): a record per dispatch and per readback, a snapshot inside it, off
{
    const recs = [], reads = [];
    G.onDispatch((r) => recs.push({ index: r.index, op: r.op, kernel: r.kernel, blender: r.blender, count: r.count, uniforms: { ...r.uniforms },
        images: Object.entries(r.images).map(([n, f]) => [n, f.h, f.w, f.format]), samplers: Object.keys(r.samplers) }));
    G.onReadback((r) => reads.push({ after: r.afterDispatch, op: r.op, name: r.name, shape: r.shape, n: r.data.length }));
    G.context.op = 'probe_op';
    const k = R.kernel('hook_probe', `//! sampler a
//! image   o r32f
//! uniform float uK
//! uniform int uI
fn kmain(p: vec2<i32>) { o_store(p, vec4<f32>(a_at(p).x * u.uK + f32(u.uI), 0.0, 0.0, 0.0)); }`);
    const a = R.field(3, 5, 1, Float32Array.from({ length: 15 }, (_, i) => i));
    const o = R.empty([3, 5], 1);
    a.name = 'h';
    o.name = 'out';
    const d0 = R.dispatches;
    R.run(k, { a }, { o }, { uK: 2.5, uI: 3 });
    R.run(k, { a }, { o }, { uK: 2.5, uI: 3 });
    await R.read(o);
    T.ok('hook: a record per dispatch: op, kernel, blender (false: the port\'s own), uniforms, bound images and samplers, count',
        recs.length === 2 && recs[0].index === d0 + 1 && recs[0].op === 'probe_op' && recs[0].kernel === 'hook_probe' &&
        recs[0].blender === false && recs[0].count === 1 && recs[1].count === 2 && recs[0].uniforms.uK === 2.5 &&
        recs[0].uniforms.uI === 3 && JSON.stringify(recs[0].images) === '[["o",3,5,"r32f"]]' &&
        JSON.stringify(recs[0].samplers) === '["a"]', JSON.stringify(recs));
    T.ok('hook: a record per field read: afterDispatch, op, name, shape, data', reads.length === 1 && reads[0].after === d0 + 2 &&
        reads[0].op === 'probe_op' && reads[0].name === 'out' && JSON.stringify(reads[0].shape) === '[3,5,1]' && reads[0].n === 15,
        JSON.stringify(reads));
    const pf = blenderMarks(R);
    T.ok('hook: blender_kernel marks a transcribed Blender kernel (kernels/<name>.wgsl, or blender: true), not kernels/prims/ or source text',
        pf.prims === false && pf.source === false && pf.marked === true, JSON.stringify(pf));
    // a step snapshot: taken in the hook at its count, it holds that dispatch's output, not the next one's
    let snap = null;
    G.onDispatch((r) => {
        if (r.kernel === 'hook_probe' && r.count === 1) [snap] = r.runner.snapshot([r.images.o]);
    });
    R.run(k, { a }, { o }, { uK: 2.5, uI: 3 });
    R.run(k, { a }, { o }, { uK: 0, uI: 7 });
    const [s, now] = await R.readAll([snap, o]);
    T.ok('hook: a snapshot copied inside the hook holds exactly its own dispatch\'s output', s.every((v, i) => v === 2.5 * i + 3) &&
        now.every((v) => v === 7));
    G.onDispatch(null);
    G.onReadback(null);
    G.context.op = null;
    const n0 = recs.length, r0 = reads.length;
    R.run(k, { a }, { o }, { uK: 1, uI: 0 });
    await R.read(o);
    T.ok('hook: off, nothing is called', recs.length === n0 && reads.length === r0);
    for (const f of [a, o, snap]) f.destroy();
}

function blenderMarks(R) {
    return { prims: R.kernel('prims/pack').blender, source: R.kernel('x', '//! image o r32f\nfn kmain(p: vec2<i32>) {}').blender,
        marked: R.kernel('flow_weights', { url: new URL('wgsl/flow_weights.wgsl', PROBES).href, blender: true }).blender };
}

T.extra.compile_ms = R.compileMs;
T.extra.counters = { dispatches: R.dispatches, submits: R.submits, fields_alive: R.fields, peak_field_mb: +(R.peakFieldBytes / 2 ** 20).toFixed(1) };
const code = T.done('runner_test.json');
G.shutdown();
Deno.exit(code);
