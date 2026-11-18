// Port of blender/eidoblend/terrain/masks.py at f90c6fc: compute's rock_toe, float32 as numpy has it: inside the
// rockfall shadow of exposed rock (smoothstep(tan of rock_toe_shadow_deg, the steepest tangent up to a rock foot)),
// on ground that is not rock itself, concave feet highest:
// rock_toe = smoothstep(...) (1 - rock) (0.75 + 0.25 concave_20m) dry.
//! include masks/lib
//! sampler tan           rock_shadow: the steepest tangent up to a rock foot within reach
//! sampler rock
//! sampler concave       concave_20m
//! sampler surf          (dry, cover_w, wet_cell, 0)
//! image   outF r32f
//! uniform vec2 uShadow  smoothstep(tan(rock_toe_shadow_deg)): (e0, k)

fn kmain(p: vec2<i32>) {
  let n = outF_size();
  if (!inside(p, n)) { return; }
  let v = ((ss(tan_at(p).x, u.uShadow) * (1.0 - rock_at(p).x)) * (0.75 + 0.25 * concave_at(p).x)) * surf_at(p).x;
  outF_store(p, vec4<f32>(v, 0.0, 0.0, 0.0));
}
