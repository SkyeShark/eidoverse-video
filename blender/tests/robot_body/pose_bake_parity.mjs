// eidoverse/pose_bake.js run as shipped, for test_pose_bake.py: the JS side of the parity checks.
//   deno run --no-config --no-lock -A pose_bake_parity.mjs <three.module.js> <pose_bake.js> key <files.json>
//       prints {"key": bakeKey(files, extra)} for {"files": [...], "extra": "..."}
//   ... read <bake file> <frames.json> <out.json>
//       binds an Object3D to every track of the file's header (and a mock mesh per morph), load()s it with the header's
//       key, applies the listed frames and writes every track's position / quaternion / scale and every influence
//   ... write <in.json> <bake file>
//       records the given per-frame values (tracks: Object3Ds; morphs: mock meshes) and save()s them with the given key
const [threePath, pbPath, mode, a1, a2, a3] = Deno.args;
const toUrl = (p) => 'file:///' + p.replace(/\\/g, '/').replace(/^\/+/, '');
const THREE = await import(toUrl(threePath));
const PB = await import(toUrl(pbPath));

if (mode === 'key') {
    const spec = JSON.parse(Deno.readTextFileSync(a1));
    console.log(JSON.stringify({ key: await PB.bakeKey(spec.files, spec.extra ?? '') }));
} else if (mode === 'read') {
    const file = a1, ks = JSON.parse(Deno.readTextFileSync(a2)).frames;
    const h = PB.bakeHeader(file);
    const tracks = h.tracks.map((name) => ({ name, obj: new THREE.Object3D() }));
    const morphs = h.morphs.map((m) => ({ name: m.name, mesh: { morphTargetInfluences: new Array(m.n).fill(0) } }));
    const bake = PB.createPoseBake(THREE, { tracks, morphs, frames: h.frames, fps: h.fps, file, key: h.key });
    const ok = bake.load();
    const out = { ok, header: { key: h.key, frames: h.frames, fps: h.fps, full: h.full, cols: h.cols.length }, frames: {} };
    if (ok) {
        for (const k of ks) {
            bake.apply(k);
            bake.applyMorphs(k);
            const row = [];
            for (const { obj: o } of tracks) row.push(o.position.x, o.position.y, o.position.z, o.quaternion.x, o.quaternion.y,
                o.quaternion.z, o.quaternion.w, o.scale.x, o.scale.y, o.scale.z);
            for (const { mesh } of morphs) row.push(...mesh.morphTargetInfluences);
            out.frames[k] = row;
        }
        // refusals: a wrong key, a renamed track
        const bad1 = PB.createPoseBake(THREE, { tracks, morphs, frames: h.frames, fps: h.fps, file, key: 'f'.repeat(24) });
        const t2 = tracks.map((t, i) => (i === 0 ? { name: t.name + '_x', obj: t.obj } : t));
        const bad2 = PB.createPoseBake(THREE, { tracks: t2, morphs, frames: h.frames, fps: h.fps, file, key: h.key });
        out.refused = { wrong_key: !bad1.load(), renamed_track: !bad2.load() };
    }
    Deno.writeTextFileSync(a3, JSON.stringify(out));
    console.log(`[pose_bake_parity] read ${file}: ok ${ok}, ${ks.length} frames applied`);
} else if (mode === 'write') {
    const spec = JSON.parse(Deno.readTextFileSync(a1)), file = a2;
    const tracks = spec.tracks.map((name) => ({ name, obj: new THREE.Object3D() }));
    const morphs = spec.morphs.map((m) => ({ name: m.name, mesh: { morphTargetInfluences: new Array(m.n).fill(0) } }));
    const bake = PB.createPoseBake(THREE, { tracks, morphs, frames: spec.frames, fps: spec.fps, file, key: spec.key });
    for (let k = 0; k < spec.frames; k++) {
        const row = spec.values[k];
        let c = 0;
        for (const { obj: o } of tracks) {
            o.position.set(row[c], row[c + 1], row[c + 2]);
            o.quaternion.set(row[c + 3], row[c + 4], row[c + 5], row[c + 6]);
            o.scale.set(row[c + 7], row[c + 8], row[c + 9]);
            c += 10;
        }
        for (const { mesh } of morphs) for (let j = 0; j < mesh.morphTargetInfluences.length; j++) mesh.morphTargetInfluences[j] = row[c++];
        bake.record(k);
    }
    const r = bake.save();
    console.log(JSON.stringify(r));
}
