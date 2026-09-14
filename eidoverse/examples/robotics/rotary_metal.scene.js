// Aluminum rotary milling: setup, eight seconds at physical cutting speed,
// then a time-lapse finish. Change material to brass for its appearance/rates.
globalThis._noAutoEnhance = true;
var machine, job, cuttingStart;
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
    material: "aluminum",
  });
  cuttingStart = job.removal.events[0].time;
  console.log(
    "METAL_STUDY",
    JSON.stringify({
      physicalDuration: job.physicalDuration,
      cuttingStart,
      settings: job.settings,
      stages: job.program.stages.length,
    }),
  );
};
globalThis.renderFrame = async function (t) {
  const time = t < 2 ? t : t < 10 ? cuttingStart + t - 2 : cuttingStart + 8 +
    Math.min(1, (t - 10) / 18) * (job.duration - cuttingStart - 8);
  job.seek(time);
  if (t < 2 || t >= 28) {
    _c.position.set(-.31, .38, .48);
    _c.lookAt(.015, .16, 0);
  } else {
    _c.position.set(.22, .275, .30);
    _c.lookAt(.025, .153, 0);
  }
  await _r.renderAsync(_s, _c);
};
globalThis.cleanup = function () {
  job.dispose();
  machine.dispose();
};
