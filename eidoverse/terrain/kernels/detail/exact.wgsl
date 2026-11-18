// Port of the `precise` lines of blender/eidoblend/terrain/kernels/pipes_water.glsl,
// blender/eidoblend/terrain/kernels/pipes_transport.glsl and blender/eidoblend/terrain/kernels/pipes_thermal.glsl
// at f90c6fc.
// exact.wgsl (`//! include detail/exact`): GLSL's `precise` for the pipe model's error-free steps, which WGSL has no
// qualifier for. The port's own file: the Blender kernels pipes_water.glsl, pipes_transport.glsl and
// pipes_thermal.glsl (at f90c6fc) mark a few lines `precise` so the compiler keeps each operation as written:
//   pipes_water      lowered = dl - e; took = dl - lowered          (and raised = dl + dep; gave = raised - dl): the
//                    sediment takes exactly what the rounded ground lost, so ground + sediment is conserved
//   pipes_transport  den_of and part: the sender and every receiver of one pipe's sediment compute it to the bit
//   pipes_thermal    dbc = db + ta.y; dl = c.x + dbc; carry = dbc - (dl - c.x): Kahan's compensation
// Written plainly in WGSL, this machine's shader compiler rewrites them algebraically (measured,
// tests/detail/kernels_test.mjs: carry = dbc - (dl - c.x) came out 0 on 65,531 of 65,531 sums whose carry is not 0;
// took = dl - (dl - e) was the ground's own loss on 2,035 of 15,628 eroding cells), which IEEE arithmetic forbids
// and which a `precise` qualifier would prevent. So each `precise` value is passed through exact(): its bits ORed
// with a zero the compiler cannot prove is zero (the top bit of a field's width, a uniform: no field is 2^31 cells
// wide). No rewrite can see through an integer operation on an unknown value, so the operation that made the value
// is computed as written, correctly rounded, and the next one starts from it; the value itself is unchanged.

/** A zero the compiler cannot prove is zero: bit 31 of a field's width (n is a <name>_size()). */
fn exact_zero(n: vec2<i32>) -> u32 { return u32(n.x) >> 31u; }

/** x, kept as computed: what `precise` gives a GLSL value (z is exact_zero's). */
fn exact(x: f32, z: u32) -> f32 { return bitcast<f32>(bitcast<u32>(x) | z); }
