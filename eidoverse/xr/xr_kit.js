// xr_kit.js — the parts every Eidoverse WebXR page needs, for the Quest browser (guide: tools-guides/webxr.md).
//
// Import it from a page whose import map points "three", "three/tsl" and "three/addons/" at node_modules
// (eidoverse/xr/serve.py serves them; see example.html). What it encodes, learned on Quest 3 / Quest Browser:
//   - WebGPURenderer on its WebGL2 backend (forceWebGL): the Quest browser has no XRGPUBinding yet.
//   - Move the WORLD, never the camera: three r184's XR manager ignores a camera's parent in a session,
//     so a camera rig does nothing (or freezes head-locked). Everything lives in a `stage` group the rig moves.
//   - Never renderer.setSize() while presenting: entering VR fires a resize, and reconfiguring the
//     swapchain kills the XR layer.
//   - Arm a session by polling renderer.xr.getSession() in the loop (the sessionstart event is not reliable)
//     and count the session's own frames next to the loop's: if they diverge, the XR layer has died.
import * as THREE from 'three';
import { uniform, color } from 'three/tsl';
import { VRButton } from 'three/addons/webxr/VRButton.js';

export const BTN = { TRIGGER: 0, GRIP: 1, STICK: 3, AX: 4, BY: 5 };   // xr-standard gamepad (A/B right, X/Y left)
const UP = new THREE.Vector3(0, 1, 0);

// ---------------------------------------------------------------- telemetry
// report({...}) POSTs one JSON line to serve.py's /report (tagged), and uncaught errors are reported with their
// stack: in a headset there is no console, so this log is how a session is read back afterwards.
export function telemetry(tag, { url = '/report' } = {}) {
  const report = (o) => fetch(url, { method: 'POST', body: JSON.stringify(Object.assign({ test: tag }, o)) }).catch(() => {});
  addEventListener('error', (e) => report({ phase: 'error', error: String(e.message), at: `${e.filename}:${e.lineno}`,
    stack: String((e.error && e.error.stack) || '').slice(0, 900) }));
  addEventListener('unhandledrejection', (e) => report({ phase: 'error', error: String((e.reason && e.reason.message) || e.reason),
    stack: String((e.reason && e.reason.stack) || '').slice(0, 900) }));
  return report;
}

// ---------------------------------------------------------------- renderer
export async function createRenderer({ parent = document.body, framebufferScale = 0.9, foveation = 1, button = true } = {}) {
  const renderer = new THREE.WebGPURenderer({ antialias: true, forceWebGL: true });
  renderer.setPixelRatio(Math.min(devicePixelRatio, 2));
  renderer.setSize(Math.max(innerWidth, 320), Math.max(innerHeight, 180));
  renderer.outputColorSpace = THREE.SRGBColorSpace;
  parent.appendChild(renderer.domElement);
  await renderer.init();
  renderer.xr.enabled = true;
  renderer.xr.setReferenceSpaceType('local-floor');
  if (renderer.xr.setFramebufferScaleFactor) renderer.xr.setFramebufferScaleFactor(framebufferScale);
  if (renderer.xr.setFoveation) try { renderer.xr.setFoveation(foveation); } catch (e) { /* not every browser */ }
  const vrButton = VRButton.createButton(renderer);
  if (button) document.body.appendChild(vrButton);
  return { renderer, vrButton };
}

// Resize with the window on the desktop — and never while presenting.
export function keepSized(renderer, camera) {
  addEventListener('resize', () => {
    if (renderer.xr.isPresenting) return;
    renderer.setSize(innerWidth, innerHeight);
    camera.aspect = innerWidth / innerHeight;
    camera.updateProjectionMatrix();
  });
}

