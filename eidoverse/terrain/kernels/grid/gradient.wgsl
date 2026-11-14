// Port of blender/eidoblend/terrain/core/grid.py at f90c6fc: gradient (np.gradient), slope_deg and aspect_deg, and
// core/io.py's hillshade, which differentiates the same way.
//   gradient   (dh/dx east, dh/dy north) by central differences, (h[k + 1] - h[k - 1]) / (2 cell), one-sided on the
//              edges, (h[1] - h[0]) / cell, as np.gradient's edge_order 1: rows run north
//   slope      degrees(arctan(hypot(gx, gy))), never clipped: the reference JSONs' definition
//   aspect     the compass direction the slope faces (downhill), degrees clockwise from north:
//              degrees(arctan2(-gx, -gy)) % 360, numpy's floor modulo (a result in [0, 360))
//   hillshade  io.hillshade: clip((-gx lx - gy ly + lz) / sqrt(gx^2 + gy^2 + 1), 0, 1) of the field times z
// numpy evaluates in float64 and the callers round to float32; this is float32 (the built-ins' errors, PORT_PLAN.md
// 2.3: atan and atan2 2 ulp, sqrt 1).
//! sampler h                the field (its first channel)
//! image   outA r32f        gx, slope, aspect or the hillshade
//! image   outB r32f        gy (mode 0; any field otherwise)
//! uniform int uMode        0 gradient, 1 slope, 2 aspect, 3 hillshade
//! uniform float uCell
//! uniform float uZ         hillshade: the height factor (1 elsewhere)
//! uniform vec3 uLight      hillshade: (lx, ly, lz), the light direction

fn hz(i: i32, j: i32) -> f32 { return h_at(vec2<i32>(i, j)).x * u.uZ; }

// np.gradient along one axis at index k of n (n >= 2)
fn diff(a: f32, b: f32, two: bool) -> f32 {
  if (two) { return (b - a) / (2.0 * u.uCell); }
  return (b - a) / u.uCell;
}

fn kmain(p: vec2<i32>) {
  let n = h_size();
  if (!inside(p, n)) { return; }
  var gx = 0.0;
  var gy = 0.0;
  if (n.x >= 2) {
    if (p.x == 0) { gx = diff(hz(0, p.y), hz(1, p.y), false); }
    else if (p.x == n.x - 1) { gx = diff(hz(n.x - 2, p.y), hz(n.x - 1, p.y), false); }
    else { gx = diff(hz(p.x - 1, p.y), hz(p.x + 1, p.y), true); }
  }
  if (n.y >= 2) {
    if (p.y == 0) { gy = diff(hz(p.x, 0), hz(p.x, 1), false); }
    else if (p.y == n.y - 1) { gy = diff(hz(p.x, n.y - 2), hz(p.x, n.y - 1), false); }
    else { gy = diff(hz(p.x, p.y - 1), hz(p.x, p.y + 1), true); }
  }
  if (u.uMode == 0) {
    outA_store(p, vec4<f32>(gx, 0.0, 0.0, 0.0));
    outB_store(p, vec4<f32>(gy, 0.0, 0.0, 0.0));
    return;
  }
  var v: f32;
  if (u.uMode == 1) {
    v = degrees(atan(sqrt(gx * gx + gy * gy)));
  } else if (u.uMode == 2) {
    // np.remainder(v, 360) for v in [-180, 180]: v + 360 below zero (which can round to 360 itself, as numpy's
    // does in its own precision), +0 for a zero
    v = degrees(atan2(-gx, -gy));
    if (v < 0.0) { v = v + 360.0; } else if (v == 0.0) { v = 0.0; }
  } else {
    let L = u.uLight;
    v = clamp((-gx * L.x - gy * L.y + L.z) / sqrt(gx * gx + gy * gy + 1.0), 0.0, 1.0);
  }
  outA_store(p, vec4<f32>(v, 0.0, 0.0, 0.0));
}
