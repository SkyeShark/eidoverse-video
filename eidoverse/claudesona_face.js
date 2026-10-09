// claudesona_face.js — the claudesona's face as digi modelled it (claude_suit.vrm / claude_suit_wardrobe.vrm): a
// lipsync driver built around how its mouth actually works, and an emotion/gaze track keyed to lyrics or dialogue.
//
//   const { installSuitMouth, makeSuitMouth, makeFaceTrack, mergeMax } = await import(new URL('claudesona_face.js', EIDOVERSE_DIR).href);
//   const face = installSuitMouth(vrm);                    // once, after load and before the first render
//   const mouth = makeSuitMouth({ inputMax: 0.35 });       // 0.35 for lipsync.py timelines, 1 for voicebox visemes
//   // per frame, in renderFrame(t), after any controller update and right before renderAsync:
//   const w = mouth.update(t, visemes[Math.floor(t * visemeFps)]);      // {aa, ih, ou, ee, oh} → face weights
//   face.set(mergeMax(w, emotions.at(t)));
//
// Guide: tools-guides/characters.md ("claude_suit.vrm — mouth + wardrobe recipes").
//
// WHY the mouth has morph targets of its own: the visible cat-smile is PAINTED on the face. The animatable mouth is
// a flat black plate kept 29 mm BEHIND the face dome, and the rig's `show MMD mouth` shapekey is a pure translation
// toward the camera, 28.8 mm per unit. At 1.0 the plate straddles the face (patches poke through), at ~1.1 it is on
// the face, and past that it FLOATS in front of it — 4–10 mm at 1.25, 15–20 mm at 1.6. The offset lies along the view
// axis, so head-on it looks right and every three-quarter shot shows a black slab sliding off the face (measured
// from the VRM's morph data; rendered at 0°/40°/70°). The rig's vowel shapes are authored flat while the face is a
// dome, so no mix of them follows it either. So installSuitMouth leaves every rig mouth shape at 0 and gives the
// plate three targets of its own, each vertex raycast onto the face 1.5 mm proud: `seat` (a sliver under the smile),
// `wide` (sliver → a full open mouth) and `round` (sliver → an "oh"). The driver speaks two channels: MOUTH_OPEN
// (0..1) and MOUTH_ROUND (0..1, the share of oh/ou).
//
// The same holds for the other painted features: the eyes and lines sit 0–6 mm proud of the dome and their
// expression targets (blink, soft eyes, looks, frown) swing parts of them up to ~12 mm off it, and the blush is a
// reveal plate that at full weight stands ~3–6 mm off the cheek. All of it reads fine head-on and hovers in profile.
// installSuitMouth therefore also re-seats them at load: every painted-feature vertex, at rest and at the end of every
// expression target, is moved along the face's depth axis onto the dome (x and y kept, so a front view is unchanged),
// the features `featureStandoff` proud, the blush `blushStandoff` proud (under the lines). The blush is then a switch at
// exactly 1 (a partial weight would sink it into the cheek).
//
// The driver keeps ONE openness signal (fast attack, slow release) and opens and closes with hysteresis, so the
// mouth stays open through a phrase instead of snapping shut on every consonant dip, and it changes vowel only at a
// syllable dip or when the new vowel clearly leads (no mid-vowel pops).

export const MOUTH_OPEN = 'mouthOpen';
export const MOUTH_ROUND = 'mouthRound';
// per vowel: how far the mouth opens at full voice, and how round it is (render-verified mapping, PR #6)
export const SUIT_VISEMES = {
    aa: { open: 1.0, round: 0 },     // big open
    ee: { open: 0.62, round: 0 },    // wide + shallow
    ih: { open: 0.45, round: 0 },    // flat slit
    oh: { open: 0.95, round: 0.8 },  // rounded drop
    ou: { open: 0.62, round: 1 },    // tight pucker
};
const VOWELS = ['aa', 'ih', 'ou', 'ee', 'oh'];
// the rig's own mouth shapes: never driven (they float off the face or ignore its curve)
const RIG_MOUTH = ['show MMD mouth', 'あ', 'い', 'う', 'え', 'お', 'JawOpen', 'A', 'I', 'U', 'E', 'O', 'LipFunnel', 'LipPucker',
    'vis_aa', 'vis_ih', 'vis_ou', 'vis_ee', 'vis_oh'];

