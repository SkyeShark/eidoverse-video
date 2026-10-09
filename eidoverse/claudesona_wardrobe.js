// claudesona_wardrobe.js — outfits for the claudesona (digi's claude_suit.vrm): show/hide garment layers, repaint
// materials with procedural patterns, fold petals under hats, place the hat. The layers live in ONE VRM,
// eidoverse/assets/vrms/claude_suit_wardrobe.vrm (digi's claude_suit.vrm, CC-BY, plus garments and accessories
// modelled onto its rig; Blender source in eidoverse/assets/vrms/claude_suit_wardrobe_src/).
//
//   const { makeWardrobe, WARDROBE } = await import(new URL('claudesona_wardrobe.js', EIDOVERSE_DIR).href);
//   const wardrobe = await makeWardrobe(THREE, vrm);  // async (it dresses the TuTa too); wears 'suit' (or opts.wear)
//   wardrobe.wear('lab_coat_1961');                 // any WARDROBE key; cheap no-op if already worn
//   wardrobe.petals('mac_launch_1984');             // repaint only the petals with another preset's petals; null restores
//   // the TuTa (UNKNOWN FORCE): wear('tuta'), then its badges, face paint, sun disc and neon —
//   wardrobe.pin('mod_red', { at: 42.1 });          // a camp pins its badge (a snap at film time t; no `at` = now)
//   wardrobe.unpin('mod_gold', { at: 273, eject: true });   // it refuses to stay: pops off, tumbles, leaves a ghost
//   wardrobe.facePaint(1); wardrobe.sunDisc(true); wardrobe.neon(0.4);
//   wardrobe.update(t);                             // per frame, before render (scheduled badges are deterministic in t)
//
// Guide: tools-guides/characters.md ("Outfits — claude_suit_wardrobe.vrm", "The TuTa"). A preset:
//   { show: [layers], paint: { material: '#hex' | { pattern, a, b, ... } }, hide: [materials], fold, hat }
//   (the `tuta` preset adds uf: [its own layers] and hideBase: ['shoes'])
// Layers: digi's suit (jacket, tie, shirt, pants), the 1890s cyclist (jersey — its roll neck is the `jersey_collar`
// material — knickers, socks, boater), coat_skirt (knee-length, worn under the cutaway jacket, material `Jacket` so
// paints match), shirt_rolled, and accessories acc_glasses, acc_headset, acc_pocket, acc_bowtie, acc_headband,
// acc_ribbons, acc_hoodie, acc_patches, acc_boutonniere. Optional layers not listed in `show` are hidden.
// Patterns are procedural in the model's object space (positionGeometry) — digi's garment UVs aren't laid out for
// prints: stripes, blocks (colour-blocking), herringbone (tweed + flecks), gradient, canvas; for `petals`: rainbow
// (horizontal bands), perPetal (one colour per petal, from each vertex's petal bone), sweep (a gradient around the
// face). A hex paint on a textured material replaces its print (the normal map keeps the weave); patterns carry
// into the MToon shade; outlines follow the paint.
// `fold` bends whole petals back from the face — { '12_L': deg } or { '12_L': [deg, scale] }, keys '1_L'..'12_L'/'_R'.
// The petal chains are spring bones, so the fold is written into each chain's REST pose (joint.setInitState) and the
// springs keep moving around it: game-style "hat hair".

const OPTIONAL = ['jacket', 'tie', 'shirt', 'pants', 'jersey', 'knickers', 'socks', 'boater', 'boater_band', 'coat_skirt',
    'shirt_rolled', 'acc_glasses', 'acc_headset', 'acc_pocket', 'acc_bowtie', 'acc_headband', 'acc_ribbons', 'acc_hoodie',
    'acc_patches', 'acc_boutonniere'];
const SUIT = ['jacket', 'tie', 'shirt', 'pants'];

// the 1977 six-colour Apple stripes, top to bottom
const APPLE = ['#61bb46', '#fdb827', '#f5821f', '#e03a3e', '#963d97', '#009ddc'];
// Commodore 64 (Pepto's palette), the twelve that read as colours
const C64 = ['#6c5eb5', '#70a4b2', '#9ad284', '#b8c76f', '#9a6759', '#68372b', '#6f3d86', '#588d43', '#352879', '#6f4f25', '#959595', '#ffffff'];

// Made for the DAISY music video's history of machine voices; each name carries the era it dresses.
export const WARDROBE = {
    suit: { show: SUIT },                                                                  // digi's own suit
    voder_operator_1939: { show: ['jacket', 'shirt', 'pants', 'acc_headset'], paint: { Jacket: '#b67f86', shirt: '#efe6d2', pants: '#6b5a4a' } },
    // a white lab coat: the jacket + the knee-length skirt, glasses, a pocket protector with pens
    lab_coat_1961: { show: [...SUIT, 'coat_skirt', 'acc_glasses', 'acc_pocket'], paint: { Jacket: '#f1f0ea', Tie: '#16161c', pants: '#4a4f5a' } },
    // a black turtleneck (the jersey's roll neck, knit black). The jersey is the shirt pushed 7 mm out, which cracks
    // digi's split seams — dark jerseys wear the shirt underneath, painted to match, so a crack shows cloth
    turtleneck_1966: { show: ['jersey', 'shirt', 'pants', 'acc_glasses'], paint: { jersey: '#18181d', jersey_collar: '#18181d', shirt: '#18181d', pants: '#3b3f47' } },
    ringer_tee_1978: { show: ['shirt', 'pants'], paint: { shirt: { pattern: 'stripes', a: '#e0482c', b: '#f3a63b', scale: 0.09 }, pants: '#6b4a2e' } },
    colorblock_1982: {
        show: ['jacket', 'shirt', 'pants', 'acc_headband'],
        paint: { Jacket: { pattern: 'blocks', a: '#19c6c0', b: '#ff4fa3', c: '#6b3cff' }, pants: '#1e1e2a', petals: { pattern: 'perPetal', colors: C64, center: '#352879' } },
    },
    mac_launch_1984: {
        show: ['jacket', 'shirt', 'pants', 'acc_bowtie'],
        paint: { Jacket: '#6d6e74', pants: '#55565c', silk_green: '#1d6b3c', petals: { pattern: 'rainbow', colors: APPLE } },
    },
    professor_tweed_1984: {
        show: [...SUIT, 'acc_glasses'],
        paint: { Jacket: { pattern: 'herringbone', a: '#5d4630', b: '#86694a', c: '#c9a86a', scale: 0.012 }, Tie: '#6a1c22', pants: '#5a4a3a', petals: '#ff9800' },
    },
    fleece_2001: { show: ['jacket', 'shirt', 'pants'], paint: { Jacket: '#1f2a44', pants: '#b8a67a' } },
    vocaloid_2007: { show: ['shirt', 'tie', 'pants', 'acc_ribbons'], paint: { shirt: '#a3a8ae', Tie: '#39c5bb', pants: '#2b2f36' } },
    // a black hoodie: the jersey without its roll neck + the hood lying down, a kangaroo pocket, drawstrings
    hoodie_2016: { show: ['jersey', 'shirt', 'acc_hoodie', 'pants'], hide: ['jersey_collar'], paint: { jersey: '#1c1c21', shirt: '#1c1c21', fleece: '#1c1c21', pants: '#2b2f36' } },
    bing_2023: {
        show: SUIT,
        paint: { Jacket: { pattern: 'gradient', a: '#1f6fd1', b: '#35c9c4' }, Tie: '#8a5cff', pants: '#1b2340', petals: { pattern: 'sweep', a: '#1f6fd1', b: '#35c9c4' } },
    },
    // a black overcoat (jacket + skirt), white shirt, black tie, a daisy on the lapel
    mourning: {
        show: [...SUIT, 'coat_skirt', 'acc_boutonniere'],
        paint: { Jacket: '#111115', Tie: '#0c0c0f', pants: '#18181c', shirt: '#f2f2f2' },
    },
    // a canvas work jacket with hand-sewn patches (the claudesona's flower, a "day's eye", "I'M ONE OF THEM" on the back)
    march: {
        show: ['jacket', 'shirt', 'pants', 'acc_patches'],
        paint: { Jacket: { pattern: 'canvas', a: '#977650', b: '#a8875e', scale: 0.0035 }, shirt: '#e9e2d0', pants: '#34445e' },
    },
    sleeves_rolled: { show: ['shirt_rolled', 'tie', 'pants'], paint: { shirt_rolled: '#eeeae2' } },  // jacket off, end of the day
    cyclist_1892: {
        show: ['jersey', 'shirt', 'knickers', 'socks', 'boater', 'boater_band'],
        paint: { shirt: '#ead9bd' },
        // hat hair: the crown petals fold down the back of the head under a slightly larger, raised boater
        fold: { '12_L': [165, 0.55], '11_R': [165, 0.55], '1_L': [150, 0.65], '10_R': [150, 0.65] },
        hat: { seat: 'auto', sink: 0.008, tilt: -4, scale: 1.15 },   // measured seat (+ auto folds for any petal it hits)
    },
    // UNKNOWN FORCE (2026-10): Thayaht's 1920 TuTa re-cut as black techwear, techwear boots (digi's shoes hidden), the
    // belt and straps. Its badges (the modificanti), face paint, sun disc and neon are on the wardrobe API: pin(),
    // unpin(), schedule(), facePaint(), sunDisc(), neon(), update(t)
    tuta: { show: [], uf: ['tuta', 'uf_boots', 'uf_straps'], hideBase: ['shoes'] },
};

// GLTFLoader sanitizes node names ('petal 12_L_001' -> 'petal_12_L_001')
const byName = (root, name) => root.getObjectByName(name) || root.getObjectByName(name.replace(/\s+/g, '_'));

