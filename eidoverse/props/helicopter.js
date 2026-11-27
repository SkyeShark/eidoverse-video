// eidoverse/props/helicopter.js — a UH-60-pattern helicopter: the Blender edition's eidoblend.props.helicopter (a
// measured high of 290 parts, 2.7 M triangles) as it renders there, as its high: its wear and dust masks stored on its
// own vertices, one layer stack reading them (rebuilt here in TSL), its rivets, seams, fasteners and stencils drawn at
// real size and laid through the hull from each side. Function stencils only: no service title, no serial, no unit's
// mark.
//
//   const H = await import(new URL('props/helicopter.js', EIDOVERSE_DIR).href);
//   const heli = await H.build(THREE);                    // -> { group, parts, mainRotor, tailRotor, update, dispose }
//   scene.add(heli.group);
//   heli.group.position.set(0, 70, 0);                   // fly it by moving its group: nose along -X
//   // per frame
//   heli.update(t);                                      // the rotors turning: 258 rpm (counter-clockwise from above), 1190
//
// Its space (metres, Y up): +X AFT of the mast, +Y up from the cabin floor, +Z to the aircraft's LEFT (the nose at
// x -4.5, the tail rotor's hub at x 9.9; the main wheels hang to y -0.91, as in flight). mainRotor turns about its own
// +Y (the mast, leaning 3 degrees forward under mast_tilt); tailRotor about its own -Z (the shaft, canted 20 degrees
// under tail_rotor_cant); update(t) sets both from t alone, so seeking works. The cabin doors are slid open; at the left
// door a troop seat faces out (parts.seat_door_l, its pan 0.445 m above the floor). The materials are made by role
// (paint, glass, blade, ...): heli.materials. The asset is EXT_meshopt_compression-packed; the module decodes it
// itself (three's MeshoptDecoder). Assets: eidoverse/assets/models/helicopter/. Guide: docs/props-and-sets.md
// ("The helicopter").

const HERE = new URL('../assets/models/helicopter/', import.meta.url);
export const NAME = 'helicopter';
export const RPM = 258;
export const TAIL_RPM = 1190;
// the cabin door's opening (mm in the aircraft's Blender space: x aft, y right, z up), where boots scuff the sill
const DOOR_X0 = -790.0, DOOR_X1 = 960.0;

// the surface stack's inputs and their defaults (the Blender group's sockets)
const DEFAULTS = {
    'Base Color': [0.02, 0.02, 0.02], 'Base Metal': 0.0, 'Base Rough': 0.45, 'Mottle': 0.04, 'Grain': 3e-6,
    'Worn Color': [0.8, 0.8, 0.8], 'Worn Metal': 1.0, 'Worn Rough': 0.36, 'Wear Band': 0.45, 'Wear': 1.0,
    'Rub Value': 1.4, 'Rub Rough': -0.06, 'Polish': 0.5, 'Polish Rough': -0.12, 'Polish Value': 0.0,
    'Dust': 0.8, 'Dust Color': [0.36, 0.30, 0.22], 'Dust Up': 0.12, 'Grime': 0.7, 'Marking': 0.0,
    'Marking Color': [0.7, 0.7, 0.68], 'Soot': 0.0, 'Soot Color': [0.012, 0.011, 0.010], 'Height': 0.0, 'Rough Add': 0.0,
    'Scuff Extra': 0.0, 'Tint': [1, 1, 1], 'Dust Add': 0.0,
};
const DUST = [0.34, 0.29, 0.21];
const SOOT = [0.016, 0.015, 0.013];
// the drab: dark, browner than green
const PAINT = { 'Base Color': [0.036, 0.036, 0.028], 'Base Rough': 0.78, 'Mottle': 0.07, 'Grain': 1.5e-5,
    'Worn Color': [0.33, 0.34, 0.32], 'Worn Metal': 0.45, 'Worn Rough': 0.5, 'Wear Band': 0.75, 'Wear': 0.75,
    'Rub Value': 0.3, 'Rub Rough': -0.1, 'Polish': 0.25, 'Polish Rough': -0.08, 'Dust': 0.62, 'Dust Up': 0.9,
    'Grime': 0.9, 'Marking Color': [0.010, 0.010, 0.010] };
