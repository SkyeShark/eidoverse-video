// accessories.js — Bestiary accessories: forge props (hats, glasses, ...) worn on creatures' sockets, fitted from
// the sockets' seat tables and the props' own fit data (work/bestiary/patches/accessories_fit.md).
//
//   const hat = await Bestiary.accessory('top_hat');             // parse once, wear on many creatures
//   const h = oct.wear(hat, { size: 0.47, palette: { felt: 0x2a2a2e, band: 0x5a1020 } });
//   h.setPalette({ band: 0xc9a637 });  h.object;  h.remove();
//   oct.wear(hat, { depth: 0.024 });                             // or seat it by depth (the size follows)
//   const g = oct.wear(await Bestiary.accessory('round_glasses'), { palette: { plating: 0xc8c8cc } });  // silver
//   g.bones; g.pose;                                             // the rigged glasses posed on seat_glasses
//   const c = oct.wear(await Bestiary.accessory('peaked_cap'), { palette: { band: 0x303030, gold: 0xc8c8cc } });
//                                                                // a prop names its own palette zones (the cap:
//                                                                // crown, band, gold, visor); a validated pose may
//                                                                // carry its own scale, translation and tilt (the
//                                                                // cap keeps its proportions) and the prop a conform
//                                                                // morph for the creature's species (its band's give,
//                                                                // the parts it carries, its visor's hinge), set only
//                                                                // at exactly the pose it was computed for
//   const m = bee.wear(await Bestiary.accessory('monocle'), { side: 'L' });   // (B10b) on socket_eye_L by its fit.monocle
//   m.chain; m.end;                                              // the chain hung to its end on the wearer, every frame
//   m.level(); m.triangles;                                      // (B10c) its LOD: the prop's links near, coarse links, a tube
const THREE = globalThis.THREE;

const PROPS = {
    top_hat: { path: 'work/bestiary/props/top_hat.glb', asset: 'top_hat' },
    round_glasses: { path: 'work/bestiary/props/round_glasses.glb', asset: 'round_glasses' },
    peaked_cap: { path: 'work/bestiary/props/peaked_cap.glb', asset: 'peaked_cap' },
    monocle: { path: 'work/bestiary/props/monocle.glb', asset: 'monocle' },
};
// the archetype's sockets to look under, in order, when the call names none (DESIGN.md's vocabulary: a head
// archetype's hat seat hangs under socket_crown; the octopus's under socket_head_top, the mantle's crest behind its
// turrets, its own socket_crown being the ARM crown, which carries no seat). A prop never names a socket: the same
// hat seats on every creature
const DEFAULT_SOCKET = { hat: ['socket_crown', 'socket_head_top', 'socket_mantle_apex'], glasses: ['socket_eyes'] };
// a hat prop's palette zones (masks B 0, 1/3, 2/3, 1) when its material names none (the top hat's), and each zone's
// default colour (sRGB) and default base (linear) when the prop's palette_base lacks it
const HAT_ZONES = ['felt', 'band', 'binding', 'inside'];
const ZONE_DEFAULTS = { felt: [0x434343, 0.057], band: [0x272727, 0.021], binding: [0x272727, 0.021],
    inside: [0xd8cbb0, 0.55] };

// the seat math (forge/fit.py hat_placement, ported): a hat's opening (ox, oz) on a seat table's rows
// [depth, rx, rz, cx, cz, r_mean]
function interp(x, xs, ys) {
    if (x <= xs[0]) return ys[0];
    for (let i = 1; i < xs.length; i++) {
        if (x <= xs[i]) { const t = (x - xs[i - 1]) / (xs[i] - xs[i - 1]); return ys[i - 1] + t * (ys[i] - ys[i - 1]); }
    }
    return ys[ys.length - 1];
}

export function hatPlacement(table, opening, { depth = null, scale = null, maxAniso = 1.25 } = {}) {
    const col = (k) => table.map((r) => r[k]);
    const ox = opening.rx, oz = opening.rz;
    if (depth == null) {
        const rm = table.map((r) => Math.sqrt(r[1] * r[2]));
        depth = interp(Math.sqrt(ox * oz) * scale, rm, col(0));
    }
    const rx = interp(depth, col(0), col(1)), rz = interp(depth, col(0), col(2));
    const cx = interp(depth, col(0), col(3)), cz = interp(depth, col(0), col(4));
    let sx = rx / ox, sz = rz / oz;
    if (sx > sz * maxAniso) sz = sx / maxAniso;
    else if (sz > sx * maxAniso) sx = sz / maxAniso;
    return { depth, translation: [cx, -depth, cz], scale: [sx, Math.sqrt(sx * sz), sz] };
}

// two validated poses alike: translation, scale and tilt within 1e-5 (the records' rounding)
function samePose(a, b) {
    if (!a || !b || !a.translation || !b.translation || !a.scale || !b.scale) return false;
    const near = (x, y) => Math.abs(x - y) <= 1e-5;
    return a.translation.every((x, i) => near(x, b.translation[i])) && a.scale.every((x, i) => near(x, b.scale[i]))
        && near(a.tilt_deg ?? 0, b.tilt_deg ?? 0);
}

