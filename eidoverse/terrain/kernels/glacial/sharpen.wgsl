// The port's own kernel: blender/eidoblend/terrain/solvers/glacial.py sharpen_walls at f90c6fc (numpy float64 over
// the level, cast to float32 at the end; here float32 in numpy's order):
//   uMode 0  the targets from per-cell cross-sections (trough_target, the level's own cells or its parent's, the 2 x 2
//            block means): outA = zf + max(H prof(rho), fillz(rho)), outB = the bedrock zf + H prof(rho)
//   uMode 1  w = clip(trough_sharp, 0, 1) (1 - smoothstep(clip((rho - 1) / 0.15, 0, 1)))
//              x smoothstep(clip(carve / 5, 0, 1)) (uHasCarve) x (1 - clip(pin_w, 0, 1)) (uHasPin)
//            dh = w (T_own - upsample(T_parent));  h' = h + dh;  bed' = min(bed + w (Tr_own - upsample(Tr_parent)), h + dh)
//            outA = h', outB = bed' (uHasBed), outC = |dh| (for the largest change)
//! include glacial/lib
//! sampler rho              mode 0: trough_rho; mode 1: trough_rho
//! sampler zf               mode 0: trough_zf; mode 1: trough_sharp
//! sampler H                mode 0: trough_H; mode 1: carve
//! sampler ff               mode 0: trough_ff; mode 1: pin_w
//! sampler fill             mode 0: trough_fill; mode 1: h
//! sampler rise             mode 0: trough_rise; mode 1: bed
//! sampler to               mode 1: T_own
//! sampler tp               mode 1: T_parent upsampled
//! sampler ro               mode 1: Tr_own
//! sampler rp               mode 1: Tr_parent upsampled
//! image   outA r32f
//! image   outB r32f
//! image   outC r32f
//! uniform int uMode
//! uniform int uHasCarve
//! uniform int uHasPin
//! uniform int uHasBed
//! uniform float uToe
//! uniform float uLip
//! uniform float uFloorFrac
//! uniform float uFloorRise
//! uniform float uShW
//! uniform float uShH
//! uniform float uShB
//! uniform float uOut

fn smooth3(t: f32) -> f32 { return t * t * (3.0 - 2.0 * t); }

fn kmain(p: vec2<i32>) {
  if (!inside(p, outA_size())) { return; }
  if (u.uMode == 0) {
    let r = rho_at(p).x;
    let z = zf_at(p).x;
    let hh = H_at(p).x;
    let f0 = ff_at(p).x;
    outA_store(p, vec4<f32>(g_target(r, z, hh, f0, fill_at(p).x, rise_at(p).x, false), 0.0, 0.0, 0.0));
    outB_store(p, vec4<f32>(g_target(r, z, hh, f0, 0.0, 0.0, true), 0.0, 0.0, 0.0));
    return;
  }
  let t = clamp((rho_at(p).x - 1.0) / 0.15, 0.0, 1.0);
  var w = clamp(zf_at(p).x, 0.0, 1.0) * (1.0 - smooth3(t));
  if (u.uHasCarve != 0) {
    let c = clamp(H_at(p).x / 5.0, 0.0, 1.0);
    w = w * smooth3(c);
  }
  if (u.uHasPin != 0) { w = w * (1.0 - clamp(ff_at(p).x, 0.0, 1.0)); }
  let hv = fill_at(p).x;
  let dh = w * (to_at(p).x - tp_at(p).x);
  outA_store(p, vec4<f32>(hv + dh, 0.0, 0.0, 0.0));
  if (u.uHasBed != 0) {
    let bed = rise_at(p).x + w * (ro_at(p).x - rp_at(p).x);
    outB_store(p, vec4<f32>(min(bed, hv + dh), 0.0, 0.0, 0.0));
  }
  outC_store(p, vec4<f32>(abs(dh), 0.0, 0.0, 0.0));
}
