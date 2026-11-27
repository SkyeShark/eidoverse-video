// eidoverse/crowd.js — crowds and marching columns of any VRM: one donor body's poses baked ONCE into a vertex-animation
// texture (VAT), drawn instanced, every body's pose and place worked out on the GPU from the frame number. The three.js
// edition's port of the Blender edition's eidoblend.characters.crowd (its Geometry Nodes flipbook), its clocks the same
// numbers. Dynamic ESM; import it inside setup():
//
//   const CROWD = await import(new URL('crowd.js', EIDOVERSE_DIR).href);
//   const lamp = CROWD.heldProp(THREE, lanternObject3D, { bone: 'rightHand', grip: 'fist', hang: true });
//   const cyc = await CROWD.strideCycle(THREE, vrm, walkClip, { fps: 24, bpm: 116, posesPerFrame: 2, props: [lamp],
//                                        curl: { right: 80 }, face: { happy: 1 } });       // ONE stride, baked
//   const pts = CROWD.formation({ files: 3, ranks: 12, interval: 0.85, distance: 1.05, origin: [0, 0, 0], heading: 90,
//                                 jitter: { lateral: 0.03, along: 0.05, phase: 0.03, seed: 11 } });
//   const column = CROWD.crowd(THREE, 'column', pts, CROWD.columnGroup(cyc, { refFrame: 1, show: [10, 400] }));
//   scene.add(column.group);
//   const wave = await CROWD.onceFlipbook(THREE, vrm, waveClip, { fps: 24, every: 2 });
//   const g = CROWD.grid({ lines: 2, units: 5, linePitch: 2.2, unitPitch: 1.25, origin: [0, 0, -14] });
//   const canon = CROWD.crowd(THREE, 'wave', g, CROWD.onceGroup(wave, { hold: [64, 24] }),
//                             { starts: CROWD.canonStarts(g, { first: 12, stepLine: 10, stepUnit: 4 }) });
//   per frame: column.update(frame); canon.update(frame)        (frame: the film's frame number, at the bake's fps)
//
// THE DONOR    one body of the VRM, posed once per pose: a stride of a locomotion clip, a stationary loop or a one-shot
//              clip, its fingers closed round a handle (curl: degrees per hand in the VRM's normalized frame), its face's
//              expressions held (face), held props in a hand. perPose(vrm, dt) runs after the clip on every pose: the
//              place for a body's own pass (claude_robot_dof.js for the robot body). Every body of the crowd is that
//              body doing that thing, set apart by its place, its phase and its start.
// THE FLIPBOOK every pose is the donor's skinned, morphed meshes as they stand, in the pose's own frame, written into one
//              float texture (positions) and one half-float texture (normals): rows of 4096 vertices, a block of rows a
//              pose. Every layer is the donor's own mesh and material, its vertices read from the texture by their index.
// THE STRIDE   strideCycle samples one cycle of the clip at N = posesPerFrame x the stride's film frames (a stride is two
//              beats: the left heel strikes on beats one and three, the right on two and four; the film frames are
//              rounded to whole poses, so every film frame shows every posesPerFrame-th pose and no body ever hitches),
//              from the pose its left heel strikes on. The clip plays in place (its hips' own travel along the walk, if
//              any, is taken out), and the Blender edition's walk is reproduced in the bake: the treadmill's speed is the
//              stance ankle's; the stance is the flat core grown through the heel's and the ball's rockers; the root
//              follows the stance feet's contact (shared through the double support): travel, sway and height, lightly
//              smoothed, so S (the stride) is the support's travel over a loop; and each planted foot's ankle is moved
//              by two-bone IK so its contact holds still on the floor (a foot in the air eases back to the clip's path
//              by its next strike). The poses are in a frame that moves forward at S a stride, and the instancer
//              carries a body forward S x k / N for the k-th pose it shows: every planted foot stays where it landed.
//              The record: S, the frames, the tempo used, the heel strikes, the double support, the seam, the IK's miss.
// THE CLOCKS   column (a cycle): phase = (frame + frameOffset - refFrame) / strideFrames + dphase; k = floor(N x phase
//              + 0.5); the pose k mod N; carried S x k / N along its heading. once (a one-shot): the pose clamp(floor(
//              (frame - start) / every), 0, N - 1). Both: show [from, to] (outside, nothing is drawn), the hold [from,
//              frames] (every body stops on its first frame, holds that pose so many frames, and carries on from where it
//              held) and each point's own stop (from that frame on it holds for good). The vertex shader runs them;
//              crowd.poseOf(i, frame) is the same arithmetic on the CPU.
// THE POINTS   formation (files abreast at an interval, ranks at a distance, jitter in spacing and phase), grid (lines of
//              units side by side) and canonStarts; heading 0 faces +Z (a VRM's front), degrees about +Y.
// Limits: the poses are rigid, so a crowd walks on level ground (each point's y is its floor's height) and in straight
// lines; transparent layers are not sorted body by body.

export const FAR = 1.0e9;
const FINGERS = ['Thumb', 'Index', 'Middle', 'Ring', 'Little'];
const JOINTS = { Thumb: ['Metacarpal', 'Proximal', 'Distal'], Index: ['Proximal', 'Intermediate', 'Distal'], Middle: ['Proximal', 'Intermediate', 'Distal'],
    Ring: ['Proximal', 'Intermediate', 'Distal'], Little: ['Proximal', 'Intermediate', 'Distal'] };
const ROW = 4096;

// a seeded uniform stream for the jitter (mulberry32)
function stream(seed) {
    let a = seed >>> 0;
    return () => { a = (a + 0x6D2B79F5) >>> 0; let t = a; t = Math.imul(t ^ (t >>> 15), t | 1); t ^= t + Math.imul(t ^ (t >>> 7), t | 61); return ((t ^ (t >>> 14)) >>> 0) / 4294967296; };
}

// three's mixer writes a bone only when its mixed value changed, so after a pose reset a held key would leave its bone
// at rest: write every active binding's value from the accumulator the update just filled
function writeAll(mixer) {
    const b = mixer._bindings, n = mixer._nActiveBindings, k = mixer._accuIndex + 1;
    for (let i = 0; i < n; i++) b[i].binding.setValue(b[i].buffer, k * b[i].valueSize);
}

// ------------------------------------------------------------------------------------------------------ the props
// a prop held in one hand: source (any Object3D made at its own origin: a mesh, or a group of meshes), bone (a humanoid
// hand bone), grip: the prop's origin in the bone's frame ([x, y, z], or [[x, y, z], [rx, ry, rz] degrees], a Matrix4)
// or 'fist': the middle of the four fingers' middle joints, inside a hand closed by curl. hang: true keeps it plumb (a
// lantern by its bail, a bag, a bucket): only the grip point follows the hand, its axes the pose frame's (+Y up, +Z the
// body's front) turned `turn` degrees about +Y; else it turns with the hand (a flag's pole, a tool)
export function heldProp(THREE, source, { bone = 'rightHand', grip = null, hang = false, turn = 0.0, name = null } = {}) {
    let G = new THREE.Matrix4();
    const fist = grip === 'fist';
    if (grip && !fist) {
        if (grip.isMatrix4) G = grip.clone();
        else if (typeof grip[0] === 'number') G.makeTranslation(grip[0], grip[1], grip[2]);
        else {
            const [loc, rot] = grip;
            G.makeRotationFromEuler(new THREE.Euler(...rot.map((d) => d * Math.PI / 180), 'XYZ')).setPosition(...loc);
        }
    }
    return { source, bone, grip: G, fist, hang, turn, name: name || source.name || 'prop' };
}

