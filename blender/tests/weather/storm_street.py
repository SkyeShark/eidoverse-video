"""A storm rolling in over a city street: wet ground and puddles, rain and splashes, lightning lighting the street,
and the matching audio.

    bash run_blender.sh blender/tests/weather/storm_street.py --mode check    (plan + key only, no GPU: the schedule)
    bash run_blender.sh blender/tests/weather/storm_street.py --mode stills   [--res 960x540 --samples 16]
    bash run_blender.sh blender/tests/weather/storm_street.py --mode video    [--res 640x360 --samples 8]

Timeline, in media time from the scene's first frame (24 fps):
    0 - 38 s   'rain' at 17:00, a pre-roll the bake integrates but does not render: the street wets, puddles fill
    39 s       transition_to('darkstorm', 1, 9 s): the canopy seals, the sky goes dark, rain thickens, lightning
               starts; darkstorm's cadence guarantees its first event a close local candidate (no forcing here)
    the shot   38 - 58 s (frames 913 - 1392): the camera walks slowly down the street (0.55 m/s) with a slight pan,
               so the rain field must stand still in the world while the camera moves through it

stills: renders the shot's key frames (rain before the storm, the frame before the strike, the strike, the sparks,
the smoke a second later, the storm, and a distant strike when there is one) into out/street/ with a contact sheet.
video: renders the shot, bakes its weather audio (bake_weather_audio.py), muxes it (merge_av.py) into
out/street/storm_street_av.mp4 (H.264 High + AAC), and checks every thunderclap lands on its strike plus 1 s per 343 m.
"""
import argparse
import json
import math
import os
import subprocess
import sys
import time

import bpy
import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.normpath(os.path.join(HERE, '..', '..')))
sys.path.insert(0, HERE)
from eidoblend.sky import make_sky  # noqa: E402
from eidoblend.weather import make_weather_system  # noqa: E402
from street_set import build_street  # noqa: E402

argv = sys.argv[sys.argv.index('--') + 1:] if '--' in sys.argv else []
ap = argparse.ArgumentParser()
ap.add_argument('--mode', default='stills')
ap.add_argument('--res', default='')
ap.add_argument('--samples', type=int, default=0)
ap.add_argument('--exposure', type=float, default=0.6)
ap.add_argument('--only', default='')
ap.add_argument('--quality', default='film')
ap.add_argument('--segment', type=int, default=120,
                help='video: frames baked and rendered at a time (the sky cache of each is deleted after it)')
args = ap.parse_args(argv)
VIDEO = args.mode == 'video'
W, H = (int(v) for v in (args.res or ('640x360' if VIDEO else '960x540')).split('x'))
SAMPLES = args.samples or (8 if VIDEO else 16)
OUT = os.path.join(HERE, 'out', 'street')
os.makedirs(OUT, exist_ok=True)
FPS = 24
F0, F1 = 913, 1392                    # the shot: 38 s - 58 s
fails = []


def check(name, ok, detail=''):
    print(('PASS ' if ok else 'FAIL ') + name + (('  ' + str(detail)) if detail != '' else ''), flush=True)
    if not ok:
        fails.append(name)


def frame_of(t):
    return int(round(1 + t * FPS))


bpy.ops.wm.read_factory_settings(use_empty=True)
sc = bpy.context.scene
sc.render.engine = 'BLENDER_EEVEE'
sc.render.resolution_x, sc.render.resolution_y, sc.render.resolution_percentage = W, H, 100
sc.render.fps = FPS
sc.frame_start, sc.frame_end = 1, F1
sc.eevee.taa_render_samples = SAMPLES
sc.eevee.use_raytracing = True
sc.eevee.ray_tracing_options.resolution_scale = '1'
sc.eevee.use_shadows = True
sc.view_settings.view_transform = 'AgX'
sc.view_settings.look = 'None'
sc.view_settings.exposure = args.exposure
sc.render.image_settings.media_type = 'IMAGE'
sc.render.image_settings.file_format = 'PNG'
S = build_street(sc, rooms=args.mode != 'check')
# the WebGPU runner's auto-enhance bloom, at its defaults (UnrealBloom strength 0.25, radius 0.4, threshold 0.85): the
# bolt's x26 core and the burn puff's ember were tuned to glow through it. Set before the sky's fog splices in.
from eidoblend.look.post import chain  # noqa: E402
chain.set_bloom(sc, strength=0.25, size=0.4, threshold=0.85)
cam = S['camera']
# the walk: 0.55 m/s down the street through the shot, a slight pan; held before and after
from eidoblend.weather.keys import key_series  # noqa: E402
walk = [(F0, -8.0, 4.0), (F1, -8.0 + 0.55 * (F1 - F0) / FPS, -3.0)]
key_series(cam, 'location', [w[0] for w in walk], [(2.2, w[1], 1.62) for w in walk], 'LINEAR')
key_series(cam, 'rotation_euler', [w[0] for w in walk], [(math.radians(91.5), 0.0, math.radians(w[2])) for w in walk],
           'LINEAR')
