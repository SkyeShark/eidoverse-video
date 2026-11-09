"""Two ASR-33s in one film (props/voice_machines/teletype.py): each keeps its own paper. Built with one scene ctx and
the default name, as a museum or a newsroom would build them, each prints its own text into its own character buffer
(the frames are named after each machine's root, which Blender keeps unique). Also the guide's Blender-relative
buffer_dir ('//screens/tty') in an unsaved and a saved blend. A probe render shows both papers side by side.

    cd <main checkout> && bash run_blender.sh <worktree>/blender/tests/voice_machines_b/test_two_teletypes.py       # checks
    HEAVY_VRAM_GB=4 bash work/claude_body/work/tmp/heavy.sh 12 bash run_blender.sh <this> --render             # + still
"""
import shutil
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import _stage as S  # noqa: E402

import bpy  # noqa: E402

TEXT_A = 'MEN ARE ALL ALIKE.\nIN WHAT WAY?\n'
TEXT_B = 'BUT YOUR DAISY IS MY DAISY TOO.\nTELL ME MORE\n'
OUT_DIR = S.OUT / 'two_teletypes'


def _make_ctx(sc, d):
    from eidoblend.harness.context import AssetMap, Ctx
    from eidoblend.harness import ledger
    d.mkdir(parents=True, exist_ok=True)
    cfg = {'width': 960, 'height': 540, 'fps': 24, 'duration': 2.0, 'frame_start': 1,
           '_scene_json': str(d / 'scene.json'), '_output': str(d / 'film.mp4')}
    return Ctx(sc, cfg, AssetMap(), ledger.Ledger(), 'build')


def _first_glyph(tt, frame, row=0):
    """the first printed character of buffer row `row` in the frame's PNG (the paper's newest line at row line % 64);
    past the last drawing (no file: Blender holds the last frame) the last file written"""
    import numpy as np
    from PIL import Image
    k = min(frame - tt.scene.frame_start + 1, max(tt.buffer.n, 1))
    im = np.asarray(Image.open(tt.buffer._file(k)))[::-1]
    return chr(32 + int(im[row, 0, 0])) if im[row, 0, 3] else ' '


def run(render=False):
    shutil.rmtree(OUT_DIR, ignore_errors=True)
    sc = S.fresh_scene(frames=(1, 48))
    ctx = _make_ctx(sc, OUT_DIR)
    from eidoblend import props
    a = props.build('teletype', ctx=ctx)
    b = props.build('teletype', ctx=ctx, location=(0.75, 0.0, 0.0))
    for f in range(1, 49):
        t = ctx.time_at(f)
        a.update(t, {'text': TEXT_A, 'nChars': f * 0.8, 'voice': 0.3})
        b.update(t, {'text': TEXT_B, 'nChars': f * 0.8, 'voice': 0.3})
    da, db = Path(a.buffer.dir).resolve(), Path(b.buffer.dir).resolve()
    S.check('two teletypes: one ctx, the default name, each its own buffer folder (screens/<root name>)',
            da != db and da.name == a.group.name and db.name == b.group.name, f'{da.name} | {db.name}')
    S.check('two teletypes: their buffer images read their own files',
            Path(bpy.path.abspath(a.buffer.image.filepath)).parent.resolve() == da
            and Path(bpy.path.abspath(b.buffer.image.filepath)).parent.resolve() == db,
            f'{a.buffer.image.filepath} | {b.buffer.image.filepath}')
    ga, gb = _first_glyph(a, 48), _first_glyph(b, 48)
    S.check("two teletypes: each frame-48 buffer holds its own machine's text", ga == 'M' and gb == 'B',
            f'A prints {ga!r}, B prints {gb!r}')
    # the same buffer_dir given to both: the files carry the root's name, so neither overwrites the other
    shared = OUT_DIR / 'shared_buffer'
    c = props.build('teletype', buffer_dir=str(shared), location=(0.0, 1.2, 0.0))
    d = props.build('teletype', buffer_dir=str(shared), location=(0.75, 1.2, 0.0))
    for f in (1, 2, 3, 4):
        c.update(c.time_at(f), {'text': 'CCCC', 'nChars': f}, frame=f)
        d.update(d.time_at(f), {'text': 'DDDD', 'nChars': f}, frame=f)
    S.check('two teletypes: one shared buffer_dir, two sets of frames (named after each root)',
            _first_glyph(c, 4) == 'C' and _first_glyph(d, 4) == 'D' and c.buffer.prefix != d.buffer.prefix,
            f'{c.buffer.prefix} {d.buffer.prefix}')
    d_files = sorted(p.name for p in shared.glob(f'{d.buffer.prefix}_*.png'))
    c.dispose(files=True)
    left = sorted(p.name for p in shared.glob('*.png'))
    S.check("two teletypes: dispose(files=True) of one takes its own frames and leaves the other's",
            left == d_files and len(d_files) >= 4 and _first_glyph(d, 4) == 'D', f'{len(left)} files left')
    d.dispose(files=True)
    S.check('two teletypes: the last one out takes the emptied folder', not shared.exists())

    # the guide's example: a Blender-relative buffer_dir, before and after the blend is saved
    try:
        e = props.build('teletype', buffer_dir='//screens/tty', location=(0.0, 2.4, 0.0))
        ok, det = Path(e.buffer.dir).is_dir(), str(e.buffer.dir)
        e.dispose(files=True)
    except Exception as ex:  # noqa: BLE001
        ok, det = False, f'{type(ex).__name__}: {ex}'
    S.check("two teletypes: buffer_dir='//screens/tty' in an unsaved blend falls back to a temp folder", ok, det)
    blend = OUT_DIR / 'saved' / 'tty_relative.blend'
    blend.parent.mkdir(parents=True, exist_ok=True)
    bpy.ops.wm.save_as_mainfile(filepath=str(blend))
    try:
        e = props.build('teletype', buffer_dir='//screens/tty', location=(0.0, 2.4, 0.0))
        want = (blend.parent / 'screens' / 'tty').resolve()
        ok, det = Path(e.buffer.dir).resolve() == want, str(e.buffer.dir)
        e.dispose(files=True)
    except Exception as ex:  # noqa: BLE001
        ok, det = False, f'{type(ex).__name__}: {ex}'
    S.check("two teletypes: buffer_dir='//screens/tty' in a saved blend lands beside it", ok, det)

    if render:
        S.floor(sc, 8.0)
        S.wall(sc, y=1.6)
        S.studio(sc, (0.38, 0.0, 0.95), dist=2.0, key=110)
        cam = S.camera(sc, (0.38, -1.05, 1.32), (0.38, 0.06, 0.98), lens=40)
        S.render(S.OUT / 'two_teletypes_papers_f048.png', frame=48)
        S.look_from(cam, (0.62, -0.42, 1.08), (0.75, 0.08, 0.93), lens=50)
        S.render(S.OUT / 'two_teletypes_second_paper_close_f048.png', frame=48)
    return S


if __name__ == '__main__':
    run(render='--render' in sys.argv)
    sys.exit(1 if S.summary('two_teletypes') else 0)
