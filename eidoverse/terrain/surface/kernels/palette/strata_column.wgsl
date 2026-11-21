// Port of numpy code of blender/eidoblend/terrain/surface/far_colour.py at d67f19e (_column), as a GPU kernel (the
// port's own, PORT_PLAN.md 3.2). strata_column: the strata column as one row of texels, COLUMN_TEXELS_PER_M: texel
// k holds the formation np.searchsorted(tops, z_k, side='right') finds at its centre z_k (clipped to the
// formations), its mean colour clipped to 0..0.95 and its roughness multiplier. The caller gives each formation's
// first texel whose centre is at or above its top (K_f, computed with numpy's double arithmetic for z_k), so the
// count of tops at or below z_k is the count of K_f at or below k: exact.
//! sampler formT   per formation f (texel (f, 0)): x K_f, y z w its mean colour (float32)
//! sampler roughT  per formation f: x its roughness multiplier
//! image   outC rgba32f
//! uniform int uN

fn kmain(p: vec2<i32>) {
  let n = outC_size();
  if (!inside(p, n)) { return; }
  var idx = 0;
  for (var f = 0; f < u.uN; f++) {
    if (f32(p.x) >= formT_at(vec2<i32>(f, 0)).x) { idx = idx + 1; }
  }
  idx = clamp(idx, 0, u.uN - 1);
  let c = formT_at(vec2<i32>(idx, 0));
  outC_store(p, vec4<f32>(clamp(c.yzw, vec3<f32>(0.0), vec3<f32>(0.95)), roughT_at(vec2<i32>(idx, 0)).x));
}
