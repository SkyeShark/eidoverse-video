// MIT. Bézier service tubing and physically metered filament delivery.
import * as T from "three/webgpu";
import {
  cross,
  float,
  Fn,
  int,
  Loop,
  mat3,
  normalLocal,
  positionLocal,
  transformNormalToView,
  uniform,
  varying,
  vec3,
} from "three/tsl";

const v3 = (p) => p?.isVector3 ? p.clone() : new T.Vector3(...p);
export function bezierPoint(points, u) {
  const v = 1 - u;
  return points[0].clone().multiplyScalar(v * v * v).addScaledVector(
    points[1],
    3 * v * v * u,
  ).addScaledVector(points[2], 3 * v * u * u).addScaledVector(
    points[3],
    u * u * u,
  );
}
function tangent(points, u) {
  const v = 1 - u;
  return points[1].clone().sub(points[0]).multiplyScalar(3 * v * v)
    .addScaledVector(points[2].clone().sub(points[1]), 6 * v * u)
    .addScaledVector(points[3].clone().sub(points[2]), 3 * u * u);
}
export function bezierLength(points, steps = 128) {
  let length = 0, previous = points[0];
  for (let i = 1; i <= steps; i++) {
    const p = bezierPoint(points, i / steps);
    length += p.distanceTo(previous);
    previous = p;
  }
  return length;
}
export function serviceLoop(start, end, length, up = [0, 1, 0]) {
  const a = v3(start), b = v3(end), n = v3(up).normalize();
  if (!(length > a.distanceTo(b) * 1.005 && Number.isFinite(length))) {
    throw Error(
      "PTFE length is too short for these endpoints and seated tangents",
    );
  }
  const points = [a, a.clone(), b.clone(), b];
  let lo = 0, hi = length * 2;
  for (let i = 0; i < 30; i++) {
    const h = (lo + hi) / 2;
    points[1].copy(a).addScaledVector(n, h);
    points[2].copy(b).addScaledVector(n, h);
    if (bezierLength(points) > length) hi = h;
    else lo = h;
  }
  const h = (lo + hi) / 2;
  points[1].copy(a).addScaledVector(n, h);
  points[2].copy(b).addScaledVector(n, h);
  return points;
}

const straight = (
  p,
  q,
) => [p, p.clone().lerp(q, 1 / 3), p.clone().lerp(q, 2 / 3), q];

// Separate short seated liners from the exposed direct-drive supply strand.
// These are geometric feed paths; they do not simulate filament elasticity.
export function directFeedRoute(
  start,
  tip,
  startDirection = new T.Vector3(0, -1, 0),
) {
  const a = v3(start), b = v3(tip), k = .5522847498307936;
  const shoulder = b.clone().add(new T.Vector3(0, .016, 0));
  // A short quarter-turn liner approaches the extruder from in front of its
  // traversing bridge. Its manufactured bend and length remain fixed as the
  // head moves; the exposed supply accommodates the changing span.
  const unit = [
    new T.Vector3(0, 1, 1),
    new T.Vector3(0, 1, 1 - k),
    new T.Vector3(0, k, 0),
    new T.Vector3(0, 0, 0),
  ];
  const radius = .080 / bezierLength(unit);
  const heading = T.MathUtils.clamp(
      Math.atan2(a.x - shoulder.x, a.z - shoulder.z),
      -.85,
      .85,
    ),
    towardGuide = new T.Vector3(Math.sin(heading), 0, Math.cos(heading));
  const entry = unit.map((p) =>
    shoulder.clone().addScaledVector(towardGuide, p.z * radius)
      .add(new T.Vector3(0, p.y * radius, 0))
  );
  const drop = a.y - entry[0].y;
  if (drop <= .02) throw Error("Direct feed needs room above the seated inlet");
  const span = a.distanceTo(entry[0]),
    horizontal = Math.hypot(a.x - entry[0].x, a.z - entry[0].z),
    lateralLimit = Math.abs(startDirection.x) > 1e-6
      ? Math.max(span * .1, (entry[0].x - a.x) * .95 / startDirection.x)
      : span * .6,
    departure = Math.min(span * .6, lateralLimit),
    arrival = Math.min(span * .3, horizontal * .6),
    path = [
      a,
      a.clone().addScaledVector(startDirection, departure),
      entry[0].clone().addScaledVector(towardGuide, arrival),
      entry[0],
    ];
  const ab = path[0].clone().lerp(path[1], .5),
    bc = path[1].clone().lerp(path[2], .5),
    cd = path[2].clone().lerp(path[3], .5),
    left = ab.clone().lerp(bc, .5),
    right = bc.clone().lerp(cd, .5),
    middle = left.clone().lerp(right, .5);
  return {
    strands: [[path[0], ab, left, middle], [middle, right, cd, path[3]]],
    entry: [entry, straight(shoulder, b)],
  };
}

