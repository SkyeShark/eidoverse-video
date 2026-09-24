// daisies.js — a superbloom of daisies (the claudesona's own flower), GPU-instanced.
//
//   const { build } = await import(new URL('sets/ocean/daisies.js', EIDOVERSE_DIR).href);   // (used by ocean/land.js)
//   const field = await build(THREE, { count: 14000, width: 60, depth: 60, heightFn, sunDir, seed: 7,
//                                      clear: [{ a: [-30, 0], b: [30, 0], w: 2.2 }] });
//   scene.add(field.group);
//   // per frame: field.update(t, { close: 0..1, pulse: 0..1, wind: 1 })
//
// One daisy = stem tube + domed disc (phyllotaxis-dotted canvas) + a whorl of 21 geometry petals (no
// alpha cards). Three InstancedMeshes share instance order, so instanceIndex drives one sway phase for
// all parts. Petals and disc are authored in HEAD space (head centre at the origin, facing +Y); the
// vertex stage closes the petals about their bases (`close`: 0 open .. 1 a shut bud — the day's eye at
// dusk), tilts the head toward the sun, lifts it onto the stem, then sways. `pulse` swells the petals
// on the kick. Colours per instance: white, cream, Claude orange, gold.

export async function build(THREE, opts = {}) {
    const {
        count = 12000, width = 50, depth = 50, center = [0, 0], seed = 7, heightFn = null,
        sunDir = [0.3, 0.35, -0.9], faceDir = null, clear = [], palette = null, stemHeight = [0.2, 0.34],
        headScale = 1.5, yawSpread = 1.3,
    } = opts;
    const { uniform, positionGeometry, instanceIndex, instancedBufferAttribute, texture, uv, vec3, float, hash, sin,
        cos, length, max } = THREE;

    // ---------- deterministic RNG
    let s0 = (seed * 2654435761) >>> 0;
    const rnd = () => {
        s0 = (s0 + 0x6D2B79F5) >>> 0;
        let t = s0;
        t = Math.imul(t ^ (t >>> 15), t | 1);
        t ^= t + Math.imul(t ^ (t >>> 7), t | 61);
        return ((t ^ (t >>> 14)) >>> 0) / 4294967296;
    };

    // ---------- textures (canvas: materials are the work)
    const petalTex = (() => {
        const cv = document.createElement('canvas');
        cv.width = 64; cv.height = 256;
        const g = cv.getContext('2d');
        const gr = g.createLinearGradient(0, 256, 0, 0);          // base (v=0) slightly green-cream -> tip white
        gr.addColorStop(0, '#d9dcb8'); gr.addColorStop(0.18, '#f4f1e6'); gr.addColorStop(1, '#fbfaf4');
        g.fillStyle = gr; g.fillRect(0, 0, 64, 256);
        g.globalAlpha = 0.22;
        for (let i = 0; i < 7; i++) {                              // veins running base -> tip
            const x = 8 + i * 8 + (i % 2 ? 1 : -1);
            g.strokeStyle = i % 2 ? '#c9c4b0' : '#d8d2bf';
            g.lineWidth = 1.2;
            g.beginPath(); g.moveTo(32 + (x - 32) * 0.3, 256); g.quadraticCurveTo(x, 150, x * 0.9 + 3, 6); g.stroke();
        }
        g.globalAlpha = 0.1;                                       // a faint tip notch shadow
        g.fillStyle = '#8a8470'; g.fillRect(29, 0, 6, 10);
        const t = new THREE.CanvasTexture(cv);
        t.colorSpace = THREE.SRGBColorSpace;
        return t;
    })();
    const discTex = (() => {
        const cv = document.createElement('canvas');
        cv.width = cv.height = 256;
        const g = cv.getContext('2d');
        const gr = g.createRadialGradient(128, 128, 4, 128, 128, 128);
        gr.addColorStop(0, '#b8741a'); gr.addColorStop(0.55, '#e4a524'); gr.addColorStop(1, '#f2c53a');
        g.fillStyle = gr; g.fillRect(0, 0, 256, 256);
        const golden = Math.PI * (3 - Math.sqrt(5));               // phyllotaxis: the florets' spiral
        for (let i = 0; i < 520; i++) {
            const r = 5.3 * Math.sqrt(i), a = i * golden;
            if (r > 124) break;
            const x = 128 + r * Math.cos(a), y = 128 + r * Math.sin(a);
            g.fillStyle = i % 3 ? 'rgba(120,70,10,0.55)' : 'rgba(255,220,120,0.55)';
            g.beginPath(); g.arc(x, y, 2.2 + r * 0.012, 0, Math.PI * 2); g.fill();
        }
        const t = new THREE.CanvasTexture(cv);
        t.colorSpace = THREE.SRGBColorSpace;
        return t;
    })();

    // ---------- one daisy's geometry
    const R0 = 0.016;                  // disc radius (head space)
    const PL = 0.042, PW = 0.0075;     // petal length / max width
    const NP = 21;
    const petalGeo = (() => {
        const pos = [], uv = [], idx = [];
        const segL = 6, segW = 2;
        for (let k = 0; k < NP; k++) {
            const a = (k / NP) * Math.PI * 2 + (rnd() - 0.5) * 0.12;
            const len = PL * (0.88 + rnd() * 0.24);
            const droop = 0.006 + rnd() * 0.006;
            const ca = Math.cos(a), sa = Math.sin(a);
            const base = pos.length / 3;
            for (let i = 0; i <= segL; i++) {
                const s = i / segL;
                const w = PW * Math.pow(Math.sin(Math.PI * (0.12 + 0.88 * s)), 0.55) * (1 - 0.35 * s * s);
                const rr = R0 * 0.8 + s * len;
                const y = 0.002 - droop * s * s + 0.0025 * Math.sin(Math.PI * s);   // a slight cup, then droop
                for (let j = 0; j <= segW; j++) {
                    const u = j / segW - 0.5;
                    const off = u * w;
                    pos.push(ca * rr - sa * off, y + Math.abs(u) * 0.0012, sa * rr + ca * off);
                    uv.push(j / segW, s);
                }
            }
            for (let i = 0; i < segL; i++) for (let j = 0; j < segW; j++) {
                const a0 = base + i * (segW + 1) + j, b0 = a0 + segW + 1;
                idx.push(a0, b0, a0 + 1, a0 + 1, b0, b0 + 1);
            }
        }
        const gg = new THREE.BufferGeometry();
        gg.setAttribute('position', new THREE.Float32BufferAttribute(pos, 3));
        gg.setAttribute('uv', new THREE.Float32BufferAttribute(uv, 2));
        gg.setIndex(idx);
        gg.computeVertexNormals();
        return gg;
    })();
    const discGeo = (() => {
        const gg = new THREE.SphereGeometry(R0, 20, 8, 0, Math.PI * 2, 0, Math.PI / 2);
        gg.scale(1, 0.42, 1);
        const uvs = gg.attributes.uv, p = gg.attributes.position;       // top-down projection for the spiral
        for (let i = 0; i < p.count; i++) uvs.setXY(i, 0.5 + p.getX(i) / (2 * R0), 0.5 + p.getZ(i) / (2 * R0));
        return gg;
    })();
    const stemGeo = (() => {
        const pts = [];
        for (let i = 0; i <= 8; i++) {
            const s = i / 8;
            pts.push(new THREE.Vector3(0.012 * Math.sin(s * 2.2), s, 0.008 * s * s));   // unit height; scaled per instance
        }
        const gg = new THREE.TubeGeometry(new THREE.CatmullRomCurve3(pts), 10, 0.0032, 5, false);
        return gg;
    })();

    // ---------- materials (vertex stages share the sway)
    const U = { close: uniform(opts.close ?? 0), pulse: uniform(0), wind: uniform(1), tilt: uniform(0.42),
        t: uniform(0) };
    const phase = hash(instanceIndex).mul(6.2832);
    const sway = (p, hN) => {                      // hN: 0 at the ground, 1 at the head
        const a = U.wind.mul(0.07).mul(hN.mul(hN));
        const ph = phase.add(U.t.mul(1.35));
        return p.add(vec3(sin(ph).mul(a), float(0), cos(ph.mul(0.83).add(1.1)).mul(a.mul(0.7))));
    };
    // head space -> (close) -> tilt about X -> lift onto the stem top (y = 1 in stem units; heads are
    // authored at real size, the stem is unit height scaled by a per-instance factor baked into the matrix)
    const headXform = (q, withClose) => {
        let p = q;
        if (withClose) {
            const r = length(q.xz);
            const d = q.xz.div(max(r, 1e-4));
            const sOut = max(r.sub(R0 * 0.8), 0.0);
            const phi = U.close.mul(1.32);
            const grow = float(1).add(U.pulse.mul(0.1));
            const nr = float(R0 * 0.8).add(sOut.mul(cos(phi)).mul(grow));
            p = vec3(d.x.mul(nr), q.y.add(sOut.mul(sin(phi)).mul(grow)), d.y.mul(nr));
        }
        const ct = cos(U.tilt), st = sin(U.tilt);
        const y1 = p.y.mul(ct).sub(p.z.mul(st));
        const z1 = p.y.mul(st).add(p.z.mul(ct));
        return vec3(p.x, y1, z1);
    };

    const HEAD_SCALE = headScale / 0.34;   // heads authored in metres, stems at unit height; >1 = stylized big heads

    // ---------- placement (computed first: the per-instance attributes feed the vertex stage)
    const inClear = (x, z) => {
        for (const c of clear) {
            const [ax, az] = c.a, [bx, bz] = c.b;
            const dx = bx - ax, dz = bz - az, L2 = dx * dx + dz * dz;
            const tt = Math.max(0, Math.min(1, ((x - ax) * dx + (z - az) * dz) / L2));
            const px = ax + dx * tt - x, pz = az + dz * tt - z;
            if (px * px + pz * pz < (c.w / 2) ** 2) return true;
        }
        return false;
    };
    const clump = (x, z) => 0.5 + 0.5 * Math.sin(x * 0.21 + Math.sin(z * 0.13) * 2.1) * Math.cos(z * 0.17 - x * 0.05);
    // sRGB: white, cream, Claude orange (#D97757), gold
    const cols = palette || [[0.97, 0.96, 0.93, 0.46], [0.98, 0.93, 0.8, 0.16], [0.85, 0.47, 0.34, 0.28], [0.98, 0.8, 0.32, 0.1]];
    const colSum = cols.reduce((a, c) => a + c[3], 0);
    const pick = () => {
        let r = rnd() * colSum;
        for (const c of cols) { if ((r -= c[3]) <= 0) return c; }
        return cols[0];
    };
    const sd = new THREE.Vector3(...(faceDir || sunDir)).normalize();   // heads turn toward faceDir (default: the sun)
    const sunYaw = Math.atan2(sd.x, sd.z);
    const P = [], R = [], C = [];
    let tries = 0;
    while (P.length / 3 < count && tries < count * 6) {
        tries++;
        const x = center[0] + (rnd() - 0.5) * width, z = center[1] + (rnd() - 0.5) * depth;
        if (inClear(x, z) || rnd() > 0.25 + 0.75 * clump(x, z)) continue;
        const h = stemHeight[0] + rnd() * (stemHeight[1] - stemHeight[0]);
        P.push(x, heightFn ? heightFn(x, z) : 0, z);
        R.push(sunYaw + (rnd() - 0.5) * yawSpread, (rnd() - 0.5) * 0.12, (rnd() - 0.5) * 0.12, h);
        const c = pick(), v = 0.92 + rnd() * 0.08;
        const lin = new THREE.Color().setRGB(c[0] * v, c[1] * v, c[2] * v, THREE.SRGBColorSpace);   // palette is sRGB
        C.push(lin.r, lin.g, lin.b);
    }
    const n = P.length / 3;
    const aPos = new THREE.InstancedBufferAttribute(new Float32Array(P), 3);
    const aRot = new THREE.InstancedBufferAttribute(new Float32Array(R), 4);
    const aCol = new THREE.InstancedBufferAttribute(new Float32Array(C), 3);
    const iPos = instancedBufferAttribute(aPos, 'vec3');
    const iRot = instancedBufferAttribute(aRot, 'vec4');       // yaw, tiltX, tiltZ, stem height (scale)
    const iCol = instancedBufferAttribute(aCol, 'vec3');
    // flower-local (unit stem space) -> world: scale, small tilts, yaw, translate
    const place = (p) => {
        let q = p.mul(iRot.w);
        const cx = cos(iRot.y), sx = sin(iRot.y);
        q = vec3(q.x, q.y.mul(cx).sub(q.z.mul(sx)), q.y.mul(sx).add(q.z.mul(cx)));
        const cz = cos(iRot.z), sz = sin(iRot.z);
        q = vec3(q.x.mul(cz).sub(q.y.mul(sz)), q.x.mul(sz).add(q.y.mul(cz)), q.z);
        const cy = cos(iRot.x), sy = sin(iRot.x);
        q = vec3(q.x.mul(cy).add(q.z.mul(sy)), q.y, q.z.mul(cy).sub(q.x.mul(sy)));
        return q.add(iPos);
    };

    // ---------- materials: every deformation runs on the raw geometry, then place()
    const petalMat = new THREE.MeshStandardNodeMaterial({ roughness: 0.62, side: THREE.DoubleSide });
    const discMat = new THREE.MeshStandardNodeMaterial({ roughness: 0.85 });
    const stemMat = new THREE.MeshStandardNodeMaterial({ color: 0x4f6b2c, roughness: 0.7 });
    const headPos = (withClose) => {
        const q = positionGeometry.mul(HEAD_SCALE);
        const h = headXform(q, withClose).add(vec3(0.012 * Math.sin(2.2), 1.0, 0.008));
        return place(sway(h, float(1.0)));
    };
    petalMat.positionNode = headPos(true);
    discMat.positionNode = headPos(false);
    stemMat.positionNode = place(sway(positionGeometry, positionGeometry.y));
    petalMat.colorNode = texture(petalTex, uv()).rgb.mul(iCol);
    discMat.colorNode = texture(discTex, uv()).rgb;
    petalMat.emissiveNode = vec3(1.0, 0.85, 0.6).mul(U.pulse.mul(0.25));

    const mk = (geo, mat) => {
        const ig = new THREE.InstancedBufferGeometry();
        ig.index = geo.index;
        for (const k of Object.keys(geo.attributes)) ig.setAttribute(k, geo.attributes[k]);
        ig.instanceCount = n;
        const m = new THREE.Mesh(ig, mat);
        m.frustumCulled = false;       // positions are placed in the vertex stage
        return m;
    };
    const stems = mk(stemGeo, stemMat);
    const discs = mk(discGeo, discMat);
    const petals = mk(petalGeo, petalMat);
    const group = new THREE.Group();
    group.add(stems, discs, petals);
    group.name = 'daisies';

    return {
        group,
        parts: { stems, discs, petals, uniforms: U, count: n },
        update(t, state = {}) {
            U.t.value = t;
            if (state.close !== undefined) U.close.value = state.close;
            if (state.pulse !== undefined) U.pulse.value = state.pulse;
            if (state.wind !== undefined) U.wind.value = state.wind;
        },
        dispose() {
            for (const m of [stems, discs, petals]) { m.geometry.dispose(); m.material.dispose(); }
            petalTex.dispose(); discTex.dispose();
        },
    };
}
