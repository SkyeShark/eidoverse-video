#!/usr/bin/env python3
"""blender/tests/dlss5nr/test_render_motion.py: blender/tools/render_motion.py on a small two-shot film, checked the
way the film's motion is used: by DLSS 5's convention check against the rendered picture.

    python blender/tests/dlss5nr/test_render_motion.py [--no-render]

1. make_film.py (Blender) builds the film: 16 frames at 320 x 180, frame_start 1, a camera marker cutting to a second
   camera at frame 9; it saves out/film.blend and renders its beauty frames (8 samples), which become out/film.mp4.
2. The tool plans the shots (--plan): cuts.txt must say 1,9.
3. The tool renders the motion: a .npz for each of the 16 frames, (4, 180, 320) float16; the moving cube's pixels move
   and the floor under the fixed camera of shot 1 does not.
4. dlss5nr/motion_check.py on film.mp4 with those files (offset -1: video frame 0 is frame 1) must name "+X -Y" in both
   shots, the convention dlss5nr.py is then given.
--no-render does 1 and 2 only (Blender, no render). Renders run Blender directly through run_blender.sh: queue the whole
test on a shared GPU (EIDO_GPU_WRAP in front of `python`, as run_all.py does). Writes out/ (git-ignored) and
out/motion_sheet.png (the beauty of frames 5 and 13 above the length of their vectors): LOOK at it.
"""
import os
import shutil
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.normpath(os.path.join(HERE, '..', '..', '..'))
sys.path.insert(0, os.path.join(ROOT, 'dlss5nr'))
sys.dont_write_bytecode = True
import numpy as np  # noqa: E402

import motion_check  # noqa: E402
import motion_npz  # noqa: E402

OUT = os.path.join(HERE, 'out', 'render_motion')
NO_WINDOW = 0x08000000 if os.name == 'nt' else 0
FAIL = []


def check(ok, what):
    print(f"[render_motion] {'PASS' if ok else 'FAIL'}: {what}", flush=True)
    if not ok:
        FAIL.append(what)


def blender(script, *args):
    """a Blender run through this checkout's run_blender.sh (no GPU queue of its own: the test as a whole is queued)"""
    cmd = ['bash', os.path.join(ROOT, 'run_blender.sh').replace('\\', '/'), script.replace('\\', '/')] + list(args)
    r = subprocess.run(cmd, cwd=ROOT, capture_output=True, text=True, encoding='utf-8', errors='replace',
                       creationflags=NO_WINDOW)
    lines = [ln for ln in (r.stdout + r.stderr).splitlines() if ln.startswith(('[motion]', '[make_film]', 'Traceback'))
             or 'Error' in ln]
    for ln in lines[-12:]:
        print('   ', ln, flush=True)
    return r


def sheet(film, motion_dir, frames, path):
    """the beauty of each frame above |XY| of its vectors (white at the frame's 99th percentile), side by side"""
    try:
        from PIL import Image
    except ImportError:
        print('[render_motion] (no Pillow: no sheet)')
        return
    tiles = []
    for m in frames:
        beauty = motion_check.video_frame(film, m - 1, 320, 180).astype(np.uint8)
        xyzw = motion_npz.load(os.path.join(motion_dir, f'{m:04d}.npz')).astype(np.float32)
        mag = np.hypot(xyzw[0], xyzw[1])
        grey = (np.clip(mag / max(1e-3, np.percentile(mag, 99)), 0, 1) * 255).astype(np.uint8)
        tiles.append(np.concatenate([beauty, np.repeat(grey[..., None], 3, axis=2)], axis=0))
    Image.fromarray(np.concatenate(tiles, axis=1)).save(path)
    print(f'[render_motion] LOOK at {path}', flush=True)


def main():
    render = '--no-render' not in sys.argv
    if os.path.isdir(OUT):
        shutil.rmtree(OUT)
    os.makedirs(OUT)
    tool = os.path.join(ROOT, 'blender', 'tools', 'render_motion.py')
    blend, motion_dir = os.path.join(OUT, 'film.blend'), os.path.join(OUT, 'motion')
    r = blender(os.path.join(HERE, 'make_film.py'), '--out', OUT, *([] if render else ['--no-render']))
    check(r.returncode == 0 and os.path.isfile(blend), 'make_film.py saved the film')
    if FAIL:
        sys.exit(1)
    r = blender(tool, '--blend', blend, '--out', motion_dir, '--plan')
    cuts = open(os.path.join(motion_dir, 'cuts.txt'), encoding='utf-8').read().strip() \
        if os.path.isfile(os.path.join(motion_dir, 'cuts.txt')) else None
    check(r.returncode == 0 and cuts == '1,9', f'--plan: the shots start at 1 and 9 (cuts.txt: {cuts})')
    check(not [n for n in os.listdir(motion_dir) if n.endswith('.npz')], '--plan renders nothing')
    if not render:
        sys.exit(1 if FAIL else 0)

    beauty = os.path.join(OUT, 'beauty')
    film = os.path.join(OUT, 'film.mp4')
    subprocess.run(['ffmpeg', '-v', 'error', '-y', '-framerate', '24', '-start_number', '1', '-i',
                    os.path.join(beauty, '%04d.png'), '-c:v', 'libx264', '-crf', '12', '-pix_fmt', 'yuv420p', film],
                   check=True, creationflags=NO_WINDOW)
    r = blender(tool, '--blend', blend, '--out', motion_dir)
    files = sorted(n for n in os.listdir(motion_dir) if n.endswith('.npz'))
    check(r.returncode == 0 and files == [f'{f:04d}.npz' for f in range(1, 17)], f'a motion file a frame ({len(files)})')
    shapes = {motion_npz.load(os.path.join(motion_dir, n)).shape for n in files}
    check(shapes == {(4, 180, 320)}, f'each (4, 180, 320) float16, the film\'s pixels ({shapes})')
    check(not os.path.isdir(os.path.join(motion_dir, '_tmp')), 'the EXRs are cleaned up')
    # shot 1: a fixed camera; the floor's corners hold still, the cube's middle row moves ~ its screen speed
    x5 = motion_npz.load(os.path.join(motion_dir, '0005.npz')).astype(np.float32)
    corner = float(np.abs(x5[:2, 150:175, 5:40]).max())
    moving = float(np.percentile(np.hypot(x5[0], x5[1]), 99.5))
    check(corner < 0.05 and moving > 1.0, f'frame 5: the floor still ({corner:.3f} px), the cube moving (p99.5 '
                                          f'{moving:.2f} px a frame)')
    results = [motion_check.check_frame(film, motion_dir, m, -1, 320, 180) for m in (5, 13)]
    for res in results:
        e = res['errors'] or {}
        print(f'    motion frame {res["frame"]}: {res["moving"]} moving pixels; '
              + ', '.join(f'{k} {e[k]:.2f}' for k in sorted(e, key=e.get)[:3]) + f'; none {e.get("none", 0):.2f}')
    best = motion_check.verdict(results)
    check(best == '+X -Y', f'motion_check names "+X -Y" in both shots (verdict {best})')
    sheet(film, motion_dir, (5, 13), os.path.join(OUT, 'motion_sheet.png'))
    print(f'[render_motion] {"FAIL" if FAIL else "PASS"}: {len(FAIL)} failed')
    sys.exit(1 if FAIL else 0)


if __name__ == '__main__':
    main()
