"""test_api.py: the harness-rest ports inside Blender, checks only (nothing renders).

    bash run_blender.sh blender/tests/pipeline2/test_api.py [--only H,K,...]
    (EIDO_ASSET_CACHE at a checkout whose cache has wooden_stool_01_1k and alarm_clock_01_2k; deno on PATH for M)

  AC  audit_core_test.mjs's 14 cases as Blender scenes, through harness.audits (build_inventory, map_declarations,
      coverage): Empty / mesh parenting, provenance (eido_src_asset), hidden objects, collection instances as virtual
      leaves, a single-vertex mesh, an explicit registration, flags as custom properties
  H   placement's check_hovering: the clock seated on the stool passes; the stool moved 0.3 m (round one's false
      negative: its splayed legs still under the clock's box) names the clock; a book on a wire rack the ray grid
      slips through still counts as seated (the real surface is found); a book against a rack post and a cushion
      against a backrest, lifted, are named (a vertical face in the footprint holds nothing up)
  K   harness kits: islands (a two-part plant is one island), part(i), family(); kit instances seated with place_on
      on the ground and on each other through their real geometry; a floating instance is named by the audit
  M   play_model_animations(clip='all', weights=...) against three's own AnimationMixer (Deno) on the same GLB:
      bone positions at 13 times, weights 1 / 1 and 1 / 0.5 (a lone clip at 0.5 sits half way out of the rest pose)
  C   clone_model: actions shared by default; independent_actions=True gives the clone its own copies
  P   harness.post: stages in the engine's order, the overlay scene composited, _no_auto_enhance, _bloom_params
  R   render_common: setup_scene's default rig and camera in Blender axes, key_camera_path, ffmpeg_rate_control
  W   html_mesh and interior_window build what they claim (plane size, material graph, room picture scene)
Prints PASS / FAIL per check and 'N/M checks passed'; exits 1 on a failure (os._exit: Blender itself exits 0).
"""
import json
import math
import os
import subprocess
import sys
import traceback

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.normpath(os.path.join(HERE, '..', '..', '..'))
sys.path.insert(0, os.path.join(ROOT, 'blender'))
sys.dont_write_bytecode = True
OUT = os.path.join(HERE, 'out', 'api')
os.makedirs(OUT, exist_ok=True)

import bpy  # noqa: E402
from mathutils import Matrix, Vector  # noqa: E402

from eidoblend.harness import audits, ledger as L  # noqa: E402

results = []
ARGS = sys.argv[sys.argv.index('--') + 1:] if '--' in sys.argv else []
ONLY = set(ARGS[ARGS.index('--only') + 1].split(',')) if '--only' in ARGS else None


def check(name, ok, msg=''):
    results.append((name, bool(ok)))
    print(f"{'PASS' if ok else 'FAIL'} {name}: {msg}", flush=True)


def fresh():
    bpy.ops.wm.read_homefile(use_empty=True)
    return bpy.context.scene


def cube(name, size=1.0, loc=(0, 0, 0), parent=None, coll=None):
    h = size / 2
    me = bpy.data.meshes.new(name)
    me.from_pydata([(x, y, z) for x in (-h, h) for y in (-h, h) for z in (-h, h)], [],
                   [(0, 1, 3, 2), (4, 6, 7, 5), (0, 4, 5, 1), (2, 3, 7, 6), (0, 2, 6, 4), (1, 5, 7, 3)])
    ob = bpy.data.objects.new(name, me)
    (coll or bpy.context.scene.collection).objects.link(ob)
    ob.location = loc
    if parent is not None:
        ob.parent = parent
    return ob


def empty(name, loc=(0, 0, 0), parent=None):
    e = bpy.data.objects.new(name, None)
    bpy.context.scene.collection.objects.link(e)
    e.location = loc
    if parent is not None:
        e.parent = parent
    return e


def inv_of(sc, **kw):
    bpy.context.view_layer.update()
    return audits.build_inventory(sc, **kw)


def records(sc, policy=None, **kw):
    inv = inv_of(sc, **kw)
    decl = audits.map_declarations(sc, inv)
    return inv, decl, L.coverage_records(decl, inv, policy or L.snapshot_policy({}))


# --------------------------------------------------------------------------------------------------------- AC ---
def test_ac():
    counts = []
    for mode in ('sibling', 'group', 'meshparent'):
        sc = fresh()
        if mode == 'sibling':
            cube('a'), cube('b', loc=(5, 0, 0))
        elif mode == 'group':
            g = empty('g')
            cube('a', parent=g), cube('b', loc=(5, 0, 0), parent=g)
        else:
            a = cube('a')
            cube('b', loc=(5, 0, 0), parent=a)
        counts.append(len(inv_of(sc)['bodies']))
    check('AC1 2 separated boxes = 2 bodies under sibling / Empty parent / mesh parent', counts == [2, 2, 2], f'{counts}')
    sc = fresh()
    cube('a'), cube('b', loc=(0.2, 0, 0))
    n1 = len(inv_of(sc)['bodies'])
    sc = fresh()
    r = empty('kit')
    r['eido_src_asset'] = 'kitA'
    cube('a', parent=r), cube('b', loc=(0.2, 0, 0), parent=r)
    n2 = len(inv_of(sc)['bodies'])
    sc = fresh()
    r = empty('kit')
    r['eido_src_asset'] = 'kitA'
    cube('a', parent=r), cube('b', loc=(1.0, 0, 0), parent=r)
    n3 = len(inv_of(sc)['bodies'])
    check('AC2 no provenance 2 bodies; same eido_src_asset embedded 1; touching 2', (n1, n2, n3) == (2, 1, 2),
          f'{(n1, n2, n3)}')
    sc = fresh()
    cube('p0', loc=(-5, 0, 0)), cube('p1'), cube('p2', loc=(5, 0, 0))
    hull = cube('hull', 20)
    hull.hide_render = True
    inv = inv_of(sc)
    check('AC3 3 props + a hidden 20 m hull = 4 bodies, 3 physical', (len(inv['bodies']), len(inv['physical_bodies']))
          == (4, 3), f"{len(inv['bodies'])} / {len(inv['physical_bodies'])}")
    got = []
    for shard in (False, True):
        sc = fresh()
        r = empty('asset')
        r['eido_src_asset'] = 'kitB'
        a, b = cube('a', parent=r), cube('b', loc=(0.2, 0, 0), parent=r)
        if shard:
            a['allow_intersect'] = True
            b['allowIntersect'] = True
        else:
            r['allow_intersect'] = True
        inv = inv_of(sc)
        u = audits.map_declarations(sc, inv)['union_by_flag']['allow_intersect']
        got.append((len(u['full']), len(u['partial'])))
    check('AC4 a parent flag and per-leaf flags both full=1 partial=0', got == [(1, 0), (1, 0)], f'{got}')
    sc = fresh()
    a, b, c, d = cube('a'), cube('b', loc=(5, 0, 0)), cube('c', loc=(10, 0, 0)), cube('d', loc=(15, 0, 0))
    a['allow_intersect'], b['no_clipping_check'], c['assembly'] = True, True, 'x'
    _i, decl, _r = records(sc)
    u = decl['union_by_sensor'].get('clipping')
    check('AC5 the clipping sensor spans the three alias spellings', u and len(u['full']) == 3, f"{u and len(u['full'])}")
    sc = fresh()
    real = cube('real')
    real['no_support_check'] = True
    for i in range(50):
        cube(f'h{i}', loc=(100 + 5 * i, 0, 0)).hide_render = True
    _i, _d, rs = records(sc)
    s = next((r for r in rs if r['check'] == 'coverage.sensor.support'), None)
    check('AC6 support coverage = 100% of physical bodies despite 50 hidden; systemic WARN',
          s and s['metrics']['fraction'] == 1 and s['outcome'] == 'WARN', f"{s and s['metrics']}")
    sc = fresh()
    coll = bpy.data.collections.new('inst_src')
    cube('unit', coll=coll)
    for k, x in enumerate((-10, 10)):
        e = empty(f'inst_{k}', loc=(x, 0, 0))
        e.instance_type, e.instance_collection = 'COLLECTION', coll
        e['eido_src_asset'] = 'inst'
    cube('gap_prop')
    inv = inv_of(sc)
    check('AC7 2 collection instances + a prop in the gap = 3 bodies (instances are virtual leaves)',
          len(inv['bodies']) == 3, f"{len(inv['bodies'])}: {[b['label'] for b in inv['bodies']]}")
    Ls = []
    for yaw in (0.0, math.pi / 4):
        sc = fresh()
        ob = cube('bar')
        ob.scale = (10, 1, 1)
        ob.rotation_euler.z = yaw
        Ls.append(inv_of(sc)['bodies'][0]['L'])
    check('AC8 L identical at 0 and 45 deg yaw', abs(Ls[0] - Ls[1]) < 1e-6, f'{Ls}')
    sc = fresh()
    cube('a')
    _i, _d, rs = records(sc, policy=L.snapshot_policy({'_noMotionCheck': 1}))
    hit = next((r for r in rs if r['check'] == 'motion.envelope' and r['outcome'] == 'SKIPPED'), None)
    check('AC9 _noMotionCheck = 1: SKIPPED with the non-boolean note', hit and 'non-boolean number' in hit['message'],
          '')
    sc = fresh()
    me = bpy.data.meshes.new('pt')
    me.from_pydata([(0, 0, 0)], [], [])
    sc.collection.objects.link(bpy.data.objects.new('pt', me))
    cube('box', loc=(5, 0, 0))
    inv = inv_of(sc)
    check('AC10 a one-vertex mesh is inventoried, not physical', (len(inv['bodies']), len(inv['physical_bodies']))
          == (2, 1), f"{len(inv['bodies'])} / {len(inv['physical_bodies'])}")
    sc = fresh()
    sign = cube('lone_sign')
    sign['no_facing_check'] = True
    for i in range(30):
        cube(f'b{i}', loc=(10 + 5 * i, 0, 0))
    _i, _d, rs = records(sc)
    led = L.create_ledger()
    for r in rs:
        led.record(**r)
    txt = L.digest_from_ledger(led)
    check('AC11 a 1-of-31 declaration reaches the digest; review gate inside',
          'no_facing_check' in txt and 'lone_sign' in txt and 'REVIEW GATE' in txt, '')
    sc = fresh()
    cube('a')
    c1 = records(sc)[2]
    c2 = records(sc, policy=L.snapshot_policy({'_no_auto_placement_check': True}))[2]
    sc = fresh()
    cube('a')['allow_intersect'] = True
    c3 = records(sc)[2]

    def clean(rs):
        lg = L.create_ledger()
        for r in rs:
            lg.record(**r)
        return lg.is_clean()
    check('AC12 bare clean; global disable not clean; a declaration not clean',
          (clean(c1), clean(c2), clean(c3)) == (True, False, False), f'{(clean(c1), clean(c2), clean(c3))}')
    sc = fresh()
    r = empty('k')
    r['eido_src_asset'] = 'k'
    cube('a', parent=r), cube('b', loc=(1.0, 0, 0), parent=r)
    n0 = len(inv_of(sc, embed_frac=0)['bodies'])
    nn = len(inv_of(sc, embed_frac=float('nan'))['bodies'])
    check('AC13 embed_frac 0 / NaN cannot merge touching parts', (n0, nn) == (2, 2), f'{(n0, nn)}')
    sc = fresh()
    g = empty('claimed_one_body')
    cube('a', parent=g), cube('b', loc=(8, 0, 0), parent=g)
    inv = inv_of(sc, explicit_bodies=[g])
    co = inv['coalescence_declarations']
    check('AC14 an explicit registration keeps 2 bodies and is recorded with 2 islands',
          len(inv['bodies']) == 2 and len(co) == 1 and co[0]['islands'] == 2, f'{co}')
    sc = fresh()
    gn = cube('ground', 1.0)
    gn.scale = (10, 10, 0.1)
    mod = gn.modifiers.new('scatter', 'NODES')
    ng = bpy.data.node_groups.new('scatter', 'GeometryNodeTree')
    ng.interface.new_socket('Geometry', in_out='INPUT', socket_type='NodeSocketGeometry')
    ng.interface.new_socket('Geometry', in_out='OUTPUT', socket_type='NodeSocketGeometry')
    gi, go = ng.nodes.new('NodeGroupInput'), ng.nodes.new('NodeGroupOutput')
    pts = ng.nodes.new('GeometryNodeMeshLine')
    pts.inputs['Count'].default_value = 3
    pts.inputs['Offset'].default_value = (0.3, 0, 0)
    cone = ng.nodes.new('GeometryNodeMeshCone')
    iop = ng.nodes.new('GeometryNodeInstanceOnPoints')
    j = ng.nodes.new('GeometryNodeJoinGeometry')
    ng.links.new(pts.outputs[0], iop.inputs['Points'])
    ng.links.new(cone.outputs[0], iop.inputs['Instance'])
    ng.links.new(gi.outputs[0], j.inputs[0])
    ng.links.new(iop.outputs[0], j.inputs[0])
    ng.links.new(j.outputs[0], go.inputs[0])
    mod.node_group = ng
    inv = inv_of(sc)
    own = next(lf for lf in inv['leaves'] if lf['id'] == 'ground')
    check('AC+ a Geometry Nodes scatter: its own mesh is one leaf with its own box (not the instances\'), each '
          'instance a leaf', len(inv['leaves']) == 4 and abs(own['box'][1][2] - 0.05) < 1e-4,
          f"{len(inv['leaves'])} leaves; ground top {own['box'][1][2]:.3f}")


