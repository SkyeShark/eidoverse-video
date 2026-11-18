// The port's own kernel (no Blender counterpart): blender/eidoblend/terrain/recipes/meadow.py op_hummocks at
// f90c6fc, which numpy makes in float64:
//     steep = clip((degrees(arctan(hypot(gx, gy))) - 12) / 6, 0, 1)      (gy, gx = np.gradient(h, cell))
//     h     = h + 0.5 amplitude_m n (1 - steep)                          (n: the fbm at spacing_m, about N(0, 1))
//! sampler h
//! sampler n
//! sampler gx
//! sampler gy
//! image   outH r32f
//! uniform float uAmp

fn kmain(p: vec2<i32>) {
  if (!inside(p, outH_size())) { return; }
  let a = gx_at(p).x;
  let b = gy_at(p).x;
  let steep = clamp((degrees(atan(sqrt(a * a + b * b))) - 12.0) / 6.0, 0.0, 1.0);
  outH_store(p, vec4<f32>(h_at(p).x + 0.5 * u.uAmp * n_at(p).x * (1.0 - steep), 0.0, 0.0, 0.0));
}
