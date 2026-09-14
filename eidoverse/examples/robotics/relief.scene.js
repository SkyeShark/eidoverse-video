// A close study of three-axis carving. Playback uses an explicit time lapse.
globalThis._noAutoEnhance = true;
var carving;
async function setup() {
  const api = await import(new URL("robotics/index.js", EIDOVERSE_DIR));
  const fab = await import(new URL("robotics/fabrication.js", EIDOVERSE_DIR));
  const view = await import(new URL("robotics/studio.js", EIDOVERSE_DIR));
  _r = new THREE.WebGPURenderer({
    canvas,
    antialias: true,
    adapter: GPU_ADAPTER,
    device: GPU_DEVICE,
  });
  await _r.init();
  _r.setSize(WIDTH, HEIGHT);
  _r.toneMapping = THREE.ACESFilmicToneMapping;
  _s = view.studio(_r, { grid: false });
  _c = new THREE.PerspectiveCamera(36, WIDTH / HEIGHT, .0001, 20);
  const machine = await api.loadRobot("cnc_relief", {
    scene: _s,
    accent: "#547b68",
  });
  carving = fab.carve(machine, fab.sampleRelief, {
    material: "wood",
    duration: 24,
    resolution: 192,
  });
  view.frameCamera(_c, [carving.mesh], {
    direction: [.8, 1.05, .8],
    margin: 1.5,
  });
}
async function renderFrame(t) {
  carving.seek(t);
  _r.render(_s, _c);
}
