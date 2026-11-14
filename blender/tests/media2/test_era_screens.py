"""Probe: the fifteen computing-history era screens, baked through media's canvas path, on screens in EEVEE.

First build DAISY's timeline (the captions, kicks and voice envelopes the scenes read), from the worktree:
    python -B blender/tests/media2/run_daisy.py song --upto chorus2 --no-tts
Then, from the main checkout (a GPU job; on a shared machine queue it with EIDO_GPU_WRAP: blender/tests/_where.py):
    bash run_blender.sh <worktree>/blender/tests/media2/test_era_screens.py [-- --only wall,curved,devices,film]

wall     the nine 1939-1984 scenes (the title card included), each baked at three moments of its own line at
         DAISY's cue with DAISY's captions (bake_canvas_scene -> canvas_bake.mjs -> the module's own draw), laid end
         to end as one 27-frame sequence on a 4.8 x 2.0 m LED wall on a dark stage (make_screen(source=...), the
         spill keyed per frame) -> out/era_wall_####.png
curved   the six 2001-2023 scenes the same way on DAISY's verse-2 wall, a 104 degree arc seen from inside
         (screens.curved_wall, a 1698 x 600 canvas) -> out/era_curved_####.png
devices  desktop_2001 on desktop2001.glb's CRT, sam_1982 on c64.glb's monitor, mac_1984 on mac1984.glb's tube
film     verse 1's first two lines (voder_1939 then bell_1961, screens.bake_canvas_playlist) playing at 12 fps on
         the wall: EEVEE frames -> H.264 -> merge_av.py with the song's excerpt -> contact_sheet.py with DAISY's
         timeline -> out/era_film_av.mp4, out/era_film_contact_sheet.jpg
Finally out/era_screens_contact_sheet.png: the fifteen scenes, three moments each, as rendered on their screens.
Prints PASS/FAIL lines for what it measures.
"""
import json
import math
import shutil
import subprocess
import sys
from pathlib import Path

import bpy
import numpy as np
from PIL import Image, ImageDraw, ImageFont

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent / 'media'))
import _stage as S  # noqa: E402  (round one's stage helpers: scene, camera, lights, boxes, glTF, stills)
from eidoblend.media import canvas_scenes as cs  # noqa: E402
from eidoblend.media import screens  # noqa: E402

argv = sys.argv[sys.argv.index('--') + 1:] if '--' in sys.argv else []
ONLY = set(argv[argv.index('--only') + 1].split(',')) if '--only' in argv else {'wall', 'curved', 'devices', 'film'}
OUT = HERE / 'out'
WORK = OUT / 'era_work'
TIMELINE = OUT / 'daisy' / 'out' / 'daisy_timeline_upto_chorus2.json'
MASTER = OUT / 'daisy' / 'out' / 'daisy_master_upto_chorus2.wav'
FPS = 24
FAILS = []
FONT = HERE.parents[2] / 'eidoverse' / 'assets' / 'fonts' / 'ShareTechMono-Regular.ttf'


def check(ok, what):
    print(f"{'PASS' if ok else 'FAIL'} {what}", flush=True)
    if not ok:
        FAILS.append(what)


def magenta_fraction(png):
    a = np.asarray(Image.open(png).convert('RGB')).astype(int)
    m = (a[..., 0] > 240) & (a[..., 1] < 20) & (a[..., 2] > 240)
    return float(m.mean())


def bake_moments(names, table, W, H, n=3):
    """Each scene at n moments of its DAISY line, one still each: [(name, u, png)]."""
    lyrics = TIMELINE if TIMELINE.exists() else None
    stills = []
    for name in names:
        s, cue = table[name], cs.DAISY_CUES[name]
        for k, u in enumerate(cs.moments(s['dur'], n)):
            f = 1 + round((cue + u) * FPS)
            info = screens.bake_canvas_scene(WORK / 'stills' / name, (f, f), scene_name=name, t0=cue, W=W, H=H,
                                             lyrics=lyrics, bpm=128, prefix=f'{name}_m{k}')
            png = Path(info['first'])
            a = np.asarray(Image.open(png).convert('RGB')).astype(float)
            ok = png.exists() and Image.open(png).size == (W, H) and a.std() > 4.0
            check(ok, f'bake {name} u={(f - 1) / FPS - cue:.2f}s: {W}x{H}, {info["draw_ms_mean"]} ms a draw, '
                      f'pixel std {a.std():.1f}')
            stills.append((name, (f - 1) / FPS - cue, png))
    return stills


