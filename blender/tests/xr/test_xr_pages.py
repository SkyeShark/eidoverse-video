"""tests/xr/test_xr_pages.py: the exported bundles in the kit's page, photographed by eidoverse/xr/shot.mjs (headless
Chrome, the WebGL2 backend the headset uses), compared with EEVEE and with the original example page.

    python blender/tests/xr/test_xr_pages.py          (after test_xr_city.py and test_xr_features.py; a GPU job:
                                                       run it through heavy.sh like a render)
Checks:
  - every still renders ('ready'), with no exception or console error
  - the city page: one 30 s clip, the grid drawn by the page's own material, the world dome; the kit's street view
    (WorldRig.standAt at stage (0, 0, 10)) IS cam_street and the desktop table view IS cam_table (the same pixels);
    the page through cam_street matches EEVEE's cam_street still; the street view matches the original example.html
  - the features page: through cam_film at t = 1, 2.5, 4 s it matches EEVEE's stills (lit, AgX, shadows on)
  - the kit check page (kit_check.html): every xr_kit export exercised on the exported stage
  - telemetry: each page's 'ready' report reached the server's log, from the WebGL2 backend
Side-by-side sheets go to out/pages/ (look at them: the numbers only say the pictures agree).
"""
import json
import os
import sys

import numpy as np
from PIL import Image, ImageDraw

HERE = os.path.dirname(os.path.abspath(__file__))
WORKTREE = os.path.abspath(os.path.join(HERE, '..', '..', '..'))
sys.path.insert(0, os.path.join(WORKTREE, 'blender'))
OUT = os.path.join(HERE, 'out', 'pages')
os.makedirs(OUT, exist_ok=True)
MAIN_NODE_MODULES = os.path.abspath(os.path.join(WORKTREE, '..', 'eidoverse-video-prealpha-0.01', 'node_modules'))
SIZE = (960, 540)
# one bundle is shot with the browser named explicitly (shots.shoot's chrome=, shot.mjs's CHROME); the rest find it
CHROME = next((p for p in (r'C:\Program Files\Google\Chrome\Application\chrome.exe', '/usr/bin/google-chrome',
                           '/Applications/Google Chrome.app/Contents/MacOS/Google Chrome') if os.path.exists(p)), None)

from eidoblend.xr import server, shots  # noqa: E402

RESULTS = []


def check(name, ok, detail=''):
    RESULTS.append((name, bool(ok), detail))
    print(f"[check] {'PASS' if ok else 'FAIL'} {name}{': ' + str(detail) if detail else ''}", flush=True)


def load(p, size=SIZE):
    im = Image.open(p).convert('RGB')
    if im.size != size:
        im = im.resize(size, Image.LANCZOS)
    return im


def mad(a, b, grid=(96, 54)):
    """Mean absolute difference (0..1) of two stills, area-averaged to a coarse grid (small shifts, noise and
    antialiasing average out; a missing object, a wrong axis or a wrong exposure does not)."""
    x = np.asarray(load(a).resize(grid, Image.BOX), dtype=np.float32) / 255.0
    y = np.asarray(load(b).resize(grid, Image.BOX), dtype=np.float32) / 255.0
    return float(np.abs(x - y).mean())


