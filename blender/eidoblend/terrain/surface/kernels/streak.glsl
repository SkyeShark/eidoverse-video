/* streak: wind exposure trailed downwind (SURFACING_DESIGN.md 2.3, step 11). Each cell takes the exposure of the
   ground upwind of it along the wind's line, weighted exp(-distance / uLength): a convex, wind-facing spot leaves a
   tail uLength cells long and one cell wide (10 : 1 by default). The line is sampled every cell, bilinearly; indices
   clamp at the padded grid's edge. Twin: surface/twins.py streak. */
//! sampler exT             x: wind exposure on convex ground (crest's outX)
//! image   outS r32f
//! uniform vec2 uWind      the unit vector the wind blows toward
//! uniform float uLength   the tail's length, cells

float exposure(vec2 pos, ivec2 n) {
  vec2 fl = floor(pos);
  vec2 t = pos - fl;
  ivec2 i0 = clamp(ivec2(fl), ivec2(0), n - 1);
  ivec2 i1 = clamp(ivec2(fl) + 1, ivec2(0), n - 1);
  float v00 = texelFetch(exT, i0, 0).x;
  float v10 = texelFetch(exT, ivec2(i1.x, i0.y), 0).x;
  float v01 = texelFetch(exT, ivec2(i0.x, i1.y), 0).x;
  float v11 = texelFetch(exT, i1, 0).x;
  return mix(mix(v00, v10, t.x), mix(v01, v11, t.x), t.y);
}

void main() {
  ivec2 p = ivec2(gl_GlobalInvocationID.xy);
  ivec2 n = textureSize(exT, 0);
  if (!inside(p, n)) return;
  int R = min(int(ceil(3.0 * uLength)), 96);
  float acc = 0.0;
  float ws = 0.0;
  for (int t = 0; t <= R; t++) {
    float w = exp(-float(t) / uLength);
    acc += w * exposure(vec2(p) - float(t) * uWind, n);
    ws += w;
  }
  imageStore(outS, p, vec4(acc / ws, 0.0, 0.0, 0.0));
}
