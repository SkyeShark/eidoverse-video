// Port of blender/eidoblend/terrain/kernels/jump_flood.glsl at f90c6fc.
//
// Transcribed statement for statement from the GLSL (PORT_PLAN.md 4.2); the `//!` header is the GLSL's, unchanged.
// The changes are WGSL's: texelFetch(x, q, 0) is x_at(q), imageStore is outC_store, textureSize is candT_size(), the
// uniforms are u.<name>; the `out float sid` of metric() and the `inout float[4]` arrays of offer() are pointers;
// the GLSL's local names `u` (cliff's 1 - t, offer's shift index) are `s` and `v` here, since `u` is the uniforms.
// solvers/glacial.js jumpFloodRun drives it.
//
/* jump_flood (design section 4.5, step 4; Rong & Tan 2006): one jump-flooding pass. Every cell keeps the four best
   seeds of DIFFERENT streams it has heard of (candT: their packed cell indices i + j n.x as floats, best first, -1
   none) and hears the candidates of the 8 cells uStep away; all are ranked here by the metric, then by index (so a
   tie resolves the same way everywhere):
       uMetric 0: the trough's target height at this cell, zf + max(H prof(r / W), fillz(r / W)): a lower
                  envelope, so a trunk's trough wins over a nearer tributary's, and a step in a floor becomes a riegel
       uMetric 1: the distance r (the test against a brute-force twin)
   prof(rho) = 0 on the floor (rho <= ff), cliff((rho - ff) / (1 - ff)) up the wall to the lip (rho = 1: a cliff
   whose slope ramps up over its toe, uToe of its run, stands at its steepest across the core and eases off over its
   lip, uLip), then the shoulder 1 + uShH ((rho - 1) / uShW)^uShB (a bench uShW W wide rising uShH H to its outer
   edge; uShW 0: none), then the upper wall up to the trimline, rising uOut H per W (so the carve ends at the
   trimline instead of planing the ridges beyond). ff = uFloorFrac seedC.x, the seed's own floor share (a
   tributary's floor is narrower than the trunk's: solvers/glacial.py centrelines). fillz(rho) = fill + rise H
   min(rho / ff, 1)^2, rise = uFloorRise seedC.y: the valley fill's top, rising from the river to the foot of the
   walls by the seed's own fans and aprons (they differ along the valley).
   One entry per stream, so the U-carve's smooth minimum joins different troughs and never a stream's neighbouring
   seeds (which would sink every floor by a quarter of the join width). Steps uStep = 2^k ... 2, 1, then 1 again
   (solvers/glacial.py jfa_steps). Twin: solvers/glacial.py jump_flood. */
//! sampler candT       xyzw: four candidate seeds (packed cell index as float; -1 none), best first
//! sampler seedA       per seed cell: x, y (m from the grid's corner), zf (the floor under the fill), H (wall, m)
//                      (cell (i, j)'s centre is ((i + .5) dx, (j + .5) dx); H runs from the floor to the lip)
//! sampler seedB       per seed cell: W (half-width, m), stream id, fill (m above zf), moraine (m)
//! sampler seedC       per seed cell: the floor share's factor (x uFloorFrac), the fans' factor (x uFloorRise),
//                      the shoulder cut (a share of H: u_carve.glsl), unused
//! image   outC rgba32f
//! uniform int uStep   the jump, cells
//! uniform float uDx   the cell, metres
//! uniform float uToe  the share of the wall's run over which its slope ramps up from the floor
//! uniform float uLip  the share over which it eases off into the shoulder
//! uniform float uFloorFrac  the floor's share of the half-width (the wall starts there)
//! uniform float uFloorRise  the fill's rise from the river to the foot of the walls, a share of H
//! uniform float uShW  the shoulder's width, a share of the half-width W (0: no shoulder)
//! uniform float uShH  the shoulder's rise to its outer edge, a share of H
//! uniform float uShB  the shoulder's exponent
//! uniform float uOut  the upper wall beyond the shoulder: its rise in H per W
//! uniform int uMetric 0: the target height; 1: the distance

fn cliff(t0: f32) -> f32 {
  let t = clamp(t0, 0.0, 1.0);
  let c = 1.0 / (1.0 - 0.5 * (u.uToe + u.uLip));
  if (t < u.uToe) { return c * t * t / (2.0 * max(u.uToe, 1e-6)); }
  if (t > 1.0 - u.uLip) {
    let s = 1.0 - t;
    return 1.0 - c * s * s / (2.0 * max(u.uLip, 1e-6));
  }
  return c * (t - 0.5 * u.uToe);
}

