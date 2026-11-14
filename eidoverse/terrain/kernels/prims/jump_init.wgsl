// jump_init: receivers as pointers for pointer jumping (the Blender edition's solvers/hydro.py path_steps and
// _terminal_of at f90c6fc): ptr = where(rec >= 0, rec, own index); d = 1 where the cell has a receiver, else 0.
//! include prims/lib
//! sampler rec r32i      every cell's receiver as a row-major index, -1 for none (an outlet, a pit)
//! image   outP r32ui    the pointer: the receiver, or the cell itself
//! image   outD r32ui    1 with a receiver, 0 without

fn kmain(p: vec2<i32>) {
  let n = rec_size();
  if (!inside(p, n)) { return; }
  let i = p.y * n.x + p.x;
  let r = rec_at(p);
  if (r >= 0) {
    outP_store(p, u32(r));
    outD_store(p, 1u);
  } else {
    outP_store(p, u32(i));
    outD_store(p, 0u);
  }
}
