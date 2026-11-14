// Port of blender/eidoblend/terrain/core/grid.py at f90c6fc: edge_distance and border_ramp.
//   edge_distance  the Chebyshev distance of every cell from the window's nearest edge, in cells (0 on the edge
//                  row): exact integers, held as float32
//   border_ramp    the border band's pin weight (design 2.2): 1 on the edge, falling to 0 at `band` cells in;
//                  'smooth' 1 - smoothstep(0, band, d) (C1: the blend leaves no crease line), 'linear' 1 - d / band
// numpy computes the ramp in float64 and rounds it to float32 once; this is float32.
//! image   outF r32f
//! uniform int uMode     0 edge distance, 1 smooth ramp, 2 linear ramp
//! uniform float uBand

fn kmain(p: vec2<i32>) {
  let n = outF_size();
  if (!inside(p, n)) { return; }
  let d = f32(min(min(p.x, n.x - 1 - p.x), min(p.y, n.y - 1 - p.y)));
  var v = d;
  if (u.uMode != 0) {
    let t = clamp(d / u.uBand, 0.0, 1.0);
    if (u.uMode == 1) { v = 1.0 - t * t * (3.0 - 2.0 * t); } else { v = 1.0 - t; }
  }
  outF_store(p, vec4<f32>(v, 0.0, 0.0, 0.0));
}
