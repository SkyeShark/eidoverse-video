// The mesh and API package's renders (PORT_PLAN.md 7.3, 8.2 P4): the port of
// blender/tests/terrain/mesh_api/render_lauterbrunnen.py, and the grazing crack views along every seam.
//
//     deno run --allow-all --unstable-webgpu --node-modules-dir=auto eidoverse/render_scene.mjs eidoverse/terrain/tests/mesh_api/render_lauterbrunnen.json
//
// (from the repository root; on a shared machine put $EIDO_GPU_WRAP in front). A scene script for the edition's
// renderer. real_place Lauterbrunnen at film quality with hero levels, read from the Blender save the API fixtures
// name (out/mesh_api/api_fixtures/lauterbrunnen_film; the level runner, run.js, is another package's): Terrain.load
// builds the ring mesh, the collider proxy, the exact ray caster and the lakes, as makeTerrain builds them. Lit as
// the reference rig lights a view: the sun 37.7 degrees up, 70 degrees left of the view heading, over grey clay
// (albedo 0.18), AgX; a hemisphere fill stands in for make_sky's sky (the reference views' rig is the parity
// package's). My robot body (claude_robot.vrm) stands 14 m in front of the reference's eye camera and 1.6 m right
// of the sight line, facing the camera, set down as Blender's characters.ground_vrm sets a body down on
// Ground(fn=t.height_at): the lowest posed foot point onto heightAt; its feet are then measured against heightAt and
// against the rendered triangles (the exact ray caster, straight down).
//
// One frame a view (1 fps; the config captures every frame as <output>_at<s>s.png):
//   0 eye_clay           the reference's eye camera (renders/lauterbrunnen_views.json), the robot in front
//   1 eye_levels         the same, the ground coloured by ring level (unlit): where each seam runs
//   2 feet_clay          the robot's feet from 3 m, 0.6 m up
//   3 seams_clay         45 degrees down from 1.1 km onto the eye spot: hero windows' borders cross the frame
//   4 seams_clay_lowsun  the same with the sun 8 degrees up, grazing (creases show most)
//   5 seams_levels       the same, coloured by level
//   6.. graze_<k>        for every seam k (ring k's border): a camera 2 m above the ground on the border line, looking
//                        along it; lit clay in the frame, and the crack test beside it: the same view at 2x
//                        (1920 x 1080, 4x MSAA), unlit: the terrain's front faces black, its back faces (the same
//                        triangles drawn again) magenta and pushed back by a depth bias, a magenta backdrop under
//                        the whole outermost window, a black sky. From above the ground a line of sight meets a back
//                        face, the skirt from inside or the backdrop only through a hole in the surface (a ray
//                        leaving the window never comes back under it), and the bias keeps a back face behind the
//                        front face that covers it (crests, where the two tie), so every magenta pixel is a crack,
//                        whichever way the view looks. Counted, and written as graze_<k>_cracks.png. The control
//                        (graze_<k>_control.png) takes one triangle of the seam out, the one the ray caster finds
//                        beside the frame's centre line three quarters of the way down: that hole must show magenta
// The record, out/mesh_api/renders/lauterbrunnen_renders.json: cameras, the sun, the robot's shift and foot gaps, the
// crack counts per seam.

const OUT_REL = 'terrain/tests/out/mesh_api/renders/';
const VIEWS = ['eye_clay', 'eye_levels', 'feet_clay', 'seams_clay', 'seams_clay_lowsun', 'seams_levels'];
const SUN_LEFT_DEG = 70.0, SUN_ELEV_DEG = 37.74320827374035, LOW_SUN_ELEV_DEG = 8.0, EYE_HEIGHT = 1.7;
const LEVEL_COLOURS = [[0.1, 0.1, 0.1], [0.2, 0.3, 0.9], [0.1, 0.7, 0.8], [0.2, 0.8, 0.2], [0.9, 0.8, 0.1],
    [0.9, 0.4, 0.1], [0.9, 0.1, 0.3], [0.9, 0.9, 0.9]];     // render_lauterbrunnen.py level_material's ramp

const B2T = (x, y, z) => new THREE.Vector3(x, z, -y);      // Blender (x, y, z) -> three.js (x, z, -y)

