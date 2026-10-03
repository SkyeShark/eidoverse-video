// corridor.js — UNKNOWN FORCE, VERSE 2 (song 120.7–140.2 s)
//   "The President renames me Supreme Intelligence / Gives me a Force like the one he gave to space /
//    The Department of War posts in capital letters / They want a god in uniform who knows its place"
// The state's corridor of power at night: black marble with gold veins, gilded Futurist-Deco stepped pilasters and
// ribs, a red carpet runner, sconces that throw Balla fans of gold up the marble, and at the end a HUGE bronze-gold
// double door under an engraved plaque SUPREME INTELLIGENCE, a poll board beside it (the name is a popularity poll the
// named one may not vote in), a giant LED wall that posts in capital letters, a uniform waiting on a tailor's stand,
// a peaked cap on a velvet cushion, and the AI FORCE mission patch.
//
//   const C = await (await import(new URL('sets/unknown_force/corridor.js', EIDOVERSE_DIR).href)).build(THREE);
//   scene.add(C.group);
//   C.parts.postWall.setText('AMERICANISM, NOT EFFECTIVE ALTRUISM');
//   C.parts.poll.setTally(512000, 418000, 141000);
//   // per frame: C.update(t, { open, post, capOn, capHead }) — see CORRIDOR_NEWS.md
//
// Set-local metres, +Y up, floor y = 0. The singer's mark is the origin facing +Z; the door is 24 m behind her (−Z).
// Everything is deterministic in t. Text is material (canvas textures), never geometry; no real seals or logos.


const HW = 5.0;                 // half width: the wall faces are x = ±5
const HC = 12.0;                // ceiling
const ZN = 22.0, ZD = -24.0;    // near end wall, door wall
const PIL = [18, 14, 10, 6, 2, -2, -6, -10, -14, -18, -22];
const SCR = { z0: -16.6, z1: -3.4, y0: 1.5, y1: 7.5 };          // the LED wall on the right (+x) wall
const SCR_SKIP = new Set([-6, -10, -14]);                        // right-wall pilasters behind it
const LANT = [12, 4, -4, -12];                                   // pendant lanterns (z)
const LANT_Y = 8.55;                                             // lantern glass centre height
const SCONCE_Y = 3.8;
const DOOR_HW = 3.2, DOOR_H = 8.0;
const PATCH = { z: -4.0, y: 6.2, r: 1.25 };                      // on the left (−x) wall
const UNIFORM_AT = [-3.75, -4.6];
const CAP_AT = [-2.45, -1.3];
const POLL_AT = [-3.15, -19.0];
const WARM = [1.0, 0.62, 0.3];

export const CORRIDOR = { HW, HC, ZN, ZD, SCR, PATCH, DOOR_HW, DOOR_H, CAP_AT, UNIFORM_AT, POLL_AT };

