// Port of blender/eidoblend/terrain/masks.py at f90c6fc: compute's height_norm, clip((h - h_lo) / (h_hi - h_lo), 0, 1)
// with the main tile's Norms (numpy float64, rounded once; here float32).
//! sampler h
//! image   outF r32f
//! uniform float uLo     float32(norms.h_lo) (an exact float32: the lowest height)
//! uniform float uInv    float32(1 / max(h_hi - h_lo, 1e-6))

fn kmain(p: vec2<i32>) {
  let n = outF_size();
  if (!inside(p, n)) { return; }
  outF_store(p, vec4<f32>(clamp((h_at(p).x - u.uLo) * u.uInv, 0.0, 1.0), 0.0, 0.0, 0.0));
}
