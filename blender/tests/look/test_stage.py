"""tests/look/test_stage.py: the stage rig in EEVEE. A proscenium arch, front-of-house profiles on a pipe hung from the
house ceiling, pars on an overhead pipe, a dark fixture (lamp=False), haze, and claude_robot.vrm centre stage.

Judge: each beam coming out of a fixture you can see (no light from nowhere), the beams in the haze, lenses glowing at
their light's level (the amber par keyed 600 W -> 60 W between frames 12 and 36: its lens dims with it, through the
driver), the dark fixture's dark lens, and clears(): a narrow FOH profile passes under the arch, a wide one paints it
(rendered alone in its own still so the painted arch shows).
    bash run_blender.sh blender/tests/look/test_stage.py --stage build
    HEAVY_VRAM_GB=4 bash work/claude_body/work/tmp/heavy.sh 12 bash run_blender.sh <this> --stage render
"""
import json
import math
import os
import sys

import bpy
from mathutils import Vector

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import fixtures as FX                                       # noqa: E402

from eidoblend.look import camera as C                       # noqa: E402
from eidoblend.look import camera_audit as CA                # noqa: E402
from eidoblend.look import exposure as EX                    # noqa: E402
from eidoblend.look import frame_stats as FS                 # noqa: E402
from eidoblend.look import lighting as L                     # noqa: E402
from eidoblend.look import probe as P                        # noqa: E402
from eidoblend.look import render_settings as RS             # noqa: E402
from eidoblend.look.stage_rig import create_stage_rig        # noqa: E402

A = FX.args()
STAGE = FX.arg(A, '--stage', 'all')
OUT = os.path.join(FX.OUT, 'stage')
BLEND = os.path.join(OUT, 'stage.blend')
os.makedirs(OUT, exist_ok=True)
REPORT = {}


def mat(name, colour, rough=0.8, metal=0.0):
    m = bpy.data.materials.new(name)
    m.use_nodes = True
    p = m.node_tree.nodes['Principled BSDF']
    p.inputs['Base Color'].default_value = (*colour, 1)
    p.inputs['Roughness'].default_value = rough
    p.inputs['Metallic'].default_value = metal
    return m


def box(name, lo, hi, m, col):
    lo, hi = Vector(lo), Vector(hi)
    me = bpy.data.meshes.new(name)
    v = [(x, y, z) for x in (lo.x, hi.x) for y in (lo.y, hi.y) for z in (lo.z, hi.z)]
    me.from_pydata(v, [], [(0, 1, 3, 2), (4, 6, 7, 5), (0, 4, 5, 1), (2, 3, 7, 6), (0, 2, 6, 4), (1, 5, 7, 3)])
    me.materials.append(m)
    ob = bpy.data.objects.new(name, me)
    col.objects.link(ob)
    return ob


