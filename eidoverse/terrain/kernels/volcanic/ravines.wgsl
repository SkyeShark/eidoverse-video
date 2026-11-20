// Port of blender/eidoblend/terrain/solvers/volcanic.py ravine_cut at f90c6fc, at the cells of a level: the depth of
// radial ravines cut into a cone, combined by their maximum. numpy, per ravine k:
//     along = r cos(az - a); lat = r sin(az - a)
//     sel = (along > r0 - 3 width) & (along < r1 + 3 width)
//     wander: lat -= wander_m fbm(along, 1000 k, 0.4 (r1 - r0), seed + 97 + k, octaves=3)   (fbm's pointwise path)
//     t = clip((along - r0) / (r1 - r0), 0, 1); prof = smoothstep(0, 0.2, t) (1 - smoothstep(0.67, 1, t))
//     w = width (0.6 + 0.6 t); cut = depth prof exp(-(lat / w)^2); out = max(out, where(sel, cut, 0))
// The port's own kernel (float32; fbm at (along, 1000 k) is noise at points off any grid: noise.wgsl lat_point).
//! include volcanic/math
//! include volcanic/noise
//! sampler rtab          per ravine, two texels: (azimuth rad, r0, r1, depth), (width, wander_m, k, seed bits of
//                        seed + 97 + k)
//! image   outF r32f
//! uniform vec2 uOrg     the level's origin minus the centre
//! uniform float uStep
//! uniform int uCount

fn kmain(p: vec2<i32>) {
  if (!inside(p, outF_size())) { return; }
  let d = u.uOrg + (vec2<f32>(p) + 0.5) * u.uStep;
  let r = length(d);
  let az = v_az(d);
  var out = 0.0;
  for (var k = 0; k < u.uCount; k++) {
    let a = rtab_at(vec2<i32>(2 * k, 0));
    let b = rtab_at(vec2<i32>(2 * k + 1, 0));
    let along = r * cos(az - a.x);
    var lat = r * sin(az - a.x);
    let r0 = a.y;
    let r1 = a.z;
    let width = b.x;
    let sel = along > r0 - 3.0 * width && along < r1 + 3.0 * width;
    if (b.y != 0.0) {
      // fbm(along, 1000 k, 0.4 (r1 - r0), seed + 97 + k, octaves=3)
      let sc = 0.4 * (r1 - r0);
      let base = bitcast<u32>(b.w);
      var total = 0.0;
      var amp = 1.0;
      var norm = 0.0;
      for (var o = 0; o < 3; o++) {
        let so = sc / f32(1 << u32(o));
        let l = lat_point(vec2<f32>(along, 1000.0 * b.z) / so);
        total = total + amp * grad_noise(l.c, l.f, base * 7919u + u32(101 * o + 17), false);
        norm = norm + amp * amp;
        amp = amp * 0.5;
      }
      lat = lat - b.y * (total / (0.24 * sqrt(norm)));
    }
    let t = clamp((along - r0) / max(r1 - r0, 1e-6), 0.0, 1.0);
    let prof = v_smoothstep(0.0, 0.2, t) * (1.0 - v_smoothstep(0.67, 1.0, t));
    let w = width * (0.6 + 0.6 * t);
    let e = lat / w;
    let cut = a.w * prof * exp(-(e * e));
    if (sel) { out = max(out, cut); }
  }
  outF_store(p, vec4<f32>(out, 0.0, 0.0, 0.0));
}