// the prop material (TSL): the baked maps, the palette by zone, sheen and the rim fuzz for cloth. Masks (the
// KHR_materials_volume thickness slot): R fuzz / sheen amount (0 off cloth), G material (the top hat: 0 felt, 1/3
// grosgrain, 2/3 leather, 1 silk), B palette zone (U.zones[0..3] at 0, 1/3, 2/3, 1), A handling wear. The ORM's B is
// the metalness (0 on the top hat; 1 on the cap's gold)
function propMaterial(src, U) {
    const { texture, uv, vec3, float, mix, normalMap, normalView, positionViewDirection, pow, abs } = THREE;
    const st = uv();
    if (src.map) src.map.colorSpace = THREE.SRGBColorSpace;
    for (const t of [src.normalMap, src.roughnessMap, src.thicknessMap]) if (t) t.colorSpace = THREE.NoColorSpace;
    const m = new THREE.MeshPhysicalNodeMaterial();
    const base = texture(src.map, st);
    const orm = texture(src.roughnessMap, st);
    const masks = src.thicknessMap ? texture(src.thicknessMap, st) : THREE.vec4(0.3, 0.0, 0.0, 0.0);
    // zone weights from B (0, 1/3, 2/3, 1: one-hot after the 8-bit round trip and bilinear seams)
    const z = masks.b.mul(3.0);
    const w0 = float(1.0).sub(z).clamp(0.0, 1.0);
    const w1 = float(1.0).sub(abs(z.sub(1.0))).clamp(0.0, 1.0);
    const w2 = float(1.0).sub(abs(z.sub(2.0))).clamp(0.0, 1.0);
    const w3 = z.sub(2.0).clamp(0.0, 1.0);
    const [z0, z1, z2, z3] = U.zones;
    const tint = U[z0].div(U[z0 + 'Base']).mul(w0).add(U[z1].div(U[z1 + 'Base']).mul(w1))
        .add(U[z2].div(U[z2 + 'Base']).mul(w2)).add(U[z3].div(U[z3 + 'Base']).mul(w3));
    let col = base.rgb.mul(tint);
    // the rim fuzz (REF_SKIN_STUDY §1's additive rim; study T's cloth layer: Fresnel exponent 1.97)
    const ndv = normalView.dot(positionViewDirection).clamp(0.0, 1.0);
    col = col.add(pow(float(1.0).sub(ndv), 2.0).mul(masks.r).mul(U.fuzz));
    m.colorNode = col;
    m.normalNode = normalMap(texture(src.normalMap, st));
    m.roughnessNode = orm.g;
    m.metalnessNode = orm.b;
    m.aoNode = orm.r;
    // sheen (Charlie): felt's soft rim; grosgrain (G ~ 1/3) a little sharper
    const isRib = float(1.0).sub(abs(masks.g.mul(3.0).sub(1.0))).clamp(0.0, 1.0);
    m.sheenNode = mix(col.mul(2.5), vec3(0.16, 0.16, 0.16), 0.5).mul(masks.r.mul(1.4)).mul(U.sheen).clamp(0.0, 0.3);
    m.sheenRoughnessNode = mix(float(0.65), float(0.45), isRib);
    m.name = (src.name || 'prop') + '_bestiary';
    return m;
}

const cache = new Map();

export async function accessory(name, opts = {}) {
    const key = opts.path || name;
    if (cache.has(key)) return cache.get(key);
    const sp = PROPS[name] || {};
    let bytes = opts.bytes || globalThis.ASSETS?.[opts.asset || sp.asset];
    if (!bytes) bytes = Deno.readFileSync(opts.path || sp.path);
    const buf = bytes.buffer.slice(bytes.byteOffset, bytes.byteOffset + bytes.byteLength);
    const gltf = await new globalThis.GLTFLoader().parseAsync(buf, '');
    const fit = gltf.userData?.bestiary?.fit || gltf.scene.children[0]?.userData?.fit;
    if (!fit) throw new Error(`[Bestiary] accessory '${name}' carries no fit data`);
    let srcMat = null;
    const mats = {};                                 // by name: a rigged prop's parts (the glasses' frame and glass)
    gltf.scene.traverse((o) => {
        if (o.isMesh && !srcMat) srcMat = o.material;
        if (o.isMesh && o.material?.name) mats[o.material.name] = o.material;
    });
    const acc = { name, kind: fit.archetype, scene: gltf.scene, fit, srcMat, mats,
        base: srcMat?.userData?.palette_base || {}, zones: srcMat?.userData?.palette_zones || HAT_ZONES };
    // (B10b) a prop's parts kept OUTSIDE its scene (the monocle's chain link and end: wear() instances them on the wearer)
    acc.parts = {};
    for (const part of ['link', 'end']) {
        const nm = fit.chain?.[part];
        const i = nm ? (gltf.parser.json.nodes || []).findIndex((n) => n.name === nm) : -1;
        if (i >= 0) acc.parts[part] = await gltf.parser.getDependency('node', i);
    }
    cache.set(key, acc);
    return acc;
}

function findSeat(creature, acc, socketName) {
    // the named socket only; else the archetype's defaults, then any socket carrying this archetype's seat
    const names = socketName ? [socketName]
        : [...new Set([...(DEFAULT_SOCKET[acc.kind] || []), ...Object.keys(creature.sockets)])];
    for (const nm of names) {
        const s = creature.sockets[nm];
        if (!s) continue;
        let seat = null;
        s.traverse((o) => { if (!seat && o.name === `seat_${acc.kind}`) seat = o; });
        if (seat) return seat;
    }
    throw new Error(`[Bestiary] no seat_${acc.kind} under ${socketName || 'any socket'} on this creature`);
}

// a zone's target colour: the caller's (a hex or CSS colour: sRGB) or else the baked mean itself (linear, exact:
// the tint is then 1 and the prop renders as baked)
function target(p, base, dflt) {
    if (p != null) return new THREE.Color(p);
    if (base) return new THREE.Color().setRGB(base[0], base[1], base[2], THREE.LinearSRGBColorSpace);
    return new THREE.Color(dflt);
}
const linear = (a, d) => (a ? new THREE.Vector3(a[0], a[1], a[2]) : new THREE.Vector3(d, d, d));

