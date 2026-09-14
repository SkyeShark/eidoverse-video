// These material-inspection examples supply their own calibrated studio lighting.
globalThis._noAutoEnhance = true;
// Current assembled humanoid, quadruped, payload drone and tracked arm.
var examples = [];
async function setup() {
  const api = await import(new URL("robotics/index.js", EIDOVERSE_DIR)),
    view = await import(new URL("robotics/studio.js", EIDOVERSE_DIR));
  _r = new THREE.WebGPURenderer({
    canvas,
    antialias: true,
    adapter: GPU_ADAPTER,
    device: GPU_DEVICE,
  });
  await _r.init();
  _r.setSize(WIDTH, HEIGHT);
  _r.toneMapping = THREE.ACESFilmicToneMapping;
  _s = view.studio(_r);
  _c = new THREE.PerspectiveCamera(35, WIDTH / HEIGHT, .001, 30);
  for (
    const [id, clip, position] of [
      ["humanoid", "run-circle", [-1.3, 0, 0]],
      ["quadruped", "run-circle", [1.6, 0, 0]],
      ["payloads/drone_hand", "flight", [0, 1.1, -1.8]],
      ["payloads/rover_arm", "drive", [0, 0, 1.8]],
    ]
  ) {
    const robot = await api.loadRobot(id, { scene: _s, position });
    examples.push({ robot, clip });
  }
  _c.position.set(5, 3.8, 7);
  _c.lookAt(-.8, .7, 0);
}
async function renderFrame(t) {
  examples.forEach(({ robot, clip }) => robot.sample(clip, t));
  await _r.renderAsync(_s, _c);
}
