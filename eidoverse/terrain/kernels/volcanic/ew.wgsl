// The element-wise numpy expressions of blender/eidoblend/terrain/solvers/volcanic.py and impact.py at f90c6fc that
// join the shapes to a level's fields, cell by cell (the port's own kernel; each mode names its numpy line). a, b, c
// are float fields (1 x 1 stand-ins where a mode does not read them); k0, k1 numbers in doubles rounded once.
//   0  a + b                                   fields[k] + v (stamp_add), h + fill
//   1  a - b                                   here - upsampled parent (stamp_add), h - cut
//   2  max(a - b, 0)                           cinder = np.maximum(out - z, 0)
//   3  a - max(a - b, 0)                       bed = height - cinder
//   4  min(a, b)                               np.minimum(bed, h)
//   5  max(a, b)                               np.maximum(talus, ...)
//   6  a - b - c - d (d = k0 x 0 + c2)         impact: delta - ejecta - fill - talus (c2: the talus, field d)
//   7  isfinite(a) ? max(a, k0) : k1           Sc = where(isfinite(s), maximum(s, tan(lo)), tan(hi))
//   8  max(a - b, k0)                          np.maximum(fill - cut, 0) and the like
//   9  k0 (a constant)                         np.full(shape, k0)
//  10  a x b                                   products of fields
//  11  k0 + (k1 - k0) b                        K_factor = pk + (1 - pk) smoothstep(...) (b the smoothstep)
//  12  clip(a, k0, k1)
//  13  a + k0 b                                h + amp x tx
//! sampler a
//! sampler b
//! sampler c
//! sampler d
//! image   outF r32f
//! uniform int uMode
//! uniform float uK0
//! uniform float uK1

fn kmain(p: vec2<i32>) {
  let n = outF_size();
  if (!inside(p, n)) { return; }
  let x = a_at(select(p, vec2<i32>(0, 0), a_size().x == 1 && n.x != 1)).x;
  let y = b_at(select(p, vec2<i32>(0, 0), b_size().x == 1 && n.x != 1)).x;
  let z = c_at(select(p, vec2<i32>(0, 0), c_size().x == 1 && n.x != 1)).x;
  let w = d_at(select(p, vec2<i32>(0, 0), d_size().x == 1 && n.x != 1)).x;
  var v: f32;
  switch u.uMode {
    case 0: { v = x + y; }
    case 1: { v = x - y; }
    case 2: { v = max(x - y, 0.0); }
    case 3: { v = x - max(x - y, 0.0); }
    case 4: { v = min(x, y); }
    case 5: { v = max(x, y); }
    case 6: { v = x - y - z - w; }
    case 7: {
      let fin = (bitcast<u32>(x) & 0x7F800000u) != 0x7F800000u;
      v = select(u.uK1, max(x, u.uK0), fin);
    }
    case 8: { v = max(x - y, u.uK0); }
    case 9: { v = u.uK0; }
    case 10: { v = x * y; }
    case 11: { v = u.uK0 + (u.uK1 - u.uK0) * y; }
    case 12: { v = clamp(x, u.uK0, u.uK1); }
    case 13: { v = x + u.uK0 * y; }
    default: { v = x; }
  }
  outF_store(p, vec4<f32>(v, 0.0, 0.0, 0.0));
}
