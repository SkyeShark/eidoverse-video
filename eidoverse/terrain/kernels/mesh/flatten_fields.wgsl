// flatten_fields: the exact flatten pass on one level, api.py flatten_fields and _flat_distance (blender/eidoblend/
// terrain at f90c6fc; design 4.13). Inside a flat area the ground is exactly its height; over `falloff` metres from
// its edge it blends back with a C1 smoothstep, w = 1 - t t (3 - 2 t), t = clip(d / falloff, 0, 1), d the distance
// from the area's edge: a disc (radius) or a rectangle (width, length, rotated by an angle about its centre);
// h = h (1 - w) + z w, and the bed is kept under it (bed = min(bed, h)).
//
// numpy decides in float64 which cells are inside (d <= 0) and which the falloff reaches (d <= falloff); a float32
// distance would move cells lying on those edges. So api.js finds, per row, the run of columns of each set with
// numpy's own expressions in doubles (the sets are convex: one run a row) and this kernel reads them: a cell inside
// is z to the bit, a cell beyond the falloff keeps h to the bit. Between them the blend is float32 (numpy's float64
// rounded once), with positions taken from the window's corner so no large coordinate enters.
//
// This kernel is the API's, kept with the mesh kernels: neither enters the cache's code hashes (PORT_PLAN.md C8),
// as api.py does not in Blender (the flatten areas themselves are in the key).
//! sampler h r32f        the level's heights
//! sampler bed r32f      its bed (any float field when uBed is 0)
//! sampler rows r32i     per row j four numbers: the first and last column inside the area, the first and last
//                        column the falloff reaches (first > last: none)
//! image   outH r32f     mode 0: the flattened heights; mode 1: 1 inside the area, else 0
//! image   outB r32f     mode 0 with uBed: min(bed, the flattened heights)
//! uniform int uMode
//! uniform int uBed
//! uniform vec4 uAt      the area's centre from the window's corner (x, y), the cosine and sine of its angle
//! uniform vec4 uShape   0 a disc or 1 a rectangle; the radius or half the width; half the length; the falloff
//! uniform float uCell
//! uniform float uZ      the area's height

fn kmain(p: vec2<i32>) {
  let n = outH_size();
  if (!inside(p, n)) { return; }
  let r0 = 4 * p.y;
  let hard = p.x >= rows_b[r0] && p.x <= rows_b[r0 + 1];
  if (u.uMode == 1) {
    var m = 0.0;
    if (hard) { m = 1.0; }
    outH_store(p, vec4<f32>(m, 0.0, 0.0, 0.0));
    return;
  }
  let h0 = h_b[p.y * n.x + p.x];
  var v = h0;
  if (hard) {
    v = u.uZ;
  } else if (p.x >= rows_b[r0 + 2] && p.x <= rows_b[r0 + 3]) {
    let q = (vec2<f32>(p) + 0.5) * u.uCell - u.uAt.xy;
    var d: f32;
    if (u.uShape.x > 0.5) {
      let a = q.x * u.uAt.z + q.y * u.uAt.w;
      let b = -q.x * u.uAt.w + q.y * u.uAt.z;
      let e = max(abs(vec2<f32>(a, b)) - u.uShape.yz, vec2<f32>(0.0, 0.0));
      d = sqrt(e.x * e.x + e.y * e.y);
    } else {
      d = max(sqrt(q.x * q.x + q.y * q.y) - u.uShape.y, 0.0);
    }
    let t = clamp(d / u.uShape.w, 0.0, 1.0);
    let w = 1.0 - t * t * (3.0 - 2.0 * t);
    v = h0 * (1.0 - w) + u.uZ * w;
  }
  outH_store(p, vec4<f32>(v, 0.0, 0.0, 0.0));
  if (u.uBed != 0) {
    outB_store(p, vec4<f32>(min(bed_b[p.y * n.x + p.x], v), 0.0, 0.0, 0.0));
  }
}
