// geometry_reference.mjs: three r184's geometry generators, as the two interiors call them, dumped to JSON for the
// Blender port's geometry parity test (test_geometry_parity.py). Also interiors_lib.js's boxUV and
// BufferGeometryUtils.mergeVertices on the toaster body.
//
//   deno run --no-config --no-lock --cached-only --import-map=three_import_map.json -A geometry_reference.mjs <out.json>
import * as THREE from 'three';
import { RoundedBoxGeometry } from 'three/addons/geometries/RoundedBoxGeometry.js';
import * as BGU from 'three/addons/utils/BufferGeometryUtils.js';

const boxUV = (geo, scale = 1) => {          // interiors_lib.js boxUV (copied: the module itself imports napi canvas)
    const g = geo.index ? geo.toNonIndexed() : geo;
    const p = g.attributes.position, n = p.count, uv = new Float32Array(n * 2);
    const a = [0, 0, 0], b = [0, 0, 0], c = [0, 0, 0];
    for (let i = 0; i < n; i += 3) {
        for (let k = 0; k < 3; k++) { a[k] = p.getComponent(i, k); b[k] = p.getComponent(i + 1, k); c[k] = p.getComponent(i + 2, k); }
        const e1 = [b[0] - a[0], b[1] - a[1], b[2] - a[2]], e2 = [c[0] - a[0], c[1] - a[1], c[2] - a[2]];
        const nx = Math.abs(e1[1] * e2[2] - e1[2] * e2[1]), ny = Math.abs(e1[2] * e2[0] - e1[0] * e2[2]), nz = Math.abs(e1[0] * e2[1] - e1[1] * e2[0]);
        for (let v = 0; v < 3; v++) {
            const x = p.getX(i + v), y = p.getY(i + v), z = p.getZ(i + v);
            let u, w;
            if (nx >= ny && nx >= nz) { u = z; w = y; } else if (ny >= nz) { u = x; w = z; } else { u = x; w = y; }
            uv[(i + v) * 2] = u * scale; uv[(i + v) * 2 + 1] = w * scale;
        }
    }
    g.setAttribute('uv', new THREE.BufferAttribute(uv, 2));
    return g;
};
const dump = (g) => ({
    pos: Array.from(g.attributes.position.array), nrm: g.attributes.normal ? Array.from(g.attributes.normal.array) : null,
    uv: g.attributes.uv ? Array.from(g.attributes.uv.array) : null, index: g.index ? Array.from(g.index.array) : null,
});
const out = {};
out.box = dump(new THREE.BoxGeometry(0.5, 0.3, 0.2, 2, 1, 3));
out.plane = dump(new THREE.PlaneGeometry(1.2, 0.8, 3, 2));
out.cylinder = dump(new THREE.CylinderGeometry(0.1, 0.2, 0.5, 12, 2, false));
out.cylinder_open = dump(new THREE.CylinderGeometry(1.46, 1.48, 0.11, 96, 1, true));
out.cone = dump(new THREE.ConeGeometry(0.4, 2.5, 40, 1, true));
out.sphere = dump(new THREE.SphereGeometry(0.9, 8, 6));
out.sphere_dome = dump(new THREE.SphereGeometry(900, 48, 24));
out.rounded_box = dump(new RoundedBoxGeometry(0.50, 0.075, 0.47, 3, 0.03));
out.rounded_box_1 = dump(new RoundedBoxGeometry(0.52, 0.62, 0.03, 1, 0.01));
out.tube = dump(new THREE.TubeGeometry(new THREE.CatmullRomCurve3([new THREE.Vector3(0.26, 1.11, -0.24), new THREE.Vector3(0.25, 1.30, -0.22),
    new THREE.Vector3(0.18, 1.40, -0.08), new THREE.Vector3(0.08, 1.36, 0.0)]), 20, 0.008, 8));
