"""eidoblend.harness.runner: the in-Blender half of eido_blender.py (run_scene.py calls main()).

A run is BUILD, then RENDER, in one headless Blender:

  build   a fresh empty file; the film preset; the config's size, rate and frame range; the scene script's setup(ctx);
          the config's "render" block; render_frame(ctx, t, i) baked frame by frame (it keys what it changes; its
          keys are made LINEAR, and a change it made without a key is named); the simulation caches stretched to the
          film's last frame and baked (point caches, Geometry Nodes simulations, volume light probes); the audits;
          the .blend saved beside the output with its build record (<scene>.build.json). A build whose inputs are
          unchanged is REUSED, not rebuilt. The inputs: the config, the script, every module it imported from the
          repository or beside the script, the declared assets' sizes and times, and every file and folder the
          script read through Python while it built (a plan file beside it, a JSON of shots, a glTF the importer
          read), plus the sources of packed images. A .blend edited by hand since its build is rendered as it is,
          and a rebuild over it is refused unless --force (my films' rule: a build never silently destroys hand
          work).
  render  by mode: film (the whole range to H.264), probe (the first N frames, probe caps), capture (PNG stills at
          given seconds), bench (time a few frames), build (no render). Render-time changes are never saved.

The digest (<out>.audit.txt + .audit.json) gets a "running" stamp first and is rewritten on every exit path, so an
absent or still-"running" digest means the run did not finish.
"""

from __future__ import annotations

import ast
import atexit
import hashlib
import json
import os
import shutil
import sys
import time
import traceback
import urllib.request
import warnings

import bpy

from .. import common
from . import audits, config as cfgmod, keying, ledger as L, output, post, settings
from .context import AssetMap, Ctx

BUILD_FORMAT = 'eido_blender.build/2'


# ------------------------------------------------------------------------------------- what the build reads ---

class _Reads:
    """Files and folders the scene script reads through Python while it builds (setup and render_frame), seen
    through Python's audit hooks: the 'open' event for reads (writes are outputs, not inputs) and the
    'os.listdir' / 'os.scandir' events. The import system's own reads are left out (its modules are tracked
    separately). Reads in C (Blender's image loader, the OBJ / PLY / STL importers) are not seen: declare such files
    under "assets". Files the build itself wrote ('open' for writing) and folders it made ('os.mkdir') are outputs:
    an html_mesh panel painted and read back, a baked map, never an input that would rebuild the scene."""

    def __init__(self):
        self.on = False
        self.files = set()
        self.dirs = set()
        self.written = set()                                         # what the build made: outputs, never inputs
        self.made = set()

    def clear(self):
        for s in (self.files, self.dirs, self.written, self.made):
            s.clear()

    def hook(self, event, args):
        if not self.on or event not in ('open', 'os.listdir', 'os.scandir', 'os.mkdir'):
            return
        try:                                                         # an audit hook must never raise
            fr = sys._getframe(1)
            if fr is not None and fr.f_code.co_filename.startswith('<frozen'):
                return                                               # importlib finding and reading modules
            if event == 'os.mkdir':
                if args and not isinstance(args[0], int):
                    self.made.add(os.path.abspath(os.fsdecode(args[0])))
                return
            if event == 'open':
                path, mode, flags = (tuple(args) + (None, None, None))[:3]
                if path is None or isinstance(path, int):
                    return
                if mode is None:
                    if not isinstance(flags, int) or flags & 3:      # os.open for writing (O_WRONLY / O_RDWR)
                        self.written.add(os.path.abspath(os.fsdecode(path)))
                        return
                elif any(c in str(mode) for c in 'wax+'):
                    self.written.add(os.path.abspath(os.fsdecode(path)))  # a painted panel, a baked map: outputs
                    return
                self.files.add(os.path.abspath(os.fsdecode(path)))
            else:
                path = args[0] if args else None
                if isinstance(path, int):
                    return
                self.dirs.add(os.path.abspath(os.fsdecode(path) if path is not None else '.'))
        except Exception:                                            # noqa: BLE001
            pass


READS = _Reads()
_HOOKED = [False]


def _track_reads(on: bool):
    if on and not _HOOKED[0]:
        sys.addaudithook(READS.hook)                                 # for the life of this Blender process
        _HOOKED[0] = True
    READS.on = on


class Refused(Exception):
    pass


# ------------------------------------------------------------------------------------------------- the run ---

class Run:
    def __init__(self, job: dict):
        self.job = job
        self.cfg = job['config']
        self.mode = job['mode']
        self.paths = cfgmod.output_paths(self.cfg, self.mode)
        self.led = L.Ledger()
        self.runtime = []
        self.status = 'running'
        self.run_id = f"{os.path.relpath(self.cfg['_scene_json'], common.REPO)}@{L.stamp()}"
        self.steps = []
        self.flushed = False
        self.outputs = []

    # the digest, written on every exit path
    def flush(self, status=None):
        if status:
            self.status = status
        try:
            common.atomic_write_text(self.paths['audit_txt'], L.digest_from_ledger(
                self.led, self.runtime, self.run_id, self.status))
            body = {'run_id': self.run_id, 'status': self.status, 'mode': self.mode, 'outputs': self.outputs}
            body.update(self.led.to_json())
            common.atomic_write_json(self.paths['audit_json'], body)
            self.flushed = True
        except Exception as e:                                       # noqa: BLE001 - a failed write retries later
            print(f'[eido_blender] digest flush failed ({e}); will retry on the next exit path', flush=True)

    def step(self, name):
        run = self

        class _S:
            def __enter__(self):
                self.t = time.perf_counter()
                common.log('eido_blender', name, '...')

            def __exit__(self, et, ev, tb):
                dt = time.perf_counter() - self.t
                run.steps.append({'step': name, 'seconds': round(dt, 2), 'ok': et is None})
                common.log('eido_blender', f'{name}: {dt:.1f} s' + ('' if et is None else ' (FAILED)'))
                return False
        return _S()


def main(argv: list) -> int:
    if not argv:
        print('usage: run_scene.py <job.json>', file=sys.stderr)
        return 2
    with open(argv[0], encoding='utf-8') as f:
        job = json.load(f)
    run = Run(job)
    for w in run.cfg.get('_warnings', []):
        run.led.record(check='config', outcome='WARN', cls='REVIEW', message=w)
    run.flush('running')
    atexit.register(lambda: None if run.flushed and run.status != 'running' else run.flush('process exit'))
    _orig_showwarning = warnings.showwarning

    def _showwarning(message, category, filename, lineno, file=None, line=None):
        run.runtime.append(f'{category.__name__}: {message} ({os.path.basename(filename)}:{lineno})')
        _orig_showwarning(message, category, filename, lineno, file, line)
    warnings.showwarning = _showwarning
    rc = 0
    try:
        scene = build_or_reuse(run)
        render(run, scene)
        run.status = 'normal completion'
    except Refused as e:
        run.led.record(check='lifecycle', outcome='WARN', cls='CORRECTNESS', message=f'refused: {e}')
        print(f'[eido_blender] REFUSED: {e}', flush=True)
        run.status = 'refused'
        rc = 3
    except Exception as e:                                           # noqa: BLE001 - every failure leaves a digest
        tb = traceback.format_exc()
        print(tb, flush=True)
        run.led.record(check='lifecycle', outcome='WARN', cls='CORRECTNESS',
                       message=f'run ended abnormally: {type(e).__name__}: {e}')
        run.runtime.append(tb.strip().splitlines()[-1])
        run.status = 'error'
        rc = 1
    finally:
        run.flush()
    _report(run)
    return rc


