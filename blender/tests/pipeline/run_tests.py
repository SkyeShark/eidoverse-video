#!/usr/bin/env python3
"""The pipeline family's tests: the Blender edition's runner, end to end. They render (small: 960x540 at most, 16
samples or fewer, a few seconds of film), so on a shared GPU run them through the slot, from the repo root:

    python blender/tests/pipeline/run_tests.py                 # all
    python blender/tests/pipeline/run_tests.py T1 T3           # some

    T0  the config, without Blender: composedOutput / outputDir fallbacks, ceil(duration x fps) frames
    T7  doctor: Blender 5.2, bash, ffmpeg, a 64x64 EEVEE render
    T1  the example: three --at stills, digest status, nothing warned, nothing unobserved (placement audits ran)
    T6  the example's film: H.264 (yuv420p, 960x540, 72 frames), three probe frames, a rerun leaves .mp4.prev
    T2  --at stills against the film's own frames (PSNR): a jumped-to frame renders as the film does
    T3  planted defects: every one named in the digest (an un-keyed light change among them)
    T4  the build is reused when nothing changed; a hand-edited .blend renders as edited, its placement audits
        re-run (the clock left floating is named), a rebuild over it is refused (exit 3), and --force rebuilds
    T5  a model's own clips on a model and its clone (stills: LOOK at them)
    T8  the placement family's audits run when a scene uses that family; a floating box is named
    T9  bench: seconds a frame at film settings, and the film's estimate
    T10 load_kit: parts out of their catalogue row standing on z = 0 (a still: LOOK at it)
    T11 navigation: a sensing walk (positive pitch looks down) arrives, keeping its full radius clear
    T12 the "bloom" render option: a halo around a hot emitter with it, none without
    T13 the config's "preset": "probe" applies the probe caps
    T14 a 300-frame rigid-body film: the cache is stretched past Blender's default 250 and the crates move late
    T15 a plan file the script reads (undeclared): an edit to it rebuilds the scene; unchanged, the build is reused
    T16 two shots: LINEAR and CONSTANT keys in the saved .blend, the keyed lamp step holds, nothing changed without
        a key, and shot B's framing measures what its camera sees
    T17 a Geometry Nodes modifier (Blender 5.2 keeps its inputs as RNA, not ID properties): the build's un-keyed check
        reads it, a keyed input plays from the saved .blend, an input set without a key is named
    T18 parts that turn in place (motion.swept_clearance): a rotor sunk in its drum and one whose blades cut a cabinet
        are named, a clear rotor and a radar scanning short of a pole are not (a still: LOOK at it)
    T19 --at stills of shots whose post effect reads earlier frames: after_image's trail (from the shot's start) and
        the era looks' CRT persistence (seven frames back) match the film's own frames, the records cleared first
    T7  (doctor) also reports Deno, its version and its npm packages imported offline

Outputs land in blender/tests/pipeline/out/ (git-ignored). Library textures and models come from the shared cache:
set EIDO_ASSET_CACHE to a checkout that has them and EIDO_NO_FETCH=1 to forbid downloads. Exit 0 when every test
passed. A passing test is not a visual review: LOOK at the PNGs.
"""
import glob
import json
import os
import shutil
import subprocess
import sys

sys.dont_write_bytecode = True               # T0 imports the package here: no __pycache__ in it
HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.normpath(os.path.join(HERE, '..', '..', '..'))
OUT = os.path.join(HERE, 'out')
EB = [sys.executable, os.path.join(ROOT, 'eido_blender.py')]
EXAMPLE = os.path.join(HERE, 'example', 'scene.json')
DEFECTS = os.path.join(HERE, 'defects', 'scene.json')
CROWS = os.path.join(HERE, 'crows', 'scene.json')
BRIDGE = os.path.join(HERE, 'placement_bridge', 'scene.json')
KIT = os.path.join(HERE, 'kit', 'scene.json')
NAV = os.path.join(HERE, 'nav', 'scene.json')
BAKE = os.path.join(HERE, 'bake', 'scene.json')
GN = os.path.join(HERE, 'gn_keying', 'scene.json')
GN_UNKEYED = os.path.join(HERE, 'gn_keying', 'scene_unkeyed.json')
STALE = os.path.join(HERE, 'stale', 'scene.json')
SHOTS = os.path.join(HERE, 'shots', 'scene.json')
SWEPT = os.path.join(HERE, 'swept', 'scene.json')
LEADIN = os.path.join(HERE, 'leadin', 'scene.json')
LEADIN_CRT = os.path.join(HERE, 'leadin', 'scene_crt.json')
results = []


