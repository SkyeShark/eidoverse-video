// The port's own kernel (no Blender counterpart): the fields blender/eidoblend/terrain/solvers/strata.py
// op_strata_fluvial() writes at its end (f90c6fc), and zs_field(), which numpy makes in float64:
//     zs = h - zoff
//     K  = K col.k_at(zs)                                   (Column._lerp of the K table, clipped to its ends)
//     Sc = col.tan_at(zs) / (Q facies_factor(zs))           (facies_factor = exp(-strength facies_noise), or 1)
// The table is the column's (1, n, 4) float32 texture (tan, creep, R, K). zs goes through exact()
// (`//! include detail/exact`): at a contact of the column a reordered h - zoff - z0 moves the lookup by a table step
// (kernels/strata_cell.wgsl's header has the measurement). The facies noise is kernels/strata/facies.wgsl, as
// strata_weather's (numpy's twin facies_noise, float32 there too). float32 here, in numpy's order.
//! sampler h
//! sampler zoff
//! sampler kin       the erodibility (par.y; mode 1)
//! sampler par       z: Q, the rock mass's run factor (mode 1)
//! sampler tab       the column's table: (tan, creep, R, K) per step
//! image   outZ r32f
//! image   outK r32f
//! image   outS r32f
//! uniform int uMode     0: zs only, 1: zs, K and Sc
//! uniform float uZ0
//! uniform float uDz
//! uniform int uN
//! uniform vec3 uLv
//! uniform vec4 uFac
//! include strata/facies
//! include detail/exact

fn kmain(p: vec2<i32>) {
  let n = outZ_size();
  if (!inside(p, n)) { return; }
  let zs = exact(h_at(p).x - zoff_at(p).x, exact_zero(n));
  outZ_store(p, vec4<f32>(zs, 0.0, 0.0, 0.0));
  if (u.uMode == 0) { return; }
  let t = clamp((zs - u.uZ0) / u.uDz, 0.0, f32(u.uN) - 1.0);
  let i0 = i32(floor(t));
  let i1 = min(i0 + 1, u.uN - 1);
  let f = t - f32(i0);
  let a = tab_at(vec2<i32>(i0, 0));
  let b = tab_at(vec2<i32>(i1, 0));
  let kc = a.w * (1.0 - f) + b.w * f;
  let tn = a.x * (1.0 - f) + b.x * f;
  var ff = 1.0;
  if (u.uFac.x > 0.0) { ff = exp(-u.uFac.x * facies_noise(world_xy(p, u.uLv), zs, u.uFac)); }
  outK_store(p, vec4<f32>(kin_at(p).x * kc, 0.0, 0.0, 0.0));
  outS_store(p, vec4<f32>(tn / (par_at(p).z * ff), 0.0, 0.0, 0.0));
}
