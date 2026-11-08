// Runs the engine's rhombic_dodecahedron.js as written (three from node_modules, a window shim) and prints JSON:
// the cell's triangles and normals, and the lattice points of fillVolumeRD, fillSphereRD and voxelizeMeshRD.
//   deno run --no-config --no-lock -A rd_dump.mjs <eidoverse dir> <three.module.js>
const [eidoDir, threePath] = Deno.args;
const THREE = await import('file:///' + threePath.replace(/\\/g, '/'));
globalThis.window = globalThis;
globalThis.THREE = THREE;
const src = await Deno.readTextFile(eidoDir + '/rhombic_dodecahedron.js');
(0, eval)(src);

const geo = window.createRhombicDodecahedron(0.5);
const out = {
    cell: {
        positions: Array.from(geo.getAttribute('position').array),
        normals: Array.from(geo.getAttribute('normal').array),
    },
};
const mat = new THREE.MeshBasicMaterial();
out.volume = window.fillVolumeRD({ bounds: { x: [-1.5, 1.5], y: [0, 2], z: [-1, 1.3] }, cellSize: 0.5, material: mat })._rdPoints;
out.sphere = window.fillSphereRD({ center: [0.2, 1.0, -0.3], radius: 1.4, cellSize: 0.4, material: mat })._rdPoints;
const box = new THREE.Mesh(new THREE.BoxGeometry(2, 1, 1.5), mat);
box.position.set(0.13, 0.07, -0.04);     // no lattice point (multiples of 0.3) on a face: no ties
out.voxelized = window.voxelizeMeshRD({ mesh: box, cellSize: 0.3, material: mat })._rdPoints;
console.log(JSON.stringify(out));
