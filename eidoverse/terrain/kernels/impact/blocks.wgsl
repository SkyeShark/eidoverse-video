// Port of blender/eidoblend/terrain/solvers/impact.py boulders and op_crater_blocks' evaluate at f90c6fc: blocks lying
// on the ground on hashed lattices, as a gather. numpy loops over the lattice cells that could reach the evaluated
// points (IX from floor((x.min() - 0.75 s1) / L) to floor((x.max() + 0.75 s1) / L), the same for IY), draws each
// cell's block from its hash (present with probability density(cx, cy), its size from a power law, a rounded slab or
// a soft mound) and stamps it over its own footprint by a maximum. Here every point visits the cells near it (within
// the largest footprint), inside that same lattice range, and takes the maximum of the blocks that cover it: the same
// maximum. numpy's uniforms are hash / 2^32 in float64; here the hash is rounded to float32 first (a block whose test
// is a near-tie at 6e-8 can go the other way). The port's own kernel.
//   density(cx, cy) = dmax smoothstep(r0, r1, q) (1 - smoothstep(r2, r3, q)), q = r / (R plan(az)) about the crater
//   h = max(rock, soft); bed = rock; deposit = max(soft - rock, 0)   (slab sets are rock, mound sets sediment)
//! include volcanic/math
//! include volcanic/az
//! include volcanic/noise
//! sampler azt r32f      the crater's planform tables (polygon, radius noise)
//! sampler stab          the sets, four texels each (impact.js blockTexels):
//                          0 (L, s0, s1, exponent)    1 (tail, height_frac lo, hi, mound 1|0)
//                          2 (dmax, r0, r1, r2)       3 (r3, seed bits, the lattice's first IX, first IY)
//                          4 (last IX, last IY, (ox - L IXb), (oy - L IYb))   5 (IXb, IYb, L IXb - cx, L IYb - cy)
//! sampler prm           (R, polygon 1|0, radius_noise, 0), (polygon row, noise row, sets, 0)
//! image   outH r32f
//! image   outB r32f
//! image   outD r32f
//! uniform float uStep

fn unit_of(h: u32, k: u32) -> f32 {
  return f32(pcg(h ^ (0x9E3779B9u * (k + 1u)))) * (1.0 / 4294967296.0);
}

fn kmain(p: vec2<i32>) {
  if (!inside(p, outH_size())) { return; }
  let g0 = prm_at(vec2<i32>(0, 0));
  let g1 = prm_at(vec2<i32>(1, 0));
  let nsets = i32(g1.z);
  var rock = 0.0;
  var soft = 0.0;
  for (var si = 0; si < nsets; si++) {
    let a = stab_at(vec2<i32>(6 * si, 0));
    let b = stab_at(vec2<i32>(6 * si + 1, 0));
    let c = stab_at(vec2<i32>(6 * si + 2, 0));
    let e = stab_at(vec2<i32>(6 * si + 3, 0));
    let f = stab_at(vec2<i32>(6 * si + 4, 0));
    let gb = stab_at(vec2<i32>(6 * si + 5, 0));
    let L = a.x;
    let mound = b.w != 0.0;
    let seed = bitcast<u32>(e.y);
    let rmax = select(0.72, 1.1, mound) * a.z;
    // this point from the lattice origin IXb, IYb (metres)
    let px = f.z + (f32(p.x) + 0.5) * u.uStep;
    let py = f.w + (f32(p.y) + 0.5) * u.uStep;
    let K = i32(ceil(rmax / L)) + 1;
    let ix0 = i32(floor(px / L));
    let iy0 = i32(floor(py / L));
    var out = 0.0;
    for (var dj = -K; dj <= K; dj++) {
      for (var di = -K; di <= K; di++) {
        let lx = ix0 + di;
        let ly = iy0 + dj;
        let IX = i32(gb.x) + lx;
        let IY = i32(gb.y) + ly;
        if (IX < i32(e.z) || IX > i32(f.x) || IY < i32(e.w) || IY > i32(f.y)) { continue; }
        let h = lattice_hash(IX, IY, seed);
        let ux = 0.1 + 0.8 * unit_of(h, 0u);
        let uy = 0.1 + 0.8 * unit_of(h, 1u);
        // the block's centre from the crater's centre, for its density
        let qc = vec2<f32>(gb.z + (f32(lx) + ux) * L, gb.w + (f32(ly) + uy) * L);
        let rq = length(qc);
        let sq = az_sampler(v_az(qc));
        var plan = 1.0;
        if (g0.y != 0.0) { plan = az_read(i32(g1.x), sq); }
        if (g0.z != 0.0) { plan = plan * (1.0 + g0.z * az_read(i32(g1.y), sq)); }
        let q = rq / (g0.x * plan);
        let dens = c.x * v_smoothstep(c.y, c.z, q) * (1.0 - v_smoothstep(c.w, e.x, q));
        if (!(unit_of(h, 2u) < dens)) { continue; }
        let size = a.y * pow(1.0 - unit_of(h, 3u) * b.x, -1.0 / a.w);
        let th = unit_of(h, 4u) * VPI;
        let asp = 0.55 + 0.45 * unit_of(h, 5u);
        let top = size * (b.y + (b.z - b.y) * unit_of(h, 6u));
        let rad = select(0.72, 1.1, mound) * size;
        let dx = px - (f32(lx) + ux) * L;
        let dy = py - (f32(ly) + uy) * L;
        if (!(abs(dx) <= rad && abs(dy) <= rad)) { continue; }
        let cs = cos(th);
        let sn = sin(th);
        let du = (dx * cs + dy * sn) / (0.5 * size);
        let dv = (dy * cs - dx * sn) / (0.5 * size * asp);
        var z: f32;
        if (mound) {
          let d2 = du * du + dv * dv;
          z = top * max(exp(-2.5 * d2) - 0.02, 0.0) / 0.98;
        } else {
          let d4 = du * du * du * du + dv * dv * dv * dv;
          var pw = 0.0;
          if (d4 > 0.0) { pw = pow(d4, 0.6); }
          z = top * sqrt(max(1.0 - pw, 0.0));
        }
        out = max(out, z);
      }
    }
    if (mound) { soft = max(soft, out); } else { rock = max(rock, out); }
  }
  outH_store(p, vec4<f32>(max(rock, soft), 0.0, 0.0, 0.0));
  outB_store(p, vec4<f32>(rock, 0.0, 0.0, 0.0));
  outD_store(p, vec4<f32>(max(soft - rock, 0.0), 0.0, 0.0, 0.0));
}
