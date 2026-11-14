// skirt_min: the lowest height on ring 0's perimeter (build/mesh.py _assemble: top[:, 2].min(), where the skirt's
// bottom hangs from). One invocation walks the perimeter's few thousand points: a minimum is exact in any order.
//! sampler zg r32f       ring 0's heights grid, ny x nx
//! image   outM r32f     1 x 1
//! uniform ivec4 uDims   nx, ny, 0, 0

fn kmain(p: vec2<i32>) {
  if (p.x != 0 || p.y != 0) { return; }
  let nx = u.uDims.x;
  let ny = u.uDims.y;
  var lo = zg_b[0];
  for (var i = 0; i < nx; i++) {
    lo = min(lo, zg_b[i]);
    lo = min(lo, zg_b[(ny - 1) * nx + i]);
  }
  for (var j = 0; j < ny; j++) {
    lo = min(lo, zg_b[j * nx]);
    lo = min(lo, zg_b[j * nx + nx - 1]);
  }
  outM_store(p, vec4<f32>(lo, 0.0, 0.0, 0.0));
}
