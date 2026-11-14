// Port of blender/eidoblend/terrain/core/io.py at f90c6fc: the integer quantisation of export_heightmap (png16, r16),
// export_mask and to_u8: clip(floor(clip((v - lo) / span, 0, 1) * top + 0.5), 0, top) (normalise_heights, then
// _round_half_up), with the north-up row flip, bit for bit what numpy computes in float64.
//
// The quantisation of a float32 value is a non-decreasing step function of it, so q(v) is the number of its steps at
// or below v: the steps T_1 .. T_top (the smallest float32 values with q >= k) are found once per call in JavaScript,
// with numpy's float64 arithmetic (core/io.js quantiseSteps: a table over the quantisation levels, not the cells),
// as order keys (prims/lib.wgsl fkey), and each cell counts them by binary search. Exact for every float32 input; a
// NaN gives 0 (numpy's cast of NaN to an integer, on this hardware).
//! include prims/lib
//! sampler src              the field (its first channel), row 0 south
//! sampler steps r32ui      the step keys, ascending, uTop of them in a list
//! image   outQ r32ui       the quantised value of each cell (row 0 north when uFlip)
//! uniform int uTop
//! uniform int uFlip

fn kmain(p: vec2<i32>) {
  let n = outQ_size();
  if (!inside(p, n)) { return; }
  var j = p.y;
  if (u.uFlip != 0) { j = n.y - 1 - p.y; }
  let key = fkey(src_at(vec2<i32>(p.x, j)).x);
  if (key == NONE) {
    outQ_store(p, 0u);
    return;
  }
  var lo = 0u;
  var hi = u32(u.uTop);
  while (lo < hi) {
    let mid = (lo + hi) >> 1u;
    if (steps_b[mid] <= key) { lo = mid + 1u; } else { hi = mid; }
  }
  outQ_store(p, lo);
}
