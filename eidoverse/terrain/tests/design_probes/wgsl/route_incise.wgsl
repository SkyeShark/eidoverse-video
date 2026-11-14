// route_incise: blender/eidoblend/terrain/kernels/route_incise.glsl in WGSL, statement for statement (header copied
// unchanged; see the GLSL file for the physics)
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
  var hnb = 3.0e38;
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
      if (s2 < 0.0) {
        s = s1;
        rh = e1;
        rd = u.uDx;
      } else if (s2 > s1) {
        s = (h - e2) / (1.41421356 * u.uDx);
        rh = e2;
        rd = 1.41421356 * u.uDx;
      } else {
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
  let e = max(h + rise - hn, 0.0);
  let qout = max(qin + (e / u.uDt - Dp) * u.uDx * u.uDx, 0.0);
  let m = mk_at(p);
  var dep = m.y + u.uDt * Dp + fill;
  var tal = m.z;
  let loose = m.w + u.uDt * Dp + fill;
  let other = max(loose - dep - tal, 0.0);
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
