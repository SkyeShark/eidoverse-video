// eidoverse/props/tandem.js
//
// DAISY finale prop: "a bicycle built for two".
//
// An 1890s safety tandem (the hero asset, modelled and baked in Blender: tandem.glb), a rider rig
// for the claudesona (claude_suit.vrm at scale 0.87) and the Utah-teapot stoker.
//
// The asset (eidoverse/assets/models/tandem_1896/tandem.glb) is built by the pack's
// blender/build_tandem.py (Blender 5.2, headless):
// lugged frame with cast lugs/brackets/crown, tangent-laced wheels with nipples, daisy-spider
// chainrings, rat-trap pedals, 1" block chain, sprung Brooks-pattern saddles, spoon brake and
// bell; layered PBR (AmbientCG sets + wear/edge/cavity/dust masks + gold lining) baked to atlases.
// Period reference photos (not distributed): 1896 Swift Tandem Safety, 1896/97 Columbia,
// 1895 Rambler, 1900 Royal Enfield (see the pack's SOURCES.md).
//
// Units: metres. Bike frame: +X = direction of travel, +Y up, +Z = the bike's right (drive) side,
// the camera side in a side shot. Wheels rest on y = 0; the origin is on the ground between the hubs.
//
// API
//   build(THREE, opts)            -> { group, parts, update(t, state), dispose(), layout, state }
//        opts.glb: GLB bytes (Uint8Array/ArrayBuffer, e.g. ASSETS.tandem), or opts.gltf (parsed);
//        without either, eidoverse/assets/models/tandem_1896/tandem.glb is read from disk
//        (resolved from this module's URL, independent of the working directory).
//   poseRider(vrm, crankAngle, o) -> pose report   (o.bike = the build() result, required)
//   buildTeapotRider(THREE, opts) -> { group, parts, update(t, crankAngle), mount(bike), dispose() }
//
// update(t, state): state.speed (m/s, number or fn(t)) or state.distance (m); optional state.steer
//   (rad about the steering axis), state.shutter (s; spoke motion blur, default half a frame).
//   Deterministic in t. Returns { distance, wheelAngle, crankAngle, speed }.
//   crankAngle: 0 = right pedal at 12 o'clock, increasing as the bike rolls forward (fixed wheel:
//   both cranks share it through the timing chain, and it is locked to the rear wheel).
//
// The film owns the root transform: move bike.group along +X by the returned distance.
// A VRM riding the tandem is carried by a vehicle: set globalThis._allowManualLocomotion = true.

const DEG = Math.PI / 180;
const TAU = Math.PI * 2;

