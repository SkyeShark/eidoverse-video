"""The app's soundscape (src/audio/ambience.js) laid out by seedthree.scene.ambience over a
minute of film, checked against the JS schedule and envelopes, and mixed down to WAV.

    bash run_blender.sh blender/tests/trees2/ambience_mixdown.py [temperate] [desert]

Checks per biome: the looping wind bed covers the whole range, end to end; its start is
the JS's linear 1.6 s fade under the master's 0.35 s approach; bird calls start
6-18 s (desert 8-24 s) apart, each a variant of the biome's kinds at rate 0.96-1.05, peak
0.06-0.14, pan +-0.7; each keyed envelope equals the JS exponential ramps at sample
times. The mixdown (out/ambience_<biome>.wav, 48 kHz stereo): the steady wind bed
measures WIND_LEVEL x the source loop's RMS; every call lifts the level while it plays,
on the side its pan says.
"""

import math
import os
import sys
import time
import wave

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import _scene as S  # noqa: E402
import bpy  # noqa: E402
import numpy as np  # noqa: E402

from eidoblend.trees import raw  # noqa: E402

FPS = 24
SECONDS = 60


def fcurve_value(strip, frame):
    ad = strip.id_data.animation_data
    from seedthree.scene.ambience import _fcurves
    for fc in _fcurves(ad.action):
        if fc.data_path == strip.path_from_id('volume'):
            return fc.evaluate(frame)
    return strip.volume


def js_bird_gain(t, dur, peak):
    """ambience.js playBird's gain at t seconds into a call of dur seconds."""
    fin = min(0.35, dur * 0.3)
    t1 = max(fin, dur - min(0.8, dur * 0.45))
    if t <= fin:
        return 0.0001 * (peak / 0.0001) ** (t / fin)
    if t <= t1:
        return peak
    return peak * (0.0001 / peak) ** ((t - t1) / (dur - t1))


def read_wav(path):
    w = wave.open(path)
    n, ch, rate = w.getnframes(), w.getnchannels(), w.getframerate()
    a = np.frombuffer(w.readframes(n), np.int16).astype(np.float32) / 32768.0
    return a.reshape(-1, ch), rate


def rms(x):
    return float(np.sqrt(np.mean(np.square(x)))) if len(x) else 0.0