def lay_sequence(stills, folder, prefix):
    folder.mkdir(parents=True, exist_ok=True)
    for old in folder.glob(f'{prefix}_*.png'):
        old.unlink()
    for i, (_n, _u, png) in enumerate(stills, start=1):
        shutil.copyfile(png, folder / f'{prefix}_{i:04d}.png')
    return folder / f'{prefix}_0001.png'


def stage_floor(sc, y=-3.0):
    S.box(sc, 'floor', (14, 12, 0.04), (0, y, -0.02), S.pbr_material('stage_floor', S.cached('textures', 'Planks039_2k'),
                                                                  scale=0.45))
    stool = S.cached('models', 'wooden_stool_01_1k')
    if stool:
        for o in S.import_gltf(stool / 'wooden_stool_01_embedded.gltf'):
            if o.parent is None:
                o.location = (1.25, -1.9, 0)


def render_animation(sc, pattern, a, b):
    sc.frame_start, sc.frame_end = a, b
    r = sc.render
    r.image_settings.media_type = 'IMAGE'
    r.image_settings.file_format = 'PNG'
    r.image_settings.color_mode = 'RGB'
    r.filepath = str(pattern)
    bpy.ops.render.render(animation=True)
    files = [Path(str(pattern).replace('####', f'{f:04d}')) for f in range(a, b + 1)]
    missing = [f for f in files if not f.exists()]
    if missing:
        raise RuntimeError(f'animation render missing {len(missing)} frames, e.g. {missing[0]}')
    return files


def probe_wall(table):
    names = [s['name'] for s in table.values() if s['module'].endswith('era_screens_1939_1984.js')]
    stills = bake_moments(names, table, 1440, 600)
    first = lay_sequence(stills, WORK / 'wall_seq', 'era')
    sc = S.fresh_scene(frames=(1, len(stills)))
    stage_floor(sc)
    S.box(sc, 'drape', (14, 0.1, 6), (0, 0.6, 3), S.plain_material('drape', (0.012, 0.012, 0.014), 0.95))
    S.box(sc, 'cabinet', (4.92, 0.14, 2.12), (0, 0.09, 1.6), S.plain_material('cabinet', (0.02, 0.02, 0.022), 0.45, 0.6))
    S.box(sc, 'riser', (5.4, 1.4, 0.5), (0, -0.4, 0.25), S.plain_material('riser', (0.03, 0.03, 0.032), 0.7))
    scr = screens.make_screen(width=4.8, height=2.0, source=first, frames=(1, len(stills)), name='era_wall',
                              strength=1.25, spill=0.75)
    scr.obj.location = (0, 0.0, 1.6)
    S.area_light(sc, (0.5, -4.0, 4.5), (0, -1.6, 0.5), 45.0, size=2.0, color=(1.0, 0.86, 0.72), name='front_wash')
    S.camera(sc, (-0.9, -7.4, 1.55), (0.0, 0.0, 1.45), lens=40)
    ld = scr.light.data
    keys = sum(len(fc.keyframe_points) for fc in screens.action_fcurves(ld.animation_data.action) if fc.data_path == 'energy')
    check(scr.image.source == 'SEQUENCE' and scr.frame_duration == len(stills),
          f'wall: one {scr.image.source} image of {scr.frame_duration} frames ({len(stills)} moments)')
    check(keys >= len(names), f'wall: spill energy keyed per frame ({keys} keys)')
    files = render_animation(sc, OUT / 'era_wall_####.png', 1, len(stills))
    for (name, u, _p), f in zip(stills, files):
        mf = magenta_fraction(f)
        a = np.asarray(Image.open(f).convert('RGB')).astype(float)
        wall = a[110:400, 230:760].mean()
        check(mf == 0.0 and wall > 12.0, f'wall render {name} u={u:.2f}: no magenta, wall mean {wall:.1f}')
    return [(n, u, f) for (n, u, _p), f in zip(stills, files)]