// ─────────────────────────────────────────────────────────────────────────────
// build()
// ─────────────────────────────────────────────────────────────────────────────
export async function build(THREE, opts = {}) {
    const gltf = opts.gltf ?? await parseGLB(opts.glb ?? await readDefaultGLB());
    const scene = gltf.scene;
    const root = scene.getObjectByName('tandem') ?? scene;
    const extras = JSON.parse(root.userData?.daisy_tandem ?? findExtras(scene));
    const L = extras.layout;
    const group = new THREE.Group();
    group.name = 'tandem_1896';
    group.add(scene);
    const node = (n) => {
        const o = scene.getObjectByName(n);
        if (!o) throw new Error('tandem.glb: missing node ' + n);
        return o;
    };
    // NodeMaterials only on this stack: convert what GLTFLoader made, keeping every baked map
    const owned = [];
    const conv = new Map();
    scene.traverse((o) => {
        if (!o.isMesh) return;
        o.castShadow = true; o.receiveShadow = true;
        const m = o.material;
        if (!conv.has(m)) { const nm = toNodeMaterial(THREE, m); conv.set(m, nm); owned.push(nm); }
        o.material = conv.get(m);
    });

    const parts = {
        steering: node('steer'), frontWheel: node('wheel_front'), rearWheel: node('wheel_rear'),
        frontCrank: node('crank_front'), rearCrank: node('crank_rear'),
        frontPedalR: node('pedal_front_R'), frontPedalL: node('pedal_front_L'),
        rearPedalR: node('pedal_rear_R'), rearPedalL: node('pedal_rear_L'),
        frontSeat: node('seat_front'), rearSeat: node('seat_rear'),
        frontGripL: node('grip_front_L'), frontGripR: node('grip_front_R'),
        rearGripL: node('grip_rear_L'), rearGripR: node('grip_rear_R'),
    };
    // seat frames: a rider parented here faces the direction of travel (+X)
    parts.frontSeat.rotation.set(0, Math.PI / 2, 0);
    parts.rearSeat.rotation.set(0, Math.PI / 2, 0);
    // grip frames: local +Z along the handle, outboard; +Y up
    for (const [k, key] of [['frontGripL', 'front_L'], ['frontGripR', 'front_R'], ['rearGripL', 'rear_L'], ['rearGripR', 'rear_R']]) {
        const g = extras.grips[key];
        const z = new THREE.Vector3(...g.axis).normalize();
        const y = new THREE.Vector3(0, 1, 0).addScaledVector(z, -z.y).normalize();
        const x = new THREE.Vector3().crossVectors(y, z);
        parts[k].quaternion.setFromRotationMatrix(new THREE.Matrix4().makeBasis(x, y, z));
    }

    // spokes: smear through the shutter interval (no motion blur on this stack)
    const uSweep = THREE.uniform(0.0);
    for (const w of [parts.frontWheel, parts.rearWheel]) {
        w.traverse((o) => {
            if (o.isMesh && o.geometry.attributes._trail) {
                const sm = spokeMaterial(THREE, o.material, uSweep);
                owned.push(sm);
                o.material = sm;
                o.castShadow = true; o.receiveShadow = false;
                o.frustumCulled = false;
            }
        });
    }

    // chains: the one-pitch link from the GLB, instanced round each belt on the GPU
    let link = null;
    scene.traverse((o) => { if (o.isMesh && /chain/i.test(o.name) && !link) link = o; });
    if (!link) throw new Error('tandem.glb: no chain link mesh');
    link.visible = false;
    const timing = beltChain(THREE, link, extras.belts.timing, extras.belts.zTiming, 'T');
    const drive = beltChain(THREE, link, extras.belts.drive, extras.belts.zDrive, 'D');
    root.add(timing.mesh, drive.mesh);
    owned.push(timing.mesh.material, drive.mesh.material);
    parts.timingChain = timing.mesh; parts.driveChain = drive.mesh;

    // ── update ─────────────────────────────────────────────────────────────
    const axisV = new THREE.Vector3(L.axis[0], L.axis[1], 0).normalize();
    const pedals = [parts.frontPedalR, parts.frontPedalL, parts.rearPedalR, parts.rearPedalL];
    const integrate = (fn, t) => {
        if (t <= 0) return 0;
        const n = Math.max(16, Math.ceil(t * 30) * 2), h = t / n;
        let s = fn(0) + fn(t);
        for (let i = 1; i < n; i++) s += fn(i * h) * (i % 2 ? 4 : 2);
        return s * h / 3;
    };
    const gear = L.sprocketTeeth / L.driveTeeth;
    const api = { group, parts, layout: L, extras, THREE, state: null, gltf };
    api.update = (t, state = {}) => {
        let dist;
        if (typeof state.distance === 'number') dist = state.distance;
        else if (typeof state.speed === 'function') dist = integrate(state.speed, t);
        else dist = (state.speed ?? 0) * t;
        const speedNow = typeof state.speed === 'function' ? state.speed(t) : (state.speed ?? 0);
        const wheelAngle = dist / L.R;
        const crankAngle = (state.crankAngle ?? wheelAngle * gear) + (state.crankPhase ?? 0);
        parts.rearWheel.rotation.z = -wheelAngle;
        parts.frontWheel.rotation.z = -wheelAngle;
        parts.frontCrank.rotation.z = -crankAngle;
        parts.rearCrank.rotation.z = -crankAngle;
        for (const p of pedals) p.rotation.z = crankAngle;       // pedals hang level unless a sole pitches them
        timing.setPhase(crankAngle);
        drive.setPhase(crankAngle);
        const fps = globalThis.FPS || 60;
        const shutter = state.shutter ?? (0.5 / fps);
        uSweep.value = Math.max(-0.7, Math.min(0.7, (speedNow / L.R) * shutter));
        parts.steering.quaternion.setFromAxisAngle(axisV, state.steer ?? 0);
        api.state = { t, distance: dist, wheelAngle, crankAngle, speed: speedNow };
        return api.state;
    };
    api.setPedalPitch = (pedal, crankAngle, pitch) => { pedal.rotation.z = crankAngle - pitch; };
    api.dispose = () => {
        scene.traverse((o) => { if (o.isMesh) o.geometry.dispose(); });
        for (const m of owned) m.dispose?.();
        timing.mesh.geometry.dispose?.(); drive.mesh.geometry.dispose?.();
    };
    api.chains = { timing, drive };
    api.update(0, { speed: 0 });
    return api;
}

async function readDefaultGLB() {
    const url = new URL('../assets/models/tandem_1896/tandem.glb', import.meta.url);
    return await Deno.readFile(url);
}

async function parseGLB(bytes) {
    const buf = bytes instanceof ArrayBuffer ? bytes : bytes.buffer.slice(bytes.byteOffset, bytes.byteOffset + bytes.byteLength);
    const loader = new globalThis.GLTFLoader();
    return await new Promise((res, rej) => loader.parse(buf, '', res, rej));
}

function findExtras(scene) {
    let s = null;
    scene.traverse((o) => { if (!s && o.userData?.daisy_tandem) s = o.userData.daisy_tandem; });
    if (!s) throw new Error('tandem.glb: no daisy_tandem extras');
    return s;
}

function toNodeMaterial(THREE, m) {
    const n = new THREE.MeshPhysicalNodeMaterial();
    n.name = m.name;
    for (const k of ['map', 'normalMap', 'roughnessMap', 'metalnessMap', 'aoMap', 'emissiveMap', 'clearcoatMap', 'clearcoatRoughnessMap', 'clearcoatNormalMap']) {
        if (m[k]) n[k] = m[k];
    }
    n.color.copy(m.color);
    n.roughness = m.roughness; n.metalness = m.metalness;
    if (m.normalScale) n.normalScale.copy(m.normalScale);
    n.aoMapIntensity = m.aoMapIntensity ?? 1;
    if (m.emissive) n.emissive.copy(m.emissive);
    if (m.isMeshPhysicalMaterial) {
        n.clearcoat = m.clearcoat; n.clearcoatRoughness = m.clearcoatRoughness;
        if (m.clearcoatNormalScale) n.clearcoatNormalScale.copy(m.clearcoatNormalScale);
    }
    n.side = m.side;
    return n;
}

