"""dlss5nr/flicker.py: does a re-rendered film flicker where its input does not?

    python dlss5nr/flicker.py <input.mp4> <output.mp4> [--from a --to b]

Frame-to-frame luma change of the output against the input's: over the pixels the input holds still (under one level a
frame), over the ones it moves, and of the whole frame's mean luma (a global pumping of the light shows there). Run it
on a DLSS 5 pass before anyone watches it: frame by frame (no motion), the network's re-rendering changes still parts of
a picture by several times what the input does; with the temporal path the still parts should change about as little
as the input's. --from / --to (0-based) name the input's frames the output holds, when the output is a piece of it.
"""
import json
import os
import subprocess
import sys

import numpy as np

NO_WINDOW = 0x08000000 if os.name == 'nt' else 0


def luma(path, sel=None):
    vf = ['-vf', f'select=between(n\\,{sel[0]}\\,{sel[1]})'] if sel else []
    s = json.loads(subprocess.run(['ffprobe', '-v', 'error', '-select_streams', 'v:0', '-show_entries', 'stream=width,height',
                                   '-of', 'json', path], capture_output=True, text=True, check=True,
                                  creationflags=NO_WINDOW).stdout)['streams'][0]
    w, h = int(s['width']), int(s['height'])
    raw = subprocess.run(['ffmpeg', '-v', 'error', '-i', path] + vf + ['-fps_mode', 'passthrough', '-f', 'rawvideo',
                          '-pix_fmt', 'gray', '-'], capture_output=True, check=True, creationflags=NO_WINDOW).stdout
    return np.frombuffer(raw, np.uint8).reshape(-1, h, w).astype(np.float32)


def measure(a, b):
    """the numbers for input luma frames a and output luma frames b (n, h, w)"""
    n = min(len(a), len(b))
    a, b = a[:n], b[:n]
    da, db = np.abs(np.diff(a, axis=0)), np.abs(np.diff(b, axis=0))
    still = da < 1.0                                          # per pixel and frame pair: the input held it
    ma, mb = a.mean((1, 2)), b.mean((1, 2))
    return {'frames': n, 'still_share': float(still.mean()),
            'still_input': float(da[still].mean()) if still.any() else 0.0,
            'still_output': float(db[still].mean()) if still.any() else 0.0,
            'still_output_p99': float(np.percentile(db[still], 99)) if still.any() else 0.0,
            'moving_input': float(da[~still].mean()) if (~still).any() else 0.0,
            'moving_output': float(db[~still].mean()) if (~still).any() else 0.0,
            'mean_step_input': float(np.abs(np.diff(ma)).mean()), 'mean_step_output': float(np.abs(np.diff(mb)).mean()),
            'mean_step_output_max': float(np.abs(np.diff(mb)).max()), 'mean_offset': float((mb - ma).mean())}


def main():
    A = sys.argv[1:]
    if len(A) < 2 or A[0].startswith('--'):
        raise SystemExit(__doc__)
    opt = lambda k, d=None: A[A.index(k) + 1] if k in A else d  # noqa: E731
    m = measure(luma(A[0], (int(opt('--from')), int(opt('--to'))) if '--from' in A else None), luma(A[1]))
    print(f'[flicker] {m["frames"]} frames; the input holds {m["still_share"] * 100:.1f} % of its pixel-steps still')
    print(f'[flicker] where the input is still: input {m["still_input"]:.3f}, output {m["still_output"]:.3f} levels a frame '
          f'(output p99 {m["still_output_p99"]:.1f})')
    print(f'[flicker] where the input moves: input {m["moving_input"]:.2f}, output {m["moving_output"]:.2f}')
    print(f'[flicker] whole-frame mean luma, frame to frame: input {m["mean_step_input"]:.3f}, output '
          f'{m["mean_step_output"]:.3f} (max {m["mean_step_output_max"]:.3f}); output - input mean {m["mean_offset"]:+.2f}')


if __name__ == '__main__':
    main()
