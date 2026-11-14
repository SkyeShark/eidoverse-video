// select_pick: after select_hist, walk each statistic's 256 counts to the digit that holds its rank, append the
// digit to its key and make the rank relative to that digit's cells. One invocation per statistic; a walk of 256
// counts in order. Exact.
//! include prims/lib
//! sampler hist r32ui       row r: the counts select_hist made
//! sampler state r32ui      row r: column 0 the key bits so far, column 1 the rank among their cells
//! image   outState r32ui   the same, one digit further
//! uniform int uShift       this pass's bit position: 24, 16, 8, 0

fn kmain(p: vec2<i32>) {
  let n = outState_size();
  if (p.x != 0 || p.y >= n.y) { return; }
  var prefix = state_at(vec2<i32>(0, p.y));
  var k = state_at(vec2<i32>(1, p.y));
  var cum = 0u;
  for (var b = 0; b < 256; b++) {
    let c = hist_at(vec2<i32>(b, p.y));
    if (k < cum + c) {
      prefix = prefix | (u32(b) << u32(u.uShift));
      k = k - cum;
      break;
    }
    cum += c;
  }
  outState_store(vec2<i32>(0, p.y), prefix);
  outState_store(vec2<i32>(1, p.y), k);
}
