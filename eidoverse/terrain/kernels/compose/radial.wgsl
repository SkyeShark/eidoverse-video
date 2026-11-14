// Port of blender/eidoblend/terrain/core/compose.py at f90c6fc: shape()'s radial kinds, at a window's cell centres
// (plus a displacement), r the distance from the shape's centre:
//   cone     linear H (1 - t), cosine H (1 + cos(pi t)) / 2 with t = clip(r / R, 0, 1); exp (the stratovolcano's,
//            design 4.7) H clip((e_r - e_R) / (1 - e_R), 0, inf), e_r = exp(-(max(r, rc) - rc) / lambda), the
//            crater excluded, e_R = exp(-(R - rc) / lambda) computed in doubles
//   bowl     -D (1 - (r / R)^p) inside the radius, 0 outside (p = 2: parabolic)
//   profile  np.interp(r, r_m, z_m): a radial profile table, linear between its points, constant past its ends;
//            the slopes come from doubles as np.interp forms them
// numpy evaluates in float64; this is float32, with the positions relative to the centre ((x0 - cx) in doubles),
// so float32 keeps a fraction of a millimetre at any world offset.
//! sampler disp             rg32f: each sample point's displacement in metres (read when uDisp is 1)
//! sampler table            profile: (r_m, z_m, slope to the next point, 0) per point, in a row
//! image   outF r32f
//! uniform int uDisp
//! uniform int uKind        0 cone linear, 1 cone cosine, 2 cone exp, 3 bowl, 4 profile
//! uniform vec2 uOrigin     the window's (x0, y0) minus the shape's centre, metres
//! uniform float uCell
//! uniform float uR         cone and bowl: the radius
//! uniform float uH         cone: the height; bowl: the depth
//! uniform float uLam       cone exp: lambda; bowl: the exponent
//! uniform float uRc        cone exp: the crater radius
//! uniform float uER        cone exp: e_R
//! uniform int uCount       profile: the points

const PI_F: f32 = 3.14159265358979;

fn kmain(p: vec2<i32>) {
  if (!inside(p, outF_size())) { return; }
  var d = u.uOrigin + (vec2<f32>(p) + 0.5) * u.uCell;
  if (u.uDisp != 0) { d = d + disp_at(p).xy; }
  let r = sqrt(d.x * d.x + d.y * d.y);
  var z = 0.0;
  if (u.uKind <= 1) {
    let t = clamp(r / u.uR, 0.0, 1.0);
    if (u.uKind == 0) { z = u.uH * (1.0 - t); } else { z = u.uH * 0.5 * (1.0 + cos(PI_F * t)); }
  } else if (u.uKind == 2) {
    let er = exp(-(max(r, u.uRc) - u.uRc) / u.uLam);
    z = u.uH * max((er - u.uER) / (1.0 - u.uER), 0.0);
  } else if (u.uKind == 3) {
    if (r < u.uR) {
      let t = r / u.uR;
      var q: f32;
      if (u.uLam == 2.0) { q = t * t; } else if (u.uLam == 1.0) { q = t; } else { q = pow(t, u.uLam); }
      z = -u.uH * (1.0 - q);
    }
  } else {
    let n = u.uCount;
    let first = table_at(vec2<i32>(0, 0));
    let last = table_at(vec2<i32>(n - 1, 0));
    if (r < first.x) {
      z = first.y;
    } else if (r >= last.x) {
      z = last.y;
    } else {
      var j = 0;
      for (var k = 1; k < n; k++) {
        if (table_at(vec2<i32>(k, 0)).x <= r) { j = k; }
      }
      let a = table_at(vec2<i32>(j, 0));
      if (a.x == r) { z = a.y; } else { z = a.z * (r - a.x) + a.y; }
    }
  }
  outF_store(p, vec4<f32>(z, 0.0, 0.0, 0.0));
}
