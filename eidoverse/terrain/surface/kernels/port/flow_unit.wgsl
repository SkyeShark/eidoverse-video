// Port of numpy code of blender/eidoblend/terrain/surface/bake.py at d67f19e, as a GPU kernel (the port's own,
// PORT_PLAN.md 3.2). flow_unit: the routed flow vector of a level made a unit vector, cell by cell (bake.py steps
// 2-4: L = np.maximum(np.hypot(fx, fy), F(1e-12)); fx / L, fy / L), into two channels; combine.wgsl's steer mode
// pads it.
//! sampler fx
//! sampler fy
//! image   outF rg32f

fn kmain(p: vec2<i32>) {
  let n = outF_size();
  if (!inside(p, n)) { return; }
  let x = fx_at(p).x;
  let y = fy_at(p).x;
  let L = max(sqrt(x * x + y * y), 1e-12);
  outF_store(p, vec4<f32>(x / L, y / L, 0.0, 0.0));
}
