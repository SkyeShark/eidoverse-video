// Port of numpy code of blender/eidoblend/terrain/surface/__init__.py (SurfaceData.tile, _gutter) and atlas.py
// (sample_lattice) at d67f19e, as a GPU kernel (the port's own, PORT_PLAN.md 3.2). tile: one map of a level's tile
// (size = n + 2 g texels a side) in physical values, filled in passes:
//   uMode 0  the data region: texel (g + i, g + j) is src's (i, j) (src: the level's own map on its n texels)
//   uMode 1  every gutter texel from src, a coarser level's map: bilinear at the texel centre's world point,
//            clamped to src's outermost centres (sample_lattice): the coarsest level the gutter reads, everywhere
//   uMode 2  the gutter texels inside src's window (its world bounds, inclusive): a finer level over the last
//   uMode 3  the constant uWin.x over the data region (uWin.y 0) or the gutter (uWin.y 1): a map a level lacks
//            (_channel_array's and _gutter's NEUTRAL fill)
// so a gutter texel ends with the finest level (by index) whose window holds it, as _gutter's finest-first search.
// uMap: src's texel coordinate of tile texel (i, j) is (uMap.x + i uMap.y, uMap.z + j uMap.w); uWin: src's window in
// the tile's texel indices (i_lo, j_lo, i_hi, j_hi; texel i inside when i_lo <= i <= i_hi). Both are folded in
// doubles by the caller: exact for nested levels, whose origins and texels are binary fractions of each other.
//! sampler src
//! image   outT r32f
//! uniform int uMode
//! uniform int uG
//! uniform int uN
//! uniform vec4 uMap
//! uniform vec4 uWin

fn kmain(p: vec2<i32>) {
  let n = outT_size();
  if (!inside(p, n)) { return; }
  let data = p.x >= u.uG && p.y >= u.uG && p.x < u.uG + u.uN && p.y < u.uG + u.uN;
  if (u.uMode == 3) {
    if (data == (u.uWin.y < 0.5)) { outT_store(p, vec4<f32>(u.uWin.x, 0.0, 0.0, 0.0)); }
    return;
  }
  if (u.uMode == 0) {
    if (data) { outT_store(p, vec4<f32>(src_at(p - vec2<i32>(u.uG, u.uG)).x, 0.0, 0.0, 0.0)); }
    return;
  }
  if (data) { return; }
  if (u.uMode == 2) {
    let q = vec2<f32>(p);
    if (q.x < u.uWin.x || q.y < u.uWin.y || q.x > u.uWin.z || q.y > u.uWin.w) { return; }
  }
  let m = src_size();
  let fi = clamp(u.uMap.x + f32(p.x) * u.uMap.y, 0.0, f32(m.x) - 1.0);
  let fj = clamp(u.uMap.z + f32(p.y) * u.uMap.w, 0.0, f32(m.y) - 1.0);
  let i0 = min(i32(floor(fi)), max(m.x - 2, 0));
  let j0 = min(i32(floor(fj)), max(m.y - 2, 0));
  let ti = fi - f32(i0);
  let tj = fj - f32(j0);
  let i1 = min(i0 + 1, m.x - 1);
  let j1 = min(j0 + 1, m.y - 1);
  let top = src_at(vec2<i32>(i0, j0)).x * (1.0 - ti) + src_at(vec2<i32>(i1, j0)).x * ti;
  let bot = src_at(vec2<i32>(i0, j1)).x * (1.0 - ti) + src_at(vec2<i32>(i1, j1)).x * ti;
  outT_store(p, vec4<f32>(top * (1.0 - tj) + bot * tj, 0.0, 0.0, 0.0));
}
