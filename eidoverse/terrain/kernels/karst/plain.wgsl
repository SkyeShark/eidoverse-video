// Port of blender/eidoblend/terrain/solvers/karst.py _plain at f90c6fc (after its river frame), as a kernel over the
// level's subsamples: the alluvial plain and its river. numpy's float64 is float32 here; np.interp of the river's
// half-width and curvature along its arc length is a binary search of the course's table (rk: its arc lengths, half
// widths and curvatures, float32).
//
// outP: x level (the plain without the channel), y surface (the channel cut in), z water level (the river's flat
// surface), w in_channel (1 inside the wetted channel). uRiver 0: level = surface, water level -1e9, in_channel 0.

//! sampler micro             the alluvial micro-relief (G.smooth)
//! sampler fd                the river's frame at the subsamples: the signed distance d (+ left of the flow) ...
//! sampler fs                ... the arc length s of the nearest point of the course
//! sampler far               its unsigned far field d_far
//! sampler rk rgba32f        per course vertex: (arc length, half-width, curvature, 0)
//! sampler axes rg32f        row 0: xs - cx (metres, per column); row 1: ys - cy (per row)
//! image   outP rgba32f
//! uniform int uRiver
//! uniform int uNK           the course's vertices
//! uniform float uTiltK      -plain_tilt_m_per_km / 1000
//! uniform float uFx         the river's direction
//! uniform float uFy
//! uniform float uWater      plan.water_level
//! uniform float uRise       plain_rise_m
//! uniform float uHwMax
//! uniform float uBankH      river_bank_m
//! uniform float uDepth      river_depth_m
//! uniform float uBar        bar_m
//! uniform float uCell
//! include karst/lib

// np.interp(s, river_s, column c of rk): the ends held
fn rinterp(s: f32, c: i32) -> f32 {
  let first = rk_at(vec2<i32>(0, 0));
  let last = rk_at(vec2<i32>(u.uNK - 1, 0));
  if (!(s >= first.x)) { return first[c]; }
  if (s >= last.x) { return last[c]; }
  var lo = 0;
  var hi = u.uNK - 1;
  loop {
    if (hi - lo <= 1) { break; }
    let mid = (lo + hi) / 2;
    if (rk_at(vec2<i32>(mid, 0)).x <= s) { lo = mid; } else { hi = mid; }
  }
  let a = rk_at(vec2<i32>(lo, 0));
  let b = rk_at(vec2<i32>(lo + 1, 0));
  let slope = (b[c] - a[c]) / (b.x - a.x);
  return slope * (s - a.x) + a[c];
}

fn kmain(p: vec2<i32>) {
  let n = outP_size();
  if (!inside(p, n)) { return; }
  let along = axes_at(vec2<i32>(p.x, 0)).x * u.uFx + axes_at(vec2<i32>(p.y, 1)).x * u.uFy;
  let tilt = u.uTiltK * along;
  var level = tilt + micro_at(p).x;
  if (u.uRiver == 0) {
    outP_store(p, vec4<f32>(level, level, -1.0e9, 0.0));
    return;
  }
  let d = fd_at(p).x;
  let s = fs_at(p).x;
  let bank_h = u.uBankH;
  let band = u.uHwMax + 6.0 * bank_h + 60.0;
  level = level + u.uRise * ksmoothstep(u.uHwMax + 3.0 * bank_h, 1500.0, far_at(p).x);
  let ws = u.uWater + tilt;
  let ad = abs(d);
  let near = ad < band;
  if (!near) {
    // beyond the band the surface is the plain (in_channel: ad >= band > 1.08 hw)
    outP_store(p, vec4<f32>(level, level, ws, 0.0));
    return;
  }
  let hw = rinterp(s, 1);
  let kap = rinterp(s, 2);
  let nrm = d / hw;
  let bend = clamp(abs(kap) * hw / 0.25, 0.0, 1.0);
  let sgk = select(-1.0, 1.0, kap >= 0.0);
  let q = nrm * sgk;                                          /* +1 at the inner bank */
  // the bed: deepest on a line swung 0.45 x bend toward the outer bank
  let nt = -0.45 * bend * sgk;
  var xr = (nrm - nt) / max(1.0 + nt, 1e-3);
  if (nrm >= nt) { xr = (nrm - nt) / max(1.0 - nt, 1e-3); }
  let depth = u.uDepth * (1.0 + 0.3 * bend) * clamp(1.0 - xr * xr, 0.0, 1.0);
  var bed = ws - depth;
  // the point bar: the inner side's bed raised toward a gravel top bar_m above the water at the inner bank
  let lift = ksmoothstep(0.15, 1.0, q) * bend;
  bed = bed + (ws + u.uBar * ksmoothstep(0.55, 1.0, q) - bed) * lift;
  // the banks: a cut bank on the outer side (30 degrees), on the inner side the bar's gravel rising at 4 degrees
  let out_m = max(ad - hw, 0.0);
  let rise = max(level - ws, 0.05);
  let cut = ws + rise * ksmoothstep(0.0, max(rise / 0.5773502691896257, 2.0 * u.uCell), out_m);
  let soft = ws + rise * ksmoothstep(0.0, max(2.5 * rise, 2.0 * u.uCell), out_m);
  let gravel = min(level, ws + u.uBar * bend + out_m * 0.06992681194351041);
  let inner = ksmoothstep(0.0, 0.3, q);
  let bankz = soft + (cut - soft) * bend * (1.0 - inner) + (gravel - soft) * bend * inner;
  var surface = min(level, bankz);
  if (ad < hw) { surface = bed; }
  outP_store(p, vec4<f32>(level, surface, ws, select(0.0, 1.0, ad < hw * 1.08)));
}
