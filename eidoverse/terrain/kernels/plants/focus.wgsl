// plants/focus.wgsl (`//! include plants/focus`, after plants/lib): plants.py path_distance on positions. A kernel
// that includes it declares `//! sampler foc r32f` (the focus' points, 4 numbers each: xi, xf, yi, yf) and
// `//! uniform int uFocusN` (how many). Two consecutive points farther apart than PATH_GAP_M (600 m) are separate
// views, not a path.

const GAP2: f32 = 360000.0;

fn fpt(k: i32) -> vec4<f32> { return vec4<f32>(foc_b[4 * k], foc_b[4 * k + 1], foc_b[4 * k + 2], foc_b[4 * k + 3]); }

fn path_dist(p: vec4<f32>) -> f32 {
  var d = sqrt(pos_d2(p, fpt(0)));
  for (var k = 0; k + 1 < u.uFocusN; k++) {
    let a = fpt(k);
    let b = fpt(k + 1);
    let abx = coord_sub(b.xy, a.xy);
    let aby = coord_sub(b.zw, a.zw);
    let L2 = abx * abx + aby * aby;
    if (L2 > GAP2) {
      d = min(d, sqrt(pos_d2(p, b)));
      continue;
    }
    if (L2 <= 0.0) { continue; }
    let px = coord_sub(p.xy, a.xy);
    let py = coord_sub(p.zw, a.zw);
    let t = clamp((px * abx + py * aby) / L2, 0.0, 1.0);
    let ex = px - t * abx;
    let ey = py - t * aby;
    d = min(d, sqrt(ex * ex + ey * ey));
  }
  return d;
}