function propMatrix(THREE, vrm, p, poseInv) {
    const node = vrm.humanoid.getRawBoneNode(p.bone);
    if (!node) throw new Error(`crowd.heldProp: the VRM has no bone ${p.bone}`);
    const W = node.matrixWorld.clone().multiply(p.grip);
    if (p.fist) {
        const side = p.bone.startsWith('left') ? 'left' : 'right';
        const heads = ['Index', 'Middle', 'Ring', 'Little'].map((f) => vrm.humanoid.getRawBoneNode(`${side}${f}Intermediate`)).filter(Boolean)
            .map((b) => new THREE.Vector3().setFromMatrixPosition(b.matrixWorld));
        if (heads.length) W.setPosition(heads.reduce((s, v) => s.add(v), new THREE.Vector3()).multiplyScalar(1 / heads.length));
    }
    if (!p.hang) return poseInv.clone().multiply(W);
    const at = new THREE.Vector3().setFromMatrixPosition(W).applyMatrix4(poseInv);
    return new THREE.Matrix4().makeRotationY(p.turn * Math.PI / 180).setPosition(at);
}

// ------------------------------------------------------------------------------------------------------ the hands
// close a hand round a handle: each finger joint of the side's hand turned `deg` toward the palm (the thumb `thumb`
// times as far), in the VRM's normalized frame (the T-pose: the fingers along -X right / +X left, the palm down)
export function curlFingers(THREE, vrm, curl, thumb = 0.6) {
    for (const [side, deg] of Object.entries(curl || {})) {
        const sign = side === 'right' ? 1.0 : -1.0;
        for (const f of FINGERS) for (const j of JOINTS[f]) {
            const b = vrm.humanoid.getNormalizedBoneNode(`${side}${f}${j}`);
            if (!b) continue;
            const a = deg * Math.PI / 180 * (f === 'Thumb' ? thumb : 1.0);
            const axis = f === 'Thumb' ? new THREE.Vector3(0, -sign, 0) : new THREE.Vector3(0, 0, sign);
            b.quaternion.setFromAxisAngle(axis, a);
        }
    }
}

// ------------------------------------------------------------------------------------------------------ the bake
// the donor's rendered meshes and how to skin them on the CPU (the bake reads the pose the clip and perPose left)
function donorLayers(THREE, vrm) {
    const out = [];
    let base = 0;
    vrm.scene.updateMatrixWorld(true);
    vrm.scene.traverse((m) => {
        if (!m.isMesh || !m.visible) return;
        let hidden = false;
        for (let p = m; p; p = p.parent) if (p.visible === false) hidden = true;
        if (hidden) return;
        const g = m.geometry;
        const n = g.attributes.position.count;
        out.push({ mesh: m, n, base, skinned: !!m.isSkinnedMesh, pos: g.attributes.position, nrm: g.attributes.normal,
            si: g.attributes.skinIndex, sw: g.attributes.skinWeight, mp: g.morphAttributes.position || null, mn: g.morphAttributes.normal || null,
            rel: g.morphTargetsRelative });
        base += n;
    });
    return { layers: out, verts: base };
}

// the donor's vertices as they stand, in the frame `poseInv` takes the world into -> (positions, normals) written at
// each layer's base, 4 floats a vertex
function skinPose(THREE, D, poseInv, P, N) {
    const M = new THREE.Matrix4(), K = [], v = new THREE.Vector3(), nn = new THREE.Vector3();
    for (const L of D.layers) {
        const m = L.mesh;
        const toPose = poseInv.clone().multiply(m.matrixWorld);
        K.length = 0;
        if (L.skinned) {
            m.skeleton.update();
            const bm = m.skeleton.boneMatrices;
            for (let j = 0; j < m.skeleton.bones.length; j++) {
                M.fromArray(bm, j * 16);
                K.push(toPose.clone().multiply(m.bindMatrixInverse).multiply(M).multiply(m.bindMatrix));
            }
        }
        const infl = m.morphTargetInfluences || [];
        const e = new Float64Array(16), en = new Float64Array(9);
        for (let i = 0; i < L.n; i++) {
            let x = L.pos.getX(i), y = L.pos.getY(i), z = L.pos.getZ(i);
            let nx = L.nrm ? L.nrm.getX(i) : 0, ny = L.nrm ? L.nrm.getY(i) : 1, nz = L.nrm ? L.nrm.getZ(i) : 0;
            if (L.mp) {
                for (let t = 0; t < infl.length; t++) {
                    const w = infl[t];
                    if (!w) continue;
                    const a = L.mp[t];
                    if (L.rel) { x += w * a.getX(i); y += w * a.getY(i); z += w * a.getZ(i); }
                    else { x += w * (a.getX(i) - L.pos.getX(i)); y += w * (a.getY(i) - L.pos.getY(i)); z += w * (a.getZ(i) - L.pos.getZ(i)); }
                    if (L.mn && L.mn[t]) { const b = L.mn[t]; nx += w * b.getX(i); ny += w * b.getY(i); nz += w * b.getZ(i); }
                }
            }
            if (L.skinned) {
                e.fill(0);
                for (let k = 0; k < 4; k++) {
                    const w = L.sw.getComponent(i, k);
                    if (!w) continue;
                    const me = K[L.si.getComponent(i, k)].elements;
                    for (let q = 0; q < 16; q++) e[q] += w * me[q];
                }
                v.set(e[0] * x + e[4] * y + e[8] * z + e[12], e[1] * x + e[5] * y + e[9] * z + e[13], e[2] * x + e[6] * y + e[10] * z + e[14]);
                nn.set(e[0] * nx + e[4] * ny + e[8] * nz, e[1] * nx + e[5] * ny + e[9] * nz, e[2] * nx + e[6] * ny + e[10] * nz);
            } else {
                const me = toPose.elements;
                v.set(x, y, z).applyMatrix4(toPose);
                nn.set(me[0] * nx + me[4] * ny + me[8] * nz, me[1] * nx + me[5] * ny + me[9] * nz, me[2] * nx + me[6] * ny + me[10] * nz);
            }
            nn.normalize();
            const o = (L.base + i) * 4;
            P[o] = v.x; P[o + 1] = v.y; P[o + 2] = v.z; P[o + 3] = 1.0;
            N[o] = nn.x; N[o + 1] = nn.y; N[o + 2] = nn.z; N[o + 3] = 0.0;
        }
    }
}

