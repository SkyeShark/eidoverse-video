// rotary_js_dump.mjs: runs the WebGPU edition's rotary carving planner (eidoverse/robotics/rotary_*.js, untouched)
// headless in Deno and dumps what the Blender port must reproduce, for test_rotary_parity.py to compare. Nothing
// renders. Every position is dumped in three's axes; the Python side converts (x, y, z) -> (x, -z, y).
//   cd <main checkout>    (its deno.json + node_modules resolve three; blender/tests/_where.py main_checkout())
//   deno run --no-check -A --node-modules-dir=manual --no-lock --config deno.json \
//       <this checkout>/blender/tests/fabrication_rotary/rotary_js_dump.mjs [full]
const here = new URL('.', import.meta.url);
const repo = new URL('../../../', here);
const outDir = new URL('out/js_parity/', here);
await Deno.mkdir(outDir, { recursive: true });
const R = (p) => import(new URL('eidoverse/robotics/' + p, repo).href);
const T = await import('three/webgpu');
const RP = await R('rotary_path.js');
const RS = await R('rotary_stock.js');
const RR = await R('rotary_removal.js');
const RM = await R('rotary_mesh.js');
const SU = await R('rotary_setup.js');
const CU = await R('cutting.js');
const SG = await R('source_geometry.js');
const full = Deno.args.includes('full');
const write = async (name, obj) => {
  await Deno.writeTextFile(new URL(name + '.json', outDir), JSON.stringify(obj));
  console.log('wrote', name);
};
const pick = (s) => Object.fromEntries(Object.entries(s).filter(([k, v]) => typeof v !== 'function'));
const segs = (path) => path.segments.map((s) => {
  const o = { ...s };
  delete o.d;
  return o;
});
let seed = 12345;
const rand = () => {
  seed = (seed * 16807) % 2147483647;
  return seed / 2147483647;
};

// ------------------------------------------------------------------ fixture setup, blank, sample, surface, materials
const setups = [{}, { stockLength: .08, stockWidth: .018, stockHeight: .026 }, { stockLength: .18, stockWidth: .044, stockHeight: .05 },
  { stockLength: .1, stockWidth: .02, stockHeight: .045, quill: .003 }, { stockLength: .13, quill: -.004 }].map((o) => ({ o, r: SU.rotaryFixtureSetup(o) }));
const setupErrors = [{ stockLength: .07 }, { stockWidth: .06 }, { stockLength: .18, quill: -.006 }, { quill: .007 }, { stockLength: NaN }]
  .map((o) => { try { SU.rotaryFixtureSetup(o); return { o, e: null }; } catch (e) { return { o, e: e.message }; } });
const blankS = { stockLength: .14, stockHeight: .036, stockWidth: .03 };
const blankPts = [];
for (let i = 0; i < 400; i++) blankPts.push([(rand() - .5) * .16, (rand() - .5) * .05, (rand() - .5) * .05]);
for (let i = 0; i < 100; i++) blankPts.push([.062 + rand() * .01, (rand() - .5) * .004, (rand() - .5) * .004]);
const blank = blankPts.map((p) => [p, RP.rotaryBlankDistance(p, blankS)]);
const samplePts = [];
for (let i = 0; i < 300; i++) samplePts.push([-.06 + rand() * .12, rand() * 7 - 1]);
const sample = samplePts.map(([x, t]) => [x, t, RP.sampleRotary(x, t), RP.sampleRotary(x, t, { start: -.03, end: .05, stockWidth: .03, stockHeight: .044 })]);
const surf = RP.rotarySurface(RP.sampleRotary, { nx: 12, na: 20 });
const materials = Object.fromEntries(['aluminum', 'brass', 'steel', 'wood', 'plywood', 'metal', 'aluminium', 'hardwood'].map((n) => [n, CU.stockProfile(n)]));
await write('basics', { setups, setupErrors, blankS, blank, sample, materials, surface: { position: Array.from(surf.getAttribute('position').array), index: Array.from(surf.index.array) } });

