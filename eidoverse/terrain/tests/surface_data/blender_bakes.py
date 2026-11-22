"""Blender's palette bake (C and P) at the pinned commit on the surface data package's bake cases, for
tests/surface_data/palette_test.mjs (PORT_PLAN.md 8.2 row P14: "C and P within 1/255"). Runs in Blender (the far
colour is a GPU kernel of Blender's GPU module):

    EIDO_BLENDER_EDITION=<a checkout or `git archive` export of the blender branch> EIDO_SURFACE_COMMIT=<its commit>
    bash <the Blender edition>/run_blender.sh eidoverse/terrain/tests/surface_data/blender_bakes.py -- \
        --from <the Blender package's bake cache: blender/tests/terrain/out/surface_data/cache> \
        --snaps <its snapshots: blender/tests/terrain/out/surface_data/snap> [--case toroweap ...] [--pin]
    (on a shared machine, behind the GPU queue)

The snapshot of a case must be the terrain its bake in <from> was made from (the bake record's `terrain`, the
snapshot's cache_key): the Blender rounds re-make their snapshots, so a case whose snapshot has moved stops with the
two keys. Make its bake again from the snapshot as it is now (Blender's surface_data/bake_cases.py, in an export
holding the snapshot in its out/surface_data/snap/) and pass --pin: the snapshot (<case>.npz, .json, _make.json) is
copied into tests/out/surface_data/fixtures/blender_<commit>/snap/, where the port's tests read it before the Blender
edition's (_surface.mjs snapPath), so a later re-make in the Blender edition leaves the fixture whole.

Per case, the Blender package's own bake of the case (<from>/<case>/surface_<key>.json and _L<i>.npz: its maps as the
cache stores them; its palette files are left where they are) is copied into
tests/out/surface_data/fixtures/blender_<commit>/bakes/<case>/ and loaded there as a cache hit, and Blender's palette
bake (SurfaceData.bake_palette, provenance always) runs on it with the case's palette ('auto', resolved as
bake_surface resolves it), writing its palette files beside it. So the port's palette bake reads the very bytes
Blender's read. palette_bake.json records per case the palette tag, what was made and the seconds (the cost record),
and the tag of the package's own palette files: those were made on the fresh bake's float32 maps (a fresh Blender
bake hands its palette bake its unquantised maps, a cache hit the stored ones), the same palette code when the tags
agree. The Blender edition is only read.
"""
from __future__ import annotations

import json
import os
import shutil
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, '..', 'parity'))
import _blender as B  # noqa: E402

CASES = ['toroweap', 'lauterbrunnen', 'meteor_crater', 'great_sand_dunes', 'badlands_sd', 'canyon', 'alpine_valley',
         'fluvial_range']


def bake_json(folder):
    for nm in sorted(os.listdir(folder)):
        if nm.startswith('surface_') and nm.endswith('.json') and '_pal' not in nm:
            return nm[len('surface_'):-len('.json')]
    return None


def snapshot_terrain(snaps, name):
    """The terrain a snapshot holds: its sidecar's cache_key (Terrain.save writes <base>.json beside <base>.npz)."""
    try:
        with open(os.path.join(snaps, name + '.json'), encoding='utf-8') as f:
            return json.load(f).get('cache_key')
    except (OSError, ValueError):
        return None


def pin(snaps, name, out_root):
    """Copy a case's snapshot (<name>.npz and its sidecars) into the fixtures' snap/ folder beside bakes/: the folder
    and the files copied."""
    dst = os.path.join(os.path.dirname(out_root), 'snap')
    os.makedirs(dst, exist_ok=True)
    made = []
    for suffix in ('.npz', '.json', '_make.json'):
        src = os.path.join(snaps, name + suffix)
        if not os.path.exists(src):
            continue
        tgt = os.path.join(dst, name + suffix)
        if os.path.normcase(os.path.abspath(src)) != os.path.normcase(os.path.abspath(tgt)):
            shutil.copyfile(src, tgt + '.tmp')
            os.replace(tgt + '.tmp', tgt)
        made.append(name + suffix)
    return dst, made