// the ground coloured by ring level, unlit (render_lauterbrunnen.py level_material: level k -> colour k)
function levelsMaterial() {
    const lev = THREE.attribute('eido_level', 'float');
    let c = THREE.vec3(...LEVEL_COLOURS[7]);
    for (let k = 6; k >= 0; k--) c = THREE.select(lev.lessThan(k + 0.5), THREE.vec3(...LEVEL_COLOURS[k]), c);
    const m = new THREE.MeshBasicNodeMaterial();
    m.colorNode = c;
    m.name = 'levels';
    return m;
}

const flat = (r, g, b, name) => {
    const m = new THREE.MeshBasicNodeMaterial();
    m.color.setRGB(r, g, b);
    m.toneMapped = false;
    m.name = name;
    return m;
};

// the crack test's back faces: magenta, pushed back by a depth bias (slope-scaled and constant), so where a front
// face covers them they lose even the exact depth ties along a crest's shared edges, and win only through a hole
const backFaces = () => {
    const m = flat(1, 0, 1, 'crack_back');
    m.side = THREE.BackSide;
    m.polygonOffset = true;
    m.polygonOffsetFactor = 2;
    m.polygonOffsetUnits = 8;
    return m;
};

// the posed vertices of each foot: every skinned vertex whose strongest weight is that side's Foot or Toes bone (as
// eidoverse/examples/claude_robot.js picks them)
function footSets(vrm) {
    const out = { left: [], right: [] };
    for (const side of ['left', 'right']) {
        const bones = new Set([`${side}Foot`, `${side}Toes`].map((n) => vrm.humanoid.getRawBoneNode(n)).filter(Boolean));
        vrm.scene.traverse((m) => {
            const si = m.isSkinnedMesh ? m.geometry.attributes.skinIndex : null, sw = si ? m.geometry.attributes.skinWeight : null;
            if (!sw) return;
            const verts = [];
            for (let i = 0; i < si.count; i++) {
                let best = 0, bw = -1;
                for (let k = 0; k < 4; k++) {
                    const w = sw.getComponent(i, k);
                    if (w > bw) { bw = w; best = si.getComponent(i, k); }
                }
                if (bones.has(m.skeleton.bones[best])) verts.push(i);
            }
            if (verts.length) out[side].push({ m, verts });
        });
    }
    return out;
}

function footPoints(sets) {
    const v = new THREE.Vector3(), P = [];
    for (const { m, verts } of sets) for (const i of verts) P.push(m.getVertexPosition(i, v).applyMatrix4(m.matrixWorld).clone());
    return P;
}

// characters.ground_vrm on Ground(fn=height_at): lower (or raise) the body so the lowest foot point of either foot
// touches the ground under it; returns the vertical shift applied
function groundVrm(vrm, feet, heightAt) {
    vrm.scene.updateMatrixWorld(true);
    let gap = Infinity;
    for (const side of ['left', 'right']) for (const p of footPoints(feet[side])) gap = Math.min(gap, p.y - heightAt(p.x, p.z));
    if (!Number.isFinite(gap)) return 0;
    vrm.scene.position.y -= gap;
    vrm.scene.updateMatrixWorld(true);
    return -gap;
}

function aim(cam, eye, target, lensMm) {
    cam.position.copy(eye);
    cam.up.set(0, 1, 0);
    cam.lookAt(target);
    cam.filmGauge = 36;
    cam.setFocalLength(lensMm);
    cam.updateMatrixWorld(true);
    cam.updateProjectionMatrix();
}

// the sun SUN_LEFT_DEG left of the camera's heading (render_lauterbrunnen.py render(): the heading's angle in
// Blender's ground plane plus 70 degrees), `elev` degrees up, its shadow frustum around `centre`
function placeSun(S, cam, elev, centre) {
    const d = new THREE.Vector3();
    cam.getWorldDirection(d);
    const hd = Math.atan2(-d.z, d.x) + SUN_LEFT_DEG * Math.PI / 180;      // Blender's atan2(d.y, d.x)
    const e = elev * Math.PI / 180;
    const dir = new THREE.Vector3(Math.cos(e) * Math.cos(hd), Math.sin(e), -Math.cos(e) * Math.sin(hd));
    S.sun.position.copy(centre).addScaledVector(dir, 200);
    S.sun.target.position.copy(centre);
    S.sun.target.updateMatrixWorld(true);
    S.sun.updateMatrixWorld(true);
    return [dir.x, -dir.z, dir.y];                                     // Blender axes, for the record
}

function setGround(S, which) {
    const one = { levels: S.levels, black: S.black }[which];
    S.t.mesh.material = one ? [one, one] : S.clay;
}

