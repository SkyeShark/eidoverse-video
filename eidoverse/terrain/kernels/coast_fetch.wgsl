// Port of the inline kernel coast_fetch_<n> of blender/eidoblend/terrain/solvers/coast.py (_fetch_source) at f90c6fc.
//
// The open-water fetch of every shore sea cell over NDIR directions (the exposure), the coast stage's first
// kernel. Blender writes one source per ray count, the direction tables written into it as constants
// (`const vec2 DIRS[n] = ...`); here the same tables are WGSL consts that solvers/coast.js fetchKernel(n) prefixes
// as the runner's defines (NDIR, DIRS, INV), and the kernel takes Blender's name, coast_fetch_<n>, so the dispatch
// log names it as Blender's does. The `//!` header below is Blender's, unchanged, plus the include of exact().
//
// Differences from the GLSL, each forced by WGSL:
//   - `precise float tx = ...`: WGSL has no `precise`; the value goes through exact() (kernels/detail/exact.wgsl:
//     its bits ORed with a zero the compiler cannot prove is zero), so it is computed as written, correctly
//     rounded, as the twin's float32 is.
//   - `out ivec2 q` is a pointer (common.wgsl neighbour); the ?: of the steps are select().

//! sampler seaT        x: 1 sea, 0 land
//! image   outE r32f     x: the exposure (mean fetch / the longest fetch, 0..1) of a shore sea cell; -1 elsewhere
//! uniform float uMaxCells   the longest fetch, cells
//! include detail/exact

/* Each ray walks every cell it passes through, in order (an exact grid traversal, Amanatides & Woo 1987: the k-th
   vertical grid line it crosses lies at t = (k + 0.5) / |dx| from the cell centre), so it cannot slip between two
   land cells that meet at a corner. The fetch is t where it enters the first land cell; leaving the grid over water
   or running past the longest fetch counts as open sea. */
fn kmain(p: vec2<i32>) {
  let n = seaT_size();
  if (!inside(p, n)) { return; }
  var shore = false;
  if (seaT_at(p).x > 0.5) {
    for (var k = 0; k < 8; k++) {
      var q: vec2<i32>;
      if (neighbour(p, k, n, BOUND_OPEN, &q) && seaT_at(q).x < 0.5) { shore = true; }
    }
  }
  if (!shore) {
    outE_store(p, vec4<f32>(-1.0, 0.0, 0.0, 0.0));
    return;
  }
  let z = exact_zero(n);
  var acc = 0.0;
  let maxIt = i32(1.5 * u.uMaxCells) + 4;               /* a ray crosses at most |dx| + |dy| <= 1.42 lines per cell */
  for (var d = 0; d < NDIR; d++) {
    let st = vec2<i32>(select(-1, 1, DIRS[d].x > 0.0), select(-1, 1, DIRS[d].y > 0.0));
    var c = p;
    var kx = 0;
    var ky = 0;
    var f = u.uMaxCells;
    for (var it = 0; it < maxIt; it++) {
      let tx = exact((f32(kx) + 0.5) * INV[d].x, z);
      let ty = exact((f32(ky) + 0.5) * INV[d].y, z);
      var t: f32;
      if (tx < ty) {
        t = tx;
        c.x += st.x;
        kx++;
      } else {
        t = ty;
        c.y += st.y;
        ky++;
      }
      if (t > u.uMaxCells) { break; }
      if (!inside(c, n)) { break; }
      if (seaT_at(c).x < 0.5) {
        f = max(t, 0.5);
        break;
      }
    }
    acc += f;
  }
  outE_store(p, vec4<f32>(acc / (f32(NDIR) * u.uMaxCells), 0.0, 0.0, 0.0));
}
