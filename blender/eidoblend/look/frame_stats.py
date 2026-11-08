"""look/frame_stats.py: what a rendered frame measures as, read from the display-referred image (PNG stills or a video).

The look family's exposure rule, measured rather than eyeballed: in a delivered frame the share of pixels with ANY channel
at 250 or above (out of 255) must stay near zero. AgX rolls highlights off toward white, so a surface that reaches 250 has
lost its texture there: an overlit wall, white shells in sun gone flat. A chrome glint or the sun disc may clip, and is
small; a clipped REGION is a lighting or exposure fault. So besides the frame's share this reports the worst cell of a
grid (16 x 9 by default): a few scattered glints keep every cell low, an overlit wall fills one.

Pure numpy, so it runs inside Blender (images read through the bundled OpenImageIO) and outside it (system Python:
Pillow or OpenCV).

    python frame_stats.py <png|folder|video> [...] [--clip 250] [--max-share 0.001] [--max-cell 0.02] [--json out.json]
    python frame_stats.py sheet <png> [...] --out sheet.jpg [--cols 3] [--tile 640]

Inside Blender: from eidoblend.look import frame_stats; frame_stats.frame_stats(frame_stats.read_rgb(path)).
"""
import json
import os
import sys

import numpy as np

CLIP = 250          # a channel at or above this is clipped (display-referred, 8 bit)
BLACK = 5           # every channel at or below this is crushed
MAX_SHARE = 0.001   # the frame's clipped share allowed (0.1 %: glints, a sun disc)
MAX_CELL = 0.02     # the worst grid cell's clipped share allowed (2 %: more is a clipped region, not a glint)
GRID = (16, 9)
REC709 = np.array([0.2126, 0.7152, 0.0722], dtype=np.float32)


# --------------------------------------------------------------------------------------------------------- image IO
def read_rgb(path):
    """An image file as an H x W x 3 uint8 array (top row first). OpenImageIO inside Blender, else Pillow, else OpenCV."""
    try:
        import OpenImageIO as oiio
        buf = oiio.ImageBuf(str(path))
        if buf.has_error:
            raise OSError(buf.geterror())
        px = buf.get_pixels(oiio.UINT8)
        if px is None:
            raise OSError(f'{path}: unreadable')
        px = np.asarray(px)
        if px.ndim == 2:
            px = px[:, :, None]
        if px.shape[2] == 1:
            px = np.repeat(px, 3, axis=2)
        return np.ascontiguousarray(px[:, :, :3])
    except ImportError:
        pass
    try:
        from PIL import Image
        with Image.open(path) as im:
            return np.asarray(im.convert('RGB'))
    except ImportError:
        import cv2
        im = cv2.imread(str(path), cv2.IMREAD_COLOR)
        if im is None:
            raise OSError(f'{path}: unreadable')
        return im[:, :, ::-1].copy()


def write_rgb(path, rgb, quality=92):
    """Write an H x W x 3 uint8 array (PNG or JPEG by extension)."""
    rgb = np.ascontiguousarray(rgb, dtype=np.uint8)
    try:
        import OpenImageIO as oiio
        spec = oiio.ImageSpec(rgb.shape[1], rgb.shape[0], 3, oiio.UINT8)
        if str(path).lower().endswith(('.jpg', '.jpeg')):
            spec.attribute('Compression', f'jpeg:{quality}')
        out = oiio.ImageOutput.create(str(path))
        if out is None:
            raise OSError(oiio.geterror())
        out.open(str(path), spec)
        out.write_image(rgb)
        out.close()
        return path
    except ImportError:
        from PIL import Image
        Image.fromarray(rgb).save(path, quality=quality)
        return path


def iter_video(path, every=1):
    """Frames of a video as uint8 RGB arrays (OpenCV; outside Blender)."""
    import cv2
    cap = cv2.VideoCapture(str(path))
    i = 0
    while True:
        ok, im = cap.read()
        if not ok:
            break
        if i % every == 0:
            yield i, im[:, :, ::-1]
        i += 1
    cap.release()


# ---------------------------------------------------------------------------------------------------------- one frame
def luma(rgb):
    """Rec.709 luma of the display values, 0..255 (a perceptual measure of the delivered frame, not scene light)."""
    return rgb[:, :, :3].astype(np.float32) @ REC709


