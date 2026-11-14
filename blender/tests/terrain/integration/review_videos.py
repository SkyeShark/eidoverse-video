"""The review videos (design section 10 item 8): per recipe an 8 s aerial orbit and a 6 s dolly at 1.7 m in the
reference rig's grey clay, and the same dolly over the built terrain (hero levels, palette, rocks). System Python;
each recipe is one Blender process (video_job.py) through the GPU slot:

    python blender/tests/terrain/integration/review_videos.py [--recipes canyon,dunes] [--no-textured | --no-clay]

The field and the eye spot are the judge's (recipe_sheets.py first: sheets/judge/<recipe>/); the meadow, which has
no place, is generated in the job and walked from the meadow probe's camera. Each video gets a silent AAC track, so
ordinary players open it, and is checked: ffprobe (H.264 High, yuv420p, 960 x 540, AAC) and a full decode.
Writes blender/tests/terrain/out/videos/<recipe>_orbit.mp4, _dolly.mp4, _dolly_textured.mp4 and videos.json.
"""
import argparse
import json
import os
import subprocess
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
TN = os.path.normpath(os.path.join(HERE, '..'))
sys.path.insert(0, TN)
sys.path.insert(0, HERE)

from judge import run as JR  # noqa: E402
from recipe_sheets import RECIPES  # noqa: E402

OUT = os.path.join(TN, 'out', 'videos')
SHEETS = os.path.join(TN, 'out', 'integration', 'sheets')
MEADOW = dict(reference='palouse_hills', seed=7,
              eye=dict(x=0.0, y=-7.0, look_x=0.0, look_y=60.0, look_dz=-0.4, lens_mm=35.0),
              flatten=[{'at': [0.0, 0.0], 'radius': 8.0, 'falloff': 8.0}])


def mux_aac(raw, final):
    """The video stream as it is, plus a silent stereo AAC track; +faststart."""
    subprocess.run(['ffmpeg', '-y', '-v', 'error', '-i', raw, '-f', 'lavfi',
                    '-i', 'anullsrc=channel_layout=stereo:sample_rate=48000', '-map', '0:v:0', '-map', '1:a:0',
                    '-c:v', 'copy', '-c:a', 'aac', '-b:a', '128k', '-shortest', '-movflags', '+faststart', final],
                   check=True)


def check(path):
    out = subprocess.run(['ffprobe', '-v', 'error', '-show_entries',
                          'stream=codec_type,codec_name,profile,pix_fmt,width,height,nb_frames:format=duration',
                          '-of', 'json', path], capture_output=True, text=True, check=True).stdout
    j = json.loads(out)
    v = next((s for s in j['streams'] if s['codec_type'] == 'video'), {})
    au = next((s for s in j['streams'] if s['codec_type'] == 'audio'), {})
    dec = subprocess.run(['ffmpeg', '-v', 'error', '-i', path, '-f', 'null', '-'], capture_output=True, text=True)
    r = dict(video=v.get('codec_name'), profile=v.get('profile'), pix_fmt=v.get('pix_fmt'), width=v.get('width'),
             height=v.get('height'), frames=int(v.get('nb_frames') or 0), audio=au.get('codec_name'),
             duration=round(float(j.get('format', {}).get('duration', 0.0)), 2),
             decodes=dec.returncode == 0 and not dec.stderr.strip(), size_mb=round(os.path.getsize(path) / 1e6, 2))
    r['ok'] = (r['video'] == 'h264' and r['profile'] == 'High' and r['pix_fmt'] == 'yuv420p'
               and (r['width'], r['height']) == (960, 540) and r['audio'] == 'aac' and r['decodes'])
    return r


def main():
    ap = argparse.ArgumentParser(description=__doc__.split('\n\n')[0])
    ap.add_argument('--recipes', default='')
    ap.add_argument('--no-textured', action='store_true')
    ap.add_argument('--no-clay', action='store_true')
    ap.add_argument('--slot-wait', type=float, default=600.0, help='minutes to wait for a free GPU slot per job')
    ap.add_argument('--index', default='videos.json', help='the record file in out/videos/ (a second pass running '
                                                           'beside the first keeps its own)')
    a = ap.parse_args()
    names = [r for r in a.recipes.split(',') if r] or list(RECIPES)
    raw_root = os.path.join(OUT, '_raw' if a.index == 'videos.json' else '_raw_' + os.path.splitext(a.index)[0])
    os.makedirs(raw_root, exist_ok=True)
    idx_path = os.path.join(OUT, a.index)
    index = json.load(open(idx_path, encoding='utf-8')) if os.path.exists(idx_path) else {}
    for r in names:
        raw = os.path.join(raw_root, r)
        os.makedirs(raw, exist_ok=True)
        if r == 'meadow':
            spec = os.path.join(raw, 'spec.json')
            with open(spec, 'w', encoding='utf-8') as f:
                json.dump(dict(eye=MEADOW['eye'], flatten=MEADOW['flatten']), f)
            args = ['--recipe', r, '--reference', MEADOW['reference'], '--seed', str(MEADOW['seed']), '--spec', spec]
        else:
            jd = os.path.join(SHEETS, 'judge', r)
            field = os.path.join(jd, f'{r}_seed1.npz')
            args = ['--recipe', r, '--reference', RECIPES[r]['ref'], '--seed', '1',
                    '--judge', os.path.join(jd, 'blender_job_result.json')]
            if os.path.exists(field):
                args += ['--field', field]
            else:
                print(f'[videos] {r}: no judged field ({field}): the job generates it', flush=True)
        args += ['--out', raw] + (['--no-textured'] if a.no_textured else []) + (['--no-clay'] if a.no_clay else [])
        t0 = time.time()
        print(f'[videos] {r}: rendering', flush=True)
        jp = os.path.join(raw, f'{r}_video_job.json')
        if os.path.exists(jp):
            os.remove(jp)
        rc, slot = JR.run_blender(os.path.join(HERE, 'video_job.py'), args, os.path.join(raw, 'blender.log'),
                                  timeout_min=a.slot_wait)
        entry = index.get(r, {})                  # a clay pass and a textured pass add to the same entry
        entry.update(rc=rc, slot=slot, seconds=round(time.time() - t0), when=time.strftime('%Y-%m-%d %H:%M'))
        if os.path.exists(jp):
            job = json.load(open(jp, encoding='utf-8'))
            entry['errors'] = job.get('errors')
            entry['eye'] = job.get('eye')
            if job.get('textured'):
                tex = job['textured']
                entry['textured'] = {k: tex.get(k) for k in ('build_s', 'render_s', 'walk_m', 'triangles', 'rocks')}
        entry.setdefault('files', {})
        for kind in ('orbit', 'dolly', 'dolly_textured'):
            src = os.path.join(raw, f'{r}_{kind}.mp4')
            if not os.path.exists(src):
                continue
            dst = os.path.join(OUT, f'{r}_{kind}.mp4')
            mux_aac(src, dst)
            entry['files'][kind] = dict(path=os.path.relpath(dst, TN).replace(os.sep, '/'), **check(dst))
            os.remove(src)
        index[r] = entry
        with open(idx_path, 'w', encoding='utf-8') as f:
            json.dump(index, f, indent=1)
        ok = all(v['ok'] for v in entry['files'].values()) and entry['files']
        print(f"[videos] {r}: {'ok' if ok else 'NOT OK'} ({', '.join(entry['files'])}; {entry['seconds']} s)"
              + (f"; errors {entry.get('errors')}" if entry.get('errors') else ''), flush=True)


if __name__ == '__main__':
    main()
