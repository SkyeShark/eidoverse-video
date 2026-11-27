// The helicopter (eidoverse/props/helicopter.js) flying low over a plain on a summer afternoon: the engine's sky
// (sky_worlds.js, earth, cumulus), a Poly Haven aerial ground set tiled to the horizon and hazing into it, the rotors
// turning at their own speeds, the camera keeping pace off the aircraft's sunlit side.
//
//   python eido.py render eidoverse/examples/helicopter/flight.json
//   python eido.py render eidoverse/examples/helicopter/flight.json --at 1 --at 6 --at 11      # stills
//
// The first run fetches the ground set (aerial_grass_rock, CC0) into eidoverse/assets/cache/. A rotor at 258 rpm
// turns 64.5 degrees a frame at 24 fps: four blades then strobe as a filmed rotor does. The engine's own post chain
// (auto-enhance) stays on: the sky system draws through it. Shadow maps stay off: with the sky facade on this stack
// they make one of its pipelines invalid (two "ShaderModule ... invalid" errors, the clouds lost).

const SPEED = 32;            // m/s along the path (about 62 knots)
const ALT = 38;              // m above the plain
const Y = new THREE.Vector3(0, 1, 0), Z = new THREE.Vector3(0, 0, 1), X = new THREE.Vector3(1, 0, 0);
let TURN = 0;                // the path's heading in the world, set in setup so that the camera side faces the sun

// the path in its own frame (forward along -x with a slow weave in z), turned by TURN
function pathAt(t) {
    return new THREE.Vector3(-SPEED * t + 180, ALT + 2.5 * Math.sin(t * 0.21), 22 * Math.sin(t * 0.32)).applyAxisAngle(Y, TURN);
}

globalThis.setup = async function () {
    const renderer = new THREE.WebGPURenderer({ canvas, antialias: true, adapter: GPU_ADAPTER, device: GPU_DEVICE });
    await renderer.init();
    renderer.setSize(WIDTH, HEIGHT);
    renderer.toneMapping = THREE.ACESFilmicToneMapping;
    renderer.toneMappingExposure = 0.85;
    const scene = new THREE.Scene();
    const camera = new THREE.PerspectiveCamera(34, WIDTH / HEIGHT, 0.5, 9000);
    const sun = new THREE.DirectionalLight(0xffffff, 3.0);
    const hemi = new THREE.HemisphereLight(0xbfd8ff, 0x5b5a3c, 0.6);
    scene.add(sun, sun.target, hemi);

    eval(Deno.readTextFileSync('eidoverse/sky_worlds.js'));
    const sky = await globalThis.makeSky({ scene, camera, renderer, sun, hemi, world: 'earth', hours: 16.5,
        clouds: 'cumulus', weather: 'clear' });
    await sky.bakeEnv();
    sky.update(0);
    // the aircraft's left (its local +Z at heading 0) toward the sun, a little ahead of it: the side the camera sees
    const sd = sky.sunDir ?? new THREE.Vector3(0.5, 0.6, 0.6);
    TURN = Math.atan2(sd.x, sd.z) + 0.45;

    // the plain: a Poly Haven aerial set at 18 m a tile, read twice (the second turned and 2.7 times larger) and
    // blended by a slow noise, its tone varied over 150 m, so the tiling does not show; it hazes into the horizon's
    // colour with distance (the sky draws its own atmosphere, so the scene has no fog of its own)
    const { texture, mix, smoothstep, mx_fractal_noise_float, positionWorld, cameraPosition, float, vec2, vec3, exp, distance } = THREE;
    const g = await globalThis.loadPBR('aerial_grass_rock', { res: '2k', maps: ['diff', 'normal', 'rough'] });
    for (const t of [g.map, g.normalMap, g.roughnessMap]) t.wrapS = t.wrapT = THREE.RepeatWrapping;
    const SIZE = 9000, TILE = 18;
    const ground = new THREE.Mesh(new THREE.PlaneGeometry(SIZE, SIZE), new THREE.MeshStandardNodeMaterial());
    const xz = vec2(positionWorld.x, positionWorld.z);
    const tuv = xz.div(TILE), tuv2 = vec2(xz.x.mul(0.8).sub(xz.y.mul(0.6)), xz.x.mul(0.6).add(xz.y.mul(0.8))).div(TILE * 2.7).add(0.37);
    const n3 = (s, o) => mx_fractal_noise_float(vec3(positionWorld.x, o, positionWorld.z).mul(s), 3, 2.0, 0.5).mul(0.5).add(0.5);
    const blend = smoothstep(0.38, 0.62, n3(1 / 45, 3.1)), tone = n3(1 / 150, 7.7);
    const col = mix(texture(g.map, tuv).rgb, texture(g.map, tuv2).rgb, blend).mul(tone.mul(0.5).add(0.75)).mul(vec3(1.0, 0.98, 0.9));
    const haze = float(1.0).sub(exp(distance(positionWorld, cameraPosition).mul(-1 / 2600)));
    ground.material.colorNode = col.mul(float(1.0).sub(haze.mul(0.85)));
    ground.material.roughnessNode = mix(texture(g.roughnessMap, tuv).g, texture(g.roughnessMap, tuv2).g, blend).mul(0.3).add(0.7);
    ground.material.normalNode = THREE.normalMap(mix(texture(g.normalMap, tuv), texture(g.normalMap, tuv2), blend));
    ground.material.emissiveNode = vec3(0.55, 0.62, 0.72).mul(haze.mul(haze).mul(0.9));
    ground.rotation.x = -Math.PI / 2;
    scene.add(ground);
    sky.wrapScene?.();

    const H = await import(new URL('props/helicopter.js', EIDOVERSE_DIR).href);
    const heli = await H.build(THREE);
    heli.group.userData.noSupportCheck = true;            // (it flies)
    scene.add(heli.group);
    globalThis._r = renderer; globalThis._s = scene; globalThis._c = camera;
    globalThis._flight = { heli, sky };
    console.log(`[flight] helicopter: ${Object.keys(heli.materials).length} materials; path turned ${(TURN * 180 / Math.PI).toFixed(0)} degrees`);
};