export function wear(creature, acc, opts = {}) {
    if (acc.kind === 'monocle') return wearMonocle(creature, acc, opts);      // (B10b) fitted on its eye socket, no seat node
    const seat = findSeat(creature, acc, opts.socket);
    if (acc.kind === 'glasses') return wearGlasses(creature, acc, seat, opts);
    const sf = seat.userData.fit;
    const object = acc.scene.clone(true);
    object.name = `accessory_${acc.name}`;
    const b = acc.base, p = opts.palette || {};
    // one colour and one base per palette zone, by the prop's own zone names (the top hat's binding follows its band
    // when only the band is given)
    const U = { zones: acc.zones, fuzz: THREE.uniform(opts.fuzz ?? 0.04), sheen: THREE.uniform(opts.sheen ?? 1.0) };
    for (const zn of acc.zones) {
        const [dflt, lin] = ZONE_DEFAULTS[zn] ?? [0x808080, 0.2];
        const follows = zn === 'binding' && p.binding == null && p.band != null;
        U[zn] = THREE.uniform(target(zn === 'binding' ? (p.binding ?? p.band) : p[zn], follows ? null : b[zn], dflt));
        U[zn + 'Base'] = THREE.uniform(linear(b[zn], lin));
    }
    const mat = propMaterial(acc.srcMat, U);
    object.traverse((o) => {
        if (o.isMesh) { o.material = mat; o.castShadow = true; o.receiveShadow = true; }
    });
    if (acc.kind === 'hat') {
        const opening = acc.fit.opening;
        // the depth the forge validated for this prop on this seat (brim clear, opening in contact), else the default
        const v = sf.validated?.[acc.name];
        const seated = v?.depth ?? sf.default.depth;
        // a validated POSE for this prop on this creature: the seat's entry when it carries one (t13), else the prop's
        // own conform record for the creature's species. Its scale keeps the prop's proportions (the cap: each axis
        // within 3 % of their mean, against the table's per-axis fit), its translation is the seat frame's, its tilt
        // leans it back. A caller's depth or size seats the prop by the table instead (clamped to the prop's own
        // max_aniso), where neither holds
        const species = creature.gltf?.userData?.bestiary?.species;
        const conform = acc.fit.conform?.[species];
        const own = opts.depth == null && opts.size == null;
        const vp = (v?.translation && v?.scale) ? v : (conform?.pose ?? null);
        const pl = own && vp ? { depth: null, translation: vp.translation, scale: vp.scale }
            : hatPlacement(sf.table, opening, {
                depth: opts.depth ?? (opts.size == null ? seated : null), scale: opts.size,
                maxAniso: opts.maxAniso ?? acc.fit.max_aniso ?? 1.25,
            });
        object.position.fromArray(pl.translation);
        object.scale.fromArray(pl.scale);
        // an extra jaunt about the seat's x (radians, + leans back) and a lift along the seat's +y (metres); else, at
        // the validated pose or depth only, the validated ones
        const tv = own ? (vp ?? v) : null;
        const tilt = opts.tilt ?? (tv?.tilt_deg != null ? tv.tilt_deg * Math.PI / 180 : 0);
        const lift = opts.lift ?? (own && !vp ? (v?.lift ?? 0) : 0);
        if (lift) object.position.y += lift;
        if (tilt) object.rotateX(-tilt);
        // the conform morph (the band's horizontal give, the parts it carries rigidly, the visor's hinge) was computed
        // for exactly the pose in the prop's conform record: it is set only when the pose in use IS that pose (a seat
        // entry that has moved since the cap's forge, the octopus re-exported, or a caller's jaunt leaves it at 0)
        if (own && vp && conform && samePose(vp, conform.pose) && opts.tilt == null && opts.lift == null) {
            object.traverse((o) => {
                const k = o.morphTargetDictionary?.[conform.target];
                if (o.isMesh && k != null) o.morphTargetInfluences[k] = 1.0;
            });
        }
        object.userData.placement = pl;
    } else {
        throw new Error(`[Bestiary] wear: no fit for the '${acc.kind}' archetype`);
    }
    seat.add(object);
    const handle = {
        object, uniforms: U,
        setPalette(q = {}) {
            for (const k of acc.zones) if (q[k] != null) U[k].value.set(q[k]);
        },
        remove() { seat.remove(object); },
    };
    return handle;
}

// ---------------------------------------------------------------------------------------------------- glasses
// A RIGGED prop (forge/props/round_glasses.py; accessories_fit.md §4): glasses_root at the bridge's contact point,
// lens_L / lens_R at the bridge's ends, pad_L / pad_R at the pad arms' roots, temple_L / temple_R at the hinge pins,
// hook_L / hook_R at the ear bends and cable_X1..3 down each ear hook. glassesPose is fit_pose ported (the forge's
// fit looks and its validator run that one; parity: work/bestiary/patches/glasses/js_parity.py): every point and
// axis in the seat's frame (+Z the bridge's skin normal, +Y the creature's up made perpendicular), the result per
// bone a LOCAL position, rotation (quaternion) and the root's uniform scale.
const v3 = (a) => new THREE.Vector3(a[0], a[1], a[2]);
const basis = (x, y, z) => new THREE.Matrix4().makeBasis(x, y, z);
const axisAngle = (axis, ang) => new THREE.Matrix4().makeRotationAxis(axis.clone().normalize(), ang);
const rotvec = (r) => {                       // a rotation vector (axis x angle, radians) as a matrix
    const v = v3(r || [0, 0, 0]);
    const a = v.length();
    return a < 1e-12 ? new THREE.Matrix4() : axisAngle(v, a);
};
const col = (m, i) => new THREE.Vector3().setFromMatrixColumn(m, i);
const rows3 = (R) => basis(new THREE.Vector3(R[0][0], R[1][0], R[2][0]), new THREE.Vector3(R[0][1], R[1][1], R[2][1]),
    new THREE.Vector3(R[0][2], R[1][2], R[2][2]));

