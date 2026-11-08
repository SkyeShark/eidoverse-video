"""The Speak & Spell homage (props/voice_machines/speakspell.py): build on its stand and without, the VFD text and
redraws, the keyed power / gain / grille glow, and probe renders at true scale.

    cd <main checkout> && bash run_blender.sh <worktree>/blender/tests/voice_machines_b/test_speakspell.py         # checks
    HEAVY_VRAM_GB=4 bash work/claude_body/work/tmp/heavy.sh 12 bash run_blender.sh <this> --render             # + stills
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import _stage as S  # noqa: E402

import bpy  # noqa: E402


def run(render=False):
    sc = S.fresh_scene(frames=(1, 48))
    from eidoblend.props.voice_machines import speakspell as SS
    ss = SS.build(text='love', screen_dir=str(S.OUT / 'speakspell_screens'))
    P = ss.parts
    S.check('speakspell: parts', all(P[k] is not None for k in ('toy', 'body', 'card', 'stand', 'display', 'speaker')))
    S.check('speakspell: text upper case, 8 characters at most', P['display'].text == 'LOVE')
    P['display'].set_text('Spelling bee')
    S.check('speakspell: set_text truncates to 8', P['display'].text == 'SPELLING')
    S.check('speakspell: 14-segment table', SS.seg_list(SS.GLYPH['R']) == ['a', 'b', 'e', 'f', 'g1', 'g2', 'm']
            and SS.seg_list(SS.GLYPH['W']) == ['b', 'c', 'e', 'f', 'k', 'm'])
    # keyed playback: power on, a syllable, the text changes, power off
    for f in range(1, 49):
        t = ss.frame_at(0) and (f - 1) / 24.0
        v = 0.9 if 10 <= f <= 20 else 0.0
        st = {'power': 0.0 if f > 40 else 1.0, 'voice': v}
        if f == 24:
            st['text'] = 'daisy'
        ss.update((f - 1) / 24.0, st)
    sc.frame_set(15)
    g = ss.group
    S.check('speakspell: gain flares with the voice (keyed)', abs(g['gain'] - (1 + 0.55 * 0.9)) < 1e-6, f"{g['gain']:.3f}")
    S.check('speakspell: the grille glows with the voice', abs(g['speaker'] - 0.9) < 1e-6)
    sc.frame_set(44)
    S.check('speakspell: power off: VFD dark and the grille silent', g['power'] == 0.0 and g['speaker'] == 0.0)
    sc.frame_set(30)
    S.check('speakspell: the new text was drawn once, at its frame', P['display'].text == 'DAISY' and
            P['display'].draws == 3, f"{P['display'].draws} drawings")
    lo, hi = S.bounds([g] + list(g.children_recursive))
    size = hi - lo
    S.check('speakspell: on its stand, footprint about index.js (0.18 x 0.10 x 0.26 m)',
            all(abs(a - b) < 0.02 for a, b in zip(size, (0.18, 0.10, 0.26))) and abs(lo.z) < 0.002,
            f'{size.x:.3f} x {size.y:.3f} x {size.z:.3f}, bottom {lo.z * 1000:.1f} mm')
    cx, cy = (lo.x + hi.x) / 2, (lo.y + hi.y) / 2
    S.check("speakspell: centre matches index.js's (0.0, 0.03 in Blender axes)", abs(cx) < 0.01 and abs(cy - 0.03) < 0.01,
            f'({cx:.3f}, {cy:.3f})')
    P['display'].set_text('hi', align='right', frame=31)
    S.check("speakspell: set_text(align='right') redraws the tube at its frame", P['display'].text == 'HI'
            and P['display']._align == 'right' and P['display'].draws == 4, f"{P['display'].draws} drawings")
    P['display'].set_text('DAISY', align='left', frame=32)
    up = SS.build(text='hello', stand=False, name='speakspell_upright', screen_dir=str(S.OUT / 'speakspell_screens'))
    up.group.location = (0.32, 0.0, 0.0)
    bpy.context.view_layer.update()
    lo2, hi2 = S.bounds([up.group] + list(up.group.children_recursive))
    S.check('speakspell: stand=False stands on its edge at z = 0, no stand', up.parts['stand'] is None and abs(lo2.z) < 1e-4,
            f'bottom {lo2.z * 1000:.2f} mm, height {(hi2.z - lo2.z) * 1000:.0f} mm')
    S.dispose_leaves_nothing('speakspell', lambda: SS.build(text='spell', name='speakspell_3',
                                                            screen_dir=str(S.OUT / 'speakspell_screens_3')),
                             lambda p: p.dispose(files=True))
    S.check('speakspell: dispose(files=True) removes its VFD frames too', not (S.OUT / 'speakspell_screens_3').exists()
            or not any((S.OUT / 'speakspell_screens_3').rglob('*.png')))

    if render:
        from PIL import Image
        from eidoblend.props.voice_machines import voder as K
        c = K.Ctx2D(1024, 209, ss=2)
        SS.draw_vfd(c, 1024, 209, 'LOVE')
        c.image().save(S.OUT / 'speakspell_vfd_art_LOVE.png')
        S.floor(sc, color=(0.42, 0.40, 0.37))
        S.wall(sc, y=0.35, color=(0.30, 0.31, 0.33))
        S.studio(sc, (0.15, 0.0, 0.12), dist=1.0, key=60, scale=0.4)
        cam = S.camera(sc, (0.42, -0.62, 0.30), (0.14, 0.0, 0.12), lens=50)
        S.render(S.OUT / 'speakspell_pair_f015.png', frame=15)
        sc.frame_set(15)
        lo, hi = S.bounds([P['display'].mesh])
        c = (lo + hi) / 2
        S.look_from(cam, (c.x, c.y - 0.16, c.z + 0.03), tuple(c), lens=70)
        S.render(S.OUT / 'speakspell_vfd_close_f015.png', frame=15)
        S.render(S.OUT / 'speakspell_vfd_close_poweroff_f044.png', frame=44)
    return S.summary('speakspell')


if __name__ == '__main__':
    sys.exit(1 if run(render='--render' in sys.argv) else 0)
