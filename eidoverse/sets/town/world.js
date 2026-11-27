// eidoverse/sets/town/world.js — the town's light and air, in the three.js edition's own way:
//
//   const W = await world(THREE, { scene, camera, renderer, root });   // the sun, makeSky's Earth sky, the dust in the air
//   per frame: W.update(t)   (before the render; the sky owns its update order)
//
// THE SUN stands 50 degrees up, from the south-east of the town's own axes (SUN_DIR: the way its light travels, in the
// town's +Z-up metres), so every parapet, tank and car draws itself with a shadow: a desert's hard sun.
// THE SKY is the sky family's (eidoverse/sky_worlds.js, makeSky: world 'earth', clear): its hour is solved so its sun
// stands at the town's 50 degrees (the afternoon root of its arc), and the town's root is turned about the vertical so
// the town's own sun direction meets the sky's sun (the ocean set's way: the layout turns, the sky stays the package's
// own). Its sun and sky are retinted toward a dusty country's (SKY_FAMILY: a warmer sun, a paler, warmer sky low down)
// and the exposure is raised to the town's balance between sun and sky.
// THE AIR is dust held in the air: a fog whose extinction is the Blender edition's volume's (0.00042 per metre: a
// third of the light at a kilometre, three quarters at 3.5 km), its colour the lit dust's, so the town greys into the
// distance and fades into its plain. sky: null leaves the scene's sky alone and only makes the sun.
export const SUN_DIR = (() => { const v = [-0.45, 0.5, -0.80]; const l = Math.hypot(...v); return v.map((x) => x / l); })();
// (exposure: stops on the AgX tone map; fill: the share of the sky package's own fill (its hemisphere light and its
// baked environment) the town is lit with, the Blender edition's make_sky ambient)
export const SKY_FAMILY = { clouds: 'clear', sun_tint: [1.0, 0.94, 0.82], sky_tint: [1.25, 1.0, 0.7], exposure: 0.5, fill: 0.35 };
export const AIR = { density: 0.00042, color: [0.86, 0.78, 0.66] };

// the sky family's hour for a sun `el` degrees up (the afternoon root of sin((h - 6) / 12 pi) * elMax)
export function skyHours(el, elMax = 62.0) {
    if (el >= elMax) throw new Error(`[town] the sun at ${el.toFixed(1)} degrees is above the sky family's highest (${elMax})`);
    return 6.0 + 12.0 * (1.0 - Math.asin(el / elMax) / Math.PI);
}

export async function world(THREE, { scene, camera, renderer, root, sky = 'sky', haze = true, hazeColor = null, exposure = SKY_FAMILY.exposure,
    fill = SKY_FAMILY.fill, sunTint = SKY_FAMILY.sun_tint, skyTint = SKY_FAMILY.sky_tint, shadow = { size: 4096, extent: 320 }, log = console.log } = {}) {
    const toSun = SUN_DIR.map((v) => -v);                            // in the town's metres
    const el = Math.asin(toSun[2]) * 180 / Math.PI;
    const sun = new THREE.DirectionalLight(0xffffff, 3.0);
    sun.castShadow = !!shadow;
    if (shadow) {
        sun.shadow.mapSize.set(shadow.size, shadow.size);
        const e = shadow.extent;
        Object.assign(sun.shadow.camera, { left: -e, right: e, top: e, bottom: -e, near: 1, far: 3000 });
        sun.shadow.bias = -0.0004;
        sun.shadow.normalBias = 0.04;
    }
    const hemi = new THREE.HemisphereLight(0xdfe6ff, 0x5a4a38, 0.4);
    scene.add(sun, sun.target, hemi);
    let S = null;
    const hours = skyHours(el);
    if (sky) {
        eval(Deno.readTextFileSync(new URL('../../sky_worlds.js', import.meta.url)));
        S = await globalThis.makeSky({ scene, camera, renderer, sun, hemi, world: 'earth', hours, clouds: SKY_FAMILY.clouds, weather: 'clear', audio: false });
        S.setTime(hours);
        S.setColors({ sun: sunTint, sky: skyTint });
        // turn the town so its own sun direction meets the sky's: the azimuth of each, about the world's +Y
        const sd = S.sunDir;
        const tw = new THREE.Vector3(toSun[0], toSun[2], -toSun[1]);  // the town's to-sun in the world, the root unturned
        const turn = Math.atan2(tw.z, tw.x) - Math.atan2(sd.z, sd.x);
        root.rotation.set(-Math.PI / 2, 0, 0);
        root.rotateOnWorldAxis(new THREE.Vector3(0, 1, 0), turn);
        root.updateMatrixWorld(true);
        log(`[town] sky family: hour ${hours.toFixed(3)}; the town turned ${(turn * 180 / Math.PI).toFixed(1)} degrees to meet its sun`);
    }
    renderer.toneMapping = THREE.AgXToneMapping;
    renderer.toneMappingExposure = 2 ** exposure;
    const sunWorld = () => {
        root.updateMatrixWorld(true);
        return new THREE.Vector3(toSun[0], toSun[1], toSun[2]).transformDirection(root.matrixWorld).normalize();
    };
    // the sun's shadow frustum follows the camera's ground point, so one 4k map covers what the lens sees
    const placeSun = () => {
        const d = sunWorld();
        const c = new THREE.Vector3();
        camera.getWorldDirection(c);
        const g = camera.position.clone();
        if (c.y < -0.05) g.addScaledVector(c, Math.min(600, -camera.position.y / c.y));
        else g.addScaledVector(c, 120);
        g.y = 0;
        sun.target.position.copy(g);
        sun.position.copy(g).addScaledVector(d, 1500);
        sun.target.updateMatrixWorld();
    };
    let fogColor = null;
    if (haze) {
        const { fog, uniform, float, exp, positionView, vec3 } = THREE;
        const c = hazeColor || [AIR.color[0] * 0.62, AIR.color[1] * 0.62, AIR.color[2] * 0.62];
        fogColor = uniform(new THREE.Color(...c));
        scene.fogNode = fog(fogColor, float(1.0).sub(exp(positionView.length().mul(-AIR.density))));
    }
    if (S) await S.bakeEnv();
    scene.environmentIntensity = fill;
    const settle = () => { hemi.intensity *= fill; placeSun(); };   // (after the sky has set its lights for the frame)
    if (S) S.update(0);
    settle();
    return {
        sun, hemi, sky: S, hours, fogColor, sunWorld,
        update(t) { if (S) S.update(t); settle(); },
        placeSun,
    };
}