export function createPTFETube({
  points = [[0, 0, 0], [0, .6, 0], [.4, .6, 0], [.4, 0, 0]],
  outerDiameter = .004,
  innerDiameter = .002,
  segments = 72,
  radialSegments = 8,
  ends = [true, true],
  color = "#e7eee5",
  opacity = innerDiameter > 0 ? .48 : 1,
  name = "PTFE guide tube",
} = {}) {
  if (
    !(outerDiameter > 0 && innerDiameter >= 0 &&
      innerDiameter < outerDiameter &&
      [outerDiameter, innerDiameter].every(Number.isFinite))
  ) throw Error("Invalid tube diameters");
  if (
    !Number.isInteger(segments) || segments < 1 || segments > 512 ||
    !Number.isInteger(radialSegments) || radialSegments < 6 ||
    radialSegments > 32
  ) throw Error("Invalid tube tessellation");
  if (!(Number.isFinite(opacity) && opacity >= 0 && opacity <= 1)) {
    throw Error("Tube opacity must be 0..1");
  }
  const controls = [0, 1, 2, 3].map(() => uniform(new T.Vector3())),
    initialNormal = uniform(new T.Vector3(1, 0, 0));
  const curve = Fn(([u]) => {
    const t = float(1).sub(u);
    return controls[0].mul(t.pow(3)).add(
      controls[1].mul(t.pow(2).mul(u).mul(3)),
    ).add(controls[2].mul(t.mul(u.pow(2)).mul(3))).add(
      controls[3].mul(u.pow(3)),
    );
  });
  const direction = Fn(([u]) => {
    const t = float(1).sub(u);
    return controls[1].sub(controls[0]).mul(t.pow(2).mul(3)).add(
      controls[2].sub(controls[1]).mul(t.mul(u).mul(6)),
    ).add(controls[3].sub(controls[2]).mul(u.pow(2).mul(3))).normalize();
  });
  const frame = Fn(([u]) => {
    const previous = direction(0).toVar(), n = initialNormal.toVar();
    // Parallel transport avoids twisting a cross section at a Frenet inflection.
    Loop({ start: int(1), end: int(17), type: "int" }, ({ i }) => {
      const next = direction(u.mul(float(i)).div(16)),
        axis = cross(previous, next),
        c = previous.dot(next);
      n.assign(
        n.add(cross(axis, n)).add(
          cross(axis, cross(axis, n)).div(c.add(1).max(.00001)),
        ).normalize(),
      );
      previous.assign(next);
    });
    return mat3(n, previous, cross(n, previous).normalize());
  });
  const positions = [], uv = [], normal = [], indices = [];
  function ring(u, r, sign = 1, axial = 0) {
    const start = positions.length / 3;
    for (let j = 0; j <= radialSegments; j++) {
      const a = j / radialSegments * Math.PI * 2;
      positions.push(Math.cos(a) * r, u, Math.sin(a) * r);
      uv.push(j / radialSegments, u);
      normal.push(
        axial ? 0 : Math.cos(a) * sign,
        axial,
        axial ? 0 : Math.sin(a) * sign,
      );
    }
    return start;
  }
  function join(a, b, flip = false) {
    for (let j = 0; j < radialSegments; j++) {
      const q = [a + j, b + j, a + j + 1, a + j + 1, b + j, b + j + 1];
      if (flip) {
        for (let k = 0; k < q.length; k += 3) {
          [q[k + 1], q[k + 2]] = [q[k + 2], q[k + 1]];
        }
      }
      indices.push(...q);
    }
  }
  const outer = [];
  for (let i = 0; i <= segments; i++) {
    outer.push(ring(i / segments, outerDiameter / 2));
  }
  for (let i = 0; i < segments; i++) join(outer[i], outer[i + 1]);
  // The bore is visible at loose ends. Only end throats need interior triangles.
  if (innerDiameter > 0) {
    for (const end of [0, 1]) {
      if (!ends[end]) continue;
      const a = ring(end, innerDiameter / 2, -1),
        b = ring(end === 0 ? .015 : .985, innerDiameter / 2, -1);
      join(a, b, end === 1);
      const c = ring(end, outerDiameter / 2, 1, end ? 1 : -1),
        d = ring(end, innerDiameter / 2, 1, end ? 1 : -1);
      join(c, d, end === 0);
    }
  }
  const g = new T.BufferGeometry();
  g.setAttribute("position", new T.Float32BufferAttribute(positions, 3));
  g.setAttribute("normal", new T.Float32BufferAttribute(normal, 3));
  g.setAttribute("uv", new T.Float32BufferAttribute(uv, 2));
  g.setIndex(indices);
  const m = new T.MeshStandardNodeMaterial({
    color,
    roughness: .34,
    metalness: 0,
    side: T.FrontSide,
    transparent: opacity < 1,
    opacity,
    depthWrite: opacity >= 1,
  });
  m.opacityNode = uniform(opacity);
  const basis = frame(positionLocal.y),
    radial = vec3(positionLocal.x, 0, positionLocal.z);
  m.positionNode = curve(positionLocal.y).add(basis.mul(radial));
  const surfaceNormal = varying(basis.mul(normalLocal), "tubeSurfaceNormal");
  m.normalNode = transformNormalToView(surfaceNormal.normalize());
  const mesh = new T.Mesh(g, m);
  mesh.name = name;
  mesh.frustumCulled = false;
  mesh.castShadow = mesh.receiveShadow = true;
  mesh.userData.proceduralCurve = true;
  let path;
  function setPoints(value) {
    if (value.length !== 4) {
      throw Error("A cubic Bézier tube needs four control points");
    }
    const next = value.map(v3);
    if (
      next.some((p) => !p.toArray().every(Number.isFinite)) ||
      next[1].distanceToSquared(next[0]) < 1e-12 ||
      next[3].distanceToSquared(next[2]) < 1e-12
    ) throw Error("Degenerate Bézier endpoint tangent");
    const t = tangent(next, 0).normalize(),
      ref = Math.abs(t.x) < .8
        ? new T.Vector3(1, 0, 0)
        : new T.Vector3(0, 0, 1);
    initialNormal.value.copy(ref.addScaledVector(t, -ref.dot(t)).normalize());
    next.forEach((p, i) => controls[i].value.copy(p));
    path = next;
    g.boundingBox = new T.Box3().setFromPoints(next).expandByScalar(
      outerDiameter / 2,
    );
    g.boundingSphere = g.boundingBox.getBoundingSphere(new T.Sphere());
    return api;
  }
  // Picking follows the deformed centreline without rebuilding/uploading vertices.
  mesh.raycast = (raycaster, hits) => {
    const inverse = mesh.matrixWorld.clone().invert(),
      ray = raycaster.ray.clone().applyMatrix4(inverse),
      onRay = new T.Vector3(),
      onTube = new T.Vector3();
    let a = path[0];
    for (let i = 1; i <= segments; i++) {
      const b = bezierPoint(path, i / segments);
      if (
        ray.distanceSqToSegment(a, b, onRay, onTube) < (outerDiameter / 2) ** 2
      ) {
        const point = onTube.clone().applyMatrix4(mesh.matrixWorld),
          distance = point.distanceTo(raycaster.ray.origin);
        if (distance >= raycaster.near && distance <= raycaster.far) {
          hits.push({
            distance,
            point,
            object: mesh,
            faceIndex: (i - 1) * radialSegments * 2,
          });
        }
      }
      a = b;
    }
  };
  function normalAt(u) {
    let previous = tangent(path, 0).normalize();
    const n = initialNormal.value.clone();
    for (let i = 1; i <= 16; i++) {
      const next = tangent(path, u * i / 16).normalize(),
        axis = previous.clone().cross(next),
        c = previous.dot(next),
        first = axis.clone().cross(n),
        second = axis.clone().cross(first);
      n.add(first).addScaledVector(second, 1 / Math.max(.00001, 1 + c))
        .normalize();
      previous = next;
    }
    return n;
  }
  const api = {
    mesh,
    setPoints,
    normalAt,
    setStartNormal(value) {
      const t = tangent(path, 0).normalize(), n = v3(value);
      initialNormal.value.copy(n.addScaledVector(t, -n.dot(t)).normalize());
    },
    get points() {
      return path.map((p) => p.clone());
    },
    get length() {
      return bezierLength(path);
    },
    sample: (u) => bezierPoint(path, u),
    setColor: (c) => {
      m.color.set(c);
    },
    dispose: () => {
      mesh.removeFromParent();
      g.dispose();
      m.dispose();
    },
  };
  setPoints(points);
  return api;
}

