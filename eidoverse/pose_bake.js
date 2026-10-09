// pose_bake.js — solve a performance ONCE, then play it back for nothing.
//
// A scene that poses its characters live (arm IK, finger searches, collision-aware grips, prop fits) spends tens of ms
// of CPU per frame on every render and every probe. Bake it instead: run the live solve once over the whole piece,
// record what it WRITES each frame — local transforms of the bones and props it moves, and morph weights — and from
// then on every render (the film, a probe, a frame alone) just copies frame k back. The pose at frame k is then the
// same everywhere by construction, and playback is a memcpy.
//
//   import { createPoseBake, bakeKey } from '<eidoverse>/pose_bake.js';
//   const bake = createPoseBake(THREE, { tracks: [{ name, obj }], morphs: [{ name, mesh }], frames: N, fps: 30,
//                                        file: 'E:/proj/work/bake/perf.bin', key: await bakeKey([...source and data files]) });
//   if (!bake.load()) { for (let k = 0; k < N; k++) { poseLive(k / 30); bake.record(k); } bake.save(); }
//   // each frame: bake.apply(k) (transforms) -> what runs on top (vrm.update: raw bones, spring bones) -> bake.applyMorphs(k)
//
// RECORD what the solver writes, not what is derived from it: a VRM's NORMALIZED bones (vrm.update derives the raw bones
// and steps the spring bones from them at playback, exactly as live), the props it places, and any proxy a clip animates
// (a VRMA clip drives the VRM's 'VRMLookAtQuaternionProxy'; vrm.update turns it into the eyes: leave it out and the
// baked eyes stare at one stale angle).
// FACES: bake the body, drive the face live — as a game plays baked body animation and drives lipsync blendshapes at
// runtime. A face driver is cheap and a function of time; a baked face fights drivers that write at draw time.
// `morphs` is for the rare morph with no live driver. A track that never changes is stored once; the file is pruned to the tracks that move.
// The key must change whenever anything the solve reads changes (its source, its data, the assets): bakeKey hashes file
// contents (sources) and size + mtime (big assets). A stale bake is refused, never played.
const MAGIC = 'EIDO-POSEBAKE-1';

// A scene file that holds the performance AND its rendering (lights, camera, passes, logging) would re-key — and re-solve
// the whole piece — on every lighting or logging edit. Mark what the solve never reads:
//   /* bake-key: skip */ ... /* bake-key: end */
// and those regions drop out of that file's key (scripts under 4 MB; anything unmarked counts, so forgetting a marker
// only costs a re-solve, never a stale bake).
const SKIP = /\/\* bake-key: skip \*\/[\s\S]*?\/\* bake-key: end \*\//g;
export async function bakeKey(files, extra = '') {
    const parts = [extra];
    for (const f of files) {
        try {
            const st = Deno.statSync(f);
            if (st.size >= 4e6) { parts.push(`${f}:${st.size}:${st.mtime?.getTime()}`); continue; }
            let bytes = Deno.readFileSync(f);
            if (/\.(m?js|ts)$/i.test(f)) bytes = new TextEncoder().encode(new TextDecoder().decode(bytes).replace(SKIP, ''));
            parts.push(`${f}:${await sha256(bytes)}`);
        } catch (_) { parts.push(`${f}:missing`); }
    }
    return (await sha256(new TextEncoder().encode(parts.join('\n')))).slice(0, 24);
}
async function sha256(bytes) {
    const h = new Uint8Array(await crypto.subtle.digest('SHA-256', bytes));
    return [...h].map((b) => b.toString(16).padStart(2, '0')).join('');
}

// a bake file's header without loading it: { key, frames, fps, tracks: [names], morphs } — to play a SHIPPED bake
// (eidoverse/assets/animations/...) bind objects to its track names in this order and pass its key
export function bakeHeader(file) {
    const bytes = Deno.readFileSync(file);
    const hl = new DataView(bytes.buffer, bytes.byteOffset).getUint32(0, true);
    return JSON.parse(new TextDecoder().decode(bytes.subarray(4, 4 + hl)));
}

