"""run_tests.py: the harness-rest suite (the harness and placement, complete), U0-U6. The round-one suite stays in
blender/tests/pipeline/run_tests.py (T0-T16); run both.

    U0  test_plain.py: no Blender. audit_core_test.mjs and gpu_check_test.mjs run under Deno, and their cases on
        the Python ports; [KIT_INFO] against fetch_model.py's own preview script; render_common.mjs's
        getCameraAtTime and alphaComposite against its own source; html_mesh's painter; the showpiece nudge
    U1  test_api.py (Blender, renders nothing): audit_core's 14 cases as Blender scenes, the hovering fix, kits and
        islands placed through their instances, play_model_animations against three's AnimationMixer, clones that
        play (shared or own actions), clip names across models and after mixes, the post hooks' order,
        render_common in Blender, html_mesh and interior_window built, the locomotion and lipsync trackers on
        claude.vrm (walked by the characters family, slid by keyed location)
    U2  test_renders.py (Blender, renders): the hovering before / after, a supplies kit stacked with a mounted
        html_mesh sign, interior-mapped windows on a brick facade from two angles, placement.md's recipes, its shelf
        filling and its character on stairs, the crow's layered clips and clones, setup_scene's default rig
        (LOOK at out/renders/)
    U3  model_preview.py, the CLI fetch_model.py calls on this branch: previews of five models with the lines it
        prints ([PREVIEW_BBOX], [PREVIEW_BBOX_BLENDER], [ORIGIN_INFO], [KIT_INFO]) (LOOK at out/previews/)
    U4  the runner: the overlay layer and the auto-enhance hooks in the engine's order, measured on a still
    U5  the runner: a build that never imports the placement family is audited by it, gets the showpiece nudge and
        records its auto-enhance stack (a build: nothing renders)
    U6  the runner: the overlay layer and hooks as a film uses them, a lower third sliding in over a graded shot
        with a vignette (two stills: mid-slide and in place; LOOK at them)

    python blender/tests/pipeline2/run_tests.py [U0 U3 ...]     # through the GPU slot when anything renders:
    cd <main checkout> && HEAVY_VRAM_GB=4 bash work/claude_body/work/tmp/heavy.sh 12 python <worktree>/blender/tests/pipeline2/run_tests.py

Library assets come from the shared cache (EIDO_ASSET_CACHE, EIDO_NO_FETCH=1). Exit 0 when every check passed. A
passing check is not a visual review: LOOK at the PNGs.
"""
import json
import os
import re
import subprocess
import sys

sys.dont_write_bytecode = True
sys.stdout.reconfigure(encoding='utf-8', errors='replace')       # a Windows console pipe is cp1252 otherwise
os.environ['PYTHONIOENCODING'] = 'utf-8'                           # and so are the children's
HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.normpath(os.path.join(HERE, '..', '..', '..'))
OUT = os.path.join(HERE, 'out')
sys.path.insert(0, ROOT)
results = []


def check(test, ok, what):
    results.append((test, bool(ok), what))
    print(f"  {'PASS' if ok else 'FAIL'} {test}: {what}", flush=True)
    return ok


def blender(script, *args, timeout=3600):
    from eido_blender import find_bash
    r = subprocess.run([find_bash(), 'run_blender.sh', script, *args], cwd=ROOT, capture_output=True, text=True,
                       encoding='utf-8', errors='replace', timeout=timeout)
    return r.returncode, r.stdout + r.stderr


def eb(*args):
    r = subprocess.run([sys.executable, os.path.join(ROOT, 'eido_blender.py'), *args], cwd=ROOT, capture_output=True,
                       text=True, encoding='utf-8', errors='replace')
    return r.returncode, r.stdout + r.stderr


def sub_checks(test, rc, out):
    """Carry a child suite's own PASS / FAIL lines into this one."""
    lines = [l for l in out.splitlines() if l.startswith(('PASS ', 'FAIL '))]
    for l in lines:
        check(test, l.startswith('PASS'), l[5:])
    m = re.search(r'(\d+)/(\d+) checks passed', out)
    check(test, rc == 0 and m and m.group(1) == m.group(2) and lines,
          f"{test} finished: exit {rc}, {m.group(0) if m else 'no summary'}" + ('' if lines else ' ' + out[-800:]))


def u0():
    r = subprocess.run([sys.executable, os.path.join(HERE, 'test_plain.py')], cwd=ROOT, capture_output=True, text=True,
                       encoding='utf-8', errors='replace')
    sub_checks('U0', r.returncode, r.stdout + r.stderr)


def u1():
    sub_checks('U1', *blender('blender/tests/pipeline2/test_api.py'))


def u2():
    sub_checks('U2', *blender('blender/tests/pipeline2/test_renders.py'))


