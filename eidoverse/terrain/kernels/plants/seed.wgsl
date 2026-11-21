// plants/seed: the seed cells of plants.py's distance rasters (blender/eidoblend/terrain/build/plants.py at f9fba8c):
// dist_channel's (flow >= channel_flow, or with the channel mask channels > 0.5) and dist_water's (water > 0.05):
// 1 where a >= uA (uModeA 0) or a > uA (uModeA 1), or b > uB when uUseB, else 0.
//! sampler a r32f
//! sampler b r32f
//! image   outS r32ui
//! uniform float uA
//! uniform float uB
//! uniform int   uModeA
//! uniform int   uUseA
//! uniform int   uUseB

fn kmain(p: vec2<i32>) {
  let n = outS_size();
  if (!inside(p, n)) { return; }
  var s = false;
  if (u.uUseA != 0) {
    let v = a_at(p).x;
    if (u.uModeA == 0) { s = v >= u.uA; } else { s = v > u.uA; }
  }
  if (u.uUseB != 0 && b_at(p).x > u.uB) { s = true; }
  outS_store(p, select(0u, 1u, s));
}
