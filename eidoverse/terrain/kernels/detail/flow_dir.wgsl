// flow_dir: a unit downhill direction per cell (the port's own kernel, PORT_PLAN.md 3.2: numpy code of
// blender/eidoblend/terrain/solvers/detail.py flow_direction at f90c6fc moved to the GPU). It replaces
//   fx, fy = the given flow (flow_x, flow_y), or -gx, -gy of the surface box-smoothed over smooth_m (uNeg 1)
//   L = hypot(fx, fy); ok = L > 1e-12
//   (where(ok, fx / L, 0), where(ok, fy / L, 0))
// numpy in float64, float32 here (graded against it).
//! sampler fx            x: the flow's x component, or dh/dx (uNeg)
//! sampler fy            x: its y component, or dh/dy (uNeg)
//! image   outX r32f
//! image   outY r32f
//! uniform int uNeg

fn kmain(p: vec2<i32>) {
  let n = outX_size();
  if (!inside(p, n)) { return; }
  var x = fx_at(p).x;
  var y = fy_at(p).x;
  if (u.uNeg != 0) {
    x = -x;
    y = -y;
  }
  let L = sqrt(x * x + y * y);
  var ox = 0.0;
  var oy = 0.0;
  if (L > 1e-12) {
    ox = x / L;
    oy = y / L;
  }
  outX_store(p, vec4<f32>(ox, 0.0, 0.0, 0.0));
  outY_store(p, vec4<f32>(oy, 0.0, 0.0, 0.0));
}
