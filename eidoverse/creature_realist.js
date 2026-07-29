// creature_realist.js — globalThis.makeRealisticCreature: the SPECIMEN
// pipeline. A second creature system that consumes makeCreature's public
// API (creature_builder.js is never modified): the original provides the
// skeleton, gait engine, behaviors and options; this module replaces the
// BODY with an offline-sculpted realist mesh (SDF anatomy -> Quadriflow
// quad retopo -> capsule skin weights) bound to the very same bones.
//
//   const c = await globalThis.makeRealisticCreature({
//       stance: 'quad', legPairs: 2,
//       bodyLength: 1.35, bodyRadius: 0.17, neck: 0.42, tail: 0.85,
//       legLength: 1.05, color: 0x6a5747, belly: 0xcfc0a8,
//       pattern: 'plain', seed: 7, speed: 0.6,
//   });
//   scene.add(c.group);   // same api as makeCreature: walkTo, say, fly...
//
// First build of a new spec sculpts offline (python + Blender Quadriflow,
// ~1 min) and caches under work/creaturelab/cache/<hash>/ — later runs of
// the same options load instantly. Requires: python (torch, trimesh,
// skimage) + Blender 4.3 (only on cache miss).
(function () {
    const THREE = globalThis.THREE;
    const LAB = 'work/creaturelab';

    // ---- spec builder (shared with work/creaturelab/export_spec.mjs) ----
    function buildRealisticSpec(c, opts) {
        c.group.updateMatrixWorld(true);
        const bones = c.bones;
        const boneIndex = new Map(bones.map((b, i) => [b, i]));
        const roles = new Array(bones.length).fill('other');
        const legInfo = [];
        for (const l of c.legs) {
            const seg = [l.hip, l.knee, l.ankle];
            const names = l.isArm ? ['shoulder', 'elbow', 'wrist'] : ['hip', 'knee', 'ankle'];
            seg.forEach((b, i) => { if (boneIndex.has(b)) roles[boneIndex.get(b)] = (l.isArm ? 'arm_' : 'leg_') + names[i]; });
            legInfo.push({ isArm: !!l.isArm, side: l.side, bones: seg.map((b) => boneIndex.get(b) ?? -1), L1: l.L1, L2: l.L2, ankleLift: l.ankleLift ?? 0 });
        }
        const legAncestors = new Set();
        for (const l of c.legs) {
            let b = l.hip;
            while (b && b.isBone) { legAncestors.add(b); b = b.parent && b.parent.isBone ? b.parent : null; }
        }
        if (c.headBone && boneIndex.has(c.headBone)) {
            roles[boneIndex.get(c.headBone)] = 'head';
            let b = c.headBone.parent;
            while (b && b.isBone && !legAncestors.has(b)) {
                if (boneIndex.has(b) && roles[boneIndex.get(b)] === 'other') roles[boneIndex.get(b)] = 'neck';
                b = b.parent;
            }
        }
        for (const b of legAncestors) if (boneIndex.has(b) && roles[boneIndex.get(b)] === 'other') roles[boneIndex.get(b)] = 'spine';
        const markTail = (b) => {
            for (const chd of b.children) {
                if (!chd.isBone || !boneIndex.has(chd)) continue;
                if (roles[boneIndex.get(chd)] === 'other') { roles[boneIndex.get(chd)] = 'tail'; markTail(chd); }
            }
        };
        if (bones[0]) markTail(bones[0]);

        const segOf = (bi) => {
            const b = bones[bi];
            const child = b.children.find((ch) => ch.isBone && boneIndex.has(ch));
            if (child) return [b.userData.bindPos, child.userData.bindPos];
            const par = b.parent && b.parent.isBone && boneIndex.has(b.parent) ? b.parent : null;
            if (par) {
                const role = roles[bi] ?? 'other';
                const k = role === 'head' ? 0.6 : 0.25;
                const p0 = b.userData.bindPos, d = p0.clone().sub(par.userData.bindPos);
                return [p0, p0.clone().add(d.multiplyScalar(k))];
            }
            return [b.userData.bindPos, b.userData.bindPos.clone().add(new THREE.Vector3(0, 0.01, 0))];
        };
        const segCache = bones.map((_, i) => segOf(i));
        const samples = bones.map(() => [[], [], [], []]);
        const vA = new THREE.Vector3(), vB = new THREE.Vector3();
        c.group.traverse((o) => {
            if (!o.isSkinnedMesh) return;
            const pos = o.geometry.getAttribute('position');
            const sIdx = o.geometry.getAttribute('skinIndex');
            const sWgt = o.geometry.getAttribute('skinWeight');
            for (let i = 0; i < pos.count; i++) {
                let best = 0, bi = 0;
                for (let k = 0; k < 4; k++) if (sWgt.getComponent(i, k) > best) { best = sWgt.getComponent(i, k); bi = sIdx.getComponent(i, k); }
                if (bi >= bones.length) continue;
                const [a, b] = segCache[bi];
                vA.set(pos.getX(i), pos.getY(i), pos.getZ(i));
                vB.copy(b).sub(a);
                const L2 = Math.max(vB.lengthSq(), 1e-9);
                const t = Math.min(1, Math.max(0, vA.clone().sub(a).dot(vB) / L2));
                const r = vA.distanceTo(a.clone().addScaledVector(vB, t));
                samples[bi][Math.min(3, Math.floor(t * 4))].push(r);
            }
        });
        const q = (arr, p) => { if (!arr.length) return null; const s = [...arr].sort((x, y) => x - y); return s[Math.min(s.length - 1, Math.floor(p * s.length))]; };
        return {
            pv: 6,   // pipeline version — bump on sculpt/paint/weight changes to invalidate caches
            opts,
            stance: opts.stance ?? null,
            bones: bones.map((b, i) => ({
                i,
                parent: b.parent && b.parent.isBone && boneIndex.has(b.parent) ? boneIndex.get(b.parent) : -1,
                role: roles[i],
                bind: [b.userData.bindPos.x, b.userData.bindPos.y, b.userData.bindPos.z],
                segEnd: [segCache[i][1].x, segCache[i][1].y, segCache[i][1].z],
                radius: samples[i].map((st) => (st.length ? [q(st, 0.4), q(st, 0.85)] : null)),
            })),
            legs: legInfo,
            headBone: c.headBone ? boneIndex.get(c.headBone) ?? -1 : -1,
        };
    }
    globalThis.buildRealisticSpec = buildRealisticSpec;

    async function sha12(text) {
        const data = new TextEncoder().encode(text);
        const buf = await crypto.subtle.digest('SHA-1', data);
        return [...new Uint8Array(buf)].map((b) => b.toString(16).padStart(2, '0')).join('').slice(0, 12);
    }

    async function exists(path) {
        try { await Deno.stat(path); return true; } catch { return false; }
    }

    async function runSculpt(specPath, outDir) {
        const cmd = new Deno.Command('python', {
            args: [`${LAB}/sculpt_creature.py`, '--spec', specPath, '--out', outDir],
            stdout: 'piped', stderr: 'piped',
        });
        const proc = cmd.spawn();
        const out = await proc.output();
        const log = new TextDecoder().decode(out.stdout) + new TextDecoder().decode(out.stderr);
        for (const line of log.split('\n')) if (/sculpt|calipers|quadriflow/.test(line)) console.log('[realist]', line.trim());
        if (!out.success) throw new Error(`[creature_realist] sculpt pipeline failed:\n${log.slice(-2000)}`);
    }

    function geometryFromBundle(header, bytes) {
        const g = new THREE.BufferGeometry();
        const view = (name, Ctor) => {
            const h = header[name];
            return new Ctor(bytes.buffer, bytes.byteOffset + h.offset, h.count * h.components);
        };
        g.setAttribute('position', new THREE.BufferAttribute(view('position', Float32Array), 3));
        g.setAttribute('normal', new THREE.BufferAttribute(view('normal', Float32Array), 3));
        g.setAttribute('color', new THREE.BufferAttribute(view('color', Float32Array), 3));
        g.setAttribute('skinIndex', new THREE.BufferAttribute(view('skinIndex', Uint16Array), 4));
        g.setAttribute('skinWeight', new THREE.BufferAttribute(view('skinWeight', Float32Array), 4));
        g.setIndex(new THREE.BufferAttribute(view('index', Uint32Array), 1));
        return g;
    }

    // ---- the public entry ------------------------------------------------
    globalThis.makeRealisticCreature = async function (opts = {}) {
        if (!globalThis.makeCreature) throw new Error('[creature_realist] makeCreature missing');
        const c = globalThis.makeCreature(opts);

        const spec = buildRealisticSpec(c, opts);
        const specJson = JSON.stringify(spec);
        const hash = await sha12(specJson);
        const dir = `${LAB}/cache/${hash}`;
        const headerPath = `${dir}/creature_mesh.json`;
        const binPath = `${dir}/creature_mesh.bin`;

        if (!(await exists(headerPath)) || !(await exists(binPath))) {
            console.log(`[creature_realist] cache miss ${hash} — sculpting (first build of this spec)...`);
            await Deno.mkdir(dir, { recursive: true });
            await Deno.writeTextFile(`${dir}/spec.json`, specJson);
            await runSculpt(`${dir}/spec.json`, dir);
        } else {
            console.log(`[creature_realist] cache hit ${hash}`);
        }

        const header = JSON.parse(await Deno.readTextFile(headerPath));
        const bytes = await Deno.readFile(binPath);
        const g = geometryFromBundle(header, bytes);

        const mat = new THREE.MeshStandardNodeMaterial({
            roughness: opts.roughness ?? 0.62,
            metalness: 0.0,
        });
        // NodeMaterial path: bind the painted vertex colors explicitly —
        // the boolean vertexColors flag does not reach the WebGPU shader
        mat.colorNode = THREE.attribute('color', 'vec3');
        const sm = new THREE.SkinnedMesh(g, mat);
        sm.name = 'realistBody';
        sm.castShadow = true; sm.receiveShadow = true;
        sm.frustumCulled = false;
        c.group.add(sm);
        sm.bind(c.skeleton, sm.matrixWorld);

        // the original tube body + feet stay as the RIG's ghost — hidden,
        // never removed (accessories keep riding their bones)
        c.group.traverse((o) => { if (o.isSkinnedMesh && o !== sm) o.visible = false; });
        for (const l of c.legs) if (l.foot) l.foot.visible = false;

        // realist eyes: glossy spheres mounted on the head bone at the
        // sculpt's socket anchors (bundle aux). The original googly eyes sit
        // buried inside the new skull; these are the specimen's own.
        if (header.aux && header.aux.eyes && c.headBone) {
            const bindP = c.headBone.userData.bindPos;
            const eyeMat = new THREE.MeshStandardNodeMaterial({
                color: new THREE.Color(opts.eyeColor ?? 0x2a1c10), roughness: 0.08, metalness: 0.0 });
            for (const e of header.aux.eyes) {
                const eye = new THREE.Mesh(new THREE.SphereGeometry(e.r * 0.95, 20, 14), eyeMat);
                eye.name = 'realistEye';
                eye.position.set(e.c[0] - bindP.x, e.c[1] - bindP.y, e.c[2] - bindP.z);
                eye.castShadow = false;
                c.headBone.add(eye);
            }
        }

        c.realistMesh = sm;
        return c;
    };

    console.log('[creature_realist] makeRealisticCreature ready — sculpted realist body (SDF anatomy -> quad retopo) bound onto the untouched makeCreature rig; same options, same gait engine, cached by spec hash');
})();
