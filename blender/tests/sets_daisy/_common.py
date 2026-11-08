"""What the sets_daisy tests share: sys.path, the shared texture library, a clean scene, the probe look, PASS/FAIL lines,
the claudesona at a set's mark, and stills at chosen frames (each through the frame's own camera marker).

Run from the main checkout (renders through the GPU slot):
    cd <main checkout> && HEAVY_VRAM_GB=4 bash work/claude_body/work/tmp/heavy.sh 12 bash run_blender.sh \
        <worktree>/blender/tests/sets_daisy/test_funeral.py [-- --only 3,5 --no-render]
"""

import math
import os
import sys
import time

import bpy

HERE = os.path.dirname(os.path.abspath(__file__))
WORKTREE = os.path.normpath(os.path.join(HERE, '..', '..', '..'))
sys.path.insert(0, os.path.join(WORKTREE, 'blender'))
OUT = os.path.join(HERE, 'out')
os.makedirs(OUT, exist_ok=True)
# the shared CC0 library: the main checkout's holds every set these sets read (no downloads from a test); a worktree's
# own cache may hold only what other work fetched into it, so the main one is preferred whenever it is on the machine
MAIN_CACHE = 'C:/Users/sdn52/OneDrive/Desktop/eidoverse-video-prealpha-0.01/eidoverse/assets/cache'
if not os.environ.get('EIDO_ASSET_CACHE') and os.path.isdir(os.path.join(MAIN_CACHE, 'textures')):
    os.environ['EIDO_ASSET_CACHE'] = MAIN_CACHE
os.environ.setdefault('EIDO_NO_FETCH', '1')

RESULTS = []


def args():
    a = sys.argv[sys.argv.index('--') + 1:] if '--' in sys.argv else []
    out = {'flags': set()}
    i = 0
    while i < len(a):
        if a[i].startswith('--') and i + 1 < len(a) and not a[i + 1].startswith('--'):
            out[a[i][2:]] = a[i + 1]
            i += 2
        else:
            out['flags'].add(a[i].lstrip('-'))
            i += 1
    return out


def check(name, ok, detail=''):
    line = ('PASS ' if ok else 'FAIL ') + name + (('  ' + detail) if detail else '')
    print(line, flush=True)
    RESULTS.append((name, bool(ok), detail))
    return ok


def summary(tag):
    n_fail = sum(1 for r in RESULTS if not r[1])
    print(f'[{tag}] {len(RESULTS) - n_fail} passed, {n_fail} failed', flush=True)
    return n_fail


def clean_scene(fps=30, frames=(1, 2), res=(960, 540)):
    for o in list(bpy.data.objects):
        bpy.data.objects.remove(o, do_unlink=True)
    for c in list(bpy.data.collections):
        bpy.data.collections.remove(c)
    sc = bpy.context.scene
    bpy.context.preferences.filepaths.save_version = 0       # no .blend1 backups in out/
    sc.render.fps, sc.render.fps_base = fps, 1.0
    sc.frame_start, sc.frame_end = frames
    sc.render.resolution_x, sc.render.resolution_y = res
    sc.render.resolution_percentage = 100
    sc.render.engine = 'BLENDER_EEVEE'
    return sc


def probe_look(sc, interior=True, exposure=0.0, bloom=True, samples=16):
    """the look family's probe preset (960 x 540, 16 samples), fast GI off indoors, a Glare bloom for the HDR glows."""
    from eidoblend.look import render_settings as RS
    done = RS.apply_auto_enhance(sc, 'probe', samples=samples, exposure=exposure,
                                 ao=False if interior else None,
                                 bloom={'strength': 0.3, 'threshold': 1.2, 'size': 0.6} if bloom else False,
                                 motion_blur=False)
    sc.view_settings.view_transform = 'AgX'
    return done


