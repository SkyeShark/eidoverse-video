// Port of numpy code of blender/eidoblend/terrain/surface/bake.py at d67f19e, as a GPU kernel (the port's own,
// PORT_PLAN.md 3.2). differ: how many cells of two fields differ (channel x), counted with an integer atomic (an
// order-independent count, plan 2.3): the fill's convergence test, numpy's np.array_equal(prev, cur) of the surface
// after two chunks of passes, read back as four bytes instead of the whole grid.
//! sampler a
//! sampler b
//! image   cnt atomic_u32

fn kmain(p: vec2<i32>) {
  let n = a_size();
  if (!inside(p, n)) { return; }
  if (a_at(p).x != b_at(p).x) { atomicAdd(&cnt_b[0], 1u); }
}
