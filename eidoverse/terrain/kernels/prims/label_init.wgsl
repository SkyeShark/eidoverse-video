// label_init: connected components, the start (the Blender edition's core/metrics.py label at f90c6fc: 8-connected
// components of a mask by union-find, hooking to the smaller root): every cell of the mask is its own component,
// named by its row-major index; the background is NONE.
//! include prims/lib
//! sampler mask r32ui    not zero: the cell is in the mask
//! image   outL r32ui

fn kmain(p: vec2<i32>) {
  let n = mask_size();
  if (!inside(p, n)) { return; }
  var l = NONE;
  if (mask_at(p) != 0u) { l = u32(p.y * n.x + p.x); }
  outL_store(p, l);
}