# ---------------------------------------------------------------------------------------------------------- H ---
def _import(name, res):
    from eidoblend.harness import assets
    return assets.import_model(assets.fetch_model_file(name, res=res), name=name)


def stool_and_clock(move=0.0):
    from eidoblend.placement import place_on
    sc = fresh()
    floor = cube('floor')
    floor.scale = (6, 6, 0.02)
    floor.location.z = -0.01
    bpy.context.view_layer.update()
    stool = _import('wooden_stool_01', '1k')
    clock = _import('alarm_clock_01', '2k')
    place_on(stool, floor, xy=(0.0, 0.0))
    place_on(clock, stool, xy=(0.03, 0.0))
    if move:
        stool.location.x += move
    bpy.context.view_layer.update()
    return sc, stool, clock


def test_h():
    from eidoblend.placement import check_hovering, clear_cache
    from eidoblend.placement import _world as W
    sc, stool, clock = stool_and_clock(0.0)
    rep = check_hovering(sc)
    check('H1 the clock seated on the stool is not flagged', not [r for r in rep if r['obj'] == clock],
          f"{[(r['obj'].name, round(r['gap'], 3), r['kind']) for r in rep]}")
    for move in (0.3, 0.6):
        sc, stool, clock = stool_and_clock(move)
        clear_cache()
        rb = W.tight_box(clock)
        sb = W.tight_box(stool)
        old = (abs(rb[0].z - sb[1].z) < 0.08 and rb[1].x > sb[0].x and rb[0].x < sb[1].x
               and rb[1].y > sb[0].y and rb[0].y < sb[1].y)
        rep = check_hovering(sc)
        hit = [r for r in rep if r['obj'] == clock]
        verdict = "the engine's box test would have missed it" if old else 'the box test also catches it'
        check(f'H2 stool moved {move} m: the clock is named ({verdict})',
              hit and hit[0]['gap'] > 0.3, f"{[(r['obj'].name, round(r['gap'], 3), r['kind']) for r in hit]}; "
              f'clock x {rb[0].x:.3f}..{rb[1].x:.3f}, stool x {sb[0].x:.3f}..{sb[1].x:.3f}')
    # a wire rack: bars 2 mm thick spaced so the 11 x 11 footprint grid passes between all of them
    from eidoblend.placement import place_on, support_under_footprint
    sc = fresh()
    floor = cube('floor')
    floor.scale = (6, 6, 0.02)
    floor.location.z = -0.01
    rack = empty('rack')
    for i in range(15):                                             # wires at odd centimetres, the grid at even
        b = cube(f'wire_{i}', 1.0, parent=rack)
        b.scale = (0.002, 0.6, 0.002)
        b.location = (-0.29 + 0.04 * i, 0.0, 0.8)
    for x in (-0.31, 0.31):
        for y in (-0.31, 0.31):
            leg = cube(f'leg_{x}_{y}', 1.0, parent=rack)
            leg.scale = (0.01, 0.01, 0.8)
            leg.location = (x, y, 0.4)
    book = cube('book', 1.0)
    book.scale = (0.2, 0.15, 0.04)
    book.location = (0.0, 0.0, 0.801 + 0.02)
    book['_support_targets'] = ['rack']
    bpy.context.view_layer.update()
    clear_cache()
    rb = W.tight_box(book)
    rays = W.Rays(W.collect(rack))
    c = W.box_center(rb)
    grid_hit = support_under_footprint(book, rays, c.x, c.y, rb[0].z + 0.01, 11, box=rb)
    rep = check_hovering(sc)
    check('H3 a book on a wire rack the 11x11 rays slip through is still seated (the real surface is found)',
          grid_hit is None and not [r for r in rep if r['obj'] == book],
          f"ray grid hit {grid_hit}; flagged {[(r['obj'].name, round(r['gap'], 3)) for r in rep]}")
    # a vertical part of the support inside the footprint holds nothing up: a book against a rack's post and a
    # cushion against a chair's backrest, each lifted off its board / seat, are named (the engine's box test named
    # them; a fallback that counted any of the support's faces rising past the base called them seated)
    from eidoblend.placement import snap_to_ground

    def boxes_mesh(name, boxes):
        verts, faces = [], []
        for (x0, y0, z0), (x1, y1, z1) in boxes:
            o = len(verts)
            verts += [(x0, y0, z0), (x1, y0, z0), (x1, y1, z0), (x0, y1, z0),
                      (x0, y0, z1), (x1, y0, z1), (x1, y1, z1), (x0, y1, z1)]
            faces += [(o, o + 3, o + 2, o + 1), (o + 4, o + 5, o + 6, o + 7), (o, o + 1, o + 5, o + 4),
                      (o + 1, o + 2, o + 6, o + 5), (o + 2, o + 3, o + 7, o + 6), (o + 3, o, o + 4, o + 7)]
        me = bpy.data.meshes.new(name)
        me.from_pydata(verts, [], faces)
        ob = bpy.data.objects.new(name, me)
        bpy.context.scene.collection.objects.link(ob)
        return ob
    posts = [((x, y, 0.0), (x + 0.04, y + 0.04, 1.8)) for x in (-0.42, 0.38) for y in (-0.22, 0.18)]
    boards = [((-0.42, -0.22, z), (0.42, 0.22, z + 0.02)) for z in (0.4, 0.9, 1.4)]
    seat_back = [((-0.22, -0.22, 0.42), (0.22, 0.22, 0.46)), ((-0.22, 0.18, 0.46), (0.22, 0.22, 0.95))] + \
        [((x, y, 0.0), (x + 0.04, y + 0.04, 0.42)) for x in (-0.22, 0.18) for y in (-0.22, 0.18)]
    out = []
    for what, sup_boxes, item_box, at, lift in (
            ('a book against a rack post', posts + boards, ((-0.075, -0.1, 0.0), (0.075, 0.1, 0.25)),
             (-0.306, -0.12, 1.05), 0.25),
            ('a cushion against a chair backrest', seat_back, ((-0.18, -0.18, 0.0), (0.18, 0.18, 0.08)),
             (0.0, 0.01, 0.47), 0.3)):
        for dz in (0.0, lift):
            sc = fresh()
            boxes_mesh('floor', [((-3, -3, -0.02), (3, 3, 0.0))])
            sup = boxes_mesh('support', sup_boxes)
            item = boxes_mesh('item', [item_box])
            item.location = at
            bpy.context.view_layer.update()
            ok = snap_to_ground(item, sup, below=True)
            item.location.z += dz
            bpy.context.view_layer.update()
            clear_cache()
            hit = [r for r in check_hovering(sc) if r['obj'] == item]
            out.append((what, dz, ok, [round(r['gap'], 3) for r in hit]))
    check('H4 a vertical part of the support (a rack post, a backrest) in the footprint holds nothing up: seated '
          'items pass, the same items lifted are named',
          all(ok and bool(g) == bool(dz) and (not dz or abs(g[0] - dz) < 0.01) for _w, dz, ok, g in out), f'{out}')


