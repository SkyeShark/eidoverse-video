// Shared-atlas assemblies retain each family's independent motion. MIT.
import * as THREE from "three/webgpu";
const smooth = (t) => {
  t = Math.max(0, Math.min(1, t));
  return t * t * t * (10 + t * (-15 + 6 * t));
};
export function graspValues(g, t) {
  const q = Object.fromEntries(
    Object.entries(g.joints_rad).map(([n, a]) => [n, a * smooth(t)]),
  );
  const frames = g.approach_keyframes ?? [];
  if (frames.length > 1) {
    const [a, b] =
        frames.slice(0, -1).map((a, i) => [a, frames[i + 1]]).find(([a, b]) =>
          t >= a.phase && t <= b.phase
        ) ?? frames.slice(-2),
      f = smooth((t - a.phase) / (b.phase - a.phase));
    for (const [n, v] of Object.entries(a.joints_rad)) {
      q[n] = v * (1 - f) + b.joints_rad[n] * f;
    }
  }
  return q;
}