// The face dome as a height field in the plate's geometry space: z of the front-most face surface over (x, y).
function faceHeightField(plate, face, res = 384) {
    const THREE = globalThis.THREE;
    const toPlate = plate.matrixWorld.clone().invert().multiply(face.matrixWorld);
    const fp = face.geometry.attributes.position, v = new THREE.Vector3();
    const P = new Float32Array(fp.count * 3);
    let x0 = Infinity, y0 = Infinity, x1 = -Infinity, y1 = -Infinity;
    for (let i = 0; i < fp.count; i++) {
        v.fromBufferAttribute(fp, i).applyMatrix4(toPlate);
        P[i * 3] = v.x; P[i * 3 + 1] = v.y; P[i * 3 + 2] = v.z;
        x0 = Math.min(x0, v.x); x1 = Math.max(x1, v.x); y0 = Math.min(y0, v.y); y1 = Math.max(y1, v.y);
    }
    const H = new Float32Array(res * res).fill(-Infinity);
    const gx = (x) => (x - x0) / (x1 - x0) * (res - 1), gy = (y) => (y - y0) / (y1 - y0) * (res - 1);
    const idx = face.geometry.index ? face.geometry.index.array : null;
    const nTri = (idx ? idx.length : fp.count) / 3;
    for (let t = 0; t < nTri; t++) {
        const a = idx ? idx[t * 3] : t * 3, b = idx ? idx[t * 3 + 1] : t * 3 + 1, c = idx ? idx[t * 3 + 2] : t * 3 + 2;
        const ax = gx(P[a * 3]), ay = gy(P[a * 3 + 1]), bx = gx(P[b * 3]), by = gy(P[b * 3 + 1]), cx = gx(P[c * 3]), cy = gy(P[c * 3 + 1]);
        const den = (by - cy) * (ax - cx) + (cx - bx) * (ay - cy);
        if (Math.abs(den) < 1e-12) continue;
        for (let yy = Math.max(0, Math.floor(Math.min(ay, by, cy))); yy <= Math.min(res - 1, Math.ceil(Math.max(ay, by, cy))); yy++) {
            for (let xx = Math.max(0, Math.floor(Math.min(ax, bx, cx))); xx <= Math.min(res - 1, Math.ceil(Math.max(ax, bx, cx))); xx++) {
                const l1 = ((by - cy) * (xx - cx) + (cx - bx) * (yy - cy)) / den, l2 = ((cy - ay) * (xx - cx) + (ax - cx) * (yy - cy)) / den;
                const l3 = 1 - l1 - l2;
                if (l1 < -1e-4 || l2 < -1e-4 || l3 < -1e-4) continue;
                const z = l1 * P[a * 3 + 2] + l2 * P[b * 3 + 2] + l3 * P[c * 3 + 2];
                if (z > H[yy * res + xx]) H[yy * res + xx] = z;
            }
        }
    }
    // z at (x, y), bilinear; null off the dome
    return (x, y) => {
        const fx = gx(x), fy = gy(y);
        if (fx < 0 || fy < 0 || fx > res - 1 || fy > res - 1) return null;
        const ix = Math.min(res - 2, Math.floor(fx)), iy = Math.min(res - 2, Math.floor(fy)), tx = fx - ix, ty = fy - iy;
        const h00 = H[iy * res + ix], h10 = H[iy * res + ix + 1], h01 = H[(iy + 1) * res + ix], h11 = H[(iy + 1) * res + ix + 1];
        if (!(h00 > -Infinity && h10 > -Infinity && h01 > -Infinity && h11 > -Infinity)) return null;
        return (h00 * (1 - tx) + h10 * tx) * (1 - ty) + (h01 * (1 - tx) + h11 * tx) * ty;
    };
}

// Re-seat a mesh's painted features on the dome (see WHY above). `mesh` shares the plate's space when it is the plate;
// other meshes (the blush) are carried into it and back. Rest vertices are moved only when `rest` is set and they sit
// within `band` m of the surface (so hidden parts — the mouth cavity, the resting blush — stay where they are);
// target endpoints are moved for every vertex the target moves that started on or near the face (or all, `allTargets`).
function conformToFace(mesh, plate, faceZ, standoff, { rest = true, band = 0.012, allTargets = false, skip = () => false } = {}) {
    const THREE = globalThis.THREE;
    const toPlate = plate.matrixWorld.clone().invert().multiply(mesh.matrixWorld), back = toPlate.clone().invert();
    const geo = mesh.geometry, pos = geo.attributes.position, n = pos.count;
    const v = new THREE.Vector3(), e = new THREE.Vector3();
    const restP = new Float32Array(n * 3), onFace = new Uint8Array(n);
    for (let i = 0; i < n; i++) {
        v.fromBufferAttribute(pos, i).applyMatrix4(toPlate);
        const z = faceZ(v.x, v.y);
        if (z !== null && !skip(v) && Math.abs(v.z - z) < band) {
            onFace[i] = 1;
            if (rest) { v.z = z + standoff; }
        }
        restP.set(v.toArray(), i * 3);
    }
    const newRest = new Float32Array(n * 3);
    for (let i = 0; i < n; i++) { v.fromArray(restP, i * 3).applyMatrix4(back); newRest.set(v.toArray(), i * 3); }
    const oldRest = pos.array.slice();
    const names = Object.entries(mesh.morphTargetDictionary || {}), targets = geo.morphAttributes.position || [];
    for (let t = 0; t < targets.length; t++) {
        const D = targets[t];
        const nm = (names.find(([, k]) => k === t) || [''])[0];
        if (RIG_MOUTH.includes(nm)) continue;                            // never driven
        for (let i = 0; i < n; i++) {
            const dx = D.getX(i), dy = D.getY(i), dz = D.getZ(i);
            const moved = dx * dx + dy * dy + dz * dz > 1e-12;
            let ex = oldRest[i * 3] + dx, ey = oldRest[i * 3 + 1] + dy, ez = oldRest[i * 3 + 2] + dz;
            if (moved && (onFace[i] || allTargets)) {
                e.set(ex, ey, ez).applyMatrix4(toPlate);
                const z = faceZ(e.x, e.y);
                if (z !== null) { e.z = z + standoff; e.applyMatrix4(back); ex = e.x; ey = e.y; ez = e.z; }
            }
            if (!moved) continue;                                        // untouched by this target: stays 0
            D.setXYZ(i, ex - newRest[i * 3], ey - newRest[i * 3 + 1], ez - newRest[i * 3 + 2]);
        }
        D.needsUpdate = true;
    }
    pos.array.set(newRest);
    pos.needsUpdate = true;
    geo.computeBoundingSphere();
}