# ---------------------------------------------------------------------------------------------------------- K ---
def make_kit_glb(path):
    """A kit as fetched kits come: a two-part plant (pot + foliage), a crate, a crate_b, a lamp post, in a row."""
    fresh()
    host = empty('KitRoot')
    parts = [('plant_pot', (0.0, 0, 0.15), (0.3, 0.3, 0.3)), ('plant_leaves', (0.0, 0, 0.55), (0.5, 0.5, 0.5)),
             ('crate_a', (2.0, 0, 0.6), (0.4, 0.4, 0.4)), ('crate_b', (3.0, 0, 0.2), (0.4, 0.4, 0.4)),
             ('lamp_post', (5.0, 0, 1.0), (0.1, 0.1, 2.0))]
    for name, loc, s in parts:
        ob = cube(name, 1.0, parent=host)
        ob.location, ob.scale = loc, s
    bpy.ops.export_scene.gltf(filepath=path, export_format='GLB', use_selection=False)
    return [p[0] for p in parts]


def test_k():
    from eidoblend.harness import assets
    from eidoblend.placement import place_on, check_hovering, clear_cache
    from eidoblend.placement import _world as W
    glb = os.path.join(OUT, 'kit_islands.glb')
    names = make_kit_glb(glb)
    sc = fresh()
    ground = cube('ground')
    ground.scale = (8, 8, 0.1)
    ground.location.z = -0.05
    kit = assets.load_kit(glb)
    # list() is the catalogue's own order, as the engine's (names.slice()); Blender's exporter wrote this GLB's
    # children by name, so here that order is alphabetical
    check('K1 the kit lists its parts through the wrapper (count, names, list in the file\'s order)',
          kit.count == 5 and sorted(kit.names) == sorted(names) and kit.list() == kit.names, f'{kit.names}')
    groups = sorted(sorted(g) for g in kit.island_groups())
    check('K2 islands: the pot and its leaves are one island; four islands in all',
          len(groups) == 4 and ['plant_leaves', 'plant_pot'] in groups, f'{groups}')
    isl = kit.islands()
    bpy.context.view_layer.update()
    lows = []
    for e in isl:
        lo, hi = W.tight_box(e)
        lows.append(round(lo.z, 4))
    check('K3 every island instance stands on its base at the origin (z = 0)', all(abs(z) < 1e-4 for z in lows),
          f'{lows}')
    for e in isl:
        bpy.data.objects.remove(e)
    first = kit.part(0)
    fam = kit.family('CRATE')
    check('K4 part(0) and family() (case-insensitive) give instances', first is not None and len(fam) == 2,
          f'{first and first.name}, {[f.name for f in fam]}')
    for e in [first] + fam:
        bpy.data.objects.remove(e)
    crate = kit.get('crate_a', location=(1.0, 0.5, 3.0), rotation_z=0.4)
    bpy.context.view_layer.update()
    clear_cache()
    ok1 = place_on(crate, ground)
    lo, hi = W.tight_box(crate)
    top = W.tight_box(ground)[1].z
    lamp = kit.get('lamp_post', location=(1.0, 0.5, 5.0))
    bpy.context.view_layer.update()
    ok2 = place_on(lamp, crate)
    llo, _lhi = W.tight_box(lamp)
    check('K5 place_on seats a kit instance on the ground, and another ON it, through their real geometry',
          ok1 and ok2 and abs(lo.z - top) < 0.002 and abs(llo.z - hi.z) < 0.002,
          f'crate bottom {lo.z:.4f} (ground top {top:.4f}); lamp bottom {llo.z:.4f} (crate top {hi.z:.4f})')
    floater = kit.get('crate_b', location=(-2.0, -2.0, 1.2))
    bpy.context.view_layer.update()
    rep = check_hovering(sc)
    named = {r['obj'].name: (round(r['gap'], 2), r['kind']) for r in rep}
    check('K6 the hovering audit sees instances: the crate left 1.2 m up is named, the seated ones are not',
          floater.name in named and crate.name not in named and lamp.name not in named, f'{named}')


# ---------------------------------------------------------------------------------------------------------- M ---
MIX_DUMP = r"""
import * as THREE from 'npm:three@0.184.0';
import { GLTFLoader } from 'npm:three@0.184.0/examples/jsm/loaders/GLTFLoader.js';
const [path, specJson] = Deno.args;
const spec = JSON.parse(specJson);
const buf = Deno.readFileSync(path);
const gltf = await new Promise((res, rej) => new GLTFLoader().parse(buf.buffer, '', res, rej));
const out = {};
for (const [tag, weights] of Object.entries(spec.weights)) {
  const root = gltf.scene.clone(true);
  const mixer = new THREE.AnimationMixer(root);
  for (const name of spec.order) {
    const clip = gltf.animations.find((c) => c.name === name);
    const a = mixer.clipAction(clip);
    a.setLoop(THREE.LoopRepeat, Infinity);
    a.weight = weights[name];
    a.play();
  }
  out[tag] = [];
  for (const t of spec.times) {
    mixer.setTime(t);
    root.updateMatrixWorld(true);
    const row = {};
    for (const n of spec.nodes) {
      const o = root.getObjectByName(n);
      const p = new THREE.Vector3(); o.getWorldPosition(p);
      row[n] = [p.x, p.y, p.z];
    }
    out[tag].push(row);
  }
}
console.log('JSON' + JSON.stringify(out));
"""


def reversed_animations_glb(src, dst):
    """A copy of a GLB with its animations array reversed (the file's clip order, not the names', decides three's
    mix)."""
    import struct
    b = open(src, 'rb').read()
    ln = struct.unpack('<I', b[12:16])[0]
    j = json.loads(b[20:20 + ln])
    rest = b[20 + ln:]
    j['animations'] = j['animations'][::-1]
    s = json.dumps(j).encode()
    s += b' ' * ((4 - len(s) % 4) % 4)
    open(dst, 'wb').write(struct.pack('<4sII', b'glTF', 2, 20 + len(s) + len(rest)) + struct.pack('<I4s', len(s), b'JSON')
                          + s + rest)
    return [a['name'] for a in j['animations']]