def build():
    sc = FX.new_scene(fps=24, frames=(1, 48))
    col = bpy.data.collections.new('theatre')
    sc.collection.children.link(col)
    boards = mat('stage_boards', (0.09, 0.07, 0.055), rough=0.45)
    black = mat('black_paint', (0.02, 0.02, 0.02), rough=0.7)
    arch_m = mat('arch_plaster', (0.55, 0.5, 0.42), rough=0.85)
    velvet = mat('velvet', (0.25, 0.015, 0.02), rough=0.9)
    # the stage (y from -1, the arch line, to +4), the house floor in front, the arch, the back curtain, house walls
    box('stage', (-5, -1.0, -1.0), (5, 4.5, 0.0), boards, col)
    box('house_floor', (-6, -12, -1.4), (6, -1.0, -1.0), black, col)
    box('arch_l', (-5.0, -1.3, -1.0), (-3.0, -1.0, 5.5), arch_m, col)
    box('arch_r', (3.0, -1.3, -1.0), (5.0, -1.0, 5.5), arch_m, col)
    box('arch_top', (-3.0, -1.3, 3.2), (3.0, -1.0, 5.5), arch_m, col)
    box('curtain', (-5, 4.0, 0.0), (5, 4.3, 5.5), velvet, col)
    box('house_ceiling', (-6, -12, 4.6), (6, -1.3, 4.8), black, col)
    # haze over the stage and the house in front of it (beams read in it)
    hz = box('haze', (-4.9, -8.0, -0.99), (4.9, 3.95, 4.55), mat('haze_unused', (1, 1, 1)), col)
    hm = bpy.data.materials.new('haze')
    hm.use_nodes = True
    nt = hm.node_tree
    nt.nodes.clear()
    vol = nt.nodes.new('ShaderNodeVolumePrincipled')
    vol.inputs['Density'].default_value = 0.02
    out = nt.nodes.new('ShaderNodeOutputMaterial')
    nt.links.new(vol.outputs['Volume'], out.inputs['Volume'])
    hz.data.materials.clear()
    hz.data.materials.append(hm)
    # the world: a dark theatre
    w = bpy.data.worlds.new('theatre')
    sc.world = w
    if w.node_tree is None:
        w.use_nodes = True
    w.node_tree.nodes['Background'].inputs['Strength'].default_value = 0.0
    # me, centre stage, standing in the stock idle
    arm, _m = FX.robot(sc, walk=False, start=(0.0, 1.0, 0.0), clip='idle')
    arm.rotation_euler = (0, 0, 0)            # facing the house (-Y in Blender: the VRM's own facing)
    # the rig
    rig = create_stage_rig(sc, ceiling=4.6)
    foh = rig.pipe(x0=-2.4, x1=2.4, z=4.38, y=-4.9)
    over = rig.pipe(x0=-3.0, x1=3.0, z=4.5, y=0.6, rods=False)
    chest = (0.0, 1.0, 1.25)
    k1 = rig.fixture(type='profile', pipe=foh, x=-1.4, target=chest, kelvin_k=4200, watts=1400, angle=0.16,
                     penumbra=0.35, name='foh_key_l')
    k2 = rig.fixture(type='profile', pipe=foh, x=1.4, target=chest, kelvin_k=4200, watts=1000, angle=0.16,
                     penumbra=0.35, name='foh_key_r')
    wide = rig.fixture(type='profile', pipe=foh, x=0.0, target=(0, 1.0, 0.8), kelvin_k=4200, watts=1600, angle=0.62,
                       penumbra=0.3, name='foh_wide')
    wide.light.hide_render = True             # rendered only in its own still
    pars = [rig.fixture(type='par', pipe=over, x=x, target=(x * 0.4, 1.6, 0.0), color=c, watts=w_, angle=0.3,
                        penumbra=0.6, name=n)
            for x, c, w_, n in ((-2.0, (0.25, 0.4, 1.0), 700, 'par_blue'), (-0.7, (1.0, 0.55, 0.15), 600, 'par_amber'),
                                (0.7, (1.0, 0.2, 0.55), 500, 'par_magenta'))]
    dark = rig.fixture(type='profile', pipe=foh, x=0.7, target=chest, lamp=False, name='foh_dark')
    # the right key profile keyed 1000 W -> 100 W between frames 30 and 42 (the reverse shot sees its lens dim)
    k2.light.data.energy = 1000
    k2.light.data.keyframe_insert('energy', frame=30)
    k2.light.data.energy = 100
    k2.light.data.keyframe_insert('energy', frame=42)
    REPORT['clears'] = {f.name: rig.clears(f, y=-1.0, z=3.2) for f in (k1, k2, wide)}
    for k, v in REPORT['clears'].items():
        print(f"[stage] clears {k}: {'passes under the arch' if v['ok'] else 'PAINTS THE ARCH'} (cone edge at "
              f"{v['edge_z']:.2f} m where the arch opening is 3.20 m)", flush=True)
    REPORT['lights'] = L.log_lights(sc)
    cams = bpy.data.collections.new('cameras')
    sc.collection.children.link(cams)
    house = C.make_camera('cam_house', lens=40, fstop=4.0, collection=cams, scene=sc)
    C.hold(sc, house, (1, 24), (0.4, -6.5, 1.5), (0.0, 1.0, 1.55))
    C.focus_on(sc, house, (1, 24), chest)
    C.add_shot(sc, 'house', 1, house)
    # the reverse: from the stage beside me, up at the front-of-house pipe (the lenses face this way)
    rev = C.make_camera('cam_reverse', lens=30, fstop=4.0, collection=cams, scene=sc)
    C.hold(sc, rev, (25, 48), (1.1, 1.3, 1.4), (0.0, -4.9, 4.1))
    C.focus_on(sc, rev, (25, 48), (0.0, -4.9, 4.1))
    C.add_shot(sc, 'reverse', 25, rev)
    # not a shot: from the back of the house, the whole arch in frame (for the wide FOH's still)
    far = C.make_camera('cam_far', lens=28, collection=cams, scene=sc)
    C.hold(sc, far, (1, 48), (0.0, -10.5, 1.9), (0.0, 1.0, 1.9))
    RS.apply_auto_enhance(sc, 'film', volumes={'tile': '8', 'samples': 64})
    REPORT['framing'] = CA.framing_audit(sc, subject=arm, frames=[12])
    bpy.ops.wm.save_as_mainfile(filepath=BLEND)
    print(f'[stage] saved {BLEND}', flush=True)


