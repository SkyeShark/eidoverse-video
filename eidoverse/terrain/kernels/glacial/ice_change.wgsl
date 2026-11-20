// The port's own kernel: the convergence test of blender/eidoblend/terrain/solvers/glacial.py ice_flux_converge at
// f90c6fc,
//     cur = dev.read(src) (float64);  change = max(|cur - prev|) / max(cur.max(), 1e-30)
// as a GPU reduction (PORT_PLAN.md 3.2: the convergence check is a reduction), so the loop reads back 8 bytes every
// `check` iterations instead of the whole field. Both maxima are of numbers >= 0, so atomicMax of their float32 bits
// is the largest whatever the order. |cur - prev| is float32 here and float64 in numpy; on a D8 tree the discharge
// stops changing exactly (a sum over a tree), so the decision is the same.
//! sampler cur              Q after this round of iterations
//! sampler prev             Q at the last test (or 0)
//! image   outC atomic_u32  [0]: the bits of max |cur - prev|; [1]: the bits of max cur (cleared before the dispatch)

fn kmain(p: vec2<i32>) {
  let n = cur_size();
  if (!inside(p, n)) { return; }
  let c = cur_at(p).x;
  atomicMax(&outC_b[0], bitcast<u32>(abs(c - prev_at(p).x)));
  atomicMax(&outC_b[1], bitcast<u32>(max(c, 0.0)));
}
