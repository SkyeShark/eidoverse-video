// MIT. G430 additive, pocket milling and 3-axis relief machining.

import * as T from "three/webgpu";
import { fitSourceGeometry } from './source_geometry.js';
import { meshSlicer } from './mesh_slices.js';
export { sourceGeometry, fitSourceGeometry } from './source_geometry.js';

import {
  attribute,
  Break,
  float,
  Fn,
  If,
  instanceIndex,
  int,
  ivec2,
  Loop,
  mix,
  normalFlat,
  positionLocal,
  storage,
  textureLoad,
  transformNormalToView,
  uniform,
  varying,
  vec2,
  vec3,
} from "three/tsl";
import { FeedPath } from "./feed_path.js";
import { FilamentPath } from "./filament_path.js";
import { indexCutterSweeps } from "./cutter_sweep.js";
import { cutterHeightNode } from "./cutter_nodes.js";
import { reliefFromMesh, reliefProgram, sampleRelief } from "./relief.js";
export { reliefFromMesh, reliefProgram, sampleRelief };
import {
  cuttingDebris,
  finishStock,
  sampleRemoval,
  stockMaterials,
  stockProfile,
} from "./cutting.js";
export { stockMaterials };

export { FeedPath };
export {rotaryCarve,rotaryProgram,rotaryMeshProgram,sampleRotary,rotarySurface} from './rotary.js';

function positive(n, name) {
  if (!(n > 0 && Number.isFinite(n))) throw Error(name + " must be positive");
  return n;
}

function intersectSpans(a,b){
  const out=[];let i=0,j=0;
  while(i<a.length&&j<b.length){
    const lo=Math.max(a[i][0],b[j][0]),hi=Math.min(a[i][1],b[j][1]);
    if(hi-lo>1e-10)out.push([lo,hi]);
    if(a[i][1]<b[j][1])i++;else j++;
  }return out;
}
function subtractSpans(a,b){
  const out=[];
  for(const [lo,hi] of a){
    let cursor=lo;
    for(const [x,z] of b){
      if(z<=cursor||x>=hi)continue;
      if(x-cursor>1e-10)out.push([cursor,Math.min(x,hi)]);
      cursor=Math.max(cursor,z);if(cursor>=hi)break;
    }
    if(hi-cursor>1e-10)out.push([cursor,hi]);
  }return out;
}