def sheet(paths, labels, out, cols=None):
    ims = [load(p).resize((480, 270), Image.LANCZOS) for p in paths]
    cols = cols or len(ims)
    rows = (len(ims) + cols - 1) // cols
    S = Image.new('RGB', (cols * 484, rows * 292), (20, 20, 24))
    d = ImageDraw.Draw(S)
    for i, (im, lab) in enumerate(zip(ims, labels)):
        x, y = (i % cols) * 484, (i // cols) * 292
        S.paste(im, (x, y + 20))
        d.text((x + 4, y + 4), lab, fill=(235, 235, 235))
    S.save(out)
    return out


def ready(rows, label, planted=()):
    """Every still 'ready', no exception or console error (but the `planted` ones a page throws on purpose)."""
    ok = all(r['status'] == 'ready' for r in rows) and len(rows) > 0
    errs = [e for r in rows for e in r['errors'] if ('EXCEPTION' in e or 'console.error' in e)
            and not any(p in e for p in planted)]
    check(f'{label}: every still rendered, no exception or console error', ok and not errs,
          '; '.join(f"{r['query']}={r['status']}" for r in rows) + (f' errors: {errs[:3]}' if errs else ''))
    return {r['query']: r for r in rows}


log = os.path.join(OUT, 'reports.jsonl')
if os.path.exists(log):
    os.remove(log)
srv = server.start(http_port=0, log=log, node_modules=MAIN_NODE_MODULES)
city_vr = os.path.join(HERE, 'out', 'city', 'vr')
feat_vr = os.path.join(HERE, 'out', 'features', 'vr')
try:
    U = srv.url
    # ------------------------------------------------------------------------- the original and the city ---
    orig = ready(shots.shoot(U + '/eidoverse/xr/example.html', os.path.join(OUT, 'original'),
                             ['t=4&street=0,10', 't=4&view=table'], size=SIZE), 'example.html (the original)')
    city = ready(shots.shoot(U + '/blender/tests/xr/out/city/vr/index.html', os.path.join(OUT, 'city'),
                             ['t=4&street=0,10', 't=4&view=table', 't=4&camera=cam_street', 't=4&camera=cam_table',
                              't=4&street=0,10&look=30&pitch=5', 't=12&street=0,4&look=-60&pitch=-20'], size=SIZE),
                 'the city bundle')
    info = city['t=4&street=0,10']['info'] or {}
    check('city page: one 30 s clip, the page grid, the world dome, no tone curve (Standard), drawn (triangles, draws)',
          info.get('clips') == 1 and abs(info.get('duration', 0) - 30) < 0.05 and info.get('pageMaterials') == 1
          and info.get('world') is True and info.get('toneMapping') == 'None' and info.get('tris', 0) > 0
          and info.get('calls', 0) > 0, info)
    c = lambda q: city[q]['path']                                        # noqa: E731
    m_s = mad(c('t=4&street=0,10'), c('t=4&camera=cam_street'))
    check("WorldRig.standAt(stage (0, 0, 10)) at 0.25 m a unit IS Blender's cam_street", m_s < 0.006, f'MAD {m_s:.4f}')
    m_t = mad(c('t=4&view=table'), c('t=4&camera=cam_table'))
    check("the desktop table view (WorldRig.toTable at 1 cm a unit) IS Blender's cam_table", m_t < 0.006, f'MAD {m_t:.4f}')
    ev_s = os.path.join(HERE, 'out', 'city', 'eevee_cam_street_t4.png')
    ev_t = os.path.join(HERE, 'out', 'city', 'eevee_cam_table_t4.png')
    m_e = mad(c('t=4&camera=cam_street'), ev_s)
    check("the page through cam_street matches EEVEE's still (same set, same time, Standard)", m_e < 0.03, f'MAD {m_e:.4f}')
    m_et = mad(c('t=4&camera=cam_table'), ev_t)
    check("the page through cam_table matches EEVEE's still", m_et < 0.03, f'MAD {m_et:.4f}')
    m_o = mad(c('t=4&street=0,10'), orig['t=4&street=0,10']['path'])
    check('the city page matches the original example.html (street; the window draw differs: other hash)', m_o < 0.06,
          f'MAD {m_o:.4f}')
    m_ot = mad(c('t=4&view=table'), orig['t=4&view=table']['path'])
    check('the city page matches the original example.html (table)', m_ot < 0.04, f'MAD {m_ot:.4f}')
    sheet([orig['t=4&street=0,10']['path'], c('t=4&street=0,10'), ev_s,
           orig['t=4&view=table']['path'], c('t=4&view=table'), ev_t],
          ['example.html (original) street t=4', 'Blender export in the kit page, street t=4', 'EEVEE cam_street t=4',
           'example.html table t=4', 'Blender export in the kit page, table t=4', 'EEVEE cam_table t=4'],
          os.path.join(OUT, 'sheet_city_original_page_eevee.png'), cols=3)
    sheet([c('t=4&street=0,10&look=30&pitch=5'), c('t=12&street=0,4&look=-60&pitch=-20')],
          ['page street 0,10 look 30 pitch 5', 'page t=12 street 0,4 look -60 pitch -20'],
          os.path.join(OUT, 'sheet_city_more_views.png'))

    # ---------------------------------------------------------------------------------------- the features ---
    if os.path.exists(os.path.join(feat_vr, 'scene.glb')):
        qs = [f't={t:g}&camera=cam_film&shadows=1' for t in (1.0, 2.5, 4.0)] + \
             ['t=2.5&shadows=1', 't=2.5&view=table&shadows=1', 't=2.5&face=90&shadows=1', 't=2.5&look=-90&shadows=1']
        feat = ready(shots.shoot(U + '/blender/tests/xr/out/features/vr/index.html', os.path.join(OUT, 'features'), qs,
                                 size=SIZE, timeout=90), 'the features bundle')
        fi = feat[qs[0]]['info'] or {}
        check('features page: one clip, the rect light, the world, AgX', fi.get('clips') == 1 and fi.get('rect') == 1
              and fi.get('world') is True and fi.get('toneMapping') == 'AgX', fi)
        paths, labels = [], []
        for t in (1.0, 2.5, 4.0):
            q = f't={t:g}&camera=cam_film&shadows=1'
            ev = os.path.join(HERE, 'out', 'features', f'eevee_cam_film_t{t:g}.png')
            m = mad(feat[q]['path'], ev)
            check(f'features: the page through cam_film at t = {t:g} matches EEVEE', m < 0.08, f'MAD {m:.4f}')
            paths += [ev, feat[q]['path']]
            labels += [f'EEVEE cam_film t={t:g}', f'kit page cam_film t={t:g} (WebGL2)']
        sheet(paths, labels, os.path.join(OUT, 'sheet_features_eevee_vs_page.png'), cols=2)
        m = mad(feat['t=2.5&face=90&shadows=1']['path'], feat['t=2.5&look=-90&shadows=1']['path'])
        check('turning the stage (face=90) shows what turning the head does (look=-90): the sky and its light turn '
              'with the stage', m < 0.006, f'MAD {m:.4f}')
        sheet([feat['t=2.5&shadows=1']['path'], feat['t=2.5&view=table&shadows=1']['path'],
               feat['t=2.5&face=90&shadows=1']['path'], feat['t=2.5&look=-90&shadows=1']['path']],
              ['page street (start 0,-4 facing +Y) t=2.5', 'page table (1:25) t=2.5',
               'stage turned: face=90', 'head turned: look=-90'],
              os.path.join(OUT, 'sheet_features_street_table.png'), cols=2)
    else:
        check('the features bundle exists (run test_xr_features.py first)', False)

    # ------------------------------------------------------------- real films round one built (test_xr_films.py)
    films_json = os.path.join(HERE, 'out', 'films', 'films.json')
    films = json.load(open(films_json)) if os.path.exists(films_json) else {}
    if not films:
        check('the film bundles exist (run test_xr_films.py first)', False)
    for name, fm in films.items():
        cam, times = fm['camera'], fm['times']
        qs = [f't={t:g}&camera={cam}&shadows=1' for t in times] + [f't={times[1]:g}', f't={times[1]:g}&view=table']
        rows = ready(shots.shoot(f"{U}/{fm['bundle']}/index.html", os.path.join(OUT, 'films', name), qs, size=SIZE,
                                 timeout=120, chrome=CHROME if name == 'example' else None), f'film {name}')
        info = rows[qs[0]]['info'] or {}
        check(f'film {name}: the page plays its clip (if it moves), its rect lights, its world, {fm["tone_mapping"]}',
              info.get('rect') == fm['rect_lights'] and info.get('world') is True
              and info.get('toneMapping') == fm['tone_mapping']
              and (info.get('clips', 0) >= 1) == (fm['counts']['duration'] > 0), info)
        paths, labels = [], []
        for t in times:
            q = f't={t:g}&camera={cam}&shadows=1'
            ev = os.path.join(WORKTREE, fm['eevee'][f'{t:g}'])
            m = mad(rows[q]['path'], ev)
            check(f'film {name}: the page through {cam} at t = {t:g} matches EEVEE', m < 0.08, f'MAD {m:.4f}')
            paths += [ev, rows[q]['path']]
            labels += [f'EEVEE {name} {cam} t={t:g}', f'kit page {name} {cam} t={t:g}']
        sheet(paths, labels, os.path.join(OUT, f'sheet_film_{name}_eevee_vs_page.png'), cols=2)
        sheet([rows[qs[-2]]['path'], rows[qs[-1]]['path']],
              [f'{name}: kit page street (the start) t={times[1]:g}', f'{name}: kit page table t={times[1]:g}'],
              os.path.join(OUT, f'sheet_film_{name}_street_table.png'))

    # ---------------------------------------------------- compressed bundles (export_cli: meshopt + WebP, Draco + JPEG)
    for tag, ext in (('vr_meshopt_webp', ('EXT_meshopt_compression', 'EXT_texture_webp')),
                     ('vr_draco_jpeg', ('KHR_draco_mesh_compression',))):
        d = os.path.join(HERE, 'out', 'city', tag)
        if not os.path.exists(os.path.join(d, 'scene.glb')):
            check(f'{tag}: the CLI bundle exists (run export_cli first)', False)
            continue
        from eidoblend.xr import glb as G                                  # noqa: E402
        s = G.summary(G.read(os.path.join(d, 'scene.glb')))
        check(f'{tag}: the GLB declares {", ".join(ext)}', all(e in s['extensions_used'] for e in ext),
              s['extensions_used'])
        rows = ready(shots.shoot(U + f'/blender/tests/xr/out/city/{tag}/index.html', os.path.join(OUT, tag),
                                 ['t=4&camera=cam_street'], size=SIZE), f'{tag} page')
        m = mad(rows['t=4&camera=cam_street']['path'], c('t=4&camera=cam_street'))
        check(f'{tag}: the page decodes it and draws the same picture', m < 0.012, f'MAD {m:.4f} vs the plain bundle')

    # --------------------------------------------------------------- the error path and shots.py's command line
    bad = shots.shoot(U + '/blender/eidoblend/xr/page/xr_page.html', os.path.join(OUT, 'error'), ['t=1'], size=(480, 270))
    check("a page that fails says so: window.__shot = 'error: ...' (the template has no manifest beside it)",
          bad and bad[0]['status'].startswith('error'), bad and bad[0]['status'])
    import subprocess                                                        # noqa: E402
    r = subprocess.run([sys.executable, os.path.join(WORKTREE, 'blender', 'eidoblend', 'xr', 'shots.py'),
                        U + '/blender/tests/xr/out/city/vr/index.html', os.path.join(OUT, 'cli'), 't=8&view=table',
                        '--size', '480x270', '--timeout', '30'], capture_output=True, text=True)
    check('shots.py from its command line: exit 0, the still written', r.returncode == 0
          and os.path.exists(os.path.join(OUT, 'cli', shots.still_name('t=8&view=table'))), r.returncode)

    # ----------------------------------------------------------------------------------------- the kit check ---
    kc = ready(shots.shoot(U + '/blender/tests/xr/kit_check.html', os.path.join(OUT, 'kit'), ['check=1'], size=SIZE,
                           timeout=90), 'kit_check.html', planted=('kit_check planted',))
    ki = kc['check=1']['info'] or {}
    for r in ki.get('results', []):
        check(f"xr_kit: {r['name']}", r['ok'], r['detail'])
    check('xr_kit: every export exercised, none failed', ki.get('fail') == 0 and ki.get('pass', 0) >= 60,
          f"{ki.get('pass')} passed, {ki.get('fail')} failed {ki.get('error', '')}")
finally:
    srv.stop()

# ------------------------------------------------------------------------------------------------ telemetry ---
lines = [json.loads(x) for x in open(log, encoding='utf-8')] if os.path.exists(log) else []
tags = {r.get('test') for r in lines if r.get('phase') == 'ready' and r.get('backend') == 'WebGL2'}
check("telemetry: the pages' 'ready' reports reached the server log, backend WebGL2",
      {'xr_example', 'xr_city', 'xr_features'} <= tags, sorted(t for t in tags if t))
kl = [r for r in lines if r.get('test') == 'xr_kit_check']
check('telemetry: the kit check reported', any(r.get('phase') == 'kit_check' for r in kl))
errs = [r for r in kl if r.get('phase') == 'error']
check('telemetry: an uncaught error and an unhandled rejection reach the log with their stacks',
      any('planted error' in r.get('error', '') and 'kit_check.html' in r.get('stack', '') for r in errs)
      and any('planted rejection' in r.get('error', '') and r.get('stack') for r in errs),
      [(r.get('error'), r.get('at')) for r in errs])
for phase, what in (('sessionarmed', "a stand-in session's arming"), ('measured', 'its measured fps'),
                    ('hb', 'its heartbeats'), ('contextlost', 'a lost WebGL context')):
    check(f'telemetry: {what} reached the log (phase {phase}, stamped by the server)',
          any(r.get('phase') == phase and r.get('at_server') for r in kl), phase)
n_fail = sum(1 for _, ok, _ in RESULTS if not ok)
print(f'[check] {len(RESULTS) - n_fail} passed, {n_fail} failed', flush=True)
sys.exit(1 if n_fail else 0)
