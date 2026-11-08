"""Canvas screen scenes without Blender: list, preview, contact-sheet, bench and NaN-sweep them (no bpy needed).

The computing-history era screens (eidoverse/graphics/era_screens_1939_1984.js and era_screens_2001_2023.js, fifteen
scenes made for the DAISY music video) and any other module exporting ``scenes`` run in Deno with Skia, the engine's
own drawing code. This module drives the engine's own tools, unchanged:

    from eidoblend.media import canvas_scenes as cs
    cs.list_scenes()                                   # [{name, label, fps, lines, dur, t0, module, prewarm}] x 15
    cs.preview('voder_1939', [0.5, 2, 3.5], out='work/<id>/preview')        # preview_screens.mjs, single form
    cs.sheet('work/<id>/screens_sheet.png', moments=5)                      # preview_screens.mjs --sheet
    cs.bench(W=1920, H=800)                                                 # preview_screens.mjs --bench
    cs.nan_sweep()                                                          # screens_nan_sweep.mjs: {'ok': True, ...}

To put a scene on a screen in a Blender film: screens.bake_canvas_scene, then screens.make_screen(source=...).
``DAISY_CUES`` is the film's own placement of the scenes (each scene's start in film seconds).

Options shared by the tools (preview_screens.mjs's): W x H the canvas (1920 x 800 is the design size), bpm the song's
tempo (a line is two 4/4 bars), at every scene's start in film seconds, cues {scene: t0 | {t0, dur}} per scene,
lyrics: align_lyrics.py output, a caption list, or a timeline {captions, hits: {kick: [...]}, envelopes, visemes_fps}
(a path, or the data itself: it is written to a JSON file for Deno). Deno runs offline (--cached-only) from the
repository root, with no config and no node_modules folder.
"""
import json
import os
import re
import shutil
import subprocess
import tempfile
from pathlib import Path

from . import JS, REPO

GRAPHICS = REPO / 'eidoverse' / 'graphics'
ERA_MODULES = ('eidoverse/graphics/era_screens_1939_1984.js', 'eidoverse/graphics/era_screens_2001_2023.js')
PREVIEW = GRAPHICS / 'preview_screens.mjs'
NAN_SWEEP = GRAPHICS / 'screens_nan_sweep.mjs'

# DAISY's placement (tools-guides/motion-graphics.md): verse 1's eight lines from 24.2273 s, 3.75 s apart (128 BPM, a
# line = two 4/4 bars); verse 2's first four lines from 106.7273 s, sydney_2023 on its last four; sydney_tribute
# across chorus 2 from 136.7273 s. The title card opens the film.
DAISY_LINE = 3.75
DAISY_CUES = {
    'title_card': 0.0,
    **{n: round(24.2273 + DAISY_LINE * i, 4) for i, n in enumerate(
        ('voder_1939', 'bell_1961', 'eliza_1966', 'speakspell_1978', 'sam_1982', 'mac_1984', 'klatt_1984', 'glitch_all'))},
    **{n: round(106.7273 + DAISY_LINE * i, 4) for i, n in enumerate(('desktop_2001', 'vocaloid_2007', 'flood_2016',
                                                                     'mask_2023', 'sydney_2023'))},
    'sydney_tribute': 136.7273,
}


# ---------------------------------------------------------------------------------------------------- Deno
def deno_exe():
    exe = shutil.which('deno')
    if exe:
        return exe
    for cand in Path.home().glob('AppData/Local/Microsoft/WinGet/Packages/DenoLand.Deno*/deno.exe'):
        return str(cand)
    raise FileNotFoundError('deno not found on PATH (the canvas-2D cores run in Deno)')


def deno(script, args, cwd=None, check=True):
    """Run a Deno script offline (the npm cache only, no config, no node_modules written) from the repository root.
    Returns the CompletedProcess; with ``check`` a non-zero exit raises with the tail of its output."""
    cmd = [deno_exe(), 'run', '-A', '--no-config', '--node-modules-dir=none', '--cached-only', str(script),
           *map(str, args)]
    r = subprocess.run(cmd, cwd=str(cwd or REPO), capture_output=True, text=True, encoding='utf-8', errors='replace')
    if check and r.returncode != 0:
        raise RuntimeError(f'{Path(script).name} failed ({r.returncode}):\n{r.stderr[-4000:]}\n{r.stdout[-2000:]}')
    return r