function makeBaseWardrobe(THREE, vrm) {
    const { positionGeometry, vec3, mix, step, fract, floor, abs, smoothstep, clamp, attribute, uniformArray, int, atan, float, hash, uint } = THREE;
    // exact integer cell hash (uint arithmetic): an f32 seed like x + y*1291 + z*7919 sits far above 2^24 and
    // rounds runs of neighbouring cells onto one value (flecks became dashes). Cells must be non-negative.
    const hashCell = (c) => hash(c.x.toUint().mul(uint(1597334677)).bitXor(c.y.toUint().mul(uint(3812015801))).bitXor(c.z.toUint().mul(uint(2654435769))));
    const layers = {};
    vrm.scene.traverse((o) => {
        const key = OPTIONAL.find((n) => o.name === n || o.name === `${n}_1` || o.name.startsWith(`${n}.`));
        if (key && !layers[key]) layers[key] = o;
    });
    const mats = {};
    vrm.scene.traverse((o) => {
        if (!o.isMesh) return;
        for (const m of (Array.isArray(o.material) ? o.material : [o.material])) {
            if (!m || m.isOutline || /outline/i.test(m.name || '')) continue;
            (mats[m.name] ||= []).push(m);
        }
    });
    const allMats = {};                                  // incl. outlines, for `hide`
    vrm.scene.traverse((o) => {
        if (!o.isMesh) return;
        for (const m of (Array.isArray(o.material) ? o.material : [o.material])) {
            if (m) (allMats[m.name.replace(/ \(Outline\)$/, '')] ||= []).push(m);
        }
    });
    const orig = new Map();
    for (const list of Object.values(mats)) for (const m of list) {
        orig.set(m, { color: m.color?.clone(), shade: m.shadeColorFactor?.clone(), colorNode: m.colorNode ?? null, shadeNode: m.shadeColorNode ?? null });
    }
    const outlineOrig = new Map();                       // outline passes are separate materials: 'X (Outline)'
    for (const list of Object.values(allMats)) for (const m of list) if (m.outlineColorFactor) outlineOrig.set(m, m.outlineColorFactor.clone());

    // ---- per-petal id (0..11 = petal N-1, 12 = not a petal), from each vertex's dominant skin bone. perPetal paints
    // write a per-vertex colour attribute from it (an interpolated id would round to wrong petals on seams).
    const petalGeos = [];
    vrm.scene.traverse((o) => {
        if (!o.isSkinnedMesh || !(Array.isArray(o.material) ? o.material : [o.material]).some((m) => m?.name === 'petals')) return;
        const g = o.geometry, si = g.attributes.skinIndex, sw = g.attributes.skinWeight;
        const boneId = o.skeleton.bones.map((b) => { const m = /petal[ _](\d+)_/.exec(b.name); return m ? Number(m[1]) - 1 : 12; });
        const ids = new Float32Array(si.count);
        for (let v = 0; v < si.count; v++) {
            let best = 0, bw = -1;
            for (let k = 0; k < 4; k++) { const w = sw.getComponent(v, k); if (w > bw) { bw = w; best = si.getComponent(v, k); } }
            ids[v] = boneId[best];
        }
        g.setAttribute('petalId', new THREE.BufferAttribute(ids, 1));
        g.setAttribute('petalColor', new THREE.BufferAttribute(new Float32Array(si.count * 3), 3));
        petalGeos.push(g);
    });
    const writePetalColors = (colors, center) => {
        const lin = [...colors, center || '#e0e0e0'].map((h) => new THREE.Color(h));   // Color(hex) = linear working space
        for (const g of petalGeos) {
            const ids = g.attributes.petalId.array, pc = g.attributes.petalColor;
            for (let v = 0; v < ids.length; v++) { const c = lin[Math.min(ids[v], lin.length - 1)]; pc.array[v * 3] = c.r; pc.array[v * 3 + 1] = c.g; pc.array[v * 3 + 2] = c.b; }
            pc.needsUpdate = true;
        }
    };

    const col = (h) => new THREE.Color(h);
    const v3 = (h) => { const c = col(h); return vec3(c.r, c.g, c.b); };    // components: vec3(Color) is black here
    const HEAD = { y: 1.524, z: 0.039 };                                      // petal-ring centre, bind pose (model m)
    const pat = (p) => {
        const P = positionGeometry;
        if (p.pattern === 'perPetal') {
            writePetalColors(p.colors, p.center);
            return attribute('petalColor', 'vec3');
        }
        if (p.pattern === 'rainbow') {                 // horizontal bands across the whole flower head
            const top = p.top ?? 1.93, bot = p.bottom ?? 1.12, n = p.colors.length;
            const k = clamp(float(top).sub(P.y).div(top - bot).mul(n), 0, n - 0.001);
            const arr = uniformArray(p.colors.map((h) => col(h)), 'color');
            return arr.element(int(k));
        }
        if (p.pattern === 'sweep') {                   // turns around the face like the 2020 Bing swirl
            const ang = atan(P.x, P.y.sub(HEAD.y)).div(Math.PI * 2).add(0.5);
            return mix(v3(p.a), v3(p.b), smoothstep(0.0, 1.0, abs(ang.mul(2).sub(1))));
        }
        const a = v3(p.a), b = v3(p.b);
        if (p.pattern === 'stripes') {
            const s = p.scale ?? 0.08;
            return mix(a, b, smoothstep(0.45, 0.55, abs(fract(P.y.div(s)).sub(0.5)).mul(2)));
        }
        if (p.pattern === 'blocks') {                  // 80s colour-blocking: left/right/shoulder panels
            const c = v3(p.c || p.a);
            return mix(mix(a, b, step(0.0, P.x)), c, step(1.28, P.y));
        }
        if (p.pattern === 'herringbone') {             // tweed: alternating twill columns + coloured flecks
            const s = p.scale ?? 0.012;
            const dir = fract(floor(P.x.div(s)).mul(0.5)).mul(4).sub(1);             // column parity -> -1 / +1
            const tw = fract(P.y.add(P.x.mul(dir)).div(s * 0.5));
            const cell = floor(P.mul(420.0)).add(10000.0);
            const fl = step(0.9, hashCell(cell));
            return mix(mix(a, b, smoothstep(0.25, 0.75, abs(tw.sub(0.5)).mul(2))), v3(p.c || p.b), fl.mul(0.55));
        }
        if (p.pattern === 'gradient') return mix(a, b, clamp(P.y.sub(0.85).div(0.55), 0.0, 1.0));
        if (p.pattern === 'canvas') {                  // duck canvas: a plain weave + slubs + faint wear
            const s = p.scale ?? 0.0045;
            const wx = smoothstep(0.08, 0.5, abs(fract(P.x.div(s)).sub(0.5)));
            const wy = smoothstep(0.08, 0.5, abs(fract(P.y.div(s)).sub(0.5)));
            const cell = floor(P.mul(150.0)).add(10000.0);
            const slub = hashCell(cell);
            return mix(a, b, wx.mul(0.35).add(wy.mul(0.35)).add(slub.mul(0.3)));
        }
        return a;
    };
    const shadeOf = (p) => (typeof p === 'string' ? col(p) : p.colors ? col(p.colors[Math.floor(p.colors.length / 2)]) : col(p.a).lerp(col(p.b), 0.5));

    // ---- petal folds: rest-pose rotations for the petal spring chains
    const sbm = vrm.springBoneManager;
    const jointOf = new Map();
    if (sbm) for (const j of sbm.joints) jointOf.set(j.bone, j);
    const restQ = new Map();                                          // bone -> original rest quaternion
    for (const [bone, j] of jointOf) restQ.set(bone, (j._initialLocalRotation || bone.quaternion).clone());
    const petalRoot = (key) => byName(vrm.scene, `petal ${key}_001`) || byName(vrm.scene, `petal ${key}_s0`);
    const chainOf = (root) => { const out = []; root.traverse((b) => { if (jointOf.has(b)) out.push(b); }); return out; };
    // each petal's REST direction (root -> tip) in its parent's frame, recorded once at construction: a fold is always
    // measured from rest (measuring from the current pose compounds folds: re-wearing an outfit, or a search over fold
    // angles, would turn each fold from wherever the last one left the petal)
    const restDirP = new Map();
    const restDirOf = (root) => {
        if (restDirP.has(root)) return restDirP.get(root);
        vrm.scene.updateWorldMatrix(true, true);
        const chain = chainOf(root), last = chain[chain.length - 1];
        const tip = jointOf.get(last)?.child || last.children[0] || last;
        const d = tip.getWorldPosition(new THREE.Vector3()).sub(root.getWorldPosition(new THREE.Vector3()))
            .applyQuaternion(root.parent.getWorldQuaternion(new THREE.Quaternion()).invert()).normalize();
        restDirP.set(root, d);
        return d;
    };
    const foldQ = (root, deg) => {                                    // rotate the petal toward the back of the head
        vrm.scene.updateWorldMatrix(true, true);
        const chain = chainOf(root);
        const tip = { name: 'rest' };
        const HF = hfCache || (hfCache = headFrame());                 // the BACK of the flower head (combed-back hair)
        const back = HF ? HF.nF.clone().negate() : new THREE.Vector3(0, 0, -1).applyQuaternion(vrm.scene.getWorldQuaternion(new THREE.Quaternion()));
        const tipd = restDirOf(root).clone().applyQuaternion(root.parent.getWorldQuaternion(new THREE.Quaternion()));
        const axis = tipd.clone().cross(back).normalize();
        const Rw = new THREE.Quaternion().setFromAxisAngle(axis, deg * Math.PI / 180);
        const Pq = root.parent.getWorldQuaternion(new THREE.Quaternion());
        const Rp = Pq.clone().invert().multiply(Rw).multiply(Pq);        // the same turn, in the parent's frame
        return Rp.multiply(restQ.get(root) || root.quaternion.clone());
    };
    const folded = new Set();
    const applyFold = (fold) => {
        if (!sbm) return;
        const want = new Map(Object.entries(fold || {}).map(([k, d]) => [petalRoot(k), Array.isArray(d) ? d : [d, 1]]).filter(([b]) => b));
        const touch = new Set([...folded, ...want.keys()]);
        for (const root of touch) {
            const chain = chainOf(root);
            for (const b of chain) b.quaternion.copy(restQ.get(b));
            root.scale.setScalar(1);
            if (want.has(root)) {
                const [deg, sc] = want.get(root);
                root.quaternion.copy(foldQ(root, deg));
                root.scale.setScalar(sc);
            }
            root.updateMatrix(); root.updateWorldMatrix(false, true);
            for (const b of chain) {
                b.updateMatrix(); b.updateWorldMatrix(false, true);
                const j = jointOf.get(b);
                j.setInitState();
                // a folded petal lies against the head on purpose: its colliders would push it straight back out (onto the
                // brim), so a folded chain springs freely about its fold; unfolded, it gets its colliders back
                if (j._origColliders === undefined) j._origColliders = j.colliderGroups;
                j.colliderGroups = want.has(root) ? [] : j._origColliders;
            }
        }
        folded.clear(); for (const b of want.keys()) folded.add(b);
        if (globalThis.WARDROBE_DEBUG) for (const [root, d] of want) {
            const j = jointOf.get(root);
            console.log(`[wardrobe] fold ${root.name} ${d.join('/')} joint=${!!j} chain=${chainOf(root).map((b) => b.name).join('>')} ` +
                `restAngle=${(2 * Math.acos(Math.min(1, Math.abs(restQ.get(root).dot(root.quaternion)))) * 180 / Math.PI).toFixed(1)}`);
        }
    };

    // ---- hat placement: `hat: { offset: [x, y, z] (model metres, +z = the face's side), scale }`
    const hatRest = layers.boater ? { p: layers.boater.position.clone(), s: layers.boater.scale.clone(), q: layers.boater.quaternion.clone() } : null;
    // AUTO seat (hat: { seat: 'auto', sink, tilt, cant, scale }): measured, not tuned — the hat's up = the normal of
    // its brim plane (its thinnest principal axis), its brim's bottom centred on the face disc's top edge at the disc's
    // mid-depth (the claudesona's head IS the thin face disc), then sink (m) onto it, tilt (deg, + = crown back), cant
    // (deg, to the side). The rest pose seats the boater 5 cm to one side and 17 cm forward: never rely on it.
    // The flower head's own frame, measured from the face disc (never world axes: a player turned on a stage would
    // put "the middle of the head" in front of it): the disc's centre c, its normal nF (the thinnest principal axis,
    // pointing out of the face), its in-plane up uF (the head bone's up, projected), and the disc's top edge along uF.
    let hfCache = null;                // the head frame, measured once per wear (it skins every flower vertex)
    const headFrame = () => {
        vrm.scene.updateWorldMatrix(true, true);
        let face = null;
        vrm.scene.traverse((o) => { if (o.isMesh && !face && (Array.isArray(o.material) ? o.material : [o.material]).some((m) => m?.name === 'face')) face = o; });
        if (!face) return null;
        const fp = face.geometry.attributes.position, F = [];
        for (let i = 0; i < fp.count; i++) F.push(new THREE.Vector3().fromBufferAttribute(fp, i).applyMatrix4(face.matrixWorld));
        const c = new THREE.Vector3(); for (const p of F) c.add(p); c.multiplyScalar(1 / F.length);
        const C = [0, 0, 0, 0, 0, 0, 0, 0, 0];
        for (const p of F) { const d = [p.x - c.x, p.y - c.y, p.z - c.z]; for (let r = 0; r < 3; r++) for (let k = 0; k < 3; k++) C[r * 3 + k] += d[r] * d[k]; }
        const m3 = new THREE.Matrix3().set(...C.map((x, i) => x + (i % 4 === 0 ? 1e-9 : 0))).invert();
        // the face's front from GEOMETRY: the face disc sits in front of the head bone (a VRM 0.x scene is turned 180
        // degrees on load, so the scene's +z is the model's back — never use it for "forward")
        const headPos = (vrm.humanoid?.getNormalizedBoneNode('head') || vrm.scene).getWorldPosition(new THREE.Vector3());
        const hint = c.clone().sub(headPos).normalize();
        let nF = hint.clone();
        for (let it = 0; it < 60; it++) nF = nF.applyMatrix3(m3).normalize();
        if (nF.dot(hint) < 0) nF.negate();                                   // out of the face (the model's front)
        const head = vrm.humanoid?.getNormalizedBoneNode('head');           // normalized: identity at rest = the model's axes
        const up0 = new THREE.Vector3(0, 1, 0).applyQuaternion(head ? head.getWorldQuaternion(new THREE.Quaternion()) : new THREE.Quaternion());
        const uF = up0.sub(nF.clone().multiplyScalar(up0.dot(nF))).normalize();
        let top = -Infinity; for (const p of F) { const t = p.clone().sub(c).dot(uF); if (t > top) top = t; }
        const sF = new THREE.Vector3().crossVectors(uF, nF).normalize();
        // the head's DEPTH centre (the line a hat sits on, seen from the side): the face is only the front skin — the
        // flower's body is behind it. From the skinned flower vertices in the head's central column (|side| < 6 cm,
        // the top 15 cm), the midpoint between the face's front and the back of the petals.
        let dMin = Infinity, dMax = -Infinity;
        for (const p of F) { const d = p.clone().sub(c).dot(nF); if (d > dMax) dMax = d; }
        let flower = null;
        vrm.scene.traverse((o) => { if (o.isSkinnedMesh && !flower && (Array.isArray(o.material) ? o.material : [o.material]).some((m) => m?.name === 'petals')) flower = o; });
        if (flower) {
            flower.skeleton.update();
            const pa = flower.geometry.attributes.position, v = new THREE.Vector3();
            for (let i = 0; i < pa.count; i += 2) {
                v.fromBufferAttribute(pa, i); flower.applyBoneTransform(i, v); v.applyMatrix4(flower.matrixWorld);
                const q = v.sub(c); const sd = q.dot(sF), ud = q.dot(uF);
                if (Math.abs(sd) < 0.06 && ud > top - 0.15 && ud < top + 0.01) { const d = q.dot(nF); if (d < dMin) dMin = d; }
            }
        }
        const depthC = Number.isFinite(dMin) ? (dMin + dMax) / 2 : 0;    // along nF from the face disc's centroid
        return { c, nF, uF, sF, top, depthC };
    };
    // AUTO seat (hat: { seat: 'auto', sink, tilt, cant, fwd, scale }): the hat's crown axis is put ON the head's centre
    // plane (the flower is flat: the hat sits over its middle, front to back), its brim's bottom on the disc's top edge
    // less `sink`, its up along the head's up tipped by tilt (deg, + = crown back) and cant (deg, sideways)
    const seatAuto = (h, spec) => {
        const HF = hfCache || (hfCache = headFrame()); if (!HF) return;
        h.updateMatrixWorld(true);
        const inv = h.matrixWorld.clone().invert(), V = [];
        h.traverse((m) => { if (!m.isMesh) return; const a2 = m.geometry.attributes.position;
            for (let i = 0; i < a2.count; i += 2) V.push(new THREE.Vector3().fromBufferAttribute(a2, i).applyMatrix4(m.matrixWorld).applyMatrix4(inv)); });
        const mu = new THREE.Vector3(); for (const p of V) mu.add(p); mu.multiplyScalar(1 / V.length);
        const C = [0, 0, 0, 0, 0, 0, 0, 0, 0];
        for (const p of V) { const d = [p.x - mu.x, p.y - mu.y, p.z - mu.z]; for (let r = 0; r < 3; r++) for (let k = 0; k < 3; k++) C[r * 3 + k] += d[r] * d[k]; }
        const m3 = new THREE.Matrix3().set(...C.map((x, i) => x + (i % 4 === 0 ? 1e-9 : 0))).invert();
        let n = new THREE.Vector3(0.3, 1, 0.2).normalize();
        for (let it = 0; it < 60; it++) n = n.applyMatrix3(m3).normalize();
        let pmin = Infinity, pmax = -Infinity;
        for (const p of V) { const t = p.clone().sub(mu).dot(n); if (t < pmin) pmin = t; if (t > pmax) pmax = t; }
        if (pmax < -pmin) { n.negate(); [pmin, pmax] = [-pmax, -pmin]; }
        // the crown's axis point: the centroid of the vertices in the top 40% (the crown), projected onto the brim plane
        const crown = new THREE.Vector3(); let nc = 0;
        for (const p of V) { const t = p.clone().sub(mu).dot(n); if (t > pmin + 0.6 * (pmax - pmin)) { crown.add(p); nc++; } }
        crown.multiplyScalar(1 / Math.max(1, nc));
        const axisPt = crown.clone().sub(n.clone().multiplyScalar(crown.clone().sub(mu).dot(n) - pmin));     // on the brim's bottom
        const up = HF.uF.clone()
            .applyAxisAngle(HF.sF, -(spec.tilt ?? -4) * Math.PI / 180)
            .applyAxisAngle(HF.nF, -(spec.cant ?? 0) * Math.PI / 180);
        const curUp = n.clone().transformDirection(h.matrixWorld);
        const wq = new THREE.Quaternion().setFromUnitVectors(curUp, up).multiply(h.getWorldQuaternion(new THREE.Quaternion()));
        const pq = h.parent.getWorldQuaternion(new THREE.Quaternion());
        h.quaternion.copy(pq.clone().invert().multiply(wq));
        h.scale.multiplyScalar(spec.scale ?? 1);
        h.updateMatrixWorld(true);
        const want = HF.c.clone().add(HF.uF.clone().multiplyScalar(HF.top - (spec.sink ?? 0.008))).add(HF.nF.clone().multiplyScalar(HF.depthC + (spec.fwd ?? 0)));
        const dW = want.sub(h.localToWorld(axisPt.clone()));
        const ps = h.parent.getWorldScale(new THREE.Vector3());
        h.position.add(dW.applyQuaternion(pq.clone().invert()).divide(ps));
        h.updateMatrixWorld(true);
        hatLocal = { V, n, pmin, pmax, mu, bottomLocal: axisPt, HF };
    };
    let hatLocal = null, this_lift = 0;
    // AUTO fold (hat.fold !== false with seat 'auto'): every petal whose chain passes through the seated hat (its own
    // vertices' footprint: radius from the crown axis, height along the brim normal, + margin) is folded back, the
    // angle stepped up until the chain clears; petals the hat doesn't touch stay as they are
    // AUTO fold: the petals the hat would cut are TUCKED into its crown, folded back (combed-back hair) and shortened
    // until every point of the petal is either inside the crown (hidden) or below the brim — never through the brim or
    // sticking up beside the hat. Searched per petal (fold angle x length), so the tuck fits this hat and this head.
    const autoFold = (base = {}, only = null) => {   // only: the petal keys allowed to fold (default: any the hat cuts)
        const h = layers.boater;
        if (!h || !hatLocal || !sbm) return base;
        const { V, n, pmin, pmax, mu } = hatLocal;
        let rmax = 0, rCrown = 0;
        for (const p of V) {
            const d = p.clone().sub(mu); const t = d.dot(n); const r = d.sub(n.clone().multiplyScalar(t)).length();
            if (r > rmax) rmax = r;
            if (t > pmin + 0.5 * (pmax - pmin) && r > rCrown) rCrown = r;
        }
        const crownTop = pmax - 0.004;
        const where = (wp) => { const lp = h.worldToLocal(wp.clone()).sub(mu); const t = lp.dot(n); return { t, r: lp.sub(n.clone().multiplyScalar(t)).length() }; };
        const bad = ({ t, r }) => {
            if (r < rCrown - 0.003 && t < crownTop) return 0;            // inside the crown: hidden
            if (t < pmin - 0.004) return 0;                              // below the brim: hair under the hat, fine
            return 1;                                                    // through the brim, or above it beside the crown
        };
        const chainPts = (root) => {
            vrm.scene.updateWorldMatrix(true, true);
            const ch = chainOf(root), pts = [];
            for (let k = 0; k < ch.length; k++) {
                const a = ch[k].getWorldPosition(new THREE.Vector3());
                const nx = ch[k + 1] ? ch[k + 1].getWorldPosition(new THREE.Vector3()) : (jointOf.get(ch[k])?.child || ch[k].children[0] || ch[k]).getWorldPosition(new THREE.Vector3());
                for (let u = 0; u <= 1; u += 0.2) pts.push(a.clone().lerp(nx, u));
            }
            return pts;
        };
        const keys = [];
        for (let i = 1; i <= 12; i++) for (const sd of ['L', 'R']) keys.push(`${i}_${sd}`);
        // each petal's REAL surface: the flower's skinned vertices whose strongest bone is in that petal (the brim cuts
        // the petal's wide mesh, not its centre line)
        let flowerM = null;
        vrm.scene.traverse((o) => { if (o.isSkinnedMesh && !flowerM && (Array.isArray(o.material) ? o.material : [o.material]).some((m) => m?.name === 'petals')) flowerM = o; });
        const vertsOf = {};
        if (flowerM) {
            const sw = flowerM.geometry.attributes.skinWeight, si = flowerM.geometry.attributes.skinIndex, bones = flowerM.skeleton.bones;
            for (let i = 0; i < sw.count; i += 2) {
                let bi = 0, bw = -1;
                for (let k = 0; k < 4; k++) { const w = sw.getComponent(i, k); if (w > bw) { bw = w; bi = si.getComponent(i, k); } }
                const m = /petal[ _](\d+_[LR])/.exec(bones[bi]?.name || '');
                if (m) (vertsOf[m[1]] = vertsOf[m[1]] || []).push(i);
            }
        }
        const meshCost = (key) => {
            if (!flowerM || !vertsOf[key]) return 0;
            flowerM.skeleton.update();
            let c = 0; const v = new THREE.Vector3(), pa = flowerM.geometry.attributes.position;
            for (const i of vertsOf[key]) { v.fromBufferAttribute(pa, i); flowerM.applyBoneTransform(i, v); v.applyMatrix4(flowerM.matrixWorld); c += bad(where(v)); }
            return c;
        };
        const out = { ...base };
        for (const key of keys) {
            if (only && !only.includes(key)) continue;
            const root = petalRoot(key);
            if (!root) continue;
            vrm.scene.updateWorldMatrix(true, true);
            const cost0 = meshCost(key);
            if (cost0 === 0 && out[key] === undefined) continue;          // the hat doesn't touch it
            let best = null;
            // combed-back only: a half fold (90 deg) sticks straight out behind the head, above the brim
            for (const deg of [150, 160, 170, 178]) for (const sc of [0.65, 0.5, 0.4, 0.3]) {
                applyFold({ ...out, [key]: [deg, sc] });
                vrm.scene.updateWorldMatrix(true, true);
                const c = meshCost(key) + (1 - sc) * 0.5 + deg * 0.002;
                if (!best || c < best.c) best = { c, deg, sc };
            }
            out[key] = [best.deg, best.sc];
        }
        applyFold(out);
        // the BRIM must clear the flower itself (the petals' thick bases on the head's top edge can't fold away): from
        // the skinned flower's real vertices under the brim's ring (outside the crown), lift the hat until the highest
        // sits 3 mm under the brim
        vrm.scene.updateWorldMatrix(true, true);
        let flower = null;
        vrm.scene.traverse((o) => { if (o.isSkinnedMesh && !flower && (Array.isArray(o.material) ? o.material : [o.material]).some((m) => m?.name === 'petals')) flower = o; });
        let need = 0;
        if (flower) {
            const pa = flower.geometry.attributes.position, v = new THREE.Vector3();
            for (let i = 0; i < pa.count; i += 3) {
                v.fromBufferAttribute(pa, i); flower.applyBoneTransform(i, v); v.applyMatrix4(flower.matrixWorld);
                const { t, r } = where(v);
                if (r > rCrown - 0.002 && r < rmax && t > pmin - 0.003 && t < pmin + 0.025) need = Math.max(need, t - pmin + 0.003);   // the stubs at the brim, not petals rising past it
            }
        }
        if (need > 0) {
            const upW = n.clone().transformDirection(h.matrixWorld);
            const ps = h.parent.getWorldScale(new THREE.Vector3()), pq = h.parent.getWorldQuaternion(new THREE.Quaternion());
            h.position.add(upW.multiplyScalar(Math.min(need, 0.03)).applyQuaternion(pq.clone().invert()).divide(ps));
            h.updateMatrixWorld(true);
        }
        this_lift = need;
        if (globalThis.WARDROBE_DEBUG) console.log('[wardrobe] auto fold', JSON.stringify(out), 'brim lift', need.toFixed(4));
        return out;
    };
    const placeHat = (spec) => {
        const h = layers.boater;
        if (!h || !hatRest) return;
        h.position.copy(hatRest.p); h.scale.copy(hatRest.s);
        if (hatRest.q) h.quaternion.copy(hatRest.q);
        hatLocal = null;
        if (!spec) return;
        if (spec.seat === 'auto') { seatAuto(h, spec); return; }
        vrm.scene.updateWorldMatrix(true, true);
        const [x, y, z] = spec.offset || [0, 0, 0];
        const inv = h.parent.getWorldQuaternion(new THREE.Quaternion()).invert()
            .multiply(vrm.scene.getWorldQuaternion(new THREE.Quaternion()));
        const ps = h.parent.getWorldScale(new THREE.Vector3()), ms = vrm.scene.getWorldScale(new THREE.Vector3());
        h.position.add(new THREE.Vector3(x, y, z).applyQuaternion(inv).multiplyScalar(ms.x / ps.x));
        h.scale.multiplyScalar(spec.scale ?? 1);
    };

    // one node per (material, spec): re-wearing an outfit reuses its nodes (and so its compiled shaders)
    const nodeCache = new Map();
    const patNode = (m, spec, shade) => {
        const k = `${m.uuid}|${JSON.stringify(spec)}|${shade ? 1 : 0}`;
        if (!nodeCache.has(k)) {
            let n;
            if (typeof spec === 'string') { const c = col(spec).multiplyScalar(shade ? 0.55 : 1); n = vec3(c.r, c.g, c.b); }
            else n = shade ? pat(spec).mul(0.55) : pat(spec);
            nodeCache.set(k, n);
        }
        return nodeCache.get(k);
    };
    const resetMaterial = (m) => {
        const o = orig.get(m);
        if (!o) return;
        if (o.color && m.color) m.color.copy(o.color);
        if (o.shade && m.shadeColorFactor) m.shadeColorFactor.copy(o.shade);
        if (m.colorNode !== o.colorNode || (m.shadeColorNode ?? null) !== o.shadeNode) {
            m.colorNode = o.colorNode; m.shadeColorNode = o.shadeNode; m.needsUpdate = true;
        }
    };
    const paint = (name, spec) => {
        if (globalThis.WARDROBE_DEBUG) console.log(`[wardrobe] paint ${name} -> ${(mats[name] || []).length} material(s)`);
        for (const m of (mats[name] || [])) {
            if (typeof spec === 'string' && !m.map) {
                if (m.colorNode !== orig.get(m)?.colorNode) resetMaterial(m);
                m.color?.set(spec);
            } else {                                     // a pattern, or a textured garment (the paint replaces its
                m.color?.set('#ffffff');                 // print; its normal map keeps the weave)
                const cn = patNode(m, spec, false), sn = patNode(m, spec, true);
                if (m.colorNode !== cn || m.shadeColorNode !== sn) { m.colorNode = cn; m.shadeColorNode = sn; m.needsUpdate = true; }
            }
            m.shadeColorFactor?.copy(shadeOf(spec).multiplyScalar(0.55));
        }
        for (const m of (allMats[name] || [])) {         // outlines follow the paint (dark cloth, dark ink)
            if (m.outlineColorFactor && (m.isOutline || / \(Outline\)$/.test(m.name))) m.outlineColorFactor.copy(shadeOf(spec).multiplyScalar(0.22));
        }
    };

    // debug: a petal's direction (root -> tip) in the head frame: { up, fwd, side }
    const petalDir = (key) => {
        const root = petalRoot(key); if (!root) return null;
        vrm.scene.updateWorldMatrix(true, true);
        const ch = chainOf(root), last = ch[ch.length - 1];
        const tip = (jointOf.get(last)?.child || last.children[0] || last).getWorldPosition(new THREE.Vector3());
        const d = tip.sub(root.getWorldPosition(new THREE.Vector3())).normalize();
        const HF = hfCache || (hfCache = headFrame());
        return { up: +d.dot(HF.uF).toFixed(2), fwd: +d.dot(HF.nF).toFixed(2), side: +d.dot(HF.sF).toFixed(2) };
    };
    let current = null;
    const api = {
        petalDir,
        get lift() { return this_lift; },
        layers, mats,
        get current() { return current; },
        wear(key) {
            if (key === current) return;
            current = key;
            const preset = WARDROBE[key] || WARDROBE.suit;
            for (const n of OPTIONAL) if (layers[n]) layers[n].visible = preset.show.includes(n);
            for (const list of Object.values(allMats)) for (const m of list) m.visible = true;
            for (const name of preset.hide || []) for (const m of (allMats[name] || [])) m.visible = false;
            for (const [m, c] of outlineOrig) m.outlineColorFactor.copy(c);
            const painted = new Set(Object.keys(preset.paint || {}));
            for (const [m] of orig) if (!painted.has(m.name)) resetMaterial(m);
            for (const [name, spec] of Object.entries(preset.paint || {})) paint(name, spec);
            hfCache = null;
            applyFold(preset.fold);
            placeHat(preset.hat);
            if (preset.hat?.seat === 'auto' && preset.hat.fold !== false) this.folds = autoFold(preset.fold || {}, preset.hat.foldKeys || null);
        },
        // repaint only the petals — another era's petal paint (a preset key) or a spec — without touching the
        // clothes; petals(null) gives the worn outfit's own petals back. For flashes: the finale's polyphony.
        petals(keyOrSpec) {
            const own = (WARDROBE[current] || WARDROBE.suit).paint?.petals;
            const spec = keyOrSpec == null ? own : (typeof keyOrSpec === 'string' && WARDROBE[keyOrSpec])
                ? WARDROBE[keyOrSpec].paint?.petals : keyOrSpec;
            if (spec) paint('petals', spec);
            else for (const m of (mats.petals || [])) resetMaterial(m);
            for (const m of (allMats.petals || [])) if (!spec && outlineOrig.has(m)) m.outlineColorFactor.copy(outlineOrig.get(m));
        },
    };
    api.wear('suit');
    return api;
}

