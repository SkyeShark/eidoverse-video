"""Probe: the canvas screen tools without Blender (canvas_scenes: preview_screens.mjs and screens_nan_sweep.mjs, run
unchanged in Deno). System Python, from the worktree:

    python -B blender/tests/media2/test_canvas_tools.py [--only list,preview,sheet,bench,sweep]

list     list_scenes(): the fifteen scenes of the two era modules, their labels, fps, lines and lengths at 128 BPM;
         with DAISY_CUES their film starts; setTempo through --bpm (a line is 8 beats: 3.75 s at 128, 4.0 at 120)
preview  preview() at chosen u and at the default moments, with DAISY's timeline as --lyrics (captions, kicks and
         voice envelopes reach st) -> out/canvas_tools/preview/<scene>_<u>.png
sheet    sheet(): every scene, five moments each, the EEVEE renders of the same scenes (test_era_screens.py's
         out/era_*.png) shown beside each row through --refs -> out/canvas_tools/era_canvas_sheet.png
bench    bench() of three scenes at 1920 x 800 after each module's prewarm
sweep    nan_sweep(): every scene at every 60-fps frame, three canvas sizes, no caption / odd words / DAISY's
         captions; must report 0 failures (several minutes of CPU)
Prints PASS/FAIL lines for what it measures.
"""
import json
import shutil
import sys
import time
from pathlib import Path

import numpy as np
from PIL import Image

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parents[1]))
from eidoblend.media import canvas_scenes as cs  # noqa: E402

sys.stdout.reconfigure(encoding='utf-8', errors='replace')
argv = sys.argv[1:]
ONLY = set(argv[argv.index('--only') + 1].split(',')) if '--only' in argv else {'list', 'preview', 'sheet', 'bench',
                                                                                 'sweep'}
OUT = HERE / 'out' / 'canvas_tools'
TIMELINE = HERE / 'out' / 'daisy' / 'out' / 'daisy_timeline_upto_chorus2.json'
FAILS = []


def check(ok, what):
    print(f"{'PASS' if ok else 'FAIL'} {what}", flush=True)
    if not ok:
        FAILS.append(what)


def probe_list():
    t = time.time()
    rows = cs.list_scenes()
    names = [r['name'] for r in rows]
    check(len(rows) == 15, f'list_scenes: {len(rows)} scenes in {time.time() - t:.1f} s: {", ".join(names)}')
    by = {r['name']: r for r in rows}
    check(abs(by['voder_1939']['dur'] - 3.75) < 1e-9 and by['voder_1939']['lines'] in (None, 1),
          f"voder_1939: one line, {by['voder_1939']['dur']} s at 128 BPM")
    check(by['sydney_2023']['lines'] == 4 and abs(by['sydney_2023']['dur'] - 15.0) < 1e-9,
          f"sydney_2023: {by['sydney_2023']['lines']} lines, {by['sydney_2023']['dur']} s")
    check(by['sydney_tribute']['lines'] == 8 and abs(by['sydney_tribute']['dur'] - 30.0) < 1e-9,
          f"sydney_tribute: {by['sydney_tribute']['lines']} lines, {by['sydney_tribute']['dur']} s")
    check(all(r['prewarm'] for r in rows), 'both modules export prewarm()')
    for r in rows:
        print(f"    {r['name']:16s} fps {r['fps']:>3}  {r['dur']:6.2f} s  {r['label']}")
    slow = {r['name']: r for r in cs.list_scenes(bpm=120)}
    check(abs(slow['voder_1939']['dur'] - 4.0) < 1e-9 and abs(slow['sydney_2023']['dur'] - 16.0) < 1e-9,
          f"setTempo through bpm=120: voder {slow['voder_1939']['dur']} s, sydney_2023 {slow['sydney_2023']['dur']} s")
    cued = {r['name']: r for r in cs.list_scenes(cues=cs.DAISY_CUES)}
    check(all(abs(cued[n]['t0'] - t0) < 1e-9 for n, t0 in cs.DAISY_CUES.items()),
          f"cues: every scene's t0 is DAISY_CUES' (voder {cued['voder_1939']['t0']}, tribute "
          f"{cued['sydney_tribute']['t0']})")
    check(cs.scene_module('mask_2023').endswith('era_screens_2001_2023.js')
          and cs.scene_module('klatt_1984').endswith('era_screens_1939_1984.js'), 'scene_module finds each module')
    return by