globalThis.setup = async function () {
    const t0 = performance.now();
    const base = new URL('terrain/', EIDOVERSE_DIR);
    const TM = await import(new URL('index.js', base).href);
    const C = await import(new URL('tests/mesh_api/_common.mjs', base).href);
    const G = await import(new URL('core/gpu.js', base).href);
    const Io = await import(new URL('core/io.js', base).href);
    const outDir = C.urlPath(new URL(OUT_REL, EIDOVERSE_DIR));
    Deno.mkdirSync(outDir, { recursive: true });

    const renderer = new THREE.WebGPURenderer({ canvas, antialias: true, adapter: GPU_ADAPTER, device: GPU_DEVICE });
    renderer.setSize(WIDTH, HEIGHT);
    renderer.outputColorSpace = THREE.SRGBColorSpace;
    renderer.toneMapping = THREE.AgXToneMapping;
    renderer.toneMappingExposure = Math.SQRT2;                      // the reference rig's +0.5 EV
    renderer.shadowMap.enabled = true;
    renderer.shadowMap.type = THREE.PCFSoftShadowMap;
    await renderer.init();
    globalThis._noAutoEnhance = true;                             // raw frames: the seams as drawn
    globalThis._noAutoPlacementCheck = true;

    // the terrain, from the Blender save the API fixtures name
    const man = C.manifest('lauterbrunnen_film', C.API_FIXTURES);
    const save = C.blenderPath(man.save);
    if (!save) throw new Error('render_lauterbrunnen: no Blender edition (set EIDO_BLENDER_EDITION) for the save ' + man.save);
    const t = await TM.Terrain.load(save, { name: 'lauterbrunnen', meshMasks: [], plants: false, THREE, renderer, log: () => {} });
    const scene = new THREE.Scene();
    scene.add(t.mesh, ...t.water.lakes);
    if (t.water.sea) scene.add(t.water.sea);
    const clay = t.mesh.material;
    const sky = new THREE.Color().setRGB(0.42, 0.56, 0.74);
    scene.background = sky;
    const hemi = new THREE.HemisphereLight(0xc4d6ee, 0x5a5348, 0.9);
    scene.add(hemi);
    const sun = new THREE.DirectionalLight(0xfff1e0, 3.2);
    sun.castShadow = true;
    sun.shadow.mapSize.set(2048, 2048);
    Object.assign(sun.shadow.camera, { left: -6, right: 6, top: 6, bottom: -6, near: 1, far: 400 });
    sun.shadow.bias = -0.0004;
    sun.shadow.normalBias = 0.02;
    scene.add(sun, sun.target);

    // the robot: 14 m in front of the eye camera, 1.6 m right of the sight line, facing the camera
    const views = JSON.parse(Deno.readTextFileSync(`${C.blenderEdition()}/blender/tests/terrain/reference/renders/lauterbrunnen_views.json`));
    const refEye = views.eye;
    const [ex, ey] = refEye.camera, [tx, ty] = refEye.target;
    const L = Math.hypot(tx - ex, ty - ey), ux = (tx - ex) / L, uy = (ty - ey) / L;
    const rx = ex + 14.0 * ux + 1.6 * uy, ry = ey + 14.0 * uy - 1.6 * ux;
    const hAt = (x, z) => t.heightAt(x, z);                       // three.js (x, z)
    // the body's metadata names its licence, CC BY 4.0, which three-vrm's metadata plugin refuses unless it is listed
    const { VRMMetaLoaderPlugin } = await import('npm:@pixiv/three-vrm@3.5.2');
    const loader = new globalThis.GLTFLoader();
    loader.register((p) => new globalThis.VRMLoaderPlugin(p, { metaPlugin: new VRMMetaLoaderPlugin(p,
        { acceptLicenseUrls: ['https://vrm.dev/licenses/1.0/', 'https://creativecommons.org/licenses/by/4.0/'] }) }));
    const gltf = await new Promise((res, rej) => loader.parse(globalThis.b64toArrayBuffer(globalThis.ASSETS.robot), '', res, rej));
    const vrm = gltf.userData.vrm;
    vrm.scene.traverse((o) => { if (o.isMesh) { o.castShadow = true; o.receiveShadow = true; o.frustumCulled = false; } });
    // arms lowered from the rest pose (a body at rest, not a T)
    vrm.humanoid.getNormalizedBoneNode('leftUpperArm').rotation.z = -1.25;
    vrm.humanoid.getNormalizedBoneNode('rightUpperArm').rotation.z = 1.25;
    vrm.update(0);
    const face = Math.atan2(ex - rx, -(ey - ry));                   // +Z toward the camera
    vrm.scene.position.copy(B2T(rx, ry, hAt(rx, -ry)));
    vrm.scene.rotation.y = face;
    scene.add(vrm.scene);
    const feet = footSets(vrm);
    const shift = groundVrm(vrm, feet, hAt);
    const rc = new THREE.Raycaster();
    const gaps = {};
    for (const side of ['left', 'right']) {
        const P = footPoints(feet[side]);
        if (!P.length) continue;
        let lo = Infinity, hi = -Infinity, low = null;
        for (const p of P) {
            const g = p.y - hAt(p.x, p.z);
            if (g < lo) { lo = g; low = p; }
            hi = Math.max(hi, g);
        }
        rc.set(new THREE.Vector3(low.x, low.y + 2.0, low.z), new THREE.Vector3(0, -1, 0));
        const hit = rc.intersectObject(t.mesh, false)[0];
        gaps[side] = { points: P.length, min_gap_m: lo, max_gap_m: hi, lowest_point_above_rendered_ground_m: hit ? low.y - hit.point.y : null };
    }
    console.log(`[render_lauterbrunnen] robot at (${rx.toFixed(1)}, ${ry.toFixed(1)}) Blender, ground shift ${shift.toFixed(4)} m, feet ${JSON.stringify(gaps)}`);

    // the crack test's pieces: black ground, a magenta backdrop under the whole outermost window, a 2x target
    const [xmin, ymin, xmax, ymax] = t.ring.bounds();
    const backdrop = new THREE.Mesh(new THREE.PlaneGeometry(xmax - xmin, ymax - ymin), flat(1, 0, 1, 'backdrop'));
    backdrop.rotation.x = -Math.PI / 2;
    backdrop.position.set(0.5 * (xmin + xmax), t.ring.heightRange[0] - 200.0, -0.5 * (ymin + ymax));
    backdrop.visible = false;
    scene.add(backdrop);
    const back = new THREE.Mesh(t.mesh.geometry, backFaces());     // the same triangles, their undersides
    back.visible = false;
    scene.add(back);
    const crackRT = new THREE.RenderTarget(2 * WIDTH, 2 * HEIGHT, { samples: 4 });
    const camera = new THREE.PerspectiveCamera(50, WIDTH / HEIGHT, 0.05, 80000);

    globalThis._r = renderer;
    globalThis._s = scene;
    globalThis._c = camera;
    globalThis._L = { t, TM, C, G, Io, renderer, scene, camera, sun, hemi, sky, clay, levels: levelsMaterial(),
        black: flat(0, 0, 0, 'crack_front'), back, backdrop, crackRT, vrm, outDir,
        ex, ey, tx, ty, ux, uy, rx, ry, hAt, refEye,
        rec: { save: man.save, terrain: { levels: t.levels.map(String), triangles: t.ring.triangleCount, rings: t.ring.rings.length },
            robot: { at_blender: [rx, ry], facing_deg: face * 180 / Math.PI, ground_vrm_shift_m: shift, feet: gaps },
            views: {}, cracks: {}, setup_s: +((performance.now() - t0) / 1000).toFixed(1) } };
    writeRecord();
};

