// Port of blender/eidoblend/terrain/solvers/karst.py _river_distance and _river_frame at f90c6fc, as a kernel over a
// uniform separable grid of points (a lattice, or the cell centres with a one-cell rim).
//
// numpy bins the course's segments and the points on a grid of max_d + 20 m and measures each bin of segments
// against the points of the 3 x 3 bins around it, so a point meets every segment within max_d of it. Here the CPU
// (solvers/karst.js riverBins) lists for every 16 x 16 tile of points the segments within max_d of the tile, in
// ascending order, with their ends in metres from the tile's first point (float64 differences rounded once), so a
// point's distance is float32 of small numbers wherever the level lies. The minimum over a superset of numpy's
// segments, capped at max_d, is numpy's minimum.
//
//   uMode 0  (_river_distance) outF.x: the distance to the course, capped at uMax (metres)
//   uMode 1  (_river_frame, where dc < uNear; dc elsewhere) outF.x: the signed distance (+ left of the flow), outF.y
//            the arc length of the nearest point; a point with no segment within uMax keeps +uMax and 0, as numpy's
//   per point, the first nearest segment in the tile's order (numpy's argmin over its candidates; their order differs
//   from the tile's only between segments exactly as near, the shared vertex of two)

//! sampler segs rgba32f   per entry: the segment's ends (ax, ay, bx, by), metres from its tile's first point
//! sampler sarc rg32f     per entry: the arc lengths at its ends
//! sampler bins r32ui     per tile (row-major over the tiles): the entries' start, then (next row) their count
//! sampler dc             uMode 1: the far field at the points (metres)
//! image   outF rg32f
//! uniform int uMode
//! uniform float uStepX   the points' spacing, metres
//! uniform float uStepY
//! uniform float uMax
//! uniform float uNear
//! uniform int uTilesX    tiles per row
fn kmain(p: vec2<i32>) {
  let n = outF_size();
  if (!inside(p, n)) { return; }
  if (u.uMode == 1) {
    let far = dc_at(p).x;
    if (!(far < u.uNear)) {
      outF_store(p, vec4<f32>(far, 0.0, 0.0, 0.0));
      return;
    }
  }
  let tile = (p.y / 16) * u.uTilesX + p.x / 16;
  let start = i32(bins_at(vec2<i32>(tile, 0)));
  let count = i32(bins_at(vec2<i32>(tile, 1)));
  let px = f32(p.x % 16) * u.uStepX;
  let py = f32(p.y % 16) * u.uStepY;
  var best = 3.0e38;
  var bk = -1;
  var bt = 0.0;
  var bdx = 0.0;
  var bdy = 0.0;
  for (var e = start; e < start + count; e++) {
    let s = segs_at(vec2<i32>(e, 0));
    let abx = s.z - s.x;
    let aby = s.w - s.y;
    let L2 = max(abx * abx + aby * aby, 1e-12);
    let t = clamp(((px - s.x) * abx + (py - s.y) * aby) / L2, 0.0, 1.0);
    let ddx = px - (s.x + t * abx);
    let ddy = py - (s.y + t * aby);
    let d2 = ddx * ddx + ddy * ddy;
    if (d2 < best) {
      best = d2;
      bk = e;
      bt = t;
      bdx = ddx;
      bdy = ddy;
    }
  }
  let d = sqrt(best);
  if (u.uMode == 0) {
    outF_store(p, vec4<f32>(min(d, u.uMax), 0.0, 0.0, 0.0));
    return;
  }
  if (bk < 0 || !(d < u.uMax)) {
    outF_store(p, vec4<f32>(u.uMax, 0.0, 0.0, 0.0));
    return;
  }
  let s = segs_at(vec2<i32>(bk, 0));
  let cross = (s.z - s.x) * bdy - (s.w - s.y) * bdx;
  let sa = sarc_at(vec2<i32>(bk, 0)).xy;
  let arc = sa.x + bt * (sa.y - sa.x);
  outF_store(p, vec4<f32>(select(-d, d, cross >= 0.0), arc, 0.0, 0.0));
}
