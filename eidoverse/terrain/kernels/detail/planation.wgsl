// Port of numpy code of blender/eidoblend/terrain/solvers/detail.py (op_planation) at f90c6fc, as a GPU kernel.
// planation: a pediment plain with residual knobs, cell by cell (the port's own kernel, PORT_PLAN.md 3.2: numpy code
// of blender/eidoblend/terrain/solvers/detail.py op_planation at f90c6fc moved to the GPU). With the two world-noise
// fields made by core/world_noise.js (the resistance fbm at resist_wavelength_m, the plain's small relief at 60 m) it
// replaces
//   datum = datum0 - tan(tilt) ((X - cx) cos(az) + (Y - cy) sin(az))
//   resistance = clip(res 1.5 + 0.5, 0, 1)
//   hard = _smoothstep(coverage - 0.04, coverage + 0.04, resistance) ** selectivity
//   relief = maximum(h_in - datum, 0) residual hard
//   foot = _smoothstep(0, max(piedmont_m tan(25 deg), 1e-6), relief)
//   h = datum + relief foot + detail (1 - hard)
// (X - cx is (x0 - cx) + (i + 0.5) cell: small numbers, so float32 keeps them). numpy evaluates in float64; float32
// here (graded against it).
//! sampler h             x: h_in, metres
//! sampler res           x: the resistance fbm (std 1/3)
//! sampler det           x: the plain's small relief, metres
//! image   outH r32f     the new surface
//! image   outC r32f     the change h - h_in (wear and deposit)
//! image   outHard r32f  hard (the log's residual fraction)
//! uniform float uDatum0
//! uniform float uTan     tan(tilt_deg)
//! uniform float uCos     cos(azimuth)
//! uniform float uSin     sin(azimuth)
//! uniform float uOx      x0 - cx
//! uniform float uOy      y0 - cy
//! uniform float uCell
//! uniform float uCovLo   coverage - 0.04
//! uniform float uCovDen  max(0.08, 1e-12)
//! uniform float uSel     selectivity
//! uniform float uResidual
//! uniform float uFootDen max(piedmont_m tan(25 deg), 1e-6)

fn kmain(p: vec2<i32>) {
  let n = outH_size();
  if (!inside(p, n)) { return; }
  let x = u.uOx + (f32(p.x) + 0.5) * u.uCell;
  let y = u.uOy + (f32(p.y) + 0.5) * u.uCell;
  let datum = u.uDatum0 - u.uTan * (x * u.uCos + y * u.uSin);
  let resistance = clamp(res_at(p).x * 1.5 + 0.5, 0.0, 1.0);
  let t = clamp((resistance - u.uCovLo) / u.uCovDen, 0.0, 1.0);
  let sm = t * t * (3.0 - 2.0 * t);
  var hard = 0.0;
  if (sm > 0.0) { hard = pow(sm, u.uSel); }
  let h0 = h_at(p).x;
  let relief = max(h0 - datum, 0.0) * u.uResidual * hard;
  let tf = clamp(relief / u.uFootDen, 0.0, 1.0);
  let foot = tf * tf * (3.0 - 2.0 * tf);
  let h = datum + relief * foot + det_at(p).x * (1.0 - hard);
  outH_store(p, vec4<f32>(h, 0.0, 0.0, 0.0));
  outC_store(p, vec4<f32>(h - h0, 0.0, 0.0, 0.0));
  outHard_store(p, vec4<f32>(hard, 0.0, 0.0, 0.0));
}
