// The port's own kernel (no Blender counterpart): the channel cells solvers/rivers.js decided again in doubles
// (blender/eidoblend/terrain/solvers/rivers.py channel() at f90c6fc, its float64 distance against the half width),
// written over kernels/strata/river_channel.wgsl's float32 result. One invocation per decided cell.
//! sampler fidx r32ui     the cells (row-major index j n + i)
//! sampler fk r32ui       their nearest segment k (0xffffffff: none)
//! sampler fv rgba32f     their t, distance, channel flag (0 / 1), 0
//! image   outD r32f
//! image   outK r32ui
//! image   outT r32f
//! image   outM r32f
//! uniform int uCount
//! local   64 1

fn kmain(p: vec2<i32>) {
  if (p.x >= u.uCount) { return; }
  let c = fidx_b[p.x];
  let v = fv_b[p.x];
  outD_b[c] = v.y;
  outK_b[c] = fk_b[p.x];
  outT_b[c] = v.x;
  outM_b[c] = v.z;
}
