// lake_cells: the cells of every lake's surface, build/water.py _lake_cells' `grown` sets (blender/eidoblend/terrain
// at f90c6fc), as a stream of (lake, cell) pairs: one quad each. Mode 0 counts the lakes that cover each cell; an
// exclusive scan of the counts gives each cell's first pair; mode 1 writes the pairs there, a cell's lakes in rising
// rank. The pairs come out in cell order, so a stable sort by lake leaves each lake's cells in row-major order, as
// np.nonzero lists them (build/water.js). Integers only: exact.
//! include prims/lib
//! include water/lib
//! sampler lab r32ui     the level's wet labels (0 dry)
//! sampler rank r32ui    a list over the labels: a kept lake's rank, NONE otherwise
//! sampler pos r32ui     mode 1: each cell's first pair (any integer field in mode 0)
//! image   outN r32ui    mode 0: per cell, the lakes that cover it
//! image   outR r32ui    mode 1: the pairs' lakes (a list)
//! image   outC r32ui    mode 1: the pairs' cells (row-major index)
//! uniform int uMode
//! uniform ivec4 uHole   the child's window in this level's cells: i0, j0, m (m = 0: no child), 0

fn kmain(p: vec2<i32>) {
  let n = lab_size();
  if (!inside(p, n)) { return; }
  var a: array<u32, 16>;
  var count = 0;
  cell_lakes(p, n, &a, &count);
  let c = p.y * n.x + p.x;
  if (u.uMode == 0) {
    outN_b[c] = u32(count);
    return;
  }
  let o = pos_b[c];
  for (var s = 0; s < count; s++) {
    outR_b[o + u32(s)] = a[s];
    outC_b[o + u32(s)] = u32(c);
  }
}
