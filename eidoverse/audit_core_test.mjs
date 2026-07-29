// audit_core_test.mjs — metamorphic + adversarial tests for audit_core.js.
// Cases sourced from work/sol_collab/REVIEW_PHASE_A.md (findings 1-10) and
// PROPOSALS.md §9: equivalent physical scenes must produce equivalent
// inventories/coverage, and no declaration may escape persistence.
//   deno run --allow-all --node-modules-dir=auto eidoverse/audit_core_test.mjs
import * as THREE from 'npm:three@0.184.0';
import {
    buildInventory, mapDeclarations, coverageRecords, createLedger,
    digestFromLedger, snapshotPolicy,
} from './audit_core.js';

let failures = 0;
function check(name, cond, detail = '') {
    if (cond) console.log(`  ok   ${name}`);
    else { console.log(`  FAIL ${name} ${detail}`); failures++; }
}
function box(size = 1, x = 0, y = 0, z = 0) {
    const m = new THREE.Mesh(new THREE.BoxGeometry(size, size, size));
    m.position.set(x, y, z);
    return m;
}
function records(scene, opts = {}, policy = snapshotPolicy({})) {
    const inv = buildInventory(THREE, scene, opts);
    const decl = mapDeclarations(THREE, scene, inv, opts);
    return { inv, decl, recs: coverageRecords(decl, inv, policy, opts) };
}

// --- 1. hierarchy invariance incl. MESH-as-parent (review finding 1) --------
{
    console.log('1. hierarchy invariance (sibling / Group parent / Mesh parent)');
    const variants = [];
    for (const mode of ['sibling', 'group', 'meshparent']) {
        const scene = new THREE.Scene();
        const a = box(1, 0, 0, 0), b = box(1, 5, 0, 0);
        if (mode === 'sibling') { scene.add(a); scene.add(b); }
        else if (mode === 'group') { const g = new THREE.Group(); g.add(a); g.add(b); scene.add(g); }
        else { b.position.set(5, 0, 0); a.add(b); scene.add(a); }   // mesh parents mesh; world pos identical
        variants.push(buildInventory(THREE, scene).bodies.length);
    }
    check('2 separated boxes = 2 bodies under sibling/Group/Mesh parenting', variants.every((c) => c === 2), `got ${variants}`);
}

// --- 2. collision cannot define identity (review finding 2) -----------------
{
    console.log('2. embedding without provenance never merges');
    const scene = new THREE.Scene();
    scene.add(box(1, 0, 0, 0)); scene.add(box(1, 0.2, 0, 0));      // deep overlap, no provenance
    check('unrelated interpenetrating boxes stay 2 bodies', buildInventory(THREE, scene).bodies.length === 2);

    const s2 = new THREE.Scene();
    const root = new THREE.Group(); root.userData.__srcAsset = 'kitA';
    root.add(box(1, 0, 0, 0)); root.add(box(1, 0.2, 0, 0));        // same provenance + embedding
    s2.add(root);
    check('same-provenance embedded pair merges to 1 body', buildInventory(THREE, s2).bodies.length === 1);

    const s3 = new THREE.Scene();
    const r3 = new THREE.Group(); r3.userData.__srcAsset = 'kitA';
    r3.add(box(1, 0, 0, 0)); r3.add(box(1, 1.0, 0, 0));            // same provenance, face touch only
    s3.add(r3);
    check('same-provenance touching pair stays 2 bodies', buildInventory(THREE, s3).bodies.length === 2);
}

// --- 3. invisible enclosing hull glues nothing (review probe) ----------------
{
    console.log('3. invisible enclosure');
    const scene = new THREE.Scene();
    scene.add(box(1, -5, 0, 0)); scene.add(box(1, 0, 0, 0)); scene.add(box(1, 5, 0, 0));
    const hull = box(20, 0, 0, 0); hull.visible = false; scene.add(hull);
    const inv = buildInventory(THREE, scene);
    check('3 props + hidden 20m hull = 4 bodies, no gluing', inv.bodies.length === 4, `got ${inv.bodies.length}`);
}