def make_rig_glb(path, third=False):
    """A three-bone chain with two clips: 'Nod' turns bones b1 and b2, 'Sway' turns b0 and b1 (b1 is in both);
    third=True adds 'Twist', a large turn of b1 as well (three clips on one bone: their mix order shows)."""
    from mathutils import Euler
    sc = fresh()
    sc.render.fps = 24
    arm = bpy.data.armatures.new('rig')
    ob = bpy.data.objects.new('rig', arm)
    sc.collection.objects.link(ob)
    bpy.context.view_layer.objects.active = ob
    bpy.ops.object.mode_set(mode='EDIT')
    prev = None
    for i in range(4):
        b = arm.edit_bones.new(f'b{i}')
        b.head = (0, 0, 0.5 * i)
        b.tail = (0, 0, 0.5 * (i + 1))
        if prev is not None:
            b.parent = prev
            b.use_connect = True
        prev = b
    bpy.ops.object.mode_set(mode='OBJECT')
    ob.animation_data_create()
    curves = {'Nod': {'b1': [(1, (0, 0, 0)), (13, (0.5, 0, 0)), (25, (0, 0, 0.3)), (37, (0, 0, 0))],
                      'b2': [(1, (0, 0, 0)), (19, (0, 0.6, 0)), (37, (0, 0, 0))]},
              'Sway': {'b0': [(1, (0, 0, 0)), (25, (0, 0.4, 0)), (49, (0, 0, 0))],
                       'b1': [(1, (0, 0, 0)), (25, (-0.4, 0, 0.2)), (49, (0, 0, 0))]}}
    if third:
        curves['Twist'] = {'b1': [(1, (0.2, 0, 0)), (17, (0.3, 1.1, -0.6)), (33, (-0.5, 0.2, 0.9)), (49, (0.2, 0, 0))]}
    for name, bones in curves.items():
        act = bpy.data.actions.new(name)
        ob.animation_data.action = act
        for bn, keys in bones.items():
            pb = ob.pose.bones[bn]
            pb.rotation_mode = 'QUATERNION'
            for f, e in keys:
                pb.rotation_quaternion = Euler(e).to_quaternion()
                pb.keyframe_insert('rotation_quaternion', frame=f)
        tr = ob.animation_data.nla_tracks.new()
        tr.name = name
        tr.strips.new(name, 1, act)
        ob.animation_data.action = None
    for pb in ob.pose.bones:
        pb.rotation_quaternion = (1, 0, 0, 0)
    bpy.ops.export_scene.gltf(filepath=path, export_format='GLB', export_animation_mode='ACTIONS',
                              export_force_sampling=True)


def test_m():
    import shutil
    from eidoblend.harness import assets
    from eidoblend import common
    deno = shutil.which('deno')
    if not deno:
        return check('M three.js mixer parity', False, 'deno not on PATH')
    glb = os.path.join(OUT, 'rig_two_clips.glb')
    make_rig_glb(glb)
    times = [i / 4 for i in range(13)]                              # 0 .. 3 s, every 6 frames
    nodes = ['b1', 'b2', 'b3']
    spec = {'order': ['Nod', 'Sway'], 'times': times, 'nodes': nodes,
            'weights': {'single': {'Nod': 1.0, 'Sway': 0.0}, 'equal': {'Nod': 1.0, 'Sway': 1.0},
                        'half': {'Nod': 0.5, 'Sway': 1.0}}}
    dump = os.path.join(OUT, 'clip_mix_dump.mjs')
    open(dump, 'w', encoding='utf-8').write(MIX_DUMP)
    r = subprocess.run([deno, 'run', '--no-config', '--no-lock', '-A', dump, glb, json.dumps(spec)],
                       capture_output=True, text=True, timeout=180)
    line = next((l for l in r.stdout.splitlines() if l.startswith('JSON')), None)
    if not line:
        return check('M three.js mixer parity', False, r.stderr[-400:])
    js = json.loads(line[4:])
    for tag, weights in spec['weights'].items():
        sc = fresh()
        sc.render.fps = 24
        sc.frame_start, sc.frame_end = 1, 73
        root = assets.import_model(glb, name='rig_model')
        clips = sorted(assets.model_clips(root))
        if tag == 'single':                                     # one clip: the NLA strip path
            played = assets.play_model_animations(root, clip='Nod') + ['Sway']
        else:
            played = assets.play_model_animations(root, clip='all', weights=weights)
        arm = next(o for o in assets.subtree(root) if o.type == 'ARMATURE')
        worst = 0.0
        for k, t in enumerate(times):
            sc.frame_set(1 + int(round(t * 24)))
            for n in nodes:
                pb = arm.pose.bones[n]
                p = arm.matrix_world @ pb.head
                q = Vector(common.from_three(*js[tag][k][n]))
                worst = max(worst, (p - q).length)
        what = "clip='Nod' (an NLA strip)" if tag == 'single' else f"clip='all', weights {weights} (baked)"
        check(f"M {what} matches three's AnimationMixer at {len(times)} times",
              worst < 2e-3 and played == ['Nod', 'Sway'] and clips == ['Nod', 'Sway'],
              f'worst bone-joint distance {worst * 1000:.3f} mm over {len(nodes)} joints')
    # three clips on one bone, the file's order not the names': Twist, Sway, Nod
    tmp = os.path.join(OUT, 'rig_three_clips.glb')
    make_rig_glb(tmp, third=True)
    glb3 = os.path.join(OUT, 'rig_three_clips_reversed.glb')
    file_order = reversed_animations_glb(tmp, glb3)
    w3 = {'Nod': 1.0, 'Sway': 0.6, 'Twist': 0.8}
    spec3 = {'order': file_order, 'times': times, 'nodes': nodes, 'weights': {'file': w3}}
    r = subprocess.run([deno, 'run', '--no-config', '--no-lock', '-A', dump, glb3, json.dumps(spec3)],
                       capture_output=True, text=True, timeout=180)
    spec3['order'] = sorted(file_order)
    r2 = subprocess.run([deno, 'run', '--no-config', '--no-lock', '-A', dump, glb3, json.dumps(spec3)],
                        capture_output=True, text=True, timeout=180)
    js3 = json.loads(next(l for l in r.stdout.splitlines() if l.startswith('JSON'))[4:])['file']
    js3n = json.loads(next(l for l in r2.stdout.splitlines() if l.startswith('JSON'))[4:])['file']
    sc = fresh()
    sc.render.fps = 24
    sc.frame_start, sc.frame_end = 1, 73
    root = assets.import_model(glb3, name='rig3')
    assets.play_model_animations(root, clip='all', weights=w3)
    arm = next(o for o in assets.subtree(root) if o.type == 'ARMATURE')
    worst = sens = 0.0
    for k, t in enumerate(times):
        sc.frame_set(1 + int(round(t * 24)))
        for n in nodes:
            p = arm.matrix_world @ arm.pose.bones[n].head
            worst = max(worst, (p - Vector(common.from_three(*js3[k][n]))).length)
            sens = max(sens, (Vector(js3[k][n]) - Vector(js3n[k][n])).length)
    check(f"M three clips on one bone, file order {file_order}: matches three's mixer in that order",
          worst < 2e-3 and sens > 5e-3 and list(root.get('eido_clip_order', [])) == file_order,
          f'worst {worst * 1000:.3f} mm; three itself moves the joints {sens * 1000:.1f} mm when the clips play in name '
          f'order instead, so the order is what this measures')


# ---------------------------------------------------------------------------------------------------------- C ---
def test_c():
    from eidoblend.harness import assets
    glb = os.path.join(OUT, 'rig_two_clips.glb')
    if not os.path.exists(glb):
        make_rig_glb(glb)
    sc = fresh()
    sc.frame_start, sc.frame_end = 1, 48
    a = assets.import_model(glb, name='rig_a')
    assets.play_model_animations(a, clip='Nod')
    shared = assets.clone_model(a, name='rig_shared')
    own = assets.clone_model(a, name='rig_own', independent_actions=True)

    def strips(root):
        arm = next(o for o in assets.subtree(root) if o.type == 'ARMATURE')
        return [s.action for t in arm.animation_data.nla_tracks for s in t.strips if s.action]
    sa, ss, so = strips(a), strips(shared), strips(own)
    check('C1 a default clone shares the clips\' actions', [x.name for x in sa] == [x.name for x in ss]
          and all(x is y for x, y in zip(sa, ss)), f'{[x.name for x in ss]}')
    check('C2 independent_actions=True: the clone owns copies of every action',
          len(so) == len(sa) and not any(x is y for x, y in zip(sa, so)) and all(x.name.endswith('.rig_own') for x in so),
          f'{[x.name for x in so]}; recorded {list(own.get("eido_own_actions", []))}')
    arm_o = next(o for o in assets.subtree(own) if o.type == 'ARMATURE')
    arm_a = next(o for o in assets.subtree(a) if o.type == 'ARMATURE')
    arm_s = next(o for o in assets.subtree(shared) if o.type == 'ARMATURE')

    def tip(arm, f):
        sc.frame_set(f)
        return (arm.matrix_world @ arm.pose.bones['b3'].head).copy()
    follow = max((tip(arm_s, f) - tip(arm_a, f)).length for f in (7, 13, 19, 31))
    moves = (tip(arm_o, 7) - tip(arm_o, 19)).length
    check('C4 the clones PLAY (not a frozen first key): the shared clone follows the original frame for frame, the '
          'own-actions clone moves', follow < 1e-5 and moves > 0.05 and (tip(arm_a, 7) - tip(arm_a, 19)).length > 0.05,
          f'shared vs original worst {follow:.2e} m; own clone b3 moves {moves:.3f} m between frames 7 and 19')
    act = next(x for x in so if x.name.startswith('Nod'))
    from bpy_extras import anim_utils
    st = next(s for t in arm_o.animation_data.nla_tracks for s in t.strips if s.action is act)
    cb = anim_utils.action_get_channelbag_for_slot(act, st.action_slot)
    for fc in cb.fcurves:
        for kp in fc.keyframe_points:
            kp.co.y += 0.3 if fc.array_index == 1 else 0.0
        fc.update()
    sc.frame_set(13)
    pa = (arm_a.matrix_world @ arm_a.pose.bones['b3'].head).copy()
    po = (arm_o.matrix_world @ arm_o.pose.bones['b3'].head) - own.location + a.location
    check('C3 editing the clone\'s own action moves only the clone', (pa - po).length > 0.01,
          f'original b3 {tuple(round(v, 3) for v in pa)}, clone b3 {tuple(round(v, 3) for v in po)}')


