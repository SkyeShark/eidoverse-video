// Port of blender/eidoblend/terrain/solvers/volcanic.py _layered_face's read at f90c6fc (`//! include volcanic/face`,
// after volcanic/math): the rock face of a layered wall at run u (metres outward from its foot) and azimuth az, read
// bilinearly from its table (solvers/volcanic.js faceTable: the 721 x 4097 (Z, S) field `zst`, rg32f, and S0 as
// row 0 of `s0t`, 721 values). numpy:
//     fa = mod(az, TAU) * (720 / TAU); j = minimum(int(fa), 719); g = fa - j
//     fu = clip(u, 0, U) * (4096 / max(U, 1e-9)); i = minimum(int(fu), 4095); f = fu - i
//     z = read(Z); s = read(S); s0 = S0[j] + (S0[j+1] - S0[j]) g; top = Z[j, -1] + (Z[j+1, -1] - Z[j, -1]) g
//     z = where(u > U, top + tw (u - U), where(u < 0, u s0, z)); s likewise (tw, s0); returns (z, 1.1 s)
// A kernel that includes this declares `//! sampler zst rg32f` and `//! sampler s0t r32f`.

const FACE_AZ: i32 = 720;
const FACE_RUN: i32 = 4096;

// (z, the threshold tangent 1.1 s); U the longest column's run, tw tan(wall_deg)
fn layered_face(u: f32, az: f32, U: f32, tw: f32) -> vec2<f32> {
  let fa = v_mod(az, VTAU) * (f32(FACE_AZ) / VTAU);
  let j = min(i32(fa), FACE_AZ - 1);
  let g = fa - f32(j);
  let fu = clamp(u, 0.0, U) * (f32(FACE_RUN) / max(U, 1e-9));
  let i = min(i32(fu), FACE_RUN - 1);
  let f = fu - f32(i);
  let a00 = zst_at(vec2<i32>(i, j));
  let a01 = zst_at(vec2<i32>(i + 1, j));
  let a10 = zst_at(vec2<i32>(i, j + 1));
  let a11 = zst_at(vec2<i32>(i + 1, j + 1));
  let ra = a00 + (a01 - a00) * f;
  let rb = a10 + (a11 - a10) * f;
  let zs = ra + (rb - ra) * g;
  let s0a = s0t_at(vec2<i32>(j, 0)).x;
  let s0 = s0a + (s0t_at(vec2<i32>(j + 1, 0)).x - s0a) * g;
  let ta = zst_at(vec2<i32>(FACE_RUN, j)).x;
  let top = ta + (zst_at(vec2<i32>(FACE_RUN, j + 1)).x - ta) * g;
  var z = zs.x;
  var s = zs.y;
  if (u > U) { z = top + tw * (u - U); s = tw; } else if (u < 0.0) { z = u * s0; s = s0; }
  return vec2<f32>(z, 1.1 * s);
}
