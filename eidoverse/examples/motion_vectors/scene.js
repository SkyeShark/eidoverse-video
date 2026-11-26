// The motion-vector example (AGENTS.md, "DLSS 5 over a finished film (host tool)"): a camera pans across a
// checkered floor while a cube slides and a sphere rises, rendered with "motionVectors" on, so the runner writes
// three's velocity for every frame. check.py renders it and confirms the files with dlss5nr/motion_check.py.
var cube, sphere;
async function setup() {
  _r = new THREE.WebGPURenderer({ canvas, antialias: true, adapter: GPU_ADAPTER, device: GPU_DEVICE });
  await _r.init();
  _r.setSize(WIDTH, HEIGHT);
  _s = new THREE.Scene();
  _s.background = new THREE.Color(0x404850);
  _c = new THREE.PerspectiveCamera(40, WIDTH / HEIGHT, 0.1, 100);
  const { uv, color, mix, step, fract, floor } = THREE;
  // a floor with a fine checker (procedural, so the frames carry detail a motion check can follow)
  const cells = floor(uv().mul(24.0));
  const parity = fract(cells.x.add(cells.y).mul(0.5)).mul(2.0);
  const floorMat = new THREE.MeshStandardNodeMaterial({ roughness: 0.8 });
  floorMat.colorNode = mix(color(0x1b2028), color(0xd8cfb4), step(0.5, parity));
  const ground = new THREE.Mesh(new THREE.PlaneGeometry(16, 16), floorMat);
  ground.rotation.x = -Math.PI / 2;
  _s.add(ground);
  const boxMat = new THREE.MeshStandardNodeMaterial({ roughness: 0.5 });
  const boxCells = floor(uv().mul(4.0));
  boxMat.colorNode = mix(color(0x9a2a10), color(0xf0c060), step(0.5, fract(boxCells.x.add(boxCells.y).mul(0.5)).mul(2.0)));
  cube = new THREE.Mesh(new THREE.BoxGeometry(1, 1, 1), boxMat);
  sphere = new THREE.Mesh(new THREE.SphereGeometry(0.4, 32, 16), boxMat);
  _s.add(cube, sphere);
  const sun = new THREE.DirectionalLight(0xffffff, 3.0);
  sun.position.set(3, 6, 4);
  _s.add(sun, new THREE.HemisphereLight(0xb0c0d0, 0x302820, 1.0));
}
async function renderFrame(t) {
  const k = t / DURATION;
  cube.position.set(-1.5 + 3.0 * k, 0.5, 0);
  cube.rotation.y = 0.6 * k;
  sphere.position.set(1.2, 0.4 + 1.0 * k, -1.2);
  _c.position.set(-1.0 + 2.2 * k, 3.0, 7.0);
  _c.lookAt(0.2 * k, 0.4, 0);
  await _r.renderAsync(_s, _c);
}