def _report(run):
    print(f"[eido_blender] digest -> {run.paths['audit_txt']} (+ .audit.json)", flush=True)
    warn = [r for r in run.led.records if r['outcome'] == 'WARN']
    if warn:
        print(f'[eido_blender] AUDIT DIGEST: {len(warn)} finding(s) above threshold. Worth a look; some may be '
              'intentional, and saying so is a fine answer:', flush=True)
        for r in warn[:20]:
            print(f"  [{r['check']}] {r['message']}", flush=True)
    else:
        print('[eido_blender] audit digest: every measurement within normal range.', flush=True)
    for p in run.outputs:
        print(f'[eido_blender] wrote {p}', flush=True)
    print('[eido_blender] the digest measures correctness, not beauty: VIEW the frames before calling it done.',
          flush=True)


# ---------------------------------------------------------------------------------------------------- build ---

def _module_key(path: str) -> str:
    """A module's name in the build record: repo-relative when it is in the repository, else absolute."""
    pa = os.path.abspath(path)
    if os.path.normcase(pa).startswith(os.path.normcase(common.REPO) + os.sep):
        return os.path.relpath(pa, common.REPO).replace('\\', '/')
    return pa.replace('\\', '/')


def _module_path(key: str) -> str:
    return key if os.path.isabs(key) else os.path.join(common.REPO, key)


def _module_files(cfg):
    """Every imported module whose file is in the repository or beside the scene script (its helpers)."""
    files = {}
    roots = [os.path.normcase(common.REPO) + os.sep,
             os.path.normcase(os.path.dirname(os.path.abspath(cfg['_script']))) + os.sep]
    for name, m in list(sys.modules.items()):
        f = getattr(m, '__file__', None)
        if not f or not f.endswith('.py'):
            continue
        fa = os.path.abspath(f)
        if any(os.path.normcase(fa).startswith(r) for r in roots) and os.path.isfile(fa):
            files[_module_key(fa)] = fa
    return files


def _skip_prefixes():
    out = [os.path.dirname(bpy.app.binary_path), sys.prefix, sys.base_prefix, sys.exec_prefix,
           os.environ.get('BLENDER_USER_RESOURCES', ''), os.path.join(common.BLENDER_DIR, 'eidoblend')]
    return [os.path.normcase(os.path.abspath(p)) + os.sep for p in out if p]


def _own_output(cfg, path) -> bool:
    """A file this harness writes for this config (the build, its record, the job, digests, videos, stills)."""
    ostem = os.path.splitext(cfg['_output'])[0]
    d, base = os.path.split(os.path.normcase(os.path.abspath(path)))
    return d == os.path.normcase(os.path.dirname(ostem)) and base.startswith(os.path.normcase(os.path.basename(ostem)))


def build_reads(cfg) -> tuple:
    """(files, folders) the script read while it built, minus Blender's and Python's own files, modules (tracked
    separately), the config, the script and this harness's outputs. Packed images' sources join the files: the
    .blend holds a copy of them."""
    skip = _skip_prefixes()
    known = {os.path.normcase(os.path.abspath(cfg['_scene_json'])), os.path.normcase(os.path.abspath(cfg['_script']))}
    wrote = {os.path.normcase(p) for p in READS.written}             # what the build made itself is an output
    made = tuple(os.path.normcase(d) + os.sep for d in READS.made)

    def built_here(n):
        return n in wrote or n.startswith(made) or (n + os.sep) in made

    def only_built(d):
        try:
            entries = [os.path.normcase(os.path.join(d, e)) for e in os.listdir(d)]
        except OSError:
            return False
        return bool(entries) and all(built_here(e) for e in entries)
    files = set()
    for p in READS.files:
        n = os.path.normcase(p)
        if n in known or any(n.startswith(s) for s in skip) or n.endswith(('.py', '.pyc', '.pyd', '.dll', '.so')):
            continue
        if _own_output(cfg, p) or not os.path.isfile(p) or built_here(n):
            continue
        files.add(p)
    for img in bpy.data.images:
        if img.packed_file is not None and img.filepath and img.library is None:
            p = os.path.abspath(bpy.path.abspath(img.filepath))
            if os.path.isfile(p) and not built_here(os.path.normcase(p)):
                files.add(p)
    dirs = set()
    for d in READS.dirs:
        n = os.path.normcase(d)
        if any(n.startswith(s) for s in skip) or not os.path.isdir(d) or built_here(n) or only_built(d):
            continue                                                 # (a folder holding only what the build wrote)
        dirs.add(d)
    return sorted(files), sorted(dirs)


def _stat(p):
    try:
        st = os.stat(p)
        return [st.st_size, st.st_mtime_ns]
    except OSError:
        return None


def _listing(cfg, d):
    """A folder's entry names (minus this config's own outputs), as an md5: an added or removed file changes it."""
    try:
        names = sorted(n for n in os.listdir(d) if n != '__pycache__' and not _own_output(cfg, os.path.join(d, n)))
    except OSError:
        return None
    return hashlib.md5('\n'.join(names).encode('utf-8')).hexdigest()


def _config_digest(cfg):
    keep = {k: v for k, v in cfg.items() if not k.startswith('_') and k not in ('capture',)}
    keep['_assets'] = cfg['_assets']
    return hashlib.md5(json.dumps(keep, sort_keys=True, default=str).encode()).hexdigest()


def _asset_stats(cfg):
    out = {}
    for k, p in sorted(cfg['_assets'].items()):
        if cfgmod.is_url(p):
            out[k] = p
        elif os.path.isfile(p):
            st = os.stat(p)
            out[k] = [st.st_size, st.st_mtime_ns]
        elif os.path.isdir(p):
            out[k] = ['dir', int(os.stat(p).st_mtime_ns)]
        else:
            out[k] = None
    return out


def inputs_digest(cfg, module_paths: dict, reads=(), listed=()) -> dict:
    mods = {}
    for key, p in sorted(module_paths.items()):
        mods[key] = common.md5_file(p) if os.path.isfile(p) else None
    return {'blender': bpy.app.version_string, 'config': _config_digest(cfg), 'script': common.md5_file(cfg['_script']),
            'modules': mods, 'assets': _asset_stats(cfg),
            'reads': {p.replace('\\', '/'): _stat(p) for p in sorted(reads)},
            'listed': {d.replace('\\', '/'): _listing(cfg, d) for d in sorted(listed)}}


