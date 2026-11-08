// parity_dump.mjs — run the WebGPU engine's own terrain.js under Node and dump what it builds,
// so test_parity.py can compare the Blender port against it number for number.
//
//   node parity_dump.mjs <three.module.js> <terrain.js> '<makeTerrain opts as JSON>' '<[[x,z],...] probes>' <out.json>
//
// Only geometry is compared, so the node material is stubbed (TSL needs a renderer); the plane,
// its rotation and computeVertexNormals are three's real code.
import fs from 'node:fs';
import vm from 'node:vm';
import { pathToFileURL } from 'node:url';

const [threePath, terrainPath, optsJson, probesJson, outPath] = process.argv.slice(2);
const T = await import(pathToFileURL(threePath).href);
class StubNodeMaterial { constructor(o = {}) { Object.assign(this, o); } }
const tslStub = () => ({ x: null, y: null, z: null, mul: () => tslStub(), add: () => tslStub() });
globalThis.THREE = { ...T, MeshStandardNodeMaterial: StubNodeMaterial,
    attribute: tslStub, texture: tslStub, uv: tslStub };
vm.runInThisContext(fs.readFileSync(terrainPath, 'utf8'), { filename: terrainPath });

const opts = JSON.parse(optsJson);
const nLayers = opts.nLayers || 0;
delete opts.nLayers;
// layers only decide how many blend weights are baked (the maps are not read for geometry)
opts.layers = Array.from({ length: nLayers }, () => ({}));
const { mesh, heightAt } = globalThis.makeTerrain(opts);
const g = mesh.geometry;
const b64 = (arr) => Buffer.from(new Float32Array(arr).buffer).toString('base64');
const probes = JSON.parse(probesJson);
fs.writeFileSync(outPath, JSON.stringify({
    count: g.attributes.position.count,
    position: b64(g.attributes.position.array),
    normal: b64(g.attributes.normal.array),
    color: g.attributes.color ? b64(g.attributes.color.array) : null,
    uv: b64(g.attributes.uv.array),
    index: Array.from(g.index.array.slice(0, 12)),
    heightAt: probes.map(([x, z]) => heightAt(x, z)),
}));
console.log('[parity_dump] wrote', outPath, g.attributes.position.count, 'vertices');