def render():
    bpy.ops.wm.open_mainfile(filepath=BLEND, load_ui=False)
    sc = bpy.context.scene
    RS.apply_auto_enhance(sc, 'probe', volumes={'tile': '8', 'samples': 64})
    arm = bpy.data.objects['claude']

    def subject_box(f):
        sc.frame_set(f)
        pb = CA.projected_box(sc, sc.camera, arm)
        return pb['box'] if pb and pb['box'] else None
    sc.frame_set(12)
    ae = EX.auto_expose(sc, os.path.join(OUT, 'sweep'), region=subject_box(12), key='region')
    REPORT['exposure'] = {'set': ae['exposure'], 'reason': ae['pick']['reason'], 'ceiling': ae['pick']['ceiling']}
    rows = P.render_stills(sc, frames=[12, 30, 42], out_dir=OUT, name='stage')
    # the wide FOH profile alone, from the back of the house: its cone paints the arch
    for o in sc.objects:
        if o.type == 'LIGHT':
            o.hide_render = o.name != 'foh_wide_light'
    keep = [m.camera for m in sc.timeline_markers]
    for m in sc.timeline_markers:
        m.camera = None
    sc.camera = bpy.data.objects['cam_far']
    P.render_still(sc, os.path.join(OUT, 'stage_wide_foh_alone.png'), 12)
    for c, m in zip(keep, sc.timeline_markers):
        m.camera = c
    for o in sc.objects:
        if o.type == 'LIGHT':
            o.hide_render = o.name == 'foh_wide_light'
    REPORT['stills'] = [{k: r[k] for k in ('frame', 'path', 'seconds', 'highlights')} for r in rows]
    FS.sheet([rows[0]['path'], os.path.join(OUT, 'stage_wide_foh_alone.png'), rows[1]['path'], rows[2]['path']],
             os.path.join(OUT, 'stage_sheet.jpg'), cols=2, tile=800,
             labels=['frame 12 from the house', 'the wide FOH alone: paints the arch',
                     'frame 30 reverse: right key 1000 W', 'frame 42 reverse: right key 100 W (its lens dims)'])


if STAGE in ('build', 'all'):
    build()
if STAGE in ('render', 'all'):
    render()
with open(os.path.join(OUT, f'report_{STAGE}.json'), 'w', encoding='utf-8') as fh:
    json.dump(REPORT, fh, indent=1, default=str)
print(f'[stage] {STAGE} done', flush=True)