// a baked flipbook: name, kind ('cycle' | 'once'), poses N, stride (m a cycle; 0 in place), strideFrames, every,
// the textures, the donor's layers (geometry + material), the props' matrices a pose, record
function makeFlipbook(THREE, D, poses, props, name, kind, record) {
    const rows = Math.ceil(D.verts / ROW);
    const N = poses.length;
    const P = new Float32Array(ROW * rows * N * 4), Nn = new Uint16Array(ROW * rows * N * 4);
    const half = THREE.DataUtils.toHalfFloat;
    poses.forEach(([pp, pn], k) => {
        P.set(pp, k * rows * ROW * 4);
        const o = k * rows * ROW * 4;
        for (let i = 0; i < pn.length; i++) Nn[o + i] = half(pn[i]);
    });
    // (the eidoverse/data/ label: the renderer's device keeps such a float texture's bytes and precision; any other
    // rgba32float texture is taken for a render target and halved, render_common.mjs)
    const tex = (data, type, what) => {
        const t = new THREE.DataTexture(data, ROW, rows * N, THREE.RGBAFormat, type);
        t.name = `eidoverse/data/crowd-${name}-${what}`;
        t.minFilter = t.magFilter = THREE.NearestFilter;
        t.generateMipmaps = false;
        t.needsUpdate = true;
        return t;
    };
    const fb = { name, kind, poses: N, rows, verts: D.verts, posTex: tex(P, THREE.FloatType, 'positions'), nrmTex: tex(Nn, THREE.HalfFloatType, 'normals'),
        layers: [], props: [], record };
    for (const L of D.layers) {
        const g = new THREE.BufferGeometry();
        const src = L.mesh.geometry;
        for (const [k, a] of Object.entries(src.attributes)) if (!['skinIndex', 'skinWeight'].includes(k)) g.setAttribute(k, a);
        if (src.index) g.setIndex(src.index);
        for (const gr of src.groups) g.addGroup(gr.start, gr.count, gr.materialIndex);
        const vid = new Float32Array(L.n);
        for (let i = 0; i < L.n; i++) vid[i] = L.base + i;
        g.setAttribute('crowdVid', new THREE.BufferAttribute(vid, 1));
        fb.layers.push({ geometry: g, material: L.mesh.material, name: L.mesh.name });
    }
    for (const p of props) {
        const mats = new Float32Array(N * 16);
        p.matrices.forEach((m, k) => mats.set(m.elements, k * 16));
        const t = new THREE.DataTexture(mats, 4, N, THREE.RGBAFormat, THREE.FloatType);
        t.name = `eidoverse/data/crowd-${name}-${p.prop.name || 'prop'}`;
        t.minFilter = t.magFilter = THREE.NearestFilter; t.generateMipmaps = false; t.needsUpdate = true;
        fb.props.push({ name: p.prop.name, source: p.prop.source, tex: t, matrices: p.matrices });
    }
    fb.stride = record.stride_m || 0.0;
    fb.strideFrames = record.stride_frames || 0.0;
    fb.every = record.every || 1.0;
    // the CPU's copy of the positions, for the checks
    fb._P = P;
    return fb;
}

// the clip on the donor: a mixer of its own; pose(t) puts the body at clip time t (the reset, the clip, writeAll, the
// fingers, the face, perPose), the spring bones stepped by dt
function driver(THREE, vrm, clip, { curl = null, face = null, perPose = null, prePose = null, post = null } = {}) {
    const mixer = new THREE.AnimationMixer(vrm.scene);
    const action = mixer.clipAction(clip);
    action.play();
    return (t, dt) => {
        vrm.humanoid.resetNormalizedPose();
        if (prePose) prePose(vrm, dt);
        action.time = t;
        mixer.update(0);
        writeAll(mixer);
        if (curl) curlFingers(THREE, vrm, curl);
        if (face && vrm.expressionManager) for (const [k, w] of Object.entries(face)) vrm.expressionManager.setValue(k, w);
        if (perPose) perPose(vrm, dt);
        if (post) post(vrm);
        vrm.update(dt);
        vrm.scene.updateMatrixWorld(true);
    };
}

const SIDES = ['left', 'right'];
const CLEARANCE = 0.03;          // the swing sole's least height over the floor, mid-swing (m)
const smooth = (a, b, x) => { const t = Math.min(1, Math.max(0, (x - a) / (b - a))); return t * t * (3 - 2 * t); };
const bump = (u) => smooth(0.0, 0.3, u) * (1.0 - smooth(0.75, 1.0, u));   // 0 at the lift and the landing, 1 between
const TREAD_TOL = 0.35;          // a low sole point moving within this fraction of the treadmill's speed is planted
const LOCK_BAND = 0.0005;        // the contact's weighting: points this much above the sole's lowest count e^-1 as much
const median = (a) => {
    const b = Float64Array.from(a).sort();
    const n = b.length;
    return n ? (n % 2 ? b[n >> 1] : 0.5 * (b[n / 2 - 1] + b[n / 2])) : 0.0;
};
// a Hann-window moving average of a periodic array, radius r samples
function hann(x, r) {
    if (r <= 0) return Float64Array.from(x);
    const w = [];
    for (let k = -r; k <= r; k++) w.push(0.5 - 0.5 * Math.cos(2.0 * Math.PI * (k + r + 1) / (2 * r + 2)));
    const sw = w.reduce((s, q) => s + q, 0), n = x.length, out = new Float64Array(n);
    for (let i = 0; i < n; i++) for (let k = -r; k <= r; k++) out[i] += w[k + r] / sw * x[(((i + k) % n) + n) % n];
    return out;
}
// drop runs (true or false) shorter than minRun samples, periodic
function cleanMask(m, minRun) {
    m = m.slice();
    const n = m.length;
    for (let it = 0; it < 2; it++) {
        for (const val of [true, false]) {
            const runs = [];
            let start = null;
            for (let k = 0; k < 2 * n; k++) {
                const x = m[k % n];
                if (x === val && start === null) start = k;
                if (x !== val && start !== null) { runs.push([start, k]); start = null; }
            }
            for (const [a, b] of runs) if (b - a < minRun && a < n) for (let k = a; k < b; k++) m[k % n] = !val;
        }
    }
    return m;
}

// two-bone IK on the normalized rig: the side's ankle to `target` (the donor's frame), the knee bending in the leg's own
// plane, the foot keeping its world rotation (so the whole foot moves by what the ankle moves) -> the miss (m)
function legIK(THREE, vrm, side, target) {
    const H = vrm.humanoid;
    const up = H.getNormalizedBoneNode(`${side}UpperLeg`), lo = H.getNormalizedBoneNode(`${side}LowerLeg`), ft = H.getNormalizedBoneNode(`${side}Foot`);
    if (!up || !lo || !ft) return 0.0;
    const V = () => new THREE.Vector3(), Q = () => new THREE.Quaternion();
    const hip = up.getWorldPosition(V()), knee = lo.getWorldPosition(V()), ank = ft.getWorldPosition(V());
    const qFoot = ft.getWorldQuaternion(Q());
    const a = knee.distanceTo(hip), b = ank.distanceTo(knee);
    const c = Math.min(Math.max(target.distanceTo(hip), Math.abs(a - b) + 1e-5), a + b - 1e-5);
    const ang = (x) => Math.acos(Math.min(1, Math.max(-1, x)));
    const now = ang((a * a + b * b - hip.distanceToSquared(ank)) / (2 * a * b));
    const want = ang((a * a + b * b - c * c) / (2 * a * b));
    const axis = V().subVectors(knee, hip).cross(V().subVectors(ank, knee));
    if (axis.lengthSq() < 1e-12) axis.set(1, 0, 0).applyQuaternion(up.getWorldQuaternion(Q()));   // a straight leg: its knee's hinge
    axis.normalize();
    const turn = (node, R) => {                                     // a world rotation on a node, about its own origin
        const pq = node.parent.getWorldQuaternion(Q());
        node.quaternion.copy(pq.invert().multiply(R.multiply(node.getWorldQuaternion(Q()))));
        node.updateMatrixWorld(true);
    };
    turn(lo, Q().setFromAxisAngle(axis, now - want));
    const a2 = ft.getWorldPosition(V()).sub(hip).normalize();
    turn(up, Q().setFromUnitVectors(a2, V().subVectors(target, hip).normalize()));
    ft.quaternion.copy(lo.getWorldQuaternion(Q()).invert().multiply(qFoot));
    ft.updateMatrixWorld(true);
    return ft.getWorldPosition(V()).distanceTo(target);
}

