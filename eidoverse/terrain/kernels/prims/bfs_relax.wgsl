// bfs_relax: breadth-first steps by integer relaxation (PORT_PLAN.md 3.4): d = 0 at a seed, else 1 + the smallest
// d among the 8 neighbours it may be reached from, swept over 16 x 16 tiles in workgroup memory (lib.wgsl) until
// nothing changes; that fixed point is the breadth-first distance, whatever the order, and a cell no seed reaches
// keeps NONE. Exact (integers).
//
// uInit 1 starts the Blender edition's solvers/hydro.py flat_distance at f90c6fc: the seeds are where a flat
// drains (a strictly lower neighbour, a cell on an edge that does not wrap, a cell at or below the sea level), and
// with uSame 1 a step joins two cells of equal height only (its frontier's take = ~seen[c] & (w[c] == w[f])).
// uInit 2 starts from the nonzero cells of `seed` instead (with uSame 0: steps between any neighbours).
//! include prims/lib
//! sampler surf             the surface (channel 0): what a seed is (uInit 1) and which steps exist (uSame 1)
//! sampler seed r32ui       with uInit 2: nonzero cells are the seeds (a 1 x 1 dummy otherwise)
//! sampler din r32ui        the distances so far (not read by a start: bind any u32 field of the grid's size)
//! image   outD r32ui
//! image   changed atomic_u32  with uCount 1: element 0 gains the number of tiles this dispatch changed
//! uniform int uInit        1: flat_distance's seeds; 2: the seed field; 0: one sweep dispatch; 3: the end of
//                           flat_distance (a cell nothing reached is 0, as there)
//! uniform int uSame        1: steps only between cells of equal surface height
//! uniform int uWrapX
//! uniform int uWrapY
//! uniform int uSea         1: cells at or below uSeaLevel are seeds (uInit 1)
//! uniform float uSeaLevel  the largest float32 at or below the sea level
//! uniform int uCount

var<workgroup> ta: array<u32, 324>;
var<workgroup> tb: array<u32, 324>;
var<workgroup> ts: array<f32, 324>;
var<workgroup> tchanged: atomic<u32>;

fn flat_seed(p: vec2<i32>, n: vec2<i32>) -> bool {
  let w = surf_at(p).x;
  if (u.uWrapX == 0 && (p.x == 0 || p.x == n.x - 1)) { return true; }
  if (u.uWrapY == 0 && (p.y == 0 || p.y == n.y - 1)) { return true; }
  if (u.uSea != 0 && w <= u.uSeaLevel) { return true; }
  for (var k = 0; k < 8; k++) {
    var q: vec2<i32>;
    if (neighbour_w(p, k, n, u.uWrapX, u.uWrapY, &q) && w > surf_at(q).x) { return true; }
  }
  return false;
}

fn kmain(p: vec2<i32>) {
  let n = outD_size();
  if (u.uInit == 3) {
    if (inside(p, n)) {
      var d = din_at(p);
      if (d == NONE) { d = 0u; }
      outD_store(p, d);
    }
    return;
  }
  if (u.uInit != 0) {
    if (inside(p, n)) {
      var s = false;
      if (u.uInit == 1) { s = flat_seed(p, n); } else { s = seed_at(p) != 0u; }
      var d0 = NONE;
      if (s) { d0 = 0u; }
      outD_store(p, d0);
    }
    return;
  }
  let lid = tile_lid(p);
  let org = p - lid;
  for (var t = lid.y * 16 + lid.x; t < TSLOTS; t += 256) {
    let q = tile_cell(org, t, n, u.uWrapX, u.uWrapY);
    var d = NONE;
    var w = 0.0;
    if (q.x >= 0) {
      d = din_at(q);
      if (u.uSame != 0) { w = surf_at(q).x; }
    }
    ta[t] = d;
    tb[t] = d;
    ts[t] = w;
  }
  if (lid.x == 0 && lid.y == 0) { atomicStore(&tchanged, 0u); }
  workgroupBarrier();
  let me = tile_me(lid);
  let live = inside(p, n);
  let d0 = ta[me];
  let held = !live || d0 == 0u;
  let wc = ts[me];
  for (var s = 0; s < 8; s++) {
    if (!held) {
      var d = ta[me];
      for (var k = 0; k < 8; k++) {
        let dq = ta[me + TOFF[k]];
        if (dq != NONE && (u.uSame == 0 || ts[me + TOFF[k]] == wc)) { d = min(d, dq + 1u); }
      }
      tb[me] = d;
    }
    workgroupBarrier();
    if (!held) {
      var d = tb[me];
      for (var k = 0; k < 8; k++) {
        let dq = tb[me + TOFF[k]];
        if (dq != NONE && (u.uSame == 0 || ts[me + TOFF[k]] == wc)) { d = min(d, dq + 1u); }
      }
      ta[me] = d;
    }
    workgroupBarrier();
  }
  let d = ta[me];
  if (live) {
    outD_store(p, d);
    if (d != d0) { atomicOr(&tchanged, 1u); }
  }
  workgroupBarrier();
  if (u.uCount != 0 && lid.x == 0 && lid.y == 0 && atomicLoad(&tchanged) != 0u) { atomicAdd(&changed_b[0], 1u); }
}
