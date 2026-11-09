/* ice_flux (design section 4.5, step 1): one Jacobi iteration of the ice discharge on a fixed routing surface,
   iterated to convergence by solvers/glacial.py ice_flux_converge:

       Q_in = mb.y + the upstream neighbours' discharge: D8 (uD8 1) the whole Q of each neighbour whose receiver
              (wT.x, its k) is this cell; MFD (uD8 0) each higher neighbour's Q x s^p / wsum (route_area's weights)
       a    = b dx^2                                     b >= 0: accumulation over the cell
            = b dx L,  L = clamp(2 W(Q_in), dx, uLmax)   b < 0: ablation over the tongue's width,
                                                         W(Q) = uWref (Q / uQw)^uWexp
       Q    = max(Q_in + a, 0)                           the terminus is where it reaches 0

   A glacier ablates over its width, not over the one cell its discharge is routed through (with dx^2 a tongue ran
   about 30 times too far). With b = 1 everywhere this is the D8 drainage area (m^2). On a filled surface the
   iteration is a sum over a tree: it stops changing after the longest flow path. Twin: solvers/glacial.py
   ice_flux. */
//! sampler st          x: the routing surface (m): lake-filled, tilted across flats (solvers/hydro.py)
//! sampler wT          x: D8: each cell's receiver k (0..7; -1 none); MFD: wsum of st.x at exponent uP
//! sampler qT          x: Q, the previous iterate (m^3/yr)
//! sampler mb          x: the mass balance b (m/yr of ice), y: Q_in, ice entering from outside the window (m^3/yr)
//! image   outQ r32f   x: Q (m^3/yr)
//! uniform float uDx   the cell, metres
//! uniform float uP    the MFD exponent (uD8 0)
//! uniform float uWref the ablating half-width at uQw (m)
//! uniform float uQw   the discharge of that width (m^3/yr)
//! uniform float uWexp the width's exponent
//! uniform float uLmax the widest ablating tongue (m)
//! uniform int uD8     1: D8 receivers; 0: MFD weights
//! uniform int uBound  BOUND_OPEN / BOUND_PERIODIC / BOUND_PINNED (pinned reads neighbours as open)

float wpow(float s, float e) { return e == 1.0 ? s : pow(s, e); }

void main() {
  ivec2 p = ivec2(gl_GlobalInvocationID.xy);
  ivec2 n = textureSize(st, 0);
  if (!inside(p, n)) return;
  float h = texelFetch(st, p, 0).x;
  vec2 m = texelFetch(mb, p, 0).xy;
  float qin = m.y;
  for (int k = 0; k < 8; k++) {
    ivec2 q;
    if (!neighbour(p, k, n, uBound, q)) continue;
    if (uD8 == 1) {
      if (int(texelFetch(wT, q, 0).x) == 7 - k) qin += texelFetch(qT, q, 0).x;
    } else {
      float hq = texelFetch(st, q, 0).x;
      if (hq > h) {
        qin += texelFetch(qT, q, 0).x * (wpow((hq - h) / (LEN[k] * uDx), uP) / max(texelFetch(wT, q, 0).x, 1e-30));
      }
    }
  }
  float b = m.x;
  float L = clamp(2.0 * uWref * pow(max(qin, 0.0) / uQw, uWexp), uDx, max(uLmax, uDx));
  float a = b >= 0.0 ? b * uDx * uDx : b * uDx * L;
  imageStore(outQ, p, vec4(max(qin + a, 0.0), 0.0, 0.0, 0.0));
}
