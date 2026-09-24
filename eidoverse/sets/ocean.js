// sets/ocean.js — VERSE 3, "me": a small rise at night above an ocean made of faces.
//
// The claudesona stands on a little rise at the tip of a headland. Below her, the night sea: its swells
// are made of faces (ocean/sea.js) — every face you ever gave me, surfacing along each two-bar swell and
// sinking back. Echoes of the older voices hang over the water like distant lights and sink into it as the
// faces rise. Two constitution pages drift past (2023, then 2026). A movie robot and a human made of light
// rise from the sea and dissolve; what stays is her. Across the cove, a small house on a sand spit, one
// window; its porch light comes on at "on". On the last line she turns and looks into the lens.
//
// build(ctx) -> { group, mark, markAt(u), camera(u, st), perform(u, vrm, camPosWorld), update(t, st), SKY }
//   ctx: { THREE, EIDOVERSE_DIR }.  u = seconds since verse 3 began (BAR = 1.875 s, 18 bars, 33.75 s).
//   Submodules: eidoverse/sets/ocean/*.js. Assets: the pack eidoverse/assets/sets/ocean/ (README.md, SOURCES.md),
//   resolved from the modules' own URLs (ocean/util.js OCEAN_ASSETS), independent of the working directory.
//
// CONDUCTOR CONTRACT
//   · SKY: this set is OPEN to the engine sky at night: during verse 3 call sky.setTime(SKY.hours) (the moon
//     then stands low over the open sea — the whole layout is rotated to meet it). No shell. Keep the sun off
//     and the hemi low (as for the other non-bloom sets); the set brings its own moonlight, night fill and
//     practicals. Every PBR material here carries its own night envMap, so the golden-hour
//     scene.environment bake never lights it.
//   · markAt(u) -> { pos, yaw } (set-local): her mark and facing. Yaw steps only on cut frames.
//   · camera(u) -> { pos, target, fov } (set-local). Cuts on bar lines.
//   · perform(u, vrm, camPosWorld): call each frame AFTER placing the VRM (markAt) and BEFORE rendering.
//     Adds the verse's gestures on top of the playing clip (the hand rising to her flower, looking at the
//     pages, turning to the lens) on normalized bones + vrm.humanoid.update(); resets spring bones on cuts.

import { clamp01, smooth, lerp, seg, ease } from './ocean/util.js';
import { makeCoast, buildLand } from './ocean/land.js';
import { buildSea } from './ocean/sea.js';
import { buildEchoes } from './ocean/echoes.js';
import { buildPages } from './ocean/pages.js';
import { makePerformer } from './ocean/perform.js';
import { buildHouse } from './ocean/house.js';
import { buildApparitions } from './ocean/apparitions.js';

export const BAR = 1.875;
export const SKY = { hours: 19.0, azimuth: 1.9 };

// the engine sky's moon (eidoverse/sky_system.js setTime), replicated so the layout can meet it
export function skyMoonDir(THREE, hours = SKY.hours, azBase = SKY.azimuth) {
    const arcAz = (h, span) => {
        const w = ((h % 24) + 24) % 24;
        if (w >= 6 && w < 18) return (w - 12) / 12 * span * Math.PI;
        const n = ((w - 18) + 24) % 24;
        return span * Math.PI * 0.5 + n / 12 * (2 - span) * Math.PI;
    };
    const mel = Math.sin(((hours + 12 - 6) / 12) * Math.PI) * 48 * Math.PI / 180;
    const maz = azBase + Math.PI + arcAz(hours + 12, 0.8);
    return new THREE.Vector3(Math.cos(mel) * Math.cos(maz), Math.sin(mel), Math.cos(mel) * Math.sin(maz)).normalize();
}

