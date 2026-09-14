import * as T from "three/webgpu";
import { catalog, loadPart, loadRobot } from "../index.js";
import { FeedPath, mill, print, stockMaterials } from "../fabrication.js";
import { bezierLength, createPTFETube } from "../filament.js";
import { sampleRemoval } from "../cutting.js";
import { frameCamera } from "../studio.js";
const assert = (v, m = "Assertion failed") => {
  if (!v) throw Error(m);
};
const near = (a, b, e = 1e-7) => assert(Math.abs(a - b) < e, `${a} != ${b}`);
const rejects = (fn, pattern) => {
  let caught = false;
  try {
    fn();
  } catch (e) {
    caught = pattern.test(e.message);
  }
  assert(caught, "Expected rejection " + pattern);
};

Deno.test("payout stays embedded and continuous through full reel traversal and on the standalone dispenser", async () => {
  for (const id of ["fdm", "spool"]) {
    const r = await loadRobot(id, { textures: false }), f = r.filament;
    let previous;
    for (let length = 0; length <= 32; length += .01) {
      f.seek(length);
      const p = f.curves[0].sample(0), info = f.payout;
      assert(info.embeddedDepth > 0 && info.embeddedDepth < .000875);
      assert(info.row > .5 && info.row < 28.5);
      if (previous) {
        assert(
          p.distanceTo(previous) < .0002,
          "Payout jumped at a winding boundary",
        );
      }
      previous = p;
    }
    f.seek(.17);
    const p = f.curves[0].sample(0);
    f.seek(20);
    f.seek(.17);
    near(p.distanceTo(f.curves[0].sample(0)), 0, 1e-10);
    r.dispose();
  }
});

Deno.test("framing fits wide machine rows and narrow modules without clipping", () => {
  for (const [size, aspect] of [[[3, .8, .7], 16 / 9], [[.2, .32, .17], .65]]) {
    const camera = new T.PerspectiveCamera(36, aspect, .001, 40);
    const box = new T.Box3(
      new T.Vector3(...size).multiplyScalar(-.5),
      new T.Vector3(...size).multiplyScalar(.5),
    );
    frameCamera(camera, [box], { direction: [-.55, .75, 1.2], margin: 1.1 });
    camera.updateMatrixWorld(true);
    let extent = 0;
    for (const x of [box.min.x, box.max.x]) {
      for (const y of [box.min.y, box.max.y]) {
        for (const z of [box.min.z, box.max.z]) {
          const p = new T.Vector3(x, y, z).project(camera);
          assert(Math.abs(p.x) < 1 && Math.abs(p.y) < 1 && Math.abs(p.z) < 1);
          extent = Math.max(extent, Math.abs(p.x), Math.abs(p.y));
        }
      }
    }
    assert(extent > .85, "Excessively loose framing");
  }
});

Deno.test("dispenser shares its atlas in the assembled printer and preserves exact part extraction", async () => {
  const c = await catalog(),
    p = await loadRobot("fdm", { textures: false }),
    s = await loadRobot("spool", { textures: false });
  assert(p.parts().includes("G430 interchangeable fixture bed"));
  assert(!p.parts().includes("EX filament inlet"));
  assert(p.roots.fdm_push_fitting.parent === p.roots.extruder_fixed);
  assert(p.roots.filament_carrier.parent === p.roots.filament_stand);
  assert(!p.roots.fdm_tube_support);
  assert(!p.parts().includes("FP dispenser foot"));
  assert(!p.parts().includes("FP swept dispenser spine"));
  assert(p.parts().includes("FP free supply filament"));
  assert(new Set(p.entry.parts).size === p.entry.parts.length);
  for (const id of c.models["manufacturing/filament_spool"].parts) {
    if (!["FP dispenser foot", "FP swept dispenser spine"].includes(id)) {
      assert(p.parts().includes(id));
    }
    assert(s.parts().includes(id));
  }
  const part = await loadPart("spool", "FP front reel cheek", {
    textures: false,
  });
  assert(part.parts().length === 1);
  assert(part.stats().triangles > 0 && part.stats().triangles < 4404);
  const before = p.materials.palette.primary.value.clone();
  p.filament.setColor("#dd6029");
  assert(
    p.materials.palette.primary.value.equals(before),
    "Filament recolor changed the body",
  );
  assert(
    !p.filament.color.equals(s.filament.color),
    "Two instances share a color uniform",
  );
  part.dispose();
  s.dispose();
  p.dispose();
});

