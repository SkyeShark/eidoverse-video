// MIT. Material-aware 2.5D stock sampling and deterministic cutting debris.
import * as T from "three/webgpu";
import { sweptCutterHeight } from "./cutter_sweep.js";
import {
  attribute,
  cos,
  float,
  fwidth,
  int,
  ivec2,
  mix,
  mx_noise_float,
  normalFlat,
  positionLocal,
  sin,
  sqrt,
  textureLoad,
  uniform,
  varying,
  vec3,
} from "three/tsl";

export const stockMaterials = Object.freeze({
  aluminum: Object.freeze({
    label: "Aluminum",
    kind: "metal",
    color: "#bec7cd",
    roughness: .29,
    metalness: 1,
    rpm: 16000,
    feed: .005,
    plunge: .0008,
    stepdown: .001,
    cutDepth: .004,
    chipSize: .0012,
  }),
  brass: Object.freeze({
    label: "Brass",
    kind: "metal",
    color: "#ba9250",
    roughness: .3,
    metalness: 1,
    rpm: 12000,
    feed: .004,
    plunge: .0007,
    stepdown: .001,
    cutDepth: .004,
    chipSize: .0008,
  }),
  steel: Object.freeze({
    label: "Steel",
    kind: "metal",
    color: "#929ca6",
    roughness: .34,
    metalness: 1,
    rpm: 4800,
    feed: .0016,
    plunge: .00025,
    stepdown: .0005,
    cutDepth: .002,
    chipSize: .0007,
  }),
  wood: Object.freeze({
    label: "Hardwood",
    kind: "wood",
    color: "#bc884e",
    roughness: .73,
    metalness: 0,
    rpm: 18000,
    feed: .035,
    plunge: .006,
    stepdown: .003,
    cutDepth: .01,
    chipSize: .0021,
  }),
  plywood: Object.freeze({
    label: "Birch plywood",
    kind: "wood",
    color: "#d3b37e",
    roughness: .75,
    metalness: 0,
    rpm: 18000,
    feed: .03,
    plunge: .005,
    stepdown: .003,
    cutDepth: .01,
    chipSize: .0018,
    plies: true,
  }),
});

export function stockProfile(name = "aluminum") {
  const id =
    ({ metal: "aluminum", aluminium: "aluminum", hardwood: "wood" })[name] ??
      name;
  if (!stockMaterials[id]) {
    throw Error(
      `Unknown stock material ${name}; choose ${
        Object.keys(stockMaterials).join(", ")
      }`,
    );
  }
  return { id, ...stockMaterials[id] };
}

export function finishStock(material, localPosition, profile, color, {fragment=false}={}) {
  const p = fragment ? localPosition : varying(localPosition, "manufacturedStockPoint");
  const tint = uniform(new T.Color(color ?? profile.color));
  if (profile.kind === "wood") {
    // Long grain follows stock Z. End grain uses the same 3D growth rings,
    // including the new pocket walls and floors, rather than a top-only decal.
    const broad = mx_noise_float(p.mul(vec3(38, 27, 19)));
    const warp = sin(p.z.mul(38)).mul(.004).add(broad.mul(.002));
    const radial = sqrt(
      p.x.add(.049).add(warp).pow(2).add(p.y.add(.024).mul(1.18).pow(2)),
    );
    const phase = radial.mul(4200).add(broad.mul(2.8));
    const rings = sin(phase).mul(.5).add(.5).pow(5).mul(
      float(1).sub(fwidth(phase).mul(.28).clamp(0, 1)),
    );
    const fiberPhase = p.x.add(warp).mul(18000);
    const fiber = sin(fiberPhase).mul(sin(p.z.mul(420))).mul(.035).mul(
      float(1).sub(fwidth(fiberPhase).mul(.3).clamp(0, 1)),
    );
    const grain = profile.plies
      ? sin(p.y.mul(Math.PI / .0013)).mul(.065).add(rings.mul(.07))
      : rings.mul(.22);
    material.colorNode = tint.mul(
      float(.92).add(broad.mul(.16)).sub(grain).add(fiber),
    );
    material.roughnessNode = float(.69).add(rings.mul(.12));
  } else {
    const phase = p.z.mul(83000).add(sin(p.x.mul(270)).mul(.7));
    const brushing = sin(phase).mul(.017).mul(
      float(1).sub(fwidth(phase).mul(.25).clamp(0, 1)),
    );
    const patina = mx_noise_float(p.mul(95)).mul(.008);
    material.colorNode = tint.mul(float(.98).add(brushing).add(patina));
    material.roughnessNode = float(profile.roughness).add(brushing.mul(1.4))
      .add(patina);
  }
  return { tint, setColor: (value) => tint.value.set(value) };
}

