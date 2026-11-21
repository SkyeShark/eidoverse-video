// Port of numpy code of blender/eidoblend/terrain/surface/bake.py at d67f19e, as a GPU kernel (the port's own,
// PORT_PLAN.md 3.2). relax_io: what bake.py _Baker._relax hands detail.relax and takes back, cell by cell:
//   uMode 0  in       outA = (b0, 0, 0, 0) with b0 = (hp + d0) / cell (T.rgba(b0): the pipe model's base), outB =
//                     hp / cell (the cohesive top, bed), numpy's float32 ((hp + d0) / F(cell)) and (hp / F(cell))
//   uMode 1  out      outA = max(d0 + state.x x cell, 0): the layer, metres (np.maximum(d0 + dl * F(cell), 0))
//   uMode 2  start    detail.relax's start with a repose per cell (the snowpack's flowing pass): outA =
//                     initial_state(b0, bed) = (0, 0, 0, min(bed - b0, 0)), outB = T.rgba(sc, rep, floor) with sc
//                     BIG_TAN (nothing cohesive fails) and floor -1e6 (detail.relax's default): the per-cell form of
//                     solvers/detail.js relax's start (kernels/detail/pipe_start.wgsl takes one repose)
//! sampler a                   mode 0: hp; mode 1: d0; mode 2: b0 (T.rgba)
//! sampler b                   mode 0: d0; mode 1: the pipe state (x: delta); mode 2: bed
//! sampler c                   mode 2: the repose tangent per cell
//! image   outA rgba32f
//! image   outB rgba32f
//! uniform int uMode
//! uniform float uCell
//! uniform float uBigTan
//! uniform float uFloor

fn kmain(p: vec2<i32>) {
  let n = outA_size();
  if (!inside(p, n)) { return; }
  if (u.uMode == 0) {
    let hp = a_at(p).x;
    outA_store(p, vec4<f32>((hp + b_at(p).x) / u.uCell, 0.0, 0.0, 0.0));
    outB_store(p, vec4<f32>(hp / u.uCell, 0.0, 0.0, 0.0));
  } else if (u.uMode == 1) {
    outA_store(p, vec4<f32>(max(a_at(p).x + b_at(p).x * u.uCell, 0.0), 0.0, 0.0, 0.0));
  } else {
    outA_store(p, vec4<f32>(0.0, 0.0, 0.0, min(b_at(p).x - a_at(p).x, 0.0)));
    outB_store(p, vec4<f32>(u.uBigTan, c_at(p).x, u.uFloor, 0.0));
  }
}
