// The port's own kernel: the walk of blender/eidoblend/terrain/solvers/glacial.py cirques at f90c6fc up each glacier
// head's hollow (`for _ in range(int(3 Ra / cell)): u = up[c]; if u < 0: break; c = u`, then z_crest = h[c]), for
// every candidate head at once: the cells after 0, 1, .., uK steps (the last one repeated once the walk ends) and
// their heights. The cirque plan itself (its draws, its order, its spacing test) stays in solvers/glacial.js, which
// reads the entry its own Ra gives (PORT_PLAN.md 2.4: the plans over objects stay JavaScript).
//! sampler heads r32i       per head: its cell's row-major index
//! sampler up r32i          per cell: its best donor (glacial/best_donor.wgsl), -1 none
//! sampler h
//! image   outC r32i        per head and step: the cell, (uK + 1) entries a head
//! image   outZ r32f        per head and step: its height
//! uniform int uK           the most steps any head walks
//! uniform int uCount       the heads

fn kmain(p: vec2<i32>) {
  let w = heads_size().x;
  let t = p.y * w + p.x;
  if (p.x >= w || t >= u.uCount) { return; }
  var c = heads_b[t];
  let base = t * (u.uK + 1);
  for (var k = 0; k <= u.uK; k++) {
    outC_b[base + k] = c;
    outZ_b[base + k] = h_b[c];
    let nx = up_b[c];
    if (nx >= 0) { c = nx; }
  }
}
