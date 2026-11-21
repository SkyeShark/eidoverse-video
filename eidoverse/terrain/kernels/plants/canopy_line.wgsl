// Port of numpy code of blender/eidoblend/terrain/build/plant_instances.py at f9fba8c, as a GPU kernel.
// plants/canopy_line: plant_instances.py canopy_line and the end of sun_shade, per spot: the shadow line the crowns
// toward the sun cast on its card (a crown [x, y, top, r] within CANOPY_REACH_M of the card, nearer the sun along its
// line of light by more than 0.5 m and within r of it across, shades it below top - along tan(el); the highest such
// line), over the card's centre and clipped to +-1e4 (CANOPY_NONE where none), and the terrain's shade from the
// levels' excess (plants/sun_sample): smoothstep of (excess + 0.5) / 3.5. The crowns on the hashed grid of
// plants/grid.wgsl in cells of the reach (the 3 x 3 cells round the card hold every crown within it; a crown counted
// in its own cell only).
//! include plants/lib
//! include plants/grid
//! sampler rec r32f      the spots' records, 12 numbers each
//! sampler vk r32f       per individual: k, the billboard's centre height
//! sampler ex r32f       per spot: the terrain's excess
//! sampler crw r32ui     the crowns (plants/crown_rec), 6 numbers each
//! sampler starts r32ui  per bucket its first crown in `order`
//! sampler counts r32ui  per bucket its crowns
//! sampler order r32ui   the crowns sorted by bucket
//! image   outS r32f     per spot: the shade, the canopy line over the card's centre less CANOPY_NONE (-1e4): 0 is
//                        no line, as the spots' numbers start
//! uniform vec4  uGO
//! uniform ivec2 uGW
//! uniform float uGInv
//! uniform int   uGMask
//! uniform vec4  uDir    ux, uy, tan(el), 1 with a sun over the horizon (0: below it, all shade; 2: overhead, none)
//! uniform vec4  uBase   sink, foot, the individuals, the reach
//! uniform int   uCount

fn crown(j: u32) -> vec4<f32> {
  let d = 6u * j;
  return vec4<f32>(bitcast<f32>(crw_b[d]), bitcast<f32>(crw_b[d + 1u]), bitcast<f32>(crw_b[d + 2u]), bitcast<f32>(crw_b[d + 3u]));
}

fn kmain(p: vec2<i32>) {
  let q = lin(p);
  if (q >= u.uCount) { return; }
  let o = 12 * q;
  let x = rec_b[o];
  let y = rec_b[o + 1];
  let sc = rec_b[o + 4];
  let tn = sqrt(rec_b[o + 7] * rec_b[o + 7] + rec_b[o + 8] * rec_b[o + 8]) / max(rec_b[o + 9], 0.2);
  let zb = rec_b[o + 2] - sc * (u.uBase.x + u.uBase.y * min(tn, 2.0));
  let v = clamp(i32(rec_b[o + 10]), 0, i32(u.uBase.z) - 1);
  let pz = zb + sc * vk_b[2 * v] * vk_b[2 * v + 1];
  var line = -1.0e9;
  var shade = 0.0;
  if (u.uDir.w > 0.5 && u.uDir.w < 1.5) {
    let e = clamp((ex_b[q] + 0.5) / 3.5, 0.0, 1.0);
    shade = e * e * (3.0 - 2.0 * e);
    let pos = vec4<f32>(floor(x), x - floor(x), floor(y), y - floor(y));
    let c0 = gcell(pos);
    let reach2 = u.uBase.w * u.uBase.w;
    for (var dy = -1; dy <= 1; dy++) {
      for (var dx = -1; dx <= 1; dx++) {
        let cc = c0 + vec2<i32>(dx, dy);
        let b = gkey(cc);
        let first = starts_b[b];
        let m = counts_b[b];
        for (var k = 0u; k < m; k++) {
          let j = order_b[first + k];
          let cp = crown(j);
          let g = gcell(cp);
          if (g.x != cc.x || g.y != cc.y) { continue; }
          let ddx = coord_sub(cp.xy, pos.xy);
          let ddy = coord_sub(cp.zw, pos.zw);
          if (ddx * ddx + ddy * ddy > reach2) { continue; }
          let along = ddx * u.uDir.x + ddy * u.uDir.y;
          let across = ddy * u.uDir.x - ddx * u.uDir.y;
          let top = bitcast<f32>(crw_b[6u * j + 4u]);
          let r = bitcast<f32>(crw_b[6u * j + 5u]);
          if (along > 0.5 && abs(across) < r) { line = max(line, top - along * u.uDir.z); }
        }
      }
    }
  } else {
    shade = select(1.0, 0.0, u.uDir.w > 1.5);
  }
  outS_b[2 * q] = shade;
  outS_b[2 * q + 1] = clamp(line - pz, -1.0e4, 1.0e4) + 1.0e4;
}
