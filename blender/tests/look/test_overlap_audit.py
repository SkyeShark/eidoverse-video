"""tests/look/test_overlap_audit.py: the overlap probe and the audit ledger (no render).

  - a box sunk 3 cm into a table top: probe_overlaps reports it CUTTING ~30 mm deep; push_clear lifts it until it
    rests (a touch, not a cut); a cup standing exactly on the table is a touch; a box clear of everything is no hit
  - the ledger: camera records, an inventory with a Geometry Nodes scatter (virtual leaves), declarations as custom
    properties (one blanket, one single), a global disable, and the digest written to out/audit/scene.audit.{json,txt}
    bash run_blender.sh blender/tests/look/test_overlap_audit.py
"""
import os
import sys

import bpy
from mathutils import Vector

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import fixtures as FX                                       # noqa: E402

from eidoblend.look import audit                             # noqa: E402
from eidoblend.look import camera as C                       # noqa: E402
from eidoblend.look import camera_audit as CA                # noqa: E402
from eidoblend.look import overlap                           # noqa: E402

RESULTS = []


def check(name, ok, detail=''):
    RESULTS.append((name, bool(ok)))
    print(f"[check] {'PASS' if ok else 'FAIL'} {name}{': ' + str(detail) if detail else ''}", flush=True)


def cube(name, centre, size):
    bpy.ops.mesh.primitive_cube_add(size=1.0, location=centre)
    o = bpy.context.object
    o.name = name
    o.scale = size
    bpy.ops.object.transform_apply(location=False, rotation=False, scale=True)    # (all three default to True)
    return o


sc = FX.new_scene(frames=(1, 24))
# a 10 cm top (z 0.66 .. 0.76): depth is the distance to the nearest way out, so a 3 cm sink in a thinner slab would
# read as its distance to the slab's underside
table = cube('table_top', (0, 0, 0.71), (1.2, 0.8, 0.10))
sunk = cube('box_sunk', (0.3, 0, 0.76 + 0.05 - 0.03), (0.1, 0.1, 0.1))   # bottom at 0.73: 3 cm into the top
cup = cube('cup_resting', (-0.3, 0, 0.76 + 0.05), (0.08, 0.08, 0.1))      # bottom exactly on the top
free = cube('box_clear', (2.0, 0, 0.5), (0.2, 0.2, 0.2))

h = overlap.probe_overlaps(sc, sunk)
print(overlap.format_overlaps(h, 'box_sunk'), flush=True)
check('a box sunk 3 cm cuts the table ~30 mm deep', h and h[0]['object'] == 'table_top' and not h[0]['touch']
      and abs(h[0]['depth'] - 0.03) < 0.004, [(x['object'], round(x['depth'], 4), x['touch']) for x in h])
h = overlap.probe_overlaps(sc, cup)
print(overlap.format_overlaps(h, 'cup_resting'), flush=True)
check('a cup standing on the table is a touch, not a cut', all(x['touch'] for x in h), [(x['object'], round(x['depth'], 5)) for x in h])
h = overlap.probe_overlaps(sc, free)
check('a box clear of everything has no hits', not h, h)
moved = overlap.push_clear(sc, sunk, direction=(0, 0, 1))
bpy.context.view_layer.update()
bottom = C.world_bounds(sunk)[0].z
h = overlap.probe_overlaps(sc, sunk)
check('push_clear lifts the box to rest on the table', moved is not None and abs(bottom - 0.76) < 0.004
      and all(x['touch'] for x in h), f'moved {moved:.4f} m, bottom at {bottom:.4f} m')

# ---- the ledger
cam = C.make_camera('cam', lens=35, scene=sc)
C.hold(sc, cam, (1, 24), (1.5, -2.0, 1.4), (0, 0, 0.8))
C.add_shot(sc, 'table', 1, cam)
bpy.ops.mesh.primitive_plane_add(size=4, location=(0, 0, 0))
floor = bpy.context.object
floor.name = 'floor'
# a Geometry Nodes scatter of the cup on the floor: its instances are virtual leaves
src = bpy.data.collections.new('scatter_src')
sc.collection.children.link(src)
pebble = cube('pebble', (0, 0, 0), (0.05, 0.05, 0.03))
for c in list(pebble.users_collection):
    c.objects.unlink(pebble)