Deno.test("extrusion volume, retraction dwells, reel travel and replay use one physical clock", async () => {
  const p = await loadRobot("fdm", { textures: false }),
    g = new T.BoxGeometry(1, 1, 1);
  const j = print(p, g, { size: .008, infill: .3, duration: 18 }),
    d = p.filament.diameter;
  near(j.filamentLength * Math.PI * d * d / 4, j.extrudedVolume, 1e-12);
  const dwells = j.path.spans.filter((s) => s.type !== "move");
  assert(
    dwells.some((s) => s.type === "retract") &&
      dwells.some((s) => s.type === "prime"),
  );
  for (const s of dwells.slice(0, 8)) {
    const a = j.path.sample(s.t0 + (s.t1 - s.t0) * .25),
      b = j.path.sample(s.t0 + (s.t1 - s.t0) * .75);
    near(a.speed, 0);
    near(a.volume, b.volume, 1e-14);
    near(
      new T.Vector3(...a.position).distanceTo(new T.Vector3(...b.position)),
      0,
    );
    assert(
      s.type === "retract"
        ? b.filamentRetraction > a.filamentRetraction
        : b.filamentRetraction < a.filamentRetraction,
    );
  }
  j.seek(7);
  const saved = [
    p.filament.rotation,
    p.filament.consumedLength,
    ...p.toolTip().toArray(),
  ];
  j.seek(18);
  near(p.filament.consumedLength, j.filamentLength);
  j.seek(7);
  saved.forEach((v, i) =>
    near(
      v,
      [
        p.filament.rotation,
        p.filament.consumedLength,
        ...p.toolTip().toArray(),
      ][i],
    )
  );
  j.setColor("#2c59bd");
  assert(j.mesh.material.color.equals(p.filament.color));
  const physical = print(p, g, { size: .008, infill: .3 });
  near(physical.duration, physical.physicalDuration);
  physical.seek(j.state.time);
  near(p.filament.consumedLength, j.state.filamentLength);
  rejects(() => print(p, g, { filamentDiameter: .00285 }), /match.*1.75/);
  physical.dispose();
  j.dispose();
  g.dispose();
  p.dispose();
});

Deno.test("short PTFE entries stay seated while exposed feed follows travel without vertex uploads", async () => {
  const p = await loadRobot("fdm", { textures: false });
  p.group.position.set(.3, .8, -.2);
  p.group.rotation.set(.1, .6, .2);
  p.group.scale.setScalar(1.2);
  const curves = p.filament.tubes,
    lengths = curves.map((c) => c.length),
    versions = curves.map((c) => c.mesh.geometry.attributes.position.version),
    saved = curves.map((c) =>
      c.mesh.geometry.attributes.position.array.slice()
    );
  for (const x of [-.19, 0, .19]) {
    for (const y of [-.235, 0, .235]) {
      for (const z of p.machine.axisLimits[2]) {
        p.axes([x, y, z]);
        p.group.updateMatrixWorld(true);
        assert(p.filament.tubeLength < .18 && p.filament.tubeLength > .14);
        near(p.filament.guideTube.length, .034, 1e-8);
        curves.forEach((c, i) => near(c.length, lengths[i], 1e-6));
        const tubeEnd = curves.at(-1).sample(1).applyMatrix4(
            curves.at(-1).mesh.matrixWorld,
          ),
          inlet = new T.Vector3(0, .115, 0).applyMatrix4(
            p.roots.extruder_fixed.matrixWorld,
          );
        near(tubeEnd.distanceTo(inlet), 0);
        const supply = p.filament.supplies[0],
          lastSupply = p.filament.supplies.at(-1);
        near(curves[1].sample(1).distanceTo(supply.sample(0)), 0);
        near(lastSupply.sample(1).distanceTo(curves[2].sample(0)), 0);
        for (let k = 1; k < p.filament.supplies.length; k++) {
          near(
            p.filament.supplies[k - 1].sample(1).distanceTo(
              p.filament.supplies[k].sample(0),
            ),
            0,
          );
        }
        for (const k of [1, 3]) {
          near(curves[k - 1].sample(1).distanceTo(curves[k].sample(0)), 0);
          near(curves[k - 1].normalAt(1).dot(curves[k].normalAt(0)), 1);
        }
        const start = curves[0].sample(0).applyMatrix4(
          curves[0].mesh.matrixWorld,
        );
        const seat = new T.Vector3(.0415, .242, .155).applyMatrix4(
          p.roots.filament_stand.matrixWorld,
        );
        near(start.distanceTo(seat), 0);
        for (
          const [a, b] of [[curves[0], curves[1]], [curves[1], supply], [
            supply,
            lastSupply,
          ], [
            lastSupply,
            curves[2],
          ], [
            curves[2],
            curves[3],
          ]]
        ) {
          const pa = a.points, pb = b.points;
          near(
            pa[3].clone().sub(pa[2]).normalize().dot(
              pb[1].clone().sub(pb[0]).normalize(),
            ),
            1,
          );
        }
      }
    }
  }
  curves.forEach((c, i) => {
    near(c.mesh.geometry.attributes.position.version, versions[i]);
    assert(
      saved[i].every((v, k) =>
        v === c.mesh.geometry.attributes.position.array[k]
      ),
    );
  });
  for (const c of curves) {
    assert(
      c.mesh.material.transparent && c.mesh.material.opacity > 0 &&
        c.mesh.material.opacity < 1,
    );
  }
  assert(p.filament.cores.length === curves.length);
  for (let i = 0; i < curves.length; i++) {
    near(curves[i].sample(.5).distanceTo(p.filament.cores[i].sample(.5)), 0);
  }
  const points = p.filament.tubes[1].points.map((v) => v.toArray()),
    tube = createPTFETube({ points });
  near(tube.length, bezierLength(tube.points));
  rejects(
    () => tube.setPoints([[0, 0, 0], [0, 0, 0], [1, 0, 0], [2, 0, 0]]),
    /Degenerate/,
  );
  tube.dispose();
  p.dispose();
});

