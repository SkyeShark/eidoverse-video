// Port of blender/eidoblend/terrain/core/metrics.py at f90c6fc: radial_spectrum's preparation of the field: the
// least-squares plane taken off, then the Hann window (np.outer(np.hanning(ny), np.hanning(nx))).
//
// Two modes:
//   0  the terms of the plane fit: (z - z0, (i - ic)(z - z0), (j - jc)(z - z0), 0). core/metrics.js sums them
//      (float32, fixed tree) and solves the normal equations in doubles. numpy solves [i, j, 1] by lstsq; on a
//      regular grid the centred regressors are orthogonal, so the same plane comes from three sums. z0 is the field's
//      mean (a number read before): the sums are then of small numbers, not of differences of large ones.
//   1  the windowed residual: ((z - z0) - (a (i - ic) + b (j - jc) + d)) * (wy[j] * wx[i]), the plane written
//      about the centre and the mean. The Hann weights are tables (float64 on the CPU, one row each).
//! sampler z
//! sampler wx               np.hanning(nx) as a row (mode 1; any field in mode 0)
//! sampler wy               np.hanning(ny) as a row
//! image   outF rgba32f     mode 0: the terms; mode 1: x = the windowed residual
//! uniform int uMode
//! uniform float uZ0        the field's mean
//! uniform float uIc        (nx - 1) / 2
//! uniform float uJc        (ny - 1) / 2
//! uniform float uA         the plane's slope per column
//! uniform float uB         the plane's slope per row
//! uniform float uD         the plane at the centre, less z0

fn kmain(p: vec2<i32>) {
  let n = z_size();
  if (!inside(p, n)) { return; }
  let dz = z_at(p).x - u.uZ0;
  let di = f32(p.x) - u.uIc;
  let dj = f32(p.y) - u.uJc;
  if (u.uMode == 0) {
    outF_store(p, vec4<f32>(dz, di * dz, dj * dz, 0.0));
    return;
  }
  let r = dz - (u.uA * di + u.uB * dj + u.uD);
  outF_store(p, vec4<f32>(r * (wy_b[p.y] * wx_b[p.x]), 0.0, 0.0, 0.0));
}
