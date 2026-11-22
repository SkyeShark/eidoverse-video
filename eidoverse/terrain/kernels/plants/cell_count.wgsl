// Port of blender/eidoblend/terrain/build/plant_instances.py at f9fba8c (its flora strokes' sky light as EEVEE gives it
// inside a sward), as a GPU kernel (the port's own step: the header of build/plant_instances.js says why).
// plants/cell_count: per plant of a flora stroke the count of plants in its cell (plants/flora_cell's key into the
// bincount of the keys), as a float for its mean; 0 for a plant of another variant (the table's last slot).
//! include plants/lib
//! sampler keys r32ui    per plant its cell's key (plants/flora_cell)
//! sampler counts r32ui  per key its plants
//! image   outC r32f     per plant its cell's count
//! uniform int uMask     the table's size (the other variants' key)
//! uniform int uCount

fn kmain(p: vec2<i32>) {
  let q = lin(p);
  if (q >= u.uCount) { return; }
  let k = keys_b[q];
  outC_b[q] = select(f32(counts_b[k]), 0.0, k >= u32(u.uMask));
}
