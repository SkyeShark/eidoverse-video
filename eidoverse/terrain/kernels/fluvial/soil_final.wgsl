// The port's own kernel (no Blender counterpart): the last lines of blender/eidoblend/terrain/solvers/hillslope.py
// op_soil_hills at f90c6fc, which numpy computes in float64 before rounding each field to float32:
//     hs = h + soft_cap(hs - h, cap)        (cap > 0)
//     hn = h + blend (hs - h) [- cut]
//     outH = hn,  outD = hn - bed           (the caller then takes bed = min(bed, hn), deposit and talus =
//                                            min(x, hn - bed): kernels/fluvial/ew.wgsl modes 17 and 18)
// numpy subtracts bed from the unrounded float64 hn; rounding hn to float32 first would leave the clamped deposit up
// to half a float32 step of hn off (1.5e-5 m at 250 m). So hn - bed is formed here as (h - bed) + the change, which
// keeps it within a step of its own size.
//! sampler h       the held surface the solve started from
//! sampler hs      the solved surface
//! sampler cut     the rill cut (uCut 1)
//! sampler bed     (uBed 1)
//! image   outH r32f
//! image   outD r32f
//! uniform float uCap
//! uniform float uBlend
//! uniform int uCut
//! uniform int uBed

fn soft_cap(r: f32, cap: f32) -> f32 {
  let half = 0.5 * cap;
  if (r <= half) { return r; }
  return half + half * tanh((r - half) / max(half, 1e-12));
}

fn kmain(p: vec2<i32>) {
  if (!inside(p, outH_size())) { return; }
  let h = h_at(p).x;
  var r = hs_at(p).x - h;
  if (u.uCap > 0.0) { r = soft_cap(r, u.uCap); }
  var t = u.uBlend * r;
  if (u.uCut == 1) { t = t - cut_at(p).x; }
  outH_store(p, vec4<f32>(h + t, 0.0, 0.0, 0.0));
  var d = 0.0;
  if (u.uBed == 1) { d = (h - bed_at(p).x) + t; }
  outD_store(p, vec4<f32>(d, 0.0, 0.0, 0.0));
}