export function sliceGeometry(
  source,
  {
    size = .04,
    layerHeight = .0004,
    beadWidth = .0008,
    base = .00065,
    infill = .25,
    solidLayers = 3,
    center = [0, 0],
    travelLift = .0012,
    matrix, space, visibleOnly, maxTriangles,
  } = {},
) {
  [size, layerHeight, beadWidth, travelLift].forEach((v, i) =>
    positive(v, ["size", "layerHeight", "beadWidth", "travelLift"][i])
  );
  if (!Number.isFinite(infill) || infill < 0 || infill > 1) throw Error("Infill must be 0..1");

  if (!Number.isInteger(solidLayers) || solidLayers < 0) {
    throw Error("solidLayers must be a nonnegative integer");
  }
  const g = fitSourceGeometry(source, {size, base, center, matrix, space, visibleOnly, maxTriangles}),
    sliceAt = meshSlicer(g,{polygons:true}),
    points = [],
    contours = [];
  const slices=[],heights=[];
  try{
    for(let y=base+layerHeight/2;y<g.boundingBox.max.y-1e-10;y+=layerHeight){heights.push(y);slices.push(sliceAt(y));}
  }catch(e){g.dispose();throw e;}
  let cursor = null, layers = 0;
  const add = (v, type) => {
    const position = v.toArray();
    if (!cursor || cursor.distanceToSquared(v) > 1e-16) {
      points.push({ position, type });
      cursor = v.clone();
    }
  };

  const travel = (v) => {
    if (cursor) {
      const h = Math.max(cursor.y, v.y) + travelLift;
      add(new T.Vector3(cursor.x, h, cursor.z), "rapid");
      add(new T.Vector3(v.x, h, v.z), "rapid");
    }
    add(v, "rapid");
  };

  for (let index=0;index<slices.length;index++) {
    const y=heights[index],rings = slices[index].flatMap(p=>p);
    if (!rings.length) continue;
    const loops = rings.map(r => r.map(([x,z]) => new T.Vector3(x,y,z)));
    const segs = loops.flatMap(loop => loop.slice(1).map((b,i) => [loop[i],b]));
    layers++;
    for (const loop of loops) {
        contours.push({ layer: layers, points: loop.map((v) => v.toArray()) });
        const path = loop.map((v) => v.clone().setY(y + layerHeight / 2));
        travel(path[0]);
        path.slice(1).forEach((v) => add(v, "extrude"));
    }

    // Compare the exact horizontal intervals at each hatch row. This avoids
    // unstable 2D Boolean operations between almost-coincident curved slices.
    // A column gets sparse fill only if it continues through all skin layers.
    const continuing=[];
    for(let offset=-solidLayers;offset<=solidLayers&&solidLayers;offset++){
      const rings=(slices[index+offset]??[]).flatMap(p=>p);
      continuing.push(rings.flatMap(r=>r.slice(1).map((b,i)=>[{x:r[i][0],z:r[i][1]},{x:b[0],z:b[1]}])));
    }
    if (infill > 0 || solidLayers) {
      const alongX = layers % 2 === 0,
        lo = alongX ? g.boundingBox.min.z : g.boundingBox.min.x,
        hi = alongX ? g.boundingBox.max.z : g.boundingBox.max.x;
      const intervals=(segments,s,inset=0)=>{
        const hits = [];
        for (const [a, b] of segments) {
          const u = alongX ? a.z : a.x, v = alongX ? b.z : b.x;
          if ((u <= s && v > s) || (v <= s && u > s)) {
            hits.push(
              (alongX ? a.x : a.z) +
                ((alongX ? b.x : b.z) - (alongX ? a.x : a.z)) * (s - u) /
                  (v - u),
            );
          }
        }
        hits.sort((a, b) => a - b);
        if (hits.length % 2) throw Error("Odd infill intersections");
        const spans = [];
        for (let j = 0; j < hits.length; j += 2) {
          if (hits[j + 1] - hits[j] > Math.max(1e-10,inset*2)) {
            spans.push([
              hits[j] + inset,
              hits[j + 1] - inset,
            ]);
          }
        }
        return spans;
      };
      let row=0;
      for (let s=lo+beadWidth;s<hi;s+=beadWidth,row++){
        const full=intervals(segs,s,beadWidth*.75);
        const sparseRow=Math.floor((row+1)*infill+1e-8)>Math.floor(row*infill+1e-8);
        // Dense skins stop at the real outer/hole perimeter, but need no gap
        // at the boundary with internal sparse fill. Avoid double deposition.
        let spans=full;
        if(!sparseRow){
          if(!solidLayers)spans=[];
          else{
            let core=full;
            for(const neighbour of continuing){core=intersectSpans(core,intervals(neighbour,s));if(!core.length)break;}
            spans=subtractSpans(full,core);
          }
        }
        if (row % 2) spans.reverse().forEach((s) => s.reverse());

        for (const [a, b] of spans) {
          const v = alongX
              ? new T.Vector3(a, y + layerHeight / 2, s)
              : new T.Vector3(s, y + layerHeight / 2, a),
            w = alongX
              ? new T.Vector3(b, y + layerHeight / 2, s)
              : new T.Vector3(s, y + layerHeight / 2, b);
          travel(v);
          add(w, "extrude");
        }
      }
    }
  }

  if (!layers) throw Error("Geometry is shorter than half a layer");
  if (cursor) add(cursor.clone().add(new T.Vector3(0, travelLift, 0)), "rapid");
  g.dispose();
  return { points, layers, contours, layerHeight, beadWidth, base, source: g.userData.manufacturingSource };
}

function chords(path, maxLength = .001) {
  const pieces = [];
  for (const s of path.segments) {
    const count = s.kind === "arc"
      ? Math.max(2, Math.ceil(s.length / maxLength), Math.ceil(s.angle / .1))
      : 1;
    let a = new T.Vector3(...s.a);
    for (let j = 1; j <= count; j++) {
      const f = j / count,
        b = s.kind === "line"
          ? new T.Vector3(...s.b)
          : new T.Vector3(...s.a).sub(new T.Vector3(...s.center))
            .applyAxisAngle(new T.Vector3(...s.normal), s.angle * f).add(
              new T.Vector3(...s.center),
            );
      pieces.push({
        a: a.clone(),
        b: b.clone(),
        start: s.distance0 + s.length * (j - 1) / count,
        end: s.distance0 + s.length * f,
        type: s.type,
      });
      a = b;
    }
  }
  return pieces;
}