const _qa = new THREE.Quaternion(), _look = new THREE.Vector3(), _fwd = new THREE.Vector3();
// the camera, as a pure function of t (so --at stills and seeking agree): off the aircraft's left, a little above it,
// ahead at first and easing back toward the tail
function cameraAt(t) {
    const p = pathAt(t), ahead = pathAt(t + 0.5);
    _fwd.subVectors(ahead, p).normalize();
    const heading = Math.atan2(_fwd.z, -_fwd.x);
    const k = THREE.MathUtils.smoothstep(t, 0, 12);
    const left = new THREE.Vector3(0, 0, 1).applyAxisAngle(Y, heading), back = new THREE.Vector3(1, 0, 0).applyAxisAngle(Y, heading);
    const pos = p.clone().addScaledVector(left, 34 - 4 * k).addScaledVector(back, -14 + 30 * k).addScaledVector(Y, 4 - 1.5 * k);
    return { p, heading, pos, back };
}

globalThis.renderFrame = async function (t) {
    const F = globalThis._flight, cam = globalThis._c;
    const { p, heading, pos, back } = cameraAt(t);
    // the nose (local -X) along the path, 6 degrees down in forward flight, banked into the weave (its lateral pull
    // over gravity)
    const bank = Math.atan2(22 * 0.32 * 0.32 * Math.sin(t * 0.32), 9.81);
    F.heli.group.quaternion.setFromAxisAngle(Y, heading)
        .multiply(_qa.setFromAxisAngle(Z, THREE.MathUtils.degToRad(6)))
        .multiply(_qa.setFromAxisAngle(X, bank));
    F.heli.group.position.copy(p);
    F.heli.update(t);
    cam.position.copy(pos);
    cam.lookAt(_look.copy(p).addScaledVector(back, 2.5).addScaledVector(Y, -2));
    F.sky.update(t);
    await globalThis._r.renderAsync(globalThis._s, cam);
};
