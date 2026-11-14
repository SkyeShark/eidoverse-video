// creep: blender/eidoblend/terrain/kernels/creep.glsl in WGSL (header copied unchanged)
//! sampler st          x: h (m); y, z, w carried
//! sampler par         z: Sc, the threshold slope's tangent
//! sampler pin         x: pin_w (0..1), y: pin_h (m)
//! image   outS rgba32f
//! uniform float uDx   the cell, metres
//! uniform float uDtSub
//! uniform float uD    the creep diffusivity, m^2/yr
//! uniform float uCap
//! uniform int uBound

fn kmain(p: vec2<i32>) {
  let n = st_size();
  if (!inside(p, n)) { return; }
  let c = st_at(p);
  let h = c.x;
  let sc = par_at(p).z;
  var acc = 0.0;
  for (var k = 0; k < 8; k++) {
    var q: vec2<i32>;
    if (!neighbour(p, k, n, u.uBound, &q)) { continue; }
    let hq = st_at(q).x;
    let scp = 0.5 * (sc + par_at(q).z);
    let r = ((hq - h) / (LEN[k] * u.uDx)) / scp;
    let f = min(1.0 / max(1.0 - r * r, 1e-9), u.uCap);
    acc += WISO[k] * f * (hq - h);
  }
  var hn = h + u.uDtSub * u.uD * acc / (u.uDx * u.uDx);
  if (u.uBound == BOUND_PINNED) {
    let pn = pin_at(p);
    hn = pin_apply(hn, pn.x, pn.y);
  }
  outS_store(p, vec4<f32>(hn, c.y, c.z, c.w));
}
