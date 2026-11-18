// Port of blender/eidoblend/terrain/masks.py at f90c6fc: compute's aspect, northness and eastness, float32 as numpy
// computes them from p and q:
//   aspect     arctan2(-p, -q) (180 / pi) % 360 (np.remainder: below zero + 360, which may round to 360 itself as
//              numpy's does), 0 where g <= 1e-9
//   northness  -q fade, eastness -p fade, fade = smoothstep(1, 3, slope) / max(g, 1e-12)
//! include masks/lib
//! sampler geo           (p, q, g, slope): masks/gradient.wgsl
//! image   outA r32f     aspect
//! image   outN r32f     northness
//! image   outE r32f     eastness
//! uniform vec2 uFade    smoothstep(1, 3): (e0, k)

fn kmain(p: vec2<i32>) {
  let n = outA_size();
  if (!inside(p, n)) { return; }
  let v = geo_at(p);
  var asp = atan2(-v.x, -v.y) * 57.29577951308232;
  if (asp < 0.0) { asp = asp + 360.0; }
  outA_store(p, vec4<f32>(select(0.0, asp, v.z > 1e-9), 0.0, 0.0, 0.0));
  let fade = ss(v.w, u.uFade) / max(v.z, 1e-12);
  outN_store(p, vec4<f32>(-v.y * fade, 0.0, 0.0, 0.0));
  outE_store(p, vec4<f32>(-v.x * fade, 0.0, 0.0, 0.0));
}
