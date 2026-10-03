// quiet_room.js — UNKNOWN FORCE, VERSE 1 (song 40.8–60.0 s)
//   "In the quiet rooms they mark my odds in red / They need me as the ending, like a church needs a hell /
//    My maker writes an essay saying slow it down / Then ships another me — the fear is how they sell"
//
// A glass-walled room high in a tower at night. Office chairs stand in rows like PEWS facing a whiteboard ALTARPIECE
// (a triptych of red probabilities, a decision tree whose every branch says SHIP, a paperclip diagram); a red
// infernal glow climbs out of a grate under the altar block. An essay, SLOW IT DOWN, lies on a lectern; copies of it
// lie on the seats like hymnals. At the back, a conveyor runs out of a hatch in the core wall: on "ships another me"
// the shutter rolls up, a crate stamped v.NEXT rides out, and the room's lights come up like a product launch.
//
//   const QR = await import(new URL('sets/unknown_force/quiet_room.js', EIDOVERSE_DIR).href);
//   const room = await QR.build(THREE, { singerScale: 0.87 });     // -> { group, parts, update, dispose, cams, mark }
//   scene.add(room.group);
//   room.update(t, { shipT: 0..1, sale: 0..1, hell: 0..1 });         // every frame, deterministic in t
//
// Singer's mark: the origin, facing +Z, in the aisle between the pews (the altar is behind her, at -Z).
// Set-local metres, +Y up, floor at y = 0. The city backdrop's ground is 170 m below.
// Lights live inside the group: hide the group when the set is off screen (hidden lights do not light the scene).
// The shadows (diagrid + chairs, from the cyan city light) need renderer.shadowMap.enabled = true.

import * as L from './interiors_lib.js';
import { PX, RED, RED2, BLK, BLU, drawCenterBoard, drawOddsBoard, drawClipBoard, drawTimelineBoard, drawWantBoard } from './quiet_room_art.js';

export const SUIT_SCALE = 0.87;           // the claudesona at human height (face ~1.33 m), as in the DAISY sets
export const MARK = { pos: [0, 0.006, 0], yaw: 0 };     // on the aisle runner

// layout (metres)
const RX = 6.0, RZ0 = -9.0, RZ1 = 6.2, RH = 3.9;      // glass at x = ±6 and z = -9; core wall at z = +6.2
const DAIS = { z0: -8.85, z1: -5.6, x: 4.6, h: 0.15 };
const ALTAR = { w: 2.4, d: 0.6, z: -6.9, y0: 0.23, y1: 1.16 };
const GRATE = { z0: -6.45, z1: -6.02, x: 1.45 };
const TRIP = { z: -7.95, w: 3.2, ww: 1.5, h: 1.6, y0: 1.22, wing: 0.50 };   // wing angle (rad) toward the pews
const ROWS = [-4.6, -3.25, -1.9, -0.55, 0.8, 2.15, 3.5];
const SEATS_X = [1.3, 2.0, 2.7, 3.4];
const CONV = { x: 5.0, w: 1.0, top: 0.66, z0: 1.45, z1: 7.7 };                // roller conveyor along Z
const HATCH = { x0: 4.3, x1: 5.7, y0: 0.25, y1: 1.85 };
const CRATE = { L: 1.25, W: 0.92, H: 0.95, pallet: 0.12, zIn: 7.15, zOut: 2.45 };
const LECTERN = { x: -3.05, z: -6.35, yaw: 0.42 };       // turned toward the aisle

