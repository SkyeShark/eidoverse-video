// Port of blender/eidoblend/terrain/masks.py at f90c6fc: compute's rock, float32 as numpy has it:
// steep = smoothstep(rock_deg, slope), with wear max(steep, smoothstep(rock_wear_m, wear)) (the raw wear field);
// rock = steep (1 - cover_w) dry.
//! include masks/lib
//! sampler geo           (p, q, g, slope)
//! sampler surf          (dry, cover_w, wet_cell, 0)
//! sampler wear          the wear field (uHasWear), else any field
//! image   outF r32f
//! uniform vec2 uRock    smoothstep(rock_deg): (e0, k)
//! uniform vec2 uWear    smoothstep(rock_wear_m): (e0, k)
//! uniform int uHasWear

fn kmain(p: vec2<i32>) {
  let n = outF_size();
  if (!inside(p, n)) { return; }
  var steep = ss(geo_at(p).w, u.uRock);
  if (u.uHasWear != 0) { steep = max(steep, ss(wear_at(p).x, u.uWear)); }
  let s = surf_at(p);
  outF_store(p, vec4<f32>((steep * (1.0 - s.y)) * s.x, 0.0, 0.0, 0.0));
}
