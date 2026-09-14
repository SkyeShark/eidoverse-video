import * as THREE from "three/webgpu";
// Local joint matrices retain the actual modular chain and reflected handedness.
export async function createRunningController(gltf, quadruped, dataURL = null) {
  const data = dataURL;
  const nodes = new Map();
  gltf.scene.traverse((o) => {
    const a = gltf.parser.associations.get(o);
    if (a?.nodes !== undefined) {
      nodes.set(gltf.parser.json.nodes[a.nodes].name, o);
    }
  });
  const convert = new THREE.Matrix4().makeRotationX(-Math.PI / 2),
    inverse = convert.clone().invert(),
    rest = new Map();
  for (const [name, rows] of Object.entries(data.rest_matrices)) {
    if (nodes.has(name)) {
      rest.set(name, new THREE.Matrix4().fromArray(rows.flat()).transpose());
    }
  }
  const original = new Map(
    [...nodes].map((
      [n, o],
    ) => [n, {
      position: o.position.clone(),
      quaternion: o.quaternion.clone(),
      scale: o.scale.clone(),
    }]),
  );
  const report = {
    root_frames: Object.fromEntries(
      Object.entries(data.joint_axes_blender).map(([n, axis]) => [n, { axis }]),
    ),
  };
  const axes = new Map(
    Object.entries(report.root_frames).map((
      [n, r],
    ) => [n, new THREE.Vector3(...r.axis).normalize()]),
  );
  for (const name of Object.keys(data.clips.circle.frames[0].joints)) {
    if (!nodes.has(name)) throw Error("Missing gait joint " + name);
  }
  if (!nodes.has(data.root)) throw Error("Missing locomotion root");
  function frame(clip, time) {
    const c = data.clips[clip],
      fs = c.frames,
      u = THREE.MathUtils.clamp(time / c.duration, 0, 1) * (fs.length - 1),
      i = Math.min(fs.length - 2, Math.floor(u)),
      a = fs[i],
      b = fs[i + 1],
      w = u - i;
    return {
      time,
      base: a.base.map((v, k) => THREE.MathUtils.lerp(v, b.base[k], w)),
      yaw: THREE.MathUtils.lerp(a.yaw, b.yaw, w),
      pitch: THREE.MathUtils.lerp(a.pitch ?? 0, b.pitch ?? 0, w),
      joints: Object.fromEntries(
        Object.entries(a.joints).map((
          [n, v],
        ) => [n, THREE.MathUtils.lerp(v, b.joints[n], w)]),
      ),
    };
  }
  function apply(clip, time) {
    const f = frame(clip, time);
    for (const [name, m] of rest) {
      const o = nodes.get(name), local = m.clone();
      if (name in f.joints) {
        local.multiply(
          new THREE.Matrix4().makeRotationAxis(axes.get(name), f.joints[name]),
        );
      }
      if (name === data.root) {
        const pivot = data.root_pivot ?? [0, 0, 0];
        local.premultiply(
          new THREE.Matrix4().makeTranslation(...pivot.map((v) => -v)),
        ).premultiply(new THREE.Matrix4().makeRotationX(f.pitch)).premultiply(
          new THREE.Matrix4().makeTranslation(...pivot),
        ).premultiply(new THREE.Matrix4().makeRotationZ(f.yaw)).premultiply(
          new THREE.Matrix4().makeTranslation(...f.base),
        );
      }
      local.premultiply(convert).multiply(inverse);
      local.decompose(o.position, o.quaternion, o.scale);
      o.updateMatrix();
    }
    gltf.scene.updateMatrixWorld(true);
    return f;
  }
  function restore() {
    for (const [n, s] of original) {
      const o = nodes.get(n);
      o.position.copy(s.position);
      o.quaternion.copy(s.quaternion);
      o.scale.copy(s.scale);
      o.updateMatrix();
    }
    gltf.scene.updateMatrixWorld(true);
  }
  function bounds(clip) {
    const box = new THREE.Box3();
    for (const f of data.clips[clip].frames) {
      box.expandByPoint(new THREE.Vector3(f.base[0], f.base[2], -f.base[1]));
    }
    box.min.add(new THREE.Vector3(-.5, 0, -.5));
    box.max.add(new THREE.Vector3(.5, quadruped ? .9 : 1.65, .5));
    return box;
  }
  return {
    data,
    nodes,
    apply,
    restore,
    frame,
    bounds,
    duration: (clip) => data.clips[clip].duration,
  };
}