# ---------------------------------------------------------------------------------------------------------- N ---
BIRDS = os.path.join(ROOT, 'eidoverse', 'assets', 'models')


def make_two_object_clip_glb(path):
    """One clip ('Spin') keying two objects (two slots of one action): a turntable and a lid."""
    sc = fresh()
    sc.render.fps = 24
    act = bpy.data.actions.new('Spin')
    for n, x in (('turntable', 0.0), ('lid', 1.0)):
        ob = cube(n, 0.3, loc=(x, 0, 0))
        ob.animation_data_create().action = act
        for f, a in ((1, 0.0), (25, math.pi)):
            ob.rotation_euler.z = a
            ob.keyframe_insert('rotation_euler', index=2, frame=f)
    bpy.ops.export_scene.gltf(filepath=path, export_format='GLB', export_animation_mode='ACTIONS')


def test_n():
    from eidoblend.harness import assets
    sc = fresh()
    sc.frame_start, sc.frame_end = 1, 48
    crow = assets.import_model(os.path.join(BIRDS, 'crow_bird_animated_corvid_raven_black_cawing_flying_walking.glb'))
    wren = assets.import_model(os.path.join(BIRDS, 'cactus_wren_bird_animated_desert_songbird_calling_hopping_walking.glb'))
    wc = sorted(assets.model_clips(wren))
    raw = sorted({s.action.name for o in assets.subtree(wren) if o.animation_data
                  for t in o.animation_data.nla_tracks for s in t.strips if s.action})
    check('N1 a second model keeps its own clip names (Blender made them unique as ' + ', '.join(raw[:2]) + ' ...)',
          'Walk' in wc and 'Walk.001' not in wc and 'Call' in wc, f'{wc}')
    first = assets.play_model_animations(crow, clip=0)
    assets.play_model_animations(crow, clip='all', weights={c: (1.0 if c in ('Walk', 'Caw') else 0.0)
                                                           for c in assets.model_clips(crow)})
    cc = sorted(assets.model_clips(crow))
    again = assets.play_model_animations(crow, clip=0)
    check('N2 after clip=\'all\' the baked mix is not a clip; clip=0 names the same clip before and after plays',
          not any(c.startswith('eido_mix') for c in cc) and len(cc) == 9 and first == again,
          f'clip 0 = {first} then {again}; {len(cc)} clips')
    own = assets.clone_model(crow, name='crow_own', independent_actions=True)
    got = assets.play_model_animations(own, clip='Peck')
    arm_o = next(o for o in assets.subtree(own) if o.type == 'ARMATURE')
    tr = [t for t in arm_o.animation_data.nla_tracks if not t.mute]
    check('N3 a clone with its own actions plays a clip by its own name, through its copy',
          got == ['Peck'] and tr and tr[-1].strips[0].action.name == 'Peck.crow_own', f'{[t.name for t in tr]}')
    glb = os.path.join(OUT, 'two_object_clip.glb')
    make_two_object_clip_glb(glb)
    sc = fresh()
    sc.render.fps = 24
    sc.frame_start, sc.frame_end = 1, 48
    root = assets.import_model(glb, name='spinner')
    act = assets.model_clips(root)['Spin']
    copy = assets.clone_model(root, name='spinner_copy')
    copy.location.x = 3.0
    got = assets.play_model_animations(copy, clip='Spin')
    sc.frame_set(13)
    turned = [o for o in assets.subtree(copy) if o.type == 'MESH' and abs(o.matrix_world.to_euler().z) > 0.5]
    check('N4 a clip that keys two objects (two slots) plays on a clone: each copy finds its original\'s slot',
          len(act.slots) == 2 and got == ['Spin'] and len(turned) == 2,
          f'{len(act.slots)} slots; turned at frame 13: {[o.name for o in turned]}')


# ---------------------------------------------------------------------------------------------------------- P ---
def test_p():
    from eidoblend.harness import post
    from eidoblend.look.post import chain
    sc = fresh()
    sc.render.resolution_x, sc.render.resolution_y = 320, 180
    cube('thing')
    cam = bpy.data.objects.new('cam', bpy.data.cameras.new('cam'))
    sc.collection.objects.link(cam)
    sc.camera = cam
    ov = post.make_overlay_layer(sc, fov=50)
    card = cube('card', 0.2)
    card.location = (0, 0, -1)
    ov.add(card)

    def hue(scene, tree):
        n = tree.nodes.new('CompositorNodeHueSat')
        n.inputs['Saturation'].default_value = 0.0
        return n

    def screen(scene, tree):
        return tree.nodes.new('CompositorNodeInvert')

    def flare(scene, tree):
        return tree.nodes.new('CompositorNodeBlur')
    ns = {'_bloom_params': {'strength': 0.4, 'radius': 0.6, 'threshold': 1.5}, '_auto_enhance_color_hook': hue,
          '_auto_enhance_screen_hook': screen, '_autoEnhancePreBloomHook': flare,
          '_ssr_params': {'thickness': 0.12, 'max_distance': 9}, '_ao_params': {'ao_radius': 0.33, 'quality': 'high'}}
    led = L.create_ledger()
    added = post.apply(sc, ns, led)
    order = [f'{s}:{n}' for s, n, _x in chain.stages(sc)]
    want = ['prebloom:pre_bloom_hook', 'bloom:bloom', 'under:color_hook', 'overlay:overlay', 'over:screen_hook']
    check('P1 the hooks land in the engine\'s order: pre-bloom, bloom, colour, overlay, screen', order == want,
          f'{order}')
    t = sc.compositing_node_group
    rl = [n for n in t.nodes if n.bl_idname == 'CompositorNodeRLayers' and n.scene == ov.scene]
    ao = next(n for _s, nm, n in chain.stages(sc) if nm == 'overlay')
    linked = rl and ao.inputs['Foreground'].is_linked and ao.inputs['Foreground'].links[0].from_node == rl[0]
    authored = ao.bl_idname == 'CompositorNodeGroup' and ao.node_tree and 'authored' in ao.node_tree.name
    check('P2 the overlay scene composites through its own Render Layers node, on the authored route (the over in '
          'display space: the HUD lands as drawn, as under the engine\'s untone-mapped output)', linked and authored
          and card.parent == ov.camera and card.name in ov.scene.objects and card.name not in sc.objects,
          f'{len(rl)} overlay render layer(s); stage {ao.bl_idname} {getattr(ao.node_tree, "name", "")}; '
          f'card parent {card.parent and card.parent.name}')
    g = next(n for _s, nm, n in chain.stages(sc) if nm == 'bloom')
    ee = sc.eevee
    check('P3 _bloom_params -> the Glare; _ssr_params / _ao_params -> EEVEE',
          abs(g.inputs['Strength'].default_value - 0.4) < 1e-6 and abs(g.inputs['Size'].default_value - 0.6) < 1e-6
          and abs(ee.ray_tracing_options.screen_trace_thickness - 0.12) < 1e-6 and abs(ee.fast_gi_distance - 0.33) < 1e-6
          and ee.fast_gi_step_count == 12, f'{added}')
    rec = [r for r in led.records if r['check'] == 'render.auto_enhance']
    check('P4 the digest records the stack, and what does not apply (max_distance)', rec and 'ignored' in
          rec[0]['message'] and 'screenHook' in rec[0]['message'], rec[0]['message'][:160] if rec else '')
    sc2 = fresh()
    sc2.eevee.use_raytracing = True
    led2 = L.create_ledger()
    post.apply(sc2, {'_no_auto_enhance': True, '_auto_enhance_color_hook': hue}, led2)
    check('P5 _no_auto_enhance: ray tracing and fast GI off, no runner stages',
          not sc2.eevee.use_raytracing and not sc2.eevee.use_fast_gi and not chain.stages(sc2), '')
    sc3 = fresh()

    def broken(scene, tree):
        raise ValueError('a typo in the hook')
    led3 = L.create_ledger()
    post.apply(sc3, {'_auto_enhance_color_hook': broken, '_auto_enhance_screen_hook': screen}, led3)
    rec = next((r for r in led3.records if r['check'] == 'render.auto_enhance'), None)
    check('P6 a hook that raises is reported (WARN) and skipped; the other hooks still go in, as the engine went on',
          rec and rec['outcome'] == 'WARN' and 'NOT installed' in rec['message']
          and [n for _s, n, _x in chain.stages(sc3)] == ['screen_hook'], rec['message'][-90:] if rec else 'missing')
    sc4 = fresh()
    cam4 = bpy.data.objects.new('cam', bpy.data.cameras.new('cam'))
    sc4.collection.objects.link(cam4)
    sc4.camera = cam4
    post.make_overlay_layer(sc4, authored=False)
    led4 = L.create_ledger()
    post.apply(sc4, {}, led4)
    st4 = next((n for _s, nm, n in chain.stages(sc4) if nm == 'overlay'), None)
    rec4 = next((r for r in led4.records if r['check'] == 'render.auto_enhance'), None)
    check('P7 make_overlay_layer(authored=False): a plain alpha-over in scene light that AgX grades, named so in the '
          'digest', st4 is not None and st4.bl_idname == 'CompositorNodeAlphaOver' and rec4
          and 'graded' in rec4['message'], f"{st4 and st4.bl_idname}; {rec4['message'][:120] if rec4 else 'missing'}")


