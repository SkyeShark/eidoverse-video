// Port of blender/eidoblend/terrain/masks.py at f90c6fc: the np.meshgrid(X, Y) compute hands a strata warp, as two
// GPU fields (the cells' world x and y: float32 of numpy's float64 centres, per column and row from masks.js).
//! sampler colT          per column: x
//! sampler rowT          per row: y
//! image   outX r32f
//! image   outY r32f

fn kmain(p: vec2<i32>) {
  let n = outX_size();
  if (!inside(p, n)) { return; }
  outX_store(p, vec4<f32>(colT_at(vec2<i32>(p.x, 0)).x, 0.0, 0.0, 0.0));
  outY_store(p, vec4<f32>(rowT_at(vec2<i32>(p.y, 0)).x, 0.0, 0.0, 0.0));
}
