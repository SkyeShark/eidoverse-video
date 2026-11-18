// breakup_surface: the rock breakup's weathering and thresholds, cell by cell (the port's own kernel, PORT_PLAN.md
// 3.2: numpy code of blender/eidoblend/terrain/solvers/detail.py op_breakup at f90c6fc moved to the GPU). From the
// gradient of the surface smoothed over 2 cells and the breakup kernel's (R, kfac, sc_abs, D) it replaces
//   tan_s = hypot(gx, gy); slope = degrees(arctan(tan_s)); rock = _smoothstep(lo, hi, slope)
//   edge = band_fade = 1 - clip(pin_w, 0, 1)
//   nf = minimum(sqrt(1 + tan_s^2), normal_cap)
//   h1 - h_in = rock * edge * D * nf                       the differential weathering along the surface normal
//   sc_rock: 'relative'  tan(radians(clip(slope + margin_deg + spread_deg R, min_deg, max_deg)))
//            'absolute'  sc_abs (the kernel's)
//            'field'     tan(radians(clip(degrees(arctan(Sc)) + spread_deg R, min_deg, max_deg)))
//   sc_eff = (sc_rock * rock + 1e3 * (1 - rock)).astype(F)  (soil does not fail: its threshold out of reach)
//   soil_sc = Sc, or tan(soil_deg) without an Sc field;  sc_new = soil_sc (1 - rock) + sc_rock rock
//   Sc_factor = sc_new / maximum(soil_sc, 1e-6)
// numpy evaluates in float64; this is float32, the tangents of up to 88 degrees included (graded against it).
//! sampler gx            x: dh/dx of the surface smoothed over 2 cells (core/grid.js gradient)
//! sampler gy            x: dh/dy
//! sampler bk            the breakup kernel's output: (R, kfac, sc_abs, D)
//! sampler pw            x: the pin weight (uHasPw)
//! sampler sc            x: the level's Sc field, a tangent (uHasSc)
//! image   outA rgba32f  (the weathering h1 - h_in in metres, rock, sc_eff, sc_new)
//! image   outF r32f     Sc_factor
//! uniform float uLo        rock_slope_deg[0]
//! uniform float uDen       max(rock_slope_deg[1] - rock_slope_deg[0], 1e-12)
//! uniform float uCap       normal_cap
//! uniform float uMargin    margin_deg
//! uniform float uSpread    spread_deg
//! uniform float uMin       min_deg
//! uniform float uMax       max_deg
//! uniform float uSoilTan   tan(soil_deg), the threshold on soil without an Sc field
//! uniform int uMode        0 relative, 1 absolute, 2 field
//! uniform int uHasPw
//! uniform int uHasSc

fn kmain(p: vec2<i32>) {
  let n = outA_size();
  if (!inside(p, n)) { return; }
  let ax = gx_at(p).x;
  let ay = gy_at(p).x;
  let tan_s = sqrt(ax * ax + ay * ay);
  let slope = degrees(atan(tan_s));
  let t = clamp((slope - u.uLo) / u.uDen, 0.0, 1.0);
  let rock = t * t * (3.0 - 2.0 * t);
  var edge = 1.0;
  if (u.uHasPw != 0) { edge = 1.0 - clamp(pw_at(p).x, 0.0, 1.0); }
  let nf = min(sqrt(1.0 + tan_s * tan_s), u.uCap);
  let b = bk_at(p);
  let w = rock * edge * b.w * nf;
  var sc_rock: f32;
  if (u.uMode == 0) {
    sc_rock = tan(radians(clamp(slope + u.uMargin + u.uSpread * b.x, u.uMin, u.uMax)));
  } else if (u.uMode == 1) {
    sc_rock = b.z;
  } else {
    let base = degrees(atan(sc_at(p).x));
    sc_rock = tan(radians(clamp(base + u.uSpread * b.x, u.uMin, u.uMax)));
  }
  let sc_eff = sc_rock * rock + 1.0e3 * (1.0 - rock);
  var soil = u.uSoilTan;
  if (u.uHasSc != 0) { soil = sc_at(p).x; }
  let sc_new = soil * (1.0 - rock) + sc_rock * rock;
  outA_store(p, vec4<f32>(w, rock, sc_eff, sc_new));
  outF_store(p, vec4<f32>(sc_new / max(soil, 1e-6), 0.0, 0.0, 0.0));
}
