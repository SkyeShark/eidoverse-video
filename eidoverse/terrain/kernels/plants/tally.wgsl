// plants/tally: the counts plants.py's stats sum ((flags & mask) == mask, for up to eight masks) and the largest of
// a non-negative value over the items whose flags hold uMaxMask (st['density_max']: dens[drawn].max(), a float's bits
// in the order of non-negative floats). Exact integers, any order: workgroup atomics, then one global atomic each.
//! include plants/lib
//! sampler flags r32ui   per item: its flags
//! sampler vals r32f     per item: the value
//! image   outT atomic_u32  9 numbers: the eight counts, then the largest value's bits
//! uniform ivec4 uM0     masks 0-3 (0: unused)
//! uniform ivec4 uM1     masks 4-7
//! uniform int   uMaxMask
//! uniform int   uCount

var<workgroup> wt: array<atomic<u32>, 9>;

fn kmain(p: vec2<i32>) {
  let l = (p.x & 15) + 16 * (p.y & 15);
  if (l < 9) { atomicStore(&wt[l], 0u); }
  workgroupBarrier();
  let i = lin(p);
  if (i < u.uCount) {
    let f = flags_b[i];
    var m = array<u32, 8>(bitcast<u32>(u.uM0.x), bitcast<u32>(u.uM0.y), bitcast<u32>(u.uM0.z), bitcast<u32>(u.uM0.w),
                          bitcast<u32>(u.uM1.x), bitcast<u32>(u.uM1.y), bitcast<u32>(u.uM1.z), bitcast<u32>(u.uM1.w));
    for (var k = 0; k < 8; k++) {
      if (m[k] != 0u && (f & m[k]) == m[k]) { atomicAdd(&wt[k], 1u); }
    }
    let mm = bitcast<u32>(u.uMaxMask);
    if (mm != 0u && (f & mm) == mm) { atomicMax(&wt[8], bitcast<u32>(max(vals_b[i], 0.0))); }
  }
  workgroupBarrier();
  if (l < 8) {
    let v = atomicLoad(&wt[l]);
    if (v != 0u) { atomicAdd(&outT_b[l], v); }
  } else if (l == 8) {
    atomicMax(&outT_b[8], atomicLoad(&wt[8]));
  }
}
