/* route_colour: one Jacobi pass of the routing of sediment and its colour down the drainage (SURFACING_DESIGN.md
   2.3, the palette bake). route_area's scheme with four channels: with P a cell's sediment production and c the
   colour of its bare rock,

       Q = P + sum over higher neighbours q of Q_q share(q -> c)          (what the cell carries)
       R = P c + sum over higher neighbours q of R_q share(q -> c)        (and its colour, premultiplied)

   on the filled, tilted surface (fill.glsl) with route_area's multiple-flow shares, to convergence. The colour the
   sediment carries is R / Q, upstream rock colours weighted by where the ground erodes. Held cells (pinT) keep their
   start value: on a child level the margin holds the parent's Q and R, so a catchment the window truncates still
   carries its upstream colour in. Twin: surface/twins.py route_colour. */
//! sampler st          x: the routing surface (m)
//! sampler wsumT       x: wsum of st.x (flow_weights)
//! sampler qT          the previous iterate: x: Q, yzw: R
//! sampler srcT        x: P, yzw: P x colour (linear)
//! sampler pinT        y: 1 where the cell holds its start value
//! image   outQ rgba32f
//! uniform float uDx   the cell, metres
//! uniform float uP    the flow exponent p
//! uniform int uBound

float wpow(float s, float e) { return e == 1.0 ? s : pow(s, e); }

void main() {
  ivec2 p = ivec2(gl_GlobalInvocationID.xy);
  ivec2 n = textureSize(st, 0);
  if (!inside(p, n)) return;
  vec4 Q = texelFetch(qT, p, 0);
  if (texelFetch(pinT, p, 0).y < 0.5) {
    float h = texelFetch(st, p, 0).x;
    Q = texelFetch(srcT, p, 0);
    for (int k = 0; k < 8; k++) {
      ivec2 q;
      if (!neighbour(p, k, n, uBound, q)) continue;
      float hq = texelFetch(st, q, 0).x;
      if (hq > h) {
        Q += texelFetch(qT, q, 0) * (wpow((hq - h) / (LEN[k] * uDx), uP) / max(texelFetch(wsumT, q, 0).x, 1e-30));
      }
    }
  }
  imageStore(outQ, p, Q);
}
