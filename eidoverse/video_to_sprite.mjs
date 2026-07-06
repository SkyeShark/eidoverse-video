// video_to_sprite.mjs — convert a video file to a sprite atlas for use as an
// animated texture in three.js. Drop-in replacement for the Pillow-based
// video_to_sprite.py — uses ffmpeg's `tile` filter instead of Pillow paste.
//
// USAGE
//   node /opt/render3d/video_to_sprite.mjs input.mp4 \
//     [--fps 12] [--width 256] [--height 144] [--max-frames 120] \
//     [--output video_sprite]
//
// OUTPUTS
//   {output}.jpg          — the atlas image (one big tiled JPEG)
//   {output}_info.json    — { cols, rows, totalFrames, fps,
//                             frameWidth, frameHeight,
//                             atlasWidth, atlasHeight }
//
// HOW TO USE IN a scene — makeVideoScreen owns the material recipe (sRGB,
// unlit, toneMapped:false) AND the per-frame UV stepping (self-updating):
//   // config.assets: { "videoSprite": "video_sprite.jpg",
//   //                  "videoInfo":   "video_sprite_info.json" }
//
//   // In setup():
//   const info = JSON.parse(new TextDecoder().decode(
//       b64toArrayBuffer(window.ASSETS.videoInfo)));
//   const spriteTex = await globalThis.loadImageTexture(window.ASSETS.videoSprite);
//   const tv = globalThis.makeVideoScreen({ texture: spriteTex, info, width: 1.6 });
//   scene.add(tv.mesh);   // position over the TV/monitor's screen face
//   // no per-frame work — never hand-roll the UV offset math or a raw material

import { spawnSync } from 'child_process';
import { writeFileSync, mkdtempSync, readdirSync, rmSync } from 'fs';
import { parseArgs } from 'util';
import { tmpdir } from 'os';
import { join } from 'path';

function printHelp() {
    console.log([
        '──────── video_to_sprite.mjs ────────',
        '',
        'Convert a video to a sprite atlas for use as an animated texture in three.js.',
        'Drop-in replacement for the deprecated video_to_sprite.py.',
        '',
        'Usage:',
        '  node /opt/render3d/video_to_sprite.mjs <input.mp4> [options]',
        '',
        'Options:',
        '  --fps N           sprite atlas frames per second              (default 12)',
        '  --width N         per-frame pixel width                        (default 256)',
        '  --height N        per-frame pixel height                       (default 144)',
        '  --max-frames N    cap on total frames extracted                (default 120)',
        '  --output PREFIX   output file prefix                           (default video_sprite)',
        '  --quality N       ffmpeg JPEG -q:v scale (2 best, 5 worst)     (default 3)',
        '  --help            print this help',
        '',
        'Outputs:',
        '  {prefix}.jpg          atlas image (one big tiled JPEG)',
        '  {prefix}_info.json    {cols, rows, totalFrames, fps,',
        '                         frameWidth, frameHeight, atlasWidth, atlasHeight}',
        '',
        'Sizing trade-offs:',
        '  • Atlas dimensions = ceil(sqrt(N)) * frameWidth × ceil(sqrt(N)) * frameHeight',
        '  • Keep atlas ≤ 8192 px per side (WebGL desktop max). For long videos,',
        '    EITHER lower --fps (12 → 6 halves frames) OR shrink --width/--height.',
        '  • 73s @ 8fps @ 320x240 → 25x24 grid → 8000x5760 (just fits).',
        '  • 73s @ 12fps @ 256x144 → 30x30 grid → 7680x4320 (default-ish).',
        '',
        'Three.js usage:',
        '  // config.assets: { videoSprite: "x.jpg", videoInfo: "x_info.json" }',
        '  const info = JSON.parse(new TextDecoder().decode(b64toArrayBuffer(window.ASSETS.videoInfo)));',
        '  const tex  = await new THREE.TextureLoader().loadAsync(URL.createObjectURL(',
        '      new Blob([new Uint8Array(b64toArrayBuffer(window.ASSETS.videoSprite))], {type:"image/jpeg"})));',
        '  tex.repeat.set(1/info.cols, 1/info.rows);',
        '  // In renderFrame(t):',
        '  const f = Math.floor(t * info.fps) % info.totalFrames;',
        '  tex.offset.set((f % info.cols) / info.cols,',
        '                  1 - (Math.floor(f / info.cols) + 1) / info.rows);',
    ].join('\n'));
}

