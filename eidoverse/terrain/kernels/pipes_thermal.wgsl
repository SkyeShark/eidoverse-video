// Port of blender/eidoblend/terrain/kernels/pipes_thermal.glsl at f90c6fc.
//
// Transcribed statement for statement from the GLSL (PORT_PLAN.md 4.2); the `//!` header is the GLSL's, unchanged
// (its one block-comment line among the declarations included). The changes are WGSL's: texelFetch is <name>_at(q),
// imageStore is outS_store / outT_store, textureSize is st_size(), uniforms are u.<name>, neighbour()'s `out`
// argument is a pointer, and `?:` is select() (both arms are plain values here, so evaluating both changes nothing).
//
// `precise`, which WGSL does not have (the one change that is not a spelling). The GLSL marks the Kahan step
// `dbc = db + ta.y; dl = c.x + dbc; carry = dbc - (dl - c.x)` precise, so the compiler cannot fold carry to 0.
// Written plainly, this machine's compiler folds it (measured, tests/detail/kernels_test.mjs: carry came out 0 on
// 65,531 of 65,531 sums whose carry is not 0), so each precise value goes through exact() (`//! include
// detail/exact`: an identity the compiler cannot see through, kernels/detail/exact.wgsl), which keeps the lines as
// written; the kernel test checks the carry in this kernel cell by cell. The pair exchange itself is symmetric to
// the bit whatever the compiler does with it: both cells of a pair evaluate the same expression of the same values
// (a + b == b + a, a - b == -(b - a) in IEEE arithmetic).
/* pipes_thermal: the thermal pass of the virtual-pipe model (design sections 4.4 step 8, 4.2 and 4.12): threshold
   failure through 8 pipes, mass-conserving, for two materials. Its numpy twin is solvers/hydraulic.py
   `pipes_thermal`. Cell units (heights / cell, so a threshold is a tangent and a pipe is LEN[k] long), the ground as
   base + delta (see pipes_flux.glsl).

   For each neighbour pair (this cell c and q) the higher cell sheds toward the lower one
       moved = uRate * max(e_rock, e_loose)
       e_rock  = min(max(|dh| - Sc_pair * LEN[k], 0),       Sc_pair: the mean of the two cells' thresholds; the
                     delta_hi - floor_hi)                   higher cell's floor (par.z) bounds how deep its cohesive
                                                            ground fails, so a failure stays a local scar instead of
                                                            retreating up a whole wall
       e_loose = min(max(|dh| - R_pair * LEN[k], 0), t_hi)  R_pair: the mean repose; t_hi: the higher cell's loose
                                                            cover (ground - bed): debris slides at repose, the
                                                            cohesive ground only above its own threshold (rock
                                                            breakup's noisy one)
   The exchange depends only on the pair, so what c loses q gains: the total is conserved (the design's threshold
   pass, with the repose rule of section 4.2 on loose material). `bed` is the top of the cohesive ground (rock, or
   soil in place): what fails becomes loose debris where it lands (bed stays below it). outT.x accumulates each cell's
   net change by sliding (signed; its positive part is the talus thickness). uRate <= 1/8 keeps every cell from
   shedding more than its excess. Water and sediment pass through. PINNED mode holds the ground to its pin.
   Float32: an exchange of 1e-7 cells added to a change of several cells is partly rounded away, and over thousands
   of passes that loses mass systematically (measured: 4e-6 of the material moved; 1e-11 in float64). outT.y carries
   what the rounding dropped into the next pass (Kahan's compensation), so it is not lost. */
//! sampler st          x: delta (ground - base), y: d water, z: s sediment, w: bed - base
//! sampler base        x: b0 (cell units)
//! sampler par         x: threshold of the cohesive ground (tangent), y: repose of debris (tangent), z: failure floor
/*                      (par.z: the delta, cell units, the cohesive ground may fail down to; -1e6 for none) */
//! sampler pin         x: pin_w (0..1), y: pin_h - base (cell units)
//! sampler tacc        x: net change by sliding so far (cell units), y: the rounding carried from the last pass
//! image   outS rgba32f
//! image   outT rgba32f
//! uniform float uRate
//! uniform int uBound
//! include detail/exact
fn kmain(p: vec2<i32>) {
  let n = st_size();
  if (!inside(p, n)) { return; }
  let c = st_at(p);
  let b0 = base_at(p).x;
  let pc = par_at(p);
  let tc = max(c.x - c.w, 0.0);
  var db = 0.0;
  for (var k = 0; k < 8; k++) {
    var q: vec2<i32>;
    if (!neighbour(p, k, n, u.uBound, &q)) { continue; }
    let cq = st_at(q);
    let pq = par_at(q);
    let dh = (b0 - base_at(q).x) + (c.x - cq.x);
    let adh = abs(dh);
    let t_hi = select(max(cq.x - cq.w, 0.0), tc, dh > 0.0);
    let room = select(max(cq.x - pq.z, 0.0), max(c.x - pc.z, 0.0), dh > 0.0);
    let e_rock = min(max(adh - 0.5 * (pc.x + pq.x) * LEN[k], 0.0), room);
    let e_loose = min(max(adh - 0.5 * (pc.y + pq.y) * LEN[k], 0.0), t_hi);
    let m = u.uRate * max(e_rock, e_loose);
    db += select(m, -m, dh > 0.0);
  }
  let ta = tacc_at(p);
  /* `precise` in the GLSL: without it the compiler may fold dbc - ((x + dbc) - x) to 0 and drop the compensation
     (GLSL allows such rewrites; the GPU's drift was unchanged until these were marked). exact(): this file's header */
  let z = exact_zero(n);
  let dbc = exact(db + ta.y, z);
  var dl = exact(c.x + dbc, z);
  let carry = exact(dbc - exact(dl - c.x, z), z);
  var bed = min(c.w, dl);
  if (u.uBound == BOUND_PINNED) {
    let pn = pin_at(p);
    dl = pin_apply(dl, pn.x, pn.y);
    bed = min(bed, dl);
  }
  outS_store(p, vec4<f32>(dl, c.y, c.z, bed));
  outT_store(p, vec4<f32>(ta.x + db, carry, 0.0, 0.0));
}