// the foot vertices of each side (their strongest skin weight a Foot or Toes bone): the contact the stride is planted on
function feetOf(vrm, D) {
    const out = { left: [], right: [] };
    for (const L of D.layers) {
        if (!L.skinned) continue;
        const bones = L.mesh.skeleton.bones;
        const side = new Map();
        for (const s of ['left', 'right']) for (const b of ['Foot', 'Toes']) { const n = vrm.humanoid.getRawBoneNode(`${s}${b}`); if (n) side.set(n, s); }
        for (let i = 0; i < L.n; i++) {
            let best = 0, bw = -1;
            for (let k = 0; k < 4; k++) { const w = L.sw.getComponent(i, k); if (w > bw) { bw = w; best = L.si.getComponent(i, k); } }
            const s = side.get(bones[best]);
            if (s) out[s].push(L.base + i);
        }
    }
    return out;
}

// ONE stride of a locomotion clip on this VRM, its feet planted, baked -> a flipbook (kind 'cycle'). fps: the film's;
// bpm: the march's tempo, a stride being two beats (null: the clip's own length a stride); posesPerFrame: poses a film
// frame (2 or 3 keep the swing smooth at any tempo); props, curl, face, perPose: as the donor's (above); warmup: laps
// played before the bake (the spring bones settle); clearance: the swinging sole's least height mid-swing (m)
export async function strideCycle(THREE, vrm, clip, { fps = 24, bpm = null, posesPerFrame = 2, props = [], curl = null, face = null, perPose = null,
    prePose = null, name = null, warmup = 1, clearance = CLEARANCE, log = console.log } = {}) {
    const t0 = performance.now();
    const ppf = Math.max(1, Math.trunc(posesPerFrame));
    const sfAsked = bpm ? 120.0 * fps / bpm : clip.duration * fps;
    const N = Math.max(8, Math.round(sfAsked * ppf));
    const sf = N / ppf;                                              // the stride's film frames, locked to the poses
    const strideS = sf / fps;
    const dur = clip.duration, dt = strideS / N;
    const D = donorLayers(THREE, vrm);
    const feet = feetOf(vrm, D);
    // the clip in place: its hips' own travel along the walk (if it has any) is taken out; the root's travel is the bake's
    vrm.humanoid.resetNormalizedPose();
    const hips = vrm.humanoid.getNormalizedBoneNode('hips'), hz = hips.position.z;
    const ankleOf = (s) => vrm.humanoid.getNormalizedBoneNode(`${s}Foot`).getWorldPosition(new THREE.Vector3());
    const plant = { left: null, right: null };                       // the pose being made: each ankle's move (null: the clip's)
    let ikMiss = 0.0;
    const post = () => {
        hips.position.z = hz;
        hips.updateMatrixWorld(true);
        for (const s of SIDES) if (plant[s]) ikMiss = Math.max(ikMiss, legIK(THREE, vrm, s, ankleOf(s).add(plant[s])));
    };
    const pose = driver(THREE, vrm, clip, { curl, face, perPose, prePose, post });
    const I = new THREE.Matrix4();
    const P = new Float32Array(D.verts * 4), Nn = new Float32Array(D.verts * 4);
    // 1. THE TREADMILL: one loop of the clip at R samples a pose (after warmup laps: the spring bones settle), each side's
    //    ankle and its sole's points (x across, y up, z along the walk)
    const R = 4, M = R * N, dtc = dur / M, wrap = (j) => ((j % M) + M) % M;
    const rr = (r) => Math.max(1, Math.round(r * M / dur / 120.0));  // the Blender edition's smoothing radii (at 120 samples a second)
    for (let w = 0; w < warmup; w++) for (let j = 0; j < M; j++) pose(dur * j / M, strideS / M);
    const an = { left: [], right: [] }, sole = { left: [], right: [] }, low = { left: [], right: [] };
    for (let j = 0; j < M; j++) {
        pose(dur * j / M, strideS / M);
        skinPose(THREE, D, I, P, Nn);
        for (const s of SIDES) {
            an[s].push(ankleOf(s));
            const pts = new Float64Array(feet[s].length * 3);
            let lo = Infinity;
            feet[s].forEach((i, q) => { pts[q * 3] = P[i * 4]; pts[q * 3 + 1] = P[i * 4 + 1]; pts[q * 3 + 2] = P[i * 4 + 2]; lo = Math.min(lo, P[i * 4 + 1]); });
            sole[s].push(pts);
            low[s].push(lo);
        }
    }
    // the treadmill's speed is the stance ankle's: it moves back steadily through the flat stance (the middle half of the
    // samples going back faster than 0.3 m/s); a sole's lowest point jumps heel / toe and rises and falls through a stance
    const back = {}, vs = [];
    for (const s of SIDES) {
        back[s] = an[s].map((_, j) => -(an[s][wrap(j + 1)].z - an[s][wrap(j - 1)].z) / (2 * dtc));
        vs.push(...back[s].filter((x) => x > 0.3));
    }
    vs.sort((x, y) => x - y);
    const q4 = vs.length >> 2;
    const v = vs.length ? median(vs.slice(q4, Math.max(q4 + 1, (3 * vs.length) >> 2))) : 0.0;
    if (!(v > 0)) throw new Error(`[crowd] strideCycle: '${clip.name}' does not step: no foot goes back under the body`);
    // THE STANCE: the flat core (the ankle at the treadmill's speed), grown while some low point of the sole (within 1 cm
    // of its lowest) moves with the treadmill: the heel's and the ball's rockers. The contact's own velocity: its lowest
    // points', weighted e^(-height above the lowest / LOCK_BAND)
    const stance = {}, vc = {}, floors = [];
    for (const s of SIDES) {
        const S_ = sole[s], np = S_[0].length / 3;
        const core = cleanMask(back[s].map((b) => Math.abs(b - v) < 0.3 * v), Math.max(2, Math.round(0.06 / dtc)));
        // (the clip's floor: where the stance sole comes lowest, mid-stance)
        const lows = low[s].filter((_, j) => core[j]).sort((x, y) => x - y);
        floors.push(lows.length ? lows[Math.floor(0.1 * (lows.length - 1))] : Math.min(...low[s]));
        const match = [], vel = [];
        for (let j = 0; j < M; j++) {
            const a = S_[wrap(j - 1)], b = S_[wrap(j + 1)], p = S_[j], lo = low[s][j];
            let hit = false, wx = 0, wz = 0, ws = 0;
            for (let q = 0; q < np; q++) {
                const rel = p[q * 3 + 1] - lo;
                const vx = (b[q * 3] - a[q * 3]) / (2 * dtc), vz = (b[q * 3 + 2] - a[q * 3 + 2]) / (2 * dtc);
                if (rel <= 0.01 && Math.hypot(vx, -vz - v) / v < TREAD_TOL) hit = true;
                const w = Math.exp(-rel / LOCK_BAND);
                wx += w * vx; wz += w * vz; ws += w;
            }
            match.push(hit);
            vel.push([wx / ws, wz / ws]);
        }
        let st = core.slice();
        for (let it = 0; it < M; it++) {
            const grow = st.map((x, j) => !x && match[j] && (st[wrap(j - 1)] || st[wrap(j + 1)]));
            if (!grow.some(Boolean)) break;
            st = st.map((x, j) => x || grow[j]);
        }
        stance[s] = st;
        vc[s] = vel;
    }
    // THE SUPPORT: the root follows the stance feet's contact (shared by their load through the double support): its
    // travel along the walk, its sway across it (its mean taken out), its height; lightly smoothed. S, the stride: the
    // support's travel over one loop
    const load = {};
    for (const s of SIDES) load[s] = hann(stance[s].map(Number), rr(4));
    const vf = new Float64Array(M), vl = new Float64Array(M), zs = new Float64Array(M);
    for (let j = 0; j < M; j++) {
        const den = load.left[j] + load.right[j] + 1e-9;
        vf[j] = -SIDES.reduce((t, s) => t + load[s][j] * vc[s][j][1], 0) / den;
        vl[j] = -SIDES.reduce((t, s) => t + load[s][j] * vc[s][j][0], 0) / den;
        zs[j] = SIDES.reduce((t, s) => t + load[s][j] * low[s][j], 0) / den;
    }
    const vfs = hann(vf, rr(6)), vls0 = hann(vl, rr(6)), zss = hann(zs, rr(4));
    const vlMean = vls0.reduce((t, x) => t + x, 0) / M;
    const fwd = [0.0], lat = [0.0];
    for (let j = 0; j < M; j++) { fwd.push(fwd[j] + vfs[j] * dtc); lat.push(lat[j] + (vls0[j] - vlMean) * dtc); }
    const S = fwd[M];
    const strikeOf = (s) => { const st = stance[s]; for (let j = 0; j < M; j++) if (st[j] && !st[wrap(j - 1)]) return j; return 0; };
    const kL = strikeOf('left'), kR = strikeOf('right');
    // 2. THE POSES from the left heel's strike, every R-th sample: the root's shift in the frame that moves S a stride
    //    (travel, sway, height), and each planted foot's ankle moved so its contact holds still on the floor (two-bone IK;
    //    a foot in the air eases back to the clip's path by its next strike)
    const unroll = (arr, j) => (j >= M ? arr[j - M] + arr[M] : arr[j]);
    const shift = [];
    for (let k = 0; k <= N; k++) {
        const j = kL + R * k;
        shift.push([unroll(lat, j) - lat[kL], -zss[wrap(j)], unroll(fwd, j) - fwd[kL] - S * k / N]);
    }
    // the contact's move from sample j0 to j1: of the sole's points low on both (within 2.5 mm of its lowest), the one
    // moving most like them all (the nearest to their median move: the pivot a rolling sole turns about)
    const cm = (s, j0, j1) => {
        const a = sole[s][wrap(j0)], b = sole[s][wrap(j1)], la = low[s][wrap(j0)], lb = low[s][wrap(j1)];
        const pts = [];
        for (let q = 0; q < a.length; q += 3) if (a[q + 1] < la + 0.0025 && b[q + 1] < lb + 0.0025) pts.push([b[q] - a[q], b[q + 2] - a[q + 2]]);
        if (!pts.length) {
            let qm = 0;
            for (let q = 0; q < a.length; q += 3) if (a[q + 1] < a[qm + 1]) qm = q;
            return [b[qm] - a[qm], b[qm + 2] - a[qm + 2]];
        }
        const mx = median(pts.map((p) => p[0])), mz = median(pts.map((p) => p[1]));
        let best = pts[0], bd = Infinity;
        for (const p of pts) { const d = Math.hypot(p[0] - mx, p[1] - mz); if (d < bd) { bd = d; best = p; } }
        return best;
    };
    const floorClip = (floors[0] + floors[1]) / 2;
    const offs = {};
    for (const s of SIDES) {
        // the planted poses: the stance, and on from either end while the sole, the root lowered, is on the floor (a
        // heel coming down, a toe leaving it): a foot that touches is a foot that holds
        let st = [...Array(N).keys()].map((k) => stance[s][wrap(kL + R * k)]);
        const near = [...Array(N).keys()].map((k) => low[s][wrap(kL + R * k)] + shift[k][1] < 0.004);
        for (let it = 0; it < N; it++) {
            const g = st.map((x, k) => !x && near[k] && (st[(k + N - 1) % N] || st[(k + 1) % N]));
            if (!g.some(Boolean)) break;
            st = st.map((x, k) => x || g[k]);
        }
        const o = Array.from({ length: N }, () => [0, 0, 0]);
        const k0 = st.findIndex((x, k) => x && !st[(k + N - 1) % N]);
        if (k0 >= 0) {
            let cur = [0, 0, 0];
            for (let i = 0; i < N; i++) {
                const k = (k0 + i) % N;
                if (!st[k]) continue;
                if (!st[(k + N - 1) % N]) cur = [0, 0, 0];
                o[k] = [cur[0], -(low[s][wrap(kL + R * k)] + shift[k][1]), cur[2]];
                if (st[(k + 1) % N]) {
                    let mx = shift[k + 1][0] - shift[k][0], mz = shift[k + 1][2] - shift[k][2];
                    const m = cm(s, kL + R * k, kL + R * (k + 1));
                    mx += m[0]; mz += m[1];
                    cur = [cur[0] - mx, 0, cur[2] - S / N - mz];     // (the contact still in the world: back S / N a pose in
                }                                                    //  this frame, which the instancer carries S / N a pose)
            }
            // the swings: from the lift's move to the strike's, the foot never lower over the floor than the clip has it
            // over its own (the root, lowered onto the support, would take a swinging foot through the floor), nor
            // than the clearance profile mid-swing (the Blender edition's: the stock walk's toe passes 4 mm over its
            // floor and dips under it on a body with longer feet)
            const swing = [];
            for (let i = 0; i < N; i++) {
                const k = (k0 + i) % N;
                if (st[k] || !st[(k + N - 1) % N]) continue;
                const a = k - 1;
                let b = k;
                while (!st[b % N]) b++;
                const oa = o[(a + N) % N], ob = o[b % N];
                for (let qk = k; qk < b; qk++) {
                    const u = (qk - a) / (b - a), q = qk % N;
                    const w = [0, 1, 2].map((c) => oa[c] + (ob[c] - oa[c]) * u);
                    const lowQ = low[s][wrap(kL + R * q)] + shift[q][1];
                    w[1] = Math.max(w[1], -shift[q][1] - floorClip, clearance * bump(u) - lowQ);
                    swing.push([q, w]);
                }
            }
            for (const [q, w] of swing) o[q] = w;
        }
        offs[s] = o;
    }
    // (a lap first, unkept: a body's own pass may keep state from pose to pose, its joints' rate limits, its springs)
    for (let k = 0; k < N; k++) {
        for (const s of SIDES) { const o = offs[s][k]; plant[s] = new THREE.Vector3(o[0], o[1], o[2]); }
        pose(dur * wrap(kL + R * k) / M, dt);
    }
    const raw = [];
    for (let k = 0; k <= N; k++) {
        for (const s of SIDES) { const o = offs[s][k % N]; plant[s] = new THREE.Vector3(o[0], o[1], o[2]); }
        pose(dur * wrap(kL + R * k) / M, dt);
        const p = new Float32Array(D.verts * 4), n = new Float32Array(D.verts * 4);
        skinPose(THREE, D, I, p, n);
        const [sx, sy, sz] = shift[k];
        for (let i = 0; i < D.verts; i++) { p[i * 4] += sx; p[i * 4 + 1] += sy; p[i * 4 + 2] += sz; }
        const props_ = props.map((q) => { const m = propMatrix(THREE, vrm, q, I); m.elements[12] += sx; m.elements[13] += sy; m.elements[14] += sz; return m; });
        raw.push({ p, n, props: props_ });
    }
    plant.left = plant.right = null;
    const poses = raw.slice(0, N).map((r) => [r.p, r.n]);
    const propMats = props.map((_, j) => raw.slice(0, N).map((r) => r.props[j]));
    // the seam: the pose one stride on, in its own moving frame, against the first
    const pN = raw[N].p, p0 = raw[0].p;
    let seam = 0;
    for (let i = 0; i < D.verts; i++) {
        seam = Math.max(seam, Math.abs(pN[i * 4] - p0[i * 4]), Math.abs(pN[i * 4 + 1] - p0[i * 4 + 1]), Math.abs(pN[i * 4 + 2] - p0[i * 4 + 2]));
    }
    const both = stance.left.filter((x, j) => x && stance.right[j]).length / M;
    const record = { clip: clip.name, bpm_asked: bpm, bpm_used: +(120.0 * fps / sf).toFixed(4), stride_frames: sf, poses_per_frame: ppf, poses: N,
        time_scale: +(dur / strideS).toFixed(5), speed_m_s: +(S / strideS).toFixed(4), clip_stride_m: +S.toFixed(4), treadmill_m_s: +v.toFixed(4),
        left_strike_clip_s: +(kL / M * dur).toFixed(4), right_strike_clip_s: +(kR / M * dur).toFixed(4), double_support: +both.toFixed(4),
        stance: SIDES.map((s) => +(stance[s].filter(Boolean).length / M).toFixed(3)),
        stride_m: +S.toFixed(5), seam_mm: +(seam * 1000).toFixed(3), right_strike_pose: Math.round(((kR - kL + M) % M) / M * N) % N,
        ik_miss_mm: +(ikMiss * 1000).toFixed(3), verts: D.verts };
    const fb = makeFlipbook(THREE, D, poses, props.map((prop, j) => ({ prop, matrices: propMats[j] })), name || `${clip.name}_stride`, 'cycle', record);
    fb.feet = feet;
    record.bake_seconds = +((performance.now() - t0) / 1000).toFixed(1);
    log(`[crowd] stride ${JSON.stringify(record)}`);
    return fb;
}

