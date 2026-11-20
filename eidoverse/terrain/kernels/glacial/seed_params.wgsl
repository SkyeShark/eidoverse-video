// The port's own kernel: the per-seed troughs of blender/eidoblend/terrain/solvers/glacial.py centrelines at f90c6fc,
// from the smoothed seeds (x, y, zc, f = fs), one invocation per seed, in numpy's order:
//     W = W_t fs;  H = H_t fs;  d = d_t max(fs, 0)^overdeepen_exp
//     wobble:   W = W clip(1 + wobble_w n1, 0.6, 1.4);  H = H clip(1 + wobble_h n2, 0.6, 1.4)   (n = 3 fbm, the seeds')
//     rise_f = clip(1 + rise_noise n3, 0.1, 2.5)  (else 1)
//     taper:    tp = head_taper_factor(dist, W, head_taper);  W, H, d = W tp, H tp, d tp
//     d = d + shoulder_cut H;  zf = zc - d
//     moraine = moraine_m fs where zc < ela_f, else 0;  floor_f = clip(fs, 1e-6, 1)^floor_exp
// numpy is float64; this is float32, and np.power is exact for the exponents 0, 1 and 2 as numpy's (s_pow, glacial/lib's
// g_pow).
//! sampler V                per seed: x, y, zc, fs
//! sampler N                per seed: the fbm values of n1, n2, n3 (times 3 here, as numpy's 3.0 * fbm; 0 when
//                           unused), its head distance (m)
//! image   outP rgba32f     per seed: W, H, d, zf
//! image   outE rgba32f     per seed: moraine, floor_f, rise_f, the taper factor
//! uniform float uWt        the trunk's half-width W_t (m)
//! uniform float uHt        its wall H_t (m)
//! uniform float uDt        its overdeepening d_t (m)
//! uniform float uOdExp     overdeepen_exp
//! uniform float uWobW      wobble_w (0: no wobble)
//! uniform float uWobH      wobble_h
//! uniform int uWobble      1: W and H wobble (wobble_m > 0 and wobble_w or wobble_h > 0)
//! uniform float uRise      rise_noise
//! uniform int uRiseOn      1: rise_noise > 0 and rise_scale_m > 0
//! uniform float uTaper     head_taper (0: none)
//! uniform float uShCut     shoulder_cut
//! uniform float uElaF      the carving ELA above the level's datum, ela_m - base_elevation_m
//! uniform float uMoraine   moraine_m
//! uniform float uFloorExp  floor_exp
//! uniform int uCount

const HEAD_TAPER_MIN: f32 = 0.1;

fn s_pow(s: f32, e: f32) -> f32 {
  if (e == 1.0) { return s; }
  if (e == 2.0) { return s * s; }
  if (e == 0.0) { return 1.0; }
  return pow(s, e);
}

fn kmain(p: vec2<i32>) {
  let w = outP_size().x;
  let s = p.y * w + p.x;
  if (p.x >= w || s >= u.uCount) { return; }
  let v = V_b[s];
  let nz = N_b[s];
  let fs = v.w;
  var W = u.uWt * fs;
  var H = u.uHt * fs;
  var d = u.uDt * s_pow(max(fs, 0.0), u.uOdExp);
  if (u.uWobble != 0) {
    W = W * clamp(1.0 + u.uWobW * (3.0 * nz.x), 0.6, 1.4);
    H = H * clamp(1.0 + u.uWobH * (3.0 * nz.y), 0.6, 1.4);
  }
  var rise = 1.0;
  if (u.uRiseOn != 0) { rise = clamp(1.0 + u.uRise * (3.0 * nz.z), 0.1, 2.5); }
  var tp = 1.0;
  if (u.uTaper > 0.0) {
    let q = clamp(nz.w / max(u.uTaper * W, 1e-6), 0.0, 1.0);
    tp = HEAD_TAPER_MIN + (1.0 - HEAD_TAPER_MIN) * q * q * (3.0 - 2.0 * q);
    W = W * tp;
    H = H * tp;
    d = d * tp;
  }
  d = d + u.uShCut * H;
  let zf = v.z - d;
  var mor = 0.0;
  if (v.z < u.uElaF) { mor = u.uMoraine * fs; }
  let ffl = s_pow(clamp(fs, 1e-6, 1.0), u.uFloorExp);
  outP_b[s] = vec4<f32>(W, H, d, zf);
  outE_b[s] = vec4<f32>(mor, ffl, rise, tp);
}
