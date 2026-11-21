// plants/mark: out[index[q]] = 1 for q < uCount (the items a selection keeps, as a 0/1 list over all of them): what
// plants.py _kept_profile's np.bincount(b[idx]) counts after max_count's cap.
//! include plants/lib
//! sampler index r32ui
//! image   outM r32ui
//! uniform int uCount

fn kmain(p: vec2<i32>) {
  let q = lin(p);
  if (q >= u.uCount) { return; }
  outM_b[index_b[q]] = 1u;
}
