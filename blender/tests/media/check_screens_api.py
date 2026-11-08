"""API check (no render, no GPU slot needed): the screens' frame bookkeeping, measured.

    cd <main checkout> && bash run_blender.sh <worktree>/blender/tests/media/check_screens_api.py

hold      make_screen(frames=(10, 20)) writes <name>_0000.png, a marked copy of file 1: Blender shows file
          <first - 1> on every frame before a sequence starts (it was the missing-texture magenta, 11-07 verify)
source    a sequence picked up at its file 5: ImageUser offset 4, files from 5 on, the real file 4 left alone
names     two screens on the defaults get their own names, folders and pixels; the default folder outlives
          Blender (not bpy.app.tempdir); with a saved blend it is //eido_screens/<blend>/<name>
retime    make_video_screen against screen.js's rule floor(k / film fps * fps * speed), wrapped or clamped: bit-coded
          counter movies at 24, 25 and 30 fps, speeds 0.5, 1 and 1.5, looping and not, started at frame 10 of a
          1..72 film; every film frame's file is found the way Blender finds it and decoded
overlay   ov.panel(frames=(10, 20)) is keyed hidden outside its range
spill     the spill light's power and colour for a saturated frame: colour m / max(m), power pi A S max(m) gain
Prints one line per check and '[check_screens_api] ALL OK' when every check passed.
"""
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

import bpy
import numpy as np
from PIL import Image

sys.path.insert(0, str(Path(__file__).resolve().parent))
import _stage as S  # noqa: E402
from eidoblend.media import overlay, raster, screens  # noqa: E402

W = S.OUT / 'screens_api_work'
if W.exists():
    shutil.rmtree(W)
W.mkdir(parents=True)
fails = []


def check(name, ok, detail=''):
    print(f'[check] {"OK  " if ok else "FAIL"} {name}{": " + detail if detail else ""}', flush=True)
    if not ok:
        fails.append(name)


def blender_file(cfra, image):
    """The file number Blender reads for scene frame cfra (BKE_image_user_frame_get, non-cyclic)."""
    c = cfra - int(image['eido_frame_start']) + 1
    c = min(max(c, 0), int(image['eido_frame_duration']))
    return c + int(image['eido_frame_offset'])


def file_for(image, num):
    p = Path(bpy.path.abspath(image.filepath))
    head, _, nd = screens._seq_split(p)
    return p.with_name(f'{head}{num:0{nd}d}{p.suffix}')


# ---------------------------------------------------------------------------------------------------- hold
sc = S.fresh_scene(frames=(1, 30))


def stamp(c, t, w, h):
    f = round(t * 24) + 1
    c.clear((f * 8 % 256, 40, 200))          # red channel encodes the frame
a = screens.make_screen(px=64, width=0.64, height=0.36, draw=stamp, frames=(10, 20), out_dir=W / 'hold',
                        name='late')
hold = W / 'hold' / 'late_0000.png'
first = W / 'hold' / 'late_0001.png'
same = np.array_equal(np.asarray(Image.open(hold)), np.asarray(Image.open(first))) if hold.exists() else False
check('hold file written and marked', hold.exists() and screens._is_hold(hold) and same,
      f'{hold.name} exists {hold.exists()}, marked {screens._is_hold(hold)}, pixels equal to file 1 {same}')
seen = {f: Image.open(file_for(a.image, blender_file(f, a.image))).getpixel((2, 2))[0] for f in (5, 9, 10, 15, 20, 25)}
want = {5: 80, 9: 80, 10: 80, 15: 120, 20: 160, 25: 160}
check('frames before / in / after the range read the first / own / last drawing', seen == want,
      f'red per frame {seen} (want {want})')
fd, files = screens._first_of(W / 'hold')
check('a directory source starts at file 1, not the hold', fd.name == 'late_0001.png' and len(files) == 11,
      f'first {fd.name}, {len(files)} files')
sc.sequence_editor_create()
strip = overlay._strip_from(sc.sequence_editor.strips, 'seq', W / 'hold', 1, 1)
check('an edit-scene image strip from that folder skips the hold', len(strip.elements) == 11 and
      strip.elements[0].filename == 'late_0001.png', f'{len(strip.elements)} elements from {strip.elements[0].filename}')
