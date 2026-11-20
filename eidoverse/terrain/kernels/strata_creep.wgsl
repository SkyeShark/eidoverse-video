// Port of the inline kernel STRATA_CREEP ('strata_creep') of blender/eidoblend/terrain/solvers/strata.py at f90c6fc.
//
// Transcribed statement for statement from the GLSL source in strata.py (PORT_PLAN.md 3.3: an inline kernel becomes
// a file of the same name); the `//!` header is the GLSL's, unchanged. The changes are WGSL's: texelFetch(x, q, 0)
// is x_at(q), imageStore is outS_store, textureSize is st_size(), a uniform uX is u.uX, and neighbour()'s `out`
// argument is a pointer.
//
// creep.glsl on soft rock only: the pair's threshold is the mean of its cells' layer tangents, its diffusivity the
// smaller of their creep factors (a cliff's rock does not creep; a shale slope and its talus do).
// Twin: solvers/strata.py strata_creep.
//! sampler st     x: h (m); y, z, w carried
//! sampler cell   x: tan(theta), y: creep factor (strata_cell)
//! sampler pin    x: pin_w, y: pin_h
//! image   outS rgba32f
//! uniform float uDx
//! uniform float uDtSub
//! uniform float uD
//! uniform float uCap
//! uniform int uBound

fn kmain(p: vec2<i32>) {
  let n = st_size();
  if (!inside(p, n)) { return; }
  let c = st_at(p);
  let h = c.x;
  let cc = cell_at(p).xy;
  var acc = 0.0;
  for (var k = 0; k < 8; k++) {
    var q: vec2<i32>;
    if (!neighbour(p, k, n, u.uBound, &q)) { continue; }
    let hq = st_at(q).x;
    let cq = cell_at(q).xy;
    let scp = 0.5 * (cc.x + cq.x);
    let r = ((hq - h) / (LEN[k] * u.uDx)) / scp;
    let f = min(1.0 / max(1.0 - r * r, 1e-9), u.uCap);
    acc += WISO[k] * f * min(cc.y, cq.y) * (hq - h);
  }
  var hn = h + u.uDtSub * u.uD * acc / (u.uDx * u.uDx);
  if (u.uBound == BOUND_PINNED) {
    let pn = pin_at(p);
    hn = pin_apply(hn, pn.x, pn.y);
  }
  outS_store(p, vec4<f32>(hn, c.y, c.z, c.w));
}