def run_deno(script, args, cwd=None):
    """Run a Deno script (see deno()) and return its stdout."""
    return deno(script, args, cwd).stdout


def repo_path(p):
    """A repo-relative or absolute path -> an absolute Path (repo-relative wins when that file exists)."""
    q = Path(str(p))
    if q.is_absolute():
        return q
    return REPO / q if (REPO / q).exists() else q.resolve()


def json_arg(value, stem, folder=None):
    """A path stays a path; data (a dict or a list) is written to a JSON file for Deno and that path returned:
    <folder>/<stem>.json, or with no folder a file of its own under the system temp (two processes passing
    different data never share one)."""
    if value is None:
        return None
    if isinstance(value, (str, os.PathLike)):
        return repo_path(value)
    if folder:
        folder = Path(folder)
        folder.mkdir(parents=True, exist_ok=True)
        p = folder / f'{stem}.json'
    else:
        d = Path(tempfile.gettempdir()) / 'eido_canvas_scenes'
        d.mkdir(parents=True, exist_ok=True)
        fd, name = tempfile.mkstemp(prefix=f'{stem}_', suffix='.json', dir=d)
        os.close(fd)
        p = Path(name)
    p.write_text(json.dumps(value), encoding='utf-8')
    return p


def _common(W, H, bpm, at, cues, lyrics, folder):
    a = ['--W', W, '--H', H, '--bpm', bpm, '--at', at]
    c = json_arg(cues, 'cues', folder)
    if c:
        a += ['--cues', c]
    ly = json_arg(lyrics, 'lyrics', folder)
    if ly:
        a += ['--lyrics', ly]
    return a


# ---------------------------------------------------------------------------------------------------- the scenes
def list_scenes(modules=ERA_MODULES, bpm=128, cues=None):
    """Every scene of the modules: [{name, label, fps, lines, dur, t0, module, prewarm}], in module order. ``dur``
    is the scene's length at ``bpm`` (lines x 8 beats, or its own dur), ``t0`` its start from ``cues`` (else 0)."""
    args = ['--bpm', bpm]
    c = json_arg(cues, 'cues')
    if c:
        args += ['--cues', c]
    out = run_deno(JS / 'canvas_scenes.mjs', [*args, *(repo_path(m) for m in modules)])
    return json.loads(out.strip().splitlines()[-1])


def scene_module(name, modules=ERA_MODULES):
    """The module (a repo-relative path from ``modules``) that holds the scene ``name``."""
    for s in list_scenes(modules):
        if s['name'] == name:
            for m in modules:
                if Path(s['module']).name == Path(str(m)).name:
                    return m
            return s['module']
    raise KeyError(f'no scene {name!r} in {", ".join(map(str, modules))}')


# ---------------------------------------------------------------------------------------------------- the tools
_PREVIEW_LINE = re.compile(r'^\[preview_screens\] (?P<file>.+?)\s+u=(?P<u>-?[\d.]+) line=(?P<line>-?\d+) '
                           r'voice=(?P<voice>-?[\d.]+) kick=(?P<kick>-?[\d.]+)\s+(?P<ms>[\d.]+) ms$')


def preview(scene, times=None, out='work/screens_preview', modules=ERA_MODULES, W=1920, H=800, moments=5, bpm=128,
            at=0.0, cues=None, lyrics=None):
    """preview_screens.mjs's single form: one PNG per ``times`` entry (seconds into the scene; default ``moments``
    times spread over it) at W x H, named <scene>_<u>.png in ``out``. Returns [{file, u, line, voice, kick, ms}]."""
    out = repo_path(out)
    out.mkdir(parents=True, exist_ok=True)
    args = [*(repo_path(m) for m in modules), scene, *[repr(float(u)) for u in (times or [])],
            '--out', out, '--moments', moments, *_common(W, H, bpm, at, cues, lyrics, out)]
    res = []
    for line in run_deno(PREVIEW, args).splitlines():
        m = _PREVIEW_LINE.match(line.strip())
        if m:
            d = m.groupdict()
            res.append({'file': str(repo_path(d['file'])), 'u': float(d['u']), 'line': int(d['line']),
                        'voice': float(d['voice']), 'kick': float(d['kick']), 'ms': float(d['ms'])})
    return res