// ONE loop of a stationary clip (a sway, a dance, an idle) in place, baked -> a flipbook (kind 'cycle', stride 0); bpm:
// the loop timed to last `beats` beats (null: the clip's own length)
export async function loopCycle(THREE, vrm, clip, { fps = 24, bpm = null, beats = 2, posesPerFrame = 1, props = [], curl = null, face = null, perPose = null,
    prePose = null, name = null, log = console.log } = {}) {
    const ppf = Math.max(1, Math.trunc(posesPerFrame));
    const sfAsked = bpm ? 60.0 * beats * fps / bpm : clip.duration * fps;
    const N = Math.max(4, Math.round(sfAsked * ppf));
    const sf = N / ppf;
    const D = donorLayers(THREE, vrm);
    const pose = driver(THREE, vrm, clip, { curl, face, perPose, prePose });
    const I = new THREE.Matrix4(), poses = [], propMats = props.map(() => []);
    for (let k = 0; k < N; k++) pose(clip.duration * k / N, sf / fps / N);
    for (let k = 0; k < N; k++) {
        pose(clip.duration * k / N, sf / fps / N);
        const p = new Float32Array(D.verts * 4), n = new Float32Array(D.verts * 4);
        skinPose(THREE, D, I, p, n);
        poses.push([p, n]);
        props.forEach((q, j) => propMats[j].push(propMatrix(THREE, vrm, q, I)));
    }
    const record = { clip: clip.name, bpm_asked: bpm, beats, stride_frames: sf, poses_per_frame: ppf, poses: N, time_scale: +(clip.duration / (sf / fps)).toFixed(5), stride_m: 0.0 };
    log(`[crowd] loop ${JSON.stringify(record)}`);
    return makeFlipbook(THREE, D, poses, props.map((prop, j) => ({ prop, matrices: propMats[j] })), name || `${clip.name}_loop`, 'cycle', record);
}

