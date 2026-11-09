/* route_incise (design section 4.1, pass 2): one step of uplift, stream-power incision and sediment deposition,
   with one Jacobi iteration of the drainage-area and sediment-flux routing (both lag the terrain by a step).

     A      = dx^2 + A_in + sum over higher neighbours q of A_q * share(q -> c)        drainage area, m^2
     qs_in  = qs_in(border) + sum over higher neighbours q of qs_q * share(q -> c)     sediment arriving, m^3/yr
     share(q -> c) = max(s_qc, 0)^p / wsum_q                                          (flow_weights)
     Dp     = G qs_in / A                                                              deposition, m/yr (Yuan 2019)
     E      = K A^m S^n, S toward the steepest receiver r (height h_r, distance d_r). uSlope 1 (the default)
              takes D-infinity's steepest facet (Tarboton 1997): the receiver is the point where the steepest
              direction crosses the facet's outer edge, between a side and a diagonal neighbour, so a channel
              running between the 8 grid directions erodes as fast as one along them (D8's slope, uSlope 0,
              underestimates it by up to 8 %, and the network combs along the grid)
   n = 1 is solved implicitly against the receiver's current height (Braun & Willett's update, one cell at a time):
     h' = (h + dt (U + Dp) + F h_r) / (1 + F),   F = dt K A^m / d_r
   which is stable for any dt and reaches the exact steady slope S = (U + Dp) / (K A^m) (the design's explicit form,
   clamped at the lowest neighbour, grades large rivers to U dt per cell instead). Other n: the explicit form,
   h' = max(h - dt E, h_low) + dt (U + Dp), h_low the lowest neighbour. A cell with no lower neighbour (a pit) does
   not incise. With uPitFill (the default) it fills like a lake filling with sediment: it is raised to uPitEps
   above its lowest neighbour, so a closed basin fills from its floor to its spill and joins the network (without
   it, a basin on a uniformly rising plateau rises with its rim and never spills: the first rolling hills kept
   undissected flats); the fill is recorded as deposit. Without uPitFill it rises with
   uplift and fills with the sediment it receives until it spills.
     qs_out = qs_in + (E_actual - Dp) dx^2          the flux the cell passes on (to its receivers, by the shares)
   The accumulators: deposition lays sediment; erosion removes loose material first (deposit, then talus, then any
   other loose cover), then rock (wear); mk.w is the loose thickness h - bed. Layered rock: when uColN > 0, K is multiplied by the column's K factor at the cell's stratigraphic
   height zs = h - zoff (a 1D texture of uColN texels from uColZ0 in steps of uColDz metres, linearly interpolated).
   In BOUND_PINNED mode the height is pulled to its pin (pin_apply), and the pull is ground added or taken like any
   other (pin_layers): added as deposit, taken loose first, then rock. The layers then always sum to the height's
   history (when only the solver's part was counted, a pit refilled under a pin every step piled hundreds of metres
   of "talus" and "deposit" into the border band). Twin: solvers/fluvial.py route_incise. */
//! sampler st          x: h (m), y: A (m^2), z: qs leaving the cell (m^3/yr), w: carried
//! sampler wsumT       x: wsum of st.x (flow_weights)
//! sampler par         x: U (m/yr), y: K (m^(1-2m)/yr), z: Sc (tangent; unused here), w: G (deposition)
//! sampler pin         x: pin_w (0..1), y: pin_h (m), z: A_in (m^2 entering from outside), w: qs_in (m^3/yr)
//! sampler mk          x: wear (m), y: deposit (m), z: talus (m), w: loose thickness h - bed (m)
//! sampler kcol        x: the layered-rock column's K factor per height step (1 row; a 1 x 1 dummy when unused)
//! sampler zoff        x: z - zs, the stratigraphic offset of the cell (m; dip and warp)
//! image   outS rgba32f
//! image   outM rgba32f
//! uniform float uDx   the cell, metres
//! uniform float uDt   the step, years
//! uniform float uM    the area exponent m
//! uniform float uN    the slope exponent n
//! uniform float uP    the flow exponent p
//! uniform float uColZ0
//! uniform float uColDz
//! uniform int uColN
//! uniform int uSlope  0: D8 steepest neighbour; 1: D-infinity steepest facet
//! uniform int uPitFill 1: a pit fills to just above its lowest neighbour
//! uniform float uPitEps metres a filled pit stands above its lowest neighbour
//! uniform int uBound

float wpow(float s, float e) { return e == 1.0 ? s : pow(s, e); }

/* the pin's change d of the height in the layers m (wear, deposit, talus, loose): d > 0 is deposit; d < 0 takes
   deposit, then talus, then other loose cover, then rock (wear) */
vec4 pin_layers(vec4 m, float d) {
  if (d >= 0.0) return vec4(m.x, m.y + d, m.z, m.w + d);
  float q = -d;
  float other = max(m.w - m.y - m.z, 0.0);
  float a = min(q, m.y);
  m.y -= a;
  q -= a;
  a = min(q, m.z);
  m.z -= a;
  q -= a;
  q -= min(q, other);
  m.w = max(m.w - (-d - q), 0.0);
  m.x += q;
  return m;
}