for ob in S['collection'].objects:              # the roofs opt out of local strikes (the JS userData
    if ob.name.startswith('building_'):         # noLightningStrike), so a local strike lands in the street
        ob['eido_noLightningStrike'] = 1
t_build = time.time()
sky = make_sky(sc, camera=cam, hours=17.0, weather='rain', cache_dir=os.path.join(OUT, 'cache_' + args.mode),
               quality=args.quality)
sky.use_fog(density=0.0012)
sky.transition_to('darkstorm', 1.0, 9.0, at=39.0)
wx = make_weather_system(sc, sky, strike_targets=[S['collection']], occluders=S['collection'],
                         storm_center=(0.0, 380.0), storm_range=420.0)
nw = wx.wrap_scene()
rows = wx.bake(frame_start=F0, frame_end=F1, bake_sky=False)        # plan + keys; the sky bakes per still / segment
print('[test] built and baked weather in %.1fs (%d materials wrapped)' % (time.time() - t_build, nw), flush=True)
events = [e for e in wx.sched.events if F0 <= frame_of(e['time']) <= F1]
local = [e for e in events if e['strike']['local']]
far = [e for e in events if not e['strike']['local']]
cam_at = {r['frame']: r['cam_matrix'] for r in rows}
for e in events:
    f = frame_of(e['time'])
    sb = wx._rows[f]['strike_blender']
    m = cam_at[f]
    e['distance'] = math.dist((sb['x'], sb['y'], sb['z']), (m[0][3], m[1][3], m[2][3]))
print('[test] events in the shot:', [(round(e['time'], 2), frame_of(e['time']), e['color_key'],
                                      'local ' + e['strike']['kind'] if e['strike']['local'] else 'distant',
                                      '%.0f m' % e['distance']) for e in events], flush=True)
check('a local strike lands in the shot', len(local) >= 1)
strike = local[0] if local else (events[0] if events else None)
fstrike = frame_of(strike['time']) if strike else F0 + 120
r0 = wx._rows[F0]
print('[test] at the shot start: wetness %.3f, pooled water %.3f, rainK %.2f' % (r0['wetness'], r0['surface_water'],
                                                                                  r0['rain_k']), flush=True)
check('the pre-roll has wet the street before the shot opens', r0['wetness'] > 0.6 and r0['surface_water'] > 0.2)


def img(path):
    from PIL import Image
    return np.asarray(Image.open(path).convert('RGB')).astype(np.float64) / 255.0


if args.mode == 'check':                         # build, plan and key only (no GPU): setup errors, the schedule
    print('[test] strike frame', fstrike, 'rows', len(rows), flush=True)
    print('[test] moisture under the camera at the shot start: wet %.3f water %.3f'
          % tuple(wx._moist.sample(2.2, -8.0)[0]), flush=True)
