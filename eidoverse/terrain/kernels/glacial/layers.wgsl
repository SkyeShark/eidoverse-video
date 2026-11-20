// The port's own kernel: the layers of blender/eidoblend/terrain/solvers/glacial.py carve_level at f90c6fc, after the
// U-carve (h, bed the level's before; S, M u_carve's outputs):
//     loose_old = max(h - bed, 0);  loose_new = max(h' - bed', 0);  took = max(h - h', 0)
//     bare = 1 - clip(loose_new / 2, 0, 1)
//     wear = wear + max(took - loose_old, 0) bare
//     hit = carved > 1e-3:  deposit = 0, talus = 0, valley_fill = loose_new where hit (else as they were)
// numpy is float64 then float32; this is float32, in numpy's order. A field the level does not have is 0 (uHas).
//! sampler h
//! sampler bed              the level's bed (its h when it has none)
//! sampler S                u_carve's outS: h', bed', rho, ice
//! sampler M                u_carve's outM: carved, floor, wall, trough
//! sampler wear
//! sampler dep
//! sampler tal
//! sampler vf
//! image   outW r32f        wear
//! image   outD r32f        deposit
//! image   outT r32f        talus
//! image   outV r32f        valley_fill
//! uniform ivec4 uHas       wear, deposit, talus, valley_fill: 1 where the level has the field

fn kmain(p: vec2<i32>) {
  if (!inside(p, outW_size())) { return; }
  let hv = h_at(p).x;
  let s = S_at(p);
  let loose_old = max(hv - bed_at(p).x, 0.0);
  let loose_new = max(s.x - s.y, 0.0);
  let took = max(hv - s.x, 0.0);
  let bare = 1.0 - clamp(loose_new / 2.0, 0.0, 1.0);
  var w0 = 0.0;
  if (u.uHas.x != 0) { w0 = wear_at(p).x; }
  let hit = M_at(p).x > 1e-3;
  var d0 = 0.0;
  if (u.uHas.y != 0 && !hit) { d0 = dep_at(p).x; }
  var t0 = 0.0;
  if (u.uHas.z != 0 && !hit) { t0 = tal_at(p).x; }
  var v0 = 0.0;
  if (u.uHas.w != 0) { v0 = vf_at(p).x; }
  if (hit) { v0 = loose_new; }
  outW_store(p, vec4<f32>(w0 + max(took - loose_old, 0.0) * bare, 0.0, 0.0, 0.0));
  outD_store(p, vec4<f32>(d0, 0.0, 0.0, 0.0));
  outT_store(p, vec4<f32>(t0, 0.0, 0.0, 0.0));
  outV_store(p, vec4<f32>(v0, 0.0, 0.0, 0.0));
}
