// Port of blender/eidoblend/terrain/solvers/hydro.py fill_depressions at f90c6fc for a surface numpy holds in float64
// that is not float32 everywhere (h + water across lakes: kernels/hydro/surface_in.wgsl), held exactly as float32
// pairs (hydro/lib). The same min-max relaxation as core/prims.js fillDepressions (prims/fill_relax.wgsl), whose
// fixed point is the priority flood's spill surface:
//     W = h at an outlet,    W = max(h, min(W, the 8 neighbours' W)) elsewhere,
// from W = h at the outlets and the largest float elsewhere (uInit 1), with the pairs compared as their values
// (lexicographically): minimum and maximum only, so the fixed point is numpy's float64 result exactly. One step per
// dispatch (prims/fill_relax sweeps tiles in workgroup memory; this is its pair form for the few levels that carry
// lake water). Outlets as fill_depressions takes them on the level runner's grids, which never wrap: every edge
// cell, and every cell at or below the sea level.
//! include prims/lib
//! include hydro/lib
//! sampler h rg32f          the surface, (hi, lo)
//! sampler win rg32f        W so far (uInit 1: not read; bind h)
//! image   outW rg32f
//! image   changed atomic_u32  with uCount 1: element 0 gains the number of cells this dispatch changed
//! uniform int uInit        1: write the start
//! uniform int uSea         1: cells at or below the sea level are outlets
//! uniform vec2 uSea2       the sea level as a pair
//! uniform int uCount

fn is_outlet(p: vec2<i32>, n: vec2<i32>, x: vec2<f32>) -> bool {
  if (on_edge(p, n)) { return true; }
  if (u.uSea != 0 && !p_less(u.uSea2, x)) { return true; }
  return false;
}

fn kmain(p: vec2<i32>) {
  let n = h_size();
  if (!inside(p, n)) { return; }
  let x = h_at(p).xy;
  if (u.uInit != 0) {
    var w = vec2<f32>(BIG, 0.0);
    if (is_outlet(p, n, x)) { w = x; }
    outW_store(p, vec4<f32>(w, 0.0, 0.0));
    return;
  }
  let w0 = win_at(p).xy;
  var w = w0;
  if (!is_outlet(p, n, x)) {
    var m = w0;
    for (var k = 0; k < 8; k++) {
      let q = p + OFF[k];
      if (!inside(q, n)) { continue; }
      let wq = win_at(q).xy;
      if (p_less(wq, m)) { m = wq; }
    }
    w = m;
    if (p_less(w, x)) { w = x; }
  }
  outW_store(p, vec4<f32>(w, 0.0, 0.0));
  if (u.uCount != 0 && !p_equal(w, w0)) { atomicAdd(&changed_b[0], 1u); }
}