def run(args, expect_rc=0):
    print('\n$ eido_blender.py ' + ' '.join(os.path.relpath(a, ROOT) if os.path.isabs(a) else a for a in args),
          flush=True)
    r = subprocess.run(EB + args, cwd=ROOT, capture_output=True, text=True, encoding='utf-8', errors='replace')
    tail = [l for l in (r.stdout + r.stderr).splitlines() if l.startswith(('eido_blender:', '[eido_blender]', '[assets]',
                                                                           '[scene]', '[bench]', '[doctor]', '[ok', '[FAIL',
                                                                           '[--', 'error', 'Traceback', '  '))]
    print('\n'.join(tail[-25:]), flush=True)
    return r.returncode, r.stdout + r.stderr


def check(test, ok, what):
    results.append((test, bool(ok), what))
    print(f"  {'PASS' if ok else 'FAIL'} {test}: {what}", flush=True)
    return ok


def digest(path):
    with open(path, encoding='utf-8') as f:
        return json.load(f)


def warns(d):
    return [r for r in d['records'] if r['outcome'] == 'WARN']


def ffprobe(video):
    r = subprocess.run(['ffprobe', '-v', 'error', '-select_streams', 'v:0', '-count_frames', '-show_entries',
                        'stream=codec_name,profile,pix_fmt,width,height,nb_read_frames', '-of', 'json', video],
                       capture_output=True, text=True)
    return json.loads(r.stdout)['streams'][0]


def psnr(a, b):
    import numpy as np
    from PIL import Image
    x = np.asarray(Image.open(a).convert('RGB'), np.float64)
    y = np.asarray(Image.open(b).convert('RGB'), np.float64)
    mse = ((x - y) ** 2).mean()
    return 99.0 if mse == 0 else 10 * np.log10(255.0 ** 2 / mse)


def query(blend, spec):
    """What a saved .blend shows (query_blend.py, no render): positions, light energies, key interpolations."""
    sys.path.insert(0, ROOT)
    from eido_blender import find_bash
    sp = os.path.join(OUT, '_query.json')
    with open(sp, 'w', encoding='utf-8') as f:
        json.dump(spec, f)
    r = subprocess.run([find_bash(), 'run_blender.sh', 'blender/tests/pipeline/query_blend.py', blend, sp], cwd=ROOT,
                       capture_output=True, text=True, encoding='utf-8', errors='replace')
    for line in r.stdout.splitlines():
        if line.startswith('QUERY_JSON '):
            return json.loads(line[len('QUERY_JSON '):])
    print(r.stdout[-2000:] + r.stderr[-2000:])
    return None


def records(d, check):
    return [r for r in d['records'] if r['check'] == check]


# ------------------------------------------------------------------------------------------------- tests ---

def t0():
    sys.path.insert(0, os.path.join(ROOT, 'blender'))
    from eidoblend.harness import config as cfgmod
    tmp = os.path.join(OUT, '_t0')
    os.makedirs(tmp, exist_ok=True)
    script = os.path.join(HERE, 'stale', 'scene.py')

    def load(extra):
        p = os.path.join(tmp, 'cfg.json')
        with open(p, 'w', encoding='utf-8') as f:
            json.dump({'script': script, **extra}, f)
        return cfgmod.load_config(p)
    c = load({'composedOutput': 'work/t0/composed.mp4'})
    check('T0', c['_output'].replace('\\', '/').endswith('work/t0/composed.mp4'),
          f"composedOutput names the film when outputVideo is absent: {c['_output']}")
    c = load({'outputDir': 'work/t0/shots'})
    check('T0', c['_output'].replace('\\', '/').endswith('work/t0/shots.mp4'), f"outputDir + '.mp4': {c['_output']}")
    c = load({'outputVideo': 'work/t0/v.mp4', 'composedOutput': 'work/t0/x.mp4'})
    check('T0', c['_output'].replace('\\', '/').endswith('work/t0/v.mp4'), 'outputVideo wins over composedOutput')
    c = load({})
    check('T0', c['_output'] == os.path.join(tmp, 'cfg.mp4'), f"no output keys: beside the config ({c['_output']})")
    n = [cfgmod.total_frames({'duration': d, 'fps': f}) for d, f in ((3, 24), (2.5, 30), (1.01, 24), (0.1 * 3, 10))]
    check('T0', n == [72, 75, 25, 3], f'ceil(duration x fps) frames, as render_scene.mjs: {n} (want [72, 75, 25, 3])')
    shutil.rmtree(tmp, ignore_errors=True)


def t7():
    rc, out = run(['doctor'])
    check('T7', rc == 0, f'doctor exit {rc}')
    deno = [l for l in out.splitlines() if l.startswith(('[ok ] Deno', '[-- ] Deno'))]
    check('T7', len(deno) >= 1 and (len(deno) == 2 or deno[0].startswith('[-- ]')),
          "doctor reports Deno (the canvas screens', books' and parole's), its version and its npm packages imported "
          f'offline: {deno}')


