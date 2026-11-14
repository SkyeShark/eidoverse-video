// Port of blender/eidoblend/terrain/core/grid.py at f90c6fc: sample_bilinear at the cell centres of a window (plus a
// displacement), the GPU form compose.shape's 'array' kind and the solvers' resampling take: the bilinear value of a
// cell-centred source grid at world (x, y), clamped to its outermost cell centres, in sample_bilinear's arithmetic.
// The sample point is computed relative to the source's origin, (x0 - src_x0) in JavaScript doubles then float32,
// plus (i + 0.5) cell and the displacement, so float32 keeps a fraction of a millimetre at any world offset.
//! sampler src              the source grid (its first channel), row 0 south
//! sampler disp             rg32f: each sample point's displacement in metres (x, y), read when uDisp is 1
//! image   outF r32f        one value per cell of the target window
//! uniform int uDisp
//! uniform vec2 uOrigin     the target window's (x0, y0) minus the source's (x0, y0), metres
//! uniform float uCell      the target window's cell, metres
//! uniform float uSrcCell   the source's cell, metres

fn kmain(p: vec2<i32>) {
  if (!inside(p, outF_size())) { return; }
  let n = src_size();
  var pos = u.uOrigin + (vec2<f32>(p) + 0.5) * u.uCell;
  if (u.uDisp != 0) { pos = pos + disp_at(p).xy; }
  let fi = clamp(pos.x / u.uSrcCell - 0.5, 0.0, f32(n.x) - 1.0);
  let fj = clamp(pos.y / u.uSrcCell - 0.5, 0.0, f32(n.y) - 1.0);
  let i0 = min(i32(floor(fi)), max(n.x - 2, 0));
  let j0 = min(i32(floor(fj)), max(n.y - 2, 0));
  let ti = fi - f32(i0);
  let tj = fj - f32(j0);
  let i1 = min(i0 + 1, n.x - 1);
  let j1 = min(j0 + 1, n.y - 1);
  let a00 = src_at(vec2<i32>(i0, j0)).x;
  let a10 = src_at(vec2<i32>(i1, j0)).x;
  let a01 = src_at(vec2<i32>(i0, j1)).x;
  let a11 = src_at(vec2<i32>(i1, j1)).x;
  let v = (a00 * (1.0 - ti) + a10 * ti) * (1.0 - tj) + (a01 * (1.0 - ti) + a11 * ti) * tj;
  outF_store(p, vec4<f32>(v, 0.0, 0.0, 0.0));
}