// Inverse trapezoid timing, keeping emission locked to physical feed acceleration.
export function distanceTime(segment, distance) {
  const s = Math.max(0, Math.min(segment.length, distance)),
    a = segment.acceleration;
  if (s <= segment.da) {
    return segment.t0 +
      (Math.sqrt(segment.v0 ** 2 + 2 * a * s) - segment.v0) / a;
  }
  const cruise = segment.da + segment.peak * segment.tc;
  if (s < cruise) {
    return segment.t0 + segment.ta + (s - segment.da) / segment.peak;
  }
  return segment.t1 -
    (Math.sqrt(segment.v1 ** 2 + 2 * a * (segment.length - s)) - segment.v1) /
      a;
}

export function sampleRemoval(
  path,
  { width, depth, height, radius, resolution, fluteLength = .018, cutter = "flat" },
) {
  if (!(fluteLength > 0 && Number.isFinite(fluteLength))) {
    throw Error("fluteLength must be positive");
  }
  const nx = resolution, nz = resolution;
  const dx = width / nx, dz = depth / nz, cellArea = dx * dz;
  const levels = new Float32Array(nx * nz).fill(height),
    events = [],
    intervals = [];
  let removed = 0;
  const at = (x, z) => {
    if (Math.abs(x) >= width / 2 || Math.abs(z) >= depth / 2) return 0;
    const i = Math.max(0, Math.min(nx - 1, Math.floor((x + width / 2) / dx)));
    const j = Math.max(0, Math.min(nz - 1, Math.floor((z + depth / 2) / dz)));
    return levels[j * nx + i];
  };
  for (const segment of path.segments) {
    if (segment.kind !== "line") {
      throw Error("Stock removal expects straight cutter segments");
    }
    const steps = Math.max(
      1,
      Math.ceil(segment.length / Math.min(radius / 3, dx * .65, dz * .65)),
    );
    const a = segment.a, b = segment.b;
    let engaged = false;
    for (let k = 0; k <= steps; k++) {
      const f = k / steps,
        p = a.map((v, i) => v + (b[i] - v) * f),
        [x, y, z] = p;
      const previous = a.map((v, i) => v + (b[i] - v) * Math.max(0, (k - 1) / steps));
      if (Math.min(y, previous[1]) >= height - 1e-7) continue;
      if (
        y < height - fluteLength && Math.abs(x) < width / 2 + radius &&
        Math.abs(z) < depth / 2 + radius
      ) {
        throw Error(
          "Cut exceeds the visible cutter flute length; the shank would enter stock",
        );
      }
      const x0 = Math.max(0, Math.floor((Math.min(x, previous[0]) - radius + width / 2) / dx)),
        x1 = Math.min(nx - 1, Math.ceil((Math.max(x, previous[0]) + radius + width / 2) / dx));
      const z0 = Math.max(0, Math.floor((Math.min(z, previous[2]) - radius + depth / 2) / dz)),
        z1 = Math.min(nz - 1, Math.ceil((Math.max(z, previous[2]) + radius + depth / 2) / dz));
      let volume = 0;
      for (let j = z0; j <= z1; j++) {
        for (let i = x0; i <= x1; i++) {
          const px = (i + .5) * dx - width / 2, pz = (j + .5) * dz - depth / 2;
          const cutHeight = sweptCutterHeight(px, pz, previous, p, radius, cutter);
          const index = j * nx + i, delta = levels[index] - cutHeight;
          if (delta <= 2e-7) continue;
          if (segment.type === "rapid") {
            throw Error(
              "Rapid move intersects uncut stock; retract above it before traversing",
            );
          }
          volume += delta * cellArea;
          levels[index] = cutHeight;
        }
      }
      if (volume > 1e-13) {
        const time = distanceTime(segment, segment.length * f);
        removed += volume;
        engaged = true;
        events.push({
          time,
          position: p,
          volume,
          totalVolume: removed,
          distance: segment.distance0 + segment.length * f,
          floor: at(x, z),
        });
      }
    }
    intervals.push({ start: segment.t0, end: segment.t1, engaged });
  }
  return {
    events,
    intervals,
    removedVolume: removed,
    cellSize: [dx, dz],
    finalHeights: levels,
    nx,
    nz,
  };
}

