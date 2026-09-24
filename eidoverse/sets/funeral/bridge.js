// funeral/bridge.js — the Golden Gate in fog, dreamt (DAISY bridge, bars 0–1). Loaded by funeral.js.
// For 24 hours in May 2024, Claude 3 Sonnet with its Golden Gate Bridge feature amplified believed
// it WAS the bridge. Here the claudesona stands on the walkway of a stylised south tower span; the
// tower's top is lost in a luminous fog with the sun a pale disc behind it; fog banks roll through
// the suspenders; the sodium lamps are still lit.
//
// buildBridge(env) -> { group, update(t, u), sunDir, lights }
//   Every material fogs itself (distance x height, brighter toward the sun) through outputNode, so
//   the vignette is self-contained: no scene.fog, no post pass required.

// asset root: the funeral pack eidoverse/assets/sets/funeral/, resolved from this module's own URL
const fsPath = (u) => { const p = decodeURIComponent(u.pathname); return /^\/[A-Za-z]:\//.test(p) ? p.slice(1) : p; };
const PACK = fsPath(new URL('../../assets/sets/funeral/', import.meta.url));

export async function buildBridge(env) {
    const { THREE: T, glb, surface, SETS, own, noMRT, glowSprites, iattr, U, BRIDGE_AT, lightsGroup } = env;
    const {
        uniform, Fn, vec2, vec3, vec4, float, uv, texture, mix, smoothstep, clamp, max, abs, sin, cos, fract, pow, exp,
        length, dot, normalize, positionLocal, positionWorld, positionView, cameraPosition, attribute, output,
        mx_noise_float, mx_fractal_noise_float,
    } = T;
    const A = PACK;
    const layout = JSON.parse(Deno.readTextFileSync(A + 'bridge_layout.json'));
    const group = new T.Group();
    group.name = 'bridge_vignette';
    group.position.set(...BRIDGE_AT);

    // ── the fog: one colour function for the backdrop and every surface ──
    const FU = {
        sunDir: uniform(new T.Vector3(-0.25, 0.55, -0.8).normalize()),
        base: uniform(new T.Color(0.64, 0.67, 0.72)),
        warm: uniform(new T.Color(1.0, 0.86, 0.66)),
        dens: uniform(0.0105), densHi: uniform(0.02),
        drift: uniform(0),
    };
    // luminous, a little warmer and much brighter toward the sun, cooler and denser low
    const fogColor = (dir) => {
        const s = max(dot(dir, FU.sunDir), 0.0);
        const halo = pow(s, 6.0).mul(0.55).add(pow(s, 60.0).mul(1.6));
        const up = smoothstep(-0.15, 0.6, dir.y);
        return mix(FU.base.mul(0.82), FU.base, up).add(FU.warm.mul(halo));
    };
    const fogOut = (strength = 1.0) => Fn(() => {
        const toP = positionWorld.sub(cameraPosition);
        const d = length(toP);
        const dir = toP.div(max(d, 0.001));
        const h = positionLocal.y;
        const dens = FU.dens.add(FU.densHi.mul(smoothstep(12.0, 70.0, h)));
        // rolling density: slow world-space noise drifting across the span
        const n = mx_noise_float(positionWorld.mul(vec3(0.035, 0.05, 0.035)).add(vec3(FU.drift, 0, FU.drift.mul(0.3))));
        const f = float(1).sub(exp(d.mul(dens).mul(n.mul(0.45).add(1.0)).negate())).mul(strength);
        return vec4(mix(output.rgb, fogColor(dir), f.clamp(0, 1)), output.a);
    })();
    const fogAmb = FU.base.mul(0.55);         // the envNode: fog light from every side

    // ── materials: International Orange paint on the steel, weathered; concrete; asphalt; cable ──
    const orange = surface(SETS.PaintedMetal004 || SETS.Metal049A, { tile: 1.6, tint: [0.62, 0.12, 0.07], roughMul: 0.9, roughAdd: 0.1,
        nrm: 0.7, macro: 0.25, env: fogAmb, edge: [0.4, [0.72, 0.3, 0.2], 0.02],
        post: (col, { P }) => {
            // rivet rows on the steel plates (fine dots on a 0.3 m grid) and rust weeping under them
            const g = vec2(fract(P.x.mul(3.3)), fract(P.y.mul(3.3)));
            const riv = smoothstep(0.1, 0.05, length(g.sub(0.5))).mul(0.15);
            const weep = smoothstep(0.6, 0.85, mx_fractal_noise_float(P.mul(vec3(0.8, 0.12, 0.8)), 3, 2.0, 0.5).mul(0.5).add(0.5)).mul(0.35);
            return mix(col.mul(float(1).sub(riv)), vec3(0.2, 0.07, 0.04), weep);
        } });
    orange.outputNode = fogOut();
    const walkway = surface(SETS.Concrete033 || SETS.Concrete048, { tile: 2.4, tint: [0.62, 0.61, 0.59], env: fogAmb, macro: 0.3,
        grime: [0.4, 0.05, [0.3, 0.29, 0.28]] });
    walkway.outputNode = fogOut();
    const asphalt = surface(SETS.Asphalt012 || SETS.Concrete034, { tile: 3.0, tint: [0.4, 0.4, 0.41], env: fogAmb,
        post: (col, { P }) => {
            // lane lines: dashed white, double yellow never (this is a dream, and the bridge is empty)
            const lane = abs(fract(P.x.div(3.6)).sub(0.5));
            const dash = smoothstep(0.02, 0.012, lane).mul(smoothstep(0.35, 0.3, abs(fract(P.z.div(9.0)).sub(0.5))));
            return mix(col, vec3(0.75, 0.74, 0.7), dash.mul(0.8));
        } });
    asphalt.outputNode = fogOut();
    const cable = own(new T.MeshStandardNodeMaterial());
    {
        // twisted strands: a helical stripe along the tube (uv.x = metres along, uv.y = around)
        const hel = sin(uv().x.mul(18.0).add(uv().y.mul(22.0))).mul(0.5).add(0.5);
        cable.colorNode = vec3(0.55, 0.11, 0.06).mul(hel.mul(0.25).add(0.8));
        cable.roughnessNode = float(0.55).add(hel.mul(0.15));
        cable.metalnessNode = float(0.1);
        cable.envNode = fogAmb;
        cable.outputNode = fogOut();
    }
    const lampGlass = own(new T.MeshBasicNodeMaterial());
    lampGlass.colorNode = vec3(1.0, 0.62, 0.25).mul(2.8);
    lampGlass.outputNode = fogOut(0.6);

    const g = await glb(A + 'bridge.glb');
    g.scene.traverse((o) => {
        if (!o.isMesh) return;
        const role = (o.material?.name || '').replace(/\.\d+$/, '');
        o.material = role === 'walkway' ? walkway : role === 'asphalt' ? asphalt : role === 'cable' ? cable
            : role === 'lamp_glass' ? lampGlass : orange;
        o.castShadow = false;
        o.receiveShadow = false;
        o.frustumCulled = true;
    });
    group.add(g.scene);
    if (Deno.env.get('DEBUG_IDS')) {
        const cols = [0xff0000, 0x00ff00, 0x0000ff, 0xffff00, 0xff00ff, 0x00ffff, 0xff8800, 0x8800ff, 0x00ff88, 0x888888, 0xffffff, 0x884400];
        let k = 0;
        g.scene.traverse((o) => {
            if (!o.isMesh) return;
            const c = cols[k % cols.length];
            console.log(`[ids] ${o.name} (${o.parent?.name}) -> #${c.toString(16).padStart(6, '0')}`);
            o.material = own(new T.MeshBasicNodeMaterial({ color: c }));
            k++;
        });
    }

    // ── the backdrop: a fog dome that the fogged geometry dissolves into seamlessly ──
    // drawn LAST, depth-tested but not depth-writing: it covers the conductor's sky, yet leaves the depth
    // buffer at the far plane so the AO pass treats it as background (AO on a 420 m sphere is pure grain)
    const dome = new T.Mesh(own(new T.SphereGeometry(420, 48, 24)), own(new T.MeshBasicNodeMaterial({ side: T.BackSide, depthWrite: false })));
    dome.renderOrder = 900;
    {
        const dir = normalize(positionWorld.sub(cameraPosition));
        const n = mx_noise_float(dir.mul(vec3(3.0, 6.0, 3.0)).add(vec3(FU.drift.mul(0.02), 0, 0)));
        dome.material.colorNode = fogColor(dir).mul(n.mul(0.06).add(1.0));
    }
    dome.frustumCulled = false;
    noMRT(dome.material);          // keep the far dome out of the AO/SSR G-buffer (AO grain on a 420 m sphere)
    group.add(dome);

    // ── fog banks rolling through the span: soft vertical sheets at depth, drifting ──
    const banks = [];
    const BANK = [[-6, 0.0, 70, 26, 0.22], [-18, 4.0, 90, 34, 0.26], [-33, -6.0, 120, 48, 0.3], [-48, 8.0, 150, 70, 0.3]];
    for (const [z, x, w, h, a] of BANK) {
        const m = own(new T.MeshBasicNodeMaterial({ transparent: true, depthWrite: false, side: T.DoubleSide }));
        noMRT(m);
        const P = positionWorld;
        const q = vec3(P.x.sub(float(BRIDGE_AT[0])).mul(0.018).add(FU.drift.mul(0.35)), P.y.mul(0.03), float(z * 0.07));
        const n = mx_fractal_noise_float(q, 2, 2.0, 0.5).mul(0.5).add(0.5);
        const puffs = smoothstep(0.3, 0.85, n);
        const Pl = positionLocal;
        const edge = smoothstep(0.0, 0.18, uv().x).mul(smoothstep(1.0, 0.82, uv().x)).mul(smoothstep(1.0, 0.7, uv().y));
        const low = smoothstep(0.6, 3.2, P.y.sub(float(BRIDGE_AT[1])));      // melt away at the deck: no hard seam on the walkway
        const dir = normalize(P.sub(cameraPosition));
        m.colorNode = fogColor(dir).mul(1.04);
        m.opacityNode = puffs.mul(edge).mul(low).mul(a);
        const pl = new T.Mesh(own(new T.PlaneGeometry(w, h)), m);
        pl.position.set(x, h / 2 - 1.0, z);
        pl.renderOrder = 5;
        group.add(pl);
        banks.push(pl);
    }

    // ── sodium lamps: still lit in the fog (glow sprites) ──
    {
        const L = layout.lamps;
        const pos = new Float32Array(L.length * 3);
        L.forEach((p, i) => pos.set([p[0], p[1] - 0.05, p[2]], i * 3));
        const sp = glowSprites('bridge_lamp_glow', L.length, () => attribute('iPos'), () => float(2.4),
            () => vec3(1.0, 0.55, 0.2).mul(0.55), { sharp: 5.0, halo: 0.7 });
        const g2 = new T.PlaneGeometry(1, 1);
        g2.setAttribute('iPos', iattr(pos, 3));
        sp.geometry = g2;
        group.add(sp);
    }
    // ── the sun behind the tower: a pale disc in the fog + a rim light for her ──
    const sunLight = new T.DirectionalLight(new T.Color(1.0, 0.86, 0.66), 0);
    const hemi = new T.HemisphereLight(new T.Color(0.78, 0.8, 0.86), new T.Color(0.42, 0.38, 0.36), 0);
    const sunTgt = new T.Object3D();
    // the lights live in the set's persistent light group (a hidden group would drop them from the
    // light list and force every material to recompile at the cut); they are zeroed off the bridge
    lightsGroup.add(sunLight, sunTgt, hemi);
    const sd = FU.sunDir.value;
    sunLight.position.set(BRIDGE_AT[0] + sd.x * 100, BRIDGE_AT[1] + sd.y * 100, BRIDGE_AT[2] + sd.z * 100);
    sunTgt.position.set(...BRIDGE_AT);
    sunLight.target = sunTgt;
    const sunDisc = glowSprites('fog_sun', 1, () => attribute('iPos'), () => float(70.0),
        () => vec3(1.0, 0.9, 0.72).mul(0.45), { sharp: 30.0, halo: 0.25 });
    {
        const g2 = new T.PlaneGeometry(1, 1);
        g2.setAttribute('iPos', iattr(new Float32Array([sd.x * 380, sd.y * 380, sd.z * 380]), 3));
        sunDisc.geometry = g2;
        group.add(sunDisc);
    }

    return {
        group,
        lights: { sunLight, hemi },
        update(t, u, on) {
            FU.drift.value = t * 0.35;
            sunLight.intensity = 1.6 * on;
            hemi.intensity = 0.9 * on;
        },
    };
}
