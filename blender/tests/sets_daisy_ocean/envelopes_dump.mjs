// envelopes_dump.mjs <three build dir> <out.json>: the untouched eidoverse/sets/ocean/house.js and apparitions.js run
// headless in Deno, and their update(u, t) sampled: the house's window and porch levels (and its two lights), the
// robot's rise, dissolve, eyes, height and visibility, the human of light's. Their timing never reads the GLBs'
// contents, so GLTFLoader is a stub that hands back one small box for every file (the files are still read).
//   deno run --no-config --no-lock -A envelopes_dump.mjs <three build> <out.json>
const [threeDir, outPath] = Deno.args;
const url = (p) => new URL('file:///' + p.replace(/\\/g, '/').replace(/^\/+/, ''));
const W = await import(url(threeDir + '/three.webgpu.js'));
const THREE = { ...W, ...W.TSL };
globalThis.GLTFLoader = class {
    parse(_buf, _path, res) {
        const scene = new THREE.Group();
        const m = new THREE.MeshStandardMaterial();
        m.name = 'body';
        scene.add(new THREE.Mesh(new THREE.BoxGeometry(1, 2, 1), m));
        res({ scene });
    }
};
const here = new URL('.', import.meta.url);
const H = await import(new URL('../../../eidoverse/sets/ocean/house.js', here).href);
const A = await import(new URL('../../../eidoverse/sets/ocean/apparitions.js', here).href);
const house = await H.buildHouse(THREE, {});
const app = await A.buildApparitions(THREE, { base: new THREE.Vector3(0, 0, 0), yaw: 0 });
if (!house || !app.robot || !app.human) throw new Error('the house or the figures did not build');
const out = { house: [], robot: [], human: [] };
for (let k = 0; k <= 900; k++) {                       // u 21.5 .. 30.5: the window at 22.52, the porch at 28.13
    const u = 21.5 + k * 0.01, t = 100 + u;
    house.update(u, t);
    out.house.push([u, t, house.U.win.value, house.U.porch.value, house.porchLight.intensity, house.winLight.intensity]);
}
for (let k = 0; k <= 420; k++) {                       // u 14.5 .. 18.7: the robot from 15.0, the human from 16.45
    const u = 14.5 + k * 0.01, t = 100 + u;
    app.update(u, t);
    out.robot.push([u, app.robot.holder.visible ? 1 : 0, app.robot.holder.position.y, app.U.rDiss.value, app.U.rEyes.value,
        app.U.rBase.value, app.U.rTop.value]);
    out.human.push([u, app.human.holder.visible ? 1 : 0, app.human.holder.position.y, app.U.hDiss.value]);
}
Deno.writeTextFileSync(outPath, JSON.stringify(out));
console.log('[envelopes_dump]', out.house.length, 'house samples,', out.robot.length, 'figure samples');
