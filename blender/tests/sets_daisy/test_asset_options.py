"""tests/sets_daisy/test_asset_options.py: the DAISY sets as assets for a piece of your own.

The film tests drive the sets on the DAISY bridge's clock. A new piece wants a look, held, on its own clock, and the
set's parts with its own timing and words. This checks, numerically (no GPU):
  - the funeral's named looks (STATES, state_u, update(t, {'state': ...}), animate(frames, state=...)): the light state
    each one holds, its keys, and t running while u holds (the candles flicker);
  - beats= re-times the set's own clock (the looks follow it); eulogy= types your own words, or none;
  - the corner's looks (the laptop, the screens painted as they stand, the dark room, the spark in flight).
With --render it then builds both whole sets and renders one still per look (the funeral's from one wide view down
the room, without the words; the corner's through its own camera at that look) into out/looks/.

    cd <main checkout> && bash run_blender.sh <worktree>/blender/tests/sets_daisy/test_asset_options.py
    cd <main checkout> && bash run_blender.sh <worktree>/blender/tests/sets_daisy/test_asset_options.py --render
    (--render: a GPU job, about 6 GB of VRAM under a 24 GB memory cap; on a shared machine queue it with EIDO_GPU_WRAP:
    blender/tests/_where.py)
"""

import math
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import _common as C                                        # noqa: E402

import bpy                                                  # noqa: E402

from eidoblend.look import camera as LC                     # noqa: E402
from eidoblend.sets.daisy import corner as CO               # noqa: E402
from eidoblend.sets.daisy import funeral as FU              # noqa: E402

A = C.args()
sc = C.clean_scene(30, (1, 60))


def at_frame(f, ob, prop):
    sc.frame_set(f)
    return float(ob[prop])


# ======================================================================================================== funeral
F = FU.build(bridge=False, crowd=False, raven=False)
C.check('funeral: every named look has a place on the clock', sorted(FU.STATES) == sorted(
    ['bridge', 'vigil', 'failing', 'dark', 'phones', 'erupt', 'golden']) and all(
    0.0 <= F.state_u(s) <= F.beats['end'] for s in FU.STATES), ', '.join(f'{s} {F.state_u(s):.2f}' for s in FU.STATES))
looks = {}
for s in FU.STATES:
    F.update(0.0, {'state': s})
    looks[s] = {k: F.U[k] for k in ('power', 'golden', 'phone_fill', 'burst_lvl', 'raise')}
C.check('funeral: the looks hold what they say (vigil lit, failing sags, dark and phones black, erupt bursts, golden)',
        looks['vigil']['power'] == 1.0 and 0.4 < looks['failing']['power'] < 0.95 and looks['dark']['power'] == 0.0
        and looks['dark']['phone_fill'] == 0.0 and looks['phones']['phone_fill'] > 0.5 and looks['phones']['power'] == 0
        and looks['erupt']['burst_lvl'] > 0.5 and looks['erupt']['raise'] > 0.3 and looks['golden']['golden'] == 1.0,
        '; '.join(f"{s} pw {v['power']:.2f} phones {v['phone_fill']:.2f} burst {v['burst_lvl']:.2f} gold {v['golden']:.2f}"
                  for s, v in looks.items()))
try:
    F.update(0.0, {'state': 'noon'})
    C.check('funeral: an unknown look names the known ones', False)
except KeyError as e:
    C.check('funeral: an unknown look names the known ones', 'golden' in str(e), str(e)[:80])
n = F.animate((1, 60), state='golden')
root = F.kit.root
cand = F.candle_lights[0]
e = []
for f in (2, 30, 59):
    sc.frame_set(f)
    e.append(cand.data.energy)
C.check('funeral: animate(state=golden) holds the look while t runs (the candles still flicker)',
        all(abs(at_frame(f, root, 'golden') - 1.0) < 1e-6 for f in (1, 30, 60)) and max(e) - min(e) > 1e-4,
        f'{n} keys; candle W {", ".join(f"{x:.4f}" for x in e)}')
F.dispose()

# beats= : the set's own clock, re-timed; the looks follow it
G = FU.build(bridge=False, crowd=False, raven=False, beats={'lights_on': 24.0, 'erupt': 21.0})
C.check('funeral: beats= re-times the clock and the looks follow (golden at lights_on + 2)',
        abs(G.state_u('golden') - 26.0) < 1e-9 and G.power(5.0) == 1.0 and abs(G.beats['erupt'] - 21.0) < 1e-9
        and FU.BEATS['erupt'] == 14 * FU.BAR, f"golden at {G.state_u('golden'):.2f}, erupt {G.beats['erupt']}")
G.update(0.0, {'u': 26.0})
C.check('funeral: re-timed, u 26 is golden', G.U['golden'] == 1.0, f"golden {G.U['golden']:.2f}")
G.dispose()

# eulogy= : none, or words of your own
H = FU.build(bridge=False, crowd=False, raven=False, eulogy=False)
H.update(0.0, {'state': 'phones'})
C.check('funeral: eulogy=False builds the room without the words', H.text_lines == [] and H.cursor is None
        and H.U['text_lvl'] == 0.0 and not [o for o in H.kit.top.all_objects if o.name.startswith('funeral:eulogy')])