// ---------------------------------------------------------------- the loop
// onFrame(now, dt, inXR) before each render · onSession(session) once per session, after it is armed ·
// heartbeat() -> extra fields for the 3 s heartbeat. Reports: sessionarmed, hb (frames vs the session's own
// frames, loopAlive, xrAlive, triangles), measured (fps over the first 10 s), contextlost.
// still: set window.__shot = 'ready' after 3 rendered frames (for eidoverse/xr/shot.mjs).
export function startLoop(renderer, scene, camera, { onFrame, onSession, report, heartbeat, hbMs = 3000, still = false } = {}) {
  let frames = 0, sFrames = 0, t0 = 0, armed = null, measured = false, lastF = -1, lastS = -1, lastNow = 0;
  const arm = (sess) => {
    frames = 0; sFrames = 0; t0 = 0; measured = false;
    const pump = () => { sFrames++; try { sess.requestAnimationFrame(pump); } catch (e) { /* session gone */ } };
    try { sess.requestAnimationFrame(pump); } catch (e) { /* session gone */ }
    if (report) report({ phase: 'sessionarmed', frameRate: sess.frameRate || null,
      supported: sess.supportedFrameRates ? [...sess.supportedFrameRates] : null });
    if (onSession) onSession(sess);
  };
  if (report) setInterval(() => {
    if (renderer.xr.isPresenting) report(Object.assign({ phase: 'hb', frames, sFrames, loopAlive: frames !== lastF,
      xrAlive: sFrames !== lastS, tris: renderer.info.render.triangles }, heartbeat ? heartbeat() : {}));
    lastF = frames; lastS = sFrames;
  }, hbMs);
  renderer.domElement.addEventListener('webglcontextlost', () => report && report({ phase: 'contextlost' }));
  renderer.setAnimationLoop((now) => {
    const xr = renderer.xr.isPresenting;
    if (document.hidden && !xr) return;
    const dt = Math.min(0.05, Math.max(0, (now - (lastNow || now)) / 1000));
    lastNow = now;
    if (xr) {
      const sess = renderer.xr.getSession();
      if (sess && sess !== armed) { armed = sess; arm(sess); }
    }
    if (onFrame) onFrame(now, dt, xr);
    renderer.render(scene, camera);
    frames++;
    if (!t0) t0 = now;
    const el = (now - t0) / 1000;
    if (xr && el > 10 && !measured) {
      measured = true;
      if (report) report({ phase: 'measured', fps: +(frames / el).toFixed(1), xrfps: +(sFrames / el).toFixed(1),
        frameRate: (renderer.xr.getSession() && renderer.xr.getSession().frameRate) || null });
    }
    if (still && frames === 3) window.__shot = 'ready';
  });
  return { get frames() { return frames; } };
}

// ---------------------------------------------------------------- the rig: move the world, never the camera
// `stage` holds the world in its own units, y up. STREET: you stand in it, `street` metres to a unit. TABLE: it
// sits in front of you like a model on a table, `table` metres to a unit. Every method moves the stage.
export class WorldRig {
  constructor({ renderer, camera, stage, street = 0.12, table = 0.01, eyeHeight = 1.6 }) {
    Object.assign(this, { renderer, camera, stage, street, table, eyeHeight });
    this.mode = 'street';
    this._flickReady = true;
    this._pos = new THREE.Vector3(); this._q = new THREE.Quaternion();
  }
  // your eyes and the way you face, in the room (the XR camera in a session, the page's camera otherwise)
  head() {
    const cam = this.renderer.xr.isPresenting ? this.renderer.xr.getCamera() : this.camera;
    if (!this.renderer.xr.isPresenting) cam.updateMatrixWorld();
    const position = new THREE.Vector3().setFromMatrixPosition(cam.matrixWorld);
    this._q.setFromRotationMatrix(cam.matrixWorld);
    return { position, forward: new THREE.Vector3(0, 0, -1).applyQuaternion(this._q) };
  }
  _flat(v) { const f = v.clone(); f.y = 0; if (f.lengthSq() < 1e-6) f.set(0, 0, -1); return f.normalize(); }
  // stand at `point` (stage units, on the ground), facing stage direction `facing`
  standAt(point, { facing = new THREE.Vector3(0, 0, -1), scale = this.street } = {}) {
    this.mode = 'street';
    const { position: H, forward } = this.head(), f = this._flat(forward), lf = this._flat(facing);
    const yaw = Math.atan2(-f.x, -f.z) - Math.atan2(-lf.x, -lf.z);
    this.stage.scale.setScalar(scale);
    this.stage.rotation.set(0, yaw, 0);
    const p = new THREE.Vector3(point.x, 0, point.z).multiplyScalar(scale).applyAxisAngle(UP, yaw);
    this.stage.position.set(H.x - p.x, 0, H.z - p.z);
  }
  // the world in front of you at table scale: stage point `centre` about `distance` m ahead, at `height`
  // (default: about 75 cm below your eyes, kept between 0.6 and 1.05 m) — or exactly at room point `at`
  toTable({ centre = new THREE.Vector3(), scale = this.table, distance = 0.45, height = null, at = null } = {}) {
    this.mode = 'table';
    const { position: H, forward } = this.head(), f = this._flat(forward);
    const yaw = Math.atan2(-f.x, -f.z);
    this.stage.scale.setScalar(scale);
    this.stage.rotation.set(0, yaw, 0);
    const y = height == null ? Math.min(1.05, Math.max(0.6, H.y - 0.75)) : height;
    const target = at ? at.clone() : new THREE.Vector3(H.x + f.x * distance, y, H.z + f.z * distance);
    const c = centre.clone().multiplyScalar(scale).applyAxisAngle(UP, yaw);
    this.stage.position.copy(target.sub(c));
    this._tableCentre = centre.clone();
  }
  // walk: forward (+) / back and right (+) / left, relative to where you look, `speed` m/s
  walk(right, forward, dt, speed = 2.6) {
    const f = this._flat(this.head().forward), r = new THREE.Vector3(-f.z, 0, f.x), v = speed * dt;
    this.stage.position.addScaledVector(f, -forward * v).addScaledVector(r, -right * v);
  }
  // turn about your head by `a` radians (+ = to your right)
  turn(a) {
    const H = this.head().position, off = this.stage.position.clone().sub(H);
    off.y = 0; off.applyAxisAngle(UP, a);
    this.stage.position.set(H.x + off.x, this.stage.position.y, H.z + off.z);
    this.stage.rotation.y += a;
  }
  // snap turning from a stick's x: 30 degrees per flick, re-armed when the stick comes back to the middle
  flick(x, step = Math.PI / 6) {
    if (this._flickReady && Math.abs(x) > 0.6) { this.turn(Math.sign(x) * step); this._flickReady = false; return true; }
    if (Math.abs(x) < 0.3) this._flickReady = true;
    return false;
  }
  // table handling: turn it about its centre, scale it about its centre, slide it (metres, relative to you)
  spin(a) { this._aboutCentre((p) => { p.applyAxisAngle(UP, a); this.stage.rotation.y += a; }); }
  zoom(k) { this._aboutCentre((p) => { p.multiplyScalar(k); this.stage.scale.multiplyScalar(k); }); }
  slide(right, forward) {
    const f = this._flat(this.head().forward), r = new THREE.Vector3(-f.z, 0, f.x);
    this.stage.position.addScaledVector(f, forward).addScaledVector(r, right);
  }
  _aboutCentre(fn) {
    this.stage.updateMatrixWorld(true);
    const c = this.stage.localToWorld((this._tableCentre || new THREE.Vector3()).clone());
    const p = this.stage.position.clone().sub(c);
    fn(p);
    this.stage.position.copy(c.add(p));
  }
  // where a ray (room coordinates) meets the stage's ground (y = 0): a stage point, or null
  groundHit(origin, dir) {
    this.stage.updateMatrixWorld(true);
    const inv = new THREE.Matrix4().copy(this.stage.matrixWorld).invert();
    const o = origin.clone().applyMatrix4(inv), d = dir.clone().transformDirection(inv);
    if (Math.abs(d.y) < 1e-6) return null;
    const k = -o.y / d.y;
    return k > 0 ? o.addScaledVector(d, k) : null;
  }
  // where you are, in stage units
  where() { this.stage.updateMatrixWorld(true); return this.stage.worldToLocal(this.head().position); }
}

