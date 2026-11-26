"""dlss5nr/motion_check.py: which reading of a motion source means "this pixel was there in the previous frame",
decided on the rendered film rather than assumed.

    python dlss5nr/motion_check.py <film.mp4> <motion dir> --frames 300,650,700 [--offset N]

--frames are motion-file numbers (the files <motion>/<frame:04d>.npz); --offset is dlss5nr.py's: the motion file of
video frame f is <f - N>, so motion file m belongs to video frame m + N. For each frame, the previous video frame is
warped by each candidate reading of the file (bilinear, edges clamped) and compared with the frame itself over the
pixels that move; the right reading has the smallest error, and clearly a smaller one than no motion at all. Pick
frames where things move (a frame with fewer than 500 moving pixels is skipped). Prints a line a frame and the
verdict, the --convention to give dlss5nr.py; exit 1 when the frames disagree or no reading beats no motion.
"""
import json
import os
import subprocess
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import numpy as np  # noqa: E402

import motion_npz  # noqa: E402

NO_WINDOW = 0x08000000 if os.name == 'nt' else 0
CANDIDATES = ('+X -Y', '-X +Y', '+X +Y', '-X -Y', '+Z -W', '-Z +W', '+Z +W', '-Z -W')


def video_size(path):
    out = subprocess.run(['ffprobe', '-v', 'error', '-select_streams', 'v:0', '-show_entries', 'stream=width,height',
                          '-of', 'json', path], capture_output=True, text=True, check=True, creationflags=NO_WINDOW).stdout
    s = json.loads(out)['streams'][0]
    return int(s['width']), int(s['height'])


def video_frame(path, index, w, h):
    """one video frame (0-based) as float32 RGB"""
    raw = subprocess.run(['ffmpeg', '-v', 'error', '-i', path, '-vf', f'select=eq(n\\,{index})', '-fps_mode', 'passthrough',
                          '-frames:v', '1', '-f', 'rawvideo', '-pix_fmt', 'rgb24', '-'], capture_output=True, check=True,
                         creationflags=NO_WINDOW).stdout
    if len(raw) != w * h * 3:
        raise SystemExit(f'[check] {path} has no frame {index}')
    return np.frombuffer(raw, np.uint8).reshape(h, w, 3).astype(np.float32)


def warp(img, dx, dy):
    """img sampled at (x + dx, y + dy): bilinear, edges clamped"""
    h, w = img.shape[:2]
    ys, xs = np.mgrid[0:h, 0:w].astype(np.float32)
    x, y = np.clip(xs + dx, 0, w - 1), np.clip(ys + dy, 0, h - 1)
    x0, y0 = np.floor(x).astype(int), np.floor(y).astype(int)
    x1, y1 = np.minimum(x0 + 1, w - 1), np.minimum(y0 + 1, h - 1)
    fx, fy = (x - x0)[..., None], (y - y0)[..., None]
    top = img[y0, x0] * (1 - fx) + img[y0, x1] * fx
    bottom = img[y1, x0] * (1 - fx) + img[y1, x1] * fx
    return top * (1 - fy) + bottom * fy


def check_frame(video, motion_dir, m, offset, w, h):
    """{'frame', 'moving', 'errors': {reading: mean abs error}} for motion file m, or None when too little moves"""
    xyzw = motion_npz.load(os.path.join(motion_dir, f'{m:04d}.npz')).astype(np.float32)
    if xyzw.shape[1:] != (h, w):
        raise SystemExit(f'[check] motion {m} is {xyzw.shape[2]}x{xyzw.shape[1]}, the film {w}x{h}')
    moving = np.abs(xyzw).max(axis=0) > 1.0
    if moving.sum() < 500:
        return {'frame': m, 'moving': int(moving.sum()), 'errors': None}
    cur, prev = video_frame(video, m + offset, w, h), video_frame(video, m + offset - 1, w, h)
    errors = {}
    for reading in CANDIDATES:
        dx, dy = motion_npz.displacement(xyzw, reading)
        errors[reading] = float(np.abs(warp(prev, dx, dy) - cur)[moving].mean())
    errors['none'] = float(np.abs(prev - cur)[moving].mean())
    return {'frame': m, 'moving': int(moving.sum()), 'errors': errors}


def verdict(results):
    """the reading that wins every checked frame and beats no motion on each, or None"""
    checked = [r for r in results if r['errors']]
    if not checked:
        return None
    winners = {min(CANDIDATES, key=r['errors'].get) for r in checked}
    if len(winners) != 1:
        return None
    best = winners.pop()
    return best if all(r['errors'][best] < 0.8 * r['errors']['none'] for r in checked) else None


def main():
    A = sys.argv[1:]
    if len(A) < 2 or '--frames' not in A:
        raise SystemExit(__doc__)
    video, motion_dir = A[0], A[1]
    opt = lambda k, d=None: A[A.index(k) + 1] if k in A else d  # noqa: E731
    offset = int(opt('--offset', '0'))
    frames = [int(v) for v in opt('--frames').split(',') if v]
    w, h = video_size(video)
    results = []
    for m in frames:
        r = check_frame(video, motion_dir, m, offset, w, h)
        results.append(r)
        if r['errors'] is None:
            print(f'[check] motion frame {m}: only {r["moving"]} moving pixels: pick a frame with motion')
            continue
        order = sorted(r['errors'], key=r['errors'].get)
        print(f'[check] motion frame {m} (video frame {m + offset}): {r["moving"]} moving pixels; '
              + ', '.join(f'{k} {r["errors"][k]:.2f}' for k in order), flush=True)
    best = verdict(results)
    if best is None:
        print('[check] no verdict: the frames disagree, or no reading beats no motion (check --offset, and the frames)')
        sys.exit(1)
    print(f'[check] convention: "{best}" (give dlss5nr.py --convention "{best}" --offset {offset})')


if __name__ == '__main__':
    main()