src.objects.link(pebble)
bpy.context.view_layer.layer_collection.children['scatter_src'].exclude = True
mod = floor.modifiers.new('scatter', 'NODES')
ng = bpy.data.node_groups.new('pebbles', 'GeometryNodeTree')
ng.interface.new_socket('Geometry', in_out='INPUT', socket_type='NodeSocketGeometry')
ng.interface.new_socket('Geometry', in_out='OUTPUT', socket_type='NodeSocketGeometry')
gi, go = ng.nodes.new('NodeGroupInput'), ng.nodes.new('NodeGroupOutput')
dist = ng.nodes.new('GeometryNodeDistributePointsOnFaces')
dist.inputs['Density'].default_value = 3.0
ci = ng.nodes.new('GeometryNodeCollectionInfo')
ci.inputs['Collection'].default_value = src
iop = ng.nodes.new('GeometryNodeInstanceOnPoints')
join = ng.nodes.new('GeometryNodeJoinGeometry')
ng.links.new(gi.outputs[0], dist.inputs['Mesh'])
ng.links.new(dist.outputs['Points'], iop.inputs['Points'])
ng.links.new(ci.outputs[0], iop.inputs['Instance'])
ng.links.new(gi.outputs[0], join.inputs[0])
ng.links.new(iop.outputs[0], join.inputs[0])
ng.links.new(join.outputs[0], go.inputs[0])
mod.node_group = ng
# declarations: one on a single object, one blanket over a parent with two children; a global disable
table['no_clipping_check'] = True
rig = bpy.data.objects.new('prop_rig', None)
sc.collection.objects.link(rig)
for o in (sunk, cup):
    o.parent = rig
rig['allow_intersect'] = True
sc['no_motion_check'] = True
bpy.context.view_layer.update()

led = audit.Ledger()
for r in CA.camera_motion_audit(sc) + CA.framing_audit(sc, subject=table):
    led.record(r)
inv = audit.build_inventory(sc)
decl = audit.map_declarations(sc, inv)
for r in audit.coverage_records(decl, inv, audit.snapshot_policy(sc)):
    led.record(r)
out = os.path.join(FX.OUT, 'audit')
js, txt = led.write(os.path.join(out, 'scene'), meta={'run_id': 'test_overlap_audit', 'status': 'test'})
digest = open(txt, encoding='utf-8').read()
print(digest, flush=True)
n_inst = sum(1 for l in inv['leaves'] if l['instancer'])
check('the inventory counts the scatter instances as virtual leaves', n_inst > 5, f'{n_inst} instance leaves of '
      f"{len(inv['leaves'])}")
check('a blanket declaration over two bodies WARNs', any(r['check'] == 'coverage.allow_intersect' and r['outcome'] == 'WARN'
                                                       for r in led.records))
check('a single-object declaration is recorded as an exception', any(r['check'] == 'coverage.no_clipping_check'
                                                                     and r['disposition'] == 'DECLARED_EXCEPTION'
                                                                     for r in led.records))
check('a global disable is recorded as SKIPPED, not passed', any(r['check'] == 'motion.envelope' and r['outcome'] == 'SKIPPED'
                                                                 for r in led.records))
check('the ledger is not clean (exceptions were declared)', not led.is_clean())
check('the digest is written from the ledger', 'AUDIT DIGEST' in digest and 'REVIEW GATE' in digest and os.path.exists(js))
bad = [n for n, ok in RESULTS if not ok]
print(f"[overlap-audit] {'PASS' if not bad else 'FAIL'}: {len(RESULTS) - len(bad)}/{len(RESULTS)}", flush=True)
