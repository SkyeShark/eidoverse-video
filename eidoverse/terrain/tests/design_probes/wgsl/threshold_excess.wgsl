// threshold_excess: the inline kernel EXCESS of blender/eidoblend/terrain/solvers/hillslope.py in WGSL
//! sampler st     x: h (m)
//! sampler par    z: Sc, the threshold slope's tangent
//! image   outP r32f   x: phi = max(1 - Sc / G, 0), G the upwind (Rouy-Tourin) gradient magnitude
//! uniform float uDx
//! uniform int uBound

fn axis_h(p: vec2<i32>, k: i32, n: vec2<i32>, h: f32) -> f32 {
  var q: vec2<i32>;
  if (neighbour(p, k, n, u.uBound, &q)) { return st_at(q).x; }
  return h;
}

fn kmain(p: vec2<i32>) {
  let n = st_size();
  if (!inside(p, n)) { return; }
  let h = st_at(p).x;
  let gx = max(h - min(axis_h(p, 3, n, h), axis_h(p, 4, n, h)), 0.0);
  let gy = max(h - min(axis_h(p, 1, n, h), axis_h(p, 6, n, h)), 0.0);
  let g = sqrt(gx * gx + gy * gy) / u.uDx;
  let sc = par_at(p).z;
  var phi = 0.0;
  if (g > sc) { phi = 1.0 - sc / g; }
  outP_store(p, vec4<f32>(phi, 0.0, 0.0, 0.0));
}
