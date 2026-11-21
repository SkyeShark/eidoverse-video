// plants/rock_place: dressing.py place_rocks per candidate (build/dressing.js): kept by rejection (u dmax < the
// density, 0 over water above 0.05) and off the excluded discs; its size from the power law N(>s) ~ s^-alpha between
// s0 and s1 (the toe bias' smallest size s0 (1 + toe_bias grain) where the terrain has the grain map), kept while it
// is at least lod_m_per_m x its distance from the focus; its model among those whose size range holds it (else the
// nearest range); its proportions jittered; its up axis turned `align` of the way from world up to the ground's
// normal, a random turn about it and a small random tilt (rotation A(up) tilt Rz(yaw), as _rotations composes it); its
// centre `bury` of its height under the ground. Out, 20 numbers a candidate: kept (0/1), the max_rocks subset key,
// the model, the size, then its instance matrix in three.js' frame (column-major).
//! include plants/lib
//! sampler cand r32ui    the candidates (plants/rock_cand: 16 numbers, the position at 0-3, the hash at 4-5)
//! sampler dens r32f     the density there (build/plants.js maskExpression)
//! sampler water r32f    the water mask there (unread without one)
//! sampler grain r32f    the surface bake's grain there (unread without it)
//! sampler zs r32f       the ground's height there (build/plants.js groundAt)
//! sampler nrm r32f      the ground's normal there, 3 numbers (Blender axes)
//! sampler tab r32f      the excluded discs (x, y, r: 3 numbers each), then per model its dims (dx, dy, dz, Blender
//                        axes) and size range (lo, hi; hi < 0: no upper bound; lo < 0: never this model)
//! image   outR r32f     20 numbers a candidate
//! uniform vec4  uF      the focus: x integer part, fraction, y integer part, fraction
//! uniform vec4  uA      dmax, s0, s1, alpha
//! uniform vec4  uB      toe_bias, lod_m_per_m, align, tilt (radians)
//! uniform vec4  uC      bury, squash lo, squash hi, 0
//! uniform ivec4 uN      discs, models, has water, has grain
//! uniform int   uCount

fn rod(ax: vec3<f32>, ang: f32) -> mat3x3<f32> {
  let a = normalize(ax);
  let K = mat3x3<f32>(vec3<f32>(0.0, a.z, -a.y), vec3<f32>(-a.z, 0.0, a.x), vec3<f32>(a.y, -a.x, 0.0));
  let I = mat3x3<f32>(vec3<f32>(1.0, 0.0, 0.0), vec3<f32>(0.0, 1.0, 0.0), vec3<f32>(0.0, 0.0, 1.0));
  return I + K * sin(ang) + (K * K) * (1.0 - cos(ang));
}

fn tb(k: i32) -> f32 { return tab_b[k]; }

// Blender (x, y, z) -> three.js (x, z, -y)
fn to3(v: vec3<f32>) -> vec3<f32> { return vec3<f32>(v.x, v.z, -v.y); }

