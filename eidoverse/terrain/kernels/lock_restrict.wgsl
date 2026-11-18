// Port of the inline kernel LOCK_RESTRICT ('lock_restrict') of blender/eidoblend/terrain/solvers/fluvial.py at
// f90c6fc.
//
// Transcribed statement for statement from the GLSL source in fluvial.py (PORT_PLAN.md 3.3: an inline kernel
// becomes a file of the same name); the `//!` header is the GLSL's, unchanged. The changes are WGSL's: texelFetch is
// x_at, imageStore is outR_store, imageSize is outR_size(), textureSize is st_size(), a uniform uX is u.uX, and the
// ?: is an if. The sums run in the GLSL's order (each row, then the rows), so the block means round as Blender's
// kernel rounds them.
//
// The low-pass lock (fluvial.py): a refining level must add detail, not move the landform. Every b x b block of its
// cells keeps the mean it started with (its parent's surface, upsampled). restrict: the blocks' drift from their
// targets. Twin: solvers/fluvial.py lock_restrict (offset_block_means).
//! sampler st       x: h of the refining level (n x n)
//! sampler tgt      x: each block's target mean
//! image   outR r32f
//! uniform int uB    the block, cells
//! uniform ivec2 uOff the block grid's offset, cells: block p covers cells uB p - uOff .. + uB (clipped to the grid)

fn kmain(p: vec2<i32>) {
  let m = outR_size();
  if (!inside(p, m)) { return; }
  let n = st_size();
  let c0 = max(u.uB * p - u.uOff, vec2<i32>(0, 0));
  let c1 = min(u.uB * p - u.uOff + u.uB, n);
  var s = 0.0;
  for (var j = c0.y; j < c1.y; j++) {
    var row = 0.0;
    for (var i = c0.x; i < c1.x; i++) { row += st_at(vec2<i32>(i, j)).x; }
    s += row;
  }
  let cnt = max(c1.x - c0.x, 0) * max(c1.y - c0.y, 0);
  var r = 0.0;
  if (cnt > 0) { r = s / f32(cnt) - tgt_at(p).x; }
  outR_store(p, vec4<f32>(r, 0.0, 0.0, 0.0));
}