def t1():
    for p in glob.glob(os.path.join(OUT, 'example_probe_at*.png')):
        os.remove(p)
    rc, _ = run(['render', EXAMPLE, '--at', '0', '--at', '1.5', '--at', '3'])
    pngs = [os.path.join(OUT, f'example_probe_at{t}s.png') for t in ('0.00', '1.50', '2.96')]
    check('T1', rc == 0, f'capture exit {rc}')
    check('T1', all(os.path.exists(p) for p in pngs), 'three stills, named by their frame times')
    d = digest(os.path.join(OUT, 'example_probe.audit.json'))
    check('T1', d['status'] == 'normal completion', f"digest status '{d['status']}'")
    w = warns(d)
    check('T1', not w, 'no warnings on the example' + (f": {[(r['check'], r['message'][:100]) for r in w]}" if w else ''))
    sk = [r['check'] for r in d['records'] if r['outcome'] == 'SKIPPED']
    check('T1', not sk, f'nothing unobserved: {sk}')
    pl = sorted({r['check'] for r in d['records'] if r['check'].startswith('placement.')})
    check('T1', 'placement.hovering' in pl and 'placement.clipping' in pl,
          f"the placement family's audits ran (the example seats things with place_on): {pl}")
    uk = records(d, 'build.unkeyed')
    check('T1', uk and uk[0]['outcome'] == 'PASS', f"nothing changed without a key: {uk[0]['message'][:90] if uk else 'no record'}")


def t6():
    video = os.path.join(OUT, 'example.mp4')
    had = os.path.exists(video)
    rc, _ = run(['render', EXAMPLE])
    check('T6', rc == 0 and os.path.exists(video), f'film exit {rc}, {video} exists')
    info = ffprobe(video)
    check('T6', info['codec_name'] == 'h264' and info['pix_fmt'] == 'yuv420p'
          and (info['width'], info['height']) == (960, 540) and int(info['nb_read_frames']) == 72,
          f"ffprobe {info['codec_name']} {info.get('profile')} {info['pix_fmt']} {info['width']}x{info['height']} "
          f"{info['nb_read_frames']} frames")
    check('T6', all(os.path.exists(os.path.join(OUT, f'example_probe{i}.png')) for i in (1, 2, 3)), 'probe frames 1..3')
    check('T6', not os.path.exists(video + '.part'), 'no .part left behind')
    if had:
        check('T6', os.path.exists(video + '.prev'), 'the previous film was kept as .mp4.prev')
    else:
        rc, _ = run(['render', EXAMPLE])
        check('T6', rc == 0 and os.path.exists(video + '.prev'), 'a rerun keeps the previous film as .mp4.prev')


def t2():
    video = os.path.join(OUT, 'example.mp4')
    if not os.path.exists(video):
        return check('T2', False, 'needs T6 first (no example.mp4)')
    tmp = os.path.join(OUT, '_t2')
    shutil.rmtree(tmp, ignore_errors=True)
    os.makedirs(tmp)
    for idx, t in ((0, '0.00'), (36, '1.50'), (71, '2.96')):
        frame = os.path.join(tmp, f'f{idx}.png')
        subprocess.run(['ffmpeg', '-y', '-loglevel', 'error', '-i', video, '-vf', f'select=eq(n\\,{idx})', '-fps_mode',
                        'vfr', '-frames:v', '1', frame], check=True)
        still = os.path.join(OUT, f'example_probe_at{t}s.png')
        if not os.path.exists(still):
            check('T2', False, f'needs T1 first ({still})')
            continue
        v = psnr(still, frame)
        check('T2', v > 35.0, f'--at {t} s vs film frame {idx}: PSNR {v:.1f} dB')
    shutil.rmtree(tmp, ignore_errors=True)


EXPECTED_DEFECTS = [
    ('motion.envelope', 'WRONG PIVOT'), ('motion.envelope', 'BELOW the ground'), ('motion.envelope', 'TELEPORTS'),
    ('motion.envelope', 'scale drifted'), ('motion.sideways', 'SIDEWAYS'), ('motion.camera', 'BOUNCES'),
    ('motion.rig_pose', 'NEVER left its pose'), ('preflight.images', 'missing'), ('preflight.colour', 'Standard'),
    ('preflight.world', 'no world'), ('assets.reads', 'unused_model'), ('coverage.no_clipping_check', 'GROUP-BLANKET'),
    ('build.unkeyed', "light 'sun'.energy"),
]