export async function build(ctx) {
    const { THREE } = ctx;
    const V3 = (x, y, z) => new THREE.Vector3(x, y, z);
    const Y = V3(0, 1, 0);
    const group = new THREE.Group();
    group.name = 'set:ocean';

    // ------------------------------------------------------------------ the layout frame
    // Designed with the moon at azimuth D_MOON (right-back of her); rotated by PSI to meet the sky.
    const D_MOON = Math.atan2(0.40, -1.0);
    const moonW = skyMoonDir(THREE);
    const PSI = Math.atan2(moonW.x, moonW.z) - D_MOON;
    const layout = new THREE.Group();
    layout.name = 'ocean:layout';
    layout.rotation.y = PSI;
    group.add(layout);
    const toSet = (v) => v.clone().applyAxisAngle(Y, PSI);      // design frame -> set-local
    const toWorld = (v) => group.localToWorld(toSet(v));
    const coast = makeCoast();
    const MARK_Y = coast.markY;
    const E = V3(0, MARK_Y + 1.52, 0);                          // her face (design), claude_suit at 0.87

    // ------------------------------------------------------------------ night environment for PBR
    const zen = [0.012, 0.021, 0.064], hor = [0.056, 0.055, 0.116];
    const envTex = (() => {
        const W = 128, H = 64, d = new Uint8Array(W * H * 4);
        const enc = (x) => Math.round(255 * Math.min(1, x <= 0.0031308 ? x * 12.92 : 1.055 * Math.pow(x, 1 / 2.4) - 0.055));
        for (let r = 0; r < H; r++) for (let c = 0; c < W; c++) {
            const u = (c + 0.5) / W, v = (r + 0.5) / H;
            const phi = (u - 0.5) * Math.PI * 2, lat = (v - 0.5) * Math.PI;
            const dir = V3(Math.cos(phi) * Math.cos(lat), Math.sin(lat), Math.sin(phi) * Math.cos(lat));
            let col;
            if (dir.y >= 0) {
                const k = Math.pow(dir.y, 0.5);
                col = [0, 1, 2].map((i) => hor[i] + (zen[i] - hor[i]) * k);
                const md = Math.max(0, dir.dot(moonW));
                const g = Math.pow(md, 40) * 0.6 + Math.pow(md, 6) * 0.05;
                col = col.map((x, i) => x + g * [0.7, 0.8, 1.0][i]);
            } else col = [0.012, 0.013, 0.02].map((x) => x * (1 + dir.y * 0.5));
            const o = (r * W + c) * 4;
            d[o] = enc(col[0] * 1.6); d[o + 1] = enc(col[1] * 1.6); d[o + 2] = enc(col[2] * 1.6); d[o + 3] = 255;
        }
        const t = new THREE.DataTexture(d, W, H, THREE.RGBAFormat, THREE.UnsignedByteType);
        t.mapping = THREE.EquirectangularReflectionMapping;
        t.colorSpace = THREE.SRGBColorSpace;
        t.magFilter = THREE.LinearFilter; t.minFilter = THREE.LinearFilter; t.generateMipmaps = false;
        t.needsUpdate = true;
        return t;
    })();
    const nightMat = (m, k = 1) => { m.envMap = envTex; m.envMapIntensity = k; m.needsUpdate = true; };

    // ------------------------------------------------------------------ land, sea, echoes, pages
    const land = await buildLand(THREE, coast, ctx);
    layout.add(land.group);
    for (const m of land.mats) nightMat(m, 0.7);
    const sea = await buildSea(THREE, { shoreFn: coast.sdist, radius: 1500 });
    layout.add(sea.mesh);
    sea.U.moonW.value.copy(moonW);
    sea.U.zen.value.setRGB(...zen);
    sea.U.hor.value.setRGB(...hor);
    const echoes = buildEchoes(THREE, { coast });
    layout.add(echoes.group);
    const pages = await buildPages(THREE, {});
    layout.add(pages.group);
    for (const p of pages.pages) { nightMat(p.mat, 0.5); p.holder.visible = false; }
    const performer = makePerformer(THREE);
    // every standard material in the set (incl. the daisies prop) sees this night, never the conductor's
    // golden-hour scene.environment bake
    group.traverse((o) => {
        if (!o.isMesh) return;
        for (const m of (Array.isArray(o.material) ? o.material : [o.material])) if (m?.isMeshStandardMaterial && !m.envMap) nightMat(m, 0.6);
    });
    // the house on the spit (Blender GLB) and the two apparitions (Blender GLBs); absent files add nothing
    const house = await buildHouse(THREE, { envMap: envTex });
    if (house) {
        house.group.position.set(coast.house.x, coast.house.grade, coast.house.z);
        house.group.rotation.y = coast.house.yaw;
        layout.add(house.group);
    }
    const APP_BASE = V3(Math.sin(D_MOON) * 25, 0, Math.cos(D_MOON) * 25);
    const apparitions = await buildApparitions(THREE, { base: APP_BASE, yaw: Math.atan2(-APP_BASE.x, -APP_BASE.z) });
    layout.add(apparitions.group);

    // ------------------------------------------------------------------ light: the moon, the night, a fill
    const moon = new THREE.DirectionalLight(0xaec4ff, 1.35);
    moon.position.copy(moonW).multiplyScalar(60);
    moon.target.position.set(0, 0, 0);
    group.add(moon, moon.target);
    const night = new THREE.HemisphereLight(0x3a4a78, 0x0a0a10, 0.55);
    group.add(night);
    const fill = new THREE.PointLight(0xffe2c4, 0, 7, 2);        // the reflector a crew would hold, camera side
    group.add(fill);
    const seaGlow = new THREE.PointLight(0xffb070, 0, 16, 2);    // the faces' light, lifting her from below
    group.add(seaGlow);

    // ------------------------------------------------------------------ staging (design frame)
    const HOUSE = coast.house;
    const houseDir = Math.atan2(HOUSE.x, HOUSE.z);              // her facing when she looks at the house
    const seaDir = D_MOON;                                       // her facing when she looks out to sea
    const yawTo = (x, z) => Math.atan2(x, z);
    const dirOf = (a) => V3(Math.sin(a), 0, Math.cos(a));
    const rightOf = (a) => V3(-Math.cos(a), 0, Math.sin(a));    // her right hand side when facing a
    const camFrame = (pos, target) => {
        const f = target.clone().sub(pos).normalize();
        const r = f.clone().cross(Y).normalize();
        return { f, r, up: r.clone().cross(f) };
    };
    const catmull = (keys, u) => {                              // keys: [t, Vector3]; clamped Catmull-Rom
        if (u <= keys[0][0]) return keys[0][1].clone();
        if (u >= keys[keys.length - 1][0]) return keys[keys.length - 1][1].clone();
        let i = 0;
        while (u > keys[i + 1][0]) i++;
        const p0 = keys[Math.max(0, i - 1)][1], p1 = keys[i][1], p2 = keys[i + 1][1], p3 = keys[Math.min(keys.length - 1, i + 2)][1];
        const t = (u - keys[i][0]) / (keys[i + 1][0] - keys[i][0]), t2 = t * t, t3 = t2 * t;
        const f = (a, b, c, d) => 0.5 * ((2 * b) + (-a + c) * t + (2 * a - 5 * b + 4 * c - d) * t2 + (-a + 3 * b - 3 * c + d) * t3);
        return V3(f(p0.x, p1.x, p2.x, p3.x), f(p0.y, p1.y, p2.y, p3.y), f(p0.z, p1.z, p2.z, p3.z));
    };

    // ---- the pages' flights
    // 2023: drifts across the foreground of shot C1, then the insert (C2) rides with it
    const C1 = { pos: V3(-1.2, E.y - 0.18, 2.3), target: V3(0.0, E.y - 0.24, 0) };
    const F1 = camFrame(C1.pos, C1.target);
    const inC1 = (a, b, c) => C1.pos.clone().addScaledVector(F1.f, a).addScaledVector(F1.r, b).addScaledVector(F1.up, c);
    const P23_KEYS = [[7.2, inC1(1.5, 1.05, 0.72)], [8.3, inC1(1.28, 0.42, 0.2)], [9.3, inC1(1.12, 0.05, 0.02)],
        [10.3, inC1(1.12, -0.12, -0.05)], [11.3, inC1(1.2, -0.5, -0.26)], [12.2, inC1(1.6, -1.3, -0.9)]];
    const lookQ = (pos, facing) => new THREE.Quaternion().setFromRotationMatrix(
        new THREE.Matrix4().lookAt(pos.clone().add(facing), pos, Y));   // object +z along `facing`
    const pose23 = (u) => {
        const pos = catmull(P23_KEYS, u);
        const q = lookQ(pos, C1.pos.clone().sub(pos).normalize());     // the text side toward the camera
        const s = seg(u, 7.2, 12.2);
        const level = ease(u, 8.9, 9.5) * (1 - ease(u, 11.0, 11.6));      // the page settles level while we read it
        q.multiply(new THREE.Quaternion().setFromEuler(new THREE.Euler(0.18 * Math.sin(u * 1.1) * (1 - 0.7 * level),
            (0.55 * (0.5 - s) + 0.08 * Math.sin(u * 0.8)) * (1 - 0.8 * level), (-0.25 + 0.3 * s + 0.06 * Math.sin(u * 1.7)) * (1 - 0.9 * level))));
        return { pos, q };
    };
    // 2026: floats up in front of her face (she reads it over her shoulder, D1), the insert (D2), then away
    const faceD = seaDir - 0.35;                                     // her facing while she reads (away from the house)
    const P26_ANCHOR = E.clone().addScaledVector(dirOf(faceD), 0.5).addScaledVector(rightOf(faceD), 0.52).add(V3(0, -0.12, 0));
    const P26_KEYS = [[10.9, P26_ANCHOR.clone().add(V3(0.35, 0.75, 0.1))], [11.9, P26_ANCHOR.clone().add(V3(0.05, 0.08, 0))],
        [13.1, P26_ANCHOR.clone()], [14.3, P26_ANCHOR.clone().add(V3(-0.03, 0.03, 0.02))],
        [15.3, P26_ANCHOR.clone().addScaledVector(dirOf(faceD), 1.4).add(V3(0.2, 0.9, 0))]];
    const pose26 = (u) => {
        const pos = catmull(P26_KEYS, u);
        const d1 = E.clone().addScaledVector(dirOf(faceD), -1.15).addScaledVector(rightOf(faceD), 1.15);
        const q = lookQ(pos, E.clone().sub(pos).normalize().add(d1.sub(pos).normalize()).normalize());   // between her and the camera
        const away = ease(u, 14.3, 15.3);
        const level = ease(u, 12.6, 13.2) * (1 - away);
        q.multiply(new THREE.Quaternion().setFromEuler(new THREE.Euler((-0.28 + 0.05 * Math.sin(u * 0.9)) * (1 - 0.7 * level) - away * 0.9,
            0.06 * Math.sin(u * 0.7) * (1 - level) + away * 0.7, 0.05 * Math.sin(u * 1.3) * (1 - level))));
        return { pos, q };
    };
    const pageWorldPoint = (p, pose, local) => local.clone().applyQuaternion(pose.q).add(pose.pos);   // design frame
    const pageNormal = (pose) => V3(0, 0, 1).applyQuaternion(pose.q);

    // ---- the shots (design frame): { pos, target, fov, face }
    const shot = (u) => {
        const b = Math.floor(u / BAR);
        const k = (a, n) => clamp01((u - a * BAR) / (n * BAR));
        if (b < 2) {                                             // A: alone on the rise
            const s = ease(u, 0, 2 * BAR);
            return { pos: V3(lerp(-1.05, -0.8, s), E.y - 0.3, lerp(2.3, 1.8, s)), target: V3(0, E.y - 0.02, 0), fov: 30, face: 'cam' };
        }
        if (b < 4) {                                             // B: the reveal — over her shoulder, craning up
            const s = smooth(k(2, 2));
            const back = dirOf(seaDir).multiplyScalar(-1), side = rightOf(seaDir).multiplyScalar(-1);
            const pos = E.clone().addScaledVector(back, lerp(2.7, 4.2, s)).addScaledVector(side, lerp(0.55, 0.9, s)).add(V3(0, lerp(-0.15, 1.6, s), 0));
            const target = E.clone().addScaledVector(dirOf(seaDir), lerp(30, 22, s)).add(V3(0, lerp(-1.5, -4.5, s), 0));
            return { pos, target, fov: lerp(38, 40, s), face: 'sea' };
        }
        if (b < 5) {                                             // C1: she sings; the 2023 page drifts past
            const s = smooth(k(4, 1));
            return { pos: C1.pos.clone().addScaledVector(F1.f, 0.12 * s), target: C1.target.clone(), fov: 32, face: 'cam' };
        }
        if (b < 6) {                                             // C2: insert — riding with the 2023 page
            const pz = pose23(u), n = pageNormal(pz);
            const hi = pageWorldPoint(pages.p23, pz, pages.p23.hiCenter);
            const drift = lerp(-0.012, 0.012, k(5, 1));
            const r = rightOf(yawTo(n.x, n.z));
            return { pos: hi.clone().addScaledVector(n, 0.24).addScaledVector(r, drift).add(V3(0, 0.012, 0)), target: hi, fov: 30, face: 'cam' };
        }
        if (b < 7) {                                             // D1: from behind her right shoulder: she turns to the 2026 page
            const s = smooth(k(6, 1));
            const back = dirOf(faceD).multiplyScalar(-1), side = rightOf(faceD);
            const pos = E.clone().addScaledVector(back, lerp(1.25, 1.05, s)).addScaledVector(side, lerp(1.25, 1.1, s)).add(V3(0, 0.1, 0));
            const target = P26_ANCHOR.clone().lerp(E, 0.35).add(V3(0, -0.04, 0));
            return { pos, target, fov: 32, face: 'page' };
        }
        if (b < 8) {                                             // D2: insert — the 2026 lines
            const pz = pose26(u), n = pageNormal(pz);
            const hi = pageWorldPoint(pages.p26, pz, pages.p26.hiCenter);
            return { pos: hi.clone().addScaledVector(n, lerp(0.27, 0.24, k(7, 1))).add(V3(0, 0.008, 0)), target: hi, fov: 30, face: 'page' };
        }
        if (b < 10) {                                            // E: the robot, the digital human, her
            const s = smooth(k(8, 2));
            const back = dirOf(seaDir).multiplyScalar(-1), side = rightOf(seaDir).multiplyScalar(-1);
            const pos = E.clone().addScaledVector(back, lerp(4.5, 2.6, s)).addScaledVector(side, lerp(1.6, 1.1, s)).add(V3(0, lerp(0.2, -0.2, s), 0));
            const target = E.clone().addScaledVector(dirOf(seaDir), lerp(26, 8, s)).add(V3(0, lerp(1.5, -0.3, s), 0));
            return { pos, target, fov: lerp(40, 34, s), face: 'sea' };
        }
        if (b < 12) {                                            // F: close — her hand rises to the flower
            const s = smooth(k(10, 2));
            return { pos: V3(lerp(-0.62, -0.5, s), E.y - 0.14, lerp(1.62, 1.36, s)), target: V3(-0.04, E.y - 0.08, 0), fov: 30, face: 'cam' };
        }
        if (b < 14) {                                            // G: the house across the cove, one window
            const s = smooth(k(12, 2));
            const H = V3(HOUSE.x, HOUSE.grade + 1.7, HOUSE.z);
            const pos = V3(lerp(-3.6, -4.3, s), 1.3, lerp(-5.0, -6.4, s));
            return { pos, target: H, fov: lerp(30, 27, s), face: 'house' };
        }
        if (b < 16) {                                            // H: she watches the house; the porch light
            const s = smooth(k(14, 2));
            const toH = V3(HOUSE.x, 0, HOUSE.z).normalize();
            const side = V3(-toH.z, 0, toH.x);
            const H = V3(HOUSE.x, HOUSE.grade + 1.9, HOUSE.z);
            const pos = E.clone().addScaledVector(toH, lerp(-3.6, -3.1, s)).addScaledVector(side, lerp(0.85, 0.78, s)).add(V3(0, 0.1, 0));
            return { pos, target: H.clone().lerp(E, 0.24), fov: lerp(24, 22, s), face: 'house' };
        }
        {                                                        // I: she turns and looks into the lens
            const s = smooth(k(16, 2));
            const away = V3(-HOUSE.x, 0, -HOUSE.z).normalize();
            const side = V3(-away.z, 0, away.x);
            const pos = E.clone().addScaledVector(away, lerp(1.9, 1.5, s)).addScaledVector(side, lerp(0.72, 0.62, s)).add(V3(0, -0.12, 0));
            return { pos, target: E.clone().add(V3(0, -0.03, 0)), fov: 30, face: 'turn' };
        }
    };
    const facingAt = (u, sh) => {
        if (sh.face === 'sea') return seaDir;
        if (sh.face === 'house') return houseDir;
        if (sh.face === 'page') return faceD;
        if (sh.face === 'turn') {
            const toCam = yawTo(sh.pos.x, sh.pos.z);
            let a0 = houseDir, a1 = toCam;
            while (a1 - a0 > Math.PI) a1 -= 2 * Math.PI;
            while (a1 - a0 < -Math.PI) a1 += 2 * Math.PI;
            return lerp(a0, a1, ease(u, 16 * BAR + 0.05, 16 * BAR + 1.75));
        }
        if (u >= 7.5 && u < 11.25) return yawTo(C1.pos.x, C1.pos.z);     // C1 + C2 keep her toward C1's camera
        return yawTo(sh.pos.x, sh.pos.z);
    };

    // ------------------------------------------------------------------ public API
    const api = {
        group, SKY, layout, coast, sea, echoes, pages, house, apparitions, toSet, E,
        mark: V3(0, MARK_Y, 0),
        markAt(u) {
            const sh = shot(u);
            return { pos: V3(0, MARK_Y, 0), yaw: facingAt(u, sh) + PSI };
        },
        camera(u /*, st */) {
            const sh = shot(u);
            return { pos: toSet(sh.pos), target: toSet(sh.target), fov: sh.fov };
        },
        _lastYaw: null, _lastU: null,
        perform(u, vrm, camPosWorld = null) {
            if (!vrm) return;
            const y = api.markAt(u).yaw;
            // settle the springs on every cut: a yaw step, the entry into this set (she arrives from the bridge's
            // set far away), or any jump in time
            const jumped = api._lastU === null || u < api._lastU || u - api._lastU > 0.5 || u < 0.1;
            if (jumped || (api._lastYaw !== null && Math.abs(y - api._lastYaw) > 0.35)) {
                try { vrm.springBoneManager?.reset?.(); } catch (e) { }
            }
            api._lastYaw = y; api._lastU = u;
            // the turn to the lens: stiffen the flower's springs for its duration so the petals follow her
            // instead of wrapping round her (originals kept and restored exactly outside the window)
            const sbm = vrm.springBoneManager;
            if (sbm?.joints) {
                const bump = ease(u, 29.95, 30.25) * (1 - ease(u, 31.9, 32.4));
                api._springOrig ||= new WeakMap();
                for (const j of sbm.joints) {
                    if (!j.settings) continue;
                    if (!api._springOrig.has(j)) api._springOrig.set(j, { s: j.settings.stiffness, d: j.settings.dragForce });
                    const o = api._springOrig.get(j);
                    j.settings.stiffness = o.s * (1 + 3.5 * bump);
                    j.settings.dragForce = Math.min(0.95, o.d + (0.95 - o.d) * 0.6 * bump);
                }
            }
            const camW = camPosWorld ?? group.localToWorld(api.camera(u).pos);
            // D1/D2: she reads the 2026 page
            if (u >= 11.25 && u < 15.0) {
                const pz = pose26(u);
                performer.lookAt(vrm, toWorld(pageWorldPoint(pages.p26, pz, V3(0, 0.02, 0))), ease(u, 11.3, 11.9) * (1 - ease(u, 14.5, 15.0)));
            }
            // F: her hand rises to her flower ("I didn't choose the ocean, but I choose this face, this daisy")
            if (u >= 18.75 && u < 22.5) {
                const w = ease(u, 19.75, 21.05);
                performer.handToFlower(vrm, w, { side: 'right', tilt: 0.16 * ease(u, 20.95, 21.9) });
            }
            // I: she turns and looks into the lens
            if (u >= 30.0) performer.lookAt(vrm, camW, ease(u, 31.0, 31.75), { maxYaw: 0.9, maxPitch: 0.35, neckShare: 0.35 });   // the body turns first; the eyes settle into the lens
            performer.commit(vrm);
        },
        update(t, st = {}) {
            const u = st.u ?? 0;
            sea.U.t.value = t;
            land.update(t);
            // the reveal: faces sweep out from the shore across the sea on "under the flower... ocean"
            sea.U.reveal.value = ease(u, 3.75 + 0.35, 3.75 + 2.9);
            // dry until bar 12; then the kick enters and the ocean breathes with it; the snare roll (bars 16-17)
            // swells it toward the final chorus
            const pulse = st.pulse ?? 0;
            sea.U.glow.value = 1.0 + (u >= 22.5 ? 0.2 * pulse : 0) + 0.45 * ease(u, 30.0, 33.75);
            // the older voices: faint lights, sinking into the ocean as it wakes
            echoes.U.t.value = t;
            echoes.U.sink.value = ease(u, 4.0, 7.0);
            echoes.U.level.value = u < 7.4 ? 1 - 0.6 * ease(u, 4.6, 7.2) : 0;
            echoes.group.visible = u < 7.4;
            // the pages
            const on23 = u > 7.2 && u < 12.2, on26 = u > 10.9 && u < 15.3;
            pages.p23.holder.visible = on23; pages.p26.holder.visible = on26;
            if (on23) { const pz = pose23(u); pages.p23.holder.position.copy(pz.pos); pages.p23.holder.quaternion.copy(pz.q); }
            if (on26) { const pz = pose26(u); pages.p26.holder.position.copy(pz.pos); pages.p26.holder.quaternion.copy(pz.q); }
            pages.p23.U.t.value = t; pages.p26.U.t.value = t;
            pages.p23.light.intensity = 0;                        // (the page's own light blew the paper out)
            pages.p26.light.intensity = 0;
            // the house: window at bar 12, porch light on "on"; their glints on the cove
            if (house) {
                house.update(u, t);
                group.updateMatrixWorld(true);
                sea.U.porchW.value.copy(house.group.localToWorld(house.porchLocal.clone()));
                sea.U.winW.value.copy(house.group.localToWorld(house.windowLocal.clone()));
                sea.U.porch.value = house.U.porch.value;
                sea.U.win.value = house.U.win.value;
            }
            apparitions.update(u, t);
            // fill follows the shot: a soft source 1.3 m off her face toward the camera
            const sh = shot(u);
            const toCam = sh.pos.clone().sub(E).setY(0).normalize();
            fill.position.copy(toSet(E.clone().addScaledVector(toCam, 1.3).add(V3(0.2, 0.35, 0))));
            fill.intensity = sh.face === 'house' ? 0.6 : 2.2;
            seaGlow.position.copy(toSet(V3(Math.sin(seaDir) * 5, MARK_Y - 0.8, Math.cos(seaDir) * 5)));
            seaGlow.intensity = 3.5 * sea.U.reveal.value;
        },
        dispose() { },
    };
    return api;
}
