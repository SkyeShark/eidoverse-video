// MIT. Indexed XYZ + A milling. Stock coordinates: X along the rotary axis.
import * as T from "three/webgpu";
import { stockProfile } from "./cutting.js";
import { rotaryMeshProgram } from './rotary_mesh.js';
export { rotaryMeshProgram };
const TAU = 2 * Math.PI;

// The mounted blank is prepared with a 60-degree centre-drilled seat and a
// narrower pilot for tip relief. This is workholding preparation, not a cut
// performed by the ball-end program. Dimensions match the supplied live centre.
export const CENTRE_SEAT = Object.freeze({
  depth: .003,
  halfAngle: Math.PI / 6,
  pilotRadius: .0008,
  pilotDepth: .006,
});
export function rotaryBlankDistance(p, settings) {
  const { stockLength: L, stockHeight: H, stockWidth: W } = settings;
  const q = [
    Math.abs(p[0]) - L / 2,
    Math.abs(p[1]) - H / 2,
    Math.abs(p[2]) - W / 2,
  ];
  const box = Math.hypot(...q.map((v) => Math.max(v, 0))) +
    Math.min(Math.max(...q), 0);
  const rho = Math.hypot(p[1], p[2]), h = p[0] - (L / 2 - CENTRE_SEAT.depth);
  const cone = Math.max(
    rho * Math.cos(CENTRE_SEAT.halfAngle) - h * Math.sin(CENTRE_SEAT.halfAngle),
    -h,
  );
  const pilot = Math.max(
    rho - CENTRE_SEAT.pilotRadius,
    L / 2 - CENTRE_SEAT.pilotDepth - p[0],
  );
  return Math.max(box, -Math.min(cone, pilot));
}

// Original asymmetric, twisted three-lobed sculpture. End stock is retained
// for chuck/tailstock workholding; parting off is a separate operation.
export function sampleRotary(x, theta, stock) {
  const start = stock?.start ?? -.041, end = stock?.end ?? .052;
  const u = T.MathUtils.clamp((x - start) / (end - start), 0, 1);
  const swell = Math.sin(Math.PI * u) ** 1.25;
  const half = Math.min(stock?.stockWidth ?? .036, stock?.stockHeight ?? .036) / 2;
  const corner = Math.hypot((stock?.stockWidth ?? .036) / 2, (stock?.stockHeight ?? .036) / 2);
  const base = Math.max(.0095 * half / .018, corner - .016);
  const scale = Math.min(half / .018, (half - .0005 - base) / .0077);
  if (!(scale > 0)) throw Error("This blank's aspect exceeds the ball tool's reach for an all-around sample");
  return base + scale * (.0048 * swell +
    .0022 * swell * Math.cos(3 * theta - u * TAU * .85) +
    .0007 * swell * Math.sin(theta + u * 4));
}
export function rotarySurface(
  radius = sampleRotary,
  { start = -.041, end = .052, nx = 100, na = 192 } = {},
) {
  const p = [], idx = [];
  for (let i = 0; i <= nx; i++) {
    for (let j = 0; j <= na; j++) {
      const x = start + (end - start) * i / nx,
        t = TAU * j / na,
        r = radius(x, t);
      if (!(r > 0 && Number.isFinite(r))) {
        throw Error("Invalid rotary surface radius");
      }
      p.push(x, r * Math.cos(t), r * Math.sin(t));
    }
  }
  for (let i = 0; i < nx; i++) {
    for (let j = 0; j < na; j++) {
      const a = i * (na + 1) + j, b = a + na + 1;
      idx.push(a, a + 1, b, a + 1, b + 1, b);
    }
  }
  for (const i of [0, nx]) {
    const c = p.length / 3;
    p.push(start + (end - start) * i / nx, 0, 0);
    for (let j = 0; j < na; j++) {
      const a = i * (na + 1) + j;
      idx.push(...(i === 0 ? [c, a + 1, a] : [c, a, a + 1]));
    }
  }
  const g = new T.BufferGeometry();
  g.setAttribute("position", new T.Float32BufferAttribute(p, 3));
  g.setIndex(idx);
  g.computeVertexNormals();
  return g;
}

