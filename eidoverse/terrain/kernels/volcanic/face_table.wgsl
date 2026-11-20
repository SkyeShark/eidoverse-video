// Port of blender/eidoblend/terrain/solvers/volcanic.py _face_table's blend at f90c6fc: the layered face's sector
// profiles blended by azimuth, tabulated once per wall (721 azimuths x 4097 runs). numpy:
//     for k, (uk, zk) in enumerate(cols):
//         Z += w[:, None] * z[None, :];  S += w[:, None] * s[None, :];  W += w
//     Z / W[:, None], S / W[:, None]
// The sector profiles z_k(ut), s_k(ut) (np.interp and the segment slopes of each column, 1D) and the von Mises weights
// w_k(at), W(at) (1D) are solvers/volcanic.js's, in doubles; this kernel makes the 2D table, one texel per (azimuth,
// run), summing the sectors in numpy's order in float32. The port's own kernel.
//! sampler zs rg32f      the sectors' profiles: row k holds (z_k, s_k) at the 4097 runs
//! sampler ws r32f       the weights: row k holds w_k at the 721 azimuths; row n holds W
//! image   outZS rg32f   (Z, S): row j the azimuth at[j], column i the run ut[i]
//! uniform int uSectors

fn kmain(p: vec2<i32>) {
  let n = outZS_size();
  if (!inside(p, n)) { return; }
  var z = 0.0;
  var s = 0.0;
  for (var k = 0; k < u.uSectors; k++) {
    let w = ws_at(vec2<i32>(p.y, k)).x;
    let a = zs_at(vec2<i32>(p.x, k));
    z = z + w * a.x;
    s = s + w * a.y;
  }
  let W = ws_at(vec2<i32>(p.y, u.uSectors)).x;
  outZS_store(p, vec4<f32>(z / W, s / W, 0.0, 0.0));
}
