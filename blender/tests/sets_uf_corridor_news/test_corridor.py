"""The gold corridor in Blender: build it, check the parts and the keyed update numerically, and (--render) render the
set's five cameras plus the states (doors open, the post typing, the cap on a head, a recount).

    cd <main checkout> && bash run_blender.sh <worktree>/blender/tests/sets_uf_corridor_news/test_corridor.py
    cd <main checkout> && HEAVY_VRAM_GB=4 bash work/claude_body/work/tmp/heavy.sh 12 bash run_blender.sh \
        <worktree>/blender/tests/sets_uf_corridor_news/test_corridor.py --render [door,corridorWide,...] [--states]
        [--samples 16] [--size 960x540] [--save]
"""
import math
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import _fixture as F  # noqa: E402

import bpy  # noqa: E402
from mathutils import Matrix, Vector  # noqa: E402

from eidoblend.sets.unknown_force import corridor as COR, cn_lib as CL  # noqa: E402

A = F.args()
RENDER = '--render' in A
STATES = '--states' in A
SAVE = '--save' in A
cams_arg = next((a for a in A if not a.startswith('--') and ',' in a or a in COR.CAMS), None)
CAMS = cams_arg.split(',') if cams_arg else list(COR.CAMS)
SAMPLES = int(A[A.index('--samples') + 1]) if '--samples' in A else 16
W, H = (int(v) for v in (A[A.index('--size') + 1] if '--size' in A else '960x540').split('x'))
OUT = F.OUT / 'corridor'
OUT.mkdir(parents=True, exist_ok=True)

sc = F.clean_scene()
F.render_settings(W, H, SAMPLES)
sc.frame_start, sc.frame_end = 1, 96
clock = F.timer()
C = COR.build(sc, {'postText': 'AMERICANISM, NOT EFFECTIVE ALTRUISM'})
print(f'[corridor] built in {clock():.1f}s', flush=True)
C.apply_look(sc)

# ------------------------------------------------------------------------------------------------- structure
objs = [o for o in C.collection.all_objects]
meshes = [o for o in objs if o.type == 'MESH']
tris = sum(sum(len(p.vertices) - 2 for p in o.data.polygons) for o in meshes)
F.check('built: meshes and triangles in the WebGPU range (42 meshes, 25k tris there)',
        30 <= len(meshes) <= 90 and 15000 <= tris <= 200000, f'{len(meshes)} meshes, {tris} tris')
for k in ('doors', 'postWall', 'poll', 'cap', 'capRest', 'capFit', 'patch', 'uniform', 'pedestal', 'cushion', 'plaque',
          'beyond', 'shafts', 'sconces', 'room', 'lights', 'uniforms', 'materials'):
    F.check(f'parts.{k}', k in C.parts and C.parts[k] is not None)
for k in ('key', 'doorL', 'doorR', 'plaque', 'beyond', 'poll', 'cap', 'uniform', 'screen', 'fill', 'hemi'):
    F.check(f'parts.lights.{k}', k in C.parts['lights'])
F.check('cams: door corridorWide postWall poll cap', set(C.cams) == {'door', 'corridorWide', 'postWall', 'poll', 'cap'})
F.check('focal: the door at (0, 5.2, -23.8) three = Blender (0, 23.8, 5.2)',
        all(abs(a - b) < 1e-9 for a, b in zip(C.focal_blender, (0.0, 23.8, 5.2))))
F.check('look: argue, exposure 1, bloom, fog null', C.look['name'] == 'argue' and C.look['fog'] is None
        and C.look['bloom']['strength'] == 0.55)
lit = C.parts['lights']
F.check('key light: 300 cd -> 300 x 4 pi W', abs(lit['key'].data.energy - 300 * 4 * math.pi) < 1e-3,
        f"{lit['key'].data.energy:.4f} W")
F.check('apply_look: AgX at 0 stops (three exposure 1, the lamps W = 4 pi cd)', sc.view_settings.view_transform == 'AgX'
        and abs(sc.view_settings.exposure) < 1e-9, f'{sc.view_settings.exposure:.3f}')
C.apply_look(sc, view_look=CL.ACES_LIKE_LOOK)
F.check("apply_look(view_look=ACES_LIKE_LOOK): the AgX look that follows the WebGPU frames' ACES tone",
        sc.view_settings.view_transform == 'AgX' and sc.view_settings.look == CL.ACES_LIKE_LOOK, sc.view_settings.look)
sc.view_settings.look = 'None'
F.check('key light: spot_size = 2 x 0.3 rad, blend 0.8',
        abs(lit['key'].data.spot_size - 0.6) < 1e-6 and abs(lit['key'].data.spot_blend - 0.8) < 1e-6)
misses = F.material_attr_misses(C.collection)
F.check('every mesh carries the uv maps and attributes its materials read (the pedestal\'s marble its UVBook)',
        not misses, str(misses[:4]))
