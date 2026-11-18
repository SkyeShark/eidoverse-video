// Port of blender/eidoblend/terrain/run.py _blend at f90c6fc: a stage's `where` limits it, so every field it
// changed is blended with what it was by the mask:
//     fields[k] = (old + m * (new - old)).astype(float32)        old = 0 for a field the stage made
// numpy computes in float64 with m = clip(where_mask, 0, 1); here float32 (the float grade), in numpy's form, so a
// field the stage left alone stays bit for bit (new - old = 0) and m = 0 leaves the old value exactly. At m = 1
// numpy's float64 sum gives back `new` exactly, so the kernel does too.
//! sampler old              uOld 1: the field before the stage; else a 1 x 1 stand-in
//! sampler cur              the field after it
//! sampler m                the where mask (clipped to 0..1 here, where_mask's np.clip)
//! image   outF r32f
//! uniform int uOld

fn kmain(p: vec2<i32>) {
  let n = cur_size();
  if (!inside(p, n)) { return; }
  let mm = clamp(m_at(p).x, 0.0, 1.0);
  let nv = cur_at(p).x;
  var ov = 0.0;
  if (u.uOld != 0) { ov = old_at(p).x; }
  var v = fma(mm, nv - ov, ov);
  if (mm == 1.0) { v = nv; }
  outF_store(p, vec4<f32>(v, 0.0, 0.0, 0.0));
}
