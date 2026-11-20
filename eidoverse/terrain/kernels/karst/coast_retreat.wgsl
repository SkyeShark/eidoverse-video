// Port of blender/eidoblend/terrain/solvers/coast.py retreat_field, stack_weight's ramp and scar_field (with _hash_u)
// at f90c6fc, and op_coast's phi = d0 - R, as a kernel over a level's cells (numpy's float64 is float32 here):
//     f       = clip(clip(E / 0.5, 1e-3, None) ** exposure_power, *exposure_clamp)
//     w       = exp(weakness n_weak)                   (n: _unit_noise, made by the world noise kernel; 1 when none)
//     stack_w = stacks smoothstep(0.55, 0.8, ridged)    (0 when stacks is 0)
//     R       = retreat_m f w (1 - 0.85 stack_w) + crenel_m n_crenel + bite
//     bite    = the deepest scar's bite at the cell: on a lattice of scar_spacing_m, a cell holds a scar when its
//               hash's first number is under `scars`; jittered inside it, radius and depth from its hash, the bite
//               depth (1 - (d / radius)^2)^1.5 (q^1.5 as q sqrt(q))
// The scar lattice's coordinates come split (per column and per row: X / spacing's integer cell and fraction,
// doubles on the CPU), so the jittered centres' offsets are float32 of small numbers. The PCG chain is exact.
// outR: (R, phi = d0 - R, bite, stack_w).

//! sampler E
//! sampler d0
//! sampler wk                weakness noise (uFlags 1)
//! sampler cr                crenel noise (uFlags 2)
//! sampler sk                the stacks' ridged noise (uFlags 4)
//! sampler sx rg32f          row 0: per column (cell, fraction) of X / scar_spacing_m; row 1: per row, of Y
//! image   outR rgba32f
//! uniform int uFlags        1 weakness, 2 crenel, 4 stacks, 8 scars
//! uniform float uRetreat
//! uniform float uPower
//! uniform float uLo
//! uniform float uHi
//! uniform float uWeak
//! uniform float uStacks
//! uniform float uCrenel
//! uniform float uScars
//! uniform float uSp
//! uniform float uRlo
//! uniform float uRhi
//! uniform float uDlo
//! uniform float uDhi
//! uniform int uSalt         seed x 7919 + 1907 (its bits)
//! uniform int uSalt2        seed x 7919 + 1913
fn hash_u(cx: i32, cy: i32, salt: u32, k: u32) -> f32 {
  var h = pcg(bitcast<u32>(cx) + pcg(bitcast<u32>(cy) + salt));
  for (var i = 0u; i <= k; i++) { h = pcg(h); }
  return f32(h & 0xFFFFFFu) / 16777215.0;
}

fn kmain(p: vec2<i32>) {
  let n = outR_size();
  if (!inside(p, n)) { return; }
  var f = max(E_at(p).x / 0.5, 1e-3);
  if (u.uPower != 1.0) { f = pow(f, u.uPower); }
  f = clamp(f, u.uLo, u.uHi);
  var w = 1.0;
  if ((u.uFlags & 1) != 0) { w = exp(u.uWeak * wk_at(p).x); }
  var R = u.uRetreat * f * w;
  var sw = 0.0;
  if ((u.uFlags & 4) != 0) {
    let t = clamp((sk_at(p).x - 0.55) / 0.25, 0.0, 1.0);
    sw = u.uStacks * (t * t * (3.0 - 2.0 * t));
  }
  R = R * (1.0 - 0.85 * sw);
  if ((u.uFlags & 2) != 0) { R = R + u.uCrenel * cr_at(p).x; }
  var bite = 0.0;
  if ((u.uFlags & 8) != 0) {
    let gx = sx_at(vec2<i32>(p.x, 0)).xy;
    let gy = sx_at(vec2<i32>(p.y, 1)).xy;
    let ix = i32(gx.x);
    let iy = i32(gy.x);
    let s1 = bitcast<u32>(u.uSalt);
    let s2 = bitcast<u32>(u.uSalt2);
    for (var dj = -1; dj <= 1; dj++) {
      for (var di = -1; di <= 1; di++) {
        let cx = ix + di;
        let cy = iy + dj;
        let ux = hash_u(cx, cy, s1, 0u);
        let uy = hash_u(cx, cy, s1, 1u);
        let ur = hash_u(cx, cy, s1, 2u);
        let ud = hash_u(cx, cy, s1, 3u);
        let keep = hash_u(cx, cy, s2, 0u) < u.uScars;
        let ex = (gx.y - f32(di) - (0.1 + 0.8 * ux)) * u.uSp;
        let ey = (gy.y - f32(dj) - (0.1 + 0.8 * uy)) * u.uSp;
        let r = u.uRlo + (u.uRhi - u.uRlo) * ur;
        let q = clamp(1.0 - (ex * ex + ey * ey) / (r * r), 0.0, 1.0);
        if (keep) { bite = max(bite, (u.uDlo + (u.uDhi - u.uDlo) * ud) * (q * sqrt(q))); }
      }
    }
  }
  R = R + bite;
  outR_store(p, vec4<f32>(R, d0_at(p).x - R, bite, sw));
}
