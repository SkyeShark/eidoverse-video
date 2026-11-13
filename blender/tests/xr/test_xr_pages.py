"""tests/xr/test_xr_pages.py: the exported bundles in the kit's page, photographed by eidoverse/xr/shot.mjs (headless
Chrome, the WebGL2 backend the headset uses), compared with EEVEE and with the original example page.

    python blender/tests/xr/test_xr_pages.py          (after test_xr_city.py and test_xr_features.py; a GPU job:
                                                       run it through heavy.sh like a render)
Checks:
  - every still renders ('ready'), with no exception or console error
  - the city page: one 30 s clip, the grid drawn by the page's own material, the world dome; the kit's street view
    (WorldRig.standAt at stage (0, 0, 10)) IS cam_street and the desktop table view IS cam_table (the same pixels);
    the page through cam_street matches EEVEE's cam_street still; the street view matches the original example.html
    (pixel by pixel with the lit windows painted out, their draw being another hash's, and as many lit windows)
  - the features page: through cam_film at t = 1, 2.5, 4 s it matches EEVEE's stills (lit, AgX, shadows on), and
    the key area light's keyed energy is on its RectAreaLight at those times; its 1:25 table view matches EEVEE
    through cam_table_view at life size (the page keeps its lights' look at any stage scale), with point / spot
    intensity x s^2 and the area light s times its size; turning the stage turns its sky and light
  - the films test_xr_films.py exported (example, crows, robot_walk, stage: those whose inputs were there): through
    the camera each shows at each time they match EEVEE's stills
  - a sun left at the origin casts its shadows on the page as in EEVEE, and a bump baked on a mesh with its own UV map
    lights the same slopes (test_xr_tangents_shadows.py's bundle)
  - the compressed CLI bundles decode (meshopt + WebP, Draco + JPEG); the --no-world one's sky is the world's mean
    radiance, measured at export
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


WINDOW_TOWER = np.array([0x1a, 0x16, 0x26], np.float32) / 255.0      # example.html's unlit tower colour


def windows_out(p):
    """A city still with its lit windows painted the tower colour (as float RGB): the page and EEVEE light another
    hash's draw of the windows than example.html (PCG there, White Noise here), at the same density, so the windows
    are compared by their count and everything else pixel by pixel."""
    a = np.asarray(load(p), dtype=np.float32) / 255.0
    lit = (a[..., 0] > 0.8) & (a[..., 1] > 0.7)
    out = a.copy()
    out[lit] = WINDOW_TOWER
    return out, int(lit.sum())


def coarse_mad(a, b, grid=(96, 54)):
    """mad() of two float RGB arrays."""
    f = lambda x: np.asarray(Image.fromarray((np.clip(x, 0, 1) * 255).astype(np.uint8)).resize(grid, Image.BOX),  # noqa
                             dtype=np.float32) / 255.0
    return float(np.abs(f(a) - f(b)).mean())


def srgb(c):
    return [12.92 * x if x <= 0.0031308 else 1.055 * x ** (1 / 2.4) - 0.055 for x in c]


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
    a_, n_page = windows_out(c('t=4&street=0,10'))
    b_, n_orig = windows_out(orig['t=4&street=0,10']['path'])
    m_ow = coarse_mad(a_, b_)
    check('the city page matches the original example.html (street): the same towers, ground, walkers and sky pixel '
          'by pixel with the lit windows painted out, and as many lit windows (their draw is another hash)',
          m_ow < 0.02 and abs(n_page - n_orig) < 0.15 * n_orig,
          f'MAD {m_ow:.4f} windows out ({m_o:.4f} with them); lit-window pixels {n_page} vs {n_orig}')
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
        # (the heaviest page: a 57 MB GLB, two casts, 4K bakes, shadows; on a shared GPU its first still has taken
        # two minutes to compile and draw)
        feat = ready(shots.shoot(U + '/blender/tests/xr/out/features/vr/index.html', os.path.join(OUT, 'features'), qs,
                                 size=SIZE, timeout=240), 'the features bundle')
        fi = feat[qs[0]]['info'] or {}
        check('features page: one clip, the rect light, the world, AgX', fi.get('clips') == 1 and fi.get('rect') == 1
              and fi.get('world') is True and fi.get('toneMapping') == 'AgX', fi)
        paths, labels = [], []
        ch = json.load(open(os.path.join(feat_vr, 'choreo.json')))
        ktr = ch.get('props', {}).get('lights', {}).get('key')
        for t in (1.0, 2.5, 4.0):
            q = f't={t:g}&camera=cam_film&shadows=1'
            ev = os.path.join(HERE, 'out', 'features', f'eevee_cam_film_t{t:g}.png')
            m = mad(feat[q]['path'], ev)
            check(f'features: the page through cam_film at t = {t:g} matches EEVEE', m < 0.08, f'MAD {m:.4f}')
            got = ((feat[q]['info'] or {}).get('rectIntensity') or {}).get('key')
            want = ktr and ktr['intensity'][min(range(len(ktr['t'])), key=lambda k: abs(ktr['t'][k] - t))]
            check(f"features: the key area light's keyed energy plays on the page's RectAreaLight at t = {t:g}",
                  got is not None and want is not None and abs(got - want) < 1e-3 * max(1.0, want), (got, want))
            paths += [ev, feat[q]['path']]
            labels += [f'EEVEE cam_film t={t:g}', f'kit page cam_film t={t:g} (WebGL2)']
        sheet(paths, labels, os.path.join(OUT, 'sheet_features_eevee_vs_page.png'), cols=2)
        # the table (1:25): the page's lights must look as they do at life size (relight: point / spot x s^2, the area
        # light s times its size), so the page's table view is EEVEE through cam_table_view (the same view, life size)
        tq = 't=2.5&view=table&shadows=1'
        ti = feat[tq]['info'] or {}
        ev_tv = os.path.join(HERE, 'out', 'features', 'eevee_cam_table_view_t2.5.png')
        if os.path.exists(ev_tv):
            m = mad(feat[tq]['path'], ev_tv)
            check("features: the page's table view (1:25) matches EEVEE through cam_table_view at life size (the "
                  'lights keep their look at the table scale)', m < 0.08, f'MAD {m:.4f}')
            sheet([ev_tv, feat[tq]['path']], ['EEVEE cam_table_view t=2.5 (life size, 25x farther)',
                                              'kit page view=table t=2.5 (the stage at 1:25)'],
                  os.path.join(OUT, 'sheet_features_table_eevee_vs_page.png'))
        else:
            check('the EEVEE table-view still exists (test_xr_features.py)', False, ev_tv)
        s_ = ti.get('stageScale')
        pts = ti.get('pointIntensity') or {}
        rsz = (ti.get('rectSize') or {}).get('key')
        check('features: at the table scale (0.04) the point and spot lights shine with intensity x s^2 and the area '
              'light is s times its size; in the street (s = 1) as exported',
              s_ is not None and abs(s_ - 0.04) < 1e-9 and len(pts) >= 2
              and all(abs(v[0] - v[1] * s_ * s_) <= 1e-4 * abs(v[1] * s_ * s_) + 1e-12 for v in pts.values())
              and rsz is not None and abs(rsz[0] - s_) < 1e-4 and abs(rsz[1] - s_) < 1e-4
              and (feat['t=2.5&shadows=1']['info'] or {}).get('stageScale') == 1
              and all(abs(v[0] - v[1]) <= 1e-4 * abs(v[1]) + 1e-12
                      for v in ((feat['t=2.5&shadows=1']['info'] or {}).get('pointIntensity') or {}).values()),
              f'stage scale {s_}, {pts}, rect {rsz}')
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

    # ------------------------------------------------- the real films test_xr_films.py exported (out/films/films.json)
    films_json = os.path.join(HERE, 'out', 'films', 'films.json')
    films = json.load(open(films_json)) if os.path.exists(films_json) else {}
    if not films:
        check('the film bundles exist (run test_xr_films.py first)', False)
    for name, fm in films.items():
        times = fm['times']
        cam_at = lambda t: fm.get('cameras', {}).get(f'{t:g}', fm['camera'])     # noqa: E731 (a film's camera cuts)
        qs = [f't={t:g}&camera={cam_at(t)}&shadows=1' for t in times] + [f't={times[1]:g}', f't={times[1]:g}&view=table']
        rows = ready(shots.shoot(f"{U}/{fm['bundle']}/index.html", os.path.join(OUT, 'films', name), qs, size=SIZE,
                                 timeout=120, chrome=CHROME if name == 'example' else None), f'film {name}')
        info = rows[qs[0]]['info'] or {}
        check(f'film {name}: the page plays its clip (if it moves), its rect lights, its world, {fm["tone_mapping"]}',
              info.get('rect') == fm['rect_lights'] and info.get('world') is True
              and info.get('toneMapping') == fm['tone_mapping']
              and (info.get('clips', 0) >= 1) == (fm['counts']['duration'] > 0), info)
        paths, labels = [], []
        for t in times:
            cam = cam_at(t)
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

    # ------------------------- a UV-mapped bumped set lit by a sun left at the origin (test_xr_tangents_shadows.py)
    ts = os.path.join(HERE, 'out', 'tangents_shadows')
    if os.path.exists(os.path.join(ts, 'vr', 'scene.glb')):
        pp = json.load(open(os.path.join(ts, 'probe_points.json')))
        tq = ['t=0&camera=cam_probe&shadows=1', 't=0&view=table&shadows=1']
        rows = ready(shots.shoot(U + '/blender/tests/xr/out/tangents_shadows/vr/index.html',
                                 os.path.join(OUT, 'tangents_shadows'), tq, size=SIZE, timeout=120),
                     'the tangents / sun-shadow bundle')
        ev, pg = os.path.join(ts, 'eevee_cam_probe_t0.png'), rows[tq[0]]['path']

        def luma(p):
            return np.asarray(load(p), dtype=np.float32) @ np.array([0.2126, 0.7152, 0.0722], np.float32) / 255.0

        def patch(a, xy, r=5):
            x, y = int(round(xy[0])), int(round(xy[1]))
            return float(a[y - r:y + r + 1, x - r:x + r + 1].mean())

        le, lp = luma(ev), luma(pg)
        r_e = patch(le, pp['pixels']['shaded']) / max(patch(le, pp['pixels']['lit']), 1e-6)
        r_p = patch(lp, pp['pixels']['shaded']) / max(patch(lp, pp['pixels']['lit']), 1e-6)
        check("a sun left at the origin: the pillar's shadow lies on the page's ground as in EEVEE (shaded / lit ground "
              'at the same x)', r_p < 0.6 and abs(r_p - r_e) < 0.2, f'EEVEE {r_e:.2f}, page {r_p:.2f}')

        def ridges(a, y, x0=500, x1=900, smooth=151):
            """The ridges' light and shade across the ground along a row (the slow trend taken out)."""
            row = a[y - 2:y + 3, x0:x1].mean(0)
            k = np.ones(smooth, np.float32) / smooth
            return row - np.convolve(np.pad(row, smooth // 2, mode='edge'), k, mode='valid')

        corr, amp = [], []
        for y in (420, 470, 510):                    # rows across the near ground, clear of shadows
            re_, rp_ = ridges(le, y), ridges(lp, y)
            corr.append(float(np.corrcoef(re_, rp_)[0, 1]))
            amp.append(float(rp_.std() / max(re_.std(), 1e-6)))
        check('the baked bump on a mesh with its own UV map: the low sun lights the same slopes of the ridges on the page '
              'as in EEVEE (bumps not read as dents), as strongly', min(corr) > 0.6 and all(0.6 < k < 1.6 for k in amp),
              f'row correlation {[round(c, 2) for c in corr]}, contrast page / EEVEE {[round(k, 2) for k in amp]}')
        m = mad(pg, ev)
        check('the bumped ground and ball, the pillar and the box through cam_probe match EEVEE', m < 0.06, f'MAD {m:.4f}')
        ti = rows[tq[0]]['info'] or {}
        check("the page's sun shadow box is fitted round the set (a negative near: the set stands behind the light) and "
              'its textures are filtered anisotropically', ti.get('sunShadow') and ti['sunShadow'][0][4] < 0
              and (ti.get('anisotropy') or 0) >= 4, (ti.get('sunShadow'), ti.get('anisotropy')))
        sheet([ev, pg, rows[tq[1]]['path']], ['EEVEE cam_probe (sun at the origin, own-UV bump)',
                                              'kit page cam_probe, shadows=1', 'kit page table (1:x), shadows=1'],
              os.path.join(OUT, 'sheet_tangents_shadows_eevee_vs_page.png'))
    else:
        check('the tangents / sun-shadow bundle exists (run test_xr_tangents_shadows.py first)', False)

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
        got, plain = rows['t=4&camera=cam_street']['path'], c('t=4&camera=cam_street')
        mc = json.load(open(os.path.join(d, 'scene.xr.json')))
        if mc.get('world'):
            m = mad(got, plain)
            check(f'{tag}: the page decodes it and draws the same picture', m < 0.012, f'MAD {m:.4f} vs the plain bundle')
            continue
        # exported --no-world: the sky is the world's flat colour (its mean radiance, measured at export); the rest of
        # the picture is the plain bundle's
        A = np.asarray(load(got), dtype=np.float32) / 255.0
        B = np.asarray(load(plain), dtype=np.float32) / 255.0
        bg = np.array(srgb(mc['background']), np.float32)              # the city is drawn without a tone curve
        sky = np.all(np.abs(A - bg) < 3.5 / 255.0, axis=-1)
        import cv2                                                         # noqa: E402
        hdr = cv2.imread(os.path.join(city_vr, 'world.hdr'), cv2.IMREAD_ANYDEPTH | cv2.IMREAD_COLOR)[..., ::-1]
        lat = (0.5 - (np.arange(hdr.shape[0]) + 0.5) / hdr.shape[0]) * np.pi       # rows top to bottom
        wt = np.cos(lat)[:, None, None]
        want = (hdr * wt).sum((0, 1)) / (wt.sum() * hdr.shape[1])
        rel = float(np.abs(np.array(mc['background']) - want).max() / max(float(want.max()), 1e-6))
        check(f"{tag}: --no-world: the sky is the world's flat colour, its mean radiance measured at export (the plain "
              "bundle's world.hdr averaged over the sphere)", mc['world'] is None and sky.mean() > 0.05 and rel < 0.1,
              f"{[round(x, 4) for x in mc['background']]} vs {[round(float(x), 4) for x in want]} ({rel:.1%}); "
              f'{sky.mean():.0%} of the still is that sky')
        A2 = A.copy()
        A2[sky] = B[sky]
        m = coarse_mad(A2, B)
        check(f'{tag}: the page decodes it and draws the same set (sky aside)', m < 0.012,
              f'MAD {m:.4f} vs the plain bundle ({mad(got, plain):.4f} with the sky)')

    # ------------------------------------- the CLI options bundle (export_cli on the features set: --street 0.5,
    # --shadows, --no-bake, --no-motion, --no-world, --max-image 512): photographed to look at, its settings read back
    vc = os.path.join(HERE, 'out', 'features', 'vr_cli')
    if os.path.exists(os.path.join(vc, 'scene.glb')):
        rows = ready(shots.shoot(U + '/blender/tests/xr/out/features/vr_cli/index.html', os.path.join(OUT, 'vr_cli'),
                                 ['t=2.5&camera=cam_film', 't=2.5'], size=SIZE, timeout=240), 'the CLI options bundle')
        vi = rows['t=2.5']['info'] or {}
        check('the CLI options bundle: no world dome; its measured flat sky lights it as a uniform environment (metals '
              'reflect it); shadows on (its settings); the street at 0.5 m a unit (the stage at 0.5)',
              vi.get('world') is False and vi.get('environment') == 'uniform' and vi.get('shadows') is True
              and vi.get('stageScale') == 0.5, vi)
        sheet([os.path.join(HERE, 'out', 'features', 'eevee_cam_film_t2.5.png'), rows['t=2.5&camera=cam_film']['path'],
               rows['t=2.5']['path']],
              ['EEVEE cam_film t=2.5 (the full export)', 'CLI: no bake / motion / world, 512 px, cam_film t=2.5',
               'CLI: street at 0.5 m a unit, start 1,-3 facing +x'], os.path.join(OUT, 'sheet_cli_options.png'))
    else:
        check('the CLI options bundle exists (run_all.sh cli)', False, vc)

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
