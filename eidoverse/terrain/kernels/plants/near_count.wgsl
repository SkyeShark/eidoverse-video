// plants/near_count: plant_instances.py card_distance's counts over a species' spots: 1 where the spot lies within
// uR of the focus (plants.py path_distance), and its scale (the mean a shrub's card distance reads), per spot. The
// spots' float32 x and y split exactly into the kernels' (integer, fraction) positions.
//! include plants/lib
//! include plants/focus
//! sampler foc r32f      the focus' points (plants/focus.wgsl)
//! sampler rec r32f      the spots' records, 12 numbers each (x, y at 0, 1; scale at 4)
//! image   outF r32ui    1 within uR of the focus, else 0
//! image   outS r32f     the spot's scale
//! uniform float uR
//! uniform int uCount
//! uniform int uFocusN

fn kmain(p: vec2<i32>) {
  let q = lin(p);
  if (q >= u.uCount) { return; }
  let x = rec_b[12 * q];
  let y = rec_b[12 * q + 1];
  let pos = vec4<f32>(floor(x), x - floor(x), floor(y), y - floor(y));
  outF_b[q] = select(0u, 1u, path_dist(pos) <= u.uR);
  outS_b[q] = rec_b[12 * q + 4];
}