// Build the plate's own targets (see WHY above). Call before the first render — a mesh's target count is fixed once
// its material compiles — and AFTER anything that runs VRMUtils.combineMorphs (EidoverseRobotController.create does,
// unless opts.skipVrmOptimize): combineMorphs rebuilds each mesh's targets from the expression binds and drops these.
const isMouthPlate = (x, y, z) => Math.abs(x) < 0.03 && y > 1.44 && y < 1.48 && z < 0.095;

function buildMouthTargets(vrm, standoff, featureStandoff, blushStandoff) {
    const THREE = globalThis.THREE;
    let plate = null, face = null, blush = null;
    vrm.scene.traverse((o) => {
        if (!o.isMesh) return;
        const mats = (Array.isArray(o.material) ? o.material : [o.material]).map((m) => m?.name);
        if (!plate && o.morphTargetInfluences && mats.includes('Material')) plate = o;   // eyes + smile + mouth plate
        if (!face && mats.includes('face')) face = o;                                   // the face disc
        if (!blush && o.morphTargetInfluences && mats.includes('BLUSH')) blush = o;      // the blush reveal plate
    });
    if (!plate || !face) throw new Error('installSuitMouth: not claude_suit.vrm / claude_suit_wardrobe.vrm');
    vrm.scene.updateMatrixWorld(true);
    // the painted features and their expression targets, and the blush, onto the dome (before the mouth targets,
    // which are built on the dome already)
    const faceZ = faceHeightField(plate, face);
    conformToFace(plate, plate, faceZ, featureStandoff, { skip: (v) => isMouthPlate(v.x, v.y, v.z) });
    if (blush) conformToFace(blush, plate, faceZ, blushStandoff, { rest: false, allTargets: true });
    const inv = plate.matrixWorld.clone().invert(), ray = new THREE.Raycaster();
    const onFace = (x, y) => {        // plate-local (x, y) → the face surface's z in front of it, + standoff
        const o = plate.localToWorld(new THREE.Vector3(x, y, 0.4));
        ray.set(o, plate.localToWorld(new THREE.Vector3(x, y, -0.6)).sub(o).normalize());
        const hit = ray.intersectObject(face, false)[0];
        return (hit ? hit.point.applyMatrix4(inv).z : 0.115) + standoff;
    };
    const TOP = 1.4762;               // the plate's top edge, just under the painted smile
    const at = (x, y, sx, sy) => { const X = x * sx, Y = TOP - (TOP - y) * sy; return [X, Y, onFace(X, Y)]; };
    const geo = plate.geometry, pos = geo.attributes.position, n = pos.count;
    const seat = new Float32Array(n * 3), wide = new Float32Array(n * 3), round = new Float32Array(n * 3);
    for (let i = 0; i < n; i++) {
        const x = pos.getX(i), y = pos.getY(i), z = pos.getZ(i);
        if (!isMouthPlate(x, y, z)) continue;                                           // the hidden mouth plate only
        const S = at(x, y, 0.55, 0.05), W = at(x, y, 1.55, 1.95), O = at(x, y, 0.95, 1.95);
        for (let k = 0; k < 3; k++) {
            seat[i * 3 + k] = S[k] - [x, y, z][k];     // behind the face → a sliver on it
            wide[i * 3 + k] = W[k] - S[k];             // sliver → full open, 57 × 55 mm
            round[i * 3 + k] = O[k] - S[k];            // sliver → an "oh", 35 × 55 mm
        }
    }
    const idx = {};
    for (const [name, arr] of [['seat', seat], ['wide', wide], ['round', round]]) {
        geo.morphAttributes.position.push(new THREE.Float32BufferAttribute(arr, 3));
        if (geo.morphAttributes.normal) geo.morphAttributes.normal.push(new THREE.Float32BufferAttribute(new Float32Array(n * 3), 3));
        idx[name] = plate.morphTargetInfluences.push(0) - 1;
    }
    return { plate, idx };
}

// Own the face plates' morphs. set(weights) zeroes them and writes `weights` straight away — call it last in
// renderFrame, after any controller update (whose vrm.update rewrites expression-bound targets such as blink) and
// right before renderAsync. Values are re-applied in onBeforeRender too, for backends where that hook still lands.
// Zeroing also removes auto-blink: add `Blink` yourself (makeSuitMouth does, between phrases).
// Weights: MOUTH_OPEN / MOUTH_ROUND for the mouth; any other morph on the plates by name (Blink, EyeClosedLeft,
// Smile, MouthSmileLeft, MouthFrown, Blush …; after combineMorphs only expression names remain: blink, happy …).
export function installSuitMouth(vrm, { standoff = 0.0015, featureStandoff = 0.0018, blushStandoff = 0.001 } = {}) {
    const { plate, idx } = buildMouthTargets(vrm, standoff, featureStandoff, blushStandoff);
    const plates = [];
    vrm.scene.traverse((o) => { if (o.isMesh && o.morphTargetInfluences && o.morphTargetDictionary) plates.push(o); });
    let weights = {};
    const write = () => {
        for (const p of plates) {
            const inf = p.morphTargetInfluences, d = p.morphTargetDictionary;
            inf.fill(0);
            for (const [nm, w] of Object.entries(weights)) if (nm in d && !RIG_MOUTH.includes(nm)) inf[d[nm]] = w;
        }
        const o = Math.min(1, Math.max(0, weights[MOUTH_OPEN] || 0)), r = Math.min(1, Math.max(0, weights[MOUTH_ROUND] || 0));
        if (o > 0.04) {
            const inf = plate.morphTargetInfluences;
            inf[idx.seat] = 1; inf[idx.wide] = o * (1 - r); inf[idx.round] = o * r;
        }
    };
    for (const p of plates) p.onBeforeRender = write;
    return { plate, plates, set(w) { weights = w || {}; write(); }, get weights() { return weights; } };
}

