import * as T from "three/webgpu";
import {
  rotaryBlankDistance,
  RotaryPath,
  rotaryProgram,
  sampleRotary,
  sweepDistance,
} from "../rotary_path.js";
import { indexRotarySweeps } from "../rotary_stock.js";
import { rotaryRemoval } from "../rotary_removal.js";
import { loadRobot } from "../index.js";
import { rotaryCarve } from "../rotary.js";
const assert = (v, m = "Assertion failed") => {
  if (!v) throw Error(m);
};
const near = (a, b, e = 1e-9) =>
  assert(Math.abs(a - b) < e, `${a} versus ${b}`);
const rejects = (fn, re) => {
  let error;
  try {
    fn();
  } catch (e) {
    error = e;
  }
  assert(error && re.test(error.message), "Expected " + re);
};

Deno.test("adjustable rectangular blanks retain jaw contact and enough gantry retraction", async () => {
  const robot = await loadRobot("cnc_rotary", {textures:false});
  for (const [L,W,H] of [[.08,.018,.026],[.18,.044,.050]]) {
    const options = {stockLength:L,stockWidth:W,stockHeight:H};
    robot.rotarySetup(options);
    robot.setJoints({rotary_output:.51});robot.group.updateMatrixWorld(true);
    for (let j=0;j<4;j++) {
      const axis = new T.Vector3(0,Math.cos(j*Math.PI/2),Math.sin(j*Math.PI/2));
      const origin = new T.Vector3(-.063,0,0).addScaledVector(axis,(j%2?W:H)/2-.001);
      const chuck=robot.roots.rotary_chuck;
      const ray=new T.Raycaster(chuck.localToWorld(origin),axis.transformDirection(chuck.matrixWorld));
      const hit=ray.intersectObjects(robot.part("RC independent jaw "+j),false)[0];
      assert(hit,"Jaw lost contact with rectangular stock");near(hit.distance,.001,2e-6);
    }
    const program=rotaryProgram(undefined,{...options,angles:16,sampleStep:.005});
    for (const move of program.moves) {
      const p=[move.position[0]+program.settings.axisX,move.position[1]+program.settings.axisHeight,move.position[2]];
      robot.moveTool(p);
      assert(robot.toolTip().distanceTo(new T.Vector3(...p))<3e-7);
    }
  }
  robot.dispose();
});

Deno.test("prepared rotary blank seats a 60-degree live centre with pilot relief", () => {
  const s = { stockLength: .140, stockHeight: .036, stockWidth: .036 };
  assert(
    rotaryBlankDistance([0, 0, 0], s) < 0,
    "Interior stock must remain solid",
  );
  assert(
    rotaryBlankDistance([.065, 0, 0], s) > 0,
    "Pilot must clear the centre point",
  );
  assert(
    rotaryBlankDistance([.063, 0, 0], s) < 0,
    "Pilot must have a closed floor",
  );
  assert(
    rotaryBlankDistance([-.069, 0, 0], s) < 0,
    "Chuck end must remain solid",
  );
  for (const a of [0, .39, 1.8, 4.7]) {
    const x = .069, r = (x - .067) * Math.tan(Math.PI / 6);
    const p = [x, r * Math.cos(a), r * Math.sin(a)];
    near(rotaryBlankDistance(p, s), 0, 1e-10);
    assert(rotaryBlankDistance([x, p[1] * .95, p[2] * .95], s) > 0);
    assert(rotaryBlankDistance([x, p[1] * 1.05, p[2] * 1.05], s) < 0);
  }
});

Deno.test("metal rotary presets alter actual cutting time and depth stages", () => {
  const opts = { angles: 16, sampleStep: .004 };
  const wood = rotaryProgram(sampleRotary, { ...opts, material: "wood" });
  const aluminum = rotaryProgram(sampleRotary, {
    ...opts,
    material: "aluminum",
  });
  const brass = rotaryProgram(sampleRotary, { ...opts, material: "brass" });
  for (const p of [aluminum, brass]) {
    assert(p.settings.feed < wood.settings.feed);
    assert(p.settings.stepdown < wood.settings.stepdown);
    assert(p.stages.length > wood.stages.length);
    assert(p.path.duration > wood.path.duration);
    for (const seg of p.path.segments.filter((s) => s.type === "cut")) {
      assert(seg.feed <= p.settings.feed);
    }
  }
});

Deno.test("indexed carving retracts beyond all stock corners and keeps XYZ stationary while rotating", () => {
  const p = rotaryProgram(sampleRotary, {
      angles: 32,
      sampleStep: .002,
      stepdown: .006,
    }),
    s = p.settings;
  assert(p.stages.length > 1 && p.stages.at(-1).name === "finish");
  let indexes = 0, cuts = 0;
  for (const seg of p.path.segments) {
    for (const f of [0, .23, .67, 1]) {
      const q = p.path.sample(seg.t0 + (seg.t1 - seg.t0) * f);
      assert(q.position.every(Number.isFinite) && Number.isFinite(q.speed));
      if (seg.type === "index") {
        indexes++;
        near(new T.Vector3(...seg.a).distanceTo(new T.Vector3(...seg.b)), 0);
        assert(
          q.position[1] >
            Math.hypot(s.stockHeight / 2, s.stockWidth / 2) + .002,
        );
      } else {
        if (seg.type === "cut") cuts++;
        assert(q.speed <= seg.feed + 1e-8 && q.speed >= 0);
        near(q.angle, seg.a0);
      }
    }
  }
  assert(indexes > 32 && cuts > 100);
  const q = p.path.sample(p.path.duration * .173);
  p.path.sample(p.path.duration);
  const back = p.path.sample(p.path.duration * .173);
  assert(JSON.stringify(q) === JSON.stringify(back));
  rejects(() => p.path.sample(NaN), /finite/);
  rejects(() => rotaryProgram(sampleRotary, { stepdown: Infinity }), /finite/);
  rejects(
    () => rotaryProgram(() => .003, { angles: 16, sampleStep: .004 }),
    /cutting length/,
  );
});

