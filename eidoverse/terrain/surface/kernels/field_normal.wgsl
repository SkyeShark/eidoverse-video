// Port of blender/eidoblend/terrain/surface/kernels/field_normal.glsl at d67f19e.
//
// Transcribed statement for statement from the GLSL (PORT_PLAN.md 4.2, 3.5); the `//!` header is the GLSL's,
// unchanged. The changes are WGSL's: texelFetch is hT_at(q), imageStore is outG_store, textureSize is hT_size(), the
// uniform is u.uTexel.
/* field_normal: the height's gradient on the detail grid, by central differences at the texel spacing
   (SURFACING_DESIGN.md 2.3, step 2). The height is the level's own on a detail grid at the cell, and its Catmull-Rom
   x 2 (upsample2: the mesh's interpolant at quarter offsets) on one at half the cell, so on the cell grid this is
   masks.py's slope arithmetic. Indices clamp at the padded grid's edge. Twin: surface/twins.py field_normal. */
//! sampler hT              x: the height on the detail grid, metres (less the level's reference height)
//! image   outG rgba32f    x: h, y: dh/dx, z: dh/dy (metres per metre), w: the slope's tangent
//! uniform float uTexel    the detail grid's texel, metres

fn kmain(p: vec2<i32>) {
  let n = hT_size();
  if (!inside(p, n)) { return; }
  let h = hT_at(p).x;
  let e = hT_at(vec2<i32>(min(p.x + 1, n.x - 1), p.y)).x;
  let w = hT_at(vec2<i32>(max(p.x - 1, 0), p.y)).x;
  let no = hT_at(vec2<i32>(p.x, min(p.y + 1, n.y - 1))).x;
  let so = hT_at(vec2<i32>(p.x, max(p.y - 1, 0))).x;
  let k = 0.5 / u.uTexel;
  let hx = (e - w) * k;
  let hy = (no - so) * k;
  outG_store(p, vec4<f32>(h, hx, hy, sqrt(hx * hx + hy * hy)));
}
