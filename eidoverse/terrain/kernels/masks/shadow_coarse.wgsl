// Port of blender/eidoblend/terrain/masks.py at f90c6fc: rock_shadow's box reduction by f for its far march: the
// rock feet's highest height in each block (np.fmax.reduce of zr padded with NaN: NOH where the block has no foot)
// and the ground's mean (h padded by 'edge', reshape(...).mean: numpy float64; here differences from the block's first
// cell summed in float32, as masks/block_mean.wgsl).
//! include masks/lib
//! sampler zr            h on a rock foot, NOH elsewhere
//! sampler h
//! image   outZ r32f     Ny x Nx
//! image   outH r32f     Ny x Nx
//! uniform int uF

fn kmain(p: vec2<i32>) {
  let n = outZ_size();
  if (!inside(p, n)) { return; }
  let ns = h_size();
  let f = u.uF;
  var z = NOH;
  let r0 = h_at(vec2<i32>(p.x * f, p.y * f)).x;
  var s = 0.0;
  for (var b = 0; b < f; b++) {
    let jj = p.y * f + b;
    let j = min(jj, ns.y - 1);
    var r = 0.0;
    for (var a = 0; a < f; a++) {
      let ii = p.x * f + a;
      let i = min(ii, ns.x - 1);
      if (ii < ns.x && jj < ns.y) { z = max(z, zr_at(vec2<i32>(ii, jj)).x); }
      r += h_at(vec2<i32>(i, j)).x - r0;
    }
    s += r;
  }
  outZ_store(p, vec4<f32>(z, 0.0, 0.0, 0.0));
  outH_store(p, vec4<f32>(select(r0 + s / f32(f * f), r0, f == 1), 0.0, 0.0, 0.0));
}