def t3():
    rc, _ = run(['render', DEFECTS, '--probe', '--frames', '1', '--rebuild', '--force'])
    check('T3', rc == 0, f'defects probe exit {rc}')
    d = digest(os.path.join(OUT, 'defects_probe.audit.json'))
    w = warns(d)
    for chk, words in EXPECTED_DEFECTS:
        hit = [r for r in w if r['check'] == chk and words.lower() in r['message'].lower()]
        check('T3', hit, f'{chk} names "{words}"' + (f": {hit[0]['message'][:90]}" if hit else ''))
    sk = [r for r in d['records'] if r['check'] == 'motion.locomotion' and r['outcome'] == 'SKIPPED'
          and r['disposition'] == 'DECLARED_EXCEPTION']
    check('T3', sk, 'the global disable _no_locomotion_check is a SKIPPED declared exception')
    uk = [r for r in w if r['check'] == 'build.unkeyed']
    check('T3', uk and uk[0].get('bodies') == ["light 'sun'.energy"],
          "the un-keyed check names the sun and nothing else (setup's own sparse keys, made LINEAR, are not "
          f"mistaken for un-keyed changes): {uk[0].get('bodies') if uk else None}")
    check('T3', d['clean'] is False, 'the digest is not clean')
    named = {(c, w_) for c, w_ in EXPECTED_DEFECTS}
    extra = [r['check'] + ': ' + r['message'][:80] for r in w
             if not any(r['check'] == c and w_.lower() in r['message'].lower() for c, w_ in named)]
    print('  (other warnings: ' + ('; '.join(extra) if extra else 'none') + ')')


def t4():
    blend = os.path.join(OUT, 'example.blend')
    rc, _ = run(['render', EXAMPLE, '--at', '1'])
    d = digest(os.path.join(OUT, 'example_probe.audit.json'))
    check('T4', rc == 0 and any('reused the build' in r['message'] for r in d['records']),
          'an unchanged build is reused')
    sys.path.insert(0, ROOT)
    from eido_blender import find_bash                               # Git Bash, never WSL's
    # 0.6 m: the stool goes out from under the clock. (At 0.3 m the clock already hangs in the air, but the
    # placement family's hovering check still counts it as touching the stool, whose bounding box, legs
    # splayed, overlaps the clock's footprint: that family's finding to fix, reported to the lead.)
    subprocess.run([find_bash(), 'run_blender.sh', 'blender/tests/pipeline/hand_edit.py', blend, 'stool', '0.6'],
                   cwd=ROOT, capture_output=True, text=True)
    rc, _ = run(['render', EXAMPLE, '--at', '1'])
    d = digest(os.path.join(OUT, 'example_probe.audit.json'))
    check('T4', rc == 0 and any('AS EDITED BY HAND' in r['message'] for r in d['records']),
          'a hand-edited .blend renders as edited, with its audits re-run')
    check('T4', any(r['check'] == 'motion.camera' for r in d['records']), 'the re-run audits are in the digest')
    fl = [r for r in d['records'] if r['check'].startswith('placement.') and r['outcome'] == 'WARN'
          and 'clock' in r['message']]
    check('T4', fl, 'the placement audits re-ran on the hand edit and name the clock it left floating: '
          + (fl[0]['check'] + ': ' + fl[0]['message'][:90] if fl else
             '; '.join(r['check'] + ' ' + r['outcome'] for r in d['records'] if r['check'].startswith('placement'))))
    if os.path.exists(os.path.join(OUT, 'example_probe_at1.00s.png')):
        shutil.copy(os.path.join(OUT, 'example_probe_at1.00s.png'), os.path.join(OUT, 'example_hand_edit_at1.00s.png'))
    rc, _ = run(['build', EXAMPLE, '--rebuild'], expect_rc=3)
    check('T4', rc == 3, f'a rebuild over the hand edit is refused (exit {rc})')
    rc, _ = run(['build', EXAMPLE, '--rebuild', '--force'])
    rec = json.load(open(os.path.join(OUT, 'example.build.json'), encoding='utf-8'))
    import hashlib
    md5 = hashlib.md5(open(blend, 'rb').read()).hexdigest()
    check('T4', rc == 0 and rec['saved']['md5'] == md5, '--force rebuilds, and the record matches the new .blend')


def t5():
    for p in glob.glob(os.path.join(OUT, 'crows_probe_at*.png')):
        os.remove(p)
    rc, out = run(['render', CROWS, '--at', '0.5', '--at', '1.6', '--at', '2.6'])
    pngs = sorted(glob.glob(os.path.join(OUT, 'crows_probe_at*.png')))
    check('T5', rc == 0 and len(pngs) == 3, f'crow stills: {[os.path.basename(p) for p in pngs]} (LOOK at them)')
    d = digest(os.path.join(OUT, 'crows_probe.audit.json'))
    check('T5', not [r for r in d['records'] if r['outcome'] == 'WARN'],
          'no warnings: ' + '; '.join(r['message'][:80] for r in warns(d)))
    # the glTF importer's 2 m 'Icosphere' bone shape once rendered over both birds while every check passed:
    # the framed subject must be the crows themselves
    fr = [r['message'] for r in d['records'] if r['check'] == 'framing']
    check('T5', fr and 'CROW' in fr[0] and 'Icosphere' not in fr[0], f'the framed subject is the crows: {fr[:1]}')


