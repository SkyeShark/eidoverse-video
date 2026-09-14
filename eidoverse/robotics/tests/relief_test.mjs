import { indexCutterSweeps, sweptCutterHeight } from "../cutter_sweep.js";
import { reliefFromMesh, reliefProgram } from "../relief.js";
import * as T from "three/webgpu";
import { loadRobot } from "../index.js";
import { carve, mill, sampleRelief } from "../fabrication.js";
const assert = (x, m = "Assertion failed") => {
  if (!x) throw Error(m);
};
const near = (a, b, e) => assert(Math.abs(a - b) < e, `${a} versus ${b}`);
Deno.test("swept ball and flat cutters agree with independent dense moving-tool samples", () => {
  for (const kind of ["flat", "ball"]) {
    for (const dy of [-.014, 0, .017]) {
      const a = [-.012, .017, 0], b = [.014, .017 + dy, .005], r = .003;
      for (
        const [x, z] of [[-.012, 0], [.001, .004], [.014, .005], [.006, -.012]]
      ) {
        let minimum = Infinity;
        for (let i = 0; i <= 50000; i++) {
          const t = i / 50000,
            dx = x - a[0] - (b[0] - a[0]) * t,
            dz = z - a[2] - (b[2] - a[2]) * t,
            d2 = dx * dx + dz * dz;
          if (d2 <= r * r) {
            minimum = Math.min(
              minimum,
              a[1] + dy * t + (kind === "ball" ? r - Math.sqrt(r * r - d2) : 0),
            );
          }
        }
        const actual = sweptCutterHeight(x, z, a, b, r, kind);
        if (minimum === Infinity) assert(actual === Infinity);
        else {
          assert(actual <= minimum + 1e-10);
          near(actual, minimum, 4e-7);
        }
      }
    }
  }
  near(
    sweptCutterHeight(.001, 0, [0, .014, 0], [0, .009, 0], .003, "ball"),
    .012 - Math.sqrt(.000008),
    1e-12,
  );
});
Deno.test("ball compensation protects a sloping relief and roughing precedes finishing", () => {
  const slope = .42, r = .003;
  const p = reliefProgram((x) => .012 + slope * x, {
    stockWidth: .036,
    stockDepth: .034,
    width: .024,
    depth: .020,
    stockHeight: .025,
    radius: r,
    sampleStep: .0015,
    stepover: .001,
  });
  const finish = p.stages.at(-1);
  assert(finish.name === "finish" && p.stages.length > 1);
  for (
    const q of p.points.slice(finish.startIndex, finish.endIndex + 1).filter(
      (q) => q.type === "cut",
    )
  ) {
    const exact = .012 + slope * q.position[0] +
      r * (Math.sqrt(1 + slope * slope) - 1);
    assert(q.position[1] >= exact, "Compensation gouges a plane");
    near(q.position[1] - exact, p.surfaceTolerance, 2e-5);
  }
  for (const s of p.stages) assert(s.endDistance > s.startDistance);
});
Deno.test("spatial bins retain every candidate sweep including stock boundary cells", () => {
  const cuts = [{
    a: new T.Vector3(-.02, .02, -.02),
    b: new T.Vector3(.02, .01, .02),
  }];
  const { headers, indices, tiles } = indexCutterSweeps(cuts, .05, .05, .003);
  for (let zi = 0; zi <= 30; zi++) {
    for (let xi = 0; xi <= 30; xi++) {
      const x = (xi / 30 - .5) * .05, z = (zi / 30 - .5) * .05;
      if (
        sweptCutterHeight(
          x,
          z,
          cuts[0].a.toArray(),
          cuts[0].b.toArray(),
          .003,
          "ball",
        ) === Infinity
      ) continue;
      const bx = Math.min(tiles - 1, Math.floor((x / .05 + .5) * tiles)),
        bz = Math.min(tiles - 1, Math.floor((z / .05 + .5) * tiles));
      const start = headers[(bz * tiles + bx) * 4],
        count = headers[(bz * tiles + bx) * 4 + 1];
      assert(indices.slice(start, start + count).includes(0));
    }
  }
});
Deno.test("mesh relief samples the transformed top envelope without changing its material", () => {
  const g = new T.BoxGeometry(.010, .004, .010),
    mat = new T.MeshBasicMaterial(),
    m = new T.Mesh(g, mat);
  m.position.y = .010;
  const h = reliefFromMesh(m, {
    width: .024,
    depth: .024,
    stockHeight: .020,
    floor: .004,
    columns: 25,
    rows: 25,
  });
  near(h.heights[12 * 25 + 12], .012, 1e-8);
  near(h.heights[0], .004, 1e-8);
  assert(m.material === mat);
  g.dispose();
  mat.dispose();
});
Deno.test("assembled relief cutter follows XYZ stages, rewinds deterministically and retains shared fixtures", async () => {
  const robot = await loadRobot("cnc_relief", { textures: false });
  assert(robot.machine.cutter.kind === "ball");
  const job = carve(robot, sampleRelief, {
    material: "wood",
    duration: 18,
    resolution: 64,
    sampleStep: .002,
    stepover: .0015,
  });
  const g = job.mesh.geometry,
    version = g.attributes.position.version,
    vertices = g.attributes.position.array.slice();
  const states = [];
  for (const fraction of [0, .17, .62, .94, 1, .17]) {
    const state = job.seek(fraction * 18);
    states.push([...state.position, state.distance]);
    near(robot.toolTip().distanceTo(new T.Vector3(...state.position)), 0, 2e-7);
    assert(typeof state.stage === "string");
  }
  states[1].forEach((v, i) => near(v, states.at(-1)[i], 1e-8));
  assert(job.program.stages.at(-1).name === "finish");
  assert(job.removal.removedVolume > 0);
  assert(
    g.attributes.position.version === version &&
      vertices.every((v, i) => v === g.attributes.position.array[i]),
  );
  assert(
    job.workholding.length === 4 &&
      job.workholding.every((root) => root.visible),
  );
  let rejected = false;
  try {
    mill(robot, null, { fluteLength: .050 });
  } catch (e) {
    rejected = /exposed length/.test(e.message);
  }
  assert(rejected, "An option cannot enlarge the actual cutter");
  job.dispose();
  assert(
    Object.entries(robot.roots).filter(([n]) => n.startsWith("cnc_clamp_"))
      .every(([, r]) => r.parent === robot.roots.gantry_base && r.visible),
  );
  robot.dispose();
});
