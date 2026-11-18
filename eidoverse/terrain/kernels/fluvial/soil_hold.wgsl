// The port's own kernel (no Blender counterpart): the held heights and hold weights of blender/eidoblend/terrain/
// solvers/hillslope.py op_soil_hills at f90c6fc, which numpy makes in float64:
//     h    = where(chan, filled, h)
//     hold = chan                                                         (head_soft <= 1)
//     hold = where(chan & ~core, 1, where(lake, 0, smoothstep(t)))       (head_soft > 1),
//            t = clip((log(max(A, 1e-12)) - log(a_ch / soft)) / (2 log soft), 0, 1); then where(h <= sea, 1, hold)
//     hold = where(deposit >= hold_deposit_m, 1, hold)                   (hold_deposit_m given, a deposit field)
//     hold = where(keep > 0.5, 1, hold)                                  (keep: max(incised, river), the courses)
//! sampler bits r32ui    bit 0 chan, bit 1 core, bit 2 lake (soil_chan, soil_down)
//! sampler A
//! sampler h
//! sampler filled
//! sampler dep
//! sampler keep
//! image   outH r32f
//! image   outW r32f
//! uniform int uSoft     1: head_soft > 1
//! uniform float uLogLo  log(a_ch / soft), in doubles
//! uniform float uLogSpan 2 log(soft)
//! uniform int uSea
//! uniform float uSea32
//! uniform int uDep      1: the deposit test
//! uniform float uDepMin
//! uniform int uKeep

fn kmain(p: vec2<i32>) {
  if (!inside(p, outH_size())) { return; }
  let b = bits_at(p);
  let chan = (b & 1u) != 0u;
  let core = (b & 2u) != 0u;
  let lake = (b & 4u) != 0u;
  var h = h_at(p).x;
  if (chan) { h = filled_at(p).x; }
  var hold = select(0.0, 1.0, chan);
  if (u.uSoft == 1) {
    let t = clamp((log(max(A_at(p).x, 1e-12)) - u.uLogLo) / u.uLogSpan, 0.0, 1.0);
    var ws = t * t * (3.0 - 2.0 * t);
    if (lake) { ws = 0.0; }
    hold = ws;
    if (chan && !core) { hold = 1.0; }
    if (u.uSea == 1 && h <= u.uSea32) { hold = 1.0; }
  }
  if (u.uDep == 1 && dep_at(p).x >= u.uDepMin) { hold = 1.0; }
  if (u.uKeep == 1 && keep_at(p).x > 0.5) { hold = 1.0; }
  outH_store(p, vec4<f32>(h, 0.0, 0.0, 0.0));
  outW_store(p, vec4<f32>(hold, 0.0, 0.0, 0.0));
}