// The spokes carry a per-vertex `_trail` flag (which side of each wire trails a forward roll).
// Trailing vertices swing back by the angle the wheel turns while the shutter is open, and the
// coverage falls to wireWidth / sweptArc, so a spinning wheel reads as blurred wire, not a strobe.
function spokeMaterial(THREE, base, uSweep) {
    const T = THREE;
    const m = new T.MeshStandardNodeMaterial({ transparent: true, depthWrite: false });
    for (const k of ['map', 'aoMap']) if (base[k]) m[k] = base[k];
    // at rest: bright nickel wire; smeared: a soft haze that shades like the wheel disc (a smeared
    // cylinder keeps its wire normals, which glint as zigzag streaks)
    const smear = T.smoothstep(0.01, 0.08, T.abs(uSweep));
    // the axle on the wire's own side: a fixed +Z axle points away from a camera on the bike's left (-Z), where
    // mix(wireNormal, axle) passes through ~0 and normalize() returns NaN/sparkle
    const axle0 = T.transformNormalToView(T.vec3(0, 0, 1));
    const axle = axle0.mul(T.select(T.dot(T.normalViewGeometry, axle0).greaterThanEqual(0.0), T.float(1.0), T.float(-1.0)));
    m.normalNode = T.normalize(T.mix(T.normalViewGeometry, axle, smear));
    m.roughnessNode = T.mix(T.float(0.2), T.float(0.62), smear);
    m.metalnessNode = T.mix(T.float(1.0), T.float(0.45), smear);
    const trailA = T.attribute('_trail', 'float');
    const trail = T.select(uSweep.greaterThanEqual(0.0), trailA, T.float(1.0).sub(trailA));
    m.positionNode = T.Fn(() => {
        const p = T.positionLocal;
        const a = trail.mul(uSweep);
        const c = T.cos(a), s = T.sin(a);
        return T.vec3(p.x.mul(c).sub(p.y.mul(s)), p.x.mul(s).add(p.y.mul(c)), p.z);
    })();
    const rr = T.length(T.positionGeometry.xy).max(0.02);
    m.opacityNode = T.float(0.0021).div(T.float(0.0021).add(rr.mul(T.abs(uSweep))));
    // no mrtNode override: the engine's scene MRT already weights the normal/metal-rough
    // attachments by the material's alpha (and an override fails to compile on lit materials)
    return m;
}

// ─────────────────────────────────────────────────────────────────────────────
// Chains: each instance is one pitch (block + side plates) walked round the belt path
// (two tangent runs + two arcs) in the vertex shader from one uniform phase.
// ─────────────────────────────────────────────────────────────────────────────
function beltChain(THREE, linkMesh, belt, z, id) {
    const T = THREE;
    const { A, rA, B, rB, N, pp, sOff } = belt;
    const Ltot = belt.L;
    const dx = B[0] - A[0], dy = B[1] - A[1], D = Math.hypot(dx, dy);
    const u = [dx / D, dy / D], n = [-u[1], u[0]];
    const phi = Math.asin((rA - rB) / D);
    const Ls = D * Math.cos(phi);
    const arcB = rB * (Math.PI - 2 * phi);
    const angUp = Math.PI / 2 - phi, angLow = -angUp;
    const dirAt = (ang) => [u[0] * Math.cos(ang) + n[0] * Math.sin(ang), u[1] * Math.cos(ang) + n[1] * Math.sin(ang)];
    const mUp = dirAt(angUp), mLow = dirAt(angLow);
    const TAup = [A[0] + rA * mUp[0], A[1] + rA * mUp[1]];
    const TBup = [B[0] + rB * mUp[0], B[1] + rB * mUp[1]];
    const TBlow = [B[0] + rB * mLow[0], B[1] + rB * mLow[1]];
    const TAlow = [A[0] + rA * mLow[0], A[1] + rA * mLow[1]];
    const dUp = [(TBup[0] - TAup[0]) / Ls, (TBup[1] - TAup[1]) / Ls];
    const dLow = [(TAlow[0] - TBlow[0]) / Ls, (TAlow[1] - TBlow[1]) / Ls];
    const { Fn, float, vec2, vec3, If, cos, sin, mod, normalize, uniform, instanceIndex, positionGeometry, normalGeometry, transformNormalToView } = T;
    const cA = vec2(A[0], A[1]), cB = vec2(B[0], B[1]), uV = vec2(u[0], u[1]), nV = vec2(n[0], n[1]);
    const beltPoint = Fn(([s]) => {
        const out = vec2(0, 0).toVar();
        If(s.lessThan(Ls), () => {
            out.assign(vec2(TAup[0], TAup[1]).add(vec2(dUp[0], dUp[1]).mul(s)));
        }).ElseIf(s.lessThan(Ls + arcB), () => {
            const ang = float(angUp).sub(s.sub(Ls).div(rB));
            out.assign(cB.add(uV.mul(cos(ang)).add(nV.mul(sin(ang))).mul(rB)));
        }).ElseIf(s.lessThan(2 * Ls + arcB), () => {
            out.assign(vec2(TBlow[0], TBlow[1]).add(vec2(dLow[0], dLow[1]).mul(s.sub(Ls + arcB))));
        }).Else(() => {
            const ang = float(angLow).sub(s.sub(2 * Ls + arcB).div(rA));
            out.assign(cA.add(uV.mul(cos(ang)).add(nV.mul(sin(ang))).mul(rA)));
        });
        return out;
    }).setLayout({ name: 'daisyBelt' + id, type: 'vec2', inputs: [{ name: 's', type: 'float' }] });
    const uPhase = uniform(0.0);
    const linkS = float(instanceIndex).mul(pp);
    const frame = () => {
        const s0 = mod(linkS.add(uPhase), Ltot);
        const s1 = mod(s0.add(pp), Ltot);
        const p0 = beltPoint(s0), p1 = beltPoint(s1);
        const t = normalize(p1.sub(p0));
        return { p0, t, nn: vec2(t.y.negate(), t.x) };
    };
    const base = linkMesh.material;
    const mat = new T.MeshStandardNodeMaterial();
    for (const k of ['map', 'normalMap', 'roughnessMap', 'metalnessMap', 'aoMap']) if (base[k]) mat[k] = base[k];
    mat.roughness = base.roughness; mat.metalness = base.metalness;
    mat.positionNode = Fn(() => {
        const { p0, t, nn } = frame();
        const G = positionGeometry;
        const xy = p0.add(t.mul(G.x)).add(nn.mul(G.y));
        return vec3(xy.x, xy.y, G.z.add(z));
    })();
    mat.normalNode = transformNormalToView(Fn(() => {
        const { t, nn } = frame();
        const Ng = normalGeometry;
        const nxy = t.mul(Ng.x).add(nn.mul(Ng.y));
        return vec3(nxy.x, nxy.y, Ng.z);
    })()).toVarying();
    const mesh = new T.InstancedMesh(linkMesh.geometry, mat, N);
    const I = new T.Matrix4();
    for (let i = 0; i < N; i++) mesh.setMatrixAt(i, I);
    mesh.frustumCulled = false;
    mesh.castShadow = false; mesh.receiveShadow = true;
    mesh.name = 'chain_' + id;
    const setPhase = (crankAngle) => {
        const s = sOff + crankAngle * belt.teethB * pp / TAU;
        uPhase.value = ((s % Ltot) + Ltot) % Ltot;
    };
    return { mesh, setPhase, uPhase };
}

