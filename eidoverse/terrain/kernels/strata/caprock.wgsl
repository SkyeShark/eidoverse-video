// The port's own kernel (no Blender counterpart): blender/eidoblend/terrain/solvers/strata.py caprock_fraction() at
// f90c6fc, numpy's mean(h - zoff >= cap_zs) over the main window's cells: here 1 on the window's cells at or above the
// caprock's base height, 0 elsewhere (solvers/strata.js counts them with core/prims.js and divides by the window's
// cells). zs goes through exact() (`//! include detail/exact`): the compiler may not fold h - zoff into the
// comparison in another order.
//! sampler st        x: h
//! sampler zoff
//! image   outF r32f
//! uniform ivec4 uWin    j0, j1, i0, i1 (fluvial.py _main_window)
//! uniform float uCap
//! include detail/exact

fn kmain(p: vec2<i32>) {
  let n = outF_size();
  if (!inside(p, n)) { return; }
  var v = 0.0;
  if (p.y >= u.uWin.x && p.y < u.uWin.y && p.x >= u.uWin.z && p.x < u.uWin.w) {
    let zs = exact(st_at(p).x - zoff_at(p).x, exact_zero(n));
    if (zs >= u.uCap) { v = 1.0; }
  }
  outF_store(p, vec4<f32>(v, 0.0, 0.0, 0.0));
}