def sheet(out_png, scenes=None, modules=ERA_MODULES, W=1920, H=800, moments=5, bpm=128, at=0.0, cues=None,
          lyrics=None, refs=None):
    """preview_screens.mjs --sheet: a contact sheet, one row per scene (all of them, or ``scenes``) with ``moments``
    frames each, its label, length and draw cost; ``refs`` a folder of <scene prefix>_*.png|jpg reference images
    shown beside each row. Returns the sheet's path."""
    out_png = repo_path(out_png)
    out_png.parent.mkdir(parents=True, exist_ok=True)
    args = [*(repo_path(m) for m in modules), '--sheet', *(scenes or []), '--out', out_png, '--moments', moments,
            *_common(W, H, bpm, at, cues, lyrics, out_png.parent)]
    if refs:
        args += ['--refs', repo_path(refs)]
    run_deno(PREVIEW, args)
    if not out_png.exists():
        raise RuntimeError(f'preview_screens.mjs --sheet wrote no {out_png}')
    return out_png


_BENCH_LINE = re.compile(r'^(?P<name>\S+)\s+mean (?P<mean>[\d.]+) ms\s+p50 (?P<p50>[\d.]+)\s+p90 (?P<p90>[\d.]+)\s+'
                         r'max (?P<max>[\d.]+)\s+first-play max (?P<first>[\d.]+)$')


def bench(scenes=None, modules=ERA_MODULES, W=1920, H=800, bpm=128, at=0.0, cues=None, lyrics=None):
    """preview_screens.mjs --bench: after each module's prewarm, every scene's draw cost in ms at W x H (the quietest
    of three 45-frame passes) and its first play's worst frame. Returns {'prewarm_ms': [...], 'scenes': {name: {mean,
    p50, p90, max, first}}}."""
    args = [*(repo_path(m) for m in modules), '--bench', *(scenes or []), *_common(W, H, bpm, at, cues, lyrics, None)]
    res = {'prewarm_ms': [], 'scenes': {}}
    for line in run_deno(PREVIEW, args).splitlines():
        line = line.strip()
        if line.startswith('prewarm '):
            res['prewarm_ms'].append(float(line.split()[1]))
            continue
        m = _BENCH_LINE.match(line)
        if m:
            d = m.groupdict()
            name = d.pop('name')                      # (popped first: the right-hand side is evaluated before it)
            res['scenes'][name] = {k: float(v) for k, v in d.items()}
    return res


_SWEEP_LINE = re.compile(r'^(?P<draws>\d+) draws of (?P<scenes>\d+) scenes, (?P<calls>\d+) guarded canvas calls, '
                         r'(?P<failures>\d+) failures \((?P<seconds>[\d.]+) s\)$')


def nan_sweep(modules=None, bpm=128, lyrics=None, cues=None):
    """screens_nan_sweep.mjs: every scene at every 60-fps frame from 0.5 s before its start to 0.5 s past its end, at
    three canvas sizes, with no caption, awkwardly timed other words and (with ``lyrics``) your captions, plus one
    draw with no st; any non-finite canvas argument fails. modules: default every era_screens_*.js. Returns
    {ok, draws, scenes, calls, failures, seconds, log}; never raises on a failing sweep (``ok`` is False)."""
    args = [*(repo_path(m) for m in (modules or ()))]
    args += ['--bpm', bpm]
    ly, c = json_arg(lyrics, 'sweep_lyrics'), json_arg(cues, 'sweep_cues')
    if ly:
        args += ['--lyrics', ly]
    if c:
        args += ['--cues', c]
    r = deno(NAN_SWEEP, args, check=False)
    res = {'ok': False, 'log': (r.stdout + r.stderr)[-6000:]}
    for line in r.stdout.splitlines():
        m = _SWEEP_LINE.match(line.strip())
        if m:
            res.update({k: (float(v) if k == 'seconds' else int(v)) for k, v in m.groupdict().items()})
    res['ok'] = r.returncode == 0 and res.get('failures') == 0
    return res


def moments(dur, n=3, lo=0.2, hi=0.9):
    """n times spread over a scene of ``dur`` seconds, from lo to hi of it (a contact sheet's moments)."""
    if n == 1:
        return [dur * (lo + hi) / 2]
    return [dur * (lo + (hi - lo) * i / (n - 1)) for i in range(n)]