// ─────────────────────────────────────────────────────────────────────────────
// Rider rig for the claudesona (claude_suit.vrm, scale 0.87): analytic two-bone IK on the
// normalized humanoid bones, solved in the VRM's own frame (= the seat frame, in model units).
// ─────────────────────────────────────────────────────────────────────────────
const _rigs = new WeakMap();
const RIG_BONES = ['hips', 'spine', 'chest', 'upperChest', 'neck', 'head',
    'leftShoulder', 'leftUpperArm', 'leftLowerArm', 'leftHand', 'rightShoulder', 'rightUpperArm', 'rightLowerArm', 'rightHand',
    'leftUpperLeg', 'leftLowerLeg', 'leftFoot', 'leftToes', 'rightUpperLeg', 'rightLowerLeg', 'rightFoot', 'rightToes'];
const FINGERS = ['Index', 'Middle', 'Ring', 'Little'];
const PHAL = ['Proximal', 'Intermediate', 'Distal'];

function rigFor(vrm, bike, opts) {
    let R = _rigs.get(vrm);
    if (R && R.bike === bike) return R;
    const THREE = bike.THREE;
    const hum = vrm.humanoid;
    const node = {};
    for (const n of RIG_BONES) { const b = hum.getNormalizedBoneNode(n); if (b) node[n] = b; }
    for (const req of ['hips', 'leftUpperLeg', 'leftLowerLeg', 'leftFoot', 'rightUpperLeg', 'rightLowerLeg', 'rightFoot',
        'leftUpperArm', 'leftLowerArm', 'leftHand', 'rightUpperArm', 'rightLowerArm', 'rightHand']) {
        if (!node[req]) throw new Error('poseRider: VRM lacks humanoid bone ' + req);
    }
    const order = RIG_BONES.filter((n) => node[n]);
    const parent = {};
    for (const n of order) {
        let p = node[n].parent, hit = null;
        while (p && !hit) { hit = order.find((k) => node[k] === p) || null; p = p.parent; }
        parent[n] = hit;
    }
    const off = {};
    for (const n of order) off[n] = node[n].position.clone();
    const fingers = {};
    for (const side of ['left', 'right']) {
        for (const f of FINGERS) for (const ph of PHAL) {
            const b = hum.getNormalizedBoneNode(side + f + ph); if (b) fingers[side + f + ph] = b;
        }
        for (const ph of ['Metacarpal', 'Proximal', 'Distal']) {
            const b = hum.getNormalizedBoneNode(side + 'Thumb' + ph); if (b) fingers[side + 'Thumb' + ph] = b;
        }
    }
    R = { bike, THREE, node, order, parent, off, fingers };
    // seat the VRM: its root frame becomes the seat frame (+Z = direction of travel)
    const S = opts.scale ?? 0.87;
    R.S = S;
    bike.parts.frontSeat.add(vrm.scene);
    vrm.scene.position.set(0, 0, 0);
    vrm.scene.quaternion.identity();
    vrm.scene.scale.setScalar(S);
    (globalThis._seatedVRMs ||= new Set()).add(vrm.scene);
    // springs (flower mane, tie) simulate relative to the rider so the bike's travel doesn't
    // drag them. The tail would trail straight back into the stoker, so by default ('curl') it
    // leaves the spring solver and the rig carries it: up behind her like a contented cat.
    const sbm = vrm.springBoneManager;
    R.tailMode = opts.tail ?? 'curl';
    R.tail = [];
    if (sbm) {
        sbm.reset?.();
        for (const j of [...sbm.joints]) {
            if (R.tailMode === 'curl' && /tail/i.test(j.bone.name)) {
                sbm.deleteJoint(j);
                j.bone.matrixAutoUpdate = true;       // spring joints switch this off; the rig owns the bone now
                continue;
            }
            j.center = vrm.scene;
        }
        sbm.setInitState?.();
    }
    if (R.tailMode === 'curl') {
        let b = vrm.scene.getObjectByName('tail_2') || null;
        while (b) {
            R.tail.push({ bone: b, q0: b.quaternion.clone() });
            b = b.children.find((c) => /tail/i.test(c.name)) || null;
        }
    }
    _rigs.set(vrm, R);
    return R;
}

