import * as T from "three/webgpu";
import { assetRoot, catalog, loadPart, loadRobot } from "../index.js";
import { mill, print } from "../fabrication.js";
Deno.test("individual parts retain exact triangle ownership and shared donors", async () => {
  for (const id of ["face", "air/air", "rotors_air_air/air_air_rotors"]) {
    const donor = await loadRobot(id, { textures: false }),
      name = id === "face"
        ? "FACE swept tilt yoke"
        : donor.parts().find((n) =>
          donor.part(n).some((o) => o.userData.part_ids?.length > 1)
        ),
      before = donor.stats().triangles;
    const expected = donor.part(name).reduce(
        (sum, o) =>
          sum + o.userData.partForFace.filter((n) => n === name).length,
        0,
      ),
      part = await loadPart(id, name, { textures: false });
    assert(expected > 0, "No triangles in selected source part " + id);
    assert(
      part.parts().length === 1 && part.stats().parts === 1,
      "Extracted part reports donor parts",
    );
    near(part.stats().triangles, expected);
    part.model.traverse((o) => {
      if (o.isMesh && o.visible) {
        assert(
          o.userData.partForFace.length ===
              (o.geometry.index?.count ??
                  o.geometry.attributes.position.count) / 3 &&
            o.userData.partForFace.every((n) => n === name),
          "Extracted face lookup differs from filtered mesh",
        );
      }
    });
    part.dispose();
    near(donor.stats().triangles, before);
    donor.dispose();
  }
});
Deno.test("unknown parts cannot leave a donor assembly in the scene", async () => {
  const scene = new T.Scene();
  let rejected = false;
  try {
    await loadPart("face", "__missing_part__", { textures: false, scene });
  } catch (e) {
    rejected = e.message.includes("Unknown part");
  }
  assert(
    rejected && scene.children.length === 0,
    "Failed extraction left donor geometry in scene",
  );
});
const assert = (v, m) => {
    if (!v) throw Error(m);
  },
  near = (a, b, e = 1e-7) => assert(Math.abs(a - b) < e, `${a} != ${b}`);