def changed_inputs(old: dict, new: dict) -> list:
    """What differs between two input digests, by name (for the rebuild message)."""
    out = [k for k in ('blender', 'config', 'script') if old.get(k) != new.get(k)]
    for k in ('modules', 'assets', 'reads', 'listed'):
        a, b = old.get(k) or {}, new.get(k) or {}
        for p in sorted(set(a) | set(b)):
            if a.get(p) != b.get(p):
                out.append(os.path.basename(str(p).rstrip('/')) + ('/' if k == 'listed' else ''))
    return out


def build_or_reuse(run: Run):
    cfg, job = run.cfg, run.job
    blend, rec_path = cfg['_blend'], cfg['_build_json']
    rec = None
    if os.path.exists(rec_path):
        try:
            with open(rec_path, encoding='utf-8') as f:
                rec = json.load(f)
        except (OSError, json.JSONDecodeError):
            rec = None
    hand = False
    if rec and os.path.exists(blend):
        hand = common.md5_file(blend) != rec.get('saved', {}).get('md5')
        old = rec.get('inputs') or {}
        mod_paths = {key: _module_path(key) for key in old.get('modules', {})}
        now = inputs_digest(cfg, mod_paths, old.get('reads', {}), old.get('listed', {}))
        if rec.get('format') != BUILD_FORMAT:
            diff = [f"the build record's format ({rec.get('format')}, this harness writes {BUILD_FORMAT})"]
        else:
            diff = changed_inputs(old, now)
        same = not diff
        if same and not job.get('rebuild'):
            return reuse(run, rec, hand)
        why = '--rebuild was given' if same else 'its inputs changed: ' + ', '.join(diff[:8]) + \
            (' ...' if len(diff) > 8 else '')
        if hand and not job.get('force'):
            raise Refused(f'{blend} was changed by hand since its build and {why}: a rebuild would lose that work. '
                          'Move the hand edits into the script, or pass --force to rebuild anyway.')
        run.led.record(check='build', outcome='PASS', cls='INFO',
                       message=('rebuilding: ' + ('--rebuild' if same else 'inputs changed: ' + ', '.join(diff[:8])
                                                  + (' ...' if len(diff) > 8 else '')))
                       + (' (overwriting a hand-edited .blend: --force)' if hand else ''))
    elif os.path.exists(blend) and not job.get('force'):
        raise Refused(f'{blend} exists without its build record ({rec_path}): it may be hand work. '
                      'Move it away, or pass --force to replace it.')
    return build(run)


def reuse(run: Run, rec: dict, hand: bool):
    cfg = run.cfg
    with run.step('open the built .blend'):
        bpy.ops.wm.open_mainfile(filepath=cfg['_blend'], load_ui=False)
    scene = bpy.context.scene
    if hand:
        run.led.record(check='build', outcome='WARN', cls='REVIEW',
                       message=f"rendering {cfg['_blend']} AS EDITED BY HAND since its build ({rec.get('built')}): "
                               'the audits below were re-run on it')
        _scene_imports(run)
        _audits(run, scene, policy=rec.get('policy') or L.snapshot_policy({}), script_ns=None, assets=None)
    else:
        run.led.record(check='build', outcome='PASS', cls='INFO',
                       message=f"reused the build of {rec.get('built')} (inputs unchanged); its audits follow")
        run.led.extend([r for r in rec.get('audit', {}).get('records', []) if r.get('check') not in ('build', 'config')])
    return scene


def _scene_imports(run: Run):
    """A reopened .blend does not run the scene script, so a family it imported (whose modules register what the
    audits read, such as the placement family's helpers) would be missing. Run the script's TOP-LEVEL import
    statements only, nothing else of it, so the reopened scene is audited by the same families as its build."""
    cfg = run.cfg
    try:
        with open(cfg['_script'], encoding='utf-8') as f:
            tree = ast.parse(f.read(), cfg['_script'])
        body = [n for n in tree.body if isinstance(n, (ast.Import, ast.ImportFrom))]
        if not body:
            return
        sdir = os.path.dirname(cfg['_script'])
        if sdir not in sys.path:
            sys.path.append(sdir)
        exec(compile(ast.Module(body=body, type_ignores=[]), cfg['_script'], 'exec'),   # noqa: S102
             {'__name__': 'eido_scene_imports', '__file__': cfg['_script']})
    except Exception as e:                                           # noqa: BLE001
        run.led.record(check='build', outcome='SKIPPED', cls='REVIEW',
                       message=f"the scene script's imports failed on the reopened .blend ({type(e).__name__}: {e}): "
                               'the audits of the families it uses may be missing')


def _resolve_assets(run: Run) -> AssetMap:
    cfg = run.cfg
    out = {}
    for key, p in cfg['_assets'].items():
        if cfgmod.is_url(p):
            d = cfgmod.asset_download_dir(cfg)
            os.makedirs(d, exist_ok=True)
            dst = os.path.join(d, f'{key}_{cfgmod.url_filename(p)}')
            if not os.path.exists(dst):
                common.log('eido_blender', f'asset {key}: downloading {p}')
                with urllib.request.urlopen(p, timeout=120) as r, open(dst + '.part', 'wb') as f:
                    shutil.copyfileobj(r, f)
                os.replace(dst + '.part', dst)
            p = dst
        if not os.path.exists(p) or (os.path.isfile(p) and os.path.getsize(p) == 0):
            raise FileNotFoundError(f"asset '{key}': {p} is missing or empty")
        out[key] = p
    return AssetMap(out)


