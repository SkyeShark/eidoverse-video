// These material-inspection examples supply their own calibrated studio lighting.
globalThis._noAutoEnhance = true;
// Demonstrate a new assembly made through interface frames, with shared assets.
var assembly = [];
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
  _c = new THREE.PerspectiveCamera(32, WIDTH / HEIGHT, .001, 20);
  const base = await api.loadRobot("mobility/body", { scene: _s }),
    camera = await api.loadRobot("camera"),
    face = await api.loadRobot("face");
  base.attach(camera, {
    port: "body_base/sensor_0",
    childPort: "camera_base/input",
  });
  base.attach(face, {
    port: "body_base/sensor_1",
    childPort: "display_base/input",
  });
  assembly = [base, camera, face];
  view.frameCamera(_c, [base.group], { direction: [1, .7, 1.5] });
}
async function renderFrame(t) {
  assembly.slice(1).forEach((r) => r.sample("joints", t));
  await _r.renderAsync(_s, _c);
}
