"""dlss5nr/motion_npz.py: the motion files DLSS 5's temporal path reads, one a frame.

A motion file is `<dir>/<frame:04d>.npz` holding one array, `xyzw`: float16, shape (4, H, W), rows top-down, in pixels.
That is the layout of Blender's raw Vector pass, X Y Z W as EEVEE writes them: X and Y point from a pixel to where its
surface was in the previous frame, with Y up; Z and W point to the next frame and are not used. So a file in this
layout is read with the convention "+X -Y" (dx = +X, dy = -Y: current -> previous, rows down). Every motion source in
the toolkit writes this layout: the Blender editions' `blender/tools/render_motion.py` (EEVEE's Vector pass), the
WebGPU editions' runner (`"motionVectors"`, three's velocity) and `flow_motion.py` (optical flow from the frames
themselves). `motion_check.py` decides a source's convention on the rendered video, so nothing needs assuming.

    import motion_npz
    motion_npz.save(path, xyzw)                    # (4, H, W) float16, deflated at level 1, written atomically
    xyzw = motion_npz.load(path)                   # the array back (np.load reads these files too)
    dx, dy = motion_npz.displacement(xyzw, '+X -Y')   # float32 pixels, current -> previous, rows down
"""
import ast
import io
import os
import zipfile

import numpy as np

AXES = 'XYZW'


def save(path, xyzw):
    """The same .npz np.savez_compressed(path, xyzw=xyzw) writes, deflated at level 1 (zlib's default level 6 takes
    about a second on a 1080p frame's 16 MB of half floats, for a file a fifth smaller), written beside and renamed."""
    xyzw = np.ascontiguousarray(xyzw, dtype=np.float16)
    if xyzw.ndim != 3 or xyzw.shape[0] != 4:
        raise ValueError(f'a motion array is (4, H, W), not {xyzw.shape}')
    b = io.BytesIO()
    np.save(b, xyzw)
    part = path + '.part'
    with zipfile.ZipFile(part, 'w', zipfile.ZIP_DEFLATED, compresslevel=1) as z:
        z.writestr('xyzw.npy', b.getvalue())
    os.replace(part, path)


def load(path):
    """The (4, H, W) float16 array of a motion file."""
    with np.load(path) as f:
        return f['xyzw']


def raw_planes(path, ix, iy, height, width):
    """Two of a motion file's channels as they are stored (float16 planes of height x width, rows top-down), as
    memoryviews of one read: no copy, no conversion. The member is read whole (one inflate and one CRC check, both
    outside the GIL, so a pool of threads can read ahead of a stream); np.load inflates in small pieces with Python
    between them. None when the file does not exist."""
    if not os.path.exists(path):
        return None
    with zipfile.ZipFile(path) as z:
        data = z.read('xyzw.npy')
    if data[:6] != b'\x93NUMPY' or data[6] not in (1, 2, 3):
        raise ValueError(f'{path}: xyzw.npy is not an .npy array')
    size = 2 if data[6] == 1 else 4
    start = 8 + size + int.from_bytes(data[8:8 + size], 'little')
    header = ast.literal_eval(data[8 + size:start].decode('latin1'))
    plane = height * width * 2
    if header != {'descr': '<f2', 'fortran_order': False, 'shape': (4, height, width)} or len(data) != start + 4 * plane:
        raise ValueError(f'{path}: xyzw is {header}, not a float16 (4, {height}, {width}) array in C order')
    view = memoryview(data)
    return view[start + ix * plane:start + (ix + 1) * plane], view[start + iy * plane:start + (iy + 1) * plane]


def parse_convention(text):
    """'+X -Y' -> ((1.0, 0), (-1.0, 1)): for dx then dy, the sign and the channel index (X Y Z W) they are read from."""
    parts = text.split()
    if len(parts) != 2 or any(len(p) != 2 or p[0] not in '+-' or p[1] not in AXES for p in parts):
        raise ValueError(f'a convention is two signed channels such as "+X -Y", not {text!r}')
    return tuple((-1.0 if p[0] == '-' else 1.0, AXES.index(p[1])) for p in parts)


def displacement(xyzw, convention):
    """dx, dy (float32 pixels, current -> previous, rows down) of a motion array read with a convention."""
    (sx, ix), (sy, iy) = parse_convention(convention)
    return sx * xyzw[ix].astype(np.float32), sy * xyzw[iy].astype(np.float32)
