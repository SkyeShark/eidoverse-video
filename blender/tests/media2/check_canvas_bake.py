"""API check (no render, no GPU slot): bake_canvas_scene's options, through js/canvas_bake.mjs. From the main checkout:

    bash run_blender.sh <worktree>/blender/tests/media2/check_canvas_bake.py

At 480 x 200, a 24 fps scene, frames 1..24 (one second):
- the art's own redraw rate holds frames: sam_1982 (25 fps) is drawn on 24 of 24 film frames, art_fps=12 on 12,
  art_fps=0 on every frame; a draw module's own `fps = 6` on 6
- prewarm (True, and 4 draws a second) changes no pixel: the caches it builds are the ones playback builds
- cues: DAISY_CUES without t0 bakes the same frames as the explicit t0
- the film's frame0 reaches the bake (scene['eido_frame0'])
- draw_module: a module exporting setup({W, H, createCanvas}), fps and draw(g, W, H, t) bakes unchanged
- bake_canvas_playlist with cues in both forms ({scene: t0} and {scene: {t0, dur}}): the dur reaches the bake
- a sprite atlas played once at 1.5x (make_atlas_screen), when test_overlay_routes.py has made the atlas
Prints PASS/FAIL lines and '[check_canvas_bake] ALL OK'.
"""
import hashlib
import shutil
import sys
from pathlib import Path

import bpy

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parents[1]))
from eidoblend.media import canvas_scenes as cs  # noqa: E402
from eidoblend.media import screens  # noqa: E402

WORK = HERE / 'out' / 'canvas_bake_work'
TIMELINE = HERE / 'out' / 'daisy' / 'out' / 'daisy_timeline_upto_chorus2.json'
FAILS = []
PANEL = r'''
// a draw module as a WebGPU scene's makeScreen callback would be, moved into a file
export const fps = 6;
let grad = null;
export async function setup({ W, H, createCanvas }) {
    const c = createCanvas(W, H), g = c.getContext('2d');
    const lg = g.createLinearGradient(0, 0, W, 0);
    lg.addColorStop(0, '#071b22'); lg.addColorStop(1, '#27e0a0');
    grad = lg;
}
export function draw(g, W, H, t) {
    g.fillStyle = grad || '#071b22';
    g.fillRect(0, 0, W, H);
    g.fillStyle = '#ffffff';
    g.font = `${Math.round(H * 0.3)}px "Share Tech Mono", monospace`;
    g.fillText(`t = ${t.toFixed(2)}`, W * 0.08, H * 0.6);
}
'''


def check(ok, what):
    print(f"{'PASS' if ok else 'FAIL'} {what}", flush=True)
    if not ok:
        FAILS.append(what)


def digests(info):
    d = Path(info['dir'])
    return [hashlib.md5((d / f"{Path(info['first']).stem[:-4]}{k:04d}.png").read_bytes()).hexdigest()
            for k in range(1, info['count'] + 1)]


