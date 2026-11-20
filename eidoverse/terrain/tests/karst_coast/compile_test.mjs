// Every kernel of the karst-and-coast package compiles (kernels/coast_*.wgsl and kernels/karst/*.wgsl), each through
// core/gpu.js's check() (the prototype's createShaderModule, plan C7), with every failure listed, not only the first.
//
//     deno run --no-config --no-lock --unstable-webgpu --allow-all eidoverse/terrain/tests/karst_coast/compile_test.mjs
//         (on a shared machine, behind $EIDO_GPU_WRAP)
// Writes tests/out/karst_coast/compile_test.json.

import * as G from '../../core/gpu.js';
import * as CO from '../../solvers/coast.js';
import * as C from '../parity/_common.mjs';
import * as KC from './_common.mjs';

const T = new C.Checks('karst and coast: every kernel compiles');
const R = await G.init();
const names = [];
for (const e of Deno.readDirSync(new URL('../../kernels/karst/', import.meta.url))) {
    if (e.isFile && e.name.endsWith('.wgsl') && e.name !== 'lib.wgsl') names.push(`karst/${e.name.slice(0, -5)}`);
}
names.sort();
const kernels = [['coast_fetch_16', () => CO.fetchKernel(R, 16)], ['coast_seed', () => R.kernel('coast_seed')],
    ['coast_jfa', () => R.kernel('coast_jfa')], ...names.map((n) => [n, () => R.kernel(n)])];
const failed = [];
for (const [name, make] of kernels) {
    try {
        const k = make();
        await R.check(k, k.spec.samplers.map(() => 1));
    } catch (e) {
        failed.push(name);
        console.log(`--- ${name}: ${String(e.message).split('\n').slice(0, 8).join('\n')}`);
    }
}
T.ok(`${kernels.length} kernels compile`, failed.length === 0, failed.join(', ') || kernels.map((k) => k[0]).join(', '));
Deno.exit(KC.finish(T, 'compile_test'));