// The lipsync driver. `update(t, frame)` takes the current viseme frame ({aa, ih, ou, ee, oh}, any may be missing)
// and returns face weights ({ mouthOpen, mouthRound, Blink }). Time-based smoothing: independent of the render fps.
// While open the mouth never drops below `floor` of its vowel's size, so it stays visible through a phrase.
export function makeSuitMouth({ inputMax = 1, floor = 0.3, attack = 0.03, release = 0.11, openAt = 0.18,
    closeAt = 0.08, switchDip = 0.3, switchLead = 0.25, blinkEvery = 4.3 } = {}) {
    const M = { open: 0, isOpen: false, pose: null, t: null };
    return {
        state: M,
        update(t, frame = {}) {
            let best = null, bv = 0;
            const val = (k) => Math.min(1, (frame[k] || 0) / inputMax);
            for (const k of VOWELS) if (val(k) > bv) { bv = val(k); best = k; }
            const dt = M.t === null ? 1 / 60 : Math.min(0.1, Math.max(1 / 240, t - M.t));
            M.t = t;
            M.open += (bv - M.open) * (1 - Math.exp(-dt / (bv > M.open ? attack : release)));
            if (!M.isOpen && M.open > openAt) M.isOpen = true;
            else if (M.isOpen && M.open < closeAt) M.isOpen = false;
            const cur = M.pose ? val(M.pose) : 0;
            if (best && (!M.pose || (best !== M.pose && (cur < switchDip || bv > cur + switchLead)))) M.pose = best;
            const out = {};
            if (M.isOpen && M.pose) {
                const v = SUIT_VISEMES[M.pose];
                out[MOUTH_OPEN] = v.open * (floor + (1 - floor) * Math.min(1, M.open));
                out[MOUTH_ROUND] = v.round;
            }
            if (blinkEvery > 0) {                             // a blink every few seconds, never mid-word
                const ph = (t % blinkEvery) / 0.18;
                if (ph < 1 && !M.isOpen) out.Blink = Math.sin(ph * Math.PI);
            }
            return out;
        },
    };
}

// ── Visemes: a full mouth-shape set on the plate (installVisemeMouth + makeVisemeTrack) ─────────────────────────────
// The two-channel mouth above (open, round) can only scale between two shapes. installVisemeMouth gives the same plate
// one target per mouth shape instead: each is an OUTLINE (a superellipse: half-width a, height above/below its centre
// bt/bb, exponent n — 2 an ellipse, 3+ boxier — and `lift`, the corners raised in mm), hung from just under the
// painted smile and raycast onto the face dome `standoff` proud like the seat. Every plate vertex keeps its place
// inside the disc (its angle and its share of the radius), so any two shapes blend into a sensible third: crossfades
// between visemes are smooth. `seat` puts the plate on the face as a sliver; a shape's target is its outline minus
// the seat. Closed (M, B, P, silence) = no shape: the sliver, then the plate goes back behind the face.
// Sizes in mm on the face (the dome is ~150 mm across; the smile ~80 mm wide).
export const VISEME_SHAPES = {
    seat: { a: 10, bt: 0.7, bb: 0.7, n: 2, lift: 0 },
    AA: { a: 25, bt: 4, bb: 22, n: 2.4, lift: 0 },      // "ah": big open drop
    E: { a: 27, bt: 3, bb: 8, n: 3.0, lift: 5 },     // "eh/ay": wide, shallow, corners up
    I: { a: 23, bt: 2, bb: 4, n: 3.2, lift: 3 },      // "ee/ih": a wide slit
    O: { a: 16, bt: 6, bb: 18, n: 2.0, lift: 0 },      // "oh/aw": a tall round
    U: { a: 10, bt: 3, bb: 7, n: 2.0, lift: 0 },      // "oo/w": a small pucker
    FV: { a: 19, bt: 1.2, bb: 3.5, n: 4.0, lift: -1 },  // lip over teeth: a flat sliver, corners down
    L: { a: 18, bt: 3, bb: 11, n: 2.4, lift: 1 },       // "l / th": medium open
    C: { a: 21, bt: 2.5, bb: 9, n: 2.8, lift: 1 },      // most consonants (s t d n k g y h): teeth near together
    CH: { a: 14, bt: 3, bb: 9, n: 2.2, lift: 0 },    // "ch sh j r er": pushed forward, rounded
    MBP: { a: 10, bt: 0, bb: 0, n: 2, lift: 0 },        // lips pressed: no opening, the line alone (LINE_WARP)
};
// The painted smile line is the lips, so every viseme reshapes it too: one warp field per viseme, applied to the
// line AND to the opening (which therefore stays tucked under the line). Over the mouth (|x| < 22 mm, fading to none
// at the line's ends, 58 mm) x scales by `sx` (narrower for O/U/CH, wider for E/I), the centre peak moves `peak` mm
// (+ up) and the line either side of it `corner` mm. The x warp is centred, so the line stays symmetric.
export const LINE_WARP = {        // the painted "3" is the character: it keeps its shape. Visemes are driven by the black
                                   // opening (VISEME_SHAPES) and by SQUEEZING the 3 in from the sides (sx < 1) for the
                                   // rounded sounds; peak/corner/k stay available for other faces but are left neutral here
    O: { sx: 0.7, peak: 0, corner: 0, k: 1 },              // rounded: squeezed in
    U: { sx: 0.56, peak: 0, corner: 0, k: 1 },             // pursed: squeezed hard
    CH: { sx: 0.76, peak: 0, corner: 0, k: 1 },            // pushed forward
    L: { sx: 0.92, peak: 0, corner: 0, k: 1 },
    MBP: { sx: 0.9, peak: 0, corner: 0, k: 1 },            // lips pressed together: a little squeeze
};
export const VISEMES = Object.keys(VISEME_SHAPES).filter((k) => k !== 'seat');

