// The port's own kernel (no Blender counterpart): the cell-by-cell numpy expressions of blender/eidoblend/terrain/
// solvers/fluvial.py and hillslope.py at f90c6fc that run on the GPU here (PORT_PLAN.md 2.4, 3.2), one mode each.
// numpy evaluates them in float64 and rounds to float32 once; here every operation is float32, in numpy's order.
//
//   uMode  out                                                     where (numpy)
//   0      a + k0 b (1 - clip(c, 0, 1))                             soil_hills: h + rill_cut (1 - w); h + seed_m nz free
//   1      (a - k0) k1                                              soil_hills: (h_route - h_route.min()) * lam
//   2      hypot(a, b)                                              soil_hills: np.hypot(gx, gy) (for its percentile)
//   3      max(k0, k1 hypot(b, c))                                  hillslope._talus_sc: max(tan, 1.1 |grad h|)
//   4      max(a, k1 hypot(b, c))                                   op_fluvial 'refine': max(Sc, 1.1 |grad h|)
//   5      pin_apply(a, b, c) = a (1 - clip(b)) + c clip(b)         op_creep linear: hb (1 - w) + pin_h w
//   6      min(a, b)                                                bed = min(bed, h)
//   7      min(a, b - c)                                            deposit, talus = min(x, hn - bed)
//   8      a - b                                                    bed = h - loose
//   9      a + k1 ((a + soft_cap(b - a, k0)) - a), cap k0 > 0;     soil_hills: hs = h + soft_cap(hs - h, cap);
//          a + k1 (b - a) when k0 <= 0                              hn = h + blend (hs - h)
//   10     a - b                                                    (kept for symmetry: hn - cut)
//   11     1 where (a - b) > k0, else 0                             (filled - h) > 1e-4: a lake, a filled hollow
//   12     a k0 / k1                                                U = U0 u / peak (op_uplift, uplift_field)
//   13     max(a, k0)                                               np.maximum(x, k)
//   14     a k0                                                     U * uf
//   15     max(a, b)                                                np.maximum(a, b)
//   16     where(b > 0.5, 0, a)                                     U = where(rigid, 0, U)
//   17     where(c < 0, b, a)                                       bed = min(bed, hn), from d = hn - bed
//   18     min(a, max(b, 0))                                        deposit = min(deposit, hn - min(bed, hn))
// soft_cap(r, cap): r up to cap / 2, then half + half tanh((r - half) / half) (hillslope.py soft_cap).
//! sampler a
//! sampler b
//! sampler c
//! image   outF r32f
//! uniform int uMode
//! uniform float uK0
//! uniform float uK1

fn soft_cap(r: f32, cap: f32) -> f32 {
  let half = 0.5 * cap;
  if (r <= half) { return r; }
  return half + half * tanh((r - half) / max(half, 1e-12));
}

fn hyp(x: f32, y: f32) -> f32 { return sqrt(x * x + y * y); }

fn kmain(p: vec2<i32>) {
  if (!inside(p, outF_size())) { return; }
  var a = 0.0;
  var b = 0.0;
  var c = 0.0;
  if (inside(p, a_size())) { a = a_at(p).x; }
  if (inside(p, b_size())) { b = b_at(p).x; }
  if (inside(p, c_size())) { c = c_at(p).x; }
  var o = 0.0;
  switch (u.uMode) {
    case 0: { o = a + u.uK0 * b * (1.0 - clamp(c, 0.0, 1.0)); }
    case 1: { o = (a - u.uK0) * u.uK1; }
    case 2: { o = hyp(a, b); }
    case 3: { o = max(u.uK0, u.uK1 * hyp(b, c)); }
    case 4: { o = max(a, u.uK1 * hyp(b, c)); }
    case 5: { o = pin_apply(a, b, c); }
    case 6: { o = min(a, b); }
    case 7: { o = min(a, b - c); }
    case 8, 10: { o = a - b; }
    case 9: {
      var hs = b;
      if (u.uK0 > 0.0) { hs = a + soft_cap(b - a, u.uK0); }
      o = a + u.uK1 * (hs - a);
    }
    case 11: { o = select(0.0, 1.0, (a - b) > u.uK0); }
    case 12: { o = a * u.uK0 / u.uK1; }
    case 13: { o = max(a, u.uK0); }
    case 14: { o = a * u.uK0; }
    case 15: { o = max(a, b); }
    case 16: { o = select(a, 0.0, b > 0.5); }
    case 17: { o = select(a, b, c < 0.0); }
    case 18: { o = min(a, max(b, 0.0)); }
    default: { o = a; }
  }
  outF_store(p, vec4<f32>(o, 0.0, 0.0, 0.0));
}
