// ring_index: one ring's vertex numbers, build/mesh.py _topology's idx[j, i] (blender/eidoblend/terrain at f90c6fc),
// as a u32 grid over the ring's lattice: the global index of the vertex at lattice row j, column i, and NONE inside
// the hole (the child ring's window). A ring's own vertices are numbered in row-major order from v0; the vertices
// of its outermost row and column that lie on the parent ring's lattice are the parent's (one shared vertex), read
// from the parent's grid. build/mesh.js ringTables() makes the tables from the lattice lines (1D, a few thousand
// numbers a ring); the numbering itself is per vertex, so it runs here. Integers only: exact.
//! include prims/lib
//! sampler tab r32i      the rings' integer tables (build/mesh.js TABLE layout); this ring's start at uTab.x
//! sampler par r32ui     the parent ring's grid (any 1 x 1 field for the outermost ring)
//! image   outI r32ui    this ring's grid, ny x nx
//! uniform ivec4 uDims   nx, ny, v0, 1 when the ring has a parent
//! uniform ivec4 uHole   the hole's inner lattice rows and columns: jLo, jHi, iLo, iHi (jLo > jHi: no hole)
//! uniform ivec4 uPar    the parent's lattice row of this ring's bottom and top border, column of its left and right
//! uniform ivec4 uTab    this ring's first table entry, 0, 0, 0

fn kmain(p: vec2<i32>) {
  let nx = u.uDims.x;
  let ny = u.uDims.y;
  if (p.x >= nx || p.y >= ny) { return; }
  let i = p.x;
  let j = p.y;
  let t0 = u.uTab.x;
  let inHoleRow = j >= u.uHole.x && j <= u.uHole.y;
  if (inHoleRow && i >= u.uHole.z && i <= u.uHole.w) {
    outI_store(p, NONE);
    return;
  }
  var start = 0;
  if (u.uDims.w != 0) {
    let pw = par_size().x;
    if (j == 0 || j == ny - 1) {
      // the bottom or top border: a column on the parent's lattice is the parent's vertex, else this ring's own,
      // numbered after the shared ones before it in the row
      let b = tab_b[t0 + ny + i];
      if (b < 0) {
        var pr = u.uPar.y;
        if (j == 0) { pr = u.uPar.x; }
        outI_store(p, par_b[pr * pw + (-1 - b)]);
        return;
      }
      outI_store(p, u32(u.uDims.z + tab_b[t0 + j] + b));
      return;
    }
    let c = tab_b[t0 + ny + nx + j];
    if (c < 0) {
      if (i == 0 || i == nx - 1) {
        var pc = u.uPar.w;
        if (i == 0) { pc = u.uPar.z; }
        outI_store(p, par_b[(-1 - c) * pw + pc]);
        return;
      }
      start = 1;
    }
  }
  var rank = i - start;
  if (inHoleRow && i > u.uHole.w) { rank -= u.uHole.w - u.uHole.z + 1; }
  outI_store(p, u32(u.uDims.z + tab_b[t0 + j] + rank));
}