elif not VIDEO:
    shots = dict(rain_before_storm=F0 + 12, before_strike=fstrike - 3, strike=fstrike, sparks=fstrike + 2,
                 smoke=fstrike + 30, storm=F1 - 6)
    if far:
        shots['distant_strike'] = frame_of(far[0]['time'])
    if args.only:
        shots = {k: v for k, v in shots.items() if k in args.only.split(',')}
    paths = {}
    for name, f in sorted(shots.items(), key=lambda kv: kv[1]):
        t0 = time.time()
        with wx._generators_off():
            sky.bake(f, f, log=lambda *a: None)
        sc.frame_set(f)
        p = os.path.join(OUT, '%s_f%04d.png' % (name, f))
        sc.render.filepath = p
        t1 = time.time()
        bpy.ops.render.render(write_still=True)
        print('[test] %s frame %d t=%.2fs: sky %.1fs, render %.1fs' % (name, f, (f - 1) / FPS, t1 - t0,
                                                                       time.time() - t1), flush=True)
        paths[name] = p
    if 'strike' in paths and 'before_strike' in paths:
        a, b = img(paths['before_strike']), img(paths['strike'])
        ground = (slice(int(H * 0.62), H), slice(0, W))
        r = b[ground].mean() / max(1e-6, a[ground].mean())
        check('the strike lights the street (ground brighter than 3 frames before)', r > 1.3, 'x%.2f' % r)
    from PIL import Image, ImageDraw
    order = [k for k in ('rain_before_storm', 'before_strike', 'strike', 'sparks', 'smoke', 'distant_strike', 'storm')
             if k in paths]
    sheet = Image.new('RGB', (W * 2, H * ((len(order) + 1) // 2)))
    for i, k in enumerate(order):
        im = Image.open(paths[k]).convert('RGB')
        ImageDraw.Draw(im).text((8, 6), '%s  f%d' % (k, shots[k]), fill=(255, 255, 255))
        sheet.paste(im, ((i % 2) * W, (i // 2) * H))
    sheet.save(os.path.join(OUT, 'storm_street_sheet.png'))
else:
    frames_dir = os.path.join(OUT, 'frames')
    os.makedirs(frames_dir, exist_ok=True)
    for f in os.listdir(frames_dir):
        os.remove(os.path.join(frames_dir, f))
    sc.render.filepath = os.path.join(frames_dir, '')
    t0 = time.time()
    seg = max(1, args.segment)
    for a in range(F0, F1 + 1, seg):              # bake + render a segment, then drop its regenerable caches
        b = min(F1, a + seg - 1)
        ts = time.time()
        wx.bake(frame_start=a, frame_end=b, bake_sky=True)
        tb = time.time()
        sc.frame_start, sc.frame_end = a, b
        bpy.ops.render.render(animation=True)
        sc.frame_start, sc.frame_end = 1, F1
        for d in (sky.cache_dir, wx.cache_dir):
            for fn in os.listdir(d):
                if fn.endswith('.exr') and fn.startswith(('sky_', 'moisture_')):
                    os.remove(os.path.join(d, fn))
        print('[test] frames %d-%d: weather + sky bake %.1fs, render %.1fs' % (a, b, tb - ts, time.time() - tb),
              flush=True)
    print('[test] rendered %d frames in %.1fs' % (F1 - F0 + 1, time.time() - t0), flush=True)
    sc.frame_start = 1
    video = os.path.join(OUT, 'storm_street_video.mp4')
    r = subprocess.run(['ffmpeg', '-y', '-loglevel', 'error', '-framerate', str(FPS), '-start_number', str(F0), '-i',
                        os.path.join(frames_dir, '%04d.png'), '-c:v', 'libx264', '-profile:v', 'high', '-pix_fmt',
                        'yuv420p', '-crf', '18', video], capture_output=True, text=True)
    check('frames encoded to H.264', r.returncode == 0 and os.path.exists(video), r.stderr[-300:])
    wav = os.path.join(OUT, 'storm_street_weather.wav')
    msg = wx.bake_audio(wav, frame_start=F0, duration=(F1 - F0 + 1) / FPS)
    print('[test]', msg, flush=True)
    tl = json.load(open(os.path.splitext(wav)[0] + '.json', encoding='utf-8'))
    check('audio timeline: rain bed, wind bed and the thunder of every strike in the shot',
          len(tl['rain']) > 0 and len(tl['wind']) > 0 and tl['stats']['strikes'] == len(events), tl['stats'])
    out_av = os.path.join(OUT, 'storm_street_av.mp4')
    msg = wx.merge_av(video, wav, out_av)
    print('[test]', msg.splitlines()[-1] if msg else '', flush=True)
    pr = subprocess.run(['ffprobe', '-v', 'error', '-show_entries', 'stream=codec_type,codec_name,profile', '-of',
                         'json', out_av], capture_output=True, text=True)
    st = json.loads(pr.stdout or '{}').get('streams', [])
    check('the film plays: H.264 High video and AAC audio',
          any(s.get('codec_name') == 'h264' and s.get('profile') == 'High' for s in st)
          and any(s.get('codec_name') == 'aac' for s in st), st)
    import wave
    with wave.open(wav) as wf:
        n = wf.getnframes()
        sr = wf.getframerate()
        data = np.frombuffer(wf.readframes(n), np.int16).reshape(-1, wf.getnchannels()).astype(np.float64)
    env = np.sqrt(np.convolve((data ** 2).mean(axis=1), np.ones(int(sr * 0.01)) / int(sr * 0.01), 'same'))
    for e in events:
        want = e['time'] - (F0 - 1) / FPS + e['distance'] / 343.0
        if want > n / sr - 0.3:
            print('[test] the clap of the strike at %.2fs lands after the shot (%.2fs)' % (e['time'], want), flush=True)
            continue
        if e['strike']['local'] or e['distance'] <= 150:          # the explosive clap: a transient on the beat
            lo_i = int(max(0.0, want - 0.6) * sr)
            hi_i = int(min(n / sr, want + 0.6) * sr)
            onset = (lo_i + int(np.argmax(np.diff(env[lo_i:hi_i])))) / sr
            check('the clap of the local strike lands on it + %.0f m / 343 m/s (want %.2fs, onset %.2fs)'
                  % (e['distance'], want, onset), abs(onset - want) < 0.25)
        else:                                                      # a rolling take swells from its time on
            pre = env[int(max(0.0, want - 1.5) * sr):int(want * sr)].mean()
            post = env[int(want * sr):int(min(n / sr, want + 1.5) * sr)].mean()
            check('the thunder of the %.0f m strike swells from its strike + %.0f m / 343 m/s (%.2fs: x%.2f)'
                  % (e['distance'], e['distance'], want, post / max(pre, 1e-9)), post > pre * 1.3)
print('RESULT', 'PASS' if not fails else 'FAIL (%d)' % len(fails), flush=True)
