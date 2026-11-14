// fft_stage: one stage of a radix-2 Stockham FFT over rows of complex values (PORT_PLAN.md 3.4: the spectrum
// metric's np.fft.rfft2 in the Blender edition's core/metrics.py at f90c6fc). log2(L) stages with uNs = 1, 2, 4,
// ..., L / 2, the rows read from `src` and written to `dst` (ping-pong), leave each row's DFT in natural order
// (Govindaraju et al. 2008, "High performance discrete Fourier transforms on graphics processors"). Lengths that are
// not powers of two go through Bluestein's chirp (fft_chirp, core/prims.js). Dispatch: one invocation per butterfly
// (x < L / 2) and row (y).
//! include prims/lib
//! sampler src rg32f      rows of uL complex values
//! sampler tw rg32f       the twiddles w_j = exp(-2 pi i j / uL), j < uL / 2 (a list, float64 rounded once)
//! image   dst rg32f
//! uniform int uL         the transform length, a power of two
//! uniform int uNs        this stage's half size: 1, 2, 4, ..., uL / 2
//! uniform int uInverse   1: conjugate twiddles (the inverse transform, unscaled)

fn kmain(p: vec2<i32>) {
  let half = u.uL / 2;
  let rows = dst_size().y;
  if (p.x >= half || p.y >= rows) { return; }
  let base = p.y * u.uL;
  let a = src_b[base + p.x];
  let v = src_b[base + p.x + half];
  let k = p.x % u.uNs;
  var w = tw_b[k * (half / u.uNs)];
  if (u.uInverse != 0) { w.y = -w.y; }
  let b = vec2<f32>(v.x * w.x - v.y * w.y, v.x * w.y + v.y * w.x);
  let o = (p.x / u.uNs) * u.uNs * 2 + k;
  dst_b[base + o] = a + b;
  dst_b[base + o + u.uNs] = a - b;
}