# ---------------------------------------------------------------------------------------------------------- R ---
def test_r():
    from eidoblend.harness import render_common as RC
    sc = fresh()
    res = RC.setup_scene({}, sc)
    bpy.context.view_layer.update()
    kinds = sorted(l.data.type for l in res['lights'])
    cam = res['camera']
    fov = math.degrees(cam.data.angle_y)
    check('R1 setup_scene: the default rig (a sun + two points, ambient as world light), transparent background',
          kinds == ['POINT', 'POINT', 'SUN'] and sc.render.film_transparent, f'{kinds}')
    check('R2 the camera: fov 45 vertical at three (0, 1.2, 3) = Blender (0, -3, 1.2), aimed at the origin',
          abs(fov - 45) < 1e-4 and (cam.location - Vector((0, -3, 1.2))).length < 1e-6
          and abs((cam.matrix_world.to_3x3() @ Vector((0, 0, -1))).normalized().dot(
              (-cam.location).normalized()) - 1) < 1e-6, f'{tuple(cam.location)}')
    sc.frame_start, sc.frame_end = 1, 49
    sc.render.fps = 24
    path = [{'time': 0, 'position': [0, 1.6, 6], 'target': [0, 1, 0]}, {'time': 2, 'position': [3, 2, 4]}]
    n = RC.key_camera_path(cam, path, sc)
    worst = 0.0
    for f in (1, 7, 25, 37, 49):
        sc.frame_set(f)
        k = RC.get_camera_at_time((f - 1) / 24, path, [0, 1.2, 3], [0, 0, 0])
        from eidoblend import common
        worst = max(worst, (cam.matrix_world.translation - Vector(common.from_three(*k['position']))).length)
    check('R3 key_camera_path keys the smoothstep path on every frame (three coords in)', n == 49 and worst < 1e-5,
          f'{n} frames, worst {worst:.2e} m')
    notes = RC.ffmpeg_rate_control(sc, {'RENDER_CODEC': 'h264_nvenc', 'RENDER_CQ': '19'})
    ff = sc.render.ffmpeg
    check('R4 RENDER_CODEC / RENDER_CQ on Blender\'s writer (NVENC means H.264 here)',
          ff.codec == 'H264' and ff.constant_rate_factor == 'CUSTOM' and ff.custom_constant_rate_factor == 19,
          f'{notes}')
    notes = RC.ffmpeg_rate_control(sc, {'RENDER_BITRATE': '20M'})
    check('R5 RENDER_BITRATE: a constant target in kb/s', ff.constant_rate_factor == 'NONE' and ff.video_bitrate == 20000,
          f'{notes}')


# ---------------------------------------------------------------------------------------------------------- W ---
def test_w():
    from eidoblend.harness.html_mesh import El, html_mesh
    from eidoblend.harness.interior_window import create_interior_window_material
    sc = fresh()
    sc.frame_start, sc.frame_end = 1, 4
    scr = html_mesh(El('div', style='display: inline-block; padding: 10px; background: #102030; color: white; '
                                    'font: 40px Exo2', text='HELLO'), out_dir=os.path.join(OUT, 'html_frames'))
    w, h = scr.obj['eido_html_px']
    dims = scr.obj.dimensions
    check('W1 html_mesh: a plane 1 mm per pixel, its own image', abs(dims.x - w * 0.001) < 1e-6
          and abs(max(dims.y, dims.z) - h * 0.001) < 1e-6, f'{w}x{h} px -> {dims.x:.3f} x {max(dims.y, dims.z):.3f} m')
    live = html_mesh(lambda t: El('div', style='display: inline-block; padding: 8px; background: #000; color: #0f0; '
                                              'font: 30px SpaceMono-Regular', text=f'{t:05.2f}'),
                     out_dir=os.path.join(OUT, 'html_live'), name='clock_card')
    files = sorted(f for f in os.listdir(os.path.join(OUT, 'html_live')) if f.endswith('.png'))
    check('W2 a function of t is painted every frame (the engine\'s update())', len(files) >= 4, f'{files[:5]}')
    from PIL import Image
    im = Image.new('RGB', (64, 64), (200, 120, 60))
    p = os.path.join(OUT, 'room_flat.png')
    im.save(p)
    m = create_interior_window_material(room=p, depth=0.5, brightness=1.0)
    kinds = {n.bl_idname for n in m.node_tree.nodes}
    check('W3 interior window: unlit (Emission), tangent-space march (Tangent, Geometry), the room image',
          {'ShaderNodeEmission', 'ShaderNodeTangent', 'ShaderNodeNewGeometry', 'ShaderNodeTexImage'} <= kinds
          and not m.use_backface_culling, f'{len(m.node_tree.nodes)} nodes')


# ---------------------------------------------------------------------------------------------------------- L ---
def _linear(ob):
    """The object's own action's keys LINEAR (keyframe_insert ignores the preference)."""
    ad = ob.animation_data
    if ad and ad.action:
        from bpy_extras import anim_utils
        cb = anim_utils.action_get_channelbag_for_slot(ad.action, ad.action_slot)
        for fc in cb.fcurves:
            for kp in fc.keyframe_points:
                kp.interpolation = 'LINEAR'


def synth_rig(name, x, walk):
    """A 19-bone humanoid named as Rigify names its bones (hips, foot.L / foot.R, the IK controls foot_ik.L / .R), no
    VRM data: travels 3 m along +Y in 72 frames by its object location. walk=True keys each foot planted in world
    space for half of a 24-frame cycle and swinging 1 m for the other half, out of phase (one foot always down);
    walk=False leaves the feet riding along with the body (a slide)."""
    sc = bpy.context.scene
    arm = bpy.data.armatures.new(name)
    ob = bpy.data.objects.new(name, arm)
    sc.collection.objects.link(ob)
    bpy.context.view_layer.objects.active = ob
    bpy.ops.object.mode_set(mode='EDIT')
    names = ['hips', 'spine', 'chest', 'neck', 'head', 'upper_arm.L', 'upper_arm.R', 'forearm.L', 'forearm.R',
             'hand.L', 'hand.R', 'thigh.L', 'thigh.R', 'shin.L', 'shin.R', 'foot.L', 'foot.R', 'foot_ik.L', 'foot_ik.R']
    for k, n in enumerate(names):
        b = arm.edit_bones.new(n)
        side = -0.12 if n.endswith('.L') else (0.12 if n.endswith('.R') else 0.0)
        z = 0.08 if n.startswith('foot') else 0.4 + 0.08 * k
        b.head, b.tail = (side, 0.0, z), (side, 0.1, z)               # along +Y: pose location y moves world y
    bpy.ops.object.mode_set(mode='OBJECT')
    ob.location = (x, 0.0, 0.0)
    for f in range(1, 74):
        y = 3.0 * (f - 1) / 72
        ob.location.y = y
        ob.keyframe_insert('location', index=1, frame=f)
        for foot, phase in (('foot.L', 0.0), ('foot.R', 0.5)):
            pb = ob.pose.bones[foot]
            if walk:
                c = ((f - 1) / 24.0 + phase) % 1.0                      # 0..0.5 planted, 0.5..1 swinging
                cyc = math.floor((f - 1) / 24.0 + phase)
                world = cyc * 1.0 + (0.0 if c < 0.5 else (c - 0.5) * 2.0 * 1.0)
                pb.location.y = world - y
            pb.keyframe_insert('location', index=1, frame=f)
    _linear(ob)
    return ob


