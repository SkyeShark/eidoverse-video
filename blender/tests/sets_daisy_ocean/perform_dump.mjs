// perform_dump.mjs: the WebGPU edition's makePerformer (eidoverse/sets/ocean/perform.js, untouched) on a three.js copy
// of claude_suit's normalized rig (test_perform_parity.py writes it: each humanoid bone's rest position in model space
// and its humanoid parent; normalized rest rotations are identity), for the cases the test lists; dumps every bone's
// normalized quaternion after each call.
//   deno run --no-config --no-lock -A perform_dump.mjs <three build dir> <rig.json> <out.json>
const [threeDir, rigPath, outPath] = Deno.args;
const url = (p) => new URL('file:///' + p.replace(/\\/g, '/').replace(/^\/+/, ''));
const THREE = await import(url(threeDir + '/three.module.js'));
const here = new URL('.', import.meta.url);
const { makePerformer } = await import(new URL('../../../eidoverse/sets/ocean/perform.js', here).href);
const { rig, point, cases } = JSON.parse(await Deno.readTextFile(rigPath));
const scene = new THREE.Group();
const nodes = {};
for (const n of Object.keys(rig)) nodes[n] = new THREE.Object3D();
for (const [n, r] of Object.entries(rig)) {
    const p = r.parent ? rig[r.parent].pos : [0, 0, 0];
    nodes[n].position.set(r.pos[0] - p[0], r.pos[1] - p[1], r.pos[2] - p[2]);
    (r.parent ? nodes[r.parent] : scene).add(nodes[n]);
}
const vrm = { scene, humanoid: { getNormalizedBoneNode: (n) => nodes[n] ?? null, update() { } } };
const out = {};
for (const [name, c] of Object.entries(cases)) {
    for (const n of Object.values(nodes)) n.quaternion.identity();
    scene.updateMatrixWorld(true);
    const P = makePerformer(THREE);
    if (c.call === 'hand') P.handToFlower(vrm, c.w, c.opts);
    else P.lookAt(vrm, new THREE.Vector3(...point), c.w, c.opts);
    P.commit(vrm);
    out[name] = Object.fromEntries(Object.entries(nodes).map(([n, o]) => [n, [o.quaternion.x, o.quaternion.y, o.quaternion.z, o.quaternion.w]]));
}
await Deno.writeTextFile(outPath, JSON.stringify(out));
console.log(`[perform_dump] ${Object.keys(cases).length} cases on ${Object.keys(nodes).length} bones -> ${outPath}`);