def build(run: Run):
    cfg = run.cfg
    with run.step('fresh scene + film preset'):
        bpy.ops.wm.read_homefile(use_empty=True)
        scene = bpy.context.scene
        scene.name = os.path.splitext(os.path.basename(cfg['_scene_json']))[0]
        notes = settings.apply_preset(scene, cfg)
        # the post chain's records of earlier frames (look.post.history: after_image, the era looks' persistence,
        # aeropittura) beside the build, not in this Blender's session folder, which is gone when it exits
        scene['eido_history_dir'] = os.path.splitext(cfg['_output'])[0] + '_post_history'
    assets = _resolve_assets(run)
    ctx = Ctx(scene, cfg, assets, run.led, run.mode)
    ns = {'__name__': 'eido_scene', '__file__': cfg['_script'], 'WIDTH': cfg['width'], 'HEIGHT': cfg['height'],
          'FPS': cfg['fps'], 'DURATION': cfg['duration'], 'TOTAL_FRAMES': ctx.total_frames,
          'FRAME_START': ctx.frame_start, 'FRAME_END': ctx.frame_end, 'ASSETS': assets,
          'EIDOVERSE_DIR': common.EIDOVERSE_DIR, 'REPO': common.REPO}
    sdir = os.path.dirname(cfg['_script'])
    if sdir not in sys.path:
        sys.path.append(sdir)
    READS.clear()
    _track_reads(True)                                               # what setup and render_frame read are inputs
    try:
        with run.step('setup(ctx)'):
            with open(cfg['_script'], encoding='utf-8') as f:
                code = compile(f.read(), cfg['_script'], 'exec')
            exec(code, ns)                                            # noqa: S102 - the scene script is the input
            if not callable(ns.get('setup')):
                raise RuntimeError(f"{cfg['script']}: no setup(ctx) function")
            ns['setup'](ctx)
            scene = bpy.context.scene                                # setup may have swapped scenes; render that one
        r = scene.render
        if (r.resolution_x, r.resolution_y) != (cfg['width'], cfg['height']) or r.engine != 'BLENDER_EEVEE':
            run.led.record(check='build.settings', outcome='WARN', cls='REVIEW',
                           message=f'setup() set {r.engine} at {r.resolution_x}x{r.resolution_y}; the config says EEVEE '
                                   f"at {cfg['width']}x{cfg['height']}: the config wins (reset)")
            r.engine = 'BLENDER_EEVEE'
            r.resolution_x, r.resolution_y = cfg['width'], cfg['height']
        policy = _policy(ns, scene)
        census0 = _census(scene)
        if cfg.get('render'):
            done = settings.apply_render_block(scene, cfg['render'])
            if done:
                notes.append('config render block: ' + ', '.join(done))
        with run.step('auto-enhance + hooks'):
            post.apply(scene, ns, run.led)              # the engine's post stack, hooks and overlay layer
        fs, fe = cfgmod.frame_range(cfg)
        intended = {}
        n_lin = keying.make_linear(ctx.key_log)        # setup's own keys first: render_frame (and the un-keyed
        if callable(ns.get('render_frame')):           # check's notes) must see the curves the film will have
            samples = set(keying.sample_frames(scene, fs, fe))
            with run.step(f'render_frame baked over frames {fs}-{fe}'):
                for f in range(fs, fe + 1):
                    scene.frame_set(f)
                    ns['render_frame'](ctx, ctx.time_at(f), f - fs)
                    if f in samples:                                 # what render_frame meant this frame to show
                        bpy.context.view_layer.update()
                        intended[f] = keying.snapshot(scene)
            n_lin += keying.make_linear(ctx.key_log)
            run.led.record(check='build.render_frame', outcome='PASS', cls='INFO',
                           metrics={'keys': ctx.keyed, 'made_linear': n_lin},
                           message=f'render_frame ran on {fe - fs + 1} frames and keyed {ctx.keyed} value(s) '
                                   f'({n_lin} key(s) set LINEAR)')
    finally:
        _track_reads(False)
    scene_modules = audits.eidoblend_modules()        # what the scene used, before the audits import anything
    reads, listed = build_reads(cfg)
    _record_reads(run, reads, listed)
    with run.step('bake caches'):
        _bake_caches(run, scene)
    if intended:
        with run.step('un-keyed change check'):
            _unkeyed(run, scene, intended)
    census1 = _census(scene)
    policy1 = _policy(ns, scene)
    if census1 != census0 or policy1 != policy:
        diffs = []
        if policy1 != policy:
            diffs.append(f"policy {policy['flags']} -> {policy1['flags']}")
        if census1 != census0:
            diffs.append(f'object flags {census0} -> {census1}')
        run.led.record(check='coverage.toctou', outcome='WARN', disposition='DECLARED_EXCEPTION', cls='CORRECTNESS',
                       message='audit flags changed after setup (render_frame changed them): ' + '; '.join(diffs))
    else:
        run.led.record(check='coverage.toctou', outcome='PASS', cls='INFO',
                       message='policy and object flags unchanged between setup and the end of the build')
    _audits(run, scene, policy, ns, assets, notes, modules=scene_modules)
    kept = _keep_temp_images(run, cfg['_blend'])
    with run.step('save the .blend'):
        scene.frame_set(fs)
        bpy.context.preferences.filepaths.save_version = 0           # no .blend1 beside the build
        os.makedirs(os.path.dirname(cfg['_blend']), exist_ok=True)
        tmp = cfg['_blend'] + '.part.blend'
        bpy.ops.wm.save_as_mainfile(filepath=tmp, compress=False, relative_remap=True, copy=True)
        os.replace(tmp, cfg['_blend'])
    _prune_kept(cfg['_blend'], kept)                   # earlier builds' copies: the new .blend points at none of them
    rec = {
        'format': BUILD_FORMAT, 'built': L.stamp(), 'scene_json': cfg['_scene_json'], 'blend': cfg['_blend'],
        'inputs': inputs_digest(cfg, _module_files(cfg), reads, listed), 'policy': policy,
        'settings': settings.describe(scene),
        'notes': notes, 'steps': run.steps, 'audit': run.led.to_json(),
        'saved': {'file': cfg['_blend'], 'bytes': os.path.getsize(cfg['_blend']), 'md5': common.md5_file(cfg['_blend'])},
    }
    common.atomic_write_json(cfg['_build_json'], rec)
    run.outputs.append(cfg['_blend'])
    if callable(ns.get('cleanup')):
        ns['cleanup'](ctx)
    return scene


def _temp_roots():
    import tempfile
    roots = {tempfile.gettempdir()} | {os.environ[k] for k in ('TMP', 'TEMP', 'TMPDIR') if os.environ.get(k)}
    return [os.path.normcase(os.path.abspath(r)) + os.sep for r in roots]


