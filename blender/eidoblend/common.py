"""eidoblend.common: what every family can share. Plain Python: importing it never imports bpy.

Paths
    REPO             the repository root (this file is <REPO>/blender/eidoblend/common.py)
    BLENDER_DIR      <REPO>/blender, the folder that goes on sys.path
    EIDOVERSE_DIR    <REPO>/eidoverse: the WebGPU engine (the port's source) and its shared assets
    ASSETS_DIR       <REPO>/eidoverse/assets: models, VRMs, animations, sets, sky textures ... reused as they are
    asset_path(*p)   an absolute path under ASSETS_DIR
    cache_dir()      the shared third-party library (fetch_texture.py / fetch_model.py --cache):
                     <REPO>/eidoverse/assets/cache, or EIDO_ASSET_CACHE when set (to read another checkout's library)

Coordinates: Blender is Z-up, metres. The WebGPU engine is three.js, Y-up, metres.
    three (x, y, z)                   -> Blender (x, -z, y)          from_three / to_three
    three quaternion (x, y, z, w)     -> Blender (w, x, -z, y)       quat_from_three (mathutils.Quaternion order)
    three ground point (x, z)         -> Blender (x, y) with y = -z  ground_from_three
    three Matrix4.elements (16, column-major) -> Blender 4x4 rows    matrix_from_three
The change of axes is a proper rotation (+90 degrees about X), so lengths, handedness and angles survive it.

Time: frames count from FRAME_START (1 by default, as in the films); t is seconds from the first frame.
    frame_at(t, fps, frame_start=1)   time_at(frame, fps, frame_start=1)

Small tools: script_args() (argv after Blender's '--'), log(tag, *msg), md5_file(path), atomic_write_text / _json.
"""

from __future__ import annotations

import hashlib
import json
import os
import sys
import tempfile

REPO = os.path.normpath(os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', '..'))
BLENDER_DIR = os.path.join(REPO, 'blender')
EIDOVERSE_DIR = os.path.join(REPO, 'eidoverse')
ASSETS_DIR = os.path.join(EIDOVERSE_DIR, 'assets')


def asset_path(*parts: str) -> str:
    """An absolute path under eidoverse/assets/ (the shared assets the Blender edition reuses as they are)."""
    return os.path.join(ASSETS_DIR, *parts)


def cache_dir(*parts: str) -> str:
    """The shared third-party library (git-ignored): textures/<ID>_<res>/, models/<id>_<res>/.

    EIDO_ASSET_CACHE points it at another folder, e.g. another checkout's eidoverse/assets/cache, so a fresh worktree
    can read a library that is already fetched instead of fetching it again."""
    base = os.environ.get('EIDO_ASSET_CACHE') or os.path.join(ASSETS_DIR, 'cache')
    return os.path.join(base, *parts)


def repo_path(p: str) -> str:
    """A scene-config path made absolute: relative paths resolve from the repository root, as in eido.py."""
    p = os.path.expanduser(str(p))
    return os.path.normpath(p if os.path.isabs(p) else os.path.join(REPO, p))


# ------------------------------------------------------------------------------------------------ coordinates ---

def from_three(x: float, y: float, z: float) -> tuple:
    """A three.js (Y-up) point or direction in Blender's Z-up axes: (x, y, z) -> (x, -z, y)."""
    return (x, -z, y)


def to_three(x: float, y: float, z: float) -> tuple:
    """A Blender (Z-up) point or direction in three.js's Y-up axes: (x, y, z) -> (x, z, -y)."""
    return (x, z, -y)


def quat_from_three(x: float, y: float, z: float, w: float) -> tuple:
    """A three.js quaternion (x, y, z, w) as a Blender rotation, in mathutils.Quaternion's (w, x, y, z) order.

    The axis of the rotation maps like any direction, (ax, ay, az) -> (ax, -az, ay); the angle is unchanged."""
    return (w, x, -z, y)


def ground_from_three(x: float, z: float) -> tuple:
    """A point on three's ground plane (x, z) on Blender's (x, y): APIs that took (x, z) take (x, y) with y = -z."""
    return (x, -z)


def matrix_from_three(elements) -> list:
    """three's Matrix4.elements (16 numbers, column-major) as a Blender 4x4 matrix (a list of 4 rows).

    B = C @ T @ C^-1 with C the change of axes; pass the result to mathutils.Matrix."""
    t = [[float(elements[c * 4 + r]) for c in range(4)] for r in range(4)]        # row-major three matrix
    perm = [(0, 1.0), (2, -1.0), (1, 1.0)]                                          # Blender axis i = sign * three axis j

    def three_index(i):
        return perm[i] if i < 3 else (3, 1.0)

    out = [[0.0] * 4 for _ in range(4)]
    for i in range(4):
        ti, si = three_index(i)
        for k in range(4):
            tk, sk = three_index(k)
            out[i][k] = si * sk * t[ti][tk]
    return out


# ------------------------------------------------------------------------------------------------------- time ---

def frame_at(t: float, fps: float, frame_start: int = 1) -> int:
    """The frame shown at t seconds (t = 0 is the first frame)."""
    return int(frame_start) + int(round(float(t) * float(fps)))


def time_at(frame: int, fps: float, frame_start: int = 1) -> float:
    """Seconds from the first frame to this one."""
    return (int(frame) - int(frame_start)) / float(fps)


# ------------------------------------------------------------------------------------------------------ tools ---

def script_args(argv=None) -> list:
    """The arguments a script was given after Blender's '--' (run_blender.sh passes its extra arguments there)."""
    argv = sys.argv if argv is None else argv
    return list(argv[argv.index('--') + 1:]) if '--' in argv else []


def log(tag: str, *msg) -> None:
    print(f'[{tag}]', *msg, flush=True)


def md5_file(path: str, chunk: int = 1 << 20) -> str:
    h = hashlib.md5()
    with open(path, 'rb') as f:
        while True:
            b = f.read(chunk)
            if not b:
                break
            h.update(b)
    return h.hexdigest()


def atomic_write_text(path: str, text: str) -> None:
    """Write through a temporary file in the same folder, then rename: a reader never sees half a file."""
    d = os.path.dirname(os.path.abspath(path))
    os.makedirs(d, exist_ok=True)
    fd, tmp = tempfile.mkstemp(dir=d, prefix='.' + os.path.basename(path) + '.', suffix='.tmp')
    try:
        with os.fdopen(fd, 'w', encoding='utf-8', newline='\n') as f:
            f.write(text)
        os.replace(tmp, path)
    except BaseException:
        try:
            os.remove(tmp)
        except OSError:
            pass
        raise


def atomic_write_json(path: str, obj, indent: int = 1) -> None:
    atomic_write_text(path, json.dumps(obj, indent=indent, default=str) + '\n')
