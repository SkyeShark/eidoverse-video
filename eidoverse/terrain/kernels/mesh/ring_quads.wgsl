// ring_quads: one ring's lattice quads into the index buffer, build/mesh.py _ring_triangles (blender/eidoblend/
// terrain at f90c6fc). Quad (j, i) has the corners a = (i, j), b = (i + 1, j), c = (i + 1, j + 1), d = (i, j + 1)
// and is split along a - c into (a, b, c) and (a, c, d), written explicitly so the split never depends on a
// rasteriser. Blender writes every kept (a, b, c) in row-major order, then every kept (a, c, d), then the seam fans
// (ring_fans): so a triangle's place is its row's start (build/mesh.js, from the rows' counts) plus its rank in the
// row. Dropped: the quads inside the hole, and along the hole the half that its fan replaces: (a, c, d) of the row
// below the hole and of the column right of it, (a, b, c) of the row above and of the column left of it. Each
// row's dropped quads are one run of columns, so the rank is the column less the run's length past it. Exact.
//! include prims/lib
//! sampler ig r32ui      this ring's vertex numbers (ring_index), ny x nx
//! sampler tab r32i      the rings' integer tables (build/mesh.js TABLE layout); this ring's start at uTab.x
//! image   outT r32ui    the index buffer, 3 vertex numbers a triangle
//! uniform ivec4 uDims   nx, ny, the ring's first triangle, its (a, b, c) triangles
//! uniform ivec4 uHole   the hole's lattice lines jb, jt, il, ir (jb < 0: no hole)
//! uniform ivec4 uTab    this ring's first table entry, 0, 0, 0

fn kmain(p: vec2<i32>) {
  let nx = u.uDims.x;
  let ny = u.uDims.y;
  if (p.x >= nx - 1 || p.y >= ny - 1) { return; }
  let i = p.x;
  let j = p.y;
  let t0 = u.uTab.x;
  let jb = u.uHole.x;
  let jt = u.uHole.y;
  let il = u.uHole.z;
  let ir = u.uHole.w;
  let hole = jb >= 0;
  let rows = hole && j >= jb && j < jt;
  // the dropped runs [lo, hi) of this row: (a, b, c) and (a, c, d)
  var alo = 0;
  var ahi = 0;
  var clo = 0;
  var chi = 0;
  if (rows) {
    alo = il - 1;
    ahi = ir;
    clo = il;
    chi = ir + 1;
  } else if (hole && j == jt) {
    alo = il;
    ahi = ir;
  } else if (hole && j == jb - 1) {
    clo = il;
    chi = ir;
  }
  let a = ig_b[j * nx + i];
  let b = ig_b[j * nx + i + 1];
  let c = ig_b[(j + 1) * nx + i + 1];
  let d = ig_b[(j + 1) * nx + i];
  if (i < alo || i >= ahi) {
    var r = i;
    if (i >= ahi) { r -= ahi - alo; }
    let s = 3u * u32(u.uDims.z + tab_b[t0 + 6 * ny + 5 * nx + j] + r);
    outT_b[s] = a;
    outT_b[s + 1u] = b;
    outT_b[s + 2u] = c;
  }
  if (i < clo || i >= chi) {
    var r = i;
    if (i >= chi) { r -= chi - clo; }
    let s = 3u * u32(u.uDims.z + u.uDims.w + tab_b[t0 + 7 * ny + 5 * nx - 1 + j] + r);
    outT_b[s] = a;
    outT_b[s + 1u] = c;
    outT_b[s + 2u] = d;
  }
}
