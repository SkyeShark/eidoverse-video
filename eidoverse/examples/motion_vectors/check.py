"""eidoverse/examples/motion_vectors/check.py: the runner's motion output ("motionVectors") checked on a render.

    python eidoverse/examples/motion_vectors/check.py [eido.py render options]     (renders on the GPU)

1. Renders the example (2 s, 320 x 180): work/motion_vectors_example/scene.mp4 and a motion file a frame in
   work/motion_vectors_example/motion/, (4, 180, 320) float16 each.
2. dlss5nr/motion_check.py on the film with those files (offset 0: the files are numbered by the video's frames) must
   name "+X -Y", the convention dlss5nr.py is then given, and warp the previous frame far closer than no motion does.
3. The attachment changes nothing in the picture: a still at 1 s rendered with "motionVectors" and one rendered from a
   copy of the config without it must be the same pixels.
Writes only under work/motion_vectors_example/. Prints PASS / FAIL lines; exit 1 on a FAIL.
"""
import glob
import json
import os
import subprocess
import sys

ROOT = os.path.normpath(os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', '..', '..'))
sys.path.insert(0, os.path.join(ROOT, 'dlss5nr'))
import numpy as np  # noqa: E402

import motion_check  # noqa: E402
import motion_npz  # noqa: E402

NO_WINDOW = 0x08000000 if os.name == 'nt' else 0
CONFIG = 'eidoverse/examples/motion_vectors/scene.json'
WORK = os.path.join(ROOT, 'work', 'motion_vectors_example')
FAIL = []


def check(ok, what):
    print(f"[motion_vectors] {'PASS' if ok else 'FAIL'}: {what}", flush=True)
    if not ok:
        FAIL.append(what)


def render(config, *extra):
    extra = list(extra) + sys.argv[1:]                     # this script's own arguments go to every render
    r = subprocess.run([sys.executable, 'eido.py', 'render', config] + extra, cwd=ROOT, capture_output=True,
                       text=True, encoding='utf-8', errors='replace', creationflags=NO_WINDOW)
    for line in (r.stdout + r.stderr).splitlines():
        if line.startswith(('[motion]', '[render_scene] DONE', '[auto-enhance] TSL')) or 'rror' in line:
            print('   ', line[:300], flush=True)
    return r.returncode


def pixels(png):
    raw = subprocess.run(['ffmpeg', '-v', 'error', '-i', png, '-f', 'rawvideo', '-pix_fmt', 'rgb24', '-'],
                         capture_output=True, check=True, creationflags=NO_WINDOW).stdout
    return np.frombuffer(raw, np.uint8)


def main():
    cfg = json.load(open(os.path.join(ROOT, CONFIG), encoding='utf-8'))
    motion_dir = os.path.join(ROOT, cfg['motionVectors'])
    film = os.path.join(ROOT, cfg['outputVideo'])
    for old in glob.glob(os.path.join(motion_dir, '*.npz')):
        os.remove(old)
    code = render(CONFIG)
    n = round(cfg['duration'] * cfg['fps'])
    files = sorted(glob.glob(os.path.join(motion_dir, '*.npz')))
    check(code == 0 and len(files) == n, f'the film and a motion file a frame ({len(files)} of {n})')
    if FAIL:
        sys.exit(1)
    shapes = {motion_npz.load(f).shape for f in files}
    check(shapes == {(4, cfg['height'], cfg['width'])}, f'each (4, {cfg["height"]}, {cfg["width"]}) ({shapes})')
    results = [motion_check.check_frame(film, motion_dir, m, 0, cfg['width'], cfg['height']) for m in (12, 24, 36)]
    for res in results:
        e = res['errors'] or {}
        print(f'    motion frame {res["frame"]}: {res["moving"]} moving pixels; '
              + ', '.join(f'{k} {e[k]:.2f}' for k in sorted(e, key=e.get)[:3]) + f'; none {e.get("none", 0):.2f}')
    best = motion_check.verdict(results)
    check(best == '+X -Y', f'motion_check names "+X -Y" (verdict {best})')
    # the same still with and without the attachment
    os.makedirs(WORK, exist_ok=True)
    plain = dict(cfg)
    plain.pop('motionVectors')
    plain['outputVideo'] = 'work/motion_vectors_example/plain.mp4'
    plain_cfg = os.path.join(WORK, 'plain.json')
    json.dump(plain, open(plain_cfg, 'w', encoding='utf-8'), indent=2)
    render(CONFIG, '--at', '1.0')
    render(os.path.relpath(plain_cfg, ROOT).replace('\\', '/'), '--at', '1.0')
    stills = [glob.glob(os.path.join(WORK, f'{stem}_probe_at*.png')) for stem in ('scene', 'plain')]
    same = all(len(s) == 1 for s in stills) and np.array_equal(pixels(stills[0][0]), pixels(stills[1][0]))
    check(same, f'the picture is the same with and without the motion attachment ({[os.path.basename(s[0]) for s in stills if s]})')
    print(f'[motion_vectors] {"FAIL" if FAIL else "PASS"}: {len(FAIL)} failed')
    sys.exit(1 if FAIL else 0)


if __name__ == '__main__':
    main()
