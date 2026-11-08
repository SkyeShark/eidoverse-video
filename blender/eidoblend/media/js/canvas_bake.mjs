// canvas_bake.mjs — bake a canvas-2D screen scene to a PNG sequence, one file per Blender frame, for the Blender
// edition's screens (blender/eidoblend/media/screens.py: bake_canvas_scene, make_screen(source=...)).
// Guide: tools-guides/motion-graphics.md ("Computing-history screen scenes"). Deno + @napi-rs/canvas (Skia), the same
// drawing code the WebGPU engine runs, so the art is the reviewed art, frame for frame.
//
//   deno run -A --no-config --node-modules-dir=none blender/eidoblend/media/js/canvas_bake.mjs \
//       --module eidoverse/graphics/era_screens_1939_1984.js --scene voder_1939 --t0 12 \
//       --fps 24 --frame0 1 --frames 280-376 --W 1920 --H 800 --out work/<id>/screens/voder [--lyrics <json>] [--bpm 128]
//   deno run ... canvas_bake.mjs --draw work/<id>/my_panel.mjs --fps 24 --frames 1-96 --W 768 --H 432 --out <dir>
//
// --module (repeatable) + --scene: a scene of the era-screen modules (any module exporting `scenes`), timed by
//     preview_screens.mjs's makeTiming: --t0 (or --cues <json>) is the scene's film start, --lyrics captions /
//     kicks / voice envelopes as preview_screens takes them, --bpm the song's tempo.
// --draw <module>: any module exporting draw(g, W, H, t[, st]) and optionally `async setup({ W, H, createCanvas })`
//     and `fps` (a WebGPU scene's makeScreen draw callback, moved into a file, bakes unchanged).
// Time: t = (frame - frame0) / fps (the film convention: frame 1 = 0 s). The art's own redraw rate (the scene's
//     `fps`, or --art-fps; 0 = every frame) holds frames, as the engine's screen tick did: the art is drawn at the
//     first film frame of each of its frames, and a held frame re-writes the previous PNG's bytes.
// Output: <out>/<prefix>_0001.png … for frames a…b (file k = frame a + k - 1), and <out>/<prefix>_bake.json.
// Non-finite numbers reaching a canvas call make Skia abort the process with no JS error; this bake makes them
// throw with a stack instead (the guard screens_nan_sweep.mjs uses).
import { createCanvas } from 'npm:@napi-rs/canvas@0.1.69';

const args = [...Deno.args];
const opts = {}, multi = { module: [] };
for (let i = 0; i < args.length; i++) {
    const a = args[i];
    if (!a.startsWith('--')) continue;
    const k = a.slice(2), v = args[i + 1];
    if (k in multi) { multi[k].push(v); i++; } else if (v === undefined || v.startsWith('--')) { opts[k] = true; } else { opts[k] = v; i++; }
}
const num = (k, d) => (opts[k] === undefined ? d : +opts[k]);
const W = num('W', 1920), H = num('H', 800), FPS = num('fps', 24), FRAME0 = num('frame0', 1);
const [FA, FB] = String(opts.frames || '1-1').split('-').map(Number);
const OUT = opts.out, PREFIX = opts.prefix || (opts.scene || 'canvas');
if (!OUT || !Number.isFinite(FA) || !Number.isFinite(FB) || FB < FA) {
    console.error('usage: canvas_bake.mjs (--module <js> … --scene <name> | --draw <mjs>) --frames a-b --out <dir> [--fps 24 --frame0 1 --W --H]');
    Deno.exit(2);
}

