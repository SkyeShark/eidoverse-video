"""The terrain cache (design section 2.6).

    key = make_key(recipe, knobs, size, resolution, seed, plan, focus)     # SHA-1 hex
    c = Cache(key)                       # eidoverse/assets/cache/terrain/<key>/ (git-ignored), or EIDO_TERRAIN_CACHE
    if c.complete():                     # meta.json written last: present = every level file is there
        fields = [c.load_level(i, lv) for i, lv in enumerate(plan)]
    else:
        ... run ...; c.save_level(i, fields); ...; c.write_meta({...})
    prune(keep_gb=20)                    # drop least recently used entries beyond a size

The key hashes the recipe dict, the resolved knob values, size, resolution, seed, the level plan, the focus,
TERRAIN_CODE_VERSION, and the bytes of the code that makes the fields (terrain/core/*.py, terrain/kernels/*.glsl,
terrain/solvers/*.py, terrain/run.py): editing a kernel or an op invalidates old entries without anyone having to
remember a bump. Bump TERRAIN_CODE_VERSION for what the sources cannot show (a driver or Blender change that alters
results). GPU results are deterministic on one machine (gathers, no atomics); across GPUs the last bits can differ,
so the cache is per machine and tests compare metrics, not bytes.

Level files are written to a temporary name and renamed into place, and meta.json last, so an interrupted run never
leaves an entry that looks complete.
"""

from __future__ import annotations

import glob
import hashlib
import json
import os
import shutil
import time

import numpy as np

TERRAIN_CODE_VERSION = 1
HERE = os.path.dirname(os.path.abspath(__file__))
TERRAIN_DIR = os.path.normpath(os.path.join(HERE, '..'))
REPO = os.path.normpath(os.path.join(TERRAIN_DIR, '..', '..', '..'))
CODE_GLOBS = ('core/*.py', 'kernels/*.glsl', 'solvers/*.py', 'run.py')


def root():
    """The cache folder: EIDO_TERRAIN_CACHE, or <repo>/eidoverse/assets/cache/terrain."""
    return os.environ.get('EIDO_TERRAIN_CACHE') or os.path.join(REPO, 'eidoverse', 'assets', 'cache', 'terrain')


def code_hash(globs=CODE_GLOBS):
    """SHA-1 over the bytes (and relative paths) of the code that makes the fields."""
    h = hashlib.sha1()
    files = sorted({p for g in globs for p in glob.glob(os.path.join(TERRAIN_DIR, g))})
    for p in files:
        h.update(os.path.relpath(p, TERRAIN_DIR).replace('\\', '/').encode('utf-8'))
        with open(p, 'rb') as f:
            h.update(f.read())
    return h.hexdigest()


def _plain(v):
    if hasattr(v, 'to_dict'):
        return v.to_dict()
    if isinstance(v, np.ndarray):
        return v.tolist()
    if isinstance(v, np.generic):
        return v.item()
    if isinstance(v, dict):
        return {str(k): _plain(x) for k, x in v.items()}
    if isinstance(v, (list, tuple)):
        return [_plain(x) for x in v]
    return v


def make_key(recipe, knobs, size, resolution, seed, plan, focus=None, extra=None):
    """The cache key: SHA-1 hex of everything that decides the fields (see the module doc). `recipe` is a Recipe
    or its dict, `plan` a list of Levels (or their dicts), `focus` points or None, `extra` any JSON-able settings the
    runner adds (sea level, flatten areas ...)."""
    payload = {'recipe': _plain(recipe), 'knobs': _plain(knobs or {}), 'size': float(size),
               'resolution': int(resolution), 'seed': int(seed), 'plan': _plain(plan), 'focus': _plain(focus),
               'extra': _plain(extra), 'version': TERRAIN_CODE_VERSION, 'code': code_hash()}
    blob = json.dumps(payload, sort_keys=True, separators=(',', ':'), default=str)
    return hashlib.sha1(blob.encode('utf-8')).hexdigest()


class Cache:
    """One cache entry: <root>/<key>/level_<i>.npz and meta.json."""

    def __init__(self, key, base=None):
        self.key = key
        self.path = os.path.join(base or root(), key)

    def level_path(self, i):
        return os.path.join(self.path, f'level_{int(i)}.npz')

    @property
    def meta_path(self):
        return os.path.join(self.path, 'meta.json')

    def complete(self):
        """True when meta.json exists and every level file it lists is present."""
        meta = self.read_meta()
        if meta is None:
            return False
        return all(os.path.exists(self.level_path(i)) for i in range(int(meta.get('levels', 0))))

    def save_level(self, i, fields, names=None, compress=False):
        """Write a level's fields (a dict of arrays; `names` limits which) to level_<i>.npz, atomically.
        Uncompressed by default: loading is the cache hit's budget (5 s)."""
        os.makedirs(self.path, exist_ok=True)
        arrays = {k: np.asarray(v) for k, v in fields.items() if names is None or k in names}
        tmp = self.level_path(i) + '.tmp.npz'
        (np.savez_compressed if compress else np.savez)(tmp, **arrays)
        os.replace(tmp, self.level_path(i))
        return self.level_path(i)

    def load_level(self, i, level=None):
        """The fields of level i: a Fields on `level` when given (core/fields.py), else a dict of arrays."""
        with np.load(self.level_path(i), allow_pickle=False) as z:
            arrays = {k: z[k] for k in z.files}
        if level is None:
            return arrays
        from .fields import Fields
        return Fields(level, arrays)

    def write_meta(self, meta):
        """meta.json, written last: what makes the entry complete. Adds key, version, code hash and time."""
        os.makedirs(self.path, exist_ok=True)
        m = dict(_plain(meta))
        m.update(key=self.key, version=TERRAIN_CODE_VERSION, code=code_hash(),
                 written=time.strftime('%Y-%m-%d %H:%M:%S'))
        tmp = self.meta_path + '.tmp'
        with open(tmp, 'w', encoding='utf-8') as f:
            json.dump(m, f, indent=1, default=str)
        os.replace(tmp, self.meta_path)
        return m

    def read_meta(self):
        try:
            with open(self.meta_path, encoding='utf-8') as f:
                m = json.load(f)
        except (OSError, ValueError):
            return None
        try:
            os.utime(self.meta_path)                       # a read counts as a use, for prune()
        except OSError:
            pass
        return m

    def size_bytes(self):
        return sum(os.path.getsize(p) for p in glob.glob(os.path.join(self.path, '*')) if os.path.isfile(p))

    def clear(self):
        shutil.rmtree(self.path, ignore_errors=True)


def entries(base=None):
    """[(last use time, bytes, Cache)] of every entry, oldest first."""
    out = []
    b = base or root()
    if not os.path.isdir(b):
        return out
    for d in os.listdir(b):
        c = Cache(d, b)
        if os.path.isdir(c.path):
            t = os.path.getmtime(c.meta_path) if os.path.exists(c.meta_path) else os.path.getmtime(c.path)
            out.append((t, c.size_bytes(), c))
    return sorted(out, key=lambda e: e[0])


def prune(keep_gb=20.0, base=None):
    """Delete the least recently used entries until the cache holds at most keep_gb. Returns the bytes freed."""
    es = entries(base)
    total = sum(e[1] for e in es)
    freed = 0
    for _t, size, c in es:
        if total - freed <= keep_gb * 1e9:
            break
        c.clear()
        freed += size
    return freed
