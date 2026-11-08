"""The corridor (UNKNOWN FORCE verse 2) in Blender: build it, check the parts and the keyed update numerically, and
(--render) render the film's five cameras plus the states (doors open, the post typing, the cap on a head, a recount).

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
F.check('key light: 300 cd -> 300 x 4 pi / 683 W', abs(lit['key'].data.energy - 300 * 4 * math.pi / 683) < 1e-4,
        f"{lit['key'].data.energy:.4f} W")
F.check('key light: spot_size = 2 x 0.3 rad, blend 0.8',
        abs(lit['key'].data.spot_size - 0.6) < 1e-6 and abs(lit['key'].data.spot_blend - 0.8) < 1e-6)
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
F.check('beyond light: 1500 cd once open', abs(lit['beyond'].data.energy - 1500 * 4 * math.pi / 683) < 1e-3)
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

# ------------------------------------------------------------------------------------------- the cue sheet
s0, s1, s2, s3 = (COR.film_state(t) for t in (120.7, 131.55, 139.0, 116.0))
F.check("film_state: at 120.7 s the film's post waits untyped, doors shut, the cap on its cushion, the tally 49/39/12",
        s0['postText'] == COR.FILM_POST_TEXT and s0['post'] == 0.0 and s0['open'] == 0.0 and s0['capOn'] == 0.0
        and s0['tally'] == [49, 39, 12] and s0['lights'] == 1.0)
F.check('film_state: at 131.55 s the post is half typed (smoothstep 130.8-132.3)', abs(s1['post'] - 0.5) < 1e-9)
F.check('film_state: at 139 s the doors are half way to their 0.06 crack, the cap on her head',
        abs(s2['open'] - 0.03) < 1e-9 and s2['capOn'] == 1.0)
F.check('film_state: the blackout at 115.45-116.6 s dips the lights to 0.15', s3['lights'] == 0.15)
F.check('cue_at: 134 s is "in capital letters", on the postWall shot', COR.cue_at(134.0)['lyric'] == 'in capital letters'
        and COR.cue_at(134.0)['cam'] == 'postWall')
c112 = COR.film_cut(112.0)
F.check("film_cut: 112 s is the film's 'cap' shot, its orbit 0.1, her hidden", c112['cam'] == 'cap'
        and c112['move'] == {'orbit': 0.1} and not c112['singer'] and abs(c112['u'] - (112.0 - 111.5) / 3.9) < 1e-9)
p0, p1 = C.film_pose('door', 0.0, {'push': 1.2}), C.film_pose('door', 1.0, {'push': 1.2})
F.check('film_pose: a push moves the camera 1.2 m toward its target over the shot',
        abs(math.dist(p0['pos'], p1['pos']) - 1.2) < 1e-9 and p0['target'] == p1['target'])
q0, q1 = C.film_pose('cap', 0.0, {'orbit': 0.1}), C.film_pose('cap', 1.0, {'orbit': 0.1})
r0 = [a - b for a, b in zip(q0['pos'], q0['target'])]
r1 = [a - b for a, b in zip(q1['pos'], q1['target'])]
ang = math.atan2(r0[0], r0[2]) - math.atan2(r1[0], r1[2])
F.check('film_pose: an orbit turns 0.1 rad about the vertical through the target', abs(abs(ang) - 0.1) < 1e-9
        and abs(r0[1] - r1[1]) < 1e-12, f'{ang:.6f} rad')
# keyed over the repost: the film's post is set from the start and waits untyped until 130.8 s
REPOST = 'THE DEPARTMENT OF WAR POSTS IN CAPITAL LETTERS'
for f in range(1, 49):
    ts = 129.8 + (f - 1) / 24.0
    sc.frame_set(f)
    C.update(ts, COR.film_state(ts, cap_head=head, post_text=REPOST), frame=f)
C.keyer.finish()
sc.frame_set(1)
v_first, n_first = C.group['post_variant'], C.group['post_n']
sc.frame_set(48)                                             # 131.758 s
n_end = C.group['post_n']
want = round(len(REPOST) * COR._ease((131.7583333 - 130.8) / 1.5))
F.check('film keyed: the repost from its first frame, untyped until 130.8 s, then typed on the smoothstep',
        v_first >= 1.0 and n_first == 0 and n_end == want, f'variant {v_first}, post_n {n_first} -> {n_end} (want {want})')
# the film's cut as cameras: one per shot, keyed with its move, cut by markers
sc.frame_start, sc.frame_end = 1, 24 * 4
cams = C.make_cameras(frames=(1, 24 * 4), t0=108.0)           # 108.0-112.0 s: poll, door (push 0.6), cap (orbit 0.1)
names = [n for (_f, n) in sorted(cams)]
F.check("make_cameras: the film's shots 108-112 s are poll, door, cap, cut by timeline markers",
        names == ['poll', 'door', 'cap'] and len([m for m in sc.timeline_markers if m.camera]) >= 3, str(sorted(cams)))
e = C.apply_post(sc, frames=(1, 96))                          # bloom + aeropittura, the door's focal keyed per frame
U = e.uniforms['aeropittura']
foc = []
for f in (10, 40, 90):                                        # the poll, door and cap shots
    sc.frame_set(f)
    foc.append(tuple(round(v, 3) for v in U['focal'].default_value)[:2])
bl = next((n for _s, nm, n in __import__('eidoblend.look.post.chain', fromlist=['stages']).stages(sc) if nm == 'bloom'), None)
F.check("apply_post: bloom at the look's strength, threshold x SPEC; the aeropittura 'argue' with its focal following "
        "the cut", bl is not None and abs(bl.inputs['Strength'].default_value - 0.55) < 1e-6
        and abs(bl.inputs['Threshold'].default_value - 0.7 / 683) < 1e-7 and len(set(foc)) == 3
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
