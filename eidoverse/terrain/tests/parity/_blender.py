"""What the parity package's Python tools share (PORT_PLAN.md 5.1, 5.2): where the Blender edition is, where the
parity outputs go and under which key, the versions every manifest records, and the JSON and npz writing of dumps.

    sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))     # from tests/parity/
    import _blender as B
    root = B.blender_edition()          # the Blender edition's root: blender/ beside eidoverse/ in this checkout (a
                                        # checkout of the blender branch holds both editions), else
                                        # $EIDO_BLENDER_EDITION (the root of a checkout of the blender branch)
    B.import_blender_terrain()          # sys.path set so `eidoblend.terrain` and the judge (`judge`) import
    B.bare_terrain_package()            # the same in plain Python: eidoblend.terrain without its __init__ (no bpy)
    B.parity_root()                     # $EIDO_PARITY_OUT, else eidoverse/terrain/tests/out/parity/ (git-ignored)
    B.source_key()                      # the Blender commit and code hashes the outputs are keyed by (5.1, 5.6)
    B.versions()                        # python, numpy, zlib, Blender, GPU: every manifest records them (C6)

Runs in Blender (bpy) or in Blender's own Python (`<Blender's python> -I`, numpy only), never the system Python: its
numpy and zlib are others (plan risk 13). Nothing here writes into the Blender edition; Python's bytecode caches
are switched off for it (sys.dont_write_bytecode) so a run leaves its folders as they were.
"""
from __future__ import annotations

import hashlib
import json
import math
import os
import subprocess
import sys

sys.dont_write_bytecode = True                  # the Blender edition is read-only to the port: no __pycache__ there

HERE = os.path.dirname(os.path.abspath(__file__))
TERRAIN = os.path.normpath(os.path.join(HERE, '..', '..'))              # eidoverse/terrain/
REPO = os.path.normpath(os.path.join(TERRAIN, '..', '..'))              # this checkout
NO_WINDOW = 0x08000000 if os.name == 'nt' else 0                        # CREATE_NO_WINDOW: no console on the desktop
# the paths whose code makes the fields and masks (core/cache.CODE_GLOBS and api._code_hash, and api.py, whose
# generate() the runs call): the outputs' key. build/ and surface/ make no field, so their commits leave it alone
TERRAIN_CODE = ('blender/eidoblend/terrain/core', 'blender/eidoblend/terrain/kernels',
                'blender/eidoblend/terrain/solvers', 'blender/eidoblend/terrain/run.py',
                'blender/eidoblend/terrain/recipes', 'blender/eidoblend/terrain/masks.py',
                'blender/eidoblend/terrain/api.py')


def blender_edition(required=True):
    """The root of the Blender edition: this checkout when it holds blender/eidoblend/terrain, else
    $EIDO_BLENDER_EDITION; None (or exit, with required) when neither does."""
    for root in (REPO, os.environ.get('EIDO_BLENDER_EDITION', '')):
        if root and os.path.isdir(os.path.join(root, 'blender', 'eidoblend', 'terrain', 'core')):
            return os.path.normpath(root)
    if required:
        sys.exit('parity: no Blender edition here or at $EIDO_BLENDER_EDITION (the root of a checkout of the blender '
                 'branch)')
    return None


def import_blender_terrain():
    """Put the Blender edition's blender/ (eidoblend) and blender/tests/terrain (the judge) and blender/tests (_where)
    on sys.path, first. Returns the edition's root."""
    root = blender_edition()
    for p in (os.path.join(root, 'blender', 'tests'), os.path.join(root, 'blender', 'tests', 'terrain'),
              os.path.join(root, 'blender')):
        if p not in sys.path:
            sys.path.insert(0, p)
    return root


def parity_root():
    """Where the parity outputs go: $EIDO_PARITY_OUT, else eidoverse/terrain/tests/out/parity/ (git-ignored)."""
    p = os.environ.get('EIDO_PARITY_OUT') or os.path.join(TERRAIN, 'tests', 'out', 'parity')
    os.makedirs(p, exist_ok=True)
    return os.path.normpath(p)


def git(root, *args):
    """A read-only git query in the Blender edition (no console window); its stdout, or '' when git fails."""
    try:
        r = subprocess.run(['git', '-C', root, *args], capture_output=True, text=True, creationflags=NO_WINDOW,
                           timeout=60)
        return r.stdout.strip() if r.returncode == 0 else ''
    except (OSError, subprocess.SubprocessError):
        return ''


