// plants/cover_acc: one species' term of plants.py _level_cover (blender/eidoblend/terrain/build/plants.py at
// f9fba8c) at the grid points of a level: the density clipped to the cluster process's ceiling and kept off the
// excluded ground, the undergrowth thinned under the expected tree cover (uS.w 1), times the share a hard core keeps
// (_kept_by_core: Matern's second process at dens g(0), 1 - exp(-a) over a) and the mean crown area; added to its
// kind's exponent, and to the far exponent times the share the plan's instances leave (1 - the kept-area profile
// at the point's distance from the focus, np.interp with 0 beyond the radius; with no plan, all of it).
//! sampler dens r32f     per point: the density (the species' generated kernel)
//! sampler allowed r32ui per point: 1 where the exclusions allow it
//! sampler tshade r32f   per point: 1 - exp(-the trees' exponent) (read when uS.w is 1)
//! sampler dist r32f     per point: the path distance to the focus (read when uK.x is 1)
//! sampler prof r32f     the kept-area profile: 48 shares, per band of uK.y metres
//! image   outE r32f     the kind's exponent (added to)
//! image   outF r32f     the kind's far exponent (added to)
//! uniform vec4 uS       dmax, 1 - shade tolerance, the mean crown area, 1: thin under the trees
//! uniform vec4 uC       g(0) pi d^2 (a = dens x this), 1: has a hard core, 0, 0
//! uniform vec4 uK       1: a plan's profile, the band, 1: the species was placed somewhere, 0
//! uniform int  uCount

fn kept_at(d: f32) -> f32 {
  if (u.uK.z < 0.5) { return 0.0; }
  let step = u.uK.y;
  // xp = (k + 0.5) step for k < 48, then 48 step (fp 0 there); np.interp: fp[0] left of xp[0], 0 right of the last
  let x = d / step - 0.5;
  if (x <= 0.0) { return prof_b[0]; }
  if (d >= 48.0 * step) { return 0.0; }
  let k = i32(floor(x));
  if (k >= 47) {
    let t = (d - 47.5 * step) / (0.5 * step);
    return prof_b[47] * (1.0 - t);
  }
  let t = x - f32(k);
  return prof_b[k] + (prof_b[k + 1] - prof_b[k]) * t;
}

fn kmain(p: vec2<i32>) {
  let n = outE_size();
  let q = p.y * n.x + p.x;
  if (q >= u.uCount || p.x >= n.x) { return; }
  var d = clamp(dens_b[q], 0.0, u.uS.x);
  if (allowed_b[q] == 0u) { d = 0.0; }
  if (u.uS.w > 0.5) { d = d * (1.0 - tshade_b[q] * u.uS.y); }
  var kb = 1.0;
  if (u.uC.y > 0.5) {
    let a = d * u.uC.x;
    if (a > 1e-9) {
      var e: f32;
      if (a < 0.5) {
        var s = 1.0;
        for (var m = 12; m >= 2; m--) { s = 1.0 - a * s / f32(m); }
        e = s;                                   // (1 - exp(-a)) / a by its series
      } else {
        e = (1.0 - exp(-a)) / a;
      }
      kb = e;
    }
  }
  let e = d * kb * u.uS.z;
  outE_b[q] = outE_b[q] + e;
  var far = e;
  if (u.uK.x > 0.5) { far = e * (1.0 - kept_at(dist_b[q])); }
  outF_b[q] = outF_b[q] + far;
}
