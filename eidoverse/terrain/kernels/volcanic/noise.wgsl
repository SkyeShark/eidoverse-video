// Port of blender/eidoblend/terrain/solvers/volcanic.py lattice_hash, gradient_noise and fbm at f90c6fc
// (`//! include volcanic/noise`): gradient (Perlin) noise of world metres, the hash common.wgsl's pcg. The port's own
// kernel code (numpy in the Blender edition).
//
// numpy: px = x / scale_m (float64); the lattice cell floor(px) as int64, its fraction cast to float32; the gradient
// angle a = lattice_hash * (TAU / 2^32) in float64, cos and sin rounded to float32; the corners, fades and blends in
// float32. Here a grid point's lattice coordinate is kept as the window's integer base plus a float32 offset
// (solvers/volcanic.js noiseTerm: base = floor(ox / scale), f0 = ox / scale - base in doubles, then f0 + (i + 0.5)
// step / scale), so the fraction keeps its precision at any distance from the origin, as core/world_noise.js keeps
// its lattices. The angle is the hash in float32 times TAU / 2^32 (an angle 2e-7 rad off numpy's at most).
// gradient_noise has two code paths in numpy whose fades are written in two orders (the grid path for meshgrids,
// the pointwise path otherwise); `grid` picks the order.

fn lattice_hash(ix: i32, iy: i32, seed: u32) -> u32 {
  return pcg(bitcast<u32>(ix) ^ pcg(bitcast<u32>(iy) ^ pcg(seed)));
}

fn grad_of(ix: i32, iy: i32, seed: u32) -> vec2<f32> {
  let h = lattice_hash(ix, iy, seed);
  // a = h * (TAU / 2^32): the hash's high 24 bits and its low 8 kept apart, so the float32 angle loses nothing
  let a = f32(h >> 8u) * (VTAU / 16777216.0) + f32(h & 0xFFu) * (VTAU / 4294967296.0);
  return vec2<f32>(cos(a), sin(a));
}

fn fade_point(t: f32) -> f32 {                 // u = t 6; u -= 15; u *= t; u += 10; u *= t; u *= t; u *= t
  var u = t * 6.0;
  u = u - 15.0;
  u = u * t;
  u = u + 10.0;
  u = u * t;
  u = u * t;
  u = u * t;
  return u;
}

fn fade_grid(t: f32) -> f32 { return t * t * t * (t * (t * 6.0 - 15.0) + 10.0); }

// gradient noise at lattice cell c with fraction f in [0, 1)
fn grad_noise(c: vec2<i32>, f: vec2<f32>, seed: u32, grid: bool) -> f32 {
  let g00 = grad_of(c.x, c.y, seed);
  let g10 = grad_of(c.x + 1, c.y, seed);
  let g01 = grad_of(c.x, c.y + 1, seed);
  let g11 = grad_of(c.x + 1, c.y + 1, seed);
  let c00 = g00.x * f.x + g00.y * f.y;
  let c10 = g10.x * (f.x - 1.0) + g10.y * f.y;
  let c01 = g01.x * f.x + g01.y * (f.y - 1.0);
  let c11 = g11.x * (f.x - 1.0) + g11.y * (f.y - 1.0);
  var ux: f32;
  var uy: f32;
  if (grid) { ux = fade_grid(f.x); uy = fade_grid(f.y); } else { ux = fade_point(f.x); uy = fade_point(f.y); }
  let n0 = c00 + (c10 - c00) * ux;
  let n1 = c01 + (c11 - c01) * ux;
  return n0 + (n1 - n0) * uy;
}

// the lattice coordinate of a grid point: base (integer) + f0 + (i + 0.5) step, split into cell and fraction
struct Lat { c: vec2<i32>, f: vec2<f32> }

fn lat_grid(base: vec2<i32>, f0: vec2<f32>, step: f32, q: vec2<i32>) -> Lat {
  let t = f0 + (vec2<f32>(q) + 0.5) * step;
  let fl = floor(t);
  return Lat(base + vec2<i32>(fl), t - fl);
}

// a point given as x / scale directly (a coordinate that is not on a grid: ravine_cut's along-ravine distance)
fn lat_point(px: vec2<f32>) -> Lat {
  let fl = floor(px);
  return Lat(vec2<i32>(fl), px - fl);
}