Deno.test("swept cutter agrees with dense independent moving capsule samples", () => {
  for (const angle of [0, .73, 2.1]) {
    for (const slope of [-.45, 0, .6]) {
      const s = {
        a: [-.008, .012, 0],
        b: [.011, .012 + slope * .019, 0],
        a0: angle,
      };
      for (
        const point of [[.002, .014, .001], [-.01, .012, .002], [
          .010,
          .023,
          -.004,
        ]]
      ) {
        for (const fraction of [.17, .6, 1]) {
          const c = Math.cos(angle),
            sn = Math.sin(angle),
            p = [
              point[0],
              point[1] * c - point[2] * sn,
              point[1] * sn + point[2] * c,
            ];
          let expected = Infinity;
          for (let i = 0; i <= 16000; i++) {
            const f = fraction * i / 16000,
              x = s.a[0] + (s.b[0] - s.a[0]) * f,
              y = s.a[1] + (s.b[1] - s.a[1]) * f;
            const cy = T.MathUtils.clamp(p[1], y + .003, y + .017);
            expected = Math.min(
              expected,
              Math.hypot(p[0] - x, p[1] - cy, p[2]) - .003,
            );
          }
          near(sweepDistance(point, s, .003, .017, fraction), expected, 1.3e-6);
        }
      }
    }
  }
});

Deno.test("sample sculpture remains inside the uncut side of every swept tool surface", () => {
  const p = rotaryProgram(sampleRotary, {
      angles: 48,
      sampleStep: .0015,
      stepdown: .006,
    }),
    s = p.settings;
  const bounds = { min: [-.07, -.027, -.027], max: [.07, .027, .027] },
    index = indexRotarySweeps(p.path, s, bounds, [32, 16, 16], 0);
  let worst = Infinity;
  for (let i = 0; i <= 101; i++) {
    for (let j = 0; j < 137; j++) {
      const x = s.start + (s.end - s.start) * i / 101,
        a = j * Math.PI * 2 / 137,
        r = sampleRotary(x, a),
        q = [x, r * Math.cos(a), r * Math.sin(a)];
      const b = q.map((v, k) =>
        Math.floor((v - bounds.min[k]) / index.cell[k])
      );
      for (const id of index.bins[b[0] + 32 * (b[1] + 16 * b[2])]) {
        worst = Math.min(
          worst,
          sweepDistance(q, p.path.segments[id], s.radius),
        );
      }
    }
  }
  assert(worst >= -1e-7, "Sample target gouged by " + (-worst) + " m");
});

Deno.test("removal emits only first engagement; air travel and repeated cuts add no stock volume", () => {
  const mk = (repeat) =>
    new RotaryPath([
      { position: [-.025, .014, 0], angle: 0, type: "rapid" },
      { position: [.025, .014, 0], angle: 0, type: "cut" },
      ...(repeat
        ? [{ position: [-.025, .014, 0], angle: 0, type: "cut" }, {
          position: [.025, .014, 0],
          angle: 0,
          type: "cut",
        }]
        : []),
      { position: [.025, .04, 0], angle: 0, type: "rapid" },
      { position: [-.025, .04, 0], angle: 0, type: "cut" },
    ]);
  const settings = {
    stockLength: .07,
    stockWidth: .036,
    stockHeight: .036,
    radius: .003,
    fluteLength: .017,
    axisX: 0,
    axisHeight: .097,
  };
  const a = rotaryRemoval(mk(false), settings, { resolution: [36, 20, 20] }),
    b = rotaryRemoval(mk(true), settings, { resolution: [36, 20, 20] });
  assert(a.removedVolume > 0 && a.events.length > 0);
  near(a.removedVolume, b.removedVolume, 1e-14);
  assert(
    a.events.every((e) =>
      e.time <= mk(false).segments[0].t1 && e.position[1] > .110
    ),
  );
  near(a.events.reduce((v, e) => v + e.volume, 0), a.removedVolume, 1e-13);
});

Deno.test("rotary fixture is a separate shared assembly and invalid jobs do not leave a stock object", async () => {
  const fixture = await loadRobot("rotary_fixture", { textures: false });
  fixture.sample("joints", 2);
  near(fixture.state.rotary_output, fixture.state.rotary_chuck, 1e-12);
  fixture.setJoints({ rotary_output: 1.2 });
  near(fixture.state.rotary_chuck, 1.2, 1e-12);
  rejects(
    () => fixture.setJoints({ rotary_output: .1, rotary_chuck: .5 }),
    /same A-axis/,
  );
  near(fixture.state.rotary_output, 1.2, 1e-12);
  fixture.dispose();
  const r = await loadRobot("cnc_rotary", { textures: false }),
    before = r.roots.gantry_base.children.length;
  assert(
    r.machine.cutter.kind === "flat" && r.roots.rotary_chuck &&
      r.roots.rotary_output,
  );
  assert(!Object.keys(r.roots).some((n) => n.startsWith("cnc_toe_clamp")));
  for (
    const options of [{ duration: 0 }, { axisX: .04 }, { start: -.060 }, {}]
  ) {
    rejects(() =>
      rotaryCarve(r, sampleRotary, {
        angles: 16,
        sampleStep: .004,
        stepdown: .006,
        ...options,
      }), /duration|calibrated|renderer/);
  }
  assert(r.roots.gantry_base.children.length === before);
  r.dispose();
});
