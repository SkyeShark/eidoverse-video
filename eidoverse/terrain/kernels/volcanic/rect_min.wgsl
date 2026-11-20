// The minimum of a field over a rectangle, per row block: piles_on's `out[sl0].min()` (blender/eidoblend/terrain/
// solvers/volcanic.py at f90c6fc), taken over the support slices of each row block that stamp_add evaluates (its
// _evaluate_grid blocks of uBlockRows rows: numpy runs piles_on once per block). The port's own kernel: an exact
// minimum (atomicMin on float keys in numpy's order, prims/lib fkey); solvers/volcanic.js reads the keys back.
//! include prims/lib
//! sampler src r32f
//! image   mins atomic_u32   one key per block (start from NONE)
//! uniform ivec4 uRect       columns [x, z), rows [y, w)
//! uniform int uBlockRows

fn kmain(p: vec2<i32>) {
  let q = p + u.uRect.xy;
  if (q.x >= u.uRect.z || q.y >= u.uRect.w) { return; }
  let v = src_at(q).x;
  atomicMin(&mins_b[q.y / u.uBlockRows], fkey(v));
}
