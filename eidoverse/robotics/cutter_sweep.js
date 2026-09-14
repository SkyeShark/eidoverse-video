// MIT. Vertical stock intersections with swept flat and ball-nose cutters.
export function sweptCutterHeight(x, z, a, b, radius, kind = "flat") {
  const vx = b[0] - a[0], vz = b[2] - a[2], dy = b[1] - a[1];
  const qx = x - a[0], qz = z - a[2], h2 = vx * vx + vz * vz;
  if (h2 < 1e-18) {
    const d2 = qx * qx + qz * qz;
    if (d2 > radius * radius) return Infinity;
    return Math.min(a[1], b[1]) +
      (kind === "ball"
        ? radius - Math.sqrt(Math.max(0, radius * radius - d2))
        : 0);
  }
  const h = Math.sqrt(h2), projected = (qx * vx + qz * vz) / h;
  const cross = qx * vz - qz * vx;
  const perpendicular2 = cross * cross / h2;
  if (perpendicular2 > radius * radius) return Infinity;
  const section = Math.sqrt(Math.max(0, radius * radius - perpendicular2));
  const lo = Math.max(0, (projected - section) / h);
  const hi = Math.min(1, (projected + section) / h);
  if (lo > hi) return Infinity;
  // Minimize the lower sphere envelope along the full 3D center trajectory.
  // Nearest-XZ projection alone is incorrect on a sloping pass.
  const candidate = kind === "ball"
    ? (projected - dy * section / Math.sqrt(h2 + dy * dy)) / h
    : dy >= 0
    ? lo
    : hi;
  const t = Math.max(lo, Math.min(hi, candidate));
  const dx = qx - vx * t, dz = qz - vz * t;
  return a[1] + dy * t +
    (kind === "ball"
      ? radius - Math.sqrt(Math.max(0, radius * radius - dx * dx - dz * dz))
      : 0);
}

export function indexCutterSweeps(cuts, width, depth, radius, tiles = 24) {
  const bins = Array.from({ length: tiles * tiles }, () => []);
  const cell = (v, extent) => Math.floor((v / extent + .5) * tiles);
  for (let i = 0; i < cuts.length; i++) {
    const { a, b } = cuts[i];
    const x0 = Math.max(0, cell(Math.min(a.x, b.x) - radius, width));
    const x1 = Math.min(tiles - 1, cell(Math.max(a.x, b.x) + radius, width));
    const z0 = Math.max(0, cell(Math.min(a.z, b.z) - radius, depth));
    const z1 = Math.min(tiles - 1, cell(Math.max(a.z, b.z) + radius, depth));
    for (let z = z0; z <= z1; z++) {
      for (let x = x0; x <= x1; x++) bins[z * tiles + x].push(i);
    }
  }
  const headers = new Float32Array(tiles * tiles * 4), indices = [];
  bins.forEach((bin, i) => {
    headers.set([indices.length, bin.length, 0, 0], i * 4);
    indices.push(...bin);
  });
  return {
    tiles,
    headers,
    indices,
    maximumBin: Math.max(...bins.map((b) => b.length)),
  };
}