function parse() {
    const { values, positionals } = parseArgs({
        options: {
            fps: { type: 'string', default: '12' },
            width: { type: 'string', default: '256' },
            height: { type: 'string', default: '144' },
            'max-frames': { type: 'string', default: '120' },
            output: { type: 'string', default: 'video_sprite' },
            quality: { type: 'string', default: '3' },
            help: { type: 'boolean', default: false },
        },
        allowPositionals: true,
    });
    if (values.help || positionals.length < 1) {
        printHelp();
        process.exit(values.help ? 0 : 1);
    }
    return {
        input: positionals[0],
        fps:    parseInt(values.fps,         10),
        width:  parseInt(values.width,       10),
        height: parseInt(values.height,      10),
        maxFrames: parseInt(values['max-frames'], 10),
        output:  values.output,
        quality: parseInt(values.quality,    10),
    };
}

function runFF(args, label) {
    const r = spawnSync('ffmpeg', ['-hide_banner', '-loglevel', 'error', ...args],
        { stdio: 'inherit' });
    if (r.status !== 0) {
        console.error(`[video_to_sprite] ffmpeg ${label} failed`);
        process.exit(1);
    }
}

const opts = parse();

// ── Pass 1: extract frames to a temp dir. Same shape as the Pillow version
// (fps + scale filters, capped with -frames:v) so downstream behaviour is
// identical — no resolution / fps differences between old and new tools.
const tmp = mkdtempSync(join(tmpdir(), 'sprite_frames_'));
try {
    runFF([
        '-y', '-i', opts.input,
        '-vf', `fps=${opts.fps},scale=${opts.width}:${opts.height}`,
        '-frames:v', String(opts.maxFrames),
        `${tmp}/frame_%04d.jpg`,
    ], 'extract');

    const frames = readdirSync(tmp)
        .filter(f => /^frame_\d+\.jpg$/.test(f))
        .sort();
    const n = frames.length;
    if (n === 0) {
        console.error('[video_to_sprite] no frames extracted');
        process.exit(1);
    }
    console.log(`Extracted ${n} frames at ${opts.fps}fps, ${opts.width}x${opts.height}`);

    // Roughly-square grid, same formula as the Python version
    const cols = Math.ceil(Math.sqrt(n));
    const rows = Math.ceil(n / cols);
    const atlasW = cols * opts.width;
    const atlasH = rows * opts.height;
    console.log(`Sprite atlas: ${cols}x${rows} grid = ${atlasW}x${atlasH} pixels`);

    // ── Pass 2: tile the extracted frames into a single atlas image.
    // ffmpeg's `tile=CxR` filter buffers input frames and emits one tiled
    // output per full grid — with `-frames:v 1` we grab exactly one atlas.
    // `-framerate 1 -start_number 1` matches ffmpeg's image-sequence defaults.
    const atlasPath = `${opts.output}.jpg`;
    runFF([
        '-y',
        '-framerate', '1',
        '-start_number', '1',
        '-i', `${tmp}/frame_%04d.jpg`,
        '-vf', `tile=${cols}x${rows}`,
        '-frames:v', '1',
        '-q:v', String(opts.quality),
        atlasPath,
    ], 'tile');

    const info = {
        cols, rows,
        totalFrames: n,
        fps: opts.fps,
        frameWidth:  opts.width,
        frameHeight: opts.height,
        atlasWidth:  atlasW,
        atlasHeight: atlasH,
    };
    writeFileSync(`${opts.output}_info.json`, JSON.stringify(info, null, 2));
    console.log(`Saved: ${atlasPath} + ${opts.output}_info.json`);
} finally {
    try { rmSync(tmp, { recursive: true, force: true }); } catch {}
}