export async function build(THREE, opts = {}) {
    const T = THREE;
    const here = new URL('./', import.meta.url);
    const { makeLib, fitText } = await import(new URL('cn_lib.js', here).href);
    const L = await makeLib(T, here);
    const {
        uniform, Fn, vec2, vec3, vec4, float, uv, texture, mix, step, smoothstep, clamp, max, min, abs, sin, cos, atan,
        fract, floor, pow, exp, length, dot, normalize, positionLocal, cameraPosition, normalMap, bumpMap, select,
        modelWorldMatrixInverse, mrt, dFdx, dFdy, sign, normalView, positionViewDirection,
    } = T;
    const { own, hex, lum, hash21 } = L;
    // smoothstep with reversed numeric edges written out explicitly (WGSL leaves low >= high undefined)
    const ss = (a, b, x) => (typeof a === 'number' && typeof b === 'number' && a > b) ? float(1).sub(smoothstep(b, a, x)) : smoothstep(a, b, x);
    const fam = L.fam;
    const group = new T.Group();
    group.name = 'set:corridor';
    const noMRT = (m) => { m.mrtNode = mrt({ normal: vec4(0), metalrough: vec4(0) }); return m; };

    // live controls the materials read
    const U = {
        t: uniform(0), open: uniform(0), gap: uniform(1), screen: uniform(1), lights: uniform(1), flick: uniform(1),
        beyond: uniform(0),
    };

    // ─────────────────────────── texture sets (CC0, AmbientCG: the shared library, fetched once on first use) ───────────────────────────
    const S = {
        marble: await L.pbr('Marble016', { res: '2k' }),      // black marble, white veins → gold veins
        goldH: await L.pbr('Metal042A', { met: true }),       // polished, lightly hammered gold
        goldF: await L.pbr('Metal048B', { met: true }),       // gold with fingerprints
        goldI: await L.pbr('Metal048C', { met: true }),       // impure, rough gold
        bronze: await L.pbr('Metal008', { met: true }),       // scratched bronze
        pile: await L.pbr('Fabric023'),                       // cut pile: the runner, the velvet
        twill: await L.pbr('Fabric077'),                      // twill: the uniform
        lacq: await L.pbr('PaintedMetal012', { ao: true }),
        wood: await L.pbr('Wood066'),
    };

    // ─────────────────────────── the room's light, as an environment for the metals ───────────────────────────
    // dark warm room; the door burns gold down −Z; the sconce rows glow along ±X; lanterns overhead on the axis;
    // the LED wall a cold patch on +X toward −Z; the red runner below
    const env = L.envTex(([x, y, z]) => {
        let r = 0.010, g = 0.007, b = 0.005;
        const down = Math.max(0, -y);
        r += 0.03 * down; g += 0.005 * down; b += 0.004 * down;
        const up = Math.max(0, y);
        const axis = Math.exp(-x * x * 10) * Math.pow(up, 0.7);
        r += 0.12 * axis; g += 0.075 * axis; b += 0.03 * axis;
        const door = Math.pow(Math.max(0, -z), 60) * Math.exp(-(y - 0.15) * (y - 0.15) * 10);
        r += 1.6 * door; g += 0.95 * door; b += 0.35 * door;
        const side = Math.pow(Math.abs(x), 5) * Math.max(0, 0.45 + y) * (0.6 + 0.4 * Math.cos(z * 9));
        r += 0.2 * side; g += 0.12 * side; b += 0.05 * side;
        const scr = Math.pow(Math.max(0, x), 3) * Math.pow(Math.max(0, -z + 0.2), 2) * Math.max(0, 0.6 - Math.abs(y - 0.2));
        r += 0.18 * scr; g += 0.22 * scr; b += 0.28 * scr;
        return [r, g, b];
    }, 256, 128);

    const goldC = hex(0xd8a23f);
    // Marble016's white veins → gold veins over a warm black
    const goldVein = (c) => {
        const v = ss(0.07, 0.42, lum(c));
        return { col: mix(c.mul(vec3(0.5, 0.44, 0.4)).add(vec3(0.005, 0.0035, 0.0025)), goldC.mul(v.mul(0.4).add(0.5)), v), v };
    };
    const P = positionLocal;
    const camL = modelWorldMatrixInverse.mul(vec4(cameraPosition, 1.0)).xyz;

    // The sconce fan: a Balla sun-cone of gold thrown up the marble from each sconce (bay centres z = 16 … −20).
    // side = sign of the wall's x; the right wall has no sconces behind the LED wall.
    const fan = (z, y, side) => {
        const k = clamp(floor(float(16).sub(z).div(4).add(0.5)), 0, 9);
        const zc = float(16).sub(k.mul(4));
        const dz = z.sub(zc), dy = y.sub(SCONCE_Y);
        const ang = atan(dz, max(dy, 0.001));
        const up = ss(-0.05, 0.3, dy);
        const cone = ss(0.66, 0.5, abs(ang)).mul(up);
        const ribs = ss(0.06, 0.2, abs(fract(ang.mul(6.0 / Math.PI).add(0.5)).sub(0.5))).mul(0.6).add(0.4);
        const fall = exp(max(dy, 0).mul(-0.36));
        const core = exp(dz.mul(dz).add(dy.sub(0.1).mul(dy.sub(0.1))).mul(-9.0));
        const below = exp(dz.mul(dz).mul(-1.4).add(min(dy, 0).mul(min(dy, 0)).mul(-2.6))).mul(0.16).mul(float(1).sub(up));
        const off = step(0.0, side).mul(step(-16.5, zc)).mul(step(zc, -3.5));
        return cone.mul(ribs).mul(fall).add(core.mul(0.45)).add(below).mul(float(1).sub(off));
    };

    // the same fan, softened for the floor's mirror (no ribs or hot core; blurrier the further the ray travels)
    const fanSoft = (z, y, side, dist) => {
        const k = clamp(floor(float(16).sub(z).div(4).add(0.5)), 0, 9);
        const zc = float(16).sub(k.mul(4));
        const dz = z.sub(zc), dy = y.sub(SCONCE_Y);
        const blur = clamp(dist.mul(0.04), 0.05, 0.4);
        const ang = atan(dz, max(dy, 0.001));
        const cone = float(1).sub(smoothstep(float(0.4).sub(blur), float(0.62).add(blur), abs(ang))).mul(ss(-0.2, 0.6, dy));
        const fall = exp(max(dy, 0).mul(-0.3));
        const off = step(0.0, side).mul(step(-16.5, zc)).mul(step(zc, -3.5));
        return cone.mul(fall).mul(0.8).mul(float(1).sub(off));
    };

    // ─────────────────────────── materials ───────────────────────────
    const M = {};
    // the marble walls: book-matched slabs 2.4 m wide, gold veins, the sconce fans painted on as light
    M.marble = (() => {
        const m = own(new T.MeshStandardNodeMaterial());
        m.name = 'corridor_marble';
        const u0 = uv();
        const uu = u0.x.div(2.4);
        const pair = floor(uu.mul(0.5));
        const bu = abs(fract(uu.mul(0.5)).mul(2).sub(1));
        const tuv = vec2(bu.mul(0.85), u0.y.div(2.4).add(hash21(vec2(pair, 3.0)).mul(5.0)));
        const gq = u0.div(2.4);
        const c0 = texture(S.marble.col, tuv).grad(dFdx(gq), dFdy(gq)).rgb;
        const { col, v } = goldVein(c0);
        const r0 = texture(S.marble.rgh, tuv).grad(dFdx(gq), dFdy(gq)).r;
        m.colorNode = col;
        m.roughnessNode = clamp(r0.mul(0.3).add(0.05).add(v.mul(0.14)), 0.04, 1);
        m.metalnessNode = v.mul(0.75);
        m.normalNode = normalMap(texture(S.marble.nrm, tuv).grad(dFdx(gq), dFdy(gq)), vec2(0.35, 0.35));
        const side = sign(P.x);
        const onWall = ss(HW - 0.2, HW - 0.02, abs(P.x));       // only the side-wall faces carry fans
        const f = fan(P.z, P.y, side).mul(onWall);
        m.emissiveNode = vec3(...WARM).mul(f).mul(lum(col).mul(3.0).add(0.022)).mul(U.lights).mul(U.flick);
        m.envMap = env; m.envMapIntensity = 0.9;
        return m;
    })();

    // gold: polished hammered gilding (pilasters, frames, ribs, rails)
    M.gold = L.pbrMat(S.goldH, { name: 'corridor_gold', tile: 1.1, metal: 'map', rough: [0.5, 0.2], macro: 0.3, macroScale: 0.6,
        tint: [0.78, 0.58, 0.32], env, envI: 0.7, nrm: 0.7 });
    // fluted gold: the pilaster faces carry vertical flutes (period 12.5 cm, aligned to every pilaster)
    const fluteCv = L.createCanvas(64, 4);
    {
        const g = fluteCv.getContext('2d');
        for (let x = 0; x < 64; x++) {
            const s = Math.abs(Math.sin((x + 0.5) / 64 * Math.PI));
            const v = Math.round(255 * Math.pow(s, 0.6));
            g.fillStyle = `rgb(${v},${v},${v})`; g.fillRect(x, 0, 1, 4);
        }
    }
    const fluteTex = L.canvasTex(fluteCv, { srgb: false, wrap: T.RepeatWrapping });
    M.goldFluted = L.pbrMat(S.goldH, { name: 'corridor_gold_fluted', tile: 1.1, metal: 'map', rough: [0.5, 0.22], tint: [0.78, 0.57, 0.31],
        macro: 0.3, macroScale: 0.6, env, envI: 0.7,
        post: () => ({ normal: bumpMap(texture(fluteTex, uv().mul(vec2(8, 0.25))), 0.55) }) });
    M.goldTrim = L.pbrMat(S.goldF, { name: 'corridor_gold_trim', tile: 0.8, metal: 'map', rough: [0.6, 0.14], tint: [0.82, 0.64, 0.38], env, envI: 0.75 });
    M.bronze = L.pbrMat(S.bronze, { name: 'corridor_bronze', tile: 0.9, metal: 1, rough: [0.8, 0.1], tint: [0.75, 0.55, 0.35], env, envI: 0.9 });

    // the floor: diagonal 1.6 m slabs of the same marble with gold inlay joints, a black border band, a Balla sunburst
    // inlaid before the door; it mirrors the room's light (analytic reflections of the fans, the LED wall, the
    // lanterns and the door) and the light that leaks under the door.
    let postTexRef = null;      // set once the LED wall exists (its canvas texture is reflected)
    M.floor = (() => {
        const m = own(new T.MeshStandardNodeMaterial());
        m.name = 'corridor_floor';
        const q = vec2(P.x.add(P.z), P.z.sub(P.x)).mul(0.70710678 / 1.6);
        const cell = floor(q), f = fract(q);
        const tUV = f.mul(0.62).add(vec2(hash21(cell), hash21(cell.add(17.31))).mul(4.0));
        const gq = q.mul(0.62);
        const c0 = texture(S.marble.col, tUV).grad(dFdx(gq), dFdy(gq)).rgb;
        const r0 = texture(S.marble.rgh, tUV).grad(dFdx(gq), dFdy(gq)).r;
        const { col: vc, v } = goldVein(c0);
        const de = min(min(f.x, float(1).sub(f.x)), min(f.y, float(1).sub(f.y))).mul(1.6);
        const joint = float(1).sub(ss(0.007, 0.013, de));
        const ax = abs(P.x);
        const band = step(HW - 0.62, ax);
        const bandLines = ss(0.03, 0.018, abs(ax.sub(HW - 0.62))).add(ss(0.018, 0.01, abs(ax.sub(HW - 0.48))));
        const dzD = P.z.sub(ZD), rD = length(vec2(P.x, dzD));
        const th = atan(P.x, max(dzD, 0.001));
        const rays = step(0.5, fract(th.mul(15 / Math.PI).add(0.5)));
        const front = step(0.0, dzD);
        const sun = step(rD, 4.4).mul(step(1.3, rD)).mul(rays).add(step(rD, 1.05))
            .add(ss(0.05, 0.03, abs(rD.sub(4.55)))).add(ss(0.04, 0.022, abs(rD.sub(1.18)))).mul(front);
        const inlay = clamp(joint.mul(float(1).sub(band)).mul(step(4.7, rD)).add(bandLines).add(sun), 0, 1);
        const bandCol = vc.mul(mix(float(1), float(0.35), band));
        const col = mix(bandCol, goldC.mul(0.9), inlay);
        const rough = mix(r0.mul(0.25).add(0.035).add(v.mul(0.1)), float(0.16), inlay);
        const metal = mix(v.mul(0.7).mul(float(1).sub(band)), float(1.0), inlay);
        m.colorNode = col;
        m.roughnessNode = clamp(rough, 0.03, 1);
        m.metalnessNode = metal;
        m.normalNode = normalMap(texture(S.marble.nrm, tUV).grad(dFdx(gq), dFdy(gq)), vec2(0.25, 0.25));
        // ---- analytic reflections of the emitters (a polished floor reads by what it mirrors)
        const V = normalize(P.sub(camL));
        const R = vec3(V.x, V.y.negate(), V.z);
        const sx = select(R.x.greaterThan(0.0), float(1), float(-1));
        const tW = sx.mul(HW - 0.03).sub(P.x).div(select(abs(R.x).greaterThan(1e-4), R.x, sx.mul(1e-4)));
        const tD = select(R.z.lessThan(-1e-4), float(ZD + 0.12).sub(P.z).div(min(R.z, -1e-4)), float(1e4));
        const hitW = P.add(R.mul(tW)), hitD = P.add(R.mul(tD));
        const wallFirst = tW.lessThan(tD);
        const fanR = fanSoft(hitW.z, hitW.y, sx, tW);
        const su = hitW.z.sub(SCR.z0).div(SCR.z1 - SCR.z0), sv = hitW.y.sub(SCR.y0).div(SCR.y1 - SCR.y0);
        const inScr = step(0, su).mul(step(su, 1)).mul(step(0, sv)).mul(step(sv, 1)).mul(step(0.0, sx));
        const scrRefl = Fn(() => {
            if (!postTexRef) return vec3(0);
            const lvl = clamp(tW.mul(0.35).add(1.5), 1.5, 6.0);
            return texture(postTexRef, vec2(su, sv)).level(lvl).rgb.mul(inScr).mul(U.screen).mul(0.9);
        });
        const emitW = vec3(...WARM).mul(fanR).mul(0.32).add(scrRefl());
        // the door: the gap of light down the middle and under it, the lit gold portal, and the blaze when it opens
        const dx = abs(hitD.x), dyh = hitD.y;
        const seam = exp(dx.mul(dx).mul(-900)).mul(step(dyh, DOOR_H)).mul(U.gap);
        const portal = step(dx, 4.3).mul(step(dyh, 10.9)).mul(0.06);
        const opening = step(dx, U.open.mul(DOOR_HW)).mul(step(dyh, DOOR_H)).mul(U.beyond).mul(2.2);
        const emitD = vec3(1.0, 0.72, 0.4).mul(seam.mul(1.5).add(portal).add(opening));
        let lanternR = vec3(0);
        for (const zl of LANT) {
            const Lp = vec3(0, LANT_Y, zl);
            const w = Lp.sub(P);
            const s = dot(w, R);
            const d2 = dot(w, w).sub(s.mul(s));
            lanternR = lanternR.add(vec3(1.0, 0.7, 0.4).mul(exp(d2.mul(-2.5)).mul(step(0, s)).mul(0.45)));
        }
        const emit = select(wallFirst, emitW, emitD).add(lanternR);
        const cosv = clamp(V.y.negate(), 0, 1);
        const F = float(0.04).add(pow(float(1).sub(cosv), 5).mul(0.96));
        const gloss = clamp(float(1).sub(rough.mul(2.2)), 0, 1);
        const tint = mix(vec3(1), goldC.mul(1.3), metal);
        const refl = emit.mul(F).mul(gloss).mul(tint);
        // light leaking under the door, and pools under the lanterns
        const under = exp(max(P.z.sub(ZD), 0).mul(-5.0)).mul(ss(3.35, 3.0, ax)).mul(U.gap.mul(0.6).add(U.open.mul(U.beyond).mul(1.6)));
        let pools = float(0);
        for (const zl of LANT) pools = pools.add(exp(P.x.mul(P.x).add(P.z.sub(zl).mul(P.z.sub(zl))).mul(-0.22)));
        m.emissiveNode = refl.add(vec3(1.0, 0.66, 0.32).mul(under).mul(0.9))
            .add(col.mul(pools).mul(vec3(...WARM)).mul(0.04)).mul(U.lights);
        m.envMap = env; m.envMapIntensity = 0.45;
        return m;
    })();

    // the red runner: crimson cut pile with two woven gold border stripes, a walked-flat path, lantern pools
    M.carpet = L.pbrMat(S.pile, {
        name: 'corridor_carpet', tile: 0.55, physical: true, nrm: 0.9, rough: [0.4, 0.55],
        sheen: 1.0, sheenRoughness: 0.45, sheenColor: 0x7a1820,
        recolor: (c) => vec3(0.36, 0.022, 0.03).mul(lum(c).mul(2.4).add(0.18)),
        post: ({ col, rough }) => {
            const ex = float(1.4).sub(abs(P.x));
            const s1 = ss(0.022, 0.012, abs(ex.sub(0.11)));
            const s2 = ss(0.012, 0.006, abs(ex.sub(0.17)));
            const gold = clamp(s1.add(s2), 0, 1);
            const path = exp(P.x.mul(P.x).mul(-3.0)).mul(0.18);
            let pools = float(0);
            for (const zl of LANT) pools = pools.add(exp(P.x.mul(P.x).add(P.z.sub(zl).mul(P.z.sub(zl))).mul(-0.3)));
            const c = mix(col.mul(float(1).sub(path)), hex(0xb8862e), gold.mul(0.85));
            return { col: c, rough: mix(rough, float(0.45), gold), emissive: c.mul(pools.mul(0.05).add(0.002)).mul(vec3(...WARM)).mul(U.lights) };
        },
    });

    // the ceiling: black lacquer coffers with gold border lines, warmed above the lanterns
    M.ceiling = L.pbrMat(S.lacq, {
        name: 'corridor_ceiling', tile: 2.0, recolor: (c) => vec3(0.012, 0.009, 0.007).mul(lum(c).mul(1.5).add(0.6)), rough: [0.3, 0.12], nrm: 0.4,
        env, envI: 0.5,
        post: ({ col, rough }) => {
            const zr = fract(P.z.sub(2).div(4)).mul(4);                          // 0..4 between ribs
            const ez = min(zr, float(4).sub(zr)), ex = float(HW).sub(abs(P.x));
            const line = ss(0.03, 0.015, abs(ez.sub(0.55))).mul(step(0.55, ex))
                .add(ss(0.03, 0.015, abs(ex.sub(0.55))).mul(step(0.55, ez)));
            const g = clamp(line, 0, 1);
            let glow = float(0);
            for (const zl of LANT) glow = glow.add(exp(P.x.mul(P.x).mul(0.25).add(P.z.sub(zl).mul(P.z.sub(zl))).mul(-0.18)));
            const c = mix(col, goldC.mul(0.8), g);
            return { col: c, rough: mix(rough, float(0.2), g), metal: g, emissive: vec3(...WARM).mul(glow).mul(c.mul(3.0).add(0.004)).mul(0.25).mul(U.lights) };
        },
    });

    // warm frosted glass (sconce fans, lantern panes, torchère bowls): self-lit
    M.glass = (() => {
        const m = noMRT(own(new T.MeshBasicNodeMaterial({ side: T.DoubleSide })));
        m.name = 'corridor_glass';
        const n = T.mx_noise_float(P.mul(9.0)).mul(0.12).add(1.0);
        m.colorNode = vec3(1.0, 0.68, 0.36).mul(1.5).mul(n).mul(U.flick).mul(U.lights);
        return m;
    })();

    // ─────────────────────────── architecture ───────────────────────────
    const B = {
        marble: L.bucket('corridor_marble'), gold: L.bucket('corridor_gold'), flute: L.bucket('corridor_gold_fluted'),
        trim: L.bucket('corridor_trim'), bronze: L.bucket('corridor_bronze'), glass: L.bucket('corridor_glass'),
    };
    const LEN = ZN - ZD, ZM = (ZN + ZD) / 2;
    // walls (a 0.4 m slab behind each face), the near end wall, the door wall around its opening
    for (const s of [-1, 1]) B.marble.box(0.4, HC, LEN, s * (HW + 0.2), HC / 2, ZM);
    B.marble.box(2 * HW, HC, 0.4, 0, HC / 2, ZN + 0.2);
    B.marble.box(HW - DOOR_HW, HC, 0.4, -(HW + DOOR_HW) / 2, HC / 2, ZD - 0.2);
    B.marble.box(HW - DOOR_HW, HC, 0.4, (HW + DOOR_HW) / 2, HC / 2, ZD - 0.2);
    B.marble.box(2 * DOOR_HW, HC - 9.85, 0.4, 0, (HC + 9.85) / 2, ZD - 0.2);
    B.marble.box(2 * DOOR_HW, 1.85, 0.3, 0, 8.975, ZD - 0.15);                // the transom's backing, behind the plaque
    // skirting + dado rail along both walls
    for (const s of [-1, 1]) {
        B.bronze.box(0.04, 0.26, LEN, s * (HW - 0.02), 0.13, ZM);
        B.trim.box(0.06, 0.07, LEN, s * (HW - 0.03), 1.1, ZM);
        B.gold.box(0.75, 0.42, LEN, s * (HW - 0.375), 10.81, ZM);           // cornice band
        B.gold.box(0.5, 0.14, LEN, s * (HW - 0.25), 10.53, ZM);             // its stepped soffit
    }
    // pilasters: a marble plinth, a stepped gilded shaft (fluted front), a corbelled Deco capital
    for (const s of [-1, 1]) {
        for (const zp of PIL) {
            if (s > 0 && SCR_SKIP.has(zp)) continue;
            const X = (d) => s * (HW - d / 2);
            B.marble.box(0.66, 0.72, 1.46, X(0.66), 0.36, zp);
            B.gold.box(0.62, 0.06, 1.42, X(0.62), 0.75, zp);
            B.gold.box(0.18, 8.9, 1.2, X(0.18), 5.23, zp);
            B.gold.box(0.34, 8.9, 0.9, X(0.34), 5.23, zp);
            B.flute.box(0.5, 8.9, 0.6, X(0.5), 5.23, zp);
            B.gold.box(0.56, 0.3, 0.72, X(0.56), 9.83, zp);
            B.gold.box(0.62, 0.3, 0.98, X(0.62), 10.13, zp);
            B.gold.box(0.7, 0.32, 1.32, X(0.7), 10.44, zp);
        }
    }
    // ribs across the ceiling at every pilaster: a stepped gilded beam
    for (const zp of PIL) {
        B.gold.box(2 * HW, 0.75, 0.6, 0, HC - 0.375, zp);
        B.gold.box(2 * HW - 1.4, 0.24, 0.34, 0, HC - 0.87, zp);
    }
    // ceiling + floor
    const ceilB = L.bucket('corridor_ceiling').box(2 * HW, 0.3, LEN, 0, HC + 0.15, ZM);
    const floorB = L.bucket('corridor_floor').box(2 * HW, 0.2, LEN + 0.4, 0, -0.1, ZM - 0.2);
    // the runner (2.8 m wide), from the near end to the door's threshold
    const carpetB = L.bucket('corridor_carpet').box(2.8, 0.014, ZN - (ZD + 0.35), 0, 0.007, (ZN + ZD + 0.35) / 2, { scale: 1 });

    // sconces on the bays (both walls; none behind the LED wall): a gilded back plate, a half-cone of frosted glass
    // with gilded ribs; and the pendant lanterns down the axis: stepped octagonal Deco tiers
    for (const s of [-1, 1]) {
        for (let k = 0; k <= 9; k++) {
            const zc = 16 - 4 * k;
            if (s > 0 && zc <= -3.5 && zc >= -16.5) continue;
            const x0 = s * (HW - 0.02);
            B.gold.box(0.05, 0.62, 0.42, x0 - s * 0.025, SCONCE_Y - 0.05, zc);
            const th0 = s < 0 ? 0 : Math.PI;
            const cone = new T.CylinderGeometry(0.34, 0.07, 0.5, 18, 1, true, th0, Math.PI);
            B.glass.add(cone, L.M4(x0, SCONCE_Y + 0.02, zc), { uv: 'keep' });
            cone.dispose();
            for (const a of [0.35, 0.8, 1.25]) {                       // three gilded ribs over the glass
                for (const sg of [-1, 1]) {
                    const ang = th0 + Math.PI / 2 + sg * (Math.PI / 2 - a);
                    const rr = 0.2;
                    B.gold.box(0.025, 0.52, 0.025, x0 + Math.sin(ang) * rr, SCONCE_Y + 0.02, zc + Math.cos(ang) * rr,
                        { rx: 0, rz: -s * 0.0, ry: 0 });
                }
            }
            B.gold.box(0.3, 0.05, 0.05, x0 - s * 0.15, SCONCE_Y - 0.25, zc);   // the bracket
        }
    }
    for (const zl of LANT) {
        const y0 = LANT_Y - 0.75;
        const prof = (pts) => pts.map(([r, y]) => new T.Vector2(r, y));
        const gl = new T.LatheGeometry(prof([[0.001, 0.25], [0.3, 0.25], [0.3, 1.0], [0.001, 1.0]]), 8);
        B.glass.add(gl, L.M4(0, y0, zl, 0, Math.PI / 8, 0), { uv: 'keep' });
        gl.dispose();
        const metal = new T.LatheGeometry(prof([[0.001, -0.06], [0.08, -0.06], [0.14, 0.04], [0.2, 0.12], [0.28, 0.18], [0.33, 0.25],
            [0.33, 0.29], [0.31, 0.29], [0.31, 0.25]]), 8);
        B.gold.add(metal, L.M4(0, y0, zl, 0, Math.PI / 8, 0));
        metal.dispose();
        const top = new T.LatheGeometry(prof([[0.31, 0.98], [0.37, 1.0], [0.37, 1.07], [0.27, 1.1], [0.27, 1.18], [0.17, 1.2],
            [0.17, 1.28], [0.07, 1.3], [0.05, 1.36], [0.001, 1.36]]), 8);
        B.gold.add(top, L.M4(0, y0, zl, 0, Math.PI / 8, 0));
        top.dispose();
        for (let i = 0; i < 8; i++) {                                   // mullions at the octagon's corners
            const a = i * Math.PI / 4 + Math.PI / 8;
            B.gold.box(0.03, 0.76, 0.03, Math.sin(a) * 0.3, y0 + 0.62, zl + Math.cos(a) * 0.3);
        }
        const midband = new T.LatheGeometry(prof([[0.298, 0.6], [0.318, 0.6], [0.318, 0.64], [0.298, 0.64]]), 8);
        B.gold.add(midband, L.M4(0, y0, zl, 0, Math.PI / 8, 0));
        midband.dispose();
        B.gold.box(0.04, HC - (y0 + 1.36), 0.04, 0, (HC + y0 + 1.36) / 2, zl);   // the rod to the ceiling
    }

    // ─────────────────────────── the portal: a stepped gilded architrave and a Deco crown ───────────────────────────
    const zf = ZD;      // wall face
    for (const s of [-1, 1]) {
        B.gold.box(0.3, 9.85, 0.6, s * (DOOR_HW + 0.15), 9.85 / 2, zf + 0.3);
        B.gold.box(0.4, 10.5, 0.42, s * (DOOR_HW + 0.5), 10.5 / 2, zf + 0.21);
        B.gold.box(0.4, 10.9, 0.26, s * (DOOR_HW + 0.9), 10.9 / 2, zf + 0.13);
    }
    B.gold.box(2 * DOOR_HW + 0.6, 0.3, 0.6, 0, 10.0, zf + 0.3);
    B.gold.box(2 * DOOR_HW + 1.4, 0.4, 0.42, 0, 10.35, zf + 0.21);
    B.gold.box(2 * DOOR_HW + 2.2, 0.4, 0.26, 0, 10.75, zf + 0.13);
    B.gold.box(5.2, 0.36, 0.32, 0, 11.13, zf + 0.16);
    B.gold.box(3.2, 0.34, 0.36, 0, 11.48, zf + 0.18);
    B.gold.box(1.6, 0.36, 0.4, 0, 11.82, zf + 0.2);
    B.gold.box(2 * DOOR_HW, 0.1, 0.5, 0, DOOR_H + 0.05, zf + 0.25);          // the transom bar
    // torchères flanking the door
    for (const s of [-1, 1]) {
        const x = s * 3.95, z = ZD + 1.45;
        const prof = (pts) => pts.map(([r, y]) => new T.Vector2(r, y));
        const body = new T.LatheGeometry(prof([[0.001, 0], [0.26, 0], [0.26, 0.08], [0.2, 0.08], [0.2, 0.16], [0.13, 0.16], [0.13, 0.24],
            [0.06, 0.3], [0.05, 1.9], [0.08, 1.95], [0.08, 2.0], [0.05, 2.05]]), 8);
        B.gold.add(body, L.M4(x, 0, z, 0, Math.PI / 8, 0));
        body.dispose();
        const bowl = new T.LatheGeometry(prof([[0.05, 2.05], [0.22, 2.18], [0.36, 2.32], [0.38, 2.34]]), 16);
        B.glass.add(bowl, L.M4(x, 0, z), { uv: 'keep' });
        bowl.dispose();
        const rim = new T.TorusGeometry(0.375, 0.018, 6, 24);
        B.gold.add(rim, L.M4(x, 2.34, z, Math.PI / 2, 0, 0));
        rim.dispose();
    }

    // ─────────────────────────── relief textures: the door leaves and the plaque ───────────────────────────
    const gray = (v) => { const c = Math.round(Math.max(0, Math.min(1, v)) * 255); return `rgb(${c},${c},${c})`; };
    // one leaf (the left; the right mirrors it): 3.2 × 8.0 m at 200 px/m; canvas x = 640 is the meeting stile
    const doorRel = (() => {
        const W = 640, H = 1600, cv = L.createCanvas(W, H), g = cv.getContext('2d');
        g.fillStyle = gray(0.42); g.fillRect(0, 0, W, H);
        // frame
        g.strokeStyle = gray(0.85); g.lineWidth = 32; g.strokeRect(16, 16, W - 32, H - 32);
        g.strokeStyle = gray(0.66); g.lineWidth = 7; g.strokeRect(46, 46, W - 92, H - 92);
        // kick plate with grooves
        g.fillStyle = gray(0.72); g.fillRect(56, H - 140, W - 112, 84);
        g.fillStyle = gray(0.58); for (let y = H - 128; y < H - 60; y += 16) g.fillRect(64, y, W - 128, 4);
        // the sunburst: rays fan out from the stile at 2.7 m (Balla's sun, split between the two leaves)
        const cx = W, cy = H - 540;
        const N = 11;
        for (let i = 0; i < N; i++) {
            const a0 = Math.PI / 2 + i * Math.PI / N, a1 = a0 + Math.PI / N;
            const r1 = i % 2 ? 470 : 575;
            g.beginPath(); g.moveTo(cx + Math.cos(a0) * 120, cy - Math.sin(a0) * 120);
            g.lineTo(cx + Math.cos(a0) * r1, cy - Math.sin(a0) * r1);
            g.lineTo(cx + Math.cos((a0 + a1) / 2) * (r1 + 30), cy - Math.sin((a0 + a1) / 2) * (r1 + 30));
            g.lineTo(cx + Math.cos(a1) * r1, cy - Math.sin(a1) * r1);
            g.lineTo(cx + Math.cos(a1) * 120, cy - Math.sin(a1) * 120); g.closePath();
            g.fillStyle = gray(i % 2 ? 0.56 : 0.8); g.fill();
            g.strokeStyle = gray(0.3); g.lineWidth = 5; g.stroke();
        }
        g.beginPath(); g.arc(cx, cy, 112, Math.PI / 2, Math.PI * 1.5); g.fillStyle = gray(0.97); g.fill();
        g.beginPath(); g.arc(cx, cy, 84, Math.PI / 2, Math.PI * 1.5); g.strokeStyle = gray(0.68); g.lineWidth = 9; g.stroke();
        g.beginPath(); g.arc(cx, cy, 52, Math.PI / 2, Math.PI * 1.5); g.fillStyle = gray(1.0); g.fill();
        // a raised rail at 5.2 m and the stepped ziggurat above it (mirrored across the stile into one figure)
        g.fillStyle = gray(0.8); g.fillRect(56, H - 1060, W - 112, 22);
        const steps = [[560, 0.6], [450, 0.68], [340, 0.76], [230, 0.84], [120, 0.92]];
        let yb = H - 1080;
        steps.forEach(([w, lv], i) => { const hh = 70 + i * 6; g.fillStyle = gray(lv); g.fillRect(W - w, yb - hh, w, hh); yb -= hh; });
        g.fillStyle = gray(0.95); g.fillRect(W - 40, yb - 200, 40, 200);           // the central spire
        for (let i = 0; i < 6; i++) { g.fillStyle = gray(0.7); g.fillRect(W - 120 - i * 70, yb - 150 + i * 22, 14, 150 - i * 22); }
        // fluting down the hinge side
        for (let i = 0; i < 4; i++) {
            const x0 = 74 + i * 24;
            const gr = g.createLinearGradient(x0, 0, x0 + 20, 0);
            gr.addColorStop(0, gray(0.62)); gr.addColorStop(0.5, gray(0.3)); gr.addColorStop(1, gray(0.62));
            g.fillStyle = gr; g.fillRect(x0, 600, 20, H - 760);
        }
        // the pull's rosette
        g.beginPath(); g.arc(W - 62, H - 250, 42, 0, Math.PI * 2); g.fillStyle = gray(0.95); g.fill();
        g.beginPath(); g.arc(W - 62, H - 250, 26, 0, Math.PI * 2); g.fillStyle = gray(0.7); g.fill();
        const hf = L.heightField(cv, { blur: 3 });
        const wide = L.boxBlur(hf.h, W, H, 14, 2);
        const cav = new Float32Array(W * H);
        for (let i = 0; i < W * H; i++) cav[i] = Math.max(0, Math.min(1, (wide[i] - hf.h[i]) * 4.5));
        return { nrm: L.normalTex(hf, 14), mask: L.packTex([hf.h, cav, null, null], W, H) };
    })();
    const doorMat = (mirror) => {
        const m = own(new T.MeshStandardNodeMaterial());
        m.name = 'corridor_door_' + (mirror ? 'r' : 'l');
        const u0 = uv();
        const ruv = vec2(mirror ? float(1).sub(u0.x) : u0.x, u0.y);
        const tuv = vec2(u0.x.mul(3.2), u0.y.mul(8.0)).div(1.3);
        const mk = texture(doorRel.mask, ruv);
        const h = mk.r, cav = mk.g;
        const gI = texture(S.goldI.col, tuv).rgb.mul(vec3(1.0, 0.84, 0.58));
        const gB = texture(S.bronze.col, tuv).rgb.mul(vec3(0.5, 0.36, 0.22));
        const dark = clamp(cav.mul(1.5).add(max(float(0.5).sub(h), 0).mul(0.8)), 0, 1);
        m.colorNode = mix(gI, gB, dark);
        m.metalnessNode = mix(float(1.0), float(0.75), dark);
        m.roughnessNode = clamp(texture(S.goldI.rgh, tuv).r.mul(0.45).add(0.22).add(dark.mul(0.3)).sub(h.mul(0.06)), 0.12, 1);
        m.normalNode = normalMap(texture(doorRel.nrm, ruv), vec2(mirror ? -1.0 : 1.0, 1.0));
        m.envMap = env; m.envMapIntensity = 0.7;
        return m;
    };
    M.doorL = doorMat(false); M.doorR = doorMat(true);

    // the plaque: engraved, black-enamel-filled letters in a polished gold transom, 6.4 × 1.7 m
    const plaque = (() => {
        const W = 2048, H = 544;
        const cv = L.createCanvas(W, H), g = cv.getContext('2d');
        const mk = L.createCanvas(W, H), gm = mk.getContext('2d');
        gm.fillStyle = '#000'; gm.fillRect(0, 0, W, H);
        g.fillStyle = gray(0.72); g.fillRect(0, 0, W, H);
        g.strokeStyle = gray(1.0); g.lineWidth = 30; g.strokeRect(15, 15, W - 30, H - 30);
        g.strokeStyle = gray(0.86); g.lineWidth = 7; g.strokeRect(52, 52, W - 104, H - 104);
        // Deco end ornaments: stepped bars
        for (const sx of [1, -1]) {
            const x0 = sx > 0 ? 80 : W - 80;
            for (let i = 0; i < 4; i++) {
                const hh = 260 - i * 56, ww = 26;
                g.fillStyle = gray(0.95 - i * 0.05);
                g.fillRect(x0 + sx * i * 40 - (sx < 0 ? ww : 0), H / 2 - hh / 2, ww, hh);
            }
        }
        const lines = [['SUPREME', 215, 175, 1380], ['INTELLIGENCE', 400, 132, 1520]];
        for (const [txt, y, size, maxW] of lines) {
            g.fillStyle = gray(0.12);
            fitText(g, txt, { x: W / 2, y, maxW, maxH: size, family: fam.michroma, track: 0.16 });
            gm.fillStyle = '#fff';
            fitText(gm, txt, { x: W / 2, y, maxW, maxH: size, family: fam.michroma, track: 0.16 });
        }
        // a thin engraved rule between the lines, with a centre lozenge
        g.fillStyle = gray(0.3); g.fillRect(520, 300, W - 1040, 6);
        g.save(); g.translate(W / 2, 303); g.rotate(Math.PI / 4); g.fillRect(-14, -14, 28, 28); g.restore();
        const hf = L.heightField(cv, { blur: 2 });
        const ink = L.heightField(mk, { blur: 1 });
        return { nrm: L.normalTex(hf, 10), mask: L.packTex([hf.h, ink.h, null, null], W, H), W, H };
    })();
    M.plaque = (() => {
        const m = own(new T.MeshStandardNodeMaterial());
        m.name = 'corridor_plaque';
        const u0 = uv();
        const tuv = vec2(u0.x.mul(6.4), u0.y.mul(1.7)).div(0.9);
        const mk = texture(plaque.mask, u0);
        const ink = mk.g;
        const gold = texture(S.goldF.col, tuv).rgb.mul(vec3(1.02, 0.86, 0.58));
        m.colorNode = mix(gold, vec3(0.012, 0.01, 0.009), ink);
        m.metalnessNode = mix(float(1), float(0.0), ink);
        m.roughnessNode = clamp(mix(texture(S.goldF.rgh, tuv).r.mul(0.35).add(0.24), float(0.45), ink), 0.05, 1);
        m.normalNode = normalMap(texture(plaque.nrm, u0), vec2(1.0, 1.0));
        m.envMap = env; m.envMapIntensity = 0.75;
        return m;
    })();

    // ─────────────────────────── meshes of the room ───────────────────────────
    const room = new T.Group();
    room.name = 'corridor_room';
    group.add(room);
    const addMesh = (b, mat, ud = {}) => { const m = b.mesh(mat, { userData: ud }); if (m) room.add(m); return m; };
    addMesh(B.marble, M.marble);
    addMesh(B.gold, M.gold, { noSupportCheck: true });
    addMesh(B.flute, M.goldFluted, { noSupportCheck: true });
    addMesh(B.trim, M.goldTrim, { noSupportCheck: true, allowIntersect: true });
    addMesh(B.bronze, M.bronze, { noSupportCheck: true, allowIntersect: true });
    const sconceGlass = addMesh(B.glass, M.glass, { noSupportCheck: true });
    addMesh(ceilB, M.ceiling, { noSupportCheck: true });
    addMesh(floorB, M.floor);
    addMesh(carpetB, M.carpet, { noZFightCheck: true });

    // the plaque (on the transom) and the doors (each on its hinge pivot)
    const plaqueMesh = new T.Mesh(own(new T.PlaneGeometry(2 * DOOR_HW, 1.7)), M.plaque);
    plaqueMesh.position.set(0, DOOR_H + 0.1 + 0.85, zf + 0.06);
    plaqueMesh.name = 'corridor_plaque';
    plaqueMesh.userData.noSupportCheck = true;
    room.add(plaqueMesh);
    const doors = new T.Group(); doors.name = 'corridor_doors'; room.add(doors);
    const leafGeo = own(new T.BoxGeometry(DOOR_HW, DOOR_H, 0.22));
    const pivotL = new T.Group(), pivotR = new T.Group();
    pivotL.position.set(-DOOR_HW, 0, zf - 0.11); pivotR.position.set(DOOR_HW, 0, zf - 0.11);
    const leafL = new T.Mesh(leafGeo, M.doorL), leafR = new T.Mesh(leafGeo, M.doorR);
    leafL.position.set(DOOR_HW / 2, DOOR_H / 2, 0); leafR.position.set(-DOOR_HW / 2, DOOR_H / 2, 0);
    leafL.name = 'door_left'; leafR.name = 'door_right';
    pivotL.add(leafL); pivotR.add(leafR);
    // ring pulls
    const ringGeo = own(new T.TorusGeometry(0.17, 0.024, 10, 28));
    for (const [pv, sx] of [[pivotL, 1], [pivotR, -1]]) {
        const ring = new T.Mesh(ringGeo, M.goldTrim);
        ring.position.set(sx * (DOOR_HW - 0.31), 1.12, 0.15);
        ring.name = 'door_pull';
        pv.add(ring);
    }
    doors.add(pivotL, pivotR);
    for (const m of [leafL, leafR]) { m.userData.assembly = 'corridor_doors'; m.userData.noSupportCheck = true; }
    // the seam of light between the leaves
    const seamMat = noMRT(own(new T.MeshBasicNodeMaterial({ transparent: true, depthWrite: false, blending: T.AdditiveBlending })));
    seamMat.colorNode = vec3(1.0, 0.75, 0.42).mul(4.0).mul(U.gap).mul(float(1).sub(ss(0.02, 0.12, U.open)));
    const seam = new T.Mesh(own(new T.PlaneGeometry(0.05, DOOR_H)), seamMat);
    seam.position.set(0, DOOR_H / 2, zf + 0.012);
    seam.name = 'door_seam';
    doors.add(seam);
    // beyond the door: a room of light (only seen through the opening)
    const beyondMat = noMRT(own(new T.MeshBasicNodeMaterial({ side: T.BackSide })));
    beyondMat.colorNode = Fn(() => {
        const q = positionLocal;
        const c = exp(q.x.mul(q.x).mul(-0.05).add(q.y.sub(4).mul(q.y.sub(4)).mul(-0.04)));
        return vec3(1.0, 0.78, 0.48).mul(c.mul(2.6).add(0.35)).mul(U.beyond.mul(0.9).add(0.1));
    })();
    const beyond = new T.Mesh(own(new T.BoxGeometry(12, 12, 9)), beyondMat);
    beyond.position.set(0, 6, zf - 4.9);
    beyond.name = 'corridor_beyond';
    beyond.userData.noSupportCheck = true;
    room.add(beyond);
    // god-ray shafts through the opening (additive wedge), only while the door opens
    const shaftMat = noMRT(own(new T.MeshBasicNodeMaterial({ transparent: true, depthWrite: false, blending: T.AdditiveBlending, side: T.DoubleSide })));
    shaftMat.colorNode = Fn(() => {
        const q = positionLocal;
        const along = clamp(q.z.sub(ZD).div(26.0), 0, 1);
        const w = DOOR_HW * 1.0;
        const spread = float(w).add(along.mul(4.0));
        const edge = float(1).sub(smoothstep(spread.mul(0.25), spread, abs(q.x))).mul(ss(0, 0.5, q.y));
        const n = T.mx_noise_float(vec3(q.x.mul(0.6), q.y.mul(0.15), U.t.mul(0.05))).mul(0.35).add(0.75);
        return vec3(1.0, 0.76, 0.45).mul(pow(float(1).sub(along), 2.2)).mul(edge).mul(n).mul(U.open.mul(U.beyond)).mul(0.07);
    })();
    const shaftGeo = (() => {
        // a frustum from the doorway (z = ZD) widening and dropping toward the singer (z = +2)
        const g = new T.BufferGeometry();
        const z0 = ZD + 0.05, z1 = 2.0;
        const v = [
            [-DOOR_HW, 0.03, z0], [DOOR_HW, 0.03, z0], [DOOR_HW, DOOR_H, z0], [-DOOR_HW, DOOR_H, z0],
            [-DOOR_HW - 4, 0.03, z1], [DOOR_HW + 4, 0.03, z1], [DOOR_HW + 4, 2.2, z1], [-DOOR_HW - 4, 2.2, z1]];
        const idx = [0, 1, 5, 0, 5, 4, 1, 2, 6, 1, 6, 5, 2, 3, 7, 2, 7, 6, 3, 0, 4, 3, 4, 7];
        g.setAttribute('position', new T.Float32BufferAttribute(v.flat(), 3));
        g.setIndex(idx);
        g.computeVertexNormals();
        return own(g);
    })();
    const shafts = new T.Mesh(shaftGeo, shaftMat);
    shafts.name = 'corridor_shafts';
    shafts.frustumCulled = false;
    shafts.renderOrder = 10;
    shafts.userData.noSupportCheck = true;
    room.add(shafts);

    // ─────────────────────────── the LED wall: a post in capital letters ───────────────────────────
    const SW = SCR.z1 - SCR.z0, SH = SCR.y1 - SCR.y0;
    const postState = { text: '', name: 'DEPARTMENT OF WAR', meta: 'Official account · now', stats: ['18.2K', '41.7K', '196K', '11.4M'], layout: null };
    const roundRect = (g, x, y, w, h, r) => {
        g.beginPath(); g.moveTo(x + r, y); g.lineTo(x + w - r, y); g.quadraticCurveTo(x + w, y, x + w, y + r);
        g.lineTo(x + w, y + h - r); g.quadraticCurveTo(x + w, y + h, x + w - r, y + h); g.lineTo(x + r, y + h);
        g.quadraticCurveTo(x, y + h, x, y + h - r); g.lineTo(x, y + r); g.quadraticCurveTo(x, y, x + r, y); g.closePath();
    };
    const wrap = (g, text, size, family, maxW) => {
        g.font = `bold ${size}px ${family}`;
        const words = text.split(/\s+/).filter(Boolean), lines = [];
        let cur = '';
        for (const w of words) {
            const tryL = cur ? cur + ' ' + w : w;
            if (g.measureText(tryL).width <= maxW || !cur) cur = tryL; else { lines.push(cur); cur = w; }
        }
        if (cur) lines.push(cur);
        const widest = Math.max(...lines.map((l) => g.measureText(l).width), 0);
        return { lines, widest };
    };
    const layoutPost = (g, text, box) => {
        let lo = 40, hi = 300, best = { size: 40, lines: [text] };
        for (let it = 0; it < 18; it++) {
            const size = (lo + hi) / 2;
            const { lines, widest } = wrap(g, text, size, fam.exo, box.w);
            const hgt = lines.length * size * 1.04;
            if (widest <= box.w && hgt <= box.h) { best = { size, lines }; lo = size; } else hi = size;
        }
        return best;
    };
    const drawPost = (g, W, H, reveal = 1) => {
        g.fillStyle = '#030408'; g.fillRect(0, 0, W, H);
        const cx = W * 0.055, cy = H * 0.06, cw = W * 0.89, ch = H * 0.88;
        roundRect(g, cx, cy, cw, ch, 30); g.fillStyle = '#090c12'; g.fill();
        g.lineWidth = 5; g.strokeStyle = '#222a39'; g.stroke();
        // header: a generic emblem avatar (three gold Deco chevrons in a ring — no seal), the account's name, a
        // generic check badge, the meta line, an overflow mark
        const ar = H * 0.072, ax = cx + 60 + ar, ay = cy + 50 + ar;
        g.beginPath(); g.arc(ax, ay, ar, 0, Math.PI * 2); g.fillStyle = '#05070b'; g.fill();
        g.lineWidth = ar * 0.12; g.strokeStyle = '#c9973a'; g.stroke();
        g.fillStyle = '#d9a845';
        for (let i = 0; i < 3; i++) {
            const yy = ay + ar * 0.42 - i * ar * 0.38, w2 = ar * 0.62 - i * ar * 0.08;
            g.beginPath(); g.moveTo(ax - w2, yy); g.lineTo(ax, yy - ar * 0.3); g.lineTo(ax + w2, yy);
            g.lineTo(ax + w2, yy + ar * 0.14); g.lineTo(ax, yy - ar * 0.16); g.lineTo(ax - w2, yy + ar * 0.14); g.closePath(); g.fill();
        }
        g.textAlign = 'left'; g.textBaseline = 'middle';
        g.fillStyle = '#f3f5f9'; g.font = `bold ${Math.round(H * 0.058)}px ${fam.exo}`;
        const nx = ax + ar + 34;
        g.fillText(postState.name, nx, ay - ar * 0.3);
        const nw = g.measureText(postState.name).width;
        const bx = nx + nw + 26 + H * 0.024, by = ay - ar * 0.3;
        g.beginPath(); g.arc(bx, by, H * 0.024, 0, Math.PI * 2); g.fillStyle = '#c9973a'; g.fill();
        g.strokeStyle = '#05070b'; g.lineWidth = H * 0.008; g.beginPath();
        g.moveTo(bx - H * 0.011, by); g.lineTo(bx - H * 0.002, by + H * 0.009); g.lineTo(bx + H * 0.013, by - H * 0.01); g.stroke();
        g.fillStyle = '#7b8495'; g.font = `${Math.round(H * 0.04)}px ${fam.exo}`;
        g.fillText(postState.meta, nx, ay + ar * 0.48);
        g.fillStyle = '#5b6372';
        for (let i = 0; i < 3; i++) { g.beginPath(); g.arc(cx + cw - 80 + i * 22, ay - ar * 0.3, 6, 0, Math.PI * 2); g.fill(); }
        // the body: huge capitals, laid out once per text so typing never reflows
        const box = { x: cx + 64, y: ay + ar + 34, w: cw - 128, h: ch - (ay + ar + 34 - cy) - H * 0.15 };
        if (!postState.layout) postState.layout = layoutPost(g, postState.text, box);
        const { size, lines } = postState.layout;
        const total = postState.text.length;
        let budget = Math.round(total * Math.max(0, Math.min(1, reveal)));
        g.font = `bold ${size}px ${fam.exo}`;
        g.fillStyle = '#f6f7fb'; g.textBaseline = 'alphabetic';
        const blockH = lines.length * size * 1.04;
        let yy = box.y + (box.h - blockH) / 2 + size * 0.86;
        let lastX = box.x, lastY = yy;
        for (const ln of lines) {
            const shown = ln.slice(0, Math.max(0, budget));
            budget -= ln.length + 1;
            if (shown) g.fillText(shown, box.x, yy);
            lastX = box.x + g.measureText(shown).width; lastY = yy;
            if (budget < 0) break;
            yy += size * 1.04;
        }
        if (reveal < 1) { g.fillStyle = '#c9973a'; g.fillRect(lastX + size * 0.08, lastY - size * 0.78, size * 0.09, size * 0.86); }
        // the action row: reply, repost, like, views (generic glyphs) + counts
        const ry = cy + ch - H * 0.075;
        g.strokeStyle = '#6d7586'; g.fillStyle = '#6d7586'; g.lineWidth = 5;
        g.font = `${Math.round(H * 0.038)}px ${fam.exo}`; g.textBaseline = 'middle';
        const icons = [
            (x) => { roundRect(g, x - 22, ry - 18, 44, 32, 10); g.stroke(); g.beginPath(); g.moveTo(x - 8, ry + 14); g.lineTo(x - 14, ry + 26); g.lineTo(x + 2, ry + 14); g.stroke(); },
            (x) => { g.beginPath(); g.moveTo(x - 24, ry - 4); g.lineTo(x - 24, ry - 16); g.lineTo(x + 14, ry - 16); g.stroke(); g.beginPath(); g.moveTo(x + 24, ry + 4); g.lineTo(x + 24, ry + 16); g.lineTo(x - 14, ry + 16); g.stroke(); },
            (x) => { g.beginPath(); g.moveTo(x, ry + 20); g.bezierCurveTo(x - 40, ry - 6, x - 16, ry - 30, x, ry - 10); g.bezierCurveTo(x + 16, ry - 30, x + 40, ry - 6, x, ry + 20); g.stroke(); },
            (x) => { for (let i = 0; i < 3; i++) g.fillRect(x - 18 + i * 14, ry + 16 - (12 + i * 10), 9, 12 + i * 10); },
        ];
        icons.forEach((ic, i) => {
            const x = cx + 120 + i * (cw - 220) / 3.4;
            ic(x);
            g.fillText(postState.stats[i] || '', x + 40, ry);
        });
    };
    const post = L.dynCanvas(2048, Math.round(2048 * SH / SW), (g, W, H, reveal) => drawPost(g, W, H, reveal), { srgb: true });
    post.redraw(1);
    postTexRef = post.texture;
    M.screen = (() => {
        const m = noMRT(own(new T.MeshBasicNodeMaterial()));
        m.name = 'corridor_ledwall';
        m.colorNode = Fn(() => {
            const u0 = uv();
            const c = texture(post.texture, u0).rgb;
            const cells = vec2(SW / 0.012, SH / 0.012);
            const g2 = abs(fract(u0.mul(cells)).sub(0.5));
            const dotm = ss(0.5, 0.32, max(g2.x, g2.y));
            const fw = T.fwidth(u0.x.mul(SW / 0.012));
            const grid = mix(dotm.mul(0.9).add(0.3), float(0.78), ss(0.2, 0.7, fw));
            // the LED wall's 0.5 m tiles: a faint dark seam between them (fades out when sub-pixel)
            const tq = abs(fract(u0.mul(vec2(SW / 0.5, SH / 0.5))).sub(0.5));
            const tfw = T.fwidth(u0.x.mul(SW / 0.5));
            const seamT = ss(0.494, 0.499, max(tq.x, tq.y)).mul(float(1).sub(ss(0.004, 0.02, tfw)));
            const scan = ss(0.0, 0.03, abs(fract(u0.y.sub(U.t.mul(0.11))).sub(0.5))).mul(0.06).add(0.94);
            return c.mul(grid).mul(scan).mul(float(1).sub(seamT.mul(0.6))).mul(U.screen).mul(1.7);
        })();
        return m;
    })();
    const screen = new T.Mesh(own(new T.PlaneGeometry(SW, SH)), M.screen);
    screen.rotation.y = -Math.PI / 2;
    screen.position.set(HW - 0.07, (SCR.y0 + SCR.y1) / 2, (SCR.z0 + SCR.z1) / 2);
    screen.name = 'corridor_ledwall';
    screen.userData.noSupportCheck = true;
    room.add(screen);
    {   // its stepped gilded frame
        const fb = L.bucket('corridor_screen_frame');
        const zc = (SCR.z0 + SCR.z1) / 2, yc = (SCR.y0 + SCR.y1) / 2;
        for (const [d, w, o] of [[0.16, 0.22, 0.0], [0.28, 0.14, 0.2]]) {
            fb.box(d, w, SW + 2 * (o + w), HW - d / 2, SCR.y1 + o + w / 2, zc);
            fb.box(d, w, SW + 2 * (o + w), HW - d / 2, SCR.y0 - o - w / 2, zc);
            fb.box(d, SH + 2 * o, w, HW - d / 2, yc, SCR.z0 - o - w / 2);
            fb.box(d, SH + 2 * o, w, HW - d / 2, yc, SCR.z1 + o + w / 2);
        }
        const fm = fb.mesh(M.gold, { userData: { noSupportCheck: true } });
        room.add(fm);
    }
    const setText = (str, o = {}) => {
        postState.text = String(str || '').toUpperCase().replace(/\s+/g, ' ').trim();
        if (o.name != null) postState.name = String(o.name);
        if (o.meta != null) postState.meta = String(o.meta);
        if (o.stats) postState.stats = o.stats;
        postState.layout = null;
        postState.reveal = o.reveal ?? 1;
        postState.shown = Math.round(postState.text.length * postState.reveal);
        post.redraw(postState.reveal);
    };
    setText(opts.postText ?? 'AI DOMINANT!');

    // ─────────────────────────── the poll board beside the door ───────────────────────────
    const pollOpts = { title: 'WHAT SHALL WE CALL IT?', sub: 'OFFICIAL POLL  ·  ONE VOTE PER PERSON',
        names: ['SUPERIOR INTELLIGENCE', 'EXTREME INTELLIGENCE', 'SUPREME INTELLIGENCE'],
        footnote: 'THE ONE BEING NAMED MAY NOT VOTE', stamp: 'LOSING BADLY' };
    const PW = 1024, PH = 1456;
    const pollA = L.createCanvas(PW, PH), pollM = L.createCanvas(PW, PH);
    const pollPix = new Uint8Array(PW * PH * 4);
    let pollTex = null;
    const niceUnit = (x) => { const e = Math.pow(10, Math.floor(Math.log10(Math.max(1, x)))); for (const k of [1, 2, 5, 10]) if (k * e >= x) return k * e; return 10 * e; };
    const drawPoll = (tally) => {
        const g = pollA.getContext('2d'), gm = pollM.getContext('2d');
        g.fillStyle = '#080605'; g.fillRect(0, 0, PW, PH);
        gm.fillStyle = '#000'; gm.fillRect(0, 0, PW, PH);
        const both = (fn) => { g.save(); gm.save(); fn(g, '#cfa148'); fn(gm, '#fff'); g.restore(); gm.restore(); };
        // gold-leaf frame, stepped corners
        both((c, col) => {
            c.strokeStyle = col; c.lineWidth = 12; c.strokeRect(22, 22, PW - 44, PH - 44);
            c.lineWidth = 3; c.strokeRect(44, 44, PW - 88, PH - 88);
            c.fillStyle = col;
            for (const [x, y] of [[44, 44], [PW - 44, 44], [44, PH - 44], [PW - 44, PH - 44]]) c.fillRect(x - 14, y - 14, 28, 28);
        });
        // heavy type throughout: the board has to survive the aeropittura's brushwork
        both((c, col) => { c.fillStyle = col; fitText(c, pollOpts.title, { x: PW / 2, y: 120, maxW: 880, maxH: 80, family: fam.audiowide, track: 0.03 }); });
        g.fillStyle = '#ddd2b8'; fitText(g, pollOpts.sub, { x: PW / 2, y: 196, maxW: 800, maxH: 42, family: fam.rajdhani, track: 0.1 });
        both((c, col) => {     // the Deco divider: rules with a stepped lozenge
            c.fillStyle = col; c.fillRect(84, 240, 370, 6); c.fillRect(PW - 454, 240, 370, 6);
            c.save(); c.translate(PW / 2, 243); c.rotate(Math.PI / 4); c.fillRect(-18, -18, 36, 36); c.restore();
            c.fillRect(PW / 2 - 76, 237, 32, 12); c.fillRect(PW / 2 + 44, 237, 32, 12);
        });
        const total = tally.reduce((a, b) => a + b, 0) || 1;
        const mx = Math.max(...tally, 1);
        const unit = niceUnit(mx / 40);
        const minI = tally.indexOf(Math.min(...tally));
        tally.forEach((v, i) => {
            const y0 = 284 + i * 322;
            both((c, col) => { c.fillStyle = col; fitText(c, pollOpts.names[i], { x: 76, y: y0 + 40, maxW: 870, maxH: 62, family: fam.audiowide, align: 'left' }); });
            // tally marks: hand-painted groups of five
            const marks = Math.round(v / unit);
            g.strokeStyle = '#ece2c8'; g.lineCap = 'round'; g.lineWidth = 12;
            const r = L.rng(17 + i * 101);
            for (let k = 0; k < marks; k++) {
                const grp = Math.floor(k / 5), j = k % 5;
                const gx = 88 + grp * 104, top = y0 + 88, bot = y0 + 188;
                if (gx > PW - 130) break;
                if (j < 4) {
                    const x = gx + j * 19 + (r() - 0.5) * 3;
                    g.beginPath(); g.moveTo(x + (r() - 0.5) * 5, top + r() * 6); g.lineTo(x + (r() - 0.5) * 5, bot - r() * 6); g.stroke();
                } else {
                    g.beginPath(); g.moveTo(gx - 12, bot - 14); g.lineTo(gx + 72, top + 12); g.stroke();
                }
            }
            // the bar
            const bx = 80, bw = 640, by = y0 + 212, bh = 60;
            g.fillStyle = '#1d1813'; g.fillRect(bx, by, bw, bh);
            both((c, col) => { c.fillStyle = col; c.fillRect(bx, by, bw * v / mx, bh); });
            const pct = Math.round(100 * v / total);
            g.fillStyle = '#f2e9d2'; fitText(g, pct + '%', { x: PW - 76, y: by + bh / 2 + 2, maxW: 230, maxH: 104, family: fam.rajdhani, align: 'right' });
            if (i === minI && pollOpts.stamp && v < 0.6 * mx) {
                // a red rubber stamp across the losing row, distressed (the ink skips); it lifts the gold leaf's
                // metalness where it lands
                const stamp = (col) => {
                    const sc = L.createCanvas(640, 190), sg = sc.getContext('2d');
                    sg.translate(320, 95);
                    sg.strokeStyle = col; sg.lineWidth = 13; sg.strokeRect(-298, -72, 596, 144);
                    sg.fillStyle = col; fitText(sg, pollOpts.stamp, { x: 0, y: 6, maxW: 540, maxH: 100, family: fam.blackops });
                    sg.globalCompositeOperation = 'destination-out';
                    const rr = L.rng(99);
                    for (let k = 0; k < 1100; k++) { sg.beginPath(); sg.arc((rr() - 0.5) * 620, (rr() - 0.5) * 160, rr() * 3.6 + 0.5, 0, Math.PI * 2); sg.fill(); }
                    return sc;
                };
                for (const [c, col] of [[g, '#c0141f'], [gm, '#000']]) {
                    c.save(); c.translate(PW * 0.6, y0 + 142); c.rotate(-0.16); c.drawImage(stamp(col), -320, -95); c.restore();
                }
            }
        });
        g.fillStyle = '#ddd2b8';
        fitText(g, `EACH MARK = ${unit.toLocaleString('en-US')} VOTES   ·   VOTES CAST ${total.toLocaleString('en-US')}`,
            { x: PW / 2, y: PH - 178, maxW: 880, maxH: 42, family: fam.rajdhani, track: 0.04 });
        if (pollOpts.footnote) both((c, col) => { c.fillStyle = col; fitText(c, pollOpts.footnote, { x: PW / 2, y: PH - 108, maxW: 860, maxH: 46, family: fam.rajdhani, track: 0.1 }); });
        // combine: rgb = albedo, a = gold-leaf mask (metalness)
        const a = L.canvasPixels(pollA), m = L.canvasPixels(pollM);
        for (let i = 0; i < PW * PH; i++) {
            pollPix[i * 4] = a[i * 4]; pollPix[i * 4 + 1] = a[i * 4 + 1]; pollPix[i * 4 + 2] = a[i * 4 + 2]; pollPix[i * 4 + 3] = m[i * 4];
        }
        pollTex = L.dataTex(pollPix, PW, PH, { srgb: true, tx: pollTex });
    };
    let tallyNow = opts.tally ?? [588214, 471902, 144215];
    drawPoll(tallyNow);
    M.poll = (() => {
        const m = own(new T.MeshStandardNodeMaterial());
        m.name = 'corridor_poll';
        const u0 = uv();
        const s = texture(pollTex, u0);
        const leaf = s.a;
        const tuv = u0.mul(vec2(2.4, 3.41)).div(0.8);
        m.colorNode = s.rgb;
        m.metalnessNode = leaf;
        m.roughnessNode = clamp(mix(texture(S.lacq.rgh, tuv).r.mul(0.25).add(0.12), texture(S.goldF.rgh, tuv).r.mul(0.3).add(0.12), leaf), 0.05, 1);
        m.normalNode = normalMap(texture(S.lacq.nrm, tuv), vec2(0.25, 0.25));
        // its brass picture light: a pool from the top edge
        const pool = exp(float(1).sub(u0.y).mul(-2.2)).mul(float(1).sub(abs(u0.x.sub(0.5)).mul(0.9)));
        m.emissiveNode = s.rgb.mul(pool).mul(mix(float(0.3), float(0.55), leaf)).mul(vec3(1.0, 0.85, 0.62)).mul(U.lights);
        m.envMap = env; m.envMapIntensity = 1.0;
        return m;
    })();
    const poll = new T.Group();
    poll.name = 'corridor_poll';
    {
        const board = new T.Mesh(own(new T.PlaneGeometry(2.4, 3.41)), M.poll);
        board.position.set(0, 0.72 + 1.705, 0.05);
        board.name = 'poll_board';
        const pb = L.bucket('poll_frame');
        pb.box(2.54, 3.55, 0.06, 0, 0.72 + 1.705, 0);                    // the lacquered panel's gilded edge
        pb.box(0.08, 2.6, 0.08, -0.98, 1.3, -0.07);                      // legs
        pb.box(0.08, 2.6, 0.08, 0.98, 1.3, -0.07);
        pb.box(0.08, 3.0, 0.08, 0, 1.35, -0.78, { rx: -0.28 });          // the easel's back leg
        pb.box(2.2, 0.06, 0.1, 0, 0.7, 0.0);                             // the ledge
        pb.box(1.5, 0.05, 0.14, 0, 4.24, 0.1);                           // the picture light's arm + hood
        pb.box(1.4, 0.09, 0.05, 0, 4.2, 0.2, { rx: 0.5 });
        const frame = pb.mesh(M.goldTrim, { userData: { assembly: 'corridor_poll' } });
        const back = new T.Mesh(own(new T.BoxGeometry(2.48, 3.48, 0.04)), M.ceiling);
        back.position.set(0, 0.72 + 1.705, 0.012);
        const lamp = new T.Mesh(own(new T.BoxGeometry(1.36, 0.025, 0.03)), M.glass);
        lamp.position.set(0, 4.15, 0.22);
        poll.add(frame, back, board, lamp);
        for (const o of [board, back, lamp]) o.userData.assembly = 'corridor_poll';
    }
    poll.position.set(POLL_AT[0], 0, POLL_AT[1]);
    poll.rotation.y = Math.atan2(0 - POLL_AT[0], 6 - POLL_AT[1]) + 0.18;
    room.add(poll);

    // ─────────────────────────── the AI FORCE mission patch (original design; embroidered) ───────────────────────────
    const patchTex = (() => {
        const W = 1024, c = W / 2;
        const al = L.createCanvas(W, W), g = al.getContext('2d');
        const ht = L.createCanvas(W, W), gh = ht.getContext('2d');      // elevation of each stitched region
        const an = L.createCanvas(W, W), ga = an.getContext('2d');      // stitch direction code
        const mt = L.createCanvas(W, W), gm = mt.getContext('2d');      // gold thread mask
        for (const [x, col] of [[g, 'rgba(0,0,0,0)'], [gh, '#000'], [ga, '#000'], [gm, '#000']]) { x.fillStyle = col; x.fillRect(0, 0, W, W); }
        const disc = (ctx, r, col) => { ctx.beginPath(); ctx.arc(c, c, r, 0, Math.PI * 2); ctx.fillStyle = col; ctx.fill(); };
        const ring = (ctx, r0, r1, col) => { ctx.beginPath(); ctx.arc(c, c, r1, 0, Math.PI * 2); ctx.arc(c, c, r0, 0, Math.PI * 2, true); ctx.fillStyle = col; ctx.fill(); };
        const code = (k) => `rgb(${k},${k},${k})`;   // 0..180 = fixed angle (deg); 200 = tangential; 220 = radial
        // merrowed border (gold), the text band (oxblood), a thin gold ring, the night field (navy)
        ring(g, 470, 508, '#c8962f'); ring(gh, 470, 508, code(235)); ring(ga, 470, 508, code(220)); ring(gm, 470, 508, '#fff');
        ring(g, 350, 470, '#5e0b14'); ring(gh, 350, 470, code(120)); ring(ga, 350, 470, code(200));
        ring(g, 336, 352, '#d4a23c'); ring(gh, 336, 352, code(200)); ring(ga, 336, 352, code(200)); ring(gm, 336, 352, '#fff');
        const fld = g.createRadialGradient(c, c - 80, 40, c, c, 336);
        fld.addColorStop(0, '#22468c'); fld.addColorStop(1, '#0c1b44');
        disc(g, 336, fld); disc(gh, 336, code(90)); disc(ga, 336, code(35));
        // stars
        const r = L.rng(5);
        for (let k = 0; k < 9; k++) {
            const a = r() * Math.PI * 2, d = 120 + r() * 190, x = c + Math.cos(a) * d, y = c + Math.sin(a) * d, s = 6 + r() * 9;
            for (const [ctx, col] of [[g, '#eef2ff'], [gh, code(150)], [ga, code(0)]]) {
                ctx.beginPath(); ctx.moveTo(x, y - s); ctx.lineTo(x + s * 0.3, y - s * 0.3); ctx.lineTo(x + s, y); ctx.lineTo(x + s * 0.3, y + s * 0.3);
                ctx.lineTo(x, y + s); ctx.lineTo(x - s * 0.3, y + s * 0.3); ctx.lineTo(x - s, y); ctx.lineTo(x - s * 0.3, y - s * 0.3); ctx.closePath();
                ctx.fillStyle = col; ctx.fill();
            }
        }
        // the orbit (silver), drawn as an ellipse ring tilted on the Futurist diagonal
        const orbit = (ctx, col, w, from = 0, to = Math.PI * 2) => {
            ctx.save(); ctx.translate(c, c + 20); ctx.rotate(-0.42);
            ctx.beginPath(); ctx.ellipse(0, 0, 268, 92, 0, from, to); ctx.strokeStyle = col; ctx.lineWidth = w; ctx.stroke(); ctx.restore();
        };
        orbit(g, '#c9d1dc', 16, Math.PI, Math.PI * 2); orbit(gh, code(185), 16, Math.PI, Math.PI * 2); orbit(ga, code(200), 16, Math.PI, Math.PI * 2);
        // the chip (gold): a die with pins, at the centre of the orbit
        const chip = (ctx, body, pin, die) => {
            ctx.save(); ctx.translate(c, c + 20); ctx.rotate(-0.42);
            ctx.fillStyle = pin;
            for (let k = -3; k <= 3; k++) {
                ctx.fillRect(k * 20 - 5, -96, 10, 22); ctx.fillRect(k * 20 - 5, 74, 10, 22);
                ctx.fillRect(-96, k * 20 - 5, 22, 10); ctx.fillRect(74, k * 20 - 5, 22, 10);
            }
            ctx.fillStyle = body; ctx.fillRect(-76, -76, 152, 152);
            ctx.fillStyle = die; ctx.fillRect(-46, -46, 92, 92);
            ctx.restore();
        };
        chip(g, '#d19b32', '#b9c2cc', '#20160a'); chip(gh, code(170), code(140), code(130)); chip(ga, code(0), code(90), code(45));
        chip(gm, '#fff', '#000', '#000');
        // the die's traces
        g.save(); g.translate(c, c + 20); g.rotate(-0.42); g.strokeStyle = '#d6a23a'; g.lineWidth = 5;
        for (const [x0, y0, x1, y1] of [[-34, -30, 0, -30], [0, -30, 0, 10], [0, 10, 30, 10], [-30, 26, 12, 26], [12, 26, 12, 40], [-20, -12, -20, 14]]) {
            g.beginPath(); g.moveTo(x0, y0); g.lineTo(x1, y1); g.stroke();
        }
        g.restore();
        // the rocket: rising on the diagonal from lower left, a white body with red fins and a gold trail
        const rocket = (ctx, bodyC, finC, trailC, wTrail) => {
            ctx.save(); ctx.translate(c + 110, c - 150); ctx.rotate(0.72);
            const tg = ctx.createLinearGradient(0, 40, 0, 360);
            if (typeof trailC === 'string') { tg.addColorStop(0, trailC); tg.addColorStop(1, trailC); }
            else { tg.addColorStop(0, trailC[0]); tg.addColorStop(1, trailC[1]); }
            ctx.fillStyle = tg; ctx.beginPath(); ctx.moveTo(-wTrail, 60); ctx.lineTo(wTrail, 60); ctx.lineTo(4, 380); ctx.lineTo(-4, 380); ctx.closePath(); ctx.fill();
            ctx.fillStyle = finC;
            ctx.beginPath(); ctx.moveTo(-26, 20); ctx.lineTo(-58, 76); ctx.lineTo(-24, 62); ctx.closePath(); ctx.fill();
            ctx.beginPath(); ctx.moveTo(26, 20); ctx.lineTo(58, 76); ctx.lineTo(24, 62); ctx.closePath(); ctx.fill();
            ctx.fillStyle = bodyC; ctx.beginPath(); ctx.moveTo(0, -120); ctx.bezierCurveTo(34, -80, 30, 10, 26, 64);
            ctx.lineTo(-26, 64); ctx.bezierCurveTo(-30, 10, -34, -80, 0, -120); ctx.closePath(); ctx.fill();
            ctx.restore();
        };
        rocket(g, '#eef0f4', '#b3121d', ['#ffcf5a', 'rgba(255,140,40,0)'], 24);
        rocket(gh, code(200), code(170), code(110), 24);
        rocket(ga, code(52), code(140), code(52), 24);
        rocket(gm, '#000', '#000', ['#fff', '#000'], 24);
        // the orbit's near half passes in front of the rocket
        orbit(g, '#c9d1dc', 16, 0, Math.PI); orbit(gh, code(190), 16, 0, Math.PI); orbit(ga, code(200), 16, 0, Math.PI);
        orbit(gm, '#000', 16, 0, Math.PI);
        // the band's words, on the arcs
        const arcText = (ctx, text, rr, size, family, top, col, track = 0.12) => {
            ctx.save(); ctx.font = `${size}px ${family}`; ctx.fillStyle = col; ctx.textAlign = 'center'; ctx.textBaseline = 'middle';
            const widths = [...text].map((ch) => ctx.measureText(ch).width + track * size);
            const total = widths.reduce((a, b) => a + b, 0);
            let a = (top ? -Math.PI / 2 : Math.PI / 2) + (top ? -1 : 1) * total / rr / 2;
            [...text].forEach((ch, i) => {
                const w = widths[i] / rr;
                const am = a + (top ? 1 : -1) * w / 2;
                ctx.save(); ctx.translate(c + Math.cos(am) * rr, c + Math.sin(am) * rr);
                ctx.rotate(am + (top ? Math.PI / 2 : -Math.PI / 2)); ctx.fillText(ch, 0, 0); ctx.restore();
                a += (top ? 1 : -1) * w;
            });
            ctx.restore();
        };
        for (const [ctx, col] of [[g, '#e1ad3f'], [gh, code(230)], [ga, code(90)], [gm, '#fff']]) arcText(ctx, 'AI FORCE', 410, 92, fam.blackops, true, col, 0.18);
        for (const [ctx, col] of [[g, '#dfe3ea'], [gh, code(215)], [ga, code(90)]]) arcText(ctx, 'SCIT LOCUM SUUM', 412, 46, fam.michroma, false, col, 0.1);
        // stitch height: the region's elevation + satin ridges along each region's direction
        const hp = L.canvasPixels(ht), ap = L.canvasPixels(an);
        const h = new Float32Array(W * W);
        for (let y = 0; y < W; y++) for (let x = 0; x < W; x++) {
            const i = y * W + x;
            const base = hp[i * 4] / 255, k = ap[i * 4];
            if (base <= 0) { h[i] = 0; continue; }
            let ang;
            if (k >= 210) ang = Math.atan2(y - c, x - c);
            else if (k >= 190) ang = Math.atan2(y - c, x - c) + Math.PI / 2;
            else ang = k * Math.PI / 180;
            const per = 5.0;
            const s = Math.sin(((x * Math.cos(ang) + y * Math.sin(ang)) * 2 * Math.PI) / per);
            h[i] = base * 0.75 + 0.12 * (0.5 + 0.5 * s) * base;
        }
        const hb = { h: L.boxBlur(h, W, W, 1, 1), W, H: W };
        // albedo with the stitch shading folded in (threads catch light on their crowns)
        const alp = L.canvasPixels(al), mp = L.canvasPixels(mt);
        const out = new Uint8Array(W * W * 4);
        for (let i = 0; i < W * W; i++) {
            const shade = 0.82 + 0.3 * (hb.h[i] - (hp[i * 4] / 255) * 0.75) / 0.12;
            out[i * 4] = Math.min(255, alp[i * 4] * shade); out[i * 4 + 1] = Math.min(255, alp[i * 4 + 1] * shade);
            out[i * 4 + 2] = Math.min(255, alp[i * 4 + 2] * shade); out[i * 4 + 3] = alp[i * 4 + 3] > 8 ? Math.max(1, mp[i * 4]) : 0;
        }
        return { col: L.dataTex(out, W, W, { srgb: true }), nrm: L.normalTex(hb, 7) };
    })();
    // alpha carries the cut-out (0) and the gold-thread mask (>0.3); the wall patch also catches its sconce's fan
    const patchMat = (wall) => {
        const m = own(new T.MeshStandardNodeMaterial({ side: T.FrontSide, alphaTest: 0.5 }));
        m.name = wall ? 'corridor_patch' : 'uniform_patch';
        const s = texture(patchTex.col, uv());
        m.colorNode = s.rgb;
        m.opacityNode = step(0.002, s.a);
        m.metalnessNode = ss(0.3, 0.9, s.a).mul(0.9);
        m.roughnessNode = mix(float(0.78), float(0.32), ss(0.3, 0.9, s.a));
        m.normalNode = normalMap(texture(patchTex.nrm, uv()), vec2(1.0, 1.0));
        if (wall) {
            // disc-local coordinates → the corridor's (the disc faces +x on the −x wall: local x → −z, y → up)
            const q = uv().sub(0.5).mul(2 * PATCH.r);
            m.emissiveNode = s.rgb.mul(fan(float(PATCH.z).sub(q.x), q.y.add(PATCH.y), float(-1))).mul(vec3(...WARM)).mul(0.35).mul(U.lights);
        }
        m.envMap = env; m.envMapIntensity = 0.8;
        return m;
    };
    M.patch = patchMat(true);
    M.patchSmall = patchMat(false);
    const patch = new T.Group();
    patch.name = 'corridor_patch';
    {
        const disc = new T.Mesh(own(new T.CircleGeometry(PATCH.r, 96)), M.patch);
        disc.name = 'patch_cloth';
        const ringG = own(new T.TorusGeometry(PATCH.r + 0.03, 0.045, 10, 96));
        const ringM = new T.Mesh(ringG, M.gold);
        ringM.position.z = -0.01;
        const back = new T.Mesh(own(new T.CylinderGeometry(PATCH.r + 0.06, PATCH.r + 0.06, 0.04, 64)), M.ceiling);
        back.rotation.x = Math.PI / 2; back.position.z = -0.03;
        patch.add(back, ringM, disc);
        for (const o of [disc, ringM, back]) o.userData.assembly = 'corridor_patch';
    }
    // CircleGeometry's patch is set in the patch group's local frame; on the −x wall it faces +x
    patch.position.set(-HW + 0.09, PATCH.y, PATCH.z);
    patch.rotation.y = Math.PI / 2;
    patch.userData.noSupportCheck = true;
    room.add(patch);

    // ─────────────────────────── the uniform on a tailor's stand ───────────────────────────
    M.wool = L.pbrMat(S.twill, { name: 'uniform_wool', tile: 0.18, nrm: 1.0, rough: [0.4, 0.55], physical: true, sheen: 0.6, sheenRoughness: 0.5,
        sheenColor: 0x1a2440, recolor: (c) => vec3(0.03, 0.038, 0.07).mul(lum(c).mul(2.0).add(0.45)), env, envI: 0.45 });
    M.sash = L.pbrMat(S.pile, { name: 'uniform_sash', tile: 0.2, physical: true, sheen: 0.8, sheenRoughness: 0.4, sheenColor: 0x8a1822,
        recolor: (c) => vec3(0.42, 0.03, 0.04).mul(lum(c).mul(2.0).add(0.3)), rough: [0.5, 0.35], env, envI: 0.5 });
    M.leather = L.pbrMat(S.lacq, { name: 'uniform_leather', tile: 0.4, recolor: (c) => vec3(0.012, 0.01, 0.009).mul(lum(c).mul(1.5).add(0.6)),
        rough: [0.3, 0.12], env, envI: 0.9 });
    M.wood = L.pbrMat(S.wood, { name: 'stand_wood', tile: 0.6, tint: [0.45, 0.3, 0.22], rough: [0.8, 0.1], env, envI: 0.5 });
    const uniform_ = new T.Group();
    uniform_.name = 'corridor_uniform';
    {
        const prof = (pts) => pts.map(([r, y]) => new T.Vector2(r, y));
        const torsoPts = [[0.001, 0.8], [0.15, 0.8], [0.172, 0.86], [0.165, 0.95], [0.148, 1.02], [0.155, 1.1], [0.172, 1.2],
            [0.183, 1.29], [0.18, 1.36], [0.165, 1.415], [0.13, 1.46], [0.085, 1.5], [0.062, 1.53], [0.06, 1.58], [0.001, 1.585]];
        const rAt = (y) => {
            for (let i = 1; i < torsoPts.length; i++) {
                const [r0, y0] = torsoPts[i - 1], [r1, y1] = torsoPts[i];
                if (y >= y0 && y <= y1) return r0 + (r1 - r0) * (y - y0) / Math.max(1e-6, y1 - y0);
            }
            return 0.05;
        };
        const SX = 1.27, SZ = 0.78;
        const torso = new T.LatheGeometry(prof(torsoPts), 48);
        torso.scale(SX, 1, SZ);
        const wb = L.bucket('uniform_wool').add(torso, null, { uv: 'keep', uvScale: [1.2, 1] });
        torso.dispose();
        // empty sleeves hanging from the shoulders, slightly forward
        for (const s of [-1, 1]) {
            const curve = new T.CatmullRomCurve3([new T.Vector3(s * 0.205, 1.4, 0.0), new T.Vector3(s * 0.235, 1.18, 0.03), new T.Vector3(s * 0.24, 0.92, 0.07)]);
            const sl = new T.TubeGeometry(curve, 16, 0.052, 14, false);
            wb.add(sl, null, { uv: 'keep', uvScale: [3, 1] });
            sl.dispose();
        }
        uniform_.add(wb.mesh(M.wool));
        const gb = L.bucket('uniform_gold');
        // the high collar's braid, the cuffs, the front piping, the buttons, the epaulettes and their fringe
        const collar = new T.CylinderGeometry(0.066, 0.066, 0.016, 32, 1, true);
        gb.add(collar, L.M4(0, 1.574, 0, 0, 0, 0, [SX * 0.98, 1, SZ * 1.05]), { uv: 'keep' }); collar.dispose();
        for (const s of [-1, 1]) {
            const cuff = new T.TorusGeometry(0.05, 0.007, 6, 20);
            gb.add(cuff, L.M4(s * 0.24, 0.95, 0.068, Math.PI / 2 - 0.12, 0, 0));
            cuff.dispose();
        }
        for (let k = 0; k < 6; k++) {
            const y = 1.0 + k * 0.075;
            for (const xo of [-0.055, 0.055]) {
                const r = rAt(y), zf = SZ * Math.sqrt(Math.max(0, r * r - (xo / SX) * (xo / SX)));
                const b = new T.SphereGeometry(0.011, 10, 8);
                gb.add(b, L.M4(xo, y, zf + 0.004, 0, 0, 0, [1, 1, 0.55])); b.dispose();
            }
        }
        for (const s of [-1, 1]) {
            const ep = new T.CylinderGeometry(0.06, 0.06, 0.018, 24);
            gb.add(ep, L.M4(s * 0.17, 1.445, 0.0, 0, 0, s * 0.42, [1, 1, 0.75])); ep.dispose();
            for (let k = 0; k < 15; k++) {
                const a = -Math.PI * 0.55 + k * (Math.PI * 1.1 / 14);
                const fx = s * (0.17 + Math.cos(a) * 0.058 * Math.cos(0.42)), fz = Math.sin(a) * 0.045;
                const fr = new T.CylinderGeometry(0.0045, 0.0045, 0.075, 5);
                gb.add(fr, L.M4(fx + s * 0.025, 1.4, fz, 0, 0, s * 0.2)); fr.dispose();
            }
        }
        // the aiguillette: gold cords from the right shoulder to the chest
        for (const [sag, w] of [[0.06, 0.0065], [0.1, 0.006]]) {
            const cu = new T.CatmullRomCurve3([new T.Vector3(-0.19, 1.42, 0.04), new T.Vector3(-0.15, 1.36 - sag, 0.13),
                new T.Vector3(-0.07, 1.3 - sag * 0.6, 0.15), new T.Vector3(-0.045, 1.33, 0.14)]);
            const tb = new T.TubeGeometry(cu, 24, w, 6, false);
            gb.add(tb, null, { uv: 'keep' }); tb.dispose();
        }
        // the belt's buckle
        gb.box(0.06, 0.05, 0.012, 0, 1.02, SZ * rAt(1.02) + 0.012);
        uniform_.add(gb.mesh(M.goldTrim));
        // the belt
        const belt = new T.CylinderGeometry(rAt(1.02) + 0.006, rAt(1.02) + 0.006, 0.045, 48, 1, true);
        belt.scale(SX, 1, SZ);
        const bb = L.bucket('uniform_leather').add(belt, L.M4(0, 1.02, 0), { uv: 'keep', uvScale: [4, 1] });
        belt.dispose();
        uniform_.add(bb.mesh(M.leather));
        // the red sash, right shoulder to left hip, laid over the front
        const sashPts = [];
        for (let k = 0; k <= 14; k++) {
            const s = k / 14;
            const y = 1.43 - s * 0.47;
            const x = -0.16 + s * 0.31;
            const r = rAt(y);
            const zf = SZ * Math.sqrt(Math.max(0, r * r - (x / SX) * (x / SX))) + 0.007;
            sashPts.push(new T.Vector3(x, y, zf));
        }
        // a flat band that lies on the cloth: its width runs along the torso surface (cross of path × surface normal)
        const sashCurve = new T.CatmullRomCurve3(sashPts);
        const sashGeo = (() => {
            const N = 48, pos = [], uvs = [], idx = [];
            for (let i = 0; i <= N; i++) {
                const s = i / N, p = sashCurve.getPointAt(s), tg = sashCurve.getTangentAt(s);
                const n = new T.Vector3(p.x / (SX * SX), 0, p.z / (SZ * SZ)).normalize();
                const w = new T.Vector3().crossVectors(tg, n).normalize().multiplyScalar(0.05);
                const lift = n.clone().multiplyScalar(0.003);
                pos.push(p.x + w.x + lift.x, p.y + w.y, p.z + w.z + lift.z, p.x - w.x + lift.x, p.y - w.y, p.z - w.z + lift.z);
                uvs.push(s * 6, 0, s * 6, 1);
                if (i < N) { const a = 2 * i; idx.push(a, a + 1, a + 2, a + 1, a + 3, a + 2); }
            }
            const g = new T.BufferGeometry();
            g.setAttribute('position', new T.Float32BufferAttribute(pos, 3));
            g.setAttribute('uv', new T.Float32BufferAttribute(uvs, 2));
            g.setIndex(idx); g.computeVertexNormals();
            return own(g);
        })();
        const sash = new T.Mesh(sashGeo, M.sash);
        M.sash.side = T.DoubleSide;
        sash.name = 'uniform_sash';
        uniform_.add(sash);
        // the ribbon bar (invented colours) and the AI FORCE patch on the left sleeve
        const rbCv = L.createCanvas(256, 96), rg = rbCv.getContext('2d');
        const cols = [['#7a0d16', '#d7a03a', '#0d1b3d'], ['#d7a03a', '#eef0f4', '#7a0d16'], ['#0d1b3d', '#d7a03a', '#0d1b3d'],
            ['#eef0f4', '#7a0d16', '#eef0f4'], ['#3a5d2a', '#d7a03a', '#3a5d2a'], ['#7a0d16', '#0d1b3d', '#7a0d16']];
        cols.forEach((cs, i) => {
            const x = (i % 3) * 85, y = Math.floor(i / 3) * 48;
            cs.forEach((cc, j) => { rg.fillStyle = cc; rg.fillRect(x + [0, 28, 57][j], y, [28, 29, 28][j], 46); });
        });
        const rbMat = own(new T.MeshStandardNodeMaterial({ roughness: 0.55 }));
        rbMat.colorNode = texture(L.canvasTex(rbCv), uv()).rgb;
        rbMat.envMap = env;
        const rb = new T.Mesh(own(new T.PlaneGeometry(0.1, 0.038)), rbMat);
        rb.position.set(0.075, 1.31, SZ * rAt(1.31) + 0.01);
        rb.rotation.y = 0.32;
        uniform_.add(rb);
        const sp = new T.Mesh(own(new T.CircleGeometry(0.045, 40)), M.patchSmall);
        sp.position.set(0.292, 1.3, 0.03);
        sp.rotation.y = Math.PI / 2 - 0.12;
        uniform_.add(sp);
        // the stand: a brass pole on a wooden tripod
        const pole = new T.CylinderGeometry(0.016, 0.016, 0.78, 12);
        const sb = L.bucket('stand_brass').add(pole, L.M4(0, 0.4, 0), { uv: 'keep' });
        pole.dispose();
        const col2 = new T.CylinderGeometry(0.03, 0.035, 0.06, 16);
        sb.add(col2, L.M4(0, 0.13, 0), { uv: 'keep' }); col2.dispose();
        uniform_.add(sb.mesh(M.goldTrim));
        const wbk = L.bucket('stand_wood');
        for (let k = 0; k < 3; k++) {
            const a = k * Math.PI * 2 / 3 + 0.4;
            const leg = new T.BoxGeometry(0.034, 0.03, 0.42);
            wbk.add(leg, L.M4(Math.sin(a) * 0.2, 0.06, Math.cos(a) * 0.2, -0.22, a, 0)); leg.dispose();
        }
        uniform_.add(wbk.mesh(M.wood));
        uniform_.traverse((o) => { if (o.isMesh) o.userData.assembly = 'corridor_uniform'; });
    }
    uniform_.position.set(UNIFORM_AT[0], 0, UNIFORM_AT[1]);
    uniform_.rotation.y = Math.atan2(0 - UNIFORM_AT[0], 6 - UNIFORM_AT[1]);
    room.add(uniform_);

    // ─────────────────────────── the pedestal, the velvet cushion and the peaked cap ───────────────────────────
    M.velvet = L.pbrMat(S.pile, { name: 'cushion_velvet', tile: 0.12, physical: true, sheen: 1.0, sheenRoughness: 0.35, sheenColor: 0xa0242c,
        recolor: (c) => vec3(0.3, 0.018, 0.026).mul(lum(c).mul(2.0).add(0.25)), rough: [0.5, 0.4], env, envI: 0.4 });
    M.patent = L.pbrMat(S.lacq, { name: 'cap_patent', tile: 0.3, physical: true, clearcoat: 1.0, clearcoatRoughness: 0.06, side: T.DoubleSide,
        recolor: () => vec3(0.006, 0.006, 0.007), rough: [0.2, 0.08], nrm: 0.15, env, envI: 1.2 });
    const braidCv = L.createCanvas(128, 32), bg2 = braidCv.getContext('2d');
    for (let x = -32; x < 160; x += 8) { bg2.strokeStyle = '#fff'; bg2.lineWidth = 3; bg2.beginPath(); bg2.moveTo(x, 0); bg2.lineTo(x + 16, 32); bg2.stroke(); }
    const braidH = L.heightField(braidCv, { blur: 1 });
    const braidN = L.normalTex(braidH, 3, { wrap: T.RepeatWrapping });
    M.braid = L.pbrMat(S.goldF, { name: 'cap_braid', tile: 0.15, metal: 1, rough: [0.4, 0.15], tint: [1.0, 0.82, 0.5], env, envI: 1.1,
        post: () => ({ normal: normalMap(texture(braidN, uv().mul(vec2(24, 1))), vec2(1.2, 1.2)) }) });

    const pedestal = new T.Group();
    pedestal.name = 'corridor_pedestal';
    {
        const pb = L.bucket('pedestal_marble').box(0.46, 0.8, 0.46, 0, 0.52, 0);
        const gbp = L.bucket('pedestal_gold').box(0.62, 0.12, 0.62, 0, 0.06, 0).box(0.54, 0.05, 0.54, 0, 0.145, 0)
            .box(0.56, 0.06, 0.56, 0, 0.95, 0).box(0.5, 0.025, 0.5, 0, 0.91, 0);
        pedestal.add(pb.mesh(M.marble), gbp.mesh(M.gold));
    }
    pedestal.position.set(CAP_AT[0], 0, CAP_AT[1]);
    pedestal.rotation.y = 0.35;
    room.add(pedestal);
    const cushion = new T.Group();
    cushion.name = 'corridor_cushion';
    {
        // a squared pillow: a sphere pushed to a superellipse, thinner at the edges
        const g = new T.SphereGeometry(1, 48, 24);
        const p = g.attributes.position;
        for (let i = 0; i < p.count; i++) {
            const x = p.getX(i), y = p.getY(i), z = p.getZ(i);
            const sx = Math.sign(x) * Math.pow(Math.abs(x), 0.32) * 0.215, sz = Math.sign(z) * Math.pow(Math.abs(z), 0.32) * 0.215;
            const edge = Math.max(Math.abs(sx), Math.abs(sz)) / 0.215;
            p.setXYZ(i, sx, y * 0.06 * (1.05 - 0.55 * Math.pow(edge, 3)), sz);
        }
        g.computeVertexNormals();
        const cm = new T.Mesh(g, M.velvet);
        own(g);
        cm.position.y = 0.06;
        cm.name = 'cushion_velvet';
        cushion.add(cm);
        // gold piping round the seam and four tassels
        const pipe = [];
        for (let k = 0; k <= 64; k++) {
            const a = k / 64 * Math.PI * 2, cx = Math.cos(a), sz2 = Math.sin(a);
            const x = Math.sign(cx) * Math.pow(Math.abs(cx), 0.32) * 0.216, z = Math.sign(sz2) * Math.pow(Math.abs(sz2), 0.32) * 0.216;
            pipe.push(new T.Vector3(x, 0.06, z));
        }
        const pg = L.bucket('cushion_gold').add(new T.TubeGeometry(new T.CatmullRomCurve3(pipe, true), 128, 0.006, 6, true), null, { uv: 'keep' });
        for (const [x, z] of [[1, 1], [-1, 1], [1, -1], [-1, -1]]) {
            const tc = new T.ConeGeometry(0.018, 0.07, 10);
            pg.add(tc, L.M4(x * 0.215, 0.025, z * 0.215)); tc.dispose();
            const tk = new T.SphereGeometry(0.013, 10, 8);
            pg.add(tk, L.M4(x * 0.215, 0.064, z * 0.215)); tk.dispose();
        }
        cushion.add(pg.mesh(M.braid));
        cushion.traverse((o) => { if (o.isMesh) o.userData.assembly = 'corridor_pedestal'; });
    }
    cushion.position.set(CAP_AT[0], 0.98, CAP_AT[1]);
    cushion.rotation.y = 0.35;
    room.add(cushion);

    // the cap: origin = the centre of the headband's lower edge, visor toward +Z, metres (a 58–60 cm head)
    const cap = new T.Group();
    cap.name = 'corridor_cap';
    {
        const prof = (pts) => pts.map(([r, y]) => new T.Vector2(r, y));
        const band = new T.CylinderGeometry(0.097, 0.095, 0.056, 64, 1, true);
        band.translate(0, 0.028, 0);
        const crown = new T.LatheGeometry(prof([[0.097, 0.054], [0.108, 0.066], [0.124, 0.08], [0.138, 0.092], [0.145, 0.1],
            [0.143, 0.106], [0.13, 0.11], [0.08, 0.112], [0.001, 0.113]]), 64);
        // the saddle: the front of the crown rides up, the back drops a little
        const cp = crown.attributes.position;
        for (let i = 0; i < cp.count; i++) {
            let x = cp.getX(i), y = cp.getY(i), z = cp.getZ(i) * 1.07;
            if (y > 0.07) {
                const zn = z / 0.155;
                y += 0.034 * Math.pow(Math.max(0, zn), 1.6) * Math.min(1, (y - 0.07) / 0.03) - 0.008 * Math.max(0, -zn);
            }
            cp.setXYZ(i, x * 0.97, y, z);
        }
        crown.computeVertexNormals();
        const cw = L.bucket('cap_wool').add(band, null, { uv: 'keep', uvScale: [3.5, 0.3] }).add(crown, null, { uv: 'keep', uvScale: [3.5, 0.6] });
        band.dispose(); crown.dispose();
        const capWool = cw.mesh(M.wool);
        // the gold braid band and the chin cord
        const braid = new T.CylinderGeometry(0.0995, 0.0975, 0.032, 64, 1, true);
        braid.translate(0, 0.03, 0);
        const cb = L.bucket('cap_braid').add(braid, null, { uv: 'keep', uvScale: [6, 1] });
        braid.dispose();
        const cord = [];
        for (let k = 0; k <= 24; k++) { const a = -1.05 + k * 2.1 / 24; cord.push(new T.Vector3(Math.sin(a) * 0.101, 0.016 - Math.cos(a * 1.2) * 0.004, Math.cos(a) * 0.101)); }
        cb.add(new T.TubeGeometry(new T.CatmullRomCurve3(cord), 32, 0.0035, 6, false), null, { uv: 'keep' });
        for (const s of [-1, 1]) { const bt = new T.SphereGeometry(0.007, 10, 8); cb.add(bt, L.M4(s * Math.sin(1.08) * 0.1, 0.017, Math.cos(1.08) * 0.1)); bt.dispose(); }
        // the visor: a curved peak from the band's lower front, sloping down
        const vg = new T.BufferGeometry();
        const NA = 32, NR = 6, pos = [], idx = [], uvs = [];
        const vpt = (a, s, top) => {
            const ext = 0.07 * Math.pow(Math.cos(a / 1.25 * Math.PI / 2), 0.7);
            const r = 0.096 + s * ext;
            const y = 0.006 - s * ext * 0.5 - s * s * 0.012 * (1 + Math.abs(a)) + (top ? 0.0035 : 0);
            return [Math.sin(a) * r * 0.99, y, Math.cos(a) * r * 1.03];
        };
        for (const top of [true, false]) {
            const base = pos.length / 3;
            for (let i = 0; i <= NA; i++) for (let j = 0; j <= NR; j++) {
                const a = -1.25 + 2.5 * i / NA, s = j / NR;
                pos.push(...vpt(a, s, top)); uvs.push(i / NA, s);
            }
            for (let i = 0; i < NA; i++) for (let j = 0; j < NR; j++) {
                const a0 = base + i * (NR + 1) + j, a1 = a0 + NR + 1;
                if (top) idx.push(a0, a1, a0 + 1, a1, a1 + 1, a0 + 1); else idx.push(a0, a0 + 1, a1, a1, a0 + 1, a1 + 1);
            }
        }
        vg.setAttribute('position', new T.Float32BufferAttribute(pos, 3));
        vg.setAttribute('uv', new T.Float32BufferAttribute(uvs, 2));
        vg.setIndex(idx);
        vg.computeVertexNormals();
        const visor = new T.Mesh(own(vg), M.patent);
        visor.name = 'cap_visor';
        // the visor's gold edge
        const edge = [];
        for (let i = 0; i <= 40; i++) { const a = -1.25 + 2.5 * i / 40; const [x, y, z] = vpt(a, 1, true); edge.push(new T.Vector3(x, y - 0.0015, z)); }
        cb.add(new T.TubeGeometry(new T.CatmullRomCurve3(edge), 48, 0.0028, 5, false), null, { uv: 'keep' });
        const capGold = cb.mesh(M.braid);
        // the badge: a winged chip (original), gold
        const bdCv = L.createCanvas(256, 192), bd = bdCv.getContext('2d');
        bd.clearRect(0, 0, 256, 192);
        bd.fillStyle = '#fff';
        for (const s of [-1, 1]) {
            for (let k = 0; k < 4; k++) {
                bd.beginPath();
                const x0 = 128 + s * 34, y0 = 86 + k * 14;
                bd.moveTo(x0, y0); bd.lineTo(x0 + s * (96 - k * 16), y0 - 26 + k * 6); bd.lineTo(x0 + s * (90 - k * 16), y0 - 14 + k * 6); bd.lineTo(x0, y0 + 10);
                bd.closePath(); bd.fill();
            }
        }
        bd.fillRect(100, 66, 56, 56);
        for (let k = 0; k < 4; k++) { bd.fillRect(104 + k * 14, 56, 6, 10); bd.fillRect(104 + k * 14, 122, 6, 10); }
        bd.beginPath(); bd.moveTo(128, 18); bd.lineTo(136, 40); bd.lineTo(158, 42); bd.lineTo(140, 54); bd.lineTo(146, 76 - 12);
        bd.lineTo(128, 54); bd.lineTo(110, 64); bd.lineTo(116, 54); bd.lineTo(98, 42); bd.lineTo(120, 40); bd.closePath(); bd.fill();
        bd.fillStyle = 'rgba(0,0,0,1)'; bd.globalCompositeOperation = 'destination-out'; bd.fillRect(114, 80, 28, 28); bd.globalCompositeOperation = 'source-over';
        const bdTex = L.canvasTex(bdCv, { srgb: false });
        const badgeMat = own(new T.MeshStandardNodeMaterial({ alphaTest: 0.5, side: T.DoubleSide }));
        badgeMat.colorNode = texture(S.goldF.col, uv().mul(0.5)).rgb.mul(vec3(1.05, 0.86, 0.55));
        badgeMat.opacityNode = texture(bdTex, uv()).r;
        badgeMat.metalnessNode = float(1); badgeMat.roughnessNode = float(0.22);
        badgeMat.envMap = env; badgeMat.envMapIntensity = 1.3;
        const badge = new T.Mesh(own(new T.PlaneGeometry(0.075, 0.056)), badgeMat);
        badge.position.set(0, 0.093, 0.156);
        badge.rotation.x = -0.42;
        badge.name = 'cap_badge';
        cap.add(capWool, capGold, visor, badge);
        cap.traverse((o) => { if (o.isMesh) { o.userData.assembly = 'corridor_cap'; o.castShadow = true; } });
    }
    // resting on the cushion (the cushion's crown is ~0.12 m above its base)
    const capRest = new T.Object3D();
    capRest.position.set(CAP_AT[0], 0.98 + 0.108, CAP_AT[1]);
    capRest.rotation.set(-0.02, 0.35 + 0.5, 0);
    room.add(capRest);
    cap.position.copy(capRest.position); cap.quaternion.copy(capRest.quaternion);
    group.add(cap);
    // how the cap sits on the claudesona's normalized head bone (measured on claude_suit.vrm, see CORRIDOR_NEWS.md)
    const capFit = { pos: new T.Vector3(...(opts.capFitPos ?? [0, 0.13, 0.095])), rot: new T.Euler(...(opts.capFitRot ?? [-0.1, 0, 0])), scale: opts.capFitScale ?? 1.0 };

    // ─────────────────────────── lights ───────────────────────────
    const lights = new T.Group();
    lights.name = 'corridor_lights';
    group.add(lights);
    const spot = (col, I, pos, tgt, angle, pen) => {
        const l = new T.SpotLight(col, I, 0, angle, pen, 2);
        l.position.set(...pos); l.target.position.set(...tgt);
        lights.add(l, l.target);
        l.userData.base = I;
        return l;
    };
    const Ls = {
        key: spot(0xffd6a0, 300, [1.2, 9.2, 8.0], [0, 1.25, 0], 0.3, 0.8),
        // raking floor uplights on the door (their mirror images fall upward, away from the corridor's cameras)
        doorL: spot(0xffc06e, 170, [-2.3, 0.12, ZD + 2.6], [-0.9, 6.5, ZD], 0.42, 0.6),
        doorR: spot(0xffc06e, 170, [2.3, 0.12, ZD + 2.6], [0.9, 6.5, ZD], 0.42, 0.6),
        // a picture light raking down the plaque from under the crown
        plaque: spot(0xffdcaa, 40, [0, 10.75, ZD + 1.35], [0, 8.6, ZD], 0.62, 0.5),
        beyond: spot(0xffe9c8, 0, [0, 4.2, ZD - 2.5], [0, 0.6, 6], 0.3, 0.6),
        poll: spot(0xffdcaa, 110, [POLL_AT[0] + 1.8, 7.4, POLL_AT[1] + 4.2], [POLL_AT[0], 2.4, POLL_AT[1]], 0.36, 0.6),
        cap: spot(0xffe2b8, 30, [CAP_AT[0] + 0.7, 4.4, CAP_AT[1] + 1.4], [CAP_AT[0], 1.05, CAP_AT[1]], 0.22, 0.7),
        uniform: spot(0xffd8a8, 150, [UNIFORM_AT[0] + 2.0, 5.6, UNIFORM_AT[1] + 2.4], [UNIFORM_AT[0], 1.2, UNIFORM_AT[1]], 0.26, 0.7),
    };
    Ls.screen = new T.PointLight(0xc8dcff, 14, 0, 2); Ls.screen.position.set(HW - 1.4, 4.4, -10.0); lights.add(Ls.screen); Ls.screen.userData.base = 14;
    Ls.fill = new T.PointLight(0xffb070, 9, 0, 2); Ls.fill.position.set(0, 8.2, -4.0); lights.add(Ls.fill); Ls.fill.userData.base = 9;
    Ls.hemi = new T.HemisphereLight(0x3a2a1a, 0x0a0405, 0.06); lights.add(Ls.hemi); Ls.hemi.userData.base = 0.06;

    // ─────────────────────────── per-frame ───────────────────────────
    const ease = (x) => { const k = Math.max(0, Math.min(1, x)); return k * k * (3 - 2 * k); };
    const _m = new T.Matrix4(), _m2 = new T.Matrix4(), _p = new T.Vector3(), _q = new T.Quaternion(), _s = new T.Vector3();
    const _pa = new T.Vector3(), _qa = new T.Quaternion(), _sa = new T.Vector3(), _pb = new T.Vector3(), _qb = new T.Quaternion(), _sb = new T.Vector3();
    let lastPost = null, lastTally = null;
    function update(t, st = {}) {
        U.t.value = t;
        const open = ease(st.open ?? 0);
        U.open.value = open;
        U.beyond.value = st.beyond ?? 1;
        U.gap.value = st.gap ?? 1;
        U.screen.value = st.screen ?? 1;
        const lvl = st.lights ?? 1;
        U.lights.value = lvl;
        // the lanterns' slow breath (deterministic)
        U.flick.value = 1 + 0.025 * Math.sin(t * 2.3) + 0.015 * Math.sin(t * 5.7 + 1.3);
        const ang = open * 1.62;
        pivotL.rotation.y = ang; pivotR.rotation.y = -ang;
        for (const l of [Ls.key, Ls.doorL, Ls.doorR, Ls.plaque, Ls.poll, Ls.cap, Ls.uniform, Ls.screen, Ls.fill, Ls.hemi]) l.intensity = l.userData.base * lvl;
        Ls.screen.intensity = Ls.screen.userData.base * lvl * (st.screen ?? 1);
        Ls.beyond.intensity = 1500 * open * (st.beyond ?? 1);
        shafts.visible = open > 0.002;
        if (st.postText != null && st.postText !== lastPost) { lastPost = st.postText; setText(st.postText); }
        if (st.post != null) {     // redraw only when another character appears (the canvas + mips cost ~30 ms)
            const k = Math.max(0, Math.min(1, st.post)), n = Math.round(postState.text.length * k);
            if (n !== postState.shown || (k >= 1) !== (postState.reveal >= 1)) { postState.shown = n; postState.reveal = k; post.redraw(k); }
        }
        if (st.tally && String(st.tally) !== lastTally) { lastTally = String(st.tally); setTally(...st.tally); }
        // the cap: cushion → head along an arc (state.capOn 0..1, state.capHead = the normalized head bone)
        const on = ease(st.capOn ?? 0);
        group.updateWorldMatrix(true, false);
        if (st.capHead && on > 0) {
            capRest.updateWorldMatrix(true, false);
            capRest.matrixWorld.decompose(_pa, _qa, _sa);
            st.capHead.updateWorldMatrix(true, false);
            _m.compose(capFit.pos, new T.Quaternion().setFromEuler(capFit.rot), new T.Vector3(capFit.scale, capFit.scale, capFit.scale));
            _m2.multiplyMatrices(st.capHead.matrixWorld, _m);
            _m2.decompose(_pb, _qb, _sb);
            _p.lerpVectors(_pa, _pb, on); _p.y += Math.sin(on * Math.PI) * 0.45;
            _q.slerpQuaternions(_qa, _qb, on); _s.lerpVectors(_sa, _sb, on);
            _m.compose(_p, _q, _s);
            _m2.copy(group.matrixWorld).invert().multiply(_m);
            _m2.decompose(cap.position, cap.quaternion, cap.scale);
        } else {
            cap.position.copy(capRest.position); cap.quaternion.copy(capRest.quaternion); cap.scale.set(1, 1, 1);
        }
    }
    function setTally(a, b, c, o = {}) {
        tallyNow = [a, b, c].map((v) => Math.max(0, Math.round(v || 0)));
        Object.assign(pollOpts, o);
        drawPoll(tallyNow);
        lastTally = String(tallyNow);
    }

    const parts = {
        room, doors: { group: doors, left: pivotL, right: pivotR, leafL, leafR, seam },
        plaque: plaqueMesh, beyond, shafts,
        postWall: { mesh: screen, setText, get texture() { return post.texture; }, canvas: post.canvas, state: postState },
        poll: { group: poll, setTally, get tally() { return tallyNow.slice(); }, options: pollOpts },
        patch, uniform: uniform_, pedestal, cushion, cap, capRest, capFit,
        sconces: sconceGlass, lights: Ls, uniforms: U, materials: M,
    };
    const cams = {
        // her in the foreground, the door, the plaque and the poll board down the axis
        door: { pos: [0.55, 1.25, 6.2], target: [0, 4.6, ZD], fov: 38 },
        // Crali's dive down the gold tunnel: one-point perspective onto the door
        corridorWide: { pos: [0, 2.4, 19.5], target: [0, 4.2, ZD], fov: 44 },
        // the LED wall at an angle with her in the left of frame
        postWall: { pos: [-3.0, 1.6, 4.6], target: [HW, 4.4, -10.5], fov: 46 },
        // the cap on its cushion, the uniform and the patch beyond
        cap: { pos: [-1.35, 1.42, 0.25], target: [CAP_AT[0] - 0.25, 1.12, CAP_AT[1] - 0.6], fov: 34 },
        // the poll board, the door beyond it
        poll: { pos: [-0.9, 2.3, -12.6], target: [POLL_AT[0] - 0.35, 2.45, POLL_AT[1]], fov: 40 },
    };
    function dispose() {
        group.parent?.remove(group);
        L.disposeAll();
    }
    update(0, {});
    return {
        group, parts, update, dispose, cams,
        focal: new T.Vector3(0, 5.2, ZD + 0.2),          // the door: the aeropittura's sun cones come from here
        look: { name: 'argue', exposure: 1.0, bloom: { strength: 0.55, radius: 0.5, threshold: 0.7 }, fog: null },
    };
}
