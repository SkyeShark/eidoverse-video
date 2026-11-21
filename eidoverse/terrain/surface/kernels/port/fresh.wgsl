// Port of numpy code of blender/eidoblend/terrain/surface/bake.py at d67f19e, as a GPU kernel (the port's own,
// PORT_PLAN.md 3.2). fresh: spi and fresh on the window's cells (bake.py step 9), in numpy's float32 order:
//     a       = max(A, cell^2) / cell                              the specific catchment
//     nxy2    = min(n20x^2 + n20y^2, 0.9999),  g20 = sqrt(nxy2 / (1 - nxy2))      the slope at 20 m
//     spi     = clamp((log10(a max(g20, 1e-3)) - lo) / (hi - lo), 0, 1)
//     dry     = 1 - smooth(0, 0.3, water);  bare = (1 - smooth(cover_m, cover)) dry
//     slope20 = degrees(atan(g20));  steep = smooth(steep_deg, slope20)
//     fresh   = smooth(spi_edges, spi) bare (1 - steep)
//               max(fresh, smooth(over_deg, slope20 - degrees(atan(Sc))) bare steep)     where the level has Sc
//               max(fresh, clamp(wear_recent, 0, 1))                                      where it has wear_recent
// WGSL has no log10: log2(x) x log10(2), within the grade of numpy's float32 log10 (graded against Blender's bake).
// smooth is bake.py's TW.smoothstep with its edges as (float32(e0), float32(e1 - e0)).
//! sampler A
//! sampler n20x
//! sampler n20y
//! sampler water
//! sampler cover
//! sampler Sc
//! sampler wr
//! image   outS r32f
//! image   outF r32f
//! uniform float uCell
//! uniform float uCell2
//! uniform vec2 uNorm          (lo, hi - lo): the main tile's spi norms
//! uniform vec2 uWet           smooth(0, 0.3)
//! uniform vec2 uCover         smooth(cover_m)
//! uniform vec2 uSteep         smooth(steep_deg)
//! uniform vec2 uSpi           smooth(fresh spi)
//! uniform vec2 uOver          smooth(over_deg)
//! uniform int uHasSc
//! uniform int uHasWr

fn ss(x: f32, e: vec2<f32>) -> f32 {
  let t = clamp((x - e.x) / e.y, 0.0, 1.0);
  return t * t * (3.0 - 2.0 * t);
}

fn kmain(p: vec2<i32>) {
  let n = outS_size();
  if (!inside(p, n)) { return; }
  let a = max(A_at(p).x, u.uCell2) / u.uCell;
  let nx = n20x_at(p).x;
  let ny = n20y_at(p).x;
  let nxy2 = min(nx * nx + ny * ny, 0.9999);
  let g20 = sqrt(nxy2 / (1.0 - nxy2));
  let spi = clamp((log2(a * max(g20, 1e-3)) * 0.30102999566398120 - u.uNorm.x) / u.uNorm.y, 0.0, 1.0);
  let dry = 1.0 - ss(water_at(p).x, u.uWet);
  let bare = (1.0 - ss(cover_at(p).x, u.uCover)) * dry;
  let slope20 = degrees(atan(g20));
  let steep = ss(slope20, u.uSteep);
  var fresh = ss(spi, u.uSpi) * bare * (1.0 - steep);
  if (u.uHasSc != 0) {
    let over = slope20 - degrees(atan(Sc_at(p).x));
    fresh = max(fresh, ss(over, u.uOver) * bare * steep);
  }
  if (u.uHasWr != 0) { fresh = max(fresh, clamp(wr_at(p).x, 0.0, 1.0)); }
  outS_store(p, vec4<f32>(spi, 0.0, 0.0, 0.0));
  outF_store(p, vec4<f32>(fresh, 0.0, 0.0, 0.0));
}