// Conservative sampled spherical tool offset. The maximum over the complete
// ball footprint keeps axial/azimuthal slopes from gouging the target.
function radialOffset(radius, x, theta, R, step = .0005, tool = 'ball') {
  let top = -Infinity;
  const centre = radius(x, theta),
    angle = Math.asin(Math.min(1, R / centre)) * 1.25;
  const n = Math.ceil(R / step), nt = Math.ceil(centre * angle / step);
  for (let i = -n; i <= n; i++) {
    for (let j = -nt; j <= nt; j++) {
      const dx = R * i / n,
        t = angle * j / nt,
        r = radius(x + dx, theta + t),
        z = r * Math.sin(t);
      const d = R * R - dx * dx - z * z;
      if (d < 0) continue;
      top = Math.max(top, r * Math.cos(t) + (tool === 'flat' ? 0 : Math.sqrt(d) - R));
    }
  }
  return top + .00004;
}
export function rotaryProgram(source = sampleRotary, options = {}) {
  if (typeof source !== "function") {
    return rotaryMeshProgram(source, options);
  }
  const tool = options.tool ?? 'ball', fluteLength = options.fluteLength ?? (tool === 'flat' ? .018 : .017);
  if (!['flat','ball'].includes(tool) || !(fluteLength > 0 && Number.isFinite(fluteLength))) throw Error('Invalid rotary cutter');
  const profile = stockProfile(options.material ?? "wood");
  const {
    stockLength = .140,
    stockWidth = .036,
    stockHeight = .036,
    start = -stockLength / 2 + .029,
    end = stockLength / 2 - .018,
    radius = .003,
    angles = 96,
    sampleStep = .001,
    roughAllowance = .0007,
    stepdown = profile.stepdown,
    material = "wood",
    rotationSpeed = .8,
    axisHeight = .097,
    axisX = -.055 + stockLength / 2,
  } = options;
  if (
    !Number.isInteger(angles) || angles < 16 || angles > 512 ||
    !(sampleStep >= .0001 && stepdown >= .0001)
  ) throw Error("Invalid rotary sampling");
  if (
    ![
      stockLength,
      stockWidth,
      stockHeight,
      start,
      end,
      radius,
      sampleStep,
      roughAllowance,
      stepdown,
      rotationSpeed,
      axisHeight,
      axisX,
    ].every(Number.isFinite)
  ) throw Error("Rotary dimensions and rates must be finite");
  if (
    !(stockLength > 0 && stockWidth > 0 && stockHeight > 0 && start < end &&
      start > -stockLength / 2 && end < stockLength / 2)
  ) throw Error("Invalid stock or cutting interval");
  if (!(rotationSpeed > 0 && radius > 0 && roughAllowance >= 0)) {
    throw Error("Invalid rotary tool settings");
  }
  const feed = options.feed ?? profile.feed,
    plunge = options.plunge ?? profile.plunge,
    rpm = options.rpm ?? profile.rpm;
  if (![feed, plunge, rpm].every((v) => v > 0 && Number.isFinite(v))) {
    throw Error("Invalid rotary feed or spindle speed");
  }
  const stockRadius = Math.hypot(stockWidth / 2, stockHeight / 2),
    safe = stockRadius + .0022;
  const target = source === sampleRotary
    ? (x, a) => sampleRotary(x, a, { start, end, stockWidth, stockHeight })
    : source;
  const count = Math.ceil((end - start) / sampleStep), profiles = [];
  let minimum = Infinity;
  for (let j = 0; j < angles; j++) {
    const theta = TAU * j / angles, row = [];
    for (let i = 0; i <= count; i++) {
      const x = start + (end - start) * i / count,
        r = radialOffset(target, x, theta, radius, .0005, tool);
      if (!(r > 0 && r < Math.min(stockWidth, stockHeight) / 2)) {
        throw Error("Target must fit inside the rotary stock");
      }
      row.push([x, r, 0]);
      minimum = Math.min(minimum, r);
    }
    profiles.push(row);
  }
  if (stockRadius - minimum > fluteLength - .0005) {
    throw Error("Target exceeds the installed cutting length");
  }
  const stages = [], moves = [];
  let cursor = [start, safe, 0], a = 0;
  const push = (position, angle, type, stage, rate) => {
    moves.push({ position, angle, type, stage, feed: rate });
    cursor = position;
    a = angle;
  };
  push(cursor, 0, "rapid", "setup");
  // Every roughing level visits the complete circumference before going deeper.
  const floors = [];
  for (
    let r = stockRadius - stepdown;
    r > minimum + roughAllowance;
    r -= stepdown
  ) floors.push(r);
  floors.push(minimum + roughAllowance);
  for (
    const [pass, floor] of [...floors.map((v, i) => [i, v]), [floors.length, 0]]
  ) {
    const finish = floor === 0,
      stage = finish ? "finish" : "rough " + (pass + 1);
    stages.push({ name: stage, firstMove: moves.length });
    // Roughing uses alternating angular stations. Finish fills all stations.
    const stride = finish ? 1 : 2;
    for (let j = 0; j < angles; j += stride) {
      const angle = -TAU * (pass + j / angles),
        row = profiles[j].map((
          [x, r, z],
        ) => [x, finish ? r : Math.max(floor, r + roughAllowance), z]);
      if ((j / stride) % 2) row.reverse();
      push([cursor[0], safe, 0], a, "rapid", stage);
      push([cursor[0], safe, 0], angle, "index", stage);
      push([row[0][0], safe, 0], angle, "rapid", stage);
      push(row[0], angle, "cut", stage, plunge);
      for (const p of row.slice(1)) push(p, angle, "cut", stage, feed);
    }
  }
  push([cursor[0], safe, 0], a, "rapid", "retract");
  const path = new RotaryPath(moves, { ...options, feed, rotationSpeed });
  return {
    moves,
    path,
    stages,
    settings: {
      stockLength,
      stockWidth,
      stockHeight,
      start,
      end,
      radius,
      angles,
      sampleStep,
      axisHeight,
      axisX,
      safe,
      fluteLength,
      tool,
      material,
      feed,
      plunge,
      rpm,
      stepdown,
      centreSeat: { ...CENTRE_SEAT },
    },
    target: source,
  };
}

