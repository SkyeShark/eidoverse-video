// Port of blender/eidoblend/terrain/kernels/route_incise.glsl at f90c6fc.
//
// Transcribed statement for statement from the GLSL (PORT_PLAN.md 4.2), starting from the design probe's
// transcription (tests/design_probes/wgsl/route_incise.wgsl); the `//!` header is the GLSL's, unchanged. The changes
// are WGSL's: texelFetch(x, q, 0) is x_at(q), imageStore is outS_store / outM_store, textureSize is st_size(), a
// uniform uX is u.uX, neighbour()'s `out` argument is a pointer, the ?: of the facet's t is an if, and the column's
// mix(a, b, f) is written a (1 - f) + b f, as the numpy twin (solvers/fluvial.py route_incise) computes it, which is
// the oracle both kernels are held to (common.wgsl says why for pin_apply).
//
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

fn wpow(s: f32, e: f32) -> f32 { if (e == 1.0) { return s; } return pow(s, e); }

/* the pin's change d of the height in the layers m (wear, deposit, talus, loose): d > 0 is deposit; d < 0 takes
   deposit, then talus, then other loose cover, then rock (wear) */
fn pin_layers(m0: vec4<f32>, d: f32) -> vec4<f32> {
  var m = m0;
  if (d >= 0.0) { return vec4<f32>(m.x, m.y + d, m.z, m.w + d); }
  var q = -d;
  let other = max(m.w - m.y - m.z, 0.0);
  var a = min(q, m.y);
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
const FACET = array<vec2<i32>, 8>(vec2<i32>(4, 7), vec2<i32>(6, 7), vec2<i32>(6, 5), vec2<i32>(3, 5), vec2<i32>(3, 0),
                                  vec2<i32>(1, 0), vec2<i32>(1, 2), vec2<i32>(4, 2));

fn kmain(p: vec2<i32>) {
  let n = st_size();
  if (!inside(p, n)) { return; }
  let c = st_at(p);
  let h = c.x;
  let pn = pin_at(p);
  var A = u.uDx * u.uDx + pn.z;
  var qin = pn.w;
  var smax = 0.0;
  var dr = 1.0;
  var hr = h;
  var hlow = h;
  var hnb = 3.0e38;                                         // the lowest neighbour of any height
  for (var k = 0; k < 8; k++) {
    var q: vec2<i32>;
    if (!neighbour(p, k, n, u.uBound, &q)) { continue; }
    let cq = st_at(q);
    hnb = min(hnb, cq.x);
    let d = LEN[k] * u.uDx;
    if (cq.x > h) {
      let share = wpow((cq.x - h) / d, u.uP) / max(wsumT_at(q).x, 1e-30);
      A += cq.y * share;
      qin += cq.z * share;
    } else {
      let s = (h - cq.x) / d;
      if (s > smax) {
        smax = s;
        dr = d;
        hr = cq.x;
      }
      hlow = min(hlow, cq.x);
    }
  }
  if (u.uSlope == 1) {
    smax = 0.0;
    for (var f = 0; f < 8; f++) {
      var q1: vec2<i32>;
      var q2: vec2<i32>;
      if (!neighbour(p, FACET[f].x, n, u.uBound, &q1) || !neighbour(p, FACET[f].y, n, u.uBound, &q2)) { continue; }
      let e1 = st_at(q1).x;
      let e2 = st_at(q2).x;
      let s1 = (h - e1) / u.uDx;
      let s2 = (e1 - e2) / u.uDx;
      var s: f32;
      var rh: f32;
      var rd: f32;
      if (s2 < 0.0) {                                       // the steepest way leaves along the side
        s = s1;
        rh = e1;
        rd = u.uDx;
      } else if (s2 > s1) {                                 // ... along the diagonal
        s = (h - e2) / (1.41421356 * u.uDx);
        rh = e2;
        rd = 1.41421356 * u.uDx;
      } else {                                              // ... through the facet, crossing its outer edge
        var t = 0.0;
        if (s1 > 0.0) { t = s2 / s1; }
        s = sqrt(s1 * s1 + s2 * s2);
        rh = e1 - t * s2 * u.uDx;
        rd = u.uDx * sqrt(1.0 + t * t);
      }
      if (s > smax) {
        smax = s;
        hr = rh;
        dr = rd;
      }
    }
  }
  let pr = par_at(p);
  var K = pr.y;
  if (u.uColN > 0) {
    let t = clamp((h - zoff_at(p).x - u.uColZ0) / u.uColDz, 0.0, f32(u.uColN - 1));
    let i0 = i32(floor(t));
    let i1 = min(i0 + 1, u.uColN - 1);
    let fr = t - f32(i0);
    K *= kcol_at(vec2<i32>(i0, 0)).x * (1.0 - fr) + kcol_at(vec2<i32>(i1, 0)).x * fr;
  }
  let Am = pow(A, u.uM);
  let Dp = pr.w * qin / A;
  let rise = u.uDt * (pr.x + Dp);
  var hn: f32;
  if (smax > 0.0) {
    if (u.uN == 1.0) {
      let F = u.uDt * K * Am / dr;
      hn = (h + rise + F * hr) / (1.0 + F);
    } else {
      hn = max(h - u.uDt * K * Am * pow(smax, u.uN), hlow) + rise;
    }
  } else {
    hn = h + rise;
  }
  var fill = 0.0;
  if (smax <= 0.0 && u.uPitFill == 1 && hnb < 3.0e38) {
    fill = max(hnb + u.uPitEps - hn, 0.0);
    hn += fill;
  }
  let e = max(h + rise - hn, 0.0);                          // metres removed this step
  let qout = max(qin + (e / u.uDt - Dp) * u.uDx * u.uDx, 0.0);
  let m = mk_at(p);
  var dep = m.y + u.uDt * Dp + fill;
  var tal = m.z;
  let loose = m.w + u.uDt * Dp + fill;
  let other = max(loose - dep - tal, 0.0);                  // loose material that is neither (scoria, regolith)
  var r = e;
  var a = min(r, dep);
  dep -= a;
  r -= a;
  a = min(r, tal);
  tal -= a;
  r -= a;
  r -= min(r, other);
  var mo = vec4<f32>(m.x + r, dep, tal, max(loose - e, 0.0));
  if (u.uBound == BOUND_PINNED) {
    let hp = pin_apply(hn, pn.x, pn.y);
    mo = pin_layers(mo, hp - hn);
    hn = hp;
  }
  outS_store(p, vec4<f32>(hn, A, qout, c.w));
  outM_store(p, mo);
}