const Dz = 0.19;
out.cord = dump(new THREE.TubeGeometry(new THREE.CatmullRomCurve3([[-0.1, 0.02, -Dz / 2], [-0.12, 0.004, -Dz / 2 - 0.06], [-0.06, 0.004, -0.2],
    [0.05, 0.004, -0.255], [0.09, -0.02, -0.282], [0.10, -0.25, -0.285], [0.07, -0.48, -0.29]].map(([x, y, z]) => new THREE.Vector3(x, y, z))), 60, 0.0035, 8));
{   // the lectern column
    const shp = new THREE.Shape(); shp.moveTo(-0.24, 0); shp.lineTo(0.24, 0); shp.lineTo(0.30, 1.0); shp.lineTo(-0.30, 1.0); shp.lineTo(-0.24, 0);
    out.lectern = dump(new THREE.ExtrudeGeometry(shp, { depth: 0.40, bevelEnabled: true, bevelSize: 0.012, bevelThickness: 0.012, bevelSegments: 2 }));
}
{   // the toaster body, and mergeVertices on it as showroom.js does
    const Lx = 0.29, Hy = 0.205, bev = 0.024, bevT = 0.03;
    const sh = new THREE.Shape();
    const w = Lx - 2 * bev, h = Hy - 2 * bev - 0.012, rt = 0.055, rb = 0.012;
    sh.moveTo(-w / 2 + rb, 0); sh.lineTo(w / 2 - rb, 0); sh.quadraticCurveTo(w / 2, 0, w / 2, rb);
    sh.lineTo(w / 2, h - rt); sh.quadraticCurveTo(w / 2, h, w / 2 - rt, h);
    sh.lineTo(-w / 2 + rt, h); sh.quadraticCurveTo(-w / 2, h, -w / 2, h - rt);
    sh.lineTo(-w / 2, rb); sh.quadraticCurveTo(-w / 2, 0, -w / 2 + rb, 0);
    let body = new THREE.ExtrudeGeometry(sh, { depth: Dz - 2 * bevT, bevelEnabled: true, bevelSize: bev, bevelThickness: bevT, bevelSegments: 7, curveSegments: 16 });
    out.toaster = dump(body);
    body = body.clone(); body.deleteAttribute('uv'); body.deleteAttribute('normal');
    body = BGU.mergeVertices(body, 1e-5); body.computeVertexNormals();
    out.toaster_merged = dump(body);
}
{   // a toast slice
    const sl = new THREE.Shape(); const bw = 0.118, bh = 0.118;
    sl.moveTo(-bw / 2, 0); sl.lineTo(bw / 2, 0); sl.lineTo(bw / 2, bh * 0.7);
    sl.bezierCurveTo(bw / 2 + 0.012, bh * 0.98, bw * 0.12, bh * 1.04, 0, bh * 0.92);
    sl.bezierCurveTo(-bw * 0.12, bh * 1.04, -bw / 2 - 0.012, bh * 0.98, -bw / 2, bh * 0.7);
    sl.lineTo(-bw / 2, 0);
    out.toast = dump(new THREE.ExtrudeGeometry(sl, { depth: 0.011, bevelEnabled: true, bevelSize: 0.002, bevelThickness: 0.002, bevelSegments: 2 }));
}
{   // the dais top: a shape with two holes
    const D = { z0: -8.85, z1: -5.6, x: 4.6 };
    const top = new THREE.Shape();
    top.moveTo(-D.x, -D.z1); top.lineTo(D.x, -D.z1); top.lineTo(D.x, -D.z0); top.lineTo(-D.x, -D.z0); top.lineTo(-D.x, -D.z1);
    for (const [hx, z0, z1] of [[1.45, -6.45, -6.02], [1.3, -6.9 - 0.3 - 0.4, -6.9 - 0.3 - 0.12]]) {
        const hp = new THREE.Path(); hp.moveTo(-hx, -z1); hp.lineTo(-hx, -z0); hp.lineTo(hx, -z0); hp.lineTo(hx, -z1); hp.lineTo(-hx, -z1);
        top.holes.push(hp);
    }
    out.dais = dump(new THREE.ShapeGeometry(top));
}
out.box_uv = dump(boxUV(new THREE.BoxGeometry(1.06, 2.16, 0.06), 1 / 2.2));
Deno.writeTextFileSync(Deno.args[0], JSON.stringify(out));
console.log('[geometry_reference] wrote', Object.keys(out).length, 'geometries');
