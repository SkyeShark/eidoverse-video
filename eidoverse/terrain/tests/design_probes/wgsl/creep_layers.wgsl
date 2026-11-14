// creep_layers: the inline kernel CREEP_LAYERS of blender/eidoblend/terrain/solvers/fluvial.py in WGSL
//! sampler st   x: h after creep
//! sampler h0   x: h before creep
//! sampler mk   x: wear, y: deposit, z: talus, w: loose thickness (m)
//! image   outM rgba32f

fn kmain(p: vec2<i32>) {
  let n = st_size();
  if (!inside(p, n)) { return; }
  var m = mk_at(p);
  let d = st_at(p).x - h0_at(p).x;
  if (d >= 0.0) {
    m.w += d;
  } else {
    var q = -d;
    let other = max(m.w - m.y - m.z, 0.0);
    var a = min(q, m.y);
    m.y -= a;
    q -= a;
    a = min(q, m.z);
    m.z -= a;
    q -= a;
    q -= min(q, other);
    m.w = max(m.w - (-d - q), 0.0);
    m.x += q;
  }
  outM_store(p, m);
}
