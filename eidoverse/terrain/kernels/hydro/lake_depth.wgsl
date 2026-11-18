// Port of the first lines of blender/eidoblend/terrain/solvers/hydro.py lakes at f90c6fc: depth = filled - h and
// the cells of a closed depression, depth > 1e-4 (the mask metrics.label numbers; solvers/hydro.js lakes).
//
// numpy subtracts in float64, where the difference of two float32 heights is exact; float32's subtraction is
// correctly rounded, so `depth` is numpy's float64 depth rounded once (what lakes() stores as water), and exact
// wherever the spill level and the bed lie within a factor of two. The test compares that depth with the largest
// float32 at or below 1e-4 (uMin), which is numpy's float64 comparison exactly for an exact depth.
//! sampler filled          fill_depressions(h): every cell's spill level
//! sampler h
//! image   outD r32f       depth = filled - h (metres, >= 0)
//! image   outM r32ui      1 where depth > 1e-4, else 0
//! uniform float uMin      the largest float32 at or below 1e-4

fn kmain(p: vec2<i32>) {
  let n = h_size();
  if (!inside(p, n)) { return; }
  let d = filled_at(p).x - h_at(p).x;
  outD_store(p, vec4<f32>(d, 0.0, 0.0, 0.0));
  var m = 0u;
  if (d > u.uMin) { m = 1u; }
  outM_store(p, m);
}
