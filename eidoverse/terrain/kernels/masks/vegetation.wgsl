// Port of blender/eidoblend/terrain/masks.py at f90c6fc: compute's vegetation, float32 as numpy has it, each factor
// in its order and only where its input was made:
//   v = 1 - smoothstep(veg_slope_deg, slope)
//   treeline: alt = float32(h + base) + 0.5 snow_aspect_m northness; v *= 1 - (1 - alpine_density)
//             smoothstep(treeline -/+ band, alt)
//   wetness: v *= 0.35 + 0.65 wetness; occlusion: v *= smoothstep(0.35, 0.75, occlusion)
//   rock: v *= 1 - rock; snow: v *= 1 - snow; rock_toe: v *= 1 - 0.5 rock_toe
//   talus field: v *= 1 - smoothstep(0.2, 2, talus); sand field: v *= 1 - smoothstep(0.1, 1, sand)
//   vegetation = clip(v dry, 0, 1)
//! include masks/lib
//! sampler h
//! sampler geo           (p, q, g, slope)
//! sampler surf          (dry, cover_w, wet_cell, 0)
//! sampler packA         (wetness, occlusion, rock, snow)
//! sampler packB         (rock_toe, talus field, sand field, northness)
//! image   outF r32f
//! uniform vec2 uSlope       smoothstep(veg_slope_deg): (e0, k)
//! uniform int uTree         1: a treeline
//! uniform float uBase       float32(base_elevation_m)
//! uniform float uHalfAspect float32(0.5 snow_aspect_m)
//! uniform vec2 uTreeline    smoothstep(treeline -/+ band): (e0, k)
//! uniform float uAlpine     float32(1 - alpine_density)
//! uniform ivec4 uHasA       which of packA's masks were made
//! uniform ivec4 uHasB       rock_toe made, talus field, sand field, -
//! uniform vec2 uTalus       smoothstep(0.2, 2.0): (e0, k)
//! uniform vec2 uSandV       smoothstep(0.1, 1.0): (e0, k)
//! uniform vec2 uOcc         smoothstep(0.35, 0.75): (e0, k)

fn kmain(p: vec2<i32>) {
  let n = outF_size();
  if (!inside(p, n)) { return; }
  let a = packA_at(p);
  let b = packB_at(p);
  var v = 1.0 - ss(geo_at(p).w, u.uSlope);
  if (u.uTree != 0) {
    let alt = (h_at(p).x + u.uBase) + u.uHalfAspect * b.w;
    v = v * (1.0 - u.uAlpine * ss(alt, u.uTreeline));
  }
  if (u.uHasA.x != 0) { v = v * (0.35 + 0.65 * a.x); }
  if (u.uHasA.y != 0) { v = v * ss(a.y, u.uOcc); }
  if (u.uHasA.z != 0) { v = v * (1.0 - 1.0 * a.z); }
  if (u.uHasA.w != 0) { v = v * (1.0 - 1.0 * a.w); }
  if (u.uHasB.x != 0) { v = v * (1.0 - 0.5 * b.x); }
  if (u.uHasB.y != 0) { v = v * (1.0 - ss(b.y, u.uTalus)); }
  if (u.uHasB.z != 0) { v = v * (1.0 - ss(b.z, u.uSandV)); }
  outF_store(p, vec4<f32>(clamp(v * surf_at(p).x, 0.0, 1.0), 0.0, 0.0, 0.0));
}
