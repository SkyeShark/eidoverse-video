#!/usr/bin/env python3
"""eidoblend.xr.shots: stills of a WebXR page from headless Chrome, through eidoverse/xr/shot.mjs. Plain Python.

shot.mjs carries over as it is (the same WebGL2 backend the headset uses; one still per query; window.__shot is the
page's 'ready' / 'error: ...' flag and window.__shotInfo its numbers). This runs it and reads its report back:

    from eidoblend.xr import server, shots
    with server.start() as srv:
        rows = shots.shoot(srv.url + '/work/<id>/vr/index.html', 'work/<id>/vr/shots',
                           ['t=4&street=0,10', 't=4&view=table'], size=(960, 540))
    for r in rows: print(r['query'], r['status'], r['path'], r['info'])

    python blender/eidoblend/xr/shots.py <page-url> <out-dir> "query" ["query" ...] [--size 960x540]

Each row: query, status ('ready', 'error: ...' or 'TIMEOUT'), seconds, path (the PNG), info (window.__shotInfo as a
dict, or None), errors (the page's exceptions and console errors / warnings printed under that still).
A GPU job on a shared machine: run it through the GPU slot (heavy.sh) like any render.
"""
from __future__ import annotations

import argparse
import json
import os
import re
import shutil
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.normpath(os.path.join(HERE, '..', '..', '..'))
SHOT_MJS = os.path.join(REPO, 'eidoverse', 'xr', 'shot.mjs')
LINE = re.compile(r'^(?P<q>.*?): (?P<st>ready|TIMEOUT|error: .*?) in (?P<s>[\d.]+) s -> (?P<path>.+?\.png)(?:  (?P<info>\{.*\}))?$')


def still_name(query: str) -> str:
    """The file shot.mjs writes for a query (its own rule: anything but [a-z0-9.=,-] becomes '_')."""
    return re.sub(r'[^a-z0-9.=,-]+', '_', query, flags=re.I) + '.png'


def runtime():
    """node (shot.mjs is a node script; deno runs it too)."""
    for exe in ('node', 'deno'):
        p = shutil.which(exe)
        if p:
            return [p] if exe == 'node' else [p, 'run', '--no-config', '--no-lock', '-A']
    raise RuntimeError('shots: neither node nor deno is on PATH')


def shoot(page_url, out_dir, queries, size=(1600, 900), timeout=60, chrome=None, log=print):
    """Run shot.mjs on page_url for each query; returns one row per query (see the module doc).

    size: SHOT_SIZE (width, height); timeout: SHOT_TIMEOUT, seconds a still may take; chrome: CHROME, the browser binary
    (default: shot.mjs's own search). Chrome's throwaway profile goes into a temporary folder of this call's own, removed
    afterwards (on Windows Chrome can still hold it when shot.mjs's own clean-up runs: shot.mjs then exits 1 after
    writing every still; the rows say what each still did)."""
    import tempfile
    import time
    out_dir = os.path.abspath(out_dir)
    os.makedirs(out_dir, exist_ok=True)
    tmp = tempfile.mkdtemp(prefix='eido_xr_shots_')
    env = dict(os.environ, SHOT_SIZE=f'{int(size[0])}x{int(size[1])}', SHOT_TIMEOUT=str(int(timeout)),
               TMP=tmp, TEMP=tmp, TMPDIR=tmp)
    if chrome:
        env['CHROME'] = chrome
    cmd = runtime() + [SHOT_MJS, page_url, out_dir] + list(queries)
    try:
        p = subprocess.run(cmd, capture_output=True, text=True, env=env, timeout=timeout * len(queries) + 120,
                           encoding='utf-8', errors='replace')
    finally:
        for _ in range(20):                                   # Chrome lets go of its profile a moment after it exits
            shutil.rmtree(tmp, ignore_errors=True)
            if not os.path.exists(tmp):
                break
            time.sleep(0.25)
    rows, pending = [], []
    # shot.mjs prints a still's exceptions and console errors (indented) while the still loads, BEFORE its summary line
    for line in p.stdout.splitlines():
        if log:
            log('[shot] ' + line)
        if line.startswith('  '):
            pending.append(line.strip())
            continue
        m = LINE.match(line)
        if not m:
            continue
        info = None
        if m.group('info'):
            try:
                info = json.loads(m.group('info'))
            except ValueError:
                info = {'raw': m.group('info')}
        rows.append({'query': m.group('q'), 'status': m.group('st'), 'seconds': float(m.group('s')),
                     'path': m.group('path'), 'info': info, 'errors': pending})
        pending = []
    if pending and rows:
        rows[-1]['errors'] += pending
    if p.returncode not in (0, 1) and log:
        log(f'[shot] shot.mjs exited {p.returncode}: {p.stderr.strip()[:800]}')
    if p.stderr.strip() and log:
        log('[shot] stderr: ' + p.stderr.strip()[:800])
    return rows


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('page')
    ap.add_argument('out_dir')
    ap.add_argument('queries', nargs='+')
    ap.add_argument('--size', default='1600x900')
    ap.add_argument('--timeout', type=int, default=60)
    a = ap.parse_args(argv)
    w, h = (int(x) for x in a.size.lower().split('x'))
    rows = shoot(a.page, a.out_dir, a.queries, size=(w, h), timeout=a.timeout)
    print(json.dumps(rows, indent=1))
    sys.exit(0 if rows and all(r['status'] == 'ready' for r in rows) else 1)


if __name__ == '__main__':
    main()
