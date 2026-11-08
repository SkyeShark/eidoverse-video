// three r184's own geometry builders, sampled for the Python ports' parity checks (test_kit_geometry.py):
//   deno run --no-config --no-lock -A blender/tests/voice_machines_b/geometry_parity_dump.mjs \
//       <node_modules/three/build dir, e.g. the main checkout's> blender/tests/voice_machines_b/out/geometry_js.json
// The era-1 craft kit builds its runtime parts with these (rbox = RoundedBoxGeometry, the lamp bulbs, the keys, the
// vacuum-column bends, the paper roll, the loop runs) and tandem.js's stoker is TeapotGeometry. The two addons import
// the bare 'three'; they are loaded with that specifier pointed at the build folder given.
const [threeDir, outPath] = Deno.args;
if (!threeDir || !outPath) throw new Error('usage: geometry_parity_dump.mjs <three build dir> <out.json>');
const dir = new URL('file:///' + threeDir.replace(/\\/g, '/').replace(/^\/+/, '').replace(/\/?$/, '/'));
const threeURL = new URL('three.module.js', dir);
const THREE = await import(threeURL.href);
async function addon(name) {
    const src = await Deno.readTextFile(new URL(`../examples/jsm/geometries/${name}.js`, dir));
    const patched = src.replaceAll("from 'three'", `from '${threeURL.href}'`);
    const b64 = btoa(String.fromCharCode(...new TextEncoder().encode(patched)));
    return await import('data:text/javascript;base64,' + b64);
}
const { RoundedBoxGeometry } = await addon('RoundedBoxGeometry');
const { TeapotGeometry } = await addon('TeapotGeometry');

const dump = (g) => ({
    position: Array.from(g.attributes.position.array),
    normal: Array.from(g.attributes.normal.array),
    uv: Array.from(g.attributes.uv.array),
    index: g.index ? Array.from(g.index.array) : null,
    groups: g.groups.map((q) => [q.start, q.count, q.materialIndex]),
});
const kitR = (w, h, d, r) => Math.max(1e-4, Math.min(r, w / 2 - 1e-4, h / 2 - 1e-4, d / 2 - 1e-4));   // the kit's rbox clamp
const out = {
    rbox_button: dump(new RoundedBoxGeometry(0.0145, 0.010, 0.0145, 2, kitR(0.0145, 0.010, 0.0145, 0.0025))),
    rbox_lens: dump(new RoundedBoxGeometry(0.066, 0.028, 0.006, 2, kitR(0.066, 0.028, 0.006, 0.002))),
    bulb: dump(new THREE.SphereGeometry(0.0062, 14, 8, 0, Math.PI * 2, 0, Math.PI / 2).rotateX(Math.PI / 2)),
    key: dump(new THREE.CylinderGeometry(0.0072, 0.0077, 0.017, 24, 1)),
    loop_bend: dump(new THREE.TorusGeometry(0.031, 0.0008, 6, 24, Math.PI)),
    roll: dump(new THREE.LatheGeometry([[0.012, -0.108], [0.035, -0.108], [0.035, 0.108], [0.012, 0.108]]
        .map(([r, y]) => new THREE.Vector2(r, y)), 64)),
    loop_run: dump(new THREE.BoxGeometry(0.0016, 0.9, 0.0127, 1, 8, 1)),
    teapot_body: dump(new TeapotGeometry(1, 20, true, false, true, true, false)),
    teapot_lid: dump(new TeapotGeometry(1, 20, false, true, false, true, false)),
};
// teletype.js paperGeo's curl (lines 567-572): a centripetal CatmullRomCurve3 through the layout's points, 72 spaced
const TL = JSON.parse(await Deno.readTextFile(new URL('../../../eidoverse/assets/models/voice_machines/teletype_layout.json',
    import.meta.url)));
{
    const Pp = TL.paper, PRINT_Z = Pp.printZ;
    const up = [[PRINT_Z + 0.0006, Pp.platenY + 0.03], [PRINT_Z - 0.002, Pp.coverTop + 0.02], [PRINT_Z - 0.010, 0.955],
        [PRINT_Z - 0.030, 1.005], [PRINT_Z - 0.070, 1.040], [PRINT_Z - 0.120, 1.056], [PRINT_Z - 0.170, 1.052], [PRINT_Z - 0.215, 1.036],
        [PRINT_Z - 0.250, 1.004], [PRINT_Z - 0.268, 0.950], [PRINT_Z - 0.273, 0.880], [PRINT_Z - 0.271, 0.800]];
    const curve = new THREE.CatmullRomCurve3(up.map(([z, y]) => new THREE.Vector3(0, y, z)));
    curve.curveType = 'centripetal';
    out.paper_curl = curve.getSpacedPoints(72).map((v) => [v.z, v.y]);
}
await Deno.writeTextFile(outPath, JSON.stringify(out));
console.log('geometry parity dump:', Object.entries(out).map(([k, v]) => `${k} ${v.position ? v.position.length / 3 : v.length}`)
    .join(', '));
