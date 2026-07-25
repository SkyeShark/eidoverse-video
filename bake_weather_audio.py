#!/usr/bin/env python3
"""Bake a weather_audio.js timeline into a WAV track.

    python bake_weather_audio.py work/<id>/wx_audio.json --out wx.wav --duration 274

The renderer is headless and writes frames to ffmpeg, so nothing can *play*
during a render (Deno has no Web Audio API). eidoverse/weather_audio.js
instead records which thunder takes fire and when, plus the rain envelope;
this turns that list into a real stereo track you can mux with merge_av.py.

Rain is the loop tiled to length with its gain automated from the recorded
envelope; each thunder event is the source clip delayed to its timestamp,
pitched by its rate, trimmed to its measured onset, and (for close tails)
low-passed -- the same parameters the browser build would have applied.
"""
import argparse, json, math, os, shlex, subprocess, sys


def build_filters(tl, duration):
    """-> (input args, filter_complex, output label)"""
    inputs, filters, mix = [], [], []
    idx = 0

    rain = tl.get("rain") or []
    if rain and any(p["gain"] > 0.0005 for p in rain):
        inputs += ["-stream_loop", "-1", "-i", tl["rainClip"]]
        # piecewise-linear gain automation from the recorded envelope
        expr_parts, prev_t, prev_g = [], 0.0, rain[0]["gain"]
        for p in rain:
            t, g = float(p["t"]), float(p["gain"])
            if t > prev_t:
                slope = (g - prev_g) / (t - prev_t)
                expr_parts.append(
                    f"between(t,{prev_t:.3f},{t:.3f})*({prev_g:.4f}+({slope:.6f})*(t-{prev_t:.3f}))")
            prev_t, prev_g = t, g
        expr_parts.append(f"gte(t,{prev_t:.3f})*{prev_g:.4f}")
        vol = "+".join(expr_parts) if expr_parts else f"{prev_g:.4f}"
        filters.append(
            f"[{idx}:a]atrim=0:{duration},volume='{vol}':eval=frame,"
            f"aformat=sample_fmts=fltp:sample_rates=48000:channel_layouts=stereo[rain]")
        mix.append("[rain]")
        idx += 1

    for n, ev in enumerate(tl.get("events") or []):
        clip = ev["clip"]
        if not os.path.exists(clip):
            print(f"  ! missing clip, skipped: {clip}", file=sys.stderr)
            continue
        inputs += ["-i", clip]
        chain = []
        if ev.get("offset", 0) > 0:
            chain.append(f"atrim=start={ev['offset']:.4f}")
            chain.append("asetpts=PTS-STARTPTS")
        if ev.get("stopAfter"):
            # the browser stops this voice early (the mid-range snap layer)
            chain.append(f"atrim=0:{float(ev['stopAfter']):.4f}")
            chain.append("asetpts=PTS-STARTPTS")
        rate = float(ev.get("rate", 1) or 1)
        if abs(rate - 1) > 1e-4:
            # asetrate repitches (the browser's playbackRate); restore the
            # nominal rate afterward so the mixer sees a uniform 48k.
            chain.append(f"asetrate=48000*{rate:.5f}")
            chain.append("aresample=48000")
        if ev.get("highpassHz"):
            chain.append(f"highpass=f={int(ev['highpassHz'])}")
        if ev.get("lowpassHz"):
            chain.append(f"lowpass=f={int(ev['lowpassHz'])}")
        # AIR ABSORPTION — high frequencies are lost over distance, which is
        # why far thunder rumbles and near thunder cracks. The event gain
        # already carries the inverse-square-ish falloff; without this the
        # spectrum stays bright and a 2 km strike still sounds close, just
        # quieter. Only bites past ~1 km, so near strikes keep their snap.
        d = float(ev.get("distance", 0) or 0)
        if d > 400:
            cut = max(1200, min(20000, 20000 * math.exp(-d / 2500.0)))
            chain.append(f"lowpass=f={int(cut)}")
        chain.append("aformat=sample_fmts=fltp:sample_rates=48000:channel_layouts=stereo")
        # STEREO PLACEMENT — equal-power pan from the recorded azimuth.
        # Weights the existing channels rather than downmixing to mono first,
        # so the field recordings keep their natural width while still landing
        # on the correct side of the listener.
        pan = max(-1.0, min(1.0, float(ev.get("pan", 0) or 0)))
        if abs(pan) > 0.01:
            ang = (pan + 1.0) * (math.pi / 4.0)      # 0 .. pi/2
            gl, gr = math.cos(ang), math.sin(ang)
            # *sqrt(2) so a centred source is unity rather than -3 dB
            gl *= math.sqrt(2); gr *= math.sqrt(2)
            chain.append(f"pan=stereo|c0={gl:.4f}*c0|c1={gr:.4f}*c1")
        chain.append(f"volume={float(ev.get('gain', 1)):.4f}")
        ms = int(round(float(ev["t"]) * 1000))
        chain.append(f"adelay={ms}|{ms}")
        filters.append(f"[{idx}:a]" + ",".join(chain) + f"[e{n}]")
        mix.append(f"[e{n}]")
        idx += 1

    if not mix:
        return None, None, None
    # normalize=0 keeps authored levels; a single loud clap must stay loud
    # instead of ducking everything else the way amix's averaging would.
    filters.append(
        f"{''.join(mix)}amix=inputs={len(mix)}:duration=longest:normalize=0,"
        f"atrim=0:{duration},alimiter=limit=0.95[out]")
    return inputs, ";".join(filters), "[out]"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("timeline")
    ap.add_argument("--out", default="weather_audio.wav")
    ap.add_argument("--duration", type=float, default=None)
    a = ap.parse_args()

    tl = json.load(open(a.timeline, encoding="utf-8"))
    evs = tl.get("events") or []
    dur = a.duration or (max((e["t"] for e in evs), default=0) + 12)

    inputs, fc, out = build_filters(tl, dur)
    if not fc:
        print("Nothing to bake — no rain and no thunder in this timeline.")
        return 1

    cmd = (["ffmpeg", "-y"] + inputs
           + ["-filter_complex", fc, "-map", out, "-c:a", "pcm_s16le", a.out])
    print(f"baking {len(evs)} thunder event(s) + "
          f"{len(tl.get('rain') or [])} rain points -> {a.out} ({dur:.1f}s)")
    r = subprocess.run(cmd, capture_output=True, text=True)
    if r.returncode != 0:
        print(r.stderr[-2500:], file=sys.stderr)
        print("\nffmpeg failed. Command:\n " + " ".join(shlex.quote(c) for c in cmd),
              file=sys.stderr)
        return r.returncode
    s = tl.get("stats", {})
    print(f"  ok — {a.out}  (strikes {s.get('strikes', 0)}: "
          f"{s.get('explosive', 0)} explosive / {s.get('close', 0)} close / "
          f"{s.get('distant', 0)} distant, peak rain {s.get('maxRain', 0):.2f})")
    return 0


if __name__ == "__main__":
    sys.exit(main())
