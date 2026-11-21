// Port of blender/eidoblend/terrain/surface/kernels/upsample2.glsl at d67f19e.
//
// Transcribed statement for statement from the GLSL (PORT_PLAN.md 4.2, 3.5); the `//!` header is the GLSL's,
// unchanged. The changes are WGSL's: texelFetch is src_at(q), imageStore is outU_store, textureSize is src_size(),
// the uniforms are u.<name>, taps()'s `out` arguments are pointers, and `P >> 1` shifts by 1u.
/* upsample2: a window of a cell-centred grid at twice the resolution (child texels nest 2 x 2 in each source cell, at
   -0.25 and +0.25 of it), as core/grid.py's crop_upsample2: Catmull-Rom for heights (the interpolant the levels are
   upsampled with and the mesh's vertices are read by), bilinear for everything else, nearest for labels. The bake
   uses it for the detail grid's height (the whole padded level, x 2) and for everything a level takes from its
   parent (the parent's padded grid, cropped to the child's padded window). Source indices clamp at the source's
   edge. Twin: core/grid.py crop_upsample2. */
//! sampler src             the source grid, up to four fields
//! image   outU rgba32f    the window at twice the resolution
//! uniform ivec2 uOrigin   the source cell under the output's first two texels
//! uniform ivec2 uSize     the output's size, texels (columns, rows)
//! uniform int uKind       0: Catmull-Rom, 1: bilinear, 2: nearest

const CR25 = array<f32, 4>(-0.0703125, 0.8671875, 0.2265625, -0.0234375);

/* the four taps of one axis: cell indices c0 .. c0 + 3 and their weights, for the child texel `odd` of cell c */
fn taps(c: i32, odd: i32, c0: ptr<function, i32>, w: ptr<function, vec4<f32>>) {
  if (u.uKind == 0) {
    *c0 = c - 2 + odd;
    *w = select(vec4<f32>(CR25[3], CR25[2], CR25[1], CR25[0]), vec4<f32>(CR25[0], CR25[1], CR25[2], CR25[3]), odd == 1);
  } else if (u.uKind == 1) {
    *c0 = c - 2 + odd;
    *w = select(vec4<f32>(0.0, 0.25, 0.75, 0.0), vec4<f32>(0.0, 0.75, 0.25, 0.0), odd == 1);
  } else {
    *c0 = c - 2;
    *w = vec4<f32>(0.0, 0.0, 1.0, 0.0);
  }
}

fn kmain(P: vec2<i32>) {
  if (!inside(P, u.uSize)) { return; }
  let n = src_size();
  let c = u.uOrigin + (P >> vec2<u32>(1u));
  let odd = P & vec2<i32>(1);
  var cx0: i32;
  var cy0: i32;
  var wx: vec4<f32>;
  var wy: vec4<f32>;
  taps(c.x, odd.x, &cx0, &wx);
  taps(c.y, odd.y, &cy0, &wy);
  var acc = vec4<f32>(0.0);
  for (var j = 0; j < 4; j++) {
    if (wy[j] == 0.0) { continue; }
    let y = clamp(cy0 + j, 0, n.y - 1);
    var row = vec4<f32>(0.0);
    for (var i = 0; i < 4; i++) {
      if (wx[i] == 0.0) { continue; }
      row += wx[i] * src_at(vec2<i32>(clamp(cx0 + i, 0, n.x - 1), y));
    }
    acc += wy[j] * row;
  }
  outU_store(P, acc);
}