export function installFilament(robot, registerPart) {
  const stand = robot.roots.filament_stand, reel = robot.roots.filament_reel;
  if (!stand || !reel) return;
  const color = robot.materials.palette.filament.value,
    bindings = new Set(),
    curves = [];
  const localOut = stand.userData.filament_out ?? [.041, -.041, .320],
    out = new T.Vector3(localOut[0], localOut[2], -localOut[1]);
  const overhead = stand.userData.feed_layout === "overhead_direct";
  const radius = .0827, gy = -.041, gz = .298 - .15, d2 = gy * gy + gz * gz;
  const py = radius * radius / d2 * gy -
      radius * Math.sqrt(d2 - radius * radius) / d2 * gz,
    pz = radius * radius / d2 * gz +
      radius * Math.sqrt(d2 - radius * radius) / d2 * gy;
  const end = [.041, .298, .041];
  let point = [0, .15 + pz, -py];
  let lead = [point, [.012, point[1] + .059, point[2] - .018], [
    .041,
    .273,
    .041,
  ], end];
  if (overhead) {
    const y = -.006, z = .155, d = y * y + z * z, r = radius + .001;
    const qy = r * r / d * y + r * Math.sqrt(d - r * r) / d * z,
      qz = r * r / d * z - r * Math.sqrt(d - r * r) / d * y;
    point = [0, .280 + qy, qz];
    // Tangential payout clears the cheek before it approaches the guide.
    lead = [point, [.003, point[1] - qz / r * .060, point[2] + qy / r * .060], [
      .0415,
      .315,
      .155,
    ], [.0415, .284, .155]];
  }
  const strand = createPTFETube({
    name: "FP live filament strand",
    outerDiameter: .00175,
    innerDiameter: 0,
    segments: 36,
    color,
    points: lead,
  });
  registerPart(strand.mesh, "FP live filament strand", stand);
  curves.push(strand);
  bindings.add(strand.mesh.material);
  let guideTube;
  if (overhead) {
    // This liner seats against the fitting's internal filament stop. The
    // separate lower tube enters from the collet side; PTFE never crosses
    // the fitting's narrower filament-only throat.
    guideTube = createPTFETube({
      name: "FP carrier PTFE liner",
      segments: 3,
      radialSegments: 10,
      points: straight(
        new T.Vector3(...lead[3]),
        new T.Vector3(.0415, .250, .155),
      ),
    });
    registerPart(guideTube.mesh, "FP carrier PTFE liner", stand);
    curves.push(guideTube);
    const bore = createPTFETube({
      name: "FP filament through guide",
      segments: 3,
      radialSegments: 6,
      outerDiameter: .00175,
      innerDiameter: 0,
      color,
      points: straight(new T.Vector3(...lead[3]), out),
    });
    registerPart(bore.mesh, "FP filament through guide", stand);
    curves.push(bore);
    bindings.add(bore.mesh.material);
  }
  const inlet = robot.roots.extruder_fixed, base = robot.roots.gantry_base;
  const tubes = [], cores = [];
  let lastKey = "", supply;
  const supplies = [];
  if (inlet && base) {
    // Straight collet insertion and a gentle guide bend; two curves at the head.
    for (let i = 0; i < 4; i++) {
      const tube = createPTFETube({
        name: "FP short PTFE entry " + i,
        segments: [1, 12, 18, 1][i],
        radialSegments: 10,
        ends: [i === 0 || i === 2, i === 1 || i === 3],
      });
      registerPart(tube.mesh, "FP short PTFE entries", base);
      tubes.push(tube);
      curves.push(tube);
      const core = createPTFETube({
        name: "FP guided filament core " + i,
        segments: [1, 12, 18, 1][i],
        radialSegments: 6,
        outerDiameter: .00175,
        innerDiameter: 0,
        color,
      });
      registerPart(core.mesh, "FP guided filament core", base);
      core.mesh.castShadow = false;
      cores.push(core);
      curves.push(core);
      bindings.add(core.mesh.material);
    }
    for (let i = 0; i < 2; i++) {
      const part = createPTFETube({
        name: "FP free supply filament " + i,
        segments: 36,
        radialSegments: 8,
        outerDiameter: .00175,
        innerDiameter: 0,
        color,
      });
      registerPart(part.mesh, "FP free supply filament", base);
      supplies.push(part);
      curves.push(part);
      bindings.add(part.mesh.material);
    }
    supply = supplies[0];
  }
  const rest = robot.rest.get(reel).quaternion.clone();
  let initialHelixAngle;
  function payout(rotation = 0) {
    robot.group.updateMatrixWorld(true);
    const rel = stand.matrixWorld.clone().invert().multiply(reel.matrixWorld),
      inverse = rel.clone().invert();
    const local = new T.Vector3(...point).applyMatrix4(inverse);
    if (initialHelixAngle === undefined) {
      initialHelixAngle =
        ((Math.atan2(-local.z, local.x) % (2 * Math.PI)) + 2 * Math.PI) %
        (2 * Math.PI);
    }
    const theta = initialHelixAngle + rotation, pitch = .00175;
    // Start on the authored helix's exact phase. For longer jobs, a continuous
    // level-wind reversal keeps the visual payout inside the pack: a modulo
    // reset would teleport it across the full reel width. The baked pack does
    // not depict individual changing layers or shrink with remainingRadius.
    const raw = 10 + theta / (2 * Math.PI),
      span = 28,
      q = ((raw - .5) % (2 * span) + 2 * span) % (2 * span);
    let turns = .5 + (q <= span ? q : 2 * span - q),
      traverseSign = q <= span ? 1 : -1;
    const edge = .25;
    if (turns < .5 + edge) {
      const d = turns - .5;
      turns = .5 + edge / 2 + d * d / (2 * edge);
      traverseSign *= d / edge;
    }
    if (turns > 28.5 - edge) {
      const d = 28.5 - turns;
      turns = 28.5 - edge / 2 - d * d / (2 * edge);
      traverseSign *= d / edge;
    }
    const axial = -.025375 + pitch * turns;
    const sector = 2 * Math.PI / 64,
      phase = ((theta % sector) + sector) % sector - sector / 2;
    const shell = .0833 * Math.cos(Math.PI / 64) / Math.cos(phase);
    const r = shell - .00010;
    const p = new T.Vector3(r * Math.cos(theta), axial, -r * Math.sin(theta))
      .applyMatrix4(rel);
    const direction = new T.Vector3(
      -r * Math.sin(theta),
      traverseSign * pitch / (2 * Math.PI),
      -r * Math.cos(theta),
    ).transformDirection(rel);
    const end = v3(lead[3]),
      chord = end.distanceTo(p),
      approach = overhead ? 1 : -1;
    if (direction.dot(end.clone().sub(p)) < 0) direction.negate();
    strand.setPoints([
      p,
      p.clone().addScaledVector(direction, chord * (overhead ? .50 : .72)),
      end.clone().add(
        new T.Vector3(
          0,
          approach * Math.min(chord * .23, Math.abs(p.y - end.y) * .5),
          0,
        ),
      ),
      end,
    ]);
    api.payout = {
      angle: theta,
      row: turns,
      shellRadius: shell,
      embeddedDepth: shell - r,
      point: p.toArray(),
      tangent: direction.toArray(),
    };
  }
  const api = {
    color,
    diameter: .00175,
    tubeLength: 0,
    supply,
    supplies,
    consumedLength: 0,
    retraction: 0,
    curves,
    tubes,
    cores,
    guideTube,
    capacity: Math.PI * (.083 ** 2 - .033 ** 2) * .05075 * .9 /
      (Math.PI * .00175 ** 2 / 4),
    setColor(value) {
      color.set(value);
      for (const m of bindings) m.color.copy(color);
      return api;
    },
    bindMaterial(m) {
      bindings.add(m);
      m.color.copy(color);
      return () => bindings.delete(m);
    },
    seek(length, retraction = 0) {
      if (
        !(length >= 0 && Number.isFinite(length) && retraction >= 0 &&
          Number.isFinite(retraction))
      ) throw Error("Invalid filament feed");
      const area = Math.PI * api.diameter ** 2 / 4,
        outer = .083,
        core = .033,
        width = .05075,
        packing = .9;
      const r2 = outer * outer - length * area / (Math.PI * width * packing);
      if (r2 < core * core) {
        throw Error(
          "The reel has insufficient filament for this print",
        );
      }
      // Integrate dL / radius as the pack is consumed, instead of a decorative RPM.
      const r = Math.sqrt(r2),
        angle = 2 * Math.PI * width * packing / area * (outer - r);
      reel.quaternion.copy(rest).multiply(
        new T.Quaternion().setFromAxisAngle(new T.Vector3(0, 1, 0), angle),
      );
      reel.updateMatrix();
      api.consumedLength = length;
      api.retraction = retraction;
      api.rotation = angle;
      api.remainingRadius = r;
      // The fixed emergence point walks backwards over the rotating winding.
      payout(-angle);
      return api;
    },
    update() {
      if (!tubes.length) return;
      robot.group.updateMatrixWorld(true);
      const inverse = base.matrixWorld.clone().invert();
      const a = out.clone().applyMatrix4(stand.matrixWorld).applyMatrix4(
          inverse,
        ),
        b = new T.Vector3(0, .115, 0).applyMatrix4(inlet.matrixWorld)
          .applyMatrix4(inverse);
      const key = [...a.toArray(), ...b.toArray()].join(",");
      if (key === lastKey) return;
      lastKey = key;
      const down = new T.Vector3(0, overhead ? -1 : 1, 0)
        .transformDirection(stand.matrixWorld).transformDirection(inverse);
      const direction = new T.Vector3(1, 0, 0),
        theta = 1.25,
        endTangent = down.clone().multiplyScalar(Math.cos(theta))
          .addScaledVector(direction, Math.sin(theta)),
        h = 4 / 3 * Math.tan(theta / 4),
        p = down.clone().multiplyScalar(Math.sin(theta))
          .addScaledVector(direction, 1 - Math.cos(theta)),
        unit = [
          new T.Vector3(),
          down.clone().multiplyScalar(h),
          p.clone().addScaledVector(endTangent, -h),
          p,
        ],
        seat = a.clone().addScaledVector(down, .006),
        radius = .038 / bezierLength(unit),
        guide = unit.map((p) => p.multiplyScalar(radius).add(seat)),
        exit = guide[3];
      const feed = directFeedRoute(exit, b, endTangent),
        route = [straight(a, seat), guide, ...feed.entry];
      supplies.forEach((curve, i) => curve.setPoints(feed.strands[i]));
      supplies[1].setStartNormal(supplies[0].normalAt(1));
      tubes.forEach((tube, i) => {
        tube.setPoints(route[i]);
        cores[i].setPoints(route[i]);
      });
      const chain = [...tubes.slice(0, 2), ...supplies, ...tubes.slice(2)];
      for (let i = 1; i < chain.length; i++) {
        chain[i].setStartNormal(chain[i - 1].normalAt(1));
      }
      cores.forEach((core, i) => core.setStartNormal(tubes[i].normalAt(0)));
      api.tubeLength = tubes.reduce(
        (n, c) => n + c.length,
        guideTube?.length ?? 0,
      );
      api.freeSpanLength = supplies.reduce((n, c) => n + c.length, 0);
    },
    dispose() {
      curves.forEach((c) => c.dispose());
      bindings.clear();
    },
  };
  robot.filament = api;
  robot.poseCallbacks.add(api.update);
  payout();
  api.update();
}