Deno.test("complete catalog loads, finite deterministic joint/motion transforms", async () => {
  const c = await catalog();
  assert(Object.keys(c.models).length >= 78, "Missing kit content");
  assert(
    c.textures.length === 67,
    "Expected the shared kit maps, dispenser, build surfaces, spool carrier and rotary workholding",
  );
  assert(
    new Set(c.textures.map((t) => t.path)).size === c.textures.length &&
      new Set(c.textures.map((t) => t.file_sha256)).size === c.textures.length,
    "Duplicate texture files",
  );
  for (const id of Object.keys(c.models)) {
    const r = await loadRobot(id, { textures: false });
    if (
      ["manufacturing/rotary_fixture", "manufacturing/cnc_rotary"].includes(id)
    ) {
      const workholding = r.materials.materials.find((m) =>
        m.name === "EIDO / rotary_workholding"
      );
      const recolor = workholding?.userData.eidoverse_recolor;
      assert(
        recolor?.fixed === "../textures/rotary_workholding_fixed.png" &&
          recolor?.mask === "../textures/rotary_workholding_mask.png" &&
          recolor.default_primary_linear.length === 3 &&
          recolor.default_accent_linear.length === 3,
        "Workholding lost its recolor texture bindings: " + id,
      );
    }
    const mappedParts = new Set();
    r.model.traverse((o) => {
      if (!o.isMesh) return;
      const faces = o.userData.partForFace;
      if (!faces) return;
      assert(
        faces.length ===
          (o.geometry.index?.count ?? o.geometry.attributes.position.count) / 3,
        "Triangle ownership length mismatch: " + id + "/" + o.name,
      );
      for (const name of faces) if (name) mappedParts.add(name);
    });
    for (const name of r.parts()) {
      assert(
        mappedParts.has(name),
        "Part has no mapped triangles: " + id + "/" + name,
      );
    }
    for (const clip of r.clips) {
      r.sample(clip, 2);
      r.group.updateMatrixWorld(true);
      const first = [];
      r.model.traverse((o) => first.push(...o.matrixWorld.elements));
      r.sample(clip, 8);
      r.sample(clip, 2);
      r.group.updateMatrixWorld(true);
      let i = 0;
      r.model.traverse((o) =>
        o.matrixWorld.elements.forEach((v) => {
          assert(Number.isFinite(v), "Nonfinite " + id + "/" + clip);
          near(v, first[i++]);
        })
      );
    }
    r.dispose();
  }
});
Deno.test("matching mounts seat without a half-turn on an upright camera", async () => {
  const body = await loadRobot("mobility/body", { textures: false }),
    camera = await loadRobot("camera", { textures: false });
  body.group.rotation.y = .7;
  body.group.position.set(.3, .5, -.2);
  body.attach(camera, {
    port: "body_base/sensor_0",
    childPort: "camera_base/input",
  });
  body.group.updateMatrixWorld(true);
  const a = body.port("body_base/sensor_0"),
    b = camera.port("camera_base/input"),
    ma = a.owner.matrixWorld.clone().multiply(a.matrix),
    mb = b.owner.matrixWorld.clone().multiply(b.matrix);
  near(
    new T.Vector3().setFromMatrixPosition(ma).distanceTo(
      new T.Vector3().setFromMatrixPosition(mb),
    ),
    0,
  );
  near(
    new T.Vector3(0, 0, 1).transformDirection(ma).dot(
      new T.Vector3(0, 0, 1).transformDirection(mb),
    ),
    -1,
  );
  near(
    new T.Vector3(0, 0, 1).transformDirection(camera.group.matrixWorld).dot(
      new T.Vector3(0, 0, 1).transformDirection(body.group.matrixWorld),
    ),
    1,
  );
  let rejected = false;
  try {
    camera.attach(body, {
      port: "camera_base/input",
      childPort: "body_base/payload",
    });
  } catch {
    rejected = true;
  }
  assert(rejected, "Cycle/mismatched interface accepted");
  body.dispose();
  assert(camera.disposed, "Attached child leaked");
});
Deno.test("mirrored legs attach to the approved articulated pelvis", async () => {
  const hip = await loadRobot("humanoid_modules/pelvis", { textures: false });
  for (const side of ["left", "right"]) {
    const leg = await loadRobot("humanoid_modules/" + side + "_leg", {
      textures: false,
    });
    hip.attach(leg, {
      port: "pelvis_" + side + "_roll/" + side + "_leg",
      childPort: "leg_mount/input",
    });
    hip.group.updateMatrixWorld(true);
    const a = hip.port("pelvis_" + side + "_roll/" + side + "_leg"),
      b = leg.port("leg_mount/input"),
      ma = a.owner.matrixWorld.clone().multiply(a.matrix),
      mb = b.owner.matrixWorld.clone().multiply(b.matrix);
    near(
      new T.Vector3().setFromMatrixPosition(ma).distanceTo(
        new T.Vector3().setFromMatrixPosition(mb),
      ),
      0,
    );
    assert(leg.parts().length < 30, "Unrelated humanoid parts retained");
  }
  hip.dispose();
});
Deno.test("humanoid has independent left/right limbs and complete thumb curl", async () => {
  const r = await loadRobot("humanoid", { textures: false }),
    hands = Object.keys(r.roots).filter((n) => n.endsWith("hand_base")),
    knees = Object.keys(r.roots).filter((n) => n.endsWith("leg_knee"));
  assert(
    hands.length === 2 && knees.length === 2,
    "Instance roots overwritten",
  );
  r.grasp(1);
  for (
    const n of Object.keys(r.state).filter((n) => n.endsWith("dh_thumb_mcp"))
  ) assert(r.state[n] > .4, "Thumb stayed straight");
  r.dispose();
});
Deno.test("fabrication matches actual tool frames, rejects travel, and never uploads vertices per frame", async () => {
  const printer = await loadRobot("fdm", { textures: false }),
    cnc = await loadRobot("cnc", { textures: false });
  printer.group.position.set(.4, .3, -.2);
  printer.group.rotation.y = .63;
  const geometry = new T.LatheGeometry(
      [[.014, 0], [.020, 0], [.020, .004], [.014, .004], [.014, 0]].map((p) =>
        new T.Vector2(...p)
      ),
      24,
    ),
    jobs = [
      print(printer, geometry, { size: .04, infill: 0, duration: 12 }),
      mill(cnc, null, { duration: 12 }),
    ];
  const bead = jobs[0].mesh.geometry,
    p = bead.attributes.position,
    n = bead.attributes.normal;
  for (let i = 0; i < bead.index.count; i += 3) {
    const ids = [0, 1, 2].map((j) => bead.index.getX(i + j)),
      v = ids.map((j) => new T.Vector3().fromBufferAttribute(p, j)),
      face = v[1].clone().sub(v[0]).cross(v[2].clone().sub(v[0]));
    if (face.lengthSq() < 1e-22) continue;
    const avg = ids.reduce(
      (a, j) => a.add(new T.Vector3().fromBufferAttribute(n, j)),
      new T.Vector3(),
    );
    assert(
      face.normalize().dot(avg.normalize()) >= -1e-4,
      "Bead surface winding disagrees with outward shading",
    );
  }
  for (const job of jobs) {
    const attrs = Object.values(job.mesh.geometry.attributes).map(
      (a) => [a, a.version, Array.from(a.array)],
    );
    for (const t of [0, 4, 12, 1, 0, 12]) {
      const state = job.seek(t);
      near(
        job.machine.toolTip().distanceTo(new T.Vector3(...state.position)),
        0,
      );
      for (const [a, v, data] of attrs) {
        assert(a.version === v, "Per-frame upload");
        assert(data.every((x, i) => x === a.array[i]), "CPU vertices changed");
      }
    }
    job.dispose();
  }
  const before = JSON.stringify(cnc.state);
  let rejected = false;
  try {
    mill(cnc, [{ position: [0, .03, 0], type: "rapid" }, {
      position: [1, -1, 0],
      type: "cut",
    }]);
  } catch {
    rejected = true;
  }
  assert(
    rejected && JSON.stringify(cnc.state) === before,
    "Bad path changed machine",
  );
  printer.dispose();
  cnc.dispose();
});
Deno.test("retired primitives cannot silently appear", async () => {
  for (const id of ["delta", "stewart", "turret", "kossel"]) {
    let rejected = false;
    try {
      await loadRobot(id, { textures: false });
    } catch {
      rejected = true;
    }
    assert(rejected, "Retired builder still active " + id);
  }
});
Deno.test("arm solvers agree with the actual exported tool transforms", async () => {
  const C = new T.Matrix4().makeRotationX(-Math.PI / 2),
    arm = await loadRobot("arm", { textures: false }),
    q = [.2, .4, -.6, .25, .6, -.2];
  arm.joints(q);
  arm.group.updateMatrixWorld(true);
  const target = C.clone().multiply(
      new T.Matrix4().set(...arm.ik.forward(q).flat()),
    ).multiply(C.clone().invert()),
    p = new T.Vector3().setFromMatrixPosition(target);
  near(
    arm.roots.a650_j6.localToWorld(new T.Vector3(.018, 0, 0)).distanceTo(p),
    0,
  );
  arm.moveTo(target, [0, .3, -.5, 0, .3, 0]);
  arm.group.updateMatrixWorld(true);
  near(
    arm.roots.a650_j6.localToWorld(new T.Vector3(.018, 0, 0)).distanceTo(p),
    0,
    3e-5,
  );
  arm.dispose();
  const sc = await loadRobot("scara", { textures: false }),
    j = [.2, .8, .04, -.4];
  sc.scaraJoints(j);
  sc.group.updateMatrixWorld(true);
  const f = sc.scara.forward(j);
  near(
    sc.roots.s500_tool.getWorldPosition(new T.Vector3()).distanceTo(
      new T.Vector3(f[0], f[2], -f[1]),
    ),
    0,
  );
  sc.dispose();
});