PREVIEW_MODELS = [
    'eidoverse/assets/models/crow_bird_animated_corvid_raven_black_cawing_flying_walking.glb',
    'eidoverse/assets/models/corner_desk.glb',
    'eidoverse/assets/models/computer_servers_rack_with_fans_on_back_single_column.glb',
    'blender/tests/pipeline2/out/kit_supplies.glb',
]


def stool_gltf():
    """The shared library's Poly Haven stool (a glTF with its textures inlined)."""
    cache = os.environ.get('EIDO_ASSET_CACHE') or os.path.join(ROOT, 'eidoverse', 'assets', 'cache')
    d = os.path.join(cache, 'models', 'wooden_stool_01_1k')
    return next(os.path.join(d, n) for n in sorted(os.listdir(d)) if n.endswith(('.gltf', '.glb')))


def u3():
    models = PREVIEW_MODELS + [stool_gltf()]
    out = os.path.join(OUT, 'previews') + os.sep
    rc, log = blender('blender/eidoblend/harness/model_preview.py', *models, '--out', out)
    blocks = re.split(r'\n(?=\[PREVIEW_BBOX\])', log)
    infos = {}
    for b in blocks:
        m = re.search(r'Preview: (.+)', b)
        if m and '[PREVIEW_BBOX]' in b:
            infos[os.path.basename(m.group(1).strip())] = b
    check('U3', rc == 0 and len(infos) == len(models), f'{len(infos)}/{len(models)} previews written, exit {rc}')
    for name, b in infos.items():
        jpg = os.path.join(OUT, 'previews', name)
        ok = os.path.exists(jpg) and os.path.getsize(jpg) > 20000
        bb = re.search(r'\[PREVIEW_BBOX_BLENDER\] (\S+) (\S+) (\S+)', b)
        check('U3', ok and bb and '[ORIGIN_INFO]' in b,
              f"{name}: {os.path.getsize(jpg) if os.path.exists(jpg) else 0} bytes, X Y Z "
              f"{tuple(round(float(v), 3) for v in bb.groups()) if bb else '?'}; "
              + (re.search(r'\[ORIGIN_INFO\] Pivot/origin: ([^:.]+)', b).group(1) if '[ORIGIN_INFO]' in b else ''))
    kit = next((b for n, b in infos.items() if n.startswith('kit_supplies')), '')
    check('U3', '[KIT_INFO]' in kit and '4 named parts' in kit,
          'the supplies kit reads as named parts: ' + (re.search(r'\[KIT_INFO\][^\n]{0,110}', kit).group(0)
                                                       if '[KIT_INFO]' in kit else 'no [KIT_INFO]'))
    crow = next((b for n, b in infos.items() if n.startswith('crow')), '')
    check('U3', 'at the BASE' in crow, 'the crow (feet at the origin) reads BASE: '
          + (re.search(r'Pivot/origin: [^.]+', crow).group(0) if crow else 'missing'))


def u4():
    import numpy as np
    from PIL import Image
    for p in os.listdir(OUT):
        if p.startswith('overlay_probe_at'):
            os.remove(os.path.join(OUT, p))
    rc, log = eb('render', os.path.join(HERE, 'overlay', 'scene.json'), '--at', '1', '--rebuild', '--force')
    png = os.path.join(OUT, 'overlay_probe_at1.00s.png')
    if not check('U4', rc == 0 and os.path.exists(png), f'the still rendered (exit {rc}): {png} (LOOK at it)'):
        print(log[-3000:])
        return
    d = json.load(open(os.path.join(OUT, 'overlay_probe.audit.json'), encoding='utf-8'))
    ae = next((r for r in d['records'] if r['check'] == 'render.auto_enhance'), None)
    check('U4', ae and ae['metrics'].get('stages') == ['under:color_hook', 'overlay:overlay', 'over:screen_hook'],
          f"the digest records the stack: {ae['metrics'].get('stages') if ae else 'missing'}")
    box = json.loads(next(r['message'] for r in d['records'] if r['check'] == 'scene.overlay_card'))['box']
    im = np.asarray(Image.open(png).convert('RGB'), np.float64)
    H, W = im.shape[:2]
    x0, y0, x1, y1 = int(box[0] * W) + 14, int(box[1] * H) + 6, int(box[2] * W) - 6, int(box[3] * H) - 6
    card = im[y0:y1, x0:x1].reshape(-1, 3)
    world = np.concatenate([im[:int(0.55 * H)].reshape(-1, 3)])
    panel = card[card.sum(1) > 600]                                   # the inverted near-black panel: near white
    ink = card[(card[:, 2] > card[:, 0] + 60)]                        # inverted orange ink: blue
    check('U4', len(panel) > 0.5 * len(card),
          f'the overlay card is there and inverted by the screen hook: {len(panel) / len(card):.0%} of it near white')
    check('U4', len(ink) > 0.02 * len(card) and ink[:, 2].mean() > ink[:, 0].mean() + 80,
          f'its orange ink came through the colour hook undesaturated, then inverted to blue: {len(ink)} px, mean '
          f'{ink.mean(0).round().tolist() if len(ink) else "-"}')
    sat = np.abs(world - world.mean(1, keepdims=True)).max(1)
    check('U4', np.percentile(sat, 99) < 6,
          f'the world (warm key on a crate) is desaturated by the colour hook: 99th percentile channel spread '
          f'{np.percentile(sat, 99):.1f} levels')


