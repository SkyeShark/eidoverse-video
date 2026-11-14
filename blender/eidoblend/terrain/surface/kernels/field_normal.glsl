/* field_normal: the height's gradient on the detail grid, by central differences at the texel spacing
   (SURFACING_DESIGN.md 2.3, step 2). The height is the level's own on a detail grid at the cell, and its Catmull-Rom
   x 2 (upsample2: the mesh's interpolant at quarter offsets) on one at half the cell, so on the cell grid this is
   masks.py's slope arithmetic. Indices clamp at the padded grid's edge. Twin: surface/twins.py field_normal. */
//! sampler hT              x: the height on the detail grid, metres (less the level's reference height)
//! image   outG rgba32f    x: h, y: dh/dx, z: dh/dy (metres per metre), w: the slope's tangent
//! uniform float uTexel    the detail grid's texel, metres

void main() {
  ivec2 p = ivec2(gl_GlobalInvocationID.xy);
  ivec2 n = textureSize(hT, 0);
  if (!inside(p, n)) return;
  float h = texelFetch(hT, p, 0).x;
  float e = texelFetch(hT, ivec2(min(p.x + 1, n.x - 1), p.y), 0).x;
  float w = texelFetch(hT, ivec2(max(p.x - 1, 0), p.y), 0).x;
  float no = texelFetch(hT, ivec2(p.x, min(p.y + 1, n.y - 1)), 0).x;
  float so = texelFetch(hT, ivec2(p.x, max(p.y - 1, 0)), 0).x;
  float k = 0.5 / uTexel;
  float hx = (e - w) * k;
  float hy = (no - so) * k;
  imageStore(outG, p, vec4(h, hx, hy, sqrt(hx * hx + hy * hy)));
}