export class RotaryPath {
  constructor(
    moves,
    { feed = .035, rapid = .08, acceleration = .3, rotationSpeed = .8 } = {},
  ) {
    if (
      ![feed, rapid, acceleration, rotationSpeed].every((v) =>
        Number.isFinite(v) && v > 0
      )
    ) throw Error("Invalid rotary motion rates");
    this.segments = [];
    let time = 0, block = [];
    const flush = () => {
      if (!block.length) return;
      const speed = Array(block.length + 1).fill(0), acc = acceleration * .6;
      // Look ahead along finely sampled surface rows. Preserve complete stops
      // at plunges, retracts and indexing; do not stop at each 1 mm sample.
      for (let i = 1; i < block.length; i++) {
        const a = block[i - 1],
          b = block[i],
          dot = a.d.reduce((n, v, k) => n + v * b.d[k], 0),
          angle = Math.acos(T.MathUtils.clamp(dot, -1, 1));
        if (a.type !== b.type || angle > .15) continue;
        const radius = Math.min(a.length, b.length) /
          (2 * Math.max(1e-8, Math.sin(angle / 2)));
        speed[i] = Math.min(
          a.feed,
          b.feed,
          Math.sqrt(acceleration * .8 * radius),
        );
      }
      for (let i = 1; i <= block.length; i++) {
        speed[i] = Math.min(
          speed[i],
          Math.sqrt(speed[i - 1] ** 2 + 2 * acc * block[i - 1].length),
        );
      }
      for (let i = block.length - 1; i >= 0; i--) {
        speed[i] = Math.min(
          speed[i],
          Math.sqrt(speed[i + 1] ** 2 + 2 * acc * block[i].length),
        );
      }
      for (let i = 0; i < block.length; i++) {
        const s = block[i],
          v0 = speed[i],
          v1 = speed[i + 1],
          peak = Math.min(
            s.feed,
            Math.sqrt(acc * s.length + (v0 * v0 + v1 * v1) / 2),
          );
        const ta = (peak - v0) / acc,
          td = (peak - v1) / acc,
          da = (v0 + peak) * ta / 2,
          dd = (v1 + peak) * td / 2,
          tc = Math.max(0, (s.length - da - dd) / peak);
        Object.assign(s, {
          t0: time,
          t1: time + ta + tc + td,
          v0,
          v1,
          peak,
          ta,
          td,
          da,
          tc,
          acceleration: acc,
          index: this.segments.length,
        });
        this.segments.push(s);
        time = s.t1;
      }
      block = [];
    };
    for (let i = 1; i < moves.length; i++) {
      const a = moves[i - 1], b = moves[i];
      if (
        ![...a.position, ...b.position, a.angle, b.angle].every(Number.isFinite)
      ) throw Error("Invalid rotary move");
      const delta = b.angle - a.angle,
        dist = new T.Vector3(...a.position).distanceTo(
          new T.Vector3(...b.position),
        );
      if (Math.abs(delta) > 1e-9 && dist > 1e-9) {
        throw Error("Indexed program rotates only with stationary XYZ");
      }
      if (Math.abs(delta) > 1e-9) {
        flush();
        if (b.type !== "index") {
          throw Error("A-axis changes require an explicit index move");
        }
        const duration = Math.max(.02, Math.abs(delta) * 1.5 / rotationSpeed);
        this.segments.push({
          a: a.position,
          b: b.position,
          a0: a.angle,
          a1: b.angle,
          type: "index",
          stage: b.stage,
          t0: time,
          t1: time + duration,
          index: this.segments.length,
        });
        time += duration;
      } else if (dist > 1e-10) {
        const rate = b.feed ?? (b.type === "rapid" ? rapid : feed);
        if (
          !(rate > 0 && Number.isFinite(rate)) ||
          !["cut", "rapid"].includes(b.type)
        ) throw Error("Invalid indexed stroke");
        if (b.type === 'cut' && Math.abs(a.position[2] - b.position[2]) > 1e-10) {
          throw Error("Indexed strokes must remain in one axial/radial plane");
        }
        block.push({
          a: a.position,
          b: b.position,
          a0: a.angle,
          a1: b.angle,
          type: b.type,
          stage: b.stage,
          length: dist,
          d: b.position.map((v, k) => (v - a.position[k]) / dist),
          feed: rate,
        });
      }
    }
    flush();
    if (!this.segments.length) throw Error("Empty rotary program");
    this.duration = time;
  }
  sample(seconds) {
    if (!Number.isFinite(seconds)) throw Error("Rotary time must be finite");
    const t = T.MathUtils.clamp(seconds, 0, this.duration);
    let lo = 0, hi = this.segments.length - 1;
    while (lo < hi) {
      const mid = (lo + hi) >> 1;
      if (this.segments[mid].t1 < t) lo = mid + 1;
      else hi = mid;
    }
    const s = this.segments[lo],
      u = (t - s.t0) / (s.t1 - s.t0),
      ease = u * u * (3 - 2 * u);
    let distance = 0, speed = 0;
    if (s.type !== "index") {
      const dt = t - s.t0;
      if (dt < s.ta) {
        speed = s.v0 + s.acceleration * dt;
        distance = s.v0 * dt + s.acceleration * dt * dt / 2;
      } else if (dt < s.ta + s.tc) {
        speed = s.peak;
        distance = s.da + s.peak * (dt - s.ta);
      } else {
        const v = dt - s.ta - s.tc;
        speed = Math.max(0, s.peak - s.acceleration * v);
        distance = s.da + s.peak * s.tc + s.peak * v -
          s.acceleration * v * v / 2;
      }
    }
    const f = s.type === "index"
      ? ease
      : T.MathUtils.clamp(distance / s.length, 0, 1);
    return {
      time: t,
      index: lo,
      fraction: f,
      position: s.a.map((v, k) => v + (s.b[k] - v) * f),
      angle: s.a0 + (s.a1 - s.a0) * ease,
      type: s.type,
      stage: s.stage,
      speed,
      done: seconds >= this.duration,
    };
  }
}

