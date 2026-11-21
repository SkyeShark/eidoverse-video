// plants/grid_points: plants.py _GridPoints (blender/eidoblend/terrain/build/plants.py at f9fba8c): the texel centres
// of an m x m raster over a level's window, x0 + (i + 0.5) side / m, as position records (4 numbers: xi, xf, yi,
// yf), row by row from the south-west: the points the cover rasters' densities are evaluated on, and the cells the
// distance rasters read their parent at. The centre is (2i + 1) x the half texel in fixed point (uH = half texel
// 2^uF), so a 16 km window keeps micrometres.
//! include plants/lib
//! image   outP r32ui    4 numbers a point
//! uniform vec4  uO      the window's x0 and y0: integer parts and fractions (xi, xf, yi, yf)
//! uniform ivec2 uH      the half texel in fixed point (hi, lo as int bits)
//! uniform int   uF      its fraction bits
//! uniform int   uM      the raster's side, texels

fn kmain(p: vec2<i32>) {
  let q = lin(p);
  if (q >= u.uM * u.uM) { return; }
  let i = q % u.uM;
  let j = q / u.uM;
  let H = vec2<u32>(bitcast<u32>(u.uH.x), bitcast<u32>(u.uH.y));
  let F = u32(u.uF);
  let ox = fixmul(2 * i + 1, H, F);
  let oy = fixmul(2 * j + 1, H, F);
  let x = coord_add(vec2<f32>(u.uO.x + ox.x, ox.y), u.uO.y);
  let y = coord_add(vec2<f32>(u.uO.z + oy.x, oy.y), u.uO.w);
  outP_b[4 * q] = bitcast<u32>(x.x);
  outP_b[4 * q + 1] = bitcast<u32>(x.y);
  outP_b[4 * q + 2] = bitcast<u32>(y.x);
  outP_b[4 * q + 3] = bitcast<u32>(y.y);
}
