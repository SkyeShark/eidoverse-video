// Port of numpy code of blender/eidoblend/terrain/surface/palette_bake.py at d67f19e (rock_colour), as a GPU kernel
// (the port's own, PORT_PLAN.md 3.2). rock_colour: the palette's bare-rock colour (linear) per cell at its
// stratigraphic height zs: z = zs + z_offset_m, plus each fault's throw x smoothstep across its width at the cell
// centre's world point; a repeating column wraps (z_lo + mod(z - z_lo, z_hi - z_lo)); the formation
// np.searchsorted(tops, z, side='right') finds there (clipped to the formations) gives the colour. Without a strata
// column (uN 0) every cell is uRock. In float32 (palette_bake.py: doubles); a cell within float32's rounding of a
// formation's top may take the formation beside it.
//! sampler zsT     the stratigraphic height of each cell (metres): the strata map, else the ground height
//! sampler formT   per formation f (texel (f, 0)): x its top, y z w its mean colour (linear, float32)
//! sampler faultT  per fault k: texel (k, 0) (x, y, nx, ny), texel (k, 1) (width, throw, 0, 0)
//! image   outC rgba32f
//! uniform vec4 uCol     (z_offset_m, z_lo, z_hi, repeat)
//! uniform vec3 uLevel   (x0, y0, cell) of the level, metres
//! uniform vec3 uRock    the rock layer's colour (uN 0)
//! uniform int uN
//! uniform int uFaults

fn kmain(p: vec2<i32>) {
  let n = outC_size();
  if (!inside(p, n)) { return; }
  if (u.uN == 0) {
    outC_store(p, vec4<f32>(u.uRock, 0.0));
    return;
  }
  var z = zsT_at(p).x + u.uCol.x;
  let x = u.uLevel.x + (f32(p.x) + 0.5) * u.uLevel.z;
  let y = u.uLevel.y + (f32(p.y) + 0.5) * u.uLevel.z;
  for (var k = 0; k < u.uFaults; k++) {
    let f = faultT_at(vec2<i32>(k, 0));
    let g = faultT_at(vec2<i32>(k, 1));
    let d = (x - f.x) * f.z + (y - f.y) * f.w;
    let t = clamp((d + 0.5 * g.x) / g.x, 0.0, 1.0);
    z = z + t * t * (3.0 - 2.0 * t) * g.y;
  }
  if (u.uCol.w > 0.5 && u.uCol.z > u.uCol.y) {
    let span = u.uCol.z - u.uCol.y;
    let r = z - u.uCol.y;
    z = u.uCol.y + (r - span * floor(r / span));
  }
  var idx = 0;
  for (var f = 0; f < u.uN; f++) {
    if (formT_at(vec2<i32>(f, 0)).x <= z) { idx = idx + 1; }
  }
  idx = clamp(idx, 0, u.uN - 1);
  outC_store(p, vec4<f32>(formT_at(vec2<i32>(idx, 0)).yzw, 0.0));
}