Deno.test("wood and metal retain material-specific feed and debris, with deterministic stock removal", async () => {
  const c = await loadRobot("cnc", { textures: false });
  let metalDuration;
  for (const material of Object.keys(stockMaterials)) {
    const j = mill(c, null, { material, duration: 18, resolution: 64 });
    assert(j.stock.removedVolume > 0);
    assert(j.removal.events.every((e) => e.volume > 0));
    assert(j.settings.material === material);
    near(j.settings.rpm, stockMaterials[material].rpm);
    assert(
      j.effects.group.children.some((m) =>
        m.name ===
          (material === "wood" || material === "plywood"
            ? "Wood shavings"
            : "Metal swarf")
      ),
    );
    assert(
      j.effects.group.children.some((m) => m.name === "Wood fines") ===
        (stockMaterials[material].kind === "wood"),
    );
    j.seek(6);
    const rotation = c.roots.spindle_rotor.quaternion.clone();
    j.seek(15);
    j.seek(6);
    near(rotation.angleTo(c.roots.spindle_rotor.quaternion), 0);
    if (material === "aluminum") metalDuration = j.physicalDuration;
    if (material === "wood") assert(j.physicalDuration < metalDuration);
    j.dispose();
  }
  for (
    const [opts, pattern] of [
      [{ material: "plastic" }, /Unknown stock/],
      [{ flutes: 0 }, /flutes/],
      [{ radius: .01 }, /3 mm radius/],
      [{ stockWidth: 1 }, /physical bed/],
    ]
  ) rejects(() => mill(c, null, opts), pattern);
  c.dispose();
});