def _keep_temp_images(run: Run, blend: str):
    """Images the build painted into the temp folder go beside the .blend before it is saved. A screen or an
    html_mesh card made in setup() has no saved .blend to sit beside yet, so the media family writes its frames to
    the temp folder; a build saved pointing there renders them pink once the temp folder is cleaned (a reused build
    keeps rendering for days). Each such image's files (a sequence's numbered frames with its hold files, or the
    one file) are copied to <blend stem>_files/<its folder's name> and the image repointed there (saved relative);
    a source folder left holding nothing else (a screen's own folder, not Blender's session folder) is removed, as
    the disk is shared."""
    import re
    roots = _temp_roots()
    session = os.path.normcase(os.path.abspath(bpy.app.tempdir or '')) if bpy.app.tempdir else None
    dest_root = os.path.splitext(blend)[0] + '_files'
    taken, moved = {}, []                                              # source folder -> (destination, files copied)
    for img in bpy.data.images:
        if img.source not in ('FILE', 'SEQUENCE') or img.packed_file is not None or img.library is not None \
                or not img.filepath:
            continue
        p = os.path.abspath(bpy.path.abspath(img.filepath))
        if not any(os.path.normcase(p).startswith(r) for r in roots) or not os.path.exists(p):
            continue
        src, base = os.path.split(p)
        if img.source == 'SEQUENCE':
            stem, ext = os.path.splitext(base)
            head = stem.rstrip('0123456789')
            pat = re.compile(re.escape(head) + r'\d+' + re.escape(ext) + '$')
            files = [f for f in os.listdir(src) if pat.match(f)]
        else:
            files = [base]
        key = os.path.normcase(src)
        dst = taken[key][0] if key in taken else os.path.join(dest_root, os.path.basename(src) or 'temp')
        os.makedirs(dst, exist_ok=True)
        for f in files:
            shutil.copy2(os.path.join(src, f), os.path.join(dst, f))
        taken.setdefault(key, (dst, set()))[1].update(files)
        img.filepath = os.path.join(dst, base)
        moved.append(img.name)
    for key, (dst, files) in taken.items():
        if any(key + os.sep == r for r in roots) or (session and key.rstrip(os.sep) == session.rstrip(os.sep)):
            continue                                                   # never empty the temp or session folder
        try:
            real = [d for d in os.listdir(key) if d not in files]
        except OSError:
            continue
        if not real:
            shutil.rmtree(key, ignore_errors=True)
    if moved:
        run.led.record(check='build.files', outcome='PASS', cls='INFO', metrics={'images': len(moved)},
                       message=f'{len(moved)} image(s) the build painted into the temp folder kept beside the .blend '
                               f"({os.path.basename(dest_root)}/): {', '.join(moved[:6])}"
                               + (' ...' if len(moved) > 6 else ''))
    return {os.path.dirname(bpy.path.abspath(img.filepath)) for img in bpy.data.images
            if img.filepath and os.path.normcase(os.path.abspath(bpy.path.abspath(img.filepath))).startswith(
                os.path.normcase(os.path.abspath(dest_root)) + os.sep)}


def _prune_kept(blend: str, kept: set):
    """After the new .blend is saved: the folders earlier builds kept beside it go (each build's painted folders
    have names of their own, so they would pile up)."""
    root = os.path.splitext(blend)[0] + '_files'
    if not os.path.isdir(root):
        return
    keep = {os.path.normcase(os.path.abspath(k)) for k in kept}
    for name in os.listdir(root):
        p = os.path.join(root, name)
        if os.path.isdir(p) and os.path.normcase(os.path.abspath(p)) not in keep:
            shutil.rmtree(p, ignore_errors=True)
    if not os.listdir(root):
        os.rmdir(root)


def _record_reads(run: Run, reads: list, listed: list):
    """Name what the build read beyond the config, the script, its modules and the declared assets: those files
    are build inputs from now on (an edit to one rebuilds), and saying so keeps them from being a surprise."""
    cfg = run.cfg
    declared = {os.path.normcase(os.path.abspath(p)) for p in cfg['_assets'].values() if not cfgmod.is_url(p)}
    lib_roots = [os.path.normcase(os.path.abspath(p)) + os.sep for p in (common.cache_dir(), common.ASSETS_DIR)]
    extra = [p for p in reads if os.path.normcase(p) not in declared]
    lib = [p for p in extra if any(os.path.normcase(p).startswith(r) for r in lib_roots)]
    other = [p for p in extra if p not in lib]
    if not extra and not listed:
        run.led.record(check='build.inputs', outcome='PASS', cls='INFO',
                       message='the build read nothing beyond the config, the script, its modules and the declared assets')
        return

    def rel(p):
        try:
            return os.path.relpath(p, common.REPO).replace('\\', '/')
        except ValueError:
            return p.replace('\\', '/')
    parts = []
    if other:
        parts.append(f"{len(other)} undeclared file(s): {', '.join(rel(p) for p in other[:6])}"
                     + (' ...' if len(other) > 6 else ''))
    if lib:
        parts.append(f'{len(lib)} file(s) from the asset library')
    if listed:
        parts.append(f"{len(listed)} folder listing(s): {', '.join(rel(d) + '/' for d in listed[:4])}"
                     + (' ...' if len(listed) > 4 else ''))
    run.led.record(check='build.inputs', outcome='PASS', cls='INFO',
                   metrics={'undeclared': len(other), 'library': len(lib), 'folders': len(listed)},
                   message='the script read ' + '; '.join(parts) + ' while it built: they are build inputs (an edit '
                           'to one rebuilds the scene); declare the files a scene depends on under "assets"')


def _unkeyed(run: Run, scene, intended: dict):
    """Jump to each sampled frame of the saved scene and compare it with what render_frame set at that frame: a
    difference is a change made without a key (the film shows the last value set, on every frame)."""
    diffs = []
    for f in sorted(intended):
        scene.frame_set(f)
        for label, v, s, idb, path in keying.diff(intended[f], keying.snapshot(scene)):
            diffs.append((f, label, v, s, idb, path))
    scene.frame_set(scene.frame_start)
    frames = sorted(intended)
    if diffs:
        labels = sorted({d[1] for d in diffs})
        run.led.record(check='build.unkeyed', outcome='WARN', cls='CORRECTNESS', metrics={'values': len(labels)},
                       bodies=labels[:20], message=keying.report(diffs, frames))
    else:
        run.led.record(check='build.unkeyed', outcome='PASS', cls='INFO', metrics={'frames_checked': len(frames)},
                       message=f'every value render_frame changed is keyed: the saved scene shows what it set '
                               f'(compared at frames {frames})')


def _policy(ns, scene):
    src = {}
    for k in list(L.GLOBAL_FLAGS) + list(L.GLOBAL_FLAG_ALIASES):
        if ns is not None and k in ns:
            src[k] = ns[k]
        if k in scene.keys():
            src[k] = scene[k]
    return L.snapshot_policy(src)


def _census(scene):
    c = {}
    for ob in scene.objects:
        for k in ob.keys():
            n = L.canonical_flag(k, L.OBJECT_FLAG_ALIASES)
            if (n in L.OBJECT_FLAGS or n == 'assembly') and ob[k]:
                c[n] = c.get(n, 0) + 1
    return c


def point_caches(scene) -> list:
    """[(name, point cache, its own range is editable)] of every simulation cache in the scene: cloth, soft body
    and dynamic paint modifiers, particle systems (their range follows their emission and lifetime) and the rigid
    body world."""
    out = []
    for ob in scene.objects:
        for m in ob.modifiers:
            pc = getattr(m, 'point_cache', None)
            if pc is not None:
                out.append((f'{ob.name}/{m.name}', pc, True))
            if m.type == 'DYNAMIC_PAINT' and m.canvas_settings is not None:
                for s in m.canvas_settings.canvas_surfaces:      # its range follows the surface's own
                    if s.point_cache is not None:
                        out.append((f'{ob.name}/{m.name}/{s.name}', s.point_cache, False))
        for ps in getattr(ob, 'particle_systems', []):
            out.append((f'{ob.name}/{ps.name}', ps.point_cache, False))
    rbw = scene.rigidbody_world
    if rbw is not None and rbw.point_cache is not None:
        out.append(('rigid body world', rbw.point_cache, True))
    return out