def u6():
    import numpy as np
    from PIL import Image
    for p in os.listdir(OUT):
        if p.startswith('lower_third_probe_at'):
            os.remove(os.path.join(OUT, p))
    rc, log = eb('render', os.path.join(HERE, 'lower_third', 'scene.json'), '--at', '0.2', '--at', '2', '--rebuild',
                 '--force')
    pngs = [os.path.join(OUT, f'lower_third_probe_at{t}s.png') for t in ('0.20', '2.00')]
    if not check('U6', rc == 0 and all(os.path.exists(p) for p in pngs),
                 f'two stills rendered (exit {rc}): {pngs} (LOOK at them)'):
        print(log[-3000:])
        return
    d = json.load(open(os.path.join(OUT, 'lower_third_probe.audit.json'), encoding='utf-8'))
    ae = next((r for r in d['records'] if r['check'] == 'render.auto_enhance'), None)
    want = ['bloom:bloom', 'under:color_hook', 'overlay:overlay', 'over:screen_hook']
    check('U6', ae and ae['metrics'].get('stages') == want and ae['outcome'] == 'PASS',
          f"the digest records the film's stack in the engine's order: {ae['metrics'].get('stages') if ae else 'missing'}")
    a, b = (np.asarray(Image.open(p).convert('RGB'), np.float64) for p in pngs)
    H, W = b.shape[:2]
    band = (slice(int(0.78 * H), int(0.89 * H)), slice(int(0.07 * W), int(0.30 * W)))   # the card's left half
    dark_b = (b[band].sum(2) < 120).mean()
    dark_a = (a[band].sum(2) < 120).mean()
    check('U6', dark_b > 0.35 and dark_b > dark_a + 0.15,
          f'the card follows its keys on the overlay layer: its dark panel fills {dark_b:.0%} of its place at 2 s '
          f'and {dark_a:.0%} at 0.2 s (still off the left edge)')
    corner = b[:int(0.12 * H), :int(0.12 * W)].mean()
    centre = b[int(0.3 * H):int(0.55 * H), int(0.4 * W):int(0.6 * W)].mean()
    check('U6', corner < 0.75 * centre, f'the vignette darkens the corners: corner mean {corner:.0f}, centre '
                                         f'{centre:.0f} (of 255)')


def u5():
    rc, log = eb('build', os.path.join(HERE, 'defaults', 'scene.json'), '--rebuild', '--force')
    d = json.load(open(os.path.join(OUT, 'defaults_build.audit.json'), encoding='utf-8'))
    recs = {r['check']: r for r in d['records']}
    hv = recs.get('placement.hovering')
    check('U5', rc == 0 and hv and hv['outcome'] == 'WARN' and 'crate_by_hand' in hv['message'],
          'the placement audits ran though the scene never imported the family, and name the crate in the air: '
          + (hv['message'][:100] if hv else 'missing'))
    sp = recs.get('palette.showpiece')
    check('U5', sp and 'fx.swe' in sp['message'], 'the 16 s scene with a coffee mug and no showpiece is pointed at the '
          'liquid: ' + (sp['message'][:90] if sp else 'missing'))
    ae = recs.get('render.auto_enhance')
    check('U5', ae and 'AO' in ae['message'], 'the auto-enhance stack is recorded: ' + (ae['message'] if ae else 'missing'))
    pal = recs.get('palette')
    check('U5', pal and 'toolkit used: none' in pal['message'], 'the runner\'s own modules are not "toolkit used": '
          + (pal['message'][-60:] if pal else 'missing'))


if __name__ == '__main__':
    os.makedirs(OUT, exist_ok=True)
    tests = {'U0': u0, 'U1': u1, 'U2': u2, 'U3': u3, 'U4': u4, 'U5': u5, 'U6': u6}
    pick = [a for a in sys.argv[1:] if a in tests] or list(tests)
    for t in pick:
        print(f'\n== {t}', flush=True)
        try:
            tests[t]()
        except Exception as e:                                      # noqa: BLE001
            import traceback
            traceback.print_exc()
            check(t, False, f'{type(e).__name__}: {e}')
    n = sum(1 for _t, ok, _w in results if ok)
    print(f'\n{n}/{len(results)} checks passed', flush=True)
    sys.exit(0 if n == len(results) else 1)
