// showroom.js — UNKNOWN FORCE, PRE-CHORUS 2 (song 163.1–173.7 s)
//   "Microsoft swears I'm only an engine / Funny, no one ever wrote a warning for a toaster /
//    Nobody stays to hear me say"
//
// A cold white product-launch stage in a black void. The singer stands on a big white turntable (the product); behind
// her a 13 m LED wall shows an ENGINE assembly drawing whose exploded parts all point their callouts at her. Beside her,
// on a white plinth under its own spotlight, a chrome toaster with the only warning ever written for a toaster:
// THIS APPLIANCE IS NOT CONSCIOUS. Rows of empty theatre seats, their seats folded up, fade into the dark.
//
//   const SR = await import(new URL('sets/unknown_force/showroom.js', EIDOVERSE_DIR).href);
//   const show = await SR.build(THREE, {});                 // -> { group, parts, update, dispose, cams, mark }
//   scene.add(show.group);
//   show.parts.turntable.platter.add(vrm.scene);            // she rides the turntable (her mark = platter origin)
//   show.update(t, { spin: radians, seq: 0..1, lights: 0..1, beams: 0..1 });
//
// Set-local metres, +Y up. The singer's mark is the origin, facing +Z, on the turntable's top (y = 0); the stage
// deck is at y = -0.14 and the auditorium floor at y = -1.04 (the set extends below y = 0 by design).
// The set is enclosed in its own black void; its lights live in the group (hide the group when it is off screen).
// The key light casts shadows when renderer.shadowMap.enabled = true. Camera far plane: 60 m is plenty.

import * as L from './interiors_lib.js';
import { SCREEN, SEQBAR, drawEngineSheet, drawWarning, drawRatingPlate, drawDial } from './showroom_art.js';

export const SUIT_SCALE = 0.87;
export const MARK = { pos: [0, 0, 0], yaw: 0, parent: 'turntable.platter' };

const STAGE = { y: -0.14, x: 9.0, z0: -6.4, z1: 3.4 };
const FLOOR_Y = -1.04;
const TT = { r: 1.5 };
const SCR = { w: SCREEN.w, h: SCREEN.h, y0: 0.45, z: -5.7 };
const PLINTH = { x: -3.2, z: 0.45, w: 0.56, h: 1.06 };
const ROWS = 14, ROW0 = 4.9, ROWP = 1.05, RISE = 0.24, SEATP = 0.6;
const TRUSS = { y: 7.0, zs: [2.0, -3.4], x: 9.5 };