function frameQuat(THREE, d0, f0, d1, f1) {
    const a0 = d0.clone().normalize(), b0 = f0.clone().addScaledVector(a0, -f0.dot(a0)).normalize(), c0 = new THREE.Vector3().crossVectors(a0, b0);
    const a1 = d1.clone().normalize(), b1 = f1.clone().addScaledVector(a1, -f1.dot(a1)).normalize(), c1 = new THREE.Vector3().crossVectors(a1, b1);
    const M0 = new THREE.Matrix4().makeBasis(a0, b0, c0), M1 = new THREE.Matrix4().makeBasis(a1, b1, c1);
    return new THREE.Quaternion().setFromRotationMatrix(M1.multiply(M0.transpose()));
}

function twoBone(THREE, root, target, L1, L2, pole) {
    const d = target.clone().sub(root);
    const dist = d.length();
    const reach = Math.min((L1 + L2) * 0.9995, Math.max(Math.abs(L1 - L2) * 1.001 + 1e-4, dist));
    const a = d.divideScalar(dist || 1);
    const b = pole.clone().addScaledVector(a, -pole.dot(a));
    if (b.lengthSq() < 1e-10) b.set(0, 0, 1);
    b.normalize();
    const cosA = Math.min(1, Math.max(-1, (L1 * L1 + reach * reach - L2 * L2) / (2 * L1 * reach)));
    const sinA = Math.sqrt(1 - cosA * cosA);
    const dir1 = a.clone().multiplyScalar(cosA).addScaledVector(b, sinA);
    const mid = root.clone().addScaledVector(dir1, L1);
    const end = root.clone().addScaledVector(a, reach);
    const dir2 = end.clone().sub(mid).normalize();
    const hinge = new THREE.Vector3().crossVectors(a, b).normalize();
    return { dir1, dir2, mid, end, hinge, reach, dist, flex: Math.acos(Math.min(1, Math.max(-1, dir1.dot(dir2)))) };
}

// Ankling: toe-down pitch through the pedal stroke (theta: that pedal's crank angle, 0 at top).
export function anklePitch(theta, scale = 1) {
    return (13 + 10 * Math.cos(theta - 240 * DEG)) * DEG * scale;
}

