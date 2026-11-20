// Port of the shared shape helpers of blender/eidoblend/terrain/solvers/volcanic.py at f90c6fc (smoothstep,
// smooth_min, smooth_max, crest_union), as WGSL functions (`//! include volcanic/math`). The port's own: the Blender
// edition evaluates these in numpy (float64) over whole levels; the kernels of kernels/volcanic/ and kernels/impact/
// evaluate them per cell in float32, in numpy's order of operations, and are graded against numpy
// (tests/volcanoes_craters/).

const VTAU: f32 = 6.283185307179586;
const VPI: f32 = 3.141592653589793;
const VBIG: f32 = 1.0e9;                  // volcanic.py _BIG: an "absent" height for the smooth unions

// smoothstep(e0, e1, v): t = clip((v - e0) / (e1 - e0), 0, 1); t^2 (3 - 2 t)
fn v_smoothstep(e0: f32, e1: f32, v: f32) -> f32 {
  let t = clamp((v - e0) / (e1 - e0), 0.0, 1.0);
  return t * t * (3.0 - 2.0 * t);
}

// smooth_min(a, b, k): the C1 polynomial smooth minimum, k the blend width (k <= 0: min). Where the blend saturates
// (h 1 or 0) numpy's b + (a - b) h - k h (1 - h) is a or b to a float64 rounding; in float32 the same sum beside the
// absent height VBIG (1e9, whose float32 spacing is 64 m) rounds a to a multiple of 64, so the ends return a and b.
fn v_smooth_min(a: f32, b: f32, k: f32) -> f32 {
  if (k <= 0.0) { return min(a, b); }
  let h = clamp(0.5 + 0.5 * (b - a) / k, 0.0, 1.0);
  if (h >= 1.0) { return a; }
  if (h <= 0.0) { return b; }
  return b + (a - b) * h - k * h * (1.0 - h);
}

fn v_smooth_max(a: f32, b: f32, k: f32) -> f32 { return -v_smooth_min(-a, -b, k); }

// crest_union(a, b, k): smooth_min lowered the crossing by k / 4; the bump (k / 4)(1 - ((a - b) / k)^2)^2 puts it back
fn v_crest_union(a: f32, b: f32, k: f32) -> f32 {
  if (k <= 0.0) { return min(a, b); }
  let u = clamp((a - b) / k, -1.0, 1.0);
  let q = 1.0 - u * u;
  return v_smooth_min(a, b, k) + 0.25 * k * q * q;
}

// np.mod(a, m) for m > 0: the result takes the divisor's sign (numpy's fmod, then + m below 0)
fn v_mod(a: f32, m: f32) -> f32 {
  let r = a - m * floor(a / m);
  return select(r, 0.0, r >= m);
}

// polar()'s azimuth: radians clockwise from north of an offset (east, north), np.arctan2(dx, dy)
fn v_az(d: vec2<f32>) -> f32 { return atan2(d.x, d.y); }
