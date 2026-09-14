// MIT. Sampled 3-axis relief planning in stock coordinates, +Y up, metres.
import * as T from "three/webgpu";
import { sourceGeometry } from './source_geometry.js';
const clamp = (v, a, b) => Math.max(a, Math.min(b, v));
const positive = (v, name) => {
  if (!(Number.isFinite(v) && v > 0)) throw Error(name + " must be positive");
  return v;
};

export function reliefFromMesh(source, {
  width = .078,
  depth = .128,
  stockHeight = .020,
  floor = .004,
  columns = 129,
  rows = 193,
} = {}) {
  [width, depth, stockHeight].forEach((v) => positive(v, "Relief bounds"));
  if (
    ![columns, rows].every((n) => Number.isInteger(n) && n >= 2 && n <= 513)
  ) {
    throw Error("Relief sampling dimensions must be 2..513");
  }
  if (!(floor >= 0 && floor < stockHeight)) throw Error("Invalid relief floor");
  if (!source?.isBufferGeometry && !source?.isObject3D) {
    throw Error("Expected a BufferGeometry or Object3D");
  }
  const material = new T.MeshBasicMaterial({ side: T.DoubleSide });
  const geometry = sourceGeometry(source), object = new T.Mesh(geometry, material);
  object.updateMatrixWorld(true);
  const box = new T.Box3().setFromObject(object);
  if (box.min.y < floor - 1e-6 || box.max.y > stockHeight + 1e-6) {
    throw Error(
      "Relief source must fit above its floor and below the stock top; place it in metres first",
    );
  }
  if (
    box.min.x < -width / 2 || box.max.x > width / 2 || box.min.z < -depth / 2 ||
    box.max.z > depth / 2
  ) {
    throw Error("Relief source extends outside stock");
  }
  const ray = new T.Raycaster(), heights = new Float32Array(columns * rows);
  ray.ray.direction.set(0, -1, 0);
  for (let z = 0; z < rows; z++) {
    for (let x = 0; x < columns; x++) {
      ray.ray.origin.set(
        (x / (columns - 1) - .5) * width,
        stockHeight + .01,
        (z / (rows - 1) - .5) * depth,
      );
      const hit = ray.intersectObject(object, true)[0];
      heights[z * columns + x] = hit ? Math.max(floor, hit.point.y) : floor;
    }
  }
  material.dispose();
  geometry.dispose();
  return {
    width,
    depth,
    columns,
    rows,
    heights,
    floor,
    interpretation:
      "Upper visible envelope; vertical undercuts are not reachable by this 3-axis tool",
  };
}

function sampler(source, options) {
  if (typeof source === "function") return source;
  if (source?.isBufferGeometry || source?.isObject3D) {
    source = reliefFromMesh(source, options);
  }
  const { heights, columns, rows, width, depth } = source ?? {};
  if (
    !heights || heights.length !== columns * rows || columns < 2 || rows < 2 ||
    !(width > 0 && depth > 0)
  ) {
    throw Error("Relief needs a height function, sampled heightfield, or mesh");
  }
  return (x, z) => {
    const u = clamp((x / width + .5) * (columns - 1), 0, columns - 1);
    const v = clamp((z / depth + .5) * (rows - 1), 0, rows - 1);
    const i = Math.min(columns - 2, Math.floor(u)),
      j = Math.min(rows - 2, Math.floor(v));
    const a = heights[j * columns + i], b = heights[j * columns + i + 1];
    const c = heights[(j + 1) * columns + i],
      d = heights[(j + 1) * columns + i + 1];
    return (a + (b - a) * (u - i)) * (1 - (v - j)) +
      (c + (d - c) * (u - i)) * (v - j);
  };
}

