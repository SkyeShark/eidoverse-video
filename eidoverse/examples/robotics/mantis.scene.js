// These material-inspection examples supply their own calibrated studio lighting.
globalThis._noAutoEnhance = true;
// Maximal shared-kit build: tracked MANTIS with multiple articulated payloads.
var mantis, cameraOffset, targetOffset;
async function setup() {
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
  _s = view.studio(_r);
  _c = new THREE.PerspectiveCamera(36, WIDTH / HEIGHT, .001, 30);
  mantis = await makeRobot("mantis", {
    scene: _s,
    primary: "#b4c6c3",
    accent: "#365e65",
  });
  mantis.sample("drive-circle", 0);
  const target=view.frameCamera(_c, [mantis.group], { direction: [.7, .65, 1], margin: 1.06 });
  const anchor=mantis.roots[mantis.report.novel.body_root].getWorldPosition(new THREE.Vector3());
  cameraOffset=_c.position.clone().sub(anchor);targetOffset=target.sub(anchor);
}
async function renderFrame(t) {
  mantis.sample("drive-circle", t);
  const anchor=mantis.roots[mantis.report.novel.body_root].getWorldPosition(new THREE.Vector3());
  _c.position.copy(anchor).add(cameraOffset);_c.lookAt(anchor.clone().add(targetOffset));
  await _r.renderAsync(_s, _c);
}
