// RED GIANT + PLANETARY SHIELD — a sky-element SYSTEM (no scene geometry).
// A procedural animated red giant that rides the sky's sun through the day
// cycle (celestial hook → visible sky, metal/puddle reflections, and the env
// bake from ONE function), plus a hex-cell radiation shield above the clouds:
// deterministic flare prominences on the star, and radiation hits arriving on
// the shield as expanding rings of whole-hexagon activations — more and
// harder hits while a flare peaks.
//
// Usage (three phases — the celestial must exist BEFORE the sky):
//   eval(Deno.readTextFileSync('work/skylab/redgiant/redgiant.js'));
//   const rg = await globalThis.makeRedGiant({ opts: { shield: true } });
//   const sky = await globalThis.makeSkySystem({ scene, textures, opts: {
//       celestial: rg.celestial, paletteTint: rg.paletteTint, ... } });
//   rg.attach({ scene, sky });
//   // per frame, after sky.update(t):
//   rg.update(t);
// opts: angularRadius (rad, default 0.28 ≈ 32° disc), granScale (32),
//       shield (true), hexScale (110), shieldRadius (19000), flares (slot array)
globalThis.makeRedGiant = async function ({ opts = {} } = {}) {
    const T3 = THREE;
    const {
        vec2, vec3, vec4, float, uniform, mix, clamp, smoothstep, dot, pow,
        max: tmax, fract, floor, sin, exp, abs, length, normalize, sqrt, step,
    } = T3;
    const atan2f = T3.atan2 ?? T3.atan;

    // ---- star state (JS-driven; update() makes the giant ride the sun) ----
    const uStarDir = uniform(new T3.Vector3(0, 0.42, -0.86).normalize());
    const uStarRight = uniform(new T3.Vector3(1, 0, 0));
    const uStarUp = uniform(new T3.Vector3(0, 1, 0));
    const uStarT = uniform(0);
    const uBurstK = uniform(0);          // live max flare envelope
    const uFlareBoost = uniform(0);      // FLAREMAX debug: force eruptions to peak
    const STAR_R = opts.angularRadius ?? 0.28;
    const SIN_R = Math.sin(STAR_R), COS_R = Math.cos(STAR_R);
    const GRAN = opts.granScale ?? 32;   // close orbit = fine boiling cells

    // flare slots: JS-authored constants so the SAME deterministic schedule
    // drives the shader prominences and the JS-side shield coupling
    const FLARES = opts.flares ?? [
        { th: 0.7, rate: 0.055, ph0: 0.13 },
        { th: 2.3, rate: 0.075, ph0: 0.55 },
        { th: 3.5, rate: 0.048, ph0: 0.82 },
        { th: 4.6, rate: 0.068, ph0: 0.30 },
        { th: 5.7, rate: 0.060, ph0: 0.68 },
    ];
    const flareEnv = (f, t) => {
        const ph = (t * f.rate + f.ph0) % 1;
        const cyc = Math.floor(t * f.rate + f.ph0);
        const act = ((Math.sin(cyc * 12.9898 + f.th * 78.233) * 43758.5453) % 1 + 1) % 1 > 0.45 ? 1 : 0;
        return Math.pow(Math.sin(Math.PI * Math.min(ph * 1.3, 1)), 2) * act;
    };

    // sin-free Hoskins hash + quintic value noise (house style)
    const h21 = (p) => {
        const a = fract(vec3(p.x, p.y, p.x).mul(0.1031));
        const d = dot(a, vec3(a.y, a.z, a.x).add(33.33));
        const b = a.add(d);
        return fract(b.x.add(b.y).mul(b.z));
    };
    const vn = (p) => {
        const i = floor(p), f = fract(p);
        const sm = f.mul(f).mul(f).mul(f.mul(f.mul(6).sub(15)).add(10));
        const a = h21(i), b = h21(i.add(vec2(1, 0)));
        const c = h21(i.add(vec2(0, 1))), d = h21(i.add(vec2(1, 1)));
        return mix(mix(a, b, sm.x), mix(c, d, sm.x), sm.y);
    };
    const fbm3 = (p) => vn(p).mul(0.55).add(vn(p.mul(2.3).add(19.7)).mul(0.28)).add(vn(p.mul(5.1).add(7.3)).mul(0.17));

    // ---- the celestial node: pass to makeSkySystem opts.celestial ----
    const celestial = (dir, col) => {
        // disc-local frame (right/up fed from JS so the star can ride the sun)
        const lx = dot(dir, uStarRight).div(SIN_R);
        const ly = dot(dir, uStarUp).div(SIN_R);
        const face = step(COS_R * 0.2, dot(dir, uStarDir));     // hemisphere guard
        const rho = length(vec2(lx, ly));
        // surface: convection granulation, slowly boiling — fine-grained
        const p = vec2(lx, ly).mul(GRAN);
        // boil rates ~18x the original: tuned for realtime seconds, they
        // drifted 3% of the domain across a whole compressed day cycle and
        // read as a fully static surface (Skye's catch)
        const w = vec2(
            fbm3(p.mul(0.55).add(uStarT.mul(0.55))),
            fbm3(p.mul(0.55).sub(uStarT.mul(0.43)).add(41.3)),
        ).sub(0.5).mul(1.9);
        const g = fbm3(p.add(w).add(vec2(uStarT.mul(0.22), 0))).mul(0.82)
            .add(vn(p.mul(3.1).add(w.mul(2)).add(vec2(0, uStarT.mul(0.9)))).mul(0.18));
        let sCol = mix(vec3(0.42, 0.050, 0.015), vec3(1.05, 0.32, 0.06), smoothstep(0.35, 0.75, g));
        sCol = mix(sCol, vec3(1.85, 1.05, 0.45), smoothstep(0.78, 0.95, g));
        // GIANT convection cells (Betelgeuse-class: a handful across the
        // disc, near-static — they live for months; the fine boil above
        // rides on top). Chiavassa 2010: cell size >60% R*, one cell can
        // carry ~8% of total flux.
        const pg = vec2(lx, ly).mul(1.15);
        const cell = fbm3(pg.add(vec2(uStarT.mul(0.006), uStarT.mul(-0.004))));
        sCol = sCol.mul(cell.sub(0.5).mul(0.55).add(1.0));
        // ONE asymmetric hot patch — the signature feature of every resolved
        // red-supergiant image (ALMA/VLT); drifts imperceptibly
        const phi = atan2f(ly, lx);
        const p2h = vec2(lx, ly);
        const hpD = p2h.sub(vec2(0.34, -0.18));
        const hotK = exp(dot(hpD, hpD).div(0.048).negate())
            .mul(vn(vec2(uStarT.mul(0.02), 3.7)).mul(0.4).add(0.8));
        sCol = sCol.add(vec3(0.55, 0.30, 0.12).mul(hotK));
        // limb darkening — STRONG for a cool giant (u≈0.95: edge ~5% of
        // center) and the limb REDDENS (blue darkens first; center is the
        // hotter, yellower layer — TiO haze at the rim)
        const muL = sqrt(tmax(float(1).sub(rho.mul(rho)), 0));
        sCol = sCol.mul(muL.mul(0.95).add(0.05));
        sCol = sCol.mul(mix(vec3(1.0, 0.60, 0.42), vec3(1.0, 1.03, 1.08), muL));
        // chromosphere rim: H-ALPHA PINK (not orange — Balmer emission),
        // patchy around the limb like the ALMA asymmetric chromosphere
        const rimPatch = vn(vec2(phi.mul(2.2), uStarT.mul(0.11))).mul(0.6).add(0.55);
        sCol = sCol.add(vec3(1.35, 0.32, 0.38).mul(pow(float(1).sub(muL), 6).mul(1.8)).mul(rimPatch));
        // COLOUR OVERRIDE, applied once the authored ramp is fully assembled:
        // granulation, convection cells, hot patch, limb darkening/reddening
        // and the chromospheric rim all keep their relative structure and only
        // the overall hue shifts. Default [1,1,1] leaves the star untouched.
        sCol = sCol.mul(uStarTint);
        // fuzzy molecular limb (MOLsphere at 1.2-1.4 R*): the silhouette is
        // a gradient ~9% of R wide, never a crisp edge
        const inDisc = smoothstep(1.045, 0.955, rho).mul(face);
        // corona: Baumbach-style three-term falloff — tight bright rim,
        // mid glow, huge faint halo (exponents stand in for r^-17/-7/-2.5)
        const glow = exp(rho.sub(1).mul(-16)).mul(0.50)
            .add(exp(rho.sub(1).mul(-6.5)).mul(0.30))
            .add(exp(rho.sub(1).mul(-2.2)).mul(0.12));
        let flare = float(0);
        let footpoint = float(0);
        for (const f of FLARES) {
            const ph = fract(uStarT.mul(f.rate).add(f.ph0));
            const cyc = floor(uStarT.mul(f.rate).add(f.ph0));
            const act = step(0.45, fract(sin(cyc.mul(12.9898).add(f.th * 78.233)).mul(43758.5453)));
            const env = f === FLARES[0] ? tmax(sin(clamp(ph.mul(1.3), 0, 1).mul(Math.PI)).pow(2).mul(act), uFlareBoost) : sin(clamp(ph.mul(1.3), 0, 1).mul(Math.PI)).pow(2).mul(act);
            // PROMINENCE LOOP (Skye: radial edge-glow = eclipse corona, not a
            // flare): an arch anchored on the limb — circle centered at the
            // limb point, radius growing with the eruption, so the visible
            // band is a handle standing on the star with both feet on the
            // surface. Filaments ripple along the arc as it rises.
            const c2 = vec2(Math.cos(f.th), Math.sin(f.th));
            const p2 = vec2(lx, ly);
            const loopR = env.mul(0.10).add(0.040);   // capped: full-size arcs read as cartoon crescents on the disc
            // center sinks INSIDE the disc by ~60% of the loop radius: only
            // the crown of the circle rises past the limb — an arch standing
            // on the surface, not a ring dangling off it
            const rel = p2.sub(c2.mul(float(1.0).sub(loopR.mul(0.6))));
            const la = atan2f(rel.y, rel.x);
            const fil = vn(vec2(la.mul(7.0), uStarT.mul(1.6).add(f.ph0 * 40))).mul(0.55).add(0.55);
            const wobble = fil.sub(0.55).mul(0.035);
            // NESTED arcs with a bright core and a wide soft glow — the thin
            // single line read cheap (Skye). Radial streak noise keeps the
            // fibrous texture of the original prominences.
            const relLen = length(rel);
            const streak = vn(vec2(la.mul(15), relLen.mul(9).sub(uStarT.mul(0.8)))).mul(0.6).add(0.55);
            let band = float(0);
            for (const [rk, ak] of [[0.82, 0.5], [1.0, 1.0], [1.16, 0.4]]) {
                const dA = abs(relLen.sub(loopR.mul(rk).add(wobble)));
                band = band.add(smoothstep(float(0.045), float(0.008), dA).mul(ak));
            }
            const glowA = abs(relLen.sub(loopR.add(wobble)));
            band = band.add(smoothstep(float(0.12), float(0.02), glowA).mul(0.4));
            band = band.mul(streak).mul(fil)
                .mul(smoothstep(float(0.955), float(1.000), rho));
            // eruptive streamer at peak: a detached blob riding outward
            const blobR = env.mul(env).mul(0.42).add(0.06);
            const dBlob = length(p2.sub(c2.mul(blobR.add(1.0))));
            const blob = smoothstep(float(0.05), float(0.012), dBlob).mul(smoothstep(0.75, 0.95, env)).mul(0.45);
            flare = flare.add(band.mul(env).mul(0.7).add(blob).mul(face));
            // footpoints: the surface burns where the loop feet stand
            const feet = smoothstep(float(0.10), float(0.02), abs(length(rel).sub(loopR)).add(abs(rho.sub(0.985)).mul(2)));
            footpoint = footpoint.add(feet.mul(env).mul(0.6));
        }
        const outside = float(1).sub(inDisc).mul(face).mul(step(1.0, rho));
        let out = mix(col, sCol, inDisc);                        // opaque body replaces sky (and stars)
        out = out.add(vec3(0.95, 0.22, 0.05).mul(glow).mul(outside).mul(0.55));
        // flares erupt FROM the surface: the old outside-only mask clipped
        // them at the silhouette (eclipse-prominence look). The limb-crossing
        // mask lets the roots burn on the disc and the arcs run past it.
        out = out.add(vec3(1.5, 0.42, 0.10).mul(flare));
        out = out.add(vec3(2.4, 1.05, 0.38).mul(flare).mul(flare).mul(0.5));  // hot core where bands stack
        out = out.add(vec3(2.3, 0.85, 0.25).mul(footpoint).mul(inDisc));
        return out;
    };

    // ---- ember palette: pass to makeSkySystem opts.paletteTint. A ~3200 K
    // photosphere emits almost NO blue — there is nothing for the air to
    // Rayleigh-scatter into a blue sky. Deep red key, red-orange horizon,
    // dim iron-red zenith.
    // channel ceiling 1.0 (same hue ratios as the original 1.30/1.22-red
    // bands): tints >1 pushed sun-facing cloud radiance past white before
    // tone mapping — the whole forward-scatter lobe cored to a white flood
    // under the giant (a third of the sky). ACES now rolls those clouds
    // into peach/orange with white only at thin silver-lining edges.
    const paletteTint = opts.paletteTint
        ?? { zen: [0.72, 0.20, 0.10], hor: [1.00, 0.29, 0.11], sun: [1.00, 0.28, 0.10] };

    // ---- shield (built in attach — needs the scene) ----
    // gnomonic-plane scale: cells this size read as HEXAGONS (~25 px at 720p
    // mid-sky); much finer and the grid collapses into noise/moiré
    const HEXSCALE = opts.hexScale ?? 22;
    const uImpP = [0, 1, 2, 3, 4].map(() => uniform(new T3.Vector3(0, 0, -99)));  // x,y = plane pos, z = birth time
    const uImpA = [0, 1, 2, 3, 4].map(() => uniform(0));
    let shield = null;
    // Live tint over the star's authored ember ramp. [1,1,1] = the dialed-in
    // red giant; this multiplies the final surface colour so granulation,
    // convection cells, the hot patch and limb darkening all keep their
    // relative structure and only the hue/level shifts.
    const uStarTint = uniform(new T3.Vector3(
        ...(opts.starColor ?? [1, 1, 1])));

    const sys = {
        celestial, paletteTint, flares: FLARES, flareEnv,
        uniforms: { starDir: uStarDir, starT: uStarT, burstK: uBurstK, impP: uImpP, impA: uImpA },
        shield: null,
        // Recolour the hex shield live. [r,g,b] in linear HDR — values above 1
        // are intentional (the lattice is emissive). Default [0.38, 0.95, 1.3]
        // is the authored cyan. No-op if the scene built with shield:false.
        setShieldColor(rgb) {
            if (!sys._uShieldColor || !Array.isArray(rgb) || rgb.length !== 3) return sys;
            sys._uShieldColor.value.set(+rgb[0], +rgb[1], +rgb[2]);
            return sys;
        },
        // Recolour the STAR itself: [r,g,b] multiplier over the authored
        // ember ramp (deep red -> orange -> hot yellow-white). [1,1,1] is the
        // dialed-in red giant; push blue for a hotter star, red for cooler.
        setStarColor(rgb) {
            if (!Array.isArray(rgb) || rgb.length !== 3) return sys;
            uStarTint.value.set(+rgb[0], +rgb[1], +rgb[2]);
            return sys;
        },
        attach({ scene, sky }) {
            sys._sky = sky;
            // Register with the sky so sky.setColors({ shield, star }) can
            // reach this module without the scene passing it in by hand.
            if (sky) sky._celestialModule = sys;
            if (opts.shield === false) return sys;
            // live shield tint — authored cyan by default, see setShieldColor
            const sc = opts.shieldColor ?? [0.38, 0.95, 1.3];
            const uShieldColor = uniform(new T3.Vector3(sc[0], sc[1], sc[2]));
            sys._uShieldColor = uShieldColor;
            const shieldMat = new T3.MeshBasicNodeMaterial({
                transparent: true, depthWrite: false, side: T3.BackSide, fog: false,
            });
            if (T3.mrt && !globalThis.EANPA_NO_MRT) shieldMat.mrtNode = T3.mrt({ normal: vec4(0), metalrough: vec4(0) });   // EANPA: forward path — mrt stamps compile to empty structs in Chrome
            {
                const dir = normalize(T3.positionWorld);
                // hex tiling on a VIRTUAL FLAT CEILING (gnomonic map): a
                // planetary shield is a dome so vast it must read FLAT from
                // the ground — like the atmosphere, curvature only exists at
                // ships-out-to-sea scale. Constant-size cells overhead,
                // honest perspective convergence toward the horizon; the
                // dome GEOMETRY stays (the star never dips under the shield
                // at sunrise), only the pattern lives on the plane.
                const p = dir.xz.div(tmax(dir.y, float(0.05))).mul(HEXSCALE);
                const r = vec2(1, 1.7320508), hh = r.mul(0.5);
                const a2 = T3.mod(p, r).sub(hh);
                const b2 = T3.mod(p.sub(hh), r).sub(hh);
                const useA = step(length(a2), length(b2));
                const gv = mix(b2, a2, useA);
                const id = p.sub(gv);
                const ha = abs(gv);
                const hexD = tmax(dot(ha, vec2(0.5, 0.8660254)), ha.x);   // 0 center → 0.5 edge
                const edge = smoothstep(float(0.40), float(0.485), hexD);
                // faint per-cell shimmer (idle flux) — activity comes from hits
                const ch = h21(id.mul(0.37).add(7.7));
                const shim = sin(uStarT.mul(ch.mul(0.6).add(0.4)).add(ch.mul(31))).mul(0.5).add(0.5).mul(0.1);
                // impact ripples: BINARY rings of whole hexagons — distance
                // is measured to the CELL CENTER (id) and the band test is a
                // hard step, so each hex fully lights or stays dark; the
                // ring of lit cells expands from the hit (no gradients).
                let hits = float(0);
                for (let i = 0; i < 5; i++) {
                    const age = uStarT.sub(uImpP[i].z);
                    const d = length(id.sub(uImpP[i].xy));
                    const lit = step(abs(d.sub(age.mul(30))), float(1.4));
                    const ring = lit.mul(h21(id.add(i * 3.7)).mul(0.5).add(0.75))
                        .mul(exp(age.mul(-1.5))).mul(step(0, age)).mul(uImpA[i]);
                    hits = hits.add(ring);
                }
                const faceK = smoothstep(float(-0.2), float(0.7), dot(dir, uStarDir)).mul(0.7).add(0.3);
                // aerial perspective: the rim toward the horizon dissolves
                const horizon = smoothstep(float(0.03), float(0.38), dir.y);
                const cellGlow = hits.add(shim.mul(faceK));
                // clouds ALWAYS read in front of the lattice (Skye): draw
                // order alone can't hide a bright emissive grid behind a
                // translucent cloud, so the lattice is DIMMED by the cloud
                // optical depth in its sight column — sample the deck where
                // the view ray crosses the cloud layer
                const deckP = dir.mul(sky.uniforms.cloudStart.div(tmax(dir.y, 0.06)));
                const cloudOcc = sky.tslCloudShadow ? sky.tslCloudShadow(deckP, 0.92) : float(1);
                // Base hex-lattice emissive, times a live tint uniform so the
                // shield can be recoloured without rebuilding the material.
                // The authored cyan stays the default; setShieldColor swaps it.
                shieldMat.colorNode = uShieldColor.mul(edge.add(cellGlow.mul(1.5)).add(0.15));
                shieldMat.opacityNode = edge.mul(faceK).mul(0.05)
                    .add(cellGlow.mul(edge.mul(0.5).add(0.5)).mul(0.45))
                    .mul(horizon).mul(cloudOcc);
            }
            shield = new T3.Mesh(new T3.SphereGeometry(opts.shieldRadius ?? 21000, 64, 32), shieldMat);
            shield.name = 'planet_shield';
            shield.renderOrder = -99;   // FINAL RULING (Skye): the shield is
            // the outermost skin — which on screen means BOTH cloud layers
            // (volumetric dome at -98 and weather overlays at 0) render IN
            // FRONT of the lattice and occlude it, since the viewer stands
            // under the clouds. Hexes/impacts are angular; radius is fiction.
            shield.frustumCulled = false; shield.userData.noSupportCheck = true; shield.userData.noWet = true;
            scene.add(shield);
            sys.shield = shield;
            return sys;
        },
        update(t) {
            uStarT.value = t;
            uFlareBoost.value = Number((globalThis.Deno?.env.get('FLAREMAX')) || 0);
            const sky = sys._sky;
            if (sky) {
                // the giant IS the sun: ride the sky's TOD sun (day cycle,
                // palette, and lighting all track one body) and keep the
                // default disc + forward-scatter glow lobes OFF (the weather
                // system rewrites sunDiscI per state; the glow lobes read as
                // a phantom white core dead-center in the giant)
                uStarDir.value.copy(sky.sunDir).normalize();
                const up0 = Math.abs(sky.sunDir.y) > 0.93 ? new T3.Vector3(1, 0, 0) : new T3.Vector3(0, 1, 0);
                uStarRight.value.crossVectors(up0, uStarDir.value).normalize();
                uStarUp.value.crossVectors(uStarDir.value, uStarRight.value).normalize();
                sky.uniforms.sunDiscI.value = 0;
                if (sky.uniforms.sunGlowI) sky.uniforms.sunGlowI.value = 0;
            }
            let env = 0;
            for (const f of FLARES) env = Math.max(env, flareEnv(f, t));
            uBurstK.value = env;
            // radiation hits: 5 deterministic slots clustered toward the
            // star's gnomonic projection on the shield plane; a live flare
            // raises the amplitude of hits born during it (the storm ARRIVES)
            const sdd = uStarDir.value;
            const gy = Math.max(sdd.y, 0.15);
            const sx = sdd.x / gy * HEXSCALE, sz = sdd.z / gy * HEXSCALE;
            // the planet is the best shield: flux collapses to a residual
            // cosmic patter once the star sets (hits track the star's
            // projection all day, then nearly stop overnight)
            const dayK = 0.1 + 0.9 * Math.min(1, Math.max(0, (sdd.y + 0.05) / 0.25));
            const h1 = (a, b) => { const v = Math.sin(a * 127.1 + b * 311.7) * 43758.5453; return v - Math.floor(v); };
            for (let i = 0; i < 5; i++) {
                const per = 2.8 + i * 1.2;                       // unhurried cadence — a hit lands every couple of seconds, not rapid fire
                const tin = t / per + i * 0.37;
                const cyc = Math.floor(tin);
                const birth = (cyc - i * 0.37) * per;
                let envB = 0;
                for (const f of FLARES) envB = Math.max(envB, flareEnv(f, birth));
                const ang = h1(cyc, i * 7 + 1) * Math.PI * 2;
                const rad = (0.12 + h1(cyc, i * 7 + 2) * 0.55) * HEXSCALE;
                uImpP[i].value.set(sx + Math.cos(ang) * rad, sz + Math.sin(ang) * rad, birth);
                const on = h1(cyc, i * 7 + 3) > (0.45 - envB * 0.35) ? 1 : 0;
                // intensity: nearer the star = hotter hit, flares slam it,
                // night collapses it
                const nearK = 1 - 0.45 * (rad / (0.67 * HEXSCALE));
                uImpA[i].value = on * (0.35 + 0.65 * h1(cyc, i * 7 + 4)) * (0.55 + 1.6 * envB) * nearK * dayK;
            }
        },
    };
    return sys;
};
