// hash_probe: common.wgsl's PCG chain and u01, and Ekigar's lattice hash, on every cell of a grid, for the bit-exact
// comparison with the numpy twins (make_twin_fixtures.py writes the same arrays from core/twins.py and
// core/world_noise.hash2)
//! sampler dummy
//! image   outPcg r32ui
//! image   outPcg2 r32ui
//! image   outPcg3 r32ui
//! image   outCell r32ui
//! image   outU01 r32f
//! image   outGrad rg32f
//! image   outH2 r32ui

fn eido_hash2_u32(ix: i32, iy: i32) -> u32 {
  let wx = u32(ix + 8388608);
  let wy = u32(iy + 8388608);
  var h = (wx * 0x27d4eb2du) ^ (wy * 0x85ebca6bu);
  h ^= h >> 15u;
  h *= 0x2c1b3c6du;
  h ^= h >> 13u;
  h *= 0x297a2d39u;
  h ^= h >> 16u;
  return h;
}

fn eido_hash2(ix: i32, iy: i32) -> vec2<f32> {
  let h = eido_hash2_u32(ix, iy);
  return vec2<f32>(f32(h & 0xFFFFu), f32(h >> 16u)) * (1.0 / 32767.5) - 1.0;
}

fn kmain(p: vec2<i32>) {
  let n = outPcg_size();
  if (!inside(p, n)) { return; }
  let i = u32(p.x);
  let j = u32(p.y);
  outPcg_store(p, pcg(i * 7919u + j * 104729u + 12345u));
  outPcg2_store(p, pcg2(i, j));
  outPcg3_store(p, pcg3(i, j, 77u));
  outCell_store(p, cell_hash(p, 3, 11));
  outU01_store(p, vec4<f32>(u01(pcg2(i, j)), 0.0, 0.0, 0.0));
  outGrad_store(p, vec4<f32>(eido_hash2(p.x - 48 - 2097152, p.y - 40 + 1000003), 0.0, 0.0));
  outH2_store(p, eido_hash2_u32(p.x - 48 - 2097152, p.y - 40 + 1000003));
}
