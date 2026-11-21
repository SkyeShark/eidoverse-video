// plants/cells: the first step of plants.py _candidates (blender/eidoblend/terrain/build/plants.py at f9fba8c) over
// the world cells of one species in a box: a cell counts when its centre lies within reach + 0.7072 c of the focus
// (path_distance), and then draws its cluster centres: hc = _h(tseed, seed, name, ix, iy) (the chain's first three
// links are uKey, made in JavaScript), npar = _poisson(parents_per_ha 1e-4 c^2, _u(hc, 1)) by its integer
// thresholds (bit-exact). Cells in plants.py's meshgrid order: row by row from the box's south-west cell.
//! include plants/lib
//! include plants/focus
//! sampler thr r32ui     Poisson thresholds, two numbers (hi, lo) an entry: ceil(cdf_k 2^53)
//! sampler foc r32f      the focus' points (plants/focus.wgsl)
//! image   outN r32ui    per cell: its cluster centres (0: off the focus' reach)
//! image   outH r32ui    per cell: its hash hc, two numbers (hi, lo)
//! uniform ivec4 uBox    the box: first ix, first iy, columns, rows
//! uniform ivec2 uC      the cell size c 2^32 (u64 as int bits: hi, lo)
//! uniform float uCm     c, metres
//! uniform float uNear   reach + 0.7072 c
//! uniform ivec2 uKey    the chain's hash after (tseed, seed, name): hi, lo as int bits
//! uniform ivec2 uTab    the parents' table: its first entry, its entries
//! uniform int   uCount  the box's cells
//! uniform int   uFocusN

// np.searchsorted(cdf, u, side='right') on the integer thresholds: the entries at or below U
fn pois(first: i32, n: i32, U: vec2<u32>) -> u32 {
  var lo = 0;
  var hi = n;
  while (lo < hi) {
    let m = (lo + hi) / 2;
    let t = vec2<u32>(thr_b[2 * (first + m)], thr_b[2 * (first + m) + 1]);
    if (u64_le(t, U)) { lo = m + 1; } else { hi = m; }
  }
  return u32(lo);
}

fn kmain(p: vec2<i32>) {
  let i = lin(p);
  if (i >= u.uCount) { return; }
  let ix = u.uBox.x + i % u.uBox.z;
  let iy = u.uBox.y + i / u.uBox.z;
  let C = vec2<u32>(bitcast<u32>(u.uC.x), bitcast<u32>(u.uC.y));
  let centre = vec4<f32>(coord_add(fixmul(ix, C, 32u), 0.5 * u.uCm), coord_add(fixmul(iy, C, 32u), 0.5 * u.uCm));
  var npar = 0u;
  var hc = vec2<u32>(0u, 0u);
  if (path_dist(centre) <= u.uNear) {
    let key = vec2<u32>(bitcast<u32>(u.uKey.x), bitcast<u32>(u.uKey.y));
    hc = hstep(hstep(key, key_i(ix)), key_i(iy));
    npar = pois(u.uTab.x, u.uTab.y, u53(hc, 1u));
  }
  outN_b[i] = npar;
  outH_b[2 * i] = hc.x;
  outH_b[2 * i + 1] = hc.y;
}