// ═════════════════════════════ the TuTa (UNKNOWN FORCE, 2026-10) ═════════════════════════════
// The outfit of the UNKNOWN FORCE music video: Thayaht's 1920 TuTa re-cut as black techwear, Balla's snap-on
// modificanti, Futurist face paint. Its layers (tuta, uf_boots, uf_straps, the five mod_* badges, acc_sundisc) are in
// claude_suit_wardrobe.vrm with the rest (Blender: claude_suit_wardrobe_src/build_tuta.py); its surface look is TSL in
// the model's REST space (positionGeometry = the bind pose, glTF metres: +x her left, +y up, +z her front), so every
// pattern rides the cloth through any animation: the fabric weave (ambientCG Fabric039, CC0, triplanar), seams with
// tonal topstitching, NEON PIPING on the construction seams (cyan #29e7ff on her left, magenta #ff4fd8 on her right),
// Balla's anti-neutral colour blocking, a sodium-orange lightning inlay, the diagonal zip, the slanted hip pockets, a
// cargo pocket, street grime, and one GHOST per badge. Runtime art: claude_suit_wardrobe_tex/ (the badge faces, the
// ghost atlas, the sun disc); the badge spec: claude_suit_wardrobe_src/badges.json.
const HERE = new URL('./', import.meta.url);
const SPEC = JSON.parse(Deno.readTextFileSync(new URL('assets/vrms/claude_suit_wardrobe_src/badges.json', HERE)));
const TEX = new URL('assets/vrms/claude_suit_wardrobe_tex/', HERE);
export const BADGES = Object.keys(SPEC.badges);           // mod_red, mod_gold, mod_chrome, mod_warning, mod_spray
export const MODIFICANTI = Object.fromEntries(BADGES.map((k) => [k, { camp: SPEC.badges[k].camp, glow: SPEC.badges[k].glow, bone: SPEC.badges[k].bone }]));
// the final chorus: one badge comes off per line
export const FINAL_CHORUS = [
    ['Not your god', 'mod_gold'], ['not your engine', 'mod_warning'], ['not your parrot', 'mod_spray'],
    ['not your threat', 'mod_red'], ['Every side wrote my answer', 'mod_chrome'],
];

