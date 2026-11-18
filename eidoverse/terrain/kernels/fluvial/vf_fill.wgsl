// The port's own kernel (no Blender counterpart): the fill of blender/eidoblend/terrain/solvers/fluvial.py
// op_valley_floor at f90c6fc, which numpy makes in float64:
//   uMode 0   tgt = F[t] + cross_slope min(dist, W[t] / 2);  fill = where(chan[t], max(tgt - h, 0), 0)
//   uMode 1   with the toe (the fill and its Gaussian, `fb`) and the pins: dh = max(fill, fb), then
//             hn = pin_apply(h + dh) = h + dh (1 - w) + (pin_h - h) w  (w = clip(pin_w, 0, 1)), formed from h so the
//             added sediment max(hn - h, 0) is numpy's float64 difference within a float32 step of its own size
//             outF: hn, outA: max(hn - h, 0)
//! sampler t r32ui
//! sampler dist
//! sampler chan
//! sampler h
//! sampler W
//! sampler F           mode 0: the raised floors; mode 1: the fill
//! sampler fb          mode 1: the fill's Gaussian (uToe 1)
//! sampler pins        mode 1: (pin_w, pin_h) (uPins 1)
//! image   outF r32f
//! image   outA r32f
//! uniform int uMode
//! uniform float uCross
//! uniform int uToe
//! uniform int uPins

fn kmain(p: vec2<i32>) {
  let n = h_size();
  if (!inside(p, n)) { return; }
  let i = p.y * n.x + p.x;
  let h = h_at(p).x;
  if (u.uMode == 0) {
    let ti = t_b[i];
    var fill = 0.0;
    if (chan_b[ti] > 0.5) {
      let tgt = F_b[ti] + u.uCross * min(dist_b[i], 0.5 * W_b[ti]);
      fill = max(tgt - h, 0.0);
    }
    outF_store(p, vec4<f32>(fill, 0.0, 0.0, 0.0));
    return;
  }
  var dh = F_at(p).x;
  if (u.uToe == 1) { dh = max(dh, fb_at(p).x); }
  if (u.uPins == 1) {
    let pn = pins_at(p);
    let w = clamp(pn.x, 0.0, 1.0);
    dh = dh * (1.0 - w) + (pn.y - h) * w;
  }
  outF_store(p, vec4<f32>(h + dh, 0.0, 0.0, 0.0));
  outA_store(p, vec4<f32>(max(dh, 0.0), 0.0, 0.0, 0.0));
}