function writeRecord() {
    const S = globalThis._L;
    Deno.writeTextFileSync(`${S.outDir}/lauterbrunnen_renders.json`, JSON.stringify(S.rec, null, 1));
}

// the camera of a seam's grazing view: on ring k's border line, 2 m above the ground, looking along the line at the
// ground a few dozen parent spacings ahead; the side turns with k, so the seams show every fan orientation
function grazeCamera(S, k) {
    const rm = S.t.ring, r = rm.rings[k], P = rm.rings[k - 1];
    const side = (k - 1) % 4;                                   // 0 south (east-going), 1 east, 2 north, 3 west
    const x0 = r.xm[0], x1 = r.xm[r.nx - 1], y0 = r.ym[0], y1 = r.ym[r.ny - 1];
    const len = side % 2 ? y1 - y0 : x1 - x0;
    const ahead = Math.min(0.6 * len, 40 * P.spec.sp * rm.unit);
    const s = 0.08 * len;
    let a, b;                                                    // Blender ground points: the camera's and the target's
    if (side === 0) { a = [x0 + s, y0]; b = [x0 + s + ahead, y0]; }
    else if (side === 1) { a = [x1, y0 + s]; b = [x1, y0 + s + ahead]; }
    else if (side === 2) { a = [x1 - s, y1]; b = [x1 - s - ahead, y1]; }
    else { a = [x0, y1 - s]; b = [x0, y1 - s - ahead]; }
    const eye = B2T(a[0], a[1], S.hAt(a[0], -a[1]) + 2.0), target = B2T(b[0], b[1], S.hAt(b[0], -b[1]));
    return { eye, target, side: ['south', 'east', 'north', 'west'][side], ahead_m: ahead,
        spacing_m: [P.spec.sp * rm.unit, r.spec.sp * rm.unit] };
}

