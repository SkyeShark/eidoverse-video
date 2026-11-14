/* pin_inflow: the source term that holds route_area's drainage area at a target on pinned cells (SURFACING_DESIGN.md
   2.3, step 8: "inflow is pinned from the parent across the border"). Twin: surface/twins.py pin_inflow.

   route_area iterates A = dx^2 + A_in + sum over higher neighbours q of A_q share(q -> c). For a pinned cell

       A_in = target - dx^2 - sum over higher pinned neighbours q of target_q share(q -> c)

   so at the fixed point every pinned cell whose higher neighbours are all pinned reads exactly its target, whatever
   the surface does there, and the free cells next to them receive the targets' flow by the surface's own shares. On
   a child level the pinned cells are the margin around its window and the target is the parent's specific catchment
   (its drainage area over its cell) times the child's cell: a river enters the window where the parent has it,
   carrying the parent's catchment. A free cell's A_in is 0. The shares are route_area's, term for term. */
//! sampler st          x: the routing surface (m)
//! sampler wsumT       x: wsum of st.x (flow_weights)
//! sampler tgtT        x: the target drainage area (m^2), y: 1 where the cell is pinned to it
//! image   outP r32f   x: A_in (m^2)
//! uniform float uDx   the cell, metres
//! uniform float uP    the flow exponent p
//! uniform int uBound

float wpow(float s, float e) { return e == 1.0 ? s : pow(s, e); }

void main() {
  ivec2 p = ivec2(gl_GlobalInvocationID.xy);
  ivec2 n = textureSize(st, 0);
  if (!inside(p, n)) return;
  vec4 tg = texelFetch(tgtT, p, 0);
  float a_in = 0.0;
  if (tg.y > 0.5) {
    float h = texelFetch(st, p, 0).x;
    float A = uDx * uDx;
    for (int k = 0; k < 8; k++) {
      ivec2 q;
      if (!neighbour(p, k, n, uBound, q)) continue;
      float hq = texelFetch(st, q, 0).x;
      vec4 tq = texelFetch(tgtT, q, 0);
      if (hq > h && tq.y > 0.5) {
        A += tq.x * wpow((hq - h) / (LEN[k] * uDx), uP) / max(texelFetch(wsumT, q, 0).x, 1e-30);
      }
    }
    a_in = tg.x - A;
  }
  imageStore(outP, p, vec4(a_in, 0.0, 0.0, 0.0));
}
