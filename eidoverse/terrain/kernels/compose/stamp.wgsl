// Port of blender/eidoblend/terrain/core/compose.py at f90c6fc: stamp()'s modes and smooth_min / smooth_max, cell by
// cell: 'add' h + s, 'max', 'min', 'smooth_max' / 'smooth_min' (the polynomial smooth minimum, C1, a blend width of k
// metres; the plain one when k <= 0), 'blend' h (1 - m) + s m with m = clip(mask, 0, 1). numpy computes in float64
// from the float32 fields and rounds once; this is float32 (add, max and min are exact either way).
//! sampler h
//! sampler s
//! sampler mask             blend: the mask (its first channel); anything otherwise
//! image   outF r32f
//! uniform int uMode        0 add, 1 max, 2 min, 3 smooth_max, 4 smooth_min, 5 blend
//! uniform float uK         the smooth modes' width, metres

fn smooth_min(a: f32, b: f32, k: f32) -> f32 {
  if (k <= 0.0) { return min(a, b); }
  let hh = max(k - abs(a - b), 0.0) / k;
  return min(a, b) - hh * hh * k * 0.25;
}

fn kmain(p: vec2<i32>) {
  if (!inside(p, outF_size())) { return; }
  let a = h_at(p).x;
  let b = s_at(p).x;
  var v: f32;
  switch u.uMode {
    case 0: { v = a + b; }
    case 1: { v = max(a, b); }
    case 2: { v = min(a, b); }
    case 3: { v = -smooth_min(-a, -b, u.uK); }
    case 4: { v = smooth_min(a, b, u.uK); }
    default: {
      let m = clamp(mask_at(p).x, 0.0, 1.0);
      v = a * (1.0 - m) + b * m;
    }
  }
  outF_store(p, vec4<f32>(v, 0.0, 0.0, 0.0));
}