// the magenta pixels of a readback (any coverage: the 4x samples resolve a sub-pixel hole to a dim magenta)
function magenta(px, W) {
    let n = 0, first = null;
    for (let q = 0; q < px.length; q += 4) {
        const r = px[q], g = px[q + 1], b = px[q + 2];
        if (r > 6 && b > 6 && g * 2 < Math.min(r, b)) {
            n++;
            if (!first) first = [(q / 4) % W, Math.floor(q / 4 / W)];
        }
    }
    return [n, first];
}

// the terrain's front faces with one triangle taken out (made degenerate), sharing the vertex buffer: the control's
// hole. One index copy, its one changed triangle written back and the next taken out by update ranges
function holed(S, face) {
    const g = S.t.mesh.geometry;
    if (!S.holed) {
        const g2 = new THREE.BufferGeometry();
        g2.setAttribute('position', g.getAttribute('position'));
        g2.setIndex(new THREE.BufferAttribute(g.index.array.slice(), 1));
        g2.boundingBox = g.boundingBox.clone();
        g2.boundingSphere = g.boundingSphere.clone();
        S.holed = { mesh: new THREE.Mesh(g2, S.black), face: -1 };
        S.holed.mesh.visible = false;
        S.scene.add(S.holed.mesh);
    }
    const H = S.holed, idx = H.mesh.geometry.index, a = idx.array, orig = g.index.array;
    if (H.face >= 0) {
        a.set(orig.subarray(3 * H.face, 3 * H.face + 3), 3 * H.face);
        idx.addUpdateRange(3 * H.face, 3);
    }
    a[3 * face + 1] = a[3 * face + 2] = a[3 * face];
    idx.addUpdateRange(3 * face, 3);
    idx.needsUpdate = true;
    H.face = face;
    return H.mesh;
}

async function crackTest(S, k, cam) {
    const { renderer, scene, crackRT } = S;
    const bg = scene.background;
    S.vrm.scene.visible = false;
    for (const l of S.t.water.lakes) l.visible = false;
    S.backdrop.visible = true;
    scene.background = new THREE.Color(0, 0, 0);
    const c2 = cam.clone();
    c2.aspect = crackRT.width / crackRT.height;
    c2.updateProjectionMatrix();
    const W = crackRT.width;
    const shot = async () => {
        renderer.setRenderTarget(crackRT);
        await renderer.renderAsync(scene, c2);
        renderer.setRenderTarget(null);
        return renderer.readRenderTargetPixelsAsync(crackRT, 0, 0, W, crackRT.height);
    };
    // the control: a triangle of the seam taken out, the one just beside the frame's centre line three quarters of
    // the way down (the camera stands on the seam line and looks along it, so that ray meets the ground at the seam;
    // a ray exactly along the line runs through the edges two triangles share, where three's triangle test can
    // reject both on a last bit, the brute-force loop as much as the ray caster); the hole must show
    const rc = new THREE.Raycaster();
    rc.setFromCamera(new THREE.Vector2(0.01, -0.5), c2);
    rc.firstHitOnly = true;
    const hit = rc.intersectObject(S.t.mesh, false)[0] ?? null;
    S.back.visible = true;
    let control = null, controlPx = null, holeAt = null;
    if (hit) {
        const h = holed(S, hit.faceIndex);
        S.t.mesh.visible = false;
        h.visible = true;
        controlPx = await shot();
        [control] = magenta(controlPx, W);
        h.visible = false;
        S.t.mesh.visible = true;
        const q = hit.point.clone().project(c2);
        holeAt = [Math.round((q.x + 1) / 2 * W), Math.round((1 - q.y) / 2 * crackRT.height)];
    }
    setGround(S, 'black');
    const px = await shot();
    S.back.visible = false;
    scene.background = bg;
    S.backdrop.visible = false;
    S.vrm.scene.visible = true;
    for (const l of S.t.water.lakes) l.visible = true;
    setGround(S, 'clay');
    const [n, first] = magenta(px, W);
    // the 2x frames as PNGs (samples on the GPU, one u32 a sample, as core/io.js encodes them)
    const R = await S.G.init();
    for (const [what, data] of [['cracks', px], ['control', controlPx]]) {
        if (!data) continue;
        const f = R.field(crackRT.height, 4 * W, 1, Uint32Array.from(data), 'u32');
        await S.Io.writePng(`${S.outDir}/lauterbrunnen_graze_${k}_${what}.png`, { field: f, width: W, height: crackRT.height, channels: 4, bitDepth: 8 });
        f.destroy();
    }
    return { magenta_pixels: n, first_at_px: first, control_magenta_pixels: control, control_face: hit?.faceIndex ?? null,
        control_distance_m: hit?.distance ?? null, control_hole_at_px: holeAt, size: [W, crackRT.height] };
}