def t8():
    rc, _ = run(['build', BRIDGE, '--rebuild', '--force'])
    check('T8', rc == 0, f'placement bridge build exit {rc}')
    d = digest(os.path.join(OUT, 'placement_bridge_build.audit.json'))
    pl = [r for r in d['records'] if r['check'].startswith('placement')]
    check('T8', pl and not any(r['check'] == 'placement' and r['outcome'] == 'SKIPPED' for r in pl),
          f"the placement family's audits ran: {sorted({r['check'] for r in pl})}")
    hit = [r for r in pl if r['outcome'] == 'WARN' and 'floater_box' in r['message']]
    check('T8', hit, 'the floating box is named: ' + (hit[0]['check'] + ': ' + hit[0]['message'][:80] if hit else
                                                     '; '.join(r['check'] + ' ' + r['outcome'] for r in pl)))
    check('T8', not [r for r in pl if r['outcome'] == 'WARN' and 'crate' in r['message'] and 'floater' not in r['message']],
          'the crate seated with place_on is not flagged')


def t9():
    rc, out = run(['bench', EXAMPLE, '--frames', '3'])
    d = digest(os.path.join(OUT, 'example_bench.audit.json'))
    b = [r for r in d['records'] if r['check'] == 'render.bench']
    spf = b[0]['metrics'].get('seconds_per_frame') if b else None
    check('T9', rc == 0 and spf and spf > 0, f'bench: {b[0]["message"] if b else "no render.bench record"}')


def t10():
    sys.path.insert(0, ROOT)
    from eido_blender import find_bash
    glb = os.path.join(OUT, 'kit_parts.glb')
    subprocess.run([find_bash(), 'run_blender.sh', 'blender/tests/pipeline/make_kit.py', glb], cwd=ROOT,
                   capture_output=True, text=True)
    check('T10', os.path.exists(glb), f'the kit GLB was made ({glb})')
    rc, _ = run(['render', KIT, '--at', '0', '--rebuild', '--force'])
    d = digest(os.path.join(OUT, 'kit_probe.audit.json'))
    for name in ('scene.kit_bases', 'scene.kit_row'):
        r = [x for x in d['records'] if x['check'] == name]
        check('T10', rc == 0 and r and r[0]['outcome'] == 'PASS', f"{name}: {r[0]['message'] if r else 'missing'}")
    check('T10', os.path.exists(os.path.join(OUT, 'kit_probe_at0.00s.png')), 'a still of the kit (LOOK at it)')


def t11():
    rc, _ = run(['render', NAV, '--at', '0', '--rebuild', '--force'])
    d = digest(os.path.join(OUT, 'nav_probe.audit.json'))
    for name in ('scene.nav_pitch', 'scene.nav_arrived', 'scene.nav_clearance'):
        r = [x for x in d['records'] if x['check'] == name]
        check('T11', rc == 0 and r and r[0]['outcome'] == 'PASS', f"{name}: {r[0]['message'] if r else 'missing'}")
    check('T11', os.path.exists(os.path.join(OUT, 'nav_probe_at0.00s.png')), 'a still of the map and route (LOOK at it)')


def t12():
    import numpy as np
    from PIL import Image
    rings = {}
    for tag, cfg in (('on', 'scene.json'), ('off', 'scene_off.json')):
        rc, _ = run(['render', os.path.join(HERE, 'bloom', cfg), '--at', '0', '--rebuild', '--force'])
        png = os.path.join(OUT, f'bloom_{tag}_probe_at0.00s.png')
        if rc or not os.path.exists(png):
            return check('T12', False, f'bloom {tag}: render exit {rc}, {png} missing')
        im = np.asarray(Image.open(png).convert('L'), np.float64)
        h, w = im.shape
        yy, xx = np.mgrid[0:h, 0:w]
        r = np.hypot(yy - h / 2, xx - w / 2)
        rings[tag] = im[(r > 40) & (r < 70)].mean()
    d = digest(os.path.join(OUT, 'bloom_on_probe.audit.json'))
    note = [x['message'] for x in d['records'] if 'bloom' in x['message']]
    check('T12', note, f'the build records the bloom pass: {note[:1]}')
    check('T12', rings['on'] > rings['off'] + 3, f"a halo around the emitter: ring mean {rings['on']:.1f} with bloom, "
          f"{rings['off']:.1f} without (of 255)")


def t13():
    rc, _ = run(['render', os.path.join(HERE, 'example', 'scene_probe_preset.json'), '--at', '1'])
    d = digest(os.path.join(OUT, 'example_pp_probe.audit.json'))
    pre = [r['message'] for r in d['records'] if r['check'] == 'render.preset']
    check('T13', rc == 0 and pre and 'probe caps' in pre[0], f'the config\'s "preset": "probe" applies: {pre[:1]}')


