// Port of numpy code of blender/eidoblend/terrain/surface/palette_bake.py at d67f19e (the (n, n, 3) colour arrays
// it saves), as a GPU kernel (the port's own, PORT_PLAN.md 3.2). interleave: the rgb of an (n, n) rgba field as an
// (n, 3 n) r32f one, texel 3 i + c of a row channel c of texel i: a numpy (n, n, 3) array's memory, for the
// float16 encoding and the one readback.
//! sampler src
//! image   outF r32f

fn kmain(p: vec2<i32>) {
  let n = outF_size();
  if (!inside(p, n)) { return; }
  let t = src_at(vec2<i32>(p.x / 3, p.y));
  let c = p.x % 3;
  var v = t.x;
  if (c == 1) { v = t.y; }
  if (c == 2) { v = t.z; }
  outF_store(p, vec4<f32>(v, 0.0, 0.0, 0.0));
}
