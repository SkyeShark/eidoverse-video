"""The per-texel material's build tests (SURFACING_DESIGN.md 2.4-2.6, 3.3-3.7): what can be checked without a render.

    bash run_blender.sh blender/tests/terrain/surfacing/test_material_data.py [--cases canyon,alpine_valley]

Each case is a snapshot of the surface-data tests (surface_data/_cases.py) with its surface bake in the surface cache;
a case whose snapshot is missing is skipped with the command that makes it. With the bake cached nothing here uses
the GPU; without it the bake runs first (a GPU job: queue the run with EIDO_GPU_WRAP, blender/tests/_where.py).

Checks per case: the material builds; its samplers stay within the budget and are counted by image and state; every
atlas is read Linear and EXTEND in both reader slots (one sampler each; the families in surfacing.CUBIC_FAMILIES also
Cubic where a texel is magnified, which shares that sampler) and the ramp image only Closest; one level
reader group serves the near material, the far material and eido_terrain_map; no Bump node has the level reader
under its height; the far material builds with three images or fewer; eido_terrain_map offers every packed map and
the derived names. Then, with no terrain: which rings take the far material for a set of cameras.
Each test prints PASS / FAIL with its numbers; the run exits 1 on any failure.
"""
import json
import os
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import _material_scene as MS  # noqa: E402

import bpy  # noqa: E402
import _cases as C  # noqa: E402
from eidoblend.terrain.build import surfacing as S  # noqa: E402

RESULTS = []


def check(name, ok, detail=''):
    RESULTS.append((name, bool(ok), detail))
    print(f"[test] {'PASS' if ok else 'FAIL'} {name}: {detail}", flush=True)


def args():
    a = sys.argv[sys.argv.index('--') + 1:] if '--' in sys.argv else []

    def opt(k, d=None):
        return a[a.index(k) + 1] if k in a else d
    return dict(cases=opt('--cases', 'canyon,alpine_valley').split(','))


def trees(ng, seen=None):
    """A node group and every group under it, each once."""
    seen = {} if seen is None else seen
    if ng.name in seen:
        return seen
    seen[ng.name] = ng
    for n in ng.nodes:
        if n.bl_idname == 'ShaderNodeGroup' and n.node_tree is not None:
            trees(n.node_tree, seen)
    return seen


def upstream_groups(sock, seen=None, out=None):
    """The node groups a socket's value depends on (through links, within one tree)."""
    seen = set() if seen is None else seen
    out = set() if out is None else out
    for ln in sock.links:
        nd = ln.from_node
        if nd.name in seen:
            continue
        seen.add(nd.name)
        if nd.bl_idname == 'ShaderNodeGroup' and nd.node_tree is not None:
            out.add(nd.node_tree.name)
        for i in nd.inputs:
            upstream_groups(i, seen, out)
    return out