def t14():
    for p in glob.glob(os.path.join(OUT, 'bake_probe_at*.png')):
        os.remove(p)
    rc, _ = run(['render', BAKE, '--at', '10', '--at', '11.5', '--at', '12', '--rebuild', '--force'])
    check('T14', rc == 0, f'bake film build + stills exit {rc}')
    d = digest(os.path.join(OUT, 'bake_probe.audit.json'))
    bk = [r['message'] for r in records(d, 'build.bake')]
    check('T14', any('rigid body world 1-250 -> 1-300' in m for m in bk),
          f"the rigid-body cache was stretched to the film's end: {bk[:1]}")
    check('T14', any('baked' in m and 'rigid body world 1-300' in m for m in bk), f'and baked 1-300: {bk[-1:]}')
    check('T14', not warns(d), 'no warnings: ' + '; '.join(r['check'] + ' ' + r['message'][:80] for r in warns(d)))
    q = query(os.path.join(OUT, 'bake.blend'), {'frames': [250, 300], 'objects': ['crate_0', 'crate_1', 'crate_2']})
    if not q:
        return check('T14', False, 'query_blend.py gave nothing')
    moved = {n: ((sum((a - b) ** 2 for a, b in zip(q['frames']['300']['objects'][n],
                                                    q['frames']['250']['objects'][n]))) ** 0.5)
             for n in ('crate_0', 'crate_1', 'crate_2')}
    check('T14', max(moved.values()) > 0.5, 'the slab knocks the crates after frame 250 (moved m, 250 -> 300): '
          + ', '.join(f'{n} {v:.2f}' for n, v in moved.items()))
    pngs = sorted(glob.glob(os.path.join(OUT, 'bake_probe_at*.png')))
    check('T14', len(pngs) == 3, f'three stills (LOOK at them): {[os.path.basename(p) for p in pngs]}')


def t15():
    plan = os.path.join(OUT, 'plan_stale.json')

    def write(size):
        with open(plan, 'w', encoding='utf-8') as f:
            json.dump({'cube_size': size}, f)
    dj = os.path.join(OUT, 'stale_build.audit.json')
    write(1.0)
    rc, _ = run(['build', STALE, '--rebuild', '--force'])
    d = digest(dj)
    inp = [r['message'] for r in records(d, 'build.inputs')]
    check('T15', rc == 0 and inp and 'plan_stale.json' in inp[0], f'the build names the plan it read: {inp[:1]}')
    rc, _ = run(['build', STALE])
    d = digest(dj)
    check('T15', rc == 0 and any('reused the build' in r['message'] for r in records(d, 'build')),
          'unchanged, the build is reused')
    write(2.0)
    rc, _ = run(['build', STALE])
    d = digest(dj)
    re_ = [r['message'] for r in records(d, 'build')]
    pl = [r['message'] for r in records(d, 'scene.plan')]
    check('T15', rc == 0 and any('inputs changed' in m and 'plan_stale.json' in m for m in re_),
          f'an edit to the plan rebuilds: {re_[:1]}')
    check('T15', pl and 'cube_size 2.0' in pl[0], f'from the new plan: {pl[:1]}')


def t16():
    for p in glob.glob(os.path.join(OUT, 'shots_probe_at*.png')):
        os.remove(p)
    rc, _ = run(['render', SHOTS, '--at', '0.5', '--at', '0.96', '--at', '1.0', '--at', '1.5', '--rebuild', '--force'])
    check('T16', rc == 0, f'two-shot build + stills exit {rc}')
    d = digest(os.path.join(OUT, 'shots_probe.audit.json'))
    check('T16', not warns(d), 'no warnings: ' + '; '.join(r['check'] + ' ' + r['message'][:80] for r in warns(d)))
    uk = records(d, 'build.unkeyed')
    check('T16', uk and uk[0]['outcome'] == 'PASS', f"nothing changed without a key: {uk[0]['message'][:100] if uk else ''}")
    fr = [r['message'] for r in records(d, 'framing') if "'cam_B'" in r['message']]
    check('T16', fr and 'kettle' in fr[0] and 'crate' not in fr[0],
          f"shot B's framing measures the kettle its camera sees, not the crate out of frame: {fr[:1]}")
    q = query(os.path.join(OUT, 'shots.blend'), {'frames': [0, 23, 24, 40], 'lights': ['lamp'],
                                                 'interp': ['crate', 'lamp']})
    if not q:
        return check('T16', False, 'query_blend.py gave nothing')
    e = {f: q['frames'][f]['lights']['lamp'] for f in ('0', '23', '24', '40')}
    check('T16', abs(e['0'] - 20) < 1e-3 and abs(e['23'] - 20) < 1e-3 and abs(e['24'] - 600) < 1e-3
          and abs(e['40'] - 600) < 1e-3, f'the saved film shows the keyed lamp step at the cut: {e}')
    crate = q['interp'].get('Object:crate', {})
    lamp = q['interp'].get('PointLight:lamp', {})
    check('T16', crate and all(v == ['LINEAR'] for v in crate.values()), f'the crate keys are LINEAR: {crate}')
    check('T16', lamp and all(v == ['CONSTANT'] for v in lamp.values()), f'the lamp keys are CONSTANT, as asked: {lamp}')
    pngs = sorted(glob.glob(os.path.join(OUT, 'shots_probe_at*.png')))
    check('T16', len(pngs) == 4, f'stills both sides of the cut (LOOK at them): {[os.path.basename(p) for p in pngs]}')


