// Port of blender/eidoblend/terrain/core/metrics.py at f90c6fc: cliff_pairs' test, pair by pair.
//
// cliff_pairs counts the 8-neighbour pairs steeper than a limit, each pair once: PAIR_DIRS = (row step, column
// step) (0, 1), (1, 0), (1, 1), (1, -1). Each cell owns the four pairs that start at it; a channel of the output is
// 1 where that pair exists and |h[a] - h[b]| / (length x cell) > tan(limit). core/metrics.js counts the ones
// (exact counts, core/prims.js) and divides by the number of pairs, which is a function of the shape alone.
// numpy subtracts in float64; here the subtraction is float32, so a pair within a rounding of the limit can fall on
// the other side.
//! sampler h
//! image   outF rgba32f     one flag per pair direction, in PAIR_DIRS' order
//! uniform float uTan       tan(limit)
//! uniform float uCell      the cell, metres
//! uniform float uDiag      sqrt(2) x the cell (math.hypot(1, 1) * cell, rounded once)

fn steep(a: f32, q: vec2<i32>, n: vec2<i32>, len: f32) -> f32 {
  if (!inside(q, n)) { return 0.0; }
  let s = abs(a - h_at(q).x) / len;
  if (s > u.uTan) { return 1.0; }
  return 0.0;
}

fn kmain(p: vec2<i32>) {
  let n = h_size();
  if (!inside(p, n)) { return; }
  let a = h_at(p).x;
  outF_store(p, vec4<f32>(steep(a, p + vec2<i32>(1, 0), n, u.uCell), steep(a, p + vec2<i32>(0, 1), n, u.uCell),
                          steep(a, p + vec2<i32>(1, 1), n, u.uDiag), steep(a, p + vec2<i32>(-1, 1), n, u.uDiag)));
}
