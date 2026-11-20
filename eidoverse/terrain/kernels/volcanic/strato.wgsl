// Port of blender/eidoblend/terrain/solvers/volcanic.py stratovolcano (its outer flank, summit crater, crest union,
// flank craters and breach; not the parasitic cones, which kernels/volcanic/pile.wgsl joins one by one) at f90c6fc,
// with exp_cone, loglinear_cone, _flank_crater and _breach_cut. The port's own kernel: numpy evaluates the shape in
// float64 at a block of points; this is float32 at the points of a grid, each offset from the centre computed as
// (grid origin - centre) + (i + 0.5) step, the origin's offset in doubles (solvers/volcanic.js stratoTable).
//! include volcanic/math
//! include volcanic/az
//! sampler azt r32f      the azimuth tables (rows: radius noise, height noise)
//! sampler prm           the cone's numbers, rgba32f texels (stratoTable):
//                          0 (H, R, rc, dc)
//                          1 (profile 0 exp / 1 loglinear, lam | t, e_foot | rb, A)
//                          2 (zb, elongation, rift az rad, radius_noise)
//                          3 (height_noise, radius-noise row, height-noise row, w: the summit platform)
//                          4 (rt, crater_floor_frac, bowl_depth, the crest union's width)
//                          5 (breach 1 | 0, ex, ey, width_m)
//                          6 (widening, floor at the vent, tan floor_slope, tan wall)
//! sampler fc            the flank craters, two texels each: (ox - at.x, oy - at.y, radius, depth),
//                        (rim_m, z0: the flank at the crater's centre, its downhill azimuth rad, 0)
//! image   outZ r32f     the surface above the foot, metres
//! uniform vec2 uOrg     the grid's origin (ox, oy) minus the centre, metres
//! uniform float uStep   the grid's spacing, metres
//! uniform int uFc       flank craters

fn cone_profile(r: f32, a: vec4<f32>, b: vec4<f32>, zb: f32) -> f32 {
  let H = a.x;
  let R = a.y;
  let rc = a.z;
  if (!(r < R)) { return 0.0; }
  if (b.x == 0.0) {
    // exp_cone: H (e^{-(r - rc)/lambda} - e_foot) / (1 - e_foot)
    return H * (exp(-(r - rc) / b.y) - b.z) / (1.0 - b.z);
  }
  // loglinear_cone: zb + t (rb - r) inside rb, A ln(R / r) outside
  let t = b.y;
  let rb = b.z;
  if (r < rb) { return zb + t * (rb - r); }
  return b.w * log(R / max(r, 1e-6));
}

fn kmain(p: vec2<i32>) {
  let n = outZ_size();
  if (!inside(p, n)) { return; }
  let t0 = prm_at(vec2<i32>(0, 0));
  let t1 = prm_at(vec2<i32>(1, 0));
  let t2 = prm_at(vec2<i32>(2, 0));
  let t3 = prm_at(vec2<i32>(3, 0));
  let t4 = prm_at(vec2<i32>(4, 0));
  let H = t0.x;
  let rc = t0.z;
  let dc = t0.w;
  let d = u.uOrg + (vec2<f32>(p) + 0.5) * u.uStep;
  let r = length(d);
  let az = v_az(d);
  let s = az_sampler(az);
  // outer(): the flank with the azimuthal modulation
  let rift = t2.z;
  let c = cos(az - rift);
  var stretch = 1.0 + (t2.y - 1.0) * (c * c - 0.5);
  if (t2.w != 0.0) { stretch = stretch * (1.0 + t2.w * az_read(i32(t3.y), s)); }
  var hfac = 1.0;
  if (t3.x != 0.0) { hfac = 1.0 + t3.x * az_read(i32(t3.z), s); }
  var rf: f32;
  if (t3.w > 0.0) {
    rf = select(rc, rc + (r - t4.x) / stretch, r > t4.x);
  } else {
    rf = select(r, rc + (r - rc) / stretch, r > rc);
  }
  let z_out = hfac * cone_profile(rf, t0, t1, t2.x);
  // the summit crater: a parabolic bowl from the rim down to H - dc, a flat floor when crater_floor_frac > 0
  let rho = r / rc;
  let f = t4.y;
  let bowl = t4.z;
  var inner = H * (1.0 + (hfac - 1.0) * rho * rho) - bowl * (1.0 - rho * rho);
  if (f > 0.0) { inner = v_smooth_max(inner, H - dc, 0.08 * dc); }
  if (!(rho < 1.6)) { inner = VBIG; }
  var z = v_crest_union(z_out, inner, t4.w);
  // flank craters (_flank_crater)
  for (var k = 0; k < u.uFc; k++) {
    let a = fc_at(vec2<i32>(2 * k, 0));
    let b = fc_at(vec2<i32>(2 * k + 1, 0));
    let dd = a.xy + (vec2<f32>(p) + 0.5) * u.uStep;
    let rr = length(dd);
    let rad = a.z;
    let dep = a.w;
    var bw = (b.y - dep) + dep * ((rr / rad) * (rr / rad));
    if (!(rr < 2.5 * rad)) { bw = VBIG; }
    var o = v_smooth_min(z, bw, 0.06 * dep);
    if (b.x > 0.0) {
      let aa = v_az(dd);
      let side = v_smoothstep(-0.3, 0.8, cos(aa - b.z));
      let e = (rr - rad) / (0.4 * rad);
      let mound = b.x * exp(-(e * e)) * side * v_smoothstep(0.7 * rad, rad, rr);
      o = o + mound;
    }
    z = o;
  }
  // a sector-collapse breach (_breach_cut)
  let t5 = prm_at(vec2<i32>(5, 0));
  if (t5.x != 0.0) {
    let t6 = prm_at(vec2<i32>(6, 0));
    let ex = t5.y;
    let ey = t5.z;
    let W = t5.w;
    let uu = d.x * ex + d.y * ey;
    let vv = -d.x * ey + d.y * ex;
    let up = max(uu, 0.0);
    let half = 0.5 * W * (1.0 + t6.x * up / W);
    let cut = t6.y - t6.z * up + t6.w * (max(abs(vv) - half, 0.0) + max(-uu, 0.0));
    z = v_smooth_min(z, cut, 15.0);
  }
  outZ_store(p, vec4<f32>(z, 0.0, 0.0, 0.0));
}