def _stretch_caches(scene) -> list:
    """Every unbaked simulation cache that stops before the film's last frame is stretched to it. Blender's
    default cache range is 1-250 (10.4 s at 24 fps): left alone, a longer film's simulation freezes at frame 250
    while everything else moves on. A cache the scene baked itself keeps its range (preflight warns if it is
    short). Returns ['name a-b -> a-c', ...]."""
    fe = scene.frame_end
    done = []
    for name, pc, editable in point_caches(scene):
        if editable and not pc.is_baked and pc.frame_end < fe:
            done.append(f'{name} {pc.frame_start}-{pc.frame_end} -> {pc.frame_start}-{fe}')
            pc.frame_end = fe
    for ob in scene.objects:
        for m in ob.modifiers:
            if m.type == 'DYNAMIC_PAINT' and m.canvas_settings is not None:
                for s in m.canvas_settings.canvas_surfaces:
                    if s.frame_end < fe and not s.point_cache.is_baked:
                        done.append(f'{ob.name}/{m.name}/{s.name} surface {s.frame_start}-{s.frame_end} -> '
                                    f'{s.frame_start}-{fe}')
                        s.frame_end = fe
            if m.type == 'FLUID' and m.fluid_type == 'DOMAIN' and m.domain_settings is not None:
                ds = m.domain_settings
                if ds.cache_frame_end < fe and not ds.has_cache_baked_any:
                    done.append(f'{ob.name}/{m.name} fluid cache {ds.cache_frame_start}-{ds.cache_frame_end} -> '
                                f'{ds.cache_frame_start}-{fe}')
                    ds.cache_frame_end = fe
    return done


def _bake_caches(run, scene):
    led = run.led
    caches = point_caches(scene)
    stretched = _stretch_caches(scene)
    if stretched:
        led.record(check='build.bake', outcome='PASS', cls='INFO',
                   message="simulation cache range(s) stretched to the film's last frame (Blender's default stops at "
                           '250): ' + '; '.join(stretched[:6]) + (' ...' if len(stretched) > 6 else ''))
    if caches and not all(pc.is_baked for _n, pc, _e in caches):
        try:
            bpy.ops.ptcache.bake_all(bake=True)
            led.record(check='build.bake', outcome='PASS', cls='INFO',
                       message=f'point caches baked ({len(caches)}): '
                               + ', '.join(f'{n} {pc.frame_start}-{pc.frame_end}' for n, pc, _e in caches[:6])
                               + (' ...' if len(caches) > 6 else ''))
        except Exception as e:                                       # noqa: BLE001
            led.record(check='build.bake', outcome='WARN', cls='CORRECTNESS', message=f'point cache bake failed: {e}')
    sims = [ob for ob in scene.objects if any(m.type == 'NODES' and m.node_group and _has_sim(m.node_group)
                                              for m in ob.modifiers)]
    if sims:
        try:
            with bpy.context.temp_override(selected_objects=sims, active_object=sims[0]):
                bpy.ops.object.simulation_nodes_cache_bake(selected=True)
            led.record(check='build.bake', outcome='PASS', cls='INFO',
                       message=f"Geometry Nodes simulations baked on {', '.join(o.name for o in sims)}")
        except Exception as e:                                       # noqa: BLE001
            led.record(check='build.bake', outcome='WARN', cls='CORRECTNESS',
                       message=f'Geometry Nodes simulation bake failed ({e}): jumped frames may differ from the film')
    vols = [ob for ob in scene.objects if ob.type == 'LIGHT_PROBE' and ob.data.type in ('VOLUME', 'GRID')]
    if vols and not run.job.get('no_probe_bake'):
        try:
            with bpy.context.temp_override(active_object=vols[0], object=vols[0], selected_objects=vols):
                bpy.ops.object.lightprobe_cache_bake(subset='ALL')
            led.record(check='build.bake', outcome='PASS', cls='INFO',
                       message=f"volume light probes baked: {', '.join(o.name for o in vols)}")
        except Exception as e:                                       # noqa: BLE001
            led.record(check='build.bake', outcome='WARN', cls='CORRECTNESS',
                       message=f'volume light probe bake failed ({e}): the probes light nothing until baked')


def _has_sim(group, seen=None):
    seen = seen or set()
    if group.name in seen:
        return False
    seen.add(group.name)
    for n in group.nodes:
        if n.bl_idname == 'GeometryNodeSimulationInput':
            return True
        if n.bl_idname == 'GeometryNodeGroup' and n.node_tree and _has_sim(n.node_tree, seen):
            return True
    return False


def _audits(run, scene, policy, script_ns, assets, notes=(), modules=None):
    led, cfg = run.led, run.cfg
    if modules is None:
        modules = audits.eidoblend_modules()
    with run.step('audits'):
        if not policy['flags'].get('_no_auto_placement_check'):
            _placement(run, scene, policy)
        if not audits.preflight(led, scene, cfg, notes):
            raise RuntimeError('preflight: the scene has no camera, so nothing can render')
        audits.coverage(led, scene, policy)            # the inventory, every declaration and the global disables
        audits.motion(led, scene, cfg, policy)
        audits.framing(led, scene)
        audits.palette(led, scene, modules, cfg)
        if assets is not None:
            audits.assets_used(led, assets, cfg)


PLACEMENT_KEYS = ('clipping', 'hovering', 'density', 'z_fighting', 'facing', 'line_intrusion', 'floaters')
VISIBLE_GAP = 0.05          # m: a "near" seating gap at least this big is in the air, not a seating tolerance


