// Eidoverse modular robotics, MIT. Public coordinates: metres, radians, +Y up.
import * as T from "three/webgpu";
import { GLTFLoader } from "npm:three@0.184.0/addons/loaders/GLTFLoader.js";
import { clone as cloneSkeleton } from "npm:three@0.184.0/addons/utils/SkeletonUtils.js";
import { bytes, cacheStats, json, texturePlugin } from "./io.js";
import { prepareMaterials } from "./materials.js";
import { installMotion } from "./motion.js";
import { installFilament } from "./filament.js";
export { createPTFETube, serviceLoop } from "./filament.js";
export const assetRoot = new URL("../assets/robotics/", import.meta.url);
export const vector = ([x, y, z]) => new T.Vector3(x, z, -y);
export const toAuthoring = ([x, y, z]) => [x, -z, y];
const templates = new Map();
export async function catalog() {
  return json(new URL("catalog.json", assetRoot));
}
function snapshot(root) {
  const a = new Map();
  root.traverse((o) =>
    a.set(o, {
      position: o.position.clone(),
      quaternion: o.quaternion.clone(),
      scale: o.scale.clone(),
    })
  );
  return a;
}
function reset(a) {
  for (const [o, r] of a) {
    o.position.copy(r.position);
    o.quaternion.copy(r.quaternion);
    o.scale.copy(r.scale);
    o.updateMatrix();
  }
}
function jointSpecs(scene, report) {
  const roots = {}, counts = new Map();
  scene.traverse((o) => {
    const id = o.userData.module_id;
    if (id) counts.set(id, (counts.get(id) ?? 0) + 1);
  });
  scene.traverse((o) => {
    const id = o.userData.module_id;
    if (!id) return;
    const name = counts.get(id) > 1 ? (o.userData.name ?? o.name) : id;
    if (roots[name]) throw Error("Ambiguous joint identity " + name);
    roots[name] = o;
  });
  const specs = {};
  for (const [n, o] of Object.entries(roots)) {
    specs[n] = { ...report.roots?.[n]?.properties, ...o.userData };
  }
  return { roots, specs };
}
function frameMatrix(point, normal) {
  const z = vector(normal).normalize(),
    ref = Math.abs(z.x) < .9 ? new T.Vector3(1, 0, 0) : new T.Vector3(0, 0, -1),
    x = ref.addScaledVector(z, -ref.dot(z)).normalize(),
    y = new T.Vector3().crossVectors(z, x),
    m = new T.Matrix4().makeBasis(x, y, z);
  m.setPosition(vector(point));
  return m;
}
function installPorts(robot) {
  const ports = {};
  const add = (name, owner, s) => {
    if (!owner || !s.interface) return;
    const p = s.position_m ?? s.position ?? [0, 0, 0],
      n = s.normal ?? [0, 0, 1];
    ports[name] = { ...s, name, owner, matrix: frameMatrix(p, n) };
  };
  for (const [n, o] of Object.entries(robot.roots)) {
    const s = robot.specs[n];
    if (s.ports_json) {
      for (const [p, d] of Object.entries(JSON.parse(s.ports_json))) {
        add(n + "/" + p, o, d);
      }
    }
    if (s.interface && s.output_frame) {
      add(n + "/output", o, {
        interface: s.interface,
        position_m: s.output_frame,
        normal: s.output_normal ?? [0, 0, 1],
      });
    }
    if (
      s.interface &&
      (s.attachment_position || s.input_frame || s.mount_pattern_m ||
        n === "parallel_gripper")
    ) {
      add(n + "/input", o, {
        interface: s.interface,
        position_m: s.attachment_position ?? s.input_frame ?? [0, 0, 0],
        normal: s.attachment_normal ?? [0, 0, -1],
      });
    }
  }
  const topRoots = Object.keys(robot.roots).filter((n) =>
    !robot.roots[n].parent?.userData.module_id
  );
  for (const [n, s] of Object.entries(robot.report.mobile?.ports ?? {})) {
    add(n, robot.roots[s.owner] ?? robot.roots[topRoots[0]], s);
  }
  for (const p of robot.derivedPorts ?? []) {
    if (Object.values(robot.roots).includes(p.owner)) ports[p.name] = p;
  }
  robot.ports = ports;
  robot.port = (name) => {
    const p = ports[name];
    if (!p) {
      throw Error(
        `Unknown port ${name}; available: ${Object.keys(ports).join(", ")}`,
      );
    }
    return p;
  };
  robot.attach = (child, { port, childPort, twist = 0 } = {}) => {
    if (child === robot || child.group.getObjectById(robot.group.id)) {
      throw Error("Attachment would create a scene-graph cycle");
    }
    const a = robot.port(port), b = child.port(childPort);
    if (a.interface !== b.interface) {
      throw Error(
        `Mount mismatch: ${a.interface} / ${b.interface}. Use the matching adapter.`,
      );
    }
    robot.group.updateMatrixWorld(true);
    child.group.updateMatrixWorld(true);
    const childFrame = child.group.matrixWorld.clone().invert().multiply(
      b.owner.matrixWorld,
    ).multiply(b.matrix);
    const mate = a.matrix.clone().multiply(new T.Matrix4().makeRotationZ(twist))
      .multiply(new T.Matrix4().makeRotationX(Math.PI)).multiply(
        childFrame.invert(),
      );
    a.owner.add(child.group);
    mate.decompose(
      child.group.position,
      child.group.quaternion,
      child.group.scale,
    );
    child.group.updateMatrix();
    if (child.connection) {
      const old = child.connection.parent;
      old.connections = old.connections.filter((c) => c !== child);
    }
    robot.connections.push(child);
    child.connection = { parent: robot, port, childPort, twist };
    return child;
  };
}
async function template(url, enabled) {
  const key = String(url) + "|" + enabled;
  if (!templates.has(key)) {
    templates.set(
      key,
      (async () => {
        const Loader = globalThis.GLTFLoader ?? GLTFLoader;
        const loader = new Loader();
        loader.register(texturePlugin(url, enabled));
        const b = await bytes(url);
        return loader.parseAsync(
          b.buffer.slice(b.byteOffset, b.byteOffset + b.byteLength),
          new URL(".", url).href,
        );
      })().catch((e) => {
        templates.delete(key);
        throw e;
      }),
    );
  }
  return templates.get(key);
}
function instantiate(gltf) {
  const scene = cloneSkeleton(gltf.scene),
    a = [],
    b = [],
    associations = new Map();
  gltf.scene.traverse((o) => a.push(o));
  scene.traverse((o) => b.push(o));
  a.forEach((o, i) => {
    if (gltf.parser.associations.has(o)) {
      associations.set(b[i], gltf.parser.associations.get(o));
    }
  });
  return { ...gltf, scene, parser: { json: gltf.parser.json, associations } };
}
export async function loadRobot(id, opts = {}) {
  const allowed = new Set([
    "model",
    "scene",
    "position",
    "rotation",
    "scale",
    "color",
    "primary",
    "accent",
    "filament",
    "textures",
    "subassembly",
  ]);
  for (const name of Object.keys(opts)) {
    if (!allowed.has(name)) {
      throw Error(
        `Unknown modular loader option '${name}'. Geometry/slot presets were retired; load and attach the required catalog modules.`,
      );
    }
  }
  for (const key of ["position", "rotation"]) {
    if (
      opts[key] &&
      (!Array.isArray(opts[key]) || opts[key].length !== 3 ||
        !opts[key].every(Number.isFinite))
    ) throw Error(key + " must be three finite numbers");
  }
  if (
    opts.scale !== undefined &&
    (!(opts.scale > 0) || !Number.isFinite(opts.scale))
  ) throw Error("Use a positive uniform display scale");
  const cat = await catalog();
  id = cat.aliases[id] ?? id;
  const entry = cat.models[id];
  if (!entry) {
    throw Error(
      `Unknown modular robot '${id}'. See await RoboticsKit.catalog(); delta, Stewart and Kossel primitive presets were retired.`,
    );
  }
  const url = new URL(entry.path, assetRoot),
    gltf = instantiate(await template(url, opts.textures !== false)),
    report = entry.metadata
      ? await json(new URL(entry.metadata, assetRoot))
      : {};
  const provenance = await json(new URL(entry.provenance, assetRoot)),
    byNode = new Map();
  for (const r of provenance.meshes) byNode.set(r.node + ":" + r.primitive, r);
  gltf.scene.traverse((o) => {
    if (!o.isMesh) return;
    const a = gltf.parser.associations.get(o),
      node = a?.nodes ?? gltf.parser.associations.get(o.parent)?.nodes,
      p = byNode.get(node + ":" + (a?.primitives ?? 0));
    o.userData = { ...o.userData };
    if (p) {
      // A glTF node with multiple primitives becomes a Group whose child meshes
      // do not inherit its extras. Preserve selectable physical-part identity.
      const extras = gltf.parser.json.nodes[node]?.extras ?? {};
      for (const key of ['assembly','batch','delivery','surface_donor','shared_mesh_primary']) {
        if(extras[key] !== undefined)o.userData[key]=extras[key];
      }
      o.userData.part_ids=[...new Set(p.faces.map(([name])=>name))];
      o.userData.part_id=o.userData.part_ids[0];
      o.userData.partForFace = p.faces.flatMap(([n, count]) =>
        Array(count).fill(n)
      );
    }
  });
  const derivedPorts = [];
  gltf.scene.updateMatrixWorld(true);
  gltf.scene.traverse((o) => {
    const s = o.userData, parent = o.parent;
    if (!s.kit_module || !parent?.userData.module_id) return;
    let input = s.attachment_position
      ? {
        interface: s.interface,
        position: s.attachment_position,
        normal: s.attachment_normal,
      }
      : null;
    if (s.kit_module === "torso" && s.ports_json) {
      const b = JSON.parse(s.ports_json).belly;
      if (b) {
        input = {
          interface: b.interface,
          position: b.position_m,
          normal: b.normal,
        };
      }
    }
    if (!input?.interface || s.kit_module === parent.userData.kit_module) {
      return;
    }
    const matrix = parent.matrixWorld.clone().invert().multiply(o.matrixWorld)
      .multiply(frameMatrix(input.position, input.normal)).multiply(
        new T.Matrix4().makeRotationX(Math.PI),
      );
    const ownerName = parent.userData.module_id;
    derivedPorts.push({
      name: ownerName + "/" + s.kit_module,
      owner: parent,
      interface: input.interface,
      matrix,
      provenance: "Mating frame measured from the approved complete assembly",
    });
  });
  const subassembly = opts.subassembly ?? entry.subassembly;
  if (subassembly) {
    gltf.scene.updateMatrixWorld(true);
    const candidates = [];
    gltf.scene.traverse((o) => {
      const a = gltf.parser.associations.get(o);
      if (gltf.parser.json.nodes[a?.nodes]?.name === subassembly.root) {
        candidates.push(o);
      }
    });
    if (candidates.length !== 1) {
      throw Error(
        "Subassembly root is missing or ambiguous: " + subassembly.root,
      );
    }
    const root = candidates[0], matrix = root.matrixWorld.clone();
    gltf.scene.clear();
    gltf.scene.add(root);
    matrix.decompose(root.position, root.quaternion, root.scale);
    root.position.set(0, 0, 0);
    if (subassembly.keepModule) {
      const remove = [];
      root.traverse((o) => {
        if (
          o !== root && o.userData.kit_module &&
          o.userData.kit_module !== subassembly.keepModule
        ) remove.push(o);
      });
      remove.forEach((o) => o.removeFromParent());
    }
    gltf.animations = [];
  }
  const group = new T.Group();
  group.name = "Eidoverse / " + id;
  group.add(gltf.scene);
  group.userData.eidoverseRobotics = true;
  group.userData._loadedAsset = true;
  // Exported assembly labels describe one mechanical instance. Qualify them
  // so two loaded machines never exempt one another in the renderer's audit.
  gltf.scene.traverse((o) => {
    if (o.userData.assembly) {
      o.userData.eidoverseAssembly = o.userData.assembly;
      o.userData.assembly = group.uuid + "/" + o.userData.assembly;
    }
  });
  const actualParts = new Set();
  gltf.scene.traverse((o) => {
    if (o.isMesh) {
      for (const p of o.userData.part_ids ?? [o.userData.part_id]) {
        if (p) actualParts.add(p);
      }
    }
  });
  const robot = {
    id,
    entry: { ...entry, parts: [...actualParts] },
    group,
    root: group,
    model: gltf.scene,
    gltf,
    report,
    ...jointSpecs(gltf.scene, report),
    derivedPorts,
    connections: [],
    state: {},
    disposed: false,
  };
  robot.poseCallbacks = new Set();
  robot.rest = snapshot(gltf.scene);
  robot.reset = () => {
    reset(robot.rest);
    robot.state = {};
    if (robot.defaultJoints) robot.setJoints(robot.defaultJoints);
    robot.filament?.seek(0);
    for (const update of robot.poseCallbacks) update();
    return robot;
  };
  robot.setJoints = (values, { clamp = false } = {}) => {
    // Validate the entire transaction before changing any joint.
    if (
      report.rotary_fixture && robot.roots.rotary_output &&
      robot.roots.rotary_chuck
    ) {
      const angle = values.rotary_output ?? values.rotary_chuck;
      if (angle !== undefined) {
        if (
          values.rotary_output !== undefined &&
          values.rotary_chuck !== undefined &&
          Math.abs(values.rotary_output - values.rotary_chuck) > 1e-9
        ) {
          throw Error("Rotary output and chuck share the same A-axis angle");
        }
        values = { ...values, rotary_output: angle, rotary_chuck: angle };
      }
    }
    const pending = [];
    for (const [n, v] of Object.entries(values)) {
      const o = robot.roots[n], s = robot.specs[n];
      if (!o || !s) throw Error("Unknown joint " + n);
      if (!Number.isFinite(v)) throw Error("Non-finite joint " + n);
      if (!["revolute", "prismatic", "continuous"].includes(s.joint_type)) {
        throw Error("Joint is fixed: " + n);
      }
      const limits = s.limits ?? [-Infinity, Infinity];
      if (!clamp && (v < limits[0] - 1e-7 || v > limits[1] + 1e-7)) {
        throw Error(`Joint ${n} outside [${limits}]`);
      }
      pending.push([n, o, s, Math.max(limits[0], Math.min(limits[1], v))]);
    }
    for (const [n, o, s, v] of pending) {
      const rest = robot.rest.get(o),
        axis = vector(s.axis ?? [0, 0, 1]).normalize();
      o.position.copy(rest.position);
      o.quaternion.copy(rest.quaternion);
      if (s.joint_type === "prismatic") {
        o.position.add(axis.applyQuaternion(rest.quaternion).multiplyScalar(v));
      } else {o.quaternion.multiply(
          new T.Quaternion().setFromAxisAngle(axis, v),
        );}
      robot.state[n] = v;
      o.updateMatrix();
    }
    for (const update of robot.poseCallbacks) update();
    return robot;
  };
  robot.parts = () => [...actualParts];
  robot.part = (name) => {
    const found = [];
    gltf.scene.traverse((o) => {
      if (
        o.isMesh && (o.userData.part_ids ?? [o.userData.part_id]).includes(name)
      ) found.push(o);
    });
    if (!found.length) throw Error("Unknown part " + name);
    return found;
  };
  robot.stats = () => {
    let triangles = 0, meshes = 0;
    const geometry = new Set(), materials = new Set(), textures = new Set();
    gltf.scene.traverse((o) => {
      if (!o.isMesh || !o.visible || !o.userData.eidoverseRobotics) return;
      triangles +=
        (o.geometry.index?.count ?? o.geometry.attributes.position.count) / 3;
      meshes++;
      geometry.add(o.geometry);
      for (const m of [].concat(o.material)) {
        materials.add(m);
        for (
          const k of [
            "map",
            "normalMap",
            "aoMap",
            "roughnessMap",
            "metalnessMap",
            "emissiveMap",
          ]
        ) if (m[k]) textures.add(m[k]);
        for (const k of ["fixedMap", "maskMap"]) {
          if (m.userData[k]) textures.add(m.userData[k]);
        }
      }
    });
    return {
      triangles,
      meshes,
      uniqueGeometry: geometry.size,
      materials: materials.size,
      textures: textures.size,
      parts: robot.parts().length,
    };
  };
  robot.materials = await prepareMaterials(gltf.scene, url, opts);
  robot.setColors = (primary, accent) => {
    robot.materials.setColor(primary, accent);
    return robot;
  };
  installPorts(robot);
  await installMotion(robot);
  installFilament(robot, (mesh, name, parent) => {
    parent.add(mesh);
    mesh.userData.part_id = name;
    mesh.userData.part_ids = [name];
    mesh.userData.partForFace = Array(
      (mesh.geometry.index?.count ?? mesh.geometry.attributes.position.count) /
        3,
    ).fill(name);
    mesh.userData.eidoverseRobotics = true;
    mesh.userData._loadedAsset = true;
    mesh.geometry.userData._loadedAsset = true;
    if (!actualParts.has(name)) robot.entry.parts.push(name);
    actualParts.add(name);
    robot.materials.materials.push(mesh.material);
  });
  if (opts.position) group.position.fromArray(opts.position);
  if (opts.rotation) group.rotation.fromArray(opts.rotation);
  if (opts.scale !== undefined) group.scale.setScalar(opts.scale);
  if (opts.scene) opts.scene.add(group);
  robot.dispose = () => {
    if (robot.disposed) return;
    robot.disposed = true;
    [...robot.connections].forEach((c) => c.dispose());
    group.removeFromParent();
    robot.stop?.();
    robot.filament?.dispose();
    robot.poseCallbacks.clear();
    robot.materials.materials.forEach((m) => m.dispose());
  };
  return robot;
}
export const makeRobot = loadRobot;
export async function loadPart(modelId, name, opts = {}) {
  const { scene, ...loadOptions } = opts;
  const robot = await loadRobot(modelId, loadOptions);
  const ownedGeometry = [];
  const dispose = robot.dispose;
  robot.dispose = () => {
    if (robot.disposed) return;
    dispose();
    ownedGeometry.forEach((g) => g.dispose());
  };
  try {
    const selected = new Set(robot.part(name));
    robot.model.traverse((o) => {
      if (!o.isMesh) return;
      if (!selected.has(o)) {
        o.visible = false;
        return;
      }
      const faces = o.userData.partForFace;
      const triangleCount =
        (o.geometry.index?.count ?? o.geometry.attributes.position.count) / 3;
      if (!faces || faces.length !== triangleCount) {
        throw Error("Exact triangle ownership unavailable for " + name);
      }
      const indices = [];
      faces.forEach((p, i) => {
        if (p === name) {
          for (let j = 0; j < 3; j++) {
            indices.push(
              o.geometry.index ? o.geometry.index.getX(i * 3 + j) : i * 3 + j,
            );
          }
        }
      });
      if (!indices.length) {
        throw Error("No mapped triangles for part " + name + " in " + o.name);
      }
      const geometry = o.geometry.clone();
      ownedGeometry.push(geometry);
      geometry.setIndex(indices);
      geometry.computeBoundingBox();
      geometry.computeBoundingSphere();
      o.geometry = geometry;
      o.userData.partForFace = Array(indices.length / 3).fill(name);
      o.userData.part_ids = [name];
    });
    robot.parts = () => [name];
    robot.entry.parts = [name];
    if (scene) scene.add(robot.group);
    return robot;
  } catch (error) {
    robot.dispose();
    throw error;
  }
}
export { cacheStats };
