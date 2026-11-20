// The port's own kernel: world noise at a list of points, for blender/eidoblend/terrain/solvers/glacial.py
// centrelines at f90c6fc, which evaluates numpy's world_noise.fbm at its seeds (the walls' and the fans' wobble):
// world_noise_field.wgsl's evaluation (the same term table, core/world_noise.js leafTerms, and kernels/noise.wgsl's
// lattice), at points given in metres from the table's origin instead of a grid's cell centres. A file of its own
// because Blender dispatches no kernel there (numpy runs it): the dispatch log sets the port's own kernels aside
// (PORT_PLAN.md 5.7), and world_noise_field is a Blender kernel.
//! include noise
//! sampler terms     two texels per lattice term: (mode, 1/w, amp, period), (base x, base y, frac x, frac y)
//! sampler pts       per point: x, y in metres from the table's origin (the level's corner)
//! image   outF r32f per point: the noise
//! uniform int uTerms
//! uniform float uConst
//! uniform int uCount

fn kmain(p: vec2<i32>) {
  let w = outF_size().x;
  let i = p.y * w + p.x;
  if (p.x >= w || i >= u.uCount) { return; }
  let local = pts_b[i].xy;
  var acc = u.uConst;
  for (var t = 0; t < u.uTerms; t++) {
    let a = terms_at(vec2<i32>(2 * t, 0));
    let b = terms_at(vec2<i32>(2 * t + 1, 0));
    let lc = b.zw + local * a.y;
    let fl = floor(lc);
    let v = eido_lattice(vec2<i32>(b.xy) + vec2<i32>(fl), lc - fl, i32(a.w));
    acc += a.z * select(v, abs(v), a.x > 0.5);
  }
  outF_b[i] = acc;
}