export function reliefProgram(source, options = {}) {
  const stockWidth = options.stockWidth ?? .078,
    stockDepth = options.stockDepth ?? .128;
  const stockHeight = options.stockHeight ?? .020,
    radius = options.radius ?? .003;
  const width = options.width ?? stockWidth - radius * 4;
  const depth = options.depth ?? stockDepth - radius * 4;
  const stepdown = options.stepdown ?? .003,
    roughStepover = options.roughStepover ?? radius * .8;
  const stepover = options.stepover ?? .0008,
    sampleStep = options.sampleStep ?? .001;
  const clearance = options.clearance ?? .006,
    allowance = options.roughAllowance ?? .0005;
  const tolerance = options.surfaceTolerance ?? .00005;
  for (
    const [name, v] of Object.entries({
      stockWidth,
      stockDepth,
      stockHeight,
      radius,
      width,
      depth,
      stepdown,
      roughStepover,
      stepover,
      sampleStep,
      clearance,
      allowance,
      tolerance,
    })
  ) positive(v, name);
  if (width + 2 * radius > stockWidth || depth + 2 * radius > stockDepth) {
    throw Error("Relief footprint and ball radius must stay inside the stock");
  }
  if (stepover > radius || roughStepover > radius * 1.5) {
    throw Error(
      "Relief stepover would leave unsupported strips between passes",
    );
  }
  if (sampleStep > radius || tolerance > allowance) {
    throw Error(
      "Use a sample step no larger than the tool radius and tolerance below rough allowance",
    );
  }
  const target = sampler(source, {
    width: stockWidth,
    depth: stockDepth,
    stockHeight,
    floor: options.floor,
  });
  const kernel = [[0, 0, 0]];
  for (let ring = 1; ring <= 8; ring++) {
    const r = radius * ring / 8, n = Math.max(12, ring * 8);
    for (let i = 0; i < n; i++) {
      const a = i / n * Math.PI * 2;
      kernel.push([
        Math.cos(a) * r,
        Math.sin(a) * r,
        radius - Math.sqrt(radius * radius - r * r),
      ]);
    }
  }
  const cache = new Map();
  const tip = (x, z) => {
    const key = x.toFixed(8) + "," + z.toFixed(8);
    if (cache.has(key)) return cache.get(key);
    let y = -Infinity;
    for (const [dx, dz, ballHeight] of kernel) {
      const value = target(x + dx, z + dz);
      if (
        !Number.isFinite(value) || value < .001 || value > stockHeight + 1e-7
      ) {
        throw Error(
          "Relief heights must be finite and lie 1 mm or more above the bed, within stock height",
        );
      }
      y = Math.max(y, value - ballHeight);
    }
    cache.set(key, y);
    return y;
  };
  const nx = Math.ceil(width / sampleStep),
    xAt = (i) => -width / 2 + width * i / nx;
  let minimum = stockHeight;
  const nzProbe = Math.ceil(depth / sampleStep);
  for (let j = 0; j <= nzProbe; j++) {
    for (let i = 0; i <= nx; i++) {
      minimum = Math.min(
        minimum,
        tip(xAt(i), -depth / 2 + depth * j / nzProbe),
      );
    }
  }
  if (stockHeight - minimum > (options.fluteLength ?? .018)) {
    throw Error("Relief depth exceeds the visible tool's flute length");
  }
  const points = [{ position: [0, stockHeight + clearance, 0], type: "rapid" }],
    stages = [];
  let distance = 0;
  const add = (position, type = "cut", feed) => {
    distance += Math.hypot(
      ...position.map((v, i) => v - points.at(-1).position[i]),
    );
    points.push({ position, type, ...(feed ? { feed } : {}) });
  };
  const raster = (name, level, spacing, leave) => {
    const startDistance = distance,
      startIndex = points.length,
      nz = Math.ceil(depth / spacing);
    for (let j = 0; j <= nz; j++) {
      const z = -depth / 2 + depth * j / nz, reverse = j % 2 === 1;
      const firstX = xAt(reverse ? nx : 0), prev = points.at(-1).position;
      add([prev[0], stockHeight + clearance, prev[2]], "rapid");
      add([firstX, stockHeight + clearance, z], "rapid");
      for (let k = 0; k <= nx; k++) {
        const x = xAt(reverse ? nx - k : k),
          y = Math.max(level, tip(x, z) + leave);
        add([x, y, z], "cut", k === 0 ? options.plunge ?? .003 : options.feed);
      }
    }
    stages.push({
      name,
      startDistance,
      endDistance: distance,
      startIndex,
      endIndex: points.length - 1,
    });
  };
  let level = stockHeight, pass = 0;
  while (level > minimum + allowance + 1e-7) {
    level = Math.max(minimum + allowance, level - stepdown);
    raster("rough " + (++pass), level, roughStepover, allowance);
    if (pass > 100) {
      throw Error(
        "Relief roughing exceeds 100 passes; check units and stepdown",
      );
    }
  }
  raster("finish", -Infinity, stepover, tolerance);
  const last = points.at(-1).position;
  add([last[0], stockHeight + clearance, last[2]], "rapid");
  return {
    points,
    stages,
    cutter: "ball",
    radius,
    width,
    depth,
    stockWidth,
    stockDepth,
    stockHeight,
    stepover,
    sampleStep,
    surfaceTolerance: tolerance,
    roughAllowance: allowance,
    sampling:
      "Ball footprint compensation on a finite sampled target; output stock is the actual swept cutter envelope",
    target,
  };
}

export function sampleRelief(x, z) {
  // Original Eidoverse relief: an asymmetric flowing crest on a recessed land.
  const u = x / .03, v = z / .05;
  const crest = Math.exp(-((u + .26 * Math.sin(v * 4)) ** 2 * 4 + v * v * 1.5));
  const pool = Math.exp(-((u - .45) ** 2 * 14 + (v + .38) ** 2 * 18));
  return .006 + .010 * crest - .0013 * pool;
}
