// js_parity_dump.mjs: runs the WebGPU edition's modular robotics kit (eidoverse/robotics/, untouched) headless in Deno
// and dumps what the Blender port must reproduce, for test_js_parity.py to compare:
//   per catalog model: its roots, joint state after loading, default joints, clips, parts, stats, ports (owner node,
//   interface, matrix), machine data, and the world matrix of every glTF node (and every split track shoe) after
//   robot.sample(clip, t) for each of its clips at two times;
//   the pure solvers: scara.forward / inverse / demo, SerialArm forward / inverse, articulatedDemo, gantryDemo,
//   constrainGantryPose, graspValues, rotaryFixtureSetup; loadPart triangle counts; frameCamera.
// Nothing renders (textures: false, no GPU).
//   cd C:/Users/sdn52/OneDrive/Desktop/eidoverse-video-prealpha-0.01   (its deno.json + node_modules resolve three)
//   deno run --no-check --allow-read --allow-write --allow-env --node-modules-dir=manual --no-lock --config deno.json \
//       C:/Users/sdn52/OneDrive/Desktop/eidoverse-video-blender/blender/tests/robotics/js_parity_dump.mjs [model ids]
const here = new URL('.', import.meta.url);
const repo = new URL('../../../', here);
const outDir = new URL('out/js_parity/', here);
await Deno.mkdir(outDir, { recursive: true });
const api = await import(new URL('eidoverse/robotics/index.js', repo).href);
const scara = await import(new URL('eidoverse/robotics/scara.js', repo).href);
const sa = await import(new URL('eidoverse/robotics/serial_arm.js', repo).href);
const { graspValues } = await import(new URL('eidoverse/robotics/grasp.js', repo).href);
const { rotaryFixtureSetup } = await import(new URL('eidoverse/robotics/rotary_setup.js', repo).href);
const studio = await import(new URL('eidoverse/robotics/studio.js', repo).href);
const T = await import('three/webgpu');

const r6 = (v) => Math.round(v * 1e6) / 1e6;
const mat = (m) => Array.from(m.elements, r6);
const safe = (id) => id.replace(/[\/\\]/g, '__');
const only = Deno.args;
const TIMES = [1.25, 5.5];

function nodeTable(robot) {
  // glTF node index of every object the loader kept (clones carry the association), plus split track shoes
  const assoc = robot.gltf.parser.associations, index = new Map(), nodes = [];
  robot.model.traverse((o) => {
    const a = assoc.get(o);
    if (a?.nodes !== undefined) index.set(o, a.nodes);
  });
  robot.model.traverse((o) => {
    if (index.has(o)) nodes.push({ key: 'n' + index.get(o), name: o.userData.name ?? o.name, parent: index.has(o.parent) ? 'n' + index.get(o.parent) : null, o });
    else if (o.isMesh && index.has(o.parent) && o.parent.isMesh && o.userData.part_ids?.length === 1 && robot.trackBindings?.some((b) => b.ob === o)) {
      nodes.push({ key: 'shoe:' + o.name + '@n' + index.get(o.parent), name: o.name, parent: 'n' + index.get(o.parent), o });
    }
  });
  return { nodes, index };
}

function worlds(robot, table) {
  robot.group.updateMatrixWorld(true);
  const out = {};
  for (const n of table.nodes) out[n.key] = mat(n.o.matrixWorld);
  return out;
}

const cat = await api.catalog();
const summary = { models: {}, solvers: {} };
for (const id of Object.keys(cat.models)) {
  if (only.length && !only.includes(id)) continue;
  const t0 = performance.now();
  const robot = await api.loadRobot(id, { textures: false });
  const table = nodeTable(robot);
  const rec = {
    id, clips: robot.clips, parts: [...robot.parts()].sort(), stats: robot.stats(),
    roots: Object.fromEntries(Object.entries(robot.roots).map(([n, o]) => ['' + n, table.index.has(o) ? 'n' + table.index.get(o) : null])),
    state: { ...robot.state }, defaultJoints: robot.defaultJoints ?? null,
    ports: Object.fromEntries(Object.entries(robot.ports).map(([n, p]) => [n, {
      interface: p.interface, owner: table.index.has(p.owner) ? 'n' + table.index.get(p.owner) : null, matrix: mat(p.matrix),
      derived: !!p.provenance,
    }])),
    nodes: table.nodes.map((n) => [n.key, n.name, n.parent]),
    rest: worlds(robot, table),
    samples: {},
  };
  if (robot.machine) {
    rec.machine = { ...robot.machine, toAxes: undefined };
    if (robot.moveTool) {
      const tests = [];
      for (const p of [[0.02, 0.03, -0.01], [-0.05, 0.06, 0.04]]) {
        try {
          robot.reset();
          robot.moveTool(p);
          const tip = robot.toolTip(), w = robot.toolTip(true);
          tests.push({ p, axes: robot.machine.toAxes(p), tip: tip.toArray().map(r6), world: w.toArray().map(r6) });
        } catch (e) {
          tests.push({ p, error: e.message });
        }
      }
      rec.moveTool = tests;
    }
  }
  for (const clip of robot.clips) {
    rec.samples[clip] = {};
    for (const t of TIMES) {
      try {
        // three's PropertyMixer writes a node only when its value changed since the mixer's LAST update, but
        // sample() resets the nodes between updates: a walk channel equal at two sampled times stays at rest the
        // second time. Rebinding the mixer before each walk sample gives the pose the clip actually holds.
        if (clip === 'walk') robot.mixer.uncacheRoot(robot.model);
        robot.sample(clip, t);
        rec.samples[clip][t] = { worlds: worlds(robot, table), state: { ...robot.state } };
      } catch (e) {
        rec.samples[clip][t] = { error: e.message };
      }
    }
  }
  robot.reset();
  if (id === 'humanoid/humanoid_receiver_study' || id === 'quadruped/quadruped_receiver_study') {
    // the running controller's own frame() and bounds()
    const fam = cat.models[id].family;
    const data = JSON.parse(await Deno.readTextFile(new URL('eidoverse/assets/robotics/metadata/' + fam + '_running.json', repo)));
    rec.running = Object.fromEntries(Object.keys(data.clips).map((c) => [c, data.clips[c].duration]));
  }
  if (robot.ik) {
    const cases = [[0, 0, 0, 0, 0, 0], [0.2, 0.4, -0.6, 0.25, 0.6, -0.2], [-0.4, 0.6, 0.3, -0.2, 0.7, 0.5]];
    rec.ik = cases.map((q) => {
      const f = robot.ik.forward(q, true);
      const target = f.transform;
      const inv = robot.ik.inverse(target, [0, 0.3, -0.5, 0, 0.3, 0]);
      return { q, forward: f.transform, jacobian: f.jacobian, inverse: inv };
    });
  }
  await Deno.writeTextFile(new URL(safe(id) + '.json', outDir), JSON.stringify(rec));
  summary.models[id] = { clips: robot.clips, seconds: Math.round(performance.now() - t0) / 1000 };
  console.log(id, robot.clips.join(','), Math.round(performance.now() - t0), 'ms');
  robot.dispose();
}