// a one-shot clip played once from its start, baked every `every` film frames -> a flipbook (kind 'once'); the pose
// frame is the donor's own
export async function onceFlipbook(THREE, vrm, clip, { fps = 24, every = 2, props = [], curl = null, face = null, perPose = null, prePose = null,
    name = null, log = console.log } = {}) {
    const D = donorLayers(THREE, vrm);
    const pose = driver(THREE, vrm, clip, { curl, face, perPose, prePose });
    const last = 1 + Math.round(clip.duration * fps);
    const frames = [];
    for (let f = 1; f < last; f += Math.max(1, Math.trunc(every))) frames.push(f);
    if (frames[frames.length - 1] !== last) frames.push(last);
    const I = new THREE.Matrix4(), poses = [], propMats = props.map(() => []);
    let prev = 1;
    for (const f of frames) {
        pose(Math.min(clip.duration, (f - 1) / fps), (f - prev) / fps);
        prev = f;
        const p = new Float32Array(D.verts * 4), n = new Float32Array(D.verts * 4);
        skinPose(THREE, D, I, p, n);
        poses.push([p, n]);
        props.forEach((q, j) => propMats[j].push(propMatrix(THREE, vrm, q, I)));
    }
    const record = { clip: clip.name, every: Math.trunc(every), clip_frames: last, poses: frames.length, pose_frames: frames };
    log(`[crowd] once ${JSON.stringify({ ...record, pose_frames: undefined })}`);
    return makeFlipbook(THREE, D, poses, props.map((prop, j) => ({ prop, matrices: propMats[j] })), name || `${clip.name}_once`, 'once', record);
}

// ------------------------------------------------------------------------------------------------------ the clocks
// a cycle flipbook's group: every point plays it from refFrame (a frame its left heel strikes on) and is carried forward
// by its stride. show: [first, last] frame; hold: [from, frames]
export function columnGroup(fb, { refFrame = 1.0, show = null, hold = null, frameOffset = 0.0 } = {}) {
    if (fb.kind !== 'cycle') throw new Error('crowd.columnGroup: a cycle flipbook (strideCycle, loopCycle); onceGroup plays a one-shot');
    return { kind: 'column', fb, refFrame, show: show || [-FAR, FAR], hold: hold || [FAR, 0.0], frameOffset };
}

// a one-shot flipbook's group: every point plays it from its own start
export function onceGroup(fb, { show = null, hold = null, frameOffset = 0.0 } = {}) {
    if (fb.kind !== 'once') throw new Error('crowd.onceGroup: a one-shot flipbook (onceFlipbook); columnGroup plays a cycle');
    return { kind: 'once', fb, show: show || [-FAR, FAR], hold: hold || [FAR, 0.0], frameOffset };
}