export function glassesPose(sf, fit, { up = null, clearance = 0.0004, gap = 0.0003, adjust = null } = {}) {
    const adj = adjust ?? sf.validated?.[fit.prop] ?? {};
    const eyes = sf.eyes;
    // the root: on the seat's origin, `clearance` out along its +Z (a low's facets lie inside the true surface),
    // scaled so each aperture is eye_factor x its eye's radius
    const s = fit.eye_factor * 0.5 * (eyes[0].radius + eyes[1].radius) / fit.lens.radius;
    const upv = (up ? up.clone() : new THREE.Vector3(0, 1, 0)).normalize();
    const root = new THREE.Vector3(0, 0, clearance);
    const so = (sf.standoff ?? 0.003) + (adj.standoff ?? 0);
    const toRoot = (p) => p.clone().sub(root).divideScalar(s);
    const bones = { glasses_root: { position: root.clone(), rotation: new THREE.Matrix4(), scale: s } };
    const z = new THREE.Vector3(0, 0, 1);
    ['L', 'R'].forEach((sfx, k) => {
        const e = eyes[k], F = fit.sides[sfx], side = k === 0 ? 1 : -1;
        const a = v3(e.axis).normalize(), c = v3(e.centre);
        // the lens: centred on the eye's axis, the standoff past the eye's front (its skin exit when the seat carries
        // it), facing along the axis, rolled so its endpiece points at the hook (the temple then leaves toward it)
        const front = e.exit ? v3(e.exit).sub(c).dot(a) : e.radius;
        const P = toRoot(c.clone().addScaledVector(a, Math.max(front, e.radius) + so));
        const hook = toRoot(v3(e.hook));
        let hd = hook.clone().sub(P);
        hd.addScaledVector(a, -hd.dot(a));
        hd = hd.lengthSq() > 1e-18 ? hd.normalize() : new THREE.Vector3().crossVectors(upv, a).normalize()
            .multiplyScalar(side);
        const e0 = v3(F.end_dir).normalize();
        const Rl = basis(hd, new THREE.Vector3().crossVectors(a, hd), a)
            .multiply(basis(e0, new THREE.Vector3().crossVectors(z, e0), z).transpose());
        const J = v3(F.junction);
        const Lj = P.clone().sub(v3(F.lens_centre).sub(J).applyMatrix4(Rl));
        bones[`lens_${sfx}`] = { position: Lj, rotation: Rl };
        // the pad arm bent at its root by the validated rotation
        bones[`pad_${sfx}`] = { position: v3(F.pad_root).sub(J), rotation: rotvec(adj.pad?.[k]) };
        // the temple rides the lens to its hinge and is aimed at the hook (pushed off the skin); the roll that hangs
        // its ear hook down the skin's tangent there (the hook normal's, else the creature's up's) is the HOOK
        // joint's (a turn about the aim, on which the hook joint lies: rolled at the hinge, the temple's knuckle
        // stood out of the barrel)
        const Rt0 = rows3(F.temple_rot);
        const Hp = Lj.clone().add(v3(F.hinge).sub(J).applyMatrix4(Rl));
        const nh = e.hook_normal ? v3(e.hook_normal) : new THREE.Vector3(side, 0, 0);
        const T = adj.target?.[k] ? toRoot(v3(adj.target[k]))
            : hook.clone().addScaledVector(nh, (gap + 0.5 * fit.cable_d + (adj.lift?.[k] ?? 0)) / s);
        const dt = T.clone().sub(Hp).normalize();
        const cur = Rl.clone().multiply(Rt0);
        const Ra = new THREE.Matrix4().makeRotationFromQuaternion(
            new THREE.Quaternion().setFromUnitVectors(col(cur, 2).negate().normalize(), dt));
        const Rt = Ra.multiply(cur);
        let roll = 0;
        const g = e.hook_normal ? upv.clone().negate().addScaledVector(nh, nh.dot(upv)) : upv.clone().negate();
        g.addScaledVector(dt, -g.dot(dt));
        if (g.lengthSq() > 1e-12) {
            g.normalize();
            const cd = col(Rt, 1).negate();
            cd.addScaledVector(dt, -cd.dot(dt)).normalize();
            roll = Math.atan2(new THREE.Vector3().crossVectors(cd, g).dot(dt), cd.dot(g));
        }
        roll += (adj.roll?.[k] ?? 0) * Math.PI / 180;        // a validated extra roll (degrees)
        bones[`temple_${sfx}`] = { position: v3(F.hinge).sub(J), rotation: Rl.clone().transpose().multiply(Rt) };
        // the hook joint slides to the aim point (the shaft skinned between it and the temple shortens) and takes the
        // roll as a turn of -roll about its local Z (the temple's -Z is the aim); the cable joints take the validated
        // drape (else the rest curl)
        bones[`hook_${sfx}`] = { position: new THREE.Vector3(0, 0, -T.distanceTo(Hp)),
            rotation: new THREE.Matrix4().makeRotationZ(-roll) };
        for (let i = 0; i < F.cable_local.length; i++) {
            bones[`cable_${sfx}${i + 1}`] = { position: v3(F.cable_local[i]),
                rotation: rotvec(adj.cable?.[sfx]?.[i]) };
        }
    });
    return { scale: s, bones };
}