export function createPoseBake(_THREE, { tracks = [], morphs = [], frames, fps = 30, file, key }) {
    // full layout while recording: per track position(3) quaternion(4) scale(3); per morph mesh its influences
    const T = tracks.length, mN = morphs.map((m) => m.mesh.morphTargetInfluences?.length || 0);
    const full = T * 10 + mN.reduce((a, b) => a + b, 0);
    let rec = null, recorded = 0;
    let play = null;                         // { stride, data, xf: [{ obj, p, q, s }], mf: [{ mesh, idx, off | val }] }

    function record(k) {
        if (!rec) rec = new Float32Array(frames * full);
        let o = k * full;
        for (const { obj } of tracks) {
            const p = obj.position, q = obj.quaternion, s = obj.scale;
            rec[o++] = p.x; rec[o++] = p.y; rec[o++] = p.z; rec[o++] = q.x; rec[o++] = q.y; rec[o++] = q.z; rec[o++] = q.w;
            rec[o++] = s.x; rec[o++] = s.y; rec[o++] = s.z;
        }
        morphs.forEach(({ mesh }, i) => { const inf = mesh.morphTargetInfluences; for (let j = 0; j < mN[i]; j++) rec[o++] = inf[j]; });
        recorded = Math.max(recorded, k + 1);
    }

    // prune: a column that never changes is a constant; the rest are packed per frame
    function save() {
        if (!rec || recorded < frames) throw new Error(`[bake] save: ${recorded} of ${frames} frames recorded`);
        const varies = new Uint8Array(full);
        for (let c = 0; c < full; c++) { const v0 = rec[c]; for (let k = 1; k < frames; k++) if (rec[k * full + c] !== v0) { varies[c] = 1; break; } }
        const cols = []; for (let c = 0; c < full; c++) if (varies[c]) cols.push(c);
        const consts = {}; for (let c = 0; c < full; c++) if (!varies[c]) consts[c] = rec[c];
        const data = new Float32Array(frames * cols.length);
        for (let k = 0; k < frames; k++) for (let i = 0; i < cols.length; i++) data[k * cols.length + i] = rec[k * full + cols[i]];
        const header = { magic: MAGIC, key, frames, fps, full, cols, consts,
            tracks: tracks.map((t) => t.name), morphs: morphs.map((m, i) => ({ name: m.name, n: mN[i] })) };
        const hb = new TextEncoder().encode(JSON.stringify(header)), pad = (4 - ((4 + hb.length) % 4)) % 4;
        const out = new Uint8Array(4 + hb.length + pad + data.byteLength);
        new DataView(out.buffer).setUint32(0, hb.length + pad, true);
        out.set(hb, 4); out.fill(32, 4 + hb.length, 4 + hb.length + pad);
        out.set(new Uint8Array(data.buffer), 4 + hb.length + pad);
        const dir = file.replace(/[\\/][^\\/]*$/, ''), base = file.slice(dir.length + 1);
        try { Deno.mkdirSync(dir, { recursive: true }); } catch (_) { /* exists */ }
        Deno.writeFileSync(file, out);
        // a new key supersedes the old bakes of the same performance (same name before the key): only this one stays
        const stem = base.replace(/[0-9a-f]{24}\.bin$/, '');
        if (stem !== base) for (const e of Deno.readDirSync(dir)) if (e.isFile && e.name !== base && e.name.startsWith(stem) && /[0-9a-f]{24}\.bin$/.test(e.name)) Deno.removeSync(`${dir}/${e.name}`);
        rec = null;
        setup(header, data);
        return { tracks: T, columns: cols.length, of: full, mb: out.byteLength / 1e6 };
    }

    // load a bake made for exactly these tracks and this key (anything else: refused, the caller re-bakes)
    function load() {
        let bytes; try { bytes = Deno.readFileSync(file); } catch (_) { return false; }
        const hl = new DataView(bytes.buffer, bytes.byteOffset).getUint32(0, true);
        const header = JSON.parse(new TextDecoder().decode(bytes.subarray(4, 4 + hl)));
        const sameTracks = header.tracks.length === T && header.tracks.every((n, i) => n === tracks[i].name)
            && header.morphs.length === morphs.length && header.morphs.every((m, i) => m.name === morphs[i].name && m.n === mN[i]);
        if (header.magic !== MAGIC || header.key !== key || header.frames !== frames || !sameTracks) return false;
        const off = bytes.byteOffset + 4 + hl;
        const data = new Float32Array(bytes.buffer.slice(off, off + header.frames * header.cols.length * 4));
        setup(header, data);
        return true;
    }

    function setup(header, data) {
        const col = new Int32Array(header.full).fill(-1); header.cols.forEach((c, i) => { col[c] = i; });
        const get = (k, c) => (col[c] >= 0 ? data[k * header.cols.length + col[c]] : header.consts[c]);
        play = { get, header };
    }

    function apply(k) {
        if (!play) return false;
        k = Math.max(0, Math.min(frames - 1, k));
        const g = play.get;
        for (let i = 0; i < T; i++) {
            const o = tracks[i].obj, c = i * 10;
            o.position.set(g(k, c), g(k, c + 1), g(k, c + 2));
            o.quaternion.set(g(k, c + 3), g(k, c + 4), g(k, c + 5), g(k, c + 6));
            o.scale.set(g(k, c + 7), g(k, c + 8), g(k, c + 9));
        }
        return true;
    }
    // A face driver that writes its weights from mesh.onBeforeRender would overwrite the baked weights at draw time
    // with its last live state. While playing, such hooks are SUSPENDED (release() puts them back for a live frame).
    // Record what that hook would render: run the driver's write before record(k).
    const suspended = new Map();
    function applyMorphs(k) {
        if (!play) return false;
        k = Math.max(0, Math.min(frames - 1, k));
        let c = T * 10;
        morphs.forEach(({ mesh }, i) => {
            if (Object.prototype.hasOwnProperty.call(mesh, 'onBeforeRender') && !suspended.has(mesh)) { suspended.set(mesh, mesh.onBeforeRender); mesh.onBeforeRender = () => {}; }
            const inf = mesh.morphTargetInfluences; for (let j = 0; j < mN[i]; j++) inf[j] = play.get(k, c++);
        });
        return true;
    }
    function release() { for (const [mesh, fn] of suspended) mesh.onBeforeRender = fn; suspended.clear(); }
    return { record, save, load, apply, applyMorphs, release, get ready() { return !!play; }, frames, fps };
}
