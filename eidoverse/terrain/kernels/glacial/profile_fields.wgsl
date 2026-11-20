// The port's own kernel: blender/eidoblend/terrain/solvers/glacial.py profile_fields at f90c6fc, the trough's
// cross-section at every cell from the jump flood's first two candidates (what every finer level re-evaluates its
// walls from, sharpen_walls):
//     T_c = the candidate's target (_metric64), inf where the slot is empty
//     trough_zf, _H, _fill = the first candidate's zf, H, fill;  trough_ff, _rise = seed_floor of its seedC (0 where
//     the slot is empty)
//     first = the slot is filled and rho >= r / max(W, 1e-6) - 1e-4 (no cirque decides the cell: u_carve's rho fell
//     under the seed's own there)
//     trough_sharp = clip((T_1 - T_0) / max(join_m, 1e-6), 0, 1) where first (1 when there is no second), else 0
// numpy is float64; this is float32 (glacial/lib's cross-section), in numpy's order.
//! include glacial/lib
//! sampler cand             the jump flood's candidates
//! sampler seedA
//! sampler seedB
//! sampler seedC
//! sampler rho              u_carve's rho (outS.z)
//! image   outZf r32f       trough_zf
//! image   outH r32f        trough_H
//! image   outFf r32f       trough_ff
//! image   outFill r32f     trough_fill
//! image   outRise r32f     trough_rise
//! image   outSharp r32f    trough_sharp
//! uniform float uDx
//! uniform float uJoin      join_m
//! uniform float uToe
//! uniform float uLip
//! uniform float uFloorFrac
//! uniform float uFloorRise
//! uniform float uShW
//! uniform float uShH
//! uniform float uShB
//! uniform float uOut

const INF: f32 = 0x1.fffffep+127f;

fn kmain(p: vec2<i32>) {
  let n = cand_size();
  if (!inside(p, n)) { return; }
  let xp = (vec2<f32>(p) + 0.5) * u.uDx;
  let c4 = cand_at(p);
  var T = array<f32, 2>(INF, INF);
  var zf = 0.0;
  var H = 0.0;
  var ff0 = 0.0;
  var fill = 0.0;
  var rise0 = 0.0;
  var first = false;
  for (var c = 0; c < 2; c++) {
    let ci = c4[c];
    if (ci < 0.0) { continue; }
    let ii = i32(ci);
    let cp = vec2<i32>(ii % n.x, ii / n.x);
    let a = seedA_at(cp);
    let b = seedB_at(cp);
    let e = seedC_at(cp);
    let d = xp - a.xy;
    let r = sqrt(d.x * d.x + d.y * d.y);
    let fr = g_seed_floor(e);
    let rho = r / b.x;
    T[c] = a.z + max(a.w * g_prof(rho, fr.x), g_fillz(rho, b.z, a.w, fr.x, fr.y));
    if (c == 0) {
      zf = a.z;
      H = a.w;
      ff0 = fr.x;
      fill = b.z;
      rise0 = fr.y;
      let own = r / max(b.x, 1e-6);
      first = !(rho_at(p).x < own - 1e-4);
    }
  }
  var gap = 1.0;
  if (T[1] < INF) { gap = (T[1] - T[0]) / max(u.uJoin, 1e-6); }
  var sharp = 0.0;
  if (first) { sharp = clamp(gap, 0.0, 1.0); }
  outZf_store(p, vec4<f32>(zf, 0.0, 0.0, 0.0));
  outH_store(p, vec4<f32>(H, 0.0, 0.0, 0.0));
  outFf_store(p, vec4<f32>(ff0, 0.0, 0.0, 0.0));
  outFill_store(p, vec4<f32>(fill, 0.0, 0.0, 0.0));
  outRise_store(p, vec4<f32>(rise0, 0.0, 0.0, 0.0));
  outSharp_store(p, vec4<f32>(sharp, 0.0, 0.0, 0.0));
}
