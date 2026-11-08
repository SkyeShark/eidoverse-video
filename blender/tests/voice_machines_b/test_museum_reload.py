"""All five props of this step in one film, built through the registry (props.build by name), animated over 48
frames, saved, reopened, and checked: the saved .blend plays and renders any frame on its own (keys, drivers, the
teletype's buffer and the Speak & Spell's VFD sequences, the tandem's Geometry Nodes). A wide still of the reopened
film at frame 30: the machines at true scale side by side.

    cd <main checkout> && bash run_blender.sh <worktree>/blender/tests/voice_machines_b/test_museum_reload.py      # checks
    HEAVY_VRAM_GB=4 bash work/claude_body/work/tmp/heavy.sh 12 bash run_blender.sh <this> --render             # + still
"""
import math
import shutil
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import _stage as S  # noqa: E402

import bpy  # noqa: E402

DIR = S.OUT / 'museum_reload'
FRAME = 30


def probe(names):
    """the values the machines show at FRAME, read from the scene as it stands"""
    sc = bpy.context.scene
    sc.frame_set(FRAME)
    ob = bpy.data.objects
    return {
        'voder.level': ob[names['voder']]['level'],
        'voder.key8': ob['voder_key_08'].rotation_euler[0],
        'mainframe.clock': ob[names['mainframe']]['clock'],
        'mainframe.reel': ob['mainframe_reel_1_file_pivot'].rotation_euler[1],
        'teletype.line': ob[names['teletype']]['line'],
        'teletype.head': ob['teletype_typebox'].location.x,
        'speakspell.gain': ob[names['speakspell']]['gain'],
        'tandem.wheel': ob['wheel_rear'].rotation_euler[1],
        'tandem.chain': ob[names['tandem']]['chain_drive'],
    }


def run(render=False):
    if DIR.exists():
        shutil.rmtree(DIR, ignore_errors=True)
    DIR.mkdir(parents=True)
    sc = S.fresh_scene(frames=(1, 48))
    # a scene's ctx, as the harness runner hands it to setup(ctx) / render_frame(ctx, t, i): the props are built
    # with it and every update keys through ctx.key (no frame= given: ctx.frame_at(t) places each key)
    from eidoblend.harness.context import AssetMap, Ctx
    from eidoblend.harness import keying, ledger
    cfg = {'width': 960, 'height': 540, 'fps': 24, 'duration': 2.0, 'frame_start': 1,
           '_scene_json': str(DIR / 'scene.json'), '_output': str(DIR / 'museum_of_voices.mp4')}
    ctx = Ctx(sc, cfg, AssetMap(), ledger.Ledger(), 'build')
    from eidoblend import props
    vo = props.build('voder', ctx=ctx)
    vo.group.location = (-2.6, 1.2, 0.0)
    mf = props.build('mainframe', name='mainframe_room', ctx=ctx)
    mf.group.location = (0.0, 4.2, 0.0)
    tt = props.build('teletype', ctx=ctx)
    tt.group.location = (-0.9, 0.9, 0.0)
    ss = props.build('speakspell', {'text': 'daisy', 'ctx': ctx})
    ss.group.location = (0.35, 0.55, 0.74)
    td = props.build('tandem', ctx=ctx)
    td.group.location = (0.6, -0.6, 0.0)
    S.check('museum: five props built by name through the registry, each with the scene\'s ctx',
            all(m is not None for m in (vo, mf, tt, ss, td)) and vo.group.get('voice_machine', {}).get('name') == 'voder'
            and ss.group.get('voice_machine', {}).get('name') == 'speakspell'
            and all(m.ctx is ctx for m in (vo, mf, tt, ss, td)))
    S.check('museum: with a ctx the teletype buffer goes to <ctx.out_dir>/screens/<name>',
            Path(tt.buffer.dir).resolve() == (DIR / 'screens' / 'teletype').resolve(), str(tt.buffer.dir))
    text = 'HOW DO YOU DO. PLEASE TELL ME YOUR PROBLEM\n'
    for f in range(1, 49):
        sc.frame_set(f)                               # as the runner does before render_frame(ctx, t, i)
        t = ctx.time_at(f)
        v = 0.5 + 0.5 * math.sin(t * 5.0)
        vo.update(t, {'voice': v, 'power': 1.0})
        mf.update(t, {'tapeSpeed': 1.0, 'voice': v})
        tt.update(t, {'text': text, 'nChars': f * 0.8, 'voice': v})
        ss.update(t, {'power': 1.0, 'voice': v})
        td.update(t, {'speed': 1.4})
    n_lin = keying.make_linear(ctx.key_log)           # the runner's pass after render_frame
    interp = {}
    for m in (vo, mf, tt, td):
        for o in [m.group] + list(m.group.children_recursive):
            for k, v in keying.interpolations(o).items():
                interp.setdefault(m.name, set()).update(v)
    S.check('museum: every update keyed through ctx.key, LINEAR after the runner\'s pass',
            ctx.keyed > 1000 and all(v == {'LINEAR'} for v in interp.values()),
            f'{ctx.keyed} keys through ctx, {n_lin} made LINEAR, {interp}')
    names = {'voder': vo.group.name, 'mainframe': mf.group.name, 'teletype': tt.group.name,
             'speakspell': ss.group.name, 'tandem': td.group.name}
    before = probe(names)
    # a desk under the toy, a floor and a wall: the room the still is taken in
    S.floor(sc, size=20)
    S.wall(sc, y=6.0, width=20)
    desk = bpy.data.meshes.new('desk')
    import bmesh
    bm = bmesh.new()
    bmesh.ops.create_cube(bm, size=1.0)
    bm.to_mesh(desk)
    bm.free()
    d = bpy.data.objects.new('desk', desk)
    sc.collection.objects.link(d)
    d.scale = (0.7, 0.45, 0.74)
    d.location = (0.35, 0.6, 0.37)
    S.studio(sc, (0.0, 1.5, 1.0), dist=6.0, key=350, scale=1.6)
    cam = S.camera(sc, (1.9, -4.9, 1.65), (-0.5, 1.6, 0.95), lens=24)
    path = DIR / 'museum_of_voices.blend'
    bpy.ops.wm.save_as_mainfile(filepath=str(path))
    bpy.ops.wm.open_mainfile(filepath=str(path))
    after = probe(names)
    bad = [k for k in before if abs(before[k] - after[k]) > 1e-5 * max(1.0, abs(before[k]))]
    S.check('museum: the reopened .blend shows the same frame 30 (keys and properties)', not bad,
            ', '.join(f'{k}: {before[k]:.4f} -> {after[k]:.4f}' for k in bad) or f"{len(before)} values")
    S.check('museum: the machines moved between frames (keyed, not posed)', abs(before['tandem.wheel']) > 1.0 and
            before['mainframe.clock'] > 1.0 and before['teletype.head'] != 0.0)
    img = next(i for i in bpy.data.images if i.name.startswith('teletype_paper_buffer'))
    files = sorted(Path(bpy.path.abspath(img.filepath)).parent.glob('*.png'))
    S.check('museum: the teletype buffer sequence is on disk for the reopened file', len(files) >= 48, f'{len(files)} files')
    if render:
        sc = bpy.context.scene
        S.render(S.OUT / 'museum_reloaded_wide_f030.png', frame=FRAME)
    return S.summary('museum')


if __name__ == '__main__':
    sys.exit(1 if run(render='--render' in sys.argv) else 0)
