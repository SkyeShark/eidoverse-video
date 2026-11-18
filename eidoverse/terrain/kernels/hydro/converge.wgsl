// Port of the convergence test of blender/eidoblend/terrain/solvers/hydro.py route_to_convergence at f90c6fc:
//     change = max(|cur - prev| / maximum(cur, 1e-12))
// as a GPU reduction (PORT_PLAN.md 3.2, "the convergence check (a reduction)"), so the loop reads back 4 bytes
// every `check` iterations instead of the whole field. A relative change is >= 0 (or NaN, whose bits are larger
// than any number's, as numpy's max returns NaN), so atomicMax of its float32 bits is the largest whatever the
// order. numpy evaluates the ratio in float64 from the float32 fields; this is float32 (the stopping decision can
// differ only when the change lies within a rounding of the tolerance).
//! include prims/lib
//! sampler cur              A after this round of iterations
//! sampler prev             A at the last test (or the start)
//! image   outC atomic_u32  [0]: the bits of the largest relative change (cleared before the dispatch)

fn kmain(p: vec2<i32>) {
  let n = cur_size();
  if (!inside(p, n)) { return; }
  let c = cur_at(p).x;
  let d = abs(c - prev_at(p).x) / max(c, 1e-12);
  atomicMax(&outC_b[0], bitcast<u32>(d));
}