def test_l():
    """render_scene.mjs's locomotion and lipsync trackers (audits.motion), on claude.vrm walked by the characters
    family, the same VRM slid by its keyed location while a stationary clip plays, a mouth keyed and one never keyed,
    and Rigify-named rigs with no VRM data (the by-name foot finder)."""
    from eidoblend.characters import Ground, key_expression, load_clip, load_vrm, play_vrma_default, walk_path
    sc = fresh()
    sc.render.fps = 24
    walker = load_vrm('claude', name='walker', location=(0.0, 0.0, 0.0), rotation=90.0)
    rep = walk_path(walker, load_clip(walker, 'walk'), [(0.0, 0.0), (4.0, 0.0)], Ground(fn=lambda x, y: 0.0 * x), f0=1,
                    log=lambda *a: None)
    f0, f1 = rep['frames']
    slider = load_vrm('claude', name='slider', location=(0.0, 3.0, 0.0), rotation=90.0)
    play_vrma_default(slider, 'still_breathe')
    for f, x in ((f0, 0.0), (f1, 4.0)):
        slider.arm.location.x = x
        slider.arm.keyframe_insert('location', index=0, frame=f)
    _linear(slider.arm)
    key_expression(walker, 'aa', [(f0, 0.0), (f0 + 8, 0.8), (f0 + 16, 0.0)])
    sc.frame_start, sc.frame_end = f0, f1
    led = L.create_ledger()
    audits.motion(led, sc, {'fps': 24}, L.snapshot_policy({}))
    loco = {r['bodies'][0]: r for r in led.records if r['check'] == 'motion.locomotion' and r['bodies']}
    lips = {r['bodies'][0]: r for r in led.records if r['check'] == 'motion.lipsync'}
    w, s = loco.get('walker'), loco.get('slider')
    check('L1 walked by walk_path (4 m): PASS, the planted foot all but still',
          w and w['outcome'] == 'PASS' and w['metrics']['planted_foot_share'] < 0.25,
          f"{w and w['metrics']}; frames {f0}-{f1}")
    check('L2 slid 4 m by keyed location while still_breathe plays: WARN, RE-RENDER REQUIRED, feet ride along',
          s and s['outcome'] == 'WARN' and 'RE-RENDER REQUIRED' in s['message'] and s['metrics']['planted_foot_share'] > 0.9,
          f"{s and s['metrics']}")
    lw, ls = lips.get('walker'), lips.get('slider')
    check('L3 lipsync: the keyed aa moves the walker\'s mouth (PASS); the slider\'s never moves (WARN, advisory)',
          lw and lw['outcome'] == 'PASS' and ls and ls['outcome'] == 'WARN' and ls['class'] == 'REVIEW',
          f"{lw and lw['message'][:70]} | {ls and ls['message'][:60]}")
    led2 = L.create_ledger()
    audits.motion(led2, sc, {'fps': 24}, L.snapshot_policy({'_allowManualLocomotion': True}))
    s2 = next((r for r in led2.records if r['check'] == 'motion.locomotion' and r['bodies'] == ['slider']), None)
    led3 = L.create_ledger()
    audits.motion(led3, sc, {'fps': 24}, L.snapshot_policy({'_no_locomotion_check': True}))
    none3 = [r for r in led3.records if r['check'] == 'motion.locomotion']
    check('L4 _allow_manual_locomotion: sampled, disposition left (PASS INFO); _no_locomotion_check: not sampled',
          s2 and s2['outcome'] == 'PASS' and 'disposition' in s2['message'] and not none3, f"{s2 and s2['message'][:80]}")
    sc = fresh()
    sc.render.fps = 24
    sc.frame_start, sc.frame_end = 1, 73
    synth_rig('rig_walk', 0.0, True)
    synth_rig('rig_slide', 2.0, False)
    led = L.create_ledger()
    audits.motion(led, sc, {'fps': 24}, L.snapshot_policy({}))
    loco = {r['bodies'][0]: r for r in led.records if r['check'] == 'motion.locomotion' and r['bodies']}
    feet = audits.rig_feet(sc.objects['rig_walk'])
    check('L5 a Rigify-named rig: hips / foot.L / foot.R found by name (not the IK controls); its walk PASSES, its '
          'slide WARNS', feet == ('hips', 'foot.L', 'foot.R') and loco.get('rig_walk', {}).get('outcome') == 'PASS'
          and loco.get('rig_slide', {}).get('outcome') == 'WARN',
          f"{feet}; walk {loco.get('rig_walk', {}).get('metrics')}, slide {loco.get('rig_slide', {}).get('metrics')}")


# ---------------------------------------------------------------------------------------------------------- Q ---
def test_q():
    """scene_placement.js's seating on claude.vrm and the local corner chair: the seat pan (not the backrest's top),
    the chair's facing following its yaw, seat_on (instant and stand_to_sit), sit_on_ground, face_camera, emote,
    unseat, and the backrest check in run_placement_audits."""
    from eidoblend.characters import load_vrm
    from eidoblend.harness import assets
    from eidoblend.placement import (place_on, seat_on, sit_on_ground, unseat, emote, face_camera, find_seat_surface,
                                     chair_facing, check_hovering, run_placement_audits, clear_cache)
    from eidoblend.placement import seating as SE
    sc = fresh()
    sc.render.fps = 24
    sc.frame_start, sc.frame_end = 1, 120
    floor = cube('floor')
    floor.scale = (10, 10, 0.02)
    floor.location.z = -0.01
    chair = assets.import_model(os.path.join(BIRDS, 'corner_chair.glb'), name='chair')
    place_on(chair, floor, xy=(0.0, 0.0))
    lo, hi = assets.bounds(chair)
    seat = find_seat_surface(chair)
    f0 = chair_facing(chair, seat)
    chair.rotation_euler.z = math.radians(40)
    bpy.context.view_layer.update()
    clear_cache()
    f40 = chair_facing(chair)
    turn = math.degrees(math.atan2(math.sin(f40 - f0), math.cos(f40 - f0))) if f0 is not None and f40 is not None else None
    check('Q1 the seat pan, not the box top (the backrest); the chair opens to -Y and its facing turns with it',
          not seat['fallback'] and 0.35 < seat['z'] < 0.55 and seat['z'] < hi.z - 0.3 and f0 is not None
          and abs(math.degrees(f0)) < 12 and turn is not None and abs(turn - 40) < 3,
          f"pan {seat['z']:.3f} m (box top {hi.z:.3f}); facing {math.degrees(f0 or 0):.1f} deg, after a 40 deg turn "
          f"{turn if turn is None else round(turn, 1)} deg more")
    sitter = load_vrm('claude', name='sitter')
    z = seat_on(sitter, chair)
    sc.frame_set(13)
    bpy.context.view_layer.update()
    hp = SE._hips(sitter)
    under = SE._lowest_up(SE._body_bvh(sitter), [(hp.x, hp.y)], z - 0.6, 1.4)
    yaw = math.degrees(SE._heading(sitter.arm) - chair_facing(chair))
    yaw = (yaw + 180) % 360 - 180
    rep = [r for r in check_hovering(sc) if r['obj'] == sitter.arm]
    check('Q2 seat_on: her underside under the hips on the pan, pressed 2 cm in (as the engine rested it), facing '
          'out of the chair, marked seated, left alone by the hovering audit',
          under is not None and abs(under - (z - 0.02)) < 0.005 and abs(yaw) < 1 and sitter.arm.get('eido_seated')
          and sitter.arm.get('eido_seat') == chair.name and not rep,
          f'seat {z:.3f}, underside at the hips {under if under is None else round(under, 4)}; heading off the chair '
          f'{yaw:.2f} deg')
    SE._set_heading(sitter.arm, SE._heading(sitter.arm) + math.pi)
    bpy.context.view_layer.update()
    res = run_placement_audits(sc)
    back = [p for p in res.get('seated_facing', []) if p['obj'] == sitter.arm]
    SE._set_heading(sitter.arm, SE._heading(sitter.arm) - math.pi)
    check('Q3 a sitter turned 180 deg after seat_on is named facing the backrest (the engine\'s deferred check)',
          back and back[0]['deg'] > 110, f"{[(p['obj'].name, round(p['deg'])) for p in back]}")
    chair2 = assets.import_model(os.path.join(BIRDS, 'corner_chair.glb'), name='chair2')
    place_on(chair2, floor, xy=(2.0, 0.0))
    walker = load_vrm('claude', name='lowerer', location=(2.0, -1.0, 0.0))
    seat_on(walker, chair2, transition='stand_to_sit', t=1.0)
    s2 = find_seat_surface(chair2)
    fps = 24
    unders = []
    fc = int(1 + round((1.0 + 0.4 * 2.0) * fps))
    for f in (fc, fc + 8, fc + 16):
        sc.frame_set(f)
        unders.append(SE._lowest_up(SE._body_bvh(walker), SE._seat_grid(s2, 3), s2['z'] - 0.25, 0.6))
    sc.frame_set(118)
    end = SE._lowest_up(SE._body_bvh(walker), SE._seat_grid(s2, 6), s2['z'] - 0.25, 0.6)
    ok_desc = all(u is None or u >= s2['z'] - 0.006 for u in unders)
    check('Q4 seat_on(transition=\'stand_to_sit\'): the descent never sinks into the seat, and it ends on the pan',
          ok_desc and end is not None and abs(end - s2['z']) < 0.02 and walker.arm.get('eido_seated'),
          f"underside in the descent {[None if u is None else round(u, 3) for u in unders]}, at the end "
          f"{end if end is None else round(end, 3)} (pan {s2['z']:.3f})")
    chair3 = assets.import_model(os.path.join(BIRDS, 'corner_chair.glb'), name='chair3')
    place_on(chair3, floor, xy=(3.5, 0.0))
    looper = load_vrm('claude', name='looper', location=(3.5, -1.0, 0.0))
    seat_on(looper, chair3, transition='stand_to_sit', t=0.5, then='sitting_normal_chair')
    s3 = find_seat_surface(chair3)
    strips = [s for tr in looper.arm.animation_data.nla_tracks for s in tr.strips]
    fades = [round(s.blend_in, 1) for s in strips]
    hips, lows = [], []
    for f in (64, 69, 74, 90, 118):                                 # the sit-down's end, the crossfade, the loop
        sc.frame_set(f)
        hp = SE._hips(looper)
        hips.append(round((hp - Vector((s3['x'], s3['y'], hp.z))).length, 3))
        lows.append(SE._lowest_up(SE._body_bvh(looper), SE._seat_grid(s3, 3), s3['z'] - 0.25, 0.6))
    check('Q7 seat_on(transition, then=<loop>): the loop crossfades in (0.25 s) and her hips stay over the pan '
          'through it and after, her underside on the pan (the loop\'s hips sit over its root, 0.4 m forward of the '
          'sit-down\'s: left on that root she ended on the pan\'s front edge, in the air)',
          all(b >= 5.9 for b in fades) and max(hips) < 0.12 and all(u is not None and abs(u - s3['z']) < 0.02
                                                                    for u in lows[2:4]),
          f"blend-in frames {fades}; hips from the pan centre {hips} m; underside "
          f"{[None if u is None else round(u - s3['z'], 3) for u in lows]} m from the pan")
    # a raised stage and a chair turned 140 degrees on it: the pan is found 0.3 m up, the sit-down (into its loop)
    # ends facing out of the turned chair with her hips over its pan, and the floor sitter rests on the stage
    stage = cube('stage')
    stage.scale = (2.0, 2.0, 0.3)
    stage.location = (0.0, 4.0, 0.15)
    bpy.context.view_layer.update()
    chair4 = assets.import_model(os.path.join(BIRDS, 'corner_chair.glb'), name='chair4')
    chair4.rotation_euler.z = math.radians(140)
    place_on(chair4, stage, xy=(0.4, 4.2))
    s4 = find_seat_surface(chair4)
    up = load_vrm('claude', name='up_sitter', location=(0.4, 3.6, 0.3))
    seat_on(up, chair4, transition='stand_to_sit', t=0.5, then='sitting_normal_chair')
    sc.frame_set(100)
    bpy.context.view_layer.update()
    hp4 = SE._hips(up)
    off4 = math.hypot(hp4.x - s4['x'], hp4.y - s4['y'])
    u4 = SE._lowest_up(SE._body_bvh(up), [(hp4.x, hp4.y)], s4['z'] - 0.6, 1.4)
    d4 = math.degrees(SE._heading(up.arm) - chair_facing(chair4))
    d4 = (d4 + 180) % 360 - 180
    stage_sitter = load_vrm('claude', name='stage_floor_sitter')
    zs = sit_on_ground(stage_sitter, at=(-0.6, 3.6), ground=[stage])
    check('Q8 on a 0.3 m stage, a chair turned 140 deg: the pan found 0.3 m up; the sit-down into its loop ends '
          'facing out of the turned chair, hips over the pan, her underside under them on it; sit_on_ground finds '
          'the stage top', abs(s4['z'] - (0.3 + seat['z'])) < 0.03 and abs(d4) < 5 and off4 < 0.12
          and u4 is not None and -0.02 < u4 - s4['z'] < 0.05 and abs(zs - 0.3) < 0.005,
          f"pan {s4['z']:.3f} (floor chair {seat['z']:.3f}); heading {d4:.1f} deg off the chair's facing; hips "
          f"{off4:.2f} m from the pan's centre; underside {u4 if u4 is None else round(u4 - s4['z'], 3)} m; "
          f'stage sit at {zs:.3f}')
    floor_sitter = load_vrm('claude', name='floor_sitter')
    fz = sit_on_ground(floor_sitter, at=(-1.5, 0.5), ground=[floor])
    sc.frame_set(13)
    pts = [(x, y) for x in (-1.9, -1.7, -1.5, -1.3, -1.1) for y in (0.1, 0.3, 0.5, 0.7, 0.9)]
    # measured on the skin that bears her, as sit_on_ground measures it (seating._support_bvh: no spring chains, no
    # loose layer such as a coat's hem, which hangs into the floor under her, hidden by her)
    low_g = SE._lowest_up(SE._support_bvh(floor_sitter), pts, fz - 0.6, 1.5)
    check('Q5 sit_on_ground: the lowest underside of the skin that bears her 5 mm above the floor',
          low_g is not None and abs(low_g - (fz + 0.005)) < 0.01,
          f'floor {fz:.3f}, lowest {low_g if low_g is None else round(low_g, 4)}')
    cam = bpy.data.objects.new('cam', bpy.data.cameras.new('cam'))
    sc.collection.objects.link(cam)
    cam.location = (3.0, -5.0, 1.5)
    sc.camera = cam
    stander = load_vrm('claude', name='stander', location=(-3.0, 1.0, 0.0))
    face_camera(stander)
    st = emote(stander, 'cheer')
    bpy.context.view_layer.update()
    fwd = stander.arm.matrix_world.to_3x3() @ Vector((0, -1, 0))
    to_cam = (cam.location - stander.arm.matrix_world.translation)
    to_cam.z = 0
    unseat(sitter)
    check('Q6 face_camera turns her front to the camera; emote plays a looping clip; unseat clears the mark',
          fwd.normalized().dot(to_cam.normalized()) > 0.999 and st is not None and 'cheer' in st.action.name.lower()
          and st.repeat > 1 and 'eido_seated' not in sitter.arm, f'front . to camera {fwd.normalized().dot(to_cam.normalized()):.4f}; '
                                                              f'strip {st.action.name if st else None} x{st.repeat if st else 0:.0f}')