// the glasses' materials (TSL): the frame's metal from its maps (the palette tints by zone: masks B 0 the plating,
// 1/3 the base metal it wore through to, 2/3 ivory), the glass a thin transmissive dielectric (KHR_materials_
// transmission, _ior, _volume in the glb), or plain see-through with opts.lens = 'transparent'
function glassesMaterials(acc, U, opts, names = ['round_glasses', 'round_glasses_lens']) {
    // (B10b) names: the prop's frame and glass materials (the monocle's are its own: 'monocle', 'monocle_lens')
    const { texture, uv, vec3, vec4, float, normalMap, abs } = THREE;
    const st = uv();
    const src = acc.mats[names[0]] || acc.srcMat;
    const gl = acc.mats[names[1]] || src;
    for (const m of [src, gl]) {
        if (m.map) m.map.colorSpace = THREE.SRGBColorSpace;
        for (const t of [m.normalMap, m.roughnessMap, m.thicknessMap]) if (t) t.colorSpace = THREE.NoColorSpace;
    }
    const base = texture(src.map, st);
    const orm = texture(src.roughnessMap, st);
    const masks = src.thicknessMap ? texture(src.thicknessMap, st) : vec4(0.0, 0.0, 0.0, 0.0);
    const zn = masks.b.mul(3.0);
    const w0 = float(1.0).sub(zn).clamp(0.0, 1.0);
    const w1 = float(1.0).sub(abs(zn.sub(1.0))).clamp(0.0, 1.0);
    const w2 = float(1.0).sub(abs(zn.sub(2.0))).clamp(0.0, 1.0);
    const w3 = zn.sub(2.0).clamp(0.0, 1.0);
    const tint = U.plating.div(U.platingBase).mul(w0).add(U.base.div(U.baseBase).mul(w1))
        .add(U.ivory.div(U.ivoryBase).mul(w2)).add(vec3(1.0, 1.0, 1.0).mul(w3));
    const frame = new THREE.MeshPhysicalNodeMaterial();
    frame.colorNode = base.rgb.mul(tint);
    frame.normalNode = normalMap(texture(src.normalMap, st));
    frame.roughnessNode = orm.g;
    frame.metalnessNode = orm.b;
    frame.aoNode = orm.r;
    frame.name = `${names[0]}_bestiary`;
    const lens = new THREE.MeshPhysicalNodeMaterial();
    lens.colorNode = texture(gl.map, st).rgb.mul(U.glass.div(U.glassBase));
    lens.normalNode = normalMap(texture(gl.normalMap, st));
    lens.roughnessNode = texture(gl.roughnessMap, st).g;
    lens.metalness = 0.0;
    lens.ior = acc.fit.lens.ior;
    if (opts.lens === 'transparent') {
        lens.transparent = true;
        lens.opacity = opts.lensOpacity ?? 0.14;
        lens.depthWrite = false;
    } else {
        lens.transmission = 1.0;
        lens.thickness = acc.fit.lens.thickness;
        lens.attenuationColor = new THREE.Color(0.93, 0.97, 0.95);
        lens.attenuationDistance = 0.03;
    }
    lens.name = `${names[1]}_bestiary`;
    return { frame, lens };
}

function wearGlasses(creature, acc, seat, opts) {
    const sf = seat.userData.fit;
    // a SKINNED clone (its own skeleton: Object3D.clone shares the original's bones, and every wearer poses its own)
    const object = globalThis.cloneModel ? globalThis.cloneModel(acc.scene) : acc.scene.clone(true);
    object.name = `accessory_${acc.name}`;
    const b = acc.base, p = opts.palette || {};
    const U = {
        plating: THREE.uniform(target(p.plating, b.plating, 0xffe4a0)),
        base: THREE.uniform(target(p.base, b.base, 0xd9cfbf)),
        ivory: THREE.uniform(target(p.ivory, b.ivory, 0xe0cfa8)),
        glass: THREE.uniform(target(p.glass, b.glass, 0xf4faf6)),
        platingBase: THREE.uniform(linear(b.plating, 0.7)), baseBase: THREE.uniform(linear(b.base, 0.6)),
        ivoryBase: THREE.uniform(linear(b.ivory, 0.5)), glassBase: THREE.uniform(linear(b.glass, 0.95)),
    };
    const { frame, lens } = glassesMaterials(acc, U, opts);
    object.traverse((o) => {
        if (o.isMesh) {
            o.material = /lens/.test(o.material?.name || '') ? lens : frame;
            o.castShadow = true;
            o.receiveShadow = true;
            o.frustumCulled = false;           // skinned: the rest pose's bounds do not hold the posed temples
        }
    });
    // the creature's up in the seat's frame (the fallback roll's, and the one the forge validated against): from the
    // creature at wear time, unless the caller or the seat gives it
    let up = opts.up ? v3(opts.up) : (sf.up ? v3(sf.up) : null);
    if (!up) {
        creature.group.updateMatrixWorld(true);
        const qs = seat.getWorldQuaternion(new THREE.Quaternion());
        const qg = creature.group.getWorldQuaternion(new THREE.Quaternion());
        up = new THREE.Vector3(0, 1, 0).applyQuaternion(qs.invert().multiply(qg));
    }
    const pose = glassesPose(sf, acc.fit, { up, clearance: opts.clearance ?? 0.0004, gap: opts.gap ?? 0.0003 });
    const bones = {};
    object.traverse((o) => { if (o.isBone && pose.bones[o.name]) bones[o.name] = o; });
    for (const [nm, bp] of Object.entries(pose.bones)) {
        const bone = bones[nm];
        if (!bone) throw new Error(`[Bestiary] wear: the glasses' bone ${nm} is missing`);
        bone.position.copy(bp.position);
        bone.quaternion.setFromRotationMatrix(bp.rotation);
        if (bp.scale != null) bone.scale.setScalar(bp.scale);
    }
    object.userData.placement = pose;
    seat.add(object);
    return {
        object, uniforms: U, bones, pose,
        setPalette(q = {}) {
            for (const k of ['plating', 'base', 'ivory', 'glass']) if (q[k] != null) U[k].value.set(q[k]);
        },
        remove() { seat.remove(object); },
    };
}