def probe_curved(table):
    names = [s['name'] for s in table.values() if s['module'].endswith('era_screens_2001_2023.js')]
    stills = bake_moments(names, table, 1698, 600)
    first = lay_sequence(stills, WORK / 'curved_seq', 'era')
    sc = S.fresh_scene(frames=(1, len(stills)))
    stage_floor(sc, y=0.0)
    wall = screens.curved_wall('verse2_wall', radius=3.74, arc=104, height=2.4, bottom=0.35)
    wall.location = (0, 0.4, 0)
    skirt = screens.curved_wall('verse2_skirt', radius=3.74, arc=104, height=0.35, bottom=0.0)
    skirt.location = (0, 0.4, 0)
    skirt.data.materials.append(S.plain_material('skirt', (0.02, 0.02, 0.022), 0.5, 0.4))
    check(abs(wall['eido_aspect'] - 1698 / 600) < 0.01, f'curved wall aspect {wall["eido_aspect"]:.3f} '
                                                        f'(canvas {1698 / 600:.3f})')
    scr = screens.make_screen(source=first, frames=(1, len(stills)), name='era_curved', strength=1.25,
                              standalone=False, spill=0.75, width=6.79, height=2.4)
    scr.apply_to(wall, glass=False, spill=0.75)
    S.box(sc, 'drape', (14, 0.1, 6), (0, 4.6, 3), S.plain_material('drape', (0.012, 0.012, 0.014), 0.95))
    S.area_light(sc, (0.0, -3.0, 4.5), (0, -1.0, 0.5), 40.0, size=2.0, color=(1.0, 0.86, 0.72), name='front_wash')
    S.camera(sc, (0.0, -3.4, 1.55), (0.0, 3.0, 1.5), lens=30)
    files = render_animation(sc, OUT / 'era_curved_####.png', 1, len(stills))
    for (name, u, _p), f in zip(stills, files):
        a = np.asarray(Image.open(f).convert('RGB')).astype(float)
        check(magenta_fraction(f) == 0.0 and a[100:400, 100:860].mean() > 12.0,
              f'curved render {name} u={u:.2f}: no magenta, wall mean {a[100:400, 100:860].mean():.1f}')
    return [(n, u, f) for (n, u, _p), f in zip(stills, files)]


def probe_devices(table):
    """Three scenes on the machines of their eras: each GLB's own display mesh, under its glass."""
    lyrics = TIMELINE if TIMELINE.exists() else None
    out = []
    for name, glb, (W, H), window, cam, target in (
            ('desktop_2001', 'desktop2001.glb', (1024, 778), None, (0.55, -1.25, 0.72), (0.0, 0.0, 0.33)),
            ('sam_1982', 'c64.glb', (768, 576), None, (0.42, -1.05, 0.55), (0.0, 0.0, 0.26)),
            ('mac_1984', 'mac1984.glb', (1024, 684), (0.0485, 0.10696, 0.9515, 0.90104), (0.36, -0.95, 0.42),
             (0.0, -0.08, 0.17))):
        sc = S.fresh_scene(frames=(1, 1))
        S.box(sc, 'desk', (1.8, 1.0, 0.04), (0, 0.05, -0.02),
              S.pbr_material('desk_wood', S.cached('textures', 'PaintedWood009C_2k'), scale=1.6))
        S.box(sc, 'wall', (3.0, 0.05, 2.0), (0, 0.62, 0.8), S.plain_material('wall', (0.30, 0.29, 0.27), 0.85))
        objs = S.import_gltf(S.ASSETS / 'models' / 'voice_machines' / glb)
        tube = next(o for o in objs if o.name.startswith('screen_crt'))
        u = table[name]['dur'] * 0.6
        cue = cs.DAISY_CUES[name]
        f = 1 + round((cue + u) * FPS)
        info = screens.bake_canvas_scene(WORK / 'devices' / name, (f, f), scene_name=name, t0=cue, W=W, H=H,
                                         lyrics=lyrics, bpm=128)
        scr = screens.make_screen(source=info['first'], frames=(1, 1), name=f'{name}_tube', standalone=False,
                                  strength=1.6, spill=0.5, width=0.3, height=0.3 * H / W)
        scr.apply_to(tube, window=window, glass=True)
        S.area_light(sc, (-0.8, -0.7, 1.0), (0, 0, 0.2), 30.0, size=0.7, color=(1.0, 0.86, 0.70), name='lamp')
        S.area_light(sc, (1.0, -1.0, 1.5), (0, 0, 0.2), 8.0, size=1.2, color=(0.75, 0.82, 1.0), name='fill')
        S.camera(sc, cam, target, lens=40)
        png = S.render_still(sc, 1, OUT / f'era_device_{name}.png')
        a = np.asarray(Image.open(png).convert('RGB')).astype(float)
        check(magenta_fraction(png) == 0.0 and a.std() > 10, f'device {name} on {glb}: rendered, std {a.std():.1f}')
        out.append((name, u, png))
    return out


