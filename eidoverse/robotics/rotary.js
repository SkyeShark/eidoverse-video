// MIT. Freestanding rotary carving on the G430 XYZ + A assembly.
import * as T from "three/webgpu";
import {
  RotaryPath,
  rotaryProgram,
  rotaryMeshProgram,
  rotarySurface,
  sampleRotary,
  sweepDistance,
} from "./rotary_path.js";
import { createRotaryStock } from "./rotary_stock.js";
import { rotaryRemoval } from "./rotary_removal.js";
import { cuttingDebris, stockProfile } from "./cutting.js";
import { rotaryFixtureSetup } from "./rotary_setup.js";
export { RotaryPath, rotaryProgram, rotaryMeshProgram, rotarySurface, sampleRotary };

export function rotaryCarve(machine, source = sampleRotary, options = {}) {
  if (!machine.roots.rotary_chuck || !machine.roots.rotary_output) {
    throw Error("Load cnc_rotary for rotary carving");
  }
  if (!['flat','ball'].includes(machine.machine?.cutter?.kind)) {
    throw Error("Rotary carving requires a fitted flat or ball-nose cutter");
  }
  if (!machine.rotarySetup) throw Error("Load the adjustable rotary fixture");
  const setup = rotaryFixtureSetup(options);
  const cutter = machine.machine.cutter;
  if(options.tool && options.tool !== cutter.kind)throw Error('Requested tool must match the installed cutter');
  const program = rotaryProgram(source, {...options,tool:cutter.kind,fluteLength:cutter.fluteLength??(cutter.kind==='flat'?.018:.017)}),
    s = program.settings,
    path = program.path;
  const duration = options.duration ?? path.duration;
  if (!(duration > 0 && Number.isFinite(duration))) {
    throw Error("Invalid job duration");
  }
  if (
    Math.abs(s.axisX - setup.axisX) > 1e-9 ||
    s.axisHeight !== setup.axisHeight ||
    s.start < setup.start - 1e-9 || s.end > setup.end + 1e-9
  ) {
    throw Error(
      "Toolpath must retain the calibrated rotary axis and sacrificial end stock",
    );
  }
  if (Math.abs(s.radius - machine.machine.cutter.radius) > 1e-9) {
    throw Error("Cutter radius must match the installed tool");
  }
  for (const v of program.moves) {
    const p = [
        v.position[0] + s.axisX,
        v.position[1] + s.axisHeight,
        v.position[2],
      ],
      q = machine.machine.toAxes(p);
    q.forEach((a, k) => {
      if (
        a < machine.machine.axisLimits[k][0] - 1e-7 ||
        a > machine.machine.axisLimits[k][1] + 1e-7
      ) {
        throw Error(
          "Rotary toolpath exceeds " + ["X", "Y", "Z"][k] + " travel",
        );
      }
    });
    if (
      v.type === "index" &&
      v.position[1] < Math.hypot(s.stockWidth / 2, s.stockHeight / 2) + .002
    ) throw Error("Retract clear of the rotating stock before indexing");
  }
  if (!options.renderer?.hasInitialized?.()) {
    throw Error("Initialize the scene renderer before rotaryCarve");
  }
  machine.rotarySetup(options);
  const owner = machine.roots.gantry_base, stockFrame = new T.Group();
  stockFrame.position.set(s.axisX, machine.machine.bedTop + s.axisHeight, 0);
  const removal = rotaryRemoval(path, s, {
    resolution: options.engagementResolution,
  });
  const volume = createRotaryStock(path, s, { ...options, parent: stockFrame });
  const debris = cuttingDebris(removal, stockProfile(s.material), {
    width: s.stockLength,
    depth: s.stockWidth,
    height: s.axisHeight + s.stockHeight,
    radius: s.radius,
  }, options);
  debris.group.position.y = machine.machine.bedTop;
  owner.add(debris.group);
  owner.add(stockFrame);
  // Stock remains held by the chuck even when a paused job is turned manually.
  const followChuck = () => {
    stockFrame.rotation.x = (machine.state.rotary_chuck ?? 0) % (2 * Math.PI);
  };
  machine.poseCallbacks.add(followChuck);
  machine.stop();
  let callback = false;
  const job = {
    machine,
    program,
    path,
    stock: volume,
    mesh: stockFrame,
    removal,
    debris,
    settings: s,
    duration,
    physicalDuration: path.duration,
    time: 0,
    state: null,
    done: false,
    seek(seconds) {
      if (!Number.isFinite(seconds)) throw Error("Job time must be finite");
      const t = T.MathUtils.clamp(seconds, 0, duration),
        state = path.sample(t / duration * path.duration);
      const p = [
        state.position[0] + s.axisX,
        state.position[1] + s.axisHeight,
        state.position[2],
      ];
      machine.moveTool(p);
      machine.setJoints({
        rotary_output: state.angle,
        rotary_chuck: state.angle,
      });
      volume.update(state);
      debris.setTime(state.time);
      const rotor = machine.roots.spindle_rotor, rest = machine.rest.get(rotor);
      rotor.quaternion.copy(rest.quaternion).multiply(
        new T.Quaternion().setFromAxisAngle(
          new T.Vector3(0, 1, 0),
          (state.time * s.rpm / 60 * 2 * Math.PI) % (2 * Math.PI),
        ),
      );
      job.state = {
        ...state,
        position: p,
        stockPosition: state.position,
        physicalTime: state.time,
        playbackTime: t,
      };
      job.time = t;
      job.done = t >= duration;
      if (!job.done) callback = false;
      if (job.done && !callback) {
        callback = true;
        options.onDone?.(job);
      }
      return job.state;
    },
    play({ start = 0, speed = 1 } = {}) {
      job.stop();
      const update = (t) => job.seek((t - start) * speed);
      globalThis._autoRobots ??= [];
      globalThis._autoRobots.push(update);
      job.stop = () => {
        const i = globalThis._autoRobots.indexOf(update);
        if (i >= 0) globalThis._autoRobots.splice(i, 1);
      };
      return job;
    },
    stop() {},
    dispose() {
      job.stop();
      machine.poseCallbacks.delete(followChuck);
      debris.dispose();
      volume.dispose();
      stockFrame.removeFromParent();
    },
  };
  job.seek(0);
  if (options.autoPlay) job.play();
  return job;
}