// ---------------------------------------------------------------------------------------------------- monocle
// (B10b) A RIGID prop with a CHAIN (forge/props/monocle.py; its frame remix.js's item contract: the origin the lens centre, +Z
// the lens's outer face, +Y up). Worn on an eye socket (opts.socket, else socket_eye_<opts.side ?? 'L'>), fitted by, in
// order: opts.fit; the socket's own fit.monocle (the beetle's rig writes it, work/bestiary/beetle/b10/r01_rig.py: offset and
// rotation in the socket's frame put the lens centre 3 mm (x10) proud of the eye's dome, facing out along its axis, +Y the
// creature's up; radius the lens as worn, so the prop's scale is that over its own lens's, as a hat's follows its seat); the
// prop's own conform record for the creature's species (the octopus's: its glb carries none). The CHAIN (the fit's chain: an
// anchor point and the skin's normal there in a joint's frame, `slack` x the span at wear long) hangs from the cord ring's
// foot (fit.eyelet.attach) to its END, a stud the prop carries, set on the wearer at the anchor; a catenary under the world's
// gravity re-hung before each draw while its ends move (the head carries the monocle, the pronotum the end: the life motion
// turns one against the other), its links instanced from the prop's link mesh, every other one turned a quarter about it
export function monocleChain(p0, p1, L, up, out) {
    // out.length points at equal arc length along a chain of length L hung between p0 and p1 under -up (a unit vector), in
    // any uniformly scaled frame (forge/props/monocle.py catenary is its twin): y = a cosh((x - x0) / a) + c in the vertical
    // plane through both ends, L^2 - v^2 = (2 a sinh(h / 2a))^2, x0 = h / 2 - a atanh(v / L)
    const n = out.length;
    const d = new THREE.Vector3().subVectors(p1, p0);
    const v = d.dot(up);
    const hv = d.clone().addScaledVector(up, -v);
    const h = hv.length();
    if (L <= Math.hypot(h, v) * (1 + 1e-9) || h < 1e-12) {
        for (let i = 0; i < n; i++) out[i].copy(p0).addScaledVector(d, i / (n - 1));
        return out;
    }
    hv.divideScalar(h);
    const k = Math.sqrt(L * L - v * v);
    let lo = h / 1400, hi = 1e4 * h, a = 0;
    for (let it = 0; it < 64; it++) {
        a = Math.sqrt(lo * hi);
        if (2 * a * Math.sinh(h / (2 * a)) > k) lo = a; else hi = a;
    }
    a = Math.sqrt(lo * hi);
    const x0 = 0.5 * h - a * Math.atanh(v / L), c0 = -a * Math.cosh(-x0 / a), s0 = a * Math.sinh(-x0 / a);
    for (let i = 0; i < n; i++) {
        const x = x0 + a * Math.asinh((s0 + L * i / (n - 1)) / a);
        out[i].copy(p0).addScaledVector(hv, x).addScaledVector(up, a * Math.cosh((x - x0) / a) + c0);
    }
    return out;
}

// (B10c) THE CHAIN'S LOD (DESIGN.md: an accessory 0.5-6 k triangles; the prop's link is 140, ~45 of them on the beetle: ~6.3 k). The
// prop's own link is drawn while a link's pitch spans `fine` pixels or more on screen; below that the same links as a coarse wire
// (`coarse.sides` round, `coarse.stations` along: 48 triangles, built from the link's size), and below `tube` pixels one tube along
// the catenary (`tubeGeo`: 288 triangles), both in the plating's own colour (its palette uniform: a link a few pixels long shows no
// texel of its maps). The level is a pure function of the camera (no hysteresis: a --jump frame equals the one reached step by step),
// set by the renderer before it draws the chain (a THREE.LOD's update) from a perspective camera only: a shadow's orthographic camera
// keeps the view's level
export const CHAIN_LOD = { fine: 6.0, tube: 1.8, coarse: { sides: 3, stations: 8 }, tubeGeo: { sides: 6, rings: 24 },
    roughness: 0.22 };

export function chainLinkGeometry(size, { sides = 3, stations = 8 } = {}) {
    // a cable chain's link as a coarse WIRE, the prop's link frame (forge/props/monocle.py _link_piece: the centreline a stadium in
    // XY, long axis X, half circles of radius (W + d) / 2 joined by straights; the wire's radius d / 2): `stations` along the
    // centreline (half on each half circle, its ends included), `sides` round the wire, the normals radial, outward (CCW)
    const hx = 0.5 * (size.L - size.W), Rc = 0.5 * (size.W + size.d), r = 0.5 * size.d, h = stations / 2;
    const pos = [], nrm = [], idx = [];
    for (let i = 0; i < stations; i++) {
        const right = i < h, a = (right ? -0.5 : 0.5) * Math.PI + Math.PI * (i % h) / (h - 1);
        const cx = (right ? hx : -hx) + Rc * Math.cos(a), cy = Rc * Math.sin(a);
        for (let k = 0; k < sides; k++) {
            const f = 2 * Math.PI * k / sides, nx = Math.cos(f) * Math.cos(a), ny = Math.cos(f) * Math.sin(a), nz = Math.sin(f);
            pos.push(cx + r * nx, cy + r * ny, r * nz);
            nrm.push(nx, ny, nz);
        }
    }
    for (let i = 0; i < stations; i++) {
        const j = (i + 1) % stations;
        for (let k = 0; k < sides; k++) {
            const l = (k + 1) % sides;
            idx.push(i * sides + k, j * sides + k, i * sides + l, j * sides + k, j * sides + l, i * sides + l);
        }
    }
    const g = new THREE.BufferGeometry();
    g.setAttribute('position', new THREE.Float32BufferAttribute(pos, 3));
    g.setAttribute('normal', new THREE.Float32BufferAttribute(nrm, 3));
    g.setIndex(idx);
    return g;
}