sc.sequence_editor_clear()

# ---------------------------------------------------------------------------------------------------- source at 5
src = W / 'src'
src.mkdir()
for k in range(1, 31):
    Image.new('RGB', (32, 18), (k * 8, 0, 0)).save(src / f'f_{k:04d}.png')
b = screens.make_screen(width=0.64, height=0.36, source=src / 'f_0005.png', frames=(10, 19), name='from5', spill=1.0)
img = b.image
check('a sequence picked up at file 5 shows file 5 at its start', img['eido_frame_offset'] == 4 and
      blender_file(10, img) == 5 and blender_file(19, img) == 14 and blender_file(3, img) == 4,
      f'offset {img["eido_frame_offset"]}, frame 10 -> file {blender_file(10, img)}, 19 -> {blender_file(19, img)},'
      f' 3 -> {blender_file(3, img)}')
r4 = Image.open(src / 'f_0004.png').getpixel((0, 0))[0]
check('the source\'s own file 4 is left alone (it is a real frame)', r4 == 32 and not screens._is_hold(src / 'f_0004.png'),
      f'f_0004 red {r4}')
check('spill means come from files 5.. (not 1..)', len(b.means) == 10 and abs(
    b.means[0][0] - raster.srgb_to_linear(np.array([40 / 255]))[0]) < 1e-4, f'{len(b.means)} means, first red '
    f'{b.means[0][0]:.5f}')

# ---------------------------------------------------------------------------------------------------- names, dirs
red = screens.make_screen(draw=lambda c, t, w, h: c.clear('#ff0000'), frames=(1, 3))
blue = screens.make_screen(draw=lambda c, t, w, h: c.clear('#0000ff'), frames=(1, 3))
pr, pb = (Path(bpy.path.abspath(s.image.filepath)) for s in (red, blue))
px = Image.open(pr).convert('RGB').getpixel((5, 5)), Image.open(pb).convert('RGB').getpixel((5, 5))
tmp_session = Path(bpy.app.tempdir).resolve() if bpy.app.tempdir else None
check('two default screens keep their own names, folders and frames',
      red.name != blue.name and pr.parent != pb.parent and px == ((255, 0, 0), (0, 0, 255)),
      f'{red.name} -> {pr.parent.name}/{pr.name} {px[0]}, {blue.name} -> {pb.parent.name}/{pb.name} {px[1]}')
check('the default folder outlives Blender (not its session temp)',
      tmp_session is None or tmp_session not in pr.resolve().parents, f'{pr.parent} (session temp {tmp_session})')
for p in (pr, pb):
    shutil.rmtree(p.parent, ignore_errors=True)              # the system-temp folders this check made
bpy.ops.wm.save_as_mainfile(filepath=str(W / 'api_film.blend'))
c3 = screens.make_screen(draw=lambda c, t, w, h: c.clear('#00ff00'), frames=(1, 3), name='after_save')
want_dir = (W / 'eido_screens' / 'api_film' / 'after_save').resolve()
got = Path(bpy.path.abspath(c3.image.filepath)).resolve().parent
check('with a saved blend the default folder is //eido_screens/<blend>/<name>, stored blend-relative',
      got == want_dir and c3.image.filepath.startswith('//'), f'{c3.image.filepath}')

# ---------------------------------------------------------------------------------------------------- retime
N, BITS, B = 72, 7, 40


def code(k):
    im = np.full((80, BITS * B), 40, np.uint8)
    for bit in range(BITS):
        if (k >> bit) & 1:
            im[20:60, bit * B + 4:(bit + 1) * B - 4] = 230
    return im


def decode(path):
    g = np.asarray(Image.open(path).convert('L'), dtype=np.float64)
    return sum(1 << bit for bit in range(BITS) if g[30:50, bit * B + 12:(bit + 1) * B - 12].mean() > 135)


cdir = W / 'code'
cdir.mkdir()
for k in range(N):
    Image.fromarray(code(k)).save(cdir / f'c_{k + 1:04d}.png')
