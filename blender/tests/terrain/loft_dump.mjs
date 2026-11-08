// loft_dump.mjs — run the engine's own loft.js under Node and dump a sweep's vertices, so
// test_loft.py can compare the Blender port against it.
//   node loft_dump.mjs <three.module.js> <loft.js> '<case json>' <out.json>
// case: { path: [[x,y,z],...] (three axes), profile: [n, r] circle | star: [ro, ri, pts], end: ..., sections,
//         scale: number | 'taper', twist }
import fs from 'node:fs';
import vm from 'node:vm';
import { pathToFileURL } from 'node:url';

const [threePath, loftPath, caseJson, outPath] = process.argv.slice(2);
const T = await import(pathToFileURL(threePath).href);
class StubNodeMaterial { constructor(o = {}) { Object.assign(this, o); } }
globalThis.THREE = { ...T, MeshStandardNodeMaterial: StubNodeMaterial };
vm.runInThisContext(fs.readFileSync(loftPath, 'utf8'), { filename: loftPath });
const L = globalThis.Loft;
const c = JSON.parse(caseJson);
const ring = (d) => d.kind === 'star' ? L.star(d.ro, d.ri, d.points) : L.circle(d.r, d.n);
const mesh = L.sweep({
    path: c.path.map((p) => new T.Vector3(p[0], p[1], p[2])),
    profile: ring(c.profile),
    profileEnd: c.end ? ring(c.end) : undefined,
    sections: c.sections,
    scale: c.scale === 'taper' ? ((t) => 1 - 0.6 * t) : c.scale,
    twist: c.twist,
    closed: true,
});
const pos = mesh.geometry.attributes.position.array;
fs.writeFileSync(outPath, JSON.stringify({ position: Array.from(pos), count: pos.length / 3 }));
console.log('[loft_dump] wrote', outPath, pos.length / 3, 'vertices');
