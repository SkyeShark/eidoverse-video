// fab_parity_dump.mjs: runs the WebGPU edition's fabrication planners (untouched) headless in Deno and dumps what
// they compute for fixed inputs: FeedPath / FilamentPath timing, swept cutter heights, the pocket program, stock
// removal, the relief program, meshSlicer sections and sliceGeometry toolpaths. test_fabrication_parity.py replays the
// same calls in the Blender port and compares number for number (three's (x, y, z) is Blender's (x, -z, y)).
//   cd <worktree> && deno run --no-config --no-lock -A --import-map=<imap.json> blender/tests/fabrication/fab_parity_dump.mjs
// (the import map points "three/webgpu" and "three/tsl" at a node_modules/three/build folder; the test writes it)
const root = new URL('../../../eidoverse/robotics/', import.meta.url);
const T = await import('three/webgpu');
const F = await import(new URL('fabrication.js', root));
const { FeedPath } = await import(new URL('feed_path.js', root));
const { FilamentPath } = await import(new URL('filament_path.js', root));
const { sweptCutterHeight, indexCutterSweeps } = await import(new URL('cutter_sweep.js', root));
const { sampleRemoval, stockProfile, distanceTime } = await import(new URL('cutting.js', root));
const { meshSlicer } = await import(new URL('mesh_slices.js', root));
const { sourceGeometry, fitSourceGeometry } = await import(new URL('source_geometry.js', root));
const { manufacturingSample } = await import(new URL('manufacturing_samples.js', root));
const out = {};

