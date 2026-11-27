// eidoverse/examples/studio_light.js — the props examples' studio light (the interactive edition's
// eidoverse/robotics/studio.js): a room environment through PMREM, a sky-and-ground hemisphere and a warm key, on a
// pale grey ground with an optional grid. Dynamic ESM:
//
//   const { studio } = await import(new URL('examples/studio_light.js', EIDOVERSE_DIR).href);
//   const scene = studio(renderer, { grid: true });          // its key: the scene's one DirectionalLight
import * as T from 'three/webgpu';
import { RoomEnvironment } from 'npm:three@0.184.0/addons/environments/RoomEnvironment.js';

export function studio(renderer, { grid = true } = {}) {
    // three r184 can ask twice for a PMREM / DFG texture already made on the native backend: reuse only an existing
    // resource of the size asked for
    const utils = renderer.backend?.textureUtils;
    if (globalThis.Deno && utils && !utils._eidoStudioReuse) {
        const create = utils.createTexture.bind(utils);
        utils.createTexture = function (texture, options) {
            const d = this.backend.get(texture), gpu = d?.texture;
            if (d?.initialized && gpu && gpu.width === options.width && gpu.height === options.height
                && gpu.depthOrArrayLayers === (options.depth ?? 1)) return;
            return create(texture, options);
        };
        utils._eidoStudioReuse = true;
    }
    const scene = new T.Scene();
    scene.background = new T.Color('#c6cfd1');
    const env = new RoomEnvironment(), generator = new T.PMREMGenerator(renderer), target = generator.fromScene(env, 0.04);
    scene.environment = target.texture;
    scene.environmentIntensity = 0.9;
    scene.userData.disposeStudio = () => { target.dispose(); generator.dispose(); env.dispose(); };
    scene.add(new T.HemisphereLight(0xe6f2ff, 0x485654, 1));
    const sun = new T.DirectionalLight(0xfff3e4, 2.3);
    sun.position.set(2, 5, 3);
    scene.add(sun);
    if (grid) {
        const ground = new T.GridHelper(8, 80, 0x748b91, 0xacb9bd);
        ground.position.y = -0.001;
        scene.add(ground);
    }
    return scene;
}