function buildVisemeTargets(vrm, shapes, standoff, featureStandoff, blushStandoff, warps = LINE_WARP) {
    const THREE = globalThis.THREE;
    let plate = null, face = null, blush = null;
    vrm.scene.traverse((o) => {
        if (!o.isMesh) return;
        const mats = (Array.isArray(o.material) ? o.material : [o.material]).map((m) => m?.name);
        if (!plate && o.morphTargetInfluences && mats.includes('Material')) plate = o;
        if (!face && mats.includes('face')) face = o;
        if (!blush && o.morphTargetInfluences && mats.includes('BLUSH')) blush = o;
    });
    if (!plate || !face) throw new Error('installVisemeMouth: not claude_suit.vrm / claude_suit_wardrobe.vrm');
    vrm.scene.updateMatrixWorld(true);
    const faceZ = faceHeightField(plate, face);
    conformToFace(plate, plate, faceZ, featureStandoff, { skip: (v) => isMouthPlate(v.x, v.y, v.z) });
    if (blush) conformToFace(blush, plate, faceZ, blushStandoff, { rest: false, allTargets: true });
    const inv = plate.matrixWorld.clone().invert(), ray = new THREE.Raycaster();
    const onFace = (x, y) => {
        const o = plate.localToWorld(new THREE.Vector3(x, y, 0.4));
        ray.set(o, plate.localToWorld(new THREE.Vector3(x, y, -0.6)).sub(o).normalize());
        const hit = ray.intersectObject(face, false)[0];
        return (hit ? hit.point.applyMatrix4(inv).z : 0.115) + standoff;
    };
    const geo = plate.geometry, pos = geo.attributes.position, n = pos.count;
    // the plate's disc in its own polar terms: centre, and its outline radius per angle (so each vertex is a share of it)
    const ids = [];
    let x0 = Infinity, x1 = -Infinity, y0 = Infinity, y1 = -Infinity;
    for (let i = 0; i < n; i++) {
        const x = pos.getX(i), y = pos.getY(i), z = pos.getZ(i);
        if (!isMouthPlate(x, y, z)) continue;
        ids.push(i);
        x0 = Math.min(x0, x); x1 = Math.max(x1, x); y0 = Math.min(y0, y); y1 = Math.max(y1, y);
    }
    const cx = (x0 + x1) / 2, cy = (y0 + y1) / 2, hx = (x1 - x0) / 2, hy = (y1 - y0) / 2;
    const BINS = 72, rmax = new Float32Array(BINS);
    const polar = new Map();
    for (const i of ids) {
        const u = (pos.getX(i) - cx) / hx, v = (pos.getY(i) - cy) / hy;
        const r = Math.hypot(u, v), th = Math.atan2(v, u);
        const b = Math.floor(((th + Math.PI) / (2 * Math.PI)) * BINS) % BINS;
        rmax[b] = Math.max(rmax[b], r);
        polar.set(i, [r, th, b]);
    }
    // the painted smile's centre-line over the mouth, from its own vertices (binned by |x|): every opening hangs from
    // it, so its top edge tucks under the line however wide it is (a flat top pokes out where the "w" dips)
    const BIN = 0.0025, NB = 20, lo = new Float32Array(NB).fill(Infinity), hi = new Float32Array(NB).fill(-Infinity);
    for (let i = 0; i < n; i++) {
        const x = pos.getX(i), y = pos.getY(i), z = pos.getZ(i);
        if (isMouthPlate(x, y, z) || Math.abs(x) > BIN * NB || y < 1.466 || y > 1.49) continue;
        const b = Math.min(NB - 1, Math.floor(Math.abs(x) / BIN));
        lo[b] = Math.min(lo[b], y); hi[b] = Math.max(hi[b], y);
    }
    const mid = [];
    for (let b = 0; b < NB; b++) if (lo[b] < Infinity) mid.push([(b + 0.5) * BIN, (lo[b] + hi[b]) / 2]);
    const TOP = y1 - 0.0005;
    const smileY = (x) => {                       // the line's centre at |x| (linear between bins; TOP if unknown)
        x = Math.abs(x);
        if (!mid.length) return TOP;
        if (x <= mid[0][0]) return mid[0][1];
        for (let k = 1; k < mid.length; k++) if (x <= mid[k][0]) {
            const f = (x - mid[k - 1][0]) / (mid[k][0] - mid[k - 1][0]);
            return mid[k - 1][1] + (mid[k][1] - mid[k - 1][1]) * f;
        }
        return mid[mid.length - 1][1];
    };
    // a vertex at share r of angle th in the disc: across, u (the shape's width a); down, from the smile line by its
    // share of the shape's height at that u (bt + bb, narrowing to the corners as a superellipse of exponent n);
    // `lift` raises the bottom toward the corners (a smile's upturn)
    // the plate is a thin closed lens (front and back surfaces stacked ~7 mm deep): keep each vertex's depth order,
    // scaled to a fifth, or both surfaces land on the same height and the back one fights through the front
    let zmax = -Infinity;
    for (const i of ids) zmax = Math.max(zmax, pos.getZ(i));
    const baseY = mid.length ? Math.min(...mid.map((m) => m[1])) : TOP;   // the smile's lowest centre-line
    let halfT = 0.0015;                                                  // the stroke's half thickness (thinnest bin)
    for (let b = 0; b < NB; b++) if (lo[b] < Infinity) halfT = Math.min(halfT, (hi[b] - lo[b]) / 2);
    const sstep = (a, b, x) => { const q = Math.max(0, Math.min(1, (x - a) / (b - a))); return q * q * (3 - 2 * q); };
    const warpXY = (wp, x, y) => {
        const ax = Math.abs(x) * 1000, f = 1 - sstep(26, 60, ax);            // 1 over the mouth, 0 at the line's ends
        const c = Math.exp(-((ax / 13) ** 2)), side = sstep(8, 28, ax);
        const k = wp.k ?? 1;                                                  // the w's depth about the line's low level
        const yc = smileY(x);                                                // flatten the CENTRE-LINE, keep the stroke
        const yk = baseY + (yc - baseY) * (1 + (k - 1) * f) + (y - yc);
        // the squeeze scales the WHOLE line about its centre (a uniform copy: no falloff, so no new kinks in the 3)
        return [x * wp.sx, yk + 0.001 * f * (wp.peak * c + wp.corner * side)];
    };
    const point = (s, r, th, z, w = null) => {
        const u = r * Math.cos(th), v = r * Math.sin(th);
        const span = Math.sqrt(Math.max(1e-6, 1 - u * u));
        const t = Math.min(1, Math.max(0, (v / span + 1) / 2));          // 1 at the top edge, 0 at the bottom
        const X = s.a * u * 0.001;
        const H = (s.bt + s.bb) * 0.001 * Math.max(0, 1 - Math.abs(u) ** s.n) ** (1 / s.n);
        const top = smileY(X) - 0.0002;                                  // follows the line (tucked under it)
        // the closed sliver stays INSIDE the line's stroke (invisible); an opening hangs from the line's lowest level
        const bot = s === shapes.seat ? top - Math.min(0.0008, halfT)
            : Math.min(top - Math.min(0.0008, halfT), baseY - Math.max(0, H - s.lift * 0.001 * u * u));
        let Y = bot + t * (top - bot), XX = X;
        if (w) [XX, Y] = warpXY(w, X, Y);
        return [XX, Y, onFace(XX, Y) - (zmax - z) * 0.2];
    };
    const tgt = {};
    for (const name of Object.keys(shapes)) tgt[name] = new Float32Array(n * 3);
    // the outline radius per angle, smoothed round the circle and read between bins (a raw per-bin max scales
    // neighbouring vertices unevenly: a ragged edge)
    for (let pass = 0; pass < 3; pass++) {
        const c = rmax.slice();
        for (let b = 0; b < BINS; b++) {
            const a0 = c[(b + BINS - 1) % BINS] || c[b], a2 = c[(b + 1) % BINS] || c[b];
            rmax[b] = Math.max(c[b], (a0 + 2 * c[b] + a2) / 4);
        }
    }
    const rAt = (th) => {
        const fb = ((th + Math.PI) / (2 * Math.PI)) * BINS - 0.5;
        const b0 = ((Math.floor(fb) % BINS) + BINS) % BINS, b1 = (b0 + 1) % BINS, f = fb - Math.floor(fb);
        return rmax[b0] * (1 - f) + rmax[b1] * f;
    };
    for (const i of ids) {
        const [r, th] = polar.get(i);
        const rr = Math.min(1, r / Math.max(1e-6, rAt(th)));
        const rest = [pos.getX(i), pos.getY(i), pos.getZ(i)];
        const S = point(shapes.seat, rr, th, rest[2]);
        for (const [name, s] of Object.entries(shapes)) {
            const P = name === 'seat' ? S : point(s, rr, th, rest[2], warps[name]);
            const base = name === 'seat' ? rest : S;
            for (let k = 0; k < 3; k++) tgt[name][i * 3 + k] = P[k] - base[k];
        }
    }
    // the line's own vertices move with each viseme's warp, re-seated on the dome at their new place
    for (let i = 0; i < n; i++) {
        const x = pos.getX(i), y = pos.getY(i), z = pos.getZ(i);
        if (isMouthPlate(x, y, z) || Math.abs(x) > 0.11 || y < 1.455 || y > 1.507) continue;   // the WHOLE 3 (tails included), below the eyes
        const z0 = onFace(x, y);
        for (const name of Object.keys(shapes)) {
            const wp = warps[name];
            if (!wp) continue;
            const [X, Y] = warpXY(wp, x, y);
            tgt[name][i * 3] = X - x; tgt[name][i * 3 + 1] = Y - y; tgt[name][i * 3 + 2] = onFace(X, Y) - z0;
        }
    }
    const idx = {};
    for (const [name, arr] of Object.entries(tgt)) {
        geo.morphAttributes.position.push(new THREE.Float32BufferAttribute(arr, 3));
        if (geo.morphAttributes.normal) geo.morphAttributes.normal.push(new THREE.Float32BufferAttribute(new Float32Array(n * 3), 3));
        idx[name] = plate.morphTargetInfluences.push(0) - 1;
    }
    return { plate, idx };
}

