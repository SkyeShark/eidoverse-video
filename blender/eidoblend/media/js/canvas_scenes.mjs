// canvas_scenes.mjs — list the scenes of canvas screen modules as JSON, through preview_screens.mjs's own loader and
// timing (blender/eidoblend/media/canvas_scenes.py: list_scenes). Guide: tools-guides/motion-graphics.md.
//
//   deno run -A --no-config --node-modules-dir=none --cached-only canvas_scenes.mjs [--bpm 128] [--cues <json>] <module…>
//
// One JSON line: [{ name, label, fps, lines, dur, t0, module, prewarm }], in module order. `dur` and `t0` are the
// scene's cue as preview_screens.mjs's makeTiming gives it (lines × 8 beats at --bpm, or the scene's own dur; t0 from
// --cues, else 0). `prewarm` says whether the scene's module exports prewarm().
const P = await import(new URL('../../../../eidoverse/graphics/preview_screens.mjs', import.meta.url).href);

const args = [...Deno.args];
const opt = (name, dflt) => { const i = args.indexOf('--' + name); if (i < 0) return dflt; const v = args[i + 1]; args.splice(i, 2); return v; };
const BPM = +opt('bpm', 128), CUES = opt('cues', null);
const mods = args.filter((a) => /\.m?js$/i.test(a));
if (!mods.length) { console.error('usage: canvas_scenes.mjs [--bpm 128] [--cues <json>] <module…>'); Deno.exit(2); }
const ALL = await P.loadScenes(mods, BPM);
const T = P.makeTiming({ bpm: BPM, cues: CUES ? JSON.parse(await Deno.readTextFile(CUES)) : null });
console.log(JSON.stringify(ALL.map((x) => {
    const c = T.cueOf(x.name, x.sc);
    return { name: x.name, label: x.sc.label || '', fps: x.sc.fps || 30, lines: x.sc.lines ?? null, dur: c.dur, t0: c.t0,
        module: x.path, prewarm: typeof x.mod.prewarm === 'function' };
})));