// ------------------------------------------------------------------------------------------------ pure solvers
const S = summary.solvers;
S.scara_forward = [[0, 0, 0, 0], [0.2, 0.8, 0.04, -0.4], [-0.4, 0.5, 0.08, 0.6]].map((q) => ({ q, tcp0: scara.forward(q), tcp: scara.forward(q, scara.gripTCP) }));
S.scara_inverse = [[0.3, 0.1, 0.2, 0], [0.32, -0.12, 0.11, 0.7], [0.1, 0.4, 0.3, -1.2], [0.6, 0, 0.2, 0], [0.25, 0.05, 0.08, 0.3]].map(([x, y, z, yaw]) => ({
  args: [x, y, z, yaw], plain: scara.inverse(x, y, z, yaw), tcp: scara.inverse(x, y, z, yaw, scara.gripTCP, [0.1, 0.5, 0.05, 0]),
  minZ: scara.inverse(x, y, z, yaw, scara.gripTCP, null, 0.055),
}));
S.scara_demo = [0, 0.13, 0.5, 0.77].map((t) => ({ t, q: scara.demo(t) }));
S.scara_limits = scara.limits;
S.scara_gripTCP = scara.gripTCP;
S.articulatedDemo = [0, 0.2, 0.61].map((t) => ({ t, q: sa.articulatedDemo(t) }));
S.gantryDemo = [];
for (const t of [0, 0.3, 0.8]) for (const [tool, z] of [['bare', null], ['extruder', null], ['spindle', null], ['spindle', 0.11]]) {
  S.gantryDemo.push({ t, tool, tipRestZ: z, xyz: sa.gantryDemo(t, tool, z) });
}
const mf = JSON.parse(await Deno.readTextFile(new URL('eidoverse/assets/robotics/metadata/manufacturing.json', repo)));
S.constrainGantryPose = [[0.5, -0.5, 0.3], [0.01, 0.02, -0.03]].map((xyz) => ({ xyz,
  plain: sa.constrainGantryPose(mf, null, xyz), assembly: sa.constrainGantryPose(mf, { z_limits_m: [-0.02, 0.01] }, xyz) }));
const inter = JSON.parse(await Deno.readTextFile(new URL('eidoverse/assets/robotics/metadata/interaction.json', repo)));
S.graspValues = [0, 0.1, 0.35, 0.5, 0.8, 1].map((t) => ({ t, q: graspValues(inter.mobile.hand.grasp, t) }));
S.rotaryFixtureSetup = [{}, { stockLength: 0.1, stockWidth: 0.02, stockHeight: 0.045, quill: 0.003 }].map((o) => ({ o, r: rotaryFixtureSetup(o) }));
// loadPart: exact triangle ownership
S.loadPart = [];
for (const id of ['face', 'air/air', 'rotors_air_air/air_air_rotors']) {
  if (only.length) break;
  const donor = await api.loadRobot(id, { textures: false });
  const name = id === 'face' ? 'FACE swept tilt yoke' : donor.parts().find((n) => donor.part(n).some((o) => o.userData.part_ids?.length > 1));
  const part = await api.loadPart(id, name, { textures: false });
  S.loadPart.push({ id, name, triangles: part.stats().triangles, donor: donor.stats().triangles, parts: part.parts() });
  part.dispose();
  donor.dispose();
}
// frameCamera on a known box
const cam = new T.PerspectiveCamera(35, 16 / 9, 0.01, 100);
const target = studio.frameCamera(cam, [new T.Box3(new T.Vector3(-0.4, 0, -0.3), new T.Vector3(0.6, 1.2, 0.5))], { direction: [0.9, 0.55, 1.5], margin: 1.25 });
S.frameCamera = { target: target.toArray(), position: cam.position.toArray(), near: cam.near, far: cam.far, quaternion: cam.quaternion.toArray() };
if (!only.length) await Deno.writeTextFile(new URL('_summary.json', outDir), JSON.stringify(summary));
console.log('done');
