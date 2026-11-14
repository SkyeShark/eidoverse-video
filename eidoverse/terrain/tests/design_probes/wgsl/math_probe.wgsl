// math_probe: the f32 built-ins the kernels lean on, for their error against float64 (kernel_parity.mjs measures the
// ULP distance from the correctly rounded value): what the twin tolerance has to absorb
//! sampler xin          x: a in (1e-3, 1e6), y: b in (0.3, 2.5), z: c in (-20, 20), w: d in (-1.5, 1.5)
//! image   outA rgba32f pow(a, b), exp(c), log(a), sqrt(a)
//! image   outB rgba32f tan(d), atan(5 d), atan2(c, d), a / b

fn kmain(p: vec2<i32>) {
  let n = xin_size();
  if (!inside(p, n)) { return; }
  let v = xin_at(p);
  outA_store(p, vec4<f32>(pow(v.x, v.y), exp(v.z), log(v.x), sqrt(v.x)));
  outB_store(p, vec4<f32>(tan(v.w), atan(5.0 * v.w), atan2(v.z, v.w), v.x / v.y));
}
