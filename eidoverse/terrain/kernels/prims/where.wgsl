// where: a comparison of one channel of a float field with a value, cell by cell (numpy's a <= v, a == v ...): 1 or
// 0, or with uIndex 1 the cell's row-major index where it holds and NONE where it does not (with reduce_u32's
// minimum, np.argmin's first index of the minimum: where(a == a.min())). Exact.
//! include prims/lib
//! sampler src
//! image   outF r32ui
//! uniform int uOp       0: <, 1: <=, 2: ==, 3: >=, 4: >, 5: !=
//! uniform float uValue
//! uniform int uChannel
//! uniform int uIndex

fn kmain(p: vec2<i32>) {
  let n = src_size();
  if (!inside(p, n)) { return; }
  let v = src_at(p)[u.uChannel];
  var t = false;
  switch u.uOp {
    case 0: { t = v < u.uValue; }
    case 1: { t = v <= u.uValue; }
    case 2: { t = v == u.uValue; }
    case 3: { t = v >= u.uValue; }
    case 4: { t = v > u.uValue; }
    default: { t = v != u.uValue; }
  }
  var r = 0u;
  if (u.uIndex != 0) {
    r = NONE;
    if (t) { r = u32(p.y * n.x + p.x); }
  } else if (t) {
    r = 1u;
  }
  outF_store(p, r);
}
