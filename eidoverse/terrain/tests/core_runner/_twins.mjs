// The 46 fixture cases of the Blender numpy twins, the hashes and the world noise, run through the production runner
// (PORT_PLAN.md 4.6, 4.7, 8.2 P1): runner_test.mjs runs them on a plain device, scene_device_test.mjs on the device
// eidoverse/render_common.mjs makes for a scene (its createShaderModule wrapper included). The kernels are the design
// probes' transcriptions (tests/design_probes/wgsl/), read as they are: their production copies belong to the
// packages that own them (plan 3.3).

import { PROBES, bitsEqual, fixtureDir, loadBin } from './_common.mjs';

export const TWIN_HINT = "<Blender's python> -I eidoverse/terrain/tests/core_runner/twin_fixtures.py";

/** The twin fixtures' folder (the first argument, else tests/out/core_runner/twin_fixtures/), or null with a hint. */
export function twinFixtures(arg) {
    return fixtureDir('twin_fixtures', arg, TWIN_HINT);
}

/** Run every case on R and add the checks to T, each named with `where` (the device). Returns the numbers. */
export async function twinChecks(R, T, FIX, where) {
    const man = JSON.parse(Deno.readTextFileSync(new URL('manifest.json', FIX)));
    const K = {};
    for (const name of ['flow_weights', 'route_incise', 'creep', 'threshold_excess', 'threshold', 'creep_layers', 'h_keep',
        'world_noise_field', 'hash_probe']) {
        K[name] = R.kernel(name, { url: new URL(`wgsl/${name}.wgsl`, PROBES).href, blender: name !== 'hash_probe' });
    }
    const cases = {};
    let worstAll = 0;
    for (const c of man.cases) {
        const k = K[c.kernel];
        const samplers = {}, images = {};
        for (const [s, a] of Object.entries(c.inputs)) samplers[s] = R.field(a.shape[0], a.shape[1], a.shape[2], loadBin(FIX, a));
        for (const [im, a] of Object.entries(c.outputs)) images[im] = R.field(a.shape[0], a.shape[1], a.shape[2]);
        R.run(k, samplers, images, c.uniforms);
        const names = Object.keys(c.outputs);
        const got = await R.readAll(names.map((n) => images[n]));
        let worst = 0;
        names.forEach((im, idx) => {
            const a = c.outputs[im], want = loadBin(FIX, a), C = a.shape[2];
            for (let ch = 0; ch < C; ch++) {                       // Blender's compare(): per channel, max |d| / range
                let lo = Infinity, hi = -Infinity, amax = 0, err = 0;
                for (let i = ch; i < want.length; i += C) {
                    const v = want[i];
                    lo = Math.min(lo, v); hi = Math.max(hi, v); amax = Math.max(amax, Math.abs(v));
                    err = Math.max(err, Math.abs(got[idx][i] - v));
                }
                worst = Math.max(worst, err / Math.max(hi - lo, 1e-6 * amax, 1e-20));
            }
        });
        cases[c.label] = +worst.toExponential(3);
        worstAll = Math.max(worstAll, worst);
        for (const f of [...Object.values(samplers), ...Object.values(images)]) f.destroy();
    }
    const failed = Object.entries(cases).filter(([, v]) => !(v <= 1e-4)).map(([n]) => n);
    T.ok(`twin fixtures (${where}): ${man.cases.length} kernel cases within 1e-4 of range`, man.cases.length === 46 && !failed.length,
        `worst ${worstAll.toExponential(3)}${failed.length ? '; failed: ' + failed.join(', ') : ''}`);

    const H = 80, W = 96, hm = man.hashes;
    const imgs = { outPcg: R.empty([H, W], 1, 'u32'), outPcg2: R.empty([H, W], 1, 'u32'), outPcg3: R.empty([H, W], 1, 'u32'),
        outCell: R.empty([H, W], 1, 'u32'), outU01: R.empty([H, W], 1), outGrad: R.empty([H, W], 2), outH2: R.empty([H, W], 1, 'u32') };
    const dummy = R.empty([1, 1], 1);
    R.run(K.hash_probe, { dummy }, imgs, {});
    const [pcg, pcg2, pcg3, cell, u01, , h2] = await R.readAll(Object.values(imgs));
    const hashes = { pcg: bitsEqual(pcg, loadBin(FIX, hm.pcg)), pcg2: bitsEqual(pcg2, loadBin(FIX, hm.pcg2)),
        pcg3: bitsEqual(pcg3, loadBin(FIX, hm.pcg3)), cell_hash: bitsEqual(cell, loadBin(FIX, hm.cell_hash_it3_seed11)),
        u01: bitsEqual(u01, loadBin(FIX, hm.u01_of_pcg)), ekigar_hash2_integer: bitsEqual(h2, loadBin(FIX, hm.ekigar_hash2_u32)) };
    T.ok(`hashes (${where}): common.wgsl's PCG chain, cell_hash and u01, and Ekigar's lattice hash, bit for bit against the numpy twins`,
        Object.values(hashes).every(Boolean), JSON.stringify(hashes));
    for (const f of [...Object.values(imgs), dummy]) f.destroy();

    const nz = man.noise, n = nz.shape[0];
    const out = R.empty([n, n], 1), terms = R.field(1, 2 * nz.n_terms, 4, loadBin(FIX, nz.terms)), disp = R.empty([n, n], 2);
    R.run(K.world_noise_field, { terms, disp }, { outF: out }, { uTerms: nz.n_terms, uCell: nz.cell, uConst: nz.const });
    const got = await R.read(out), want = loadBin(FIX, nz.expected_float64_as_f32);
    let lo = Infinity, hi = -Infinity, err = 0;
    for (let i = 0; i < want.length; i++) { lo = Math.min(lo, want[i]); hi = Math.max(hi, want[i]); err = Math.max(err, Math.abs(got[i] - want[i])); }
    T.ok(`world noise (${where}): within 1e-5 of range of numpy's float64 field, 40 km from the origin`, err / (hi - lo) <= 1e-5,
        `${(err / (hi - lo)).toExponential(3)} of range`);
    for (const f of [out, terms, disp]) f.destroy();
    return { cases, worst: +worstAll.toExponential(3), worldNoise: +(err / (hi - lo)).toExponential(3), versions: {
        python: man.python ?? null, numpy: man.numpy ?? null, zlib: man.zlib ?? null } };
}

/** A kernel that declares `var c = u32(0);`: render_common.mjs's wrapper would make it an i32 and fail it; through
 * GPUDevice.prototype.createShaderModule (core/gpu.js) it compiles and counts on every device (plan 4.2, C7). */
export async function u32ZeroCheck(R, T, where) {
    const k = R.kernel('u32_zero', `//! image o r32ui
fn kmain(p: vec2<i32>) {
  var c = u32(0);
  for (var i = 0; i < 3; i++) { c += 2u; }
  o_store(p, c);
}`);
    const o = R.empty([2, 3], 1, 'u32');
    R.run(k, {}, { o }, {});
    const v = await R.read(o);
    o.destroy();
    T.ok(`compile (${where}): a kernel declaring var c = u32(0) compiles and runs exactly`, v.every((x) => x === 6), Array.from(v).join(' '));
}