def probe_film():
    """Verse 1's first two lines on the wall at 12 fps, then the engine-agnostic tools on the result."""
    fps, t_start, seconds = 12, 24.25, 7.5
    sc = S.fresh_scene(res=(640, 360), samples=8, fps=fps, frames=(1, int(seconds * fps)))
    sc['eido_frame0'] = 1 - round(t_start * fps)               # frame 1 = t_start in the song's time
    n = int(seconds * fps)
    pl = screens.bake_canvas_playlist(WORK / 'film_seq', (1, n),
                                      {k: cs.DAISY_CUES[k] for k in ('voder_1939', 'bell_1961')},
                                      W=1440, H=600, lyrics=TIMELINE, bpm=128, prefix='verse1')
    print('[film] playlist spans', pl['spans'])
    check(len(pl['spans']) == 2 and pl['spans'][1][1] == 1 + math.ceil((27.9773 - t_start) * fps - 1e-9),
          f'film: playlist switches to bell_1961 at frame {pl["spans"][1][1]} (27.9773 s)')
    stage_floor(sc)
    S.box(sc, 'drape', (14, 0.1, 6), (0, 0.6, 3), S.plain_material('drape', (0.012, 0.012, 0.014), 0.95))
    S.box(sc, 'cabinet', (4.92, 0.14, 2.12), (0, 0.09, 1.6), S.plain_material('cabinet', (0.02, 0.02, 0.022), 0.45, 0.6))
    S.box(sc, 'riser', (5.4, 1.4, 0.5), (0, -0.4, 0.25), S.plain_material('riser', (0.03, 0.03, 0.032), 0.7))
    scr = screens.make_screen(width=4.8, height=2.0, source=pl['first'], frames=(1, n), name='verse1_wall',
                              strength=1.25, spill=0.75)
    scr.obj.location = (0, 0.0, 1.6)
    S.area_light(sc, (0.5, -4.0, 4.5), (0, -1.6, 0.5), 45.0, size=2.0, color=(1.0, 0.86, 0.72), name='front_wash')
    S.camera(sc, (-0.9, -7.4, 1.55), (0.0, 0.0, 1.45), lens=40)
    files = render_animation(sc, WORK / 'film_frames' / 'f_####.png', 1, n)
    check(len(files) == n, f'film: {n} EEVEE frames')
    root = HERE.parents[2]
    silent = OUT / 'era_film_silent.mp4'
    subprocess.run(['ffmpeg', '-v', 'error', '-y', '-framerate', str(fps), '-start_number', '1', '-i',
                    str(WORK / 'film_frames' / 'f_%04d.png'), '-c:v', 'libx264', '-pix_fmt', 'yuv420p', '-crf', '18',
                    str(silent)], check=True)
    song = WORK / 'verse1_excerpt.wav'               # frame 1 shows at the movie's 0 s and is the song's t_start
    subprocess.run(['ffmpeg', '-v', 'error', '-y', '-ss', f'{t_start:.4f}', '-t', f'{seconds:.4f}', '-i',
                    str(MASTER), str(song)], check=True)
    av = OUT / 'era_film_av.mp4'
    r = subprocess.run(['python', '-B', str(root / 'merge_av.py'), '--video', str(silent), '--audio', str(song),
                        '--out', str(av)], capture_output=True, text=True, cwd=str(root))
    print('[film] merge_av.py', r.returncode, r.stdout[-600:], r.stderr[-600:])
    check(r.returncode == 0 and av.exists(), 'film: merge_av.py muxed the EEVEE film and the song')
    # the timeline in the film's own time (frame 1 = 0 s) for the contact sheet's labels
    tl = json.loads(TIMELINE.read_text(encoding='utf-8'))
    t0 = t_start
    sh = {'sections': [{'name': s['name'], 't0': s['t0'] - t0, 't1': s['t1'] - t0} for s in tl['sections']
                       if s['t1'] > t0],
          'captions': [{'text': c['text'], 't0': c['t0'] - t0, 't1': c['t1'] - t0} for c in tl['captions']
                       if c['t1'] > t0 and c['t0'] < t0 + seconds]}
    (WORK / 'film_timeline.json').write_text(json.dumps(sh), encoding='utf-8')
    r = subprocess.run(['python', '-B', str(root / 'contact_sheet.py'), str(av), '--every', '1', '--cols', '4',
                        '--tile', '480', '--timeline', str(WORK / 'film_timeline.json'), '--title',
                        'DAISY verse 1 on the EEVEE wall', '--out', str(OUT / 'era_film_contact_sheet')],
                       capture_output=True, text=True, cwd=str(root))
    print('[film] contact_sheet.py', r.returncode, r.stdout[-600:], r.stderr[-600:])
    check(r.returncode == 0 and (OUT / 'era_film_contact_sheet.jpg').exists(),
          'film: contact_sheet.py made a labelled sheet of the EEVEE film')