fn prof(rho: f32, ff: f32) -> f32 {
  if (rho <= 1.0) { return cliff((rho - ff) / (1.0 - ff)); }
  if (u.uShW <= 0.0) { return 1.0 + u.uOut * (rho - 1.0); }
  let s = (rho - 1.0) / u.uShW;
  if (s <= 1.0) { return 1.0 + u.uShH * pow(s, u.uShB); }
  return 1.0 + u.uShH + u.uOut * (rho - 1.0 - u.uShW);
}

fn fillz(rho: f32, fill: f32, H: f32, ff: f32, rise: f32) -> f32 {
  let t = min(rho / max(ff, 1e-3), 1.0);
  return fill + rise * H * t * t;
}

fn metric(ci: i32, n: vec2<i32>, xp: vec2<f32>, sid: ptr<function, f32>) -> f32 {
  let c = vec2<i32>(ci % n.x, ci / n.x);
  let a = seedA_at(c);
  let b = seedB_at(c);
  let e = seedC_at(c);
  *sid = b.y;
  let d = xp - a.xy;
  let r = sqrt(d.x * d.x + d.y * d.y);
  if (u.uMetric == 1) { return r; }
  let rho = r / b.x;
  let ff = clamp(u.uFloorFrac * e.x, 0.0, 0.95);
  return a.z + max(a.w * prof(rho, ff), fillz(rho, b.z, a.w, ff, u.uFloorRise * e.y));
}

/* (ci, m, sid) into the sorted list: one entry per stream (the better kept), the four best streams */
fn offer(bi: ptr<function, array<f32, 4>>, bm: ptr<function, array<f32, 4>>, bs: ptr<function, array<f32, 4>>,
         ci: f32, m: f32, sid: f32) {
  for (var t = 0; t < 4; t++) {
    if ((*bi)[t] >= 0.0 && (*bs)[t] == sid) {
      if (!(m < (*bm)[t] || (m == (*bm)[t] && ci < (*bi)[t]))) { return; }
      for (var v = t; v < 3; v++) {
        (*bi)[v] = (*bi)[v + 1];
        (*bm)[v] = (*bm)[v + 1];
        (*bs)[v] = (*bs)[v + 1];
      }
      (*bi)[3] = -1.0;
      (*bm)[3] = 3.0e38;
      (*bs)[3] = -1.0;
      break;
    }
  }
  var at = 4;
  for (var t = 0; t < 4; t++) {
    if (at == 4 && ((*bi)[t] < 0.0 || m < (*bm)[t] || (m == (*bm)[t] && ci < (*bi)[t]))) { at = t; }
  }
  if (at == 4) { return; }
  for (var t = 3; t > at; t--) {
    (*bi)[t] = (*bi)[t - 1];
    (*bm)[t] = (*bm)[t - 1];
    (*bs)[t] = (*bs)[t - 1];
  }
  (*bi)[at] = ci;
  (*bm)[at] = m;
  (*bs)[at] = sid;
}

fn kmain(p: vec2<i32>) {
  let n = candT_size();
  if (!inside(p, n)) { return; }
  let xp = (vec2<f32>(p) + 0.5) * u.uDx;
  var bi = array<f32, 4>(-1.0, -1.0, -1.0, -1.0);
  var bm = array<f32, 4>(3.0e38, 3.0e38, 3.0e38, 3.0e38);
  var bs = array<f32, 4>(-1.0, -1.0, -1.0, -1.0);
  for (var oy = -1; oy <= 1; oy++) {
    for (var ox = -1; ox <= 1; ox++) {
      let q = p + vec2<i32>(ox, oy) * u.uStep;
      if (!inside(q, n)) { continue; }
      let c4 = candT_at(q);
      for (var t = 0; t < 4; t++) {
        let ci = c4[t];
        if (ci < 0.0) { continue; }
        var sid: f32;
        let m = metric(i32(ci), n, xp, &sid);
        offer(&bi, &bm, &bs, ci, m, sid);
      }
    }
  }
  outC_store(p, vec4<f32>(bi[0], bi[1], bi[2], bi[3]));
}