// Install the viseme mouth (instead of installSuitMouth — one or the other per VRM). set(weights): the face plates'
// morphs by name as before, plus `viseme: {AA: 0.7, O: 0.3, ...}` (shares, summing to ≤ 1; the rest is the closed
// sliver) and `mouth` (0..1, how far the mouth is open at all: 0 = behind the face). Call last in renderFrame.
export function installVisemeMouth(vrm, { shapes = VISEME_SHAPES, standoff = 0.0015, featureStandoff = 0.0018,
    blushStandoff = 0.001 } = {}) {
    const { plate, idx } = buildVisemeTargets(vrm, shapes, standoff, featureStandoff, blushStandoff);
    const plates = [];
    vrm.scene.traverse((o) => { if (o.isMesh && o.morphTargetInfluences && o.morphTargetDictionary) plates.push(o); });
    let weights = {};
    const write = () => {
        for (const p of plates) {
            const inf = p.morphTargetInfluences, d = p.morphTargetDictionary;
            inf.fill(0);
            for (const [nm, w] of Object.entries(weights)) if (typeof w === 'number' && nm in d && !RIG_MOUTH.includes(nm)) inf[d[nm]] = w;
        }
        const vis = weights.viseme || {}, m = Math.min(1, Math.max(0, weights.mouth ?? 0));
        // the plate comes onto the face only for an opening; pressed lips (MBP) move the line alone
        let open = 0;
        for (const [k, w] of Object.entries(vis)) if (k !== 'MBP') open += Math.max(0, w);
        if (m > 0.02) {
            const inf = plate.morphTargetInfluences;
            if (open > 0.02) inf[idx.seat] = 1;
            for (const [k, w] of Object.entries(vis)) if (k in idx && k !== 'seat') inf[idx[k]] = Math.max(0, w) * m;
        }
    };
    for (const p of plates) p.onBeforeRender = write;
    return { plate, plates, idx, set(w) { weights = w || {}; write(); }, get weights() { return weights; } };
}