// ------------------------------------------------------------------ programs
const programs = {
  wood_ball_16: [RP.sampleRotary, { angles: 16, sampleStep: .004 }],
  wood_flat_16: [RP.sampleRotary, { angles: 16, sampleStep: .004, tool: 'flat', fluteLength: .018 }],
  alu_ball_16: [RP.sampleRotary, { angles: 16, sampleStep: .004, material: 'aluminum' }],
  brass_ball_16: [RP.sampleRotary, { angles: 16, sampleStep: .004, material: 'brass' }],
  wood_32: [RP.sampleRotary, { angles: 32, sampleStep: .002, stepdown: .006 }],
  odd_blank: [RP.sampleRotary, { angles: 20, sampleStep: .003, stockLength: .12, stockWidth: .03, stockHeight: .044, tool: 'flat', fluteLength: .018 }],
  custom_fn: [(x, a) => .0125 + .002 * Math.cos(2 * a) + .001 * Math.sin(40 * x), { angles: 24, sampleStep: .003, tool: 'flat', fluteLength: .018, roughAllowance: .0004 }],
};
const progDump = {};
for (const [name, [src, o]] of Object.entries(programs)) {
  const p = RP.rotaryProgram(src, o);
  const times = [0, .37, 1.9, p.path.duration * .173, p.path.duration * .5, p.path.duration * .91, p.path.duration, p.path.duration + 3];
  progDump[name] = { o, moves: p.moves, stages: p.stages, settings: p.settings, duration: p.path.duration, segments: segs(p.path),
    samples: times.map((t) => p.path.sample(t)) };
}
const progErrors = [
  [RP.sampleRotary, { stepdown: Infinity }], [() => .003, { angles: 16, sampleStep: .004 }], [RP.sampleRotary, { angles: 15 }],
  [RP.sampleRotary, { angles: 16.5 }], [RP.sampleRotary, { sampleStep: .00005 }], [RP.sampleRotary, { start: -.08 }],
  [RP.sampleRotary, { radius: -1 }], [RP.sampleRotary, { feed: 0 }], [RP.sampleRotary, { tool: 'vee' }], [RP.sampleRotary, { material: 'cheese' }],
  [() => .03, { angles: 16, sampleStep: .004 }],
].map(([s, o]) => { try { RP.rotaryProgram(s, o); return { o, e: null }; } catch (e) { return { o, e: e.message }; } });
await write('programs', { programs: progDump, errors: progErrors });