ped = [o for o in C.parts['pedestal'].children if o.type == 'MESH' and C.materials['marble'] in list(o.data.materials)]
F.check('pedestal: the marble block has its own book-matched slab uv', len(ped) == 1 and 'UVBook' in ped[0].data.uv_layers)
# the door is 24 m behind her: the door leaves' hinge pivots at three z = ZD - 0.11 -> Blender y = 24.11
pl = C.parts['doors']['left']
F.check('door pivots at three (-3.2, 0, -24.11) -> Blender (-3.2, 24.11, 0)',
        (Vector(pl.matrix_world.translation) - Vector((-3.2, 24.11, 0))).length < 1e-4 or
        (COR._world_of(pl).translation - Vector((-3.2, 24.11, 0))).length < 1e-4)

# ---------------------------------------------------------------------------------------- the keyed update
head = bpy.data.objects.new('test_head', None)            # a stand-in normalized head bone: 1.45 m up, at her mark
C.collection.objects.link(head)
head.location = (0.0, 0.0, 1.45)


def state(t):
    return {'open': max(0.0, (t - 2.0) / 1.5), 'post': min(1.0, t / 1.5), 'capOn': min(1.0, max(0.0, t - 1.0)),
            'capHead': head, 'tally': [512000, 418000, 141000] if t > 3.0 else None}


C.animate(state, frames=(1, 96), scene=sc)
sc.frame_set(1)
F.check('post: frame 1 shows 0 characters', C.group['post_n'] == 0, f"post_n {C.group['post_n']}")
sc.frame_set(19)
n19 = C.group['post_n']
F.check('post: typing at 0.75 s shows half the text', abs(n19 - round(len(C.parts['postWall']['state']['text']) * 0.5)) <= 1,
        f'post_n {n19}')
sc.frame_set(96)
F.check('post: typed in full by 1.5 s, cursor off', C.group['post_n'] == len(C.parts['postWall']['state']['text'])
        and C.group['post_cursor'] == 0.0)
ang = C.parts['doors']['left'].rotation_euler[2]
F.check('doors: open eased to 93 deg at t = 3.5 s', abs(ang - 1.62) < 1e-3, f'{math.degrees(ang):.1f} deg')
F.check('beyond light: 1500 cd once open', abs(lit['beyond'].data.energy - 1500 * 4 * math.pi) < 1e-2)
F.check('shafts: shown once the doors part', not C.parts['shafts'].hide_render)
sc.frame_set(1)
F.check('shafts: hidden while shut', C.parts['shafts'].hide_render)
F.check('poll: a recount added a second board, keyed on at t > 3', len(C.parts['poll']['variants'].items) == 2)
sc.frame_set(96)
F.check('poll: the recount shows at the end', C.group['poll_variant'] == 1.0)
cap = C.parts['cap']
dg = bpy.context.evaluated_depsgraph_get()
sc.frame_set(96)
cw = cap.matrix_world.translation
fit = Vector(CL.b3(C.parts['capFit']['pos']))
F.check('cap: on the head at capOn = 1 (head + fit offset)', (cw - (head.location + fit)).length < 1e-3,
        f'{tuple(round(v, 3) for v in cw)}')
sc.frame_set(1)
rest = COR._world_of(C.parts['capRest']).translation
F.check('cap: on the cushion at capOn = 0', (cap.matrix_world.translation - rest).length < 1e-3)
sc.frame_set(37)                                             # capOn = 0.5 eased: half way, lifted 0.45 m by the arc
mid = cap.matrix_world.translation
F.check('cap: mid-flight rides the 0.45 m arc', mid.z > max(rest.z, (head.location + fit).z) + 0.2, f'z {mid.z:.3f}')
fc = [f for f in C.group.animation_data.action.layers[0].strips[0].channelbags[0].fcurves] \
    if C.group.animation_data and hasattr(C.group.animation_data.action, 'layers') else []
interp = {f.data_path: {k.interpolation for k in f.keyframe_points} for f in fc}
F.check('keys: uniforms LINEAR, post_n CONSTANT', interp.get('["open"]') == {'LINEAR'}
        and interp.get('["post_n"]') == {'CONSTANT'}, str({k: v for k, v in interp.items() if k in ('["open"]', '["post_n"]')}))
cv = C.parts['postWall'].canvas
F.check('postWall.canvas: the shown post, drawn in full (2048 x 931)', (cv.width, cv.height) == (2048, 931))

# ------------------------------------------------------------------ a repost on your own clock, keyed
# a new post set from the first keyed frame waits untyped until its typing starts at 1.0 s, then types over 0.5 s
REPOST = 'A NEW POST, IN CAPITAL LETTERS'
for f in range(1, 49):
    ts = (f - 1) / 24.0
    sc.frame_set(f)
    C.update(ts, {'postText': REPOST, 'post': max(0.0, min(1.0, (ts - 1.0) / 0.5))}, frame=f)
