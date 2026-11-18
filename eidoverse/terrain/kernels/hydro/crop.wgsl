// A window of a field (numpy's a[j0:j1, i0:i1]): run.js windowRelief takes the main tile's cells of the coarsest
// level with it (blender/eidoblend/terrain/solvers/fluvial.py window_relief at f90c6fc), before the exact selection
// of its percentiles. The output's size is the window's.
//! sampler src
//! image   outF r32f
//! uniform ivec2 uOrigin    (i0, j0): the window's first column and row

fn kmain(p: vec2<i32>) {
  if (!inside(p, outF_size())) { return; }
  outF_store(p, src_at(p + u.uOrigin));
}
