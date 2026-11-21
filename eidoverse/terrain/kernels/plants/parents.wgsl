// plants/parents: plants.py _candidates' cluster centres (blender/eidoblend/terrain/build/plants.py at f9fba8c): per
// world cell, its npar centres in order, hp = _h(hc, pj), px = (ix + _u(hp, 2)) c, py = (iy + _u(hp, 3)) c, and each
// centre's offspring count _poisson(mu, _u(hp, 5)) by its integer thresholds. Centre k of a cell goes to slot
// offs[cell] + k: _ragged's order. A record: xi, xf, yi, yf (float32 bits), hp hi, hp lo, offspring, 0.
//! include plants/lib
//! sampler npar r32ui    per cell: its centres (plants/cells)
//! sampler offs r32ui    per cell: the centres of the cells before it (an exclusive scan)
//! sampler hcs r32ui     per cell: hc (hi, lo)
//! sampler thr r32ui     Poisson thresholds (plants/cells)
//! image   outP r32ui    the centres' records, 8 numbers each
//! image   outO r32ui    per centre: its offspring (for the scan)
//! uniform ivec4 uBox    the box: first ix, first iy, columns, rows
//! uniform ivec2 uC      c 2^32 (hi, lo as int bits)
//! uniform float uCm     c, metres
//! uniform ivec2 uTab    the offspring table: its first entry, its entries
//! uniform int   uCount  the box's cells

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
  let n = npar_b[i];
  if (n == 0u) { return; }
  let ix = u.uBox.x + i % u.uBox.z;
  let iy = u.uBox.y + i / u.uBox.z;
  let C = vec2<u32>(bitcast<u32>(u.uC.x), bitcast<u32>(u.uC.y));
  let x0 = fixmul(ix, C, 32u);
  let y0 = fixmul(iy, C, 32u);
  let hc = vec2<u32>(hcs_b[2 * i], hcs_b[2 * i + 1]);
  let h1 = hstep(H0, hc);
  let base = offs_b[i];
  for (var k = 0u; k < n; k++) {
    let hp = hstep(h1, vec2<u32>(0u, k));
    let px = coord_add(x0, u53f(u53(hp, 2u)) * u.uCm);
    let py = coord_add(y0, u53f(u53(hp, 3u)) * u.uCm);
    let o = 8u * (base + k);
    outP_b[o] = bitcast<u32>(px.x);
    outP_b[o + 1u] = bitcast<u32>(px.y);
    outP_b[o + 2u] = bitcast<u32>(py.x);
    outP_b[o + 3u] = bitcast<u32>(py.y);
    outP_b[o + 4u] = hp.x;
    outP_b[o + 5u] = hp.y;
    let off = pois(u.uTab.x, u.uTab.y, u53(hp, 5u));
    outP_b[o + 6u] = off;
    outP_b[o + 7u] = 0u;
    outO_b[base + k] = off;
  }
}