// ------------------------------------------------------------------ hand-made paths and the swept cutter
const handPaths = {
  removal_once: [
    { position: [-.025, .014, 0], angle: 0, type: 'rapid' }, { position: [.025, .014, 0], angle: 0, type: 'cut' },
    { position: [.025, .04, 0], angle: 0, type: 'rapid' }, { position: [-.025, .04, 0], angle: 0, type: 'cut' }],
  removal_twice: [
    { position: [-.025, .014, 0], angle: 0, type: 'rapid' }, { position: [.025, .014, 0], angle: 0, type: 'cut' },
    { position: [-.025, .014, 0], angle: 0, type: 'cut' }, { position: [.025, .014, 0], angle: 0, type: 'cut' },
    { position: [.025, .04, 0], angle: 0, type: 'rapid' }, { position: [-.025, .04, 0], angle: 0, type: 'cut' }],
  wiggle: [
    { position: [0, .03, 0], angle: 0, type: 'rapid' }, { position: [0, .03, 0], angle: 1.2, type: 'index' },
    { position: [.01, .02, 0], angle: 1.2, type: 'rapid' }, { position: [.011, .019, 0], angle: 1.2, type: 'cut', feed: .01 },
    { position: [.012, .0185, 0], angle: 1.2, type: 'cut', feed: .01 }, { position: [.02, .0185, 0], angle: 1.2, type: 'cut' },
    { position: [.02, .0185, 0], angle: -2, type: 'index' }, { position: [.02, .0185, .004], angle: -2, type: 'rapid' },
    { position: [.03, .02, .004], angle: -2, type: 'cut' }],
};
const handDump = {};
for (const [name, moves] of Object.entries(handPaths)) {
  const p = new RP.RotaryPath(moves, name === 'wiggle' ? { feed: .02, rapid: .1, acceleration: .5, rotationSpeed: 1.1 } : {});
  const samples = [];
  for (let i = 0; i <= 40; i++) samples.push(p.sample(p.duration * i / 37));
  handDump[name] = { moves, segments: segs(p), duration: p.duration, samples };
}
const pathErrors = [
  [[{ position: [0, 0, 0], angle: 0, type: 'rapid' }, { position: [.01, 0, 0], angle: .5, type: 'index' }]],
  [[{ position: [0, 0, 0], angle: 0, type: 'rapid' }, { position: [0, 0, 0], angle: .5, type: 'cut' }]],
  [[{ position: [0, 0, 0], angle: 0, type: 'rapid' }, { position: [.01, 0, .01], angle: 0, type: 'cut' }]],
  [[{ position: [0, 0, 0], angle: 0, type: 'rapid' }, { position: [.01, 0, 0], angle: 0, type: 'plunge' }]],
  [[{ position: [0, 0, 0], angle: 0, type: 'rapid' }, { position: [0, 0, 0], angle: 0, type: 'rapid' }]],
  [[{ position: [0, 0, 0], angle: 0, type: 'rapid' }, { position: [NaN, 0, 0], angle: 0, type: 'rapid' }]],
  [[{ position: [0, 0, 0], angle: 0, type: 'rapid' }, { position: [.01, 0, 0], angle: 0, type: 'rapid' }], { rapid: -1 }],
].map(([m, o]) => { try { new RP.RotaryPath(m, o); return { e: null }; } catch (e) { return { e: e.message }; } });
const sweeps = [];
for (let n = 0; n < 1500; n++) {
  const a0 = rand() * 7 - 3.5, lat = rand() < .5 ? 0 : (rand() - .5) * .01;
  const s = { a: [(rand() - .5) * .03, .005 + rand() * .02, lat], b: null, a0 };
  s.b = rand() < .3 ? [s.a[0], s.a[1] + (rand() - .5) * .01, lat] : [s.a[0] + (rand() - .5) * .02, s.a[1] + (rand() - .5) * .01, lat];
  const p = [(rand() - .5) * .05, (rand() - .5) * .06, (rand() - .5) * .06];
  const f = [1, .37, rand()][n % 3], tool = n % 2 ? 'flat' : 'ball', R0 = [.003, .0015, .0025][n % 3], fl = [.017, .018, .012][n % 3];
  sweeps.push({ p, s, R: R0, fl, f, tool, d: RP.sweepDistance(p, s, R0, fl, f, tool) });
}
await write('paths', { handPaths: handDump, errors: pathErrors, sweeps });

// ------------------------------------------------------------------ index, removal
const small = RP.rotaryProgram(RP.sampleRotary, { angles: 16, sampleStep: .004 });
const idx = RS.indexRotarySweeps(small.path, small.settings, { min: [-.07, -.027, -.027], max: [.07, .027, .027] }, [32, 16, 16], 0);
const idxB = RS.indexRotarySweeps(small.path, small.settings, { min: [-.072, -.02, -.02], max: [.072, .02, .02] }, [40, 16, 16], .002);
const removalSettings = { stockLength: .07, stockWidth: .036, stockHeight: .036, radius: .003, fluteLength: .017, axisX: 0, axisHeight: .097 };
const removals = {
  hand_once: RR.rotaryRemoval(new RP.RotaryPath(handPaths.removal_once), removalSettings, { resolution: [36, 20, 20] }),
  hand_twice: RR.rotaryRemoval(new RP.RotaryPath(handPaths.removal_twice), removalSettings, { resolution: [36, 20, 20] }),
  small_ball: RR.rotaryRemoval(small.path, small.settings, { resolution: [48, 16, 16] }),
};
const flatSmall = RP.rotaryProgram(RP.sampleRotary, { angles: 16, sampleStep: .004, tool: 'flat', fluteLength: .018 });
removals.small_flat = RR.rotaryRemoval(flatSmall.path, flatSmall.settings, { resolution: [40, 14, 18] });
await write('index_removal', {
  index: { dims: idx.dims, cell: idx.cell, maxBin: idx.maxBin, counts: idx.bins.map((b) => b.length), records: idx.records.length, headers: idx.headers.length, links: idx.links.length,
    first: idx.bins.findIndex((b) => b.length), sample: idx.bins.map((b, i) => [i, b]).filter(([i, b]) => b.length).slice(0, 40) },
  indexB: { dims: idxB.dims, cell: idxB.cell, maxBin: idxB.maxBin, counts: idxB.bins.map((b) => b.length) },
  removals: Object.fromEntries(Object.entries(removals).map(([k, r]) => [k, { ...r }])),
  removalSettings,
});