def test_case(case):
    try:
        t = C.terrain(case)
    except FileNotFoundError as e:
        print(f'[skip] {case}: {e}', flush=True)
        return
    sd = MS.surface(t)
    pal, strata = MS.palette_args(t)
    t0 = time.time()
    mat = S.surface_material(pal, recipe=t.recipe, strata=strata, data=sd, name=f'{case}_near', log=MS.log)
    build = time.time() - t0
    ng = next(n.node_tree for n in mat.node_tree.nodes if n.bl_idname == 'ShaderNodeGroup')
    nimg, nsamp = S._count_samplers(ng)
    check(f'{case}: the per-texel material builds within the sampler budget',
          nsamp <= S.MAX_SAMPLERS and nsamp == int(ng['eido_samplers']),
          f'{nimg} images, {nsamp} samplers of {S.MAX_SAMPLERS}, {S._nodes_in(ng)} nodes (groups expanded), '
          f'built in {build:.1f} s; D0 {float(ng["eido_far_m"]):.0f} m')
    fams = sd.images()
    atlas = {img.name for img in fams.values()}
    cubic_ok = {fams[f].name for f in S.CUBIC_FAMILIES if f in fams}
    states, lut = {}, set()
    for tr in trees(ng).values():
        for n in tr.nodes:
            if n.bl_idname != 'ShaderNodeTexImage' or n.image is None:
                continue
            if n.image.name in atlas:
                states.setdefault(n.image.name, set()).add((n.interpolation, n.extension))
            elif n.image.name.startswith('eido_ramps_'):
                lut.add((n.interpolation, n.extension))
    # Linear and Cubic share a sampler (SURFACING_DESIGN.md 1.3, probe A): the families in CUBIC_FAMILIES may add a
    # Cubic read where a texel is magnified; anything else (Closest, REPEAT, CLIP) would cost a sampler more
    bad = {k: sorted(v) for k, v in states.items()
           if not ({('Linear', 'EXTEND')} <= v <= {('Linear', 'EXTEND'), ('Cubic', 'EXTEND')})
           or (('Cubic', 'EXTEND') in v and k not in cubic_ok)}
    check(f'{case}: every atlas is read Linear (Cubic on {", ".join(S.CUBIC_FAMILIES)}, the same sampler) and EXTEND '
          f'only: one sampler for both reader slots', not bad,
          f'{len(states)} atlases read' + (f'; {bad}' if bad else ''))
    check(f'{case}: the ramp image is read Closest only', lut <= {('Closest', 'EXTEND')},
          f'{sorted(lut) or "no ramp in this palette"}')
    readers = [k for k in trees(ng) if k.startswith('eido_terrain_reader_')]
    under = []
    for tr in trees(ng).values():
        for n in tr.nodes:
            if n.bl_idname == 'ShaderNodeBump':
                if any(g.startswith('eido_terrain_reader_') for g in upstream_groups(n.inputs['Height'])):
                    under.append(tr.name)
    bumps = sum(1 for tr in trees(ng).values() for n in tr.nodes if n.bl_idname == 'ShaderNodeBump')
    check(f'{case}: no Bump node evaluates the level reader (a Bump runs its height three times)', not under,
          f'{bumps} Bump nodes' + (f'; reader under a bump in {under}' if under else ''))
    # the sector frames: hex-tiled for the box layers of the largest tiles (the cliffs), read once for the smaller
    # box tiles under them (surfacing.STEEP_HEX_SHARE)
    pal_d = S.resolve(pal, t.recipe, strata)
    box = {L['set']: float(L['tile_m']) for L in pal_d['layers'] if L['projection'] == 'box'}
    hexed = {}
    for n in ng.nodes:
        if n.bl_idname == 'ShaderNodeGroup' and n.node_tree is not None and n.node_tree.name.startswith('eido_layer_'):
            if 'S0' in n.inputs:
                tile = json.loads(n.node_tree['eido_sig'])[2]
                hexed[tile] = 'S0 RD0' in n.inputs
    big = max(box.values()) if box else 0.0
    want = {tile: tile >= S.STEEP_HEX_SHARE * big for tile in hexed}
    check(f'{case}: sector frames hex-tiled for the cliff-sized box tiles only', hexed == want,
          f'box tiles {sorted(box.values())}: hex-tiled in their sector frames {hexed}')
    fm = S.far_material(pal, recipe=t.recipe, strata=strata, data=sd, name=f'{case}_far', log=MS.log)
    fg = next(n.node_tree for n in fm.node_tree.nodes if n.bl_idname == 'ShaderNodeGroup')
    tm = S.terrain_map_group(sd)
    r_far = [k for k in trees(fg) if k.startswith('eido_terrain_reader_')]
    r_map = [k for k in trees(tm) if k.startswith('eido_terrain_reader_')]
    check(f'{case}: one level reader group serves the near material, the far material and eido_terrain_map',
          len(readers) == 1 and r_far == readers and r_map == readers, f'{readers}')
    check(f'{case}: the far material reads three images or fewer', int(fg['eido_samplers']) <= 3,
          f"{fg['eido_samplers']} samplers, {S._nodes_in(fg)} nodes")
    outs = {s.name for s in tm.interface.items_tree if s.in_out == 'OUTPUT'}
    packed = {n for grp in sd.packing() for n in grp}
    need = packed | {'slope', 'aspect', 'northness', 'eastness', 'insolation', 'height', 'Level'}
    check(f'{case}: eido_terrain_map offers every packed map and the derived names', need <= outs,
          f'{len(outs)} outputs' + (f'; missing {sorted(need - outs)}' if not need <= outs else ''))
    for m in (mat, fm):
        bpy.data.materials.remove(m)


def test_far_rings():
    """Rings beyond 1.5 D0 of every camera take the far material; a ring a camera stands on never does."""
    table = []
    wins = [(-8000, -8000, 8000, 8000), (-4000, -4000, 4000, 4000), (-1000, -1000, 1000, 1000),
            (-250, -250, 250, 250)]
    start = 0
    for k, w in enumerate(wins):
        table.append(dict(ring=k, level=k, start=start, count=100, window=list(w),
                          hole=list(wins[k + 1]) if k + 1 < len(wins) else None))
        start += 100
    obj = {'eido_terrain_rings': json.dumps(table)}
    centre = S.far_rings(obj, None, [(0.0, 0.0, 2.0)], far_m=1000.0)
    edge = S.far_rings(obj, None, [(0.0, 0.0), (7000.0, 0.0)], far_m=1000.0)
    near = S.far_rings(obj, None, [(0.0, 0.0)], far_m=3000.0)
    none = S.far_rings(obj, None, [], far_m=1000.0)
    check('far rings: beyond 1.5 D0 of every camera, never the ring a camera stands on',
          centre == [0] and edge == [] and near == [] and none == [],
          f'camera at the centre, D0 1000: {centre}; a second camera on the outer ring: {edge}; D0 3000: {near}; '
          f'no cameras: {none}')


def main():
    for case in args()['cases']:
        test_case(case)
    test_far_rings()
    bad = [n for n, ok, _d in RESULTS if not ok]
    print(f"[test] {len(RESULTS) - len(bad)} / {len(RESULTS)} passed" + (f'; FAILED: {bad}' if bad else ''), flush=True)
    return 1 if bad else 0


try:
    code = main()
except Exception:                                           # noqa: BLE001
    import traceback
    traceback.print_exc()
    code = 1
sys.stdout.flush()
os._exit(code)