def one(name, src_root, snaps, out_root, log=print, pin_snapshot=False):
    from eidoblend.terrain import api as A
    from eidoblend.terrain import surface as S
    from eidoblend.terrain.surface import bake as SB
    src = os.path.join(src_root, name)
    key = bake_json(src)
    if key is None:
        raise FileNotFoundError(f'{name}: no surface bake in {src}')
    with open(os.path.join(src, f'surface_{key}.json'), encoding='utf-8') as f:
        info = json.load(f)
    terrain, made_of = snapshot_terrain(snaps, name), info.get('terrain')
    if made_of and terrain != made_of:
        raise ValueError(f'{name}: the snapshot in {snaps} is terrain {terrain}, the bake in {src} is of terrain '
                         f'{made_of}: the snapshot was re-made after that bake (bake it again from the snapshot, then '
                         '--pin)')
    pinned = pin(snaps, name, out_root)[1] if pin_snapshot else None
    n = len(info['names'])
    dst = os.path.join(out_root, name)
    if os.path.isdir(dst):
        shutil.rmtree(dst)
    os.makedirs(dst)
    for i in range(n):
        shutil.copyfile(os.path.join(src, f'surface_{key}_L{i}.npz'), os.path.join(dst, f'surface_{key}_L{i}.npz'))
    shutil.copyfile(os.path.join(src, f'surface_{key}.json'), os.path.join(dst, f'surface_{key}.json'))
    own = sorted({nm[len(f'surface_{key}_'):].split('_L')[0] for nm in os.listdir(src)
                  if nm.startswith(f'surface_{key}_pal') and nm.endswith('.npz')})
    t = A.Terrain.load(os.path.join(snaps, name + '.npz'), build=False)
    palette = 'auto'
    info0 = getattr(t, 'info', None) or {}
    if info0.get('palette') not in (None, 'auto'):
        palette = info0['palette']                        # bake_surface's rule: the one make_terrain resolved
    pal = SB.resolve_palette(t, palette)
    hit = S.load_cached(dst, key, len(t.levels))
    if hit is None:
        raise FileNotFoundError(f'{name}: the copied bake does not load from {dst}')
    baked, binfo = hit
    sd = S.SurfaceData(t, baked, dict(binfo, cache_hit=True), info['options'], key, palette=pal, cache_dir=dst)
    t0 = time.perf_counter()
    sd.bake_palette(pal, cache=dst, log=log, provenance=True)
    sec = round(time.perf_counter() - t0, 3)
    rec = dict(case=name, key=key, terrain=terrain, snapshot_pinned=pinned, palette=palette, palette_name=pal.get('name'),
               tag=sd.info['palette_bake']['tag'], palette_bake=sd.info['palette_bake'], seconds=sec, package_tags=own,
               same_code_as_package=sd.info['palette_bake']['tag'] in own,
               levels=[dict(index=lv.index, role=lv.role, n=int(lv.n), cell=float(lv.cell)) for lv in t.levels])
    log(f'[blender_bakes] {name}: palette bake {rec["tag"]} in {sec} s ({sd.info["palette_bake"]})')
    return rec


def main():
    a = B.script_args()
    B.import_blender_terrain()
    names = [a[i + 1] for i, v in enumerate(a) if v == '--case' and i + 1 < len(a)] or CASES
    if '--from' not in a or '--snaps' not in a:
        print('blender_bakes: --from <the Blender package bake cache> and --snaps <its snapshots> are needed')
        return 2
    src_root, snaps = a[a.index('--from') + 1], a[a.index('--snaps') + 1]
    commit = os.environ.get('EIDO_SURFACE_COMMIT') or B.git(B.blender_edition(), 'rev-parse', 'HEAD') or 'unknown'
    out_root = os.path.join(B.TERRAIN, 'tests', 'out', 'surface_data', 'fixtures', f'blender_{commit[:7]}', 'bakes')
    os.makedirs(out_root, exist_ok=True)
    recs, rc = {}, 0
    for nm in names:
        try:
            recs[nm] = one(nm, src_root, snaps, out_root, pin_snapshot='--pin' in a)
        except Exception as e:                                # noqa: BLE001 - reported; the other cases go on
            import traceback
            traceback.print_exc()
            recs[nm] = dict(case=nm, error=repr(e))
            rc = 1
        sys.stdout.flush()
    path = os.path.join(out_root, 'palette_bake.json')
    old = {}
    if os.path.exists(path):
        with open(path, encoding='utf-8') as f:
            old = json.load(f).get('cases', {})
    old.update(recs)
    B.write_json(path, dict(commit=commit, versions=B.versions(), date=time.strftime('%Y-%m-%d %H:%M:%S'), cases=old))
    print(f'[blender_bakes] {len(recs)} cases -> {out_root}', flush=True)
    return rc


if __name__ == '__main__':
    code = main()
    sys.stdout.flush()
    os._exit(code)