// --- 4. leaf-sharding union (review finding 6) --------------------------------
{
    console.log('4. all-leaves-sharded multi-mesh body counts as FULL');
    const makeScene = (shard) => {
        const scene = new THREE.Scene();
        const root = new THREE.Group(); root.name = 'asset'; root.userData.__srcAsset = 'kitB';
        const a = box(1, 0, 0, 0), b = box(1, 0.2, 0, 0);          // one 2-leaf body
        root.add(a); root.add(b); scene.add(root);
        if (shard) { a.userData.allowIntersect = true; b.userData.allowIntersect = true; }
        else root.userData.allowIntersect = true;
        return scene;
    };
    const covs = [false, true].map((shard) => {
        const scene = makeScene(shard);
        const inv = buildInventory(THREE, scene);
        const u = mapDeclarations(THREE, scene, inv).unionByFlag.get('allowIntersect');
        return `${u.full.size}/${u.partial.size}`;
    });
    check('parent flag and per-leaf flags both yield full=1 partial=0', covs[0] === '1/0' && covs[1] === '1/0', `got ${covs}`);
}

// --- 5. per-sensor alias union (review finding 7) -----------------------------
{
    console.log('5. alias alternation cannot stay under the sensor union');
    const scene = new THREE.Scene();
    const a = box(1, 0, 0, 0); a.userData.allowIntersect = true;
    const b = box(1, 5, 0, 0); b.userData.noClippingCheck = true;
    const c = box(1, 10, 0, 0); c.userData.assembly = 'x';
    const d = box(1, 15, 0, 0);
    for (const m of [a, b, c, d]) scene.add(m);
    const { decl } = records(scene);
    const u = decl.unionBySensor.get('clipping');
    check('clipping sensor union spans all 3 alias spellings', u && u.full.size === 3, `got ${u && u.full.size}`);
}

// --- 6. ballast cannot dilute systemic coverage (review finding 8) ------------
{
    console.log('6. invisible/zero-tri ballast excluded from denominators');
    const scene = new THREE.Scene();
    const real = box(1, 0, 0, 0); real.userData.noSupportCheck = true; scene.add(real);
    for (let i = 0; i < 50; i++) { const m = box(1, 100 + i * 5, 0, 0); m.visible = false; scene.add(m); }
    const { recs } = records(scene);
    const sys = recs.find((r) => r.check === 'coverage.sensor.support');
    check('support coverage = 100% of PHYSICAL bodies despite 50 hidden ballast', sys && sys.metrics.fraction === 1, `got ${sys && sys.metrics.fraction}`);
    check('systemic warn fires', sys && sys.outcome === 'WARN');
}

// --- 7. InstancedMesh virtualization (review finding 4) -----------------------
{
    console.log('7. instanced virtual leaves; gap object not glued');
    const scene = new THREE.Scene();
    const im = new THREE.InstancedMesh(new THREE.BoxGeometry(1, 1, 1), new THREE.MeshBasicMaterial(), 2);
    const m4 = new THREE.Matrix4();
    im.setMatrixAt(0, m4.makeTranslation(-10, 0, 0));
    im.setMatrixAt(1, m4.makeTranslation(10, 0, 0));
    im.userData.__srcAsset = 'inst';
    scene.add(im);
    scene.add(box(1, 0, 0, 0));                                     // unrelated prop in the gap
    const inv = buildInventory(THREE, scene);
    check('2 instances + gap prop = 3 bodies', inv.bodies.length === 3, `got ${inv.bodies.length}`);
}

// --- 8. rotation-invariant scale descriptors (review finding 5) ---------------
{
    console.log('8. L invariant under rigid yaw');
    const Ls = [];
    for (const yaw of [0, Math.PI / 4]) {
        const scene = new THREE.Scene();
        const m = new THREE.Mesh(new THREE.BoxGeometry(10, 1, 1));
        m.rotation.y = yaw; scene.add(m);
        Ls.push(buildInventory(THREE, scene).bodies[0].L);
    }
    check('L identical at 0° and 45° yaw', Math.abs(Ls[0] - Ls[1]) < 1e-6, `got ${Ls}`);
}

