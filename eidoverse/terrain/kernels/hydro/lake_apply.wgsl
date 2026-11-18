// Port of the cell updates of blender/eidoblend/terrain/solvers/hydro.py lakes at f90c6fc:
//     lake_cells = big[lab]
//     mode 'lake':      water = where(lake_cells, depth, 0);  fill_cells = (lab > 0) & ~lake_cells
//     mode 'sediment':  fill_cells = lab > 0
//     band > 0:         fill_cells &= edge_distance > seam_hold        (the seam's own cells stay the parent's)
//     add = where(fill_cells, depth, 0);  h = h + add;  deposit = deposit + add (or add without a deposit field)
// numpy adds in float64, where h + (filled - h) is the spill level exactly, so a filled cell gets `filled` itself;
// every other cell gets h + 0 (numpy's sum, which turns a -0 into +0). A filled cell's deposit is numpy's exact
// deposit + filled - h rounded once (hydro/lib sum3: filled - h alone is not a float32 value where the bed lies
// below half the spill level, near 0 m). solvers/hydro.js keeps h and deposit as they were when no cell fills
// (numpy's `if fill_cells.any()`), from the count. Exact.
//! include prims/lib
//! include hydro/lib
//! sampler h
//! sampler filled           the spill levels (fill_depressions)
//! sampler depth            filled - h
//! sampler lab r32ui        the depression labels
//! sampler big r32ui        per label: 1 for a lake (lake_big.wgsl)
//! sampler deposit          uDeposit 1: the deposit field; else a 1 x 1 stand-in
//! image   outH r32f        h with the fill cells raised to their spill level
//! image   outW r32f        the lake water: depth on lake cells (mode 'lake'), else 0
//! image   outDep r32f      deposit + add (add alone without a deposit field)
//! image   count atomic_u32 [0]: the fill cells
//! uniform int uLake        1: mode 'lake'; 0: 'sediment'
//! uniform int uBand        a child level's border band in cells (0: none)
//! uniform int uHold        seam_hold: cells this close to the edge never fill (with a band)
//! uniform int uDeposit

fn kmain(p: vec2<i32>) {
  let n = h_size();
  if (!inside(p, n)) { return; }
  let hv = h_at(p).x;
  let l = lab_at(p);
  let lake = l > 0u && big_b[l] != 0u;
  var water = 0.0;
  var fill = l > 0u;
  if (u.uLake != 0) {
    if (lake) { water = depth_at(p).x; }
    fill = l > 0u && !lake;
  }
  if (u.uBand > 0) {
    let e = min(min(p.x, n.x - 1 - p.x), min(p.y, n.y - 1 - p.y));
    fill = fill && e > u.uHold;
  }
  var add = 0.0;
  var hn = hv + 0.0;
  if (fill) {
    add = depth_at(p).x;
    hn = filled_at(p).x;
    atomicAdd(&count_b[0], 1u);
  }
  var dep = add;
  if (u.uDeposit != 0) {
    dep = deposit_at(p).x + 0.0;
    if (fill) { dep = sum3(deposit_at(p).x, filled_at(p).x, -hv); }
  }
  outH_store(p, vec4<f32>(hn, 0.0, 0.0, 0.0));
  outW_store(p, vec4<f32>(water, 0.0, 0.0, 0.0));
  outDep_store(p, vec4<f32>(dep, 0.0, 0.0, 0.0));
}
