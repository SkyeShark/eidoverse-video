// An indexed rotary carving study. Change radius(x, angle) to design the shape.
globalThis._noAutoEnhance = true;
var machine, job;
globalThis.setup = async function () {
  const api = await import(EIDOVERSE_DIR + "robotics/index.js");
  const fab = await import(EIDOVERSE_DIR + "robotics/fabrication.js");
  const { studio } = await import(EIDOVERSE_DIR + "robotics/studio.js");
  _r = new THREE.WebGPURenderer({
    canvas,
    antialias: true,
    adapter: GPU_ADAPTER,
    device: GPU_DEVICE,
  });
  await _r.init();
  _r.setSize(WIDTH, HEIGHT);
  _r.outputColorSpace = THREE.SRGBColorSpace;
  _r.toneMapping = THREE.ACESFilmicToneMapping;
  _s = studio(_r, { grid: false });
  _c = new THREE.PerspectiveCamera(36, WIDTH / HEIGHT, .035, 10);
  machine = await api.loadRobot("cnc_rotary", {
    scene: _s,
    primary: "#b9c7c8",
    accent: "#235b68",
  });
  job = fab.rotaryCarve(machine, fab.sampleRotary, {
    renderer: _r,
    material: "wood",
    duration: 28,
  });
  _c.position.set(-.31, .38, .48);
  _c.lookAt(.015, .16, 0);
};
globalThis.renderFrame = async function (t) {
  job.seek(Math.max(0, t - 1));
  await _r.renderAsync(_s, _c);
};
globalThis.cleanup = function () {
  job.dispose();
  machine.dispose();
};
