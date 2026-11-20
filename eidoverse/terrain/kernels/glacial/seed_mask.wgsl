// The port's own kernel: blender/eidoblend/terrain/solvers/glacial.py centrelines at f90c6fc,
//     f = min((max(Q, 0) / max(Q_ref, 1e-30))^0.4, f_max);  seeds = chan & (W_t f >= min_width_cells cell)
// numpy decides it in float64 from the float32 discharge. The decision rises with Q, so solvers/glacial.js finds,
// with numpy's own arithmetic in doubles, the smallest float32 discharge it holds for (uQmin), and the test here is
// Q >= uQmin: numpy's decision cell for cell.
//! sampler chan             chan_mask.wgsl's outC
//! sampler Q
//! image   outS r32ui       1 on a seed cell (the flags np.flatnonzero reads)
//! uniform float uQmin

fn kmain(p: vec2<i32>) {
  if (!inside(p, outS_size())) { return; }
  outS_store(p, select(0u, 1u, chan_at(p).x > 0.5 && Q_at(p).x >= u.uQmin));
}
