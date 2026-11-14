"""The Teletype ASR-33 (props/voice_machines/teletype.py): build, printing (layout, the character buffer, the type
box, the line feed), the keyboard and lamps, and probe renders at true scale.

    cd <main checkout> && bash run_blender.sh <worktree>/blender/tests/voice_machines_b/test_teletype.py           # checks
    bash run_blender.sh <this> --render                                                                        # + stills
    (--render: a GPU job; on a shared machine queue it with EIDO_GPU_WRAP: blender/tests/_where.py)
"""
import json
import math
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import _stage as S  # noqa: E402

import bpy  # noqa: E402

ELIZA = ('MEN ARE ALL ALIKE.\nIN WHAT WAY?\nTHEY\'RE ALWAYS BUGGING US ABOUT SOMETHING OR OTHER.\n'
         'CAN YOU THINK OF A SPECIFIC EXAMPLE?\nWELL, MY BOYFRIEND MADE ME COME HERE.\n'
         'YOUR BOYFRIEND MADE YOU COME HERE\nI WAS A MIRROR NAMED ELIZA\n')


def run(render=False):
    sc = S.fresh_scene(frames=(1, 96))
    from eidoblend.props.voice_machines import teletype as TT
    tt = TT.build(buffer_dir=str(S.OUT / 'teletype_buffer'))
    P = tt.parts
    S.check('teletype: every GLB role has a material', not tt.missing_roles, ', '.join(sorted(tt.missing_roles)))
    S.decals_drawn('teletype', [im for im in tt.made['images'] if im is not tt.buffer.image])
    was = tt.seated_decals.get('teletype_logo', (0.0, 0.0))[0]
    S.decals_on_panels('teletype', tt, 3, was > 0.009,
                       f'; the TT monogram, {was * 1000:.1f} mm off the sloped cover in the GLB, lies on it')
    S.check('teletype: 53 keys (52 legends + the space bar)', len(P['keys']) == 53)
    S.check('teletype: parts', all(P[k] is not None for k in ('printhead', 'platen', 'roll', 'keyboard', 'lamps', 'body')))
    seeds = sorted(round(o.data.attributes['aSeed'].data[0].value) for o in
                   list(P['printhead'].children) + list(P['roll'].children) if 'aSeed' in o.data.attributes)
    S.check('teletype: the runtime parts carry their seeds (K.mesh: type box 40-42, roll 43)', seeds == [40, 41, 42, 43],
            str(seeds))

    def tinted(m, colour):
        """the paper material holds the paper tint (paper_color in linear) as a constant"""
        want = TT.K.lin(colour)
        return any(n.bl_idname == 'ShaderNodeVectorMath' and all(abs(a - b) < 1e-6 for a, b in zip(n.inputs[0].default_value, want))
                   for n in m.node_tree.nodes)

    def check_and_dispose(t2):
        pm = t2.parts['paper'].mesh.data.materials[0]
        S.check('teletype: paper_color (opts.paperColor) tints the paper', tinted(pm, 0xe9e4d6) and not tinted(pm, 0xf0dfa4))
        d = Path(t2.buffer.dir)
        t2.dispose(files=True)
        S.check('teletype: dispose(files=True) removes the buffer folder too', not d.exists(), str(d))
    S.dispose_leaves_nothing('teletype', lambda: TT.build(name='teletype_2', paper_color=0xe9e4d6, power=0.0,
                                                          glb=str(Path(TT.K.PACK) / 'teletype.glb'),
                                                          buffer_dir=str(S.OUT / 'teletype_buffer_2')), check_and_dispose)

    # the printing rules (teletype.js clean/layout)
    text = TT.clean(ELIZA)
    S.check('teletype: upper case, every "?" stripped', '?' not in text and text == text.upper())
    long = 'A' * 100 + '\nB'
    L = TT.layout(TT.clean(long), 200)
    S.check('teletype: 72 columns then wrap; \\n starts a line', [len(x) for x in L] == [72, 28, 1])

    # parity of the jitter hash (JS Math.sin in doubles) and so of the buffer bytes
    dump = S.OUT / 'parity_js.json'
    if dump.exists():
        J = json.loads(dump.read_text())
        if 'tty_hash' in J:
            worst = max(abs(TT.js_hash(n) - h) for n, h in J['tty_hash'])
            S.check('teletype: hash(n) equals the engine (Math.sin) on the buffer inputs', worst < 1e-9, f'{worst:.2e}')
        if 'tty_buffer' in J:
            import numpy as np
            lines = TT.layout(TT.clean(J['tty_buffer']['text']), 10 ** 9)
            got = TT.buffer_bytes(lines)
            want = np.array(J['tty_buffer']['bytes'], np.uint8).reshape(TT.ROWS, TT.BUF_W, 4)
            S.check('teletype: character buffer bytes equal teletype.js writeBuffer', np.array_equal(got, want),
                    f'{int((got != want).sum())} bytes differ')

    # print over the film: one character every 2 frames, keyed
    n_total = len(text)
    frames = range(1, 97)
    for f in frames:
        t = tt.time_at(f)
        n = max(0.0, (f - 4) * 0.5)
        tt.update(t, {'text': ELIZA, 'nChars': n, 'voice': 0.6 if (f // 12) % 2 else 0.0, 'power': 1.0}, frame=f)
    S.check('teletype: the buffer was redrawn only when the print changed', 0 < tt.buffer_writes <= n_total + 2,
            f'{tt.buffer_writes} PNG writes over 96 frames')
    files = sorted(Path(tt.buffer.dir).glob('*_[0-9][0-9][0-9][0-9].png'))
    S.check('teletype: one buffer file per frame (holds hard-linked)', len(files) >= 96, f'{len(files)} files')
    # decode the frame-60 buffer back to text: the glyphs it holds are the layout's
    from PIL import Image
    import numpy as np
    f = 60
    n60 = int(math.floor((f - 4) * 0.5))
    im = np.asarray(Image.open(tt.buffer._file(f - sc.frame_start + 1)))[::-1]
    lines60 = TT.layout(text, n60)
    row = (len(lines60) - 1) % TT.ROWS
    s = ''.join(chr(32 + g) if a else ' ' for g, a in zip(im[row, :len(lines60[-1]), 0], im[row, :len(lines60[-1]), 3]))
    S.check('teletype: frame 60 buffer decodes to the line being typed', s.rstrip() == lines60[-1].rstrip(), repr(s))
    # line feed and type box at a fractional count on '\n'
    i_nl = text.index('\n')
    st = P['paper'].set_text(ELIZA, i_nl + 0.35, frame=200, key=False)
    feed = TT.sstep01(0.35 / 0.7)
    S.check('teletype: on "\\n" the paper feeds smoothly', abs(tt.line.value - (st['line'] + feed)) < 1e-9,
            f"line {tt.line.value:.4f}")
    st = P['paper'].set_text(ELIZA, 5.5, frame=201, key=False)
    want_x = TT.col_x(min(TT.COLS - 1, 5 + TT.sstep01(0.5))) - TT.CHAR * 0.5
    S.check('teletype: the type box travels to the next column', abs(P['printhead'].location.x - want_x) < 1e-7,
            f"{P['printhead'].location.x:.5f} vs {want_x:.5f} {st}")
    # keyed: the type box moves along the platen between frames 10 and 14 (n = 3 -> 5, one line)
    sc.frame_set(10)
    x10 = P['printhead'].matrix_world.translation.x
    sc.frame_set(14)
    x14 = P['printhead'].matrix_world.translation.x
    S.check('teletype: the type box is keyed (two columns in four frames)', abs((x14 - x10) - 2 * TT.CHAR) < 1e-6,
            f'{x10:.4f} -> {x14:.4f}')
    # the struck key goes down: the last printed character's key
    sc.frame_set(30)
    n30 = (30 - 4) * 0.5
    last = text[int(n30) - 1]
    kidx = TT.KEY_OF.get(last, -1)
    dz = P['keys'][kidx].location.length if kidx >= 0 else 0
    S.check(f'teletype: the struck key ({last!r}) is down at frame 30', kidx >= 0 and dz > 0.002, f'{dz * 1000:.2f} mm')
    w0 = tt.buffer_writes
    tt.update(tt.time_at(97), {'power': 0.0, 'voice': 0.0}, frame=97)
    sc.frame_set(97)
    S.check('teletype: power 0 (keyed) darkens the call-control lamps; an update without text prints nothing',
            tt.group['power'] == 0.0 and tt.buffer_writes == w0)
    sc.frame_set(96)
    lo, hi = S.bounds([tt.group] + list(tt.group.children_recursive))
    size = hi - lo
    S.check('teletype: footprint about index.js (0.60 x 0.76 x 1.07 m)',
            all(abs(a - b) < 0.05 for a, b in zip(size, TT.MACHINE['footprint'])), f'{size.x:.3f} x {size.y:.3f} x {size.z:.3f}')
    cx, cy = (lo.x + hi.x) / 2, (lo.y + hi.y) / 2
    feet = S.rest_height(tt)
    S.check("teletype: centre matches index.js's (0.0, 0.12 in Blender axes); the pedestal's sled feet stand on z = 0 "
            '(the power cord runs into the floor)', abs(cx - TT.MACHINE['center'][0]) < 0.02
            and abs(cy - TT.MACHINE['center'][1]) < 0.02 and abs(feet) < 0.002,
            f'({cx:.3f}, {cy:.3f}), feet {feet * 1000:.1f} mm, cord {lo.z * 1000:.1f} mm')

    if render:
        from PIL import Image as PI
        from eidoblend.props.voice_machines import voder as K
        for nm, w, h, fn in (('keys', 1024, 1024, TT._draw_keys), ('glyphs', 1024, 384, TT._draw_glyphs),
                             ('tag', 512, 216, TT._draw_tag), ('band', 1024, 72, TT._draw_band),
                             ('logo', 256, 128, TT._draw_logo)):
            c = K.Ctx2D(w, h, ss=3)
            fn(c, w, h)
            bg = PI.new('RGBA', (w, h), (90, 90, 90, 255))
            bg.alpha_composite(c.image())
            bg.save(S.OUT / f'teletype_art_{nm}.png')
        S.studio(sc, (0, 0.0, 0.8), dist=2.2, key=120)      # the voder's exposure (key / dist^2 about 25)
        S.floor(sc)
        S.wall(sc, y=1.0, color=(0.33, 0.31, 0.28))
        cam = S.camera(sc, (0.95, -1.55, 1.35), (0.0, 0.0, 0.78), lens=35)
        S.render(S.OUT / 'teletype_three_quarter_f096.png', frame=96)
        S.look_from(cam, (0.05, -0.32, 1.12), (0.0, 0.04, 0.93), lens=50)
        S.render(S.OUT / 'teletype_paper_close_f096.png', frame=96)
        S.look_from(cam, (0.12, -0.42, 0.98), (0.03, -0.12, 0.76), lens=45)
        S.render(S.OUT / 'teletype_keyboard_close_f030.png', frame=30)
        # an extreme close-up of the type: the glyph atlas magnified, the cell seams the four-tap filter avoids
        sc.frame_set(96)
        x0 = -TT.PAPER_W / 2 + TT.MARGIN + 8 * TT.CHAR
        S.look_from(cam, (x0, -0.065, 0.90), (x0, 0.079, 0.868), lens=100)
        S.render(S.OUT / 'teletype_type_macro_f096.png', frame=96)
        # from the front, above the keys: the TT monogram on the cover's sloped face (the GLB stood it 9-16 mm off)
        S.look_from(cam, (-0.02, -0.40, 0.93), (-0.11, -0.04, 0.81), lens=55)
        S.render(S.OUT / 'teletype_cover_logo_f096.png', frame=96)
    return S.summary('teletype')


if __name__ == '__main__':
    sys.exit(1 if run(render='--render' in sys.argv) else 0)
