// Port of blender/eidoblend/terrain/solvers/hydro.py _parent_lake_water at f90c6fc, combined as lakes() combines
// it: water = max(water, the parent's lake water on this level).
//     surf = where(pw > 1e-6, ph + pw, -inf)          each parent lake cell at its lake level
//     grown = max of surf over the cell and its 8 neighbours (an off-grid neighbour is -inf)
//     L = grown at the parent cell holding the child cell (index j0 + j // f, clipped to the parent grid)
//     water = where(isfinite(L) & (L > h), L - h, 0)
// numpy sums in float64, where ph + pw and ph + pw - h of float32 heights are exact, and rounds the water to float32
// once. Here the lake levels are compared by the exact sign of their difference (hydro/lib sum_sign4), so the
// largest is numpy's, and L - h is that cell's ph + pw - h rounded once (sum3): numpy's value, its sign numpy's
// L > h.
//! include hydro/lib
//! sampler h                the child's height (after lakes() filled its pits)
//! sampler water            the child's own lake water (lake_apply.wgsl)
//! sampler ph               the parent's height
//! sampler pw               the parent's water
//! image   outW r32f        max(water, the parent's lake water)
//! uniform ivec2 uOrigin    the child's window in parent cells: round((x0 - px0) / pcell), round((y0 - py0) / pcell)
//! uniform int uF           round(parent cell / child cell)
//! uniform float uMin       the largest float32 at or below 1e-6

fn kmain(p: vec2<i32>) {
  let n = h_size();
  if (!inside(p, n)) { return; }
  let pn = ph_size();
  let P = vec2<i32>(clamp(u.uOrigin.x + p.x / u.uF, 0, pn.x - 1), clamp(u.uOrigin.y + p.y / u.uF, 0, pn.y - 1));
  var found = false;
  var bh = 0.0;
  var bw = 0.0;
  for (var k = -1; k < 8; k++) {
    var q = P;
    if (k >= 0) { q = P + OFF[k]; }
    if (!inside(q, pn)) { continue; }
    let w = pw_at(q).x;
    if (!(w > u.uMin)) { continue; }
    let hq = ph_at(q).x;
    if (!found || sum_sign4(hq, w, -bh, -bw) > 0) {
      found = true;
      bh = hq;
      bw = w;
    }
  }
  var out = water_at(p).x;
  if (found) {
    let lh = sum3(bh, bw, -h_at(p).x);
    if (lh > 0.0) { out = max(out, lh); }
  }
  outW_store(p, vec4<f32>(out, 0.0, 0.0, 0.0));
}
