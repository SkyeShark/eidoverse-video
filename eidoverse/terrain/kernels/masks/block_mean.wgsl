// Port of blender/eidoblend/terrain/masks.py at f90c6fc: window_grid's box average (np.pad mode 'edge' to whole
// blocks, then reshape(Ny, f, Nx, f).mean(axis=(1, 3))), of h - centre, as _blurred asks for it; also sky_view's
// observer on the coarse grid and rock_shadow's ground (centre 0). numpy averages in float64; here the block's cells
// are summed as differences from its first cell (row sums, then their sum), so float32 keeps the digits of the
// relief inside a block, not of the altitude. f = 1 is h - centre.
//! sampler src           the level's grid, ny x nx (its first channel)
//! image   outF r32f     ceil(ny / f) x ceil(nx / f)
//! uniform int uF
//! uniform float uCentre

fn kmain(p: vec2<i32>) {
  let n = outF_size();
  if (!inside(p, n)) { return; }
  let ns = src_size();
  let f = u.uF;
  let r0 = src_at(vec2<i32>(p.x * f, p.y * f)).x;
  if (f == 1) {
    outF_store(p, vec4<f32>(r0 - u.uCentre, 0.0, 0.0, 0.0));
    return;
  }
  var s = 0.0;
  for (var b = 0; b < f; b++) {
    let j = min(p.y * f + b, ns.y - 1);
    var r = 0.0;
    for (var a = 0; a < f; a++) {
      let i = min(p.x * f + a, ns.x - 1);
      r += src_at(vec2<i32>(i, j)).x - r0;
    }
    s += r;
  }
  outF_store(p, vec4<f32>((r0 - u.uCentre) + s / f32(f * f), 0.0, 0.0, 0.0));
}
