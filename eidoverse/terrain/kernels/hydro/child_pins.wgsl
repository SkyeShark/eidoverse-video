// Port of blender/eidoblend/terrain/run.py child_pins at f90c6fc (its pin weight and value; the inflow is
// inflow.wgsl): a child level's border band holds the inherited surface, weight 1 on the outer SEAM_HOLD cells,
// easing to 0 at `band` cells in, and every sea cell (h_start <= sea level) is held at min(h, sea level).
//     d = edge_distance(n);  t = clip((d - SEAM_HOLD) / max(band - SEAM_HOLD, 1), 0, 1);  w = 1 - t^2 (3 - 2t)
// The weight depends on the integer d alone, so run.js computes it for d = 0 .. band in doubles exactly as numpy
// does and rounds it to float32 once (the `ramp` table): every weight is numpy's to the bit. numpy compares the
// float32 h_start with the Python-float sea level in float32 (the level rounded to nearest, numpy 2's rule for a
// Python scalar beside a float32 array), so uSea32 is that rounding, and np.minimum takes F32(sea_level).
//! sampler h                h_start: the child's inherited height
//! sampler ramp             the band's weights: ramp[d] for d = 0 .. band; beyond the table the weight is 0
//! image   outW r32f        pin_w
//! image   outH r32f        pin_h
//! uniform int uRamp        the table's length
//! uniform int uSea         1 with a sea level
//! uniform float uSea32     float32(sea level)

fn kmain(p: vec2<i32>) {
  let n = h_size();
  if (!inside(p, n)) { return; }
  let e = min(min(p.x, n.x - 1 - p.x), min(p.y, n.y - 1 - p.y));
  var w = 0.0;
  if (e < u.uRamp) { w = ramp_b[e]; }
  var ph = h_at(p).x;
  if (u.uSea != 0 && ph <= u.uSea32) {
    w = 1.0;
    ph = min(ph, u.uSea32);
  }
  outW_store(p, vec4<f32>(w, 0.0, 0.0, 0.0));
  outH_store(p, vec4<f32>(ph, 0.0, 0.0, 0.0));
}
