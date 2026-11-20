// Port of blender/eidoblend/terrain/solvers/volcanic.py radial_streaks (and cone_rills' per-cone expression) at
// f90c6fc, at the points of a grid. numpy:
//     r, az = polar(x, y, centre)
//     wander: az += wander_m fbm(x, y, wander_scale_m, seed + 613, octaves=2) / max(r, 0.25 wander_scale_m)
//     lr = log(max(r, 1)); per band b: c = l0 + wid (b + 0.5); w = exp(-((lr - c) / wid)^2); out += w table_b(az);
//     wsum += w^2
//     env = smoothstep(l0 - wid / 2, l0, lr) (1 - smoothstep(l1, l1 + wid / 2, lr)); out = env out / sqrt(max(wsum,
//     1e-12)); sparse: out = -2 max(-out - sparse, 0)
// uMode 0 writes the streaks; uMode 1 is cone_rills' cone over its support rectangle, combined by a maximum into the
// output in place: depth fade smoothstep(1.15 rcr, 1.6 rcr, r) (1 - smoothstep(0.8 R, R, r)) clip(-0.25 s, 0, 1).
// The port's own kernel: float32 in numpy's order; the tables are the bands' azimuth_noise (solvers/volcanic.js).
//! include volcanic/math
//! include volcanic/az
//! include volcanic/noise
//! sampler azt r32f
//! sampler prm           (l0, l1, wid, bands), (sparse 1|0, sparse, wander_m, 0.25 wander_scale_m),
//                        (first band's table row, depth fade (mode 1), rcr, R)
//! sampler ntab          the wander's fbm, two octave terms of two texels each (volcanic.js noiseTexels)
//! image   outF r32f
//! uniform int uMode
//! uniform vec2 uOrg     the grid's origin minus the centre, metres
//! uniform float uStep
//! uniform ivec4 uRect   mode 1: columns [x, z), rows [y, w)

fn fbm2t(t: i32, q: vec2<i32>) -> f32 {
  var total = 0.0;
  var amp = 1.0;
  for (var o = 0; o < 2; o++) {
    let a = ntab_at(vec2<i32>(2 * (t + o), 0));
    let b = ntab_at(vec2<i32>(2 * (t + o) + 1, 0));
    let l = lat_grid(vec2<i32>(a.xy), a.zw, b.x, q);
    total = total + amp * grad_noise(l.c, l.f, bitcast<u32>(b.y), true);
    amp = amp * 0.5;
  }
  return total / (0.24 * sqrt(1.25));
}

fn kmain(p: vec2<i32>) {
  var q = p;
  if (u.uMode == 1) {
    q = p + u.uRect.xy;
    if (q.x >= u.uRect.z || q.y >= u.uRect.w) { return; }
  }
  if (!inside(q, outF_size())) { return; }
  let t0 = prm_at(vec2<i32>(0, 0));
  let t1 = prm_at(vec2<i32>(1, 0));
  let t2 = prm_at(vec2<i32>(2, 0));
  let d = u.uOrg + (vec2<f32>(q) + 0.5) * u.uStep;
  let r = length(d);
  var az = v_az(d);
  if (t1.z != 0.0) { az = az + t1.z * fbm2t(0, q) / max(r, t1.w); }
  let s = az_sampler(az);
  let lr = log(max(r, 1.0));
  let l0 = t0.x;
  let l1 = t0.y;
  let wid = t0.z;
  var o = 0.0;
  var wsum = 0.0;
  for (var b = 0; b < i32(t0.w); b++) {
    let c = l0 + wid * (f32(b) + 0.5);
    let e = (lr - c) / wid;
    let w = exp(-(e * e));
    o = o + w * az_read(i32(t2.x) + b, s);
    wsum = wsum + w * w;
  }
  let env = v_smoothstep(l0 - 0.5 * wid, l0, lr) * (1.0 - v_smoothstep(l1, l1 + 0.5 * wid, lr));
  o = env * o / sqrt(max(wsum, 1e-12));
  if (t1.x != 0.0) { o = -2.0 * max(-o - t1.y, 0.0); }
  if (u.uMode == 0) {
    outF_store(q, vec4<f32>(o, 0.0, 0.0, 0.0));
    return;
  }
  let rcr = t2.z;
  let R = t2.w;
  let env2 = v_smoothstep(1.15 * rcr, 1.6 * rcr, r) * (1.0 - v_smoothstep(0.8 * R, 1.0 * R, r));
  let v = t2.y * env2 * clamp(-0.25 * o, 0.0, 1.0);
  outF_store(q, vec4<f32>(max(outF_load(q).x, v), 0.0, 0.0, 0.0));
}
