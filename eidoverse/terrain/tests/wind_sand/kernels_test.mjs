// The dune kernels against the Blender edition's numpy twins (PORT_PLAN.md 5.1, 5.3, 8.2 P8: "kernel fixtures (the
// hash decisions identical)").
//
//     deno run --config deno.json --frozen --unstable-webgpu --allow-all eidoverse/terrain/tests/wind_sand/kernels_test.mjs
//
// (from the repository root; on a shared machine behind $EIDO_GPU_WRAP). The cases are the Blender package test's own
// (blender/tests/terrain/wind_sand/test_gpu.py test_parity: a non-square 96 x 80 field with pins, every boundary mode,
// four wind directions, the wind unturned and steered, three speed-up powers, both rise modes), recorded through the
// twins by tests/parity/fixtures.py --kernels under Blender's own Python. Checked here:
//   headers    each kernels/dune_*.wgsl declares exactly the //! lines of its GLSL (dune_avalanche: aeolian.py's
//              AVALANCHE_SRC), and its uniforms fit Blender's 128 push-constant bytes
//   shadow     dune_shadow within 1e-4 of each output channel's range (the kernel grade)
//   activate   dune_activate's plan records identical to the twin's, record for record (lift, hop x, hop y, landing
//              hop): every decision is an integer hash, so a correct port makes exactly the twin's
//   transport  dune_transport's sand identical to the twin's (the gather adds the same slabs in the same order)
//   avalanche  dune_avalanche within 1e-4 of range
// JavaScript per cell here is test code.

import * as G from '../../core/gpu.js';
import * as C from '../parity/_common.mjs';
import * as S from './_common.mjs';

const T = new S.Checks('wind and sand: the dune kernels against the Blender twins');
const R = await G.init();

// ---- the interfaces
const SOURCES = { dune_shadow: S.blenderSource('kernels/dune_shadow.glsl'), dune_activate: S.blenderSource('kernels/dune_activate.glsl'),
    dune_transport: S.blenderSource('kernels/dune_transport.glsl'), dune_avalanche: S.avalancheSource() };
for (const [name, glsl] of Object.entries(SOURCES)) {
    const k = R.kernel(name);
    const mine = S.headerLines(k.text);
    if (glsl === null) {
        S.W.skip(`${name}: the header against Blender's`, 'set EIDO_BLENDER_EDITION to a checkout of the blender branch');
    } else {
        const theirs = S.headerLines(glsl);
        T.ok(`${name}: the //! declarations are the Blender kernel's, line for line`, JSON.stringify(mine) === JSON.stringify(theirs),
            `${mine.length} lines` + (JSON.stringify(mine) === JSON.stringify(theirs) ? '' : `; port ${JSON.stringify(mine)} | Blender ${JSON.stringify(theirs)}`));
    }
    T.ok(`${name}: its uniforms fit Blender's push constants (${G.PUSH_LIMIT_BYTES} bytes)`, k.spec.pushBytes() <= G.PUSH_LIMIT_BYTES,
        `${k.spec.pushBytes()} bytes`);
    T.ok(`${name}: marked a transcribed Blender kernel in the dispatch log`, k.blender === true);
}

// ---- the fixture cases
const fx = C.loadFixture('kernels');
const summary = {};
if (fx) {
    const runs = [
        ['dune_shadow', { uses: ['divide'] }, 'within 1e-4 of range'],
        ['dune_activate', { exact: { outPlan: [0, 1, 2, 3] } }, 'plan records identical to the twin\'s'],
        ['dune_transport', { exact: { outSt: [0, 1] } }, 'transported sand identical to the twin\'s'],
        ['dune_avalanche', { uses: ['divide'] }, 'within 1e-4 of range'],
    ];
    for (const [name, opts, what] of runs) {
        const r = await C.kernelCases(R, name, { ...opts, fixture: fx });
        const modes = [...new Set(fx.manifest.cases.filter((c) => c.kernel === name).map((c) => c.uniforms.uBound))].sort();
        summary[name] = { cases: r.n, worst: r.worst, failed: r.failed, boundary_modes: modes };
        T.ok(`${name}: ${r.n} cases of the Blender test's parity set (boundary modes ${modes.join(', ')}), ${what}`,
            r.ok && r.n >= (name === 'dune_avalanche' ? 3 : 24) && modes.length === 3, r.detail);
    }
}

G.shutdown();
Deno.exit(S.finish(T, 'kernels_test', { fixtures: fx?.dir ?? null, versions: fx?.manifest?.versions ?? null, summary }));
