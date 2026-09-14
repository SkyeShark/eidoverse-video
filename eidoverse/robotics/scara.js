// Original S-500 analytic kinematics. Metres and radians; Blender Z up. MIT.
// The finished shared TC70 receiver moved the tool-root datum by 9 mm.
// Calibrated against the actual delivered s500_tool transform at zero travel.
const L1 = .245, L2 = .255, Z = .341, pi = Math.PI;
export const gripTCP = [0, 0, -.1641];
export const limits = [
  [-125 * pi / 180, 125 * pi / 180],
  [-145 * pi / 180, 145 * pi / 180],
  [0, .14],
  [-pi, pi],
];
const wrap = (a) => ((a + pi) % (2 * pi) + 2 * pi) % (2 * pi) - pi;
export function forward(q, tcp = [0, 0, 0]) {
  const [a, b, z, r] = q, yaw = wrap(a + b + r), [tx, ty, tz] = tcp;
  return [
    L1 * Math.cos(a) + L2 * Math.cos(a + b) + Math.cos(yaw) * tx -
    Math.sin(yaw) * ty,
    L1 * Math.sin(a) + L2 * Math.sin(a + b) + Math.sin(yaw) * tx +
    Math.cos(yaw) * ty,
    Z - z + tz,
    yaw,
  ];
}
export function inverse(
  x,
  y,
  z,
  yaw = 0,
  tcp = [0, 0, 0],
  seed = null,
  minZ = null,
) {
  if (
    ![x, y, z, yaw, ...tcp].every(Number.isFinite) ||
    (minZ !== null && z < minZ)
  ) return [];
  const [tx, ty, tz] = tcp;
  x -= Math.cos(yaw) * tx - Math.sin(yaw) * ty;
  y -= Math.sin(yaw) * tx + Math.cos(yaw) * ty;
  const d = (x * x + y * y - L1 * L1 - L2 * L2) / (2 * L1 * L2);
  if (Math.abs(d) > 1 + 1e-10) return [];
  const angle = Math.acos(Math.max(-1, Math.min(1, d))), result = [];
  for (const b of angle > 1e-9 ? [angle, -angle] : [0]) {
    const a = wrap(
        Math.atan2(y, x) - Math.atan2(L2 * Math.sin(b), L1 + L2 * Math.cos(b)),
      ),
      q = [a, b, Z + tz - z, wrap(yaw - a - b)];
    if (
      q.every((v, i) => v >= limits[i][0] - 1e-9 && v <= limits[i][1] + 1e-9)
    ) result.push(q);
  }
  if (seed) {
    const distance = (q) =>
      q.reduce(
        (s, v, i) => s + (i === 2 ? (v - seed[i]) * 8 : wrap(v - seed[i])) ** 2,
        0,
      );
    result.sort((a, b) => distance(a) - distance(b));
  }
  return result;
}
export function demo(t) {
  const a = t * 2 * pi,
    solutions = inverse(
      .32 + .08 * Math.cos(a),
      .12 * Math.sin(a),
      .102 + .025 * Math.cos(a * 2),
      0,
      gripTCP,
      null,
      .055,
    );
  const q = solutions.find((q) => q[1] >= 0);
  if (!q) throw new Error("SCARA path is unreachable");
  return q;
}
