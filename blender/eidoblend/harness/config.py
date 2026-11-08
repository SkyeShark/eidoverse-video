"""eidoblend.harness.config: the scene config (scene.json) and the run job. Plain Python, no bpy: eido_blender.py
reads and checks the config before Blender starts, and the runner inside Blender reads the job it wrote.

scene.json keeps the WebGPU edition's keys:

    {
        "width": 1920, "height": 1080, "fps": 24, "duration": 12,
        "script": "work/<id>/scene.py",
        "outputVideo": "work/<id>/scene.mp4",
        "assets": {"floor_scan": "work/<id>/floor.glb", "kettle": "eidoverse/assets/models/....glb"},
        "frame_start": 1,
        "render": {"preset": "film", "samples": 64, "motion_blur": true}
    }

Paths are relative to the repository root unless absolute. "render" and "frame_start" are optional (the Blender
edition's two additions); RENDER_KEYS below lists what "render" may hold. Without "outputVideo" the film is
"composedOutput", else "<outputDir>.mp4", else <config name>.mp4 beside the config (render_scene.mjs's order).
The film has ceil(duration x fps) frames.
"""

from __future__ import annotations

import json
import math
import os
import re
import urllib.parse

from .. import common

DEFAULTS = {'width': 1280, 'height': 720, 'fps': 30, 'duration': 5.0, 'frame_start': 1}
KNOWN_KEYS = {'width', 'height', 'fps', 'duration', 'script', 'outputVideo', 'assets', 'frame_start', 'render',
              'capture', 'composedOutput', 'outputDir', 'title', 'notes', 'description'}
PRESETS = ('film', 'probe')
# the "render" block: applied AFTER setup(), so it overrides what the script set (a per-run choice: samples, blur)
RENDER_KEYS = {
    'preset': 'film | probe: probe renders this scene at the probe caps every time (at render time, never saved)',
    'samples': 'EEVEE render samples (taa_render_samples)',
    'motion_blur': 'true/false',
    'shutter': 'motion blur shutter, in frames (0.5 = a 180-degree shutter)',
    'raytracing': 'true/false: EEVEE ray tracing (screen-space traces + denoise)',
    'volume_tile': 'volumetric tile size in pixels (1, 2, 4, 8, 16)',
    'volume_samples': 'volumetric samples',
    'exposure': 'view exposure in stops',
    'look': "AgX look, e.g. 'AgX - Base Contrast', 'AgX - Punchy', 'None'",
    'bloom': 'true or {"threshold": 1.0, "size": 0.5, "strength": 1.0}: a compositor Glare (bloom) pass',
    'film_transparent': 'true/false: transparent background (PNG captures keep alpha; video does not)',
    'resolution_percentage': 'render at this percentage of width x height',
}
PROBE_MAX = (960, 540)          # the probe preset's cap (long side, short side)
PROBE_SAMPLES = 16


class ConfigError(ValueError):
    pass


def is_url(s: str) -> bool:
    return bool(re.match(r'^[a-z][a-z0-9+.-]*://', str(s), re.I)) and not re.match(r'^[a-z]:[\\/]', str(s), re.I)


