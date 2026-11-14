// fft_mul: every row of a complex field times one complex row (Bluestein's convolution: the transformed input
// times the transformed chirp, core/prims.js).
//! include prims/lib
//! sampler src rg32f      rows of uL complex values
//! sampler b rg32f        uL complex values (a list)
//! image   dst rg32f
//! uniform int uL

fn kmain(p: vec2<i32>) {
  let rows = dst_size().y;
  if (p.x >= u.uL || p.y >= rows) { return; }
  let i = p.y * u.uL + p.x;
  let a = src_b[i];
  let c = b_b[p.x];
  dst_b[i] = vec2<f32>(a.x * c.x - a.y * c.y, a.x * c.y + a.y * c.x);
}