function validateMachine(machine, points, kind, { radius = 0 } = {}) {
  if (!machine.machine?.tool || !machine.moveTool) {
    throw Error("Fabrication needs the assembled G430 FDM or CNC machine");
  }
  const required = kind === "print" ? "extruder_fixed" : "spindle_fixed";
  if (machine.machine.tool !== required) {
    throw Error("Wrong process head: expected " + required);
  }

  const bb = machine.machine.bedBounds;
  for (const { position: p, type } of points) {
    const q = machine.machine.toAxes(p);
    q.forEach((v, i) => {
      const l = machine.machine.axisLimits[i];
      if (!Number.isFinite(v) || v < l[0] - 1e-7 || v > l[1] + 1e-7) {
        throw Error(
          `Toolpath exceeds G430 ${["X", "Y", "Z"][i]} travel at ${p}`,
        );
      }
    });
    if (
      type !== "rapid" &&
      (p[0] - radius < bb[0] || p[0] + radius > bb[1] ||
        -p[2] - radius < bb[2] || -p[2] + radius > bb[3])
    ) throw Error("Process path exceeds the physical bed");
  }
}

function makeJob(machine, path, mesh, options = {}) {
  machine.stop();
  const owner = machine.roots.gantry_base;
  mesh.position.y = machine.machine.bedTop;
  owner.add(mesh);
  let callbackDone = false;

  const duration = options.duration ?? path.duration;
  positive(duration, "duration");
  const job = {
    machine,
    path,
    mesh,
    duration,
    physicalDuration: path.duration,
    time: 0,
    done: false,
    state: null,
  };

  job.seek = (seconds) => {
    if (!Number.isFinite(seconds)) throw Error("Job time must be finite");
    const t = T.MathUtils.clamp(seconds, 0, duration),
      state = path.sample(t / duration * path.duration);
    machine.moveTool(state.position);
    mesh.userData.progress.value = state.distance;
    job.time = t;
    job.done = t >= duration;
    job.state = { ...state, playbackTime: t, physicalTime: state.time };
    if (state.filamentLength !== undefined) {
      machine.filament?.seek(state.filamentLength, state.filamentRetraction);
      machine.coolingFan?.(state.time, { rpm: options.fanRpm ?? 4800 });
    }
    job.effects?.setTime(state.time);
    if (machine.roots.spindle_rotor) {
      const r = machine.roots.spindle_rotor, rest = machine.rest.get(r);
      r.quaternion.copy(rest.quaternion).multiply(
        new T.Quaternion().setFromAxisAngle(
          new T.Vector3(0, 1, 0),
          state.time * (options.rpm ?? 1800) / 60 * Math.PI * 2,
        ),
      );
    }
    if (t < duration) callbackDone = false;
    if (job.done && !callbackDone) {
      callbackDone = true;
      options.onDone?.(job);
    }
    return job.state;
  };

  job.play = ({ start = 0, speed = 1 } = {}) => {
    job.stop();
    const update = (t) => job.seek((t - start) * speed);
    globalThis._autoRobots ??= [];
    globalThis._autoRobots.push(update);
    job.stop = () => {
      const i = globalThis._autoRobots.indexOf(update);
      if (i >= 0) globalThis._autoRobots.splice(i, 1);
    };
    return job;
  };
  job.stop = () => {};

  job.dispose = () => {
    job.stop();
    mesh.removeFromParent();
    mesh.geometry.dispose();
    mesh.material.dispose();
  };
  job.seek(0);
  if (options.autoPlay) job.play({ start: options.start ?? 0 });
  return job;
}