def _hash_files(root, rels, exts=('.py', '.glsl')):
    h = hashlib.sha1()
    files = []
    for rel in rels:
        p = os.path.join(root, *rel.split('/'))
        if os.path.isfile(p):
            files.append(p)
        elif os.path.isdir(p):
            for dp, dn, fn in os.walk(p):
                dn[:] = sorted(d for d in dn if d != '__pycache__')
                files += [os.path.join(dp, f) for f in sorted(fn) if f.endswith(exts)]
    for p in sorted(files):
        h.update(os.path.relpath(p, root).replace('\\', '/').encode())
        with open(p, 'rb') as f:
            h.update(f.read())
    return h.hexdigest()


def bare_terrain_package():
    """Make `eidoblend.terrain` importable in plain Python (Blender's, -I) without its __init__: the bare package
    make_twin_fixtures.py makes (plain_import.install's, without its makedirs), so the numpy modules (core, the
    solvers' twins, the judge) import with no bpy. Inside Blender the real package is used instead."""
    import types
    root = import_blender_terrain()
    if 'eidoblend.terrain' in sys.modules:
        return root
    import eidoblend                                                      # noqa: F401 - imports nothing
    pkg = types.ModuleType('eidoblend.terrain')
    pkg.__path__ = [os.path.join(root, 'blender', 'eidoblend', 'terrain')]
    pkg.__package__ = 'eidoblend.terrain'
    sys.modules['eidoblend.terrain'] = pkg
    sys.modules['eidoblend'].terrain = pkg
    return root


def blender_code_hashes():
    """The Blender edition's two cache hashes as its own code computes them: (core/cache.code_hash(), the field
    hash; api._code_hash(), the terrain hash over recipes/*.py and masks.py, its lines repeated here so that api,
    which imports the mesh builder, is not imported)."""
    import glob
    from eidoblend.terrain.core import cache as CA
    here = os.path.dirname(os.path.abspath(CA.__file__))
    terrain = os.path.normpath(os.path.join(here, '..'))
    h = hashlib.sha1()
    for p in sorted(glob.glob(os.path.join(terrain, 'recipes', '*.py')) + [os.path.join(terrain, 'masks.py')]):
        if os.path.exists(p):
            with open(p, 'rb') as f:
                h.update(f.read())
    return CA.code_hash(), h.hexdigest()


def source_key(root=None):
    """What the parity outputs are keyed by (plan 5.1, 5.6): the last commit that changed the code making the fields
    and masks (TERRAIN_CODE: a commit of the surfacing pass alone leaves the fixtures valid), the files of
    TERRAIN_CODE that differ from it in the working tree (none, for a fixture worth keeping), the Blender code hashes
    (blender_code_hashes) and a hash over every file of TERRAIN_CODE. The folder is
    'blender_<commit 7>_<field hash 10>'."""
    root = root or blender_edition()
    commit = git(root, 'log', '-1', '--format=%H', '--', *TERRAIN_CODE) or 'unknown'
    dirty = git(root, 'status', '--porcelain', '--', *TERRAIN_CODE)
    field_hash, terrain_hash = blender_code_hashes()
    key = dict(commit=commit, head=git(root, 'rev-parse', 'HEAD') or 'unknown',
               branch=git(root, 'rev-parse', '--abbrev-ref', 'HEAD') or 'unknown',
               dirty=[ln for ln in dirty.splitlines() if ln.strip()], field_hash=field_hash, terrain_hash=terrain_hash,
               files_hash=_hash_files(root, TERRAIN_CODE))
    key['folder'] = f'blender_{commit[:7]}_{field_hash[:10]}'
    return key


def versions(gpu_info=None):
    """python, numpy, zlib, Blender (in Blender) and the GPU: what every manifest records (plan 5.1, C6)."""
    import platform
    import zlib
    import numpy as np
    v = dict(python=platform.python_version(), numpy=np.__version__, zlib=zlib.ZLIB_RUNTIME_VERSION,
             executable=os.path.basename(sys.executable))
    try:
        import bpy
        v['blender'] = bpy.app.version_string
    except ImportError:
        v['blender'] = None
    if gpu_info:
        v['gpu'] = dict(gpu_info)
    return v


# ------------------------------------------------------------------------------------------- JSON and arrays ---

