// Port of blender/eidoblend/terrain/kernels/threshold.glsl at f90c6fc.
//
// Transcribed statement for statement from the GLSL (PORT_PLAN.md 4.2), starting from the design probe's
// transcription (tests/design_probes/wgsl/threshold.wgsl); the `//!` header is the GLSL's, unchanged. The changes are
// WGSL's: texelFetch(x, q, 0) is x_at(q), imageStore is outS_store / outM_store, textureSize is st_size(), a uniform
// uX is u.uX, neighbour()'s `out` argument is a pointer, and the ?: are select() (both arms are plain reads) or ifs.
//
/* threshold (design section 4.1, pass 4; 4.2): one iteration of the mass-conserving threshold relaxation, which
   keeps slopes at or under their threshold (hillslopes failing at their angle; talus at repose). Every neighbour
   pair exchanges an amount computed alike from both of its cells, so the sum of h is conserved (open and periodic
   modes); the moved material lands where the rivers carry it away.

   uIso = 1 (the default): isotropic. Each cell's slope is the upwind (Rouy-Tourin) gradient magnitude
       G = sqrt(max(h - min(h_W, h_E), 0)^2 + max(h - min(h_S, h_N), 0)^2) / dx,
   exact for a plane facing any direction, and its excess phi = max(1 - Sc / G, 0) (phiT: written for the same h
   by solvers/hillslope.py's inline kernel threshold_excess, once per iteration). The pair (c, k) exchanges
       x = rate WISO_k (h_c - h_k) (phi_c + phi_k) / 2,
   a nonlinear diffusion that runs only where the slope is over its threshold, along the gradient with the
   isotropic 9-point weights, until G <= Sc everywhere.
   uIso = 0: the design's pair excess, x = rate max(|h_c - h_k| - Sc_pair L_k dx, 0) from the higher cell. Its
   stable slopes form an octagon (8 % steeper between the grid directions) and it relaxes axis-facing slopes slower
   than diagonal ones (the excess is counted in height over a pair √2 longer): on the first range's threshold slopes
   that printed 4-fold (0.12) and 8-fold (0.07) aspect bias, against the San Gabriels' 0.02 and 0.004.

   uLoose = 1 limits it to loose material: a cell gives at most an eighth of its loose thickness (mk.w, h - bed) to
   each neighbour, so bedrock walls stand and only debris relaxes (the talus stage). The accumulators: a net gain is
   talus; a net loss takes talus, then deposit, then other loose cover, then rock (wear); mk.w, the loose
   thickness, follows the net change. In BOUND_PINNED mode the height is pulled to its pin, and the pull is counted
   in the layers as route_incise.glsl counts it (pin_layers: added as deposit, taken loose first, then rock).
   Twin: solvers/hillslope.py threshold. */
//! sampler st          x: h (m); y, z, w carried
//! sampler par         z: Sc, the threshold slope's tangent
//! sampler pin         x: pin_w (0..1), y: pin_h (m)
//! sampler mk          x: wear (m), y: deposit (m), z: talus (m), w: loose thickness h - bed (m)
//! sampler phiT        x: every cell's excess phi (isotropic mode; a 1 x 1 dummy in pair mode)
//! image   outS rgba32f
//! image   outM rgba32f
//! uniform float uDx   the cell, metres
//! uniform float uRate the share moved per iteration (pair excess 0.06; isotropic 0.12)
//! uniform int uLoose  1: only loose material moves
//! uniform int uIso    1: isotropic (upwind gradient magnitude); 0: the design's pair excess
//! uniform int uBound

/* the pin's change d of the height in the layers m (as route_incise.glsl) */
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

fn kmain(p: vec2<i32>) {
  let n = st_size();
  if (!inside(p, n)) { return; }
  let c = st_at(p);
  let h = c.x;
  let sc = par_at(p).z;
  let m = mk_at(p);
  var phc = 0.0;
  if (u.uIso == 1) { phc = phiT_at(p).x; }
  var dh = 0.0;
  for (var k = 0; k < 8; k++) {
    var q: vec2<i32>;
    if (!neighbour(p, k, n, u.uBound, &q)) { continue; }
    let hq = st_at(q).x;
    var x: f32;                                           // what c gives q (negative: what it receives)
    if (u.uIso == 1) {
      x = u.uRate * WISO[k] * ((h - hq) * (0.5 * (phc + phiT_at(q).x)));
    } else {
      let t = 0.5 * (sc + par_at(q).z) * LEN[k] * u.uDx;
      let e = u.uRate * max(abs(h - hq) - t, 0.0);
      x = select(-e, e, h > hq);
    }
    if (u.uLoose == 1) {
      let giver = select(mk_at(q).w, m.w, h > hq);
      x = sign(x) * min(abs(x), 0.125 * max(giver, 0.0));
    }
    dh -= x;
  }
  var tal = m.z;
  var dep = m.y;
  var wear = m.x;
  if (dh >= 0.0) {
    tal += dh;
  } else {
    let other = max(m.w - dep - tal, 0.0);
    var r = -dh;
    var a = min(r, tal);
    tal -= a;
    r -= a;
    a = min(r, dep);
    dep -= a;
    r -= a;
    r -= min(r, other);
    wear += r;
  }
  var hn = h + dh;
  var mo = vec4<f32>(wear, dep, tal, max(m.w + dh, 0.0));
  if (u.uBound == BOUND_PINNED) {
    let pn = pin_at(p);
    let hp = pin_apply(hn, pn.x, pn.y);
    mo = pin_layers(mo, hp - hn);
    hn = hp;
  }
  outS_store(p, vec4<f32>(hn, c.y, c.z, c.w));
  outM_store(p, mo);
}
