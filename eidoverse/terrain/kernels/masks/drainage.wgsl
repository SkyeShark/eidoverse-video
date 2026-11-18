// Port of blender/eidoblend/terrain/masks.py at f90c6fc: compute's flow, channels and wetness, float32 as numpy has
// them:
//   A = max(A, cell^2); log_a = log10(A) - log10(cell)                      (log10 of a = A / cell)
//   flow      clip((log_a - flow_lo) / (flow_hi - flow_lo), 0, 1)
//   channels  smoothstep(lt - 0.7, lt + 0.3, log_a + log10(cell)) dry, lt = log10(threshold area); on sand times
//             1 - smoothstep(sand_swallows_m, sand)
//   wetness   max(clip((twi - twi_lo) / (twi_hi - twi_lo), 0, 1), wet_cell), twi = log_a ln 10 - ln(max(g, 1e-3))
// (log10 is log2 times log10(2): WGSL has no log10; both are within a few float32 steps of numpy's float32 log10.)
//! include masks/lib
//! sampler A             the converged drainage area, m^2
//! sampler geo           (p, q, g, slope)
//! sampler surf          (dry, cover_w, wet_cell, 0)
//! sampler sand          the sand field (uHasSand), else any field
//! image   outF r32f     flow
//! image   outC r32f     channels
//! image   outW r32f     wetness
//! uniform float uCell2      float32(cell^2)
//! uniform float uLogCell    float32(log10(cell))
//! uniform float uFlowLo
//! uniform float uFlowInv    float32(1 / max(flow_hi - flow_lo, 1e-6))
//! uniform vec2 uCh          smoothstep(lt - 0.7, lt + 0.3): (e0, k)
//! uniform int uHasSand
//! uniform vec2 uSand        smoothstep(sand_swallows_m): (e0, k)
//! uniform float uTwiLo
//! uniform float uTwiInv     float32(1 / max(twi_hi - twi_lo, 1e-6))
//! uniform float uLn10       float32(ln 10)

fn kmain(p: vec2<i32>) {
  let n = outF_size();
  if (!inside(p, n)) { return; }
  let a = max(A_at(p).x, u.uCell2);
  let log_a = log10f(a) - u.uLogCell;
  let s = surf_at(p);
  outF_store(p, vec4<f32>(clamp((log_a - u.uFlowLo) * u.uFlowInv, 0.0, 1.0), 0.0, 0.0, 0.0));
  var ch = ss(log_a + u.uLogCell, u.uCh) * s.x;
  if (u.uHasSand != 0) { ch = ch * (1.0 - ss(sand_at(p).x, u.uSand)); }
  outC_store(p, vec4<f32>(ch, 0.0, 0.0, 0.0));
  let twi = log_a * u.uLn10 - log(max(geo_at(p).z, 1e-3));
  let tw = clamp((twi - u.uTwiLo) * u.uTwiInv, 0.0, 1.0);
  outW_store(p, vec4<f32>(max(tw, s.z), 0.0, 0.0, 0.0));
}