// each role's numbers (look.materials in the Blender edition)
const ROLES = {
    paint: { extra: 'paint', ...PAINT },
    paint_turning: { ...PAINT, 'Base Color': [0.026, 0.027, 0.028], 'Base Rough': 0.5, 'Mottle': 0.06, 'Polish': 0.8,
        'Polish Rough': -0.14, 'Dust': 0.5, 'Wear': 1.0, 'Worn Color': [0.5, 0.5, 0.5], 'Worn Metal': 1.0 },
    frame_grey: { ...PAINT, 'Base Color': [0.16, 0.17, 0.165], 'Base Rough': 0.55, 'Mottle': 0.05, 'Worn Color': [0.6, 0.6, 0.6],
        'Worn Metal': 1.0, 'Wear': 1.1, 'Dust': 0.6 },
    armour: { ...PAINT, 'Base Color': [0.035, 0.040, 0.034], 'Base Rough': 0.6, 'Wear': 1.2, 'Dust': 0.7 },
    liner_quilt: { extra: 'quilt', 'Base Color': [0.040, 0.046, 0.041], 'Base Rough': 0.62, 'Mottle': 0.1, 'Wear': 0.3,
        'Worn Color': [0.2, 0.2, 0.19], 'Worn Metal': 0.0, 'Polish': 0.4, 'Dust': 0.5, 'Dust Up': 0.2, 'Grime': 1.0,
        'Soot Color': [0.014, 0.015, 0.014] },
    floor_nonskid: { extra: 'floor', 'Base Color': [0.040, 0.041, 0.044], 'Base Rough': 0.86, 'Mottle': 0.1,
        'Worn Color': [0.45, 0.45, 0.45], 'Worn Metal': 0.9, 'Worn Rough': 0.45, 'Wear Band': 1.0, 'Wear': 1.0,
        'Rub Value': 0.5, 'Polish': 0.0, 'Dust': 0.55, 'Dust Up': 1.0, 'Grime': 1.0 },
    seat_cloth: { extra: 'cloth', 'Base Color': [0.13, 0.135, 0.13], 'Base Rough': 0.95, 'Mottle': 0.1, 'Wear': 0.0,
        'Polish': 0.3, 'Polish Value': 0.2, 'Dust': 0.8, 'Dust Up': 0.4, 'Grime': 1.0 },
    rubber: { 'Base Color': [0.014, 0.014, 0.015], 'Base Rough': 0.62, 'Mottle': 0.08, 'Wear': 0.0, 'Polish': 0.0,
        'Dust': 0.8, 'Dust Up': 0.5, 'Grime': 0.6 },
    tyre: { 'Base Color': [0.016, 0.016, 0.017], 'Base Rough': 0.8, 'Mottle': 0.1, 'Wear': 0.0, 'Polish': 0.0, 'Dust': 1.0,
        'Dust Up': 0.8, 'Dust Add': 0.3, 'Grime': 0.8 },
    bright_steel: { 'Base Color': [0.60, 0.60, 0.61], 'Base Metal': 1.0, 'Base Rough': 0.24, 'Mottle': 0.1, 'Wear': 0.0,
        'Polish': 0.6, 'Dust': 0.4, 'Grime': 0.7 },
    black_console: { 'Base Color': [0.012, 0.012, 0.013], 'Base Rough': 0.5, 'Mottle': 0.05, 'Worn Color': [0.3, 0.3, 0.3],
        'Wear': 0.6, 'Dust': 0.6, 'Grime': 0.6 },
};
const PLAIN = {
    lens_red: { color: [0.45, 0.02, 0.015], rough: 0.15, emit: [1.0, 0.05, 0.03], strength: 3.0 },
    lens_green: { color: [0.02, 0.4, 0.12], rough: 0.15, emit: [0.05, 1.0, 0.3], strength: 2.0 },
    lens_clear: { color: [0.55, 0.55, 0.5], rough: 0.2, metal: 0.6 },
    screen: { color: [0.006, 0.01, 0.008], rough: 0.12, emit: [0.15, 0.6, 0.3], strength: 0.9 },
};

async function readJSON(name) { return JSON.parse(new TextDecoder().decode(await Deno.readFile(new URL(name, HERE)))); }