// a path -> an importable URL (relative paths resolve from the working directory)
function toUrl(p) {
    if (/^(file|https?):/i.test(p)) return p;
    let abs = String(p).replaceAll('\\', '/');
    if (!/^([A-Za-z]:)?\//.test(abs)) abs = Deno.cwd().replaceAll('\\', '/') + '/' + abs;
    return new URL('file://' + (abs.startsWith('/') ? '' : '/') + encodeURI(abs)).href;
}

// guard every numeric 2D-context entry point (screens_nan_sweep.mjs's list)
{
    const proto = Object.getPrototypeOf(createCanvas(1, 1).getContext('2d'));
    for (const m of ['arc', 'arcTo', 'moveTo', 'lineTo', 'bezierCurveTo', 'quadraticCurveTo', 'rect', 'roundRect', 'ellipse',
        'fillRect', 'strokeRect', 'clearRect', 'drawImage', 'fillText', 'strokeText', 'createLinearGradient',
        'createRadialGradient', 'translate', 'scale', 'rotate', 'setTransform', 'transform', 'getImageData', 'putImageData',
        'createImageData']) {
        const orig = proto[m];
        if (typeof orig !== 'function') continue;
        proto[m] = function (...a) {
            for (let i = 0; i < a.length; i++) {
                const v = a[i];
                if (typeof v === 'number' && !Number.isFinite(v)) throw new Error(`non-finite arg ${i} to ${m}(${a.map(String).join(', ')})`);
            }
            return orig.apply(this, a);
        };
    }
}

let draw, artFps, label;
if (opts.draw) {
    const mod = await import(toUrl(opts.draw));
    if (typeof mod.draw !== 'function') { console.error(`${opts.draw} exports no draw(g, W, H, t)`); Deno.exit(2); }
    if (typeof mod.setup === 'function') await mod.setup({ W, H, createCanvas });
    draw = (g, t) => mod.draw(g, W, H, t, null);
    artFps = num('art-fps', mod.fps || 0);
    label = opts.draw;
} else {
    if (!multi.module.length || !opts.scene) { console.error('--module <js> and --scene <name> (or --draw <mjs>)'); Deno.exit(2); }
    const P = await import(new URL('../../../../eidoverse/graphics/preview_screens.mjs', import.meta.url).href);
    const ALL = await P.loadScenes(multi.module, num('bpm', 128));
    const x = ALL.find((s) => s.name === opts.scene);
    if (!x) { console.error(`unknown scene ${opts.scene}; have: ${ALL.map((s) => s.name).join(', ')}`); Deno.exit(2); }
    const T = P.makeTiming({
        bpm: num('bpm', 128), at: num('t0', 0),
        cues: opts.cues ? JSON.parse(await Deno.readTextFile(opts.cues)) : null,
        lyrics: opts.lyrics ? await P.loadLyrics(opts.lyrics) : null,
    });
    if (opts.prewarm && x.mod.prewarm) {          // --prewarm [perSecond]: era_screens_1939_1984's sampling rate (12)
        const per = opts.prewarm === true ? undefined : +opts.prewarm;
        x.mod.prewarm(W, H, (name) => { const y = ALL.find((s) => s.name === name); const c = T.cueOf(name, y.sc); return { t0: c.t0, dur: c.dur, st: (t) => T.stAt(name, y.sc, t) }; }, per);
    }
    draw = (g, t) => x.sc.draw(g, W, H, t, T.stAt(x.name, x.sc, t));
    artFps = num('art-fps', x.sc.fps || 0);
    label = `${x.name} (${x.sc.label || ''})`;
}

await Deno.mkdir(OUT, { recursive: true });
const canvas = createCanvas(W, H), g = canvas.getContext('2d');
const pad = (n) => String(n).padStart(4, '0');
let lastArt = null, lastBuf = null, drawn = 0, ms = 0;
for (let f = FA; f <= FB; f++) {
    const t = (f - FRAME0) / FPS;
    const art = artFps > 0 ? Math.floor(t * artFps + 1e-6) : f;
    if (art !== lastArt || !lastBuf) {
        const a = performance.now();
        draw(g, t);                                        // as the engine's screen tick: drawn when the art's frame changes
        ms += performance.now() - a;
        lastBuf = canvas.toBuffer('image/png');
        lastArt = art;
        drawn++;
    }
    const file = `${OUT}/${PREFIX}_${pad(f - FA + 1)}.png`;
    await Deno.writeFile(file + '.part', lastBuf);
    await Deno.rename(file + '.part', file);
}
const info = { source: label, first_frame: FA, last_frame: FB, count: FB - FA + 1, fps: FPS, frame0: FRAME0, W, H,
    art_fps: artFps, drawn, draw_ms_mean: drawn ? +(ms / drawn).toFixed(2) : 0, pattern: `${PREFIX}_####.png` };
await Deno.writeTextFile(`${OUT}/${PREFIX}_bake.json`, JSON.stringify(info, null, 1));
console.log(JSON.stringify(info));
