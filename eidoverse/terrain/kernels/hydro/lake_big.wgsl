// Port of the per-label decision of blender/eidoblend/terrain/solvers/hydro.py lakes at f90c6fc:
//     big = maxd > threshold_m;  big[0] = False;  big &= ~touches;   nlakes = int(big.sum())
// one invocation per label (a list, core/prims.js lineGroups). The threshold arrives as the largest float32 at or
// below numpy's float64 threshold, so maxd > uThr is numpy's comparison exactly for float32 depths. The count is
// an integer atomic (order-independent). Exact.
//! include prims/lib
//! sampler maxd r32ui       per label: the bits of its largest depth (lake_labels.wgsl)
//! sampler touch r32ui      per label: 1 when it reaches the border band or a flatten area
//! image   big r32ui        per label: 1 for a depression that becomes a lake (mode 'lake'), else 0
//! image   count atomic_u32 [0]: how many labels are big
//! uniform int uCount       the labels' list length, n + 1
//! uniform float uThr       the largest float32 at or below the threshold, metres

fn kmain(p: vec2<i32>) {
  let l = line_index(p);
  if (l >= u.uCount) { return; }
  var b = 0u;
  if (l > 0 && bitcast<f32>(maxd_b[l]) > u.uThr && touch_b[l] == 0u) {
    b = 1u;
    atomicAdd(&count_b[0], 1u);
  }
  big_b[l] = b;
}