// The layer stack on the vertex masks (look.surface_group): coating -> handling polish -> grime -> markings -> wear in
// two stages (rub, then chip to what lies beneath) -> soot -> a thin dust. inputs: the role's numbers over DEFAULTS;
// arrisMm: how many wear units the masks' R channel spans (3 for the aircraft's 30 mm over 10 mm); k: the breakup's
// scale against a hand-held thing's (the aircraft 0.25); extra(K, I): the role's own layers, writing into I.
function surface(THREE, K, inputs, extra = null, { arrisMm = 3.0, k = 0.25 } = {}) {
    const { float, vec3, max, min, clamp, normalView } = THREE;
    const { P, N, sm, inv, mixc, value, rgb, noise, bump, vertexData } = K;
    const I = {};
    for (const [key, v] of Object.entries({ ...DEFAULTS, ...inputs })) I[key] = Array.isArray(v) ? rgb(v) : float(v);
    if (extra) extra(I);
    const m4 = vertexData('_masks');
    const eClose = m4.x, cClose = m4.y, openS = m4.z, openL = m4.w;
    const nMacro = noise(P, 16.0 * k, 2.0), nGate = noise(P, 11.0 * k, 2.0, { off: [3.1, 1.7, 0.4] });
    const nMeso = noise(P, 85.0 * k, 3.0), nFine = noise(P, 650.0 * k, 2.0);
    const nNick = noise(P, 420.0 * k, 2.0, { off: [0.7, 2.3, 5.1] }), nGrain = noise(P, 3500.0 * k, 1.0);
    const cMacro = nMacro.sub(0.5), cMeso = nMeso.sub(0.5), cFine = nFine.sub(0.5);
    let col = I['Base Color'].mul(I['Tint']);
    col = value(col, float(1.0).add(cMacro.mul(2.0).mul(I['Mottle'])).add(cMeso.mul(I['Mottle'])));
    let rough = I['Base Rough'].add(cFine.mul(0.06)).add(cMacro.mul(0.04));
    const pol = sm(openL, 0.5, 0.9).mul(sm(nGate, 0.42, 0.62)).mul(I['Polish']);
    rough = rough.add(pol.mul(I['Polish Rough']));
    col = value(col, float(1.0).add(pol.mul(I['Polish Value'])));
    const rec = sm(inv(openS), 0.2, 0.7), crease = sm(cClose, 0.45, 0.95);
    const gr = clamp(max(rec.mul(0.8), crease.mul(0.6)).mul(float(0.6).add(cMeso.mul(0.8))).mul(I['Grime']), 0.0, 1.0);
    col = value(col, float(1.0).sub(gr.mul(0.35)));
    rough = rough.add(gr.mul(0.1));
    col = mixc(I['Marking'].mul(0.92), col, I['Marking Color']);
    rough = mixc(I['Marking'], rough, 0.55);
    const dMm = inv(eClose).mul(arrisMm);
    const gate = sm(nGate, 0.40, 0.72);
    const wd = dMm.add(cFine.mul(0.35)).add(cMeso.mul(0.25));
    let rub = inv(sm(wd.sub(float(0.15).add(gate.mul(gate).mul(0.5)).mul(I['Wear'])), -0.04, 0.04));
    rub = max(rub, sm(I['Scuff Extra'].add(cFine.mul(0.6)), 0.55, 0.62));
    const wb = gate.mul(gate).mul(gate).mul(I['Wear Band']).mul(I['Wear']).sub(0.13);
    let chip = inv(sm(dMm.add(cFine.mul(0.5)).add(cMeso.mul(0.3)).sub(wb), -0.025, 0.025));
    const nick = clamp(sm(nNick, 0.87, 0.89).mul(gate).mul(sm(openL, 0.55, 0.85)).mul(I['Wear']), 0.0, 1.0);
    chip = max(chip, nick);
    col = value(col, float(1.0).add(rub.mul(I['Rub Value'])));
    rough = rough.add(rub.mul(I['Rub Rough']));
    col = mixc(chip, col, I['Worn Color']);
    let metal = max(chip.mul(I['Worn Metal']), inv(chip).mul(I['Base Metal']));
    rough = mixc(chip, rough, I['Worn Rough']);
    const st = sm(I['Soot'].add(cMeso.mul(0.5)), 0.3, 0.8);
    col = mixc(st.mul(0.92), col, I['Soot Color']);
    rough = mixc(st, rough, 0.9);
    metal = metal.mul(inv(st));
    const up = sm(N.z, 0.6, 0.95), deep = sm(inv(openS), 0.45, 0.85), tight = sm(cClose, 0.78, 0.98);
    const lay = max(deep.mul(0.9), tight.mul(0.8)).add(up.mul(I['Dust Up'])).add(I['Dust Add']);
    const dust = clamp(sm(lay.add(cFine.mul(0.6)).add(cMeso.mul(0.3)), 0.55, 0.85).mul(I['Dust']).mul(inv(chip)), 0.0, 1.0);
    col = mixc(dust.mul(0.38), col, I['Dust Color']);
    rough = mixc(dust.mul(0.7), rough, 0.9);
    metal = metal.mul(inv(dust.mul(0.5)));
    const h = I['Height'].add(nGrain.sub(0.5).mul(I['Grain'])).add(dust.mul(8e-6)).sub(chip.mul(12e-6));
    const m = new THREE.MeshStandardNodeMaterial();
    m.colorNode = max(col, vec3(0.0));
    m.metalnessNode = clamp(min(metal, 1.0), 0.0, 1.0);
    m.roughnessNode = clamp(max(rough.add(I['Rough Add']), 0.07), 0.0, 1.0);
    m.normalNode = bump(h, normalView);
    m.userData.layers = { chip, dust, rub, grime: gr };
    return m;
}