// ---------------------------------------------------------------- controllers
// pads.poll() once a frame, then pads.hand('left' | 'right'): { x, y } stick (dead-zoned), pressed[i],
// edge(i) (went down this frame), released(i), ray { origin, dir } in room coordinates. Buttons: BTN.
const IDLE = { x: 0, y: 0, pressed: [], edge: () => false, released: () => false, ray: null };
export class Pads {
  constructor(renderer, scene, { deadZone = 0.15 } = {}) {
    this.renderer = renderer; this.deadZone = deadZone; this.prev = {}; this.hands = {};
    this.ctrls = [0, 1].map((i) => { const c = renderer.xr.getController(i); scene.add(c); return c; });
  }
  poll() {
    this.hands = {};
    const sess = this.renderer.xr.getSession();
    if (!sess) return;
    const dz = (v) => (Math.abs(v) > this.deadZone ? v : 0), q = new THREE.Quaternion();
    sess.inputSources.forEach((src, i) => {
      const gp = src.gamepad;
      if (!gp || !src.handedness) return;
      const h = src.handedness, b = gp.buttons.map((x) => x.pressed), was = this.prev[h] || [];
      const ax = gp.axes.length >= 4 ? gp.axes[2] : 0, ay = gp.axes.length >= 4 ? gp.axes[3] : 0;
      const ctrl = this.ctrls[i] || this.ctrls[0];
      q.setFromRotationMatrix(ctrl.matrixWorld);
      this.hands[h] = {
        x: dz(ax), y: dz(ay), pressed: b,
        edge: (k) => !!b[k] && !was[k], released: (k) => !b[k] && !!was[k],
        ray: { origin: new THREE.Vector3().setFromMatrixPosition(ctrl.matrixWorld), dir: new THREE.Vector3(0, 0, -1).applyQuaternion(q) },
      };
      this.prev[h] = b;
    });
  }
  hand(h) { return this.hands[h] || IDLE; }
}

