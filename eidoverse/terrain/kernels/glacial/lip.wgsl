// The port's own kernel: blender/eidoblend/terrain/solvers/glacial.py lip_open at f90c6fc and refine_level's use of
// it (numpy float64; here float32 in numpy's order). The opening itself (_filter1d's square minimum, then maximum,
// edges repeated) is core/prims.js dilate (min, then max): exact.
//   uMode 0  band = smoothstep(clip((rho - lo) / 0.05, 0, 1)) smoothstep(clip((hi - rho) / 0.15, 0, 1)): outA = band
//   uMode 1  drop = band max(h - opening, 0);  free = 1 - clip(pin_w, 0, 1)
//            outA = h - free drop;  outB = min(bed, h - free drop) (uHasBed);  outC = free drop
//! sampler rho
//! sampler h
//! sampler op               mode 1: the opening of h
//! sampler band             mode 1: mode 0's band
//! sampler pin              mode 1: pin_w
//! sampler bed              mode 1: bed (uHasBed)
//! image   outA r32f
//! image   outB r32f
//! image   outC r32f
//! uniform int uMode
//! uniform float uLo
//! uniform float uHi
//! uniform int uHasBed

fn smooth3(t: f32) -> f32 { return t * t * (3.0 - 2.0 * t); }

fn kmain(p: vec2<i32>) {
  if (!inside(p, outA_size())) { return; }
  if (u.uMode == 0) {
    let r = rho_at(p).x;
    let t0 = clamp((r - u.uLo) / 0.05, 0.0, 1.0);
    let t1 = clamp((u.uHi - r) / 0.15, 0.0, 1.0);
    outA_store(p, vec4<f32>(smooth3(t0) * smooth3(t1), 0.0, 0.0, 0.0));
    return;
  }
  let hv = h_at(p).x;
  let drop = band_at(p).x * max(hv - op_at(p).x, 0.0);
  let fd = (1.0 - clamp(pin_at(p).x, 0.0, 1.0)) * drop;
  let h1 = hv - fd;
  outA_store(p, vec4<f32>(h1, 0.0, 0.0, 0.0));
  if (u.uHasBed != 0) { outB_store(p, vec4<f32>(min(bed_at(p).x, h1), 0.0, 0.0, 0.0)); }
  outC_store(p, vec4<f32>(fd, 0.0, 0.0, 0.0));
}
