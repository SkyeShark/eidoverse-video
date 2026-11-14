// reduce_next: one more level of the reduction tree reduce_first starts: each output cell folds an 8 x 8 block of
// block results (min of mins, max of maxes, sum of sums in row-major order, counts added).
//! include prims/lib
//! sampler inS           x: min, y: max, z: sum
//! sampler inN r32ui     cells counted
//! sampler inC r32ui     cells not zero
//! image   outS rgba32f
//! image   outN r32ui
//! image   outC r32ui

const BLOCK: i32 = 8;

fn kmain(p: vec2<i32>) {
  let no = outS_size();
  if (!inside(p, no)) { return; }
  let n = inS_size();
  var lo = BIG;
  var hi = -BIG;
  var sum = 0.0;
  var cnt = 0u;
  var nz = 0u;
  for (var j = 0; j < BLOCK; j++) {
    for (var i = 0; i < BLOCK; i++) {
      let q = p * BLOCK + vec2<i32>(i, j);
      if (!inside(q, n)) { continue; }
      let c = inN_at(q);
      if (c == 0u) { continue; }
      let s = inS_at(q);
      lo = min(lo, s.x);
      hi = max(hi, s.y);
      sum += s.z;
      cnt += c;
      nz += inC_at(q);
    }
  }
  outS_store(p, vec4<f32>(lo, hi, sum, 0.0));
  outN_store(p, cnt);
  outC_store(p, nz);
}
