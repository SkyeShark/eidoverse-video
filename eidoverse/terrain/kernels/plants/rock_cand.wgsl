// Port of numpy code of blender/eidoblend/terrain/build/dressing.py at f9fba8c, as a GPU kernel.
// plants/rock_cand: dressing.py place_rocks' candidates (build/dressing.js), as the planner's candidate records (16
// numbers, the position at 0-3 as integer part and fraction): uMode 0, candidate i uniform in the disc of radius R
// round the focus (r = R sqrt(u), theta = 2 pi u'), its id at 4-5; uMode 1, the density's 96 x 96 probe grid over the
// disc's square (np.linspace(f - R, f + R, 96) each way), point k = j 96 + i. A candidate's uniforms are hashes of
// (the scatter's key, i) (plants/lib.wgsl), where Blender draws them in turn from numpy's generator.
//! include plants/lib
//! image   outC r32ui    16 numbers a point
//! uniform vec4  uF      the focus: x integer part, fraction, y integer part, fraction
//! uniform vec4  uR      R, 0, 0, 0
//! uniform ivec2 uKey    the scatter's key, hi and lo bits
//! uniform int   uMode
//! uniform int   uCount

fn kmain(p: vec2<i32>) {
  let i = lin(p);
  if (i >= u.uCount) { return; }
  let R = u.uR.x;
  var dx = 0.0;
  var dy = 0.0;
  let key = vec2<u32>(bitcast<u32>(u.uKey.x), bitcast<u32>(u.uKey.y));
  let h = hstep(key, key_i(i));
  if (u.uMode == 0) {
    let r = R * sqrt(u53f(u53(h, 0u)));
    let cs = cossin2pi(u53(h, 1u));
    dx = r * cs.x;
    dy = r * cs.y;
  } else {
    let gi = i % 96;
    let gj = i / 96;
    dx = -R + f32(gi) * (2.0 * R / 95.0);
    dy = -R + f32(gj) * (2.0 * R / 95.0);
    // a probe outside the disc reads the focus instead (inside it): the maximum is the disc's
    if (dx * dx + dy * dy > R * R) { dx = 0.0; dy = 0.0; }
  }
  let x = coord_add(u.uF.xy, dx);
  let y = coord_add(u.uF.zw, dy);
  let o = 16u * u32(i);
  outC_b[o] = bitcast<u32>(x.x);
  outC_b[o + 1u] = bitcast<u32>(x.y);
  outC_b[o + 2u] = bitcast<u32>(y.x);
  outC_b[o + 3u] = bitcast<u32>(y.y);
  outC_b[o + 4u] = h.x;
  outC_b[o + 5u] = h.y;
  outC_b[o + 6u] = bitcast<u32>(select(0.0, 1.0, dx * dx + dy * dy <= R * R));
  for (var w = 7u; w < 16u; w++) { outC_b[o + w] = 0u; }
}