// Phones → visemes (ARPAbet, stress digits dropped). M/B/P press the lips (MBP: the line only, no opening).
export const PHONE_VISEME = {
    AA: 'AA', AH: 'L', AE: 'AA', AY: 'AA', AW: 'AA', EH: 'E', EY: 'E', IY: 'I', IH: 'I', Y: 'I', AO: 'O', OW: 'O',
    OY: 'O', UW: 'U', UH: 'U', W: 'U', ER: 'CH', R: 'CH', CH: 'CH', JH: 'CH', SH: 'CH', ZH: 'CH', F: 'FV', V: 'FV',
    TH: 'L', DH: 'L', L: 'L', S: 'C', Z: 'C', T: 'C', D: 'C', N: 'C', K: 'C', G: 'C', NG: 'C', HH: 'C',
    M: 'MBP', B: 'MBP', P: 'MBP',
};

// A viseme track from timed phones: events [{t0, t1, v}] (v a viseme name, or null = closed), as visemes_from_words
// writes them. at(t) → {viseme: {...shares}, mouth}. Each event fades in over `lead` before its start (the mouth
// shapes ahead of the sound) and the next one crosses over it; gaps longer than `closeGap` close the mouth.
// `breath` adds a slow swell on long held vowels (sung notes), `scale` sizes the shapes (0.8 = a smaller mouth).
export function makeVisemeTrack(events, { lead = 0.05, fade = 0.07, closeGap = 0.16, breath = 0.06, scale = 1 } = {}) {
    const E = [...events].sort((a, b) => a.t0 - b.t0);
    let i0 = 0;
    const smooth = (a, b, x) => { const t = Math.max(0, Math.min(1, (x - a) / (b - a))); return t * t * (3 - 2 * t); };
    return {
        at(t) {
            while (i0 > 0 && E[i0].t0 > t) i0--;
            while (i0 < E.length - 1 && E[i0 + 1].t0 - lead <= t) i0++;
            const vis = {};
            let mouth = 0;
            for (let k = Math.max(0, i0 - 1); k <= Math.min(E.length - 1, i0 + 1); k++) {
                const e = E[k];
                const win = smooth(e.t0 - lead - fade, e.t0 - lead + fade * 0.4, t) * (1 - smooth(e.t1 - fade * 0.3, e.t1 + fade, t));
                if (win <= 0) continue;
                if (e.v) {
                    const held = e.t1 - e.t0 > 0.35 ? 1 + breath * Math.sin((t - e.t0) * 2 * Math.PI * 1.3) : 1;
                    vis[e.v] = Math.max(vis[e.v] || 0, win * held * scale);
                    mouth = Math.max(mouth, win);
                }
            }
            const tot = Object.values(vis).reduce((a, b) => a + b, 0);
            if (tot > 1) for (const k of Object.keys(vis)) vis[k] /= tot;
            // a short gap between sounding events keeps the mouth on the face (no flicker); long gaps close it
            const prev = E[i0], next = E[i0 + 1];
            if (mouth < 0.3 && prev && next && prev.v && next.v && next.t0 - prev.t1 < closeGap && t > prev.t1 && t < next.t0) mouth = 0.3;
            return { viseme: vis, mouth };
        },
    };
}

