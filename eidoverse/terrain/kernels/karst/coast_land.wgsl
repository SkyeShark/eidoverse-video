// Port of blender/eidoblend/terrain/solvers/coast.py shore_coordinate, land_shape and op_coast_land's arithmetic at
// f90c6fc, as a kernel over a level's cells. numpy's float64 is float32 here.
//     s0      = -((X - cx) ux + (Y - cy) uy) + offset_m + retreat_m (+ wiggle_m w: the fbm the CPU had the world
//               noise kernel make)                    metres inland of the original coastline
//     inland  = (1 - (1 - c) exp(-max(s0, 0) / rise)) x max(1 + inland_gain clip(s0 / max(tilt_m, 1), 0, 1), 0.05)
//     seaward = c exp(min(s0, 0) / L),  L = c rise / (1 - c)
//     shape   = (s0 >= 0 ? inland : seaward) x max(1 + texture tex, 0.1)
//     U       = U_m_per_yr shape;   h0 = max(start_m shape (1 + start_roughness rough), 0.05)
// outL: (s0, U, h0, shape).

//! sampler axes rg32f        row 0: X - cx per column; row 1: Y - cy per row (metres)
//! sampler wig               the wiggle's fbm (uWiggle 0: not read)
//! sampler tex               the texture noise (uHasTex 0: zero)
//! sampler rough             the start's noise (uHasRough 0: zero)
//! image   outL rgba32f
//! uniform float uUx
//! uniform float uUy
//! uniform float uOffset
//! uniform float uRetreat
//! uniform float uWiggle
//! uniform float uC
//! uniform float uRise
//! uniform float uGain
//! uniform float uTilt       max(tilt_m, 1)
//! uniform float uL          c rise / (1 - c)
//! uniform float uTexture
//! uniform float uURate
//! uniform float uStart
//! uniform float uRoughK
//! uniform int uFlags        1: a texture, 2: a start noise, 4: a wiggle
fn kmain(p: vec2<i32>) {
  let n = outL_size();
  if (!inside(p, n)) { return; }
  let dx = axes_at(vec2<i32>(p.x, 0)).x;
  let dy = axes_at(vec2<i32>(p.y, 1)).x;
  var s = -(dx * u.uUx + dy * u.uUy) + u.uOffset + u.uRetreat;
  if ((u.uFlags & 4) != 0) { s = s + u.uWiggle * wig_at(p).x; }
  var inland = 1.0 - (1.0 - u.uC) * exp(-max(s, 0.0) / u.uRise);
  inland = inland * max(1.0 + u.uGain * clamp(s / u.uTilt, 0.0, 1.0), 0.05);
  let seaward = u.uC * exp(min(s, 0.0) / u.uL);
  var shape = select(seaward, inland, s >= 0.0);
  var t = 0.0;
  if ((u.uFlags & 1) != 0) { t = tex_at(p).x; }
  shape = shape * max(1.0 + u.uTexture * t, 0.1);
  var r = 0.0;
  if ((u.uFlags & 2) != 0) { r = rough_at(p).x; }
  let h0 = max(u.uStart * shape * (1.0 + u.uRoughK * r), 0.05);
  outL_store(p, vec4<f32>(s, u.uURate * shape, h0, shape));
}
