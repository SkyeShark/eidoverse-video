// Port of numpy code of blender/eidoblend/terrain/surface/bake.py at d67f19e, as a GPU kernel (the port's own,
// PORT_PLAN.md 3.2). pick: one channel of a field at the cell uOffset away, into an r32f field: bake.py's
// _crop(a[..., c], m, n, f) (uOffset = m f) and its a[..., c] (uOffset = 0).
//! sampler a
//! image   outF r32f
//! uniform int uCh
//! uniform ivec2 uOffset

fn kmain(p: vec2<i32>) {
  let n = outF_size();
  if (!inside(p, n)) { return; }
  outF_store(p, vec4<f32>(a_at(p + u.uOffset)[u.uCh], 0.0, 0.0, 0.0));
}