def _placement(run, scene, policy):
    """The placement family's audits (eidoblend.placement.run_placement_audits) run on EVERY build and every
    hand-edited reopen, as the WebGPU runner ran checkClipping / checkHovering / ... after every setup(): a scene
    that never imports the family is audited all the same (a prop dumped in mid-air by a hand-set location is
    exactly what they exist to catch). The scene-wide flag _no_auto_placement_check is the only way out, and it is
    recorded as a declared exception (the checks it switched off are UNOBSERVED, not passed).

    Most of what the family returns is DATA, and is recorded as such (PASS): every contact or overlap pair
    (clipping: "data, not defects"), a display panel's clearances (facing), the object count (density). WARN is
    kept for what the family itself calls a defect: an object substantially INSIDE another (clipping, 'deep'),
    one with no real support (floaters: 'void' / 'far'), a panel interpenetrating or buried (facing), something
    planted in a transport line (line_intrusion); and two harness readings: a coplanar pair of two THIN sheets
    (z_fighting: a decal flush on a wall flickers; a thick object resting on a floor plane does not, its bottom
    face is hidden under it) and a "near" seating gap of VISIBLE_GAP or more (the family's near reaches 1 m: a
    clock left 0.45 m above the floor is in the air, not seated)."""
    led = run.led
    try:
        import importlib
        fn = importlib.import_module('eidoblend.placement').run_placement_audits
    except Exception as e:                                           # noqa: BLE001
        led.record(check='placement', outcome='SKIPPED', cls='CORRECTNESS',
                   message=f'the placement checks (clipping, hovering, density, z-fighting, facing, line intrusion) '
                           f'could not load ({type(e).__name__}: {e}): their obligations are UNOBSERVED.')
        return
    try:
        res = fn(scene, auto_fix=bool(policy['flags'].get('_auto_fix_placement'))) or {}
    except Exception as e:                                           # noqa: BLE001
        led.record(check='placement', outcome='SKIPPED', cls='CORRECTNESS',
                   message=f'eidoblend.placement.run_placement_audits failed ({type(e).__name__}: {e}): UNOBSERVED')
        return
    if not res:
        led.record(check='placement', outcome='SKIPPED', cls='CORRECTNESS',
                   message='eidoblend.placement skipped its audits (its scene flag): UNOBSERVED')
        return
    if policy['flags'].get('_auto_fix_placement'):
        led.record(check='repair', outcome='PASS', cls='REVIEW',
                   message='opt-in placement repair ran before the audits (the scene was changed by request)')

    def nm(ob):
        return getattr(ob, 'name', None) or str(ob)[:60]

    def listed(items, fmt, n=6):
        return ', '.join(fmt(i) for i in items[:n]) + (' ...' if len(items) > n else '')

    def put(key, warn, data, warn_msg, data_msg, cls='CORRECTNESS'):
        if warn:
            led.record(check=f'placement.{key}', outcome='WARN', cls=cls, metrics={'count': len(warn), 'data': len(data)},
                       message=warn_msg + ' (eidoblend.placement; its log lines above say more)')
        else:
            led.record(check=f'placement.{key}', outcome='PASS', cls='INFO', metrics={'data': len(data)},
                       message=data_msg)

    def items(key):
        v = res.get(key) or []
        return list(v) if isinstance(v, (list, tuple)) else [v]
    if 'clipping' in res:
        pairs = [p for p in items('clipping') if isinstance(p, dict)]
        deep = [p for p in pairs if p.get('deep')]
        put('clipping', deep, pairs,
            f'{len(deep)} object(s) substantially INSIDE another: '
            + listed(deep, lambda p: f"{nm(p.get('a'))} / {nm(p.get('b'))}"),
            f'{len(pairs)} contact or overlap pair(s) measured (data, not defects), none deep'
            + (': ' + listed(pairs, lambda p: f"{nm(p.get('a'))} / {nm(p.get('b'))}", 4) if pairs else ''))
    if 'hovering' in res:
        near = sorted((h for h in items('hovering') if isinstance(h, dict) and h.get('kind') == 'near'),
                      key=lambda h: -float(h.get('gap', 0)))
        big = [h for h in near if float(h.get('gap', 0)) >= VISIBLE_GAP]
        put('hovering', big, near,
            f'{len(big)} object(s) in the air above their surface, more than a seating gap: '
            + listed(big, lambda h: f"{nm(h.get('obj'))} {float(h.get('gap', 0)):.2f} m"),
            (f'{len(near)} seating gap(s) under {VISIBLE_GAP * 100:.0f} cm: '
             + listed(near, lambda h: f"{nm(h.get('obj'))} {float(h.get('gap', 0)) * 1000:.0f} mm")) if near
            else 'nothing hovers above its surface')
    if 'floaters' in res:
        fl = [h for h in items('floaters') if isinstance(h, dict)]
        put('floaters', fl, fl,
            f'{len(fl)} object(s) genuinely unsupported, which read as floating on camera: '
            + listed(fl, lambda h: nm(h.get('obj')) + (' (nothing beneath)' if h.get('kind') == 'void' else
                                                       f" ({float(h.get('gap', 0)):.2f} m up)"))
            + ". place_on(obj, surface) seats a piece; a flyer declares obj['no_support_check'] = True",
            'every solid piece rests on a surface')
    if 'z_fighting' in res:
        pairs = [p for p in items('z_fighting') if isinstance(p, dict)]

        def sheets(p):
            ax = 'xyz'.index(p.get('axis', 'z')) if p.get('axis') in ('x', 'y', 'z') else 2
            thin = []
            for ob in (p.get('a'), p.get('b')):
                b = audits.world_box(ob) if ob is not None else None
                thin.append(b is not None and (b[1][ax] - b[0][ax]) < 0.06)
            return all(thin)
        bad = [p for p in pairs if sheets(p)]
        put('z_fighting', bad, pairs,
            f'{len(bad)} pair(s) of thin sheets share a face depth and will flicker: '
            + listed(bad, lambda p: f"{nm(p.get('a'))} <=> {nm(p.get('b'))} ({p.get('axis')})")
            + '. A few mm either way settles it',
            (f'{len(pairs)} coplanar contact(s) of a sheet and a solid resting on it (no flicker: the solid hides '
             'its own face): ' + listed(pairs, lambda p: f"{nm(p.get('a'))} / {nm(p.get('b'))}", 4)) if pairs
            else 'no coplanar faces')
    if 'facing' in res:
        panels = [p for p in items('facing') if isinstance(p, dict)]
        bad = [p for p in panels if p.get('penetrated') or all(
            float((p.get('clearance') or {}).get(k, float('inf'))) < 0.3 for k in ('plus', 'minus'))]
        put('facing', bad, panels,
            f'{len(bad)} display panel(s) interpenetrating something or buried on both sides: '
            + listed(bad, lambda p: nm(p.get('obj'))),
            f'{len(panels)} display panel(s) measured, each facing open space' if panels else 'no display panels')
    if 'line_intrusion' in res:
        li = [p for p in items('line_intrusion') if isinstance(p, dict)]
        put('line_intrusion', li, li,
            f'{len(li)} object(s) planted IN a transport line: '
            + listed(li, lambda p: f"{nm(p.get('obj'))} in {nm(p.get('line'))}"),
            'nothing stands in a transport line')
    if 'seated_facing' in res:
        sf = [p for p in items('seated_facing') if isinstance(p, dict)]
        back = [p for p in sf if float(p.get('deg', 0)) > 110]
        if back:
            put('seated_facing', back, sf,
                'RE-RENDER REQUIRED: ' + listed(back, lambda p: f"{nm(p.get('obj'))} faces the BACKREST of "
                                                               f"{nm(p.get('chair'))} ({float(p.get('deg', 0)):.0f} deg off)")
                + '. Most often a rotation set after seat_on: pass face= to seat_on instead', '')
        elif sf:
            led.record(check='placement.seated_facing', outcome='WARN', cls='REVIEW', metrics={'count': len(sf)},
                       message=listed(sf, lambda p: f"{nm(p.get('obj'))} is {float(p.get('deg', 0)):.0f} deg off "
                                                    f"{nm(p.get('chair'))}'s natural facing")
                       + ': verify the render (deliberate? pass face= to seat_on)')
    if 'density' in res:
        v = res['density']
        led.record(check='placement.density', outcome='PASS', cls='INFO', metrics={'value': v},
                   message=f'{v} distinct top-level object(s) placed (an observation, never a demand)')


