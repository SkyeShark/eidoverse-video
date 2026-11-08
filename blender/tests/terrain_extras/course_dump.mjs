// Runs eidoverse/terrain_base.js's setup() on a recording stand-in for three.js and dumps the course it builds
// (every mesh: geometry and its parameters, position, rotation, material colour; the Rapier half extents it would
// collide with; the telemetry segments; its log lines), for test_course_parity.py. setup() stops where it loads the
// character (no ASSETS.character_vrm here): the terrain is complete by then.
//   deno run --no-config --no-lock -A course_dump.mjs <terrain_base.js> <configs.json> <out.json>
const [SRC, CONFIGS, OUT] = Deno.args;
const configs = JSON.parse(Deno.readTextFileSync(CONFIGS));

class V3 { constructor(x = 0, y = 0, z = 0) { this.x = x; this.y = y; this.z = z; }
    set(x, y, z) { this.x = x; this.y = y; this.z = z; return this; } }
class Euler { constructor() { this.x = 0; this.y = 0; this.z = 0; } }
class Geo { constructor(type, args) { this.type = type; this.args = args; } }
class Mesh {
    constructor(geo, mat) { this.geometry = geo; this.material = mat; this.position = new V3(); this.rotation = new Euler();
        this.userData = {}; this.quaternion = { x: 0, y: 0, z: 0, w: 1 }; }
}
class Mat { constructor(o) { this.opts = o; } }
const added = [];
const logs = [];
const THREE = {
    WebGPURenderer: class { constructor() { this.shadowMap = {}; } setSize() {} async init() {} },
    SRGBColorSpace: 'srgb', ACESFilmicToneMapping: 4,
    Scene: class { add(o) { added.push(o); } },
    Color: class { constructor(c) { this.c = c; } },
    PerspectiveCamera: class { constructor(...a) { this.args = a; this.position = new V3(); } },
    DirectionalLight: class { constructor(c, i) { this.color = c; this.intensity = i; this.position = new V3();
        this.shadow = { mapSize: new V3(), camera: {} }; this.isLight = true; } },
    AmbientLight: class { constructor(c, i) { this.color = c; this.intensity = i; this.isLight = true; } },
    MeshStandardNodeMaterial: Mat,
    Mesh,
    PlaneGeometry: class extends Geo { constructor(...a) { super('Plane', a); } },
    BoxGeometry: class extends Geo { constructor(...a) { super('Box', a); } },
    SphereGeometry: class extends Geo { constructor(...a) { super('Sphere', a); } },
    CylinderGeometry: class extends Geo { constructor(...a) { super('Cylinder', a); } },
};
globalThis.THREE = THREE;
globalThis.GLTFLoader = class { register() {} };
globalThis.canvas = {}; globalThis.WIDTH = 960; globalThis.HEIGHT = 540;
globalThis.GPU_ADAPTER = null; globalThis.GPU_DEVICE = null;
globalThis.ASSETS = {};
const realLog = console.log;
console.log = (...a) => logs.push(a.join(' '));
(0, eval)(Deno.readTextFileSync(SRC));

const results = {};
for (const [name, cfg] of Object.entries(configs)) {
    added.length = 0; logs.length = 0;
    globalThis.TERRAIN_CONFIG = cfg;
    let error = null;
    try { await globalThis.setup(); } catch (e) { error = String(e.message); }
    const meshes = added.filter(o => o instanceof Mesh).map(m => ({
        geo: m.geometry.type, args: m.geometry.args, pos: [m.position.x, m.position.y, m.position.z],
        rot: [m.rotation.x, m.rotation.y, m.rotation.z], color: m.material.opts.color,
        metalness: m.material.opts.metalness, roughness: m.material.opts.roughness, userData: m.userData,
    }));
    const lights = added.filter(o => o.isLight).map(l => ({ color: l.color, intensity: l.intensity,
        pos: l.position ? [l.position.x, l.position.y, l.position.z] : null }));
    results[name] = { error, meshes, lights, segments: globalThis._terrainTelemetrySegments ?? null, logs: [...logs] };
}
console.log = realLog;
Deno.writeTextFileSync(OUT, JSON.stringify(results, null, 1));
console.log(`[course_dump] ${Object.keys(results).length} configs -> ${OUT}`);
