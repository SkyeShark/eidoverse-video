// lake_quads: the faces of a level's lake surfaces, build/water.py lake_geometry (blender/eidoblend/terrain at
// f90c6fc): one quad per (lake, cell) of the sorted stream (lake_cells), its corners (i, j), (i + 1, j),
// (i + 1, j + 1), (i, j + 1): counter-clockwise from above, the corners shared within a lake. A corner's vertex is
// its place in the lake's run of the sorted (lake, corner) stream (lake_corners), found by bisection: Blender's
// np.unique(..., return_inverse=True). A quad is written as its two triangles, (a, b, c) and (a, c, d), since a
// three.js index buffer holds triangles. Integers only: exact.
//! include prims/lib
//! sampler qRank r32ui     the quads in order: each one's lake
//! sampler qCell r32ui     and its cell (row-major)
//! sampler vCorner r32ui   the vertices in order: each one's corner
//! sampler vStart r32ui    each lake's first vertex (one more entry than lakes: the last is the vertex count)
//! image   outT r32ui      6 vertex numbers a quad
//! uniform int uCount      the quads
//! uniform int uN          the level's cells a side

fn vertex_of(lake: u32, corner: u32) -> u32 {
  var lo = vStart_b[lake];
  var hi = vStart_b[lake + 1u];
  while (lo < hi) {
    let m = (lo + hi) / 2u;
    if (vCorner_b[m] < corner) { lo = m + 1u; } else { hi = m; }
  }
  return lo;
}

fn kmain(p: vec2<i32>) {
  let q = line_index(p);
  if (q >= u.uCount) { return; }
  let lake = qRank_b[q];
  let cell = qCell_b[q];
  let n = u32(u.uN);
  let c00 = (cell / n) * (n + 1u) + cell % n;
  let a = vertex_of(lake, c00);
  let b = vertex_of(lake, c00 + 1u);
  let c = vertex_of(lake, c00 + n + 2u);
  let d = vertex_of(lake, c00 + n + 1u);
  let o = 6 * q;
  outT_b[o] = a;
  outT_b[o + 1] = b;
  outT_b[o + 2] = c;
  outT_b[o + 3] = a;
  outT_b[o + 4] = c;
  outT_b[o + 5] = d;
}