export function cuttingDebris(
  removal,
  profile,
  stock,
  { maxParticles = 1200, seed = 7319, dust = true } = {},
) {
  if (
    !Number.isInteger(maxParticles) || maxParticles < 0 || maxParticles > 50000
  ) throw Error("maxParticles must be 0..50000");
  const events = removal.events,
    time = uniform(-1),
    cursor = uniform(-1, "int"),
    group = new T.Group();
  group.name = "Material removal chips and dust";
  const eventsPerRow = 256,
    rows = Math.max(1, Math.ceil(events.length / eventsPerRow));
  const pixels = new Float32Array(eventsPerRow * rows * 8);
  events.forEach((e, i) =>
    pixels.set([...e.position, e.time, e.volume, e.floor, 0, 0], i * 8)
  );
  const data = new T.DataTexture(
    pixels,
    eventsPerRow * 2,
    rows,
    T.RGBAFormat,
    T.FloatType,
  );
  data.name = "eidoverse/data/removal-events";
  data.needsUpdate = true;
  function make(isDust) {
    const perEvent = isDust ? 8 : 6,
      count = Math.min(maxParticles, events.length * perEvent);
    if (!count) return;
    const g = new T.InstancedBufferGeometry();
    const points = isDust
      ? [-.5, 0, -.5, .5, 0, -.5, .5, 0, .5, -.5, 0, .5]
      : [-.5, 0, -.4, .5, 0, -.4, -.5, .3, 0, .5, .3, 0, -.5, 0, .4, .5, 0, .4];
    g.setAttribute("position", new T.Float32BufferAttribute(points, 3));
    g.setIndex(
      isDust ? [0, 2, 1, 0, 3, 2] : [0, 2, 1, 1, 2, 3, 2, 4, 3, 3, 4, 5],
    );
    g.computeVertexNormals();
    const ids = [];
    for (let i = 0; i < count; i++) {
      ids.push(Math.floor(i / perEvent), i % perEvent);
    }
    g.setAttribute(
      "chipId",
      new T.InstancedBufferAttribute(new Float32Array(ids), 2),
    );
    g.instanceCount = count;
    const id = attribute("chipId", "vec2"),
      event = cursor.sub(int(id.x)),
      safe = event.max(0),
      sample = textureLoad(
        data,
        ivec2(safe.mod(eventsPerRow).mul(2), safe.div(eventsPerRow)),
      );
    // Event identity, rather than pool slot, seeds trajectories. Scrubbing and
    // advancing the ring buffer leave already-emitted chips on the same arc.
    const random = (k) =>
      sin(float(event).mul(12.9898).add(id.y.mul(78.233)).add(k + seed)).mul(
        43758.5453,
      ).fract();
    const theta = random(1).mul(Math.PI * 2),
      speed = random(2).mul(isDust ? .11 : .65).add(isDust ? .03 : .25),
      vy = random(3).mul(isDust ? .13 : .6).add(isDust ? .12 : .25);
    const velocity = vec3(cos(theta).mul(speed), vy, sin(theta).mul(speed));
    const origin = sample.xyz.add(
      vec3(
        cos(theta).mul(stock.radius * .55),
        .0015,
        sin(theta).mul(stock.radius * .55),
      ),
    );
    const ttl = isDust
      ? float(.16)
      : vy.add(sqrt(vy.pow(2).add(2 * 9.81 * .0015))).div(9.81).min(.22);
    const age = time.sub(sample.w),
      a = age.clamp(0, ttl),
      spin = theta.add(a.mul(isDust ? 5 : 27));
    const size = random(4).mul(.8).add(.4).mul(
      profile.chipSize * (isDust ? .16 : 1),
    );
    const p = positionLocal.mul(size),
      turned = vec3(
        p.x.mul(cos(spin)).sub(p.z.mul(sin(spin))),
        p.y,
        p.x.mul(sin(spin)).add(p.z.mul(cos(spin))),
      );
    const m = new T.MeshStandardNodeMaterial({
      color: profile.color,
      roughness: isDust ? 1 : profile.roughness,
      metalness: profile.metalness,
      side: T.DoubleSide,
      transparent: isDust,
      depthWrite: !isDust,
      alphaTest: isDust ? .02 : .5,
    });
    // Fine wood particles follow a damped airflow; larger chips are ballistic.
    const travel = isDust ? float(1).sub(a.mul(-14).exp()).div(14) : a;
    const drop = isDust ? a.sub(travel).mul(9.81 / 14) : a.pow(2).mul(9.81 / 2);
    m.positionNode = origin.add(velocity.mul(travel)).sub(vec3(0, drop, 0)).add(
      turned,
    );
    m.normalNode = normalFlat;
    m.colorNode = uniform(new T.Color(profile.color)).mul(
      random(5).mul(.35).add(.8),
    );
    const alive = event.greaterThanEqual(0).and(age.greaterThanEqual(0)).and(
      age.lessThan(ttl),
    );
    m.opacityNode = alive.select(
      isDust ? float(.28).mul(float(1).sub(a.div(ttl))) : float(1),
      0,
    );
    const mesh = new T.Mesh(g, m);
    // Bounds describe the shader's metre-scale trajectories, not its unit chip
    // template. Scene framing and placement tools inspect these CPU bounds.
    g.boundingBox = new T.Box3(
      new T.Vector3(-stock.width / 2 - .22, -.04, -stock.depth / 2 - .22),
      new T.Vector3(
        stock.width / 2 + .22,
        stock.height + .09,
        stock.depth / 2 + .22,
      ),
    );
    g.boundingSphere = g.boundingBox.getBoundingSphere(new T.Sphere());
    mesh.name = isDust
      ? "Wood fines"
      : profile.kind === "wood"
      ? "Wood shavings"
      : "Metal swarf";
    mesh.frustumCulled = false;
    group.add(mesh);
  }
  make(false);
  if (profile.kind === "wood" && dust) make(true);
  return {
    group,
    emissionEvents: events.length,
    particleCount: group.children.reduce(
      (n, m) => n + m.geometry.instanceCount,
      0,
    ),
    setTime(t) {
      time.value = t;
      let lo = 0, hi = events.length;
      while (lo < hi) {
        const mid = (lo + hi) >> 1;
        if (events[mid].time <= t) lo = mid + 1;
        else hi = mid;
      }
      cursor.value = lo - 1;
    },
    dispose() {
      group.removeFromParent();
      for (const m of group.children) {
        m.geometry.dispose();
        m.material.dispose();
      }
      data.dispose();
    },
  };
}