def claudesona(location_fn, frames, fps, u0=0.0, name='claudesona'):
    """claude_suit.vrm at 0.87 (the scale every set frames) breathing on the spot, at the set's mark, keyed per frame
    (a CONSTANT step at each cut of the mark)."""
    from eidoblend.characters import load_vrm, play_vrma_default
    h = load_vrm('claude_suit', name=name)
    arm = h.arm if hasattr(h, 'arm') else h.armature
    arm.scale = (0.87, 0.87, 0.87)
    try:
        play_vrma_default(h, 'idle')
    except Exception as e:                                     # noqa: BLE001
        print(f'[claudesona] idle clip: {e}')
    last = None
    arm.rotation_mode = 'XYZ'
    for f in range(frames[0], frames[1] + 1):
        u = u0 + (f - frames[0]) / fps
        m = location_fn(u)
        key = (tuple(round(x, 5) for x in m['pos']), round(m['yaw'], 5))
        if key != last or f == frames[0] or f == frames[1]:
            arm.location = m['pos']
            arm.rotation_euler = (0.0, 0.0, m['yaw'])
            for p in ('location', 'rotation_euler'):
                arm.keyframe_insert(p, frame=f)
            last = key
    ad = arm.animation_data
    if ad and ad.action:
        from eidoblend.sets.daisy.funeral import action_fcurves
        for fc in action_fcurves(ad.action):
            if fc.data_path in ('location', 'rotation_euler'):
                for k in fc.keyframe_points:
                    k.interpolation = 'CONSTANT'
    return h


def render_still(sc, frame, path):
    """a still at `frame` through the camera its marker binds (Blender's renders follow the markers)."""
    from eidoblend.look import camera as LC
    sc.frame_set(frame)
    cam = LC.camera_at(sc, frame)
    if cam is not None:
        sc.camera = cam
    sc.render.filepath = path
    sc.render.image_settings.media_type = 'IMAGE'
    sc.render.image_settings.file_format = 'PNG'
    t0 = time.time()
    bpy.ops.render.render(write_still=True)
    dt = time.time() - t0
    ok = os.path.isfile(path)
    print(f'[render] frame {frame} -> {os.path.basename(path)} ({dt:.1f} s){"" if ok else "  MISSING"}', flush=True)
    return ok, dt


def image_stats(path):
    """mean / max luma (0..1) of a PNG, and the share of pure magenta (a missing texture)."""
    import numpy as np
    img = bpy.data.images.load(path, check_existing=False)
    px = np.empty(img.size[0] * img.size[1] * img.channels, np.float32)
    img.pixels.foreach_get(px)
    px = px.reshape(-1, img.channels)
    bpy.data.images.remove(img)
    luma = px[:, 0] * 0.2126 + px[:, 1] * 0.7152 + px[:, 2] * 0.0722
    magenta = float(((px[:, 0] > 0.95) & (px[:, 1] < 0.05) & (px[:, 2] > 0.95)).mean())
    return {'mean': float(luma.mean()), 'max': float(luma.max()), 'magenta': magenta}


def frame_of(u, u0, f0, fps):
    return f0 + int(round((u - u0) * fps))


def write_stills(out_dir, stills):
    """the stills a test renders, for render_saved.py: [(name, u, frame[, camera name])] -> out_dir/stills.json."""
    import json
    rows = [{'name': s[0], 'u': float(s[1]), 'frame': int(s[2]), **({'camera': s[3]} if len(s) > 3 and s[3] else {})}
            for s in stills]
    with open(os.path.join(out_dir, 'stills.json'), 'w', encoding='utf-8') as f:
        json.dump(rows, f, indent=1)
    return rows


def select_stills(stills, only):
    """--only a,b,3: the stills named, or at those list indices."""
    if not only:
        return stills
    keep = set(only.split(','))
    return [s for i, s in enumerate(stills) if str(i) in keep or s[0] in keep]


def vclose(a, b, tol=1e-4):
    return all(abs(x - y) <= tol for x, y in zip(a, b))


def deg(x):
    return math.degrees(x)
