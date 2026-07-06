// iso_field.js — globalThis.makeIsoField: GPU-RAYMARCHED ISOSURFACE for a
// CPU-owned scalar voxel field. The speed path for the MarchingCubes
// pattern: SAME field layout (x + y*res + z*res²), same block mapping,
// but the surface is found PER-PIXEL in a fragment raymarch — zero
// per-frame CPU triangulation, no maxPolyCount ceiling, field resolution
// costs memory instead of frame time. (three's MarchingCubes.update() is
// a JS polygonizer — calling it per frame is what tanks renders to ~1fps.)
//
//   const iso = globalThis.makeIsoField({
//       resolution: 64,        // field res (memory + raymarch quality)
//       half: 0.5,             // world half-extent: x,z ∈ [-half,half], y ∈ [0,2half]
//       iso: 50,               // surface threshold
//       color: 0x9aa2ac, metalness: 0.85, roughness: 0.35,
//       steps: 160,            // raymarch samples across the box
//       emissive: (hp, n) => vec3-node,   // optional TSL hook (world hit point)
//       parent: group,         // where the proxy mesh lands (world-static!)
//   });
//   iso.field[iso.idx(x, y, z)] = 100;   // write cells like mc.field
//   iso.upload();                         // after a batch of writes
//
// Correct occlusion BOTH ways: the fragment writes the true hit-point
// depth (depthNode), so scene geometry in front of the surface hides it
// and geometry behind it is hidden — no transparent-sorting artifacts.
// Shading samples the SCENE's lights (strongest directional + hemisphere
// + two strongest point lights, captured at bind()) so the solid sits in
// the same light as everything else. Raymarched pixels still can't CAST
// shadows — pair with a colorWrite:false proxy box (CNCSim does).
//
// TSL gotchas encoded here: instancedArray does NOT alias the array you
// pass it (write through .value.array); TSL mix() with all-JS-number
// args emits INVALID WGSL silently (blend JS constants in JS).
(function () {
    const THREE = globalThis.THREE;
    if (!THREE) { console.warn('[iso_field] THREE global not present — skipping load'); return; }

    function makeIsoField(o = {}) {
        const {
            Fn, If, Break, Loop, instancedArray, uniform, float, int, vec3, vec4,
            mix, max, min, clamp, normalize, pow, dot, floor, positionWorld,
            cameraPosition, cameraProjectionMatrix, cameraViewMatrix, reflect, smoothstep,
        } = THREE;
        const res = o.resolution ?? 64;
        const half = o.half ?? 0.5;
        const fieldBuf = instancedArray(new Float32Array(res * res * res), 'float');
        // write through the attribute's OWN array — instancedArray does not
        // alias the JS array you hand it
        const field = fieldBuf.value.array;
        const isoU = uniform(o.iso ?? 50);
        const STEPS = o.steps ?? 160;
        const col = new THREE.Color(o.color ?? 0x9aa2ac);
        const metal = o.metalness ?? 0.85;
        const rough = o.roughness ?? 0.35;

        // world bounds captured at bind() (parent must be world-static)
        const bMin = uniform(new THREE.Vector3(-half, 0, -half));
        const bMax = uniform(new THREE.Vector3(half, 2 * half, half));

        // trilinear field sample at a WORLD point — node-centered grid to
        // match the (i/(res-1)) mapping the CNC/print field writers use
        const R1 = float(res - 1), RI = int(res - 1);
        const RES = res, RES2 = res * res;
        const sampleF = (wp) => {
            const gp = wp.sub(bMin).div(bMax.sub(bMin)).mul(R1);
            const gi = floor(gp);
            const f = gp.sub(gi);
            const at = (ox, oy, oz) => {
                const cx = max(int(0), min(RI, int(gi.x).add(int(ox))));
                const cy = max(int(0), min(RI, int(gi.y).add(int(oy))));
                const cz = max(int(0), min(RI, int(gi.z).add(int(oz))));
                return fieldBuf.element(cx.add(cy.mul(int(RES))).add(cz.mul(int(RES2))));
            };
            const x00 = mix(at(0, 0, 0), at(1, 0, 0), f.x);
            const x10 = mix(at(0, 1, 0), at(1, 1, 0), f.x);
            const x01 = mix(at(0, 0, 1), at(1, 0, 1), f.x);
            const x11 = mix(at(0, 1, 1), at(1, 1, 1), f.x);
            return mix(mix(x00, x10, f.y), mix(x01, x11, f.y), f.z);
        };

        // the march returns WHERE it hit (xyz) + whether it hit (w); color,
        // opacity and depth all derive from this ONE node
        const rd = normalize(positionWorld.sub(cameraPosition));
        const march = Fn(() => {
            const ro = cameraPosition;
            const inv = vec3(1).div(rd);
            const ta = bMin.sub(ro).mul(inv);
            const tb = bMax.sub(ro).mul(inv);
            const tsm = min(ta, tb), tbg = max(ta, tb);
            const tEnter = max(max(tsm.x, tsm.y), tsm.z).max(0.0);
            const tExit = min(min(tbg.x, tbg.y), tbg.z);
            const dt = tExit.sub(tEnter).div(float(STEPS));
            const t = tEnter.add(dt.mul(0.5)).toVar();
            const found = float(0).toVar();
            const hp = vec3(0, 0, 0).toVar();
            Loop({ start: 0, end: STEPS, type: 'int' }, () => {
                If(t.greaterThan(tExit), () => Break());
                const wp = ro.add(rd.mul(t));
                If(sampleF(wp).greaterThan(isoU), () => {
                    hp.assign(wp);
                    found.assign(1.0);
                    Break();
                });
                t.addAssign(dt);
            });
            return vec4(hp, found);
        })();
        const hp = march.xyz;
        const found = march.w;

        // normal from the field gradient (field is high INSIDE)
        const cell = bMax.sub(bMin).div(R1);
        const nx = sampleF(hp.add(vec3(cell.x, 0, 0))).sub(sampleF(hp.sub(vec3(cell.x, 0, 0))));
        const ny = sampleF(hp.add(vec3(0, cell.y, 0))).sub(sampleF(hp.sub(vec3(0, cell.y, 0))));
        const nz = sampleF(hp.add(vec3(0, 0, cell.z))).sub(sampleF(hp.sub(vec3(0, 0, cell.z))));
        const n = normalize(vec3(nx, ny, nz).negate());

        // ── material: REAL scene lighting. MeshStandardNodeMaterial with the
        // raymarch gradient as normalNode — the engine's PBR + the scene's
        // lights + auto-enhance SSR/bloom light the solid exactly like every
        // other mesh (hand-rolled shading read as matte chalk). Lighting
        // evaluates at the proxy-box fragment position, not the hit point —
        // point-light falloff is approximate within the box, which reads fine
        // at machine scale.
        let mat;
        if (o.flat || o.shade === 'normals') {
            mat = new THREE.MeshBasicNodeMaterial({ side: THREE.BackSide });
            mat.colorNode = o.flat ? vec3(0.9, 0.4, 0.9) : n.mul(0.5).add(0.5);
        } else {
            mat = new THREE.MeshStandardNodeMaterial({ side: THREE.BackSide, metalness: metal, roughness: rough });
            // colorNode/roughnessNode hooks receive the HIT POINT (world) —
            // build procedural surfaces from hp, never positionWorld (that's
            // the proxy box fragment, not the surface)
            mat.colorNode = o.colorNode ? o.colorNode(hp, n) : vec3(col.r, col.g, col.b);
            if (o.roughnessNode) mat.roughnessNode = o.roughnessNode(hp, n);
            mat.normalNode = cameraViewMatrix.mul(vec4(n, 0.0)).xyz;   // view-space normal slot
            if (o.emissive) mat.emissiveNode = o.emissive(hp, n);
        }
        // opaque + alpha-test discard + TRUE hit-point depth: correct
        // occlusion against scene geometry in BOTH directions (the
        // transparent/BackSide/no-depth approach let anything between the
        // camera and the box's BACK faces draw over the surface)
        mat.opacityNode = found;
        mat.alphaTest = 0.5;
        const clip = cameraProjectionMatrix.mul(cameraViewMatrix).mul(vec4(hp, 1.0));
        mat.depthNode = clip.z.div(clip.w);
        const mesh = new THREE.Mesh(new THREE.BoxGeometry(2 * half, 2 * half, 2 * half), mat);
        mesh.position.set(0, half, 0);
        mesh.frustumCulled = false;
        mesh.userData.noSupportCheck = true;
        mesh.userData.noClippingCheck = true;
        mesh.userData.noZFightCheck = true;
        if (o.parent) o.parent.add(mesh);

        let bound = false;
        const api = {
            mesh, field, res,
            idx: (x, y, z) => x + y * RES + z * RES2,
            uniforms: { iso: isoU, bMin, bMax },
            // capture WORLD bounds from wherever the mesh ended up parented
            bind() {
                mesh.updateWorldMatrix(true, false);
                const wp = new THREE.Vector3().setFromMatrixPosition(mesh.matrixWorld);
                bMin.value.set(wp.x - half, wp.y - half, wp.z - half);
                bMax.value.set(wp.x + half, wp.y + half, wp.z + half);
                bound = true;
            },
            upload() {
                if (!bound) api.bind();
                fieldBuf.value.needsUpdate = true;
            },
        };
        return api;
    }

    globalThis.makeIsoField = makeIsoField;
    console.log('[iso_field] makeIsoField ready — GPU-raymarched isosurface over a CPU-written voxel field (true hit-point depth, scene-light shading)');
})();
