// Port of blender/eidoblend/terrain/core/grid.py at f90c6fc: from_north_up / to_north_up (a[::-1]), the row flip
// between this package's frame (row 0 south) and top-down files (row 0 north). Exact.
//! sampler src
//! image   outF r32f

fn kmain(p: vec2<i32>) {
  let n = outF_size();
  if (!inside(p, n)) { return; }
  outF_store(p, src_at(vec2<i32>(p.x, n.y - 1 - p.y)));
}
