// histogram: counts of an integer field's values (np.bincount in the Blender edition: label sizes, bins of a
// profile). A value at or above the number of bins is not counted. Integer atomics: exact, order-independent.
//! include prims/lib
//! sampler keys r32ui       the values
//! image   hist atomic_u32  one count per bin, row-major (cleared by the caller)
//! uniform int uCount       only the first uCount values in row-major order (a list's items)

fn kmain(p: vec2<i32>) {
  let n = keys_size();
  if (!inside(p, n) || p.y * n.x + p.x >= u.uCount) { return; }
  let nb = hist_size();
  let k = keys_at(p);
  if (k < u32(nb.x * nb.y)) { atomicAdd(&hist_b[k], 1u); }
}
