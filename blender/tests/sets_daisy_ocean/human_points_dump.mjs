// human_points_dump.mjs <three build dir> <dir prefix> <out.json>: the untouched eidoverse/sets/ocean/apparitions.js
// run headless with three's GLTFLoader (an import map points 'three' at the same three.webgpu.js module): it loads
// <prefix>human.glb (the prefix's folder holds no robot.glb, so the robot is skipped as missing, as the set does when
// a file is absent) and samples its 5200 points of light; their centres and random draws are dumped.
//   deno run --no-config --no-lock -A --import-map=<map.json> human_points_dump.mjs <three build> <prefix> <out.json>
const [threeDir, prefix, outPath] = Deno.args;
const url = (p) => new URL('file:///' + p.replace(/\\/g, '/').replace(/^\/+/, ''));
const W = await import('three');
const THREE = { ...W, ...W.TSL };
const { GLTFLoader } = await import(url(threeDir + '/../examples/jsm/loaders/GLTFLoader.js'));
globalThis.GLTFLoader = GLTFLoader;
const here = new URL('.', import.meta.url);
const A = await import(new URL('../../../eidoverse/sets/ocean/apparitions.js', here).href);
const app = await A.buildApparitions(THREE, { dir: prefix, base: new THREE.Vector3(0, 0, 0), yaw: 0 });
if (!app.human) throw new Error('the human did not load');
const pts = app.human.holder.children.find((o) => o.geometry?.attributes?.center);
const cen = pts.geometry.attributes.center.array, rnd = pts.geometry.attributes.rnd.array;
const out = { n: cen.length / 12, robot: !!app.robot, center: [], rnd: [] };
for (let i = 0; i < out.n; i++) {
    out.center.push([cen[i * 12], cen[i * 12 + 1], cen[i * 12 + 2]]);
    out.rnd.push([rnd[i * 16], rnd[i * 16 + 1], rnd[i * 16 + 2], rnd[i * 16 + 3]]);
}
Deno.writeTextFileSync(outPath, JSON.stringify(out));
console.log('[human_points_dump]', out.n, 'points; robot loaded:', out.robot);