function wearMonocle(creature, acc, opts) {
    const sockName = opts.socket ?? `socket_eye_${opts.side ?? 'L'}`;
    const sock = creature.sockets?.[sockName];
    if (!sock) throw new Error(`[Bestiary] wear: no ${sockName} on this creature`);
    const species = creature.gltf?.userData?.bestiary?.species;
    const mf = opts.fit ?? sock.userData?.fit?.monocle ?? acc.fit.conform?.[species]?.[sockName];
    if (!mf) {
        throw new Error(`[Bestiary] wear: no monocle fit for ${sockName} (opts.fit, the socket's fit.monocle, the prop's conform `
            + `record for '${species}')`);
    }
    const object = acc.scene.clone(true);
    object.name = `accessory_${acc.name}`;
    const b = acc.base, p = opts.palette || {};
    const U = {
        plating: THREE.uniform(target(p.plating, b.plating, 0xffe4a0)),
        base: THREE.uniform(target(p.base, b.base, 0xd9cfbf)),
        ivory: THREE.uniform(target(p.ivory, b.ivory, 0xe0cfa8)),
        glass: THREE.uniform(target(p.glass, b.glass, 0xf4faf6)),
        platingBase: THREE.uniform(linear(b.plating, 0.7)), baseBase: THREE.uniform(linear(b.base, 0.6)),
        ivoryBase: THREE.uniform(linear(b.ivory, 0.5)), glassBase: THREE.uniform(linear(b.glass, 0.95)),
    };
    const { frame, lens } = glassesMaterials(acc, U, opts, [acc.name, `${acc.name}_lens`]);
    const dress = (root) => root.traverse((o) => {
        if (o.isMesh) {
            o.material = /lens/.test(o.material?.name || '') ? lens : frame;
            o.castShadow = true;
            o.receiveShadow = true;
        }
    });
    dress(object);
    const holder = new THREE.Group();
    holder.name = `holder_${acc.name}`;
    holder.position.fromArray(mf.offset);
    holder.quaternion.fromArray(mf.rotation);
    const s = mf.radius / acc.fit.lens.radius;
    holder.scale.setScalar(s);
    holder.add(object);
    sock.add(holder);
    const handle = {
        object, holder, uniforms: U, fit: mf, scale: s, chain: null, end: null,
        setPalette(q = {}) {
            for (const k of ['plating', 'base', 'ivory', 'glass']) if (q[k] != null) U[k].value.set(q[k]);
        },
        remove() {
            sock.remove(holder);
            handle.end?.parent?.remove(handle.end);
        },
    };
    const cf = mf.chain, bone = cf ? creature.bones?.get(cf.joint) : null, link = acc.parts?.link;
    if (!cf || !bone || !link || opts.chain === false) return handle;
    // the END on the wearer: at the anchor, its +Y the skin's normal there, at the prop's scale
    const end = acc.parts.end ? acc.parts.end.clone(true) : new THREE.Group();
    end.name = `chain_end_${acc.name}`;
    dress(end);
    end.position.fromArray(cf.point);
    end.quaternion.setFromUnitVectors(new THREE.Vector3(0, 1, 0), new THREE.Vector3().fromArray(cf.normal).normalize());
    end.scale.setScalar(s);
    bone.add(end);
    // the CHAIN, in the holder's frame (the prop's units): N links of the prop's pitch over its length (slack x the span now)
    const A = new THREE.Vector3().fromArray(acc.fit.eyelet.attach);
    const Eend = new THREE.Vector3().fromArray(acc.fit.chain.end_attach);
    const pitch = acc.fit.chain.pitch;
    const mInv = new THREE.Matrix4(), vE = new THREE.Vector3(), vUp = new THREE.Vector3();
    const endInHolder = () => {
        holder.updateWorldMatrix(true, false);
        end.updateWorldMatrix(true, false);
        mInv.copy(holder.matrixWorld).invert();
        vE.copy(Eend).applyMatrix4(end.matrixWorld).applyMatrix4(mInv);
        vUp.set(0, 1, 0).transformDirection(mInv);
    };
    endInHolder();
    const Lc = (cf.slack ?? 1.1) * vE.distanceTo(A);
    const N = Math.max(2, Math.round(Lc / pitch));
    const instanced = (geo, mat, nm) => {
        const im = new THREE.InstancedMesh(geo, mat, N);
        im.name = nm;
        im.castShadow = true;
        im.receiveShadow = true;
        im.frustumCulled = false;         // re-hung every frame: bounds from its first instances would not hold
        return im;
    };
    const chain = instanced(link.geometry, frame, `chain_${acc.name}`);
    // (B10c) the LOD's coarse links and tube (CHAIN_LOD), in the plating's colour
    const LOD = { ...CHAIN_LOD, ...(typeof opts.chainLod === 'object' ? opts.chainLod : {}) };
    const plain = new THREE.MeshPhysicalNodeMaterial();
    plain.colorNode = U.plating;
    plain.metalness = 1.0;
    plain.roughness = LOD.roughness;
    plain.name = `${acc.name}_chain_plain_bestiary`;
    const coarse = instanced(chainLinkGeometry(acc.fit.chain.link_size, LOD.coarse), plain, `chain_${acc.name}_coarse`);
    const TS = LOD.tubeGeo.sides, TR = LOD.tubeGeo.rings;
    const ls = acc.fit.chain.link_size;
    // the tube's radius: half the chain's mean width as drawn (its links' metal area seen face on and edge on, a pitch's worth,
    // over the pitch)
    const tubeR = 0.25 * ((Math.PI * (ls.W + ls.d) + 2 * (ls.L - ls.W)) * ls.d + (ls.L + 2 * ls.d) * ls.d) / ls.L;
    const tubeGeo = new THREE.BufferGeometry();
    tubeGeo.setAttribute('position', new THREE.Float32BufferAttribute(new Float32Array((TR + 1) * TS * 3), 3));
    tubeGeo.setAttribute('normal', new THREE.Float32BufferAttribute(new Float32Array((TR + 1) * TS * 3), 3));
    const tix = [];
    for (let i = 0; i < TR; i++) {
        for (let k = 0; k < TS; k++) {
            const l = (k + 1) % TS;      // (CCW from outside: the ring runs Y -> Z about the tangent X, Z = X x Y)
            tix.push(i * TS + k, i * TS + l, (i + 1) * TS + k, (i + 1) * TS + k, i * TS + l, (i + 1) * TS + l);
        }
    }
    tubeGeo.setIndex(tix);
    const tube = new THREE.Mesh(tubeGeo, plain);
    tube.name = `chain_${acc.name}_tube`;
    tube.castShadow = true;
    tube.receiveShadow = true;
    tube.frustumCulled = false;
    const lod = new THREE.LOD();
    lod.name = `chain_lod_${acc.name}`;
    lod.add(chain, coarse, tube);
    holder.add(lod);
    const reps = [chain, coarse, tube];
    const lv = { level: 0, px: Infinity, H: 1080 };
    const camW = new THREE.Vector3(), aW = new THREE.Vector3(), eW = new THREE.Vector3(), sW = new THREE.Vector3();
    const setLevel = (k) => {
        lv.level = k;
        reps.forEach((o, i) => { o.visible = i === k; });
    };
    setLevel(0);
    lod.update = (camera) => {
        // the link's pitch on screen: its world length over the camera's distance to the chain's middle, in the drawing buffer's
        // pixels (from the last frame's renderer; 1080 before the first)
        if (opts.chainLod === false || !camera?.isPerspectiveCamera) return;
        aW.copy(A).applyMatrix4(holder.matrixWorld);
        eW.copy(Eend).applyMatrix4(end.matrixWorld);
        aW.add(eW).multiplyScalar(0.5);
        const dist = camW.setFromMatrixPosition(camera.matrixWorld).distanceTo(aW);
        const pw = pitch * sW.setFromMatrixScale(holder.matrixWorld).x;
        lv.px = pw * lv.H * (camera.zoom ?? 1) / (2 * Math.max(dist, 1e-9) * Math.tan(camera.fov * Math.PI / 360));
        setLevel(lv.px >= LOD.fine ? 0 : lv.px >= LOD.tube ? 1 : 2);
    };
    const P = Array.from({ length: N + 1 }, () => new THREE.Vector3());
    const PT = Array.from({ length: TR + 1 }, () => new THREE.Vector3());
    const last = new THREE.Vector3(Infinity, 0, 0), lastUp = new THREE.Vector3();
    const X = new THREE.Vector3(), Y = new THREE.Vector3(), Z = new THREE.Vector3(), C = new THREE.Vector3();
    const M = new THREE.Matrix4(), bufH = new THREE.Vector2();
    let ver = 0;
    // the catenary re-hung while its ends move (a pose version), each drawn level brought to it when it is drawn
    const hang = (rep, renderer) => {
        if (renderer?.getDrawingBufferSize) lv.H = renderer.getDrawingBufferSize(bufH).y || lv.H;
        endInHolder();
        if (!(vE.distanceToSquared(last) < 1e-18 && vUp.distanceToSquared(lastUp) < 1e-18)) {
            last.copy(vE);
            lastUp.copy(vUp);
            monocleChain(A, vE, Lc, vUp, P);
            ver++;
        }
        if (rep.userData.ver === ver) return;
        rep.userData.ver = ver;
        if (rep === tube) {
            monocleChain(A, vE, Lc, vUp, PT);
            const pa = tubeGeo.attributes.position, na = tubeGeo.attributes.normal;
            for (let i = 0; i <= TR; i++) {
                X.subVectors(PT[Math.min(i + 1, TR)], PT[Math.max(i - 1, 0)]).normalize();
                Y.crossVectors(vUp, X);
                if (Y.lengthSq() < 1e-12) Y.set(1, 0, 0).cross(X);
                Y.normalize();
                Z.crossVectors(X, Y);
                for (let k = 0; k < TS; k++) {
                    const f = 2 * Math.PI * k / TS, c = Math.cos(f), s = Math.sin(f);
                    C.copy(Y).multiplyScalar(c).addScaledVector(Z, s);
                    na.setXYZ(i * TS + k, C.x, C.y, C.z);
                    pa.setXYZ(i * TS + k, PT[i].x + tubeR * C.x, PT[i].y + tubeR * C.y, PT[i].z + tubeR * C.z);
                }
            }
            pa.needsUpdate = true;
            na.needsUpdate = true;
            return;
        }
        for (let i = 0; i < N; i++) {
            X.subVectors(P[i + 1], P[i]);
            const seg = X.length();
            X.divideScalar(seg || 1);
            // the link's width across the chain: level for the even links, the odd ones a quarter turned about it
            Y.crossVectors(vUp, X);
            if (Y.lengthSq() < 1e-12) Y.set(1, 0, 0).cross(X);
            Y.normalize();
            if (i % 2) Y.cross(X).negate();
            Z.crossVectors(X, Y);
            C.addVectors(P[i], P[i + 1]).multiplyScalar(0.5);
            M.makeBasis(X.multiplyScalar(seg / pitch), Y, Z).setPosition(C);
            rep.setMatrixAt(i, M);
        }
        rep.instanceMatrix.needsUpdate = true;
    };
    for (const rep of reps) {
        hang(rep);
        rep.onBeforeRender = (renderer) => hang(rep, renderer);
    }
    const tris = (g) => (g.index ? g.index.count : g.attributes.position.count) / 3;
    Object.assign(handle, { chain, end, links: N, length: Lc, lod, coarse, tube,
        // the level drawn last (0 the prop's links, 1 the coarse links, 2 the tube), the link's pitch in pixels, each level's triangles
        level: () => lv.level, pixels: () => lv.px,
        triangles: { fine: N * tris(link.geometry), coarse: N * tris(coarse.geometry), tube: tris(tubeGeo) } });
    return handle;
}
