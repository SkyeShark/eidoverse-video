// Port of numpy code of blender/eidoblend/terrain/build/plant_instances.py at f9fba8c, as a GPU kernel.
// plants/variant_key: each spot's individual, np.clip(variant, 0, uVariants - 1) (plant_instances.py's variants), as
// a u32 key (the spots of each individual counted by a bincount over it).
//! include plants/lib
//! sampler rec r32f      the spots' records, 12 numbers each (the variant at 10)
//! image   outK r32ui
//! uniform int uVariants
//! uniform int uCount

fn kmain(p: vec2<i32>) {
  let q = lin(p);
  if (q >= u.uCount) { return; }
  outK_b[q] = u32(clamp(i32(rec_b[12 * q + 10]), 0, u.uVariants - 1));
}