def main():
    if WORK.exists():
        shutil.rmtree(WORK)
    sc = bpy.context.scene
    sc.render.fps, sc.render.fps_base = 24, 1.0
    sc.frame_start, sc.frame_end = 1, 24
    small = dict(W=480, H=200, lyrics=TIMELINE, bpm=128)
    cue = cs.DAISY_CUES['sam_1982']
    sc['eido_frame0'] = 1 - round(cue * 24)                     # frame 1 = the scene's own start
    a = screens.bake_canvas_scene(WORK / 'sam', (1, 24), scene_name='sam_1982', t0=cue, **small)
    check(a['drawn'] == 24 and a['art_fps'] == 25, f"sam_1982 at its own 25 fps: drawn on {a['drawn']} of 24 frames")
    check(a['frame0'] == sc['eido_frame0'], f"the film's frame0 reaches the bake ({a['frame0']})")
    b = screens.bake_canvas_scene(WORK / 'sam12', (1, 24), scene_name='sam_1982', t0=cue, art_fps=12, **small)
    hb = digests(b)
    # art frames sit on the film's own clock (floor(t x 12)), as the engine's screen tick throttled on its time
    arts = [int((f - sc['eido_frame0']) / 24 * 12 + 1e-6) for f in range(1, 25)]
    same = all(hb[i] == hb[j] for i in range(24) for j in range(24) if arts[i] == arts[j])   # a held frame: a copy
    check(b['drawn'] == len(set(arts)) and same,
          f"art_fps=12: drawn on {b['drawn']} frames (the film clock's {len(set(arts))} art frames over these 24), "
          f"each held while its art frame lasts")
    c = screens.bake_canvas_scene(WORK / 'sam0', (1, 24), scene_name='sam_1982', t0=cue, art_fps=0, **small)
    check(c['drawn'] == 24, f"art_fps=0: drawn on every frame ({c['drawn']})")
    for pw in (True, 4):
        p = screens.bake_canvas_scene(WORK / f'sam_pw{pw}', (1, 24), scene_name='sam_1982', t0=cue, prewarm=pw,
                                      **small)
        check(digests(p) == digests(a), f'prewarm={pw}: the same 24 frames, byte for byte')
    k = screens.bake_canvas_scene(WORK / 'sam_cues', (1, 24), scene_name='sam_1982', cues=cs.DAISY_CUES, **small)
    check(digests(k) == digests(a), 'cues=DAISY_CUES (no t0): the same frames as t0 = its cue')
    panel = WORK / 'panel.mjs'
    panel.write_text(PANEL, encoding='utf-8')
    sc['eido_frame0'] = 1
    d = screens.bake_canvas_scene(WORK / 'panel', (1, 24), draw_module=panel, W=480, H=200)
    hd = digests(d)
    check(d['drawn'] == 6 and d['art_fps'] == 6 and len(set(hd)) == 6,
          f"draw_module with setup() and fps = 6: drawn on {d['drawn']} frames, {len(set(hd))} distinct")

    # playlist cues in both forms, {scene: t0} and {scene: {t0, dur}}: the dur reaches the scene's bake
    t_bell = cs.DAISY_CUES['bell_1961']
    sc.frame_start, sc.frame_end = 1, 36
    sc['eido_frame0'] = 1 - round(27.0 * 24)                    # frame 1 = 27.0 s: bell_1961 cues in at frame 25
    mixed = {'voder_1939': cs.DAISY_CUES['voder_1939'], 'bell_1961': {'t0': t_bell, 'dur': 4.0}}
    pl = screens.bake_canvas_playlist(WORK / 'playlist_dur', (1, 36), mixed, prefix='pl', W=480, H=200,
                                      lyrics=TIMELINE, bpm=128)
    one = screens.bake_canvas_scene(WORK / 'bell_dur', (25, 36), scene_name='bell_1961', cues={'bell_1961':
                                    mixed['bell_1961']}, **small)
    hp = digests(pl)
    check([s[0] for s in pl['spans']] == ['voder_1939', 'bell_1961'] and pl['spans'][1][1] == 25
          and hp[24:] == digests(one),
          f"bake_canvas_playlist with a {{t0, dur}} cue: spans {pl['spans']}; bell_1961's frames equal "
          f"bake_canvas_scene(cues={{'bell_1961': {{t0, dur: 4}}}})")
    tl = screens.bake_canvas_scene(WORK / 'bell_dur_t0', (25, 36), scene_name='bell_1961', t0=t_bell,
                                   cues={'bell_1961': {'t0': 0.0, 'dur': 4.0}}, **small)
    check(digests(tl) == digests(one), 'an explicit t0 over a {t0, dur} cue keeps the cue\'s dur')

    # a sprite atlas played once at 1.5x from frame 10 (test_overlay_routes.py's video_to_sprite.mjs atlas)
    jpg = HERE / 'out' / 'overlay_work' / 'atlas' / 'era_film_sprite.jpg'
    if jpg.exists():
        import numpy as np
        info = screens.read_atlas_info(jpg.with_name('era_film_sprite_info.json'))
        sc.frame_start, sc.frame_end = 1, 72
        scr = screens.make_atlas_screen(jpg, info, width=0.4, start_frame=10, speed=1.5, loop=False,
                                        out_dir=WORK / 'atlas_once', name='atlas_once')
        tiles = [np.asarray(screens.atlas_tile(jpg, info, i).convert('RGB')).astype(float)
                 for i in range(info['totalFrames'])]
        got, want = [], []
        for f in (10, 11, 40, 72):
            a = np.asarray(screens.raster.Image.open(WORK / 'atlas_once' / f'atlas_once_{f - 9:04d}.png')
                           .convert('RGB')).astype(float)
            got.append(int(np.argmin([np.abs(a - t).mean() for t in tiles])))
            want.append(screens.engine_movie_frame(f - 10, 24, info['fps'], 1.5, info['totalFrames'], False))
        check(got == want and scr.frame_start == 10,
              f'atlas once at 1.5x from frame 10: frames 10/11/40/72 show tiles {got} (screen.js rule {want}); the '
              f'sequence covers frames 10..72, {scr.frame_duration} frames, the scene\'s end cutting it at tile '
              f'{want[-1]} of {info["totalFrames"]}')
    else:
        print('[check_canvas_bake] (no atlas yet: run test_overlay_routes.py --only atlas for the atlas check)')
    print(f'[check_canvas_bake] {"ALL OK" if not FAILS else f"{len(FAILS)} FAILED"}', flush=True)


main()