sc = S.fresh_scene(frames=(1, 72))
bad_total = 0
for fps in (24, 25, 30):
    mp4 = W / f'code_{fps}.mp4'
    subprocess.run(['ffmpeg', '-v', 'error', '-y', '-framerate', str(fps), '-start_number', '1', '-i',
                    str(cdir / 'c_%04d.png'), '-c:v', 'libx264', '-pix_fmt', 'yuv420p', '-crf', '10', str(mp4)],
                   check=True)
    for speed in (0.5, 1.0, 1.5):
        if fps == 24 and speed == 1.0:                      # the native MOVIE path (rendered in test_screens)
            v = screens.make_video_screen(mp4, width=0.5, start_frame=10, loop=True, name='native24',
                                          standalone=False)
            check('a native movie loops on its counted frames', v.image.source == 'MOVIE' and
                  v.image['eido_frame_duration'] == N, f'{v.image["eido_frame_duration"]} (counted {N}; Blender\'s '
                  f'own frame_duration {v.image.frame_duration})')
            continue
        for loop in (True, False):
            tag = f'r{fps}_{speed}_{"loop" if loop else "once"}'
            v = screens.make_video_screen(mp4, width=0.5, start_frame=10, speed=speed, loop=loop, out_dir=W / tag,
                                          name=tag, standalone=False)
            bad = []
            for f in range(1, 73):
                got = decode(file_for(v.image, blender_file(f, v.image)))
                exp = screens.engine_movie_frame(f - 10, 24.0, fps, speed, N, loop)
                if got != exp:
                    bad.append((f, got, exp))
            bad_total += len(bad)
            check(f'retime {fps} fps x {speed} {"looping" if loop else "once"}: film frames 1..72 match the engine',
                  not bad, f'{len(bad)} differ' + (f', first (frame, shown, engine) {bad[:4]}' if bad else '') +
                  f'; sequence {v.frame_start} + {v.frame_duration}')

# ---------------------------------------------------------------------------------------------------- overlay keys
sc = S.fresh_scene(frames=(1, 30))
cam = S.camera(sc, (0, -3, 1), (0, 0, 1))
ov = overlay.make_overlay_layer(sc)
bar = ov.panel(draw=lambda c, t, w, h: c.clear((255, 255, 255, 255)), frames=(10, 20), out_dir=W / 'lt', name='lt',
               px=64)
fc = next(f for f in screens.action_fcurves(bar.obj.animation_data.action) if f.data_path == 'hide_render')
vis = {f: not bool(round(fc.evaluate(f))) for f in (1, 9, 10, 20, 21, 30)}
check('an overlay panel renders only inside its frames', vis == {1: False, 9: False, 10: True, 20: True, 21: False,
                                                                 30: False}, f'visible per frame {vis}')
full = ov.panel(draw=lambda c, t, w, h: c.clear((255, 255, 255, 255)), out_dir=W / 'lt', name='full', px=64)
check('a panel over the whole range gets no keys', full.obj.animation_data is None)

# ---------------------------------------------------------------------------------------------------- spill formula
sc = S.fresh_scene(frames=(1, 1))
s = screens.make_screen(width=1.0, height=0.6, px=32, draw=lambda c, t, w, h: c.clear('#2050ff'), frames=(1, 1),
                        out_dir=W / 'spill', name='blue', strength=1.0, spill=1.0)
m = s.means[0]
ld = s.light.data
want_w = np.pi * 0.6 * 1.0 * float(m.max())
col = np.array(ld.color)
check('spill: colour m / max(m), power pi A S max(m) gain, a custom cutoff',
      abs(ld.energy - want_w) < 1e-4 and np.allclose(col * ld.energy, m / m.max() * want_w, atol=2e-3)
      and ld.use_custom_distance and ld.cutoff_distance == 30.0,
      f'mean {np.round(m, 4).tolist()} -> {ld.energy:.4f} W x {np.round(col, 3).tolist()} (want {want_w:.4f} W), '
      f'cutoff {ld.cutoff_distance} m')

print('[check_screens_api]', 'ALL OK' if not fails else f'{len(fails)} FAILED: {fails}')
