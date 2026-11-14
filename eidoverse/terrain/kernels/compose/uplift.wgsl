// Port of blender/eidoblend/terrain/core/compose.py at f90c6fc: uplift()'s shapes, about 0..1 and smooth everywhere
// (Gaussian falloffs of distances in a domain-warped plane, unions by smooth maximum: no creases, design 4.1), at a
// window's cell centres moved by the warp (disp: the warp's displacement, plus any the caller gave), relative to the
// shape's centre:
//   dome     gauss(r, size / 2)
//   plateau  smoothstep of t = clip((size - r) / edge, 0, 1)
//   ridge    gauss(distance to the spine, W / 2), each spur smooth_max'ed in (0.8 gauss(distance to the spur,
//            0.22 W), width 0.15)
//   massif   0.6 gauss(r, 0.55 size), each peak smooth_max'ed in (amp gauss(distance to the peak, sigma), width 0.2)
// then the kilometre-scale texture, f max(1 + 2 tex n, 0) with n the fbm read at the warped points, and max(f, 0).
// The spurs and peaks (numpy's Generator draws) are planned on the CPU (core/compose.js) and read from `table`.
// numpy evaluates in float64; this is float32 (exp and the distances), positions relative to the centre.
//! sampler disp             rg32f: the sample points' displacement in metres (the warp's; read when uDisp is 1)
//! sampler tex              the texture's fbm at the warped points (its first channel); anything when uTex is 0
//! sampler table            ridge: (px, py, ex, ey) per spur; massif: (px, py, amp, sigma) per peak; relative to the centre
//! image   outF r32f
//! uniform int uDisp
//! uniform int uKind        0 dome, 1 plateau, 2 ridge, 3 massif
//! uniform vec2 uOrigin     the window's (x0, y0) minus the shape's centre, metres
//! uniform float uCell
//! uniform float uSize      dome, plateau, massif: the size (radius)
//! uniform float uWidth     plateau: max(edge, 1e-9); ridge: W
//! uniform vec4 uSpine      ridge: (ax, ay, bx, by), the spine's ends relative to the centre
//! uniform int uCount       spurs or peaks
//! uniform float uTex       the texture amount (0: none)

fn gauss(d: f32, sigma: f32) -> f32 {
  let t = d / max(sigma, 1e-9);
  return exp(-0.5 * (t * t));
}

fn seg_dist(x: vec2<f32>, a: vec2<f32>, b: vec2<f32>) -> f32 {
  let v = b - a;
  let l2 = max(v.x * v.x + v.y * v.y, 1e-12);
  let t = clamp(((x.x - a.x) * v.x + (x.y - a.y) * v.y) / l2, 0.0, 1.0);
  let q = x - (a + t * v);
  return sqrt(q.x * q.x + q.y * q.y);
}

fn smooth_min(a: f32, b: f32, k: f32) -> f32 {
  if (k <= 0.0) { return min(a, b); }
  let hh = max(k - abs(a - b), 0.0) / k;
  return min(a, b) - hh * hh * k * 0.25;
}

fn smooth_max(a: f32, b: f32, k: f32) -> f32 { return -smooth_min(-a, -b, k); }

fn kmain(p: vec2<i32>) {
  if (!inside(p, outF_size())) { return; }
  var x = u.uOrigin + (vec2<f32>(p) + 0.5) * u.uCell;
  if (u.uDisp != 0) { x = x + disp_at(p).xy; }
  var f = 0.0;
  if (u.uKind == 0) {
    f = gauss(sqrt(x.x * x.x + x.y * x.y), u.uSize * 0.5);
  } else if (u.uKind == 1) {
    let t = clamp((u.uSize - sqrt(x.x * x.x + x.y * x.y)) / u.uWidth, 0.0, 1.0);
    f = t * t * (3.0 - 2.0 * t);
  } else if (u.uKind == 2) {
    f = gauss(seg_dist(x, u.uSpine.xy, u.uSpine.zw), u.uWidth * 0.5);
    for (var k = 0; k < u.uCount; k++) {
      let s = table_at(vec2<i32>(k, 0));
      let sp = 0.8 * gauss(seg_dist(x, s.xy, s.zw), u.uWidth * 0.22);
      f = smooth_max(f, sp, 0.15);
    }
  } else {
    f = 0.6 * gauss(sqrt(x.x * x.x + x.y * x.y), u.uSize * 0.55);
    for (var k = 0; k < u.uCount; k++) {
      let s = table_at(vec2<i32>(k, 0));
      let q = x - s.xy;
      f = smooth_max(f, s.z * gauss(sqrt(q.x * q.x + q.y * q.y), s.w), 0.2);
    }
  }
  if (u.uTex > 0.0) {
    f = f * max(1.0 + u.uTex * 2.0 * tex_at(p).x, 0.0);
  }
  outF_store(p, vec4<f32>(max(f, 0.0), 0.0, 0.0, 0.0));
}