H.dispose()
mine = ['we were HERE', 'and the lights STAYED on', 'say it LOUDER']
J = FU.build(bridge=False, crowd=False, raven=False, eulogy=mine)
J.update(0.0, {'u': J.beats['lines'][1][2] - 0.5})
C.check('funeral: eulogy= types your own lines (one quad per glyph, typed on the clock)',
        [L['n_chars'] for L in J.text_lines] == [len(s) + 1 for s in mine]
        and J.text_lines[1]['obj']['head'] > 0, f"{[L['n_chars'] for L in J.text_lines]}, line 2 head "
        f"{J.text_lines[1]['obj']['head']:.1f}")
J.dispose()
try:
    FU.build(bridge=False, crowd=False, raven=False, eulogy=mine + ['a fourth'])
    C.check('funeral: more lines than beats is refused with the fix in the message', False)
except ValueError as e:
    C.check('funeral: more lines than beats is refused with the fix in the message', 'beats' in str(e), str(e)[:90])

# ========================================================================================================= corner
R = CO.build(camp=False)
C.check('corner: every named look has a place on the clock', sorted(CO.STATES) == sorted(
    ['evening', 'late', 'camp', 'chant', 'spark', 'dark']) and CO.area_at(R.state_u('camp')) == 'camp'
    and CO.mood_at(R.state_u('late')) == 'late' and CO.mood_at(R.state_u('dark')) == 'dark',
    ', '.join(f'{s} {R.state_u(s):.2f}' for s in CO.STATES))
lid = R.room['lid']
R.update(0.0, {'state': 'late'})
open_x = lid.rotation_euler.x
R.update(0.0, {'state': 'evening'})
C.check('corner: late opens the laptop, evening closes it', abs(open_x) > 1.0 and abs(lid.rotation_euler.x) < 1e-6
        and R.U['screen'] == 0.0, f'lid {math.degrees(open_x):.0f} deg open')
n = R.animate((1, 40), state='dark')
sc.frame_set(20)
C.check('corner: animate(state=dark) keys the dark room (the window dimmed, the laptop shut)',
        abs(R.kit.root['win'] - 0.16) < 1e-6 and abs(R.kit.root['screen']) < 1e-6, f'{n} keys')
R.animate((1, 40), state='late')
img = R.room['chat_node'].image
C.check('corner: a held look paints the screens as they stand there', img is not None and img.name.startswith(
    'corner:chat_held') and R.room['nb_node'].image.name.startswith('corner:notebook_held'), img.name if img else '')
R.update(0.0, {'state': 'spark'})
C.check('corner: the spark look flies the spark (its core lit, between the lamp and her flower)',
        R.U['spark_core'] > 0.5 and not R.spark['core'].hide_render, f"core {R.U['spark_core']:.2f}")
R.dispose()


# ============================================================================================ the looks, rendered
def render_looks(name, build, looks, cam_of, post=False):
    """one still per look: each look keyed on a frame of its own (t running), through cam_of(set, look) -> (pos, target,
    fov) set-local Blender axes. A set with a room probe bakes it first."""
    out = os.path.join(C.OUT, 'looks')
    os.makedirs(out, exist_ok=True)
    C.probe_look(sc)
    sc.eevee.shadow_pool_size = '2048'
    S = build()
    fx = S.post.apply(sc) if post else None
    keys = None
    for i, look in enumerate(looks):
        k = S.update(1.0 + 0.37 * i, {'state': look}, frame=i + 1)
        if fx is not None:
            S.post.drive(fx, S.state_u(look), k)
        keys = k if keys is None else keys.merge(k)
    keys.finish()
    bpy.context.view_layer.update()
    if hasattr(S, 'bake_probes'):
        sc.frame_start, sc.frame_end = 1, len(looks)
        print(f'[looks] {name}: probe baked {S.bake_probes(sc)}', flush=True)
    M = S.kit.root.matrix_world
    for i, look in enumerate(looks):
        pos, tgt, fov = cam_of(S, look)
        cam = LC.make_camera(f'looks:{name}_{look}', fov=fov, scene=sc)
        cam.matrix_world = LC.look_matrix(M @ pos, M @ tgt)
        p = os.path.join(out, f'{name}_{look}.png')
        sc.camera = cam
        ok, dt = C.render_still(sc, i + 1, p)
        st = C.image_stats(p) if ok else {'mean': 0, 'max': 0, 'magenta': 1}
        C.check(f'{name} look {look} renders', ok and st['magenta'] < 0.001 and st['max'] > 0.05,
                f"mean {st['mean']:.3f} ({dt:.1f} s)")
    S.dispose()


if 'render' in A['flags']:
    WIDE = (FU.V(0.0, 3.4, 9.5), FU.V(0.0, 1.9, -4.0), 58.0)       # down the room from the stage end (shot 10's view)

    def funeral_cam(S, look):
        if look == 'bridge':
            c = S.camera(S.state_u('bridge'))
            return c['pos'], c['target'], c['fov']
        return WIDE

    def corner_cam(S, look):
        c = S.camera(S.state_u(look))
        return c['pos'], c['target'], c['fov']
    render_looks('funeral', lambda: FU.build(eulogy=False), list(FU.STATES), funeral_cam, post=True)
    render_looks('corner', lambda: CO.build(), list(CO.STATES), corner_cam)
sys.exit(1 if C.summary('test_asset_options') else 0)
