// Port of the inline kernel H_KEEP ('h_keep') of blender/eidoblend/terrain/solvers/fluvial.py at f90c6fc.
//
// Transcribed statement for statement from the GLSL source in fluvial.py (PORT_PLAN.md 3.3: an inline kernel
// becomes a file of the same name), as the design probe's transcription (tests/design_probes/wgsl/h_keep.wgsl); the
// `//!` header is the GLSL's, unchanged. The changes are WGSL's: texelFetch is st_at, imageStore is outH_store,
// textureSize is st_size().
//
// creep.glsl moves height only; in the fluvial step its net change over the sub-steps is counted afterwards: h is
// kept before (H_KEEP, into the flow weights' texture, free by then) and the difference goes into the layers
// (creep_layers.wgsl). Twin: solvers/fluvial.py h_keep.
//! sampler st   x: h
//! image   outH r32f

fn kmain(p: vec2<i32>) {
  let n = st_size();
  if (!inside(p, n)) { return; }
  outH_store(p, vec4<f32>(st_at(p).x, 0.0, 0.0, 0.0));
}
