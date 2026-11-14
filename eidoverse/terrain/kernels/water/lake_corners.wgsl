// lake_corners: the vertices of every lake's surface, build/water.py lake_geometry's np.unique(corners) per lake
// (blender/eidoblend/terrain at f90c6fc), as a stream of (lake, corner) pairs. A cell corner is a lake's vertex when
// one of the four cells around it is covered by the lake. Mode 0 counts each corner's lakes, mode 1 writes the
// pairs at the corner's first place (an exclusive scan of the counts), in rising rank. The pairs come out in corner
// order, so a stable sort by lake leaves each lake's corners in rising order, as np.unique sorts them: a vertex's
// place in the sorted stream is its number in Blender's vertex list. Integers only: exact.
//! include prims/lib
//! include water/lib
//! sampler lab r32ui     the level's wet labels (0 dry), n x n
//! sampler rank r32ui    a list over the labels: a kept lake's rank, NONE otherwise
//! sampler pos r32ui     mode 1: each corner's first pair (any integer field in mode 0)
//! image   outN r32ui    mode 0: per corner of the (n + 1) x (n + 1) lattice, the lakes that use it
//! image   outR r32ui    mode 1: the pairs' lakes (a list)
//! image   outC r32ui    mode 1: the pairs' corners (row-major index on the corner lattice)
//! uniform int uMode
//! uniform ivec4 uHole   the child's window in this level's cells: i0, j0, m (m = 0: no child), 0

fn kmain(p: vec2<i32>) {
  let n = lab_size();
  let m = n + vec2<i32>(1, 1);
  if (!inside(p, m)) { return; }
  var a: array<u32, 16>;
  var count = 0;
  for (var db = -1; db <= 0; db++) {
    for (var da = -1; da <= 0; da++) {
      cell_lakes(p + vec2<i32>(da, db), n, &a, &count);
    }
  }
  let c = p.y * m.x + p.x;
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
