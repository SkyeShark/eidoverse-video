// Port of blender/eidoblend/terrain/masks.py at f90c6fc: compute's peaks at one scale, float32 as numpy has it:
//   hc = h - mu, rise = hc - b, std = sqrt(max(b2 - b b, floor^2)),
//   pk = max(pk, smoothstep(dev[0], dev[1], rise / std) smoothstep(rise[0] s, rise[1] s, rise))
// (b and b2 the centred height and its square blurred at the scale, at the kept cells); after the last scale
// peaks = pk smoothstep(height_norm[0], height_norm[1], height_norm).
//! include masks/lib
//! sampler h
//! sampler b             the blurred h - mu
//! sampler b2            the blurred (h - mu)^2
//! sampler pk            the maximum over the scales before this one (ignored at the first)
//! sampler hn            height_norm
//! image   outF r32f
//! uniform float uMu     float32(h.mean())
//! uniform float uFloor2 float32(peaks_std_floor_m^2)
//! uniform vec2 uDev     smoothstep(peaks_dev): (e0, k)
//! uniform vec2 uRise    smoothstep(peaks_rise s): (e0, k)
//! uniform int uFirst    1: no scale before this one
//! uniform int uLast     1: times the height band
//! uniform vec2 uHn      smoothstep(peaks_height_norm): (e0, k)

fn kmain(p: vec2<i32>) {
  let n = outF_size();
  if (!inside(p, n)) { return; }
  let hc = h_at(p).x - u.uMu;
  let bb = b_at(p).x;
  let rise = hc - bb;
  let sd = sqrt(max(b2_at(p).x - bb * bb, u.uFloor2));
  let v = ss(rise / sd, u.uDev) * ss(rise, u.uRise);
  var pk = v;
  if (u.uFirst == 0) { pk = max(pk_at(p).x, v); } else { pk = max(0.0, v); }
  if (u.uLast != 0) { pk = pk * ss(hn_at(p).x, u.uHn); }
  outF_store(p, vec4<f32>(pk, 0.0, 0.0, 0.0));
}