def frame_stats(rgb, clip=CLIP, black=BLACK, grid=GRID, region=None):
    """The measurements of one display-referred frame.

    clipped      share of pixels with any channel >= clip      (the highlight check)
    white        share with every channel >= clip              (pure white: the worst of it)
    black        share with every channel <= black
    luma_*       mean, median, 1st and 99th percentile of Rec.709 luma (0..255)
    worst_cell   [col, row, share]: the grid cell with the largest clipped share (grid cols x rows over the frame)
    cells_over   how many cells hold more than MAX_CELL clipped
    region       the same numbers inside a normalised box (x0, y0, x1, y1; origin top left), e.g. the subject's
    """
    rgb = np.asarray(rgb)[:, :, :3]
    h, w = rgb.shape[:2]
    mx = rgb.max(axis=2)
    mn = rgb.min(axis=2)
    clipped = mx >= clip
    y = luma(rgb)
    gc, gr = grid
    ys = np.linspace(0, h, gr + 1).astype(int)
    xs = np.linspace(0, w, gc + 1).astype(int)
    cell = np.zeros((gr, gc), dtype=np.float32)
    for r in range(gr):
        for c in range(gc):
            blk = clipped[ys[r]:ys[r + 1], xs[c]:xs[c + 1]]
            cell[r, c] = blk.mean() if blk.size else 0.0
    wr, wc = np.unravel_index(int(np.argmax(cell)), cell.shape)
    out = {
        'size': [int(w), int(h)],
        'clipped': float(clipped.mean()),
        'white': float((mn >= clip).mean()),
        'black': float((mx <= black).mean()),
        'luma_mean': float(y.mean()),
        'luma_median': float(np.median(y)),
        'luma_p01': float(np.percentile(y, 1)),
        'luma_p99': float(np.percentile(y, 99)),
        'worst_cell': [int(wc), int(wr), float(cell[wr, wc])],
        'cells_over': int((cell > MAX_CELL).sum()),
    }
    if region is not None:
        x0, y0, x1, y1 = region
        X0, X1 = int(max(0, min(w, x0 * w))), int(max(0, min(w, x1 * w)))
        Y0, Y1 = int(max(0, min(h, y0 * h))), int(max(0, min(h, y1 * h)))
        if X1 > X0 and Y1 > Y0:
            sub = rgb[Y0:Y1, X0:X1]
            sy = luma(sub)
            out['region'] = {'box': [X0, Y0, X1, Y1], 'clipped': float((sub.max(axis=2) >= clip).mean()),
                             'luma_median': float(np.median(sy)), 'luma_p99': float(np.percentile(sy, 99))}
    return out


def check_highlights(stats, max_share=MAX_SHARE, max_cell=MAX_CELL):
    """(ok, message) for one frame's stats: the frame's clipped share and its worst cell against the limits."""
    c, wc = stats['clipped'], stats['worst_cell']
    ok = c <= max_share and wc[2] <= max_cell
    msg = (f"clipped {c * 100:.3f} % of the frame (limit {max_share * 100:.2f} %), worst cell {wc[2] * 100:.1f} % at "
           f"col {wc[0]} row {wc[1]} (limit {max_cell * 100:.0f} %), white {stats['white'] * 100:.3f} %, "
           f"luma median {stats['luma_median']:.0f}, p99 {stats['luma_p99']:.0f}")
    if not ok:
        what = 'a clipped REGION (an overlit surface)' if wc[2] > max_cell else 'clipping spread over the frame'
        msg = f'HIGHLIGHTS CLIP: {what}; {msg}'
    return ok, msg


def clip_mask(rgb, clip=CLIP):
    """A review image: the frame darkened, clipped pixels painted magenta (where the highlight check is failing)."""
    rgb = np.asarray(rgb)[:, :, :3]
    out = (rgb.astype(np.float32) * 0.45).astype(np.uint8)
    m = rgb.max(axis=2) >= clip
    out[m] = (255, 0, 255)
    return out


# ------------------------------------------------------------------------------------------------------- a sequence
def sequence_stats(frames, clip=CLIP, frozen_mad=0.25, jump=12.0):
    """Measurements over a sequence of frames ((index, rgb) pairs, e.g. iter_video or PNG paths read in order).

    black_frames   indices whose 99th-percentile luma is under 8 (a black frame)
    frozen_runs    [first, last] runs where consecutive frames differ by under frozen_mad (mean abs, 0..255)
    luma_jumps     indices where the mean luma jumps by more than `jump` from the previous frame (a pop, a flash)
    clipped_max    the worst frame's clipped share, and its index
    """
    prev = None
    prev_mean = None
    black, jumps, frozen = [], [], []
    run = None
    worst = (0.0, None)
    n = 0
    for i, rgb in frames:
        n += 1
        rgb = np.asarray(rgb)[:, :, :3]
        y = luma(rgb)
        if np.percentile(y, 99) < 8:
            black.append(int(i))
        m = float(y.mean())
        if prev_mean is not None and abs(m - prev_mean) > jump:
            jumps.append(int(i))
        c = float((rgb.max(axis=2) >= clip).mean())
        if c > worst[0]:
            worst = (c, int(i))
        if prev is not None:
            mad = float(np.abs(rgb.astype(np.int16) - prev.astype(np.int16)).mean())
            if mad < frozen_mad:
                run = [run[0], int(i)] if run else [int(i) - 1, int(i)]
            elif run:
                frozen.append(run)
                run = None
        prev, prev_mean = rgb, m
    if run:
        frozen.append(run)
    return {'frames': n, 'black_frames': black, 'frozen_runs': frozen, 'luma_jumps': jumps,
            'clipped_max': [worst[0], worst[1]]}


