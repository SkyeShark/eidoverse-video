// finish_h: a detail op's height and bed written into the level, cell by cell (the port's own kernel, PORT_PLAN.md
// 3.2: numpy code of blender/eidoblend/terrain/solvers/hydraulic.py finish() at f90c6fc moved to the GPU). It
// replaces
//   w = clip(pin_w, 0, 1); keep = 1 - w
//   moved = anchor(h_new - h_base, scale) - (h_new - h_base)          (with an anchor: -lp, lp the change's low-pass)
//   h_new += moved; bed_new += moved
//   h   = h_new * keep + pin_h * w
//   bed = min(min(bed_new, h_new) * keep + pin_h * w, h)
// numpy holds h_new = h_base + change in float64; here the surface is h_in + (seedK seed + (change - lp)): the
// metre-scale height and the small terms are added once, so float32 keeps the change's digits (h_base = h_in +
// seedK seed: op_hydraulic's micro-relief kept on fine levels; uAbs: the change is a whole new surface, op_planation's).
// bed_new is h_base + its own change (uBedMode 0), a surface of its own (1: op_gully's bed field, op_planation's
// min(bed, h)) or h_new itself (2). Graded against numpy's float64.
//! sampler hin           x: the height the op started from, metres (h_base without the seed)
//! sampler seed          x: the micro-relief seed, metres (uSeedK != 0)
//! sampler x             x: the change h_new - h_base, metres (uAbs: h_new itself)
//! sampler lp            x: the change's low-pass, metres (uHasLp: the anchor)
//! sampler bed           x: bed_new - h_base (uBedMode 0) or bed_new (1), metres
//! sampler pw            x: the pin weight (uHasPin)
//! sampler ph            x: the pin height, metres (uHasPin)
//! image   outH r32f
//! image   outBed r32f
//! uniform float uSeedK
//! uniform int uAbs
//! uniform int uHasLp
//! uniform int uBedMode
//! uniform int uHasPin

fn kmain(p: vec2<i32>) {
  let n = outH_size();
  if (!inside(p, n)) { return; }
  let h0 = hin_at(p).x;
  var sd = 0.0;
  if (u.uSeedK != 0.0) { sd = u.uSeedK * seed_at(p).x; }
  var lp = 0.0;
  if (u.uHasLp != 0) { lp = lp_at(p).x; }
  var hn: f32;
  if (u.uAbs != 0) {
    hn = x_at(p).x - lp;
  } else {
    hn = h0 + (sd + (x_at(p).x - lp));
  }
  var bn: f32;
  if (u.uBedMode == 0) {
    bn = h0 + (sd + (bed_at(p).x - lp));
  } else if (u.uBedMode == 1) {
    bn = bed_at(p).x - lp;
  } else {
    bn = hn;
  }
  var w = 0.0;
  var ph = 0.0;
  if (u.uHasPin != 0) {
    w = clamp(pw_at(p).x, 0.0, 1.0);
    ph = ph_at(p).x;
  }
  let keep = 1.0 - w;
  let h = hn * keep + ph * w;
  outH_store(p, vec4<f32>(h, 0.0, 0.0, 0.0));
  outBed_store(p, vec4<f32>(min(min(bn, hn) * keep + ph * w, h), 0.0, 0.0, 0.0));
}