export function poseRider(vrm, crankAngle, opts = {}) {
    const bike = opts.bike;
    if (!bike || !bike.parts) throw new Error('poseRider: pass { bike } (the tandem build() result)');
    const R = rigFor(vrm, bike, opts);
    const THREE = R.THREE;
    const V = THREE.Vector3, Q = THREE.Quaternion;
    const S = R.S;                                   // world metres -> model units: divide by S
    const t = opts.t ?? 0;
    const th = crankAngle;
    bike.group.updateWorldMatrix(true, true);
    const inv = new THREE.Matrix4().copy(vrm.scene.matrixWorld).invert();
    const invQ = new Q();
    { const p = new V(), s = new V(); inv.decompose(p, invQ, s); }
    const toModel = (obj) => new V().setFromMatrixPosition(obj.matrixWorld).applyMatrix4(inv);
    const X = new V(1, 0, 0), Y = new V(0, 1, 0), Z = new V(0, 0, 1);
    const qe = (x, y, z) => new Q().setFromEuler(new THREE.Euler(x, y, z, 'YXZ'));

    // ── torso ────────────────────────────────────────────────────────────
    const lean = opts.lean ?? 0.34;
    const sway = opts.sway ?? 1;
    const roll = 0.022 * Math.sin(th) * sway, yaw = 0.020 * Math.cos(th) * sway;
    const breathe = 0.010 * Math.sin(TAU * 0.27 * t);
    const lq = {};
    lq.hips = qe(lean * 0.42, yaw, roll);
    lq.spine = qe(lean * 0.22, -yaw * 0.7, -roll * 0.6);
    lq.chest = qe(lean * 0.20 + breathe, -yaw * 0.4, -roll * 0.3);
    lq.upperChest = qe(lean * 0.16 - breathe * 0.5, 0, 0);
    const nod = 0.010 * Math.sin(2 * th);
    lq.neck = qe(-lean * 0.34 + (opts.headPitch ?? 0) * 0.4, yaw * 0.3, roll * 0.3);
    lq.head = qe(-lean * 0.40 + nod + (opts.headPitch ?? 0) * 0.6 + 0.06, (opts.headYaw ?? 0) + yaw * 0.4, roll * 0.5);
    lq.leftShoulder = qe(0.0, -0.10, -0.04);
    lq.rightShoulder = qe(0.0, 0.10, 0.04);

    // pelvis: the hip-joint midpoint sits on the saddle at the fitted riding position
    const lay = bike.layout;
    const hipAbove = (opts.hipAboveSeat ?? (lay.hipTarget[1] - lay.frontSit[1])) / S;
    const hipFwd = (opts.hipForward ?? (lay.hipTarget[0] - lay.frontSit[0])) / S;
    const midOff = R.off.leftUpperLeg.clone().add(R.off.rightUpperLeg).multiplyScalar(0.5);
    const hipsPos = new V(0, hipAbove, hipFwd).sub(midOff.clone().applyQuaternion(lq.hips));
    hipsPos.y += (0.0015 / S) * Math.cos(2 * th);

    const W = {};
    const fkBone = (n) => {
        const p = R.parent[n];
        const lqn = lq[n] || new Q();
        if (!p) { W[n] = { p: hipsPos.clone(), q: lqn.clone() }; return; }
        W[n] = { p: R.off[n].clone().applyQuaternion(W[p].q).add(W[p].p), q: W[p].q.clone().multiply(lqn) };
    };
    for (const n of ['hips', 'spine', 'chest', 'upperChest', 'neck', 'head', 'leftShoulder', 'rightShoulder']) if (R.node[n]) fkBone(n);
    const childPos = (n) => { const p = R.parent[n]; return R.off[n].clone().applyQuaternion(W[p].q).add(W[p].p); };

    // ── legs ─────────────────────────────────────────────────────────────
    const legs = {};
    const pedalPitch = {};
    const pedalTop = (lay.pedalTop ?? 0.016) / S;
    const sole = (opts.sole ?? 0.0214) / S;           // claude_suit: toe joint sits 2.1 cm above the sole
    for (const side of ['left', 'right']) {
        const isR = side === 'right';
        const pedalObj = isR ? bike.parts.frontPedalR : bike.parts.frontPedalL;
        const thS = isR ? th : th + Math.PI;
        const phi = anklePitch(thS, opts.ankling ?? 1);
        pedalPitch[side] = phi;
        const toeOut = (isR ? -1 : 1) * (opts.toeOut ?? 3 * DEG);
        const qFoot = new Q().setFromAxisAngle(Y, toeOut).premultiply(new Q().setFromAxisAngle(X, phi));
        const pc = toModel(pedalObj);
        const up = Y.clone().applyQuaternion(qFoot);
        const ball = pc.clone().addScaledVector(up, pedalTop + sole).addScaledVector(Z.clone().applyQuaternion(qFoot), (opts.footForward ?? 0) / S);
        const toesOff = R.off[side + 'Toes'];
        const ankle = ball.clone().sub(toesOff.clone().applyQuaternion(qFoot));
        const ul = side + 'UpperLeg', ll = side + 'LowerLeg', ft = side + 'Foot';
        const hip = childPos(ul);
        const L1 = R.off[ll].length(), L2 = R.off[ft].length();
        const pole = new V(isR ? -0.10 : 0.10, 0.15, 1.0);
        const s = twoBone(THREE, hip, ankle, L1, L2, pole);
        const qThigh = frameQuat(THREE, R.off[ll], Z, s.dir1, new V().crossVectors(s.hinge, s.dir1));
        const qShin = frameQuat(THREE, R.off[ft], Z, s.dir2, new V().crossVectors(s.hinge, s.dir2));
        lq[ul] = W.hips.q.clone().invert().multiply(qThigh);
        lq[ll] = qThigh.clone().invert().multiply(qShin);
        lq[ft] = qShin.clone().invert().multiply(qFoot);
        if (R.node[side + 'Toes']) lq[side + 'Toes'] = new Q();
        legs[side] = { hip, knee: s.mid, ankle, ball, pedal: pc, flex: s.flex, reachErr: (s.dist - s.reach) * S, phi };
    }

    // ── arms: shoulder -> elbow -> wrist, hands wrapped on the grips ─────
    const arms = {};
    for (const side of ['left', 'right']) {
        const isR = side === 'right';
        const gripObj = isR ? bike.parts.frontGripR : bike.parts.frontGripL;
        const G = toModel(gripObj);
        const gq = new Q(); gripObj.getWorldQuaternion(gq);
        const gAxis = Z.clone().applyQuaternion(gq).applyQuaternion(invQ).normalize();
        const ua = side + 'UpperArm', la = side + 'LowerArm', hd = side + 'Hand';
        const shoulder = childPos(ua);
        const L1 = R.off[la].length(), L2 = R.off[hd].length();
        const pole = new V(isR ? -0.65 : 0.65, -0.55, -0.35);
        const along = (opts.gripAlong ?? 0.074) / S, palm = (opts.gripPalm ?? 0.028) / S;
        const drop = opts.wristDrop ?? 12 * DEG;
        // the hand continues the forearm (a straight wrist), wrapped round the grip; iterate twice
        let dH = Z.clone().multiplyScalar(Math.cos(0.8)).addScaledVector(Y, -Math.sin(0.8));
        let s = null, wrist = null, nP = null;
        for (let it = 0; it < 3; it++) {
            dH.addScaledVector(gAxis, -dH.dot(gAxis)).normalize();
            nP = new V().crossVectors(gAxis, dH).normalize();
            if (nP.y > 0) nP.negate();
            wrist = G.clone().addScaledVector(dH, -along).addScaledVector(nP, -palm);
            s = twoBone(THREE, shoulder, wrist, L1, L2, pole);
            const fore = s.dir2.clone();
            fore.addScaledVector(gAxis, -fore.dot(gAxis)).normalize();
            // pitch a little further down round the grip axis
            const c = Math.cos(drop), sn = Math.sin(drop);
            const cand = fore.clone().multiplyScalar(c).addScaledVector(new V().crossVectors(gAxis, fore), sn);
            const cand2 = fore.clone().multiplyScalar(c).addScaledVector(new V().crossVectors(gAxis, fore), -sn);
            dH = cand.y < cand2.y ? cand : cand2;
        }
        const back = new V(0, 0, -1);
        const qUpper = frameQuat(THREE, R.off[la], back, s.dir1, new V().crossVectors(s.hinge, s.dir1));
        const qFore = frameQuat(THREE, R.off[hd], back, s.dir2, new V().crossVectors(s.hinge, s.dir2));
        const qHand = frameQuat(THREE, R.off[hd], new V(0, -1, 0), dH, nP);
        const parentQ = W[R.parent[ua]].q;
        lq[ua] = parentQ.clone().invert().multiply(qUpper);
        // share the wrist twist with the forearm so the skin doesn't candy-wrap
        const qForeLocal = qUpper.clone().invert().multiply(qFore);
        const qHandLocal = qFore.clone().invert().multiply(qHand);
        const tAxis = R.off[hd].clone().normalize();
        const r = new V(qHandLocal.x, qHandLocal.y, qHandLocal.z);
        const pr = tAxis.clone().multiplyScalar(r.dot(tAxis));
        const tw = new Q(pr.x, pr.y, pr.z, qHandLocal.w).normalize();
        const half = new Q().slerp(tw, 0.5);
        lq[la] = qForeLocal.clone().multiply(half);
        lq[hd] = half.clone().invert().multiply(qHandLocal);
        arms[side] = { shoulder, elbow: s.mid, wrist, grip: G, flex: s.flex, reachErr: (s.dist - s.reach) * S };
    }

    // ── fingers close round the handle ────────────────────────────────────
    const curl = opts.fingerCurl ?? 1;
    const sgn = { left: -1, right: 1 };
    const seg = { Proximal: 1.05, Intermediate: 1.20, Distal: 0.75 };
    for (const side of ['left', 'right']) {
        for (const f of FINGERS) for (const ph of PHAL) {
            const b = R.fingers[side + f + ph];
            if (b) b.quaternion.setFromAxisAngle(Z, sgn[side] * seg[ph] * curl);
        }
        const t1 = R.fingers[side + 'ThumbMetacarpal'], t2 = R.fingers[side + 'ThumbProximal'], t3 = R.fingers[side + 'ThumbDistal'];
        if (t1) t1.quaternion.setFromEuler(new THREE.Euler(0.25 * curl, sgn[side] * -0.25 * curl, sgn[side] * 0.35 * curl));
        if (t2) t2.quaternion.setFromAxisAngle(Z, sgn[side] * 0.45 * curl);
        if (t3) t3.quaternion.setFromAxisAngle(Z, sgn[side] * 0.55 * curl);
    }

    // ── write the pose (normalized bones), transfer to raw now so it lands this frame ──
    for (const n of R.order) {
        const q = lq[n];
        if (q) R.node[n].quaternion.copy(q);
    }
    R.node.hips.position.copy(hipsPos);
    vrm.humanoid.update();
    if (R.tail.length > 1) poseTail(R, vrm, th, t, opts);
    if (!R.settled && vrm.springBoneManager && (opts.settle ?? true)) {
        // pre-roll the springs in this pose (deterministic; nothing is rendered) so the mane and tie
        // don't swing from the T-pose into place on camera
        vrm.scene.updateWorldMatrix(true, true);
        for (let k = 0; k < 120; k++) vrm.springBoneManager.update(1 / 60);
        R.settled = true;
    }
    bike.setPedalPitch(bike.parts.frontPedalR, th, pedalPitch.right);
    bike.setPedalPitch(bike.parts.frontPedalL, th, pedalPitch.left);
    return { legs, arms, hipsPos };
}

