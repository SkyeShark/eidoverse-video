// One round of pointer jumping that carries a path maximum and the cell it comes from: for the routing surface's
// descent (kernels/hydro/descend.wgsl, blender/eidoblend/terrain/solvers/hydro.py _descend at f90c6fc, in the
// path-maximum form of PORT_PLAN.md C11). core/prims.js pathMax carries the value alone (prims/jump_max.wgsl); the
// descent needs the cell too, so that its result is made from that cell's own height (descend.wgsl says why).
//     (key, arg) = the larger of (key, arg) and (key, arg)[ptr], the smaller cell index on equal keys;  ptr = ptr[ptr]
// After ceil(log2(longest path)) rounds each cell holds the largest key on its path to the outlet (both ends
// included) and where it is. The choice is a maximum with a fixed tie order: associative, so exact and the same in
// any order of the rounds.
//! include prims/lib
//! sampler ptr r32ui       every cell's pointer (prims/jump_init.wgsl: the receiver, or the cell itself)
//! sampler key             the largest key so far
//! sampler arg r32ui       the cell it comes from
//! image   outP r32ui
//! image   outK r32f
//! image   outA r32ui

fn kmain(p: vec2<i32>) {
  let n = ptr_size();
  if (!inside(p, n)) { return; }
  let i = p.y * n.x + p.x;
  let q = ptr_b[i];
  var k = key_b[i];
  var a = arg_b[i];
  let kq = key_b[q];
  let aq = arg_b[q];
  if (kq > k || (kq == k && aq < a)) {
    k = kq;
    a = aq;
  }
  outP_store(p, ptr_b[q]);
  outK_store(p, vec4<f32>(k, 0.0, 0.0, 0.0));
  outA_store(p, a);
}
