// ring_heights: one ring's heights on its lattice, build/mesh.py _sample and _seam_override (blender/eidoblend/
// terrain at 3dda52e). A lattice point is a cell corner of the ring's level: its height is the level's field there by
// Catmull-Rom, weights (-1, 9, 9, -1) / 16 over the four cells either side on each axis (edge cells repeated), rows
// first and then columns, in that order of terms. The outermost row and column of a ring with a parent then take the
// parent's straight edge: np.interp along the parent's lattice line through the parent's heights as written
// (slope (z1 - z0) / (x1 - x0), then slope * (x - x0) + z0; a point on a parent vertex takes its height exactly).
//
// Blender evaluates in float64 and rounds once to float32; this is float32 throughout (PORT_PLAN.md 2.3, 7.3): within
// 13.5 ulp of the corner's largest tap for any evaluation order, fused or not (12.5 from the two four-term sums,
// whose weights sum to 20 / 16 in magnitude, 1 from Blender's rounding). A seam point adds the interpolation's
// rounding to its parent vertices' own.
//
// The same lattice for a mask (uKind 1; the debug attributes of build/mesh.js, _assemble's `attributes`): bilinear at
// the corner, _lattice_bilinear's float32 sums in its order (the two rows of each column, the two columns, x 0.25:
// exact in float32, so equal to numpy's to the bit), the border from the parent's lattice in the same way. uKind 2:
// the level has no such mask, so 0 inside (the border still follows the parent).
//! sampler hl r32f       the level's heights (uKind 1: its mask), n x n, row 0 south; any field when uKind is 2
//! sampler tab r32i      the rings' integer tables (build/mesh.js TABLE layout); this ring's start at uTab.x
//! sampler pz r32f       the parent ring's lattice of the same quantity (any 1 x 1 field for the outermost ring)
//! image   outZ r32f     this ring's lattice, ny x nx
//! uniform ivec4 uDims   nx, ny, 1 when the ring has a parent, n (the level's cells a side)
//! uniform ivec4 uPar    the parent's lattice row of this ring's bottom and top border, column of its left and right
//! uniform ivec4 uTab    this ring's first table entry, 0, 0, 0
//! uniform int uKind     0: heights (Catmull-Rom); 1: a mask (bilinear); 2: nothing on this level (0)

const W = array<f32, 4>(-0.0625, 0.5625, 0.5625, -0.0625);

fn h_at(i: i32, j: i32, n: i32) -> f32 { return hl_b[j * n + i]; }

// np.interp at a lattice point from its table entry (m, o, L): the parent's line values z0 at m, z1 at m + 1
fn seam(m: i32, o: i32, l: i32, z0: f32, z1: f32) -> f32 {
  if (l == 0) { return z0; }
  let slope = (z1 - z0) / f32(l);
  return slope * f32(o) + z0;
}

fn kmain(p: vec2<i32>) {
  let nx = u.uDims.x;
  let ny = u.uDims.y;
  if (p.x >= nx || p.y >= ny) { return; }
  let i = p.x;
  let j = p.y;
  let t0 = u.uTab.x;
  let n = u.uDims.w;
  if (u.uDims.z != 0 && (j == 0 || j == ny - 1 || i == 0 || i == nx - 1)) {
    let pw = pz_size().x;
    var z: f32;
    if (i == 0 || i == nx - 1) {
      // a column of the parent: interpolated along the parent's lattice rows (_seam_override's last assignment)
      var pc = u.uPar.w;
      if (i == 0) { pc = u.uPar.z; }
      let e = t0 + 3 * ny + 5 * nx + 3 * j;
      let m = tab_b[e];
      let l = tab_b[e + 2];
      var z1 = 0.0;
      if (l != 0) { z1 = pz_b[(m + 1) * pw + pc]; }
      z = seam(m, tab_b[e + 1], l, pz_b[m * pw + pc], z1);
    } else {
      var pr = u.uPar.y;
      if (j == 0) { pr = u.uPar.x; }
      let e = t0 + 3 * ny + 2 * nx + 3 * i;
      let m = tab_b[e];
      let l = tab_b[e + 2];
      var z1 = 0.0;
      if (l != 0) { z1 = pz_b[pr * pw + m + 1]; }
      z = seam(m, tab_b[e + 1], l, pz_b[pr * pw + m], z1);
    }
    outZ_store(p, vec4<f32>(z, 0.0, 0.0, 0.0));
    return;
  }
  if (u.uKind == 2) {
    outZ_store(p, vec4<f32>(0.0));
    return;
  }
  // the cell-corner indices: corner m sits between cells m - 1 and m; taps m - 2 .. m + 1, clamped
  let mx = tab_b[t0 + 2 * ny + nx + i];
  let my = tab_b[t0 + 2 * ny + 2 * nx + j];
  if (u.uKind == 1) {
    let i0 = clamp(mx - 1, 0, n - 1);
    let i1 = clamp(mx, 0, n - 1);
    let j0 = clamp(my - 1, 0, n - 1);
    let j1 = clamp(my, 0, n - 1);
    let c0 = h_at(i0, j0, n) + h_at(i0, j1, n);
    let c1 = h_at(i1, j0, n) + h_at(i1, j1, n);
    outZ_store(p, vec4<f32>((c0 + c1) * 0.25, 0.0, 0.0, 0.0));
    return;
  }
  var ix: array<i32, 4>;
  var iy: array<i32, 4>;
  for (var q = 0; q < 4; q++) {
    ix[q] = clamp(mx - 2 + q, 0, n - 1);
    iy[q] = clamp(my - 2 + q, 0, n - 1);
  }
  var t: array<f32, 4>;
  for (var b = 0; b < 4; b++) {
    var s = h_at(ix[b], iy[0], n) * W[0];
    s += h_at(ix[b], iy[1], n) * W[1];
    s += h_at(ix[b], iy[2], n) * W[2];
    s += h_at(ix[b], iy[3], n) * W[3];
    t[b] = s;
  }
  var z = t[0] * W[0];
  z += t[1] * W[1];
  z += t[2] * W[2];
  z += t[3] * W[3];
  outZ_store(p, vec4<f32>(z, 0.0, 0.0, 0.0));
}