def biome_test(biome):
    api = raw()
    from seedthree.scene import ambience as A
    scene = S.reset()
    scene.render.fps = FPS
    scene.render.fps_base = 1.0
    scene.frame_start, scene.frame_end = 1, SECONDS * FPS
    strips = A.build_ambience(scene, biome=biome, seed=1)
    beds = [s for s in strips if s.name.startswith('SeedThree wind')]
    calls = sorted([s for s in strips if not s.name.startswith('SeedThree wind')], key=lambda s: s.frame_final_start)
    cover = beds and beds[0].frame_final_start <= scene.frame_start and beds[-1].frame_final_end > scene.frame_end and all(
        a.frame_final_end == b.frame_final_start for a, b in zip(beds, beds[1:]))
    S.check('%s wind bed covers the minute end to end' % biome, cover,
            '%d copies of %.1f s' % (len(beds), beds[0].frame_final_duration / FPS if beds else 0))
    f0 = beds[0].frame_final_start
    errs = []
    n = int(math.ceil(7 * 0.35 * FPS))
    for i in range(n):
        t = i / FPS
        bed = 0.0001 + (A.WIND_LEVEL - 0.0001) * min(1.0, t / 1.6)
        want = bed * (1 - math.exp(-t / 0.35))
        errs.append(abs(fcurve_value(beds[0], f0 + i) - want * A.BED_GAIN))
    errs.append(abs(fcurve_value(beds[0], f0 + n + 24) - A.WIND_LEVEL * A.BED_GAIN))   # then the level itself
    S.check('%s wind fade-in = linear 1.6 s x the master approach' % biome, max(errs) < 1e-7, 'max error %.2e' % max(errs))
    lo, hi = A.INTERVAL['desert' if biome == 'desert' else 'temperate']
    starts = [scene.frame_start / FPS] + [s.frame_final_start / FPS for s in calls]
    gaps = [b - a for a, b in zip(starts, starts[1:])]
    S.check('%s calls %d-%d s apart' % (biome, lo, hi), calls and all(lo - 0.05 <= g <= hi + 0.05 for g in gaps),
            '%d calls, gaps %s s' % (len(calls), ', '.join('%.1f' % g for g in gaps)))
    kinds = A.BIRD_KINDS['desert' if biome == 'desert' else 'temperate']
    meta = [dict(s['st_call']) for s in calls]
    S.check('%s calls: kinds, rate, peak, pan in the JS ranges' % biome, all(
        m['kind'] in kinds and 0.96 <= m['rate'] <= 1.05 and 0.06 <= m['peak'] <= 0.14 for m in meta) and all(
        -0.7 <= s.pan <= 0.7 for s in calls), '; '.join('%s r%.3f p%.3f pan%+.2f' % (m['file'], m['rate'], m['peak'], s.pan)
                                                       for m, s in zip(meta, calls)))
    worst = 0.0
    for s, m in zip(calls, meta):
        dur = m['dur_frames'] / FPS        # the call's length at its playback rate
        for frac in (0.0, 0.1, 0.25, 0.5, 0.8, 0.95, 1.0):
            t = frac * dur
            got = fcurve_value(s, s.frame_final_start + t * FPS)
            want = js_bird_gain(t, dur, m['peak'])
            worst = max(worst, abs(math.log(max(got, 1e-6)) - math.log(want)))
    # between per-frame keys the gain is linear: at most ~0.1 in log gain off the true exponential
    S.check('%s call envelopes = the JS exponential ramps (frame-keyed)' % biome, worst < 0.15,
            'worst log-gain error %.3f' % worst)
    path = os.path.join(S.OUT, 'ambience_%s.wav' % biome).replace('\\', '/')
    if os.path.exists(path):
        os.remove(path)
    bpy.ops.sound.mixdown(filepath=path, check_existing=False, container='WAV', codec='PCM', format='S16',
                          mixrate=48000, channels='STEREO', accuracy=1024)
    # Blender 5.2 mixes down in a worker thread (a wm job): the operator returns at once and
    # the file grows behind it. Wait for the full length (a reset or quit would cut it short).
    want_bytes = (scene.frame_end - scene.frame_start + 1) * 48000 // FPS * 4
    t0 = time.time()
    while time.time() - t0 < 180:
        if os.path.isfile(path) and os.path.getsize(path) >= want_bytes:
            break
        time.sleep(0.25)
    time.sleep(0.5)
    ok = os.path.isfile(path) and os.path.getsize(path) >= want_bytes
    S.check('%s mixdown written' % biome, ok, '%s (%.1f MB in %.1f s)' % (
        path, os.path.getsize(path) / 1e6 if os.path.isfile(path) else 0, time.time() - t0))
    if not ok:
        return
    mix, rate = read_wav(path)
    src, srate = read_wav(os.path.join(api.ASSETS_DIR, 'audio', 'wind_%s.wav' % ('desert' if biome == 'desert' else 'temperate')))
    busy = np.zeros(len(mix), bool)
    for s in calls:
        a = int((s.frame_final_start - 1) / FPS * rate)
        b = int((s.frame_final_end - 1) / FPS * rate)
        busy[max(0, a - rate // 10):min(len(mix), b + rate // 10)] = True
    steady = np.zeros(len(mix), bool)
    steady[int(3 * rate):] = True
    quiet = mix[steady & ~busy].mean(axis=1)
    want = A.WIND_LEVEL * rms(src[:, 0])
    got = rms(quiet)
    S.check('%s steady wind bed level' % biome, abs(got - want) <= 0.25 * want,
            'mix RMS %.5f vs WIND_LEVEL x source RMS %.5f' % (got, want))
    lifted = []
    for s in calls:
        a = int((s.frame_final_start - 1) / FPS * rate)
        b = int((s.frame_final_end - 1) / FPS * rate)
        seg = mix[a:b]
        lv, rv = rms(seg[:, 0]), rms(seg[:, 1])
        side_ok = (lv >= rv) if s.pan < -0.15 else (rv >= lv) if s.pan > 0.15 else True
        lifted.append((rms(seg.mean(axis=1)) > 1.5 * got, side_ok, s.pan, lv, rv))
    S.check('%s every call is heard, on its pan side' % biome, lifted and all(a and b for a, b, *_ in lifted),
            '; '.join('pan%+.2f L%.4f R%.4f' % (p, lv, rv) for _, _, p, lv, rv in lifted))


def main():
    a = S.args()
    for biome in [b for b in ('temperate', 'desert') if b in a] or ['temperate', 'desert']:
        biome_test(biome)
    S.summary('ambience_mixdown')


main()
