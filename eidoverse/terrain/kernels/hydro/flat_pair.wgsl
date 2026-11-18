// Port of blender/eidoblend/terrain/solvers/hydro.py flat_distance at f90c6fc for a surface numpy holds in float64
// that is not float32 everywhere, held exactly as float32 pairs (hydro/lib): breadth-first steps (8-connected) across
// every flat from where it drains. The same integer relaxation as core/prims.js flatDistance (prims/bfs_relax.wgsl):
// d = 0 at a seed (a strictly lower neighbour, an edge, the sea), else 1 + the smallest d among its equal
// neighbours; its fixed point is the breadth-first distance; a cell no seed reaches is 0 at the end, as numpy's.
// Equal means equal pairs: numpy's float64 equality. One step per dispatch (its pair form for the few levels that
// carry lake water); the level runner's grids never wrap.
//! include prims/lib
//! include hydro/lib
//! sampler surf rg32f       the surface, (hi, lo)
//! sampler din r32ui        the distances so far (uInit 1: not read; bind any u32 field of the grid's size)
//! image   outD r32ui
//! image   changed atomic_u32  with uCount 1: element 0 gains the number of cells this dispatch changed
//! uniform int uInit        1: the seeds; 0: one step; 3: the end (a cell nothing reached is 0)
//! uniform int uSea         1: cells at or below the sea level are seeds
//! uniform vec2 uSea2       the sea level as a pair
//! uniform int uCount

fn is_seed(p: vec2<i32>, n: vec2<i32>, w: vec2<f32>) -> bool {
  if (on_edge(p, n)) { return true; }
  if (u.uSea != 0 && !p_less(u.uSea2, w)) { return true; }
  for (var k = 0; k < 8; k++) {
    let q = p + OFF[k];
    if (inside(q, n) && p_less(surf_at(q).xy, w)) { return true; }
  }
  return false;
}

fn kmain(p: vec2<i32>) {
  let n = surf_size();
  if (!inside(p, n)) { return; }
  if (u.uInit == 1) {
    var d = NONE;
    if (is_seed(p, n, surf_at(p).xy)) { d = 0u; }
    outD_store(p, d);
    return;
  }
  let d0 = din_at(p);
  if (u.uInit == 3) {
    var d = d0;
    if (d == NONE) { d = 0u; }
    outD_store(p, d);
    return;
  }
  var d = d0;
  if (d != 0u) {
    let w = surf_at(p).xy;
    for (var k = 0; k < 8; k++) {
      let q = p + OFF[k];
      if (!inside(q, n) || !p_equal(surf_at(q).xy, w)) { continue; }
      let dq = din_at(q);
      if (dq != NONE && dq + 1u < d) { d = dq + 1u; }
    }
  }
  outD_store(p, d);
  if (u.uCount != 0 && d != d0) { atomicAdd(&changed_b[0], 1u); }
}
