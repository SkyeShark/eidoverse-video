// plants/dist_rows: the first pass of plants.py _distance_to (blender/eidoblend/terrain/build/plants.py at f9fba8c),
// one invocation per row: each cell's distance along its row to the row's nearest seed (np.maximum.accumulate of
// the seeds' indices from the left, np.minimum.accumulate from the right), capped at R + 1 cells, squared: exact
// integers in float32.
//! include prims/lib
//! sampler seed r32ui
//! image   outG r32f     per cell: (the row distance in cells)^2
//! uniform int uR        ceil(cap / cell)

fn kmain(p: vec2<i32>) {
  let n = seed_size();
  let j = line_index(p);
  if (j >= n.y) { return; }
  let far = n.x + u.uR + 2;
  var left = -far;
  for (var i = 0; i < n.x; i++) {
    if (seed_at(vec2<i32>(i, j)) != 0u) { left = i; }
    outG_store(vec2<i32>(i, j), vec4<f32>(f32(i - left), 0.0, 0.0, 0.0));
  }
  var right = 2 * far;
  for (var i = n.x - 1; i >= 0; i--) {
    if (seed_at(vec2<i32>(i, j)) != 0u) { right = i; }
    let dl = i32(outG_load(vec2<i32>(i, j)).x);
    let dx = f32(min(min(dl, right - i), u.uR + 1));
    outG_store(vec2<i32>(i, j), vec4<f32>(dx * dx, 0.0, 0.0, 0.0));
  }
}