// the clocks on the CPU, the shader's arithmetic exactly: the frame a point plays and its pose -> { pose, travel }
export function clockOf(G, pt, frame) {
    const f = frame + G.frameOffset;
    const f1 = Math.min(f, pt.stop ?? FAR);
    const held = Math.max(Math.min(f1 - G.hold[0], G.hold[1]), 0.0);
    const fe = f1 - held;
    const N = G.fb.poses;
    if (G.kind === 'once') return { pose: Math.min(Math.max(Math.floor((fe - (pt.start ?? 0)) / G.fb.every), 0), N - 1), travel: 0.0 };
    const ph = (fe - G.refFrame) / G.fb.strideFrames + (pt.dphase ?? 0);
    const k = Math.floor(N * ph + 0.5);
    return { pose: k - Math.floor(k / N) * N, travel: k * G.fb.stride / N };
}

// ------------------------------------------------------------------------------------------------------ the points
// a column at its phase 0: `files` abreast `interval` m apart, `ranks` one behind another `distance` m apart, the head
// rank's middle at `origin`, marching toward `heading` (degrees about +Y; 0 toward +Z, a VRM's front). jitter: { lateral,
// along (m), phase (strides), seed }, each uniform in +- that
export function formation({ files, ranks, interval = 0.75, distance = 0.95, origin = [0, 0, 0], heading = 0.0, jitter = {} } = {}) {
    const j = { lateral: 0.0, along: 0.0, phase: 0.0, seed: 1, ...jitter };
    const rnd = stream(j.seed);
    const u = () => rnd() * 2.0 - 1.0;
    const yaw = heading * Math.PI / 180;
    const fwd = [Math.sin(yaw), 0.0, Math.cos(yaw)], left = [Math.cos(yaw), 0.0, -Math.sin(yaw)];
    const out = [];
    for (let r = 0; r < ranks; r++) for (let fi = 0; fi < files; fi++) {
        const a = -r * distance + u() * j.along;
        const s = (fi - (files - 1) / 2.0) * interval + u() * j.lateral;
        out.push({ p: [origin[0] + fwd[0] * a + left[0] * s, origin[1], origin[2] + fwd[2] * a + left[2] * s], yaw, dphase: u() * j.phase, rank: r, file: fi });
    }
    return out;
}

// lines of units: a line's units side by side `unitPitch` apart along the bodies' left, the lines one behind another
// `linePitch` apart, every body facing `heading` (degrees; 0 faces +Z). Lines and units count from 1
export function grid({ lines, units, linePitch = 2.4, unitPitch = 1.2, origin = [0, 0, 0], heading = 0.0 } = {}) {
    const yaw = heading * Math.PI / 180;
    const fwd = [Math.sin(yaw), 0.0, Math.cos(yaw)], left = [Math.cos(yaw), 0.0, -Math.sin(yaw)];
    const out = [];
    for (let ln = 0; ln < lines; ln++) for (let u = 0; u < units; u++) {
        const b = -ln * linePitch, s = (u - (units - 1) / 2.0) * unitPitch;
        out.push({ p: [origin[0] + fwd[0] * b + left[0] * s, origin[1], origin[2] + fwd[2] * b + left[2] * s], yaw, line: ln + 1, unit: u + 1 });
    }
    return out;
}

// the canon as numbers: start = first + stepLine x the line's place + stepUnit x the unit's place in its line
export function canonStarts(points, { first, stepLine, stepUnit, order = null } = {}) {
    const lines = [...new Set(points.map((p) => p.line))].sort(order || ((a, b) => a - b));
    const place = new Map(lines.map((ln, i) => [ln, i]));
    const firstUnit = new Map(lines.map((ln) => [ln, Math.min(...points.filter((p) => p.line === ln).map((p) => p.unit))]));
    return points.map((p) => first + stepLine * place.get(p.line) + stepUnit * (p.unit - firstUnit.get(p.line)));
}