// Independent numeric swept tool distance, useful for planning/review queries.
// Each indexed stroke sweeps a ball nose and its cylindrical cutting length.
export function sweepDistance(
  point,
  s,
  radius,
  fluteLength = .017,
  fraction = 1,
  tool = 'ball',
) {
  const c = Math.cos(s.a0),
    sn = Math.sin(s.a0),
    p = [
      point[0],
      point[1] * c - point[2] * sn,
      point[1] * sn + point[2] * c - s.a[2],
    ];
  if (tool === 'flat') {
    const dx=(s.b[0]-s.a[0])*fraction,dy=(s.b[1]-s.a[1])*fraction;
    const x=p[0]-s.a[0],y=p[1]-s.a[1],w=Math.sqrt(Math.max(0,radius*radius-p[2]*p[2]));
    const tx=T.MathUtils.clamp(x,Math.min(0,dx),Math.max(0,dx));
    const radial=Math.hypot(x-tx,p[2])-radius;
    let lo=0,hi=1;
    if(Math.abs(dx)>1e-12){lo=T.MathUtils.clamp(Math.min((x-w)/dx,(x+w)/dx),0,1);hi=T.MathUtils.clamp(Math.max((x-w)/dx,(x+w)/dx),0,1);}
    const low=Math.min(lo*dy,hi*dy),high=Math.max(lo*dy,hi*dy)+fluteLength;
    const normalizer=Math.abs(dx)>1e-12?Math.sqrt(1+(dy/dx)**2*(1+(p[2]/Math.max(w,1e-7))**2)):1;
    return Math.max(radial,(low-y)/normalizer,(y-high)/normalizer);
  }
  const a = [s.a[0], s.a[1] + radius],
    b = [
      s.a[0] + (s.b[0] - s.a[0]) * fraction,
      s.a[1] + (s.b[1] - s.a[1]) * fraction + radius,
    ];
  const h = fluteLength - radius,
    poly = [a, b, [b[0], b[1] + h], [a[0], a[1] + h]];
  let d = Infinity, inside = false;
  for (let i = 0, j = 3; i < 4; j = i++) {
    const v = poly[i],
      w = poly[j],
      dx = w[0] - v[0],
      dy = w[1] - v[1],
      l = dx * dx + dy * dy;
    const u = l
      ? T.MathUtils.clamp(((p[0] - v[0]) * dx + (p[1] - v[1]) * dy) / l, 0, 1)
      : 0;
    d = Math.min(d, (p[0] - v[0] - u * dx) ** 2 + (p[1] - v[1] - u * dy) ** 2);
    if (
      (v[1] > p[1]) !== (w[1] > p[1]) &&
      p[0] < (w[0] - v[0]) * (p[1] - v[1]) / (w[1] - v[1]) + v[0]
    ) inside = !inside;
  }
  return Math.sqrt((inside ? 0 : d) + p[2] * p[2]) - radius;
}