# --------------------------------------------------------------------------------------------------- contact sheet
def sheet(paths, out, cols=3, tile=640, labels=None, gap=6):
    """Stills side by side in a grid (each tile keeps its aspect), with a label strip under each when Pillow is there."""
    ims = [read_rgb(p) for p in paths]
    if not ims:
        raise ValueError('sheet: no images')
    h0, w0 = ims[0].shape[:2]
    th = int(round(tile * h0 / w0))
    lab_h = 22 if labels else 0
    rows = (len(ims) + cols - 1) // cols
    W = cols * tile + (cols + 1) * gap
    H = rows * (th + lab_h) + (rows + 1) * gap
    canvas = np.full((H, W, 3), 24, dtype=np.uint8)
    for k, im in enumerate(ims):
        r, c = divmod(k, cols)
        y0 = gap + r * (th + lab_h + gap)
        x0 = gap + c * (tile + gap)
        canvas[y0:y0 + th, x0:x0 + tile] = _resize(im, tile, th)
    try:
        from PIL import Image, ImageDraw
        img = Image.fromarray(canvas)
        if labels:
            d = ImageDraw.Draw(img)
            for k, text in enumerate(labels):
                r, c = divmod(k, cols)
                d.text((gap + c * (tile + gap) + 4, gap + r * (th + lab_h + gap) + th + 4), str(text), fill=(230, 230, 230))
        img.save(out, quality=90)
    except ImportError:
        write_rgb(out, canvas)
    return out


def _resize(im, w, h):
    """Area-average resize with numpy alone (a contact-sheet tile; no interpolation library needed in Blender)."""
    H, W = im.shape[:2]
    if (W, H) == (w, h):
        return im
    ys = (np.arange(h + 1) * H / h).astype(int)
    xs = (np.arange(w + 1) * W / w).astype(int)
    f = im.astype(np.float32)
    # integral image, then box means per output pixel
    ii = np.zeros((H + 1, W + 1, 3), dtype=np.float64)
    ii[1:, 1:] = f.cumsum(0).cumsum(1)
    y0, y1 = ys[:-1], np.maximum(ys[1:], ys[:-1] + 1)
    x0, x1 = xs[:-1], np.maximum(xs[1:], xs[:-1] + 1)
    s = ii[y1][:, x1] - ii[y0][:, x1] - ii[y1][:, x0] + ii[y0][:, x0]
    area = ((y1 - y0)[:, None] * (x1 - x0)[None, :])[:, :, None]
    return np.clip(s / area, 0, 255).astype(np.uint8)


# ----------------------------------------------------------------------------------------------------------------- CLI
def _main(argv):
    if argv and argv[0] == 'sheet':
        import argparse
        ap = argparse.ArgumentParser(prog='frame_stats.py sheet')
        ap.add_argument('images', nargs='+')
        ap.add_argument('--out', required=True)
        ap.add_argument('--cols', type=int, default=3)
        ap.add_argument('--tile', type=int, default=640)
        ap.add_argument('--labels', default=None, help='comma separated; default: the file names')
        a = ap.parse_args(argv[1:])
        labels = a.labels.split(',') if a.labels else [os.path.basename(p) for p in a.images]
        print(sheet(a.images, a.out, cols=a.cols, tile=a.tile, labels=labels))
        return 0
    import argparse
    ap = argparse.ArgumentParser(description=__doc__.split('\n')[0])
    ap.add_argument('inputs', nargs='+', help='PNG/JPG files, folders of them, or a video')
    ap.add_argument('--clip', type=int, default=CLIP)
    ap.add_argument('--max-share', type=float, default=MAX_SHARE)
    ap.add_argument('--max-cell', type=float, default=MAX_CELL)
    ap.add_argument('--every', type=int, default=1, help='video: measure every Nth frame')
    ap.add_argument('--mask', default=None, help='write the clip mask of each failing still into this folder')
    ap.add_argument('--json', default=None)
    a = ap.parse_args(argv)
    rows, bad = [], 0
    for inp in a.inputs:
        if os.path.isdir(inp):
            files = sorted(os.path.join(inp, f) for f in os.listdir(inp) if f.lower().endswith(('.png', '.jpg', '.jpeg')))
        elif inp.lower().endswith(('.mp4', '.mov', '.mkv', '.webm', '.avi')):
            seq = sequence_stats(iter_video(inp, a.every), clip=a.clip)
            print(f'{inp}: {json.dumps(seq)}')
            rows.append({'video': inp, **seq})
            if seq['clipped_max'][0] > a.max_share:
                bad += 1
            continue
        else:
            files = [inp]
        for f in files:
            rgb = read_rgb(f)
            st = frame_stats(rgb, clip=a.clip)
            ok, msg = check_highlights(st, a.max_share, a.max_cell)
            print(f"{'ok ' if ok else 'BAD'} {f}: {msg}")
            rows.append({'file': f, 'ok': ok, **st})
            if not ok:
                bad += 1
                if a.mask:
                    os.makedirs(a.mask, exist_ok=True)
                    write_rgb(os.path.join(a.mask, os.path.splitext(os.path.basename(f))[0] + '_clip.png'), clip_mask(rgb, a.clip))
    if a.json:
        with open(a.json, 'w', encoding='utf-8') as fh:
            json.dump(rows, fh, indent=1)
    return 1 if bad else 0


if __name__ == '__main__':
    sys.exit(_main(sys.argv[1:]))
