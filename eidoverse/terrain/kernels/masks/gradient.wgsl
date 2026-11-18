// Port of blender/eidoblend/terrain/masks.py at f90c6fc: gradient (central differences at the kept cells of a
// padded array: p = (h[i + 1] - h[i - 1]) (0.5 / cell) east, q the same north), as compute and _slope_tan use it
// (numpy's float64 differences, then float32), with compute's g = hypot(p, q) and slope = arctan(g) (180 / pi)
// (float32). The padded grid is padLevel's (tap, offset) pairs (rg32f) or plain values (r32f: offset 0): the
// difference of the taps is exact beside each other (Sterbenz) and the offsets are added to it, so p keeps numpy's
// float64 digits to an ulp of the slope even across a level's edge, where the outside value is a sum of parent taps.
//! sampler hp            the padded height, margin uM
//! image   outG rgba32f  ny x nx: (p, q, g, slope in degrees)
//! uniform int uM
//! uniform float uK      float32(0.5 / cell)

fn hv(q: vec2<i32>) -> vec2<f32> { return hp_at(q).xy; }

fn kmain(p: vec2<i32>) {
  let n = outG_size();
  if (!inside(p, n)) { return; }
  let c = p + vec2<i32>(u.uM, u.uM);
  let e = hv(c + vec2<i32>(1, 0));
  let w = hv(c - vec2<i32>(1, 0));
  let no = hv(c + vec2<i32>(0, 1));
  let so = hv(c - vec2<i32>(0, 1));
  let gx = ((e.x - w.x) + (e.y - w.y)) * u.uK;
  let gy = ((no.x - so.x) + (no.y - so.y)) * u.uK;
  let g = sqrt(gx * gx + gy * gy);
  let slope = atan(g) * 57.29577951308232;
  outG_store(p, vec4<f32>(gx, gy, g, slope));
}
