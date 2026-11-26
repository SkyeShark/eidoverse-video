"""dlss5nr/flow_motion.py: motion files for DLSS 5's temporal path from the frames themselves (optical flow), for a film
whose renderer wrote no motion vectors.

    python dlss5nr/flow_motion.py <film.mp4> <out dir> [--preset medium | fast | ultrafast]

For every frame after the first, OpenCV's DIS optical flow from the frame to the one before: where each pixel was a
frame earlier, in pixels. Flow follows what the frames show, so it also catches what geometry vectors miss (grass and
leaves in the wind, a screen's changing face, a shadow sliding); it is rough where things are fine and fast, and at
disocclusions. Saved in the motion-file layout (motion_npz.py): <out>/<frame:04d>.npz, X = dx and Y = -dy (Y up, as
Blender's pass), so dlss5nr.py reads them with --convention "+X -Y" --offset 0. The numbers are the video's own 0-based
frames; frame 0 has no file, so the history starts at frame 1. A 1080p film takes about 0.3 s a frame (medium) and
writes 1-4 MB a frame: delete the folder after the pass. Needs OpenCV (pip install opencv-python-headless).
"""
import json
import os
import subprocess
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import numpy as np  # noqa: E402

import motion_npz  # noqa: E402

NO_WINDOW = 0x08000000 if os.name == 'nt' else 0


def main():
    A = sys.argv[1:]
    if len(A) < 2 or A[0].startswith('--'):
        raise SystemExit(__doc__)
    src, out = A[0], A[1]
    try:
        import cv2
    except ImportError:
        raise SystemExit('[flow] needs OpenCV: pip install opencv-python-headless')
    presets = {'ultrafast': cv2.DISOPTICAL_FLOW_PRESET_ULTRAFAST, 'fast': cv2.DISOPTICAL_FLOW_PRESET_FAST,
               'medium': cv2.DISOPTICAL_FLOW_PRESET_MEDIUM}
    preset = A[A.index('--preset') + 1] if '--preset' in A else 'medium'
    if preset not in presets:
        raise SystemExit(f'[flow] --preset is one of {sorted(presets)}')
    os.makedirs(out, exist_ok=True)
    s = json.loads(subprocess.run(['ffprobe', '-v', 'error', '-select_streams', 'v:0', '-show_entries', 'stream=width,height',
                                   '-of', 'json', src], capture_output=True, text=True, check=True,
                                  creationflags=NO_WINDOW).stdout)['streams'][0]
    w, h = int(s['width']), int(s['height'])
    dec = subprocess.Popen(['ffmpeg', '-v', 'error', '-i', src, '-f', 'rawvideo', '-pix_fmt', 'gray', '-'],
                           stdout=subprocess.PIPE, creationflags=NO_WINDOW)
    dis = cv2.DISOpticalFlow_create(presets[preset])
    prev, f, t0, mags = None, 0, time.time(), []
    while True:
        raw = dec.stdout.read(w * h)
        if len(raw) < w * h:
            break
        cur = np.frombuffer(raw, np.uint8).reshape(h, w)
        if prev is not None:
            flow = dis.calc(cur, prev, None)                  # cur(x) ~ prev(x + flow(x)): current -> previous
            xyzw = np.zeros((4, h, w), np.float16)
            xyzw[0], xyzw[1] = flow[..., 0], -flow[..., 1]
            motion_npz.save(os.path.join(out, f'{f:04d}.npz'), xyzw)
            mags.append(float(np.percentile(np.hypot(flow[..., 0], flow[..., 1]), 95)))
        prev, f = cur, f + 1
    dec.wait()
    if f < 2:
        raise SystemExit(f'[flow] {src}: {f} frame(s) decoded, no flow to measure')
    print(f'[flow] {f} frames, {f - 1} flows to {out} ({(time.time() - t0) / (f - 1):.2f} s a frame); '
          f'95th-percentile motion {np.median(mags):.1f} px a frame (median over frames), up to {max(mags):.1f}')


if __name__ == '__main__':
    main()
