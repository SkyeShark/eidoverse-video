// Port of numpy code of blender/eidoblend/terrain/surface/bake.py at d67f19e, as a GPU kernel (the port's own,
// PORT_PLAN.md 3.2). gate: the geometry gates of the gully spectrum (bake.py _Baker._geo_gates), on the padded cell
// grid:
//   uMode 0  square   outF = (t0^2, t1^2, t2^2, t3^2) for the channels uOn names (0 elsewhere): crest's terms at the
//                     gate scales squared, to be blurred at 2 s (blur.wgsl, channel by channel)
//   uMode 1  rms      outF = sqrt(max(a, 0)) channel by channel: the terms' RMS over a Gaussian of 2 s
//   uMode 2  final    outF.c = 1 - smooth(lo, hi, s_c.x) for the channels uOn names (s_c: the made RMS field each
//                     reads), 1 elsewhere: 1 where the level's own height is smooth at that scale, 0 where it already
//                     holds relief of a gully octave's size
// smooth is bake.py's TW.smoothstep with its edges as (float32(lo), float32(hi - lo)) (uEdge).
//! sampler a                   mode 1: the blurred squares
//! sampler t0
//! sampler t1
//! sampler t2
//! sampler t3
//! image   outF rgba32f
//! uniform int uMode
//! uniform ivec4 uOn
//! uniform vec2 uEdge

fn ss(x: f32, e: vec2<f32>) -> f32 {
  let t = clamp((x - e.x) / e.y, 0.0, 1.0);
  return t * t * (3.0 - 2.0 * t);
}

fn kmain(p: vec2<i32>) {
  let n = outF_size();
  if (!inside(p, n)) { return; }
  if (u.uMode == 0) {
    var v = vec4<f32>(0.0);
    if (u.uOn.x != 0) { let t = t0_at(p).x; v.x = t * t; }
    if (u.uOn.y != 0) { let t = t1_at(p).x; v.y = t * t; }
    if (u.uOn.z != 0) { let t = t2_at(p).x; v.z = t * t; }
    if (u.uOn.w != 0) { let t = t3_at(p).x; v.w = t * t; }
    outF_store(p, v);
  } else if (u.uMode == 1) {
    outF_store(p, sqrt(max(a_at(p), vec4<f32>(0.0))));
  } else {
    var v = vec4<f32>(1.0);
    if (u.uOn.x != 0) { v.x = 1.0 - ss(t0_at(p).x, u.uEdge); }
    if (u.uOn.y != 0) { v.y = 1.0 - ss(t1_at(p).x, u.uEdge); }
    if (u.uOn.z != 0) { v.z = 1.0 - ss(t2_at(p).x, u.uEdge); }
    if (u.uOn.w != 0) { v.w = 1.0 - ss(t3_at(p).x, u.uEdge); }
    outF_store(p, v);
  }
}
