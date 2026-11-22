// Port of blender/eidoblend/terrain/build/plant_instances.py at f9fba8c (its SeedThree plants' sky light as EEVEE gives
// it inside a crown), as a GPU kernel (the port's own step: the header of build/plant_instances.js says why).
// plants/alpha_raw: an 8-bit RGBA image's alpha per pixel (0..1), for its mean: the share of a leaf card the leaf
// covers (build/plant_instances.js crownOf).
//! include plants/lib
//! sampler px r32ui      the pixels, RGBA8 packed in a u32 each (R in the low byte)
//! image   outA r32f
//! uniform int uCount

fn kmain(p: vec2<i32>) {
  let q = lin(p);
  if (q >= u.uCount) { return; }
  outA_b[q] = f32((px_b[q] >> 24u) & 255u) / 255.0;
}