/* D-infinity's 8 facets: (side neighbour, diagonal neighbour) in common.glsl's k order */
const ivec2 FACET[8] = ivec2[8](ivec2(4, 7), ivec2(6, 7), ivec2(6, 5), ivec2(3, 5), ivec2(3, 0), ivec2(1, 0),
                                ivec2(1, 2), ivec2(4, 2));

void main() {
  ivec2 p = ivec2(gl_GlobalInvocationID.xy);
  ivec2 n = textureSize(st, 0);
  if (!inside(p, n)) return;
  vec4 c = texelFetch(st, p, 0);
  float h = c.x;
  vec4 pn = texelFetch(pin, p, 0);
  float A = uDx * uDx + pn.z;
  float qin = pn.w;
  float smax = 0.0;
  float dr = 1.0;
  float hr = h;
  float hlow = h;
  float hnb = 3.0e38;                                       // the lowest neighbour of any height
  for (int k = 0; k < 8; k++) {
    ivec2 q;
    if (!neighbour(p, k, n, uBound, q)) continue;
    vec4 cq = texelFetch(st, q, 0);
    hnb = min(hnb, cq.x);
    float d = LEN[k] * uDx;
    if (cq.x > h) {
      float share = wpow((cq.x - h) / d, uP) / max(texelFetch(wsumT, q, 0).x, 1e-30);
      A += cq.y * share;
      qin += cq.z * share;
    } else {
      float s = (h - cq.x) / d;
      if (s > smax) {
        smax = s;
        dr = d;
        hr = cq.x;
      }
      hlow = min(hlow, cq.x);
    }
  }
  if (uSlope == 1) {
    smax = 0.0;
    for (int f = 0; f < 8; f++) {
      ivec2 q1, q2;
      if (!neighbour(p, FACET[f].x, n, uBound, q1) || !neighbour(p, FACET[f].y, n, uBound, q2)) continue;
      float e1 = texelFetch(st, q1, 0).x;
      float e2 = texelFetch(st, q2, 0).x;
      float s1 = (h - e1) / uDx;
      float s2 = (e1 - e2) / uDx;
      float s, rh, rd;
      if (s2 < 0.0) {                                       // the steepest way leaves along the side
        s = s1;
        rh = e1;
        rd = uDx;
      } else if (s2 > s1) {                                 // ... along the diagonal
        s = (h - e2) / (1.41421356 * uDx);
        rh = e2;
        rd = 1.41421356 * uDx;
      } else {                                              // ... through the facet, crossing its outer edge
        float t = s1 > 0.0 ? s2 / s1 : 0.0;
        s = sqrt(s1 * s1 + s2 * s2);
        rh = e1 - t * s2 * uDx;
        rd = uDx * sqrt(1.0 + t * t);
      }
      if (s > smax) {
        smax = s;
        hr = rh;
        dr = rd;
      }
    }
  }
  vec4 pr = texelFetch(par, p, 0);
  float K = pr.y;
  if (uColN > 0) {
    float t = clamp((h - texelFetch(zoff, p, 0).x - uColZ0) / uColDz, 0.0, float(uColN - 1));
    int i0 = int(floor(t));
    int i1 = min(i0 + 1, uColN - 1);
    K *= mix(texelFetch(kcol, ivec2(i0, 0), 0).x, texelFetch(kcol, ivec2(i1, 0), 0).x, t - float(i0));
  }
  float Am = pow(A, uM);
  float Dp = pr.w * qin / A;
  float rise = uDt * (pr.x + Dp);
  float hn;
  if (smax > 0.0) {
    if (uN == 1.0) {
      float F = uDt * K * Am / dr;
      hn = (h + rise + F * hr) / (1.0 + F);
    } else {
      hn = max(h - uDt * K * Am * pow(smax, uN), hlow) + rise;
    }
  } else {
    hn = h + rise;
  }
  float fill = 0.0;
  if (smax <= 0.0 && uPitFill == 1 && hnb < 3.0e38) {
    fill = max(hnb + uPitEps - hn, 0.0);
    hn += fill;
  }
  float e = max(h + rise - hn, 0.0);                       // metres removed this step
  float qout = max(qin + (e / uDt - Dp) * uDx * uDx, 0.0);
  vec4 m = texelFetch(mk, p, 0);
  float dep = m.y + uDt * Dp + fill;
  float tal = m.z;
  float loose = m.w + uDt * Dp + fill;
  float other = max(loose - dep - tal, 0.0);               // loose material that is neither (scoria, regolith)
  float r = e;
  float a = min(r, dep);
  dep -= a;
  r -= a;
  a = min(r, tal);
  tal -= a;
  r -= a;
  r -= min(r, other);
  vec4 mo = vec4(m.x + r, dep, tal, max(loose - e, 0.0));
  if (uBound == BOUND_PINNED) {
    float hp = pin_apply(hn, pn.x, pn.y);
    mo = pin_layers(mo, hp - hn);
    hn = hp;
  }
  imageStore(outS, p, vec4(hn, A, qout, c.w));
  imageStore(outM, p, mo);
}
