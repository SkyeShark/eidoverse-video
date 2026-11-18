// Port of blender/eidoblend/terrain/solvers/fluvial.py (d8_receivers) and solvers/hydro.py (flow_receivers) at
// f90c6fc: numpy code the Blender edition runs over a whole level, as one GPU kernel (PORT_PLAN.md 3.2, the hydro
// row). solvers/hydro.js d8Receivers and flowReceivers drive it.
//
// d8_receivers (mode 0): every cell's steepest strictly lower neighbour, common.glsl's neighbour order, the slope
// s_k = (h - h_k) / LEN[k] with LEN the twins' float32 lengths; `better = s > best` from best = 0, so a tie keeps
// the earlier neighbour. An off-grid neighbour is never lower (numpy pads with +inf; d8_receivers never wraps).
// With uBreach, a cell of the `breach` mask that has none takes its lowest neighbour instead (the first k of the
// smallest h_k).
// flow_receivers (mode 1): d8_receivers without a breach, then each cell that has none and lies on a flat (its
// breadth-first distance dist > 0, hydro.flat_distance) takes its first neighbour, in the same order and wrapped
// on a periodic axis, of equal height whose distance is one step less.
//
// The surface is read as an exact pair (hydro/lib): a float32 field is (h, 0); numpy's float64 h + water across a
// lake, which is not a float32 value, is (hi, lo) (kernels/hydro/surface_in.wgsl). Exactness: numpy compares the
// slopes in float64, where h - h_k is exact. Two neighbours at the same distance (both sides or both diagonals) are
// compared by their heights, h_k < h_best (as pairs): the same order as numpy's slopes, exactly. A side against a
// diagonal compares d_side * LEN against d_diagonal through fma(), the differences rounded once from the exact
// pairs (hydro/lib p_diff); its sign is the exact product's when the backend fuses it. Only a side and a diagonal
// slope within a rounding of each other could be ordered otherwise (tests/hydro counts them on every fixture and
// floor run's level).
//! include prims/lib
//! include hydro/lib
//! sampler W               the surface (metres): r32f, or rg32f (hi, lo)
//! sampler dist r32ui      mode 1: flat_distance(W) (breadth-first steps); mode 0: a 1 x 1 stand-in
//! sampler breach          mode 0 with uBreach 1: the cells (nonzero) that take their lowest neighbour; else a stand-in
//! image   outR r32i       the receiver as a row-major index, -1 for none
//! uniform int uMode       0: d8_receivers; 1: flow_receivers
//! uniform int uBreach
//! uniform int uWrapX      flow_receivers' wrap: the columns wrap (a periodic axis)
//! uniform int uWrapY      the rows wrap

fn diagonal(k: i32) -> bool { return k == 0 || k == 2 || k == 5 || k == 7; }

// (h - hq) / LEN[k] > (h - hb) / LEN[kb], with the best's slope positive (fluvial.d8_receivers' s > best)
fn steeper(h: vec2<f32>, hq: vec2<f32>, kd: bool, hb: vec2<f32>, bd: bool) -> bool {
  if (kd == bd) { return p_less(hq, hb); }
  let dq = p_diff(h, hq);
  let db = p_diff(h, hb);
  if (!kd) { return fma(dq, LEN[0], -db) > 0.0; }     // a side against a diagonal best: dq > db / LEN
  return fma(-db, LEN[0], dq) > 0.0;                   // a diagonal against a side best: dq / LEN > db
}

fn kmain(p: vec2<i32>) {
  let n = W_size();
  if (!inside(p, n)) { return; }
  let h = W_at(p).xy;
  var kb = -1;
  var hb = vec2<f32>(0.0, 0.0);
  var bd = false;
  var kl = -1;
  var low = vec2<f32>(0.0, 0.0);
  for (var k = 0; k < 8; k++) {
    let q = p + OFF[k];
    if (!inside(q, n)) { continue; }
    let hq = W_at(q).xy;
    let kd = diagonal(k);
    var better = false;
    if (kb < 0) { better = p_less(hq, h); } else { better = steeper(h, hq, kd, hb, bd); }
    if (better) {
      kb = k;
      hb = hq;
      bd = kd;
    }
    if (kl < 0 || p_less(hq, low)) {
      kl = k;
      low = hq;
    }
  }
  var r = -1;
  if (kb >= 0) {
    let q = p + OFF[kb];
    r = q.y * n.x + q.x;
  } else if (u.uMode == 0 && u.uBreach != 0 && kl >= 0 && breach_at(p).x != 0.0) {
    let q = p + OFF[kl];
    r = q.y * n.x + q.x;
  }
  if (u.uMode == 1 && r < 0) {
    let dn = dist_at(p);
    if (dn > 0u) {
      for (var k = 0; k < 8; k++) {
        var q: vec2<i32>;
        if (!neighbour_w(p, k, n, u.uWrapX, u.uWrapY, &q)) { continue; }
        if (p_equal(W_at(q).xy, h) && dist_at(q) == dn - 1u) {
          r = q.y * n.x + q.x;
          break;
        }
      }
    }
  }
  outR_store(p, r);
}
