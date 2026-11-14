// threshold: blender/eidoblend/terrain/kernels/threshold.glsl in WGSL (header copied unchanged)
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
    var x: f32;
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