// ------------------------------------------------------------------------------------------------------ the crowd
// ONE group of instanced layers, a body a point: every layer of the donor and every held prop drawn once with all the
// points, their poses read from the flipbook by the vertex shader. points: [{ p, yaw, dphase, ... }]; starts / stops:
// a frame a point (stops: null or FAR where a body never stops alone) -> { group, update(frame), poseOf(i, frame),
// points, dispose() }
export function crowd(THREE, name, points, G, { starts = null, stops = null, castShadow = true } = {}) {
    const T = THREE;
    const { Fn, float, int, ivec2, vec3, vec4, uniform, attribute, textureLoad, floor, min, max, clamp, sin, cos, positionLocal, normalLocal, mat4 } = T;
    const fb = G.fb;
    const n = points.length;
    const pts = points.map((p, i) => ({ ...p, start: starts ? starts[i] : (p.start ?? 0.0), stop: stops && stops[i] !== null && stops[i] !== undefined ? stops[i] : FAR }));
    const a0 = new Float32Array(n * 4), a1 = new Float32Array(n * 4);
    pts.forEach((p, i) => { a0.set([p.p[0], p.p[1], p.p[2], p.yaw || 0], i * 4); a1.set([p.dphase || 0, p.start, p.stop, 0], i * 4); });
    const U = { frame: uniform(0.0), offset: uniform(G.frameOffset), ref: uniform(G.refFrame ?? 0), sf: uniform(fb.strideFrames || 1), poses: uniform(fb.poses),
        stride: uniform(fb.stride || 0), holdFrom: uniform(G.hold[0]), holdFrames: uniform(G.hold[1]), every: uniform(fb.every || 1) };
    // the clock, per instance: the pose it shows and how far it has walked
    const clock = Fn(() => {
        const A1 = attribute('crowdB', 'vec4');
        const f = U.frame.add(U.offset);
        const f1 = min(f, A1.z);
        const held = max(min(f1.sub(U.holdFrom), U.holdFrames), 0.0);
        const fe = f1.sub(held);
        if (G.kind === 'once') {
            const i = clamp(floor(fe.sub(A1.y).div(U.every)), 0.0, U.poses.sub(1.0));
            return vec4(i, 0.0, 0.0, 0.0);
        }
        const ph = fe.sub(U.ref).div(U.sf).add(A1.x);
        const k = floor(U.poses.mul(ph).add(0.5));
        const idx = k.sub(floor(k.div(U.poses)).mul(U.poses));
        return vec4(idx, k.mul(U.stride).div(U.poses), 0.0, 0.0);
    });
    // a point's place: its pose turned by its yaw about +Y, carried along its heading, set at its point
    const turned = (v, A0) => {
        const c = cos(A0.w), s = sin(A0.w);
        return vec3(v.x.mul(c).add(v.z.mul(s)), v.y, v.z.mul(c).sub(v.x.mul(s)));
    };
    const along = (A0, travel) => vec3(sin(A0.w).mul(travel), 0.0, cos(A0.w).mul(travel));
    const group = new T.Group();
    group.name = `crowd.${name}`;
    const meshes = [];
    const instance = (geo, mat) => {
        const im = new T.InstancedMesh(geo, mat, n);
        geo.setAttribute('crowdA', new T.InstancedBufferAttribute(a0, 4));
        geo.setAttribute('crowdB', new T.InstancedBufferAttribute(a1, 4));
        im.frustumCulled = false;
        im.castShadow = castShadow; im.receiveShadow = true;
        group.add(im);
        meshes.push(im);
        return im;
    };
    // a material's copy for the crowd (a node material's clone keeps its nodes but not a standard material's own values:
    // colour, maps, roughness, metalness, emission, so they are carried over)
    const KEEP = ['color', 'map', 'emissive', 'emissiveMap', 'emissiveIntensity', 'roughness', 'roughnessMap', 'metalness', 'metalnessMap',
        'normalMap', 'normalScale', 'aoMap', 'aoMapIntensity', 'alphaMap', 'envMap', 'envMapIntensity', 'clearcoat', 'clearcoatRoughness',
        'transmission', 'ior', 'thickness', 'sheen', 'sheenColor', 'specularIntensity', 'specularColor', 'opacity', 'transparent', 'alphaTest',
        'side', 'vertexColors', 'flatShading', 'depthWrite', 'toneMapped'];
    const copyOf = (src) => {
        const m = src.clone();
        const standard = src.isMeshStandardNodeMaterial || src.isMeshPhysicalNodeMaterial || src.isMeshBasicNodeMaterial
            || src.isMeshLambertNodeMaterial || src.isMeshPhongNodeMaterial;
        if (!standard) return m;                                     // (MToon and the like copy themselves whole)
        for (const k of KEEP) {
            if (!(k in src) || src[k] === undefined) continue;
            const v = src[k];
            if (v && v.isColor) m[k] = v.clone();
            else if (v && v.isVector2) m[k] = v.clone();
            else m[k] = v;
        }
        return m;
    };
    // the donor's layers: their vertices from the flipbook
    const fromVat = (src) => {
        const m = copyOf(src);
        m.positionNode = Fn(() => {
            const A0 = attribute('crowdA', 'vec4');
            const ck = clock();
            const vid = attribute('crowdVid', 'float');
            const row = ck.x.mul(fb.rows).add(floor(vid.div(ROW)));
            const col = vid.sub(floor(vid.div(ROW)).mul(ROW));
            const at = ivec2(int(col), int(row));
            const p = textureLoad(fb.posTex, at).xyz;
            const nn = textureLoad(fb.nrmTex, at).xyz;
            normalLocal.assign(turned(nn, A0));
            return turned(p, A0).add(along(A0, ck.y)).add(A0.xyz);
        })();
        return m;
    };
    const matCache = new Map();
    for (const L of fb.layers) {
        const mats = (Array.isArray(L.material) ? L.material : [L.material]).map((m) => {
            if (!matCache.has(m)) matCache.set(m, fromVat(m));
            return matCache.get(m);
        });
        instance(L.geometry.clone(), Array.isArray(L.material) ? mats : mats[0]);
    }
    // the props: each pose's matrix from the flipbook, then the point's place
    for (const pr of fb.props) {
        pr.source.updateMatrixWorld(true);
        const rootInv = pr.source.matrixWorld.clone().invert();
        pr.source.traverse((o) => {
            if (!o.isMesh) return;
            const geo = o.geometry.clone().applyMatrix4(rootInv.clone().multiply(o.matrixWorld));
            const wrap = (src) => {
                const m = src.isNodeMaterial ? copyOf(src) : (() => { const x = new T.MeshStandardNodeMaterial(); x.copy?.(src); return x; })();
                m.positionNode = Fn(() => {
                    const A0 = attribute('crowdA', 'vec4');
                    const ck = clock();
                    const r = int(ck.x);
                    const M = mat4(textureLoad(pr.tex, ivec2(int(0), r)), textureLoad(pr.tex, ivec2(int(1), r)), textureLoad(pr.tex, ivec2(int(2), r)), textureLoad(pr.tex, ivec2(int(3), r)));
                    const p = M.mul(vec4(positionLocal, 1.0)).xyz;
                    normalLocal.assign(turned(M.mul(vec4(normalLocal, 0.0)).xyz, A0));
                    return turned(p, A0).add(along(A0, ck.y)).add(A0.xyz);
                })();
                return m;
            };
            instance(geo, Array.isArray(o.material) ? o.material.map(wrap) : wrap(o.material));
        });
    }
    const poseOf = (i, frame) => clockOf(G, pts[i], frame);
    return {
        group, points: pts, G, meshes, uniforms: U,
        update(frame) {
            U.frame.value = frame;
            group.visible = frame + G.frameOffset >= G.show[0] && frame + G.frameOffset <= G.show[1];
        },
        poseOf,
        // a body's world matrix of its pose frame on a frame (the group's own transform not included)
        frameOf(i, frame) {
            const p = pts[i], c = clockOf(G, p, frame);
            const m = new T.Matrix4().makeRotationY(p.yaw || 0);
            m.setPosition(p.p[0] + Math.sin(p.yaw || 0) * c.travel, p.p[1], p.p[2] + Math.cos(p.yaw || 0) * c.travel);
            return m;
        },
        dispose() { for (const m of meshes) { m.geometry.dispose(); } group.removeFromParent(); },
    };
}

// ------------------------------------------------------------------------------------------------------ the checks
// ONE body's planted feet, frame after frame, as the Blender edition measures them: a foot is down when its lowest
// vertex is within `touch` of the floor; on each side down on two frames running, the vertices within `floor` on both
// are the contact, and the least move among them (a sole rolling about its heel or ball keeps that point still) is the
// slip -> { worstSlideMm, worstSpreadMm, pairs, frames }
export function feetSlide(THREE, C, frames, point = 0, floor = 0.0025, touch = 0.0004) {
    const fb = C.G.fb, P = fb._P, rows = fb.rows;
    let worst = 0.0, spread = 0.0, prev = null, looked = 0;
    for (const f of frames) {
        const { pose } = C.poseOf(point, f);
        const M = C.frameOf(point, f);
        const o = pose * rows * ROW * 4;
        const cur = {}, pos = new Map();
        for (const s of ['left', 'right']) {
            const ids = (fb.feet ? fb.feet[s] : []).filter((i) => P[o + i * 4 + 1] < floor);
            const lo = ids.length ? Math.min(...ids.map((i) => P[o + i * 4 + 1])) : 1;
            cur[s] = new Set(lo < touch ? ids : []);
            for (const i of ids) pos.set(i, new THREE.Vector3(P[o + i * 4], P[o + i * 4 + 1], P[o + i * 4 + 2]).applyMatrix4(M));
        }
        if (prev) {
            for (const s of ['left', 'right']) {
                const both = [...cur[s]].filter((i) => prev.cur[s].has(i));
                if (both.length >= 3) {
                    const d = both.map((i) => Math.hypot(pos.get(i).x - prev.pos.get(i).x, pos.get(i).z - prev.pos.get(i).z));
                    worst = Math.max(worst, Math.min(...d) * 1000);
                    spread = Math.max(spread, Math.max(...d) * 1000);
                    looked++;
                }
            }
        }
        prev = { cur, pos };
    }
    return { worstSlideMm: +worst.toFixed(3), worstSpreadMm: +spread.toFixed(3), pairs: looked, frames: [frames[0], frames[frames.length - 1]] };
}

// the pose every point shows on a frame, by the CPU's clock -> [pose]
export function shownPoses(C, frame) { return C.points.map((_, i) => C.poseOf(i, frame).pose); }
