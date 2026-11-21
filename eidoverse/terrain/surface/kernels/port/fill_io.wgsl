// Port of numpy code of blender/eidoblend/terrain/surface/bake.py at d67f19e, as a GPU kernel (the port's own,
// PORT_PLAN.md 3.2). fill_io: the filled surface's start (bake.py _Baker._fill), cell by cell on the padded grid:
//     z = hp + water                          the ground and its lake water (float32)
//     held = the grid's outer ring            core/twins.py on_edge
//     outZ = (z, held, 0, 0)                  fill.glsl's zT
//     outW = held ? z : BIG                   W0, the surface before the first pass
//! sampler hp
//! sampler water
//! image   outZ rgba32f
//! image   outW r32f
//! uniform float uBig

fn kmain(p: vec2<i32>) {
  let n = outZ_size();
  if (!inside(p, n)) { return; }
  let z = hp_at(p).x + water_at(p).x;
  let held = on_edge(p, n);
  outZ_store(p, vec4<f32>(z, select(0.0, 1.0, held), 0.0, 0.0));
  outW_store(p, vec4<f32>(select(u.uBig, z, held), 0.0, 0.0, 0.0));
}