// Emotion + gaze, keyed to WORDS and sections rather than seconds, so re-timing the audio can't desync a feeling.
// TL = { sections: [{name, t0, t1}], captions: [{text, t0, t1}] } (the shape voicebox/song timelines use).
// sectionBase: { sectionName: {smile, frown, wide, blush, soft, down, up, jaw} } — the resting feeling of a section.
// lineCues: [[/regex on the caption text/, {smile: 0.6, blush: 0.5}], ...] — a feeling per line, eased in and out.
// closeAfterLast: the eyes close slowly after the last caption (a day's eye closing at dusk); false to disable.
// Channel → morph (render-measured on this face):
//   smile  Smile + MouthSmileLeft/Right: the corners curl up smoothly with the value (Smile alone barely moves)
//   frown  MouthFrown, smooth · wide EyeWide, subtle · down/up EyeLookDown*/EyeLookUp*, subtle
//   soft   EyeClosedLeft/Right as given: up to ~0.5 the eyes only SHRINK to small dots; 0.7–0.9 flattens them into
//          content, sleepy slits; 1 closes them. Use 0.75–0.85 for a soft look.
//   blush  a SWITCH: the blush is a plate revealed like the mouth, re-seated on the cheek at exactly Blush 1 (see
//          installSuitMouth), so blush ≥ 0.3 shows it and below 0.3, none.
//   jaw    a silent open mouth: jaw ≥ 0.15 opens it (MOUTH_OPEN 0.3–1 with the value); below, the painted line.
const MORPHS = {
    smile: ['Smile', 'MouthSmileLeft', 'MouthSmileRight'], frown: ['MouthFrown'], wide: ['EyeWide'],
    soft: ['EyeClosedLeft', 'EyeClosedRight'], down: ['EyeLookDownLeft', 'EyeLookDownRight'],
    up: ['EyeLookUpLeft', 'EyeLookUpRight\t'],            // (digi's morph name carries a tab)
};
const SWITCHES = {
    blush: (v) => (v >= 0.3 ? { Blush: 1 } : {}),
    jaw: (v) => (v >= 0.15 ? { [MOUTH_OPEN]: 0.3 + 0.7 * Math.min(1, v) } : {}),
};
// Merge weight dicts by per-morph maximum (a lipsync pose and an emotion both may drive the same morph).
export function mergeMax(...ws) {
    const out = {};
    for (const w of ws) for (const [k, v] of Object.entries(w || {})) out[k] = Math.max(out[k] || 0, v);
    return out;
}
const smooth = (a, b, x) => { const t = Math.max(0, Math.min(1, (x - a) / (b - a))); return t * t * (3 - 2 * t); };

export function makeFaceTrack(TL, { sectionBase = {}, lineCues = [], closeAfterLast = true } = {}) {
    const sections = TL.sections || [];
    const cues = [];
    for (const c of TL.captions || []) {
        const hit = lineCues.find(([re]) => re.test(c.text));
        if (hit) cues.push({ t0: c.t0, t1: c.t1, f: hit[1] });
    }
    const lastWord = (TL.captions || []).length ? Math.max(...TL.captions.map((c) => c.t1)) : Infinity;
    return {
        at(t) {
            // inside a section → it; before the first → the FIRST (not the
            // last); in a gap or after the end → the latest one already begun
            let sec = sections.find((s) => t >= s.t0 && t < s.t1);
            if (!sec && sections.length) {
                let prev = null, first = sections[0];
                for (const s of sections) {
                    if (s.t0 < first.t0) first = s;
                    if (s.t0 <= t && (!prev || s.t0 >= prev.t0)) prev = s;
                }
                sec = prev || first;
            }
            const f = { ...((sec && sectionBase[sec.name]) || {}) };
            for (const c of cues) {
                const w = smooth(c.t0 - 0.25, c.t0 + 0.4, t) * (1 - smooth(c.t1 + 0.3, c.t1 + 0.9, t));
                if (w <= 0) continue;
                for (const [k, v] of Object.entries(c.f)) f[k] = (f[k] || 0) * (1 - w) + v * w;
                for (const k of Object.keys(f)) if (!(k in c.f)) f[k] *= 1 - 0.6 * w;
            }
            if (closeAfterLast) {
                const dusk = smooth(lastWord - 3.5, lastWord + 1.5, t);
                if (dusk > 0) { f.soft = Math.max(f.soft || 0, 0.92 * dusk); f.smile = Math.max(f.smile || 0, 0.35 * dusk); }
            }
            const out = {};
            for (const [k, v] of Object.entries(f)) {
                for (const m of MORPHS[k] || []) out[m] = Math.max(out[m] || 0, v);
                for (const [m, w] of Object.entries(SWITCHES[k]?.(v) || {})) out[m] = Math.max(out[m] || 0, w);
            }
            return out;
        },
    };
}
