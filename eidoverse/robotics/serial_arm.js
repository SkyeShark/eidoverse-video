// Native Blender coordinates, metres and radians. MIT.
const identity = () =>
  Array.from(
    { length: 4 },
    (_, i) => Array.from({ length: 4 }, (_, j) => +(i === j)),
  );
const mul = (a, b) =>
  a.map((row) =>
    b[0].map((_, j) => row.reduce((s, v, k) => s + v * b[k][j], 0))
  );
const cross = (
  a,
  b,
) => [
  a[1] * b[2] - a[2] * b[1],
  a[2] * b[0] - a[0] * b[2],
  a[0] * b[1] - a[1] * b[0],
];
const length = (a) => Math.hypot(...a);
function rotation(axis, angle) {
  const [x, y, z] = axis.map((v) => v / length(axis)),
    c = Math.cos(angle),
    s = Math.sin(angle),
    v = 1 - c,
    r = identity();
  r[0].splice(0, 3, c + x * x * v, x * y * v - z * s, x * z * v + y * s);
  r[1].splice(0, 3, y * x * v + z * s, c + y * y * v, y * z * v - x * s);
  r[2].splice(0, 3, z * x * v - y * s, z * y * v + x * s, c + z * z * v);
  return r;
}
function rotationError(target, actual) {
  const r = Array.from(
    { length: 3 },
    (_, i) =>
      Array.from(
        { length: 3 },
        (_, j) =>
          [0, 1, 2].reduce((s, k) => s + target[i][k] * actual[j][k], 0),
      ),
  );
  let q = [0, 0, 0, 0];
  const trace = r[0][0] + r[1][1] + r[2][2];
  if (trace > 0) {
    const s = Math.sqrt(trace + 1) * 2;
    q = [
      (r[2][1] - r[1][2]) / s,
      (r[0][2] - r[2][0]) / s,
      (r[1][0] - r[0][1]) / s,
      s / 4,
    ];
  } else {
    let i = 0;
    for (let k = 1; k < 3; k++) if (r[k][k] > r[i][i]) i = k;
    const j = (i + 1) % 3,
      k = (i + 2) % 3,
      s = 2 * Math.sqrt(Math.max(0, 1 + r[i][i] - r[j][j] - r[k][k]));
    q[i] = s / 4;
    q[j] = (r[j][i] + r[i][j]) / s;
    q[k] = (r[k][i] + r[i][k]) / s;
    q[3] = (r[k][j] - r[j][k]) / s;
  }
  if (q[3] < 0) q = q.map((v) => -v);
  const n = length(q.slice(0, 3));
  return n < 1e-10
    ? q.slice(0, 3).map((v) => v * 2)
    : q.slice(0, 3).map((v) => v * 2 * Math.atan2(n, q[3]) / n);
}
function solve(a, b) {
  const m = a.map((r, i) => [...r, b[i]]), n = b.length;
  for (let k = 0; k < n; k++) {
    let p = k;
    for (let i = k + 1; i < n; i++) {
      if (Math.abs(m[i][k]) > Math.abs(m[p][k])) p = i;
    }
    [m[k], m[p]] = [m[p], m[k]];
    if (Math.abs(m[k][k]) < 1e-16) return null;
    const d = m[k][k];
    for (let j = k; j <= n; j++) m[k][j] /= d;
    for (let i = 0; i < n; i++) {
      if (i !== k) {
        const d = m[i][k];
        for (let j = k; j <= n; j++) m[i][j] -= d * m[k][j];
      }
    }
  }
  return m.map((r) => r[n]);
}
export class SerialArm {
  constructor(report, tip = [.018, 0, 0]) {
    this.tip = tip;
    this.joints = [];
    let previous = null;
    for (let i = 1; i <= 6; i++) {
      const name = `a650_j${i}`, chain = [];
      let node = name;
      while (node !== previous) {
        const r = report.roots[node];
        chain.push(r);
        node = r.parent;
        if (node === null) break;
      }
      let rest = identity();
      for (const r of chain.reverse()) {
        const [x, y, z] = r.rotation_euler;
        const t = mul(
          mul(rotation([0, 0, 1], z), rotation([0, 1, 0], y)),
          rotation([1, 0, 0], x),
        );
        for (let k = 0; k < 3; k++) t[k][3] = r.location[k];
        rest = mul(rest, t);
      }
      this.joints.push({ rest, ...report.roots[name].properties });
      previous = name;
    }
  }
  forward(q, withJacobian = false) {
    let t = identity();
    const origins = [], axes = [];
    for (let i = 0; i < 6; i++) {
      const j = this.joints[i];
      t = mul(t, j.rest);
      origins.push(t.slice(0, 3).map((r) => r[3]));
      axes.push(
        t.slice(0, 3).map((r) => j.axis.reduce((s, v, k) => s + r[k] * v, 0)),
      );
      t = mul(t, rotation(j.axis, q[i]));
    }
    for (let i = 0; i < 3; i++) {
      t[i][3] += this.tip.reduce((s, v, k) => s + t[i][k] * v, 0);
    }
    if (!withJacobian) return t;
    const columns = axes.map((
      a,
      i,
    ) => [
      ...cross(a, t.slice(0, 3).map((r, k) => r[3] - origins[i][k])),
      ...a,
    ]);
    return {
      transform: t,
      jacobian: Array.from({ length: 6 }, (_, i) => columns.map((c) => c[i])),
    };
  }
  inverse(target, seed = null) {
    if (
      target.length !== 4 ||
      target.some((r) => r.length !== 4 || r.some((v) => !Number.isFinite(v)))
    ) throw Error("A finite 4x4 target transform is required");
    let q = (seed ?? this.joints.map((j) => (j.limits[0] + j.limits[1]) / 2))
      .map((v, i) =>
        Math.max(
          this.joints[i].limits[0],
          Math.min(this.joints[i].limits[1], v),
        )
      );
    const weights = [1, 1, 1, .18, .18, .18];
    for (let step = 0; step < 100; step++) {
      const { transform: t, jacobian: raw } = this.forward(q, true),
        p = t.slice(0, 3).map((r, i) => target[i][3] - r[3]),
        o = rotationError(target, t);
      if (length(p) < 2e-5 && length(o) < 2e-4) return q;
      const e = [...p, ...o].map((v, i) => v * weights[i]),
        j = raw.map((r, i) => r.map((v) => v * weights[i])),
        a = j.map((r, i) =>
          j.map((s, k) =>
            r.reduce((v, n, l) => v + n * s[l], 0) + (i === k ? 1e-6 : 0)
          )
        ),
        solution = solve(a, e);
      if (!solution) return null;
      const dq = q.map((_, k) =>
          j.reduce((s, r, i) => s + r[k] * solution[i], 0)
        ),
        scale = Math.min(1, .2 / Math.max(...dq.map(Math.abs)));
      q = q.map((v, i) =>
        Math.max(
          this.joints[i].limits[0],
          Math.min(this.joints[i].limits[1], v + dq[i] * scale),
        )
      );
    }
    return null;
  }
}
export function articulatedDemo(t) {
  const a = t * Math.PI * 2;
  return [
    .35 * Math.sin(a),
    .20 + .23 * Math.sin(a + .4),
    -.45 + .27 * Math.cos(a),
    .30 * Math.sin(a + .8),
    .65 + .24 * Math.sin(a + .5),
    .4 * Math.cos(a),
  ];
}
export function gantryDemo(t, tool = "bare", tipRestZ = null) {
  const a = t * Math.PI * 2, tip = .066 + .035 * (1 - Math.cos(a));
  return [
    .145 * Math.sin(a),
    .110 * Math.sin(2 * a + .3),
    Number.isFinite(tipRestZ)
      ? tip - tipRestZ
      : tool === "extruder"
      ? tip - (.275 - .077)
      : tool === "spindle"
      ? tip - (.275 - .132)
      : -.07 + .06 * Math.sin(a + .9),
  ];
}
export function constrainGantryPose(report, assembly, xyz) {
  if (xyz.length !== 3 || xyz.some((v) => !Number.isFinite(v))) {
    throw Error("A finite XYZ pose is required");
  }
  return xyz.map((v, i) => {
    const limits = i === 2 && assembly?.z_limits_m
      ? assembly.z_limits_m
      : report.roots[["gantry_x", "gantry_y", "gantry_z"][i]].properties.limits;
    return Math.max(limits[0], Math.min(limits[1], v));
  });
}