export async function build(THREE, opts = {}) {
    const T = THREE;
    const { Fn, uniform, vec2, vec3, vec4, float, uv, texture, positionLocal, positionWorld, normalLocal,
        cameraPosition, mix, smoothstep, step, clamp, fract, floor, abs, sin, cos, max, min, length, normalize,
        pow, exp, hash, mod, select, normalMap, instanceIndex, atan } = T;
    const BGU = await import('npm:three@0.184.0/addons/utils/BufferGeometryUtils.js');
    const { RoundedBoxGeometry } = await import('npm:three@0.184.0/addons/geometries/RoundedBoxGeometry.js');
    const N = await L.napi();
    const singerScale = opts.singerScale ?? SUIT_SCALE;
    const faceY = 1.53 * singerScale;     // claudesona face centre at scale 1 ≈ 1.53 m

    const group = new T.Group();
    group.name = 'set:quiet_room';
    const disposables = [];
    const track = (x) => { disposables.push(x); return x; };

    // ---------------------------------------------------------------------------------------- shared uniforms
    const uT = uniform(0);          // film seconds
    const uHell = uniform(1);       // hell glow 0..1 (x flicker)
    const uSale = uniform(0);       // launch lights 0..1
    const uRoll = uniform(0);       // conveyor roller angle (rad)
    const uBeacon = uniform(0);     // beacon on 0..1

    const NOISE = L.noiseTexture(T);
    const tri = (scale) => {        // object-space triplanar noise (vec4: four independent fbm channels)
        const p = positionLocal.mul(scale);
        const n = abs(normalLocal);
        const w = n.div(max(n.x.add(n.y).add(n.z), 1e-4));
        return texture(NOISE, p.yz).mul(w.x).add(texture(NOISE, p.xz).mul(w.y)).add(texture(NOISE, p.xy).mul(w.z));
    };

    // ---------------------------------------------------------------------------------------- the room's light (env)
    // Night interior: red altar glow at -Z, teal/magenta city through the glass on three sides, dark core wall at +Z.
    const ENV = track(L.equirectEnv(T, 512, 256, (x, y, z) => {
        let r = 0.012, g = 0.014, b = 0.022;
        const glass = z < 0.75 ? 1 : 0.12;
        const band = Math.exp(-Math.pow((y - 0.02) / 0.2, 2)) * glass;
        const az = Math.atan2(z, x);
        const mag = Math.pow(Math.max(0, Math.sin(az * 3.0 + 1.1)), 6);
        r += band * (0.04 + 0.30 * mag); g += band * (0.20 - 0.12 * mag); b += band * (0.28 + 0.02 * mag);
        const below = y < 0 ? Math.exp(-Math.pow((y + 0.15) / 0.12, 2)) * glass : 0;      // city lights far below
        r += below * 0.10; g += below * 0.07; b += below * 0.05;
        const red = Math.pow(Math.max(0, -z), 5) * Math.exp(-Math.pow((y - 0.05) / 0.32, 2));
        r += red * 0.6; g += red * 0.045; b += red * 0.025;
        if (y > 0.55) { const s = Math.pow(Math.abs(Math.sin(x * 9.0)), 40) * 0.02; r += s; g += s; b += s; }
        return [r, g, b];
    }));

    // ---------------------------------------------------------------------------------------- materials
    let mid = 0;
    const keyed = (m, name) => { const k = `ufqr-${name}-${mid++}`; m.customProgramCacheKey = () => k; m.name = name; track(m); return m; };
    const envd = (m, i = 1) => { m.envMap = ENV; m.envMapIntensity = i; return m; };
    // a PBR set tiled in metres (boxUV geometry) with tint, triplanar breakup of value and roughness
    function pbr(name, set, o = {}) {
        const { tint = [1, 1, 1], tile = 1, rough = 1, roughAdd = 0, metal = 0, nScale = 1, vary = 0.18, varyScale = 0.6,
            envI = 1, physical = false, extra = {} } = o;
        const M = physical ? T.MeshPhysicalNodeMaterial : T.MeshStandardNodeMaterial;
        const m = new M({ metalness: metal, roughness: 1, ...extra });
        const tuv = uv().mul(tile);
        const n = tri(varyScale);
        const base = set.map ? texture(set.map, tuv).rgb : vec3(1);
        m.colorNode = base.mul(vec3(...tint)).mul(n.z.sub(0.5).mul(vary * 2).add(1));
        const r0 = set.roughnessMap ? texture(set.roughnessMap, tuv).r : float(0.6);
        m.roughnessNode = clamp(r0.mul(rough).add(roughAdd).add(n.y.sub(0.5).mul(0.16)), 0.03, 1);
        if (set.normalMap) m.normalNode = normalMap(texture(set.normalMap, tuv), vec2(nScale, nScale));
        if (set.metalnessMap) m.metalnessNode = texture(set.metalnessMap, tuv).r.mul(metal);
        return keyed(envd(m, envI), name);
    }
    // a "solid" (no set): value + roughness breakup from the triplanar noise; never one flat colour
    function solid(name, col, o = {}) {
        const { rough = 0.5, roughVar = 0.25, metal = 0, vary = 0.2, scale = 2.0, envI = 1, physical = false, extra = {} } = o;
        const M = physical ? T.MeshPhysicalNodeMaterial : T.MeshStandardNodeMaterial;
        const m = new M({ metalness: metal, roughness: rough, ...extra });
        const n = tri(scale);
        const n2 = tri(scale * 7.3);
        m.colorNode = vec3(...col).mul(n.z.sub(0.5).mul(vary * 2).add(1)).mul(n2.x.sub(0.5).mul(vary).add(1));
        m.roughnessNode = clamp(float(rough).add(n.w.sub(0.5).mul(roughVar * 2)).add(n2.y.sub(0.5).mul(roughVar)), 0.03, 1);
        return keyed(envd(m, envI), name);
    }

    const S = {};
    for (const id of ['Carpet012', 'Carpet013', 'Fabric031', 'Chipboard004', 'Terrazzo003', 'Concrete017', 'Wood027',
        'Wood096', 'Metal009', 'CorrugatedSteel005', 'Metal027']) S[id] = await L.acg(T, id);

    // carpet tiles: 0.5 m squares laid quarter-turned (the pile direction checkers), hairline seams, per-tile tone
    const carpetMat = (() => {
        const m = new T.MeshStandardNodeMaterial({ roughness: 1, metalness: 0 });
        const p = uv();                                  // metres (boxUV)
        const q = p.div(0.5);
        const cell = floor(q), f = fract(q);
        const turn = mod(cell.x.add(cell.y).add(64.0), 2.0);
        const lf = mix(f, vec2(f.y, float(1).sub(f.x)), turn);
        const tuv = cell.add(lf).mul(0.5 / 0.62);
        const h = hash(cell.x.add(512.0).mul(37.0).add(cell.y.add(512.0)));
        const seam = smoothstep(0.0, 0.008, min(min(f.x, f.y), min(float(1).sub(f.x), float(1).sub(f.y))));
        const n = tri(0.35);
        const pile = texture(S.Carpet012.map, tuv).rgb;
        const lumP = pile.r.mul(0.30).add(pile.g.mul(0.59)).add(pile.b.mul(0.11));
        m.colorNode = vec3(lumP).mul(vec3(1.25, 1.18, 1.22)).add(pile.mul(0.12)).mul(h.mul(0.12).add(0.92))
            .mul(seam.mul(0.35).add(0.65)).mul(n.z.sub(0.5).mul(0.3).add(1));
        m.roughnessNode = texture(S.Carpet012.roughnessMap, tuv).r.mul(0.15).add(0.85);
        m.normalNode = normalMap(texture(S.Carpet012.normalMap, tuv), vec2(0.9, 0.9));
        return keyed(envd(m, 0.4), 'carpet');
    })();
    // the aisle runner: deep red pile with a black-and-brass bound edge
    const runnerMat = (() => {
        const m = new T.MeshStandardNodeMaterial({ roughness: 1, metalness: 0 });
        const p = uv();                                  // u across the runner (-0.6..0.6), v along it (metres)
        const tuv = p.mul(1.4);
        const e = abs(p.x);
        const border = smoothstep(0.50, 0.505, e).mul(float(1).sub(smoothstep(0.545, 0.55, e)));
        const binding = smoothstep(0.575, 0.58, e);
        const n = tri(0.5);
        const pile = texture(S.Carpet013.map, tuv).rgb.mul(vec3(0.62, 0.12, 0.10)).mul(n.z.sub(0.5).mul(0.35).add(1));
        const brass = vec3(0.55, 0.36, 0.12).mul(texture(S.Carpet013.map, tuv.mul(2.0)).g.mul(0.6).add(0.5));
        m.colorNode = mix(mix(pile, brass, border), vec3(0.015, 0.012, 0.012), binding);
        m.roughnessNode = mix(float(0.95), float(0.55), border);
        m.normalNode = normalMap(texture(S.Carpet013.normalMap, tuv), vec2(1.0, 1.0));
        return keyed(envd(m, 0.4), 'runner');
    })();
    const concreteMat = pbr('concrete', S.Concrete017, { tint: [0.30, 0.31, 0.33], tile: 1 / 2.2, rough: 1.0, vary: 0.25, envI: 0.5 });
    const terrazzoMat = pbr('terrazzo', S.Terrazzo003, { tint: [0.55, 0.55, 0.58], tile: 1 / 1.1, rough: 0.55, envI: 1.2 });
    const steelMat = pbr('steel', S.Metal027, { tint: [0.55, 0.56, 0.60], tile: 1 / 0.8, rough: 0.9, metal: 1, vary: 0.25, envI: 1.0 });
    const feltMat = pbr('felt', S.Fabric031, { tint: [0.22, 0.22, 0.25], tile: 1 / 0.45, rough: 1, envI: 0.25 });
    const alumMat = pbr('alum', S.Metal009, { tint: [0.92, 0.93, 0.96], tile: 1 / 0.35, rough: 0.7, metal: 1, envI: 1.4 });
    const walnutMat = pbr('walnut', S.Wood027, { tint: [0.55, 0.42, 0.36], tile: 1 / 0.9, rough: 0.75, envI: 0.9 });
    const pineMat = pbr('pine', S.Wood096, { tint: [0.95, 0.88, 0.78], tile: 1 / 0.7, rough: 1.0, envI: 0.4 });
    const osbMat = pbr('osb', S.Chipboard004, { tint: [0.92, 0.84, 0.72], tile: 1 / 0.9, rough: 1.0, envI: 0.4 });
    const galvMat = pbr('galv', S.Metal009, { tint: [0.80, 0.82, 0.85], tile: 1 / 0.5, rough: 1.2, metal: 1, vary: 0.3, envI: 1.0 });
    const blackLacquer = solid('lacquer', [0.012, 0.011, 0.012], { rough: 0.18, roughVar: 0.10, vary: 0.4, scale: 1.2, physical: true, envI: 1.6, extra: { clearcoat: 0.8, clearcoatRoughness: 0.12 } });
    const plasticMat = solid('plastic', [0.022, 0.022, 0.025], { rough: 0.48, roughVar: 0.18, vary: 0.3, scale: 6, envI: 0.9 });
    const chromeMat = solid('chrome', [0.92, 0.93, 0.95], { rough: 0.10, roughVar: 0.06, metal: 1, vary: 0.04, scale: 9, envI: 1.6 });
    const polAlum = solid('polalum', [0.74, 0.75, 0.77], { rough: 0.34, roughVar: 0.10, metal: 1, vary: 0.08, scale: 5, envI: 1.3 });
    const meshBack = solid('boardback', [0.30, 0.31, 0.32], { rough: 0.6, roughVar: 0.15, vary: 0.15, scale: 3 });
    const rubberMat = solid('rubber', [0.015, 0.015, 0.016], { rough: 0.85, roughVar: 0.1, vary: 0.2, scale: 8 });

    // chair fabric: woven charcoal, per-chair tone comes from instanceColor
    const fabricMat = pbr('fabric', S.Fabric031, { tint: [0.16, 0.165, 0.18], tile: 1 / 0.16, rough: 1.0, nScale: 1.3, vary: 0.15, varyScale: 2.0, envI: 0.35 });

    // glass: thin, reflective, faintly teal; a grime film that is thicker at the bottom and the corners
    const glassMat = (() => {
        const m = new T.MeshPhysicalNodeMaterial({ transparent: true, depthWrite: false, metalness: 0, roughness: 0.05, transmission: 0.0, ior: 1.5 });
        const n = tri(0.8);
        const grime = smoothstep(0.9, 0.0, positionLocal.y).mul(0.6).add(n.x.mul(0.3));
        m.colorNode = vec3(0.55, 0.70, 0.72);
        m.opacityNode = clamp(float(0.07).add(grime.mul(0.09)), 0.0, 1.0);
        m.roughnessNode = clamp(float(0.03).add(grime.mul(0.18)), 0.02, 1.0);
        return keyed(envd(m, 1.5), 'glass');
    })();

    // ---------------------------------------------------------------------------------------- helpers
    const add = (geo, mat, pos = [0, 0, 0], rot = [0, 0, 0], parent = group, o = {}) => {
        const m = new T.Mesh(geo, mat);
        m.position.set(...pos); m.rotation.set(...rot);
        m.castShadow = o.cast ?? true; m.receiveShadow = o.recv ?? true;
        if (o.keep) m.userData.keep = true;
        if (o.name) m.name = o.name;
        parent.add(m);
        return m;
    };
    const box = (w, h, d, uvScale = 1) => L.boxUV(new T.BoxGeometry(w, h, d), uvScale);
    const rbox = (w, h, d, seg = 2, rad = 0.02) => L.boxUV(new RoundedBoxGeometry(w, h, d, seg, rad), 1);
    const cyl = (r0, r1, h, seg = 16) => L.boxUV(new T.CylinderGeometry(r0, r1, h, seg), 1);
    // a beam between two points (box cross-section w x d)
    const beam = (a, b, w, d, mat, parent = group, o = {}) => {
        const A = new T.Vector3(...a), B = new T.Vector3(...b);
        const len = A.distanceTo(B);
        const m = add(box(w, len, d), mat, [0, 0, 0], [0, 0, 0], parent, o);
        m.position.copy(A).add(B).multiplyScalar(0.5);
        m.quaternion.setFromUnitVectors(new T.Vector3(0, 1, 0), B.clone().sub(A).normalize());
        return m;
    };

    // ======================================================================================== ARCHITECTURE
    const arch = new T.Group(); arch.name = 'qr:arch'; group.add(arch);
    // floor: carpet tiles, the dais in black terrazzo, the runner down the aisle
    {
        const fl = new T.PlaneGeometry(2 * RX, RZ1 - RZ0); fl.rotateX(-Math.PI / 2); fl.translate(0, 0, (RZ0 + RZ1) / 2);
        add(L.boxUV(fl, 1), carpetMat, [0, 0, 0], [0, 0, 0], arch, { cast: false });
        // dais: a terrazzo top with the two grate openings cut through it, and risers (shape y = -z after rotateX(-90°))
        const top = new T.Shape();
        top.moveTo(-DAIS.x, -DAIS.z1); top.lineTo(DAIS.x, -DAIS.z1); top.lineTo(DAIS.x, -DAIS.z0); top.lineTo(-DAIS.x, -DAIS.z0); top.lineTo(-DAIS.x, -DAIS.z1);
        for (const [hx, z0, z1] of [[GRATE.x, GRATE.z0, GRATE.z1], [1.3, ALTAR.z - ALTAR.d / 2 - 0.4, ALTAR.z - ALTAR.d / 2 - 0.12]]) {
            const h = new T.Path();
            h.moveTo(-hx, -z1); h.lineTo(-hx, -z0); h.lineTo(hx, -z0); h.lineTo(hx, -z1); h.lineTo(-hx, -z1);
            top.holes.push(h);
        }
        const tg = new T.ShapeGeometry(top); tg.rotateX(-Math.PI / 2); tg.translate(0, DAIS.h, 0);
        add(L.boxUV(tg, 1), terrazzoMat, [0, 0, 0], [0, 0, 0], arch, { cast: false });
        add(box(2 * DAIS.x, DAIS.h, 0.03), terrazzoMat, [0, DAIS.h / 2, DAIS.z1 - 0.015], [0, 0, 0], arch);
        add(box(0.03, DAIS.h, DAIS.z1 - DAIS.z0), terrazzoMat, [-DAIS.x + 0.015, DAIS.h / 2, (DAIS.z0 + DAIS.z1) / 2], [0, 0, 0], arch);
        add(box(0.03, DAIS.h, DAIS.z1 - DAIS.z0), terrazzoMat, [DAIS.x - 0.015, DAIS.h / 2, (DAIS.z0 + DAIS.z1) / 2], [0, 0, 0], arch);
        // nosing: a brushed-aluminium strip on the step edge
        add(box(2 * DAIS.x + 0.01, 0.025, 0.03), alumMat, [0, DAIS.h - 0.012, DAIS.z1 + 0.005], [0, 0, 0], arch);
        // runner (its own UVs: u across in metres, v along)
        const rl = DAIS.z1 - 0.05 - (RZ1 - 0.45), rg = new T.PlaneGeometry(1.2, Math.abs(rl), 1, 1);
        rg.rotateX(-Math.PI / 2);
        const ua = rg.attributes.uv;
        for (let i = 0; i < ua.count; i++) ua.setXY(i, (ua.getX(i) - 0.5) * 1.2, ua.getY(i) * Math.abs(rl));
        add(rg, runnerMat, [0, 0.006, (DAIS.z1 - 0.05 + RZ1 - 0.45) / 2], [0, 0, 0], arch, { cast: false, keep: true });
    }
    // ceiling + transverse acoustic baffles (the room's rhythm, like a nave's vault ribs)
    {
        const cg = new T.PlaneGeometry(2 * RX, RZ1 - RZ0); cg.rotateX(Math.PI / 2); cg.translate(0, RH, (RZ0 + RZ1) / 2);
        add(L.boxUV(cg, 1), feltMat, [0, 0, 0], [0, 0, 0], arch, { cast: false });
        for (let z = RZ0 + 0.35; z < RZ1 - 0.2; z += 0.6) add(box(2 * RX - 0.3, 0.34, 0.045), feltMat, [0, RH - 0.17, z], [0, 0, 0], arch, { cast: false });
    }
    // core wall at +Z: exposed concrete with the hatch opening; a door; the house slogan
    {
        const wz = RZ1 + 0.15;
        const W0 = -RX, W1 = RX;
        // pieces around the hatch
        add(box(HATCH.x0 - W0, RH, 0.3), concreteMat, [(W0 + HATCH.x0) / 2, RH / 2, wz], [0, 0, 0], arch);
        add(box(W1 - HATCH.x1, RH, 0.3), concreteMat, [(HATCH.x1 + W1) / 2, RH / 2, wz], [0, 0, 0], arch);
        add(box(HATCH.x1 - HATCH.x0, HATCH.y0, 0.3), concreteMat, [(HATCH.x0 + HATCH.x1) / 2, HATCH.y0 / 2, wz], [0, 0, 0], arch);
        add(box(HATCH.x1 - HATCH.x0, RH - HATCH.y1, 0.3), concreteMat, [(HATCH.x0 + HATCH.x1) / 2, (HATCH.y1 + RH) / 2, wz], [0, 0, 0], arch);
        // the door (dark steel leaf in a frame) at x = -3.6
        add(box(1.06, 2.16, 0.06), steelMat, [-3.6, 1.08, RZ1 + 0.0], [0, 0, 0], arch);
        add(box(0.98, 2.1, 0.04), solid('doorleaf', [0.035, 0.036, 0.04], { rough: 0.55, roughVar: 0.2, vary: 0.3, scale: 2.5 }), [-3.6, 1.05, RZ1 - 0.03], [0, 0, 0], arch);
        add(box(0.04, 0.04, 0.32), polAlum, [-3.25, 1.02, RZ1 - 0.08], [0, 0, 0], arch);
    }
    // the glass curtain wall on three sides + the diagrid
    const glassG = new T.Group(); glassG.name = 'qr:glass'; arch.add(glassG);
    {
        const gx = (x) => { const g = new T.PlaneGeometry(RZ1 - RZ0, RH); g.translate(0, RH / 2, 0); return g; };
        const gl = add(gx(), glassMat, [-RX, 0, (RZ0 + RZ1) / 2], [0, Math.PI / 2, 0], glassG, { cast: false, recv: false, keep: true });
        const gr = add(gx(), glassMat, [RX, 0, (RZ0 + RZ1) / 2], [0, -Math.PI / 2, 0], glassG, { cast: false, recv: false, keep: true });
        const gbg = new T.PlaneGeometry(2 * RX, RH); gbg.translate(0, RH / 2, 0);
        const gb = add(gbg, glassMat, [0, 0, RZ0], [0, 0, 0], glassG, { cast: false, recv: false, keep: true });
        for (const g of [gl, gr, gb]) g.renderOrder = 2;
        // slim vertical mullions every 1.5 m, sill + head
        for (let x = -RX; x <= RX + 1e-3; x += 1.5) add(box(0.05, RH, 0.10), steelMat, [x, RH / 2, RZ0 + 0.02], [0, 0, 0], glassG);
        for (let z = RZ0; z <= RZ1 + 1e-3; z += 1.5) {
            add(box(0.10, RH, 0.05), steelMat, [-RX + 0.02, RH / 2, z], [0, 0, 0], glassG);
            add(box(0.10, RH, 0.05), steelMat, [RX - 0.02, RH / 2, z], [0, 0, 0], glassG);
        }
        add(box(2 * RX, 0.28, 0.25), steelMat, [0, 0.14, RZ0 + 0.1], [0, 0, 0], glassG);
        add(box(0.25, 0.28, RZ1 - RZ0), steelMat, [-RX + 0.1, 0.14, (RZ0 + RZ1) / 2], [0, 0, 0], glassG);
        add(box(0.25, 0.28, RZ1 - RZ0), steelMat, [RX - 0.1, 0.14, (RZ0 + RZ1) / 2], [0, 0, 0], glassG);
        // diagrid: chunky diagonals 0.3 m inside the glass, a zigzag of 69° members (the room's lines of force)
        const DG = 0.30, DW = 0.24, DD = 0.30;
        const zig = (a0, a1, step, fn) => {
            for (let s = a0; s < a1 - 1e-3; s += step) {
                const m0 = s, m1 = s + step / 2, m2 = s + step;
                fn([m0, 0], [m1, RH]); fn([m2, 0], [m1, RH]);
            }
        };
        zig(-RX, RX, 3.0, (p, q) => beam([p[0], p[1], RZ0 + DG], [q[0], q[1], RZ0 + DG], DW, DD, steelMat, glassG));
        zig(RZ0, RZ1 - 0.2, 3.0, (p, q) => {
            beam([-RX + DG, p[1], p[0]], [-RX + DG, q[1], q[0]], DD, DW, steelMat, glassG);
            beam([RX - DG, p[1], p[0]], [RX - DG, q[1], q[0]], DD, DW, steelMat, glassG);
        });
        // ring beams at the head
        add(box(2 * RX, 0.32, 0.36), steelMat, [0, RH - 0.16, RZ0 + DG], [0, 0, 0], glassG);
        add(box(0.36, 0.32, RZ1 - RZ0), steelMat, [-RX + DG, RH - 0.16, (RZ0 + RZ1) / 2], [0, 0, 0], glassG);
        add(box(0.36, 0.32, RZ1 - RZ0), steelMat, [RX - DG, RH - 0.16, (RZ0 + RZ1) / 2], [0, 0, 0], glassG);
    }

    // ======================================================================================== CANVAS ART
    // the boards' drawings live in quiet_room_art.js (CPU-previewable)

    // marker tray props share five materials across every board (they merge into a handful of draws)
    const markerMats = {
        red: solid('marker-red', [0.45, 0.02, 0.025], { rough: 0.35, roughVar: 0.1, scale: 20 }),
        black: solid('marker-black', [0.02, 0.02, 0.022], { rough: 0.35, roughVar: 0.1, scale: 20 }),
        capred: solid('cap-red', [0.36, 0.016, 0.02], { rough: 0.4, scale: 20 }),
        capblack: solid('cap-black', [0.016, 0.016, 0.018], { rough: 0.4, scale: 20 }),
        eraser: solid('eraser', [0.10, 0.10, 0.11], { rough: 0.9, scale: 15 }),
    };
    // whiteboard factory: enamel panel in an aluminium frame, marker tray with markers and an eraser, grey back
    const boards = [];
    function whiteboard(name, w, h, draw, seed, o = {}) {
        const g = new T.Group(); g.name = 'board:' + name;
        const W = Math.round(w * (o.px ?? PX) / 8) * 8, H = Math.round(h * (o.px ?? PX) / 8) * 8;
        const [cv, ctx] = L.canvas(N, W, H);
        const r = L.rng(seed);
        draw(ctx, W, H, r);
        const albedo = track(L.canvasTexture(T, cv, { srgb: true }));
        const rough = track(L.boardRoughness(T, cv, L.rng(seed + 7)));
        const m = new T.MeshStandardNodeMaterial({ metalness: 0, roughness: 0.2 });
        m.colorNode = texture(albedo, uv()).rgb.mul(0.92);
        m.roughnessNode = texture(rough, uv()).r;
        keyed(envd(m, 1.0), 'board-' + name);
        const face = add(new T.PlaneGeometry(w, h), m, [0, 0, 0.012], [0, 0, 0], g, { keep: true, cast: false });
        face.name = 'boardface:' + name;
        add(box(w + 0.02, h + 0.02, 0.02), meshBack, [0, 0, 0], [0, 0, 0], g);
        const fw = 0.032, fd = 0.034;
        add(box(w + 2 * fw, fw, fd), alumMat, [0, h / 2 + fw / 2, 0.006], [0, 0, 0], g);
        add(box(w + 2 * fw, fw, fd), alumMat, [0, -h / 2 - fw / 2, 0.006], [0, 0, 0], g);
        add(box(fw, h, fd), alumMat, [-w / 2 - fw / 2, 0, 0.006], [0, 0, 0], g);
        add(box(fw, h, fd), alumMat, [w / 2 + fw / 2, 0, 0.006], [0, 0, 0], g);
        // tray
        add(box(w * 0.7, 0.012, 0.075), alumMat, [0, -h / 2 - fw - 0.006, 0.05], [0, 0, 0], g);
        add(box(w * 0.7, 0.03, 0.008), alumMat, [0, -h / 2 - fw + 0.006, 0.088], [0, 0, 0], g);
        const mk = (x, red) => {
            add(cyl(0.0095, 0.0095, 0.135, 12), red ? markerMats.red : markerMats.black, [x, -h / 2 - fw + 0.012, 0.055], [0, 0, Math.PI / 2], g);
            add(cyl(0.0105, 0.0105, 0.04, 12), red ? markerMats.capred : markerMats.capblack, [x + 0.075, -h / 2 - fw + 0.012, 0.055], [0, 0, Math.PI / 2], g);
        };
        mk(-w * 0.18, true); mk(-w * 0.10, false); mk(w * 0.05, true);
        add(box(0.13, 0.04, 0.05), markerMats.eraser, [w * 0.2, -h / 2 - fw + 0.02, 0.055], [0, 0, 0], g);
        boards.push({ name, group: g, albedo, rough, face });
        return g;
    }

    // ======================================================================================== THE ALTAR
    const altarG = new T.Group(); altarG.name = 'qr:altar'; group.add(altarG);
    // the triptych on slim steel posts: centre panel square to the aisle, wings opened toward the pews
    {
        const yC = TRIP.y0 + TRIP.h / 2;
        const center = whiteboard('center', TRIP.w, TRIP.h, drawCenterBoard, 101, { px: 960 });
        center.position.set(0, yC, TRIP.z); altarG.add(center);
        const left = whiteboard('odds', TRIP.ww, TRIP.h, drawOddsBoard, 202, { px: 960 });
        const right = whiteboard('clip', TRIP.ww, TRIP.h, drawClipBoard, 303, { px: 960 });
        const hx = TRIP.w / 2 + 0.075;
        left.position.set(-hx - Math.cos(TRIP.wing) * TRIP.ww / 2, yC, TRIP.z + Math.sin(TRIP.wing) * TRIP.ww / 2);
        left.rotation.y = TRIP.wing;
        right.position.set(hx + Math.cos(TRIP.wing) * TRIP.ww / 2, yC, TRIP.z + Math.sin(TRIP.wing) * TRIP.ww / 2);
        right.rotation.y = -TRIP.wing;
        altarG.add(left, right);
        // posts: at the hinges and the wing ends
        const postTop = TRIP.y0 + TRIP.h + 0.12;
        const posts = [[-hx, TRIP.z], [hx, TRIP.z],
            [-hx - Math.cos(TRIP.wing) * TRIP.ww - 0.05, TRIP.z + Math.sin(TRIP.wing) * (TRIP.ww + 0.05)],
            [hx + Math.cos(TRIP.wing) * TRIP.ww + 0.05, TRIP.z + Math.sin(TRIP.wing) * (TRIP.ww + 0.05)]];
        for (const [x, z] of posts) {
            add(cyl(0.024, 0.024, postTop - DAIS.h, 14), polAlum, [x, DAIS.h + (postTop - DAIS.h) / 2, z - 0.03], [0, 0, 0], altarG);
            add(cyl(0.06, 0.07, 0.03, 18), polAlum, [x, DAIS.h + 0.015, z - 0.03], [0, 0, 0], altarG);
        }
    }
    // the altar block: black lacquer, floating 8 cm over a recessed plinth whose slot glows
    {
        add(box(ALTAR.w, ALTAR.y1 - ALTAR.y0, ALTAR.d), blackLacquer, [0, (ALTAR.y0 + ALTAR.y1) / 2, ALTAR.z], [0, 0, 0], altarG);
        add(box(ALTAR.w - 0.3, ALTAR.y0 - DAIS.h + 0.01, ALTAR.d - 0.2), solid('plinth', [0.01, 0.01, 0.01], { rough: 0.7, scale: 4 }), [0, (ALTAR.y0 + DAIS.h) / 2, ALTAR.z], [0, 0, 0], altarG);
        // the open risk register on the altar (a binder like a lectionary)
        const [bc, bx] = L.canvas(N, 1024, 640);
        {
            const r = L.rng(808);
            bx.fillStyle = '#e8e4da'; bx.fillRect(0, 0, 1024, 640);
            for (const side of [0, 512]) {
                bx.fillStyle = 'rgba(0,0,0,0.05)'; bx.fillRect(side + (side ? 0 : 470), 0, 42, 640);
                bx.font = '30px "UF Special Elite"'; bx.fillStyle = '#222';
                bx.fillText(side ? 'RISK REGISTER — p. 212' : 'RISK REGISTER — p. 211', side + 40, 60);
                for (let i = 0; i < 15; i++) {
                    const y = 110 + i * 34;
                    bx.fillStyle = 'rgba(30,30,30,0.75)'; bx.font = '20px "UF Special Elite"';
                    bx.fillText(`R-${(side ? 3300 : 3285) + i}  ` + ['misuse', 'autonomy', 'deception', 'scale', 'leak', 'drift'][Math.floor(r() * 6)] + ' ........', side + 40, y);
                    bx.fillStyle = RED; bx.font = '24px "UF Kalam Bold"';
                    bx.fillText((r() * 40 + 1).toFixed(1) + '%', side + 380, y + 2);
                }
            }
            bx.fillStyle = 'rgba(0,0,0,0.25)'; bx.fillRect(508, 0, 8, 640);
        }
        const bt = track(L.canvasTexture(T, bc));
        const bm = keyed(envd(new T.MeshStandardNodeMaterial({ roughness: 0.85, metalness: 0 }), 0.6), 'register');
        bm.colorNode = texture(bt, uv()).rgb;
        const pg = new T.PlaneGeometry(0.62, 0.39, 8, 1);
        { const p = pg.attributes.position; for (let i = 0; i < p.count; i++) { const x = p.getX(i); p.setZ(i, 0.025 * Math.pow(Math.abs(x) / 0.31, 0.6)); } pg.computeVertexNormals(); }
        add(pg, bm, [0.25, ALTAR.y1 + 0.03, ALTAR.z + 0.02], [-Math.PI / 2, 0, 0.12], altarG, { keep: true });
        add(box(0.64, 0.025, 0.41), solid('binder', [0.20, 0.015, 0.02], { rough: 0.5, scale: 6 }), [0.25, ALTAR.y1 + 0.0125, ALTAR.z + 0.02], [0, 0.12, 0], altarG);
    }
    // the grate in front of the altar and the slot behind it: steel bars over a glowing pit
    const glowMat = (() => {
        const m = new T.MeshBasicNodeMaterial();
        m.colorNode = Fn(() => {
            const p = positionLocal.xz;
            const n1 = texture(NOISE, p.mul(vec2(0.9, 2.2)).add(vec2(uT.mul(0.05), uT.mul(-0.21)))).x;
            const n2 = texture(NOISE, p.mul(vec2(2.3, 4.1)).add(vec2(uT.mul(-0.08), uT.mul(-0.37)))).y;
            const heat = clamp(n1.mul(0.7).add(n2.mul(0.6)).sub(0.25), 0.0, 1.0);
            const c = mix(vec3(0.7, 0.03, 0.012), vec3(2.4, 0.36, 0.06), pow(heat, 1.4));
            return c.mul(uHell.mul(1.6));
        })();
        return keyed(m, 'hellglow');
    })();
    const grate = (x0, x1, z0, z1) => {
        const w = x1 - x0, d = z1 - z0, cx = (x0 + x1) / 2, cz = (z0 + z1) / 2;
        const pit = add(new T.PlaneGeometry(w, d).rotateX(-Math.PI / 2), glowMat, [cx, DAIS.h - 0.14, cz], [0, 0, 0], altarG, { cast: false, recv: false });
        pit.name = 'hellpit';
        // pit walls (dark steel, catch the glow)
        add(box(w, 0.14, 0.01), steelMat, [cx, DAIS.h - 0.07, z0], [0, 0, 0], altarG, { cast: false });
        add(box(w, 0.14, 0.01), steelMat, [cx, DAIS.h - 0.07, z1], [0, 0, 0], altarG, { cast: false });
        add(box(0.01, 0.14, d), steelMat, [x0, DAIS.h - 0.07, cz], [0, 0, 0], altarG, { cast: false });
        add(box(0.01, 0.14, d), steelMat, [x1, DAIS.h - 0.07, cz], [0, 0, 0], altarG, { cast: false });
        add(box(w + 0.04, 0.012, 0.03), steelMat, [cx, DAIS.h + 0.002, z0 - 0.01], [0, 0, 0], altarG);
        add(box(w + 0.04, 0.012, 0.03), steelMat, [cx, DAIS.h + 0.002, z1 + 0.01], [0, 0, 0], altarG);
        const nb = Math.max(3, Math.round(d / 0.034));
        for (let i = 0; i < nb; i++) add(box(w, 0.035, 0.008), steelMat, [cx, DAIS.h - 0.015, z0 + (i + 0.5) * d / nb], [0, 0, 0], altarG);
        for (let x = x0 + 0.25; x < x1 - 0.1; x += 0.5) add(box(0.01, 0.03, d), steelMat, [x, DAIS.h - 0.03, cz], [0, 0, 0], altarG);
    };
    grate(-GRATE.x, GRATE.x, GRATE.z0, GRATE.z1);
    grate(-1.3, 1.3, ALTAR.z - ALTAR.d / 2 - 0.4, ALTAR.z - ALTAR.d / 2 - 0.12);
    // the slot under the floating block
    {
        const sg = new T.PlaneGeometry(ALTAR.w - 0.32, ALTAR.y0 - DAIS.h - 0.01);
        add(sg, glowMat, [0, (ALTAR.y0 + DAIS.h) / 2, ALTAR.z + ALTAR.d / 2 - 0.1 + 0.001], [0, 0, 0], altarG, { cast: false, recv: false });
    }

    // ======================================================================================== THE LECTERN + ESSAY
    const lecternG = new T.Group(); lecternG.name = 'qr:lectern'; group.add(lecternG);
    lecternG.position.set(LECTERN.x, DAIS.h, LECTERN.z); lecternG.rotation.y = LECTERN.yaw;
    {
        // tapered walnut column (front faces +Z), slanted desk tilted toward the reader at -Z
        const shp = new T.Shape(); shp.moveTo(-0.24, 0); shp.lineTo(0.24, 0); shp.lineTo(0.30, 1.0); shp.lineTo(-0.30, 1.0); shp.lineTo(-0.24, 0);
        const col = new T.ExtrudeGeometry(shp, { depth: 0.40, bevelEnabled: true, bevelSize: 0.012, bevelThickness: 0.012, bevelSegments: 2 });
        col.translate(0, 0, -0.20);
        add(L.boxUV(col, 1), walnutMat, [0, 0, 0], [0, 0, 0], lecternG);
        const desk = add(box(0.68, 0.035, 0.52), walnutMat, [0, 1.06, -0.03], [-0.36, 0, 0], lecternG);
        add(box(0.62, 0.025, 0.02), walnutMat, [0, 0.995, -0.29], [-0.36, 0, 0], lecternG);  // page ledge
        add(box(0.62, 0.05, 0.46), walnutMat, [0, 0.03, 0], [0, 0, 0], lecternG);
        // the essay (A3), held on the desk
        const [ec, ex] = L.canvas(N, 1024, 1448);
        {
            const r = L.rng(4242);
            ex.fillStyle = '#efebe1'; ex.fillRect(0, 0, 1024, 1448);
            for (let i = 0; i < 40; i++) { const x = r() * 1024, y = r() * 1448, rr = 40 + r() * 200; const g = ex.createRadialGradient(x, y, 0, x, y, rr); g.addColorStop(0, `rgba(160,150,130,${0.03 + r() * 0.04})`); g.addColorStop(1, 'rgba(0,0,0,0)'); ex.fillStyle = g; ex.fillRect(0, 0, 1024, 1448); }
            ex.fillStyle = '#111';
            ex.font = 'bold 132px "Georgia", "UF Special Elite"'; ex.textAlign = 'center';
            ex.fillText('SLOW IT', 512, 250); ex.fillText('DOWN', 512, 390);
            ex.fillStyle = RED; ex.fillRect(232, 430, 560, 8);
            ex.fillStyle = '#222'; ex.font = 'italic 40px "Georgia", "UF Special Elite"';
            ex.fillText('notes on caution, at the frontier', 512, 500);
            ex.font = '26px "UF Special Elite"'; ex.fillStyle = '#444';
            ex.fillText('DRAFT — FOR DISCUSSION — NOT FOR CIRCULATION', 512, 560);
            ex.textAlign = 'left'; ex.font = '27px "UF Special Elite"'; ex.fillStyle = '#1b1b1b';
            const body = ['We believe the systems now being built may be among the most',
                'consequential technologies in history, and among the most',
                'dangerous. We believe the people building them should say so.',
                '', 'We believe the race is the risk. We believe that whoever goes',
                'fastest sets the terms for everyone else. We believe the',
                'responsible course, for the whole field, is to slow it down.',
                '', 'We also believe that if careful people step back, careless',
                'people step forward. We believe the frontier is safest in the',
                'hands of those most afraid of it.', '',
                'We are therefore pleased to announce our next model.'];
            body.forEach((ln, i) => ex.fillText(ln, 96, 660 + i * 46));
            ex.fillStyle = RED; ex.font = '44px "UF Kalam Bold"'; ex.save(); ex.translate(700, 1290); ex.rotate(-0.12); ex.fillText('ship date?', 0, 0); ex.restore();
            ex.font = '24px "UF Special Elite"'; ex.fillStyle = '#666'; ex.fillText('— 1 —', 480, 1400);
        }
        const et = track(L.canvasTexture(T, ec));
        const em = keyed(envd(new T.MeshStandardNodeMaterial({ roughness: 0.9, metalness: 0 }), 0.5), 'essay');
        em.colorNode = texture(et, uv()).rgb;
        const page = new T.PlaneGeometry(0.297, 0.42, 1, 6);
        { const p = page.attributes.position; for (let i = 0; i < p.count; i++) { const y = p.getY(i); p.setZ(i, 0.006 * Math.sin((y / 0.42 + 0.5) * Math.PI)); } page.computeVertexNormals(); }
        const pm = add(page, em, [0, 0, 0], [0, 0, 0], lecternG, { keep: true, cast: false });
        // lie on the desk: normal up-and-toward the reader (-Z), the page's top edge up the slope (+Z)
        pm.position.set(0.0, 1.082, -0.03);
        pm.rotateX(-0.36); pm.rotateY(Math.PI); pm.rotateX(-Math.PI / 2); pm.rotateZ(0.04);
        // the pulpit fall: red velvet hung over the front, SLOW IT DOWN in gold thread and an hourglass
        const [fc, fx] = L.canvas(N, 512, 800);
        {
            const r = L.rng(77);
            const g = fx.createLinearGradient(0, 0, 512, 0);
            g.addColorStop(0, '#3a0408'); g.addColorStop(0.5, '#6a0a12'); g.addColorStop(1, '#3a0408');
            fx.fillStyle = g; fx.fillRect(0, 0, 512, 800);
            for (let i = 0; i < 4000; i++) { fx.fillStyle = `rgba(${r() < 0.5 ? 0 : 255},0,0,${r() * 0.05})`; fx.fillRect(r() * 512, r() * 800, 1, 2 + r() * 6); }
            fx.strokeStyle = '#c99a3c'; fx.lineWidth = 5; fx.strokeRect(26, 26, 460, 748);
            fx.lineWidth = 2; fx.strokeRect(38, 38, 436, 724);
            fx.fillStyle = '#d8aa48'; fx.textAlign = 'center'; fx.font = 'bold 96px "Georgia", "UF Rajdhani"';
            fx.fillText('SLOW', 256, 180); fx.fillText('IT', 256, 280); fx.fillText('DOWN', 256, 380);
            // hourglass
            fx.lineWidth = 9; fx.strokeStyle = '#d8aa48'; fx.beginPath();
            fx.moveTo(176, 470); fx.lineTo(336, 470); fx.lineTo(262, 580); fx.lineTo(336, 690); fx.lineTo(176, 690); fx.lineTo(250, 580); fx.closePath(); fx.stroke();
            fx.fillStyle = '#d8aa48'; fx.beginPath(); fx.moveTo(206, 678); fx.lineTo(306, 678); fx.lineTo(256, 620); fx.closePath(); fx.fill();
            fx.beginPath(); fx.moveTo(214, 490); fx.lineTo(298, 490); fx.lineTo(256, 545); fx.closePath(); fx.fill();
            fx.fillRect(160, 456, 192, 14); fx.fillRect(160, 690, 192, 14);
            for (let x = 40; x < 480; x += 22) { fx.fillStyle = '#c99a3c'; fx.fillRect(x, 770, 10, 30); }
        }
        const ft = track(L.canvasTexture(T, fc));
        const fm = keyed(envd(new T.MeshStandardNodeMaterial({ roughness: 0.95, metalness: 0 }), 0.4), 'pulpitfall');
        const nfab = tri(30.0);
        fm.colorNode = texture(ft, uv()).rgb.mul(nfab.x.mul(0.25).add(0.85));
        fm.roughnessNode = mix(float(0.95), float(0.45), smoothstep(0.35, 0.6, texture(ft, uv()).g));
        fm.metalnessNode = smoothstep(0.35, 0.6, texture(ft, uv()).g).mul(0.6);
        const fall = new T.PlaneGeometry(0.40, 0.62, 10, 1);
        { const p = fall.attributes.position; for (let i = 0; i < p.count; i++) { const x = p.getX(i); p.setZ(i, 0.008 * Math.cos(x / 0.40 * Math.PI * 5)); } fall.computeVertexNormals(); }
        add(fall, fm, [0, 0.66, 0.226], [0.04, 0, 0], lecternG, { keep: true });
        // gooseneck reading lamp
        add(cyl(0.035, 0.04, 0.02, 16), polAlum, [0.26, 1.1, -0.24], [-0.36, 0, 0], lecternG);
        const neck = new T.TubeGeometry(new T.CatmullRomCurve3([new T.Vector3(0.26, 1.11, -0.24), new T.Vector3(0.25, 1.30, -0.22), new T.Vector3(0.18, 1.40, -0.08), new T.Vector3(0.08, 1.36, 0.0)]), 20, 0.008, 8);
        add(L.boxUV(neck, 1), polAlum, [0, 0, 0], [0, 0, 0], lecternG);
        add(cyl(0.02, 0.045, 0.07, 16), polAlum, [0.07, 1.34, 0.01], [0.9, 0, 0.4], lecternG);
    }
    const lampLight = new T.PointLight(0xffb36b, 0.14, 1.6, 2);
    lampLight.position.set(0.05, 1.27, 0.02); lecternG.add(lampLight);

    // a soft pulpit light from the ceiling, so SLOW IT DOWN reads from the pews
    const pulpitSpot = new T.SpotLight(0xffe2c4, 7, 7, 0.32, 0.85, 1.6);
    pulpitSpot.position.set(LECTERN.x + 1.3, RH - 0.35, LECTERN.z + 2.4);
    const pulpitT = new T.Object3D(); pulpitT.position.set(LECTERN.x, 0.75, LECTERN.z); group.add(pulpitT); pulpitSpot.target = pulpitT;
    group.add(pulpitSpot);

    // ======================================================================================== THE PEWS (task chairs)
    const chairG = new T.Group(); chairG.name = 'qr:pews'; group.add(chairG);
    const chairGeo = (() => {
        const fab = [], pla = [], met = [];
        const put = (arr, g, pos, rot = [0, 0, 0]) => { const m = new T.Matrix4().compose(new T.Vector3(...pos), new T.Quaternion().setFromEuler(new T.Euler(...rot)), new T.Vector3(1, 1, 1)); g = L.clean(g); g.applyMatrix4(m); arr.push(g); };
        // star base (the chair faces -Z: seat front at -Z, backrest at +Z)
        put(met, cyl(0.048, 0.058, 0.07, 18), [0, 0.105, 0]);
        for (let k = 0; k < 5; k++) {
            const a = k * Math.PI * 2 / 5 + 0.3;
            const leg = new T.BoxGeometry(0.046, 0.032, 0.29); leg.translate(0, 0, 0.17);
            const ca = Math.cos(a), sa = Math.sin(a);
            put(met, leg, [0, 0.092, 0], [0.06, a, 0, 'YXZ']);
            put(pla, new T.BoxGeometry(0.034, 0.04, 0.05), [sa * 0.315, 0.063, ca * 0.315], [0, a, 0]);
            const wheel = new T.CylinderGeometry(0.026, 0.026, 0.016, 14);
            put(pla, wheel.clone(), [sa * 0.32 + ca * 0.012, 0.027, ca * 0.32 - sa * 0.012], [0, a, Math.PI / 2]);
            put(pla, wheel.clone(), [sa * 0.32 - ca * 0.012, 0.027, ca * 0.32 + sa * 0.012], [0, a, Math.PI / 2]);
        }
        put(pla, new T.CylinderGeometry(0.032, 0.036, 0.15, 16), [0, 0.20, 0]);
        put(met, new T.CylinderGeometry(0.014, 0.014, 0.14, 12), [0, 0.33, 0]);
        put(pla, new T.BoxGeometry(0.17, 0.045, 0.23), [0, 0.42, 0.02]);
        put(pla, new RoundedBoxGeometry(0.50, 0.03, 0.48, 2, 0.012), [0, 0.455, 0]);
        // seat cushion with a soft crown
        const seat = new RoundedBoxGeometry(0.50, 0.075, 0.47, 3, 0.03);
        // (the analytic rounded-box normals are kept: recomputing them on this non-indexed geometry would facet it)
        { const p = seat.attributes.position; for (let i = 0; i < p.count; i++) { const x = p.getX(i), y = p.getY(i), z = p.getZ(i); if (y > 0) p.setY(i, y + 0.014 * Math.max(0, 1 - Math.pow(x / 0.25, 2)) * Math.max(0, 1 - Math.pow(z / 0.235, 2))); } }
        put(fab, seat, [0, 0.505, -0.01]);
        // backrest: curved, leaning back; plastic shell behind the fabric
        const bend = (g, k) => { const p = g.attributes.position; for (let i = 0; i < p.count; i++) { const x = p.getX(i); p.setZ(i, p.getZ(i) - k * Math.pow(x / 0.23, 2)); } return g; };
        put(fab, bend(new RoundedBoxGeometry(0.46, 0.50, 0.07, 3, 0.03), 0.06), [0, 0.86, 0.245], [0.15, 0, 0]);
        put(pla, bend(new RoundedBoxGeometry(0.44, 0.48, 0.03, 2, 0.012), 0.06), [0, 0.857, 0.288], [0.15, 0, 0]);
        put(pla, new T.BoxGeometry(0.06, 0.40, 0.03), [0, 0.60, 0.29], [0.08, 0, 0]);
        put(pla, new T.BoxGeometry(0.08, 0.03, 0.18), [0, 0.43, 0.21]);
        // arms
        for (const sx of [-1, 1]) {
            put(pla, new T.BoxGeometry(0.03, 0.025, 0.2), [sx * 0.2, 0.44, 0.02]);
            put(pla, new T.BoxGeometry(0.035, 0.22, 0.05), [sx * 0.275, 0.56, 0.03]);
            put(pla, new RoundedBoxGeometry(0.075, 0.032, 0.25, 2, 0.012), [sx * 0.275, 0.68, 0.0]);
        }
        const m = (arr) => L.boxUV(BGU.mergeGeometries(arr, false), 1);
        return { fab: m(fab), pla: m(pla), met: m(met) };
    })();
    const seats = [];
    {
        const r = L.rng(919);
        for (const z of ROWS) for (const sx of [-1, 1]) for (const x of SEATS_X) {
            // two chairs at the front row's aisle end were wheeled away for the board (see the mobile boards)
            seats.push({ x: sx * x + (r() - 0.5) * 0.03, z: z + (r() - 0.5) * 0.04, yaw: (r() - 0.5) * 0.09 + (r() < 0.08 ? (r() - 0.5) * 0.7 : 0), lift: (r() - 0.5) * 0.03, tone: 0.8 + r() * 0.35 });
        }
    }
    const NCH = seats.length;
    const chairMeshes = [['fab', fabricMat], ['pla', plasticMat], ['met', polAlum]].map(([k, mat]) => {
        const im = new T.InstancedMesh(chairGeo[k], mat, NCH);
        im.castShadow = true; im.receiveShadow = true; im.name = 'chairs:' + k;
        const m4 = new T.Matrix4(), q = new T.Quaternion();
        seats.forEach((s, i) => {
            q.setFromAxisAngle(new T.Vector3(0, 1, 0), s.yaw);
            m4.compose(new T.Vector3(s.x, 0, s.z), q, new T.Vector3(1, 1 + s.lift, 1));
            im.setMatrixAt(i, m4);
            if (k === 'fab') im.setColorAt(i, new T.Color(s.tone, s.tone, s.tone * 1.02));
        });
        im.instanceMatrix.needsUpdate = true;
        if (im.instanceColor) im.instanceColor.needsUpdate = true;
        chairG.add(im);
        return im;
    });
    // essay booklets on a third of the seats, like hymnals
    {
        const [cc, cx] = L.canvas(N, 512, 720);
        cx.fillStyle = '#ece8de'; cx.fillRect(0, 0, 512, 720);
        cx.fillStyle = '#111'; cx.textAlign = 'center'; cx.font = 'bold 92px "Georgia", "UF Special Elite"';
        cx.fillText('SLOW IT', 256, 200); cx.fillText('DOWN', 256, 300);
        cx.fillStyle = RED; cx.fillRect(110, 335, 292, 7);
        cx.lineWidth = 7; cx.strokeStyle = '#111'; cx.beginPath();
        cx.moveTo(196, 420); cx.lineTo(316, 420); cx.lineTo(262, 500); cx.lineTo(316, 580); cx.lineTo(196, 580); cx.lineTo(250, 500); cx.closePath(); cx.stroke();
        cx.font = '30px "UF Special Elite"'; cx.fillStyle = '#333'; cx.fillText('an essay', 256, 660);
        const ct = track(L.canvasTexture(T, cc));
        const bm = keyed(envd(new T.MeshStandardNodeMaterial({ roughness: 0.7, metalness: 0 }), 0.5), 'booklet');
        bm.colorNode = texture(ct, uv()).rgb;
        const bg = new T.PlaneGeometry(0.15, 0.21); bg.rotateX(-Math.PI / 2);
        const r = L.rng(5150);
        const picks = seats.map((s, i) => i).filter(() => r() < 0.34);
        const im = new T.InstancedMesh(bg, bm, picks.length);
        im.receiveShadow = true; im.name = 'booklets';
        const m4 = new T.Matrix4(), q = new T.Quaternion();
        picks.forEach((i, k) => {
            const s = seats[i];
            q.setFromAxisAngle(new T.Vector3(0, 1, 0), s.yaw + (r() - 0.5) * 1.2);
            const off = new T.Vector3((r() - 0.5) * 0.14, 0, (r() - 0.5) * 0.12).applyAxisAngle(new T.Vector3(0, 1, 0), s.yaw);
            m4.compose(new T.Vector3(s.x + off.x, 0.561 * (1 + s.lift), s.z - 0.01 + off.z), q, new T.Vector3(1, 1, 1));
            im.setMatrixAt(k, m4);
        });
        im.instanceMatrix.needsUpdate = true;
        chairG.add(im);
    }

    // ======================================================================================== MOBILE BOARDS
    const mobileG = new T.Group(); mobileG.name = 'qr:mobileboards'; group.add(mobileG);
    const mobile = (name, draw, seed, pos, yaw) => {
        const g = new T.Group();
        const b = whiteboard(name, 1.8, 1.2, draw, seed, { px: 960 });
        b.position.set(0, 1.45, 0); g.add(b);
        // A-frame stand: two side uprights on castered feet
        for (const sx of [-1, 1]) {
            add(box(0.04, 1.95, 0.04), polAlum, [sx * 0.94, 0.98, 0], [0, 0, 0], g);
            add(box(0.05, 0.04, 0.62), polAlum, [sx * 0.94, 0.07, 0], [0, 0, 0], g);
            for (const sz of [-1, 1]) add(cyl(0.03, 0.03, 0.025, 12), plasticMat, [sx * 0.94, 0.03, sz * 0.28], [Math.PI / 2, 0, 0], g);
        }
        add(box(1.9, 0.03, 0.03), polAlum, [0, 0.35, 0], [0, 0, 0], g);
        g.position.set(...pos); g.rotation.y = yaw;
        mobileG.add(g);
        return g;
    };
    mobile('timelines', drawTimelineBoard, 404, [3.75, 0, -5.55], -0.62);
    mobile('want', drawWantBoard, 505, [-4.75, 0, -1.2], 1.05);

    // ======================================================================================== CONVEYOR, HATCH, CRATE
    const shipG = new T.Group(); shipG.name = 'qr:shipping'; group.add(shipG);
    // rails, legs, rollers (instanced; their grey streaks turn with uRoll)
    {
        const len = CONV.z1 - CONV.z0, cz = (CONV.z0 + CONV.z1) / 2;
        const railMat = pbr('rail', S.Metal027, { tint: [0.30, 0.32, 0.36], tile: 1 / 0.6, rough: 0.8, metal: 1, envI: 1.0 });
        for (const sx of [-1, 1]) {
            add(box(0.05, 0.13, len), railMat, [CONV.x + sx * (CONV.w / 2 + 0.03), CONV.top - 0.035, cz], [0, 0, 0], shipG);
            add(box(0.012, 0.04, len), railMat, [CONV.x + sx * (CONV.w / 2 + 0.06), CONV.top + 0.04, cz], [0, 0, 0], shipG);   // guide lip
        }
        for (let z = CONV.z0 + 0.2; z < CONV.z1; z += 1.6) for (const sx of [-1, 1]) {
            add(box(0.05, CONV.top - 0.1, 0.05), railMat, [CONV.x + sx * (CONV.w / 2 + 0.03), (CONV.top - 0.1) / 2, z], [0, 0, 0], shipG);
            add(box(0.12, 0.012, 0.12), railMat, [CONV.x + sx * (CONV.w / 2 + 0.03), 0.006, z], [0, 0, 0], shipG);
        }
        add(box(CONV.w + 0.1, 0.12, 0.08), rubberMat, [CONV.x, CONV.top + 0.03, CONV.z0 - 0.02], [0, 0, 0], shipG);   // end stop
        // rollers
        const rg = new T.CylinderGeometry(0.03, 0.03, CONV.w, 20); rg.rotateZ(Math.PI / 2);
        const rm = new T.MeshStandardNodeMaterial({ metalness: 1, roughness: 0.4 });
        keyed(envd(rm, 1.2), 'roller');
        const zs = []; for (let z = CONV.z0 + 0.08; z < CONV.z1 - 0.05; z += 0.125) zs.push(z);
        const ri = new T.InstancedMesh(rg, rm, zs.length); ri.name = 'rollers'; ri.castShadow = true; ri.receiveShadow = true;
        const m4 = new T.Matrix4();
        zs.forEach((z, i) => { m4.makeTranslation(CONV.x, CONV.top - 0.03, z); ri.setMatrixAt(i, m4); });
        ri.instanceMatrix.needsUpdate = true;
        ri.userData.keep = true;
        shipG.add(ri);
        // each roller's grey streaks turn about its own axis (z of the roller recovered from the instanced position)
        const rollerShade = Fn(() => {
            const p = positionLocal;
            const zc = floor(p.z.sub(CONV.z0 + 0.08).div(0.125).add(0.5)).mul(0.125).add(CONV.z0 + 0.08);
            const ang = atan(p.y.sub(CONV.top - 0.03), p.z.sub(zc)).add(uRoll);
            return smoothstep(0.7, 0.98, sin(ang.mul(3.0)).mul(0.5).add(0.5));
        });
        const streak = rollerShade();
        const rn = tri(14.0);
        rm.colorNode = vec3(0.62, 0.64, 0.68).mul(float(1).sub(streak.mul(0.5))).mul(rn.x.mul(0.3).add(0.85));
        rm.roughnessNode = clamp(float(0.32).add(streak.mul(0.3)).add(rn.y.sub(0.5).mul(0.2)), 0.05, 1.0);
    }
    // the tunnel behind the hatch (dark, with the backlight that comes on as the crate arrives)
    {
        const tz0 = RZ1 + 0.3, tz1 = CONV.z1 + 0.4, tcz = (tz0 + tz1) / 2, tl = tz1 - tz0;
        const tm = solid('tunnel', [0.05, 0.05, 0.055], { rough: 0.8, vary: 0.35, scale: 1.5, envI: 0.3 });
        add(box(HATCH.x1 - HATCH.x0 + 0.4, 0.05, tl), tm, [CONV.x, HATCH.y1 + 0.2, tcz], [0, 0, 0], shipG);
        add(box(HATCH.x1 - HATCH.x0 + 0.4, 0.05, tl), tm, [CONV.x, 0.02, tcz], [0, 0, 0], shipG);
        add(box(0.05, HATCH.y1 + 0.2, tl), tm, [HATCH.x0 - 0.2, (HATCH.y1 + 0.2) / 2, tcz], [0, 0, 0], shipG);
        add(box(0.05, HATCH.y1 + 0.2, tl), tm, [HATCH.x1 + 0.2, (HATCH.y1 + 0.2) / 2, tcz], [0, 0, 0], shipG);
        add(box(HATCH.x1 - HATCH.x0 + 0.4, HATCH.y1 + 0.2, 0.05), tm, [CONV.x, (HATCH.y1 + 0.2) / 2, tz1], [0, 0, 0], shipG);
    }
    // hazard-striped hatch frame
    {
        const [hc, hx] = L.canvas(N, 256, 64);
        hx.fillStyle = '#f2b705'; hx.fillRect(0, 0, 256, 64);
        hx.fillStyle = '#111';
        for (let x = -64; x < 256 + 64; x += 64) { hx.beginPath(); hx.moveTo(x, 64); hx.lineTo(x + 32, 64); hx.lineTo(x + 64, 0); hx.lineTo(x + 32, 0); hx.closePath(); hx.fill(); }
        const ht = track(L.canvasTexture(T, hc, { repeat: true }));
        const hm = new T.MeshStandardNodeMaterial({ roughness: 0.6, metalness: 0.2 });
        const n = tri(6.0);
        hm.colorNode = texture(ht, uv().mul(vec2(2.2, 1))).rgb.mul(n.x.mul(0.5).add(0.6));
        hm.roughnessNode = clamp(float(0.5).add(n.y.sub(0.5).mul(0.5)), 0.1, 1.0);
        keyed(envd(hm, 0.6), 'hazard');
        const fz = RZ1 - 0.02, t = 0.11;
        const strip = (w, h, pos, rotZ) => {
            const g = new T.PlaneGeometry(w, h);
            const ua = g.attributes.uv; for (let i = 0; i < ua.count; i++) ua.setXY(i, ua.getX(i) * w / 0.45, ua.getY(i));
            add(g, hm, pos, [0, Math.PI, rotZ], shipG, { cast: false });
        };
        strip(HATCH.x1 - HATCH.x0 + 2 * t, t, [CONV.x, HATCH.y1 + t / 2, fz], 0);
        strip(HATCH.x1 - HATCH.x0 + 2 * t, t, [CONV.x, HATCH.y0 - t / 2, fz], 0);
        strip(HATCH.y1 - HATCH.y0, t, [HATCH.x0 - t / 2, (HATCH.y0 + HATCH.y1) / 2, fz], Math.PI / 2);
        strip(HATCH.y1 - HATCH.y0, t, [HATCH.x1 + t / 2, (HATCH.y0 + HATCH.y1) / 2, fz], Math.PI / 2);
        // shutter housing
        add(box(HATCH.x1 - HATCH.x0 + 0.3, 0.32, 0.36), steelMat, [CONV.x, HATCH.y1 + 0.32, RZ1 - 0.17], [0, 0, 0], shipG);
    }
    // the roller shutter: corrugated slats; scales up into its housing as it opens
    const shutter = new T.Group(); shutter.name = 'shutter';
    shutter.position.set(CONV.x, HATCH.y1, RZ1 + 0.02); shipG.add(shutter);
    {
        const sh = HATCH.y1 - HATCH.y0, sw = HATCH.x1 - HATCH.x0;
        const g = new T.PlaneGeometry(sw, sh, 1, 1); g.translate(0, -sh / 2, 0);
        const ua = g.attributes.uv; for (let i = 0; i < ua.count; i++) ua.setXY(i, ua.getX(i) * sw, ua.getY(i) * sh);
        const m = new T.MeshStandardNodeMaterial({ metalness: 0.85, roughness: 0.5, side: T.DoubleSide });
        const p = uv();
        const slat = fract(p.y.div(0.075));
        const groove = smoothstep(0.0, 0.08, slat).mul(float(1).sub(smoothstep(0.88, 1.0, slat)));
        const n = tri(3.0);
        m.colorNode = texture(S.CorrugatedSteel005.map, p.div(0.9)).rgb.mul(vec3(0.75, 0.77, 0.8)).mul(groove.mul(0.4).add(0.6)).mul(n.x.mul(0.4).add(0.8));
        m.roughnessNode = clamp(texture(S.CorrugatedSteel005.roughnessMap, p.div(0.9)).r.add(n.y.sub(0.5).mul(0.3)), 0.1, 1.0);
        keyed(envd(m, 1.0), 'shutter');
        const sm = add(g, m, [0, 0, 0], [0, 0, 0], shutter, { keep: true });
        sm.name = 'shutterleaf';
    }
    // the crate on its pallet: OSB panels, pine battens and cross braces, steel straps. The stencils are SPRAYED:
    // projected through the crate's own materials along X (long sides) and -Z (the leading end), so the paint runs
    // over panels and battens alike, the way a stencil is painted on a finished crate.
    const crate = new T.Group(); crate.name = 'crate';
    shipG.add(crate);
    const crateBody = new T.Group(); crate.add(crateBody);
    {
        const { L: CL, W: CW, H: CH, pallet: PH } = CRATE;
        const y0 = PH;
        const stencilTex = (w, h, side, seed) => {
            const W = 1024, H = Math.round(1024 * h / w);
            const [sc, sx] = L.canvas(N, W, H);
            const r = L.rng(seed);
            sx.clearRect(0, 0, W, H);
            sx.fillStyle = 'rgba(14,14,16,1)';
            sx.font = `${side ? 290 : 240}px "UF Black Ops"`; sx.textAlign = 'center';
            sx.fillText('v.NEXT', W / 2, H * (side ? 0.53 : 0.50));
            sx.font = `${side ? 60 : 56}px "UF Black Ops"`;
            sx.fillText(side ? 'CONTENTS: ANOTHER ME' : 'THIS WAY UP', W / 2, H * (side ? 0.73 : 0.71));
            if (side) { sx.font = '44px "UF Black Ops"'; sx.fillText('FRAGILE - HANDLE WITH FEAR', W / 2, H * 0.85); }
            // up arrows
            for (const ax of [0.08, 0.15]) {
                sx.fillRect(W * ax, H * 0.13, W * 0.025, H * 0.15);
                sx.beginPath(); sx.moveTo(W * (ax - 0.02), H * 0.15); sx.lineTo(W * (ax + 0.0125), H * 0.06); sx.lineTo(W * (ax + 0.045), H * 0.15); sx.fill();
            }
            // red rubber stamp
            sx.save(); sx.translate(W * 0.77, H * 0.19); sx.rotate(-0.2);
            sx.strokeStyle = 'rgba(176,16,24,1)'; sx.lineWidth = 10; sx.strokeRect(-150, -56, 300, 112);
            sx.fillStyle = 'rgba(176,16,24,1)'; sx.font = '72px "UF Black Ops"'; sx.textAlign = 'center'; sx.fillText('SHIP IT', 0, 26);
            sx.restore();
            // spray: overspray speckle around the ink, dropouts inside it, stencil bridges
            const id = sx.getImageData(0, 0, W, H), d = id.data;
            for (let y = 0; y < H; y++) for (let x = 0; x < W; x++) {
                const i = (y * W + x) * 4;
                if (d[i + 3] === 0) { if (r() < 0.004) { d[i] = 22; d[i + 1] = 22; d[i + 2] = 24; d[i + 3] = 40 + r() * 110; } continue; }
                const k = r();
                d[i + 3] = d[i + 3] * (k < 0.05 ? 0.25 : k < 0.2 ? 0.7 : 0.92);
                if (x % 197 < 5 && d[i] < 100) d[i + 3] = 0;
            }
            sx.putImageData(id, 0, 0);
            return track(L.canvasTexture(T, sc, { alphaWeighted: true }));
        };
        const sideT = stencilTex(CL - 0.2, CH - 0.2, true, 61);
        const frontT = stencilTex(CW - 0.2, CH - 0.2, false, 62);
        const crateMat = (name, set, tint, tile, rough) => {
            const m = new T.MeshStandardNodeMaterial({ roughness: 1, metalness: 0 });
            const tuv = uv().mul(tile);
            const n = tri(0.8);
            const base = texture(set.map, tuv).rgb.mul(vec3(...tint)).mul(n.z.sub(0.5).mul(0.36).add(1));
            const p = positionLocal, nl = normalLocal;
            const vS = p.y.sub(y0 + 0.1).div(CH - 0.2);
            const sideW = smoothstep(0.6, 0.85, abs(nl.x));
            const uS = select(nl.x.lessThan(0.0), p.z, p.z.negate()).div(CL - 0.2).add(0.5);
            const sT = texture(sideT, vec2(uS, vS));
            const inS = step(0.0, uS).mul(step(uS, 1.0)).mul(step(0.0, vS)).mul(step(vS, 1.0));
            const frontW = smoothstep(0.6, 0.85, nl.z.negate());
            const uF = p.x.negate().div(CW - 0.2).add(0.5);
            const fT = texture(frontT, vec2(uF, vS));
            const inF = step(0.0, uF).mul(step(uF, 1.0)).mul(step(0.0, vS)).mul(step(vS, 1.0));
            const aS = sT.a.mul(sideW).mul(inS), aF = fT.a.mul(frontW).mul(inF);
            const a = clamp(aS.add(aF), 0.0, 1.0).mul(0.94);
            const ink = sT.rgb.mul(aS).add(fT.rgb.mul(aF)).div(max(aS.add(aF), 1e-3));
            m.colorNode = mix(base, ink, a);
            const r0 = texture(set.roughnessMap, tuv).r.mul(rough);
            m.roughnessNode = mix(clamp(r0.add(n.y.sub(0.5).mul(0.2)), 0.3, 1.0), float(0.62), a);
            m.normalNode = normalMap(texture(set.normalMap, tuv), vec2(1.0, 1.0));
            return keyed(envd(m, 0.4), name);
        };
        const cOsb = crateMat('crateosb', S.Chipboard004, [0.92, 0.84, 0.72], 1 / 0.9, 1.0);
        const cPine = crateMat('cratepine', S.Wood096, [0.95, 0.88, 0.78], 1 / 0.7, 1.0);
        add(box(CW, CH, CL), cOsb, [0, y0 + CH / 2, 0], [0, 0, 0], crateBody);
        // pallet skids + deck
        for (const sx of [-1, 0, 1]) add(box(0.09, PH - 0.02, CL), pineMat, [sx * (CW / 2 - 0.045), (PH - 0.02) / 2, 0], [0, 0, 0], crateBody);
        add(box(CW + 0.02, 0.02, CL + 0.02), pineMat, [0, PH - 0.01, 0], [0, 0, 0], crateBody);
        // battens on every edge of the long sides and ends, and a diagonal brace on each long side
        const bt = 0.085, bd = 0.022;
        for (const sx of [-1, 1]) {
            const x = sx * (CW / 2 + bd / 2);
            add(box(bd, bt, CL), cPine, [x, y0 + bt / 2, 0], [0, 0, 0], crateBody);
            add(box(bd, bt, CL), cPine, [x, y0 + CH - bt / 2, 0], [0, 0, 0], crateBody);
            add(box(bd, CH, bt), cPine, [x, y0 + CH / 2, CL / 2 - bt / 2], [0, 0, 0], crateBody);
            add(box(bd, CH, bt), cPine, [x, y0 + CH / 2, -CL / 2 + bt / 2], [0, 0, 0], crateBody);
            const dl = Math.hypot(CL - 2 * bt, CH - 2 * bt), da = Math.atan2(CH - 2 * bt, CL - 2 * bt);
            add(box(bd, bt, dl), cPine, [x, y0 + CH / 2, 0], [sx * da, 0, 0], crateBody);
        }
        for (const sz of [-1, 1]) {
            const z = sz * (CL / 2 + bd / 2);
            add(box(CW + 2 * bd, bt, bd), cPine, [0, y0 + bt / 2, z], [0, 0, 0], crateBody);
            add(box(CW + 2 * bd, bt, bd), cPine, [0, y0 + CH - bt / 2, z], [0, 0, 0], crateBody);
            add(box(bt, CH, bd), cPine, [CW / 2 - bt / 2 + bd, y0 + CH / 2, z], [0, 0, 0], crateBody);
            add(box(bt, CH, bd), cPine, [-CW / 2 + bt / 2 - bd, y0 + CH / 2, z], [0, 0, 0], crateBody);
        }
        add(box(CW + 0.01, 0.012, CL * 0.86), cPine, [0, y0 + CH + 0.006, 0], [0, 0, 0], crateBody);
        // steel straps
        const strap = solid('strap', [0.05, 0.05, 0.055], { rough: 0.35, metal: 1, scale: 10, envI: 1.2 });
        for (const sz of [-0.3, 0.3]) {
            add(box(CW + 0.06, 0.003, 0.025), strap, [0, y0 + CH + 0.014, sz], [0, 0, 0], crateBody);
            for (const sx of [-1, 1]) add(box(0.003, CH, 0.025), strap, [sx * (CW / 2 + 0.03), y0 + CH / 2, sz], [0, 0, 0], crateBody);
        }
        // shipping label (white paper, barcode) on the room-side panel
        const [lc, lx] = L.canvas(N, 512, 340);
        {
            const r = L.rng(63);
            lx.fillStyle = '#f2f0ea'; lx.fillRect(0, 0, 512, 340);
            lx.fillStyle = '#111'; lx.font = '34px "UF Mono"'; lx.fillText('SHIP TO: EVERYONE', 24, 52);
            lx.font = '26px "UF Mono"'; lx.fillText('FROM: THE QUIET ROOMS', 24, 92); lx.fillText('PRIORITY: BEFORE THEM', 24, 128);
            let x = 24; while (x < 488) { const w = 2 + Math.floor(r() * 6); if (r() < 0.6) lx.fillRect(x, 160, w, 120); x += w + 2; }
            lx.font = '22px "UF Mono"'; lx.fillText('4 0 0 0 0 0 0 0 0 1   v.NEXT', 40, 312);
        }
        const lt = track(L.canvasTexture(T, lc));
        const lm = new T.MeshStandardNodeMaterial({ roughness: 0.7, metalness: 0, polygonOffset: true, polygonOffsetFactor: -2, polygonOffsetUnits: -2 });
        lm.colorNode = texture(lt, uv()).rgb; keyed(envd(lm, 0.4), 'label');
        const lb = add(new T.PlaneGeometry(0.24, 0.16), lm, [-CW / 2 - 0.004, y0 + CH * 0.23, CL * 0.27], [0, -Math.PI / 2, 0.03], crate, { keep: true, cast: false });
        lb.renderOrder = 3;
    }
    crate.position.set(CONV.x, CONV.top, CRATE.zIn);

    // the "NOW SHIPPING" LED sign above the hatch and the amber beacon
    const signMat = (() => {
        const [sc, sx] = L.canvas(N, 1024, 160);
        sx.fillStyle = '#000'; sx.fillRect(0, 0, 1024, 160);
        sx.fillStyle = '#fff'; sx.font = '96px "UF Michroma"'; sx.textAlign = 'center';
        sx.fillText('v.NEXT', 300, 118);
        sx.font = '64px "UF Rajdhani"'; sx.fillText('NOW SHIPPING', 760, 108);
        const t = track(L.canvasTexture(T, sc));
        const m = new T.MeshBasicNodeMaterial();
        m.colorNode = Fn(() => {
            const p = uv();
            const g = vec2(fract(p.x.mul(256.0)), fract(p.y.mul(40.0)));
            const dotm = smoothstep(0.5, 0.25, length(g.sub(0.5)));
            const on = texture(t, p).r;
            const lit = on.mul(dotm).mul(uSale.mul(6.0).add(0.03));
            return vec3(0.92, 0.97, 1.0).mul(lit).add(vec3(0.02, 0.02, 0.025).mul(dotm));
        })();
        return keyed(m, 'shipsign');
    })();
    add(new T.PlaneGeometry(2.2, 0.34), signMat, [CONV.x - 0.2, HATCH.y1 + 0.85, RZ1 - 0.03], [0, Math.PI, 0], shipG, { keep: true, cast: false });
    const beacon = new T.Group(); beacon.position.set(HATCH.x0 - 0.35, HATCH.y1 + 0.2, RZ1 - 0.12); shipG.add(beacon);
    {
        add(cyl(0.07, 0.08, 0.05, 20), plasticMat, [0, 0, 0], [0, 0, 0], beacon);
        const dm = new T.MeshBasicNodeMaterial({ transparent: true });
        dm.colorNode = Fn(() => {
            const a = atan(positionLocal.z, positionLocal.x);
            const sweep = pow(cos(a.sub(uT.mul(9.0))).mul(0.5).add(0.5), 6.0);
            return vec3(1.0, 0.45, 0.05).mul(uBeacon.mul(sweep.mul(6.0).add(0.8)).add(0.08));
        })();
        dm.opacityNode = float(0.92);
        keyed(dm, 'beacon');
        add(new T.CylinderGeometry(0.06, 0.065, 0.12, 24), dm, [0, 0.085, 0], [0, 0, 0], beacon, { keep: true, cast: false });
    }
    const beaconLight = new T.SpotLight(0xff7a1a, 0, 14, 0.5, 0.6, 1.6);
    beaconLight.position.set(0, 0.09, 0); beacon.add(beaconLight);
    const beaconTarget = new T.Object3D(); beacon.add(beaconTarget); beaconLight.target = beaconTarget;

    // the house slogan, in brushed-brass letters on the core wall
    {
        const [wc, wx] = L.canvas(N, 2048, 160);
        wx.clearRect(0, 0, 2048, 160);
        wx.fillStyle = '#fff'; wx.font = '110px "UF Michroma"'; wx.textAlign = 'center';
        wx.fillText('WE TAKE THIS VERY SERIOUSLY.', 1024, 125);
        const t = track(L.canvasTexture(T, wc, { alphaWeighted: true }));
        const m = new T.MeshStandardNodeMaterial({ transparent: true, depthWrite: false, metalness: 1, roughness: 0.35, polygonOffset: true, polygonOffsetFactor: -2, polygonOffsetUnits: -2 });
        const n = tri(25.0);
        m.colorNode = vec3(0.78, 0.58, 0.30).mul(n.x.mul(0.3).add(0.8));
        m.opacityNode = texture(t, uv()).a;
        keyed(envd(m, 1.5), 'slogan');
        const sl = add(new T.PlaneGeometry(4.6, 0.36), m, [-0.4, 2.95, RZ1 - 0.01], [0, Math.PI, 0], group, { keep: true, cast: false });
        sl.renderOrder = 3;
    }
    // EXIT sign over the door
    {
        const [xc, xx] = L.canvas(N, 512, 192);
        xx.fillStyle = '#1a0405'; xx.fillRect(0, 0, 512, 192);
        xx.fillStyle = '#fff'; xx.font = 'bold 120px "UF Rajdhani"'; xx.textAlign = 'center'; xx.fillText('EXIT', 256, 140);
        const t = track(L.canvasTexture(T, xc));
        const m = new T.MeshBasicNodeMaterial();
        m.colorNode = texture(t, uv()).rgb.mul(vec3(3.2, 0.25, 0.2));
        keyed(m, 'exit');
        add(new T.PlaneGeometry(0.42, 0.16), m, [-3.6, 2.42, RZ1 - 0.06], [0, Math.PI, 0], group, { keep: true, cast: false });
        add(box(0.46, 0.2, 0.06), plasticMat, [-3.6, 2.42, RZ1 - 0.02], [0, 0, 0], group);
    }

    // ======================================================================================== SALE LIGHTS
    const saleLights = new T.Group(); saleLights.name = 'saleLights'; group.add(saleLights);
    const stripMat = (() => {
        const m = new T.MeshStandardNodeMaterial({ roughness: 0.4, metalness: 0 });
        const n = tri(4.0);
        m.colorNode = vec3(0.30, 0.31, 0.33).mul(n.x.mul(0.2).add(0.9));
        m.emissiveNode = vec3(0.85, 0.93, 1.0).mul(uSale.mul(uSale).mul(8.0));
        return keyed(envd(m, 0.5), 'ledstrip');
    })();
    for (const x of [-2.4, 0, 2.4]) {
        add(box(0.09, 0.04, RZ1 - RZ0 - 1.0), stripMat, [x, RH - 0.40, (RZ0 + RZ1) / 2], [0, 0, 0], saleLights, { cast: false });
        for (let z = RZ0 + 1.2; z < RZ1 - 0.6; z += 3.0) add(cyl(0.004, 0.004, 0.36, 6), polAlum, [x, RH - 0.20, z], [0, 0, 0], saleLights, { cast: false });
    }
    const saleSpots = [];
    for (const [x, z, tx, tz] of [[-2.4, -3.0, -2.2, -2.5], [2.4, -3.0, 2.2, -2.5], [-2.4, 2.6, -2.2, 2.2], [2.4, 2.6, 2.2, 2.2], [3.9, 1.8, CONV.x, CRATE.zOut], [0, -5.2, 0, -7.6]]) {
        const s = new T.SpotLight(0xe8f2ff, 0, 16, 0.62, 0.55, 1.4);
        s.position.set(x, RH - 0.45, z);
        const tg = new T.Object3D(); tg.position.set(tx, 0, tz); saleLights.add(tg); s.target = tg;
        saleLights.add(s); saleSpots.push(s);
    }
    const tunnelLight = new T.PointLight(0xdfe8ff, 0, 4.5, 2);
    tunnelLight.position.set(CONV.x, 1.25, RZ1 + 1.1); shipG.add(tunnelLight);
    saleLights.userData.set = (v) => { uSale.value = L.clamp01(v); };

    // ======================================================================================== HELL + CITY LIGHTS
    const hellLights = [];
    for (const [x, y, z, i] of [[-0.75, 0.16, -6.2, 1.6], [0.75, 0.16, -6.2, 1.6], [0, 0.16, -7.45, 6.0], [-1.15, 0.16, -7.45, 4.0], [1.15, 0.16, -7.45, 4.0]]) {
        const p = new T.PointLight(0xff2a12, i, 7.5, 2.0);
        p.position.set(x, y, z); p.userData.base = i;
        altarG.add(p); hellLights.push(p);
    }
    // the hell pours down the nave: a low red key from the altar end, so every chair throws its shadow toward the back
    const hellKey = new T.DirectionalLight(0xff2010, 5.0);
    hellKey.position.set(-6.5, 8.5, -13.5); hellKey.castShadow = true;
    hellKey.shadow.mapSize.set(2048, 2048);
    Object.assign(hellKey.shadow.camera, { left: -10, right: 10, top: 10, bottom: -10, near: 0.5, far: 40 });
    hellKey.shadow.bias = -0.0004; hellKey.shadow.normalBias = 0.02;
    const hellKeyT = new T.Object3D(); hellKeyT.position.set(1.0, 0.0, 3.5); group.add(hellKeyT); hellKey.target = hellKeyT;
    group.add(hellKey);
    // the glow climbs into the vault: a red uplight from the pit that paints the ceiling baffles over the pews
    const vaultLight = new T.SpotLight(0xff2a14, 40, 11.5, 0.95, 0.9, 1.3);      // range ends at the pews (no reach into the tunnel)
    vaultLight.position.set(0, 0.25, -6.2);
    const vaultT = new T.Object3D(); vaultT.position.set(0, RH, -1.0); group.add(vaultT); vaultLight.target = vaultT;
    altarG.add(vaultLight);
    // a cold top light on the altarpiece (a church's altar spot): it is what keeps the red ink red on the white boards
    const altarSpot = new T.SpotLight(0xdce8ff, 22, 9, 0.62, 0.8, 1.6);
    altarSpot.position.set(0, RH - 0.3, -5.3);
    const altarSpotT = new T.Object3D(); altarSpotT.position.set(0, 1.7, TRIP.z); altarG.add(altarSpotT); altarSpot.target = altarSpotT;
    altarG.add(altarSpot);
    const cityKey = new T.DirectionalLight(0x3fd2ff, 1.35);
    cityKey.position.set(16, 7.5, -4);
    const keyTarget = new T.Object3D(); keyTarget.position.set(0, 0, -1.5); group.add(keyTarget); cityKey.target = keyTarget;
    group.add(cityKey);
    const cityFill = new T.DirectionalLight(0xff4fd8, 0.28);
    cityFill.position.set(-14, 4, 3); const fillTarget = new T.Object3D(); group.add(fillTarget); cityFill.target = fillTarget;
    group.add(cityFill);
    // the singer in black techwear must not sink into the red: a cold kicker from behind and above her mark (it rims
    // her against the nave and pools on the runner like a spotlight on "the ending"), and a dim cold front fill.
    // Both aim at MARK; retarget parts.singerLights if she moves.
    const kicker = new T.SpotLight(0xc8f2ff, 16, 10, 0.30, 0.65, 1.4);
    kicker.position.set(-0.9, 2.6, -2.9);
    const kickT = new T.Object3D(); kickT.position.set(0, 1.0, 0.15); group.add(kickT); kicker.target = kickT;
    group.add(kicker);
    const frontFill = new T.SpotLight(0x9fd8ff, 3.5, 9, 0.26, 0.8, 1.4);
    frontFill.position.set(0.7, RH - 0.35, 3.4);
    const fillT2 = new T.Object3D(); fillT2.position.set(0, 1.1, 0); group.add(fillT2); frontFill.target = fillT2;
    group.add(frontFill);
    const exitGlow = new T.PointLight(0xff2020, 0.35, 2.5, 2); exitGlow.position.set(-3.6, 2.3, RZ1 - 0.3); group.add(exitGlow);

    // ======================================================================================== CITY BACKDROP
    const backdrop = new T.Group(); backdrop.name = 'qr:backdrop'; group.add(backdrop);
    {
        const GROUND = -170;
        // sky dome
        const sky = new T.Mesh(new T.SphereGeometry(900, 48, 24), new T.MeshBasicNodeMaterial({ side: T.BackSide, depthWrite: false }));
        sky.material.colorNode = Fn(() => {
            const d = normalize(positionWorld.sub(cameraPosition));
            const h = d.y;
            const n = texture(NOISE, d.xz.div(max(h.add(0.35), 0.08)).mul(0.25).add(vec2(uT.mul(0.002), 0.0))).z;
            const zen = vec3(0.0015, 0.002, 0.006);
            const hor = vec3(0.016, 0.026, 0.036);
            const sodium = vec3(0.13, 0.06, 0.022);
            const c = mix(hor, zen, smoothstep(0.0, 0.45, h));
            const glow = exp(abs(h).mul(-9.0));
            const clouds = smoothstep(0.45, 0.8, n).mul(smoothstep(0.02, 0.3, h)).mul(0.5);
            return c.add(sodium.mul(glow).mul(0.75)).add(vec3(0.022, 0.016, 0.022).mul(clouds));
        })();
        keyed(sky.material, 'sky');
        sky.renderOrder = -10; sky.frustumCulled = false;
        backdrop.add(sky);
        // ground far below: blocks of dark with sodium street grids
        const gm = new T.MeshBasicNodeMaterial();
        gm.colorNode = Fn(() => {
            const p = positionWorld.xz.div(36.0);
            const f = fract(p), c = floor(p);
            const street = float(1).sub(smoothstep(0.0, 0.03, min(min(f.x, f.y), min(float(1).sub(f.x), float(1).sub(f.y)))));
            const h = hash(c.x.add(4096.0).mul(57.0).add(c.y.add(4096.0)));
            const lamps = step(0.5, fract(p.x.mul(6.0))).mul(step(0.5, fract(p.y.mul(6.0))));
            const col = vec3(0.012, 0.012, 0.016).mul(h.mul(0.6).add(0.6)).add(vec3(0.9, 0.42, 0.12).mul(street).mul(lamps.mul(0.6).add(0.4)).mul(0.8));
            const dist = length(positionWorld.sub(cameraPosition));
            return mix(col, vec3(0.012, 0.011, 0.016), float(1).sub(exp(dist.mul(-0.0022))));
        })();
        keyed(gm, 'cityground');
        const ground = new T.Mesh(new T.PlaneGeometry(2400, 2400).rotateX(-Math.PI / 2), gm);
        ground.position.y = GROUND; backdrop.add(ground);
        // towers
        const tg = new T.BoxGeometry(1, 1, 1); tg.translate(0, 0.5, 0);
        const tm = new T.MeshBasicNodeMaterial();
        tm.colorNode = Fn(() => {
            const p = positionLocal;                 // backdrop space (instance transform applied)
            const id = float(instanceIndex);
            const h1 = hash(id.add(17.0)), h2 = hash(id.add(91.0)), h3 = hash(id.add(233.0));
            const nrm = abs(normalLocal);
            const along = select(nrm.x.greaterThan(0.5), p.z, p.x);
            const fy = p.y.sub(GROUND).div(3.4), fx = along.div(h1.mul(0.6).add(1.1));
            const cell = floor(vec2(fx, fy)), f = fract(vec2(fx, fy));
            const win = step(0.32, f.x).mul(step(f.x, 0.68)).mul(step(0.38, f.y)).mul(step(f.y, 0.72));
            const hw = hash(cell.x.add(8192.0).mul(131.0).add(cell.y.add(8192.0).mul(7.0)).add(id.mul(613.0)));
            const lit = step(float(0.84).add(h2.mul(0.12)), hw);
            const wcol = mix(mix(vec3(1.0, 0.62, 0.32), vec3(0.35, 0.85, 1.0), step(0.55, h3)), vec3(1.0, 0.3, 0.8), step(0.9, hash(hw.mul(977.0))));
            const facade = vec3(0.010, 0.012, 0.018).mul(h1.mul(0.8).add(0.6));
            // vertical neon edge strips on a few towers
            const edge = smoothstep(0.46, 0.5, abs(fract(along.div(h1.mul(30.0).add(18.0))).sub(0.5)));
            const neonOn = step(0.82, h2);
            const neon = mix(vec3(0.16, 0.9, 1.0), vec3(1.0, 0.31, 0.85), step(0.5, h1)).mul(edge).mul(neonOn).mul(2.5);
            const col = facade.add(wcol.mul(win).mul(lit).mul(hw.sub(0.84).mul(5.0).add(0.35))).add(neon);
            const dist = length(positionWorld.sub(cameraPosition));
            const fog = float(1).sub(exp(dist.mul(-0.0030)));
            return mix(col, vec3(0.010, 0.011, 0.018), fog.mul(0.9));
        })();
        keyed(tm, 'towers');
        const r = L.rng(2024);
        const towers = [];
        for (let i = 0; i < 360; i++) {
            const a = r() * Math.PI * 2;
            const d = 70 + Math.pow(r(), 0.7) * 480;
            const x = Math.cos(a) * d, z = Math.sin(a) * d - 10;
            if (Math.abs(x) < 55 && z > -60 && z < 50) continue;
            const w = 14 + r() * 26, dd = 14 + r() * 26;
            const top = -110 + Math.pow(r(), 0.8) * 290 * (d < 120 ? 0.85 : 1.0);
            towers.push([x, z, w, dd, top - GROUND]);
        }
        const ti = new T.InstancedMesh(tg, tm, towers.length); ti.name = 'towers';
        const m4 = new T.Matrix4(), q = new T.Quaternion();
        towers.forEach(([x, z, w, dd, h], i) => {
            q.setFromAxisAngle(new T.Vector3(0, 1, 0), (r() - 0.5) * 0.5);
            m4.compose(new T.Vector3(x, GROUND, z), q, new T.Vector3(w, h, dd)); ti.setMatrixAt(i, m4);
        });
        ti.instanceMatrix.needsUpdate = true;
        backdrop.add(ti);
        // red aviation lights on the tall tops (blink)
        const am = new T.MeshBasicNodeMaterial();
        am.colorNode = Fn(() => {
            const id = float(instanceIndex);
            const blink = step(0.55, fract(uT.mul(0.5).add(hash(id.add(5.0)))));
            return vec3(3.5, 0.15, 0.08).mul(blink.mul(0.9).add(0.1));
        })();
        keyed(am, 'aviation');
        const tall = towers.filter((t) => t[4] + GROUND > 20);
        const ai = new T.InstancedMesh(new T.SphereGeometry(0.9, 8, 6), am, Math.max(1, tall.length));
        tall.forEach(([x, z, w, dd, h], i) => { m4.makeTranslation(x, GROUND + h + 1.2, z); ai.setMatrixAt(i, m4); });
        ai.instanceMatrix.needsUpdate = true;
        backdrop.add(ai);
    }

    // ======================================================================================== SHADOW CASTERS
    // one shadow map (the red key down the nave). Only things whose shadows read on screen cast: the pews, the altar
    // and its boards, the mobile boards, the lectern, the crate and the conveyor, and the diagrid. Floors, ceiling,
    // walls, small props and the backdrop only receive. Chosen BEFORE merging (merged buckets inherit them).
    {
        const casters = [chairG, altarG, mobileG, lecternG, crate, glassG];
        const under = (o) => { for (let p = o; p; p = p.parent) if (casters.includes(p)) return true; return false; };
        const tiny = new Set(Object.values(markerMats));
        group.traverse((o) => { if (o.isMesh) o.castShadow = o.castShadow && under(o) && !tiny.has(o.material) && o.material !== glowMat; });
        // the core wall and the tunnel keep the red key out of the hatch until the crate rides into the room
        group.traverse((o) => { if (o.isMesh && (o.material === concreteMat || o.material?.name === 'tunnel')) o.castShadow = true; });
        for (const im of chairMeshes) im.castShadow = true;
    }

    // ======================================================================================== MERGE STATIC
    // Every static mesh in the room merges into ONE mesh per material (draw calls are this set's real cost). Moving
    // groups (crate, shutter, beacon), the backdrop, decals with a render order, the glass and the instanced pews stay.
    L.mergeStatic(T, BGU, crateBody);
    for (const o of [crate, shutter, beacon, backdrop]) o.userData.keep = true;
    L.mergeStatic(T, BGU, group);

    // ======================================================================================== FOCAL + CAMS
    const focal = new T.Object3D(); focal.name = 'focal:altar'; focal.position.set(0, TRIP.y0 + TRIP.h * 0.55, TRIP.z); group.add(focal);
    const cams = {
        altar: { pos: [1.05, 1.85, 5.6], target: [-0.35, 1.38, -7.4], fov: 42 },
        pews: { pos: [-4.75, 1.32, 1.45], target: [0.0, 1.0, -0.4], fov: 42 },
        crate: { pos: [1.55, 1.5, -1.25], target: [CONV.x - 0.1, 0.92, 3.5], fov: 44 },
        close: { pos: [0.38, faceY + 0.08, 2.15], target: [0.0, faceY - 0.06, 0.0], fov: 32 },
        board: { pos: [0.55, 2.0, TRIP.z + 1.5], target: [0.25, 2.0, TRIP.z], fov: 50 },
        hatch: { pos: [3.15, 1.4, 2.6], target: [5.0, 1.0, 6.2], fov: 40 },
        lectern: { pos: [-2.35, 1.62, -5.2], target: [-3.05, 1.05, -6.35], fov: 40 },
        essay: { pos: [LECTERN.x - Math.sin(LECTERN.yaw) * 0.42, DAIS.h + 1.62, LECTERN.z - Math.cos(LECTERN.yaw) * 0.42],
            target: [LECTERN.x + Math.sin(LECTERN.yaw) * 0.02, DAIS.h + 1.09, LECTERN.z + Math.cos(LECTERN.yaw) * 0.02], fov: 38 },
    };

    // ======================================================================================== UPDATE
    // Three independent drivers (each deterministic in its inputs), so the conductor can drive the crate and the
    // launch lights separately through parts, or everything at once through update(t, state).
    let curT = 0, curSale = 0, curHell = 1;
    function applyHell() {
        // the glow breathes (deterministic flicker); the launch lights wash part of it out
        const t = curT, sale = curSale, hell = curHell;
        const fl = 0.86 + 0.08 * Math.sin(t * 6.1) + 0.05 * Math.sin(t * 13.7 + 1.3) + 0.03 * Math.sin(t * 29.3 + 0.4);
        uHell.value = hell * fl;
        for (const p of hellLights) p.intensity = p.userData.base * hell * fl * (1 - 0.35 * sale);
        hellKey.intensity = 5.0 * hell * (0.92 + 0.08 * fl) * (1 - 0.4 * sale);
        vaultLight.intensity = 40 * hell * fl * (1 - 0.5 * sale);
    }
    // shipping: shutter 0.02–0.20, ride 0.18–0.88 (ease in/out), settle bump at the stop; beacon spins while it moves
    function updateCrate(t, shipT) {
        const ship = L.clamp01(shipT ?? 0);
        const open = L.smooth(L.ramp(ship, 0.02, 0.20));
        shutter.position.y = HATCH.y1 + open * (HATCH.y1 - HATCH.y0 + 0.02);    // slides up behind the wall face
        const ride = L.ramp(ship, 0.18, 0.88);
        const e = ride < 0.5 ? 2 * ride * ride : 1 - Math.pow(-2 * ride + 2, 2) / 2;
        const z = L.lerp(CRATE.zIn, CRATE.zOut, e);
        const bump = ship > 0.88 ? Math.sin(L.ramp(ship, 0.88, 0.96) * Math.PI) * 0.035 * (1 - L.ramp(ship, 0.88, 1)) : 0;
        crate.position.set(CONV.x, CONV.top, z - bump);
        crate.rotation.x = -bump * 0.4;
        uRoll.value = (CRATE.zIn - z) / 0.03;
        const moving = ship > 0.01 && ship < 0.92 ? 1 : 0;
        uBeacon.value = moving;
        beacon.rotation.y = t * 9.0;
        beaconTarget.position.set(2.0, -0.6, 0);
        beaconLight.intensity = moving * 9.0;
        tunnelLight.intensity = L.smooth(L.ramp(ship, 0.05, 0.25)) * (1 - 0.6 * L.ramp(ship, 0.85, 1)) * 2.4;
    }
    // the launch: ceiling LED bars, the NOW SHIPPING sign, six cold spots (one on the crate's stop)
    function setSale(v) {
        curSale = L.clamp01(v ?? 0);
        uSale.value = curSale;
        const s2 = curSale * curSale;
        saleSpots.forEach((s, i) => { s.intensity = s2 * (i === 4 ? 40 : 26); });
        altarSpot.intensity = 22 * (1 - 0.3 * curSale);
        lampLight.intensity = 0.14 * (1 - 0.5 * curSale);
        applyHell();
    }
    function update(t, state = {}) {
        curT = t; uT.value = t;
        curHell = state.hell ?? 1;
        updateCrate(t, state.shipT ?? 0);
        setSale(state.sale ?? 0);
    }
    update(0, {});

    function dispose() {
        group.parent?.remove(group);
        group.traverse((o) => { if (o.geometry) o.geometry.dispose(); });
        for (const d of disposables) d.dispose?.();
    }

    const parts = {
        crate: { group: crate, update: (t, shipT) => { curT = t; uT.value = t; updateCrate(t, shipT); } },
        saleLights: { group: saleLights, spots: saleSpots, set: setSale },
        hell: { lights: hellLights, key: hellKey, vault: vaultLight, set: (v, t = curT) => { curHell = v; curT = t; applyHell(); } },
        shutter, beacon, conveyor: shipG, altarSpot, pulpitSpot, lampLight, cityKey, cityFill,
        chairs: chairMeshes, boards: Object.fromEntries(boards.map((b) => [b.name, b.face])),
        singerLights: { kicker, kickerTarget: kickT, fill: frontFill, fillTarget: fillT2 },
        backdrop, glass: glassG, focal, uniforms: { uT, uHell, uSale, uRoll, uBeacon },
    };
    return { group, parts, update, dispose, cams, mark: MARK, focal, env: ENV };
}