def jsonable(v, arrays=None, path='', max_list=4096):
    """v as JSON: numpy scalars as numbers, NaN and infinities as None (and the reason kept: {'__float__': 'nan'}),
    tuples as lists, small arrays as lists; with `arrays` (a dict), an array of more than max_list values (or any
    2-D or higher array) goes there under `path` and the JSON holds {'__array__': path, 'shape', 'dtype'}; any other
    object as {'__class__': 'module.Name', ...its attributes}."""
    import numpy as np
    if isinstance(v, dict):
        return {str(k): jsonable(x, arrays, f'{path}.{k}' if path else str(k), max_list) for k, x in v.items()}
    if isinstance(v, (list, tuple)):
        return [jsonable(x, arrays, f'{path}[{i}]', max_list) for i, x in enumerate(v)]
    if isinstance(v, np.ndarray):
        if arrays is not None and (v.ndim >= 2 or v.size > max_list):
            arrays[path] = v
            return {'__array__': path, 'shape': list(v.shape), 'dtype': str(v.dtype)}
        return jsonable(v.tolist(), arrays, path, max_list)
    if isinstance(v, (np.bool_, bool)):
        return bool(v)
    if isinstance(v, (np.integer, int)):
        return int(v)
    if isinstance(v, (np.floating, float)):
        f = float(v)
        return f if math.isfinite(f) else {'__float__': repr(f)}
    if v is None or isinstance(v, str):
        return v
    d = getattr(v, '__dict__', None)
    if d is not None:
        out = {'__class__': f'{type(v).__module__}.{type(v).__qualname__}'}
        out.update(jsonable(dict(d), arrays, path, max_list))
        return out
    return {'__repr__': repr(v)}


def save_npz(path, arrays, compressed=True):
    """np.savez(_compressed) of {name: array} (names as given; a '/' or '.' in a name is kept: np.savez allows it)."""
    import numpy as np
    os.makedirs(os.path.dirname(os.path.abspath(path)) or '.', exist_ok=True)
    clean = {str(k): np.asarray(v) for k, v in arrays.items()}
    (np.savez_compressed if compressed else np.savez)(path, **clean)
    return path


def write_json(path, obj):
    os.makedirs(os.path.dirname(os.path.abspath(path)) or '.', exist_ok=True)
    tmp = path + '.tmp'
    with open(tmp, 'w', encoding='utf-8') as f:
        json.dump(obj, f, indent=1)
    os.replace(tmp, path)
    return path


def read_json(path, default=None):
    try:
        with open(path, encoding='utf-8') as f:
            return json.load(f)
    except (OSError, ValueError):
        return default


# ------------------------------------------------------------------------------------------------ the judge ---

LAKES_AS_SURFACE = ('judged with the lakes as their flat surfaces and no lake mask: judge/match.py cannot bring a lake '
                    'mask to a reference pixel finer than the generated cell when the reference is a softened radar '
                    'DSM (its _mask_to upsamples through core/grid.resample_box, which only averages down), so the '
                    "basin read's \"holds water\" rule is off for this verdict; the surface measured is the same")


def judge_dict(result, reference, label=None, source_chain=True):
    """The Blender judge's verdict (judge.judging.judge, as it is) of `result` (a Terrain, a Terrain.save path, a
    dict or an (h, cell) pair) as a dict, with every number. One judge for both editions (plan 6.3).

    One case the judge itself cannot take (reported to the lead as a defect of the Blender judge, not fixed there): a
    terrain with lakes whose cell is coarser than the reference's pixel and finer than its native resolution (a draft
    tower_karst, 15.6 m cells, against guilin_karst, 30 m radar stored at 8 m) raises in match._mask_to. Then the same
    surface is judged again with the lake depth added to the height and no lake mask, and the verdict carries
    'judge_note' saying so: the base run, the perturbed runs and the port are all judged this way, like for like."""
    import numpy as np
    from judge import judge
    from judge.judging import unpack
    try:
        return judge(result, reference, label=label, source_chain=source_chain).to_dict()
    except ValueError as e:
        h, cell, water, sea = unpack(result)
        if 'resample_box averages down' not in str(e) or water is None:
            raise
    w = np.asarray(water, np.float64)
    surf = np.asarray(h, np.float64) + np.where(w > 0.01, w, 0.0)          # match.surface's lake rule
    v = judge(dict(h=surf, cell=cell, sea_level=sea), reference, label=label, source_chain=source_chain).to_dict()
    v['judge_note'] = LAKES_AS_SURFACE
    v['notes'] = list(v.get('notes') or []) + [LAKES_AS_SURFACE]
    return v


def script_args():
    """The script's own arguments: after Blender's `--` (run_blender.sh passes one, and may pass a second)."""
    a = sys.argv[sys.argv.index('--') + 1:] if '--' in sys.argv else sys.argv[1:]
    while a and a[0] == '--':
        a = a[1:]
    return a
