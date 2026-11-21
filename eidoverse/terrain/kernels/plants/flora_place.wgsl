// Port of numpy code of blender/eidoblend/terrain/build/plant_instances.py at f9fba8c, as a GPU kernel.
// plants/flora_place: a flora species' spots as createFlora placements (plant_instances.py _instance_flora): per
// spot in three.js' frame its x and z (-y), its stroke scale scale x size_m[1] / h0 of its individual, and its base
// height (_base_z with half the foot: `sink` x scale under the ground, deeper by the drop across the foot), and its
// individual (the variant, clipped to the seeds). Five numbers a spot.
//! include plants/lib
//! sampler rec r32f      the spots' records, 12 numbers each
//! sampler h0 r32f       per individual size_m[1] / h0 (the stroke scale of a spot of scale 1)
//! image   outP r32f     per spot: x, -y, scale, base z, variant
//! uniform float uSink
//! uniform float uFoot
//! uniform int uVariants
//! uniform int uCount

fn kmain(p: vec2<i32>) {
  let q = lin(p);
  if (q >= u.uCount) { return; }
  let o = 12 * q;
  let sc = rec_b[o + 4];
  let nz = max(rec_b[o + 9], 0.2);
  let tn = sqrt(rec_b[o + 7] * rec_b[o + 7] + rec_b[o + 8] * rec_b[o + 8]) / nz;
  let v = clamp(i32(rec_b[o + 10]), 0, u.uVariants - 1);
  outP_b[5 * q] = rec_b[o];
  outP_b[5 * q + 1] = -rec_b[o + 1];
  outP_b[5 * q + 2] = sc * h0_b[v];
  outP_b[5 * q + 3] = rec_b[o + 2] - sc * (u.uSink + u.uFoot * min(tn, 2.0));
  outP_b[5 * q + 4] = f32(v);
}