Deno.test("authored build surfaces share one rectangular atlas and preserve process datums", async () => {
  const cat = await catalog(),
    p = await loadRobot("fdm", { textures: false }),
    c = await loadRobot("cnc", { textures: false });
  const f = await loadRobot("fdm_plate", { textures: false }),
    m = await loadRobot("cnc_plate", { textures: false });
  const images = cat.textures.filter((t) =>
    t.path.startsWith("textures/plates_")
  );
  assert(
    images.length === 3 &&
      images.every((t) => t.dimensions[0] === 512 && t.dimensions[1] === 1024),
  );
  assert(
    m.parts().filter((n) => n.startsWith("BP T-slot deck extrusion")).length ===
      8,
  );
  for (
    const name of [
      "fdm_plate",
      "cnc_plate",
      "cnc_clamp",
      "tube_support",
      "push_fitting",
      "fdm",
      "cnc",
      "cnc_relief",
    ]
  ) {
    const path = cat.models["manufacturing/" + name].path;
    const bytes = await Deno.readFile(
      new URL("../../assets/robotics/" + path, import.meta.url),
    );
    const size = new DataView(bytes.buffer, bytes.byteOffset).getUint32(
      12,
      true,
    );
    const glb = JSON.parse(
      new TextDecoder().decode(bytes.subarray(20, 20 + size)),
    );
    const plateTextures = glb.textures.filter((t) =>
      glb.images[t.source].uri?.includes("plates_")
    );
    assert(plateTextures.length >= 3);
    assert(
      plateTextures.every((t) =>
        glb.samplers[t.sampler].extras?.eidoverse_anisotropy === 8
      ),
    );
  }
  assert(!c.parts().includes("G430 interchangeable fixture bed"));
  p.group.updateMatrixWorld(true);
  c.group.updateMatrixWorld(true);
  const sheet = new T.Box3().setFromObject(
    p.part("BP removable PEI spring-steel sheet")[0],
  );
  near(sheet.min.y, p.machine.bedTop, 1e-7);
  near(sheet.max.y, p.machine.bedTop + .00065, 1e-7);
  near(sheet.min.x, -.229, 1e-7);
  near(sheet.max.x, .229, 1e-7);
  near(sheet.max.z, .298, 1e-7);
  const original = new T.Box3().setFromObject(
    p.part("G430 interchangeable fixture bed")[0],
  );
  near(original.max.y, p.machine.bedTop, 1e-7);
  assert(sheet.min.x < original.min.x && sheet.max.x > original.max.x);
  assert(
    sheet.max.z > original.max.z + .02,
    "Pull tabs must overhang the accepted bed",
  );
  p.moveTool([0, .00085, 0]);
  near(p.toolTip().y, .00085, 1e-7);
  const fixture = new T.Box3().setFromObject(c.roots.cnc_fixture_plate);
  near(fixture.max.y, c.machine.bedTop, 1e-7);
  const ray = new T.Raycaster(new T.Vector3(0, .1, 0), new T.Vector3(0, -1, 0));
  const deck = c.parts().filter((n) => n.startsWith("BP T-slot deck extrusion"))
    .flatMap((n) => c.part(n));
  near(ray.intersectObjects(deck, false)[0].point.y, .038, 1e-7);
  ray.ray.origin.x = .025;
  near(ray.intersectObjects(deck, false)[0].point.y, .056, 1e-7);
  assert(
    Object.keys(c.roots).filter((n) => n.startsWith("cnc_clamp_")).length === 4,
  );
  const g = new T.BoxGeometry(1, 1, 1), j = print(p, g, { size: .008 });
  assert(j.plate === p.roots.fdm_build_plate);
  j.dispose();
  assert(
    p.roots.fdm_build_plate.parent === p.roots.gantry_base,
    "Job disposal removed shared hardware",
  );
  rejects(() => print(p, g, { base: .012 }), /removable PEI sheet/);
  const custom = print(p, g, { base: .012, buildPlate: false });
  assert(!p.roots.fdm_build_plate.visible);
  custom.dispose();
  g.dispose();
  f.dispose();
  m.dispose();
  p.dispose();
  c.dispose();
});

Deno.test("ball tools and adjustable fixtures share their finished atlas across assemblies", async () => {
  const cat = await catalog();
  const maps = cat.textures.filter(t => t.path.startsWith("textures/rotary_workholding_"));
  assert(maps.length === 5 && maps.every(t => t.dimensions[0] === 2048 && t.dimensions[1] === 2048));
  let primary;
  for (const name of ["ball_tool", "rotary_fixture", "cnc_relief", "cnc_rotary"]) {
    const robot = await loadRobot(name, {textures:false});
    const bindings = robot.report.texture_bindings.rotary_workholding;
    assert(bindings && Object.keys(bindings).length === 5);
    const identity = JSON.stringify(Object.keys(bindings).sort().map(k => [k, bindings[k].identity, bindings[k].uri]));
    primary ??= identity;
    assert(identity === primary, "Finished cutter/fixture maps must be shared in " + name);
    robot.dispose();
  }
});

Deno.test("air cuts and repeated passes emit no false debris, and rapid stock collisions are rejected", () => {
  const options = {
    width: .04,
    depth: .04,
    height: .02,
    radius: .003,
    resolution: 128,
  };
  const path = (points) =>
    new FeedPath(points, {
      feed: .01,
      rapid: .08,
      acceleration: .25,
      blendTolerance: 0,
    });
  const air = sampleRemoval(
    path([{ position: [-.01, .025, 0], type: "rapid" }, {
      position: [.01, .025, 0],
      type: "cut",
    }]),
    options,
  );
  assert(air.events.length === 0);
  const points = [{ position: [-.01, .03, 0], type: "rapid" }, {
    position: [-.01, .015, 0],
    type: "cut",
  }, { position: [.01, .015, 0], type: "cut" }];
  const first = sampleRemoval(path(points), options);
  points.push({ position: [-.01, .015, 0], type: "cut" });
  const repeat = sampleRemoval(path(points), options);
  near(first.removedVolume, repeat.removedVolume, 1e-12);
  assert(!repeat.intervals.at(-1).engaged);
  rejects(
    () =>
      sampleRemoval(
        path([{ position: [-.01, .03, 0], type: "rapid" }, {
          position: [-.01, .015, 0],
          type: "rapid",
        }]),
        options,
      ),
    /Rapid move intersects/,
  );
  rejects(
    () =>
      sampleRemoval(
        path([{ position: [0, .03, 0], type: "rapid" }, {
          position: [0, .001, 0],
          type: "cut",
        }]),
        options,
      ),
    /flute length/,
  );
});