export function print(machine, source, options = {}) {
  if (options.fanRpm !== undefined && (!Number.isFinite(options.fanRpm) || options.fanRpm < 0)) {
    throw Error("fanRpm must be finite and nonnegative");
  }
  const surface = machine.roots.fdm_build_plate;
  const base = source?.base ?? options.base ?? .00065;
  if (options.buildPlate !== false) {
    if (!surface) {
      throw Error("The FDM assembly needs its authored build surface");
    }
    if (
      Math.abs(base - .00065) > 1e-7 ||
      (options.plateWidth !== undefined &&
        Math.abs(options.plateWidth - .458) > 1e-7) ||
      (options.plateDepth !== undefined &&
        Math.abs(options.plateDepth - .528) > 1e-7)
    ) {
      throw Error(
        "The removable PEI sheet is 458 x 528 x 0.65 mm on the original 450 x 520 mm bed; use buildPlate:false for a custom fixture",
      );
    }
  }
  if (
    machine.filament && options.filamentDiameter !== undefined &&
    Math.abs(options.filamentDiameter - machine.filament.diameter) > 1e-9
  ) {
    throw Error(
      "filamentDiameter must match the loaded reel's 1.75 mm filament",
    );
  }
  const spec = source?.points ? source : sliceGeometry(source, options),
    layerHeight = options.layerHeight ?? spec.layerHeight ?? .0004,
    beadWidth = options.beadWidth ?? spec.beadWidth ?? .0008;

  validateMachine(machine, spec.points, "print", { radius: beadWidth / 2 });
  if (
    options.buildPlate !== false &&
    spec.points.some((p) =>
      p.type === "extrude" &&
      (Math.abs(p.position[0]) + beadWidth / 2 > .224 ||
        p.position[2] - beadWidth / 2 < -.245 ||
        p.position[2] + beadWidth / 2 > .273)
    )
  ) {
    throw Error("Print exceeds the unobstructed area of the PEI sheet");
  }
  const geometricPath = new FeedPath(spec.points, {
    feed: options.feed ?? .025,
    rapid: options.rapid ?? .10,
    acceleration: options.acceleration ?? .5,
    beadArea: Math.PI * beadWidth * layerHeight / 4,
    blendTolerance: options.blendTolerance ?? .000015,
  });

  const path = new FilamentPath(geometricPath, options);
  if (machine.filament && path.filamentLength > machine.filament.capacity) {
    throw Error("The reel has insufficient filament for this print");
  }
  const arrays = {
      position: [],
      normal: [],
      fabA: [],
      fabB: [],
      fabOffset: [],
      fabBounds: [],
      fabEnd: [],
    },
    indices = [];

  for (
    const s of chords(path, beadWidth * .4).filter((s) => s.type === "extrude")
  ) {
    if (Math.abs(s.a.y - s.b.y) > 1e-6) {
      throw Error(
        "FDM extrusion must lie within a layer; use rapid for Z travel",
      );
    }
    const d = s.b.clone().sub(s.a).normalize(),
      side = new T.Vector3(-d.z, 0, d.x),
      base = arrays.position.length / 3;

    for (let end = 0; end < 2; end++) {
      for (let j = 0; j < 8; j++) {
        const a = j * Math.PI / 4,
          off = side.clone().multiplyScalar(Math.cos(a) * beadWidth / 2).add(
            new T.Vector3(
              0,
              Math.sin(a) * layerHeight / 2 - layerHeight / 2,
              0,
            ),
          ),
          normal = side.clone().multiplyScalar(Math.cos(a) / beadWidth).add(
            new T.Vector3(0, Math.sin(a) / layerHeight, 0),
          ).normalize();
        arrays.position.push(...(end ? s.b : s.a).clone().add(off).toArray());
        arrays.normal.push(...normal.toArray());
        arrays.fabA.push(...s.a.toArray());
        arrays.fabB.push(...s.b.toArray());
        arrays.fabOffset.push(...off.toArray());
        arrays.fabBounds.push(s.start, s.end);
        arrays.fabEnd.push(end);
      }
    }

    for (let j = 0; j < 8; j++) {
      const k = (j + 1) % 8;
      indices.push(
        base + j,
        base + k,
        base + 8 + k,
        base + j,
        base + 8 + k,
        base + 8 + j,
      );
    }
    for (let j = 1; j < 7; j++) {
      indices.push(
        base,
        base + j + 1,
        base + j,
        base + 8,
        base + 8 + j,
        base + 8 + j + 1,
      );
    }
  }

  // This cross-section is clockwise along the extrusion direction. The
  // visible outside must agree with the authored outward vertex normals.
  for (let i = 0; i < indices.length; i += 3) {
    [indices[i + 1], indices[i + 2]] = [indices[i + 2], indices[i + 1]];
  }
  const g = new T.BufferGeometry();
  for (const [n, a] of Object.entries(arrays)) {
    g.setAttribute(
      n,
      new T.Float32BufferAttribute(
        a,
        n === "fabBounds" ? 2 : n === "fabEnd" ? 1 : 3,
      ),
    );
  }
  g.setIndex(indices);
  g.computeBoundingSphere();
  const progress = uniform(-1),
    bounds = attribute("fabBounds", "vec2"),
    f = progress.sub(bounds.x).div(bounds.y.sub(bounds.x)).clamp(0, 1),
    m = new T.MeshStandardNodeMaterial({
      color: options.color ?? machine.filament?.color ?? 0x278b79,
      roughness: .4,
      metalness: 0,
      alphaTest: .5,
    });
  m.positionNode = mix(
    attribute("fabA", "vec3"),
    attribute("fabB", "vec3"),
    f.mul(attribute("fabEnd", "float")),
  ).add(attribute("fabOffset", "vec3"));
  m.opacityNode = progress.sub(bounds.x).greaterThan(1e-9).select(1, 0);

  const mesh = new T.Mesh(g, m);
  mesh.name = "FDM deposited bead";
  mesh.castShadow = mesh.receiveShadow = true;
  mesh.frustumCulled = false;
  mesh.userData.progress = progress;

  const job = makeJob(machine, path, mesh, options);
  job.layers = spec.layers;
  job.extrudedVolume = path.volume;
  job.filamentLength = path.filamentLength;
  job.setColor = (color) => {
    m.color.set(color);
    machine.filament?.setColor(color);
    return job;
  };
  job.setColor(options.color ?? machine.filament?.color ?? 0x278b79);
  const unbindColor = machine.filament?.bindMaterial(m);
  const printDispose = job.dispose;
  job.dispose = () => {
    unbindColor?.();
    printDispose();
  };
  job.base = spec.base ?? options.base ?? .00065;

  if (surface) surface.visible = options.buildPlate !== false;
  if (options.buildPlate !== false) job.plate = surface;

  return job;
}

