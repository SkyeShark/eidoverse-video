// preview_rgb: the main level's hillshade as an RGB image with the hero windows outlined, api.py Terrain.preview
// (blender/eidoblend/terrain at f90c6fc): rgb = repeat(grey, 3); every finer level's window drawn as a one-cell
// outline (rows j0 and j1 over columns i0 .. i1, columns i0 and i1 over rows j0 .. j1) in one colour; then the rows
// flipped, so the PNG is north up. Integers only: exact.
//! sampler grey r32ui    the hillshade's 0..255 samples, n x n, row 0 south
//! sampler rects r32i    four numbers a window: i0, j0, i1, j1 (cells of this level)
//! image   outC r32ui    the image's samples, n rows of 3 n (r, g, b a cell), row 0 north
//! uniform int uRects    the windows
//! uniform ivec4 uColour the outline's r, g, b

fn kmain(p: vec2<i32>) {
  let n = grey_size();
  if (!inside(p, n)) { return; }
  let g = grey_b[p.y * n.x + p.x];
  var c = vec3<u32>(g, g, g);
  for (var k = 0; k < u.uRects; k++) {
    let i0 = rects_b[4 * k];
    let j0 = rects_b[4 * k + 1];
    let i1 = rects_b[4 * k + 2];
    let j1 = rects_b[4 * k + 3];
    let onRow = (p.y == j0 || p.y == j1) && p.x >= i0 && p.x <= i1;
    let onCol = (p.x == i0 || p.x == i1) && p.y >= j0 && p.y <= j1;
    if (onRow || onCol) { c = vec3<u32>(u32(u.uColour.x), u32(u.uColour.y), u32(u.uColour.z)); }
  }
  let o = (n.y - 1 - p.y) * 3 * n.x + 3 * p.x;
  outC_b[o] = c.x;
  outC_b[o + 1] = c.y;
  outC_b[o + 2] = c.z;
}
