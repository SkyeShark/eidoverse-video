// Port of blender/eidoblend/terrain/solvers/volcanic.py _blocks_down with how='nanmax' at f90c6fc: a supersampled
// field back to cells by the largest finite value of each s x s block (NaN when all of the block is NaN: a threshold
// field that is NaN off a wall). The port's own kernel; max and the NaN test are exact.
//! sampler src r32f      the field at the sub-cell points
//! image   outF r32f     the cells
//! uniform int uS

fn kmain(p: vec2<i32>) {
  if (!inside(p, outF_size())) { return; }
  var m = 0.0;
  var any = false;
  for (var j = 0; j < u.uS; j++) {
    for (var i = 0; i < u.uS; i++) {
      let v = src_at(p * u.uS + vec2<i32>(i, j)).x;
      let b = bitcast<u32>(v) & 0x7FFFFFFFu;
      if (b > 0x7F800000u) { continue; }
      if (!any || v > m) { m = v; }
      any = true;
    }
  }
  var out = m;
  if (!any) { out = bitcast<f32>(0x7FC00000u); }
  outF_store(p, vec4<f32>(out, 0.0, 0.0, 0.0));
}