export function pocketProgram(
  {
    width = .048,
    depth = .080,
    stockHeight = .020,
    cutDepth = .010,
    stepdown = .002,
    stepover = .0025,
    radius = .003,
    clearance = .012,
    plunge = .001,
  } = {},
) {
  [
    width,
    depth,
    stockHeight,
    cutDepth,
    stepdown,
    stepover,
    radius,
    clearance,
    plunge,
  ]
    .forEach((v, i) => positive(v, "pocket parameter " + i));
  if (width <= 2 * radius || depth <= 2 * radius || cutDepth >= stockHeight) {
    throw Error("Invalid pocket dimensions");
  }

  const points = [{ position: [0, stockHeight + clearance, 0], type: "rapid" }],
    x0 = -width / 2 + radius,
    x1 = width / 2 - radius,
    z0 = -depth / 2 + radius,
    z1 = depth / 2 - radius;

  for (
    let cut = Math.min(stepdown, cutDepth);;
    cut = Math.min(cut + stepdown, cutDepth)
  ) {
    const y = stockHeight - cut, prev = points.at(-1).position;
    points.push(
      { position: [prev[0], stockHeight + clearance, prev[2]], type: "rapid" },
      { position: [x0, stockHeight + clearance, z0], type: "rapid" },
      { position: [x0, y, z0], type: "cut", feed: plunge },
    );
    let row = 0;

    for (let z = z0;; z = Math.min(z + stepover, z1)) {
      const a = row % 2 ? x1 : x0, b = row % 2 ? x0 : x1;
      points.push({ position: [a, y, z], type: "cut" }, {
        position: [b, y, z],
        type: "cut",
      });
      row++;
      if (z >= z1 - 1e-9) break;
    }

    if (cut >= cutDepth - 1e-9) break;
  }

  const last = points.at(-1).position;
  points.push({
    position: [last[0], stockHeight + clearance, last[2]],
    type: "rapid",
  });
  return points;
}

