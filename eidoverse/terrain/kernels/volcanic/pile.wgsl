// Port of blender/eidoblend/terrain/solvers/volcanic.py piles_on's join (and add_on_support with combine=np.maximum)
// at f90c6fc: one cone joined to the surface over its support, in place. numpy:
//     p = b + aged_cinder_cone(xs, ys, kt, **c)
//     out[sl] = smooth_max(out[sl], p, k) if smooth else np.maximum(out[sl], p)
// over the support slices sl (rows and columns of the grid within rb of the vent, numpy's searchsorted bounds, found
// in doubles by solvers/volcanic.js and given as uRect), or over the masked points |x - at| < rb and |y - at| < rb
// when the grid has fewer than two rows (support_slices gives None: uMode + 2, uRb). The port's own kernel; the cone
// is kernels/volcanic/cone.wgsl's.
//! include volcanic/math
//! include volcanic/az
//! include volcanic/cone
//! sampler azt r32f      the azimuth tables (the cone's outline noise)
//! sampler ctab          the cone (eight texels, cone.wgsl)
//! sampler patch r32f    an aged cone's patch (a stand-in for a fresh cone)
//! image   outH r32f     the surface, joined in place
//! uniform ivec4 uRect   the cells joined: columns [x, z), rows [y, w)
//! uniform float uStep   the grid's spacing, metres
//! uniform float uBase   b: the cone's base height (0: add_on_support's maximum)
//! uniform float uK      the smooth maximum's width (toe_frac x H)
//! uniform int uMode     0 smooth maximum, 1 plain maximum; + 2: the masked points (|dx| < uRb and |dy| < uRb)
//! uniform float uRb

fn kmain(p: vec2<i32>) {
  let q = p + u.uRect.xy;
  if (q.x >= u.uRect.z || q.y >= u.uRect.w) { return; }
  if (!inside(q, outH_size())) { return; }
  let k = cone_read(0);
  if (u.uMode >= 2) {
    let d = k.h.xy + (vec2<f32>(q) + 0.5) * u.uStep;
    if (!(abs(d.x) < u.uRb && abs(d.y) < u.uRb)) { return; }
  }
  let g = outH_load(q).x;
  let pv = u.uBase + cone_at_grid(q, u.uStep, k);
  var o: f32;
  if ((u.uMode & 1) == 0) { o = v_smooth_max(g, pv, u.uK); } else { o = max(g, pv); }
  outH_store(q, vec4<f32>(o, 0.0, 0.0, 0.0));
}
