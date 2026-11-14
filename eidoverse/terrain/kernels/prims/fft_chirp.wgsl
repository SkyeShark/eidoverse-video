// fft_chirp: the multiplications around Bluestein's convolution, which turns a DFT of any length n into a
// circular convolution of length M (a power of two): X_j = c_j sum_k (x_k c_k) conj(c_(j - k)), c_k = exp(-pi i
// k^2 / n). Row by row: out[r][k] = scale * (x[r][k] * c_k) for k < uN, 0 for uN <= k < uOut (the zero padding to
// M before the convolution; the kept bins after it). The input is one channel of a float field (real) or a complex
// rg32f field. With uSwap 1 the input is read transposed (x[r][k] = src[k][r]), which turns the columns of a 2D
// transform into rows.
//! include prims/lib
//! sampler src            the rows (real: channel uChannel; complex: rg32f)
//! sampler chirp rg32f    c_k for k < uN (a list)
//! image   dst rg32f      rows of uOut complex values
//! uniform int uN         the input row length taken
//! uniform int uOut       the output row length
//! uniform int uComplex   1: src is complex (x, y = real, imaginary)
//! uniform int uChannel   the real channel (uComplex 0)
//! uniform int uSwap      1: read src transposed
//! uniform float uScale

fn kmain(p: vec2<i32>) {
  let n = dst_size();
  if (p.x >= u.uOut || p.y >= n.y) { return; }
  var v = vec2<f32>(0.0, 0.0);
  if (p.x < u.uN) {
    var q = p;
    if (u.uSwap != 0) { q = vec2<i32>(p.y, p.x); }
    let s = src_at(q);
    if (u.uComplex != 0) { v = s.xy; } else { v = vec2<f32>(s[u.uChannel], 0.0); }
    let c = chirp_b[p.x];
    v = vec2<f32>(v.x * c.x - v.y * c.y, v.x * c.y + v.y * c.x) * u.uScale;
  }
  dst_b[p.y * u.uOut + p.x] = v;
}