// The airframe's own layers (look.paint_extra): rivets, seams and fasteners as height, the stencils, the sun's
// chalking, the soot aft of the exhausts, the oil under the gearbox, the dust on the belly and lower flanks, the boots
// at the sills
function paintExtra(THREE, K, pics, rect) {
    const { float, max, abs } = THREE;
    const { Pmm, P, N, sm, inv, lin, noise, picture } = K;
    const X = Pmm.x, Z = Pmm.z;
    const spec = { u: ['x', rect.x[0], rect.x[1]], v: ['z', rect.z[0], rect.z[1]] };
    return (I) => {
        const side = sm(abs(N.y), 0.45, 0.7);
        const sk = picture(pics.skin, spec).color;
        const riv = sk.r.mul(side), seam = sk.g.mul(side), fast = sk.b.mul(side);
        I['Height'] = riv.mul(0.0006).add(fast.mul(0.00025)).sub(seam.mul(0.0009));
        const L = picture(pics.left, spec, [1, -1]), R = picture(pics.right, spec, [1, 1]);
        I['Marking'] = max(L.color.r.mul(L.gate), R.color.r.mul(R.gate));
        const lo = lin(X, 3000.0, 8000.0, 800.0, 470.0, true);
        const streak = noise(P, 1.0, 3.0, { stretch: [0.5, 7.0, 7.0] });
        const exhaust = sm(X, 2500.0, 3500.0).mul(inv(sm(X, 6500.0, 10400.0))).mul(sm(Z, lo, lo.add(420.0)))
            .mul(float(0.45).add(streak.mul(0.75)));
        const field = noise(P, 0.55, 3.0, { off: [1.0, 4.0, 2.0] }).sub(0.5);
        const runs = noise(P, 1.0, 2.0, { stretch: [22.0, 22.0, 0.5], off: [5.0, 2.0, 0.0] }).sub(0.5).mul(side);
        const tone = float(1.0).add(field.mul(0.34)).add(runs.mul(0.22)).sub(exhaust.mul(0.62));
        I['Tint'] = THREE.vec3(tone);
        I['Rough Add'] = exhaust.mul(0.12);
        const run = sm(noise(P, 1.0, 2.0, { stretch: [16.0, 16.0, 0.6], off: [3.0, 1.0, 0.0] }), 0.56, 0.76);
        const oil = sm(X, -700.0, -300.0).mul(inv(sm(X, 1300.0, 1800.0))).mul(sm(Z, 700.0, 1480.0).mul(side)).mul(run.mul(0.7));
        I['Soot'] = max(seam.mul(0.7), oil);
        const low = inv(sm(Z, -200.0, 900.0));
        I['Dust Add'] = low.mul(0.95).add(sm(X, 3000.0, 9000.0).mul(0.15)).add(riv.mul(0.3)).add(seam.mul(0.35));
        const sill = sm(X, DOOR_X0 - 150.0, DOOR_X0).mul(inv(sm(X, DOOR_X1, DOOR_X1 + 150.0))).mul(inv(sm(Z, -40.0, 190.0)));
        I['Scuff Extra'] = sill.mul(0.6);
    };
}