// Tail (raw, non-humanoid bones): aim each segment along a rising arc in the rider's frame,
// with a small sway that travels down the tail twice per crank turn. World-space aiming against
// each parent's current rotation, so it composes with whatever the hips are doing.
function poseTail(R, vrm, th, t, opts) {
    const THREE = R.THREE;
    const V = THREE.Vector3, Q = THREE.Quaternion;
    vrm.scene.updateWorldMatrix(true, true);
    const sq = vrm.scene.getWorldQuaternion(new Q());
    const n = R.tail.length;
    const lift = opts.tailLift ?? 1;
    for (let k = 0; k < n - 1; k++) {
        const { bone, q0 } = R.tail[k];
        const child = R.tail[k + 1].bone;
        const u = k / Math.max(1, n - 2);
        const alpha = (22 + 92 * Math.pow(u, 0.7)) * DEG * lift;            // back, then rising close behind her
        const sway = 0.16 * u * u * Math.sin(2 * th - 1.1 * k) + 0.05 * u * Math.sin(TAU * 0.21 * t);
        const dModel = new V(sway, Math.sin(alpha), -Math.cos(alpha)).normalize();
        const dWorld = dModel.applyQuaternion(sq);
        const pq = bone.parent.getWorldQuaternion(new Q());
        const restWorld = pq.clone().multiply(q0);
        const cur = child.position.clone().applyQuaternion(restWorld).normalize();
        const delta = new Q().setFromUnitVectors(cur, dWorld);
        const want = delta.multiply(restWorld);
        bone.quaternion.copy(pq.invert().multiply(want));
        bone.updateMatrix();
        bone.updateWorldMatrix(false, true);
    }
}

