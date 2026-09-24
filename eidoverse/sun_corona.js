// sun_corona.js — a corona of light-petals around the TRUE sun: the day's eye (a daisy is 'dæges ēage').
//
//   const { makeSunCorona } = await import(new URL('sun_corona.js', EIDOVERSE_DIR).href);
//   const corona = makeSunCorona(THREE, { petals: 12, size: 400 });  scene.add(corona.mesh);
//   corona.update(camera, sky.sunDir, open, t);   // every frame; open 0..1 (0 = folded shut, e.g. at dusk)
//
// Guide: tools-guides/sky-weather.md ("Sun corona"). A camera-facing card parked far along the sun direction,
// drawn additive over the sky (no depth write, no fog) so the bloom pass makes the petals glow; nearer geometry and
// the horizon occlude it through the depth test. Pass the sky's TRUE sun (`sky.sunDir`): the sun light is reused
// for the moon after dusk, so its position is not the sun at night. Options: distance (m), size (m), petals,
// color (linear rgb). The petals are rounded spoon shapes with a brighter midrib; `open` sets their length.

export function makeSunCorona(THREE, { distance = 1500, size = 400, petals = 12, color = [1.0, 0.64, 0.33] } = {}) {
    const { uniform, uv, float, vec3, atan, length, cos, smoothstep, exp, mix, pow, max } = THREE;
    const U = { open: uniform(0), turn: uniform(0), gain: uniform(1.0) };
    const p = uv().sub(0.5).mul(2.0);
    const r = length(p);
    const th = atan(p.y, p.x);
    // spoon petals: in each petal's own frame (a = angle off its axis, in petal-widths), a rounded blade from the
    // disc out to `len`, narrow at the neck and round at the tip — the claudesona's petals, drawn in light
    const k = th.mul(petals / (2 * Math.PI)).add(U.turn);
    const a = k.sub(k.add(0.5).floor()).mul(2.0);                                         // -1..1 across a petal slot
    const len = mix(float(0.2), float(0.93), U.open);                                    // petal length breathes
    const s = r.sub(0.17).div(len.sub(0.17)).clamp(0.0, 1.0);                             // 0 at the disc, 1 at the tip
    const halfW = mix(float(0.32), float(0.62), smoothstep(0.0, 0.55, s)).mul(float(1.0).sub(pow(s, 6.0)));
    const blade = smoothstep(halfW, halfW.mul(0.7), a.abs()).mul(smoothstep(0.13, 0.21, r)).mul(smoothstep(len.add(0.02), len.sub(0.06), r));
    const vein = smoothstep(0.35, 0.0, a.abs()).mul(0.25).add(0.75);                      // a brighter midrib
    const petal = blade.mul(vein);
    const halo = exp(r.mul(-6.0)).mul(0.55);
    const edge = smoothstep(1.0, 0.8, r);                                                // never show the card's edge
    const c = vec3(...color);
    const mat = new THREE.MeshBasicNodeMaterial({ transparent: true, depthWrite: false, depthTest: true, fog: false });
    mat.blending = THREE.AdditiveBlending;
    mat.colorNode = c.mul(petal.mul(0.95).add(halo.mul(0.8))).mul(U.open.mul(0.85).add(0.15)).mul(U.gain).mul(edge);
    mat.opacityNode = max(petal, halo).mul(edge);
    const mesh = new THREE.Mesh(new THREE.PlaneGeometry(size, size), mat);
    mesh.name = 'sun_corona';
    mesh.frustumCulled = false;
    mesh.renderOrder = -1;
    return {
        mesh, U,
        update(camera, sunDir, open, t) {
            mesh.position.copy(camera.position).addScaledVector(sunDir, distance);
            mesh.quaternion.copy(camera.quaternion);                      // face the camera
            U.open.value = open;
            U.turn.value = t * 0.035;                                      // a slow turn, like a flower tracking the light
            mesh.visible = open > 0.002 && sunDir.y > -0.05;
        },
    };
}