def t17():
    rc, out = run(['build', GN, '--rebuild', '--force'])
    d = digest(os.path.join(OUT, 'gn_keying_build.audit.json'))
    check('T17', rc == 0 and d['status'] == 'normal completion',
          f"a scene with a Geometry Nodes modifier builds (exit {rc}, digest '{d['status']}')")
    read = [l for l in out.splitlines() if 'grow inputs as the snapshot reads them' in l]
    check('T17', read and "Height (Socket_2)" in read[0] and "Twist (Socket_3)" in read[0],
          f"keying.node_inputs reads the modifier's inputs by their socket names: {read[0][-130:] if read else out[-300:]}")
    uk = records(d, 'build.unkeyed')
    check('T17', uk and uk[0]['outcome'] == 'PASS', f"the keyed input is not flagged: {uk[0]['message'][:100] if uk else ''}")
    path = 'modifiers["grow"].properties.inputs.Socket_2.value'
    q = query(os.path.join(OUT, 'gn_keying.blend'), {'frames': [0, 24, 47], 'paths': {'pillar': [path]},
                                                     'dims': ['pillar']})
    if not q:
        return check('T17', False, 'query_blend.py gave nothing')
    h = {f: q['frames'][f]['paths']['pillar'][path] for f in ('0', '24', '47')}
    z = {f: q['frames'][f]['dims']['pillar'][2] for f in ('0', '24', '47')}
    want = {'0': 0.5, '24': 1.5, '47': 0.5 + 47 / 24}
    check('T17', all(abs(h[f] - want[f]) < 1e-4 for f in want),
          'the saved .blend plays the keyed Height (0.5 + t): ' + ', '.join(f'frame {f} {h[f]:.3f}' for f in h))
    check('T17', all(abs(z[f] - 1.01 * want[f]) < 1e-3 for f in want),
          "and the evaluated pillar is that tall (the modifier's output, 1.01 m x Height): "
          + ', '.join(f'frame {f} {z[f]:.3f} m' for f in z))
    rc, _ = run(['build', GN_UNKEYED, '--rebuild', '--force'])
    d = digest(os.path.join(OUT, 'gn_unkeyed_build.audit.json'))
    uk = [r for r in warns(d) if r['check'] == 'build.unkeyed']
    check('T17', rc == 0 and uk and "'pillar'/'grow' input 'Twist (Socket_3)'" in uk[0]['message']
          and 'properties.inputs.Socket_3.value' in uk[0]['message'],
          f"an input set without a key is named, with the ctx.key call that fixes it: {uk[0]['message'][:240] if uk else 'no WARN'}")


def t18():
    for p in glob.glob(os.path.join(OUT, 'swept_probe_at*.png')):
        os.remove(p)
    rc, _ = run(['render', SWEPT, '--at', '0.5', '--rebuild', '--force'])
    check('T18', rc == 0, f'build + still exit {rc}')
    d = digest(os.path.join(OUT, 'swept_probe.audit.json'))
    by = {r['bodies'][0]: r for r in records(d, 'motion.swept_clearance') if r['outcome'] == 'WARN' and r['bodies']}
    b, c = by.get('rotor_B'), by.get('rotor_C')
    check('T18', b and b['bodies'] == ['rotor_B', 'mount_B'] and b['metrics']['angles_hit'] == 12
          and 'sits inside' in b['message'],
          f"rotor_B, sunk in its drum, sits inside mount_B at every angle: {b['message'][:150] if b else 'not named'}")
    check('T18', c and c['bodies'] == ['rotor_C', 'cabinet_C'] and 0 < c['metrics']['angles_hit'] < 12,
          f"rotor_C sweeps through cabinet_C at some angles: {c['message'][:150] if c else 'not named'}")
    check('T18', 'rotor_A' not in by and 'radar' not in by,
          'the clear rotor and the radar scanning short of the pole are not named: ' + str(sorted(by)))
    # the placement family sees the sunk rotor too, as a part substantially inside another at the first frame
    sunk = [r for r in warns(d) if r['check'] == 'placement.clipping' and 'mount_B / rotor_B' in r['message']]
    other = [r['check'] + ': ' + r['message'][:90] for r in warns(d)
             if r['check'] != 'motion.swept_clearance' and r not in sunk]
    check('T18', not other, 'nothing else warns on the four mechanisms (the placement family names the sunk rotor '
          f"too: {bool(sunk)}): " + ('; '.join(other) or 'none'))
    check('T18', os.path.exists(os.path.join(OUT, 'swept_probe_at0.50s.png')),
          'a still of the four mechanisms (LOOK at it)')