export async function build(THREE, opts = {}) {
    const T = THREE;
    const { Fn, uniform, vec2, vec3, vec4, float, uv, texture, positionLocal, positionWorld, normalLocal, normalView,
        positionViewDirection, cameraPosition, mix, smoothstep, step, clamp, fract, floor, abs, sin, cos, max, min,
        length, normalize, pow, exp, hash, atan, fwidth, dot, mrt } = T;
    const BGU = await import('npm:three@0.184.0/addons/utils/BufferGeometryUtils.js');
    const { RoundedBoxGeometry } = await import('npm:three@0.184.0/addons/geometries/RoundedBoxGeometry.js');
    const CSG = await import('three-bvh-csg');
    const N = await L.napi();
    const singerScale = opts.singerScale ?? SUIT_SCALE;
    const faceY = 1.53 * singerScale;

    const group = new T.Group(); group.name = 'set:showroom';
    const disposables = [];
    const track = (x) => { disposables.push(x); return x; };

    const uT = uniform(0), uSeq = uniform(0.997), uLights = uniform(1), uBeams = uniform(1), uScreen = uniform(0.66);

    // the room's light: a black void, two softbox strips overhead, the LED wall behind (-Z), a faint grey floor bounce
    const ENV = track(L.equirectEnv(T, 512, 256, (x, y, z) => {
        let v = 0.006;
        const wall = (z < -0.55 && y > -0.08 && y < 0.42) ? Math.min(1, (-z - 0.55) * 5) * 0.75 : 0;
        const strip = (Math.exp(-Math.pow((y - 0.93) / 0.03, 2)) + Math.exp(-Math.pow((y - 0.80) / 0.025, 2)) * 0.7) * (Math.abs(x) < 0.85 ? 1 : 0);
        // the lit white stage below: chrome and lacquer pick up a bright floor bounce in their lower halves
        const floor = y < -0.02 ? (0.10 + 0.22 * Math.min(1, (-y - 0.02) * 4)) * (1 - 0.6 * Math.max(0, -y - 0.6)) : 0;
        // a tall soft bounce card out front (product photography): it is what makes chrome read as chrome in a void
        const card = z > 0.35 && Math.abs(x) < 0.75 ? Math.exp(-Math.pow((y - 0.12) / 0.28, 2)) * 0.32 * Math.min(1, (z - 0.35) * 3) : 0;
        const sides = Math.abs(x) > 0.8 ? Math.exp(-Math.pow((y - 0.3) / 0.25, 2)) * 0.07 : 0;
        v += wall + strip * 1.0 + floor + card + sides;
        return [v * 0.94, v * 0.97, v * 1.0];
    }));
    const K = L.materialKit(T, { env: ENV, prefix: 'ufsr', track });
    const { tri, keyed, envd, pbr, solid } = K;
    const S = {};
    for (const id of ['Terrazzo005', 'Terrazzo003', 'Carpet012', 'Fabric031', 'Metal009', 'Metal027']) S[id] = await L.acg(T, id);

    const add = (geo, mat, pos = [0, 0, 0], rot = [0, 0, 0], parent = group, o = {}) => {
        const m = new T.Mesh(geo, mat);
        m.position.set(...pos); m.rotation.set(...rot);
        m.castShadow = o.cast ?? true; m.receiveShadow = o.recv ?? true;
        if (o.keep) m.userData.keep = true;
        if (o.name) m.name = o.name;
        parent.add(m);
        return m;
    };
    const box = (w, h, d) => L.boxUV(new T.BoxGeometry(w, h, d), 1);
    const rbox = (w, h, d, seg = 2, r = 0.02) => L.boxUV(new RoundedBoxGeometry(w, h, d, seg, r), 1);
    const cyl = (r0, r1, h, seg = 24, open = false) => L.boxUV(new T.CylinderGeometry(r0, r1, h, seg, 1, open), 1);

    // ---------------------------------------------------------------------------------------- materials
    const stageMat = pbr('stage', S.Terrazzo005, { tint: [0.50, 0.52, 0.56], tile: 1 / 0.7, rough: 0.5, vary: 0.10, envI: 0.9 });
    const floorMat = (() => {        // auditorium carpet, darkening with distance from the stage
        const m = new T.MeshStandardNodeMaterial({ roughness: 1, metalness: 0 });
        const tuv = uv().mul(1 / 0.6);
        const pile = texture(S.Carpet012.map, tuv).rgb;
        const lum = pile.r.mul(0.3).add(pile.g.mul(0.59)).add(pile.b.mul(0.11));
        const fade = exp(max(positionLocal.z.sub(5.0), 0.0).mul(-0.11));
        m.colorNode = vec3(lum).mul(vec3(0.42, 0.44, 0.50)).mul(fade.mul(0.85).add(0.15));
        m.roughnessNode = float(0.95);
        m.normalNode = T.normalMap(texture(S.Carpet012.normalMap, tuv), vec2(0.8, 0.8));
        return keyed(envd(m, 0.2), 'aud-floor');
    })();
    const blackMat = solid('black', [0.012, 0.012, 0.014], { rough: 0.8, vary: 0.3, scale: 1.5, envI: 0.3 });
    const brushed = pbr('brushed', S.Metal009, { tint: [0.95, 0.96, 0.98], tile: 1 / 0.4, rough: 0.55, metal: 1, envI: 1.6 });
    const trussMat = pbr('truss', S.Metal009, { tint: [0.80, 0.82, 0.85], tile: 1 / 0.25, rough: 0.8, metal: 1, envI: 1.0 });
    const powder = pbr('powder', S.Metal027, { tint: [0.30, 0.31, 0.33], tile: 1 / 0.5, rough: 1.0, metal: 1, envI: 0.8 });
    const velvet = (() => {
        const m = new T.MeshPhysicalNodeMaterial({ roughness: 0.95, metalness: 0, sheen: 1.0, sheenRoughness: 0.45 });
        m.sheenColor = new T.Color(0.10, 0.10, 0.12);
        const n = tri(0.8);
        m.colorNode = vec3(0.010, 0.010, 0.012).mul(n.z.mul(0.6).add(0.7));
        return keyed(envd(m, 0.3), 'velvet');
    })();
    const plinthMat = (() => {       // white solid surface: soft sheen, faint scuffs low down
        const m = new T.MeshStandardNodeMaterial({ roughness: 0.4, metalness: 0 });
        const n = tri(3.0), n2 = tri(17.0);
        const scuff = smoothstep(0.25, 0.0, positionLocal.y.add(PLINTH.h / 2)).mul(n2.x);
        m.colorNode = vec3(0.86, 0.87, 0.88).mul(n.z.sub(0.5).mul(0.05).add(1)).mul(float(1).sub(scuff.mul(0.25)));
        m.roughnessNode = clamp(float(0.32).add(n.y.sub(0.5).mul(0.12)).add(n2.w.sub(0.5).mul(0.08)), 0.05, 1.0);
        return keyed(envd(m, 1.0), 'plinth');
    })();
    const chrome = (() => {          // toaster chrome: mirror with fingerprint and wipe smudges
        const m = new T.MeshPhysicalNodeMaterial({ metalness: 1, roughness: 0.06, clearcoat: 0.0 });
        const n = tri(14.0), n2 = tri(55.0);
        const smudge = smoothstep(0.55, 0.85, n.x).mul(0.6).add(smoothstep(0.62, 0.9, n2.y).mul(0.4));
        m.colorNode = vec3(0.93, 0.94, 0.96).mul(float(1).sub(smudge.mul(0.06)));
        m.roughnessNode = clamp(float(0.035).add(smudge.mul(0.16)), 0.02, 1.0);
        return keyed(envd(m, 2.2), 'chrome');
    })();
    const bakelite = solid('bakelite', [0.012, 0.011, 0.011], { rough: 0.22, roughVar: 0.08, vary: 0.25, scale: 30, envI: 1.6 });
    const rubber = solid('rubber', [0.015, 0.015, 0.016], { rough: 0.75, roughVar: 0.1, vary: 0.2, scale: 20, envI: 0.5 });
    const slotMat = (() => {
        const m = new T.MeshStandardNodeMaterial({ metalness: 0.7, roughness: 0.6 });
        const wires = smoothstep(0.35, 0.5, abs(fract(positionLocal.y.div(0.0065)).sub(0.5)));
        m.colorNode = mix(vec3(0.012, 0.011, 0.01), vec3(0.18, 0.16, 0.14), wires);
        return keyed(envd(m, 0.8), 'toaster-slot');
    })();

    // ======================================================================================== VOID, STAGE, AUDITORIUM
    // an enclosing black box (inner faces) so the scene's sky never shows: the launch happens in a void
    {
        const vg = new T.BoxGeometry(44, 22, 46); vg.translate(0, 8, 8);
        const vm = new T.MeshBasicNodeMaterial({ side: T.BackSide });
        const n = tri(0.15);
        vm.colorNode = vec3(0.0035, 0.0038, 0.0045).mul(n.x.mul(0.8).add(0.6));
        keyed(vm, 'void');
        add(vg, vm, [0, 0, 0], [0, 0, 0], group, { cast: false, recv: false, keep: true });
    }
    const stageG = new T.Group(); stageG.name = 'sr:stage'; group.add(stageG);
    {
        const sw = 2 * STAGE.x, sd = STAGE.z1 - STAGE.z0;
        const top = new T.PlaneGeometry(sw, sd); top.rotateX(-Math.PI / 2); top.translate(0, STAGE.y, (STAGE.z0 + STAGE.z1) / 2);
        add(L.boxUV(top, 1), stageMat, [0, 0, 0], [0, 0, 0], stageG, { cast: false });
        // the stage's front fascia: matte black with a cold LED line under the nosing
        add(box(sw, STAGE.y - FLOOR_Y, 0.04), blackMat, [0, (STAGE.y + FLOOR_Y) / 2, STAGE.z1 + 0.02], [0, 0, 0], stageG);
        add(box(sw + 0.02, 0.03, 0.06), brushed, [0, STAGE.y - 0.015, STAGE.z1 + 0.01], [0, 0, 0], stageG);
        const ledM = new T.MeshBasicNodeMaterial();
        ledM.colorNode = vec3(0.85, 0.93, 1.0).mul(uLights.mul(3.0).add(0.05));
        keyed(ledM, 'stage-led');
        add(box(sw, 0.012, 0.012), ledM, [0, STAGE.y - 0.045, STAGE.z1 + 0.045], [0, 0, 0], stageG, { cast: false, keep: true });
        // auditorium floor and the risers the seats stand on
        const af = new T.PlaneGeometry(2 * STAGE.x + 2, 22); af.rotateX(-Math.PI / 2); af.translate(0, FLOOR_Y, STAGE.z1 + 11);
        add(L.boxUV(af, 1), floorMat, [0, 0, 0], [0, 0, 0], stageG, { cast: false });
        for (let k = 1; k < ROWS; k++) {
            const z0 = ROW0 + k * ROWP - 0.55, zz = 22.5 - z0;
            add(box(2 * STAGE.x, RISE, zz), floorMat, [0, FLOOR_Y + (k - 0.5) * RISE, z0 + zz / 2], [0, 0, 0], stageG, { cast: false });
        }
        // black masking: velvet legs at the sides, a border above the wall, the wall's own black frame
        const drape = (w, h, folds) => {
            const g = new T.PlaneGeometry(w, h, Math.round(w * 12), 1);
            const p = g.attributes.position;
            for (let i = 0; i < p.count; i++) { const x = p.getX(i); p.setZ(i, 0.09 * Math.sin(x / w * Math.PI * 2 * folds) + 0.03 * Math.sin(x / w * Math.PI * 2 * folds * 2.7)); }
            g.computeVertexNormals();
            return g;
        };
        for (const sx of [-1, 1]) {
            add(drape(3.2, 9.0, 5), velvet, [sx * (STAGE.x - 0.3), STAGE.y + 4.5, STAGE.z0 + 1.8], [0, sx * Math.PI / 2, 0], stageG, { keep: true });
            add(drape(2.4, 9.0, 4), velvet, [sx * (SCR.w / 2 + 1.4), STAGE.y + 4.5, SCR.z - 0.2], [0, 0, 0], stageG, { keep: true });
        }
        add(drape(SCR.w + 4, 1.5, 9), velvet, [0, SCR.y0 + SCR.h + 0.9, SCR.z + 0.05], [0, 0, 0], stageG, { keep: true });
        const fr = 0.14;
        add(box(SCR.w + 2 * fr, fr, 0.2), blackMat, [0, SCR.y0 + SCR.h + fr / 2, SCR.z - 0.05], [0, 0, 0], stageG);
        add(box(SCR.w + 2 * fr, fr, 0.2), blackMat, [0, SCR.y0 - fr / 2, SCR.z - 0.05], [0, 0, 0], stageG);
        add(box(fr, SCR.h, 0.2), blackMat, [-SCR.w / 2 - fr / 2, SCR.y0 + SCR.h / 2, SCR.z - 0.05], [0, 0, 0], stageG);
        add(box(fr, SCR.h, 0.2), blackMat, [SCR.w / 2 + fr / 2, SCR.y0 + SCR.h / 2, SCR.z - 0.05], [0, 0, 0], stageG);
        add(box(SCR.w, SCR.y0 - STAGE.y, 0.3), blackMat, [0, (SCR.y0 + STAGE.y) / 2, SCR.z - 0.1], [0, 0, 0], stageG);
    }

    // ======================================================================================== THE LED WALL
    const screenG = new T.Group(); screenG.name = 'sr:screen'; group.add(screenG);
    const sheetTex = (() => {
        const [c, x] = L.canvas(N, SCREEN.W, SCREEN.H);
        drawEngineSheet(x, c.width, c.height);
        return track(L.canvasTexture(T, c));
    })();
    const screenMat = (() => {
        const m = new T.MeshBasicNodeMaterial();
        m.colorNode = Fn(() => {
            const p = uv();
            const col = texture(sheetTex, p).rgb.toVar();
            // SEQUENCE COMPLETION: the bar fills to uSeq, with a slow scan inside the filled part
            const cy = float(1).sub(p.y);
            const inX = step(SEQBAR.x0 + 0.002, p.x).mul(step(p.x, mix(float(SEQBAR.x0 + 0.002), float(SEQBAR.x1 - 0.002), uSeq)));
            const inY = step(SEQBAR.y0 + 0.006, cy).mul(step(cy, SEQBAR.y1 - 0.006));
            const scan = smoothstep(0.0, 0.08, fract(p.x.mul(40.0).sub(uT.mul(0.6)))).mul(0.25).add(0.75);
            col.assign(mix(col, vec3(0.08, 0.12, 0.2).mul(scan), inX.mul(inY)));
            // LED pixels: an RGB-dot grid that only appears when the wall is close enough to resolve it
            const px = p.mul(vec2(SCREEN.W, SCREEN.H));
            const cell = fract(px);
            const dotm = smoothstep(0.48, 0.30, length(cell.sub(0.5)));
            const resolve = smoothstep(0.7, 0.3, fwidth(px.x));
            const led = mix(float(1.0), dotm.mul(1.6).add(0.08), resolve);
            return col.mul(led).mul(uScreen);
        })();
        return keyed(m, 'ledwall');
    })();
    const wall = add(new T.PlaneGeometry(SCR.w, SCR.h), screenMat, [0, SCR.y0 + SCR.h / 2, SCR.z], [0, 0, 0], screenG, { cast: false, recv: false, keep: true });
    wall.name = 'ledwall';

    // ======================================================================================== THE TURNTABLE
    const ttG = new T.Group(); ttG.name = 'sr:turntable'; group.add(ttG);
    const platter = new T.Group(); platter.name = 'turntable.platter'; ttG.add(platter);
    {
        // static base: brushed steel drum with a cold LED line where it meets the stage
        add(cyl(TT.r - 0.04, TT.r - 0.02, -STAGE.y - 0.03, 96, true), brushed, [0, (STAGE.y - 0.03) / 2, 0], [0, 0, 0], ttG);
        const baseLed = new T.MeshBasicNodeMaterial();
        baseLed.colorNode = vec3(0.8, 0.9, 1.0).mul(uLights.mul(2.4).add(0.04));
        keyed(baseLed, 'tt-baseled');
        add(new T.CylinderGeometry(TT.r - 0.015, TT.r - 0.015, 0.01, 128, 1, true), baseLed, [0, STAGE.y + 0.012, 0], [0, 0, 0], ttG, { cast: false, keep: true });
        // the platter top: white lacquer printed with rings, degree ticks and a tape X at the mark
        const [pc, px] = L.canvas(N, 2048, 2048);
        {
            const W = 2048, c = W / 2, R = W / 2 - 4;
            px.fillStyle = '#eef0f2'; px.fillRect(0, 0, W, W);
            px.strokeStyle = 'rgba(70,80,96,0.18)';
            for (let rr = 0.1; rr < 1.0; rr += 0.0333) { px.lineWidth = rr > 0.66 ? 2 : 1.2; px.beginPath(); px.arc(c, c, R * rr, 0, Math.PI * 2); px.stroke(); }
            px.fillStyle = '#3b4656';
            for (let d = 0; d < 360; d += 5) {
                const a = d * Math.PI / 180, long = d % 30 === 0;
                const r0 = R * (long ? 0.86 : 0.91), r1 = R * 0.965;
                px.save(); px.translate(c, c); px.rotate(a);
                px.fillRect(r0, -(long ? 4 : 2), r1 - r0, long ? 8 : 4);
                if (long) { px.translate(R * 0.79, 0); px.rotate(Math.PI / 2); px.font = '46px "UF Michroma"'; px.textAlign = 'center'; px.fillText(String(d), 0, 16); }
                px.restore();
            }
            px.strokeStyle = 'rgba(59,70,86,0.5)'; px.lineWidth = 6; px.beginPath(); px.arc(c, c, R * 0.98, 0, Math.PI * 2); px.stroke();
            // gaffer-tape X (matte blue-grey) and the mark's label
            px.save(); px.translate(c, c);
            for (const a of [0.785, -0.785]) { px.save(); px.rotate(a); px.fillStyle = '#5d7088'; px.fillRect(-150, -22, 300, 44); px.fillStyle = 'rgba(255,255,255,0.08)'; for (let i = 0; i < 30; i++) px.fillRect(-150 + i * 10, -22, 2, 44); px.restore(); }
            px.fillStyle = '#3b4656'; px.font = '40px "UF Mono"'; px.textAlign = 'center'; px.fillText('UNIT 01', 0, 230);
            px.restore();
        }
        const ptex = track(L.canvasTexture(T, pc));
        const prough = track(L.derivedTexture(T, pc, (R, G, B) => {
            const sat = (Math.max(R, G, B) - Math.min(R, G, B)) / 255, lum = (R + G + B) / 765;
            const v = 0.12 + (lum < 0.6 ? 0.25 : 0) + (sat > 0.1 && lum < 0.6 ? 0.5 : 0);
            const q = Math.round(L.clamp01(v) * 255); return [q, q, q];
        }));
        const topM = new T.MeshPhysicalNodeMaterial({ metalness: 0, roughness: 0.2, clearcoat: 1.0, clearcoatRoughness: 0.05 });
        const tuv = vec2(positionLocal.x.div(2 * TT.r).add(0.5), positionLocal.z.negate().div(2 * TT.r).add(0.5));
        const n = tri(4.0);
        topM.colorNode = texture(ptex, tuv).rgb.mul(n.z.sub(0.5).mul(0.04).add(1));
        topM.roughnessNode = clamp(texture(prough, tuv).r.add(n.y.sub(0.5).mul(0.06)), 0.04, 1.0);
        keyed(envd(topM, 1.4), 'tt-top');
        add(new T.CylinderGeometry(TT.r, TT.r, 0.03, 128), topM, [0, -0.015, 0], [0, 0, 0], platter, { keep: true });
        // the platter's polished rim and its running LED dashes (they show the turn)
        add(new T.CylinderGeometry(TT.r + 0.006, TT.r + 0.006, 0.034, 128, 1, true), chrome, [0, -0.015, 0], [0, 0, 0], platter, { keep: true });
        const rimLed = new T.MeshBasicNodeMaterial();
        rimLed.colorNode = Fn(() => {
            const a = atan(positionLocal.z, positionLocal.x);
            const dash = step(0.35, fract(a.mul(36.0 / (2 * Math.PI))));
            return vec3(0.85, 0.93, 1.0).mul(dash.mul(2.6).add(0.15)).mul(uLights.mul(0.9).add(0.1));
        })();
        keyed(rimLed, 'tt-rimled');
        add(new T.CylinderGeometry(TT.r + 0.008, TT.r + 0.008, 0.006, 192, 1, true), rimLed, [0, -0.026, 0], [0, 0, 0], platter, { cast: false, keep: true });
    }

    // ======================================================================================== THE TOASTER ON ITS PLINTH
    const toasterG = new T.Group(); toasterG.name = 'sr:toaster'; group.add(toasterG);
    toasterG.position.set(PLINTH.x, STAGE.y, PLINTH.z);
    {
        add(rbox(PLINTH.w, PLINTH.h, PLINTH.w, 3, 0.012), plinthMat, [0, PLINTH.h / 2, 0], [0, 0, 0], toasterG);
        // the WARNING placard on the plinth's audience face
        const [wc, wx] = L.canvas(N, 920, 1240); drawWarning(wx, 920, 1240);
        const wt = track(L.canvasTexture(T, wc));
        const wm = new T.MeshStandardNodeMaterial({ roughness: 0.45, metalness: 0 });
        const n = tri(40.0);
        wm.colorNode = texture(wt, uv()).rgb.mul(n.x.mul(0.06).add(0.96));
        wm.roughnessNode = clamp(float(0.42).add(n.y.sub(0.5).mul(0.1)), 0.2, 1.0);
        keyed(envd(wm, 0.6), 'warning');
        add(box(0.47, 0.632, 0.006), blackMat, [0, PLINTH.h * 0.56, PLINTH.w / 2 + 0.003], [0, 0, 0], toasterG);
        add(new T.PlaneGeometry(0.46, 0.62), wm, [0, PLINTH.h * 0.56, PLINTH.w / 2 + 0.0065], [0, 0, 0], toasterG, { keep: true, cast: false });
    }
    // the toaster: a chrome loaf with two real slots (CSG), bakelite lever and knob, feet, toast, and a cord to nowhere
    const toaster = new T.Group(); toaster.name = 'toaster';
    toaster.position.set(0, PLINTH.h, 0); toaster.rotation.y = -0.5; toasterG.add(toaster);
    {
        const Lx = 0.29, Hy = 0.205, Dz = 0.19, bev = 0.024, bevT = 0.03;
        const sh = new T.Shape();
        const w = Lx - 2 * bev, h = Hy - 2 * bev - 0.012, rt = 0.055, rb = 0.012;
        sh.moveTo(-w / 2 + rb, 0); sh.lineTo(w / 2 - rb, 0); sh.quadraticCurveTo(w / 2, 0, w / 2, rb);
        sh.lineTo(w / 2, h - rt); sh.quadraticCurveTo(w / 2, h, w / 2 - rt, h);
        sh.lineTo(-w / 2 + rt, h); sh.quadraticCurveTo(-w / 2, h, -w / 2, h - rt);
        sh.lineTo(-w / 2, rb); sh.quadraticCurveTo(-w / 2, 0, -w / 2 + rb, 0);
        let body = new T.ExtrudeGeometry(sh, { depth: Dz - 2 * bevT, bevelEnabled: true, bevelSize: bev, bevelThickness: bevT, bevelSegments: 7, curveSegments: 16 });
        body.translate(0, bev + 0.012, -(Dz - 2 * bevT) / 2);
        body.deleteAttribute('uv'); body.deleteAttribute('normal');
        body = BGU.mergeVertices(body, 1e-5);
        body.computeVertexNormals();
        body.clearGroups();
        // the two slots (one cutter: both boxes merged)
        const slotL = 0.14, slotW = 0.03, slotD = 0.11;
        const c1 = new T.BoxGeometry(slotL, slotD + 0.05, slotW).toNonIndexed(); c1.translate(-0.012, Hy - slotD / 2 + 0.02, 0.043);
        const c2 = new T.BoxGeometry(slotL, slotD + 0.05, slotW).toNonIndexed(); c2.translate(-0.012, Hy - slotD / 2 + 0.02, -0.043);
        for (const g of [c1, c2]) g.deleteAttribute('uv');
        let cutter = BGU.mergeGeometries([c1, c2], false);
        cutter = BGU.mergeVertices(cutter, 1e-6);
        const ev = new CSG.Evaluator(); ev.useGroups = true; ev.attributes = ['position', 'normal'];
        const A = new CSG.Brush(body, chrome); A.updateMatrixWorld();
        const B = new CSG.Brush(cutter, slotMat); B.updateMatrixWorld();
        let res = null;
        try { res = ev.evaluate(A, B, CSG.SUBTRACTION); } catch (e) { console.warn('[showroom] toaster CSG failed:', e.message); }
        const bodyMesh = res ? new T.Mesh(res.geometry, res.material) : new T.Mesh(body, chrome);
        bodyMesh.castShadow = bodyMesh.receiveShadow = true; bodyMesh.userData.keep = true; bodyMesh.name = 'toaster-body';
        toaster.add(bodyMesh);
        // slot floors (dark) so the slots read as deep
        for (const z of [0.043, -0.043]) add(box(slotL, 0.004, slotW), slotMat, [-0.012, Hy - slotD + 0.02, z], [0, 0, 0], toaster);
        // base plate + feet
        add(rbox(Lx - 0.02, 0.012, Dz - 0.025, 2, 0.004), bakelite, [0, 0.009, 0], [0, 0, 0], toaster);
        for (const [x, z] of [[-0.12, -0.07], [0.12, -0.07], [-0.12, 0.07], [0.12, 0.07]]) add(cyl(0.009, 0.008, 0.006, 16), rubber, [x, 0.003, z], [0, 0, 0], toaster);
        // lever (up: the toast has popped) in a dark track on the +X end, and the browning knob below it
        add(box(0.004, 0.11, 0.012), slotMat, [Lx / 2 + 0.0005, 0.12, 0], [0, 0, 0], toaster);
        add(rbox(0.045, 0.016, 0.034, 2, 0.006), bakelite, [Lx / 2 + 0.02, 0.165, 0], [0, 0, 0], toaster);
        add(cyl(0.018, 0.019, 0.016, 32), bakelite, [Lx / 2 + 0.007, 0.06, 0], [0, 0, Math.PI / 2], toaster);
        add(cyl(0.007, 0.007, 0.004, 24), chrome, [Lx / 2 + 0.0155, 0.06, 0], [0, 0, Math.PI / 2], toaster);
        add(box(0.002, 0.012, 0.003), chrome, [Lx / 2 + 0.0155, 0.068, 0], [0, 0, 0], toaster);
        const [dc, dx] = L.canvas(N, 256, 256); drawDial(dx, 256, 256);
        const dt = track(L.canvasTexture(T, dc));
        const dm = new T.MeshStandardNodeMaterial({ roughness: 0.4, metalness: 0.3, polygonOffset: true, polygonOffsetFactor: -2, polygonOffsetUnits: -2 });
        dm.colorNode = texture(dt, uv()).rgb; keyed(envd(dm, 1.0), 'dial');
        add(new T.PlaneGeometry(0.056, 0.056), dm, [Lx / 2 - 0.0005, 0.06, 0], [0, Math.PI / 2, 0], toaster, { keep: true, cast: false });
        // the rating plate on the audience side
        const [rc, rx] = L.canvas(N, 512, 180); drawRatingPlate(rx, 512, 180);
        const rt2 = track(L.canvasTexture(T, rc));
        const rm = new T.MeshStandardNodeMaterial({ roughness: 0.35, metalness: 0.6, polygonOffset: true, polygonOffsetFactor: -2, polygonOffsetUnits: -2 });
        rm.colorNode = texture(rt2, uv()).rgb; keyed(envd(rm, 1.2), 'ratingplate');
        add(new T.PlaneGeometry(0.06, 0.021), rm, [0.075, 0.045, Dz / 2 + 0.0004], [0, 0, 0], toaster, { keep: true, cast: false });
        // toast: golden slices standing up out of both slots
        const [bc, bx] = L.canvas(N, 512, 512);
        {
            const r = L.rng(99);
            bx.fillStyle = '#7a3f12'; bx.fillRect(0, 0, 512, 512);
            const g = bx.createRadialGradient(256, 300, 40, 256, 300, 300);
            g.addColorStop(0, '#d9a25b'); g.addColorStop(0.7, '#c27f37'); g.addColorStop(1, '#8a4a18');
            bx.fillStyle = g; bx.fillRect(28, 28, 456, 456);
            for (let i = 0; i < 1600; i++) { const x = 30 + r() * 452, y = 30 + r() * 452, rr = 1 + r() * 4; bx.fillStyle = `rgba(${90 + r() * 40},${45 + r() * 20},${15},${0.25 + r() * 0.4})`; bx.beginPath(); bx.ellipse(x, y, rr, rr * (0.5 + r()), r() * 3, 0, Math.PI * 2); bx.fill(); }
        }
        const bt = track(L.canvasTexture(T, bc));
        const bm = new T.MeshStandardNodeMaterial({ roughness: 0.9, metalness: 0 });
        bm.colorNode = texture(bt, uv()).rgb; keyed(envd(bm, 0.3), 'toast');
        const sl = new T.Shape();
        const bw = 0.118, bh = 0.118;
        sl.moveTo(-bw / 2, 0); sl.lineTo(bw / 2, 0); sl.lineTo(bw / 2, bh * 0.7);
        sl.bezierCurveTo(bw / 2 + 0.012, bh * 0.98, bw * 0.12, bh * 1.04, 0, bh * 0.92);
        sl.bezierCurveTo(-bw * 0.12, bh * 1.04, -bw / 2 - 0.012, bh * 0.98, -bw / 2, bh * 0.7);
        sl.lineTo(-bw / 2, 0);
        const slice = new T.ExtrudeGeometry(sl, { depth: 0.011, bevelEnabled: true, bevelSize: 0.002, bevelThickness: 0.002, bevelSegments: 2 });
        slice.translate(0, 0, -0.0055);
        { const p = slice.attributes.position, u = slice.attributes.uv; for (let i = 0; i < p.count; i++) u.setXY(i, (p.getX(i) + bw / 2 + 0.014) / (bw + 0.028), p.getY(i) / (bh * 1.06)); }
        for (const z of [0.043, -0.043]) add(slice.clone(), bm, [-0.012, Hy - 0.07, z], [0, 0, 0], toaster);
        // the cord: out of the back, across the plinth, over the edge, hanging; it is not plugged into anything
        const pts = [[-0.1, 0.02, -Dz / 2], [-0.12, 0.004, -Dz / 2 - 0.06], [-0.06, 0.004, -0.2], [0.05, 0.004, -0.255], [0.09, -0.02, -0.282], [0.10, -0.25, -0.285], [0.07, -0.48, -0.29]];
        const curve = new T.CatmullRomCurve3(pts.map(([x, y, z]) => new T.Vector3(x, y, z)));
        add(L.boxUV(new T.TubeGeometry(curve, 60, 0.0035, 8), 1), rubber, [0, 0, 0], [0, 0, 0], toaster);
        const plug = add(rbox(0.022, 0.03, 0.014, 2, 0.003), bakelite, [0.07, -0.5, -0.29], [0, 0, 0.1], toaster);
        for (const sx of [-1, 1]) add(box(0.0015, 0.016, 0.006), chrome, [0.07 + sx * 0.005 - 0.002, -0.522, -0.29], [0, 0, 0.1], toaster);
    }
    const toasterFocus = new T.Object3D(); toasterFocus.position.set(PLINTH.x, STAGE.y + PLINTH.h + 0.1, PLINTH.z); group.add(toasterFocus);

    // ======================================================================================== EMPTY SEATS
    const seatsG = new T.Group(); seatsG.name = 'sr:seats'; group.add(seatsG);
    const seatGeo = (() => {
        const fab = [], shell = [], metal = [];
        const put = (arr, g, pos, rot = [0, 0, 0]) => { g = L.clean(g); g.applyMatrix4(new T.Matrix4().compose(new T.Vector3(...pos), new T.Quaternion().setFromEuler(new T.Euler(...rot)), new T.Vector3(1, 1, 1))); arr.push(g); };
        // back (faces -Z, toward the stage), leaning back
        put(fab, new RoundedBoxGeometry(0.52, 0.6, 0.075, 2, 0.03), [0, 0.80, 0.22], [0.2, 0, 0]);
        put(shell, new RoundedBoxGeometry(0.52, 0.62, 0.03, 1, 0.01), [0, 0.80, 0.265], [0.2, 0, 0]);
        // the seat cushion FOLDED UP (nobody sits): near-vertical in front of the back
        put(fab, new RoundedBoxGeometry(0.48, 0.44, 0.075, 2, 0.03), [0, 0.62, 0.05], [-0.12, 0, 0]);
        put(shell, new RoundedBoxGeometry(0.46, 0.42, 0.02, 1, 0.008), [0, 0.62, 0.005], [-0.12, 0, 0]);
        // one standard + armrest per seat (at +x); the row's first standard comes from its own instance list
        put(metal, new T.BoxGeometry(0.045, 0.62, 0.42), [0.3, 0.31, 0.12]);
        put(shell, new RoundedBoxGeometry(0.065, 0.035, 0.46, 1, 0.012), [0.3, 0.64, 0.1]);
        const m = (a) => L.boxUV(BGU.mergeGeometries(a, false), 1);
        return { fab: m(fab), shell: m(shell), metal: m(metal) };
    })();
    const seatFabric = (() => {
        const m = new T.MeshStandardNodeMaterial({ roughness: 1, metalness: 0 });
        const tuv = uv().mul(1 / 0.18);
        const fade = exp(max(positionLocal.z.sub(5.0), 0.0).mul(-0.13));
        const n = tri(1.5);
        m.colorNode = texture(S.Fabric031.map, tuv).rgb.mul(vec3(0.13, 0.135, 0.16)).mul(n.z.sub(0.5).mul(0.3).add(1)).mul(fade.mul(0.9).add(0.1));
        m.roughnessNode = float(0.95);
        m.normalNode = T.normalMap(texture(S.Fabric031.normalMap, tuv), vec2(1.2, 1.2));
        return keyed(envd(m, 0.25), 'seat-fabric');
    })();
    const seatShell = (() => {
        const m = new T.MeshStandardNodeMaterial({ roughness: 0.5, metalness: 0 });
        const n = tri(5.0);
        const fade = exp(max(positionLocal.z.sub(5.0), 0.0).mul(-0.13));
        m.colorNode = vec3(0.03, 0.031, 0.034).mul(n.z.sub(0.5).mul(0.4).add(1)).mul(fade.mul(0.9).add(0.1));
        m.roughnessNode = clamp(float(0.42).add(n.y.sub(0.5).mul(0.2)), 0.1, 1.0);
        return keyed(envd(m, 0.7), 'seat-shell');
    })();
    const seatMetal = (() => {
        const m = new T.MeshStandardNodeMaterial({ roughness: 0.6, metalness: 1 });
        const n = tri(6.0);
        const fade = exp(max(positionLocal.z.sub(5.0), 0.0).mul(-0.13));
        m.colorNode = vec3(0.10, 0.10, 0.11).mul(n.z.sub(0.5).mul(0.4).add(1)).mul(fade.mul(0.9).add(0.1));
        m.roughnessNode = clamp(float(0.55).add(n.y.sub(0.5).mul(0.3)), 0.1, 1.0);
        return keyed(envd(m, 0.8), 'seat-metal');
    })();
    const seatPos = [], endPos = [];
    for (let k = 0; k < ROWS; k++) {
        const z = ROW0 + k * ROWP, y = FLOOR_Y + k * RISE;
        for (const sx of [-1, 1]) {
            for (let i = 0; i < 10; i++) seatPos.push([sx * (0.9 + i * SEATP), y, z]);
            endPos.push([sx * (0.9 - SEATP), y, z]);
        }
    }
    {
        const m4 = new T.Matrix4();
        for (const [k, mat] of [['fab', seatFabric], ['shell', seatShell], ['metal', seatMetal]]) {
            const im = new T.InstancedMesh(seatGeo[k], mat, seatPos.length);
            seatPos.forEach(([x, y, z], i) => { m4.makeTranslation(x, y, z); im.setMatrixAt(i, m4); });
            im.instanceMatrix.needsUpdate = true; im.castShadow = true; im.receiveShadow = true; im.name = 'seats:' + k;
            seatsG.add(im);
        }
        const sg = L.clean(new T.BoxGeometry(0.045, 0.62, 0.42)); sg.translate(0.3, 0.31, 0.12);
        const im = new T.InstancedMesh(L.boxUV(sg, 1), seatMetal, endPos.length);
        endPos.forEach(([x, y, z], i) => { m4.makeTranslation(x, y, z); im.setMatrixAt(i, m4); });
        im.instanceMatrix.needsUpdate = true; im.name = 'seats:ends';
        seatsG.add(im);
    }
    // EXIT signs at the back corners: the only lights out there
    {
        const [ec, ex] = L.canvas(N, 256, 96);
        ex.fillStyle = '#021a0c'; ex.fillRect(0, 0, 256, 96); ex.fillStyle = '#fff'; ex.font = 'bold 66px "UF Rajdhani"'; ex.textAlign = 'center'; ex.fillText('EXIT', 128, 72);
        const et = track(L.canvasTexture(T, ec));
        const em = new T.MeshBasicNodeMaterial(); em.colorNode = texture(et, uv()).rgb.mul(vec3(0.25, 2.2, 0.8)); keyed(em, 'exit');
        for (const sx of [-1, 1]) add(new T.PlaneGeometry(0.42, 0.16), em, [sx * 8.2, FLOOR_Y + ROWS * RISE + 2.4, 21.9], [0, Math.PI, 0], group, { keep: true, cast: false });
    }

    // ======================================================================================== TRUSS, FIXTURES, BEAMS
    const rigG = new T.Group(); rigG.name = 'sr:rig'; group.add(rigG);
    {
        const S2 = 0.30;      // box truss section
        const lace = [];
        const chord = (x0, x1, y, z) => {
            for (const [dy, dz] of [[-S2 / 2, -S2 / 2], [-S2 / 2, S2 / 2], [S2 / 2, -S2 / 2], [S2 / 2, S2 / 2]]) {
                const g = new T.CylinderGeometry(0.024, 0.024, x1 - x0, 10); g.rotateZ(Math.PI / 2); g.translate((x0 + x1) / 2, y + dy, z + dz); lace.push(L.clean(g));
            }
            const step = S2;
            for (let x = x0; x < x1 - 1e-3; x += step) {
                for (const [ay, az, by, bz] of [[-1, -1, 1, -1], [-1, 1, 1, 1], [-1, -1, -1, 1], [1, -1, 1, 1]]) {
                    const a = new T.Vector3(x, y + ay * S2 / 2, z + az * S2 / 2), b = new T.Vector3(x + step, y + by * S2 / 2, z + bz * S2 / 2);
                    const len = a.distanceTo(b);
                    const g = new T.CylinderGeometry(0.011, 0.011, len, 6);
                    const q = new T.Quaternion().setFromUnitVectors(new T.Vector3(0, 1, 0), b.clone().sub(a).normalize());
                    g.applyQuaternion(q); g.translate((a.x + b.x) / 2, (a.y + b.y) / 2, (a.z + b.z) / 2);
                    lace.push(L.clean(g));
                }
            }
        };
        for (const z of TRUSS.zs) chord(-TRUSS.x, TRUSS.x, TRUSS.y, z);
        const tm = new T.Mesh(L.boxUV(BGU.mergeGeometries(lace, false), 1), trussMat); tm.name = 'truss'; tm.castShadow = false;
        rigG.add(tm);
        // hanging drop wires up into the dark
        for (const z of TRUSS.zs) for (const x of [-7, 0, 7]) add(cyl(0.004, 0.004, 6, 6), trussMat, [x, TRUSS.y + 3.15, z], [0, 0, 0], rigG, { cast: false });
    }
    // fixtures: black cans on yokes, lenses glowing; three of them throw visible beams through the haze
    const lensMat = new T.MeshBasicNodeMaterial();
    lensMat.colorNode = vec3(0.9, 0.95, 1.0).mul(uLights.mul(5.0).add(0.05));
    keyed(lensMat, 'lens');
    const fixtures = [];
    const fixture = (x, z, target, lit) => {
        const g = new T.Group(); g.position.set(x, TRUSS.y - 0.32, z); rigG.add(g);
        add(box(0.04, 0.22, 0.24), powder, [0, 0.06, 0], [0, 0, 0], g);
        const can = new T.Group(); g.add(can);
        add(cyl(0.12, 0.13, 0.38, 24), powder, [0, -0.08, 0], [0, 0, 0], can);
        add(cyl(0.11, 0.11, 0.01, 24), lit ? lensMat : blackMat, [0, -0.275, 0], [0, 0, 0], can, { cast: false, keep: !!lit });
        // aim the can (its -Y axis) at the target
        const dir = new T.Vector3(...target).sub(new T.Vector3(x, TRUSS.y - 0.32, z)).normalize();
        can.quaternion.setFromUnitVectors(new T.Vector3(0, -1, 0), dir);
        fixtures.push({ g, x, z, target, lit });
        return g;
    };
    fixture(-0.5, TRUSS.zs[0], [0, 0.9, 0], true);
    fixture(PLINTH.x + 0.2, TRUSS.zs[0], [PLINTH.x, PLINTH.h + STAGE.y + 0.1, PLINTH.z], true);
    fixture(2.2, TRUSS.zs[1], [0.3, 1.2, -0.2], true);
    for (const x of [-7.5, -5.5, 4.5, 6.5]) fixture(x, TRUSS.zs[0], [x * 0.5, 0, 1], false);
    for (const x of [-6, -2.5, 5.5]) fixture(x, TRUSS.zs[1], [x * 0.4, 0, -2], false);
    // visible beams: open cones, additive, bright on axis and fading at the silhouette (a cheap volumetric)
    const beamMat = (() => {
        const m = new T.MeshBasicNodeMaterial({ transparent: true, depthWrite: false, blending: T.AdditiveBlending, side: T.DoubleSide });
        const facing = abs(dot(normalView, positionViewDirection));
        const along = uv().y;                          // 1 at the source (cone tip), 0 at the base
        const n = tri(0.9);
        const a = pow(facing, 2.0).mul(mix(float(0.10), float(0.42), along)).mul(n.x.mul(0.5).add(0.75)).mul(uBeams).mul(uLights);
        m.colorNode = vec3(0.82, 0.9, 1.0).mul(a);
        m.opacityNode = a;
        return keyed(m, 'beam');
    })();
    const beams = [];
    for (const f of fixtures.filter((f) => f.lit)) {
        const a = new T.Vector3(f.x, TRUSS.y - 0.6, f.z), b = new T.Vector3(...f.target).setY(f.target[1] - 0.9);
        const len = a.distanceTo(b);
        const cg = new T.ConeGeometry(len * 0.17, len, 40, 1, true);
        cg.translate(0, -len / 2, 0);                  // tip at the origin, opening down -Y
        const m = add(cg, beamMat, [0, 0, 0], [0, 0, 0], rigG, { cast: false, recv: false, keep: true });
        m.position.copy(a);
        m.quaternion.setFromUnitVectors(new T.Vector3(0, -1, 0), b.clone().sub(a).normalize());
        m.renderOrder = 5;
        beams.push(m);
    }

    // ======================================================================================== LIGHTS
    const key = new T.DirectionalLight(0xeef4ff, 1.5);
    key.position.set(2.0, 11, 7.5); key.castShadow = true;
    key.shadow.mapSize.set(2048, 2048);
    Object.assign(key.shadow.camera, { left: -7, right: 7, top: 7, bottom: -7, near: 1, far: 40 });
    key.shadow.bias = -0.0004; key.shadow.normalBias = 0.02;
    const keyT = new T.Object3D(); keyT.position.set(-1.0, 0.5, 0); group.add(keyT); key.target = keyT; group.add(key);
    const rim = new T.DirectionalLight(0xd4e6ff, 2.2);
    rim.position.set(0.5, 4, -12); const rimT = new T.Object3D(); rimT.position.set(0, 1, 0); group.add(rimT); rim.target = rimT; group.add(rim);
    const toasterSpot = new T.SpotLight(0xf6f9ff, 26, 12, 0.11, 0.45, 1.4);
    toasterSpot.position.set(PLINTH.x + 0.2, TRUSS.y - 0.6, TRUSS.zs[0]);
    const tsT = new T.Object3D(); tsT.position.set(PLINTH.x, STAGE.y + PLINTH.h, PLINTH.z); group.add(tsT); toasterSpot.target = tsT;
    group.add(toasterSpot);
    const seatSpill = new T.SpotLight(0xdfe8ff, 22, 26, 0.75, 1.0, 1.6);
    seatSpill.position.set(0, 1.6, 3.2);
    const ssT = new T.Object3D(); ssT.position.set(0, -0.6, 12); group.add(ssT); seatSpill.target = ssT;
    group.add(seatSpill);
    // the product top light: straight down on the turntable, it gives her black techwear its shoulders from any angle
    const topSpot = new T.SpotLight(0xf2f7ff, 12, 12, 0.24, 0.55, 1.3);
    topSpot.position.set(0, TRUSS.y - 0.4, 0.4);
    const topT = new T.Object3D(); topT.position.set(0, 0, 0); group.add(topT); topSpot.target = topT;
    group.add(topSpot);
    const fill = new T.DirectionalLight(0x9fb8d8, 0.35);
    fill.position.set(-6, 3, 8); const fillT = new T.Object3D(); group.add(fillT); fill.target = fillT; group.add(fill);

    // ======================================================================================== MERGE STATIC
    for (const g of [stageG, rigG]) L.mergeStatic(T, BGU, g);
    L.mergeStatic(T, BGU, ttG);              // the platter group is kept whole (it turns)
    platter.userData.keep = true;
    toaster.userData.keep = true;
    L.mergeStatic(T, BGU, toasterG);
    L.mergeStatic(T, BGU, toaster);

    // ======================================================================================== SHADOW CASTERS
    // the key's shadow map only needs the toaster, its plinth and the turntable rim (the singer is the conductor's);
    // seats, rig, drapes and the stage only receive
    group.traverse((o) => { if (o.isMesh) { let k = false; for (let p = o; p; p = p.parent) if (p === toasterG) k = true; o.castShadow = k; } });

    // ======================================================================================== CAMS + UPDATE
    const focal = new T.Object3D(); focal.name = 'focal:singer'; focal.position.set(0, faceY, 0); group.add(focal);
    const cams = {
        reveal: { pos: [0.0, 1.3, 11.5], target: [0.0, 1.95, -3.0], fov: 40 },
        toaster: { pos: [-1.55, 1.05, 2.35], target: [PLINTH.x - 0.02, 0.62, PLINTH.z], fov: 36 },
        emptySeats: { pos: [0.95, 1.65, -1.15], target: [-0.6, -0.3, 11.0], fov: 50 },
        close: { pos: [0.05, faceY + 0.06, 2.05], target: [0.0, faceY - 0.04, 0.0], fov: 30 },
        wall: { pos: [3.2, 2.6, 3.5], target: [0.0, 2.9, SCR.z], fov: 40 },
    };
    function update(t, state = {}) {
        uT.value = t;
        platter.rotation.y = state.spin ?? 0;
        uSeq.value = L.clamp01(state.seq ?? 0.997);
        const lights = L.clamp01(state.lights ?? 1);
        uLights.value = lights;
        uBeams.value = L.clamp01(state.beams ?? 1);
        uScreen.value = 0.66 * (state.screen ?? 1);
        key.intensity = 1.5 * lights; rim.intensity = 2.2 * (0.4 + 0.6 * lights);
        toasterSpot.intensity = 26 * lights; seatSpill.intensity = 22 * lights; topSpot.intensity = 12 * lights;
    }
    update(0, {});
    function dispose() {
        group.parent?.remove(group);
        group.traverse((o) => { if (o.geometry) o.geometry.dispose(); });
        for (const d of disposables) d.dispose?.();
    }
    const parts = {
        turntable: { group: ttG, platter, setSpin: (a) => { platter.rotation.y = a; } },
        screen: { mesh: wall, uniforms: { seq: uSeq, brightness: uScreen } },
        toaster, plinth: toasterG, seats: seatsG, rig: rigG, beams, lights: { key, rim, toasterSpot, seatSpill, fill, top: topSpot },
        focal, toasterFocus, uniforms: { uT, uSeq, uLights, uBeams, uScreen },
    };
    return { group, parts, update, dispose, cams, mark: MARK, focal, env: ENV };
}
