// masks/lib.wgsl: what the masks' kernels share (`//! include masks/lib`). The masks are blender/eidoblend/terrain/
// masks.py at f90c6fc, which runs in numpy; these kernels are its per-cell steps on the GPU (PORT_PLAN.md 3.2), and
// masks.js drives them.

// "No terrain here". masks.py marks it with NaN, which np.fmax and np.isfinite skip (beyond every level in the
// occlusion march; not a rock foot in rock_shadow). WGSL lets an implementation assume that no NaN or infinity
// reaches a shader, so the port marks it with this sentinel instead: below every height and every tangent, and
// still finite when a march multiplies it by 1 / distance (at most 1 / 0.1 m).
const NOH: f32 = -1.0e30;
fn has_h(v: f32) -> bool { return v > -1.0e29; }

// masks.py smoothstep(e0, e1, x) in float32, step for step: t = (x - e0) * k with k = float32(1 / (e1 - e0)), the
// double numpy computes for the Python float (masks.js passes e = (float32(e0), k)), clipped to [0, 1], then the
// in-place steps u = t * t; t *= -2; t += 3; t *= u. (e1 < e0 runs it downhill.)
fn ss(x: f32, e: vec2<f32>) -> f32 {
  var t = (x - e.x) * e.y;
  t = clamp(t, 0.0, 1.0);
  let u = t * t;
  t = t * -2.0;
  t = t + 3.0;
  return t * u;
}

// i on a periodic axis of n cells, for any i (no % of a negative number: on this edition's wgpu an i32 % with a
// negative operand is not WGSL's, core/gpu.js says why)
fn wrap1(i: i32, n: i32) -> i32 {
  if (i < 0) { return (n - 1) - ((-i - 1) % n); }
  return i % n;
}

// log10(x) for x > 0: WGSL has log2 only
fn log10f(x: f32) -> f32 { return log2(x) * 0.30102999566398120; }
