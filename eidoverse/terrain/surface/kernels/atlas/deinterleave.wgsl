// Port of numpy code of blender/eidoblend/terrain/surface/palette_bake.py at d67f19e (the (n, n, 3) colour arrays
// it loads), as a GPU kernel (the port's own, PORT_PLAN.md 3.2). deinterleave: interleave.wgsl's inverse, an
// (n, 3 n) r32f field (a numpy (n, n, 3) array's memory) as the rgb of an (n, n) rgba one, alpha 0.
//! sampler src
//! image   outR rgba32f

fn kmain(p: vec2<i32>) {
  let n = outR_size();
  if (!inside(p, n)) { return; }
  let q = vec2<i32>(3 * p.x, p.y);
  outR_store(p, vec4<f32>(src_at(q).x, src_at(q + vec2<i32>(1, 0)).x, src_at(q + vec2<i32>(2, 0)).x, 0.0));
}
