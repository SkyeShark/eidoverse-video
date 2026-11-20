// The port's own kernel (no Blender counterpart; PORT_PLAN.md 3.2, the glacial row): blender/eidoblend/terrain/
// solvers/glacial.py at f90c6fc keeps its receivers as the neighbour k (0..7, common.wgsl's order; -1 none) in a
// float32 array (d8_receivers, drainage_receivers), which ice_flux.wgsl reads (wT.x) and streams() walks. The
// receivers themselves are solvers/hydro.js's kernel (hydro.py flow_receivers / fluvial.d8_receivers: the same rule,
// P5's), which gives each cell's receiver as a row-major index; this turns that index into its k.
//! sampler rec r32i       the receiver's row-major index, -1 none
//! image   outK r32f      its k (0..7), -1 none

fn kmain(p: vec2<i32>) {
  let n = outK_size();
  if (!inside(p, n)) { return; }
  let r = rec_at(p);
  var k = -1.0;
  if (r >= 0) {
    let d = vec2<i32>(r % n.x, r / n.x) - p;
    for (var j = 0; j < 8; j++) {
      if (OFF[j].x == d.x && OFF[j].y == d.y) { k = f32(j); }
    }
  }
  outK_store(p, vec4<f32>(k, 0.0, 0.0, 0.0));
}
