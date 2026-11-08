"""Several UNKNOWN FORCE exterior sets in one .blend (no GPU):

    cd <main checkout> && bash run_blender.sh <worktree>/blender/tests/sets_uf_city/test_two_sets_one_file.py

  - the city, then the standalone hole in the same scene (the registry's separate 'hole' set): the city keeps its
    materials, uniforms (and their keys), fog group and World; the two kits hold separate datablocks
  - two cities with different seeds side by side; disposing one leaves the other whole (the shared texture files
    stay while a set uses them), disposing both leaves nothing
  - the hole's lights: a light already in the scene does not reach a standalone hole's surfaces (hole.js's setLights
    [ring, hemi]); city_lights keeps a light; set_lights([light]) lets an excluded light back in
  - a canvas sequence baked to a blend-relative folder ('//uf_screens')
Prints PASS / FAIL.
"""
import sys
import tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parents[1]))

import bpy  # noqa: E402
from eidoblend.sets import unknown_force as UF  # noqa: E402
from eidoblend.sets.unknown_force import city as C  # noqa: E402
from eidoblend.sets.unknown_force import hole as H  # noqa: E402

OUT = HERE / 'out'
OUT.mkdir(exist_ok=True)
results = []


def check(name, ok, detail=''):
    results.append((name, bool(ok)))
    print('[uf-two-sets] %s %s %s' % ('PASS' if ok else 'FAIL', name, detail), flush=True)


def wipe():
    for c in (bpy.data.objects, bpy.data.meshes, bpy.data.materials, bpy.data.lights, bpy.data.cameras,
              bpy.data.node_groups, bpy.data.images, bpy.data.worlds):
        for x in list(c):
            c.remove(x)
    for c in list(bpy.data.collections):
        bpy.data.collections.remove(c)


def counts():
    return {k: len(getattr(bpy.data, k)) for k in ('objects', 'meshes', 'materials', 'images', 'node_groups',
                                                   'collections', 'worlds', 'lights')}


def alive(idb):
    try:
        idb.name
        return True
    except ReferenceError:
        return False


def mats_of(meshes):
    return {k: (o.material_slots[0].material.name if o.material_slots and o.material_slots[0].material else None)
            for k, o in meshes.items()}


wipe()
scene = bpy.context.scene
scene.render.fps = 24
n0 = counts()

# ---- the city, then the hole alone in the same scene
city = UF.build('city', scene, rain_count=200)
city.parts.apply_atmosphere(scene)
U = city.parts.uniforms
U.key('power', 100, 0.5)
M = city.parts.meshes
before = mats_of(M)
fac = M['uf_towers_concrete'].material_slots[0].material
groups_before = sorted(n.node_tree.name for n in fac.node_tree.nodes if n.type == 'GROUP')
world = scene.world
hole = UF.build('hole', scene)
after = mats_of(M)
groups_after = sorted(n.node_tree.name for n in fac.node_tree.nodes if n.type == 'GROUP') if alive(fac) else []
check('the city keeps its materials after the hole is built beside it', after == before and None not in after.values(),
      str(after))
check('... its uniforms (with their keys) and its fog group', alive(U.tree) and groups_after == groups_before and
      U.tree.animation_data is not None and U.tree.animation_data.action is not None, str(groups_after))
check('... and the scene\'s World (the hole\'s own waits for its apply_atmosphere)', scene.world == world and alive(world)
      and hole.parts.kit.world is not None and hole.parts.kit.world != world, scene.world.name if scene.world else None)
hk = hole.parts.kit
check('two kits, separate datablocks', hk.U.tree != U.tree and hk.fog_group() != city.parts.kit.fog_group() and
      hk.mat['concrete'] != city.parts.kit.mat['concrete'], f'{U.tree.name} / {hk.U.tree.name}')
hk.U['power'] = 0.1
check('the hole\'s controls are its own', abs(U['power'] - 0.5) < 1e-6 and abs(hk.U['power'] - 0.1) < 1e-6)
hole.dispose()
check('disposing the hole leaves the city whole', mats_of(M) == before and alive(U.tree) and scene.world == world and
      all(alive(i) for i in city.parts.kit.tex['concrete'].values()))