// --- 9. truthy non-boolean globals (review finding 10) ------------------------
{
    console.log('9. truthy non-boolean global disables are recorded');
    const scene = new THREE.Scene(); scene.add(box(1));
    const policy = snapshotPolicy({ _noMotionCheck: 1 });
    const { recs } = records(scene, {}, policy);
    const hit = recs.find((r) => r.check === 'motion.envelope' && r.outcome === 'SKIPPED');
    check('_noMotionCheck=1 produces SKIPPED with non-boolean note', !!hit && hit.message.includes('non-boolean number'));
}

// --- 10. degenerate/extreme conditioning (review probe) -----------------------
{
    console.log('10. conditioning states');
    const scene = new THREE.Scene();
    const pts = new THREE.Mesh(new THREE.BufferGeometry(), new THREE.MeshBasicMaterial());
    pts.geometry.setAttribute('position', new THREE.BufferAttribute(new Float32Array([0, 0, 0]), 3));
    scene.add(pts);                                                  // zero-triangle, zero-extent
    scene.add(box(1, 5, 0, 0));
    const inv = buildInventory(THREE, scene);
    check('degenerate mesh is inventoried but not physical', inv.bodies.length === 2 && inv.physicalBodies.length === 1);
}

// --- 11. every declaration persists in the digest (review finding 16) ---------
{
    console.log('11. small declarations reach the persisted digest');
    const scene = new THREE.Scene();
    const a = box(1, 0, 0, 0); a.userData.noFacingCheck = true; a.name = 'lone_sign'; scene.add(a);
    for (let i = 0; i < 30; i++) scene.add(box(1, 10 + 5 * i, 0, 0));
    const ledger = createLedger();
    const { recs } = records(scene);
    for (const r of recs) ledger.record(r);
    const text = digestFromLedger(ledger);
    check('1-of-31 noFacingCheck appears in digest text', text.includes('noFacingCheck') && text.includes('lone_sign'));
    check('review gate is inside the persisted digest', text.includes('REVIEW GATE'));
}

// --- 12. clean semantics (review finding 15) ----------------------------------
{
    console.log('12. isClean');
    const scene = new THREE.Scene(); scene.add(box(1));
    const l1 = createLedger();
    for (const r of records(scene).recs) l1.record(r);
    check('bare scene is clean', l1.isClean());
    const l2 = createLedger();
    for (const r of records(scene, {}, snapshotPolicy({ _noAutoPlacementCheck: true })).recs) l2.record(r);
    check('global disable is NOT clean', !l2.isClean());
    const s3 = new THREE.Scene(); const m3 = box(1); m3.userData.allowIntersect = true; s3.add(m3);
    const l3 = createLedger();
    for (const r of records(s3).recs) l3.record(r);
    check('a declaration is NOT clean', !l3.isClean());
}

// --- 13. embedFrac validation --------------------------------------------------
{
    console.log('13. embedFrac clamps');
    const scene = new THREE.Scene();
    const root = new THREE.Group(); root.userData.__srcAsset = 'k';
    root.add(box(1, 0, 0, 0)); root.add(box(1, 1.0, 0, 0));         // touch only
    scene.add(root);
    const n0 = buildInventory(THREE, scene, { embedFrac: 0 }).bodies.length;
    const nn = buildInventory(THREE, scene, { embedFrac: NaN }).bodies.length;
    check('embedFrac 0/NaN cannot merge touching parts', n0 === 2 && nn === 2, `got ${n0},${nn}`);
}

// --- 14. explicit registration cannot merge islands (review finding 3) ---------
{
    console.log('14. coalescence declarations');
    const scene = new THREE.Scene();
    const g = new THREE.Group(); g.name = 'claimed_one_body';
    g.add(box(1, 0, 0, 0)); g.add(box(1, 8, 0, 0));
    scene.add(g);
    const inv = buildInventory(THREE, scene, { explicitBodies: [g] });
    check('islands stay separate bodies', inv.bodies.length === 2);
    check('registration recorded as coalescence declaration', inv.coalescenceDeclarations.length === 1 && inv.coalescenceDeclarations[0].islands === 2);
}

console.log(failures === 0 ? 'ALL PASS' : `${failures} FAILURE(S)`);
Deno.exit(failures === 0 ? 0 : 1);
