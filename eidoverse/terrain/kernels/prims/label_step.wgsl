// label_step: connected components by label propagation with pointer jumping (PORT_PLAN.md 3.4). The Blender
// edition's core/metrics.py label at f90c6fc hooks every component to its smallest root (np.minimum.at(parent, hi,
// lo), then parent = parent[parent]) until each cell's parent is its component's smallest row-major index. Here a
// cell of the mask takes the smallest label among itself and its 8 neighbours in the mask, swept 16 times over its
// 16 x 16 tile in workgroup memory (lib.wgsl), then follows that label to the label its owner held at the start of
// the dispatch (the jump). A label is always the index of a cell of the same component and never grows, so the
// dispatches end with every cell holding its component's smallest index, whatever the order: the root numpy's
// union-find ends on. Background cells hold NONE, which is never the minimum. Exact.
//! include prims/lib
//! sampler lab r32ui       the labels so far (NONE: background)
//! image   outL r32ui
//! image   changed atomic_u32  with uCount 1: element 0 gains the number of tiles this dispatch changed
//! uniform int uCount

var<workgroup> ta: array<u32, 324>;
var<workgroup> tb: array<u32, 324>;
var<workgroup> tchanged: atomic<u32>;

fn kmain(p: vec2<i32>) {
  let n = lab_size();
  let lid = tile_lid(p);
  let org = p - lid;
  for (var t = lid.y * 16 + lid.x; t < TSLOTS; t += 256) {
    let q = tile_cell(org, t, n, 0, 0);
    var v = NONE;
    if (q.x >= 0) { v = lab_at(q); }
    ta[t] = v;
    tb[t] = v;
  }
  if (lid.x == 0 && lid.y == 0) { atomicStore(&tchanged, 0u); }
  workgroupBarrier();
  let me = tile_me(lid);
  let live = inside(p, n);
  let l0 = ta[me];
  let held = !live || l0 == NONE;
  for (var s = 0; s < 8; s++) {
    if (!held) {
      var m = ta[me];
      for (var k = 0; k < 8; k++) { m = min(m, ta[me + TOFF[k]]); }
      tb[me] = m;
    }
    workgroupBarrier();
    if (!held) {
      var m = tb[me];
      for (var k = 0; k < 8; k++) { m = min(m, tb[me + TOFF[k]]); }
      ta[me] = m;
    }
    workgroupBarrier();
  }
  if (live) {
    var l = ta[me];
    if (l != NONE) { l = min(l, lab_b[l]); }
    outL_store(p, l);
    if (l != l0) { atomicOr(&tchanged, 1u); }
  }
  workgroupBarrier();
  if (u.uCount != 0 && lid.x == 0 && lid.y == 0 && atomicLoad(&tchanged) != 0u) { atomicAdd(&changed_b[0], 1u); }
}
