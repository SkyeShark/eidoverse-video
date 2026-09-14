// MIT. Deterministic controls for the approved rigid modules and sample builds.
import * as T from "three/webgpu";
import { json } from "./io.js";
import { graspValues } from "./grasp.js";
import { articulatedDemo, gantryDemo, SerialArm } from "./serial_arm.js";
import * as scara from "./scara.js";
import { createRunningController } from "./running.js";
import { rotaryFixtureSetup } from "./rotary_setup.js";
const TAU = Math.PI * 2,
  C = new T.Matrix4().makeRotationX(-Math.PI / 2),
  Ci = C.clone().invert();
const axis = ([x, y, z]) => new T.Vector3(x, z, -y),
  smooth = (x) => {
    x = T.MathUtils.clamp(x, 0, 1);
    return x * x * x * (10 + x * (-15 + 6 * x));
  };
const suffix = (n) => n.split(" / ").at(-1);
function trackFrame(s, p) {
  const h = p.half_wheelbase_m, r = p.radius_m, z = p.height_m;
  s = T.MathUtils.euclideanModulo(s, p.length_m);
  let x, y, tx, tz, nx, nz;
  if (s < 2 * h) {
    x = -h + s;
    y = z + r;
    tx = 1;
    tz = 0;
    nx = 0;
    nz = 1;
  } else if ((s -= 2 * h) < Math.PI * r) {
    const a = Math.PI / 2 - s / r;
    x = h + r * Math.cos(a);
    y = z + r * Math.sin(a);
    tx = Math.sin(a);
    tz = -Math.cos(a);
    nx = Math.cos(a);
    nz = Math.sin(a);
  } else if ((s -= Math.PI * r) < 2 * h) {
    x = h - s;
    y = z - r;
    tx = -1;
    tz = 0;
    nx = 0;
    nz = -1;
  } else {
    const a = -Math.PI / 2 - (s - 2 * h) / r;
    x = -h + r * Math.cos(a);
    y = z + r * Math.sin(a);
    tx = Math.sin(a);
    tz = -Math.cos(a);
    nx = Math.cos(a);
    nz = Math.sin(a);
  }
  return new T.Matrix4().set(
    tx,
    0,
    nx,
    x,
    0,
    1,
    0,
    0,
    tz,
    0,
    nz,
    y,
    0,
    0,
    0,
    1,
  );
}
function installTracks(robot) {
  const specs = robot.report.mobile?.tracks;
  if (!specs) return;
  const bindings = [];
  robot.group.updateMatrixWorld(true);
  const originals = [];
  robot.model.traverse((o) => {
    if (o.isMesh) originals.push(o);
  });
  for (const [n, s] of Object.entries(specs)) {
    const root = robot.roots[n];
    if (!root) continue;
    const shoes = new Map(s.shoes.map((t) => [t.part, t]));
    for (const mesh of originals) {
      const faces = mesh.userData.partForFace;
      if (!faces?.some((p) => shoes.has(p))) continue;
      const g = mesh.geometry,
        index = (i) => g.index ? g.index.getX(i) : i,
        keep = [],
        parts = new Map();
      faces.forEach((name, fi) => {
        const dest = shoes.has(name)
          ? (parts.get(name) ?? (parts.set(name, []), parts.get(name)))
          : keep;
        for (let j = 0; j < 3; j++) dest.push(index(fi * 3 + j));
      });
      const localFromRoot = mesh.matrixWorld.clone().invert().multiply(
          root.matrixWorld,
        ),
        rootFromLocal = localFromRoot.clone().invert();
      const retained = g.clone();
      retained.setIndex(keep);
      mesh.geometry = retained;
      mesh.userData.partForFace = faces.filter((p) => !shoes.has(p));
      for (const [p, indices] of parts) {
        const geom = g.clone();
        geom.setIndex(indices);
        geom.computeBoundingSphere();
        const ob = new T.Mesh(geom, mesh.material);
        ob.name = p;
        ob.userData = {
          ...mesh.userData,
          part_ids: [p],
          partForFace: Array(indices.length / 3).fill(p),
        };
        ob.matrixAutoUpdate = false;
        ob.castShadow = ob.receiveShadow = true;
        mesh.add(ob);
        const spec = shoes.get(p);
        bindings.push({
          n,
          ob,
          spec,
          path: s.path,
          left: localFromRoot.clone().multiply(C),
          right: new T.Matrix4().set(...spec.rest_frame.flat()).invert()
            .multiply(Ci).multiply(rootFromLocal),
        });
      }
    }
  }
  robot.trackTravel = (values = {}) => {
    for (const [n, v] of Object.entries(values)) {
      if (!specs[n] || !Number.isFinite(v)) {
        throw Error("Invalid track travel " + n);
      }
    }
    for (const b of bindings) {
      b.ob.matrix.copy(b.left).multiply(
        trackFrame(b.spec.distance_m + (values[b.n] ?? 0), b.path),
      ).multiply(b.right);
      b.ob.matrixWorldNeedsUpdate = true;
    }
    const wheels = {};
    for (const [n, s] of Object.entries(specs)) {
      const d = values[n] ?? 0;
      for (const w of [...s.wheel_roots, ...s.roller_roots]) {
        if (robot.roots[w]) {
          const spec = robot.specs[w],
            a = d / (spec.rolling_radius_m ?? .058),
            rest = robot.rest.get(robot.roots[w]);
          robot.roots[w].quaternion.copy(rest.quaternion).multiply(
            new T.Quaternion().setFromAxisAngle(axis(spec.axis), a),
          );
          wheels[w] = a;
        }
      }
    }
    return { distances: { ...values }, wheels };
  };
  robot.trackTravel({});
  robot.trackBindings = bindings;
}
export async function installMotion(robot) {
  const { roots, specs, report } = robot;
  const names = Object.keys(roots);
  if (roots.rotary_tailstock && roots.rotary_jaw_0) {
    robot.rotarySetup = (options = {}) => {
      const setup = rotaryFixtureSetup(options);
      robot.setJoints(setup.joints);
      robot.rotaryStockSetup = setup;
      return setup;
    };
  }
  const fans = names.filter((n) => suffix(n) === "extruder_fan");
  robot.coolingFan = (seconds, { rpm = 4800 } = {}) => {
    if (!Number.isFinite(seconds) || seconds < 0 || !Number.isFinite(rpm) || rpm < 0) {
      throw Error("Cooling fan time and rpm must be finite and nonnegative");
    }
    for (const n of fans) {
      const angle = (seconds * rpm / 60 * TAU) % TAU;
      roots[n].quaternion.copy(robot.rest.get(roots[n]).quaternion).multiply(
        new T.Quaternion().setFromAxisAngle(axis(specs[n].axis), angle),
      );
      robot.state[n] = angle;
      roots[n].updateMatrix();
    }
    return robot;
  };
  const interaction = await json(
    new URL("../assets/robotics/metadata/interaction.json", import.meta.url),
  );
  if (report.novel) {
    for (const [n, rows] of Object.entries(report.novel.nominal_matrices)) {
      const o = roots[n];
      if (!o) continue;
      const m = C.clone().multiply(new T.Matrix4().set(...rows.flat()))
          .multiply(Ci),
        r = robot.rest.get(o);
      m.decompose(r.position, r.quaternion, r.scale);
    }
    robot.defaultJoints = Object.fromEntries(
      Object.entries(report.novel.drives).filter(([n]) => roots[n]).map((
        [n, d],
      ) => [n, d.angle]),
    );
    robot.reset();
    robot.setJoints(robot.defaultJoints);
  }
  const grasp = interaction.mobile.hand.grasp,
    graspPrefixes = names.filter((n) => suffix(n) === "hand_base").map((n) =>
      n.slice(0, -"hand_base".length)
    );
  robot.grasp = (phase) => {
    if (!Number.isFinite(phase) || phase < 0 || phase > 1) {
      throw Error("Grasp phase must be 0..1");
    }
    const q = {};
    for (const p of graspPrefixes) {
      for (const [n, v] of Object.entries(graspValues(grasp, phase))) {
        if (roots[p + n]) q[p + n] = v;
      }
    }
    robot.setJoints(q);
    return robot;
  };
  robot.graspReference = () => {
    const objects = [];
    for (const p of graspPrefixes) {
      const s = grasp.object,
        ob = new T.Mesh(
          new T.CylinderGeometry(s.radius_m, s.radius_m, s.length_m, 48),
          new T.MeshStandardNodeMaterial({
            color: 0x367d85,
            roughness: .5,
            metalness: .1,
          }),
        );
      ob.position.copy(axis(s.center_m));
      ob.quaternion.setFromUnitVectors(new T.Vector3(0, 1, 0), axis(s.axis));
      roots[p + "hand_base"].add(ob);
      ob.name = "Grasp reference";
      objects.push(ob);
    }
    return objects;
  };
  robot.jawGap = (gap) => {
    if (!Number.isFinite(gap) || gap < 0 || gap > .044) {
      throw Error("Jaw gap must be 0..0.044 m");
    }
    const q = {};
    for (const n of names) {
      if (suffix(n) === "jaw_left" || suffix(n) === "jaw_right") q[n] = gap / 2;
      else if (suffix(n) === "pg_drive_screw") q[n] = -gap / 2 / .004 * TAU;
    }
    robot.setJoints(q);
    return robot;
  };
  robot.spinRotors = (angle) => {
    if (!Number.isFinite(angle)) throw Error("Rotor angle must be finite");
    const q = {};
    for (const n of names) {
      if (/air_rotor_[0-3]$/.test(n)) {
        const boom = n.replace("rotor", "boom");
        if (
          Math.abs(robot.state[boom] ?? 0) > 1e-7 && angle !== 0
        ) throw Error("Deploy booms before spinning rotors");
        q[n] = angle * ([1, -1, -1, 1][Number(n.at(-1))]);
      }
    }
    for (const [n, v] of Object.entries(q)) {
      const r = robot.rest.get(roots[n]);
      roots[n].quaternion.copy(r.quaternion).multiply(
        new T.Quaternion().setFromAxisAngle(axis(specs[n].axis), v),
      );
    }
    return robot;
  };
  robot.fold = (phase) => {
    if (phase < 0 || phase > 1 || !Number.isFinite(phase)) {
      throw Error("Fold phase must be 0..1");
    }
    robot.spinRotors(0);
    const q = {};
    for (const n of names) {
      if (/air_boom_[0-3]$/.test(n)) {
        q[n] = Math.max(0, (phase - .15) / .85) * .95;
      }
      if (/air_lock_[0-3]$/.test(n)) q[n] = Math.min(phase / .15, 1) * .04;
    }
    robot.setJoints(q);
    return robot;
  };
  installTracks(robot);
  if (roots.a650_j6) {
    robot.ik = new SerialArm(report);
    robot.joints = (q) =>
      robot.setJoints(
        Object.fromEntries(q.map((v, i) => ["a650_j" + (i + 1), v])),
      );
    robot.moveTo = (target, seed) => {
      const b = C.clone().invert().multiply(target.clone()).multiply(C);
      const rows = Array.from(
        { length: 4 },
        (_, i) => Array.from({ length: 4 }, (_, j) => b.elements[j * 4 + i]),
      );
      const q = robot.ik.inverse(rows, seed);
      if (!q) throw Error("A650 target is unreachable within joint limits");
      return robot.joints(q);
    };
  }
  const scaraNames = ["s500_shoulder", "s500_elbow", "s500_quill", "s500_tool"];
  robot.scara = roots.s500_shoulder ? scara : null;
  if (robot.scara) {
    robot.scaraJoints = (q) =>
      robot.setJoints(Object.fromEntries(scaraNames.map((n, i) => [n, q[i]])));
    robot.moveScara = (position, yaw = 0, { tcp = [0, 0, 0], seed } = {}) => {
      const [x, y, z] = position;
      const q = scara.inverse(x, -z, y, yaw, tcp, seed)[0];
      if (!q) throw Error("S500 target is unreachable");
      return robot.scaraJoints(q);
    };
  }
  if (roots.gantry_x) {
    const a = report.inspector?.assemblies?.[robot.entry.assembly] ?? {},
      tool = a.tool === "spindle"
        ? "spindle_fixed"
        : a.tool === "extruder"
        ? "extruder_fixed"
        : null;
    robot.machine = {
      bedTop: a.bed_top_z_m ?? .056,
      axisLimits: [
        specs.gantry_x.limits,
        specs.gantry_y.limits,
        a.z_limits_m ?? specs.gantry_z.limits,
      ],
      bedBounds: specs.gantry_base?.bed_bounds_xy ?? [-.225, .225, -.274, .246],
      tool,
      cutter: a.cutter ?? (a.tool === "spindle" ? {kind: "flat", radius: .003, fluteLength: .018} : null),
    };
    robot.axes = (q) => {
      if (q.length !== 3) throw Error("XYZ requires 3 coordinates");
      const limits = robot.machine.axisLimits;
      q.forEach((v, i) => {
        if (
          !Number.isFinite(v) || v < limits[i][0] - 1e-7 ||
          v > limits[i][1] + 1e-7
        ) throw Error("G430 travel exceeded on " + ["X", "Y", "Z"][i]);
      });
      const values = { gantry_x: q[0], gantry_y: q[1], gantry_z: q[2] };
      for (const [n, s] of Object.entries(specs)) {
        if (n.startsWith("gantry_") && n.includes("screw")) {
          const i = n.includes("_x_") ? 0 : n.includes("_y_") ? 1 : 2;
          values[n] = q[i] / .008 * TAU;
        }
      }
      robot.setJoints(values);
      return robot;
    };
    if (tool) {
      robot.group.updateMatrixWorld(true);
      const rest = roots.gantry_base.worldToLocal(
        roots[tool].getWorldPosition(new T.Vector3()),
      );
      robot.machine.restTip = rest.toArray();
      robot.machine.toAxes = (p) => [
        p[0] - rest.x,
        -p[2] + rest.z,
        p[1] + robot.machine.bedTop - rest.y,
      ];
      robot.moveTool = (p) => robot.axes(robot.machine.toAxes(p));
      robot.toolTip = (world = false) => {
        robot.group.updateMatrixWorld(true);
        const p = roots[tool].getWorldPosition(new T.Vector3());
        return world ? p : roots.gantry_base.worldToLocal(p).add(
          new T.Vector3(0, -robot.machine.bedTop, 0),
        );
      };
    }
  }
  const mixer = new T.AnimationMixer(robot.model);
  robot.mixer = mixer;
  const actions = robot.gltf.animations.map((c) => mixer.clipAction(c));
  let running = null;
  const gait = robot.entry.family === "humanoid" ||
    robot.entry.family === "quadruped";
  if (gait) {
    running = await createRunningController(
      robot.gltf,
      robot.entry.family === "quadruped",
      await json(
        new URL(
          "../assets/robotics/metadata/" + robot.entry.family + "_running.json",
          import.meta.url,
        ),
      ),
    );
  }
  robot.clips = gait
    ? ["walk", "run-circle", "run-figure_eight", "run-straight"]
    : [];
  if (graspPrefixes.length) robot.clips.push("grasp");
  if (robot.trackTravel) robot.clips.push("drive", "drive-circle");
  if (robot.rotarySetup) robot.clips.push("stock-setup");
  if (names.some((n) => n.endsWith("airframe"))) {
    robot.clips.push("flight", "fold", "rotors");
  }
  robot.clips.push("joints");
  if (roots.filament_reel && !robot.machine) robot.clips.unshift("filament-feed");
  robot.sample = (clip, time) => {
    if (!Number.isFinite(time) || time < 0) {
      throw Error("Animation time must be nonnegative seconds");
    }
    robot.reset();
    const t = (time % 12) / 12,
      s = Math.sin(t * TAU),
      curl = .5 - .5 * Math.cos(t * TAU);
    if (clip === "stock-setup") {
      if (!robot.rotarySetup) throw Error("No adjustable rotary fixture");
      robot.rotarySetup({
        stockLength: .130 + .050 * s,
        stockWidth: .034 + .016 * Math.cos(t * TAU),
        stockHeight: .034 - .016 * Math.cos(t * TAU),
        quill: .004 * s,
      });
      robot.setJoints({ rotary_output: time * .25 });
      return robot;
    }
    if (clip === "walk") {
      if (!gait) throw Error("No walk clip for " + robot.id);
      actions.forEach((a) => a.play());
      mixer.setTime(time);
      return robot;
    }
    mixer.stopAllAction();
    if (clip.startsWith("run-")) {
      if (!running) throw Error("No gait for " + robot.id);
      const c = clip.slice(4);
      if (!running.data.clips[c]) throw Error("Unknown gait " + clip);
      running.apply(c, time % running.duration(c));
      return robot;
    }
    if (!robot.clips.includes(clip)) {
      throw Error("Unknown sample " + clip + " for " + robot.id);
    }
    if (clip === "filament-feed") {
      robot.filament.seek(time * .025);
      return robot;
    }
    if (clip === "grasp") {
      robot.grasp(Math.min(time / 3, 1));
      return robot;
    }
    if (clip === "fold") {
      robot.fold(curl);
      return robot;
    }
    if (clip === "rotors") {
      robot.spinRotors(time * TAU * 1.2);
      return robot;
    }
    if (clip === "flight") {
      const envelope = smooth((t - .30) / .08) * (1 - smooth((t - .74) / .08)),
        height = .22 * smooth((t - .12) / .17) * (1 - smooth((t - .78) / .18)),
        x = .11 * Math.sin(TAU * (t - .30) / .44) * envelope;
      for (const n of names.filter((n) => suffix(n) === "airframe")) {
        roots[n].position.add(new T.Vector3(x, height, 0));
      }
      robot.spinRotors(time * TAU * 1.6416667);
      return robot;
    }
    if (clip.startsWith("drive")) {
      const tracks = report.mobile.tracks, q = {};
      for (
        const left of Object.keys(tracks).filter((n) => n.endsWith("left"))
      ) {
        const right = left.slice(0, -4) + "right",
          parent = report.novel?.body_root ?? report.roots[left].parent,
          base = roots[parent];
        if (!tracks[right] || !base) continue;
        const gauge = robot.rest.get(roots[left]).position.distanceTo(
            robot.rest.get(roots[right]).position,
          ),
          yaw = clip === "drive-circle"
            ? time * TAU / 20
            : .55 * smooth((t - .22) / .14) * (1 - smooth((t - .66) / .14)),
          a = .26 * smooth(t / .18) * (1 - smooth((t - .82) / .18)),
          b = .14 * smooth((t - .40) / .10) * (1 - smooth((t - .54) / .10)),
          distance = clip === "drive-circle" ? 1.35 * yaw : a + b;
        q[left] = distance + gauge * yaw / 2;
        q[right] = distance - gauge * yaw / 2;
        base.position.add(
          clip === "drive-circle"
            ? new T.Vector3(
              1.35 * Math.sin(yaw),
              0,
              -1.35 * (1 - Math.cos(yaw)),
            )
            : new T.Vector3(a + b * Math.cos(yaw), 0, -b * Math.sin(yaw)),
        );
        base.quaternion.multiply(
          new T.Quaternion().setFromAxisAngle(new T.Vector3(0, 1, 0), yaw),
        );
      }
      robot.trackTravel(q);
      return robot;
    }
    const q = {};
    if (robot.entry.family === "humanoid_modules") {
      for (const n of names) {
        const id = suffix(n),
          v = {
            leg_hip: -.4 * curl,
            leg_knee: .8 * curl,
            leg_ankle: -.4 * curl,
            pelvis_left_yaw: .15 * s,
            pelvis_right_yaw: -.15 * s,
            pelvis_left_roll: .1 * s,
            pelvis_right_roll: -.1 * s,
          }[id];
        if (v !== undefined) q[n] = v;
      }
    }
    for (const n of names) {
      const id = suffix(n),
        limit = report.mobile?.configuration_limits?.[n] ?? specs[n].limits;
      const arm = {
        m360_yaw: .25 * s,
        m360_shoulder_pitch: -.22 + .15 * s,
        m360_upper_roll: .15 * s,
        m360_elbow_pitch: n.startsWith("drone_") ? .2 * s : .65 + .25 * s,
        m360_forearm_roll: .18 * s,
        m360_wrist_pitch: n.startsWith("drone_")
          ? -.3 + .15 * s
          : -.2 + .1 * Math.cos(t * TAU),
        m360_wrist_roll: .4 * s,
      };
      const v = arm[id] ?? ({
        camera_pan: .65 * s,
        camera_tilt: .18 * s,
        display_pan: .5 * s,
        display_tilt: .16 * s,
        antenna_hinge: .4 * curl,
        linear_carriage: .08 * s,
        linear_screw: -.08 * s / .007384615 * TAU,
        rotary_output: .5 * s,
      }[id]);
      if (v !== undefined) q[n] = limit ? T.MathUtils.clamp(v, ...limit) : v;
    }
    if (robot.ik) robot.joints(articulatedDemo(t));
    if (robot.scara) robot.scaraJoints(scara.demo(t));
    if (robot.machine) {
      robot.axes(
        gantryDemo(
          t,
          robot.machine.tool?.startsWith("extruder") ? "extruder" : "spindle",
          report.inspector?.assemblies?.[robot.entry.assembly]
            ?.tool_tip_rest_z_m,
        ).map((v, i) => T.MathUtils.clamp(v, ...robot.machine.axisLimits[i])),
      );
    }
    if (report.novel) {
      for (const [n, d] of Object.entries(report.novel.drives)) {
        if (roots[n]) {
          q[n] = T.MathUtils.clamp(
            d.angle +
              (n.includes("m360_yaw") || n.includes("elbow_pitch")
                ? .08 * s
                : 0),
            d.limits[0] + .005,
            d.limits[1] - .005,
          );
        }
      }
    }
    robot.setJoints(q);
    robot.grasp(curl);
    robot.jawGap(.044 * curl);
    return robot;
  };
  robot.play = (clip = robot.clips[0], { speed = 1, start = 0 } = {}) => {
    robot.stop();
    const update = (t) => robot.sample(clip, Math.max(0, (t - start) * speed));
    globalThis._autoRobots ??= [];
    globalThis._autoRobots.push(update);
    robot.stop = () => {
      const i = globalThis._autoRobots.indexOf(update);
      if (i >= 0) globalThis._autoRobots.splice(i, 1);
    };
    return robot;
  };
  robot.stop = () => {};
}
