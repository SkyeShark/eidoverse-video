// Port of the inline kernel SOIL ('soil_jacobi') of blender/eidoblend/terrain/solvers/hillslope.py at f90c6fc.
//
// Transcribed statement for statement from the GLSL source in hillslope.py (PORT_PLAN.md 3.3: an inline kernel
// becomes a file of the same name); the `//!` header is the GLSL's, unchanged. The changes are WGSL's: texelFetch is
// x_at, imageStore is outS_store, textureSize is st_size(), a uniform uX is u.uX, neighbour()'s `out` argument is a
// pointer, and the ?: are select() (both arms are plain values) or an if. The GLSL's two mix(a, b, t) are written
// a (1 - t) + b t, as the numpy twin (solvers/hillslope.py soil_jacobi) computes them, which is the oracle both
// kernels are held to (common.wgsl says why for pin_apply: backends lower mix to a + (b - a) t, which differs in the
// last bits and leaves a fully held cell off its value).
//
// Soil hillslopes at steady state (hillslope.py): linear creep with uplift, div(D grad h) = -U, with the channels
// held. One damped Jacobi step of the 9-point isotropic stencil per dispatch; each pair's weight depends only on
// which of the two cells is higher, so the operator is the divergence of a flux. The diffusivity may depend on which
// way a slope faces the wind: D (1 - a cos theta), theta between the pair's downslope direction and the wind's.
//! sampler st     x: h (m)
//! sampler con    x: hold (1 on channels), y: the held height (m), z: pin_w, w: pin_h (the border band)
//! image   outS r32f
//! uniform float uDx      the cell, metres
//! uniform float uC       U / D (1/m): the steady Laplacian of h is -uC
//! uniform float uAsym    a: the pair's diffusivity is 1 - a cos(downslope direction, wind)
//! uniform vec2 uWind     the unit vector the wind blows toward (x east, y north)
//! uniform float uOmega   the Jacobi damping, 0..1
//! uniform int uBound

fn kmain(p: vec2<i32>) {
  let n = st_size();
  if (!inside(p, n)) { return; }
  let h = st_at(p).x;
  var num = 0.0;
  var den = 0.0;
  for (var k = 0; k < 8; k++) {
    var q: vec2<i32>;
    if (!neighbour(p, k, n, u.uBound, &q)) { continue; }
    let hq = st_at(q).x;
    let dw = dot(vec2<f32>(OFF[k]), u.uWind) / LEN[k];      // c -> q along the wind
    let w = WISO[k] * (1.0 - u.uAsym * select(-dw, dw, h >= hq));
    num += w * hq;
    den += w;
  }
  var hj = h;
  if (den > 0.0) { hj = (num + u.uC * u.uDx * u.uDx) / den; }
  let c = con_at(p);
  var hn = h * (1.0 - u.uOmega) + hj * u.uOmega;
  let a = clamp(c.x, 0.0, 1.0);
  hn = hn * (1.0 - a) + c.y * a;
  hn = pin_apply(hn, c.z, c.w);
  outS_store(p, vec4<f32>(hn, 0.0, 0.0, 0.0));
}
