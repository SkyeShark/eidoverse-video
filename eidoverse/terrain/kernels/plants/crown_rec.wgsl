// plants/crown_rec: plant_instances.py _crowns: a SeedThree species' plants as the crowns that shade each other, 6
// numbers each (the position as integer part and fraction for plants/grid, its top z + scale x size_m[1], its radius
// crown_m x scale), as u32 bits, written from slot uFirst of the list.
//! include plants/lib
//! sampler rec r32f      the spots' records, 12 numbers each
//! image   outC r32ui    6 numbers a crown
//! uniform vec4 uS       size_m[1], crown_m, 0, 0
//! uniform int  uFirst
//! uniform int  uCount

fn kmain(p: vec2<i32>) {
  let q = lin(p);
  if (q >= u.uCount) { return; }
  let o = 12 * q;
  let x = rec_b[o];
  let y = rec_b[o + 1];
  let d = 6 * (q + u.uFirst);
  outC_b[d] = bitcast<u32>(floor(x));
  outC_b[d + 1] = bitcast<u32>(x - floor(x));
  outC_b[d + 2] = bitcast<u32>(floor(y));
  outC_b[d + 3] = bitcast<u32>(y - floor(y));
  outC_b[d + 4] = bitcast<u32>(rec_b[o + 2] + rec_b[o + 4] * u.uS.x);
  outC_b[d + 5] = bitcast<u32>(rec_b[o + 4] * u.uS.y);
}
