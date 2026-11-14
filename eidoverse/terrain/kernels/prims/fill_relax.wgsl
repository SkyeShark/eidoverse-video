// fill_relax: depression filling by min-max relaxation (PORT_PLAN.md 3.4). The Blender edition's
// solvers/hydro.py fill_depressions at f90c6fc gives every cell its spill level by a priority flood over the graph
// of D8 basins: the lowest level a cell's water must reach to leave the map, which is the smallest, over all
// 8-connected paths from the cell to an outlet, of the highest ground on the path. That surface W is the one fixed
// point of
//     W = h at an outlet,    W = max(h, min(W, the 8 neighbours' W)) elsewhere,
// and this kernel sweeps it, from W = h at the outlets and the largest float elsewhere (uInit 1 writes that start).
// The update only lowers W and never below the fixed point, so any order of updates ends on it: this kernel sweeps
// each 16 x 16 tile 16 times per dispatch in workgroup memory (lib.wgsl's tiles), the halo held at the dispatch's
// input. Minimum and maximum only, so the fixed point is bit for bit numpy's float64 result for float32 heights.
// The sequential priority flood becomes a relaxation: that is the deviation the plan names (3.4); its oracle is
// fill_depressions itself.
//
// Outlets, as fill_depressions takes them: every cell on an edge that does not wrap (water leaves the map at the
// cell's own height), every cell at or below the sea level, and on a tile that wraps on both axes with no sea the
// lowest cell (np.argmin: its D8 basin is the outlet basin, and every cell of that basin descends to it).
//! include prims/lib
//! sampler h               the ground, metres (channel 0)
//! sampler win             W so far (with uInit 1 not read: bind h)
//! image   outW r32f
//! image   changed atomic_u32  with uCount 1: element 0 gains the number of tiles this dispatch changed
//! uniform int uInit       1: write the start
//! uniform int uWrapX      1: the columns wrap
//! uniform int uWrapY      1: the rows wrap
//! uniform int uSea        1: cells with h <= uSeaLevel are outlets
//! uniform float uSeaLevel the largest float32 at or below the sea level, so the float32 test is numpy's float64 one
//! uniform int uRoot       a row-major cell index that is an outlet (the lowest cell), -1 for none
//! uniform int uCount

var<workgroup> ta: array<f32, 324>;
var<workgroup> tb: array<f32, 324>;
var<workgroup> tchanged: atomic<u32>;

fn is_outlet(p: vec2<i32>, n: vec2<i32>, h: f32) -> bool {
  if (u.uWrapX == 0 && (p.x == 0 || p.x == n.x - 1)) { return true; }
  if (u.uWrapY == 0 && (p.y == 0 || p.y == n.y - 1)) { return true; }
  if (u.uSea != 0 && h <= u.uSeaLevel) { return true; }
  if (p.y * n.x + p.x == u.uRoot) { return true; }
  return false;
}

fn kmain(p: vec2<i32>) {
  let n = h_size();
  if (u.uInit != 0) {
    if (inside(p, n)) {
      let h0 = h_at(p).x;
      var w = BIG;
      if (is_outlet(p, n, h0)) { w = h0; }
      outW_store(p, vec4<f32>(w, 0.0, 0.0, 0.0));
    }
    return;
  }
  let lid = tile_lid(p);
  let org = p - lid;
  for (var t = lid.y * 16 + lid.x; t < TSLOTS; t += 256) {
    let q = tile_cell(org, t, n, u.uWrapX, u.uWrapY);
    var v = BIG;
    if (q.x >= 0) { v = win_at(q).x; }
    ta[t] = v;
    tb[t] = v;
  }
  if (lid.x == 0 && lid.y == 0) { atomicStore(&tchanged, 0u); }
  workgroupBarrier();
  let me = tile_me(lid);
  let live = inside(p, n);
  var hc = BIG;
  var held = true;
  if (live) {
    hc = h_at(p).x;
    held = is_outlet(p, n, hc);
  }
  let w0 = ta[me];
  for (var s = 0; s < 8; s++) {
    if (!held) {
      var m = ta[me];
      for (var k = 0; k < 8; k++) { m = min(m, ta[me + TOFF[k]]); }
      tb[me] = max(hc, m);
    }
    workgroupBarrier();
    if (!held) {
      var m = tb[me];
      for (var k = 0; k < 8; k++) { m = min(m, tb[me + TOFF[k]]); }
      ta[me] = max(hc, m);
    }
    workgroupBarrier();
  }
  let w = ta[me];
  if (live) {
    outW_store(p, vec4<f32>(w, 0.0, 0.0, 0.0));
    if (bitcast<u32>(w) != bitcast<u32>(w0)) { atomicOr(&tchanged, 1u); }
  }
  workgroupBarrier();
  if (u.uCount != 0 && lid.x == 0 && lid.y == 0 && atomicLoad(&tchanged) != 0u) { atomicAdd(&changed_b[0], 1u); }
}