// ------------------------------------------------------------------ mesh programs (the test geometry and a fitted knot)
const group = new T.Group(), body = new T.Mesh(new T.CylinderGeometry(.011, .011, .060, 28, 1));
body.rotation.z = Math.PI / 2; group.add(body);
const ridge = new T.Mesh(new T.BoxGeometry(.045, .002, .00008)); ridge.position.set(.002, .012, .0031); group.add(ridge);
const o1 = { fit: false, angles: 4, gridStep: .00065, sampleStep: .003, stepover: .0035, stepdown: .006 };
const meshDump = {};
const tri = (g) => Array.from(g.getAttribute('position').array);
let g1 = SG.sourceGeometry(group);
meshDump.group = { triangles: tri(g1), o: o1, program: RP.rotaryProgram(group, o1) };
ridge.position.z = -.005;
let g2 = SG.sourceGeometry(group);
meshDump.group_moved = { triangles: tri(g2), o: o1, program: RP.rotaryProgram(group, o1) };
const flatBox = new T.BoxGeometry(.060, .003, .005);
const o2 = { fit: false, angles: 4, gridStep: .001, sampleStep: .005, stepover: .004, stepdown: .008 };
meshDump.flat_box = { triangles: tri(SG.sourceGeometry(flatBox)), o: o2, program: RP.rotaryProgram(flatBox, o2) };
const knot = new T.TorusKnotGeometry(1, .3, 48, 8);
const o3 = { angles: 6, gridStep: .0008, sampleStep: .002, stepover: .003, tool: 'ball', fluteLength: .017 };
meshDump.knot_fit = { triangles: tri(SG.sourceGeometry(knot)), o: o3, program: RP.rotaryProgram(knot, o3) };
const env = RM.meshEnvelope(g1, .7, { minX: -.04, maxX: .04, minZ: -.03, maxZ: .03, step: .001 });
meshDump.envelope = { angle: .7, opts: { minX: -.04, maxX: .04, minZ: -.03, maxZ: .03, step: .001 }, nx: env.nx, nz: env.nz, dx: env.dx, dz: env.dz,
  heights: Array.from(env.heights, (v) => (Number.isFinite(v) ? v : null)) };
for (const k of ['group', 'group_moved', 'flat_box', 'knot_fit']) {
  const p = meshDump[k].program;
  meshDump[k].program = { moves: p.moves, stages: p.stages, report: p.report, settings: p.settings, duration: p.path.duration, nsegs: p.path.segments.length };
}
await write('mesh', meshDump);

// ------------------------------------------------------------------ the examples' own programs (summaries)
if (full) {
  const ex = {};
  for (const [name, mat] of [['rotary', 'wood'], ['rotary_metal', 'aluminum']]) {
    const s = SU.rotaryFixtureSetup({});
    const p = RP.rotaryProgram(RP.sampleRotary, { material: mat, tool: 'flat', fluteLength: .018, ...(name === 'rotary' ? { duration: 28 } : {}) });
    const rem = RR.rotaryRemoval(p.path, p.settings, {});
    ex[name] = { setup: s, settings: p.settings, stages: p.stages, moves: p.moves.length, segments: p.path.segments.length, duration: p.path.duration,
      cuts: p.path.segments.filter((x) => x.type === 'cut').length, removedVolume: rem.removedVolume, events: rem.events.length, queries: rem.queries,
      cuttingStart: rem.events[0].time, firstEvents: rem.events.slice(0, 20), lastEvents: rem.events.slice(-5),
      samples: [0, 10, 100, 600, p.path.duration * .5, p.path.duration].map((t) => p.path.sample(t)) };
  }
  await write('examples', ex);
}
