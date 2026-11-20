// Port of the label decisions of blender/eidoblend/terrain/solvers/coast.py at f90c6fc (sea_phi, _connected and the
// stacks' detached land), as a kernel over a level's cells, with core/prims.js label's components:
//   uPass 0  per label, by order-independent integer atomics: flag[l] = 1 where a cell of l lies on the window's edge
//            (edge_distance < 1; uEdge 1) or where `a` > 0.5 (uMarkA 1: the original sea under a cut cell); cnt[l]
//            counts its cells (np.bincount)
//   uPass 1  keep[lab] as 1 / 0 (outK), from the label list `keep` the CPU settled (np.unique / argmax there)
//   uPass 2  outK = (lab > 0) & (lab != uLargest)              (the stacks: land the cut detached from the mainland)

//! sampler lab r32ui
//! sampler a
//! sampler keep r32ui
//! image   outK r32f
//! image   flag atomic_u32
//! image   cnt atomic_u32
//! uniform int uPass
//! uniform int uEdge
//! uniform int uMarkA
//! uniform int uLargest
//! uniform int uW
//! uniform int uH
fn kmain(p: vec2<i32>) {
  let n = vec2<i32>(u.uW, u.uH);
  if (!inside(p, n)) { return; }
  let l = lab_at(p);
  if (u.uPass == 0) {
    atomicAdd(&cnt_b[l], 1u);
    if (l > 0u && ((u.uEdge != 0 && on_edge(p, n)) || (u.uMarkA != 0 && a_at(p).x > 0.5))) { atomicMax(&flag_b[l], 1u); }
    return;
  }
  var v = false;
  if (u.uPass == 1) {
    v = keep_at(vec2<i32>(i32(l), 0)) != 0u;
  } else {
    v = l > 0u && i32(l) != u.uLargest;
  }
  outK_store(p, vec4<f32>(select(0.0, 1.0, v), 0.0, 0.0, 0.0));
}