city.dispose()
leak = {k: v - n0[k] for k, v in counts().items() if v != n0[k]}
check('disposing both leaves nothing', not leak, f'left: {leak}')

# ---- two cities, two seeds
a = C.build({'hole': False, 'seed': 1909, 'rain_count': 100}, scene=scene)
b = C.build({'hole': False, 'seed': 7, 'rain_count': 100}, scene=scene)
ma, mb = mats_of(a.parts.meshes), mats_of(b.parts.meshes)
check('two cities side by side: each its own materials', set(ma.values()).isdisjoint(mb.values()), f'{ma} / {mb}')
tex = list(a.parts.kit.tex['asphalt'].values())
check('... sharing the texture files', tex == list(b.parts.kit.tex['asphalt'].values()))
a.dispose()
check('disposing the first leaves the second whole (its textures too)', mats_of(b.parts.meshes) == mb and
      all(alive(i) for i in tex) and alive(b.parts.uniforms.tree))
b.dispose()
check('... then the texture files go with the last set using them', not any(alive(i) for i in tex))
leak = {k: v - n0[k] for k, v in counts().items() if v != n0[k]}
check('disposing both cities leaves nothing', not leak, f'left: {leak}')

# ---- the hole's lights
key_d = bpy.data.lights.new('conductor_key', 'SPOT')
key = bpy.data.objects.new('conductor_key', key_d)
scene.collection.objects.link(key)
fill_d = bpy.data.lights.new('conductor_fill', 'POINT')
fill = bpy.data.objects.new('conductor_fill', fill_d)
scene.collection.objects.link(fill)


def state(light, coll):
    rc = light.light_linking.receiver_collection
    if rc is None:
        return None
    for i, c in enumerate(rc.children):
        if c == coll:
            return rc.collection_children[i].light_linking.link_state
    return None


tmp = Path(tempfile.mkdtemp(prefix='uf_two_sets_', dir=str(OUT)))
bpy.ops.wm.save_as_mainfile(filepath=str(tmp / 'two_sets.blend'))          # (small: saved before the hole is built)
h = H.build({'city_lights': [fill]}, scene=scene)
hc = h.collection
check('a standalone hole: a light already in the scene does not reach its surfaces', state(key, hc) == 'EXCLUDE',
      str(state(key, hc)))
check('... city_lights keeps one', state(fill, hc) is None, str(state(fill, hc)))
check('... its own lights are left to their own linking (the ring lights the hole and her)',
      {c.name for c in h.parts.lights['ring'].light_linking.receiver_collection.children} == {hc.name, h.parts.her.name})
h.parts.set_lights([key, fill])
check('set_lights([key, fill]): an excluded light lights the hole again', state(key, hc) is None and state(fill, hc) is None)
h.parts.set_lights([])
check('set_lights([]): neither does', state(key, hc) == 'EXCLUDE' and state(fill, hc) == 'EXCLUDE')

# ---- a canvas sequence into a blend-relative folder
board = h.parts.billboards[3]
try:
    board.set_canvas(lambda ctx, w, h_, t: H.draw_camp_screen(ctx, w, h_, H.CAMPS[7], t), frames=range(1700, 1704),
                     fps=24, out_dir='//uf_screens')
    files = sorted(p.name for p in (tmp / 'uf_screens').glob('*.png'))
    check('set_canvas(out_dir="//uf_screens"): the sequence beside the .blend', len(files) >= 4, ', '.join(files[:5]))
except Exception as e:                                   # noqa: BLE001
    check('set_canvas(out_dir="//uf_screens"): the sequence beside the .blend', False, repr(e))
h.dispose()
check('DIVE_C is in Blender axes', max(abs(x - y) for x, y in zip(C.DIVE_C, (116.6726, -116.6726, 12.0))) < 1e-3,
      str(C.DIVE_C))
for p in sorted(tmp.rglob('*'), reverse=True):
    p.unlink() if p.is_file() else p.rmdir()
tmp.rmdir()
fails = [n for n, ok in results if not ok]
print(f'[uf-two-sets] {len(results) - len(fails)}/{len(results)} passed' + (f'; FAILED: {fails}' if fails else ''))