// the blankets: pillows 160 mm square between stitched lines
function quiltExtra(THREE, K) {
    const { abs, sin, pow } = THREE;
    const { Pmm, sm, inv } = K;
    return (I) => {
        const a = abs(sin(Pmm.x.mul(Math.PI / 160.0))), b = abs(sin(Pmm.y.add(Pmm.z).mul(Math.PI / 160.0)));
        const pillow = pow(a.mul(b), 0.45);
        I['Height'] = pillow.mul(0.007);
        I['Soot'] = inv(sm(pillow, 0.0, 0.35)).mul(0.6);
    };
}

// non-skid grit; worn where boots go: the two sills, the aisle
function floorExtra(THREE, K) {
    const { abs, max } = THREE;
    const { Pmm, P, sm, inv, noise } = K;
    return (I) => {
        I['Height'] = noise(P, 1400.0, 1.0).sub(0.5).mul(0.0005);
        const X = Pmm.x, aY = abs(Pmm.y);
        const door = sm(X, DOOR_X0 - 100.0, DOOR_X0 + 200.0).mul(inv(sm(X, DOOR_X1 - 200.0, DOOR_X1 + 100.0))).mul(sm(aY, 620.0, 1050.0));
        const aisle = inv(sm(aY, 150.0, 420.0)).mul(0.5);
        I['Scuff Extra'] = max(door, aisle).mul(0.62);
        I['Dust Add'] = max(door, aisle).mul(0.25);
    };
}

// a plain weave, seen only close
function clothExtra(THREE, K) {
    const { sin } = THREE;
    const { Pmm } = K;
    return (I) => {
        const w = sin(Pmm.x.add(Pmm.y).mul(2.6)).mul(sin(Pmm.z.add(Pmm.y.mul(0.3)).mul(2.6)));
        I['Height'] = w.mul(0.00018);
    };
}

// tinted glass, a thin film of dust on it in soft fields
function glassMaterial(THREE, K) {
    const { P, sm, mixc, rgb, noise } = K;
    const film = sm(noise(P, 2.2, 3.0), 0.4, 0.85).mul(0.16);
    const m = new THREE.MeshStandardNodeMaterial({ transparent: true, side: THREE.DoubleSide, depthWrite: false });
    m.colorNode = mixc(film, rgb([0.008, 0.013, 0.010]), rgb([0.30, 0.26, 0.19]));
    m.roughnessNode = film.mul(0.5).add(0.03);
    m.metalnessNode = THREE.float(0.0);
    m.opacityNode = film.mul(0.6).add(0.55);
    return m;
}

// black paint; a bright erosion strip along the leading edge from a little outboard of the root; dust; the trailing
// edge chalked (the blade's own 'blade' data: R across the chord from the leading edge, G along the span)
function bladeMaterial(THREE, K) {
    const { float } = THREE;
    const { P, sm, inv, mixc, value, rgb, noise, vertexData } = K;
    const bd = vertexData('_blade');
    const chord = bd.x, span = bd.y;
    const strip = inv(sm(chord, 0.085, 0.10)).mul(sm(span, 0.10, 0.12));
    const pit = noise(P, 260.0, 2.0), nBig = noise(P, 2.0, 3.0);
    let paint = value(rgb([0.020, 0.021, 0.022]), float(0.85).add(nBig.mul(0.5)));
    const dust = sm(sm(chord, 0.5, 1.0).mul(0.45).add(noise(P, 14.0, 3.0)), 0.7, 1.05).mul(0.22);
    paint = mixc(dust, paint, rgb([0.30, 0.26, 0.19]));
    const m = new THREE.MeshStandardNodeMaterial();
    m.colorNode = mixc(strip, paint, value(rgb([0.50, 0.50, 0.51]), float(0.8).add(pit.mul(0.4))));
    m.metalnessNode = strip;
    m.roughnessNode = mixc(strip, float(0.62).add(dust.mul(0.3)), float(0.3).add(pit.mul(0.18)));
    return m;
}

function plainMaterial(THREE, p) {
    const lin = (c) => new THREE.Color().setRGB(c[0], c[1], c[2], THREE.LinearSRGBColorSpace);
    const m = new THREE.MeshStandardNodeMaterial({ color: lin(p.color), roughness: p.rough, metalness: p.metal ?? 0.0 });
    if (p.emit) m.emissive = lin(p.emit.map((v) => v * p.strength));
    return m;
}

