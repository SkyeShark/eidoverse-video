// These material-inspection examples supply their own calibrated studio lighting.
globalThis._noAutoEnhance = true;
// G430 FDM and CNC. The 18-second clip is an explicit process time-lapse.
var jobs = [];
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
  _r.outputColorSpace = THREE.SRGBColorSpace;
  _r.toneMapping = THREE.ACESFilmicToneMapping;
  _s = view.studio(_r);
  _c = new THREE.PerspectiveCamera(36, WIDTH / HEIGHT, .001, 20);
  const printer = await api.loadRobot("fdm", {
      scene: _s,
      position: [-.78, 0, 0],
      accent: "#267c82",
      filament: "#218675",
    }),
    cnc = await api.loadRobot("cnc", {
      scene: _s,
      position: [0, 0, 0],
      accent: "#b26c36",
    }),
    woodCnc = await api.loadRobot("cnc_relief", {
      scene: _s,
      position: [.78, 0, 0],
      accent: "#688050",
    });
  const sleeve = new THREE.LatheGeometry(
    [[.014, 0], [.020, 0], [.020, .006], [.014, .006], [.014, 0]].map((p) =>
      new THREE.Vector2(...p)
    ),
    48,
  );
  jobs = [
    fab.print(printer, sleeve, {
      size: .04,
      infill: .25,
      duration: 18,
      color: "#218675",
    }),
    fab.mill(cnc, null, { material: "aluminum", duration: 18 }),
    fab.carve(woodCnc, fab.sampleRelief, {
      material: "wood",
      duration: 18,
      resolution: 192,
    }),
  ];
  sleeve.dispose();
  view.frameCamera(_c, [printer.group, cnc.group, woodCnc.group], {
    direction: [-.55, .75, 1.2],
    margin: 1.12,
  });
  // This fixed wide camera has ample foreground clearance. Preserve depth
  // precision for the real 0.65 mm sheet directly above its original bed.
  _c.near = .05;
  _c.updateProjectionMatrix();
}
async function renderFrame(t) {
  jobs.forEach((j) => j.seek(t));
  _r.render(_s, _c);
}
