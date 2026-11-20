// The port's own kernel (no Blender counterpart): one joint set of blender/eidoblend/terrain/solvers/strata.py
// joint_field() at f90c6fc, which numpy evaluates in float64 from the GPU's float32 noise:
//     u = (x cos a - y sin a) / spacing  (+ 3 wiggle / spacing f_wiggle)     across the lines
//     d = |u - round(u)| spacing,   line = exp(-(d / w)^2),   seg = clip((f_seg + 0.15) / 0.3, 0, 1)
//     out = max(out, strength line seg)                                      the sets combine by max
// u is its value at cell (0, 0) plus its steps per column and per row, made in doubles by solvers/strata.js. WGSL's
// round() is half to even, as numpy's. float32 here, in numpy's order.
//! sampler prev     the weakness so far (1 x 1 stand-in on the first set: 0)
//! sampler wig      the set's wiggle noise (1 x 1 stand-in without)
//! sampler seg      the set's segment noise
//! image   outJ r32f
//! uniform ivec2 uHas    x: prev given, y: wiggle
//! uniform vec3 uU       u at cell (0, 0), per column, per row
//! uniform vec4 uJ       3 wiggle / spacing, spacing, w, strength

fn kmain(p: vec2<i32>) {
  let n = outJ_size();
  if (!inside(p, n)) { return; }
  var uu = u.uU.x + f32(p.x) * u.uU.y + f32(p.y) * u.uU.z;
  if (u.uHas.y == 1) { uu = uu + u.uJ.x * wig_at(p).x; }
  let d = abs(uu - round(uu)) * u.uJ.y;
  let r = d / u.uJ.z;
  let line = exp(-(r * r));
  let s = clamp((seg_at(p).x + 0.15) / 0.3, 0.0, 1.0);
  var out = u.uJ.w * line * s;
  if (u.uHas.x == 1) { out = max(prev_at(p).x, out); } else { out = max(0.0, out); }
  outJ_store(p, vec4<f32>(out, 0.0, 0.0, 0.0));
}