export function mill(machine, points, options = {}) {
  const cutter = options.cutter ?? machine.machine?.cutter?.kind ?? "flat";
  if (!["flat", "ball"].includes(cutter)) {
    throw Error("Cutter must be flat or ball");
  }
  if (cutter !== (machine.machine?.cutter?.kind ?? "flat")) {
    throw Error(
      "The requested cutter profile does not match the fitted tool; load the CNC relief assembly for a ball nose",
    );
  }
  const profile = stockProfile(options.material ?? "aluminum");
  options = {
    feed: profile.feed,
    plunge: profile.plunge,
    rpm: profile.rpm,
    stepdown: profile.stepdown,
    cutDepth: profile.cutDepth,
    ...options,
  };
  positive(options.rpm, "spindle rpm");
  if (!Number.isInteger(options.flutes ?? 2) || (options.flutes ?? 2) < 1) {
    throw Error("flutes must be a positive integer");
  }
  const radius = options.radius ?? .003,
    width = options.stockWidth ?? .078,
    depth = options.stockDepth ?? .128,
    height = options.stockHeight ?? .020,
    resolution = options.resolution ?? 128;

  [radius, width, depth, height].forEach((v, i) =>
    positive(v, "stock parameter " + i)
  );
  if (Math.abs(radius - (machine.machine?.cutter?.radius ?? .003)) > 1e-8) {
    throw Error(
      "The installed G430 end mill has a 3 mm radius; cutter geometry and removal radius must match",
    );
  }
  const fittedFluteLength = machine.machine?.cutter?.fluteLength ?? .018;
  const fluteLength = options.fluteLength ?? fittedFluteLength;
  positive(fluteLength, "flute length");
  if (fluteLength > fittedFluteLength + 1e-8) {
    throw Error("Flute length exceeds the exposed length of the fitted cutter");
  }
  const bed = machine.machine?.bedBounds;
  if (
    bed &&
    (-width / 2 < bed[0] || width / 2 > bed[1] || -depth / 2 < bed[2] ||
      depth / 2 > bed[3])
  ) throw Error("Stock extends beyond the physical bed");
  const clamps = Object.entries(machine.roots).filter(([name]) =>
    name.startsWith("cnc_clamp_")
  );
  if (clamps.length) {
    const fitted = Math.abs(width - .078) < 1e-7 && depth >= .108 &&
      depth <= .148 && height >= .015;
    if (options.workholding !== false && !fitted) {
      throw Error(
        "The fitted toe clamps seat a 78 mm wide stock, 108..148 mm deep and at least 15 mm high; use workholding:false with your own fixture",
      );
    }
  }
  if (!Number.isInteger(resolution) || resolution < 16 || resolution > 512) {
    throw Error("Stock resolution must be 16..512");
  }

  points = points ?? pocketProgram({ ...options, stockHeight: height, radius });
  validateMachine(machine, points, "mill", { radius });

  const path = new FeedPath(points, {
      feed: options.feed ?? .012,
      rapid: options.rapid ?? .08,
      acceleration: options.acceleration ?? .25,
      blendTolerance: 0,
    }),
    cuts = chords(path).filter((s) => s.type === "cut");

  if (!cuts.length) throw Error("Milling path has no cutting moves");
  for (const s of cuts) {
    if (Math.min(s.a.y, s.b.y) < 0) {
      throw Error("Cutter would enter the machine bed");
    }
  }

  const removal = sampleRemoval(path, {
    width,
    depth,
    height,
    radius,
    resolution,
    fluteLength,
    cutter,
  });
  // A static float texture supports indexed reads on both WebGPU and Three's
  // browser WebGL fallback. Storage attributes lose random indexing there.
  const pathWidth = 512, pathRows = Math.max(1, Math.ceil(cuts.length / 256));
  const data = new Float32Array(pathWidth * pathRows * 4);
  cuts.forEach((s, i) =>
    data.set([...s.a.toArray(), s.start, ...s.b.toArray(), s.end], i * 8)
  );
  const cutTexture = new T.DataTexture(
    data,
    pathWidth,
    pathRows,
    T.RGBAFormat,
    T.FloatType,
  );
  // A sampled data resource, never a render target. The native backend uses
  // this label to keep the Float32 upload format without render-attachment usage.
  cutTexture.name = "eidoverse/data/cutter-path";
  cutTexture.needsUpdate = true;
  const binning = indexCutterSweeps(cuts, width, depth, radius);
  const binTexture = new T.DataTexture(
    binning.headers,
    binning.tiles,
    binning.tiles,
    T.RGBAFormat,
    T.FloatType,
  );
  const indexRows = Math.max(1, Math.ceil(binning.indices.length / 256));
  const indexData = new Float32Array(256 * indexRows * 4);
  binning.indices.forEach((value, i) => indexData[i * 4] = value);
  const indexTexture = new T.DataTexture(
    indexData,
    256,
    indexRows,
    T.RGBAFormat,
    T.FloatType,
  );
  binTexture.name = "eidoverse/data/cutter-spatial-bins";
  indexTexture.name = "eidoverse/data/cutter-spatial-indices";
  binTexture.needsUpdate = indexTexture.needsUpdate = true;
  const progress = uniform(-1);
  const positions = [], uv = [], top = [], indices = [], n = resolution + 1;
  for (let z = 0; z < n; z++) {
    for (let x = 0; x < n; x++) {
      positions.push(
        (x / resolution - .5) * width,
        height,
        (z / resolution - .5) * depth,
      );
      uv.push(x / resolution, z / resolution);
      top.push(1);
    }
  }
  for (let z = 0; z < resolution; z++) {
    for (let x = 0; x < resolution; x++) {
      const a = z * n + x;
      indices.push(a, a + n, a + 1, a + 1, a + n, a + n + 1);
    }
  }

  const border = [];
  for (let x = 0; x < n; x++) border.push(x);
  for (let z = 1; z < n; z++) border.push(z * n + resolution);
  for (let x = resolution - 1; x >= 0; x--) border.push(resolution * n + x);
  for (let z = resolution - 1; z > 0; z--) border.push(z * n);

  const bottom = [];
  for (const i of border) {
    bottom.push(positions.length / 3);
    positions.push(positions[i * 3], 0, positions[i * 3 + 2]);
    uv.push(0, 0);
    top.push(0);
  }
  for (let i = 0; i < border.length; i++) {
    const j = (i + 1) % border.length;
    indices.push(
      border[i],
      border[j],
      bottom[j],
      border[i],
      bottom[j],
      bottom[i],
    );
  }
  for (let i = 1; i < bottom.length - 1; i++) {
    indices.push(bottom[0], bottom[i], bottom[i + 1]);
  }

  const g = new T.BufferGeometry();
  g.setAttribute("position", new T.Float32BufferAttribute(positions, 3));
  g.setAttribute("uv", new T.Float32BufferAttribute(uv, 2));
  g.setAttribute("fabTop", new T.Float32BufferAttribute(top, 1));
  g.setIndex(indices);
  g.computeVertexNormals();
  g.computeBoundingSphere();

  const m = new T.MeshStandardNodeMaterial({
    color: options.color ?? profile.color,
    roughness: profile.roughness,
    metalness: profile.metalness,
  });

  const envelope = cutterHeightNode(radius, cutter);
  const heightAt = Fn(([xz]) => {
    const h = float(height).toVar();
    const bx = int(
      xz.x.div(width).add(.5).mul(binning.tiles).floor().clamp(
        0,
        binning.tiles - 1,
      ),
    );
    const bz = int(
      xz.y.div(depth).add(.5).mul(binning.tiles).floor().clamp(
        0,
        binning.tiles - 1,
      ),
    );
    const bin = textureLoad(binTexture, ivec2(bx, bz));
    Loop({ start: int(0), end: int(bin.y), type: "int" }, ({ i }) => {
      const address = int(bin.x).add(i);
      const segment = int(
        textureLoad(indexTexture, ivec2(address.mod(256), address.div(256))).x,
      );
      const a = textureLoad(
          cutTexture,
          ivec2(segment.mod(256).mul(2), segment.div(256)),
        ),
        b = textureLoad(
          cutTexture,
          ivec2(segment.mod(256).mul(2).add(1), segment.div(256)),
        );
      If(progress.lessThan(a.w), () => Break());
      If(progress.greaterThan(a.w), () => {
        const f = progress.sub(a.w).div(b.w.sub(a.w)).clamp(0, 1),
          end = mix(a.xyz, b.xyz, f);
        const candidate = envelope(xz, a.xyz, end);
        h.assign(h.min(candidate));
      });
    });
    return h;
  });
  m.positionNode = vec3(
    positionLocal.x,
    heightAt(positionLocal.xz).mul(attribute("fabTop", "float")),
    positionLocal.z,
  );
  m.normalNode = normalFlat;
  if (cutter === "ball") {
    // Filter normals at the stock grid's physical sampling scale. Sampling a
    // sub-grid scallop's instantaneous normal aliases into broad false stripes.
    // Keep discontinuous roughing walls and stock sides geometrically shaded.
    const dx = 2 * width / resolution, dz = 2 * depth / resolution;
    const xz = positionLocal.xz;
    const slope = vec3(
      heightAt(xz.sub(vec2(dx, 0))).sub(heightAt(xz.add(vec2(dx, 0)))).div(
        2 * dx,
      ),
      1,
      heightAt(xz.sub(vec2(0, dz))).sub(heightAt(xz.add(vec2(0, dz)))).div(
        2 * dz,
      ),
    );
    const curved = transformNormalToView(varying(slope, "cutterSurfaceNormal"))
      .normalize();
    const topFace = varying(attribute("fabTop", "float"), "cutterTopFace");
    m.normalNode = topFace.greaterThan(.9999).and(
      curved.dot(normalFlat).greaterThan(.65),
    ).select(curved, normalFlat);
  }
  const finish = finishStock(m, m.positionNode, profile, options.color);

  const mesh = new T.Mesh(g, m);
  mesh.name = cutter === "ball"
    ? "CNC swept ball-nose relief stock"
    : "CNC swept flat-end stock";
  mesh.castShadow = mesh.receiveShadow = true;
  mesh.frustumCulled = false;
  mesh.userData.progress = progress;
  const job = makeJob(machine, path, mesh, options);
  job.stock = {
    width,
    depth,
    height,
    resolution,
    cellSize: [width / resolution, depth / resolution],
    radius,
    cutter,
  };
  job.cutSegments = cuts;
  job.stock.material = profile.id;
  job.stock.removedVolume = removal.removedVolume;
  job.stock.removalCellSize = removal.cellSize;
  job.workholding = clamps.map(([, root]) => root);
  const clampVisibility = job.workholding.map((root) => root.visible);
  job.workholding.forEach((root) => {
    root.visible = options.workholding !== false;
  });
  job.settings = {
    material: profile.id,
    rpm: options.rpm,
    feed: options.feed,
    plunge: options.plunge,
    stepdown: options.stepdown,
    cutterDiameter: radius * 2,
    cutter,
    flutes: options.flutes ?? 2,
    chipLoad: options.feed * 60 / (options.rpm * (options.flutes ?? 2)),
  };
  job.setColor = (color) => {
    finish.setColor(color);
    return job;
  };
  job.removal = removal;
  if (options.effects !== false) {
    job.effects = cuttingDebris(
      removal,
      profile,
      job.stock,
      typeof options.effects === "object" ? options.effects : {},
    );
    machine.roots.gantry_base.add(job.effects.group);
    job.effects.group.position.y = machine.machine.bedTop;
    job.effects.setTime(0);
  }

  job.inspectHeights = async (renderer, pointsXZ) => {
    const input = new T.StorageBufferAttribute(
        new Float32Array(pointsXZ.flatMap(([x, z]) => [x, 0, z, 0])),
        4,
      ),
      output = new T.StorageBufferAttribute(
        new Float32Array(pointsXZ.length),
        1,
      ),
      a = storage(input, "vec4", pointsXZ.length).toReadOnly(),
      b = storage(output, "float", pointsXZ.length),
      compute = Fn(() => {
        b.element(instanceIndex).assign(heightAt(a.element(instanceIndex).xz));
      })().compute(pointsXZ.length);
    await renderer.computeAsync(compute);
    const values = new Float32Array(await renderer.getArrayBufferAsync(output));
    compute.dispose();
    return Array.from(values);
  };

  const dispose = job.dispose;
  job.dispose = () => {
    dispose();
    cutTexture.dispose();
    binTexture.dispose();
    indexTexture.dispose();
    job.effects?.dispose();
    job.workholding.forEach((root, i) => {
      root.visible = clampVisibility[i];
    });
  };
  return job;
}
export function carve(machine, source, options = {}) {
  if (Array.isArray(source) || !source) return mill(machine, source, options);
  const material = options.material ?? "wood", profile = stockProfile(material);
  options = {
    feed: profile.feed,
    plunge: profile.plunge,
    stepdown: profile.stepdown,
    fluteLength: machine.machine?.cutter?.fluteLength,
    ...options,
    material,
    cutter: "ball",
  };
  const program = reliefProgram(source, options);
  const job = mill(machine, program.points, options);
  job.program = program;
  const seek = job.seek;
  job.seek = (time) => {
    const state = seek(time);
    state.stage =
      program.stages.find((s) => state.distance <= s.endDistance)?.name ??
        "retract";
    return state;
  };
  job.seek(0);
  return job;
}
