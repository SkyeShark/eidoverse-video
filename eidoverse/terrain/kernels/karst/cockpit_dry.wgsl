// Port of the `allowed` masks blender/eidoblend/terrain/solvers/karst.py gives _cockpit_floors at f90c6fc, as a kernel:
//   uMode 0  the floor map's: (water <= 0) & (h >= plain - 0.25)        (_floor_map; plain - 0.25 in float32 as numpy's)
//   uMode 1  a context level's: G.down(surface >= level - 0.25) > 0.999 (evaluate: every subsample of the cell dry)
// 1 where a basin's bottom may lie, 0 elsewhere.

//! sampler h
//! sampler water
//! sampler plain
//! sampler B rgba32f         uMode 1: compose.wgsl's per-cell pack (z: the dry share)
//! image   outA r32f
//! uniform int uMode
fn kmain(p: vec2<i32>) {
  let n = outA_size();
  if (!inside(p, n)) { return; }
  var ok = false;
  if (u.uMode == 0) {
    ok = water_at(p).x <= 0.0 && h_at(p).x >= plain_at(p).x - 0.25;
  } else {
    ok = B_at(p).z > 0.999;
  }
  outA_store(p, vec4<f32>(select(0.0, 1.0, ok), 0.0, 0.0, 0.0));
}