def load_config(path: str) -> dict:
    """Read scene.json, fill the defaults, resolve paths, and check what can be checked without Blender.

    Returns a new dict: the original keys plus '_scene_json' (absolute), '_script' (absolute), '_output' (absolute
    output video), '_assets' ({key: absolute path or URL}), '_blend' and '_build_json' (the build's files beside the
    output) and '_warnings' (a list of strings)."""
    path = os.path.abspath(path)
    if not os.path.isfile(path):
        raise ConfigError(f'{path}: not found')
    try:
        with open(path, encoding='utf-8') as f:
            cfg = json.load(f)
    except json.JSONDecodeError as e:
        raise ConfigError(f'{path}: not valid JSON ({e})')
    if not isinstance(cfg, dict):
        raise ConfigError(f'{path}: the config must be a JSON object')
    warnings = []
    for k in sorted(set(cfg) - KNOWN_KEYS):
        if not k.startswith('_'):
            warnings.append(f"unknown config key '{k}' (ignored)")
    if 'inlineScript' in cfg:
        raise ConfigError("'inlineScript' is not supported in the Blender edition: put the script in a .py file")
    out = dict(DEFAULTS)
    out.update(cfg)
    for k in ('width', 'height', 'frame_start'):
        try:
            out[k] = int(out[k])
        except (TypeError, ValueError):
            raise ConfigError(f"'{k}' must be an integer, got {out[k]!r}")
    for k in ('fps', 'duration'):
        try:
            out[k] = float(out[k])
        except (TypeError, ValueError):
            raise ConfigError(f"'{k}' must be a number, got {out[k]!r}")
    if out['fps'] == int(out['fps']):
        out['fps'] = int(out['fps'])
    if out['width'] <= 0 or out['height'] <= 0:
        raise ConfigError('width and height must be positive')
    if out['width'] % 2 or out['height'] % 2:
        raise ConfigError(f"width x height {out['width']}x{out['height']}: H.264 (yuv420p) needs even sizes")
    if out['fps'] <= 0 or out['duration'] <= 0:
        raise ConfigError('fps and duration must be positive')
    if not out.get('script'):
        raise ConfigError("'script' is required: the scene's Python file with setup(ctx)")
    out['_scene_json'] = path
    out['_script'] = common.repo_path(out['script'])
    if not out['_script'].endswith('.py'):
        raise ConfigError(f"script {out['script']}: the Blender edition runs Python scene scripts (.py); "
                          "a WebGPU .js scene is the port's source, not something this harness runs")
    if not os.path.isfile(out['_script']):
        raise ConfigError(f"script {out['script']}: not found ({out['_script']})")
    stem = os.path.splitext(os.path.basename(path))[0]
    # as render_scene.mjs: outputVideo, else composedOutput, else <outputDir>.mp4; with none of them, the film is
    # named after the config, beside it
    video = out.get('outputVideo') or out.get('composedOutput')
    if not video:
        video = (out['outputDir'].rstrip('/\\') + '.mp4') if out.get('outputDir') else \
            os.path.join(os.path.dirname(path), stem + '.mp4')
    out['_output'] = common.repo_path(video)
    if os.path.splitext(out['_output'])[1].lower() not in ('.mp4', '.mov', '.mkv'):
        raise ConfigError(f"outputVideo {video}: use .mp4 (or .mov / .mkv)")
    ostem = os.path.splitext(out['_output'])[0]          # the build is named after the film, as every other output
    out['_blend'] = ostem + '.blend'
    out['_build_json'] = ostem + '.build.json'
    out['_job'] = ostem + '.job.json'
    assets = out.get('assets') or {}
    if not isinstance(assets, dict):
        raise ConfigError("'assets' must be an object {key: path}")
    resolved = {}
    for key, v in assets.items():
        if isinstance(v, dict) and 'path' in v:
            v = v['path']
        if not isinstance(v, str) or not v.strip():
            raise ConfigError(f"asset '{key}': give a file path (or URL), got {v!r}")
        resolved[key] = v if is_url(v) else common.repo_path(v)
    out['_assets'] = resolved
    render = out.get('render') or {}
    if not isinstance(render, dict):
        raise ConfigError("'render' must be an object")
    for k in sorted(set(render) - set(RENDER_KEYS)):
        warnings.append(f"unknown render key '{k}' (ignored); known: {', '.join(sorted(RENDER_KEYS))}")
    if render.get('preset', 'film') not in PRESETS:
        raise ConfigError(f"render.preset must be one of {PRESETS}")
    out['render'] = render
    out['_warnings'] = warnings
    return out


def total_frames(cfg: dict) -> int:
    """Frames in the film: ceil(duration x fps), at least 1, as render_scene.mjs counts them (a part frame is a
    frame). The product is trimmed by 1e-9 first, so 2.9999999 x 24 does not become 73."""
    return max(1, int(math.ceil(float(cfg['duration']) * float(cfg['fps']) - 1e-9)))


def frame_range(cfg: dict) -> tuple:
    fs = int(cfg['frame_start'])
    return fs, fs + total_frames(cfg) - 1


def missing_assets(cfg: dict) -> list:
    """Declared local assets that are absent or empty (URLs are checked when they are downloaded)."""
    bad = []
    for key, p in cfg['_assets'].items():
        if is_url(p):
            continue
        if not os.path.exists(p):
            bad.append(f"asset '{key}': {p} does not exist")
        elif os.path.isfile(p) and os.path.getsize(p) == 0:
            bad.append(f"asset '{key}': {p} is empty")
    return bad


def output_paths(cfg: dict, mode: str) -> dict:
    """The files a run writes, by mode (film | probe | capture | bench | build), next to outputVideo.

    film      <out>.mp4, <stem>_probe1..3.png (frames at 15/50/85 %), <stem>.audit.txt / .audit.json
    probe     <stem>_probe.mp4, <stem>_probe_probe1..3.png, <stem>_probe.audit.txt / .json
    capture   <stem>_probe_at<seconds>s.png (seconds = the frame's own time, 2 decimals), <stem>_probe.audit.*
    build     the .blend and .build.json only, <stem>_build.audit.*
    bench     no images, <stem>_bench.audit.*
    """
    out = cfg['_output']
    stem, ext = os.path.splitext(out)
    if mode in ('probe', 'capture'):
        video = f'{stem}_probe{ext}'
    elif mode in ('build', 'bench'):
        video = f'{stem}_{mode}{ext}'                  # never written; names the digest so no run overwrites another's
    else:
        video = out
    vstem = os.path.splitext(video)[0]
    return {'video': video, 'stem': vstem, 'audit_txt': vstem + '.audit.txt', 'audit_json': vstem + '.audit.json',
            'part': video + '.part', 'prev': video + '.prev'}


def capture_png(stem: str, seconds: float) -> str:
    return f'{stem}_at{seconds:.2f}s.png'


def asset_download_dir(cfg: dict) -> str:
    """Where URL assets are downloaded: an _assets folder beside the scene config."""
    return os.path.join(os.path.dirname(cfg['_scene_json']), '_assets')


def url_filename(url: str) -> str:
    name = os.path.basename(urllib.parse.urlparse(url).path) or 'asset'
    return re.sub(r'[^A-Za-z0-9._-]+', '_', name)
