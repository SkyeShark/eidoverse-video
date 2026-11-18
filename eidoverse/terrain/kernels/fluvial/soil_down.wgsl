// The port's own kernel (no Blender counterpart): one pass of blender/eidoblend/terrain/solvers/hillslope.py
// _downstream at f90c6fc (the channel mask grown down the receiver paths until every cell downstream of a channel
// cell is channel too). numpy's pass marks every masked cell's receiver; here, as a gather, a cell takes bit 0 when a
// neighbour whose receiver it is has it. Iterated to the fixed point (solvers/hillslope.js downstream): the same mask.
//! sampler bits r32ui    bit 0: chan (grown), bit 1: core, bit 2: lake
//! sampler rec r32i      hydro.flow_receivers: row-major receiver index, -1 none
//! image   outB r32ui
//! image   changed atomic_u32
//! uniform int uCount    1: count the cells that changed (the chunk's last pass)

fn kmain(p: vec2<i32>) {
  let n = outB_size();
  if (!inside(p, n)) { return; }
  let b = bits_at(p);
  if ((b & 1u) != 0u) {
    outB_store(p, b);
    return;
  }
  let me = p.y * n.x + p.x;
  var hit = false;
  for (var k = 0; k < 8; k++) {
    let q = p + OFF[k];
    if (!inside(q, n)) { continue; }
    if (rec_at(q) == me && (bits_at(q) & 1u) != 0u) { hit = true; }
  }
  if (hit) {
    outB_store(p, b | 1u);
    if (u.uCount == 1) { atomicAdd(&changed_b[0], 1u); }
  } else {
    outB_store(p, b);
  }
}