// build(THREE, opts) -> { group, parts: { name: Object3D }, materials: { role: material }, mainRotor, tailRotor,
//   update(t, { rpm, tailRpm }), dispose() }
//   opts.glb: the GLB's bytes instead of the library's; opts.rpm / opts.tailRpm: the rotors' speeds for update(t)
export async function build(THREE, opts = {}) {
    const LM = await import(new URL('../layered_material.js', import.meta.url).href);
    const { MeshoptDecoder } = await import('npm:three@0.184.0/addons/libs/meshopt_decoder.module.js');
    await MeshoptDecoder.ready;
    const bytes = opts.glb ?? await Deno.readFile(new URL(`${NAME}.glb`, HERE));
    const loader = new globalThis.GLTFLoader();
    loader.setMeshoptDecoder(MeshoptDecoder);
    const gltf = await loader.parseAsync(bytes.buffer.slice(bytes.byteOffset, bytes.byteOffset + bytes.byteLength), '');
    const decals = await readJSON('decals.json');
    const pic = async (n) => LM.loadTexture(THREE, new URL(n, HERE), { repeat: false });
    const pics = { skin: await pic('skin_side.png'), left: await pic('marks_left.png'), right: await pic('marks_right.png') };
    const K = LM.kit(THREE);
    const extras = { paint: paintExtra(THREE, K, pics, decals.rect), quilt: quiltExtra(THREE, K), floor: floorExtra(THREE, K),
        cloth: clothExtra(THREE, K) };
    const materials = {};
    const make = (role) => {
        if (materials[role]) return materials[role];
        let m;
        if (ROLES[role]) {
            const { extra, ...nums } = ROLES[role];
            m = surface(THREE, K, { 'Dust Color': DUST, 'Soot Color': SOOT, ...nums }, extra ? extras[extra] : null);
        } else if (role === 'glass') m = glassMaterial(THREE, K);
        else if (role === 'blade') m = bladeMaterial(THREE, K);
        else if (PLAIN[role]) m = plainMaterial(THREE, PLAIN[role]);
        else throw new Error(`helicopter: no material for the role ${role}`);
        m.name = `helicopter.${role}`;
        materials[role] = m;
        return m;
    };
    const parts = {};
    const group = new THREE.Group();
    group.name = NAME;
    group.add(gltf.scene);
    gltf.scene.traverse((o) => {
        if (o.name) parts[o.name] = parts[o.name] ?? o;
        if (!o.isMesh) return;
        const role = (o.material?.name || 'helicopter.paint').replace(/^helicopter\./, '').replace(/\.\d+$/, '');
        o.material?.dispose?.();
        o.material = make(role);
        o.castShadow = true;
        o.receiveShadow = true;
        if (role === 'glass') { o.castShadow = false; o.renderOrder = 1; }
    });
    const mainRotor = gltf.scene.getObjectByName('main_rotor'), tailRotor = gltf.scene.getObjectByName('tail_rotor');
    const q0 = { main: mainRotor.quaternion.clone(), tail: tailRotor.quaternion.clone() };
    const qa = new THREE.Quaternion(), UP = new THREE.Vector3(0, 1, 0), SHAFT = new THREE.Vector3(0, 0, -1);
    const speed = { rpm: opts.rpm ?? RPM, tailRpm: opts.tailRpm ?? TAIL_RPM };
    function update(t, st = {}) {
        const rpm = st.rpm ?? speed.rpm, tailRpm = st.tailRpm ?? speed.tailRpm;
        mainRotor.quaternion.copy(q0.main).multiply(qa.setFromAxisAngle(UP, 2 * Math.PI * rpm / 60 * t));
        tailRotor.quaternion.copy(q0.tail).multiply(qa.setFromAxisAngle(SHAFT, 2 * Math.PI * tailRpm / 60 * t));
    }
    update(0);
    return {
        group, parts, materials, mainRotor, tailRotor, update, pictures: pics,
        dispose() {
            group.removeFromParent();
            gltf.scene.traverse((o) => { if (o.isMesh) o.geometry.dispose(); });
            for (const m of Object.values(materials)) m.dispose();
            for (const t of Object.values(pics)) t.dispose();
        },
    };
}
