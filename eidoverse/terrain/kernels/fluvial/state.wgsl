// The port's own kernel (no Blender counterpart): the state packs blender/eidoblend/terrain/solvers/fluvial.py's
// FluvialRun and hillslope.py's _Pass stack from a level's fields with numpy (T.rgba) at f90c6fc, made on the GPU:
//     st = (h, A, qs, 0)                          A: the field, else uArea (FluvialRun: cell^2; _Pass: 0)
//     mk = (wear, deposit, talus, loose)          loose = max(h - bed, 0) (np.maximum of the float32 difference), 0
//                                                 without a bed; a missing layer is 0
//! sampler h
//! sampler A
//! sampler qs
//! sampler bed
//! sampler wear
//! sampler dep
//! sampler tal
//! image   outS rgba32f
//! image   outM rgba32f
//! uniform ivec4 uHas    A, qs, bed, (wear, deposit, talus present: bits 0, 1, 2)
//! uniform float uArea

fn kmain(p: vec2<i32>) {
  if (!inside(p, outS_size())) { return; }
  let h = h_at(p).x;
  var A = u.uArea;
  if (u.uHas.x == 1) { A = A_at(p).x; }
  var q = 0.0;
  if (u.uHas.y == 1) { q = qs_at(p).x; }
  var loose = 0.0;
  if (u.uHas.z == 1) { loose = max(h - bed_at(p).x, 0.0); }
  var m = vec4<f32>(0.0, 0.0, 0.0, loose);
  if ((u.uHas.w & 1) != 0) { m.x = wear_at(p).x; }
  if ((u.uHas.w & 2) != 0) { m.y = dep_at(p).x; }
  if ((u.uHas.w & 4) != 0) { m.z = tal_at(p).x; }
  outS_store(p, vec4<f32>(h, A, q, 0.0));
  outM_store(p, m);
}
