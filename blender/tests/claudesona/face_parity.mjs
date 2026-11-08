// face_parity.mjs: claudesona_face.js's drivers (makeSuitMouth, makeVisemeTrack, makeFaceTrack, mergeMax) and the
// wardrobe's tables (WARDROBE, BADGES, MODIFICANTI, FINAL_CHORUS), run in deno on a job's inputs, as the reference the
// Blender port is measured against. Prints a result JSON on stdout.
//
//   deno run --no-config --no-lock -A face_parity.mjs <job.json>
//
// job: { root: <worktree>, times: [t...], visemes: [{aa, ih, ou, ee, oh} per time], suit: {opts},
//        events: [{t0, t1, v}], track: {opts}, TL: {sections, captions}, face: {sectionBase, lineCues: [[src, flags, feel]],
//        closeAfterLast}, merge: [[w...]] }
const job = JSON.parse(Deno.readTextFileSync(Deno.args[0]));
const root = 'file:///' + job.root.replace(/\\/g, '/') + '/eidoverse/';
const F = await import(root + 'claudesona_face.js');
const out = {};
if (job.visemes) {
    const m = F.makeSuitMouth(job.suit || {});
    out.suit = job.times.map((t, i) => m.update(t, job.visemes[i]));
}
if (job.events) {
    const tr = F.makeVisemeTrack(job.events, job.track || {});
    out.track = job.times.map((t) => tr.at(t));
}
if (job.TL) {
    const cues = (job.face.lineCues || []).map(([src, flags, feel]) => [new RegExp(src, flags), feel]);
    const ft = F.makeFaceTrack(job.TL, { sectionBase: job.face.sectionBase || {}, lineCues: cues, closeAfterLast: job.face.closeAfterLast ?? true });
    out.feel = job.times.map((t) => ft.at(t));
}
if (job.merge) out.merge = job.merge.map((ws) => F.mergeMax(...ws));
out.constants = { SUIT_VISEMES: F.SUIT_VISEMES, VISEME_SHAPES: F.VISEME_SHAPES, LINE_WARP: F.LINE_WARP, VISEMES: F.VISEMES,
    PHONE_VISEME: F.PHONE_VISEME, MOUTH_OPEN: F.MOUTH_OPEN, MOUTH_ROUND: F.MOUTH_ROUND };
if (job.wardrobe) {
    globalThis.loadImageTexture = async () => null;
    const W = await import(root + 'claudesona_wardrobe.js');
    out.wardrobe = { WARDROBE: W.WARDROBE, BADGES: W.BADGES, MODIFICANTI: W.MODIFICANTI, FINAL_CHORUS: W.FINAL_CHORUS };
}
console.log(JSON.stringify(out));