// ─────────────────────────────────────────────────────────────────────────────
// The Utah teapot stoker (Newell's original proportions, blinn = false)
// ─────────────────────────────────────────────────────────────────────────────
export async function buildTeapotRider(THREE, opts = {}) {
    const { TeapotGeometry } = await import('npm:three@0.184.0/addons/geometries/TeapotGeometry.js');
    const T = THREE;
    const H = opts.height ?? 0.35, seg = opts.segments ?? 20;
    const body = new TeapotGeometry(1, seg, true, false, true, true, false);
    const lid = new TeapotGeometry(1, seg, false, true, false, true, false);
    body.computeBoundingBox(); lid.computeBoundingBox();
    const bb = body.boundingBox.clone().union(lid.boundingBox);
    const s = H / (bb.max.y - bb.min.y);
    for (const g of [body, lid]) {
        g.translate(0, -bb.min.y, 0);
        g.scale(s, s, s);
        g.rotateY(-Math.PI / 2);                 // spout (+X) now points +Z: forward on the seat
    }
    lid.computeBoundingBox();
    const lidBase = new T.Vector3((lid.boundingBox.min.x + lid.boundingBox.max.x) / 2, lid.boundingBox.min.y, (lid.boundingBox.min.z + lid.boundingBox.max.z) / 2);
    lid.translate(-lidBase.x, -lidBase.y, -lidBase.z);
    // glazed ceramic, classic cream, fine crazing in the glaze
    const { vec3, float, mix, smoothstep, oneMinus, sqrt, max, length, positionView, clamp } = T;
    const P = T.positionGeometry;
    const C = (hex) => { const c = new T.Color(hex); return vec3(c.r, c.g, c.b); };
    const n01 = (x) => x.mul(0.5).add(0.5);
    const px = max(length(positionView.dFdx()), length(positionView.dFdy()));
    const mat = new T.MeshPhysicalNodeMaterial({ roughness: 0.3, clearcoat: 1, clearcoatRoughness: 0.05, side: T.DoubleSide });
    {
        const w1 = T.mx_worley_noise_vec2(P.mul(1.0 / 0.018));
        const c1 = oneMinus(smoothstep(0.0, 0.045, sqrt(w1.y).sub(sqrt(w1.x)))).mul(smoothstep(0.0045, 0.0015, px));
        const w2 = T.mx_worley_noise_vec2(P.mul(1.0 / 0.0065).add(vec3(5.1, 2.3, 7.7)));
        const c2 = oneMinus(smoothstep(0.0, 0.04, sqrt(w2.y).sub(sqrt(w2.x)))).mul(smoothstep(0.0018, 0.0006, px));
        const craze = max(c1, c2.mul(0.55));
        const mott = n01(T.mx_fractal_noise_float(P.mul(9.0), 3, 2.0, 0.5, 1.0));
        const foot = smoothstep(0.012, 0.0, P.y);
        let col = mix(C(opts.color ?? 0xe0cc9f), C(0xc5a978), mott.mul(0.28));
        col = mix(col, C(0x7a5a3a), craze.mul(0.32));
        col = mix(col, C(0xb09a7c), foot.mul(0.7));
        mat.colorNode = col;
        mat.roughnessNode = float(0.30).add(craze.mul(0.2)).add(foot.mul(0.4));
        mat.clearcoatNode = oneMinus(foot);
        mat.clearcoatRoughnessNode = clamp(float(0.045).add(craze.mul(0.1)).add(mott.mul(0.03)), 0.02, 1.0);
    }
    const group = new T.Group(); group.name = 'teapot_rider';
    const tilt = new T.Group(); group.add(tilt);
    const bob = new T.Group(); tilt.add(bob);
    const mBody = new T.Mesh(body, mat); mBody.castShadow = true; mBody.receiveShadow = true; mBody.name = 'teapot_body';
    const lidPivot = new T.Group(); lidPivot.position.copy(lidBase);
    const mLid = new T.Mesh(lid, mat); mLid.castShadow = true; mLid.receiveShadow = true; mLid.name = 'teapot_lid';
    lidPivot.add(mLid);
    bob.add(mBody, lidPivot);
    tilt.rotation.set(opts.pitch ?? -0.035, 0, opts.roll ?? 0.055);    // upright, a little jaunty
    const api = { group, parts: { tilt, bob, body: mBody, lid: mLid, lidPivot }, height: H };
    api.update = (t, crankAngle = 0) => {
        const th = crankAngle;
        bob.position.y = 0.0028 * (0.5 - 0.5 * Math.cos(2 * th));
        bob.rotation.z = 0.018 * Math.sin(th);
        bob.rotation.x = 0.012 * Math.sin(2 * th + 0.8);
        const rattle = Math.pow(Math.max(0, Math.sin(2 * th + 1.3)), 6);
        lidPivot.position.y = lidBase.y + 0.0011 * rattle;
        mLid.rotation.y = 0.025 * Math.sin(2 * th);
    };
    api.mount = (bike) => {
        bike.parts.rearSeat.add(group);
        group.position.set(0, opts.contact ?? 0.0005, opts.seatOffset ?? -0.004);
        return api;
    };
    api.dispose = () => { body.dispose(); lid.dispose(); mat.dispose(); };
    api.update(0, 0);
    return api;
}