C.keyer.finish()
sc.frame_set(1)
v_first, n_first = C.group['post_variant'], C.group['post_n']
sc.frame_set(31)                                             # t = 1.25 s: half typed
n_mid = C.group['post_n']
F.check('repost keyed: the new post from its first frame, untyped until 1.0 s, half typed at 1.25 s',
        v_first >= 1.0 and n_first == 0 and n_mid == COR._js_round(len(REPOST) * 0.5),
        f'variant {v_first}, post_n {n_first} -> {n_mid}')
vi = C.parts['postWall'].set_text('ANOTHER POST', name='MINISTRY OF ANYTHING', meta='just now',
                                  stats=('1', '2', '3', '4'))
pst = C.parts['postWall']['state']
F.check("set_text: a new name, meta and stats on the card make a new variant", vi >= 2 and pst['text'] == 'ANOTHER POST'
        and pst['name'] == 'MINISTRY OF ANYTHING' and pst['stats'] == ['1', '2', '3', '4'], f'variant {vi}')
# the sets' contract reads the result as a dict too
F.check("contract: C['parts'] is C.parts, C['update'] the update, keys() holds group, parts, update, dispose, cams",
        C['parts'] is C.parts and C['update'] is C.update and {'group', 'parts', 'update', 'dispose', 'cams'}
        <= set(C.keys()) and C.get('nothing') is None)
F.check("depthWrite false: the door's shafts and seam add every layer (Transparency Overlap)",
        all(bpy.data.materials[n].use_transparency_overlap for n in ('corridor_shafts', 'corridor_door_seam')))
# opts plaque: two lines of your own engraved over the door (the ink mask: where the black enamel fills the letters)
ink0 = COR._plaque_relief(C.lib)['ink_canvas'].pixels()[..., 0].astype(float) / 255
ink1 = COR._plaque_relief(C.lib, ('Ministry of', 'Anything'))['ink_canvas'].pixels()[..., 0].astype(float) / 255
F.check('opts plaque: other words engraved, both lines inked, the transom the same size', ink1.shape == ink0.shape
        and ink1[150:280].mean() > 0.05 and ink1[340:460].mean() > 0.05 and abs(ink1 - ink0).mean() > 0.02,
        f'ink {ink0.mean():.3f} -> {ink1.mean():.3f}')
# the suggested look, its focal keyed through the scene's camera as markers cut between three of the set's cameras
sc.frame_start, sc.frame_end = 1, 96
for f, name in ((1, 'poll'), (25, 'door'), (60, 'cap')):
    m = sc.timeline_markers.new(f'cut_{name}', frame=f)
    m.camera = C.camera(name, sc, set_active=False)
e = C.apply_post(sc, frames=(1, 96))                          # bloom + aeropittura, the door's focal keyed per frame
U = e.uniforms['aeropittura']
foc = []
for f in (10, 40, 90):                                        # the poll, door and cap cameras
    sc.frame_set(f)
    foc.append(tuple(round(v, 3) for v in U['focal'].default_value)[:2])
bl = next((n for _s, nm, n in __import__('eidoblend.look.post.chain', fromlist=['stages']).stages(sc) if nm == 'bloom'), None)
F.check("apply_post: bloom at the look's strength and threshold; the aeropittura 'argue' with its focal following "
        "the cut", bl is not None and abs(bl.inputs['Strength'].default_value - 0.55) < 1e-6
        and abs(bl.inputs['Threshold'].default_value - 0.7 * CL.SPEC) < 1e-7 and len(set(foc)) == 3
        and abs(U['strokes'].default_value - 0.9) < 1e-6, str(foc))

if SAVE:
    bpy.ops.wm.save_as_mainfile(filepath=str(OUT / 'corridor_test.blend'), copy=True)

# --------------------------------------------------------------------------------------------------- renders
if RENDER:
    sc.frame_set(1)
    for name in CAMS:
        C.camera(name, sc)
        C.set_u('pix', CL.pix_of(sc))
        F.render_still(OUT / f'corridor_{name}_shut_f1.png', sc)
    if STATES:
        sc.frame_set(96)                                       # doors open, the post typed, the cap on the head
        for name in ('door', 'corridorWide'):
            C.camera(name, sc)
            F.render_still(OUT / f'corridor_{name}_open_f96.png', sc)
        sc.frame_set(19)
        C.camera('postWall', sc)
        F.render_still(OUT / 'corridor_postWall_typing_f19.png', sc)
        sc.frame_set(96)
        C.camera('poll', sc)
        F.render_still(OUT / 'corridor_poll_recount_f96.png', sc)
F.summary()