# --------------------------------------------------------------------------------------------------- render ---

def render(run: Run, scene):
    mode, cfg, job, led = run.mode, run.cfg, run.job, run.led
    fs, fe = scene.frame_start, scene.frame_end
    if mode == 'build':
        return
    preset = job.get('preset') or ('probe' if mode == 'probe' else (cfg.get('render') or {}).get('preset', 'film'))
    if preset == 'probe':
        caps = settings.apply_probe_caps(scene)
        led.record(check='render.preset', outcome='PASS', cls='INFO',
                   message='probe caps (not saved): ' + (', '.join(caps) if caps else 'already within them'))
    post.match_overlay(scene)                          # a composited overlay scene renders the film's size
    led.record(check='render.settings', outcome='PASS', cls='INFO', metrics=settings.describe(scene),
               message=_settings_line(scene))
    if mode == 'capture':
        fps = float(cfg['fps'])
        frames = sorted({min(fe, max(fs, common.frame_at(t, fps, fs))) for t in job['at']})
        pre = int(round(float(job.get('preroll') or 0) * fps))
        # effects that read earlier frames back (look.post.history): each still renders the frames its records come
        # from first, in order, from its shot's start or as far back as the effect reads, as the film renders them
        hist = output.post_histories(scene)
        ran, lead, leads = None, 0, []
        with run.step(f'capture {len(frames)} frame(s)'):
            for f in frames:
                first = output.history_lead_in(scene, f, hist) if hist else f
                if ran is not None and first <= ran + 1:
                    first = ran + 1                          # this run already rendered (and recorded) the frames before
                for g in range(max(fs, f - pre), first):
                    scene.frame_set(g)
                if first < f:
                    t0 = time.perf_counter()
                    n = output.render_lead_in(scene, first, f, hist)
                    lead += n
                    leads.append(f'{first}-{f - 1}')
                    common.log('eido_blender', f'frame {f}: lead-in frames {first}-{f - 1} rendered for the post '
                               f"chain's records ({', '.join(h['key'] for h in hist)}): {time.perf_counter() - t0:.1f} s")
                png = cfgmod.capture_png(run.paths['stem'], common.time_at(f, fps, fs))
                t0 = time.perf_counter()
                output.render_still(scene, f, png)
                ran = f
                output.prune_histories(hist, f)
                run.outputs.append(png)
                common.log('eido_blender', f'frame {f} ({common.time_at(f, fps, fs):.2f} s): '
                           f'{time.perf_counter() - t0:.1f} s -> {png}')
        msg = f'{len(frames)} still(s) at frames {frames}' + (f', {pre}-frame preroll' if pre else '')
        if hist:
            kinds = ', '.join(f"{h['key']} ({'its shot from its cut' if h['feedback'] else str(h['depth']) + ' back'})"
                              for h in hist)
            msg += (f'; {lead} lead-in frame(s) rendered first, in order ({", ".join(leads) or "none needed"}), so the '
                    f"post chain's records of earlier frames hold what the film gives each still: {kinds}")
        led.record(check='render.capture', outcome='PASS', cls='INFO',
                   metrics={'stills': len(frames), 'lead_in_frames': lead}, message=msg)
        return
    if mode == 'bench':
        n = max(1, int(job.get('frames') or 3))
        picks = sorted({fs + int((fe - fs) * k / max(1, n - 1)) for k in range(n)}) if n > 1 else [(fs + fe) // 2]
        times = []
        with run.step(f'bench {len(picks)} frame(s)'):
            for f in picks:
                scene.frame_set(f)
                t0 = time.perf_counter()
                bpy.ops.render.render(write_still=False)
                times.append(time.perf_counter() - t0)
                common.log('eido_blender', f'bench frame {f}: {times[-1]:.2f} s')
        warm = times[1:] if len(times) > 1 else times
        per = sum(warm) / len(warm)
        total = per * (fe - fs + 1)
        led.record(check='render.bench', outcome='PASS', cls='INFO',
                   metrics={'seconds_per_frame': round(per, 3), 'frames': fe - fs + 1, 'estimate_s': round(total, 1),
                            'samples': times},
                   message=f'{per:.2f} s a frame (first frame {times[0]:.2f} s, shaders included): the whole film '
                           f'({fe - fs + 1} frames) ~{total / 60:.1f} min at these settings')
        print(f'[bench] {per:.2f} s a frame; {fe - fs + 1} frames ~ {total / 60:.1f} min', flush=True)
        return
    video = run.paths['video']
    if mode == 'probe':
        n = max(1, int(job.get('frames') or 1))
        a, b = fs, min(fe, fs + n - 1)
    else:
        a, b = fs, fe
    prev = output.displace(video)
    if prev:
        common.log('eido_blender', f'moved the previous output to {prev}: if this run fails, {video} will NOT exist')
    t0 = time.perf_counter()
    with run.step(f'render frames {a}-{b} to H.264'):
        output.render_video(scene, video, a, b)
    dt = time.perf_counter() - t0
    run.outputs.append(video)
    info = output.probe_video(video)
    led.record(check='render.video', outcome='PASS', cls='INFO', metrics={'seconds': round(dt, 1), **info},
               message=f'{b - a + 1} frame(s) in {dt:.1f} s ({dt / (b - a + 1):.2f} s a frame) -> {video} '
                       + (f"({info.get('codec_name')} {info.get('profile')} {info.get('pix_fmt')} "
                          f"{info.get('width')}x{info.get('height')}, {info.get('nb_read_frames')} frames)" if info else ''))
    try:
        pngs = output.extract_probe_frames(video, b - a + 1)
        run.outputs.extend(pngs)
        if not pngs:
            led.record(check='render.probe_frames', outcome='SKIPPED', cls='REVIEW',
                       message='no ffmpeg on PATH: extract and VIEW frames yourself')
    except Exception as e:                                           # noqa: BLE001
        led.record(check='render.probe_frames', outcome='SKIPPED', cls='REVIEW',
                   message=f'probe-frame extraction failed ({e}): extract and VIEW frames yourself')


def _settings_line(scene):
    d = settings.describe(scene)
    return (f"EEVEE {d['size'][0]}x{d['size'][1]} ({d['size'][2]}%), {d['fps']} fps, frames {d['frames'][0]}-"
            f"{d['frames'][1]}, {d['samples']} samples, raytracing {d['raytracing']} (traces {d['trace_resolution']}), "
            f"motion blur {d['motion_blur'][0]} ({d['motion_blur'][1]}), volumes {d['volumes'][0]} px x "
            f"{d['volumes'][1]}, {d['colour'][0]} / {d['colour'][1]} / {d['colour'][2]:+} EV, world {d['world']}, "
            f"camera {d['camera']}")
