// plants/prefilter: the first lines of plants.py _thin (blender/eidoblend/terrain/build/plants.py at f9fba8c): a
// candidate stays when it lies on the terrain (the outermost level's window, inclusive), within exact + pad of the
// focus (path_distance), and off every excluded disc ((x - ex)^2 + (y - ey)^2 > reach^2; a 'crown' disc reaches
// r + crown_m x size / size_m[1]). Writes the candidate's path distance into its record (word 9) and its flag.
//! include plants/lib
//! include plants/focus
//! sampler foc r32f      the focus' points (plants/focus.wgsl)
//! sampler dsc r32f      the excluded discs, 6 numbers each: xi, xf, yi, yf, r, crown (1: keep crowns off too)
//! image   cand r32ui    the candidates' records (plants/offspring): word 9 written
//! image   outF r32ui    1: the candidate stays
//! uniform vec4  uBI     the terrain's bounds (x0, y0, x1, y1): integer parts
//! uniform vec4  uBF     and fractions
//! uniform vec4  uLim    exact + pad, crown_m, size_m[1], 0
//! uniform int   uDiscs
//! uniform int   uCount
//! uniform int   uFocusN

fn kmain(p: vec2<i32>) {
  let i = lin(p);
  if (i >= u.uCount) { return; }
  let o = 16u * u32(i);
  let pos = vec4<f32>(bitcast<f32>(cand_b[o]), bitcast<f32>(cand_b[o + 1u]), bitcast<f32>(cand_b[o + 2u]),
                      bitcast<f32>(cand_b[o + 3u]));
  let size = bitcast<f32>(cand_b[o + 7u]);
  let d = path_dist(pos);
  cand_b[o + 9u] = bitcast<u32>(d);
  var ok = coord_sub(pos.xy, vec2<f32>(u.uBI.x, u.uBF.x)) >= 0.0 && coord_sub(pos.xy, vec2<f32>(u.uBI.z, u.uBF.z)) <= 0.0 &&
           coord_sub(pos.zw, vec2<f32>(u.uBI.y, u.uBF.y)) >= 0.0 && coord_sub(pos.zw, vec2<f32>(u.uBI.w, u.uBF.w)) <= 0.0 &&
           d <= u.uLim.x;
  for (var k = 0; k < u.uDiscs; k++) {
    let c = vec4<f32>(dsc_b[6 * k], dsc_b[6 * k + 1], dsc_b[6 * k + 2], dsc_b[6 * k + 3]);
    var reach = dsc_b[6 * k + 4];
    if (dsc_b[6 * k + 5] > 0.5) { reach = reach + u.uLim.y * size / u.uLim.z; }
    ok = ok && pos_d2(pos, c) > reach * reach;
  }
  outF_b[i] = select(0u, 1u, ok);
}
