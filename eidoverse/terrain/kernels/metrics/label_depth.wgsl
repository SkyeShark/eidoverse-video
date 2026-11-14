// Port of blender/eidoblend/terrain/core/metrics.py at f90c6fc: depressions' per-label reductions
// (np.maximum.at(maxd, lab, depth), keep = maxd > thr, keep[lab].mean(), keep.sum()).
//
// Three modes over one set of bindings:
//   0  every labelled cell raises its label's entry of `acc` to its depth: atomicMax on the depth's bits, which
//      order as the floats do because a depth is never negative (PORT_PLAN.md 2.3: integer atomics on monotonic
//      bit patterns, so the result is the same whatever the order)
//   1  outF = 1 where the cell's label is kept (its deepest point is over the threshold), else 0
//   2  outF (a list, one item per label) = 1 where label k is kept
//! include prims/lib
//! sampler lab r32ui        the labels, 0 the background (core/prims.js label)
//! sampler depth            filled - h, metres
//! image   acc atomic_u32   one entry per label (index = the label), cleared by the caller before mode 0
//! image   outF r32ui       mode 1: the level's shape; mode 2: a list of count + 1 items
//! uniform int uMode
//! uniform float uThr       the threshold, metres (the largest float32 at or below the float64 threshold)
//! uniform int uCount       the number of labels

fn kmain(p: vec2<i32>) {
  if (u.uMode == 2) {
    let no = outF_size();
    if (!inside(p, no)) { return; }
    let k = p.y * no.x + p.x;
    var keep = 0u;
    if (k >= 1 && k <= u.uCount && bitcast<f32>(atomicLoad(&acc_b[k])) > u.uThr) { keep = 1u; }
    outF_store(p, keep);
    return;
  }
  let n = lab_size();
  if (!inside(p, n)) { return; }
  let l = lab_at(p);
  if (u.uMode == 0) {
    if (l != 0u) { atomicMax(&acc_b[l], bitcast<u32>(max(depth_at(p).x, 0.0))); }
    return;
  }
  var keep = 0u;
  if (l != 0u && bitcast<f32>(atomicLoad(&acc_b[l])) > u.uThr) { keep = 1u; }
  outF_store(p, keep);
}