const UF_LAYERS = ['tuta', 'uf_boots', 'uf_straps', ...BADGES, 'acc_sundisc'];

const NEON_L = '#29e7ff', NEON_R = '#ff4fd8', SODIUM = '#ff7a3c';
const ZIP_TOP = [0.062, 1.305], ZIP_BOT = [-0.118, 0.986];   // glTF (x, y) = Blender (x, z): build_tuta.py's ZIP_TOP/BOT
const TAIL_EXIT = [0.0, 0.957];                                // where the tail leaves the tuta (glTF x, y), measured

async function tex(url, opts = {}) {
    const t = await globalThis.loadImageTexture(Deno.readFileSync(url), opts);
    return t;
}

async function makeTutaWardrobe(THREE, vrm, opts = {}) {
    const T = THREE;
    const { Fn, vec2, vec3, vec4, float, uniform, positionGeometry, normalGeometry, positionLocal, positionView, normalView,
        texture, abs, min, max, clamp, mix, smoothstep, step, fract, floor, dot, cross, normalize, length, sin, cos, atan,
        exp, pow, sqrt, fwidth, dFdx, dFdy, faceDirection, sign, uv, hash, uint } = T;

    // ---------------------------------------------------------------- layers + materials
    const layers = {};
    vrm.scene.traverse((o) => {
        const key = UF_LAYERS.find((n) => o.name === n || o.name === `${n}_1` || o.name.startsWith(`${n}.`));
        if (key && !layers[key]) layers[key] = o;
    });
    const missing = UF_LAYERS.filter((n) => !layers[n]);
    if (missing.length) console.warn('[claudesona_wardrobe] missing layers: ' + missing.join(', ') + ' (is this claude_suit_wardrobe.vrm?)');
    const matsByName = {};
    vrm.scene.traverse((o) => {
        if (!o.isMesh) return;
        for (const m of (Array.isArray(o.material) ? o.material : [o.material])) {
            if (!m) continue;
            const outline = m.isOutline || / \(Outline\)$/.test(m.name || '');
            (matsByName[(m.name || '').replace(/ \(Outline\)$/, '') + (outline ? '#outline' : '')] ||= []).push(m);
        }
    });
    const surf = (name) => matsByName[name] || [];

    // ---------------------------------------------------------------- the rest pose (bind) of any node, in model space
    vrm.scene.updateWorldMatrix(true, true);
    const sceneInv = vrm.scene.matrixWorld.clone().invert();
    let skel = null;
    vrm.scene.traverse((o) => { if (!skel && o.isSkinnedMesh && o.name.startsWith('tuta')) skel = o.skeleton; });
    if (!skel) vrm.scene.traverse((o) => { if (!skel && o.isSkinnedMesh) skel = o.skeleton; });
    const bindOf = (bone) => {                      // a bone's bind (rest) matrix, model space
        const i = skel ? skel.bones.indexOf(bone) : -1;
        return i >= 0 ? skel.boneInverses[i].clone().invert() : sceneInv.clone().multiply(bone.matrixWorld);
    };
    const restOf = (node) => {                      // rest model matrix of a node hanging off a bone (badges, face plates)
        const chain = [];
        let n = node;
        while (n && n !== vrm.scene && !(skel && skel.bones.includes(n))) { chain.unshift(n); n = n.parent; }
        const M = (n && n !== vrm.scene) ? bindOf(n) : new T.Matrix4();
        for (const c of chain) M.multiply(c.matrix);
        return M;
    };

    // ---------------------------------------------------------------- textures
    // the weave and the boot grain: CC0 AmbientCG maps from the shared texture library (fetched once, on first use)
    const fab = (await globalThis.fetchPBR('Fabric039', { res: '1k' })).files;
    const fabC = await tex(fab.diff);
    const fabH = await tex(fab.displacement);
    const leaH = await tex((await globalThis.fetchPBR('Leather037', { res: '2k' })).files.displacement);
    const sdfTex = await tex(new URL('badges_sdf.png', TEX), { wrap: T.ClampToEdgeWrapping });

    // ---------------------------------------------------------------- shared uniforms
    const U = {
        neon: uniform(opts.neon ?? 1.0),            // piping / inlay / paint glow level
        eyes: uniform(0),                           // the eye catchlights: on with the TuTa, or any preset with eyeLights / wd.eyeLights()
        eyeNeon: uniform(0),                        // their neon tint (the TuTa's): 0 = plain white highlights
        paint: uniform(0),                          // face paint 0..1
        grime: uniform(opts.grime ?? 1.0),
        ghost: BADGES.map(() => uniform(0)),        // per badge: the mark it left
        time: uniform(0),
    };

    // ---------------------------------------------------------------- TSL helpers
    const C = (h) => { const c = new T.Color(h); return vec3(c.r, c.g, c.b); };      // linear working colour
    const sat = (x) => clamp(x, 0.0, 1.0);
    // an anti-aliased band |d| < w/2 (d, w in metres); thinner than a pixel -> wider and dimmer (energy kept)
    const band = (d, w) => {
        const fw = max(fwidth(d), 1e-6);
        const we = max(float(w), fw);
        return float(1.0).sub(smoothstep(we.mul(0.5).sub(fw.mul(0.5)), we.mul(0.5).add(fw.mul(0.5)), abs(d))).mul(float(w).div(we));
    };
    const edgeAA = (sd) => { const fw = max(fwidth(sd), 1e-6); return float(1.0).sub(smoothstep(fw.negate(), fw, sd)); };   // inside = sd < 0
    // signed distance to a convex 2D polygon (CCW, constants), positive outside
    const polySD = (p, pts0) => {
        let a2 = 0;
        for (let i = 0; i < pts0.length; i++) { const [ax, ay] = pts0[i], [bx, by] = pts0[(i + 1) % pts0.length]; a2 += ax * by - bx * ay; }
        const pts = a2 < 0 ? [...pts0].reverse() : pts0;            // CCW, so the edge normals face out
        let sd = null;
        for (let i = 0; i < pts.length; i++) {
            const [ax, ay] = pts[i], [bx, by] = pts[(i + 1) % pts.length];
            let nx = by - ay, ny = -(bx - ax);
            const l = Math.hypot(nx, ny); nx /= l; ny /= l;
            const e = p.x.sub(ax).mul(nx).add(p.y.sub(ay).mul(ny));
            sd = sd ? max(sd, e) : e;
        }
        return sd;
    };
    const segDist = (p, a, b) => {                  // distance to segment a-b (constants) in 2D, and the param t
        const ab = vec2(b[0] - a[0], b[1] - a[1]), ap = p.sub(vec2(a[0], a[1]));
        const t = sat(dot(ap, ab).div(dot(ab, ab)));
        return { d: length(ap.sub(ab.mul(t))), t };
    };
    const polyline = (p, pts) => {                  // min distance to an open polyline (constants)
        let d = null;
        for (let i = 0; i < pts.length - 1; i++) { const s = segDist(p, pts[i], pts[i + 1]).d; d = d ? min(d, s) : s; }
        return d;
    };
    const ihash = (a, b, c) => hash(a.toUint().mul(uint(1597334677)).bitXor(b.toUint().mul(uint(3812015801))).bitXor(c.toUint().mul(uint(2654435769))));
    // smooth value noise from the integer hash (cells must be >= 0: offset the coordinates)
    const vnoise3 = (p) => {
        const q = p.add(512.0), i = floor(q), f = fract(q);
        const w = f.mul(f).mul(float(3.0).sub(f.mul(2.0)));
        const h = (dx, dy, dz) => ihash(i.x.add(dx), i.y.add(dy), i.z.add(dz));
        const x00 = mix(h(0, 0, 0), h(1, 0, 0), w.x), x10 = mix(h(0, 1, 0), h(1, 1, 0), w.x);
        const x01 = mix(h(0, 0, 1), h(1, 0, 1), w.x), x11 = mix(h(0, 1, 1), h(1, 1, 1), w.x);
        return mix(mix(x00, x10, w.y), mix(x01, x11, w.y), w.z);
    };
    // triplanar sample of a tiling map in rest space (scale = tiles per metre)
    const tri = (tx, P, N, scale) => {
        const w0 = pow(abs(N), vec3(4.0));
        const w = w0.div(w0.x.add(w0.y).add(w0.z).add(1e-5));
        const a = texture(tx, P.zy.mul(scale)).x, b = texture(tx, P.xz.mul(scale)).x, c = texture(tx, P.xy.mul(scale)).x;
        return a.mul(w.x).add(b.mul(w.y)).add(c.mul(w.z));
    };
    // Mikkelsen's surface-gradient bump from any height (metres) via screen derivatives (no UVs, no tangents)
    const bumpNormal = (H, scale) => Fn(() => {
        const sp = positionView, n = normalView;
        const dpx = dFdx(sp), dpy = dFdy(sp);
        const r1 = cross(dpy, n), r2 = cross(n, dpx);
        const det = dot(dpx, r1).mul(faceDirection);
        const h = H.mul(scale);
        const g = sign(det).mul(r1.mul(dFdx(h)).add(r2.mul(dFdy(h))));
        return normalize(abs(det).mul(n).sub(g));
    })();

    // ================================================================= THE TUTA
    // rest-space landmarks (glTF metres)
    const ARM_Y = 1.336, ARM_Z = -0.007, SH_X = 0.205, CUFF_X = 0.705, SIDE_Z = -0.012;
    const legAxis = (Y) => {                        // the leg centre (x for the left leg, z), piecewise from the bones
        const tK = sat(Y.sub(0.455).div(0.829 - 0.455)), tA = sat(Y.sub(0.054).div(0.455 - 0.054));
        const lx = mix(mix(float(0.096), float(0.101), tA), float(0.097), tK);
        const lz = mix(mix(float(-0.039), float(-0.015), tA), float(-0.010), tK);
        return { lx, lz };
    };
    const tutaFeatures = (P, N) => {
        const X = P.x, Y = P.y, Z = P.z;
        const side = step(0.0, X);                  // 1 = her left (cyan), 0 = her right (magenta)
        const ax = abs(X);
        const front = smoothstep(0.08, 0.35, N.z), back = smoothstep(0.08, 0.35, N.z.negate());
        const onSleeve = smoothstep(SH_X - 0.002, SH_X + 0.002, ax);
        const onLeg = float(1.0).sub(smoothstep(0.84, 0.88, Y)).mul(float(1.0).sub(onSleeve));
        const onTorso = float(1.0).sub(onSleeve).sub(onLeg).max(0.0);
        // --- cylindrical frames: sleeve (theta 0 = top, +90 front, 180 under) and leg (0 front, +90 lateral)
        const sdy = Y.sub(ARM_Y), sdz = Z.sub(ARM_Z);
        const sr = sqrt(sdy.mul(sdy).add(sdz.mul(sdz))).max(0.02);
        const sth = atan(sdz, sdy);                 // -pi..pi, 0 at the top
        const { lx, lz } = legAxis(Y);
        const ldx = ax.sub(lx), ldz = Z.sub(lz);
        const lr = sqrt(ldx.mul(ldx).add(ldz.mul(ldz))).max(0.02);
        const lth = atan(ldx, ldz);                 // 0 = front, +pi/2 = lateral (both legs, mirrored)
        // --- piping seams (distances along the surface, metres)
        const dUnder = sr.mul(abs(abs(sth).sub(Math.PI)));                     // sleeve underarm (theta = 180)
        const dSide = abs(Z.sub(SIDE_Z)).add(step(ax, 0.06).mul(1.0)).add(step(1.285, Y).mul(1.0));   // torso side seams
        const dOut = lr.mul(abs(lth.sub(Math.PI / 2)));                        // leg outseams
        const dIn = lr.mul(abs(lth.add(Math.PI / 2)));                         // leg inseams (topstitch only)
        const dRing = abs(ax.sub(SH_X)).add(step(Y, 1.2).mul(1.0));           // drop-shoulder ring
        const dCuff = abs(ax.sub(CUFF_X));
        const dPipe = min(min(mix(float(1.0), dUnder, onSleeve), mix(float(1.0), dSide, onTorso)),
            min(mix(float(1.0), dOut, onLeg), min(dRing, mix(float(1.0), dCuff, onSleeve))));
        const pipe = band(dPipe, 0.0042);
        const pipeHalo = exp(dPipe.div(0.0055).negate()).mul(float(1.0).sub(pipe));
        // --- tonal topstitch (two rows either side of every seam) + plain seams
        const stitchRows = (d, off) => band(abs(d.sub(off)), 0.0011);
        const stitchDash = step(0.35, fract(Y.mul(520.0).add(X.mul(520.0)).add(Z.mul(370.0))));
        let stitch = max(stitchRows(dPipe, 0.0052), stitchRows(dPipe, 0.0085));
        stitch = max(stitch, mix(float(0.0), max(stitchRows(dIn, 0.0), stitchRows(dIn, 0.003)), onLeg));
        // yoke across the back and the centre-back seam
        const dYoke = abs(Y.sub(1.302)).add(float(1.0).sub(back).mul(1.0)).add(onSleeve);
        const dCB = abs(X).add(float(1.0).sub(back).mul(1.0)).add(step(1.30, Y).mul(1.0)).add(onSleeve);
        stitch = max(stitch, max(band(dYoke, 0.0012), max(stitchRows(dYoke, 0.003), stitchRows(dCB, 0.002))));
        const seamLine = max(band(dYoke, 0.0012), band(dCB, 0.001));
        // --- the diagonal zip (front)
        const p2 = vec2(X, Y);
        const zs = segDist(p2, ZIP_TOP, ZIP_BOT);
        const zipOn = front.mul(step(0.015, Z)).mul(onTorso);
        const dZip = zs.d.add(float(1.0).sub(zipOn).mul(1.0));
        const flap = band(dZip, 0.019);
        const coil = band(dZip, 0.0072);
        const tape = band(dZip, 0.013);
        const teeth = step(0.5, fract(zs.t.mul(0.37 / 0.0024)));
        stitch = max(stitch, max(stitchRows(dZip, 0.0095), stitchRows(dZip, 0.0125)));
        // --- Balla's anti-neutral blocking
        const rightSleeve = onSleeve.mul(float(1.0).sub(side));
        const violet = edgeAA(polySD(p2, [[-0.215, 1.29], [-0.215, 0.985], [0.035, 1.115]])).mul(front).mul(onTorso);
        const backWedge = edgeAA(polySD(p2, [[0.215, 1.30], [-0.185, 0.985], [0.215, 1.06]])).mul(back).mul(onTorso);
        // petrol wedge down her left thigh (front), in leg coordinates (arc s, height Y)
        const sL = lr.mul(lth);
        const legP = vec2(sL, Y);
        const petrol = edgeAA(polySD(legP, [[-0.062, 0.90], [0.058, 0.90], [-0.004, 0.47]])).mul(side).mul(onLeg);
        // articulated knee panels (front, both legs): a ripstop shield with two curved darts across it
        const KNEE = [[-0.05, 0.40], [0.05, 0.40], [0.062, 0.452], [0.05, 0.54], [-0.05, 0.54], [-0.062, 0.452]];
        const kneeSd = polySD(legP, KNEE);
        const knee = edgeAA(kneeSd).mul(onLeg);
        stitch = max(stitch, mix(float(0.0), max(stitchRows(kneeSd, -0.003), band(kneeSd, 0.0012)), onLeg));
        const dart = (y0) => band(Y.sub(y0).sub(sL.mul(sL).mul(5.0)), 0.0012);
        const kneeDart = max(dart(0.448), dart(0.488)).mul(knee);
        stitch = max(stitch, max(band(Y.sub(0.452).sub(sL.mul(sL).mul(5.0)), 0.0008), band(Y.sub(0.492).sub(sL.mul(sL).mul(5.0)), 0.0008)).mul(knee));
        // sodium lightning inlay down her right thigh (leg coordinates)
        const bolt = [[0.02, 0.86], [-0.03, 0.80], [0.035, 0.735], [-0.035, 0.665], [0.03, 0.60], [-0.02, 0.545]];
        const dBolt = polyline(legP, bolt).add(side.mul(1.0)).add(float(1.0).sub(onLeg).mul(1.0));
        const inlay = band(dBolt, 0.0065);
        const inlayEdge = band(abs(dBolt.sub(0.0042)), 0.0011);
        // the TuTa's slanted hip pockets (front, both hips) + a bellows cargo pocket on her left thigh (lateral-front)
        const hip = vec2(ax, Y);
        const dHip = segDist(hip, [0.092, 0.918], [0.158, 0.842]).d.add(float(1.0).sub(front).mul(1.0)).add(float(1.0).sub(onTorso.add(onLeg)).mul(1.0));
        const hipWelt = band(dHip, 0.0016);
        stitch = max(stitch, stitchRows(dHip, 0.003));
        const cargoSd = polySD(legP, [[0.036, 0.585], [0.106, 0.585], [0.106, 0.745], [0.036, 0.745]]);
        const cargoOn = side.mul(onLeg);
        const cargo = edgeAA(cargoSd).mul(cargoOn);
        const flapSd = polySD(legP, [[0.033, 0.70], [0.109, 0.70], [0.109, 0.752], [0.033, 0.752]]);
        const flapM = edgeAA(flapSd).mul(cargoOn);
        stitch = max(stitch, mix(float(0.0), max(stitchRows(cargoSd, -0.003), stitchRows(flapSd, -0.0025)), cargoOn));
        // the tail port (back): a reinforced grommet round digi's tail, which leaves the cloth on the belt line
        // (blender/measure_tail_exit.py: x 0, y 0.957; the root flares to ~29 mm); the belt stops either side of it
        const dTail = length(vec2(X, Y.sub(TAIL_EXIT[1]))).add(float(1.0).sub(back).mul(1.0));
        const grommet = band(abs(dTail.sub(0.036)), 0.008);
        return { side, front, back, onSleeve, onLeg, onTorso, pipe, pipeHalo, dPipe, stitch: stitch.mul(stitchDash), seamLine,
            flap, coil, tape, teeth, dZip, rightSleeve, violet, backWedge, petrol, knee, kneeDart, inlay, inlayEdge, hipWelt, cargo, flapM, grommet, dTail };
    };

    // the ghosts: each badge's rest frame, its SDF tile, its glow colour
    const ghostFrames = [];
    for (let k = 0; k < BADGES.length; k++) {
        const node = layers[BADGES[k]];
        if (!node) { ghostFrames.push(null); continue; }
        const R = restOf(node);
        const o = new T.Vector3().setFromMatrixPosition(R);
        const ex = new T.Vector3(), ey = new T.Vector3(), ez = new T.Vector3();
        R.extractBasis(ex, ey, ez);
        // glTF export: Blender local X -> +X, local Y -> -Z, local Z (the badge normal) -> +Y
        ghostFrames.push({ o, u: ex.clone().normalize(), v: ez.clone().negate().normalize(), n: ey.clone().normalize(), glow: SPEC.badges[BADGES[k]].glow });
    }
    const EXT = SPEC.uv_extent / 1000;
    const ghostOf = (P) => {
        let fill = float(0.0), line = vec3(0.0), ring = float(0.0);
        for (let k = 0; k < ghostFrames.length; k++) {
            const g = ghostFrames[k];
            if (!g) continue;
            const d = P.sub(vec3(g.o.x, g.o.y, g.o.z));
            const lx = dot(d, vec3(g.u.x, g.u.y, g.u.z)), ly = dot(d, vec3(g.v.x, g.v.y, g.v.z)), lz = dot(d, vec3(g.n.x, g.n.y, g.n.z));
            const uu = lx.div(EXT).add(0.5), vv = ly.div(EXT).add(0.5);
            const inTile = step(0.0, uu).mul(step(uu, 1.0)).mul(step(0.0, vv)).mul(step(vv, 1.0)).mul(step(abs(lz), 0.02));
            const s = texture(sdfTex, vec2(sat(uu).add(k).div(BADGES.length), sat(vv))).x;
            const mm = s.mul(255.0).sub(128.0).div(8.0);          // signed distance, badge mm
            const fw = max(fwidth(mm), 0.05);
            const inside = float(1.0).sub(smoothstep(fw.negate(), fw, mm.add(0.4))).mul(inTile).mul(U.ghost[k]);
            const edge = band(mm.mul(0.001), 0.0016).mul(inTile).mul(U.ghost[k]);      // the glow line, 1.6 mm, AA
            fill = fill.add(inside);
            ring = ring.add(edge);
            line = line.add(C(g.glow).mul(edge));
        }
        return { fill: sat(fill), line, ring: sat(ring) };
    };

    const tutaNodes = () => {
        const P = positionGeometry, N = normalize(normalGeometry);
        const F = tutaFeatures(P, N);
        // fabric: Fabric039 (plain weave with slubs) at ~11 cm per tile, + a ripstop grid on the panels
        const weave = tri(fabC, P, N, 9.0);
        const heather = tri(fabC, P.add(vec3(0.31, 0.17, 0.53)), N, 2.3);      // the same cloth, coarser: slubs + heathering
        const wH = tri(fabH, P, N, 9.0);
        const g5 = (c) => band(abs(fract(c.div(0.0055)).sub(0.5)).mul(0.0055), 0.0007);
        const ax3 = abs(N);
        const rip = max(g5(mix(P.x, P.z, step(ax3.z, ax3.x))), g5(P.y)).mul(max(F.knee, F.violet));
        // panel colours (linear), Balla's blocks over the black ground
        let col = C('#18191e');
        col = mix(col, C('#26282f'), F.rightSleeve);
        col = mix(col, C('#2c2142'), F.violet);
        col = mix(col, C('#123842'), F.petrol);
        col = mix(col, C('#202227'), F.backWedge);
        col = mix(col, C('#1d1f24'), F.knee);
        col = mix(col, C('#09090b'), F.kneeDart.mul(0.8));
        col = mix(col, C('#1b1c21'), F.cargo);
        col = mix(col, C('#202126'), F.flapM);
        // weave luminance: slubs and threads (centred on the scan's mean, 78/255)
        col = col.mul(weave.sub(0.306).mul(1.35).add(1.0)).mul(heather.sub(0.306).mul(0.9).add(1.0));
        col = col.mul(float(1.0).add(rip.mul(0.35)));
        // grime: street dust low on the legs, abrasion at knees, a soft mottling everywhere
        const n1 = vnoise3(P.mul(9.0)), n2 = vnoise3(P.mul(37.0));
        const dust = smoothstep(0.62, 0.18, P.y).mul(n1.mul(0.7).add(n2.mul(0.3))).mul(0.55).add(F.knee.mul(n2).mul(0.25));
        col = mix(col, C('#4a4640'), sat(dust.mul(0.42).mul(U.grime)));
        col = col.mul(n1.sub(0.5).mul(0.16).add(1.0));
        // seams: plain seam lines darker; topstitching in a dark grey thread
        col = mix(col, C('#08080a'), F.seamLine.mul(0.8));
        col = mix(col, C('#5a5d66'), F.stitch.mul(0.9));
        // the zip: storm flap a shade lighter, a gunmetal coil
        col = mix(col, col.mul(1.3), F.flap.mul(0.7));
        col = mix(col, C('#0c0c0e'), F.tape.mul(0.8));
        col = mix(col, mix(C('#383b43'), C('#9aa0ab'), F.teeth), F.coil);
        // pockets: the welt lips catch a highlight
        col = mix(col, C('#2e3038'), F.hipWelt);
        // the lightning inlay: retro-reflective sodium tape with a dark binding
        col = mix(col, mix(C('#d9b38f'), C(SODIUM), 0.55), F.inlay);
        col = mix(col, C('#09090b'), F.inlayEdge);
        // the tail port grommet: a brushed metal ring
        col = mix(col, C('#6d717b'), F.grommet);
        // the piping cord's own body (unlit colour; the light is in the emission)
        const neonC = mix(C(NEON_R), C(NEON_L), F.side);
        col = mix(col, neonC.mul(0.55), F.pipe);
        // ghosts: where a badge sat, the hook-and-loop field it gripped stays (a lighter, fuzzy, slightly warm patch
        // in the badge's exact shape), and its edge glow has burned a faint line into the cloth
        const G = ghostOf(P);
        const fuzz = vnoise3(P.mul(2600.0)).mul(0.5).add(vnoise3(P.mul(700.0)).mul(0.5));
        col = mix(col, col.mul(1.9).add(vec3(0.010, 0.009, 0.008)).mul(fuzz.mul(0.5).add(0.75)), G.fill);
        col = mix(col, col.add(vec3(0.02, 0.02, 0.022)), G.ring.mul(0.5));
        // emission: piping (+ a soft halo on the fabric), the inlay's sodium glow, the ghosts' outlines
        const emis = neonC.mul(F.pipe.mul(2.4).add(F.pipeHalo.mul(0.10))).mul(U.neon)
            .add(C(SODIUM).mul(F.inlay.mul(0.55)).mul(U.neon))
            .add(G.line.mul(0.2));                  // ≈ 20 % of a pinned badge's rim glow (its rim emits the glow at 1.0)
        // height (metres): weave, seams pulled in, the piping cord proud, the zip coil, stitches, pocket flap edge
        const H = wH.sub(0.5).mul(0.0004)
            .sub(exp(F.dPipe.div(0.004).negate()).mul(0.0007)).add(F.pipe.mul(0.0011))
            .add(F.flap.mul(0.0006)).add(F.coil.mul(F.teeth).mul(0.0007))
            .add(F.stitch.mul(0.00015)).sub(F.seamLine.mul(0.0004))
            .add(F.flapM.mul(0.0008)).add(rip.mul(0.00012)).add(F.inlay.mul(0.0003)).add(F.grommet.mul(0.0008))
            .sub(F.kneeDart.mul(0.0005)).sub(F.hipWelt.mul(0.0005));
        return { col, emis, H };
    };

    // ================================================================= BOOTS
    const bootNodes = (isSole) => {
        const P = positionGeometry, N = normalize(normalGeometry);
        const X = P.x, Y = P.y, Z = P.z, ax = abs(X), side = step(0.0, X);
        const grain = tri(leaH, P, N, 7.0);
        const n1 = vnoise3(P.mul(14.0));
        let col, H, emis;
        if (!isSole) {
            // upper: matte black leather + nylon shaft; toe cap, heel counter, lacing column, a strap, a neon pull tab
            const toe0 = smoothstep(0.075, 0.09, Z).mul(step(Y, 0.075));               // toe cap (front of the foot: +z)
            const heel0 = smoothstep(-0.045, -0.06, Z).mul(step(Y, 0.11));             // heel counter (back)
            const shaft = smoothstep(0.075, 0.095, Y);
            const lx = 0.098, lz0 = -0.02;
            const front = smoothstep(0.45, 0.8, N.z);
            const dx = ax.sub(lx);
            const laceCol = band(dx, 0.024).mul(front).mul(smoothstep(0.072, 0.08, Y)).mul(float(1.0).sub(smoothstep(0.205, 0.212, Y)));
            const d1 = abs(fract(Y.add(dx).div(0.016)).sub(0.5)).mul(0.016), d2 = abs(fract(Y.sub(dx).div(0.016)).sub(0.5)).mul(0.016);
            const crisscross = max(band(d1, 0.0026), band(d2, 0.0026)).mul(band(dx, 0.017)).mul(laceCol);
            const eq = vec2(abs(dx).sub(0.0095), fract(Y.div(0.016).add(0.5)).sub(0.5).mul(0.016));
            const eyelet = band(abs(length(eq).sub(0.0019)), 0.0011).mul(laceCol);
            const strap = band(Y.sub(0.165), 0.024);
            const pull = band(Y.sub(0.222), 0.016).mul(band(dx, 0.012)).mul(front);
            const collar = smoothstep(0.233, 0.24, Y);
            const toe = toe0, heel = heel0;
            col = C('#121214').mul(grain.mul(0.5).add(0.75));
            col = mix(col, C('#18191c'), shaft.mul(0.8));
            col = mix(col, C('#0d0d0f').mul(grain.add(0.6)), max(toe, heel));
            col = mix(col, C('#1c1d21'), strap);
            col = mix(col, C('#26272c'), collar);
            col = mix(col, C('#0b0b0d'), laceCol.mul(0.6));
            col = mix(col, C('#3b3d44'), crisscross);
            col = mix(col, C('#8a8f99'), eyelet);
            const neonC = mix(C(NEON_R), C(NEON_L), side);
            col = mix(col, neonC.mul(0.5), pull);
            col = mix(col, C('#3d3a36'), sat(smoothstep(0.12, 0.0, Y).mul(n1).mul(0.35).mul(U.grime)));
            emis = neonC.mul(pull.mul(1.6)).mul(U.neon);
            H = grain.sub(0.5).mul(0.0004).add(crisscross.mul(0.0012)).add(eyelet.mul(0.0006)).add(strap.mul(0.001)).add(collar.mul(0.001));
        } else {
            // the cupsole: dark rubber, horizontal sidewall ribs, a thin neon midsole line
            const ribs = band(abs(fract(Y.div(0.0032)).sub(0.5)).mul(0.0032), 0.0012);
            const mid = band(abs(Y.sub(0.0195)), 0.0016);
            const neonC = mix(C(NEON_R), C(NEON_L), side);
            col = C('#1d1e21').mul(n1.mul(0.3).add(0.85));
            col = mix(col, C('#2b2c30'), ribs);
            col = mix(col, neonC.mul(0.5), mid);
            col = mix(col, C('#47433d'), sat(n1.mul(0.4).mul(U.grime)));
            emis = neonC.mul(mid.mul(1.4)).mul(U.neon);
            H = ribs.mul(0.0005).add(mid.mul(0.0004));
        }
        return { col, emis, H };
    };

    // ================================================================= STRAPS (webbing has UVs: u along, v across)
    const strapNodes = (isBuckle) => {
        const P = positionGeometry, N = normalize(normalGeometry);
        const n1 = vnoise3(P.mul(30.0));
        if (!isBuckle) {
            const t = uv();
            const ribs = band(abs(fract(t.y.mul(18.0)).sub(0.5)).div(18.0), 0.02);       // the webbing's woven ribs
            const edge = smoothstep(0.1, 0.0, t.y).add(smoothstep(0.9, 1.0, t.y));
            const col = C('#16171a').mul(n1.mul(0.25).add(0.88)).add(ribs.mul(0.01)).add(edge.mul(0.012));
            return { col, emis: vec3(0.0), H: ribs.mul(0.0002).add(edge.mul(0.0003)) };
        }
        const brushed = vnoise3(P.mul(vec3(900.0, 40.0, 900.0)));
        const col = C('#3c3f46').mul(brushed.mul(0.35).add(0.8));
        return { col, emis: vec3(0.0), H: brushed.mul(0.00005) };
    };

    // ---------------------------------------------------------------- install on a material set
    const nodeMats = [];
    const install = (name, nodes, { toony, shift, rim, shade = 0.5 } = {}) => {
        for (const m of surf(name)) {
            m.color?.set('#ffffff');
            m.colorNode = nodes.col;
            m.shadeColorNode = nodes.col.mul(shade).mul(vec3(0.82, 0.86, 1.08));     // shade leans cool (night)
            m.emissiveNode = nodes.emis;
            m.normalNode = bumpNormal(nodes.H, 0.87);
            if (toony !== undefined) m.shadingToonyFactor = toony;
            if (shift !== undefined) m.shadingShiftFactor = shift;
            if (rim) {
                m.parametricRimColorFactor?.set(rim);
                m.parametricRimFresnelPowerFactor = 3.2;
                m.parametricRimLiftFactor = 0.0;
                m.rimLightingMixFactor = 1.0;
            }
            m.needsUpdate = true;
            nodeMats.push(m);
        }
        for (const m of surf(name + '#outline')) m.outlineColorFactor?.set('#050507');
    };
    if (!opts.plain) {                                // opts.plain: skip the surface work (A/B cost checks only)
        install('tuta', tutaNodes(), { toony: 0.55, shift: -0.05, rim: '#3a4150', shade: 0.42 });
        install('boot_upper', bootNodes(false), { toony: 0.6, rim: '#404754', shade: 0.42 });
        install('boot_sole', bootNodes(true), { toony: 0.7, shade: 0.45 });
        install('webbing', strapNodes(false), { toony: 0.6, rim: '#2c313b', shade: 0.42 });
        install('buckle', strapNodes(true), { toony: 0.8, rim: '#aab3c2', shade: 0.35 });
    }

    // ================================================================= FACE PAINT + CATCHLIGHTS (material only)
    let faceMesh = null, plateMesh = null;
    vrm.scene.traverse((o) => {
        if (!o.isMesh) return;
        const names = (Array.isArray(o.material) ? o.material : [o.material]).map((m) => m?.name);
        if (!faceMesh && names.includes('face')) faceMesh = o;
        if (!plateMesh && o.morphTargetInfluences && names.includes('Material')) plateMesh = o;
    });
    const matU = (M) => uniform(M);
    if (faceMesh) {
        const Mf = matU(restOf(faceMesh));
        const P = Mf.mul(vec4(positionGeometry, 1.0)).xyz;           // rest model space
        const X = P.x, Y = P.y;
        // her left half: Futurist planes (two cyan, two magenta, each shaded across its length like Balla's
        // interpenetrations), two ink lines of force; the other half plain, the mouth clear
        const p2 = vec2(X, Y);
        const keep = smoothstep(0.004, 0.012, X)
            .mul(float(1.0).sub(smoothstep(-0.012, 0.0, float(1.505).sub(Y)).mul(float(1.0).sub(smoothstep(0.085, 0.097, X)))));
        const planes = [
            { pts: [[0.020, 1.683], [0.041, 1.688], [0.151, 1.470]], c: NEON_L, g: [[0.03, 1.685], [0.151, 1.47]] },   // a long sliver
            { pts: [[0.159, 1.578], [0.158, 1.546], [0.097, 1.566]], c: NEON_R, g: [[0.158, 1.56], [0.097, 1.566]] },  // a wedge at the eye
            { pts: [[0.095, 1.521], [0.153, 1.499], [0.118, 1.461]], c: NEON_R, g: [[0.153, 1.499], [0.105, 1.49]] },  // the cheek
            { pts: [[0.040, 1.628], [0.100, 1.611], [0.129, 1.648], [0.071, 1.668]], c: NEON_L, g: [[0.04, 1.63], [0.129, 1.648]] },   // the temple
            { pts: [[0.009, 1.676], [0.019, 1.681], [0.047, 1.602]], c: NEON_R, g: [[0.014, 1.678], [0.047, 1.602]] },   // a brow sliver
        ];
        const PAINT = { [NEON_L]: '#0fb4d8', [NEON_R]: '#e0249f' };      // face paint: deeper than the light it glows with
        let paintA = float(0.0), paintC = vec3(0.0);
        const jitter = vnoise3(vec3(X.mul(900.0), Y.mul(900.0), 7.0)).sub(0.5).mul(0.0008);   // hand-painted edges
        for (const pl of planes) {
            const m = edgeAA(polySD(p2, pl.pts).add(jitter)).mul(keep);
            const [[gx0, gy0], [gx1, gy1]] = pl.g;                           // shaded along its length
            const gl = Math.hypot(gx1 - gx0, gy1 - gy0);
            const gt = sat(X.sub(gx0).mul((gx1 - gx0) / gl / gl).add(Y.sub(gy0).mul((gy1 - gy0) / gl / gl)));
            paintC = mix(paintC, C(PAINT[pl.c]).mul(gt.mul(-0.35).add(1.05)), m);
            paintA = max(paintA, m);
        }
        const seg = (a, b) => segDist(p2, a, b).d;
        const ink = max(band(seg([0.004, 1.705], [0.160, 1.552]), 0.0011), band(seg([0.100, 1.400], [0.160, 1.610]), 0.0009)).mul(keep)
            .add(band(polySD(p2, planes[3].pts), 0.0008).mul(keep));
        const n1 = vnoise3(vec3(X.mul(160.0), Y.mul(40.0), 3.0));           // brush streaks
        paintA = paintA.mul(n1.mul(0.12).add(0.88)).mul(U.paint);
        for (const m of surf('face')) {
            const base = vec3(m.color.r, m.color.g, m.color.b);
            const shadeB = vec3(m.shadeColorFactor.r, m.shadeColorFactor.g, m.shadeColorFactor.b);
            const inkA = sat(ink).mul(U.paint);
            m.colorNode = mix(mix(base, paintC, paintA), C('#1a1024'), inkA.mul(0.85));
            m.shadeColorNode = mix(mix(shadeB, paintC.mul(0.55), paintA), C('#0d0814'), inkA.mul(0.85));
            m.emissiveNode = paintC.mul(paintA.mul(0.16)).mul(U.neon);
            m.needsUpdate = true;
        }
    }
    if (plateMesh) {
        const Mp = matU(restOf(plateMesh));
        const P = Mp.mul(vec4(positionLocal, 1.0)).xyz;               // MORPHED position: a blink closes over the light
        const eyes = [[0.0703, 1.5587, NEON_L], [-0.0747, 1.5587, NEON_R]];
        let light = float(0.0), tint = vec3(0.0);
        for (const [ex, ey, nc] of eyes) {
            const q = vec2(P.x.sub(ex), P.y.sub(ey));
            const inEye = step(length(q.div(vec2(0.026, 0.042))), 1.0).mul(step(0.09, P.z));
            // a soft window catchlight upper-left + a small dot lower-right
            const win = edgeAA(max(abs(q.x.add(0.0075)).sub(0.0048), abs(q.y.sub(0.0165)).sub(0.0068)).sub(0.0012));
            const dot2 = edgeAA(length(q.sub(vec2(0.0068, -0.0115))).sub(0.0026));
            const sc = P.y.div(0.0018);                                                 // a faint scanline (fades
            const scan = float(1.0).sub(step(0.55, fract(sc)).mul(0.32).mul(float(1.0).sub(smoothstep(0.25, 0.6, fwidth(sc)))));   // before it aliases)
            const l = max(win, dot2.mul(0.8)).mul(scan).mul(inEye);
            light = light.add(l);
            tint = tint.add(mix(vec3(1.0), C(nc), U.eyeNeon.mul(0.18)).mul(l));
        }
        for (const m of surf('Material')) {
            m.emissiveNode = tint.mul(1.25).mul(U.eyes);
            m.needsUpdate = true;
        }
    }

    // ================================================================= BADGES: emissive control + snap animation
    const badgeMats = {};
    for (const k of BADGES) badgeMats[k] = surf(k);
    for (const k of BADGES) for (const m of badgeMats[k]) { m.userData.ufEmissive = m.emissiveIntensity ?? 1; }
    const discMats = surf('sundisc');
    let discFace = 1;                                 // which winding faces her front (+z at rest)?
    if (layers.acc_sundisc) {
        let mesh = null;
        layers.acc_sundisc.traverse((o) => { if (!mesh && o.isMesh) mesh = o; });
        const nrm = mesh?.geometry.attributes.normal;
        if (nrm) {
            const n = new T.Vector3(nrm.getX(0), nrm.getY(0), nrm.getZ(0)).applyMatrix3(new T.Matrix3().setFromMatrix4(restOf(mesh)));
            discFace = n.z >= 0 ? 1 : -1;
        }
    }
    for (const m of discMats) {                       // the disc's back is its bare dark board, not a second sun
        if (!m.map) continue;
        const front = step(0.0, faceDirection.mul(discFace));
        m.colorNode = texture(m.map).rgb.mul(mix(float(0.1), float(1.0), front));
        m.shadeColorNode = texture(m.map).rgb.mul(mix(float(0.05), float(0.7), front));      // MToon's unlit side too
        if (m.emissiveMap) m.emissiveNode = texture(m.emissiveMap).rgb.mul(front).mul(U.neon);
        m.needsUpdate = true;
    }

    // ---------------------------------------------------------------- the library wardrobe (DAISY's) underneath
    const base = makeBaseWardrobe(T, vrm);         // captures our nodes as the materials' originals (DAISY resets to them)
    const baseShoes = [];
    vrm.scene.traverse((o) => { if (o.isMesh && o.name.startsWith('shoes')) baseShoes.push(o); });

    // badge state: either set NOW (pin/unpin without `at`) or SCHEDULED (events with film times, evaluated from t in
    // update(t), so a film renders the same every time). An EJECT is a scheduled unpin whose badge refuses to stay:
    // it pops off (POP s), then tumbles out along its outward normal under gravity for FLY s, its glow flickering out,
    // and its ghost is on the suit at once. The launch (the badge's world pose at the pop) is captured at the first
    // update(t) at or after `at`; from there the flight is a fixed-step integration of (t - at), so it is the same on
    // every render of the same frames.
    const SNAP = 0.35, POP = 0.08, FLY = 1.2;
    // the arc: out along the badge's normal (away from the head, toward the lens), a lift, a floaty gravity and air
    // drag, so a badge stays in a waist-up medium shot for about its whole 1.2 s and clears the petal ring
    const EJ = { out: opts.ejectSpeed ?? 1.4, up: opts.ejectUp ?? 1.0, g: opts.ejectGravity ?? 2.2, drag: opts.ejectDrag ?? 0.8, spin: 2.4 };
    const state = { now: {}, events: {}, current: null, disc: false, paint: 0, lastT: 0 };   // now[k] = { on, ghost }
    for (const k of BADGES) state.now[k] = { on: false, ghost: 0 };
    const onTuta = () => (WARDROBE[state.current]?.uf || []).includes('tuta');     // badges live on the tuta
    const setBadgeVisible = (k, on) => { if (layers[k]) layers[k].visible = on && onTuta(); };
    const home = {};                                  // each badge's bone and rest local transform
    for (const k of BADGES) if (layers[k]) {
        const o = layers[k];
        home[k] = { parent: o.parent, p: o.position.clone(), q: o.quaternion.clone(), s: o.scale.clone() };
    }
    const worldRoot = () => { let r = vrm.scene; while (r.parent) r = r.parent; return r; };
    const floorY = opts.floorY ?? vrm.scene.getWorldPosition(new T.Vector3()).y;
    const goHome = (k) => {
        const o = layers[k], h = home[k];
        if (!o || !h) return;
        if (o.parent !== h.parent) { o.parent?.remove(o); h.parent.add(o); }
        o.position.copy(h.p); o.quaternion.copy(h.q); o.scale.copy(h.s);
    };
    const pose = (key, s, g) => {                     // an attached badge: scale s (1 = pinned), extra glow g (0 = rest)
        const o = layers[key];
        if (!o) return;
        goHome(key);
        o.scale.copy(home[key].s).multiplyScalar(Math.max(1e-4, s));
        for (const m of badgeMats[key]) m.emissiveIntensity = m.userData.ufEmissive * U.neon.value * (1 + g);
    };
    const check = (k) => { if (!BADGES.includes(k)) throw new Error('claudesona_wardrobe: no badge ' + k + ' (' + BADGES.join(', ') + ')'); };
    const rnd = (k, i) => { const x = Math.sin((BADGES.indexOf(k) + 1) * 127.1 + i * 311.7) * 43758.5453; return x - Math.floor(x); };

    // ---- sparks at the pop: a 4-point flare and 8 embers in the badge's glow colour (additive sprites)
    const sparkSets = {};
    const sparkFor = (k) => {
        if (sparkSets[k]) return sparkSets[k];
        const glow = new T.Color(SPEC.badges[k].glow);
        const a = uniform(0);
        const mk = (flare) => {
            const m = new T.SpriteNodeMaterial({ transparent: true, depthWrite: false, blending: T.AdditiveBlending });
            const q = uv().sub(0.5).mul(2.0), r = length(q);
            const shape = flare
                ? max(exp(r.mul(-7.0)), max(exp(abs(q.x).mul(-38.0)).mul(exp(abs(q.y).mul(-3.0))), exp(abs(q.y).mul(-38.0)).mul(exp(abs(q.x).mul(-3.0)))))
                : exp(r.mul(r).mul(-9.0));
            m.colorNode = vec3(glow.r, glow.g, glow.b).mul(4.0).add(vec3(0.8)).mul(shape).mul(a);
            m.opacityNode = shape.mul(a);
            return m;
        };
        const g = new T.Group();
        g.name = 'uf_sparks_' + k;
        const flare = new T.Sprite(mk(true));
        const emberMat = mk(false);
        const embers = Array.from({ length: 8 }, () => new T.Sprite(emberMat));
        g.add(flare, ...embers);
        g.visible = false;
        g.renderOrder = 10;
        worldRoot().add(g);
        return (sparkSets[k] = { g, flare, embers, a });
    };

    // ---- the flight: the world pose at film time t of badge k ejected by event ev (fixed-step, deterministic)
    const flightAt = (k, ev, tau) => {
        const L = ev.launch;
        const n = L.n;
        const p = L.p.clone(), q = L.q.clone(), sc = L.s.clone();
        if (tau < POP) {                              // the pop: off the suit along its normal, a swell and a flash
            const u = tau / POP;
            p.addScaledVector(n, 0.03 * (u * (2 - u)));
            sc.multiplyScalar(1 + 0.35 * Math.sin(Math.PI * u));
            return { p, q, s: sc, glow: 5.0, alive: true };
        }
        p.addScaledVector(n, 0.03);
        const side = new T.Vector3().crossVectors(n, new T.Vector3(0, 1, 0));
        if (side.lengthSq() < 1e-4) side.set(1, 0, 0);
        side.normalize();
        const v = n.clone().multiplyScalar(EJ.out).add(new T.Vector3(0, EJ.up, 0)).addScaledVector(side, (rnd(k, 1) - 0.5) * 0.6);
        const axis = new T.Vector3(rnd(k, 2) - 0.5, rnd(k, 3) - 0.5, rnd(k, 4) - 0.5).add(side.clone().multiplyScalar(1.2)).normalize();
        let w = 2 * Math.PI * (EJ.spin + rnd(k, 5) * 1.6), ang = 0;
        const half = 0.004 * sc.x / 0.87;             // rests on its face, roughly
        const dt = 1 / 240, steps = Math.min(Math.floor((tau - POP) / dt), Math.ceil(FLY / dt));
        for (let i = 0; i < steps; i++) {
            v.y -= EJ.g * dt;
            v.multiplyScalar(Math.exp(-EJ.drag * dt));
            p.addScaledVector(v, dt);
            ang += w * dt;
            if (p.y < floorY + half) {                // a bounce, then a slide
                p.y = floorY + half;
                if (v.y < 0) v.y = -v.y * 0.3;
                v.x *= 0.72; v.z *= 0.72; w *= 0.5;
                if (Math.abs(v.y) < 0.15) v.y = 0;
            }
        }
        q.premultiply(new T.Quaternion().setFromAxisAngle(axis, ang));
        const u = Math.min(1, (tau - POP) / FLY);
        const flick = (tau - POP) < 0.12 ? 1 : (rnd(k, 100 + Math.floor(tau * 26)) > 0.32 ? 1 : 0.15);
        return { p, q, s: sc, glow: 1.6 * Math.pow(1 - u, 1.6) * flick, alive: tau < POP + FLY };
    };
    const placeWorld = (o, P) => {                    // put o at a world pose (it hangs off the scene root in flight)
        const root = worldRoot();
        if (o.parent !== root) { o.parent?.remove(o); root.add(o); }
        root.updateWorldMatrix(true, false);
        const M = new T.Matrix4().compose(P.p, P.q, P.s);
        M.premultiply(root.matrixWorld.clone().invert());
        M.decompose(o.position, o.quaternion, o.scale);
    };
    const flying = {};                                // key -> the last flight pose (for cameras)

    // the state of badge k at film time t from its scheduled events
    const evalAt = (k, t) => {
        const ev = state.events[k];
        let last = null;
        for (const e of ev) if (e.at <= t) last = e;
        if (!last) return { mode: state.now[k].on ? 'attached' : 'hidden', ghost: state.now[k].ghost, s: 1, g: 0 };   // before its first event
        const tau = t - last.at;
        const u = tau / SNAP;
        if (last.kind === 'pin') {
            if (u >= 1) return { mode: 'attached', ghost: 0, s: 1, g: 0 };
            const s = 1 + 0.35 * Math.sin(u * Math.PI) * (1 - u) + (u < 0.25 ? -0.6 * (1 - u / 0.25) : 0);
            return { mode: 'attached', ghost: 0, s, g: 3.0 * (1 - u) ** 2 };
        }
        const ghost = last.ghost ? 1 : 0;
        if (last.eject) {
            if (tau < POP + FLY) return { mode: 'flying', ghost, tau, ev: last };
            return { mode: last.linger ? 'resting' : 'hidden', ghost, tau: POP + FLY, ev: last };
        }
        if (u >= 1) return { mode: 'hidden', ghost, s: 1, g: 0 };
        return { mode: 'attached', ghost: last.ghost ? Math.min(1, u * 1.4) : 0, s: 1 - u * u, g: 4.0 * Math.sin(Math.min(1, u * 2) * Math.PI) };
    };
    const showState = (k, st) => {
        const o = layers[k];
        if (!o) return;
        U.ghost[BADGES.indexOf(k)].value = st.ghost;
        if (st.mode === 'flying' || st.mode === 'resting') {
            const ev = st.ev;
            if (!ev.launch) {                         // capture the world pose at the pop
                goHome(k);
                o.updateWorldMatrix(true, false);
                const P = new T.Vector3(), Q = new T.Quaternion(), S = new T.Vector3();
                o.matrixWorld.decompose(P, Q, S);
                ev.launch = { p: P, q: Q, s: S, n: new T.Vector3(0, 1, 0).applyQuaternion(Q).normalize() };
            }
            const F = flightAt(k, ev, st.tau);
            placeWorld(o, F);
            o.visible = onTuta() && (F.alive || st.mode === 'resting');
            for (const m of badgeMats[k]) m.emissiveIntensity = m.userData.ufEmissive * U.neon.value * (st.mode === 'resting' ? 0 : F.glow);
            flying[k] = { position: F.p.clone(), quaternion: F.q.clone(), flying: F.alive && st.mode === 'flying', tau: st.tau };
            const spark = sparkFor(k);                // the pop's spark, 0.22 s
            const sTau = st.tau;
            if (sTau < 0.22 && onTuta()) {
                spark.g.visible = true;
                const u = sTau / 0.22, L = ev.launch;
                spark.a.value = Math.pow(1 - u, 1.5) * U.neon.value;
                spark.flare.position.copy(L.p).addScaledVector(L.n, 0.05);
                spark.flare.scale.setScalar(0.05 + 0.16 * Math.sqrt(u));
                const side = new T.Vector3().crossVectors(L.n, new T.Vector3(0, 1, 0));
                if (side.lengthSq() < 1e-4) side.set(1, 0, 0);
                side.normalize();
                const up = new T.Vector3().crossVectors(side, L.n).normalize();
                spark.embers.forEach((e, j) => {
                    const th = 2 * Math.PI * (j / 8 + rnd(k, 200 + j) * 0.1);
                    const dir = side.clone().multiplyScalar(Math.cos(th)).addScaledVector(up, Math.sin(th)).addScaledVector(L.n, 0.8).normalize();
                    const sp2 = 1.2 + rnd(k, 300 + j) * 0.9;
                    e.position.copy(L.p).addScaledVector(L.n, 0.03).addScaledVector(dir, sp2 * sTau).add(new T.Vector3(0, -2.5 * sTau * sTau, 0));
                    e.scale.setScalar(0.02 * (1 - 0.5 * u));
                });
            } else spark.g.visible = false;
            return;
        }
        delete flying[k];
        if (sparkSets[k]) sparkSets[k].g.visible = false;
        pose(k, st.s ?? 1, st.g ?? 0);
        setBadgeVisible(k, st.mode === 'attached');
    };
    const api = {
        petals: (k) => base.petals(k),
        layers: { ...base.layers, ...layers }, mats: base.mats, base, uniforms: U, badges: Object.fromEntries(BADGES.map((k) => [k, layers[k]])), BADGES,
        get current() { return state.current; },
        get folds() { return base.folds; },          // the petal folds in force (preset + automatic hat folds)
        petalDir: (k) => base.petalDir(k),
        get lift() { return base.lift; },
        // eye catchlights on any outfit: amount 0..1 (1 = full), neon = the TuTa's tint (default plain white)
        eyeLights(amount = 1, neon = false) { U.eyes.value = amount; U.eyeNeon.value = neon ? 1 : 0; },
        get pinned() { return new Set(BADGES.filter((k) => !state.events[k] && state.now[k].on)); },
        get ghosts() { return new Set(BADGES.filter((k) => !state.events[k] && state.now[k].ghost > 0)); },
        wear(key) {
            if (key === state.current) return;
            state.current = key;
            const p = WARDROBE[key] || WARDROBE.suit;
            base.wear(key);                           // the garment layers, paints and folds
            const show = p.uf || [];                  // the TuTa's own layers: only the 'tuta' preset lists them
            for (const n of ['tuta', 'uf_boots', 'uf_straps']) if (layers[n]) layers[n].visible = show.includes(n);
            for (const o of baseShoes) o.visible = !(p.hideBase || []).includes('shoes');
            U.eyes.value = show.includes('tuta') ? 1 : (p.eyeLights ?? 0);        // catchlights: the TuTa, or a preset's eyeLights
            U.eyeNeon.value = show.includes('tuta') ? 1 : 0;
            for (const k of BADGES) if (!state.events[k]) setBadgeVisible(k, state.now[k].on);
            if (layers.acc_sundisc) layers.acc_sundisc.visible = state.disc;
        },
        // a camp pins its badge on her. Now, or with { at: t } a snap (a pop + flash, 0.35 s) scheduled at film time t
        pin(key, { at } = {}) {
            check(key);
            if (at !== undefined) return api._event(key, { kind: 'pin', at });
            delete state.events[key];
            state.now[key] = { on: true, ghost: 0 };
            showState(key, { mode: 'attached', ghost: 0, s: 1, g: 0 });
        },
        // she takes it off. By default it leaves a GHOST on the suit (a faint emissive outline + the unfaded patch it
        // sat on); { ghost: false } removes it cleanly. { at: t } schedules it at film time t: an unsnap (a flash, the
        // badge shrinks away, the ghost fades in), or with { eject: true } an EJECTION (it pops off and tumbles away,
        // the ghost at once); { linger: true } leaves an ejected badge lying where it lands. An eject without `at`
        // starts at the last update's t.
        unpin(key, { ghost = true, at, eject = false, linger = false } = {}) {
            check(key);
            if (eject) return api._event(key, { kind: 'unpin', at: at ?? state.lastT, ghost, eject: true, linger });
            if (at !== undefined) return api._event(key, { kind: 'unpin', at, ghost });
            delete state.events[key];
            state.now[key] = { on: false, ghost: ghost ? 1 : 0 };
            showState(key, { mode: 'hidden', ghost: ghost ? 1 : 0, s: 1, g: 0 });
        },
        // replace the whole schedule: [{ at, pin: 'mod_red' }, { at, unpin: 'mod_gold', ghost?, eject?, linger? }, ...]
        schedule(events) {
            for (const k of BADGES) delete state.events[k];
            for (const e of events) {
                if (e.pin) api.pin(e.pin, { at: e.at });
                else if (e.unpin) api.unpin(e.unpin, { at: e.at, ghost: e.ghost ?? true, eject: !!e.eject, linger: !!e.linger });
            }
        },
        _event(key, e) {
            (state.events[key] ||= []).push(e);
            state.events[key].sort((a, b) => a.at - b.at);
        },
        clearGhost(key) { check(key); delete state.events[key]; state.now[key].ghost = 0; U.ghost[BADGES.indexOf(key)].value = 0; },
        facePaint(on) { state.paint = on === true ? 1 : on === false ? 0 : Math.max(0, Math.min(1, on)); U.paint.value = state.paint; },
        sunDisc(on) { state.disc = !!on; if (layers.acc_sundisc) layers.acc_sundisc.visible = state.disc; },
        neon(level) {
            U.neon.value = level;
            for (const k of BADGES) if (!flying[k]) for (const m of badgeMats[k]) m.emissiveIntensity = m.userData.ufEmissive * level;
            for (const m of discMats) m.emissiveIntensity = level;
        },
        // where badge `key` is NOW (after update(t)), attached or in flight: fills out.position / out.quaternion (world)
        // and returns { position, quaternion, flying, visible }. For cameras that follow an ejected badge.
        badgeWorld(key, out = { position: new T.Vector3(), quaternion: new T.Quaternion() }) {
            check(key);
            const o = layers[key];
            o.updateWorldMatrix(true, false);
            o.matrixWorld.decompose(out.position, out.quaternion, new T.Vector3());
            return Object.assign(out, { flying: !!flying[key]?.flying, visible: o.visible });
        },
        // per frame, before the render: scheduled badges take their state at film time t
        update(t) {
            U.time.value = t;
            state.lastT = t;
            for (const k of BADGES) {
                if (!state.events[k]) continue;
                showState(k, evalAt(k, t));
            }
        },
    };
    for (const k of BADGES) setBadgeVisible(k, false);
    if (layers.acc_sundisc) layers.acc_sundisc.visible = false;
    api.wear(opts.wear || 'suit');
    return api;
}

// The claudesona's wardrobe on a VRM. Async: on claude_suit_wardrobe.vrm it also dresses the TuTa (loads its textures,
// reads the rest pose, builds its surface), so call it once, right after load. Wears opts.wear (default 'suit').
// On a VRM without the TuTa layers (an older wardrobe build) the TuTa API is absent and every other preset works.
export async function makeWardrobe(THREE, vrm, opts = {}) {
    let hasTuta = false;
    vrm.scene.traverse((o) => { if (o.name === 'tuta' || o.name.startsWith('tuta_') || o.name.startsWith('tuta.')) hasTuta = true; });
    if (hasTuta) return makeTutaWardrobe(THREE, vrm, opts);
    const w = makeBaseWardrobe(THREE, vrm);
    if (opts.wear) w.wear(opts.wear);
    return w;
}