// FeedPath with blended corners, a plunge, an arc-free cut and a rapid
const pts = [
  { position: [0, .03, 0], type: 'rapid' }, { position: [.01, .03, -.01], type: 'rapid' },
  { position: [.01, .018, -.01], type: 'cut', feed: .001 }, { position: [.03, .018, -.01], type: 'cut' },
  { position: [.03, .018, .02], type: 'cut' }, { position: [.0, .018, .025], type: 'cut' },
  { position: [0, .03, .025], type: 'rapid' }, { position: [.02, .002, .0], type: 'extrude' },
  { position: [.04, .002, .0], type: 'extrude' }, { position: [.04, .002, .02], type: 'extrude' },
  { position: [.02, .002, .03], type: 'extrude' },
];
for (const [name, opts] of [['blend', { feed: .012, rapid: .1, acceleration: .3, blendTolerance: .000025, beadArea: 2e-7 }],
                            ['sharp', { feed: .02, rapid: .08, acceleration: .25, blendTolerance: 0 }]]) {
  const p = new FeedPath(pts, opts);
  const samples = [];
  for (let i = 0; i <= 40; i++) {
    const s = p.sample(p.duration * i / 40);
    samples.push({ t: s.time, position: s.position, tangent: s.tangent, speed: s.speed, distance: s.distance,
                   volume: s.volume, type: s.type, index: s.index, acceleration: s.acceleration });
  }
  const walked = [];
  p.walk(p.duration * .2, p.duration * .5, .004, (a, b, type) => walked.push([a.time, b.time, type]));
  out['feed_' + name] = { duration: p.duration, length: p.length, volume: p.volume, segments: p.segments.length,
    kinds: p.segments.map(s => s.kind), samples, walked: walked.length,
    distance_time: p.segments.filter(s => s.kind === 'line').slice(0, 6).map(s => [0, .25, .5, 1].map(f => distanceTime(s, s.length * f))) };
}
// FilamentPath
{
  const p = new FeedPath(pts, { feed: .025, rapid: .1, acceleration: .5, blendTolerance: .000015, beadArea: Math.PI * .0008 * .0004 / 4 });
  const f = new FilamentPath(p, {});
  const samples = [];
  for (let i = 0; i <= 60; i++) {
    const s = f.sample(f.duration * i / 60);
    samples.push({ t: s.time, type: s.type, position: s.position, filamentLength: s.filamentLength,
                   filamentRetraction: s.filamentRetraction, filamentSpeed: s.filamentSpeed, speed: s.speed });
  }
  out.filament = { duration: f.duration, retractionTime: f.retractionTime, filamentLength: f.filamentLength,
                   spans: f.spans.map(s => [s.type, s.t0, s.t1]), samples };
}
// swept cutter heights
{
  const cases = [];
  for (const kind of ['flat', 'ball']) for (const dy of [-.014, 0, .017]) {
    const a = [-.012, .017, 0], b = [.014, .017 + dy, .005], r = .003;
    for (const [x, z] of [[-.012, 0], [.001, .004], [.014, .005], [.006, -.012], [.0, .0021], [-.013, .001]]) {
      const h = sweptCutterHeight(x, z, a, b, r, kind);
      cases.push([kind, x, z, a, b, r, Number.isFinite(h) ? h : null]);
    }
  }
  cases.push(['ball', .001, 0, [0, .014, 0], [0, .009, 0], .003, sweptCutterHeight(.001, 0, [0, .014, 0], [0, .009, 0], .003, 'ball')]);
  out.swept = cases;
}
// pocket program and removal (aluminum defaults as mill() passes them)
{
  const profile = stockProfile('aluminum');
  const points = F.pocketProgram({ feed: profile.feed, plunge: profile.plunge, stepdown: profile.stepdown,
                                   cutDepth: profile.cutDepth, stockHeight: .020, radius: .003 });
  out.pocket = points;
  out.pocket_default = F.pocketProgram();
  const path = new FeedPath(points, { feed: profile.feed, rapid: .08, acceleration: .25, blendTolerance: 0 });
  const removal = sampleRemoval(path, { width: .078, depth: .128, height: .020, radius: .003, resolution: 128, fluteLength: .018, cutter: 'flat' });
  out.removal = { removedVolume: removal.removedVolume, events: removal.events.length,
                  first: removal.events.slice(0, 5), last: removal.events.slice(-3),
                  engaged: removal.intervals.filter(i => i.engaged).length, duration: path.duration,
                  heights_sum: Array.from(removal.finalHeights).reduce((a, b) => a + b, 0),
                  heights_min: Math.min(...removal.finalHeights) };
  const cuts = []; // chords as mill() makes them
  for (const s of path.segments) if (s.type === 'cut') cuts.push({ a: new T.Vector3(...s.a), b: new T.Vector3(...s.b) });
  const bins = indexCutterSweeps(cuts, .078, .128, .003);
  out.bins = { maximumBin: bins.maximumBin, total: bins.indices.length, cuts: cuts.length };
}
// relief program (the original sample, the carve defaults for wood)
{
  const prof = stockProfile('wood');
  const prog = F.reliefProgram(F.sampleRelief, { feed: prof.feed, plunge: prof.plunge, stepdown: prof.stepdown, fluteLength: .017 });
  out.relief = { points: prog.points.length, stages: prog.stages, first: prog.points.slice(0, 8), last: prog.points.slice(-4),
                 sum: prog.points.reduce((s, p) => [s[0] + p.position[0], s[1] + p.position[1], s[2] + p.position[2]], [0, 0, 0]),
                 mid: prog.points.slice(5000, 5006) };
  const fine = F.reliefProgram(F.sampleRelief, { feed: prof.feed, plunge: prof.plunge, stepdown: prof.stepdown, sampleStep: .002, stepover: .0015 });
  out.relief_coarse = { points: fine.points.length, stages: fine.stages.map(s => [s.name, s.endIndex, s.endDistance]) };
  const slope = F.reliefProgram((x) => .012 + .42 * x, { stockWidth: .036, stockDepth: .034, width: .024, depth: .020, stockHeight: .025, radius: .003, sampleStep: .0015, stepover: .001 });
  out.relief_slope = { points: slope.points.length, stages: slope.stages, sample: slope.points.slice(100, 110) };
  out.sample_relief = [[0, 0], [.01, .02], [-.02, -.03], [.013, -.019]].map(([x, z]) => F.sampleRelief(x, z));
}
// slicing
{
  const slices = {};
  const box = new T.BoxGeometry(1, 1, 1);
  const sleeve = new T.LatheGeometry([[.014, 0], [.020, 0], [.020, .006], [.014, .006], [.014, 0]].map(p => new T.Vector2(...p)), 48);
  const handle = manufacturingSample('handle');
  const bracket = manufacturingSample('bracket');
  const ring = manufacturingSample('ring');
  const specs = {
    box: [box, { size: .008, infill: .3 }],
    sleeve: [sleeve, { size: .04, infill: .25 }],
    handle: [handle, { size: .04 }],
    bracket: [bracket, { size: .04 }],
    ring: [ring, { size: .04, layerHeight: .0008 }],
  };
  for (const [name, [src, opts]] of Object.entries(specs)) {
    const s = F.sliceGeometry(src, opts);
    const perLayer = {};
    let extrude = 0, rapid = 0;
    for (let i = 1; i < s.points.length; i++) {
      const a = s.points[i - 1].position, b = s.points[i].position, l = Math.hypot(b[0] - a[0], b[1] - a[1], b[2] - a[2]);
      if (s.points[i].type === 'extrude') { extrude += l; const k = b[1].toFixed(6); perLayer[k] = (perLayer[k] ?? 0) + l; }
      else rapid += l;
    }
    const contourLength = s.contours.map(c => { let l = 0; for (let i = 1; i < c.points.length; i++) l += Math.hypot(...c.points[i].map((v, k) => v - c.points[i - 1][k])); return l; });
    slices[name] = { layers: s.layers, points: s.points.length, extrude, rapid, perLayer, contours: s.contours.length,
                     contourLength, extrudes: s.points.filter(p => p.type === 'extrude').length };
    if (name === 'sleeve' || name === 'box') {
      const geometric = new FeedPath(s.points, { feed: .025, rapid: .10, acceleration: .5, beadArea: Math.PI * .0008 * .0004 / 4, blendTolerance: .000015 });
      const fp = new FilamentPath(geometric, {});
      slices[name].duration = fp.duration;
      slices[name].volume = fp.volume;
      slices[name].filamentLength = fp.filamentLength;
    }
  }
  out.slices = slices;
  // meshSlicer sections
  const g = sourceGeometry(handle);
  const fit = fitSourceGeometry(handle, { size: .04, base: .00065 });
  out.handle_fit = fit.userData.manufacturingSource.fit;
  out.handle_bbox = [g.boundingBox.min.toArray(), g.boundingBox.max.toArray()];
  const area = r => Math.abs(r.slice(1).reduce((s, p, i) => s + r[i][0] * p[1] - p[0] * r[i][1], 0) / 2);
  const cut = meshSlicer(fit, { polygons: true });
  out.handle_sections = [.002, .006, .01, .014, .02].map(y => cut(y).map(poly => poly.map(r => [r.length, area(r)])));
}
console.log(JSON.stringify(out));
