// Port of numpy code of blender/eidoblend/terrain/surface/atlas.py at d67f19e (sample_bilinear, sample_lattice), as
// a GPU kernel (the port's own, PORT_PLAN.md 3.2). bilinear: a texel-centred grid's four channels at an affine
// lattice of points, clamped to the grid's outermost centres. Output texel (i, j) reads the source at the texel
// coordinates (uMap.x + i uMap.y, uMap.z + j uMap.w): atlas.py's fi = clip((x - x0) / texel - 0.5, 0, m - 1) at
// x = (the output's x0) + (i + 0.5) (its texel), which the caller folds into uMap in doubles (exact when the two grids'
// origins and texels are binary fractions of each other, as nested levels' are). The taps i0 = min(floor(fi), m - 2)
// and i1 = min(i0 + 1, m - 1), the weight fi - i0, the rows blended first and then the two rows (sample_lattice's
// order; sample_bilinear's is the same).
//! sampler src
//! image   outB rgba32f
//! uniform vec4 uMap

fn kmain(p: vec2<i32>) {
  let n = outB_size();
  if (!inside(p, n)) { return; }
  let m = src_size();
  let fi = clamp(u.uMap.x + f32(p.x) * u.uMap.y, 0.0, f32(m.x) - 1.0);
  let fj = clamp(u.uMap.z + f32(p.y) * u.uMap.w, 0.0, f32(m.y) - 1.0);
  let i0 = min(i32(floor(fi)), max(m.x - 2, 0));
  let j0 = min(i32(floor(fj)), max(m.y - 2, 0));
  let ti = fi - f32(i0);
  let tj = fj - f32(j0);
  let i1 = min(i0 + 1, m.x - 1);
  let j1 = min(j0 + 1, m.y - 1);
  let top = src_at(vec2<i32>(i0, j0)) * (1.0 - ti) + src_at(vec2<i32>(i1, j0)) * ti;
  let bot = src_at(vec2<i32>(i0, j1)) * (1.0 - ti) + src_at(vec2<i32>(i1, j1)) * ti;
  outB_store(p, top * (1.0 - tj) + bot * tj);
}