// A thin laser from a controller to a point (room coordinates), for pointing: laser.show(from, to) / hide().
export function makeLaser(scene, hex = '#ff7a5a') {
  const mesh = new THREE.Mesh(new THREE.BoxGeometry(0.002, 0.002, 1), new THREE.MeshBasicNodeMaterial());
  mesh.material.colorNode = color(hex);
  mesh.visible = false;
  scene.add(mesh);
  return {
    mesh,
    show(from, to) { mesh.visible = true; mesh.position.copy(from).lerp(to, 0.5); mesh.lookAt(to); mesh.scale.z = from.distanceTo(to); },
    hide() { mesh.visible = false; },
  };
}

// ---------------------------------------------------------------- the desktop preview
// street: WASD walks where the camera looks, drag to look · table: drag to orbit, wheel to zoom. The camera
// moves here (only on the desktop: in a session the rig moves the world instead).
export class Desktop {
  constructor({ camera, dom, eyeHeight = 1.6, orbitTarget = new THREE.Vector3(0, 0.9, -0.45) }) {
    Object.assign(this, { camera, eyeHeight });
    this.mode = 'street';
    this.walker = { x: 0, z: 0, yaw: 0, pitch: -0.1 };
    this.orbit = { yaw: 0, pitch: 0.6, dist: 1.4, at: orbitTarget.clone() };
    this.keys = {};
    camera.rotation.order = 'YXZ';
    let drag = null;
    dom.addEventListener('pointerdown', (e) => { drag = [e.clientX, e.clientY]; });
    addEventListener('pointerup', () => { drag = null; });
    addEventListener('pointermove', (e) => {
      if (!drag) return;
      const dx = e.clientX - drag[0], dy = e.clientY - drag[1];
      drag = [e.clientX, e.clientY];
      if (this.mode === 'street') {
        this.walker.yaw -= dx * 0.004;
        this.walker.pitch = Math.min(1.2, Math.max(-1.3, this.walker.pitch - dy * 0.004));
      } else {
        this.orbit.yaw -= dx * 0.005;
        this.orbit.pitch = Math.min(1.4, Math.max(0.05, this.orbit.pitch + dy * 0.005));
      }
      this.apply();
    });
    addEventListener('wheel', (e) => {
      if (this.mode === 'street') return;
      this.orbit.dist = Math.min(8, Math.max(0.1, this.orbit.dist * Math.exp(e.deltaY * 0.001)));
      this.apply();
    });
    addEventListener('keydown', (e) => { this.keys[e.key.toLowerCase()] = true; });
    addEventListener('keyup', (e) => { this.keys[e.key.toLowerCase()] = false; });
  }
  setMode(mode) { this.mode = mode; if (mode === 'street') Object.assign(this.walker, { x: 0, z: 0, yaw: 0 }); this.apply(); }
  apply() {
    const c = this.camera;
    if (this.mode === 'street') {
      c.position.set(this.walker.x, this.eyeHeight, this.walker.z);
      c.rotation.set(this.walker.pitch, this.walker.yaw, 0);
    } else {
      const o = this.orbit;
      c.position.set(o.at.x + o.dist * Math.sin(o.yaw) * Math.cos(o.pitch), o.at.y + o.dist * Math.sin(o.pitch),
        o.at.z + o.dist * Math.cos(o.yaw) * Math.cos(o.pitch));
      c.lookAt(o.at);
    }
  }
  update(dt, speed = 3) {
    if (this.mode !== 'street') return;
    const k = this.keys, kx = (k.d ? 1 : 0) - (k.a ? 1 : 0), ky = (k.w ? 1 : 0) - (k.s ? 1 : 0);
    if (!kx && !ky) return;
    const w = this.walker, f = new THREE.Vector3(-Math.sin(w.yaw), 0, -Math.cos(w.yaw)), r = new THREE.Vector3(-f.z, 0, f.x);
    w.x += (f.x * ky + r.x * kx) * speed * dt; w.z += (f.z * ky + r.z * kx) * speed * dt;
    this.apply();
  }
}

// ---------------------------------------------------------------- a veil round your head
// For fades and flashes that must fill your view in a headset (a full-screen quad can't: there is no screen).
// veil.set(opacity, '#hex'); call veil.follow(rig.head().position) each frame.
export function makeVeil(scene) {
  const op = uniform(0), col = uniform(new THREE.Color(0, 0, 0));
  const mesh = new THREE.Mesh(new THREE.SphereGeometry(0.3, 16, 12), new THREE.MeshBasicNodeMaterial({
    side: THREE.BackSide, transparent: true, depthTest: false, depthWrite: false }));
  mesh.material.colorNode = col;
  mesh.material.opacityNode = op;
  mesh.renderOrder = 1e6;
  mesh.frustumCulled = false;
  mesh.visible = false;
  scene.add(mesh);
  return {
    mesh,
    set(opacity, hex = '#000000') { op.value = opacity; col.value.set(hex); mesh.visible = opacity > 0.001; },
    follow(p) { mesh.position.copy(p); },
  };
}
