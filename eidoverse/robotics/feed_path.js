// MIT.
// Original 2.5D process geometry and feed timing, metres and seconds.
const clamp = (v, a, b) => Math.max(a, Math.min(b, v));
const add = (a, b) => a.map((v, i) => v + b[i]),
  sub = (a, b) => a.map((v, i) => v - b[i]),
  mul = (a, s) => a.map((v) => v * s);
const dot = (a, b) => a.reduce((s, v, i) => s + v * b[i], 0),
  length = (a) => Math.sqrt(dot(a, a));
const unit = (a) => mul(a, 1 / length(a)),
  cross = (
    a,
    b,
  ) => [
    a[1] * b[2] - a[2] * b[1],
    a[2] * b[0] - a[0] * b[2],
    a[0] * b[1] - a[1] * b[0],
  ];
const rotate = (p, n, a) =>
  add(
    add(mul(p, Math.cos(a)), mul(cross(n, p), Math.sin(a))),
    mul(n, dot(n, p) * (1 - Math.cos(a))),
  );

export class FeedPath {
  constructor(
    points,
    {
      feed = .012,
      rapid = .10,
      acceleration = .3,
      blendTolerance = .000025,
      beadArea = 0,
    } = {},
  ) {
    if (points.length < 2) {
      throw new Error("A process path needs at least two points");
    }
    if (
      ![feed, rapid, acceleration].every((v) => v > 0 && Number.isFinite(v)) ||
      !(blendTolerance >= 0 && Number.isFinite(blendTolerance)) ||
      !(beadArea >= 0 && Number.isFinite(beadArea))
    ) throw new Error("Invalid feed settings");
    for (const p of points) {
      if (p.position.length !== 3 || !p.position.every(Number.isFinite)) {
        throw new Error("Invalid tool coordinate");
      }
    }
    this.acceleration = acceleration;
    this.beadArea = beadArea;
    this.blendTolerance = blendTolerance;
    const nodes = points.map((p) => ({ ...p, position: [...p.position] }));
    const raw = [];
    for (let i = 1; i < nodes.length; i++) {
      const d = sub(nodes[i].position, nodes[i - 1].position), l = length(d);
      if (l < 1e-10) continue;
      const type = nodes[i].type || "cut";
      if (!["cut", "rapid", "extrude"].includes(type)) {
        throw new Error("Unsupported process mode");
      }
      const rate = nodes[i].feed ?? (type === "rapid" ? rapid : feed);
      if (!(rate > 0 && Number.isFinite(rate))) {
        throw new Error("Invalid segment feed");
      }
      raw.push({
        a: nodes[i - 1].position,
        b: nodes[i].position,
        length: l,
        d: mul(d, 1 / l),
        type,
        feed: rate,
      });
    }
    if (!raw.length) throw new Error("Path has zero length");
    const joins = Array(raw.length - 1).fill(null);
    for (let i = 0; i < joins.length; i++) {
      const a = raw[i],
        b = raw[i + 1],
        c = clamp(dot(a.d, b.d), -1, 1),
        angle = Math.acos(c);
      if (
        a.type !== b.type || angle < 1e-5 || angle > Math.PI - .001 ||
        blendTolerance === 0
      ) continue;
      if (a.type === "cut" && (Math.abs(a.d[1]) + Math.abs(b.d[1]) > 1e-8)) {
        continue; // A plunge ends before horizontal cutting.
      }
      const radius = blendTolerance / (1 / Math.cos(angle / 2) - 1),
        trim = Math.min(
          radius * Math.tan(angle / 2),
          a.length * .35,
          b.length * .35,
        ),
        r = trim / Math.tan(angle / 2);
      const n = unit(cross(a.d, b.d)),
        start = sub(a.b, mul(a.d, trim)),
        end = add(a.b, mul(b.d, trim));
      const center = add(start, mul(cross(n, a.d), r));
      joins[i] = {
        kind: "arc",
        a: start,
        b: end,
        center,
        normal: n,
        angle,
        radius: r,
        length: r * angle,
        type: a.type,
        feed: Math.min(a.feed, b.feed, Math.sqrt(acceleration * .8 * r)),
        entryDirection: a.d,
        exitDirection: b.d,
      };
    }
    this.segments = [];
    for (let i = 0; i < raw.length; i++) {
      const r = raw[i],
        a = joins[i - 1]?.b || r.a,
        b = joins[i]?.a || r.b,
        l = length(sub(b, a));
      if (l > 1e-10) {
        this.segments.push({
          ...r,
          kind: "line",
          a,
          b,
          length: l,
          entryDirection: r.d,
          exitDirection: r.d,
        });
      }
      if (joins[i]) this.segments.push(joins[i]);
    }
    const s = this.segments,
      n = s.length,
      velocity = Array(n + 1).fill(0),
      tangentA = acceleration * .6;
    for (let i = 1; i < n; i++) {
      if (
        s[i - 1].type === s[i].type &&
        dot(s[i - 1].exitDirection, s[i].entryDirection) > 1 - 1e-6
      ) velocity[i] = Math.min(s[i - 1].feed, s[i].feed);
    }
    for (let i = 1; i <= n; i++) {
      velocity[i] = Math.min(
        velocity[i],
        Math.sqrt(velocity[i - 1] ** 2 + 2 * tangentA * s[i - 1].length),
      );
    }
    for (let i = n - 1; i >= 0; i--) {
      velocity[i] = Math.min(
        velocity[i],
        Math.sqrt(velocity[i + 1] ** 2 + 2 * tangentA * s[i].length),
      );
    }
    let time = 0, distance = 0, volume = 0;
    for (let i = 0; i < n; i++) {
      const g = s[i],
        v0 = velocity[i],
        v1 = velocity[i + 1],
        peak = Math.min(
          g.feed,
          Math.sqrt(tangentA * g.length + (v0 * v0 + v1 * v1) / 2),
        );
      const ta = (peak - v0) / tangentA,
        td = (peak - v1) / tangentA,
        da = (v0 + peak) * ta / 2,
        dd = (v1 + peak) * td / 2,
        tc = Math.max(0, (g.length - da - dd) / peak);
      Object.assign(g, {
        t0: time,
        t1: time + ta + tc + td,
        v0,
        v1,
        peak,
        ta,
        td,
        tc,
        da,
        acceleration: tangentA,
        distance0: distance,
        volume0: volume,
      });
      time = g.t1;
      distance += g.length;
      if (g.type === "extrude") volume += g.length * beadArea;
    }
    this.duration = time;
    this.length = distance;
    this.volume = volume;
  }
  segmentAt(t) {
    let lo = 0, hi = this.segments.length - 1;
    while (lo < hi) {
      const m = (lo + hi) >> 1;
      if (this.segments[m].t1 < t) lo = m + 1;
      else hi = m;
    }
    return lo;
  }
  sample(seconds) {
    const t = clamp(seconds, 0, this.duration),
      index = this.segmentAt(t),
      g = this.segments[index],
      dt = t - g.t0;
    let s, v, at;
    if (dt < g.ta) {
      v = g.v0 + g.acceleration * dt;
      s = g.v0 * dt + g.acceleration * dt * dt / 2;
      at = g.acceleration;
    } else if (dt < g.ta + g.tc) {
      v = g.peak;
      s = g.da + g.peak * (dt - g.ta);
      at = 0;
    } else {
      const u = dt - g.ta - g.tc;
      v = g.peak - g.acceleration * u;
      s = g.da + g.peak * g.tc + g.peak * u - g.acceleration * u * u / 2;
      at = -g.acceleration;
    }
    s = clamp(s, 0, g.length);
    v = Math.max(0, v);
    let position, tangent, normalAcceleration = [0, 0, 0];
    if (g.kind === "line") {
      position = add(g.a, mul(g.d, s));
      tangent = g.d;
    } else {
      const a = g.angle * s / g.length,
        radial = rotate(sub(g.a, g.center), g.normal, a);
      position = add(g.center, radial);
      tangent = rotate(g.entryDirection, g.normal, a);
      normalAcceleration = mul(unit(radial), -v * v / g.radius);
    }
    if (seconds < 0 || seconds >= this.duration) {
      v = 0;
      at = 0;
      normalAcceleration = [0, 0, 0];
    }
    return {
      time: t,
      position,
      tangent,
      velocity: mul(tangent, v),
      acceleration: add(mul(tangent, at), normalAcceleration),
      speed: v,
      type: g.type,
      index,
      segmentDistance: s,
      distance: g.distance0 + s,
      volume: g.volume0 + (g.type === "extrude" ? s * this.beadArea : 0),
      done: seconds >= this.duration,
    };
  }
  walk(from, to, step, visit) {
    if (to < from) throw new Error("Reset the process before rewinding");
    const start = clamp(from, 0, this.duration),
      end = clamp(to, 0, this.duration);
    for (let i = this.segmentAt(start); i <= this.segmentAt(end); i++) {
      const g = this.segments[i],
        a = Math.max(start, g.t0),
        b = Math.min(end, g.t1);
      if (b < a) continue;
      const first = this.sample(a),
        last = this.sample(b),
        count = Math.max(
          1,
          Math.ceil(
            Math.max(0, last.segmentDistance - first.segmentDistance) / step,
          ),
          Math.ceil((b - a) * g.peak / step),
        );
      let previous = first;
      for (let k = 1; k <= count; k++) {
        const next = this.sample(a + (b - a) * k / count);
        visit(previous, next, g.type);
        previous = next;
      }
    }
  }
}
