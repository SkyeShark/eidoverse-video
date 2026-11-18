// The port's own kernel (no Blender counterpart): one round of the pointer jumping of blender/eidoblend/terrain/
// solvers/fluvial.py op_valley_floor at f90c6fc (numpy: dist = dist + dist[t]; t = t[t]), carrying a float sum along
// the pointers: the path's length to its first channel cell, and the floors' grade length along the channel network.
// After ceil(log2(longest path)) rounds every cell points at its path's end and holds the sum to it; numpy's loop stops
// when the pointers stop changing, which gives the same values (a settled cell adds 0 from its end).
//! sampler ptr r32ui
//! sampler val
//! image   outP r32ui
//! image   outV r32f

fn kmain(p: vec2<i32>) {
  let n = ptr_size();
  if (!inside(p, n)) { return; }
  let i = p.y * n.x + p.x;
  let q = ptr_b[i];
  outP_store(p, ptr_b[q]);
  outV_store(p, vec4<f32>(val_b[i] + val_b[q], 0.0, 0.0, 0.0));
}
