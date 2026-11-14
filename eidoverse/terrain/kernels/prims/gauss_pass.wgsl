// gauss_pass: one axis of a Gaussian blur, computed as the Blender edition's FFT blurs compute it (PORT_PLAN.md
// 3.4). blender/eidoblend/terrain at f90c6fc blurs by FFT: solvers/hillslope.py gaussian_blur pads the field by
// reflection (np.pad 'reflect', ceil(4 sigma) cells a side), masks.py gaussian_blur extends it by holding its last
// row and column (np.pad 'edge') to a fast FFT length, and both multiply the spectrum by exp(-2 pi^2 sigma^2 f^2) on
// numpy's frequencies (fftfreq, rfftfreq). That is a circular convolution over the extended axis with the inverse
// DFT of the transfer function, g[m] = (1 / N) sum_k G(f_k) cos(2 pi k m / N): separable, and core/prims.js
// computes g in float64 from those frequencies. This pass sums g[m] times the extended field at (t - m) mod N for
// every kept cell t, over the offsets uLo..uHi where g is not negligible (every offset once when it is not). The
// sum runs over differences from the cell's own value, so float32 keeps the digits of the relief, not of the
// altitude. Deviation (the plan's: per-texel work as GPU compute): a direct convolution instead of an FFT; its
// oracle is the FFT blur itself.
//! include prims/lib
//! sampler src           the field (channel uChannel), or the first pass's output for the second
//! sampler taps r32f     g[0], g[1], ...: the kernel, a list (g[-m] = g[m])
//! image   outB r32f     the blurred axis, the field's size
//! uniform int uAxis     0: along a row (x), 1: along a column (y)
//! uniform int uLo       the first offset (<= 0)
//! uniform int uHi       the last offset (>= 0)
//! uniform int uPeriod   N: the length of the extended axis the FFT is circular over
//! uniform int uPad      cells of extension before the field on this axis (reflection); 0 for the held edge
//! uniform int uMode     0: reflection; 1: the field, then its last cell held
//! uniform int uChannel

fn kmain(p: vec2<i32>) {
  let n = outB_size();
  if (!inside(p, n)) { return; }
  let ns = src_size();
  let len = select(ns.y, ns.x, u.uAxis == 0);
  let t = select(p.y, p.x, u.uAxis == 0) + u.uPad;
  let c = src_at(p)[u.uChannel];
  let N = u.uPeriod;
  var acc = 0.0;
  for (var m = u.uLo; m <= u.uHi; m++) {
    // t is in [0, N) and |m| <= N / 2: one step folds t - m onto the circle (no % of a negative number)
    var e = t - m;
    if (e < 0) { e += N; } else if (e >= N) { e -= N; }
    var s = min(e, len - 1);
    if (u.uMode == 0) { s = reflect_index(e - u.uPad, len); }
    var q = p;
    if (u.uAxis == 0) { q.x = s; } else { q.y = s; }
    acc += taps_b[abs(m)] * (src_at(q)[u.uChannel] - c);
  }
  outB_store(p, vec4<f32>(c + acc, 0.0, 0.0, 0.0));
}
