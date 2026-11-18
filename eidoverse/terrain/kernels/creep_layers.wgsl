// Port of the inline kernel CREEP_LAYERS ('creep_layers') of blender/eidoblend/terrain/solvers/fluvial.py at f90c6fc.
//
// Transcribed statement for statement from the GLSL source in fluvial.py (PORT_PLAN.md 3.3: an inline kernel
// becomes a file of the same name), as the design probe's transcription (tests/design_probes/wgsl/creep_layers.wgsl);
// the `//!` header is the GLSL's, unchanged. The changes are WGSL's: texelFetch is x_at, imageStore is outM_store,
// textureSize is st_size().
//
// creep's net change over the fluvial step's sub-steps, counted in the layers: a gain is soil, other loose cover; a
// loss takes deposit, talus, other loose cover, then rock. Uncounted, a pit refilled every step (deposit) that creep
// levelled again gathered hundreds of metres of "deposit" in one cell. Twin: solvers/fluvial.py creep_layers.
//! sampler st   x: h after creep
//! sampler h0   x: h before creep
//! sampler mk   x: wear, y: deposit, z: talus, w: loose thickness (m)
//! image   outM rgba32f

fn kmain(p: vec2<i32>) {
  let n = st_size();
  if (!inside(p, n)) { return; }
  var m = mk_at(p);
  let d = st_at(p).x - h0_at(p).x;
  if (d >= 0.0) {
    m.w += d;
  } else {
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
  }
  outM_store(p, m);
}