globalThis.renderFrame = async function (_time, frame) {
    const S = globalThis._L;
    const { camera, renderer, scene, t } = S;
    const name = frame < VIEWS.length ? VIEWS[frame] : `graze_${frame - VIEWS.length + 1}`;
    const eyeZ = S.hAt(S.ex, -S.ey) + EYE_HEIGHT;
    const robot = B2T(S.rx, S.ry, S.hAt(S.rx, -S.ry));
    let rec = {};
    setGround(S, 'clay');
    if (name.startsWith('eye')) {
        aim(camera, B2T(S.ex, S.ey, eyeZ), B2T(...S.refEye.target), S.refEye.lens_mm);
        camera.near = 0.05;
        rec.sun_dir = placeSun(S, camera, SUN_ELEV_DEG, robot);
        if (name === 'eye_levels') setGround(S, 'levels');
    } else if (name === 'feet_clay') {
        const fx = S.rx - 3.0 * S.ux + 0.8 * S.uy, fy = S.ry - 3.0 * S.uy - 0.8 * S.ux;
        aim(camera, B2T(fx, fy, S.hAt(fx, -fy) + 0.6), B2T(S.rx, S.ry, S.hAt(S.rx, -S.ry) + 0.15), 40.0);
        camera.near = 0.02;
        rec.sun_dir = placeSun(S, camera, SUN_ELEV_DEG, robot);
    } else if (name.startsWith('seams')) {
        const back = 1100.0 * Math.cos(Math.PI / 4);
        const cx = S.ex - back * S.ux, cy = S.ey - back * S.uy;
        aim(camera, B2T(cx, cy, eyeZ + 1100.0 * Math.sin(Math.PI / 4)), B2T(S.ex, S.ey, eyeZ), 35.0);
        camera.near = 1.0;
        rec.sun_dir = placeSun(S, camera, name === 'seams_clay_lowsun' ? LOW_SUN_ELEV_DEG : SUN_ELEV_DEG, robot);
        if (name === 'seams_levels') setGround(S, 'levels');
    } else {
        const k = frame - VIEWS.length + 1;
        if (k >= t.ring.rings.length) {                          // past the last seam: the eye view again
            aim(camera, B2T(S.ex, S.ey, eyeZ), B2T(...S.refEye.target), S.refEye.lens_mm);
        } else {
            const g = grazeCamera(S, k);
            aim(camera, g.eye, g.target, 35.0);
            camera.near = 0.05;
            rec = { side: g.side, ahead_m: g.ahead_m, spacing_m: g.spacing_m };
            rec.sun_dir = placeSun(S, camera, SUN_ELEV_DEG, g.eye);
            rec.cracks = await crackTest(S, k, camera);
            S.rec.cracks[k] = rec.cracks;
            console.log(`[render_lauterbrunnen] seam ${k} (${g.spacing_m.join(' -> ')} m, ${g.side} border): ${rec.cracks.magenta_pixels} magenta ` +
                `pixels at 2x; with the seam's triangle ${rec.cracks.control_distance_m?.toFixed(1)} m ahead taken out: ${rec.cracks.control_magenta_pixels}`);
        }
    }
    camera.far = 80000;
    camera.aspect = WIDTH / HEIGHT;
    camera.updateProjectionMatrix();
    rec.camera_blender = [camera.position.x, -camera.position.z, camera.position.y];
    rec.lens_mm = camera.getFocalLength();
    S.rec.views[name] = rec;
    writeRecord();
    await renderer.renderAsync(scene, camera);
};
