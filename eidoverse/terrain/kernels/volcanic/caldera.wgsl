// Port of blender/eidoblend/terrain/solvers/volcanic.py caldera_collapse at f90c6fc, cell by cell: a ring-fault
// collapse cut into the edifice h_before. numpy:
//     shape = 1 + (elongation - 1)(cos(az - el_az)^2 - 0.5)
//             x (1 + radius_noise n52) x (1 + edge_noise n53) x (1 + scallop) x polygon x (1 + embayment)
//     u = r - r_floor shape                         the outward distance from the floor's edge
//     talus_line = floor_m + tt u;  shift = talus_vary th n54
//     rock_line = floor_m + th + shift + (the layered face at u - (th + shift) / tt, or tw (u - (th + shift) / tt))
//     surface = smooth_max(smooth_max(talus_line, rock_line, k), floor_m, k);  rock = smooth_max(rock_line, floor_m, k)
//     h = crest_union(hb, surface, kr) (round_crest) or min(hb, surface)
//     talus = clip(min(surface, hb) - rock, 0); floor = u < 0
//     strength = where((u > (th + shift) / tt) & (surface < hb + 1), the face's 1.1 s, NaN)
// The outline's tables (solvers/volcanic.js calderaPlan, in doubles) are rows of `azt`; the face's table is `zst` /
// `s0t` (kernels/volcanic/face.wgsl). The port's own kernel: float32 in numpy's order.
//! include volcanic/math
//! include volcanic/az
//! include volcanic/face
//! sampler azt r32f
//! sampler zst rg32f     the layered face (a 1 x 1 stand-in without cliffs)
//! sampler s0t r32f
//! sampler prm           the collapse's numbers (calderaPlan), rgba32f texels:
//                          0 (Hw, r_floor, tt, tw)
//                          1 (th, floor_m, k = 0.02 Hw, kr = crest_round_m (tw + 0.1))
//                          2 (elongation, its azimuth rad, radius_noise, edge_noise)
//                          3 (scallops 1|0, polygon 1|0, embayments 1|0, talus_vary)
//                          4 (rows: radius noise, edge noise, scallop, polygon)
//                          5 (rows: embayment, talus noise; round_crest 1|0, cliffs 1|0)
//                          6 (the face's U, tan(wall_deg), 0, 0)
//! sampler hb            the edifice's surface (h before)
//! image   outH r32f
//! image   outT r32f     the talus apron's thickness over the rock
//! image   outF r32f     1 on the flat floor
//! image   outS r32f     the threshold the wall was built at (NaN off it; cliffs only)
//! uniform vec2 uOrg     the grid's origin minus the centre, metres
//! uniform float uStep

fn kmain(p: vec2<i32>) {
  let n = outH_size();
  if (!inside(p, n)) { return; }
  let t0 = prm_at(vec2<i32>(0, 0));
  let t1 = prm_at(vec2<i32>(1, 0));
  let t2 = prm_at(vec2<i32>(2, 0));
  let t3 = prm_at(vec2<i32>(3, 0));
  let t4 = prm_at(vec2<i32>(4, 0));
  let t5 = prm_at(vec2<i32>(5, 0));
  let t6 = prm_at(vec2<i32>(6, 0));
  let Hw = t0.x;
  let tt = t0.z;
  let tw = t0.w;
  let th = t1.x;
  let fl = t1.y;
  let k = t1.z;
  let d = u.uOrg + (vec2<f32>(p) + 0.5) * u.uStep;
  let r = length(d);
  let az = v_az(d);
  let s = az_sampler(az);
  let c = cos(az - t2.y);
  var shape = 1.0 + (t2.x - 1.0) * (c * c - 0.5);
  if (t2.z != 0.0) { shape = shape * (1.0 + t2.z * az_read(i32(t4.x), s)); }
  if (t2.w != 0.0) { shape = shape * (1.0 + t2.w * az_read(i32(t4.y), s)); }
  if (t3.x != 0.0) { shape = shape * (1.0 + az_read(i32(t4.z), s)); }
  if (t3.y != 0.0) { shape = shape * az_read(i32(t4.w), s); }
  if (t3.z != 0.0) { shape = shape * (1.0 + az_read(i32(t5.x), s)); }
  let uu = r - t0.y * shape;
  let talus_line = fl + tt * uu;
  var shift = 0.0;
  if (t3.w != 0.0) { shift = t3.w * th * az_read(i32(t5.y), s); }
  let foot = (th + shift) / tt;
  var rock_line: f32;
  var strength = 0.0;
  if (t5.w != 0.0) {
    let fz = layered_face(uu - foot, az, t6.x, t6.y);
    rock_line = fz.x + fl + th + shift;
    strength = fz.y;
  } else {
    rock_line = fl + th + shift + tw * (uu - foot);
  }
  let surface = v_smooth_max(v_smooth_max(talus_line, rock_line, k), fl, k);
  let rock = v_smooth_max(rock_line, fl, k);
  let h0 = hb_at(p).x;
  var h: f32;
  if (t5.z != 0.0) { h = v_crest_union(h0, surface, t1.w); } else { h = min(h0, surface); }
  let talus = max(min(surface, h0) - rock, 0.0);
  outH_store(p, vec4<f32>(h, 0.0, 0.0, 0.0));
  outT_store(p, vec4<f32>(talus, 0.0, 0.0, 0.0));
  outF_store(p, vec4<f32>(select(0.0, 1.0, uu < 0.0), 0.0, 0.0, 0.0));
  var sv = bitcast<f32>(0x7FC00000u);
  if (t5.w != 0.0 && uu > foot && surface < h0 + 1.0) { sv = strength; }
  outS_store(p, vec4<f32>(sv, 0.0, 0.0, 0.0));
}