def _film_frame(video, idx, dst):
    subprocess.run(['ffmpeg', '-y', '-loglevel', 'error', '-i', video, '-vf', f'select=eq(n\\,{idx})', '-fps_mode',
                    'vfr', '-frames:v', '1', dst], check=True)


def _lum(path):
    import numpy as np
    from PIL import Image
    return np.asarray(Image.open(path).convert('L'), np.float64)


def t19():
    import numpy as np
    for cfg, tag, depth, want_lead in ((LEADIN, 'leadin', 1, 29), (LEADIN_CRT, 'leadin_crt', 7, 14)):
        hist = os.path.join(OUT, f'{tag}_post_history')
        shutil.rmtree(hist, ignore_errors=True)
        video = os.path.join(OUT, f'{tag}.mp4')
        rc, _ = run(['render', cfg, '--rebuild', '--force'])
        if not check('T19', rc == 0 and os.path.exists(video), f'{tag}: the film (36 frames) rendered, exit {rc}'):
            continue
        left = sorted(glob.glob(os.path.join(hist, '*', '*.exr')))
        check('T19', len(left) == depth, f"{tag}: the film pruned its records as it rendered: {len(left)} left "
              f"(the last {depth}): {[os.path.basename(p) for p in left][:8]}")
        shutil.rmtree(hist, ignore_errors=True)               # from here a still rendered alone would read nothing
        for p in glob.glob(os.path.join(OUT, f'{tag}_probe_at*.png')):
            os.remove(p)
        rc, _ = run(['render', cfg, '--at', '0.75', '--at', '1.25'])
        d = digest(os.path.join(OUT, f'{tag}_probe.audit.json'))
        cap = records(d, 'render.capture')
        lead = cap[0]['metrics'].get('lead_in_frames') if cap else None
        check('T19', rc == 0 and lead == want_lead, f'{tag}: {lead} lead-in frames rendered before the stills (want '
              f"{want_lead}): {cap[0]['message'][:230] if cap else 'no render.capture record'}")
        tmp = os.path.join(OUT, f'_t19_{tag}')
        shutil.rmtree(tmp, ignore_errors=True)
        os.makedirs(tmp)
        for idx, t in ((18, '0.75'), (30, '1.25')):
            frame = os.path.join(tmp, f'f{idx}.png')
            _film_frame(video, idx, frame)
            still = os.path.join(OUT, f'{tag}_probe_at{t}s.png')
            if not check('T19', os.path.exists(still), f'{tag}: {still} written (LOOK at it)'):
                continue
            check('T19', psnr(still, frame) > 35.0, f'{tag} --at {t} s against the film frame {idx}: PSNR '
                  f'{psnr(still, frame):.1f} dB')
        if tag == 'leadin':
            # the trail itself: where the ball was nine frames before the still, film frame 1 shows the dark wall and
            # the still shows the trail it left (a still with no records would show the wall there too)
            _film_frame(video, 9, os.path.join(tmp, 'f9.png'))
            _film_frame(video, 0, os.path.join(tmp, 'f0.png'))
            f9 = _lum(os.path.join(tmp, 'f9.png'))
            ys, xs = np.nonzero(f9 >= 0.9 * f9.max())
            y, x = int(ys.mean()), int(xs.mean())
            patch = (slice(max(0, y - 2), y + 3), slice(max(0, x - 2), x + 3))
            wall = _lum(os.path.join(tmp, 'f0.png'))[patch].mean()
            trail = _lum(os.path.join(OUT, 'leadin_probe_at0.75s.png'))[patch].mean()
            check('T19', trail > wall + 25.0, f'the still at 0.75 s holds the ball\'s trail where it was at frame 10 '
                  f'(pixel {x}, {y}): {trail:.0f} against the bare wall\'s {wall:.0f} (of 255)')
        shutil.rmtree(tmp, ignore_errors=True)


TESTS = {'T0': t0, 'T7': t7, 'T1': t1, 'T6': t6, 'T2': t2, 'T3': t3, 'T4': t4, 'T5': t5, 'T8': t8, 'T9': t9,
         'T10': t10, 'T11': t11, 'T12': t12, 'T13': t13, 'T14': t14, 'T15': t15, 'T16': t16, 'T17': t17,
         'T18': t18, 'T19': t19}

if __name__ == '__main__':
    os.makedirs(OUT, exist_ok=True)
    pick = [a.upper() for a in sys.argv[1:]] or list(TESTS)
    for name in pick:
        print(f'\n=== {name}', flush=True)
        try:
            TESTS[name]()
        except Exception as e:                                       # noqa: BLE001
            check(name, False, f'raised {type(e).__name__}: {e}')
    bad = [r for r in results if not r[1]]
    print(f'\n{len(results) - len(bad)}/{len(results)} checks passed' + (':' if bad else ''))
    for t, _, w in bad:
        print(f'  FAIL {t}: {w}')
    sys.exit(1 if bad else 0)
