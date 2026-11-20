// The port's own kernel (no Blender counterpart): blender/eidoblend/terrain/solvers/strata.py plateau_surface() at
// f90c6fc, which numpy evaluates in float64 from the GPU's float32 noise:
//   mode 0, one escarpment (an `edge`), in order:
//     side = (x - ax) uy - (y - ay) ux  (+ 3 wiggle_m f, its own noise)       > 0 right of the strike direction
//     t = clip(side / w + 0.5, 0, 1),   drop = drop_m t t (3 - 2 t)           (outD)
//     beyond = clip((side - 0.5 w) / max(fade w, 1e-6), 0, 1),  keep = keep (1 - beyond^2 (3 - 2 beyond))   (outK,
//     when roughness_low != 1; else keep is copied)
//   mode 1, the start:   rough = rough (low + (1 - low) keep) when roughness_low != 1;  h = base + rough   (outD)
//   (the drops are then subtracted one by one in order by kernels/strata/acc.wgsl, as numpy's h = h - d)
// side is its value at cell (0, 0) plus its steps per column and per row, made in doubles by solvers/strata.js.
// float32 here, in numpy's order.
//! sampler keepIn     the keep factor so far (mode 0; 1 x 1 stand-in on the first edge: 1)
//! sampler wig        the edge's wiggle noise (1 x 1 stand-in without)
//! sampler base       mode 1: the surface before roughness
//! sampler rough      mode 1: the roughness (1 x 1 stand-in without: 0)
//! image   outD r32f
//! image   outK r32f
//! uniform int uMode
//! uniform ivec4 uHas    x: keepIn given, y: wiggle, z: roughness (mode 1), w: roughness_low != 1
//! uniform vec3 uS       side at cell (0, 0), per column, per row
//! uniform vec4 uE       mode 0: 3 wiggle_m, w, drop_m, fade w;  mode 1: x = roughness_low

fn kmain(p: vec2<i32>) {
  let n = outD_size();
  if (!inside(p, n)) { return; }
  var keep = 1.0;
  if (u.uHas.x == 1) { keep = keepIn_at(p).x; }
  if (u.uMode == 0) {
    var side = u.uS.x + f32(p.x) * u.uS.y + f32(p.y) * u.uS.z;
    if (u.uHas.y == 1) { side = side + u.uE.x * wig_at(p).x; }
    let t = clamp(side / u.uE.y + 0.5, 0.0, 1.0);
    let drop = u.uE.z * t * t * (3.0 - 2.0 * t);
    if (u.uHas.w == 1) {
      let b = clamp((side - 0.5 * u.uE.y) / max(u.uE.w, 1e-6), 0.0, 1.0);
      keep = keep * (1.0 - b * b * (3.0 - 2.0 * b));
    }
    outD_store(p, vec4<f32>(drop, 0.0, 0.0, 0.0));
    outK_store(p, vec4<f32>(keep, 0.0, 0.0, 0.0));
    return;
  }
  var r = 0.0;
  if (u.uHas.z == 1) { r = rough_at(p).x; }
  if (u.uHas.w == 1) {
    let low = u.uE.x;
    r = r * (low + (1.0 - low) * keep);
  }
  outD_store(p, vec4<f32>(base_at(p).x + r, 0.0, 0.0, 0.0));
  outK_store(p, vec4<f32>(keep, 0.0, 0.0, 0.0));
}
