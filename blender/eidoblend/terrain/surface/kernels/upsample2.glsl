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

const float CR25[4] = float[4](-0.0703125, 0.8671875, 0.2265625, -0.0234375);

/* the four taps of one axis: cell indices c0 .. c0 + 3 and their weights, for the child texel `odd` of cell c */
void taps(int c, int odd, out int c0, out vec4 w) {
  if (uKind == 0) {
    c0 = c - 2 + odd;
    w = odd == 1 ? vec4(CR25[0], CR25[1], CR25[2], CR25[3]) : vec4(CR25[3], CR25[2], CR25[1], CR25[0]);
  } else if (uKind == 1) {
    c0 = c - 2 + odd;
    w = odd == 1 ? vec4(0.0, 0.75, 0.25, 0.0) : vec4(0.0, 0.25, 0.75, 0.0);
  } else {
    c0 = c - 2;
    w = vec4(0.0, 0.0, 1.0, 0.0);
  }
}

void main() {
  ivec2 P = ivec2(gl_GlobalInvocationID.xy);
  if (!inside(P, uSize)) return;
  ivec2 n = textureSize(src, 0);
  ivec2 c = uOrigin + (P >> 1);
  ivec2 odd = P & 1;
  int cx0, cy0;
  vec4 wx, wy;
  taps(c.x, odd.x, cx0, wx);
  taps(c.y, odd.y, cy0, wy);
  vec4 acc = vec4(0.0);
  for (int j = 0; j < 4; j++) {
    if (wy[j] == 0.0) continue;
    int y = clamp(cy0 + j, 0, n.y - 1);
    vec4 row = vec4(0.0);
    for (int i = 0; i < 4; i++) {
      if (wx[i] == 0.0) continue;
      row += wx[i] * texelFetch(src, ivec2(clamp(cx0 + i, 0, n.x - 1), y), 0);
    }
    acc += wy[j] * row;
  }
  imageStore(outU, P, acc);
}
