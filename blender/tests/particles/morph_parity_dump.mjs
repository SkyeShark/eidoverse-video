// morph_parity_dump.mjs: runs the WebGPU edition's particle_morph.js (untouched) headless in Deno with Math.random
// replaced by a seeded mulberry32 stream, and dumps what its CPU side builds: the target generators (neuralNet,
// neuronGraph, fromPoints up- and down-sampling), and makeParticleMorph's per-instance buffers (iFrom, iTo, iSeed)
// before and after morph() swaps the segment and updateTarget() replaces one. test_morph_parity.py replays the same
// calls on the same stream in the Blender port and compares number for number. Nothing renders: the TSL material
// graphs are built but never compiled.
//
// three.js draws from Math.random too: every UUID (an Object3D such as the Scene passed in, a geometry, a material,
// each TSL node) takes 4 draws. The dump counts the draws and records the stream position around each call, so the
// replay can skip three's own draws and compare only the morph's (targets, then seeds, which come first and together).
//   cd <worktree> && deno run --no-config --no-lock -A blender/tests/particles/morph_parity_dump.mjs <three build dir>
// (the three build dir: a node_modules/three/build folder, e.g. the main checkout's)
const threeDir = Deno.args[0];
if (!threeDir) throw new Error('usage: morph_parity_dump.mjs <node_modules/three/build dir>');
const url = (p) => new URL('file:///' + p.replace(/\\/g, '/').replace(/^\/+/, ''));
const W = await import(url(threeDir + '/three.webgpu.js'));
globalThis.THREE = { ...W, ...W.TSL };
await import(url(Deno.cwd() + '/eidoverse/particle_morph.js'));

// the same generator as eidoblend.fx.particle_morph.JSRandom
function mulberry32(a) {
    return function () {
        a = (a + 0x6D2B79F5) | 0;
        let t = a;
        t = Math.imul(t ^ (t >>> 15), t | 1);
        t ^= t + Math.imul(t ^ (t >>> 7), t | 61);
        return ((t ^ (t >>> 14)) >>> 0) / 4294967296;
    };
}
const stream = mulberry32(12345);
let calls = 0;
Math.random = () => { calls++; return stream(); };
const PM = globalThis.ParticleMorph;
const arr = (a) => Array.from(a);
const out = { calls: {} };
out.first_randoms = [Math.random(), Math.random(), Math.random()];
const nn = PM.neuralNet({ count: 3000, layers: [4, 7, 5, 3] });
const nnDef = PM.neuralNet({ count: 2000 });
const ng = PM.neuronGraph({ count: 3000, nodes: 40, k: 3 });
const ngDef = PM.neuronGraph({ count: 2000 });
const up = PM.fromPoints([[0, 0, 0], [1, 2, 3], [-1, 0.5, 2], [0.3, -0.2, 0.1]], 500);
const down = PM.fromPoints(nn, 1000);
Object.assign(out, { nn: arr(nn), nn_def: arr(nnDef), ng: arr(ng), ng_def: arr(ngDef), up: arr(up), down: arr(down) });
out.calls.before_make = calls;
const scene1 = new THREE.Scene();                 // three's UUID: 4 draws
out.calls.after_scene = calls;
const m = globalThis.makeParticleMorph({ scene: scene1, count: 1500, targets: [nn, ng, up] });
out.calls.after_make = calls;
const g = m.mesh.geometry;
out.morph_from0 = arr(g.attributes.iFrom.array);
out.morph_to0 = arr(g.attributes.iTo.array);
out.morph_seed = arr(g.attributes.iSeed.array);
m.morph(1, 2, 1.3);                          // segment swap, m clamped to 1, turb defaults to sin(pi m)
out.morph_from1 = arr(g.attributes.iFrom.array);
out.morph_to1 = arr(g.attributes.iTo.array);
out.morph_u = { morph: m.uniforms.morph.value, turb: m.uniforms.turb.value };
m.morph(1, 2, 0.25, 0.8);
out.morph_u2 = { morph: m.uniforms.morph.value, turb: m.uniforms.turb.value };
out.calls.before_update = calls;
m.updateTarget(2, down);                      // the active To buffer is re-uploaded
out.calls.after_update = calls;
out.morph_to2 = arr(g.attributes.iTo.array);
out.colors = { color: arr(m.uniforms.color.value.toArray()), color2: arr(m.uniforms.color2.value.toArray()),
    size: m.uniforms.size.value, opacity: m.uniforms.opacity.value };
const scene2 = new THREE.Scene();
out.calls.before_make2 = calls;
const m2 = globalThis.makeParticleMorph({ scene: scene2, count: 10, targets: [up, up], color: 0xff7a30 });
out.calls.after_make2 = calls;
out.morph2_seed = arr(m2.mesh.geometry.attributes.iSeed.array);
out.colors_one = { color: arr(m2.uniforms.color.value.toArray()), color2: arr(m2.uniforms.color2.value.toArray()) };
out.calls.end = calls;
out.last_random = Math.random();
const dir = Deno.cwd() + '/blender/tests/particles/out/parity';
await Deno.mkdir(dir, { recursive: true });
await Deno.writeTextFile(dir + '/morph_parity.json', JSON.stringify(out));
console.log('[morph parity] wrote', dir + '/morph_parity.json', 'nn', nn.length / 3, 'ng', ng.length / 3,
    'draws', JSON.stringify(out.calls));
