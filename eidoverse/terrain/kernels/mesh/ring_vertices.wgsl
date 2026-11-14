// ring_vertices: one ring's own vertices into the mesh's position and uv buffers, build/mesh.py _assemble
// (blender/eidoblend/terrain at f90c6fc): verts[idx] = (xm[i], ym[j], Z[j, i]) for the lattice points the ring adds,
// in three.js axes (x, z, -y) (PORT_PLAN.md 2.2: a rotation, so the triangles keep their winding). xm and ym are the
// lattice lines in metres as Blender writes them, float32(origin + lattice * unit) made in JavaScript doubles
// (build/mesh.js), so x and z are bit-equal to Blender's; only the negation is done here (exact). The uv is
// make_object's 'UVMap' in world metres, u = x, v = y (north). The heights' range (for the geometry's bounding
// volumes, so nothing walks the vertices on the CPU) is kept by integer atomics on order-preserving keys: exact and
// the same whatever the order.
//! include prims/lib
//! sampler zg r32f       this ring's heights grid, ny x nx
//! sampler ig r32ui      this ring's vertex numbers (ring_index)
//! sampler lines r32f    the rings' lattice lines in metres (build/mesh.js LINES layout); this ring's at uDims.w
//! image   outP r32f     positions, 3 numbers a vertex
//! image   outU r32f     uv, 2 numbers a vertex
//! image   outB atomic_u32  [the largest ~key, the largest key] of the heights written
//! uniform ivec4 uDims   nx, ny, v0, this ring's first line entry (xm[nx] then ym[ny])

var<workgroup> wlo: atomic<u32>;
var<workgroup> whi: atomic<u32>;

fn kmain(p: vec2<i32>) {
  let nx = u.uDims.x;
  let ny = u.uDims.y;
  var key = 0u;
  var have = false;
  if (p.x < nx && p.y < ny) {
    let v = ig_b[p.y * nx + p.x];
    if (v != NONE && v >= u32(u.uDims.z)) {
      let x = lines_b[u.uDims.w + p.x];
      let y = lines_b[u.uDims.w + nx + p.y];
      let z = zg_b[p.y * nx + p.x];
      outP_b[3u * v] = x;
      outP_b[3u * v + 1u] = z;
      outP_b[3u * v + 2u] = -y;
      outU_b[2u * v] = x;
      outU_b[2u * v + 1u] = y;
      key = fkey(z);
      have = true;
    }
  }
  if (have) {
    atomicMax(&wlo, ~key);
    atomicMax(&whi, key);
  }
  workgroupBarrier();
  if ((p.x & 15) == 0 && (p.y & 15) == 0) {
    atomicMax(&outB_b[0], atomicLoad(&wlo));
    atomicMax(&outB_b[1], atomicLoad(&whi));
  }
}