def probe_preview():
    out = OUT / 'preview'
    if out.exists():
        shutil.rmtree(out)
    res = cs.preview('eliza_1966', [0.5, 2.0, 3.5], out=out, W=960, H=400, at=cs.DAISY_CUES['eliza_1966'],
                     lyrics=TIMELINE)
    check(len(res) == 3 and all(Path(r['file']).exists() for r in res),
          'preview eliza_1966 at u 0.5 / 2.0 / 3.5 with DAISY\'s captions: ' +
          ', '.join(f"u={r['u']} voice={r['voice']} kick={r['kick']} {r['ms']} ms" for r in res))
    sizes = {Image.open(r['file']).size for r in res}
    check(sizes == {(960, 400)}, f'preview size {sizes}')
    # with captions, the voice is the singer's envelope (0 between words), not the synthetic beat pulse
    check(any(r['voice'] != round(0.5 + 0.4 * abs(np.sin(np.pi * r['u'] / (60 / 128))), 2) for r in res),
          'preview: st.voice comes from the timeline\'s envelopes, not the synthetic pulse')
    a = np.asarray(Image.open(res[0]['file']).convert('L')).astype(float)
    b = np.asarray(Image.open(res[2]['file']).convert('L')).astype(float)
    check(np.abs(a - b).mean() > 1.0, f'preview: the page moves between u 0.5 and 3.5 (mean |diff| {np.abs(a - b).mean():.1f})')
    d = cs.preview('sam_1982', None, out=out, W=640, H=267, moments=3)
    check(len(d) == 3 and abs(d[0]['u'] - 0.04 * 3.75) < 0.01 and abs(d[-1]['u'] - 0.96 * 3.75) < 0.01,
          f"preview sam_1982 with the default moments: u {[x['u'] for x in d]}")
    return res


def probe_sheet():
    refs = OUT / 'refs'
    if refs.exists():
        shutil.rmtree(refs)
    refs.mkdir(parents=True)
    # the EEVEE renders of test_era_screens.py, one per scene, as the reference column (prefix = name up to the _)
    wall = sorted((HERE / 'out').glob('era_wall_0*.png'))
    curved = sorted((HERE / 'out').glob('era_curved_0*.png'))
    order1 = ['title_card', 'voder_1939', 'bell_1961', 'eliza_1966', 'speakspell_1978', 'sam_1982', 'mac_1984',
              'klatt_1984', 'glitch_all']
    order2 = ['desktop_2001', 'vocaloid_2007', 'flood_2016', 'mask_2023', 'sydney_2023', 'sydney_tribute']
    n_ref = 0
    for names, files in ((order1, wall), (order2, curved)):
        for i, n in enumerate(names):
            k = 3 * i + 1                                    # the middle of the scene's three moments
            if k < len(files):
                shutil.copyfile(files[k], refs / f"{n.split('_')[0]}_{n}_eevee.png")
                n_ref += 1
    png = cs.sheet(OUT / 'era_canvas_sheet.png', moments=4, W=1920, H=800, cues=cs.DAISY_CUES, lyrics=TIMELINE,
                   refs=refs)
    im = Image.open(png)
    check(png.exists() and im.size[1] > 15 * 200, f'sheet: {im.size[0]} x {im.size[1]} with {n_ref} EEVEE reference '
                                                    f'renders beside the rows')
    return png


def probe_bench():
    t = time.time()
    b = cs.bench(['voder_1939', 'mac_1984', 'desktop_2001'], W=1920, H=800)
    ok = len(b['scenes']) == 3 and len(b['prewarm_ms']) == 2 and all(v['mean'] > 0 for v in b['scenes'].values())
    check(ok, f"bench in {time.time() - t:.0f} s: prewarm {b['prewarm_ms']} ms; " + '; '.join(
        f"{k} mean {v['mean']} p90 {v['p90']} first {v['first']} ms" for k, v in b['scenes'].items()))
    return b


def probe_sweep():
    t = time.time()
    r = cs.nan_sweep(lyrics=TIMELINE, cues=cs.DAISY_CUES)
    check(r['ok'] and r.get('failures') == 0 and r.get('scenes') == 15,
          f"nan_sweep: {r.get('draws')} draws of {r.get('scenes')} scenes, {r.get('calls')} guarded calls, "
          f"{r.get('failures')} failures ({time.time() - t:.0f} s)")
    if not r['ok']:
        print(r['log'])
    return r


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    check(TIMELINE.exists(), f'DAISY timeline present ({TIMELINE.name})')
    res = {}
    if 'list' in ONLY:
        probe_list()
    if 'preview' in ONLY:
        probe_preview()
    if 'sheet' in ONLY:
        probe_sheet()
    if 'bench' in ONLY:
        res['bench'] = probe_bench()
    if 'sweep' in ONLY:
        s = probe_sweep()
        res['sweep'] = {k: v for k, v in s.items() if k != 'log'}
    (OUT / 'canvas_tools_results.json').write_text(json.dumps(res, indent=1), encoding='utf-8')
    print(f'[test_canvas_tools] {"ALL OK" if not FAILS else f"{len(FAILS)} FAILED"}', flush=True)
    sys.exit(1 if FAILS else 0)


main()
