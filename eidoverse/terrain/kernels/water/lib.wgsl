// water/lib.wgsl: what the lake kernels share (`//! include water/lib`): which lakes cover a cell, as build/water.py
// _lake_cells decides it (blender/eidoblend/terrain at f90c6fc). A kept lake is grown one cell under its shore (its
// cells and their eight neighbours) and limited to the level's ring (the cells outside its child's window), so a
// cell is covered by every kept lake that has a wet cell among the nine around it. Two lakes a cell apart both
// cover the cell between them: Blender builds each lake's surface on its own.
//
// A kernel that includes this declares
//     //! sampler lab r32ui    the level's wet labels (core/prims.js label: 0 dry, 1 .. count)
//     //! sampler rank r32ui   a list over the labels: a kept lake's rank among the kept ones, NONE otherwise
//     //! uniform ivec4 uHole  the child's window in this level's cells: i0, j0, m (m = 0: no child), 0

// r into the sorted, distinct ranks a[0 .. n)
fn add_rank(r: u32, a: ptr<function, array<u32, 16>>, n: ptr<function, i32>) {
  var k = 0;
  while (k < *n && (*a)[k] < r) { k++; }
  if (k < *n && (*a)[k] == r) { return; }
  for (var m = *n; m > k; m--) { (*a)[m] = (*a)[m - 1]; }
  (*a)[k] = r;
  *n = *n + 1;
}

fn in_ring(c: vec2<i32>) -> bool {
  let m = u.uHole.z;
  return !(c.x >= u.uHole.x && c.x < u.uHole.x + m && c.y >= u.uHole.y && c.y < u.uHole.y + m);
}

// the ranks of the lakes that cover cell c, added to a (nothing for a cell off the grid or inside the child's window)
fn cell_lakes(c: vec2<i32>, n: vec2<i32>, a: ptr<function, array<u32, 16>>, count: ptr<function, i32>) {
  if (!inside(c, n) || !in_ring(c)) { return; }
  for (var dj = -1; dj <= 1; dj++) {
    for (var di = -1; di <= 1; di++) {
      let q = c + vec2<i32>(di, dj);
      if (!inside(q, n)) { continue; }
      let l = lab_b[q.y * n.x + q.x];
      if (l == 0u) { continue; }
      let r = rank_b[l];
      if (r != NONE) { add_rank(r, a, count); }
    }
  }
}
