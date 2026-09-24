// claudesona_wardrobe.js — outfits for the claudesona (digi's claude_suit.vrm): show/hide garment layers, repaint
// materials with procedural patterns, fold petals under hats, place the hat. The layers live in ONE VRM,
// eidoverse/assets/vrms/claude_suit_wardrobe.vrm (digi's claude_suit.vrm, CC-BY, plus garments and accessories
// modelled onto its rig; Blender source in eidoverse/assets/vrms/claude_suit_wardrobe_src/).
//
//   const { makeWardrobe, WARDROBE } = await import(new URL('claudesona_wardrobe.js', EIDOVERSE_DIR).href);
//   const wardrobe = makeWardrobe(THREE, vrm);      // wears 'suit'
//   wardrobe.wear('lab_coat_1961');                 // any WARDROBE key; cheap no-op if already worn
//   wardrobe.petals('mac_launch_1984');             // repaint only the petals with another preset's petals; null restores
//
// Guide: AGENTS.md ("Outfits — claude_suit_wardrobe.vrm"). A preset:
//   { show: [layers], paint: { material: '#hex' | { pattern, a, b, ... } }, hide: [materials], fold, hat }
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
        hat: { offset: [0, 0.018, -0.015], scale: 1.12 },
    },
};

// GLTFLoader sanitizes node names ('petal 12_L_001' -> 'petal_12_L_001')
const byName = (root, name) => root.getObjectByName(name) || root.getObjectByName(name.replace(/\s+/g, '_'));

export function makeWardrobe(THREE, vrm) {
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
    const foldQ = (root, deg) => {                                    // rotate the petal toward the back of the head
        vrm.scene.updateWorldMatrix(true, true);
        const chain = chainOf(root), last = chain[chain.length - 1];
        const tip = jointOf.get(last).child || last.children[0] || last;          // VRM1: the last node is only a tail
        const p0 = root.getWorldPosition(new THREE.Vector3()), p1 = tip.getWorldPosition(new THREE.Vector3());
        const back = new THREE.Vector3(0, 0, -1).applyQuaternion(vrm.scene.getWorldQuaternion(new THREE.Quaternion()));
        const axis = p1.sub(p0).normalize().cross(back).normalize();
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
            for (const b of chain) { b.updateMatrix(); b.updateWorldMatrix(false, true); jointOf.get(b).setInitState(); }
        }
        folded.clear(); for (const b of want.keys()) folded.add(b);
        if (globalThis.WARDROBE_DEBUG) for (const [root, d] of want) {
            const j = jointOf.get(root);
            console.log(`[wardrobe] fold ${root.name} ${d.join('/')} joint=${!!j} chain=${chainOf(root).map((b) => b.name).join('>')} ` +
                `restAngle=${(2 * Math.acos(Math.min(1, Math.abs(restQ.get(root).dot(root.quaternion)))) * 180 / Math.PI).toFixed(1)}`);
        }
    };

    // ---- hat placement: `hat: { offset: [x, y, z] (model metres, +z = the face's side), scale }`
    const hatRest = layers.boater ? { p: layers.boater.position.clone(), s: layers.boater.scale.clone() } : null;
    const placeHat = (spec) => {
        const h = layers.boater;
        if (!h || !hatRest) return;
        h.position.copy(hatRest.p); h.scale.copy(hatRest.s);
        if (!spec) return;
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

    let current = null;
    const api = {
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
            applyFold(preset.fold);
            placeHat(preset.hat);
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
