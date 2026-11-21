// plants/crowns: the placed trees' crowns in a level raster's texels (plants.py PlantSpots.cover): from the spots'
// records (12 numbers: x, y at 0-1, scale at 4), the centre ((x - x0) / cell, (y - y0) / cell) and the radius
// crown_m x scale / cell, 4 numbers a crown for plants/discs.
//! include plants/lib
//! sampler rec r32f      the spots' records, 12 numbers each
//! image   outC r32f     4 numbers a crown
//! uniform vec4 uO       x0, y0, the raster's cell, crown_m
//! uniform int  uCount

fn kmain(p: vec2<i32>) {
  let q = lin(p);
  if (q >= u.uCount) { return; }
  let r = 12 * q;
  outC_b[4 * q] = (rec_b[r] - u.uO.x) / u.uO.z;
  outC_b[4 * q + 1] = (rec_b[r + 1] - u.uO.y) / u.uO.z;
  outC_b[4 * q + 2] = u.uO.w * rec_b[r + 4] / u.uO.z;
  outC_b[4 * q + 3] = 0.0;
}
