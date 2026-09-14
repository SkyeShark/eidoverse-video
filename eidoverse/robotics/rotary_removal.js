// MIT. One-time volumetric engagement sampling for deterministic chip events.
import { indexRotarySweeps } from "./rotary_stock.js";
import { rotaryBlankDistance, sweepDistance } from "./rotary_path.js";
import { distanceTime } from "./cutting.js";

export function rotaryRemoval(
  path,
  settings,
  { resolution = [96, 28, 28] } = {},
) {
  if (
    resolution.length !== 3 ||
    resolution.some((v) => !Number.isInteger(v) || v < 12 || v > 256)
  ) throw Error("Invalid removal sampling resolution");
  const {
    stockLength: L,
    stockHeight: H,
    stockWidth: W,
    radius,
    fluteLength,
    axisHeight,
    axisX,
  } = settings;
  const lo = [-L / 2, -H / 2, -W / 2],
    hi = [L / 2, H / 2, W / 2],
    cell = hi.map((v, k) => (v - lo[k]) / resolution[k]);
  const indexed = indexRotarySweeps(path, settings, { min: lo, max: hi }, [
      32,
      12,
      12,
    ], 0),
    volume = cell.reduce((a, b) => a * b, 1),
    buckets = new Map();
  let removed = 0, queries = 0;
  for (let z = 0; z < resolution[2]; z++) {
    for (let y = 0; y < resolution[1]; y++) {
      for (let x = 0; x < resolution[0]; x++) {
        const p = [x, y, z].map((v, k) => lo[k] + (v + .5) * cell[k]);
        if (rotaryBlankDistance(p, settings) >= 0) continue;
        const b = p.map((v, k) =>
          Math.min(
            indexed.dims[k] - 1,
            Math.floor((v - lo[k]) / indexed.cell[k]),
          )
        );
        const candidates = indexed
          .bins[b[0] + indexed.dims[0] * (b[1] + indexed.dims[1] * b[2])];
        for (const id of candidates) {
          const s = path.segments[id];
          queries++;
          if (sweepDistance(p, s, radius, fluteLength, 1, settings.tool) > 0) continue;
          let low = 0, high = 1;
          for (let i = 0; i < 14; i++) {
            const f = (low + high) / 2;
            if (sweepDistance(p, s, radius, fluteLength, f, settings.tool) <= 0) high = f;
            else low = f;
          }
          const key = id * 8 + Math.min(7, Math.floor(high * 8));
          const c = Math.cos(s.a0),
            sn = Math.sin(s.a0),
            position = [
              p[0] + axisX,
              p[1] * c - p[2] * sn + axisHeight,
              p[1] * sn + p[2] * c,
            ];
          const time = distanceTime(s, s.length * high),
            row = buckets.get(key) ??
              { position: [0, 0, 0], time: 0, volume: 0, count: 0, floor: 0 };
          for (let k = 0; k < 3; k++) row.position[k] += position[k];
          row.time += time;
          row.volume += volume;
          row.count++;
          buckets.set(key, row);
          removed += volume;
          break;
        }
      }
    }
  }
  const events = [...buckets.values()].map((e) => ({
    ...e,
    position: e.position.map((v) => v / e.count),
    time: e.time / e.count,
  })).sort((a, b) => a.time - b.time);
  let total = 0;
  for (const e of events) {
    total += e.volume;
    e.totalVolume = total;
    delete e.count;
  }
  return {
    events,
    removedVolume: removed,
    resolution,
    cellSize: cell,
    queries,
  };
}