# ---------------------------------------------------------------------------------------------------------- V ---
def test_v():
    """preflight.sequencer: picture strips left in the film scene's sequencer would render instead of the 3D view."""
    sc = fresh()
    cube('thing')
    cam = bpy.data.objects.new('cam', bpy.data.cameras.new('cam'))
    sc.collection.objects.link(cam)
    sc.camera = cam
    cfg = {'fps': 24, 'duration': 1, 'width': 320, 'height': 180, 'frame_start': 1}
    sc.frame_start, sc.frame_end = 1, 24

    def rec():
        led = L.create_ledger()
        audits.preflight(led, sc, cfg)
        return next((r for r in led.records if r['check'] == 'preflight.sequencer'), None)
    before = rec()
    se = sc.sequence_editor_create()
    strips = se.strips if hasattr(se, 'strips') else se.sequences      # 'sequences' before Blender 4.4
    strips.new_effect(name='title_card', type='COLOR', channel=1, frame_start=1, length=24)
    sc.render.use_sequencer = True
    on = rec()
    sc.render.use_sequencer = False
    off = rec()
    check('V preflight.sequencer: silent with no strips, WARN for a colour strip that would replace the film, silent '
          'once use_sequencer is off', before is None and on and on['outcome'] == 'WARN' and off is None,
          on['message'][:90] if on else 'missing')


# ---------------------------------------------------------------------------------------------------------- S ---
def test_s():
    """The audits' x-sweep (no repair pass) visits exactly the pairs the engine's all-pairs loop reports."""
    import random
    import time
    from eidoblend.placement import audits as A
    sc = fresh()
    rnd = random.Random(11)
    for i in range(160):
        s = rnd.uniform(0.2, 1.2)
        ob = cube(f'c{i}', s, loc=(rnd.uniform(0, 30), rnd.uniform(0, 6), s / 2 + rnd.choice((0.0, 0.0, 0.3))))
        if i % 9 == 0:
            ob.scale = (1, 1, 0.01)                                # thin sheets for the z-fighting pass
    bpy.context.view_layer.update()
    for i in range(20):                                            # decals flush on some cubes' tops
        host = sc.objects[f'c{i * 7}']
        top = max((host.matrix_world @ Vector(c)).z for c in host.bound_box)
        d = cube(f'decal_{i}', 0.3, loc=(host.location.x, host.location.y, top + 0.0015))
        d.scale = (1, 1, 0.01)
    bpy.context.view_layer.update()
    t0 = time.perf_counter()
    cs = [(p['a'].name, p['b'].name) for p in A.check_clipping(sc)]
    zs = [(p['a'].name, p['b'].name, p['axis']) for p in A.check_z_fighting(sc)]
    t1 = time.perf_counter()
    orig = A._pairs
    A._pairs = lambda E, tol, exhaustive: orig(E, tol, True)
    try:
        ce = [(p['a'].name, p['b'].name) for p in A.check_clipping(sc)]
        ze = [(p['a'].name, p['b'].name, p['axis']) for p in A.check_z_fighting(sc)]
    finally:
        A._pairs = orig
    t2 = time.perf_counter()
    check('S the x-sweep reports exactly the all-pairs loop\'s clipping and z-fighting pairs, in its order',
          cs == ce and zs == ze and len(cs) > 5 and len(zs) > 3,
          f'{len(cs)} clipping, {len(zs)} z-fighting pairs; sweep {t1 - t0:.2f} s, all pairs {t2 - t1:.2f} s')


if __name__ == '__main__':
    for key, fn in (('AC', test_ac), ('H', test_h), ('K', test_k), ('M', test_m), ('C', test_c), ('P', test_p),
                    ('R', test_r), ('W', test_w), ('S', test_s), ('L', test_l), ('N', test_n), ('Q', test_q),
                    ('V', test_v)):
        if ONLY and key not in ONLY:
            continue
        try:
            fn()
        except Exception as e:                                      # noqa: BLE001
            traceback.print_exc()
            check(f'{key} (crashed)', False, f'{type(e).__name__}: {e}')
    n = sum(1 for _, ok in results if ok)
    print(f'\n{n}/{len(results)} checks passed', flush=True)
    os._exit(0 if n == len(results) else 1)
