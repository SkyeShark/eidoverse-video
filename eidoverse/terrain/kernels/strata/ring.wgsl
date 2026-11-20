// The port's own kernel (no Blender counterpart): blender/eidoblend/terrain/solvers/strata.py op_strata_fluvial()'s
// edge follow at f90c6fc, numpy's
//     inner = _ring_inner(h)                         on the outer ring, each cell's inward neighbour (the diagonal one
//                                                    at the corners)
//     lower = ring & (inner < pin_h);  pin_h[lower] = inner[lower]
// in place on the base pins' heights (each cell reads and writes only its own pin).
//! sampler st       the run's state (x: h)
//! image   ph r32f  the base pins' height
//! local   16 16

fn kmain(p: vec2<i32>) {
  let n = ph_size();
  if (!inside(p, n)) { return; }
  if (!on_edge(p, n)) { return; }
  let q = vec2<i32>(clamp(p.x, 1, n.x - 2), clamp(p.y, 1, n.y - 2));
  let inner = st_at(q).x;
  if (inner < ph_load(p).x) { ph_store(p, vec4<f32>(inner, 0.0, 0.0, 0.0)); }
}