fn kmain(p: vec2<i32>) {
  let q = lin(p);
  if (q >= u.uCount) { return; }
  let o = 16u * u32(q);
  let pos = vec4<f32>(bitcast<f32>(cand_b[o]), bitcast<f32>(cand_b[o + 1u]), bitcast<f32>(cand_b[o + 2u]), bitcast<f32>(cand_b[o + 3u]));
  let h = vec2<u32>(cand_b[o + 4u], cand_b[o + 5u]);
  let x = coord_f32(pos.xy);
  let y = coord_f32(pos.zw);
  var d = max(dens_b[q], 0.0);
  if (u.uN.z == 1 && water_b[q] > 0.05) { d = 0.0; }
  var keep = u53f(u53(h, 2u)) * u.uA.x < d;
  for (var k = 0; k < u.uN.x; k++) {
    let ex = tb(3 * k) - x;
    let ey = tb(3 * k + 1) - y;
    let er = tb(3 * k + 2);
    if (!(ex * ex + ey * ey > er * er)) { keep = false; }
  }
  let s0 = u.uA.y;
  let s1 = u.uA.z;
  let al = u.uA.w;
  let uu = u53f(u53(h, 3u));
  var lo = s0;
  if (u.uB.x > 0.0 && u.uN.w == 1) { lo = min(s0 * (1.0 + u.uB.x * clamp(grain_b[q], 0.0, 1.0)), 0.95 * s1); }
  let size = lo * pow(1.0 - uu * (1.0 - pow(lo / s1, al)), -1.0 / al);
  let dist = sqrt(coord_sub(pos.xy, u.uF.xy) * coord_sub(pos.xy, u.uF.xy) + coord_sub(pos.zw, u.uF.zw) * coord_sub(pos.zw, u.uF.zw));
  keep = keep && size >= max(s0, u.uB.y * dist);
  // the model: uniformly among those whose range holds the size, else the nearest range (_pick)
  let mt = 3 * u.uN.x;
  var nok = 0;
  var best = 3.4e38;
  for (var m = 0; m < u.uN.y; m++) {
    let mlo = tb(mt + 5 * m + 3);
    var mhi = tb(mt + 5 * m + 4);
    if (mhi < 0.0) { mhi = 3.4e38; }
    if (mlo < 0.0) { continue; }
    if (size >= mlo && size <= mhi) { nok++; }
    best = min(best, max(mlo - size, 0.0) + max(size - mhi, 0.0));
  }
  let take = u53f(u53(h, 5u));
  var pick = 0;
  var seen = 0;
  var want = 0;
  if (nok > 0) {
    want = min(i32(take * f32(nok)), nok - 1);
  } else {
    // the nearest ranges (ties: uniformly among them)
    for (var m = 0; m < u.uN.y; m++) {
      let mlo = tb(mt + 5 * m + 3);
      var mhi = tb(mt + 5 * m + 4);
      if (mhi < 0.0) { mhi = 3.4e38; }
      if (mlo >= 0.0 && max(mlo - size, 0.0) + max(size - mhi, 0.0) == best) { nok++; }
    }
    want = min(i32(take * f32(max(nok, 1))), max(nok, 1) - 1);
  }
  for (var m = 0; m < u.uN.y; m++) {
    let mlo = tb(mt + 5 * m + 3);
    var mhi = tb(mt + 5 * m + 4);
    if (mhi < 0.0) { mhi = 3.4e38; }
    if (mlo < 0.0) { continue; }
    var ok = size >= mlo && size <= mhi;
    if (best > 0.0 && !ok) { ok = max(mlo - size, 0.0) + max(size - mhi, 0.0) == best; }
    if (ok) {
      if (seen == want) { pick = m; }
      seen++;
    }
  }
  let dims = vec3<f32>(tb(mt + 5 * pick), tb(mt + 5 * pick + 1), tb(mt + 5 * pick + 2));
  let kk = size / max(max(dims.x, dims.y), 1e-6);
  let sc = vec3<f32>(kk * (0.9 + 0.2 * u53f(u53(h, 6u))), kk * (0.9 + 0.2 * u53f(u53(h, 7u))),
                     kk * (u.uC.y + (u.uC.z - u.uC.y) * u53f(u53(h, 8u))));
  let hgt = dims.z * sc.z;
  let n = normalize(vec3<f32>(nrm_b[3 * q], nrm_b[3 * q + 1], nrm_b[3 * q + 2]));
  let a = u.uB.z;
  let up = normalize(vec3<f32>(0.0, 0.0, 1.0 - a) + a * n);
  let yaw = 6.2831853071795864769 * u53f(u53(h, 9u));
  let phi = 6.2831853071795864769 * u53f(u53(h, 10u));
  let g1 = max(u53f(u53(h, 11u)), 1e-12);
  let g2 = u53f(u53(h, 12u));
  let tilt = u.uB.w * sqrt(-2.0 * log(g1)) * cos(6.2831853071795864769 * g2);
  let Rz = mat3x3<f32>(vec3<f32>(cos(yaw), sin(yaw), 0.0), vec3<f32>(-sin(yaw), cos(yaw), 0.0), vec3<f32>(0.0, 0.0, 1.0));
  let T = rod(vec3<f32>(cos(phi), sin(phi), 0.0), tilt);
  var axis = cross(vec3<f32>(0.0, 0.0, 1.0), up);
  if (length(axis) < 1e-9) { axis = vec3<f32>(1.0, 0.0, 0.0); }
  let A = rod(axis, acos(clamp(up.z, -1.0, 1.0)));
  let Rb = A * T * Rz;
  let zc = zs_b[q] + (0.5 - u.uC.x) * hgt * up.z;
  // three.js: C (R S) C^T, C (x, y, z) = (x, z, -y): its columns C b0, C b2, -C b1
  let b0 = Rb[0] * sc.x;
  let b1 = Rb[1] * sc.y;
  let b2 = Rb[2] * sc.z;
  let c0 = to3(b0);
  let c1 = to3(b2);
  let c2 = -to3(b1);
  let r = 20 * q;
  outR_b[r] = select(0.0, 1.0, keep);
  outR_b[r + 1] = u53f(u53(h, 4u));
  outR_b[r + 2] = f32(pick);
  outR_b[r + 3] = size;
  outR_b[r + 4] = c0.x; outR_b[r + 5] = c0.y; outR_b[r + 6] = c0.z; outR_b[r + 7] = 0.0;
  outR_b[r + 8] = c1.x; outR_b[r + 9] = c1.y; outR_b[r + 10] = c1.z; outR_b[r + 11] = 0.0;
  outR_b[r + 12] = c2.x; outR_b[r + 13] = c2.y; outR_b[r + 14] = c2.z; outR_b[r + 15] = 0.0;
  outR_b[r + 16] = x; outR_b[r + 17] = zc; outR_b[r + 18] = -y; outR_b[r + 19] = 1.0;
}
