// plants/discs: plants.py _discs (blender/eidoblend/terrain/build/plants.py at f9fba8c): the placed tree crowns on a
// level's cover raster (texel k spanning [k, k + 1)). uMode 0, per crown: one smaller than 0.75 texel adds its area to
// the texel holding its centre (an integer sum in 2^-20 texel^2: exact in any order, where np.bincount sums floats in
// the crowns' order); a larger one stamps clip(r - d + 0.5, 0, 1) over its box, the largest per texel (atomicMax on
// the float's bits: non-negative). uMode 1, per texel: max(1 - exp(-area), stamp), clipped to 0..1.
//! sampler crowns r32f   per crown 4 numbers: centre x, y and radius in texels, 0
//! image   area atomic_u32  per texel: the small crowns' area, 2^-20 texel^2
//! image   stamp atomic_u32 per texel: the large crowns' stamp (float bits)
//! image   outC r32f        per texel: the canopy (uMode 1)
//! uniform int uMode
//! uniform int uCount    the crowns (uMode 0)
//! uniform int uNx
//! uniform int uNy

fn kmain(p: vec2<i32>) {
  if (u.uMode == 1) {
    if (p.x >= u.uNx || p.y >= u.uNy) { return; }
    let t = p.y * u.uNx + p.x;
    let a = f32(atomicLoad(&area_b[t])) * 0x1p-20f;
    let s = bitcast<f32>(atomicLoad(&stamp_b[t]));
    outC_b[t] = clamp(max(1.0 - exp(-a), s), 0.0, 1.0);
    return;
  }
  let q = p.y * 4096 + p.x;
  if (q >= u.uCount) { return; }
  let cx = crowns_b[4 * q];
  let cy = crowns_b[4 * q + 1];
  let r = crowns_b[4 * q + 2];
  let nx = f32(u.uNx);
  let ny = f32(u.uNy);
  if (!(cx > -r && cx < nx + r && cy > -r && cy < ny + r)) { return; }
  if (r < 0.75) {
    if (cx >= 0.0 && cx < nx && cy >= 0.0 && cy < ny) {
      let i = clamp(i32(floor(cx)), 0, u.uNx - 1);
      let j = clamp(i32(floor(cy)), 0, u.uNy - 1);
      atomicAdd(&area_b[j * u.uNx + i], u32(round(3.14159265358979 * r * r * 1048576.0)));
    }
    return;
  }
  let i0 = max(i32(floor(cx - r - 1.0)), 0);
  let i1 = min(i32(ceil(cx + r + 1.0)), u.uNx);
  let j0 = max(i32(floor(cy - r - 1.0)), 0);
  let j1 = min(i32(ceil(cy + r + 1.0)), u.uNy);
  for (var j = j0; j < j1; j++) {
    for (var i = i0; i < i1; i++) {
      let dx = f32(i) + 0.5 - cx;
      let dy = f32(j) + 0.5 - cy;
      let v = clamp(r - sqrt(dx * dx + dy * dy) + 0.5, 0.0, 1.0);
      if (v > 0.0) { atomicMax(&stamp_b[j * u.uNx + i], bitcast<u32>(v)); }
    }
  }
}