def sheet(rows, path, title):
    """The renders as a labelled grid: one row per scene, its moments across."""
    by = {}
    for name, u, f in rows:
        by.setdefault(name, []).append((u, f))
    tw, th, pad, lab = 320, 180, 8, 22
    cols = max(len(v) for v in by.values())
    W = pad + cols * (tw + pad) + 200
    H = 40 + len(by) * (th + pad) + pad
    im = Image.new('RGB', (W, H), (18, 18, 22))
    d = ImageDraw.Draw(im)
    fnt, big = ImageFont.truetype(str(FONT), 15), ImageFont.truetype(str(FONT), 20)
    d.text((pad, 10), title, font=big, fill=(232, 228, 216))
    for r, (name, v) in enumerate(by.items()):
        y = 40 + r * (th + pad)
        d.text((pad, y + th // 2 - 8), name, font=fnt, fill=(232, 228, 216))
        for c, (u, f) in enumerate(v):
            x = 200 + c * (tw + pad)
            im.paste(Image.open(f).convert('RGB').resize((tw, th), Image.LANCZOS), (x, y))
            d.rectangle([x, y, x + 74, y + lab], fill=(0, 0, 0))
            d.text((x + 4, y + 3), f'u {u:5.2f}', font=fnt, fill=(232, 228, 216))
    im.save(path)
    print(f'[sheet] {path}')
    return path


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    check(TIMELINE.exists(), f'DAISY timeline present ({TIMELINE.name}; run run_daisy.py song first)')
    table = {s['name']: s for s in cs.list_scenes()}
    check(len(table) == 15, f'{len(table)} scenes listed across the two era modules')
    rows = []
    if 'wall' in ONLY:
        w = probe_wall(table)
        sheet(w, OUT / 'era_wall_sheet.png', 'era screens 1939-1984 on the LED wall (EEVEE, AgX)')
        rows += w
    if 'curved' in ONLY:
        c = probe_curved(table)
        sheet(c, OUT / 'era_curved_sheet.png', 'era screens 2001-2023 on the curved verse-2 wall (EEVEE, AgX)')
        rows += c
    if 'devices' in ONLY:
        probe_devices(table)
    if rows and {'wall', 'curved'} <= ONLY:
        sheet(rows, OUT / 'era_screens_contact_sheet.png',
              'the fifteen era screens on screens in EEVEE: three moments of each scene at DAISY\'s cues')
    if 'film' in ONLY:
        probe_film()
    shutil.rmtree(WORK / 'film_frames', ignore_errors=True)
    print(f'[test_era_screens] {"ALL OK" if not FAILS else f"{len(FAILS)} FAILED"}', flush=True)


main()
