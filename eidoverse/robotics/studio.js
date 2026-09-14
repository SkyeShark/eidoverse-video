// MIT. Compact, shared presentation for examples and the inspector.
import * as T from "three/webgpu";
import { RoomEnvironment } from "npm:three@0.184.0/addons/environments/RoomEnvironment.js";
export function studio(renderer, { grid = true } = {}) {
  // Three r184 can ask twice for a PMREM/DFG texture already initialized on
  // the native backend. Reuse only an existing resource of the requested size.
  const utils = renderer.backend?.textureUtils;
  if (globalThis.Deno && utils && !utils._eidoStudioReuse) {
    const create = utils.createTexture.bind(utils);
    utils.createTexture = function (texture, options) {
      const d = this.backend.get(texture), gpu = d?.texture;
      if (
        d?.initialized && gpu && gpu.width === options.width &&
        gpu.height === options.height &&
        gpu.depthOrArrayLayers === (options.depth ?? 1)
      ) return;
      return create(texture, options);
    };
    utils._eidoStudioReuse = true;
  }
  const scene = new T.Scene();
  scene.background = new T.Color("#c6cfd1");
  const env = new RoomEnvironment(),
    generator = new T.PMREMGenerator(renderer),
    target = generator.fromScene(env, .04);
  scene.environment = target.texture;
  scene.environmentIntensity = .9;
  scene.userData.disposeStudio = () => {
    target.dispose();
    generator.dispose();
    env.dispose();
  };
  scene.add(new T.HemisphereLight(0xe6f2ff, 0x485654, 1));
  const sun = new T.DirectionalLight(0xfff3e4, 2.3);
  sun.position.set(2, 5, 3);
  scene.add(sun);
  if (grid) {
    const ground = new T.GridHelper(8, 80, 0x748b91, 0xacb9bd);
    ground.position.y = -.001;
    scene.add(ground);
  }
  return scene;
}
export function frameCamera(
  camera,
  objects,
  { direction = [.9, .55, 1.5], margin = 1.25 } = {},
) {
  const box = new T.Box3();
  objects.forEach((o) => o.isBox3 ? box.union(o) : box.expandByObject(o));
  if (box.isEmpty()) return new T.Vector3();
  const target = box.getCenter(new T.Vector3()),
    towardCamera = new T.Vector3(...direction).normalize(),
    right = new T.Vector3().crossVectors(camera.up, towardCamera),
    halfVertical = T.MathUtils.degToRad(camera.fov / 2),
    tanV = Math.tan(halfVertical),
    tanH = tanV * camera.aspect;
  if (right.lengthSq() < 1e-8) right.set(1, 0, 0);
  right.normalize();
  const up = new T.Vector3().crossVectors(towardCamera, right).normalize();
  let d = .01;
  for (const x of [box.min.x, box.max.x]) {
    for (const y of [box.min.y, box.max.y]) {
      for (const z of [box.min.z, box.max.z]) {
        const p = new T.Vector3(x, y, z).sub(target);
        d = Math.max(
          d,
          p.dot(towardCamera) +
            margin *
              Math.max(
                Math.abs(p.dot(right)) / tanH,
                Math.abs(p.dot(up)) / tanV,
              ),
        );
      }
    }
  }
  camera.position.copy(target).add(
    towardCamera.multiplyScalar(d),
  );
  camera.near = Math.max(.001, d / 2000);
  camera.far = Math.max(20, d * 20);
  camera.updateProjectionMatrix();
  camera.lookAt(target);
  return target;
}
